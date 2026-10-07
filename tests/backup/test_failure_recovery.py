from contextlib import contextmanager
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from renulus.contracts import ApiError
from renulus.server import create_app
from renulus.storage import recovery_files

from .conftest import forge, preview, restore, state, zip_bytes


def changed_snapshot(source, target):
    services, selected = source
    restore(target, zip_bytes(services))
    services.registry["knowledge"].import_text("SYNTHETIC new electrolyte note after the first backup", process=False)
    def deletion(manifest, bundle, members):
        bundle["records"]["deletion_ledger"].append({"entity_type": "knowledge-document",
            "entity_id": selected[0]["document_id"], "deleted_at": "2026-10-04T23:00:00Z"})
    return forge(zip_bytes(services), deletion)


def test_conflicting_unrelated_target_file_is_not_overwritten(source, target):
    checked = preview(target, zip_bytes(source[0]))
    recovery = target.registry["data_recovery"]
    entry = recovery._preview[2].originals[0]
    target_path = target.paths.root / entry["path"]
    target_path.parent.mkdir(parents=True)
    target_path.write_bytes(b"SYNTHETIC_UNRELATED_LOCAL_FILE")
    before = state(target)
    with pytest.raises(ApiError):
        recovery.restore_preview(checked["preview_token"], checked["exported_at"], True)
    assert state(target) == before
    assert recovery._preview is None
    assert target_path.read_bytes() == b"SYNTHETIC_UNRELATED_LOCAL_FILE"


@pytest.mark.parametrize("point", ["prepare", "promote"])
def test_same_byte_file_appearing_before_our_move_is_never_deleted_by_rollback(source, target, monkeypatch, point):
    checked = preview(target, zip_bytes(source[0]))
    recovery = target.registry["data_recovery"]
    before_collision = []
    operation = getattr(recovery_files.OriginalTransaction, point)
    def collide(transaction):
        entry = transaction.promotions[0]
        destination = target.paths.root / entry["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(entry["staged"].read_bytes())
        before_collision.append(state(target))
        return operation(transaction)
    monkeypatch.setattr(recovery_files.OriginalTransaction, point, collide)
    with pytest.raises(ApiError):
        recovery.restore_preview(checked["preview_token"], checked["exported_at"], True)
    assert state(target) == before_collision[0]
    assert not list((target.paths.state / "recovery/transactions").iterdir())


def test_failure_after_quarantining_deleted_original_restores_existing_records_and_files(source, target, monkeypatch):
    data = changed_snapshot(source, target)
    before = state(target)
    original_move, calls = recovery_files._move_no_replace, []
    def fail_second(source_path, target_path):
        calls.append((source_path, target_path))
        if len(calls) == 2:
            raise OSError("Synthetic disk failure after quarantine")
        return original_move(source_path, target_path)
    monkeypatch.setattr(recovery_files, "_move_no_replace", fail_second)
    with pytest.raises(ApiError) as failure:
        restore(target, data)
    assert failure.value.code == "backup_file"
    assert state(target) == before
    assert len(calls) == 3  # Removal, failed promotion, verified quarantine rollback.
    assert not list((target.paths.state / "recovery/transactions").iterdir())


def test_pending_rollback_keeps_move_identity_and_blocks_operations_until_restart(source, target, monkeypatch):
    data = changed_snapshot(source, target)
    before_records, before_files = state(target)
    move = recovery_files._move_no_replace
    collision = {}
    def fail_promotion_and_rollback(source_path, destination):
        if "verified" in source_path.parts:
            payload = source_path.read_bytes()
            destination.write_bytes(payload)
            collision[destination.relative_to(target.paths.library).as_posix()] = payload
            raise FileExistsError("Synthetic same-byte destination collision")
        if "removed" in source_path.parts:
            raise OSError("Synthetic temporary rollback failure")
        return move(source_path, destination)
    monkeypatch.setattr(recovery_files, "_move_no_replace", fail_promotion_and_rollback)
    recovery = target.registry["data_recovery"]
    with pytest.raises(ApiError) as error:
        restore(target, data)
    assert error.value.code == "recovery_pending"
    assert recovery._preview is None
    assert list((target.paths.cache / "recovery/previews").glob("*/verified/*"))
    for operation in (recovery.backup, recovery.request_rebuild):
        with pytest.raises(ApiError) as error:
            operation()
        assert error.value.code == "recovery_pending"
    monkeypatch.setattr(recovery_files, "_move_no_replace", move)
    restarted = create_app(target.paths.root).state.services
    assert state(restarted) == (before_records, {**before_files, **collision})
    assert not list((restarted.paths.state / "recovery/transactions").iterdir())
    assert not list((restarted.paths.cache / "recovery/previews").iterdir())


def test_database_commit_failure_rolls_back_all_promotions_and_deletion_cleanup(source, target, monkeypatch):
    data = changed_snapshot(source, target)
    checked = preview(target, data)
    before = state(target)
    @contextmanager
    def failed_commit():
        conn = target.db.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            raise sqlite3.OperationalError("Synthetic commit failure")
        finally:
            conn.rollback()
            conn.close()
    monkeypatch.setattr(target.db, "transaction", failed_commit)
    with pytest.raises(ApiError) as failure:
        target.registry["data_recovery"].restore_preview(checked["preview_token"], checked["exported_at"], True)
    assert failure.value.code == "backup_references"
    assert state(target) == before
    assert not list((target.paths.state / "recovery/transactions").iterdir())


@pytest.mark.parametrize("point", ["before_receipt", "after_commit"])
def test_abrupt_process_exit_uses_sqlite_receipt_to_roll_back_or_complete_file_journal(source, target, tmp_path, point):
    data = changed_snapshot(source, target)
    before = state(target)
    archive = tmp_path / "explicit-synthetic-restore.zip"
    archive.write_bytes(data)
    code = """
import os, sys
from pathlib import Path
from renulus.server import create_app
from renulus.storage.recovery_files import OriginalTransaction
services = create_app(sys.argv[1]).state.services
recovery = services.registry['data_recovery']
identifier, directory = recovery.begin_preview()
(directory / 'input.zip').write_bytes(Path(sys.argv[2]).read_bytes())
checked = recovery.complete_preview(identifier, directory)
recovery.end_upload(directory, keep=True)
if sys.argv[3] == 'before_receipt':
    original = OriginalTransaction.promote
    def crash(self):
        original(self)
        os._exit(79)
    OriginalTransaction.promote = crash
else:
    OriginalTransaction.finish = lambda self: os._exit(80)
recovery.restore_preview(checked['preview_token'], checked['exported_at'], True)
raise AssertionError('Synthetic crash injection did not run')
"""
    environment = {**os.environ, "PYTHONPATH": str(Path(__file__).parents[2] / "runtime")}
    result = subprocess.run([sys.executable, "-c", code, str(target.paths.root), str(archive), point],
                            env=environment, capture_output=True, timeout=45)
    assert result.returncode == (79 if point == "before_receipt" else 80), result.stderr.decode()
    assert list((target.paths.state / "recovery/transactions").iterdir())
    restarted = create_app(target.paths.root).state.services
    assert not list((target.paths.state / "recovery/transactions").iterdir())
    assert not list((target.paths.cache / "recovery/previews").iterdir())
    if point == "before_receipt":
        assert state(restarted) == before
    else:
        assert restarted.db.is_deleted("knowledge-document", source[1][0]["document_id"])
        assert restarted.db.fetch_one("SELECT id FROM knowledge_documents WHERE id=?", (source[1][0]["document_id"],)) is None
        assert len(list(restarted.paths.library.rglob("original.*"))) == 4
        assert len(restarted.db.fetch_all("SELECT * FROM storage_recovery_runs")) == 2
        assert restarted.registry["data_recovery"].status()["rebuild"]["status"] == "required"


def test_memory_reindex_seam_receives_only_reconciled_canonical_data_and_no_capture_call(source, target):
    restore(target, zip_bytes(source[0]))
    calls = []
    class Knowledge:
        def rebuild_index(self):
            calls.append("knowledge")
            assert len(target.db.fetch_all("SELECT * FROM knowledge_revisions")) == 4
            return {"status": "complete", "rebuilt_records": 4}
    class Memory:
        def reindex(self):
            calls.append("memory")
            assert all(Path(row["original_path"]).is_file() for row in target.db.fetch_all("SELECT original_path FROM knowledge_revisions"))
            return {"ready": True, "count": 0, "generation": "synthetic-local-generation"}
        def process_pending(self, **kwargs):
            pytest.fail("Rebuild must not trigger generative memory capture")
    target.registry["knowledge"], target.registry["memory"] = Knowledge(), Memory()
    recovery = target.registry["data_recovery"]
    identifier, _, _ = recovery.request_rebuild()
    recovery.rebuild(identifier)
    assert calls == ["knowledge", "memory"]
    status = recovery.status()["rebuild"]
    assert status["status"] == "complete"
    assert status["modules"]["memory"] == {"status": "complete", "rebuilt_records": 0, "rebuilt_unit": "records"}


def test_missing_offline_helper_blocks_rebuild_without_rolling_back_verified_restore(source, target):
    restore(target, zip_bytes(source[0]))
    before = state(target)
    # Index bookkeeping is derived: helper failures may update it, never retained records or originals.
    assert not {"memory_index_state", "memory_index_entries"}.intersection(before[0])
    assert target.db.fetch_one("SELECT state FROM memory_index_state WHERE singleton=1")["state"] == "dirty"
    class HelpersUnavailable:
        def rebuild_index(self):
            raise ApiError("offline_helpers_missing", "Install the packaged offline helpers and retry", 503, True)
    target.registry["knowledge"] = HelpersUnavailable()
    recovery = target.registry["data_recovery"]
    identifier, _, _ = recovery.request_rebuild()
    recovery.rebuild(identifier)
    assert state(target) == before
    assert target.db.fetch_one("SELECT state FROM memory_index_state WHERE singleton=1")["state"] == "failed"
    assert recovery.status()["rebuild"]["status"] == "blocked"
    assert recovery.status()["rebuild"]["modules"]["knowledge"]["error_code"] == "offline_helpers_missing"
    assert recovery.status()["rebuild"]["modules"]["memory"]["status"] == "blocked"
