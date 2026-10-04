"""A narrow local source-status journal, independent of source fetching."""
import hashlib
import json
import re
from urllib.parse import unquote, urldefrag, urlparse

from pydantic import ValidationError

from ..contracts import ApiError
from ..storage import utc_now
from .models import SourceMetadata

CHANGE_FIELDS = {
    "publication_status", "publication_date", "revision_date",
    "latest_final_verified", "content_reviewed", "review_due", "correction",
    "retracted", "superseded", "repository_removed", "access_changed",
    "supersedes", "replaced_topics", "excluded_pages",
}
IDENTITY_FIELDS = {"canonical_url", "pinned_source_id", "doi", "pmid", "pmcid"}


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def article_ids(value):
    result = {}
    for key in ("doi", "pmid", "pmcid"):
        raw = value.get(key)
        if not raw:
            continue
        text = str(raw).strip()
        if key == "doi":
            text = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", text, flags=re.I).lower()
            pattern = r"10\.\d{4,9}/[^\s\"<>]+"
        else:
            text = text.upper() if key == "pmcid" else text
            pattern = r"PMC[1-9]\d{0,11}" if key == "pmcid" else r"[1-9]\d{0,11}"
        if not re.fullmatch(pattern, text):
            raise ValueError("Invalid publication identity")
        result[key] = text
    return result


def url_ids(url):
    parts = urlparse(url or "")
    path = unquote(parts.path).strip("/")
    if parts.hostname in ("doi.org", "dx.doi.org"):
        return article_ids({"doi": path})
    if parts.hostname == "pubmed.ncbi.nlm.nih.gov" and path.isdigit():
        return article_ids({"pmid": path})
    match = re.fullmatch(r"article/(MED|PMC)/([A-Za-z0-9]+)", path, re.I)
    if parts.hostname in ("europepmc.org", "www.europepmc.org") and match:
        return article_ids({"pmid" if match[1].upper() == "MED" else "pmcid": match[2]})
    match = re.search(r"(?:^|/)articles/(PMC\d+)(?:/|$)", path, re.I)
    if parts.hostname in ("pmc.ncbi.nlm.nih.gov", "www.ncbi.nlm.nih.gov") and match:
        return article_ids({"pmcid": match[1]})
    return {}


def validate_event(payload):
    try:
        if not isinstance(payload, dict) or type(payload.get("contract_version")) is not int or payload["contract_version"] != 1:
            raise ValueError()
        if not isinstance(payload.get("event_id"), str) or not 1 <= len(payload["event_id"]) <= 200:
            raise ValueError()
        if not re.fullmatch(r"[A-Z]\d{2}", payload["source_id"]):
            raise ValueError()
        identity, changes = payload["identity"], payload["changes"]
        if not isinstance(identity, dict) or set(identity) - IDENTITY_FIELDS or not identity:
            raise ValueError()
        if not isinstance(changes, dict) or not changes or set(changes) - CHANGE_FIELDS:
            raise ValueError()
        explicit = article_ids(identity)
        inferred = url_ids(identity.get("canonical_url"))
        if any(key in explicit and explicit[key] != value for key, value in inferred.items()):
            raise ValueError()
        if "retracted" in changes and not (explicit or inferred):
            raise ValueError()
        SourceMetadata.model_validate({"source_id": payload["source_id"], **changes}, strict=True)
        scope = payload.get("scope", {})
        if not isinstance(scope, dict) or set(scope) - {"topic_ids", "locators"}:
            raise ValueError()
        if any(not isinstance(items, list) or len(items) > 100 or any(not isinstance(x, str) or len(x) > 1000 for x in items) for items in scope.values()):
            raise ValueError()
        observed_only = set(changes) <= {"latest_final_verified", "content_reviewed"} and all(value is False for value in changes.values())
        evidence = payload.get("evidence")
        if not observed_only and (not isinstance(evidence, list) or not evidence or not all(isinstance(item, dict) and item.get("inspected") is True for item in evidence)):
            raise ValueError()
        canonical(payload)
        return payload
    except (KeyError, TypeError, ValueError, ValidationError):
        raise ApiError("source_status_invalid", "Check exact publication identity, reviewed evidence and source-status fields", 422) from None


def matches(metadata, event):
    if metadata["source_id"] != event["source_id"]:
        return False
    identity = event["identity"]
    try:
        wanted = {**url_ids(identity.get("canonical_url")), **article_ids(identity)}
        actual = {**url_ids(metadata.get("canonical_url")), **article_ids(metadata)}
    except ValueError:
        return False
    if wanted:
        if any(key in actual and actual[key] != value for key, value in wanted.items()):
            return False
        identified = any(actual.get(key) == value for key, value in wanted.items())
    else:
        identified = bool(identity.get("canonical_url")) and urldefrag(identity["canonical_url"])[0] == urldefrag(metadata.get("canonical_url") or "")[0]
    if not identified:
        return False  # Pack-only IDs do not identify a Library revision.
    scope = event.get("scope", {})
    if scope.get("topic_ids") and metadata.get("topic_ids") and not set(scope["topic_ids"]) & set(metadata["topic_ids"]):
        return False
    if scope.get("locators") and not set(scope["locators"]) & {metadata.get("collection_chapter"), metadata.get("collection_section")}:
        return False  # Unmapped chapter/page identities require explicit review.
    return True


class SourceStatusJournal:
    def __init__(self, repository):
        self.repository, self.db = repository, repository.db

    def events(self, source_id, conn=None):
        if conn is not None:
            rows = conn.execute("SELECT payload_json FROM knowledge_source_status_events WHERE source_id=? ORDER BY rowid", (source_id,)).fetchall()
        elif self.db.fetch_one("SELECT 1 FROM sqlite_master WHERE type='table' AND name='knowledge_source_status_events'"):
            rows = self.db.fetch_all("SELECT payload_json FROM knowledge_source_status_events WHERE source_id=? ORDER BY rowid", (source_id,))
        else:
            rows = []  # Explicit isolated engine fixtures can have only base DDL.
        return [json.loads(row["payload_json"]) for row in rows]

    def effective(self, metadata, events=None):
        value = metadata.model_dump() if isinstance(metadata, SourceMetadata) else dict(metadata)
        for event in events if events is not None else self.events(value["source_id"]):
            if matches(value, event):
                value.update(event["changes"])
                if value["publication_status"] != "final" or any(value[key] for key in ("retracted", "superseded", "repository_removed")):
                    value["latest_final_verified"] = False
        return SourceMetadata.model_validate(value, strict=True)

    def update(self, payload):
        event = validate_event(payload)
        serialized = canonical(event)
        digest = hashlib.sha256(serialized.encode()).hexdigest()
        with self.repository._lock, self.db.transaction() as conn:
            previous = conn.execute("SELECT request_hash FROM knowledge_source_status_events WHERE id=?", (event["event_id"],)).fetchone()
            if previous and previous["request_hash"] != digest:
                raise ApiError("source_status_conflict", "That source event belongs to different evidence", 409)
            conn.execute("INSERT OR IGNORE INTO knowledge_source_status_events VALUES(?,?,?,?,?)",
                         (event["event_id"], event["source_id"], digest, serialized, utc_now()))
            events = self.events(event["source_id"], conn)
            rows = conn.execute("SELECT r.id,r.metadata_json FROM knowledge_revisions r JOIN knowledge_documents d ON d.id=r.document_id WHERE d.deleted_at IS NULL AND d.source_id=?", (event["source_id"],)).fetchall()
            matched = 0
            for row in rows:
                metadata = json.loads(row["metadata_json"])
                matched += int(matches(metadata, event))
                effective = self.effective(metadata, events)
                conn.execute("UPDATE knowledge_revisions SET metadata_json=? WHERE id=?", (effective.model_dump_json(), row["id"]))
        return {"state": "applied" if matched else "no-match", "event_id": event["event_id"], "revisions": matched}
