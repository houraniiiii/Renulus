# SPDX-License-Identifier: MIT
"""Credential-free MCP byte broker for native OpenCode (spec section 6, BF03).

Native OpenCode keeps every MCP protocol message, session and approval. This
process only carries bounded HTTP/SSE bytes (through `CapabilityTransport`: DNS
pinned, endpoint/byte/expiry bound, no redirects) or developer-only owned stdio
frames, injects OAuth credentials from the protected store, strips auth data from
what it returns, and asks the host (reverse `current` frames) before every
attempt. It never mints authority, chooses routes, or starts a login.

Wire: one JSON object per line on stdin/stdout. Host requests carry `id` and `op`;
replies carry the same `id` plus `ok` or `error`. The broker asks the host
`{"op":"current","id":n,"conn":...,"lease":...,"bytes":n}` and waits for
`{"reply":n,"ok":bool}`; silence or false is stale.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
from pathlib import Path
import sys
from threading import Thread
import time
from urllib.parse import urlencode
from uuid import uuid4

from .capability_transport import (CapabilityHttpStream, CapabilityTransport, CapabilityTransportError,
    Endpoint, NetworkLease)
from .mcp_tokens import McpCredentialError, McpCredentials
from .mcp_stdio import McpStdioError, OwnedMcpServer

LINE_LIMIT = 4 * 1024 * 1024
FORWARDED_HEADERS = {"content-type", "content-length", "mcp-session-id"}  # never location/www-authenticate/set-cookie
SHELL_ENVIRONMENT = ("SystemRoot", "WINDIR", "TEMP", "TMP", "PATH", "PATHEXT", "COMSPEC")
CLEANUP_TTL_MS = 10_000


class McpBrokerError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


class _Stream:
    def __init__(self, stream: CapabilityHttpStream, secrets):
        self.stream, self.secrets, self.tail = stream, [s.encode() for s in secrets], b""


class _Connection:
    def __init__(self, transport: CapabilityTransport):
        self.transport, self.streams, self.servers, self.closed = transport, {}, {}, False


class McpBroker:
    def __init__(self, credentials: McpCredentials, ask, *, workspace: Path | None = None):
        self.credentials, self.ask, self.workspace = credentials, ask, workspace
        self.connections: dict[str, _Connection] = {}
        self.methods = {"connection.open": self.open, "connection.close": self.close, "http": self.http,
            "http.read": self.http_read, "http.close": self.http_close, "cleanup": self.cleanup,
            "credential.discover": self.discover, "credential.refresh": self.refresh,
            "credential.put": self.put, "credential.forget": self.forget,
            "stdio.open": self.stdio_open, "stdio.read": self.stdio_read, "stdio.write": self.stdio_write,
            "stdio.close": self.stdio_close}

    async def handle(self, frame: dict) -> dict:
        method = self.methods.get(frame.get("op"))
        if method is None:
            raise McpBrokerError("mcp_frame_invalid")
        return await method(frame)

    def _connection(self, frame) -> _Connection:
        conn = self.connections.get(frame.get("conn"))
        if conn is None or conn.closed:
            raise McpBrokerError("mcp_connection_closed")
        return conn

    def _current(self, conn_id, lease):
        async def current(_lease_id, count):
            return await self.ask(conn_id, lease, count)
        return current

    async def _exchange(self, conn, url, method="GET", form=None):
        body = urlencode(form).encode() if form else b""
        headers = {"accept": "application/json", **({"content-type": "application/x-www-form-urlencoded"} if form else {})}
        stream = await conn.transport.http(url=url, method=method, headers=headers, body=body, body_sha256=_sha(body))
        try:
            data = bytearray()
            while (chunk := await stream.read()) is not None:
                data.extend(chunk)
                if len(data) > 65536:
                    raise McpBrokerError("mcp_exchange_limit")
            try:
                parsed = json.loads(data)
            except ValueError:
                raise McpBrokerError("mcp_exchange_invalid") from None
            if not isinstance(parsed, dict):
                raise McpBrokerError("mcp_exchange_invalid")
            return stream.status, parsed
        finally:
            await stream.close()

    async def open(self, frame):
        conn_id = frame["conn"]
        if conn_id in self.connections:
            raise McpBrokerError("mcp_connection_exists")
        endpoints = tuple(Endpoint(e["host"], e["port"], e["private_network"]) for e in frame["endpoints"])
        holder = []

        async def credential(ref, revision, url):
            return await self.credentials.headers(ref, revision, url,
                lambda endpoint, form: self._exchange(holder[0], endpoint, "POST", form))
        transport = CapabilityTransport(NetworkLease(conn_id, endpoints, frame["expires_at_ms"], max_bytes=frame["max_bytes"]),
            current=self._current(conn_id, conn_id), credential=credential)
        holder.append(_Connection(transport))
        self.connections[conn_id] = holder[0]
        return {}

    async def http(self, frame):
        conn = self._connection(frame)
        ref, revision = frame.get("credential_ref"), frame.get("credential_revision")
        stream = await conn.transport.http(url=frame["url"], method=frame["method"], headers=frame["headers"],
            body=base64.b64decode(frame["body_base64"], validate=True), body_sha256=frame["body_sha256"],
            credential_ref=ref, credential_revision=revision)
        secrets = self.credentials.secrets(ref) if ref else []
        headers = {k.lower(): v for k, v in stream.headers.items() if k.lower() in FORWARDED_HEADERS}
        if any(secret in value for value in headers.values() for secret in secrets):
            await stream.close()
            raise McpBrokerError("mcp_credential_echo")
        identity = "stream_" + uuid4().hex
        conn.streams[identity] = _Stream(stream, secrets)
        return {"stream": identity, "status": stream.status, "headers": headers}

    async def http_read(self, frame):
        conn = self._connection(frame)
        entry = conn.streams.get(frame["stream"])
        if entry is None:
            raise McpBrokerError("mcp_stream_unbound")
        data = await entry.stream.read()
        if data is None:
            return {"data_base64": None}
        window = entry.tail + data
        if any(secret in window for secret in entry.secrets):
            await self._drop(conn, frame["stream"])
            raise McpBrokerError("mcp_credential_echo")
        entry.tail = window[-max([len(s) for s in entry.secrets] + [1]) + 1:]
        return {"data_base64": base64.b64encode(data).decode()}

    async def _drop(self, conn, identity):
        entry = conn.streams.pop(identity, None)
        if entry is not None:
            await entry.stream.close()

    async def http_close(self, frame):
        await self._drop(self._connection(frame), frame["stream"])
        return {}

    async def cleanup(self, frame):
        """One-use termination of an already-admitted session: DELETE only, own tiny lease, no refresh."""
        target = frame["endpoint"]
        lease_id = frame["conn"] + ":cleanup"
        lease = NetworkLease(lease_id, (Endpoint(target["host"], target["port"], target["private_network"]),),
            int(time.time() * 1000) + CLEANUP_TTL_MS, max_bytes=65536, max_sockets=1)

        async def credential(ref, revision, url):
            return await self.credentials.headers(ref, revision, url, None, refresh=False)
        transport = CapabilityTransport(lease, current=self._current(frame["conn"], lease_id), credential=credential)
        try:
            stream = await transport.http(url=frame["url"], method="DELETE", headers={"mcp-session-id": frame["session_id"]},
                body=b"", body_sha256=_sha(b""), credential_ref=frame.get("credential_ref"),
                credential_revision=frame.get("credential_revision"))
            status = stream.status
            await stream.close()
            return {"status": status}
        finally:
            await transport.close()

    async def discover(self, frame):
        conn = self._connection(frame)
        return {"credential": await self.credentials.discover(frame["ref"], frame["revision"],
            lambda url: self._json(conn, url))}

    async def put(self, frame):
        # Explicit Settings handoff only: the broker is the single DPAPI writer, so the value goes caller -> this pipe -> DPAPI.
        self.credentials.put(frame["ref"], revision=frame["revision"], resource=frame["resource"], client_id=frame["client_id"],
            access_token=frame["access_token"], refresh_token=frame.get("refresh_token"), expires_at=frame["expires_at"],
            token_endpoint=frame.get("token_endpoint"))
        return {"credential": self.credentials.metadata(frame["ref"], frame["revision"])}

    async def forget(self, frame):
        self.credentials.forget(frame["ref"])
        return {}

    async def _json(self, conn, url):
        status, body = await self._exchange(conn, url)
        if status != 200:
            raise McpBrokerError("mcp_discovery_invalid")
        return body

    async def refresh(self, frame):
        conn = self._connection(frame)
        await self.credentials.refresh(frame["ref"], frame["revision"],
            lambda endpoint, form: self._exchange(conn, endpoint, "POST", form), force=True)
        return {"credential": self.credentials.metadata(frame["ref"], frame["revision"])}

    async def stdio_open(self, frame):
        conn = self._connection(frame)
        if self.workspace is None:
            raise McpBrokerError("mcp_local_developer_only")
        server = OwnedMcpServer.start(frame["argv"], cwd=frame["cwd"], workspace=str(self.workspace),
            environment={k: os.environ[k] for k in SHELL_ENVIRONMENT if k in os.environ},
            current=lambda: not conn.closed)
        identity = "server_" + uuid4().hex
        conn.servers[identity] = server
        return {"server": identity}

    def _server(self, frame):
        server = self._connection(frame).servers.get(frame["server"])
        if server is None:
            raise McpBrokerError("mcp_server_unbound")
        return server

    async def stdio_read(self, frame):
        data = await self._server(frame).read()
        return {"frame_base64": None if data is None else base64.b64encode(data).decode()}

    async def stdio_write(self, frame):
        await self._server(frame).write(base64.b64decode(frame["frame_base64"], validate=True))
        return {}

    async def stdio_close(self, frame):
        conn = self._connection(frame)
        server = conn.servers.get(frame["server"])
        if server is None:
            raise McpBrokerError("mcp_server_unbound")
        settlement = await server.close()
        conn.servers.pop(frame["server"], None)
        return {"settlement": settlement}

    async def close(self, frame):
        """Revoke/finalize: cancels streams, closes sockets, settles every owned descendant."""
        conn = self.connections.get(frame["conn"])
        if conn is None:
            return {"settlements": []}
        conn.closed = True
        results = await asyncio.gather(conn.transport.close(), *(s.close() for s in tuple(conn.servers.values())),
            return_exceptions=True)
        conn.streams.clear()
        conn.servers.clear()
        if any(isinstance(r, BaseException) for r in results):
            raise McpBrokerError("mcp_cleanup_held")
        self.connections.pop(frame["conn"], None)
        return {"settlements": [r for r in results if isinstance(r, dict)]}

    async def shutdown(self):
        for conn_id in tuple(self.connections):
            await self.close({"conn": conn_id})


def _code(error: BaseException) -> str:
    if isinstance(error, (McpBrokerError, McpCredentialError)):
        return error.code
    if isinstance(error, (CapabilityTransportError, McpStdioError)):
        return str(error)
    if isinstance(error, (KeyError, TypeError, ValueError)):
        return "mcp_frame_invalid"
    return "mcp_broker_failed"


async def serve(stdin, stdout):
    """Run the JSON-lines service until stdin closes, then settle everything."""
    loop = asyncio.get_running_loop()
    lines: asyncio.Queue = asyncio.Queue()

    def read():
        for line in iter(lambda: stdin.readline(LINE_LIMIT + 1), b""):
            loop.call_soon_threadsafe(lines.put_nowait, line if len(line) <= LINE_LIMIT else None)
        loop.call_soon_threadsafe(lines.put_nowait, b"")
    Thread(target=read, name="renulus-mcp-broker-stdin", daemon=True).start()

    write_lock, pending, counter, tasks = asyncio.Lock(), {}, [0], set()

    async def send(frame):
        data = json.dumps(frame, separators=(",", ":")).encode() + b"\n"
        async with write_lock:
            await loop.run_in_executor(None, lambda: (stdout.write(data), stdout.flush()))

    async def ask(conn_id, lease, count):
        counter[0] += 1
        identity, future = counter[0], loop.create_future()
        pending[identity] = future
        await send({"op": "current", "id": identity, "conn": conn_id, "lease": lease, "bytes": count})
        try:
            return await asyncio.wait_for(future, 5) is True
        except asyncio.TimeoutError:
            return False
        finally:
            pending.pop(identity, None)

    launch = json.loads(await lines.get())
    if launch.get("op") != "launch":
        return 2
    profile, state = Path(launch["profile"]), Path(launch["state"])
    workspace = Path(launch["workspace"]) if launch.get("workspace") else None
    broker = McpBroker(McpCredentials(profile, state), ask, workspace=workspace)
    await send({"op": "ready", "id": 0})

    async def run(frame):
        try:
            reply = {"id": frame["id"], "ok": await broker.handle(frame)}
        except asyncio.CancelledError:
            raise
        except BaseException as error:
            reply = {"id": frame.get("id"), "error": _code(error)}
        await send(reply)

    while (line := await lines.get()):
        try:
            frame = json.loads(line)
        except ValueError:
            continue
        if "reply" in frame:
            future = pending.get(frame["reply"])
            if future is not None and not future.done():
                future.set_result(frame.get("ok"))
            continue
        task = asyncio.create_task(run(frame))
        tasks.add(task)
        task.add_done_callback(tasks.discard)
    for task in tuple(tasks):
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    await broker.shutdown()
    return 0


if __name__ == "__main__":
    code = asyncio.run(serve(sys.stdin.buffer, sys.stdout.buffer))
    os._exit(code)  # the stdin reader thread is blocked on a pipe
