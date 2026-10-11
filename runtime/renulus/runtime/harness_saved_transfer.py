# SPDX-License-Identifier: MIT
"""Bounded saved-session transfer through an injected public process port.

Canonical snapshots/journals are the caller's responsibility. This adapter
performs no database IO and never prompts or publishes a learning answer.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import hashlib
import json
import math
import re
from typing import Literal, Protocol

from renulus.contracts import ApiError
from renulus.design_c_contracts import canonical_digest
from renulus.harness_contracts import HarnessCommandIdentity, validate_command_outcome
from renulus.learn.harness_migration import MAX_BUNDLE_BYTES, MAX_MESSAGES, NativeReadback, TransferRequest
from .harness_process import HarnessProcessError, NativeProcessIdentity

MAX_PART_BYTES = 48 * 1024
MAX_PARTS = 256
MAX_RECORDS = 256
MAX_STAGES = 4
MAX_STAGED_BYTES = 16 * 1024 * 1024


class TransferTransport(Protocol):
    def native_identity(self) -> NativeProcessIdentity: ...
    async def request(self, command: str, payload: dict, operation_id: str,
                      attempt_id: str, timeout: float) -> dict: ...
    async def query_result(self, request_id: str) -> dict | None: ...
    async def release_observation(self, request_id: str) -> bool: ...


@dataclass
class _Bundle:
    request: TransferRequest
    identity: NativeProcessIdentity
    aliases: tuple[str, ...]
    roles: tuple[str, ...]
    part_count: int
    total_bytes: int
    part_bytes: tuple[int, ...]
    plan_digest: str = ""
    staged: bool = False
    committed: bool = False
    retirement_acknowledged: bool = False


@dataclass
class _Call:
    task: asyncio.Task | None = None
    result: dict | None = None
    error: tuple[str, int, bool] | None = None


def _json_bytes(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()


def _identifier(value):
    return type(value) is str and 0 < len(value) <= 256 and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]*", value)


class HarnessSavedTransfer:
    """One authenticated transport generation; use a new adapter after restart.

    Each caller has one observation deadline, including all stage parts or a
    read's release publication. Expiry/cancellation leaves admitted requests
    owned. The canonical journal must claim import once across adapter/process
    replacement; this adapter keeps no durable transcript or journal. Verified
    readback trusts the host's exact SDK export check, never model assertions.
    close drains local owners, not the child process or uncertain native effects.
    """
    def __init__(self, transport: TransferTransport, *, observation_timeout: float):
        if (type(observation_timeout) not in (int, float) or
                not math.isfinite(observation_timeout) or not 0 < observation_timeout <= 45):
            raise ValueError("Observation timeout must be positive and at most 45 seconds.")
        self.transport = transport
        self.observation_timeout = observation_timeout
        self._bundles: dict[str, _Bundle] = {}
        self._retired: set[str] = set()
        self._native: NativeProcessIdentity | None = None
        self._calls: dict[tuple, _Call] = {}
        self._owned: set[asyncio.Task] = set()
        self._sealed = False

    def _identity(self, request, *, expected=None):
        try:
            identity = self.transport.native_identity()
        except HarnessProcessError:
            raise ApiError("harness_migration_transport", "Native transfer identity is unavailable.", 503) from None
        if (not isinstance(identity, NativeProcessIdentity) or type(identity.pid) is not int or identity.pid <= 0 or
                not _identifier(identity.generation) or
                (identity.profile_id, identity.store_id) != (request.profile_id, request.store_id) or
                self._native is not None and identity != self._native or
                expected is not None and identity != expected):
            raise ApiError("harness_migration_identity", "Native transfer scope or generation changed.", 409)
        self._native = identity
        return identity

    @staticmethod
    def _target(request):
        return {"sessionId": request.session_id, "bundleDigest": request.bundle_digest}

    @staticmethod
    def _validate_request(request):
        if (not isinstance(request, TransferRequest) or
                not all(_identifier(value) for value in (request.migration_id, request.profile_id, request.store_id)) or
                type(request.session_id) is not str or not re.fullmatch(r"ses_[0-9a-f]{64}", request.session_id) or
                type(request.bundle_digest) is not str or not re.fullmatch(r"[0-9a-f]{64}", request.bundle_digest)):
            raise ApiError("harness_migration_source", "Transfer requires an exact reserved operation and target.", 409)

    @classmethod
    def _source(cls, request, document):
        cls._validate_request(request)
        if type(document) is not bytes:
            raise ApiError("harness_migration_source", "Transfer requires an immutable bundle and exact target.", 409)
        if not 0 < len(document) <= MAX_BUNDLE_BYTES:
            raise ApiError("harness_migration_budget", "Saved bundle exceeds the native byte bound.", 409)
        if hashlib.sha256(document).hexdigest() != request.bundle_digest:
            raise ApiError("harness_migration_conflict", "The staged bundle digest differs from its reservation.", 409)
        try:
            text = document.decode("utf-8")
            source = json.loads(text)
            if (type(source) is not dict or source.get("format") != "renulus.saved-session/1" or
                    not _identifier(source.get("conversationId")) or type(source.get("messages")) is not list):
                raise ValueError
            if request.session_id != "ses_" + canonical_digest(["renulus-h06-session-v1",
                    request.profile_id, request.store_id, source["conversationId"]]):
                raise ValueError
            messages = source["messages"]
            if len(messages) > MAX_MESSAGES:
                raise ApiError("harness_migration_budget", "Saved bundle exceeds the native message bound.", 409)
            ids, roles = [], []
            for message in messages:
                if (type(message) is not dict or not _identifier(message.get("id")) or
                        message.get("id") in ids or message.get("role") not in ("user", "assistant")):
                    raise ValueError
                ids.append(message["id"])
                roles.append(message["role"])
            aliases = tuple("msg_" + canonical_digest(["renulus-h06-message-v1", request.session_id, identifier])
                            for identifier in ids)
        except (ValueError, TypeError, UnicodeError, RecursionError):
            raise ApiError("harness_migration_source", "Saved bundle needs valid UTF-8 message identities and roles.", 409) from None
        return text, aliases, tuple(roles)

    @classmethod
    def _parts(cls, request, text, total_bytes):
        header = {**cls._target(request), "partIndex": MAX_PARTS - 1,
                  "partCount": MAX_PARTS, "totalBytes": total_bytes}
        chunks = []
        offset = 0
        while offset < len(text):
            lower, upper = 0, min(MAX_PART_BYTES, len(text) - offset)
            while lower < upper:
                length = (lower + upper + 1) // 2
                if len(_json_bytes({**header, "chunk": text[offset:offset + length]})) <= MAX_PART_BYTES:
                    lower = length
                else:
                    upper = length - 1
            if lower == 0 or len(chunks) == MAX_PARTS:
                raise ApiError("harness_migration_budget", "Saved bundle exceeds the serialized part bound.", 409)
            chunks.append(text[offset:offset + lower])
            offset += lower
        return chunks

    def _done(self, call, task):
        self._owned.discard(task)
        if task.cancelled():
            call.error = ("harness_migration_uncertain", 409, False)
        else:
            error = task.exception()
            if error is None:
                call.result = task.result()
            elif isinstance(error, ApiError) and _identifier(error.code):
                call.error = (error.code, error.status, error.retryable)
            else:
                call.error = ("harness_migration_transport", 503, False)
        # Do not cache failed task tracebacks: they can hold the submitted chunk.
        call.task = None

    async def _send(self, bundle, command, payload, *, deadline=None):
        self._identity(bundle.request, expected=bundle.identity)
        loop = asyncio.get_running_loop()
        if deadline is None:
            deadline = loop.time() + self.observation_timeout
        remaining = deadline - loop.time()
        if remaining <= 0:
            raise ApiError("harness_migration_observation_timeout",
                "Native observation expired; admitted requests remain owned.", 503, True)
        key = (bundle.request.migration_id, command, payload.get("partIndex"))
        call = self._calls.get(key)
        if call is None:
            if self._sealed and command != "operation.retire":
                raise ApiError("transfer_stopping", "Saved transfer admission is sealed.", 409)
            task = asyncio.create_task(self._command(bundle, command, payload, remaining))
            call = _Call(task=task)
            self._calls[key] = call
            self._owned.add(task)
            task.add_done_callback(lambda completed: self._done(call, completed))
        task = call.task
        if task is not None:
            try:
                await asyncio.wait_for(asyncio.shield(task), max(0, deadline - loop.time()))
            except TimeoutError:
                if not task.done():
                    raise ApiError("harness_migration_observation_timeout",
                        "Native observation expired; admitted requests remain owned.", 503, True) from None
            except Exception:
                pass  # The completed owner retains only safe error metadata below.
            if call.task is not None:
                self._done(call, task)
        del task
        self._identity(bundle.request, expected=bundle.identity)
        if call.error is not None:
            code, status, retryable = call.error
            raise ApiError(code, "Native transfer could not be confirmed; no write is retried.", status, retryable)
        result = call.result
        if command == "session.import.inspect" or command == "operation.retire" and result == {"state": "pending"}:
            if self._calls.get(key) is call:
                del self._calls[key]
        return result

    async def _command(self, bundle, command, payload, timeout):
        request, identity = bundle.request, bundle.identity
        part_index = payload.get("partIndex")
        self._identity(request, expected=identity)
        response = await self.transport.request(command, payload, request.migration_id, "1", timeout)
        del payload  # Keep no second transcript/chunk after actual request publication.
        self._identity(request, expected=identity)
        try:
            expected = HarnessCommandIdentity(protocol="renulus-harness/1",
                profile_id=request.profile_id, store_id=request.store_id, generation=identity.generation,
                operation_id=request.migration_id, attempt_id="1", request_id=response["request_id"])
        except (ValueError, TypeError, KeyError):
            raise ApiError("harness_migration_response", "Native transfer reply identity is invalid.", 409) from None
        while True:
            try:
                checked = validate_command_outcome({key: value for key, value in response.items()
                    if key in {"kind", "outcome", "result", "error", *HarnessCommandIdentity.model_fields}}, expected=expected)
            except (ValueError, TypeError, AttributeError):
                raise ApiError("harness_migration_response", "Native transfer observation identity is invalid.", 409) from None
            if checked.outcome != "accepted_pending":
                break
            self._identity(request, expected=identity)
            await asyncio.sleep(0.01)
            self._identity(request, expected=identity)
            response = await self.transport.query_result(expected.request_id)
            self._identity(request, expected=identity)
        if command == "session.import.inspect" and checked.outcome in (
                "committed_reference", "rejected_before_admission", "cancelled_settled"):
            # Only this bundle's authenticated retirement can supersede a
            # terminal read release. An in-flight release remains owned.
            while not bundle.retirement_acknowledged:
                self._identity(request, expected=identity)
                released = await self.transport.release_observation(expected.request_id)
                self._identity(request, expected=identity)
                if released is True:
                    break
                if released is not False:
                    raise ApiError("harness_migration_response", "Native release acknowledgement is invalid.", 409)
                await asyncio.sleep(0.01)
        if checked.outcome != "committed_reference" or checked.error:
            raise ApiError(checked.error.code if checked.error else "harness_migration_uncertain",
                "Native transfer could not be confirmed; no write is retried.", 409)
        result = checked.result
        if command == "session.import.reserve":
            if (type(result) is not dict or type(result.get("partCount")) is not int or
                    result != {"state": "reserved", **self._target(request),
                    "partCount": bundle.part_count, "planDigest": bundle.plan_digest}):
                raise ApiError("harness_migration_response", "Native reservation acknowledgement is invalid.", 409)
        elif command == "session.import.stage":
            self._stage_reply(bundle, result, part_index)
        elif command in ("session.import", "session.import.inspect"):
            self._readback(bundle, result, absent=command == "session.import.inspect")
        elif type(result) is not dict or set(result) != {"state"} or result["state"] not in ("pending", "retired"):
            raise ApiError("harness_migration_retirement", "Native operation retirement is unavailable.", 409)
        elif result["state"] == "retired":
            bundle.retirement_acknowledged = True
        return result

    async def stage(self, request: TransferRequest, *, document: bytes) -> None:
        deadline = asyncio.get_running_loop().time() + self.observation_timeout
        text, aliases, roles = self._source(request, document)
        identity = self._identity(request)
        if request.migration_id in self._retired:
            raise ApiError("transfer_retired", "This transfer operation has been retired.", 409)
        chunks = self._parts(request, text, len(document))
        bundle = _Bundle(request, identity, aliases, roles, len(chunks), len(document),
                         tuple(len(chunk.encode()) for chunk in chunks))
        payloads = [{**self._target(request), "partIndex": index, "partCount": len(chunks),
                     "totalBytes": len(document), "chunk": chunk} for index, chunk in enumerate(chunks)]
        part_sizes = [len(_json_bytes(payload)) for payload in payloads]
        bundle.plan_digest = canonical_digest(["renulus-transfer-reservation/1", request.session_id,
            request.bundle_digest, len(document), part_sizes])
        prior = self._bundles.get(request.migration_id)
        if prior is not None:
            if (prior.request, prior.identity, prior.aliases, prior.roles) != (request, identity, aliases, roles):
                raise ApiError("harness_migration_conflict", "The staged operation already has another source.", 409)
            if prior.staged:
                return
            bundle = prior
        else:
            if (len(self._bundles) + len(self._retired) >= MAX_RECORDS or
                    sum(item.part_count > 0 for item in self._bundles.values()) >= MAX_STAGES or
                    sum(item.total_bytes for item in self._bundles.values()) + len(document) > MAX_STAGED_BYTES):
                raise ApiError("harness_migration_capacity", "Native staging capacity is retained.", 409)
            self._bundles[request.migration_id] = bundle
        await self._send(bundle, "session.import.reserve", {**self._target(request),
            "totalBytes": len(document), "partPayloadBytes": part_sizes}, deadline=deadline)
        for payload in payloads:
            await self._send(bundle, "session.import.stage", payload, deadline=deadline)
        bundle.staged = True

    @classmethod
    def _stage_reply(cls, bundle, result, index):
        sent_bytes = sum(bundle.part_bytes[:index + 1])
        if (type(result) is not dict or set(result) != {"state", "sessionId", "bundleDigest",
                    "receivedParts", "receivedBytes", "complete"} or result["state"] != "staged" or
                    any(result[key] != value for key, value in cls._target(bundle.request).items()) or
                    type(result["receivedParts"]) is not int or type(result["receivedBytes"]) is not int or
                    not index + 1 <= result["receivedParts"] <= bundle.part_count or
                    not sent_bytes <= result["receivedBytes"] <= bundle.total_bytes or
                    type(result["complete"]) is not bool or result["complete"] !=
                    (result["receivedParts"] == bundle.part_count and result["receivedBytes"] == bundle.total_bytes) or
                    index == bundle.part_count - 1 and not result["complete"]):
            raise ApiError("harness_migration_response", "Native staging acknowledgement is invalid.", 409)

    def _staged(self, request):
        self._identity(request)
        bundle = self._bundles.get(request.migration_id)
        if bundle is None or not bundle.staged:
            raise ApiError("transfer_stage_incomplete", "Stage the exact saved bundle before native transfer.", 409)
        if bundle.request != request:
            raise ApiError("harness_migration_conflict", "The transfer target differs from its staged source.", 409)
        self._identity(request, expected=bundle.identity)
        return bundle

    @classmethod
    def _readback(cls, bundle, result, *, absent=False):
        target = cls._target(bundle.request)
        if (type(result) is not dict or any(result.get(key) != value for key, value in target.items())):
            raise ApiError("harness_migration_readback", "Native readback does not match the exact staged target.", 409)
        if absent and result.get("state") == "absent" and set(result) == {"state", *target}:
            return None
        if (set(result) != {"state", *target, "messageCount"} or result.get("state") != "verified" or
                type(result["messageCount"]) is not int or result["messageCount"] != len(bundle.aliases)):
            raise ApiError("harness_migration_readback", "Native readback has no exact verified message count.", 409)
        users = bundle.roles.count("user")
        return NativeReadback(bundle.request, bundle.aliases, len(bundle.aliases),
                              users, len(bundle.aliases) - users, "settled")

    async def commit(self, request: TransferRequest) -> None:
        bundle = self._staged(request)
        if not bundle.committed:
            result = await self._send(bundle, "session.import", self._target(request))
            self._readback(bundle, result)
            bundle.committed = True

    async def inspect(self, request: TransferRequest) -> NativeReadback | None:
        bundle = self._staged(request)
        result = await self._send(bundle, "session.import.inspect", self._target(request))
        readback = self._readback(bundle, result, absent=True)
        if readback is not None:
            bundle.committed = True
        return readback

    async def retire(self, request: TransferRequest) -> Literal["pending", "retired"]:
        self._validate_request(request)
        identity = self._identity(request)
        if request.migration_id in self._retired:
            return "retired"
        bundle = self._bundles.get(request.migration_id)
        if bundle is None:
            if len(self._bundles) + len(self._retired) >= MAX_RECORDS:
                raise ApiError("harness_migration_capacity", "Native retirement identities are retained.", 409)
            # Active journal recovery has no staging bytes. Cleanup uses only
            # the authenticated operation frame; it never imports or prompts.
            bundle = _Bundle(request, identity, (), (), 0, 0, ())
            self._bundles[request.migration_id] = bundle
        if bundle.request != request:
            raise ApiError("harness_migration_conflict", "Retirement differs from the reserved operation.", 409)
        result = await self._send(bundle, "operation.retire", {})
        if type(result) is not dict or set(result) != {"state"} or result["state"] not in ("pending", "retired"):
            raise ApiError("harness_migration_retirement", "Native operation retirement is unavailable.", 409)
        if result["state"] == "retired":
            if self._bundles.get(request.migration_id) is bundle:
                self._bundles.pop(request.migration_id, None)
            self._retired.add(request.migration_id)
            self._calls = {key: call for key, call in self._calls.items() if key[0] != request.migration_id}
        return result["state"]

    def status(self) -> dict:
        """Report admission and unfinished local request/query/release owners."""
        return {"accepting": not self._sealed,
                "active": sum(not task.done() for task in self._owned)}

    def seal(self) -> None:
        """Refuse new commands while existing request/query/release owners drain."""
        self._sealed = True

    async def settled(self) -> None:
        """Wait for retained local tasks; uncertainty never proves child settlement."""
        while self._owned:
            await asyncio.gather(*(asyncio.shield(task) for task in tuple(self._owned)), return_exceptions=True)

    async def close(self) -> None:
        self.seal()
        await self.settled()
