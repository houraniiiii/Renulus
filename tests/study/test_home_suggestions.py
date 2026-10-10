# SPDX-License-Identifier: MIT
"""Owned synthetic Home checks; no live inference, credentials or owner profile."""
import json
import asyncio
import os
from copy import deepcopy
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
    monkeypatch.setattr("renulus.server.MODULE_ORDER", ("runtime", "content", "knowledge", "learn", "cases", "assessment", "memory", "study", "updates"))
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


class SyntheticHomeReviewedContent:
    """Original contract adapter; the real collection/attempt owners produce evidence."""
    def __init__(self):
        self.question = {
            "id": "home_renal_question", "version": 1, "key_version": 1,
            "family_id": "home_renal_family", "family_version": 1, "topic_id": "T01",
            "stem": "PRIVATE_HOME_REVIEWED_STEM", "kind": "single_best_answer",
            "usage": "assessment_reserved", "objective_ids": ["T01-objective"],
            "options": [{"id": "a", "text": "Original synthetic option A"},
                        {"id": "b", "text": "Original synthetic option B"}],
            "correct_option_ids": ["a"], "explanation": "PRIVATE_HOME_REVIEWED_KEY",
            "sources": [{"source_id": "home-original", "locator": "Synthetic section"}],
            "difficulty": "foundation", "withdrawn": False, "current_version": 1,
            "review": {"status": "assistant_reviewed", "source_key_checked": True},
        }

    def list_question_summaries(self, **_):
        fields = ("id", "version", "key_version", "family_id", "family_version",
                  "topic_id", "objective_ids", "difficulty", "usage", "review")
        return [{field: deepcopy(self.question[field]) for field in fields}]

    def get_question_version(self, identifier, version):
        assert (identifier, version) == (self.question["id"], 1)
        return deepcopy(self.question)


@pytest.fixture
def home_whole(home):
    from renulus.assessment.test_models import CreateReviewedTestRequest
    from renulus.assessment.attempt_models import StartAttempt

    app, service, transport = home
    services = app.state.services
    services.registry["content"] = SyntheticHomeReviewedContent()
    saved = services.get("saved_tests").create_reviewed(CreateReviewedTestRequest(
        idempotency_key="home-whole-reviewed", title="Original synthetic renal learning", count=1))
    owner = services.get("whole_attempts")
    attempt = owner.start(StartAttempt(version={"type": "saved_test_version", "id": saved["version_id"]},
                                      mode="study", timing={"kind": "untimed"}), "home-whole-start")
    return service, transport, owner, attempt, saved


def home_whole_commit(owner, attempt, *, key="home-whole-commit", option="a"):
    from renulus.assessment.attempt_models import CommitAnswer

    return owner.commit_answer(attempt["id"], CommitAnswer(
        expected_revision=attempt["draft_revision"], item_id=attempt["current_item"]["item_id"],
        option_ids=[option]), key)


@pytest.mark.asyncio
async def test_whole_attempt_reviewed_commit_enters_home_only_as_safe_scalar_activity(home_whole):
    service, transport, owner, attempt, _ = home_whole
    home_whole_commit(owner, attempt)
    with service.db.transaction() as conn:
        context = service._context(conn)
    assert len(context.material["learning_activity"]) == 1
    activity = context.material["learning_activity"][0]
    assert activity["topic_id"] == "T01" and activity["correct"] is True
    assert activity["reviewed"] is True and activity["bank_cohort_eligible"] is True
    assert activity["assisted"] is False and activity["repeat"] is False
    assert activity["mode"] == "study" and activity["score_bucket"] == "fresh"
    evidence = service.db.fetch_one("SELECT id FROM learning_evidence WHERE kind='assessment-test-answer'")
    assert any(pin.dependency.target.id == evidence["id"] for pin in context.inputs)
    await service.refresh()
    assert (await finish(service))["suggestions"]
    sent = json.dumps(transport.calls)
    assert "PRIVATE_HOME_REVIEWED" not in sent and "correct_option_ids" not in sent
    assert "home_renal_question" not in sent and attempt["id"] not in sent


def test_whole_attempt_pending_draft_and_reserved_bank_content_are_not_home_activity(home_whole):
    from renulus.assessment.attempt_models import SaveDraft

    service, _, owner, attempt, _ = home_whole
    owner.save(attempt["id"], SaveDraft(expected_revision=0, position=0, answers=[{
        "item_id": attempt["current_item"]["item_id"], "option_ids": ["a"], "marked": False,
    }]), "home-pending-draft")
    assert not service.db.fetch_all("SELECT id FROM learning_evidence")
    with service.db.transaction() as conn:
        context = service._context(conn)
    assert context.material["learning_activity"] == []
    assert "PRIVATE_HOME_REVIEWED" not in json.dumps(context.material)


def test_whole_attempt_unanswered_test_result_does_not_become_home_mistake(home_whole):
    from renulus.assessment.attempt_models import StartAttempt, SubmitAttempt

    service, _, owner, _, saved = home_whole
    attempt = owner.start(StartAttempt(version={"type": "saved_test_version", "id": saved["version_id"]},
                                      mode="test"), "home-blank-test")
    result = owner.submit(attempt["id"], SubmitAttempt(expected_draft_revision=0), "home-submit-blank")
    assert result["result"]["unanswered"] == 1
    payload = json.loads(service.db.fetch_one("SELECT payload_json FROM learning_evidence")["payload_json"])
    assert payload["outcome"] == "unanswered"
    with service.db.transaction() as conn:
        assert service._context(conn).material["learning_activity"] == []


def test_whole_attempt_personal_edit_of_reviewed_origin_keeps_personal_cohort(home_whole):
    from renulus.assessment.test_models import EditTestVersionRequest
    from renulus.assessment.attempt_models import StartAttempt

    service, _, owner, _, saved = home_whole
    repository = service.services.get("saved_tests")
    items = repository.preview_version(saved["test_id"], saved["version_id"])["items"]
    # Explicit original synthetic personal keys, not a read of reviewed private keys.
    items[0].update(correct_option_ids=["b"], explanation="Original synthetic personal explanation")
    personal = repository.edit_version(saved["test_id"], EditTestVersionRequest(
        expected_revision=1, base_version_id=saved["version_id"], items=items, idempotency_key="home-personal-edit"))
    attempt = owner.start(StartAttempt(version={"type": "saved_test_version", "id": personal["version_id"]}),
                          "home-personal-study")
    home_whole_commit(owner, attempt, option="b")
    with service.db.transaction() as conn:
        activities = service._context(conn).material["learning_activity"]
    assert len(activities) == 1
    activity = activities[0]
    assert activity["origin"] == "reviewed_bank" and activity["review_quality"] == "personal"
    assert activity["score_bucket"] == "personal"
    assert activity["reviewed"] is False and activity["bank_cohort_eligible"] is False


def test_whole_attempt_assisted_repeat_keeps_both_flags_in_home_activity(home_whole):
    from renulus.assessment.attempt_models import HelpRequest, StartAttempt

    service, _, owner, _, saved = home_whole
    repeat = owner.start(StartAttempt(version={"type": "saved_test_version", "id": saved["version_id"]}),
                         "home-repeat-study")
    assert repeat["current_item"]["repeat"] is True
    owner.help(repeat["id"], HelpRequest(expected_revision=0, expected_policy_revision=repeat["policy"]["revision"],
               item_id=repeat["current_item"]["item_id"], kind="sources"), "home-repeat-sources")
    home_whole_commit(owner, repeat)
    with service.db.transaction() as conn:
        activity = service._context(conn).material["learning_activity"][0]
    assert activity["score_bucket"] == "repeat"
    assert activity["assisted"] is True and activity["repeat"] is True


@pytest.mark.parametrize("change", ["forged_commit", "extra_private_field", "cohort_flip",
                                    "evidence_copy", "attempt_deleted", "suppressed"])
def test_whole_attempt_home_rejects_untrusted_or_unavailable_evidence(home_whole, change):
    service, _, owner, attempt, _ = home_whole
    home_whole_commit(owner, attempt)
    evidence = service.db.fetch_one("SELECT * FROM learning_evidence WHERE kind='assessment-test-answer'")
    value = json.loads(evidence["payload_json"])
    if change == "forged_commit":
        value["commit_id"] = "not-a-canonical-commit"
    elif change == "extra_private_field":
        value["raw_test_key"] = "PRIVATE_HOME_FORGED_KEY"
    elif change == "cohort_flip":
        value["bank_cohort_eligible"] = False
    elif change == "evidence_copy":
        service.db.execute("INSERT INTO learning_evidence VALUES(?,?,?,?,?,?)",
            ("unmatched-evidence-copy", evidence["kind"], evidence["topic_id"], evidence["entity_id"],
             evidence["payload_json"], utc_now()))
        service.db.execute("DELETE FROM learning_evidence WHERE id=?", (evidence["id"],))
    elif change == "attempt_deleted":
        service.db.mark_deleted("test_attempt", attempt["id"])
    else:
        service.db.execute("INSERT INTO memory_suppression VALUES(?,?)", ("evidence:" + evidence["id"], utc_now()))
    if change in ("forged_commit", "extra_private_field", "cohort_flip"):
        service.db.execute("UPDATE learning_evidence SET payload_json=? WHERE id=?", (json.dumps(value), evidence["id"]))
    with service.db.transaction() as conn:
        context = service._context(conn)
    assert context.material["learning_activity"] == []
    assert not context.inputs


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["suppressed", "attempt_deleted", "source_withdrawn", "evidence_revision"])
@pytest.mark.parametrize("stage", ["during_provider", "cache_read"])
async def test_whole_attempt_source_and_suppression_rechecked_at_publication_and_cache(home_whole, change, stage):
    service, transport, owner, attempt, _ = home_whole
    home_whole_commit(owner, attempt)
    evidence = service.db.fetch_one("SELECT id FROM learning_evidence WHERE kind='assessment-test-answer'")
    if stage == "during_provider":
        transport.release = asyncio.Event()
    await service.refresh()
    await asyncio.wait_for(transport.started.wait(), timeout=5)
    if stage == "cache_read":
        assert (await finish(service))["suggestions"] == bundle()
    if change == "suppressed":
        service.db.execute("INSERT INTO memory_suppression VALUES(?,?)", ("evidence:" + evidence["id"], utc_now()))
    elif change == "attempt_deleted":
        service.db.mark_deleted("test_attempt", attempt["id"])
    elif change == "source_withdrawn":
        service.services.get("content").question["withdrawn"] = True
    else:
        # Even unchanged safe scalars cannot reuse a digest for a changed canonical row.
        service.db.execute("UPDATE learning_evidence SET created_at=? WHERE id=?",
                           ("2026-10-10T20:00:00Z", evidence["id"]))
    if stage == "during_provider":
        transport.release.set()
        result = await finish(service)
        assert result["job"]["state"] == "failed"
        assert result["job"]["error_code"] == "dependency_changed"
        assert service.db.fetch_one("SELECT 1 FROM preferences WHERE key='home.suggestions'") is None
    assert service.read()["suggestions"] is None
    sent = json.dumps(transport.calls)
    assert "PRIVATE_HOME_REVIEWED" not in sent and attempt["id"] not in sent


@pytest.mark.skipif(os.environ.get("RENULUS_HOME_CONNECTED") != "1",
                    reason="Opt-in assembled loopback renderer/SQLite consumer proof")
def test_actual_default_home_renderer_saved_five_study_and_lost_ack_replay(home):
    import runpy
    import shutil
    import socket
    import subprocess
    import threading
    import time
    from pathlib import Path
    import uvicorn
    from renulus.learn.chat_test_api import create_router
    from renulus.storage.backup import export_records

    app, service, home_transport = home
    services = app.state.services
    if "chat_tests" not in services.registry:
        app.include_router(create_router(services), prefix="/api/v1")
    services.on_shutdown.append(services.get("chat_tests").close)
    root = Path(__file__).resolve().parents[2]
    # Reuse the owner-published original synthetic subscription transport.
    fictional_type = runpy.run_path(str(root / "tests/integration/test_design_c_chat_tests.py"))["FictionalTransport"]
    fictional_transport = fictional_type()

    class ConnectedTransport:
        async def stream(self, provider, model, token, messages):
            assert (provider, model, token) == ("codex", "gpt-6.1-sol", "synthetic-home-token")
            payload = json.loads(messages[-1]["content"])
            if "learning_activity" in payload:
                async for event in home_transport.stream(provider, model, token, messages):
                    yield event
            else:
                async for event in fictional_transport.stream(provider, model, "synthetic-chat-test-token", messages):
                    yield event

    services.get("provider")._transport = ConnectedTransport()
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    worker = threading.Thread(target=server.run, daemon=True)
    worker.start()
    deadline = time.monotonic() + 15
    while not server.started and worker.is_alive() and time.monotonic() < deadline:
        time.sleep(0.05)
    try:
        assert server.started, "Owned loopback app did not start"
        node = shutil.which("node")
        assert node, "Existing Node runtime required"
        receipt = Path("C:/Renulus/scratch/design-c/home/home-connected01.xml")
        receipt.parent.mkdir(parents=True, exist_ok=True)
        process = subprocess.run([node, "node_modules/vitest/vitest.mjs", "run",
            "src/modules/home/home.connected.test.tsx", "--reporter=default", "--reporter=junit",
            "--outputFile=" + str(receipt)], cwd=root / "apps/desktop",
            env={**os.environ, "RENULUS_HOME_TEST_ORIGIN": f"http://127.0.0.1:{port}"},
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        (receipt.parent / "home-connected-stdout.txt").write_text(process.stdout + process.stderr, encoding="utf-8")
        assert process.returncode == 0, process.stdout + process.stderr
        assert len(fictional_transport.calls) == 4  # Two original batches and their separate reviews.
        assert len(services.db.fetch_all("SELECT * FROM assessment_test_versions")) == 2
        assert len(services.db.fetch_all("SELECT * FROM assessment_test_attempts")) == 2
        assert len(services.db.fetch_all("SELECT * FROM assessment_attempt_commands WHERE operation='start'")) == 2
        assert len(services.db.fetch_all("SELECT * FROM learning_evidence WHERE kind='assessment-test-answer'")) == 1
        assert len(services.db.fetch_all("SELECT * FROM assessment_test_jobs WHERE operation='daily_suggestions'")) == 1
        assert not services.db.fetch_all("SELECT * FROM assessment_test_jobs WHERE operation != 'daily_suggestions'")
        assert not services.db.fetch_all("SELECT * FROM memory_jobs")
        marker = b"HOME_VOLATILE_ORIGINAL_SOURCE_8FA0"
        assert marker.decode() not in json.dumps(export_records(services))
        assert all(marker not in path.read_bytes() for path in services.paths.root.rglob("*") if path.is_file())
        assert all(run.source_text == "" and run.source is None for run in services.get("chat_tests").runs.values())
    finally:
        server.should_exit = True
        worker.join(timeout=15)
        assert not worker.is_alive(), "Owned loopback backend must stop"
