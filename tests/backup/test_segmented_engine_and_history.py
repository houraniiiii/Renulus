# SPDX-License-Identifier: MIT
"""Format-2 recovery through real CPU engines and historical teaching records."""
import io
import json
from pathlib import Path
import zipfile

from .test_content_release_compatibility import (
    profiles as release_profiles, learner_records, assert_learner_records,
    assert_current_bank, restore_backup, succeeded)
from .test_offline_engine_round_trip import (
    offline_profiles, library_search, memory_search, restore_zip, wait_ready)


def test_segmented_legacy_bank_and_learner_history_keep_latest_target_selection(release_profiles):
    with release_profiles("legacy-segmented", "1.0.0") as (client, services):
        content = services.registry["content"]
        assert content.active_manifest()["version"] == "1.0.0"
        keys = {item["id"]: content.get_question_version(item["id"], item["version"])
            for item in content.list_question_summaries()}
        legacy = learner_records(client, content, "legacy-segmented")
        exported = client.get("/api/v1/data/backup?format_version=2")
        assert exported.status_code == 200, exported.text
        data = exported.content
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            assert manifest["format_version"] == 2
            assert "records.json" not in archive.namelist()
    with release_profiles("latest-segmented") as (client, services):
        assert_current_bank(client)
        target = learner_records(client, services.registry["content"], "target-segmented")
        restored = restore_backup(client, "zip", data, {})
        assert restored["restored_records"] > 0 and restored["format_version"] == 2
        assert_current_bank(client)
        assert_learner_records(client, legacy)
        assert_learner_records(client, target)
        for identifier, snapshot in keys.items():
            assert services.registry["content"].get_question_version(identifier, snapshot["version"]) == snapshot
        assert restore_backup(client, "zip", data, {})["restored_records"] == 0
    with release_profiles("latest-segmented", reopen=True) as (client, services):
        assert_current_bank(client)
        assert_learner_records(client, legacy)
        assert_learner_records(client, target)
        session = succeeded(client.get(f"/api/v1/assessment/sessions/{legacy['session']['id']}"))
        item = session["current_item"]
        key = keys[item["question_id"]]
        finished = succeeded(client.post(f"/api/v1/assessment/sessions/{session['id']}/answer", json={
            "item_id": item["id"], "option_ids": key["correct_option_ids"], "idempotency_key": "v2-restored-resume"}))
        assert finished["feedback"]["correct"] is True
        assert finished["feedback"]["explanation"] == key["rationale"]


def test_actual_cpu_segmented_library_note_restore_retrieve_cite_edit_delete(offline_profiles, tmp_path):
    inputs = tmp_path / "explicit-synthetic-v2-inputs"
    inputs.mkdir()
    contents = {"ckd.txt": "SYNTHETIC CKD education: albuminuria and eGFR trajectories.\n\nStudy kidney disease progression mechanisms.",
        "dialysis.md": "SYNTHETIC dialysis education: fistula access flow and stenosis surveillance.\n\nStudy dialysis access mechanisms."}
    documents, locators = {}, {}
    note_text = "SYNTHETIC learner preference: revisit transplant rejection mechanisms."
    with offline_profiles("v2s") as (client, services):
        for filename, text in contents.items():
            path = inputs / filename
            path.write_text(text, encoding="utf-8")
            topic = "ckd" if filename == "ckd.txt" else "dialysis"
            options = {"title": "Synthetic " + topic + " v2 source", "scope": {"kind": "personal-library"},
                "metadata": {"source_id": "R02", "edition": "Synthetic format-2 proof", "topic_ids": [topic]},
                "idempotency_key": "v2-" + topic}
            documents[topic] = wait_ready(client, succeeded(client.post("/api/v1/library/import/file", content=path.read_bytes(),
                headers={"x-renulus-filename": filename, "x-renulus-import-options": json.dumps(options)}), 202))
            citation = succeeded(client.get(f"/api/v1/library/revisions/{documents[topic]['revision_id']}/citation"))
            assert citation["locators"] and all(locator["char_span"] for locator in citation["locators"])
            locators[topic] = citation["locators"]
        note = succeeded(client.post("/api/v1/memory/facts", json={"text": note_text, "kind": "preference",
            "topic_id": "transplant", "scope": {"kind": "study"}, "idempotency_key": "v2-offline-note"}), 201)
        assert succeeded(client.post("/api/v1/memory/reindex"))["count"] == 1
        source_generation = services.registry["knowledge"].rebuild_index()["generation"]
        assert services.registry["knowledge_worker"].status()["running"]
        response = client.get("/api/v1/data/backup?format_version=2")
        assert response.status_code == 200, response.text
        data = response.content
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            tables = manifest["canonical"]["tables"]
            passage_count = tables["knowledge_passages"]
            assert passage_count > 0 and tables["memory_facts"] == 1
            assert "knowledge_catalogue" not in tables and not any(name.startswith("memory_index") for name in tables)
            preferences = [json.loads(line) for entry in manifest["canonical"]["segments"] if entry["table"] == "preferences"
                for line in archive.read(entry["path"]).splitlines()]
            assert all(row["key"] != "knowledge.index_generation" for row in preferences)
            assert len(manifest["originals"]) == 2
    with offline_profiles("v2t") as (client, services):
        restored, report = restore_zip(client, data)
        assert restored["format_version"] == 2 and restored["restored_originals"] == 2
        assert report["rebuild"]["modules"]["knowledge"]["rebuilt_records"] == passage_count
        assert report["rebuild"]["modules"]["memory"]["rebuilt_records"] == 1
        knowledge, memory = services.registry["knowledge"], services.registry["memory"]
        assert knowledge.index.path.name != source_generation
        assert knowledge.index._table.__class__.__module__.startswith("lancedb")
        assert knowledge.embedder._model.__class__.__module__.startswith("fastembed")
        assert memory._engine.memory.vector_store.client._client.__class__.__name__ == "QdrantLocal"
        assert memory._engine.memory.__class__.__module__ == "mem0.memory.main"
        assert memory._engine.memory.db.connection.execute("SELECT COUNT(*) FROM history").fetchone()[0] == 0
        for topic, document in documents.items():
            revision = document["revision_id"]
            found = library_search(client, "albuminuria eGFR" if topic == "ckd" else "fistula stenosis", topic)
            assert any(hit["document_revision"] == revision for hit in found["passages"])
            citation = succeeded(client.get(f"/api/v1/library/revisions/{revision}/citation"))
            assert citation["locators"] == locators[topic]
            original = client.get(citation["original_url"])
            assert original.status_code == 200
            # write_text uses Windows CRLF; compare the actual selected input
            # bytes, not its normalized source string.
            assert original.content == (inputs / ("ckd.txt" if topic == "ckd" else "dialysis.md")).read_bytes()
            row = services.db.fetch_one("SELECT original_path FROM knowledge_revisions WHERE id=?", (revision,))
            assert Path(row["original_path"]).is_relative_to(services.paths.library)
        assert memory_search(client, "transplant rejection preference")["records"][0]["text"] == note_text
        corrected = "SYNTHETIC corrected preference: revisit glomerular proteinuria mechanisms."
        edited = succeeded(client.patch(f"/api/v1/memory/facts/{note['id']}", json={"text": corrected, "expected_revision": 1}))
        assert edited["revision"] == 2 and edited["purge_pending"] is False
        assert memory_search(client, "glomerular proteinuria preference")["records"][0]["text"] == corrected
        assert succeeded(client.delete(f"/api/v1/memory/facts/{note['id']}?expected_revision=2"))["deleted"]
        assert succeeded(client.delete(f"/api/v1/library/documents/{documents['ckd']['document_id']}"))["status"] == "deleted"
        replayed, _ = restore_zip(client, data)
        assert replayed["restored_originals"] == 1 and replayed["excluded_originals"] == 1
        assert memory_search(client, "transplant glomerular preference")["records"] == []
        assert library_search(client, "albuminuria eGFR", "ckd")["passages"] == []
        assert library_search(client, "fistula stenosis", "dialysis")["passages"]
        assert client.get(f"/api/v1/library/revisions/{documents['ckd']['revision_id']}/citation").status_code == 404
    for filename, text in contents.items():
        assert (inputs / filename).read_text(encoding="utf-8") == text
