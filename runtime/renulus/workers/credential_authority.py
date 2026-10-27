"""Settings-only credential leases around the maintained ProviderManager/OAuth flow.

No provider selection or token exchange is implemented here. The existing auth
flow owns PKCE/OIDC and DPAPI; this adapter supplies host authority at its HTTP,
publication and owned callback seams. A login lease survives its start command.
"""
from __future__ import annotations

import asyncio
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass, field
from threading import Event, RLock
import time

import httpx

from renulus.runtime.auth import CodexLogin, JWKS_URL, REVOKE_URL, TOKEN_URL
from renulus.runtime.policy import BASE_URLS
from .broker_models import CredentialAuthority


class CredentialRefused(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


_scope = ContextVar("renulus_credential_authority", default=None)


@dataclass
class CredentialLease:
    authority: CredentialAuthority
    current: object
    publication_lock: object = field(default_factory=RLock)
    revoked: Event = field(default_factory=Event)
    credential_ref: str = field(init=False)
    credential_revision: int = field(init=False)

    def __post_init__(self):
        self.credential_ref = self.authority.credential_ref
        self.credential_revision = self.authority.credential_revision

    def check(self):
        if self.revoked.is_set():
            raise CredentialRefused("stale_revision")
        if self.authority.expires_at_ms <= int(time.time() * 1000):
            raise CredentialRefused("credential_authority_expired")
        try:
            valid = self.current() is True
        except Exception:
            valid = False
        if not valid:
            raise CredentialRefused("stale_revision")

    def endpoint(self, method, url):
        self.check()
        a = self.authority
        allowed = set()
        if a.action in {"connect", "refresh"}:
            allowed.add(("GET", BASE_URLS[a.provider_id] + "/models"))
            if a.provider_id == "codex":
                allowed.add(("POST", TOKEN_URL))
                if a.action == "connect":
                    allowed.add(("GET", JWKS_URL))
        if a.action == "forget" and a.provider_id == "codex":
            allowed.add(("POST", REVOKE_URL))
        if (method, str(url)) not in allowed:
            raise CredentialRefused("credential_endpoint_denied")

    def record(self, manager):
        a = self.authority
        if (manager._credential_refs[a.provider_id] != self.credential_ref
                or manager._credential_epochs[a.provider_id] != self.credential_revision):
            raise CredentialRefused("stale_revision")


class _CredentialClient(httpx.AsyncClient):
    def __init__(self, owner):
        self.owner = owner
        super().__init__(transport=owner.manager._http_transport, trust_env=False,
            follow_redirects=False, timeout=httpx.Timeout(20, connect=10),
            headers={"accept-encoding": "identity"})

    async def send(self, request, **kwargs):
        lease = self.owner.lease()
        lease.endpoint(request.method, request.url)
        lease.record(self.owner.manager)

        async def perform():
            async def receive():
                # Credential responses are bounded RAM, never worker artifacts.
                response = await super(_CredentialClient, self).send(request, **{**kwargs, "stream": True})
                try:
                    if 300 <= response.status_code < 400:
                        raise CredentialRefused("credential_endpoint_denied")
                    if response.headers.get("content-encoding", "identity").lower() != "identity":
                        raise CredentialRefused("credential_command_failed")
                    body = bytearray()
                    async for chunk in response.aiter_bytes(chunk_size=16384):
                        lease.check()
                        if len(body) + len(chunk) > 1024 * 1024:
                            raise CredentialRefused("credential_command_failed")
                        body.extend(chunk)
                    response._content = bytes(body)
                    lease.check()
                    return response
                finally:
                    await response.aclose()
            # A Python-injected transport is test authority, never a wire field.
            if self.owner.manager._http_transport is not None:
                return await receive()
            from .transport_guard import endpoint_network
            async with endpoint_network(str(request.url)):
                lease.check()
                return await receive()

        pending = asyncio.create_task(perform())
        try:
            while not pending.done():
                await asyncio.wait({pending}, timeout=0.02)
                lease.check()
            result = pending.result()
            lease.check()
            return result
        finally:
            if not pending.done():
                pending.cancel()
            # Settlement includes the real client/response finalizers.
            # Concurrent revoke, expiry and close can cancel the callback more
            # than once. Shield its HTTP cleanup from those later signals.
            while not pending.done():
                try:
                    await asyncio.shield(pending)
                except (Exception, asyncio.CancelledError):
                    pass
            try:
                pending.result()
            except (Exception, asyncio.CancelledError):
                pass


class _OwnedLogin(CodexLogin):
    def __init__(self, owner):
        super().__init__(owner.manager)
        self.owner = owner
        self.listeners = set()

    async def _stop_listener(self, attempt):
        server = attempt.server
        if server is not None:
            self.listeners.add(server)
        await super()._stop_listener(attempt)

    async def complete(self, login_id, query):
        lease = self.owner.logins.get(login_id)
        if lease is None:
            raise CredentialRefused("credential_authority_invalid")
        try:
            return await self.owner.run(lease, lambda: super(_OwnedLogin, self).complete(login_id, query))
        except asyncio.CancelledError:
            # Let CodexLogin's accepted callback write its neutral response and
            # close the socket. Raising here would skip that existing cleanup.
            return self.status(login_id)
        finally:
            # A callback rejected before the exchange (wrong state, replay) leaves
            # the legitimate pending login and its listener untouched. Only a
            # finished or cancelled attempt ends the lease; the callback still
            # writes and closes its socket, which the lifetime monitor joins.
            attempt = self._attempts.get(login_id)
            if attempt is None or attempt.status != "pending":
                lease.revoked.set()


class CredentialOwner:
    _state = ("_settings", "_catalogs", "_catalog_errors", "_capabilities",
        "_unsupported_models", "_credential_epochs", "_credential_refs", "_connection_versions")

    def __init__(self, manager):
        self.manager = manager
        self.logins = {}
        self.monitors = set()
        self.lock = asyncio.Lock()
        self.active = set()
        self.original_save = manager._save
        manager._client = lambda: _CredentialClient(self)
        manager._save = self.save
        manager._auth = _OwnedLogin(self)

    def lease(self):
        binding = _scope.get()
        if binding is None or binding[0] is not self:
            raise CredentialRefused("broker_authority_unbound")
        binding[1].check()
        return binding[1]

    def save(self):
        lease = self.lease()
        with lease.publication_lock:
            lease.check()
            self.original_save()
            provider = lease.authority.provider_id
            lease.credential_ref = self.manager._credential_refs[provider]
            lease.credential_revision = self.manager._credential_epochs[provider]
            # A later revoke cannot undo an already committed DPAPI write.
            # Rollback of failed subsequent work returns to that exact state.
            snapshot = _scope.get()[2]
            snapshot.clear()
            snapshot.update(self.snapshot())

    def snapshot(self):
        return {name: deepcopy(getattr(self.manager, name)) for name in self._state}

    async def run(self, lease, operation):
        async with self.lock:
            lease.check()
            lease.record(self.manager)
            # Failed/stale remote work must not leave a usable RAM credential.
            snapshot = self.snapshot()
            token = _scope.set((self, lease, snapshot))
            task = asyncio.current_task()
            self.active.add(task)
            try:
                result = await operation()
                lease.check()
                return result
            except BaseException:
                for name, value in snapshot.items():
                    setattr(self.manager, name, value)
                raise
            finally:
                self.active.discard(task)
                _scope.reset(token)

    def retain_login(self, login, lease):
        login_id = login["login_id"]
        self.logins[login_id] = lease
        task = asyncio.create_task(self._monitor(login_id, lease))
        self.monitors.add(task)
        task.add_done_callback(self.monitors.discard)

    async def _monitor(self, login_id, lease):
        try:
            while True:
                try:
                    lease.check()
                    lease.record(self.manager)
                except CredentialRefused:
                    break
                if self.manager.auth.status(login_id)["status"] not in {"pending", "exchanging"}:
                    break
                await asyncio.sleep(0.02)
        finally:
            lease.revoked.set()
            await self._cancel_login(login_id)
            self.logins.pop(login_id, None)

    async def _cancel_login(self, login_id):
        auth = self.manager.auth
        attempt = auth._attempts.get(login_id)
        exchange = attempt.exchange_task if attempt else None
        expiry = attempt.expiry_task if attempt else None
        if attempt:
            await auth.cancel(login_id)
        if exchange is not None and exchange is not asyncio.current_task():
            await asyncio.gather(exchange, return_exceptions=True)
        if expiry is not None and expiry is not asyncio.current_task():
            await asyncio.gather(expiry, return_exceptions=True)
        listeners = tuple(auth.listeners)
        for server in listeners:
            await server.wait_closed()
            auth.listeners.discard(server)

    async def cancel_login(self, login_id):
        lease = self.logins.get(login_id)
        if lease:
            lease.revoked.set()
        await self._cancel_login(login_id)
        return self.manager.auth.status(login_id)

    async def close(self):
        for lease in self.logins.values():
            lease.revoked.set()
        # Also cancel active start/refresh/native-secret jobs, then join them.
        current = asyncio.current_task()
        active = [task for task in self.active if task is not current]
        for task in active:
            task.cancel()
        await asyncio.gather(*active, return_exceptions=True)
        for login_id in list(self.manager.auth._attempts):
            await self._cancel_login(login_id)
        await asyncio.gather(*tuple(self.monitors), return_exceptions=True)


def credential_owner(manager):
    owner = getattr(manager, "_worker_credential_owner", None)
    if owner is None:
        owner = manager._worker_credential_owner = CredentialOwner(manager)
    return owner
