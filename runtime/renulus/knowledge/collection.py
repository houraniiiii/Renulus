"""Read-only acquisition metadata and explicit, selected import batches."""
from __future__ import annotations
import base64
import hashlib
import json
from pathlib import Path
import re

from ..contracts import ApiError, ContextScope, Scope
from ..storage.database import utc_now
from .models import Rights, SourceMetadata
from .repository import MEDIA
from .acquired import (AcquiredLiterature, AcquisitionCancelled, MARKER, catalogue_policy, collection_path,
                       version_identity, version_name, acquisition_topic_ids, unique_object,
                       FrozenLiteratureSelection, recorded_file, recorded_licence, component_exceptions, asset_id)

COLLECTION = Path.home() / "Documents" / "Renulus-data"
MANIFEST = "metadata/acquisition-2026-10-04/acquisition-manifest.jsonl"
CATALOGUE = "metadata/era-neph-manual-2026-10-04-catalogue.json"
VERIFICATION = "metadata/era-neph-manual-2026-10-04-file-verification.json"
SELECTION_FAILURES = {"literature_selection_excluded", "literature_selection_outside",
    "literature_selection_unavailable", "literature_selection_invalid", "literature_selection_changed",
    "literature_selection_review_unavailable", "literature_selection_review_invalid", "literature_project_selection_excluded"}


class CollectionCatalogue:
    def __init__(self, repository, root=COLLECTION):
        self.repository, self.db = repository, repository.db
        self.root = Path(root).resolve()
        self._selection = None

    def _literature_selection(self):
        if self._selection is None or self._selection.root != self.root.resolve():
            self._selection = FrozenLiteratureSelection(self.root)
        return self._selection

    def _path(self, value):
        return collection_path(self.root, value)

    def _entry(self, path, source_id, title, digest, size, metadata, rights, reserved=False):
        relative = path.relative_to(self.root).as_posix()
        identifier = "asset_" + hashlib.sha256((source_id + "\n" + relative).encode()).hexdigest()[:24]
        supported = path.suffix.lower() in MEDIA
        if source_id == "E07" and "illustration_original_png" in metadata.asset_role:
            supported = supported and path.suffix.lower() == ".png"
        if source_id == "L03" and "fulltext_original_PDF" in metadata.asset_role:
            supported = supported and path.suffix.lower() == ".pdf"
        eligible = supported and not reserved and rights.index and rights.embedding and rights.cache and rights.display
        return {"id": identifier, "collection_path": relative, "source_id": source_id,
                "title": title, "expected_sha256": digest, "bytes": size, "reserved": reserved,
                "eligibility": "eligible" if eligible else ("reserved" if reserved else "permission_or_format_unavailable"),
                "metadata": metadata.model_dump(), "rights": rights.model_dump()}

    def preview(self, *, source_id=None, limit=250, offset=0, _all=False):
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
                        collection_section=section.get("title"), collection_chapter=chapter.get("title"),
                        asset_role=categories, notes=notes)
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
                        # Catalogue receipts without reading bodies or testing every
                        # acquired file. Selected import performs existence/hash checks.
                        path = collection_path(self.root, value, must_exist=False)
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
                        if recorded_file(item):
                            metadata.asset_role = [item["artifact_type"]]
                            metadata.latest_final_verified = metadata.content_reviewed = False
                            metadata.original_sha256 = item.get("sha256")
                            metadata.notes.append("renulus-collection-v1:" + json.dumps({key: item.get(key) for key in
                                ("licence", "processing_scope", "acquisition_provenance", "frozen_selection_state", "frozen_selection_exclusion")}, ensure_ascii=False))
                        if sid == "L02":
                            metadata.topic_ids = acquisition_topic_ids(item)
                        entry = self._entry(path, sid, item.get("title") or path.stem, item.get("sha256"), item.get("bytes"), metadata, rights, reserved)
                        policy = catalogue_policy(item)
                        if sid in ("L01", "L02", "L03", "L04", "L05", "L06", "L07", "L08"):
                            selection_policy = self._literature_selection().policy(item)
                            policy = selection_policy or catalogue_policy(item, project_selected=True)
                            if not selection_policy and sid in ("L02", "L03"):
                                metadata.notes.append("renulus-selection-v1:" + json.dumps(self._literature_selection().observation(item), ensure_ascii=False))
                        if policy:
                            entry["eligibility"], explanation = policy
                            entry["rights"] = Rights(licence=rights.licence).model_dump()
                            metadata.notes.append(explanation)
                            metadata.asset_role = [str(item.get("artifact_type", "acquired-payload"))]
                            if sid == "L02" and item.get("artifact_type") == "fulltext-jats":
                                metadata.asset_role.append(MARKER)
                                try:
                                    metadata.edition = version_name(version_identity(item))
                                except ApiError:
                                    pass
                            # Dataset receipt dates and claimed finality do not
                            # settle scientific status for acquired literature.
                            metadata.publication_status = "unknown"
                            metadata.latest_final_verified = metadata.content_reviewed = False
                        entry["metadata"] = metadata.model_dump()
                        if entry["id"] not in seen:
                            entries.append(entry)
                            seen.add(entry["id"])
                    except (ValueError, TypeError, KeyError, ApiError):
                        errors.append({"manifest": MANIFEST, "line": line_no, "code": "invalid_manifest_entry"})
        # Manifest-wide totals are observed on this read, never assumed from a
        # previous acquisition summary. Page the large collection metadata.
        eligible = sum(x["eligibility"] == "eligible" for x in entries)
        return {"entries": entries if _all else entries[offset:offset + min(limit, 1000)], "total": len(entries),
                "eligible": eligible, "offset": offset, "errors": errors,
                "checked_at": utc_now(), "indexed": False}

    @staticmethod
    def _rights(item):
        # Accept explicit operation booleans or separately recorded permissions.
        # Unknown language is deliberately not promoted to permission.
        scope = item.get("processing_scope", {})
        if not isinstance(scope, dict):
            # Acquisition notes are often prose. Retain the catalogue record,
            # but do not infer operation permissions from an unstructured note.
            scope = {}
        licence = item.get("licence", {})
        if isinstance(licence, str):
            licence = {"identifier": licence}
        if not isinstance(licence, dict):
            licence = {}
        identifier = recorded_licence(item)
        open_licence = identifier.upper().replace(" " , "-") in {"CC-BY-4.0", "CC-BY-3.0", "CC0-1.0", "CC0"}
        supported_record = recorded_file(item)
        phrases = {
            "display": {"cc by 4.0 attribution required"},
            "index": {"eligible under cc by 4.0 subject to attribution and exclusions"},
            "embedding": {"eligible under cc by 4.0 subject to attribution and exclusions"},
            "model_input": {"licence allows reuse; no model calls performed"},
            "derivation": {"permitted; indicate changes"},
        } if supported_record else {}
        def allowed(name, *aliases):
            values = [scope[key] for key in (name, *aliases) if key in scope]
            if any(v is False or (isinstance(v, str) and re.search(
                    r"not (?:authori[sz]ed|permitted|allowed|cleared|activated|assessed)|prohibit|denied|unknown|unverified|reading.only|reference verification only", v, re.I)) for v in values):
                return False
            if not supported_record:
                # Preserve existing separately classified source routes. Only
                # E07 PNG/L03 PDF aliases and schema are added by this lane.
                return any(v is True for v in values) or (open_licence and any(
                    isinstance(v, str) and ("licence" in v.lower() or "permitted" in v.lower()) for v in values))
            accepted = {"permitted", "permitted under licence", "permitted under license", *phrases.get(name, set())}
            # Every supplied alias must be understood: a false, denial or
            # unknown phrase cannot be outweighed by another alias's true.
            if any(v is not True and not (open_licence and isinstance(v, str) and v.strip().lower() in accepted) for v in values):
                return False
            if component_exceptions(item) and name not in ("display", "cache"):
                return False
            return bool(values)
        return Rights(display=allowed("display", "human_reading"),
            cache=allowed("cache", "caching", *(("human_reading",) if not supported_record else ())),
            index=allowed("index", "indexing", "indexing_embedding"),
            embedding=allowed("embedding", "indexing_embedding"), model_input=allowed("model_input", "ai_processing"),
            derivation=allowed("derivation"), evaluation=allowed("evaluation"),
            redistribution=allowed("redistribution"), licence=identifier,
            permission_reference=licence.get("evidence_url", licence.get("url", "")),
            attribution=json.dumps(licence.get("attribution", {}), ensure_ascii=False))

    def register(self, *, source_id=None):
        preview = self.preview(source_id=source_id, _all=True)
        with self.db.transaction() as conn:
            for entry in preview["entries"]:
                if entry["source_id"] in ("L02", "L03"):
                    policy = self._literature_selection().policy({**entry["metadata"], "sha256": entry["expected_sha256"]})
                    if policy:
                        entry["eligibility"] = policy[0]
                        entry["rights"] = Rights(licence=entry["rights"]["licence"]).model_dump()
                        entry["metadata"]["notes"].append(policy[1])
                conn.execute("INSERT INTO knowledge_catalogue(id,collection_path,source_id,title,expected_sha256,bytes,reserved,eligibility,metadata_json,rights_json,checked_at) VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,expected_sha256=excluded.expected_sha256,bytes=excluded.bytes,eligibility=excluded.eligibility,metadata_json=excluded.metadata_json,rights_json=excluded.rights_json,checked_at=excluded.checked_at",
                    (entry["id"], entry["collection_path"], entry["source_id"], entry["title"], entry["expected_sha256"], entry["bytes"], int(entry["reserved"]), entry["eligibility"], json.dumps(entry["metadata"]), json.dumps(entry["rights"]), preview["checked_at"]))
        return {"catalogued": len(preview["entries"]), "errors": preview["errors"], "status": "catalogued", "indexed": False}

    def list(self, *, source_id=None, limit=250, offset=0, eligibility=None, query=""):
        """Page registered metadata without recataloguing or inspecting bodies."""
        if eligibility not in (None, "eligible", "inspection_required", "reserved", "unavailable"):
            raise ApiError("invalid_collection_filter", "Choose a supported collection eligibility filter", 422)
        if not isinstance(query, str) or len(query) > 200:
            raise ApiError("invalid_collection_filter", "Use a literal title query of at most 200 characters", 422)
        clauses, args = [], []
        if source_id:
            clauses.append("c.source_id=?")
            args.append(source_id)
        if eligibility == "unavailable":
            clauses.append("c.eligibility NOT IN ('eligible','inspection_required','reserved')")
        elif eligibility is not None:
            clauses.append("c.eligibility=?")
            args.append(eligibility)
        if query:
            # A title substring, not a LIKE pattern; keep literal whitespace too.
            term = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            clauses.append("c.title LIKE ? ESCAPE '\\'")
            args.append("%" + term + "%")
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        count = self.db.fetch_one("SELECT COUNT(*) AS n FROM knowledge_catalogue c" + where, args)["n"]
        entries = self.db.fetch_all("SELECT c.*,j.state AS processing_status,j.error_code FROM knowledge_catalogue c LEFT JOIN knowledge_jobs j ON j.id=c.job_id" + where + " ORDER BY c.source_id,c.title,c.id LIMIT ? OFFSET ?", [*args, min(limit, 1000), offset])
        for entry in entries:
            entry["metadata"] = json.loads(entry.pop("metadata_json"))
            entry["rights"] = json.loads(entry.pop("rights_json"))
            entry["processing_status"] = entry["processing_status"] or "acquired"
        return {"entries": entries, "total": count, "offset": offset}

    def import_next(self, *, source_id="L02", query="", limit=100, cursor=None, cancelled=None):
        """Adopt one bounded pending acquired page through the existing queue."""
        if source_id != "L02" or type(limit) is not int or not 1 <= limit <= 250:
            raise ApiError("invalid_collection_bulk", "Choose L02 and a page size from 1 to 250", 422)
        if not isinstance(query, str) or len(query) > 200:
            raise ApiError("invalid_collection_filter", "Use a literal title query of at most 200 characters", 422)
        fingerprint = hashlib.sha256(json.dumps([source_id, query], ensure_ascii=False).encode()).hexdigest()
        after, through = "", None
        if cursor is not None:
            try:
                if not isinstance(cursor, str) or len(cursor) > 1000:
                    raise ValueError()
                value = json.loads(base64.b64decode(cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True), object_pairs_hook=unique_object)
                if not isinstance(value, dict) or set(value) != {"after", "through", "filter"} or value["filter"] != fingerprint:
                    raise ValueError()
                after, through = value["after"], value["through"]
                if not isinstance(after, str) or (after and not re.fullmatch(r"asset_[0-9a-f]{24}", after)) or not isinstance(through, str) or not re.fullmatch(r"asset_[0-9a-f]{24}", through) or after > through:
                    raise ValueError()
            except (ValueError, TypeError, UnicodeError):
                raise ApiError("invalid_collection_cursor", "Restart bulk selection with the same source and title filter", 422) from None
        # Asset IDs remain stable when inspection changes title/eligibility.
        # Skip live jobs for the exact edition/original hash. Changed receipts
        # and retries still pass through inspection and canonical deduplication.
        joins = " FROM knowledge_catalogue c LEFT JOIN knowledge_jobs j ON j.id=c.job_id LEFT JOIN knowledge_revisions r ON r.id=j.revision_id LEFT JOIN knowledge_documents d ON d.id=r.document_id"
        choices = ["eligible", "inspection_required", *sorted(SELECTION_FAILURES)]
        clauses = ["c.source_id=?", "c.reserved=0", "c.eligibility IN (" + ",".join("?" for _ in choices) + ")",
            "EXISTS (SELECT 1 FROM json_each(c.metadata_json,'$.asset_role') WHERE value=?)",
            "(j.id IS NULL OR j.state NOT IN ('queued','processing','ready') OR d.deleted_at IS NOT NULL OR json_extract(r.metadata_json,'$.original_sha256') IS NOT c.expected_sha256 OR json_extract(r.metadata_json,'$.edition') IS NOT json_extract(c.metadata_json,'$.edition'))"]
        args = [source_id, *choices, MARKER]
        if query:
            term = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            clauses.append("c.title LIKE ? ESCAPE '\\'")
            args.append("%" + term + "%")
        where = " WHERE " + " AND ".join(clauses)
        if through is None:
            through = self.db.fetch_one("SELECT MAX(c.id) AS last" + joins + where, args)["last"] or ""
        page_where = where + " AND c.id>? AND c.id<=?"
        page_args = [*args, after, through]
        entries = self.db.fetch_all("SELECT c.id" + joins + page_where + " ORDER BY c.id LIMIT ?", [*page_args, limit])
        result = self.import_selected([entry["id"] for entry in entries], cancelled=cancelled, report_replay=True)
        results = result["results"]
        if results:
            after = results[-1]["entry_id"]
        remaining = self.db.fetch_one("SELECT COUNT(*) AS n" + joins + page_where, [*args, after, through])["n"]
        next_cursor = base64.urlsafe_b64encode(json.dumps({"after": after, "through": through, "filter": fingerprint}, separators=(",", ":")).encode()).decode().rstrip("=") if remaining else None
        accepted = {entry["job"]["id"] for entry in results if "job" in entry}
        new_jobs = {entry["job"]["id"] for entry in results if "job" in entry and not entry.get("replayed")}
        rejections = {}
        for entry in results:
            if "job" not in entry:
                rejections[entry["code"]] = rejections.get(entry["code"], 0) + 1
        return {**result, "selected": len(entries), "attempted": len(results), "accepted": len(accepted),
            "newly_queued": len(new_jobs), "replayed": sum(entry.get("replayed", False) for entry in results),
            "rejected": sum(rejections.values()), "rejections": rejections, "remaining": remaining,
            "next_cursor": next_cursor, "done": remaining == 0, "cancelled": bool(cancelled and cancelled())}

    def import_selected(self, entry_ids: list[str], *, cancelled=None, report_replay=False):
        if len(entry_ids) > 250:
            raise ApiError("batch_limit", "Select at most 250 files per import batch", 413)
        results = []
        acquired_selection = None
        recorded_receipts = None
        for entry_id in dict.fromkeys(entry_ids):
            if cancelled and cancelled():
                break
            entry = self.db.fetch_one("SELECT * FROM knowledge_catalogue WHERE id=?", (entry_id,))
            if not entry:
                results.append({"entry_id": entry_id, "status": "failed", "code": "catalogue_entry_missing"})
                continue
            metadata = json.loads(entry["metadata_json"])
            is_acquired = MARKER in metadata.get("asset_role", [])
            is_recorded = ((entry["source_id"] == "E07" and Path(entry["collection_path"]).suffix.lower() == ".png")
                or (entry["source_id"] == "L03" and "fulltext_original_PDF" in metadata.get("asset_role", [])))
            try:
                if entry["source_id"] in ("L02", "L03"):
                    self._literature_selection().require({**metadata, "sha256": entry["expected_sha256"]})
                recoverable_selection = entry["eligibility"] in SELECTION_FAILURES
                if entry["reserved"] or (entry["eligibility"] != "eligible" and not (is_acquired and entry["eligibility"] == "inspection_required") and not recoverable_selection):
                    results.append({"entry_id": entry_id, "status": "excluded", "code": entry["eligibility"]})
                    continue
                if is_acquired:
                    # One metadata pass for this deliberate batch, and only its
                    # selected JATS plus exact matching metadata are opened.
                    if acquired_selection is None:
                        candidates = []
                        for identifier in dict.fromkeys(entry_ids):
                            candidate = self.db.fetch_one("SELECT * FROM knowledge_catalogue WHERE id=?", (identifier,))
                            if candidate and not candidate["reserved"] and candidate["eligibility"] in ("eligible", "inspection_required", *SELECTION_FAILURES) and MARKER in json.loads(candidate["metadata_json"]).get("asset_role", []):
                                candidates.append(candidate)
                        try:
                            acquired_selection = AcquiredLiterature(self.root, self._literature_selection()).selections(candidates, cancelled=cancelled)
                        except (OSError, UnicodeError):
                            acquired_selection = ApiError("acquisition_manifest_unavailable", "The acquisition manifest cannot be read; refresh it before selecting articles", 409)
                        except ApiError as error:
                            acquired_selection = error
                    if isinstance(acquired_selection, ApiError):
                        raise acquired_selection
                    selected, matched = acquired_selection
                    item = selected.get(entry_id)
                    if isinstance(item, ApiError):
                        raise item
                    if not item:
                        raise ApiError("article_receipt_missing", "Refresh the catalogue; this selected receipt is no longer in the manifest", 409)
                    if item.get("sha256") != entry["expected_sha256"] or item.get("bytes") != entry["bytes"]:
                        raise ApiError("catalogue_receipt_changed", "Refresh the catalogue before selecting this changed receipt", 409)
                    self._literature_selection().require(item)
                    policy = catalogue_policy(item, project_selected=True)
                    if policy and policy[0] != "inspection_required":
                        raise ApiError(*policy, 409)
                    article = AcquiredLiterature(self.root, self._literature_selection()).inspect(item, matched.get(version_identity(item), {}))
                    if cancelled and cancelled():
                        break
                    result = self._import_acquired(entry, article)
                    if not report_replay:
                        result.pop("replayed", None)
                    results.append({"entry_id": entry_id, **result})
                    continue
                if is_recorded:
                    if recorded_receipts is None:
                        recorded_receipts = self._recorded_receipts(entry_ids)
                    result = self._import_recorded(entry, recorded_receipts.get(entry_id))
                    results.append({"entry_id": entry_id, **result})
                    continue
                previous = self.db.fetch_one("SELECT j.id,j.state,r.sha256,d.deleted_at FROM knowledge_jobs j JOIN knowledge_revisions r ON r.id=j.revision_id JOIN knowledge_documents d ON d.id=r.document_id WHERE j.id=?", (entry["job_id"],)) if entry["job_id"] else None
                if previous and not previous["deleted_at"] and previous["sha256"] == entry["expected_sha256"] and previous["state"] in ("queued", "processing", "ready"):
                    results.append({"entry_id": entry_id, **self.repository._result(previous["id"])})
                    continue
                key = "catalogue:" + entry_id + ":" + str(entry["expected_sha256"])
                replacement = entry["document_id"] if previous and not previous["deleted_at"] else None
                if previous and previous["state"] in ("failed", "cancelled"):
                    key += ":retry:" + previous["id"]
                elif previous and previous["deleted_at"]:
                    key += ":reimport:" + previous["id"]
                result = self.repository.import_file(self._path(entry["collection_path"]),
                    title=entry["title"], metadata=json.loads(entry["metadata_json"]), rights=json.loads(entry["rights_json"]),
                    scope=ContextScope(kind=Scope.LIBRARY), expected_sha256=entry["expected_sha256"],
                    idempotency_key=key, document_id=replacement, process=False)
                self.db.execute("UPDATE knowledge_catalogue SET document_id=?,job_id=? WHERE id=?", (result["document_id"], result["job"]["id"], entry_id))
                results.append({"entry_id": entry_id, **result})
            except AcquisitionCancelled:
                break
            except ApiError as error:
                if is_acquired or is_recorded or error.code in SELECTION_FAILURES:
                    metadata.setdefault("notes", []).append("Selected inspection unavailable: " + error.code + " — " + error.message)
                    self.db.execute("UPDATE knowledge_catalogue SET eligibility=?,metadata_json=?,rights_json=?,checked_at=? WHERE id=?",
                        (error.code, json.dumps(metadata), Rights().model_dump_json(), utc_now(), entry_id))
                results.append({"entry_id": entry_id, "status": "failed", "code": error.code, "message": error.message})
        return {"results": results, "queued": len({r["job"]["id"] for r in results if r["status"] == "queued"})}

    def _recorded_receipts(self, entry_ids):
        selected = {}
        try:
            with collection_path(self.root, MANIFEST).open(encoding="utf-8-sig") as stream:
                for line in stream:
                    try:
                        item = json.loads(line, object_pairs_hook=unique_object)
                        if not isinstance(item, dict) or not recorded_file(item):
                            continue
                        path = collection_path(self.root, item.get("local_path") or item.get("path"), must_exist=False)
                        identifier = asset_id(item["source_id"], path.relative_to(self.root).as_posix())
                        if identifier in entry_ids:
                            if identifier in selected and selected[identifier] != item:
                                raise ApiError("article_receipt_ambiguous", "Conflicting selected file receipts require review", 409)
                            selected[identifier] = item
                    except (ValueError, KeyError, TypeError):
                        continue
        except (OSError, UnicodeError):
            raise ApiError("acquisition_manifest_unavailable", "The acquisition manifest cannot be read", 409) from None
        return selected

    def _import_recorded(self, entry, item):
        if not item:
            raise ApiError("article_receipt_missing", "Refresh the catalogue; this selected receipt is no longer in the manifest", 409)
        if item.get("sha256") != entry["expected_sha256"] or item.get("bytes") != entry["bytes"]:
            raise ApiError("catalogue_receipt_changed", "Refresh the catalogue before importing a changed file receipt", 409)
        selection_proof = None
        metadata = json.loads(entry["metadata_json"])
        def guard():
            nonlocal selection_proof
            if item["source_id"] == "L03":
                proof = self._literature_selection().require(item)
                if selection_proof is not None and proof != selection_proof:
                    raise ApiError("literature_selection_changed", "The batch selection evidence changed during file import; select again", 409)
                selection_proof = proof
            policy = catalogue_policy(item, project_selected=item["source_id"] == "L03")
            if policy:
                raise ApiError(*policy, 409)
            effective = self.repository.source_status.effective(SourceMetadata.model_validate(metadata))
            if any((effective.retracted, effective.superseded, effective.repository_removed, effective.access_changed)):
                raise ApiError("article_status_unavailable", "A recorded source-status restriction overrides this file receipt", 409)
            rights = self._rights(item)
            if not all((rights.display, rights.cache, rights.index, rights.embedding)):
                raise ApiError("source_permission_required", "The current receipt does not grant the required file operations", 403)
            return rights
        rights = guard()
        metadata["notes"] = [note for note in metadata.get("notes", []) if not note.startswith(("renulus-collection-v1:", "renulus-selection-v1:"))]
        metadata["notes"].append("renulus-collection-v1:" + json.dumps({key: item.get(key) for key in
            ("licence", "processing_scope", "acquisition_provenance", "frozen_selection_state", "frozen_selection_exclusion")}, ensure_ascii=False))
        if item["source_id"] == "L03":
            metadata["notes"].append("renulus-selection-v1:" + json.dumps(self._literature_selection().observation(item), ensure_ascii=False))
        # Replays also pass current selection and permission guards.
        with self.repository._lock:
            previous = self.db.fetch_one("SELECT j.id,j.state,r.sha256,d.deleted_at FROM knowledge_jobs j JOIN knowledge_revisions r ON r.id=j.revision_id JOIN knowledge_documents d ON d.id=r.document_id WHERE j.id=?", (entry["job_id"],)) if entry["job_id"] else None
            if previous and not previous["deleted_at"] and previous["sha256"] == entry["expected_sha256"] and previous["state"] in ("queued", "processing", "ready"):
                guard()
                return self.repository._result(previous["id"])
        path = self._path(entry["collection_path"])
        if path.suffix.lower() != (".png" if item["source_id"] == "E07" else ".pdf"):
            raise ApiError("unsupported_file", "Choose the recorded E07 PNG or L03 PDF original", 415)
        if path.stat().st_size > 64 * 1024 * 1024:
            raise ApiError("document_limit", "The supported selected file must be at most 64 MiB", 413)
        guard()
        with path.open("rb") as stream:
            data = stream.read(64 * 1024 * 1024 + 1)
        if hashlib.sha256(data).hexdigest() != entry["expected_sha256"]:
            raise ApiError("source_hash_changed", "The selected file differs from its acquisition receipt", 409)
        if path.suffix.lower() == ".pdf" and not data.lstrip().startswith(b"%PDF-"):
            raise ApiError("malformed_pdf", "The selected file has no PDF signature", 422)
        key = "catalogue:" + entry["id"] + ":" + entry["expected_sha256"]
        replacement = entry["document_id"] if previous and not previous["deleted_at"] else None
        if previous:
            key += (":reimport:" if previous["deleted_at"] else ":retry:") + previous["id"]
        with self.repository._lock:
            rights = guard()
            result = self.repository._import(data, path.suffix.lower(), entry["title"], metadata, rights,
                ContextScope(kind=Scope.LIBRARY), key, replacement, False, False)
            self.db.execute("UPDATE knowledge_catalogue SET document_id=?,job_id=? WHERE id=?", (result["document_id"], result["job"]["id"], entry["id"]))
        return result

    def _import_acquired(self, entry, article):
        # Serialize canonical version adoption with journal updates and recovery.
        # import_text(process=False) uses normal import guards; CPU extraction
        # remains serial in the worker and must not block this enqueue path.
        with self.repository._lock:
            def guard_selection():
                proof = self._literature_selection().require(article.metadata.model_dump())
                if proof != article.evidence.get("selection_fingerprint"):
                    raise ApiError("literature_selection_changed", "The batch selection evidence changed after inspection; inspect again before adoption or replay", 409)
            guard_selection()
            effective = self.repository.source_status.effective(article.metadata)
            if any((effective.retracted, effective.superseded, effective.repository_removed, effective.access_changed)):
                raise ApiError("article_status_unavailable", "A recorded source-status restriction overrides the acquired receipt", 409)
            # The parent journal binds positive/clearing reviews to this exact
            # edition and verified original hash; import_text replays that state.
            base = article.key
            version_prefix = "acquired:L02:" + article.metadata.edition + ":"
            previous = self.db.fetch_one("SELECT j.id,j.state,j.idempotency_key,r.sha256,r.document_id,d.deleted_at FROM knowledge_jobs j JOIN knowledge_revisions r ON r.id=j.revision_id JOIN knowledge_documents d ON d.id=r.document_id WHERE j.idempotency_key>=? AND j.idempotency_key<? ORDER BY (d.deleted_at IS NOT NULL),j.created_at DESC,r.ordinal DESC,j.id DESC LIMIT 1", (version_prefix, version_prefix + "\uffff"))
            same_proof = previous and (previous["idempotency_key"] == base or previous["idempotency_key"].startswith(base + ":"))
            if same_proof and not previous["deleted_at"] and previous["sha256"] == article.evidence["derivative_sha256"] and previous["state"] in ("queued", "processing", "ready"):
                guard_selection()
                result = {**self.repository._result(previous["id"]), "replayed": True}
            else:
                key, replacement = base, None
                if previous:
                    if previous["deleted_at"]:
                        key += ":reimport:" + previous["id"]
                    else:
                        replacement = previous["document_id"]
                        key += ":retry:" + previous["id"]
                guard_selection()
                result = self.repository.import_text(article.text, title=article.title,
                    metadata=article.metadata, rights=article.rights, scope=ContextScope(kind=Scope.LIBRARY),
                    idempotency_key=key, document_id=replacement, process=False)
                result["replayed"] = False
            self.db.execute("UPDATE knowledge_catalogue SET title=?,eligibility='eligible',metadata_json=?,rights_json=?,document_id=?,job_id=?,checked_at=? WHERE id=?",
                (article.title, article.metadata.model_dump_json(), article.rights.model_dump_json(),
                 result["document_id"], result["job"]["id"], utc_now(), entry["id"]))
            return result
