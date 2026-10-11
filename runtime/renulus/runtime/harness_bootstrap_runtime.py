# SPDX-License-Identifier: MIT
"""Actual closed inspection and initial gated startup for one existing app.

The coordinator persists the Candidate before inspection and owns validation,
effective-pointer activation and final admission. Construct on the serving loop
before producers start. Supplied process bounds and executable/module evidence
are trusted integrator inputs; an immutable artifact does not prove that closure.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
import math
from pathlib import Path
import re

from renulus.contracts import ApiError
from renulus.services import Services
from .harness_configuration import Candidate, CandidateHealth, ConfigurationAuthority, ConfigurationSpec
from .harness_configuration_controller import RegistryHealth
from .harness_configuration_lifecycle import install_harness_configuration
from .harness_domain import DomainBinding
from .harness_launch import FrozenLaunchInputs, HarnessLaunchError, LaunchArtifactStore, finish_spec
from .harness_learning import HarnessLearningOwner
from .harness_model_registry import HarnessModelRegistry, ModelRunAuthority
from .harness_process import HarnessProcessConfig
from .harness_profile_owner import ProfileOwnerError, ProfileOwnerLease
from .manager import ProviderManager


ModelRegistryFactory = Callable[
    [Callable[[DomainBinding], ModelRunAuthority | None]], HarnessModelRegistry]
_MESSAGE = "The managed bootstrap runtime is unavailable."


def _safe(error):
    code, status, retryable = "harness_bootstrap_runtime_failed", 503, True
    if (isinstance(error, ApiError) and type(error.code) is str
            and re.fullmatch(r"[a-z][a-z0-9_]{0,127}", error.code)
            and type(error.status) is int and 400 <= error.status <= 599
            and type(error.retryable) is bool):
        code, status, retryable = error.code, error.status, error.retryable
    raise ApiError(code, _MESSAGE, status, retryable) from None


class ManagedBootstrapRuntime:
    """One Owner/controller, retained by Services before factory publication.

    The optional registry factory is synchronous and local: a fresh registry uses
    the same authority and explicit deployment evidence/HTTP/bounds. No factory
    denies model callbacks; native RegistryHealth is not account/deployment health.
    close drains the shared Services owner and never releases the issuer lease.
    """
    def __init__(self, spec: ConfigurationSpec, inputs: FrozenLaunchInputs, lease: ProfileOwnerLease, *,
                 services: Services, authority: ConfigurationAuthority, config: HarnessProcessConfig,
                 launch_store: LaunchArtifactStore, candidate_root: Path, attempt_timeout: float,
                 model_registry_factory: ModelRegistryFactory | None = None) -> None:
        if type(lease) is not ProfileOwnerLease:
            raise ApiError("harness_bootstrap_conflict", _MESSAGE, 409)
        try:
            lease.require_predecessor(lease.predecessor)
        except ProfileOwnerError:
            raise ApiError("harness_bootstrap_conflict", _MESSAGE, 409) from None
        if (type(services) is not Services or type(authority) is not ConfigurationAuthority
                or type(config) is not HarnessProcessConfig or authority.db is not services.db):
            raise ApiError("harness_bootstrap_conflict", _MESSAGE, 409)
        scope = lease.scope
        provider = services.registry.get("provider")
        if (config.profile_root != scope.root or services.paths.root != scope.root
                or config.profile_id != scope.profile_id or config.store_id != scope.runtime_store_id
                or config.domain_store_id != scope.domain_store_id
                or type(config.domain_path) is not str or not config.domain_path
                or Path(config.domain_path).is_absolute() or ".." in Path(config.domain_path).parts
                or (scope.root / config.domain_path).resolve() != services.db.path
                or type(provider) is not ProviderManager or provider.paths is not services.paths):
            raise ApiError("harness_bootstrap_conflict", _MESSAGE, 409)
        if (type(attempt_timeout) not in (int, float) or not math.isfinite(attempt_timeout)
                or attempt_timeout <= 0 or type(config.start_timeout) not in (int, float)
                or not math.isfinite(config.start_timeout) or config.start_timeout <= 0
                or any(type(value) is not int or value <= 0 for value in (config.max_inflight,
                    config.max_control_inflight, config.max_domain_inflight, config.max_domain_result_records,
                    config.max_domain_result_bytes, config.max_frame_bytes, config.max_result_records,
                    config.max_result_bytes))):
            raise ApiError("harness_bootstrap_bounds_invalid", _MESSAGE, 409)
        if (type(spec) is not ConfigurationSpec or type(inputs) is not FrozenLaunchInputs
                or type(launch_store) is not LaunchArtifactStore):
            raise ApiError("harness_launch_invalid", _MESSAGE, 409)
        references = [item for item in spec.inputs if item.kind == "artifact" and item.name == "launch"]
        if len(references) != 1:
            raise ApiError("harness_launch_invalid", _MESSAGE, 409)
        try:
            loaded = launch_store.load(references[0].sha256)
            matches = loaded == inputs and finish_spec(loaded, spec.registry_hash) == spec
        except HarnessLaunchError:
            raise ApiError("harness_launch_invalid", _MESSAGE, 409) from None
        if not matches:
            raise ApiError("harness_launch_invalid", _MESSAGE, 409)
        self._inputs = loaded
        self._config = replace(config, boot_settings=loaded.boot_settings)
        if (not isinstance(candidate_root, Path)
                or not candidate_root.is_absolute() or candidate_root.resolve() != candidate_root
                or candidate_root.is_relative_to(scope.root) or scope.root.is_relative_to(candidate_root)
                or any(not isinstance(path, Path) or not path.is_absolute() or not path.is_file()
                    for path in (config.node_executable, config.host_entry))
                or model_registry_factory is not None and not callable(model_registry_factory)
                or services.stopping):
            raise ApiError("harness_bootstrap_conflict", _MESSAGE, 409)
        memory = services.get("memory")
        if memory.services is not services or memory.db is not services.db:
            raise ApiError("harness_bootstrap_conflict", _MESSAGE, 409)
        services.get("conversations")
        self._services, self._authority, self._lease = services, authority, lease
        self._spec, self._store, self._provider, self._memory = spec, launch_store, provider, memory
        self._candidate_root, self._attempt_timeout = candidate_root, attempt_timeout
        self._registry_factory = model_registry_factory
        self._partial_registry = None
        self._owner = self._lifecycle = None
        self._candidate = self._inspected = None
        self._installed = self._failed = self._closing = False
        # This callback owns only an unfinished installation. Registering close
        # here would recurse into the Services drain which is already executing.
        services.on_shutdown_dependencies.append(self._drain_partial)

    def _require_candidate(self, candidate):
        if self._closing or self._services.stopping:
            raise ApiError("runtime_stopping", _MESSAGE, 503, True)
        if self._failed:
            raise ApiError("harness_bootstrap_conflict", _MESSAGE, 409)
        try:
            self._lease.require_predecessor(self._lease.predecessor)
        except ProfileOwnerError:
            raise ApiError("harness_bootstrap_conflict", _MESSAGE, 409) from None
        if (self._authority.db is not self._services.db
                or self._services.registry.get("provider") is not self._provider
                or self._services.registry.get("memory") is not self._memory
                or type(candidate) is not Candidate or candidate.spec != self._spec
                or type(candidate.grant_epoch) is not int
                or candidate.grant_epoch != self._authority.revocation_overlay()["epoch"]
                or self._candidate is not None and candidate != self._candidate
                or any(value is not False for value in (candidate.generation_open, candidate.recovery_open,
                    candidate.package_acquisition_open, candidate.mcp_startup_open, candidate.live_store_writer))
                or self._authority.configuration(candidate.version) != self._spec):
            raise ApiError("candidate_authority_stale", _MESSAGE, 409, True)

    def _install(self, candidate):
        self._require_candidate(candidate)
        if self._installed:
            return
        registry = self._services.registry
        if (any(registry.get(key) is not None for key in ("learning_harness", "harness_learning",
                "harness_configuration_controller", "harness_configuration_lifecycle"))
                or registry.get("harness_configuration_authority") not in (None, self._authority)):
            raise ApiError("harness_bootstrap_conflict", _MESSAGE, 409)
        self._candidate = candidate
        try:
            self._owner = HarnessLearningOwner(self._services, self._config, configuration_id=candidate.version,
                memory=self._memory, context_filtering=True, configuration_authority=self._authority,
                profile_owner=self._lease, model_registry_factory=(self._make_registry
                    if self._registry_factory is not None else None))
            self._owner.install()
            install_harness_configuration(self._owner, authority=self._authority, provider=self._provider,
                candidate_root=self._candidate_root, attempt_timeout=self._attempt_timeout,
                launch_store=self._store)
            self._lifecycle = registry["harness_configuration_lifecycle"]
            self._installed = True
        except Exception as error:
            self._failed = True
            _safe(error)

    async def inspect_candidate(self, candidate: Candidate) -> CandidateHealth:
        try:
            self._install(candidate)
            health = await self._lifecycle.inspect_candidate(candidate)
            self._require_candidate(candidate)
            self._inspected = candidate
            return health
        except Exception as error:
            _safe(error)

    async def start_live(self, candidate: Candidate) -> RegistryHealth:
        try:
            self._require_candidate(candidate)
            if not self._installed or self._inspected != candidate:
                raise ApiError("harness_bootstrap_conflict", _MESSAGE, 409)
            return await self._owner.start_gated(candidate)
        except Exception as error:
            _safe(error)

    async def _drain_partial(self):
        if self._owner is not None and not self._installed:
            await self._owner.close()
        registry = self._partial_registry
        if registry is not None and (self._owner is None or registry is not self._owner.model_registry):
            await registry.close(0)
            while (await registry.settlement(1)).owned:
                pass

    def _make_registry(self, resolve_run):
        if (self._partial_registry is not None
                and (self._owner is None or self._partial_registry is not self._owner.model_registry)):
            raise ApiError("harness_bootstrap_conflict", _MESSAGE, 409)
        try:
            registry = self._registry_factory(resolve_run)
        except Exception as error:
            _safe(error)
        if isinstance(registry, HarnessModelRegistry):
            # Owner's constructor can reject the factory product before returning.
            # Services already retains this callback, including that failure path.
            self._partial_registry = registry
        return registry

    async def close(self) -> None:
        """Observe the retained app drain; never register this method as its callback."""
        self._closing = True
        await self._services.finish_shutdown()
