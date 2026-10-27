"""Inherited-stdio worker entrypoint; no listener, provider or canonical writer.

Launch with --config <host-owned immutable JSON>. The token is supplied once in
the first stdin hello frame, never via arguments, environment, replies or logs.
Frames are compact UTF-8 JSON followed by LF, bounded including that LF.
"""
from __future__ import annotations

import argparse
from collections import deque
import hashlib
import hmac
import ipaddress
import json
import os
from pathlib import Path
import sys
from threading import Condition, Thread

from pydantic import ValidationError

from renulus.worker_contracts import (Capacity, COMMAND, Hello, LaunchConfig, MAX_FRAME_BYTES,
                                      Ready, SUPPORTED_COMMANDS, UNAVAILABLE_COMMANDS)
from .runtime import Worker
from .lineage import attest_launcher
from .engines import SelectedEngines
from .transport_guard import permitted_connection


def loads(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result
    def invalid(_):
        raise ValueError("nonfinite JSON")
    return json.loads(data, object_pairs_hook=pairs, parse_constant=invalid)


def read_frame(stream, bound):
    data = stream.readline(bound + 1)
    if not data:
        return None
    if len(data) > bound or not data.endswith(b"\n"):
        raise ValueError("invalid frame")
    return loads(data)


class Writer:
    """Independent bounded reply pump, with reserved priority control capacity.

    One admitted data request emits at most two replies. At most request_count
    frames can be admitted per process; stalled consumers apply backpressure.
    Terminal frames are never dropped while the inherited output pipe is alive.
    """
    def __init__(self, stream, capacity):
        self.stream, self.capacity = stream, capacity
        self.control, self.data = deque(), deque()
        self.condition = Condition()
        self.closed = self.failed = False
        self.thread = Thread(target=self._run, name="renulus-replies", daemon=True)
        self.thread.start()

    def emit(self, reply):
        data = (reply.model_dump_json(exclude_none=False) + "\n").encode("utf-8")
        if len(data) > self.capacity.max_frame_bytes:
            raise ValueError("reply exceeds frame capacity")
        # State replies are controls; terminal engine replies use the data lane.
        control = getattr(reply.result, "tag", None) == "state"
        queue = self.control if control else self.data
        bound = self.capacity.control_slots if control else 2 * (
            self.capacity.data_in_flight + self.capacity.data_queued) + 2
        with self.condition:
            while len(queue) >= bound and not self.failed:
                self.condition.wait()
            if self.failed:
                return
            queue.append(data)
            self.condition.notify_all()

    def _run(self):
        try:
            while True:
                with self.condition:
                    while not self.control and not self.data and not self.closed:
                        self.condition.wait()
                    if not self.control and not self.data and self.closed:
                        return
                    data = (self.control if self.control else self.data).popleft()
                    self.condition.notify_all()
                self.stream.write(data)
                self.stream.flush()
        except (OSError, ValueError):
            with self.condition:
                self.failed = True
                self.condition.notify_all()

    def close(self):
        with self.condition:
            self.closed = True
            self.condition.notify_all()
        self.thread.join(timeout=2)


def _absolute_directory(value):
    path = Path(value)
    if not path.is_absolute():
        raise ValueError("launch path must be absolute")
    # Launch roots are host-controlled; reject links/junctions before use.
    for item in (path, *path.parents):
        if item.is_symlink() or item.is_junction():
            raise ValueError("redirected launch root")
    return path


def _offline_audit(event, args):
    if event == "socket.connect":
        address = args[1]
        if permitted_connection(address):
            return
        try:
            if isinstance(address, tuple) and ipaddress.ip_address(address[0]).is_loopback:
                return  # Windows self-pipe primitives; no remote engine service.
        except ValueError:
            pass
        raise PermissionError("worker network unavailable")


def main():
    sys.dont_write_bytecode = True
    # Preserve only the protocol descriptor. Native stdout/stderr and Python
    # logging are discarded process-wide, before importing any selected helper.
    protocol = os.fdopen(os.dup(sys.stdout.fileno()), "wb", buffering=0)
    with open(os.devnull, "wb") as null:
        os.dup2(null.fileno(), sys.stdout.fileno())
        os.dup2(null.fileno(), sys.stderr.fileno())
    writer = worker = None
    try:
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument("--config", required=True)
        args = parser.parse_args()
        config_path = Path(args.config)
        if not config_path.is_absolute() or config_path.stat().st_size > MAX_FRAME_BYTES:
            return 2
        config = LaunchConfig.model_validate(loads(config_path.read_bytes()))
        if config.native:
            for key in ('originals_root', 'budget_root', 'grants_root'):
                _absolute_directory(getattr(config.native, key))
            original = Path(config.native.originals_root).absolute()
            budget = Path(config.native.budget_root).absolute()
            grants = Path(config.native.grants_root).absolute()
            if original == budget or not original.is_relative_to(budget) or grants.is_relative_to(original) or original.is_relative_to(grants):
                raise ValueError('native launch namespace overlap')
        if config.helpers:
            for value in config.helpers.model_dump().values():
                _absolute_directory(value)
            cache = Path(config.helpers.cache_root).resolve()
            for protected in (config.helpers.helpers_root, config.helpers.source_root):
                protected = Path(protected).resolve()
                if cache.is_relative_to(protected) or protected.is_relative_to(cache):
                    raise ValueError("cache overlaps immutable launch resources")
        hello_value = read_frame(sys.stdin.buffer, config.capacity.max_frame_bytes)
        hello = Hello.model_validate(hello_value)
        if (hello.identity != config.identity or not hmac.compare_digest(
                hashlib.sha256(hello.launch_token.encode("utf-8")).hexdigest(), config.launch_token_sha256)):
            return 2
        attestation = attest_launcher(hello.expected_launcher_pid)
        sys.addaudithook(_offline_audit)
        engines = SelectedEngines(config.helpers)
        try:
            engines.prepare()
        except Exception:
            # Missing helpers keep the boundary available; engine requests fail
            # with a tagged error, without a constructor or provider fallback.
            pass
        capacity_values = {k: min(getattr(config.capacity, k), getattr(hello.capacity, k))
                           for k in Capacity.model_fields}
        # Leave enough envelope room for base64, metadata and UTF-8 JSON overhead.
        capacity_values["max_chunk_bytes"] = min(capacity_values["max_chunk_bytes"],
            (capacity_values["max_frame_bytes"] - 4096) * 3 // 4)
        capacity = Capacity(**capacity_values)
        ready = Ready(identity=config.identity, pid=os.getpid(), parent_pid=os.getppid(),
                      process=attestation, capacity=capacity,
                      supported_commands=list(SUPPORTED_COMMANDS),
                      unavailable_commands=list(UNAVAILABLE_COMMANDS))
        protocol.write((ready.model_dump_json() + "\n").encode("utf-8"))
        protocol.flush()
        # Authentication is consumed and no raw token is retained in worker state.
        del hello, hello_value
        writer = Writer(protocol, capacity)
        worker = Worker(config, capacity, writer.emit, engines=engines)
        while not writer.failed:
            raw = read_frame(sys.stdin.buffer, capacity.max_frame_bytes)
            if raw is None:
                break
            command = COMMAND.validate_python(raw)
            worker.handle(command, raw["input"])
        return 0
    except (ValueError, TypeError, KeyError, OSError, ValidationError, RecursionError):
        # Malformed frames cannot be safely identity-bound. Fail closed without
        # reflecting their contents. The host records outstanding leases uncertain.
        return 2
    finally:
        if worker:
            worker.disconnect()
        if writer:
            writer.close()
        protocol.close()


if __name__ == "__main__":
    raise SystemExit(main())
