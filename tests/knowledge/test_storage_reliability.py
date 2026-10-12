"""Issue #25 regressions through public seams, without CPU helpers or private state."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from threading import Event
import json

import pytest

from renulus.contracts import ApiError
from renulus.knowledge.engines import LanceIndex
from renulus.knowledge.priority_queue import LibraryPriorityQueue
from renulus.knowledge.repository import KnowledgeRepository
from renulus.knowledge.worker import IngestionWorker
from renulus.services import Services
from renulus.storage import AppPaths, Database
from renulus.storage.backup import export_records
from renulus.storage.recovery import Recovery
from test_repository import SyntheticEmbedder, SyntheticExtractor


class FaultIndex:
    def __init__(self, path, dimensions=384):
        self.path = Path(path).resolve()
        self.path.mkdir(parents=True, exist_ok=True)
        self.rows = []
        self.removed = []
        self.fail_remove = False
        self.fail_optimize = False
        self.fail_close = False
        self.closed = False
        self.optimizations = 0

    def stage(self, rows, **kwargs):
        self.rows.extend(rows)

    def build_fts(self):
        pass

    def validate_passages(self, identities):
        assert {(r['passage_id'], r['revision_id'], r['document_id']) for r in self.rows} == identities

    def remove(self, revision_id):
        self.removed.append(revision_id)
        if self.fail_remove:
            raise OSError('synthetic removal fault')
        self.rows = [r for r in self.rows if r['revision_id'] != revision_id]

    def optimize(self):
        self.optimizations += 1
        if self.fail_optimize:
            raise OSError('synthetic maintenance fault')

    def close(self):
        if self.fail_close:
            raise OSError('synthetic close fault')
        self.closed = True


@pytest.fixture
def repository(tmp_path):
    paths = AppPaths.create(tmp_path / 'profile')
    db = Database(paths.database)
    module = Path(__file__).parents[2] / 'runtime/renulus/knowledge'
    db.apply_migration('knowledge-001', (module / 'schema.sql').read_text())
    for migration in sorted((module / 'migrations').glob('*.sql')):
        db.apply_migration('knowledge-' + migration.stem, migration.read_text())
    repo = KnowledgeRepository(Services(paths, db), extractor=SyntheticExtractor(),
        embedder=SyntheticEmbedder(), index=FaultIndex(paths.indexes / 'knowledge'))
    yield repo
    repo.index.fail_close = False
    repo.index.close()


def interrupted(repo):
    item = repo.import_text('Synthetic dialysis source', process=False)
    repo.db.execute("UPDATE knowledge_jobs SET state='processing' WHERE id=?", (item['job']['id'],))
    repo.db.execute("UPDATE knowledge_revisions SET status='processing' WHERE id=?", (item['revision_id'],))
    repo.index.stage([{'passage_id': 'partial', 'revision_id': item['revision_id'],
        'document_id': item['document_id'], 'text': 'Synthetic partial', 'vector': [1.] * 384}])
    return item


@pytest.mark.parametrize('admission', ['direct', 'fifo', 'interactive'])
def test_failed_recovery_cleanup_fences_only_affected_revision(repository, admission):
    repo = repository
    item = interrupted(repo)
    unrelated = repo.import_text('Synthetic transplant source', process=False)
    repo.index.fail_remove = True
    assert repo.recover()
    if admission == 'direct':
        assert repo.run_job(item['job']['id'])['state'] == 'queued'
    elif admission == 'fifo':
        assert repo.next_queued_job() == {'id': unrelated['job']['id']}
    else:
        queue = LibraryPriorityQueue(repo)
        queue.mark(item['job']['id'])
        assert queue.next_job() == {'id': unrelated['job']['id']}
    assert repo.get_job(item['job']['id'])['state'] == 'queued'
    assert repo.run_job(unrelated['job']['id'])['state'] == 'ready'
    repo.index.fail_remove = False
    assert repo.cleanup() == []
    assert repo.run_job(item['job']['id'])['state'] == 'ready'
    assert repo.cleanup() == []
    assert len([r for r in repo.index.rows if r['revision_id'] == item['revision_id']]) == 1


def test_lance_delete_success_is_not_optimization_failure(tmp_path):
    class Table:
        def __init__(self):
            self.deletes = []
        def delete(self, predicate):
            self.deletes.append(predicate)
        def optimize(self, **kwargs):
            raise OSError('synthetic optimize fault after delete')
    index = LanceIndex(tmp_path / 'synthetic-index')
    table = Table()
    index._table = table
    index.remove('rev_synthetic')
    assert table.deletes == ["revision_id = 'rev_synthetic'"]


def test_removed_revision_leaves_only_non_destructive_maintenance_debt(repository):
    repo = repository
    first = repo.import_text('Synthetic kidney source')
    repo.index.fail_optimize = True
    result = repo.delete_document(first['document_id'])
    assert repo.db.fetch_all('SELECT * FROM knowledge_cleanup') == []
    debt = repo.db.fetch_all('SELECT * FROM knowledge_index_work')
    assert any(row['kind'] == 'maintenance' for row in debt)
    assert not any(row['kind'] == 'removal' for row in debt)
    assert result['cleanup_pending'] is True
    removed = list(repo.index.removed)
    repo.index.fail_optimize = False
    assert repo.cleanup() == []
    assert repo.index.removed == removed


def test_stale_cleanup_cannot_remove_current_ready_but_superseded_ready_is_removable(repository):
    repo = repository
    first = repo.import_text('Synthetic renal source')
    repo.db.execute('INSERT INTO knowledge_cleanup(revision_id,remove_original,created_at) VALUES(?,1,?)',
        (first['revision_id'], '2026-10-12'))
    assert repo.cleanup() == []
    assert first['revision_id'] not in repo.index.removed
    original = repo.db.fetch_one('SELECT original_path FROM knowledge_revisions WHERE id=?', (first['revision_id'],))
    assert Path(original['original_path']).exists()
    second = repo.import_text('Synthetic replacement', document_id=first['document_id'])
    assert second['status'] == 'ready'
    assert first['revision_id'] in repo.index.removed
    assert all(r['revision_id'] == second['revision_id'] for r in repo.index.rows)


def test_published_selector_and_close_failure_is_ready_and_retry_is_cleanup_only(repository, monkeypatch):
    repo = repository
    repo.import_text('Synthetic renal anemia')
    previous = repo.index
    previous.fail_close = True
    candidates = []
    def candidate(path, dimensions):
        index = FaultIndex(path, dimensions)
        candidates.append(index)
        return index
    monkeypatch.setattr('renulus.knowledge.repository.LanceIndex', candidate)
    result = repo.rebuild_index()
    assert result['status'] == 'ready' and result['cleanup_pending'] is True
    selector = repo.db.fetch_one("SELECT value FROM preferences WHERE key='knowledge.index_generation'")
    assert json.loads(selector['value']) == result['generation']
    assert previous.path.exists() and not previous.closed
    assert repo.cleanup()  # Failed close is not permission to remove the folder.
    assert previous.path.exists()
    previous.fail_close = False
    retried = repo.rebuild_index()
    assert retried['status'] == 'ready' and not retried['cleanup_pending']
    assert retried['generation'] == result['generation']
    assert len(candidates) == 1
    assert previous.closed and not previous.path.exists()


def test_public_recover_cannot_reset_a_live_ingestion_owner(repository):
    repo = repository
    item = repo.import_text('Synthetic held extraction', process=False)
    entered, release = Event(), Event()
    base = repo.extractor
    class Held:
        def extract_file(self, path, title):
            entered.set()
            assert release.wait(10)
            return base.extract_file(path, title)
    repo.extractor = Held()
    with ThreadPoolExecutor(max_workers=1) as pool:
        active = pool.submit(repo.run_job, item['job']['id'])
        assert entered.wait(5)
        try:
            with pytest.raises(ApiError) as error:
                repo.recover()
            assert error.value.code == 'recovery_busy'
            assert repo.get_job(item['job']['id'])['state'] == 'processing'
        finally:
            release.set()
        assert active.result(timeout=5)['state'] == 'ready'


def test_worker_stop_timeout_reports_live_owner_until_actual_settlement(repository):
    repo = repository
    item = repo.import_text('Synthetic held native stage', process=False)
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
        status = worker.status()
        assert status['running'] and status['stopping'] and not status['settled']
        assert status['active_job'] == item['job']['id']
        assert not repo.index.closed
        with pytest.raises(ApiError):
            repo.recover()
    finally:
        release.set()
        worker.stop(None)
    assert worker.status()['settled'] and not worker.status()['running']
    assert repo.get_job(item['job']['id'])['state'] == 'ready'


def test_lance_close_failure_retains_native_handles_for_retry(tmp_path):
    class Native:
        def __init__(self):
            self.fail = True
        def close(self):
            if self.fail:
                raise OSError('synthetic native close fault')
    class Table:
        def __init__(self):
            self._table = Native()
    index = LanceIndex(tmp_path / 'index')
    table = Table()
    index._table = table
    with pytest.raises(OSError):
        index.close()
    assert index._table is table
    table._table.fail = False
    index.close()
    assert index._table is None


def test_machine_local_debt_is_excluded_from_export(repository):
    repo = repository
    item = interrupted(repo)
    repo.index.fail_remove = True
    repo.recover()
    records = export_records(repo.services)['records']
    assert 'knowledge_index_work' not in records
    assert set(records['knowledge_jobs'][0]) == {'id', 'revision_id', 'idempotency_key',
        'request_hash', 'state', 'phase', 'error_code', 'error_message', 'created_at', 'finished_at'}
    assert set(records['knowledge_cleanup'][0]) == {'revision_id', 'remove_original', 'created_at', 'error_code'}
    assert records['knowledge_cleanup'][0]['revision_id'] == item['revision_id']


def test_optimize_uses_public_safe_retention_defaults_and_never_deletes_rows(tmp_path):
    class Table:
        def __init__(self):
            self.options = []
        def optimize(self, **kwargs):
            self.options.append(kwargs)
            return 'coalesced'
    leases = []
    @contextmanager
    def synthetic_owner():
        leases.append('entered')
        try:
            yield
        finally:
            leases.append('settled')
    index = LanceIndex(tmp_path / 'index')
    table = Table()
    index._table = table
    with pytest.raises(ApiError) as error:
        index.optimize()
    assert error.value.code == 'index_maintenance_owner_required'
    assert table.options == []
    index.maintenance_guard = synthetic_owner
    assert index.optimize() == 'coalesced'
    assert table.options == [{'delete_unverified': False}]
    assert leases == ['entered', 'settled']


def test_connection_close_failure_retains_only_the_unresolved_connection(tmp_path):
    class Native:
        def __init__(self, fail=False):
            self.fail, self.calls = fail, 0
        def close(self):
            self.calls += 1
            if self.fail:
                raise OSError('Synthetic close failure')
    class Table:
        def __init__(self):
            self._table = Native()
    class Connection:
        def __init__(self):
            self._conn = Native(fail=True)
    index = LanceIndex(tmp_path / 'index')
    table, connection = Table(), Connection()
    index._table, index._connection = table, connection
    with pytest.raises(OSError):
        index.close()
    assert index._table is None and index._connection is connection
    with pytest.raises(ApiError) as error:
        index._open()
    assert error.value.code == 'index_close_pending'
    assert index._connection is connection
    connection._conn.fail = False
    index.close()
    assert table._table.calls == 1 and connection._conn.calls == 2
    assert index._connection is None


def test_original_cleanup_failure_retries_files_not_successful_native_delete(repository, monkeypatch):
    repo = repository
    item = repo.import_text('Synthetic glomerular original')
    remove_tree = __import__('shutil').rmtree
    folder = repo._folder(item['document_id'], item['revision_id'])
    def fail(path, *args, **kwargs):
        if Path(path) == folder:
            raise OSError('Synthetic locked original')
        return remove_tree(path, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr('renulus.knowledge.repository.shutil.rmtree', fail)
        assert repo.delete_document(item['document_id'])['cleanup_pending']
    removed = list(repo.index.removed)
    assert repo.cleanup() == []
    assert repo.index.removed == removed
    assert not folder.exists()


def test_cleanup_backoff_and_explicit_retry_do_not_turn_append_into_maintenance(repository, monkeypatch):
    repo = repository
    clock = [1000.]
    monkeypatch.setattr('renulus.knowledge.repository.time.time', lambda: clock[0])
    item = interrupted(repo)
    repo.index.fail_remove = True
    repo.recover()
    work = repo.db.fetch_one("SELECT * FROM knowledge_index_work WHERE kind='removal'")
    assert work['attempts'] == 1 and work['retry_after'] == 1001.
    calls = len(repo.index.removed)
    assert repo.cleanup(force=False)
    assert len(repo.index.removed) == calls
    clock[0] = 1001.
    assert repo.cleanup(force=False)
    work = repo.db.fetch_one("SELECT * FROM knowledge_index_work WHERE kind='removal'")
    assert work['attempts'] == 2 and work['retry_after'] == 1003.
    repo.index.fail_remove = False
    assert repo.cleanup() == []  # Deliberate retry does not wait for wall clock.
    optimizations = repo.index.optimizations
    assert repo.run_job(item['job']['id'])['state'] == 'ready'
    assert repo.import_text('Synthetic electrolyte append')['status'] == 'ready'
    assert repo.index.optimizations == optimizations


def test_reentrant_public_recover_cannot_reset_its_extractor_job(repository):
    repo = repository
    base = repo.extractor
    class Extractor:
        def extract_file(self, path, title):
            for operation in (repo.recover, repo.rebuild_index):
                with pytest.raises(ApiError) as error:
                    operation()
                assert error.value.code == 'recovery_busy'
            with pytest.raises(ApiError):
                with repo.recovery_guard():
                    pytest.fail('A reentrant recovery cannot own this active job')
            with pytest.raises(ApiError) as error:
                repo.run_job(repo._active_ingestion)
            assert error.value.code == 'ingestion_busy'
            assert repo.get_job(repo._active_ingestion)['state'] == 'processing'
            return base.extract_file(path, title)
    repo.extractor = Extractor()
    assert repo.import_text('Synthetic reentrant recovery')['status'] == 'ready'


def test_published_cleanup_only_retry_survives_reopen(repository, monkeypatch):
    repo = repository
    repo.import_text('Synthetic transplant rebuild')
    monkeypatch.setattr('renulus.knowledge.repository.LanceIndex', FaultIndex)
    previous = repo.index
    remove_tree = repo._remove_index_folder
    def fail(path):
        if Path(path) == previous.path:
            raise OSError('Synthetic locked old folder')
        return remove_tree(path)
    monkeypatch.setattr(repo, '_remove_index_folder', fail)
    published = repo.rebuild_index()
    assert published['cleanup_pending'] and previous.closed
    repo.index.close()
    reopened = KnowledgeRepository(repo.services, extractor=SyntheticExtractor(),
        embedder=SyntheticEmbedder(), index=FaultIndex(repo._selected_index_path()))
    def no_build(*args):
        pytest.fail('A ready publication must not be rebuilt for retirement retry')
    reopened.embedder.embed = no_build
    result = reopened.rebuild_index()
    assert result == {**published, 'cleanup_pending': False}
    assert reopened.index.path.exists() and not previous.path.exists()


def test_failed_candidate_close_retains_handle_until_cleanup_and_preserves_original_error(repository, monkeypatch):
    repo = repository
    repo.import_text('Synthetic candidate failure')
    candidate = None
    class Rejected(FaultIndex):
        def validate_passages(self, identities):
            raise ApiError('synthetic_rejected', 'Synthetic rejected candidate', 503, True)
    def factory(path, dimensions):
        nonlocal candidate
        candidate = Rejected(path, dimensions)
        candidate.fail_close = True
        return candidate
    monkeypatch.setattr('renulus.knowledge.repository.LanceIndex', factory)
    old = repo.index
    with pytest.raises(ApiError) as error:
        repo.rebuild_index()
    assert error.value.code == 'synthetic_rejected'
    assert repo.index is old and candidate.path.exists() and not candidate.closed
    assert repo.cleanup()
    candidate.fail_close = False
    assert repo.cleanup() == []
    assert candidate.closed and not candidate.path.exists()


def test_cleanup_revalidates_sweep_intent_before_destructive_call(repository, monkeypatch):
    repo = repository
    item = repo.import_text('Synthetic later activation')
    repo.db.execute('UPDATE knowledge_documents SET active_revision=NULL WHERE id=?', (item['document_id'],))
    repo.db.execute("UPDATE knowledge_revisions SET status='failed' WHERE id=?", (item['revision_id'],))
    repo.db.execute('INSERT INTO knowledge_cleanup(revision_id,remove_original,created_at) VALUES(?,1,?)',
        (item['revision_id'], '2026-10-12'))
    fetch_all = repo.db.fetch_all
    def activate_after_selection(sql, parameters=()):
        selected = fetch_all(sql, parameters)
        if sql.startswith('SELECT c.revision_id,w.retry_after'):
            repo.db.execute('UPDATE knowledge_documents SET active_revision=? WHERE id=?',
                (item['revision_id'], item['document_id']))
            repo.db.execute("UPDATE knowledge_revisions SET status='ready' WHERE id=?", (item['revision_id'],))
        return selected
    monkeypatch.setattr(repo.db, 'fetch_all', activate_after_selection)
    before = list(repo.index.removed)
    assert repo.cleanup() == []
    assert repo.index.removed == before
    assert repo.original(item['revision_id'])[0].exists()


def test_restore_reconstructs_removal_fence_without_resetting_owned_retirement(repository):
    repo = repository
    repo.services.registry['knowledge'] = repo
    item = interrupted(repo)
    repo.index.fail_remove = True
    repo.recover()
    bundle = export_records(repo.services)
    token = 'k/' + 'e' * 32
    retired = FaultIndex(repo.paths.indexes / token)
    retired.fail_close = True
    repo._retired_indexes[token] = retired
    with repo.db.transaction() as conn:
        repo._work_in(conn, 'retirement', token, token)
        conn.execute("INSERT INTO knowledge_index_work(kind,target,generation,passages) VALUES('publication',?,?,1)",
            ('index_' + 'f' * 32, repo._index_token()))
    recovery = Recovery(repo.services)
    result = recovery.restore_json(bundle, confirm_backup_date=True)
    assert result['rebuild']['status'] == 'required'
    assert not repo.db.fetch_all("SELECT * FROM knowledge_index_work WHERE kind IN ('publication','removal')")
    assert repo.db.fetch_one("SELECT 1 FROM knowledge_index_work WHERE kind='retirement' AND target=?", (token,))
    assert repo._retired_indexes[token] is retired and not retired.closed
    assert repo.next_queued_job() is None
    assert repo.run_job(item['job']['id'])['state'] == 'queued'
    assert repo.cleanup()
    assert repo.db.fetch_one("SELECT 1 FROM knowledge_index_work WHERE kind='removal' AND target=?", (item['revision_id'],))
    assert retired.path.exists()
    repo.index.fail_remove = False
    retired.fail_close = False
    assert repo.cleanup() == []
    assert repo.run_job(item['job']['id'])['state'] == 'ready'
    assert retired.closed and not retired.path.exists()


def test_worker_retries_due_fence_without_restarting_or_duplicate_staging(repository, monkeypatch):
    repo = repository
    item = interrupted(repo)
    clock = [1000.]
    monkeypatch.setattr('renulus.knowledge.repository.time.time', lambda: clock[0])
    repo.index.fail_remove = True
    worker = IngestionWorker(repo)
    staged = Event()
    stage = repo.index.stage
    def observed(rows, **kwargs):
        assert not any(r['revision_id'] == item['revision_id'] for r in repo.index.rows)
        stage(rows, **kwargs)
        staged.set()
    repo.index.stage = observed
    try:
        worker.start()
        assert repo.get_job(item['job']['id'])['state'] == 'queued'
        assert not staged.is_set()
        repo.index.fail_remove = False
        clock[0] = 1002.
        worker.wake()
        assert staged.wait(5)
    finally:
        worker.stop(None)
    assert repo.get_job(item['job']['id'])['state'] == 'ready'
    assert len(repo.index.rows) == 1 and worker.status()['settled']


def test_removal_sweeps_are_bounded_and_remaining_intent_stays_durable(repository):
    from renulus.knowledge.repository import CLEANUP_SWEEP
    repo = repository
    items = [repo.import_text('Synthetic bounded cleanup', process=False)
             for _ in range(CLEANUP_SWEEP + 1)]
    with repo.db.transaction() as conn:
        for item in items:
            repo._cancel_in(conn, item['job']['id'], item['revision_id'], 'synthetic-cancel')
    assert repo.cleanup()
    assert len(repo.index.removed) == CLEANUP_SWEEP
    assert len(repo.db.fetch_all('SELECT * FROM knowledge_cleanup')) == 1
    assert repo.cleanup() == []
    assert len(repo.index.removed) == CLEANUP_SWEEP + 1


def test_failed_table_open_reuses_its_still_owned_connection(tmp_path, monkeypatch):
    import sys
    from types import SimpleNamespace
    opened, tables = [], []
    class Native:
        def __init__(self):
            self.closed = False
        def close(self):
            self.closed = True
    class Connection:
        def __init__(self):
            self._conn = Native()
            self.calls = 0
        def create_table(self, name, *, schema, exist_ok):
            self.calls += 1
            if self.calls == 1:
                raise OSError('Synthetic native table-open failure')
            table = SimpleNamespace(schema=schema, _table=Native())
            tables.append(table)
            return table
    def connect(path):
        connection = Connection()
        opened.append(connection)
        return connection
    monkeypatch.setitem(sys.modules, 'lancedb', SimpleNamespace(connect=connect))
    index = LanceIndex(tmp_path / 'index')
    with pytest.raises(OSError):
        index._open()
    assert index._connection is opened[0]
    assert index._open() is tables[0]
    assert len(opened) == 1
    index.close()
    assert opened[0]._conn.closed and tables[0]._table.closed
