"""Fixed official endpoints, bounded reads, no redirects or ambient credentials."""
from __future__ import annotations

import ipaddress
import asyncio
import json
import logging
from urllib.parse import urlsplit

import httpx

from renulus.contracts import ApiError

HOSTS = frozenset({"eutils.ncbi.nlm.nih.gov", "www.ebi.ac.uk", "api.search.brave.com",
                  "api.tavily.com", "api.exa.ai"})
TOTAL_SECONDS = 25


def public_link(value: str) -> str | None:
    try:
        url = urlsplit(value)
        host = url.hostname or ""
        if url.scheme != "https" or url.username or url.password or url.port not in (None, 443):
            return None
        if not host or "." not in host or host.endswith((".localhost", ".local", ".internal")):
            return None
        try:
            if not ipaddress.ip_address(host).is_global:
                return None
        except ValueError:
            pass
        return value
    except (ValueError, TypeError):
        return None


class OfficialHTTP:
    def __init__(self, *, transport=None):
        self.transport = transport
        for name in ("httpx", "httpcore"):
            logging.getLogger(name).disabled = True

    async def request(self, method: str, url: str, *, params=None, body=None, headers=None,
                      max_bytes: int = 2 * 1024 * 1024) -> bytes:
        parsed = urlsplit(url)
        if public_link(url) is None or parsed.hostname not in HOSTS or parsed.fragment:
            raise ApiError("unsafe_retrieval_url", "Use a registered official retrieval endpoint.", 400)
        try:
            return await asyncio.wait_for(self._read(method, url, params, body, headers, max_bytes), TOTAL_SECONDS)
        except ApiError:
            raise
        except (httpx.HTTPError, OSError, TimeoutError):
            raise ApiError("retrieval_unavailable", "The selected source is unavailable. Check your connection and retry.", 503, True) from None

    async def _read(self, method, url, params, body, headers, max_bytes):
        async with httpx.AsyncClient(transport=self.transport, trust_env=False,
            follow_redirects=False, timeout=httpx.Timeout(25, connect=10)) as client:
            async with client.stream(method, url, params=params, json=body,
                headers={"User-Agent": "Renulus/0.1 literature discovery", **(headers or {})}) as response:
                if 300 <= response.status_code < 400:
                    raise ApiError("retrieval_redirect_blocked", "The source redirected outside the fixed retrieval route.", 502)
                if response.status_code in (401, 403):
                    raise ApiError("retrieval_authentication_required", "Check the selected retrieval key and its permissions.", 401)
                if response.status_code == 429:
                    raise ApiError("retrieval_provider_limit", "The selected source reached its usage limit. Retry later.", 429, True)
                if response.status_code == 404:
                    raise ApiError("article_unavailable", "This article is unavailable through the selected source.", 404)
                if response.status_code >= 400:
                    raise ApiError("retrieval_failed", "The selected source could not complete the request.", 503, True)
                data = bytearray()
                async for chunk in response.aiter_bytes(chunk_size=65536):
                    data.extend(chunk)
                    if len(data) > max_bytes:
                        raise ApiError("retrieval_size_limit", "The source response exceeds the retrieval size limit.", 413)
                return bytes(data)

    async def json(self, method: str, url: str, **kwargs) -> dict:
        try:
            result = json.loads(await self.request(method, url, **kwargs))
            if not isinstance(result, dict):
                raise ValueError()
            return result
        except (ValueError, TypeError):
            raise ApiError("retrieval_invalid_response", "The source returned an unsupported response.", 502) from None
