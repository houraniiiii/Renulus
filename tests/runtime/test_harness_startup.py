"""Explicit managed-startup configuration, before profile provisioning."""
import json
from pathlib import Path

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
