"""SQLite authority with staged, cancellable derived revisions."""
import asyncio
from datetime import datetime, timezone
from contextlib import ExitStack, closing, contextmanager, nullcontext
import hashlib
import json
from pathlib import Path
import re
import time
from threading import RLock

from ..contracts import ApiError, ContextScope, Scope, durable_id
from ..storage.database import utc_now
from ..storage.assessment_policy import require_assistance
from .engines import DoclingExtractor, FastEmbedEngine, LanceIndex, MAX_BYTES, MAX_PAGES, OfflineAssets
from .models import Rights, SourceMetadata, own_text_rights
from .office import OFFICE_MEDIA, validate_office
from .source_status import SourceStatusJournal
from .ownership import KnowledgeCapacity, NativeOwnership, exact_path_absent
from .original_io import RetainedOriginalIO, MAX_ORIGINAL_BYTES, CHUNK_BYTES

TERMINAL = {"ready", "failed", "cancelled"}
INDEX_BATCH = 64
CLEANUP_SWEEP = 64
RETRY_BASE_SECONDS = 1
RETRY_MAX_SECONDS = 300
MAINTENANCE_BATCHES = 32
MAINTENANCE_BYTES = 64 * 1024 ** 2
ORIGINAL_PUBLICATION_LIMIT = 64  # Matches migration 006's independent insert cap.
ORIGINAL_NATIVE_MAX_BYTES = MAX_ORIGINAL_BYTES  # Existing 64 MiB product contract, chunked on retained handles.
WAITING_ADMISSION_CODES = {'knowledge_low_space', 'knowledge_capacity_unavailable', 'index_owner_busy'}
# Shared by FIFO and priority selection; direct execution rechecks in its claim
# transaction. Canonical cleanup is also the fence after a portable restore.
QUEUE_CAPACITY_WAIT = ("EXISTS (SELECT 1 FROM knowledge_index_work w WHERE w.kind='maintenance' "
                       "AND w.target=j.revision_id AND w.retry_after>unixepoch('subsec'))")
QUEUED_JOB = ("j.state='queued' AND NOT EXISTS "
              "(SELECT 1 FROM knowledge_cleanup c WHERE c.revision_id=j.revision_id) AND NOT " + QUEUE_CAPACITY_WAIT)
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
    def __init__(self, services, *, extractor=None, embedder=None, index=None,
                 owner=None, capacity=None, maintenance_batches=MAINTENANCE_BATCHES,
                 maintenance_bytes=MAINTENANCE_BYTES):
        if any(type(value) is not int or value <= 0 for value in (maintenance_batches, maintenance_bytes)):
            raise ValueError('Maintenance thresholds must be positive integers')
        self.services, self.db, self.paths = services, services.db, services.paths
        self._owner = owner or NativeOwnership(self.paths.state / 'knowledge-native-owner')
        self._owner.acquire()  # Before reading selectors or admitting restore/native work.
        self._closed = False
        self._closing = False
        self._lock = RLock()
        self._ingest_lock = RLock()
        self._index_lock = RLock()
        self._active_ingestion = None
        self._retired_indexes = {}
        self._retirement_owners = {}
        self.maintenance_batches, self.maintenance_bytes = maintenance_batches, maintenance_bytes
        try:
            self.capacity = capacity or KnowledgeCapacity(filesystem=self._owner.fs)
            self.assets = OfflineAssets(services)
            self.extractor = extractor or DoclingExtractor(self.assets)
            self.embedder = embedder or FastEmbedEngine(self.assets)
            self.index = index or LanceIndex(self._selected_index_path())
            self._bind_index(self.index)
            self.source_status = SourceStatusJournal(self)
            self._recover_original_publications()  # Recorded paths only; never an orphan sweep.
        except BaseException:
            self._owner.close()  # No native operation has been admitted yet.
            raise
        # Services calls dependencies only after worker stop(None) and request
        # drain. Router stop(0)/observation timeout never releases this owner.
        self.services.on_shutdown_dependencies.append(self._shutdown_close)

    async def _shutdown_close(self):
        # Native Rust close, token release and retirement are synchronous and
        # may block. The shared Services task owns this thread to completion;
        # observer timeout/cancellation never releases or cancels its ownership.
        await asyncio.to_thread(self.close)

    def _bind_index(self, index):
        bind = getattr(index, 'bind_profile_owner', None)
        if callable(bind):
            bind(self._owner)

    def _require_open(self):
        if self._closed or self._closing:
            raise ApiError('index_close_pending', 'The Library is closing; wait for native work to settle', 503, True)
        self._owner.require()

    def close(self):
        """Real drain/close only. Failed retirement/native close keeps profile fenced."""
        if self._closed:
            return
        with self._ingest_lock:
            if self._closed:
                return
            if self._active_ingestion is not None:
                raise ApiError('recovery_busy', 'The Library still owns an import', 409, True)
            self._closing = True
            self._owner.seal()  # A bound native adapter cannot reopen during close.
            with self._index_lock, self._lock:
                # Do not release the profile while unresolved old native
                # resources/folders remain. Explicit close() retry must settle.
                pending = self._cleanup_index_generations()
                if pending:
                    raise ApiError('index_cleanup_pending', 'The Library still owns retired native resources', 503, True)
                self.index.close()
                self._owner.close()
                self._closed = True

    def _capacity_check(self, index=None, *, operation, growth_bytes=0, live_bytes=0):
        index = index or self.index
        forecast = self.capacity.preflight(index.path, operation=operation,
            growth_bytes=growth_bytes, live_bytes=live_bytes, measured_root=index.path)
        with self.db.transaction() as conn:
            self._work_in(conn, 'maintenance', 'passages', self._index_token(index))
            conn.execute("UPDATE knowledge_index_work SET measured_logical_bytes=?,measured_allocated_bytes=?,forecast_peak_bytes=? "
                         "WHERE kind='maintenance' AND target='passages' AND generation=?",
                         (forecast.logical_bytes, forecast.allocated_bytes, forecast.peak_bytes, self._index_token(index)))
        return forecast

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
                self._require_open()
                try:
                    yield
                finally:
                    # Restore imports canonical rows only. Keep this process's
                    # native owners, and reconstruct local debt instead of
                    # treating an imported selector/timer as cleanup authority.
                    if self.db.fetch_one("SELECT 1 FROM preferences WHERE key='knowledge.restore_dirty' AND value='true'"):
                        with self.db.transaction() as conn:
                            self.mark_index_dirty_in(conn, batch=False)
                            conn.execute("DELETE FROM knowledge_index_work WHERE kind='maintenance' AND target!='passages'")
        finally:
            self._ingest_lock.release()

    @staticmethod
    def _original_identity(info):
        identity = info.identity
        if hasattr(identity, 'volume') and hasattr(identity, 'file_id'):
            return [identity.volume, identity.file_id]
        return list(identity)  # Explicit portable test identity, not native authority.

    def _original_intent_update(self, revision_id, identities, phase):
        encoded = dumps(identities)
        if len(encoded) > 32768:
            raise ApiError('original_intent_limit', 'Original publication identity metadata exceeds its bounded record', 503, True)
        changed = self.db.execute("UPDATE knowledge_index_original_publications SET identities_json=?,phase=? WHERE revision_id=?",
                                  (encoded, phase, revision_id))
        if changed != 1:
            raise ApiError('original_intent_changed', 'Original publication intent needs recovery', 503, True)

    @contextmanager
    def _original_publication(self, *, document_id, revision_id, job_id, key, request_hash, digest, data, suffix):
        """Persist exact bounded intent before bytes; retain atomic creation handles.

        No file/tree disposal, inferred orphan adoption or all-stream authority.
        Canonical publication must clear this intent inside its own transaction.
        """
        if not 0 < len(data) <= ORIGINAL_NATIVE_MAX_BYTES:
            raise ApiError('original_publication_size_limit',
                'Original publication accepts nonempty inputs up to the existing 64 MiB file limit; preserve the source', 413)
        if any(not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', item) for item in (document_id, revision_id, job_id)):
            raise ApiError('unsafe_document_path', 'Original publication requires exact local record IDs', 409)
        fs = self._owner.fs
        root = Path(self.paths.library).absolute()
        folder = root / 'knowledge' / document_id / revision_id
        original = folder / ('original' + suffix)
        operation_id = hashlib.sha256(key.encode('utf-8')).hexdigest()
        intent_created = False
        try:
            with ExitStack() as claims:
                claims.enter_context(fs.guarded_roots([root]))
                ancestor, missing = folder.parent, [folder]
                while not fs.path_exists(ancestor):
                    missing.append(ancestor)
                    if ancestor == root:
                        raise ApiError('original_intent_unavailable', 'Original publication root needs recovery', 503, True)
                    ancestor = ancestor.parent
                claims.enter_context(fs.guarded_roots([ancestor]))
                identities = {'root': self._original_identity(fs.file_info(root)),
                              'parent': self._original_identity(fs.file_info(ancestor)),
                              'directories': {}, 'file': None}
                self.capacity.preflight(folder, operation='original', growth_bytes=len(data))
                try:
                    with self.db.transaction() as conn:
                        pending = conn.execute("SELECT request_sha256 FROM knowledge_index_original_publications WHERE operation_id=?", (operation_id,)).fetchone()
                        if pending:
                            if pending['request_sha256'] != request_hash:
                                raise ApiError('idempotency_conflict', 'That import key belongs to a different pending publication', 409)
                            raise ApiError('original_publication_pending',
                                'This import has a preserved original publication awaiting recovery; no new bytes were allocated', 503, True)
                        if conn.execute('SELECT COUNT(*) FROM knowledge_index_original_publications').fetchone()[0] >= ORIGINAL_PUBLICATION_LIMIT:
                            raise ApiError('original_publication_limit',
                                'The 64 pending original-publication slots are held. Review preserved attempts before importing more; no new bytes were allocated', 503, True)
                        conn.execute("INSERT INTO knowledge_index_original_publications VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                            (revision_id, document_id, job_id, operation_id, request_hash, str(root), str(ancestor),
                             str(original), digest, len(data), dumps(identities), 'prepared'))
                except ApiError:
                    raise
                except Exception:
                    raise ApiError('original_intent_unavailable',
                        'Original publication intent could not be persisted; no input bytes were allocated. Preserve the source and retry', 503, True) from None
                intent_created = True
                for directory in reversed(missing):
                    created = claims.enter_context(fs.created_directory(directory))
                    actual = fs.file_info(directory)
                    if not actual.directory or actual.identity != created.identity:
                        raise ApiError('original_identity_changed', 'Original publication namespace changed; preserved intent needs recovery', 503, True)
                    identities['directories'][str(directory)] = self._original_identity(created)
                    self._original_intent_update(revision_id, identities, 'creating')
                created = claims.enter_context(fs.created_file(original))
                identities['file'] = self._original_identity(created.info)
                self._original_intent_update(revision_id, identities, 'created')
                # The production wrapper never reopens a data path or duplicates
                # the claim. Explicit filesystem doubles supply their modeled I/O
                # adapter; there is no automatic unpinned/platform fallback.
                factory = getattr(fs, 'original_io', RetainedOriginalIO)
                with factory(fs, created, original) as io:
                    io.publish(data)
                    if io.sha256(expected_bytes=len(data)) != digest:
                        raise ApiError('original_identity_changed', 'Original publication bytes did not verify; preserve the input', 503, True)
                    self._original_intent_update(revision_id, identities, 'written')
                    yield original, dumps(identities)
        except BaseException:
            if intent_created:
                try:
                    # Never erase known identities when later recording fails.
                    # An abrupt process exit may leave an earlier phase; preintent
                    # still makes that uncertain interruption durably visible.
                    self.db.execute("UPDATE knowledge_index_original_publications SET phase='held' WHERE revision_id=?", (revision_id,))
                except Exception:
                    pass  # Previously committed intent remains; do not mask original failure.
            raise

    def _recover_original_publications(self):
        # Admission uses this same metadata lock: recovery must not classify an
        # original while its live retained writer is still publishing it.
        with self._lock:
            self._require_open()
            self._classify_original_publications()

    def _classify_original_publications(self):
        """Classify only recorded paths/identities; never adopt, replay or dispose."""
        fs = self._owner.fs
        rows = self.db.fetch_all('SELECT * FROM knowledge_index_original_publications ORDER BY revision_id LIMIT ?',
                                  (ORIGINAL_PUBLICATION_LIMIT + 1,))
        if len(rows) > ORIGINAL_PUBLICATION_LIMIT:
            raise ApiError('original_intent_limit', 'Original publication records exceed their finite recovery bound', 503, True)
        for row in rows:
            phase = 'held_uncertain'
            try:
                root = Path(self.paths.library).absolute()
                if any(not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', row[key]) for key in ('document_id', 'revision_id', 'job_id')):
                    raise ValueError('Uncertain recorded original IDs')
                if not re.fullmatch(r'[0-9a-f]{64}', row['sha256']) or not 0 < row['expected_bytes'] <= ORIGINAL_NATIVE_MAX_BYTES:
                    raise ValueError('Uncertain recorded original expectations')
                original = root / 'knowledge' / row['document_id'] / row['revision_id'] / Path(row['original_path']).name
                parent = Path(row['parent_path'])
                if '..' in parent.parts or not parent.is_absolute():
                    raise ValueError('Uncertain recorded ancestor path')
                if (str(root) != row['root_path'] or str(original) != row['original_path'] or
                        not parent.is_relative_to(root) or not original.parent.is_relative_to(parent) or
                        not re.fullmatch(r'original\.[a-z0-9]+', original.name)):
                    raise ValueError('Uncertain recorded original namespace')
                identities = json.loads(row['identities_json'])
                with ExitStack() as pins:
                    pins.enter_context(fs.guarded_roots([root, parent]))
                    if (self._original_identity(fs.file_info(root)) != identities['root'] or
                            self._original_identity(fs.file_info(parent)) != identities['parent']):
                        phase = 'held_changed'
                    else:
                        phase = 'held_matching'
                        for spelling, identity in identities['directories'].items():
                            directory = Path(spelling)
                            if not directory.is_relative_to(parent) or not original.parent.is_relative_to(directory):
                                phase = 'held_uncertain'
                                break
                            if not fs.path_exists(directory):
                                phase = 'held_missing'
                                break
                            pins.enter_context(fs.guarded_roots([directory]))
                            if self._original_identity(fs.file_info(directory)) != identity:
                                phase = 'held_changed'
                                break
                        if phase == 'held_matching':
                            if not fs.path_exists(original):
                                phase = 'held_missing'
                            elif identities['file'] is None:
                                phase = 'held_uncertain'  # Never adopt a crash-gap/racing file.
                            else:
                                retained = pins.enter_context(fs.opened_file(original))
                                if (self._original_identity(retained.info) != identities['file'] or
                                        retained.info.logical_bytes != row['expected_bytes'] or retained.info.links != 1):
                                    phase = 'held_changed'
                                else:
                                    factory = getattr(fs, 'original_io', RetainedOriginalIO)
                                    with factory(fs, retained, original) as io:
                                        if io.sha256(expected_bytes=row['expected_bytes']) != row['sha256']:
                                            phase = 'held_changed'
            except Exception:
                phase = 'held_uncertain'  # Reparse/access/missing ancestor is not disposal authority.
            self.db.execute('UPDATE knowledge_index_original_publications SET phase=? WHERE revision_id=?',
                            (phase, row['revision_id']))

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
        if exact_path_absent(self._owner.fs, path):
            return
        # No governed-birth/all-stream authority is implemented. Neither a
        # canonical name, a sidecar nor retained identity pins authorize wiping
        # unknown files or late ADS. Keep retirement debt and pins; do not drop a
        # pin to make pathname rmtree possible. Stream reclamation is pending.
        raise ApiError('index_cleanup_pending',
            'Retired Library bytes are preserved pending safe stream reclamation', 503, True)

    def _retire_index(self, token):
        """Close native resources, retaining exact pins/debt until safe reclamation."""
        self._owner.require()
        if token == self._index_token():
            raise ApiError('unsafe_index_path', 'The active Library generation cannot be retired', 409)
        path = self._index_folder(token)
        previous = self._retired_indexes.get(token)
        if token not in self._retirement_owners:
            if previous is None:
                if (exact_path_absent(self._owner.fs, path) and
                        exact_path_absent(self._owner.fs, path.parent / (path.name + '.native-owner'))):
                    return  # No retained resource or unknown token; no creation/adoption.
            else:
                if Path(previous.path).absolute() != Path(path).absolute():
                    raise ApiError('unsafe_index_path', 'Retained Library generation path changed', 409)
                settle = getattr(previous, 'retire_unopened_if_absent', None)
                if callable(settle) and settle():
                    self._retired_indexes.pop(token)
                    return  # Never-opened absence, not existing-byte reclamation.
        if exact_path_absent(self._owner.fs, path):
            # An empty pathname is never authority to close/release an unresolved
            # adapter, generation owner/pin or foreign sibling coordination token.
            raise ApiError('index_cleanup_pending', 'Absent Library generation has unresolved ownership', 503, True)
        prepare = getattr(previous, 'prepare_retirement', None)
        if callable(prepare):
            prepare()
        else:
            owner = self._retirement_owners.get(token)
            if owner is None:
                # Discoverable orphan/restart generations also need the exact
                # token. No inferred "process dead" ownership permits deletion.
                owner = NativeOwnership(path.parent / (path.name + '.native-owner'), filesystem=self._owner.fs)
                owner.acquire_for_path(path, create=False)
                self._retirement_owners[token] = owner
            if previous is not None:
                previous.close()
        self._remove_index_folder(path)
        if callable(prepare):
            previous.finish_retirement()
        owner = self._retirement_owners.get(token)
        if owner is not None:
            owner.close()
            del self._retirement_owners[token]
        self._retired_indexes.pop(token, None)

    @staticmethod
    def _work_in(conn, kind, target, generation):
        conn.execute("INSERT INTO knowledge_index_work(kind,target,generation) VALUES(?,?,?) "
                     "ON CONFLICT(kind,target,generation) DO NOTHING", (kind, target, generation))

    def _work_failed(self, kind, target, generation, code):
        with self.db.transaction() as conn:
            if kind == 'maintenance' and target != 'passages' and not conn.execute(
                    "SELECT 1 FROM knowledge_jobs WHERE revision_id=? AND state='queued' AND phase IN ('waiting_space','waiting_owner')",
                    (target,)).fetchone():
                return  # Cancellation/replacement may have won after the wait was recorded.
            self._work_in(conn, kind, target, generation)
            attempts = conn.execute("SELECT attempts FROM knowledge_index_work WHERE kind=? AND target=? AND generation=?",
                                    (kind, target, generation)).fetchone()[0] + 1
            delay = min(RETRY_MAX_SECONDS, RETRY_BASE_SECONDS * 2 ** min(attempts - 1, 20))
            conn.execute("UPDATE knowledge_index_work SET attempts=?,retry_after=?,error_code=? "
                         "WHERE kind=? AND target=? AND generation=?",
                         (attempts, time.time() + delay, code, kind, target, generation))

    def mark_index_dirty_in(self, conn, generation=None, *, growth_bytes=0, batch=True):
        """Caller owns _index_lock; commit debt BEFORE every append/delete/FTS."""
        generation = generation or self._index_token()
        self._work_in(conn, 'maintenance', 'passages', generation)
        conn.execute("UPDATE knowledge_index_work SET dirty_sequence=dirty_sequence+1,pending_batches=pending_batches+?,"
                     "pending_bytes=pending_bytes+? WHERE kind='maintenance' AND target='passages' AND generation=?",
                     (int(batch), growth_bytes, generation))

    def _maintain_index(self, *, force=False, queue_drained=False):
        """One attempt per bounded operation boundary, with durable retry/backoff.

        The index lock serializes mutations across the dirty-sequence snapshot;
        the native lifetime tokens (not this RLock) authorize reclamation.
        """
        generation = self._index_token()
        debt = self.db.fetch_one("SELECT * FROM knowledge_index_work WHERE kind='maintenance' AND target='passages' AND generation=? "
                                 "AND dirty_sequence>completed_sequence", (generation,))
        if not debt or (not force and debt['retry_after'] > time.time()):
            return
        due = (force or queue_drained or debt['attempts'] > 0 or
               debt['pending_batches'] >= self.maintenance_batches or debt['pending_bytes'] >= self.maintenance_bytes)
        if not due:
            return
        try:
            self._owner.require()
            self._capacity_check(operation='maintenance')
            self.index.optimize()
            self.db.execute("UPDATE knowledge_index_work SET completed_sequence=?,pending_batches=0,pending_bytes=0,"
                            "attempts=0,retry_after=0,error_code=NULL WHERE kind='maintenance' AND target='passages' AND generation=?",
                            (debt['dirty_sequence'], generation))
        except Exception as error:
            code = error.code if isinstance(error, ApiError) else 'index_maintenance_pending'
            self._work_failed('maintenance', 'passages', generation, code)

    def _cleanup_index_generations(self, *, force=True):
        active = self._index_token()
        candidates = {"knowledge", *self._retired_indexes, *self._retirement_owners}
        for folder, pattern in (("knowledge-generations", r"index_[0-9a-f]{32}"),
                                ("k", r"[0-9a-f]{32}")):
            generations = self.paths.indexes / folder
            if generations.is_dir() and not generations.is_symlink() and not generations.is_junction():
                candidates.update(folder + "/" + path.name for path in generations.iterdir()
                                  if re.fullmatch(pattern, path.name))
        with self.db.transaction() as conn:
            for token in candidates - {active}:
                if token in self._retired_indexes or token in self._retirement_owners or self._index_folder(token).exists():
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
                self._retire_index(token)
                with self.db.transaction() as conn:
                    conn.execute("DELETE FROM knowledge_index_work WHERE generation=? AND kind IN ('retirement','maintenance','removal')", (token,))
            except Exception:
                self._work_failed("retirement", token, task["generation"], "index_cleanup_pending")
        return self.db.fetch_all("SELECT target AS generation,error_code FROM knowledge_index_work WHERE kind='retirement'")

    def maintenance_status(self):
        debt = self.db.fetch_one("SELECT * FROM knowledge_index_work WHERE kind='maintenance' AND target='passages' AND generation=?",
                                 (self._index_token(),))
        removal = self.db.fetch_one("SELECT COUNT(*) AS n FROM knowledge_cleanup")['n']
        work = self.db.fetch_all("SELECT kind,target,generation,error_code,retry_after FROM knowledge_index_work WHERE "
            "kind IN ('removal','retirement','publication') OR (kind='maintenance' AND "
            "(target!='passages' OR dirty_sequence>completed_sequence)) "
            "ORDER BY retry_after,CASE kind WHEN 'removal' THEN 0 WHEN 'retirement' THEN 1 ELSE 2 END,target,generation")
        failed = next((row for row in work if row['error_code']), None)
        original = self.db.fetch_one("SELECT COUNT(*) AS n FROM knowledge_cleanup c JOIN knowledge_index_work w "
            "ON w.kind='removal' AND w.target=c.revision_id AND w.generation=? "
            "WHERE c.remove_original=1 AND w.completed_sequence=1", (self._index_token(),))['n']
        publications = {row['phase']: row['n'] for row in self.db.fetch_all(
            'SELECT phase,COUNT(*) AS n FROM knowledge_index_original_publications GROUP BY phase ORDER BY phase')}
        publication_count = sum(publications.values())
        return {'pending': bool(removal or work or publication_count),
                'original_publication_pending': publication_count,
                'original_publication_limit': ORIGINAL_PUBLICATION_LIMIT,
                'original_publication_max_bytes': ORIGINAL_NATIVE_MAX_BYTES,
                'original_publication_chunk_bytes': CHUNK_BYTES,
                'original_publication_admission_held': publication_count >= ORIGINAL_PUBLICATION_LIMIT,
                'original_publication_states': publications,
                'removal_pending': removal,
                'retirement_pending': sum(row['kind'] == 'retirement' for row in work),
                'original_pending': original,
                'error_code': failed['error_code'] if failed else ('original_publication_pending' if publication_count else None),
                'retry_after': failed['retry_after'] if failed else (work[0]['retry_after'] if work else 0),
                'pending_batches': debt['pending_batches'] if debt else 0,
                'estimated_growth_bytes': debt['pending_bytes'] if debt else 0,
                'measured_logical_bytes': debt['measured_logical_bytes'] if debt else 0,
                'measured_allocated_bytes': debt['measured_allocated_bytes'] if debt else 0,
                'forecast_peak_bytes': debt['forecast_peak_bytes'] if debt else 0}

    def _pending_index_work(self):
        pending = self.db.fetch_all("SELECT revision_id,error_code FROM knowledge_cleanup")
        pending += self.db.fetch_all("SELECT generation,COALESCE(error_code,'index_cleanup_pending') AS error_code "
                                     "FROM knowledge_index_work WHERE kind='retirement' OR "
                                     "(kind='maintenance' AND dirty_sequence>completed_sequence)")
        pending += self.db.fetch_all("SELECT revision_id,'original_publication_pending' AS error_code "
                                    "FROM knowledge_index_original_publications ORDER BY revision_id LIMIT ?",
                                    (ORIGINAL_PUBLICATION_LIMIT,))
        return pending

    def rebuild_index(self):
        """Stage canonical eligible passages, validate, then atomically select them."""
        with self._ingest_lock, self._index_lock, self._lock:
            self._require_open()
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
            # Forecast before constructing/copying a candidate, preserving the
            # selected ready generation and canonical records on low space.
            live = self.db.fetch_one("SELECT COALESCE(SUM(length(CAST(context_text AS BLOB))+?+256),0) AS n FROM knowledge_passages",
                                     (4 * self.embedder.dimensions,))['n']
            self.capacity.preflight(self.paths.indexes, operation='rebuild', live_bytes=live,
                                    measured_root=self.index.path)
            generation = durable_id("index")
            candidate = LanceIndex(self._generation_path(generation), self.embedder.dimensions)
            self._bind_index(candidate)
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
                        growth = self.capacity.rows_bytes(rows)
                        self._capacity_check(candidate, operation='rebuild', growth_bytes=growth, live_bytes=live)
                        with self.db.transaction() as conn:
                            self.mark_index_dirty_in(conn, self._index_token(candidate), growth_bytes=growth)
                        candidate.stage(rows, create_fts=False)
                        identities.update((row["passage_id"], row["revision_id"], row["document_id"]) for row in rows)
                if identities:
                    self._prepare_fts(candidate)
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
                    self._cleanup_index_generations()
                    self._maintain_index(force=True)
                    pending = self._pending_index_work()
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
                        self._retire_index(token)
                        self.db.execute("DELETE FROM knowledge_index_work WHERE generation=? AND kind IN ('maintenance','removal','retirement')", (token,))
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
            self._require_open()
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
            with self._original_publication(document_id=document_id, revision_id=revision_id,
                    job_id=job_id, key=key, request_hash=request_hash, digest=digest, data=data, suffix=suffix) as (original, identities_json):
                with self.db.transaction() as conn:
                    intent = conn.execute("SELECT * FROM knowledge_index_original_publications WHERE revision_id=?", (revision_id,)).fetchone()
                    if (not intent or intent['identities_json'] != identities_json or intent['phase'] != 'written' or
                            intent['document_id'] != document_id or intent['job_id'] != job_id or
                            intent['operation_id'] != hashlib.sha256(key.encode('utf-8')).hexdigest() or
                            intent['request_sha256'] != request_hash or intent['sha256'] != digest or
                            intent['expected_bytes'] != len(data) or intent['original_path'] != str(original)):
                        raise ApiError('original_intent_changed', 'Original publication intent changed before canonical commit', 503, True)
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
                    # Clearing intent and canonical publication are one commit;
                    # rollback restores the exact written intent, never orphan bytes.
                    conn.execute('DELETE FROM knowledge_index_original_publications WHERE revision_id=?', (revision_id,))
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
        maintenance = self.db.fetch_one("SELECT 1 FROM knowledge_index_work WHERE kind='maintenance' AND generation=? "
                                        "AND dirty_sequence>completed_sequence", (self._index_token(),))
        return {"document_id": revision["document_id"], "revision_id": job["revision_id"],
                "status": job["state"], "job": job, "maintenance_pending": bool(maintenance)}

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
            self._require_open()
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
                    waiting = code in WAITING_ADMISSION_CODES
                    state = 'queued' if waiting else 'failed'
                    phase = ('waiting_owner' if code == 'index_owner_busy' else 'waiting_space') if waiting else 'failed'
                    conn.execute("UPDATE knowledge_jobs SET state=?,phase=?,error_code=?,error_message=?,finished_at=? WHERE id=?",
                                 (state, phase, code, message, None if waiting else utc_now(), job_id))
                    conn.execute("UPDATE knowledge_revisions SET status=? WHERE id=?", (state, revision['id']))
                    self._schedule_cleanup(conn, revision['id'], not waiting)
            if code in WAITING_ADMISSION_CODES:
                # This target is a local queue retry timer, NOT passage debt or a
                # removal acknowledgement. Explicit run_job retries immediately.
                self._work_failed('maintenance', revision['id'], self._index_token(), code)
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
                growth = self.capacity.rows_bytes(rows)
                self._capacity_check(operation='stage', growth_bytes=growth)
                with self._lock, self.db.transaction() as conn:
                    if not self._guard(conn, job_id):
                        return
                    self.mark_index_dirty_in(conn, growth_bytes=growth)
                self.index.stage(rows, create_fts=False)
                # A long single document or endless queue cannot defer due work
                # until eventual idle. This boundary holds no SQLite write txn.
                self._maintain_index()
        # Prepare potentially large JSON before entering the publication lock.
        stored = [(p["id"], revision["id"], i, p["text"], p["context_text"],
                   dumps(p["locators"]), dumps(p["headings"])) for i, p in enumerate(passages)]
        extraction_json = dumps(extracted.document)
        with self._index_lock:
            with self._lock, self.db.transaction() as conn:
                if not self._guard(conn, job_id):
                    return
            if passages and not document["reserved"]:
                self._prepare_fts(self.index)
            with self._lock, self.db.transaction() as conn:
                if not self._guard(conn, job_id):
                    self._schedule_cleanup(conn, revision["id"], True)
                    return
                previous = conn.execute("SELECT active_revision FROM knowledge_documents WHERE id=?", (document["id"],)).fetchone()[0]
                conn.executemany("INSERT INTO knowledge_passages VALUES(?,?,?,?,?,?,?)", stored)
                now = utc_now()
                conn.execute("UPDATE knowledge_revisions SET status='ready',extraction_json=?,embedding_model=?,chunk_tokens=?,activated_at=? WHERE id=?", (extraction_json, self.embedder.model_id, self.embedder.max_tokens, now, revision["id"]))
                conn.execute("UPDATE knowledge_documents SET active_revision=?,updated_at=? WHERE id=?", (revision["id"], now, document["id"]))
                conn.execute("UPDATE knowledge_jobs SET state='ready',phase='complete',error_code=NULL,error_message=NULL,finished_at=? WHERE id=?", (now, job_id))
                conn.execute("DELETE FROM knowledge_index_work WHERE kind='maintenance' AND target=?", (revision['id'],))
                if previous and previous != revision["id"]:
                    self._schedule_cleanup(conn, previous, False)

    def _prepare_fts(self, index):
        discover = getattr(index, 'has_fts', None)
        if (callable(discover) and discover()) or getattr(index, '_fts_ready', False):
            return
        self._capacity_check(index, operation='fts')
        with self.db.transaction() as conn:
            self.mark_index_dirty_in(conn, self._index_token(index), batch=False)
        index.build_fts()  # Native adapter checks persisted index metadata on reopen.

    def _schedule_cleanup(self, conn, revision_id, remove_original):
        # A saved note revision is an immutable original even when its derived
        # extraction is cancelled or fails. Explicit owner deletion still
        # upgrades durable disposition intent; bytes stay pending until safe
        # governed stream reclamation is available.
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
        # Admission timers belong only to live queued retries, not destructive
        # cleanup. Keep removal/native maintenance debt independently.
        conn.execute("DELETE FROM knowledge_index_work WHERE kind='maintenance' AND target=? AND "
                     "NOT EXISTS(SELECT 1 FROM knowledge_jobs WHERE revision_id=? AND state IN ('queued','processing'))",
                     (revision_id, revision_id))
        conn.execute("INSERT INTO knowledge_cleanup(revision_id,remove_original,created_at) VALUES(?,?,?) "
            "ON CONFLICT(revision_id) DO UPDATE SET remove_original=CASE WHEN ? THEN 0 "
            "ELSE MAX(remove_original,excluded.remove_original) END",
            (revision_id, int(remove_original), utc_now(), int(retain_note)))
        self._work_in(conn, 'removal', revision_id, self._index_token())

    def _cancel_in(self, conn, job_id, revision_id, reason):
        conn.execute("UPDATE knowledge_jobs SET state='cancelled',phase=?,finished_at=? WHERE id=? AND state IN ('queued','processing')", (reason, utc_now(), job_id))
        conn.execute("UPDATE knowledge_revisions SET status='cancelled' WHERE id=? AND status IN ('queued','processing')", (revision_id,))
        self._schedule_cleanup(conn, revision_id, True)

    def cancel_job(self, job_id):
        with self._lock, self.db.transaction() as conn:
            self._require_open()
            job = conn.execute("SELECT * FROM knowledge_jobs WHERE id=?", (job_id,)).fetchone()
            if not job:
                raise ApiError("job_missing", "Import job was not found", 404)
            if job["state"] not in TERMINAL:
                self._cancel_in(conn, job_id, job["revision_id"], "cancelled")
        self.cleanup()
        return self.get_job(job_id)

    def cleanup(self, *, force=True, queue_drained=False):
        """Bounded cleanup; explicit retry bypasses backoff, worker uses due work.

        Removal acknowledgement and fragment maintenance are separate. A native
        optimize failure cannot leave destructive cleanup aimed at a later retry.
        """
        if not self._index_lock.acquire(blocking=False):
            return self._pending_index_work()
        try:
            self._require_open()
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
                        # Delete appends native manifests/versions too. Forecast
                        # before the SDK mutation, outside the canonical writer;
                        # dirty intent was already committed above.
                        self._capacity_check(operation='removal')
                        self.index.remove(revision_id)
                        # Native delete acknowledgement precedes file cleanup.
                        with self.db.transaction() as conn:
                            conn.execute("UPDATE knowledge_index_work SET completed_sequence=1,error_code=NULL "
                                         "WHERE kind='removal' AND target=? AND generation=?", (revision_id, generation))
                    if task["remove_original"]:
                        # Canonical original_path is not all-stream authority or
                        # proof that a renamed original is truly absent. Preserve
                        # the original reference, unknown siblings/replacements
                        # and named streams until governed reclamation exists.
                        # Native row-removal acknowledgement remains independent.
                        raise ApiError('original_cleanup_pending',
                            'Original Library disposition needs safe stream reclamation', 503, True)
                    with self._lock, self.db.transaction() as conn:
                        if task["remove_original"]:
                            conn.execute("UPDATE knowledge_revisions SET original_path=NULL,extraction_json=NULL WHERE id=?", (revision_id,))
                        # A delete can upgrade a task while native removal runs.
                        conn.execute("DELETE FROM knowledge_cleanup WHERE revision_id=? AND remove_original=?", (revision_id, task["remove_original"]))
                        if not conn.execute("SELECT 1 FROM knowledge_cleanup WHERE revision_id=?", (revision_id,)).fetchone():
                            conn.execute("DELETE FROM knowledge_index_work WHERE kind='removal' AND target=?", (revision_id,))
                except Exception as error:
                    code = error.code if isinstance(error, ApiError) else 'cleanup_pending'
                    self.db.execute("UPDATE knowledge_cleanup SET error_code=? WHERE revision_id=?", (code, revision_id))
                    self._work_failed("removal", revision_id, generation, code)
            self._maintain_index(force=force, queue_drained=queue_drained)
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
                self._require_open()
                # Reconstruct unknown/legacy local history after a process loss
                # without importing ownership or trusting portable retry timers.
                if self.index.path.exists() and not conn.execute(
                        "SELECT 1 FROM knowledge_index_work WHERE kind='maintenance' AND target='passages' AND generation=?",
                        (self._index_token(),)).fetchone():
                    self.mark_index_dirty_in(conn, batch=False)
                conn.execute("DELETE FROM knowledge_index_work WHERE kind='maintenance' AND target!='passages' AND "
                             "(generation!=? OR NOT EXISTS(SELECT 1 FROM knowledge_jobs j WHERE j.revision_id=target "
                             "AND j.state='queued' AND j.phase IN ('waiting_space','waiting_owner')))", (self._index_token(),))
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
            self._recover_original_publications()
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
            self._require_open()
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
            self._require_open()
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
