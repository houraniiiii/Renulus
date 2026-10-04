"""Bounded official public metadata fetches; no case queries or paid tool calls."""
import asyncio
import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import httpx

from renulus.contracts import ApiError


async def public_url(url, allowed_hosts):
    parts = urlparse(url)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise ApiError("source_url_blocked", "Only official HTTPS source links are supported")
    if parts.port not in (None, 443) or parts.hostname.lower() not in allowed_hosts:
        raise ApiError("source_host_blocked", "This redirect leaves the selected official source")
    addresses = await asyncio.to_thread(socket.getaddrinfo, parts.hostname, 443, type=socket.SOCK_STREAM)
    for address in addresses:
        if not ipaddress.ip_address(address[4][0]).is_global:
            raise ApiError("private_source_blocked", "Private network source access is disabled")
    return url


class SourceFetcher:
    def __init__(self, transport=None):
        self.transport = transport

    async def fetch(self, url, allowed_hosts, limit=2_000_000):
        async with httpx.AsyncClient(timeout=25, follow_redirects=False, transport=self.transport,
            headers={"User-Agent": "Renulus/0.1 source-metadata-check"}) as client:
            for redirect in range(4):
                if self.transport is None:
                    await public_url(url, allowed_hosts)
                async with client.stream("GET", url) as response:
                    if response.status_code in (301, 302, 303, 307, 308):
                        url = urljoin(url, response.headers.get("location", ""))
                        if urlparse(url).hostname not in allowed_hosts or urlparse(url).scheme != "https":
                            raise ApiError("source_redirect_blocked", "Source redirect left the official host", 502)
                        continue
                    response.raise_for_status()
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > limit:
                            raise ApiError("source_metadata_too_large", "Source metadata exceeded the check limit", 413)
                    return bytes(body), dict(response.headers), str(response.url)
        raise ApiError("source_redirect_limit", "Source redirected too many times", 502)
