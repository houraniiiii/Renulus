"""Follow-up 15 normative checks: tiny synthetic data; destructive APIs intercepted."""
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

from renulus.contracts import ApiError
from renulus.knowledge.engines import LanceIndex
from renulus.knowledge.ownership import NativeOwnership, MIN_FREE_BYTES
from renulus.knowledge.worker import IngestionWorker
from renulus.storage import filesystem as native
from test_index_maintenance import repository as baseline_repository


@pytest.fixture
def repository(tmp_path):
    fixture = baseline_repository.__wrapped__(tmp_path)
    repo = next(fixture)
    try:
        yield repo
    finally:
        # Explicit process-end model only, never product retirement or deletion.
        # Tests above assert live pins/debt before this portable model teardown.
        repo._owner.fs.held.clear()
        repo._closed = True
        with pytest.raises(StopIteration):
            next(fixture)
from test_storage_reliability import SyntheticFilesystem, synthetic_owner


@pytest.mark.parametrize('parent', [False, True])
def test_created_native_identity_retained_until_generation_pin(tmp_path, parent):
    target = tmp_path / 'missing' / 'generation' if parent else tmp_path / 'generation'
    attacked = target.parent if parent else target
    moved = attacked.with_name(attacked.name + '-preserved')
    attempts = []
    class Intercept:
        def __getattr__(self, name):
            return getattr(native, name)
        def attack(self, path):
            if Path(path) != attacked:
                return
            try:
                Path(path).rename(moved)
            except OSError:
                attempts.append('blocked-by-retained-creation')
            else:
                attempts.append('substituted')
                Path(path).mkdir()
                (Path(path) / 'unknown.txt').write_bytes(b'synthetic unknown replacement')
        def mkdir_exact(self, path):
            info = native.mkdir_exact(path)
            self.attack(path)
            return info
        @contextmanager
        def created_directory(self, path):
            with native.created_directory(path) as info:
                self.attack(path)
                yield info
    owner = NativeOwnership(target.with_suffix('.native-owner'), filesystem=Intercept())
    try:
        owner.acquire_for_path(target)
        assert attempts == ['blocked-by-retained-creation']
        with pytest.raises(OSError):
            attacked.rename(moved)
    finally:
        owner.close()


def forbid_tree_delete(monkeypatch):
    calls = []
    def forbidden(path, *args, **kwargs):
        calls.append(str(path))
        raise AssertionError('Whole-tree disposition intercepted, never executed')
    monkeypatch.setattr('shutil.rmtree', forbidden)
    return calls


@pytest.mark.parametrize('late_ads', [False, True])
def test_retirement_preserves_unknown_streams_and_pins(repository, monkeypatch, late_ads):
    repo = repository
    token = 'k/' + 'a' * 32
    path = repo._index_folder(token)
    path.mkdir(parents=True)
    marker = path / 'unknown.txt'
    marker.write_bytes(b'synthetic unknown')
    calls = forbid_tree_delete(monkeypatch)
    repo._work_failed('retirement', token, token, 'index_cleanup_pending')
    assert repo.cleanup()
    if late_ads:
        Path(str(marker) + ':late-synthetic').write_bytes(b'synthetic late ADS')
    assert repo.cleanup()
    assert calls == []
    assert marker.read_bytes() == b'synthetic unknown'
    if late_ads:
        assert Path(str(marker) + ':late-synthetic').read_bytes() == b'synthetic late ADS'
    owner = repo._retirement_owners[token]
    assert owner._path_pin is not None
    owner.require()
    state = IngestionWorker(repo).status()['index_maintenance']
    assert state['pending'] and state['retirement_pending'] == 1
    assert state['error_code'] == 'index_cleanup_pending' and state['retry_after'] > 0
    with pytest.raises(ApiError):
        repo.close()


def test_retirement_path_substitution_checkpoint_cannot_delete(repository, monkeypatch):
    repo = repository
    token = 'k/' + 'b' * 32
    path = repo._index_folder(token)
    path.mkdir(parents=True)
    moved = path.with_name('preserved-synthetic-generation')
    remove = repo._remove_index_folder
    calls = forbid_tree_delete(monkeypatch)
    def substitute(folder):
        # Portable model intentionally allows replacement; production pins forbid it.
        path.rename(moved)
        path.mkdir()
        (path / 'foreign.txt').write_bytes(b'synthetic replacement')
        return remove(folder)
    monkeypatch.setattr(repo, '_remove_index_folder', substitute)
    repo._work_failed('retirement', token, token, 'index_cleanup_pending')
    assert repo.cleanup()
    assert calls == [] and (path / 'foreign.txt').read_bytes() == b'synthetic replacement'
    assert moved.exists()
    assert repo._retirement_owners[token]._path_pin is not None


def test_truly_absent_generation_parent_acknowledged_without_creation(repository):
    repo = repository
    token = 'k/' + 'c' * 32
    assert not repo._index_folder(token).parent.exists()
    repo._work_failed('retirement', token, token, 'index_cleanup_pending')
    assert repo.cleanup() == []
    assert not repo._index_folder(token).parent.exists()
    assert not repo.db.fetch_all("SELECT * FROM knowledge_index_work WHERE kind='retirement'")


def test_retirement_status_has_deterministic_backoff(repository, monkeypatch):
    repo = repository
    monkeypatch.setattr('renulus.knowledge.repository.time.time', lambda: 1000.)
    for char in ('d', 'e'):
        token = 'k/' + char * 32
        repo._index_folder(token).mkdir(parents=True)
        repo._work_failed('retirement', token, token, 'index_cleanup_pending')
    state = repo.maintenance_status()
    assert state['pending'] and state['retirement_pending'] == 2
    assert state['error_code'] == 'index_cleanup_pending' and state['retry_after'] == 1001.
    repo.cleanup(force=False)
    assert all(row['attempts'] == 1 for row in repo.db.fetch_all("SELECT * FROM knowledge_index_work WHERE kind='retirement'"))


def test_removal_capacity_precedes_native_call_and_keeps_intent(repository):
    repo = repository
    item = repo.import_text('Tiny synthetic removal capacity source')
    repo.cleanup(force=False, queue_drained=True)
    repo._owner.fs.free = MIN_FREE_BYTES
    before = list(repo.index.removed)
    result = repo.delete_document(item['document_id'])
    assert result['cleanup_pending'] and repo.index.removed == before
    row = repo.db.fetch_one("SELECT * FROM knowledge_index_work WHERE kind='removal'")
    assert row['completed_sequence'] == 0 and row['error_code'] == 'knowledge_low_space'
    status = repo.maintenance_status()
    assert status['pending'] and status['error_code'] == 'knowledge_low_space'
    assert status['retry_after'] == row['retry_after']
    assert repo.db.fetch_one("SELECT * FROM knowledge_cleanup")
    repo._owner.fs.free = MIN_FREE_BYTES + 1024 ** 3
    assert repo.cleanup()  # Explicit retry settles rows, not uncertain originals.
    assert len(repo.index.removed) == len(before) + 1
    row = repo.db.fetch_one("SELECT * FROM knowledge_index_work WHERE kind='removal'")
    assert row['completed_sequence'] == 1 and row['error_code'] == 'original_cleanup_pending'
    removed = list(repo.index.removed)
    assert repo.cleanup() and repo.index.removed == removed


@pytest.mark.parametrize('unknown', ['sibling', 'ads', 'substitution'])
def test_original_disposition_refuses_uncertain_tree_preserves_row_ack(repository, monkeypatch, unknown):
    repo = repository
    item = repo.import_text('Tiny synthetic retained original')
    folder = repo._folder(item['document_id'], item['revision_id'])
    original = folder / 'original.txt'
    if unknown == 'substitution':
        moved = folder.with_name(folder.name + '-preserved')
        folder.rename(moved)
        folder.mkdir()
        marker = folder / 'replacement.txt'
    elif unknown == 'ads':
        marker = Path(str(original) + ':unknown-synthetic')
    else:
        marker = folder / 'unknown.txt'
    marker.write_bytes(b'unknown synthetic bytes')
    calls = forbid_tree_delete(monkeypatch)
    assert repo.delete_document(item['document_id'])['cleanup_pending']
    assert calls == [] and marker.read_bytes() == b'unknown synthetic bytes'
    row = repo.db.fetch_one("SELECT * FROM knowledge_index_work WHERE kind='removal'")
    assert row['completed_sequence'] == 1 and row['error_code'] == 'original_cleanup_pending'
    removed = list(repo.index.removed)
    assert repo.cleanup() and repo.index.removed == removed
    assert repo.db.fetch_one('SELECT original_path FROM knowledge_revisions WHERE id=?', (item['revision_id'],))['original_path'] is not None
    assert repo.maintenance_status()['original_pending'] == 1


@pytest.mark.parametrize('close_fails', [False, True])
def test_incompatible_candidate_never_cached(repository, monkeypatch, close_fails):
    model = repository._owner.fs
    index = LanceIndex(repository.paths.indexes / 'incompatible', dimensions=384,
        ownership_factory=lambda token: synthetic_owner(token, model))
    calls = []
    def close():
        calls.append('close')
        if close_fails:
            raise OSError('Synthetic unresolved rejected-table close')
    table = SimpleNamespace(schema=SimpleNamespace(field=lambda name: SimpleNamespace(type=SimpleNamespace(list_size=3))),
        _table=SimpleNamespace(close=close))
    connection = SimpleNamespace(create_table=lambda *args, **kwargs: table, _conn=SimpleNamespace(close=lambda: None))
    monkeypatch.setitem(sys.modules, 'lancedb', SimpleNamespace(connect=lambda path: connection))
    monkeypatch.setitem(sys.modules, 'pyarrow', SimpleNamespace(schema=lambda value: value, field=lambda *args: args,
        string=lambda: 'string', list_=lambda *args: args, float32=lambda: 'float32'))
    for attempt in range(2):
        with pytest.raises(ApiError) as error:
            index._open()
        assert error.value.code == ('index_close_pending' if close_fails and attempt else 'incompatible_index')
        assert index._table is None
    if close_fails:
        assert index._rejected_table is table
        index._ownership.require()
        close_fails = False
    index.close()
    assert len(calls) >= 2


def test_creation_identity_mismatch_refused_without_adoption(tmp_path):
    model = SyntheticFilesystem()
    create = model.created_directory
    @contextmanager
    def mismatched(path):
        with create(path):
            (Path(path) / 'unknown.txt').write_bytes(b'synthetic unknown')
            yield SimpleNamespace(identity=('not-the-created-identity',), directory=True)
    model.created_directory = mismatched
    owner = NativeOwnership(tmp_path / 'generation.native-owner', filesystem=model)
    with pytest.raises(ApiError) as error:
        owner.acquire_for_path(tmp_path / 'generation')
    assert error.value.code == 'index_owner_busy'
    assert (tmp_path / 'generation/unknown.txt').read_bytes() == b'synthetic unknown'
    assert owner._guard is None and not model.held


def test_absent_original_spelling_is_not_proof_of_disposition(repository, monkeypatch):
    repo = repository
    item = repo.import_text('Synthetic renamed original')
    folder = repo._folder(item['document_id'], item['revision_id'])
    moved = folder.with_name(folder.name + '-preserved-original')
    folder.rename(moved)
    calls = forbid_tree_delete(monkeypatch)
    assert repo.delete_document(item['document_id'])['cleanup_pending']
    assert calls == [] and (moved / 'original.txt').read_text() == 'Synthetic renamed original'
    assert repo.db.fetch_one('SELECT original_path FROM knowledge_revisions WHERE id=?', (item['revision_id'],))['original_path']
    assert repo.maintenance_status()['original_pending'] == 1


def test_failed_import_publication_preserves_unregistered_original_and_error(repository, monkeypatch):
    repo = repository
    transaction = repo.db.transaction
    @contextmanager
    def fail_transaction():
        with transaction() as conn:
            if list(repo.paths.library.rglob('original.txt')):
                raise ApiError('synthetic_publication_failed', 'Synthetic publication failure', 503, True)
            yield conn
    monkeypatch.setattr(repo.db, 'transaction', fail_transaction)
    calls = forbid_tree_delete(monkeypatch)
    with pytest.raises(ApiError) as error:
        repo.import_text('Synthetic unpublished retained original')
    assert error.value.code == 'synthetic_publication_failed'
    assert calls == []
    originals = list(repo.paths.library.rglob('original.txt'))
    assert len(originals) == 1 and originals[0].read_bytes() == b''
    # Follow-up 16 records the preintent and stops before body writes when later
    # identity recording fails; the preserved empty native claim is not orphaned.
    intent = repo.db.fetch_one('SELECT * FROM knowledge_index_original_publications')
    assert intent['original_path'] == str(originals[0])
    assert intent['expected_bytes'] == len(b'Synthetic unpublished retained original')
    assert not repo.db.fetch_all('SELECT * FROM knowledge_revisions')


def test_removal_forecast_committed_dirty_intent_without_sqlite_writer(repository):
    repo = repository
    item = repo.import_text('Synthetic manifest-growth source')
    repo.cleanup(force=False, queue_drained=True)
    preflight = repo.capacity.preflight
    operations = []
    def checked(target, **kwargs):
        if kwargs['operation'] == 'removal':
            assert repo.db._active_writers == 0
            debt = repo.db.fetch_one("SELECT * FROM knowledge_index_work WHERE kind='maintenance' AND target='passages'")
            assert debt['dirty_sequence'] > debt['completed_sequence']
            operations.append('forecast')
        return preflight(target, **kwargs)
    remove = repo.index.remove
    def checked_remove(revision):
        assert operations == ['forecast'] and repo.db._active_writers == 0
        operations.append('remove')
        return remove(revision)
    repo.capacity.preflight = checked
    repo.index.remove = checked_remove
    assert repo.delete_document(item['document_id'])['cleanup_pending']
    assert operations == ['forecast', 'remove']


def test_incompatible_nonvector_schema_refused_before_cache(repository, monkeypatch):
    index = LanceIndex(repository.paths.indexes / 'wrong-schema',
        ownership_factory=lambda token: synthetic_owner(token, repository._owner.fs))
    schema = SimpleNamespace(field=lambda name: SimpleNamespace(type=SimpleNamespace(list_size=384)),
        equals=lambda expected, **kwargs: False)
    table = SimpleNamespace(schema=schema, _table=SimpleNamespace(close=lambda: None))
    connection = SimpleNamespace(create_table=lambda *args, **kwargs: table, _conn=SimpleNamespace(close=lambda: None))
    monkeypatch.setitem(sys.modules, 'lancedb', SimpleNamespace(connect=lambda path: connection))
    for _ in range(2):
        with pytest.raises(ApiError) as error:
            index._open()
        assert error.value.code == 'incompatible_index' and index._table is None
    index.close()
