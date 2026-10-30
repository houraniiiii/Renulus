# SPDX-License-Identifier: MIT
"""Production Python restore: frontier first, native graphs require their owner."""
import io
import json
import zipfile

import pytest

from renulus.contracts import ApiError, ContextScope, Scope
from renulus.server import create_app
from renulus.storage.backup import export_records, restore_records
from renulus.storage.invalidation import MEMORY_RESTORE_BARRIER_PREFIX, MEMORY_RESTORE_CAPTURE_PREFIX

from .conftest import forge, preview, restore, state
from .test_design_c_attachments import archive_bytes, seed_attachment


def restore_via(source, target, route):
    if route == "records":
        return restore_records(target, export_records(source), confirm_older=True)
    if route == "json":
        return target.get("data_recovery").restore_json(export_records(source), confirm_backup_date=True)
    return restore(target, archive_bytes(source, int(route[-1]))[0])


@pytest.mark.parametrize("route", ["records", "json", "zip1", "zip2"])
def test_missing_deletion_frontier_quarantines_before_mutation(tmp_path, route):
    source = create_app(tmp_path / "source").state.services
    target = create_app(tmp_path / "target").state.services
    source.get("learn").create_thread("SYNTHETIC incoming CKD study")
    target.get("learn").create_thread("SYNTHETIC current transplant study")
    before = state(target)
    if route in ("records", "json"):
        bundle = export_records(source)
        del bundle["records"]["deletion_ledger"]
        with pytest.raises(ApiError) as error:
            if route == "records":
                restore_records(target, bundle, confirm_older=True)
            else:
                target.get("data_recovery").restore_json(bundle, confirm_backup_date=True)
    else:
        data, _ = archive_bytes(source, int(route[-1]))
        if route == "zip1":
            data = forge(data, lambda manifest, bundle, members: bundle["records"].pop("deletion_ledger"))
        else:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                members = {name: archive.read(name) for name in archive.namelist()}
            manifest = json.loads(members["manifest.json"])
            assert manifest["canonical"]["tables"].pop("deletion_ledger") == 0
            members["manifest.json"] = json.dumps(manifest).encode()
            output = io.BytesIO()
            with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
                for name, body in members.items():
                    archive.writestr(name, body)
            data = output.getvalue()
        with pytest.raises(ApiError) as error:
            preview(target, data)
    assert error.value.code == "recovery_frontier_missing"
    assert state(target) == before
    assert target.db.fetch_all("SELECT * FROM memory_jobs") == []


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ["records", "json", "zip1", "zip2"])
async def test_current_frontier_filters_rows_and_originals_before_explicit_capture(tmp_path, route):
    source = create_app(tmp_path / "source").state.services
    target = create_app(tmp_path / "target").state.services
    chat, attachment, original, _ = seed_attachment(source)
    scope = ContextScope(kind=Scope.STUDY)
    payload = json.dumps({"scope": scope.model_dump(mode="json"), "general_learning": True,
                          "text": "SYNTHETIC AKI learning point"})
    source.db.execute("INSERT INTO learning_evidence VALUES('restored-evidence','learning-point',NULL,NULL,?,'now')", (payload,))
    source.db.execute("INSERT INTO memory_jobs VALUES('failed-capture','restored-evidence','foreign',?,'failed',1,'old-error','now','now')",
                      (scope.model_dump_json(),))
    for identifier in ("corrected-fact", "deleted-fact"):
        source.db.execute("INSERT INTO memory_facts VALUES(?,?,'old-hash','concept','aki','study',1,'manual',NULL,'now','now')",
                          (identifier, "SYNTHETIC old learning"))
        source.db.execute("INSERT INTO memory_history VALUES(?,1,'SYNTHETIC old learning','created','now')", (identifier,))
    source.db.execute("INSERT INTO memory_sources VALUES('evidence:suppressed','corrected-fact')")
    target.db.execute("INSERT INTO memory_facts VALUES('corrected-fact','SYNTHETIC current correction','new-hash',"
                      "'concept','aki','study',2,'manual',NULL,'now','now')")
    target.db.execute("INSERT INTO memory_suppression VALUES('evidence:suppressed','now')")
    target.db.mark_deleted("memory_fact", "deleted-fact")
    target.db.mark_deleted("attachment", attachment)
    current = target.get("learn").create_thread("SYNTHETIC newer independent transplant work")
    target.db.execute("CREATE TRIGGER refuse_suppressed_restore BEFORE INSERT ON memory_sources "
                      "WHEN NEW.source_key='evidence:suppressed' BEGIN SELECT RAISE(ABORT,'suppressed row inserted'); END")
    target.db.execute("CREATE TRIGGER refuse_old_history BEFORE INSERT ON memory_history "
                      "WHEN NEW.record_id='corrected-fact' AND NEW.revision<2 BEGIN SELECT RAISE(ABORT,'old history inserted'); END")
    restore_via(source, target, route)
    assert target.db.fetch_one("SELECT text,revision FROM memory_facts WHERE id='corrected-fact'") == {
        "text": "SYNTHETIC current correction", "revision": 2}
    assert target.db.fetch_all("SELECT * FROM memory_history") == []
    assert target.db.fetch_all("SELECT * FROM memory_sources") == []
    assert target.db.fetch_one("SELECT id FROM memory_facts WHERE id='deleted-fact'") is None
    assert target.db.fetch_one("SELECT id FROM learn_threads WHERE id=?", (current["id"],))
    assert target.db.fetch_one("SELECT id FROM learn_threads WHERE id=?", (chat["identity"]["id"],))
    assert target.db.fetch_one("SELECT id FROM knowledge_attachments WHERE id=?", (attachment,)) is None
    assert target.db.fetch_one("SELECT id FROM knowledge_attachment_originals WHERE id=?", (original,)) is None
    assert not (target.paths.library / "attachments" / attachment).exists()
    key = MEMORY_RESTORE_BARRIER_PREFIX + "restored-evidence"
    assert target.db.fetch_one("SELECT value FROM preferences WHERE key=?", (key,))["value"] == "explicit-capture-required"
    assert MEMORY_RESTORE_BARRIER_PREFIX not in str(export_records(target))
    memory = target.get("memory")
    # Prove the new prefix alone fences both scan and delayed/global Retry.
    target.db.execute("DELETE FROM preferences WHERE key=?", (MEMORY_RESTORE_CAPTURE_PREFIX + "restored-evidence",))
    assert (await memory.process_pending(retry=True))["processed"] == 0
    assert target.db.fetch_one("SELECT value FROM preferences WHERE key=?", (key,))
    explicit = memory.enqueue("restored-evidence", scope)
    assert explicit["state"] == "queued"
    assert target.db.fetch_one("SELECT value FROM preferences WHERE key=?", (key,)) is None
    assert target.db.fetch_all("PRAGMA foreign_key_check") == []
    await memory.close()


@pytest.mark.parametrize("route", ["records", "json", "zip1", "zip2"])
@pytest.mark.parametrize("table", ["mappings", "answers", "migrations", "purges"])
def test_native_links_refuse_without_native_owner_mapping(tmp_path, route, table):
    source = create_app(tmp_path / "source").state.services
    target = create_app(tmp_path / "target").state.services
    thread = source.get("learn").create_thread("SYNTHETIC native dialysis study")["id"]
    if table == "mappings":
        source.db.execute("INSERT INTO learn_harness_mappings(thread_id,profile_id,store_id,session_id) VALUES(?,'synthetic-profile','synthetic-store','native-session')", (thread,))
    elif table == "answers":
        source.db.execute("INSERT INTO learn_runs VALUES('run',?,'request','completed',NULL,'now','now')", (thread,))
        source.db.execute("INSERT INTO learn_harness_answers(run_id,thread_id,request_digest,state,input_id) VALUES('run',?,'digest','completed','native-message')", (thread,))
    elif table == "migrations":
        source.db.execute("INSERT INTO learn_harness_migrations(migration_id,thread_id,source_revision,profile_id,store_id,session_id,source_digest,manifest_json,pins_json,message_refs_json) "
                          "VALUES('migration',?,1,'synthetic-profile','synthetic-store','native-session',?,'{}','{}','[]')", (thread, "a" * 64))
    else:
        source.db.execute("INSERT INTO learn_harness_purges VALUES('purge','synthetic-profile','synthetic-store','native-session','operation','attempt','pending')")
    before = state(target)
    with pytest.raises(ApiError) as error:
        restore_via(source, target, route)
    assert error.value.code == "recovery_native_mapping_required"
    assert "TypeScript" in error.value.message
    assert state(target) == before
