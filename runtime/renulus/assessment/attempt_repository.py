# SPDX-License-Identifier: MIT
"""Durable Study commitments and atomic whole-Test submission. No provider work.

The integration lead installs migration004 and all cross-module disclosure gates.
Helpers ending in _in accept the caller's BEGIN IMMEDIATE transaction.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import time
from threading import RLock

from renulus.contracts import ApiError, durable_id
from renulus.design_c_contracts import SavedTestVersion

from .attempt_models import DraftState

POLICY_REVISION = "design_c.policy_revision"
TERMINAL = {"submitted", "ended"}
HELP_KINDS = {"hint", "sources", "notes", "chat"}


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def timestamp(value):
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds")


def parse(value):
    return datetime.fromisoformat(value) if value else None


def bump_policy_revision_in(conn, now):
    """Shared parent seam; call in the transaction starting/sealing a Test."""
    conn.execute("INSERT INTO preferences VALUES(?,'1',?) ON CONFLICT(key) DO UPDATE SET "
                 "value=CAST(CAST(preferences.value AS INTEGER)+1 AS TEXT),updated_at=excluded.updated_at",
                 (POLICY_REVISION, timestamp(now)))


class WholeAttemptRepository:
    def __init__(self, services, *, clock=None, monotonic=None):
        self.services, self.db = services, services.db
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.monotonic = monotonic or time.monotonic
        self._observations = {}
        self._lock = RLock()

    def _run(self, operation):
        # Expected refusals must not roll back an expiry reconciled just before
        # them. Storage/evidence failures still roll back the entire transaction.
        error = None
        with self._lock, self.db.transaction() as conn:
            self._ready(conn)
            self._reconcile_all_in(conn)
            try:
                result = operation(conn)
            except ApiError as caught:
                error = caught
        if error:
            raise error
        return result

    @staticmethod
    def _ready(conn):
        required = {"assessment_test_attempts", "assessment_attempt_drafts",
                    "assessment_attempt_exposure", "assessment_attempt_commands"}
        installed = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not required <= installed:
            raise ApiError("attempts_unavailable", "Attempt storage is not ready. Try again after updating Renulus.", 503, True)

    @staticmethod
    def _row(conn, attempt_id):
        row = conn.execute("SELECT * FROM assessment_test_attempts WHERE id=?", (attempt_id,)).fetchone()
        if row is None:
            raise ApiError("not_found", "This attempt is unavailable.", 404)
        return dict(row)

    @staticmethod
    def _version(row):
        return SavedTestVersion.model_validate_json(row["version_snapshot_json"])

    @staticmethod
    def _draft(conn, row):
        return dict(conn.execute("SELECT * FROM assessment_attempt_drafts WHERE attempt_id=?", (row["id"],)).fetchone())

    def _now_in(self, conn, row):
        wall = self.clock()
        if wall.tzinfo is None or wall.utcoffset() is None:
            raise RuntimeError("Attempt clock must be timezone aware")
        high = parse(row["clock_high_water_at"])
        tick = self.monotonic()
        previous = self._observations.get(row["id"])
        effective = max(wall, high or wall)
        if previous:
            effective = max(effective, previous[0] + timedelta(seconds=max(0, tick - previous[1])))
        elif high and wall < high - timedelta(seconds=1) and row["timing_kind"] == "timed" and row["status"] == "active":
            # After restart, elapsed time across an offline clock rollback is
            # unknowable. Conservatively expire rather than grant extra time.
            effective = max(effective, parse(row["deadline_at"]))
        self._observations[row["id"]] = (effective, tick)
        row["clock_high_water_at"] = row["last_reconciled_at"] = timestamp(effective)
        conn.execute("UPDATE assessment_test_attempts SET clock_high_water_at=?,last_reconciled_at=? WHERE id=?",
                     (row["clock_high_water_at"], row["last_reconciled_at"], row["id"]))
        return effective

    def _reconcile_all_in(self, conn):
        rows = conn.execute("SELECT * FROM assessment_test_attempts WHERE status IN ('active','paused')").fetchall()
        for stored in rows:
            row = dict(stored)
            now = self._now_in(conn, row)
            if row["status"] == "active" and row["deadline_at"] and now >= parse(row["deadline_at"]):
                if row["mode"] == "test":
                    self._finalise_in(conn, row, now, "deadline")
                else:
                    conn.execute("UPDATE assessment_test_attempts SET status='timer_expired',updated_at=? WHERE id=?",
                                 (timestamp(now), row["id"]))

    def policy_in(self, conn):
        """Expiry + policy lookup, using the caller's write transaction."""
        self._ready(conn)
        self._reconcile_all_in(conn)
        return self._policy_snapshot_in(conn)

    def reconcile_in(self, conn):
        """Shared-policy callback; caller commits reconciliation before return."""
        self._ready(conn)
        self._reconcile_all_in(conn)

    def policy_snapshot(self, conn):
        return self.policy_in(conn)

    def require_assistance(self, conn, *, expected_revision=None):
        policy = self.policy_snapshot(conn)
        if not policy["assistance_allowed"]:
            raise ApiError("attempt_restricted", "Finish your active Test before using assistance.", 409)
        if expected_revision is not None and expected_revision != policy["revision"]:
            raise ApiError("revision_conflict", "Learning access changed. Reopen this question.", 409, True)
        return policy["revision"]

    @staticmethod
    def _policy_snapshot_in(conn):
        active = conn.execute("SELECT id FROM assessment_test_attempts WHERE mode='test' AND status='active'").fetchone()
        revision = conn.execute("SELECT value FROM preferences WHERE key=?", (POLICY_REVISION,)).fetchone()
        return {"active_test_id": active[0] if active else None,
                "revision": int(revision[0]) if revision else 0, "assistance_allowed": active is None}

    def policy(self):
        return self._run(self._policy_snapshot_in)

    def _allowed_in(self, conn, attempt_id=None):
        policy = self._policy_snapshot_in(conn)
        if policy["active_test_id"] and policy["active_test_id"] != attempt_id:
            raise ApiError("attempt_restricted", "Finish your active Test before opening other learning content.", 409)
        return policy

    def _replay_in(self, conn, key, operation, request, attempt_id=None):
        command = conn.execute("SELECT * FROM assessment_attempt_commands WHERE idempotency_key=?", (key,)).fetchone()
        target = attempt_id or (command["target_id"] if command else None)
        self._allowed_in(conn, target)  # Even stored acknowledgements need policy.
        if command is None:
            return None
        digest = hashlib.sha256(encode(request).encode()).hexdigest()
        if command["operation"] != operation or command["request_hash"] != digest or (attempt_id and command["target_id"] != attempt_id):
            raise ApiError("idempotency_conflict", "This request key was already used for a different action.", 409)
        return json.loads(command["result_json"])

    def _record_in(self, conn, key, operation, request, attempt_id, result):
        conn.execute("INSERT INTO assessment_attempt_commands "
                     "(idempotency_key,operation,target_type,target_id,request_hash,result_json,created_at) VALUES(?,?,?,?,?,?,?)",
                     (key, operation, "test_attempt", attempt_id, hashlib.sha256(encode(request).encode()).hexdigest(),
                      encode(result), timestamp(self.clock())))
        return result

    @staticmethod
    def _require_active(row, revision):
        if row["status"] != "active":
            raise ApiError("attempt_not_active", "Resume the attempt before continuing.", 409)
        if row["draft_revision"] != revision:
            raise ApiError("revision_conflict", "This draft changed. Reopen it before saving.", 409, True)

    def _repeat_in(self, conn, row, item):
        existing = conn.execute("SELECT repeat FROM assessment_attempt_exposure WHERE attempt_id=? AND item_id=? "
                                "AND kind='presented'", (row["id"], item.item_id)).fetchone()
        if existing:
            return bool(existing[0])
        repeat = conn.execute("SELECT 1 FROM assessment_attempt_exposure WHERE family_id=? AND attempt_id<>? LIMIT 1",
                              (item.family_id, row["id"])).fetchone() is not None
        legacy = conn.execute("SELECT 1 FROM sqlite_master WHERE name='assessment_exposure'").fetchone()
        if legacy and not repeat:
            repeat = conn.execute("SELECT 1 FROM assessment_exposure WHERE family_id=? LIMIT 1", (item.family_id,)).fetchone() is not None
        return repeat

    def _expose_in(self, conn, row, item, kind, now):
        repeat = self._repeat_in(conn, row, item)
        conn.execute("INSERT OR IGNORE INTO assessment_attempt_exposure "
                     "(id,attempt_id,item_id,question_id,question_version,key_version,family_id,family_version,kind,created_at,repeat) "
                     "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                     (durable_id("exposure"), row["id"], item.item_id, item.question_id, item.question_version,
                      item.key_version, item.family_id, item.family_version, kind, timestamp(now), int(repeat)))
        return repeat

    def _availability_in(self, conn, row, item):
        if row["live_version_id"] is None or not conn.execute("SELECT 1 FROM assessment_test_versions WHERE id=?",
                                                              (row["live_version_id"],)).fetchone():
            return "unavailable"
        version = self._version(row)
        if version.origin != "reviewed_bank":
            return "current"
        repository = self.services.registry.get("content")
        if repository is None:
            return "unavailable"
        try:
            current = repository.get_question_version(item.question_id, int(item.question_version))
        except (LookupError, ApiError):
            return "unavailable"
        if current.get("withdrawn"):
            return "withdrawn"
        if current.get("current_version") is None:
            return "unavailable"
        return "current" if str(current["current_version"]) == item.question_version else "corrected"

    def _view_in(self, conn, row):
        version, draft = self._version(row), self._draft(conn, row)
        policy = self._allowed_in(conn, row["id"])
        answers = json.loads(draft["answers_json"])
        commitments = json.loads(row["committed_json"])
        item = version.items[draft["position"]]
        presented = conn.execute("SELECT 1 FROM assessment_attempt_exposure WHERE attempt_id=? AND item_id=? "
                                 "AND kind='presented'", (row["id"], item.item_id)).fetchone()
        current = None
        if row["status"] == "active" and presented:
            current = item.model_dump(mode="json", exclude={"correct_option_ids", "explanation"})
            current["repeat"] = self._repeat_in(conn, row, item)
            current["availability"] = self._availability_in(conn, row, item)
        now = parse(row["clock_high_water_at"])
        deadline = parse(row["deadline_at"])
        effective = parse(row["paused_at"]) if row["status"] == "paused" else now
        return {"id": row["id"], "version_id": row["version_id"], "origin": version.origin,
                "review_quality": version.review_quality, "mode": row["mode"], "status": row["status"],
                "item_count": version.item_count, "provenance_unavailable": row["live_version_id"] is None,
                "draft_revision": row["draft_revision"], "position": draft["position"], "answers": answers,
                "current_item": current, "committed": commitments,
                "result": json.loads(row["result_json"]) if row["result_json"] else None,
                "timing": {"kind": row["timing_kind"], "duration_seconds": row["duration_seconds"],
                           "deadline_at": row["deadline_at"], "paused_seconds": row["paused_seconds"],
                           "remaining_seconds": max(0, int((deadline - effective).total_seconds())) if deadline else None},
                "policy": policy}

    def start(self, request, key):
        body = request.model_dump(mode="json")
        def operation(conn):
            replay = self._replay_in(conn, key, "start", body)
            if replay:
                return self._view_in(conn, self._row(conn, replay["id"]))
            version = self.services.get("saved_tests").pinned_version(conn, request.version.id)
            if version.status != "ready":
                raise ApiError("test_not_ready", "Resolve this test's questions before starting.", 409)
            now = self.clock()
            attempt_id = durable_id("test_attempt")
            deadline = now + timedelta(seconds=request.timing.duration_seconds) if request.timing.kind == "timed" else None
            conn.execute("INSERT INTO assessment_test_attempts "
                         "(id,version_id,live_version_id,version_snapshot_json,mode,status,draft_revision,timing_kind,"
                         "duration_seconds,started_at,deadline_at,paused_seconds,last_reconciled_at,created_at,updated_at,"
                         "finalized_at,committed_json,result_json,clock_high_water_at,paused_at) "
                         "VALUES(?,?,?,?,?,'active',0,?,?,?,?,0,?,?,?,NULL,'[]',NULL,?,NULL)",
                         (attempt_id, version.id, version.id, version.model_dump_json(), request.mode, request.timing.kind,
                          request.timing.duration_seconds, timestamp(now) if deadline else None, timestamp(deadline) if deadline else None,
                          timestamp(now), timestamp(now), timestamp(now), timestamp(now)))
            answers = [{"item_id": item.item_id, "option_ids": [], "marked": False} for item in version.items]
            conn.execute("INSERT INTO assessment_attempt_drafts VALUES(?,0,0,?,?)", (attempt_id, encode(answers), timestamp(now)))
            if request.mode == "test":
                bump_policy_revision_in(conn, now)
            row = self._row(conn, attempt_id)
            self._expose_in(conn, row, version.items[0], "presented", now)
            return self._record_in(conn, key, "start", body, attempt_id, self._view_in(conn, row))
        return self._run(operation)

    def get(self, attempt_id):
        return self._run(lambda conn: self._view_in(conn, self._row(conn, attempt_id)))

    def list(self):
        def operation(conn):
            return {"items": [dict(r) for r in conn.execute("SELECT id,version_id,mode,status,created_at,finalized_at "
                                                            "FROM assessment_test_attempts ORDER BY created_at DESC,id LIMIT 100")],
                    "policy": self._policy_snapshot_in(conn)}
        return self._run(operation)

    def _save_in(self, conn, row, state, revision):
        self._require_active(row, revision)
        version = self._version(row)
        if state.position >= version.item_count:
            raise ApiError("invalid_request", "Choose a question in this version.", 422)
        items = {item.item_id: item for item in version.items}
        choices = {answer.item_id: answer for answer in state.answers}
        if set(choices) != set(items):
            raise ApiError("invalid_request", "Save the full pinned draft, including unanswered questions.", 422)
        for identifier, answer in choices.items():
            if not set(answer.option_ids) <= {o.id for o in items[identifier].options}:
                raise ApiError("invalid_request", "A choice does not belong to this question.", 422)
        committed = json.loads(row["committed_json"])
        for entry in committed:
            if set(choices[entry["item_id"]].option_ids) != set(entry["selected_option_ids"]):
                raise ApiError("answer_locked", "A submitted Study answer cannot change.", 409)
        old = self._draft(conn, row)
        if row["mode"] == "study" and state.position > old["position"] and version.items[old["position"]].item_id not in {e["item_id"] for e in committed}:
            raise ApiError("answer_required", "Submit this answer before moving to the next question.", 409)
        now = timestamp(self.clock())
        next_revision = revision + 1
        conn.execute("UPDATE assessment_attempt_drafts SET revision=?,position=?,answers_json=?,updated_at=? WHERE attempt_id=?",
                     (next_revision, state.position, encode([a.model_dump(mode="json") for a in state.answers]), now, row["id"]))
        conn.execute("UPDATE assessment_test_attempts SET draft_revision=?,updated_at=? WHERE id=?", (next_revision, now, row["id"]))
        row["draft_revision"] = next_revision

    def save(self, attempt_id, request, key):
        body = request.model_dump(mode="json")
        def operation(conn):
            replay = self._replay_in(conn, key, "draft", body, attempt_id)
            if replay:
                return replay
            row = self._row(conn, attempt_id)
            self._save_in(conn, row, request, request.expected_revision)
            return self._record_in(conn, key, "draft", body, attempt_id, self._view_in(conn, row))
        return self._run(operation)

    def present(self, attempt_id, request, key):
        body = request.model_dump(mode="json")
        def operation(conn):
            replay = self._replay_in(conn, key, "present", body, attempt_id)
            if replay:
                return replay
            row = self._row(conn, attempt_id)
            self._require_active(row, request.expected_revision)
            item = self._version(row).items[self._draft(conn, row)["position"]]
            if item.item_id != request.item_id:
                raise ApiError("revision_conflict", "The current question changed.", 409, True)
            self._expose_in(conn, row, item, "presented", self.clock())
            return self._record_in(conn, key, "present", body, attempt_id, self._view_in(conn, row))
        return self._run(operation)

    def record_help_in(self, conn, attempt_id, request):
        policy = self._allowed_in(conn)
        if policy["revision"] != request.expected_policy_revision:
            raise ApiError("revision_conflict", "Learning access changed. Reopen this question.", 409, True)
        row = self._row(conn, attempt_id)
        self._require_active(row, request.expected_revision)
        version = self._version(row)
        item = version.items[self._draft(conn, row)["position"]]
        if row["mode"] != "study" or item.item_id != request.item_id:
            raise ApiError("attempt_restricted", "Help is available for the current Study question.", 409)
        if any(e["item_id"] == item.item_id for e in json.loads(row["committed_json"])):
            raise ApiError("answer_locked", "This answer is already submitted. Open its feedback.", 409)
        if request.kind == "hint":
            raise ApiError("hint_unavailable", "This pinned version has no authored hint. Sources, notes and chat remain available.", 409)
        self._expose_in(conn, row, item, request.kind, self.clock())
        return {"references": [ref.model_dump(mode="json") for ref in version.source_refs] if request.kind == "sources" else [],
                "context": {"attempt_id": row["id"], "item_id": item.item_id, "version_id": version.id,
                            "draft_revision": row["draft_revision"], "policy_revision": policy["revision"], "kind": request.kind},
                "assisted": True}

    def help(self, attempt_id, request, key):
        body = request.model_dump(mode="json")
        def operation(conn):
            # Recheck item/context before replay too; an old item receipt is not
            # permission for a late response to populate the next question.
            row = self._row(conn, attempt_id)
            self._allowed_in(conn)
            self._require_active(row, request.expected_revision)
            if self._version(row).items[self._draft(conn, row)["position"]].item_id != request.item_id:
                raise ApiError("revision_conflict", "The current question changed.", 409, True)
            replay = self._replay_in(conn, key, "help", body, attempt_id)
            if replay:
                if replay["context"]["policy_revision"] != self._policy_snapshot_in(conn)["revision"]:
                    raise ApiError("revision_conflict", "Learning access changed. Reopen this question.", 409, True)
                return replay
            result = self.record_help_in(conn, attempt_id, request)
            return self._record_in(conn, key, "help", body, attempt_id, result)
        return self._run(operation)

    def _commit_in(self, conn, row, item, option_ids, now):
        version = self._version(row)
        if not set(option_ids) <= {o.id for o in item.options}:
            raise ApiError("invalid_request", "A choice does not belong to this question.", 422)
        available = self._availability_in(conn, row, item)
        excluded = available != "current"
        assisted = conn.execute("SELECT 1 FROM assessment_attempt_exposure WHERE attempt_id=? AND item_id=? "
                                "AND kind IN ('hint','sources','notes','chat')", (row["id"], item.item_id)).fetchone() is not None
        repeat = self._repeat_in(conn, row, item)
        bank = version.bank_cohort_eligible
        bucket = ("repeat" if repeat else "assisted" if assisted else "fresh") if bank else "personal"
        correct = bool(option_ids) and set(option_ids) == set(item.correct_option_ids) and not excluded
        outcome = "excluded" if excluded else "unanswered" if not option_ids else "correct" if correct else "incorrect"
        commit_id = durable_id("answer_commit")
        entry = {"commit_id": commit_id, "item_id": item.item_id, "selected_option_ids": list(option_ids),
                 "question_id": item.question_id, "question_version": item.question_version, "key_version": item.key_version,
                 "family_id": item.family_id, "family_version": item.family_version, "committed_at": timestamp(now),
                 "assisted": assisted, "repeat": repeat, "score_bucket": bucket, "correct": correct, "outcome": outcome,
                 "exclusion_reason": available if excluded else None,
                 "feedback": {"correct_option_ids": list(item.correct_option_ids) if not excluded else [],
                              "explanation": item.explanation if not excluded else "This pinned item was excluded because its content is no longer current."},
                 "evidence_id": None}
        if not excluded:
            evidence_id = durable_id("evidence")
            payload = {field: entry[field] for field in ("commit_id", "item_id", "question_id", "question_version", "key_version",
                                                       "family_id", "family_version", "assisted", "repeat", "score_bucket", "correct", "outcome", "committed_at")}
            payload.update({"attempt_id": row["id"], "version_id": version.id, "origin": version.origin,
                            "review_quality": version.review_quality, "mode": row["mode"], "reviewed": bank,
                            "bank_cohort_eligible": bank, "topic_id": item.topic_id})
            conn.execute("INSERT INTO learning_evidence VALUES(?,?,?,?,?,?)",
                         (evidence_id, "assessment-test-answer", item.topic_id, row["id"], encode(payload), timestamp(now)))
            entry["evidence_id"] = evidence_id
        self._expose_in(conn, row, item, "answered", now)
        return entry

    def commit_answer(self, attempt_id, request, key):
        body = request.model_dump(mode="json")
        def operation(conn):
            replay = self._replay_in(conn, key, "submit-answer", body, attempt_id)
            if replay:
                return replay
            row = self._row(conn, attempt_id)
            self._require_active(row, request.expected_revision)
            if row["mode"] != "study":
                raise ApiError("attempt_restricted", "Test answers commit together at final submission.", 409)
            version, draft = self._version(row), self._draft(conn, row)
            item = version.items[draft["position"]]
            if item.item_id != request.item_id:
                raise ApiError("revision_conflict", "The current question changed.", 409, True)
            entries = json.loads(row["committed_json"])
            if any(entry["item_id"] == item.item_id for entry in entries):
                raise ApiError("answer_locked", "This Study answer is already submitted.", 409)
            self._expose_in(conn, row, item, "presented", self.clock())
            answers = json.loads(draft["answers_json"])
            for answer in answers:
                if answer["item_id"] == item.item_id:
                    answer["option_ids"] = list(request.option_ids)
            self._save_in(conn, row, DraftState(position=draft["position"], answers=answers), request.expected_revision)
            entries.append(self._commit_in(conn, row, item, request.option_ids, self.clock()))
            row["committed_json"] = encode(entries)
            conn.execute("UPDATE assessment_test_attempts SET committed_json=? WHERE id=?", (row["committed_json"], attempt_id))
            return self._record_in(conn, key, "submit-answer", body, attempt_id, self._view_in(conn, row))
        return self._run(operation)

    def _finalise_in(self, conn, row, now, reason):
        if row["status"] in TERMINAL:
            return
        entries = json.loads(row["committed_json"])
        if row["mode"] == "test":
            answers = {a["item_id"]: a["option_ids"] for a in json.loads(self._draft(conn, row)["answers_json"])}
            entries = [self._commit_in(conn, row, item, answers[item.item_id], now) for item in self._version(row).items]
        included = [e for e in entries if e["outcome"] != "excluded"]
        version = self._version(row)
        result = {"attempt_id": row["id"], "version_id": row["version_id"], "origin": version.origin,
                  "review_quality": version.review_quality, "mode": row["mode"], "items": entries,
                  "correct": sum(e["correct"] for e in included), "denominator": len(included),
                  "excluded": len(entries) - len(included), "unanswered": sum(e["outcome"] == "unanswered" for e in included),
                  "not_submitted": version.item_count - len(entries), "item_count": version.item_count,
                  "reason": reason, "finalized_at": timestamp(now), "draft_revision": row["draft_revision"],
                  "cohorts": {bucket: {"answered": sum(e["score_bucket"] == bucket for e in included),
                                        "correct": sum(e["score_bucket"] == bucket and e["correct"] for e in included)}
                              for bucket in ("fresh", "assisted", "repeat", "personal")}}
        status = "submitted" if row["mode"] == "test" else "ended"
        conn.execute("UPDATE assessment_test_attempts SET status=?,committed_json=?,result_json=?,finalized_at=?,updated_at=? WHERE id=?",
                     (status, encode(entries), encode(result), timestamp(now), timestamp(now), row["id"]))
        row.update(status=status, committed_json=encode(entries), result_json=encode(result), finalized_at=timestamp(now))
        if row["mode"] == "test":
            bump_policy_revision_in(conn, now)

    def submit(self, attempt_id, request, key):
        body = request.model_dump(mode="json")
        def operation(conn):
            replay = self._replay_in(conn, key, "submit", body, attempt_id)
            if replay:
                return replay
            row = self._row(conn, attempt_id)
            if row["status"] not in TERMINAL:
                if request.expected_draft_revision != row["draft_revision"]:
                    raise ApiError("saving_incomplete", "Reopen the latest saved draft before submitting.", 409, True)
                if request.latest_draft is not None:
                    self._save_in(conn, row, request.latest_draft, request.expected_draft_revision)
                self._finalise_in(conn, row, parse(row["clock_high_water_at"]), "manual")
            return self._record_in(conn, key, "submit", body, attempt_id, self._view_in(conn, row))
        return self._run(operation)

    def transition(self, attempt_id, action, request, key):
        body = request.model_dump(mode="json")
        def operation(conn):
            replay = self._replay_in(conn, key, action, body, attempt_id)
            if replay:
                return replay
            row = self._row(conn, attempt_id)
            if row["mode"] == "test":
                raise ApiError("attempt_restricted", "Test timing cannot pause. You can leave and resume the active Test.", 409)
            if row["draft_revision"] != request.expected_revision:
                raise ApiError("revision_conflict", "This attempt changed. Reopen it.", 409, True)
            now = parse(row["clock_high_water_at"])
            if action == "pause" and row["status"] == "active":
                conn.execute("UPDATE assessment_test_attempts SET status='paused',paused_at=?,updated_at=? WHERE id=?",
                             (timestamp(now), timestamp(now), attempt_id))
            elif action == "resume" and row["status"] == "paused":
                delta = now - parse(row["paused_at"])
                deadline = parse(row["deadline_at"])
                conn.execute("UPDATE assessment_test_attempts SET status='active',paused_at=NULL,paused_seconds=paused_seconds+?,"
                             "deadline_at=?,updated_at=? WHERE id=?",
                             (int(delta.total_seconds()), timestamp(deadline + delta) if deadline else None, timestamp(now), attempt_id))
            elif action == "continue-untimed" and row["status"] == "timer_expired":
                conn.execute("UPDATE assessment_test_attempts SET status='active',timing_kind='untimed',duration_seconds=NULL,"
                             "started_at=NULL,deadline_at=NULL,paused_at=NULL,updated_at=? WHERE id=?", (timestamp(now), attempt_id))
            else:
                raise ApiError("invalid_transition", "This timing action is unavailable for the current state.", 409)
            return self._record_in(conn, key, action, body, attempt_id, self._view_in(conn, self._row(conn, attempt_id)))
        return self._run(operation)

    def report(self, attempt_id, request, key):
        def operation(conn):
            row = self._row(conn, attempt_id)
            self._allowed_in(conn, attempt_id)
            version = self._version(row)
            if request.item_id not in {item.item_id for item in version.items}:
                raise ApiError("not_found", "This question is not in the pinned attempt.", 404)
            return self.services.get("saved_tests").save_question_report(conn, version=version, attempt_id=attempt_id,
                item_id=request.item_id, report_text=request.report_text, idempotency_key=key)
        return self._run(operation)
