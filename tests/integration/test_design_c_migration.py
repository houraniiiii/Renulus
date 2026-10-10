# SPDX-License-Identifier: MIT
"""Design C upgrade/recovery regressions using only owned synthetic profiles."""
import sqlite3

import pytest

from renulus.contracts import ApiError
from renulus.server import create_app
from renulus.storage import Database
from renulus.storage.backup import export_records, restore_records
from renulus.storage.compatibility import LEGACY_COLUMN_DEFAULTS, LEGACY_SCHEMA
from renulus.storage.recovery_limits import SEGMENTED_LIMITS
from renulus.storage.recovery_records import installed_schema, prune_deleted
from renulus.storage.invalidation import context_epoch
from renulus.design_c_contracts import TABLE_COLUMNS
from renulus.storage.assessment_policy import policy_snapshot, require_assistance, advance_policy


PROJECT_FIXTURE = """
CREATE TABLE study_projects(id TEXT PRIMARY KEY);
CREATE TABLE study_project_documents(
    project_id TEXT NOT NULL REFERENCES study_projects(id),
    revision_id TEXT NOT NULL REFERENCES knowledge_revisions(id),
    PRIMARY KEY(project_id,revision_id));
"""


def test_installed_feature_inventory_and_retry_outcomes_survive_recovery(tmp_path):
    services = create_app(tmp_path / "inventory").state.services
    with services.db.connect() as conn:
        for table, expected in TABLE_COLUMNS.items():
            if table.startswith("knowledge_attachment"):
                continue  # Knowledge003 is published with its original/media policy.
            installed = {row["name"] for row in conn.execute(f'PRAGMA table_info("{table}")')}
            assert installed == set(expected), table
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    for table in ("conversation_commands", "study_project_commands", "assessment_attempt_commands"):
        services.db.execute(f'INSERT INTO "{table}" VALUES(?,?,?,?,?,?,?)',
            (table + "_key", "create", "synthetic", "original_id", "hash", '{"id":"original_id"}', "now"))
    bundle = export_records(services)
    target = create_app(tmp_path / "restored").state.services
    restore_records(target, bundle, confirm_older=True)
    for table in ("conversation_commands", "study_project_commands", "assessment_attempt_commands"):
        assert dict(target.db.fetch_one(f'SELECT * FROM "{table}"')) == dict(services.db.fetch_one(f'SELECT * FROM "{table}"'))


def test_policy_revision_blocks_late_help_even_after_test_finishes(tmp_path):
    services = create_app(tmp_path / "policy").state.services
    with services.db.transaction() as conn:
        captured = require_assistance(conn)
        conn.execute("INSERT INTO assessment_test_attempts(id,version_id,version_snapshot_json,mode,clock_high_water_at,created_at,updated_at) VALUES('test','deleted_version','{}','test','now','now','now')")
        assert advance_policy(conn) == 2
        assert policy_snapshot(conn)["active_test_id"] == "test"
        with pytest.raises(ApiError, match="Submit the active Test"):
            require_assistance(conn, expected_revision=captured)
        conn.execute("UPDATE assessment_test_attempts SET status='submitted' WHERE id='test'")
        assert advance_policy(conn) == 3
        with pytest.raises(ApiError, match="policy changed"):
            require_assistance(conn, expected_revision=captured)
        assert require_assistance(conn) == 3
    assert "design_c.assessment_policy_revision" not in {row["key"] for row in export_records(services)["records"]["preferences"]}


def fixture(services):
    imported = services.registry["knowledge"].import_text("SYNTHETIC shared CKD document", process=False)
    services.db.execute("INSERT INTO study_projects(id,title,created_at,updated_at) VALUES('project_synthetic','Synthetic project','now','now')")
    services.db.execute("INSERT INTO study_project_documents(id,project_id,revision_id,created_at) VALUES('link_synthetic',?,?,'now')",
        ("project_synthetic", imported["revision_id"]))
    services.db.mark_deleted("project", "project_synthetic")
    return imported


def test_composite_link_identity_preserves_independent_endpoints(tmp_path):
    db = Database(tmp_path / "composite.sqlite3")
    db.apply_migration("fixture-composite", """
      CREATE TABLE knowledge_documents(id TEXT PRIMARY KEY);
      CREATE TABLE knowledge_revisions(id TEXT PRIMARY KEY,document_id TEXT);
    """ + PROJECT_FIXTURE)
    db.execute("INSERT INTO knowledge_documents VALUES('document')")
    db.execute("INSERT INTO knowledge_revisions VALUES('revision','document')")
    db.execute("INSERT INTO study_projects VALUES('project')")
    db.execute("INSERT INTO study_project_documents VALUES('project','revision')")
    db.mark_deleted("project", "project")
    with db.transaction() as conn:
        conn.execute("PRAGMA defer_foreign_keys=ON")
        prune_deleted(conn, installed_schema(conn, SEGMENTED_LIMITS), SEGMENTED_LIMITS)
    assert db.fetch_all("SELECT * FROM study_project_documents") == []
    assert db.fetch_one("SELECT id FROM knowledge_revisions")["id"] == "revision"
    assert db.fetch_one("SELECT id FROM knowledge_documents")["id"] == "document"


def test_unlinked_membership_tombstone_cannot_revive_from_older_export(tmp_path):
    services = create_app(tmp_path / "unlink").state.services
    imported = services.registry["knowledge"].import_text("SYNTHETIC transplant study note", process=False)
    services.db.execute("INSERT INTO study_projects(id,title,created_at,updated_at) VALUES('project','Study','now','now')")
    services.db.execute("INSERT INTO study_project_documents(id,project_id,revision_id,created_at) VALUES('link','project',?,'now')", (imported["revision_id"],))
    before = export_records(services)
    services.db.mark_deleted("project_document", "link")
    restore_records(services, before, confirm_older=True)
    assert services.db.fetch_all("SELECT * FROM study_project_documents") == []
    assert services.db.fetch_one("SELECT id FROM study_projects WHERE id='project'")
    assert services.db.fetch_one("SELECT id FROM knowledge_revisions WHERE id=?", (imported["revision_id"],))


@pytest.mark.parametrize("recovery_path", ["json", "segmented"])
def test_project_link_deletion_preserves_shared_revision_and_original_identity(tmp_path, recovery_path):
    services = create_app(tmp_path / recovery_path).state.services
    imported = fixture(services)
    if recovery_path == "json":
        restore_records(services, export_records(services), confirm_older=True)
    else:
        with services.db.connect() as conn:
            conn.execute("PRAGMA defer_foreign_keys=ON")
            prune_deleted(conn, installed_schema(conn, SEGMENTED_LIMITS), SEGMENTED_LIMITS)
    assert services.db.fetch_all("SELECT * FROM study_projects") == []
    assert services.db.fetch_all("SELECT * FROM study_project_documents") == []
    assert services.db.fetch_one("SELECT id FROM knowledge_revisions WHERE id=?", (imported["revision_id"],))
    assert services.db.fetch_one("SELECT id FROM knowledge_documents WHERE id=?", (imported["document_id"],))


@pytest.mark.parametrize("recovery_path", ["json", "segmented"])
def test_tombstone_namespaces_and_edited_memory_provenance_are_independent(tmp_path, recovery_path):
    services = create_app(tmp_path / recovery_path).state.services
    thread = services.registry["learn"].create_thread("SYNTHETIC dialysis learning")
    services.db.mark_deleted("case", thread["id"])
    services.db.execute("INSERT INTO memory_facts VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        ("fact_synthetic", "SYNTHETIC independently edited learning", "synthetic_hash", "concept",
         "dialysis", "study", 2, "study", thread["id"], "now", "now"))
    # The real schema has eleven columns; retain history independently of its
    # removed source. This fixture never calls an engine or generative provider.
    services.db.execute("INSERT INTO memory_history VALUES(?,?,?,?,?)",
        ("fact_synthetic", 2, "SYNTHETIC independently edited learning", "edited", "now"))
    if recovery_path == "json":
        restore_records(services, export_records(services), confirm_older=True)
    else:
        with services.db.connect() as conn:
            prune_deleted(conn, installed_schema(conn, SEGMENTED_LIMITS), SEGMENTED_LIMITS)
    assert services.db.fetch_one("SELECT id FROM learn_threads WHERE id=?", (thread["id"],))
    services.db.mark_deleted("learn_thread", thread["id"])
    if recovery_path == "json":
        restore_records(services, export_records(services), confirm_older=True)
    else:
        with services.db.connect() as conn:
            conn.execute("PRAGMA defer_foreign_keys=ON")
            prune_deleted(conn, installed_schema(conn, SEGMENTED_LIMITS), SEGMENTED_LIMITS)
    assert services.db.fetch_one("SELECT id FROM memory_facts WHERE id='fact_synthetic'")
    assert services.db.fetch_one("SELECT record_id FROM memory_history WHERE record_id='fact_synthetic'")


def test_schema_one_populated_json_upgrades_exact_known_columns_without_reclassifying(tmp_path, monkeypatch):
    source = create_app(tmp_path / "source").state.services
    thread = source.registry["learn"].create_thread("SYNTHETIC transplant learning")
    bundle = {**export_records(source), "schema_version": 1}
    bundle["records"] = {name: rows for name, rows in bundle["records"].items() if name in LEGACY_SCHEMA}
    target = create_app(tmp_path / "target").state.services
    target.db.execute("ALTER TABLE learn_threads ADD COLUMN lifecycle TEXT NOT NULL DEFAULT 'active'")
    with pytest.raises(ApiError, match="explicitly supported column"):
        restore_records(target, bundle, confirm_older=True)
    assert target.db.fetch_all("SELECT * FROM learn_threads") == []
    monkeypatch.setitem(LEGACY_COLUMN_DEFAULTS, ("learn_threads", "lifecycle"), "active")
    restored = restore_records(target, bundle, confirm_older=True)
    assert restored["restored_records"] > 0
    row = target.db.fetch_one("SELECT * FROM learn_threads WHERE id=?", (thread["id"],))
    assert row["title"] == thread["title"] and row["lifecycle"] == "active"
    assert restore_records(target, bundle, confirm_older=True)["restored_records"] == 0


def test_unknown_applied_migration_refuses_before_schema_stamp_or_feature_writes(tmp_path):
    path = tmp_path / "unknown.sqlite3"
    db = Database(path)
    db.apply_migration("future-module-009", "CREATE TABLE future_record(id TEXT);")
    with db.connect() as conn:
        conn.execute("PRAGMA user_version=1")
    with pytest.raises(RuntimeError, match="unknown.*downgrade refused"):
        Database(path, migration_inventory={})
    with sqlite3.connect(path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM future_record").fetchone()[0] == 0


def test_restore_invalidates_derived_state_atomically_without_provider_work(tmp_path):
    source = create_app(tmp_path / "source").state.services
    source.registry["learn"].create_thread("SYNTHETIC glomerular learning")
    target = create_app(tmp_path / "target").state.services
    target.db.execute("UPDATE memory_index_state SET state='ready',epoch=7 WHERE singleton=1")
    before = context_epoch(target.db)
    result = target.registry["data_recovery"].restore_json(export_records(source), confirm_backup_date=True,
        confirmed_exported_at=None)
    assert result["indexes"] == "rebuild-required"
    state = target.db.fetch_one("SELECT epoch,state FROM memory_index_state WHERE singleton=1")
    assert state == {"epoch": 8, "state": "dirty"}
    assert context_epoch(target.db) == before + 1
    assert target.db.fetch_one("SELECT value FROM preferences WHERE key='knowledge.restore_dirty'")["value"] == "true"
    assert 'design_c.context_epoch' not in str(export_records(target))
    assert target.db.fetch_all("SELECT * FROM memory_jobs") == []
