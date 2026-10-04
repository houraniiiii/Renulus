"""Reuse Hermes wire conversion without its agent, plugin or persistence startup."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import logging
import sys
from typing import AsyncIterator

import httpx
from openai import AsyncOpenAI

from renulus.contracts import ApiError
from .inputs import to_hermes_messages
from .policy import ALLOWED_MODELS, BASE_URLS, INSTRUCTIONS, require_provider


class HermesSubscriptionTransport:
    def __init__(self, source_root: Path, profile: Path, *, http_transport=None):
        self.source = source_root / "upstream" / "hermes"
        self.profile = profile
        self.http_transport = http_transport
        # SDK debug logs can include the request body. This controlled backend
        # deliberately does not emit transport diagnostics containing payloads.
        for name in ("openai", "openai._base_client", "httpx", "httpcore"):
            logging.getLogger(name).disabled = True
        if not (self.source / "agent" / "transports" / "codex.py").is_file():
            raise ApiError("hermes_not_packaged", "The attributed Hermes runtime is missing.", 503)
        # The backend owns this pinned package, never another app's installed Hermes.
        existing = sys.modules.get("hermes_constants")
        if existing and not Path(existing.__file__).resolve().is_relative_to(self.source.resolve()):
            raise ApiError("hermes_source_conflict", "A different Hermes source is loaded in this process.", 503)
        if str(self.source) not in sys.path:
            sys.path.insert(0, str(self.source))

    @contextmanager
    def controlled(self):
        import hermes_constants
        import providers
        from hermes_cli import mem_trim
        home_token = hermes_constants.set_hermes_home_override(self.profile / "state" / "hermes")
        guard_token = providers.set_provider_discovery_disabled()
        trim_token = mem_trim.set_memory_trim_disabled()
        try:
            yield
        finally:
            mem_trim.reset_memory_trim_disabled(trim_token)
            providers.reset_provider_discovery_disabled(guard_token)
            hermes_constants.reset_hermes_home_override(home_token)

    def build_request(self, provider: str, model: str, messages: list[dict]) -> dict:
        require_provider(provider)
        if model not in ALLOWED_MODELS[provider]:
            raise ApiError("model_not_allowed", "The transport refused an unapproved model.")
        messages = to_hermes_messages(messages)
        with self.controlled():
            if provider == "codex":
                from agent.transports.codex import ResponsesApiTransport
                instructions = INSTRUCTIONS + "\n\n" + "\n\n".join(
                    message["content"] if isinstance(message["content"], str) else
                    "\n".join(part["text"] for part in message["content"])
                    for message in messages if message["role"] == "system")
                payload = [message for message in messages if message["role"] != "system"]
                kwargs = ResponsesApiTransport().build_kwargs(
                    model, payload, tools=None, provider="codex",
                    base_url=BASE_URLS[provider], instructions=instructions,
                    replay_encrypted_reasoning=False,
                )
                # No cross-run cache identities or native background compaction.
                for name in ("prompt_cache_key", "prompt_cache_retention", "include",
                             "context_management", "extra_headers"):
                    kwargs.pop(name, None)
                kwargs["store"] = False
            else:
                from agent.transports.chat_completions import ChatCompletionsTransport
                kwargs = ChatCompletionsTransport().build_kwargs(
                    model, [{"role": "system", "content": INSTRUCTIONS}, *messages],
                    tools=None, base_url=BASE_URLS[provider], provider="opencode-go",
                )
            if kwargs.get("model") != model:
                raise ApiError("route_policy_violation", "The runtime refused a changed model identity.", 503)
            kwargs.pop("tools", None)
            kwargs.pop("tool_choice", None)
            kwargs["stream"] = True
            return kwargs

    async def stream(self, provider: str, model: str, access_token: str,
                     messages: list[dict]) -> AsyncIterator[dict]:
        request = self.build_request(provider, model, messages)
        # An explicitly supplied key and endpoint only; no environment credentials,
        # SDK retries, alternate subscription, proxy credentials or debug dumps.
        http = httpx.AsyncClient(transport=self.http_transport, trust_env=False,
                                 timeout=httpx.Timeout(90, connect=15))
        async with AsyncOpenAI(api_key=access_token, base_url=BASE_URLS[provider],
                               max_retries=0, http_client=http) as client:
            if provider == "codex":
                stream = await client.responses.create(**request)
                async with stream:
                    async for event in stream:
                        kind = event.type
                        if kind == "response.output_text.delta":
                            yield {"type": "delta", "text": event.delta}
                        elif kind == "response.completed":
                            yield {"type": "completed"}
                            return
                        elif kind in ("error", "response.failed", "response.incomplete"):
                            raise ApiError("provider_stream_failed", "The selected subscription did not finish the response.", 503, True)
                        elif kind == "response.output_item.added" and getattr(event.item, "type", "") not in ("message", "reasoning"):
                            raise ApiError("tools_disabled", "The runtime refused an automation response.", 409)
            else:
                stream = await client.chat.completions.create(**request)
                async with stream:
                    async for chunk in stream:
                        for choice in chunk.choices:
                            if choice.delta.tool_calls or getattr(choice.delta, "function_call", None):
                                raise ApiError("tools_disabled", "The runtime refused an automation response.", 409)
                            if choice.delta.content:
                                yield {"type": "delta", "text": choice.delta.content}
                            if choice.finish_reason:
                                if choice.finish_reason != "stop":
                                    raise ApiError("provider_stream_incomplete", "The response ended before completion. Retry or shorten the input.", 409, True)
                                yield {"type": "completed"}
                                return
        raise ApiError("provider_stream_incomplete", "The subscription stream ended without completion.", 503, True)
