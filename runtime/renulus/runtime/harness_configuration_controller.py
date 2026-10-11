# SPDX-License-Identifier: MIT
"""Configuration orchestration; the parent owns provider/lifecycle observations.

No host, credentials, schema or startup reconciliation lives here. The injected
lifecycle must observe actual ownership and settlement; synthetic implementations
only exercise this controller seam.
"""
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Protocol
from pydantic import Field, ValidationError

from renulus.contracts import ApiError

from .harness_configuration import (Candidate, CandidateHealth, ConfigurationAuthority,
    ConfigurationSpec, ConnectionReference, FrozenModel, RestartBoundary, RolePolicy)


class ConfigurationProvider(Protocol):
    """Cached provider owner; check full selection identity without IO/refresh."""
    def connections(self) -> dict: ...

    def require_configuration_connection(self, connection: ConnectionReference) -> None: ...


class NewRunSeal(Protocol):
    """Root gate only; release is synchronous, nonthrowing and parent-owned."""
    def release(self) -> None: ...


class RegistryHealth(FrozenModel):
    """Final transformed registry from the fresh live owner with ingress gated."""
    configuration_version: str = Field(pattern=r"^[0-9a-f]{64}$")
    grant_epoch: int = Field(ge=0)
    registry_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    healthy: bool = True


class ConfigurationLifecycle(Protocol):
    """One parent adapter; observation results must come from real lifecycle work."""
    async def inspect_candidate(self, candidate: Candidate) -> CandidateHealth:
        """Healthy results require isolated closed inspection AND settlement.

        A bounded settlement_pending refusal retains its isolated cleanup owner;
        the parent drains lifecycle.close before releasing runtime dependencies.
        """
        ...

    async def seal_new_runs(self, *, expected_effective: str | None) -> NewRunSeal:
        """Failure-atomic: exceptions leave ingress and ownership unchanged.

        After acquisition, return its seal without awaiting or doing fallible work.
        busy/conflict ApiErrors with status 409 are explicit pre-acquisition refusals.
        """
        ...

    async def stop_and_settle(self, seal: NewRunSeal) -> RestartBoundary:
        """Idempotent per seal, including a partially started fresh owner."""
        ...

    async def start_gated(self, candidate: Candidate, *, seal: NewRunSeal) -> RegistryHealth: ...


def _public_configuration(spec: ConfigurationSpec | None) -> dict | None:
    if spec is None:
        return None
    return {"roles": [role.model_dump(mode="json") for role in spec.roles],
            "attempts": spec.attempts.model_dump(include={"foreground_dispatches",
                "standalone_dispatches", "title_dispatches", "retries"})}


def _failed_probe(candidate: Candidate) -> CandidateHealth:
    raise RuntimeError("The isolated candidate probe failed.")


def _lifecycle_error(error: Exception) -> ApiError:
    if isinstance(error, ApiError):
        return error
    return ApiError("harness_configuration_lifecycle_failed",
        "The managed configuration lifecycle did not finish safely.", 503, True)


class HarnessConfigurationController:
    """One profile-owned instance; cancelled observers do not abandon mutations.

    After canonical admission closes, failures retain the seal and pointers.
    A seal acquisition error retains an unresolved ownership fence. Managed startup
    reconciliation or a future settled CAS rollback belongs to the parent; this
    instance refuses subsequent mutations while recovery is required.
    """
    def __init__(self, authority: ConfigurationAuthority, provider: ConfigurationProvider,
                 lifecycle: ConfigurationLifecycle):
        self.authority = authority
        self.provider = provider
        self.lifecycle = lifecycle
        self._seal: NewRunSeal | None = None
        self._acquisition_unresolved = False
        self._mutation_lock = asyncio.Lock()
        self._mutations: set[asyncio.Task] = set()
        self._closing = False
        self._close_task: asyncio.Task | None = None

    async def close(self) -> None:
        """Seal mutations and drain owned tasks/finalizers before dependencies close.

        Waiters share one barrier; cancellation propagates only after it finishes.
        The parent owns native settlement and any unresolved acquisition.
        """
        self._closing = True
        if self._close_task is None:
            self._close_task = asyncio.create_task(self._drain_mutations(tuple(self._mutations)))
        cancelled = False
        while not self._close_task.done():
            try:
                await asyncio.shield(self._close_task)
            except asyncio.CancelledError:
                cancelled = True
        self._close_task.result()
        if cancelled:
            raise asyncio.CancelledError

    async def _drain_mutations(self, mutations: tuple[asyncio.Task, ...]) -> None:
        if mutations:
            await asyncio.gather(*mutations, return_exceptions=True)

    def _require_running(self):
        if self._closing:
            raise ApiError("runtime_stopping",
                "Renulus is closing this profile. Wait for local work to finish", 503, True)

    async def activate(self, version: str) -> dict:
        return await self._mutate(lambda: self._activate(version))

    async def _mutate(self, operation: Callable[[], Awaitable[dict]]) -> dict:
        self._require_running()
        async def own_mutation():
            async with self._mutation_lock:
                self._require_running()
                if self._seal is not None or self._acquisition_unresolved:
                    raise ApiError("harness_configuration_recovery_required",
                        "Configuration admission is sealed pending managed recovery.", 503, True)
                return await operation()

        task = asyncio.create_task(own_mutation())
        self._mutations.add(task)
        task.add_done_callback(self._mutation_finished)
        return await asyncio.shield(task)

    def _mutation_finished(self, task: asyncio.Task):
        self._mutations.discard(task)
        if not task.cancelled():
            task.exception()  # Retrieve failures even when the HTTP observer has gone.

    async def _acquire_seal(self, expected_effective: str | None) -> NewRunSeal:
        self._acquisition_unresolved = True
        try:
            seal = await self.lifecycle.seal_new_runs(expected_effective=expected_effective)
        except Exception as error:
            if (isinstance(error, ApiError) and error.status == 409
                    and error.code in {'harness_configuration_busy', 'activation_conflict'}):
                self._acquisition_unresolved = False
            # Unclassified acquisition failure retains a fence; no handle means no release.
            raise _lifecycle_error(error) from None
        self._seal = seal
        self._acquisition_unresolved = False
        return seal

    async def _activate(self, version: str) -> dict:
        expected = self.authority.activation_snapshot()
        if (expected["requested"] != version or expected["effective"] == version or expected["activating"]
                or expected["configuration"] is None or not expected["admission_open"]):
            raise ApiError("activation_conflict",
                "Activate the requested version from a healthy effective configuration.", 409, True)
        self.provider.require_configuration_connection(expected["requested_configuration"].connection)
        seal = await self._acquire_seal(expected["effective"])
        closed = False
        starting = False
        try:
            current = self.authority.activation_snapshot()
            if current["pinned_runs"]:
                raise ApiError("harness_configuration_busy",
                    "Finish or stop the pinned runs before activating configuration.", 409, True)
            candidate = Candidate(version, self.authority.configuration(version), current["grant_epoch"])
            try:
                health = await self.lifecycle.inspect_candidate(candidate)
            except Exception:
                self.authority.validate(version, _failed_probe)
                raise
            if not self.authority.validate(version, lambda _: health):
                raise ApiError(self.authority.status()["failure_code"],
                    "The isolated configuration candidate did not pass validation.", 409, True)
            self.provider.require_configuration_connection(candidate.spec.connection)
            self.authority.close_admission(expected_effective=expected["effective"],
                requested_version=version, grant_epoch=candidate.grant_epoch)
            closed = True
            boundary = await self.lifecycle.stop_and_settle(seal)
            self.authority.activate(version, boundary, expected_effective=expected["effective"])
            starting = True
            final = await self.lifecycle.start_gated(candidate, seal=seal)
            if not isinstance(final, RegistryHealth) or not final.healthy:
                raise ApiError("candidate_unhealthy", "The fresh registry is not healthy.", 409, True)
            if final.registry_hash != candidate.spec.registry_hash:
                raise ApiError("registry_mismatch", "The fresh registry differs from the candidate.", 409, True)
            if (final.configuration_version != version or final.grant_epoch != candidate.grant_epoch):
                raise ApiError("candidate_authority_stale",
                    "The fresh registry observation is stale.", 409, True)
            self.provider.require_configuration_connection(candidate.spec.connection)
            current = self.authority.activation_snapshot()
            if (current["requested"] != version or current["effective"] != version
                    or current["activating"] != version):
                raise ApiError("activation_conflict",
                    "Configuration pointers changed during activation.", 409, True)
            self.authority.open_admission(version, registry_hash=final.registry_hash,
                grant_epoch=final.grant_epoch, expected_requested=version,
                expected_activating=version)
            seal.release()  # Synchronous/nonthrowing: ingress is the last opening step.
            self._seal = None
            starting = False
            return await self.snapshot()
        except BaseException as error:
            if starting:
                try:
                    await self.lifecycle.stop_and_settle(seal)
                except BaseException:
                    pass  # Retain seal/pointers even if the parent cannot prove settlement.
            if not isinstance(error, Exception):
                raise
            raise _lifecycle_error(error) from None
        finally:
            if not closed:
                seal.release()
                self._seal = None

    async def stage_roles(self, roles: tuple[RolePolicy, ...]) -> dict:
        return await self._mutate(lambda: self._stage_roles(roles))

    async def _stage_roles(self, roles: tuple[RolePolicy, ...]) -> dict:
        if (not isinstance(roles, tuple) or not 1 <= len(roles) <= 14
                or any(not isinstance(role, RolePolicy) for role in roles)):
            raise ApiError("configuration_invalid", "Supply one to fourteen typed role policies.")
        snapshot = self.authority.activation_snapshot()
        effective = snapshot["configuration"]
        if effective is None or not snapshot["admission_open"] or snapshot["activating"]:
            raise ApiError("configuration_not_active",
                "Activate a healthy selected connection before changing roles.", 409, True)
        self.provider.require_configuration_connection(effective.connection)
        try:
            candidate = ConfigurationSpec.model_validate_json(
                effective.model_copy(update={"roles": roles}).model_dump_json())
        except ValidationError:
            raise ApiError("configuration_invalid", "Supply allowed unique role policies.") from None
        freeze_inputs = getattr(self.lifecycle, 'freeze_inputs', None)
        if freeze_inputs is not None:
            try:
                candidate = freeze_inputs(candidate)
            except Exception as error:
                raise _lifecycle_error(error) from None
        version = self.authority.stage_if_current(candidate,
            expected_effective=snapshot['effective'], expected_requested=snapshot['requested'],
            expected_activating=snapshot['activating'], grant_epoch=snapshot['grant_epoch'])
        return {"version": version, **self.authority.status()}

    async def snapshot(self) -> dict:
        snapshot = self.authority.activation_snapshot()
        connections = self.provider.connections()
        selected = connections["selected_provider"]
        catalogue = next((row["allowed_models"] for row in connections["connections"]
                          if row["provider"] == selected), [])
        return {**{key: snapshot[key] for key in ("requested", "effective", "failed",
                    "failure_code", "admission_open", "pinned_runs")},
                "configuration": _public_configuration(snapshot["configuration"]),
                "requested_configuration": _public_configuration(
                    snapshot["requested_configuration"]),
                "catalogue": list(catalogue)}
