# SPDX-License-Identifier: MIT
"""Saved notes through real Knowledge originals, migrations and owner APIs."""
from concurrent.futures import ThreadPoolExecutor
from contextvars import Context
import hashlib
from io import BytesIO
import json
import socket
import zipfile

from fastapi.testclient import TestClient
import pytest

from renulus.contracts import ApiError
from renulus.knowledge.models import Rights, SourceMetadata
from renulus.server import create_app


@pytest.fixture
def app(tmp_path, monkeypatch):
    connect = socket.socket.connect
    def local_only(instance, address):
        if isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"}:
            return connect(instance, address)
        raise AssertionError("Notes tests forbid external network and providers")
    monkeypatch.setattr(socket.socket, "connect", local_only)
    result = create_app(tmp_path / "synthetic-notes")
    assert "notes" in result.state.services.registry
    try:
        yield result
    finally:
        result.state.services.get("knowledge").index.close()


def test_replacing_a_queued_study_note_retains_its_immutable_original(app):
    knowledge = app.state.services.get("knowledge")
    first = knowledge.import_text("SYNTHETIC first retained note",
        metadata=SourceMetadata(asset_role=["study-note"]), process=False)
    second = knowledge.import_text("SYNTHETIC updated retained note",
        metadata=SourceMetadata(asset_role=["study-note"]),
        document_id=first["document_id"], process=False)
    knowledge.cleanup()
    first_path = knowledge.original(first["revision_id"])[0]
    second_path = knowledge.original(second["revision_id"])[0]
    assert first_path.read_text() == "SYNTHETIC first retained note"
    assert second_path.read_text() == "SYNTHETIC updated retained note"
    assert knowledge.get_job(first["job"]["id"])["state"] == "cancelled"
    deleted = knowledge.delete_document(first["document_id"])
    assert deleted["status"] == "deleted"
    assert not first_path.exists() and not second_path.exists()


@pytest.mark.parametrize("finish", ["cancel", "fail"])
def test_cancelled_or_failed_note_keeps_original_until_explicit_delete(app, finish):
    knowledge = app.state.services.get("knowledge")
    saved = knowledge.import_text("SYNTHETIC retained despite unavailable extraction",
        metadata=SourceMetadata(asset_role=["study-note"]), process=False)
    path = knowledge.original(saved["revision_id"])[0]
    if finish == "cancel":
        result = knowledge.cancel_job(saved["job"]["id"])
        assert result["state"] == "cancelled"
    else:
        # This synthetic profile contains no helper assets: exercise the actual
        # offline failure, rather than replacing extraction with a success.
        result = knowledge.run_job(saved["job"]["id"])
        assert result["state"] == "failed" and result["error_code"]
    assert knowledge.original(saved["revision_id"])[0].read_text() == "SYNTHETIC retained despite unavailable extraction"
    knowledge.delete_document(saved["document_id"])
    assert not path.exists()
    with pytest.raises(ApiError) as missing:
        knowledge.original(saved["revision_id"])
    assert missing.value.code == "original_missing"


def test_ordinary_cancelled_import_keeps_its_existing_discard_semantics(app):
    knowledge = app.state.services.get("knowledge")
    saved = knowledge.import_text("SYNTHETIC ordinary file input", process=False)
    path = knowledge.original(saved["revision_id"])[0]
    knowledge.cancel_job(saved["job"]["id"])
    assert not path.exists()


def test_note_http_create_edit_replay_and_historical_original_reopen(app):
    client = TestClient(app)
    assert client.get("/api/v1/library/notes").json() == {"items": []}
    first_request = {"title": "SYNTHETIC first title", "text": "SYNTHETIC original note body",
        "idempotency_key": "SYNTHETIC_note_create"}
    first = client.post("/api/v1/library/notes", json=first_request)
    assert first.status_code == 201, first.text
    first = first.json()
    assert first["ordinal"] == 1 and first["text"] == first_request["text"]
    assert first["reference"] == {"target": {"type": "note_revision", "id": first["revision_id"]}, "locator": None}
    assert client.post("/api/v1/library/notes", json=first_request).json() == first
    path = "/api/v1/library/notes/" + first["document_id"]
    update = {"title": "SYNTHETIC second title", "text": "SYNTHETIC revised note body",
        "expected_revision_id": first["revision_id"], "idempotency_key": "SYNTHETIC_note_edit"}
    edited = client.put(path, json=update)
    assert edited.status_code == 200, edited.text
    second = edited.json()
    assert second["ordinal"] == 2 and second["revision_id"] != first["revision_id"]
    assert client.put(path, json=update).json() == second
    app.state.services.get("knowledge").cleanup()
    assert client.get(path).json() == second
    historical = client.get(path, params={"revision_id": first["revision_id"]})
    assert historical.status_code == 200 and historical.json() == first
    reopened = create_app(app.state.services.paths.root)
    try:
        other = TestClient(reopened)
        assert other.get(path).json() == second
        assert other.get(path, params={"revision_id": first["revision_id"]}).json() == first
    finally:
        reopened.state.services.get("knowledge").index.close()


def test_note_stale_commands_and_delete_replay_never_overwrite_or_expose_originals(app):
    client = TestClient(app)
    create = {"title": "SYNTHETIC immutable", "text": "SYNTHETIC_PRIVATE_NOTE_BODY",
        "idempotency_key": "SYNTHETIC_cas_create"}
    first = client.post("/api/v1/library/notes", json=create).json()
    path = "/api/v1/library/notes/" + first["document_id"]
    edit = {"title": "SYNTHETIC next", "text": "SYNTHETIC newest body",
        "expected_revision_id": first["revision_id"], "idempotency_key": "SYNTHETIC_cas_edit"}
    second = client.put(path, json=edit).json()
    stale = client.put(path, json={**edit, "text": "SYNTHETIC stale overwrite", "idempotency_key": "SYNTHETIC_cas_stale"})
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "note_revision_conflict"
    conflict = client.put(path, json={**edit, "expected_revision_id": second["revision_id"]})
    assert conflict.status_code == 409 and conflict.json()["error"]["code"] == "idempotency_conflict"
    assert client.get(path).json() == second
    assert len(app.state.services.get("knowledge").get_document(first["document_id"])["revisions"]) == 2
    headers = {"Idempotency-Key": "SYNTHETIC_cas_delete"}
    stale = client.delete(path, params={"expected_revision_id": first["revision_id"]}, headers=headers)
    assert stale.status_code == 409 and "SYNTHETIC_PRIVATE_NOTE_BODY" not in stale.text
    originals = [app.state.services.get("knowledge").original(item["revision_id"])[0] for item in (first, second)]
    removed = client.delete(path, params={"expected_revision_id": second["revision_id"]}, headers=headers)
    assert removed.status_code == 200 and removed.json() == {
        "document_id": first["document_id"], "revision_id": second["revision_id"], "deleted": True}
    assert client.delete(path, params={"expected_revision_id": second["revision_id"]}, headers=headers).json() == removed.json()
    assert all(not original.exists() for original in originals)
    assert client.get(path).status_code == 404
    assert client.get(path, params={"revision_id": first["revision_id"]}).status_code == 404
    assert client.get("/api/v1/library/notes").json() == {"items": []}
    assert client.post("/api/v1/library/notes", json=create).status_code == 404


def create_note(client, key, *, project_id=None, headers=None):
    body = {"title": "SYNTHETIC title " + key, "text": "SYNTHETIC_PRIVATE_NOTE_" + key, "idempotency_key": key}
    if project_id is not None:
        body["project_id"] = project_id
    response = client.post("/api/v1/library/notes", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def edit_note(client, note, key):
    response = client.put("/api/v1/library/notes/" + note["document_id"], json={
        "title": "SYNTHETIC title " + key, "text": "SYNTHETIC_PRIVATE_NOTE_" + key,
        "expected_revision_id": note["revision_id"], "idempotency_key": key})
    assert response.status_code == 200, response.text
    return response.json()


def project_notes(client, identifier):
    response = client.get("/api/v1/library/notes", params={"project_id": identifier})
    assert response.status_code == 200, response.text
    return response.json()["items"]


def test_mounted_note_project_filter_tracks_current_membership_and_archive_without_copying(app):
    client = TestClient(app); services = app.state.services
    first_project = client.post("/api/v1/study/projects", json={"title": "SYNTHETIC CKD"}).json()
    second_project = client.post("/api/v1/study/projects", json={"title": "SYNTHETIC Transplant"}).json()
    first = create_note(client, "SYNTHETIC_project_note_one", project_id=first_project["id"])
    second = create_note(client, "SYNTHETIC_project_note_two", project_id=second_project["id"])
    personal = create_note(client, "SYNTHETIC_unscoped_note")
    assert [note["revision_id"] for note in project_notes(client, first_project["id"])] == [first["revision_id"]]
    assert [note["revision_id"] for note in project_notes(client, second_project["id"])] == [second["revision_id"]]
    assert len(client.get("/api/v1/library/notes").json()["items"]) == 3
    newer = edit_note(client, first, "SYNTHETIC_project_note_edit")
    assert [note["revision_id"] for note in project_notes(client, first_project["id"])] == [newer["revision_id"]]
    assert client.get("/api/v1/library/notes/" + first["document_id"], params={"revision_id": first["revision_id"]}).json() == first
    project_path = "/api/v1/study/projects/" + first_project["id"]
    current_project = client.get(project_path).json()
    archived = client.post(project_path + "/archive", json={"expected_revision": current_project["revision"]})
    assert archived.status_code == 200, archived.text
    newer = edit_note(client, newer, "SYNTHETIC_archived_note_edit")
    assert [note["revision_id"] for note in project_notes(client, first_project["id"])] == [newer["revision_id"]]
    current_project = client.get(project_path).json()
    membership = current_project["documents"][0]
    unlinked = client.delete(project_path + "/documents/" + newer["revision_id"],
        params={"expected_revision": current_project["revision"]})
    assert unlinked.status_code == 200, unlinked.text
    assert services.db.is_deleted("project_document", membership["id"])
    newest = edit_note(client, newer, "SYNTHETIC_unlinked_note_edit")
    assert project_notes(client, first_project["id"]) == []
    assert client.get("/api/v1/library/notes/" + first["document_id"]).json() == newest
    before = services.db.fetch_one("SELECT COUNT(*) AS n FROM knowledge_documents")["n"]
    refused = client.post("/api/v1/library/notes", json={"title": "SYNTHETIC refused", "text": "SYNTHETIC refused body",
        "idempotency_key": "SYNTHETIC_archived_note_refusal", "project_id": first_project["id"]})
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "project_archived"
    assert services.db.fetch_one("SELECT COUNT(*) AS n FROM knowledge_documents")["n"] == before
    other_path = "/api/v1/study/projects/" + second_project["id"]
    current_project = client.get(other_path).json()
    deleted = client.delete(other_path, params={"expected_revision": current_project["revision"]})
    assert deleted.status_code == 200, deleted.text
    assert services.db.is_deleted("project", second_project["id"])
    assert client.get("/api/v1/library/notes", params={"project_id": second_project["id"]}).status_code == 404
    assert client.get("/api/v1/library/notes/" + second["document_id"]).json() == second
    assert client.get("/api/v1/library/notes/" + personal["document_id"]).json() == personal


@pytest.mark.parametrize("revoked", ["display", "cache"])
def test_mounted_note_current_rights_and_canonical_tombstones_never_expose_original(app, revoked):
    client = TestClient(app); services = app.state.services
    project = client.post("/api/v1/study/projects", json={"title": "SYNTHETIC permissions"}).json()
    first = create_note(client, "SYNTHETIC_rights_first", project_id=project["id"])
    latest = edit_note(client, first, "SYNTHETIC_rights_latest")
    path = "/api/v1/library/notes/" + first["document_id"]
    row = services.db.fetch_one("SELECT rights_json FROM knowledge_revisions WHERE id=?", (latest["revision_id"],))
    # There is no dedicated rights-edit endpoint. Change the complete validated
    # canonical Rights record; never manufacture assessment policy/attempt rows.
    rights = Rights.model_validate_json(row["rights_json"], strict=True)
    denied_rights = rights.model_copy(update={revoked: False})
    services.db.execute("UPDATE knowledge_revisions SET rights_json=? WHERE id=?",
        (denied_rights.model_dump_json(), latest["revision_id"]))
    assert project_notes(client, project["id"]) == []
    assert client.get("/api/v1/library/notes").json() == {"items": []}
    denied = client.get(path)
    assert denied.status_code == 403 and latest["text"] not in denied.text and latest["title"] not in denied.text
    assert client.get(path, params={"revision_id": first["revision_id"]}).json() == first
    read_only = rights.model_copy(update={"model_input": False, "derivation": False})
    services.db.execute("UPDATE knowledge_revisions SET rights_json=? WHERE id=?",
        (read_only.model_dump_json(), latest["revision_id"]))
    assert client.get(path).json() == latest
    resolved = client.post("/api/v1/readers/resolve", json={"reference": latest["reference"]})
    assert resolved.status_code == 200 and not resolved.json()["capabilities"]["passage"]
    services.db.mark_deleted("knowledge-revision", latest["revision_id"])
    assert client.get(path).status_code == 404
    assert project_notes(client, project["id"]) == []
    assert client.get(path, params={"revision_id": first["revision_id"]}).json() == first
    services.db.mark_deleted("knowledge-document", first["document_id"])
    assert client.get(path, params={"revision_id": first["revision_id"]}).status_code == 404
    assert client.get("/api/v1/library/notes").json() == {"items": []}


def notes_study_context(app, client):
    from renulus.design_c_contracts import QuestionSnapshot, SavedTestVersion
    from renulus.storage import utc_now
    services = app.state.services
    version = SavedTestVersion(id="SYNTHETIC_notes_study_version", test_id="SYNTHETIC_notes_study_test", ordinal=1,
        origin="imported", review_quality="personal", status="ready", provenance={"method": "import"},
        created_at=utc_now(), terms="SYNTHETIC user-owned teaching material", items=[QuestionSnapshot(
            item_id="SYNTHETIC_notes_study_item", question_id="SYNTHETIC_notes_study_question", question_version="1",
            key_version="1", family_id="SYNTHETIC_notes_study_family", family_version="1", topic_id="general",
            stem="SYNTHETIC Study question", options=[{"id": "a", "text": "SYNTHETIC first choice"},
                {"id": "b", "text": "SYNTHETIC second choice"}],
            correct_option_ids=["a"], explanation="SYNTHETIC_PRIVATE_STUDY_KEY")])
    with services.db.transaction() as conn:
        services.get("saved_tests").publish_version(conn, version, title="SYNTHETIC Notes Study",
            provenance={"schema": "saved-test-provenance/1"}, idempotency_key="SYNTHETIC_notes_version_publish")
    started = client.post("/api/v1/assessment/test-attempts", json={"version": {"type": "saved_test_version", "id": version.id},
        "mode": "study"}, headers={"Idempotency-Key": "SYNTHETIC_notes_study_start"})
    assert started.status_code == 201, started.text
    attempt = started.json()
    exposed = client.post("/api/v1/assessment/test-attempts/" + attempt["id"] + "/help", json={
        "expected_revision": attempt["draft_revision"], "expected_policy_revision": attempt["policy"]["revision"],
        "item_id": version.items[0].item_id, "kind": "notes"}, headers={"Idempotency-Key": "SYNTHETIC_notes_study_help"})
    assert exposed.status_code == 200, exposed.text
    context = exposed.json()["context"]
    prepared = client.post("/api/v1/study/help-context", json=context)
    assert prepared.status_code == 200, prepared.text
    assert "SYNTHETIC_PRIVATE_STUDY_KEY" not in prepared.text
    assert services.db.fetch_one("SELECT id FROM assessment_attempt_exposure WHERE attempt_id=? AND item_id=? AND kind='notes'",
        (attempt["id"], context["item_id"]))
    return attempt, context


def change_study_draft(client, attempt, context):
    changed = client.put("/api/v1/assessment/test-attempts/" + attempt["id"] + "/draft", json={
        "expected_revision": attempt["draft_revision"], "position": 0,
        "answers": [{"item_id": context["item_id"], "option_ids": ["b"], "marked": False}]},
        headers={"Idempotency-Key": "SYNTHETIC_notes_draft_change"})
    assert changed.status_code == 200, changed.text
    assert changed.json()["draft_revision"] == attempt["draft_revision"] + 1


@pytest.mark.parametrize("operation", ["list", "get", "create", "edit", "delete"])
def test_mounted_note_stale_study_exposure_refuses_reads_and_commands(app, operation):
    client = TestClient(app); services = app.state.services
    first = create_note(client, "SYNTHETIC_study_retained_note")
    attempt, context = notes_study_context(app, client)
    headers = {"X-Renulus-Study-Context": json.dumps(context)}
    assert client.get("/api/v1/library/notes", headers=headers).status_code == 200
    change_study_draft(client, attempt, context)
    path = "/api/v1/library/notes/" + first["document_id"]
    if operation == "list":
        refused = client.get("/api/v1/library/notes", headers=headers)
    elif operation == "get":
        refused = client.get(path, headers=headers)
    elif operation == "create":
        refused = client.post("/api/v1/library/notes", json={"title": "SYNTHETIC stale new", "text": "SYNTHETIC stale body",
            "idempotency_key": "SYNTHETIC_stale_create"}, headers=headers)
    elif operation == "edit":
        refused = client.put(path, json={"title": "SYNTHETIC stale edit", "text": "SYNTHETIC stale body",
            "expected_revision_id": first["revision_id"], "idempotency_key": "SYNTHETIC_stale_edit"}, headers=headers)
    else:
        refused = client.delete(path, params={"expected_revision_id": first["revision_id"]},
            headers={**headers, "Idempotency-Key": "SYNTHETIC_stale_delete"})
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "revision_conflict"
    assert first["text"] not in refused.text and "SYNTHETIC_PRIVATE_STUDY_KEY" not in refused.text
    assert client.get(path).json() == first
    assert services.db.fetch_one("SELECT COUNT(*) AS n FROM knowledge_revisions")["n"] == 1
    assert services.db.fetch_one("SELECT COUNT(*) AS n FROM deletion_ledger")["n"] == 0


@pytest.mark.parametrize("operation", ["list", "get"])
def test_mounted_note_read_rechecks_study_after_actual_original_read(app, monkeypatch, operation):
    client = TestClient(app)
    first = create_note(client, "SYNTHETIC_study_read_note")
    attempt, context = notes_study_context(app, client)
    notes = app.state.services.get("notes")
    actual_read = getattr(notes, operation)
    reads = []
    def read_then_change(*args, **kwargs):
        result = actual_read(*args, **kwargs); reads.append(result)
        with ThreadPoolExecutor(max_workers=1) as worker:
            worker.submit(Context().run, change_study_draft, client, attempt, context).result(timeout=15)
        return result
    monkeypatch.setattr(notes, operation, read_then_change)
    path = "/api/v1/library/notes" + ("/" + first["document_id"] if operation == "get" else "")
    refused = client.get(path, headers={"X-Renulus-Study-Context": json.dumps(context)})
    assert len(reads) == 1
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "revision_conflict"
    assert first["text"] not in refused.text and first["title"] not in refused.text


@pytest.mark.parametrize("operation", ["create", "edit"])
def test_mounted_note_publication_rechecks_study_before_actual_import(app, monkeypatch, operation):
    client = TestClient(app); services = app.state.services
    first = create_note(client, "SYNTHETIC_study_saved_note")
    attempt, context = notes_study_context(app, client)
    knowledge = services.get("knowledge"); actual_import = knowledge.import_text
    imports = []
    def change_before_import(*args, **kwargs):
        imports.append(operation)
        with ThreadPoolExecutor(max_workers=1) as worker:
            worker.submit(Context().run, change_study_draft, client, attempt, context).result(timeout=15)
        return actual_import(*args, **kwargs)
    monkeypatch.setattr(knowledge, "import_text", change_before_import)
    body = {"title": "SYNTHETIC forbidden publication", "text": "SYNTHETIC_UNPUBLISHED_NOTE",
        "idempotency_key": "SYNTHETIC_late_note_import"}
    path = "/api/v1/library/notes"
    if operation == "edit":
        path += "/" + first["document_id"]; body["expected_revision_id"] = first["revision_id"]
    refused = client.request("PUT" if operation == "edit" else "POST", path, json=body,
        headers={"X-Renulus-Study-Context": json.dumps(context)})
    assert imports == [operation]
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "revision_conflict"
    assert services.db.fetch_one("SELECT COUNT(*) AS n FROM knowledge_revisions")["n"] == 1
    assert services.db.fetch_one("SELECT id FROM knowledge_jobs WHERE idempotency_key=?", (body["idempotency_key"],)) is None
    assert client.get("/api/v1/library/notes/" + first["document_id"]).json() == first


@pytest.mark.parametrize("format_version", [1, 2])
def test_mounted_note_delete_and_older_full_zip_reopen_cannot_restore_revisions_or_membership(app, format_version):
    client = TestClient(app); services = app.state.services
    knowledge = services.get("knowledge")
    project = client.post("/api/v1/study/projects", json={"title": "SYNTHETIC Notes recovery"}).json()
    first = create_note(client, "SYNTHETIC_zip_first", project_id=project["id"])
    latest = edit_note(client, first, "SYNTHETIC_zip_latest")
    retained = create_note(client, "SYNTHETIC_zip_retained")
    originals = [knowledge.original(note["revision_id"])[0] for note in (first, latest)]
    retained_path = knowledge.original(retained["revision_id"])[0]
    retained_sha256 = hashlib.sha256(retained_path.read_bytes()).hexdigest()
    assert [note["revision_id"] for note in project_notes(client, project["id"])] == [latest["revision_id"]]
    backup = client.get("/api/v1/data/backup", params={"format_version": format_version})
    assert backup.status_code == 200, backup.text
    assert backup.headers["X-Renulus-Backup-Format"] == str(format_version)
    # Inspect only the Notes-owned descriptors/bytes in the actual full archive.
    with zipfile.ZipFile(BytesIO(backup.content)) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        entries = {entry["revision_id"]: entry for entry in manifest["originals"]}
        for note in (first, latest, retained):
            entry = entries[note["revision_id"]]
            expected = note["text"].encode("utf-8")
            assert archive.read(entry["path"]) == expected
            assert entry["sha256"] == hashlib.sha256(expected).hexdigest()
    (services.paths.cache / ("notes-before-delete-" + str(format_version) + ".zip")).write_bytes(backup.content)
    path = "/api/v1/library/notes/" + first["document_id"]
    deleted = client.delete(path, params={"expected_revision_id": latest["revision_id"]},
        headers={"Idempotency-Key": "SYNTHETIC_zip_note_delete"})
    assert deleted.status_code == 200, deleted.text
    assert all(not original.exists() for original in originals)
    assert services.db.is_deleted("knowledge-document", first["document_id"])
    # The owner uses the document tombstone plus deleted revision state; typed
    # recovery propagates that parent deletion without requiring extra markers.
    for note in (first, latest):
        assert client.get(path, params={"revision_id": note["revision_id"]}).status_code == 404
    assert project_notes(client, project["id"]) == []
    preview = client.post("/api/v1/data/backup/preview", params={"format_version": format_version},
        content=backup.content, headers={"Content-Type": "application/zip"})
    assert preview.status_code == 200, preview.text
    preview = preview.json()
    restored = client.post("/api/v1/data/backup/restore", json={
        "preview_token": preview["preview_token"], "confirmed_exported_at": preview["exported_at"],
        "acknowledge_deletion_limits": True})
    assert restored.status_code == 200, restored.text
    assert restored.json()["excluded_originals"] == 2
    assert restored.json()["restored_originals"] == 1
    assert all(not original.exists() for original in originals)
    assert client.get(path).status_code == 404
    for note in (first, latest):
        assert client.get(path, params={"revision_id": note["revision_id"]}).status_code == 404
    assert project_notes(client, project["id"]) == []
    assert client.get("/api/v1/study/projects/" + project["id"]).json()["documents"] == []
    assert client.get("/api/v1/library/notes/" + retained["document_id"]).json() == retained
    assert hashlib.sha256(retained_path.read_bytes()).hexdigest() == retained_sha256
    reopened = create_app(services.paths.root)
    try:
        other = TestClient(reopened)
        assert other.get(path).status_code == 404
        for note in (first, latest):
            assert other.get(path, params={"revision_id": note["revision_id"]}).status_code == 404
        assert project_notes(other, project["id"]) == []
        assert other.get("/api/v1/study/projects/" + project["id"]).json()["documents"] == []
        assert other.get("/api/v1/library/notes/" + retained["document_id"]).json() == retained
        assert all(not original.exists() for original in originals)
        assert hashlib.sha256(retained_path.read_bytes()).hexdigest() == retained_sha256
    finally:
        reopened.state.services.get("knowledge").index.close()
