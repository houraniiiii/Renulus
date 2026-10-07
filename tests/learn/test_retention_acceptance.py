"""Real integrated APIs/SQLite/content; synthetic generation, no helper inference."""
import asyncio
import json
import socket

from fastapi.testclient import TestClient
import pytest

from renulus.contracts import Scope
from renulus.server import create_app
from renulus.storage.backup import export_records


BASE = "SYNTHETIC_EXPLICIT_SAVED_CASE_8231"
DERIVATIVE = "SYNTHETIC_UNSAVED_LEARN_CASE_8232"
NOTE = "SYNTHETIC_CORRECTED_LEARNER_FACT_8233"


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    connect = socket.socket.connect
    def local_only(sock, address):
        if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
            return connect(sock, address)  # Windows asyncio self-pipe only.
        raise AssertionError("Acceptance proofs must not use public sockets")
    monkeypatch.setattr(socket.socket, "connect", local_only)
    monkeypatch.setattr(socket.socket, "connect_ex", lambda *args: (_ for _ in ()).throw(AssertionError("No external sockets")))


class Provider:
    fail = False
    async def stream(self, messages, **options):
        assert options["purpose"] == "explain"
        if options["scope"].kind == Scope.STUDY:
            yield "Synthetic ordinary learning explanation."
        else:
            assert options["scope"].kind == Scope.TEMPORARY_CASE
            assert BASE in str(messages)
            yield DERIVATIVE
            if self.fail:
                raise RuntimeError(DERIVATIVE)
    async def cancel(self, run_id):
        return True


def setup(tmp_path):
    app = create_app(tmp_path / "profile")
    services = app.state.services
    provider = Provider()
    services.registry["provider"] = provider
    # This is a retention proof. Public discovery and helper-backed passage
    # retrieval have their own proofs and are not producers in this fixture.
    services.registry["retrieval"] = services.registry["knowledge"] = None
    return app, services, provider, TestClient(app)  # Deliberately no background lifespan.


def events(response):
    assert response.status_code == 200
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]


def absent(root, marker):
    for path in root.rglob("*"):
        if path.is_file():
            assert marker.encode() not in path.read_bytes(), str(path.relative_to(root))


def test_saved_case_followup_remains_volatile_through_learn_error_success_restart_and_delete(tmp_path):
    app, services, provider, api = setup(tmp_path)
    case = api.post("/api/v1/cases/sessions", json={"text": BASE}).json()
    path = "/api/v1/cases/sessions/" + case["id"]
    saved = api.post(path + "/save", json={"revision": case["revision"]}).json()
    original = services.db.fetch_one("SELECT * FROM case_sessions WHERE id=?", (case["id"],))
    for failed in (True, False):
        provider.fail = failed
        current = api.get(path).json()
        ticket = api.post(path + "/handoff", json={"revision": current["revision"], "target": "explain", "question": "Explain this synthetic case"}).json()
        body = {"question": ticket["question"], "scope": ticket["scope"], "case_handoff_id": ticket["id"]}
        assert body["scope"]["kind"] == "temporary-case"
        denied = api.post("/api/v1/learn/ask", json={**body, "scope": {"kind": "study"}})
        assert denied.status_code == 409
        flow = events(api.post("/api/v1/learn/ask", json=body))
        assert flow[-1]["type"] == ("error" if failed else "completed")
        if failed:
            assert DERIVATIVE not in json.dumps(flow[-1])
        assert services.db.fetch_one("SELECT * FROM case_sessions WHERE id=?", (case["id"],)) == original
        assert api.get("/api/v1/learn/threads").json()["threads"] == []
        assert services.db.fetch_all("SELECT * FROM learning_evidence") == []
        assert asyncio.run(services.get("memory").process_pending())["processed"] == 0
        assert api.get("/api/v1/memory/facts").json()["records"] == []
        assert services.db.fetch_all("SELECT * FROM memory_jobs") == []
        assert DERIVATIVE not in str(export_records(services))
        absent(services.paths.root, DERIVATIVE)
    reopened = create_app(services.paths.root).state.services.get("cases").get(case["id"])
    assert reopened["revision"] == saved["revision"] and reopened["messages"] == []
    current = api.get(path).json()
    assert current["dirty"] and current["messages"][-1]["content"] == DERIVATIVE
    assert api.post(path + "/save", json={"revision": current["revision"]}).status_code == 200
    reopened = create_app(services.paths.root).state.services.get("cases").get(case["id"])
    assert reopened["messages"][-1]["content"] == DERIVATIVE
    assert api.delete(path).json()["purge_pending"] is False
    absent(services.paths.root, BASE)
    absent(services.paths.root, DERIVATIVE)
    api.close()


def test_committed_study_produces_reference_only_idempotent_memory_and_correction_deletion(tmp_path):
    app, services, provider, api = setup(tmp_path)
    body = {"question": "Compare transplantation mechanisms", "scope": {"kind": "study"}, "topic_id": "T21"}
    flow = events(api.post("/api/v1/learn/ask", json=body, headers={"Idempotency-Key": "retention-study"}))
    assert flow[-1]["type"] == "completed"
    thread_id = flow[-1]["payload"]["thread_id"]
    memory = services.get("memory")
    assert asyncio.run(memory.process_pending())["processed"] == 1
    facts = api.get("/api/v1/memory/facts").json()["records"]
    assert len(facts) == 1 and facts[0]["text"] == "I explored T21 in Explain."
    job = services.db.fetch_one("SELECT * FROM memory_jobs WHERE evidence_id LIKE 'learn:%'")
    assert "Compare transplantation" not in str(job)
    assert job["evidence_id"].startswith("learn:")
    # General-answer capture is also durable, but this fixture deliberately has
    # no offline helpers. Its retryable job must retain only a reference.
    answer_job = services.db.fetch_one("SELECT * FROM memory_jobs WHERE evidence_id LIKE 'learn-answer:%'")
    assert answer_job["state"] == "failed"
    assert "Compare transplantation" not in str(answer_job)
    assert "Synthetic ordinary learning explanation" not in str(answer_job)
    replay = events(api.post("/api/v1/learn/ask", json=body, headers={"Idempotency-Key": "retention-study"}))
    assert replay[-1]["payload"]["replayed"]
    assert asyncio.run(memory.process_pending())["processed"] == 0
    assert len(api.get("/api/v1/memory/facts").json()["records"]) == 1
    path = "/api/v1/memory/facts/" + facts[0]["id"]
    edited = api.patch(path, json={"text": NOTE, "expected_revision": facts[0]["revision"]})
    assert edited.status_code == 200 and edited.json()["purge_pending"] is False
    assert api.delete(path + "/history").json()["purge_pending"] is False
    assert api.get(path + "/history").json()["history"] == []
    assert api.delete(path, params={"expected_revision": edited.json()["revision"]}).json()["purge_pending"] is False
    assert asyncio.run(memory.process_pending())["processed"] == 0
    assert api.get("/api/v1/memory/facts").json()["records"] == []
    absent(services.paths.root, NOTE)
    restarted = create_app(services.paths.root).state.services
    assert restarted.get("learn").get_thread(thread_id)["messages"][-1]["role"] == "assistant"
    assert restarted.get("memory").repository.list() == []
    api.close()


def test_staged_cases_reveal_installed_content_across_topics_without_incidental_save(tmp_path):
    app, services, provider, api = setup(tmp_path)
    catalogue = api.get("/api/v1/cases/teaching").json()["cases"]
    selected = {}
    for item in catalogue:
        selected.setdefault(item["topic_id"], item)
    assert len(selected) >= 2
    for item in list(selected.values())[:2]:
        installed = services.get("content").get_case(item["id"])
        session = api.post("/api/v1/cases/sessions", json={"kind": "teaching", "teaching_case_id": item["id"]}).json()
        assert session["teaching"]["version"] == installed["version"]
        assert session["teaching"]["stages"][0]["narrative"] == installed["stages"][0]["narrative"]
        assert session["teaching"]["revealed_count"] == 1
        path = "/api/v1/cases/sessions/" + session["id"]
        revealed = api.post(path + "/reveal", json={"revision": session["revision"]}).json()
        assert revealed["teaching"]["stages"][1]["narrative"] == installed["stages"][1]["narrative"]
        assert api.get("/api/v1/cases/saved").json()["cases"] == []
        assert services.db.fetch_all("SELECT * FROM learning_evidence") == []
        assert api.post(path + "/close", json={"revision": revealed["revision"]}).status_code == 200
    api.close()
