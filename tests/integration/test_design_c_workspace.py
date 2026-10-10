# SPDX-License-Identifier: MIT
"""Workspace persistence/access checks against the assembled API and real rows."""
import json

import pytest
from fastapi.testclient import TestClient

from renulus.server import create_app
from renulus.storage.backup import export_records
from renulus.storage.assessment_policy import advance_policy
from renulus.knowledge.models import own_text_rights


@pytest.mark.parametrize("kind", ["learning", "case"])
def test_saved_tabs_reopen_and_temporary_contexts_never_persist(tmp_path, kind):
    profile = tmp_path / kind
    app = create_app(profile)
    client = TestClient(app)
    chat = client.post("/api/v1/conversations", json={"kind": kind}).json()
    temporary = client.post("/api/v1/conversations", json={"kind": kind, "temporary": True}).json()
    imported = app.state.services.registry["knowledge"].import_text("SYNTHETIC dialysis source", process=False)
    tab = {"context": chat["identity"], "retention": "saved", "position": None,
        "content": {"target": {"type": "library_revision", "id": imported["revision_id"]}}}
    saved = client.put("/api/v1/workspace/preferences", json={"width": 540, "tabs": [tab]})
    assert saved.status_code == 200, saved.text
    bad = {**tab, "context": temporary["identity"]}
    assert client.put("/api/v1/workspace/preferences", json={"width": 540, "tabs": [bad]}).status_code == 409
    assert temporary["identity"]["id"] not in app.state.services.db.fetch_one(
        "SELECT value FROM preferences WHERE key='design_c.workspace'")["value"]
    reopened = TestClient(create_app(profile)).get("/api/v1/workspace/preferences").json()
    assert reopened == saved.json()
    assert "design_c.workspace" not in {row["key"] for row in export_records(app.state.services)["records"]["preferences"]}


def test_display_is_separate_from_extraction_and_late_policy(tmp_path):
    app = create_app(tmp_path / "access")
    services = app.state.services
    client = TestClient(app)
    imported = services.registry["knowledge"].import_text("SYNTHETIC transplant passage", process=False)
    request = {"kind": "content", "context": None, "policy": client.get("/api/v1/assessment/policy").json(),
        "reference": {"target": {"type": "library_revision", "id": imported["revision_id"]}}}
    services.db.execute("UPDATE knowledge_revisions SET status='failed' WHERE id=?", (imported["revision_id"],))
    assert client.post("/api/v1/workspace/authorize", json=request).json() == {"allowed": True}
    services.db.execute("UPDATE knowledge_revisions SET rights_json=? WHERE id=?", ('{"display":false}', imported["revision_id"]))
    assert client.post("/api/v1/workspace/authorize", json=request).json() == {"allowed": False, "reason": "access_denied"}
    with services.db.transaction() as conn:
        advance_policy(conn)
    response = client.post("/api/v1/workspace/authorize", json=request)
    assert response.status_code == 409 and response.json()["error"]["code"] == "assistance_changed"


def test_removed_content_keeps_known_tab_but_deleted_chat_does_not_reopen(tmp_path):
    app = create_app(tmp_path / "deleted")
    client = TestClient(app)
    services = app.state.services
    chat = client.post("/api/v1/conversations", json={}).json()
    imported = services.registry["knowledge"].import_text("SYNTHETIC electrolyte note", process=False)
    tab = {"context": chat["identity"], "content": {"target": {"type": "library_revision", "id": imported["revision_id"]}}}
    assert client.put("/api/v1/workspace/preferences", json={"tabs": [tab]}).status_code == 200
    services.db.execute("UPDATE knowledge_documents SET deleted_at='now' WHERE id=?", (imported["document_id"],))
    assert client.put("/api/v1/workspace/preferences", json={"tabs": [tab], "width": 560}).status_code == 200
    request = {"kind": "content", "context": {"identity": chat["identity"], "retention": "saved"},
        "policy": client.get("/api/v1/assessment/policy").json(), "reference": tab["content"]}
    assert client.post("/api/v1/workspace/authorize", json=request).json() == {"allowed": False, "reason": "not_found"}
    services.db.mark_deleted("learn_thread", chat["identity"]["id"])
    assert client.get("/api/v1/workspace/preferences").json()["tabs"] == []


def test_project_entries_use_exact_linked_revision_and_omit_paths(tmp_path):
    app = create_app(tmp_path / "project")
    services = app.state.services
    client = TestClient(app)
    project = client.post("/api/v1/study/projects", json={"title": "Synthetic glomerular study"}).json()
    imported = services.registry["knowledge"].import_text("SYNTHETIC project source", process=False)
    services.db.execute("INSERT INTO study_project_documents(id,project_id,revision_id,created_at) VALUES('link',?,?,'now')",
        (project["id"], imported["revision_id"]))
    services.db.execute("UPDATE knowledge_documents SET latest_revision=NULL WHERE id=?", (imported["document_id"],))
    result = client.get("/api/v1/workspace/entries", params={"context_type": "project", "context_id": project["id"]}).json()
    assert len(result["items"]) == 1 and result["items"][0]["reference"]["target"]["id"] == imported["revision_id"]
    assert "original_path" not in json.dumps(result)
    assert client.put("/api/v1/workspace/preferences", json={"tabs": [], "secret": "not accepted"}).status_code == 422


@pytest.mark.parametrize('kind', ['learning', 'case'])
def test_files_lists_only_current_authorized_saved_chat_attachments(tmp_path, kind):
    app = create_app(tmp_path / ('workspace-files-' + kind)); client = TestClient(app)
    services = app.state.services
    chat = client.post('/api/v1/conversations', json={'kind': kind}).json()
    other = client.post('/api/v1/conversations', json={'kind': kind}).json()
    temporary = client.post('/api/v1/conversations', json={'kind': kind, 'temporary': True}).json()
    attached = []
    for index, target in enumerate((chat, other, temporary)):
        pins = client.get('/api/v1/attachments/' + kind + '/' + target['identity']['id']).json()
        request = {'conversation': target['identity'], 'expected_conversation_revision': pins['conversation_revision'],
            'expected_policy_revision': pins['policy_revision'], 'expected_context_epoch': pins['context_epoch'],
            'idempotency_key': 'workspace-file-' + str(index), 'filename': 'synthetic.md',
            'title': 'Synthetic saved file ' + str(index), 'rights': own_text_rights().model_dump(), 'metadata': {}}
        response = client.post('/api/v1/attachments', content=b'# Synthetic study source', headers={'x-renulus-attachment-options': json.dumps(request)})
        assert response.status_code == 201, response.text
        attached.append(response.json())
    query = {'section': 'Files', 'context_type': chat['identity']['type'], 'context_id': chat['identity']['id']}
    response = client.get('/api/v1/workspace/entries', params=query)
    assert response.status_code == 200, response.text
    items = response.json()['items']
    assert [item['reference']['target']['id'] for item in items] == [attached[0]['id']]
    assert 'original_path' not in response.text and 'source_id' not in response.text
    opened = client.post('/api/v1/readers/resolve', json={'reference': items[0]['reference'], 'conversation': chat['identity']})
    assert opened.status_code == 200, opened.text
    assert not client.get('/api/v1/workspace/entries', params={'section': 'Files'}).json()['items']
    assert not client.get('/api/v1/workspace/entries', params={**query, 'section': 'Notes'}).json()['items']
    assert client.get('/api/v1/workspace/entries', params={**query, 'context_id': temporary['identity']['id']}).status_code == 404
    services.db.execute("UPDATE knowledge_attachment_metadata SET rights_json=json_set(rights_json,'$.display',json('false')) WHERE attachment_id=?", (attached[0]['id'],))
    assert client.get('/api/v1/workspace/entries', params=query).json()['items'] == []
    services.db.execute("UPDATE knowledge_attachment_metadata SET rights_json=json_set(rights_json,'$.display',json('true')) WHERE attachment_id=?", (attached[0]['id'],))
    services.db.mark_deleted('attachment', attached[0]['id'])
    assert client.get('/api/v1/workspace/entries', params=query).json()['items'] == []
