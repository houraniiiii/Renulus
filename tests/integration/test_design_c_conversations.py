# SPDX-License-Identifier: MIT
"""Connected conversations use the real legacy owners and additive sidecars."""
from fastapi.testclient import TestClient
import pytest
import json

from renulus.server import create_app
from renulus.learn.conversation_api import create_router


def app_at(profile):
    app = create_app(profile)
    if "conversations" not in app.state.services.registry:
        app.include_router(create_router(app.state.services), prefix="/api/v1")
    return app


@pytest.mark.parametrize("kind", ["learning", "case"])
def test_saved_default_chat_and_draft_survive_restart_using_original_owner(tmp_path, kind):
    profile = tmp_path / "saved-chat"
    with TestClient(app_at(profile)) as client:
        created = client.post("/api/v1/conversations", json={"kind": kind, "title": "Fictional CKD study"})
        assert created.status_code == 201, created.text
        chat = created.json()
        assert chat["retention"] == "saved" and chat["project_id"] is None
        identifier = chat["identity"]["id"]
        route = f"/api/v1/conversations/{kind}/{identifier}"
        written = client.put(route + "/draft", json={"expected_revision": chat["revision"],
            "text": "Explain this fictional nephrology topic.", "content_refs": []})
        assert written.status_code == 200, written.text
    with TestClient(app_at(profile)) as restarted:
        result = restarted.get(route).json()
        assert result["identity"] == chat["identity"]
        assert restarted.get(route + "/draft").json()["text"] == "Explain this fictional nephrology topic."
        owner_route = f"/api/v1/learn/threads/{identifier}" if kind == "learning" else f"/api/v1/cases/sessions/{identifier}"
        assert restarted.get(owner_route).status_code == 200


@pytest.mark.parametrize("kind", ["learning", "case"])
def test_archive_restore_rename_and_delete_preserve_revision_and_draft(tmp_path, kind):
    with TestClient(app_at(tmp_path / "chat-lifecycle")) as client:
        chat = client.post("/api/v1/conversations", json={"kind": kind}).json()
        route = f"/api/v1/conversations/{kind}/{chat['identity']['id']}"
        saved = client.put(route + "/draft", json={"expected_revision": chat["revision"], "text": "A retained draft"}).json()
        renamed = client.patch(route, json={"expected_revision": saved["conversation_revision"], "title": "Renamed CKD discussion"})
        assert renamed.status_code == 200, renamed.text
        revision = renamed.json()["revision"]
        archived = client.post(route + "/archive", json={"expected_revision": revision})
        assert archived.status_code == 200, archived.text
        assert client.get("/api/v1/conversations").json()["items"] == []
        assert client.get("/api/v1/conversations?lifecycle=archived").json()["items"][0]["identity"] == chat["identity"]
        restored = client.post(route + "/restore", json={"expected_revision": archived.json()["revision"]}).json()
        assert client.get(route + "/draft").json()["text"] == "A retained draft"
        assert client.patch(route, json={"expected_revision": revision, "title": "Stale title"}).status_code == 409
        deleted = client.delete(route, params={"expected_revision": restored["revision"]})
        assert deleted.status_code == 200, deleted.text
        assert client.get(route).status_code == 404
        assert client.get("/api/v1/conversations").json()["items"] == []


def test_saved_command_replay_survives_restart_and_checks_present_policy(tmp_path):
    profile = tmp_path / 'command-replay'
    body = {'kind': 'learning', 'title': 'Fictional dialysis learning'}
    headers = {'Idempotency-Key': 'create-command-1234'}
    with TestClient(app_at(profile)) as client:
        original = client.post('/api/v1/conversations', json=body, headers=headers).json()
    app = app_at(profile)
    with TestClient(app) as client:
        assert client.post('/api/v1/conversations', json=body, headers=headers).json() == original
        assert client.post('/api/v1/conversations', json={**body, 'title': 'Different'}, headers=headers).status_code == 409
        # A real active Test row is installed by the assessment owner; this fixture
        # tests the shared disclosure boundary through the conversation API.
        app.state.services.db.execute(
            "INSERT INTO assessment_test_attempts(id,version_id,version_snapshot_json,mode,clock_high_water_at,created_at,updated_at) "
            "VALUES('policy-test','pinned-unavailable','{}','test',?,?,?)",
            (original['created_at'],) * 3)
        denied = client.post('/api/v1/conversations', json=body, headers=headers)
        assert denied.status_code == 409 and denied.json()['error']['code'] == 'assistance_restricted'


@pytest.mark.parametrize('kind', ['learning', 'case'])
def test_temporary_draft_and_delete_leave_no_durable_identity_or_payload(tmp_path, kind):
    from renulus.storage.backup import export_records
    profile = tmp_path / 'volatile-chat'
    app = app_at(profile)
    with TestClient(app) as client:
        chat = client.post('/api/v1/conversations', json={'kind': kind, 'temporary': True}).json()
        identifier = chat['identity']['id']
        route = f'/api/v1/conversations/{kind}/{identifier}'
        marker = 'FICTIONAL_VOLATILE_DRAFT_981427'
        draft = client.put(route + '/draft', json={'expected_revision': 1, 'text': marker}).json()
        assert client.get('/api/v1/conversations').json()['items'] == []
        assert client.get(route + '/draft').json()['text'] == marker
        assert client.delete(route, params={'expected_revision': draft['conversation_revision']}).status_code == 200
        exported = json.dumps(export_records(app.state.services))
        assert marker not in exported and identifier not in exported
    for path in profile.rglob('*'):
        if path.is_file():
            assert marker.encode() not in path.read_bytes() and identifier.encode() not in path.read_bytes()


def test_message_pages_pin_snapshot_and_reject_cross_chat_cursor(tmp_path):
    app = app_at(tmp_path / 'paged-chat')
    with TestClient(app) as client:
        chat = client.post('/api/v1/conversations', json={}).json()
        other = client.post('/api/v1/conversations', json={}).json()
        identifier = chat['identity']['id']
        db = app.state.services.db
        # Deliberate timestamp ties exercise keyset ordering at the public page seam.
        with db.transaction() as conn:
            conn.execute("INSERT INTO learn_runs VALUES('page-run',?,'page-key','completed',NULL,?,?)",
                         (identifier, chat['created_at'], chat['created_at']))
            for i in range(5):
                conn.execute('INSERT INTO learn_messages VALUES(?,?,?,?,?,?,?)',
                    (f'message-{i}', identifier, 'page-run', 'user', f'Fictional message {i}', '[]', chat['created_at']))
        path = f'/api/v1/conversations/learning/{identifier}/messages'
        first = client.get(path, params={'limit': 2}).json()
        db.execute('INSERT INTO learn_messages VALUES(?,?,?,?,?,?,?)',
            ('message-later', identifier, 'page-run', 'user', 'Later addition', '[]', '2099-01-01T00:00:00+00:00'))
        seen = [x['id'] for x in first['items']]
        cursor = first['next_cursor']
        invalid = client.get(f"/api/v1/conversations/learning/{other['identity']['id']}/messages", params={'cursor': cursor})
        assert invalid.status_code == 422
        while cursor:
            page = client.get(path, params={'limit': 2, 'cursor': cursor}).json()
            seen.extend(x['id'] for x in page['items'])
            cursor = page['next_cursor']
        assert seen == [f'message-{i}' for i in range(5)]
        assert 'message-later' in [x['id'] for x in client.get(path).json()['items']]
