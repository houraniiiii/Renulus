"""Approved Go routing with synthetic SDK traffic; no live model access proof."""
import ipaddress
import json
import socket
from uuid import UUID

import httpx
import pytest

from renulus.contracts import ApiError, ContextScope, Scope
from renulus.runtime.hermes import HermesSubscriptionTransport
from renulus.runtime.manager import ProviderManager
from renulus.runtime.policy import ALLOWED_MODELS
from renulus.server import create_app

SENTINEL = "SYNTHETIC_EDUCATIONAL_CASE_NEVER_SAVE_152"
GO = "opencode-go"


@pytest.fixture(autouse=True)
def no_external_sockets(monkeypatch):
    for name in ("connect", "connect_ex"):
        original = getattr(socket.socket, name)

        def local_only(sock, address, _original=original):
            assert isinstance(address, tuple) and ipaddress.ip_address(address[0]).is_loopback
            return _original(sock, address)

        monkeypatch.setattr(socket.socket, name, local_only)


def catalog(request):
    assert request.url == "https://opencode.ai/zen/go/v1/models"
    assert request.headers["user-agent"] == "Renulus/0.1.0"
    assert UUID(request.headers["x-opencode-session"])
    return httpx.Response(200, json={"data": [{"id": model} for model in ALLOWED_MODELS[GO]]})


def completion(request):
    assert request.url == "https://opencode.ai/zen/go/v1/chat/completions"
    assert request.headers["user-agent"] == "Renulus/0.1.0"
    assert "opencode-version" not in request.headers
    assert UUID(request.headers["x-opencode-session"])
    body = json.loads(request.content)
    assert body["model"] in ALLOWED_MODELS[GO] and "tools" not in body
    events = [{"id": "synthetic", "object": "chat.completion.chunk", "created": 1,
        "model": body["model"], "choices": [{"index": 0, "delta": {"content": text},
        "finish_reason": reason}]} for text, reason in [("Synthetic result", None), (None, "stop")]]
    return httpx.Response(200, headers={"content-type": "text/event-stream"},
        content="".join("data: " + json.dumps(event) + "\n\n" for event in events) + "data: [DONE]\n\n")


@pytest.mark.asyncio
async def test_app_approval_does_not_claim_account_access_or_select_implicitly(app_paths):
    requests = []

    def serve(request):
        requests.append(request)
        return catalog(request)

    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(serve))
    initial = manager.connections()["connections"][1]
    assert initial["status"] == "disconnected"
    assert initial["learning_use"]["status"] == "app_approved"
    assert initial["learning_use"]["generation_allowed"] is True
    with pytest.raises(ApiError) as error:
        manager.select(GO)
    assert error.value.code == "connection_required"
    await manager.connect_go("synthetic-go-key")
    await manager.refresh(GO)
    assert manager.connections()["selected_provider"] is None
    assert len(requests) == 2 and not manager.status()["live_provider_verified"]
    assert ALLOWED_MODELS[GO] == ("mimo-v2.6-pro", "deepseek-v4.1-flash")


@pytest.mark.asyncio
async def test_failed_connect_preserves_current_selection_and_saved_credentials(app_paths):
    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(
        lambda request: httpx.Response(401, json={"error": {"code": "invalid_api_key"}})))
    manager._settings["selected_provider"] = "codex"
    manager._settings["connections"][GO] = {"access_token": "synthetic-old-go-key"}
    with pytest.raises(ApiError) as error:
        await manager.connect_go("synthetic-rejected-key", select=True)
    assert error.value.code == "authentication_required"
    assert manager.connections()["selected_provider"] == "codex"
    assert manager._settings["connections"][GO]["access_token"] == "synthetic-old-go-key"


@pytest.mark.asyncio
@pytest.mark.parametrize("model", ALLOWED_MODELS[GO])
async def test_exact_go_selection_persists_and_routes_without_catalogue_after_restart(app_paths, model):
    requests = []

    def serve(request):
        requests.append(request)
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": []})
        assert json.loads(request.content)["model"] == model
        return completion(request)

    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(serve))
    await manager.connect_go("synthetic-go-key", select=True)
    manager.select(GO, model)
    rows = manager.connections()["connections"][1]
    assert rows["status"] == "connected"
    assert all(row["availability"] == "available" and not row["catalogue_listed"] for row in rows["models"])
    restarted = ProviderManager(app_paths, http_transport=httpx.MockTransport(serve))
    assert restarted.connections()["selected_models"][GO] == model
    assert restarted.connections()["selected_provider"] == GO
    assert restarted._route(None) == (GO, model)
    events = [event async for event in restarted.events([{"role": "user", "content": SENTINEL}],
        scope=ContextScope(kind=Scope.TEMPORARY_CASE), run_id="go-restart")]
    assert [event.type for event in events] == ["started", "delta", "completed"]
    assert len(requests) == 2 and not restarted.status()["live_provider_verified"]
    other = next(item for item in ALLOWED_MODELS[GO] if item != model)
    assert restarted._route(other) == (GO, other)
    assert restarted.connections()["selected_models"][GO] == model
    restarted._settings["connections"]["codex"] = {"access_token": "synthetic-other-key"}
    restarted.select("codex", "gpt-6-astra")
    restarted.select(GO)
    assert restarted.connections()["selected_models"] == {GO: model, "codex": "gpt-6-astra"}
    restarted.select(GO, None)
    assert ProviderManager(app_paths).connections()["selected_models"][GO] is None
    for path in app_paths.root.rglob("*"):
        if path.is_file():
            assert SENTINEL.encode() not in path.read_bytes()
            assert b"synthetic-go-key" not in path.read_bytes()


@pytest.mark.asyncio
@pytest.mark.parametrize("model", ALLOWED_MODELS[GO])
@pytest.mark.parametrize("kind", list(Scope))
async def test_go_generation_preserves_every_scope_without_writing_request_data(app_paths, model, kind):
    requests = []

    def serve(request):
        requests.append(request)
        assert json.loads(request.content)["model"] == model
        return completion(request)

    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(serve))
    manager._settings["connections"][GO] = {"access_token": "synthetic-key"}
    manager.select(GO, model)
    before = {path: path.read_bytes() for path in app_paths.root.rglob("*") if path.is_file()}
    events = [event async for event in manager.events([{"role": "user", "content": SENTINEL}],
        scope=ContextScope(kind=kind), run_id="go-scope", purpose="memory")]
    assert [event.type for event in events] == ["started", "delta", "completed"]
    assert len(requests) == 1 and not manager.status()["active_runs"]
    assert before == {path: path.read_bytes() for path in app_paths.root.rglob("*") if path.is_file()}


@pytest.mark.asyncio
@pytest.mark.parametrize("model", ALLOWED_MODELS[GO])
async def test_model_rejection_has_no_retry_fallback_or_changed_preference(app_paths, model):
    requests = []

    def serve(request):
        requests.append(request)
        assert json.loads(request.content)["model"] == model
        return httpx.Response(404, json={"error": {"code": "model_not_found", "message": SENTINEL}})

    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(serve))
    manager._settings["connections"][GO] = {"access_token": "synthetic-key"}
    manager._settings["connections"]["codex"] = {"access_token": "synthetic-other-subscription"}
    manager.select(GO, model)
    for run in ("go-reject", "go-no-retry"):
        events = [event async for event in manager.events([{"role": "user", "content": SENTINEL}],
            scope=ContextScope(kind=Scope.TEMPORARY_CASE), run_id=run)]
        assert events[-1].type == "error" and events[-1].payload["code"] == "account_model_unsupported"
        assert SENTINEL not in json.dumps([event.model_dump() for event in events])
    assert len(requests) == 1
    assert manager.connections()["selected_provider"] == GO
    assert manager.connections()["selected_models"][GO] == model
    assert manager._route(next(item for item in ALLOWED_MODELS[GO] if item != model))[0] == GO
    with pytest.raises(ApiError) as error:
        manager.select(GO, "gpt-6.1-sol")
    assert error.value.code == "model_not_allowed"


@pytest.mark.asyncio
@pytest.mark.parametrize("model", ALLOWED_MODELS[GO])
async def test_api_selects_exact_go_model_and_retains_failed_study_on_provider_limit(app_paths, model):
    app = create_app(app_paths.root, token="synthetic-token", source_root=app_paths.source_root)
    provider = app.state.services.registry["provider"]
    requests = []

    def serve(request):
        requests.append(request)
        assert json.loads(request.content)["model"] == model
        return httpx.Response(429, json={"error": {"code": "rate_limit_exceeded"}})

    provider._http_transport = httpx.MockTransport(serve)
    provider._settings["connections"][GO] = {"access_token": "synthetic-key"}
    app.state.services.registry["knowledge"] = app.state.services.registry["memory"] = None
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1",
        headers={"x-renulus-token": "synthetic-token"}) as client:
        selected = await client.post("/api/v1/connections/select", json={"provider": GO, "model": model})
        assert selected.status_code == 200 and selected.json()["selected_models"][GO] == model
        reselected = await client.post("/api/v1/connections/select", json={"provider": GO})
        assert reselected.json()["selected_models"][GO] == model
        assert not requests
        answer = await client.post("/api/v1/learn/ask", json={"question": "Explain synthetic CKD study",
            "scope": {"kind": "study"}})
        events = [json.loads(line[6:]) for line in answer.text.splitlines() if line.startswith("data: ")]
        assert events[-1]["type"] == "error" and events[-1]["payload"]["code"] == "subscription_limit"
        thread_id = events[0]["payload"]["thread_id"]
        thread = (await client.get("/api/v1/learn/threads/" + thread_id)).json()
        assert [message["role"] for message in thread["messages"]] == ["user"]
        assert thread["runs"][0]["state"] == "failed"
    assert len(requests) == 1 and provider.connections()["selected_provider"] == GO
    assert not provider.status()["live_provider_verified"]


def test_upstream_ambient_identity_cannot_replace_app_owned_header(app_paths, monkeypatch):
    transport = HermesSubscriptionTransport(app_paths.source_root, app_paths.root)
    with transport.controlled():
        from agent import opencode_affinity
    monkeypatch.setattr(opencode_affinity, "resolve_affinity_key", lambda session_id: "synthetic-other-conversation")
    with pytest.raises(ApiError) as error:
        transport.request_headers("opencode-go", "synthetic-app-conversation")
    assert error.value.code == "session_identity_changed"


@pytest.mark.asyncio
async def test_approved_headers_are_truthful_stable_scoped_and_private(app_paths):
    requests = []

    def serve(request):
        requests.append(request)
        if request.url.path.endswith("/models"):
            return catalog(request)
        assert request.url == "https://opencode.ai/zen/go/v1/chat/completions"
        assert request.headers["user-agent"] == "Renulus/0.1.0"
        assert "opencode-version" not in request.headers
        data = [{"id": "synthetic", "object": "chat.completion.chunk", "created": 1, "model": "mimo-v2.6-pro",
            "choices": [{"index": 0, "delta": {"content": text}, "finish_reason": reason}]} for text, reason in [("Synthetic result", None), (None, "stop")]]
        return httpx.Response(200, headers={"content-type": "text/event-stream"},
            content="".join("data: " + json.dumps(item) + "\n\n" for item in data) + "data: [DONE]\n\n")

    async def send(manager, kind, entity_id, run_id):
        return [part async for part in manager.stream([{"role": "user", "content": SENTINEL}],
            scope=ContextScope(kind=kind, entity_id=entity_id), run_id=run_id)]

    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(serve))
    await manager.connect_go("synthetic-key", select=True)
    before = {path: path.read_bytes() for path in app_paths.root.rglob("*") if path.is_file()}
    await send(manager, Scope.STUDY, "synthetic-thread-one", "turn1")
    await send(manager, Scope.STUDY, "synthetic-thread-one", "turn2")
    await send(manager, Scope.STUDY, "synthetic-thread-two", "turn3")
    restarted = ProviderManager(app_paths, http_transport=httpx.MockTransport(serve))
    await restarted.refresh("opencode-go")
    await send(restarted, Scope.STUDY, "synthetic-thread-one", "turn4")
    await send(manager, Scope.TEMPORARY_CASE, "synthetic-thread-one", "temporary1")
    await send(manager, Scope.TEMPORARY_CASE, "synthetic-thread-one", "temporary2")
    inference = [request for request in requests if request.url.path.endswith("/chat/completions")]
    ids = [request.headers["x-opencode-session"] for request in inference]
    assert ids[0] == ids[1] == ids[3] and ids[2] != ids[0] and ids[4] != ids[5]
    assert all(UUID(value) for value in ids)
    assert all(SENTINEL not in json.dumps(dict(request.headers)) and "synthetic-thread" not in json.dumps(dict(request.headers)) for request in requests)
    assert before == {path: path.read_bytes() for path in app_paths.root.rglob("*") if path.is_file()}
    assert not manager.status()["live_provider_verified"]
