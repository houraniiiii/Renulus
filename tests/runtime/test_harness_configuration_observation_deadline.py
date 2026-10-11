"""Actual closed SDK candidate; delayed public release observation is synthetic."""
import asyncio
import os
from pathlib import Path

import pytest

from renulus.contracts import ApiError
from renulus.runtime.harness_configuration import Candidate, ConfigurationSpec, ConnectionReference
from renulus.runtime.harness_configuration_lifecycle import ManagedConfigurationLifecycle
from renulus.runtime.harness_learning import HarnessLearningOwner
from renulus.runtime.harness_process import HarnessProcessConfig, ManagedHarnessProcess
from renulus.server import create_app


async def test_candidate_release_observation_obeys_the_total_request_budget(tmp_path, monkeypatch):
    services = create_app(tmp_path / "live").state.services
    config = HarnessProcessConfig(node_executable=Path(os.environ["RENULUS_HARNESS_NODE"]),
        host_entry=Path(__file__).resolve().parents[2] / "packages/harness/test/fixtures/configuration-probe-host.mjs",
        profile_root=services.paths.root, profile_id="synthetic-profile", store_id="synthetic-runtime",
        domain_store_id="synthetic-domain", domain_path="state/renulus.sqlite3")
    owner = HarnessLearningOwner(services, config, configuration_id="a" * 64)
    lifecycle = ManagedConfigurationLifecycle(owner, candidate_root=tmp_path / "candidates",
        attempt_timeout=2)
    entered, release, finalized = asyncio.Event(), asyncio.Event(), asyncio.Event()
    publications = []
    original = ManagedHarnessProcess.release_observation

    async def observed_release(process, request_id):
        async def owned():
            try:
                entered.set()
                await release.wait()
                return await original(process, request_id)
            finally:
                finalized.set()
        task = asyncio.create_task(owned())
        publications.append(task)
        return await asyncio.shield(task)  # Match the public process port's retained ownership.

    monkeypatch.setattr(ManagedHarnessProcess, "release_observation", observed_release)
    spec = ConfigurationSpec(connection=ConnectionReference(provider="opencode-go",
        credential_reference="synthetic-reference", credential_revision=0), registry_hash="b" * 64)
    inspection = asyncio.create_task(lifecycle.inspect_candidate(Candidate("a" * 64, spec, 0)))
    try:
        await asyncio.wait_for(entered.wait(), 20)
        with pytest.raises(ApiError) as failed:
            await asyncio.wait_for(asyncio.shield(inspection), 4)
        assert failed.value.code == "harness_configuration_lifecycle_failed"
        assert failed.value.status == 503 and failed.value.retryable is True
        assert not finalized.is_set() and not publications[0].done()
    finally:
        release.set()
        await asyncio.gather(inspection, *publications, return_exceptions=True)
        await lifecycle.close()
        await owner.close()
        services.get("helpers").startup.close()
    assert finalized.is_set()
