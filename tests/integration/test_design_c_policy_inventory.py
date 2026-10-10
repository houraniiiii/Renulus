# SPDX-License-Identifier: MIT
"""DC14 assembled policy inventory and legacy producer boundary regressions.

Real create_app, installed migrations, saved collection and whole Test authority.
Synthetic output exercises the actual legacy producer; no live model is called.
The client deliberately omits lifespan: background indexing/schedulers are not
under test. Separate owner suites prove their late publication boundaries.

Late-publication inventory reviewed against the actual owner implementations;
existing bounded proofs are reused, not claimed rerun by this module:
* original Learn: service.check_run(conn=...) in answer's write transaction;
  original Case: _current_run before delta/complete, check_run_boundary for
  terminal cache replay (new boundary/HTTP scheduling probes below).
* typed Chat: test_design_c_conversations.test_context_change_during_reply_blocks_late_assistant_publication;
  Study handoffs: test_design_c_study_help.test_commit_rechecks_help_receipt_and_rolls_back_on_same_transaction_change.
* saved generation: test_saved_generation.test_changes_during_provider_wait_prevent_stale_publication;
  imports: test_saved_imports.test_late_normalization_cannot_overwrite_actual_edit.
* Home: test_home_suggestions.test_whole_memory_late_publication_rechecks_correction_source_suppression_and_boundaries;
  Nightly: test_design_c_nightly.test_final_publication_transaction_rechecks_context.
* Memory: test_whole_attempt_evidence (canonical scalar resolution, policy/epoch,
  suppression/source changes, explicit restore capture barriers).
* attachment/extraction/Notes: test_attachment_producer, test_saved_extraction,
  test_design_c_notes.test_mounted_note_publication_rechecks_study_before_actual_import.

Recorded-replay classification (read-only audit): original Learn's completed
request selects canonical learn_runs and rereads learn_messages in the API;
it does not replay an in-memory text cache or restart a provider. Shared HTTP
policy fences that new read. Legacy generated practice has canonical command
receipts on restart, with a newly captured boundary, AND in-process events
bound to their original policy/epoch. Original Cases has only volatile terminal
Run.events, even when the underlying Case was explicitly saved. Its boundary
must remain the original one. Wrapped chat command receipts are canonical for
saved chats and contain completion identity/state; their history is read through
the owner. Temporary wrappers keep volatile command receipts. None of these
replay paths should turn an interrupted provider request into new inference.

Limits: route denial/dispatch and selected valid owner replays, not every success
payload or authentication flow. No installed-renderer, native, credential,
inference-quality, scheduler or media-extraction acceptance is asserted here.
"""
import asyncio
import json
import re

from fastapi.testclient import TestClient
import pytest

from renulus.assessment.attempt_models import StartAttempt, SubmitAttempt
from renulus.assessment.generated_contracts import GenerateRequest, GeneratedBatch
from renulus.assessment.generated_streaming import generate
from renulus.contracts import ApiError
from renulus.design_c_contracts import QuestionSnapshot, SavedTestVersion
from renulus.server import create_app
from renulus.storage.database import utc_now
from renulus.storage.invalidation import invalidate_restored_context

BASE = "/api/v1/assessment/test-attempts"
PRIVATE = "INVENTORY_PRIVATE_KEY"


@pytest.fixture
def assembled(tmp_path, monkeypatch):
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    monkeypatch.setenv("HF_HOME", str(tmp_path / "offline-cache"))
    app = create_app(tmp_path / "profile")
    services = app.state.services
    version = SavedTestVersion(id="inventory_version", test_id="inventory_test", ordinal=1,
        origin="imported", review_quality="personal", status="ready", provenance={"method": "import"},
        created_at=utc_now(), terms="Original synthetic material", items=[QuestionSnapshot(
            item_id="inventory_item", question_id="inventory_question", question_version="1", key_version="1",
            family_id="inventory_family", family_version="1", topic_id="general", stem="Synthetic question?",
            options=[{"id": "a", "text": "First"}, {"id": "b", "text": "Second"}],
            correct_option_ids=["a"], explanation=PRIVATE)])
    with services.db.transaction() as conn:
        services.get("saved_tests").publish_version(conn, version, title="Synthetic inventory",
            provenance={"schema": "saved-test-provenance/1"}, idempotency_key="inventory-publish")
    client = TestClient(app)
    yield app, services, client
    client.close()


def start(services, mode="test", key="inventory-start-test"):
    return services.get("whole_attempts").start(StartAttempt(
        version={"type": "saved_test_version", "id": "inventory_version"}, mode=mode), key)


def boundary(services, kind):
    if kind == "restore":
        with services.db.transaction() as conn:
            invalidate_restored_context(conn)
        return "practice_context_changed"
    attempt = start(services)
    if kind == "cycle":
        services.get("whole_attempts").submit(attempt["id"], SubmitAttempt(
            expected_draft_revision=attempt["draft_revision"]), "inventory-end-test")
        return "assistance_changed"
    return "assistance_restricted"


def request(**overrides):
    return GenerateRequest(**{"idempotency_key": "inventory-legacy-generate", "prompt": "Synthetic learning",
                              "count": 1, "context": "study", **overrides})


def batch():
    return GeneratedBatch.model_validate({"items": [{"stem": "Synthetic token?",
        "options": [{"id": "a", "text": "First"}, {"id": "b", "text": "Second"}],
        "correct_option_id": "a", "explanation": PRIVATE, "source_indices": []}]})


@pytest.mark.parametrize("change", ["active", "cycle", "restore"])
def test_legacy_prepared_before_boundary_cannot_publish(assembled, change):
    _, services, _ = assembled
    repo = services.get("generated_practice")
    run, _ = repo.prepare(request())
    code = boundary(services, change)
    with pytest.raises(ApiError) as error:
        repo.publish(run, batch(), [])
    assert error.value.code == code
    for table in ("assessment_generated_sessions", "assessment_generated_items", "assessment_generated_commands"):
        assert services.db.fetch_all("SELECT * FROM " + table) == []


class OutputTransport:
    """Synthetic text transport through the actual legacy Provider consumer seam."""
    def __init__(self, during=None):
        self.during, self.calls, self.cancelled = during, 0, []

    def status(self):
        return {"test_adapter": True, "live_provider_verified": False}

    async def stream(self, *args, **kwargs):
        self.calls += 1
        if self.during:
            self.during()
        yield batch().model_dump_json()

    async def cancel(self, run_id):
        self.cancelled.append(run_id)


async def collect(repo, run, replay=None):
    return [event async for event in generate(repo, run, replay)]


@pytest.mark.parametrize("change", ["active", "cycle", "restore"])
def test_legacy_publication_rechecks_inside_write_transaction(assembled, monkeypatch, change):
    _, services, _ = assembled
    repo = services.get("generated_practice")
    run, _ = repo.prepare(request())
    guard = repo.guard_run
    expected = []

    def change_after_outer_check(run, conn=None):
        guard(run, conn)
        if conn is None and not expected:
            expected.append(boundary(services, change))

    monkeypatch.setattr(repo, "guard_run", change_after_outer_check)
    with pytest.raises(ApiError) as error:
        repo.publish(run, batch(), [])
    assert error.value.code == expected[0]
    assert services.db.fetch_all("SELECT * FROM assessment_generated_sessions") == []
    assert services.db.fetch_all("SELECT * FROM assessment_generated_commands") == []


@pytest.mark.parametrize("phase", ["prepared", "retrieval_error", "provider_delta"])
@pytest.mark.parametrize("change", ["active", "cycle", "restore"])
def test_legacy_stream_fences_before_provider_and_after_await(assembled, phase, change):
    _, services, _ = assembled
    repo = services.get("generated_practice")
    run, _ = repo.prepare(request())
    codes = []

    def change_boundary():
        codes.append(boundary(services, change))

    class Retrieval:
        def retrieve(self, *args, **kwargs):
            if phase == "retrieval_error":
                change_boundary()
                raise RuntimeError("PRIVATE_RETRIEVAL_FAILURE")
            return {"passages": []}

    transport = OutputTransport(change_boundary if phase == "provider_delta" else None)
    services.registry.update(provider=transport, knowledge=Retrieval())
    if phase == "prepared":
        change_boundary()
    events = asyncio.run(collect(repo, run))
    assert events[-1].type == "error"
    assert events[-1].payload["code"] == codes[0]
    assert transport.calls == int(phase == "provider_delta")
    assert all(e.type not in {"progress", "completed"} for e in events)
    assert PRIVATE not in json.dumps([e.model_dump(mode="json") for e in events])
    assert "PRIVATE_RETRIEVAL_FAILURE" not in str(events)
    assert services.db.fetch_all("SELECT * FROM assessment_generated_sessions") == []


@pytest.mark.parametrize("change", ["active", "cycle", "restore"])
def test_recorded_events_and_prepare_replay_recheck_boundary(assembled, change):
    _, services, _ = assembled
    repo = services.get("generated_practice")
    services.registry["provider"] = OutputTransport()
    services.registry.pop("knowledge", None)
    run, _ = repo.prepare(request())
    assert asyncio.run(collect(repo, run))[-1].type == "completed"

    async def replay_then_change():
        stream = generate(repo, run)
        first = await anext(stream)
        code = boundary(services, change)
        return first, code, [event async for event in stream]

    first, code, rest = asyncio.run(replay_then_change())
    assert first.type == "started"
    assert len(rest) == 1 and rest[0].type == "error" and rest[0].payload["code"] == code
    with pytest.raises(ApiError) as error:
        repo.prepare(request())
    assert error.value.code == code
    assert len(services.db.fetch_all("SELECT * FROM assessment_generated_sessions")) == 1


def test_durable_replay_gates_before_lookup_and_stream_without_inference(assembled):
    from renulus.assessment.generated_repository import GeneratedPracticeRepository
    _, services, _ = assembled
    repo = services.get("generated_practice")
    run, _ = repo.prepare(request())
    result = repo.publish(run, batch(), [])
    # New repository represents restart: the old in-process run is absent.
    restarted = GeneratedPracticeRepository(services)
    replay_run, replay = restarted.prepare(request())
    assert replay == result
    boundary(services, "active")
    with pytest.raises(ApiError) as error:
        restarted.prepare(request(prompt="Changed payload with the old key"))
    assert error.value.code == "assistance_restricted"  # before hash/replay
    events = asyncio.run(collect(restarted, replay_run, replay))
    assert [event.type for event in events] == ["error"]
    assert events[0].payload["code"] == "assistance_restricted"


def test_cancelled_run_remains_neutral_during_test(assembled):
    _, services, _ = assembled
    repo = services.get("generated_practice")
    run, _ = repo.prepare(request())
    boundary(services, "active")
    assert repo.cancel(run.id) == {"run_id": run.id, "cancelled": True}
    assert [e.type for e in asyncio.run(collect(repo, run))] == ["cancelled"]
    replay = asyncio.run(collect(repo, run))
    assert len(replay) == 1 and replay[0].type == "cancelled" and replay[0].payload == {}


@pytest.mark.parametrize("context", ["study", "temporary", "unclassified", "case"])
def test_normal_legacy_generation_and_replay_preserve_retention(assembled, context):
    from renulus.cases.models import StartCase, HandoffCase
    _, services, _ = assembled
    repo = services.get("generated_practice")
    services.registry.update(provider=OutputTransport())
    services.registry.pop("knowledge", None)
    overrides = {"context": context}
    if context == "case":
        cases = services.get("cases")
        case = cases.start(StartCase(text="Original synthetic case"))
        ticket = cases.handoff(case["id"], HandoffCase(revision=case["revision"], target="generated-practice"))
        overrides = {"context": "study", "case_handoff_id": ticket["id"]}
    body = request(**overrides)
    run, _ = repo.prepare(body)
    events = asyncio.run(collect(repo, run))
    assert events[-1].type == "completed", events
    session = events[-1].payload["session"]
    assert session["retention"] == ("persistent" if context == "study" else "volatile")
    assert PRIVATE not in str(events)
    replay_run, replay = repo.prepare(body)
    assert asyncio.run(collect(repo, replay_run, replay)) == events
    assert len(services.db.fetch_all("SELECT * FROM assessment_generated_sessions")) == int(context == "study")


# Explicit route/method exceptions, independent of server.needs_assistance.
# Connection mutations use invalid bodies/providers: no auth, credential write,
# external retrieval or refresh is executed. These probes prove dispatch only.
NEUTRAL = {
    ("GET", "/health"), ("GET", "/meta"), ("GET", "/assessment/policy"),
    ("GET", "/runtime/status"), ("GET", "/data/recovery"),
    ("GET", "/home/preferences"), ("PUT", "/home/preferences"),
    ("GET", "/nightly"), ("GET", "/nightly/preferences"), ("PUT", "/nightly/preferences"),
    ("GET", "/connections"), ("POST", "/connections/opencode-go"),
    ("POST", "/connections/select"), ("POST", "/connections/codex/login"),
    ("GET", "/connections/codex/login/{login_id}"), ("DELETE", "/connections/codex/login/{login_id}"),
    ("POST", "/connections/{provider}/refresh"), ("DELETE", "/connections/{provider}"),
    ("GET", "/retrieval/connections"), ("PUT", "/retrieval/connections/{provider}"),
    ("DELETE", "/retrieval/connections/{provider}"), ("POST", "/retrieval/connections/select"),
    ("DELETE", "/runtime/runs/{run_id}"), ("DELETE", "/data/backup/preview/{preview_token}"),
    ("POST", "/conversations/{kind}/{identifier}/runs/{run_id}/cancel"),
    ("GET", "/conversations/{kind}/{identifier}/runs"),
    ("POST", "/assessment/generation/jobs/{identifier}/cancel"),
    ("POST", "/assessment/imports/{identifier}/cancel"),
    ("POST", "/nightly/jobs/{identifier}/cancel"),
    ("GET", "/conversations/test-drafts/runs/{run_id}"),
    ("POST", "/conversations/test-drafts/runs/{run_id}/cancel"),
}
AUTHENTICATED_NEUTRAL = {("GET", "/runtime/shutdown"), ("POST", "/runtime/shutdown")}
ATTEMPT_OWNED = {("GET", "/assessment/test-attempts"), ("POST", "/assessment/test-attempts"),
    ("GET", "/assessment/test-attempts/{attempt_id}"), ("PUT", "/assessment/test-attempts/{attempt_id}/draft"),
    *(("POST", "/assessment/test-attempts/{attempt_id}/" + action) for action in
      ("present", "help", "submit-answer", "submit", "pause", "resume", "continue-untimed", "reports"))}


def route_inventory(routes, prefix=""):
    """Support FastAPI's nested _IncludedRouter as well as flattened routes."""
    for route in routes:
        nested = getattr(route, "original_router", None)
        if nested is not None:
            yield from route_inventory(nested.routes, prefix + route.include_context.prefix)
        elif getattr(route, "path", None):
            path = prefix + route.path
            if path.startswith("/api/v1/"):
                for method in sorted(getattr(route, "methods", ())):
                    yield method, path.removeprefix("/api/v1"), route.endpoint.__module__


def concrete(path):
    return "/api/v1" + re.sub(r"\{([^}]+)\}", lambda match:
        "learning" if match[1] == "kind" else "inventory_missing", path)


def assert_denied(response, code="assistance_restricted"):
    assert response.status_code == 409, (response.request.method, str(response.request.url), response.text)
    assert response.json()["error"]["code"] == code, response.text
    assert PRIVATE not in response.text


def test_assembled_route_method_inventory_denies_every_non_neutral_entry(assembled, record_property):
    app, services, client = assembled
    entries = sorted(route_inventory(app.routes))
    operations = {(method, path) for method, path, _ in entries}
    assert NEUTRAL | AUTHENTICATED_NEUTRAL | ATTEMPT_OWNED <= operations
    # Cross-check the walk against FastAPI's own schema, including both nested
    # runtime routers. Duplicate policy registration is retained in the receipt.
    schema_operations = {(method.upper(), path.removeprefix("/api/v1"))
        for path, item in app.openapi()["paths"].items() if path.startswith("/api/v1/")
        for method in item if method.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}}
    assert operations == schema_operations
    assert {owner for _, _, owner in entries} >= {
        "renulus.runtime.api", "renulus.content.api", "renulus.knowledge.api", "renulus.assessment.api",
        "renulus.memory.api", "renulus.learn.api", "renulus.cases.api", "renulus.assessment.import_api"}
    active = start(services)
    assert client.get("/api/v1/assessment/policy").json()["active_test_id"] == active["id"]
    denied = sorted(operations - NEUTRAL - AUTHENTICATED_NEUTRAL - ATTEMPT_OWNED)
    record_property("route_inventory", json.dumps(entries))
    record_property("distinct_operations", len(operations))
    record_property("guarded_operations", len(denied))
    record_property("neutral_operations", len(NEUTRAL))
    record_property("authenticated_neutral_operations", len(AUTHENTICATED_NEUTRAL))
    record_property("attempt_owned_operations", len(ATTEMPT_OWNED))
    for method, path in denied:
        # Real mounted routes, malformed/missing bodies: the policy must run
        # before validation, replay, lookup, source reads or export work.
        response = client.request(method, concrete(path), json={})
        assert_denied(response)
        assert response.headers.get("cache-control") == "no-store"
    for method, path in sorted(AUTHENTICATED_NEUTRAL):
        # No session token is configured in this route-inventory fixture.
        # Shutdown remains neutral during Test, but cannot bypass authentication.
        response = client.request(method, concrete(path), json={})
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "invalid_session"
    assert services.shutdown_status() == {"state": "open", "api_version": 1}
    for method, path in sorted(NEUTRAL):
        response = client.request(method, concrete(path), json={"inventory_invalid": True})
        assert response.status_code in {200, 201, 202, 204, 400, 404, 409, 422}, (method, path, response.text)
        if response.content:
            assert response.json().get("error", {}).get("code") not in {"assistance_restricted", "assistance_changed"}, (method, path)
        assert PRIVATE not in response.text


def test_closed_feedback_replay_blocked_current_test_keys_hidden(assembled):
    _, services, client = assembled
    study = start(services, "study", "inventory-start-study")
    body = {"expected_revision": study["draft_revision"], "item_id": "inventory_item", "option_ids": ["a"]}
    headers = {"Idempotency-Key": "inventory-commit-study"}
    committed = client.post(BASE + "/" + study["id"] + "/submit-answer", json=body, headers=headers)
    assert committed.status_code == 200, committed.text
    assert PRIVATE in committed.text  # A real historical disclosure exists.
    ended = client.post(BASE + "/" + study["id"] + "/submit",
        json={"expected_draft_revision": committed.json()["draft_revision"]},
        headers={"Idempotency-Key": "inventory-close-study"})
    assert ended.status_code == 200, ended.text
    closed = start(services, key="inventory-previous-test")
    services.get("whole_attempts").submit(closed["id"], SubmitAttempt(
        expected_draft_revision=closed["draft_revision"]), "inventory-close-previous")
    active = start(services)
    for historical in (study, closed):
        assert_denied(client.get(BASE + "/" + historical["id"]), "attempt_restricted")
    assert_denied(client.post(BASE + "/" + study["id"] + "/submit-answer", json=body, headers=headers), "attempt_restricted")
    assert_denied(client.post(BASE, json={"version": {"type": "saved_test_version", "id": "inventory_version"},
        "mode": "study"}, headers={"Idempotency-Key": "inventory-start-study"}), "attempt_restricted")
    identifier = active["id"]
    url = BASE + "/" + identifier
    responses = [client.get(url), client.post(BASE, json={"version": {"type": "saved_test_version", "id": "inventory_version"},
        "mode": "test"}, headers={"Idempotency-Key": "inventory-start-test"})]
    responses.append(client.put(url + "/draft", json={"expected_revision": active["draft_revision"], "position": 0,
        "answers": [{"item_id": "inventory_item", "option_ids": ["b"], "marked": True}]},
        headers={"Idempotency-Key": "inventory-save-test-draft"}))
    for response in responses:
        assert response.status_code in {200, 201}, response.text
        value = response.json()
        assert value["committed"] == [] and value["result"] is None
        assert "correct_option" not in response.text and PRIVATE not in response.text
        assert "explanation" not in value["current_item"]
    current = responses[-1].json()
    assert_denied(client.post(url + "/help", json={"expected_revision": current["draft_revision"],
        "item_id": "inventory_item", "kind": "hint", "expected_policy_revision": current["policy"]["revision"]},
        headers={"Idempotency-Key": "inventory-test-help"}), "attempt_restricted")
    reported = client.post(url + "/reports", json={"item_id": "inventory_item", "report_text": "Synthetic question report"},
        headers={"Idempotency-Key": "inventory-test-report"})
    assert reported.status_code == 201, reported.text
    assert set(reported.json()) == {"id", "status", "created_at"}
    listed = client.get(BASE).json()
    assert PRIVATE not in str(listed)
    for row in listed["items"]:
        assert set(row) == {"id", "version_id", "mode", "status", "created_at", "finalized_at"}


def test_neutral_run_status_requires_exact_query_and_typed_path(assembled):
    _, services, client = assembled
    start(services)
    for kind in ("learning", "case"):
        url = "/api/v1/conversations/" + kind + "/inventory_missing/runs/inventory_run"
        for suffix in ("", "?neutral=false", "?neutral=True", "?neutral=true&neutral=false"):
            assert_denied(client.get(url + suffix))
        for suffix in ("?neutral=true", "?neutral=false&neutral=true"):
            response = client.get(url + suffix)
            assert response.status_code == 404, response.text
            assert response.json()["error"]["code"] != "assistance_restricted"
    assert_denied(client.get("/api/v1/conversations/other/inventory_missing/runs/inventory_run?neutral=true"))
    assert_denied(client.post("/api/v1/conversations/other/inventory_missing/runs/inventory_run/cancel"))


def test_real_legacy_answer_and_private_import_receipts_do_not_bypass_test(assembled):
    _, services, client = assembled
    repo = services.get("generated_practice")
    run, _ = repo.prepare(request())
    session = repo.publish(run, batch(), [])["session"]
    answer = {"idempotency_key": "inventory-legacy-answer", "item_id": session["current_item"]["id"], "option_ids": ["a"]}
    answer_url = "/api/v1/assessment/practice/sessions/" + session["id"] + "/answer"
    receipt = client.post(answer_url, json=answer)
    assert receipt.status_code == 200 and PRIVATE in receipt.text, receipt.text
    original = {"idempotency_key": "inventory-import-create", "title": "Original private synthetic import",
        "original": {"kind": "paste", "text": "1. Synthetic question?\nA. First\nB. Second\nAnswer: A\nExplanation: " + PRIVATE,
                     "terms": "Original synthetic material", "permission_confirmed": True}}
    imported = client.post("/api/v1/assessment/imports", json=original)
    assert imported.status_code == 201, imported.text
    value = imported.json()
    import_url = "/api/v1/assessment/imports/" + value["id"]
    candidate = value["candidates"][0]
    resolved = client.post(import_url + "/candidates/" + candidate["id"] + "/resolve", json={
        "idempotency_key": "inventory-import-resolve", "expected_revision": value["revision"],
        "correct_option_ids": [candidate["options"][0]["id"]], "review_confirmed": True})
    assert resolved.status_code == 200, resolved.text
    save = {"idempotency_key": "inventory-import-save", "expected_revision": resolved.json()["revision"]}
    published = client.post(import_url + "/save", json=save)
    assert published.status_code == 200, published.text
    start(services)
    for method, url, body in [("POST", answer_url, answer),
        ("POST", "/api/v1/assessment/practice/generate", request().model_dump()),
        ("GET", answer_url.removesuffix("/answer") + "/review", {}),
        ("POST", "/api/v1/assessment/imports", original), ("POST", import_url + "/save", save),
        ("GET", import_url + "/original", {})]:
        assert_denied(client.request(method, url, json=body))
    cancelled = client.post(import_url + "/cancel", json={"idempotency_key": "inventory-import-cancel"})
    assert cancelled.status_code == 200, cancelled.text
    assert set(cancelled.json()) == {"id", "state"}
    assert PRIVATE not in cancelled.text


@pytest.mark.parametrize("change", ["active", "cycle", "restore"])
def test_original_learn_and_case_prepared_producers_refuse_changed_boundary(assembled, change):
    from renulus.cases.models import StartCase, DiscussCase
    from renulus.cases.streaming import discuss
    from renulus.contracts import ContextScope, Scope
    _, services, _ = assembled
    learn = services.get("learn")
    _, learn_run = learn.prepare("Synthetic explanation", ContextScope(kind=Scope.STUDY), None, None,
                                 "direct", "inventory-learn-request")
    cases = services.get("cases")
    case = cases.start(StartCase(text="Original synthetic case"))
    case_run, messages = cases.begin_discussion(case["id"], DiscussCase(revision=case["revision"],
        message="Synthetic discussion", request_id="inventory-case-request"))
    transport = OutputTransport()
    services.registry["provider"] = transport
    code = boundary(services, change)
    expected = "dependency_changed" if change == "restore" else code

    async def outputs():
        learned = [event async for event in learn.answer(learn_run, "Synthetic explanation", "direct", None)]
        discussed = [event async for event in discuss(cases, case_run, messages)]
        return learned, discussed

    learned, discussed = asyncio.run(outputs())
    assert expected in str(learned) and expected in str(discussed)
    assert all(event.type not in {"completed", "delta", "answer.delta"} for event in learned + discussed)
    assert transport.calls == 0
    assert services.db.fetch_all("SELECT * FROM learn_messages WHERE role='assistant'") == []
    assert not any(row["role"] == "assistant" for row in cases.get(case["id"])["messages"])


CASE_TEXT = "SYNTHETIC_CASE_TERMINAL_CACHE"


class CaseTextTransport(OutputTransport):
    async def stream(self, *args, **kwargs):
        self.calls += 1
        yield CASE_TEXT


def sse_values(response):
    assert response.status_code == 200, response.text
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]


def completed_case(services, client, saved=False):
    from renulus.cases.models import StartCase
    cases = services.get("cases")
    case = cases.start(StartCase(text="Original synthetic Case input"))
    if saved:
        case = cases.save(case["id"], case["revision"])
    transport = CaseTextTransport()
    services.registry["provider"] = transport
    body = {"revision": case["revision"], "message": "Synthetic question", "request_id": "inventory-case-terminal"}
    url = "/api/v1/cases/sessions/" + case["id"] + "/discuss"
    events = sse_values(client.post(url, json=body))
    assert events[-1]["type"] == "completed" and CASE_TEXT in str(events)
    return cases, case, transport, url, body, events


@pytest.mark.parametrize("change", ["cycle", "restore"])
def test_original_case_http_replay_rechecks_boundary_after_preparation(assembled, monkeypatch, change):
    _, services, client = assembled
    cases, case, transport, url, body, original_events = completed_case(services, client)
    original = cases.begin_discussion

    def restore_between_prepare_and_stream(*args, **kwargs):
        result = original(*args, **kwargs)
        boundary(services, change)
        return result

    monkeypatch.setattr(cases, "begin_discussion", restore_between_prepare_and_stream)
    response = client.post(url, json=body)
    # A Test cycle is also fenced by shared HTTP policy. Restore keeps that
    # policy revision unchanged, so the recorded producer must fence its epoch.
    assert CASE_TEXT not in response.text, response.text
    if response.status_code == 200:
        events = sse_values(response)
        assert len(events) == 1 and events[0]["type"] == "failed"
        assert events[0]["payload"]["error"]["code"] == ("dependency_changed" if change == "restore" else "assistance_changed")
    else:
        assert_denied(response, "assistance_changed")
    assert transport.calls == 1
    assert len(cases.get(case["id"])["messages"]) == 2


@pytest.mark.parametrize("change", ["active", "cycle", "restore"])
def test_original_case_terminal_checks_each_event_without_active_run_requirement(assembled, change):
    from renulus.cases.streaming import discuss
    _, services, client = assembled
    cases, case, transport, _, _, recorded = completed_case(services, client)
    run = cases._runs[recorded[0]["run_id"]]
    original_receipt = list(run.events)

    async def partial_replay():
        stream = discuss(cases, run, [])
        first = await anext(stream)
        code = boundary(services, change)
        rest = [event async for event in stream]
        return first, code, rest

    first, code, rest = asyncio.run(partial_replay())
    assert first.type == "started"  # completed run passes a current boundary
    assert len(rest) == 1 and rest[0].type == "failed"
    assert rest[0].sequence == 2
    assert rest[0].payload["error"]["code"] == ("dependency_changed" if change == "restore" else code)
    assert CASE_TEXT not in str(rest)
    assert run.events == original_receipt and run.status == "completed"
    assert transport.calls == 1


@pytest.mark.parametrize("saved", [False, True])
def test_original_case_normal_terminal_replay_keeps_explicit_save_semantics(assembled, saved):
    _, services, client = assembled
    cases, case, transport, url, body, original = completed_case(services, client, saved=saved)
    assert sse_values(client.post(url, json=body)) == original
    assert transport.calls == 1
    current = cases.get(case["id"])
    assert len(current["messages"]) == 2 and current["dirty"]
    rows = services.db.fetch_all("SELECT * FROM case_sessions WHERE id=?", (case["id"],))
    assert len(rows) == int(saved)
    if rows:
        assert CASE_TEXT not in str(rows)  # original API requires explicit Save


@pytest.mark.parametrize("temporary", [False, True])
def test_wrapped_case_terminal_replay_keeps_saved_or_temporary_retention(assembled, temporary):
    _, services, client = assembled
    transport = CaseTextTransport()
    services.registry["provider"] = transport
    created = client.post("/api/v1/conversations", json={"kind": "case", "temporary": temporary,
        "text": "Synthetic wrapped Case context"})
    assert created.status_code == 201, created.text
    chat = created.json()
    url = "/api/v1/conversations/case/" + chat["identity"]["id"]
    body = {"expected_revision": chat["revision"], "text": "Synthetic question", "request_id": "inventory-wrapped-case"}
    first = sse_values(client.post(url + "/messages", json=body))
    assert first[-1]["type"] == "completed", first
    assert CASE_TEXT in str(first)
    replay = sse_values(client.post(url + "/messages", json=body))
    assert replay[-1]["type"] == "completed" and transport.calls == 1, replay
    history = client.get(url + "/messages").json()["items"]
    assert len(history) == 2 and CASE_TEXT in str(history)
    rows = services.db.fetch_all("SELECT * FROM case_sessions WHERE id=?", (chat["identity"]["id"],))
    assert len(rows) == int(not temporary)
    if rows:
        assert CASE_TEXT in str(rows)  # wrapped saved conversation publishes


def test_original_case_cancelled_replay_is_neutral_after_restore_and_test(assembled):
    from renulus.cases.models import StartCase, DiscussCase
    from renulus.cases.streaming import discuss
    _, services, _ = assembled
    cases = services.get("cases")
    case = cases.start(StartCase(text="Synthetic cancellation context"))
    run, _ = cases.begin_discussion(case["id"], DiscussCase(revision=case["revision"],
        message="Synthetic prompt", request_id="inventory-cancelled-case"))
    cases.append_delta(run, CASE_TEXT)
    cases.cancel(run.id)
    cases.finish_error(run, cancelled=True)
    boundary(services, "restore")
    boundary(services, "active")

    async def replay():
        return [event async for event in discuss(cases, run, [])]

    events = asyncio.run(replay())
    assert len(events) == 1 and events[0].type == "cancelled" and events[0].payload == {}
    assert events[0].sequence == 1 and CASE_TEXT not in str(events)
