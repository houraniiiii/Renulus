# SPDX-License-Identifier: MIT
"""Private launch/control adapter around the existing domain app, not a domain.

renulus-domain/1: bounded LF-delimited UTF-8 JSON on inherited stdin/stdout.
Only the stdin hello contains the session token. The actual process attests its
Windows launcher, binds port zero itself and publishes ready after ASGI startup.
Shutdown ACK, clean exit and pipe closure are separate proofs at the parent.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import queue
import re
import socket
import sys
import threading

from renulus.workers.lineage import attest_launcher

PROTOCOL = "renulus-domain/1"
FRAME_BYTES = 16_384
UUID = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\Z")


def read_frame(stream):
    data = stream.readline(FRAME_BYTES + 1)
    if not data:
        return None
    if len(data) > FRAME_BYTES or not data.endswith(b"\n"):
        raise ValueError("invalid domain control frame")

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate control field")
            result[key] = value
        return result

    def invalid(_):
        raise ValueError("nonfinite control value")

    value = json.loads(data.decode("utf-8"), object_pairs_hook=pairs, parse_constant=invalid)
    if not isinstance(value, dict) or value.get("protocol") != PROTOCOL:
        raise ValueError("invalid domain control protocol")
    return value


def read_hello(stream, args):
    value = read_frame(stream)
    if (not value or set(value) != {"protocol", "kind", "profile", "launch_nonce", "expected_launcher_pid", "token"}
            or value["kind"] != "hello" or value["launch_nonce"] != args.launch_nonce
            or not UUID.fullmatch(args.launch_nonce)
            or not isinstance(value["profile"], str)
            or os.path.normcase(str(Path(value["profile"]).resolve())) != os.path.normcase(str(args.profile.resolve()))
            or type(value["expected_launcher_pid"]) is not int or not 0 < value["expected_launcher_pid"] <= 0xFFFFFFFF
            or not isinstance(value["token"], str) or not 1 <= len(value["token"].encode("utf-8")) <= 4096):
        raise ValueError("invalid domain hello binding")
    attestation = attest_launcher(value["expected_launcher_pid"])
    return value, attestation


class ControlInput:
    """Bounded reader independent of startup/shutdown; no executor to strand.

    The process uses an unbuffered raw input file so a daemon blocked in OS read
    cannot retain Python's buffered-stdin lock at interpreter exit.
    """
    def __init__(self, stream):
        self.stream = stream
        self.frames = queue.Queue(maxsize=8)
        self.loop = asyncio.get_running_loop()
        self.wake = asyncio.Event()
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self._read, name="renulus-domain-control", daemon=True)
        self.thread.start()

    def _read(self):
        while not self.stopped.is_set():
            try:
                frame = read_frame(self.stream)
            except (ValueError, OSError):
                frame = None  # Malformed input loses authority just like EOF.
            while not self.stopped.is_set():
                try:
                    self.frames.put(frame, timeout=.1)
                    self.loop.call_soon_threadsafe(self.wake.set)
                    break
                except queue.Full:
                    continue
                except RuntimeError:
                    return
            if frame is None:
                return

    async def next(self):
        while True:
            self.wake.clear()
            try:
                return self.frames.get_nowait()
            except queue.Empty:
                await self.wake.wait()


def create_application(args, token):
    if args.desktop_harness:
        from .desktop_harness import create_desktop_app
        return create_desktop_app(args.profile, token=token, source_root=args.source_root)
    from renulus.server import create_app
    return create_app(args.profile, token=token, source_root=args.source_root)


async def serve_domain(args, hello, attestation, input_stream, output_stream):
    import uvicorn

    binding = {"protocol": PROTOCOL, "profile": hello["profile"], "launch_nonce": args.launch_nonce,
               "pid": os.getpid()}

    def write(value):
        data = (json.dumps(value, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
        if len(data) > FRAME_BYTES:
            raise ValueError("domain reply too large")
        remaining = memoryview(data)
        while remaining:
            written = output_stream.write(remaining)
            if not written:
                raise OSError("domain output closed")
            remaining = remaining[written:]
        output_stream.flush()

    token = hello.pop("token")
    app = create_application(args, token)
    services = app.state.services
    from .domain_peer import DomainPeer
    secured_app = DomainPeer(app, token)
    del token
    reader = ControlInput(input_stream)
    started = asyncio.Event()
    parent_lost = asyncio.Event()

    class OwnedServer(uvicorn.Server):
        async def startup(self, sockets=None):
            await super().startup(sockets=sockets)
            if self.started:
                try:
                    write({**binding, "kind": "ready", "process": attestation.model_dump(),
                           "port": listener.getsockname()[1]})
                except OSError:
                    # Lost output is parent loss even if stdin has not closed.
                    parent_lost.set()
                started.set()

    server = OwnedServer(uvicorn.Config(secured_app, host="127.0.0.1", port=0, lifespan="on",
                                       access_log=False, log_level="warning"))

    async def control():
        await started.wait()  # Never race teardown against lifespan startup.
        while True:
            incoming = asyncio.create_task(reader.next())
            lost = asyncio.create_task(parent_lost.wait())
            try:
                done, _ = await asyncio.wait({incoming, lost}, return_when=asyncio.FIRST_COMPLETED)
                request = incoming.result() if incoming in done and not parent_lost.is_set() else None
            finally:
                incoming.cancel()
                lost.cancel()
                await asyncio.gather(incoming, lost, return_exceptions=True)
            valid = (request is not None and set(request) == set(binding) | {"kind", "request_id", "timeout_seconds"}
                     and all(type(request.get(k)) is type(v) and request[k] == v for k, v in binding.items())
                     and request["kind"] == "shutdown" and isinstance(request["request_id"], str)
                     and UUID.fullmatch(request["request_id"])
                     and type(request["timeout_seconds"]) in (int, float) and 0 < request["timeout_seconds"] <= 30)
            if not valid:
                # Retain lifespan on parent loss and retry the existing frozen
                # shutdown plan until really drained. Never detach the writer.
                await services.finish_shutdown()
                server.should_exit = True
                return
            try:
                result = await services.shutdown(timeout=request["timeout_seconds"])
                settled = result["state"] == "settled"
            except Exception:
                settled = False
            try:
                write({**binding, "kind": "shutdown", "request_id": request["request_id"],
                       "state": "settled" if settled else "held"})
            except OSError:
                parent_lost.set()
            if settled:
                server.should_exit = True
                return

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        if os.name == "nt":
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        listener.bind(("127.0.0.1", 0))
        task = asyncio.create_task(control(), name="renulus-domain-owner")
        try:
            await server.serve(sockets=[listener])
        finally:
            reader.stopped.set()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            await services.finish_shutdown()


def main():
    parser = argparse.ArgumentParser(description="Renulus owned domain adapter")
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--launch-nonce", required=True)
    parser.add_argument("--desktop-harness", action="store_true")
    args = parser.parse_args()
    if any(not p.is_absolute() or p.resolve() == Path(p.anchor) for p in (args.profile, args.source_root)):
        parser.error("explicit owned paths required")
    # Reserve the protocol descriptor before importing app/engine code. Redirect
    # even native writes to fd 1 away from the private protocol channel.
    output = os.fdopen(os.dup(sys.stdout.fileno()), "wb", buffering=0)
    os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
    input_stream = os.fdopen(os.dup(sys.stdin.fileno()), "rb", buffering=0)
    try:
        hello, attestation = read_hello(input_stream, args)
        asyncio.run(serve_domain(args, hello, attestation, input_stream, output))
        return 0
    except Exception:
        # Never log the hello, token, profile contents or exception payload.
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
