"""SQLite authority with staged, cancellable derived revisions."""
from datetime import datetime, timezone
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import re
import shutil
from threading import RLock

from ..contracts import ApiError, ContextScope, Scope, durable_id
from ..storage.database import utc_now
from .engines import DoclingExtractor, FastEmbedEngine, LanceIndex, MAX_BYTES, OfflineAssets
from .models import Rights, SourceMetadata, own_text_rights
from .source_status import SourceStatusJournal

TERMINAL = {"ready", "failed", "cancelled"}
MEDIA = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg",
         ".jpeg": "image/jpeg", ".tif": "image/tiff", ".tiff": "image/tiff",
         ".txt": "text/plain", ".md": "text/markdown"}


def dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class KnowledgeRepository:
    def __init__(self, services, *, extractor=None, embedder=None, index=None):
        self.services, self.db, self.paths = services, services.db, services.paths
        self.assets = OfflineAssets(services)
        self.extractor = extractor or DoclingExtractor(self.assets)
        self.embedder = embedder or FastEmbedEngine(self.assets)
        self.index = index or LanceIndex(self._selected_index_path())
        self._lock = RLock()
        self._ingest_lock = RLock()
        self.source_status = SourceStatusJournal(self)

    def update_source_status(self, event):
        return self.source_status.update(event)

    @contextmanager
    def recovery_guard(self):
        if not self._ingest_lock.acquire(timeout=90):
            raise ApiError("recovery_busy", "The library is finishing an import. Retry backup or restore after this file completes", 409, True)
        try:
            with self._lock:
                yield
        finally:
            self._ingest_lock.release()

    def _selected_index_path(self):
        row = self.db.fetch_one("SELECT value FROM preferences WHERE key='knowledge.index_generation'")
        if row is None:
            return self.paths.indexes / "knowledge"
        try:
            generation = json.loads(row["value"])
        except (TypeError, ValueError):
            generation = None
        if not isinstance(generation, str) or not re.fullmatch(r"index_[0-9a-f]{32}", generation):
            raise ApiError("invalid_index_generation", "The library index selector needs recovery", 503, True)
        return self.paths.indexes / "knowledge-generations" / generation

    def _remove_index_folder(self, path):
        path = Path(path)
        if not path.exists():
            return
        if path.is_symlink() or not path.resolve().is_relative_to(self.paths.indexes.resolve()):
            raise ApiError("unsafe_index_path", "Derived index cleanup left its owned folder", 409)
        shutil.rmtree(path)

    def _cleanup_index_generations(self):
        active = self.index.path.resolve()
        candidates = [self.paths.indexes / "knowledge"]
        generations = self.paths.indexes / "knowledge-generations"
        if generations.is_dir():
            candidates += [path for path in generations.iterdir()
                           if re.fullmatch(r"index_[0-9a-f]{32}", path.name)]
        pending = []
        for path in candidates:
            if path.resolve() != active:
                try:
                    self._remove_index_folder(path)
                except Exception:
                    pending.append(path.name)
        return pending

    def rebuild_index(self):
        """Stage canonical eligible passages, validate, then atomically select them."""
        with self._ingest_lock, self._lock:
            # A restore can bring an older active row beside a newer tombstone.
            deleted = self.db.fetch_all("SELECT d.id FROM knowledge_documents d JOIN deletion_ledger l ON l.entity_id=d.id AND l.entity_type='knowledge-document' WHERE d.deleted_at IS NULL")
            for row in deleted:
                self.delete_document(row["id"])
            if self.cleanup():
                raise ApiError("knowledge_cleanup_pending", "Finish deleted-document cleanup before rebuilding the library", 503, True)
            generation = durable_id("index")
            candidate = LanceIndex(self.paths.indexes / "knowledge-generations" / generation, self.embedder.dimensions)
            previous = self.index
            activated = False
            try:
                revisions = self.db.fetch_all("SELECT r.*,d.title FROM knowledge_revisions r JOIN knowledge_documents d ON d.active_revision=r.id WHERE d.deleted_at IS NULL AND d.reserved=0 AND d.scope_kind='personal-library' AND r.status='ready'")
                identities = set()
                for revision in revisions:
                    if not self._eligible(json.loads(revision["metadata_json"]), json.loads(revision["rights_json"]), None, False):
                        continue
                    passages = self.db.fetch_all("SELECT id,context_text FROM knowledge_passages WHERE revision_id=? ORDER BY ordinal", (revision["id"],))
                    for offset in range(0, len(passages), 64):
                        batch = passages[offset:offset + 64]
                        vectors = self.embedder.embed([row["context_text"] for row in batch])
                        rows = [{"passage_id": row["id"], "revision_id": revision["id"],
                                 "document_id": revision["document_id"], "text": row["context_text"], "vector": vector}
                                for row, vector in zip(batch, vectors, strict=True)]
                        candidate.stage(rows, create_fts=False)
                        identities.update((row["passage_id"], row["revision_id"], row["document_id"]) for row in rows)
                candidate.build_fts()
                candidate.validate_passages(identities)
                with self.db.transaction() as conn:
                    conn.execute("INSERT INTO preferences VALUES('knowledge.index_generation',?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at", (json.dumps(generation), utc_now()))
                self.index = candidate
                activated = True
                previous.close()
                pending = self._cleanup_index_generations()
                return {"status": "ready", "passages": len(identities), "generation": generation,
                        "cleanup_pending": bool(pending)}
            except Exception:
                if not activated:
                    candidate.close()
                    try:
                        self._remove_index_folder(candidate.path)
                    except Exception:
                        pass  # Startup cleanup retries abandoned staging folders.
                raise

    def capabilities(self):
        return self.assets.capabilities()

    def extract_bytes(self, data: bytes, filename: str, title: str):
        if self.capabilities()["temporary_extraction"] is not True:
            raise ApiError("temporary_extraction_unavailable", "The verified temporary extraction path is not available", 503, True)
        return self.extractor.extract_bytes(data, filename, title)

    @staticmethod
    def _scope(scope) -> ContextScope:
        if not isinstance(scope, ContextScope):
            scope = ContextScope.model_validate(scope)
        return scope

    def _import_scope(self, scope):
        scope = self._scope(scope)
        if scope.kind != Scope.LIBRARY:
            raise ApiError("unsafe_import_scope",
                "Library import requires deliberate personal-library scope. Temporary attachments must stay in their case session", 409)
        return scope

    def import_text(self, text: str, *, title="Personal study note", metadata=None, rights=None,
                    scope=None, idempotency_key=None, document_id=None, reserved=False, process=True):
        scope = self._import_scope(scope or ContextScope(kind=Scope.LIBRARY))
        if not text.strip():
            raise ApiError("empty_document", "Add some text before importing", 422)
        data = text.encode("utf-8")
        return self._import(data, ".txt", title, metadata, rights or own_text_rights(), scope,
                            idempotency_key, document_id, reserved, process)

    def import_file(self, path: str | Path, *, title=None, metadata=None, rights=None, scope=None,
                    idempotency_key=None, document_id=None, reserved=False, expected_sha256=None, process=True):
        scope = self._import_scope(scope or ContextScope(kind=Scope.LIBRARY))
        path = Path(path).resolve()
        if not path.is_file():
            raise ApiError("file_missing", "The selected file is no longer available", 404, True)
        suffix = path.suffix.lower()
        if suffix not in MEDIA:
            raise ApiError("unsupported_file", "Choose a PDF, image or UTF-8 text file", 415)
        if path.stat().st_size > MAX_BYTES:
            raise ApiError("document_limit", "The maximum file size is 64 MiB", 413)
        # Bounded read from the explicit selection only; never discover siblings.
        with path.open("rb") as source:
            data = source.read(MAX_BYTES + 1)
        if expected_sha256 and hashlib.sha256(data).hexdigest() != expected_sha256:
            raise ApiError("source_hash_changed", "The selected file differs from its acquisition record", 409)
        if suffix == ".pdf" and not data.lstrip().startswith(b"%PDF-"):
            raise ApiError("malformed_pdf", "The selected file does not have a PDF signature", 422)
        return self._import(data, suffix, title or path.stem, metadata, rights or Rights(), scope,
                            idempotency_key, document_id, reserved, process)

    def _import(self, data, suffix, title, metadata, rights, scope, key, document_id, reserved, process):
        if len(data) > MAX_BYTES:
            raise ApiError("document_limit", "The maximum file size is 64 MiB", 413)
        metadata = metadata if isinstance(metadata, SourceMetadata) else SourceMetadata.model_validate(metadata or {})
        rights = rights if isinstance(rights, Rights) else Rights.model_validate(rights)
        if metadata.source_id == "E02":
            reserved = True
        if not rights.cache or not rights.display or (not reserved and (not rights.index or not rights.embedding)):
            raise ApiError("source_permission_required", "Confirm display, local caching, indexing and embedding permission for this source", 403)
        digest = hashlib.sha256(data).hexdigest()
        request_metadata = metadata.model_dump()
        if request_metadata.get("original_sha256") is None:
            # The additive provenance field must not change a pre-field replay.
            request_metadata.pop("original_sha256", None)
        request_hash = hashlib.sha256(dumps([digest, title, request_metadata, rights.model_dump(),
                                             scope.model_dump(), document_id, reserved]).encode()).hexdigest()
        key = key or durable_id("import")
        with self._lock:
            old_job = self.db.fetch_one("SELECT * FROM knowledge_jobs WHERE idempotency_key=?", (key,))
            if old_job:
                if old_job["request_hash"] != request_hash:
                    raise ApiError("idempotency_conflict", "That import key belongs to a different request", 409)
                return self._result(old_job["id"])
            # Replay reviewed source state for a later import while keeping its
            # idempotency hash tied to the caller's original import request.
            metadata = self.source_status.effective(metadata)
            now = utc_now()
            revision_id, job_id = durable_id("rev"), durable_id("ingest")
            existing = self.get_document(document_id) if document_id else None
            if existing and (existing["scope"] != scope.model_dump() or existing["source_id"] != metadata.source_id):
                raise ApiError("replacement_scope_changed", "A replacement must retain its source and library scope", 409)
            document_id = document_id or durable_id("doc")
            folder = self._folder(document_id, revision_id)
            folder.mkdir(parents=True, exist_ok=False)
            original = folder / ("original" + suffix)
            try:
                original.write_bytes(data)
                with self.db.transaction() as conn:
                    if existing:
                        row = conn.execute("SELECT * FROM knowledge_documents WHERE id=? AND deleted_at IS NULL", (document_id,)).fetchone()
                        if row is None:
                            raise ApiError("document_deleted", "The document was deleted", 409)
                        ordinal = conn.execute("SELECT COALESCE(MAX(ordinal),0)+1 FROM knowledge_revisions WHERE document_id=?", (document_id,)).fetchone()[0]
                        pending = conn.execute("SELECT j.id,j.revision_id FROM knowledge_jobs j JOIN knowledge_revisions r ON r.id=j.revision_id WHERE r.document_id=? AND j.state IN ('queued','processing')", (document_id,)).fetchall()
                        for item in pending:
                            self._cancel_in(conn, item["id"], item["revision_id"], "replaced")
                        conn.execute("UPDATE knowledge_documents SET title=?,latest_revision=?,reserved=?,updated_at=? WHERE id=?", (title, revision_id, int(reserved), now, document_id))
                    else:
                        ordinal = 1
                        conn.execute("INSERT INTO knowledge_documents(id,title,source_id,scope_kind,scope_entity,reserved,latest_revision,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)", (document_id, title, metadata.source_id, scope.kind.value, scope.entity_id, int(reserved), revision_id, now, now))
                    conn.execute("INSERT INTO knowledge_revisions(id,document_id,ordinal,status,sha256,media_type,bytes,original_path,metadata_json,rights_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (revision_id, document_id, ordinal, "queued", digest, MEDIA[suffix], len(data), str(original), metadata.model_dump_json(), rights.model_dump_json(), now))
                    conn.execute("INSERT INTO knowledge_jobs(id,revision_id,idempotency_key,request_hash,state,phase,created_at) VALUES(?,?,?,?,?,?,?)", (job_id, revision_id, key, request_hash, "queued", "queued", now))
            except BaseException:
                shutil.rmtree(folder)
                raise
        if process:
            self.run_job(job_id)
        return self._result(job_id)

    def _folder(self, document_id, revision_id):
        folder = (self.paths.library / "knowledge" / document_id / revision_id).resolve()
        if not folder.is_relative_to((self.paths.library / "knowledge").resolve()):
            raise ApiError("unsafe_document_path", "Document path is outside its library", 409)
        return folder

    def get_job(self, job_id):
        row = self.db.fetch_one("SELECT * FROM knowledge_jobs WHERE id=?", (job_id,))
        if not row:
            raise ApiError("job_missing", "Import job was not found", 404)
        return row

    def _result(self, job_id):
        job = self.get_job(job_id)
        revision = self.db.fetch_one("SELECT document_id FROM knowledge_revisions WHERE id=?", (job["revision_id"],))
        return {"document_id": revision["document_id"], "revision_id": job["revision_id"],
                "status": job["state"], "job": job}

    def _guard(self, conn, job_id):
        row = conn.execute("SELECT j.state,r.id,r.document_id,d.latest_revision,d.deleted_at FROM knowledge_jobs j JOIN knowledge_revisions r ON r.id=j.revision_id JOIN knowledge_documents d ON d.id=r.document_id WHERE j.id=?", (job_id,)).fetchone()
        return row and row["state"] == "processing" and row["deleted_at"] is None and row["latest_revision"] == row["id"]

    def _phase(self, job_id, phase):
        with self._lock, self.db.transaction() as conn:
            if not self._guard(conn, job_id):
                return False
            conn.execute("UPDATE knowledge_jobs SET phase=? WHERE id=?", (phase, job_id))
            return True

    def run_job(self, job_id):
        # Keep CPU conversion/model state serial while allowing cancellation,
        # replacement and deletion to change canonical state during extraction.
        with self._ingest_lock:
            return self._run_job(job_id)

    def _run_job(self, job_id):
        with self._lock, self.db.transaction() as conn:
            job = conn.execute("SELECT * FROM knowledge_jobs WHERE id=?", (job_id,)).fetchone()
            if not job:
                raise ApiError("job_missing", "Import job was not found", 404)
            if job["state"] != "queued":
                return dict(job)
            revision = dict(conn.execute("SELECT * FROM knowledge_revisions WHERE id=?", (job["revision_id"],)).fetchone())
            document = dict(conn.execute("SELECT * FROM knowledge_documents WHERE id=?", (revision["document_id"],)).fetchone())
            conn.execute("UPDATE knowledge_jobs SET state='processing',phase='extraction' WHERE id=?", (job_id,))
            conn.execute("UPDATE knowledge_revisions SET status='processing' WHERE id=?", (revision["id"],))
        try:
            extracted = self.extractor.extract_file(Path(revision["original_path"]), document["title"])
            if not self._phase(job_id, "embedding"):
                self.cleanup()
                return self.get_job(job_id)
            passages = extracted.passages
            for item in passages:
                item["id"] = durable_id("passage")
            vectors = [] if document["reserved"] else self.embedder.embed([p["context_text"] for p in passages])
            with self._lock:
                with self.db.transaction() as conn:
                    if not self._guard(conn, job_id):
                        return self.get_job(job_id)
                if not document["reserved"]:
                    self.index.stage([{"passage_id": p["id"], "revision_id": revision["id"],
                        "document_id": document["id"], "text": p["context_text"], "vector": v}
                        for p, v in zip(passages, vectors, strict=True)])
                with self.db.transaction() as conn:
                    if not self._guard(conn, job_id):
                        self._schedule_cleanup(conn, revision["id"], True)
                    else:
                        previous = conn.execute("SELECT active_revision FROM knowledge_documents WHERE id=?", (document["id"],)).fetchone()[0]
                        for i, p in enumerate(passages):
                            conn.execute("INSERT INTO knowledge_passages VALUES(?,?,?,?,?,?,?)", (p["id"], revision["id"], i, p["text"], p["context_text"], dumps(p["locators"]), dumps(p["headings"])))
                        now = utc_now()
                        conn.execute("UPDATE knowledge_revisions SET status='ready',extraction_json=?,embedding_model=?,chunk_tokens=?,activated_at=? WHERE id=?", (dumps(extracted.document), self.embedder.model_id, self.embedder.max_tokens, now, revision["id"]))
                        conn.execute("UPDATE knowledge_documents SET active_revision=?,updated_at=? WHERE id=?", (revision["id"], now, document["id"]))
                        conn.execute("UPDATE knowledge_jobs SET state='ready',phase='complete',finished_at=? WHERE id=?", (now, job_id))
                        if previous and previous != revision["id"]:
                            self._schedule_cleanup(conn, previous, False)
        except Exception as error:
            code = error.code if isinstance(error, ApiError) else "ingestion_failed"
            message = error.message if isinstance(error, ApiError) else "Document ingestion failed; check offline helpers and file integrity"
            with self._lock, self.db.transaction() as conn:
                if self._guard(conn, job_id):
                    conn.execute("UPDATE knowledge_jobs SET state='failed',phase='failed',error_code=?,error_message=?,finished_at=? WHERE id=?", (code, message, utc_now(), job_id))
                    conn.execute("UPDATE knowledge_revisions SET status='failed' WHERE id=?", (revision["id"],))
                    self._schedule_cleanup(conn, revision["id"], True)
        self.cleanup()
        return self.get_job(job_id)

    def _schedule_cleanup(self, conn, revision_id, remove_original):
        conn.execute("INSERT INTO knowledge_cleanup(revision_id,remove_original,created_at) VALUES(?,?,?) ON CONFLICT(revision_id) DO UPDATE SET remove_original=MAX(remove_original,excluded.remove_original)", (revision_id, int(remove_original), utc_now()))

    def _cancel_in(self, conn, job_id, revision_id, reason):
        conn.execute("UPDATE knowledge_jobs SET state='cancelled',phase=?,finished_at=? WHERE id=? AND state IN ('queued','processing')", (reason, utc_now(), job_id))
        conn.execute("UPDATE knowledge_revisions SET status='cancelled' WHERE id=? AND status IN ('queued','processing')", (revision_id,))
        self._schedule_cleanup(conn, revision_id, True)

    def cancel_job(self, job_id):
        with self._lock, self.db.transaction() as conn:
            job = conn.execute("SELECT * FROM knowledge_jobs WHERE id=?", (job_id,)).fetchone()
            if not job:
                raise ApiError("job_missing", "Import job was not found", 404)
            if job["state"] not in TERMINAL:
                self._cancel_in(conn, job_id, job["revision_id"], "cancelled")
        self.cleanup()
        return self.get_job(job_id)

    def cleanup(self):
        with self._lock:
            for task in self.db.fetch_all("SELECT c.*,r.document_id FROM knowledge_cleanup c JOIN knowledge_revisions r ON r.id=c.revision_id"):
                try:
                    self.index.remove(task["revision_id"])
                    if task["remove_original"]:
                        folder = self._folder(task["document_id"], task["revision_id"])
                        if folder.exists():
                            shutil.rmtree(folder)
                        self.db.execute("UPDATE knowledge_revisions SET original_path=NULL,extraction_json=NULL WHERE id=?", (task["revision_id"],))
                    self.db.execute("DELETE FROM knowledge_cleanup WHERE revision_id=?", (task["revision_id"],))
                except Exception:
                    self.db.execute("UPDATE knowledge_cleanup SET error_code='cleanup_pending' WHERE revision_id=?", (task["revision_id"],))
            pending = self.db.fetch_all("SELECT revision_id,error_code FROM knowledge_cleanup")
            pending += [{"generation": name, "error_code": "index_cleanup_pending"}
                        for name in self._cleanup_index_generations()]
            return pending

    def recover(self):
        """Resume durable jobs, discard partial index rows and retain stored originals."""
        with self._lock, self.db.transaction() as conn:
            jobs = conn.execute("SELECT j.id,j.revision_id,j.state,r.original_path,d.latest_revision,d.deleted_at,d.scope_kind FROM knowledge_jobs j JOIN knowledge_revisions r ON r.id=j.revision_id JOIN knowledge_documents d ON d.id=r.document_id WHERE j.state IN ('queued','processing')").fetchall()
            for job in jobs:
                if job["deleted_at"] or job["latest_revision"] != job["revision_id"] or job["scope_kind"] != Scope.LIBRARY.value:
                    self._cancel_in(conn, job["id"], job["revision_id"], "obsolete")
                elif not job["original_path"] or not Path(job["original_path"]).is_file():
                    conn.execute("UPDATE knowledge_jobs SET state='failed',phase='failed',error_code='original_missing',error_message='Stored input is missing; import the original again',finished_at=? WHERE id=?", (utc_now(), job["id"]))
                    conn.execute("UPDATE knowledge_revisions SET status='failed' WHERE id=?", (job["revision_id"],))
                    self._schedule_cleanup(conn, job["revision_id"], True)
                elif job["state"] == "processing":
                    conn.execute("UPDATE knowledge_jobs SET state='queued',phase='resuming',error_code=NULL,error_message=NULL,finished_at=NULL WHERE id=?", (job["id"],))
                    conn.execute("UPDATE knowledge_revisions SET status='queued',extraction_json=NULL WHERE id=?", (job["revision_id"],))
                    conn.execute("DELETE FROM knowledge_passages WHERE revision_id=?", (job["revision_id"],))
                    self._schedule_cleanup(conn, job["revision_id"], False)
        return self.cleanup()

    def next_queued_job(self):
        # Work is durable in SQLite, not held in a request or an in-memory list.
        return self.db.fetch_one("SELECT id FROM knowledge_jobs WHERE state='queued' ORDER BY created_at,id LIMIT 1")

    def list_documents(self, *, include_deleted=False, limit=None, offset=0, query="", status=None):
        if limit is not None and (type(limit) is not int or not 1 <= limit <= 100):
            raise ApiError("invalid_library_page", "Choose between 1 and 100 documents per page", 422)
        if type(offset) is not int or offset < 0 or not isinstance(query, str) or len(query) > 200:
            raise ApiError("invalid_library_page", "Check the library search and page offset", 422)
        if status not in (None, "ready", "queued", "processing", "failed", "cancelled", "empty", "deleted"):
            raise ApiError("invalid_library_status", "Choose a supported import status", 422)
        state = "CASE WHEN d.deleted_at IS NOT NULL THEN 'deleted' ELSE COALESCE(r.status,'empty') END"
        source = " FROM knowledge_documents d LEFT JOIN knowledge_revisions r ON r.id=d.latest_revision"
        base = [] if include_deleted else ["d.deleted_at IS NULL"]
        filtered, parameters = list(base), []
        if query.strip():
            # Search title/source literally: user percent/underscore characters
            # must not broaden a query into a wildcard match.
            term = query.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            filtered.append("(d.title LIKE ? ESCAPE '\\' OR d.source_id LIKE ? ESCAPE '\\')")
            parameters.extend(["%" + term + "%"] * 2)
        if status is not None:
            filtered.append(state + "=?")
            parameters.append(status)
        where = " WHERE " + " AND ".join(filtered) if filtered else ""
        count_where = " WHERE " + " AND ".join(base) if base else ""
        with self._lock:
            counts = {row["status"]: row["n"] for row in self.db.fetch_all(
                "SELECT " + state + " AS status,COUNT(*) AS n" + source + count_where + " GROUP BY " + state)}
            total = self.db.fetch_one("SELECT COUNT(*) AS n" + source + where, tuple(parameters))["n"]
            paging = " LIMIT ? OFFSET ?" if limit is not None else " LIMIT -1 OFFSET ?"
            page_parameters = parameters + ([limit, offset] if limit is not None else [offset])
            rows = self.db.fetch_all("SELECT d.id" + source + where +
                                    " ORDER BY d.updated_at DESC,d.id" + paging, tuple(page_parameters))
            return {"documents": [self.get_document(row["id"], include_deleted=include_deleted) for row in rows],
                    "total": total, "counts": counts, "offset": offset, "limit": limit}

    def get_document(self, document_id, *, include_deleted=False):
        row = self.db.fetch_one("SELECT * FROM knowledge_documents WHERE id=?", (document_id,))
        if row is None or (row["deleted_at"] and not include_deleted):
            raise ApiError("document_missing", "Document was not found", 404)
        row["scope"] = {"kind": row.pop("scope_kind"), "entity_id": row.pop("scope_entity")}
        row["reserved"] = bool(row["reserved"])
        row["revisions"] = []
        for revision in self.db.fetch_all("SELECT * FROM knowledge_revisions WHERE document_id=? ORDER BY ordinal DESC", (document_id,)):
            revision["metadata"] = json.loads(revision.pop("metadata_json"))
            revision["rights"] = json.loads(revision.pop("rights_json"))
            revision.pop("extraction_json")
            revision.pop("original_path")
            revision["passage_count"] = self.db.fetch_one("SELECT COUNT(*) AS n FROM knowledge_passages WHERE revision_id=?", (revision["id"],))["n"]
            row["revisions"].append(revision)
        row["status"] = "deleted" if row["deleted_at"] else (row["revisions"][0]["status"] if row["revisions"] else "empty")
        row["cleanup_pending"] = bool(self.db.fetch_one("SELECT 1 FROM knowledge_cleanup c JOIN knowledge_revisions r ON r.id=c.revision_id WHERE r.document_id=?", (document_id,)))
        return row

    def _eligible(self, metadata, rights, topic_id, current_only):
        if not rights.get("model_input") or not rights.get("index") or not rights.get("embedding"):
            return False
        if metadata.get("retracted") or metadata.get("superseded") or metadata.get("access_changed"):
            return False
        if metadata.get("publication_status") in ("draft", "preprint"):
            return False
        if topic_id and (topic_id in metadata.get("replaced_topics", []) or (metadata.get("topic_ids") and topic_id not in metadata["topic_ids"])):
            return False
        # Replaced guidance also occurs in summaries/tables outside chapter
        # boundaries. Until reviewed passage-level replacement masks exist,
        # suppress the affected source rather than leak a mixed-topic chunk.
        if metadata.get("replaced_topics"):
            return False
        if current_only:
            if metadata.get("publication_status") != "final" or not metadata.get("latest_final_verified") or not metadata.get("content_reviewed") or metadata.get("repository_removed"):
                return False
            due = metadata.get("review_due")
            if due and due[:10] < datetime.now(timezone.utc).date().isoformat():
                return False
        return True

    def retrieve(self, query, topic_id=None, scope=None, *, limit=8, current_only=False):
        if scope is None:
            raise ApiError("scope_required", "Retrieval requires an app-owned context scope", 422)
        scope = self._scope(scope)
        if scope.kind in (Scope.UNCLASSIFIED, Scope.REVIEWED_ASSESSMENT):
            raise ApiError("retrieval_scope_denied", "This scope does not permit library retrieval", 403)
        if not query.strip():
            return {"passages": [], "status": "empty_query"}
        if len(query) > 16000:
            raise ApiError("query_limit", "The retrieval query is too long", 413)
        limit = max(1, min(int(limit), 50))
        with self._lock:
            rows = self.db.fetch_all("SELECT r.*,d.title,d.source_id FROM knowledge_revisions r JOIN knowledge_documents d ON d.active_revision=r.id WHERE d.deleted_at IS NULL AND d.reserved=0 AND r.status='ready' AND d.scope_kind='personal-library' AND (d.scope_entity IS NULL OR d.scope_entity=?)", (scope.entity_id,))
            eligible = {r["id"]: r for r in rows if self._eligible(json.loads(r["metadata_json"]), json.loads(r["rights_json"]), topic_id, current_only)}
            if not eligible:
                return {"passages": [], "status": "no_eligible_documents", "current_only": current_only}
            vector = self.embedder.embed([query], query=True)[0]
            matches = self.index.search(query, vector, list(eligible), limit * 3)
            passages = []
            for hit in matches:
                revision = eligible.get(hit["revision_id"])
                if revision is None:
                    continue
                passage = self.db.fetch_one("SELECT * FROM knowledge_passages WHERE id=? AND revision_id=?", (hit["passage_id"], revision["id"]))
                if not passage:
                    continue
                locators = json.loads(passage["locators_json"])
                metadata = json.loads(revision["metadata_json"])
                excluded = set(metadata.get("excluded_pages", []))
                if any(p.get("page") in excluded for p in locators):
                    continue
                passages.append({"id": passage["id"], "text": passage["text"],
                    "context_text": passage["context_text"], "document_id": revision["document_id"],
                    "document_revision": revision["id"], "title": revision["title"],
                    "source_id": revision["source_id"], "locators": locators,
                    "headings": json.loads(passage["headings_json"]), "metadata": metadata,
                    "rights": json.loads(revision["rights_json"]), "score": hit.get("_relevance_score"),
                    "original_url": f"/api/v1/library/revisions/{revision['id']}/original"})
                if len(passages) >= limit:
                    break
            return {"passages": passages, "status": "ready", "current_only": current_only}

    def citation(self, document_revision, page=None):
        revision = self.db.fetch_one("SELECT r.*,d.title,d.source_id,d.deleted_at FROM knowledge_revisions r JOIN knowledge_documents d ON d.id=r.document_id WHERE r.id=?", (document_revision,))
        if not revision or revision["deleted_at"] or revision["status"] != "ready":
            raise ApiError("citation_missing", "The cited document revision is unavailable", 404)
        locators = [locator for row in self.db.fetch_all("SELECT locators_json FROM knowledge_passages WHERE revision_id=?", (document_revision,)) for locator in json.loads(row["locators_json"]) if page is None or locator.get("page") == page]
        if page is not None and not locators:
            raise ApiError("page_missing", "That page has no extracted citation location", 404)
        return {"document_id": revision["document_id"], "document_revision": document_revision,
                "title": revision["title"], "source_id": revision["source_id"], "page": page,
                "locators": locators, "metadata": json.loads(revision["metadata_json"]),
                "original_url": f"/api/v1/library/revisions/{document_revision}/original",
                "viewer_url": f"/library/{revision['document_id']}?revision={document_revision}" + (f"&page={page}" if page else "")}

    def original(self, revision_id):
        row = self.db.fetch_one("SELECT r.*,d.deleted_at FROM knowledge_revisions r JOIN knowledge_documents d ON d.id=r.document_id WHERE r.id=?", (revision_id,))
        if not row or row["deleted_at"] or row["status"] != "ready" or not row["original_path"]:
            raise ApiError("original_missing", "The original is no longer available", 404)
        if not json.loads(row["rights_json"])["display"]:
            raise ApiError("display_denied", "Display permission is unavailable", 403)
        path = Path(row["original_path"]).resolve()
        if not path.is_relative_to(self._folder(row["document_id"], revision_id)) or not path.is_file():
            raise ApiError("original_missing", "The stored original is unavailable", 404)
        return path, row["media_type"]

    def delete_document(self, document_id):
        with self._lock, self.db.transaction() as conn:
            row = conn.execute("SELECT id FROM knowledge_documents WHERE id=?", (document_id,)).fetchone()
            if row is None:
                raise ApiError("document_missing", "Document was not found", 404)
            now = utc_now()
            conn.execute("UPDATE knowledge_documents SET deleted_at=?,active_revision=NULL,title='Deleted document',updated_at=? WHERE id=?", (now, now, document_id))
            conn.execute("INSERT OR REPLACE INTO deletion_ledger VALUES('knowledge-document',?,?)", (document_id, now))
            for revision in conn.execute("SELECT id FROM knowledge_revisions WHERE document_id=?", (document_id,)).fetchall():
                for job in conn.execute("SELECT id FROM knowledge_jobs WHERE revision_id=? AND state IN ('queued','processing')", (revision["id"],)).fetchall():
                    self._cancel_in(conn, job["id"], revision["id"], "deleted")
                conn.execute("DELETE FROM knowledge_passages WHERE revision_id=?", (revision["id"],))
                conn.execute("UPDATE knowledge_revisions SET status='deleted',metadata_json='{}',rights_json='{}',extraction_json=NULL WHERE id=?", (revision["id"],))
                self._schedule_cleanup(conn, revision["id"], True)
        pending = self.cleanup()
        return {"document_id": document_id, "status": "deleted", "cleanup_pending": bool(pending)}
