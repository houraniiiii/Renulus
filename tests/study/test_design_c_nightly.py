# SPDX-License-Identifier: MIT
"""Owned synthetic nightly checks on assembled migrations; no live inference."""
import asyncio
from datetime import datetime, timedelta, timezone
import json

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from renulus.contracts import ApiError
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
