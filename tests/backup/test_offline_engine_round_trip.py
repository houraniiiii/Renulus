"""Opt-in ZIP recovery through actual CPU engines and isolated synthetic profiles.

Set RENULUS_RECOVERY_HELPERS to the verified public helper directory. Only that
directory is shared read-only; no installed profile, index, key or corpus is used.
The test requires the selected packages and never provisions assets or providers.
"""
import asyncio
import builtins
from contextlib import contextmanager
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import time
import traceback
import zipfile

import pytest
from fastapi.testclient import TestClient

from renulus import server
from renulus.storage import AppPaths


@pytest.fixture
def offline_profiles(tmp_path_factory, monkeypatch):
    configured = os.environ.get("RENULUS_RECOVERY_HELPERS")
    if not configured:
        pytest.skip("Set RENULUS_RECOVERY_HELPERS to verified public CPU assets")
    helper_root = Path(configured).resolve()
    assert (helper_root / "manifest.json").is_file(), "Explicit helper manifest is missing"
    required = ("docling", "docling_core", "fastembed", "lancedb", "mem0", "qdrant_client")
    assert all(importlib.util.find_spec(name) is not None for name in required), "Selected offline packages are required"
    source_root = Path(__file__).resolve().parents[2]
    trusted = json.loads((source_root / "packaging/runtime/helper-assets.json").read_text(encoding="utf-8"))

    def asset_snapshot():
        paths = ["manifest.json", *{entry["path"] for group in trusted["groups"].values() for entry in group["files"]}]
        return {name: (helper_root / name).stat().st_size for name in paths}

    before_assets = asset_snapshot()
    attempted = []
    # Leave room for native Lance generation/data filenames on Windows.
    profiles_root = tmp_path_factory.mktemp("rcpu")

    def no_write(path, writing):
        if writing and isinstance(path, (str, bytes, os.PathLike)) and Path(os.fsdecode(path)).resolve().is_relative_to(helper_root):
            attempted.append("shared-helper-write")
            raise AssertionError("Shared helper artifacts are read-only")

    def guarded_open(operation):
        def open_file(file, mode="r", *args, **kwargs):
            no_write(file, any(flag in mode for flag in "wax+"))
            return operation(file, mode, *args, **kwargs)
        return open_file

    original_os_open = os.open
    def open_descriptor(path, flags, *args, **kwargs):
        no_write(path, bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)))
        return original_os_open(path, flags, *args, **kwargs)
    monkeypatch.setattr(builtins, "open", guarded_open(builtins.open))
    monkeypatch.setattr(io, "open", guarded_open(io.open))
    monkeypatch.setattr(os, "open", open_descriptor)

    def local_only(address):
        return isinstance(address, tuple) and address[0] in ("localhost", "127.0.0.1", "::1")

    def guarded_connect(operation):
        def connect(sock, address):
            if not local_only(address):
                attempted.append("external-network")
                raise AssertionError("External network is forbidden in recovery proof")
            return operation(sock, address)
        return connect
    monkeypatch.setattr(socket.socket, "connect", guarded_connect(socket.socket.connect))
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect(socket.socket.connect_ex))
    original_connection = socket.create_connection
    def create_connection(address, *args, **kwargs):
        if not local_only(address):
            attempted.append("external-network")
            raise AssertionError("External network is forbidden in recovery proof")
        return original_connection(address, *args, **kwargs)
    monkeypatch.setattr(socket, "create_connection", create_connection)

    class SharedReadOnlyHelpers(AppPaths):
        @property
        def helpers(self):
            return helper_root
    monkeypatch.setattr(server, "AppPaths", SharedReadOnlyHelpers)

    class NoProvider:
        async def stream(self, *args, **kwargs):
            attempted.append("provider-generation")
            raise AssertionError("Recovery must never call a provider")
            yield  # Keep the existing async streaming interface.
        async def cancel(self, *args, **kwargs):
            attempted.append("provider-cancellation")
            raise AssertionError("No provider operation is expected")

    @contextmanager
    def profile(name):
        root = profiles_root / name
        assert not root.exists()
        app = server.create_app(root, token="synthetic-recovery-session", source_root=source_root)
        services = app.state.services
        assert services.paths.helpers == helper_root
        assert all(path.is_relative_to(root) for path in (services.paths.state, services.paths.cache, services.paths.indexes, services.paths.library))
        services.registry["provider"] = NoProvider()
        rebuild_errors = services.registry["recovery_proof_errors"] = []
        knowledge = services.registry["knowledge"]
        rebuild = knowledge.rebuild_index
        def traced_rebuild():
            try:
                return rebuild()
            except Exception:
                # The production API intentionally hides native exception bodies.
                # Retain a diagnostic only inside this synthetic proof fixture.
                rebuild_errors.append(traceback.format_exc())
                raise
        monkeypatch.setattr(knowledge, "rebuild_index", traced_rebuild)
        helpers = services.registry["helpers"]
        client = TestClient(app, headers={"x-renulus-token": "synthetic-recovery-session"})
        try:
            asyncio.run(helpers.startup.start())
            assert helpers.startup.status()["imports"]["embedding"]["ready"]
            # Bootstrap before importing Mem0's provider interfaces; this pins
            # import defaults to the synthetic profile and disables telemetry.
            from renulus.memory.engine import bootstrap
            bootstrap(services)
            from renulus.memory.providers import ApprovedLLM
            def no_inference(*args, **kwargs):
                attempted.append("mem0-inference")
                raise AssertionError("Manual notes and reindex must use infer=False")
            monkeypatch.setattr(ApprovedLLM, "generate_response", no_inference)
            services.registry["knowledge_worker"].start()
            yield client, services
        finally:
            services.registry["knowledge_worker"].stop(timeout=10)
            asyncio.run(services.registry["memory"].close())
            services.registry["knowledge"].index.close()
            client.close()
            helpers.startup.close()
        assert asset_snapshot() == before_assets
        # Full public manifest/hash validation detects same-size asset changes.
        assert helpers.embedding_config()["local_files_only"] is True
        assert helpers.docling_config()["device"] == "cpu"
        assert attempted == []

    return profile


def succeeded(response, code=200):
    assert response.status_code == code, response.text
    return response.json()


def wait_ready(client, document):
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        status = succeeded(client.get(f"/api/v1/library/documents/{document['document_id']}/import-status"))
        if status["status"] == "ready":
            return status
        assert status["status"] in ("queued", "processing"), status
        time.sleep(0.1)
    pytest.fail("Synthetic CPU text ingestion exceeded 120 seconds")


def library_search(client, query, topic_id):
    return succeeded(client.post("/api/v1/library/retrieve", json={
        "query": query, "topic_id": topic_id, "scope": {"kind": "study"}}))


def memory_search(client, query):
    return succeeded(client.post("/api/v1/memory/search", json={
        "query": query, "scope": {"kind": "study"}}))


def restore_zip(client, archive):
    preview = succeeded(client.post("/api/v1/data/backup/preview", content=archive,
        headers={"content-type": "application/zip"}))
    result = succeeded(client.post("/api/v1/data/backup/restore", json={
        "preview_token": preview["preview_token"], "confirmed_exported_at": preview["exported_at"],
        "acknowledge_deletion_limits": True}))
    # TestClient waits for actual background rebuild tasks to finish.
    report = succeeded(client.get("/api/v1/data/recovery"))
    assert report["rebuild"]["status"] == "complete", (
        json.dumps(report["rebuild"], indent=2) + "\n" +
        "\n".join(client.app.state.services.registry["recovery_proof_errors"]))
    assert report["rebuild"]["modules"]["knowledge"]["rebuilt_unit"] == "passages"
    assert report["rebuild"]["modules"]["memory"]["rebuilt_unit"] == "records"
    return result, report


def test_actual_cpu_library_and_manual_note_zip_restore_retrieve_edit_delete(offline_profiles, tmp_path):
    inputs = tmp_path / "explicit-synthetic-inputs"
    inputs.mkdir()
    contents = {
        "ckd.txt": "SYNTHETIC CKD study: albuminuria and eGFR trajectories are distinct learning concepts.\n\nReview chronic kidney disease progression mechanisms.",
        "dialysis.md": "SYNTHETIC dialysis study: fistula access flow and stenosis surveillance.\n\nCompare dialysis access mechanisms during educational review.",
    }
    note_text = "SYNTHETIC learner preference: revisit transplant rejection mechanisms during study."
    documents, source_locators = {}, {}
    with offline_profiles("source-profile") as (client, services):
        for filename, text in contents.items():
            path = inputs / filename
            path.write_text(text, encoding="utf-8")
            topic = "ckd" if filename == "ckd.txt" else "dialysis"
            options = {"title": "Synthetic " + topic + " source", "scope": {"kind": "personal-library"},
                "metadata": {"source_id": "R02", "edition": "Synthetic recovery 1", "topic_ids": [topic]},
                "idempotency_key": "recovery-" + topic}
            documents[topic] = wait_ready(client, succeeded(client.post("/api/v1/library/import/file",
                content=path.read_bytes(), headers={"x-renulus-filename": filename,
                "x-renulus-import-options": json.dumps(options)}), 202))
            found = library_search(client, "albuminuria eGFR" if topic == "ckd" else "fistula stenosis", topic)
            assert any(hit["document_revision"] == documents[topic]["revision_id"] for hit in found["passages"]), found
            citation = succeeded(client.get(f"/api/v1/library/revisions/{documents[topic]['revision_id']}/citation"))
            assert citation["locators"] and all(location["page"] is None and location["char_span"] for location in citation["locators"])
            source_locators[topic] = citation["locators"]
        note = succeeded(client.post("/api/v1/memory/facts", json={"text": note_text,
            "kind": "preference", "topic_id": "transplant", "scope": {"kind": "study"},
            "idempotency_key": "synthetic-recovery-note"}), 201)
        assert succeeded(client.post("/api/v1/memory/reindex"))["count"] == 1
        assert memory_search(client, "transplant rejection learning preference")["records"][0]["id"] == note["id"]
        source_generation = services.registry["knowledge"].rebuild_index()["generation"]
        assert services.registry["knowledge_worker"].status()["running"]
        response = client.get("/api/v1/data/backup")
        assert response.status_code == 200, response.text
        archive = response.content
        with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
            bundle = json.loads(zipped.read("records.json"))
            assert len(zipped.namelist()) == 4  # Manifest, records and two actual originals.
            assert "knowledge_catalogue" not in bundle["records"]
            passage_count = len(bundle["records"]["knowledge_passages"])
            assert passage_count > 0
            assert not any(name.startswith("memory_index") for name in bundle["records"])
            assert all(row["key"] != "knowledge.index_generation" for row in bundle["records"]["preferences"])
            assert all(row["original_path"].startswith("library/knowledge/") for row in bundle["records"]["knowledge_revisions"])
        assert not list((services.paths.cache / "recovery/exports").iterdir())

    with offline_profiles("different-target-profile") as (client, services):
        result, report = restore_zip(client, archive)
        assert result["restored_originals"] == 2 and result["excluded_originals"] == 0
        assert report["rebuild"]["modules"]["knowledge"]["rebuilt_records"] == passage_count
        assert report["rebuild"]["modules"]["memory"]["rebuilt_records"] == 1
        knowledge, memory = services.registry["knowledge"], services.registry["memory"]
        assert knowledge.index.path.is_relative_to(services.paths.indexes)
        assert knowledge.index.path.name != source_generation
        assert knowledge.index._table.__class__.__module__.startswith("lancedb")
        assert knowledge.embedder._model.__class__.__module__.startswith("fastembed")
        assert memory._engine.path.is_relative_to(services.paths.indexes)
        assert memory._engine.memory.__class__.__module__ == "mem0.memory.main"
        assert memory._engine.memory.vector_store.client._client.__class__.__name__ == "QdrantLocal"
        assert memory._engine.memory.embedding_model.delegate.model.__class__.__module__.startswith("fastembed")
        assert memory._engine.memory.embedding_model.delegate.config["cpu_threads"] == 2
        assert memory._engine.memory.db.connection.execute("SELECT COUNT(*) FROM history").fetchone()[0] == 0
        for topic, document in documents.items():
            revision = document["revision_id"]
            found = library_search(client, "albuminuria eGFR" if topic == "ckd" else "fistula stenosis", topic)
            matching = [hit for hit in found["passages"] if hit["document_revision"] == revision]
            assert matching and matching[0]["rights"]["display"] is True
            citation = succeeded(client.get(f"/api/v1/library/revisions/{revision}/citation"))
            assert citation["locators"] == source_locators[topic]
            original = client.get(citation["original_url"])
            assert original.status_code == 200
            filename = "ckd.txt" if topic == "ckd" else "dialysis.md"
            assert original.content == (inputs / filename).read_bytes()
            row = services.db.fetch_one("SELECT * FROM knowledge_revisions WHERE id=?", (revision,))
            assert Path(row["original_path"]).is_relative_to(services.paths.library)
            assert row["sha256"] == hashlib.sha256(original.content).hexdigest()
            assert row["bytes"] == len(original.content)
        recalled = memory_search(client, "transplant rejection learning preference")
        assert recalled["records"][0]["text"] == note_text
        assert f"[{note['id']} r1]" in recalled["context"]
        edited_text = "SYNTHETIC corrected learner preference: revisit glomerular proteinuria mechanisms."
        edited = succeeded(client.patch(f"/api/v1/memory/facts/{note['id']}",
            json={"text": edited_text, "expected_revision": 1}))
        assert edited["revision"] == 2 and edited["purge_pending"] is False
        corrected = memory_search(client, "glomerular proteinuria learning preference")
        assert corrected["records"][0]["text"] == edited_text and note_text not in corrected["context"]
        assert f"[{note['id']} r2]" in corrected["context"]
        deleted_note = succeeded(client.delete(f"/api/v1/memory/facts/{note['id']}?expected_revision=2"))
        assert deleted_note["deleted"] and deleted_note["purge_pending"] is False
        removed = succeeded(client.delete(f"/api/v1/library/documents/{documents['ckd']['document_id']}"))
        assert removed["status"] == "deleted" and removed["cleanup_pending"] is False
        assert client.get(f"/api/v1/library/revisions/{documents['ckd']['revision_id']}/citation").status_code == 404
        assert not list((services.paths.library / "knowledge" / documents["ckd"]["document_id"]).rglob("original.*"))
        replayed, report = restore_zip(client, archive)
        assert replayed["restored_originals"] == 1 and replayed["excluded_originals"] == 1
        assert report["rebuild"]["modules"]["memory"]["rebuilt_records"] == 0
        assert memory_search(client, "transplant glomerular proteinuria")["records"] == []
        assert library_search(client, "albuminuria eGFR", "ckd")["passages"] == []
        assert library_search(client, "fistula stenosis", "dialysis")["passages"]
        assert client.get(f"/api/v1/library/revisions/{documents['ckd']['revision_id']}/original").status_code == 404
        assert services.db.is_deleted("memory_fact", note["id"])
        assert services.db.is_deleted("knowledge-document", documents["ckd"]["document_id"])
    for filename, text in contents.items():
        assert (inputs / filename).read_text(encoding="utf-8") == text
