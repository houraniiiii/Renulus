# SPDX-License-Identifier: MIT
"""Server disclosure boundary across legacy, replay, readers and recovery."""
from fastapi.testclient import TestClient

from renulus.server import create_app
from renulus.assessment.attempt_models import StartAttempt
from renulus.design_c_contracts import QuestionSnapshot, SavedTestVersion
from renulus.storage import utc_now


def start_test(services):
    version = SavedTestVersion(id='policy_version', test_id='policy_test', ordinal=1, origin='imported',
        review_quality='personal', status='ready', provenance={'method':'import'}, created_at=utc_now(),
        terms='Synthetic owned educational fixture',
        items=[QuestionSnapshot(item_id='policy_item', question_id='policy_question', question_version='1',
            key_version='1', family_id='policy_family', family_version='1', topic_id='general',
            stem='Which synthetic learning statement is correct?', options=[{'id':'a','text':'First option'},
            {'id':'b','text':'Second option'}], correct_option_ids=['a'], explanation='Synthetic explanation')])
    with services.db.transaction() as conn:
        services.get('saved_tests').publish_version(conn, version, title='Synthetic policy practice',
            provenance={'schema':'saved-test-provenance/1'}, idempotency_key='policy-version-create')
    return services.get('whole_attempts').start(StartAttempt(version={'type':'saved_test_version','id':version.id},
        mode='test', timing={'kind':'untimed'}), 'policy-start-test')


def test_active_test_blocks_all_legacy_help_and_recovery_disclosures(tmp_path):
    app = create_app(tmp_path / "policy")
    client = TestClient(app)
    assert client.get("/api/v1/assessment/policy").json()["assistance_allowed"] is True
    start_test(app.state.services)
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
        start_test(app.state.services)
        return {"explanation": "SYNTHETIC_PRIVATE_KEY_SENTINEL"}
    response = TestClient(app).get("/api/v1/synthetic-late-help")
    assert response.status_code == 409
    assert "SYNTHETIC_PRIVATE_KEY_SENTINEL" not in response.text


def test_active_test_permits_typed_chat_cancellation_but_no_run_disclosure(tmp_path):
    app = create_app(tmp_path / "cancel")
    start_test(app.state.services)
    client = TestClient(app)
    response = client.post("/api/v1/conversations/learning/synthetic_chat/runs/synthetic_run/cancel")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "conversation_run_missing"
    assert client.get("/api/v1/conversations/learning/synthetic_chat/runs").json() == {"items": [], "next_cursor": None}
    assert client.get("/api/v1/conversations/learning/synthetic_chat/runs/synthetic_run?neutral=true").status_code == 404
    for path in ("/api/v1/conversations/learning/synthetic_chat/runs/synthetic_run",
                 "/api/v1/conversations/learning/synthetic_chat/runs/synthetic_run?neutral=false",
                 "/api/v1/conversations/learning/synthetic_chat/runs/synthetic_run?neutral=true&neutral=false",
                 "/api/v1/conversations/learning/synthetic_chat/messages"):
        assert client.get(path).json()["error"]["code"] == "assistance_restricted"
    assert client.post("/api/v1/conversations/other/chat/runs/run/cancel").status_code == 409


def test_active_test_neutral_receipts_and_nightly_off_keep_exact_safe_shapes(tmp_path):
    import json
    from renulus.learn.conversation_models import NewConversation
    app = create_app(tmp_path / "neutral")
    services, client = app.state.services, TestClient(app)
    conversation = services.get("conversations").create(NewConversation(title="SYNTHETIC private title"))
    identifier = conversation["identity"]["id"]
    receipt = {"run_id": "synthetic_run", "state": "failed", "conversation": conversation,
               "error": {"message": "SYNTHETIC private error"}}
    services.db.execute("INSERT INTO conversation_commands VALUES(?,?,?,?,?,?,?)",
        ("synthetic_command", "send", "learn_thread", identifier, "synthetic", json.dumps(receipt), "now"))
    root = f"/api/v1/conversations/learning/{identifier}/runs"
    assert client.get(root + "/synthetic_run?neutral=true").json() == {"run_id": "synthetic_run", "state": "failed"}
    assert client.get(root + "/synthetic_run").json()["conversation"]["title"] == conversation["title"]
    start_test(services)
    assert client.get(root).json() == {"items": [{"run_id": "synthetic_run", "state": "failed"}], "next_cursor": None}
    assert client.get(root + "/synthetic_run?neutral=true").json() == {"run_id": "synthetic_run", "state": "failed"}
    assert client.get(root + "/synthetic_run").status_code == 409
    preferences = client.get("/api/v1/nightly/preferences").json()
    assert set(preferences) == {"enabled", "local_time", "question_count", "revision"}
    response = client.put("/api/v1/nightly/preferences", headers={"Idempotency-Key": "synthetic-disable"},
        json={**{key: preferences[key] for key in ("local_time", "question_count")}, "enabled": False,
              "expected_revision": preferences["revision"]})
    assert response.status_code == 200
    assert response.json()["enabled"] is False
    assert set(response.json()) == set(preferences)


def test_volatile_test_stop_and_status_are_neutral_during_real_test(tmp_path):
    app = create_app(tmp_path / 'volatile-neutral')
    start_test(app.state.services)
    client = TestClient(app)
    root = '/api/v1/conversations/test-drafts/runs/synthetic_run'
    for method, path in ((client.get, root), (client.post, root + '/cancel')):
        response = method(path)
        assert response.status_code == 404
        assert response.json()['error']['code'] == 'chat_test_run_missing'
    assert client.get(root + '/result').json()['error']['code'] == 'assistance_restricted'
    assert client.post('/api/v1/conversations/test-drafts', json={}).json()['error']['code'] == 'assistance_restricted'
