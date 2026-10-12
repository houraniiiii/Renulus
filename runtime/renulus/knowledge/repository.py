"""SQLite authority with staged, cancellable derived revisions."""
from datetime import datetime, timezone
from contextlib import closing, contextmanager, nullcontext
import hashlib
import json
from pathlib import Path
import re
import shutil
import time
from threading import RLock

from ..contracts import ApiError, ContextScope, Scope, durable_id
from ..storage.database import utc_now
from ..storage.assessment_policy import require_assistance
from .engines import DoclingExtractor, FastEmbedEngine, LanceIndex, MAX_BYTES, MAX_PAGES, OfflineAssets
from .models import Rights, SourceMetadata, own_text_rights
from .office import OFFICE_MEDIA, validate_office
from .source_status import SourceStatusJournal

TERMINAL = {"ready", "failed", "cancelled"}
INDEX_BATCH = 64
CLEANUP_SWEEP = 64
RETRY_BASE_SECONDS = 1
RETRY_MAX_SECONDS = 300
# Shared by FIFO and priority selection; direct execution rechecks in its claim
# transaction. Canonical cleanup is also the fence after a portable restore.
QUEUED_JOB = ("j.state='queued' AND NOT EXISTS "
              "(SELECT 1 FROM knowledge_cleanup c WHERE c.revision_id=j.revision_id)")
MAX_RETRIEVAL_REVISIONS = 1000
# Metadata routes must not load the extracted document or original file path.
REVISION_SUMMARY = ("r.id,r.document_id,r.ordinal,r.status,r.sha256,r.media_type,r.bytes,"
                    "r.metadata_json,r.rights_json,r.embedding_model,r.chunk_tokens,"
                    "r.created_at,r.activated_at")
MEDIA = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg",
         ".jpeg": "image/jpeg", ".tif": "image/tiff", ".tiff": "image/tiff",
         ".txt": "text/plain", ".md": "text/markdown", ".csv": "text/csv",
         ".html": "text/html", ".htm": "text/html", ".xml": "application/xml", **OFFICE_MEDIA}


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
        self._index_lock = RLock()
        self._active_ingestion = None
        # Native handles survive failed close until a real cleanup retry settles
        # them. SQLite records intent, not transferable process ownership.
        self._retired_indexes = {}
        self.source_status = SourceStatusJournal(self)

    def update_source_status(self, event):
        return self.source_status.update(event)

    @contextmanager
    def recovery_guard(self):
        if not self._ingest_lock.acquire(timeout=90):
            raise ApiError("recovery_busy", "The library is finishing an import. Retry backup or restore after this file completes", 409, True)
        try:
            if self._active_ingestion is not None:
                raise ApiError("recovery_busy", "The library is still finishing an import. Retry recovery after it settles", 409, True)
            with self._index_lock, self._lock:
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
        compact = self._generation_path(generation)
        legacy = self.paths.indexes / "knowledge-generations" / generation
        # Existing selected generations remain readable. New generations use a
        # shorter local path so Lance's Windows atomic writer stays below MAX_PATH.
        return legacy if legacy.is_dir() and not compact.is_dir() else compact

    def _generation_path(self, generation):
        return self.paths.indexes / "k" / generation.removeprefix("index_")

    def _index_token(self, index=None):
        return Path((index or self.index).path).relative_to(self.paths.indexes).as_posix()

    def _index_folder(self, token):
        if not re.fullmatch(r"knowledge|k/[0-9a-f]{32}|knowledge-generations/index_[0-9a-f]{32}", token):
            raise ApiError("unsafe_index_path", "Derived index cleanup left its owned folder", 409)
        return self.paths.indexes / token

    def _remove_index_folder(self, path):
        path = Path(path)
        self._index_folder(path.relative_to(self.paths.indexes).as_posix())
        # Do not follow a replaced generation parent or a Windows junction.
        for part in (path, path.parent):
            if part.is_symlink() or part.is_junction():
                raise ApiError("unsafe_index_path", "Derived index cleanup left its owned folder", 409)
        if not path.exists():
            return
        if not path.resolve().is_relative_to(self.paths.indexes.resolve()):
            raise ApiError("unsafe_index_path", "Derived index cleanup left its owned folder", 409)
        shutil.rmtree(path)

    @staticmethod
    def _work_in(conn, kind, target, generation):
        conn.execute("INSERT INTO knowledge_index_work(kind,target,generation) VALUES(?,?,?) "
                     "ON CONFLICT(kind,target,generation) DO NOTHING", (kind, target, generation))

    def _work_failed(self, kind, target, generation, code):
        with self.db.transaction() as conn:
            self._work_in(conn, kind, target, generation)
            attempts = conn.execute("SELECT attempts FROM knowledge_index_work WHERE kind=? AND target=? AND generation=?",
                                    (kind, target, generation)).fetchone()[0] + 1
            delay = min(RETRY_MAX_SECONDS, RETRY_BASE_SECONDS * 2 ** min(attempts - 1, 20))
            conn.execute("UPDATE knowledge_index_work SET attempts=?,retry_after=?,error_code=? "
                         "WHERE kind=? AND target=? AND generation=?",
                         (attempts, time.time() + delay, code, kind, target, generation))

    def mark_index_dirty_in(self, conn, generation=None):
        """Caller owns _index_lock; durable debt must precede native mutation.

        #25 uses this only for removal. #26 may use it for admitted append/FTS
        maintenance; ordinary append maintenance is deliberately not enabled yet.
        """
        generation = generation or self._index_token()
        self._work_in(conn, "maintenance", "passages", generation)
        conn.execute("UPDATE knowledge_index_work SET dirty_sequence=dirty_sequence+1 "
                     "WHERE kind='maintenance' AND target='passages' AND generation=?", (generation,))

    def _cleanup_index_generations(self, *, force=True):
        active = self._index_token()
        candidates = {"knowledge", *self._retired_indexes}
        for folder, pattern in (("knowledge-generations", r"index_[0-9a-f]{32}"),
                                ("k", r"[0-9a-f]{32}")):
            generations = self.paths.indexes / folder
            if generations.is_dir() and not generations.is_symlink() and not generations.is_junction():
                candidates.update(folder + "/" + path.name for path in generations.iterdir()
                                  if re.fullmatch(pattern, path.name))
        with self.db.transaction() as conn:
            for token in candidates - {active}:
                if token in self._retired_indexes or self._index_folder(token).exists():
                    self._work_in(conn, "retirement", token, token)
        tasks = self.db.fetch_all("SELECT * FROM knowledge_index_work WHERE kind='retirement' "
                                 "ORDER BY retry_after,target")
        attempted = 0
        for task in tasks:
            token = task["target"]
            if token == active or attempted >= CLEANUP_SWEEP or (not force and task["retry_after"] > time.time()):
                continue
            attempted += 1
            try:
                previous = self._retired_indexes.get(token)
                if previous is not None:
                    previous.close()
                    del self._retired_indexes[token]
                self._remove_index_folder(self._index_folder(token))
                with self.db.transaction() as conn:
                    conn.execute("DELETE FROM knowledge_index_work WHERE generation=? AND kind IN ('retirement','maintenance','removal')", (token,))
            except Exception:
                self._work_failed("retirement", token, task["generation"], "index_cleanup_pending")
        return self.db.fetch_all("SELECT target AS generation,error_code FROM knowledge_index_work WHERE kind='retirement'")

    def _pending_index_work(self):
        pending = self.db.fetch_all("SELECT revision_id,error_code FROM knowledge_cleanup")
        pending += self.db.fetch_all("SELECT generation,COALESCE(error_code,'index_cleanup_pending') AS error_code "
                                     "FROM knowledge_index_work WHERE kind='retirement' OR "
                                     "(kind='maintenance' AND dirty_sequence>completed_sequence)")
        return pending

    def rebuild_index(self):
        """Stage canonical eligible passages, validate, then atomically select them."""
        with self._ingest_lock, self._index_lock, self._lock:
            if self._active_ingestion is not None:
                raise ApiError("recovery_busy", "The library is still finishing an import. Retry recovery after it settles", 409, True)
            publication = self.db.fetch_one("SELECT * FROM knowledge_index_work WHERE kind='publication' AND generation=?",
                                            (self._index_token(),))
            restored = self.db.fetch_one("SELECT 1 FROM preferences WHERE key='knowledge.restore_dirty' AND value='true'")
            if publication and not restored:
                # A committed selector is not a failed build. Retry only old
                # handle/folder cleanup, even across a process restart.
                pending = self.cleanup()
                if not pending:
                    self.db.execute("DELETE FROM knowledge_index_work WHERE kind='publication' AND generation=?", (self._index_token(),))
                return {"status": "ready", "passages": publication["passages"],
                        "generation": publication["target"], "cleanup_pending": bool(pending)}
            # A restore can bring an older active row beside a newer tombstone.
            deleted = self.db.fetch_all("SELECT d.id FROM knowledge_documents d JOIN deletion_ledger l ON l.entity_id=d.id AND l.entity_type='knowledge-document' WHERE d.deleted_at IS NULL")
            for row in deleted:
                self.delete_document(row["id"])
            self.cleanup()
            # Optimization debt does not invalidate ready rows and must not
            # prevent replacing their generation. Only unfinished row/original
            # cleanup is a destructive admission fence.
            if self.db.fetch_one("SELECT 1 FROM knowledge_cleanup"):
                raise ApiError("knowledge_cleanup_pending", "Finish deleted-document cleanup before rebuilding the library", 503, True)
            generation = durable_id("index")
            candidate = LanceIndex(self._generation_path(generation), self.embedder.dimensions)
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
                if identities:
                    candidate.build_fts()
                candidate.validate_passages(identities)
                with self.db.transaction() as conn:
                    conn.execute("INSERT INTO preferences VALUES('knowledge.index_generation',?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at", (json.dumps(generation), utc_now()))
                    conn.execute("DELETE FROM preferences WHERE key='knowledge.restore_dirty'")
                    token, old_token = self._index_token(candidate), self._index_token(previous)
                    self._work_in(conn, "retirement", old_token, old_token)
                    conn.execute("DELETE FROM knowledge_index_work WHERE kind='publication'")
                    conn.execute("INSERT INTO knowledge_index_work(kind,target,generation,passages) VALUES('publication',?,?,?)",
                                 (generation, token, len(identities)))
                self.index = candidate
                activated = True
                self._retired_indexes[old_token] = previous
                try:
                    pending = self._cleanup_index_generations()
                    if not pending:
                        self.db.execute("DELETE FROM knowledge_index_work WHERE kind='publication' AND generation=?", (token,))
                except Exception:
                    # Publication already committed. Durable retirement intent
                    # and the retained object make the next retry cleanup-only.
                    pending = True
                return {"status": "ready", "passages": len(identities), "generation": generation,
                        "cleanup_pending": bool(pending)}
            except Exception:
                if not activated:
                    token = self._index_token(candidate)
                    self._retired_indexes[token] = candidate
                    try:
                        candidate.close()
                        del self._retired_indexes[token]
                        self._remove_index_folder(candidate.path)
                    except Exception:
                        self._work_failed("retirement", token, token, "index_cleanup_pending")
                raise

    def capabilities(self):
        result = self.assets.capabilities()
        import importlib.util
        result["markup_import"] = bool(result["text_import"] and importlib.util.find_spec("defusedxml"))
        return result

    def extract_bytes(self, data: bytes, filename: str, title: str):
        if self.capabilities()["temporary_extraction"] is not True:
            raise ApiError("temporary_extraction_unavailable", "The verified temporary extraction path is not available", 503, True)
        return self.extractor.extract_bytes(data, filename, title)

    def saved_extraction_in(self, conn, revision_id, *, operation="import", expected_fingerprint=None,
                            expected_policy_revision=None, expected_context_epoch=None):
        """Trusted saved extraction; caller owns snapshot/publication transaction."""
        from .saved_extraction import saved_extraction_in
        return saved_extraction_in(self, conn, revision_id, operation=operation,
            expected_fingerprint=expected_fingerprint, expected_policy_revision=expected_policy_revision,
            expected_context_epoch=expected_context_epoch)

    def require_original_display_in(self, conn, pin):
        """Authorize another owner's immutable private source body for inspection."""
        from .saved_extraction import require_original_display_in
        return require_original_display_in(self, conn, pin)

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
                    scope=None, idempotency_key=None, document_id=None, reserved=False, process=True,
                    expected_revision_id=None, note_save=False, note_project_id=None):
        scope = self._import_scope(scope or ContextScope(kind=Scope.LIBRARY))
        if not text.strip():
            raise ApiError("empty_document", "Add some text before importing", 422)
        data = text.encode("utf-8")
        return self._import(data, ".txt", title, metadata, rights or own_text_rights(), scope,
                            idempotency_key, document_id, reserved, process,
                            expected_revision_id=expected_revision_id, note_save=note_save,
                            note_project_id=note_project_id)

    def import_file(self, path: str | Path, *, title=None, metadata=None, rights=None, scope=None,
                    idempotency_key=None, document_id=None, reserved=False, expected_sha256=None, process=True):
        scope = self._import_scope(scope or ContextScope(kind=Scope.LIBRARY))
        path = Path(path).resolve()
        if not path.is_file():
            raise ApiError("file_missing", "The selected file is no longer available", 404, True)
        suffix = path.suffix.lower()
        if suffix not in MEDIA:
            raise ApiError("unsupported_file", "Choose a PDF, image, UTF-8 text, PPTX, DOCX or XLSX file", 415)
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

    def _import(self, data, suffix, title, metadata, rights, scope, key, document_id, reserved, process,
                *, expected_revision_id=None, note_save=False, note_project_id=None):
        if len(data) > MAX_BYTES:
            raise ApiError("document_limit", "The maximum file size is 64 MiB", 413)
        metadata = metadata if isinstance(metadata, SourceMetadata) else SourceMetadata.model_validate(metadata or {})
        rights = rights if isinstance(rights, Rights) else Rights.model_validate(rights)
        if metadata.source_id == "E02":
            reserved = True
        if not rights.cache or not rights.display or (not reserved and (not rights.index or not rights.embedding)):
            raise ApiError("source_permission_required", "Confirm display, local caching, indexing and embedding permission for this source", 403)
        if suffix in OFFICE_MEDIA:
            validate_office(data, suffix, max_bytes=MAX_BYTES, max_pages=MAX_PAGES)
        digest = hashlib.sha256(data).hexdigest()
        request_metadata = metadata.model_dump()
        if request_metadata.get("original_sha256") is None:
            # The additive provenance field must not change a pre-field replay.
            request_metadata.pop("original_sha256", None)
        request_values = [digest, title, request_metadata, rights.model_dump(), scope.model_dump(), document_id, reserved]
        if expected_revision_id is not None or note_save:
            request_values.append({"expected_revision_id": expected_revision_id,
                "note_save": note_save, "project_id": note_project_id})
        request_hash = hashlib.sha256(dumps(request_values).encode()).hexdigest()
        note_saved_in = None
        if note_save:
            projects = self.services.registry.get("projects")
            note_saved_in = getattr(projects, "note_saved_in", None)
            if not callable(note_saved_in):
                raise ApiError("notes_owner_unavailable", "Saved note project links are not connected", 503, True)
            if (suffix != ".txt" or reserved or scope.entity_id is not None or
                    "study-note" not in metadata.asset_role or bool(document_id) != bool(expected_revision_id)):
                raise ApiError("note_request_invalid", "Use the saved personal note owner and current revision", 422)
            with self.db.transaction() as conn:
                require_assistance(conn)
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
                        if expected_revision_id is not None and row["latest_revision"] != expected_revision_id:
                            raise ApiError("note_revision_conflict", "Reload the note before saving", 409, True)
                        if note_save:
                            current = self._note_row_in(conn, document_id, expected_revision_id)
                            allowed = self.require_original_display_in(conn, {"document_id": document_id,
                                "revision_id": current["id"], "original_sha256": current["sha256"]})
                            if allowed["rights"] != rights.model_dump():
                                raise ApiError("note_rights_changed", "Note permissions changed; reload before saving", 409, True)
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
                    if note_save:
                        require_assistance(conn)
                        note_saved_in(conn, document_id, revision_id, note_project_id)
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
        row = conn.execute("SELECT j.state,r.id,r.document_id,d.latest_revision,d.deleted_at,d.scope_kind FROM knowledge_jobs j JOIN knowledge_revisions r ON r.id=j.revision_id JOIN knowledge_documents d ON d.id=r.document_id WHERE j.id=?", (job_id,)).fetchone()
        return (row and row["state"] == "processing" and row["deleted_at"] is None
                and row["latest_revision"] == row["id"] and row["scope_kind"] == Scope.LIBRARY.value)

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
            if self._active_ingestion is not None:
                raise ApiError("ingestion_busy", "The library is still finishing an import. Retry after it settles", 409, True)
            self._active_ingestion = job_id
            try:
                return self._run_job(job_id)
            finally:
                self._active_ingestion = None

    def _run_job(self, job_id):
        with self._lock, self.db.transaction() as conn:
            job = conn.execute("SELECT * FROM knowledge_jobs WHERE id=?", (job_id,)).fetchone()
            if not job:
                raise ApiError("job_missing", "Import job was not found", 404)
            if job["state"] != "queued":
                return dict(job)
            if conn.execute("SELECT 1 FROM knowledge_cleanup WHERE revision_id=?", (job["revision_id"],)).fetchone():
                return dict(job)  # Partial rows must settle before this same ID stages again.
            revision = dict(conn.execute("SELECT * FROM knowledge_revisions WHERE id=?", (job["revision_id"],)).fetchone())
            document = dict(conn.execute("SELECT * FROM knowledge_documents WHERE id=?", (revision["document_id"],)).fetchone())
            conn.execute("UPDATE knowledge_jobs SET state='processing',phase='extraction' WHERE id=?", (job_id,))
            conn.execute("UPDATE knowledge_revisions SET status='processing' WHERE id=?", (revision["id"],))
        try:
            extracted = self.extractor.extract_file(Path(revision["original_path"]), document["title"])
            if not self._phase(job_id, "embedding"):
                self.cleanup(force=False)
                return self.get_job(job_id)
            passages = extracted.passages
            for item in passages:
                item["id"] = durable_id("passage")
            self._stage_import(job_id, revision, document, extracted)
        except Exception as error:
            code = error.code if isinstance(error, ApiError) else "ingestion_failed"
            message = error.message if isinstance(error, ApiError) else "Document ingestion failed; check offline helpers and file integrity"
            with self._lock, self.db.transaction() as conn:
                if self._guard(conn, job_id):
                    conn.execute("UPDATE knowledge_jobs SET state='failed',phase='failed',error_code=?,error_message=?,finished_at=? WHERE id=?", (code, message, utc_now(), job_id))
                    conn.execute("UPDATE knowledge_revisions SET status='failed' WHERE id=?", (revision["id"],))
                    self._schedule_cleanup(conn, revision["id"], True)
        self.cleanup(force=False)
        return self.get_job(job_id)

    def _stage_import(self, job_id, revision, document, extracted):
        # Bound native work and recheck cancellation/replacement between batches.
        # No engine operation or wait for an engine lock owns the metadata lock.
        passages = extracted.passages
        for offset in range(0, len(passages), INDEX_BATCH):
            if not self._phase(job_id, "embedding"):
                return
            batch = passages[offset:offset + INDEX_BATCH]
            if document["reserved"]:
                continue
            vectors = self.embedder.embed([p["context_text"] for p in batch])
            rows = [{"passage_id": p["id"], "revision_id": revision["id"],
                     "document_id": document["id"], "text": p["context_text"], "vector": v}
                    for p, v in zip(batch, vectors, strict=True)]
            with self._index_lock:
                with self._lock, self.db.transaction() as conn:
                    if not self._guard(conn, job_id):
                        return
                self.index.stage(rows, create_fts=False)
        # Prepare potentially large JSON before entering the publication lock.
        stored = [(p["id"], revision["id"], i, p["text"], p["context_text"],
                   dumps(p["locators"]), dumps(p["headings"])) for i, p in enumerate(passages)]
        extraction_json = dumps(extracted.document)
        with self._index_lock:
            with self._lock, self.db.transaction() as conn:
                if not self._guard(conn, job_id):
                    return
            if passages and not document["reserved"]:
                self.index.build_fts()
            with self._lock, self.db.transaction() as conn:
                if not self._guard(conn, job_id):
                    self._schedule_cleanup(conn, revision["id"], True)
                    return
                previous = conn.execute("SELECT active_revision FROM knowledge_documents WHERE id=?", (document["id"],)).fetchone()[0]
                conn.executemany("INSERT INTO knowledge_passages VALUES(?,?,?,?,?,?,?)", stored)
                now = utc_now()
                conn.execute("UPDATE knowledge_revisions SET status='ready',extraction_json=?,embedding_model=?,chunk_tokens=?,activated_at=? WHERE id=?", (extraction_json, self.embedder.model_id, self.embedder.max_tokens, now, revision["id"]))
                conn.execute("UPDATE knowledge_documents SET active_revision=?,updated_at=? WHERE id=?", (revision["id"], now, document["id"]))
                conn.execute("UPDATE knowledge_jobs SET state='ready',phase='complete',finished_at=? WHERE id=?", (now, job_id))
                if previous and previous != revision["id"]:
                    self._schedule_cleanup(conn, previous, False)

    def _schedule_cleanup(self, conn, revision_id, remove_original):
        # A saved note revision is an immutable original even when its derived
        # extraction is cancelled or fails. Explicit owner deletion still
        # upgrades the durable cleanup task and removes all revision bytes.
        row = conn.execute("SELECT r.metadata_json,r.status,d.deleted_at,d.scope_kind,d.scope_entity,d.reserved "
            "FROM knowledge_revisions r JOIN knowledge_documents d ON d.id=r.document_id WHERE r.id=? "
            "AND NOT EXISTS(SELECT 1 FROM deletion_ledger WHERE "
            "(entity_type IN ('knowledge-document','document') AND entity_id=d.id) OR "
            "(entity_type IN ('knowledge-revision','revision') AND entity_id=r.id))", (revision_id,)).fetchone()
        retain_note = False
        if (row and not row["deleted_at"] and row["status"] != "deleted" and not row["reserved"]
                and row["scope_kind"] == Scope.LIBRARY.value and row["scope_entity"] is None):
            try:
                retain_note = "study-note" in SourceMetadata.model_validate_json(row["metadata_json"]).asset_role
            except ValueError:
                pass
        remove_original = bool(remove_original and not retain_note)
        conn.execute("INSERT INTO knowledge_cleanup(revision_id,remove_original,created_at) VALUES(?,?,?) "
            "ON CONFLICT(revision_id) DO UPDATE SET remove_original=CASE WHEN ? THEN 0 "
            "ELSE MAX(remove_original,excluded.remove_original) END",
            (revision_id, int(remove_original), utc_now(), int(retain_note)))

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

    def cleanup(self, *, force=True):
        """Bounded cleanup; explicit retry bypasses backoff, worker uses due work.

        Removal acknowledgement and fragment maintenance are separate. A native
        optimize failure cannot leave destructive cleanup aimed at a later retry.
        """
        if not self._index_lock.acquire(blocking=False):
            return self._pending_index_work()
        try:
            generation = self._index_token()
            # Machine-local retries are reconstructed from canonical intent on
            # restore/restart. Old-generation removal is never an admission fence.
            with self.db.transaction() as conn:
                conn.execute("DELETE FROM knowledge_index_work WHERE kind='removal' AND "
                             "(generation!=? OR NOT EXISTS(SELECT 1 FROM knowledge_cleanup c WHERE c.revision_id=target))", (generation,))
                for task in conn.execute("SELECT revision_id FROM knowledge_cleanup").fetchall():
                    self._work_in(conn, "removal", task["revision_id"], generation)
            tasks = self.db.fetch_all("SELECT c.revision_id,w.retry_after FROM knowledge_cleanup c "
                                     "JOIN knowledge_index_work w ON w.kind='removal' AND w.target=c.revision_id AND w.generation=? "
                                     "ORDER BY w.retry_after,c.created_at,c.revision_id", (generation,))
            attempted = 0
            for selected in tasks:
                if attempted >= CLEANUP_SWEEP or (not force and selected["retry_after"] > time.time()):
                    continue
                attempted += 1
                revision_id = selected["revision_id"]
                try:
                    # Re-read intent under the engine/metadata lock order, not
                    # the stale sweep snapshot. Activation needs _index_lock.
                    with self._lock, self.db.transaction() as conn:
                        row = conn.execute("SELECT c.*,r.document_id,r.status,d.active_revision,d.deleted_at,w.completed_sequence AS removed "
                            "FROM knowledge_cleanup c JOIN knowledge_revisions r ON r.id=c.revision_id "
                            "JOIN knowledge_documents d ON d.id=r.document_id JOIN knowledge_index_work w "
                            "ON w.kind='removal' AND w.target=c.revision_id AND w.generation=? WHERE c.revision_id=?", (generation, revision_id)).fetchone()
                        if not row:
                            continue
                        task = dict(row)
                        tombstone = conn.execute("SELECT 1 FROM deletion_ledger WHERE "
                            "(entity_type IN ('knowledge-document','document') AND entity_id=?) OR "
                            "(entity_type IN ('knowledge-revision','revision') AND entity_id=?)",
                            (task["document_id"], revision_id)).fetchone()
                        if task["active_revision"] == revision_id and task["status"] == "ready" and not task["deleted_at"] and not tombstone:
                            conn.execute("DELETE FROM knowledge_cleanup WHERE revision_id=?", (revision_id,))
                            conn.execute("DELETE FROM knowledge_index_work WHERE kind='removal' AND target=?", (revision_id,))
                            continue
                        if not task["removed"]:
                            self.mark_index_dirty_in(conn, generation)
                    if not task["removed"]:
                        self.index.remove(revision_id)
                        # Native delete acknowledgement precedes file cleanup.
                        with self.db.transaction() as conn:
                            conn.execute("UPDATE knowledge_index_work SET completed_sequence=1,error_code=NULL "
                                         "WHERE kind='removal' AND target=? AND generation=?", (revision_id, generation))
                    if task["remove_original"]:
                        folder = self._folder(task["document_id"], revision_id)
                        if folder.exists():
                            shutil.rmtree(folder)
                    with self._lock, self.db.transaction() as conn:
                        if task["remove_original"]:
                            conn.execute("UPDATE knowledge_revisions SET original_path=NULL,extraction_json=NULL WHERE id=?", (revision_id,))
                        # A delete can upgrade a task while native removal runs.
                        conn.execute("DELETE FROM knowledge_cleanup WHERE revision_id=? AND remove_original=?", (revision_id, task["remove_original"]))
                        if not conn.execute("SELECT 1 FROM knowledge_cleanup WHERE revision_id=?", (revision_id,)).fetchone():
                            conn.execute("DELETE FROM knowledge_index_work WHERE kind='removal' AND target=?", (revision_id,))
                except Exception:
                    self.db.execute("UPDATE knowledge_cleanup SET error_code='cleanup_pending' WHERE revision_id=?", (revision_id,))
                    self._work_failed("removal", revision_id, generation, "cleanup_pending")
            debt = self.db.fetch_one("SELECT * FROM knowledge_index_work WHERE kind='maintenance' AND generation=? AND dirty_sequence>completed_sequence", (generation,))
            if debt and (force or debt["retry_after"] <= time.time()):
                try:
                    self.index.optimize()
                    self.db.execute("UPDATE knowledge_index_work SET completed_sequence=?,attempts=0,retry_after=0,error_code=NULL "
                                    "WHERE kind='maintenance' AND target='passages' AND generation=?", (debt["dirty_sequence"], generation))
                except Exception as error:
                    code = error.code if isinstance(error, ApiError) else "index_maintenance_pending"
                    self._work_failed("maintenance", "passages", generation, code)
            self._cleanup_index_generations(force=force)
            return self._pending_index_work()
        finally:
            self._index_lock.release()

    def recover(self):
        """Resume interrupted jobs only after their real ingestion owner settles."""
        if not self._ingest_lock.acquire(blocking=False):
            raise ApiError("recovery_busy", "The library is still finishing an import. Retry recovery after it settles", 409, True)
        try:
            # RLock reentrancy is not permission for an extractor callback to
            # reset its own still-processing job.
            if self._active_ingestion is not None:
                raise ApiError("recovery_busy", "The library is still finishing an import. Retry recovery after it settles", 409, True)
            with self._index_lock, self._lock, self.db.transaction() as conn:
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
                    if not job["deleted_at"] and job["latest_revision"] == job["revision_id"] and job["scope_kind"] == Scope.LIBRARY.value and job["original_path"] and Path(job["original_path"]).is_file():
                        # An imported/stale cleanup flag may describe a prior
                        # cancelled attempt, not this canonical live retry.
                        conn.execute("UPDATE knowledge_cleanup SET remove_original=0 WHERE revision_id=?", (job["revision_id"],))
            return self.cleanup()
        finally:
            self._ingest_lock.release()

    def next_queued_job(self):
        # Work is durable in SQLite, not held in a request or an in-memory list.
        return self.db.fetch_one("SELECT j.id FROM knowledge_jobs j WHERE " + QUEUED_JOB + " ORDER BY j.created_at,j.id LIMIT 1")

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
        with self._lock, closing(self.db.connect()) as conn:
            # One read snapshot/connection for counts and the selected page.
            conn.execute("BEGIN")
            counts = {row["status"]: row["n"] for row in conn.execute(
                "SELECT " + state + " AS status,COUNT(*) AS n" + source + count_where + " GROUP BY " + state)}
            total = conn.execute("SELECT COUNT(*) AS n" + source + where, tuple(parameters)).fetchone()["n"]
            paging = " LIMIT ? OFFSET ?" if limit is not None else " LIMIT -1 OFFSET ?"
            page_parameters = parameters + ([limit, offset] if limit is not None else [offset])
            rows = [dict(row) for row in conn.execute("SELECT d.*" + source + where +
                    " ORDER BY d.updated_at DESC,d.id" + paging, tuple(page_parameters))]
            return {"documents": self._document_summaries(conn, rows),
                    "total": total, "counts": counts, "offset": offset, "limit": limit}

    def get_document(self, document_id, *, include_deleted=False):
        with self._lock, closing(self.db.connect()) as conn:
            conn.execute("BEGIN")
            row = conn.execute("SELECT * FROM knowledge_documents WHERE id=?", (document_id,)).fetchone()
            if row is None or (row["deleted_at"] and not include_deleted):
                raise ApiError("document_missing", "Document was not found", 404)
            return self._document_summaries(conn, [dict(row)])[0]

    def _document_summaries(self, conn, documents):
        for offset in range(0, len(documents), 100):
            batch = documents[offset:offset + 100]
            by_id = {row["id"]: row for row in batch}
            for row in batch:
                row["scope"] = {"kind": row.pop("scope_kind"), "entity_id": row.pop("scope_entity")}
                row["reserved"] = bool(row["reserved"])
                row["revisions"] = []
                row["cleanup_pending"] = False
            placeholders = ",".join("?" for _ in batch)
            identifiers = tuple(by_id)
            sql = ("SELECT " + REVISION_SUMMARY +
                   ",(SELECT COUNT(*) FROM knowledge_passages p WHERE p.revision_id=r.id) AS passage_count "
                   "FROM knowledge_revisions r WHERE r.document_id IN (" + placeholders + ") ORDER BY r.ordinal DESC")
            for stored in conn.execute(sql, identifiers):
                revision = dict(stored)
                revision["metadata"] = json.loads(revision.pop("metadata_json"))
                revision["rights"] = json.loads(revision.pop("rights_json"))
                by_id[revision["document_id"]]["revisions"].append(revision)
            for pending in conn.execute(
                    "SELECT DISTINCT r.document_id FROM knowledge_cleanup c JOIN knowledge_revisions r ON r.id=c.revision_id WHERE r.document_id IN (" + placeholders + ")", identifiers):
                by_id[pending["document_id"]]["cleanup_pending"] = True
            for row in batch:
                row["status"] = "deleted" if row["deleted_at"] else (row["revisions"][0]["status"] if row["revisions"] else "empty")
        return documents

    def _eligible(self, metadata, rights, topic_id, current_only):
        if not all(rights.get(operation) for operation in ("display", "model_input", "index", "embedding")):
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

    def retrieve(self, query, topic_id=None, scope=None, *, limit=8, current_only=False,
                 revision_ids: list[str] | None = None):
        """Intersect canonical eligibility with an optional caller-owned revision pin.

        None preserves global Library retrieval; an empty list is an empty scope.
        Capture the supplied list once so concurrent caller mutation cannot widen
        candidates. Project owners still recheck membership/context before publishing.
        """
        revision_filter = None
        if revision_ids is not None:
            if (not isinstance(revision_ids, list) or len(revision_ids) > MAX_RETRIEVAL_REVISIONS
                    or any(not isinstance(value, str) or not 1 <= len(value) <= 256
                           for value in revision_ids)):
                raise ApiError("revision_scope_invalid", "Use at most 1,000 revision IDs of 1–256 characters", 422)
            revision_filter = tuple(dict.fromkeys(revision_ids))
        if self.db.fetch_one("SELECT 1 FROM preferences WHERE key='knowledge.restore_dirty' AND value='true'"):
            raise ApiError("knowledge_rebuild_required", "The restored Library needs its local search rebuild. Open data recovery and retry the rebuild.", 503, True)
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
            eligible = self._retrievable_revisions(scope, topic_id, current_only, revision_ids=revision_filter)
            if not eligible:
                return {"passages": [], "status": "no_eligible_documents", "current_only": current_only}
        vector = self.embedder.embed([query], query=True)[0]
        with self._index_lock:
            # Embedding may have waited for a cold model or an import batch.
            with self._lock:
                eligible = self._retrievable_revisions(scope, topic_id, current_only, revision_ids=revision_filter)
            if not eligible:
                return {"passages": [], "status": "no_eligible_documents", "current_only": current_only}
            matches = self.index.search(query, vector, list(eligible), limit * 3)
        with self._lock, closing(self.db.connect()) as conn:
            conn.execute("BEGIN")
            # Search is also expensive: recheck active version, deletion, source
            # status, permissions and page exclusions against the same snapshot.
            eligible = self._retrievable_revisions(scope, topic_id, current_only, conn=conn, revision_ids=revision_filter)
            passages = []
            for hit in matches:
                revision = eligible.get(hit["revision_id"])
                if revision is None:
                    continue
                passage = conn.execute("SELECT * FROM knowledge_passages WHERE id=? AND revision_id=?", (hit["passage_id"], revision["id"])).fetchone()
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

    def _retrievable_revisions(self, scope, topic_id, current_only, *, conn=None, revision_ids=None):
        if revision_ids is not None and not revision_ids:
            return {}
        sql = ("SELECT " + REVISION_SUMMARY + ",d.title,d.source_id FROM knowledge_revisions r "
               "JOIN knowledge_documents d ON d.active_revision=r.id WHERE d.deleted_at IS NULL "
               "AND d.reserved=0 AND r.status='ready' AND d.scope_kind='personal-library' "
               "AND (d.scope_entity IS NULL OR d.scope_entity=?) "
               "AND EXISTS (SELECT 1 FROM knowledge_passages p WHERE p.revision_id=r.id)")
        parameters = (scope.entity_id,)
        if revision_ids is not None:
            # One JSON parameter keeps the bounded set below SQLite variable limits.
            # This predicate applies before the native index ranks any candidates.
            sql += " AND r.id IN (SELECT value FROM json_each(?))"
            parameters += (dumps(revision_ids),)
        rows = ([dict(row) for row in conn.execute(sql, parameters)]
                if conn is not None else self.db.fetch_all(sql, parameters))
        return {r["id"]: r for r in rows if self._eligible(
            json.loads(r["metadata_json"]), json.loads(r["rights_json"]), topic_id, current_only)}

    def check_evidence(self, citations, *, scope, topic_id=None, current_only=False, conn=None):
        """Read-only source projection; optionally use the caller's publication snapshot.

        A supplied connection already owns canonical serialization. Do not acquire
        the Library lock underneath its write transaction (import uses lock → DB).
        This path does no engine, index, original-file or remote work.
        """
        scope = self._scope(scope)
        if scope.kind != Scope.STUDY:
            raise ApiError("retrieval_scope_denied", "Evidence checks require ordinary study scope", 403)
        if not isinstance(citations, list) or len(citations) > 20:
            raise ApiError("evidence_limit", "Check at most twenty source references", 422)
        eligible_ids, metadata_by_id = [], {}
        supplied = conn is not None
        with (nullcontext() if supplied else self._lock), (nullcontext(conn) if supplied else closing(self.db.connect())) as conn:
            if not supplied:
                conn.execute("BEGIN")
            revisions = self._retrievable_revisions(scope, topic_id, current_only, conn=conn)
            for citation in citations:
                identifier = citation.get("id") if isinstance(citation, dict) else None
                if not isinstance(identifier, str):
                    continue
                if citation.get("source_kind") == "public-article":
                    try:
                        metadata = SourceMetadata.model_validate(citation["metadata"])
                        rights = Rights.model_validate(citation["rights"])
                        if (metadata.source_id != "L03" or not metadata.pmcid
                                or not re.fullmatch(r"PMC[1-9][0-9]*", metadata.pmcid)
                                or metadata.canonical_url != "https://europepmc.org/articles/" + metadata.pmcid
                                or citation.get("canonical_url") != metadata.canonical_url
                                or citation.get("publication_date") != metadata.publication_date
                                or not metadata.original_sha256 or not metadata.publication_date
                                or not citation.get("locators") or not citation.get("text")
                                or not all((rights.display, rights.model_input, rights.derivation, rights.cache))
                                or rights.licence not in ("CC-BY-2.0", "CC-BY-3.0", "CC-BY-4.0", "CC0-1.0")):
                            continue
                        effective = self.source_status.effective(metadata,
                            self.source_status.events(metadata.source_id, conn)).model_dump()
                        if (any(effective[key] for key in ("retracted", "superseded", "repository_removed", "access_changed", "replaced_topics"))
                                or effective["publication_status"] in ("draft", "preprint")
                                or effective["correction"] and not effective["content_reviewed"]
                                or topic_id and effective["topic_ids"] and topic_id not in effective["topic_ids"]
                                or effective["review_due"] and effective["review_due"][:10] < datetime.now(timezone.utc).date().isoformat()):
                            continue
                        if current_only and (effective["publication_status"] != "final"
                                or not effective["latest_final_verified"] or not effective["content_reviewed"]):
                            continue
                    except (ValueError, TypeError, KeyError):
                        continue
                else:
                    revision_id = citation.get("document_revision") or citation.get("revision_id")
                    revision = revisions.get(revision_id)
                    if not revision or revision["document_id"] != citation.get("document_id"):
                        continue
                    passage = conn.execute("SELECT locators_json FROM knowledge_passages WHERE id=? AND revision_id=?",
                        (citation.get("passage_id") or identifier, revision_id)).fetchone()
                    if not passage:
                        continue
                    effective = json.loads(revision["metadata_json"])
                    rights = json.loads(revision["rights_json"])
                    if (not all(rights.get(operation) for operation in ("display", "cache", "model_input", "derivation"))
                            or effective.get("repository_removed")
                            or effective.get("correction") and not effective.get("content_reviewed")):
                        continue
                    if any(locator.get("page") in effective.get("excluded_pages", []) for locator in json.loads(passage["locators_json"])):
                        continue
                eligible_ids.append(identifier)
                metadata_by_id[identifier] = effective
        return {"state": "available", "eligible_ids": eligible_ids, "metadata": metadata_by_id}

    def citation(self, document_revision, page=None, *, passage_id=None):
        if passage_id is not None and (not isinstance(passage_id, str) or
                not re.fullmatch(r"passage_[0-9a-f]{32}", passage_id)):
            raise ApiError("invalid_passage_id", "Choose a valid cited passage identifier", 422)
        with self._lock:
            revision = self.db.fetch_one("SELECT " + REVISION_SUMMARY + ",d.title,d.source_id,d.deleted_at,d.reserved,d.scope_kind FROM knowledge_revisions r JOIN knowledge_documents d ON d.id=r.document_id WHERE r.id=?", (document_revision,))
            if not revision or revision["deleted_at"] or revision["status"] != "ready":
                raise ApiError("citation_missing", "The cited document revision is unavailable", 404)
            if passage_id is None:
                rows = self.db.fetch_all("SELECT locators_json FROM knowledge_passages WHERE revision_id=?", (document_revision,))
            else:
                passage = self.db.fetch_one("SELECT locators_json FROM knowledge_passages WHERE id=? AND revision_id=?", (passage_id, document_revision))
                if not passage:
                    raise ApiError("passage_missing", "The cited passage is unavailable", 404)
                metadata, rights = json.loads(revision["metadata_json"]), json.loads(revision["rights_json"])
                passage_locators = json.loads(passage["locators_json"])
                # Historical ready revisions remain inspectable. Eligibility
                # applies to the whole passage before any page filter/recovery.
                if (revision["reserved"] or revision["scope_kind"] != Scope.LIBRARY.value or
                        not rights.get("display") or metadata.get("repository_removed") or
                        not self._eligible(metadata, rights, None, False) or
                        any(locator.get("page") in metadata.get("excluded_pages", []) for locator in passage_locators)):
                    raise ApiError("passage_missing", "The cited passage is unavailable or no longer eligible", 404)
                rows = [passage]
            locators = [locator for row in rows for locator in json.loads(row["locators_json"]) if page is None or locator.get("page") == page]
            if page is not None and not locators:
                raise ApiError("page_missing", "That page has no extracted citation location", 404)
            result = {"document_id": revision["document_id"], "document_revision": document_revision,
                    "title": revision["title"], "source_id": revision["source_id"], "page": page,
                    "locators": locators, "metadata": json.loads(revision["metadata_json"]),
                    "original_url": f"/api/v1/library/revisions/{document_revision}/original",
                    "viewer_url": f"/library/{revision['document_id']}?revision={document_revision}" + (f"&page={page}" if page else "")}
            if passage_id is not None:
                result["passage_id"] = passage_id
                result["viewer_url"] += f"&passage_id={passage_id}"
            return result

    def original(self, revision_id):
        row = self.db.fetch_one("SELECT r.id,r.document_id,r.status,r.original_path,r.rights_json,r.media_type,d.deleted_at FROM knowledge_revisions r JOIN knowledge_documents d ON d.id=r.document_id WHERE r.id=?", (revision_id,))
        if not row or row["deleted_at"] or row["status"] == "deleted" or not row["original_path"]:
            raise ApiError("original_missing", "The original is no longer available", 404)
        if not json.loads(row["rights_json"])["display"]:
            raise ApiError("display_denied", "Display permission is unavailable", 403)
        path = Path(row["original_path"]).resolve()
        if not path.is_relative_to(self._folder(row["document_id"], revision_id)) or not path.is_file():
            raise ApiError("original_missing", "The stored original is unavailable", 404)
        return path, row["media_type"]

    def _note_row_in(self, conn, document_id, revision_id=None):
        """Canonical saved-note classification; caller owns the transaction."""
        row = conn.execute("SELECT r.*,d.title,d.source_id,d.latest_revision FROM knowledge_revisions r "
            "JOIN knowledge_documents d ON d.id=r.document_id WHERE d.id=? AND r.id=COALESCE(?,d.latest_revision) "
            "AND d.deleted_at IS NULL AND r.status!='deleted' AND d.scope_kind='personal-library' "
            "AND d.scope_entity IS NULL AND d.reserved=0 AND NOT EXISTS(SELECT 1 FROM deletion_ledger WHERE "
            "(entity_type IN ('knowledge-document','document') AND entity_id=d.id) OR "
            "(entity_type IN ('knowledge-revision','revision') AND entity_id=r.id))", (document_id, revision_id)).fetchone()
        if row is None:
            raise ApiError("note_missing", "The saved note is unavailable", 404)
        try:
            metadata = SourceMetadata.model_validate_json(row["metadata_json"])
        except ValueError:
            raise ApiError("notes_unavailable", "Saved note metadata needs repair", 503) from None
        if ("study-note" not in metadata.asset_role or metadata.source_id != row["source_id"]
                or row["media_type"] != "text/plain"):
            raise ApiError("note_missing", "The saved note is unavailable", 404)
        return dict(row)

    def delete_document(self, document_id, *, expected_revision_id=None, idempotency_key=None, note_delete=False):
        with self._lock, self.db.transaction() as conn:
            delete_hash = None
            if note_delete:
                require_assistance(conn)
                if not expected_revision_id or not idempotency_key:
                    raise ApiError("note_request_invalid", "Use a current note revision and deletion key", 422)
                delete_hash = hashlib.sha256(dumps(["note-delete/1", document_id, expected_revision_id]).encode()).hexdigest()
                previous = conn.execute("SELECT request_hash FROM knowledge_jobs WHERE idempotency_key=?", (idempotency_key,)).fetchone()
                if previous:
                    if previous["request_hash"] != delete_hash:
                        raise ApiError("idempotency_conflict", "That key belongs to a different note request", 409)
                    return {"document_id": document_id, "status": "deleted"}
            row = conn.execute("SELECT id,latest_revision FROM knowledge_documents WHERE id=?", (document_id,)).fetchone()
            if row is None:
                raise ApiError("document_missing", "Document was not found", 404)
            if expected_revision_id is not None and row["latest_revision"] != expected_revision_id:
                raise ApiError("note_revision_conflict", "Reload the note before deleting", 409, True)
            if note_delete:
                self._note_row_in(conn, document_id, expected_revision_id)
            now = utc_now()
            conn.execute("UPDATE knowledge_documents SET deleted_at=?,active_revision=NULL,title='Deleted document',updated_at=? WHERE id=?", (now, now, document_id))
            conn.execute("INSERT OR REPLACE INTO deletion_ledger VALUES('knowledge-document',?,?)", (document_id, now))
            for revision in conn.execute("SELECT id FROM knowledge_revisions WHERE document_id=?", (document_id,)).fetchall():
                for job in conn.execute("SELECT id FROM knowledge_jobs WHERE revision_id=? AND state IN ('queued','processing')", (revision["id"],)).fetchall():
                    self._cancel_in(conn, job["id"], revision["id"], "deleted")
                conn.execute("DELETE FROM knowledge_passages WHERE revision_id=?", (revision["id"],))
                conn.execute("UPDATE knowledge_revisions SET status='deleted',metadata_json='{}',rights_json='{}',extraction_json=NULL WHERE id=?", (revision["id"],))
                self._schedule_cleanup(conn, revision["id"], True)
            if note_delete:
                conn.execute("INSERT INTO knowledge_jobs(id,revision_id,idempotency_key,request_hash,state,phase,created_at,finished_at) "
                    "VALUES(?,?,?,?,?,?,?,?)", (durable_id("ingest"), expected_revision_id,
                    idempotency_key, delete_hash, "cancelled", "note-deleted", now, now))
                require_assistance(conn)
        pending = self.cleanup()
        return {"document_id": document_id, "status": "deleted", "cleanup_pending": bool(pending)}
