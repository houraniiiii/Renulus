# SPDX-License-Identifier: MIT
"""Product format-2 recovery, including data beyond the legacy canonical cap."""
from contextlib import contextmanager
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import zipfile

from fastapi.testclient import TestClient
import pytest

from renulus.contracts import ApiError
from renulus.server import create_app
from renulus.knowledge.models import own_text_rights
from renulus.storage.backup import export_records
from renulus.storage.recovery_files import remove_owned_tree

from .conftest import preview, state


def download(services):
    directory, manifest = services.registry["data_recovery"].backup(format_version=2)
    try:
        return (directory / "backup.zip").read_bytes(), manifest
    finally:
        remove_owned_tree(services.paths, directory)


def restore_v2(target, data):
    checked = preview(target, data)
    assert checked["format_version"] == 2
    return target.registry["data_recovery"].restore_preview(checked["preview_token"], checked["exported_at"], True)


def repack_v2(data, change):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        members = {info.filename: archive.read(info) for info in archive.infolist()}
    manifest = json.loads(members["manifest.json"])
    change(manifest, members)
    members["manifest.json"] = json.dumps(manifest, separators=(",", ":")).encode()
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, contents in members.items():
            archive.writestr(name, contents)
    return result.getvalue()


def test_product_api_streams_large_canonical_library_and_rebases_verified_originals(source, tmp_path, monkeypatch):
    services, selected = source
    revision = selected[0]["revision_id"]
    text = "SYNTHETIC renal learning; Δ µ source attribution. " * 40
    with services.db.transaction() as conn:
        conn.executemany("INSERT INTO knowledge_passages VALUES(?,?,?,?,?,?,?)", (
            (f"pass_large_{i:06d}", revision, i, text + str(i), text + str(i),
             json.dumps([{ "page": i + 1, "item_id": f"#/texts/{i}"}]), '["SYNTHETIC CKD heading"]')
            for i in range(9000)))
        conn.execute("UPDATE knowledge_revisions SET extraction_json=? WHERE id=?",
            ('{"excluded":"' + "SYNTHETIC_EXTRACTION" * 1000000 + '"}', revision))
    import renulus.storage.backup as legacy
    def forbidden(*args, **kwargs):
        pytest.fail("Format 2 used the whole-corpus legacy snapshot/merge")
    monkeypatch.setattr(legacy, "snapshot_in", forbidden)
    monkeypatch.setattr(legacy, "apply_records", forbidden)
    source_app = create_app(services.paths.root)
    source_client = TestClient(source_app)
    downloaded = source_client.get("/api/v1/data/backup?format_version=2")
    assert downloaded.status_code == 200, downloaded.text[:500]
    assert downloaded.headers["x-renulus-backup-format"] == "2"
    with zipfile.ZipFile(io.BytesIO(downloaded.content)) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["format_version"] == 2
        assert manifest["canonical"]["bytes"] > 32 * 1024 * 1024
        assert manifest["canonical"]["tables"]["knowledge_passages"] == 9000
        passage_segments = [s for s in manifest["canonical"]["segments"] if s["table"] == "knowledge_passages"]
        assert len(passage_segments) >= 2
        assert "records.json" not in archive.namelist()
        assert "knowledge_catalogue" not in manifest["canonical"]["tables"]
        for entry in manifest["canonical"]["segments"]:
            data = archive.read(entry["path"])
            assert len(data) == entry["bytes"]
            assert hashlib.sha256(data).hexdigest() == entry["sha256"]
            assert str(services.paths.root).encode() not in data
            assert b"SYNTHETIC_EXTRACTION" not in data
            assert b"SYNTHETIC_PROVIDER_SENTINEL" not in data
    target_app = create_app(tmp_path / "fresh-large-target")
    target = target_app.state.services
    client = TestClient(target_app)
    checked = client.post("/api/v1/data/backup/preview?format_version=2", content=downloaded.content)
    assert checked.status_code == 200, checked.text
    assert checked.json()["record_count"] >= 9000
    fields = {"preview_token": checked.json()["preview_token"],
        "confirmed_exported_at": checked.json()["exported_at"], "acknowledge_deletion_limits": True}
    restored = client.post("/api/v1/data/backup/restore", json=fields)
    assert restored.status_code == 200, restored.text
    assert restored.json()["restored_originals"] == 4
    assert target.db.fetch_one("SELECT COUNT(*) AS n FROM knowledge_passages")["n"] == 9000
    passage = target.db.fetch_one("SELECT * FROM knowledge_passages WHERE id='pass_large_008999'")
    assert passage["text"] == text + "8999"
    assert json.loads(passage["locators_json"]) == [{"page": 9000, "item_id": "#/texts/8999"}]
    assert target.db.fetch_one("SELECT id FROM learning_evidence WHERE id='evidence_synthetic'")
    assert target.db.fetch_one("SELECT value FROM preferences WHERE key='learn.teaching_style'")["value"] == "guided"
    assert not target.db.fetch_one("SELECT value FROM preferences WHERE key='runtime.selected_provider'")
    for item in selected:
        row = target.db.fetch_one("SELECT * FROM knowledge_revisions WHERE id=?", (item["revision_id"],))
        assert Path(row["original_path"]).is_relative_to(target.paths.library)
        assert Path(row["original_path"]).read_bytes() == item["bytes"]
        assert row["extraction_json"] is None
        assert item["input"].read_bytes() == item["bytes"]
    repeated = restore_v2(target, downloaded.content)
    assert repeated["restored_records"] == 0
    assert repeated["restored_originals"] == 4


def test_v2_newer_target_deletion_reconciles_transitive_rows_before_original_promotion_and_rebuild(source, target):
    services, selected = source
    deleted = selected[0]
    services.db.execute("INSERT INTO knowledge_passages VALUES(?,?,?,?,?,?,?)",
        ("pass_descendant", deleted["revision_id"], 0, "SYNTHETIC passage", "SYNTHETIC passage", '[{"page":1}]', '[]'))
    data, _ = download(services)
    restore_v2(target, data)
    target.db.mark_deleted("knowledge-document", deleted["document_id"])
    timeline = []
    class Knowledge:
        @contextmanager
        def recovery_guard(self):
            yield
            timeline.append("promoted")
        def rebuild_index(self):
            timeline.append("rebuild")
            assert not target.db.fetch_one("SELECT id FROM knowledge_passages WHERE id='pass_descendant'")
            assert not target.db.fetch_one("SELECT id FROM knowledge_documents WHERE id=?", (deleted["document_id"],))
            assert not list((target.paths.library / "knowledge" / deleted["document_id"]).rglob("original.*"))
            return {"status": "ready", "passages": 0, "generation": "synthetic", "cleanup_pending": False}
    class Memory:
        def reindex(self):
            assert timeline == ["promoted", "rebuild"]
            return {"ready": True, "count": 0, "generation": "synthetic"}
        def process_pending(self):
            pytest.fail("No generative capture during rebuild")
    target.registry.update(knowledge=Knowledge(), memory=Memory())
    result = restore_v2(target, data)
    assert result["excluded_originals"] == 1
    assert result["excluded_by_deletion"] == 4
    assert result["removed_by_deletion"] == 4
    recovery = target.registry["data_recovery"]
    identifier, _, _ = recovery.request_rebuild()
    recovery.rebuild(identifier)
    assert recovery.status()["rebuild"]["status"] == "complete"


@pytest.mark.parametrize("mutation", ["late-hash", "duplicate-row", "missing-reference", "immutable-content",
    "provider-preference", "nonportable-path", "extraction", "traversal", "unlisted-original", "row-count"])
def test_v2_forged_segments_with_valid_zip_crc_never_change_existing_profile(source, target, mutation):
    data, _ = download(source[0])
    before = state(target)
    def change(manifest, members):
        segments = manifest["canonical"]["segments"]
        table = {"late-hash": "preferences", "duplicate-row": "knowledge_jobs", "missing-reference": "knowledge_jobs",
            "immutable-content": "content_question_versions", "provider-preference": "preferences",
            "nonportable-path": "knowledge_revisions", "extraction": "knowledge_revisions"}.get(mutation)
        entry = next(s for s in segments if s["table"] == table) if table else segments[-1]
        lines = members[entry["path"]].splitlines()
        if mutation == "traversal":
            entry["path"] = "../owner.txt"
            return
        if mutation == "unlisted-original":
            members['library/knowledge/doc_forged/rev_forged/original.txt'] = b"forged"
            return
        if mutation == "row-count":
            entry["records"] += 1
            return
        row = json.loads(lines[-1])
        if mutation == "late-hash":
            members[entry["path"]] = members[entry["path"]].replace(b"guided", b"FORGED", 1)
            return
        if mutation == "duplicate-row":
            lines.append(lines[-1])
            entry["records"] += 1
            manifest["canonical"]["records"] += 1
            manifest["canonical"]["tables"][entry["table"]] += 1
        else:
            if mutation == "missing-reference": row["revision_id"] = "rev_missing"
            elif mutation == "immutable-content": row["body_json"] = '{"forged":"historical key"}'
            elif mutation == "provider-preference": row["key"] = "runtime.selected_provider"
            elif mutation == "nonportable-path": row["original_path"] = "C:/owner/original.txt"
            elif mutation == "extraction": row["extraction_json"] = '{"forged":"derived extraction"}'
            lines[-1] = json.dumps(row, separators=(",", ":")).encode()
        new = b"\n".join(lines) + b"\n"
        manifest["canonical"]["bytes"] += len(new) - entry["bytes"]
        entry.update(bytes=len(new), sha256=hashlib.sha256(new).hexdigest())
        members[entry["path"]] = new
    with pytest.raises(ApiError):
        preview(target, repack_v2(data, change))
    assert state(target) == before
    assert not list((target.paths.cache / "recovery/previews").iterdir())


def test_v2_sql_commit_failure_rolls_back_verified_original_promotion(source, target, monkeypatch):
    data, _ = download(source[0])
    checked = preview(target, data)
    before = state(target)
    @contextmanager
    def failed_commit():
        conn = target.db.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            raise sqlite3.OperationalError("SYNTHETIC commit failure")
        finally:
            conn.rollback()
            conn.close()
    monkeypatch.setattr(target.db, "transaction", failed_commit)
    with pytest.raises(ApiError):
        target.registry["data_recovery"].restore_preview(checked["preview_token"], checked["exported_at"], True)
    assert state(target) == before
    assert not list((target.paths.state / "recovery/transactions").iterdir())


def test_legacy_json_and_zip_default_stay_usable_and_status_exposes_versioned_limits(source, target):
    client = TestClient(create_app(source[0].paths.root))
    data = client.get("/api/v1/data/backup")
    assert data.status_code == 200
    with zipfile.ZipFile(io.BytesIO(data.content)) as archive:
        assert json.loads(archive.read("manifest.json"))["format_version"] == 1
        assert "records.json" in archive.namelist()
    checked = preview(target, data.content)
    result = target.registry["data_recovery"].restore_preview(checked["preview_token"], checked["exported_at"], True)
    assert result["restored_originals"] == 4
    records = client.get("/api/v1/data/export")
    assert records.status_code == 200 and records.json()["data_kind"] == "records-only"
    formats = client.get("/api/v1/data/recovery").json()["backup_formats"]
    assert formats["1"]["json_bytes"] == 16 * 1024 * 1024
    assert formats["2"]["canonical_bytes"] >= 32 * 1024 * 1024


@pytest.mark.parametrize("kind", ["zip", "json"])
def test_valid_legacy_backup_merges_into_large_target_without_legacy_target_snapshot(source, target, tmp_path, kind):
    path = tmp_path / "selected-large-target.txt"
    path.write_bytes(b"SYNTHETIC independently retained target Library original.")
    imported = target.registry["knowledge"].import_file(path, rights=own_text_rights(), process=False)
    text = "SYNTHETIC target passage remains retained. " * 50
    with target.db.transaction() as conn:
        conn.executemany("INSERT INTO knowledge_passages VALUES(?,?,?,?,?,?,?)", (
            (f"pass_retained_{i:05d}", imported["revision_id"], i, text, text, '[{"page":1}]', '[]')
            for i in range(6000)))
    recovery = target.registry["data_recovery"]
    if kind == "json":
        bundle = export_records(source[0])
        result = recovery.restore_json(bundle, confirm_backup_date=True, confirmed_exported_at=bundle["exported_at"])
        assert result["restored_originals"] == 0
    else:
        directory, _ = source[0].registry["data_recovery"].backup()
        try:
            checked = preview(target, (directory / "backup.zip").read_bytes())
            result = recovery.restore_preview(checked["preview_token"], checked["exported_at"], True)
        finally:
            remove_owned_tree(source[0].paths, directory)
        assert result["restored_originals"] == 4
    assert result["format_version"] == 1
    assert target.db.fetch_one("SELECT COUNT(*) AS n FROM knowledge_passages")["n"] == 6000
    assert target.db.fetch_one("SELECT text FROM knowledge_passages WHERE id='pass_retained_05999'")["text"] == text
    assert target.db.fetch_one("SELECT id FROM learning_evidence WHERE id='evidence_synthetic'")
    original = target.db.fetch_one("SELECT original_path FROM knowledge_revisions WHERE id=?", (imported["revision_id"],))
    assert Path(original["original_path"]).read_bytes() == path.read_bytes()
