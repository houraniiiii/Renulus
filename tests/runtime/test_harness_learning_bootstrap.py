"""Gated saved-owner startup over actual production main; no inference.

Configuration staging/validation/activation is explicit test-owned metadata
assembly with a synthetic connection reference, not a profile coordinator.
"""
from contextlib import asynccontextmanager
from dataclasses import replace

import pytest

from renulus.contracts import ApiError
from renulus.learn.conversation_models import NewConversation, Send
from renulus.runtime.harness_configuration import (
    AttemptPolicy, Candidate, CandidateHealth, ConfigurationAuthority, ConfigurationSpec,
    ConnectionReference, ContextPolicy, RestartBoundary, RolePolicy,
)
from renulus.runtime.harness_configuration_controller import RegistryHealth
from renulus.runtime.harness_learning import HarnessLearningOwner
from renulus.runtime.harness_process import HarnessProcessError, ManagedHarnessProcess
from renulus.server import create_app
from test_harness_learning_models import SOURCE, inspect_candidate, process_config


class ObservedProcess(ManagedHarnessProcess):
    """Record gate metadata from actual public replies, then return unchanged."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.observations = []

    async def request(self, command, payload, operation_id, attempt_id, timeout):
        reply = await super().request(command, payload, operation_id, attempt_id, timeout)
        if command in {"host.stores.activate", "host.inspect", "host.activate"}:
            result = reply.get("result", {})
            keys = ("state", "registry_hash", "generation_open", "recovery_open",
                "package_acquisition_open", "mcp_startup_open", "live_store_writer", "configurationId")
            self.observations.append({"command": command, "outcome": reply["outcome"],
                "configuration_id": payload.get("configuration_id"),
                "result": {key: result[key] for key in keys if key in result}})
        return reply


class AfterAuthenticatedStartProcess(ObservedProcess):
    """Invoke trusted local work after actual readiness, returning unchanged."""
    def __init__(self, *args, after_start, **kwargs):
        super().__init__(*args, **kwargs)
        self.after_start = after_start

    async def start(self, config):
        ready = await super().start(config)
        self.after_start()
        return ready


@asynccontextmanager
async def bootstrap_profile(tmp_path):
    isolated = await inspect_candidate(tmp_path / "candidate")
    services = create_app(tmp_path / "profile", source_root=SOURCE).state.services
    authority = ConfigurationAuthority(services.db)
    owner = None
    try:
        spec = ConfigurationSpec(connection=ConnectionReference(provider="opencode-go",
            credential_reference="synthetic_bootstrap_connection", credential_revision=1,
            selected_model="mimo-v2.6-pro"), registry_hash=isolated["registry_hash"],
            roles=(RolePolicy(purpose="explain", model_id="mimo-v2.6-pro",
                output_tokens=32, dispatch_limit=1),), capabilities=("text", "tools"),
            context=ContextPolicy(requested_window_tokens=640, reserve_tokens=8),
            attempts=AttemptPolicy(foreground_dispatches=1, retries=0))
        version = authority.stage(spec)
        observed = ("registry_hash", "generation_open", "recovery_open",
            "package_acquisition_open", "mcp_startup_open", "live_store_writer")
        assert authority.validate(version, lambda candidate: CandidateHealth(
            configuration_version=candidate.version, grant_epoch=candidate.grant_epoch,
            **{key: isolated[key] for key in observed}))
        authority.activate(version, RestartBoundary(admission_closed=True, runtime_stopped=True,
            domain_settled=True), expected_effective=None)
        candidate = Candidate(version, authority.configuration(version),
            authority.revocation_overlay()["epoch"])
        owner = HarnessLearningOwner(services, process_config(services.paths.root,
            "synthetic-gated-learning"), configuration_id=version, configuration_authority=authority)
        assert (await owner.process.settlement(0))["state"] == "settled"
        observed = ObservedProcess(domain_authority=owner.authorize)
        seal = owner.seal_new_runs(expected_effective=version)
        try:
            owner.replace_process(observed, configuration_id=version, seal=seal)
        finally:
            seal.release()
        owner.install()
        yield services, owner, authority, candidate, isolated
    finally:
        if owner is not None:
            await owner.close()
            assert (await owner.process.settlement(10))["state"] == "settled"
            assert owner.process.domain_status()["active"] == 0
        services.get("helpers").startup.close()


async def test_gated_saved_owner_proves_live_registry_without_opening_canonical_admission(tmp_path):
    async with bootstrap_profile(tmp_path) as (services, owner, authority, candidate, isolated):
        before = await owner.process.request("host.status", {}, "before-live-bootstrap", "1", 0)
        assert before["outcome"] == "rejected_before_admission"
        assert before["error"]["code"] == "not_started"
        assert authority.status()["effective"] == candidate.version
        assert authority.status()["admission_open"] is False
        health = await owner.start_gated(candidate)
        assert isinstance(health, RegistryHealth)
        assert health.model_dump() == {"configuration_version": candidate.version,
            "grant_epoch": candidate.grant_epoch, "registry_hash": isolated["registry_hash"],
            "healthy": True}
        assert owner.manifest()["state"] == "active"
        assert owner.activation.status() == {"state": "active", "error_code": None}
        assert owner.process.observations == [
            {"command": "host.stores.activate", "outcome": "committed_reference",
                "configuration_id": None, "result": {"state": "active"}},
            {"command": "host.inspect", "outcome": "committed_reference", "configuration_id": None,
                "result": {"state": "policy_blocked", "registry_hash": isolated["registry_hash"],
                    "generation_open": False, "recovery_open": False,
                    "package_acquisition_open": False, "mcp_startup_open": False, "live_store_writer": True}},
            {"command": "host.activate", "outcome": "committed_reference",
                "configuration_id": candidate.version,
                "result": {"state": "ready", "configurationId": candidate.version}},
        ]
        ready = await owner.process.request("host.status", {}, "after-gated-bootstrap", "1", 5)
        assert ready["outcome"] == "committed_reference"
        assert ready["result"]["state"] == "ready"
        assert ready["result"]["configurationId"] == candidate.version
        assert ready["result"]["activeSessionIds"] == []
        assert authority.status()["admission_open"] is False
        repo = services.get("conversations")
        chat = repo.create(NewConversation())
        with pytest.raises(ApiError) as denied:
            repo.streaming.begin("learning", chat["identity"]["id"], Send(
                expected_revision=chat["revision"], text="Synthetic bootstrap gate check.",
                request_id="synthetic-bootstrap-closed"))
        assert denied.value.code == "configuration_not_active" and denied.value.status == 409
        assert repo.streaming.active == {}
        await owner.start()
        reused = await owner.process.request("host.status", {}, "reused-gated-bootstrap", "1", 5)
        assert reused["outcome"] == "committed_reference"
        assert reused["generation"] == ready["generation"]
        assert reused["result"] == ready["result"]
        assert len(owner.process.observations) == 3
        assert authority.status()["admission_open"] is False
        assert owner.process.domain_status()["active"] == 0


async def test_candidate_epoch_mismatch_refuses_before_live_native_readiness(tmp_path):
    async with bootstrap_profile(tmp_path) as (services, owner, authority, candidate, isolated):
        canonical = authority.activation_snapshot()
        stale = replace(candidate, grant_epoch=candidate.grant_epoch + 1)
        with pytest.raises(ApiError) as denied:
            await owner.start_gated(stale)
        assert denied.value.code == "candidate_authority_stale"
        assert denied.value.status == 409 and denied.value.retryable is True
        with pytest.raises(HarnessProcessError, match="unavailable"):
            owner.process.native_identity()
        response = await owner.process.request("host.status", {}, "refused-bootstrap", "1", 0)
        assert response["outcome"] == "rejected_before_admission"
        assert response["error"]["code"] == "not_started"
        assert owner.process.observations == []
        assert owner.activation.status() == {"state": "prepared", "error_code": None}
        assert authority.activation_snapshot() == canonical
        assert authority.status()["admission_open"] is False
        assert services.get("conversations").streaming.active == {}
        assert owner.process.domain_status()["active"] == 0


async def test_epoch_change_during_authenticated_start_refuses_before_store_activation(tmp_path):
    async with bootstrap_profile(tmp_path) as (services, owner, authority, candidate, isolated):
        assert (await owner.process.settlement(0))["state"] == "settled"
        observed = AfterAuthenticatedStartProcess(domain_authority=owner.authorize,
            after_start=lambda: authority.revoke("tools"))
        seal = owner.seal_new_runs(expected_effective=candidate.version)
        try:
            owner.replace_process(observed, configuration_id=candidate.version, seal=seal)
        finally:
            seal.release()
        with pytest.raises(ApiError) as denied:
            await owner.start_gated(candidate)
        assert denied.value.code == "candidate_authority_stale"
        assert denied.value.status == 409 and denied.value.retryable is True
        assert authority.revocation_overlay() == {"epoch": candidate.grant_epoch + 1, "revoked": ["tools"]}
        identity = owner.process.native_identity()
        response = await owner.process.request("host.status", {}, "startup-epoch-refusal", "1", 5)
        assert response["outcome"] == "committed_reference"
        assert response["generation"] == identity.generation
        assert response["result"]["state"] == "policy_blocked"
        assert response["result"].get("configurationId") is None
        assert response["result"]["activeSessionIds"] == []
        assert (await owner.process.settlement(0))["state"] == "pending"
        assert authority.status()["admission_open"] is False
        assert services.get("conversations").streaming.active == {}
        assert owner.activation.status() == {"state": "prepared", "error_code": None}
        assert owner.process.observations == []
        assert owner.process.domain_status()["active"] == 0
    assert (await owner.process.settlement(0))["state"] == "settled"
    with pytest.raises(HarnessProcessError, match="unavailable"):
        owner.process.native_identity()
