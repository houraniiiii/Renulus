"""R26-01..08 focused repairs: synthetic storage/native boundaries, not SDK acceptance."""
import asyncio
from pathlib import Path
from threading import Event
from types import SimpleNamespace
import time

import pytest

from renulus.contracts import ApiError
from renulus.knowledge.engines import LanceIndex
from renulus.knowledge.ownership import KnowledgeCapacity, MIN_FREE_BYTES, NATIVE_MARGIN
from renulus.knowledge.repository import KnowledgeRepository
from renulus.services import Services
from test_index_maintenance import MaintenanceIndex, repository
from test_repository import SyntheticEmbedder, SyntheticExtractor
from test_storage_reliability import synthetic_index, synthetic_owner


def reopen(repo):
    index = MaintenanceIndex(repo.index.path)
    index.rows = list(repo.index.rows)
    return KnowledgeRepository(Services(repo.paths, repo.db), extractor=SyntheticExtractor(),
        embedder=SyntheticEmbedder(), index=index,
        owner=synthetic_owner(repo.paths.state / 'knowledge-native-owner', repo._owner.fs),
        capacity=KnowledgeCapacity(filesystem=repo._owner.fs))


def test_r26_02_shutdown_retries_only_unsettled_dependencies(repository):
    repo = repository
    calls = []
    services = repo.services
    services.on_stopping.append(lambda: calls.append('signal'))
    services.on_shutdown.append(lambda: calls.append('producer'))
    services.on_shutdown_dependencies.append(lambda: calls.append('first-dependency'))
    services.on_shutdown_dependencies.insert(0, lambda: calls.append('last-dependency'))
    close = repo.index.close
    def fail_once():
        calls.append('native-close')
        if calls.count('native-close') == 1:
            raise OSError('Synthetic transient native close')
        close()
    repo.index.close = fail_once
    async def scenario():
        with pytest.raises(ApiError) as error:
            await services.shutdown(timeout=1)
        assert error.value.code == 'runtime_shutdown_failed'
        assert services.shutdown_status()['state'] == 'failed'
        repo._owner.require()
        with pytest.raises(ApiError):
            services.admit_request(lambda: asyncio.sleep(0), lambda: None)
        assert (await services.shutdown(timeout=1))['state'] == 'settled'
        assert repo._closed
    asyncio.run(scenario())
    assert calls == ['signal', 'producer', 'first-dependency', 'native-close', 'native-close', 'last-dependency']


def test_r26_02_finish_shutdown_eventually_retries_without_deadlock(repository):
    repo = repository
    calls = []
    close = repo.index.close
    def fail_once():
        calls.append('close')
        if len(calls) == 1:
            raise OSError('Synthetic transient close')
        close()
    repo.index.close = fail_once
    async def scenario():
        with pytest.raises(ApiError):
            await repo.services.shutdown(timeout=1)
        await asyncio.wait_for(repo.services.finish_shutdown(), timeout=2)
        assert repo.services.shutdown_status()['state'] == 'settled'
    asyncio.run(scenario())
    assert calls == ['close', 'close']


def test_r26_03_native_close_observation_timeout_does_not_block_or_cancel(repository):
    repo = repository
    entered, release = Event(), Event()
    close = repo.index.close
    def held_close():
        entered.set()
        assert release.wait(2)
        close()
    repo.index.close = held_close
    async def scenario():
        started = time.perf_counter()
        try:
            with pytest.raises(ApiError) as error:
                await repo.services.shutdown(timeout=.02)
            assert error.value.code == 'runtime_shutdown_pending'
            assert time.perf_counter() - started < .5
            assert entered.is_set() and not repo._closed
            repo._owner.require()
            with pytest.raises(ApiError):
                repo._require_open()
            with pytest.raises(ApiError):
                synthetic_owner(repo._owner.path, repo._owner.fs).acquire()
            observer = asyncio.create_task(repo.services.shutdown())
            await asyncio.sleep(.01)
            observer.cancel()
            with pytest.raises(asyncio.CancelledError):
                await observer
            assert not repo.services._shutdown_task.done()
        finally:
            release.set()
        assert (await repo.services.shutdown(timeout=1))['state'] == 'settled'
    asyncio.run(scenario())


def test_r26_04_retirement_survives_ordinary_close(tmp_path):
    index = synthetic_index(tmp_path / 'index')
    index.path.mkdir()
    index._table = SimpleNamespace(_table=SimpleNamespace(close=lambda: None))
    index.prepare_retirement()
    with pytest.raises(ApiError) as error:
        index.finish_retirement()
    assert error.value.code == 'index_cleanup_pending'
    for _ in range(2):
        index.close()
        with pytest.raises(ApiError) as error:
            index._open()
        assert error.value.code == 'index_close_pending'
        assert index.path.exists() and index._ownership._path_pin is not None


@pytest.mark.parametrize('direct_journal', [False, True])
def test_r26_05_stale_source_publication_refused_inside_journal(repository, direct_journal):
    repo = repository
    ready = repo.import_text('Synthetic exact source', metadata={
        'source_id': 'P01', 'canonical_url': 'https://example.org/synthetic'})
    repo.close()
    new = reopen(repo)
    try:
        operation = repo.source_status.update if direct_journal else repo.update_source_status
        with pytest.raises(ApiError) as error:
            operation({'contract_version': 1, 'event_id': 'stale-repo', 'source_id': 'P01',
                'identity': {'canonical_url': 'https://example.org/synthetic'},
                'changes': {'content_reviewed': False}})
        assert error.value.code == 'index_close_pending'
        new._owner.require()
        assert new.db.fetch_one('SELECT COUNT(*) AS n FROM knowledge_source_status_events')['n'] == 0
        assert new.get_job(ready['job']['id'])['state'] == 'ready'
    finally:
        new.close()


@pytest.mark.parametrize('persisted', [True, False])
def test_r26_06_public_import_discovers_fts_before_creation_forecast(repository, monkeypatch, persisted):
    import sys
    repo = repository
    fs = repo._owner.fs
    observations = []
    monkeypatch.setitem(sys.modules, 'lancedb.index', SimpleNamespace(FTS=lambda **kwargs: kwargs))
    class Table:
        _table = SimpleNamespace(close=lambda: None)
        def add(self, rows):
            observations.append('append')
            fs.free = MIN_FREE_BYTES + NATIVE_MARGIN + 2 * fs.measured.allocated_bytes - 1
        def delete(self, predicate):
            observations.append('delete')
        def list_indices(self):
            assert repo.db._active_writers == 0
            index._ownership.require()
            observations.append('discover')
            return [SimpleNamespace(index_type='FTS', columns=['text'])] if persisted else []
        def create_index(self, *args, **kwargs):
            pytest.fail('Existing FTS is no-op; absent FTS needs capacity before create')
        def optimize(self, **kwargs):
            pytest.fail('Maintenance remains capacity gated')
    index = LanceIndex(repo.index.path, ownership_factory=lambda token: synthetic_owner(token, fs))
    index.bind_profile_owner(repo._owner)
    index._table = Table()
    repo.index = index
    item = repo.import_text('Synthetic appended source')
    assert observations[:2] == ['append', 'discover']
    if persisted:
        assert item['status'] == 'ready'
        assert observations == ['append', 'discover']
        assert repo.db.fetch_one('SELECT COUNT(*) AS n FROM knowledge_passages')['n'] == 1
        debt = repo.db.fetch_one("SELECT * FROM knowledge_index_work WHERE target='passages'")
        assert debt['dirty_sequence'] == 1  # Append only, not FTS discovery.
    else:
        assert item['status'] == 'queued' and item['job']['phase'] == 'waiting_space'
        assert observations == ['append', 'discover']
        removal = repo.db.fetch_one("SELECT * FROM knowledge_index_work WHERE kind='removal'")
        assert removal['completed_sequence'] == 0 and removal['error_code'] == 'knowledge_low_space'
    assert repo.original(item['revision_id'])[0].exists()


def test_r26_07_clean_durable_reopen_does_not_create_debt(repository):
    repo = repository
    item = repo.import_text('Synthetic maintained source')
    repo.cleanup(force=False, queue_drained=True)
    before = repo.db.fetch_one("SELECT dirty_sequence,completed_sequence FROM knowledge_index_work WHERE target='passages'")
    assert before['dirty_sequence'] == before['completed_sequence']
    repo.close()
    new = reopen(repo)
    try:
        assert new.recover() == []
        assert new.recover() == []
        after = new.db.fetch_one("SELECT dirty_sequence,completed_sequence FROM knowledge_index_work WHERE target='passages'")
        assert after == before and new.index.optimizations == 0
        assert new.get_job(item['job']['id'])['state'] == 'ready'
    finally:
        new.close()


@pytest.mark.parametrize('terminal', ['cancel', 'replace', 'delete', 'failure'])
def test_r26_08_terminal_wait_timers_removed_but_native_debt_retained(repository, terminal):
    repo = repository
    preflight = repo.capacity.preflight
    def low_stage(target, **kwargs):
        if kwargs['operation'] == 'stage':
            raise ApiError('knowledge_low_space', 'Synthetic waiting space', 503, True)
        return preflight(target, **kwargs)
    repo.capacity.preflight = low_stage
    item = repo.import_text('Synthetic admission wait')
    assert item['job']['phase'] == 'waiting_space'
    assert repo.db.fetch_one("SELECT 1 FROM knowledge_index_work WHERE target=?", (item['revision_id'],))
    repo.index.fail_remove = True
    if terminal == 'cancel':
        repo.cancel_job(item['job']['id'])
    elif terminal == 'replace':
        repo.import_text('Synthetic replacement', document_id=item['document_id'], process=False)
    elif terminal == 'delete':
        repo.delete_document(item['document_id'])
    else:
        repo.capacity.preflight = preflight
        class FailedExtractor:
            def extract_file(self, *args):
                raise ApiError('extraction_failed', 'Synthetic terminal extraction', 422)
        repo.extractor = FailedExtractor()
        repo.run_job(item['job']['id'])
    assert not repo.db.fetch_one("SELECT 1 FROM knowledge_index_work WHERE kind='maintenance' AND target=?", (item['revision_id'],))
    assert repo.db.fetch_one('SELECT 1 FROM knowledge_cleanup WHERE revision_id=?', (item['revision_id'],))
    assert repo.db.fetch_one("SELECT 1 FROM knowledge_index_work WHERE kind='removal' AND target=?", (item['revision_id'],))
    assert repo.maintenance_status()['pending']
    repo.index.fail_remove = False
    repo.cleanup()
