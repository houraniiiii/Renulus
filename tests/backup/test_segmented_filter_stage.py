# SPDX-License-Identifier: MIT
"""Local delivery selection through verified iterable canonical staging."""
import json
from contextlib import closing
from pathlib import Path
import sqlite3

import pytest

from renulus.contracts import ApiError
from renulus.server import create_app
from renulus.storage.recovery_files import remove_owned_tree

from .conftest import preview, state


TABLES = {"content_packs", "content_topics", "content_case_versions", "content_question_versions",
    "content_pack_topics", "content_pack_cases", "content_pack_questions", "content_active_pack",
    "content_question_withdrawals", "content_pack_withdrawals", "knowledge_documents",
    "knowledge_revisions", "knowledge_jobs", "knowledge_passages", "knowledge_cleanup",
    "knowledge_source_status_events", "deletion_ledger"}


def selected_rows(validated, services, *, omit=None):
    for table, row in validated.iter_records(services):
        if table in TABLES and table != omit and (table != "deletion_ledger" or row["entity_type"] == "knowledge-document"):
            yield table, row


@pytest.mark.parametrize("format_version", [1, 2])
def test_iterable_delivery_selection_reexports_exact_library_without_learner_state(source, tmp_path, format_version):
    services, originals = source
    services.db.execute("INSERT INTO knowledge_source_status_events VALUES(?,?,?,?,?)", (
        "source_event_synthetic", "R02", "synthetic-review-hash", '{"status":"reviewed"}', "2026-10-04T22:00:00+00:00"))
    services.db.mark_deleted("knowledge-document", "doc_deleted_synthetic")
    services.db.mark_deleted("memory-fact", "fact_excluded_synthetic")
    source_recovery = services.registry["data_recovery"]
    exported, _ = source_recovery.backup(format_version=format_version)
    scratch = create_app(tmp_path / "packaging-scratch").state.services
    recovery = scratch.registry["data_recovery"]
    try:
        checked = preview(scratch, (exported / "backup.zip").read_bytes())
    finally:
        remove_owned_tree(services.paths, exported)
    with recovery.validated_preview(checked["preview_token"]) as validated:
        # Parent's delivery filter may keep a trusted SQL reader open while
        # selecting exact bindings. Windows cleanup waits until the lease ends.
        with closing(sqlite3.connect(validated.stage)) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA query_only=ON")
            def sql_rows():
                for table in sorted(TABLES):
                    for row in conn.execute(f'SELECT * FROM "{table}" ORDER BY rowid'):
                        if table != "deletion_ledger" or row["entity_type"] == "knowledge-document":
                            yield table, dict(row)
            filtered = recovery.preview_records(sql_rows(),
                exported_at=checked["exported_at"], omissions=checked["omissions"], originals=validated.originals)
            assert validated.stage.exists()
    assert filtered["format"] == "renulus-canonical-record-stage"
    assert filtered["record_count"] < checked["record_count"]
    assert filtered["original_count"] == 4
    assert not list((scratch.paths.cache / "recovery/previews" / checked["preview_token"]).glob("*"))
    restored = recovery.restore_preview(filtered["preview_token"], filtered["exported_at"], True)
    assert restored["restored_originals"] == 4 and restored["rebuild"]["status"] == "required"
    assert scratch.db.fetch_one("SELECT COUNT(*) AS n FROM learning_evidence")["n"] == 0
    assert scratch.db.fetch_one("SELECT COUNT(*) AS n FROM preferences")["n"] == 0
    assert scratch.db.fetch_one("SELECT COUNT(*) AS n FROM deletion_ledger")["n"] == 1
    directory, manifest = recovery.backup(format_version=2)
    try:
        assert manifest["canonical"]["tables"]["learning_evidence"] == 0
        assert manifest["canonical"]["tables"]["preferences"] == 0
        assert "knowledge_catalogue" not in manifest["canonical"]["tables"]
        final = create_app(tmp_path / "fresh-final").state.services
        final_recovery = final.registry["data_recovery"]
        final_checked = preview(final, (directory / "backup.zip").read_bytes())
        final_recovery.restore_preview(final_checked["preview_token"], final_checked["exported_at"], True)
    finally:
        remove_owned_tree(scratch.paths, directory)
    assert final.db.fetch_one("SELECT payload_json FROM knowledge_source_status_events WHERE id='source_event_synthetic'")["payload_json"] == '{"status":"reviewed"}'
    assert not final.db.fetch_one("SELECT id FROM learning_evidence WHERE id='evidence_synthetic'")
    for original in originals:
        row = final.db.fetch_one("SELECT * FROM knowledge_revisions WHERE id=?", (original["revision_id"],))
        assert Path(row["original_path"]).is_relative_to(final.paths.library)
        assert Path(row["original_path"]).read_bytes() == original["bytes"]
        assert json.loads(row["metadata_json"])["edition"] == "Synthetic recovery 1"
        assert json.loads(row["rights_json"])["cache"] is True
    assert state(services)[1]  # Selected source originals were preserved.


@pytest.mark.parametrize("failure,code", [("duplicate", "backup_duplicates"),
    ("missing-reference", "backup_references"), ("missing-original", "backup_manifest"),
    ("foreign-original", "backup_path")])
def test_failed_iterable_selection_keeps_previous_preview_and_canonical_profile_unchanged(source, target, failure, code):
    directory, _ = source[0].registry["data_recovery"].backup(format_version=2)
    try:
        checked = preview(target, (directory / "backup.zip").read_bytes())
    finally:
        remove_owned_tree(source[0].paths, directory)
    recovery, before = target.registry["data_recovery"], state(target)
    with recovery.validated_preview(checked["preview_token"]) as verified:
        def rows():
            for table, row in selected_rows(verified, target):
                if failure == "missing-reference" and table == "knowledge_jobs":
                    row = {**row, "revision_id": "rev_missing"}
                yield table, row
                if failure == "duplicate" and table == "knowledge_documents":
                    yield table, row
        originals = verified.originals
        if failure == "missing-original":
            originals = originals[:-1]
        if failure == "foreign-original":
            originals = [{**originals[0], "staged": source[1][0]["input"]}, *originals[1:]]
        with pytest.raises(ApiError) as rejected:
            recovery.preview_records(rows(), exported_at=checked["exported_at"],
                omissions=checked["omissions"], originals=originals)
        assert rejected.value.code == code
    assert state(target) == before
    assert [item.name for item in (target.paths.cache / "recovery/previews").iterdir()] == [checked["preview_token"]]
    with recovery.validated_preview(checked["preview_token"]) as verified:
        assert len(verified.originals) == 4
        assert sum(1 for _ in verified.iter_records(target)) == checked["record_count"]
    recovery.discard_preview(checked["preview_token"])
