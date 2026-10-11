"""Saved admission pins configuration through the same canonical transaction.

The native transport and registry health below are explicit synthetic adapters;
the public conversations and ConfigurationAuthority own the persisted behavior.
"""
from pathlib import Path

import pytest

from renulus.contracts import ApiError
from renulus.learn.conversation_models import NewConversation, Send
from renulus.learn.harness_bridge import HarnessLearningBridge
from renulus.runtime.harness_configuration import (
    CandidateHealth, ConfigurationAuthority, ConfigurationSpec, ConnectionReference,
    RestartBoundary,
)
from renulus.runtime.harness_learning import HarnessLearningOwner
from renulus.runtime.harness_process import HarnessProcessConfig
from renulus.server import create_app

from tests.learn.test_harness_bridge import ScriptedTransport, active_shape


@pytest.fixture
def saved_admission(tmp_path):
    services = create_app(tmp_path / "profile").state.services
    authority = ConfigurationAuthority(services.db)
    spec = ConfigurationSpec(connection=ConnectionReference(provider="opencode-go",
        credential_reference="synthetic-admission-connection", credential_revision=1),
        registry_hash="a" * 64, capabilities=("tools",))
    version = authority.stage(spec)
    assert authority.validate(version, lambda candidate: CandidateHealth(
        configuration_version=candidate.version, grant_epoch=candidate.grant_epoch,
        registry_hash=candidate.spec.registry_hash))
    authority.activate(version, RestartBoundary(admission_closed=True, runtime_stopped=True,
        domain_settled=True), expected_effective=None)
    authority.open_admission(version, registry_hash=spec.registry_hash, grant_epoch=0)
    repo = services.get("conversations")
    bridge = HarnessLearningBridge(repo, ScriptedTransport(), active_manifest=active_shape,
        configuration_id=version)
    services.registry["learning_harness"] = bridge
    chat = repo.create(NewConversation())
    request = Send(expected_revision=chat["revision"], text="Explain synthetic glomerular disease.",
        request_id="synthetic-atomic-admission")
    try:
        yield services, authority, bridge, repo, chat, request, version
    finally:
        repo.streaming.active.clear()
        services.get("helpers").startup.close()


def test_saved_run_pins_configuration_once_in_its_owner_transaction(saved_admission):
    services, authority, bridge, repo, chat, request, version = saved_admission
    observed = []

    def admit(conn, run, incoming):
        observed.append((conn.in_transaction, incoming is request))
        authority.begin_run_in(conn, run.id, "explain", expected_version=version,
            capability_scope=("tools",), operation_model=incoming.model)

    bridge.admit_run_in = admit
    entry, receipt = repo.streaming.begin("learning", chat["identity"]["id"], request)
    pinned = authority.run(receipt["run_id"])
    assert observed == [(True, True)]
    assert (pinned["run_id"], pinned["version"], pinned["purpose"]) == (
        entry["run"].id, version, "explain")
    assert pinned["route"]["model_id"] == "mimo-v2.6-pro"
    assert pinned["spent_dispatches"] == 0

    # A duplicate saved command cannot create or repin a second operation.
    with pytest.raises(ApiError, match="already running"):
        repo.streaming.begin("learning", chat["identity"]["id"], request)
    assert observed == [(True, True)]
    assert [pin["run_id"] for pin in authority.activation_snapshot()["pinned_runs"]] == [entry["run"].id]


def test_rejected_configuration_pin_rolls_back_saved_admission_and_can_retry(saved_admission):
    _, authority, bridge, repo, chat, request, version = saved_admission
    seen = []

    def refuse_after_pin(conn, run, incoming):
        seen.append(run.id)
        authority.begin_run_in(conn, run.id, "explain", expected_version=version,
            capability_scope=("tools",))
        raise ApiError("synthetic_admission_refusal", "Synthetic admission refuses after pinning.", 409)

    bridge.admit_run_in = refuse_after_pin
    with pytest.raises(ApiError) as error:
        repo.streaming.begin("learning", chat["identity"]["id"], request)
    assert error.value.code == "synthetic_admission_refusal"
    assert authority.activation_snapshot()["pinned_runs"] == []
    assert repo.streaming.list("learning", chat["identity"]["id"])["items"] == []
    assert repo.get("learning", chat["identity"]["id"])["revision"] == chat["revision"]
    with pytest.raises(ApiError) as missing:
        authority.run(seen[0])
    assert missing.value.code == "run_missing"

    # Reusing the same public request remains possible after atomic rollback.
    bridge.admit_run_in = lambda conn, run, incoming: authority.begin_run_in(conn, run.id,
        "explain", expected_version=version, capability_scope=("tools",))
    _, receipt = repo.streaming.begin("learning", chat["identity"]["id"], request)
    assert authority.run(receipt["run_id"])["state"] == "active"
    assert len(authority.activation_snapshot()["pinned_runs"]) == 1


def test_learning_owner_uses_the_canonical_configuration_route_at_saved_admission(saved_admission):
    services, authority, _, repo, chat, request, version = saved_admission
    config = HarnessProcessConfig(node_executable=Path("G:/unused-node.exe"),
        host_entry=Path("G:/unused-host.mjs"), profile_root=services.paths.root,
        profile_id="synthetic-profile", store_id="synthetic-runtime",
        domain_store_id="synthetic-domain", domain_path="state/renulus.sqlite3")
    owner = HarnessLearningOwner(services, config, configuration_id=version,
        configuration_authority=authority)
    owner.bridge.active_manifest = active_shape
    services.registry["learning_harness"] = owner.bridge
    entry, receipt = repo.streaming.begin("learning", chat["identity"]["id"], request)
    pinned = authority.run(receipt["run_id"])
    assert pinned["route"]["model_id"] == "mimo-v2.6-pro"
    assert entry["run"].harness_configuration_version == version
    assert entry["run"].harness_model_id == "mimo-v2.6-pro"
    assert entry["run"].harness_capabilities == ("tools",)
    assert pinned["spent_dispatches"] == 0
