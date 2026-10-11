"""Closed candidate inspection sees the actual final native tool registry."""
import hashlib
import json
import os
from pathlib import Path

from renulus.runtime.harness_activation import HarnessProfileActivation
from renulus.runtime.harness_process import HarnessProcessConfig, ManagedHarnessProcess
from renulus.server import create_app


async def test_native_candidate_inspects_final_registry_without_opening_generation(tmp_path):
    root = tmp_path / "closed-candidate"
    services = create_app(root).state.services
    config = HarnessProcessConfig(node_executable=Path(os.environ["RENULUS_HARNESS_NODE"]),
        host_entry=Path(__file__).resolve().parents[2] / "packages/harness/test/fixtures/configuration-probe-host.mjs",
        profile_root=root, profile_id="synthetic-candidate", store_id="synthetic-runtime",
        domain_store_id="synthetic-domain", domain_path="state/renulus.sqlite3")
    process = ManagedHarnessProcess()
    try:
        await process.start(config)
        inspected = await process.request("host.inspect", {}, "closed-health", "1", 10)
        if inspected["outcome"] != "committed_reference":
            diagnostic = await process.request("host.status", {}, "probe-diagnostics", "1", 5)
            raise AssertionError(json.dumps(diagnostic["result"], indent=2))
        health = inspected["result"]
        assert health["state"] == "policy_blocked"
        assert health["generation_open"] is False and health["recovery_open"] is False
        assert health["package_acquisition_open"] is False and health["mcp_startup_open"] is False
        assert [item["name"] for item in health["registry"]] == ["renulus_library_citation", "renulus_library_retrieve"]
        encoded = json.dumps(health["registry"], sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        assert health["registry_hash"] == hashlib.sha256(encoded.encode()).hexdigest()
        status = await process.request("host.status", {}, "closed-health", "1", 5)
        assert status["result"]["modelCalls"] == 0
        assert status["result"]["activeSessionIds"] == []
        rejected = await process.request("session.create", {"title": "Cannot admit candidate work"}, "denied", "1", 5)
        assert rejected["outcome"] == "rejected_before_admission"
    finally:
        assert (await process.close(10))["state"] == "closed"
        services.get("helpers").startup.close()


async def test_fresh_gated_owner_inspects_active_stores_without_admitting_work(tmp_path):
    root = tmp_path / "active-gated-registry"
    services = create_app(root).state.services
    config = HarnessProcessConfig(node_executable=Path(os.environ["RENULUS_HARNESS_NODE"]),
        host_entry=Path(__file__).resolve().parents[2] / "packages/harness/test/fixtures/configuration-probe-host.mjs",
        profile_root=root, profile_id="synthetic-profile", store_id="synthetic-runtime",
        domain_store_id="synthetic-domain", domain_path="state/renulus.sqlite3")
    process = ManagedHarnessProcess()
    try:
        await process.start(config)
        await HarnessProfileActivation(services.db, process, config).activate()
        first = await process.request("host.inspect", {}, "gated-registry", "1", 10)
        assert first["outcome"] == "committed_reference"
        assert first["result"]["live_store_writer"] is True
        assert (await process.close(10))["state"] == "closed"

        process = ManagedHarnessProcess()
        await process.start(config)
        observed = await process.request("host.inspect", {}, "fresh-gated-registry", "1", 10)
        assert observed["outcome"] == "committed_reference"
        health = observed["result"]
        assert health["state"] == "policy_blocked"
        assert health["live_store_writer"] is True
        assert health["registry_hash"] == first["result"]["registry_hash"]
        assert all(health[key] is False for key in ("generation_open", "recovery_open",
            "package_acquisition_open", "mcp_startup_open"))
        assert [item["name"] for item in health["registry"]] == [
            "renulus_library_citation", "renulus_library_retrieve"]
        denied = await process.request("session.create", {"title": "Gated generation"},
            "still-gated", "1", 5)
        assert denied["outcome"] == "rejected_before_admission"
        status = (await process.request("host.status", {}, "registry-status", "1", 5))["result"]
        assert status["modelCalls"] == 0
        assert status["activeSessionIds"] == []
        assert status["heldSessionIds"] == []
    finally:
        assert (await process.close(10))["state"] == "closed"
        services.get("helpers").startup.close()
