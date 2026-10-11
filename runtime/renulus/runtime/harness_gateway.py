"""Python-owned final HTTP dispatch; the parent owns purpose, context and IPC.

No model selection, credential discovery, retries or fallback occur here.
"""
from __future__ import annotations

import base64
import asyncio
import binascii
from dataclasses import dataclass
import hashlib
import json
import math
import re
from collections.abc import Callable

import httpx

from renulus.contracts import ApiError
from .harness_configuration import ConfigurationAuthority, ConnectionReference, RouteLimits
from .harness_domain import DomainCancellation, DomainCancelled
from .manager import ProviderManager
from .provider_adapter import SubscriptionRoute


@dataclass(frozen=True)
class GatewayBounds:
    max_request_bytes: int
    max_response_bytes: int
    timeout_seconds: float

    def __post_init__(self):
        if (type(self.max_request_bytes) is not int or not 1 <= self.max_request_bytes <= 32 * 1024 * 1024
                or type(self.max_response_bytes) is not int or not 1 <= self.max_response_bytes <= 16 * 1024 * 1024
                or type(self.timeout_seconds) not in (int, float) or not math.isfinite(self.timeout_seconds)
                or not 0 < self.timeout_seconds <= 300):
            _deny("gateway_bounds_invalid")


def _deny(code: str):
    raise ApiError(code, "The selected subscription gateway refused the request.", 409)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError("nonfinite JSON")


def _sse_failure(payload: bytes | bytearray, credential: str) -> tuple[bool, str | None]:
    try:
        text = payload.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    except UnicodeError:
        _deny("gateway_invalid_response")
    secrets = (credential, base64.b64encode(credential.encode()).decode())
    text_tail = ""
    tail_size = max(map(len, secrets))
    for frame in text.split("\n\n"):
        data = "\n".join(line[5:].lstrip(" ") for line in frame.split("\n") if line.startswith("data:"))
        if not data or data == "[DONE]":
            continue
        try:
            event = json.loads(data)
        except (ValueError, RecursionError):
            _deny("gateway_invalid_response")
        if not isinstance(event, dict):
            _deny("gateway_invalid_response")
        if event.get("type") in {"error", "response.failed", "response.incomplete"} or "error" in event:
            response = event.get("response")
            error = event.get("error", response.get("error", event) if isinstance(response, dict) else event)
            return True, error.get("code") if isinstance(error, dict) and isinstance(error.get("code"), str) else None
        stack = [event]
        while stack:
            value = stack.pop()
            if isinstance(value, str) and any(secret in value for secret in secrets):
                _deny("gateway_credential_echo")
            if isinstance(value, dict):
                stack.extend(value.keys())
                stack.extend(value.values())
            elif isinstance(value, list):
                stack.extend(value)
        fragments = [event["delta"]] if isinstance(event.get("delta"), str) else []
        for choice in event.get("choices", []) if isinstance(event.get("choices"), list) else []:
            delta = choice.get("delta") if isinstance(choice, dict) else None
            if isinstance(delta, dict) and isinstance(delta.get("content"), str):
                fragments.append(delta["content"])
        for fragment in fragments:
            joined = text_tail + fragment
            if any(secret in joined for secret in secrets):
                _deny("gateway_credential_echo")
            text_tail = joined[-tail_size:]
    return False, None


class HarnessGateway:
    def __init__(self, manager: ProviderManager | None, authority: ConfigurationAuthority | None, *,
                 cancellation: DomainCancellation | None, check_current: Callable[[], bool] | None,
                 http_transport: httpx.AsyncBaseTransport | None, bounds: GatewayBounds):
        if not isinstance(bounds, GatewayBounds):
            _deny("gateway_bounds_invalid")
        self.manager, self.authority = manager, authority
        self.cancellation, self.check_current = cancellation, check_current
        self.http_transport, self.bounds = http_transport, bounds
        self._busy = False
        self._active_permit_id: str | None = None

    def _current(self, run_id, route, connection, required):
        self.cancellation.check_current()
        try:
            current = self.check_current()
        except Exception:
            raise ApiError("gateway_authority_unbound", "The parent gateway guard is unavailable.", 409) from None
        if current is not True:
            _deny("gateway_authority_unbound")
        self.manager.require_harness_route(route)
        return self.authority.require_current(run_id, connection=connection,
            required_capabilities=required, permit_id=self._active_permit_id)

    def _envelope(self, route, request):
        if (not isinstance(request, dict)
                or set(request) != {"method", "url", "headers", "body_base64"}
                or request["method"] != "POST" or request["url"] != route.endpoint
                or not isinstance(request["headers"], dict)):
            _deny("gateway_invalid_request")
        headers = {}
        for key, value in request["headers"].items():
            if (not isinstance(key, str) or not isinstance(value, str) or len(value) > 256
                    or key.lower() in headers or "\r" in value or "\n" in value):
                _deny("gateway_invalid_request")
            headers[key.lower()] = value
        allowed = {"content-type", "content-length", "accept", "accept-encoding",
                   "user-agent", "x-opencode-session"}
        if (set(headers) - allowed or headers.get("content-type") != "application/json"
                or headers.get("user-agent", "Renulus/0.1.0") != "Renulus/0.1.0"
                or headers.get("accept", "text/event-stream") != "text/event-stream"
                or headers.get("accept-encoding", "identity") != "identity"
                or ("x-opencode-session" in headers and (route.provider_id != "opencode-go"
                    or not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", headers["x-opencode-session"])))):
            _deny("gateway_invalid_request")
        encoded = request["body_base64"]
        if not isinstance(encoded, str) or len(encoded) > 4 * ((self.bounds.max_request_bytes + 2) // 3):
            _deny("gateway_request_too_large")
        try:
            body = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error):
            _deny("gateway_invalid_request")
        if not body or len(body) > self.bounds.max_request_bytes:
            _deny("gateway_request_too_large")
        if "content-length" in headers and headers["content-length"] != str(len(body)):
            _deny("gateway_invalid_request")
        return body, {key: value for key, value in headers.items() if key == "x-opencode-session"}

    def _wire(self, route, body, current, limits):
        try:
            payload = json.loads(body.decode("utf-8"), object_pairs_hook=_unique_object,
                                 parse_constant=_invalid_constant)
        except (ValueError, UnicodeError, RecursionError):
            _deny("gateway_invalid_request")
        if not isinstance(limits, RouteLimits) or any(value is None for value in (
                limits.input_tokens, limits.output_tokens, limits.window_tokens)):
            _deny("route_limits_unknown")
        pinned = current["route"]
        codex = route.provider_id == "codex"
        field = "max_output_tokens" if codex else "max_completion_tokens"
        if (pinned["model_id"] != route.catalog_model_id
                or pinned["endpoint"] + ("/responses" if codex else "/chat/completions") != route.endpoint
                or pinned["protocol"] != ("responses" if codex else "chat-completions")):
            _deny("gateway_route_mismatch")
        if (not isinstance(payload, dict) or payload.get("model") != route.wire_model_id
                or payload.get("stream") is not True
                or ("store" in payload and payload["store"] is not False)
                or type(payload.get(field)) is not int or not 1 <= payload[field] <= min(
                    pinned["output_tokens"], limits.output_tokens)
                or any(key in payload for key in ({"max_tokens", "max_completion_tokens",
                    "max_output_tokens"} - {field}) | {"api_key", "authorization", "headers",
                    "base_url", "provider", "fallback", "websocket", "context_management",
                    "previous_response_id", "conversation"})
                or payload.get("truncation") not in (None, "disabled")):
            _deny("gateway_invalid_request")
        common = {"model", "stream", "tools", "tool_choice", "temperature", "top_p",
                  "frequency_penalty", "presence_penalty", "store", "stream_options",
                  "parallel_tool_calls", "top_logprobs", "reasoning"}
        specific = ({"input", "instructions", "max_output_tokens", "text", "truncation",
                     "safety_identifier", "prompt_cache_key", "include", "max_tool_calls", "service_tier"}
                    if codex else {"messages", "max_completion_tokens", "seed", "stop",
                                   "response_format", "reasoning_effort", "logprobs"})
        if set(payload) - (common | specific):
            _deny("gateway_invalid_request")
        tools = payload.get("tools", [])
        if (not isinstance(tools, list) or any(not isinstance(tool, dict) or tool.get("type") != "function"
                for tool in tools) or payload.get("service_tier") not in (None, "auto", "default")):
            _deny("gateway_invalid_request")
        return payload[field]

    async def dispatch(self, run_id: str, step_id: str, route: SubscriptionRoute,
                       serialized_request: dict, *, limits: RouteLimits, input_tokens: int,
                       required_capabilities: tuple[str, ...], request_kind: str,
                       continuation_of: str | None = None) -> dict:
        """One send, retaining ownership through transport and credential finalizers.

        Domain cancellation and revocation are checked while headers/body are idle.
        A cancelled caller cannot abandon the worker or cancel its finalizer twice.
        """
        if self._busy:
            _deny("gateway_busy")
        self._busy = True
        worker = asyncio.create_task(self._dispatch(run_id, step_id, route, serialized_request,
            limits=limits, input_tokens=input_tokens, required_capabilities=required_capabilities,
            request_kind=request_kind, continuation_of=continuation_of))
        stopped = None
        deadline = asyncio.get_running_loop().time() + self.bounds.timeout_seconds
        try:
            while not worker.done():
                try:
                    done, _ = await asyncio.wait({worker}, timeout=0.05)
                    if done:
                        break
                    if stopped is None:
                        connection = ConnectionReference(provider=route.provider_id,
                            credential_reference=route.credential_ref, credential_revision=route.credential_epoch)
                        self._current(run_id, route, connection, required_capabilities)
                        if asyncio.get_running_loop().time() >= deadline:
                            _deny("gateway_timeout")
                except BaseException as error:
                    if stopped is None:
                        stopped = error
                        if isinstance(error, asyncio.CancelledError) and self.cancellation:
                            self.cancellation.cancel()
                        worker.cancel()  # Exactly once; its finalizers remain owned.
            try:
                result = worker.result()
            except BaseException:
                if stopped is not None:
                    raise stopped from None
                raise
            if stopped is not None:
                raise stopped from None
            return result
        finally:
            self._active_permit_id = None
            self._busy = False

    async def _dispatch(self, run_id: str, step_id: str, route: SubscriptionRoute,
                        serialized_request: dict, *, limits: RouteLimits, input_tokens: int,
                        required_capabilities: tuple[str, ...], request_kind: str,
                        continuation_of: str | None) -> dict:
        if (not isinstance(self.manager, ProviderManager)
                or not isinstance(self.authority, ConfigurationAuthority)
                or not isinstance(self.cancellation, DomainCancellation)
                or not callable(self.check_current)
                or not isinstance(self.http_transport, httpx.AsyncBaseTransport)):
            _deny("gateway_authority_unbound")
        self.manager.require_harness_route(route)
        connection = ConnectionReference(provider=route.provider_id,
            credential_reference=route.credential_ref, credential_revision=route.credential_epoch)
        current = self._current(run_id, route, connection, required_capabilities)
        body, safe_headers = self._envelope(route, serialized_request)
        output = self._wire(route, body, current, limits)
        if request_kind == "tool-continuation":
            if not isinstance(continuation_of, str):
                _deny("gateway_continuation_unbound")
            previous = self.authority.permit(continuation_of)
            if previous["run_id"] != run_id or previous["state"] != "confirmed":
                _deny("gateway_continuation_unbound")
        elif continuation_of is not None:
            _deny("gateway_continuation_unbound")
        digest = hashlib.sha256(body).hexdigest()
        permit = self.authority.admit(run_id, step_id, payload_hash=digest,
            request_kind=request_kind, connection=connection, limits=limits,
            input_tokens=input_tokens, required_capabilities=required_capabilities,
            continuation_of=continuation_of)
        self._active_permit_id = permit["permit_id"]
        if output > permit["output_tokens"]:
            self.authority.complete(permit["permit_id"], "cancelled_before_send")
            _deny("gateway_output_exceeds_permit")
        try:
            credential = await self.manager.credential_for_harness(route)
            async with httpx.AsyncClient(transport=self.http_transport, trust_env=False,
                    follow_redirects=False, timeout=self.bounds.timeout_seconds) as client:
                request = httpx.Request("POST", route.endpoint, content=body, headers={
                    "content-type": "application/json", "accept": "text/event-stream",
                    "accept-encoding": "identity", "user-agent": "Renulus/0.1.0",
                    "authorization": "Bearer " + credential, **safe_headers,
                })
                self._current(run_id, route, connection, required_capabilities)
                admitted = self.authority.mark_dispatched(permit["permit_id"], connection=connection,
                    limits=limits, input_tokens=input_tokens, payload_hash=digest,
                    required_capabilities=required_capabilities)
                if output > admitted["output_tokens"]:
                    _deny("gateway_output_exceeds_permit")
                response = await client.send(request, stream=True)
                try:
                    payload = bytearray()
                    if response.status_code == 200:
                        if response.headers.get("content-encoding", "identity") != "identity":
                            _deny("gateway_invalid_response")
                        async for chunk in response.aiter_bytes():
                            self._current(run_id, route, connection, required_capabilities)
                            if len(payload) + len(chunk) > self.bounds.max_response_bytes:
                                _deny("gateway_response_too_large")
                            payload.extend(chunk)
                finally:
                    await response.aclose()
            self._current(run_id, route, connection, required_capabilities)
            if 300 <= response.status_code < 400:
                _deny("gateway_redirect_refused")
            if response.status_code >= 400:
                code = ("authentication_required" if response.status_code in {401, 403} else
                        "rate_limit_exceeded" if response.status_code == 429 else None)
                public = self.manager.observe_harness_stream_error(route, code)
                raise ApiError(public.code, public.message, public.status, False) from None
            if (response.status_code != 200
                    or response.headers.get("content-type", "").split(";")[0].strip().lower() != "text/event-stream"):
                _deny("gateway_invalid_response")
            failed, code = _sse_failure(payload, credential)
            if failed:
                public = self.manager.observe_harness_stream_error(route, code)
                raise ApiError(public.code, public.message, public.status, False) from None
            if credential.encode() in payload or base64.b64encode(credential.encode()) in payload:
                _deny("gateway_credential_echo")
            self.authority.complete(permit["permit_id"], "confirmed", result_reference=permit["permit_id"])
            return {"status": response.status_code, "headers": {"content-type": "text/event-stream"},
                    "body_base64": base64.b64encode(payload).decode(), "permit_id": permit["permit_id"]}
        except BaseException as error:
            state = self.authority.permit(permit["permit_id"])["state"]
            known = {"authentication_required", "subscription_limit", "model_unavailable",
                     "gateway_redirect_refused", "provider_stream_failed"}
            outcome = ("cancelled_before_send" if state == "reserved" else
                       "failed" if isinstance(error, ApiError) and error.code in known else "uncertain")
            if state in {"reserved", "dispatched"}:
                self.authority.complete(permit["permit_id"], outcome, failure_code=
                    error.code if isinstance(error, ApiError) and error.code in {
                        "authentication_required", "subscription_limit", "model_unavailable"} else None)
            if not isinstance(error, (ApiError, DomainCancelled, asyncio.CancelledError)):
                raise ApiError("transport_unavailable", "The selected subscription transport was interrupted.",
                               503, False) from None
            raise
