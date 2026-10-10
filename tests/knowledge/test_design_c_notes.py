# SPDX-License-Identifier: MIT
"""Saved notes through real Knowledge originals, migrations and owner APIs."""
import socket

from fastapi.testclient import TestClient
import pytest

from renulus.contracts import ApiError
from renulus.knowledge.models import SourceMetadata
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
    from renulus.knowledge.note_api import create_router
    app.include_router(create_router(app.state.services), prefix="/api/v1")
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
        reopened.include_router(create_router(reopened.state.services), prefix="/api/v1")
        other = TestClient(reopened)
        assert other.get(path).json() == second
        assert other.get(path, params={"revision_id": first["revision_id"]}).json() == first
    finally:
        reopened.state.services.get("knowledge").index.close()


def test_note_stale_commands_and_delete_replay_never_overwrite_or_expose_originals(app):
    from renulus.knowledge.note_api import create_router
    app.include_router(create_router(app.state.services), prefix="/api/v1")
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
