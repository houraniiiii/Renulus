# SPDX-License-Identifier: MIT
"""Actual SDK/store activation over the authenticated owned IPC seam."""
import asyncio
import os
from pathlib import Path

import pytest

from renulus.runtime.harness_process import HarnessProcessConfig, ManagedHarnessProcess
from renulus.storage import Database

REPO = Path(__file__).resolve().parents[2]
NODE = Path(os.environ.get("RENULUS_HARNESS_NODE", ""))
pytestmark = pytest.mark.skipif(
    not os.environ.get("RENULUS_HARNESS_NODE") or not NODE.is_file(),
    reason="Requires the pinned managed Node 26.4.0 and source-built cohort.")


async def test_actual_stores_activate_and_reopen_before_any_model_dispatch(tmp_path):
    from renulus.runtime.harness_activation import HarnessProfileActivation
    config = HarnessProcessConfig(node_executable=NODE,
        host_entry=REPO / "packages/harness/test/fixtures/scripted-host.mjs",
        profile_root=tmp_path / "profile", profile_id="synthetic-profile",
        store_id="synthetic-runtime", domain_store_id="synthetic-domain",
        domain_path="domain/renulus.sqlite3", start_timeout=30, max_inflight=1)
    db = Database(config.profile_root / config.domain_path)
    process = ManagedHarnessProcess()
    try:
        await process.start(config)
        owner = HarnessProfileActivation(db, process, config)
        manifest = await owner.activate()
        assert manifest.state == "active"
        assert owner.status()["state"] == "active"
        assert (await process.request("host.status", {}, "status-1", "1", 5))["result"]["modelCalls"] == 0
        assert await process.close(15) == {"state": "closed", "outcome": "cancelled_settled"}
        process = ManagedHarnessProcess()
        await process.start(config)
        reopened = await HarnessProfileActivation(db, process, config).activate()
        assert reopened == manifest
        assert (await process.request("host.status", {}, "status-2", "1", 5))["result"]["modelCalls"] == 0
    finally:
        assert await process.close(15) == {"state": "closed", "outcome": "cancelled_settled"}
