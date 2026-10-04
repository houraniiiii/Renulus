"""Read-only acquisition metadata and explicit, selected import batches."""
import hashlib
import json
from pathlib import Path

from ..contracts import ApiError, ContextScope, Scope
from ..storage.database import utc_now
from .models import Rights, SourceMetadata
from .repository import MEDIA

COLLECTION = Path("C:/Users/karol/Documents/Renulus-data")
MANIFEST = "metadata/acquisition-2026-10-04/acquisition-manifest.jsonl"
CATALOGUE = "metadata/era-neph-manual-2026-10-04-catalogue.json"
VERIFICATION = "metadata/era-neph-manual-2026-10-04-file-verification.json"


class CollectionCatalogue:
    def __init__(self, repository, root=COLLECTION):
        self.repository, self.db = repository, repository.db
        self.root = Path(root).resolve()

    def _path(self, value):
        path = Path(value)
        if not path.is_absolute():
            path = self.root / path
        path = path.resolve()
        if not path.is_relative_to(self.root) or not path.is_file():
            raise ApiError("collection_path_invalid", "The acquisition entry has no valid file within the authorised collection", 409)
        return path

    def _entry(self, path, source_id, title, digest, size, metadata, rights, reserved=False):
        relative = path.relative_to(self.root).as_posix()
        identifier = "asset_" + hashlib.sha256((source_id + "\n" + relative).encode()).hexdigest()[:24]
        supported = path.suffix.lower() in MEDIA
        eligible = supported and not reserved and rights.index and rights.embedding and rights.cache and rights.display
        return {"id": identifier, "collection_path": relative, "source_id": source_id,
                "title": title, "expected_sha256": digest, "bytes": size, "reserved": reserved,
                "eligibility": "eligible" if eligible else ("reserved" if reserved else "permission_or_format_unavailable"),
                "metadata": metadata.model_dump(), "rights": rights.model_dump()}

    def preview(self, *, source_id=None, limit=250, offset=0):
        entries, errors, seen = [], [], set()
        catalogue_path = self.root / CATALOGUE
        if catalogue_path.is_file() and source_id in (None, "E01"):
            catalogue = json.loads(catalogue_path.read_text(encoding="utf-8-sig"))
            verification = json.loads((self.root / VERIFICATION).read_text(encoding="utf-8-sig"))
            verified = {str(Path(x["path"]).resolve()): x for x in verification.get("files", [])}
            files = [(section, chapter, item) for section in catalogue.get("sections", [])
                     for chapter in section.get("chapters", []) for item in chapter.get("files", [])]
            files.extend(({}, {}, item) for item in catalogue.get("course_files", []))
            for section, chapter, item in files:
                try:
                    path = self._path(item["collection_path"])
                    check = verified.get(str(path))
                    if not check or check.get("status") != "valid_pdf" or check.get("sha256") != item.get("sha256"):
                        raise ApiError("verification_missing", "Manual file has no matching integrity record", 409)
                    categories = item.get("categories", [])
                    reserved = any(x in ("questions", "mcqs", "test", "assessment") for x in categories)
                    notes = ["Receipt is not a publication or edition date"]
                    if chapter.get("source_content_issue"):
                        notes.append("Catalogue records a source content anomaly; human review is required")
                    metadata = SourceMetadata(source_id="E01", source_owner=catalogue.get("source_owner", "ERA"),
                        canonical_url=item.get("source_url") or chapter.get("source_url"), access_class="authorised-user-download",
                        received_at=catalogue.get("receipt_date"), edition=catalogue.get("edition"),
                        topic_ids=[f"era-section-{section['id']}"] if section else [], notes=notes)
                    rights = Rights(display=True, cache=True, index=True, embedding=True, model_input=True,
                        licence="ERA user-owned access; original terms retained",
                        permission_reference="Owner authorised this manual for local Renulus processing on 2026-10-04; no redistribution inferred",
                        attribution="ERA Neph-Manual; " + chapter.get("title", "Course material"))
                    title = chapter.get("title", "ERA Neph-Manual") + " — " + item.get("label", path.stem)
                    entry = self._entry(path, "E01", title, item.get("sha256"), item.get("bytes"), metadata, rights, reserved)
                    entries.append(entry)
                    seen.add(entry["id"])
                except (ApiError, KeyError, TypeError) as error:
                    errors.append({"manifest": CATALOGUE, "code": getattr(error, "code", "invalid_manual_entry")})
        manifest = self.root / MANIFEST
        if manifest.is_file() and source_id != "E01":
            with manifest.open(encoding="utf-8-sig") as stream:
                for line_no, line in enumerate(stream, 1):
                    try:
                        item = json.loads(line)
                        sid = item.get("source_id")
                        if not sid or (source_id and sid != source_id):
                            continue
                        value = item.get("local_path") or item.get("path")
                        if not value:
                            continue
                        path = self._path(value)
                        reserved = sid == "E02" or bool(item.get("reserved"))
                        rights = self._rights(item)
                        status = str(item.get("status", ""))
                        metadata = SourceMetadata(source_id=sid, source_owner=item.get("source_owner", sid),
                            canonical_url=item.get("origin_url") or item.get("canonical_url"),
                            access_class=item.get("access_class", "unverified"),
                            edition=item.get("edition"), publication_date=item.get("publication_date"),
                            retrieved_at=item.get("retrieved_utc"), checked_at=item.get("checked_at"),
                            publication_status="draft" if "draft" in status else "unknown",
                            latest_final_verified=item.get("latest_final_verified") is True,
                            content_reviewed=item.get("content_reviewed") is True,
                            retracted=item.get("retracted") is True, superseded=item.get("superseded") is True,
                            doi=item.get("doi"), pmid=str(item["pmid"]) if item.get("pmid") else None,
                            pmcid=item.get("pmcid"), notes=["Acquisition does not establish currentness or clinical review"])
                        entry = self._entry(path, sid, item.get("title") or path.stem, item.get("sha256"), item.get("bytes"), metadata, rights, reserved)
                        if entry["id"] not in seen:
                            entries.append(entry)
                            seen.add(entry["id"])
                    except (ValueError, TypeError, KeyError, ApiError):
                        errors.append({"manifest": MANIFEST, "line": line_no, "code": "invalid_manifest_entry"})
        # Manifest-wide totals are observed on this read, never assumed from a
        # previous acquisition summary. Page the large collection metadata.
        eligible = sum(x["eligibility"] == "eligible" for x in entries)
        return {"entries": entries[offset:offset + min(limit, 1000)], "total": len(entries),
                "eligible": eligible, "offset": offset, "errors": errors,
                "checked_at": utc_now(), "indexed": False}

    @staticmethod
    def _rights(item):
        # Accept explicit operation booleans or separately recorded permissions.
        # Unknown language is deliberately not promoted to permission.
        scope = item.get("processing_scope", {})
        licence = item.get("licence", {})
        if isinstance(licence, str):
            licence = {"identifier": licence}
        identifier = licence.get("identifier", "unverified")
        open_licence = identifier.upper().replace(" " , "-") in {"CC-BY-4.0", "CC-BY-3.0", "CC0-1.0", "CC0"}
        def allowed(name, *aliases):
            values = [scope.get(key) for key in (name, *aliases)]
            if any(v is False or (isinstance(v, str) and any(s in v.lower() for s in ("not authorised", "not authorized", "prohibited", "reference verification only"))) for v in values):
                return False
            return any(v is True for v in values) or (open_licence and any(isinstance(v, str) and ("licence" in v.lower() or "permitted" in v.lower()) for v in values))
        return Rights(display=allowed("display", "human_reading"), cache=allowed("cache", "caching", "human_reading"),
            index=allowed("index", "indexing", "indexing_embedding"),
            embedding=allowed("embedding", "indexing_embedding"), model_input=allowed("model_input", "ai_processing"),
            derivation=allowed("derivation"), evaluation=allowed("evaluation"),
            redistribution=allowed("redistribution"), licence=identifier,
            permission_reference=licence.get("evidence_url", licence.get("url", "")),
            attribution=json.dumps(licence.get("attribution", {}), ensure_ascii=False))

    def register(self, *, source_id=None):
        offset, count, errors = 0, 0, []
        while True:
            preview = self.preview(source_id=source_id, limit=1000, offset=offset)
            with self.db.transaction() as conn:
                for entry in preview["entries"]:
                    conn.execute("INSERT INTO knowledge_catalogue(id,collection_path,source_id,title,expected_sha256,bytes,reserved,eligibility,metadata_json,rights_json,checked_at) VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,expected_sha256=excluded.expected_sha256,bytes=excluded.bytes,eligibility=excluded.eligibility,metadata_json=excluded.metadata_json,rights_json=excluded.rights_json,checked_at=excluded.checked_at",
                        (entry["id"], entry["collection_path"], entry["source_id"], entry["title"], entry["expected_sha256"], entry["bytes"], int(entry["reserved"]), entry["eligibility"], json.dumps(entry["metadata"]), json.dumps(entry["rights"]), preview["checked_at"]))
            count += len(preview["entries"])
            errors = preview["errors"]
            offset += 1000
            if offset >= preview["total"]:
                break
        return {"catalogued": count, "errors": errors, "status": "catalogued", "indexed": False}

    def list(self, *, source_id=None, limit=250, offset=0):
        where, args = (" WHERE c.source_id=?", [source_id]) if source_id else ("", [])
        count = self.db.fetch_one("SELECT COUNT(*) AS n FROM knowledge_catalogue c" + where, args)["n"]
        entries = self.db.fetch_all("SELECT c.*,j.state AS processing_status,j.error_code FROM knowledge_catalogue c LEFT JOIN knowledge_jobs j ON j.id=c.job_id" + where + " ORDER BY c.source_id,c.title LIMIT ? OFFSET ?", [*args, min(limit, 1000), offset])
        for entry in entries:
            entry["metadata"] = json.loads(entry.pop("metadata_json"))
            entry["rights"] = json.loads(entry.pop("rights_json"))
            entry["processing_status"] = entry["processing_status"] or "acquired"
        return {"entries": entries, "total": count, "offset": offset}

    def import_selected(self, entry_ids: list[str]):
        if len(entry_ids) > 250:
            raise ApiError("batch_limit", "Select at most 250 files per import batch", 413)
        results = []
        for entry_id in dict.fromkeys(entry_ids):
            entry = self.db.fetch_one("SELECT * FROM knowledge_catalogue WHERE id=?", (entry_id,))
            if not entry:
                results.append({"entry_id": entry_id, "status": "failed", "code": "catalogue_entry_missing"})
                continue
            if entry["eligibility"] != "eligible" or entry["reserved"]:
                results.append({"entry_id": entry_id, "status": "excluded", "code": entry["eligibility"]})
                continue
            try:
                result = self.repository.import_file(self._path(entry["collection_path"]),
                    title=entry["title"], metadata=json.loads(entry["metadata_json"]), rights=json.loads(entry["rights_json"]),
                    scope=ContextScope(kind=Scope.LIBRARY), expected_sha256=entry["expected_sha256"],
                    idempotency_key="catalogue:" + entry_id + ":" + str(entry["expected_sha256"]), process=False)
                self.db.execute("UPDATE knowledge_catalogue SET document_id=?,job_id=? WHERE id=?", (result["document_id"], result["job"]["id"], entry_id))
                results.append({"entry_id": entry_id, **result})
            except ApiError as error:
                results.append({"entry_id": entry_id, "status": "failed", "code": error.code, "message": error.message})
        return {"results": results, "queued": sum(r["status"] == "queued" for r in results)}
