# SPDX-License-Identifier: MIT
"""Opt-in startup under a real profile issuer, before application provisioning.

Parent assembly keeps API/root ingress closed until the final canonical CAS.
Native observation and cleanup belong to the installed runtime adapter. This
module neither reconstructs native recovery claims nor grants deployment health.
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path
from threading import current_thread, main_thread
from typing import Callable, Protocol

from fastapi import FastAPI

from renulus.contracts import ApiError

from .harness_configuration import (Candidate, CandidateHealth, ConfigurationAuthority,
                                    ConfigurationSpec, RestartBoundary)
from .harness_configuration_controller import RegistryHealth
from .harness_launch import FrozenLaunchInputs, HarnessLaunchError, LaunchArtifactStore, finish_spec
from .harness_profile_owner import ProfileOwnerLease, ProfileOwnerScope
from .manager import ProviderManager


class BootstrapRuntime(Protocol):
    """Parent installs the Owner once, when it first receives exact candidate V."""
    async def inspect_candidate(self, candidate: Candidate) -> CandidateHealth:
        """Observe actual closed native registry; settle or retain classified cleanup."""
        ...

    async def start_live(self, candidate: Candidate) -> RegistryHealth:
        """Delegate Owner.start_gated: pair, inspect blocked registry, then arm activate."""
        ...

    async def close(self) -> None:
        """Drain owned native work, or raise classified pending with its owner retained."""
        ...


RuntimeFactory = Callable[[ConfigurationSpec, FrozenLaunchInputs, ProfileOwnerLease], BootstrapRuntime]


_APPLICATION_OWNER: ProfileOwnerLease | None = None


@dataclass(frozen=True)
class BootstrapResult:
    effective_version: str | None
    admission_open: bool
    reason_code: str | None = None


class HarnessBootstrap:
    """One app and one retained startup task; repeated callers only observe it.

    The factory must install its shutdown ownership before publishing an adapter;
    exceptions before return must leave no unowned partial runtime. Successful
    runtimes remain app-owned. Startup failures await the adapter's finalizer.
    The actual issuer can provision only one app in its process lifetime.
    """
    def __init__(self, scope: ProfileOwnerScope, *, profile_owner: ProfileOwnerLease):
        self.scope = scope
        self.profile_owner = profile_owner
        self._require_owner()
        self._app = None
        self._creation_started = False
        self._starting = None
        self._arguments = None
        self._runtime = None
        self._observation = None
        self._closing = None

    def _require_owner(self):
        if current_thread() is not main_thread():
            raise ApiError("harness_bootstrap_main_thread_required", "Bootstrap requires the profile's main thread.", 409)
        scope, profile_owner = self.scope, self.profile_owner
        if (type(scope) is not ProfileOwnerScope or type(profile_owner) is not ProfileOwnerLease
                or profile_owner.scope != scope):
            raise ApiError("harness_bootstrap_conflict", "The bootstrap profile owner does not match.", 409)
        profile_owner.require_predecessor(profile_owner.predecessor)

    def create_app(self, *, token: str | None = None, source_root: Path | None = None,
                   provider_http_transport=None) -> FastAPI:
        global _APPLICATION_OWNER
        self._require_owner()
        if self._creation_started or _APPLICATION_OWNER is not None:
            raise ApiError("harness_bootstrap_conflict", "Application creation was already attempted.", 409)
        self._creation_started = True
        _APPLICATION_OWNER = self.profile_owner
        from renulus.server import create_app
        try:
            self._app = create_app(self.scope.root, token=token, source_root=source_root,
                provider_http_transport=provider_http_transport)
            self._services = self._app.state.services
            return self._app
        except Exception as error:
            raise _safe_failure(error) from None

    async def start(self, *, authority: ConfigurationAuthority, provider: ProviderManager,
                    launch_store: LaunchArtifactStore, assemble_runtime: RuntimeFactory,
                    initial_spec: ConfigurationSpec | None = None) -> BootstrapResult:
        self._require_binding(authority, provider)
        arguments = (authority, provider, launch_store, assemble_runtime, initial_spec)
        if self._arguments is not None and (any(left is not right for left, right
                in zip(arguments[:4], self._arguments[:4])) or initial_spec != self._arguments[4]):
            raise ApiError("harness_bootstrap_conflict", "Startup is already bound to another request.", 409)
        if self._starting is None:
            self._arguments = arguments
            self._starting = asyncio.create_task(
                self._start_guarded(authority, provider, launch_store, assemble_runtime, initial_spec),
                name="renulus-harness-bootstrap")
            self._starting.add_done_callback(lambda task: None if task.cancelled() else task.exception())
        result = await asyncio.shield(self._starting)
        try:
            if self._observation is not None:
                self._current(*self._observation)
            else:
                self._require_binding(authority, provider)
                current = authority.activation_snapshot()
                if any(current[key] != value for key, value in self._closed_state.items()):
                    raise ApiError("activation_conflict", "Closed startup state changed.", 409, True)
                if provider.configuration_connection() != self._local_connection:
                    raise ApiError("connection_changed", "Startup connection changed.", 409, True)
            return result
        except Exception as error:
            raise _safe_failure(error) from None

    def _require_binding(self, authority, provider):
        self._require_owner()
        if (self._app is None or self._app.state.services is not self._services
                or authority.db is not self._services.db
                or provider.paths is not self._services.paths
                or self._services.paths.root != self.scope.root
                or authority.db.path != self.scope.root / "state/renulus.sqlite3"):
            raise ApiError("harness_bootstrap_conflict", "Bootstrap must use this application's canonical services.", 409)

    def _boundary(self):
        # The issuer proves predecessor Python/native/job termination or explicit
        # new empty scope. No new process or store-lock observation grants this.
        self._require_owner()
        return RestartBoundary(admission_closed=True, runtime_stopped=True, domain_settled=True)

    def _launch(self, store, spec):
        references = [item for item in spec.inputs if item.kind == "artifact" and item.name == "launch"]
        if len(references) != 1:
            raise ApiError("harness_launch_invalid", "The immutable launch reference is missing.", 409)
        try:
            inputs = store.load(references[0].sha256)
            matches = finish_spec(inputs, spec.registry_hash) == spec
        except HarnessLaunchError:
            raise ApiError("harness_launch_invalid", "The immutable launch is unavailable.", 409) from None
        if not matches:
            raise ApiError("harness_launch_invalid", "The immutable launch does not match.", 409)
        return inputs

    def _current(self, authority, provider, store, candidate, expected):
        self._require_binding(authority, provider)
        provider.require_configuration_connection(candidate.spec.connection)
        self._launch(store, candidate.spec)
        snapshot = authority.activation_snapshot()
        if any(snapshot[key] != value for key, value in expected.items()):
            raise ApiError("activation_conflict", "Startup configuration changed.", 409, True)
        if authority.configuration(candidate.version) != candidate.spec:
            raise ApiError("activation_conflict", "Startup policy changed.", 409, True)
        if snapshot["pinned_runs"]:
            raise ApiError("harness_bootstrap_recovery_pending", "Canonical ownership is still unresolved.", 409, True)

    def _retire_predecessor(self, authority, previous):
        self._require_owner()
        current = authority.activation_snapshot()["pinned_runs"]
        if not current:
            return
        allowed = {pin["run_id"] for pin in previous["pinned_runs"]}
        if (self.profile_owner.predecessor.previous_generation is None
                or any(pin["run_id"] not in allowed for pin in current)):
            raise ApiError("harness_bootstrap_recovery_pending", "These pins have no settled predecessor.", 409, True)
        runs = {pin["run_id"]: authority.run(pin["run_id"]) for pin in current}
        depths = {}
        for run_id, run in runs.items():
            if run["state"] not in ("active", "settled"):
                raise ApiError("harness_bootstrap_recovery_pending", "The predecessor pin is unclassified.", 409, True)
            chain, cursor = [], run_id
            while cursor in runs and cursor not in depths:
                if cursor in chain:
                    raise ApiError("harness_bootstrap_recovery_pending", "The predecessor graph is invalid.", 409, True)
                chain.append(cursor)
                cursor = runs[cursor]["parent_id"]
            depth = depths.get(cursor, -1)
            for member in reversed(chain):
                depth += 1
                depths[member] = depth
        for run_id in sorted(runs, key=lambda item: (-depths[item], item)):
            self._require_owner()
            authority.settle_run(run_id)
        if authority.activation_snapshot()["pinned_runs"]:
            raise ApiError("harness_bootstrap_recovery_pending", "Unknown receipts still own policy pins.", 409, True)

    async def _start_guarded(self, authority, provider, launch_store, assemble_runtime, initial_spec):
        try:
            return await self._start(authority, provider, launch_store, assemble_runtime, initial_spec)
        except BaseException as error:
            if self._runtime is not None:
                try:
                    self._closing = asyncio.create_task(self._runtime.close(), name="renulus-bootstrap-cleanup")
                    while not self._closing.done():
                        try:
                            await asyncio.shield(self._closing)
                        except asyncio.CancelledError:
                            continue  # The cleanup owner remains retained until actual settlement.
                    self._closing.result()
                except BaseException as cleanup_error:
                    raise _safe_failure(cleanup_error, cleanup=True) from None
                try:
                    if self._observation is not None:
                        self._current(*self._observation)
                except Exception as changed:
                    error = changed
            raise _safe_failure(error) from None

    async def _start(self, authority, provider, launch_store, assemble_runtime, initial_spec):
        self._require_binding(authority, provider)
        previous = authority.activation_snapshot()
        if previous["pinned_runs"] and self.profile_owner.predecessor.previous_generation is None:
            raise ApiError("harness_bootstrap_recovery_pending", "Current pins have no terminated predecessor.", 409, True)
        authority.reconcile_restart(self._boundary())
        self._retire_predecessor(authority, previous)
        status = authority.activation_snapshot()
        self._closed_state = {key: status[key] for key in ("effective", "requested",
            "activating", "grant_epoch", "admission_open")}
        self._local_connection = provider.configuration_connection()
        if self._local_connection is None:
            return BootstrapResult(status["effective"], False, "harness_bootstrap_no_connection")
        if initial_spec is not None and any(status[key] is not None
                for key in ("effective", "requested", "activating")):
            raise ApiError("activation_conflict", "An initial policy requires null pointers.", 409)
        if status["effective"] is None and initial_spec is None:
            return BootstrapResult(status["effective"], False, "harness_bootstrap_policy_required")
        initial = status["effective"] is None
        spec = initial_spec if initial else status["configuration"]
        provider.require_configuration_connection(spec.connection)
        inputs = self._launch(launch_store, spec)
        if initial:
            version = authority.stage_if_current(spec, expected_effective=None,
                expected_requested=None, grant_epoch=status["grant_epoch"], expected_activating=None)
        else:
            version = status["effective"]
        candidate = Candidate(version, spec, status["grant_epoch"])
        expected = {"effective": status["effective"],
            "requested": version if initial else status["requested"],
            "activating": status["activating"], "grant_epoch": candidate.grant_epoch, "admission_open": False}
        self._observation = (authority, provider, launch_store, candidate, expected)
        self._current(*self._observation)
        self._runtime = assemble_runtime(spec, inputs, self.profile_owner)
        health = await self._runtime.inspect_candidate(candidate)
        self._current(*self._observation)
        def observed(given):
            if given != candidate:
                raise ApiError("candidate_authority_stale", "The candidate changed.", 409)
            return health
        if not authority.validate(version, observed):
            raise ApiError("candidate_unhealthy", "The isolated candidate did not validate.", 409, True)
        if initial:
            authority.activate(version, self._boundary(), expected_effective=None)
            expected.update(effective=version, activating=version)
        self._current(*self._observation)
        live = await self._runtime.start_live(candidate)
        self._current(*self._observation)
        if (not isinstance(live, RegistryHealth) or not live.healthy
                or live.configuration_version != version or live.grant_epoch != candidate.grant_epoch
                or live.registry_hash != spec.registry_hash):
            raise ApiError("registry_mismatch", "The gated live registry did not match.", 409, True)
        authority.open_admission(version, registry_hash=live.registry_hash, grant_epoch=live.grant_epoch,
            expected_requested=expected["requested"], expected_activating=expected["activating"])
        expected.update(admission_open=True, activating=None)
        return BootstrapResult(version, True)


def _safe_failure(error, *, cleanup=False):
    code = "harness_bootstrap_cleanup_pending" if cleanup else "harness_bootstrap_failed"
    status, retryable = 503, True
    if (isinstance(error, ApiError) and isinstance(error.code, str)
            and re.fullmatch(r"[a-z][a-z0-9_]{0,127}", error.code)
            and type(error.status) is int and 400 <= error.status <= 599
            and type(error.retryable) is bool):
        code, status, retryable = error.code, error.status, error.retryable
    return ApiError(code, "The harness could not finish startup safely.", status, retryable)
