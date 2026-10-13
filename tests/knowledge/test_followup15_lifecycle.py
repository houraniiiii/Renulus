"""Narrow actual Windows lifetime checks; no SDK/provider/helper or dispositions."""
import asyncio
import json
from pathlib import Path
import subprocess
import sys
from threading import Event

import pytest

from renulus.contracts import ApiError
from renulus.knowledge.ownership import NativeOwnership, KnowledgeCapacity
from renulus.knowledge.repository import KnowledgeRepository
from renulus.services import Services
from renulus.storage import AppPaths, Database
from test_index_maintenance import MaintenanceIndex
from test_repository import SyntheticExtractor, SyntheticEmbedder
from test_storage_reliability import SyntheticFilesystem


def test_real_generation_pin_retained_until_process_end_not_retirement(tmp_path):
    path = tmp_path / 'generation'
    path.mkdir()
    marker = path / 'unknown-synthetic.txt'
    marker.write_bytes(b'unknown synthetic file')
    ads = Path(str(marker) + ':late-synthetic')
    runtime = Path(__file__).parents[2] / 'runtime'
    code = """
import json, sys
from pathlib import Path
from types import SimpleNamespace
sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1])
from renulus.contracts import ApiError
from renulus.knowledge.engines import LanceIndex
from renulus.knowledge.ownership import NativeOwnership
path = Path(sys.argv[2])
index = LanceIndex(path)
index._table = SimpleNamespace(_table=SimpleNamespace(close=lambda: None))
index._open()
index.prepare_retirement()
Path(str(path / 'unknown-synthetic.txt') + ':late-synthetic').write_bytes(b'late synthetic ADS')
index.close()
assert index._ownership._path_pin is not None
try:
    index.finish_retirement()
except ApiError as error:
    assert error.code == 'index_cleanup_pending'
else:
    raise AssertionError('Retirement incorrectly settled')
try:
    path.rename(path.with_name('substituted'))
except OSError:
    pass
else:
    raise AssertionError('Retained generation pin allowed replacement')
try:
    NativeOwnership(index._ownership.path).acquire_for_path(path)
except ApiError as error:
    assert error.code == 'index_owner_busy'
else:
    raise AssertionError('Pending retirement token released')
print(json.dumps({'native_close_settled': True, 'retirement_pending': True, 'pins_retained': True, 'rename_refused': True, 'contender_refused': True}))
# Deliberately exit with live retirement pins: OS process-end release, not product
# reclamation acknowledgement, no explicit tree/file disposition or release gap.
"""
    completed = subprocess.run([sys.executable, '-I', '-c', code, str(runtime), str(path)],
        capture_output=True, text=True, timeout=15)
    assert completed.returncode == 0, completed.stderr
    observed = json.loads(completed.stdout)
    assert all(observed.values())
    assert marker.read_bytes() == b'unknown synthetic file'
    assert ads.read_bytes() == b'late synthetic ADS'
    fresh = NativeOwnership(path.with_suffix('.native-owner')).acquire_for_path(path)
    fresh.close()  # Release this test reader only, never retire preserved bytes.


def test_real_profile_owner_outlives_close_thread_observers(tmp_path):
    paths = AppPaths.create(tmp_path / 'profile')
    db = Database(paths.database)
    module = Path(__file__).parents[2] / 'runtime/renulus/knowledge'
    db.apply_migration('knowledge-001', (module / 'schema.sql').read_text())
    for migration in sorted((module / 'migrations').glob('*.sql')):
        db.apply_migration('knowledge-' + migration.stem, migration.read_text())
    repo = KnowledgeRepository(Services(paths, db), extractor=SyntheticExtractor(), embedder=SyntheticEmbedder(),
        index=MaintenanceIndex(paths.indexes / 'knowledge'),
        owner=NativeOwnership(paths.state / 'knowledge-native-owner'),
        capacity=KnowledgeCapacity(filesystem=SyntheticFilesystem()))
    entered, release = Event(), Event()
    original = repo.index.close
    def held_close():
        entered.set()
        assert release.wait(3)
        original()
    repo.index.close = held_close
    async def scenario():
        try:
            with pytest.raises(ApiError) as error:
                await repo.services.shutdown(timeout=.02)
            assert error.value.code == 'runtime_shutdown_pending'
            assert entered.is_set() and not repo._closed
            with pytest.raises(ApiError) as contention:
                NativeOwnership(repo._owner.path).acquire()
            assert contention.value.code == 'index_owner_busy'
            observer = asyncio.create_task(repo.services.shutdown())
            await asyncio.sleep(0)
            observer.cancel()
            with pytest.raises(asyncio.CancelledError):
                await observer
            assert not repo.services._shutdown_task.done()
            with pytest.raises(ApiError):
                NativeOwnership(repo._owner.path).acquire()
        finally:
            release.set()
        assert (await repo.services.shutdown(timeout=1))['state'] == 'settled'
        assert repo._closed
        fresh = NativeOwnership(repo._owner.path).acquire()
        fresh.close()
    try:
        asyncio.run(scenario())
    finally:
        release.set()
        repo.close()


def test_shutdown_retry_never_replays_settled_producers_or_new_hooks():
    services = Services(None, None)
    calls, attempts = [], [0]
    services.on_stopping.append(lambda: calls.append('signal'))
    async def success():
        calls.append('success')
        await asyncio.sleep(0)
    async def flaky():
        attempts[0] += 1
        calls.append('flaky')
        await asyncio.sleep(0)
        if attempts[0] == 1:
            raise OSError('Synthetic producer failure')
    services.on_shutdown.extend([flaky, success])
    services.on_shutdown_dependencies.append(lambda: calls.append('dependency'))
    async def scenario():
        with pytest.raises(ApiError) as error:
            await services.shutdown(timeout=1)
        assert error.value.code == 'runtime_shutdown_failed'
        services.on_shutdown.append(lambda: calls.append('late-producer'))
        services.on_shutdown_dependencies.append(lambda: calls.append('late-dependency'))
        assert (await services.shutdown(timeout=1))['state'] == 'settled'
        assert (await services.shutdown(timeout=1))['state'] == 'settled'
    asyncio.run(scenario())
    assert calls == ['signal', 'success', 'flaky', 'flaky', 'dependency']
