"""App-owned connections and cancellable, volatile approved generation."""
from __future__ import annotations

import asyncio
from contextlib import aclosing, suppress
from dataclasses import dataclass, field
import time
from typing import TYPE_CHECKING, AsyncIterator

import httpx

from renulus.contracts import ApiError, ContextScope, Event, durable_id
from .context import CONTEXT_BUDGET, OUTPUT_RESERVATION, SUMMARY_MAX_CHARS, HermesContextAdapter
from .hermes import HermesSubscriptionTransport
from .inputs import has_images
from .policy import ALLOWED_MODELS, BASE_URLS, rejection_kind, require_provider, require_run_id, safe_error, validate_messages
from .protected import ConnectionStore

if TYPE_CHECKING:
    from renulus.storage import AppPaths


@dataclass
class _Run:
    stopped: asyncio.Event = field(default_factory=asyncio.Event)
    pending: asyncio.Task | None = None
    provider: str | None = None


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
        self._capabilities: dict[tuple[str, str], dict] = {}
        self._unsupported_models: set[tuple[str, str]] = set()
        self._completed_requests = 0
        self._credential_locks = {name: asyncio.Lock() for name in ALLOWED_MODELS}
        self._connection_versions = {name: 0 for name in ALLOWED_MODELS}
        self._auth = None
        self._context = None

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=self._http_transport, trust_env=False,
                                 timeout=httpx.Timeout(20, connect=10), follow_redirects=False)

    def _save(self) -> None:
        self.store.save(self._settings)

    def _require_connection_version(self, provider: str, version: int) -> None:
        if self._connection_versions[provider] != version:
            raise ApiError("connection_changed", "The connection changed during the request. Retry with the current connection.", 409, True)

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
                         "models": [self._model_status(provider, model, catalog) for model in allowed]})
        return {"selected_provider": self._settings["selected_provider"], "connections": rows}

    def _model_status(self, provider: str, model: str, catalog: set[str] | None) -> dict:
        unavailable = (provider, model) in self._unsupported_models
        missing = catalog is not None and model not in catalog
        observed = self._capabilities.get((provider, model), {})
        fallback = "account_unsupported" if unavailable or missing else "unknown"
        return {"id": model,
                "availability": "account_unsupported" if unavailable else
                "unknown" if catalog is None else "unavailable" if missing else "available",
                "text_input": fallback if unavailable or missing else observed.get("text", "unknown"),
                "image_input": fallback if unavailable or missing else observed.get("image", "unknown"),
                "capability_evidence": {"text": observed.get("text_evidence", "model_not_in_catalogue" if missing else "none"),
                                        "image": observed.get("image_evidence", "model_not_in_catalogue" if missing else "none")},
                "image_interpretation_verified": False}

    def _clear_capabilities(self, provider: str) -> None:
        self._capabilities = {key: value for key, value in self._capabilities.items() if key[0] != provider}
        self._unsupported_models = {key for key in self._unsupported_models if key[0] != provider}

    def _observe_completion(self, provider: str, model: str, *, images: bool) -> None:
        observed = self._capabilities.setdefault((provider, model), {})
        observed.update(text="supported", text_evidence="completed_request")
        if images:
            observed.update(image="supported", image_evidence="completed_request")
        self._completed_requests += 1

    def status(self) -> dict:
        return {**self.connections(), "active_runs": list(self._runs),
                "runtime": "hermes-provider-transports",
                "general_automation": False, "auxiliary_model_calls": False,
                "hermes_persistence": False, "temporary_scope": "volatile",
                "image_route": "typed-inline-input",
                "input_limits": {"images": 4, "per_image_bytes": 8 * 1024 * 1024,
                                 "total_image_bytes": 16 * 1024 * 1024, "image_pixels": 16_000_000},
                "live_provider_verified": self._completed_requests > 0 and self._http_transport is None
                    and isinstance(self._transport, HermesSubscriptionTransport)}

    @property
    def context(self) -> HermesContextAdapter:
        if self._context is None:
            self._context = HermesContextAdapter(HermesSubscriptionTransport(self.paths.source_root, self.paths.root))
        return self._context

    def _stop_provider_runs(self, provider: str) -> None:
        for run in self._runs.values():
            if run.provider == provider:
                run.stopped.set()
                if run.pending and not run.pending.done():
                    run.pending.cancel()

    def select(self, provider: str) -> dict:
        require_provider(provider)
        if provider not in self._settings["connections"]:
            raise ApiError("connection_required", "Connect this subscription before selecting it.", 409)
        previous = self._settings["selected_provider"]
        if previous and previous != provider:
            self._stop_provider_runs(previous)
        self._settings["selected_provider"] = provider
        self._save()
        return self.connections()

    async def connect_go(self, api_key: str, *, select: bool = False) -> dict:
        if not isinstance(api_key, str) or not api_key.strip() or len(api_key) > 8192:
            raise ApiError("invalid_connection", "Enter your OpenCode Go subscription key.")
        async with self._credential_locks["opencode-go"]:
            version = self._connection_versions["opencode-go"]
            # Discovery tests the explicitly entered credential without inference.
            catalog = await self._fetch_catalog("opencode-go", api_key.strip())
            self._require_connection_version("opencode-go", version)
            self._stop_provider_runs("opencode-go")
            self._connection_versions["opencode-go"] += 1
            self._settings["connections"]["opencode-go"] = {"access_token": api_key.strip()}
            self._clear_capabilities("opencode-go")
            self._catalogs["opencode-go"] = catalog
            self._catalog_errors.pop("opencode-go", None)
            if select:
                previous = self._settings["selected_provider"]
                if previous and previous != "opencode-go":
                    self._stop_provider_runs(previous)
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
            # ChatGPT plan access has models[].slug/visibility; compatible APIs
            # expose data[].id. Neither listing establishes image capability.
            rows = data.get("models", data.get("data", [])) if provider == "codex" else data.get("data", [])
            if not isinstance(rows, list):
                raise ApiError("provider_catalogue_invalid", "The selected subscription returned an invalid model catalogue.", 503, True)
            ids = {row.get("slug", row.get("id")) for row in rows if isinstance(row, dict)
                   and row.get("visibility", "list") == "list"
                   and isinstance(row.get("slug", row.get("id")), str)}
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
                    from .auth import TOKEN_URL, RESOURCE, validate_plan_token
                    version = self._connection_versions[provider]
                    try:
                        async with self._client() as client:
                            response = await client.post(TOKEN_URL, data={
                                "grant_type": "refresh_token", "client_id": record["client_id"],
                                "refresh_token": record["refresh_token"], "resource": RESOURCE})
                            response.raise_for_status()
                            tokens = response.json()
                        self._require_connection_version(provider, version)
                        validated = validate_plan_token(tokens, previous_scopes=record.get("scopes", []))
                        record.update(validated, refresh_token=tokens.get("refresh_token", record["refresh_token"]))
                        self._save()
                    except Exception as error:
                        self._require_connection_version(provider, version)
                        public = safe_error(error)
                        self._catalogs.pop(provider, None)
                        self._catalog_errors[provider] = ("authentication_required" if public.code in {
                            "invalid_token_response", "plan_permission_required"} else public.code)
                        raise public from None
        return record["access_token"]

    async def refresh(self, provider: str) -> dict:
        require_provider(provider)
        version = self._connection_versions[provider]
        try:
            token = await self._access_token(provider)
            catalog = await self._fetch_catalog(provider, token)
            self._require_connection_version(provider, version)
            self._catalogs[provider] = catalog
            # Explicit refresh permits retry after an account-specific rejection.
            self._clear_capabilities(provider)
            self._catalog_errors.pop(provider, None)
        except Exception as error:
            self._require_connection_version(provider, version)
            public = safe_error(error)
            self._catalogs.pop(provider, None)
            if provider in self._settings["connections"]:
                self._catalog_errors[provider] = public.code
            else:
                self._catalog_errors.pop(provider, None)
            raise public from None
        return self.connections()

    async def disconnect(self, provider: str) -> dict:
        require_provider(provider)
        self._connection_versions[provider] += 1
        # Stop active runs before dropping credentials. No switch to another provider.
        self._stop_provider_runs(provider)
        if provider == "codex" and self._auth:
            await self._auth.cancel_all()
        record = self._settings["connections"].pop(provider, None)
        if provider == "codex" and record:
            # Sign-out removes credentials, not the stable registration for this
            # app/account/host. Reconnect must not create a new dynamic client.
            self._settings["codex_registration"] = {
                name: record[name] for name in ("client_id", "subject", "issuer") if name in record}
        self._catalogs.pop(provider, None)
        self._catalog_errors.pop(provider, None)
        self._clear_capabilities(provider)
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

    def _route(self, model: str | None) -> tuple[str, str]:
        provider = self._settings["selected_provider"]
        if provider is None:
            raise ApiError("connection_required", "Select an app-owned subscription connection.", 409)
        require_provider(provider)
        if model is not None and model not in ALLOWED_MODELS[provider]:
            raise ApiError("model_not_allowed", "Choose an allowed model in the selected subscription.")
        catalog = self._catalogs.get(provider)
        if catalog is None:
            raise ApiError("capabilities_unverified", "Refresh the selected connection before generation.", 409, True)
        chosen = model or next((item for item in ALLOWED_MODELS[provider] if item in catalog), None)
        if not chosen or chosen not in catalog:
            raise ApiError("model_unavailable", "No requested allowed model is available in the selected subscription.", 409, True)
        if (provider, chosen) in self._unsupported_models:
            raise ApiError("account_model_unsupported", "The selected account cannot use this model. Refresh the connection to retry.", 409)
        return provider, chosen

    async def compact(self, messages: list[dict], *, scope: ContextScope, run_id: str,
                      model: str | None = None, system: str | None = None, force: bool = True) -> dict:
        """Explicit bounded compaction; summaries use the shared stream seam."""
        require_run_id(run_id)
        if run_id in self._runs:
            raise ApiError("run_already_active", "This run is already active.", 409)
        if not isinstance(scope, ContextScope):
            try:
                scope = ContextScope.model_validate(scope)
            except Exception:
                raise ApiError("invalid_scope", "Choose an explicit context scope before compaction.") from None
        prepared = validate_messages(messages)
        if system is not None:
            if not isinstance(system, str) or len(system) > 100_000:
                raise ApiError("invalid_system", "Supply a bounded teaching instruction.")
            prepared.insert(0, {"role": "system", "content": system})
        provider, chosen = self._route(model)
        plan = self.context.plan(prepared, provider=provider, model=chosen, force=force)
        result = await self._finish_context(plan, scope=scope, run_id=run_id, provider=provider, model=chosen)
        return {**result, "provider": provider, "model": chosen, "scope": scope.model_dump(mode="json"),
                "engine": "hermes-context-compressor", "persisted": False}

    async def _finish_context(self, plan, *, scope: ContextScope, run_id: str, provider: str, model: str) -> dict:
        if plan.turns is None:
            return self.context.finish(plan)
        if self._settings["selected_provider"] != provider:
            raise ApiError("connection_changed", "The selected connection changed before compaction. Retry the request.", 409, True)
        identity = self._settings["connections"].get(provider)
        summary = []
        size = 0
        try:
            async with aclosing(self.stream(self.context.summary_messages(plan), scope=scope,
                run_id=run_id, model=model, purpose="compaction")) as stream:
                async for delta in stream:
                    size += len(delta)
                    if size > SUMMARY_MAX_CHARS:
                        raise ApiError("compaction_failed", "The approved summary exceeded the context budget. Input was preserved.", 409)
                    summary.append(delta)
            if self._settings["selected_provider"] != provider or self._settings["connections"].get(provider) is not identity:
                raise ApiError("connection_changed", "The selected account changed during compaction. Input was preserved.", 409, True)
            return self.context.finish(plan, "".join(summary))
        finally:
            summary.clear()

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
                                   item.payload.get("status", 503), item.payload["retryable"])
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
        provider = chosen = None
        version = None
        images = has_images(messages)
        try:
            provider, chosen = self._route(model)
            run.provider = provider
            version = self._connection_versions[provider]
            catalog = self._catalogs.get(provider)
            capability = self._model_status(provider, chosen, catalog)
            if images and capability["image_input"] == "account_unsupported":
                raise ApiError("image_input_unsupported", "This account rejected image input for the selected model. Choose an explicitly available image route.", 409)
            run.pending = asyncio.create_task(self._access_token(provider))
            try:
                token = await run.pending
            except asyncio.CancelledError:
                if not run.stopped.is_set():
                    raise
                yield event("cancelled")
                return
            finally:
                run.pending = None
            if run.stopped.is_set():
                yield event("cancelled")
                return
            transport = self._transport
            if transport is None:
                transport = HermesSubscriptionTransport(self.paths.source_root, self.paths.root,
                                                         http_transport=self._http_transport)
                self._transport = transport
            yield event("started", provider=provider, model=chosen, scope=scope.kind.value,
                        purpose=purpose, input_capability="image" if images else "text",
                        capability_status=capability["image_input" if images else "text_input"])
            if purpose != "compaction":
                plan = self.context.plan(messages, provider=provider, model=chosen)
                if plan.turns is not None:
                    identity = self._settings["connections"].get(provider)
                    yield event("progress", stage="compaction", status="started",
                                estimated_tokens=plan.before, provider=provider, model=chosen)
                    run.pending = asyncio.create_task(self._finish_context(plan, scope=scope,
                        run_id=durable_id("compact"), provider=provider, model=chosen))
                    try:
                        result = await run.pending
                    except asyncio.CancelledError:
                        if not run.stopped.is_set():
                            raise
                        yield event("cancelled")
                        return
                    finally:
                        run.pending = None
                    if run.stopped.is_set():
                        yield event("cancelled")
                        return
                    if self._settings["selected_provider"] != provider or self._settings["connections"].get(provider) is not identity:
                        raise ApiError("connection_changed", "The selected account changed during compaction. Retry the request.", 409, True)
                    messages = result["messages"]
                    yield event("progress", stage="compaction", status="completed",
                                estimated_tokens_before=result["estimated_tokens_before"],
                                estimated_tokens_after=result["estimated_tokens_after"], persisted=False)
            elif self.context.estimate(messages) > CONTEXT_BUDGET - OUTPUT_RESERVATION:
                raise ApiError("context_limit", "The compaction request exceeds the approved context budget. Input was preserved.", 409)
            if run.stopped.is_set():
                yield event("cancelled")
                return
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
                    self._observe_completion(provider, chosen, images=images)
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
            if run.stopped.is_set():
                yield event("cancelled")
                return
            if provider and version != self._connection_versions[provider]:
                yield event("error", code="connection_changed",
                            message="The connection changed during the request. Retry with the current connection.",
                            retryable=True, status=409)
                return
            rejected = rejection_kind(error, images=images)
            if provider and chosen and rejected == "image":
                self._capabilities.setdefault((provider, chosen), {}).update(
                    image="account_unsupported", image_evidence="provider_rejection")
                public = ApiError("image_input_unsupported", "The selected account rejected image input for this model. No other model or subscription was tried.", 409)
            elif provider and chosen and rejected == "model":
                self._unsupported_models.add((provider, chosen))
                observed = self._capabilities.setdefault((provider, chosen), {})
                observed.update(text_evidence="provider_rejection", image_evidence="provider_rejection")
                public = ApiError("account_model_unsupported", "The selected account cannot use this model. Refresh its capabilities.", 409, True)
            else:
                public = safe_error(error)
            if provider and public.code == "authentication_required":
                self._catalogs.pop(provider, None)
                self._catalog_errors[provider] = public.code
                self._clear_capabilities(provider)
            yield event("error", code=public.code, message=public.message, retryable=public.retryable, status=public.status)
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
