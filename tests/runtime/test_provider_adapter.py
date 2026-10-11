"""Public subscription preparation; all credentials and transports are synthetic."""
import asyncio
import json
import time
from uuid import uuid4

import httpx
import pytest

from renulus.runtime.manager import ProviderManager
from renulus.contracts import ApiError, ContextScope, Scope
from renulus.runtime.protected import ConnectionStore
from renulus.runtime.protected import WindowsDPAPI
from renulus.runtime.harness_configuration import ConnectionReference


def legacy_selected_go_profile(app_paths):
    ConnectionStore(app_paths.root, app_paths.state).save({
        'version': 1, 'host_id': uuid4().urn, 'selected_provider': 'opencode-go',
        'selected_models': {'opencode-go': 'deepseek-v4.1-flash'},
        'connections': {'opencode-go': {'access_token': uuid4().hex}},
    })


def legacy_selected_codex_profile(app_paths, *, expires_at, refresh_token=None):
    ConnectionStore(app_paths.root, app_paths.state).save({
        'version': 1, 'host_id': uuid4().urn, 'selected_provider': 'codex',
        'selected_models': {'codex': 'gpt-6-astra'},
        'connections': {'codex': {'client_id': 'synthetic-registered-client',
            'access_token': uuid4().hex, 'expires_at': expires_at,
            'scopes': ['resource.invoke', 'chatgpt.tokens.use.direct'],
            **({'refresh_token': refresh_token} if refresh_token else {})}},
    })


def forbid_provider_usage(request):
    pytest.fail('Preparation unexpectedly called a provider', pytrace=False)


@pytest.mark.asyncio
async def test_configuration_connection_reconnect_and_auth_revocation_survive_reopen_without_port_io(app_paths):
    legacy_selected_go_profile(app_paths)
    calls = []

    def catalogue(request):
        calls.append(request.url.path)
        return httpx.Response(200, json={'data': [{'id': 'deepseek-v4.1-flash'}]})

    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(catalogue))
    try:
        await manager.prepare_harness_route()
        original = manager.configuration_connection()
        await manager.connect_go(uuid4().hex, select=True)
        current = manager.configuration_connection()
        assert current.credential_reference == original.credential_reference
        assert current.credential_revision > original.credential_revision
        assert calls == ['/zen/go/v1/models']
        with pytest.raises(ApiError) as stale:
            manager.require_configuration_connection(original)
        assert stale.value.code == 'connection_changed'
        assert manager.require_configuration_connection(current) is None
        route = await manager.prepare_harness_route()
        manager.observe_harness_result(route, code='authentication_required')
        protected_before = manager.store.path.read_bytes()
        with pytest.raises(ApiError) as invalid:
            manager.configuration_connection()
        assert invalid.value.code == 'authentication_required'
        with pytest.raises(ApiError) as stale:
            manager.require_configuration_connection(current)
        assert stale.value.code == 'connection_changed'
        assert calls == ['/zen/go/v1/models']
        assert manager.store.path.read_bytes() == protected_before
    finally:
        await manager.close()
    reopened = ProviderManager(app_paths, http_transport=httpx.MockTransport(forbid_provider_usage))
    try:
        with pytest.raises(ApiError) as invalid:
            reopened.configuration_connection()
        assert invalid.value.code == 'authentication_required'
        for old in [original, current]:
            with pytest.raises(ApiError) as stale:
                reopened.require_configuration_connection(old)
            assert stale.value.code == 'connection_changed'
        await reopened.disconnect('opencode-go')
        assert reopened.configuration_connection() is None
    finally:
        await reopened.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('selected,connections', [
    (None, {}),
    (None, {'opencode-go': {'access_token': 'synthetic-unselected'}}),
    ('codex', {'opencode-go': {'access_token': 'synthetic-other-provider'}}),
])
async def test_configuration_connection_none_means_no_actual_selected_connection(app_paths, selected, connections):
    store = ConnectionStore(app_paths.root, app_paths.state)
    store.save({'version': 1, 'host_id': uuid4().urn, 'selected_provider': selected, 'connections': connections})
    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(forbid_provider_usage))
    try:
        protected_before = store.path.read_bytes()
        assert manager.configuration_connection() is None
        guessed = ConnectionReference(provider='opencode-go', credential_reference=str(uuid4()),
            credential_revision=0, selected_model=None)
        with pytest.raises(ApiError) as stale:
            manager.require_configuration_connection(guessed)
        assert stale.value.code == 'connection_changed'
        assert store.path.read_bytes() == protected_before
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_configuration_connection_ports_do_not_read_or_write_protected_storage(app_paths):
    legacy_selected_go_profile(app_paths)

    class CountedProtection:
        def __init__(self):
            self.calls = []
            self.actual = WindowsDPAPI()

        def protect(self, data, entropy):
            self.calls.append('protect')
            return self.actual.protect(data, entropy)

        def unprotect(self, data, entropy):
            self.calls.append('unprotect')
            return self.actual.unprotect(data, entropy)

    protection = CountedProtection()
    manager = ProviderManager(app_paths, protector=protection,
        http_transport=httpx.MockTransport(forbid_provider_usage))
    try:
        await manager.prepare_harness_route()
        before = tuple(protection.calls)
        assert before == ('unprotect', 'protect')
        connection = manager.configuration_connection()
        assert manager.require_configuration_connection(connection) is None
        assert tuple(protection.calls) == before
    finally:
        await manager.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('stale_status', [401, 503])
async def test_stale_refresh_error_cannot_revoke_or_discard_newer_success(app_paths, stale_status):
    legacy_selected_go_profile(app_paths)
    entered, release = asyncio.Event(), asyncio.Event()
    calls = 0

    async def catalogue(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            entered.set()
            await release.wait()
            return httpx.Response(stale_status)
        return httpx.Response(200, json={'data': [{'id': 'deepseek-v4.1-flash'}]})

    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(catalogue))
    pending = None
    try:
        await manager.prepare_harness_route()
        pending = asyncio.create_task(manager.refresh('opencode-go'))
        await asyncio.wait_for(entered.wait(), 3)
        await manager.refresh('opencode-go')
        current = await manager.prepare_harness_route()
        before = manager.harness_capabilities(current)
        protected_before = manager.store.path.read_bytes()
        release.set()
        with pytest.raises(ApiError) as stale:
            await asyncio.wait_for(pending, 3)
        assert stale.value.code == 'connection_changed'
        assert manager.require_harness_route(current) is None
        assert manager.harness_capabilities(current) == before
        assert manager.store.path.read_bytes() == protected_before
    finally:
        release.set()
        if pending is not None:
            await asyncio.gather(pending, return_exceptions=True)
        await manager.close()


@pytest.mark.asyncio
async def test_configuration_connection_model_changes_preserve_exact_none_and_reopen_binding(app_paths):
    legacy_selected_go_profile(app_paths)
    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(forbid_provider_usage))
    try:
        await manager.prepare_harness_route()
        explicit = manager.configuration_connection()
        manager.select('opencode-go', None)
        automatic = manager.configuration_connection()
        assert automatic.selected_model is None
        assert automatic.credential_reference == explicit.credential_reference
        assert automatic.credential_revision == explicit.credential_revision
        with pytest.raises(ApiError) as stale:
            manager.require_configuration_connection(explicit)
        assert stale.value.code == 'connection_changed'
        assert manager.require_configuration_connection(automatic) is None
        manager.select('opencode-go', 'mimo-v2.6-pro')
        current = manager.configuration_connection()
        with pytest.raises(ApiError) as stale:
            manager.require_configuration_connection(automatic)
        assert stale.value.code == 'connection_changed'
    finally:
        await manager.close()
    reopened = ProviderManager(app_paths, http_transport=httpx.MockTransport(forbid_provider_usage))
    try:
        assert reopened.configuration_connection() == current
        assert reopened.require_configuration_connection(current) is None
        for old in [explicit, automatic]:
            with pytest.raises(ApiError) as stale:
                reopened.require_configuration_connection(old)
            assert stale.value.code == 'connection_changed'
    finally:
        await reopened.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('provider,record,model', [
    ('opencode-go', {'access_token': ''}, 'deepseek-v4.1-flash'),
    ('opencode-go', {'access_token': None}, 'deepseek-v4.1-flash'),
    ('codex', {'access_token': 'synthetic-expired', 'expires_at': 1}, 'gpt-6-astra'),
    ('codex', {'access_token': 'synthetic-invalid-expiry', 'expires_at': float('nan')}, 'gpt-6-astra'),
])
async def test_configuration_connection_denies_invalid_local_account_without_refresh_or_io(app_paths, provider, record, model):
    reference = str(uuid4())
    store = ConnectionStore(app_paths.root, app_paths.state)
    store.save({'version': 1, 'host_id': uuid4().urn, 'selected_provider': provider,
        'selected_models': {provider: model}, 'connections': {provider: record},
        'credential_metadata': {provider: {'reference': reference, 'epoch': 0, 'authentication_required': False}}})
    connection = ConnectionReference(provider=provider, credential_reference=reference,
        credential_revision=0, selected_model=model)
    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(forbid_provider_usage))
    try:
        protected_before = store.path.read_bytes()
        with pytest.raises(ApiError) as invalid:
            manager.configuration_connection()
        assert invalid.value.code == 'authentication_required'
        with pytest.raises(ApiError) as invalid:
            manager.require_configuration_connection(connection)
        assert invalid.value.code == 'authentication_required'
        assert store.path.read_bytes() == protected_before
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_configuration_connection_guard_requires_exact_automatic_identity_without_io(app_paths):
    legacy_selected_go_profile(app_paths)
    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(forbid_provider_usage))
    try:
        manager.select('opencode-go', None)
        automatic = manager.configuration_connection()
        assert automatic.selected_model is None
        protected_before = manager.store.path.read_bytes()
        assert manager.require_configuration_connection(automatic) is None
        for changed in [
            {'provider': 'codex'},
            {'credential_reference': str(uuid4())},
            {'credential_revision': automatic.credential_revision + 1},
            {'selected_model': 'deepseek-v4.1-flash'},
        ]:
            candidate = ConnectionReference(**{**automatic.model_dump(), **changed})
            with pytest.raises(ApiError) as stale:
                manager.require_configuration_connection(candidate)
            assert stale.value.code == 'connection_changed'
        for candidate in [None, automatic.model_dump()]:
            with pytest.raises(ApiError) as invalid:
                manager.require_configuration_connection(candidate)
            assert invalid.value.code == 'connection_changed'
        assert manager.store.path.read_bytes() == protected_before
    finally:
        await manager.close()
    reopened = ProviderManager(app_paths, http_transport=httpx.MockTransport(forbid_provider_usage))
    try:
        assert reopened.configuration_connection() == automatic
        assert reopened.require_configuration_connection(automatic) is None
    finally:
        await reopened.close()


@pytest.mark.asyncio
async def test_configuration_connection_bootstrap_is_exact_durable_and_private_without_provider_io(app_paths):
    legacy_selected_go_profile(app_paths)
    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(forbid_provider_usage))
    try:
        route = await manager.prepare_harness_route()
        protected_before = manager.store.path.read_bytes()
        before = manager.configuration_connection()
        assert isinstance(before, ConnectionReference)
        assert before.provider == 'opencode-go'
        assert before.selected_model == 'deepseek-v4.1-flash'
        assert (before.credential_reference, before.credential_revision) == (route.credential_ref, route.credential_epoch)
        assert manager.store.path.read_bytes() == protected_before
        if before.credential_reference in json.dumps(manager.connections()) + json.dumps(manager.status()):
            pytest.fail('Protected connection reference leaked into public status', pytrace=False)
    finally:
        await manager.close()
    reopened = ProviderManager(app_paths, http_transport=httpx.MockTransport(forbid_provider_usage))
    try:
        assert reopened.configuration_connection() == before
    finally:
        await reopened.close()


@pytest.mark.asyncio
async def test_configuration_connection_legacy_identity_requires_trusted_preparation_without_port_io(app_paths):
    legacy_selected_go_profile(app_paths)
    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(forbid_provider_usage))
    try:
        protected_before = manager.store.path.read_bytes()
        with pytest.raises(ApiError) as unanchored:
            manager.configuration_connection()
        assert unanchored.value.code == 'connection_changed'
        assert manager.store.path.read_bytes() == protected_before
        route = await manager.prepare_harness_route()
        current = manager.configuration_connection()
        assert current.credential_reference == route.credential_ref
        assert current.credential_revision == route.credential_epoch
        assert manager.require_configuration_connection(current) is None
    finally:
        await manager.close()


@pytest.mark.parametrize('metadata', [
    None, [], {'unapproved-provider': {}}, {'opencode-go': None},
    {'opencode-go': {}},
    *({'opencode-go': {'reference': reference, 'epoch': 0, 'authentication_required': False}}
      for reference in [None, 1, 'invalid-reference', '6BCE9A07-6511-40A6-A9F2-555972541409']),
    *({'opencode-go': {'reference': '6bce9a07-6511-40a6-a9f2-555972541409',
        'epoch': epoch, 'authentication_required': False}} for epoch in [-1, True, 1.5, '1']),
    {'opencode-go': {'reference': '6bce9a07-6511-40a6-a9f2-555972541409',
        'epoch': 0, 'authentication_required': 'false'}},
    {'opencode-go': {'reference': '6bce9a07-6511-40a6-a9f2-555972541409',
        'epoch': 0, 'authentication_required': False, 'extra': 'untrusted'}},
])
def test_malformed_durable_identity_fails_closed_without_rewriting_profile(app_paths, metadata):
    legacy_selected_go_profile(app_paths)
    store = ConnectionStore(app_paths.root, app_paths.state)
    settings = store.load()
    settings['credential_metadata'] = metadata
    store.save(settings)
    with pytest.raises(ApiError) as invalid:
        ProviderManager(app_paths, http_transport=httpx.MockTransport(forbid_provider_usage))
    assert invalid.value.code == 'connection_record_invalid'
    assert store.load()['credential_metadata'] == metadata
    assert str(invalid.value) == "Reconnect this profile's subscription."


@pytest.mark.asyncio
async def test_stale_refresh_cannot_discard_evidence_from_newer_successful_refresh(app_paths):
    legacy_selected_go_profile(app_paths)
    entered, release = asyncio.Event(), asyncio.Event()
    calls = 0

    async def catalogue(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            entered.set()
            await release.wait()
            return httpx.Response(200, json={'data': [{'id': 'mimo-v2.6-pro'}]})
        return httpx.Response(200, json={'data': [{'id': 'deepseek-v4.1-flash'}]})

    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(catalogue))
    pending = None
    try:
        await manager.prepare_harness_route()
        pending = asyncio.create_task(manager.refresh('opencode-go'))
        await asyncio.wait_for(entered.wait(), 3)
        await manager.refresh('opencode-go')
        current = await manager.prepare_harness_route()
        before = manager.harness_capabilities(current)
        assert before['catalogue_listed'] is True
        release.set()
        with pytest.raises(ApiError) as stale:
            await asyncio.wait_for(pending, 3)
        assert stale.value.code == 'connection_changed'
        assert manager.harness_capabilities(current) == before
    finally:
        release.set()
        if pending is not None:
            await asyncio.gather(pending, return_exceptions=True)
        await manager.close()


@pytest.mark.asyncio
async def test_inflight_codex_rotation_cannot_clear_newer_auth_invalidation(app_paths, monkeypatch):
    now = 1_900_000_000
    monkeypatch.setattr(time, 'time', lambda: now)
    legacy_selected_codex_profile(app_paths, expires_at=now + 600, refresh_token=uuid4().hex)
    entered, release = asyncio.Event(), asyncio.Event()

    async def rotate(request):
        if request.url.path == '/api/accounts/oauth/token':
            entered.set()
            await release.wait()
            return httpx.Response(200, json={'access_token': uuid4().hex, 'token_type': 'Bearer',
                'expires_in': 3600, 'scope': 'resource.invoke chatgpt.tokens.use.direct'})
        return httpx.Response(200, json={'models': [{'slug': 'gpt-6-astra'}]})

    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(rotate))
    pending = None
    try:
        route = await manager.prepare_harness_route()
        now += 600
        pending = asyncio.create_task(manager.refresh('codex'))
        await asyncio.wait_for(entered.wait(), 3)
        manager.observe_harness_result(route, code='authentication_required')
        denied_epoch = next(item for item in manager.connections()['connections']
            if item['provider'] == 'codex')['models'][1]['credential_epoch']
        release.set()
        with pytest.raises(ApiError) as stale:
            await asyncio.wait_for(pending, 3)
        assert stale.value.code == 'connection_changed'
    finally:
        release.set()
        if pending is not None:
            await asyncio.gather(pending, return_exceptions=True)
        await manager.close()
    reopened = ProviderManager(app_paths, http_transport=httpx.MockTransport(forbid_provider_usage))
    try:
        with pytest.raises(ApiError) as invalid:
            await reopened.prepare_harness_route()
        assert invalid.value.code == 'authentication_required'
        row = next(item for item in reopened.connections()['connections'] if item['provider'] == 'codex')
        assert row['models'][1]['credential_epoch'] == denied_epoch
    finally:
        await reopened.close()


@pytest.mark.asyncio
async def test_inflight_refresh_cannot_clear_newer_auth_invalidation_or_revive_it_on_reopen(app_paths):
    legacy_selected_go_profile(app_paths)
    entered, release = asyncio.Event(), asyncio.Event()

    async def catalogue(request):
        entered.set()
        await release.wait()
        return httpx.Response(200, json={'data': [{'id': 'deepseek-v4.1-flash'}]})

    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(catalogue))
    pending = None
    try:
        route = await manager.prepare_harness_route()
        pending = asyncio.create_task(manager.refresh('opencode-go'))
        await asyncio.wait_for(entered.wait(), 3)
        manager.observe_harness_result(route, code='authentication_required')
        denied_epoch = next(item for item in manager.connections()['connections']
            if item['provider'] == 'opencode-go')['models'][0]['credential_epoch']
        release.set()
        with pytest.raises(ApiError) as stale:
            await asyncio.wait_for(pending, 3)
        assert stale.value.code == 'connection_changed'
    finally:
        release.set()
        if pending is not None:
            await asyncio.gather(pending, return_exceptions=True)
        await manager.close()
    reopened = ProviderManager(app_paths, http_transport=httpx.MockTransport(forbid_provider_usage))
    try:
        with pytest.raises(ApiError) as invalid:
            await reopened.prepare_harness_route()
        assert invalid.value.code == 'authentication_required'
        row = next(item for item in reopened.connections()['connections'] if item['provider'] == 'opencode-go')
        assert row['models'][0]['credential_epoch'] == denied_epoch
    finally:
        await reopened.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('status,payload,code', [
    (401, {}, 'authentication_required'),
    (200, {'access_token': 'synthetic-invalid', 'token_type': 'invalid', 'expires_in': 3600,
        'scope': 'resource.invoke chatgpt.tokens.use.direct'}, 'invalid_token_response'),
    (200, {'access_token': 'synthetic-no-plan', 'token_type': 'Bearer', 'expires_in': 3600,
        'scope': 'resource.invoke'}, 'plan_permission_required'),
])
async def test_codex_refresh_rejection_durably_revokes_prepared_route(app_paths, monkeypatch, status, payload, code):
    now = 1_900_000_000
    monkeypatch.setattr(time, 'time', lambda: now)
    legacy_selected_codex_profile(app_paths, expires_at=now + 600, refresh_token=uuid4().hex)
    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(
        lambda request: httpx.Response(status, json=payload)))
    try:
        route = await manager.prepare_harness_route()
        now += 600
        with pytest.raises(ApiError) as invalid:
            await manager.prepare_harness_route()
        assert invalid.value.code == code
    finally:
        await manager.close()
    reopened = ProviderManager(app_paths, http_transport=httpx.MockTransport(forbid_provider_usage))
    try:
        with pytest.raises(ApiError) as stale:
            reopened.require_harness_route(route)
        assert stale.value.code == 'connection_changed'
        with pytest.raises(ApiError) as invalid:
            await reopened.prepare_harness_route()
        assert invalid.value.code == 'authentication_required'
        row = next(item for item in reopened.connections()['connections'] if item['provider'] == 'codex')
        assert row['status'] == 'authentication_required'
        assert row['models'][1]['credential_epoch'] > route.credential_epoch
    finally:
        await reopened.close()


@pytest.mark.asyncio
async def test_codex_token_rotation_persists_new_revision_and_protected_token_across_reopen(app_paths, monkeypatch):
    now = 1_900_000_000
    monkeypatch.setattr(time, 'time', lambda: now)
    legacy_selected_codex_profile(app_paths, expires_at=now + 600, refresh_token=uuid4().hex)
    rotated_token = uuid4().hex
    calls = []

    def rotate(request):
        calls.append((request.method, request.url.path))
        assert calls[-1] == ('POST', '/api/accounts/oauth/token')
        return httpx.Response(200, json={'access_token': rotated_token, 'refresh_token': uuid4().hex,
            'token_type': 'Bearer', 'expires_in': 3600,
            'scope': 'resource.invoke chatgpt.tokens.use.direct'})

    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(rotate))
    try:
        original = await manager.prepare_harness_route()
        assert not calls
        now += 600
        current = await manager.prepare_harness_route()
        assert current.credential_ref == original.credential_ref
        assert current.credential_epoch > original.credential_epoch
        assert calls == [('POST', '/api/accounts/oauth/token')]
        with pytest.raises(ApiError) as stale:
            manager.require_harness_route(original)
        assert stale.value.code == 'connection_changed'
    finally:
        await manager.close()
    reopened = ProviderManager(app_paths, http_transport=httpx.MockTransport(forbid_provider_usage))
    try:
        assert reopened.require_harness_route(current) is None
        if await reopened.credential_for_harness(current) != rotated_token:
            pytest.fail('Rotated protected credential was not retained', pytrace=False)
        if rotated_token in json.dumps(current.descriptor()) + json.dumps(reopened.status()):
            pytest.fail('Rotated credential leaked into public status', pytrace=False)
        with pytest.raises(ApiError) as stale:
            reopened.require_harness_route(original)
        assert stale.value.code == 'connection_changed'
        report = reopened.harness_capabilities(current)
        assert report['catalogue_listed'] is None
        assert report['documented_support']['image'] == 'supported'
        assert report['capability_evidence']['image'] == 'documented_model'
    finally:
        await reopened.close()


@pytest.mark.asyncio
async def test_explicit_refresh_after_reopen_recovers_under_new_revision_without_reviving_old_route(app_paths):
    legacy_selected_go_profile(app_paths)
    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(forbid_provider_usage))
    try:
        original = await manager.prepare_harness_route()
        manager.observe_harness_result(original, code='authentication_required')
        denied_epoch = next(item for item in manager.connections()['connections']
            if item['provider'] == 'opencode-go')['models'][0]['credential_epoch']
    finally:
        await manager.close()
    recovering = ProviderManager(app_paths, http_transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={'data': [{'id': 'mimo-v2.6-pro'}]})))
    try:
        with pytest.raises(ApiError) as invalid:
            await recovering.prepare_harness_route()
        assert invalid.value.code == 'authentication_required'
        await recovering.refresh('opencode-go')
        current = await recovering.prepare_harness_route()
        assert current.credential_ref == original.credential_ref
        assert current.credential_epoch > denied_epoch
        assert current.catalog_model_id == original.catalog_model_id
        assert current.catalogue_listed is False
    finally:
        await recovering.close()
    reopened = ProviderManager(app_paths, http_transport=httpx.MockTransport(forbid_provider_usage))
    try:
        assert reopened.require_harness_route(current) is None
        with pytest.raises(ApiError) as stale:
            reopened.require_harness_route(original)
        assert stale.value.code == 'connection_changed'
        reopened.observe_harness_result(original, code='authentication_required')
        assert reopened.require_harness_route(current) is None
    finally:
        await reopened.close()


@pytest.mark.asyncio
async def test_transient_refresh_preserves_valid_revision_but_does_not_persist_capability_evidence(app_paths):
    legacy_selected_go_profile(app_paths)
    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(
        lambda request: httpx.Response(503)))
    try:
        route = await manager.prepare_harness_route()
        manager.observe_harness_result(route, code='completed', images=True, tools=True)
        with pytest.raises(ApiError) as transient:
            await manager.refresh('opencode-go')
        assert transient.value.code == 'provider_unavailable'
        assert manager.require_harness_route(route) is None
        report = manager.harness_capabilities(route)
        assert report['credential_epoch'] == route.credential_epoch
        assert report['tool_input'] == 'supported'
        assert report['capability_evidence']['tools'] == 'completed_request'
    finally:
        await manager.close()
    reopened = ProviderManager(app_paths, http_transport=httpx.MockTransport(forbid_provider_usage))
    try:
        after = await reopened.prepare_harness_route()
        assert (after.credential_ref, after.credential_epoch) == (route.credential_ref, route.credential_epoch)
        assert reopened.require_harness_route(route) is None
        report = reopened.harness_capabilities(after)
        assert report['catalogue_listed'] is None
        assert report['documented_support'] == {'text': 'unknown', 'image': 'unknown', 'tools': 'unknown'}
        assert report['text_input'] == report['image_input'] == report['tool_input'] == 'unknown'
        assert report['capability_evidence'] == {'text': 'none', 'image': 'none', 'tools': 'none'}
        assert not reopened.status()['completed_requests']
    finally:
        await reopened.close()


@pytest.mark.asyncio
async def test_reconnect_and_disconnect_preserve_reference_and_revoke_routes_across_reopen(app_paths):
    legacy_selected_go_profile(app_paths)
    catalogue = httpx.MockTransport(lambda request: httpx.Response(200, json={
        'data': [{'id': 'deepseek-v4.1-flash'}]}))
    manager = ProviderManager(app_paths, http_transport=catalogue)
    try:
        original = await manager.prepare_harness_route()
        await manager.connect_go(uuid4().hex, select=True)
        reconnected = await manager.prepare_harness_route()
        assert reconnected.credential_ref == original.credential_ref
        assert reconnected.credential_epoch > original.credential_epoch
    finally:
        await manager.close()
    reopened = ProviderManager(app_paths, http_transport=catalogue)
    try:
        assert reopened.require_harness_route(reconnected) is None
        with pytest.raises(ApiError) as stale:
            reopened.require_harness_route(original)
        assert stale.value.code == 'connection_changed'
        await reopened.disconnect('opencode-go')
        disconnected_epoch = next(item for item in reopened.connections()['connections']
            if item['provider'] == 'opencode-go')['models'][0]['credential_epoch']
        assert disconnected_epoch > reconnected.credential_epoch
    finally:
        await reopened.close()
    signed_out = ProviderManager(app_paths, http_transport=catalogue)
    try:
        assert signed_out.connections()['selected_provider'] is None
        assert next(item for item in signed_out.connections()['connections']
            if item['provider'] == 'opencode-go')['models'][0]['credential_epoch'] == disconnected_epoch
        await signed_out.connect_go(uuid4().hex, select=True)
        newest = await signed_out.prepare_harness_route()
        assert newest.credential_ref == original.credential_ref
        assert newest.credential_epoch > disconnected_epoch
        for old in [original, reconnected]:
            with pytest.raises(ApiError) as stale:
                signed_out.require_harness_route(old)
            assert stale.value.code == 'connection_changed'
    finally:
        await signed_out.close()
    final = ProviderManager(app_paths, http_transport=httpx.MockTransport(forbid_provider_usage))
    try:
        assert final.require_harness_route(newest) is None
        for old in [original, reconnected]:
            with pytest.raises(ApiError) as stale:
                final.require_harness_route(old)
            assert stale.value.code == 'connection_changed'
    finally:
        await final.close()


@pytest.mark.asyncio
async def test_missing_codex_refresh_token_durably_revokes_prepared_identity(app_paths, monkeypatch):
    now = 1_900_000_000
    monkeypatch.setattr(time, 'time', lambda: now)
    legacy_selected_codex_profile(app_paths, expires_at=now + 600)
    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(forbid_provider_usage))
    try:
        route = await manager.prepare_harness_route()
        now += 600
        with pytest.raises(ApiError) as invalid:
            await manager.prepare_harness_route()
        assert invalid.value.code == 'authentication_required'
        with pytest.raises(ApiError) as stale:
            manager.require_harness_route(route)
        assert stale.value.code == 'connection_changed'
    finally:
        await manager.close()
    reopened = ProviderManager(app_paths, http_transport=httpx.MockTransport(forbid_provider_usage))
    try:
        with pytest.raises(ApiError) as stale:
            reopened.require_harness_route(route)
        assert stale.value.code == 'connection_changed'
        row = next(item for item in reopened.connections()['connections'] if item['provider'] == 'codex')
        assert row['status'] == 'authentication_required'
        assert row['models'][1]['credential_epoch'] > route.credential_epoch
    finally:
        await reopened.close()


@pytest.mark.asyncio
async def test_prepared_identity_survives_protected_profile_reopen_without_provider_usage(app_paths):
    legacy_selected_go_profile(app_paths)
    first = ProviderManager(app_paths, http_transport=httpx.MockTransport(forbid_provider_usage))
    try:
        before = await first.prepare_harness_route()
    finally:
        await first.close()
    reopened = ProviderManager(app_paths, http_transport=httpx.MockTransport(forbid_provider_usage))
    try:
        after = await reopened.prepare_harness_route()
        assert (after.credential_ref, after.credential_epoch) == (before.credential_ref, before.credential_epoch)
        assert reopened.require_harness_route(before) is None
        assert after.catalog_model_id == 'deepseek-v4.1-flash'
        assert reopened.harness_capabilities(before)['catalogue_listed'] is None
        assert reopened.harness_capabilities(before)['capability_evidence']['text'] == 'none'
    finally:
        await reopened.close()


@pytest.mark.asyncio
async def test_native_auth_invalidation_survives_reopen_without_reviving_old_route(app_paths):
    legacy_selected_go_profile(app_paths)
    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(forbid_provider_usage))
    try:
        route = await manager.prepare_harness_route()
        manager.observe_harness_result(route, code='authentication_required')
    finally:
        await manager.close()
    reopened = ProviderManager(app_paths, http_transport=httpx.MockTransport(forbid_provider_usage))
    try:
        with pytest.raises(ApiError) as stale:
            reopened.require_harness_route(route)
        assert stale.value.code == 'connection_changed'
        with pytest.raises(ApiError) as invalid:
            await reopened.prepare_harness_route()
        assert invalid.value.code == 'authentication_required'
        row = next(item for item in reopened.connections()['connections'] if item['provider'] == 'opencode-go')
        assert row['models'][0]['credential_epoch'] > route.credential_epoch
        assert row['status'] == 'authentication_required'
    finally:
        await reopened.close()


@pytest.mark.asyncio
async def test_explicit_successful_refresh_persists_new_epoch_and_keeps_old_route_revoked(app_paths):
    legacy_selected_go_profile(app_paths)
    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={'data': [{'id': 'deepseek-v4.1-flash'}]})))
    try:
        original = await manager.prepare_harness_route()
        await manager.refresh('opencode-go')
        refreshed = await manager.prepare_harness_route()
        assert refreshed.credential_ref == original.credential_ref
        assert refreshed.credential_epoch > original.credential_epoch
    finally:
        await manager.close()
    reopened = ProviderManager(app_paths, http_transport=httpx.MockTransport(forbid_provider_usage))
    try:
        current = await reopened.prepare_harness_route()
        assert current.credential_epoch == refreshed.credential_epoch
        assert reopened.require_harness_route(refreshed) is None
        with pytest.raises(ApiError) as stale:
            reopened.require_harness_route(original)
        assert stale.value.code == 'connection_changed'
    finally:
        await reopened.close()


@pytest.mark.asyncio
async def test_explicit_refresh_auth_failure_remains_revoked_after_reopen(app_paths):
    legacy_selected_go_profile(app_paths)
    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(
        lambda request: httpx.Response(401)))
    try:
        route = await manager.prepare_harness_route()
        with pytest.raises(ApiError) as failed:
            await manager.refresh('opencode-go')
        assert failed.value.code == 'authentication_required'
    finally:
        await manager.close()
    reopened = ProviderManager(app_paths, http_transport=httpx.MockTransport(forbid_provider_usage))
    try:
        with pytest.raises(ApiError) as stale:
            reopened.require_harness_route(route)
        assert stale.value.code == 'connection_changed'
        with pytest.raises(ApiError) as invalid:
            await reopened.prepare_harness_route()
        assert invalid.value.code == 'authentication_required'
    finally:
        await reopened.close()


@pytest.mark.asyncio
async def test_transient_refresh_does_not_clear_durable_auth_block_or_advance_revision(app_paths):
    legacy_selected_go_profile(app_paths)
    status = 503
    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(
        lambda request: httpx.Response(status, json={'data': [{'id': 'deepseek-v4.1-flash'}]})))
    try:
        route = await manager.prepare_harness_route()
        manager.observe_harness_result(route, code='authentication_required')
        epoch = next(item for item in manager.connections()['connections']
            if item['provider'] == 'opencode-go')['models'][0]['credential_epoch']
        with pytest.raises(ApiError) as transient:
            await manager.refresh('opencode-go')
        assert transient.value.code == 'provider_unavailable'
        with pytest.raises(ApiError) as invalid:
            await manager.prepare_harness_route()
        assert invalid.value.code == 'authentication_required'
        assert next(item for item in manager.connections()['connections']
            if item['provider'] == 'opencode-go')['models'][0]['credential_epoch'] == epoch
    finally:
        await manager.close()
    reopened = ProviderManager(app_paths, http_transport=httpx.MockTransport(forbid_provider_usage))
    try:
        with pytest.raises(ApiError) as invalid:
            await reopened.prepare_harness_route()
        assert invalid.value.code == 'authentication_required'
        assert next(item for item in reopened.connections()['connections']
            if item['provider'] == 'opencode-go')['models'][0]['credential_epoch'] == epoch
    finally:
        await reopened.close()


@pytest.mark.asyncio
async def test_legacy_generation_auth_failure_remains_revoked_after_reopen(app_paths):
    legacy_selected_go_profile(app_paths)

    class DeniedInference:
        async def stream(self, provider, model, token, messages):
            raise ApiError('authentication_required', 'Synthetic authentication failure', 401)
            yield

    manager = ProviderManager(app_paths, transport=DeniedInference(),
        http_transport=httpx.MockTransport(forbid_provider_usage))
    try:
        route = await manager.prepare_harness_route()
        events = [item async for item in manager.events(
            [{'role': 'user', 'content': 'Synthetic CKD learning'}],
            scope=ContextScope(kind=Scope.TEMPORARY_CASE), run_id='durable-legacy-denial')]
        assert events[-1].payload['code'] == 'authentication_required'
    finally:
        await manager.close()
    reopened = ProviderManager(app_paths, http_transport=httpx.MockTransport(forbid_provider_usage))
    try:
        with pytest.raises(ApiError) as stale:
            reopened.require_harness_route(route)
        assert stale.value.code == 'connection_changed'
        with pytest.raises(ApiError) as invalid:
            await reopened.prepare_harness_route()
        assert invalid.value.code == 'authentication_required'
    finally:
        await reopened.close()


@pytest.mark.asyncio
async def test_selected_default_prepares_exact_wire_route_without_credential_in_descriptor(app_paths, monkeypatch):
    canary = uuid4().hex
    monkeypatch.setenv("OPENAI_API_KEY", uuid4().hex)
    calls = []

    def serve(request):
        calls.append(request.url.path)
        return httpx.Response(200, json={"data": [{"id": "mimo-v2.6-pro"}]})

    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(serve))
    await manager.connect_go(canary, select=True)
    manager.select("opencode-go", "deepseek-v4.1-flash")
    route = await manager.prepare_harness_route()
    descriptor = route.descriptor()
    assert descriptor["provider_id"] == "opencode-go"
    assert descriptor["catalog_model_id"] == descriptor["wire_model_id"] == "deepseek-v4.1-flash"
    assert descriptor["endpoint"] == "https://opencode.ai/zen/go/v1/chat/completions"
    assert descriptor["protocol"] == "openai-chat"
    assert descriptor["catalogue_listed"] is False
    assert isinstance(descriptor["credential_ref"], str)
    if canary in json.dumps(descriptor) + repr(route) + json.dumps(manager.status()):
        pytest.fail("Credential leaked into a public route", pytrace=False)
    assert calls == ["/zen/go/v1/models"]


@pytest.mark.asyncio
async def test_harness_401_invalidates_reference_until_explicit_refresh_and_preserves_selection(app_paths):
    canary = uuid4().hex
    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"data": [{"id": "mimo-v2.6-pro"}]})))
    await manager.connect_go(canary, select=True)
    route = await manager.prepare_harness_route()
    if await manager.credential_for_harness(route) != canary:
        pytest.fail("Protected lookup returned the wrong credential", pytrace=False)
    manager.observe_harness_result(route, code="authentication_required")
    with pytest.raises(ApiError) as denied:
        await manager.credential_for_harness(route)
    assert denied.value.code == "connection_changed"
    with pytest.raises(ApiError) as blocked:
        await manager.prepare_harness_route()
    assert blocked.value.code == "authentication_required"
    await manager.refresh("opencode-go")
    fresh = await manager.prepare_harness_route()
    assert fresh.credential_epoch > route.credential_epoch
    assert manager.connections()["selected_provider"] == "opencode-go"
    with pytest.raises(ApiError):
        await manager.credential_for_harness(route)
    manager.observe_harness_result(route, code="authentication_required")
    assert manager.connections()["connections"][1]["status"] == "connected"


@pytest.mark.asyncio
async def test_old_completion_cannot_restore_observations_after_another_run_gets_401(app_paths):
    entered, release = asyncio.Event(), asyncio.Event()

    class ExternalInference:
        async def stream(self, provider, model, token, messages):
            if messages[0]["content"] == "Synthetic old answer":
                entered.set()
                await release.wait()
                yield {"type": "completed"}
            else:
                raise ApiError("authentication_required", "Synthetic authentication failure", 401)

    manager = ProviderManager(app_paths, transport=ExternalInference(), http_transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"data": [{"id": "mimo-v2.6-pro"}]})))
    await manager.connect_go(uuid4().hex, select=True)

    async def events(text, run):
        return [item async for item in manager.events([{"role": "user", "content": text}],
            scope=ContextScope(kind=Scope.TEMPORARY_CASE), run_id=run)]

    old = asyncio.create_task(events("Synthetic old answer", "old-answer"))
    try:
        await asyncio.wait_for(entered.wait(), 3)
        failed = await events("Synthetic denied answer", "denied-answer")
        assert failed[-1].payload["code"] == "authentication_required"
        release.set()
        flow = await asyncio.wait_for(old, 3)
        assert flow[-1].type == "error" and flow[-1].payload["code"] == "connection_changed"
        model = manager.connections()["connections"][1]["models"][0]
        assert model["text_input"] == "unknown"
        assert model["capability_evidence"]["text"] == "none"
        assert not manager.status()["completed_requests"]
    finally:
        release.set()
        await manager.close()
        await asyncio.gather(old, return_exceptions=True)


@pytest.mark.asyncio
async def test_explicit_refresh_401_invalidates_previously_observed_access(app_paths):
    denied = False

    def serve(request):
        return httpx.Response(401 if denied else 200, json={"data": [{"id": "mimo-v2.6-pro"}]})

    class SyntheticInference:
        async def stream(self, provider, model, token, messages):
            yield {"type": "completed"}

    manager = ProviderManager(app_paths, transport=SyntheticInference(), http_transport=httpx.MockTransport(serve))
    try:
        await manager.connect_go(uuid4().hex, select=True)
        [item async for item in manager.stream([{"role": "user", "content": "Synthetic renal learning"}],
            scope=ContextScope(kind=Scope.TEMPORARY_CASE), run_id="access-observation")]
        before = await manager.prepare_harness_route()
        assert manager.connections()["connections"][1]["models"][0]["text_input"] == "supported"
        denied = True
        with pytest.raises(ApiError):
            await manager.refresh("opencode-go")
        after = manager.connections()["connections"][1]["models"][0]
        assert after["availability"] == after["text_input"] == after["image_input"] == "unknown"
        assert after["credential_epoch"] > before.credential_epoch
        with pytest.raises(ApiError) as stale:
            await manager.credential_for_harness(before)
        assert stale.value.code == "connection_changed"
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_capability_report_and_observations_are_bound_to_the_prepared_route(app_paths):
    status = 200
    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(
        lambda request: httpx.Response(status, json={"data": [{"id": "mimo-v2.6-pro"}]})))
    try:
        await manager.connect_go(uuid4().hex, select=True)
        route = await manager.prepare_harness_route()
        before = manager.harness_capabilities(route)
        assert before["route"] == route.descriptor()
        assert before["documented_support"] == {"text": "unknown", "image": "unknown", "tools": "unknown"}
        assert before["tool_input"] == "unknown"
        manager.observe_harness_result(route, code="completed", images=True, tools=True)
        observed = manager.harness_capabilities(route)
        assert observed["text_input"] == observed["image_input"] == observed["tool_input"] == "supported"
        assert observed["capability_evidence"]["tools"] == "completed_request"
        assert not observed["image_interpretation_verified"]
        status = 503
        with pytest.raises(ApiError):
            await manager.refresh("opencode-go")
        transient = manager.harness_capabilities(route)
        assert transient["availability"] == "unknown"
        assert transient["credential_epoch"] == route.credential_epoch
        assert transient["image_input"] == transient["tool_input"] == "supported"
        manager.observe_harness_result(route, code="authentication_required")
        with pytest.raises(ApiError):
            manager.harness_capabilities(route)
        status = 200
        await manager.refresh("opencode-go")
        current = await manager.prepare_harness_route()
        manager.observe_harness_result(route, code="completed", images=True, tools=True)
        assert manager.harness_capabilities(current)["tool_input"] == "unknown"
        manager.observe_harness_result(current, code="unsupported_image_input", images=True)
        assert manager.harness_capabilities(current)["image_input"] == "account_unsupported"
        manager.observe_harness_result(current, code="model_access_denied")
        assert manager.connections()["connections"][1]["models"][0]["availability"] == "account_unsupported"
    finally:
        await manager.close()


def test_final_image_decoder_reuses_existing_mime_pixel_and_frame_limits():
    import base64
    from io import BytesIO

    from PIL import Image
    from renulus.runtime.provider_adapter import validate_harness_images

    def image(size=(1, 1), fmt="PNG"):
        buffer = BytesIO()
        Image.new("L", size).save(buffer, format=fmt)
        return {"type": "image", "media_type": "image/" + fmt.lower(),
                "data": base64.b64encode(buffer.getvalue()).decode("ascii")}

    valid = image()
    assert validate_harness_images([valid]) is None
    for images in [[{**valid, "media_type": "image/jpeg"}],
                   [image(size=(4001, 4000))], [valid] * 5,
                   [{**valid, "data": base64.b64encode(b"\x89PNG\r\n\x1a\n").decode("ascii")}],
                   [{"type": "text", "text": "Supply no image"}],
                   [{**valid, "data": uuid4().hex}]]:
        with pytest.raises(ApiError):
            validate_harness_images(images)


@pytest.mark.asyncio
async def test_gateway_public_revalidation_and_redacted_errors_require_no_private_access(app_paths):
    from renulus.runtime.provider_adapter import SubscriptionRoute

    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"data": [{"id": "mimo-v2.6-pro"}]})))
    try:
        await manager.connect_go(uuid4().hex, select=True)
        route = SubscriptionRoute(**(await manager.prepare_harness_route()).descriptor())
        assert manager.require_harness_route(route) is None
        manager.observe_harness_stream_error(route, "unsupported_image_input", images=True)
        assert manager.harness_capabilities(route)["image_input"] == "account_unsupported"
        canary = uuid4().hex
        request = httpx.Request("POST", route.endpoint)
        error = httpx.HTTPStatusError(canary, request=request, response=httpx.Response(401, request=request))
        public = manager.observe_harness_error(route, error)
        assert public.code == "authentication_required"
        if canary in str(public) + repr(public):
            pytest.fail("Credential leaked into a gateway error", pytrace=False)
        with pytest.raises(ApiError) as stale:
            manager.require_harness_route(route)
        assert stale.value.code == "connection_changed"
        await manager.refresh("opencode-go")
        current = await manager.prepare_harness_route()
        manager.observe_harness_stream_error(route, "invalid_api_key")
        assert manager.require_harness_route(current) is None
    finally:
        await manager.close()
