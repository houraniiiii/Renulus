"""Key-free read projection of immutable original pack citations, owned by Updates."""
import json
from urllib.parse import urldefrag

from .models import article_identity, identity_from_url


class AffectedVersions:
    def __init__(self, db):
        self.db = db

    @staticmethod
    def matches(source, target):
        if source["register_id"] != target["register_id"]:
            return False
        if target.get("pinned_source_id") and source["id"] != target["pinned_source_id"]:
            return False
        wanted = article_identity(target)
        actual = {**identity_from_url(source.get("url") or source.get("canonical_url")), **article_identity(source)}
        if wanted:
            # A conflicting supplied identifier must never broaden an exact match.
            if any(key in actual and actual[key] != value for key, value in wanted.items()):
                return False
            return any(actual.get(key) == value for key, value in wanted.items())
        if target.get("canonical_url"):
            return urldefrag(source.get("url") or source.get("canonical_url") or "")[0] == urldefrag(target["canonical_url"])[0]
        return bool(target.get("pinned_source_id"))

    def projection(self, conn):
        # Only original M8 packs are read. No user cases, stems, keys or attempts
        # cross this seam. JSON extraction avoids reading those payloads at all.
        for kind, table, key in (("question", "content_question_versions", "question_id"),
                                 ("case", "content_case_versions", "case_id")):
            if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
                continue
            rows = conn.execute(f"SELECT {key} AS entity_id,version,json_extract(body_json,'$.source_records') AS records,json_extract(body_json,'$.sources') AS citations,json_extract(body_json,'$.topic_id') AS topic_id,json_extract(body_json,'$.secondary_topic_ids') AS secondary,json_extract(body_json,'$.objective_ids') AS objectives,(SELECT json_group_array(json_extract(stage.value,'$.sources')) FROM json_each(body_json,'$.stages') stage) AS stage_citations FROM {table}")
            for row in rows:
                citations = json.loads(row["citations"] or "[]")
                for stage in json.loads(row["stage_citations"] or "[]"):
                    citations.extend(json.loads(stage) if isinstance(stage, str) else stage or [])
                yield {"kind": kind, "id": row["entity_id"], "version": row["version"],
                       "topic_id": row["topic_id"], "topic_ids": [row["topic_id"], *json.loads(row["secondary"] or "[]")],
                       "objective_ids": json.loads(row["objectives"] or "[]"),
                       "source_records": json.loads(row["records"] or "[]"), "citations": citations}

    def record(self, conn, entry_id, target, detected_at, basis):
        count = 0
        for item in self.projection(conn):
            if target.get("topic_ids") and not set(target["topic_ids"]) & set(item["topic_ids"]):
                continue
            for source in item["source_records"]:
                if not self.matches(source, target):
                    continue
                locators = sorted({citation["locator"] for citation in item["citations"] if citation["source_id"] == source["id"]})
                if target.get("locators"):
                    locators = sorted(set(locators) & set(target["locators"]))
                if not locators:
                    continue
                count += conn.execute("INSERT INTO update_affected_versions(entry_id,kind,entity_id,version,pinned_source_id,register_id,locators_json,topic_id,objective_ids_json,detected_at,basis) VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(entry_id,kind,entity_id,version,pinned_source_id) DO UPDATE SET locators_json=excluded.locators_json,basis=excluded.basis,state='needs-re-review'",
                    (entry_id, item["kind"], item["id"], item["version"], source["id"], source["register_id"],
                     json.dumps(locators), item["topic_id"], json.dumps(item["objective_ids"]), detected_at, basis)).rowcount
        return count

    @staticmethod
    def decode(row):
        row["locators"] = json.loads(row.pop("locators_json"))
        row["objective_ids"] = json.loads(row.pop("objective_ids_json"))
        return row

    def for_entry(self, entry_id, limit=100, offset=0):
        total = self.db.fetch_one("SELECT COUNT(*) AS count FROM update_affected_versions WHERE entry_id=?", (entry_id,))["count"]
        limit, offset = max(1, min(limit, 250)), max(0, offset)
        rows = self.db.fetch_all("SELECT * FROM update_affected_versions WHERE entry_id=? ORDER BY kind,entity_id,version,pinned_source_id LIMIT ? OFFSET ?", (entry_id, limit, offset))
        return {"affected": [self.decode(row) for row in rows], "total": total, "limit": limit, "offset": offset,
                "next_offset": offset + len(rows) if offset + len(rows) < total else None}

    def needs_re_review(self, kind, identifier, version):
        rows = self.db.fetch_all("SELECT a.*,e.url,e.title,e.review_state FROM update_affected_versions a JOIN update_entries e ON e.id=a.entry_id WHERE a.kind=? AND a.entity_id=? AND a.version=? ORDER BY a.detected_at,a.entry_id,a.pinned_source_id", (kind, identifier, version))
        annotations = [self.decode(row) for row in rows]
        return {"kind": kind, "id": identifier, "version": version,
                "needs_re_review": any(row["state"] == "needs-re-review" for row in annotations),
                "annotations": annotations}
