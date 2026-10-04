from datetime import date, datetime, timedelta, timezone
import hashlib
from html.parser import HTMLParser
import json
from urllib.parse import urlencode, urljoin, urlparse

from renulus.contracts import ApiError
from renulus.storage import utc_now
from .fetch import SourceFetcher
from .sources import read_register
from .publications import Publications, freshness


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
        return self.decode_entry(row)

    def list_entries(self, reviewed_only=False, *, limit=100, offset=0, state=None):
        state = "reviewed" if reviewed_only else state
        if state not in (None, "pending", "reviewed", "dismissed"):
            raise ApiError("review_state_invalid", "Choose a supported update queue")
        rows = self.db.fetch_all("SELECT * FROM update_entries " +
            ("WHERE review_state=? " if state else "") + "ORDER BY discovered_at DESC,id DESC LIMIT ? OFFSET ?",
            ([state] if state else []) + [max(1, min(limit, 250)), max(0, offset)])
        return [self.decode_entry(row) for row in rows]

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
        content = self.services.registry.get("content")
        topics = {topic["id"]: topic.get("title", topic.get("name", topic["id"]))
                  for topic in content.list_topics()} if content else {}
        selected = [(key, topics[key]) for key in topic_ids if key in topics][:5]
        if not selected:
            raise ApiError("topics_required", "Choose an installed topic for the literature check")
        since = (date.today() - timedelta(days=days)).isoformat()
        now, discovered = utc_now(), 0
        for topic_id, topic in selected:
            # Only canonical topic labels leave the app, never raw case or chat text.
            query = f'({topic}) FIRST_PDATE:[{since} TO {date.today().isoformat()}]'
            url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?" + urlencode(
                {"query": query, "format": "json", "pageSize": 25, "sort": "FIRST_PDATE_D desc"})
            body, _, _ = await self.fetcher.fetch(url, {"www.ebi.ac.uk"})
            result = json.loads(body)
            with self.db.transaction() as conn:
                for article in result.get("resultList", {}).get("result", []):
                    external_id = f"epmc:{article.get('source', 'MED')}:{article['id']}"
                    title, pub_type = article.get("title", "Untitled publication"), article.get("pubType", "")
                    kind = "retraction" if "retract" in pub_type.lower() else "correction" if any(
                        word in pub_type.lower() for word in ("erratum", "correction")) else "research"
                    article_url = f"https://europepmc.org/article/{article.get('source','MED')}/{article['id']}"
                    count = conn.execute("INSERT OR IGNORE INTO update_entries VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        ("update_" + hashlib.sha256(external_id.encode()).hexdigest()[:24], "L03", external_id,
                         title, article_url, kind, article.get("firstPublicationDate"), now, None, None,
                         "pending", "New publication metadata. Educational implications have not been reviewed.",
                         json.dumps([topic_id]), json.dumps(article), None)).rowcount
                    discovered += count
        return {"discovered": discovered, "checked_at": now, "review_state": "pending",
                "source": "Europe PMC publication metadata"}

    def review(self, identifier, summary, topic_ids, reviewer, state):
        if state == "reviewed" and not summary.strip():
            raise ApiError("review_summary_required", "Write the reviewed educational implication")
        count = self.db.execute("UPDATE update_entries SET summary=?,topic_ids_json=?,reviewer=?,reviewed_at=?,review_state=? WHERE id=?",
            (summary, json.dumps(topic_ids), reviewer, utc_now(), state, identifier))
        if not count:
            raise ApiError("update_missing", "This update is no longer available", 404)
        return self.get_entry(identifier)

    def mark_read(self, identifier):
        if not self.db.execute("UPDATE update_entries SET read_at=? WHERE id=?", (utc_now(), identifier)):
            raise ApiError("update_missing", "This update is no longer available", 404)
        return {"read": True}
