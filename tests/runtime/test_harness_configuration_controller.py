"""Controller/SQLite seam with synthetic lifecycle evidence, not live activation."""
import asyncio
import pytest

from renulus.contracts import ApiError
from renulus.runtime.harness_configuration import (
    ConfigurationAuthority, ConfigurationSpec, ConnectionReference, RolePolicy,
    CandidateHealth, RestartBoundary, InputHash, ContextPolicy, AttemptPolicy, ChildPolicy,
    RouteLimits,
)
from renulus.runtime.harness_configuration_controller import HarnessConfigurationController, RegistryHealth
from renulus.storage.database import Database


class SyntheticProvider:
    def __init__(self, connection=None):
        self.connection = connection
        self.checks = []

    def connections(self):
        if self.connection is None:
            return {"selected_provider": None, "selected_models": {}, "connections": []}
        return {"selected_provider": self.connection.provider,
                "selected_models": {self.connection.provider: self.connection.selected_model},
                "connections": [{"provider": self.connection.provider, "status": "connected",
                    "allowed_models": ["deepseek-v4.1-flash", "mimo-v2.6-pro"],
                    "credential_canary": "MUST-NOT-LEAVE"}]}

    def require_configuration_connection(self, connection):
        self.checks.append(connection)
        if connection != self.connection:
            raise ApiError("connection_changed", "The selected connection changed.", 409, True)


class SyntheticSeal:
    def __init__(self, lifecycle):
        self.lifecycle = lifecycle
        self.released = False

    def release(self):
        assert not self.released
        if self.lifecycle.on_release:
            self.lifecycle.on_release()
        self.released = True
        self.lifecycle.roots_open = True
        self.lifecycle.events.append("release")
        self.lifecycle.released.set()


class SyntheticLifecycle:
    """Explicitly synthetic: flags/events exercise orchestration, not the SDK."""
    def __init__(self, authority):
        self.authority = authority
        self.events = []
        self.roots_open = True
        self.seals = []
        self.on_seal = None
        self.on_release = None
        self.on_inspect = None
        self.on_stop = None
        self.on_start = None
        self.inspect_started = asyncio.Event()
        self.inspect_gate = None
        self.released = asyncio.Event()

    async def inspect_candidate(self, candidate):
        assert self.roots_open is False
        assert self.authority.activation_snapshot()["admission_open"] is True
        self.events.append("inspect-settled")
        self.inspect_started.set()
        if self.inspect_gate:
            await self.inspect_gate.wait()
        if self.on_inspect:
            return self.on_inspect(candidate)
        return CandidateHealth(configuration_version=candidate.version,
            grant_epoch=candidate.grant_epoch, registry_hash=candidate.spec.registry_hash)

    async def stop_and_settle(self, seal):
        assert not seal.released
        assert self.authority.activation_snapshot()["admission_open"] is False
        self.events.append("stop-settled")
        if self.on_stop:
            return self.on_stop()
        return RestartBoundary(admission_closed=True, runtime_stopped=True, domain_settled=True)

    async def start_gated(self, candidate, *, seal):
        from renulus.runtime.harness_configuration_controller import RegistryHealth
        assert not seal.released
        state = self.authority.activation_snapshot()
        assert state["effective"] == candidate.version
        assert state["admission_open"] is False
        self.events.append("start-gated")
        if self.on_start:
            return self.on_start(candidate)
        return RegistryHealth(configuration_version=candidate.version,
            grant_epoch=candidate.grant_epoch, registry_hash=candidate.spec.registry_hash)

    async def seal_new_runs(self, *, expected_effective):
        assert self.authority.activation_snapshot()["effective"] == expected_effective
        self.roots_open = False
        self.events.append("seal")
        seal = SyntheticSeal(self)
        self.seals.append(seal)
        if self.on_seal:
            self.on_seal()
        return seal

    def begin_run(self, run_id, purpose):
        if not self.roots_open:
            raise ApiError("harness_configuration_busy", "Synthetic roots sealed.", 409, True)
        return self.authority.begin_run(run_id, purpose)


@pytest.fixture
def configured(tmp_path):
    authority = ConfigurationAuthority(Database(tmp_path / "canonical.sqlite"))
    spec = ConfigurationSpec(
        connection=ConnectionReference(provider="opencode-go", credential_reference="protected-ref",
            credential_revision=7, selected_model=None), registry_hash="a" * 64,
        roles=(RolePolicy(purpose="explain"), RolePolicy(purpose="summary", dispatch_limit=1)),
        inputs=(InputHash(kind="instruction", name="educational", sha256="b" * 64),),
        capabilities=("library-read",), context=ContextPolicy(requested_window_tokens=8192),
        attempts=AttemptPolicy(foreground_dispatches=6, retries=1,
            retryable_errors=("transport_unavailable",)), children=ChildPolicy(concurrency=1))
    version = authority.stage(spec)
    # Synthetic setup only; the parent owns real bootstrap and engine settlement.
    assert authority.validate(version, lambda candidate: CandidateHealth(
        configuration_version=candidate.version, grant_epoch=candidate.grant_epoch,
        registry_hash=candidate.spec.registry_hash))
    authority.activate(version, RestartBoundary(admission_closed=True, runtime_stopped=True,
        domain_settled=True), expected_effective=None)
    authority.open_admission(version, registry_hash=spec.registry_hash, grant_epoch=0)
    provider = SyntheticProvider(spec.connection)
    controller = HarnessConfigurationController(authority, provider, object())
    return authority, spec, version, provider, controller


@pytest.mark.asyncio
async def test_no_account_bootstrap_stays_null_closed_without_lifecycle_work(tmp_path):
    authority = ConfigurationAuthority(Database(tmp_path / "canonical.sqlite"))
    controller = HarnessConfigurationController(authority, SyntheticProvider(), object())
    assert await controller.snapshot() == {
        "requested": None, "effective": None, "failed": None, "failure_code": None,
        "admission_open": False, "configuration": None,
        "requested_configuration": None, "pinned_runs": [], "catalogue": [],
    }


@pytest.mark.asyncio
async def test_stage_replaces_only_roles_and_returns_redacted_coherent_snapshot(configured):
    authority, spec, effective, provider, controller = configured
    roles = (RolePolicy(purpose="explain", model_id=None, output_tokens=1024, dispatch_limit=2),
             RolePolicy(purpose="title", enabled=False, model_id="mimo-v2.6-pro"))
    result = await controller.stage_roles(roles)
    candidate = authority.configuration(result["version"])
    assert candidate.roles == roles
    assert candidate.model_dump(exclude={"roles"}) == spec.model_dump(exclude={"roles"})
    assert candidate.connection.selected_model is None
    assert provider.checks == [spec.connection]
    assert result == {"version": result["version"], "requested": result["version"],
        "effective": effective, "failed": None, "failure_code": None, "admission_open": True}
    snapshot = await controller.snapshot()
    assert snapshot["requested"] == result["version"]
    assert snapshot["effective"] == effective
    assert snapshot["catalogue"] == ["deepseek-v4.1-flash", "mimo-v2.6-pro"]
    assert snapshot["configuration"] == {"roles": [role.model_dump() for role in spec.roles],
        "attempts": {"foreground_dispatches": 6, "standalone_dispatches": 1,
                     "title_dispatches": 0, "retries": 1}}
    assert snapshot["requested_configuration"]["roles"] == [role.model_dump() for role in roles]
    assert set(snapshot["requested_configuration"]) == {"roles", "attempts"}
    assert "protected-ref" not in str(snapshot)
    assert "MUST-NOT-LEAVE" not in str(snapshot)


@pytest.mark.asyncio
@pytest.mark.parametrize("roles", [(), [RolePolicy(purpose="explain")]])
async def test_stage_requires_bounded_typed_tuple_without_changing_pointers(configured, roles):
    authority, _, _, _, controller = configured
    before = authority.activation_snapshot()
    with pytest.raises(ApiError) as error:
        await controller.stage_roles(roles)
    assert error.value.code == "configuration_invalid"
    assert authority.activation_snapshot() == before


@pytest.mark.asyncio
@pytest.mark.parametrize("roles", [
    tuple(RolePolicy(purpose="explain") for _ in range(15)),
    (RolePolicy(purpose="summary"), RolePolicy(purpose="summary")),
    (RolePolicy(purpose="explain", model_id="gpt-6.1-sol"),),
    ({"purpose": "explain", "credential_reference": "injection"},),
])
async def test_stage_refuses_invalid_roles_and_foreign_model_without_writes(configured, roles):
    authority, _, _, _, controller = configured
    before = authority.activation_snapshot()
    with pytest.raises(ApiError) as error:
        await controller.stage_roles(roles)
    assert error.value.code == "configuration_invalid"
    assert authority.activation_snapshot() == before


@pytest.mark.asyncio
@pytest.mark.parametrize("selection", [
    None, ConnectionReference(provider="opencode-go", credential_reference="different-ref",
        credential_revision=7),
    ConnectionReference(provider="opencode-go", credential_reference="protected-ref",
        credential_revision=8),
    ConnectionReference(provider="opencode-go", credential_reference="protected-ref",
        credential_revision=7, selected_model="mimo-v2.6-pro"),
    ConnectionReference(provider="codex", credential_reference="protected-ref", credential_revision=7),
])
async def test_stage_checks_full_existing_connection_identity(configured, selection):
    authority, _, _, provider, controller = configured
    provider.connection = selection
    before = authority.activation_snapshot()
    with pytest.raises(ApiError) as error:
        await controller.stage_roles((RolePolicy(purpose="explain"),))
    assert (error.value.code, error.value.status, error.value.retryable) == (
        "connection_changed", 409, True)
    assert authority.activation_snapshot() == before


@pytest.mark.asyncio
async def test_stage_cannot_bootstrap_absent_effective_configuration(tmp_path):
    authority = ConfigurationAuthority(Database(tmp_path / "canonical.sqlite"))
    provider = SyntheticProvider(ConnectionReference(provider="opencode-go",
        credential_reference="existing-connection", credential_revision=7))
    controller = HarnessConfigurationController(authority, provider, object())
    before = authority.activation_snapshot()
    with pytest.raises(ApiError) as error:
        await controller.stage_roles((RolePolicy(purpose="explain"),))
    assert error.value.code == "configuration_not_active"
    assert authority.activation_snapshot() == before


@pytest.mark.asyncio
async def test_busy_root_is_checked_after_ingress_seal_without_changing_authority(configured):
    authority, spec, version, provider, _ = configured
    authority.begin_run("root", "explain")
    candidate = authority.stage(spec.model_copy(update={"roles": (RolePolicy(purpose="explain",
        output_tokens=1024),)}))
    lifecycle = SyntheticLifecycle(authority)
    controller = HarnessConfigurationController(authority, provider, lifecycle)
    before = authority.activation_snapshot()
    observed = []
    def after_seal():
        observed.append(authority.activation_snapshot())
        with pytest.raises(ApiError):
            lifecycle.begin_run("new-root", "explain")
    lifecycle.on_seal = after_seal
    with pytest.raises(ApiError) as error:
        await controller.activate(candidate)
    assert (error.value.code, error.value.status, error.value.retryable) == (
        "harness_configuration_busy", 409, True)
    assert observed == [before]
    assert authority.activation_snapshot() == before
    assert lifecycle.events == ["seal", "release"]
    assert lifecycle.roots_open is True
    assert (await controller.snapshot())["pinned_runs"] == [
        {"run_id": "root", "purpose": "explain", "version": version}]


@pytest.mark.asyncio
async def test_synthetic_activation_opens_canonical_then_ingress_after_final_health(configured):
    authority, spec, _, provider, _ = configured
    candidate = authority.stage(spec.model_copy(update={"roles": (RolePolicy(purpose="explain",
        output_tokens=1024),)}))
    lifecycle = SyntheticLifecycle(authority)
    controller = HarnessConfigurationController(authority, provider, lifecycle)
    at_release = []
    lifecycle.on_release = lambda: at_release.append(authority.activation_snapshot())
    result = await controller.activate(candidate)
    assert result["requested"] == result["effective"] == candidate
    assert result["admission_open"] is True
    assert result["failed"] is None
    assert lifecycle.events == ["seal", "inspect-settled", "stop-settled", "start-gated", "release"]
    assert len(at_release) == 1
    assert at_release[0]["admission_open"] is True
    assert at_release[0]["activating"] is None
    assert at_release[0]["previous"] is None
    assert lifecycle.roots_open is True
    assert provider.checks and all(check == spec.connection for check in provider.checks)
    assert authority.begin_run("fresh", "explain")["version"] == candidate


@pytest.mark.asyncio
async def test_cancelled_observer_cannot_release_mutation_and_get_does_not_wait(configured):
    authority, spec, version, provider, _ = configured
    candidate = authority.stage(spec.model_copy(update={"roles": (RolePolicy(purpose="explain",
        output_tokens=1024),)}))
    lifecycle = SyntheticLifecycle(authority)
    lifecycle.inspect_gate = asyncio.Event()
    controller = HarnessConfigurationController(authority, provider, lifecycle)
    observer = asyncio.create_task(controller.activate(candidate))
    await asyncio.wait_for(lifecycle.inspect_started.wait(), 2)
    try:
        snapshot = await asyncio.wait_for(controller.snapshot(), 2)
        assert snapshot["requested"] == candidate
        assert snapshot["effective"] == version
        observer.cancel()
        with pytest.raises(asyncio.CancelledError):
            await observer
        assert lifecycle.roots_open is False
        assert lifecycle.events == ["seal", "inspect-settled"]
    finally:
        lifecycle.inspect_gate.set()
    await asyncio.wait_for(lifecycle.released.wait(), 2)
    snapshot = await controller.snapshot()
    assert snapshot["effective"] == candidate
    assert snapshot["admission_open"] is True


@pytest.mark.asyncio
async def test_requested_revision_race_at_final_start_cannot_open_stale_candidate(configured):
    authority, spec, previous, provider, _ = configured
    candidate = authority.stage(spec.model_copy(update={"roles": (RolePolicy(purpose="explain",
        output_tokens=1024),)}))
    lifecycle = SyntheticLifecycle(authority)
    newer = []
    def final_observation(value):
        newer.append(authority.stage(spec))
        return RegistryHealth(configuration_version=value.version, grant_epoch=value.grant_epoch,
            registry_hash=value.spec.registry_hash)
    lifecycle.on_start = final_observation
    controller = HarnessConfigurationController(authority, provider, lifecycle)
    with pytest.raises(ApiError) as error:
        await controller.activate(candidate)
    assert error.value.code == "activation_conflict"
    state = authority.activation_snapshot()
    assert state["requested"] == newer[0]
    assert state["effective"] == state["activating"] == candidate
    assert state["previous"] == previous
    assert state["admission_open"] is False
    assert lifecycle.roots_open is False
    assert "release" not in lifecycle.events


@pytest.mark.asyncio
async def test_requested_pointer_race_after_final_observation_keeps_admission_and_roots_closed(configured, monkeypatch):
    authority, spec, previous, provider, _ = configured
    candidate = authority.stage(spec.model_copy(update={"roles": (RolePolicy(purpose="explain",
        output_tokens=1024),)}))
    lifecycle = SyntheticLifecycle(authority)
    controller = HarnessConfigurationController(authority, provider, lifecycle)
    independent = ConfigurationAuthority(Database(authority.db.path))
    open_admission = authority.open_admission
    newer = []

    def stage_before_open(*args, **kwargs):
        # Arrive after the controller's final observation, before the actual CAS.
        observed = independent.activation_snapshot()
        assert observed["requested"] == observed["effective"] == observed["activating"] == candidate
        assert observed["admission_open"] is False
        newer.append(independent.stage(spec.model_copy(update={"roles": (RolePolicy(purpose="summary"),)})))
        return open_admission(*args, **kwargs)

    monkeypatch.setattr(authority, "open_admission", stage_before_open)
    try:
        with pytest.raises(ApiError) as error:
            await controller.activate(candidate)
        assert (error.value.code, error.value.status, error.value.retryable) == (
            "activation_conflict", 409, False)
        state = authority.activation_snapshot()
        assert len(newer) == 1 and state["requested"] == newer[0]
        assert state["effective"] == state["activating"] == candidate
        assert state["previous"] == previous
        assert state["admission_open"] is False
        assert lifecycle.events == ["seal", "inspect-settled", "stop-settled",
                                    "start-gated", "stop-settled"]
        assert lifecycle.roots_open is False and not lifecycle.seals[0].released
        with pytest.raises(ApiError) as root_denied:
            lifecycle.begin_run("late-root", "explain")
        assert root_denied.value.code == "harness_configuration_busy"
        with pytest.raises(ApiError) as mutation_denied:
            await controller.activate(newer[0])
        assert mutation_denied.value.code == "harness_configuration_recovery_required"
        assert authority.activation_snapshot() == state
    finally:
        await controller.close()
    assert authority.activation_snapshot() == state
    assert lifecycle.roots_open is False and not lifecycle.seals[0].released


@pytest.mark.asyncio
async def test_failed_fresh_owner_is_settled_without_rollback_or_reopening(configured):
    authority, spec, previous, provider, _ = configured
    candidate = authority.stage(spec.model_copy(update={"roles": (RolePolicy(purpose="explain",
        output_tokens=1024),)}))
    lifecycle = SyntheticLifecycle(authority)
    lifecycle.on_start = lambda value: RegistryHealth(configuration_version=value.version,
        grant_epoch=value.grant_epoch, registry_hash=value.spec.registry_hash, healthy=False)
    controller = HarnessConfigurationController(authority, provider, lifecycle)
    with pytest.raises(ApiError) as error:
        await controller.activate(candidate)
    assert error.value.code == "candidate_unhealthy"
    assert lifecycle.events == ["seal", "inspect-settled", "stop-settled",
                                "start-gated", "stop-settled"]
    state = authority.activation_snapshot()
    assert state["effective"] == state["activating"] == candidate
    assert state["previous"] == previous
    assert state["admission_open"] is False
    assert lifecycle.roots_open is False
    for operation in (controller.stage_roles((RolePolicy(purpose="summary"),)),
                      controller.activate(candidate)):
        with pytest.raises(ApiError) as blocked:
            await operation
        assert (blocked.value.code, blocked.value.status) == (
            "harness_configuration_recovery_required", 503)
    assert authority.activation_snapshot() == state


@pytest.mark.asyncio
async def test_settled_inspector_failure_marks_candidate_without_leaking_private_error(configured):
    authority, spec, previous, provider, _ = configured
    candidate = authority.stage(spec.model_copy(update={"roles": (RolePolicy(purpose="explain",
        output_tokens=1024),)}))
    lifecycle = SyntheticLifecycle(authority)
    def fail(_):
        raise RuntimeError("SYNTHETIC-PRIVATE-CREDENTIAL-CANARY")
    lifecycle.on_inspect = fail
    controller = HarnessConfigurationController(authority, provider, lifecycle)
    with pytest.raises(ApiError) as error:
        await controller.activate(candidate)
    assert error.value.code == "harness_configuration_lifecycle_failed"
    assert "CANARY" not in error.value.message
    status = await controller.snapshot()
    assert status["requested"] == status["failed"] == candidate
    assert status["failure_code"] == "candidate_validation_failed"
    assert status["effective"] == previous
    assert status["admission_open"] is True
    assert lifecycle.events == ["seal", "inspect-settled", "release"]


@pytest.mark.asyncio
@pytest.mark.parametrize("change,code", [
    ({"healthy": False}, "candidate_unhealthy"),
    ({"registry_hash": "c" * 64}, "registry_mismatch"),
    ({"configuration_version": "d" * 64}, "candidate_authority_stale"),
    ({"grant_epoch": 1}, "candidate_authority_stale"),
    ({"generation_open": True}, "candidate_not_closed"),
    ({"recovery_open": True}, "candidate_not_closed"),
    ({"package_acquisition_open": True}, "candidate_not_closed"),
    ({"mcp_startup_open": True}, "candidate_not_closed"),
    ({"live_store_writer": True}, "candidate_not_closed"),
])
async def test_bad_isolated_health_preserves_healthy_effective(configured, change, code):
    authority, spec, previous, provider, _ = configured
    candidate = authority.stage(spec.model_copy(update={"roles": (RolePolicy(purpose="summary"),)}))
    lifecycle = SyntheticLifecycle(authority)
    lifecycle.on_inspect = lambda value: CandidateHealth(configuration_version=value.version,
        grant_epoch=value.grant_epoch, registry_hash=value.spec.registry_hash).model_copy(update=change)
    controller = HarnessConfigurationController(authority, provider, lifecycle)
    with pytest.raises(ApiError) as error:
        await controller.activate(candidate)
    assert error.value.code == code
    status = await controller.snapshot()
    assert status["requested"] == status["failed"] == candidate
    assert status["failure_code"] == code
    assert status["effective"] == previous
    assert status["admission_open"] is True
    assert lifecycle.events == ["seal", "inspect-settled", "release"]


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["inspect", "stop", "start"])
async def test_epoch_change_cannot_activate_stale_candidate_at_any_boundary(configured, phase):
    authority, spec, previous, provider, _ = configured
    candidate = authority.stage(spec.model_copy(update={"roles": (RolePolicy(purpose="summary"),)}))
    lifecycle = SyntheticLifecycle(authority)
    def inspected(value):
        authority.revoke("library-read")
        return CandidateHealth(configuration_version=value.version, grant_epoch=value.grant_epoch,
            registry_hash=value.spec.registry_hash)
    def stopped():
        authority.revoke("library-read")
        return RestartBoundary(admission_closed=True, runtime_stopped=True, domain_settled=True)
    def started(value):
        authority.revoke("library-read")
        return RegistryHealth(configuration_version=value.version, grant_epoch=value.grant_epoch,
            registry_hash=value.spec.registry_hash)
    if phase == "inspect":
        lifecycle.on_inspect = inspected
    elif phase == "stop":
        lifecycle.on_stop = stopped
    else:
        lifecycle.on_start = started
    controller = HarnessConfigurationController(authority, provider, lifecycle)
    with pytest.raises(ApiError) as error:
        await controller.activate(candidate)
    assert error.value.code == ("activation_conflict" if phase == "stop" else "candidate_authority_stale")
    state = authority.activation_snapshot()
    assert state["grant_epoch"] == 1
    assert state["revoked"] == ["library-read"]
    assert state["effective"] == (candidate if phase == "start" else previous)
    assert state["admission_open"] is (phase == "inspect")
    assert lifecycle.roots_open is (phase == "inspect")


@pytest.mark.asyncio
@pytest.mark.parametrize("change,code", [
    ({"registry_hash": "c" * 64}, "registry_mismatch"),
    ({"configuration_version": "d" * 64}, "candidate_authority_stale"),
    ({"grant_epoch": 1}, "candidate_authority_stale"),
])
async def test_final_registry_must_match_exact_candidate(configured, change, code):
    authority, spec, previous, provider, _ = configured
    candidate = authority.stage(spec.model_copy(update={"roles": (RolePolicy(purpose="summary"),)}))
    lifecycle = SyntheticLifecycle(authority)
    lifecycle.on_start = lambda value: RegistryHealth(configuration_version=value.version,
        grant_epoch=value.grant_epoch, registry_hash=value.spec.registry_hash).model_copy(update=change)
    controller = HarnessConfigurationController(authority, provider, lifecycle)
    with pytest.raises(ApiError) as error:
        await controller.activate(candidate)
    assert error.value.code == code
    state = authority.activation_snapshot()
    assert state["previous"] == previous
    assert state["effective"] == state["activating"] == candidate
    assert state["admission_open"] is False
    assert lifecycle.events[-1] == "stop-settled"
    assert lifecycle.roots_open is False


@pytest.mark.asyncio
async def test_repeated_activation_of_current_version_does_not_stop_healthy_owner(configured):
    authority, _, effective, provider, _ = configured
    lifecycle = SyntheticLifecycle(authority)
    controller = HarnessConfigurationController(authority, provider, lifecycle)
    before = authority.activation_snapshot()
    with pytest.raises(ApiError) as error:
        await controller.activate(effective)
    assert error.value.code == "activation_conflict"
    assert authority.activation_snapshot() == before
    assert lifecycle.events == []


@pytest.mark.asyncio
async def test_stage_waits_for_owned_activation_while_snapshot_remains_available(configured):
    authority, spec, previous, provider, _ = configured
    candidate = authority.stage(spec.model_copy(update={"roles": (RolePolicy(purpose="explain",
        output_tokens=1024),)}))
    lifecycle = SyntheticLifecycle(authority)
    lifecycle.inspect_gate = asyncio.Event()
    controller = HarnessConfigurationController(authority, provider, lifecycle)
    activation = asyncio.create_task(controller.activate(candidate))
    await asyncio.wait_for(lifecycle.inspect_started.wait(), 2)
    roles = (RolePolicy(purpose="summary", output_tokens=2048),)
    stage = asyncio.create_task(controller.stage_roles(roles))
    try:
        await asyncio.sleep(0)
        assert not stage.done()
        snapshot = await controller.snapshot()
        assert snapshot["requested"] == candidate
        assert snapshot["effective"] == previous
    finally:
        lifecycle.inspect_gate.set()
    activated, staged = await asyncio.wait_for(asyncio.gather(activation, stage), 2)
    assert activated["effective"] == staged["effective"] == candidate
    assert staged["requested"] == staged["version"] != candidate
    assert authority.configuration(staged["version"]).roles == roles
    assert lifecycle.events.count("seal") == 1


@pytest.mark.asyncio
async def test_root_seal_does_not_block_existing_tool_continuation_and_child_pins(configured):
    authority, spec, version, provider, _ = configured
    candidate = authority.stage(spec.model_copy(update={"roles": (RolePolicy(purpose="summary"),)}))
    authority.begin_run("root", "explain")
    limits = RouteLimits(input_tokens=4096, output_tokens=2048, window_tokens=8192)
    first = authority.admit("root", "first", payload_hash="1" * 64, request_kind="primary",
        connection=spec.connection, limits=limits, input_tokens=100)
    authority.mark_dispatched(first["permit_id"], connection=spec.connection,
        limits=limits, input_tokens=100, payload_hash="1" * 64)
    authority.complete(first["permit_id"], "confirmed", result_reference="partial-answer")
    before = authority.status()
    lifecycle = SyntheticLifecycle(authority)
    continued = []
    def after_seal():
        continued.append(authority.admit("root", "continuation", payload_hash="2" * 64,
            request_kind="tool-continuation", continuation_of=first["permit_id"],
            connection=spec.connection, limits=limits, input_tokens=100))
        authority.begin_child("child", "root", "summary")
    lifecycle.on_seal = after_seal
    controller = HarnessConfigurationController(authority, provider, lifecycle)
    with pytest.raises(ApiError) as error:
        await controller.activate(candidate)
    assert error.value.code == "harness_configuration_busy"
    assert authority.status() == before
    assert continued[0]["state"] == "reserved"
    assert continued[0]["dispatch_purpose"] == "explain"
    assert (await controller.snapshot())["pinned_runs"] == [
        {"run_id": "child", "purpose": "summary", "version": version},
        {"run_id": "root", "purpose": "explain", "version": version}]
    assert authority.mark_dispatched(continued[0]["permit_id"], connection=spec.connection,
        limits=limits, input_tokens=100, payload_hash="2" * 64)["dispatch_allowed"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("permit_state", ["reserved", "dispatched", "confirmed", "uncertain"])
async def test_busy_includes_attempt_owners_and_terminal_finalizers(configured, permit_state):
    authority, spec, version, provider, _ = configured
    candidate = authority.stage(spec.model_copy(update={"roles": (RolePolicy(purpose="summary"),)}))
    authority.begin_run("owner", "explain")
    limits = RouteLimits(input_tokens=4096, output_tokens=2048, window_tokens=8192)
    permit = authority.admit("owner", "first", payload_hash="1" * 64, request_kind="primary",
        connection=spec.connection, limits=limits, input_tokens=100)
    if permit_state != "reserved":
        authority.mark_dispatched(permit["permit_id"], connection=spec.connection,
            limits=limits, input_tokens=100, payload_hash="1" * 64)
    if permit_state in {"confirmed", "uncertain"}:
        authority.complete(permit["permit_id"], permit_state)
    lifecycle = SyntheticLifecycle(authority)
    controller = HarnessConfigurationController(authority, provider, lifecycle)
    before = authority.activation_snapshot()
    with pytest.raises(ApiError) as error:
        await controller.activate(candidate)
    assert (error.value.code, error.value.status, error.value.retryable) == (
        "harness_configuration_busy", 409, True)
    assert authority.activation_snapshot() == before
    assert lifecycle.events == ["seal", "release"]
    assert (await controller.snapshot())["pinned_runs"] == [
        {"run_id": "owner", "purpose": "explain", "version": version}]


@pytest.mark.asyncio
async def test_canonical_close_independently_rejects_late_pin_without_stopping(configured):
    authority, spec, previous, provider, _ = configured
    candidate = authority.stage(spec.model_copy(update={"roles": (RolePolicy(purpose="summary"),)}))
    lifecycle = SyntheticLifecycle(authority)
    def inspected(value):
        # Simulate an independently arriving canonical pin despite the synthetic gate.
        authority.begin_run("late", "explain")
        return CandidateHealth(configuration_version=value.version, grant_epoch=value.grant_epoch,
            registry_hash=value.spec.registry_hash)
    lifecycle.on_inspect = inspected
    before = authority.status()
    controller = HarnessConfigurationController(authority, provider, lifecycle)
    with pytest.raises(ApiError) as error:
        await controller.activate(candidate)
    assert (error.value.code, error.value.retryable) == ("harness_configuration_busy", True)
    assert authority.status() == before
    assert authority.run("late")["version"] == previous
    assert lifecycle.events == ["seal", "inspect-settled", "release"]


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["admission_closed", "runtime_stopped", "domain_settled"])
async def test_incomplete_stopped_boundary_never_selects_or_reopens(configured, field):
    authority, spec, previous, provider, _ = configured
    candidate = authority.stage(spec.model_copy(update={"roles": (RolePolicy(purpose="summary"),)}))
    lifecycle = SyntheticLifecycle(authority)
    lifecycle.on_stop = lambda: RestartBoundary(admission_closed=True, runtime_stopped=True,
        domain_settled=True).model_copy(update={field: False})
    controller = HarnessConfigurationController(authority, provider, lifecycle)
    with pytest.raises(ApiError) as error:
        await controller.activate(candidate)
    assert error.value.code == "restart_boundary_required"
    state = authority.activation_snapshot()
    assert state["effective"] == previous
    assert state["requested"] == candidate
    assert state["admission_open"] is False
    assert lifecycle.roots_open is False
    assert lifecycle.events == ["seal", "inspect-settled", "stop-settled"]


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["inspect", "start"])
async def test_provider_identity_is_rechecked_after_lifecycle_waits(configured, phase):
    authority, spec, previous, provider, _ = configured
    candidate = authority.stage(spec.model_copy(update={"roles": (RolePolicy(purpose="summary"),)}))
    lifecycle = SyntheticLifecycle(authority)
    def changed(value):
        provider.connection = spec.connection.model_copy(update={"credential_revision": 8})
        health_type = CandidateHealth if phase == "inspect" else RegistryHealth
        return health_type(configuration_version=value.version, grant_epoch=value.grant_epoch,
            registry_hash=value.spec.registry_hash)
    if phase == "inspect":
        lifecycle.on_inspect = changed
    else:
        lifecycle.on_start = changed
    controller = HarnessConfigurationController(authority, provider, lifecycle)
    with pytest.raises(ApiError) as error:
        await controller.activate(candidate)
    assert (error.value.code, error.value.status, error.value.retryable) == ("connection_changed", 409, True)
    state = authority.activation_snapshot()
    assert state["effective"] == (previous if phase == "inspect" else candidate)
    assert state["admission_open"] is (phase == "inspect")
    assert lifecycle.roots_open is (phase == "inspect")


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["inspect", "stop", "start"])
async def test_known_lifecycle_api_error_keeps_classification(configured, phase):
    authority, spec, previous, provider, _ = configured
    candidate = authority.stage(spec.model_copy(update={"roles": (RolePolicy(purpose="summary"),)}))
    lifecycle = SyntheticLifecycle(authority)
    expected = ApiError("synthetic_owner_unavailable", "Synthetic owner is unavailable.", 503, True)
    def fail(*args):
        raise expected
    setattr(lifecycle, "on_" + phase, fail)
    controller = HarnessConfigurationController(authority, provider, lifecycle)
    with pytest.raises(ApiError) as error:
        await controller.activate(candidate)
    assert error.value is expected
    state = authority.activation_snapshot()
    assert state["effective"] == (candidate if phase == "start" else previous)
    assert state["admission_open"] is (phase == "inspect")
    assert lifecycle.roots_open is (phase == "inspect")


@pytest.mark.asyncio
async def test_owner_shutdown_signal_is_preserved_while_admission_remains_closed(configured):
    class SyntheticShutdown(BaseException):
        pass

    authority, spec, _, provider, _ = configured
    candidate = authority.stage(spec.model_copy(update={"roles": (RolePolicy(purpose="summary"),)}))
    lifecycle = SyntheticLifecycle(authority)
    signal = SyntheticShutdown()
    def stopped():
        raise signal
    lifecycle.on_stop = stopped
    controller = HarnessConfigurationController(authority, provider, lifecycle)
    with pytest.raises(SyntheticShutdown) as error:
        await controller.activate(candidate)
    assert error.value is signal
    assert authority.activation_snapshot()["admission_open"] is False
    assert lifecycle.roots_open is False


class HeldFinalizerLifecycle(SyntheticLifecycle):
    """Hold the owned activation's cleanup, after its HTTP observer exits."""
    def __init__(self, authority):
        super().__init__(authority)
        self.stop_count = 0
        self.finalizer_started = asyncio.Event()
        self.finalizer_release = asyncio.Event()
        self.finalizer_settled = asyncio.Event()
        self.finalizer_cancelled = asyncio.Event()
        self.on_start = lambda value: RegistryHealth(configuration_version=value.version,
            grant_epoch=value.grant_epoch, registry_hash=value.spec.registry_hash, healthy=False)

    async def stop_and_settle(self, seal):
        self.stop_count += 1
        if self.stop_count == 2:
            self.finalizer_started.set()
            try:
                await self.finalizer_release.wait()
            except asyncio.CancelledError:
                self.finalizer_cancelled.set()
                raise
        boundary = await super().stop_and_settle(seal)
        if self.stop_count == 2:
            self.finalizer_settled.set()
        return boundary


@pytest.mark.asyncio
async def test_close_drains_held_finalizer_after_cancelled_observer_and_seals_mutations(configured):
    authority, spec, _, provider, _ = configured
    candidate = authority.stage(spec.model_copy(update={"roles": (RolePolicy(purpose="summary"),)}))
    lifecycle = HeldFinalizerLifecycle(authority)
    controller = HarnessConfigurationController(authority, provider, lifecycle)
    observer = asyncio.create_task(controller.activate(candidate))
    close_waiter = None
    try:
        await asyncio.wait_for(lifecycle.finalizer_started.wait(), 2)
        observer.cancel()
        with pytest.raises(asyncio.CancelledError):
            await observer
        before = await controller.snapshot()
        close_waiter = asyncio.create_task(controller.close())
        await asyncio.sleep(0)
        assert not close_waiter.done()
        assert not lifecycle.finalizer_settled.is_set()
        assert not lifecycle.finalizer_cancelled.is_set()
        assert await asyncio.wait_for(controller.snapshot(), 2) == before
        for operation in (controller.stage_roles((RolePolicy(purpose="explain"),)),
                          controller.activate(candidate)):
            with pytest.raises(ApiError) as error:
                await asyncio.wait_for(operation, 2)
            assert (error.value.code, error.value.status, error.value.retryable) == (
                "runtime_stopping", 503, True)
        assert not close_waiter.done()
    finally:
        lifecycle.finalizer_release.set()
        await asyncio.wait_for(lifecycle.finalizer_settled.wait(), 2)
        if close_waiter is not None:
            assert await asyncio.wait_for(close_waiter, 2) is None
    assert await controller.snapshot() == before
    assert lifecycle.roots_open is False


@pytest.mark.asyncio
async def test_close_waiter_cancellation_cannot_finish_before_finalizer_settlement(configured):
    authority, spec, _, provider, _ = configured
    candidate = authority.stage(spec.model_copy(update={"roles": (RolePolicy(purpose="summary"),)}))
    lifecycle = HeldFinalizerLifecycle(authority)
    controller = HarnessConfigurationController(authority, provider, lifecycle)
    observer = asyncio.create_task(controller.activate(candidate))
    waiters = []
    try:
        await asyncio.wait_for(lifecycle.finalizer_started.wait(), 2)
        observer.cancel()
        with pytest.raises(asyncio.CancelledError):
            await observer
        waiters = [asyncio.create_task(controller.close()) for _ in range(2)]
        await asyncio.sleep(0)
        waiters[0].cancel()
        await asyncio.sleep(0)
        assert not waiters[0].done()
        assert not waiters[1].done()
        assert not lifecycle.finalizer_cancelled.is_set()
        assert not lifecycle.finalizer_settled.is_set()
        assert (await controller.snapshot())["admission_open"] is False
    finally:
        lifecycle.finalizer_release.set()
        await asyncio.wait_for(lifecycle.finalizer_settled.wait(), 2)
        results = await asyncio.wait_for(asyncio.gather(*waiters, return_exceptions=True), 2)
    assert isinstance(results[0], asyncio.CancelledError)
    assert results[1] is None
    assert await controller.close() is None
    assert not lifecycle.finalizer_cancelled.is_set()


@pytest.mark.asyncio
async def test_failed_seal_acquisition_sanitizes_and_retains_unknown_gate_recovery_fence(configured):
    authority, spec, _, provider, _ = configured
    candidate = authority.stage(spec.model_copy(update={"roles": (RolePolicy(purpose="summary"),)}))
    lifecycle = SyntheticLifecycle(authority)
    def failed_acquisition():
        # Deliberately violate failure-atomic acquisition; no handle reaches the controller.
        raise RuntimeError("SYNTHETIC-PRIVATE-ACQUISITION-CANARY")
    lifecycle.on_seal = failed_acquisition
    controller = HarnessConfigurationController(authority, provider, lifecycle)
    before = await controller.snapshot()
    with pytest.raises(ApiError) as error:
        await controller.activate(candidate)
    assert (error.value.code, error.value.status, error.value.retryable) == (
        "harness_configuration_lifecycle_failed", 503, True)
    assert "CANARY" not in error.value.message
    assert await controller.snapshot() == before
    for operation in (controller.stage_roles((RolePolicy(purpose="explain"),)),
                      controller.activate(candidate)):
        with pytest.raises(ApiError) as blocked:
            await operation
        assert (blocked.value.code, blocked.value.status, blocked.value.retryable) == (
            "harness_configuration_recovery_required", 503, True)
    assert lifecycle.events == ["seal"]
    assert lifecycle.roots_open is False
    assert not lifecycle.seals[0].released
    assert await controller.close() is None
    assert await controller.snapshot() == before
    assert lifecycle.events == ["seal"]


@pytest.mark.asyncio
async def test_close_rejects_queued_stage_but_allows_running_activation_to_finish(configured):
    authority, spec, _, provider, _ = configured
    candidate = authority.stage(spec.model_copy(update={"roles": (RolePolicy(purpose="explain",
        output_tokens=1024),)}))
    lifecycle = SyntheticLifecycle(authority)
    lifecycle.inspect_gate = asyncio.Event()
    controller = HarnessConfigurationController(authority, provider, lifecycle)
    observer = asyncio.create_task(controller.activate(candidate))
    tasks = [observer]
    try:
        await asyncio.wait_for(lifecycle.inspect_started.wait(), 2)
        queued = asyncio.create_task(controller.stage_roles((RolePolicy(purpose="summary"),)))
        tasks.append(queued)
        await asyncio.sleep(0)
        assert not queued.done()
        before = await controller.snapshot()
        closer = asyncio.create_task(controller.close())
        tasks.append(closer)
        await asyncio.sleep(0)
        assert not closer.done()
        assert await controller.snapshot() == before
    finally:
        lifecycle.inspect_gate.set()
        results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), 2)
    assert results[0]["effective"] == candidate
    assert isinstance(results[1], ApiError)
    assert (results[1].code, results[1].status, results[1].retryable) == (
        "runtime_stopping", 503, True)
    assert results[2] is None
    snapshot = await controller.snapshot()
    assert snapshot["requested"] == snapshot["effective"] == candidate
    assert snapshot["admission_open"] is True
    assert lifecycle.events == ["seal", "inspect-settled", "stop-settled", "start-gated", "release"]


@pytest.mark.asyncio
async def test_close_without_owned_mutations_is_idempotent_and_preserves_snapshot(configured):
    authority, _, _, _, controller = configured
    before = await controller.snapshot()
    assert await controller.close() is None
    assert await controller.close() is None
    assert await controller.snapshot() == before
    with pytest.raises(ApiError) as error:
        await controller.stage_roles((RolePolicy(purpose="summary"),))
    assert (error.value.code, error.value.status, error.value.retryable) == (
        "runtime_stopping", 503, True)
    assert authority.status()["admission_open"] is True


@pytest.mark.parametrize('code', ('harness_configuration_busy', 'activation_conflict'))
async def test_failure_atomic_root_refusal_allows_later_configuration_retry(configured, code):
    authority, spec, _, provider, _ = configured
    candidate = authority.stage(spec.model_copy(update={"roles": (RolePolicy(purpose="explain", output_tokens=1024),)}))

    class RefusedOnce(SyntheticLifecycle):
        refused = False

        async def seal_new_runs(self, *, expected_effective):
            if not self.refused:
                self.refused = True
                raise ApiError(code, 'The root gate refused before acquisition.', 409, True)
            return await super().seal_new_runs(expected_effective=expected_effective)

    lifecycle = RefusedOnce(authority)
    controller = HarnessConfigurationController(authority, provider, lifecycle)
    before = await controller.snapshot()
    with pytest.raises(ApiError) as refused:
        await controller.activate(candidate)
    assert refused.value.code == code
    assert await controller.snapshot() == before
    assert lifecycle.roots_open and not lifecycle.seals
    result = await controller.activate(candidate)
    assert result['effective'] == candidate and result['admission_open']
