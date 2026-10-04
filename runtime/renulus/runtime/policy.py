"""One exact route policy for interactive and background generation."""
from __future__ import annotations

import re
from typing import Any

from renulus.contracts import ApiError

ALLOWED_MODELS = {
    "codex": ("gpt-6.1-sol", "gpt-6-astra", "gpt-6-luna"),
    "opencode-go": ("mimo-v2.6-pro", "deepseek-v4.1-flash"),
}
BASE_URLS = {
    "codex": "https://api.openai.com/v1",
    "opencode-go": "https://opencode.ai/zen/go/v1",
}
INSTRUCTIONS = (
    "You are Renulus, an English-language nephrology learning assistant. "
    "Explain educational reasoning clearly. Distinguish retrieved evidence from "
    "unverified statements. You have no automation tools. Do not claim to save "
    "cases, modify records, or perform actions outside this conversation."
)


def require_provider(provider: str) -> str:
    if provider not in ALLOWED_MODELS:
        raise ApiError("provider_not_allowed", "Choose Codex or OpenCode Go.")
    return provider


def require_run_id(run_id: str) -> str:
    if not isinstance(run_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", run_id):
        raise ApiError("invalid_run_id", "Supply an opaque run identifier.")
    return run_id


def validate_messages(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
    # Exclude tools, model-generated instructions and hidden replay fields.
    if not isinstance(messages, list) or not 1 <= len(messages) <= 200:
        raise ApiError("invalid_messages", "Supply between 1 and 200 text messages.")
    result = []
    size = 0
    for message in messages:
        if not isinstance(message, dict) or set(message) != {"role", "content"}:
            raise ApiError("invalid_messages", "Messages contain only role and text content.")
        if message["role"] not in ("system", "user", "assistant"):
            raise ApiError("tools_disabled", "Automation and tool messages are disabled.")
        if not isinstance(message["content"], str):
            raise ApiError("input_capability_unverified", "This connection currently accepts text only.")
        size += len(message["content"])
        result.append(dict(message))
    if size > 1_000_000:
        raise ApiError("context_limit", "Shorten the conversation before trying again.")
    return result


def safe_error(error: Exception) -> ApiError:
    """Never forward SDK request/response bodies, tokens or case text."""
    if isinstance(error, ApiError):
        return error
    status = getattr(error, "status_code", None)
    if status is None:
        status = getattr(getattr(error, "response", None), "status_code", None)
    if status in (401, 403):
        return ApiError("authentication_required", "Reconnect the selected subscription.", 401, True)
    if status == 429:
        return ApiError("subscription_limit", "The selected subscription reached a usage limit.", 429, True)
    if status in (400, 404, 422):
        return ApiError("model_unavailable", "The selected model or input is unavailable. Refresh its capabilities.", 409, True)
    return ApiError("provider_unavailable", "The selected subscription could not complete the request. Retry when connected.", 503, True)
