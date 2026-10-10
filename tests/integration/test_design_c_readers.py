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
from renulus.storage.assessment_policy import advance_policy
from renulus.storage.invalidation import bump_context_epoch


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
    assert body["preview_state"] == "ready" and body["capabilities"]["passage"]
    item = body["payload"]["blocks"][1]
    selected = client.post("/api/v1/readers/passage", json={"reference": reference,
        "original_sha256": body["original"]["sha256"], "locator": item["locator"],
        "expected_policy_revision": body["policy_revision"], "expected_context_epoch": body["context_epoch"]})
    assert item["text"] == "Study reversible causes."
    assert selected.status_code == 200 and selected.json()["text"] == "Study reversible causes."
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
        "original_sha256": body["original"]["sha256"], "expected_policy_revision": body["policy_revision"],
        "expected_context_epoch": body["context_epoch"], "locator": {"kind": "table", "format": "csv",
            "first_row": 2, "last_row": 2, "first_column": 1, "last_column": 2}})
    assert denied.status_code == 403
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
    old_route = client.get("/api/v1/library/revisions/" + reference["target"]["id"] + "/original")
    assert old_route.status_code == 200 and old_route.headers["content-type"] == "application/octet-stream"
    assert old_route.headers["content-disposition"] == "attachment"
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


def test_persisted_shared_policy_and_restore_epoch_refuse_stale_passages(reader_app, tmp_path):
    reference = saved_source(reader_app, tmp_path, "SYNTHETIC.txt", b"SYNTHETIC glomerular study")
    client = TestClient(reader_app)
    body = client.post("/api/v1/readers/resolve", json={"reference": reference}).json()
    db = reader_app.state.services.db
    command = {"reference": reference,
        "original_sha256": body["original"]["sha256"], "locator": body["payload"]["blocks"][0]["locator"],
        "expected_policy_revision": body["policy_revision"], "expected_context_epoch": body["context_epoch"]}
    with db.transaction() as conn:
        conn.execute("INSERT INTO assessment_test_attempts(id,version_id,version_snapshot_json,mode,status,clock_high_water_at,created_at,updated_at) VALUES(?,?,'{}','test','active',?,?,?)",
            ("SYNTHETIC_attempt", "SYNTHETIC_version", "2026-10-10T00:00:00Z", "2026-10-10T00:00:00Z", "2026-10-10T00:00:00Z"))
        advance_policy(conn)
    assert client.post("/api/v1/readers/resolve", json={"reference": reference}).status_code == 409
    assert client.post("/api/v1/readers/passage", json=command).json()["error"]["code"] == "assistance_restricted"
    with db.transaction() as conn:
        conn.execute("UPDATE assessment_test_attempts SET status='submitted' WHERE id='SYNTHETIC_attempt'")
        advance_policy(conn)
    assert client.post("/api/v1/readers/passage", json=command).json()["error"]["code"] == "assistance_changed"
    current = client.post("/api/v1/readers/resolve", json={"reference": reference}).json()
    command["expected_policy_revision"] = current["policy_revision"]
    assert client.post("/api/v1/readers/passage", json=command).status_code == 200
    with db.transaction() as conn:
        bump_context_epoch(conn)
    assert client.post("/api/v1/readers/passage", json=command).json()["error"]["code"] == "reader_context_changed"


def test_legacy_case_original_keeps_exact_bytes_and_case_authority(reader_app):
    from io import BytesIO
    from PIL import Image
    from renulus.cases.models import StartCase
    from renulus.cases.originals import accepted_original
    cases = reader_app.state.services.get("cases")
    buffer = BytesIO(); Image.new("RGB", (20, 20), "white").save(buffer, format="PNG")
    original_bytes = buffer.getvalue()
    original = accepted_original("SYNTHETIC.png", "SYNTHETIC saved Case original", "image/png", original_bytes)
    case = cases.start(StartCase(text="SYNTHETIC saved Case"))
    case = cases.attach(case["id"], case["revision"], original)
    case = cases.save(case["id"], case["revision"])
    client = TestClient(reader_app)
    body = {"reference": {"target": {"type": "attachment", "id": original["id"]}},
            "conversation": {"type": "case", "id": case["id"]}}
    result = client.post("/api/v1/readers/resolve", json=body)
    assert result.status_code == 200 and result.json()["authority"] == "case"
    assert not result.json()["capabilities"]["passage"]  # Legacy rights are not silently broadened.
    assert client.post("/api/v1/readers/original", json=body).content == original_bytes
    assert cases.original(case["id"], original["id"])[1] == original_bytes
    body["conversation"] = {"type": "learn_thread", "id": "SYNTHETIC_other"}
    assert client.post("/api/v1/readers/resolve", json=body).status_code == 403
