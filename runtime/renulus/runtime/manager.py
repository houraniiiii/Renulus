"""App-owned connections and cancellable, volatile approved generation."""
from __future__ import annotations

import asyncio
from contextlib import aclosing, suppress
from dataclasses import dataclass, field
import time
from typing import TYPE_CHECKING, AsyncIterator

import httpx

from renulus.contracts import ApiError, ContextScope, Event
from .hermes import HermesSubscriptionTransport
from .policy import ALLOWED_MODELS, BASE_URLS, require_provider, require_run_id, safe_error, validate_messages
from .protected import ConnectionStore

if TYPE_CHECKING:
    from renulus.storage import AppPaths


@dataclass
class _Run:
    stopped: asyncio.Event = field(default_factory=asyncio.Event)
    pending: asyncio.Task | None = None


class ProviderManager:
    def __init__(self, paths: AppPaths, *, transport=None, protector=None, http_transport=None):
        self.paths = paths
        self.store = ConnectionStore(paths.root, paths.state, protector)
        self._settings = self.store.load()
        self._transport = transport
        self._http_transport = http_transport
        self._runs: dict[str, _Run] = {}
        self._catalogs: dict[str, set[str]] = {}
        self._catalog_errors: dict[str, str] = {}
        self._credential_locks = {name: asyncio.Lock() for name in ALLOWED_MODELS}
        self._auth = None

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=self._http_transport, trust_env=False,
                                 timeout=httpx.Timeout(20, connect=10), follow_redirects=False)

    def _save(self) -> None:
        self.store.save(self._settings)

    def connections(self) -> dict:
        rows = []
        for provider, allowed in ALLOWED_MODELS.items():
            record = self._settings["connections"].get(provider)
            catalog = self._catalogs.get(provider)
            status = "disconnected" if not record else "configured"
            if record and catalog is not None:
                status = "connected" if catalog else "no_allowed_models"
            if provider in self._catalog_errors:
                status = self._catalog_errors[provider]
            rows.append({"provider": provider, "status": status,
                         "allowed_models": list(allowed),
                         "models": [{"id": model,
                                     "availability": "unknown" if catalog is None else
                                     "available" if model in catalog else "unavailable",
                                     "image_input": "unverified"} for model in allowed]})
        return {"selected_provider": self._settings["selected_provider"], "connections": rows}

    def status(self) -> dict:
        return {**self.connections(), "active_runs": list(self._runs),
                "runtime": "hermes-provider-transports",
                "general_automation": False, "auxiliary_model_calls": False,
                "hermes_persistence": False, "temporary_scope": "volatile",
                "live_provider_verified": False}

    def select(self, provider: str) -> dict:
        require_provider(provider)
        if provider not in self._settings["connections"]:
            raise ApiError("connection_required", "Connect this subscription before selecting it.", 409)
        self._settings["selected_provider"] = provider
        self._save()
        return self.connections()

    async def connect_go(self, api_key: str, *, select: bool = False) -> dict:
        if not isinstance(api_key, str) or not api_key.strip() or len(api_key) > 8192:
            raise ApiError("invalid_connection", "Enter your OpenCode Go subscription key.")
        async with self._credential_locks["opencode-go"]:
            # Discovery tests the explicitly entered credential without inference.
            catalog = await self._fetch_catalog("opencode-go", api_key.strip())
            self._settings["connections"]["opencode-go"] = {"access_token": api_key.strip()}
            self._catalogs["opencode-go"] = catalog
            self._catalog_errors.pop("opencode-go", None)
            if select:
                self._settings["selected_provider"] = "opencode-go"
            self._save()
        return self.connections()

    async def _fetch_catalog(self, provider: str, token: str) -> set[str]:
        try:
            async with self._client() as client:
                result = await client.get(BASE_URLS[provider] + "/models",
                                          headers={"Authorization": "Bearer " + token})
                result.raise_for_status()
                data = result.json()
            ids = {row["id"] for row in data.get("data", []) if isinstance(row, dict) and isinstance(row.get("id"), str)}
            return ids.intersection(ALLOWED_MODELS[provider])
        except Exception as error:
            raise safe_error(error) from None

    async def _access_token(self, provider: str) -> str:
        record = self._settings["connections"].get(provider)
        if not record:
            raise ApiError("connection_required", "Connect your selected subscription in Renulus.", 409)
        if provider == "codex" and record.get("expires_at", 0) <= time.time() + 60:
            async with self._credential_locks[provider]:
                record = self._settings["connections"].get(provider)
                if not record:
                    raise ApiError("connection_required", "Reconnect your selected subscription.", 409)
                if record.get("expires_at", 0) <= time.time() + 60:
                    if not record.get("refresh_token"):
                        raise ApiError("authentication_required", "Continue with ChatGPT to reconnect.", 401, True)
                    from .auth import TOKEN_URL, RESOURCE, PLAN_SCOPE
                    try:
                        async with self._client() as client:
                            response = await client.post(TOKEN_URL, data={
                                "grant_type": "refresh_token", "client_id": record["client_id"],
                                "refresh_token": record["refresh_token"], "resource": RESOURCE})
                            response.raise_for_status()
                            tokens = response.json()
                        if PLAN_SCOPE not in set(tokens.get("scope", " ".join(record["scopes"])).split()):
                            raise ApiError("plan_permission_required", "Authorize ChatGPT plan usage before continuing.", 403)
                        record.update(access_token=tokens["access_token"],
                                      refresh_token=tokens.get("refresh_token", record["refresh_token"]),
                                      expires_at=time.time() + float(tokens["expires_in"]))
                        self._save()
                    except Exception as error:
                        self._catalogs.pop(provider, None)
                        self._catalog_errors[provider] = "authentication_required"
                        raise safe_error(error) from None
        return record["access_token"]

    async def refresh(self, provider: str) -> dict:
        require_provider(provider)
        try:
            token = await self._access_token(provider)
            self._catalogs[provider] = await self._fetch_catalog(provider, token)
            self._catalog_errors.pop(provider, None)
        except Exception as error:
            public = safe_error(error)
            self._catalogs.pop(provider, None)
            self._catalog_errors[provider] = public.code
            raise public from None
        return self.connections()

    async def disconnect(self, provider: str) -> dict:
        require_provider(provider)
        # Stop active runs before dropping credentials. No switch to another provider.
        for run_id in list(self._runs):
            await self.cancel(run_id)
        if provider == "codex" and self._auth:
            await self._auth.cancel_all()
        record = self._settings["connections"].pop(provider, None)
        self._catalogs.pop(provider, None)
        self._catalog_errors.pop(provider, None)
        if self._settings["selected_provider"] == provider:
            self._settings["selected_provider"] = None
        self._save()
        if provider == "codex" and record and record.get("refresh_token"):
            from .auth import REVOKE_URL
            try:
                async with self._client() as client:
                    response = await client.post(REVOKE_URL, data={
                        "client_id": record["client_id"], "token": record["refresh_token"],
                        "token_type_hint": "refresh_token"})
                    response.raise_for_status()
            except Exception:
                return {**self.connections(), "revocation": "failed", "recovery": "Remove Renulus in your ChatGPT account's connected apps."}
        return self.connections()

    @property
    def auth(self):
        if self._auth is None:
            from .auth import CodexLogin
            self._auth = CodexLogin(self)
        return self._auth

    async def cancel(self, run_id: str) -> bool:
        require_run_id(run_id)
        run = self._runs.get(run_id)
        if not run:
            return False
        run.stopped.set()
        if run.pending and not run.pending.done():
            run.pending.cancel()
        return True

    async def stream(self, messages: list[dict], *, scope: ContextScope, run_id: str,
                     model: str | None = None, system: str | None = None,
                     purpose: str = "explain") -> AsyncIterator[str]:
        async with aclosing(self.events(messages, scope=scope, run_id=run_id, model=model,
                                        system=system, purpose=purpose)) as events:
            async for item in events:
                if item.type == "delta":
                    yield item.payload["text"]
                elif item.type == "error":
                    raise ApiError(item.payload["code"], item.payload["message"],
                                   503, item.payload["retryable"])
                elif item.type == "cancelled":
                    raise asyncio.CancelledError()

    async def events(self, messages: list[dict], *, scope: ContextScope | dict, run_id: str,
                     model: str | None = None, system: str | None = None,
                     purpose: str = "explain") -> AsyncIterator[Event]:
        require_run_id(run_id)
        if run_id in self._runs:
            raise ApiError("run_already_active", "This run is already active.", 409)
        # Scope is compulsory even though F0 never writes conversation data.
        if not isinstance(scope, ContextScope):
            try:
                scope = ContextScope.model_validate(scope)
            except Exception:
                raise ApiError("invalid_scope", "Choose an explicit context scope before generation.") from None
        messages = validate_messages(messages)
        if system is not None:
            if not isinstance(system, str) or len(system) > 100_000:
                raise ApiError("invalid_system", "Supply a bounded teaching instruction.")
            messages.insert(0, {"role": "system", "content": system})
        run = _Run()
        self._runs[run_id] = run
        sequence = 0

        def event(kind: str, **payload) -> Event:
            nonlocal sequence
            sequence += 1
            return Event(run_id=run_id, sequence=sequence, type=kind, payload=payload)

        iterator = None
        try:
            provider = self._settings["selected_provider"]
            if provider is None:
                raise ApiError("connection_required", "Select an app-owned subscription connection.", 409)
            require_provider(provider)
            if model is not None and model not in ALLOWED_MODELS[provider]:
                raise ApiError("model_not_allowed", "Choose an allowed model in the selected subscription.")
            catalog = self._catalogs.get(provider)
            if catalog is None:
                raise ApiError("capabilities_unverified", "Refresh the selected connection before generation.", 409, True)
            chosen = model or next((m for m in ALLOWED_MODELS[provider] if m in catalog), None)
            if not chosen or chosen not in catalog:
                raise ApiError("model_unavailable", "No requested allowed model is available in the selected subscription.", 409, True)
            token = await self._access_token(provider)
            if run.stopped.is_set():
                yield event("cancelled")
                return
            transport = self._transport
            if transport is None:
                transport = HermesSubscriptionTransport(self.paths.source_root, self.paths.root,
                                                         http_transport=self._http_transport)
                self._transport = transport
            yield event("started", provider=provider, model=chosen, scope=scope.kind.value)
            iterator = transport.stream(provider, chosen, token, messages).__aiter__()
            while not run.stopped.is_set():
                run.pending = asyncio.create_task(anext(iterator))
                try:
                    item = await run.pending
                except StopAsyncIteration:
                    raise ApiError("provider_stream_incomplete", "The subscription ended without completion.", 503, True) from None
                except asyncio.CancelledError:
                    if not run.stopped.is_set():
                        raise
                    break
                finally:
                    run.pending = None
                if run.stopped.is_set():
                    break
                if item["type"] == "completed":
                    yield event("completed", provider=provider, model=chosen)
                    return
                if item["type"] != "delta" or not isinstance(item.get("text"), str):
                    raise ApiError("provider_protocol_error", "The runtime refused an unexpected subscription event.", 503)
                yield event("delta", text=item["text"])
            yield event("cancelled")
        except asyncio.CancelledError:
            run.stopped.set()
            raise
        except Exception as error:
            public = safe_error(error)
            yield event("error", code=public.code, message=public.message, retryable=public.retryable)
        finally:
            if run.pending:
                run.pending.cancel()
                await asyncio.gather(run.pending, return_exceptions=True)
            if iterator and hasattr(iterator, "aclose"):
                with suppress(Exception, asyncio.CancelledError):
                    await iterator.aclose()
            self._runs.pop(run_id, None)
            # No transcripts, request dumps, spillover, memories or trajectories.
            messages.clear()

    async def close(self) -> None:
        for run_id in list(self._runs):
            await self.cancel(run_id)
        if self._auth:
            await self._auth.cancel_all()
