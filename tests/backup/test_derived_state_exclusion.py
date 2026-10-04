"""Derived engine identities cannot travel through either recovery format."""
import io
import json
from pathlib import Path
import zipfile

from fastapi.testclient import TestClient
import pytest

from renulus.contracts import ApiError
from renulus.memory.models import ManualFact
from renulus.server import create_app
from renulus.storage.backup import export_records

from .conftest import forge, preview, restore, state, zip_bytes


def seed_canonical_note_and_local_index(services):
    note = services.registry["memory"].add(ManualFact.model_validate({
        "text": "SYNTHETIC study preference: review transplantation mechanisms",
        "kind": "preference", "topic_id": "transplant", "scope": {"kind": "study"},
        "idempotency_key": "derived-exclusion-note"}))
    # Represent an already built derivative without provisioning CPU assets.
    services.db.execute("UPDATE memory_index_state SET generation=?,fingerprint=?,state='ready' WHERE singleton=1",
        ("generation_synthetic_machine_local", "SYNTHETIC_LOCAL_EMBEDDING_FINGERPRINT"))
    services.db.execute("INSERT INTO memory_index_entries VALUES(?,?,?,?)",
        (note["id"], 1, "SYNTHETIC_LOCAL_MEM0_ID", "generation_synthetic_machine_local"))
    services.db.execute("INSERT INTO preferences VALUES(?,?,?)",
        ("knowledge.index_generation", json.dumps("index_" + "1" * 32), "2026-10-04T21:00:00Z"))
    return note


@pytest.mark.parametrize("kind", ["json", "zip"])
def test_download_keeps_canonical_note_history_but_excludes_local_engine_state(source, kind):
    services, _ = source
    note = seed_canonical_note_and_local_index(services)
    client = TestClient(create_app(services.paths.root))
    try:
        response = client.get("/api/v1/data/export" if kind == "json" else "/api/v1/data/backup")
        assert response.status_code == 200, response.text
        if kind == "zip":
            with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                payload = archive.read("records.json")
        else:
            payload = response.content
    finally:
        client.close()
    records = json.loads(payload)["records"]
    assert records["memory_facts"][0]["id"] == note["id"]
    assert records["memory_history"][0]["text"] == note["text"]
    assert records["memory_sources"][0]["record_id"] == note["id"]
    assert "memory_index_state" not in records
    assert "memory_index_entries" not in records
    assert all(row["key"] != "knowledge.index_generation" for row in records["preferences"])
    assert b"SYNTHETIC_LOCAL_MEM0_ID" not in payload
    assert b"SYNTHETIC_LOCAL_EMBEDDING_FINGERPRINT" not in payload


@pytest.mark.parametrize("kind", ["json", "zip"])
@pytest.mark.parametrize("table", ["memory_index_state", "memory_index_entries"])
def test_forged_derived_tables_are_refused_before_any_profile_change(source, target, kind, table):
    services, _ = source
    seed_canonical_note_and_local_index(services)
    incoming = [dict(row) for row in services.db.fetch_all(f'SELECT * FROM "{table}"')]
    before = state(target)
    local_state = [dict(row) for row in target.db.fetch_all("SELECT * FROM memory_index_state")]
    if kind == "json":
        bundle = export_records(services)
        bundle["records"][table] = incoming
        operation = lambda: target.registry["data_recovery"].restore_json(bundle,
            confirm_backup_date=True, confirmed_exported_at=bundle["exported_at"])
    else:
        def add_derived_table(manifest, bundle, members):
            bundle["records"][table] = incoming
        archive = forge(zip_bytes(services), add_derived_table)
        operation = lambda: preview(target, archive)
    with pytest.raises(ApiError) as error:
        operation()
    assert error.value.code == "backup_table"
    assert state(target) == before
    assert [dict(row) for row in target.db.fetch_all("SELECT * FROM memory_index_state")] == local_state
    assert target.db.fetch_all("SELECT * FROM memory_index_entries") == []
    assert not list((target.paths.cache / "recovery/previews").iterdir())


@pytest.mark.parametrize("kind", ["json", "zip"])
def test_large_structured_extraction_is_omitted_before_budget_checks_but_passage_locators_survive(source, target, kind):
    services, selected = source
    item = selected[2]
    structured = json.dumps({"synthetic": "X" * (20 * 1024 * 1024)})
    services.db.execute("UPDATE knowledge_revisions SET extraction_json=? WHERE id=?",
        (structured, item["revision_id"]))
    locators = '[{"page":1,"item_ref":"#/texts/0"}]'
    services.db.execute("INSERT INTO knowledge_passages VALUES(?,?,?,?,?,?,?)",
        ("passage_synthetic_recovery", item["revision_id"], 0, "Synthetic transplant passage",
         "Synthetic transplant passage with heading", locators, '["Synthetic source"]'))
    if kind == "json":
        bundle = export_records(services)
        target.registry["data_recovery"].restore_json(bundle, confirm_backup_date=True,
            confirmed_exported_at=bundle["exported_at"])
    else:
        archive = zip_bytes(services)
        with zipfile.ZipFile(io.BytesIO(archive)) as contents:
            bundle = json.loads(contents.read("records.json"))
        restore(target, archive)
        restored = target.db.fetch_one("SELECT original_path FROM knowledge_revisions WHERE id=?", (item["revision_id"],))
        assert Path(restored["original_path"]).read_bytes() == item["bytes"]
    assert bundle["omissions"]["knowledge_extractions"]["records"] == 1
    assert all(row["extraction_json"] is None for row in bundle["records"]["knowledge_revisions"])
    assert target.db.fetch_one("SELECT extraction_json FROM knowledge_revisions WHERE id=?", (item["revision_id"],))["extraction_json"] is None
    passage = target.db.fetch_one("SELECT * FROM knowledge_passages WHERE id='passage_synthetic_recovery'")
    assert passage["text"] == "Synthetic transplant passage" and passage["locators_json"] == locators
    assert services.db.fetch_one("SELECT extraction_json FROM knowledge_revisions WHERE id=?", (item["revision_id"],))["extraction_json"] == structured
