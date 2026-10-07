"""Bounded official public metadata fetches; no case queries or paid tool calls."""
import asyncio
import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import httpx

from renulus.contracts import ApiError


def validate_url(url, allowed_hosts):
    parts = urlparse(url)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise ApiError("source_url_blocked", "Only official HTTPS source links are supported")
    try:
        port = parts.port
    except ValueError:
        raise ApiError("source_url_blocked", "Invalid source port") from None
    if port not in (None, 443) or parts.hostname.lower() not in allowed_hosts:
        raise ApiError("source_host_blocked", "This redirect leaves the selected official source")
    try:
        address = ipaddress.ip_address(parts.hostname)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ApiError("private_source_blocked", "Private network source access is disabled")
    return parts


async def public_url(url, allowed_hosts):
    parts = validate_url(url, allowed_hosts)
    addresses = await asyncio.to_thread(socket.getaddrinfo, parts.hostname, 443, type=socket.SOCK_STREAM)
    if not addresses:
        raise ApiError("source_dns_failed", "The official source could not be resolved", 502)
    for address in addresses:
        if not ipaddress.ip_address(address[4][0]).is_global:
            raise ApiError("private_source_blocked", "Private network source access is disabled")
    return url


class SourceFetcher:
    def __init__(self, transport=None):
        self.transport = transport

    async def fetch(self, url, allowed_hosts, limit=2_000_000):
        async with asyncio.timeout(45), httpx.AsyncClient(timeout=25, follow_redirects=False,
            transport=self.transport, trust_env=False,
            headers={"User-Agent": "Renulus/0.1 source-metadata-check"}) as client:
            for redirect in range(4):
                validate_url(url, allowed_hosts)
                if self.transport is None:
                    await public_url(url, allowed_hosts)
                client.cookies.clear()
                async with client.stream("GET", url) as response:
                    if response.status_code in (301, 302, 303, 307, 308):
                        url = urljoin(url, response.headers.get("location", ""))
                        try:
                            validate_url(url, allowed_hosts)
                        except ApiError:
                            raise ApiError("source_redirect_blocked", "Source redirect left the official host", 502)
                        continue
                    response.raise_for_status()
                    length = response.headers.get("content-length")
                    if length and length.isdigit() and int(length) > limit:
                        raise ApiError("source_metadata_too_large", "Source metadata exceeded the check limit", 413)
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > limit:
                            raise ApiError("source_metadata_too_large", "Source metadata exceeded the check limit", 413)
                    if not body:
                        raise ApiError("source_empty_response", "The source returned no publication data", 502)
                    if length and length.isdigit() and not response.headers.get("content-encoding") and len(body) != int(length):
                        raise ApiError("source_incomplete_response", "The publication response was incomplete", 502)
                    return bytes(body), dict(response.headers), str(response.url)
        raise ApiError("source_redirect_limit", "Source redirected too many times", 502)
