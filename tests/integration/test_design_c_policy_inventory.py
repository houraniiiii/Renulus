# SPDX-License-Identifier: MIT
"""DC14 assembled policy inventory and legacy producer boundary regressions.

Real create_app, installed migrations, saved collection and whole Test authority.
Synthetic output exercises the actual legacy producer; no live model is called.
The client deliberately omits lifespan: background indexing/schedulers are not
under test. Separate owner suites prove their late publication boundaries.
"""
import asyncio
import json

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
