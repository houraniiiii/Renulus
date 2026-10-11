"""Actual native restart and registry; connection policy is synthetic."""
from dataclasses import replace
import asyncio
import os
from pathlib import Path

import pytest

from renulus.contracts import ApiError
from renulus.learn.conversation_models import NewConversation, Send
from renulus.runtime.harness_configuration import (CandidateHealth,
    ConfigurationAuthority, ConfigurationSpec, ConnectionReference, RestartBoundary, RolePolicy)
from renulus.runtime.harness_configuration_controller import HarnessConfigurationController
from renulus.runtime.harness_learning import HarnessLearningOwner
from renulus.runtime.harness_process import HarnessProcessConfig, ManagedHarnessProcess
from renulus.runtime.harness_domain import DomainGrant
from renulus.server import create_app


class SyntheticConnection:
    def __init__(self, connection):
        self.connection = connection

    def require_configuration_connection(self, connection):
        assert connection == self.connection

    def connections(self):
        return {"selected_provider": "opencode-go", "connections": [{
            "provider": "opencode-go", "allowed_models": ["mimo-v2.6-pro"]}]}


async def test_bounded_stop_retains_the_actual_domain_finalizer_until_close(tmp_path):
    from renulus.runtime.harness_configuration_lifecycle import ManagedConfigurationLifecycle

    services = create_app(tmp_path / "live").state.services
    config = HarnessProcessConfig(node_executable=Path(os.environ["RENULUS_HARNESS_NODE"]),
        host_entry=Path(__file__).resolve().parents[2] / "packages/harness/test/fixtures/domain-host.mjs",
        profile_root=services.paths.root, profile_id="synthetic-profile", store_id="synthetic-runtime",
        domain_store_id="synthetic-domain", domain_path="state/renulus.sqlite3")
    entered, release, finalized = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def authorize(request):
        async def handler(current, cancellation):
            entered.set()
            try:
                await release.wait()
                cancellation.check_current()
                return {'synthetic': True}
            finally:
                finalized.set()
        return DomainGrant(request.binding, handler, lambda: True)

    owner = HarnessLearningOwner(services, config, configuration_id='a' * 64)
    assert (await owner.process.settlement(0))['state'] == 'settled'
    seal = owner.seal_new_runs(expected_effective='a' * 64)
    owner.replace_process(ManagedHarnessProcess(domain_authority=authorize), configuration_id='a' * 64, seal=seal)
    lifecycle = ManagedConfigurationLifecycle(owner, candidate_root=tmp_path / 'candidates')
    stopping = closing = None
    try:
        await owner.process.start(config)
        await owner.process.request('session.get', {'session_id': 'native-session'}, 'learning-1', 'attempt-1', .01)
        await asyncio.wait_for(entered.wait(), 5)
        stopping = asyncio.create_task(lifecycle.stop_and_settle(seal))
        done, _ = await asyncio.wait({stopping}, timeout=5.3)
        assert done, 'A drain attempt must return a bounded blocked result.'
        with pytest.raises(ApiError) as blocked:
            await stopping
        assert blocked.value.code == 'harness_configuration_settlement_pending'
        assert (await owner.process.settlement(0))['state'] == 'pending'
        assert not finalized.is_set()
        closing = asyncio.create_task(lifecycle.close())
        await asyncio.sleep(0)
        assert not closing.done()
        release.set()
        await asyncio.wait_for(closing, 5)
        assert finalized.is_set()
        assert (await owner.process.settlement(0))['state'] == 'settled'
    finally:
        release.set()
        if stopping is not None:
            await asyncio.gather(stopping, return_exceptions=True)
        if closing is not None:
            await asyncio.gather(closing, return_exceptions=True)
        await owner.close()
        services.get('helpers').startup.close()


async def test_restart_requires_an_actual_owned_root_lease(tmp_path):
    from renulus.runtime.harness_configuration_lifecycle import ManagedConfigurationLifecycle

    services = create_app(tmp_path / "live").state.services
    config = HarnessProcessConfig(node_executable=Path(os.environ["RENULUS_HARNESS_NODE"]),
        host_entry=Path(__file__).resolve().parents[2] / "packages/harness/test/fixtures/configuration-probe-host.mjs",
        profile_root=services.paths.root, profile_id="synthetic-profile", store_id="synthetic-runtime",
        domain_store_id="synthetic-domain", domain_path="state/renulus.sqlite3")
    owner = HarnessLearningOwner(services, config, configuration_id='a' * 64)
    lifecycle = ManagedConfigurationLifecycle(owner, candidate_root=tmp_path / "candidates")
    try:
        for missing in (None, object()):
            with pytest.raises(ApiError) as denied:
                await lifecycle.stop_and_settle(missing)
            assert denied.value.code == "activation_conflict"
        seal = await lifecycle.seal_new_runs(expected_effective='a' * 64)
        seal.release()
        with pytest.raises(ApiError) as released:
            await lifecycle.stop_and_settle(seal)
        assert released.value.code == "activation_conflict"
    finally:
        await owner.close()
        services.get("helpers").startup.close()


async def test_controller_restarts_the_real_idle_owner_after_isolated_registry_validation(tmp_path):
    from renulus.runtime.harness_configuration_lifecycle import ManagedConfigurationLifecycle

    services = create_app(tmp_path / "live").state.services
    config = HarnessProcessConfig(node_executable=Path(os.environ["RENULUS_HARNESS_NODE"]),
        host_entry=Path(__file__).resolve().parents[2] / "packages/harness/test/fixtures/configuration-probe-host.mjs",
        profile_root=services.paths.root, profile_id="synthetic-profile", store_id="synthetic-runtime",
        domain_store_id="synthetic-domain", domain_path="state/renulus.sqlite3")
    cold = ManagedHarnessProcess()
    try:
        await cold.start(replace(config, profile_root=tmp_path / "initial-registry",
            profile_id="synthetic-initial", store_id="synthetic-initial-runtime",
            domain_store_id="synthetic-initial-domain"))
        observed = (await cold.request("host.inspect", {}, "initial-registry", "1", 10))["result"]
    finally:
        assert (await cold.close(10))["state"] == "closed"
    assert observed["live_store_writer"] is False
    authority = ConfigurationAuthority(services.db)
    connection = ConnectionReference(provider="opencode-go", credential_reference="synthetic-reference",
        credential_revision=0)
    initial = authority.stage(ConfigurationSpec(connection=connection, registry_hash=observed["registry_hash"],
        capabilities=("text", "tools")))
    assert authority.validate(initial, lambda candidate: CandidateHealth(
        configuration_version=candidate.version, registry_hash=observed["registry_hash"],
        grant_epoch=candidate.grant_epoch))
    owner = HarnessLearningOwner(services, config, configuration_id=initial)
    owner.install()
    lifecycle = ManagedConfigurationLifecycle(owner, candidate_root=tmp_path / "candidates")
    # No live owner has started. The public transport proves that empty owner
    # is settled; this is explicit bootstrap fixture setup, not startup policy.
    assert (await owner.process.close(1))["state"] == "closed"
    authority.activate(initial, RestartBoundary(admission_closed=True, runtime_stopped=True,
        domain_settled=owner.process.domain_status()["active"] == 0), expected_effective=None)
    authority.open_admission(initial, registry_hash=observed["registry_hash"], grant_epoch=0)
    # A never-started transport was closed above, so start uses a fresh owner.
    owner.process = ManagedHarnessProcess(domain_authority=owner.authorize)
    owner.bridge.transport = owner.process
    from renulus.runtime.harness_activation import HarnessProfileActivation
    owner.activation = HarnessProfileActivation(services.db, owner.process, config)
    controller = HarnessConfigurationController(authority, SyntheticConnection(connection), lifecycle)
    try:
        await owner.start()
        old = owner.process
        old_status = await old.request("host.status", {}, "old-status", "1", 5)
        seal = await lifecycle.seal_new_runs(expected_effective=initial)
        chat = services.get("conversations").create(NewConversation())
        with pytest.raises(ApiError) as denied:
            services.get("conversations").streaming.begin("learning", chat["identity"]["id"],
                Send(expected_revision=chat["revision"], text="Synthetic CKD learning", request_id="sealed-root"))
        assert denied.value.code == "harness_configuration_busy"
        seal.release()
        staged = await controller.stage_roles((RolePolicy(purpose="explain", output_tokens=2048),))
        activated = await controller.activate(staged["version"])
        assert activated["effective"] == staged["version"]
        assert activated["admission_open"] is True
        assert activated["configuration"]["roles"][0]["output_tokens"] == 2048
        assert (await old.settlement(0))["state"] == "settled"
        assert owner.process is not old
        current = await owner.process.request("host.status", {}, "new-status", "1", 5)
        assert current["generation"] != old_status["generation"]
        assert current["result"]["configurationId"] == staged["version"]
        assert current["result"]["activeSessionIds"] == []
        assert current["result"]["modelCalls"] == 0
        assert owner.bridge.configuration_id == staged["version"]
    finally:
        await owner.close()
        services.get("helpers").startup.close()


async def test_reserved_saved_run_keeps_root_acquisition_failure_atomic(tmp_path):
    from renulus.runtime.harness_configuration_lifecycle import ManagedConfigurationLifecycle

    services = create_app(tmp_path / "live").state.services
    config = HarnessProcessConfig(node_executable=Path(os.environ["RENULUS_HARNESS_NODE"]),
        host_entry=Path(__file__).resolve().parents[2] / "packages/harness/test/fixtures/configuration-probe-host.mjs",
        profile_root=services.paths.root, profile_id="synthetic-profile", store_id="synthetic-runtime",
        domain_store_id="synthetic-domain", domain_path="state/renulus.sqlite3")
    owner = HarnessLearningOwner(services, config, configuration_id='a' * 64)
    owner.install()
    lifecycle = ManagedConfigurationLifecycle(owner, candidate_root=tmp_path / "candidates")
    try:
        for alias in (services.paths.root, services.paths.root / "nested-candidates", tmp_path):
            with pytest.raises(ValueError):
                ManagedConfigurationLifecycle(owner, candidate_root=alias)
        await owner.start()
        repo = services.get("conversations")
        first = repo.create(NewConversation())
        entry, _ = repo.streaming.begin("learning", first["identity"]["id"],
            Send(expected_revision=first["revision"], text="Synthetic CKD learning", request_id="reserved-root"))
        with pytest.raises(ApiError) as busy:
            await lifecycle.seal_new_runs(expected_effective='a' * 64)
        assert busy.value.code == "harness_configuration_busy"
        owner.bridge.check(entry["run"].id)
        assert entry["run"].cancelled.is_set() is False
        # Failed acquisition leaves admission available; a different saved
        # conversation can reserve its root under the unchanged live owner.
        second = repo.create(NewConversation())
        another, _ = repo.streaming.begin("learning", second["identity"]["id"],
            Send(expected_revision=second["revision"], text="Synthetic glomerular learning", request_id="second-root"))
        owner.bridge.check(another["run"].id)
        status = (await owner.process.request("host.status", {}, "busy-health", "1", 5))["result"]
        assert status["configurationId"] == 'a' * 64
        assert status["state"] == "ready" and status["modelCalls"] == 0
        assert status["activeSessionIds"] == []
    finally:
        await owner.close()
        services.get("helpers").startup.close()
