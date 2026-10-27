# SPDX-License-Identifier: MIT
"""MCP OAuth credentials: private to the Python broker, never to Node or native OpenCode.

Tokens live only in a profile-bound DPAPI record (the retrieval-connection pattern)
and broker memory. Node holds a credential *reference* and revision. Discovery and
refresh are explicit commands/connection-scoped work; the network exchange is
supplied by the caller so it passes the same admitted, DNS-pinned transport as every
other request. No browser login is started here (never from model execution).
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
import hashlib
from pathlib import Path
import time
from urllib.parse import urlsplit

from renulus.contracts import ApiError
from renulus.runtime.protected import ConnectionStore

REFRESH_LEEWAY_SECONDS = 30


class McpCredentialError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _origin(url):
    parts = urlsplit(url)
    if parts.scheme not in {"https", "http"} or not parts.hostname or parts.username or parts.password or parts.fragment:
        raise McpCredentialError("mcp_credential_url_invalid")
    return parts.scheme, parts.hostname, parts.port or (443 if parts.scheme == "https" else 80)


class McpCredentials:
    def __init__(self, profile: Path, state: Path, *, protector=None, clock=time.time):
        self.store = ConnectionStore(profile, state, protector)
        self.store.path = state / "mcp" / "connections.dpapi"
        self.store.entropy = hashlib.sha256(("Renulus.mcp.v1:" + str(profile.resolve())).encode()).digest()
        if not self.store.path.resolve().is_relative_to(profile.resolve()):
            raise McpCredentialError("mcp_credential_storage_invalid")
        self.clock, self.refreshing = clock, asyncio.Lock()
        try:
            self.settings = self.store.load()
        except ApiError:
            raise McpCredentialError("mcp_credential_record_invalid") from None

    def _save(self, settings):
        # A failed protected write leaves the previous record authoritative.
        self.store.save(settings)
        self.settings = settings

    def _record(self, ref, revision=None):
        record = self.settings["connections"].get(ref)
        if record is None or (revision is not None and record["revision"] != revision):
            raise McpCredentialError("mcp_credential_stale")
        return record

    def put(self, ref, *, revision, resource, client_id, access_token, refresh_token=None, expires_at, token_endpoint=None):
        """Explicit Settings/login handoff only; replacing a record requires a newer revision."""
        _origin(resource)
        settings = deepcopy(self.settings)
        old = settings["connections"].get(ref)
        if old is not None and revision <= old["revision"]:
            raise McpCredentialError("mcp_credential_stale")
        settings["connections"][ref] = {"revision": revision, "resource": resource, "client_id": client_id,
            "access_token": access_token, "refresh_token": refresh_token, "expires_at": expires_at,
            "token_endpoint": token_endpoint}
        self._save(settings)

    def forget(self, ref):
        settings = deepcopy(self.settings)
        settings["connections"].pop(ref, None)
        self._save(settings)

    def metadata(self, ref, revision):
        record = self._record(ref, revision)
        return {"revision": record["revision"], "resource": record["resource"], "expires_at": record["expires_at"],
            "has_refresh": bool(record["refresh_token"]), "token_endpoint": record["token_endpoint"]}

    def secrets(self, ref):
        """Values that must never appear in protocol data returned to Node."""
        record = self.settings["connections"].get(ref) or {}
        return [v for v in (record.get("access_token"), record.get("refresh_token")) if v]

    async def discover(self, ref, revision, get_json):
        """RFC 9728 protected-resource metadata, then RFC 8414 authorization-server metadata."""
        record = self._record(ref, revision)
        scheme, host, port = _origin(record["resource"])
        base = f"{scheme}://{host}:{port}"
        resource = await get_json(base + "/.well-known/oauth-protected-resource")
        servers = resource.get("authorization_servers")
        if not isinstance(servers, list) or not servers or not isinstance(servers[0], str):
            raise McpCredentialError("mcp_discovery_invalid")
        issuer = servers[0].rstrip("/")
        _origin(issuer)
        metadata = await get_json(issuer + "/.well-known/oauth-authorization-server")
        endpoint = metadata.get("token_endpoint")
        if not isinstance(endpoint, str) or _origin(endpoint) != _origin(issuer):
            raise McpCredentialError("mcp_discovery_invalid")
        self._record(ref, revision)  # a newer revision may have replaced it while waiting
        settings = deepcopy(self.settings)
        settings["connections"][ref]["token_endpoint"] = endpoint
        self._save(settings)
        return self.metadata(ref, revision)

    async def refresh(self, ref, revision, post_form, *, force=False):
        async with self.refreshing:
            record = self._record(ref, revision)
            if not force and record["expires_at"] - self.clock() > REFRESH_LEEWAY_SECONDS:
                return
            if not record["refresh_token"] or not record["token_endpoint"]:
                raise McpCredentialError("mcp_credential_expired")
            status, body = await post_form(record["token_endpoint"], {"grant_type": "refresh_token",
                "refresh_token": record["refresh_token"], "client_id": record["client_id"]})
            token = body.get("access_token")
            if status != 200 or not isinstance(token, str) or not token or str(body.get("token_type", "Bearer")).lower() != "bearer":
                raise McpCredentialError("mcp_refresh_failed")
            lifetime = body.get("expires_in")
            self._record(ref, revision)  # a revoke/replace during the exchange discards its result
            settings = deepcopy(self.settings)
            fresh = settings["connections"][ref]
            fresh.update(access_token=token, expires_at=self.clock() + (lifetime if type(lifetime) is int and lifetime > 0 else 300))
            if isinstance(body.get("refresh_token"), str) and body["refresh_token"]:
                fresh["refresh_token"] = body["refresh_token"]
            self._save(settings)

    async def headers(self, ref, revision, url, post_form, *, refresh=True):
        """Authorization for one admitted request to the record's own origin only."""
        record = self._record(ref, revision)
        if _origin(url) != _origin(record["resource"]):
            raise McpCredentialError("mcp_credential_origin")
        if refresh:
            await self.refresh(ref, revision, post_form)
        return {"authorization": "Bearer " + self._record(ref, revision)["access_token"]}
