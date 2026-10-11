"""H06 deletion keeps only opaque command tombstones in new exports."""
import json

from fastapi.testclient import TestClient

from renulus.server import create_app
from renulus.storage.backup import export_records, restore_records


def test_deleted_saved_owner_scrubs_creation_and_draft_receipts_and_replay(tmp_path):
    profile = tmp_path / 'retired-saved-owner'
    app = create_app(profile)
    create_key, draft_key, delete_key = ('synthetic-create-receipt',
        'synthetic-draft-receipt', 'synthetic-delete-receipt')
    original = {'title': 'SYNTHETIC_RETIRED_TITLE_DELTA_47'}
    with TestClient(app) as client:
        created = client.post('/api/v1/conversations', json=original,
            headers={'Idempotency-Key': create_key})
        assert created.status_code == 201
        chat = created.json()
        route = '/api/v1/conversations/learning/' + chat['identity']['id']
        draft = {'expected_revision': chat['revision'],
            'text': 'SYNTHETIC_RETIRED_DRAFT_DELTA_47'}
        saved = client.put(route + '/draft', json=draft,
            headers={'Idempotency-Key': draft_key})
        assert saved.status_code == 200
        before = client.get('/api/v1/data/export')
        assert before.status_code == 200
        receipts = before.json()['records']['conversation_commands']
        hashes = [row['request_hash'] for row in receipts]
        assert len(hashes) == 2
        deleted = client.delete(route,
            params={'expected_revision': saved.json()['conversation_revision']},
            headers={'Idempotency-Key': delete_key})
        assert deleted.status_code == 200
        after = client.get('/api/v1/data/export')
        assert after.status_code == 200
        exported = json.dumps(after.json())
        assert original['title'] not in exported and draft['text'] not in exported
        assert all(digest not in exported for digest in hashes)
        assert client.get(route).status_code == 404

    reopened = create_app(profile)
    with TestClient(reopened) as client:
        replays = [
            client.post('/api/v1/conversations', json=original,
                headers={'Idempotency-Key': create_key}),
            client.post('/api/v1/conversations', json={'title': 'Different deleted request'},
                headers={'Idempotency-Key': create_key}),
            client.put(route + '/draft', json=draft,
                headers={'Idempotency-Key': draft_key}),
            client.delete(route, params={'expected_revision': saved.json()['conversation_revision']},
                headers={'Idempotency-Key': delete_key}),
        ]
        for response in replays:
            assert response.status_code == 410, response.text
            assert response.json()['error']['code'] == 'command_terminal_unavailable'
            assert response.json()['error']['retryable'] is False
        assert client.get('/api/v1/conversations').json()['items'] == []
        assert client.get('/api/v1/data/export').json()['records']['conversation_commands'] == []


def test_older_records_restore_cannot_reintroduce_retired_command_payload(tmp_path):
    app = create_app(tmp_path / 'retired-command-restore')
    key = 'synthetic-retired-backup-create'
    request = {'title': 'SYNTHETIC_OLD_EXPORT_TITLE_47'}
    with TestClient(app) as client:
        created = client.post('/api/v1/conversations', json=request,
            headers={'Idempotency-Key': key})
        assert created.status_code == 201
        chat = created.json()
        before = export_records(app.state.services)
        route = '/api/v1/conversations/learning/' + chat['identity']['id']
        assert client.delete(route, params={'expected_revision': chat['revision']}).status_code == 200
        restored = restore_records(app.state.services, before, confirm_older=True)
        assert restored['excluded_by_deletion'] > 0
        exported = export_records(app.state.services)
        assert exported['records']['conversation_commands'] == []
        assert request['title'] not in json.dumps(exported)
        replay = client.post('/api/v1/conversations', json=request,
            headers={'Idempotency-Key': key})
        assert replay.status_code == 410
        assert replay.json()['error']['code'] == 'command_terminal_unavailable'
