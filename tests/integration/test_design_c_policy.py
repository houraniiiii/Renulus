# SPDX-License-Identifier: MIT
"""Server disclosure boundary across legacy, replay, readers and recovery."""
from fastapi.testclient import TestClient

from renulus.server import create_app
from renulus.storage.assessment_policy import advance_policy


def start_test(db):
    with db.transaction() as conn:
        conn.execute("INSERT INTO assessment_test_attempts(id,version_id,version_snapshot_json,mode,clock_high_water_at,created_at,updated_at) VALUES('test','version','{}','test','now','now','now')")
        advance_policy(conn)


def test_active_test_blocks_all_legacy_help_and_recovery_disclosures(tmp_path):
    app = create_app(tmp_path / "policy")
    client = TestClient(app)
    assert client.get("/api/v1/assessment/policy").json()["assistance_allowed"] is True
    start_test(app.state.services.db)
    for path in ("/assessment/aggregates", "/assessment/progress", "/assessment/mistakes",
                 "/assessment/sessions", "/assessment/practice/sessions", "/study",
                 "/memory", "/learn/threads", "/cases/saved", "/knowledge/documents",
                 "/content/topics", "/data/export", "/data/backup?format_version=1",
                 "/data/backup?format_version=2", "/home"):
        response = client.get("/api/v1" + path)
        assert response.status_code == 409, path
        assert response.json()["error"]["code"] == "assistance_restricted"
    for path in ("/data/restore", "/data/backup/restore", "/runtime/runs", "/retrieval/discover"):
        response = client.post("/api/v1" + path, json={})
        assert response.status_code == 409, path
    for path in ("/health", "/assessment/policy", "/connections", "/data/recovery", "/home/preferences"):
        assert client.get("/api/v1" + path).status_code == 200, path


def test_late_read_cannot_publish_help_after_policy_changes(tmp_path):
    app = create_app(tmp_path / "late")
    @app.get("/api/v1/synthetic-late-help")
    def late():
        start_test(app.state.services.db)
        return {"explanation": "SYNTHETIC_PRIVATE_KEY_SENTINEL"}
    response = TestClient(app).get("/api/v1/synthetic-late-help")
    assert response.status_code == 409
    assert "SYNTHETIC_PRIVATE_KEY_SENTINEL" not in response.text
