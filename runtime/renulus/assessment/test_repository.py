# SPDX-License-Identifier: MIT
"""Saved collections and immutable manifests, independent of attempt execution."""
from contextlib import closing
import json

from pydantic import ValidationError

from renulus.contracts import ApiError, durable_id
from renulus.design_c_contracts import QuestionSnapshot, SavedTestVersion, canonical_digest
from renulus.storage.database import utc_now
from renulus.storage.assessment_policy import require_assistance
from renulus.storage.invalidation import bump_context_epoch
from renulus.storage.relations import reconcile_unavailable_references
from .content import ContentGateway


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def legacy_test_ids(kind, session_id):
    """Exact, domain-separated mapping; no case folding or ID-prefix inference."""
    if kind not in ("reviewed", "generated"):
        raise ValueError("Unknown legacy assessment kind")
    return tuple(prefix + canonical_digest([domain, kind, session_id]) for prefix, domain in
                 (("test_legacy_", "legacy-test/1"), ("version_legacy_", "legacy-version/1")))


def _exists(conn, table):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def _deleted(conn, kind, identifier):
    return conn.execute("SELECT 1 FROM deletion_ledger WHERE entity_type=? AND entity_id=?",
                        (kind, identifier)).fetchone() is not None


class SavedTestRepository:
    def __init__(self, services):
        self.services, self.db = services, services.db
        self.content = ContentGateway(services)

    @staticmethod
    def _require_disclosure(conn):
        require_assistance(conn)

    @staticmethod
    def _test(conn, test_id, *, deleted=False):
        row = conn.execute("SELECT * FROM assessment_tests WHERE id=?", (test_id,)).fetchone()
        if row is None or (not deleted and (row["lifecycle"] == "deleted" or _deleted(conn, "saved_test", test_id))):
            raise ApiError("not_found", "This saved test was deleted or is unavailable", 404)
        return dict(row)

    @staticmethod
    def _revision(row, expected):
        if row["revision"] != expected:
            raise ApiError("revision_conflict", "This test changed. Reopen it before saving your changes", 409)

    @staticmethod
    def _replay(conn, key, operation, target_type, target_id, request_hash):
        row = conn.execute("SELECT * FROM assessment_test_commands WHERE idempotency_key=?", (key,)).fetchone()
        if row is None:
            return None
        if (row["operation"], row["target_type"], row["target_id"], row["request_hash"]) != (
                operation, target_type, target_id, request_hash):
            raise ApiError("idempotency_conflict", "This request key was already used for a different action", 409)
        return json.loads(row["result_json"])

    @staticmethod
    def _record(conn, key, operation, target_type, target_id, request_hash, result):
        conn.execute("INSERT INTO assessment_test_commands "
                     "(idempotency_key,operation,target_type,target_id,request_hash,result_json,created_at) "
                     "VALUES(?,?,?,?,?,?,?)", (key, operation, target_type, target_id, request_hash, encode(result), utc_now()))

    def pinned_version(self, conn, version_id):
        """PRIVATE: trusted attempt/generation code only, includes answer keys."""
        row = conn.execute("SELECT * FROM assessment_test_versions WHERE id=?", (version_id,)).fetchone()
        if row is None or _deleted(conn, "saved_test_version", version_id):
            raise ApiError("not_found", "The selected version is unavailable; retained attempts remain unchanged", 404)
        self._test(conn, row["test_id"])
        try:
            return SavedTestVersion(id=row["id"], test_id=row["test_id"], ordinal=row["ordinal"], origin=row["origin"],
                review_quality=row["review_quality"], status=row["status"], items=json.loads(row["items_json"]),
                source_refs=json.loads(row["source_refs_json"]), provenance=json.loads(row["provenance_json"])["producer"],
                terms=row["terms"], created_at=row["created_at"])
        except (KeyError, TypeError, ValueError):
            raise ApiError("test_version_unavailable", "The saved manifest is incomplete. Retained history stays unchanged", 409) from None

    def pinned_provenance(self, conn, version_id):
        """PRIVATE: capture native pack/source metadata beside an attempt's version pin."""
        self.pinned_version(conn, version_id)
        return json.loads(conn.execute("SELECT provenance_json FROM assessment_test_versions WHERE id=?", (version_id,)).fetchone()[0])

    @staticmethod
    def _version_summary(row):
        items = json.loads(row["items_json"])
        return {field: row[field] for field in ("id", "test_id", "ordinal", "origin", "review_quality", "status", "created_at")} | {
            "item_count": len(items), "topic_ids": sorted({item["topic_id"] for item in items})}

    def _summary(self, conn, row):
        version = conn.execute("SELECT * FROM assessment_test_versions WHERE test_id=? ORDER BY ordinal DESC LIMIT 1",
                               (row["id"],)).fetchone()
        return {**row, "latest_version": self._version_summary(version) if version else None}

    def list_tests(self, *, lifecycle="active", origin=None, query="", limit=50, before=None):
        with closing(self.db.connect()) as conn:
            conn.execute("BEGIN")
            # Stable ID ordering is unaffected by rename/archive. Filter-bound cursors
            # are represented by the exact last ID; transport validates their scope.
            clauses, values = ["t.lifecycle=?"], [lifecycle]
            if query:
                clauses.append("instr(lower(t.title),lower(?))>0"); values.append(query)
            if origin:
                clauses.append("(SELECT v.origin FROM assessment_test_versions v WHERE v.test_id=t.id ORDER BY v.ordinal DESC LIMIT 1)=?")
                values.append(origin)
            if before:
                clauses.append("t.id>?"); values.append(before)
            rows = conn.execute("SELECT t.* FROM assessment_tests t WHERE " + " AND ".join(clauses) +
                                " ORDER BY t.id LIMIT ?", (*values, limit + 1)).fetchall()
            selected = [dict(row) for row in rows[:limit] if not _deleted(conn, "saved_test", row["id"])]
            return {"items": [self._summary(conn, row) for row in selected],
                    "next_cursor": rows[limit - 1]["id"] if len(rows) > limit else None}

    def get_test(self, test_id):
        with closing(self.db.connect()) as conn:
            conn.execute("BEGIN")
            row = self._test(conn, test_id)
            versions = conn.execute("SELECT * FROM assessment_test_versions WHERE test_id=? ORDER BY ordinal DESC LIMIT 50", (test_id,))
            return {**self._summary(conn, row), "versions": [self._version_summary(version) for version in versions]}

    def list_versions(self, test_id, *, limit=50, before=None):
        with closing(self.db.connect()) as conn:
            conn.execute("BEGIN")
            self._test(conn, test_id)
            rows = conn.execute("SELECT * FROM assessment_test_versions WHERE test_id=? AND (? IS NULL OR ordinal<?) "
                                "ORDER BY ordinal DESC LIMIT ?", (test_id, before, before, limit + 1)).fetchall()
            return {"items": [self._version_summary(row) for row in rows[:limit]],
                    "next_before": rows[limit - 1]["ordinal"] if len(rows) > limit else None}

    def preview_version(self, test_id, version_id):
        with closing(self.db.connect()) as conn:
            conn.execute("BEGIN")
            self._require_disclosure(conn)
            version = self.pinned_version(conn, version_id)
            if version.test_id != test_id:
                raise ApiError("not_found", "This version belongs to another test", 404)
            # Editing does not disclose the source's bank keys or explanations.
            return {"version_id": version.id, "items": [{key: value for key, value in item.model_dump(mode="json").items()
                    if key not in ("correct_option_ids", "explanation", "key_version")} for item in version.items]}

    def setup(self, test_id, version_id=None):
        with closing(self.db.connect()) as conn:
            conn.execute("BEGIN")
            self._require_disclosure(conn)
            test = self._test(conn, test_id)
            if version_id is None:
                row = conn.execute("SELECT id FROM assessment_test_versions WHERE test_id=? ORDER BY ordinal DESC LIMIT 1", (test_id,)).fetchone()
                if row is None:
                    raise ApiError("not_found", "This test has no saved version", 404)
                version_id = row[0]
            version = self.pinned_version(conn, version_id)
            if version.test_id != test_id:
                raise ApiError("not_found", "This version does not belong to the selected test", 404)
            provenance = json.loads(conn.execute("SELECT provenance_json FROM assessment_test_versions WHERE id=?", (version_id,)).fetchone()[0])
            legacy = provenance.get("legacy")
            warnings = []
            if version.bank_cohort_eligible:
                for item in version.items:
                    annotation = self.content.annotation(item.model_dump())
                    if annotation["status"] != "current":
                        warnings.append({"item_id": item.item_id, "status": annotation["status"]})
            return {"test": test, "version": {"id": version.id, "test_id": test_id, "ordinal": version.ordinal,
                "origin": version.origin, "review_quality": version.review_quality, "status": version.status,
                "item_count": version.item_count, "topic_ids": sorted({i.topic_id for i in version.items})},
                "can_start": version.status == "ready" and test["lifecycle"] == "active" and not warnings,
                "content_warnings": warnings, "legacy": legacy, "modes": ["study", "test"], "timing_default": "untimed"}

    def setup_version(self, version_id):
        with closing(self.db.connect()) as conn:
            row = conn.execute("SELECT test_id FROM assessment_test_versions WHERE id=?", (version_id,)).fetchone()
            if row is None:
                raise ApiError("not_found", "This saved version is unavailable", 404)
            test_id = row[0]
        return self.setup(test_id, version_id)

    def legacy_history(self, test_id):
        """Read existing commitments; never create a new attempt or regrade blanks."""
        with closing(self.db.connect()) as conn:
            conn.execute("BEGIN")
            self._require_disclosure(conn)
            self._test(conn, test_id)
            row = conn.execute("SELECT provenance_json FROM assessment_test_versions WHERE test_id=? ORDER BY ordinal LIMIT 1", (test_id,)).fetchone()
            legacy = json.loads(row[0]).get("legacy") if row else None
            if not legacy:
                return {"legacy": None}
            prefix = "assessment" if legacy["kind"] == "reviewed" else "assessment_generated"
            session = conn.execute(f"SELECT * FROM {prefix}_sessions WHERE id=?", (legacy["session_id"],)).fetchone()
            if session is None:
                return {"legacy": legacy, "available": False}
            items = conn.execute(f"SELECT * FROM {prefix}_items WHERE session_id=? ORDER BY ordinal", (session["id"],)).fetchall()
            answers = conn.execute(f"SELECT * FROM {prefix}_attempts WHERE session_id=? ORDER BY committed_at,id", (session["id"],)).fetchall()
            scores = {}
            for answer in answers:
                bucket = answer["score_bucket"] if legacy["kind"] == "reviewed" else "personal"
                current = scores.setdefault(bucket, {"answered": 0, "correct": 0})
                current["answered"] += 1; current["correct"] += answer["correct"]
            by_id = {item["id"]: item for item in items}
            feedback = []
            for answer in answers:
                item = by_id.get(answer["item_id"])
                if item is None:
                    continue
                question = json.loads(item["snapshot_json"])
                feedback.append({"answer_id": answer["id"], "item_id": item["id"], "ordinal": item["ordinal"],
                    "stem": question["stem"], "options": [{"id": option["id"], "text": option["text"]} for option in question["options"]],
                    "selected_option_ids": json.loads(answer["answer_json"]),
                    "correct_option_ids": question.get("correct_option_ids") or ([question["correct_option_id"]] if question.get("correct_option_id") else []),
                    "correct": bool(answer["correct"]), "assisted": bool(answer["assisted"]),
                    "score_bucket": answer["score_bucket"] if legacy["kind"] == "reviewed" else "personal",
                    "explanation": question.get("explanation", ""), "committed_at": answer["committed_at"]})
            return {"legacy": legacy, "available": True, "compatibility": "legacy_study", "status": session["status"],
                "item_count": len(items), "denominator": len(answers), "unanswered_not_scored": len(items) - len(answers),
                "committed_answer_ids": [row["id"] for row in answers], "scores": scores, "feedback": feedback,
                "presented_item_ids": [row["id"] for row in items if row["presented_at"]] if legacy["kind"] == "reviewed" else [row["id"] for row in items if row["presented"]],
                "assisted_item_ids": [row["id"] for row in items if row["assisted"]]}

    def publish_version(self, conn, version: SavedTestVersion, *, title, provenance, idempotency_key,
                        expected_revision=None):
        """Trusted producer seam; caller owns the job/cancellation transaction.

        No HTTP endpoint accepts an origin or reviewed-quality attestation.
        Publication never changes an existing manifest, result or attempt.
        """
        version = SavedTestVersion.model_validate(version)
        producer = version.provenance.model_dump(mode="json")
        if "producer" in provenance and provenance["producer"] != producer:
            raise ApiError("invalid_request", "Producer provenance must match the pinned version", 422)
        provenance = {**provenance, "producer": producer}
        manifest = version.model_dump(mode="json")
        digest = canonical_digest({"version": manifest, "provenance": provenance})
        request_hash = canonical_digest({"version": manifest, "provenance": provenance, "title": title,
                                         "expected_revision": expected_revision})
        previous = self._replay(conn, idempotency_key, "publish_version", "saved_test", version.test_id, request_hash)
        if _deleted(conn, "saved_test", version.test_id) or _deleted(conn, "saved_test_version", version.id):
            raise ApiError("not_found", "This test or version was deleted; publication cannot restore it", 404)
        if previous is not None:
            return previous
        if provenance.get("schema") != "saved-test-provenance/1":
            raise ApiError("invalid_request", "Use the versioned test provenance envelope", 422)
        row = conn.execute("SELECT * FROM assessment_tests WHERE id=?", (version.test_id,)).fetchone()
        existing = conn.execute("SELECT * FROM assessment_test_versions WHERE id=?", (version.id,)).fetchone()
        if existing:
            if existing["sha256"] != digest:
                raise ApiError("revision_conflict", "An immutable version cannot be replaced", 409)
        else:
            if row:
                if row["lifecycle"] != "active":
                    raise ApiError("revision_conflict", "Restore this archived test before editing it", 409)
                self._revision(row, expected_revision)
                last = conn.execute("SELECT COALESCE(MAX(ordinal),0) FROM assessment_test_versions WHERE test_id=?", (version.test_id,)).fetchone()[0]
                if version.ordinal != last + 1:
                    raise ApiError("revision_conflict", "Publish the next immutable version", 409)
                conn.execute("UPDATE assessment_tests SET revision=revision+1,updated_at=? WHERE id=?", (utc_now(), version.test_id))
            else:
                if expected_revision is not None or version.ordinal != 1:
                    raise ApiError("revision_conflict", "A new saved test starts at version one", 409)
                conn.execute("INSERT INTO assessment_tests (id,title,lifecycle,revision,created_at,updated_at) VALUES(?,?,'active',1,?,?)",
                             (version.test_id, title, version.created_at.isoformat(), utc_now()))
            conn.execute("INSERT INTO assessment_test_versions "
                "(id,test_id,ordinal,origin,review_quality,status,items_json,source_refs_json,terms,sha256,provenance_json,created_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (version.id, version.test_id, version.ordinal, version.origin,
                version.review_quality, version.status, encode(manifest["items"]), encode(manifest["source_refs"]),
                version.terms, digest, encode(provenance), version.created_at.isoformat()))
        result = {"test_id": version.test_id, "version_id": version.id, "ordinal": version.ordinal,
                  "item_count": version.item_count, "status": version.status}
        self._record(conn, idempotency_key, "publish_version", "saved_test", version.test_id, request_hash, result)
        return result

    def create_reviewed(self, request):
        digest = canonical_digest(request.model_dump(exclude={"idempotency_key"}, mode="json"))
        with self.db.transaction() as conn:
            self._require_disclosure(conn)
            previous = self._replay(conn, request.idempotency_key, "create_reviewed", "collection", "", digest)
            if previous:
                self._test(conn, previous["test_id"])
                return previous
            pool = sorted(self.content.summaries(request.selector), key=lambda q: (q["id"], q["version"]))
            chosen, families = [], set()
            for item in pool:
                if item["family_id"] not in families:
                    chosen.append(self.content.pin(item)); families.add(item["family_id"])
                if len(chosen) == request.count:
                    break
            if len(chosen) != request.count:
                raise ApiError("insufficient_coverage", "Fewer eligible reviewed questions are available. Choose a smaller set", 409)
            now, test_id, version_id = utc_now(), durable_id("test"), durable_id("test_version")
            items, original = [], []
            for index, question in enumerate(chosen, 1):
                item_id = durable_id("test_item")
                items.append(self._snapshot(item_id, question))
                original.append({"item_id": item_id, "ordinal": index, "original_snapshot": question})
            version = SavedTestVersion(id=version_id, test_id=test_id, ordinal=1, origin="reviewed_bank",
                review_quality="reviewed", status="ready", items=items,
                provenance={"method": "reviewed_pack"},
                terms="Original published content and source terms are retained in provenance.", created_at=now)
            result = self.publish_version(conn, version, title=request.title,
                provenance={"schema": "saved-test-provenance/1", "items": original,
                            "selector": request.selector.model_dump(), "requested_count": request.count},
                idempotency_key="internal:" + canonical_digest(["create-reviewed", request.idempotency_key]))
            self._record(conn, request.idempotency_key, "create_reviewed", "collection", "", digest, result)
            return result

    @staticmethod
    def _snapshot(item_id, question):
        key = question.get("correct_option_ids") or ([question["correct_option_id"]] if question.get("correct_option_id") else [])
        return QuestionSnapshot(item_id=item_id, question_id=str(question.get("id") or item_id),
            question_version=str(question.get("version") or "legacy-1"), key_version=str(question.get("key_version") or "legacy-1") if key else None,
            family_id=str(question.get("family_id") or item_id), family_version=str(question.get("family_version") or "legacy-1"),
            topic_id=question.get("topic_id") or "general", stem=question["stem"],
            options=[{"id": o["id"], "text": o["text"]} for o in question["options"]],
            correct_option_ids=key, explanation=question.get("explanation") or "")

    def rename(self, test_id, request):
        return self._change(test_id, request, "rename", title=request.title)

    def lifecycle(self, test_id, request, action):
        if action not in ("archive", "restore", "delete"):
            raise ValueError("Unknown test lifecycle action")
        return self._change(test_id, request, action)

    def _change(self, test_id, request, operation, *, title=None):
        digest = canonical_digest(request.model_dump(exclude={"idempotency_key"}, mode="json"))
        with self.db.transaction() as conn:
            previous = self._replay(conn, request.idempotency_key, operation, "saved_test", test_id, digest)
            if previous is not None:
                if operation != "delete": self._test(conn, test_id)
                return previous
            row = self._test(conn, test_id)
            self._revision(row, request.expected_revision)
            if operation == "delete":
                self.db.mark_deleted("saved_test", test_id, conn=conn)
                for version in conn.execute("SELECT id FROM assessment_test_versions WHERE test_id=?", (test_id,)):
                    self.db.mark_deleted("saved_test_version", version["id"], conn=conn)
                conn.execute("DELETE FROM assessment_test_versions WHERE test_id=?", (test_id,))
                conn.execute("DELETE FROM assessment_tests WHERE id=?", (test_id,))
                reconcile_unavailable_references(conn)
                bump_context_epoch(conn)
                result = {"id": test_id, "lifecycle": "deleted", "revision": row["revision"] + 1}
            else:
                state = {"archive": "archived", "restore": "active"}.get(operation, row["lifecycle"])
                conn.execute("UPDATE assessment_tests SET title=?,lifecycle=?,revision=revision+1,updated_at=? WHERE id=?",
                             (title if title is not None else row["title"], state, utc_now(), test_id))
                result = self._summary(conn, self._test(conn, test_id))
            self._record(conn, request.idempotency_key, operation, "saved_test", test_id, digest, result)
            return result

    def edit_version(self, test_id, request):
        with self.db.transaction() as conn:
            self._require_disclosure(conn)
            digest = canonical_digest(request.model_dump(exclude={"idempotency_key"}, mode="json"))
            previous = self._replay(conn, request.idempotency_key, "edit_version", "saved_test", test_id, digest)
            if previous:
                self._test(conn, test_id); return previous
            test = self._test(conn, test_id)
            self._revision(test, request.expected_revision)
            base = self.pinned_version(conn, request.base_version_id)
            if base.test_id != test_id:
                raise ApiError("not_found", "The base version belongs to another test", 404)
            next_ordinal = conn.execute("SELECT MAX(ordinal)+1 FROM assessment_test_versions WHERE test_id=?", (test_id,)).fetchone()[0]
            # A personal edit cannot publish a new reviewed-bank key/family identity.
            version_id = durable_id("test_version")
            items = [item.model_copy(update={"question_id": "personal_" + canonical_digest([version_id, item.item_id]),
                    "question_version": "1", "key_version": "1" if item.correct_option_ids else None}) for item in request.items]
            ready = all(item.correct_option_ids for item in items)
            try:
                version = SavedTestVersion(id=version_id, test_id=test_id, ordinal=next_ordinal, origin=base.origin,
                    review_quality="personal" if ready else "needs_review", status="ready" if ready else "needs_review",
                    items=items, source_refs=base.source_refs, provenance=base.provenance,
                    terms=base.terms, created_at=utc_now())
            except ValidationError:
                raise ApiError("invalid_request", "Use distinct items and families with valid options and keys", 422) from None
            original = json.loads(conn.execute("SELECT provenance_json FROM assessment_test_versions WHERE id=?", (base.id,)).fetchone()[0])
            item_ids = {item.item_id for item in items}
            result = self.publish_version(conn, version, title=test["title"],
                provenance={"schema": "saved-test-provenance/1", "derived_from": base.id,
                            "items": [item for item in original.get("items", []) if item.get("item_id") in item_ids]},
                idempotency_key="internal:" + canonical_digest(["edit-version", request.idempotency_key]), expected_revision=request.expected_revision)
            bump_context_epoch(conn)
            self._record(conn, request.idempotency_key, "edit_version", "saved_test", test_id, digest, result)
            return result

    def save_question_report(self, conn, *, version: SavedTestVersion, attempt_id, item_id, report_text, idempotency_key,
                             provenance=None):
        """Trusted callers resolve the attempt pin before invoking this neutral writer."""
        item = next((item for item in version.items if item.item_id == item_id), None)
        if item is None:
            raise ApiError("not_found", "This item is not in the pinned test version", 404)
        if not report_text.strip() or len(report_text) > 2000 or not 8 <= len(idempotency_key) <= 128:
            raise ApiError("invalid_request", "Enter a bounded local report and request key", 422)
        request_hash = canonical_digest({"version_id": version.id, "attempt_id": attempt_id,
                                        "item_id": item_id, "report_text": report_text})
        previous = conn.execute("SELECT * FROM assessment_question_reports WHERE idempotency_key=?", (idempotency_key,)).fetchone()
        if previous:
            if previous["request_hash"] != request_hash:
                raise ApiError("idempotency_conflict", "This report key was used for different text or a different item", 409)
            return {"id": previous["id"], "status": "saved", "created_at": previous["created_at"]}
        live = conn.execute("SELECT provenance_json FROM assessment_test_versions WHERE id=?", (version.id,)).fetchone()
        snapshot = {"schema": "question-report-snapshot/1", "question": item.model_dump(mode="json"),
                    "version_id": version.id, "test_id": version.test_id, "origin": version.origin,
                    "review_quality": version.review_quality, "terms": version.terms,
                    "producer": version.provenance.model_dump(mode="json"),
                    "source_refs": [reference.model_dump(mode="json") for reference in version.source_refs]}
        if provenance is None and live:
            provenance = json.loads(live[0])
        if provenance is not None:
            snapshot["provenance"] = {"schema": provenance.get("schema"), "item": next(
                (raw for raw in provenance.get("items", []) if raw.get("item_id") == item_id), None)}
        identifier, now = durable_id("question_report"), utc_now()
        live_attempt = attempt_id if attempt_id and _exists(conn, "assessment_test_attempts") and conn.execute(
            "SELECT 1 FROM assessment_test_attempts WHERE id=?", (attempt_id,)).fetchone() else None
        conn.execute("INSERT INTO assessment_question_reports "
            "(id,version_id,live_version_id,attempt_id,live_attempt_id,item_id,question_id,question_version,key_version,"
            "family_id,family_version,report_text,idempotency_key,request_hash,question_snapshot_json,created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (identifier, version.id, version.id if live else None,
            attempt_id, live_attempt, item_id, item.question_id, item.question_version, item.key_version,
            item.family_id, item.family_version, report_text, idempotency_key, request_hash, encode(snapshot), now))
        return {"id": identifier, "status": "saved", "created_at": now}

    def report_question(self, test_id, version_id, request):
        with self.db.transaction() as conn:
            # A saved receipt remains replayable if deletion follows a lost acknowledgement.
            previous = conn.execute("SELECT * FROM assessment_question_reports WHERE idempotency_key=?",
                                    (request.idempotency_key,)).fetchone()
            if previous:
                digest = canonical_digest({"version_id": version_id, "attempt_id": None,
                    "item_id": request.item_id, "report_text": request.report_text})
                if previous["request_hash"] != digest or json.loads(previous["question_snapshot_json"])["test_id"] != test_id:
                    raise ApiError("idempotency_conflict", "This report key was used for a different question or text", 409)
                return {"id": previous["id"], "status": "saved", "created_at": previous["created_at"]}
            version = self.pinned_version(conn, version_id)
            if version.test_id != test_id:
                raise ApiError("not_found", "This version belongs to another test", 404)
            return self.save_question_report(conn, version=version, attempt_id=None, item_id=request.item_id,
                report_text=request.report_text, idempotency_key=request.idempotency_key)

    def backfill_legacy(self):
        """Add manifests only; legacy sessions/answers/exposure remain authoritative."""
        counts = {"created": 0, "existing": 0, "deleted": 0, "unavailable": 0}
        with self.db.transaction() as conn:
            for kind, prefix in (("reviewed", "assessment"), ("generated", "assessment_generated")):
                if not _exists(conn, prefix + "_sessions"):
                    continue
                sessions = conn.execute(f"SELECT * FROM {prefix}_sessions ORDER BY id").fetchall()
                for session in sessions:
                    test_id, version_id = legacy_test_ids(kind, session["id"])
                    if (_deleted(conn, "saved_test", test_id) or _deleted(conn, "saved_test_version", version_id)
                            or _deleted(conn, "assessment_session" if kind == "reviewed" else "generated_session", session["id"])):
                        counts["deleted"] += 1; continue
                    if conn.execute("SELECT 1 FROM assessment_tests WHERE id=?", (test_id,)).fetchone():
                        counts["existing"] += 1; continue
                    rows = conn.execute(f"SELECT * FROM {prefix}_items WHERE session_id=? ORDER BY ordinal", (session["id"],)).fetchall()
                    if not rows:
                        counts["unavailable"] += 1; continue
                    try:
                        snapshots, originals = [], []
                        for raw in rows:
                            original = json.loads(raw["snapshot_json"])
                            if kind == "reviewed":
                                original = {**original, "id": raw["question_id"], "version": raw["question_version"],
                                    "key_version": raw["key_version"], "family_id": raw["family_id"], "family_version": raw["family_version"],
                                    "topic_id": raw["topic_id"]}
                            else:
                                original = {**original, "topic_id": session["topic_id"] or "general"}
                            snapshots.append(self._snapshot(raw["id"], original))
                            originals.append({"item_id": raw["id"], "ordinal": raw["ordinal"],
                                              "original_snapshot": json.loads(raw["snapshot_json"])})
                        ready = all(item.correct_option_ids for item in snapshots)
                        version = SavedTestVersion(id=version_id, test_id=test_id, ordinal=1,
                            origin="reviewed_bank" if kind == "reviewed" else "generated",
                            review_quality=("reviewed" if kind == "reviewed" else "personal") if ready else "needs_review",
                            status="ready" if ready else "needs_review",
                            provenance={"method": "legacy_conversion"},
                            items=snapshots, terms="Retained original source terms; no new licence is granted.", created_at=session["created_at"])
                    except (KeyError, TypeError, ValueError):
                        counts["unavailable"] += 1; continue
                    self.publish_version(conn, version, title="Previous reviewed quiz" if kind == "reviewed" else "Previous generated practice",
                        provenance={"schema": "saved-test-provenance/1", "legacy": {"kind": kind, "session_id": session["id"]}, "items": originals},
                        idempotency_key="backfill:" + canonical_digest([kind, session["id"]]))
                    counts["created"] += 1
        return counts
