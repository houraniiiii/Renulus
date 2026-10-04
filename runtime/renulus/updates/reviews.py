"""Evidence-backed review journal and retryable local library metadata seam."""
from datetime import datetime, timezone
from urllib.parse import urldefrag
import hashlib
import json

from pydantic import ValidationError

from renulus.contracts import ApiError
from renulus.storage import utc_now
from .models import ReviewedEvidence, SourceChanges, SourceTarget, article_identity


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


class SourceReviews:
    def __init__(self, updates):
        self.updates, self.db = updates, updates.db

    def validate(self, entry, state, target, changes, evidence):
        if state not in ("reviewed", "dismissed"):
            raise ApiError("review_state_invalid", "Choose review or dismiss")
        try:
            evidence = [ReviewedEvidence.model_validate(item).model_dump(mode="json") for item in evidence or []]
            changes = SourceChanges.model_validate(changes or {}).model_dump(mode="json", exclude_unset=True)
            target = SourceTarget.model_validate(target).model_dump(exclude_none=True) if target else None
        except (ValidationError, ValueError):
            raise ApiError("review_evidence_invalid", "Check the evidence, exact source identity and independent publication states", 422) from None
        if state == "reviewed" and not evidence:
            raise ApiError("review_evidence_required", "Record the source location, finding and date you actually inspected", 422)
        if state == "dismissed" and (target or changes):
            raise ApiError("dismissed_status_change", "A dismissed discovery cannot publish source-status changes", 422)
        if changes and not target:
            raise ApiError("review_target_required", "Choose the exact publication whose status was reviewed", 422)
        if target and target["register_id"] != entry["source_id"]:
            raise ApiError("review_source_mismatch", "The reviewed target must belong to this update's register source", 422)
        if target and target["register_id"] not in {source["id"] for source in self.updates.sources}:
            raise ApiError("source_missing", "The target is not in docs/SOURCES.md", 404)
        if target and entry["source_metadata"].get("publication_id") and target.get("canonical_url") != entry["source_metadata"].get("canonical_url"):
            raise ApiError("review_publication_mismatch", "Review the publication whose bytes changed", 422)
        if changes.get("retracted") is not None and not article_identity(target or {}):
            raise ApiError("retraction_identity_required", "Confirm the original article's exact DOI, PMID or PMCID; a notice or source family is insufficient", 422)
        if target and changes.get("replaced_topics"):
            if not target.get("topic_ids"):
                target["topic_ids"] = changes["replaced_topics"]
            elif not set(target["topic_ids"]) <= set(changes["replaced_topics"]):
                raise ApiError("replacement_scope_mismatch", "Affected topics must be within the reviewed replacement scope", 422)
        return target, changes, evidence

    def enqueue(self, conn, identifier, entry_id, target, changes, evidence, reason):
        payload = {"contract_version": 1, "event_id": identifier, "source_id": target["register_id"],
                   "identity": {key: target[key] for key in ("canonical_url", "pinned_source_id", "doi", "pmid", "pmcid", "edition", "original_sha256") if target.get(key)},
                   "scope": {key: target.get(key, []) for key in ("topic_ids", "locators")},
                   "changes": changes, "evidence": evidence, "reason": reason}
        conn.execute("INSERT OR IGNORE INTO update_library_changes(id,entry_id,payload_json) VALUES(?,?,?)",
                     (identifier, entry_id, canonical(payload)))

    def observed_change(self, conn, entry_id, target, previous_digest, observed, now):
        # Observation invalidates prior currency review. It does not claim a
        # correction, new edition, final publication or scientific retraction.
        changes = {"latest_final_verified": False, "content_reviewed": False}
        self.enqueue(conn, "observed:" + entry_id, entry_id, target, changes,
                     {"kind": "publication-digest", "observed_at": now,
                      "previous_sha256": previous_digest, "observed": observed},
                     "Published bytes changed; source currency needs re-review")
        # Retain publication/access/retraction facts independently. Only the
        # prior review's applicability is invalidated for this exact URL.
        for row in conn.execute("SELECT target_key,target_json,status_json FROM update_source_statuses").fetchall():
            stored = json.loads(row["target_json"])
            if (stored["register_id"] == target["register_id"] and stored.get("canonical_url")
                    and urldefrag(stored["canonical_url"])[0] == urldefrag(target.get("canonical_url") or "")[0]):
                status = {**json.loads(row["status_json"]), **changes}
                conn.execute("UPDATE update_source_statuses SET status_json=? WHERE target_key=?", (canonical(status), row["target_key"]))

    def review(self, identifier, summary, topic_ids, reviewer, state, *, target=None, changes=None, evidence=None):
        entry = self.updates.get_entry(identifier)
        if reviewer not in ("learner", "assistant"):
            raise ApiError("reviewer_invalid", "Identify the learner or assistant performing this review", 422)
        if state == "reviewed" and not summary.strip():
            raise ApiError("review_summary_required", "Write the reviewed educational implication")
        if len(summary) > 8000 or len(topic_ids) > 100 or len(evidence or []) > 20:
            raise ApiError("review_limit", "Keep this review within the source-evidence limits", 422)
        target, changes, evidence = self.validate(entry, state, target, changes, evidence)
        identity = canonical({"entry_id": identifier, "summary": summary.strip(), "topic_ids": sorted(set(topic_ids)),
                              "reviewer": reviewer, "state": state, "target": target, "changes": changes, "evidence": evidence})
        review_id = "review_" + hashlib.sha256(identity.encode()).hexdigest()[:24]
        if self.db.fetch_one("SELECT 1 FROM update_reviews WHERE id=?", (review_id,)):
            # A retry of an older request must not overwrite a later review.
            return self.updates.get_entry(identifier)
        now = utc_now()
        with self.db.transaction() as conn:
            previous = conn.execute("SELECT reviewed_at FROM update_reviews WHERE id=?", (review_id,)).fetchone()
            reviewed_at = previous["reviewed_at"] if previous else now
            conn.execute("INSERT OR IGNORE INTO update_reviews(id,entry_id,target_json,changes_json,evidence_json,summary,topic_ids_json,reviewer,state,reviewed_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (review_id, identifier, canonical(target), canonical(changes), canonical(evidence), summary.strip(),
                 canonical(sorted(set(topic_ids))), reviewer, state, reviewed_at))
            conn.execute("INSERT INTO update_review_heads(entry_id,review_id) VALUES(?,?) ON CONFLICT(entry_id) DO UPDATE SET review_id=excluded.review_id", (identifier, review_id))
            conn.execute("UPDATE update_entries SET summary=?,topic_ids_json=?,reviewer=?,reviewed_at=?,review_state=? WHERE id=?",
                (summary.strip(), canonical(sorted(set(topic_ids))), reviewer, reviewed_at, state, identifier))
            conn.execute("UPDATE update_affected_versions SET state=? WHERE entry_id=?",
                         ("dismissed" if state == "dismissed" else "needs-re-review", identifier))
            if target and changes:
                if target.get("topic_ids") or target.get("locators"):
                    # Evidence-confirmed scope narrows a broad byte-change
                    # alert, retaining dismissed annotations for provenance.
                    conn.execute("UPDATE update_affected_versions SET state='dismissed' WHERE entry_id=?", (identifier,))
                # Remove scope from the identity so patches for chapter/topic
                # replacements preserve other facts about the same publication.
                exact = {key: value for key, value in target.items() if key not in ("topic_ids", "locators")}
                # Additional DOI/PMID metadata enriches one URL's identity;
                # it cannot discard its earlier publication/access facts.
                key_identity = {"register_id": exact["register_id"]}
                if exact.get("canonical_url"):
                    key_identity["canonical_url"] = urldefrag(exact["canonical_url"])[0]
                else:
                    key = next(key for key in ("doi", "pmid", "pmcid", "pinned_source_id") if exact.get(key))
                    key_identity[key] = exact[key]
                if exact.get("pinned_source_id"):
                    key_identity["pinned_source_id"] = exact["pinned_source_id"]
                # Edition and original file bytes identify an acquired version;
                # reviewing one file cannot clear another file's source facts.
                for key in ("edition", "original_sha256"):
                    if key in exact:
                        key_identity[key] = exact[key]
                target_key = hashlib.sha256(canonical(key_identity).encode()).hexdigest()
                current = conn.execute("SELECT target_json,status_json FROM update_source_statuses WHERE target_key=?", (target_key,)).fetchone()
                if current:
                    previous_target = json.loads(current["target_json"])
                    if any(previous_target.get(key) and previous_target[key] != value for key, value in article_identity(exact).items()):
                        raise ApiError("review_identity_conflict", "The identifiers conflict with the recorded publication identity", 422)
                    exact = {**previous_target, **exact}
                merged = {**(json.loads(current["status_json"]) if current else {}), **changes}
                if merged.get("publication_status") not in (None, "final") or any(merged.get(key) for key in ("retracted", "superseded", "repository_removed")):
                    merged["latest_final_verified"] = False
                conn.execute("INSERT INTO update_source_statuses(target_key,target_json,status_json,review_id) VALUES(?,?,?,?) ON CONFLICT(target_key) DO UPDATE SET target_json=excluded.target_json,status_json=excluded.status_json,review_id=excluded.review_id",
                             (target_key, canonical(exact), canonical(merged), review_id))
                material = any(key in changes for key in ("correction", "retracted", "superseded", "repository_removed",
                               "access_changed", "replaced_topics", "excluded_pages")) or entry["kind"] == "publication-change" or entry["source_metadata"].get("previous_entry_id")
                if material:
                    self.updates.affected.record(conn, identifier, target, reviewed_at, "reviewed source status changed")
                self.enqueue(conn, review_id, identifier, {**target, **exact}, changes,
                    {"kind": "reviewed-publication", "reviewer": reviewer, "reviewed_at": reviewed_at, "references": evidence}, summary.strip())
                conn.execute("UPDATE update_reviews SET library_sync_state='pending' WHERE id=? AND library_sync_state='not-requested'", (review_id,))
        if target and changes:
            self.sync(review_id)
        return self.updates.get_entry(identifier)

    def sync(self, identifier):
        row = self.db.fetch_one("SELECT * FROM update_library_changes WHERE id=?", (identifier,))
        if not row:
            raise ApiError("source_change_missing", "This source metadata change is unavailable", 404)
        if row["state"] == "applied":
            return {"event_id": identifier, "state": "applied", "result": json.loads(row["result_json"] or "{}")}
        knowledge = self.updates.services.registry.get("knowledge")
        registry = self.updates.services.registry
        hook = (registry.get("update_source_status") or getattr(knowledge, "update_source_status", None)
                or registry.get("apply_source_status") or getattr(knowledge, "apply_source_status", None))
        result, code = None, None
        if not callable(hook):
            state, code = "unavailable", "library_status_seam_unavailable"
        else:
            try:
                result = hook(json.loads(row["payload_json"]))
                # The local metadata adapter must explicitly acknowledge the
                # event. An absent/malformed result is never treated as applied.
                if not isinstance(result, dict) or result.get("state") not in ("applied", "no-match"):
                    raise ApiError("library_status_result_invalid", "The library did not confirm the metadata change")
                state = "applied" if result["state"] == "applied" else "no-match"
            except Exception as error:
                state, code = "failed", error.code if isinstance(error, ApiError) else "library_status_sync_failed"
        now = utc_now()
        with self.db.transaction() as conn:
            conn.execute("UPDATE update_library_changes SET state=?,last_attempt_at=?,error_code=?,result_json=? WHERE id=?",
                         (state, now, code, canonical(result) if result is not None else None, identifier))
            conn.execute("UPDATE update_reviews SET library_sync_state=?,library_sync_error=?,library_result_json=? WHERE id=?",
                         (state, code, canonical(result) if result is not None else None, identifier))
        return {"event_id": identifier, "state": state, "error_code": code, "result": result}

    def retry_pending(self):
        rows = self.db.fetch_all("SELECT id FROM update_library_changes WHERE state IN ('pending','failed','unavailable','no-match') ORDER BY rowid LIMIT 100")
        return {"changes": [self.sync(row["id"]) for row in rows]}

    def sync_entry(self, entry_id):
        self.updates.get_entry(entry_id)
        rows = self.db.fetch_all("SELECT id FROM update_library_changes WHERE entry_id=? ORDER BY rowid", (entry_id,))
        return {"changes": [self.sync(row["id"]) for row in rows]}

    def statuses(self, source_id):
        rows = self.db.fetch_all("SELECT s.*,r.reviewed_at,r.reviewer FROM update_source_statuses s JOIN update_reviews r ON r.id=s.review_id WHERE json_extract(s.target_json,'$.register_id')=? ORDER BY s.target_key", (source_id,))
        return [{"target_key": row["target_key"], "target": json.loads(row["target_json"]),
                 "status": json.loads(row["status_json"]), "review_id": row["review_id"],
                 "reviewed_at": row["reviewed_at"], "reviewer": row["reviewer"]} for row in rows]

    def decorate(self, rows):
        if not rows:
            return rows
        placeholders = ",".join("?" for row in rows)
        reviews = {row["entry_id"]: row for row in self.db.fetch_all(
            f"SELECT r.* FROM update_review_heads h JOIN update_reviews r ON r.id=h.review_id WHERE h.entry_id IN ({placeholders})", [row["id"] for row in rows])}
        jobs = {}
        for job in self.db.fetch_all(f"SELECT entry_id,id,state,error_code FROM update_library_changes WHERE entry_id IN ({placeholders}) ORDER BY rowid", [row["id"] for row in rows]):
            jobs.setdefault(job.pop("entry_id"), []).append(job)
        for entry in rows:
            entry["library_changes"] = jobs.get(entry["id"], [])
            review = reviews.get(entry["id"])
            entry["review"] = None if not review else {"id": review["id"], "target": json.loads(review["target_json"]),
                "changes": json.loads(review["changes_json"]), "evidence": json.loads(review["evidence_json"]),
                "library_sync_state": review["library_sync_state"], "library_sync_error": review["library_sync_error"]}
        return rows
