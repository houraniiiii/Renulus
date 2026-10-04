from fastapi.testclient import TestClient

from renulus.server import create_app

from .conftest import SOURCE_ROOT


def test_feature_router_real_sqlite_missing_helpers_full_manual_flow(tmp_path):
    app = create_app(tmp_path / 'api-profile', source_root=SOURCE_ROOT)
    with TestClient(app) as client:
        response = client.post('/api/v1/memory/facts', json={'text': 'A synthetic learning point.',
            'scope': {'kind': 'study'}, 'idempotency_key': 'api-add-1'})
        assert response.status_code == 201
        record = response.json()
        identifier = record['id']
        assert client.get('/api/v1/memory/facts').json()['records'][0]['text'] == record['text']
        edit = client.patch('/api/v1/memory/facts/' + identifier, json={
            'text': 'Corrected synthetic learning.', 'expected_revision': 1})
        assert edit.status_code == 200 and edit.json()['revision'] == 2
        stale = client.patch('/api/v1/memory/facts/' + identifier, json={
            'text': 'Stale late edit.', 'expected_revision': 1})
        assert stale.status_code == 409 and stale.json()['error']['code'] == 'memory_revision_conflict'
        history = '/api/v1/memory/facts/' + identifier + '/history'
        assert len(client.get(history).json()['history']) == 2
        assert client.delete(history).json()['purged']
        assert client.get(history).json()['history'] == []
        assert client.delete('/api/v1/memory/facts/' + identifier + '?expected_revision=2').json()['deleted']
        assert client.get('/api/v1/memory/facts').json()['records'] == []
        assert client.get('/api/v1/memory/status').json()['producer'] == 'mem0-oss'
        assert not client.get('/api/v1/memory/status').json()['index']['helper_ready']


def test_api_excluded_scope_and_validation_do_not_echo_or_persist(tmp_path):
    app = create_app(tmp_path / 'api-profile', source_root=SOURCE_ROOT)
    sentinel = 'SYNTHETIC_UNCLASSIFIED_SENTINEL_318276'
    with TestClient(app) as client:
        for kind in ('temporary-case', 'unclassified', 'saved-case'):
            response = client.post('/api/v1/memory/facts', json={'text': sentinel,
                'scope': {'kind': kind}, 'idempotency_key': sentinel})
            assert response.status_code == 409
            assert sentinel not in response.text
            query = client.post('/api/v1/memory/search', json={'query': sentinel, 'scope': {'kind': kind}})
            assert query.status_code == 409 and sentinel not in query.text
        invalid = client.post('/api/v1/memory/facts', json={'text': sentinel, 'scope': {'kind': 'garbled'}})
        assert invalid.status_code == 422 and sentinel not in invalid.text
        assert client.get('/api/v1/memory/jobs').json()['jobs'] == []
    paths = app.state.services.paths
    assert all(sentinel.encode() not in path.read_bytes() for path in paths.root.rglob('*') if path.is_file())
