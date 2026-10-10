# SPDX-License-Identifier: MIT
import json

from fastapi.testclient import TestClient
from renulus.server import create_app
from renulus.storage.invalidation import bump_context_epoch
from renulus.storage.assessment_policy import advance_policy


def test_search_saved_content_archive_paging_and_scope(tmp_path):
    app = create_app(tmp_path / "search")
    client, services = TestClient(app), app.state.services
    chats = [client.post("/api/v1/conversations", json={"title": "Synthetic dialysis " + str(i)}).json() for i in range(3)]
    temporary = client.post("/api/v1/conversations", json={"title": "Temporary dialysis sentinel", "temporary": True}).json()
    project = client.post("/api/v1/study/projects", json={"title": "Synthetic dialysis project"}).json()
    identity = chats[0]["identity"]["id"]
    services.db.execute("INSERT INTO learn_messages VALUES('synthetic-message',?,'run','user','transplant content sentinel','[]','now')", (identity,))
    scoped = client.put(f"/api/v1/conversations/learning/{identity}/project", json={"expected_revision": 1, "project_id": project["id"]})
    assert scoped.status_code == 200
    page = client.get("/api/v1/search", params={"q": "dialysis", "limit": 1}).json()
    seen = []
    while True:
        seen.extend(x["key"] for x in page["items"])
        if not page["next_cursor"]:
            break
        page = client.get("/api/v1/search", params={"q": "dialysis", "limit": 1, "cursor": page["next_cursor"]}).json()
    assert len(seen) == len(set(seen)) == 4
    assert temporary["identity"]["id"] not in json.dumps(seen)
    content = client.get("/api/v1/search", params={"q": "transplant"}).json()["items"]
    assert len(content) == 1 and content[0]["identity"] == chats[0]["identity"]
    assert content[0]["project_id"] == project["id"]
    services.db.execute("UPDATE learn_conversations SET lifecycle='archived' WHERE thread_id=?", (identity,))
    assert client.get("/api/v1/search", params={"q": "transplant"}).json()["items"] == []
    assert client.get("/api/v1/search", params={"q": "transplant", "archived": True}).json()["items"][0]["lifecycle"] == "archived"
    items = client.get("/api/v1/search", params={"q": "dialysis", "project_id": project["id"], "archived": True}).json()["items"]
    assert len(items) == 2


def test_search_library_readiness_location_rights_and_context_invalidation(tmp_path):
    app = create_app(tmp_path / "files")
    services, client = app.state.services, TestClient(app)
    knowledge = services.registry["knowledge"]
    imported = knowledge.import_text("Synthetic CKD text", title="Dialysis note", process=False)
    services.db.execute("UPDATE knowledge_documents SET active_revision=? WHERE id=?", (imported["revision_id"], imported["document_id"]))
    services.db.execute("UPDATE knowledge_revisions SET status='ready' WHERE id=?", (imported["revision_id"],))
    services.db.execute("INSERT INTO knowledge_passages VALUES('passage',?,0,'transplant sentinel','context',?, '[]')",
        (imported["revision_id"], '[{"page":2}]'))
    found = client.get("/api/v1/search", params={"q": "transplant"}).json()["items"]
    assert found[0]["reference"]["target"]["id"] == imported["revision_id"]
    assert found[0]["reference"]["locator"] == {"kind": "pdf", "physical_page": 2}
    services.db.execute("UPDATE knowledge_revisions SET status='failed' WHERE id=?", (imported["revision_id"],))
    assert client.get("/api/v1/search", params={"q": "transplant"}).json()["items"] == []
    assert client.get("/api/v1/search", params={"q": "dialysis"}).json()["items"][0]["status"] == "failed"
    services.db.execute("UPDATE knowledge_revisions SET rights_json='{}' WHERE id=?", (imported["revision_id"],))
    assert client.get("/api/v1/search", params={"q": "dialysis"}).json()["items"] == []
    for i in range(2):
        client.post("/api/v1/conversations", json={"title": "CKD " + str(i)})
    cursor = client.get("/api/v1/search", params={"q": "CKD", "limit": 1}).json()["next_cursor"]
    assert cursor
    assert client.get("/api/v1/search", params={"q": "other", "cursor": cursor}).status_code == 409
    with services.db.transaction() as conn:
        bump_context_epoch(conn)
    assert client.get("/api/v1/search", params={"q": "CKD", "cursor": cursor}).status_code == 409
    with services.db.transaction() as conn:
        conn.execute("INSERT INTO assessment_test_attempts(id,version_id,version_snapshot_json,mode,clock_high_water_at,created_at,updated_at) VALUES('test','version','{}','test','now','now','now')")
        advance_policy(conn)
    denied = client.get("/api/v1/search", params={"q": "CKD"})
    assert denied.status_code == 409 and "snippet" not in denied.text
