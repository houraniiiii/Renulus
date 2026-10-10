# SPDX-License-Identifier: MIT
"""Real saved-test router/SQLite checks. All profiles and inputs are synthetic."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from renulus.assessment.test_api import create_router
from renulus.assessment.test_models import CreateReviewedTestRequest
from renulus.assessment.test_models import QuestionReportRequest, TestLifecycleRequest as LifecycleRequest
from renulus.assessment.test_repository import legacy_test_ids
from renulus.assessment.attempt_models import QuestionReport, StartAttempt, SubmitAttempt
from renulus.assessment.fictionalisation import fictionalise_test
from renulus.storage.assessment_policy import policy_snapshot
from renulus.storage.invalidation import context_epoch_in
from renulus.contracts import ApiError
from renulus.storage.backup import apply_records, export_records
from test_fictionalisation import RAW, Transport
from test_saved_imports import extracted_imports, request as import_request, resolve_all, command as import_command
from renulus.assessment.import_models import CreateImportRequest


@pytest.fixture(autouse=True)
def assessment_modules(monkeypatch):
    # Use the current assembled registries and actual migrations.
    monkeypatch.setattr("renulus.server.MODULE_ORDER", ("runtime", "content", "knowledge", "learn", "cases", "assessment", "memory", "study", "updates"))


@pytest.fixture
def saved_app(app):
    # Parent's actual migration is required; never substitute fixture DDL.
    services = app.state.services
    assert services.db.fetch_one("SELECT name FROM sqlite_master WHERE name='assessment_test_commands'"), (
        "Prerequisite: integrate parent's assessment-003 migration before persistence acceptance")
    if "saved_tests" not in services.registry:
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
    with saved_app.state.services.db.transaction() as conn:
        provenance = saved_app.state.services.get("saved_tests").pinned_provenance(conn, pin.id)
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
    assert saved_client.post(report_path, json=request).json() == report.json()
    assert saved_client.post(report_path, json={**request, "report_text": "Changed after deletion"}).status_code == 409
    assert db.fetch_all("SELECT * FROM learning_evidence") == []
    # Attempt owner can still report against its independent snapshot after deletion.
    with db.transaction() as conn:
        receipt = saved_app.state.services.get("saved_tests").save_question_report(conn, version=pin,
            attempt_id=None, item_id=pin.items[1].item_id, report_text="Retained snapshot report", idempotency_key="after-delete-synthetic",
            provenance=provenance)
    assert receipt["status"] == "saved"
    snapshot = json.loads(db.fetch_one("SELECT question_snapshot_json FROM assessment_question_reports WHERE id=?", (receipt["id"],))["question_snapshot_json"])
    assert snapshot["producer"] == pin.provenance.model_dump(mode="json")
    assert snapshot["provenance"]["item"]["original_snapshot"]["sources"][0]["locator"] == "Fixture section 1"


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
    history = repository.legacy_history(test_id)
    assert history["scores"] == {before["assessment_attempts"][0]["score_bucket"]: {"answered": 1, "correct": 1}}
    assert history["denominator"] == 1 and history["unanswered_not_scored"] == 2
    assert history["committed_answer_ids"] == [row["id"] for row in before["assessment_attempts"]]
    assert len(history["feedback"]) == 1 and history["feedback"][0]["answer_id"] == before["assessment_attempts"][0]["id"]
    assert history["feedback"][0]["selected_option_ids"] == ['a']
    assert {table: db.fetch_all("SELECT * FROM " + table + " ORDER BY id") for table in tables} == before
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


def test_shared_active_test_policy_blocks_disclosure_but_keeps_neutral_report(saved_app, saved_client):
    result = create(saved_client, count=1)
    version = private_version(saved_app, result["version_id"])
    db = saved_app.state.services.db
    attempt = saved_app.state.services.get("whole_attempts").start(
        StartAttempt(version={"type": "saved_test_version", "id": version.id}, mode="test"), "real-active-synthetic-test")
    path = "/api/v1/assessment/tests/" + result["test_id"]
    for suffix in ("/setup", "/versions/" + version.id + "/preview", "/history"):
        response = saved_client.get(path + suffix)
        assert response.status_code == 409 and response.json()["error"]["code"] == "assistance_restricted"
    response = saved_client.post("/api/v1/assessment/tests/reviewed", json={"idempotency_key": "blocked-create-synthetic", "count": 1})
    assert response.status_code == 409
    assert saved_client.get("/api/v1/assessment/tests").status_code == 409
    report = saved_client.post(path + "/versions/" + version.id + "/reports", json={
        "idempotency_key": "restricted-neutral-report", "item_id": version.items[0].item_id, "report_text": "Synthetic local report"})
    assert report.status_code == 409
    report_path = "/api/v1/assessment/test-attempts/" + attempt["id"] + "/reports"
    body = {"item_id": version.items[0].item_id, "report_text": "Synthetic local report"}
    headers = {"Idempotency-Key": "actual-neutral-attempt-report"}
    report = saved_client.post(report_path, json=body, headers=headers)
    assert report.status_code == 201 and set(report.json()) == {"id", "status", "created_at"}
    assert saved_client.post(report_path, json=body, headers=headers).json() == report.json()
    assert len(db.fetch_all("SELECT * FROM assessment_tests")) == 1


def assert_native_report_lifetime(services, result, *, client=None):
    """Real attempt pin, typed pruning and Recovery.restore_json; no fixture DDL."""
    repository, attempts, db = services.get("saved_tests"), services.get("whole_attempts"), services.db
    with db.transaction() as conn:
        version = repository.pinned_version(conn, result["version_id"])
        native = repository.pinned_provenance(conn, version.id)
    item = version.items[0]
    request = QuestionReportRequest(idempotency_key="native-report-" + version.id[-24:],
        item_id=item.item_id, report_text="Synthetic provenance ambiguity")
    receipt = repository.report_question(version.test_id, version.id, request)
    attempt = attempts.start(StartAttempt(version={"type": "saved_test_version", "id": version.id}, mode="test"),
        "native-attempt-" + version.id[-24:])
    attempt_key = "native-attempt-report-" + version.id[-24:]
    body = QuestionReport(item_id=item.item_id, report_text="Synthetic retained attempt report")
    if client:
        path = "/api/v1/assessment/test-attempts/" + attempt["id"] + "/reports"
        response = client.post(path, json=body.model_dump(mode="json"), headers={"Idempotency-Key": attempt_key})
        assert response.status_code == 201, response.text
        attempt_receipt = response.json()
        assert client.post(path, json=body.model_dump(mode="json"), headers={"Idempotency-Key": attempt_key}).json() == attempt_receipt
        collection_path = "/api/v1/assessment/tests/" + version.test_id + "/versions/" + version.id + "/reports"
        assert client.post(collection_path, json=request.model_dump(mode="json")).status_code == 409
    else:
        attempt_receipt = attempts.report(attempt["id"], body, attempt_key)
        assert attempts.report(attempt["id"], body, attempt_key) == attempt_receipt
    assert set(receipt) == set(attempt_receipt) == {"id", "status", "created_at"}
    expected = {key: value for key, value in native.items() if key != "items"}
    expected["item"] = next((value for value in native.get("items", []) if value["item_id"] == item.item_id), None)
    for saved in (receipt, attempt_receipt):
        with db.transaction() as conn:
            snapshot = repository.pinned_report_snapshot(conn, saved["id"])
        assert snapshot["schema"] == "question-report-snapshot/2"
        assert snapshot["provenance"] == expected
        assert snapshot["provenance_status"] == {"state": "retained", "reason": "native_envelope"}
        assert "original_text" not in json.dumps(snapshot) and RAW not in json.dumps(snapshot)
    attempts.submit(attempt["id"], SubmitAttempt(expected_draft_revision=attempt["draft_revision"]),
        "native-submit-" + version.id[-24:])
    older = export_records(services)
    stored = {saved["id"]: db.fetch_one("SELECT question_snapshot_json FROM assessment_question_reports WHERE id=?", (saved["id"],))["question_snapshot_json"]
              for saved in (receipt, attempt_receipt)}
    repository.lifecycle(version.test_id, LifecycleRequest(idempotency_key="native-delete-" + version.id[-24:], expected_revision=1), "delete")
    db.mark_deleted("test_attempt", attempt["id"])
    # Actual restore honors typed tombstones: it removes the live attempt but
    # retains independently owned reports and their immutable historical pins.
    services.get("data_recovery").restore_json(older, confirm_backup_date=True, confirmed_exported_at=older["exported_at"])
    assert db.fetch_one("SELECT id FROM assessment_test_versions WHERE id=?", (version.id,)) is None
    assert db.fetch_one("SELECT id FROM assessment_test_attempts WHERE id=?", (attempt["id"],)) is None
    for saved in (receipt, attempt_receipt):
        row = db.fetch_one("SELECT * FROM assessment_question_reports WHERE id=?", (saved["id"],))
        assert row["question_snapshot_json"] == stored[saved["id"]]
        assert row["live_version_id"] is None and row["live_attempt_id"] is None
        assert row["version_id"] == version.id
    assert db.fetch_one("SELECT attempt_id FROM assessment_question_reports WHERE id=?", (attempt_receipt["id"],))["attempt_id"] == attempt["id"]
    assert repository.report_question(version.test_id, version.id, request) == receipt
    if client:
        response = client.post(collection_path, json=request.model_dump(mode="json"))
        assert response.status_code == 200 and response.json() == receipt
        assert client.post(collection_path, json={**request.model_dump(mode="json"), "report_text": "changed"}).status_code == 409
    return stored, native


@pytest.mark.asyncio
@pytest.mark.parametrize("producer", ["import", "fictional"])
async def test_actual_native_import_and_fictional_report_envelopes_survive_delete_restore(saved_app, saved_client, producer):
    services = saved_app.state.services
    if producer == "import":
        imports = services.get("saved_imports")
        row = resolve_all(imports, imports.create(import_request("native-import-original")))
        result = imports.save(row["id"], import_command(row, "native-import-save"))["result"]
    else:
        provider = services.get("provider")
        provider._settings["connections"]["codex"] = {"access_token": "synthetic-fictional-token", "expires_at": 9999999999}
        provider._settings["selected_provider"] = "codex"
        provider._settings.setdefault("selected_models", {})["codex"] = "gpt-6.1-sol"
        provider._transport = Transport()
        with services.db.transaction() as conn:
            revision, epoch = policy_snapshot(conn)["revision"], context_epoch_in(conn)
        artifact = await fictionalise_test(services, source_text=RAW, instruction="Teach the general concept", count=5,
            cancel=asyncio.Event(), expected_policy_revision=revision, expected_context_epoch=epoch)
        result = await services.get("saved_generation").publish_fictional_artifact(artifact,
            expected_policy_revision=revision, expected_context_epoch=epoch)
        assert len(provider._transport.calls) == 2
    stored, native = assert_native_report_lifetime(services, result, client=saved_client)
    if producer == "import":
        assert native["import"]["original_sha256"] and native["import"]["private"] is True
        assert native["import"]["source_pin"] is None
        await imports.delete(row["id"], import_command(imports.read(row["id"]), "native-original-delete"))
        assert services.db.fetch_one("SELECT id FROM assessment_test_imports WHERE id=?", (row["id"],)) is None
    else:
        assert native["fictionalisation"]["validation_id"] == artifact.validation_id
        assert native["fictionalisation"]["sha256"] == artifact.sha256
        assert native["fictionalisation"]["privacy_review"] == "independent-selected-model+overlap/1"
        assert native["fictionalisation"]["route"]["model"] == "gpt-6.1-sol"
        serialised = json.dumps(export_records(services))
        assert all(value not in serialised for value in (RAW, "SYNTHETIC_PRIVATE_PERSON", "CASE_SENTINEL_928374"))
        assert len(provider._transport.calls) == 2
    for identifier, snapshot in stored.items():
        assert services.db.fetch_one("SELECT question_snapshot_json FROM assessment_question_reports WHERE id=?", (identifier,))["question_snapshot_json"] == snapshot


def test_actual_library_native_report_retains_private_source_pin(extracted_imports):
    services, imports, transport, note, _ = extracted_imports
    row = resolve_all(imports, imports.create(CreateImportRequest(idempotency_key="native-library-original",
        original={"kind": "library_revision", "revision_id": note["revision_id"]})))
    pin = imports.original(row["id"])["original"]["source_pin"]
    result = imports.save(row["id"], import_command(row, "native-library-save"))["result"]
    calls = len(transport.calls)
    stored, native = assert_native_report_lifetime(services, result)
    assert native["import"]["source_pin"] == pin
    assert pin["original_sha256"] and pin["original"]["relative_path"]
    services.get("knowledge").delete_document(note["document_id"])
    for identifier, snapshot in stored.items():
        assert services.db.fetch_one("SELECT question_snapshot_json FROM assessment_question_reports WHERE id=?", (identifier,))["question_snapshot_json"] == snapshot
    assert len(transport.calls) == calls


def test_private_report_reader_labels_legacy_projection_without_rewriting_history(saved_app, saved_client):
    result = create(saved_client, count=1)
    services, db = saved_app.state.services, saved_app.state.services.db
    version = private_version(saved_app, result["version_id"])
    request = QuestionReportRequest(idempotency_key="legacy-projection-report", item_id=version.items[0].item_id, report_text="Legacy local report")
    receipt = services.get("saved_tests").report_question(version.test_id, version.id, request)
    raw = json.loads(db.fetch_one("SELECT question_snapshot_json FROM assessment_question_reports WHERE id=?", (receipt["id"],))["question_snapshot_json"])
    # Exact historical writer shape: discarded headers are not recoverable.
    raw["schema"] = "question-report-snapshot/1"
    raw["provenance"] = {"schema": raw["provenance"]["schema"], "item": raw["provenance"]["item"]}
    raw.pop("provenance_status")
    encoded = json.dumps(raw)
    db.execute("UPDATE assessment_question_reports SET question_snapshot_json=? WHERE id=?", (encoded, receipt["id"]))
    with db.transaction() as conn:
        snapshot = services.get("saved_tests").pinned_report_snapshot(conn, receipt["id"])
    assert snapshot["provenance_status"] == {"state": "incomplete", "reason": "legacy_report_projection"}
    assert snapshot["provenance"] == raw["provenance"]
    assert db.fetch_one("SELECT question_snapshot_json FROM assessment_question_reports WHERE id=?", (receipt["id"],))["question_snapshot_json"] == encoded
    assert services.get("saved_tests").report_question(version.test_id, version.id, request) == receipt


def test_nullable_unresolved_report_key_and_exact_text_bound(saved_app, saved_client):
    result = create(saved_client, count=1)
    version = private_version(saved_app, result["version_id"])
    item = version.items[0].model_dump(mode="json")
    item["correct_option_ids"] = []; item["key_version"] = None
    path = "/api/v1/assessment/tests/" + result["test_id"]
    edited = saved_client.post(path + "/versions", json={"idempotency_key": "unresolved-bound-edit", "expected_revision": 1,
        "base_version_id": version.id, "items": [item]}).json()
    report_path = path + "/versions/" + edited["version_id"] + "/reports"
    request = {"idempotency_key": "nullable-key-report", "item_id": item["item_id"], "report_text": "x" * 2000}
    assert saved_client.post(report_path, json=request).status_code == 200
    assert saved_client.post(report_path, json={**request, "idempotency_key": "too-long-local-report", "report_text": "x" * 2001}).status_code == 422
    row = saved_app.state.services.db.fetch_one("SELECT * FROM assessment_question_reports")
    assert row["key_version"] is None and len(row["report_text"]) == 2000
    assert json.loads(row["question_snapshot_json"])["provenance"]["item"]["original_snapshot"]["sources"]


def test_version_history_is_bounded_and_older_pin_still_opens(saved_app, saved_client):
    result = create(saved_client, count=1)
    version = private_version(saved_app, result["version_id"])
    path = "/api/v1/assessment/tests/" + result["test_id"]
    for revision in (1, 2):
        response = saved_client.post(path + "/versions", json={"idempotency_key": "bounded-version-" + str(revision),
            "expected_revision": revision, "base_version_id": version.id, "items": [version.items[0].model_dump(mode="json")]})
        assert response.status_code == 200
    first = saved_client.get(path + "/versions?limit=1").json()
    assert first["items"][0]["ordinal"] == 3 and first["next_before"] == 3
    second = saved_client.get(path + "/versions?limit=1&before=3").json()
    assert second["items"][0]["ordinal"] == 2 and second["next_before"] == 2
    last = saved_client.get(path + "/versions?limit=1&before=2").json()
    assert last["items"][0]["id"] == version.id and last["next_before"] is None
    assert saved_client.get("/api/v1/assessment/tests/versions/" + version.id + "/setup").json()["version"]["ordinal"] == 1


def test_unavailable_legacy_snapshot_does_not_block_other_sessions(saved_app, saved_client):
    starts = [saved_client.post("/api/v1/assessment/start", json={"idempotency_key": key, "count": 1}).json()
              for key in ("legacy-valid-synthetic", "legacy-incomplete-synthetic")]
    db = saved_app.state.services.db
    broken_id = starts[1]["id"]
    db.execute("UPDATE assessment_items SET snapshot_json='{}' WHERE session_id=?", (broken_id,))
    before = db.fetch_all("SELECT * FROM assessment_items WHERE session_id=?", (broken_id,))
    response = saved_client.get("/api/v1/assessment/tests")
    assert response.status_code == 200 and response.json()["legacy_unavailable"] == 1
    assert len(response.json()["items"]) == 1
    assert db.fetch_all("SELECT * FROM assessment_items WHERE session_id=?", (broken_id,)) == before
    version = private_version(saved_app, legacy_test_ids("reviewed", starts[0]["id"])[1])
    assert version.provenance.method == "legacy_conversion"
    repository = saved_app.state.services.get("saved_tests")
    receipt = repository.report_question(version.test_id, version.id, QuestionReportRequest(
        idempotency_key="actual-legacy-conversion-report", item_id=version.items[0].item_id, report_text="Legacy source ambiguity"))
    with db.transaction() as conn:
        snapshot = repository.pinned_report_snapshot(conn, receipt["id"])
    assert snapshot["provenance_status"] == {"state": "incomplete", "reason": "legacy_conversion"}
    assert snapshot["provenance"]["legacy"] == {"kind": "reviewed", "session_id": starts[0]["id"]}


def test_withdrawn_source_has_useful_state_without_mutating_pin(saved_app, saved_client, content):
    result = create(saved_client, count=1)
    version = private_version(saved_app, result["version_id"])
    content.withdraw(version.items[0].question_id)
    setup = saved_client.get("/api/v1/assessment/tests/versions/" + version.id + "/setup").json()
    assert setup["can_start"] is False and setup["content_warnings"] == [{"item_id": version.items[0].item_id, "status": "withdrawn"}]
    assert private_version(saved_app, version.id) == version
