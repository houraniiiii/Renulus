from fastapi.testclient import TestClient
import pytest

from renulus.contracts import ApiError
from renulus.server import create_app
from renulus.storage.backup import export_records, restore_records


def test_export_roundtrip_excludes_connection_state_and_preserves_newer_deletions(tmp_path):
    source = create_app(tmp_path / "source").state.services
    thread = source.registry["learn"].create_thread("Original study", "ckd")
    source.db.execute("INSERT INTO preferences VALUES(?,?,?)",
                      ("connection.token", "SYNTHETIC_SECRET_NOT_EXPORTED", "now"))
    snapshot = export_records(source)
    assert snapshot["format_version"] == 1
    assert "SYNTHETIC_SECRET_NOT_EXPORTED" not in str(snapshot)
    target = create_app(tmp_path / "target").state.services
    with pytest.raises(ApiError, match="Confirm the backup date"):
        restore_records(target, snapshot)
    result = restore_records(target, snapshot, confirm_older=True)
    assert result["indexes"] == "rebuild-required"
    assert target.registry["learn"].get_thread(thread["id"])["title"] == "Original study"
    target.db.execute("DELETE FROM learn_threads WHERE id=?", (thread["id"],))
    target.db.mark_deleted("learn_thread", thread["id"])
    assert restore_records(target, snapshot, confirm_older=True)["excluded_by_deletion"] >= 1
    assert target.db.fetch_one("SELECT * FROM learn_threads WHERE id=?", (thread["id"],)) is None


def test_restore_rejects_unknown_schema_and_is_atomic_for_broken_references(tmp_path):
    source = create_app(tmp_path / "source").state.services
    source.registry["learn"].create_thread("Study")
    snapshot = export_records(source)
    target = create_app(tmp_path / "target").state.services
    bad = {**snapshot, "schema_version": 99}
    with pytest.raises(ApiError, match="compatible app"):
        restore_records(target, bad, confirm_older=True)
    snapshot["records"]["learn_messages"] = [{"id": "orphan", "thread_id": "missing",
        "run_id": "missing-run", "role": "user", "content": "Synthetic",
        "citations_json": "[]", "created_at": "now"}]
    with pytest.raises(ApiError, match="incomplete linked records"):
        restore_records(target, snapshot, confirm_older=True)
    assert target.db.fetch_all("SELECT * FROM learn_threads") == []


def test_restore_suppresses_indirect_deleted_document_rows_and_applies_imported_markers(tmp_path):
    source = create_app(tmp_path / "source").state.services
    imported = source.registry["knowledge"].import_text("Synthetic source text", process=False)
    snapshot = export_records(source)
    target = create_app(tmp_path / "target").state.services
    restore_records(target, snapshot, confirm_older=True)
    assert target.db.fetch_one("SELECT id FROM knowledge_jobs WHERE id=?", (imported["job"]["id"],))
    # A later snapshot carries a deletion unknown to this restored installation.
    snapshot["records"]["deletion_ledger"].append({"entity_type": "document",
        "entity_id": imported["document_id"], "deleted_at": "2026-10-04T23:00:00+00:00"})
    result = restore_records(target, snapshot, confirm_older=True)
    assert result["removed_by_deletion"] == 3
    assert result["excluded_by_deletion"] == 3
    for table in ("knowledge_documents", "knowledge_revisions", "knowledge_jobs"):
        assert target.db.fetch_all(f'SELECT * FROM "{table}"') == []
    assert target.db.is_deleted("document", imported["document_id"])


def test_restore_rejects_conflicting_published_keys_without_changing_history(tmp_path):
    source = create_app(tmp_path / "source").state.services
    snapshot = export_records(source)
    target = create_app(tmp_path / "target").state.services
    original = target.db.fetch_all("SELECT * FROM content_question_versions")
    snapshot["records"]["content_question_versions"][0]["sha256"] = "conflicting-synthetic-key"
    with pytest.raises(ApiError, match="published content version differs"):
        restore_records(target, snapshot, confirm_older=True)
    assert target.db.fetch_all("SELECT * FROM content_question_versions") == original
