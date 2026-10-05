# SPDX-License-Identifier: MIT
"""Developer delivery uses the guarded API and never replaces an existing profile."""
import asyncio
from contextlib import contextmanager
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import zipfile

from fastapi.testclient import TestClient
import pytest
from starlette.responses import Response
import uvicorn

from renulus import server

from .test_content_release_compatibility import learner_records, assert_learner_records
from .test_offline_engine_round_trip import offline_profiles, succeeded, wait_ready


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/prepare_delivery_profile.py"


def delivery_tool():
    spec = importlib.util.spec_from_file_location("prepare_delivery_profile", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextmanager
def loopback_proxy(app):
    """A real HTTP source with the app's proxy-injected synthetic session token."""
    async def proxy(scope, receive, send):
        scope = {**scope, "headers": [*scope["headers"],
            (b"x-renulus-token", b"synthetic-recovery-session")]}
        await app(scope, receive, send)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    url = f"http://127.0.0.1:{listener.getsockname()[1]}"
    running = uvicorn.Server(uvicorn.Config(proxy, lifespan="off", access_log=False, log_config=None))
    thread = threading.Thread(target=lambda: running.run(sockets=[listener]), daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 15
        while not running.started:
            assert thread.is_alive() and time.monotonic() < deadline
            time.sleep(0.02)
        yield url
    finally:
        running.should_exit = True
        thread.join(timeout=15)
        listener.close()
        assert not thread.is_alive()


def test_existing_profile_is_refused_before_network_or_helper_access(tmp_path):
    target = tmp_path / "existing"
    target.mkdir()
    sentinel = target / "owner-state.txt"
    sentinel.write_text("OWNER STATE MUST SURVIVE", encoding="utf-8")
    result = subprocess.run([sys.executable, "-B", str(SCRIPT),
        "--source-url", "http://127.0.0.1:1", "--output-profile", str(target),
        "--helper-root", str(tmp_path / "not-installed"), "--source-root", str(ROOT)],
        capture_output=True, text=True, timeout=20)
    assert result.returncode != 0
    assert "already exists" in result.stderr
    assert sentinel.read_text(encoding="utf-8") == "OWNER STATE MUST SURVIVE"
    assert list(target.iterdir()) == [sentinel]


def test_metadata_report_exposes_source_capacity_refusal_without_creating_a_profile(tmp_path):
    tool = delivery_tool()
    refused = Response(json.dumps({"error": {"code": "backup_limit",
        "message": "synthetic canonical capacity exceeded"}}), status_code=413, media_type="application/json")
    with loopback_proxy(refused) as url:
        report = tool.report_source_snapshot(source_url=url, source_root=ROOT)
    assert report["status"] == "blocked" and report["http_status"] == 413
    assert report["error_code"] == "backup_limit"
    assert report["limits"]["json_bytes"] == 16_777_216
    assert report["limits"]["archive_bytes"] == 301_989_888
    assert report["canonical_record_limit"] == 100_000
    assert report["zip_bytes"] is None
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("format_version", [1, 2])
def test_guarded_http_library_delivery_retains_originals_journal_and_queue_without_learner_history(offline_profiles, tmp_path, format_version):
    tool = delivery_tool()
    payloads = {
        "ready.txt": b"SYNTHETIC approved CKD Library source: albuminuria and eGFR learning concepts.",
        "queued.md": b"# SYNTHETIC approved dialysis Library source\nFistula flow and stenosis mechanisms.",
    }
    with offline_profiles("s") as (client, services):
        helper_root = services.paths.helpers
        rights = {"display": True, "cache": True, "index": True, "embedding": True,
            "model_input": True, "derivation": True, "licence": "CC BY 4.0",
            "permission_reference": "Synthetic fixture explicitly permits these operations",
            "attribution": "Synthetic Author; synthetic fixture; CC BY 4.0"}
        def add(name, *, reserved=False):
            options = {"title": "SYNTHETIC approved delivery " + name,
                "scope": {"kind": "personal-library"},
                "metadata": {"source_id": "R02", "edition": "Synthetic delivery edition", "topic_ids": ["ckd"]},
                "rights": rights, "reserved": reserved, "idempotency_key": "delivery-" + name}
            return succeeded(client.post("/api/v1/library/import/file", content=payloads.get(name, b"SYNTHETIC reserved source must be omitted"),
                headers={"x-renulus-filename": name, "x-renulus-import-options": json.dumps(options)}), 202)
        ready = wait_ready(client, add("ready.txt"))
        services.registry["knowledge_worker"].stop(timeout=10)
        queued = add("queued.md")
        reserved = add("reserved.txt", reserved=True)
        removed = add("removed.txt")
        succeeded(client.delete(f"/api/v1/library/documents/{removed['document_id']}"))
        # Preserve deployed passage/job identity prefixes as well as the older
        # compatible fixtures; unrelated learner tombstones stay excluded.
        services.db.mark_deleted("knowledge-passage", "passage_deleted_synthetic")
        services.db.mark_deleted("knowledge-job", "ingest_deleted_synthetic")
        services.db.mark_deleted("memory-fact", "mem_deleted_synthetic")
        # An acquisition receipt is discovery metadata, not an imported Library
        # original. It must never cause the tool to open/copy its external XML.
        from renulus.knowledge.collection import MANIFEST
        collection_root = services.paths.root.parent / "acq"
        external = collection_root / "unimported.xml"
        external.parent.mkdir()
        external.write_bytes(b"SYNTHETIC DO_NOT_DELIVER_DISCOVERY_ORIGINAL")
        receipt = {"source_id": "L02", "title": "Synthetic discovery receipt",
            "local_path": "unimported.xml", "artifact_type": "fulltext-jats",
            "sha256": hashlib.sha256(external.read_bytes()).hexdigest(), "bytes": external.stat().st_size}
        acquisition_manifest = collection_root / MANIFEST
        acquisition_manifest.parent.mkdir(parents=True)
        acquisition_manifest.write_text(json.dumps(receipt) + "\n", encoding="utf-8")
        services.registry["knowledge_catalogue"].root = collection_root
        assert succeeded(client.post("/api/v1/library/collection/catalogue"))["catalogued"] == 1
        event = {"contract_version": 1, "event_id": "synthetic-delivery-source-event", "source_id": "R02",
            "identity": {"canonical_url": "https://example.invalid/synthetic-delivery"},
            "changes": {"content_reviewed": False}, "scope": {}}
        services.registry["knowledge"].update_source_status(event)
        excluded = learner_records(client, services.registry["content"], "DO_NOT_DELIVER_LEARNER")
        assert succeeded(client.post("/api/v1/memory/reindex"))["count"] == 1
        services.db.execute("INSERT INTO preferences VALUES(?,?,?)",
            ("learn.teaching_style", "DO_NOT_DELIVER_CONFIGURATION", "2026-10-04T20:00:00+00:00"))
        schedule = succeeded(client.put("/api/v1/updates/schedule", json={"enabled": True,
            "cadence_hours": 48, "selection": [{"kind": "source", "id": "K01"}]}))
        assert schedule["enabled"] is True
        native = services.paths.state / "synthetic-native-state.bin"
        native.write_bytes(b"DO_NOT_DELIVER_NATIVE_OR_CREDENTIAL_STATE")
        before = succeeded(client.get("/api/v1/data/export"))["records"]
        locators = succeeded(client.get(f"/api/v1/library/revisions/{ready['revision_id']}/citation"))["locators"]
        output = services.paths.root.parent / "d"
        assert not output.exists()
        # Validate every source member before applying the delivery filter, even
        # when the tampered original belongs to a reserved document to be dropped.
        source_backup = client.get("/api/v1/data/backup?format_version=" + str(format_version))
        assert source_backup.status_code == 200
        damaged = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(source_backup.content)) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            reserved_path = next(row["path"] for row in manifest["originals"]
                if row["document_id"] == reserved["document_id"])
            with zipfile.ZipFile(damaged, "w", zipfile.ZIP_DEFLATED) as forged:
                for name in archive.namelist():
                    body = archive.read(name)
                    if name == reserved_path:
                        body = bytes([body[0] ^ 1]) + body[1:]
                    forged.writestr(name, body)
        bad_target = output.with_name("bad")
        with loopback_proxy(Response(damaged.getvalue(), media_type="application/zip")) as url:
            with pytest.raises(tool.DeliveryError, match="backup_integrity"):
                tool.prepare_delivery_profile(source_url=url, output_profile=bad_target,
                    helper_root=helper_root, source_root=ROOT, format_version=format_version)
        assert not bad_target.exists()
        assert not list(output.parent.glob(".rnl-dp-*"))
        with loopback_proxy(client.app) as url:
            capacity = tool.report_source_snapshot(source_url=url, source_root=ROOT)
            assert capacity["status"] == "within_canonical_bounds"
            assert capacity["tables"]["knowledge_documents"] == 4
            assert capacity["tables"]["memory_facts"] == 1
            assert capacity["candidate_tables"]["knowledge_documents"] == 2
            assert capacity["candidate_library_revision_bytes"] == sum(map(len, payloads.values()))
            assert capacity["discovery_omission"] == 1 and capacity["catalogue_present"] is False
            assert capacity["originals_verified"] is False and capacity["zip_bytes"] is None
            report = tool.prepare_delivery_profile(source_url=url, output_profile=output,
                helper_root=helper_root, source_root=ROOT, format_version=format_version)
        assert report["status"] == "ready"
        assert report["format_version"] == format_version
        assert report["originals"] == 2 and report["verified_originals"] == 2
        assert report["original_bytes"] == sum(map(len, payloads.values()))
        assert report["rebuild"]["status"] == "complete"
        assert report["rebuild"]["modules"]["knowledge"]["rebuilt_records"] > 0
        assert report["rebuild"]["modules"]["memory"]["rebuilt_records"] == 0
        assert report["queued_jobs"] == 1
        assert succeeded(client.get("/api/v1/data/export"))["records"] == before
        assert_learner_records(client, excluded)
        assert native.read_bytes() == b"DO_NOT_DELIVER_NATIVE_OR_CREDENTIAL_STATE"
        assert external.read_bytes() == b"SYNTHETIC DO_NOT_DELIVER_DISCOVERY_ORIGINAL"
        assert json.loads(acquisition_manifest.read_text(encoding="utf-8")) == receipt

        target_app = server.create_app(output, source_root=ROOT)
        target = target_app.state.services
        target.registry["helpers"].startup.configure()
        # Do not enter the lifespan: queued imports belong to native app startup.
        delivered = TestClient(target_app)
        try:
            assert succeeded(delivered.get("/api/v1/content/manifest"))["version"] == "1.1.0"
            documents = succeeded(delivered.get("/api/v1/library/documents"))["documents"]
            assert {row["id"] for row in documents} == {ready["document_id"], queued["document_id"]}
            assert delivered.get(f"/api/v1/library/documents/{reserved['document_id']}").status_code == 404
            assert delivered.get(f"/api/v1/library/documents/{removed['document_id']}").status_code == 404
            assert succeeded(delivered.get(f"/api/v1/library/documents/{queued['document_id']}/import-status"))["status"] == "queued"
            found = succeeded(delivered.post("/api/v1/library/retrieve", json={
                "query": "albuminuria eGFR", "topic_id": "ckd", "scope": {"kind": "study"}}))
            assert any(hit["document_revision"] == ready["revision_id"] for hit in found["passages"])
            for name, imported in (("ready.txt", ready), ("queued.md", queued)):
                revision = imported["revision_id"]
                row = target.db.fetch_one("SELECT * FROM knowledge_revisions WHERE id=?", (revision,))
                assert Path(row["original_path"]).is_relative_to(output / "library")
                assert Path(row["original_path"]).read_bytes() == payloads[name], name
                assert row["bytes"] == len(payloads[name]), name
                assert row["sha256"] == hashlib.sha256(payloads[name]).hexdigest()
                assert json.loads(row["rights_json"])["attribution"] == rights["attribution"]
            original = delivered.get(f"/api/v1/library/revisions/{ready['revision_id']}/original")
            assert original.status_code == 200 and original.content == payloads["ready.txt"]
            # The viewer intentionally serves ready revisions. The queued
            # original is proved above without claiming its ingestion job.
            assert delivered.get(f"/api/v1/library/revisions/{queued['revision_id']}/original").status_code == 404
            assert succeeded(delivered.get(f"/api/v1/library/revisions/{ready['revision_id']}/citation"))["locators"] == locators
            assert succeeded(delivered.get("/api/v1/memory/facts"))["records"] == []
            assert succeeded(delivered.get("/api/v1/updates/schedule"))["enabled"] is False
            for table in ("learn_threads", "learn_messages", "case_sessions", "assessment_sessions",
                    "assessment_attempts", "memory_facts", "memory_history", "memory_jobs",
                    "learning_evidence", "knowledge_catalogue", "retrieval_imports",
                    "study_activities", "update_entries", "update_schedule_jobs", "update_schedule_runs"):
                assert target.db.fetch_one(f'SELECT COUNT(*) AS n FROM "{table}"')["n"] == 0, table
            assert target.db.fetch_all("SELECT * FROM knowledge_source_status_events") == before["knowledge_source_status_events"]
            assert target.db.fetch_all("SELECT * FROM deletion_ledger") == [
                row for row in before["deletion_ledger"] if tool.delivery_tombstone(row)]
            delivered_tombstones = {(row["entity_type"], row["entity_id"])
                for row in target.db.fetch_all("SELECT * FROM deletion_ledger")}
            assert ("knowledge-passage", "passage_deleted_synthetic") in delivered_tombstones
            assert ("knowledge-job", "ingest_deleted_synthetic") in delivered_tombstones
            assert ("memory-fact", "mem_deleted_synthetic") not in delivered_tombstones
            assert not (output / "state/synthetic-native-state.bin").exists()
            assert not (output / "state/runtime/connections.dpapi").exists()
            assert not list((output / "helpers").rglob("*"))
            assert not list(output.rglob("unimported.xml"))
            assert not list(output.rglob("acquisition-manifest.jsonl"))
        finally:
            delivered.close()
            target.registry["knowledge"].index.close()
            asyncio.run(target.registry["memory"].close())
            target.registry["helpers"].startup.close()
