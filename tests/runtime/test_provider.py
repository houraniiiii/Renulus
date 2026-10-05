import asyncio
import json

import httpx
import pytest

# Synthetic wire/lifecycle checks assume future eligibility, not release approval.
pytestmark = pytest.mark.usefixtures("synthetic_go_approval")

from renulus.contracts import ApiError, ContextScope, Scope
from renulus.runtime.hermes import HermesSubscriptionTransport
from renulus.runtime.manager import ProviderManager
from renulus.runtime.policy import ALLOWED_MODELS

SENTINEL = "SYNTHETIC_TEMP_CASE_0f56d658_never_save"
GO_KEY = "synthetic-renulus-go-subscription-key"


def catalog(request):
    return httpx.Response(200, json={"data": [{"id": model} for model in
        [*ALLOWED_MODELS["opencode-go"], "unapproved-extra-model"]]})


def sse_chat(text="Synthetic CKD learning response"):
    def chunk(content, finish):
        return {"id": "synthetic", "object": "chat.completion.chunk", "created": 1,
                "model": "mimo-v2.6-pro", "choices": [{"index": 0,
                "delta": {"content": content}, "finish_reason": finish}]}
    items = [chunk(text, None), chunk(None, "stop")]
    return "".join("data: " + json.dumps(item) + "\n\n" for item in items) + "data: [DONE]\n\n"


@pytest.mark.asyncio
async def test_disconnected_does_not_read_env_or_make_http_calls(app_paths, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-other-app-key-not-authorized")
    monkeypatch.setenv("OPENCODE_GO_API_KEY", "synthetic-other-app-key-not-authorized")
    calls = []
    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(lambda request: calls.append(request)))
    assert {row["status"] for row in manager.connections()["connections"]} == {"disconnected"}
    with pytest.raises(ApiError, match="Select an app-owned"):
        _ = [part async for part in manager.stream([{"role": "user", "content": SENTINEL}],
            scope=ContextScope(kind=Scope.TEMPORARY_CASE), run_id="disconnected")]
    assert not calls
    assert not list(app_paths.state.rglob("*.dpapi"))
    assert not manager.status()["active_runs"]


@pytest.mark.parametrize("provider,model", [(p, m) for p, ids in ALLOWED_MODELS.items() for m in ids])
def test_actual_hermes_transport_preserves_all_five_ids_and_disables_tools(app_paths, provider, model):
    transport = HermesSubscriptionTransport(app_paths.source_root, app_paths.root)
    request = transport.build_request(provider, model, [{"role": "user", "content": "Synthetic transplantation teaching"}])
    assert request["model"] == model
    assert request["stream"] is True
    assert "tools" not in request and "context_management" not in request
    if provider == "codex":
        assert request["store"] is False
        assert "prompt_cache_key" not in request
    import providers
    with transport.controlled():
        assert providers.list_providers() == []
        assert providers.get_provider_profile("codex") is None


def test_transport_itself_rejects_unapproved_outbound_route(app_paths):
    transport = HermesSubscriptionTransport(app_paths.source_root, app_paths.root)
    with pytest.raises(ApiError) as failure:
        transport.build_request("codex", "gpt-5.4", [])
    assert failure.value.code == "model_not_allowed"


@pytest.mark.asyncio
async def test_real_sdk_go_stream_no_temp_payload_on_disk_and_protected_restart(app_paths):
    requests = []
    def serve(request):
        requests.append(request)
        if request.url.path.endswith("/models"):
            return catalog(request)
        assert request.url == "https://opencode.ai/zen/go/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer " + GO_KEY
        body = json.loads(request.content)
        assert body["model"] == "mimo-v2.6-pro" and "tools" not in body
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=sse_chat())
    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(serve))
    await manager.connect_go(GO_KEY, select=True)
    events = [event async for event in manager.events([{"role": "user", "content": SENTINEL}],
        scope=ContextScope(kind=Scope.TEMPORARY_CASE), run_id="no-save")]
    assert [event.type for event in events] == ["started", "delta", "completed"]
    assert [event.sequence for event in events] == [1, 2, 3]
    assert not manager.status()["active_runs"]
    assert len(requests) == 2  # Exactly one catalog and one inference request.
    for path in app_paths.root.rglob("*"):
        if path.is_file():
            assert SENTINEL.encode() not in path.read_bytes()
            assert GO_KEY.encode() not in path.read_bytes()
    restarted = ProviderManager(app_paths)
    assert restarted.connections()["selected_provider"] == "opencode-go"
    assert restarted.connections()["connections"][1]["status"] == "configured"
    assert GO_KEY not in json.dumps(restarted.status())
    assert "unapproved-extra-model" not in json.dumps(manager.connections())


@pytest.mark.asyncio
async def test_scope_and_cross_subscription_model_rejected_before_inference(app_paths):
    calls = []
    def serve(request):
        calls.append(request)
        return catalog(request)
    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(serve))
    await manager.connect_go(GO_KEY, select=True)
    with pytest.raises(ApiError) as failure:
        _ = [part async for part in manager.stream([{"role": "user", "content": SENTINEL}],
            scope=ContextScope(kind=Scope.STUDY), run_id="wrong-route", model="gpt-6.1-sol")]
    assert failure.value.code == "model_not_allowed"
    with pytest.raises(ApiError):
        _ = [part async for part in manager.stream([{"role": "tool", "content": SENTINEL}],
            scope=ContextScope(kind=Scope.TEMPORARY_CASE), run_id="tool")]
    with pytest.raises(ApiError):
        _ = [part async for part in manager.stream([{"role": "user", "content": SENTINEL}],
            scope={}, run_id="no-scope")]
    assert len(calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("status,code", [(401, "authentication_required"), (429, "subscription_limit"), (500, "provider_unavailable")])
async def test_provider_error_is_redacted_and_never_switches_subscription(app_paths, status, code):
    calls = []
    def serve(request):
        calls.append(request)
        if request.url.path.endswith("/models"):
            return catalog(request)
        return httpx.Response(status, json={"error": {"message": SENTINEL + GO_KEY}})
    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(serve))
    await manager.connect_go(GO_KEY, select=True)
    events = [event async for event in manager.events([{"role": "user", "content": SENTINEL}],
        scope=ContextScope(kind=Scope.TEMPORARY_CASE), run_id="forced-error")]
    assert events[-1].type == "error" and events[-1].payload["code"] == code
    assert SENTINEL not in json.dumps([event.model_dump() for event in events])
    assert len(calls) == 2 and manager.connections()["selected_provider"] == "opencode-go"
    for path in app_paths.root.rglob("*"):
        if path.is_file():
            assert SENTINEL.encode() not in path.read_bytes()


@pytest.mark.asyncio
async def test_cancellation_interrupts_pending_read_closes_transport_and_has_one_terminal(app_paths):
    entered = asyncio.Event()
    closed = asyncio.Event()
    class SlowTransport:
        async def stream(self, provider, model, token, messages):
            try:
                yield {"type": "delta", "text": "Partial educational answer"}
                entered.set()
                await asyncio.Event().wait()
            finally:
                closed.set()
    manager = ProviderManager(app_paths, transport=SlowTransport(), http_transport=httpx.MockTransport(catalog))
    await manager.connect_go(GO_KEY, select=True)
    async def consume():
        return [event async for event in manager.events([{"role": "user", "content": SENTINEL}],
            scope=ContextScope(kind=Scope.TEMPORARY_CASE), run_id="cancel-me")]
    task = asyncio.create_task(consume())
    await asyncio.wait_for(entered.wait(), 2)
    assert await manager.cancel("cancel-me") is True
    events = await asyncio.wait_for(task, 2)
    assert [event.type for event in events] == ["started", "delta", "cancelled"]
    assert closed.is_set() and await manager.cancel("cancel-me") is False
    assert not manager.status()["active_runs"]
