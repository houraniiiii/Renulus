"""Index16 original-publication intent regressions; tiny synthetic inputs only."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from renulus.contracts import ApiError
from renulus.knowledge.repository import KnowledgeRepository
from renulus.knowledge.ownership import KnowledgeCapacity
from renulus.services import Services
from renulus.storage.backup import eligible_table, export_records
from test_index_maintenance import repository, MaintenanceIndex
from test_repository import SyntheticEmbedder, SyntheticExtractor
from test_storage_reliability import synthetic_owner

TABLE = 'knowledge_index_original_publications'


def intents(repo):
    return repo.db.fetch_all('SELECT * FROM ' + TABLE + ' ORDER BY revision_id')


def reopen(repo):
    repo.close()
    return KnowledgeRepository(Services(repo.paths, repo.db), extractor=SyntheticExtractor(),
        embedder=SyntheticEmbedder(), index=MaintenanceIndex(repo.index.path),
        owner=synthetic_owner(repo.paths.state / 'knowledge-native-owner', repo._owner.fs),
        capacity=KnowledgeCapacity(filesystem=repo._owner.fs))


def test_success_intent_exists_before_allocation_and_clears_with_canonical_commit(repository):
    repo = repository
    fs = repo._owner.fs
    create = fs.created_directory
    observed = []
    @contextmanager
    def checked(path):
        row = intents(repo)[0]
        assert row['phase'] in ('prepared', 'creating')
        assert row['expected_bytes'] == len(b'Synthetic intent publication')
        assert row['sha256'] == hashlib.sha256(b'Synthetic intent publication').hexdigest()
        assert repo.db._active_writers == 0
        observed.append(Path(path))
        with create(path) as created:
            yield created
    fs.created_directory = checked
    item = repo.import_text('Synthetic intent publication', process=False)
    assert observed and intents(repo) == []
    assert repo.db.fetch_one('SELECT original_path FROM knowledge_revisions WHERE id=?', (item['revision_id'],))


def test_intent_commit_failure_refuses_before_any_folder_or_file_allocation(repository, monkeypatch):
    repo = repository
    transaction = repo.db.transaction
    @contextmanager
    def fail():
        with transaction() as conn:
            yield conn
            if conn.execute('SELECT 1 FROM ' + TABLE).fetchone():
                raise OSError('Synthetic intent commit failure')
    monkeypatch.setattr(repo.db, 'transaction', fail)
    with pytest.raises(ApiError) as error:
        repo.import_text('Synthetic cannot persist intent', process=False)
    assert error.value.code == 'original_intent_unavailable'
    assert not (repo.paths.library / 'knowledge').exists()
    assert intents(repo) == []


def test_failed_write_retains_preintent_known_identities_and_expectations(repository):
    repo = repository
    create = repo._owner.fs.created_file
    @contextmanager
    def fail(path, **kwargs):
        with create(path, **kwargs) as created:
            def publish(data):
                created.publish(data[:3])
                raise OSError('Synthetic partial original write')
            yield SimpleNamespace(info=created.info, publish=publish, check=created.check, read=created.read)
    repo._owner.fs.created_file = fail
    with pytest.raises(OSError):
        repo.import_text('Synthetic partial retained original', process=False)
    row = intents(repo)[0]
    assert row['expected_bytes'] == len(b'Synthetic partial retained original')
    known = json.loads(row['identities_json'])
    assert known['file'] is not None and known['directories']
    assert Path(row['original_path']).read_bytes() == b'Syn'
    assert not repo.db.fetch_all('SELECT * FROM knowledge_revisions')
    assert 'Synthetic partial retained original' not in json.dumps(row)
    status = repo.maintenance_status()
    assert status['original_publication_pending'] == 1 and status['removal_pending'] == 0
    assert status['pending'] and status['error_code'] == 'original_publication_pending'


def test_failed_canonical_commit_retains_written_original_and_exact_intent(repository, monkeypatch):
    repo = repository
    transaction = repo.db.transaction
    @contextmanager
    def fail():
        with transaction() as conn:
            yield conn
            if conn.execute('SELECT 1 FROM knowledge_revisions').fetchone():
                raise OSError('Synthetic canonical commit failure')
    monkeypatch.setattr(repo.db, 'transaction', fail)
    with pytest.raises(OSError):
        repo.import_text('Synthetic uncommitted original', process=False)
    row = intents(repo)[0]
    assert json.loads(row['identities_json'])['file']
    assert Path(row['original_path']).read_bytes() == b'Synthetic uncommitted original'
    assert not repo.db.fetch_all('SELECT * FROM knowledge_revisions')
    assert row['phase'] in ('written', 'held')


@pytest.mark.parametrize('boundary', ['before-create', 'after-directory', 'after-file', 'after-write'])
def test_interruption_reopen_holds_recorded_publication_without_adoption(repository, boundary):
    repo = repository
    class Interrupted(BaseException):
        pass
    fs = repo._owner.fs
    if boundary in ('before-create', 'after-directory'):
        create = fs.created_directory
        @contextmanager
        def interrupt(path):
            if boundary == 'before-create':
                raise Interrupted()
            with create(path):
                raise Interrupted()  # Created, but identity recording has not run yet.
                yield  # contextmanager generator, deliberately unreachable
        fs.created_directory = interrupt
    else:
        create = fs.created_file
        @contextmanager
        def interrupt(path, **kwargs):
            with create(path, **kwargs) as created:
                if boundary == 'after-file':
                    raise Interrupted()
                def publish(data):
                    created.publish(data)
                    raise Interrupted()
                yield SimpleNamespace(info=created.info, publish=publish, check=created.check, read=created.read)
        fs.created_file = interrupt
    with pytest.raises(Interrupted):
        repo.import_text('Synthetic process boundary', idempotency_key='boundary-key', process=False)
    before = intents(repo)[0]
    new = reopen(repo)
    try:
        assert new.recover()
        after = intents(new)[0]
        assert after['revision_id'] == before['revision_id']
        assert after['original_path'] == before['original_path']
        assert after['identities_json'] == before['identities_json']
        assert after['phase'].startswith('held')
        assert not new.db.fetch_all('SELECT * FROM knowledge_revisions')
        with pytest.raises(ApiError) as error:
            new.import_text('Synthetic process boundary', idempotency_key='boundary-key', process=False)
        assert error.value.code == 'original_publication_pending'
        assert len(intents(new)) == 1
    finally:
        new.close()


def test_pending_count_cap_refuses_before_extra_bytes(repository):
    repo = repository
    fs = repo._owner.fs
    create = fs.created_file
    @contextmanager
    def fail(path, **kwargs):
        with create(path, **kwargs) as created:
            def publish(data):
                raise OSError('Synthetic retained empty original')
            yield SimpleNamespace(info=created.info, publish=publish, check=created.check, read=created.read)
    fs.created_file = fail
    status = repo.maintenance_status()
    limit = status['original_publication_limit']
    assert type(limit) is int and 0 < limit <= 64
    for number in range(limit):
        with pytest.raises(OSError):
            repo.import_text('Synthetic capped publication', idempotency_key='cap-' + str(number), process=False)
    before = set(repo.paths.library.rglob('*'))
    status = repo.maintenance_status()
    assert status['original_publication_pending'] == limit and status['original_publication_admission_held']
    with pytest.raises(ApiError) as error:
        repo.import_text('Synthetic cap refusal', idempotency_key='beyond-cap', process=False)
    assert error.value.code == 'original_publication_limit'
    assert set(repo.paths.library.rglob('*')) == before and len(intents(repo)) == limit
    import sqlite3
    row = intents(repo)[0]
    row.update(revision_id='rev_' + 'f' * 32, operation_id='f' * 64)
    columns = ','.join(row)
    with pytest.raises(sqlite3.IntegrityError):
        repo.db.execute('INSERT INTO ' + TABLE + '(' + columns + ') VALUES(' + ','.join('?' for _ in row) + ')', tuple(row.values()))
    assert len(intents(repo)) == limit  # Independent SQL cap, not only caller convention.


def test_local_intent_excluded_from_records_backup_without_canonical_shape_change(repository):
    repo = repository
    assert not eligible_table(TABLE)
    item = repo.import_text('Synthetic canonical backup shape', process=False)
    assert intents(repo) == []
    records = export_records(repo.services)['records']
    assert TABLE not in records
    assert set(records['knowledge_cleanup']) == set()
    assert set(records['knowledge_jobs'][0]) == {'id', 'revision_id', 'idempotency_key', 'request_hash', 'state', 'phase',
        'error_code', 'error_message', 'created_at', 'finished_at'}
    assert records['knowledge_revisions'][0]['id'] == item['revision_id']


def test_recovery_visits_only_recorded_paths_preserves_unknown_sibling_and_replacement(repository):
    repo = repository
    create = repo._owner.fs.created_file
    @contextmanager
    def fail(path, **kwargs):
        with create(path, **kwargs) as created:
            def publish(data):
                created.publish(data)
                raise OSError('Synthetic pending exact publication')
            yield SimpleNamespace(info=created.info, publish=publish, check=created.check, read=created.read)
    repo._owner.fs.created_file = fail
    with pytest.raises(OSError):
        repo.import_text('Synthetic unchanged expected original', process=False)
    row = intents(repo)[0]
    original = Path(row['original_path'])
    moved = original.parent.with_name(original.parent.name + '-preserved')
    original.parent.rename(moved)
    original.parent.mkdir()
    original.write_bytes(b'Synthetic unrelated replacement')
    unknown = repo.paths.library / 'not-recorded'
    unknown.mkdir()
    marker = unknown / 'unknown.txt'
    marker.write_bytes(b'Unknown synthetic sibling')
    repo.recover()
    after = intents(repo)[0]
    assert after['phase'] == 'held_changed'
    assert after['identities_json'] == row['identities_json']
    assert original.read_bytes() == b'Synthetic unrelated replacement'
    assert marker.read_bytes() == b'Unknown synthetic sibling'
    assert (moved / original.name).read_bytes() == b'Synthetic unchanged expected original'
    assert not repo.db.fetch_all('SELECT * FROM knowledge_revisions')


def test_identity_update_failure_keeps_preintent_and_stops_more_allocation(repository, monkeypatch):
    repo = repository
    transaction = repo.db.transaction
    @contextmanager
    def fail_update():
        with transaction() as conn:
            yield conn
            row = conn.execute('SELECT * FROM ' + TABLE).fetchone()
            if row and row['phase'] != 'prepared':
                raise OSError('Synthetic later intent update failure')
    monkeypatch.setattr(repo.db, 'transaction', fail_update)
    with pytest.raises(OSError):
        repo.import_text('Synthetic preintent survives', process=False)
    row = intents(repo)[0]
    assert row['phase'] == 'prepared'
    assert not Path(row['original_path']).exists()
    assert repo.maintenance_status()['original_publication_pending'] == 1


def test_recovery_root_replacement_is_held_without_adoption(repository):
    repo = repository
    create = repo._owner.fs.created_file
    @contextmanager
    def fail(path, **kwargs):
        with create(path, **kwargs) as created:
            def publish(data):
                created.publish(data)
                raise OSError('Synthetic root checkpoint')
            yield SimpleNamespace(info=created.info, publish=publish, check=created.check, read=created.read)
    repo._owner.fs.created_file = fail
    with pytest.raises(OSError):
        repo.import_text('Synthetic original under known root', process=False)
    before = intents(repo)[0]
    preserved = repo.paths.library.with_name('preserved-library-root')
    repo.paths.library.rename(preserved)
    repo.paths.library.mkdir()
    marker = repo.paths.library / 'unknown-root.txt'
    marker.write_bytes(b'Synthetic replacement root')
    repo.recover()
    assert intents(repo)[0]['phase'] == 'held_changed'
    assert intents(repo)[0]['identities_json'] == before['identities_json']
    assert marker.read_bytes() == b'Synthetic replacement root'
    assert list(preserved.rglob('original.txt'))[0].read_bytes() == b'Synthetic original under known root'


def test_restore_does_not_import_or_erase_local_original_intent(repository):
    from renulus.storage.recovery import Recovery
    repo = repository
    repo.services.registry['knowledge'] = repo
    bundle = export_records(repo.services)
    create = repo._owner.fs.created_file
    @contextmanager
    def fail(path, **kwargs):
        with create(path, **kwargs) as created:
            def publish(data):
                raise OSError('Synthetic local recovery debt')
            yield SimpleNamespace(info=created.info, publish=publish, check=created.check, read=created.read)
    repo._owner.fs.created_file = fail
    with pytest.raises(OSError):
        repo.import_text('Synthetic local retained attempt', process=False)
    before = intents(repo)[0]
    result = Recovery(repo.services).restore_json(bundle, confirm_backup_date=True)
    assert result['rebuild']['status'] == 'required'
    after = intents(repo)[0]
    assert after == before and TABLE not in bundle['records']
    assert repo.maintenance_status()['original_publication_pending'] == 1


def test_writer_size_bound_refuses_before_intent_or_bytes(repository, monkeypatch):
    repo = repository
    monkeypatch.setattr('renulus.knowledge.repository.ORIGINAL_NATIVE_MAX_BYTES', 8)
    with pytest.raises(ApiError) as error:
        repo.import_text('Synthetic oversized for injected writer boundary', process=False)
    assert error.value.code == 'original_publication_size_limit'
    assert intents(repo) == [] and not (repo.paths.library / 'knowledge').exists()


@pytest.mark.parametrize('boundary', ['before-create', 'after-directory', 'after-file', 'after-write'])
def test_actual_process_exit_preserves_durable_intent_and_no_replay(tmp_path, boundary):
    import subprocess
    import sys
    from renulus.storage import AppPaths, Database
    from renulus.knowledge.ownership import NativeOwnership
    from test_storage_reliability import SyntheticFilesystem
    runtime = Path(__file__).parents[2] / 'runtime'
    tests = Path(__file__).parent
    code = """
import os, sys
from pathlib import Path
from contextlib import contextmanager
sys.dont_write_bytecode = True
sys.path[:0] = [sys.argv[1], sys.argv[2]]
from renulus.knowledge.repository import KnowledgeRepository
from renulus.knowledge.ownership import NativeOwnership, KnowledgeCapacity
from renulus.storage import AppPaths, Database, filesystem as fs
from renulus.services import Services
from test_index_maintenance import MaintenanceIndex
from test_repository import SyntheticExtractor, SyntheticEmbedder
from test_storage_reliability import SyntheticFilesystem
paths = AppPaths.create(Path(sys.argv[3]) / 'profile')
db = Database(paths.database)
module = Path(sys.argv[1]) / 'renulus/knowledge'
db.apply_migration('knowledge-001', (module / 'schema.sql').read_text())
for migration in sorted((module / 'migrations').glob('*.sql')):
    db.apply_migration('knowledge-' + migration.stem, migration.read_text())
repo = KnowledgeRepository(Services(paths, db), extractor=SyntheticExtractor(), embedder=SyntheticEmbedder(),
    index=MaintenanceIndex(paths.indexes / 'knowledge'), owner=NativeOwnership(paths.state / 'knowledge-native-owner'),
    capacity=KnowledgeCapacity(filesystem=SyntheticFilesystem()))
boundary = sys.argv[4]
if boundary in ('before-create','after-directory'):
    create = fs.created_directory
    @contextmanager
    def interrupted(path):
        if boundary == 'before-create':
            os._exit(73)
        with create(path):
            os._exit(73)
            yield
    fs.created_directory = interrupted
else:
    create = fs.created_file
    @contextmanager
    def interrupted(path, **kwargs):
        with create(path, **kwargs) as created:
            if boundary == 'after-file':
                os._exit(73)
            from renulus.knowledge.original_io import RetainedOriginalIO
            flush = RetainedOriginalIO._flush
            def stop(self):
                flush(self)
                os._exit(73)
            RetainedOriginalIO._flush = stop
            yield created
    fs.created_file = interrupted
repo.import_text('Synthetic actual process boundary', idempotency_key='native-boundary', process=False)
raise AssertionError('Interruption boundary did not fire')
"""
    result = subprocess.run([sys.executable, '-I', '-c', code, str(runtime), str(tests), str(tmp_path), boundary],
        capture_output=True, text=True, timeout=20)
    assert result.returncode == 73, result.stderr
    paths = AppPaths.create(tmp_path / 'profile')
    db = Database(paths.database)
    before = db.fetch_one('SELECT * FROM ' + TABLE)
    assert before and not db.fetch_all('SELECT * FROM knowledge_revisions')
    new = KnowledgeRepository(Services(paths, db), extractor=SyntheticExtractor(), embedder=SyntheticEmbedder(),
        index=MaintenanceIndex(paths.indexes / 'knowledge'), owner=NativeOwnership(paths.state / 'knowledge-native-owner'),
        capacity=KnowledgeCapacity(filesystem=SyntheticFilesystem()))
    try:
        after = intents(new)[0]
        assert after['identities_json'] == before['identities_json'] and after['phase'].startswith('held')
        assert new.recover() and len(intents(new)) == 1
        with pytest.raises(ApiError) as error:
            new.import_text('Synthetic actual process boundary', idempotency_key='native-boundary', process=False)
        assert error.value.code == 'original_publication_pending'
        if boundary == 'after-write':
            original = Path(before['original_path'])
            assert after['phase'] == 'held_matching'
            assert original.read_bytes() == b'Synthetic actual process boundary'
            ads = Path(str(original) + ':unknown-synthetic')
            ads.write_bytes(b'Synthetic late ADS')
            alias = original.with_name('unknown-hardlink.txt')
            alias.hardlink_to(original)
            new.recover()
            assert intents(new)[0]['phase'] in ('held_changed','held_uncertain')
            assert alias.read_bytes() == b'Synthetic actual process boundary'
            assert ads.read_bytes() == b'Synthetic late ADS'
        assert not new.db.fetch_all('SELECT * FROM knowledge_revisions')
    finally:
        new.close()


@pytest.mark.parametrize('race', ['directory', 'file'])
def test_racing_unknown_publication_path_never_adopted_or_overwritten(repository, race):
    repo = repository
    fs = repo._owner.fs
    markers = []
    if race == 'directory':
        create = fs.created_directory
        @contextmanager
        def substitute(path):
            if Path(path).name.startswith('rev_'):
                assert intents(repo)
                Path(path).mkdir()
                marker = Path(path) / 'unknown.txt'
                marker.write_bytes(b'Synthetic racing directory')
                markers.append(marker)
            with create(path) as created:
                yield created
        fs.created_directory = substitute
    else:
        create = fs.created_file
        @contextmanager
        def substitute(path, **kwargs):
            assert intents(repo)
            Path(path).write_bytes(b'Synthetic racing file')
            markers.append(Path(path))
            with create(path, **kwargs) as created:
                yield created
        fs.created_file = substitute
    with pytest.raises(FileExistsError):
        repo.import_text('Synthetic never overwrite racer', idempotency_key='synthetic-private-key', process=False)
    before = intents(repo)[0]
    assert 'synthetic-private-key' not in json.dumps(before)
    assert before['operation_id'] == hashlib.sha256(b'synthetic-private-key').hexdigest()
    assert markers and markers[0].read_bytes() == ('Synthetic racing ' + race).encode()
    repo.recover()
    assert intents(repo)[0]['phase'].startswith('held')
    assert intents(repo)[0]['identities_json'] == before['identities_json']
    assert markers[0].read_bytes() == ('Synthetic racing ' + race).encode()
    assert not repo.db.fetch_all('SELECT * FROM knowledge_revisions')


def test_actual_native_original_publication_commits_and_clears_intent(tmp_path):
    from renulus.storage import AppPaths, Database
    from renulus.knowledge.ownership import NativeOwnership
    from test_storage_reliability import SyntheticFilesystem
    paths = AppPaths.create(tmp_path / 'profile')
    db = Database(paths.database)
    module = Path(__file__).parents[2] / 'runtime/renulus/knowledge'
    db.apply_migration('knowledge-001', (module / 'schema.sql').read_text())
    for migration in sorted((module / 'migrations').glob('*.sql')):
        db.apply_migration('knowledge-' + migration.stem, migration.read_text())
    repo = KnowledgeRepository(Services(paths, db), extractor=SyntheticExtractor(), embedder=SyntheticEmbedder(),
        index=MaintenanceIndex(paths.indexes / 'knowledge'), owner=NativeOwnership(paths.state / 'knowledge-native-owner'),
        capacity=KnowledgeCapacity(filesystem=SyntheticFilesystem()))
    try:
        item = repo.import_text('Synthetic native retained creation', process=False)
        assert intents(repo) == []
        row = repo.db.fetch_one('SELECT original_path FROM knowledge_revisions WHERE id=?', (item['revision_id'],))
        assert Path(row['original_path']).read_bytes() == b'Synthetic native retained creation'
    finally:
        repo.close()
