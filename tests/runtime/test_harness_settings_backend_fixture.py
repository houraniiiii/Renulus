"""Fixed fixture contracts; synthetic helper bytes, no native/app/model startup."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
from renulus.contracts import ApiError

SOURCE = Path(__file__).resolve().parents[2]
ENTRY = SOURCE / 'tools/renulus-control/harness-settings-backend.py'
NODE = Path('C:/Renulus/scratch/ocf/tools/node-v26.4.0-win-x64/node.exe').resolve()


def module():
    spec = importlib.util.spec_from_file_location('settings_backend_fixture', ENTRY)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def document(tmp_path):
    directory = tmp_path / 's-1234abcd'
    output = directory / 'out'
    output.mkdir(parents=True)
    assets = tmp_path / 'assets'
    assets.mkdir()
    identity = 'synthetic-settings-s-1234abcd'
    data = {'version': 1, 'process': {'node_executable': str(NODE),
        'host_entry': str(SOURCE / 'packages/harness/src/main.mjs'),
        'profile_root': str(directory / 'p'), 'profile_id': identity,
        'store_id': identity + '-runtime', 'domain_store_id': identity + '-domain',
        'domain_path': 'state/renulus.sqlite3', 'max_inflight': 1, 'max_domain_inflight': 1,
        'max_frame_bytes': 65536, 'start_timeout': 45}, 'artifact_root': str(directory / 'a'),
        'candidate_root': str(directory / 'k'), 'attempt_timeout': 45, 'initialize_new': True}
    return directory / 'p', output / 'startup-1.json', assets, data


def write_document(file, data):
    raw = json.dumps(data).encode()
    file.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def test_fixed_launch_document_is_read_only_and_has_no_initial_authority(tmp_path):
    profile, file, assets, data = document(tmp_path)
    digest = write_document(file, data)
    options = module().load_fixture_launch(file, digest, profile=profile, helper_assets=assets)
    assert options.scope.root == profile
    assert options.initial_spec is None
    assert options.config.host_entry == SOURCE / 'packages/harness/src/main.mjs'
    assert not profile.exists()


@pytest.mark.parametrize('change', ['digest', 'initial-policy', 'host-entry', 'boolean-count', 'extra', 'oversized', 'duplicate'])
def test_altered_startup_document_denies_before_profile_acquisition(tmp_path, change):
    profile, file, assets, data = document(tmp_path)
    if change == 'initial-policy':
        data['initial_spec'] = {}
    elif change == 'host-entry':
        data['process']['host_entry'] = str(tmp_path / 'arbitrary.mjs')
    elif change == 'boolean-count':
        data['process']['max_inflight'] = True
    elif change == 'extra':
        data['provider_endpoint'] = 'https://example.invalid'
    digest = write_document(file, data)
    if change == 'digest':
        digest = '0' * 64
    elif change in ('oversized', 'duplicate'):
        raw = b' ' * 262145 if change == 'oversized' else b'{"version":1,"version":1}'
        file.write_bytes(raw)
        digest = hashlib.sha256(raw).hexdigest()
    with pytest.raises(ApiError) as denied:
        module().load_fixture_launch(file, digest, profile=profile, helper_assets=assets)
    assert denied.value.code == 'harness_settings_fixture_invalid'
    assert not profile.exists()


def test_helper_provisioning_refuses_an_unbound_issuer_before_writes(tmp_path):
    with pytest.raises(ApiError) as denied:
        module().provision_helpers(object(), tmp_path / 'assets', source_root=tmp_path / 'source')
    assert denied.value.code == 'harness_settings_fixture_invalid'
    assert list(tmp_path.iterdir()) == []


def helper_bundle(tmp_path):
    assets, source = tmp_path / 'assets', tmp_path / 'source'
    assets.mkdir()
    (source / 'packaging/runtime').mkdir(parents=True)
    groups = {}
    for name in ('embedding', 'docling', 'ocr'):
        raw = ('synthetic-' + name).encode()
        (assets / (name + '.bin')).write_bytes(raw)
        groups[name] = {'revision': 'synthetic-reviewed', 'source_url': 'https://example.invalid/' + name,
            'files': [{'path': name + '.bin', 'size': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}]}
    raw = json.dumps({'version': 1, 'groups': groups})
    (assets / 'manifest.json').write_text(raw)
    (source / 'packaging/runtime/helper-assets.json').write_text(raw)
    return assets, source


def provision_in_owned_process(tmp_path, assets, source):
    import renulus
    code = '''
import importlib.util, json, sys
from pathlib import Path
from renulus.runtime.harness_profile_owner import ProfileOwnerScope, acquire_profile_owner
spec = importlib.util.spec_from_file_location('fixed_settings_fixture', sys.argv[1])
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
root = Path(sys.argv[2])
assert not root.exists()
lease = acquire_profile_owner(ProfileOwnerScope(root, 'synthetic-helper-profile',
    'synthetic-helper-domain', 'synthetic-helper-runtime'), initialize_new=True)
result = fixture.provision_helpers(lease, Path(sys.argv[3]), source_root=Path(sys.argv[4]))
print(json.dumps({'result': result, 'issuer': lease.predecessor.kind}))
'''
    environment = {key: os.environ[key] for key in ('SYSTEMROOT', 'SystemRoot', 'WINDIR') if key in os.environ}
    environment['PYTHONPATH'] = os.pathsep.join((str(Path(renulus.__file__).parents[1]), str(SOURCE / 'upstream/hermes')))
    return subprocess.run([sys.executable, '-c', code, str(ENTRY), str(tmp_path / 'profile'),
        str(assets), str(source)], env=environment, capture_output=True, text=True, timeout=15)


def test_declared_synthetic_helpers_copy_after_real_subprocess_issuer(tmp_path):
    assets, source = helper_bundle(tmp_path)
    completed = provision_in_owned_process(tmp_path, assets, source)
    assert completed.returncode == 0, completed.stderr
    observed = json.loads(completed.stdout)
    assert observed['issuer'] == 'new_profile'
    assert observed['result']['status'] == 'copied-and-verified'
    assert set(observed['result']['groups']) == {'docling', 'embedding', 'ocr'}
    assert (tmp_path / 'profile/helpers/manifest.json').read_bytes()
    assert (tmp_path / 'profile/helpers/embedding.bin').read_bytes() == b'synthetic-embedding'


def test_corrupt_helper_source_denies_before_any_helper_manifest_publication(tmp_path):
    assets, source = helper_bundle(tmp_path)
    (assets / 'ocr.bin').write_bytes(b'synthetic-corruption')
    completed = provision_in_owned_process(tmp_path, assets, source)
    assert completed.returncode != 0
    assert 'The fixed Settings fixture inputs are invalid' in completed.stderr
    assert not (tmp_path / 'profile/helpers/manifest.json').exists()
    assert not (tmp_path / 'profile/helpers/embedding.bin').exists()


def test_fixed_app_and_connection_routes_share_the_original_synthetic_provider(tmp_path):
    import renulus
    profile, file, assets, data = document(tmp_path)
    digest = write_document(file, data)
    code = '''
import asyncio, importlib.util, json, sys
from pathlib import Path
import httpx
spec = importlib.util.spec_from_file_location('fixed_settings_fixture', sys.argv[1])
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
try:
    app = fixture.create_fixture_app(Path(sys.argv[2]), sys.argv[3], profile=Path(sys.argv[4]),
        helper_assets=Path(sys.argv[5]), token='synthetic-only-session')
except Exception as error:
    import traceback
    traceback.print_exception(error.__context__)
    raise
async def run():
    services = app.state.services
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://127.0.0.1:18777',
                headers={'x-renulus-token': 'synthetic-only-session'}) as client:
            connected = await client.post('/api/v1/connections/opencode-go',
                json={'api_key': 'synthetic-only-never-networked', 'select': True})
            assert connected.status_code == 200, connected.text
            visible = await client.get('/api/v1/connections')
            assert visible.status_code == 200, visible.text
            assert visible.json()['selected_provider'] == 'opencode-go'
            assert services.get('provider').configuration_connection().provider == 'opencode-go'
            print(json.dumps({'route': 'opencode-go', 'native_started': False}))
    finally:
        assert (await services.shutdown(timeout=5))['state'] == 'settled'
asyncio.run(run())
'''
    environment = {key: os.environ[key] for key in ('SYSTEMROOT', 'SystemRoot', 'WINDIR') if key in os.environ}
    environment['PYTHONPATH'] = os.pathsep.join((str(Path(renulus.__file__).parents[1]), str(SOURCE / 'upstream/hermes')))
    completed = subprocess.run([sys.executable, '-c', code, str(ENTRY), str(file), digest,
        str(profile), str(assets)], env=environment, capture_output=True, text=True, timeout=20)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)['route'] == 'opencode-go'


def test_missing_helpers_stop_managed_lifespan_before_policy_or_native_admission(tmp_path):
    import renulus
    profile, file, assets, data = document(tmp_path)
    digest = write_document(file, data)
    code = '''
import asyncio, importlib.util, json, sys
from pathlib import Path
from renulus.contracts import ApiError
spec = importlib.util.spec_from_file_location('fixed_settings_fixture', sys.argv[1])
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
app = fixture.create_fixture_app(Path(sys.argv[2]), sys.argv[3], profile=Path(sys.argv[4]),
    helper_assets=Path(sys.argv[5]), token='synthetic-only-session')
async def run():
    try:
        async with app.router.lifespan_context(app):
            raise AssertionError('Missing helpers admitted startup')
    except ApiError as error:
        assert error.code == 'harness_settings_fixture_invalid', error.code
    authority = app.state.harness_configuration_authority
    assert authority.status()['effective'] is None
    assert authority.status()['requested'] is None
    assert not authority.status()['admission_open']
    print(json.dumps({'denied': True}))
asyncio.run(run())
'''
    environment = {key: os.environ[key] for key in ('SYSTEMROOT', 'SystemRoot', 'WINDIR') if key in os.environ}
    environment['PYTHONPATH'] = os.pathsep.join((str(Path(renulus.__file__).parents[1]), str(SOURCE / 'upstream/hermes')))
    completed = subprocess.run([sys.executable, '-c', code, str(ENTRY), str(file), digest,
        str(profile), str(assets)], env=environment, capture_output=True, text=True, timeout=20)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)['denied']


@pytest.mark.parametrize('phase', ['held-release', 'return-expiry'])
def test_committed_inspection_deadline_enters_real_drain_with_release_publisher_retained(tmp_path, phase):
    """Actual native inspect/issuer; synthetic helpers and elapsed clock, held OS drain."""
    import renulus
    assets, fixture_source = helper_bundle(tmp_path)
    native = fixture_source / 'packages/harness'
    published_native = Path(renulus.__file__).parents[2] / 'packages/harness'
    shutil.copytree(published_native / 'src', native / 'src')
    shutil.copyfile(published_native / 'package.json', native / 'package.json')
    for link, dependency in ((native / 'node_modules', SOURCE / 'packages/harness/node_modules'),
                             (fixture_source / 'upstream/hermes', SOURCE / 'upstream/hermes')):
        link.parent.mkdir(parents=True, exist_ok=True)
        dependency_path = str(dependency.resolve()).replace("'", "''")
        link_path = str(link).replace("'", "''")
        linked = subprocess.run(['C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe',
            '-NoProfile', '-NonInteractive', '-Command',
            f"New-Item -ItemType Junction -Path '{link_path}' -Target '{dependency_path}' | Out-Null"],
            capture_output=True, text=True, timeout=10)
        assert linked.returncode == 0, linked.stderr
    entry = fixture_source / 'tools/renulus-control/harness-settings-backend.py'
    entry.parent.mkdir(parents=True)
    shutil.copyfile(ENTRY, entry)
    profile, file, _, data = document(tmp_path / 'launch')
    data['process']['host_entry'] = str(native / 'src/main.mjs')
    digest = write_document(file, data)
    code = '''
import asyncio, importlib.util, json, sys
from pathlib import Path
from renulus.contracts import ApiError
from renulus.runtime import harness_process
from renulus.runtime.harness_launch import LaunchArtifactStore
spec = importlib.util.spec_from_file_location('fixed_settings_fixture', sys.argv[1])
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)

async def run():
    phase = sys.argv[6]
    loop = asyncio.get_running_loop()
    clock, elapsed = loop.time, 0
    # The immutable production document still requests 45s. Advancing only the
    # public clock makes the remaining-budget test deterministic and fast.
    loop.time = lambda: clock() + elapsed
    publisher_entered, release_gate, close_entered = (asyncio.Event() for _ in range(3))
    observer_cancelled, publisher_completed = asyncio.Event(), asyncio.Event()
    publisher_cancelled = False
    held_writer, process, inspection = None, None, None
    original_write, original_drain = asyncio.StreamWriter.write, asyncio.StreamWriter.drain

    def write(writer, data):
        nonlocal held_writer
        if json.loads(data)['kind'] == 'observation_release':
            held_writer = writer
        return original_write(writer, data)

    async def drain(writer):
        nonlocal elapsed, publisher_cancelled
        if phase == 'held-release' and writer is held_writer and not release_gate.is_set():
            elapsed = 46
            publisher_entered.set()
            try:
                await release_gate.wait()
            except asyncio.CancelledError:
                publisher_cancelled = True
                raise
            await original_drain(writer)
            publisher_completed.set()
            return
        await original_drain(writer)

    class ObservedProcess(harness_process.ManagedHarnessProcess):
        async def request(self, command, *args, **kwargs):
            nonlocal elapsed, process, inspection
            result = await super().request(command, *args, **kwargs)
            if command == 'host.inspect':
                assert result['outcome'] == 'committed_reference', result
                assert {row['name'] for row in result['result']['registry']} == {
                    'renulus_library_retrieve', 'renulus_library_citation'}
                assert self.native_identity().pid > 0
                process, inspection = self, result
                elapsed = 40
            return result

        async def release_observation(self, request_id):
            nonlocal elapsed
            try:
                result = await super().release_observation(request_id)
                if phase == 'return-expiry':
                    assert result is True
                    elapsed = 46
                    publisher_completed.set()
                    publisher_entered.set()
                return result
            except asyncio.CancelledError:
                observer_cancelled.set()
                raise

        async def close(self, timeout):
            close_entered.set()
            return await super().close(timeout)

    # Public process observers delegate all behavior. Only the OS drain is held.
    harness_process.ManagedHarnessProcess = ObservedProcess
    asyncio.StreamWriter.write, asyncio.StreamWriter.drain = write, drain
    def refuse_expired_publication(self, frozen):
        raise AssertionError('Expired inspection reached launch artifact publication')
    LaunchArtifactStore.save = refuse_expired_publication
    app = fixture.create_fixture_app(Path(sys.argv[2]), sys.argv[3], profile=Path(sys.argv[4]),
        helper_assets=Path(sys.argv[5]), token='synthetic-only-session')
    async def start():
        async with app.router.lifespan_context(app):
            raise AssertionError('Expired inspection admitted startup')
    starting = asyncio.create_task(start())
    try:
        await asyncio.wait_for(publisher_entered.wait(), 60)
        await asyncio.wait_for(close_entered.wait(), .3)
        if phase == 'held-release':
            assert observer_cancelled.is_set()
            assert not publisher_cancelled and not publisher_completed.is_set()
            assert not starting.done()
            assert await process.query_result(inspection['request_id']) == inspection
            assert (await process.settlement(0))['state'] == 'pending'
        else:
            assert not observer_cancelled.is_set() and publisher_completed.is_set()
            assert await process.query_result(inspection['request_id']) is None
        release_gate.set()
        try:
            await asyncio.wait_for(starting, 15)
        except ApiError as error:
            assert error.code == 'harness_settings_fixture_invalid', error.code
        else:
            raise AssertionError('Expired inspection returned a registry hash')
        assert publisher_completed.is_set() and not publisher_cancelled
        assert (await process.settlement(0))['state'] == 'settled'
        assert process.domain_status()['active'] == 0
        assert await process.query_result(inspection['request_id']) is None
        status = app.state.harness_configuration_authority.status()
        assert status['requested'] is None and status['effective'] is None
        assert not status['admission_open']
        print(json.dumps({'committed_inspection': True, 'retained_publisher': phase == 'held-release', 'settled': True}))
    finally:
        release_gate.set()
        try:
            await asyncio.wait_for(starting, 15)
        except Exception as cleanup_error:
            print('cleanup outcome: ' + type(cleanup_error).__name__, file=sys.stderr)
        asyncio.StreamWriter.write, asyncio.StreamWriter.drain = original_write, original_drain
        loop.time = clock

asyncio.run(run())
'''
    environment = {key: os.environ[key] for key in ('SYSTEMROOT', 'SystemRoot', 'WINDIR') if key in os.environ}
    environment['PYTHONPATH'] = os.pathsep.join((str(Path(renulus.__file__).parents[1]), str(SOURCE / 'upstream/hermes')))
    completed = subprocess.run([sys.executable, '-c', code, str(entry), str(file), digest,
        str(profile), str(assets), phase], env=environment, capture_output=True, text=True, timeout=85)
    (tmp_path / 'observation.stdout.txt').write_text(completed.stdout, encoding='utf-8')
    (tmp_path / 'observation.stderr.txt').write_text(completed.stderr, encoding='utf-8')
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {'committed_inspection': True,
        'retained_publisher': phase == 'held-release', 'settled': True}


def test_fixed_lifespan_prepares_connection_and_readable_immutable_launch_artifact(tmp_path):
    """Actual issuer/native bootstrap; synthetic catalogue/helpers, stop before warmup."""
    import renulus
    assets, fixture_source = helper_bundle(tmp_path)
    native = fixture_source / 'packages/harness'
    published_native = Path(renulus.__file__).parents[2] / 'packages/harness'
    shutil.copytree(published_native / 'src', native / 'src')
    shutil.copyfile(published_native / 'package.json', native / 'package.json')
    for link, dependency in ((native / 'node_modules', SOURCE / 'packages/harness/node_modules'),
                             (fixture_source / 'upstream/hermes', SOURCE / 'upstream/hermes')):
        link.parent.mkdir(parents=True, exist_ok=True)
        dependency_path = str(dependency.resolve()).replace("'", "''")
        link_path = str(link).replace("'", "''")
        linked = subprocess.run(['C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe',
            '-NoProfile', '-NonInteractive', '-Command',
            f"New-Item -ItemType Junction -Path '{link_path}' -Target '{dependency_path}' | Out-Null"],
            capture_output=True, text=True, timeout=10)
        assert linked.returncode == 0, linked.stderr
    entry = fixture_source / 'tools/renulus-control/harness-settings-backend.py'
    entry.parent.mkdir(parents=True)
    shutil.copyfile(ENTRY, entry)
    profile, file, _, data = document(tmp_path / 'launch')
    data['process']['host_entry'] = str(native / 'src/main.mjs')
    digest = write_document(file, data)
    code = '''
import asyncio, importlib.util, json, sys
from pathlib import Path
from renulus.runtime.harness_configuration import ConfigurationSpec
from renulus.runtime.harness_launch import LaunchArtifactStore, finish_spec
spec = importlib.util.spec_from_file_location('fixed_settings_fixture', sys.argv[1])
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
profile = Path(sys.argv[4])
app = fixture.create_fixture_app(Path(sys.argv[2]), sys.argv[3], profile=profile,
    helper_assets=Path(sys.argv[5]), token='synthetic-only-session')

class PreparationObserved(Exception):
    pass

async def run():
    services = app.state.services
    authority = app.state.harness_configuration_authority
    observed = None

    def observe_prepared_configuration():
        nonlocal observed
        snapshot = authority.activation_snapshot()
        prepared = snapshot['configuration']
        assert type(prepared) is ConfigurationSpec
        assert snapshot['effective'] == snapshot['requested']
        assert snapshot['admission_open']
        assert prepared.connection.provider == 'opencode-go'
        assert prepared.connection.selected_model == 'mimo-v2.6-pro'
        assert prepared.connection == services.get('provider').configuration_connection()
        artifact, = (item for item in prepared.inputs if item.kind == 'artifact' and item.name == 'launch')
        store = LaunchArtifactStore(profile.parent / 'a', live_root=profile,
            candidate_root=profile.parent / 'k')
        frozen = store.load(artifact.sha256)
        assert frozen.launch_hash == artifact
        assert frozen.boot_settings == {}
        assert finish_spec(frozen, prepared.registry_hash) == prepared
        observed = {'connection': 'opencode-go', 'immutable_artifact_readable': True}
        raise PreparationObserved

    # Observe the actual bootstrap handoff before tiny synthetic helper bytes
    # could be mistaken for warmup or serving acceptance. No factory/inference.
    services.on_startup.insert(0, observe_prepared_configuration)
    try:
        async with app.router.lifespan_context(app):
            raise AssertionError('Bounded preparation unexpectedly entered serving')
    except PreparationObserved:
        pass
    assert observed is not None
    assert (await services.shutdown(timeout=0))['state'] == 'settled'
    assert services.stopping
    print(json.dumps({**observed, 'settled': True}))

asyncio.run(run())
'''
    environment = {key: os.environ[key] for key in ('SYSTEMROOT', 'SystemRoot', 'WINDIR') if key in os.environ}
    environment['PYTHONPATH'] = os.pathsep.join((str(Path(renulus.__file__).parents[1]), str(SOURCE / 'upstream/hermes')))
    completed = subprocess.run([sys.executable, '-c', code, str(entry), str(file), digest,
        str(profile), str(assets)], env=environment, capture_output=True, text=True, timeout=85)
    (tmp_path / 'preparation.stdout.txt').write_text(completed.stdout, encoding='utf-8')
    (tmp_path / 'preparation.stderr.txt').write_text(completed.stderr, encoding='utf-8')
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {'connection': 'opencode-go',
        'immutable_artifact_readable': True, 'settled': True}
