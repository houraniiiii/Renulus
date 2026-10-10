# SPDX-License-Identifier: MIT
"""Owned synthetic nightly checks on assembled migrations; no live inference."""
import asyncio
from datetime import datetime, timedelta, timezone
import json

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from renulus.contracts import ApiError
from renulus.assessment.generation_models import CreateGenerationRequest
from renulus.design_c_contracts import canonical_digest
from renulus.server import create_app
from renulus.storage import utc_now
from renulus.storage.assessment_policy import advance_policy
from renulus.storage.invalidation import bump_context_epoch
from renulus.study.nightly_api import create_router
from renulus.study.nightly_models import NightlyPreferences, NightlySchedule, NightlyState, PreferencesUpdate
from renulus.study.nightly_service import COMMANDS, PREFERENCES, STATE, _load, _save


class Clock:
    def __init__(self):
        self.now = datetime(2026, 10, 10, 20, tzinfo=timezone.utc)

    def __call__(self):
        return self.now


class SyntheticTransport:
    """Application seam: the actual ProviderManager owns route selection."""
    def __init__(self):
        self.calls = []
        self.responses = []
        self.release = None
        self.started = asyncio.Event()
        self.error = None

    async def stream(self, provider, model, token, messages):
        assert token == "synthetic-nightly-token"
        number = len(self.calls)
        self.calls.append((provider, model, json.loads(json.dumps(messages))))
        self.started.set()
        if self.release is not None:
            await self.release.wait()
        if self.error:
            raise self.error
        output = self.responses[number] if number < len(self.responses) else batch(number * 5)
        yield {"type": "delta", "text": output if isinstance(output, str) else json.dumps(output)}
        yield {"type": "completed", "response_model": model}


def batch(start=0, count=5):
    return {"items": [{"stem": f"Original synthetic nightly question {number}",
        "options": [{"id": "a", "text": "First interpretation", "rationale": "Synthetic rationale"},
                    {"id": "b", "text": "Second interpretation", "rationale": "Other rationale"}],
        "correct_option_id": "a", "explanation": "PRIVATE_GENERATED_NIGHTLY_EXPLANATION", "hint": None,
        "source_indices": []} for number in range(start, start + count)]}


@pytest.fixture
def nightly(tmp_path, monkeypatch):
    monkeypatch.setattr("renulus.server.MODULE_ORDER", ("runtime", "content", "knowledge", "learn", "cases", "assessment", "memory", "study"))
    app = create_app(tmp_path / "synthetic-nightly")
    if "nightly" not in app.state.services.registry:
        app.include_router(create_router(app.state.services), prefix="/api/v1")
    services = app.state.services
    service = services.get("nightly")
    clock = Clock()
    service.local_now = clock
    provider = services.get("provider")
    transport = SyntheticTransport()
    provider._settings["connections"]["codex"] = {"access_token": "synthetic-nightly-token", "expires_at": 9999999999}
    provider._settings["selected_provider"] = "codex"
    provider._settings.setdefault("selected_models", {})["codex"] = "gpt-6.1-sol"
    provider._transport = transport
    generation = services.get("saved_generation")
    # Keep all real migrations/owners; avoid unrelated acquisition/startup work.
    services.on_startup = [generation.recover, service.start]
    services.on_shutdown = [provider.close, generation.close, service.close]
    return app, service, clock, transport


async def enable(service, **values):
    current = service.preferences()
    return await service.update_preferences(PreferencesUpdate(enabled=True,
        expected_revision=current["revision"], **values), "synthetic-enable:" + str(current["revision"]))


def add_memory(service):
    stamp = utc_now()
    service.db.execute("INSERT INTO memory_facts VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        ("nightly_memory", "Synthetic transplantation learning", "synthetic-hash", "learning-point", "T01", "study", 1, "manual", None, stamp, stamp))
    service.db.execute("INSERT INTO memory_history VALUES(?,?,?,?,?)",
                       ("nightly_memory", 1, "Synthetic transplantation learning", "added", stamp))


def guard_job(service, clock):
    """Install only a real-DDL guard specimen, not a substitute generation producer."""
    with service.db.transaction() as conn:
        state = _load(conn, STATE, NightlyState)
        context = service.services.get("home")._context(conn)
        key = "nightly:" + clock.now.date().isoformat()
        state = state.model_copy(update={"last_key": key, "last_claimed_day": clock.now.date()})
        _save(conn, STATE, state)
        schedule = NightlySchedule(day=clock.now.date(), timezone=str(clock.now.tzinfo),
            preferences_revision=service._preferences(conn).revision, home_settings_revision=context.settings_revision,
            eligibility_token=state.eligibility_token)
        stamp = utc_now()
        conn.execute("INSERT INTO assessment_test_jobs "
            "(id,operation,state,idempotency_key,request_hash,inputs_json,checkpoint_json,settings_revision,policy_revision,context_epoch,requested_count,created_at,updated_at) "
            "VALUES('nightly_guard','nightly_test','running',?,?,?,?,?,?,?,5,?,?)",
            (key, canonical_digest({}), json.dumps([entry.model_dump(mode="json") for entry in context.inputs[:20]]),
             json.dumps({"nightly": schedule.model_dump(mode="json")}), context.settings_revision, context.policy_revision, context.epoch, stamp, stamp))
        return dict(conn.execute("SELECT * FROM assessment_test_jobs WHERE id='nightly_guard'").fetchone())


def test_exact_default_preferences_and_rejected_renderer_payloads():
    assert NightlyPreferences().model_dump() == {"enabled": False, "local_time": "22:00", "question_count": 5, "revision": 1}
    with pytest.raises(ValidationError):
        PreferencesUpdate(expected_revision=1, prompt="RAW_PROMPT")
    with pytest.raises(ValidationError):
        PreferencesUpdate(expected_revision=1, inputs=[])


@pytest.mark.parametrize("values", [
    {"enabled": "true"}, {"enabled": 1}, {"question_count": 5.0}, {"question_count": True},
    {"question_count": "5"}, {"question_count": 7}, {"local_time": "24:00"}, {"local_time": "2:00"},
    {"local_time": "22:60"}, {"local_time": "22:00:00"}, {"local_time": "２２:００"}, {"revision": 0},
])
def test_preferences_strict_types_time_and_counts(values):
    with pytest.raises(ValidationError):
        NightlyPreferences(**values)


@pytest.mark.asyncio
async def test_off_startup_read_ticks_and_closed_recovery_never_infer(nightly):
    _, service, clock, transport = nightly
    await service.start()
    clock.now += timedelta(days=14)
    for _ in range(3):
        assert (await service.tick())["preferences"]["enabled"] is False
    assert service.read()["last_job"] is None
    assert not transport.calls
    await service.close()


@pytest.mark.asyncio
async def test_old_preference_key_retains_original_receipt_without_reenabling(nightly):
    _, service, _, transport = nightly
    first = PreferencesUpdate(enabled=True, expected_revision=1)
    original = await service.update_preferences(first, "synthetic-nightly-first")
    await service.update_preferences(PreferencesUpdate(enabled=False, expected_revision=2), "synthetic-nightly-second")
    assert await service.update_preferences(first, "synthetic-nightly-first") == original
    assert service.preferences() == {"enabled": False, "local_time": "22:00", "question_count": 5, "revision": 3}
    with pytest.raises(ApiError) as failure:
        await service.update_preferences(PreferencesUpdate(enabled=False, expected_revision=1), "synthetic-nightly-first")
    assert failure.value.code == "idempotency_conflict"
    assert not transport.calls


@pytest.mark.asyncio
async def test_evicted_preferences_receipt_cannot_apply_again(nightly):
    _, service, _, _ = nightly
    first = PreferencesUpdate(expected_revision=1)
    await service.update_preferences(first, "synthetic-nightly-old")
    for number in range(128):
        await service.update_preferences(PreferencesUpdate(expected_revision=service.preferences()["revision"]),
                                         "synthetic-nightly-bounded:" + str(number))
    with pytest.raises(ApiError) as failure:
        await service.update_preferences(first, "synthetic-nightly-old")
    assert failure.value.code == "revision_conflict"
    journal = json.loads(service.db.fetch_one("SELECT value FROM preferences WHERE key=?", (COMMANDS,))["value"])
    assert len(journal["receipts"]) == 128


@pytest.mark.asyncio
async def test_recovery_epoch_and_timezone_arm_future_boundary_only(nightly):
    _, service, clock, transport = nightly
    await enable(service)
    clock.now = clock.now.replace(hour=23)
    service.recover()
    assert service.read()["next_eligible_at"] == "2026-10-11T22:00:00+00:00"
    await service.tick()
    with service.db.transaction() as conn:
        bump_context_epoch(conn)
    await service.tick()
    clock.now = clock.now.astimezone(timezone(timedelta(hours=3), "Synthetic-East"))
    await service.tick()
    assert service.read()["next_eligible_at"] == "2026-10-11T22:00:00+03:00"
    assert service.read()["last_job"] is None and not transport.calls


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["off", "settings", "epoch", "policy", "delete-memory", "delete-revision", "recover"])
async def test_transactional_guard_checks_actual_canonical_sources_and_revision(nightly, change):
    _, service, clock, transport = nightly
    add_memory(service)
    await enable(service)
    row = guard_job(service, clock)
    with service.db.transaction() as conn:
        service.require_publication(conn, row)
    with service.db.transaction() as conn:
        if change in ("off", "settings"):
            prefs = service._preferences(conn)
            _save(conn, PREFERENCES, prefs.model_copy(update={"enabled": change != "off", "revision": prefs.revision + 1}))
        elif change == "epoch":
            bump_context_epoch(conn)
        elif change == "policy":
            advance_policy(conn)
        elif change == "delete-memory":
            conn.execute("DELETE FROM memory_facts WHERE id='nightly_memory'")
        elif change == "delete-revision":
            conn.execute("DELETE FROM memory_history WHERE record_id='nightly_memory'")
    if change == "recover":
        service.recover()
    with service.db.transaction() as conn, pytest.raises(ApiError):
        service.require_publication(conn, row)
    assert not transport.calls


def test_actual_router_offline_preference_save_and_invalid_import_fail_closed(nightly):
    app, service, _, transport = nightly
    service.services.get("provider")._settings["selected_provider"] = None
    with TestClient(app) as client:
        assert client.get("/api/v1/nightly").headers["cache-control"] == "no-store"
        headers = {"Idempotency-Key": "synthetic-router-preferences"}
        body = {"enabled": True, "local_time": "20:30", "question_count": 10, "expected_revision": 1}
        response = client.put("/api/v1/nightly/preferences", json=body, headers=headers)
        assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
        assert response.json() == {"enabled": True, "local_time": "20:30", "question_count": 10, "revision": 2}
        assert client.put("/api/v1/nightly/preferences", json=body, headers=headers).json() == response.json()
        assert client.put("/api/v1/nightly/preferences", json={**body, "question_count": 5}, headers=headers).status_code == 409
        assert client.put("/api/v1/nightly/preferences", json={**body, "prompt": "RAW_PROMPT"}, headers=headers).status_code == 422
    service.db.execute("UPDATE preferences SET value=? WHERE key=?", (json.dumps({"enabled": "true", "revision": 2}), PREFERENCES))
    assert service.preferences()["enabled"] is False and not transport.calls


async def finish_job(service, identifier):
    owner = service.services.get("saved_generation")
    task = owner.tasks.get(identifier)
    if task:
        await asyncio.wait_for(asyncio.shield(task), timeout=5)
    return service.read()["last_job"]


async def due_job(service, clock, **preferences):
    await enable(service, **preferences)
    clock.now = clock.now.replace(hour=22)
    return (await service.tick())["last_job"]


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [5, 10, 20])
async def test_scheduler_publishes_exact_saved_count_through_selected_route(nightly, count):
    _, service, clock, transport = nightly
    add_memory(service)
    job = await due_job(service, clock, question_count=count)
    final = await finish_job(service, job["id"])
    assert final["state"] == "published"
    assert final["validated_count"] == final["requested_count"] == count
    assert final["result"]["available"] is True
    assert len(transport.calls) == count // 5
    assert all((provider, model) == ("codex", "gpt-6.1-sol") for provider, model, _ in transport.calls)
    assert "Synthetic transplantation learning" in json.dumps(transport.calls)
    row = service.db.fetch_one("SELECT * FROM assessment_test_jobs WHERE id=?", (job["id"],))
    checkpoint = json.loads(row["checkpoint_json"])
    assert row["operation"] == "nightly_test" and row["idempotency_key"] == "nightly:2026-10-10"
    assert set(checkpoint["nightly"]) == {"day", "timezone", "preferences_revision", "home_settings_revision", "eligibility_token"}
    version = service.db.fetch_one("SELECT * FROM assessment_test_versions WHERE id=?", (row["published_version_id"],))
    assert version["origin"] == "nightly"
    assert len(json.loads(version["items_json"])) == count
    assert json.loads(version["provenance_json"])["producer"]["method"] == "nightly"
    assert "PRIVATE_GENERATED_NIGHTLY_EXPLANATION" not in json.dumps(service.read())
    # An original published receipt stays immutable after Off and token rotation.
    await service.update_preferences(PreferencesUpdate(enabled=False, expected_revision=2), "synthetic-published-off")
    replay = await service.services.get("saved_generation").create_nightly(
        CreateGenerationRequest.model_validate(checkpoint["request"]), schedule=checkpoint["nightly"])
    assert replay["result"]["version_id"] == row["published_version_id"]
    assert len(transport.calls) == count // 5


@pytest.mark.asyncio
async def test_concurrent_sleep_catchup_claims_only_latest_due_day(nightly):
    _, service, clock, transport = nightly
    await enable(service)
    clock.now += timedelta(days=9, hours=3)
    results = await asyncio.gather(*(service.tick() for _ in range(8)))
    identifier = next(result["last_job"]["id"] for result in results if result["last_job"])
    assert (await finish_job(service, identifier))["state"] == "published"
    rows = service.db.fetch_all("SELECT idempotency_key FROM assessment_test_jobs WHERE operation='nightly_test'")
    assert [row["idempotency_key"] for row in rows] == ["nightly:2026-10-19"]
    for _ in range(3):
        await service.tick()
    clock.now -= timedelta(days=4)
    await service.tick()
    clock.now += timedelta(days=4)
    await service.tick()
    assert len(transport.calls) == 1


@pytest.mark.asyncio
async def test_offline_day_consumed_without_retry_then_next_day_can_run(nightly):
    _, service, clock, transport = nightly
    provider = service.services.get("provider")
    provider._settings["selected_provider"] = None
    await enable(service)
    clock.now = clock.now.replace(hour=22)
    failed = await service.tick()
    assert failed["error_code"] and failed["last_job"] is None
    provider._settings["selected_provider"] = "codex"
    for _ in range(3):
        await service.tick()
    assert not transport.calls
    clock.now += timedelta(days=1)
    job = (await service.tick())["last_job"]
    assert (await finish_job(service, job["id"]))["state"] == "published"
    assert len(transport.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("output,expected", [("invalid-json", "failed"), (batch(count=3), "needs_review")])
async def test_failed_or_short_generation_never_auto_retries_or_publishes(nightly, output, expected):
    _, service, clock, transport = nightly
    transport.responses = [output]
    job = await due_job(service, clock)
    final = await finish_job(service, job["id"])
    assert final["state"] == expected and final["result"] is None
    for _ in range(3):
        await service.tick()
    assert len(transport.calls) == 1
    assert not service.db.fetch_one("SELECT id FROM assessment_test_versions WHERE origin='nightly'")


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["off", "cancel", "memory-correction", "memory-delete", "epoch", "policy", "timezone"])
async def test_running_scheduler_job_cannot_publish_changed_eligibility(nightly, change):
    _, service, clock, transport = nightly
    add_memory(service)
    transport.release = asyncio.Event()
    job = await due_job(service, clock)
    await asyncio.wait_for(transport.started.wait(), timeout=3)
    if change == "off":
        await service.update_preferences(PreferencesUpdate(enabled=False, expected_revision=2), "synthetic-off-during-run")
    elif change == "cancel":
        cancelled = await service.cancel(job["id"], "synthetic-stop-during-run")
        assert cancelled == {"id": job["id"], "state": "cancelled"}
    else:
        with service.db.transaction() as conn:
            if change == "memory-correction":
                conn.execute("UPDATE memory_facts SET text='Corrected synthetic learning',revision=2 WHERE id='nightly_memory'")
                conn.execute("INSERT INTO memory_history VALUES('nightly_memory',2,'Corrected synthetic learning','edited',?)", (utc_now(),))
            elif change == "memory-delete":
                conn.execute("DELETE FROM memory_facts WHERE id='nightly_memory'")
            elif change == "epoch":
                bump_context_epoch(conn)
            elif change == "policy":
                advance_policy(conn)
        if change == "timezone":
            clock.now = clock.now.astimezone(timezone(timedelta(hours=3), "Synthetic-East"))
    transport.release.set()
    final = await finish_job(service, job["id"])
    assert final["state"] in ("failed", "cancelled") and final["result"] is None
    assert not service.db.fetch_one("SELECT id FROM assessment_test_versions WHERE origin='nightly'")
    await service.tick()
    assert len(transport.calls) == 1


@pytest.mark.asyncio
async def test_final_publication_transaction_rechecks_context(nightly, monkeypatch):
    _, service, clock, transport = nightly
    owner = service.services.get("saved_generation")
    publish = owner._publish
    def invalidate_at_publication(conn, row, checkpoint, **kwargs):
        bump_context_epoch(conn)
        publish(conn, row, checkpoint, **kwargs)
    monkeypatch.setattr(owner, "_publish", invalidate_at_publication)
    job = await due_job(service, clock)
    final = await finish_job(service, job["id"])
    assert final["state"] == "failed" and final["validated_count"] == 5
    assert final["error_code"] == "nightly_invalidated"
    assert len(transport.calls) == 1
    assert not service.db.fetch_one("SELECT id FROM assessment_test_versions WHERE origin='nightly'")


@pytest.mark.asyncio
async def test_enabled_restart_after_due_waits_for_next_future_night(nightly):
    app, service, clock, transport = nightly
    await enable(service)
    clock.now += timedelta(days=5, hours=3)
    await service.close()
    reopened = create_app(app.state.services.paths.root)
    if "nightly" not in reopened.state.services.registry:
        reopened.include_router(create_router(reopened.state.services), prefix="/api/v1")
    next_service = reopened.state.services.get("nightly")
    next_service.local_now = clock
    next_service.recover()
    assert next_service.read()["preferences"]["enabled"] is True
    assert next_service.read()["next_eligible_at"] == "2026-10-16T22:00:00+00:00"
    await next_service.tick()
    assert next_service.read()["last_job"] is None and not transport.calls
