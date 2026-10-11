# SPDX-License-Identifier: MIT
"""Trusted, bounded model plans for already admitted canonical root operations.

The owning domain pins the native input and canonical configuration run before any
model callback. This registry allocates steps, never purposes or grants from
model arguments. Evidence/counters are explicit local trusted injections; absent
evidence denies. Gateway alone debits/sends, with a fresh owned HTTP transport.
Standalone memory-extraction is text-only and owns one primary permit. No child,
other auxiliary, retry or restart admission is provided by this module.
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
import json
import math
import sqlite3
from typing import Literal, Protocol
from uuid import uuid4

import httpx

from renulus.contracts import ApiError
from .harness_configuration import ConfigurationAuthority, RoleBinding
from .harness_deployment import (
    DeploymentBinding, DeploymentEvidence, DeploymentPreparation, HarnessDeployment, NativeManifest,
)
from .harness_domain import DomainBinding, DomainCancellation, DomainCancelled, DomainGrant, DomainRequest
from .harness_gateway import GatewayBounds, HarnessGateway
from .manager import ProviderManager
from .provider_adapter import SubscriptionRoute, subscription_route


_MESSAGE = "The admitted model operation is unavailable."
_COMMANDS = frozenset({"model.prepare", "model.manifest", "model.dispatch"})


def _deny(code):
    raise ApiError(code, _MESSAGE, 409)


def _safe(error):
    if isinstance(error, ApiError):
        raise ApiError(error.code, _MESSAGE, error.status, error.retryable) from None
    if isinstance(error, DomainCancelled):
        raise DomainCancelled("domain_cancelled") from None
    if isinstance(error, asyncio.CancelledError):
        raise error
    raise ApiError("model_registry_unavailable", _MESSAGE, 503, True) from None


def _size(value):
    try:
        return len(json.dumps(value, ensure_ascii=False, allow_nan=False,
            separators=(",", ":")).encode("utf-8"))
    except (ValueError, TypeError, RecursionError, UnicodeError):
        _deny("model_registry_payload_invalid")


def _serialized(value):
    if (not isinstance(value, dict) or set(value) != {"method", "url", "headers", "body_base64"}
            or any(not isinstance(value[key], str) for key in ("method", "url", "body_base64"))
            or not isinstance(value["headers"], dict)
            or any(not isinstance(key, str) or not isinstance(item, str)
                for key, item in value["headers"].items())):
        _deny("deployment_request_invalid")
    # Copy the flat wire envelope; never decode/recode the native HTTP JSON body.
    return {**value, "headers": dict(value["headers"])}


def _evidence_metadata(evidence):
    return {"id": evidence.id, "route": evidence.route.descriptor(),
        "limits": evidence.limits.model_dump(), "capabilities": evidence.capabilities,
        "limits_revision": evidence.limits_revision,
        "capabilities_revision": evidence.capabilities_revision,
        "counter_revision": evidence.counter_revision}


class ModelCurrent(Protocol):
    def __call__(self, *, conn: sqlite3.Connection | None = None) -> None: ...


@dataclass(frozen=True)
class ModelRunAuthority:
    binding: DomainBinding
    configuration_version: str
    purpose: str
    operation_model: str | None
    required_capabilities: tuple[str, ...]
    cancellation: DomainCancellation = field(repr=False)
    current: ModelCurrent = field(repr=False, compare=False)


@dataclass(frozen=True)
class ModelRegistryBounds:
    max_runs: int
    max_plans_per_run: int
    max_owned: int
    max_retained_bytes: int
    max_manifest_bytes: int
    max_frame_bytes: int

    def __post_init__(self):
        if any(type(value) is not int or value <= 0 for value in asdict(self).values()):
            _deny("model_registry_bounds_invalid")


@dataclass(frozen=True)
class ModelReceipt:
    dispatch_id: str
    step_id: str
    permit_id: str
    request_kind: str
    continuation_of: str | None
    body_sha256: str
    body_bytes: int
    input_tokens: int
    input_manifest_sha256: str
    evidence_id: str


@dataclass(frozen=True)
class ModelRegistryStatus:
    state: Literal["open", "closing", "settled"]
    runs: int
    plans: int
    owned: int
    retained_bytes: int
    phases: tuple[tuple[str, str, str], ...]
    receipts: tuple[ModelReceipt, ...]


@dataclass
class _Plan:
    step_id: str
    request_kind: str
    continuation_of: str | None
    reservation: int
    phase: str = "preparing"
    preparation: DeploymentPreparation | None = None
    manifest: NativeManifest | None = None
    receipt: ModelReceipt | None = None


@dataclass
class _Run:
    admission: ModelRunAuthority
    role: RoleBinding
    route: SubscriptionRoute
    plans: list[_Plan] = field(default_factory=list)
    closed: bool = False
    reservation: int = 0


class _OwnedTransport(httpx.AsyncBaseTransport):
    """Gateway may fail before opening a client; close the factory owner once."""
    def __init__(self, transport):
        self.transport = transport
        self.finalizer = None

    async def handle_async_request(self, request):
        return await self.transport.handle_async_request(request)

    async def aclose(self):
        if self.finalizer is None:
            self.finalizer = asyncio.create_task(self.transport.aclose())
        cancelled = False
        while not self.finalizer.done():
            try:
                await asyncio.shield(self.finalizer)
            except asyncio.CancelledError:
                cancelled = True
            except Exception:
                break
        if cancelled:
            if not self.finalizer.cancelled():
                self.finalizer.exception()
            raise asyncio.CancelledError
        return self.finalizer.result()


class HarnessModelRegistry:
    """One event-loop owner; current(conn) is local and returns None or raises.

resolve_run reads trusted Owner metadata; evidence is a local immutable lookup.
http_transport(route) MUST produce a fresh transport owned by that dispatch.
close/settlement observe this registry's actual workers, never native exit/pipe
settlement. Parent settles the canonical run after all native/domain work and
then calls release. Held grants stay closed after close or release.
"""
    def __init__(self, manager: ProviderManager, authority: ConfigurationAuthority, *,
                 resolve_run: Callable[[DomainBinding], ModelRunAuthority | None],
                 evidence: Callable[[SubscriptionRoute], DeploymentEvidence | None],
                 http_transport: Callable[[SubscriptionRoute], httpx.AsyncBaseTransport],
                 gateway_bounds: GatewayBounds, bounds: ModelRegistryBounds):
        if (not isinstance(manager, ProviderManager) or not isinstance(authority, ConfigurationAuthority)
                or not isinstance(bounds, ModelRegistryBounds) or not isinstance(gateway_bounds, GatewayBounds)
                or not all(callable(value) for value in (resolve_run, evidence, http_transport))):
            _deny("model_registry_authority_unbound")
        self.manager, self.authority = manager, authority
        self.resolve_run, self.evidence, self.http_transport = resolve_run, evidence, http_transport
        self.gateway_bounds, self.bounds = gateway_bounds, bounds
        self._runs: dict[DomainBinding, _Run] = {}
        self._tasks: dict[asyncio.Task, _Run] = {}
        self._closing = False
        self.deployment = HarnessDeployment(resolve=self._resolve_deployment, evidence=evidence,
            check_current=self._check_preparation, max_request_bytes=gateway_bounds.max_request_bytes)

    def _run(self, binding):
        admission = self.resolve_run(binding)
        if (not isinstance(admission, ModelRunAuthority) or admission.binding != binding
                or not isinstance(admission.cancellation, DomainCancellation) or not callable(admission.current)):
            _deny("model_registry_authority_unbound")
        run = self._runs.get(binding)
        if run is not None:
            if admission != run.admission:
                _deny("model_registry_authority_changed")
            return run
        if any(known.operation_id == binding.operation_id for known in self._runs):
            _deny("model_registry_authority_changed")
        canonical = self.authority.run(binding.operation_id)
        if len(self._runs) >= self.bounds.max_runs:
            _deny("model_registry_capacity")
        pinned = canonical["route"]
        if (canonical["state"] != "active" or admission.configuration_version != canonical["version"]
                or admission.purpose != canonical["purpose"]
                or admission.operation_model != pinned["model_id"]
                or type(admission.required_capabilities) is not tuple
                or len(set(admission.required_capabilities)) != len(admission.required_capabilities)
                or set(admission.required_capabilities) != set(canonical["effective_capabilities"])
                or not isinstance(admission.cancellation, DomainCancellation) or not callable(admission.current)):
            _deny("model_registry_authority_unbound")
        if (canonical["parent_id"] is not None or canonical["root_id"] != binding.operation_id
                or canonical["purpose"] not in {"explain", "case-discuss", "case-image-discuss", "evidence-review",
                    "memory-extraction"}):
            _deny("model_registry_kind_unavailable")
        if canonical["purpose"] == "memory-extraction" and (
                canonical["dispatch_limit"] != 1 or set(canonical["effective_capabilities"]) != {"text"}):
            _deny("model_registry_kind_unavailable")
        if canonical["spent_dispatches"]:
            _deny("model_registry_recovery_unavailable")
        spec = self.authority.configuration(canonical["version"])
        route = subscription_route(pinned["provider"], pinned["model_id"],
            credential_ref=pinned["credential_reference"], credential_epoch=pinned["credential_revision"],
            catalogue=None)
        if (pinned["endpoint"] + ("/responses" if pinned["protocol"] == "responses" else "/chat/completions")
                != route.endpoint or spec.connection.provider != route.provider_id
                or spec.connection.credential_reference != route.credential_ref
                or spec.connection.credential_revision != route.credential_epoch):
            _deny("model_registry_authority_unbound")
        role = RoleBinding(canonical["version"], canonical["purpose"], spec.connection,
            pinned["model_id"], pinned["output_tokens"], canonical["dispatch_limit"])
        run = _Run(admission, role, route)
        run.reservation = _size({"binding": asdict(binding), "role": {
            "version": role.version, "purpose": role.purpose, "model_id": role.model_id,
            "output_tokens": role.output_tokens, "dispatch_limit": role.dispatch_limit,
            "connection": role.connection.model_dump()},
            "route": route.descriptor(), "capabilities": admission.required_capabilities})
        if self.status().retained_bytes + run.reservation > self.bounds.max_retained_bytes:
            _deny("model_registry_capacity")
        self._current(run)
        self._runs[binding] = run
        return run

    def _current(self, run, *, conn=None):
        if self._closing or run.closed or run.admission.cancellation.cancelled:
            raise DomainCancelled("domain_cancelled")
        if run.admission.current(conn=conn) is not None:
            _deny("model_registry_authority_unbound")
        self.manager.require_harness_route(run.route)
        connection = run.role.connection
        current = self.authority.require_current(run.admission.binding.operation_id,
            required_capabilities=run.admission.required_capabilities, connection=connection, conn=conn)
        if current["version"] != run.role.version or current["purpose"] != run.role.purpose:
            _deny("model_registry_authority_changed")
        for plan in run.plans:
            if plan.preparation is not None and self.evidence(run.route) != plan.preparation.evidence:
                _deny("deployment_evidence_stale")
            if plan.receipt is not None:
                self.authority.require_current(run.admission.binding.operation_id,
                    required_capabilities=run.admission.required_capabilities, connection=connection,
                    permit_id=plan.receipt.permit_id, conn=conn)

    async def _resolve_deployment(self, binding):
        run = self._runs[binding]
        self._current(run)
        # Canonical admission already owns the route. Preparing it again can
        # refresh a credential over HTTP before unknown evidence is rejected.
        # Local Manager guards validate this descriptor; only Gateway resolves
        # protected credentials after proof and durable effect admission.
        return DeploymentBinding(binding, binding.operation_id, run.role, run.route)

    def _check_preparation(self, preparation):
        self._current(self._runs[preparation.binding])

    async def authorize(self, request: DomainRequest) -> DomainGrant | None:
        """Authenticate the three model callbacks; each grant handler is one-shot."""
        if request.command not in _COMMANDS:
            return None
        try:
            if self._closing:
                raise DomainCancelled("domain_cancelled")
            run = self._run(request.binding)
            self._current(run)
        except Exception as error:
            _safe(error)

        def check():
            try:
                self._current(run)
                return True
            except Exception as error:
                _safe(error)

        claimed = False

        async def handle(actual, cancellation):
            nonlocal claimed
            if actual != request:
                _deny("model_registry_callback_unbound")
            check()
            cancellation.check_current()
            if claimed:
                _deny("model_registry_callback_consumed")
            if len(self._tasks) >= self.bounds.max_owned:
                _deny("model_registry_capacity")
            claimed = True
            task = asyncio.create_task(self._handle(run, actual, cancellation))
            self._tasks[task] = run
            task.add_done_callback(self._settled_task)
            cancelled = False
            while not task.done():
                try:
                    await asyncio.shield(task)
                except asyncio.CancelledError:
                    cancelled = True
                    cancellation.cancel()
                except Exception:
                    break
            self._settled_task(task)
            if cancelled:
                if not task.cancelled():
                    task.exception()
                raise asyncio.CancelledError
            return task.result()

        return DomainGrant(request.binding, handle, check, run.admission.cancellation)

    def _discard_idle_plans(self, run):
        if self._closing and not any(owner is run for owner in self._tasks.values()):
            for plan in run.plans:
                if plan.phase in {"prepared", "manifest_registered"}:
                    plan.phase = "cancelled"
                    self._discard_payload(plan)

    def _settled_task(self, task):
        run = self._tasks.pop(task, None)
        if run is not None:
            self._discard_idle_plans(run)

    async def _handle(self, run, request, cancellation):
        owned_plan = None
        try:
            self._current(run)
            cancellation.check_current()
            if request.command == "model.prepare":
                if request.payload:
                    _deny("model_registry_payload_invalid")
                if run.plans and run.plans[-1].phase != "confirmed":
                    _deny("model_registry_phase_invalid")
                if len(run.plans) >= min(self.bounds.max_plans_per_run, run.role.dispatch_limit):
                    _deny("model_registry_capacity")
                reservation = (self.gateway_bounds.max_request_bytes + self.bounds.max_manifest_bytes
                    + self.gateway_bounds.max_response_bytes + 2 * self.bounds.max_frame_bytes)
                if self.status().retained_bytes + reservation > self.bounds.max_retained_bytes:
                    _deny("model_registry_capacity")
                previous = run.plans[-1].receipt if run.plans else None
                plan = _Plan(uuid4().hex, "tool-continuation" if previous else "primary",
                    previous.permit_id if previous else None, reservation)
                run.plans.append(plan)
                owned_plan = plan
                prepared = await self.deployment.prepare(request.binding,
                    required_capabilities=run.admission.required_capabilities)
                evidence_bytes = _size(_evidence_metadata(prepared.evidence))
                if self.status().retained_bytes + evidence_bytes > self.bounds.max_retained_bytes:
                    _deny("model_registry_capacity")
                plan.reservation += evidence_bytes
                plan.preparation = prepared
                self._current(run)
                cancellation.check_current()
                result = {"dispatch_id": prepared.id, "binding": asdict(request.binding),
                    "role": {"version": run.role.version, "purpose": run.role.purpose,
                        "model_id": run.role.model_id, "output_tokens": prepared.output_tokens,
                        "dispatch_limit": run.role.dispatch_limit}, "request_kind": plan.request_kind,
                    "route": run.route.descriptor(), "native_capabilities": {
                        "tools": "tools" in prepared.required_capabilities,
                        "input": [value for value in ("text", "image") if value in prepared.required_capabilities],
                        "output": ["text"]}, "limits": prepared.limits.model_dump(),
                    "required_capabilities": list(prepared.required_capabilities), "bounds": {
                        "max_request_bytes": self.gateway_bounds.max_request_bytes,
                        "max_response_bytes": self.gateway_bounds.max_response_bytes,
                        "max_frame_bytes": self.bounds.max_frame_bytes}}
                if plan.continuation_of is not None:
                    result["continuation_of"] = plan.continuation_of
                if _size(result) > self.bounds.max_frame_bytes:
                    _deny("model_registry_capacity")
                plan.phase = "prepared"
                return result
            if not run.plans:
                _deny("model_registry_phase_invalid")
            plan = run.plans[-1]
            if request.command == "model.manifest":
                if set(request.payload) != {"manifest"} or plan.phase != "prepared":
                    _deny("model_registry_phase_invalid")
                if _size(request.payload["manifest"]) > self.bounds.max_manifest_bytes:
                    _deny("model_registry_capacity")
                plan.manifest = NativeManifest.from_payload(request.payload["manifest"])
                plan.phase = "manifest_registered"
                return {"registered": True}
            if (set(request.payload) != {"dispatch_id", "serialized_request"}
                    or plan.phase != "manifest_registered"
                    or request.payload["dispatch_id"] != plan.preparation.id):
                _deny("model_registry_phase_invalid")
            owned_plan = plan
            plan.phase = "proving"
            if _size(request.payload) > self.bounds.max_frame_bytes:
                _deny("model_registry_capacity")
            serialized = _serialized(request.payload["serialized_request"])
            proof = await self.deployment.prove(plan.preparation, step_id=plan.step_id,
                request_kind=plan.request_kind, serialized_request=serialized, manifest=plan.manifest,
                continuation_of=plan.continuation_of)

            def guard():
                cancellation.check_current()
                self.deployment.require_current(proof, body=proof.body)
                return True

            guard()
            transport = self.http_transport(run.route)
            if not isinstance(transport, httpx.AsyncBaseTransport):
                _deny("model_registry_transport_unbound")
            # Stamp the factory owner itself: no unbounded lifetime registry of
            # disposed transports, including when external callers retain them.
            if getattr(transport, "_renulus_model_dispatch_owned", False):
                _deny("model_registry_transport_reused")
            transport._renulus_model_dispatch_owned = True
            transport = _OwnedTransport(transport)
            gateway = HarnessGateway(self.manager, self.authority, cancellation=cancellation,
                check_current=guard, http_transport=transport, bounds=self.gateway_bounds)
            plan.phase = "sending"
            try:
                result = await gateway.dispatch(request.binding.operation_id, plan.step_id, run.route, serialized,
                    limits=plan.preparation.limits, input_tokens=proof.input_tokens,
                    required_capabilities=run.admission.required_capabilities, request_kind=plan.request_kind,
                    continuation_of=plan.continuation_of)
            finally:
                await transport.aclose()
            plan.receipt = ModelReceipt(plan.preparation.id, plan.step_id, result["permit_id"],
                plan.request_kind, plan.continuation_of, proof.body_sha256, proof.body_bytes,
                proof.input_tokens, proof.input_manifest_sha256, plan.preparation.evidence_id)
            self._current(run)
            cancellation.check_current()
            if _size(result) > self.bounds.max_frame_bytes:
                _deny("model_registry_capacity")
            plan.phase = "confirmed"
            self._discard_payload(plan)
            return result
        except BaseException as error:
            if owned_plan is not None and owned_plan.phase in {"preparing", "proving", "sending"}:
                owned_plan.phase = "cancelled" if isinstance(error,
                    (DomainCancelled, asyncio.CancelledError)) else "failed"
                self._discard_payload(owned_plan)
            _safe(error)

    def _discard_payload(self, plan):
        plan.manifest = None
        evidence = plan.preparation.evidence if plan.preparation else None
        plan.reservation = _size({"step_id": plan.step_id, "request_kind": plan.request_kind,
            "continuation_of": plan.continuation_of, "phase": plan.phase,
            "dispatch_id": plan.preparation.id if plan.preparation else None,
            "receipt": asdict(plan.receipt) if plan.receipt else None,
            "evidence": _evidence_metadata(evidence) if evidence else None})

    def require_publication(self, binding: DomainBinding, *, conn: sqlite3.Connection) -> None:
        """Guard every consumed permit in the caller's local commit transaction."""
        try:
            run = self._runs.get(binding)
            if run is None:
                _deny("model_registry_authority_unbound")
            self._current(run, conn=conn)
            if not run.plans or any(plan.phase != "confirmed" for plan in run.plans):
                _deny("model_registry_publication_pending")
        except Exception as error:
            _safe(error)

    def cancel(self, binding: DomainBinding) -> None:
        try:
            run = self._runs.get(binding)
            admission = run.admission if run is not None else self.resolve_run(binding)
            if (not isinstance(admission, ModelRunAuthority) or admission.binding != binding
                    or not isinstance(admission.cancellation, DomainCancellation)):
                _deny("model_registry_authority_unbound")
            admission.cancellation.cancel()
        except Exception as error:
            _safe(error)

    def status(self, binding: DomainBinding | None = None) -> ModelRegistryStatus:
        """Immutable observation only; filtered state still describes global close."""
        runs = list(self._runs.values()) if binding is None else (
            [self._runs[binding]] if binding in self._runs else [])
        plans = [plan for run in runs for plan in run.plans]
        owned = len(self._tasks) if binding is None else sum(
            any(owner is run for run in runs) for owner in self._tasks.values())
        return ModelRegistryStatus("settled" if self._closing and not self._tasks else
            "closing" if self._closing else "open", len(runs), len(plans), owned,
            sum(run.reservation for run in runs) + sum(plan.reservation for plan in plans),
            tuple((run.admission.binding.operation_id,
                plan.preparation.id if plan.preparation else plan.step_id, plan.phase)
                for run in runs for plan in run.plans),
            tuple(plan.receipt for plan in plans if plan.receipt is not None))

    async def settlement(self, timeout: float) -> ModelRegistryStatus:
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 <= timeout <= 300:
            _deny("model_registry_timeout_invalid")
        if self._tasks:
            await asyncio.wait(tuple(self._tasks), timeout=timeout)
        return self.status()

    async def close(self, timeout: float) -> ModelRegistryStatus:
        self._closing = True
        for run in self._runs.values():
            run.admission.cancellation.cancel()
            self._discard_idle_plans(run)
        return await self.settlement(timeout)

    def release(self, binding: DomainBinding) -> None:
        """Discard receipts after parent settlement; held grants remain closed."""
        try:
            run = self._runs.get(binding)
            if run is None:
                _deny("model_registry_authority_unbound")
            if run in self._tasks.values() or self.authority.run(binding.operation_id)["state"] != "settled":
                _deny("model_registry_settlement_pending")
            run.closed = True
            del self._runs[binding]
        except Exception as error:
            _safe(error)
