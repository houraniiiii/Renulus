"""Bounded Europe PMC metadata discovery and exact-identity refresh, no paid tools."""
from datetime import date, timedelta
import hashlib
import json
import re
from urllib.parse import urlencode

from renulus.contracts import ApiError
from renulus.storage import utc_now
from .models import article_identity
from .reviews import canonical


def publication_types(article):
    types = article.get("pubTypeList", {})
    types = types.get("pubType", []) if isinstance(types, dict) else types
    if isinstance(types, str):
        types = [types]
    return [str(value) for value in (types or [])] + ([str(article["pubType"])] if article.get("pubType") else [])


def metadata(article):
    # Retain bibliographic/status metadata, not core abstracts or full text.
    result = {key: article[key] for key in ("id", "source", "doi", "pmid", "pmcid", "title",
              "firstPublicationDate", "pubYear", "isOpenAccess", "inPMC", "inEPMC",
              "pubType", "pubTypeList", "isRetracted", "commentCorrectionList") if key in article}
    identities = {key: article[key] for key in ("doi", "pmid", "pmcid") if article.get(key)}
    if article.get("source", "MED") == "MED" and str(article["id"]).isdigit():
        identities.setdefault("pmid", str(article["id"]))
    result["identifiers"] = article_identity(identities)
    result["publication_types"] = publication_types(article)
    # Preliminary status is a metadata hint. Never infer final guidance.
    result["reported_publication_status"] = "preprint" if article.get("source") == "PPR" or any("preprint" in value.lower() for value in result["publication_types"]) else "unknown"
    return result


def entry_kind(article):
    types = " ".join(publication_types(article)).lower()
    if "retract" in types or article.get("isRetracted") in ("Y", True):
        return "retraction"
    if any(value in types for value in ("erratum", "correction", "corrigendum")):
        return "correction"
    return "research"


class Literature:
    def __init__(self, updates):
        self.updates, self.db = updates, updates.db

    async def query(self, query, page_size=25):
        url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?" + urlencode(
            {"query": query, "format": "json", "resultType": "core", "pageSize": page_size, "sort": "FIRST_PDATE_D desc"})
        body, _, _ = await self.updates.fetcher.fetch(url, {"www.ebi.ac.uk"})
        result = json.loads(body)
        articles = result.get("resultList", {}).get("result") if isinstance(result, dict) else None
        if not isinstance(articles, list) or len(articles) > page_size:
            raise ApiError("literature_metadata_invalid", "The literature source returned unsupported metadata", 502)
        return articles, result.get("hitCount")

    def record(self, article, topic_ids, now, previous_entry=None):
        source, article_id = str(article.get("source", "MED")), str(article.get("id", ""))
        if not re.fullmatch(r"[A-Z]{2,10}", source) or not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", article_id):
            raise ApiError("literature_identity_invalid", "The literature record has no supported publication identity", 502)
        article = {**article, "source": source, "id": article_id}
        current_metadata = metadata(article)
        fingerprint = hashlib.sha256(canonical(current_metadata).encode()).hexdigest()
        external_id = f"epmc:{source}:{article_id}"
        with self.db.transaction() as conn:
            prior = conn.execute("SELECT * FROM update_literature_records WHERE external_id=?", (external_id,)).fetchone()
            legacy = conn.execute("SELECT * FROM update_entries WHERE external_id=?", (external_id,)).fetchone() if not prior else None
            if not prior and legacy:
                legacy_metadata = metadata(json.loads(legacy["source_metadata_json"]))
                prior = {"fingerprint": hashlib.sha256(canonical(legacy_metadata).encode()).hexdigest(), "observation": 1,
                         "entry_id": legacy["id"], "metadata_json": canonical(legacy_metadata)}
            state = "baseline" if not prior else "unchanged" if prior["fingerprint"] == fingerprint else "changed"
            observation = (prior["observation"] if prior else 0) + int(state != "unchanged")
            entry_id = prior["entry_id"] if prior else None
            if state != "unchanged":
                identity = external_id if not prior else f"{external_id}:revision:{observation}:{fingerprint}"
                entry_id = "update_" + hashlib.sha256(identity.encode()).hexdigest()[:24]
                article_url = f"https://europepmc.org/article/{source}/{article_id}"
                source_metadata = {**current_metadata, "metadata_fingerprint": fingerprint,
                                   "previous_fingerprint": prior["fingerprint"] if prior else None,
                                   "previous_entry_id": prior["entry_id"] if prior else None}
                conn.execute("INSERT OR IGNORE INTO update_entries(id,source_id,external_id,title,url,kind,publication_date,discovered_at,review_state,summary,topic_ids_json,source_metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (entry_id, "L03", identity, article.get("title", "Untitled publication"), article_url, entry_kind(article),
                     article.get("firstPublicationDate"), now, "pending", "Publication metadata requires review; notice identity and original article identity are separate.", canonical(topic_ids), canonical(source_metadata)))
                # Metadata notices do not identify the affected original article
                # without reviewed relationship evidence. No L03-family flags.
                if prior:
                    # Only the same record's prior review is invalidated. A
                    # correction/retraction notice cannot identify another article
                    # or publish an educational review through detection alone.
                    target = {"register_id": "L03", "canonical_url": article_url,
                              **current_metadata["identifiers"]}
                    self.updates.affected.record(conn, entry_id, target, now, "publication metadata changed; educational implication unreviewed")
                    self.updates.reviews.observed_change(conn, entry_id, target, prior["fingerprint"], current_metadata, now)
            elif topic_ids:
                entry = conn.execute("SELECT topic_ids_json,review_state FROM update_entries WHERE id=?", (entry_id,)).fetchone()
                if entry["review_state"] == "pending":
                    merged = sorted(set(json.loads(entry["topic_ids_json"])) | set(topic_ids))
                    conn.execute("UPDATE update_entries SET topic_ids_json=? WHERE id=?", (canonical(merged), entry_id))
            conn.execute("INSERT INTO update_literature_records(external_id,entry_id,fingerprint,observation,metadata_json,last_checked_at,last_success_at,state) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(external_id) DO UPDATE SET entry_id=excluded.entry_id,fingerprint=excluded.fingerprint,observation=excluded.observation,metadata_json=excluded.metadata_json,last_checked_at=excluded.last_checked_at,last_success_at=excluded.last_success_at,state=excluded.state,error_code=NULL",
                         (external_id, entry_id, fingerprint, observation, canonical(current_metadata), now, now, state))
        if state == "changed":
            self.updates.reviews.sync("observed:" + entry_id)
        return {"external_id": external_id, "entry_id": entry_id, "state": state, "discovered": int(state != "unchanged")}

    async def check(self, topic_ids, days=7):
        content = self.updates.services.registry.get("content")
        topics = {topic["id"]: topic.get("title", topic.get("name", topic["id"])) for topic in content.list_topics()} if content else {}
        selected = [(key, topics[key]) for key in dict.fromkeys(topic_ids) if key in topics][:5]
        if not selected or any(len(topic) > 200 for key, topic in selected):
            raise ApiError("topics_required", "Choose an installed topic for the literature check")
        if not 1 <= days <= 90 or len(topic_ids) > 5 or any(key not in topics for key in topic_ids):
            raise ApiError("literature_limits", "Choose up to five installed topics and a window of 1–90 days")
        today = date.today()
        since = (today - timedelta(days=days)).isoformat()
        now, discovered, checks = utc_now(), 0, []
        for topic_id, topic in selected:
            # Only the canonical installed topic label leaves the app.
            query = f'({topic}) FIRST_PDATE:[{since} TO {today.isoformat()}]'
            found, checked = 0, 0
            try:
                articles, hits = await self.query(query)
                for article in articles:
                    change = self.record(article, [topic_id], now)
                    found += change["discovered"]
                    discovered += change["discovered"]
                    checked += 1
                self.db.execute("INSERT INTO update_literature_checks(topic_id,last_checked_at,last_success_at,state,result_count) VALUES(?,?,?,'checked',?) ON CONFLICT(topic_id) DO UPDATE SET last_checked_at=excluded.last_checked_at,last_success_at=excluded.last_success_at,state='checked',error_code=NULL,result_count=excluded.result_count",
                                (topic_id, now, now, len(articles)))
                checks.append({"topic_id": topic_id, "state": "checked", "discovered": found, "records_checked": len(articles),
                               "hit_count": hits, "truncated": isinstance(hits, int) and hits > len(articles)})
            except Exception as error:
                code = error.code if isinstance(error, ApiError) else "literature_fetch_failed"
                self.db.execute("INSERT INTO update_literature_checks(topic_id,last_checked_at,state,error_code) VALUES(?,?,'failed',?) ON CONFLICT(topic_id) DO UPDATE SET last_checked_at=excluded.last_checked_at,state='failed',error_code=excluded.error_code", (topic_id, now, code))
                checks.append({"topic_id": topic_id, "state": "failed", "error_code": code, "discovered": found, "records_checked": checked})
        return {"discovered": discovered, "checked_at": now, "checks": checks,
                "state": "checked" if all(item["state"] == "checked" for item in checks) else "partial" if discovered or any(item["state"] == "checked" for item in checks) else "failed",
                "review_state": "pending", "source": "Europe PMC publication metadata", "max_records_per_topic": 25}

    def checks(self):
        return self.db.fetch_all("SELECT * FROM update_literature_checks ORDER BY topic_id")

    async def refresh(self, entry):
        parts = entry["external_id"].split(":")
        if len(parts) < 3 or parts[0] != "epmc" or not re.fullmatch(r"[A-Z]{2,10}", parts[1]) or not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", parts[2]):
            raise ApiError("literature_identity_invalid", "This update has no supported exact article identity")
        external_id = ":".join(parts[:3])
        now = utc_now()
        if not self.db.fetch_one("SELECT 1 FROM update_literature_records WHERE external_id=?", (external_id,)):
            old = metadata(entry["source_metadata"])
            self.db.execute("INSERT OR IGNORE INTO update_literature_records(external_id,entry_id,fingerprint,metadata_json,state) VALUES(?,?,?,?,'unverified-baseline')",
                            (external_id, entry["id"], hashlib.sha256(canonical(old).encode()).hexdigest(), canonical(old)))
        try:
            articles, _ = await self.query(f'EXT_ID:{parts[2]} AND SRC:{parts[1]}', page_size=1)
            if not articles or str(articles[0].get("id")) != parts[2] or articles[0].get("source", "MED") != parts[1]:
                raise ApiError("literature_record_unavailable", "The exact article metadata could not be checked; absence is not a scientific retraction", 502)
            change = self.record(articles[0], entry["topic_ids"], now)
            return {**change, "checked_at": now, "entry": self.updates.get_entry(entry["id"]),
                    "latest_entry": self.updates.get_entry(change["entry_id"])}
        except Exception as error:
            code = error.code if isinstance(error, ApiError) else "literature_fetch_failed"
            self.db.execute("UPDATE update_literature_records SET last_checked_at=?,state='failed',error_code=? WHERE external_id=?", (now, code, external_id))
            return {"state": "failed", "checked_at": now, "entry": self.updates.get_entry(entry["id"]),
                    "error": {"code": code, "message": "Article metadata check failed. Prior metadata and review remain dated evidence."}}
