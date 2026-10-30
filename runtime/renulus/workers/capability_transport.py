# SPDX-License-Identifier: MIT
"""BF03 protected developer HTTP and browser byte transport. No canonical DB.

The host supplies an immutable admitted lease and an authenticated current/credit
callback. Callbacks are mandatory at socket open, each read/write, and return.
HTTP uses maintained httpx/httpcore; no MCP or HTTP protocol is implemented here.
DNS is resolved once; the network backend connects only to that pinned address.
"""
from __future__ import annotations
import asyncio
from dataclasses import dataclass, field
import hashlib
import ipaddress
import socket
import ssl
import time
from typing import Awaitable, Callable
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
import httpcore
from httpcore._backends.auto import AutoBackend
from .transport_guard import _addresses


class CapabilityTransportError(Exception):
    pass


def deny(code):
    raise CapabilityTransportError(code) from None


@dataclass(frozen=True)
class Endpoint:
    host: str
    port: int
    private_network: bool = False


@dataclass(frozen=True)
class NetworkLease:
    id: str
    endpoints: tuple[Endpoint, ...]
    expires_at_ms: int
    max_bytes: int = 100 * 1024 * 1024
    max_sockets: int = 8


@dataclass
class _Socket:
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    address: str
    port: int
    reading: bool = False
    writing: bool = False


class _PinnedBackend(httpcore.AsyncNetworkBackend):
    def __init__(self, owner, target, address):
        self.owner, self.target, self.address = owner, target, address
        self.backend = AutoBackend()

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        if host != self.target.host or port != self.target.port:
            deny("capability_endpoint_denied")
        await self.owner.credit()
        token = _addresses.set(frozenset({(self.address, port)}))
        try:
            stream = await self.backend.connect_tcp(self.address, port, timeout, local_address, socket_options)
            try:
                await self.owner.credit()
            except BaseException:
                await stream.aclose()
                raise
            return stream
        finally:
            _addresses.reset(token)

    async def connect_unix_socket(self, *args, **kwargs):
        deny("capability_endpoint_denied")

    async def sleep(self, seconds):
        await asyncio.sleep(seconds)


class CapabilityTransport:
    def __init__(self, lease: NetworkLease, *, current: Callable[[str, int], Awaitable[bool]],
                 credential: Callable[[str, int, str], Awaitable[dict[str, str]]] | None = None):
        if (not isinstance(lease, NetworkLease) or not callable(current)
                or type(lease.max_sockets) is not int or not 1 <= lease.max_sockets <= 8
                or type(lease.max_bytes) is not int or not 1 <= lease.max_bytes <= 100 * 1024 * 1024
                or not lease.endpoints or len(lease.endpoints) > 32):
            deny("capability_lease_invalid")
        self.lease, self.current, self.credential = lease, current, credential
        self.closed, self.bytes, self.opening = False, 0, 0
        self.sockets: dict[str, _Socket] = {}
        self.responses: set[httpx.Response] = set()
        self.clients: set[httpx.AsyncClient] = set()
        self.tasks: set[asyncio.Task] = set()
        self.lock = asyncio.Lock()
        self.expiry = asyncio.get_running_loop().call_later(max(0, (lease.expires_at_ms - time.time()*1000)/1000), self._expire)

    def _expire(self):
        self.closed = True
        asyncio.create_task(self.close())

    async def credit(self, count=0):
        async with self.lock:
            if (self.closed or self.lease.expires_at_ms <= time.time()*1000
                    or type(count) is not int or count < 0 or self.bytes + count > self.lease.max_bytes):
                deny("capability_stale_or_limit")
            if not await self.current(self.lease.id, count):
                deny("capability_stale")
            if self.closed or self.lease.expires_at_ms <= time.time()*1000:
                deny("capability_stale")
            self.bytes += count

    async def resolve(self, host, port):
        target = next((e for e in self.lease.endpoints if e.host == host and e.port == port), None)
        if target is None:
            deny("capability_endpoint_denied")
        await self.credit()
        rows = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
        addresses = sorted({str(ipaddress.ip_address(row[4][0])) for row in rows})
        if not addresses or any(not ipaddress.ip_address(a).is_global for a in addresses) and not target.private_network:
            deny("capability_private_network_denied")
        await self.credit()
        return target, addresses[0]

    async def open(self, target):
        if type(target) is not dict or set(target) != {"host", "port"} or type(target["port"]) is not int:
            deny("capability_target_invalid")
        if len(self.sockets) + self.opening >= self.lease.max_sockets:
            deny("capability_socket_limit")
        self.opening += 1
        task = asyncio.current_task()
        self.tasks.add(task)
        writer = None
        try:
            endpoint, address = await self.resolve(target["host"], target["port"])
            token = _addresses.set(frozenset({(address, endpoint.port)}))
            try:
                reader, writer = await asyncio.wait_for(asyncio.open_connection(address, endpoint.port, limit=65536), 10)
            finally:
                _addresses.reset(token)
            await self.credit()
            identity = "socket_" + uuid4().hex
            self.sockets[identity] = _Socket(reader, writer, address, endpoint.port)
            return identity
        except BaseException:
            if writer is not None:
                writer.close()
                await writer.wait_closed()
            raise
        finally:
            self.opening -= 1
            self.tasks.discard(task)

    async def read(self, identity):
        entry = self.sockets.get(identity)
        if entry is None or entry.reading:
            deny("capability_socket_unbound")
        entry.reading = True
        task = asyncio.current_task()
        self.tasks.add(task)
        try:
            await self.credit()
            data = await entry.reader.read(65536)
            await self.credit(len(data))
            return data
        finally:
            entry.reading = False
            self.tasks.discard(task)

    async def write(self, identity, data, end=False):
        entry = self.sockets.get(identity)
        if entry is None or entry.writing or not isinstance(data, bytes) or len(data) > 65536:
            deny("capability_socket_unbound")
        entry.writing = True
        task = asyncio.current_task()
        self.tasks.add(task)
        try:
            await self.credit(len(data))
            entry.writer.write(data)
            if end:
                entry.writer.write_eof()
            await entry.writer.drain()
            await self.credit()
        finally:
            entry.writing = False
            self.tasks.discard(task)

    async def close_socket(self, identity):
        entry = self.sockets.get(identity)
        if entry is None:
            return
        entry.writer.close()
        await entry.writer.wait_closed()
        self.sockets.pop(identity, None)

    async def http(self, *, url, method="GET", headers=None, body=b"", body_sha256=None,
                   credential_ref=None, credential_revision=None):
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password or parsed.fragment:
            deny("capability_url_invalid")
        headers = dict(headers or {})
        if (not all(k.lower() in {"accept", "content-type", "mcp-session-id", "mcp-protocol-version", "last-event-id"} for k in headers)
                or method not in {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}
                or len(body) > min(self.lease.max_bytes, 1024*1024)
                or body_sha256 != hashlib.sha256(body).hexdigest()):
            deny("capability_http_invalid")
        target, address = await self.resolve(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
        if credential_ref is not None:
            if self.credential is None:
                deny("capability_credential_unavailable")
            # The worker alone resolves/decrypts the exact host-authorized revision.
            headers.update(await self.credential(credential_ref, credential_revision, url))
        await self.credit(len(body))
        transport = httpx.AsyncHTTPTransport(retries=0)
        transport._pool = httpcore.AsyncConnectionPool(ssl_context=ssl.create_default_context(), max_connections=8,
            max_keepalive_connections=0, retries=0, network_backend=_PinnedBackend(self, target, address))
        client = httpx.AsyncClient(transport=transport, trust_env=False, follow_redirects=False, timeout=httpx.Timeout(30))
        self.clients.add(client)
        try:
            response = await client.send(client.build_request(method, url, headers=headers, content=body), stream=True)
            self.responses.add(response)
            await self.credit()
        except BaseException:
            await client.aclose()
            self.clients.discard(client)
            raise
        return CapabilityHttpStream(self, client, response)

    async def close(self):
        self.closed = True
        self.expiry.cancel()
        current = asyncio.current_task()
        tasks = [t for t in self.tasks if t is not current]
        for task in tasks:
            task.cancel()
        results = await asyncio.gather(*(self.close_socket(i) for i in tuple(self.sockets)),
            *(r.aclose() for r in tuple(self.responses)), *(c.aclose() for c in tuple(self.clients)),
            return_exceptions=True)
        await asyncio.gather(*tasks, return_exceptions=True)
        if any(isinstance(r, BaseException) for r in results):
            deny("capability_cleanup_held")
        self.responses.clear()
        self.clients.clear()


class CapabilityHttpStream:
    def __init__(self, owner, client, response):
        self.owner, self.client, self.response = owner, client, response
        self.status = response.status_code
        self.headers = {k: v for k, v in response.headers.items() if k.lower() in
            {"content-type", "content-length", "location", "mcp-session-id", "www-authenticate"}}
        self.iterator = response.aiter_raw(chunk_size=65536).__aiter__()

    async def read(self):
        task = asyncio.current_task()
        self.owner.tasks.add(task)
        try:
            await self.owner.credit()
            data = await anext(self.iterator, None)
            await self.owner.credit(len(data) if data else 0)
            return data
        finally:
            self.owner.tasks.discard(task)

    async def close(self):
        await self.response.aclose()
        await self.client.aclose()
        self.owner.responses.discard(self.response)
        self.owner.clients.discard(self.client)
