# SPDX-License-Identifier: MIT
"""Actual process/registry adapter for restart-based configuration changes.

The controller owns canonical activation. This adapter owns isolated candidate
processes, a root-only learning lease, actual exit/domain settlement and rebinding
the existing transcript/resolver owner to a fresh gated generation. It does not
invent account evidence, bootstrap health, rollback or recovery authority.
"""
import asyncio
import math
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from renulus.contracts import ApiError
from .harness_configuration import Candidate, CandidateHealth, ConfigurationSpec, RestartBoundary
from .harness_configuration_controller import HarnessConfigurationController, RegistryHealth
from .harness_launch import FrozenLaunchInputs, HarnessLaunchError, LaunchArtifactStore, finish_spec
from .harness_process import ManagedHarnessProcess, OBSERVATION_COMMANDS


def _launch_error() -> ApiError:
    return ApiError('harness_launch_invalid',
        'The launch artifact is unavailable or does not match the configuration.', 409, True)


def install_harness_configuration(owner, *, authority, candidate_root: Path, provider=None,
                                  attempt_timeout=5, launch_store: LaunchArtifactStore | None = None):
    """Explicit assembly only; it does not bootstrap or activate a configuration."""
    services = owner.services
    if (services.registry.get('harness_learning') is not owner or authority.db is not services.db
            or services.registry.get('harness_configuration_controller') is not None):
        raise ApiError('harness_owner_conflict', 'Configuration already has an owner or a different profile.', 409)
    lifecycle = ManagedConfigurationLifecycle(owner, candidate_root=candidate_root,
        attempt_timeout=attempt_timeout, launch_store=launch_store)
    controller = HarnessConfigurationController(authority, provider or services.get('provider'), lifecycle)
    services.registry['harness_configuration_authority'] = authority
    services.registry['harness_configuration_lifecycle'] = lifecycle
    services.registry['harness_configuration_controller'] = controller
    services.on_shutdown.append(controller.close)
    # Owner.install registered owner.close earlier. Reversed dependency shutdown
    # therefore drains retained candidates before closing the learning transport.
    services.on_shutdown_dependencies.append(lifecycle.close)
    return controller


class ManagedConfigurationLifecycle:
    def __init__(self, owner, *, candidate_root: Path, attempt_timeout: float = 5,
                 launch_store: LaunchArtifactStore | None = None):
        live = owner.config.profile_root
        if (not isinstance(candidate_root, Path) or not candidate_root.is_absolute()
                or candidate_root.resolve() != candidate_root
                or candidate_root.is_relative_to(live) or live.is_relative_to(candidate_root)):
            raise ValueError('Candidate profiles need a separate explicit owned root.')
        if type(attempt_timeout) not in (int, float) or not math.isfinite(attempt_timeout) or attempt_timeout <= 0:
            raise ValueError('Lifecycle attempts need a positive finite observation budget.')
        self.owner, self.candidate_root = owner, candidate_root
        self.attempt_timeout = attempt_timeout
        self.launch_store = launch_store
        self._stopped = None
        self._owned_processes = set()
        self._drains = {}
        self._closing = False

    def _launch_inputs(self, spec: ConfigurationSpec) -> FrozenLaunchInputs:
        references = [item for item in spec.inputs
                      if item.kind == 'artifact' and item.name == 'launch']
        store = self.launch_store
        if store is None or len(references) != 1:
            raise _launch_error()
        try:
            return store.load(references[0].sha256)
        except HarnessLaunchError:
            raise _launch_error() from None

    def freeze_inputs(self, spec: ConfigurationSpec) -> ConfigurationSpec:
        """Save the proposed policy with its prior immutable native boot payload."""
        if self.launch_store is None:
            return spec
        old = self._launch_inputs(spec)
        try:
            frozen = FrozenLaunchInputs(boot_settings=old.boot_settings,
                connection=spec.connection, roles=spec.roles,
                inputs=tuple(item for item in spec.inputs
                    if not (item.kind == 'artifact' and item.name == 'launch')),
                capabilities=spec.capabilities, context=spec.context,
                attempts=spec.attempts, children=spec.children)
            self.launch_store.save(frozen)
            return finish_spec(frozen, spec.registry_hash)
        except HarnessLaunchError:
            raise _launch_error() from None

    def _verified_launch(self, spec: ConfigurationSpec) -> FrozenLaunchInputs | None:
        if self.launch_store is None:
            return None
        inputs = self._launch_inputs(spec)
        try:
            matches = finish_spec(inputs, spec.registry_hash) == spec
        except HarnessLaunchError:
            matches = False
        if not matches:
            raise _launch_error()
        return inputs

    async def _own(self, work):
        """An observer cannot leave before process/finalizer ownership settles."""
        task = asyncio.create_task(work)
        cancelled = False
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                cancelled = True
            except BaseException:
                break
        if cancelled:
            if not task.cancelled():
                task.exception()
            raise asyncio.CancelledError
        return task.result()

    async def _stop(self, process):
        self._owned_processes.add(process)
        task = self._drains.get(process)
        if task is None:
            task = asyncio.create_task(self._drain_process(process))
            self._drains[process] = task
            task.add_done_callback(lambda done: self._drain_finished(process, done))
        done, _ = await asyncio.wait({task}, timeout=self.attempt_timeout)
        if not done:
            raise ApiError('harness_configuration_settlement_pending',
                'The old runtime still owns work.', 503, True)
        task.result()

    async def _drain_process(self, process):
        while True:
            await process.close(1)
            if ((await process.settlement(0))['state'] == 'settled'
                    and not process.domain_status()['active']):
                return
            await asyncio.sleep(.01)

    def _drain_finished(self, process, task):
        if not task.cancelled() and task.exception() is None:
            self._owned_processes.discard(process)
            self._drains.pop(process, None)

    async def close(self):
        """Shutdown retains every isolated/blocked owner until actual settlement."""
        self._closing = True
        await self._own(self._close())

    async def _close(self):
        for process in tuple(self._owned_processes):
            task = self._drains.get(process)
            if task is None:
                task = asyncio.create_task(self._drain_process(process))
                self._drains[process] = task
                task.add_done_callback(lambda done, owned=process: self._drain_finished(owned, done))
            await asyncio.shield(task)

    def _require_open(self):
        if self._closing:
            raise ApiError('runtime_stopping', 'The configuration runtime is closing.', 503, True)

    async def inspect_candidate(self, candidate: Candidate) -> CandidateHealth:
        self._require_open()
        if self._owned_processes:
            raise ApiError('harness_configuration_settlement_pending',
                'An isolated configuration runtime still owns work.', 503, True)
        return await self._own(self._inspect_candidate(candidate))

    async def _inspect_candidate(self, candidate):
        self.owner.require_profile_owner()
        inputs = self._verified_launch(candidate.spec)
        suffix = uuid4().hex
        root = self.candidate_root / suffix
        root.mkdir(parents=True)
        config = replace(self.owner.config, profile_root=root, profile_id='candidate-' + suffix,
            store_id='candidate-runtime-' + suffix, domain_store_id='candidate-domain-' + suffix)
        if inputs is not None:
            config = replace(config, boot_settings=inputs.boot_settings)
        process = ManagedHarnessProcess()  # Candidate has no domain or credential grants.
        self._owned_processes.add(process)
        try:
            await process.start(config)
            self.owner.register_process(process, config)
            result = await self._request(process, 'host.inspect', {})
            return CandidateHealth(configuration_version=candidate.version, grant_epoch=candidate.grant_epoch,
                registry_hash=result['registry_hash'], generation_open=result['generation_open'],
                recovery_open=result['recovery_open'], package_acquisition_open=result['package_acquisition_open'],
                mcp_startup_open=result['mcp_startup_open'], live_store_writer=result['live_store_writer'])
        finally:
            await self._stop(process)

    async def seal_new_runs(self, *, expected_effective):
        self._require_open()
        # Synchronous canonical acquisition: no await after sealing before return.
        return self.owner.seal_new_runs(expected_effective=expected_effective)

    def _require_seal(self, seal):
        self.owner.require_root_seal(seal)

    async def stop_and_settle(self, seal) -> RestartBoundary:
        self._require_seal(seal)
        await self._own(self._stop(self.owner.process))
        self._stopped = self.owner.process
        return RestartBoundary(admission_closed=True, runtime_stopped=True, domain_settled=True)

    async def start_gated(self, candidate, *, seal) -> RegistryHealth:
        self._require_open()
        self._require_seal(seal)
        if self._stopped is not self.owner.process:
            raise ApiError('restart_boundary_required', 'Observe old-owner settlement before restart.', 409)
        return await self._own(self._start_gated(candidate, seal))

    async def _start_gated(self, candidate, seal):
        self.owner.require_profile_owner()
        inputs = self._verified_launch(candidate.spec)
        self._require_seal(seal)
        if inputs is not None:
            # Bind the copied payload before the existing owner builds activation.
            self.owner.config = replace(self.owner.config, boot_settings=inputs.boot_settings)
        process = ManagedHarnessProcess(domain_authority=self.owner.authorize)
        self.owner.replace_process(process, configuration_id=candidate.version, seal=seal)
        # Rebinding first retains a partially started fresh owner for idempotent
        # stop_and_settle if launch, activation or registry inspection fails.
        await process.start(self.owner.config)
        self.owner.register_process(process, self.owner.config)
        await self.owner.activation.activate()
        registry = await self._request(process, 'host.inspect', {})
        if (not registry['live_store_writer'] or registry['registry_hash'] != candidate.spec.registry_hash
                or any(registry[key] for key in ('generation_open', 'recovery_open',
                    'package_acquisition_open', 'mcp_startup_open'))):
            raise ApiError('registry_mismatch', 'The fresh gated registry differs from the candidate.', 409, True)
        await self._request(process, 'host.activate', {'configuration_id': candidate.version})
        return RegistryHealth(configuration_version=candidate.version, grant_epoch=candidate.grant_epoch,
            registry_hash=registry['registry_hash'])

    async def _request(self, process, command, payload):
        deadline = asyncio.get_running_loop().time() + self.attempt_timeout
        response = await process.request(command, payload, 'configuration-' + uuid4().hex, '1', self.attempt_timeout)
        while response['outcome'] == 'accepted_pending':
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise ApiError('harness_configuration_lifecycle_failed',
                    'The configuration operation remains pending; its owner is retained.', 503, True)
            await asyncio.sleep(min(0.02, remaining))
            response = await process.query_result(response['request_id'])
        release = getattr(process, 'release_observation', None)
        if command in OBSERVATION_COMMANDS and release is not None:
            try:
                await asyncio.wait_for(release(response['request_id']),
                    max(0, deadline - asyncio.get_running_loop().time()))
            except TimeoutError:
                raise ApiError('harness_configuration_lifecycle_failed',
                    'The observation release remains pending; its owner is retained.', 503, True) from None
        if response['outcome'] != 'committed_reference':
            raise ApiError('harness_configuration_lifecycle_failed',
                'The managed runtime did not confirm its configuration operation.', 503, True)
        return response['result']
