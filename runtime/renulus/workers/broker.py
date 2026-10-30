"""Protected HTTP execution inside the owned Python worker; no admission owner.

Integration:
* TS commits final admission, then sends TransportPlan on authenticated inherited
  worker pipes. Mandatory check_current checks the worker envelope before send,
  during idle I/O, and before returning. TS must also recheck before publication.
* Create an operation-bound BrokerLaunch/ProtectedBroker with the exact native
  manifest and registry hashes; share ONE explicitly activated ProviderManager
  across scopes. No per-request process or Node credential read is needed.
* Process-wide, bounded tombstones survive scope close/reopen; never evict them.
  They contain no body/credential. After process death TS's durable dispatched /
  uncertain receipts MUST refuse resend; in-memory tombstones cannot do that.
* execute[_sync] returns TransportExecution(result, body). body is bounded RAM
  and is only for worker artifact staging, NEVER a JSON reply/log/disk payload.
  Reserve plan.output before execute. Stage raw bytes only after current checks,
  mark the existing artifact complete, and return result metadata. Revoke/release
  retains the reservation until HTTP and staging have actually settled.

No Services, Database, ConfigurationAuthority, route choice, native serializer,
automatic token refresh, retry, redirect, proxy/environment auth or fallback.
"""
from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass, field
import hashlib
import math
from pathlib import Path
import re
from threading import Event, RLock
import time
from typing import Callable
from urllib.parse import urlsplit

import httpx

from renulus.contracts import ApiError
from renulus.runtime.harness_configuration import RouteLimits
from renulus.runtime.harness_gateway import (GatewayBounds, HarnessGateway,
    _invalid_constant, _sse_failure, _unique_object)
from renulus.runtime.manager import ProviderManager
from renulus.runtime.policy import ALLOWED_MODELS
from renulus.runtime.provider_adapter import PATHS, SubscriptionRoute, subscription_route
from renulus.worker_contracts import payload_digest
from .contract_base import ArtifactResult, Revisions
from .broker_models import (BrokerLaunch, CredentialAuthority, CredentialMetadata, CredentialResult,
    EvidencePlan, HttpPlan, HttpResult, TransportPlan, TransportResult, TransportRoute)


class BrokerRefused(Exception):
    """Closed public error codes only; never retain an underlying HTTP exception."""
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class TransportExecution:
    result: TransportResult | HttpResult
    body: bytes = field(default=b"", repr=False)


@dataclass
class _Attempt:
    scope: object
    cancel: Event = field(default_factory=Event)
    started: bool = False
    requests: int = 0
    settled: bool = False
    result: TransportResult | HttpResult | None = None


@dataclass
class _Process:
    profile: str
    state: str
    retention: str
    revisions: Revisions
    capacity: int
    attempts: dict[str, _Attempt] = field(default_factory=dict)
    credential_authorities: set[str] = field(default_factory=set)
    lock: RLock = field(default_factory=RLock)


_PROCESSES: dict[tuple, _Process] = {}
_PROCESS_LOCK = RLock()


def _deny(code):
    raise BrokerRefused(code)


def _loopback(endpoint: str) -> bool:
    try:
        url = urlsplit(endpoint)
        return (url.scheme == "http" and url.hostname == "127.0.0.1"
            and url.netloc == "127.0.0.1:" + str(url.port)
            and url.port is not None and 0 < url.port < 65536
            and url.path in ("/responses", "/chat/completions")
            and not url.query and not url.fragment)
    except ValueError:
        return False


class ProtectedBroker:
    def __init__(self, launch: BrokerLaunch, *, manager: ProviderManager | None = None,
                 synthetic_transport: httpx.AsyncBaseTransport | None = None):
        if not isinstance(launch, BrokerLaunch):
            _deny("broker_launch_invalid")
        profile, state = Path(launch.profile_root), Path(launch.state_root)
        if (not profile.is_absolute() or not state.is_absolute()
                or not state.resolve().is_relative_to(profile.resolve())
                or any(not _loopback(url) for url in launch.synthetic_endpoints)
                or len(set(launch.synthetic_endpoints)) != len(launch.synthetic_endpoints)
                or synthetic_transport is not None and not launch.synthetic_endpoints):
            _deny("broker_launch_invalid")
        if manager is not None and (not isinstance(manager, ProviderManager)
                or manager.store.profile != profile.resolve()
                or manager.store.path.resolve() != (state / "runtime" / "connections.dpapi").resolve()):
            _deny("broker_namespace_mismatch")
        self.launch, self.manager = launch, manager
        self.synthetic_transport = synthetic_transport
        self.closed = False
        self.credential_leases = []
        self._scope = object()
        # Identity includes profile/store/authority/process. Across a process
        # restart TS must issue a NEW generation and retain durable old debits.
        key = tuple(launch.identity.model_dump().values())
        with _PROCESS_LOCK:
            process = _PROCESSES.get(key)
            if process is None:
                process = _Process(str(profile.resolve()), str(state.resolve()), launch.retention,
                    launch.revisions, launch.bounds.permit_count)
                _PROCESSES[key] = process
            elif (process.profile != str(profile.resolve()) or process.state != str(state.resolve())
                    or process.retention != launch.retention or process.revisions != launch.revisions
                    or process.capacity != launch.bounds.permit_count):
                _deny("broker_launch_mismatch")
            self._process = process
        # Existing maintained validators only. No legacy dispatch/admit method
        # is called and no ConfigurationAuthority is constructed.
        self.bounds = GatewayBounds(launch.bounds.max_request_bytes,
            launch.bounds.max_response_bytes, launch.bounds.timeout_seconds)

    def activate_credentials(self, *, check_current: Callable[[], bool]) -> ProviderManager:
        """Explicit worker activation; __init__ never opens a connection record.

        Reuse the returned manager for every operation scope. The source root
        comes from the installed module, never the environment or a model plan;
        existing direct login/catalog primitives may need attributed Hermes
        request-header helpers. They are not invoked by transport execution.
        """
        try:
            if self.closed or not callable(check_current) or check_current() is not True:
                _deny("broker_authority_unbound")
        except BrokerRefused:
            raise
        except Exception:
            raise BrokerRefused("broker_authority_unbound") from None
        if self.manager is None:
            from types import SimpleNamespace
            self.manager = ProviderManager(SimpleNamespace(root=Path(self.launch.profile_root),
                state=Path(self.launch.state_root), source_root=Path(__file__).resolve().parents[3]))
        return self.manager

    def _manager(self):
        if self.manager is None:
            _deny("broker_not_activated")
        return self.manager

    def _credential(self, route: TransportRoute) -> str:
        # Deliberately do NOT call credential_for_harness/_access_token: these
        # can refresh. This narrow seam reads the existing DPAPI-backed record
        # and compares its persisted identity; it never selects or saves.
        manager = self._manager()
        provider = route.provider_id
        if (manager._credential_refs[provider] != route.credential_ref
                or manager._credential_epochs[provider] != route.credential_revision):
            _deny("credential_changed")
        record = manager._settings["connections"].get(provider)
        if not isinstance(record, dict) or manager._catalog_errors.get(provider) == "authentication_required":
            _deny("authentication_required")
        token = record.get("access_token")
        if not isinstance(token, str) or not re.fullmatch(r"[\x21-\x7e]{1,8192}", token):
            _deny("authentication_required")
        expiry = record.get("expires_at")
        if provider == "codex" and (type(expiry) not in (int, float)
                or not math.isfinite(expiry) or expiry <= time.time() + 60):
            _deny("authentication_required")
        return token

    def _current(self, plan, attempt, check_current, external_cancel):
        self._alive(plan, attempt, check_current, external_cancel)
        self._credential(plan.route)

    def _alive(self, plan, attempt, check_current, external_cancel):
        if self.closed or attempt.cancel.is_set() or external_cancel is not None and external_cancel.is_set():
            _deny("transport_cancelled")
        if check_current is None:
            _deny("broker_authority_unbound")
        try:
            current = check_current()
        except Exception:
            _deny("broker_authority_unbound")
        if current is not True:
            _deny("stale_revision")
        with self._process.lock:
            if plan.revisions != self._process.revisions:
                _deny("stale_revision")
        if (plan.expires_at_ms <= int(time.time() * 1000)
                or plan.output.expires_at_ms <= int(time.time() * 1000)):
            _deny("transport_expired")

    def _validate(self, plan):
        launch = self.launch
        if (any(getattr(plan.identity, name) != value for name, value in launch.identity.model_dump().items())
                or plan.retention != launch.retention
                or plan.native_manifest_sha256 != launch.native_manifest_sha256
                or plan.registry_sha256 != launch.registry_sha256):
            _deny("transport_binding_mismatch")
        route = plan.route
        if route.model_id not in ALLOWED_MODELS[route.provider_id] or route.wire_model_id != route.model_id:
            _deny("transport_route_invalid")
        canonical = subscription_route(route.provider_id, route.model_id,
            credential_ref=route.credential_ref, credential_epoch=route.credential_revision, catalogue=None)
        synthetic = route.endpoint in launch.synthetic_endpoints
        if (route.protocol != canonical.protocol or route.endpoint != canonical.endpoint and not synthetic
                or synthetic and urlsplit(route.endpoint).path != PATHS[route.provider_id]
                or self.synthetic_transport is not None and not synthetic):
            _deny("transport_route_invalid")
        request = plan.serialized_request
        # Keep duplicate headers visible until the maintained validator rejects
        # them; constructing a dict first would silently collapse duplicates.
        if len({header.name.lower() for header in request.headers}) != len(request.headers):
            _deny("gateway_invalid_request")
        envelope = {"method": request.method, "url": request.url,
            "headers": {header.name: header.value for header in request.headers},
            "body_base64": request.body_base64}
        if payload_digest(envelope) != plan.envelope_sha256:
            _deny("transport_digest_mismatch")
        selected = SubscriptionRoute(route.provider_id, route.model_id, route.wire_model_id,
            route.endpoint, route.protocol, route.credential_ref, route.credential_revision, None)
        body, headers = HarnessGateway._envelope(self, selected, envelope)
        if len(body) != plan.request_bytes or hashlib.sha256(body).hexdigest() != plan.request_sha256:
            _deny("transport_digest_mismatch")
        # The legacy validator rejects explicit Infinity/NaN. Also reject
        # finite-looking exponent overflow, e.g. temperature:1e999.
        import json
        def finite_float(value):
            parsed = float(value)
            if not math.isfinite(parsed):
                raise ValueError("nonfinite JSON")
            return parsed
        try:
            json.loads(body.decode("utf-8"), object_pairs_hook=_unique_object,
                parse_constant=_invalid_constant, parse_float=finite_float)
        except (ValueError, UnicodeError, RecursionError):
            _deny("gateway_invalid_request")
        codex = route.provider_id == "codex"
        suffix = "/responses" if codex else "/chat/completions"
        current = {"route": {"model_id": route.model_id, "endpoint": route.endpoint[:-len(suffix)],
            "protocol": "responses" if codex else "chat-completions",
            "output_tokens": plan.max_output_tokens}}
        HarnessGateway._wire(self, selected, body, current,
            RouteLimits(input_tokens=1, output_tokens=plan.max_output_tokens,
                window_tokens=plan.max_output_tokens + 1))
        # A response must fit its already-reserved artifact. Native serialization
        # stays byte-for-byte unchanged; Python only adds fixed auth headers.
        return body, headers

    def _result(self, plan, attempt, *, outcome, effect, code=None, status=None, body=b""):
        artifact = (ArtifactResult(artifact_handle=plan.output.artifact_handle,
            artifact_revision=plan.output.artifact_revision, artifact_sha256=hashlib.sha256(body).hexdigest(),
            bytes=len(body), engine="protected-http:1", pages=None, next_cursor=None)
            if outcome == "committed_reference" else None)
        result = TransportResult(admission_receipt=plan.admission_receipt, identity=plan.identity,
            revisions=plan.revisions, request_sha256=plan.request_sha256, outcome=outcome,
            effect=effect, network_started=attempt.started, code=code, http_status=status,
            content_type="text/event-stream" if artifact else None, artifact=artifact)
        return TransportExecution(result, body if artifact else b"")

    async def _http(self, plan, attempt, body, headers, check_current, cancel):
        if self.synthetic_transport is not None:
            return await self._http_request(plan, attempt, body, headers, check_current, cancel)
        from .transport_guard import endpoint_network
        # The validated exact route is the only remote socket authority in this
        # worker. Keep it through actual HTTP cleanup; engine lanes stay offline.
        async with endpoint_network(plan.route.endpoint):
            return await self._http_request(plan, attempt, body, headers, check_current, cancel)

    async def _http_request(self, plan, attempt, body, headers, check_current, cancel):
        credential = self._credential(plan.route)
        transport = self.synthetic_transport or httpx.AsyncHTTPTransport(retries=0, trust_env=False)
        async with httpx.AsyncClient(transport=transport, trust_env=False, follow_redirects=False,
                timeout=self.launch.bounds.timeout_seconds) as client:
            request = httpx.Request("POST", plan.route.endpoint, content=body, headers={
                "content-type": "application/json", "accept": "text/event-stream",
                "accept-encoding": "identity", "user-agent": "Renulus/0.1.0",
                "authorization": "Bearer " + credential, **headers})
            self._current(plan, attempt, check_current, cancel)
            # Mark before the await: even connect/header exceptions may leave a
            # remote effect. No error path can return this permit to unused.
            with self._process.lock:
                if attempt.cancel.is_set() or plan.revisions != self._process.revisions:
                    _deny("stale_revision")
                attempt.started = True
            response = await client.send(request, stream=True)
            try:
                status = response.status_code
                if 300 <= status < 400:
                    _deny("transport_redirect_refused")
                if status != 200:
                    return self._result(plan, attempt, outcome="cancelled_settled", effect="response_received",
                        code="authentication_required" if status in (401, 403) else
                        "subscription_limit" if status == 429 else "transport_http_error", status=status)
                if (response.headers.get("content-encoding", "identity") != "identity"
                        or response.headers.get("content-type", "").split(";")[0].strip().lower() != "text/event-stream"):
                    _deny("gateway_invalid_response")
                payload = bytearray()
                # Raw bounded reads avoid implicit decompression. Idle reads and
                # headers are also guarded by execute's independent control loop.
                async for chunk in response.aiter_raw(chunk_size=16384):
                    self._current(plan, attempt, check_current, cancel)
                    if len(payload) + len(chunk) > min(self.bounds.max_response_bytes, plan.output.max_bytes):
                        _deny("gateway_response_too_large")
                    payload.extend(chunk)
            finally:
                await response.aclose()
        self._current(plan, attempt, check_current, cancel)
        # Suppress the entire artifact on raw, escaped JSON, base64 or split-SSE
        # credential echo. No secret-bearing partial stream reaches the host.
        if credential.encode() in payload or base64.b64encode(credential.encode()) in payload:
            _deny("gateway_credential_echo")
        failed, _ = _sse_failure(payload, credential, require_data=True)
        if failed:
            _deny("transport_stream_error")
        return self._result(plan, attempt, outcome="committed_reference", effect="response_received",
                            status=200, body=bytes(payload))

    async def execute(self, plan: TransportPlan, *, check_current: Callable[[], bool],
                      cancel: Event | None = None) -> TransportExecution:
        """Exactly one possible send, retaining ownership through actual cleanup.

        Caller task cancellation is converted to a settled tagged result after
        HTTP finalizers return. Even repeated cancellation cannot abandon them.
        check_current is mandatory, including synthetic tests; no permissive
        default. The worker must bind it to its admitted command/revision lease.
        """
        if not isinstance(plan, TransportPlan):
            _deny("transport_plan_invalid")
        attempt = _Attempt(self._scope)
        key = hashlib.sha256(plan.permit_id.encode("ascii")).hexdigest()
        with self._process.lock:
            if key in self._process.attempts:
                return self._result(plan, attempt, outcome="rejected_before_admission", effect="not_sent",
                                    code="transport_permit_replayed")
            if len(self._process.attempts) >= self._process.capacity:
                return self._result(plan, attempt, outcome="rejected_before_admission", effect="not_sent",
                                    code="transport_capacity")
            self._process.attempts[key] = attempt
        worker = None
        stopped = None
        execution = None
        try:
            body, headers = self._validate(plan)
            self._current(plan, attempt, check_current, cancel)
            worker = asyncio.create_task(self._http(plan, attempt, body, headers, check_current, cancel))
            deadline = asyncio.get_running_loop().time() + self.launch.bounds.timeout_seconds
            while not worker.done():
                try:
                    await asyncio.wait({worker}, timeout=0.02)
                    if stopped is None:
                        self._current(plan, attempt, check_current, cancel)
                        if asyncio.get_running_loop().time() >= deadline:
                            _deny("transport_timeout")
                except (Exception, asyncio.CancelledError) as error:
                    if stopped is None:
                        stopped = error.code if isinstance(error, BrokerRefused) else "transport_cancelled"
                        attempt.cancel.set()
                        worker.cancel()  # Once. Repeated caller cancellation cannot cancel finalizers.
            if stopped is not None:
                # Retrieve exceptions without retaining raw transport/request data.
                try:
                    worker.result()
                except BaseException:
                    pass
                _deny(stopped)
            execution = worker.result()
            self._current(plan, attempt, check_current, cancel)
        except (Exception, asyncio.CancelledError) as error:
            code = error.code if isinstance(error, BrokerRefused) else (
                error.code if isinstance(error, ApiError) and error.code in {
                    "gateway_invalid_request", "gateway_request_too_large", "gateway_route_mismatch",
                    "gateway_invalid_response", "gateway_response_too_large", "gateway_credential_echo"}
                else "transport_cancelled" if isinstance(error, asyncio.CancelledError) else "transport_failed")
            execution = self._result(plan, attempt,
                outcome="rejected_before_admission" if not attempt.started else
                    "cancelled_settled" if code in {"transport_cancelled", "stale_revision"} else
                    "uncertain_after_disconnect",
                effect="uncertain" if attempt.started else "not_sent", code=code)
        with self._process.lock:
            attempt.settled = True
            attempt.result = execution.result
        return execution

    async def _capability(self, plan, check_current, cancel, endpoints, max_bytes, operation, credential=None):
        from .capability_transport import CapabilityTransport, CapabilityTransportError, NetworkLease
        from .evidence import Failure
        attempt = _Attempt(self._scope)

        def result(outcome, effect, code=None, body=b"", status=None, headers=()):
            artifact = (ArtifactResult(artifact_handle=plan.output.artifact_handle,
                artifact_revision=plan.output.artifact_revision, artifact_sha256=hashlib.sha256(body).hexdigest(),
                bytes=len(body), engine="protected-http:1", pages=None, next_cursor=None)
                if outcome == "committed_reference" else None)
            return TransportExecution(HttpResult(admission_receipt=plan.admission_receipt,
                identity=plan.identity, revisions=plan.revisions, outcome=outcome, effect=effect,
                network_started=attempt.started, requests_started=attempt.requests, code=code,
                http_status=status, headers=headers, artifact=artifact), body if artifact else b"")

        key = hashlib.sha256(plan.permit_id.encode("ascii")).hexdigest()
        with self._process.lock:
            if key in self._process.attempts:
                return result("rejected_before_admission", "not_sent", "transport_permit_replayed")
            if len(self._process.attempts) >= self._process.capacity:
                return result("rejected_before_admission", "not_sent", "transport_capacity")
            self._process.attempts[key] = attempt
        stopped = None
        try:
            if (any(getattr(plan.identity, name) != value for name, value in self.launch.identity.model_dump().items())
                    or plan.retention != self.launch.retention):
                _deny("transport_binding_mismatch")
            self._alive(plan, attempt, check_current, cancel)

            async def current(_lease, _count):
                self._alive(plan, attempt, check_current, cancel)
                return True

            async def run():
                transport = CapabilityTransport(NetworkLease(plan.admission_receipt, endpoints,
                    plan.expires_at_ms, max_bytes), current=current, credential=credential)
                try:
                    return await operation(transport, attempt)
                finally:
                    await transport.close()

            worker = asyncio.create_task(run())
            deadline = asyncio.get_running_loop().time() + self.launch.bounds.timeout_seconds
            while not worker.done():
                try:
                    await asyncio.wait({worker}, timeout=0.02)
                    if stopped is None:
                        self._alive(plan, attempt, check_current, cancel)
                        if asyncio.get_running_loop().time() >= deadline:
                            _deny("transport_timeout")
                except (Exception, asyncio.CancelledError) as error:
                    if stopped is None:
                        stopped = error.code if isinstance(error, BrokerRefused) else "transport_cancelled"
                        attempt.cancel.set()
                        worker.cancel()
            if stopped is not None:
                try:
                    worker.result()
                except BaseException:
                    pass
                _deny(stopped)
            body, status, headers = worker.result()
            self._alive(plan, attempt, check_current, cancel)
            if len(body) > plan.output.max_bytes:
                raise Failure("capability_response_limit", True)
            execution = result("committed_reference", "response_received" if attempt.started else "not_sent",
                body=body, status=status, headers=headers)
        except (Exception, asyncio.CancelledError) as error:
            code = (error.code if isinstance(error, (BrokerRefused, Failure)) else
                str(error) if isinstance(error, CapabilityTransportError) else
                "transport_cancelled" if isinstance(error, asyncio.CancelledError) else "transport_failed")
            answered = isinstance(error, Failure) and error.answered
            execution = result("cancelled_settled" if answered else
                "uncertain_after_disconnect" if attempt.started else "rejected_before_admission",
                "response_received" if answered else "uncertain" if attempt.started else "not_sent", code)
        with self._process.lock:
            attempt.settled = True
            attempt.result = execution.result
        return execution

    async def execute_http(self, plan: HttpPlan, *, check_current: Callable[[], bool],
                           cancel: Event | None = None) -> TransportExecution:
        from .broker_models import HttpHeader
        from .capability_transport import Endpoint, CapabilityTransportError
        body = base64.b64decode(plan.body_base64, validate=True)

        async def operation(transport, attempt):
            self._alive(plan, attempt, check_current, cancel)
            attempt.started = True
            attempt.requests = 1
            credential = plan.credential
            stream = await transport.http(url=plan.url, method=plan.method,
                headers={h.name: h.value for h in plan.headers}, body=body, body_sha256=plan.body_sha256,
                credential_ref=credential.ref if credential else None,
                credential_revision=credential.revision if credential else None)
            try:
                payload = bytearray()
                while (chunk := await stream.read()) is not None:
                    if len(payload) + len(chunk) > min(plan.max_response_bytes, plan.output.max_bytes):
                        raise CapabilityTransportError("capability_response_limit")
                    payload.extend(chunk)
                return bytes(payload), stream.status, tuple(HttpHeader(name=k, value=v) for k, v in stream.headers.items())
            finally:
                await stream.close()

        return await self._capability(plan, check_current, cancel,
            tuple(Endpoint(e.host, e.port, e.private_network) for e in plan.endpoints),
            plan.max_response_bytes + len(body) + 65536, operation)

    async def execute_evidence(self, plan: EvidencePlan, *, check_current: Callable[[], bool],
                               cancel: Event | None = None) -> TransportExecution:
        from . import evidence
        from .capability_transport import Endpoint

        async def operation(transport, attempt):
            body = await evidence.run(plan, transport, attempt, self.launch.profile_root, self.launch.state_root)
            return body, None, ()

        endpoint = plan.endpoint
        endpoints = (Endpoint(endpoint.host, endpoint.port, endpoint.private_network),) if endpoint else (
            Endpoint(evidence.OFFICIAL["europe-pmc"][0], 443),)
        return await self._capability(plan, check_current, cancel, endpoints,
            evidence.ARTICLE_BYTES * max(1, plan.max_requests) + 1024 * 1024, operation,
            credential=evidence.credential_callback(self.launch.profile_root, self.launch.state_root, plan))

    def execute_sync(self, plan: TransportPlan, *, check_current: Callable[[], bool],
                     cancel: Event | None = None) -> TransportExecution:
        """Worker thread adapter. Call execute directly when already in asyncio."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.execute(plan, check_current=check_current, cancel=cancel))
        _deny("broker_sync_in_async_loop")

    def cancel(self, permit_id: str) -> bool:
        """Signal only. True is NOT settlement; query/original reply establishes it."""
        key = hashlib.sha256(permit_id.encode("ascii")).hexdigest()
        with self._process.lock:
            attempt = self._process.attempts.get(key)
            if attempt is None or attempt.scope is not self._scope:
                return False
            attempt.cancel.set()
            return True

    def query(self, permit_id: str) -> TransportResult | None:
        """None while pending/unknown. Never infer settlement from a Stop ACK."""
        key = hashlib.sha256(permit_id.encode("ascii")).hexdigest()
        with self._process.lock:
            attempt = self._process.attempts.get(key)
            return attempt.result if attempt is not None else None

    def revoke(self, revisions: Revisions) -> None:
        """Apply host-committed monotonic revisions; Python does not choose them."""
        with self._process.lock:
            if not isinstance(revisions, Revisions) or any(getattr(revisions, key) < value
                    for key, value in self._process.revisions.model_dump().items()):
                _deny("stale_revision")
            if revisions != self._process.revisions:
                self._process.revisions = revisions
                for lease in self.credential_leases:
                    lease.revoked.set()
                for attempt in self._process.attempts.values():
                    if not attempt.settled:
                        attempt.cancel.set()

    def close(self) -> None:
        """Close this operation scope. Keep process tombstones and shared manager."""
        self.closed = True
        for lease in self.credential_leases:
            lease.revoked.set()
        with self._process.lock:
            for attempt in self._process.attempts.values():
                if attempt.scope is self._scope and not attempt.settled:
                    attempt.cancel.set()

    def credential_metadata(self) -> CredentialResult:
        manager = self._manager()
        rows = []
        for provider in ALLOWED_MODELS:
            route = TransportRoute(provider_id=provider, model_id=ALLOWED_MODELS[provider][0],
                wire_model_id=ALLOWED_MODELS[provider][0], endpoint="unused", protocol=(
                    "openai-responses" if provider == "codex" else "openai-chat"),
                credential_ref=manager._credential_refs[provider],
                credential_revision=manager._credential_epochs[provider])
            try:
                self._credential(route)
                usable = True
            except BrokerRefused:
                usable = False
            rows.append(CredentialMetadata(provider_id=provider, credential_ref=route.credential_ref,
                credential_revision=route.credential_revision, configured=provider in manager._settings["connections"],
                usable=usable, selected=manager._settings["selected_provider"] == provider,
                selected_model=manager._selected_model(provider)))
        return CredentialResult(credentials=tuple(rows))

    async def credential_command(self, action: str, provider: str, *, authority: CredentialAuthority,
                                 check_current: Callable[[], bool],
                                 login_current: Callable[[], bool] | None = None, publication_lock=None,
                                 secret_reader: Callable[[], str] | None = None,
                                 login_id: str | None = None) -> CredentialResult:
        """Direct Settings commands only, authenticated by the worker envelope.

        secret_reader is a protected Python handoff, not a JSON secret field.
        Connect never changes TS/provider/model selection. Login callbacks stay
        in CodexLogin's existing owned listener; no OAuth code returns to Node.
        Refresh/forget may perform their existing explicit account HTTP; never
        call these during worker startup, metadata or transport execution.
        """
        from .credential_authority import CredentialLease, CredentialRefused, credential_owner
        try:
            if self.closed or not callable(check_current) or check_current() is not True:
                _deny("broker_authority_unbound")
            if provider not in ALLOWED_MODELS:
                _deny("transport_route_invalid")
            manager = self._manager()
            if (not isinstance(authority, CredentialAuthority) or authority.source != "settings" or authority.action != action
                    or authority.provider_id != provider or authority.retention != self.launch.retention
                    or any(getattr(authority.identity, name) != value
                        for name, value in self.launch.identity.model_dump().items())
                    or authority.revisions != self._process.revisions
                    or authority.credential_ref != manager._credential_refs[provider]
                    or authority.credential_revision != manager._credential_epochs[provider]
                    or authority.expires_at_ms > int(time.time() * 1000) + 600000):
                _deny("credential_authority_invalid")
            def current():
                return (not self.closed and authority.revisions == self._process.revisions
                    and (login_current if action == "connect" and provider == "codex" else check_current)() is True)
            if action == "connect" and provider == "codex" and not callable(login_current):
                _deny("broker_authority_unbound")
            lease = CredentialLease(authority, current, publication_lock or self._process.lock)
            lease.check()
            with self._process.lock:
                if authority.authority_id in self._process.credential_authorities:
                    _deny("credential_authority_replayed")
                if len(self._process.credential_authorities) >= self._process.capacity:
                    _deny("transport_capacity")
                self._process.credential_authorities.add(authority.authority_id)
            self.credential_leases.append(lease)
            owner = credential_owner(manager)
            login = None
            remote = None
            async def operation():
                nonlocal login, remote
                if action == "connect" and provider == "opencode-go" and callable(secret_reader) and login_id is None:
                    lease.check()
                    # Keep ownership through actual native dialog settlement.
                    pending = asyncio.create_task(asyncio.to_thread(secret_reader))
                    try:
                        secret = await asyncio.shield(pending)
                    finally:
                        while not pending.done():
                            try:
                                await asyncio.shield(pending)
                            except asyncio.CancelledError:
                                pass
                    lease.check()
                    await manager.connect_go(secret, select=False)
                elif action == "connect" and provider == "codex" and secret_reader is None and login_id is None:
                    login = await manager.auth.start(select=False)
                    owner.retain_login(login, lease)
                elif action == "refresh" and secret_reader is None and login_id is None:
                    await manager.refresh(provider)
                elif action == "forget" and secret_reader is None and login_id is None:
                    result = await manager.disconnect(provider)
                    remote = "failed" if result.get("revocation") == "failed" else None
                elif action == "login-status" and provider == "codex" and login_id and secret_reader is None:
                    login = manager.auth.status(login_id)
                else:
                    _deny("credential_command_invalid")
            if action == "login-cancel" and provider == "codex" and login_id and secret_reader is None:
                lease.check()
                login = await owner.cancel_login(login_id)
                lease.check()
            else:
                if action in {"connect", "forget"} and provider == "codex":
                    for pending_id in list(owner.logins):
                        await owner.cancel_login(pending_id)
                await owner.run(lease, operation)
            if check_current() is not True:
                _deny("stale_revision")
            result = self.credential_metadata()
            if login:
                result = CredentialResult(credentials=result.credentials, login_id=login["login_id"],
                    login_status=login["status"], authorization_url=login.get("authorization_url"))
            return result.model_copy(update={"remote_revocation": remote})
        except BrokerRefused:
            raise
        except CredentialRefused as error:
            raise BrokerRefused(error.code) from None
        except Exception:
            raise BrokerRefused("credential_command_failed") from None
