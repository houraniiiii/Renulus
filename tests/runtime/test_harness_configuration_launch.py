# SPDX-License-Identifier: MIT
"""Launch/lifecycle public seams with owned artifacts and synthetic process IO."""
from types import SimpleNamespace

import pytest

from renulus.contracts import ApiError

from renulus.runtime.harness_configuration import (
    AttemptPolicy, Candidate, CandidateHealth, ChildPolicy, ConfigurationAuthority,
    ConnectionReference, ContextPolicy, InputHash, RestartBoundary, RolePolicy,
)
from renulus.runtime.harness_configuration_controller import HarnessConfigurationController
from renulus.runtime.harness_configuration_lifecycle import (
    ManagedConfigurationLifecycle, install_harness_configuration,
)
from renulus.runtime.harness_launch import FrozenLaunchInputs, LaunchArtifactStore, finish_spec
from renulus.runtime.harness_process import HarnessProcessConfig
from renulus.storage.database import Database


def launch_fixture(tmp_path):
    store = LaunchArtifactStore(tmp_path / "artifacts", live_root=tmp_path / "live",
                               candidate_root=tmp_path / "candidates")
    inputs = FrozenLaunchInputs(
        boot_settings={"config": {"instructions": ["Synthetic CKD learning"]}},
        connection=ConnectionReference(provider="opencode-go",
            credential_reference="synthetic-selected", credential_revision=4),
        roles=(RolePolicy(purpose="explain", output_tokens=2048),),
        inputs=(InputHash(kind="build", name="synthetic-reviewed-cohort", sha256="b" * 64),),
        capabilities=("text", "tools"),
        context=ContextPolicy(requested_window_tokens=8192, reserve_tokens=256),
        attempts=AttemptPolicy(foreground_dispatches=4), children=ChildPolicy(),
    )
    store.save(inputs)
    spec = finish_spec(inputs, "a" * 64)
    config = HarnessProcessConfig(
        node_executable=tmp_path / "synthetic-node.exe",
        host_entry=tmp_path / "synthetic-host.mjs",
        profile_root=tmp_path / "live", profile_id="synthetic-profile",
        store_id="synthetic-runtime", domain_store_id="synthetic-domain",
        domain_path="state/renulus.sqlite3",
        boot_settings={"config": {"instructions": ["Ambient config must not win"]}},
    )
    return store, inputs, spec, SimpleNamespace(config=config)


def test_role_edit_freezes_a_new_artifact_with_the_same_boot_payload(tmp_path):
    store, old_inputs, spec, owner = launch_fixture(tmp_path)
    lifecycle = ManagedConfigurationLifecycle(owner, candidate_root=tmp_path / "candidates",
                                              launch_store=store)
    roles = (RolePolicy(purpose="explain", output_tokens=1024, dispatch_limit=2),)
    proposed = spec.model_copy(update={"roles": roles})
    frozen = lifecycle.freeze_inputs(proposed)
    references = [item for item in frozen.inputs if item.kind == "artifact" and item.name == "launch"]
    assert len(references) == 1 and references[0].sha256 != old_inputs.sha256
    loaded = store.load(references[0].sha256)
    assert loaded.boot_settings == {"config": {"instructions": ["Synthetic CKD learning"]}}
    assert finish_spec(loaded, frozen.registry_hash) == frozen
    assert frozen.roles == roles
    assert frozen.model_dump(exclude={"roles", "inputs"}) == spec.model_dump(exclude={"roles", "inputs"})
    assert frozen.inputs[:-1] == spec.inputs[:-1]
    assert lifecycle.freeze_inputs(frozen) == frozen
    assert store.load(old_inputs.sha256) == old_inputs
    assert owner.config.boot_settings["config"]["instructions"] == ["Ambient config must not win"]


class SyntheticProcess:
    """Only the external process seam is synthetic; lifecycle code is unchanged."""
    def __init__(self, observation, *, domain_authority=None):
        self.observation = observation
        self.writer = False
        self.closed = False
        observation.processes.append(self)

    async def start(self, config):
        self.observation.starts.append(config)

    async def close(self, timeout):
        self.closed = True
        return {"state": "closed"}

    async def settlement(self, timeout):
        return {"state": "settled"}

    def domain_status(self):
        return {"active": 0}

    async def request(self, command, payload, request_id, attempt_id, timeout):
        self.observation.commands.append(command)
        result = {"registry_hash": "a" * 64, "generation_open": False,
                  "recovery_open": False, "package_acquisition_open": False,
                  "mcp_startup_open": False, "live_store_writer": self.writer}
        return {"outcome": "committed_reference", "result": result}


class SyntheticOwner:
    def __init__(self, config, observation):
        self.config = config
        self.process = SyntheticProcess(observation)
        self.seal = None
        self.activation = None

    async def authorize(self, request):
        raise AssertionError("No domain/network calls are part of these fixtures.")

    def seal_new_runs(self, *, expected_effective):
        self.seal = object()
        return self.seal

    def require_root_seal(self, seal):
        if seal is None or seal is not self.seal:
            raise ApiError("activation_conflict", "Synthetic root seal changed.", 409, True)

    def replace_process(self, process, *, configuration_id, seal):
        self.require_root_seal(seal)
        self.process = process

        async def activate():
            process.writer = True

        self.activation = SimpleNamespace(activate=activate, config=self.config)


def process_fixture(tmp_path, monkeypatch, *, with_store=True):
    store, inputs, spec, old_owner = launch_fixture(tmp_path)
    observation = SimpleNamespace(processes=[], starts=[], commands=[])
    owner = SyntheticOwner(old_owner.config, observation)
    monkeypatch.setattr("renulus.runtime.harness_configuration_lifecycle.ManagedHarnessProcess",
        lambda **kwargs: SyntheticProcess(observation, **kwargs))
    lifecycle = ManagedConfigurationLifecycle(owner, candidate_root=tmp_path / "candidates",
                                              launch_store=store if with_store else None)
    return store, inputs, spec, owner, observation, lifecycle


@pytest.mark.parametrize("phase", ["candidate", "live"])
@pytest.mark.parametrize("case", ["missing-file", "tampered-file", "mismatched-policy",
                                  "missing-reference", "duplicate-reference"])
async def test_invalid_launch_evidence_denies_before_process_construction(tmp_path, monkeypatch, phase, case):
    store, inputs, spec, owner, observation, lifecycle = process_fixture(tmp_path, monkeypatch)
    path = tmp_path / "artifacts" / (inputs.sha256 + ".json")
    if case == "missing-file":
        path.unlink()
    elif case == "tampered-file":
        path.write_bytes(b"changed synthetic artifact")
    elif case == "mismatched-policy":
        spec = spec.model_copy(update={"roles": (RolePolicy(purpose="summary"),)})
    elif case == "missing-reference":
        spec = spec.model_copy(update={"inputs": spec.inputs[:-1]})
    else:
        spec = spec.model_copy(update={"inputs": (*spec.inputs, spec.inputs[-1])})
    candidate = Candidate("c" * 64, spec, 0)
    old_process = owner.process
    initial_config = owner.config
    if phase == "live":
        seal = await lifecycle.seal_new_runs(expected_effective="d" * 64)
        await lifecycle.stop_and_settle(seal)
    with pytest.raises(ApiError) as denied:
        if phase == "candidate":
            await lifecycle.inspect_candidate(candidate)
        else:
            await lifecycle.start_gated(candidate, seal=seal)
    assert denied.value.code == "harness_launch_invalid"
    assert observation.processes == [old_process]
    assert observation.starts == [] and observation.commands == []
    assert owner.process is old_process and owner.config is initial_config
    assert not (tmp_path / "candidates").exists()
    await lifecycle.close()


async def test_default_without_launch_store_preserves_legacy_boot_and_policy(tmp_path, monkeypatch):
    store, inputs, spec, owner, observation, _ = process_fixture(tmp_path, monkeypatch)
    initial_config = owner.config
    legacy = spec.model_copy(update={"inputs": spec.inputs[:-1]})
    lifecycle = ManagedConfigurationLifecycle(owner, candidate_root=tmp_path / "candidates")
    assert lifecycle.freeze_inputs(legacy) is legacy
    candidate = Candidate("c" * 64, legacy, 0)
    await lifecycle.inspect_candidate(candidate)
    assert observation.starts[0].boot_settings == initial_config.boot_settings
    seal = await lifecycle.seal_new_runs(expected_effective="d" * 64)
    await lifecycle.stop_and_settle(seal)
    await lifecycle.start_gated(candidate, seal=seal)
    assert owner.config is initial_config
    assert observation.starts[1] is initial_config
    assert sorted(path.name for path in (tmp_path / "artifacts").iterdir()) == [inputs.sha256 + ".json"]
    await lifecycle.close()


async def test_installer_forwards_the_explicit_optional_launch_store(tmp_path):
    store, inputs, spec, owner = launch_fixture(tmp_path)
    services = SimpleNamespace(db=object(), registry={"harness_learning": owner},
                               on_shutdown=[], on_shutdown_dependencies=[])
    owner.services = services
    authority = SimpleNamespace(db=services.db)
    controller = install_harness_configuration(owner, authority=authority, provider=object(),
        candidate_root=tmp_path / "candidates", launch_store=store)
    lifecycle = services.registry["harness_configuration_lifecycle"]
    assert services.registry["harness_configuration_controller"] is controller
    frozen = lifecycle.freeze_inputs(spec.model_copy(update={"roles": (RolePolicy(purpose="summary"),)}))
    reference = next(item for item in frozen.inputs if item.kind == "artifact" and item.name == "launch")
    assert reference.sha256 != inputs.sha256
    assert finish_spec(store.load(reference.sha256), frozen.registry_hash) == frozen
    assert services.on_shutdown == [controller.close]
    assert services.on_shutdown_dependencies == [lifecycle.close]
    await controller.close()
    await lifecycle.close()


@pytest.mark.parametrize("case", ["missing-file", "tampered-file", "save-refused"])
async def test_controller_freeze_failure_preserves_authority_and_uses_safe_errors(tmp_path, monkeypatch, case, caplog):
    from renulus.runtime.harness_launch import HarnessLaunchError

    store, inputs, spec, version, authority, provider, lifecycle, controller = controller_fixture(tmp_path)
    before = authority.activation_snapshot()
    path = tmp_path / "artifacts" / (inputs.sha256 + ".json")
    canary = "synthetic-" + "launch-canary-never-in-receipts"
    if case == "missing-file":
        path.unlink()
    elif case == "tampered-file":
        path.write_text(canary, encoding="utf-8")
    else:
        def refused_save(frozen):
            raise HarnessLaunchError("launch_artifact_invalid")
        monkeypatch.setattr(store, "save", refused_save)
    with pytest.raises(ApiError) as denied:
        await controller.stage_roles((RolePolicy(purpose="explain", output_tokens=1024),))
    assert denied.value.code == "harness_launch_invalid"
    assert canary not in denied.value.message and canary not in caplog.text
    assert authority.activation_snapshot() == before
    assert authority.configuration(version) == spec
    await controller.close()


class SyntheticProvider:
    def __init__(self, connection):
        self.connection = connection
        self.checks = []

    def require_configuration_connection(self, connection):
        assert connection == self.connection
        self.checks.append(connection)


def controller_fixture(tmp_path):
    store, inputs, spec, owner = launch_fixture(tmp_path)
    authority = ConfigurationAuthority(Database(tmp_path / "canonical.sqlite"))
    version = authority.stage(spec)
    # Explicit synthetic setup only; production activation belongs to the parent.
    assert authority.validate(version, lambda candidate: CandidateHealth(
        configuration_version=candidate.version, grant_epoch=candidate.grant_epoch,
        registry_hash=candidate.spec.registry_hash))
    authority.activate(version, RestartBoundary(admission_closed=True, runtime_stopped=True,
        domain_settled=True), expected_effective=None)
    authority.open_admission(version, registry_hash=spec.registry_hash, grant_epoch=0)
    provider = SyntheticProvider(spec.connection)
    lifecycle = ManagedConfigurationLifecycle(owner, candidate_root=tmp_path / "candidates",
                                              launch_store=store)
    controller = HarnessConfigurationController(authority, provider, lifecycle)
    return store, inputs, spec, version, authority, provider, lifecycle, controller


async def test_controller_stages_the_new_frozen_artifact_before_authority_stage(tmp_path, monkeypatch):
    store, inputs, spec, version, authority, provider, lifecycle, controller = controller_fixture(tmp_path)
    before = authority.activation_snapshot()
    observed_at_save = []
    save = store.save

    def observe_save(frozen):
        observed_at_save.append(authority.activation_snapshot())
        return save(frozen)

    monkeypatch.setattr(store, "save", observe_save)
    roles = (RolePolicy(purpose="explain", output_tokens=1024),)
    result = await controller.stage_roles(roles)
    staged = authority.configuration(result["version"])
    assert staged.roles == roles
    references = [item for item in staged.inputs if item.kind == "artifact" and item.name == "launch"]
    assert len(references) == 1 and references[0].sha256 != inputs.sha256
    loaded = store.load(references[0].sha256)
    assert finish_spec(loaded, staged.registry_hash) == staged
    assert loaded.boot_settings == inputs.boot_settings
    assert observed_at_save == [before]
    assert authority.status()["effective"] == version
    assert authority.configuration(version) == spec
    assert provider.checks == [spec.connection]
    await controller.close()


@pytest.mark.parametrize("change,code", [("requested", "activation_conflict"),
                                          ("epoch", "candidate_authority_stale")])
async def test_controller_rejects_stale_authority_after_artifact_save(tmp_path, monkeypatch, change, code):
    store, inputs, spec, version, authority, provider, lifecycle, controller = controller_fixture(tmp_path)
    independent = ConfigurationAuthority(Database(authority.db.path))
    save = store.save
    after_change = []

    def save_then_change(frozen):
        reference = save(frozen)
        if change == "requested":
            independent.stage(spec.model_copy(update={"registry_hash": "e" * 64}))
        else:
            independent.revoke("tools")
        after_change.append(independent.activation_snapshot())
        return reference

    monkeypatch.setattr(store, "save", save_then_change)
    with pytest.raises(ApiError) as denied:
        await controller.stage_roles((RolePolicy(purpose="explain", output_tokens=1024),))
    assert denied.value.code == code
    assert authority.activation_snapshot() == after_change[0]
    assert authority.configuration(version) == spec
    assert len(list((tmp_path / "artifacts").glob("*.json"))) == 2
    assert provider.checks == [spec.connection]
    await controller.close()


async def test_candidate_and_live_start_use_independent_exact_artifact_boot_copies(tmp_path, monkeypatch):
    store, inputs, spec, owner, observation, lifecycle = process_fixture(tmp_path, monkeypatch)
    loads = []
    original_load = store.load

    def counted_load(digest):
        loads.append(digest)
        return original_load(digest)

    monkeypatch.setattr(store, "load", counted_load)
    candidate = Candidate("c" * 64, spec, 0)
    initial_config = owner.config
    health = await lifecycle.inspect_candidate(candidate)
    assert health.registry_hash == spec.registry_hash
    isolated_config = observation.starts[0]
    assert isolated_config.boot_settings == {"config": {"instructions": ["Synthetic CKD learning"]}}
    assert isolated_config.profile_root.is_relative_to(tmp_path / "candidates")
    assert isolated_config.profile_root != initial_config.profile_root
    assert owner.config is initial_config
    assert observation.processes[1].closed
    isolated_config.boot_settings["config"]["instructions"].append("candidate mutation")
    seal = await lifecycle.seal_new_runs(expected_effective="d" * 64)
    await lifecycle.stop_and_settle(seal)
    live = await lifecycle.start_gated(candidate, seal=seal)
    assert live.registry_hash == spec.registry_hash
    live_config = observation.starts[1]
    assert live_config.boot_settings == {"config": {"instructions": ["Synthetic CKD learning"]}}
    assert live_config.profile_root == initial_config.profile_root
    assert live_config.node_executable == initial_config.node_executable
    assert live_config.host_entry == initial_config.host_entry
    assert owner.config is live_config and owner.activation.config is live_config
    assert live_config.boot_settings is not isolated_config.boot_settings
    assert loads == [inputs.sha256, inputs.sha256]
    assert original_load(inputs.sha256).boot_settings == inputs.boot_settings
    await lifecycle.close()
