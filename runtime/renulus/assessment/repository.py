"""Durable reviewed quizzes with atomic scoring and family exposure."""
from collections import defaultdict
import json

from renulus.contracts import ApiError, durable_id
from renulus.storage.database import utc_now

from .content import ContentGateway
from .contracts import Selector


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class AssessmentRepository:
    def __init__(self, services):
        self.services = services
        self.db = services.db
        self.content = ContentGateway(services)

    @staticmethod
    def _one(conn, sql, parameters=()):
        row = conn.execute(sql, parameters).fetchone()
        return dict(row) if row else None

    def _session(self, conn, session_id):
        session = self._one(conn, "SELECT * FROM assessment_sessions WHERE id=?", (session_id,))
        if session is None:
            raise ApiError("session_not_found", "This assessment session was not found", 404)
        return session

    def _item(self, conn, session_id, item_id):
        item = self._one(conn, "SELECT * FROM assessment_items WHERE id=? AND session_id=?",
                         (item_id, session_id))
        if item is None:
            raise ApiError("item_not_found", "This item does not belong to the session", 404)
        return item

    @staticmethod
    def _require_active(session):
        if session["status"] != "active":
            raise ApiError("session_not_active", "Resume this session before answering or asking for help",
                           409)

    def _replay(self, conn, key, operation, target, request):
        previous = self._one(conn, "SELECT * FROM assessment_commands WHERE idempotency_key=?",
                             (key,))
        if previous is None:
            return None
        if (previous["operation"] != operation or previous["target"] != target
                or previous["request_json"] != encode(request)):
            raise ApiError("idempotency_conflict",
                           "This request key was already used for a different action", 409)
        return json.loads(previous["result_json"])

    @staticmethod
    def _record(conn, key, operation, target, request, result):
        conn.execute("INSERT INTO assessment_commands VALUES(?,?,?,?,?,?)",
                     (key, operation, target, encode(request), encode(result), utc_now()))

    def _repeat(self, conn, item):
        return self._one(conn,
            "SELECT 1 FROM assessment_exposure WHERE family_id=? AND item_id<>? LIMIT 1",
            (item["family_id"], item["id"])) is not None

    @staticmethod
    def _expose(conn, item, kind):
        conn.execute("INSERT OR IGNORE INTO assessment_exposure VALUES(?,?,?,?,?,?,?)",
                     (durable_id("exposure"), item["family_id"], item["question_id"],
                      item["question_version"], item["id"], kind, utc_now()))

    @staticmethod
    def _public_item(item):
        question = json.loads(item["snapshot_json"])
        # Explicit allowlist: option rationales, keys, sources and reviewer notes
        # must never accidentally leak through a future content schema change.
        return {"id": item["id"], "ordinal": item["ordinal"],
                "question_id": item["question_id"],
                "question_version": item["question_version"],
                "key_version": item["key_version"],
                "family_id": item["family_id"], "family_version": item["family_version"],
                "topic_id": item["topic_id"], "domain_id": item["domain_id"],
                "kind": question["kind"], "stem": question["stem"],
                "options": [{"id": option["id"], "text": option["text"]}
                            for option in question["options"]],
                "assisted": bool(item["assisted"])}

    def _scores(self, conn, session_id=None):
        where = " WHERE session_id=?" if session_id else ""
        params = (session_id,) if session_id else ()
        rows = conn.execute(
            "SELECT score_bucket,COUNT(*) AS answered,SUM(correct) AS correct "
            "FROM assessment_attempts" + where + " GROUP BY score_bucket", params).fetchall()
        scores = {name: {"answered": 0, "correct": 0, "accuracy": None}
                  for name in ("fresh", "assisted", "repeat")}
        for row in rows:
            scores[row["score_bucket"]] = {"answered": row["answered"],
                "correct": row["correct"], "accuracy": row["correct"] / row["answered"]}
        return {"reviewed": scores, "generated": {"available": False, "answered": 0},
                "bucket_policy": "assisted takes precedence over repeat; both attempt flags are retained"}

    def _view(self, conn, session_id, present=False):
        session = self._session(conn, session_id)
        counts = conn.execute(
            "SELECT COUNT(*) AS total,COUNT(a.id) AS answered FROM assessment_items i "
            "LEFT JOIN assessment_attempts a ON a.item_id=i.id WHERE i.session_id=?",
            (session_id,)).fetchone()
        result = {"id": session_id, "mode": session["mode"],
                  "scope": {"kind": session["scope"], "entity_id": session_id},
                  "status": session["status"], "created_at": session["created_at"],
                  "updated_at": session["updated_at"], "ended_at": session["ended_at"],
                  "selector": json.loads(session["selector_json"]),
                  "coverage": json.loads(session["coverage_json"]),
                  "item_count": counts["total"], "answered_count": counts["answered"],
                  "scores": self._scores(conn, session_id), "current_item": None}
        if present and session["status"] == "active":
            item = self._one(conn,
                "SELECT i.* FROM assessment_items i LEFT JOIN assessment_attempts a ON a.item_id=i.id "
                "WHERE i.session_id=? AND a.id IS NULL ORDER BY i.ordinal LIMIT 1", (session_id,))
            if item:
                self._expose(conn, item, "presented")
                if item["presented_at"] is None:
                    conn.execute("UPDATE assessment_items SET presented_at=? WHERE id=?",
                                 (utc_now(), item["id"]))
                result["current_item"] = {**self._public_item(item),
                                          "repeat": self._repeat(conn, item),
                                          "content_status": self.content.annotation(item)}
        return result

    def catalog(self, selector=None):
        selector = selector or Selector()
        with self.db.transaction() as conn:
            summaries = self.content.summaries(selector)
            topics = self.content.topics()
            by_topic = defaultdict(set)
            for summary in summaries:
                by_topic[summary["topic_id"]].add(summary["family_id"])
            return {"mode": "reviewed",
                    "domains": [{"id": topic["id"], "label": topic["label"],
                                 "available_families": len(by_topic[topic["id"]])}
                                for topic in topics],
                    "available_families": len({q["family_id"] for q in summaries}),
                    "tracks": [{"id": "general_nephrology", "available": True},
                               {"id": "esen_eph", "available": False,
                                "reason": "The installed pack is not formally mapped to ESENeph"}],
                    "complete_exam_available": False,
                    "coverage_note": "A selected quiz is not a complete curriculum or exam simulation",
                    "generated": {"available": False,
                                  "reason": "Approved practice generation is not connected"}}

    def _choose(self, conn, summaries, count):
        exposures = {row["family_id"]: row["n"] for row in conn.execute(
            "SELECT family_id,COUNT(*) AS n FROM assessment_exposure GROUP BY family_id")}
        groups = defaultdict(list)
        for summary in sorted(summaries, key=lambda q: (exposures.get(q["family_id"], 0), q["id"])):
            groups[summary["topic_id"]].append(summary)
        chosen, families = [], set()
        domains = sorted(groups, key=lambda d: (
            min(exposures.get(q["family_id"], 0) for q in groups[d]), d))
        while len(chosen) < count and any(groups.values()):
            for domain in domains:
                while groups[domain] and groups[domain][0]["family_id"] in families:
                    groups[domain].pop(0)
                if groups[domain] and len(chosen) < count:
                    candidate = groups[domain].pop(0)
                    chosen.append(candidate)
                    families.add(candidate["family_id"])
        return chosen

    def start(self, request):
        if request.mode == "generated":
            raise ApiError("generated_practice_unavailable",
                           "Approved practice generation is not connected; choose a reviewed quiz",
                           503, True)
        body = request.model_dump(exclude={"idempotency_key"})
        with self.db.transaction() as conn:
            previous = self._replay(conn, request.idempotency_key, "start", "", body)
            if previous is not None:
                return previous
            summaries = self.content.summaries(request.selector)
            chosen = self._choose(conn, summaries, request.count)
            if not chosen:
                raise ApiError("insufficient_coverage",
                               "No reviewed items match this selection; choose other topics or install a pack",
                               409)
            questions = [self.content.pin(summary) for summary in chosen]
            topics = {q["topic_id"] for q in summaries}
            coverage = {"requested_count": request.count, "selected_count": len(questions),
                        "available_families": len({q["family_id"] for q in summaries}),
                        "insufficient_count": len(questions) < request.count,
                        "missing_topic_ids": sorted(set(request.selector.topic_ids) - topics),
                        "missing_domain_ids": sorted(set(request.selector.domain_ids) - topics),
                        "complete_exam_available": False,
                        "note": "Limited reviewed quiz coverage; this is not a complete exam simulation"}
            session_id, now = durable_id("assessment"), utc_now()
            conn.execute("INSERT INTO assessment_sessions VALUES(?,?,?,?,?,?,?,?,?)",
                         (session_id, "reviewed", "reviewed-assessment", "active",
                          encode(request.selector.model_dump()), encode(coverage), now, now, None))
            for ordinal, question in enumerate(questions, start=1):
                conn.execute("INSERT INTO assessment_items "
                    "(id,session_id,ordinal,question_id,question_version,key_version,family_id,"
                    "family_version,topic_id,domain_id,snapshot_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (durable_id("item"), session_id, ordinal, question["id"], str(question["version"]),
                     str(question["key_version"]), question["family_id"], str(question["family_version"]),
                     question["topic_id"], question["domain_id"], encode(question)))
            result = self._view(conn, session_id, present=True)
            self._record(conn, request.idempotency_key, "start", "", body, result)
            return result

    def session(self, session_id):
        # GET can reveal a question, therefore exposure is a deliberate durable
        # effect that completes before the transport can return that question.
        with self.db.transaction() as conn:
            return self._view(conn, session_id, present=True)

    def sessions(self):
        with self.db.transaction() as conn:
            rows = conn.execute("SELECT id FROM assessment_sessions ORDER BY updated_at DESC LIMIT 100")
            return {"sessions": [self._view(conn, row["id"]) for row in rows]}

    def _feedback(self, conn, item, attempt):
        question = json.loads(item["snapshot_json"])
        self._expose(conn, item, "reviewed")
        return {"attempt_id": attempt["id"], "item": self._public_item(item),
                "selected_option_ids": json.loads(attempt["answer_json"]),
                "correct_option_ids": question["correct_option_ids"],
                "correct": bool(attempt["correct"]), "score_bucket": attempt["score_bucket"],
                "assisted": bool(attempt["assisted"]), "repeat": bool(attempt["repeat"]),
                "committed_at": attempt["committed_at"],
                "explanation": question["explanation"],
                "options": [{"id": o["id"], "text": o["text"],
                             "rationale": o.get("rationale")} for o in question["options"]],
                "sources": question["sources"], "review": question["review"],
                "content_status": self.content.annotation(item)}

    def answer(self, session_id, request):
        body = request.model_dump(exclude={"idempotency_key"})
        with self.db.transaction() as conn:
            previous = self._replay(conn, request.idempotency_key, "answer", session_id, body)
            if previous is not None:
                return previous
            session = self._session(conn, session_id)
            self._require_active(session)
            item = self._item(conn, session_id, request.item_id)
            if self._one(conn, "SELECT id FROM assessment_attempts WHERE item_id=?", (item["id"],)):
                raise ApiError("answer_already_committed",
                               "This answer is committed; use the original request key to retry", 409)
            if item["presented_at"] is None:
                raise ApiError("item_not_presented", "Open this item before committing an answer", 409)
            annotation = self.content.annotation(item)
            if annotation["status"] in ("withdrawn", "inactive", "corrected", "unavailable"):
                raise ApiError("content_changed",
                               "This item is no longer current; end this session and choose a new quiz",
                               409, True)
            question = json.loads(item["snapshot_json"])
            options = {option["id"] for option in question["options"]}
            if len(request.option_ids) != 1 or not set(request.option_ids).issubset(options):
                raise ApiError("invalid_answer", "Choose one of this item's options", 422)
            correct = request.option_ids == sorted(question["correct_option_ids"])
            assisted, repeat = bool(item["assisted"]), self._repeat(conn, item)
            bucket = "assisted" if assisted else "repeat" if repeat else "fresh"
            attempt_id, now = durable_id("attempt"), utc_now()
            conn.execute("INSERT INTO assessment_attempts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (attempt_id, session_id, item["id"], item["question_id"], item["question_version"],
                 item["key_version"], item["family_id"], item["family_version"], item["topic_id"],
                 encode(request.option_ids), int(correct), int(assisted), int(repeat), bucket, now))
            self._expose(conn, item, "answered")
            # Only general activity evidence is eligible for memory/teaching.
            # Pinned bank snapshots and rationales stay inside assessment.
            evidence = {"scope": {"kind": "reviewed-assessment", "entity_id": session_id},
                        "mode": "reviewed", "session_id": session_id,
                        "attempt_id": attempt_id, "item_id": item["id"],
                        "question_id": item["question_id"],
                        "question_version": item["question_version"],
                        "key_version": item["key_version"], "family_id": item["family_id"],
                        "family_version": item["family_version"],
                        "topic_id": item["topic_id"], "objective_ids": question.get("objective_ids", []),
                        "objective_id": next(iter(question.get("objective_ids", [])), None),
                        "correct": correct, "assisted": assisted, "repeat": repeat,
                        "score_bucket": bucket}
            conn.execute("INSERT INTO learning_evidence VALUES(?,?,?,?,?,?)",
                         ("assessment:" + attempt_id, "assessment-answer",
                          item["topic_id"], attempt_id, encode(evidence), now))
            conn.execute("UPDATE assessment_sessions SET updated_at=? WHERE id=?", (now, session_id))
            attempt = self._one(conn, "SELECT * FROM assessment_attempts WHERE id=?", (attempt_id,))
            result = {"feedback": self._feedback(conn, item, attempt),
                      "session": self._view(conn, session_id)}
            self._record(conn, request.idempotency_key, "answer", session_id, body, result)
            return result

    def help(self, session_id, request):
        body = request.model_dump(exclude={"idempotency_key"})
        with self.db.transaction() as conn:
            previous = self._replay(conn, request.idempotency_key, "help", session_id, body)
            if previous is not None:
                return previous
            self._require_active(self._session(conn, session_id))
            item = self._item(conn, session_id, request.item_id)
            if item["presented_at"] is None:
                raise ApiError("item_not_presented", "Open this item before asking for help", 409)
            if self._one(conn, "SELECT id FROM assessment_attempts WHERE item_id=?", (item["id"],)):
                raise ApiError("answer_already_committed", "Use review for committed answers", 409)
            question = json.loads(item["snapshot_json"])
            hint = question.get("hint")
            if request.kind == "hint" and not hint:
                raise ApiError("hint_unavailable",
                               "This reviewed item has no authored hint; source help is available", 409)
            conn.execute("UPDATE assessment_items SET assisted=1 WHERE id=?", (item["id"],))
            self._expose(conn, item, request.kind)
            result = {"item_id": item["id"], "assisted": True,
                      "kind": request.kind, "hint": hint if request.kind == "hint" else None,
                      "sources": question["sources"] if request.kind == "sources" else []}
            self._record(conn, request.idempotency_key, "help", session_id, body, result)
            return result

    def review(self, session_id, item_id=None, mistakes_only=False):
        with self.db.transaction() as conn:
            self._session(conn, session_id)
            if item_id:
                item = self._item(conn, session_id, item_id)
                attempt = self._one(conn, "SELECT * FROM assessment_attempts WHERE item_id=?", (item_id,))
                if attempt is None:
                    raise ApiError("answer_not_committed",
                                   "Commit an answer before revealing its feedback", 409)
                feedback = [self._feedback(conn, item, attempt)]
            else:
                sql = "SELECT * FROM assessment_attempts WHERE session_id=?"
                if mistakes_only:
                    sql += " AND correct=0"
                attempts = conn.execute(sql + " ORDER BY committed_at,id", (session_id,)).fetchall()
                feedback = [self._feedback(conn, self._item(conn, session_id, a["item_id"]), dict(a))
                            for a in attempts]
            return {"session_id": session_id, "feedback": feedback,
                    "scores": self._scores(conn, session_id),
                    "unanswered_feedback_available": False}

    def transition(self, session_id, operation, request):
        with self.db.transaction() as conn:
            previous = self._replay(conn, request.idempotency_key, operation, session_id, {})
            if previous is not None:
                return previous
            session = self._session(conn, session_id)
            if operation == "resume" and session["status"] == "ended":
                raise ApiError("session_ended", "This session ended; start a new quiz", 409)
            if operation == "pause" and session["status"] == "ended":
                raise ApiError("session_ended", "This session already ended", 409)
            status = {"pause": "paused", "resume": "active", "end": "ended"}[operation]
            now = utc_now()
            conn.execute("UPDATE assessment_sessions SET status=?,updated_at=?,ended_at=? WHERE id=?",
                         (status, now, session["ended_at"] or now if status == "ended" else None, session_id))
            result = self._view(conn, session_id, present=operation == "resume")
            self._record(conn, request.idempotency_key, operation, session_id, {}, result)
            return result

    def aggregates(self):
        with self.db.transaction() as conn:
            return self._scores(conn)

    def progress_summary(self):
        """Observed activity only: this does not infer curriculum mastery."""
        with self.db.transaction() as conn:
            total = conn.execute("SELECT COUNT(*) AS count,MAX(committed_at) AS last_attempt_at "
                                 "FROM assessment_attempts").fetchone()
            return {"attempt_count": total["count"], "last_attempt_at": total["last_attempt_at"],
                    "scores": self._scores(conn), "mastery_inferred": False}

    def mistakes(self, limit=100):
        """Key-free study candidates. Detailed feedback stays in assessment."""
        with self.db.transaction() as conn:
            rows = conn.execute("SELECT * FROM assessment_attempts WHERE correct=0 "
                                "ORDER BY committed_at DESC,id LIMIT ?", (min(max(limit, 1), 100),))
            result = []
            for row in rows:
                attempt = dict(row)
                item = self._item(conn, attempt["session_id"], attempt["item_id"])
                snapshot = json.loads(item["snapshot_json"])
                result.append({"attempt_id": attempt["id"], "session_id": attempt["session_id"],
                               "item_id": attempt["item_id"], "topic_id": attempt["topic_id"],
                               "question_id": attempt["question_id"],
                               "question_version": attempt["question_version"],
                               "objective_id": next(iter(snapshot.get("objective_ids", [])), None),
                               "correct": False, "assisted": bool(attempt["assisted"]),
                               "repeat": bool(attempt["repeat"]),
                               "score_bucket": attempt["score_bucket"],
                               "committed_at": attempt["committed_at"],
                               "content_status": self.content.annotation(item)})
            return result
