# SPDX-License-Identifier: MIT
"""Actual additive import migration and private retained recovery boundaries."""
import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

from renulus.design_c_contracts import TABLE_COLUMNS
from renulus.server import MODULE_ORDER, create_app
from renulus.storage import Database, utc_now
from renulus.storage.backup import export_records, restore_records


def import_row(services, **changes):
    value = dict.fromkeys(TABLE_COLUMNS["assessment_test_imports"])
    text = "  SYNTHETIC PRIVATE IMPORT\nA. Dialysis\nAnswer: A\n"
    value.update(id="import_synthetic", title="Synthetic import", state="running", revision=3,
        source_kind="library_revision", source_revision_id="removed_revision",
        live_source_revision_id="removed_revision", original_text=text,
        original_sha256=hashlib.sha256(text.encode()).hexdigest(),
        original_json=json.dumps({"schema":"saved-test-import-original/1", "terms":"Private synthetic terms"}),
        candidates_json=json.dumps([{"edited_stem":"Retained edited CKD question", "resolved":True}]),
        checkpoint_json=json.dumps({"schema":"saved-test-import/1", "route":{"provider":"codex","model":"gpt-6.1-sol"}}),
        policy_revision=1, context_epoch=5, call_count=2, idempotency_key="synthetic-import-create",
        request_hash="a"*64, created_at=utc_now(), updated_at=utc_now())
    value.update(changes)
    with services.db.transaction() as conn:
        columns = list(value)
        conn.execute("INSERT INTO assessment_test_imports ("+",".join(columns)+") VALUES("+",".join("?" for _ in columns)+")", tuple(value.values()))
    return value


def test_import_additive_upgrade_preserves_populated_original_owner_and_blocks_old_inventory(tmp_path):
    services = create_app(tmp_path / "populated").state.services
    thread = services.get("learn").create_thread("SYNTHETIC original learning")
    before = services.db.fetch_one("SELECT * FROM learn_threads WHERE id=?", (thread["id"],))
    with services.db.transaction() as conn:
        # Model the real prior installed inventory, retaining all earlier rows.
        conn.execute("DROP TABLE assessment_test_imports")
        conn.execute("DELETE FROM migration_ledger WHERE name='assessment-005'")
    upgraded = create_app(tmp_path / "populated").state.services
    assert upgraded.db.fetch_one("SELECT * FROM learn_threads WHERE id=?", (thread["id"],)) == before
    with upgraded.db.connect() as conn:
        assert tuple(row["name"] for row in conn.execute("PRAGMA table_info(assessment_test_imports)")) == TABLE_COLUMNS["assessment_test_imports"]
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    base = Path(__file__).parents[2] / "runtime" / "renulus"
    inventory = {"storage-recovery-001": (base / "storage/recovery_schema.sql").read_text(encoding="utf-8")}
    for name in MODULE_ORDER:
        module = base / name
        if (module / "schema.sql").exists():
            inventory[name+"-001"] = (module / "schema.sql").read_text(encoding="utf-8")
        inventory.update({name+"-"+path.stem:path.read_text(encoding="utf-8")
            for path in (module / "migrations").glob("*.sql") if name+"-"+path.stem != "assessment-005"})
    with pytest.raises(RuntimeError, match="unknown to this app"):
        Database(upgraded.paths.database, migration_inventory=inventory)


def test_import_restore_keeps_private_original_edits_pins_and_interrupts_running_without_provider(tmp_path):
    source = create_app(tmp_path / "source").state.services
    original = import_row(source)
    bundle = export_records(source)
    target = create_app(tmp_path / "target").state.services
    target.db.mark_deleted("knowledge-revision", "removed_revision")
    target.db.execute("INSERT INTO preferences VALUES('design_c.context_epoch','4',?)", (utc_now(),))
    target.get("data_recovery").restore_json(bundle, confirm_backup_date=True)
    retained = target.db.fetch_one("SELECT * FROM assessment_test_imports")
    for field in ("original_text", "original_sha256", "original_json", "candidates_json", "source_revision_id", "checkpoint_json", "call_count", "revision"):
        assert retained[field] == original[field], field
    assert retained["live_source_revision_id"] is None
    assert (retained["state"], retained["error_code"]) == ("failed", "interrupted")
    assert target.db.fetch_one("SELECT value FROM preferences WHERE key='design_c.context_epoch'")["value"] == "5"
    assert target.db.fetch_all("SELECT * FROM memory_jobs") == []
    target.db.mark_deleted("test_import", original["id"])
    restore_records(target, bundle, confirm_older=True)
    assert target.db.fetch_all("SELECT * FROM assessment_test_imports") == []


@pytest.mark.parametrize("changes", [{"call_count":4}, {"candidates_json":"{}"}, {"checkpoint_json":"[]"}, {"state":"ready"}, {"source_kind":"temporary"}])
def test_import_ddl_refuses_unbounded_or_wrongly_classified_state(tmp_path, changes):
    services = create_app(tmp_path / "invalid").state.services
    with pytest.raises(sqlite3.IntegrityError):
        import_row(services, **changes)
    assert services.db.fetch_all("SELECT * FROM assessment_test_imports") == []
