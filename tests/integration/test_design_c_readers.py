# SPDX-License-Identifier: MIT
"""Connected real router/SQLite/original/parser checks, without providers."""
import hashlib
import json

from fastapi.testclient import TestClient
import pytest

from renulus.contracts import ApiError
from renulus.knowledge.models import own_text_rights
from renulus.knowledge.reader_api import create_router
from renulus.server import create_app


@pytest.fixture
def reader_app(tmp_path, monkeypatch):
    import socket
    connect = socket.socket.connect
    def forbidden(instance, address):
        # Windows asyncio uses a localhost self-pipe even for in-process ASGI.
        if isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"}:
            return connect(instance, address)
        raise AssertionError("Reader tests cannot use an external network/provider")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    app = create_app(tmp_path / "synthetic-reader-profile")
    app.include_router(create_router(app.state.services), prefix="/api/v1")
    return app


def saved_source(app, tmp_path, filename, data):
    path = tmp_path / filename; path.write_bytes(data)
    result = app.state.services.get("knowledge").import_file(path, rights=own_text_rights(), process=False)
    return {"target": {"type": "library_revision", "id": result["revision_id"]}}


def test_queued_then_failed_original_reads_and_bounded_passage_use_actual_router(reader_app, tmp_path):
    reference = saved_source(reader_app, tmp_path, "SYNTHETIC.md", b"# SYNTHETIC AKI\n\nStudy reversible causes.")
    client = TestClient(reader_app)  # No lifespan: no background extraction/provider jobs.
    response = client.post("/api/v1/readers/resolve", json={"reference": reference})
    assert response.status_code == 200
    body = response.json()
    assert body["preview_state"] == "ready" and not body["capabilities"]["passage"]
    item = body["payload"]["blocks"][1]
    selected = client.post("/api/v1/readers/passage", json={"reference": reference,
        "original_sha256": body["original"]["sha256"], "locator": item["locator"]})
    assert item["text"] == "Study reversible causes."
    assert selected.status_code == 503 and selected.json()["error"]["code"] == "reader_policy_unavailable"
    db = reader_app.state.services.db
    db.execute("UPDATE knowledge_revisions SET status='failed' WHERE id=?", (reference["target"]["id"],))
    assert client.post("/api/v1/readers/resolve", json={"reference": reference}).json()["preview_state"] == "ready"
    original = client.post("/api/v1/readers/original", json={"reference": reference})
    assert original.content == b"# SYNTHETIC AKI\n\nStudy reversible causes."
    assert original.headers["content-type"] == "application/octet-stream"
    assert original.headers["content-security-policy"] == "default-src 'none'; sandbox"
    assert "attachment;" in original.headers["content-disposition"]
    path, _ = reader_app.state.services.get("knowledge").original(reference["target"]["id"])
    assert path.read_bytes() == original.content


def test_display_and_model_permissions_are_independent_and_delete_removes_read_authority(reader_app, tmp_path):
    reference = saved_source(reader_app, tmp_path, "SYNTHETIC.csv", b"topic,value\nSYNTHETIC CKD,15%\n")
    client = TestClient(reader_app); db = reader_app.state.services.db
    rights = own_text_rights().model_dump(); rights.update(index=False, embedding=False, model_input=False)
    db.execute("UPDATE knowledge_revisions SET rights_json=? WHERE id=?", (json.dumps(rights), reference["target"]["id"]))
    body = client.post("/api/v1/readers/resolve", json={"reference": reference}).json()
    assert body["preview_state"] == "ready" and not body["capabilities"]["passage"]
    denied = client.post("/api/v1/readers/passage", json={"reference": reference,
        "original_sha256": body["original"]["sha256"], "locator": {"kind": "table", "format": "csv",
            "first_row": 2, "last_row": 2, "first_column": 1, "last_column": 2}})
    assert denied.status_code == 503  # Shared policy is a real unresolved prerequisite.
    rights["display"] = False
    db.execute("UPDATE knowledge_revisions SET rights_json=? WHERE id=?", (json.dumps(rights), reference["target"]["id"]))
    assert client.post("/api/v1/readers/original", json={"reference": reference}).status_code == 403
    row = db.fetch_one("SELECT document_id FROM knowledge_revisions WHERE id=?", (reference["target"]["id"],))
    reader_app.state.services.get("knowledge").delete_document(row["document_id"])
    assert client.post("/api/v1/readers/resolve", json={"reference": reference}).status_code == 404


def test_malicious_html_is_inert_and_invalid_xml_reports_failure_while_retaining_original(reader_app, tmp_path):
    reference = saved_source(reader_app, tmp_path, "SYNTHETIC.html", b'<p>SYNTHETIC dialysis</p><script>fetch("/api/v1/cases/saved")</script><img src="file:///C:/no-read">')
    client = TestClient(reader_app)
    response = client.post("/api/v1/readers/resolve", json={"reference": reference})
    assert response.status_code == 200 and "SYNTHETIC dialysis" in response.text
    assert "fetch(" not in response.text and "file:///" not in response.text
    xml = saved_source(reader_app, tmp_path, "SYNTHETIC.xml", b'<!DOCTYPE x [<!ENTITY e "unsafe">]><x>&e;</x>')
    result = client.post("/api/v1/readers/resolve", json={"reference": xml}).json()
    assert result["preview_state"] == "failed" and result["error"]["code"] == "reader_xml_invalid"
    assert client.post("/api/v1/readers/original", json={"reference": xml}).status_code == 200


def test_hash_mismatch_missing_original_and_uninstalled_attachment_schema_are_honest(reader_app, tmp_path):
    reference = saved_source(reader_app, tmp_path, "SYNTHETIC.txt", b"SYNTHETIC transplant note")
    client = TestClient(reader_app); db = reader_app.state.services.db
    row = db.fetch_one("SELECT original_path FROM knowledge_revisions WHERE id=?", (reference["target"]["id"],))
    from pathlib import Path
    path = Path(row["original_path"]); path.write_bytes(b"SYNTHETIC changed bytes")
    response = client.post("/api/v1/readers/resolve", json={"reference": reference})
    assert response.status_code == 409 and response.json()["error"]["code"] == "reader_original_integrity"
    path.unlink()
    assert client.post("/api/v1/readers/original", json={"reference": reference}).status_code == 404
    response = client.post("/api/v1/readers/resolve", json={"reference": {"target": {"type": "attachment", "id": "SYNTHETIC_missing"}}})
    assert response.status_code == 503 and response.json()["error"]["code"] == "reader_schema_unavailable"


def test_policy_rechecked_after_actual_parse_before_passage_publication(reader_app, tmp_path):
    reference = saved_source(reader_app, tmp_path, "SYNTHETIC.txt", b"SYNTHETIC glomerular study")
    client = TestClient(reader_app)
    body = client.post("/api/v1/readers/resolve", json={"reference": reference}).json()
    operations = []
    # Contract-boundary check only; this does not establish the parent's active-Test producer.
    def snapshot(conn):
        return {"revision": 3, "active_test_id": None, "assistance_allowed": True}
    def require(conn, *, expected_revision=None):
        operations.append(expected_revision)
        if operations.count(3) == 2:
            raise ApiError("active_test_help_denied", "SYNTHETIC policy changed", 403)
        return 3
    reader_app.state.services.get("readers").bind_shared_policy(snapshot, require, lambda conn: 1)
    result = client.post("/api/v1/readers/passage", json={"reference": reference,
        "original_sha256": body["original"]["sha256"], "locator": body["payload"]["blocks"][0]["locator"],
        "expected_policy_revision": 3, "expected_context_epoch": 1})
    assert result.status_code == 403 and operations == [3, 3]
