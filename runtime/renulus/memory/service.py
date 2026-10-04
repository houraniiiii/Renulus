"""Durable capture/recovery and rebuildable, revision-filtered learner recall."""
import asyncio
from contextlib import closing, contextmanager
import shutil
import threading
from pathlib import Path

from renulus.contracts import ApiError, ContextScope, durable_id

from .engine import Mem0Index, bootstrap, embedding_config
from .models import require_eligible
from .repository import MemoryRepository


class MemoryService:
    def __init__(self, services, *, index_factory=Mem0Index):
        self.services, self.db = services, services.db
        self.repository = MemoryRepository(services)
        self.root = services.paths.owned('indexes/learner-memory')
        self.index_factory = index_factory
        self._engine = self._embedding = None
        self._lock = threading.RLock()
        self._process_lock = asyncio.Lock()
        self._wake = asyncio.Event()
        self._worker = self._loop = None
        self._active_runs = set()
        self._capture_state = threading.RLock()
        self._recovery_paused = False
        self._stopping = False
        # Reindex on restart; no index file is a record authority. This also
        # reconciles deletion markers from restores before any recall.
        self.db.execute("UPDATE memory_index_state SET state='dirty' WHERE singleton=1")

    def notify(self):
        if self._loop and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._wake.set)

    def add(self, request):
        with self._canonical_mutation():
            result = self.repository.add(request)
        self.notify()
        return result

    @contextmanager
    def _canonical_mutation(self):
        with self._capture_state:
            if self._recovery_paused:
                raise ApiError('recovery_busy', 'Wait for learner-memory backup or restore to finish', 409, True)
            yield

    @contextmanager
    def recovery_guard(self):
        # Claim/pause bookkeeping is brief. Do not hold a thread lock across
        # remote inference or block the event loop during a ZIP operation.
        with self._capture_state:
            if self._recovery_paused or self._active_runs:
                raise ApiError('recovery_busy', 'Finish or cancel active learner-memory capture before backup or restore', 409, True)
            self._recovery_paused = True
        try:
            with self._lock:
                yield
        finally:
            with self._capture_state:
                self._recovery_paused = False
            self.notify()

    def _remove(self, path):
        target, root = Path(path).resolve(), self.root.resolve()
        if target == root or not target.is_relative_to(root):
            raise ApiError('memory_index_path', 'The memory cleanup path leaves its profile', 503)
        if target.exists():
            shutil.rmtree(target)

    def _purge(self):
        # Close the local Qdrant owner before removing Windows files. Whole
        # derived generations remove old payloads as well as live vector rows.
        with self._lock:
            if self._engine:
                self._engine.close()
                self._engine = None
            if self.root.exists():
                for path in self.root.iterdir():
                    if path.is_dir():
                        self._remove(path)
            with self.db.transaction() as conn:
                conn.execute('DELETE FROM memory_index_entries')
                conn.execute("UPDATE memory_index_state SET generation=NULL,state='dirty' WHERE singleton=1")

    def _purge_result(self, result):
        self._cancel_retired_jobs()
        try:
            self._purge()
            # secure_delete handles pages; truncate WAL so superseded text isn't
            # retained in an app-owned log after correction/history removal.
            with closing(self.db.connect()) as conn:
                checkpoint = conn.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()
                if checkpoint[0]:
                    raise ApiError('memory_purge_pending', 'Memory cleanup must finish after active readers close', 503, True)
            pending = False
        except (OSError, ApiError):
            self.db.execute("UPDATE memory_index_state SET state='failed',error_code='memory_purge_pending' WHERE singleton=1")
            pending = True
        self.notify()
        return {**result, 'purge_pending': pending}

    def _cancel_retired_jobs(self):
        provider = self.services.registry.get('provider')
        if not provider or not self._loop or self._loop.is_closed():
            return
        identifiers = [row['id'] for row in self.db.fetch_all(
            "SELECT id FROM memory_jobs WHERE state='cancelled'") if row['id'] in self._active_runs]
        async def cancel_runs():
            for identifier in identifiers:
                try:
                    await provider.cancel(identifier)
                except Exception:
                    pass  # The canonical state guard still excludes late results.
        if identifiers:
            asyncio.run_coroutine_threadsafe(cancel_runs(), self._loop)

    def edit(self, identifier, text, revision):
        with self._canonical_mutation():
            result = self.repository.edit(identifier, text, revision)
        purged = self._purge_result(result)
        return {**self.repository.get(identifier), 'purge_pending': purged['purge_pending']}

    def delete(self, identifier, revision):
        with self._canonical_mutation():
            result = self.repository.delete(identifier, revision)
        return self._purge_result(result)

    def purge_history(self, identifier):
        with self._canonical_mutation():
            result = self.repository.purge_history(identifier)
        return self._purge_result(result)

    def enqueue(self, evidence_id, scope):
        with self._canonical_mutation():
            result = self.repository.enqueue(evidence_id, scope)
        self.notify()
        return result

    async def cancel(self, identifier):
        job = self.repository.cancel(identifier)
        if job['state'] == 'cancelled':
            provider = self.services.registry.get('provider')
            if provider:
                await provider.cancel(identifier)
        return job

    def _get_embedding(self):
        with self._lock:
            config = embedding_config(self.services)
            if self._embedding is None or self._embedding.config['fingerprint'] != config['fingerprint']:
                bootstrap(self.services)
                from .providers import OfflineEmbedding
                self._embedding = OfflineEmbedding(config)
            return self._embedding

    def _extract(self, job, material, loop):
        # Extraction gets its own disposable derived namespace, never the live
        # recall index. Only durable general evidence can reach this function.
        path = self.root / durable_id('capture')
        engine = None
        try:
            embedding = self._get_embedding()
            engine = self.index_factory(self.services, path, embedding, transient=True)
            binding = {'services': self.services, 'loop': loop, 'scope': material['scope'],
                       'run_id': job['id'], 'current': lambda: self.repository.current(job)}
            return engine.extract(material['text'], binding)
        finally:
            if engine:
                engine.close()
            self._remove(path)

    async def process_pending(self, *, retry=False):
        if self._loop is None:
            self._loop = asyncio.get_running_loop()
        async with self._process_lock:
            with self._capture_state:
                if self._recovery_paused:
                    return {'processed': 0}
                if retry:
                    self.repository.retry()
                self.repository.scan()
                queued = self.db.fetch_all("SELECT id FROM memory_jobs WHERE state='queued' ORDER BY created_at LIMIT 100")
            processed = 0
            for row in queued:
                with self._capture_state:
                    if self._stopping or self._recovery_paused:
                        break
                    job = self.repository.claim(row['id'])
                    if not job:
                        continue
                    self._active_runs.add(job['id'])
                try:
                    if not self.repository.current(job):
                        self.repository.cancel(job['id'])
                        continue
                    scope = ContextScope.model_validate_json(job['scope'])
                    material = self.repository.material(job['evidence_id'], scope)
                    # Structured assessment/interest records need no generated
                    # claim. General points use real Mem0 extraction through F0.
                    if material['infer']:
                        texts = await asyncio.to_thread(self._extract, job, material, asyncio.get_running_loop())
                    else:
                        texts = [material['text']]
                    self.repository.commit_capture(job, material, texts)
                    processed += 1
                except asyncio.CancelledError:
                    self.repository.cancel(job['id'])
                    provider = self.services.registry.get('provider')
                    if provider:
                        await provider.cancel(job['id'])
                    raise
                except Exception as error:
                    code = error.code if isinstance(error, ApiError) else 'memory_capture_failed'
                    self.repository.fail(job['id'], code)
                finally:
                    with self._capture_state:
                        self._active_runs.discard(job['id'])
            state = self.db.fetch_one('SELECT state FROM memory_index_state WHERE singleton=1')['state']
            if state in ('dirty', 'empty') or retry:
                try:
                    await asyncio.to_thread(self.reindex)
                except ApiError:
                    pass  # Canonical captures remain available; retry repairs the derivative.
            return {'processed': processed}

    def reindex(self):
        with self._lock:
            old = self.db.fetch_one('SELECT * FROM memory_index_state WHERE singleton=1')
            generation, engine = durable_id('generation'), None
            path = self.root / generation
            try:
                embedding = self._get_embedding()
                rows = self.repository.list()
                engine = self.index_factory(self.services, path, embedding)
                entries = [(row['id'], row['revision'], engine.add(row), generation) for row in rows]
                # Mem0 history/messages are derivative copies, never canonical
                # learner history. Remove them even after a successful rebuild.
                engine.purge_history()
                with self.db.transaction() as conn:
                    current = conn.execute('SELECT epoch FROM memory_index_state WHERE singleton=1').fetchone()
                    if current[0] != old['epoch']:
                        raise ApiError('memory_reindex_superseded', 'Memory changed while rebuilding. Retry the index', 409, True)
                    conn.execute('DELETE FROM memory_index_entries')
                    conn.executemany('INSERT INTO memory_index_entries VALUES(?,?,?,?)', entries)
                    conn.execute("UPDATE memory_index_state SET generation=?,fingerprint=?,state='ready',error_code=NULL WHERE singleton=1",
                                 (generation, embedding.config['fingerprint']))
                if self._engine:
                    self._engine.close()
                self._engine = engine
                engine = None
                # Retain the previous active generation until the new one is
                # validated and the epoch-guarded switch commits. Then physically
                # remove it and any crash leftovers before reporting ready.
                for candidate in self.root.iterdir():
                    if candidate.is_dir() and candidate.name != generation and not candidate.name.startswith('capture_'):
                        self._remove(candidate)
                return {'ready': True, 'count': len(rows), 'generation': generation}
            except Exception as error:
                if engine:
                    engine.close()
                if engine is not None or not self._engine or self._engine.path != path:
                    self._remove(path)
                code = error.code if isinstance(error, ApiError) else 'memory_reindex_failed'
                # A concurrent edit leaves state dirty; do not overwrite its epoch.
                self.db.execute("UPDATE memory_index_state SET state='failed',error_code=? WHERE singleton=1 AND epoch=?",
                                (code, old['epoch']))
                if isinstance(error, ApiError):
                    raise
                raise ApiError(code, 'The memory index could not be rebuilt. Retry after checking the offline helpers', 503, True) from None

    def retrieve(self, query, *, scope: ContextScope, limit=10, budget_chars=4000, topic_id=None):
        require_eligible(scope)
        with self._lock:
            state = self.db.fetch_one('SELECT * FROM memory_index_state WHERE singleton=1')
            if state['state'] != 'ready' or self._engine is None:
                self.reindex()
            config = embedding_config(self.services)
            state = self.db.fetch_one('SELECT * FROM memory_index_state WHERE singleton=1')
            if config['fingerprint'] != state['fingerprint']:
                raise ApiError('memory_embedding_incompatible', 'Rebuild memory for the current offline helper', 503, True)
            hits = self._engine.search(query, min(100, limit * 3))
            records, context, seen = [], '', set()
            with self.db.transaction() as conn:
                for hit in hits:
                    entry = conn.execute(
                        'SELECT f.* FROM memory_index_entries e JOIN memory_facts f ON f.id=e.record_id '
                        'WHERE e.engine_id=? AND e.generation=? AND e.revision=f.revision',
                        (hit['id'], state['generation'])).fetchone()
                    if not entry or entry['id'] in seen or conn.execute(
                            "SELECT 1 FROM deletion_ledger WHERE entity_type='memory_fact' AND entity_id=?",
                            (entry['id'],)).fetchone() or (topic_id and entry['topic_id'] not in (None, topic_id)):
                        continue
                    record = self.repository._view(dict(entry))
                    # Derived model text never replaces the canonical revision.
                    line = f"[{record['id']} r{record['revision']}] {record['text']}\n"
                    if len(context) + len(line) > budget_chars:
                        continue
                    seen.add(record['id'])
                    context += line
                    records.append(record)
                    if len(records) == limit:
                        break
            return {'records': records, 'context': context, 'producer': 'mem0-oss'}

    def status(self):
        state = self.db.fetch_one('SELECT * FROM memory_index_state WHERE singleton=1')
        pending = self.db.fetch_one("SELECT count(*) n FROM memory_jobs WHERE state IN ('queued','running','failed')")['n']
        try:
            embedding_config(self.services)
            helper_ready, message = True, None
        except ApiError as error:
            helper_ready, message = False, error.message
        return {'index': {'ready': state['state'] == 'ready', 'state': state['state'],
                          'helper_ready': helper_ready, 'error_code': state['error_code'], 'message': message},
                'pending_jobs': pending, 'producer': 'mem0-oss', 'automatic_capture': True}

    async def start(self):
        self._loop = asyncio.get_running_loop()
        self._worker = asyncio.create_task(self._run(), name='renulus-memory-outbox')

    async def _run(self):
        while not self._stopping:
            self._wake.clear()
            try:
                await self.process_pending()
            except asyncio.CancelledError:
                raise
            except Exception:
                # Never log evidence or exception bodies. The outbox retains work.
                pass
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=2)
            except TimeoutError:
                pass

    async def close(self):
        self._stopping = True
        if self._worker:
            self._worker.cancel()
            try:
                await self._worker
            except asyncio.CancelledError:
                pass
        with self._lock:
            if self._engine:
                self._engine.close()
                self._engine = None
            self._embedding = None
