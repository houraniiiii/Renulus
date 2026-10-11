"""Explicit managed-startup configuration, before profile provisioning."""
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading

import pytest
import httpx

from renulus.contracts import ApiError


def startup_document(tmp_path):
    return {
        'version': 1,
        'process': {
            'node_executable': str(tmp_path / 'node.exe'),
            'host_entry': str(tmp_path / 'main.mjs'),
            'profile_root': str(tmp_path / 'profile'),
            'profile_id': 'synthetic-startup-profile',
            'store_id': 'synthetic-startup-runtime',
            'domain_store_id': 'synthetic-startup-domain',
            'domain_path': 'state/renulus.sqlite3',
        },
        'artifact_root': str(tmp_path / 'artifacts'),
        'candidate_root': str(tmp_path / 'candidates'),
        'attempt_timeout': 15,
        'initialize_new': True,
    }


def test_explicit_startup_document_cannot_select_a_different_profile(tmp_path):
    from renulus.runtime.harness_startup import load_startup_options
    requested = tmp_path / 'requested-profile'
    file = tmp_path / 'startup.json'
    file.write_text(json.dumps(startup_document(tmp_path)), encoding='utf-8')
    with pytest.raises(ApiError) as rejected:
        load_startup_options(file, profile=requested)
    assert rejected.value.code == 'harness_startup_invalid'
    assert rejected.value.status == 409
    assert not requested.exists()
    assert not (tmp_path / 'profile').exists()


def test_valid_startup_uses_explicit_identities_and_existing_transport_defaults(tmp_path):
    from renulus.runtime.harness_startup import load_startup_options
    document = startup_document(tmp_path)
    document['process']['max_inflight'] = 1
    document['process']['max_domain_inflight'] = 1
    file = tmp_path / 'startup.json'
    file.write_text(json.dumps(document), encoding='utf-8')
    options = load_startup_options(file, profile=tmp_path / 'profile')
    assert options.scope.root == tmp_path / 'profile'
    assert options.scope.profile_id == 'synthetic-startup-profile'
    assert options.scope.domain_store_id == 'synthetic-startup-domain'
    assert options.scope.runtime_store_id == 'synthetic-startup-runtime'
    assert options.config.max_inflight == options.config.max_domain_inflight == 1
    assert options.config.max_frame_bytes == 1048576
    assert options.config.boot_settings == {}
    assert options.initial_spec is None
    assert not options.scope.root.exists()


@pytest.mark.parametrize('change', ['extra', 'version-bool', 'relative-node',
    'domain-path', 'ambient-boot', 'frame-bool', 'timeout-nan', 'initialize-int',
    'candidate-nested', 'artifact-nested', 'unknown-spec', 'unknown-process'])
def test_invalid_startup_metadata_denies_before_profile_mutation(tmp_path, change):
    from renulus.runtime.harness_startup import load_startup_options
    data = startup_document(tmp_path)
    if change == 'extra':
        data['credentials'] = 'synthetic-canary'
    elif change == 'version-bool':
        data['version'] = True
    elif change == 'relative-node':
        data['process']['node_executable'] = 'node.exe'
    elif change == 'domain-path':
        data['process']['domain_path'] = 'state/other.sqlite3'
    elif change == 'ambient-boot':
        data['process']['boot_settings'] = {'config': {'instructions': ['synthetic-canary']}}
    elif change == 'frame-bool':
        data['process']['max_frame_bytes'] = True
    elif change == 'timeout-nan':
        data['attempt_timeout'] = float('nan')
    elif change == 'initialize-int':
        data['initialize_new'] = 1
    elif change == 'candidate-nested':
        data['candidate_root'] = str(tmp_path / 'profile' / 'candidates')
    elif change == 'artifact-nested':
        data['artifact_root'] = str(tmp_path / 'candidates' / 'artifacts')
    elif change == 'unknown-spec':
        data['initial_spec'] = {'authority': 'synthetic-canary'}
    else:
        data['process']['credential'] = 'synthetic-canary'
    file = tmp_path / 'startup.json'
    file.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ApiError) as denied:
        load_startup_options(file, profile=tmp_path / 'profile')
    assert denied.value.code == 'harness_startup_invalid'
    assert 'synthetic-canary' not in denied.value.message
    assert not (tmp_path / 'profile').exists()


@pytest.mark.parametrize('content', ['{"version":1,"version":1}', '{',
    'null', '[' + '0,' * 140000 + '0]'],
    ids=['duplicate-fields', 'invalid-json', 'null-document', 'oversized'])
def test_malformed_or_ambiguous_startup_file_denies_before_profile_mutation(tmp_path, content):
    from renulus.runtime.harness_startup import load_startup_options
    file = tmp_path / 'startup.json'
    file.write_text(content, encoding='utf-8')
    with pytest.raises(ApiError) as denied:
        load_startup_options(file, profile=tmp_path / 'profile')
    assert denied.value.code == 'harness_startup_invalid'
    assert not (tmp_path / 'profile').exists()


async def test_initial_account_preparation_and_connection_api_share_one_provider(tmp_path):
    from renulus.server import create_app
    observed = []

    def catalogue(request):
        assert request.method == 'GET' and request.url.path.endswith('/models')
        observed.append(request.url.path)
        return httpx.Response(200, json={'data': [{'id': 'mimo-v2.6-pro'}]})

    app = create_app(tmp_path / 'account-profile',
        provider_http_transport=httpx.MockTransport(catalogue))
    services = app.state.services
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                base_url='http://testserver') as client:
            connected = await client.post('/api/v1/connections/opencode-go',
                json={'api_key': 'synthetic-startup-never-networked', 'select': True})
            assert connected.status_code == 200, connected.text
            assert services.get('provider').configuration_connection().provider == 'opencode-go'
            visible = await client.get('/api/v1/connections')
            assert visible.status_code == 200, visible.text
            assert visible.json()['selected_provider'] == 'opencode-go'
            assert len(observed) == 1
    finally:
        assert (await services.shutdown(timeout=5))['state'] == 'settled'


@pytest.mark.skipif(os.name != 'nt', reason='Actual Windows profile issuer')
@pytest.mark.parametrize('cancel_close', [False, True], ids=['normal-close', 'cancelled-close'])
def test_managed_lifespan_joins_coordinator_before_services_dependencies(tmp_path, cancel_close):
    from test_harness_profile_owner import ObservedChild

    repo = Path(__file__).resolve().parents[2]
    child = subprocess.Popen([sys.executable, '-B', '-u', str(Path(__file__).resolve()),
        '--observe-managed-close', str(tmp_path), str(int(cancel_close))], stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, close_fds=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
        env={**os.environ, 'PYTHONPATH': str(repo / 'runtime'),
             'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1'})
    messages = queue.Queue()

    def read():
        for line in child.stdout:
            messages.put(line)
        messages.put(None)

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    actual = None
    try:
        first = messages.get(timeout=15)
        assert first, child.stderr.read()
        actual = ObservedChild(json.loads(first)['actual_pid'])
        line = messages.get(timeout=30)
        assert line, child.stderr.read()
        result = json.loads(line)
        assert actual.wait(10000) == 0
        child.wait(timeout=10)
        assert child.returncode == 0, result
        assert result == {'startup_code': 'configuration_not_active',
            'events': ['coordinator-joined', 'dependency-closed'],
            'repeated_start_code': 'runtime_stopping', 'services_state': 'settled',
            'close_observer_pending': True, 'early_dependency_close': False}
    finally:
        if actual:
            if actual.wait(0) == 258:
                actual.terminate()  # Only this retained synthetic child.
                assert actual.wait(5000) == 0
            actual.close()
        elif child.poll() is None:
            child.terminate()  # Only our launcher before child identification.
        child.wait(timeout=10)
        reader.join(timeout=2)
        child.stdout.close()
        child.stderr.close()


async def observe_managed_close(root, *, cancel_close=False):
    import asyncio
    from renulus.runtime.harness_launch import LaunchArtifactStore
    from renulus.runtime.harness_startup import create_managed_app, load_startup_options

    repo = Path(__file__).resolve().parents[2]
    document = startup_document(root)
    document['process']['node_executable'] = 'C:/Renulus/scratch/ocf/tools/node-v26.4.0-win-x64/node.exe'
    document['process']['host_entry'] = str(repo / 'packages/harness/src/main.mjs')
    path = root / 'managed-startup.json'
    path.write_text(json.dumps(document), encoding='utf-8')
    app = create_managed_app(load_startup_options(path, profile=root / 'profile'), source_root=repo)
    bootstrap, services = app.state.harness_bootstrap, app.state.services
    events = []
    original_close = getattr(bootstrap, 'close', None)
    closing, release_close = asyncio.Event(), asyncio.Event()
    if not cancel_close:
        release_close.set()

    async def observed_close():
        closing.set()
        await release_close.wait()
        if original_close is not None:
            await original_close()
        events.append('coordinator-joined')

    # Observe the public close edge without substituting its behavior. The
    # pre-repair coordinator lacks it, so the lifespan never calls this wrapper.
    bootstrap.close = observed_close
    services.on_shutdown_dependencies.append(lambda: events.append('dependency-closed'))
    async def serve():
        try:
            async with app.router.lifespan_context(app):
                raise AssertionError('No-account assembly must not serve')
        except ApiError as error:
            return error.code
        except asyncio.CancelledError:
            return 'cancelled'

    serving = asyncio.create_task(serve())
    close_observer_pending, early_dependency_close = True, False
    if cancel_close:
        await closing.wait()
        for _ in range(2):
            serving.cancel()
            await asyncio.sleep(0)
        close_observer_pending = not serving.done()
        early_dependency_close = 'dependency-closed' in events
        release_close.set()
    startup_code = await serving
    repeated_start_code = None
    try:
        await bootstrap.start(authority=app.state.harness_configuration_authority,
            provider=services.get('provider'),
            launch_store=LaunchArtifactStore(root / 'artifacts', live_root=root / 'profile',
                candidate_root=root / 'candidates'),
            assemble_runtime=lambda *args: (_ for _ in ()).throw(AssertionError('No runtime')))
    except ApiError as error:
        repeated_start_code = error.code
    return {'startup_code': startup_code, 'events': events,
        'repeated_start_code': repeated_start_code, 'services_state': services.shutdown_status()['state'],
        'close_observer_pending': close_observer_pending, 'early_dependency_close': early_dependency_close}


if __name__ == '__main__' and sys.argv[1] == '--observe-managed-close':
    import asyncio
    print(json.dumps({'actual_pid': os.getpid()}), flush=True)
    try:
        print(json.dumps(asyncio.run(observe_managed_close(Path(sys.argv[2]),
            cancel_close=sys.argv[3] == '1'))), flush=True)
    except BaseException as error:
        print(json.dumps({'failure': type(error).__name__, 'message': str(error)}), flush=True)
        raise
