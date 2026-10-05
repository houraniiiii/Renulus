"""Public practice failures via real Hermes/SDK and synthetic subscription I/O."""
import ipaddress
import json
from pathlib import Path
import socket
import sqlite3
import time

import httpx
import pytest

from renulus.assessment.generated_streaming import safe_error
from renulus.contracts import ApiError
from renulus.runtime.manager import ProviderManager
from renulus.server import create_app

MODEL = "gpt-6-astra"
PRIVATE = "SYNTHETIC_PRIVATE_PROVIDER_BODY_TOKEN_CASE_937"


@pytest.fixture(autouse=True)
def no_external_sockets(monkeypatch):
    for name in ("connect", "connect_ex"):
        original = getattr(socket.socket, name)

        def local_only(sock, address, _original=original):
            assert isinstance(address, tuple) and ipaddress.ip_address(address[0]).is_loopback
            return _original(sock, address)

        monkeypatch.setattr(socket.socket, name, local_only)


@pytest.mark.parametrize("retryable", [True, False])
@pytest.mark.parametrize("code", [
    "subscription_limit", "capabilities_unverified", "account_model_unsupported",
    "connection_changed", "provider_stream_incomplete", "provider_stream_failed",
    "provider_protocol_error", "model_not_allowed", "context_limit",
    "compaction_failed", "compaction_not_effective", "image_input_unsupported",
    "image_capabilities_unverified", "tools_disabled",
])
def test_public_provider_code_and_retryability_survive_without_provider_prose(code, retryable):
    error = safe_error(ApiError(code, PRIVATE, 409, retryable))
    assert error["code"] == code and error["retryable"] is retryable
    assert error["message"] and PRIVATE not in json.dumps(error)
    assert set(error) == {"code", "message", "retryable"}


@pytest.mark.parametrize("error", [
    RuntimeError(PRIVATE), ApiError(PRIVATE, PRIVATE, 409, False), sqlite3.Error(PRIVATE),
])
def test_unknown_provider_and_storage_errors_are_redacted(error):
    result = safe_error(error)
    assert result["code"] == ("assessment_storage_failed" if isinstance(error, sqlite3.Error)
                              else "practice_generation_failed")
    assert result["retryable"] is True and PRIVATE not in json.dumps(result)


def sse(events):
    return httpx.Response(200, headers={"content-type": "text/event-stream"},
        content="".join("data: " + json.dumps(event) + "\n\n" for event in events))


def delta(text):
    return {"type": "response.output_text.delta", "delta": text, "item_id": "synthetic",
            "output_index": 0, "content_index": 0, "sequence_number": 1}


def batch():
    return {"items": [{"stem": "Original synthetic transplantation token exercise",
        "options": [{"id": "a", "text": "Marked token", "rationale": "Marked original token"},
                    {"id": "b", "text": "Other token", "rationale": "Original distractor"}],
        "correct_option_id": "a", "explanation": "SYNTHETIC_UNREVIEWED_TOKEN_KEY",
        "hint": None, "source_indices": []}]}


def decoded(response):
    assert response.status_code == 200
    events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
    assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
    assert sum(event["type"] in {"completed", "error", "cancelled"} for event in events) == 1
    return events


@pytest.mark.asyncio
@pytest.mark.parametrize("failure,expected", [
    ("quota-http", "subscription_limit"), ("quota-sse", "subscription_limit"),
    ("auth-http", "authentication_required"), ("model-sse", "account_model_unsupported"),
    ("eof", "provider_stream_incomplete"), ("unknown-sse", "provider_stream_failed"),
])
async def test_sdk_practice_failure_is_actionable_redacted_and_needs_explicit_retry(tmp_path, failure, expected):
    requests = []
    phase = {"failed": True}

    def serve(request):
        assert request.url.host == "api.openai.com"
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"models": [{"slug": MODEL, "visibility": "list"}]})
        assert request.url.path == "/v1/responses"
        assert json.loads(request.content)["model"] == MODEL
        requests.append(request)
        if not phase["failed"]:
            return sse([delta(json.dumps(batch())), {"type": "response.completed", "sequence_number": 2,
                "response": {"id": "synthetic", "object": "response", "created_at": 1,
                             "status": "completed", "model": MODEL, "output": []}}])
        if failure in {"auth-http", "quota-http"}:
            return httpx.Response(401 if failure == "auth-http" else 429,
                json={"error": {"message": PRIVATE}})
        if failure == "eof":
            return sse([delta("SYNTHETIC_PARTIAL_PRACTICE_NOT_PUBLISHED")])
        if failure == "model-sse":
            return sse([{"type": "response.failed", "sequence_number": 1,
                "response": {"id": "synthetic", "object": "response", "created_at": 1,
                    "status": "failed", "model": MODEL, "output": [],
                    "error": {"code": "model_not_found", "message": PRIVATE}}}])
        code = "subscription_sharing_usage_limit_exceeded" if failure == "quota-sse" else PRIVATE
        return sse([{"type": "error", "sequence_number": 1, "code": code,
                     "message": PRIVATE, "param": None}])

    app = create_app(tmp_path, token="synthetic-local-token",
        source_root=Path(__file__).resolve().parents[2])
    services = app.state.services
    provider = ProviderManager(services.paths, http_transport=httpx.MockTransport(serve))
    provider._settings["connections"]["codex"] = {"client_id": "synthetic-client",
        "access_token": "synthetic-plan-token", "expires_at": time.time() + 600}
    provider._settings["selected_provider"] = "codex"
    provider._catalogs["codex"] = {MODEL}
    provider._save()
    services.registry["provider"] = provider
    request = {"prompt": "Original synthetic transplantation token exercise", "count": 1,
               "context": "study", "idempotency_key": "failed-practice"}
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                base_url="http://127.0.0.1", headers={"x-renulus-token": "synthetic-local-token"}) as local:
            failure_flow = decoded(await local.post("/api/v1/assessment/practice/generate", json=request))
            assert failure_flow[-1]["type"] == "error"
            assert failure_flow[-1]["payload"]["code"] == expected
            assert failure_flow[-1]["payload"]["retryable"] is True
            assert PRIVATE not in json.dumps(failure_flow)
            assert len(requests) == 1 and provider.status()["active_runs"] == []
            assert services.db.fetch_all("SELECT * FROM assessment_generated_sessions") == []
            assert services.db.fetch_all("SELECT * FROM learning_evidence") == []
            replay = decoded(await local.post("/api/v1/assessment/practice/generate", json=request))
            assert replay == failure_flow and len(requests) == 1
            phase["failed"] = False
            await provider.refresh("codex")
            retry = decoded(await local.post("/api/v1/assessment/practice/generate",
                json={**request, "idempotency_key": "explicit-retry"}))
            assert retry[-1]["type"] == "completed" and len(requests) == 2
            assert len(services.db.fetch_all("SELECT * FROM assessment_generated_sessions")) == 1
            assert services.db.fetch_all("SELECT * FROM assessment_attempts") == []
            assert services.db.fetch_all("SELECT * FROM learning_evidence") == []
            assert "SYNTHETIC_UNREVIEWED_TOKEN_KEY" not in json.dumps(retry)
        assert provider.status()["active_runs"] == [] and not provider.status()["live_provider_verified"]
        assert provider.connections()["selected_provider"] == "codex"
    finally:
        await provider.close()
