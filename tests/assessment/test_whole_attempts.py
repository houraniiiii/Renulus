# SPDX-License-Identifier: MIT
"""Actual collection → whole-attempt router → SQLite; no provider or fixture DDL."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from renulus.assessment.attempt_api import create_router
from renulus.assessment.attempt_models import StartAttempt, SubmitAttempt
from renulus.assessment.attempt_repository import WholeAttemptRepository
from renulus.contracts import ApiError
from renulus.design_c_contracts import SavedTestVersion
from renulus.assessment.test_api import create_router as collection_router
from renulus.services import Services
from renulus.storage import Database
from renulus.storage.relations import reconcile_unavailable_references

BASE = "/api/v1/assessment/test-attempts"


@pytest.fixture(autouse=True)
def assessment_modules(monkeypatch, tmp_path):
    # Exercise the parent's actual full router/policy assembly. The inherited
    # narrow fixture currently cannot construct the new conversation router.
    # No provider endpoints are invoked; helpers are offline and profile-owned.
    monkeypatch.setattr("renulus.server.MODULE_ORDER", ("runtime", "content", "knowledge", "retrieval", "learn", "cases",
                                                       "assessment", "memory", "study", "updates"))
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    monkeypatch.setenv("HF_HOME", str(tmp_path / "offline-helper-cache"))


class Clock:
    def __init__(self):
        self.now = datetime(2026, 10, 10, 12, tzinfo=timezone.utc)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += timedelta(seconds=seconds)


@pytest.fixture
def whole(app):
    services = app.state.services
    root = Path(os.environ.get("RENULUS_ATTEMPT_MIGRATIONS", Path(__file__).parents[2] / "runtime/renulus/assessment/migrations"))
    for ordinal in ("003", "004"):
        migration = root / (ordinal + ".sql")
        assert migration.is_file(), "Integrate parent migration" + ordinal + " before persistence acceptance"
        services.db.apply_migration("assessment-" + ordinal, migration.read_text(encoding="utf-8"))
    if "saved_tests" not in services.registry:
        app.include_router(collection_router(services), prefix="/api/v1")
    if "whole_attempts" not in services.registry:
        app.include_router(create_router(services), prefix="/api/v1")
    clock = Clock()
    repository = services.get("whole_attempts")
    repository.clock, repository.monotonic = clock, lambda: 0
    with TestClient(app) as client:
        response = client.post("/api/v1/assessment/tests/reviewed", json={
            "idempotency_key": "synthetic-version-1", "title": "Synthetic mixed nephrology", "count": 3})
        assert response.status_code == 200, response.text
        yield client, services, clock, response.json()["version_id"]


def post(client, attempt, action, body, key):
    return client.post(BASE + "/" + attempt["id"] + "/" + action, json=body, headers={"Idempotency-Key": key})


def start(whole, mode="study", seconds=None, key="start-attempt-1"):
    client, _, _, version_id = whole
    timing = {"kind": "untimed"} if seconds is None else {"kind": "timed", "duration_seconds": seconds}
    response = client.post(BASE, json={"version": {"type": "saved_test_version", "id": version_id}, "mode": mode, "timing": timing},
                           headers={"Idempotency-Key": key})
    assert response.status_code == 201, response.text
    return response.json()


def draft(attempt, *, position=None, first="a"):
    return {"position": attempt["position"] if position is None else position,
            "answers": [{**answer, "option_ids": [first] if index == 0 and first else answer["option_ids"]}
                        for index, answer in enumerate(attempt["answers"])]}


def save(client, attempt, state=None, key="save-draft-1"):
    return client.put(BASE + "/" + attempt["id"] + "/draft", headers={"Idempotency-Key": key},
                      json={"expected_revision": attempt["draft_revision"], **(state or draft(attempt))})


def commit(client, attempt, option="a", key="commit-answer-1"):
    return post(client, attempt, "submit-answer", {"expected_revision": attempt["draft_revision"],
                "item_id": attempt["current_item"]["item_id"], "option_ids": [option]}, key)


def finish(client, attempt, latest=None, key="final-submit-1"):
    return post(client, attempt, "submit", {"expected_draft_revision": attempt["draft_revision"], "latest_draft": latest}, key)


def test_study_draft_explicit_commit_reopen_locks_and_idempotency(whole):
    client, services, clock, _ = whole
    attempt = start(whole)
    assert "correct_option_ids" not in json.dumps(attempt)
    assert len(services.db.fetch_all("SELECT * FROM assessment_attempt_exposure")) == 1
    saved = save(client, attempt).json()
    assert saved["committed"] == [] and services.db.fetch_all("SELECT * FROM learning_evidence") == []
    assert client.get(BASE + "/" + attempt["id"]).json()["answers"][0]["option_ids"] == ["a"]
    result = commit(client, saved)
    assert result.status_code == 200, result.text
    assert commit(client, saved).json() == result.json()
    assert commit(client, saved, option="b").json()["error"]["code"] == "idempotency_conflict"
    locked = result.json()
    assert locked["committed"][0]["feedback"]["explanation"] == "PRIVATE_REVIEWED_KEY_SENTINEL"
    changed = draft(locked, first="b")
    assert save(client, locked, changed, "change-locked-1").json()["error"]["code"] == "answer_locked"
    restarted = WholeAttemptRepository(services, clock=clock, monotonic=lambda: 0).get(attempt["id"])
    assert restarted["committed"] == locked["committed"]
    assert len(services.db.fetch_all("SELECT * FROM learning_evidence")) == 1
    evidence = services.db.fetch_one("SELECT * FROM learning_evidence")
    assert evidence["kind"] == "assessment-test-answer" and evidence["entity_id"] == attempt["id"]
    assert "PRIVATE_" not in evidence["payload_json"] and "correct_option_ids" not in evidence["payload_json"]
    assert json.loads(evidence["payload_json"])["bank_cohort_eligible"] is True


def test_empty_commit_next_presentation_and_study_finish_do_not_grade_draft(whole):
    client, services, _, _ = whole
    attempt = start(whole)
    empty = post(client, attempt, "submit-answer", {"expected_revision": 0, "item_id": attempt["current_item"]["item_id"], "option_ids": []}, "empty-answer-1")
    assert empty.status_code == 422
    assert save(client, attempt, draft(attempt, position=1)).json()["error"]["code"] == "answer_required"
    committed = commit(client, attempt).json()
    moved = save(client, committed, draft(committed, position=1), "move-next-question").json()
    assert moved["current_item"] is None  # No question returned before presentation.
    response = post(client, moved, "present", {"expected_revision": moved["draft_revision"],
                                              "item_id": moved["answers"][1]["item_id"]}, "present-question-2")
    assert response.status_code == 200, response.text
    assert response.json()["current_item"]["item_id"] == moved["answers"][1]["item_id"]
    final = finish(client, response.json()).json()
    assert final["result"]["denominator"] == 1 and final["result"]["not_submitted"] == 2
    assert len(services.db.fetch_all("SELECT * FROM learning_evidence")) == 1


def test_help_records_before_return_survives_restart_and_late_context_is_refused(whole):
    client, services, clock, _ = whole
    attempt = start(whole)
    body = {"expected_revision": 0, "expected_policy_revision": attempt["policy"]["revision"],
            "item_id": attempt["current_item"]["item_id"], "kind": "sources"}
    help_result = post(client, attempt, "help", body, "source-help-1")
    assert help_result.status_code == 200, help_result.text
    assert services.db.fetch_one("SELECT kind FROM assessment_attempt_exposure WHERE kind='sources'")
    assert "PRIVATE_" not in help_result.text
    restarted = WholeAttemptRepository(services, clock=clock, monotonic=lambda: 0)
    assert restarted.get(attempt["id"])["draft_revision"] == 0
    committed = commit(client, attempt).json()
    assert committed["committed"][0]["assisted"] is True
    assert committed["committed"][0]["score_bucket"] == "assisted"
    assert post(client, committed, "help", body, "source-help-1").status_code == 409


def test_repeat_is_frozen_when_first_presented_not_recomputed_at_commit(whole):
    client, _, _, _ = whole
    first = start(whole)
    second = start(whole, key="start-attempt-2")
    assert first["current_item"]["repeat"] is False and second["current_item"]["repeat"] is True
    assert commit(client, first).json()["committed"][0]["repeat"] is False


def test_test_latest_draft_atomic_blank_counts_and_terminal_result(whole):
    client, services, _, _ = whole
    attempt = start(whole, "test")
    assert attempt["policy"]["active_test_id"] == attempt["id"]
    assert post(client, attempt, "pause", {"expected_revision": 0}, "pause-test-refused").status_code == 409
    saved = save(client, attempt).json()
    assert saved["result"] is None and saved["committed"] == []
    assert services.db.fetch_all("SELECT * FROM learning_evidence") == []
    latest = draft(saved, first="b")
    final = finish(client, saved, latest)
    assert final.status_code == 200, final.text
    result = final.json()
    assert result["result"]["correct"] == 0 and result["result"]["unanswered"] == 2
    assert result["result"]["denominator"] == 3 and result["answers"][0]["option_ids"] == ["b"]
    assert result["policy"]["assistance_allowed"] is True
    assert finish(client, saved, latest).json() == result
    assert save(client, saved, key="late-save-refused").status_code == 409
    assert len(services.db.fetch_all("SELECT * FROM learning_evidence")) == 3
    assert client.get(BASE + "/" + attempt["id"]).json()["result"] == result["result"]


def test_evidence_failure_rolls_back_whole_test_and_releases_no_policy(whole):
    client, services, _, _ = whole
    attempt = start(whole, "test")
    services.db.execute("CREATE TRIGGER synthetic_evidence_failure BEFORE INSERT ON learning_evidence BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END")
    failed = finish(client, attempt, draft(attempt))
    assert failed.status_code == 503 and "synthetic failure" not in failed.text
    row = services.db.fetch_one("SELECT * FROM assessment_test_attempts")
    assert row["status"] == "active" and row["result_json"] is None and row["committed_json"] == "[]"
    assert services.db.fetch_all("SELECT * FROM learning_evidence") == []
    assert client.get("/api/v1/assessment/policy").json()["assistance_allowed"] is False
    services.db.execute("DROP TRIGGER synthetic_evidence_failure")
    assert finish(client, attempt, draft(attempt)).status_code == 200


def test_profile_gate_precedes_old_feedback_and_command_replay(whole):
    client, _, _, _ = whole
    study = start(whole)
    assert commit(client, study).status_code == 200
    active_test = start(whole, "test", key="start-test-blocker")
    replay = commit(client, study)
    assert replay.status_code == 409 and "PRIVATE_" not in replay.text
    assert client.get(BASE + "/" + study["id"]).status_code == 409
    assert finish(client, active_test).status_code == 200
    assert commit(client, study).status_code == 200


def test_stale_save_finalisation_and_two_submit_requests_do_not_duplicate(whole):
    client, services, _, _ = whole
    attempt = start(whole, "test")
    saved = save(client, attempt).json()
    assert save(client, attempt, draft(attempt, first="b"), "stale-save-2").status_code == 409
    assert finish(client, attempt).json()["error"]["code"] == "saving_incomplete"
    request = SubmitAttempt(expected_draft_revision=saved["draft_revision"])
    repository = services.get("whole_attempts")
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda key: repository.submit(attempt["id"], request, key), ("final-concurrent-1", "final-concurrent-2")))
    assert responses[0]["result"] == responses[1]["result"]
    assert len(services.db.fetch_all("SELECT * FROM learning_evidence")) == 3


def test_timed_test_expiry_uses_durable_draft_on_restart_and_late_save_cannot_undo(whole):
    client, services, clock, _ = whole
    attempt = start(whole, "test", seconds=30)
    saved = save(client, attempt).json()
    clock.advance(30)
    restarted = WholeAttemptRepository(services, clock=clock, monotonic=lambda: 0)
    final = restarted.get(attempt["id"])
    assert final["result"]["reason"] == "deadline" and final["result"]["correct"] == 1
    assert final["result"]["unanswered"] == 2
    assert save(client, saved, draft(saved, first="b"), "past-deadline-save").status_code == 409
    assert services.db.fetch_one("SELECT result_json FROM assessment_test_attempts")["result_json"] == json.dumps(final["result"], sort_keys=True, separators=(",", ":"))


def test_study_pause_expiry_and_continue_untimed_preserve_unsubmitted_selection(whole):
    client, services, clock, _ = whole
    attempt = start(whole, seconds=30)
    saved = save(client, attempt).json()
    paused = post(client, saved, "pause", {"expected_revision": 1}, "pause-study-1").json()
    clock.advance(40)
    assert client.get(BASE + "/" + attempt["id"]).json()["status"] == "paused"
    resumed = post(client, paused, "resume", {"expected_revision": 1}, "resume-study-1").json()
    assert resumed["timing"]["paused_seconds"] == 40
    clock.advance(30)
    expired = client.get(BASE + "/" + attempt["id"]).json()
    assert expired["status"] == "timer_expired" and expired["answers"][0]["option_ids"] == ["a"]
    assert expired["committed"] == [] and services.db.fetch_all("SELECT * FROM learning_evidence") == []
    continued = post(client, expired, "continue-untimed", {"expected_revision": 1}, "continue-study-1").json()
    assert continued["status"] == "active" and continued["timing"]["kind"] == "untimed"


def test_restart_clock_rollback_expires_conservatively(whole):
    _, services, clock, _ = whole
    attempt = start(whole, "test", seconds=30)
    clock.advance(10)
    services.get("whole_attempts").get(attempt["id"])
    clock.advance(-20)
    restarted = WholeAttemptRepository(services, clock=clock, monotonic=lambda: 0)
    assert restarted.get(attempt["id"])["result"]["reason"] == "deadline"


def test_invalid_pinned_content_excludes_and_finalises_instead_of_stranding(whole, content):
    client, services, _, _ = whole
    attempt = start(whole, "test")
    content.withdraw(attempt["current_item"]["question_id"])
    result = finish(client, attempt, draft(attempt)).json()
    assert result["status"] == "submitted" and result["result"]["excluded"] == 1
    assert result["result"]["denominator"] == 2
    assert len(services.db.fetch_all("SELECT * FROM learning_evidence")) == 2


def test_report_and_result_retain_snapshot_when_live_collection_disappears(whole):
    client, services, clock, version_id = whole
    attempt = start(whole)
    item_id = attempt["current_item"]["item_id"]
    committed = commit(client, attempt).json()
    result = finish(client, committed).json()["result"]
    with services.db.transaction() as conn:
        conn.execute("DELETE FROM assessment_test_versions WHERE id=?", (version_id,))
        reconcile_unavailable_references(conn)
    report = post(client, attempt, "reports", {"item_id": item_id, "report_text": "Synthetic uncertainty"}, "question-report-1")
    assert report.status_code == 201 and set(report.json()) == {"id", "status", "created_at"}
    assert post(client, attempt, "reports", {"item_id": item_id, "report_text": "Synthetic uncertainty"}, "question-report-1").json() == report.json()
    reopened_services = Services(services.paths, Database(services.paths.database))
    reopened = WholeAttemptRepository(reopened_services, clock=clock, monotonic=lambda: 0).get(attempt["id"])
    assert reopened["provenance_unavailable"] and reopened["result"] == result
    row = services.db.fetch_one("SELECT * FROM assessment_question_reports")
    assert row["live_version_id"] is None and row["version_id"] == version_id
    assert json.loads(row["question_snapshot_json"])["provenance"]["item"]["item_id"] == item_id
    snapshot = json.loads(services.db.fetch_one("SELECT version_snapshot_json FROM assessment_test_attempts")["version_snapshot_json"])
    assert snapshot["schema"] == "whole-attempt-snapshot/1" and snapshot["pinned_provenance"]["items"]


def test_shared_reconcile_callback_advances_policy_and_late_help_context_refuses(whole):
    client, services, clock, _ = whole
    study = start(whole)
    receipt = post(client, study, "help", {"expected_revision": 0, "expected_policy_revision": study["policy"]["revision"],
                   "item_id": study["current_item"]["item_id"], "kind": "hint"}, "pinned-authored-hint").json()
    assert receipt["hint"] == "An original synthetic hint" and "PRIVATE_" not in json.dumps(receipt)
    repository = services.get("whole_attempts")
    with services.db.transaction() as conn:
        assert repository.require_help_context_in(conn, receipt["context"]) == study["policy"]["revision"]
    test = start(whole, "test", seconds=10, key="start-expiring-test")
    clock.advance(10)
    repository.reconcile_all()
    policy = client.get("/api/v1/assessment/policy").json()
    assert policy["assistance_allowed"] and policy["revision"] == test["policy"]["revision"] + 1
    with services.db.transaction() as conn, pytest.raises(ApiError):
        repository.require_help_context_in(conn, receipt["context"])
    repository.reconcile_all()
    assert client.get("/api/v1/assessment/policy").json() == policy


def test_same_process_rollback_uses_monotonic_and_never_rewinds_commit_timestamp(whole):
    client, services, clock, _ = whole
    ticks = [0]
    repository = services.get("whole_attempts")
    repository.monotonic = lambda: ticks[0]
    attempt = start(whole, seconds=30)
    ticks[0] = 10
    clock.advance(-20)
    observed = repository.get(attempt["id"])
    assert observed["status"] == "active" and observed["timing"]["remaining_seconds"] == 20
    committed = commit(client, observed).json()["committed"][0]
    assert committed["committed_at"] == "2026-10-10T12:00:10.000000+00:00"
    assert committed["question"]["stem"] and committed["question"]["options"]
    assert "correct_option_ids" not in committed["question"]


def test_archived_collection_cannot_start_and_repeat_receipt_survives_repository_restart(whole):
    client, services, clock, version_id = whole
    first = start(whole)
    start(whole, key="second-study-exposure")
    reopened = WholeAttemptRepository(services, clock=clock, monotonic=lambda: 0).get(first["id"])
    assert reopened["current_item"]["repeat"] is False
    receipt = services.db.fetch_one("SELECT result_json FROM assessment_attempt_commands WHERE operation='presentation' AND target_id=?", (first["id"],))
    assert json.loads(receipt["result_json"])["repeat"] is False
    services.db.execute("UPDATE assessment_tests SET lifecycle='archived'")
    response = client.post(BASE, json={"version": {"type": "saved_test_version", "id": version_id}}, headers={"Idempotency-Key": "archive-start-refused"})
    assert response.status_code == 409 and response.json()["error"]["code"] == "test_not_active"


def test_personal_edited_bank_origin_never_becomes_reviewed_by_selecting_test_mode(whole):
    client, services, _, version_id = whole
    with services.db.transaction() as conn:
        version = services.get("saved_tests").pinned_version(conn, version_id)
    edited = client.post("/api/v1/assessment/tests/" + version.test_id + "/versions", json={"idempotency_key": "synthetic-personal-edit",
        "expected_revision": 1, "base_version_id": version_id, "items": [item.model_dump(mode="json") for item in version.items]})
    assert edited.status_code == 200, edited.text
    response = client.post(BASE, json={"version": {"type": "saved_test_version", "id": edited.json()["version_id"]}, "mode": "test"},
                           headers={"Idempotency-Key": "start-personal-test"})
    assert response.status_code == 201, response.text
    attempt = response.json()
    final = finish(client, attempt, draft(attempt)).json()["result"]
    assert final["origin"] == "reviewed_bank" and final["review_quality"] == "personal"
    assert final["cohorts"]["personal"]["denominator"] == 3 and final["cohorts"]["fresh"]["denominator"] == 0
    payloads = [json.loads(row["payload_json"]) for row in services.db.fetch_all("SELECT * FROM learning_evidence")]
    assert all(not payload["reviewed"] and not payload["bank_cohort_eligible"] for payload in payloads)


@pytest.mark.parametrize("origin,method", [("generated", "generation"), ("imported", "import"), ("nightly", "nightly")])
def test_published_personal_origins_keep_mode_and_eligibility_separate(whole, origin, method):
    """Consumer contract only: trusted synthetic publication, no origin producer/model substitute."""
    client, services, _, source_id = whole
    repository = services.get("saved_tests")
    with services.db.transaction() as conn:
        raw = repository.pinned_version(conn, source_id).model_dump(mode="json")
        raw.update(id="synthetic_" + origin + "_version", test_id="synthetic_" + origin + "_test",
                   origin=origin, review_quality="personal", provenance={"method": method})
        for index, item in enumerate(raw["items"]):
            item.update(item_id=origin + "_item_" + str(index), question_id=origin + "_question_" + str(index),
                        family_id=origin + "_family_" + str(index), stem="Original synthetic consumer question " + str(index))
        version = SavedTestVersion.model_validate(raw)
        repository.publish_version(conn, version, title="Original synthetic " + origin,
            provenance={"schema": "saved-test-provenance/1", "consumer_fixture": origin},
            idempotency_key="synthetic-consumer-publish-" + origin)
    setup = client.get("/api/v1/assessment/tests/versions/" + version.id + "/setup")
    assert setup.status_code == 200 and setup.json()["can_start"]
    for mode in ("study", "test"):
        response = client.post(BASE, json={"version": {"type": "saved_test_version", "id": version.id}, "mode": mode},
                               headers={"Idempotency-Key": "start-consumer-" + origin + "-" + mode})
        assert response.status_code == 201, response.text
        attempt = response.json()
        assert attempt["version_id"] == version.id and attempt["origin"] == origin
        if mode == "study":
            committed = commit(client, attempt, key="commit-consumer-" + origin).json()
            final = finish(client, committed, key="finish-consumer-" + origin).json()["result"]
        else:
            final = finish(client, attempt, draft(attempt), key="submit-consumer-" + origin).json()["result"]
        assert final["mode"] == mode and final["review_quality"] == "personal"
        assert final["cohorts"]["personal"]["denominator"] == len(final["items"])
        assert all(final["cohorts"][bucket]["denominator"] == 0 for bucket in ("fresh", "assisted", "repeat"))
        evidence = services.db.fetch_all("SELECT kind,entity_id,payload_json FROM learning_evidence WHERE entity_id=?", (attempt["id"],))
        assert len(evidence) == len(final["items"])
        for row in evidence:
            payload = json.loads(row["payload_json"])
            assert row["kind"] == "assessment-test-answer" and row["entity_id"] == attempt["id"]
            assert payload["mode"] == mode and payload["origin"] == origin and payload["version_id"] == version.id
            assert payload["score_bucket"] == "personal" and not payload["reviewed"] and not payload["bank_cohort_eligible"]
            assert "correct_option_ids" not in payload and "explanation" not in payload
        snapshot = json.loads(services.db.fetch_one("SELECT version_snapshot_json FROM assessment_test_attempts WHERE id=?", (attempt["id"],))["version_snapshot_json"])
        assert snapshot["pinned_provenance"]["consumer_fixture"] == origin


def test_start_refuses_lost_review_attestation_without_creating_partial_attempt(whole, content):
    client, services, _, version_id = whole
    with services.db.transaction() as conn:
        version = services.get("saved_tests").pinned_version(conn, version_id)
    content.versions[(version.items[0].question_id, 1)]["review"]["source_key_checked"] = False
    response = client.post(BASE, json={"version": {"type": "saved_test_version", "id": version_id}}, headers={"Idempotency-Key": "unreviewed-start-refused"})
    assert response.status_code == 409 and response.json()["error"]["code"] == "test_not_ready"
    assert services.db.fetch_all("SELECT * FROM assessment_test_attempts") == []


def test_producer_rechecks_policy_before_serialising_study_feedback(whole, monkeypatch):
    client, services, _, version_id = whole
    study = start(whole)
    assert commit(client, study).status_code == 200
    repository = services.get("whole_attempts")
    original = repository.get
    def racing_read(attempt_id):
        result = original(attempt_id)
        repository.start(StartAttempt(version={"type": "saved_test_version", "id": version_id}, mode="test"), "start-between-read-and-json")
        return result
    monkeypatch.setattr(repository, "get", racing_read)
    response = client.get(BASE + "/" + study["id"])
    assert response.status_code == 409 and "PRIVATE_REVIEWED_KEY_SENTINEL" not in response.text


def test_real_active_test_gates_legacy_routes_and_expiry_is_reconciled_before_help_dispatch(whole):
    client, services, clock, _ = whole
    attempt = start(whole, "test", seconds=30)
    for path in ("/assessment/aggregates", "/assessment/progress", "/assessment/mistakes", "/assessment/sessions",
                 "/assessment/practice/sessions", "/study", "/memory", "/learn/threads", "/cases/saved",
                 "/knowledge/documents", "/content/topics", "/data/export", "/data/backup?format_version=2", "/home"):
        response = client.get("/api/v1" + path)
        assert response.status_code == 409, path
        assert "PRIVATE_" not in response.text
    for path in ("/runtime/runs", "/retrieval/discover", "/data/restore", "/data/backup/restore"):
        assert client.post("/api/v1" + path, json={}).status_code == 409, path
    for path in ("/health", "/assessment/policy", "/connections", "/data/recovery", "/home/preferences"):
        assert client.get("/api/v1" + path).status_code == 200, path
    clock.advance(30)
    assert client.get("/api/v1/content/topics").status_code == 200
    final = client.get(BASE + "/" + attempt["id"]).json()
    assert final["result"]["reason"] == "deadline" and final["result"]["unanswered"] == 3
    assert len(services.db.fetch_all("SELECT * FROM learning_evidence")) == 3


def test_reviewed_single_answer_rejects_multiple_selection_without_committing(whole):
    client, services, _, _ = whole
    attempt = start(whole)
    response = post(client, attempt, "submit-answer", {"expected_revision": 0, "item_id": attempt["current_item"]["item_id"],
                    "option_ids": ["a", "b"]}, "multi-choice-refused")
    assert response.status_code == 422
    assert services.db.fetch_one("SELECT draft_revision,committed_json FROM assessment_test_attempts")["draft_revision"] == 0
    assert services.db.fetch_all("SELECT * FROM learning_evidence") == []
