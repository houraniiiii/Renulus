"""Explicit Library catalogue state for owned app construction."""
import json
from pathlib import Path

from fastapi.testclient import TestClient


def test_explicit_collection_constructs_original_app_without_home_lookup(tmp_path, monkeypatch):
    from renulus.server import create_app

    root = tmp_path / 'synthetic-collection'
    manifest = root / 'metadata/acquisition-2026-10-04/acquisition-manifest.jsonl'
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({
        'source_id': 'R01', 'title': 'Synthetic owned catalogue receipt',
        'local_path': 'raw/R01/synthetic-note.txt', 'sha256': 'a' * 64, 'bytes': 9,
        'processing_scope': {'display': True, 'cache': True, 'index': True,
                             'embedding': True, 'model_input': True},
        'licence': {'identifier': 'CC-BY-4.0'},
    }) + '\n', encoding='utf-8')

    def unavailable_home():
        raise AssertionError('Owned catalogue construction must not resolve a system home')

    with monkeypatch.context() as guard:
        guard.setattr(Path, 'home', staticmethod(unavailable_home))
        app = create_app(tmp_path / 'profile', collection_root=root)
    with TestClient(app) as client:
        response = client.get('/api/v1/library/collection/preview', params={'source_id': 'R01'})
        assert response.status_code == 200
        observed = response.json()
        assert observed['total'] == 1 and observed['indexed'] is False
        assert observed['errors'] == []
        assert observed['entries'][0]['title'] == 'Synthetic owned catalogue receipt'
        assert observed['entries'][0]['collection_path'] == 'raw/R01/synthetic-note.txt'
        assert client.get('/api/v1/library/documents').json()['documents'] == []


def test_default_collection_retains_documents_location(tmp_path, monkeypatch):
    from renulus.server import create_app

    home = tmp_path / 'synthetic-home'
    manifest = home / 'Documents/Renulus-data/metadata/acquisition-2026-10-04/acquisition-manifest.jsonl'
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({'source_id': 'R01', 'title': 'Synthetic default catalogue',
                                  'local_path': 'raw/R01/default.txt',
                                  'sha256': 'b' * 64, 'bytes': 7}) + '\n', encoding='utf-8')
    with monkeypatch.context() as guard:
        guard.setattr(Path, 'home', staticmethod(lambda: home))
        app = create_app(tmp_path / 'profile')
    with TestClient(app) as client:
        response = client.get('/api/v1/library/collection/preview', params={'source_id': 'R01'})
        assert response.status_code == 200
        observed = response.json()
        assert observed['total'] == 1 and observed['errors'] == []
        assert observed['entries'][0]['title'] == 'Synthetic default catalogue'
