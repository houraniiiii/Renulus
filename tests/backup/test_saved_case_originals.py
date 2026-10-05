# SPDX-License-Identifier: MIT
"""Canonical case originals in bounded format-2 recovery; synthetic bytes only."""
import base64
from contextlib import closing
import hashlib
import io
import json
import sqlite3
import zipfile

from fastapi.testclient import TestClient
import pytest

from renulus.cases.models import StartCase
from renulus.contracts import ApiError
from renulus.server import create_app
from renulus.storage.backup import export_records, portable_records

from tests.cases.test_saved_originals import (ORIGINAL_SENTINEL, attach,
                                            canonical_state, synthetic_original)
from .test_segmented_recovery import download, repack_v2, restore_v2


def saved_source(tmp_path, kind="pdf"):
    app = create_app(tmp_path / "saved-original-source")
    services = app.state.services
    repository = services.registry["cases"]
    original = synthetic_original(kind)
    raw = original["data"]
    case = attach(repository, repository.start(StartCase(text="Synthetic recovery case")), original)
    saved = repository.save(case["id"], case["revision"])
    return app, saved, original, raw


@pytest.mark.parametrize("kind", ["pdf", "png"])
def test_segmented_full_recovery_preserves_original_parts_hashes_and_binary_api(tmp_path, kind):
    app, case, original, raw = saved_source(tmp_path, kind)
    services = app.state.services
    before = canonical_state(services)
    archive_bytes, manifest = download(services)
    assert manifest["canonical"]["tables"]["case_attachments"] == 1
    assert manifest["canonical"]["tables"]["case_attachment_parts"] > 1
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        restored_parts = []
        for segment in manifest["canonical"]["segments"]:
            data = archive.read(segment["path"])
            assert len(data) == segment["bytes"]
            assert hashlib.sha256(data).hexdigest() == segment["sha256"]
            if segment["table"] == "case_attachment_parts":
                restored_parts.extend(json.loads(line) for line in data.splitlines())
        restored_parts.sort(key=lambda part: part["part"])
        assert b"".join(base64.b64decode(part["data"], validate=True) for part in restored_parts) == raw
    target_app = create_app(tmp_path / "saved-original-target")
    target = target_app.state.services
    result = restore_v2(target, archive_bytes)
    assert result["rebuild"]["status"] == "required"
    assert canonical_state(target) == before
    with TestClient(target_app) as client:
        opened = client.get(f"/api/v1/cases/sessions/{case['id']}")
        assert opened.status_code == 200
        assert opened.json()["attachments"] == case["attachments"]
        assert ORIGINAL_SENTINEL not in opened.text
        binary = client.get(f"/api/v1/cases/sessions/{case['id']}/attachments/{original['id']}/original")
        assert binary.status_code == 200 and binary.content == raw
        assert binary.headers["cache-control"] == "no-store"
        assert hashlib.sha256(binary.content).hexdigest() == original["sha256"]


def test_records_only_omits_parts_before_reading_and_restores_honest_metadata(tmp_path, monkeypatch):
    app, case, original, raw = saved_source(tmp_path, "png")
    services = app.state.services
    connect = services.db.connect
    def metadata_only():
        conn = connect()
        conn.set_authorizer(lambda action, table, column, database, trigger:
            sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_READ and table == "case_attachment_parts"
            else sqlite3.SQLITE_OK)
        return conn
    with monkeypatch.context() as guard:
        guard.setattr(services.db, "connect", metadata_only)
        exported = export_records(services)
    assert exported["data_kind"] == "records-only"
    assert exported["records"]["case_attachment_parts"] == []
    assert exported["records"]["case_attachments"] == canonical_state(services)["case_attachments"]
    assert exported["omissions"]["case_originals"]["records"] == 1
    assert "full backup" in exported["omissions"]["case_originals"]["reason"].lower()
    assert ORIGINAL_SENTINEL not in json.dumps(exported)
    parts = canonical_state(services)["case_attachment_parts"]
    assert portable_records({"case_attachment_parts": parts})["case_attachment_parts"] == []
    assert portable_records({"case_attachment_parts": parts}, originals=True)["case_attachment_parts"] == parts
    target_app = create_app(tmp_path / "records-only-target")
    target = target_app.state.services
    target.registry["data_recovery"].restore_json(exported, confirm_backup_date=True,
                                                confirmed_exported_at=exported["exported_at"])
    with TestClient(target_app) as client:
        reopened = client.get(f"/api/v1/cases/sessions/{case['id']}").json()
        metadata = reopened["attachments"][0]
        assert metadata["id"] == original["id"] and metadata["saved"]
        assert metadata["bytes"] == len(raw) and metadata["sha256"] == original["sha256"]
        assert metadata["original_available"] is False
        unavailable = client.get(f"/api/v1/cases/sessions/{case['id']}/attachments/{original['id']}/original")
        assert unavailable.status_code == 409 and unavailable.headers["cache-control"] == "no-store"
        assert ORIGINAL_SENTINEL not in unavailable.text
    assert target.db.fetch_all("SELECT * FROM case_attachment_parts") == []


def test_newer_saved_case_deletion_suppresses_metadata_and_all_parts_on_old_restore(tmp_path):
    app, case, original, raw = saved_source(tmp_path)
    services = app.state.services
    archived, _ = download(services)
    target_app = create_app(tmp_path / "case-deletion-target")
    target = target_app.state.services
    restore_v2(target, archived)
    target.registry["cases"].delete(case["id"], case["revision"])
    restore_v2(target, archived)
    assert canonical_state(target) == {table: [] for table in canonical_state(target)}
    assert target.db.is_deleted("case", case["id"])
    with TestClient(target_app) as client:
        response = client.get(f"/api/v1/cases/sessions/{case['id']}/attachments/{original['id']}/original")
        assert response.status_code == 410 and ORIGINAL_SENTINEL not in response.text
    final_archive, final_manifest = download(target)
    assert final_manifest["canonical"]["tables"]["case_attachments"] == 0
    assert final_manifest["canonical"]["tables"]["case_attachment_parts"] == 0
    fresh = create_app(tmp_path / "case-deletion-fresh").state.services
    restore_v2(fresh, final_archive)
    assert canonical_state(fresh) == {table: [] for table in canonical_state(fresh)}
    assert fresh.db.is_deleted("case", case["id"])


def test_tampered_case_part_segment_rejects_before_any_target_changes(tmp_path):
    app, case, original, raw = saved_source(tmp_path)
    archived, _ = download(app.state.services)
    target = create_app(tmp_path / "guarded-original-target").state.services
    before = canonical_state(target)
    def change(manifest, members):
        segment = next(row for row in manifest["canonical"]["segments"]
                       if row["table"] == "case_attachment_parts")
        # ZIP CRC is recomputed; retain the canonical SHA to exercise its guard.
        data = members[segment["path"]]
        rows = [json.loads(line) for line in data.splitlines()]
        rows[-1]["data"] = base64.b64encode(b"synthetic tampered part").decode()
        members[segment["path"]] = b"".join(json.dumps(row, separators=(",", ":")).encode() + b"\n" for row in rows)
    forged = repack_v2(archived, change)
    with pytest.raises(ApiError) as rejected:
        restore_v2(target, forged)
    assert ORIGINAL_SENTINEL not in str(rejected.value)
    assert canonical_state(target) == before


@pytest.mark.parametrize("table", ["case_attachments", "case_attachment_parts"])
def test_resealed_same_id_original_collision_is_atomic(tmp_path, table):
    app, case, original, raw = saved_source(tmp_path)
    archived, _ = download(app.state.services)
    target = create_app(tmp_path / "original-collision-target").state.services
    restore_v2(target, archived)
    before = canonical_state(target)
    def change(manifest, members):
        segment = next(row for row in manifest["canonical"]["segments"] if row["table"] == table)
        rows = [json.loads(line) for line in members[segment["path"]].splitlines()]
        if table == "case_attachments":
            rows[0]["filename"] = "synthetic-changed-original.pdf"
        else:
            rows[0]["data"] = base64.b64encode(b"x" * 49152).decode()
        changed = b"".join(json.dumps(row, ensure_ascii=False, sort_keys=True,
                                      separators=(",", ":")).encode() + b"\n" for row in rows)
        manifest["canonical"]["bytes"] += len(changed) - segment["bytes"]
        segment["bytes"] = len(changed)
        segment["sha256"] = hashlib.sha256(changed).hexdigest()
        members[segment["path"]] = changed
    forged = repack_v2(archived, change)
    with pytest.raises(ApiError) as rejected:
        restore_v2(target, forged)
    assert rejected.value.code == "backup_case_original_conflict"
    assert ORIGINAL_SENTINEL not in str(rejected.value)
    assert canonical_state(target) == before
    assert target.registry["cases"].original(case["id"], original["id"])[1] == raw
