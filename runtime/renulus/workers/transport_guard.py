"""Socket authority for one protected broker request, never an engine thread.

The broker validates the product route and committed permit before entering this
scope. DNS results and the exact port constrain socket.connect; the ContextVar
is local to its asynchronous request/cleanup tasks, with no process-wide switch.
"""
from contextlib import asynccontextmanager
from contextvars import ContextVar
import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit

_addresses: ContextVar[frozenset[tuple[str, int]]] = ContextVar(
    "renulus_protected_transport_addresses", default=frozenset())


def permitted_connection(address) -> bool:
    if not isinstance(address, tuple) or len(address) < 2:
        return False
    try:
        return (str(ipaddress.ip_address(address[0])), address[1]) in _addresses.get()
    except (ValueError, TypeError):
        return False


@asynccontextmanager
async def endpoint_network(endpoint: str):
    url = urlsplit(endpoint)
    if url.scheme not in {"https", "http"} or not url.hostname or url.username or url.password:
        raise PermissionError("protected endpoint required")
    port = url.port or (443 if url.scheme == "https" else 80)
    resolved = await asyncio.get_running_loop().getaddrinfo(url.hostname, port, type=socket.SOCK_STREAM)
    addresses = frozenset((str(ipaddress.ip_address(item[4][0])), port) for item in resolved)
    if not addresses:
        raise PermissionError("protected endpoint unavailable")
    token = _addresses.set(addresses)
    try:
        yield
    finally:
        _addresses.reset(token)
