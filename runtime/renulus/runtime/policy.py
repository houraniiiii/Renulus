"""One exact route policy for interactive and background generation."""
from __future__ import annotations

import re
from typing import Any

from renulus.contracts import ApiError
from .inputs import validate_inputs

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


def validate_messages(messages: list[dict[str, Any]]) -> list[dict]:
    return validate_inputs(messages)


def rejection_kind(error: Exception, *, images: bool) -> str | None:
    """Read only explicit machine codes, never provider body text."""
    code = getattr(error, "code", None)
    body = getattr(error, "body", None)
    if isinstance(body, dict):
        structured = body.get("error", body)
        if isinstance(structured, dict):
            code = structured.get("code", code)
    if not isinstance(code, str):
        return None
    if images and code in {"unsupported_image_input", "image_input_not_supported",
                          "unsupported_input_modality", "unsupported_modality"}:
        return "image"
    if code in {"model_not_found", "model_access_denied", "account_model_unsupported"}:
        return "model"
    return None


def coded_failure(code: str | None) -> ApiError | None:
    """Map explicit machine codes without trusting provider prose or payloads."""
    if not isinstance(code, str):
        return None
    if code in {"subscription_sharing_usage_limit_exceeded", "rate_limit_exceeded", "insufficient_quota"}:
        return ApiError("subscription_limit", "The selected subscription reached a usage limit.", 429, True)
    if code in {"invalid_api_key", "invalid_access_token", "token_expired", "invalid_token",
                "invalid_grant", "authentication_required", "access_denied", "permission_denied"}:
        return ApiError("authentication_required", "Reconnect the selected subscription.", 401, True)
    return None


def stream_failure(code: str | None) -> ApiError:
    public = coded_failure(code)
    if public:
        return public
    if isinstance(code, str) and code in {"model_not_found", "model_access_denied", "account_model_unsupported",
                "unsupported_image_input", "image_input_not_supported",
                "unsupported_input_modality", "unsupported_modality"}:
        # Retain only known machine codes for the manager capability transition.
        return ApiError(code, "The selected account rejected this model or input.", 409, True)
    return ApiError("provider_stream_failed", "The selected subscription did not finish the response.", 503, True)


def safe_error(error: Exception) -> ApiError:
    """Never forward SDK request/response bodies, tokens or case text."""
    if isinstance(error, ApiError):
        return error
    body = getattr(error, "body", None)
    structured = body.get("error", body) if isinstance(body, dict) else {}
    code = structured.get("code", getattr(error, "code", None)) if isinstance(structured, dict) else None
    public = coded_failure(code)
    if public:
        return public
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
