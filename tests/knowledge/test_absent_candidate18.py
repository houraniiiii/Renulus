"""Resource-free rebuild retirement versus unresolved native owners; tiny fixtures.

Windows controls use real ownership/original handles in isolated subprocesses.
SDK/extraction/capacity remain explicit doubles. No disposition is authorized.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from renulus.contracts import ApiError
from renulus.knowledge.engines import LanceIndex
from renulus.storage import filesystem as native
from test_index_maintenance import repository as baseline_repository


@pytest.fixture(autouse=True)
def no_dispositions(monkeypatch):
    calls = []
    def forbidden(*args, **kwargs):
        calls.append(repr(args))
        raise AssertionError('Library18 disposition intercepted; bytes must stay preserved')
    for name in ('unlink', 'remove', 'rmdir', 'rename', 'replace'):
        monkeypatch.setattr(os, name, forbidden)
    monkeypatch.setattr('shutil.rmtree', forbidden)
    monkeypatch.setattr(native.k, 'SetFileInformationByHandle', forbidden)
    yield calls
    assert calls == []


@pytest.fixture
def repository(tmp_path):
    fixture = baseline_repository.__wrapped__(tmp_path)
    repo = next(fixture)
    try:
        yield repo
    finally:
        # Only the explicitly injected portable owner model: pending cases assert
        # graceful-close refusal before modeling process end. Never native release.
        repo._owner.fs.held.clear()
        repo._closed = True
        with pytest.raises(StopIteration):
            next(fixture)


def capture_candidates(monkeypatch, repo):
    candidates = []
    def construct(path, dimensions):
        candidate = LanceIndex(path, dimensions)
        candidates.append(candidate)
        return candidate
    monkeypatch.setattr('renulus.knowledge.repository.LanceIndex', construct)
    return candidates


def fail_embedding(texts):
    raise OSError('Synthetic embedding failure before candidate native admission')


def ready_snapshot(repo, item):
    return (repo.db.fetch_all('SELECT * FROM knowledge_passages ORDER BY id'),
            repo.db.fetch_all('SELECT * FROM knowledge_revisions ORDER BY id'),
            repo.db.fetch_all('SELECT * FROM preferences WHERE key=\'knowledge.index_generation\''),
            repo.get_job(item['job']['id']))


@pytest.mark.parametrize('parent_exists', [False, True])
@pytest.mark.parametrize('boundary', ['cleanup', 'close'])
def test_before_native_rebuild_failures_settle_and_close_without_allocating(repository, monkeypatch, parent_exists, boundary):
    repo = repository
    item = repo.import_text('Tiny synthetic ready nephrology study text')
    if parent_exists:
        (repo.paths.indexes / 'k').mkdir()
    selected, before = repo.index, ready_snapshot(repo, item)
    candidates = capture_candidates(monkeypatch, repo)
    monkeypatch.setattr(repo.embedder, 'embed', fail_embedding)
    for _ in range(2):
        with pytest.raises(OSError, match='before candidate native admission'):
            repo.rebuild_index()
        assert repo.index is selected and ready_snapshot(repo, item) == before
        if boundary == 'cleanup':
            assert repo.cleanup() == [], 'Never-opened absence is not native retirement debt'
    if boundary == 'close':
        repo.close()  # Must also settle without a separate cleanup call.
    assert not repo._retired_indexes and not repo._retirement_owners
    assert repo.maintenance_status()['retirement_pending'] == 0
    for candidate in candidates:
        assert not candidate.path.exists()
        assert candidate.path.parent.exists() == parent_exists
        assert not candidate.path.with_name(candidate.path.name + '.native-owner').exists()
        assert candidate._ownership is None and candidate._connection is None
        assert candidate._table is None and candidate._rejected_table is None
        with pytest.raises(ApiError) as reopened:
            candidate._open()
        assert reopened.value.code == 'index_close_pending'
    repo.close()
    repo.close()
    assert repo._closed and selected.closed
    assert repo.original(item['revision_id'])[0].read_text() == 'Tiny synthetic ready nephrology study text'


def test_absence_access_failure_retains_candidate_until_verified_cleanup_retry(repository, monkeypatch):
    repo = repository
    item = repo.import_text('Tiny synthetic retry source')
    selected, before = repo.index, ready_snapshot(repo, item)
    candidates = capture_candidates(monkeypatch, repo)
    exists = repo._owner.fs.path_exists
    denied = [True]
    def uncertain(path):
        if candidates and Path(path) == candidates[0].path.parent and denied[0]:
            raise PermissionError('Synthetic absent-parent uncertainty')
        return exists(path)
    monkeypatch.setattr(repo._owner.fs, 'path_exists', uncertain)
    monkeypatch.setattr(repo.embedder, 'embed', fail_embedding)
    with pytest.raises(OSError):
        repo.rebuild_index()
    candidate = candidates[0]
    assert repo.cleanup() and repo._retired_indexes[repo._index_token(candidate)] is candidate
    with pytest.raises(ApiError) as close:
        repo.close()
    assert close.value.code == 'index_cleanup_pending' and not repo._closed
    repo._owner.require()
    denied[0] = False
    repo.close()  # Sealed profile still owns cleanup retry; never re-admit work.
    assert repo._closed and not repo._retired_indexes
    assert repo.index is selected and ready_snapshot(repo, item) == before
    assert not candidate.path.parent.exists()


@pytest.mark.parametrize('resource', ['ownership', 'table', 'rejected_table', 'connection', 'failed_close', 'retiring', 'token', 'retirement_owner'])
def test_absent_path_with_unresolved_resource_never_settles(repository, monkeypatch, resource):
    repo = repository
    item = repo.import_text('Tiny synthetic unresolved native control')
    selected, before = repo.index, ready_snapshot(repo, item)
    candidates = capture_candidates(monkeypatch, repo)
    closed = []
    marker = SimpleNamespace(close=lambda: closed.append('unknown-owner'),
        _table=SimpleNamespace(close=lambda: closed.append('unknown-table')),
        _conn=SimpleNamespace(close=lambda: closed.append('unknown-connection')),
        require=lambda: None, fs=repo._owner.fs, _path_pin=object())
    def fail(texts):
        candidate = candidates[0]
        if resource in ('table', 'rejected_table', 'connection', 'ownership'):
            setattr(candidate, '_' + resource, marker)
        elif resource == 'failed_close':
            candidate._closing = True  # Outstanding failed close, no resource proof.
        elif resource == 'retiring':
            candidate._retiring = True
        elif resource == 'token':
            candidate.path.parent.mkdir()
            candidate.path.with_name(candidate.path.name + '.native-owner').write_bytes(b'unknown synthetic token')
        else:
            repo._retirement_owners[repo._index_token(candidate)] = marker
        raise OSError('Synthetic before-open fault with unresolved neighbor')
    monkeypatch.setattr(repo.embedder, 'embed', fail)
    with pytest.raises(OSError):
        repo.rebuild_index()
    candidate = candidates[0]
    # A retained generation owner + missing path is a modeled contradiction:
    # do not turn path absence into release authority even if its close succeeds.
    assert repo.cleanup(), 'Unresolved resources cannot use resource-free absence acknowledgement'
    assert repo._retired_indexes.get(repo._index_token(candidate)) is candidate
    assert not candidate.path.exists()
    with pytest.raises(ApiError) as close:
        repo.close()
    assert close.value.code == 'index_cleanup_pending' and not repo._closed
    repo._owner.require()
    assert repo.index is selected and ready_snapshot(repo, item) == before
    assert 'unknown-owner' not in closed
    if resource in ('table', 'rejected_table', 'connection'):
        assert getattr(candidate, '_' + resource) is marker
        assert closed == []


def test_failed_native_admission_without_current_handles_is_not_never_opened(repository, monkeypatch):
    repo = repository
    repo.import_text('Tiny synthetic attempted native admission')
    candidates = capture_candidates(monkeypatch, repo)
    def failed_factory(token):
        raise OSError('Synthetic uncertain ownership factory failure')
    def fail(texts):
        candidate = candidates[0]
        candidate._ownership_factory = failed_factory
        with pytest.raises(OSError):
            candidate._open()
        assert candidate._ownership is None and candidate._connection is None
        assert not candidate.path.exists()
        raise OSError('Synthetic rebuild fault after attempted native admission')
    monkeypatch.setattr(repo.embedder, 'embed', fail)
    with pytest.raises(OSError):
        repo.rebuild_index()
    assert repo.cleanup() and len(repo._retired_indexes) == 1
    with pytest.raises(ApiError):
        repo.close()
    repo._owner.require()


def test_appearing_missing_ancestor_is_uncertainty_not_absence(repository, monkeypatch):
    repo = repository
    repo.import_text('Tiny synthetic ancestor checkpoint')
    candidates = capture_candidates(monkeypatch, repo)
    guard = repo._owner.fs.guarded_roots
    appeared = [False]
    @contextmanager
    def racing(paths):
        with guard(paths):
            if candidates and Path(paths[0]) == repo.paths.indexes and not appeared[0]:
                # Portable race: an absent parent appears after ancestor selection.
                # It represents a foreign/reparse namespace, never adopted.
                candidates[0].path.parent.mkdir()
                appeared[0] = True
            yield
    monkeypatch.setattr(repo._owner.fs, 'guarded_roots', racing)
    monkeypatch.setattr(repo.embedder, 'embed', fail_embedding)
    with pytest.raises(OSError):
        repo.rebuild_index()
    assert repo.maintenance_status()['retirement_pending'] == 1
    candidate = candidates[0]
    assert repo._retired_indexes[repo._index_token(candidate)] is candidate
    # A new verification can now pin the newly existing ordinary parent, not the
    # earlier uncertainty. There are still no token/table/connection resources.
    assert repo.cleanup() == []
    repo.close()


@pytest.mark.parametrize('refusal', ['reparse', 'alias'])
def test_foreign_ancestor_refusal_is_preserved_without_native_admission(repository, monkeypatch, refusal):
    repo = repository
    repo.import_text('Tiny synthetic foreign ancestor')
    candidates = capture_candidates(monkeypatch, repo)
    guard = repo._owner.fs.guarded_roots
    @contextmanager
    def refused(paths):
        if candidates and Path(paths[0]).is_relative_to(repo.paths.indexes):
            raise OSError('Synthetic no-follow ' + refusal + ' refusal')
        with guard(paths):
            yield
    monkeypatch.setattr(repo._owner.fs, 'guarded_roots', refused)
    monkeypatch.setattr(repo.embedder, 'embed', fail_embedding)
    with pytest.raises(OSError):
        repo.rebuild_index()
    assert repo.cleanup() and len(repo._retired_indexes) == 1
    candidate = candidates[0]
    assert candidate._ownership is None and not candidate.path.parent.exists()
    with pytest.raises(ApiError):
        repo.close()
    repo._owner.require()


NATIVE_CODE = r'''
import json, os, sys
from pathlib import Path
from types import SimpleNamespace
sys.path[:0] = [sys.argv[1] + '/runtime', sys.argv[1] + '/tests/knowledge']
from renulus.contracts import ApiError
from renulus.knowledge.engines import LanceIndex
from renulus.knowledge.ownership import NativeOwnership
import renulus.knowledge.repository as module
from renulus.storage import filesystem as fs
from test_original_io17 import native_repo

attempts = []
def audit(event, args):
    if event in ('os.remove', 'os.rmdir', 'os.rename', 'shutil.rmtree'):
        attempts.append(event)
        raise AssertionError('Native18 disposition intercepted')
sys.addaudithook(audit)
def deny(*args):
    attempts.append('SetFileInformationByHandle')
    raise AssertionError('Native18 whole-object disposition intercepted')
fs.k.SetFileInformationByHandle = deny
root, mode = Path(sys.argv[2]), sys.argv[3]
repo = native_repo(root)
item = repo.import_text('Actual tiny Windows owner, synthetic ready Library text')
selected = repo.index
before = repo.db.fetch_all('SELECT * FROM knowledge_passages ORDER BY id')
candidates = []
def construct(path, dimensions):
    index = LanceIndex(path, dimensions)
    candidates.append(index)
    return index
module.LanceIndex = construct
closed = []
def fail(texts):
    index = candidates[0]
    if mode == 'pending-native':
        def close_table():
            closed.append('table')
            raise OSError('Synthetic native table close fault')
        index._table = SimpleNamespace(_table=SimpleNamespace(close=close_table))
        # Actual Windows generation/token pins; the SDK handle is a double.
        index._open()
        index._connection = SimpleNamespace(_conn=SimpleNamespace(close=lambda: closed.append('connection')))
        (index.path / 'unknown.txt').write_bytes(b'preserved unknown synthetic bytes')
        Path(str(index.path / 'unknown.txt') + ':late-synthetic').write_bytes(b'preserved synthetic ADS')
    raise OSError('Synthetic before native embedding failure')
repo.embedder.embed = fail
try:
    repo.rebuild_index()
except OSError:
    pass
else:
    raise AssertionError('Expected embedding failure')
index = candidates[0]
pending = repo.cleanup()
try:
    repo.close()
except ApiError as error:
    close_code = error.code
else:
    close_code = None
try:
    contender = NativeOwnership(repo._owner.path).acquire()
except ApiError as error:
    contender_code = error.code
else:
    contender_code = None
    contender.close()
observed = {'mode': mode, 'pending': pending, 'close_code': close_code,
    'contender_code': contender_code, 'repository_closed': repo._closed,
    'ready_preserved': repo.index is selected and repo.get_job(item['job']['id'])['state'] == 'ready'
        and repo.db.fetch_all('SELECT * FROM knowledge_passages ORDER BY id') == before
        and repo.db.fetch_one("SELECT value FROM preferences WHERE key='knowledge.index_generation'") is None,
    'candidate_path_absent': not index.path.exists(), 'candidate_parent_absent': not index.path.parent.exists(),
    'retirement_count': repo.maintenance_status()['retirement_pending'],
    'retained_candidate': repo._retired_indexes.get(repo._index_token(index)) is index,
    'disposition_attempts': attempts, 'native_close_calls': closed}
if mode == 'pending-native':
    observed['pins_retained'] = index._ownership._path_pin is not None and index._connection is not None and index._table is not None
    observed['unknown_preserved'] = (index.path / 'unknown.txt').read_bytes() == b'preserved unknown synthetic bytes'
    observed['ads_preserved'] = Path(str(index.path / 'unknown.txt') + ':late-synthetic').read_bytes() == b'preserved synthetic ADS'
    try:
        NativeOwnership(index._ownership.path).acquire_for_path(index.path)
    except ApiError as error:
        observed['generation_contender_code'] = error.code
    else:
        raise AssertionError('Native generation owner was released')
else:
    observed['no_native_resources'] = all(value is None for value in (index._ownership, index._table, index._rejected_table, index._connection))
    if repo._closed:
        repo.close()  # Public idempotence, not an out-of-band resource release.
print(json.dumps(observed))
# Pending mode deliberately ends its process with live pins. OS process-end
# release is not product retirement acknowledgement; every fixture stays intact.
'''


@pytest.mark.parametrize('mode', ['absent', 'pending-native'])
def test_actual_windows_profile_owner_and_contender(tmp_path, mode):
    completed = subprocess.run([sys.executable, '-I', '-B', '-c', NATIVE_CODE,
        str(Path(__file__).parents[2]), str(tmp_path), mode],
        capture_output=True, text=True, timeout=20)
    assert completed.returncode == 0, completed.stderr
    observed = json.loads(completed.stdout)
    (tmp_path / 'native-observation.json').write_text(json.dumps(observed, indent=2))
    assert observed['ready_preserved'] and observed['disposition_attempts'] == []
    if mode == 'absent':
        assert observed['candidate_path_absent'] and observed['candidate_parent_absent']
        assert observed['no_native_resources']
        assert observed['pending'] == [], 'Actual never-opened candidate must not retain the Windows profile owner'
        assert observed['close_code'] is None and observed['contender_code'] is None
        assert observed['repository_closed'] and observed['retirement_count'] == 0
        assert not observed['retained_candidate']
    else:
        assert observed['pending'] and observed['close_code'] == 'index_cleanup_pending'
        assert observed['contender_code'] == observed['generation_contender_code'] == 'index_owner_busy'
        assert not observed['repository_closed'] and observed['retained_candidate']
        assert observed['pins_retained'] and observed['unknown_preserved'] and observed['ads_preserved']
        assert 'connection' not in observed['native_close_calls']
