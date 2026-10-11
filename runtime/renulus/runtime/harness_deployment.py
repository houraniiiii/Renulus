"""Trusted deployment preparation and proof of the exact native HTTP body.

The parent supplies admitted bindings, immutable account/deployment evidence and
a verified token counter. This module never discovers limits, probes providers,
allocates a dispatch step, writes records or sends HTTP. Proofs stay in the
trusted Python owner; neither a model argument nor a decoded IPC proof is a grant.
"""
from __future__ import annotations

import base64
import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace
import hashlib
import json
import re
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from renulus.contracts import ApiError
from .harness_configuration import RoleBinding, RouteLimits
from .harness_domain import DomainBinding, DomainCancelled
from .provider_adapter import SubscriptionRoute


MESSAGE = "Deployment authority could not validate the request."


def _deny(code: str):
    raise ApiError(code, MESSAGE, 409)


def _unavailable():
    raise ApiError("deployment_proof_unavailable", MESSAGE, 503, True) from None


def _safe(error: ApiError):
    raise ApiError(error.code, MESSAGE, error.status, error.retryable) from None


async def _owned(callback, *args):
    """Cancellation ends publication, while the actual async worker still settles."""
    try:
        task = asyncio.ensure_future(callback(*args))
    except ApiError as error:
        _safe(error)
    except DomainCancelled:
        raise DomainCancelled("domain_cancelled") from None
    except Exception:
        _unavailable()
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            if task.cancelled():
                raise
            cancelled = True
        except Exception:
            break
    if cancelled:
        # Retrieve a settled failure before propagating caller cancellation.
        if not task.cancelled():
            task.exception()
        raise asyncio.CancelledError
    try:
        return task.result()
    except ApiError as error:
        _safe(error)
    except DomainCancelled:
        raise DomainCancelled("domain_cancelled") from None
    except Exception:
        _unavailable()


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class NativeText(_Frozen):
    type: Literal["text"] = "text"
    text: str


class NativeImage(_Frozen):
    type: Literal["image"] = "image"
    media_type: Literal["image/png", "image/jpeg", "image/webp"]
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    bytes: int = Field(gt=0)
    detail: Literal["auto", "low", "high"] | None


class NativeToolCall(_Frozen):
    type: Literal["tool-call"] = "tool-call"
    id: str
    name: str
    arguments_json: str


class NativeToolResult(_Frozen):
    type: Literal["tool-result"] = "tool-result"
    id: str
    output_text: str


NativePart = Annotated[NativeText | NativeImage | NativeToolCall | NativeToolResult,
                       Field(discriminator="type")]


class NativeMessage(_Frozen):
    role: Literal["user", "assistant", "tool"]
    content: tuple[NativePart, ...]

    @field_validator("content", mode="before")
    @classmethod
    def freeze_content(cls, value):
        return tuple(value) if isinstance(value, list) else value


class NativeTool(_Frozen):
    name: str
    description: str
    parameters_json: str


class NativeManifest(_Frozen):
    """Admitted post-selection/shaping snapshot, captured before media filtering.

system is native SystemPart text joined with LF. Only ordinary function tools,
plain text results and inline user images are supported by this v1 contract.
JSON schema/argument strings keep all nested state immutable. The parent must
capture this snapshot through native admission, never model.dispatch arguments.
"""
    version: Literal[1]
    system: str
    messages: tuple[NativeMessage, ...]
    tools: tuple[NativeTool, ...]

    @field_validator("version", mode="before")
    @classmethod
    def strict_version(cls, value):
        if type(value) is not int:
            raise ValueError("manifest version must be an integer")
        return value

    @field_validator("messages", "tools", mode="before")
    @classmethod
    def freeze_arrays(cls, value):
        return tuple(value) if isinstance(value, list) else value

    @classmethod
    def from_payload(cls, payload: dict) -> NativeManifest:
        try:
            return cls.model_validate(payload)
        except (ValidationError, ValueError, TypeError):
            raise ApiError("deployment_manifest_invalid", MESSAGE, 409) from None


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def _constant(_):
    raise ValueError("nonfinite number")


def _json(value, code="deployment_request_invalid"):
    try:
        return json.loads(value, object_pairs_hook=_unique, parse_constant=_constant)
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise ApiError(code, MESSAGE, 409) from None


def _json_identity(value) -> str:
    try:
        return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False,
                          separators=(",", ":"))
    except (ValueError, TypeError, RecursionError):
        raise ApiError("deployment_manifest_invalid", MESSAGE, 409) from None


def _fields(value, required, optional=()):
    if not isinstance(value, dict) or not set(required) <= value.keys() or value.keys() - set(required) - set(optional):
        _deny("deployment_manifest_mismatch")


def _text(value) -> str:
    if not isinstance(value, str):
        _deny("deployment_manifest_mismatch")
    return value


def _parts(parts):
    """Native Chat joins adjacent plain text; retain every intervening image."""
    joined = []
    for part in parts:
        if part[0] == "text" and joined and joined[-1][0] == "text":
            joined[-1] = ("text", joined[-1][1] + part[1])
        else:
            joined.append(part)
    return tuple(joined)


def _image(value, detail):
    match = re.fullmatch(r"data:(image/(?:png|jpeg|webp));base64,([A-Za-z0-9+/=]+)", _text(value))
    if not match or detail not in (None, "auto", "low", "high"):
        _deny("deployment_manifest_mismatch")
    try:
        decoded = base64.b64decode(match[2], validate=True)
    except ValueError:
        raise ApiError("deployment_manifest_mismatch", MESSAGE, 409) from None
    if not decoded:
        _deny("deployment_manifest_mismatch")
    return ("image", match[1], hashlib.sha256(decoded).hexdigest(), len(decoded), detail)


def _expected(manifest: NativeManifest, responses: bool):
    events, calls, results = [], set(), set()
    for message in manifest.messages:
        plain, tools = [], []
        for part in message.content:
            if isinstance(part, NativeText) and message.role in ("user", "assistant"):
                plain.append(("text", part.text))
            elif isinstance(part, NativeImage) and message.role == "user":
                plain.append(("image", part.media_type, part.sha256, part.bytes, part.detail))
            elif isinstance(part, NativeToolCall) and message.role == "assistant":
                if not part.id or not part.name or part.id in calls:
                    _deny("deployment_manifest_invalid")
                calls.add(part.id)
                call = ("call", part.id, part.name,
                        _json_identity(_json(part.arguments_json, "deployment_manifest_invalid")))
                if responses:
                    if plain:
                        events.append(("message", "assistant", _parts(plain)))
                        plain = []
                    events.append(call)
                else:
                    tools.append(call)
            elif isinstance(part, NativeToolResult) and message.role == "tool":
                if part.id not in calls or part.id in results:
                    _deny("deployment_manifest_invalid")
                results.add(part.id)
                events.append(("result", part.id, part.output_text))
            else:
                _deny("deployment_manifest_invalid")
        if plain or message.role == "user":
            events.append(("message", message.role, _parts(plain)))
        events.extend(tools)
    if calls != results:
        _deny("deployment_manifest_invalid")
    names, schemas = set(), []
    for tool in manifest.tools:
        schema = _json(tool.parameters_json, "deployment_manifest_invalid")
        if not tool.name or tool.name in names or not isinstance(schema, dict):
            _deny("deployment_manifest_invalid")
        names.add(tool.name)
        schemas.append((tool.name, tool.description, _json_identity(schema)))
    return tuple(events), tuple(schemas)


def _wire_parts(content, role, responses):
    if isinstance(content, str):
        return (("text", content),)
    if not isinstance(content, list):
        _deny("deployment_manifest_mismatch")
    parts = []
    for part in content:
        text_kind = ("input_text" if role == "user" else "output_text") if responses else "text"
        if isinstance(part, dict) and part.get("type") == text_kind:
            _fields(part, ("type", "text"), ("annotations",) if responses and role == "assistant" else ())
            if part.get("annotations") not in (None, []):
                _deny("deployment_manifest_mismatch")
            parts.append(("text", _text(part["text"])))
        elif isinstance(part, dict) and role == "user" and part.get("type") == ("input_image" if responses else "image_url"):
            _fields(part, ("type", "image_url"), ("detail",) if responses else ())
            image = part["image_url"]
            if responses:
                parts.append(_image(image, part.get("detail")))
            else:
                _fields(image, ("url",), ("detail",))
                parts.append(_image(image["url"], image.get("detail")))
        else:
            _deny("deployment_manifest_mismatch")
    return _parts(parts)


def _wire_manifest(payload, responses):
    # Close the body boundary independently of Gateway: opaque history pointers
    # and provider compaction can add inputs absent from NativeManifest v1.
    common = {"model", "stream", "tools", "tool_choice", "temperature", "top_p",
              "frequency_penalty", "presence_penalty", "store", "stream_options",
              "parallel_tool_calls", "top_logprobs", "reasoning"}
    specific = ({"input", "instructions", "max_output_tokens", "text", "truncation",
                 "safety_identifier", "prompt_cache_key", "include", "max_tool_calls", "service_tier"}
                if responses else {"messages", "max_completion_tokens", "seed", "stop",
                                   "response_format", "reasoning_effort", "logprobs"})
    _fields(payload, ("model", "stream"), common | specific)
    if "truncation" in payload and payload["truncation"] != "disabled":
        _deny("deployment_manifest_mismatch")
    events, schemas = [], []
    messages = payload.get("input" if responses else "messages")
    if not isinstance(messages, list):
        _deny("deployment_manifest_mismatch")
    system = payload.get("instructions", "") if responses else ""
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            _deny("deployment_manifest_mismatch")
        kind, role = message.get("type"), message.get("role")
        if responses and kind == "function_call":
            _fields(message, ("type", "call_id", "name", "arguments"), ("id", "status"))
            events.append(("call", _text(message["call_id"]), _text(message["name"]),
                           _json_identity(_json(message["arguments"]))))
        elif responses and kind == "function_call_output":
            _fields(message, ("type", "call_id", "output"), ("id", "status"))
            events.append(("result", _text(message["call_id"]), _text(message["output"])))
        elif not responses and role == "tool":
            _fields(message, ("role", "tool_call_id", "content"))
            parts = _wire_parts(message["content"], "tool", False)
            if len(parts) != 1 or parts[0][0] != "text":
                _deny("deployment_manifest_mismatch")
            events.append(("result", _text(message["tool_call_id"]), parts[0][1]))
        elif not responses and role == "system" and index == 0:
            _fields(message, ("role", "content"))
            parts = _wire_parts(message["content"], "system", False)
            if len(parts) != 1 or parts[0][0] != "text":
                _deny("deployment_manifest_mismatch")
            system = parts[0][1]
        elif role in ("user", "assistant") and (not responses or kind in (None, "message")):
            optional = ("type", "id", "status") if responses else ("tool_calls",)
            if not responses and role == "assistant":
                # Pinned Chat emits an empty DeepSeek replay marker without reasoning;
                # the original raw body, including this field, remains counted.
                optional += ("reasoning_content",)
            _fields(message, ("role", "content"), optional)
            if "reasoning_content" in message and message["reasoning_content"] != "":
                _deny("deployment_manifest_mismatch")
            content = message["content"]
            parts = () if content is None and role == "assistant" else _wire_parts(content, role, responses)
            if parts or role == "user":
                events.append(("message", role, parts))
            if not responses:
                calls = message.get("tool_calls", [])
                if not isinstance(calls, list) or calls and role != "assistant":
                    _deny("deployment_manifest_mismatch")
                for call in calls:
                    _fields(call, ("id", "type", "function"))
                    _fields(call["function"], ("name", "arguments"))
                    if call["type"] != "function":
                        _deny("deployment_manifest_mismatch")
                    events.append(("call", _text(call["id"]), _text(call["function"]["name"]),
                                   _json_identity(_json(call["function"]["arguments"]))))
        else:
            _deny("deployment_manifest_mismatch")
    tools = payload.get("tools", [])
    if not isinstance(tools, list):
        _deny("deployment_manifest_mismatch")
    for tool in tools:
        _fields(tool, ("type", "name", "description", "parameters") if responses else ("type", "function"),
                ("strict",) if responses else ())
        if tool["type"] != "function":
            _deny("deployment_manifest_mismatch")
        function = tool if responses else tool["function"]
        if not responses:
            _fields(function, ("name", "description", "parameters"), ("strict",))
        if function.get("strict") is not None and function["strict"] is not False:
            _deny("deployment_manifest_mismatch")
        if not isinstance(function["parameters"], dict):
            _deny("deployment_manifest_mismatch")
        schemas.append((_text(function["name"]), _text(function["description"]),
                        _json_identity(function["parameters"])))
    return _text(system), tuple(events), tuple(schemas)


InputCounter = Callable[[bytes, NativeManifest], Awaitable[int | None]]


@dataclass(frozen=True)
class DeploymentBinding:
    binding: DomainBinding
    run_id: str
    role: RoleBinding
    route: SubscriptionRoute


@dataclass(frozen=True)
class DeploymentEvidence:
    """Injected verified evidence, including account revision and inclusive count.

counter_revision identifies one verified tokenizer artifact AND protocol framing,
system/history/tool-schema/tool-result/image accounting rules for this deployment.
An observed completion, catalogue entry or generic model limit is insufficient.
counter returns an inclusive exact count or a proven safe upper bound; it must
not return a character estimate or tokenize raw JSON/base64 as prompt text.
"""
    id: str
    route: SubscriptionRoute
    limits: RouteLimits
    capabilities: tuple[str, ...]
    limits_revision: str | None
    capabilities_revision: str | None
    counter_revision: str | None
    counter: InputCounter | None = field(repr=False)


@dataclass(frozen=True)
class DeploymentPreparation:
    id: str
    binding: DomainBinding
    run_id: str
    role: RoleBinding
    route: SubscriptionRoute
    evidence: DeploymentEvidence
    required_capabilities: tuple[str, ...]
    _issuer: object = field(repr=False, compare=False)

    @property
    def limits(self) -> RouteLimits:
        return self.evidence.limits

    @property
    def evidence_id(self) -> str:
        return self.evidence.id

    @property
    def output_tokens(self) -> int:
        return min(self.role.output_tokens, self.limits.output_tokens)


@dataclass(frozen=True)
class DeploymentProof:
    preparation: DeploymentPreparation
    step_id: str
    request_kind: str
    continuation_of: str | None
    body: bytes = field(repr=False)
    body_sha256: str
    body_bytes: int
    input_tokens: int
    output_tokens: int
    input_manifest_sha256: str
    manifest: NativeManifest = field(repr=False)
    _issuer: object = field(repr=False, compare=False)


class HarnessDeployment:
    """Parent-owned injections; check_current returns None or raises.

    resolve(binding) asynchronously returns the admitted run/role/route snapshot.
    evidence(route) synchronously returns current immutable DeploymentEvidence or
    None; its revisions identify verified capability/limit/accounting evidence.
    check_current(preparation) synchronously verifies inherited profile/store/
    generation, actual input/cancellation, role/config version, credentials and
    evidence authority without remote work. It must remain usable at the parent's
    final local dispatch guard. ConfigurationAuthority still checks the configured
    window/reserve and debits the permit. Every counter must await its actual CPU
    work/finalizers; shielding retains that owned task until it really settles.
    """
    def __init__(self, *, resolve: Callable[[DomainBinding], Awaitable[DeploymentBinding]],
                 evidence: Callable[[SubscriptionRoute], DeploymentEvidence | None],
                 check_current: Callable[[DeploymentPreparation], None], max_request_bytes: int):
        if (not all(callable(value) for value in (resolve, evidence, check_current))
                or type(max_request_bytes) is not int or not 1 <= max_request_bytes <= 32 * 1024 * 1024):
            _deny("deployment_authority_unbound")
        self.resolve, self.evidence, self.check_current = resolve, evidence, check_current
        self.max_request_bytes = max_request_bytes
        self._issuer = object()

    async def prepare(self, binding: DomainBinding, *,
                      required_capabilities: tuple[str, ...]) -> DeploymentPreparation:
        owner = await _owned(self.resolve, binding)
        if (not isinstance(owner, DeploymentBinding) or owner.binding != binding
                or not isinstance(binding, DomainBinding) or not isinstance(owner.role, RoleBinding)
                or not isinstance(owner.route, SubscriptionRoute)):
            _deny("deployment_authority_unbound")
        role, route = owner.role, owner.route
        if (role.model_id != route.catalog_model_id or role.connection.provider != route.provider_id
                or role.connection.credential_reference != route.credential_ref
                or role.connection.credential_revision != route.credential_epoch
                or route.protocol not in ("openai-responses", "openai-chat")
                or type(role.output_tokens) is not int or role.output_tokens <= 0
                or type(role.dispatch_limit) is not int or role.dispatch_limit <= 0):
            _deny("deployment_role_mismatch")
        evidence = self._evidence(owner.route)
        if evidence is None:
            _deny("deployment_evidence_unknown")
        if (not isinstance(evidence, DeploymentEvidence)
                or not isinstance(evidence.route, SubscriptionRoute)
                or not all(isinstance(value, str) and value.strip() for value in
                           (evidence.id, evidence.limits_revision, evidence.capabilities_revision))):
            _deny("deployment_evidence_unknown")
        if replace(evidence.route, catalogue_listed=None) != replace(route, catalogue_listed=None):
            _deny("deployment_evidence_mismatch")
        if not isinstance(evidence.limits, RouteLimits) or any(type(value) is not int or value <= 0 for value in
                (evidence.limits.input_tokens, evidence.limits.output_tokens, evidence.limits.window_tokens)):
            _deny("route_limits_unknown")
        if (not isinstance(evidence.counter_revision, str) or not evidence.counter_revision.strip()
                or not callable(evidence.counter)):
            _deny("deployment_counter_unknown")
        if (type(required_capabilities) is not tuple or type(evidence.capabilities) is not tuple
                or any(not isinstance(item, str) or not item for item in (*required_capabilities, *evidence.capabilities))
                or len(set(required_capabilities)) != len(required_capabilities)
                or len(set(evidence.capabilities)) != len(evidence.capabilities)
                or not set(required_capabilities) <= set(evidence.capabilities)):
            _deny("deployment_capability_unknown")
        preparation = DeploymentPreparation(uuid4().hex, binding, owner.run_id, owner.role,
            owner.route, evidence, required_capabilities, self._issuer)
        self._current(preparation)
        return preparation

    def _evidence(self, route):
        try:
            return self.evidence(route)
        except ApiError as error:
            _safe(error)
        except DomainCancelled:
            raise DomainCancelled("domain_cancelled") from None
        except Exception:
            _unavailable()

    def _current(self, preparation: DeploymentPreparation):
        if not isinstance(preparation, DeploymentPreparation) or preparation._issuer is not self._issuer:
            _deny("deployment_preparation_unbound")
        if self._evidence(preparation.route) != preparation.evidence:
            _deny("deployment_evidence_stale")
        try:
            if self.check_current(preparation) is not None:
                _deny("deployment_authority_unbound")
        except ApiError as error:
            _safe(error)
        except DomainCancelled:
            raise DomainCancelled("domain_cancelled") from None
        except Exception:
            _unavailable()
        if self._evidence(preparation.route) != preparation.evidence:
            _deny("deployment_evidence_stale")

    async def prove(self, preparation: DeploymentPreparation, *, step_id: str,
                    request_kind: str, serialized_request: dict, manifest: NativeManifest,
                    continuation_of: str | None = None) -> DeploymentProof:
        self._current(preparation)
        if (not isinstance(step_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", step_id)
                or request_kind not in {"primary", "child", "tool-continuation", "generate", "title",
                                        "summary", "compaction", "summary-repair", "transport-fallback", "recovery"}
                or (request_kind == "tool-continuation") != (continuation_of is not None)
                or continuation_of is not None and (not isinstance(continuation_of, str)
                    or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", continuation_of))):
            _deny("deployment_step_unbound")
        if (not isinstance(serialized_request, dict)
                or set(serialized_request) != {"method", "url", "headers", "body_base64"}
                or serialized_request["method"] != "POST"
                or serialized_request["url"] != preparation.route.endpoint
                or not isinstance(serialized_request["headers"], dict)
                or not isinstance(serialized_request["body_base64"], str)):
            _deny("deployment_request_invalid")
        encoded = serialized_request["body_base64"]
        if len(encoded) > 4 * ((self.max_request_bytes + 2) // 3):
            _deny("deployment_request_too_large")
        try:
            body = base64.b64decode(encoded, validate=True)
        except ValueError:
            raise ApiError("deployment_request_invalid", MESSAGE, 409) from None
        if not body or len(body) > self.max_request_bytes:
            _deny("deployment_request_too_large")
        payload = _json(body)
        if (not isinstance(payload, dict) or payload.get("model") != preparation.route.wire_model_id
                or payload.get("stream") is not True):
            _deny("deployment_request_invalid")
        if not isinstance(manifest, NativeManifest):
            _deny("deployment_manifest_invalid")
        features = {"text"}
        if manifest.tools or any(isinstance(part, (NativeToolCall, NativeToolResult))
                                 for message in manifest.messages for part in message.content):
            features.add("tools")
        if any(isinstance(part, NativeImage) for message in manifest.messages for part in message.content):
            features.add("image")
        if not features <= set(preparation.required_capabilities):
            _deny("deployment_capability_unprepared")
        responses = preparation.route.protocol == "openai-responses"
        output = payload.get("max_output_tokens" if responses else "max_completion_tokens")
        if type(output) is not int or not 1 <= output <= preparation.output_tokens:
            _deny("deployment_output_exceeds_limit")
        events, schemas = _expected(manifest, responses)
        if _wire_manifest(payload, responses) != (manifest.system, events, schemas):
            _deny("deployment_manifest_mismatch")
        counter = preparation.evidence.counter
        if counter is None:
            _deny("deployment_counter_unknown")
        tokens = await _owned(counter, body, manifest)
        self._current(preparation)
        if type(tokens) is not int or tokens < 0:
            _deny("deployment_counter_unknown")
        if tokens > preparation.limits.input_tokens:
            _deny("deployment_input_exceeds_limit")
        if tokens + output > preparation.limits.window_tokens:
            _deny("deployment_window_exceeds_limit")
        return DeploymentProof(preparation, step_id, request_kind, continuation_of, body,
            hashlib.sha256(body).hexdigest(), len(body), tokens, output,
            hashlib.sha256(manifest.model_dump_json().encode()).hexdigest(), manifest, self._issuer)

    def require_current(self, proof: DeploymentProof, *, body: bytes) -> None:
        if not isinstance(proof, DeploymentProof) or proof._issuer is not self._issuer:
            _deny("deployment_proof_unbound")
        self._current(proof.preparation)
        if type(body) is not bytes or len(body) != proof.body_bytes or hashlib.sha256(body).hexdigest() != proof.body_sha256:
            _deny("deployment_body_changed")
