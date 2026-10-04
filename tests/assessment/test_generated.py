"""Original token exercises through the exact approved Provider consumer seam."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import os
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from renulus.assessment.contracts import AnswerRequest
from renulus.assessment.generated_contracts import GenerateRequest
from renulus.assessment.generated_streaming import generate
from renulus.contracts import ApiError, ContextScope, Scope
from renulus.server import create_app

BASE = "/api/v1/assessment/practice"
SENTINEL = "ORIGINAL_GENERATED_KEY_NOT_REVIEWED"


def output(count=1, source_indices=None):
    return {"items": [{"stem": "Original token exercise " + str(index),
            "options": [{"id": "a", "text": "Marked token", "rationale": "Original marked token"},
                        {"id": "b", "text": "Unmarked token", "rationale": "Original distractor"}],
            "correct_option_id": "a", "explanation": SENTINEL, "hint": "Inspect the token marker",
            "source_indices": source_indices or []} for index in range(count)]}


class SyntheticProvider:
    def __init__(self, data=None, error=None, callback=None):
        self.data = data if data is not None else output()
        self.error, self.callback, self.calls, self.cancelled = error, callback, [], []

    def status(self):
        return {"test_adapter": True, "live_provider_verified": False}

    async def stream(self, messages, *, scope, run_id, model=None, system=None, purpose="explain"):
        self.calls.append({"messages": deepcopy(messages), "scope": scope, "run_id": run_id,
                           "model": model, "system": system, "purpose": purpose})
        if self.error:
            raise self.error
        text = json.dumps(self.data) if isinstance(self.data, dict) else self.data
        yield text[:30]
        if self.callback:
            self.callback()
        yield text[30:]

    async def cancel(self, run_id):
        self.cancelled.append(run_id)
        return True


class SyntheticKnowledge:
    def __init__(self):
        self.calls, self.revision, self.fail = [], "fixture-r1", False

    def retrieve(self, query, topic_id=None, scope=None):
        self.calls.append({"query": query, "topic_id": topic_id, "scope": scope})
        if self.fail:
            raise RuntimeError("PRIVATE_RETRIEVAL_SENTINEL")
        return {"passages": [{"id": "fixture-p1", "document_revision": self.revision,
                "source_id": "original-test-source", "text": "Original fixture marks token a",
                "title": "Original token source", "locators": [{"page": 2}],
                "rights": {"model_input": True, "cache": True, "display": True}, "metadata": {"edition": "Test 1"}}]}


def events(response):
    assert response.status_code == 200, response.text
    result = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
    assert [event["sequence"] for event in result] == list(range(1, len(result) + 1))
    assert len({event["run_id"] for event in result}) == 1
    assert sum(event["type"] in ("completed", "error", "cancelled") for event in result) == 1
    assert result[-1]["type"] in ("completed", "error", "cancelled")
    return result


def generate_one(client, **overrides):
    request = {"idempotency_key": "generate-original", "prompt": "Original fixture tokens",
               "count": 1, "context": "study", **overrides}
    result = events(client.post(BASE + "/generate", json=request))
    return result, request


def answer_request(session, key="original-generated-answer", option="a"):
    return {"idempotency_key": key, "item_id": session["current_item"]["id"], "option_ids": [option]}


def test_approved_seam_separate_scoring_assistance_restart_and_idempotent_generation(app, tmp_path):
    provider, knowledge = SyntheticProvider(output(source_indices=[0])), SyntheticKnowledge()
    app.state.services.registry.update(provider=provider, knowledge=knowledge)
    with TestClient(app) as client:
        result, request = generate_one(client, topic_id="dialysis")
        session = result[-1]["payload"]["session"]
        assert session["retention"] == "persistent"
        assert SENTINEL not in json.dumps(result)
        assert "correct_option_id" not in json.dumps(result)
        call = provider.calls[0]
        assert call["scope"].kind == Scope.GENERATED_PRACTICE
        assert call["purpose"] == "generated-practice" and call["model"] is None
        assert "PRIVATE_REVIEWED_KEY" not in json.dumps(call["messages"])
        assert len(knowledge.calls) == 2
        identifier = session["id"]
        assert client.get(BASE + f"/sessions/{identifier}/review").json()["feedback"] == []
        help_result = client.post(BASE + f"/sessions/{identifier}/help", json={
            "idempotency_key": "generated-help", "item_id": session["current_item"]["id"], "kind": "sources"}).json()
        assert help_result["assisted"] is True and help_result["sources"][0]["locator"] == "page 2"
        answer = answer_request(session)
        committed = client.post(BASE + f"/sessions/{identifier}/answer", json=answer)
        assert committed.status_code == 200, committed.text
        assert committed.json()["feedback"]["verification"] == "generated-unreviewed"
        assert committed.json()["feedback"]["explanation"] == SENTINEL
        assert committed.json()["session"]["scores"]["assisted"]["answered"] == 1
        assert app.state.services.db.fetch_all("SELECT * FROM learning_evidence") == []
        assert app.state.services.db.fetch_all("SELECT * FROM assessment_attempts") == []
        assert events(client.post(BASE + "/generate", json=request)) == result
        assert len(provider.calls) == 1
    restarted = create_app(tmp_path / "profile")
    with TestClient(restarted) as client:
        replay = client.post(BASE + f"/sessions/{identifier}/answer", json=answer)
        assert replay.json() == committed.json()
        generation_replay = events(client.post(BASE + "/generate", json=request))
        assert generation_replay[-1]["payload"]["session"]["id"] == identifier
        assert len(restarted.state.services.db.fetch_all("SELECT * FROM assessment_generated_attempts")) == 1
        assert client.post(BASE + f"/sessions/{identifier}/pause", json={"idempotency_key": "practice-pause"}).json()["status"] == "paused"
        assert client.post(BASE + f"/sessions/{identifier}/resume", json={"idempotency_key": "practice-resume"}).json()["status"] == "active"
        assert len(client.get(BASE + f"/sessions/{identifier}/review").json()["feedback"]) == 1


@pytest.mark.parametrize("context", ["temporary", "unclassified"])
def test_temporary_or_unclassified_generated_answers_write_nothing(app, context, tmp_path):
    provider, knowledge = SyntheticProvider(), SyntheticKnowledge()
    app.state.services.registry.update(provider=provider, knowledge=knowledge)
    with TestClient(app) as client:
        result, request = generate_one(client, context=context, prompt="PRIVATE_TEMPORARY_ORIGINAL_SENTINEL")
        session = result[-1]["payload"]["session"]
        assert session["retention"] == "volatile"
        assert knowledge.calls == []
        assert provider.calls[0]["scope"].kind in (Scope.TEMPORARY_CASE, Scope.UNCLASSIFIED)
        response = client.post(BASE + f"/sessions/{session['id']}/answer", json=answer_request(session))
        assert response.status_code == 200
        assert response.json()["feedback"]["correct"] is True
        assert client.get(BASE + "/sessions").json() == {"sessions": []}
        for table in ("assessment_generated_sessions", "assessment_generated_attempts", "assessment_generated_items",
                      "assessment_generated_commands", "learning_evidence"):
            assert app.state.services.db.fetch_all("SELECT * FROM " + table) == []
    with TestClient(create_app(tmp_path / "profile")) as restarted:
        assert restarted.get(BASE + f"/sessions/{session['id']}").status_code == 404


@pytest.mark.parametrize("bad", ["not json", {"items": []}, output(source_indices=[4]),
    {"items": [{**output()["items"][0], "correct_option_id": "missing"}]}, output(2)])
def test_invalid_generation_has_one_sanitized_terminal_and_no_records(app, bad):
    app.state.services.registry["provider"] = SyntheticProvider(bad)
    with TestClient(app) as client:
        result, _ = generate_one(client)
        assert result[-1]["type"] == "error"
        assert result[-1]["payload"]["code"] == "practice_invalid_output"
        assert app.state.services.db.fetch_all("SELECT * FROM assessment_generated_sessions") == []
        assert app.state.services.db.fetch_all("SELECT * FROM learning_evidence") == []


def test_provider_failure_and_missing_adapter_are_real_sanitized_errors(app):
    with TestClient(app) as client:
        assert client.get(BASE + "/capabilities").json()["available"] is False
        result, _ = generate_one(client)
        assert result[-1]["payload"]["code"] == "capability_unavailable"
        provider = SyntheticProvider(error=RuntimeError("SECRET_PROVIDER_PROMPT_SENTINEL"))
        app.state.services.registry["provider"] = provider
        result, _ = generate_one(client, idempotency_key="failed-provider-original")
        assert "SECRET_PROVIDER_PROMPT_SENTINEL" not in json.dumps(result)
        assert result[-1]["payload"]["code"] == "practice_generation_failed"
        client.post(BASE + "/runs/learn_other_owned_run/cancel")
        assert "learn_other_owned_run" not in provider.cancelled


def test_source_revision_change_aborts_generated_publish(app):
    knowledge = SyntheticKnowledge()
    provider = SyntheticProvider(output(source_indices=[0]), callback=lambda: setattr(knowledge, "revision", "fixture-r2"))
    app.state.services.registry.update(provider=provider, knowledge=knowledge)
    with TestClient(app) as client:
        result, _ = generate_one(client)
        assert result[-1]["payload"]["code"] == "practice_sources_changed"
        assert app.state.services.db.fetch_all("SELECT * FROM assessment_generated_sessions") == []


def test_concurrent_answer_and_storage_failure_preserve_one_atomic_generated_attempt(app):
    app.state.services.registry["provider"] = SyntheticProvider()
    with TestClient(app) as client:
        result, _ = generate_one(client)
        session = result[-1]["payload"]["session"]
        identifier = session["id"]
        db = app.state.services.db
        db.execute("CREATE TRIGGER fail_generated BEFORE INSERT ON assessment_generated_commands BEGIN SELECT RAISE(ABORT, 'private failure'); END")
        request = answer_request(session)
        failed = client.post(BASE + f"/sessions/{identifier}/answer", json=request)
        assert failed.status_code == 503 and "private failure" not in failed.text
        assert db.fetch_all("SELECT * FROM assessment_generated_attempts") == []
        db.execute("DROP TRIGGER fail_generated")
        repository = app.state.services.registry["generated_practice"]
        with ThreadPoolExecutor(max_workers=4) as pool:
            outcomes = list(pool.map(lambda _: repository.answer(identifier, AnswerRequest(**request)), range(4)))
        assert all(value == outcomes[0] for value in outcomes)
        assert len(db.fetch_all("SELECT * FROM assessment_generated_attempts")) == 1
        assert db.fetch_all("SELECT * FROM learning_evidence") == []


class SyntheticCases:
    """Guard contract exercise, separately from actual Cases producer checks."""
    def __init__(self):
        self.scope = ContextScope(kind=Scope.TEMPORARY_CASE, entity_id="case-original")
        self.original_cancel, self.guard_cancel = asyncio.Event(), asyncio.Event()
        self.revision, self.deleted, self.commits = 1, False, []

    def resolve_handoff(self, ticket, target):
        assert target == "generated-practice"
        flag = self.original_cancel if ticket == "case-ticket-original" else self.guard_cancel
        if self.deleted or flag.is_set():
            raise ApiError("case_handoff_expired", "Private original case text never in errors", 409)
        return {"scope": self.scope, "cancel": flag, "revision": self.revision, "case_id": "case-original",
                "messages": [{"role": "user", "content": "ORIGINAL_CASE_VOLATILE_SENTINEL"}]}

    def commit_handoff(self, ticket, target, content, *, cancel, scope):
        self.resolve_handoff(ticket, target)
        assert cancel is self.original_cancel and scope == self.scope
        self.commits.append(content)
        self.original_cancel.set()
        self.revision += 1
        return {"id": "case-original", "revision": self.revision}

    def handoff(self, case_id, request):
        assert case_id == "case-original" and request.revision == self.revision
        return {"case_handoff_id": "case-ticket-guard"}


def test_case_handoff_is_resolved_committed_with_shared_cancel_and_derivatives_stay_volatile(app):
    cases, provider, knowledge = SyntheticCases(), SyntheticProvider(), SyntheticKnowledge()
    app.state.services.registry.update(cases=cases, provider=provider, knowledge=knowledge)
    with TestClient(app) as client:
        result, request = generate_one(client, context="study", case_handoff_id="case-ticket-original")
        session = result[-1]["payload"]["session"]
        assert session["scope"] == cases.scope.model_dump(mode="json")
        assert session["retention"] == "volatile"
        assert knowledge.calls == []
        assert len(cases.commits) == 1 and SENTINEL not in cases.commits[0]
        assert "ORIGINAL_CASE_VOLATILE_SENTINEL" in json.dumps(provider.calls[0]["messages"])
        identifier = session["id"]
        answer = answer_request(session)
        assert client.post(BASE + f"/sessions/{identifier}/answer", json=answer).status_code == 200
        assert app.state.services.db.fetch_all("SELECT * FROM assessment_generated_sessions") == []
        assert app.state.services.db.fetch_all("SELECT * FROM learning_evidence") == []
        cases.deleted = True
        assert client.get(BASE + f"/sessions/{identifier}/review").status_code == 409
        assert client.post(BASE + f"/sessions/{identifier}/answer", json=answer).status_code == 409
        assert client.post(BASE + "/generate", json=request).status_code == 409


def test_case_revision_cancellation_before_completion_does_not_publish(app):
    cases = SyntheticCases()
    provider = SyntheticProvider(callback=cases.original_cancel.set)
    app.state.services.registry.update(cases=cases, provider=provider)
    with TestClient(app) as client:
        result, _ = generate_one(client, case_handoff_id="case-ticket-original")
        assert result[-1]["type"] == "cancelled"
        assert cases.commits == []
        assert app.state.services.registry["generated_practice"].volatile == {}
        assert app.state.services.db.fetch_all("SELECT * FROM assessment_generated_sessions") == []


def test_idle_provider_can_be_cancelled_and_disconnect_records_single_terminal(app):
    class IdleProvider(SyntheticProvider):
        async def stream(self, messages, *, scope, run_id, model=None, system=None, purpose="explain"):
            await asyncio.Event().wait()
            yield "unreachable"
    provider = IdleProvider()
    app.state.services.registry["provider"] = provider
    repository = app.state.services.registry["generated_practice"]
    async def run_check():
        run, replay = repository.prepare(GenerateRequest(idempotency_key="idle-provider-original", prompt="Synthetic idle request"))
        async def collect():
            return [event async for event in generate(repository, run, replay)]
        task = asyncio.create_task(collect())
        await asyncio.sleep(.05)
        repository.cancel(run.id)
        received = await asyncio.wait_for(task, timeout=3)
        assert received[-1].type == "cancelled"
        assert sum(event.type in ("completed", "error", "cancelled") for event in received) == 1
        disconnected, _ = repository.prepare(GenerateRequest(idempotency_key="disconnect-original", prompt="Synthetic disconnect request"))
        iterator = generate(repository, disconnected)
        await anext(iterator)
        await iterator.aclose()
        assert disconnected.events[-1].type == "cancelled"
    asyncio.run(run_check())
    assert app.state.services.db.fetch_all("SELECT * FROM assessment_generated_sessions") == []


def actual_cases(app):
    """Optional explicit producer source, read as code only, with fresh test state."""
    import renulus
    module_root = Path(os.environ.get("RENULUS_CASES_TEST_SOURCE", str(Path(__file__).resolve().parents[2] / "runtime/renulus")))
    if not (module_root / "cases/repository.py").is_file():
        pytest.skip("Actual Cases producer is absent; select its source explicitly")
    if str(module_root) not in renulus.__path__:
        renulus.__path__.append(str(module_root))
    from renulus.cases.repository import CaseRepository
    from renulus.cases.models import EditCase, HandoffCase, StartCase
    app.state.services.db.apply_migration("cases-001", (module_root / "cases/schema.sql").read_text(encoding="utf-8"))
    cases = CaseRepository(app.state.services)
    app.state.services.registry["cases"] = cases
    return cases, StartCase, HandoffCase, EditCase


@pytest.mark.parametrize("saved", [False, True])
def test_actual_cases_producer_commits_temporary_handshake_and_invalidates_answers_on_edit(app, saved):
    cases, StartCase, HandoffCase, EditCase = actual_cases(app)
    case = cases.start(StartCase(text="ORIGINAL_ACTUAL_CASE_SENTINEL"))
    if saved:
        case = cases.save(case["id"], case["revision"])
    ticket = cases.handoff(case["id"], HandoffCase(revision=case["revision"], target="generated-practice", question="Original token practice"))
    original_guard = cases.resolve_handoff(ticket["id"], "generated-practice")
    provider = SyntheticProvider()
    app.state.services.registry["provider"] = provider
    with TestClient(app) as client:
        result, request = generate_one(client, case_handoff_id=ticket["id"], context="study")
        assert result[-1]["type"] == "completed", result
        session = result[-1]["payload"]["session"]
        assert session["retention"] == "volatile"
        assert provider.calls[0]["scope"] == original_guard["scope"]
        assert original_guard["cancel"].is_set()
        identifier = session["id"]
        answer = answer_request(session)
        assert client.post(BASE + f"/sessions/{identifier}/answer", json=answer).status_code == 200
        retained = cases.get(case["id"])
        assert SENTINEL not in json.dumps(retained)
        cases.edit(case["id"], EditCase(revision=retained["revision"], text="Original changed case tokens"))
        assert client.get(BASE + f"/sessions/{identifier}/review").status_code == 409
        assert client.post(BASE + f"/sessions/{identifier}/answer", json=answer).status_code == 409
        for table in ("assessment_generated_sessions", "assessment_generated_items", "assessment_generated_attempts", "learning_evidence"):
            assert app.state.services.db.fetch_all("SELECT * FROM " + table) == []


def test_actual_cases_deletion_while_provider_is_idle_prevents_generated_publish(app):
    cases, StartCase, HandoffCase, _ = actual_cases(app)
    case = cases.start(StartCase(text="ORIGINAL_ACTUAL_CASE_SENTINEL"))
    ticket = cases.handoff(case["id"], HandoffCase(revision=case["revision"], target="generated-practice"))
    app.state.services.registry["provider"] = SyntheticProvider(callback=lambda: cases.delete(case["id"]))
    with TestClient(app) as client:
        result, _ = generate_one(client, case_handoff_id=ticket["id"])
        assert result[-1]["type"] == "cancelled"
        assert app.state.services.registry["generated_practice"].volatile == {}
        assert app.state.services.db.fetch_all("SELECT * FROM assessment_generated_sessions") == []
