# SPDX-License-Identifier: MIT
"""Connected real router/SQLite/original/parser checks, without providers."""
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from contextvars import Context

from fastapi.testclient import TestClient
import pytest

from renulus.contracts import ApiError
from renulus.knowledge.models import own_text_rights
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


def test_pending_case_attachment_removal_revokes_reader_before_save(reader_app):
    from io import BytesIO
    from PIL import Image
    from renulus.cases.models import StartCase
    from renulus.cases.originals import accepted_original
    cases = reader_app.state.services.get("cases")
    stream = BytesIO(); Image.new("RGB", (20, 20), "white").save(stream, format="PNG")
    original = accepted_original("SYNTHETIC.png", "SYNTHETIC removed original", "image/png", stream.getvalue())
    case = cases.start(StartCase(text="SYNTHETIC Case removal"))
    case = cases.attach(case["id"], case["revision"], original)
    case = cases.save(case["id"], case["revision"])
    client = TestClient(reader_app)
    body = {"reference": {"target": {"type": "attachment", "id": original["id"]}},
            "conversation": {"type": "case", "id": case["id"]}}
    assert client.post("/api/v1/readers/original", json=body).status_code == 200
    cases.remove_attachment(case["id"], original["id"], case["revision"])
    # Canonical parts still exist until Save, but the current owner revoked use.
    assert reader_app.state.services.db.fetch_one("SELECT id FROM case_attachments WHERE id=?", (original["id"],))
    assert client.post("/api/v1/readers/resolve", json=body).status_code == 404
    assert client.post("/api/v1/readers/original", json=body).status_code == 404


def test_actual_workspace_router_uses_registered_case_attachment_authority(reader_app):
    from io import BytesIO
    from PIL import Image
    from renulus.cases.models import StartCase
    from renulus.cases.originals import accepted_original
    cases = reader_app.state.services.get("cases")
    stream = BytesIO(); Image.new("RGB", (20, 20), "white").save(stream, format="PNG")
    original = accepted_original("SYNTHETIC.png", "SYNTHETIC Workspace original", "image/png", stream.getvalue())
    case = cases.start(StartCase(text="SYNTHETIC volatile Workspace Case"))
    case = cases.attach(case["id"], case["revision"], original)
    client = TestClient(reader_app)
    request = {"kind": "content", "context": {"identity": {"type": "case", "id": case["id"]},
        "retention": "temporary"}, "policy": client.get("/api/v1/assessment/policy").json(),
        "reference": {"target": {"type": "attachment", "id": original["id"]}}}
    result = client.post("/api/v1/workspace/authorize", json=request)
    assert result.status_code == 200 and result.json() == {"allowed": True}
    assert not reader_app.state.services.db.fetch_one("SELECT id FROM case_sessions WHERE id=?", (case["id"],))
    cases.remove_attachment(case["id"], original["id"], case["revision"])
    assert client.post("/api/v1/workspace/authorize", json=request).json()["allowed"] is False


def test_actual_html_grid_passage_uses_retained_cells_and_shared_revision_guard(reader_app, tmp_path):
    reference = saved_source(reader_app, tmp_path, "SYNTHETIC-grid.html",
        b'<table><tr><th>Topic</th><th>Value</th></tr><tr><td>SYNTHETIC CKD</td><td>15%</td></tr></table>')
    client = TestClient(reader_app)
    result = client.post("/api/v1/readers/resolve", json={"reference": reference})
    assert result.status_code == 200
    body = result.json()
    table = body["payload"]["blocks"][0]
    assert table["grid"]["rows"] == [["Topic", "Value"], ["SYNTHETIC CKD", "15%"]]
    passage = client.post("/api/v1/readers/passage", json={"reference": reference,
        "locator": table["locator"], "original_sha256": body["original"]["sha256"],
        "expected_policy_revision": body["policy_revision"], "expected_context_epoch": body["context_epoch"]})
    assert passage.status_code == 200 and passage.json()["text"] == "Topic\tValue\nSYNTHETIC CKD\t15%"
    assert passage.json()["reference"]["locator"] == table["locator"]


@pytest.mark.parametrize("endpoint,owner_method", [
    ("resolve", "resolve"), ("asset", "asset"), ("original", "download"), ("passage", "passage"),
])
@pytest.mark.parametrize("stale_at", ["before_read", "after_read"])
def test_actual_study_receipt_guards_all_reader_requests_before_and_after_reads(
        reader_app, tmp_path, monkeypatch, endpoint, owner_method, stale_at):
    from io import BytesIO
    from PIL import Image
    from renulus.assessment.attempt_models import HelpRequest, SaveDraft, StartAttempt
    from renulus.design_c_contracts import QuestionSnapshot, SavedTestVersion
    from renulus.storage import utc_now
    services = reader_app.state.services
    version = SavedTestVersion(id="SYNTHETIC_reader_study_version", test_id="SYNTHETIC_reader_study_test",
        ordinal=1, origin="imported", review_quality="personal", status="ready", provenance={"method": "import"},
        created_at=utc_now(), terms="SYNTHETIC owned teaching material", items=[QuestionSnapshot(
            item_id="SYNTHETIC_reader_study_item", question_id="SYNTHETIC_reader_study_question",
            question_version="1", key_version="1", family_id="SYNTHETIC_reader_study_family",
            family_version="1", topic_id="general", stem="SYNTHETIC Study question",
            options=[{"id": "a", "text": "SYNTHETIC first option"}, {"id": "b", "text": "SYNTHETIC second option"}],
            correct_option_ids=["a"], explanation="SYNTHETIC_PRIVATE_STUDY_KEY")])
    with services.db.transaction() as conn:
        services.get("saved_tests").publish_version(conn, version, title="SYNTHETIC Reader Study",
            provenance={"schema": "saved-test-provenance/1"}, idempotency_key="SYNTHETIC_reader_version")
    owner = services.get("whole_attempts")
    attempt = owner.start(StartAttempt(version={"type": "saved_test_version", "id": version.id}), "SYNTHETIC_reader_start")
    receipt = owner.help(attempt["id"], HelpRequest(expected_revision=attempt["draft_revision"],
        expected_policy_revision=attempt["policy"]["revision"], item_id=version.items[0].item_id, kind="sources"),
        "SYNTHETIC_reader_help")
    client = TestClient(reader_app)
    if endpoint == "asset":
        image = BytesIO(); Image.new("RGB", (20, 20), "white").save(image, format="PNG")
        reference = saved_source(reader_app, tmp_path, "SYNTHETIC-study-image.png", image.getvalue())
    else:
        reference = saved_source(reader_app, tmp_path, "SYNTHETIC-study.txt", b"SYNTHETIC_PRIVATE_READER_SOURCE")
    resolved = client.post("/api/v1/readers/resolve", json={"reference": reference})
    assert resolved.status_code == 200
    document = resolved.json()
    command = {"reference": reference}
    if endpoint == "asset":
        command.update(asset_id=document["payload"]["asset_id"], original_sha256=document["original"]["sha256"])
    elif endpoint == "passage":
        command.update(locator=document["payload"]["blocks"][0]["locator"],
            original_sha256=document["original"]["sha256"], expected_policy_revision=document["policy_revision"],
            expected_context_epoch=document["context_epoch"])
    headers = {"X-Renulus-Study-Context": json.dumps(receipt["context"])}
    current = client.post("/api/v1/readers/" + endpoint, json=command, headers=headers)
    assert current.status_code == 200, current.text

    def invalidate():
        return owner.save(attempt["id"], SaveDraft(expected_revision=attempt["draft_revision"], position=0,
            answers=[{"item_id": version.items[0].item_id, "option_ids": ["b"], "marked": False}]),
            "SYNTHETIC_reader_draft_change")

    if stale_at == "before_read":
        invalidate()
    readers = services.get("readers")
    actual_read = getattr(readers, owner_method)
    reads = []
    def read_then_change(request):
        result = actual_read(request)
        reads.append(endpoint)
        # An independent control operation changes real canonical state after
        # the reader finishes. It carries no inherited request publication guard.
        with ThreadPoolExecutor(max_workers=1) as worker:
            worker.submit(Context().run, invalidate).result(timeout=5)
        return result
    monkeypatch.setattr(readers, owner_method, read_then_change)
    stale = client.post("/api/v1/readers/" + endpoint, json=command, headers=headers)
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "revision_conflict"
    assert reads == ([] if stale_at == "before_read" else [endpoint])
    assert "SYNTHETIC_PRIVATE_READER_SOURCE" not in stale.text and "SYNTHETIC_PRIVATE_STUDY_KEY" not in stale.text
    assert "application/json" in stale.headers["content-type"]
    assert owner.get(attempt["id"])["draft_revision"] == attempt["draft_revision"] + 1
