"""Cross-module proofs: guarded context reaches Learn without implicit retention."""
import json

from fastapi.testclient import TestClient
import pytest

from renulus.cases.models import EditCase, HandoffCase, StartCase
from renulus.contracts import Scope
from renulus.server import create_app
from renulus.storage.backup import export_records


SENTINEL = "SYNTHETIC_HANDOFF_CASE_48470"


class Provider:
    def __init__(self, before_finish=None):
        self.before_finish = before_finish
        self.messages = []

    async def stream(self, messages, **options):
        self.messages = messages
        assert options["scope"].kind == Scope.TEMPORARY_CASE
        yield "Synthetic explanation of " + SENTINEL
        if self.before_finish:
            self.before_finish()

    async def cancel(self, run_id):
        return True


def fixture(tmp_path):
    app = create_app(tmp_path)
    cases = app.state.services.registry["cases"]
    case = cases.start(StartCase(text=SENTINEL, title="Synthetic case"))
    ticket = cases.handoff(case["id"], HandoffCase(revision=case["revision"], target="explain", question="Explain the mechanism"))
    body = {"question": ticket["question"], "scope": ticket["scope"], "case_handoff_id": ticket["id"]}
    return app, cases, case, body


def stream_events(response):
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]


def test_case_explanation_returns_to_live_session_and_saves_only_explicitly(tmp_path):
    app, cases, case, body = fixture(tmp_path)
    provider = Provider()
    app.state.services.registry["provider"] = provider
    with TestClient(app) as client:
        flow = stream_events(client.post("/api/v1/learn/ask", json=body))
        assert flow[-1]["type"] == "completed"
        assert SENTINEL in str(provider.messages)
        current = cases.get(case["id"])
        assert current["messages"][-1]["content"].endswith(SENTINEL)
        assert current["revision"] > case["revision"]
        assert cases.list_saved() == []
        assert client.get("/api/v1/learn/threads").json()["threads"] == []
        assert SENTINEL not in str(export_records(app.state.services))
        for path in tmp_path.rglob("*"):
            if path.is_file():
                assert SENTINEL.encode() not in path.read_bytes()
        saved = client.post(f"/api/v1/cases/sessions/{case['id']}/save", json={"revision": current["revision"]})
        assert saved.status_code == 200
    restarted = create_app(tmp_path).state.services
    assert restarted.registry["cases"].get(case["id"])["messages"][-1]["content"].endswith(SENTINEL)


@pytest.mark.parametrize("action", ["edit", "delete"])
def test_case_change_during_generation_rejects_late_completion(tmp_path, action):
    app, cases, case, body = fixture(tmp_path)
    def change():
        if action == "edit":
            cases.edit(case["id"], EditCase(revision=case["revision"], text="Replacement synthetic case"))
        else:
            cases.delete(case["id"])
    app.state.services.registry["provider"] = Provider(change)
    with TestClient(app) as client:
        flow = stream_events(client.post("/api/v1/learn/ask", json=body))
        assert flow[-1]["type"] == "cancelled"
        assert client.get("/api/v1/learn/threads").json()["threads"] == []
        assert SENTINEL not in str(export_records(app.state.services))
        if action == "edit":
            assert cases.get(case["id"])["messages"] == []


def test_forged_persistent_scope_cannot_promote_a_case_handoff(tmp_path):
    app, cases, case, body = fixture(tmp_path)
    app.state.services.registry["provider"] = Provider()
    with TestClient(app) as client:
        result = client.post("/api/v1/learn/ask", json={**body, "scope": {"kind": "study"}})
        assert result.status_code == 409
        assert client.get("/api/v1/learn/threads").json()["threads"] == []
        changed = client.post("/api/v1/learn/ask", json={**body, "question": "Different question"})
        assert changed.status_code == 409
        assert cases.get(case["id"])["messages"] == []
