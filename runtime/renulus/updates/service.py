from datetime import datetime, timedelta, timezone
import hashlib
from html.parser import HTMLParser
import json
from urllib.parse import urljoin, urlparse

from renulus.contracts import ApiError
from renulus.storage import utc_now
from .fetch import SourceFetcher
from .sources import read_register
from .publications import Publications, freshness
from .impact import AffectedVersions
from .reviews import SourceReviews
from .literature import Literature


class Links(HTMLParser):
    def __init__(self, base):
        super().__init__()
        self.base, self.links, self.label, self.href = base, [], [], None
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.href = dict(attrs).get("href")
            self.label = []
    def handle_data(self, data):
        if self.href:
            self.label.append(data.strip())
    def handle_endtag(self, tag):
        if tag == "a" and self.href:
            url, label = urljoin(self.base, self.href), " ".join(x for x in self.label if x)
            if urlparse(url).scheme == "https" and (".pdf" in url.lower() or any(
                word in label.lower() for word in ("guideline", "corrigend", "correction", "draft", "retract"))):
                self.links.append({"url": url, "label": label[:500]})
            self.href = None


class UpdatesService:
    def __init__(self, services, fetcher=None):
        self.services, self.db = services, services.db
        self.fetcher = fetcher or SourceFetcher()
        register = services.paths.source_root / "docs" / "SOURCES.md"
        self.sources = read_register(register) if register.exists() else []
        self.publications = Publications(self)
        self.affected = AffectedVersions(self.db)
        self.reviews = SourceReviews(self)
        self.literature = Literature(self)
        services.on_startup.append(self.reviews.retry_pending)
        for source in self.sources:
            self.db.execute("INSERT INTO update_source_checks(source_id,title,url,snapshot_status) VALUES(?,?,?,?) ON CONFLICT(source_id) DO UPDATE SET title=excluded.title,url=excluded.url,snapshot_status=excluded.snapshot_status",
                            (source["id"], source["title"], source["url"], source["snapshot_status"]))

    def list_sources(self):
        rows = self.db.fetch_all("SELECT * FROM update_source_checks ORDER BY source_id")
        for row in rows:
            row["links"] = json.loads(row.pop("links_json"))
            row["freshness"] = freshness(row)
            row["currentness"] = "Source snapshot and checks do not establish clinical review."
        return rows

    @staticmethod
    def decode_entry(row):
        row["topic_ids"] = json.loads(row.pop("topic_ids_json"))
        row["source_metadata"] = json.loads(row.pop("source_metadata_json"))
        return row

    def get_entry(self, identifier):
        row = self.db.fetch_one("SELECT * FROM update_entries WHERE id=?", (identifier,))
        if not row:
            raise ApiError("update_missing", "This update is no longer available", 404)
        return self.reviews.decorate([self.decode_entry(row)])[0]

    def list_entries(self, reviewed_only=False, *, limit=100, offset=0, state=None):
        state = "reviewed" if reviewed_only else state
        if state not in (None, "pending", "reviewed", "dismissed"):
            raise ApiError("review_state_invalid", "Choose a supported update queue")
        rows = self.db.fetch_all("SELECT * FROM update_entries " +
            ("WHERE review_state=? " if state else "") + "ORDER BY discovered_at DESC,id DESC LIMIT ? OFFSET ?",
            ([state] if state else []) + [max(1, min(limit, 250)), max(0, offset)])
        return self.reviews.decorate([self.decode_entry(row) for row in rows])

    def entries_page(self, *, reviewed_only=False, limit=50, offset=0, state=None):
        limit, offset = max(1, min(limit, 250)), max(0, offset)
        state = "reviewed" if reviewed_only else state
        rows = self.list_entries(limit=limit, offset=offset, state=state)
        counts = {key: 0 for key in ("pending", "reviewed", "dismissed")}
        for row in self.db.fetch_all("SELECT review_state,COUNT(*) AS count FROM update_entries GROUP BY review_state"):
            counts[row["review_state"]] = row["count"]
        total = counts[state] if state else sum(counts.values())
        return {"entries": rows, "counts": counts, "total": total, "limit": limit, "offset": offset,
                "next_offset": offset + len(rows) if offset + len(rows) < total else None}

    async def check_source(self, source_id, force=False):
        row = self.db.fetch_one("SELECT * FROM update_source_checks WHERE source_id=?", (source_id,))
        if not row:
            raise ApiError("source_missing", "This source is not in the development register", 404)
        if row["last_checked_at"] and not force and (datetime.now(timezone.utc) -
            datetime.fromisoformat(row["last_checked_at"]) < timedelta(hours=6)):
            result = {"source_id": source_id, "state": row["state"], "cached": True}
            if row["state"] == "failed":
                result["error"] = {"code": row["error_code"], "message": "The previous check failed. Its last successful check has not advanced."}
            return result
        now = utc_now()
        host = urlparse(row["url"]).hostname
        allowed = {host}
        if host.startswith("www."):
            allowed.add(host[4:])
        else:
            allowed.add("www." + host)
        try:
            body, headers, final_url = await self.fetcher.fetch(row["url"], allowed)
            parser = Links(final_url)
            parser.feed(body.decode("utf-8", errors="replace"))
            links = sorted(parser.links, key=lambda entry: (entry["url"], entry["label"]))
            # Watch publication links, avoiding dates/menus that change on every page load.
            fingerprint = hashlib.sha256(json.dumps(links, sort_keys=True).encode()).hexdigest()
            state = "baseline" if not row["fingerprint"] else "changed" if row["fingerprint"] != fingerprint else "unchanged"
            with self.db.transaction() as conn:
                conn.execute("UPDATE update_source_checks SET fingerprint=?,links_json=?,last_checked_at=?,last_success_at=?,state=?,error_code=NULL WHERE source_id=?",
                             (fingerprint, json.dumps(links), now, now, state, source_id))
                if state == "changed":
                    previous = {item["url"] for item in json.loads(row["links_json"])}
                    added = [item for item in links if item["url"] not in previous]
                    identity = f"source:{source_id}:{fingerprint}"
                    conn.execute("INSERT OR IGNORE INTO update_entries VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        ("update_" + hashlib.sha256(identity.encode()).hexdigest()[:24], source_id, identity,
                         "Publication links changed: " + row["title"], final_url, "source-change", None, now,
                         None, None, "pending", "Inspect the official publication, final/draft status, corrections and replaced scope before reviewing this change.",
                         "[]", json.dumps({"new_links": added, "all_links": links, "snapshot_status": row["snapshot_status"]}), None))
            return {"source_id": source_id, "state": state, "checked_at": now, "links": links,
                    "review_required": state == "changed"}
        except Exception as error:
            code = error.code if isinstance(error, ApiError) else "source_fetch_failed"
            self.db.execute("UPDATE update_source_checks SET last_checked_at=?,state='failed',error_code=? WHERE source_id=?",
                            (now, code, source_id))
            return {"source_id": source_id, "state": "failed", "checked_at": now,
                    "error": {"code": code, "message": "The official source could not be checked. Its last successful check remains visible."}}

    async def check_literature(self, topic_ids, days=7):
        return await self.literature.check(topic_ids, days)

    async def refresh_entry(self, identifier):
        entry = self.get_entry(identifier)
        if entry["source_id"] == "L03" and entry["external_id"].startswith("epmc:"):
            return await self.literature.refresh(entry)
        publication_id = entry["source_metadata"].get("publication_id")
        result = await self.publications.check(publication_id, force=True) if publication_id else await self.check_source(entry["source_id"], force=True)
        return {**result, "entry": self.get_entry(identifier)}

    def review(self, identifier, summary, topic_ids, reviewer, state, *, target=None, changes=None, evidence=None):
        return self.reviews.review(identifier, summary, topic_ids, reviewer, state,
                                   target=target, changes=changes, evidence=evidence)

    def mark_read(self, identifier):
        if not self.db.execute("UPDATE update_entries SET read_at=? WHERE id=?", (utc_now(), identifier)):
            raise ApiError("update_missing", "This update is no longer available", 404)
        return {"read": True}
