"""Owned reverse callbacks. Authority is resolved by the parent, never tool args."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import json
import hashlib
import re
import threading

from renulus.contracts import ApiError


@dataclass(frozen=True)
class DomainBinding:
    operation_id: str
    attempt_id: str
    session_id: str
    input_id: str
    cancellation_id: str


@dataclass(frozen=True)
class DomainRequest:
    callback_id: str
    binding: DomainBinding
    command: str
    payload: dict


class DomainCancelled(RuntimeError):
    """Publication authority has ended; actual worker ownership has not."""


class DomainCancellation:
    def __init__(self):
        self._event = threading.Event()
        self._check: Callable[[], bool] = lambda: True
        self._parent: DomainCancellation | None = None

    @property
    def cancelled(self) -> bool:
        return self._event.is_set() or bool(self._parent and self._parent.cancelled)

    def cancel(self) -> None:
        self._event.set()

    def check_current(self) -> None:
        # This synchronous guard is safe at the parent's local commit seam.
        if self.cancelled or self._check() is not True:
            raise DomainCancelled("domain_cancelled")


@dataclass(frozen=True)
class DomainGrant:
    binding: DomainBinding
    handler: Callable[[DomainRequest, DomainCancellation], Awaitable[dict]]
    check_current: Callable[[], bool]
    cancellation: DomainCancellation | None = None


DomainAuthority = Callable[[DomainRequest], Awaitable[DomainGrant | None]]
BINDING_KEYS = tuple(DomainBinding.__dataclass_fields__)


def _encode(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":")).encode("utf-8") + b"\n"


def _identifier(value) -> bool:
    return (isinstance(value, str) and len(value) <= 256
            and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]*", value) is not None)


class DomainCallbacks:
    def __init__(self, identity: dict, authority: DomainAuthority | None, send, *,
                 max_inflight: int, max_records: int, max_bytes: int, max_frame: int):
        self.identity = identity
        self.authority = authority
        self.send = send
        self.records: dict[str, bytes] = {}
        self.tasks: set[asyncio.Task] = set()
        self.tokens: dict[str, tuple[DomainBinding, DomainCancellation]] = {}
        self.digests: dict[str, str] = {}
        self.envelopes: dict[str, dict] = {}
        self.sizes: dict[str, int] = {}
        self.max_inflight, self.max_records = max_inflight, max_records
        self.max_bytes, self.max_frame = max_bytes, max_frame
        self.auxiliary: asyncio.Task | None = None
        self.closed = False

    def accept(self, frame: dict) -> None:
        if (set(frame) != {*self.identity, *BINDING_KEYS, "kind", "callback_id", "command", "payload"}
                or any(frame.get(key) != value for key, value in self.identity.items())
                or not all(_identifier(frame.get(key)) for key in (*BINDING_KEYS, "callback_id", "command"))
                or not isinstance(frame.get("payload"), dict)):
            return
        callback_id = frame["callback_id"]
        digest = hashlib.sha256(json.dumps({key: value for key, value in frame.items()
                                           if key != "token"}, sort_keys=True,
                                          allow_nan=False).encode("utf-8")).hexdigest()
        if callback_id in self.digests:
            if self.digests[callback_id] != digest:
                self._auxiliary_reply({**self._envelope(frame),
                                       "outcome": "rejected_before_admission",
                                       "error": {"code": "callback_id_conflict"}})
            elif callback_id in self.records:
                token = self.tokens[callback_id][1]
                try:
                    token.check_current()
                    self._auxiliary_reply(self.records[callback_id], callback_id)
                except Exception:
                    self._auxiliary_reply({**self._envelope(frame),
                                           "outcome": "rejected_before_admission",
                                           "error": {"code": "domain_cancelled"}})
            return
        if self.closed or len(self.tasks) >= self.max_inflight:
            self._reject(frame, "domain_closing" if self.closed else "domain_overloaded")
            return
        if len(_encode({**self._envelope(frame), "outcome": "uncertain_after_disconnect",
                        "error": {"code": "domain_invalid_result"}})) > self.max_frame:
            return  # No possible bounded terminal reply: never admit the effect.
        reservation = len(_encode(frame)) + self.max_frame * 2 + len(_encode(self._envelope(frame)))
        if (len(self.digests) >= self.max_records
                or sum(self.sizes.values()) + reservation > self.max_bytes):
            self._reject(frame, "domain_result_capacity")
            return
        binding = DomainBinding(**{key: frame[key] for key in DomainBinding.__dataclass_fields__})
        self.tokens[frame["callback_id"]] = (binding, DomainCancellation())
        self.digests[callback_id] = digest
        self.envelopes[callback_id] = self._envelope(frame)
        self.sizes[callback_id] = reservation
        task = asyncio.create_task(self._run(frame))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    def _reject(self, frame: dict, code: str) -> None:
        self._auxiliary_reply({**self._envelope(frame), "outcome": "rejected_before_admission",
                               "error": {"code": code}})

    def _envelope(self, frame: dict) -> dict:
        return {**self.identity, **{key: frame[key] for key in
                (*DomainBinding.__dataclass_fields__, "callback_id")}, "kind": "domain_result"}

    def _auxiliary_reply(self, result: dict | bytes, callback_id: str | None = None) -> None:
        # One independent reply slot bounds overload/conflict/replay traffic.
        if self.auxiliary and not self.auxiliary.done():
            return
        async def publish():
            try:
                await self.send(result if isinstance(result, bytes) else _encode(result), callback_id)
            except (ConnectionError, OSError):
                pass
        self.auxiliary = asyncio.create_task(publish())

    async def _run(self, frame: dict) -> None:
        binding = DomainBinding(**{key: frame[key] for key in DomainBinding.__dataclass_fields__})
        request = DomainRequest(frame["callback_id"], binding, frame["command"], frame["payload"])
        envelope = self._envelope(frame)
        token = self.tokens[request.callback_id][1]
        try:
            grant = await self.authority(request) if self.authority else None
            if not grant or grant.binding != binding:
                result = {**envelope, "outcome": "rejected_before_admission",
                          "error": {"code": "domain_unbound"}}
            else:
                token._parent = grant.cancellation
                token._check = grant.check_current
                token.check_current()
                value = await grant.handler(request, token)
                token.check_current()
                result = {**envelope, "outcome": "committed_reference", "result": value}
        except (DomainCancelled, asyncio.CancelledError):
            result = {**envelope, "outcome": "cancelled_settled",
                      "error": {"code": "domain_cancelled"}}
        except ApiError as error:
            result = {**envelope, "outcome": "uncertain_after_disconnect", "error": {
                "code": error.code if _identifier(error.code) else "domain_handler_error",
                "status": error.status, "retryable": error.retryable}}
        except Exception:
            result = {**envelope, "outcome": "uncertain_after_disconnect",
                      "error": {"code": "domain_handler_error"}}
        if token.cancelled:
            result = {**envelope, "outcome": "cancelled_settled",
                      "error": {"code": "domain_cancelled"}}
        try:
            if "result" in result and not isinstance(result["result"], dict):
                raise ValueError("domain_invalid_result")
            if "error" in result:
                error = result["error"]
                if ("status" in error and (type(error["status"]) is not int
                                             or not 400 <= error["status"] <= 599)
                        or "retryable" in error and type(error["retryable"]) is not bool):
                    raise ValueError("domain_invalid_result")
            wire = _encode(result)
            if len(wire) > self.max_frame:
                raise ValueError("domain_result_too_large")
        except (ValueError, TypeError, RecursionError, UnicodeError):
            wire = _encode({**envelope, "outcome": "uncertain_after_disconnect",
                            "error": {"code": "domain_invalid_result"}})
        self.records[request.callback_id] = wire
        self.sizes[request.callback_id] = len(_encode(envelope)) + len(wire) * 2
        try:
            await self.send(wire, request.callback_id)
        except (ConnectionError, OSError):
            pass

    def cancel(self, cancellation_id: str | None = None) -> int:
        count = 0
        for binding, token in self.tokens.values():
            if cancellation_id is None or binding.cancellation_id == cancellation_id:
                token.cancel()
                count += 1
        return count

    def publication_wire(self, callback_id: str) -> bytes:
        """Recheck locally at pipe-write admission, including replay/queue delay."""
        try:
            self.tokens[callback_id][1].check_current()
        except Exception:
            wire = _encode({**self.envelopes[callback_id], "outcome": "cancelled_settled",
                            "error": {"code": "domain_cancelled"}})
            self.records[callback_id] = wire
            self.sizes[callback_id] = len(_encode(self.envelopes[callback_id])) + len(wire) * 2
        return self.records[callback_id]

    def seal(self) -> None:
        self.closed = True
        self.cancel()

    def receive_cancel(self, frame: dict) -> None:
        if set(frame) != {*self.identity, *BINDING_KEYS, "kind", "callback_id"}:
            return
        callback_id = frame.get("callback_id")
        if not isinstance(callback_id, str):
            return
        owned = self.tokens.get(callback_id)
        if (owned and all(frame.get(key) == getattr(owned[0], key) for key in BINDING_KEYS)
                and all(frame.get(key) == value for key, value in self.identity.items())):
            owned[1].cancel()

    async def settled(self) -> None:
        while self.tasks:
            await asyncio.gather(*(asyncio.shield(task) for task in tuple(self.tasks)))
        if self.auxiliary:
            await asyncio.shield(self.auxiliary)

    def result(self, callback_id: str) -> dict | None:
        value = self.records.get(callback_id)
        if value:
            result = json.loads(value)
        elif callback_id in self.envelopes:
            result = {**self.envelopes[callback_id], "outcome": "accepted_pending"}
        else:
            return None
        result.pop("token", None)
        return result

    def status(self) -> dict:
        return {"active": len(self.tasks), "retained": len(self.digests),
                "bytes": sum(self.sizes.values()), "accepting": not self.closed}
