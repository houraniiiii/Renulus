# SPDX-License-Identifier: MIT
"""Real saved-test router/SQLite checks. All profiles and inputs are synthetic."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from renulus.assessment.test_api import create_router
from renulus.assessment.test_models import CreateReviewedTestRequest
from renulus.assessment.test_repository import legacy_test_ids
from renulus.contracts import ApiError
from renulus.storage.backup import apply_records, export_records


@pytest.fixture
def saved_app(app):
    # Parent's actual migration is required; never substitute fixture DDL.
    services = app.state.services
    assert services.db.fetch_one("SELECT name FROM sqlite_master WHERE name='assessment_test_commands'"), (
        "Prerequisite: integrate parent's assessment-003 migration before persistence acceptance")
    app.include_router(create_router(services), prefix="/api/v1")
    return app


@pytest.fixture
def saved_client(saved_app):
    with TestClient(saved_app) as client:
        yield client


def create(client, *, key="create-reviewed-synthetic", count=2):
    result = client.post("/api/v1/assessment/tests/reviewed", json={"idempotency_key": key, "count": count, "title": "Synthetic mixed practice"})
    assert result.status_code == 200, result.text
    return result.json()


def private_version(app, identifier):
    services = app.state.services
    with services.db.transaction() as conn:
        return services.get("saved_tests").pinned_version(conn, identifier)


def test_public_collection_setup_and_preview_never_disclose_keys(saved_app, saved_client):
    result = create(saved_client)
    paths = ["", "/" + result["test_id"], "/" + result["test_id"] + "/setup",
             "/" + result["test_id"] + "/versions/" + result["version_id"] + "/preview"]
    for path in paths:
        response = saved_client.get("/api/v1/assessment/tests" + path)
        assert response.status_code == 200
        assert "correct_option_ids" not in response.text
        assert "PRIVATE_REVIEWED_KEY_SENTINEL" not in response.text
        assert "PRIVATE_OPTION_RATIONALE" not in response.text
    version = private_version(saved_app, result["version_id"])
    assert version.items[0].correct_option_ids == ("a",)
    assert version.items[0].explanation == "PRIVATE_REVIEWED_KEY_SENTINEL"
    assert saved_client.get("/api/v1/assessment/tests/" + result["test_id"] + "/setup").json()["version"]["item_count"] == 2


def test_retry_and_concurrent_create_publish_exactly_once(saved_app, saved_client):
    result = create(saved_client)
    assert create(saved_client) == result
    services = saved_app.state.services
    repository = services.get("saved_tests")
    request = CreateReviewedTestRequest(idempotency_key="concurrent-synthetic-create", count=1)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: repository.create_reviewed(request), range(2)))
    assert results[0] == results[1]
    assert len(services.db.fetch_all("SELECT id FROM assessment_tests")) == 2
    changed = saved_client.post("/api/v1/assessment/tests/reviewed", json={"idempotency_key": "create-reviewed-synthetic", "count": 1})
    assert changed.status_code == 409 and changed.json()["error"]["code"] == "idempotency_conflict"
    assert services.db.fetch_all("SELECT * FROM learning_evidence") == []


def test_short_reviewed_pool_refuses_silent_shorter_publication(saved_app, saved_client):
    result = saved_client.post("/api/v1/assessment/tests/reviewed", json={"idempotency_key": "too-large-synthetic", "count": 50})
    assert result.status_code == 409 and result.json()["error"]["code"] == "insufficient_coverage"
    assert saved_app.state.services.db.fetch_all("SELECT * FROM assessment_tests") == []


def test_rename_archive_restore_keep_exact_manifest_and_replay(saved_app, saved_client):
    result = create(saved_client)
    path = "/api/v1/assessment/tests/" + result["test_id"]
    db = saved_app.state.services.db
    original = db.fetch_one("SELECT * FROM assessment_test_versions WHERE id=?", (result["version_id"],))
    request = {"idempotency_key": "rename-synthetic", "expected_revision": 1, "title": "Dialysis and CKD review"}
    rename = saved_client.patch(path, json=request)
    assert rename.status_code == 200 and rename.json()["revision"] == 2
    assert saved_client.patch(path, json=request).json() == rename.json()
    archive = saved_client.post(path + "/archive", json={"idempotency_key": "archive-synthetic", "expected_revision": 2})
    assert archive.json()["lifecycle"] == "archived"
    assert saved_client.get("/api/v1/assessment/tests").json()["items"] == []
    assert len(saved_client.get("/api/v1/assessment/tests?lifecycle=archived").json()["items"]) == 1
    assert saved_client.get(path + "/setup").json()["can_start"] is False
    restore = saved_client.post(path + "/restore", json={"idempotency_key": "restore-synthetic", "expected_revision": 3})
    assert restore.json()["lifecycle"] == "active"
    stale = saved_client.patch(path, json={**request, "idempotency_key": "stale-synthetic"})
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "revision_conflict"
    assert db.fetch_one("SELECT * FROM assessment_test_versions WHERE id=?", (result["version_id"],)) == original


def test_edit_creates_personal_version_without_mutating_original(saved_app, saved_client):
    result = create(saved_client)
    original = private_version(saved_app, result["version_id"])
    items = [item.model_dump(mode="json") for item in original.items]
    items[0]["stem"] = "Synthetic personal refinement"
    request = {"idempotency_key": "edit-synthetic", "expected_revision": 1, "base_version_id": original.id, "items": items}
    path = "/api/v1/assessment/tests/" + result["test_id"] + "/versions"
    edit = saved_client.post(path, json=request)
    assert edit.status_code == 200, edit.text
    assert saved_client.post(path, json=request).json() == edit.json()
    changed = private_version(saved_app, edit.json()["version_id"])
    assert changed.ordinal == 2 and changed.review_quality == "personal" and not changed.bank_cohort_eligible
    assert changed.items[0].question_id != original.items[0].question_id
    assert private_version(saved_app, original.id) == original
    forged = saved_client.post(path, json={**request, "idempotency_key": "forged-synthetic", "review_quality": "reviewed"})
    assert forged.status_code == 422


def test_missing_key_personal_edit_stays_needs_review(saved_app, saved_client):
    result = create(saved_client)
    original = private_version(saved_app, result["version_id"])
    items = [item.model_dump(mode="json") for item in original.items]
    items[0]["correct_option_ids"] = []
    edited = saved_client.post("/api/v1/assessment/tests/" + result["test_id"] + "/versions", json={
        "idempotency_key": "missing-key-synthetic", "expected_revision": 1, "base_version_id": original.id, "items": items})
    assert edited.status_code == 200 and edited.json()["status"] == "needs_review"
    setup = saved_client.get("/api/v1/assessment/tests/" + result["test_id"] + "/setup").json()
    assert setup["can_start"] is False and setup["version"]["review_quality"] == "needs_review"


def test_report_retry_conflict_and_snapshot_survive_collection_delete(saved_app, saved_client):
    result = create(saved_client)
    pin = private_version(saved_app, result["version_id"])
    path = "/api/v1/assessment/tests/" + result["test_id"]
    report_path = path + "/versions/" + pin.id + "/reports"
    request = {"idempotency_key": "report-synthetic", "item_id": pin.items[0].item_id, "report_text": "Synthetic question ambiguity"}
    report = saved_client.post(report_path, json=request)
    assert report.status_code == 200 and set(report.json()) == {"id", "status", "created_at"}
    assert saved_client.post(report_path, json=request).json() == report.json()
    assert saved_client.post(report_path, json={**request, "report_text": "Changed text"}).status_code == 409
    deletion = {"idempotency_key": "delete-synthetic", "expected_revision": 1}
    assert saved_client.request("DELETE", path, json=deletion).status_code == 200
    assert saved_client.request("DELETE", path, json=deletion).json()["lifecycle"] == "deleted"
    db = saved_app.state.services.db
    row = db.fetch_one("SELECT * FROM assessment_question_reports")
    assert row["version_id"] == pin.id and row["live_version_id"] is None
    assert json.loads(row["question_snapshot_json"])["question"]["stem"] == pin.items[0].stem
    assert db.is_deleted("saved_test", result["test_id"]) and db.is_deleted("saved_test_version", pin.id)
    assert saved_client.get(path).status_code == 404
    assert db.fetch_all("SELECT * FROM learning_evidence") == []
    # Attempt owner can still report against its independent snapshot after deletion.
    with db.transaction() as conn:
        receipt = saved_app.state.services.get("saved_tests").save_question_report(conn, version=pin,
            attempt_id=None, item_id=pin.items[1].item_id, report_text="Retained snapshot report", idempotency_key="after-delete-synthetic")
    assert receipt["status"] == "saved"


def test_failed_command_record_rolls_back_mutation(saved_app, saved_client):
    result = create(saved_client)
    db = saved_app.state.services.db
    db.execute("CREATE TRIGGER synthetic_record_failure BEFORE INSERT ON assessment_test_commands "
               "WHEN NEW.operation='rename' BEGIN SELECT RAISE(ABORT,'synthetic failure'); END;")
    response = saved_client.patch("/api/v1/assessment/tests/" + result["test_id"], json={
        "idempotency_key": "failed-rename-synthetic", "expected_revision": 1, "title": "Unsaved title"})
    assert response.status_code == 503
    row = db.fetch_one("SELECT * FROM assessment_tests WHERE id=?", (result["test_id"],))
    assert row["revision"] == 1 and row["title"] == "Synthetic mixed practice"
    assert db.fetch_one("SELECT * FROM assessment_test_commands WHERE idempotency_key='failed-rename-synthetic'") is None


def test_cursor_is_bound_to_filters(saved_client):
    create(saved_client, key="first-cursor-synthetic")
    create(saved_client, key="second-cursor-synthetic")
    page = saved_client.get("/api/v1/assessment/tests?limit=1").json()
    assert len(page["items"]) == 1 and page["next_cursor"]
    response = saved_client.get("/api/v1/assessment/tests", params={"limit": 1, "cursor": page["next_cursor"]})
    assert response.status_code == 200 and response.json()["items"][0]["id"] != page["items"][0]["id"]
    assert saved_client.get("/api/v1/assessment/tests", params={"lifecycle": "archived", "cursor": page["next_cursor"]}).status_code == 422


def test_legacy_backfill_retains_partial_denominator_and_exact_rows(saved_app, saved_client):
    db = saved_app.state.services.db
    start = saved_client.post("/api/v1/assessment/start", json={"idempotency_key": "legacy-start-synthetic", "count": 3})
    assert start.status_code == 200
    session_id, item_id = start.json()["id"], start.json()["current_item"]["id"]
    answer = saved_client.post("/api/v1/assessment/sessions/" + session_id + "/answer", json={
        "idempotency_key": "legacy-answer-synthetic", "item_id": item_id, "option_ids": ["a"]})
    assert answer.status_code == 200
    tables = ("assessment_sessions", "assessment_items", "assessment_attempts", "assessment_exposure")
    before = {table: db.fetch_all("SELECT * FROM " + table + " ORDER BY id") for table in tables}
    repository = saved_app.state.services.get("saved_tests")
    assert repository.backfill_legacy()["created"] == 1
    assert repository.backfill_legacy()["existing"] == 1
    assert {table: db.fetch_all("SELECT * FROM " + table + " ORDER BY id") for table in tables} == before
    test_id, version_id = legacy_test_ids("reviewed", session_id)
    setup = repository.setup(test_id, version_id)
    assert setup["legacy"] == {"kind": "reviewed", "session_id": session_id}
    score = saved_client.get("/api/v1/assessment/sessions/" + session_id).json()["scores"]["reviewed"]["fresh"]
    assert score == {"answered": 1, "correct": 1, "accuracy": 1.0}
    manifest = private_version(saved_app, version_id)
    assert {item.item_id for item in manifest.items} == {row["id"] for row in before["assessment_items"]}


def test_generated_backfill_and_overlapping_typed_session_ids(saved_app, saved_client):
    db = saved_app.state.services.db
    fixture_path = Path(__file__).resolve().parents[2] / "packages/contracts/fixtures/design-c/legacy-schema1-records.json"
    records = json.loads(fixture_path.read_text(encoding="utf-8"))["records"]
    # Actual immutable schema-1 rows from DC02, no generation/provider call.
    for prefix in ("assessment", "assessment_generated"):
        session = deepcopy(records[prefix + "_sessions"][0]); original_id = session["id"]
        session["id"] = "overlapping_synthetic_session"
        with db.transaction() as conn:
            columns = list(session)
            conn.execute("INSERT INTO " + prefix + "_sessions(" + ",".join(columns) + ") VALUES(" + ",".join("?" for _ in columns) + ")", tuple(session.values()))
            for original in records[prefix + "_items"]:
                if original["session_id"] != original_id: continue
                row = {**original, "session_id": session["id"]}
                columns = list(row)
                conn.execute("INSERT INTO " + prefix + "_items(" + ",".join(columns) + ") VALUES(" + ",".join("?" for _ in columns) + ")", tuple(row.values()))
    repository = saved_app.state.services.get("saved_tests")
    assert repository.backfill_legacy()["created"] == 2
    reviewed = legacy_test_ids("reviewed", "overlapping_synthetic_session")
    generated = legacy_test_ids("generated", "overlapping_synthetic_session")
    assert reviewed != generated
    assert private_version(saved_app, generated[1]).review_quality == "personal"
    assert not private_version(saved_app, generated[1]).bank_cohort_eligible
    before = export_records(saved_app.state.services)
    saved_client.request("DELETE", "/api/v1/assessment/tests/" + generated[0], json={
        "idempotency_key": "delete-legacy-synthetic", "expected_revision": 1})
    with db.transaction() as conn:
        apply_records(conn, before)
    assert repository.backfill_legacy()["deleted"] == 1
    assert db.fetch_one("SELECT 1 FROM assessment_tests WHERE id=?", (generated[0],)) is None
    assert db.fetch_one("SELECT 1 FROM assessment_tests WHERE id=?", (reviewed[0],)) is not None
    assert db.fetch_one("SELECT 1 FROM assessment_generated_sessions WHERE id='overlapping_synthetic_session'") is not None


def test_private_publication_cannot_overwrite_manifest(saved_app, saved_client):
    result = create(saved_client)
    version = private_version(saved_app, result["version_id"])
    db = saved_app.state.services.db
    provenance = json.loads(db.fetch_one("SELECT provenance_json FROM assessment_test_versions WHERE id=?", (version.id,))["provenance_json"])
    changed = version.model_copy(update={"items": (version.items[0].model_copy(update={"stem": "Attempted rewrite"}), *version.items[1:])})
    with pytest.raises(ApiError, match="immutable"):
        with db.transaction() as conn:
            saved_app.state.services.get("saved_tests").publish_version(conn, changed, title="Synthetic mixed practice",
                provenance=provenance, idempotency_key="overwrite-synthetic", expected_revision=1)
    assert private_version(saved_app, version.id) == version
