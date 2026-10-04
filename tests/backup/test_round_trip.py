from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import zipfile

from fastapi.testclient import TestClient
import pytest

from renulus.contracts import ApiError
from renulus.server import create_app
from renulus.storage.backup import export_records
from renulus.storage.recovery_archive import DEFAULT_LIMITS

from .conftest import forge, preview, restore, state, zip_bytes


def test_text_pdf_image_originals_and_learning_records_round_trip_into_fresh_profile(source, target):
    source_services, selected = source
    archive = zip_bytes(source_services)
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        names = bundle.namelist()
        records = json.loads(bundle.read("records.json"))
        assert len(names) == 6  # Manifest, JSON and four actual originals.
        all_contents = b"".join(bundle.read(name) for name in names)
        for sentinel in (b"SYNTHETIC_PROTECTED_SENTINEL", b"SYNTHETIC_PROVIDER_SENTINEL",
                         b"SYNTHETIC_WEIGHT_SENTINEL", b"SYNTHETIC_INDEX_SENTINEL", b"SYNTHETIC_UNREFERENCED_SENTINEL"):
            assert sentinel not in all_contents
        assert str(source_services.paths.root).encode() not in all_contents
        assert all(row["original_path"].startswith("library/knowledge/") for row in records["records"]["knowledge_revisions"])
    result = restore(target, archive)
    assert result["restored_originals"] == 4
    assert result["excluded_originals"] == 0
    assert result["indexes"] == "rebuild-required"
    assert target.db.fetch_one("SELECT value FROM preferences WHERE key='learn.teaching_style'")["value"] == "guided"
    assert target.db.fetch_one("SELECT id FROM learning_evidence WHERE id='evidence_synthetic'")
    assert not target.db.fetch_one("SELECT value FROM preferences WHERE key='runtime.selected_provider'")
    for item in selected:
        row = target.db.fetch_one("SELECT * FROM knowledge_revisions WHERE id=?", (item["revision_id"],))
        path = Path(row["original_path"])
        assert path.is_relative_to(target.paths.library)
        assert path.read_bytes() == item["bytes"]
        assert row["sha256"] == hashlib.sha256(item["bytes"]).hexdigest()
        assert row["bytes"] == len(item["bytes"])
        assert json.loads(row["metadata_json"])["edition"] == "Synthetic recovery 1"
        assert item["input"].read_bytes() == item["bytes"]  # External selected original preserved.
    before = state(target)
    repeated = restore(target, archive)
    assert repeated["restored_records"] == 0
    assert state(target) == before


def test_newer_local_tombstone_removes_originals_before_rebuild_and_never_promotes_deleted_revision(source, target):
    services, selected = source
    archive = zip_bytes(services)
    restore(target, archive)
    deleted = selected[0]
    target.db.mark_deleted("knowledge-document", deleted["document_id"])
    timeline = []
    memory_calls = []
    memory = target.registry["memory"]
    class Seam:
        @contextmanager
        def recovery_guard(self):
            timeline.append("guard")
            yield
            timeline.append("promoted")
        def rebuild_index(self):
            timeline.append("rebuild")
            assert target.db.fetch_one("SELECT id FROM knowledge_documents WHERE id=?", (deleted["document_id"],)) is None
            assert not list((target.paths.library / "knowledge" / deleted["document_id"]).rglob("original.*"))
            assert len(list(target.paths.library.rglob("original.*"))) == 3
            return {"status": "complete", "rebuilt_records": 0}
    class Memory:
        def recovery_guard(self):
            return memory.recovery_guard()
        def reindex(self):
            memory_calls.append("reindex")
            assert timeline == ["guard", "promoted", "rebuild"]
            return {"ready": True, "count": 0, "generation": "synthetic-memory-generation"}
        def process_pending(self, **kwargs):
            pytest.fail("Recovery must rebuild memory without capturing or calling a provider")
    target.registry.update(knowledge=Seam(), memory=Memory())
    result = restore(target, archive)
    assert result["excluded_originals"] == 1
    assert result["removed_by_deletion"] == 3
    assert target.db.is_deleted("knowledge-document", deleted["document_id"])
    identifier, _, start = target.registry["data_recovery"].request_rebuild()
    assert start
    target.registry["data_recovery"].rebuild(identifier)
    assert timeline == ["guard", "promoted", "rebuild"]
    assert memory_calls == ["reindex"]
    assert target.registry["data_recovery"].status()["rebuild"]["status"] == "complete"


def test_imported_tombstone_wins_over_already_restored_original_and_descendants(source, target):
    services, selected = source
    archive = zip_bytes(services)
    restore(target, archive)
    deleted = selected[1]
    def remove_incoming(manifest, bundle, members):
        bundle["records"]["deletion_ledger"].append({"entity_type": "knowledge-document",
            "entity_id": deleted["document_id"], "deleted_at": "2026-10-04T23:00:00+00:00"})
    result = restore(target, forge(archive, remove_incoming))
    assert result["excluded_by_deletion"] == 3
    assert result["removed_by_deletion"] == 3
    assert result["excluded_originals"] == 1
    for table, column, identifier in (("knowledge_documents", "id", deleted["document_id"]),
                                      ("knowledge_revisions", "id", deleted["revision_id"]),
                                      ("knowledge_jobs", "revision_id", deleted["revision_id"])):
        assert target.db.fetch_one(f"SELECT * FROM {table} WHERE {column}=?", (identifier,)) is None
    assert not list((target.paths.library / "knowledge" / deleted["document_id"]).rglob("original.*"))


def test_records_only_export_drops_paths_and_restores_without_copying_any_original(source, target):
    services, selected = source
    bundle = export_records(services)
    assert bundle["data_kind"] == "records-only"
    assert all(row["original_path"] is None for row in bundle["records"]["knowledge_revisions"])
    # Even an old/forged absolute reference is never read by the JSON route.
    bundle["records"]["knowledge_revisions"][0]["original_path"] = str(selected[0]["input"])
    result = target.registry["data_recovery"].restore_json(bundle, confirm_backup_date=True,
        confirmed_exported_at=bundle["exported_at"])
    assert result["restored_originals"] == 0
    assert result["data_kind"] == "records-only"
    assert list(target.paths.library.rglob("original.*")) == []
    assert all(row["original_path"] is None for row in target.db.fetch_all("SELECT * FROM knowledge_revisions"))
    assert selected[0]["input"].read_bytes() == selected[0]["bytes"]
    result = restore(target, zip_bytes(services))  # ZIP can later supply verified originals for same records.
    assert result["restored_records"] == 0
    assert result["restored_originals"] == 4


def test_old_zip_cannot_reinstate_originals_against_newer_target_caching_rights(source, target):
    services, selected = source
    bundle = export_records(services)
    target.registry["data_recovery"].restore_json(bundle, confirm_backup_date=True,
        confirmed_exported_at=bundle["exported_at"])
    row = target.db.fetch_one("SELECT rights_json FROM knowledge_revisions WHERE id=?", (selected[0]["revision_id"],))
    rights = json.loads(row["rights_json"])
    rights["cache"], rights["display"] = False, False
    target.db.execute("UPDATE knowledge_revisions SET rights_json=? WHERE id=?", (json.dumps(rights), selected[0]["revision_id"]))
    before = state(target)
    with pytest.raises(ApiError) as error:
        restore(target, zip_bytes(services))
    assert error.value.code == "backup_rights"
    assert state(target) == before
    assert not list(target.paths.library.rglob("original.*"))


def test_deliberate_date_confirmation_expiry_and_one_use_preview(source, target):
    archive = zip_bytes(source[0])
    checked = preview(target, archive)
    recovery = target.registry["data_recovery"]
    before = state(target)
    for date, acknowledgment in ((checked["exported_at"], False), ("2020-01-01T00:00:00Z", True)):
        with pytest.raises(ApiError) as failure:
            recovery.restore_preview(checked["preview_token"], date, acknowledgment)
        assert failure.value.code == "restore_confirmation"
        assert state(target) == before
    old = recovery._preview
    recovery._preview = (old[0], datetime.now(timezone.utc) - timedelta(seconds=1), old[2])
    with pytest.raises(ApiError) as failure:
        recovery.restore_preview(checked["preview_token"], checked["exported_at"], True)
    assert failure.value.code == "backup_preview_expired"
    assert state(target) == before
    assert not old[2].directory.exists()
    checked = preview(target, archive)
    recovery.restore_preview(checked["preview_token"], checked["exported_at"], True)
    with pytest.raises(ApiError, match="verify"):
        recovery.restore_preview(checked["preview_token"], checked["exported_at"], True)


@pytest.mark.parametrize("cleanup_pending", [False, True])
def test_parent_rebuild_contracts_persist_passage_counts_and_keep_index_pointer_local(source, target, cleanup_pending):
    services, _ = source
    source_generation = "index_" + "a" * 32
    target_generation = "index_" + "b" * 32
    services.db.execute("INSERT INTO preferences VALUES(?,?,?)", (
        "knowledge.index_generation", json.dumps(source_generation), "2026-10-04T21:00:00Z"))
    target.db.execute("INSERT INTO preferences VALUES(?,?,?)", (
        "knowledge.index_generation", json.dumps(target_generation), "2026-10-04T21:00:00Z"))
    restore(target, zip_bytes(services))
    assert target.db.fetch_one("SELECT value FROM preferences WHERE key='knowledge.index_generation'")["value"] == json.dumps(target_generation)
    calls = []
    class Knowledge:
        def rebuild_index(self):
            assert len(target.db.fetch_all("SELECT id FROM knowledge_revisions WHERE original_path IS NOT NULL")) == 4
            calls.append("knowledge")
            return {"status": "ready", "passages": 17, "generation": "index_" + "c" * 32,
                    "cleanup_pending": cleanup_pending}
    class Memory:
        def reindex(self):
            calls.append("memory")
            return {"ready": True, "count": 3, "generation": "memory_local"}
        def process_pending(self):
            pytest.fail("Recovery must never capture memory or call a provider")
    target.registry.update(knowledge=Knowledge(), memory=Memory())
    recovery = target.registry["data_recovery"]
    identifier, running, start = recovery.request_rebuild()
    assert start and running["status"] == "running"
    recovery.rebuild(identifier)
    expected = "partial" if cleanup_pending else "complete"
    report = recovery.status()["rebuild"]
    assert calls == ["knowledge", "memory"]
    assert report["status"] == expected
    assert report["modules"]["knowledge"]["rebuilt_records"] == 17
    assert report["modules"]["knowledge"]["rebuilt_unit"] == "passages"
    assert report["modules"]["knowledge"]["cleanup_pending"] is cleanup_pending
    assert report["modules"]["memory"] == {"status": "complete", "rebuilt_records": 3, "rebuilt_unit": "records"}
    if cleanup_pending:
        assert "search is ready" in report["modules"]["knowledge"]["message"]
    assert create_app(target.paths.root).state.services.registry["data_recovery"].status()["rebuild"] == report
    records = export_records(target)
    assert all(row["key"] != "knowledge.index_generation" for row in records["records"]["preferences"])


@pytest.mark.parametrize("worker_status", [
    {"running": True, "active_job": None, "queued": 0},
    {"running": False, "active_job": "synthetic-job-still-finishing", "queued": 0},
])
def test_restore_refuses_uncoordinated_worker_even_when_idle_then_uses_public_guard(source, target, worker_status):
    archive = zip_bytes(source[0])
    class Worker:
        def status(self):
            return worker_status
    class GuardlessKnowledge:
        pass
    # The parent now supplies a guard; explicitly exercise a legacy adapter without it.
    target.registry["knowledge"] = GuardlessKnowledge()
    target.registry["knowledge_worker"] = Worker()
    before = state(target)
    with pytest.raises(ApiError) as error:
        restore(target, archive)
    assert error.value.code == "recovery_busy"
    assert state(target) == before
    guarded = []
    class Knowledge:
        @contextmanager
        def recovery_guard(self):
            guarded.append("entered")
            yield
            guarded.append("released")
    target.registry["knowledge"] = Knowledge()
    assert restore(target, archive)["restored_originals"] == 4
    assert guarded == ["entered", "released"]


def test_real_http_download_raw_preview_restore_and_honest_missing_rebuild_seam(source, tmp_path):
    source_services, _ = source
    source_client = TestClient(create_app(source_services.paths.root))
    downloaded = source_client.get("/api/v1/data/backup")
    assert downloaded.status_code == 200
    assert downloaded.headers["content-type"] == "application/zip"
    assert downloaded.headers["cache-control"] == "no-store"
    assert not list((source_services.paths.cache / "recovery/exports").iterdir())
    app = create_app(tmp_path / "http-target")
    knowledge = app.state.services.registry["knowledge"]
    class KnowledgeWithoutRebuild:
        def recovery_guard(self):
            return knowledge.recovery_guard()
    # Keep real recovery coordination while modelling a runtime without the rebuild seam.
    app.state.services.registry["knowledge"] = KnowledgeWithoutRebuild()
    client = TestClient(app)
    checked = client.post("/api/v1/data/backup/preview", content=downloaded.content,
                          headers={"content-type": "application/zip"})
    assert checked.status_code == 200
    fields = {"preview_token": checked.json()["preview_token"], "confirmed_exported_at": checked.json()["exported_at"]}
    assert client.post("/api/v1/data/backup/restore", json=fields).status_code == 409
    result = client.post("/api/v1/data/backup/restore", json={**fields, "acknowledge_deletion_limits": True})
    assert result.status_code == 200
    assert result.json()["restored_originals"] == 4
    status = client.get("/api/v1/data/recovery").json()
    assert status["rebuild"]["status"] == "blocked"
    assert status["rebuild"]["modules"]["knowledge"]["error_code"] == "rebuild_seam_missing"
    records_only = client.get("/api/v1/data/export")
    assert records_only.headers["x-renulus-data-kind"] == "records-only"
    assert records_only.json()["data_kind"] == "records-only"
    assert client.post("/api/v1/data/rebuild").status_code == 202
    assert client.get("/api/v1/data/recovery").json()["rebuild"]["status"] == "blocked"


def test_catalogue_at_183891_rows_is_explicitly_omitted_without_reading_bulk_metadata(source, monkeypatch):
    services, _ = source
    services.db.execute("""WITH RECURSIVE numbers(n) AS (
        SELECT 1 UNION ALL SELECT n+1 FROM numbers WHERE n<183891)
        INSERT INTO knowledge_catalogue(id,collection_path,source_id,title,bytes,reserved,eligibility,metadata_json,rights_json,checked_at)
        SELECT 'acquired_'||n, 'C:/SYNTHETIC-EXTERNAL-COLLECTION/'||n, 'R02', 'Synthetic acquired metadata',
        4096, 0, 'unverified', json_object('notes',replace(hex(zeroblob(256)),'0','S')), '{}', '2026-10-04T21:00:00Z'
        FROM numbers""")
    import sqlite3
    connect = services.db.connect
    def count_only():
        conn = connect()
        def authorise(action, table, column, database, trigger):
            if action == sqlite3.SQLITE_READ and table == "knowledge_catalogue" and column:
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        conn.set_authorizer(authorise)
        return conn
    monkeypatch.setattr(services.db, "connect", count_only)
    records = export_records(services)
    assert "knowledge_catalogue" not in records["records"]
    assert records["omissions"]["knowledge_catalogue"]["records"] == 183891
    assert len(json.dumps(records)) < 1024 * 1024
    data = zip_bytes(services)
    assert len(data) < 1024 * 1024
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        contents = archive.read("records.json")
        assert b"SYNTHETIC-EXTERNAL-COLLECTION" not in contents
        assert json.loads(contents)["omissions"]["knowledge_catalogue"]["records"] == 183891


def test_oversized_learner_table_is_refused_before_materializing_it_for_either_export(source, monkeypatch):
    services, _ = source
    services.db.execute("""WITH RECURSIVE numbers(n) AS (
        SELECT 1 UNION ALL SELECT n+1 FROM numbers WHERE n<100000)
        INSERT INTO learning_evidence(id,kind,topic_id,entity_id,payload_json,created_at)
        SELECT 'synthetic-scale-'||n, 'manual-study', NULL, NULL, '{}', '2026-10-04T21:00:00Z' FROM numbers""")
    import sqlite3
    connect = services.db.connect
    def count_only():
        conn = connect()
        conn.set_authorizer(lambda action, table, column, database, trigger:
            sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_READ and table == "learning_evidence" and column else sqlite3.SQLITE_OK)
        return conn
    monkeypatch.setattr(services.db, "connect", count_only)
    for operation in (lambda: export_records(services), lambda: services.registry["data_recovery"].backup()):
        with pytest.raises(ApiError) as error:
            operation()
        assert error.value.code == "backup_limit" and error.value.status == 413
    assert not list((services.paths.cache / "recovery/exports").iterdir())


@pytest.mark.parametrize("kind", ["json", "zip"])
def test_imported_library_citation_rights_and_parent_source_journal_survive_fresh_restore(source, target, kind):
    services, selected = source
    # Exact canonical table shape from parent's 19762d0e additive migration.
    schema = """CREATE TABLE knowledge_source_status_events (
        id TEXT PRIMARY KEY, source_id TEXT NOT NULL, request_hash TEXT NOT NULL,
        payload_json TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE INDEX knowledge_source_status_source ON knowledge_source_status_events(source_id);"""
    for installation in (services, target):
        if not installation.db.fetch_one("SELECT 1 FROM sqlite_master WHERE type='table' AND name='knowledge_source_status_events'"):
            installation.db.apply_migration("synthetic-source-status-002", schema)
    selected_revision = selected[0]["revision_id"]
    services.db.execute("INSERT INTO knowledge_passages VALUES(?,?,?,?,?,?,?)", (
        "pass_synthetic_citation", selected_revision, 0, "Synthetic CKD study passage",
        "Synthetic source title > CKD > Synthetic CKD study passage",
        '[{"page":1,"label":"Synthetic citation locator"}]', '["Synthetic CKD section"]'))
    events = []
    for identifier, change, date in (("synthetic-z-first", "content_reviewed", "2026-10-04T21:00:00Z"),
                                    ("synthetic-a-second", "latest_final_verified", "2026-10-04T21:02:00Z")):
        payload = json.dumps({"contract_version": 1, "event_id": identifier, "source_id": "R02",
            "identity": {"canonical_url": "https://example.invalid/synthetic-source"},
            "changes": {change: False}}, sort_keys=True, separators=(",", ":"))
        row = {"id": identifier, "source_id": "R02", "request_hash": hashlib.sha256(payload.encode()).hexdigest(),
               "payload_json": payload, "created_at": date}
        services.db.execute("INSERT INTO knowledge_source_status_events VALUES(?,?,?,?,?)", tuple(row.values()))
        events.append(row)
    rights = services.db.fetch_one("SELECT rights_json FROM knowledge_revisions WHERE id=?", (selected_revision,))["rights_json"]
    if kind == "zip":
        result = restore(target, zip_bytes(services))
        assert result["restored_originals"] == 4
    else:
        bundle = export_records(services)
        assert "knowledge_catalogue" not in bundle["records"]
        result = target.registry["data_recovery"].restore_json(bundle, confirm_backup_date=True,
            confirmed_exported_at=bundle["exported_at"])
        assert result["restored_originals"] == 0
    assert [dict(row) for row in target.db.fetch_all("SELECT * FROM knowledge_source_status_events ORDER BY rowid")] == events
    citation = target.db.fetch_one("SELECT * FROM knowledge_passages WHERE id='pass_synthetic_citation'")
    assert citation["revision_id"] == selected_revision
    assert json.loads(citation["locators_json"]) == [{"page": 1, "label": "Synthetic citation locator"}]
    assert json.loads(citation["headings_json"]) == ["Synthetic CKD section"]
    assert target.db.fetch_one("SELECT rights_json FROM knowledge_revisions WHERE id=?", (selected_revision,))["rights_json"] == rights
