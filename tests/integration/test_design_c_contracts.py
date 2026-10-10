# SPDX-License-Identifier: MIT
"""DC02 fixture/legacy-backend evidence, not connected C feature acceptance."""
from contextlib import closing
from copy import deepcopy
from datetime import datetime
import json
import hashlib
from pathlib import Path
import shutil
import sqlite3
import zipfile
from uuid import uuid4

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from renulus.contracts import ApiError
from renulus.design_c_contracts import (
    AttemptDraft, ContentReference, Conversation, CreateConversation, Dependency,
    EligibleInput, ErrorEnvelope, Exposure, FictionalTestArtifact, Identity, Job,
    GoalState, QuestionSnapshot, canonical_digest,
    MessagePage, PageRequest, PersistedAttemptPin, RELATION_PROPOSALS, Relation,
    SavedTestVersion, TABLE_COLUMNS, TestAttempt as Attempt, UNAVAILABLE_REFERENCE_COLUMNS,
    WorkspaceTab, disclosure_allowed, legacy_contract_views, owned_deletion_closure,
    publication_decision, reject_temporary_metadata, request_fingerprint,
    require_durable_conversation, server_retention, test_deadline_reached as deadline_reached,
    validate_attempt_draft, validate_fictional_artifact,
)
from renulus.server import create_app
from renulus.storage.backup import export_records, restore_records, validate_records
from renulus.storage.database import Database, SUPPORTED_SCHEMA
from renulus.storage.recovery_archive import backup_to
from renulus.storage.recovery_segmented import backup_segmented_to

FIXTURES = Path(__file__).resolve().parents[2] / "packages/contracts/fixtures/design-c"
SCRATCH = Path("C:/Renulus/scratch/design-c/contracts").resolve()


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_fixture_manifest_pins_captured_and_validated_json_bytes():
    manifest = fixture("fixture-manifest.json")
    assert manifest["provider_calls"] == 0
    assert len(manifest["files"]) == 11
    for name, entry in manifest["files"].items():
        data = (FIXTURES / name).read_bytes()
        assert len(data) == entry["bytes"]
        assert hashlib.sha256(data).hexdigest() == entry["sha256"]
        assert isinstance(json.loads(data), (dict, list))


@pytest.fixture(scope="module")
def scratch_root():
    root = SCRATCH / ("pytest-" + uuid4().hex[:10])
    root.mkdir(parents=True)
    assert root.resolve().is_relative_to(SCRATCH)
    return root


def services_at(root, name):
    return create_app(root / name).state.services


@pytest.fixture(scope="module")
def legacy_bundle():
    return fixture("legacy-schema1-records.json")


@pytest.fixture(scope="module")
def version():
    return SavedTestVersion.model_validate(fixture("saved-test-version.json"))


def test_fixture_is_actual_legacy_inventory_and_preserves_original_column_sets(scratch_root, legacy_bundle):
    services = services_at(scratch_root, "inventory")
    inventory = fixture("legacy-schema1-inventory.json")
    with closing(services.db.connect()) as conn:
        for table, columns in inventory["columns"].items():
            actual = [row["name"] for row in conn.execute(f'PRAGMA table_info("{table}")')]
            assert actual == columns, f"Use a sidecar, not changed original columns: {table}"
        for table, rows in legacy_bundle["records"].items():
            assert all(set(row) == set(inventory["columns"][table]) for row in rows)
    ledger = {row["name"]: row["checksum"] for row in services.db.fetch_all(
        "SELECT name,checksum FROM migration_ledger")}
    assert all(ledger[row["name"]] == row["checksum"] for row in inventory["migration_ledger"])


def test_real_json_fixture_restore_is_repeatable_with_legacy_answers_unchanged(scratch_root, legacy_bundle):
    services = services_at(scratch_root, "json-roundtrip")
    for _ in range(2):
        restore_records(services, deepcopy(legacy_bundle), confirm_older=True)
        exported = export_records(services)
        for table, rows in legacy_bundle["records"].items():
            if rows:
                # Compare canonical scalars, including key snapshots, exposure
                # and already-returned command feedback; preserve original IDs.
                expected = sorted(json.dumps(row, sort_keys=True) for row in rows)
                actual = sorted(json.dumps(row, sort_keys=True) for row in exported["records"][table])
                if table == "update_schedule":
                    # Existing restore retains the newer local singleton time.
                    assert [{key: value for key, value in row.items() if key != "updated_at"}
                            for row in exported["records"][table]] == [
                        {key: value for key, value in row.items() if key != "updated_at"} for row in rows]
                    continue
                assert actual == expected, table
    conversations, views = legacy_contract_views(legacy_bundle)
    assert {c.identity.id for c in conversations} == {
        row["id"] for table in ("learn_threads", "case_sessions") for row in legacy_bundle["records"][table]}
    assert all(c.project_id is None and c.retention == "saved" for c in conversations)
    assert {view.origin for view in views} == {"reviewed", "generated"}
    assert all(view.denominator == 1 and view.unanswered_not_scored == 2 for view in views)
    assert all(view.compatibility == "legacy_study" for view in views)
    assert next(view for view in views if view.origin == "reviewed").assisted_item_ids
    assert "DC02_VOLATILE_INPUT_OMITTED" not in json.dumps(legacy_bundle)


def test_newer_legacy_tombstone_prevents_reimport_without_regrading(scratch_root, legacy_bundle):
    services = services_at(scratch_root, "tombstone")
    restore_records(services, deepcopy(legacy_bundle), confirm_older=True)
    identifier = legacy_bundle["records"]["learn_threads"][0]["id"]
    services.db.execute("DELETE FROM learn_threads WHERE id=?", (identifier,))
    services.db.mark_deleted("learn_thread", identifier)
    restore_records(services, deepcopy(legacy_bundle), confirm_older=True)
    assert services.db.fetch_one("SELECT id FROM learn_threads WHERE id=?", (identifier,)) is None
    assert services.db.fetch_all("SELECT id FROM assessment_attempts") == [
        {"id": row["id"]} for row in legacy_bundle["records"]["assessment_attempts"]]


@pytest.mark.parametrize("format_version", [1, 2])
def test_actual_zip_adapters_roundtrip_known_original_and_legacy_history(scratch_root, legacy_bundle, format_version):
    source = services_at(scratch_root, f"zip-source-{format_version}")
    restore_records(source, deepcopy(legacy_bundle), confirm_older=True)
    text = "Entirely fictional DC02 original for ZIP ownership and digest checks."
    imported = source.registry["knowledge"].import_text(text, title="Fictional ZIP original", process=False)
    output = source.paths.root / "cache" / f"dc02-format-{format_version}.zip"
    writer = backup_to if format_version == 1 else backup_segmented_to
    writer(source, output)
    target = services_at(scratch_root, f"zip-target-{format_version}")
    recovery = target.registry["data_recovery"]
    identifier, directory = recovery.begin_preview()
    keep = False
    try:
        shutil.copyfile(output, directory / "input.zip")
        preview = recovery.complete_preview(identifier, directory)
        keep = True
    finally:
        recovery.end_upload(directory, keep=keep)
    with zipfile.ZipFile(output) as archive:
        assert json.loads(archive.read("manifest.json"))["format_version"] == format_version
    assert preview["original_count"] == 1
    result = recovery.restore_preview(identifier, preview["exported_at"], True)
    assert result["restored_originals"] == 1
    revision = target.db.fetch_one("SELECT original_path FROM knowledge_revisions WHERE id=?",
                                  (imported["revision_id"],))
    original = Path(revision["original_path"])
    assert original.resolve().is_relative_to(target.paths.root.resolve())
    assert original.read_text(encoding="utf-8") == text
    assert target.db.fetch_all("SELECT id FROM assessment_attempts") == [
        {"id": row["id"]} for row in legacy_bundle["records"]["assessment_attempts"]]


def test_existing_atomic_migration_ledger_rolls_back_interruption_and_refuses_changed_script(scratch_root):
    services = services_at(scratch_root, "migration")
    sql = "CREATE TABLE dc02_synthetic_probe(id TEXT PRIMARY KEY);"
    with pytest.raises(sqlite3.OperationalError):
        services.db.apply_migration("dc02-synthetic-probe", sql + "INSERT INTO dc02_missing VALUES(1);")
    assert services.db.fetch_one("SELECT name FROM sqlite_master WHERE name='dc02_synthetic_probe'") is None
    assert services.db.fetch_one("SELECT name FROM migration_ledger WHERE name='dc02-synthetic-probe'") is None
    services.db.apply_migration("dc02-synthetic-probe", sql)
    services.db.apply_migration("dc02-synthetic-probe", sql)
    with pytest.raises(RuntimeError, match="Applied migration changed"):
        services.db.apply_migration("dc02-synthetic-probe", sql + "-- changed")


def test_unsupported_profile_schema_and_unknown_export_are_refused(scratch_root, legacy_bundle):
    path = scratch_root / "unsupported.sqlite3"
    with sqlite3.connect(path) as conn:
        conn.execute(f"PRAGMA user_version={SUPPORTED_SCHEMA + 1}")
    with pytest.raises(RuntimeError, match="downgrade refused"):
        Database(path)
    with pytest.raises(ValueError, match="known schema-1"):
        legacy_contract_views({**legacy_bundle, "schema_version": 99})
    malformed = deepcopy(legacy_bundle)
    malformed["records"]["case_sessions"][0]["saved_at"] = None
    with pytest.raises(ValueError, match="explicit saved snapshot"):
        legacy_contract_views(malformed)


def test_module_row_relation_proposals_match_owned_additive_columns(legacy_bundle):
    proposal = fixture("relations-and-rows.json")
    inventory = fixture("legacy-schema1-inventory.json")["columns"]
    assert proposal["contract_version"] == "design-c/1"
    assert set(proposal["migration_reservations"]) == {
        "learn-002", "cases-003", "knowledge-003", "study-002", "assessment-003", "assessment-004"}
    assert all(table not in inventory for table in TABLE_COLUMNS)
    for edge in RELATION_PROPOSALS:
        parent = inventory.get(edge.parent_table, TABLE_COLUMNS.get(edge.parent_table))
        assert edge.parent_column in parent
        assert edge.child_column in TABLE_COLUMNS[edge.child_table]
        if edge.discriminator_column:
            assert edge.discriminator_column in TABLE_COLUMNS[edge.child_table]
            assert edge.discriminator_value in ("learning", "case")
        assert edge.on_missing == "delete_row"
    # Pinned provenance columns are deliberately absent from the prune registry.
    for table, pinned, live in UNAVAILABLE_REFERENCE_COLUMNS:
        assert pinned in TABLE_COLUMNS[table] and live in TABLE_COLUMNS[table]
        assert not any(edge.child_table == table and edge.child_column == pinned for edge in RELATION_PROPOSALS)
    assert "project_id" not in TABLE_COLUMNS["learn_conversations"]
    assert "project_id" not in TABLE_COLUMNS["case_conversations"]
    assert proposal["table_columns"] == {table: list(columns) for table, columns in TABLE_COLUMNS.items()}
    assert TABLE_COLUMNS["assessment_test_commands"] == (
        "idempotency_key", "operation", "target_type", "target_id", "request_hash", "result_json", "created_at")
    assert "assessment_commands" in inventory and "assessment_test_commands" not in inventory
    for table, additions in {
        "assessment_test_versions": {"provenance_json"},
        "assessment_test_attempts": {"committed_json", "result_json", "clock_high_water_at", "paused_at"},
        "assessment_question_reports": {"question_snapshot_json", "request_hash"},
        "assessment_test_jobs": {"accepted_count"},
        "study_project_goals": {"status", "progress_json"},
    }.items():
        assert additions <= set(TABLE_COLUMNS[table])


def test_typed_ownership_preserves_shared_originals_and_namespaces():
    project = Identity(type="project", id="same_id")
    other = Identity(type="project", id="other_project")
    doc = Identity(type="library_document", id="same_id")
    revision = Identity(type="library_revision", id="revision_1")
    chat = Identity(type="case", id="case_1")
    attachment = Identity(type="attachment", id="attachment_1")
    original = Identity(type="attachment_original", id="original_1")
    relations = (Relation(source=project, target=revision, relationship="link"),
        Relation(source=other, target=revision, relationship="link"),
        Relation(source=project, target=chat, relationship="link"),
        Relation(source=doc, target=revision, relationship="owned"),
        Relation(source=chat, target=attachment, relationship="owned"),
        Relation(source=attachment, target=original, relationship="owned"))
    assert owned_deletion_closure((project,), relations) == {project}
    assert owned_deletion_closure((attachment,), relations) == {attachment, original}
    assert owned_deletion_closure((chat,), relations) == {chat, attachment, original}
    assert doc != project
    with pytest.raises(ValidationError):
        Relation(source=project, target=doc, relationship="owned")


def test_server_retention_is_separate_from_kind_and_temp_metadata_is_rejected():
    conversation = Conversation.model_validate(fixture("conversation.json"))
    assert server_retention(CreateConversation(kind="case")) == "saved"
    assert server_retention(CreateConversation(kind="learning", temporary=True)) == "temporary"
    with pytest.raises(ValidationError):
        CreateConversation(kind="learning", scope={"kind": "saved-case"})
    temporary = Conversation.model_validate({**conversation.model_dump(mode="json"), "retention": "temporary"})
    with pytest.raises(ValueError, match="metadata may be durable"):
        require_durable_conversation(temporary)
    with pytest.raises(ValidationError):
        Conversation.model_validate({**temporary.model_dump(mode="json"), "project_id": "project_1"})
    tab = WorkspaceTab(content={"target": {"type": "attachment", "id": "volatile_attachment_1"}}, context=temporary.identity)
    with pytest.raises(ValueError, match="durable boundary"):
        reject_temporary_metadata(tab, (temporary.identity.id, "volatile_attachment_1"))
    with pytest.raises(ValidationError):
        WorkspaceTab.model_validate({**tab.model_dump(mode="json"), "retention": "temporary"})


def test_locators_pin_real_location_conventions_and_reject_ambiguous_ranges():
    refs = [ContentReference.model_validate(row) for row in fixture("locators.json")]
    assert refs[0].locator.physical_page == 3 and refs[0].locator.printed_label == "ii"
    assert refs[1].locator.item_ref == "#/texts/2"
    assert refs[3].locator.sheet_name == "Fictional study"
    assert refs[4].locator.frame == 2
    for locator in ({"kind": "pdf", "physical_page": 0},
                    {"kind": "text", "item_ref": "#/texts/0", "start": 5, "end": 3},
                    {"kind": "image", "frame": 1, "bounds": [0, 0, 2, 1]}):
        with pytest.raises(ValidationError):
            ContentReference(target=refs[0].target, locator=locator)
    with pytest.raises(ValidationError):
        ContentReference(target={"type": "library_revision", "id": "C:/private/file.pdf"})


def test_paginated_read_shape_preserves_tied_timestamp_order_and_bounds():
    identity = {"type": "learn_thread", "id": "thread_page_1"}
    def message(identifier):
        return {"id": identifier, "run_id": "run_1", "role": "user", "content": "Synthetic",
                "created_at": "2026-10-10T12:00:00Z"}
    page = MessagePage(conversation=identity, items=(message("message_a"), message("message_b")), next_cursor="opaque-snapshot-cursor")
    assert [item.id for item in page.items] == ["message_a", "message_b"]
    for items in ((message("message_b"), message("message_a")), (message("message_a"), message("message_a"))):
        with pytest.raises(ValidationError):
            MessagePage(conversation=identity, items=items)
    with pytest.raises(ValidationError):
        PageRequest(limit=101)


def test_immutable_version_mode_and_attempt_draft_remain_separate(version):
    data = fixture("attempt-and-draft.json")
    attempt = Attempt.model_validate(data["attempt"])
    draft = AttemptDraft.model_validate(data["draft"])
    exposure = Exposure.model_validate(data["exposure"])
    validate_attempt_draft(draft, attempt, version)
    assert version.item_count == 5 and not version.bank_cohort_eligible
    assert version.provenance.schema_version == 1 and version.provenance.method == "generation"
    assert exposure.kind == "presented" and exposure.version_id == version.id
    assert "correct" not in draft.model_dump_json() and "correct_option_ids" not in attempt.model_dump_json()
    with pytest.raises(ValidationError):
        version.ordinal = 2
    with pytest.raises(ValidationError):
        SavedTestVersion.model_validate({**version.model_dump(mode="json"), "review_quality": "reviewed"})
    malformed = draft.model_dump(mode="json")
    malformed["answers"][0]["option_ids"] = ["not_a_supplied_option"]
    with pytest.raises(ValueError):
        validate_attempt_draft(AttemptDraft.model_validate(malformed), attempt, version)


def test_deleted_version_keeps_original_pin_payload_report_and_job_outcome(version):
    data = fixture("unavailable-references.json")
    pin = PersistedAttemptPin.model_validate(data["attempt_pin"])
    assert pin.live_version_id is None and pin.version_id == version.id
    assert pin.version_snapshot.items == version.items
    assert pin.version_snapshot.provenance == version.provenance
    assert data["report"]["version_id"] == version.id and data["report"]["live_version_id"] is None
    assert data["report"]["attempt_id"] == pin.attempt_id and data["report"]["live_attempt_id"] is None
    report = data["report"]
    question = QuestionSnapshot.model_validate(report["question_snapshot"])
    assert question == version.items[0]
    assert report["request_hash"] == canonical_digest({key: report[key] for key in (
        "version_id", "attempt_id", "item_id", "report_text")})
    assert data["job_outcome"]["published_version_id"] == version.id
    assert data["job_outcome"]["live_published_version_id"] is None
    with pytest.raises(ValidationError):
        PersistedAttemptPin.model_validate({**data["attempt_pin"], "version_id": "rewritten_pin"})


def test_study_commit_and_result_payloads_survive_resume_without_test_disclosure():
    data = fixture("attempt-and-draft.json")
    raw = {**data["attempt"], "mode": "study", "status": "paused", "committed": data["study_committed"]}
    resumed = Attempt.model_validate(raw)
    assert resumed.committed[0].assisted and resumed.committed[0].correct
    final = Attempt.model_validate({**raw, "status": "ended", "result": data["study_result"]})
    assert final.result.scored_count == 1 and final.result.unanswered_count == 4
    with pytest.raises(ValidationError, match="scored answers"):
        Attempt.model_validate({**raw, "mode": "test", "status": "active"})
    assert "committed_json" in TABLE_COLUMNS["assessment_test_attempts"]
    assert "result_json" in TABLE_COLUMNS["assessment_test_attempts"]


def test_test_policy_and_clock_shapes_cover_precommit_disclosure_and_backward_clock():
    attempt = Attempt.model_validate(fixture("attempt-and-draft.json")["attempt"])
    for operation in ("chat", "sources", "notes", "search_snippets", "legacy_feedback", "command_replay",
                      "aggregates", "mistakes", "export", "backup", "restore", "unknown_operation"):
        assert not disclosure_allowed(attempt, operation)
    assert disclosure_allowed(attempt, "report_question")
    assert disclosure_allowed(attempt, "connection_status")
    assert not deadline_reached(attempt, datetime.fromisoformat("2026-10-10T12:09:59+00:00"))
    assert deadline_reached(attempt, datetime.fromisoformat("2026-10-10T12:10:00+00:00"))
    prior = attempt.model_dump(mode="json")
    prior["clock_high_water_at"] = "2026-10-10T12:11:00Z"
    assert deadline_reached(Attempt.model_validate(prior), datetime.fromisoformat("2026-10-10T12:00:00+00:00"))
    without_high_water = {key: value for key, value in prior.items() if key != "clock_high_water_at"}
    with pytest.raises(ValidationError):
        Attempt.model_validate(without_high_water)
    with pytest.raises(ValidationError):
        Attempt.model_validate({**prior, "paused_at": "2026-10-10T12:01:00Z"})
    prior["timing"]["last_reconciled_at"] = "2026-10-10T12:11:00Z"
    assert deadline_reached(Attempt.model_validate(prior), datetime.fromisoformat("2026-10-10T12:00:00+00:00"))
    with pytest.raises(ValidationError):
        Attempt.model_validate({**prior, "status": "paused"})
    study = Attempt.model_validate({**prior, "mode": "study", "status": "timer_expired"})
    assert not deadline_reached(study, datetime.fromisoformat("2026-10-10T13:00:00+00:00"))


def test_job_publication_rechecks_epoch_revisions_settings_and_cancel_winner():
    data = fixture("job.json")
    job = Job.model_validate(data)
    kwargs = {"settings_revision": 1, "policy_revision": 1, "context_epoch": 3}
    current = {job.inputs[0].dependency.target.key: "2"}
    assert publication_decision(job, current, **kwargs) == "publishable"
    assert publication_decision(job, {}, **kwargs) == "invalidated"
    assert publication_decision(job, current, **{**kwargs, "context_epoch": 4}) == "invalidated"
    assert publication_decision(job, current, **kwargs, enabled=False) == "invalidated"
    assert publication_decision(Job.model_validate({**data, "state": "cancelled"}), current, **kwargs) == "cancelled"
    published = Job.model_validate({**data, "state": "published", "published_version": {"id": "test_version_fiction_1"}})
    assert publication_decision(published, {}, **kwargs, enabled=False) == "published"
    with pytest.raises(ValidationError):
        Job.model_validate({**published.model_dump(mode="json"), "validated_count": 4})


def test_explicit_shorter_set_preserves_original_request_and_publication_winner():
    data = fixture("accepted-shorter-set.json")
    job = Job.model_validate(data["job"])
    original = Job.model_validate({**data["job"], "accepted_count": None})
    current = {job.inputs[0].dependency.target.key: "2"}
    kwargs = {"settings_revision": 1, "policy_revision": 1, "context_epoch": 3}
    assert original.requested_count == job.requested_count == 20
    assert original.request_hash == job.request_hash
    assert job.validated_count == job.accepted_count == job.effective_count == data["effective_count"] == 5
    assert publication_decision(original, current, **kwargs) == "not_ready"
    assert publication_decision(job, current, **kwargs) == "publishable"
    published = Job.model_validate({**data["job"], "state": "published",
        "published_version": {"id": "test_version_fiction_1"}})
    assert published.requested_count == 20 and published.request_hash == original.request_hash
    assert publication_decision(published, {}, **kwargs, enabled=False) == "published"
    for invalid in (0, 6, 21, True):
        with pytest.raises(ValidationError):
            Job.model_validate({**data["job"], "accepted_count": invalid})
    with pytest.raises(ValidationError):
        Job.model_validate({**data["job"], "accepted_count": 10, "validated_count": 10, "requested_count": 5})
    with pytest.raises(ValidationError):
        Job.model_validate({**data["job"], "accepted_count": None, "state": "published",
            "published_version": {"id": "test_version_fiction_1"}})


def test_goal_progress_is_explicit_manual_intent_or_evidence_without_percentages():
    default = GoalState()
    assert default.status == "active" and default.progress.model_dump(exclude_unset=True) == {}
    goal = GoalState.model_validate(fixture("accepted-shorter-set.json")["goal"])
    assert goal.status == "completed" and goal.progress.evidence_ids == ("evidence_fiction_1",)
    assert goal.progress.manual_intent
    for invalid in ({"status": "inferred_complete"}, {"progress": {"percentage": 100}},
                    {"progress": {"evidence_ids": ["evidence_1", "evidence_1"]}}):
        with pytest.raises(ValidationError):
            GoalState.model_validate(invalid)


@pytest.mark.parametrize("source_type", ["case", "learn_thread", "library_revision", "attachment", "saved_test_version"])
def test_raw_context_and_keys_are_not_personalisation_inputs(source_type):
    with pytest.raises(ValidationError):
        EligibleInput(kind="memory", dependency=Dependency(
            target=Identity(type=source_type, id="ineligible_input"), expected_revision="1"))


def test_only_trusted_fictional_artifact_boundary_admits_validated_questions(version):
    artifact = FictionalTestArtifact.model_validate(fixture("fictional-artifact.json"))
    assert artifact.questions == version.items
    built = validate_fictional_artifact(version.items, artifact_id=artifact.id, validation_id=artifact.validation_id,
        privacy_check=lambda items: all("Fictional learning scenario" in q.stem for q in items),
        forbidden_fragments=("VOLATILE_IDENTIFYING_SENTINEL",))
    assert built == artifact
    with pytest.raises(ValueError, match="privacy review"):
        validate_fictional_artifact(version.items, artifact_id=artifact.id, validation_id=artifact.validation_id,
            privacy_check=lambda _: False, forbidden_fragments=())
    with pytest.raises(ValueError, match="durable boundary"):
        validate_fictional_artifact(version.items, artifact_id="volatile_case_id", validation_id=artifact.validation_id,
            privacy_check=lambda _: True, forbidden_fragments=("volatile_case_id",))
    with pytest.raises(ValidationError):
        FictionalTestArtifact.model_validate({**artifact.model_dump(mode="json"), "temporary_source_id": "volatile_case_id"})
    with pytest.raises(ValidationError):
        Job.model_validate({**fixture("job.json"), "raw_prompt": "VOLATILE_IDENTIFYING_SENTINEL"})


def test_error_envelope_and_fingerprint_reuse_existing_api_semantics(scratch_root):
    app = create_app(scratch_root / "error-api")
    with TestClient(app, raise_server_exceptions=True) as client:
        response = client.post("/api/v1/cases/sessions", json={
            "text": "FICTIONAL_ERROR_PAYLOAD_SENTINEL", "retention": "saved"})
    assert response.status_code == 422
    envelope = ErrorEnvelope.model_validate(response.json())
    assert envelope.error.code == "invalid_request"
    assert "FICTIONAL_ERROR_PAYLOAD_SENTINEL" not in response.text
    target = Identity(type="case", id="case_1")
    request = CreateConversation(kind="case")
    assert request_fingerprint("create", target, request) == request_fingerprint("create", target, request)
    assert request_fingerprint("create", target, request) != request_fingerprint(
        "create", target, CreateConversation(kind="case", temporary=True))
