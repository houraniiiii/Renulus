# SPDX-License-Identifier: MIT
"""Source fixture contracts; account, limits and inclusive counts are synthetic."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from renulus.contracts import ApiError


SOURCE = Path(__file__).resolve().parents[2]
ENTRY = SOURCE / 'tools/renulus-control/harness-learning-backend.py'
NODE = Path('C:/Renulus/scratch/ocf/tools/node-v26.4.0-win-x64/node.exe').resolve()
PROMPT = 'Explain this synthetic study note and cite its Library passage.'


def module():
    spec = importlib.util.spec_from_file_location('learning_backend_fixture', ENTRY)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def document(tmp_path, ordinal=1):
    directory = tmp_path / 's-1234abcd'
    output = directory / 'out'
    output.mkdir(parents=True, exist_ok=True)
    assets = tmp_path / 'assets'
    assets.mkdir(exist_ok=True)
    identity = 'synthetic-learning-s-1234abcd'
    data = {'version': 1, 'process': {'node_executable': str(NODE),
        'host_entry': str(SOURCE / 'packages/harness/src/main.mjs'),
        'profile_root': str(directory / 'p'), 'profile_id': identity,
        'store_id': identity + '-runtime', 'domain_store_id': identity + '-domain',
        'domain_path': 'state/renulus.sqlite3', 'max_inflight': 1, 'max_domain_inflight': 1,
        'max_frame_bytes': 65536, 'start_timeout': 45}, 'artifact_root': str(directory / 'a'),
        'candidate_root': str(directory / 'k'), 'attempt_timeout': 45, 'initialize_new': ordinal == 1}
    return directory / 'p', output / f'startup-{ordinal}.json', assets, data


def write_document(file, data):
    raw = json.dumps(data).encode()
    file.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def test_learning_launch_is_distinct_immutable_and_read_only(tmp_path):
    profile, file, assets, data = document(tmp_path)
    digest = write_document(file, data)
    options = module().load_fixture_launch(file, digest, profile=profile, helper_assets=assets)
    assert options.scope.root == profile
    assert options.scope.profile_id == 'synthetic-learning-s-1234abcd'
    assert options.config.host_entry == SOURCE / 'packages/harness/src/main.mjs'
    assert options.initialize_new is True and options.initial_spec is None
    assert not profile.exists()
    profile, file, assets, data = document(tmp_path, ordinal=2)
    options = module().load_fixture_launch(file, write_document(file, data),
        profile=profile, helper_assets=assets)
    assert options.initialize_new is False and not profile.exists()


@pytest.mark.parametrize('change', ['digest', 'settings-identity', 'initial-policy', 'host',
    'boolean-count', 'ordinal', 'extra', 'duplicate', 'oversized'])
def test_untrusted_launch_changes_deny_without_profile_writes(tmp_path, change):
    profile, file, assets, data = document(tmp_path)
    if change == 'settings-identity':
        data['process']['profile_id'] = 'synthetic-settings-s-1234abcd'
    elif change == 'initial-policy':
        data['initial_spec'] = {}
    elif change == 'host':
        data['process']['host_entry'] = str(tmp_path / 'arbitrary.mjs')
    elif change == 'boolean-count':
        data['process']['max_inflight'] = True
    elif change == 'ordinal':
        data['initialize_new'] = False
    elif change == 'extra':
        data['fixture_script'] = 'caller supplied inference'
    digest = write_document(file, data)
    if change == 'digest':
        digest = '0' * 64
    elif change == 'duplicate':
        file.write_text(file.read_text().replace('"version": 1', '"version": 1, "version": 1'))
        digest = hashlib.sha256(file.read_bytes()).hexdigest()
    elif change == 'oversized':
        file.write_bytes(b' ' * 262145)
        digest = hashlib.sha256(file.read_bytes()).hexdigest()
    with pytest.raises(ApiError) as failure:
        module().load_fixture_launch(file, digest, profile=profile, helper_assets=assets)
    assert failure.value.code == 'harness_learning_fixture_invalid'
    assert not profile.exists()


def test_managed_fixture_real_library_roundtrip_two_requests_and_shutdown(tmp_path, record_property):
    profile, file, _, data = document(tmp_path)
    digest = write_document(file, data)
    assets = Path('C:/Renulus/dev/helper-assets').resolve()
    assert (assets / 'manifest.json').is_file()
    environment = {key: os.environ[key] for key in ('SYSTEMROOT', 'SystemRoot', 'WINDIR') if key in os.environ}
    environment['PYTHONPATH'] = os.pathsep.join((str(SOURCE / 'runtime'), str(SOURCE / 'upstream/hermes')))
    environment['TEMP'] = environment['TMP'] = str(tmp_path)
    completed = subprocess.run([sys.executable, str(Path(__file__)), '--fixture-child',
        str(file), digest, str(profile), str(assets)], env=environment,
        capture_output=True, text=True, timeout=180)
    assert completed.returncode == 0, completed.stderr
    receipt = json.loads(next(line.removeprefix('LEARNING_RECEIPT ')
        for line in completed.stdout.splitlines() if line.startswith('LEARNING_RECEIPT ')))
    assert receipt['admission_open'] is True
    assert receipt['provider_is_original'] is True
    assert receipt['roles_enabled'] == ['explain']
    assert receipt['spent_dispatches'] == 2 and receipt['run_state'] == 'settled'
    assert receipt['citation_opened'] is True and receipt['automatic_jobs'] == 0
    assert receipt['m5_eligible'] is True
    assert receipt['extra_dispatch_denied'] is True
    assert receipt['shutdown'] == receipt['native_settlement'] == 'settled'
    observations = receipt['observations']
    assert observations['fixture'] == 'learning-v1'
    assert observations['http_requests'] == observations['completed_http_requests'] == 2
    assert observations['counter_calls'] == observations['finalized_transports'] == 2
    assert observations['authenticated_requests'] == 2
    assert observations['handlers'] == observations['errors'] == 0
    assert observations['listener_closed'] is True
    assert len(observations['body_sha256']) == 2
    assert observations['query_sha256'] == hashlib.sha256(PROMPT.encode()).hexdigest()
    record_property('source_fixture_receipt', json.dumps(receipt, sort_keys=True))
    # Only this first dedicated Python process owns initialization. A separate
    # issuer must prove the predecessor and reopen the same paired generation.
    _, reopened_file, _, reopened_data = document(tmp_path, ordinal=2)
    reopened_digest = write_document(reopened_file, reopened_data)
    reopened = subprocess.run([sys.executable, str(Path(__file__)), '--reopen-child',
        str(reopened_file), reopened_digest, str(profile), str(assets)], env=environment,
        capture_output=True, text=True, timeout=90)
    assert reopened.returncode == 0, reopened.stderr
    observed = json.loads(next(line.removeprefix('LEARNING_RECEIPT ')
        for line in reopened.stdout.splitlines() if line.startswith('LEARNING_RECEIPT ')))
    assert observed['effective_version'] == observed['requested_version'] == receipt['effective_version']
    assert observed['launch_hash'] == receipt['launch_hash']
    assert observed['predecessor_generation'] == receipt['issuer_generation']
    assert observed['shutdown'] == observed['native_settlement'] == 'settled'
    assert observed['observations']['http_requests'] == observed['observations']['counter_calls'] == 0
    assert observed['observations']['listener_closed'] is True
    record_property('reopen_fixture_receipt', json.dumps(observed, sort_keys=True))


def test_expired_inspection_release_cannot_publish_initial_policy(tmp_path):
    profile, file, _, data = document(tmp_path)
    assets = Path('C:/Renulus/dev/helper-assets').resolve()
    environment = {key: os.environ[key] for key in ('SYSTEMROOT', 'SystemRoot', 'WINDIR') if key in os.environ}
    environment['PYTHONPATH'] = os.pathsep.join((str(SOURCE / 'runtime'), str(SOURCE / 'upstream/hermes')))
    environment['TEMP'] = environment['TMP'] = str(tmp_path)
    completed = subprocess.run([sys.executable, str(Path(__file__)), '--deadline-child',
        str(file), write_document(file, data), str(profile), str(assets)], env=environment,
        capture_output=True, text=True, timeout=90)
    assert completed.returncode == 0, completed.stderr
    assert 'INSPECTION_DENIED' in completed.stdout


def test_expired_inspection_cleanup_cannot_publish_initial_policy(tmp_path):
    profile, file, _, data = document(tmp_path)
    assets = Path('C:/Renulus/dev/helper-assets').resolve()
    environment = {key: os.environ[key] for key in ('SYSTEMROOT', 'SystemRoot', 'WINDIR') if key in os.environ}
    environment['PYTHONPATH'] = os.pathsep.join((str(SOURCE / 'runtime'), str(SOURCE / 'upstream/hermes')))
    environment['TEMP'] = environment['TMP'] = str(tmp_path)
    completed = subprocess.run([sys.executable, str(Path(__file__)), '--cleanup-deadline-child',
        str(file), write_document(file, data), str(profile), str(assets)], env=environment,
        capture_output=True, text=True, timeout=90)
    assert completed.returncode == 0, completed.stderr
    assert 'CLEANUP_DEADLINE_DENIED' in completed.stdout


def test_missing_session_token_denies_before_owned_profile_creation(tmp_path):
    profile, file, assets, data = document(tmp_path)
    environment = {key: os.environ[key] for key in ('SYSTEMROOT', 'SystemRoot', 'WINDIR') if key in os.environ}
    environment['PYTHONPATH'] = os.pathsep.join((str(SOURCE / 'runtime'), str(SOURCE / 'upstream/hermes')))
    completed = subprocess.run([sys.executable, str(Path(__file__)), '--token-child',
        str(file), write_document(file, data), str(profile), str(assets)], env=environment,
        capture_output=True, text=True, timeout=20)
    assert completed.returncode == 0, completed.stderr
    assert not profile.exists()


def test_owned_fixture_constructor_preserves_home_and_uses_explicit_state(tmp_path):
    profile, file, assets, data = document(tmp_path)
    environment = {key: os.environ[key] for key in ('SYSTEMROOT', 'SystemRoot', 'WINDIR') if key in os.environ}
    environment['PYTHONPATH'] = os.pathsep.join((str(SOURCE / 'runtime'), str(SOURCE / 'upstream/hermes')))
    environment['TEMP'] = environment['TMP'] = str(tmp_path)
    completed = subprocess.run([sys.executable, str(Path(__file__)), '--explicit-state-child',
        str(file), write_document(file, data), str(profile), str(assets)], env=environment,
        capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stderr
    assert 'EXPLICIT_STATE_WITHOUT_HOME' in completed.stdout


async def child_explicit_state(file, digest, profile, assets):
    import httpx
    homes = {name: os.environ.get(name) for name in ('USERPROFILE', 'HOME', 'CODEX_HOME')}

    def unavailable_home():
        raise AssertionError('Owned fixture construction must not resolve a system home')

    with pytest.MonkeyPatch.context() as guard:
        guard.setattr(Path, 'home', staticmethod(unavailable_home))
        app = module().create_fixture_app(file, digest, profile=profile, helper_assets=assets,
            token='synthetic-only-session')
    services = app.state.services
    try:
        assert {name: os.environ.get(name) for name in homes} == homes
        assert services.paths.root == profile
        assert services.get('provider').paths == services.paths
        assert services.get('helpers').paths == services.paths
        assert services.get('knowledge_catalogue').root == profile / 'library/collection'
        helpers = services.get('helpers')
        helpers.startup.configure()
        for name in ('HF_HOME', 'HF_HUB_CACHE', 'TRANSFORMERS_CACHE',
                'HF_MODULES_CACHE', 'TORCH_HOME', 'FASTEMBED_CACHE_PATH', 'TEMP', 'TMP'):
            assert Path(os.environ[name]).is_relative_to(services.paths.cache)
        manifest = profile / 'library/collection/metadata/acquisition-2026-10-04/acquisition-manifest.jsonl'
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({'source_id': 'R01',
            'title': 'Synthetic owned learning fixture catalogue',
            'local_path': 'raw/R01/synthetic-note.txt', 'sha256': 'a' * 64, 'bytes': 9}) + '\n',
            encoding='utf-8')
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                base_url='http://127.0.0.1:18777',
                headers={'x-renulus-token': 'synthetic-only-session'}) as client:
            response = await client.get('/api/v1/library/collection/preview', params={'source_id': 'R01'})
            assert response.status_code == 200
            observed = response.json()
            assert observed['total'] == 1 and observed['indexed'] is False and observed['errors'] == []
            assert observed['entries'][0]['title'] == 'Synthetic owned learning fixture catalogue'
            assert observed['entries'][0]['collection_path'] == 'raw/R01/synthetic-note.txt'
        assert app.state.learning_fixture.observations()['http_requests'] == 0
    finally:
        await app.state.harness_bootstrap.close()
        await services.finish_shutdown()
    assert {name: os.environ.get(name) for name in homes} == homes
    assert services.shutdown_status()['state'] == 'settled'
    print('EXPLICIT_STATE_WITHOUT_HOME', flush=True)


async def child_expired_inspection(file, digest, profile, assets):
    import asyncio
    from renulus.runtime import harness_process
    loop = asyncio.get_running_loop()
    clock, elapsed = loop.time, 0
    loop.time = lambda: clock() + elapsed
    actual = harness_process.ManagedHarnessProcess

    class ExpiredRelease(actual):
        async def release_observation(self, request_id):
            nonlocal elapsed
            released = await super().release_observation(request_id)
            assert released is True
            elapsed = 46
            return released

    # Observe real IPC/OS ownership; only the public elapsed clock is advanced.
    harness_process.ManagedHarnessProcess = ExpiredRelease
    app = module().create_fixture_app(file, digest, profile=profile, helper_assets=assets,
        token='synthetic-only-session')
    with pytest.raises(ApiError) as failed:
        async with app.router.lifespan_context(app):
            raise AssertionError('Expired inspection admitted startup')
    assert failed.value.code == 'harness_learning_fixture_invalid'
    status = app.state.harness_configuration_authority.activation_snapshot()
    assert status['effective'] is status['requested'] is status['activating'] is None
    assert status['admission_open'] is False
    assert app.state.services.shutdown_status()['state'] == 'settled'
    assert app.state.learning_fixture.observations()['http_requests'] == 0
    print('INSPECTION_DENIED', flush=True)


async def child_expired_cleanup(file, digest, profile, assets):
    import asyncio
    from renulus.runtime import harness_process
    loop = asyncio.get_running_loop()
    clock, elapsed = loop.time, 0
    loop.time = lambda: clock() + elapsed
    cleanup_entered, cleanup_allowed = asyncio.Event(), asyncio.Event()
    actual_settled = False
    actual = harness_process.ManagedHarnessProcess

    class ExpiredCleanup(actual):
        async def close(self, timeout):
            if not cleanup_entered.is_set():
                cleanup_entered.set()
                await cleanup_allowed.wait()
            return await super().close(timeout)

        async def settlement(self, timeout):
            nonlocal elapsed, actual_settled
            observed = await super().settlement(timeout)
            if observed['state'] == 'settled':
                actual_settled = True
                elapsed = 46
            return observed

    harness_process.ManagedHarnessProcess = ExpiredCleanup
    app = module().create_fixture_app(file, digest, profile=profile, helper_assets=assets,
        token='synthetic-only-session')

    async def startup():
        async with app.router.lifespan_context(app):
            raise AssertionError('Expired actual cleanup admitted startup')

    owned = asyncio.create_task(startup())
    await asyncio.wait_for(cleanup_entered.wait(), 60)
    assert not owned.done() and actual_settled is False
    status = app.state.harness_configuration_authority.activation_snapshot()
    assert status['effective'] is status['requested'] is status['activating'] is None
    assert status['admission_open'] is False
    cleanup_allowed.set()
    with pytest.raises(ApiError) as failed:
        await owned
    assert failed.value.code == 'harness_learning_fixture_invalid'
    assert actual_settled is True
    status = app.state.harness_configuration_authority.activation_snapshot()
    assert status['effective'] is status['requested'] is status['activating'] is None
    assert status['admission_open'] is False
    assert app.state.services.shutdown_status()['state'] == 'settled'
    assert app.state.learning_fixture.observations()['http_requests'] == 0
    print('CLEANUP_DEADLINE_DENIED', flush=True)


async def child_roundtrip(file, digest, profile, assets, *, reopen=False):
    fixture = module()
    app = fixture.create_fixture_app(file, digest, profile=profile, helper_assets=assets,
        token='synthetic-only-session')
    services = app.state.services
    provider = services.get('provider')
    authority = app.state.harness_configuration_authority
    text = ('Original synthetic study exercise, not clinical guidance; renal-study-delta-47.\n\n'
        'CKD assessment compares albuminuria and filtration as complementary concepts.\n\n'
        'Dialysis adequacy, transplant rejection and glomerular disease need distinct evidence.')
    async with app.router.lifespan_context(app):
        owner = services.get('harness_learning')
        registry = owner.model_registry
        assert registry.manager is provider and registry.authority is authority
        snapshot = authority.activation_snapshot()
        assert snapshot['admission_open'] is True and snapshot['activating'] is None
        spec = authority.configuration(snapshot['effective'])
        assert spec.attempts.foreground_dispatches == 2 and spec.attempts.retries == 0
        assert spec.attempts.standalone_dispatches == spec.attempts.title_dispatches == 0
        assert spec.children.max_depth == spec.children.concurrency == 0
        issuer = app.state.harness_bootstrap.profile_owner
        boot = {'effective_version': snapshot['effective'], 'requested_version': snapshot['requested'],
            'launch_hash': next(item.sha256 for item in spec.inputs if item.name == 'launch'),
            'issuer_generation': issuer.generation,
            'predecessor_generation': issuer.predecessor.previous_generation}
        if reopen:
            result = boot
        else:
            result = await saved_answer(app, owner, services, provider, authority, spec, snapshot, text)
            result.update(boot)
    result.update(shutdown=services.shutdown_status()['state'],
        native_settlement=(await owner.process.settlement(0))['state'],
        observations=app.state.learning_fixture.observations())
    return result


async def saved_answer(app, owner, services, provider, authority, spec, snapshot, text):
    import asyncio
    import httpx
    from renulus.contracts import ContextScope, Scope
    from renulus.learn.conversation_models import NewConversation, Send
    from test_harness_learning_models import collect_events
    registry = owner.model_registry
    library = services.get('knowledge')
    source = await asyncio.to_thread(library.import_text, text, title='Synthetic CKD fixture',
        scope=ContextScope(kind=Scope.LIBRARY), idempotency_key='learning-control-library')
    assert source['status'] == 'ready', source
    conversations = services.get('conversations')
    chat = conversations.create(NewConversation())
    entry, receipt = conversations.streaming.begin('learning', chat['identity']['id'],
        Send(expected_revision=chat['revision'], text=PROMPT,
            request_id='learning-control-roundtrip'))
    events = await collect_events(conversations, entry, receipt)
    assert events[-1]['type'] == 'completed', [event['type'] for event in events]
    reference = events[-1]['payload']['answer_reference']
    assert len(reference['citations']) == 1
    citation = reference['citations'][0]
    assert citation['document_id'] == source['document_id']
    assert citation['revision_id'] == source['revision_id']
    opened = library.citation(source['revision_id'], passage_id=citation['passage_id'])
    assert opened['locators'] == citation['locators']
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
            base_url='http://127.0.0.1:18777', headers={'x-renulus-token': 'synthetic-only-session'}) as client:
        original = await client.get(opened['original_url'])
        assert original.status_code == 200 and original.text == text
        visible = await client.get('/api/v1/connections')
        assert visible.status_code == 200 and visible.json()['selected_provider'] == 'opencode-go'
    resolved = await owner.resolve_completed_answer(reference)
    assert 'renal-study-delta-47' in resolved['text']
    assert resolved['digest'] == hashlib.sha256(resolved['text'].encode()).hexdigest()
    saved = owner.bridge.completed(entry['run'].id)
    assert saved['publication_digest'] == resolved['publication_digest']
    memory = services.get('memory')
    with services.db.transaction() as conn:
        eligible = memory.eligible_answer_references_in(conn, (reference,))
    assert len(eligible) == 1 and eligible[0].kind == 'committed_evidence'
    assert eligible[0].dependency.expected_revision == saved['publication_digest']
    run = authority.run(entry['run'].id)
    assert registry.status().owned == 0 and registry.status().runs == 0
    next_chat = conversations.create(NewConversation())
    next_entry, next_receipt = conversations.streaming.begin('learning', next_chat['identity']['id'],
        Send(expected_revision=next_chat['revision'], text='Try another synthetic CKD answer.',
            request_id='learning-control-third-send-denied'))
    rejected = await collect_events(conversations, next_entry, next_receipt)
    assert rejected[-1]['type'] == 'error', [event['type'] for event in rejected]
    assert authority.run(next_entry['run'].id)['spent_dispatches'] == 0
    assert registry.status().owned == registry.status().runs == 0
    return {'admission_open': snapshot['admission_open'], 'provider_is_original':
        services.get('provider') is provider, 'roles_enabled': sorted(role.purpose for role in spec.roles
            if role.enabled), 'spent_dispatches': run['spent_dispatches'], 'run_state': run['state'],
        'citation_opened': True, 'm5_eligible': True, 'extra_dispatch_denied': True,
        'automatic_jobs': len(memory.repository.jobs())}


if __name__ == '__main__':
    import asyncio
    if sys.argv[1] == '--token-child':
        with pytest.raises(ApiError) as failed:
            module().create_fixture_app(Path(sys.argv[2]), sys.argv[3], profile=Path(sys.argv[4]),
                helper_assets=Path(sys.argv[5]), token=None)
        assert failed.value.code == 'harness_learning_fixture_invalid'
    elif sys.argv[1] == '--deadline-child':
        asyncio.run(child_expired_inspection(Path(sys.argv[2]), sys.argv[3],
            Path(sys.argv[4]), Path(sys.argv[5])))
    elif sys.argv[1] == '--cleanup-deadline-child':
        asyncio.run(child_expired_cleanup(Path(sys.argv[2]), sys.argv[3],
            Path(sys.argv[4]), Path(sys.argv[5])))
    elif sys.argv[1] == '--explicit-state-child':
        asyncio.run(child_explicit_state(Path(sys.argv[2]), sys.argv[3],
            Path(sys.argv[4]), Path(sys.argv[5])))
    else:
        assert sys.argv[1] in ('--fixture-child', '--reopen-child')
        print('LEARNING_RECEIPT ' + json.dumps(asyncio.run(child_roundtrip(
            Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4]), Path(sys.argv[5]),
            reopen=sys.argv[1] == '--reopen-child'))), flush=True)
