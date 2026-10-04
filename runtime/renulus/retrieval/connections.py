"""Separate profile-bound retrieval namespace reusing the approved DPAPI store."""
from __future__ import annotations

import hashlib
from copy import deepcopy
import re

from renulus.contracts import ApiError
from renulus.runtime.protected import ConnectionStore

TOOLS = ("ncbi", "brave", "tavily", "exa")
FREE = ("europe-pmc", "pubmed")


class RetrievalConnections:
    def __init__(self, paths, *, protector=None):
        self.store = ConnectionStore(paths.root, paths.state, protector)
        # Assign both before load: never open F0's subscription record.
        self.store.path = paths.state / "retrieval" / "connections.dpapi"
        self.store.entropy = hashlib.sha256(("Renulus.retrieval.v1:" + str(paths.root.resolve())).encode()).digest()
        if not self.store.path.resolve().is_relative_to(paths.root.resolve()):
            raise ApiError("invalid_profile", "Retrieval connection storage leaves the app profile.")
        self.settings = self.store.load()
        self.settings.setdefault("selected_provider", None)
        if self.settings.get("selected_provider") not in (None, *TOOLS):
            raise ApiError("retrieval_record_invalid", "Reconnect this profile's retrieval tools.", 503)
        for provider, record in self.settings["connections"].items():
            if provider not in TOOLS or not isinstance(record, dict) or not isinstance(record.get("enabled", False), bool) or any(type(record.get(name, default)) is not int or not 0 <= record.get(name, default) <= 10000 for name, default in (("daily_request_limit", 100), ("daily_credit_limit", 20))) or not isinstance(record.get("api_key", ""), str):
                raise ApiError("retrieval_record_invalid", "Reconnect this profile's retrieval tools.", 503)

    def _save(self, settings):
        # A failed DPAPI write cannot activate an unpersisted connection.
        self.store.save(settings)
        self.settings = settings

    def config(self, provider: str) -> dict:
        if provider not in (*TOOLS, *FREE):
            raise ApiError("retrieval_provider_unknown", "Choose a supported retrieval source.")
        record = self.settings["connections"].get(provider, {})
        return {"enabled": False, "daily_request_limit": 100, "daily_credit_limit": 20, **record}

    def configure(self, provider: str, *, api_key: str | None = None, enabled: bool = False,
                  daily_request_limit: int = 100, daily_credit_limit: int = 20) -> None:
        self.config(provider)
        if not isinstance(enabled, bool):
            raise ApiError("invalid_retrieval_settings", "Choose whether this tool is enabled.")
        if provider not in TOOLS:
            raise ApiError("retrieval_key_not_supported", "This public source needs no key.")
        record = self.config(provider)
        if api_key is not None:
            if not isinstance(api_key, str) or not api_key.strip() or len(api_key) > 8192 or re.search(r"\s|[\x00-\x1f\x7f]", api_key.strip()):
                raise ApiError("invalid_retrieval_key", "Enter a valid retrieval key.")
            record["api_key"] = api_key.strip()
        if enabled and not record.get("api_key"):
            raise ApiError("retrieval_key_required", "Add your own key before enabling this tool.", 409)
        if type(daily_request_limit) is not int or type(daily_credit_limit) is not int or not 0 <= daily_request_limit <= 10000 or not 0 <= daily_credit_limit <= 10000:
            raise ApiError("invalid_retrieval_limit", "Choose daily limits between zero and 10000.")
        record.update(enabled=enabled, daily_request_limit=daily_request_limit,
                      daily_credit_limit=daily_credit_limit)
        settings = deepcopy(self.settings)
        settings["connections"][provider] = record
        if not enabled and settings["selected_provider"] == provider:
            settings["selected_provider"] = None
        self._save(settings)

    def select(self, provider: str | None) -> None:
        if provider is not None:
            record = self.config(provider)
            if provider not in TOOLS or not record["enabled"] or not record.get("api_key"):
                raise ApiError("retrieval_tool_disabled", "Enable a configured tool before selecting it.", 409)
        settings = deepcopy(self.settings)
        settings["selected_provider"] = provider
        self._save(settings)

    def disconnect(self, provider: str) -> None:
        self.config(provider)
        settings = deepcopy(self.settings)
        settings["connections"].pop(provider, None)
        if settings["selected_provider"] == provider:
            settings["selected_provider"] = None
        self._save(settings)
