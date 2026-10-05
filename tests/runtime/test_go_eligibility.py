"""Default release gate and hypothetical-approved SDK headers, never live calls."""
import asyncio
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

SENTINEL = "SYNTHETIC_EDUCATIONAL_CASE_NEVER_SEND_152"


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
    return httpx.Response(200, json={"data": [{"id": model} for model in ALLOWED_MODELS["opencode-go"]]})


@pytest.mark.asyncio
async def test_default_capability_is_unresolved_and_metadata_cannot_enable_learning(app_paths):
    requests = []

    def serve(request):
        requests.append(request)
        return catalog(request)

    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(serve))
    initial = manager.connections()["connections"][1]
    assert initial["status"] == "disconnected"
    assert initial["learning_use"]["status"] == "unresolved"
    assert initial["learning_use"]["generation_allowed"] is False
    await manager.connect_go("synthetic-go-key")
    await manager.refresh("opencode-go")
    row = manager.connections()["connections"][1]
    assert row["status"] == "connected" and all(model["availability"] == "available" for model in row["models"])
    assert row["learning_use"]["generation_allowed"] is False
    assert manager.connections()["selected_provider"] is None
    with pytest.raises(ApiError) as error:
        manager.select("opencode-go")
    assert error.value.code == "learning_use_unverified" and error.value.status == 403
    assert not error.value.retryable and len(requests) == 2
    assert ALLOWED_MODELS["opencode-go"] == ("mimo-v2.6-pro", "deepseek-v4.1-flash")


@pytest.mark.asyncio
async def test_connect_and_select_cannot_override_policy_or_replace_current_subscription(app_paths):
    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(lambda request: pytest.fail("Unexpected provider request")))
    manager._settings["selected_provider"] = "codex"
    with pytest.raises(ApiError) as error:
        await manager.connect_go("synthetic-go-key", select=True)
    assert error.value.code == "learning_use_unverified"
    assert manager.connections()["selected_provider"] == "codex"
    assert not manager._settings["connections"]


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", list(Scope))
@pytest.mark.parametrize("purpose", ["explain", "memory", "compaction", "coding"])
async def test_legacy_selected_go_blocks_every_scope_and_purpose_before_provider_io(app_paths, kind, purpose):
    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(lambda request: pytest.fail("Learning egress")))
    manager._settings["connections"]["opencode-go"] = {"access_token": "synthetic-legacy-go-key"}
    manager._settings["selected_provider"] = "opencode-go"
    manager._catalogs["opencode-go"] = set(ALLOWED_MODELS["opencode-go"])
    manager._save()
    before = {path: path.read_bytes() for path in app_paths.root.rglob("*") if path.is_file()}
    events = [event async for event in manager.events([{"role": "user", "content": SENTINEL}],
        scope=ContextScope(kind=kind), run_id="legacy-go", purpose=purpose)]
    assert [event.type for event in events] == ["error"]
    assert events[0].payload["code"] == "learning_use_unverified"
    assert SENTINEL not in json.dumps([event.model_dump() for event in events])
    assert manager.connections()["selected_provider"] == "opencode-go"
    assert not manager.status()["active_runs"]
    assert before == {path: path.read_bytes() for path in app_paths.root.rglob("*") if path.is_file()}
    with pytest.raises(ApiError) as error:
        await manager.compact([{"role": "user", "content": SENTINEL}],
            scope=ContextScope(kind=kind), run_id="compact-blocked")
    assert error.value.code == "learning_use_unverified"


@pytest.mark.asyncio
async def test_direct_hermes_transport_cannot_bypass_route_gate(app_paths):
    transport = HermesSubscriptionTransport(app_paths.source_root, app_paths.root,
        http_transport=httpx.MockTransport(lambda request: pytest.fail("Direct transport egress")))
    with pytest.raises(ApiError) as error:
        _ = [item async for item in transport.stream("opencode-go", "mimo-v2.6-pro", "synthetic-key",
            [{"role": "user", "content": SENTINEL}], session_id="synthetic-session")]
    assert error.value.code == "learning_use_unverified"


def test_upstream_ambient_identity_cannot_replace_app_owned_header(app_paths, monkeypatch):
    transport = HermesSubscriptionTransport(app_paths.source_root, app_paths.root)
    with transport.controlled():
        from agent import opencode_affinity
    monkeypatch.setattr(opencode_affinity, "resolve_affinity_key", lambda session_id: "synthetic-other-conversation")
    with pytest.raises(ApiError) as error:
        transport.request_headers("opencode-go", "synthetic-app-conversation")
    assert error.value.code == "session_identity_changed"


@pytest.mark.asyncio
async def test_real_api_exposes_gate_and_retains_failed_study_without_egress(app_paths):
    app = create_app(app_paths.root, token="synthetic-token", source_root=app_paths.source_root)
    provider = app.state.services.registry["provider"]
    provider._http_transport = httpx.MockTransport(lambda request: pytest.fail("Unexpected provider traffic"))
    provider._settings["connections"]["opencode-go"] = {"access_token": "synthetic-key"}
    provider._settings["selected_provider"] = "opencode-go"
    app.state.services.registry["knowledge"] = app.state.services.registry["memory"] = None
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1",
        headers={"x-renulus-token": "synthetic-token"}) as client:
        status = (await client.get("/api/v1/connections")).json()
        assert status["connections"][1]["learning_use"]["generation_allowed"] is False
        denied = await client.post("/api/v1/connections/select", json={"provider": "opencode-go"})
        assert denied.status_code == 403 and denied.json()["error"]["code"] == "learning_use_unverified"
        answer = await client.post("/api/v1/learn/ask", json={"question": "Explain synthetic CKD study",
            "scope": {"kind": "study"}})
        events = [json.loads(line[6:]) for line in answer.text.splitlines() if line.startswith("data: ")]
        assert events[-1]["type"] == "error" and events[-1]["payload"]["code"] == "learning_use_unverified"
        thread_id = events[0]["payload"]["thread_id"]
        thread = (await client.get("/api/v1/learn/threads/" + thread_id)).json()
        assert [message["role"] for message in thread["messages"]] == ["user"]
        assert thread["runs"][0]["state"] == "failed"


@pytest.mark.asyncio
async def test_hypothetical_approved_headers_are_truthful_stable_scoped_and_private(app_paths, synthetic_go_approval):
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
