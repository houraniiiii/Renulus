# SPDX-License-Identifier: MIT
"""Actual installed-schema recovery of typed, synthetic chat-owned originals."""
import hashlib
import io
import json
from pathlib import Path
import zipfile

import pytest

from renulus.contracts import ApiError
from renulus.knowledge.models import SourceMetadata, own_text_rights
from renulus.learn.conversation_models import NewConversation
from renulus.server import create_app
from renulus.storage.backup import export_records
from renulus.storage.recovery_files import remove_owned_tree
from renulus.storage import recovery_files

from .conftest import preview, restore, state


def seed_attachment(services, *, kind="learning", suffix="md"):
    chat = services.get("conversations").create(NewConversation(kind=kind, title="SYNTHETIC attachment owner"))
    attachment_id, original_id = "att_synthetic_" + suffix, "orig_synthetic_" + suffix
    payload = ("SYNTHETIC nephrology document " + suffix).encode()
    path = services.paths.library / "attachments" / attachment_id / ("original." + suffix)
    path.parent.mkdir(parents=True)
    path.write_bytes(payload)
    media = {"md": "text/markdown", "csv": "text/csv", "html": "text/html", "xml": "application/xml"}[suffix]
    with services.db.transaction() as conn:
        conn.execute("INSERT INTO knowledge_attachments(id,chat_kind,chat_id,title,media_type,created_at,updated_at) "
                     "VALUES(?,?,?,?,?,?,?)", (attachment_id, kind, chat["identity"]["id"], "Synthetic original", media, "now", "now"))
        conn.execute("INSERT INTO knowledge_attachment_originals VALUES(?,?,?,?,?,?,?)",
                     (original_id, attachment_id, "original", str(path), hashlib.sha256(payload).hexdigest(), len(payload), "now"))
        conn.execute("INSERT INTO knowledge_attachment_metadata(attachment_id,filename,source_id,metadata_json,rights_json) "
                     "VALUES(?,?,?,?,?)", (attachment_id, path.name, "R02", SourceMetadata().model_dump_json(), own_text_rights().model_dump_json()))
    return chat, attachment_id, original_id, payload


def archive_bytes(services, version):
    directory, manifest = services.get("data_recovery").backup(format_version=version)
    try:
        return (directory / "backup.zip").read_bytes(), manifest
    finally:
        remove_owned_tree(services.paths, directory)


@pytest.mark.parametrize("version", [1, 2])
def test_chat_originals_and_new_library_media_round_trip(version, tmp_path):
    source = create_app(tmp_path / "source").state.services
    target = create_app(tmp_path / "target").state.services
    attachments = [seed_attachment(source, suffix=suffix) for suffix in ("md", "csv", "html", "xml")]
    for suffix in ("csv", "html", "xml"):
        path = tmp_path / ("SYNTHETIC." + suffix)
        path.write_text("SYNTHETIC original " + suffix, encoding="utf-8")
        source.get("knowledge").import_file(path, rights=own_text_rights(), metadata=SourceMetadata(), process=False)
    data, manifest = archive_bytes(source, version)
    assert len(manifest["originals"]) == 7
    assert sum(entry.get("kind") == "chat-attachment" for entry in manifest["originals"]) == 4
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert str(source.paths.root).encode() not in b"".join(archive.read(name) for name in archive.namelist())
    result = restore(target, data)
    assert result["restored_originals"] == 7
    for chat, attachment_id, original_id, payload in attachments:
        row = target.db.fetch_one("SELECT * FROM knowledge_attachment_originals WHERE id=?", (original_id,))
        assert Path(row["original_path"]).is_relative_to(target.paths.library)
        assert Path(row["original_path"]).read_bytes() == payload
        assert target.db.fetch_one("SELECT chat_id FROM knowledge_attachments WHERE id=?", (attachment_id,))["chat_id"] == chat["identity"]["id"]
    assert restore(target, data)["restored_records"] == 0
    assert target.db.fetch_all("SELECT * FROM memory_jobs") == []


@pytest.mark.parametrize("version", [1, 2])
def test_typed_attachment_and_parent_deletion_never_restore_bytes(version, tmp_path):
    source = create_app(tmp_path / "source").state.services
    target = create_app(tmp_path / "target").state.services
    chat, attachment_id, original_id, _ = seed_attachment(source)
    data, _ = archive_bytes(source, version)
    restore(target, data)
    target.db.mark_deleted("attachment", attachment_id)
    result = restore(target, data)
    assert result["excluded_originals"] == 1
    assert not target.db.fetch_one("SELECT id FROM knowledge_attachments")
    assert not target.db.fetch_one("SELECT id FROM knowledge_attachment_originals")
    assert not list((target.paths.library / "attachments").rglob("original.*"))
    assert target.db.fetch_one("SELECT id FROM learn_threads WHERE id=?", (chat["identity"]["id"],))
    # The same marker in the Case namespace must not delete the Learn owner.
    source.db.mark_deleted("case", chat["identity"]["id"])
    filtered, manifest = archive_bytes(source, version)
    assert len(manifest["originals"]) == 1
    source.db.mark_deleted("learn_thread", chat["identity"]["id"])
    filtered, manifest = archive_bytes(source, version)
    assert manifest["originals"] == []
    checked = preview(target, filtered)
    target.get("data_recovery").restore_preview(checked["preview_token"], checked["exported_at"], True)
    assert not target.db.fetch_one("SELECT id FROM learn_threads WHERE id=?", (chat["identity"]["id"],))


def test_records_only_nulls_attachment_paths_and_zip_requires_current_rights(tmp_path):
    source = create_app(tmp_path / "source").state.services
    target = create_app(tmp_path / "target").state.services
    _, attachment_id, original_id, _ = seed_attachment(source, kind="case")
    bundle = export_records(source)
    assert bundle["records"]["knowledge_attachment_originals"][0]["original_path"] is None
    target.get("data_recovery").restore_json(bundle, confirm_backup_date=True, confirmed_exported_at=bundle["exported_at"])
    rights = own_text_rights().model_dump()
    rights["display"] = False
    target.db.execute("UPDATE knowledge_attachment_metadata SET rights_json=? WHERE attachment_id=?", (json.dumps(rights), attachment_id))
    before = state(target)
    with pytest.raises(ApiError) as failure:
        restore(target, archive_bytes(source, 2)[0])
    assert failure.value.code == "backup_rights"
    assert state(target) == before
    assert target.db.fetch_one("SELECT original_path FROM knowledge_attachment_originals WHERE id=?", (original_id,))["original_path"] is None


@pytest.mark.parametrize("version", [1, 2])
def test_original_promotion_failure_rolls_back_chat_rows_and_bytes(version, tmp_path, monkeypatch):
    source = create_app(tmp_path / "source").state.services
    target = create_app(tmp_path / "target").state.services
    seed_attachment(source)
    seed_attachment(source, suffix="csv")
    data, _ = archive_bytes(source, version)
    before = state(target)
    move, calls = recovery_files._move_no_replace, []
    def fail_second(source_path, destination):
        calls.append(source_path)
        if len(calls) == 2:
            raise OSError("SYNTHETIC disk failure")
        return move(source_path, destination)
    monkeypatch.setattr(recovery_files, "_move_no_replace", fail_second)
    with pytest.raises(ApiError) as failure:
        restore(target, data)
    assert failure.value.code == "backup_file"
    assert state(target) == before
    assert not list((target.paths.state / "recovery/transactions").iterdir())
