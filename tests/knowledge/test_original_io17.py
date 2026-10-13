"""64 MiB compatibility and chunked retained-original I/O; synthetic inputs only."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sys

import pytest

from renulus.contracts import ApiError, ContextScope, Scope
from renulus.knowledge.engines import MAX_BYTES
from renulus.knowledge.models import own_text_rights
from renulus.knowledge.ownership import NativeOwnership, KnowledgeCapacity
from renulus.knowledge.repository import KnowledgeRepository
from renulus.services import Services
from renulus.storage import AppPaths, Database, filesystem as fs
from test_index_maintenance import MaintenanceIndex, repository
from test_original_publication16 import intents
from test_repository import SyntheticEmbedder, SyntheticExtractor
from test_storage_reliability import SyntheticFilesystem

INPUT = Path('C:/Renulus/scratch/sr26/index17-input-20261013/synthetic-33m.pdf')
BODY = b'Synthetic retained chunked original'


def native_repo(tmp_path):
    paths = AppPaths.create(tmp_path / 'profile')
    db = Database(paths.database)
    module = Path(__file__).parents[2] / 'runtime/renulus/knowledge'
    db.apply_migration('knowledge-001', (module / 'schema.sql').read_text())
    for migration in sorted((module / 'migrations').glob('*.sql')):
        db.apply_migration('knowledge-' + migration.stem, migration.read_text())
    return KnowledgeRepository(Services(paths, db), extractor=SyntheticExtractor(),
        embedder=SyntheticEmbedder(), index=MaintenanceIndex(paths.indexes / 'knowledge'),
        owner=NativeOwnership(paths.state / 'knowledge-native-owner'),
        capacity=KnowledgeCapacity(filesystem=SyntheticFilesystem()))


def test_actual_33m_pdf_publication_preserves_existing_upload_compatibility(tmp_path):
    repo = native_repo(tmp_path)
    try:
        item = repo.import_file(INPUT, rights=own_text_rights(), process=False)
        row = repo.db.fetch_one('SELECT * FROM knowledge_revisions WHERE id=?', (item['revision_id'],))
        original = Path(row['original_path'])
        assert fs.file_info(original).logical_bytes == 33 * 1024**2
        assert row['bytes'] == 33 * 1024**2 and intents(repo) == []
        with fs.opened_file(original) as retained:
            from renulus.knowledge.original_io import RetainedOriginalIO
            with RetainedOriginalIO(fs, retained, original) as io:
                assert io.sha256(expected_bytes=row['bytes']) == row['sha256']
        assert item['status'] == 'queued'
        assert INPUT.is_file() and INPUT.stat().st_size == 33 * 1024**2
    finally:
        repo.close()


def test_actual_33m_failed_commit_reopens_with_streamed_expected_hash(tmp_path, monkeypatch):
    repo = native_repo(tmp_path)
    transaction = repo.db.transaction
    @contextmanager
    def fail():
        with transaction() as conn:
            yield conn
            if conn.execute('SELECT 1 FROM knowledge_revisions').fetchone():
                raise OSError('Synthetic canonical rollback after 33 MiB original')
    monkeypatch.setattr(repo.db, 'transaction', fail)
    try:
        with pytest.raises(OSError):
            repo.import_file(INPUT, rights=own_text_rights(), process=False)
        before = intents(repo)[0]
        assert before['expected_bytes'] == 33 * 1024**2
        assert fs.file_info(Path(before['original_path'])).logical_bytes == before['expected_bytes']
        assert not repo.db.fetch_all('SELECT * FROM knowledge_revisions')
    finally:
        repo.close()
    new = native_repo(tmp_path)
    try:
        after = intents(new)[0]
        assert after['phase'] == 'held_matching'
        assert after['identities_json'] == before['identities_json']
        assert after['sha256'] == before['sha256']
        assert new.maintenance_status()['original_publication_pending'] == 1
        assert new.maintenance_status()['removal_pending'] == 0
        assert new.recover() and intents(new)[0]['phase'] == 'held_matching'
        assert not new.db.fetch_all('SELECT * FROM knowledge_revisions')
    finally:
        new.close()


def test_above_64m_controlled_input_refuses_before_intent_or_allocation(repository):
    class Oversize:
        def __len__(self):
            return MAX_BYTES + 1
    repo = repository
    before = set(repo.paths.library.rglob('*'))
    with pytest.raises(ApiError) as error:
        repo._import(Oversize(), '.pdf', 'Synthetic modeled oversized PDF', None,
            own_text_rights(), ContextScope(kind=Scope.LIBRARY), None, None, False, False)
    assert error.value.code == 'document_limit'
    assert intents(repo) == [] and set(repo.paths.library.rglob('*')) == before


def test_original_io_bound_matches_existing_product_and_reader(repository):
    from renulus.knowledge.original_io import MAX_ORIGINAL_BYTES, CHUNK_BYTES
    from renulus.knowledge.reader import MAX_ORIGINAL_BYTES as reader_limit
    from renulus.knowledge.repository import ORIGINAL_NATIVE_MAX_BYTES
    assert MAX_ORIGINAL_BYTES == MAX_BYTES == reader_limit == ORIGINAL_NATIVE_MAX_BYTES == 64 * 1024**2
    assert 0 < CHUNK_BYTES <= 1024**2
    status = repository.maintenance_status()
    assert status['original_publication_max_bytes'] == MAX_BYTES
    assert status['original_publication_chunk_bytes'] == CHUNK_BYTES
    assert status['original_publication_limit'] == 64


def test_exact_64m_algorithm_boundary_with_explicit_no_disk_model(tmp_path):
    # Algorithm control only, NOT retained Windows enforcement proof. The real
    # 33 MiB cases separately prove native large-file publication and recovery.
    from types import SimpleNamespace
    from renulus.knowledge.original_io import RetainedOriginalIO, CHUNK_BYTES
    io = RetainedOriginalIO.__new__(RetainedOriginalIO)
    io.fs = fs
    io.resource = fs.CreatedFile(1, SimpleNamespace(identity='modeled-no-handle'))
    length, reads, writes = [0], [], []
    def checkpoint(*, expected_bytes=None):
        assert expected_bytes is None or expected_bytes == length[0]
    def write(data):
        writes.append(len(data))
        length[0] += len(data)
        return len(data)
    io.checkpoint = checkpoint
    io._seek = lambda operation: None
    io._write = write
    io._truncate = lambda: None
    io._flush = lambda: None
    io._read = lambda size: reads.append(size) or b'X' * size
    data = b'X' * MAX_BYTES
    io.publish(data)
    assert io.sha256(expected_bytes=MAX_BYTES) == hashlib.sha256(data).hexdigest()
    assert len(writes) == len(reads) == 64 and set(writes) == set(reads) == {CHUNK_BYTES}
    with pytest.raises(fs.FilesystemError):
        io.publish(data)  # A claim cannot retry/republish, even in the model.


def test_actual_truncated_original_recovery_preserves_expectations_without_repair(tmp_path, monkeypatch):
    repo = native_repo(tmp_path)
    transaction = repo.db.transaction
    @contextmanager
    def fail():
        with transaction() as conn:
            yield conn
            if conn.execute('SELECT 1 FROM knowledge_revisions').fetchone():
                raise OSError('Synthetic rollback before truncation control')
    monkeypatch.setattr(repo.db, 'transaction', fail)
    try:
        with pytest.raises(OSError):
            repo.import_text(BODY.decode(), process=False)
        before = intents(repo)[0]
        original = Path(before['original_path'])
        assert original.read_bytes() == BODY
        original.write_bytes(BODY[:5])  # Owned synthetic default stream only.
        repo.recover()
        after = intents(repo)[0]
        assert after['phase'] == 'held_changed'
        assert after['identities_json'] == before['identities_json']
        assert after['sha256'] == before['sha256'] and after['expected_bytes'] == len(BODY)
        assert original.read_bytes() == BODY[:5] and not repo.db.fetch_all('SELECT * FROM knowledge_revisions')
    finally:
        repo.close()


@pytest.mark.parametrize('fault', ['short-write','write-error','truncate-error','flush-error','short-read','identity','late-ads','late-link'])
def test_actual_chunk_fault_retains_known_intent_without_canonical_publication(tmp_path, monkeypatch, fault):
    from renulus.knowledge.original_io import RetainedOriginalIO
    repo = native_repo(tmp_path)
    original_write = RetainedOriginalIO._write
    original_read = RetainedOriginalIO._read
    calls = []
    def write(self, data):
        row = intents(repo)[0]
        assert json.loads(row['identities_json'])['file'] is not None
        assert repo.db._active_writers == 0
        calls.append(len(data))
        if fault == 'short-write':
            return original_write(self, data[:3])
        if fault == 'write-error':
            original_write(self, data[:3])
            raise OSError('Synthetic retained chunk write error')
        count = original_write(self, data)
        if fault == 'late-ads':
            Path(str(self.path) + ':unknown-synthetic').write_bytes(b'Synthetic unknown ADS')
        if fault == 'late-link':
            self.path.with_name('unknown-alias.txt').hardlink_to(self.path)
        if fault == 'identity':
            from dataclasses import replace
            self.resource.info = replace(self.resource.info, identity=fs.FileIdentity('synthetic', 'changed'))
        return count
    monkeypatch.setattr(RetainedOriginalIO, '_write', write)
    if fault == 'truncate-error':
        monkeypatch.setattr(RetainedOriginalIO, '_truncate', lambda self: (_ for _ in ()).throw(OSError('Synthetic truncate failure')))
    if fault == 'flush-error':
        monkeypatch.setattr(RetainedOriginalIO, '_flush', lambda self: (_ for _ in ()).throw(OSError('Synthetic flush failure')))
    if fault == 'short-read':
        monkeypatch.setattr(RetainedOriginalIO, '_read', lambda self, size: original_read(self, size)[:3])
    try:
        with pytest.raises((OSError, fs.FilesystemError)):
            repo.import_text(BODY.decode(), process=False)
        row = intents(repo)[0]
        known = json.loads(row['identities_json'])
        assert known['file'] and known['directories'] and row['expected_bytes'] == len(BODY)
        assert row['sha256'] == hashlib.sha256(BODY).hexdigest()
        assert not repo.db.fetch_all('SELECT * FROM knowledge_revisions')
        original = Path(row['original_path'])
        assert original.exists() and calls and max(calls) <= 1024**2
        assert original.read_bytes() == (BODY[:3] if fault in ('short-write','write-error') else BODY)
        repo.recover()
        assert intents(repo)[0]['identities_json'] == row['identities_json']
        assert repo.maintenance_status()['original_publication_pending'] == 1
        if fault == 'late-ads':
            assert Path(str(original) + ':unknown-synthetic').read_bytes() == b'Synthetic unknown ADS'
        if fault == 'late-link':
            assert original.with_name('unknown-alias.txt').read_bytes() == BODY
    finally:
        repo.close()


@pytest.mark.parametrize('denied', ['read','write','truncate','flush'])
def test_native_audit_precedes_exact_retained_handle_operations(tmp_path, monkeypatch, denied):
    from renulus.knowledge.original_io import RetainedOriginalIO
    repo = native_repo(tmp_path)
    audit = sys.audit
    events, low_calls, attempts = [], [], [0]
    def observed(event, *args):
        if event == 'renulus.storage.native':
            operation, path, identity, retained = args
            events.append((operation, path, identity, retained))
            if operation == denied:
                attempts[0] += 1
                # Let the seek audit pass; reject the data call's OWN audit.
                # This proves a seek event cannot mask an unaudited chunk.
                if attempts[0] == (2 if denied in ('read','write') else 1):
                    assert identity is not None and retained is True
                    assert fs.exact_path(path) == Path(intents(repo)[0]['original_path'])
                    raise PermissionError('Synthetic exact native grant refusal')
        return audit(event, *args)
    monkeypatch.setattr(sys, 'audit', observed)
    # Intercept at the kernel call, not the helper method that contains its audit.
    name = {'read':'ReadFile','write':'WriteFile','truncate':'SetEndOfFile','flush':'FlushFileBuffers'}[denied]
    original = getattr(fs.k, name)
    def low(*args):
        low_calls.append(name)
        return original(*args)
    monkeypatch.setattr(fs.k, name, low)
    try:
        with pytest.raises(PermissionError):
            repo.import_text(BODY.decode(), process=False)
        assert events and events[-1][0] == denied and low_calls == []
        assert intents(repo) and not repo.db.fetch_all('SELECT * FROM knowledge_revisions')
    finally:
        repo.close()


def test_actual_multi_chunk_counts_flush_hash_and_parent_pin(tmp_path, monkeypatch):
    from renulus.knowledge.original_io import RetainedOriginalIO, CHUNK_BYTES
    repo = native_repo(tmp_path)
    body = b'S' * (CHUNK_BYTES + 17)
    write, read, flush = RetainedOriginalIO._write, RetainedOriginalIO._read, RetainedOriginalIO._flush
    writes, reads, flushes = [], [], []
    def observed_write(self, data):
        writes.append(len(data))
        assert intents(repo)[0]['phase'] == 'created' and repo.db._active_writers == 0
        with pytest.raises(OSError):
            self.path.parent.rename(self.path.parent.with_name('should-not-move'))
        return write(self, data)
    def observed_read(self, size):
        reads.append(size)
        return read(self, size)
    def observed_flush(self):
        flushes.append(True)
        return flush(self)
    monkeypatch.setattr(RetainedOriginalIO, '_write', observed_write)
    monkeypatch.setattr(RetainedOriginalIO, '_read', observed_read)
    monkeypatch.setattr(RetainedOriginalIO, '_flush', observed_flush)
    try:
        item = repo.import_text(body.decode(), process=False)
        row = repo.db.fetch_one('SELECT * FROM knowledge_revisions WHERE id=?', (item['revision_id'],))
        assert writes == [CHUNK_BYTES,17] and reads == [CHUNK_BYTES,17] and flushes == [True]
        assert row['sha256'] == hashlib.sha256(body).hexdigest() and intents(repo) == []
    finally:
        repo.close()


def test_unknown_ads_before_first_write_is_held_without_modification(tmp_path, monkeypatch):
    from renulus.knowledge.original_io import RetainedOriginalIO
    repo = native_repo(tmp_path)
    create = fs.created_file
    paths = []
    @contextmanager
    def appeared(path, **kwargs):
        with create(path, **kwargs) as resource:
            ads = Path(str(path) + ':unknown-synthetic')
            ads.write_bytes(b'Synthetic pre-write unknown ADS')
            paths.append((Path(path), ads))
            yield resource
    monkeypatch.setattr(fs, 'created_file', appeared)
    try:
        with pytest.raises(fs.FilesystemError) as error:
            repo.import_text(BODY.decode(), process=False)
        assert error.value.code == 'named_stream_hold'
        assert paths[0][0].read_bytes() == b''
        assert paths[0][1].read_bytes() == b'Synthetic pre-write unknown ADS'
        assert intents(repo) and not repo.db.fetch_all('SELECT * FROM knowledge_revisions')
    finally:
        repo.close()
