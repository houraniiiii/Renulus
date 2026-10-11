"""Owned subprocess transport for the Renulus harness; no domain/store locks."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import json
import math
import os
from pathlib import Path
import secrets
import subprocess
from uuid import uuid4

from .harness_profile import load_harness_profile
from renulus.harness_contracts import HarnessCommandIdentity, validate_command_outcome


PROTOCOL = "renulus-harness/1"
CONTROLS = frozenset({"host.status", "session.cancel", "host.close"})
COMMANDS = CONTROLS | {"host.activate", "host.stores.activate", "host.recover", "session.create", "session.prompt",
                       "session.get", "session.messages"}


def _json_bytes(value: dict) -> bytes:
    return json.dumps(value, allow_nan=False, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def _invalid_constant(value: str):
    raise ValueError("Non-finite numbers are not JSON.")


def _observe_exception(future: asyncio.Future) -> None:
    if not future.cancelled():
        future.exception()


class HarnessProcessError(RuntimeError):
    """The owned host could not become ready; close still owns any live child."""


@dataclass(frozen=True)
class HarnessProcessConfig:
    node_executable: Path
    host_entry: Path
    profile_root: Path
    profile_id: str
    store_id: str
    domain_store_id: str
    domain_path: str
    max_inflight: int = 8
    max_control_inflight: int = 4
    max_frame_bytes: int = 1048576
    max_result_records: int = 256
    max_result_bytes: int = 16777216
    start_timeout: float = 10
    boot_settings: dict = field(default_factory=dict)


@dataclass(slots=True)
class _Request:
    frame: dict
    future: asyncio.Future[None]
    result: bytes
    lane: str
    metadata_size: int
    wire_size: int
    reply_capacity: int
    pending: bool = True
    admission: str = "transport_queued"
    disconnect_error: str | None = None

    @property
    def size(self) -> int:
        return self.metadata_size + self.wire_size + (
            self.reply_capacity if self.pending else len(self.result) + 256)

    def finish_write(self) -> None:
        self.wire_size = 0

    def snapshot(self) -> dict:
        result = json.loads(self.result)
        result.pop("token", None)
        result["admission"] = self.admission
        if self.disconnect_error:
            result.update(outcome="uncertain_after_disconnect", error={"code": self.disconnect_error})
        return result

    def publish(self, result: dict, wire: bytes) -> None:
        # Preserve bounded wire bytes. Normalizing compact numeric JSON can
        # expand its retained representation beyond the reserved frame budget.
        self.result = wire
        self.admission = result["admission"]
        self.disconnect_error = None
        self.pending = result["outcome"] == "accepted_pending"
        if not self.future.done():
            self.future.set_result(None)

    def disconnect(self, code: str) -> None:
        self.disconnect_error = code
        self.pending = False
        if not self.future.done():
            self.future.set_result(None)


class ManagedHarnessProcess:
    """A single event loop owns launch, request observations and bounded close."""

    def __init__(self):
        self._process: asyncio.subprocess.Process | None = None
        self._identity: dict = {}
        self._requests: dict[str, _Request] = {}
        self._ready: asyncio.Future | None = None
        self._disconnected = False
        self._closing = False
        self._close_request_id: str | None = None
        self._started = False
        self._spawn: asyncio.Task | None = None

    async def start(self, config: HarnessProcessConfig) -> dict:
        if self._started:
            raise HarnessProcessError("This transport already owns a generation; use a new instance after close.")
        for path in (config.node_executable, config.host_entry, config.profile_root):
            if not isinstance(path, Path) or not path.is_absolute():
                raise ValueError("Executable, host entry and profile root must be absolute Paths.")
        if not config.node_executable.is_file() or not config.host_entry.is_file():
            raise ValueError("Executable and host entry must exist.")
        if (not isinstance(config.profile_id, str) or not config.profile_id
                or not isinstance(config.store_id, str) or not config.store_id):
            raise ValueError("Profile and store identities must be nonempty strings.")
        for value in (config.max_inflight, config.max_control_inflight, config.max_frame_bytes,
                      config.max_result_records, config.max_result_bytes):
            if type(value) is not int or value < 1:
                raise ValueError("Admission and frame limits must be positive integers.")
        if (not isinstance(config.start_timeout, (int, float))
                or not math.isfinite(config.start_timeout) or config.start_timeout <= 0):
            raise ValueError("Readiness timeout must be positive and finite.")
        if not isinstance(config.boot_settings, dict) or set(config.boot_settings) & {
                "protocol", "profile_id", "store_id", "generation", "token", "root",
                "domain_store_id", "domain_path"}:
            raise ValueError("Boot settings cannot replace reserved identity/root fields.")
        try:
            json.dumps(config.boot_settings, allow_nan=False)
        except (TypeError, ValueError, RecursionError):
            raise ValueError("Boot settings must be a JSON object.") from None
        self._config = config
        self._disconnected = False
        self._closing = False
        self._close_request_id = None
        root = config.profile_root.resolve()
        load_harness_profile(root, profile_id=config.profile_id,
                                domain_store_id=config.domain_store_id,
                                runtime_store_id=config.store_id, domain_path=config.domain_path)
        self._identity = {
            "protocol": PROTOCOL, "profile_id": config.profile_id,
            "store_id": config.store_id, "generation": uuid4().hex,
            "token": secrets.token_urlsafe(32),
        }
        boot = {**config.boot_settings, **self._identity, "root": str(root),
                "domain_store_id": config.domain_store_id, "domain_path": config.domain_path}
        environment = {key: os.environ[key] for key in ("SYSTEMROOT", "WINDIR")
                       if key in os.environ}
        environment["PATH"] = str(config.node_executable.parent)
        for key, name in {"HOME": "home", "USERPROFILE": "home", "APPDATA": "config",
                          "LOCALAPPDATA": "local", "XDG_CONFIG_HOME": "config",
                          "XDG_DATA_HOME": "data", "XDG_CACHE_HOME": "cache",
                          "XDG_STATE_HOME": "state", "XDG_RUNTIME_DIR": "run",
                          "TEMP": "temp", "TMP": "temp"}.items():
            directory = root / name
            directory.mkdir(exist_ok=True)
            environment[key] = str(directory)
        environment["RENULUS_HARNESS_BOOT"] = json.dumps(boot)
        self._ready = asyncio.get_running_loop().create_future()
        self._ready.add_done_callback(_observe_exception)
        self._outbound: asyncio.PriorityQueue = asyncio.PriorityQueue(
            maxsize=config.max_inflight + config.max_control_inflight + 1)
        self._sequence = 0
        self._started = True
        self._spawn = asyncio.create_task(self._spawn_child(config, root, environment))
        self._spawn.add_done_callback(_observe_exception)
        try:
            async with asyncio.timeout(config.start_timeout):
                await asyncio.shield(self._spawn)
                ready = await asyncio.shield(self._ready)
            if self._closing:
                raise HarnessProcessError("The child is closing.")
            return ready
        except TimeoutError:
            self._closing = True
            raise HarnessProcessError("The child did not authenticate readiness in time.") from None
        except asyncio.CancelledError:
            self._closing = True
            raise

    async def _spawn_child(self, config: HarnessProcessConfig, root: Path, environment: dict):
        try:
            self._process = await asyncio.create_subprocess_exec(
                str(config.node_executable), str(config.host_entry),
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE, cwd=root, env=environment,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                limit=config.max_frame_bytes,
            )
        except OSError:
            raise HarnessProcessError("The child could not be launched.") from None
        self._reader = asyncio.create_task(self._read())
        self._writer = asyncio.create_task(self._write())
        self._stderr = asyncio.create_task(self._drain_stderr())
        self._exit = asyncio.create_task(self._watch_exit())

    async def request(self, command: str, payload: dict, operation_id: str,
                      attempt_id: str, timeout: float) -> dict:
        frame = {**self._identity, "kind": "request", "command": command,
                 "payload": payload, "operation_id": operation_id,
                 "attempt_id": attempt_id, "request_id": uuid4().hex}
        future = asyncio.get_running_loop().create_future()
        pending = {key: value for key, value in frame.items()
                   if key not in ("token", "command", "payload")}
        pending.update(kind="reply", outcome="accepted_pending", admission="transport_queued")
        if self._process is None:
            pending.update(outcome="rejected_before_admission", admission="rejected_before_admission",
                           error={"code": "not_started"})
            return pending
        invalid = None
        try:
            if (not isinstance(command, str) or command not in COMMANDS
                    or not isinstance(payload, dict)
                    or not isinstance(operation_id, str) or not operation_id
                    or not isinstance(attempt_id, str) or not attempt_id
                    or not isinstance(timeout, (int, float)) or not math.isfinite(timeout)
                    or timeout < 0):
                raise ValueError("invalid request")
            HarnessCommandIdentity.model_validate({
                key: frame[key] for key in HarnessCommandIdentity.model_fields})
            encoded = _json_bytes(frame) + b"\n"
            if len(encoded) > self._config.max_frame_bytes:
                invalid = "frame_too_large"
        except (TypeError, ValueError, RecursionError):
            invalid = "invalid_request"
        if invalid:
            pending.update(outcome="rejected_before_admission", admission="rejected_before_admission",
                           error={"code": invalid})
            return pending
        control = command in CONTROLS
        lane = "close" if command == "host.close" else "control" if control else "data"
        limit = self._config.max_control_inflight if control else self._config.max_inflight
        records = [record for record in self._requests.values() if record.lane == lane]
        if lane == "close" and records:
            return records[0].snapshot()
        inflight = sum(record.pending for record in records)
        unavailable = (self._disconnected or self._process is None
                       or self._process.returncode is not None)
        if unavailable or (self._closing and not control) or inflight >= limit:
            pending.update(outcome="rejected_before_admission",
                           admission="rejected_before_admission",
                           error={"code": "disconnected" if unavailable else
                                  "closing" if self._closing and not control else "overloaded"})
            return pending
        # Retain identities, not a second copy of request payloads. Reserve the
        # largest possible reply before sending, so later replies never evict
        # earlier ones to make space. Data and control use independent budgets.
        metadata = {key: value for key, value in frame.items() if key not in ("payload", "token")}
        metadata_size = len(_json_bytes(metadata))
        reservation = metadata_size + len(encoded) + self._config.max_frame_bytes + 256
        used = sum(record.size for record in records)
        if lane != "close" and (len(records) >= self._config.max_result_records
                                or used + reservation > self._config.max_result_bytes):
            pending.update(outcome="rejected_before_admission", admission="rejected_before_admission",
                           error={"code": "result_capacity"})
            return pending
        self._requests[frame["request_id"]] = _Request(
            frame=metadata, future=future, result=_json_bytes(pending), lane=lane,
            metadata_size=metadata_size, wire_size=len(encoded),
            reply_capacity=self._config.max_frame_bytes + 256)
        if lane == "close":
            self._close_request_id = frame["request_id"]
            self._closing = True
        self._sequence += 1
        self._outbound.put_nowait((0 if control else 1, self._sequence, frame["request_id"], encoded))
        try:
            await asyncio.wait_for(asyncio.shield(future), timeout)
        except TimeoutError:
            result = self._requests[frame["request_id"]].snapshot()
            result["observation"] = "timeout"
            return result
        return self._requests[frame["request_id"]].snapshot()

    async def query_result(self, request_id: str) -> dict | None:
        record = self._requests.get(request_id)
        return record.snapshot() if record else None

    async def settlement(self, timeout: float) -> dict:
        """Observe actual child/pipe settlement, separate from clean close proof.

        Process death settles native write ownership even if command outcomes
        remain uncertain. A broken pipe by itself never proves settlement.
        """
        if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout < 0:
            raise ValueError("Settlement timeout must be nonnegative and finite.")
        deadline = asyncio.get_running_loop().time() + timeout
        try:
            if self._spawn is not None:
                await asyncio.wait_for(asyncio.shield(self._spawn), timeout)
            if self._process is None:
                return {"state": "settled", "exit_code": None}
            await asyncio.wait_for(asyncio.shield(self._exit),
                max(0, deadline - asyncio.get_running_loop().time()))
        except TimeoutError:
            return {"state": "pending"}
        except HarnessProcessError:
            return {"state": "settled", "exit_code": None}
        return {"state": "settled", "exit_code": self._process.returncode}

    async def close(self, timeout: float) -> dict:
        if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout < 0:
            raise ValueError("Close timeout must be nonnegative and finite.")
        deadline = asyncio.get_running_loop().time() + timeout
        self._closing = True
        if self._spawn is not None:
            try:
                await asyncio.wait_for(asyncio.shield(self._spawn), timeout)
            except TimeoutError:
                return {"state": "blocked", "outcome": "uncertain_after_disconnect"}
            except HarnessProcessError:
                return {"state": "closed", "outcome": "cancelled_settled"}
        if self._process is None:
            return {"state": "closed", "outcome": "cancelled_settled"}
        if self._process.returncode is None and self._close_request_id is None:
            response = await self.request("host.close", {}, uuid4().hex, uuid4().hex, 0)
            if response["outcome"] != "rejected_before_admission":
                self._close_request_id = response["request_id"]
        try:
            await asyncio.wait_for(asyncio.shield(self._exit),
                                   max(0, deadline - asyncio.get_running_loop().time()))
        except TimeoutError:
            return {"state": "blocked", "outcome": "uncertain_after_disconnect"}
        response = await self.query_result(self._close_request_id)
        if self._process.returncode != 0 or not response or response["outcome"] != "cancelled_settled":
            return {"state": "blocked", "outcome": "uncertain_after_disconnect"}
        return {"state": "closed", "outcome": "cancelled_settled"}

    async def _read(self):
        assert self._process is not None and self._process.stdout is not None
        while True:
            try:
                line = await self._process.stdout.readline()
                if not line:
                    self._disconnect("stdout_closed")
                    return
                if len(line) > self._config.max_frame_bytes or not line.endswith(b"\n"):
                    raise ValueError("invalid frame size or termination")
                frame = json.loads(line.decode("utf-8"), parse_constant=_invalid_constant)
                # JSON exponent overflow and escaped lone surrogates are not
                # rejected by loads; validate before entering reply handling.
                _json_bytes(frame)
            except (ValueError, RecursionError, OSError):
                self._disconnect("invalid_frame")
                # Keep draining the owned pipe even after protocol failure, so
                # it cannot block actual process settlement on a full buffer.
                try:
                    while await self._process.stdout.read(65536):
                        pass
                except OSError:
                    pass
                return
            if not isinstance(frame, dict) or any(
                    frame.get(key) != value for key, value in self._identity.items()):
                continue
            public = {key: value for key, value in frame.items() if key != "token"}
            if frame.get("kind") == "ready":
                if not isinstance(frame.get("state"), str) or not frame["state"]:
                    continue
                if self._ready is not None and not self._ready.done():
                    self._ready.set_result(public)
            elif frame.get("kind") == "reply":
                if not isinstance(frame.get("request_id"), str):
                    continue
                record = self._requests.get(frame.get("request_id"))
                if record is None or any(frame.get(key) != record.frame[key]
                                         for key in ("operation_id", "attempt_id")):
                    continue
                try:
                    expected = HarnessCommandIdentity.model_validate({
                        key: record.frame[key] for key in HarnessCommandIdentity.model_fields})
                    validate_command_outcome(public, expected=expected)
                except (ValueError, TypeError):
                    continue
                if not record.pending and not record.disconnect_error:
                    continue
                public["admission"] = ("rejected_before_admission"
                                       if frame["outcome"] == "rejected_before_admission"
                                       else "host_accepted")
                record.publish(public, line)

    async def _drain_stderr(self):
        assert self._process is not None and self._process.stderr is not None
        while await self._process.stderr.read(65536):
            pass

    async def _write(self):
        assert self._process is not None and self._process.stdin is not None
        try:
            while True:
                _, _, request_id, encoded = await self._outbound.get()
                record = self._requests[request_id]
                self._process.stdin.write(encoded)
                record.admission = "sent_unacknowledged"
                await self._process.stdin.drain()
                encoded = None
                record.finish_write()
        except (BrokenPipeError, ConnectionError, OSError):
            self._disconnect("pipe_disconnected")

    async def _watch_exit(self):
        assert self._process is not None
        await self._process.wait()
        await self._reader
        await self._stderr
        self._disconnect("process_exited")
        self._writer.cancel()
        await asyncio.gather(self._writer, return_exceptions=True)
        while not self._outbound.empty():
            self._outbound.get_nowait()
        for record in self._requests.values():
            record.finish_write()

    def _disconnect(self, code: str):
        self._disconnected = True
        if self._ready is not None and not self._ready.done():
            self._ready.set_exception(HarnessProcessError("The child disconnected before readiness."))
        for record in self._requests.values():
            if not record.pending:
                continue
            record.disconnect(code)
