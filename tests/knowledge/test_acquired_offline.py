"""Opt-in acquired proof: explicit entry IDs, isolated prepared profile, no network."""
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import socket
import time

from fastapi.testclient import TestClient
import pytest

from renulus.knowledge.acquired import EVIDENCE_PREFIX, SELECTION, SELECTION_REVIEW, asset_id, collection_path, version_identity
from renulus.knowledge.collection import MANIFEST
from renulus.server import create_app
from renulus.storage.database import utc_now


def test_actual_selected_acquired_jats_through_offline_api_worker(monkeypatch):
    profile = os.environ.get("RENULUS_ACQUIRED_PROOF_PROFILE")
    ids = os.environ.get("RENULUS_ACQUIRED_PROOF_IDS")
    root = os.environ.get("RENULUS_ACQUIRED_PROOF_COLLECTION")
    if not profile or not ids or not root:
        pytest.skip("Requires an explicit prepared isolated profile, collection and selected entry IDs")
    entry_ids = json.loads(ids)
    assert isinstance(entry_ids, list) and 1 <= len(entry_ids) <= 10
    root = Path(root).resolve()
    manifest = collection_path(root, MANIFEST)
    identities, candidates = set(), []
    with manifest.open(encoding="utf-8-sig") as stream:
        for line in stream:
            item = json.loads(line)
            if item.get("source_id") == "L02" and item.get("artifact_type") == "fulltext-jats":
                relative = collection_path(root, item["local_path"], must_exist=False).relative_to(root).as_posix()
                if asset_id("L02", relative) in entry_ids:
                    identities.add(version_identity(item))
                    candidates.append(root / relative)
    allowed = {manifest.resolve(), (root / SELECTION).resolve(), (root / SELECTION_REVIEW).resolve(),
        *(path.resolve() for path in candidates)}
    with manifest.open(encoding="utf-8-sig") as stream:
        for line in stream:
            item = json.loads(line)
            if item.get("source_id") == "L02" and item.get("artifact_type") == "article-version-metadata" and version_identity(item) in identities:
                allowed.add(collection_path(root, item["local_path"]).resolve())
    original_open, opened = Path.open, set()
    def selected_files_only(path, *args, **kwargs):
        if path.absolute().is_relative_to(root):
            resolved = path.resolve()
            assert resolved in allowed, "Only selected JATS, matched metadata and the manifest may be opened"
            opened.add(resolved)
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", selected_files_only)
    for name in ("connect", "connect_ex"):
        original = getattr(socket.socket, name)
        def guard(sock, address, original=original):
            if isinstance(address, tuple) and ipaddress.ip_address(address[0]).is_loopback:
                return original(sock, address)
            raise AssertionError("External network forbidden throughout the actual acquired proof")
        monkeypatch.setattr(socket.socket, name, guard)
    app = create_app(profile)
    services = app.state.services
    collection, repository = services.registry["knowledge_catalogue"], services.registry["knowledge"]
    collection.root = root
    started = time.monotonic()
    with TestClient(app) as api:
        registered = api.post("/api/v1/library/collection/catalogue?source_id=L02")
        assert registered.status_code == 200, "Actual metadata catalogue registration failed"
        capabilities = repository.capabilities()
        assert capabilities["text_import"], "Actual text helpers are not provisioned"
        response = api.post("/api/v1/library/collection/import", json={"entry_ids": entry_ids, "scope": {"kind": "personal-library"}})
        assert response.status_code == 202
        selected = response.json()["results"]
        queued = [r for r in selected if "job" in r]
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            states = [repository.get_job(r["job"]["id"])["state"] for r in queued]
            if all(state in ("ready", "failed", "cancelled") for state in states):
                break
            time.sleep(0.25)
        summaries = []
        for result in selected:
            summary = {"entry_id": result["entry_id"], "status": result["status"]}
            if "job" not in result:
                summary["code"] = result.get("code")
                summaries.append(summary)
                continue
            revision = services.db.fetch_one("SELECT * FROM knowledge_revisions WHERE id=?", (result["revision_id"],))
            metadata = json.loads(revision["metadata_json"])
            evidence = json.loads(next(n[len(EVIDENCE_PREFIX):] for n in metadata["notes"] if n.startswith(EVIDENCE_PREFIX)))
            summary.update({"article_version": metadata["edition"], "status": repository.get_job(result["job"]["id"])["state"],
                "topic_ids": metadata["topic_ids"], "licence": evidence["licence"], "licence_url": evidence["licence_url"],
                "original_sha256": evidence["original_sha256"], "metadata_sha256": evidence["metadata_sha256"],
                "derivative_sha256": evidence["derivative_sha256"], "original_bytes": evidence["original_bytes"],
                "derivative_bytes": evidence["derivative_bytes"], "passages": services.db.fetch_one("SELECT COUNT(*) AS n FROM knowledge_passages WHERE revision_id=?", (result["revision_id"],))["n"]})
            with collection_path(collection.root, evidence["original_path"]).open("rb") as stream:
                assert hashlib.file_digest(stream, "sha256").hexdigest() == evidence["original_sha256"], "External original changed"
            with collection_path(collection.root, evidence["metadata_path"]).open("rb") as stream:
                assert hashlib.file_digest(stream, "sha256").hexdigest() == evidence["metadata_sha256"], "External metadata changed"
            assert revision["sha256"] == evidence["derivative_sha256"]
            assert metadata["publication_status"] == "unknown" and not metadata["latest_final_verified"] and not metadata["content_reviewed"]
            summaries.append(summary)
        with collection_path(collection.root, MANIFEST).open("rb") as stream:
            manifest_hash = hashlib.file_digest(stream, "sha256").hexdigest()
        proof = {"checked_at": utc_now(), "manifest_sha256": manifest_hash, "catalogued": registered.json()["catalogued"],
            "catalogue_errors": len(registered.json()["errors"]), "selected": len(entry_ids),
            "ready": sum(s["status"] == "ready" for s in summaries), "elapsed_seconds": round(time.monotonic() - started, 2),
            "network": "external Python sockets denied; helper offline flags enabled",
            "collection_files_opened": sorted(p.relative_to(root).as_posix() for p in opened), "entries": summaries}
        output = Path(profile) / "acquired-proof.json"
        output.write_text(json.dumps(proof, indent=2), encoding="utf-8")
        # Actual retrieval is verified without putting any acquired passage text
        # in the evidence file or assertion output.
        hits = api.post("/api/v1/library/retrieve", json={"query": "kidney", "scope": {"kind": "study"}, "limit": 50}).json()["passages"]
        proof["retrieved_passages"] = len(hits)
        output.write_text(json.dumps(proof, indent=2), encoding="utf-8")
        assert proof["ready"] >= 2 and len(hits) > 0, "See hash/count-only acquired-proof.json for unavailable selections"
        assert not api.post("/api/v1/library/retrieve", json={"query": "kidney", "scope": {"kind": "study"}, "current_only": True}).json()["passages"]
