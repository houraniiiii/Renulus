# SPDX-License-Identifier: MIT
"""Owned synthetic nightly checks on assembled migrations; no live inference."""
import asyncio
from datetime import datetime, timedelta, timezone
import json

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest
from httpx import ASGITransport, AsyncClient, ReadError

from renulus.contracts import ApiError
from renulus.assessment.generation_models import CreateGenerationRequest
from renulus.design_c_contracts import canonical_digest
from renulus.server import create_app
from renulus.storage import utc_now
from renulus.storage.assessment_policy import advance_policy
from renulus.storage.invalidation import bump_context_epoch, context_epoch_in
from renulus.storage.backup import export_records
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


async def finish_job(service, identifier, *, timeout=5):
    owner = service.services.get("saved_generation")
    task = owner.tasks.get(identifier)
    if task:
        await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
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


@pytest.mark.asyncio
async def test_actual_export_restore_epoch_collision_interrupts_and_waits_for_future_night(nightly, tmp_path):
    app, service, clock, transport = nightly
    with service.db.transaction() as conn:
        while context_epoch_in(conn) < 5:
            bump_context_epoch(conn)
    transport.release = asyncio.Event()
    job = await due_job(service, clock)
    await asyncio.wait_for(transport.started.wait(), timeout=20)
    bundle = export_records(app.state.services)
    preferences = {row["key"]: json.loads(row["value"]) for row in bundle["records"]["preferences"]}
    assert preferences[PREFERENCES] == {"enabled": True, "local_time": "22:00", "question_count": 5, "revision": 2}
    assert STATE not in preferences and COMMANDS not in preferences and "home.suggestions" not in preferences
    original = next(row for row in bundle["records"]["assessment_test_jobs"] if row["id"] == job["id"])
    assert original["state"] == "running" and original["context_epoch"] == 5
    restored = create_app(tmp_path / "restored-synthetic-nightly")
    destination = restored.state.services.get("nightly")
    destination.local_now = clock
    with destination.db.transaction() as conn:
        while context_epoch_in(conn) < 4:
            bump_context_epoch(conn)
    restored.state.services.get("data_recovery").restore_json(bundle, confirm_backup_date=True, confirmed_exported_at=bundle["exported_at"])
    with destination.db.transaction() as conn:
        assert context_epoch_in(conn) == 5  # Same integer, different local process.
    row = destination.db.fetch_one("SELECT * FROM assessment_test_jobs WHERE id=?", (job["id"],))
    assert row["state"] == "failed" and row["error_code"] == "interrupted"
    assert row["checkpoint_json"] == original["checkpoint_json"]
    assert row["validated_count"] == original["validated_count"]
    assert destination.read()["last_job"]["state"] == "failed"
    await destination.tick()
    assert destination.read()["next_eligible_at"] == "2026-10-11T22:00:00+00:00"
    assert restored.state.services.get("saved_generation").tasks == {}
    assert restored.state.services.get("provider").status()["active_runs"] == []
    assert len(transport.calls) == 1
    await service.services.get("saved_generation").close()
    assert not destination.db.fetch_one("SELECT id FROM assessment_test_versions WHERE origin='nightly'")


@pytest.mark.asyncio
async def test_cold_status_reconciles_same_epoch_orphan_without_generation_ui(nightly):
    app, service, clock, transport = nightly
    transport.release = asyncio.Event()
    job = await due_job(service, clock)
    await asyncio.wait_for(transport.started.wait(), timeout=20)
    # An actual pending job has no process-local task in this new owner.
    cold = create_app(app.state.services.paths.root)
    cold_service = cold.state.services.get("nightly")
    cold_service.local_now = clock
    assert cold_service.services.get("saved_generation").tasks == {}
    final = cold_service.read()["last_job"]
    assert final["state"] == "failed" and final["error_code"] == "interrupted"
    await finish_job(service, job["id"])
    await cold_service.tick()
    assert len(transport.calls) == 1 and cold_service.services.get("saved_generation").tasks == {}
    clock.now += timedelta(days=1)
    await cold_service.tick()
    assert cold_service.read()["error_code"] != "generation_capacity"
    with cold_service.db.transaction() as conn:
        assert conn.execute("SELECT COUNT(*) FROM assessment_test_jobs WHERE state IN ('queued','running') AND operation='nightly_test'").fetchone()[0] == 0


@pytest.mark.asyncio
async def test_scheduler_saved_setup_study_and_test_replay_keep_one_personal_version(nightly):
    """Actual Nightly producer and HTTP consumers; only provider transport is synthetic."""
    app, service, clock, transport = nightly
    attempts = service.services.get("whole_attempts")
    # The attempt owner uses an independent clock: moving the scheduler to the
    # following day below must not accidentally expire an explicitly timed Test.
    attempt_time = clock.now.replace(hour=22)
    attempts.clock, attempts.monotonic = lambda: attempt_time, lambda: 0
    base = "/api/v1/assessment/test-attempts"
    lost_keys = {"nightly-consumer-study-start", "nightly-consumer-test-start",
                 "nightly-consumer-test-draft", "nightly-consumer-test-submit"}

    class LostAcknowledgement(ASGITransport):
        async def handle_async_request(self, request):
            response = await super().handle_async_request(request)
            key = request.headers.get("Idempotency-Key")
            if key in lost_keys and response.is_success:
                lost_keys.remove(key)
                # The assembled app has committed and produced a real response.
                # Lose it at the HTTP boundary, without replacing any owner result.
                await response.aread()
                await response.aclose()
                raise ReadError("Synthetic lost acknowledgement", request=request)
            return response

    async with AsyncClient(transport=LostAcknowledgement(app), base_url="http://testserver") as client:
        async def replay_after_lost_ack(method, url, body, key, expected=200):
            headers = {"Idempotency-Key": key}
            with pytest.raises(ReadError, match="Synthetic lost acknowledgement"):
                await client.request(method, url, json=body, headers=headers)
            response = await client.request(method, url, json=body, headers=headers)
            assert response.status_code == expected, response.text
            return response.json()

        initial = await client.get("/api/v1/nightly")
        assert initial.status_code == 200 and initial.json()["preferences"]["enabled"] is False
        assert (await service.tick())["last_job"] is None and not transport.calls
        enabled = await client.put("/api/v1/nightly/preferences",
            json={"enabled": True, "local_time": "22:00", "question_count": 5, "expected_revision": 1},
            headers={"Idempotency-Key": "nightly-consumer-enable"})
        assert enabled.status_code == 200 and enabled.json()["revision"] == 2
        clock.now = clock.now.replace(hour=22)
        job = (await service.tick())["last_job"]
        assert (await finish_job(service, job["id"], timeout=20))["state"] == "published"
        ready = await client.get("/api/v1/nightly")
        assert ready.status_code == 200, ready.text
        result = ready.json()["last_job"]["result"]
        version_id, test_id = result["version"]["id"], result["test"]["id"]
        assert result == {"version": {"type": "saved_test_version", "id": version_id},
                          "test": {"type": "saved_test", "id": test_id}, "available": True}
        assert ready.json()["last_job"]["validated_count"] == 5
        stored_version = dict(service.db.fetch_one("SELECT * FROM assessment_test_versions WHERE id=?", (version_id,)))
        assert stored_version["origin"] == "nightly" and stored_version["review_quality"] == "personal"
        assert len(json.loads(stored_version["items_json"])) == 5
        assert json.loads(stored_version["provenance_json"])["producer"]["method"] == "nightly"
        collection = await client.get("/api/v1/assessment/tests", params={"origin": "nightly"})
        assert collection.status_code == 200, collection.text
        assert [(item["id"], item["latest_version"]["id"]) for item in collection.json()["items"]] == [(test_id, version_id)]
        for url, params in (("/api/v1/assessment/tests/" + test_id + "/setup", {"version_id": version_id}),
                            ("/api/v1/assessment/tests/versions/" + version_id + "/setup", {})):
            setup = await client.get(url, params=params)
            assert setup.status_code == 200, setup.text
            assert setup.json()["can_start"] is True
            assert setup.json()["version"]["id"] == version_id and setup.json()["version"]["item_count"] == 5
            assert setup.json()["modes"] == ["study", "test"] and setup.json()["timing_default"] == "untimed"
            assert "PRIVATE_GENERATED_NIGHTLY_EXPLANATION" not in setup.text
        # Publication and setup are selection only: no start, timer, exposure or grading.
        for table in ("assessment_test_attempts", "assessment_attempt_drafts",
                      "assessment_attempt_exposure", "assessment_attempt_commands", "learning_evidence"):
            assert service.db.fetch_all("SELECT * FROM " + table) == []

        study_body = {"version": result["version"], "mode": "study", "timing": {"kind": "untimed"}}
        study = await replay_after_lost_ack("POST", base, study_body, "nightly-consumer-study-start", 201)
        assert study["version_id"] == version_id and study["status"] == "active"
        assert study["timing"]["deadline_at"] is None and study["committed"] == [] and study["result"] is None
        assert study["current_item"]["repeat"] is False
        assert "PRIVATE_GENERATED_NIGHTLY_EXPLANATION" not in json.dumps(study)
        study_url = base + "/" + study["id"]
        help_body = {"expected_revision": study["draft_revision"], "expected_policy_revision": study["policy"]["revision"],
                     "item_id": study["current_item"]["item_id"], "kind": "sources"}
        help_response = await client.post(study_url + "/help", json=help_body,
            headers={"Idempotency-Key": "nightly-consumer-study-help"})
        assert help_response.status_code == 200, help_response.text
        help_result = help_response.json()
        assert help_result["assisted"] is True and help_result["references"] == []
        assert help_result["context"]["version_id"] == version_id and help_result["context"]["attempt_id"] == study["id"]
        assert "PRIVATE_GENERATED_NIGHTLY_EXPLANATION" not in help_response.text
        assert service.db.fetch_all("SELECT * FROM learning_evidence") == []
        commit_body = {"expected_revision": study["draft_revision"],
                       "item_id": study["current_item"]["item_id"], "option_ids": ["a"]}
        committed = await client.post(study_url + "/submit-answer", json=commit_body,
            headers={"Idempotency-Key": "nightly-consumer-study-answer"})
        assert committed.status_code == 200, committed.text
        study = committed.json()
        assert len(study["committed"]) == 1
        entry = study["committed"][0]
        assert entry["assisted"] is True and entry["repeat"] is False and entry["score_bucket"] == "personal"
        study_end = await client.post(study_url + "/submit", json={"expected_draft_revision": study["draft_revision"]},
            headers={"Idempotency-Key": "nightly-consumer-study-end"})
        assert study_end.status_code == 200 and study_end.json()["status"] == "ended", study_end.text
        study_result = study_end.json()["result"]
        assert study_result["version_id"] == version_id and study_result["not_submitted"] == 4
        assert study_result["cohorts"]["personal"] == {"denominator": 1, "answered": 1, "unanswered": 0, "correct": 1}
        current_study = await client.post(base, json=study_body, headers={"Idempotency-Key": "nightly-consumer-study-start"})
        assert current_study.status_code == 201 and current_study.json()["id"] == study["id"]
        assert current_study.json()["status"] == "ended" and current_study.json()["result"] == study_result

        test_body = {"version": result["version"], "mode": "test",
                     "timing": {"kind": "timed", "duration_seconds": 600}}
        test = await replay_after_lost_ack("POST", base, test_body, "nightly-consumer-test-start", 201)
        assert test["version_id"] == version_id and test["current_item"]["repeat"] is True
        assert test["timing"]["deadline_at"] == (attempt_time + timedelta(seconds=600)).isoformat(timespec="microseconds")
        assert test["timing"]["remaining_seconds"] == 600
        assert test["policy"]["active_test_id"] == test["id"] and test["policy"]["assistance_allowed"] is False
        test_url = base + "/" + test["id"]
        draft_body = {"expected_revision": test["draft_revision"], "position": test["position"],
                      "answers": [{**answer, "option_ids": ["a"] if index == 0 else [], "marked": index == 0}
                                  for index, answer in enumerate(test["answers"])]}
        test = await replay_after_lost_ack("PUT", test_url + "/draft", draft_body, "nightly-consumer-test-draft")
        assert test["draft_revision"] == 1 and test["answers"][0]["option_ids"] == ["a"]
        assert test["answers"][0]["marked"] is True and test["committed"] == [] and test["result"] is None
        assert "PRIVATE_GENERATED_NIGHTLY_EXPLANATION" not in json.dumps(test)
        assert service.db.fetch_all("SELECT * FROM learning_evidence WHERE entity_id=?", (test["id"],)) == []
        status = await client.get("/api/v1/nightly")
        assert status.status_code == 200 and status.json()["assistance_allowed"] is False
        assert status.json()["last_job"]["result"] == result
        assert "PRIVATE_GENERATED_NIGHTLY_EXPLANATION" not in status.text
        assert status.headers["cache-control"] == "no-store"
        off = await client.put("/api/v1/nightly/preferences",
            json={"enabled": False, "local_time": "22:00", "question_count": 5, "expected_revision": 2},
            headers={"Idempotency-Key": "synthetic-nightly-test-off"})
        assert off.status_code == 200 and off.json()["enabled"] is False
        stop = await client.post("/api/v1/nightly/jobs/" + job["id"] + "/cancel", headers={"Idempotency-Key": "synthetic-nightly-test-stop"})
        assert stop.status_code == 200 and stop.json() == {"id": job["id"], "state": "published"}
        stop_replay = await client.post("/api/v1/nightly/jobs/" + job["id"] + "/cancel", headers={"Idempotency-Key": "synthetic-nightly-test-stop"})
        assert stop_replay.status_code == 200 and stop_replay.json() == stop.json()
        clock.now += timedelta(days=1)
        assert (await service.tick())["preferences"]["enabled"] is False
        active = await client.get(test_url)
        assert active.status_code == 200 and active.json()["status"] == "active"
        assert active.json()["timing"]["deadline_at"] == test["timing"]["deadline_at"]
        final_body = {"expected_draft_revision": test["draft_revision"]}
        final = await replay_after_lost_ack("POST", test_url + "/submit", final_body, "nightly-consumer-test-submit")
        assert final["status"] == "submitted" and final["policy"]["assistance_allowed"] is True
        test_result = final["result"]
        assert test_result["version_id"] == version_id and test_result["item_count"] == 5
        assert test_result["reason"] == "manual" and test_result["not_submitted"] == 0
        assert test_result["cohorts"]["personal"] == {"denominator": 5, "answered": 1, "unanswered": 4, "correct": 1}
        first = next(item for item in test_result["items"] if item["item_id"] == entry["item_id"])
        assert first["repeat"] is True and first["assisted"] is False and first["score_bucket"] == "personal"
        current_test = await client.post(base, json=test_body, headers={"Idempotency-Key": "nightly-consumer-test-start"})
        assert current_test.status_code == 201 and current_test.json()["id"] == test["id"]
        assert current_test.json()["status"] == "submitted" and current_test.json()["result"] == test_result
        for final_result in (study_result, test_result):
            assert final_result["origin"] == "nightly" and final_result["review_quality"] == "personal"
            assert all(final_result["cohorts"][bucket]["denominator"] == 0 for bucket in ("fresh", "assisted", "repeat"))
        persisted_attempts = service.db.fetch_all("SELECT * FROM assessment_test_attempts")
        assert {(row["id"], row["version_id"], row["mode"]) for row in persisted_attempts} == {
            (study["id"], version_id, "study"), (test["id"], version_id, "test")}
        for row in persisted_attempts:
            snapshot = json.loads(row["version_snapshot_json"])
            assert snapshot["version"]["id"] == version_id and len(snapshot["version"]["items"]) == 5
            assert snapshot["pinned_provenance"] == json.loads(stored_version["provenance_json"])
        starts = service.db.fetch_all("SELECT target_id FROM assessment_attempt_commands WHERE operation='start'")
        assert sorted(row["target_id"] for row in starts) == sorted([study["id"], test["id"]])
        evidence = service.db.fetch_all("SELECT * FROM learning_evidence")
        assert len(evidence) == 6
        with service.db.transaction() as conn:
            for row in evidence:
                payload = json.loads(row["payload_json"])
                assert payload["version_id"] == version_id and payload["origin"] == "nightly"
                assert payload["review_quality"] == "personal" and payload["score_bucket"] == "personal"
                assert payload["bank_cohort_eligible"] is False and payload["reviewed"] is False
                assert "PRIVATE_GENERATED_NIGHTLY_EXPLANATION" not in row["payload_json"]
                canonical = attempts.committed_evidence_in(conn, row["id"])
                if payload["outcome"] == "unanswered":
                    assert canonical is None
                else:
                    assert canonical["payload"] == payload
        assert (await client.get("/api/v1/nightly")).json()["last_job"]["result"] == result
    assert lost_keys == set()
    assert dict(service.db.fetch_one("SELECT * FROM assessment_test_versions WHERE id=?", (version_id,))) == stored_version
    assert len(service.db.fetch_all("SELECT id FROM assessment_test_versions WHERE origin='nightly'")) == 1
    assert len(transport.calls) == 1
    assert transport.calls[0][:2] == ("codex", "gpt-6.1-sol")
