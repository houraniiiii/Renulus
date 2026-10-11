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
from .harness_domain import DomainAuthority, DomainCallbacks
from renulus.harness_contracts import HarnessCommandIdentity, validate_command_outcome


PROTOCOL = "renulus-harness/1"
CONTROLS = frozenset({"host.status", "session.cancel", "host.close",
                      "model.extract.status", "model.extract.cancel", "model.extract.release"})
COMMANDS = CONTROLS | {"host.inspect", "host.activate", "host.stores.activate", "host.recover", "session.create", "session.prompt",
                       "session.get", "session.messages", "session.find", "model.extract",
                       "session.import.stage", "session.import", "session.import.inspect",
                       "session.remove", "operation.retire"}
OBSERVATION_COMMANDS = frozenset({"session.get", "session.messages", "session.find",
                                  "host.status", "host.inspect", "model.extract.status",
                                  "session.import.inspect"})
OBSERVATION_OUTCOMES = frozenset({"committed_reference", "rejected_before_admission",
                                 "cancelled_settled"})


def _json_bytes(value: dict) -> bytes:
    return json.dumps(value, allow_nan=False, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def _invalid_constant(value: str):
    raise ValueError("Non-finite numbers are not JSON.")


def _observe_exception(future: asyncio.Future) -> None:
    if not future.cancelled():
        future.exception()


class HarnessProcessError(RuntimeError):
    """The owned host is unavailable; close still owns any live child."""


@dataclass(frozen=True)
class NativeProcessIdentity:
    """Live child observation; no FILETIME, job or admission authority."""
    pid: int
    profile_id: str
    store_id: str
    generation: str


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
    max_domain_inflight: int = 4
    max_domain_result_records: int = 256
    max_domain_result_bytes: int = 16777216
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
    observed: bool = False
    releasing: asyncio.Task[bool] | None = None

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
        if not self.pending and result["outcome"] in OBSERVATION_OUTCOMES:
            self.observed = True
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

    def __init__(self, *, domain_authority: DomainAuthority | None = None):
        self._domain_authority = domain_authority
        self._domains: DomainCallbacks | None = None
        self._process: asyncio.subprocess.Process | None = None
        self._identity: dict = {}
        self._requests: dict[str, _Request] = {}
        self._retired_operations: set[str] = set()
        self._ready: asyncio.Future | None = None
        self._disconnected = False
        self._closing = False
        self._close_request_id: str | None = None
        self._started = False
        self._spawn: asyncio.Task | None = None
        self._observation_release_pending = False

    def native_identity(self) -> NativeProcessIdentity:
        """Observe an authenticated live child without IO or changing ownership.

        The caller independently verifies creation FILETIME and job membership.
        Closing, disconnected and unready generations grant no observation.
        Only ready/policy_blocked startup states describe a live native owner.
        """
        process, ready = self._process, self._ready
        if (not self._started or self._closing or self._disconnected
                or process is None or process.returncode is not None
                or type(process.pid) is not int or process.pid <= 0
                or ready is None or not ready.done() or ready.cancelled()
                or ready.exception() is not None):
            raise HarnessProcessError("Native child identity is unavailable.") from None
        authenticated = ready.result()
        if (type(authenticated) is not dict
                or any(authenticated.get(key) != self._identity.get(key)
                    for key in ("protocol", "profile_id", "store_id", "generation"))
                or authenticated.get("state") not in ("ready", "policy_blocked")):
            raise HarnessProcessError("Native child identity is unavailable.") from None
        return NativeProcessIdentity(process.pid, self._identity["profile_id"],
            self._identity["store_id"], self._identity["generation"])

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
        for value in (config.max_inflight, config.max_control_inflight, config.max_domain_inflight,
                      config.max_domain_result_records, config.max_domain_result_bytes, config.max_frame_bytes,
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
        ipc = boot.get("ipc", {})
        if not isinstance(ipc, dict):
            raise ValueError("IPC limits must be a JSON object.")
        ipc = dict(ipc)
        for key, limit in {"max_domain_inflight": config.max_domain_inflight,
                           "max_domain_result_records": config.max_domain_result_records,
                           "max_domain_result_bytes": config.max_domain_result_bytes}.items():
            requested = ipc.get(key, limit)
            if type(requested) is not int or requested < 1:
                raise ValueError("Domain IPC limits must be positive integers.")
            ipc[key] = min(requested, limit)
        boot["ipc"] = ipc
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
            # One bounded release publication cannot consume command/close slots.
            maxsize=config.max_inflight + config.max_control_inflight + config.max_domain_inflight + 3)
        self._domains = DomainCallbacks(self._identity, self._domain_authority, self._send_domain,
            max_inflight=config.max_domain_inflight, max_records=config.max_domain_result_records,
            max_bytes=config.max_domain_result_bytes, max_frame=config.max_frame_bytes)
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
            # Authenticated scalar readiness must not share the caller's snapshot.
            return dict(ready)
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
        if (type(operation_id) is str and type(command) is str
                and operation_id in self._retired_operations
                and command not in OBSERVATION_COMMANDS | {'host.close'}):
            if command == 'operation.retire' and payload == {}:
                pending.update(outcome='committed_reference', admission='host_accepted', result={'state': 'retired'})
            else:
                pending.update(outcome='rejected_before_admission', admission='rejected_before_admission',
                    error={'code': 'operation_terminal_unavailable'})
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
        record = self._requests[frame['request_id']]
        if lane == "close":
            self._close_request_id = frame["request_id"]
            self._closing = True
            if self._domains:
                self._domains.seal()
        self._sequence += 1
        self._outbound.put_nowait((0 if control else 2, self._sequence, frame["request_id"], encoded, None, None))
        try:
            await asyncio.wait_for(asyncio.shield(future), timeout)
        except TimeoutError:
            result = record.snapshot()
            result["observation"] = "timeout"
            return result
        return record.snapshot()

    async def query_result(self, request_id: str) -> dict | None:
        record = self._requests.get(request_id)
        return record.snapshot() if record else None

    async def release_observation(self, request_id: str) -> bool:
        """Forget an observed terminal read only after its release frame is sent.

        True acknowledges local pipe publication, not native settlement. Native
        IPC retains any active command/reply until its own finalizers settle.
        Cancellation of an observer leaves this publication owned.
        A busy release allowance returns False and retains the receipt.
        """
        if type(request_id) is not str:
            return False
        record = self._requests.get(request_id)
        if (record is None or not record.observed or record.pending or record.disconnect_error
                or record.frame["command"] not in OBSERVATION_COMMANDS
                or json.loads(record.result)["outcome"] not in OBSERVATION_OUTCOMES
                or self._disconnected or self._process is None or self._process.returncode is not None):
            return False
        if record.releasing is None:
            if self._observation_release_pending:
                return False
            self._observation_release_pending = True
            record.releasing = asyncio.create_task(self._release_observation(request_id, record))
            record.releasing.add_done_callback(_observe_exception)
        return await asyncio.shield(record.releasing)

    async def _release_observation(self, request_id: str, record: _Request) -> bool:
        completion = asyncio.get_running_loop().create_future()
        completion.add_done_callback(_observe_exception)
        encoded = _json_bytes({**self._identity, "kind": "observation_release",
                               "request_id": request_id}) + b"\n"
        self._sequence += 1
        try:
            self._outbound.put_nowait((0, self._sequence, None, encoded, completion, None))
            await completion
        except (asyncio.QueueFull, ConnectionError, OSError):
            record.releasing = None
            return False
        finally:
            self._observation_release_pending = False
        if self._requests.get(request_id) is record:
            del self._requests[request_id]
        return True

    def domain_result(self, callback_id: str) -> dict | None:
        return self._domains.result(callback_id) if self._domains else None

    def domain_status(self, *, operation_id: str | None = None) -> dict:
        """Observe bound callback ownership separately from native settlement."""
        if self._domains:
            return self._domains.status(operation_id=operation_id)
        if operation_id is None:
            return {"active": 0, "retained": 0}
        return {"active": 0, "retained": 0, "bytes": 0, "accepting": False}

    def cancel_domain(self, cancellation_id: str) -> int:
        return self._domains.cancel(cancellation_id) if self._domains else 0

    async def _send_domain(self, encoded: bytes, callback_id: str | None = None) -> None:
        if self._disconnected or self._process is None or self._process.returncode is not None:
            raise ConnectionError("domain_disconnected")
        if len(encoded) > self._config.max_frame_bytes:
            raise ConnectionError("domain_frame_too_large")
        done = asyncio.get_running_loop().create_future()
        self._sequence += 1
        self._outbound.put_nowait((1, self._sequence, None, encoded, done, callback_id))
        await done

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
        if self._domains:
            self._domains.seal()
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
            if frame.get("kind") == "domain_request":
                self._domains.accept(frame)
            elif frame.get("kind") == "domain_cancel":
                self._domains.receive_cancel(frame)
            elif frame.get("kind") == "ready":
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
                if (record.frame['command'] == 'operation.retire'
                        and public['outcome'] == 'committed_reference'
                        and public.get('result') == {'state': 'retired'}):
                    operation_id = record.frame['operation_id']
                    self._retired_operations.add(operation_id)
                    for identifier, previous in tuple(self._requests.items()):
                        if previous.frame['operation_id'] == operation_id and not previous.pending:
                            del self._requests[identifier]

    async def _drain_stderr(self):
        assert self._process is not None and self._process.stderr is not None
        while await self._process.stderr.read(65536):
            pass

    async def _write(self):
        assert self._process is not None and self._process.stdin is not None
        completion = None
        try:
            while True:
                _, _, request_id, encoded, completion, callback_id = await self._outbound.get()
                record = self._requests.get(request_id)
                if callback_id:
                    encoded = self._domains.publication_wire(callback_id)
                self._process.stdin.write(encoded)
                if record:
                    record.admission = "sent_unacknowledged"
                await self._process.stdin.drain()
                encoded = None
                if record:
                    record.finish_write()
                if completion and not completion.done():
                    completion.set_result(None)
        except (BrokenPipeError, ConnectionError, OSError):
            self._disconnect("pipe_disconnected")
        finally:
            if completion and not completion.done():
                completion.set_exception(ConnectionError("domain_disconnected"))

    async def _watch_exit(self):
        assert self._process is not None
        await self._process.wait()
        await self._reader
        await self._stderr
        self._disconnect("process_exited")
        self._writer.cancel()
        await asyncio.gather(self._writer, return_exceptions=True)
        while not self._outbound.empty():
            _, _, _, _, completion, _ = self._outbound.get_nowait()
            if completion and not completion.done():
                completion.set_exception(ConnectionError("domain_disconnected"))
        for record in self._requests.values():
            record.finish_write()
        if self._domains:
            await self._domains.settled()

    def _disconnect(self, code: str):
        self._disconnected = True
        if self._domains:
            self._domains.seal()
        if self._ready is not None and not self._ready.done():
            self._ready.set_exception(HarnessProcessError("The child disconnected before readiness."))
        for record in self._requests.values():
            if not record.pending:
                continue
            record.disconnect(code)
