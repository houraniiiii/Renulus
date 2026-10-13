# SPDX-License-Identifier: MIT
"""Real saved extraction pins; explicit public offline assets, no providers."""
from contextlib import closing
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import shutil
import socket

from fastapi.testclient import TestClient
import pytest

from renulus.contracts import ApiError
from renulus.design_c_contracts import ContentReference
from renulus.knowledge.models import SourceMetadata, own_text_rights
from renulus.knowledge.source_status import validate_event
from renulus.server import create_app
from renulus.storage.assessment_policy import advance_policy
from renulus.storage.database import utc_now
from renulus.storage.invalidation import bump_context_epoch


@pytest.fixture(scope="module")
def saved(tmp_path_factory):
    selected = os.environ.get("RENULUS_SAVED_EXTRACTION_ASSETS")
    if not selected:
        pytest.skip("Select public pinned offline assets explicitly; no extraction capability is simulated")
    root = tmp_path_factory.mktemp("saved-extraction")
    manifest = json.loads((Path(__file__).parents[2] / "packaging/runtime/helper-assets.json").read_text())
    for record in manifest["groups"]["embedding"]["files"]:
        source = Path(selected) / record["path"]
        assert source.stat().st_size == record["size"]
        assert hashlib.sha256(source.read_bytes()).hexdigest() == record["sha256"]
        target = root / "helpers" / record["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    (root / "helpers/manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    # All writable state and model caches stay inside the explicit pytest root.
    with pytest.MonkeyPatch.context() as guard:
        connect, connect_ex = socket.socket.connect, socket.socket.connect_ex
        def local_only(original):
            def checked(instance, address):
                if isinstance(address, tuple) and ipaddress.ip_address(address[0]).is_loopback:
                    return original(instance, address)
                raise AssertionError("Saved extraction tests forbid external connections/providers")
            return checked
        guard.setattr(socket.socket, "connect", local_only(connect))
        guard.setattr(socket.socket, "connect_ex", local_only(connect_ex))
        app = create_app(root)
        services = app.state.services
        knowledge = services.get("knowledge")
        note = knowledge.import_text("SYNTHETIC glomerular question: Which observation is recorded?\n\nA. Hematuria\nB. Fistula stenosis\nKey: A",
            title="SYNTHETIC private questions", metadata=SourceMetadata(
                canonical_url="https://example.invalid/SYNTHETIC-questions"))
        assert note["status"] == "ready", note
        csv = root / "SYNTHETIC-questions.csv"
        csv.write_text("question,option,key\nSYNTHETIC dialysis observation,Fistula stenosis,A\n", encoding="utf-8")
        table = knowledge.import_file(csv, rights=own_text_rights())
        assert table["status"] == "ready", table
        state = {'app': app, 'services': services, 'note': note, 'table': table}
        try:
            yield state
        finally:
            state['services'].get('knowledge').close()


@pytest.fixture
def conn(saved):
    with closing(saved["services"].db.connect()) as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            yield connection
        finally:
            connection.rollback()


def snapshot(saved, conn, kind="note"):
    return saved["services"].get("readers").import_original(conn, saved[kind]["revision_id"])


def code(expected):
    return pytest.raises(ApiError, match=".*", check=lambda error: error.code == expected)


def update_rights(saved, conn, **changes):
    rights = own_text_rights().model_dump()
    rights.update(changes)
    conn.execute("UPDATE knowledge_revisions SET rights_json=? WHERE id=?",
        (json.dumps(rights), saved["note"]["revision_id"]))


def test_actual_docling_saved_text_and_csv_map_offsets_originals_and_reopen(saved, conn):
    for kind in ("note", "table"):
        result = snapshot(saved, conn, kind)
        assert result["contract"] == "saved-extraction/1"
        assert "SYNTHETIC" in result["text"] and result["segments"]
        original = saved["services"].paths.root / result["original"]["relative_path"]
        assert hashlib.sha256(original.read_bytes()).hexdigest() == result["original_sha256"]
        assert result["original"]["revision_id"] == saved[kind]["revision_id"]
        assert result["content_sha256"] == hashlib.sha256(result["text"].encode()).hexdigest()
        for segment in result["segments"]:
            passage = conn.execute("SELECT text FROM knowledge_passages WHERE id=?", (segment["passage_id"],)).fetchone()
            assert result["text"][segment["start"]:segment["end"]] == passage["text"]
            assert segment["locators"]
            ContentReference.model_validate(segment["reference"])
        if kind == "table":
            assert any(segment["reference"]["locator"]["kind"] == "table" for segment in result["segments"])
    pin = snapshot(saved, conn)
    conn.rollback()
    saved['services'].get('knowledge').close()
    reopened = create_app(saved['services'].paths.root)
    # The module fixture follows the real reopened owner for subsequent checks.
    saved['app'], saved['services'] = reopened, reopened.state.services
    other = reopened.state.services
    with other.db.transaction() as reopened_conn:
        assert other.get('readers').recheck_import_original(reopened_conn, pin)['fingerprint'] == pin['fingerprint']


def test_saved_snapshot_loads_no_converter_index_helper_or_new_connection(saved, conn, monkeypatch):
    knowledge = saved["services"].get("knowledge")
    pin = snapshot(saved, conn)
    def forbidden(*args, **kwargs):
        raise AssertionError("Saved extraction opened an engine/helper/connection")
    monkeypatch.setattr(knowledge.db, "connect", forbidden)
    monkeypatch.setattr(knowledge, "capabilities", forbidden)
    monkeypatch.setattr(knowledge.assets, "validate", forbidden)
    monkeypatch.setattr(knowledge.extractor, "extract_file", forbidden)
    monkeypatch.setattr(knowledge.embedder, "embed", forbidden)
    monkeypatch.setattr(knowledge.index, "search", forbidden)
    assert saved["services"].get("readers").recheck_import_original(conn, pin)["text"] == pin["text"]


@pytest.mark.parametrize("operation", ["display", "cache", "model_input", "derivation"])
def test_operation_specific_rights_are_rechecked_in_publication_snapshot(saved, conn, operation):
    pin = snapshot(saved, conn)
    update_rights(saved, conn, **{operation: False})
    with code("saved_extraction_denied"):
        saved["services"].get("readers").recheck_import_original(conn, pin)


def test_index_and_embedding_rights_do_not_control_private_test_import(saved, conn):
    update_rights(saved, conn, index=False, embedding=False)
    assert snapshot(saved, conn)["text"]


@pytest.mark.parametrize("entity_type", ["knowledge-document", "document", "knowledge-revision", "revision"])
def test_all_parent_tombstone_aliases_block_live_rows_without_exposure(saved, conn, entity_type):
    pin = snapshot(saved, conn)
    identifier = saved["note"]["document_id"] if entity_type in ("document", "knowledge-document") else saved["note"]["revision_id"]
    conn.execute("INSERT INTO deletion_ledger VALUES(?,?,?)", (entity_type, identifier, utc_now()))
    with code("saved_extraction_not_found") as caught:
        saved["services"].get("readers").recheck_import_original(conn, pin)
    assert "SYNTHETIC" not in caught.value.message and "library/" not in caught.value.message
    with code("saved_extraction_not_found"):
        saved["services"].get("readers").require_original_display(conn, pin)


@pytest.mark.parametrize("state,expected", [("queued", "pending"), ("processing", "pending"),
                                           ("failed", "failed"), ("cancelled", "failed")])
def test_pending_failed_and_cancelled_have_explicit_codes(saved, conn, state, expected):
    conn.execute("UPDATE knowledge_revisions SET status=? WHERE id=?", (state, saved["note"]["revision_id"]))
    with code("saved_extraction_" + expected):
        snapshot(saved, conn)


def test_ready_flag_and_reader_preview_cannot_attest_canonical_extraction(saved, conn):
    revision = saved["note"]["revision_id"]
    conn.execute("UPDATE knowledge_revisions SET extraction_json=NULL WHERE id=?", (revision,))
    with code("saved_extraction_unavailable"):
        snapshot(saved, conn)
    conn.execute("UPDATE knowledge_revisions SET extraction_json='{\"synthetic\":true}' WHERE id=?", (revision,))
    with code("saved_extraction_unavailable"):
        snapshot(saved, conn)


def test_effective_status_journal_is_visible_from_caller_uncommitted_snapshot(saved, conn):
    pin = snapshot(saved, conn)
    event = validate_event({"contract_version": 1, "event_id": "SYNTHETIC-access", "source_id": "R02",
        "identity": {"canonical_url": "https://example.invalid/SYNTHETIC-questions"},
        "changes": {"access_changed": True}, "scope": {},
        "evidence": [{"url": "https://example.invalid/notice", "inspected": True}],
        "reason": "SYNTHETIC rights check"})
    encoded = json.dumps(event)
    conn.execute("INSERT INTO knowledge_source_status_events VALUES(?,?,?,?,?)",
        (event["event_id"], "R02", hashlib.sha256(encoded.encode()).hexdigest(), encoded, utc_now()))
    with code("saved_extraction_denied"):
        saved["services"].get("readers").recheck_import_original(conn, pin)


def test_source_replacement_and_canonical_passage_edit_invalidate_captured_pin(saved, conn):
    pin = snapshot(saved, conn)
    conn.execute("UPDATE knowledge_documents SET active_revision=NULL WHERE id=?", (pin["document_id"],))
    with code("saved_extraction_stale"):
        saved["services"].get("readers").recheck_import_original(conn, pin)
    conn.execute("UPDATE knowledge_documents SET active_revision=? WHERE id=?", (pin["revision_id"], pin["document_id"]))
    conn.execute("UPDATE knowledge_passages SET text=text || ' SYNTHETIC changed' WHERE revision_id=?", (pin["revision_id"],))
    with code("saved_extraction_stale"):
        saved["services"].get("readers").recheck_import_original(conn, pin)


def test_policy_and_restore_generation_are_rechecked_without_independent_authority(saved, conn):
    pin = snapshot(saved, conn)
    bump_context_epoch(conn)
    with code("saved_extraction_context_changed"):
        saved["services"].get("readers").recheck_import_original(conn, pin)
    pin = snapshot(saved, conn)
    advance_policy(conn)
    with code("assistance_changed"):
        saved["services"].get("readers").recheck_import_original(conn, pin)


def test_real_active_test_row_blocks_source_snapshot_before_content_disclosure(saved, conn):
    conn.execute("INSERT INTO assessment_test_attempts(id,version_id,version_snapshot_json,mode,"
        "clock_high_water_at,created_at,updated_at) VALUES('SYNTHETIC-test','SYNTHETIC-version',"
        "'{}','test','now','now','now')")
    advance_policy(conn)
    with code("assistance_restricted"):
        snapshot(saved, conn)


def test_unsupported_saved_format_is_distinct_from_a_failed_supported_extraction(saved, conn):
    conn.execute("UPDATE knowledge_revisions SET media_type='application/vnd.openxmlformats-officedocument.presentationml.presentation' WHERE id=?",
        (saved["note"]["revision_id"],))
    with code("saved_extraction_unsupported"):
        snapshot(saved, conn)


def test_empty_passages_and_large_text_are_explicit_unavailable_and_limit_states(saved, conn):
    revision = saved["note"]["revision_id"]
    conn.execute("SAVEPOINT no_passages")
    conn.execute("DELETE FROM knowledge_passages WHERE revision_id=?", (revision,))
    with code("saved_extraction_unavailable"):
        snapshot(saved, conn)
    conn.execute("ROLLBACK TO no_passages")
    conn.execute("UPDATE knowledge_passages SET text=? WHERE revision_id=?", ("x" * (4 * 1024 * 1024 + 1), revision))
    with code("saved_extraction_limit"):
        snapshot(saved, conn)


@pytest.mark.parametrize("damage", ["missing", "same_size_changed"])
def test_private_original_existence_and_actual_bytes_are_rechecked(saved, conn, damage):
    pin = snapshot(saved, conn)
    path = saved["services"].paths.root / pin["original"]["relative_path"]
    original = path.read_bytes()
    try:
        if damage == "missing":
            path.unlink()
        else:
            path.write_bytes(bytes([original[0] ^ 1]) + original[1:])
        with code("original_missing"):
            saved["services"].get("readers").recheck_import_original(conn, pin)
        with code("original_missing"):
            saved["services"].get("readers").require_original_display(conn, pin)
    finally:
        path.write_bytes(original)


def test_excluded_page_does_not_silently_become_partial_test_import(saved, conn):
    revision = saved["note"]["revision_id"]
    metadata = json.loads(conn.execute("SELECT metadata_json FROM knowledge_revisions WHERE id=?", (revision,)).fetchone()[0])
    metadata["excluded_pages"] = [2]
    conn.execute("UPDATE knowledge_revisions SET metadata_json=? WHERE id=?", (json.dumps(metadata), revision))
    conn.execute("UPDATE knowledge_passages SET locators_json='[{\"page\":2}]' WHERE revision_id=?", (revision,))
    with code("saved_extraction_denied"):
        snapshot(saved, conn)


def test_absent_schema_is_real_isolated_rollback_and_missing_id_is_not_found(saved, conn):
    with code("saved_extraction_not_found"):
        saved["services"].get("readers").import_original(conn, "rev_MISSING")
    conn.execute("DROP TABLE knowledge_source_status_events")
    with code("saved_extraction_unavailable"):
        snapshot(saved, conn)


def test_import_requires_caller_transaction_and_complete_server_pin(saved):
    reader = saved["services"].get("readers")
    with closing(saved["services"].db.connect()) as conn:
        with code("saved_extraction_snapshot_required"):
            reader.import_original(conn, saved["note"]["revision_id"])
    with saved["services"].db.transaction() as conn:
        with code("saved_extraction_invalid_pin"):
            reader.recheck_import_original(conn, {"revision_id": saved["note"]["revision_id"]})
        with code("saved_extraction_invalid_pin"):
            reader.recheck_import_original(conn, {"revision_id": saved["note"]["revision_id"],
                "fingerprint": None, "policy_revision": None, "context_epoch": None})


@pytest.mark.parametrize("operation", ["model_input", "derivation"])
def test_retained_text_remains_readable_after_refinement_rights_revocation(saved, conn, operation):
    pin = snapshot(saved, conn)
    reader = saved["services"].get("readers")
    update_rights(saved, conn, **{operation: False})
    with code("saved_extraction_denied"):
        reader.recheck_import_original(conn, pin)
    result = reader.recheck_import_original(conn, pin, operation="read")
    assert result["text"] == pin["text"] and result["segments"] == pin["segments"]
    assert result["fingerprint"] != pin["fingerprint"]
    assert reader.require_original_display(conn, pin)["allowed"]


@pytest.mark.parametrize("operation", ["display", "cache"])
def test_read_does_not_bypass_current_display_or_cache_denial(saved, conn, operation):
    pin = snapshot(saved, conn)
    reader = saved["services"].get("readers")
    update_rights(saved, conn, **{operation: False})
    with code("saved_extraction_denied"):
        reader.recheck_import_original(conn, pin, operation="read")
    with code("saved_extraction_denied"):
        reader.require_original_display(conn, pin)


def test_retained_body_authorization_survives_derived_extraction_cache_loss(saved, conn):
    pin = snapshot(saved, conn)
    conn.execute("UPDATE knowledge_revisions SET extraction_json=NULL WHERE id=?", (pin["revision_id"],))
    conn.execute("DELETE FROM knowledge_passages WHERE revision_id=?", (pin["revision_id"],))
    reader = saved["services"].get("readers")
    with code("saved_extraction_unavailable"):
        reader.import_original(conn, pin["revision_id"])
    allowed = reader.require_original_display(conn, pin)
    assert allowed["allowed"] and allowed["original"]["sha256"] == pin["original_sha256"]
    assert "text" not in allowed and "segments" not in allowed


def test_source_status_warning_allows_inspection_but_denies_further_import(saved, conn):
    pin = snapshot(saved, conn)
    metadata = dict(pin["metadata"], superseded=True)
    conn.execute("UPDATE knowledge_revisions SET metadata_json=? WHERE id=?", (json.dumps(metadata), pin["revision_id"]))
    reader = saved["services"].get("readers")
    with code("saved_extraction_denied"):
        reader.import_original(conn, pin["revision_id"])
    assert reader.import_original(conn, pin["revision_id"], operation="read")["metadata"]["superseded"]
    assert reader.require_original_display(conn, pin)["metadata"]["superseded"]


def test_actual_pending_replacement_blocks_old_active_import_but_keeps_private_read(saved):
    services = saved["services"]
    knowledge, reader = services.get("knowledge"), services.get("readers")
    old = knowledge.import_text("SYNTHETIC immutable old private question")
    with services.db.transaction() as conn:
        pin = reader.import_original(conn, old["revision_id"])
    replacement = knowledge.import_text("SYNTHETIC pending new private question",
        document_id=old["document_id"], process=False)
    assert replacement["status"] == "queued"
    with services.db.transaction() as conn:
        with code("saved_extraction_stale"):
            reader.recheck_import_original(conn, pin)
        assert reader.recheck_import_original(conn, pin, operation="read")["text"] == pin["text"]
        assert reader.require_original_display(conn, pin)["allowed"]
        with code("saved_extraction_pending"):
            reader.import_original(conn, replacement["revision_id"])


@pytest.mark.parametrize("kind", ["note", "table"])
def test_actual_saved_library_source_creates_private_import_with_canonical_pins_and_reopens(saved, kind):
    services = saved["services"]
    revision_id = saved[kind]["revision_id"]
    with services.db.transaction() as conn:
        pin = services.get("readers").import_original(conn, revision_id)
    client = TestClient(saved["app"])
    request = {"idempotency_key": "SYNTHETIC_reader_import_" + kind, "title": "SYNTHETIC extracted private import",
        "original": {"kind": "library_revision", "revision_id": revision_id}}
    created = client.post("/api/v1/assessment/imports", json=request)
    assert created.status_code == 201, created.text
    identifier = created.json()["id"]
    assert created.json()["source_revision_id"] == revision_id and created.json()["call_count"] == 0
    original = client.get("/api/v1/assessment/imports/" + identifier + "/original")
    assert original.status_code == 200 and original.json()["text"] == pin["text"]
    row = services.db.fetch_one("SELECT * FROM assessment_test_imports WHERE id=?", (identifier,))
    retained = json.loads(row["original_json"])
    assert row["original_text"] == pin["text"] and row["original_sha256"] == pin["content_sha256"]
    assert retained["source_pin"]["fingerprint"] == pin["fingerprint"]
    assert retained["source_pin"]["original_sha256"] == pin["original_sha256"]
    assert retained["segments"] == pin["segments"] and retained["source_pin"]["terms"] == pin["terms"]
    assert row["source_revision_id"] == row["live_source_revision_id"] == revision_id
    assert client.post("/api/v1/assessment/imports", json=request).json()["id"] == identifier
    assert services.db.fetch_one("SELECT COUNT(*) AS count FROM assessment_test_imports WHERE id=?", (identifier,))["count"] == 1
    services.get('knowledge').close()
    reopened = create_app(services.paths.root)
    saved['app'], saved['services'] = reopened, reopened.state.services
    other = TestClient(reopened)
    read = other.get('/api/v1/assessment/imports/' + identifier + '/original')
    assert read.status_code == 200 and read.json()['text'] == pin['text']
    with reopened.state.services.db.transaction() as conn:
        current = reopened.state.services.get('readers').recheck_import_original(conn, pin)
        assert current['fingerprint'] == pin['fingerprint']
    private_original = reopened.state.services.paths.root / pin['original']['relative_path']
    assert hashlib.sha256(private_original.read_bytes()).hexdigest() == pin['original_sha256']
