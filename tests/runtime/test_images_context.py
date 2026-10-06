import asyncio
import base64
import builtins
import copy
from io import BytesIO
import json
import os
from pathlib import Path
import socket
import sys
import time

import httpx
from PIL import Image, PngImagePlugin
import pytest

# Actual SDK protocol checks use synthetic HTTP and simulated future eligibility.
pytestmark = pytest.mark.usefixtures("synthetic_go_approval")

from renulus.contracts import ApiError, ContextScope, Scope
from renulus.runtime.context import SUMMARY_INSTRUCTIONS
from renulus.runtime.inputs import validate_inputs
from renulus.runtime.manager import ProviderManager
from renulus.runtime.policy import ALLOWED_MODELS

SENTINEL = "SYNTHETIC_CONTEXT_IMAGE_DO_NOT_SAVE_241721"
SCOPE = ContextScope(kind=Scope.TEMPORARY_CASE)


def image_part():
    image = Image.new("RGB", (12, 8), "white")
    output = BytesIO()
    info = PngImagePlugin.PngInfo()
    info.add_text("Synthetic", SENTINEL)
    image.save(output, format="PNG", pnginfo=info)
    return {"type": "image", "media_type": "image/png",
            "data": base64.b64encode(output.getvalue()).decode(), "detail": "auto"}


def image_messages():
    return [{"role": "user", "content": [{"type": "text", "text": "Describe this synthetic teaching image."}, image_part()]}]


def long_conversation():
    content = ("CKD albuminuria; dialysis potassium; transplant rejection; glomerular haematuria; electrolyte sodium. " * 28)
    return [{"role": "user", "content": "Learn nephrology across domains."}] + [
        {"role": "user" if index % 2 == 0 else "assistant", "content": SENTINEL + str(index) + content}
        for index in range(42)] + [{"role": "user", "content": "What should I review next in transplantation?"}]


def response(provider, text):
    if provider == "codex":
        events = [{"type": "response.output_text.delta", "delta": text, "item_id": "synthetic",
                   "output_index": 0, "content_index": 0, "sequence_number": 1},
                  {"type": "response.completed", "sequence_number": 2,
                   "response": {"id": "synthetic", "object": "response", "created_at": 1,
                                "status": "completed", "model": "gpt-6.1-sol", "output": []}}]
    else:
        events = [{"id": "synthetic", "object": "chat.completion.chunk", "created": 1,
                   "model": "mimo-v2.6-pro", "choices": [{"index": 0, "delta": {"content": delta},
                   "finish_reason": finish}]} for delta, finish in ((text, None), (None, "stop"))]
    data = "".join("data: " + json.dumps(event) + "\n\n" for event in events)
    if provider != "codex":
        data += "data: [DONE]\n\n"
    return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=data)


async def connected(app_paths, provider, model, infer, transport=None):
    requests = []
    def serve(request):
        requests.append(request)
        if request.url.path.endswith("/models"):
            data = ({"models": [{"slug": model, "visibility": "list"},
                                {"slug": "unapproved", "visibility": "list"}]} if provider == "codex" else
                {"data": [{"id": model}]})
            return httpx.Response(200, json=data)
        return infer(request)
    manager = ProviderManager(app_paths, transport=transport, http_transport=httpx.MockTransport(serve))
    if provider == "codex":
        manager._settings["connections"][provider] = {"client_id": "synthetic-client",
            "access_token": "synthetic-plan-token", "expires_at": time.time() + 1200}
        manager._settings["selected_provider"] = provider
        await manager.refresh(provider)
    else:
        await manager.connect_go("synthetic-go-key", select=True)
    return manager, requests


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,model", [(p, m) for p, ids in ALLOWED_MODELS.items() for m in ids])
async def test_actual_hermes_sdk_image_wire_all_five_models_and_honest_capabilities(app_paths, provider, model):
    bodies = []
    def infer(request):
        body = json.loads(request.content)
        bodies.append(body)
        assert body["model"] == model and "tools" not in body
        if provider == "codex":
            assert body["store"] is False
            parts = next(item["content"] for item in body["input"] if item["role"] == "user")
            image = next(part for part in parts if part["type"] == "input_image")
            url = image["image_url"]
        else:
            parts = body["messages"][-1]["content"]
            image = next(part for part in parts if part["type"] == "image_url")
            url = image["image_url"]["url"]
        assert url == "data:image/png;base64," + image_part()["data"]
        return response(provider, "Synthetic image accepted")
    manager, requests = await connected(app_paths, provider, model, infer)
    status = next(row for row in manager.connections()["connections"] if row["provider"] == provider)
    selected = next(row for row in status["models"] if row["id"] == model)
    assert selected["image_input"] == selected["text_input"] == ("supported" if provider == "codex" else "unknown")
    deltas = [item async for item in manager.stream(image_messages(), scope=SCOPE, run_id="image-wire", model=model)]
    assert deltas == ["Synthetic image accepted"] and len(requests) == 2
    status = next(row for row in manager.connections()["connections"] if row["provider"] == provider)
    selected = next(row for row in status["models"] if row["id"] == model)
    assert selected["image_input"] == selected["text_input"] == "supported"
    assert selected["capability_evidence"]["image"] == "completed_request"
    assert selected["image_interpretation_verified"] is False
    assert manager.status()["live_provider_verified"] is False  # actual SDK, synthetic HTTP
    for path in app_paths.root.rglob("*"):
        if path.is_file():
            assert SENTINEL.encode() not in path.read_bytes()
            assert image_part()["data"].encode() not in path.read_bytes()


@pytest.mark.asyncio
async def test_case_image_uses_documented_support_without_probe(app_paths):
    manager, requests = await connected(app_paths, "codex", "gpt-6.1-sol",
        lambda request: response("codex", "Synthetic image discussion"))
    assert manager.connections()["connections"][0]["models"][0]["capability_evidence"]["image"] == "documented_model"
    parts = [part async for part in manager.stream(image_messages(), scope=SCOPE,
        run_id="no-probe-case-image", model="gpt-6.1-sol", purpose="case-image-discuss")]
    assert parts == ["Synthetic image discussion"] and len(requests) == 2
    assert manager.status()["active_runs"] == []
    assert not manager.status()["live_provider_verified"]
    await manager.close()


@pytest.mark.parametrize("change", ["remote-url", "bad-base64", "wrong-mime", "assistant", "unknown-part", "too-many"])
def test_image_validation_rejects_remote_files_corruption_roles_and_oversize_counts(change):
    messages = image_messages()
    part = messages[0]["content"][-1]
    if change == "remote-url":
        part.pop("data")
        part["url"] = "file:///synthetic-only.png"
    elif change == "bad-base64":
        part["data"] = SENTINEL
    elif change == "wrong-mime":
        part["media_type"] = "image/jpeg"
    elif change == "assistant":
        messages[0]["role"] = "assistant"
    elif change == "unknown-part":
        part["type"] = "input_file"
    else:
        messages[0]["content"] = [image_part() for _ in range(5)]
    with pytest.raises(ApiError) as failure:
        validate_inputs(messages)
    assert SENTINEL not in str(failure.value)


@pytest.mark.asyncio
async def test_image_account_rejection_blocks_replay_but_keeps_text_and_subscription(app_paths):
    def infer(request):
        body = json.loads(request.content)
        if isinstance(body["messages"][-1]["content"], list):
            return httpx.Response(400, json={"error": {"code": "unsupported_image_input", "message": SENTINEL}})
        return response("opencode-go", "Synthetic text response")
    manager, requests = await connected(app_paths, "opencode-go", "mimo-v2.6-pro", infer)
    for run_id in ("image-reject", "image-replay"):
        with pytest.raises(ApiError) as failure:
            _ = [part async for part in manager.stream(image_messages(), scope=SCOPE, run_id=run_id)]
        assert failure.value.code == "image_input_unsupported" and failure.value.status == 409
        assert SENTINEL not in str(failure.value)
    assert len(requests) == 2  # catalogue plus first rejection, no retry/fallback
    result = [part async for part in manager.stream([{"role": "user", "content": "CKD learning"}], scope=SCOPE, run_id="text-after-image")]
    assert result == ["Synthetic text response"]
    selected = manager.connections()["connections"][1]["models"][0]
    assert selected["text_input"] == "supported" and selected["image_input"] == "account_unsupported"
    assert manager.connections()["selected_provider"] == "opencode-go"


@pytest.mark.asyncio
async def test_quota_and_model_access_are_distinct_from_documented_image_capability(app_paths):
    rejection = {"status": 429, "code": "rate_limit_exceeded"}
    manager, requests = await connected(app_paths, "codex", "gpt-6.1-sol", lambda request:
        httpx.Response(rejection["status"], json={"error": {"code": rejection["code"], "message": SENTINEL}}))
    with pytest.raises(ApiError) as failure:
        _ = [part async for part in manager.stream(image_messages(), scope=SCOPE, run_id="quota")]
    assert failure.value.code == "subscription_limit"
    assert manager.connections()["connections"][0]["models"][0]["image_input"] == "supported"
    rejection.update(status=404, code="model_not_found")
    with pytest.raises(ApiError) as failure:
        _ = [part async for part in manager.stream(image_messages(), scope=SCOPE, run_id="account-model")]
    assert failure.value.code == "account_model_unsupported"
    assert manager.connections()["connections"][0]["models"][0]["availability"] == "account_unsupported"
    assert len(requests) == 3 and manager.connections()["selected_provider"] == "codex"


def forbid_payload_writes(monkeypatch):
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    real_open = builtins.open
    real_path_open = Path.open
    def guard(source, mode="r", *args, **kwargs):
        assert not any(flag in mode for flag in "wax+"), "Unexpected filesystem write"
        return real_open(source, mode, *args, **kwargs)
    def path_guard(source, mode="r", *args, **kwargs):
        assert not any(flag in mode for flag in "wax+"), "Unexpected filesystem write"
        return real_path_open(source, mode, *args, **kwargs)
    monkeypatch.setattr(builtins, "open", guard)
    monkeypatch.setattr(Path, "open", path_guard)
    real_os_open = os.open
    def os_open_guard(source, flags, *args, **kwargs):
        assert not flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND), "Unexpected OS write"
        return real_os_open(source, flags, *args, **kwargs)
    monkeypatch.setattr(os, "open", os_open_guard)
    for name in ("mkdir", "link", "symlink", "replace", "rename", "remove", "unlink"):
        monkeypatch.setattr(os, name, lambda *args, **kwargs: pytest.fail("Unexpected filesystem mutation"))
    monkeypatch.setattr(socket.socket, "connect", lambda *args: pytest.fail("Unexpected network connection"))


@pytest.mark.asyncio
async def test_real_hermes_compactor_sdk_selected_route_scope_head_tail_and_no_temp_writes(app_paths, monkeypatch):
    bodies = []
    def infer(request):
        body = json.loads(request.content)
        bodies.append(body)
        text = ("CKD albuminuria and dialysis potassium were discussed; transplantation review remains open." if
            SUMMARY_INSTRUCTIONS in json.dumps(body) else "Synthetic transplant learning response")
        return response("opencode-go", text)
    manager, requests = await connected(app_paths, "opencode-go", "mimo-v2.6-pro", infer)
    messages = long_conversation()
    original = copy.deepcopy(messages)
    plan = manager.context.plan(messages, provider="opencode-go", model="mimo-v2.6-pro")
    from agent.context_compressor import ContextCompressor
    from agent import auxiliary_client, context_compressor
    assert isinstance(plan.engine, ContextCompressor) and plan.turns is not None
    assert "agent.conversation_loop" not in sys.modules and "hermes_logging" not in sys.modules
    monkeypatch.setattr(auxiliary_client, "call_llm", lambda *args, **kwargs: pytest.fail("Auxiliary inference forbidden"))
    monkeypatch.setattr(context_compressor, "call_llm", lambda *args, **kwargs: pytest.fail("Auxiliary inference forbidden"))
    forbid_payload_writes(monkeypatch)
    events = [event async for event in manager.events(messages, scope=SCOPE, run_id="auto-compact")]
    assert [event.type for event in events] == ["started", "progress", "progress", "delta", "completed"]
    assert [event.sequence for event in events] == list(range(1, 6))
    assert events[1].payload["stage"] == "compaction" and events[2].payload["persisted"] is False
    assert events[2].payload["estimated_tokens_after"] < events[2].payload["estimated_tokens_before"]
    assert len(requests) == 3 and all(body["model"] == "mimo-v2.6-pro" for body in bodies)
    assert requests[1].headers["x-opencode-session"] == requests[2].headers["x-opencode-session"]
    assert requests[0].headers["x-opencode-session"] != requests[1].headers["x-opencode-session"]
    assert all(request.headers["user-agent"] == "Renulus/0.1.0" for request in requests)
    assert bodies[-1]["messages"][1]["content"].startswith(messages[0]["content"])
    assert bodies[-1]["messages"][-1]["content"] == messages[-1]["content"]
    assert "RENULUS CONTEXT SUMMARY" in json.dumps(bodies[-1])
    assert "MEMORY.md" not in json.dumps(bodies[-1])
    assert messages == original and not manager.status()["active_runs"]


@pytest.mark.asyncio
async def test_failed_compaction_preserves_input_and_does_not_send_primary_generation(app_paths):
    manager, requests = await connected(app_paths, "opencode-go", "mimo-v2.6-pro", lambda request:
        httpx.Response(429, json={"error": {"message": SENTINEL}}))
    messages = long_conversation()
    original = copy.deepcopy(messages)
    events = [item async for item in manager.events(messages, scope=SCOPE, run_id="summary-fails")]
    assert [item.type for item in events] == ["started", "progress", "error"]
    assert events[-1].payload["code"] == "subscription_limit" and len(requests) == 2
    assert messages == original and not manager.status()["active_runs"]


@pytest.mark.asyncio
async def test_parent_cancel_stops_compaction_child_and_has_one_terminal(app_paths):
    entered = asyncio.Event()
    closed = asyncio.Event()
    class WaitingSummary:
        async def stream(self, provider, model, token, messages):
            try:
                assert messages[0]["content"] == SUMMARY_INSTRUCTIONS
                entered.set()
                await asyncio.Event().wait()
                yield {"type": "completed"}
            finally:
                closed.set()
    manager, requests = await connected(app_paths, "opencode-go", "mimo-v2.6-pro", lambda request: pytest.fail("Inference should use injected transport"), transport=WaitingSummary())
    task = asyncio.create_task(consume(manager, "cancel-compaction"))
    await asyncio.wait_for(entered.wait(), 5)
    assert len(manager.status()["active_runs"]) == 2
    assert await manager.cancel("cancel-compaction")
    events = await asyncio.wait_for(task, 5)
    assert [item.type for item in events] == ["started", "progress", "cancelled"]
    assert closed.is_set() and not manager.status()["active_runs"] and len(requests) == 1


async def consume(manager, run_id):
    return [event async for event in manager.events(long_conversation(), scope=SCOPE, run_id=run_id)]


@pytest.mark.asyncio
async def test_scope_is_validated_before_image_parser_or_provider_use(app_paths, monkeypatch):
    from renulus.runtime import inputs
    monkeypatch.setattr(inputs, "_image_size", lambda part: pytest.fail("Image parsed before scope"))
    manager = ProviderManager(app_paths)
    with pytest.raises(ApiError) as failure:
        _ = [part async for part in manager.stream(image_messages(), scope={}, run_id="no-scope")]
    assert failure.value.code == "invalid_scope"
    assert not manager.status()["active_runs"]


@pytest.mark.asyncio
async def test_inference_auth_failure_invalidates_catalogue_without_image_claim(app_paths):
    manager, requests = await connected(app_paths, "opencode-go", "mimo-v2.6-pro", lambda request:
        httpx.Response(401, json={"error": {"code": "invalid_api_key", "message": SENTINEL}}))
    with pytest.raises(ApiError) as failure:
        _ = [part async for part in manager.stream(image_messages(), scope=SCOPE, run_id="expired-auth")]
    assert failure.value.code == "authentication_required"
    row = manager.connections()["connections"][1]
    assert row["status"] == "authentication_required"
    assert all(model["image_input"] == model["availability"] == "unknown" for model in row["models"])
    assert len(requests) == 2 and manager.connections()["selected_provider"] == "opencode-go"


@pytest.mark.asyncio
async def test_compact_api_returns_scoped_volatile_context_via_exact_selected_route(app_paths):
    from renulus.server import create_app
    app = create_app(app_paths.root, token="synthetic-app-token", source_root=app_paths.source_root)
    manager = app.state.services.registry["provider"]
    bodies = []
    def serve(request):
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "mimo-v2.6-pro"}]})
        bodies.append(json.loads(request.content))
        return response("opencode-go", "Dialysis and CKD were discussed; transplantation review remains open.")
    manager._http_transport = httpx.MockTransport(serve)
    await manager.connect_go("synthetic-go-key", select=True)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1",
        headers={"x-renulus-token": "synthetic-app-token"}) as client:
        result = await client.post("/api/v1/runtime/context/compact", json={
            "run_id": "explicit-compaction", "messages": long_conversation(),
            "scope": SCOPE.model_dump(mode="json"), "model": "mimo-v2.6-pro"})
    assert result.status_code == 200
    context = result.json()
    assert context["compacted"] is True and context["persisted"] is False
    assert context["scope"] == SCOPE.model_dump(mode="json")
    assert context["provider"] == "opencode-go" and context["model"] == "mimo-v2.6-pro"
    assert context["messages"][-1] == long_conversation()[-1]
    assert len(bodies) == 1 and bodies[0]["model"] == "mimo-v2.6-pro"
