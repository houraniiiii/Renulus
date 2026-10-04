"""Opt-in public publication digests. A byte change is evidence for review only."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from urllib.parse import urldefrag, urlparse

from renulus.contracts import ApiError
from renulus.storage import utc_now
from .fetch import validate_url


def freshness(row):
    success = row["last_success_at"]
    if row["state"] == "failed":
        return "stale" if success else "unchecked"
    if not success:
        return "unchecked"
    return "stale" if datetime.now(timezone.utc) - datetime.fromisoformat(success) > timedelta(days=7) else "checked-recently"


class Publications:
    def __init__(self, updates):
        self.updates, self.db = updates, updates.db

    def hosts(self, source_id):
        source = next((s for s in self.updates.sources if s["id"] == source_id), None)
        if not source:
            raise ApiError("source_missing", "Choose a source in docs/SOURCES.md", 404)
        hosts = {urlparse(url).hostname.lower() for url in source["urls"]}
        return hosts | {host[4:] if host.startswith("www.") else "www." + host for host in hosts}

    def candidates(self, source_id):
        allowed = self.hosts(source_id)
        source = next(s for s in self.updates.sources if s["id"] == source_id)
        candidates = {}
        def add(url, title, provenance):
            url = urldefrag(url)[0]
            try:
                validate_url(url, allowed)
            except (ApiError, ValueError):
                return
            candidates[url] = {"url": url, "title": title, "provenance": provenance}
        for url in source["urls"][1:]:
            if urlparse(url).path.lower().endswith(".pdf"):
                add(url, source["title"], "docs/SOURCES.md")
        row = self.db.fetch_one("SELECT links_json FROM update_source_checks WHERE source_id=?", (source_id,))
        for link in json.loads(row["links_json"]) if row else []:
            add(link["url"], link["label"] or source["title"], "official publication-link check")
        content = self.updates.services.registry.get("content")
        if content and hasattr(content, "list_sources"):
            for pinned in content.list_sources():
                if pinned["register_id"] == source_id:
                    add(pinned["url"], pinned["title"], "installed pinned source metadata")
        return sorted(candidates.values(), key=lambda value: value["url"])

    def track(self, source_id, url, permission_reference, max_bytes=16_000_000):
        url = urldefrag(url)[0]
        validate_url(url, self.hosts(source_id))
        candidate = next((c for c in self.candidates(source_id) if c["url"] == url), None)
        if not candidate:
            raise ApiError("publication_not_registered", "Select a publication from registered or checked official source links")
        if not permission_reference.strip():
            raise ApiError("publication_permission_required", "Record the permission for an anonymous public digest check")
        if not 1024 <= max_bytes <= 20_000_000:
            raise ApiError("publication_limit_invalid", "Publication checks must be bounded to at most 20 MB")
        identifier = "publication_" + hashlib.sha256((source_id + "\n" + url).encode()).hexdigest()[:24]
        with self.db.transaction() as conn:
            existing = conn.execute("SELECT enabled FROM update_publications WHERE id=?", (identifier,)).fetchone()
            if (not existing or not existing["enabled"]) and conn.execute("SELECT COUNT(*) FROM update_publications WHERE enabled=1").fetchone()[0] >= 100:
                raise ApiError("publication_tracking_limit", "Stop tracking a publication before adding more than 100")
            conn.execute("INSERT INTO update_publications(id,source_id,url,title,permission_reference,max_bytes,tracked_at) VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET enabled=1,permission_reference=excluded.permission_reference,max_bytes=excluded.max_bytes",
                         (identifier, source_id, url, candidate["title"], permission_reference.strip(), max_bytes, utc_now()))
        return self.get(identifier)

    @staticmethod
    def decode(row):
        row["fetch_metadata"] = json.loads(row.pop("fetch_metadata_json"))
        row["freshness"] = freshness(row)
        row["enabled"] = bool(row["enabled"])
        return row

    def get(self, identifier):
        row = self.db.fetch_one("SELECT * FROM update_publications WHERE id=?", (identifier,))
        if not row:
            raise ApiError("publication_missing", "This tracked publication is unavailable", 404)
        return self.decode(row)

    def list(self):
        return [self.decode(row) for row in self.db.fetch_all("SELECT * FROM update_publications WHERE enabled=1 ORDER BY source_id,title,id")]

    def stop(self, identifier):
        self.get(identifier)
        self.db.execute("UPDATE update_publications SET enabled=0 WHERE id=?", (identifier,))
        return {"id": identifier, "enabled": False}

    async def check(self, identifier, force=False):
        row = self.get(identifier)
        if not row["enabled"]:
            raise ApiError("publication_tracking_disabled", "Resume tracking this publication before checking it")
        if row["last_checked_at"] and not force and datetime.now(timezone.utc) - datetime.fromisoformat(row["last_checked_at"]) < timedelta(hours=6):
            return {**row, "cached": True, "review_required": row["state"] == "changed"}
        now = utc_now()
        try:
            allowed = self.hosts(row["source_id"])
            body, headers, final_url = await self.updates.fetcher.fetch(row["url"], allowed, limit=row["max_bytes"])
            validate_url(final_url, allowed)
            if not body or len(body) > row["max_bytes"]:
                raise ApiError("publication_response_invalid", "The publication response was empty or exceeded its limit")
            media_type = headers.get("content-type", "").split(";")[0].lower().strip()
            if urlparse(row["url"]).path.lower().endswith(".pdf"):
                if not body.startswith(b"%PDF-"):
                    raise ApiError("publication_format_changed", "The public PDF returned a different format; access needs checking")
            elif media_type not in ("text/html", "application/xhtml+xml", "text/plain", "application/xml", "text/xml", "application/pdf", "application/json"):
                raise ApiError("publication_format_unsupported", "This response is not supported publication data")
            digest = hashlib.sha256(body).hexdigest()
            metadata = {"sha256": digest, "bytes": len(body), "media_type": media_type, "final_url": final_url,
                        "etag": headers.get("etag"), "last_modified": headers.get("last-modified")}
            with self.db.transaction() as conn:
                current = conn.execute("SELECT digest,observation,enabled FROM update_publications WHERE id=?", (identifier,)).fetchone()
                if not current["enabled"]:
                    return {"id": identifier, "state": "tracking-stopped"}
                state = "baseline" if not current["digest"] else "changed" if current["digest"] != digest else "unchanged"
                observation = current["observation"] + int(state != "unchanged")
                conn.execute("UPDATE update_publications SET digest=?,observation=?,fetch_metadata_json=?,last_checked_at=?,last_success_at=?,state=?,error_code=NULL WHERE id=?",
                             (digest, observation, json.dumps(metadata), now, now, state, identifier))
                if state == "changed":
                    identity = f"publication:{identifier}:{observation}:{digest}"
                    entry_id = "update_" + hashlib.sha256(identity.encode()).hexdigest()[:24]
                    change = {"publication_id": identifier, "canonical_url": row["url"], "previous_sha256": current["digest"],
                              "observed": metadata, "permission_reference": row["permission_reference"],
                              "change_basis": "published bytes changed; edition and educational implications unreviewed"}
                    conn.execute("INSERT INTO update_entries(id,source_id,external_id,title,url,kind,publication_date,discovered_at,review_state,summary,source_metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                        (entry_id, row["source_id"], identity, "Publication content changed: " + row["title"], row["url"],
                         "publication-change", None, now, "pending", "Inspect the changed publication before reviewing its status or educational implications.", json.dumps(change)))
            return {**self.get(identifier), "review_required": state == "changed"}
        except Exception as error:
            code = error.code if isinstance(error, ApiError) else "publication_fetch_failed"
            self.db.execute("UPDATE update_publications SET last_checked_at=?,state='failed',error_code=? WHERE id=? AND enabled=1", (now, code, identifier))
            return {**self.get(identifier), "error": {"code": code, "message": "Publication check failed. The previous digest and last successful check are retained."}}
