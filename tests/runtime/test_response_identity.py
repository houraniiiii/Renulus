"""Bounded route observations from real SDK envelopes and synthetic transports."""
import ipaddress
import json
import socket
import time
from types import SimpleNamespace

import httpx
import pytest

from renulus.contracts import ApiError, ContextScope, Scope
from renulus.runtime.manager import ProviderManager
from renulus.runtime.policy import ALLOWED_MODELS

SCOPE = ContextScope(kind=Scope.TEMPORARY_CASE)
SECRET = "SYNTHETIC_PRIVATE_PROMPT credential with spaces"


@pytest.fixture(autouse=True)
def no_external_sockets(monkeypatch):
    for name in ("connect", "connect_ex"):
        original = getattr(socket.socket, name)

        def local_only(sock, address, _original=original):
            assert isinstance(address, tuple) and ipaddress.ip_address(address[0]).is_loopback
            return _original(sock, address)

        monkeypatch.setattr(socket.socket, name, local_only)


def envelope(provider, identities):
    if provider == "codex":
        events = [{"type": "response.completed", "sequence_number": 1,
            "response": {"id": "synthetic", "object": "response", "created_at": 1,
                "status": "completed", "model": identities[0], "output": [],
                "metadata": {"private": SECRET}}}]
    else:
        events = [{"id": "synthetic", "object": "chat.completion.chunk", "created": 1,
            "model": identity, "choices": [{"index": 0, "delta": {},
                "finish_reason": "stop" if index == len(identities) - 1 else None}],
            "private": SECRET} for index, identity in enumerate(identities)]
    return httpx.Response(200, headers={"content-type": "text/event-stream"},
        content="".join("data: " + json.dumps(event) + "\n\n" for event in events))


def seed(manager, provider, model):
    manager._settings["connections"][provider] = {"access_token": "synthetic-key", "expires_at": time.time() + 600}
    manager._settings["selected_provider"] = provider
    manager._settings["selected_models"] = {provider: model}


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,model", [(p, m) for p, models in ALLOWED_MODELS.items() for m in models])
async def test_sdk_completion_preserves_reported_model_in_event_and_status(app_paths, provider, model):
    requests = []

    def serve(request):
        requests.append(request)
        assert json.loads(request.content)["model"] == model
        return envelope(provider, [model])

    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(serve))
    seed(manager, provider, model)
    events = [event async for event in manager.events([{"role": "user", "content": SECRET}],
        scope=SCOPE, run_id="identity", purpose="memory-extraction")]
    assert events[-1].type == "completed"
    assert events[-1].payload == {"provider": provider, "model": model, "response_model": model}
    history = manager.status()["completed_requests"]
    assert history == [{"run_id": "identity", "purpose": "memory-extraction", "provider": provider,
                        "model": model, "response_model": model}]
    assert len(requests) == 1 and SECRET not in json.dumps(history)
    assert manager.status()["live_provider_verified"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ALLOWED_MODELS)
async def test_reported_identity_is_observed_not_replaced_by_requested_identity(app_paths, provider):
    model = ALLOWED_MODELS[provider][0]
    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(
        lambda request: envelope(provider, ["different-model"])))
    seed(manager, provider, model)
    events = [event async for event in manager.events([{"role": "user", "content": SECRET}],
        scope=SCOPE, run_id="different")]
    assert events[-1].payload == {"provider": provider, "model": model, "response_model": "different-model"}
    assert manager.status()["completed_requests"][0]["response_model"] == "different-model"
    assert manager._completed_requests == 0 and manager._capabilities == {}
    assert manager.connections()["selected_models"][provider] == model


@pytest.mark.asyncio
async def test_go_chunk_identity_changes_fail_without_completion_history(app_paths):
    model = ALLOWED_MODELS["opencode-go"][0]
    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(
        lambda request: envelope("opencode-go", [model, "different-model"])))
    seed(manager, "opencode-go", model)
    events = [event async for event in manager.events([{"role": "user", "content": SECRET}],
        scope=SCOPE, run_id="changed")]
    assert events[-1].type == "error" and events[-1].payload["code"] == "provider_protocol_error"
    assert manager.status()["completed_requests"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ALLOWED_MODELS)
@pytest.mark.parametrize("reported", [None, SECRET, "x" * 129])
async def test_absent_or_unsafe_response_model_is_not_inferred_or_exposed(app_paths, provider, reported):
    model = ALLOWED_MODELS[provider][0]
    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(
        lambda request: envelope(provider, [reported])))
    seed(manager, provider, model)
    events = [event async for event in manager.events([{"role": "user", "content": SECRET}],
        scope=SCOPE, run_id="absent")]
    assert events[-1].type == "completed" and "response_model" not in events[-1].payload
    assert manager.status()["completed_requests"][0]["response_model"] is None
    assert SECRET not in json.dumps(manager.status())


@pytest.mark.asyncio
async def test_completion_history_is_bounded_transient_and_contains_only_safe_route_fields(app_paths):
    class SyntheticTransport:
        fail = False

        async def stream(self, provider, model, token, messages):
            if self.fail:
                raise ApiError("subscription_limit", "Synthetic limit", 429, True)
            yield {"type": "completed", "private": SECRET}

    transport = SyntheticTransport()
    manager = ProviderManager(app_paths, transport=transport)
    manager._context = SimpleNamespace(plan=lambda *args, **kwargs: SimpleNamespace(turns=None))
    seed(manager, "opencode-go", "deepseek-v4.1-flash")
    manager._save()
    before = {path: path.read_bytes() for path in app_paths.root.rglob("*") if path.is_file()}
    for index in range(35):
        result = [part async for part in manager.stream([{"role": "user", "content": SECRET}],
            scope=SCOPE, run_id=f"metadata-{index}", purpose=SECRET)]
        assert result == []
    history = manager.status()["completed_requests"]
    assert len(history) == 32 and [item["run_id"] for item in history] == [f"metadata-{i}" for i in range(3, 35)]
    assert all(item == {"run_id": f"metadata-{i}", "purpose": "other", "provider": "opencode-go",
                       "model": "deepseek-v4.1-flash", "response_model": None} for i, item in zip(range(3, 35), history))
    history[0]["purpose"] = SECRET
    history.clear()
    assert len(manager.status()["completed_requests"]) == 32
    assert SECRET not in json.dumps(manager.status())
    transport.fail = True
    with pytest.raises(ApiError):
        _ = [part async for part in manager.stream([{"role": "user", "content": SECRET}],
            scope=SCOPE, run_id="failed")]
    assert manager.status()["completed_requests"][-1]["run_id"] == "metadata-34"
    assert ProviderManager(app_paths).status()["completed_requests"] == []
    assert before == {path: path.read_bytes() for path in app_paths.root.rglob("*") if path.is_file()}
