"""Configuration routes on the existing local server, without account usage."""
import httpx
import os
from pathlib import Path

from renulus.runtime.harness_configuration import ConfigurationAuthority
from renulus.runtime.harness_learning import HarnessLearningOwner
from renulus.runtime.harness_process import HarnessProcessConfig

from renulus.server import create_app


async def test_unassembled_harness_settings_is_explicitly_unavailable_on_the_existing_server(tmp_path):
    app = create_app(tmp_path / 'profile')
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://testserver') as client:
            response = await client.get('/api/v1/runtime/harness/configuration')
        assert response.status_code == 503
        assert response.json()['error']['code'] == 'harness_configuration_unavailable'
        assert response.json()['error']['retryable'] is True
        assert response.headers['cache-control'] == 'no-store'
    finally:
        app.state.services.get('helpers').startup.close()


async def test_explicit_assembly_exposes_null_configuration_and_drains_its_owners(tmp_path):
    from renulus.runtime.harness_configuration_lifecycle import install_harness_configuration

    app = create_app(tmp_path / 'profile')
    services = app.state.services
    config = HarnessProcessConfig(node_executable=Path(os.environ['RENULUS_HARNESS_NODE']),
        host_entry=Path(__file__).resolve().parents[2] / 'packages/harness/test/fixtures/configuration-probe-host.mjs',
        profile_root=services.paths.root, profile_id='synthetic-profile', store_id='synthetic-runtime',
        domain_store_id='synthetic-domain', domain_path='state/renulus.sqlite3')
    owner = HarnessLearningOwner(services, config, configuration_id='a' * 64)
    owner.install()
    authority = ConfigurationAuthority(services.db)
    install_harness_configuration(owner, authority=authority, candidate_root=tmp_path / 'candidates')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://testserver') as client:
        response = await client.get('/api/v1/runtime/harness/configuration')
        assert response.status_code == 200
        data = response.json()
        assert data['requested'] is data['effective'] is data['failed'] is None
        assert data['admission_open'] is False and data['catalogue'] == []
        refused = await client.post('/api/v1/runtime/harness/configuration',
            json={'roles': [{'purpose': 'explain'}]})
        assert refused.status_code == 409
        assert refused.json()['error']['code'] == 'configuration_not_active'
        assert (await client.get('/api/v1/runtime/harness/configuration')).json() == data
    assert (await services.shutdown(timeout=5))['state'] == 'settled'
    assert (await owner.process.settlement(0))['state'] == 'settled'
