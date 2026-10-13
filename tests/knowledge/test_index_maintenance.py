"""Tiny #26 product regressions; engine doubles are NOT LanceDB growth evidence."""
from pathlib import Path

import pytest

from renulus.knowledge.repository import KnowledgeRepository
from renulus.services import Services
from renulus.storage import AppPaths, Database
from test_repository import SyntheticEmbedder, SyntheticExtractor
from test_storage_reliability import FaultIndex, SyntheticFilesystem, synthetic_owner, synthetic_index, close_synthetic_fixture
from renulus.knowledge.ownership import KnowledgeCapacity, MIN_FREE_BYTES
from renulus.contracts import ApiError
from renulus.knowledge.worker import IngestionWorker
from renulus.knowledge.priority_queue import LibraryPriorityQueue


class MaintenanceIndex(FaultIndex):
    def __init__(self, path, dimensions=384):
        super().__init__(path, dimensions)
        self.fts_calls = 0
        self.before_stage = lambda: None

    def stage(self, rows, **kwargs):
        self.before_stage()
        super().stage(rows, **kwargs)

    def build_fts(self):
        self.fts_calls += 1


@pytest.fixture
def repository(tmp_path):
    paths = AppPaths.create(tmp_path / 'profile')
    db = Database(paths.database)
    module = Path(__file__).parents[2] / 'runtime/renulus/knowledge'
    db.apply_migration('knowledge-001', (module / 'schema.sql').read_text())
    for migration in sorted((module / 'migrations').glob('*.sql')):
        db.apply_migration('knowledge-' + migration.stem, migration.read_text())
    fs = SyntheticFilesystem()
    repo = KnowledgeRepository(Services(paths, db), extractor=SyntheticExtractor(),
        embedder=SyntheticEmbedder(), index=MaintenanceIndex(paths.indexes / 'knowledge'),
        owner=synthetic_owner(paths.state / 'knowledge-native-owner', fs), capacity=KnowledgeCapacity(filesystem=fs))
    yield repo
    repo.index.fail_close = False
    fs.fail_release = False
    for index in repo._retired_indexes.values():
        index.fail_close = False
    close_synthetic_fixture(repo)


def test_append_records_dirty_before_native_write(repository):
    repo = repository
    def assert_dirty():
        debt = repo.db.fetch_one("SELECT * FROM knowledge_index_work WHERE kind='maintenance'")
        assert debt and debt['dirty_sequence'] > debt['completed_sequence']
        assert repo.db._active_writers == 0
    repo.index.before_stage = assert_dirty
    assert repo.import_text('Synthetic dialysis addition')['status'] == 'ready'


def test_continuous_queue_attempts_coalesced_maintenance(repository):
    repo = repository
    items = [repo.import_text('Synthetic transplant addition', process=False) for _ in range(34)]
    for item in items[:31]:
        assert repo.run_job(item['job']['id'])['state'] == 'ready'
    assert repo.index.optimizations == 0
    assert repo.run_job(items[31]['job']['id'])['state'] == 'ready'
    assert repo.index.optimizations == 1
    assert repo.next_queued_job() is not None


def test_queue_drain_maintains_append_debt(repository):
    repo = repository
    assert repo.import_text('Synthetic anemia addition')['status'] == 'ready'
    assert repo.index.optimizations == 0  # No per-document full optimize.
    assert repo.cleanup(force=False, queue_drained=True) == []
    assert repo.index.optimizations == 1
    work = repo.db.fetch_one("SELECT * FROM knowledge_index_work WHERE kind='maintenance'")
    assert work and work['dirty_sequence'] == work['completed_sequence']


def test_fts_created_once_and_discovered_on_reopen(tmp_path, monkeypatch):
    import sys
    from types import SimpleNamespace
    monkeypatch.setitem(sys.modules, 'lancedb.index', SimpleNamespace(FTS=lambda **kwargs: kwargs))
    class Table:
        def __init__(self):
            self.indices, self.creates, self.adds = [], [], []
            self._table = SimpleNamespace(close=lambda: None)
        def list_indices(self):
            return self.indices
        def create_index(self, column, **kwargs):
            self.creates.append((column, kwargs))
            self.indices.append(SimpleNamespace(index_type='FTS', columns=['text']))
        def add(self, rows):
            self.adds.extend(rows)
    table = Table()
    index = synthetic_index(tmp_path / 'index')
    index._table = table
    for i in range(5):
        index.stage([{'text': 'Synthetic fragment', 'revision_id': str(i)}])
    assert table.creates == [('text', {'config': {'with_position': True}, 'replace': False})]
    assert len(table.adds) == 5
    index.close()
    reopened = synthetic_index(tmp_path / 'index')
    reopened._table = table
    reopened.build_fts()
    assert len(table.creates) == 1
    reopened.close()


def test_hybrid_path_preserves_prefilter_rrf_and_does_not_enable_fast_search(tmp_path, monkeypatch):
    import sys
    from types import SimpleNamespace
    calls = []
    class Query:
        def vector(self, value):
            calls.append(('vector', value)); return self
        def text(self, value):
            calls.append(('text', value)); return self
        def where(self, value, **kwargs):
            calls.append(('where', value, kwargs)); return self
        def rerank(self, value):
            calls.append(('rerank', value)); return self
        def limit(self, value):
            calls.append(('limit', value)); return self
        def to_list(self):
            return [{'passage_id': 'synthetic-appended'}]
    monkeypatch.setitem(sys.modules, 'lancedb.rerankers', SimpleNamespace(RRFReranker=lambda: 'RRF'))
    index = synthetic_index(tmp_path / 'index')
    index._table = SimpleNamespace(search=lambda **kwargs: (calls.append(('search', kwargs)) or Query()),
                                   _table=SimpleNamespace(close=lambda: None))
    assert index.search('appended', [1.], ["revision'quoted"], 4) == [{'passage_id': 'synthetic-appended'}]
    assert calls == [('search', {'query_type': 'hybrid'}), ('vector', [1.]), ('text', 'appended'),
                     ('where', "revision_id IN ('revision''quoted')", {'prefilter': True}),
                     ('rerank', 'RRF'), ('limit', 4)]
    index.close()


def test_maintenance_failure_keeps_accepted_publication_and_retries_only_maintenance(repository, monkeypatch):
    repo = repository
    clock = [1000.]
    monkeypatch.setattr('renulus.knowledge.repository.time.time', lambda: clock[0])
    item = repo.import_text('Synthetic accepted source')
    repo.index.fail_optimize = True
    assert repo.cleanup(force=False, queue_drained=True)
    debt = repo.db.fetch_one("SELECT * FROM knowledge_index_work WHERE kind='maintenance' AND target='passages'")
    assert debt['attempts'] == 1 and debt['retry_after'] == 1001.
    assert repo.get_job(item['job']['id'])['state'] == 'ready'
    identities = list(repo.index.rows)
    repo.index.fail_optimize = False
    repo.cleanup(force=False, queue_drained=True)
    assert repo.index.optimizations == 1
    clock[0] = 1001.
    assert repo.cleanup(force=False) == []
    assert repo.index.optimizations == 2 and repo.index.rows == identities
    assert repo.original(item['revision_id'])[0].exists()
    assert not repo.db.fetch_all('SELECT * FROM knowledge_cleanup')


def test_growth_trigger_is_configurable_and_native_maintenance_has_no_sqlite_writer(repository):
    repo = repository
    repo.maintenance_batches = 999
    repo.maintenance_bytes = 1
    base = repo.index.optimize
    def optimize():
        assert repo.db._active_writers == 0
        repo._owner.require()
        return base()
    repo.index.optimize = optimize
    item = repo.import_text('Synthetic measured growth')
    assert item['status'] == 'ready' and repo.index.optimizations == 1
    work = repo.db.fetch_one("SELECT * FROM knowledge_index_work WHERE kind='maintenance' AND target='passages'")
    assert work['measured_logical_bytes'] == 256
    assert work['measured_allocated_bytes'] == 512
    assert work['forecast_peak_bytes'] >= 2 * 512


def test_low_space_original_admission_precedes_copy_and_canonical_commit(repository):
    repo = repository
    repo._owner.fs.free = MIN_FREE_BYTES
    with pytest.raises(ApiError) as error:
        repo.import_text('Synthetic rejected copy')
    assert error.value.code == 'knowledge_low_space' and error.value.retryable
    assert not repo.db.fetch_all('SELECT * FROM knowledge_revisions')
    assert not list(repo.paths.library.rglob('original.*'))
    repo._owner.fs.free = MIN_FREE_BYTES + 1024 ** 3
    assert repo.import_text('Synthetic admitted copy')['status'] == 'ready'


def test_low_space_maintenance_preserves_ready_and_original_then_retries(repository):
    repo = repository
    item = repo.import_text('Synthetic ready source')
    rows = list(repo.index.rows)
    repo._owner.fs.free = MIN_FREE_BYTES
    assert repo.cleanup()
    debt = repo.db.fetch_one("SELECT * FROM knowledge_index_work WHERE kind='maintenance' AND target='passages'")
    assert debt['error_code'] == 'knowledge_low_space'
    assert repo.index.optimizations == 0
    assert repo.get_job(item['job']['id'])['state'] == 'ready'
    assert repo.original(item['revision_id'])[0].exists() and repo.index.rows == rows
    repo._owner.fs.free = MIN_FREE_BYTES + 1024 ** 3
    assert repo.cleanup() == []
    assert repo.index.optimizations == 1 and repo.index.rows == rows


def test_low_space_rebuild_admission_never_constructs_candidate(repository, monkeypatch):
    repo = repository
    item = repo.import_text('Synthetic ready before rebuild')
    repo.cleanup()
    previous = repo.index
    repo._owner.fs.free = MIN_FREE_BYTES
    def candidate(*args):
        pytest.fail('No large candidate is constructed to discover low capacity')
    monkeypatch.setattr('renulus.knowledge.repository.LanceIndex', candidate)
    with pytest.raises(ApiError) as error:
        repo.rebuild_index()
    assert error.value.code == 'knowledge_low_space'
    assert repo.index is previous and repo.get_job(item['job']['id'])['state'] == 'ready'
    assert repo.original(item['revision_id'])[0].exists()


def test_mid_batch_capacity_failure_keeps_original_and_retry_fences_partial_rows(repository, monkeypatch):
    from renulus.knowledge.engines import Extracted
    repo = repository
    class Many:
        def extract_file(self, path, title):
            return Extracted([{'text': 'Synthetic', 'context_text': 'Synthetic', 'headings': [], 'locators': []}
                              for _ in range(65)], {'synthetic': True})
    repo.extractor = Many()
    preflight = repo.capacity.preflight
    stages = [0]
    def limited(target, **kwargs):
        if kwargs['operation'] == 'stage':
            stages[0] += 1
            if stages[0] == 2:
                raise ApiError('knowledge_low_space', 'Synthetic staging capacity', 503, True)
        return preflight(target, **kwargs)
    monkeypatch.setattr(repo.capacity, 'preflight', limited)
    item = repo.import_text('Synthetic original retained')
    assert item['status'] == 'queued' and item['job']['phase'] == 'waiting_space'
    assert repo.original(item['revision_id'])[0].exists()
    assert repo.index.rows == [] and not repo.db.fetch_all('SELECT * FROM knowledge_passages')
    assert repo.next_queued_job() is None
    queue = LibraryPriorityQueue(repo)
    queue.mark(item['job']['id'])
    assert queue.next_job() is None
    monkeypatch.setattr(repo.capacity, 'preflight', preflight)
    assert repo.run_job(item['job']['id'])['state'] == 'ready'  # explicit retry bypasses backoff
    assert len(repo.index.rows) == 65
    assert len({row['passage_id'] for row in repo.index.rows}) == 65
    assert not repo.db.fetch_all("SELECT * FROM knowledge_index_work WHERE target=?", (item['revision_id'],))


def test_target_volume_forecast_uses_measurement_and_available_bytes_not_free_after_copy(repository):
    from renulus.knowledge.ownership import NATIVE_MARGIN
    repo = repository
    fs = repo._owner.fs
    forecast = repo.capacity.preflight(repo.index.path, operation='maintenance', growth_bytes=32, measured_root=repo.index.path)
    assert (forecast.logical_bytes, forecast.allocated_bytes, forecast.peak_bytes) == (256, 512, 2 * (512 + 32) + NATIVE_MARGIN)
    assert fs.targets[-1] == repo.index.path
    fs.free = MIN_FREE_BYTES + forecast.peak_bytes - 1
    with pytest.raises(ApiError):
        repo.capacity.preflight(repo.index.path, operation='maintenance', growth_bytes=32, measured_root=repo.index.path)


def test_profile_owner_excludes_second_repository_until_real_close(repository):
    repo = repository
    fs = repo._owner.fs
    def reopen():
        return KnowledgeRepository(repo.services, extractor=SyntheticExtractor(), embedder=SyntheticEmbedder(),
            index=MaintenanceIndex(repo.index.path), owner=synthetic_owner(repo.paths.state / 'knowledge-native-owner', fs),
            capacity=KnowledgeCapacity(filesystem=fs))
    with pytest.raises(ApiError) as error:
        reopen()
    assert error.value.code == 'index_owner_busy'
    repo.index.fail_close = True
    with pytest.raises(OSError):
        repo.close()
    with pytest.raises(ApiError):
        reopen()
    repo.index.fail_close = False
    repo.close()
    fresh = reopen()
    fresh.close()


def test_owner_release_failure_is_not_settlement(repository):
    repo = repository
    fs = repo._owner.fs
    fs.fail_release = True
    with pytest.raises(OSError):
        repo.close()
    repo._owner.require()
    assert fs.held and not repo._closed
    fs.fail_release = False
    repo.close()
    assert not fs.held


def test_retirement_keeps_generation_fence_until_folder_and_release_settle(repository, monkeypatch):
    repo = repository
    repo.import_text('Synthetic publication')
    previous = repo.index
    monkeypatch.setattr('renulus.knowledge.repository.LanceIndex', MaintenanceIndex)
    remove = repo._remove_index_folder
    def held(path):
        if Path(path) == previous.path:
            raise OSError('Synthetic locked generation folder')
        return remove(path)
    monkeypatch.setattr(repo, '_remove_index_folder', held)
    result = repo.rebuild_index()
    assert result['status'] == 'ready' and result['cleanup_pending']
    assert previous.closed and previous.path.exists()
    assert repo._retired_indexes['knowledge'] is previous
    token = previous.path.parent / (previous.path.name + '.native-owner')
    with pytest.raises(ApiError):
        synthetic_owner(token, repo._owner.fs).acquire()
    with pytest.raises(ApiError):
        repo.close()
    repo._owner.require()
    monkeypatch.setattr(repo, '_remove_index_folder', remove)
    with pytest.raises(ApiError):
        repo.cleanup()  # closing repository only allows close() retries
    with pytest.raises(ApiError) as error:
        repo.close()
    assert error.value.code == 'index_cleanup_pending'
    assert previous.path.exists() and repo._owner.fs.held
    assert repo._retirement_owners['knowledge']._path_pin is not None


def test_stop_zero_and_held_native_work_keep_exact_profile_ownership(repository):
    from threading import Event
    repo = repository
    item = repo.import_text('Synthetic held work', process=False)
    entered, release = Event(), Event()
    base = repo.index.stage
    def held(rows, **kwargs):
        entered.set()
        assert release.wait(10)
        return base(rows, **kwargs)
    repo.index.stage = held
    worker = IngestionWorker(repo)
    try:
        worker.start()
        assert entered.wait(5)
        worker.stop(0)
        assert not worker.status()['settled']
        repo._owner.require()
        with pytest.raises(ApiError):
            synthetic_owner(repo.paths.state / 'knowledge-native-owner', repo._owner.fs).acquire()
    finally:
        release.set()
        worker.stop(None)
    assert worker.status()['settled'] and repo.get_job(item['job']['id'])['state'] == 'ready'
    # Worker settlement alone is not native repository closure.
    with pytest.raises(ApiError):
        synthetic_owner(repo.paths.state / 'knowledge-native-owner', repo._owner.fs).acquire()
    repo.close()
    fresh = synthetic_owner(repo.paths.state / 'knowledge-native-owner', repo._owner.fs).acquire()
    fresh.close()


def test_native_close_drains_reader_before_generation_token_release(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from types import SimpleNamespace
    import sys
    entered, release = Event(), Event()
    monkeypatch.setitem(sys.modules, 'lancedb.rerankers', SimpleNamespace(RRFReranker=lambda: 'RRF'))
    class Query:
        def vector(self, value): return self
        def text(self, value): return self
        def where(self, *args, **kwargs): return self
        def rerank(self, value): return self
        def limit(self, value): return self
        def to_list(self):
            entered.set()
            assert release.wait(10)
            return []
    index = synthetic_index(tmp_path / 'index')
    index._table = SimpleNamespace(search=lambda **kwargs: Query(), _table=SimpleNamespace(close=lambda: None))
    with ThreadPoolExecutor(max_workers=2) as pool:
        reader = pool.submit(index.search, 'Synthetic', [1.], ['revision'], 2)
        assert entered.wait(5)
        owner = index._ownership
        closing = pool.submit(index.close)
        try:
            assert not closing.done()
            owner.require()
            with pytest.raises(ApiError):
                synthetic_owner(owner.path, owner.fs).acquire()
        finally:
            release.set()
        assert reader.result(timeout=5) == []
        closing.result(timeout=5)
    fresh = synthetic_owner(owner.path, owner.fs).acquire()
    fresh.close()


def test_crash_before_append_recovery_reconstructs_debt_without_duplicate_import(repository):
    repo = repository
    item = repo.import_text('Synthetic preappend crash', process=False)
    class Crash(BaseException): pass
    def crash():
        debt = repo.db.fetch_one("SELECT * FROM knowledge_index_work WHERE kind='maintenance' AND target='passages'")
        assert debt['dirty_sequence'] > debt['completed_sequence']
        raise Crash()
    repo.index.before_stage = crash
    with pytest.raises(Crash):
        repo.run_job(item['job']['id'])
    assert repo.get_job(item['job']['id'])['state'] == 'processing'
    repo.index.before_stage = lambda: None
    assert repo.recover() == []
    assert repo.get_job(item['job']['id'])['state'] == 'queued'
    assert repo.original(item['revision_id'])[0].exists()
    assert repo.run_job(item['job']['id'])['state'] == 'ready'
    assert len(repo.index.rows) == 1
    assert len(repo.db.fetch_all('SELECT * FROM knowledge_jobs')) == 1


def test_ready_append_debt_survives_real_repository_close_and_reopen(repository):
    repo = repository
    item = repo.import_text('Synthetic ready reopen')
    assert item['maintenance_pending'] is True
    old_rows = list(repo.index.rows)
    repo.close()  # Close/drain doesn't invent maintenance completion.
    fs = repo._owner.fs
    index = MaintenanceIndex(repo.index.path)
    index.rows = old_rows  # Only the engine adapter is a double; SQLite reopens.
    fresh = KnowledgeRepository(repo.services, extractor=SyntheticExtractor(), embedder=SyntheticEmbedder(), index=index,
        owner=synthetic_owner(repo.paths.state / 'knowledge-native-owner', fs), capacity=KnowledgeCapacity(filesystem=fs))
    try:
        assert fresh.get_job(item['job']['id'])['state'] == 'ready'
        assert fresh.recover() == []
        assert index.optimizations == 1 and index.rows == old_rows
        assert fresh.next_queued_job() is None
    finally:
        fresh.close()


def test_reopen_legacy_native_history_reconstructs_missing_local_maintenance(repository):
    repo = repository
    item = repo.import_text('Synthetic legacy publication')
    repo.db.execute('DELETE FROM knowledge_index_work')
    assert repo.recover() == []
    assert repo.index.optimizations == 1
    assert repo.get_job(item['job']['id'])['state'] == 'ready'
    assert len(repo.index.rows) == 1


def test_worker_attempts_queue_drain_maintenance_without_new_ingress(repository):
    from threading import Event
    repo = repository
    repo.import_text('Synthetic background idle', process=False)
    completed = Event()
    base = repo.index.optimize
    def optimize():
        result = base()
        if repo.db.fetch_one("SELECT 1 FROM knowledge_jobs WHERE state='ready'"):
            completed.set()
        return result
    repo.index.optimize = optimize
    worker = IngestionWorker(repo)
    try:
        worker.start()
        assert completed.wait(5)
    finally:
        worker.stop(None)
    assert worker.status()['settled']
    debt = repo.db.fetch_one("SELECT * FROM knowledge_index_work WHERE kind='maintenance' AND target='passages'")
    assert debt['completed_sequence'] == debt['dirty_sequence']


def test_native_retirement_handle_survives_folder_failure(tmp_path):
    from types import SimpleNamespace
    index = synthetic_index(tmp_path / 'index')
    index.path.mkdir()
    index._table = SimpleNamespace(_table=SimpleNamespace(close=lambda: None))
    index.prepare_retirement()
    owner = index._ownership
    assert index._table is None
    with pytest.raises(ApiError):
        synthetic_owner(owner.path, owner.fs).acquire()
    with pytest.raises(ApiError):
        index._open()
    with pytest.raises(ApiError) as error:
        index.finish_retirement()
    assert error.value.code == 'index_cleanup_pending'
    index.close()  # Ordinary close cannot release pending retirement pins.
    assert index.path.exists() and owner._path_pin is not None
    with pytest.raises(ApiError):
        synthetic_owner(owner.path, owner.fs).acquire()


def test_bound_adapter_cannot_reopen_in_native_close_profile_release_gap(repository, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from types import SimpleNamespace
    from renulus.knowledge.engines import LanceIndex
    repo = repository
    fs = repo._owner.fs
    index = LanceIndex(repo.index.path, ownership_factory=lambda token: synthetic_owner(token, fs))
    index.bind_profile_owner(repo._owner)
    index._table = SimpleNamespace(_table=SimpleNamespace(close=lambda: None))
    index._open()
    repo.index = index
    entered, release = Event(), Event()
    base = repo._owner.close
    def held_release():
        entered.set()
        assert release.wait(10)
        base()
    monkeypatch.setattr(repo._owner, 'close', held_release)
    with ThreadPoolExecutor(max_workers=1) as pool:
        closing = pool.submit(repo.close)
        assert entered.wait(5)
        try:
            assert index._table is None and index._ownership is None
            with pytest.raises(ApiError) as error:
                index._open()
            assert error.value.code == 'index_close_pending'
            repo._owner.require()
        finally:
            release.set()
        closing.result(timeout=5)
    assert not fs.held and repo._closed


def test_reentrant_close_cannot_seal_its_own_live_ingestion(repository):
    repo = repository
    base = repo.extractor
    class Extractor:
        def extract_file(self, path, title):
            with pytest.raises(ApiError) as error:
                repo.close()
            assert error.value.code == 'recovery_busy'
            repo._owner.require_open()
            return base.extract_file(path, title)
    repo.extractor = Extractor()
    assert repo.import_text('Synthetic close callback')['status'] == 'ready'


def test_live_direct_generation_reader_fences_orphan_retirement(repository):
    from types import SimpleNamespace
    from renulus.knowledge.engines import LanceIndex
    repo = repository
    fs = repo._owner.fs
    token = 'k/' + 'a' * 32
    path = repo._index_folder(token)
    path.mkdir(parents=True)
    reader = LanceIndex(path, ownership_factory=lambda name: synthetic_owner(name, fs))
    reader._table = SimpleNamespace(_table=SimpleNamespace(close=lambda: None))
    reader._open()
    try:
        assert repo.cleanup()
        assert path.exists()
        debt = repo.db.fetch_one("SELECT * FROM knowledge_index_work WHERE kind='retirement' AND target=?", (token,))
        assert debt['error_code'] == 'index_cleanup_pending'
    finally:
        reader.close()
    assert repo.cleanup() and path.exists()
    assert repo._retirement_owners[token]._path_pin is not None
    assert repo.maintenance_status()['retirement_pending'] == 1


def test_services_observer_timeout_retains_owner_until_real_dependency_drain(repository):
    import asyncio
    from threading import Event
    repo = repository
    repo.import_text('Synthetic services drain', process=False)
    entered, release = Event(), Event()
    base = repo.index.stage
    def held(rows, **kwargs):
        entered.set()
        assert release.wait(10)
        return base(rows, **kwargs)
    repo.index.stage = held
    worker = IngestionWorker(repo)
    services = repo.services
    services.on_stopping.append(lambda: worker.stop(0))
    services.on_shutdown.append(lambda: asyncio.to_thread(worker.stop, None))
    worker.start()
    assert entered.wait(5)
    async def scenario():
        try:
            with pytest.raises(ApiError) as error:
                await services.shutdown(timeout=.01)
            assert error.value.code == 'runtime_shutdown_pending'
            repo._owner.require()
            with pytest.raises(ApiError):
                synthetic_owner(repo.paths.state / 'knowledge-native-owner', repo._owner.fs).acquire()
        finally:
            release.set()
        assert (await services.shutdown())['state'] == 'settled'
        assert repo._closed and not repo._owner.fs.held
    try:
        asyncio.run(scenario())
    finally:
        release.set()
        worker.stop(None)


def test_closed_repository_cannot_mutate_a_later_owner_canonical_state(repository):
    repo = repository
    ready = repo.import_text('Synthetic protected ready')
    queued = repo.import_text('Synthetic protected queue', process=False)
    repo.close()
    for operation in (lambda: repo.delete_document(ready['document_id']),
                      lambda: repo.cancel_job(queued['job']['id'])):
        with pytest.raises(ApiError) as error:
            operation()
        assert error.value.code == 'index_close_pending'
    assert repo.get_job(queued['job']['id'])['state'] == 'queued'
    assert repo.get_document(ready['document_id'])['active_revision'] == ready['revision_id']
    assert not repo.db.fetch_all('SELECT * FROM deletion_ledger')


def test_native_owner_contention_is_retryable_and_keeps_imported_original(repository):
    repo = repository
    def busy():
        raise ApiError('index_owner_busy', 'Synthetic held native generation reader', 503, True)
    repo.index.before_stage = busy
    item = repo.import_text('Synthetic waiting for native owner')
    assert item['status'] == 'queued' and item['job']['phase'] == 'waiting_owner'
    assert repo.original(item['revision_id'])[0].exists()
    assert repo.next_queued_job() is None
    repo.index.before_stage = lambda: None
    assert repo.run_job(item['job']['id'])['state'] == 'ready'
    assert len(repo.index.rows) == 1 and repo.original(item['revision_id'])[0].exists()
