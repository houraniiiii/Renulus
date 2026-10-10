# SPDX-License-Identifier: MIT
"""Owned synthetic Home checks; no live inference, credentials or owner profile."""
import json
import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from renulus.study.home_models import HomePreferences, SuggestionBundle
from renulus.contracts import ApiError
from renulus.server import create_app
from renulus.storage import utc_now
from renulus.storage.assessment_policy import advance_policy
from renulus.storage.invalidation import bump_context_epoch
from renulus.study.home_models import NameUpdate
from renulus.study.home_service import HomeService
from fastapi.testclient import TestClient


class SyntheticTransport:
    """Application stream adapter; the actual ProviderManager still chooses the route."""
    def __init__(self):
        self.calls = []
        self.response = json.dumps(bundle())
        self.error = None
        self.started = asyncio.Event()
        self.release = None

    async def stream(self, provider, model, token, messages):
        assert token == "synthetic-home-token"
        self.calls.append((provider, model, json.loads(json.dumps(messages))))
        self.started.set()
        if self.release is not None:
            await self.release.wait()
        if self.error:
            raise self.error
        yield {"type": "delta", "text": self.response}
        yield {"type": "completed", "response_model": model}


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr("renulus.server.MODULE_ORDER", ("runtime", "content", "knowledge", "learn", "cases", "assessment", "memory", "study"))
    app = create_app(tmp_path / "synthetic-profile")
    service = app.state.services.registry["home"]
    provider = app.state.services.registry["provider"]
    transport = SyntheticTransport()
    provider._settings["connections"]["codex"] = {"access_token": "synthetic-home-token", "expires_at": 9999999999}
    provider._settings["selected_provider"] = "codex"
    provider._settings.setdefault("selected_models", {})["codex"] = "gpt-6.1-sol"
    provider._transport = transport
    # Home API lifecycle is real; helper/model acquisition is outside this slice.
    app.state.services.on_startup = [service.recover]
    app.state.services.on_shutdown = [provider.close, service.close]
    service.local_now = lambda: datetime(2026, 10, 10, 12, tzinfo=timezone(timedelta(hours=2), "Europe/Warsaw"))
    return app, service, transport


def memory(service, *, text="Synthetic general renal learning", scope="study"):
    stamp = utc_now()
    service.db.execute("INSERT INTO memory_facts VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        ("memory_synthetic", text, "synthetic-hash", "learning-point", "T01", scope, 1, "manual", None, stamp, stamp))
    service.db.execute("INSERT INTO memory_history VALUES(?,?,?,?,?)",
        ("memory_synthetic", 1, text, "added", stamp))


async def finish(service):
    assert service._task is not None
    await service._task
    return service.read()


def bundle():
    return {kind: [f"Synthetic {kind} learning prompt {i}" for i in range(5)]
            for kind in ("explain", "case", "practice")}


def test_absent_name_and_normalised_chosen_name():
    assert HomePreferences().doctor_name is None
    assert HomePreferences(doctor_name="   ").doctor_name is None
    assert HomePreferences(doctor_name="  Ada  ").doctor_name == "Ada"


@pytest.mark.parametrize("name", [12, False, [], {}, "x" * 81, "Ada\nByron", "Ada\u202eByron", "Ada\x00Byron"])
def test_name_rejects_types_lengths_controls_and_bidi(name):
    with pytest.raises(ValidationError):
        HomePreferences(doctor_name=name)


@pytest.mark.parametrize("change", ["missing", "extra", "short", "long", "empty", "number", "duplicate", "control"])
def test_whole_bundle_validation_rejects_partial_or_unsafe_output(change):
    value = bundle()
    if change == "missing":
        del value["practice"]
    elif change == "extra":
        value["answer_key"] = "not allowed"
    elif change == "short":
        value["case"].pop()
    elif change == "long":
        value["case"].append("sixth")
    elif change == "empty":
        value["explain"][0] = "   "
    elif change == "number":
        value["explain"][0] = 1
    elif change == "duplicate":
        value["case"][0] = value["explain"][0].upper()
    elif change == "control":
        value["case"][0] = "control\u202e"
    with pytest.raises(ValidationError):
        SuggestionBundle.model_validate_json(json.dumps(value))


def test_whole_bundle_has_exactly_fifteen_prompts():
    valid = SuggestionBundle.model_validate_json(json.dumps(bundle()))
    assert len(valid.explain + valid.case + valid.practice) == 15


@pytest.mark.asyncio
async def test_repeated_concurrent_opens_one_real_selected_route_job_and_dated_cache(home):
    app, service, transport = home
    initial = await asyncio.gather(*(service.refresh() for _ in range(8)))
    assert len({row["job_id"] for row in initial}) == 1
    result = await finish(service)
    assert result["suggestions"] == bundle()
    assert result["suggestions_date"] == "2026-10-10"
    assert result["job"]["state"] == "published"
    assert len(transport.calls) == 1
    assert transport.calls[0][:2] == ("codex", "gpt-6.1-sol")
    await service.refresh()
    assert len(transport.calls) == 1
    assert len(service.db.fetch_all("SELECT * FROM assessment_test_jobs")) == 1
    assert service.db.fetch_one("SELECT COUNT(*) AS n FROM learning_evidence")["n"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["invalid", "quota", "offline", "timeout", "oversized", "duplicate_json"])
async def test_failure_keeps_prior_valid_cache_with_its_date_and_deduplicates(home, failure):
    _, service, transport = home
    await service.refresh()
    await finish(service)
    previous = service.db.fetch_one("SELECT value FROM preferences WHERE key='home.suggestions'")["value"]
    service.local_now = lambda: datetime(2026, 10, 11, 12, tzinfo=timezone(timedelta(hours=2), "Europe/Warsaw"))
    if failure == "invalid":
        transport.response = '{"explain": ["partial"]}'
    elif failure == "quota":
        transport.error = ApiError("provider_quota", "Synthetic quota failure", 429)
    elif failure == "offline":
        transport.error = ApiError("provider_unavailable", "Synthetic offline failure", 503)
    elif failure == "duplicate_json":
        transport.response = json.dumps(bundle())[:-1] + ' ,"case":' + json.dumps(bundle()["case"]) + "}"
    elif failure == "oversized":
        transport.response = "x" * 16001
    else:
        transport.release = asyncio.Event()
        service.timeout = 0.02
    await service.refresh()
    result = await finish(service)
    assert result["suggestions"] == bundle()
    assert result["stale"] and result["suggestions_date"] == "2026-10-10"
    assert result["job"]["state"] == "failed"
    assert not service.services.get("provider").status()["active_runs"]
    assert service.db.fetch_one("SELECT value FROM preferences WHERE key='home.suggestions'")["value"] == previous
    await service.refresh()
    assert len(transport.calls) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["memory_edit", "memory_delete", "restore", "settings", "policy"])
async def test_changed_canonical_inputs_or_epoch_settings_policy_block_publication(home, change):
    _, service, transport = home
    memory(service)
    transport.release = asyncio.Event()
    await service.refresh()
    await asyncio.wait_for(transport.started.wait(), timeout=5)
    with service.db.transaction() as conn:
        if change == "memory_edit":
            conn.execute("UPDATE memory_facts SET text='Corrected synthetic learning',revision=2")
        elif change == "memory_delete":
            conn.execute("DELETE FROM memory_facts")
        elif change == "restore":
            bump_context_epoch(conn)
        elif change == "policy":
            advance_policy(conn)
        else:
            conn.execute("INSERT INTO preferences VALUES('study.goals',?,?)",
                (json.dumps({"track": "general", "topic_ids": ["T01"], "hours_per_week": 5}), utc_now()))
    transport.release.set()
    result = await finish(service)
    assert result["suggestions"] is None
    assert result["job"]["state"] == "failed"
    assert service.db.fetch_one("SELECT 1 FROM preferences WHERE key='home.suggestions'") is None


@pytest.mark.asyncio
async def test_source_existence_is_rechecked_without_relying_only_on_epoch(home):
    _, service, transport = home
    stamp = utc_now()
    service.db.execute("INSERT INTO learn_threads VALUES(?,?,?,?,?,?)",
        ("thread_synthetic", "Synthetic thread", "T01", "direct", stamp, stamp))
    service.db.execute("INSERT INTO learning_evidence VALUES(?,?,?,?,?,?)",
        ("evidence_synthetic", "study-interest", "T01", "thread_synthetic",
         json.dumps({"scope": {"kind": "study", "entity_id": "thread_synthetic"}, "activity": "explain", "topic_id": "T01"}), stamp))
    transport.release = asyncio.Event()
    await service.refresh()
    await transport.started.wait()
    service.db.execute("DELETE FROM learn_threads WHERE id='thread_synthetic'")
    transport.release.set()
    result = await finish(service)
    assert result["suggestions"] is None
    assert result["job"]["error_code"] == "dependency_changed"


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["memory_delete", "restore", "policy"])
async def test_cache_rechecks_deleted_memory_restore_and_policy_on_every_read(home, change):
    _, service, _ = home
    memory(service)
    await service.refresh()
    assert (await finish(service))["suggestions"]
    with service.db.transaction() as conn:
        if change == "memory_delete":
            conn.execute("DELETE FROM memory_facts")
        elif change == "restore":
            bump_context_epoch(conn)
        else:
            advance_policy(conn)
    assert service.read()["suggestions"] is None


@pytest.mark.asyncio
async def test_input_boundary_uses_only_eligible_canonical_memory_not_case_originals_or_keys(home):
    _, service, transport = home
    memory(service)
    stamp = utc_now()
    for kind in ("case-discussion", "study-answer", "learning-point"):
        service.db.execute("INSERT INTO learning_evidence VALUES(?,?,?,?,?,?)",
            ("excluded_" + kind, kind, "T01", "temporary_synthetic",
             json.dumps({"scope": {"kind": "saved-case"}, "raw": "RAW_CASE_SENTINEL", "correct_option_ids": ["KEY_SENTINEL"]}), stamp))
    service.db.execute("INSERT INTO case_sessions VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        ("case_synthetic", 1, "daily", "PRIVATE_TITLE_SENTINEL", "RAW_CASE_SENTINEL", "[]", None, 0, 0, stamp, stamp, stamp))
    await service.refresh()
    result = await finish(service)
    sent = json.dumps(transport.calls)
    assert "Synthetic general renal learning" in sent
    assert all(sentinel not in sent for sentinel in ("RAW_CASE_SENTINEL", "KEY_SENTINEL", "PRIVATE_TITLE_SENTINEL", "temporary_synthetic"))
    stored = json.dumps(service.db.fetch_all("SELECT inputs_json,checkpoint_json FROM assessment_test_jobs"))
    assert "RAW_CASE_SENTINEL" not in stored and "temporary_synthetic" not in stored
    assert result["suggestions"]


def test_first_run_disconnected_name_api_revision_and_export_boundary(home):
    app, service, transport = home
    provider = app.state.services.registry["provider"]
    provider._settings["selected_provider"] = None
    with TestClient(app) as client:
        response = client.get("/api/v1/home")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.json()["suggestions"] is None
        assert response.json()["preferences"] == {"doctor_name": None, "revision": 1}
        body = {"doctor_name": "Ada", "expected_revision": 1}
        headers = {"Idempotency-Key": "synthetic-name-1"}
        saved = client.put("/api/v1/home/preferences", json=body, headers=headers)
        assert saved.json() == {"doctor_name": "Ada", "revision": 2}
        assert client.put("/api/v1/home/preferences", json=body, headers=headers).json() == saved.json()
        assert client.put("/api/v1/home/preferences", json={**body, "doctor_name": "Other"}, headers=headers).status_code == 409
        assert client.put("/api/v1/home/preferences", json=body, headers={"Idempotency-Key": "synthetic-name-2"}).status_code == 409
        assert client.put("/api/v1/home/preferences", json={**body, "doctor_name": 12}, headers=headers).status_code == 422
        assert client.post("/api/v1/home/suggestions/refresh", headers={"Idempotency-Key": "synthetic-refresh"}).status_code == 409
    assert not transport.calls
    from renulus.storage.backup import snapshot_in
    with service.db.transaction() as conn:
        conn.execute("INSERT INTO preferences VALUES('home.suggestions','{}',?)", (utc_now(),))
        exported = snapshot_in(conn)
    assert "home.preferences" in str(exported)
    assert "home.suggestions" not in str(exported)
    assert "home.preference_commands" not in str(exported)


def test_name_replay_after_later_edits_returns_original_durable_outcome_without_reapplying(home):
    _, service, _ = home
    first = NameUpdate(doctor_name="Ada", expected_revision=1)
    original = service.save_name(first, "synthetic-first")
    service.save_name(NameUpdate(doctor_name="Grace", expected_revision=2), "synthetic-second")
    assert service.save_name(first, "synthetic-first") == original
    assert service.preferences() == {"doctor_name": "Grace", "revision": 3}
    for number in range(128):
        current = service.preferences()
        service.save_name(NameUpdate(doctor_name="Synthetic", expected_revision=current["revision"]),
                          "synthetic-bounded-" + str(number))
    with pytest.raises(ApiError) as failed:
        service.save_name(first, "synthetic-first")
    assert failed.value.code == "revision_conflict"
    receipts = json.loads(service.db.fetch_one("SELECT value FROM preferences WHERE key='home.preference_commands'")["value"])["receipts"]
    assert len(receipts) == 128


@pytest.mark.asyncio
async def test_actual_export_restore_keeps_chosen_name_without_daily_cache_or_command_receipts(home, tmp_path):
    app, service, transport = home
    service.save_name(NameUpdate(doctor_name="Ada", expected_revision=1), "synthetic-export-name")
    await service.refresh()
    assert (await finish(service))["suggestions"] == bundle()
    from renulus.storage.backup import export_records, restore_records
    exported = export_records(app.state.services)
    exported_preferences = {row["key"]: json.loads(row["value"])
                            for row in exported["records"]["preferences"]}
    assert exported_preferences["home.preferences"] == {"doctor_name": "Ada", "revision": 2}
    assert "home.suggestions" not in exported_preferences
    assert "home.preference_commands" not in exported_preferences
    target = create_app(tmp_path / "synthetic-restored-profile").state.services
    restore_records(target, exported, confirm_older=True)
    assert target.registry["home"].preferences() == {"doctor_name": "Ada", "revision": 2}
    assert target.db.fetch_one("SELECT 1 FROM preferences WHERE key IN ('home.suggestions','home.preference_commands')") is None
    assert target.registry["home"].read()["suggestions"] is None
    assert len(transport.calls) == 1


def test_home_router_refresh_uses_real_provider_manager_and_real_jobs(home):
    app, service, transport = home
    with TestClient(app) as client:
        started = client.post("/api/v1/home/suggestions/refresh", headers={"Idempotency-Key": "synthetic-home-open"})
        assert started.status_code == 202 and started.headers["cache-control"] == "no-store"
        for _ in range(80):
            state = client.get("/api/v1/home").json()
            if state["job"]["state"] == "published":
                break
        assert state["suggestions"] == bundle()
        assert client.post("/api/v1/home/suggestions/refresh", headers={"Idempotency-Key": "synthetic-home-open2"}).json()["job_id"] == started.json()["job_id"]
        assert len(transport.calls) == 1
        job = service.db.fetch_one("SELECT checkpoint_json,validated_count FROM assessment_test_jobs")
        assert json.loads(job["checkpoint_json"]) == {}
        assert job["validated_count"] == 15


def test_malformed_imported_name_uses_generic_welcome_preference(home):
    _, service, _ = home
    service.db.execute("INSERT INTO preferences VALUES('home.preferences',?,?)",
        (json.dumps({"doctor_name": ["not a name"], "revision": 1}), utc_now()))
    assert service.preferences() == {"doctor_name": None, "revision": 1}


@pytest.mark.asyncio
async def test_restart_and_cancellation_do_not_resume_provider_work(home):
    app, service, transport = home
    transport.release = asyncio.Event()
    await service.refresh()
    await transport.started.wait()
    await service.close()
    row = service.db.fetch_one("SELECT state FROM assessment_test_jobs")
    assert row["state"] == "cancelled"
    restarted = HomeService(app.state.services, local_now=service.local_now)
    restarted.recover()
    await restarted.refresh()
    assert len(transport.calls) == 1
    assert restarted._task is None
