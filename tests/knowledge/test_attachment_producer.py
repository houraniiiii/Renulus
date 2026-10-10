# SPDX-License-Identifier: MIT
"""Actual conversation retention, Knowledge003 persistence and reader calls."""
from contextlib import closing
from io import BytesIO
import json
from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient
import pytest

from renulus.contracts import ApiError
from renulus.design_c_contracts import Identity
from renulus.knowledge.attachment_api import create_router
from renulus.knowledge.attachment_models import AttachmentRemoval, AttachmentUpload
from renulus.knowledge.models import own_text_rights
from renulus.learn.conversation_models import NewConversation
from renulus.server import create_app
from renulus.storage.assessment_policy import advance_policy, policy_snapshot
from renulus.storage.invalidation import bump_context_epoch, context_epoch_in


@pytest.fixture
def app(tmp_path, monkeypatch):
    import socket
    connect = socket.socket.connect
    def forbidden(instance, address):
        if isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"}:
            return connect(instance, address)
        raise AssertionError("Attachment tests must not use an external network or provider")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    result = create_app(tmp_path / "synthetic-ordinary-attachments")
    result.include_router(create_router(result.state.services), prefix="/api/v1")
    try:
        yield result
    finally:
        result.state.services.get("knowledge").index.close()


def conversation(app, *, temporary=False, kind="learning"):
    return app.state.services.get("conversations").create(NewConversation(
        kind=kind, temporary=temporary, title="SYNTHETIC attachment chat"))


def upload_request(app, chat, *, key="SYNTHETIC_upload_001", filename="SYNTHETIC.md", rights=None):
    with closing(app.state.services.db.connect()) as conn:
        return AttachmentUpload(conversation=chat["identity"], expected_conversation_revision=chat["revision"],
            expected_policy_revision=policy_snapshot(conn)["revision"], expected_context_epoch=context_epoch_in(conn),
            idempotency_key=key, filename=filename, title="SYNTHETIC study file", rights=rights or own_text_rights(), metadata={})


def read_body(receipt):
    return {"reference": receipt["reference"], "conversation": receipt["conversation"]}


def test_saved_upload_persists_exact_original_sidecar_and_reopens_without_extraction(app):
    services = app.state.services
    chat = conversation(app)
    request = upload_request(app, chat)
    client = TestClient(app)
    data = b"# SYNTHETIC AKI\n\nStudy reversible causes."
    response = client.post("/api/v1/attachments", content=data,
        headers={"x-renulus-attachment-options": request.model_dump_json()})
    assert response.status_code == 201, response.text
    receipt = response.json()
    assert receipt["retention"] == "saved" and receipt["conversation_revision"] == chat["revision"] + 1
    assert receipt["extraction_state"] == receipt["index_state"] == "not_requested"
    assert "original_path" not in response.text and "data" not in receipt
    original = services.db.fetch_one("SELECT * FROM knowledge_attachment_originals WHERE attachment_id=?", (receipt["id"],))
    expected = services.paths.library / "attachments" / receipt["id"] / "original.md"
    assert Path(original["original_path"]) == expected and expected.read_bytes() == data
    metadata = services.db.fetch_one("SELECT * FROM knowledge_attachment_metadata WHERE attachment_id=?", (receipt["id"],))
    assert metadata["filename"] == "SYNTHETIC.md" and metadata["source_id"] == "R02"
    assert json.loads(metadata["metadata_json"])["original_sha256"] == receipt["original"]["sha256"]
    assert metadata["preview_json"] is None and metadata["extraction_json"] is None
    result = client.post("/api/v1/readers/resolve", json=read_body(receipt))
    assert result.status_code == 200 and result.json()["payload"]["blocks"][0]["text"] == "SYNTHETIC AKI"
    reader = result.json()
    draft_url = "/api/v1/conversations/learning/" + chat["identity"]["id"] + "/draft"
    prior = client.put(draft_url, json={"text": "SYNTHETIC prior draft", "content_refs": [],
        "expected_revision": receipt["conversation_revision"]})
    assert prior.status_code == 200
    item = reader["payload"]["blocks"][1]
    passage = client.post("/api/v1/readers/passage", json={**read_body(receipt), "locator": item["locator"],
        "original_sha256": reader["original"]["sha256"], "expected_policy_revision": reader["policy_revision"],
        "expected_context_epoch": reader["context_epoch"]})
    assert passage.status_code == 200 and passage.json()["text"] == "Study reversible causes."
    merged = client.put(draft_url, json={"text": prior.json()["text"] + "\n\n" + passage.json()["text"],
        "content_refs": [passage.json()["reference"]], "expected_revision": prior.json()["conversation_revision"]})
    assert merged.status_code == 200
    saved_draft = client.get(draft_url).json()
    assert saved_draft["text"] == "SYNTHETIC prior draft\n\nStudy reversible causes."
    assert saved_draft["content_refs"] == [passage.json()["reference"]]
    assert services.db.fetch_one("SELECT COUNT(*) AS count FROM learn_messages WHERE thread_id=?", (chat["identity"]["id"],))["count"] == 0
    services.db.execute("UPDATE knowledge_attachments SET extraction_state='failed',index_state='failed' WHERE id=?", (receipt["id"],))
    assert client.post("/api/v1/readers/original", json=read_body(receipt)).content == data
    reopened = create_app(services.paths.root)
    try:
        assert TestClient(reopened).post("/api/v1/readers/original", json=read_body(receipt)).content == data
    finally:
        reopened.state.services.get("knowledge").index.close()


@pytest.mark.parametrize("kind", ["learning", "case"])
def test_temporary_upload_keeps_bytes_and_commands_out_of_canonical_storage(app, kind):
    services = app.state.services
    chat = conversation(app, temporary=True, kind=kind)
    rights = own_text_rights().model_copy(update={"cache": False})
    request = upload_request(app, chat, rights=rights)
    data = b"SYNTHETIC temporary dialysis study"
    receipt = services.get("knowledge_attachments").upload(request, data)
    assert receipt["retention"] == "temporary"
    assert not services.db.fetch_one("SELECT 1 FROM knowledge_attachments WHERE id=?", (receipt["id"],))
    assert not services.db.fetch_one("SELECT 1 FROM conversation_commands WHERE idempotency_key=?", (request.idempotency_key,))
    assert not (services.paths.library / "attachments" / receipt["id"]).exists()
    client = TestClient(app)
    result = client.post("/api/v1/readers/resolve", json=read_body(receipt))
    assert result.status_code == 200 and result.json()["authority"] == "knowledge"
    assert client.post("/api/v1/readers/original", json=read_body(receipt)).content == data
    with services.db.transaction() as conn:
        result = services.get("knowledge_attachments").authorize_in(conn, receipt["id"],
            context=Identity.model_validate(chat["identity"]))
        assert result == {"allowed": True}
        assert services.get("knowledge_attachments").authorize_in(conn, receipt["id"]) == {
            "allowed": False, "reason": "not_found"}
    reopened = create_app(services.paths.root)
    try:
        assert TestClient(reopened).post("/api/v1/readers/resolve", json=read_body(receipt)).status_code == 404
    finally:
        reopened.state.services.get("knowledge").index.close()


@pytest.mark.parametrize("temporary", [False, True])
def test_retry_is_idempotent_and_different_bytes_or_revision_do_not_duplicate(app, temporary):
    services = app.state.services
    chat = conversation(app, temporary=temporary)
    request = upload_request(app, chat)
    owner = services.get("knowledge_attachments")
    receipt = owner.upload(request, b"SYNTHETIC original")
    assert owner.upload(request, b"SYNTHETIC original") == receipt
    assert services.get("conversations").get("learning", chat["identity"]["id"])["revision"] == receipt["conversation_revision"]
    with pytest.raises(ApiError) as caught:
        owner.upload(request, b"SYNTHETIC different")
    assert caught.value.code == "idempotency_conflict"
    stale = request.model_copy(update={"idempotency_key": "SYNTHETIC_stale_002"})
    with pytest.raises(ApiError) as caught:
        owner.upload(stale, b"SYNTHETIC second")
    assert caught.value.code == "conversation_revision_conflict"
    assert len(owner._volatile) == (1 if temporary else 0)
    rows = services.db.fetch_all("SELECT id FROM knowledge_attachments")
    assert len(rows) == (0 if temporary else 1)


def test_policy_and_context_changes_during_upload_refuse_publication(app, monkeypatch):
    services = app.state.services
    chat = conversation(app)
    request = upload_request(app, chat)
    import renulus.knowledge.attachments as module
    real = module.admit
    def changed(filename, data, **kwargs):
        result = real(filename, data, **kwargs)
        with services.db.transaction() as conn:
            bump_context_epoch(conn)
        return result
    monkeypatch.setattr(module, "admit", changed)
    with pytest.raises(ApiError) as caught:
        services.get("knowledge_attachments").upload(request, b"SYNTHETIC stale context")
    assert caught.value.code == "attachment_context_changed"
    assert not services.db.fetch_all("SELECT id FROM knowledge_attachments")
    assert not (services.paths.library / "attachments").exists()
    current = upload_request(app, chat)
    monkeypatch.setattr(module, "admit", real)
    with services.db.transaction() as conn:
        advance_policy(conn)
    with pytest.raises(ApiError) as caught:
        services.get("knowledge_attachments").upload(current, b"SYNTHETIC stale policy")
    assert caught.value.code == "assistance_changed"


def test_real_original_write_failure_leaves_no_attachment_or_conversation_revision(app, monkeypatch):
    services = app.state.services
    chat = conversation(app)
    import renulus.knowledge.attachments as module
    def failed(self, conn, record, path):
        assert path.read_bytes() == b"SYNTHETIC disk rollback"
        raise sqlite3.OperationalError("SYNTHETIC insert failure after original write")
    monkeypatch.setattr(module.KnowledgeAttachments, "_insert_in", failed)
    with pytest.raises(sqlite3.OperationalError):
        services.get("knowledge_attachments").upload(upload_request(app, chat), b"SYNTHETIC disk rollback")
    assert not services.db.fetch_all("SELECT id FROM knowledge_attachments")
    assert not list((services.paths.library / "attachments").iterdir())
    assert services.get("conversations").get("learning", chat["identity"]["id"])["revision"] == chat["revision"]


@pytest.mark.parametrize("temporary", [False, True])
def test_remove_revokes_reader_and_cleans_only_owned_original_with_safe_retry(app, tmp_path, temporary):
    services = app.state.services
    chat = conversation(app, temporary=temporary)
    upload = upload_request(app, chat)
    receipt = services.get("knowledge_attachments").upload(upload, b"SYNTHETIC removed study file")
    sentinel = services.paths.library / "SYNTHETIC-unowned.txt"
    sentinel.write_bytes(b"SYNTHETIC preserve")
    removal = AttachmentRemoval(conversation=chat["identity"], expected_conversation_revision=receipt["conversation_revision"],
        expected_policy_revision=upload.expected_policy_revision, expected_context_epoch=upload.expected_context_epoch,
        idempotency_key="SYNTHETIC_remove_001", expected_attachment_revision=1)
    owner = services.get("knowledge_attachments")
    result = owner.remove(receipt["id"], removal)
    assert owner.remove(receipt["id"], removal) == result
    assert sentinel.read_bytes() == b"SYNTHETIC preserve"
    assert not (services.paths.library / "attachments" / receipt["id"]).exists()
    assert TestClient(app).post("/api/v1/readers/original", json=read_body(receipt)).status_code == 404
    assert services.db.is_deleted("attachment", receipt["id"]) is not temporary
    assert services.db.is_deleted("attachment_original", receipt["original"]["id"]) is not temporary
    with pytest.raises(ApiError):
        owner.upload(upload, b"SYNTHETIC removed study file")


def test_saved_upload_requires_cache_and_raw_api_rejects_path_and_invalid_signature(app):
    chat = conversation(app)
    rights = own_text_rights().model_copy(update={"cache": False})
    request = upload_request(app, chat, rights=rights)
    client = TestClient(app)
    denied = client.post("/api/v1/attachments", content=b"SYNTHETIC no cache", headers={
        "x-renulus-attachment-options": request.model_dump_json()})
    assert denied.status_code == 403
    bad = request.model_dump(mode="json"); bad["filename"] = "../SYNTHETIC.md"
    assert client.post("/api/v1/attachments", content=b"SYNTHETIC", headers={
        "x-renulus-attachment-options": json.dumps(bad)}).status_code == 422
    pdf = upload_request(app, chat, filename="SYNTHETIC.pdf")
    assert client.post("/api/v1/attachments", content=b"SYNTHETIC not PDF", headers={
        "x-renulus-attachment-options": pdf.model_dump_json()}).status_code == 422
    assert not app.state.services.db.fetch_all("SELECT id FROM knowledge_attachments")


def test_delete_chat_plan_tombstones_processing_and_rolls_back_without_deleting_bytes(app, monkeypatch):
    services = app.state.services
    chat = conversation(app)
    owner = services.get("knowledge_attachments")
    receipt = owner.upload(upload_request(app, chat), b"SYNTHETIC delete transaction")
    path = services.paths.library / "attachments" / receipt["id"] / "original.md"
    services.db.execute("UPDATE knowledge_attachment_metadata SET processing_json=? WHERE attachment_id=?",
        (json.dumps({"schema_version": "SYNTHETIC_processing"}), receipt["id"]))
    conn = services.db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        def forbidden(*args, **kwargs):
            raise AssertionError("delete_chat_in cannot use files or nested connections")
        with monkeypatch.context() as patch:
            patch.setattr(services.db, "connect", forbidden)
            for method in ("resolve", "open", "stat", "exists", "is_file", "mkdir"):
                patch.setattr(Path, method, forbidden)
            plan = owner.delete_chat_in(conn, "learning", chat["identity"]["id"])
        assert plan == [{"attachment_id": receipt["id"], "relative_directory": "library/attachments/" + receipt["id"]}]
        assert path.read_bytes() == b"SYNTHETIC delete transaction"
        assert not conn.execute("SELECT 1 FROM knowledge_attachment_metadata WHERE attachment_id=?", (receipt["id"],)).fetchone()
        assert conn.execute("SELECT 1 FROM deletion_ledger WHERE entity_type='attachment_original' AND entity_id=?",
            (receipt["original"]["id"],)).fetchone()
    finally:
        conn.rollback(); conn.close()
    assert services.db.fetch_one("SELECT processing_json FROM knowledge_attachment_metadata WHERE attachment_id=?", (receipt["id"],))
    assert not services.db.is_deleted("attachment", receipt["id"])
    with services.db.transaction() as conn:
        committed = owner.delete_chat_in(conn, "learning", chat["identity"]["id"])
    assert committed == plan and path.exists()
    assert services.db.is_deleted("attachment", receipt["id"])
    assert TestClient(app).post("/api/v1/readers/original", json=read_body(receipt)).status_code == 404
    # Parent's live Delete file journal consumes the inert plan. This service
    # helper is post-commit cleanup only; the hook itself never deletes bytes.
    owner.cleanup_deleted([entry["attachment_id"] for entry in plan])
    assert not path.exists()


def test_volatile_forget_releases_payload_and_retry_receipts_without_durable_deletion(app):
    services = app.state.services
    chat = conversation(app, temporary=True)
    owner = services.get("knowledge_attachments")
    assert services.get("chat_attachments") is owner
    request = upload_request(app, chat)
    receipt = owner.upload(request, b"SYNTHETIC volatile forget")
    owner.discard_volatile("learning", chat["identity"]["id"])
    assert not owner._volatile and not owner._volatile_commands
    assert not services.db.fetch_one("SELECT 1 FROM deletion_ledger WHERE entity_id=?", (receipt["id"],))
    assert not (services.paths.library / "attachments").exists()
    assert TestClient(app).post("/api/v1/readers/original", json=read_body(receipt)).status_code == 404


def test_promotion_stage_preserves_volatile_bytes_until_caller_commit_or_rollback(app):
    services = app.state.services
    chat = conversation(app, temporary=True)
    owner, conversations = services.get("knowledge_attachments"), services.get("conversations")
    receipt = owner.upload(upload_request(app, chat), b"SYNTHETIC staged promotion")
    path = services.paths.library / "attachments" / receipt["id"] / "original.md"
    with owner.promotion_guard(), conversations._lock, conversations.cases._lock:
        conn = services.db.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            lease = owner.prepare_promotion_in(conn, "learning", chat["identity"]["id"])
            assert path.exists() and receipt["id"] in owner._volatile
            assert conn.execute("SELECT 1 FROM knowledge_attachments WHERE id=?", (receipt["id"],)).fetchone()
        finally:
            conn.rollback(); conn.close()
        lease.rollback()
        assert not path.exists() and receipt["id"] in owner._volatile
        with services.db.transaction() as conn:
            lease = owner.prepare_promotion_in(conn, "learning", chat["identity"]["id"])
            # Exercise the actual caller-connection Learn owner, not a fabricated
            # chat table. Zeno still owns wiring this into Conversation.promote.
            conversations.learn.create_thread(chat["title"], conn=conn, identifier=chat["identity"]["id"])
            conversations._insert_sidecar(conn, "learning", chat["identity"]["id"])
        lease.commit()
        conversations._temporary.pop(("learning", chat["identity"]["id"]))
    assert receipt["id"] not in owner._volatile and path.read_bytes() == b"SYNTHETIC staged promotion"
    assert TestClient(app).post("/api/v1/readers/original", json=read_body(receipt)).content == b"SYNTHETIC staged promotion"


def test_promotion_refuses_ungranted_cache_before_any_file_write(app):
    services = app.state.services
    chat = conversation(app, temporary=True)
    owner = services.get("knowledge_attachments")
    owner.upload(upload_request(app, chat, rights=own_text_rights().model_copy(update={"cache": False})), b"SYNTHETIC cache denied")
    with owner.promotion_guard(), services.get("conversations")._lock, services.db.transaction() as conn:
        with pytest.raises(ApiError) as caught:
            owner.prepare_promotion_in(conn, "learning", chat["identity"]["id"])
        assert caught.value.code == "attachment_cache_denied"
    assert not (services.paths.library / "attachments").exists()


def test_ordinary_upload_all_required_formats_connect_to_actual_reader_and_native_assets(app):
    from docx import Document
    from openpyxl import Workbook
    from PIL import Image
    from test_reader_formats import synthetic_pdf
    docx = Document(); docx.add_heading("SYNTHETIC transplant study", 1)
    table = docx.add_table(rows=1, cols=2)
    table.cell(0, 0).text, table.cell(0, 1).text = "SYNTHETIC marker", "0015"
    document = BytesIO(); docx.save(document)
    xlsx = Workbook(); xlsx.active.append(["SYNTHETIC topic", 0.15]); xlsx.active["B1"].number_format = "0%"
    workbook = BytesIO(); xlsx.save(workbook)
    files = {"SYNTHETIC.pdf": synthetic_pdf(), "SYNTHETIC.docx": document.getvalue(),
        "SYNTHETIC.csv": b"topic,value\nSYNTHETIC CKD,15%\n", "SYNTHETIC.xlsx": workbook.getvalue(),
        "SYNTHETIC.md": b"# SYNTHETIC AKI\n\n| Topic | Value |\n| --- | --- |\n| CKD | 15% |",
        "SYNTHETIC.html": b'<table><tr><td>SYNTHETIC dialysis</td></tr></table><script>fetch("/api/v1/health")</script>',
        "SYNTHETIC.xml": b'<study>SYNTHETIC glomerular study</study>'}
    for format, extension in (("PNG", "png"), ("JPEG", "jpg"), ("TIFF", "tiff")):
        image = BytesIO(); Image.new("RGB", (20, 20), "white").save(image, format=format)
        files["SYNTHETIC." + extension] = image.getvalue()
    services = app.state.services
    chat, client = conversation(app), TestClient(app)
    for number, (filename, data) in enumerate(files.items()):
        request = upload_request(app, chat, key=f"SYNTHETIC_format_{number:03}", filename=filename)
        uploaded = client.post("/api/v1/attachments", content=data, headers={"x-renulus-attachment-options": request.model_dump_json()})
        assert uploaded.status_code == 201, uploaded.text
        receipt = uploaded.json()
        chat = services.get("conversations").get("learning", chat["identity"]["id"])
        result = client.post("/api/v1/readers/resolve", json=read_body(receipt))
        assert result.status_code == 200, result.text
        body = result.json()
        assert body["preview_state"] == "ready", (filename, body["error"])
        assert client.post("/api/v1/readers/original", json=read_body(receipt)).content == data
        assert "fetch(" not in json.dumps(body["payload"])
        if body["payload"]["asset_id"]:
            asset = client.post("/api/v1/readers/asset", json={**read_body(receipt),
                "asset_id": body["payload"]["asset_id"], "original_sha256": body["original"]["sha256"]})
            assert asset.status_code == 200 and asset.content.startswith(b"\x89PNG\r\n\x1a\n")
        if receipt["media_type"].startswith("image/"):
            assert body["capabilities"]["ocr"] is False and body["capabilities"]["passage"] is False
    listed = client.get("/api/v1/attachments/learning/" + chat["identity"]["id"])
    assert listed.status_code == 200 and len(listed.json()["items"]) == len(files)
    assert all(item["access"] == {"allowed": True} for item in listed.json()["items"])
