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
        """Return/raise only after isolated closed inspection AND candidate settlement."""
        ...

    async def seal_new_runs(self, *, expected_effective: str | None) -> NewRunSeal: ...

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


class HarnessConfigurationController:
    """One profile-owned instance; cancelled observers do not abandon mutations.

    Post-close failures retain the seal and canonical pointers. Managed startup
    reconciliation or a future settled CAS rollback belongs to the parent; this
    instance refuses subsequent mutations while recovery is required.
    """
    def __init__(self, authority: ConfigurationAuthority, provider: ConfigurationProvider,
                 lifecycle: ConfigurationLifecycle):
        self.authority = authority
        self.provider = provider
        self.lifecycle = lifecycle
        self._seal: NewRunSeal | None = None
        self._mutation_lock = asyncio.Lock()
        self._mutations: set[asyncio.Task] = set()

    async def activate(self, version: str) -> dict:
        return await self._mutate(lambda: self._activate(version))

    async def _mutate(self, operation: Callable[[], Awaitable[dict]]) -> dict:
        async def own_mutation():
            async with self._mutation_lock:
                if self._seal is not None:
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

    async def _activate(self, version: str) -> dict:
        expected = self.authority.activation_snapshot()
        if (expected["requested"] != version or expected["effective"] == version or expected["activating"]
                or expected["configuration"] is None or not expected["admission_open"]):
            raise ApiError("activation_conflict",
                "Activate the requested version from a healthy effective configuration.", 409, True)
        self.provider.require_configuration_connection(expected["requested_configuration"].connection)
        seal = await self.lifecycle.seal_new_runs(expected_effective=expected["effective"])
        self._seal = seal
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
                grant_epoch=final.grant_epoch)
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
            if not isinstance(error, Exception) or isinstance(error, ApiError):
                raise
            raise ApiError("harness_configuration_lifecycle_failed",
                "The managed configuration lifecycle did not finish safely.", 503, True) from None
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
        version = self.authority.stage(candidate)
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
