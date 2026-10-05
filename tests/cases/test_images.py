"""Actual SDK and Cases API proofs; synthetic images and controlled HTTP only."""
import asyncio
import base64
from io import BytesIO
import json
import socket
import time

import httpx
from fastapi.testclient import TestClient
from PIL import Image, PngImagePlugin
import pytest

from renulus.cases.models import ImageDiscussion, StartCase
from renulus.cases.api import create_router
from renulus.contracts import ContextScope, Scope
from renulus.runtime.manager import ProviderManager
from renulus.runtime.policy import learning_usage
from renulus.server import create_app

from .conftest import assert_absent_from_profile
from .test_api import decode_sse

MODEL = "gpt-6.1-sol"
IMAGE_SENTINEL = "RENULUS_SYNTHETIC_IMAGE_BYTES_NEVER_SAVE_9217"
QUESTION = "RENULUS_SYNTHETIC_IMAGE_QUESTION_2317"
ANSWER = "RENULUS_SYNTHETIC_IMAGE_ANSWER_4721"


def image():
    output = BytesIO()
    info = PngImagePlugin.PngInfo()
    info.add_text("Synthetic", IMAGE_SENTINEL)
    Image.new("RGB", (12, 8), "white").save(output, format="PNG", pnginfo=info)
    return output.getvalue()


def sdk_response(text=ANSWER):
    frames = [{"type": "response.output_text.delta", "delta": text, "item_id": "synthetic",
               "output_index": 0, "content_index": 0, "sequence_number": 1},
              {"type": "response.completed", "sequence_number": 2, "response": {
                  "id": "synthetic", "object": "response", "created_at": 1,
                  "status": "completed", "model": MODEL, "output": []}}]
    return httpx.Response(200, headers={"content-type": "text/event-stream"},
        content="".join("data: " + json.dumps(frame) + "\n\n" for frame in frames))


async def connect(services, *, supported=True, infer=None):
    bodies = []
    def serve(request):
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"models": [{"slug": MODEL, "visibility": "list"}]})
        bodies.append(json.loads(request.content))
        return infer(request) if infer else sdk_response()
    manager = ProviderManager(services.paths, http_transport=httpx.MockTransport(serve))
    manager._settings["connections"]["codex"] = {"client_id": "synthetic-client",
        "access_token": "synthetic-plan-token", "expires_at": time.time() + 1200}
    manager._settings["selected_provider"] = "codex"
    await manager.refresh("codex")
    services.registry["provider"] = manager
    if supported:
        # Establish capability through an actual SDK request, not a test-only flag.
        part = {"type": "image", "media_type": "image/png",
                "data": base64.b64encode(image()).decode(), "detail": "auto"}
        _ = [delta async for delta in manager.stream([{
            "role": "user", "content": [{"type": "text", "text": "Synthetic capability probe"}, part]}],
            scope=ContextScope(kind=Scope.TEMPORARY_CASE), run_id="synthetic-image-probe", model=MODEL)]
    return manager, bodies


def headers(case, *, mode="image"):
    return {"content-type": "image/png", "x-renulus-filename": "synthetic.png",
        "x-renulus-case-options": json.dumps({"revision": case["revision"], "mode": mode,
            "scope": {"kind": "temporary-case", "entity_id": case["id"]}})}


def upload(client, case, raw=None):
    path = f"/api/v1/cases/sessions/{case['id']}/attachments"
    options = headers(case)
    reservation = client.post(path + "/prepare", headers=options)
    assert reservation.status_code == 201, reservation.text
    options["x-renulus-preview-id"] = reservation.json()["id"]
    response = client.post(path + "/extract", headers=options, content=image() if raw is None else raw)
    return response


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    original = socket.socket.connect
    def deny(sock, address):
        # Windows asyncio builds its wake-up socketpair over loopback.
        if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
            return original(sock, address)
        raise AssertionError("Public sockets are forbidden in Cases image proofs")
    monkeypatch.setattr(socket.socket, "connect", deny)


def test_real_cases_api_actual_sdk_image_wire_explicit_save_omits_image(tmp_path):
    profile = tmp_path / "image-api"
    app = create_app(profile)
    services = app.state.services
    manager, bodies = asyncio.run(connect(services))
    with TestClient(app) as client:
        case = client.post("/api/v1/cases/sessions", json={"text": "Synthetic image learning"}).json()
        caps = client.get("/api/v1/cases/capabilities").json()["image_interpretation"]
        assert caps["supported"] and caps["models"] == [MODEL]
        assert caps["interpretation_verified"] is False
        preview = upload(client, case)
        assert preview.status_code == 202 and preview.headers["cache-control"] == "no-store"
        preview = preview.json()
        encoded = base64.b64encode(image()).decode()
        assert preview["image"]["data"] == encoded and preview["image_retained"] is False
        assert len(bodies) == 1  # Upload/preview never invokes a model.
        assert_absent_from_profile(services, IMAGE_SENTINEL, encoded, QUESTION, ANSWER)
        response = client.post(f"/api/v1/cases/attachments/{preview['id']}/discuss-image",
            json={"revision": 1, "request_id": "explicit-image", "message": QUESTION, "model": MODEL})
        assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
        frames = decode_sse(response.text)
        assert [frame["type"] for frame in frames] == ["started", "answer.delta", "completed"]
        assert frames[0]["payload"]["scope"]["kind"] == "temporary-case"
        assert len(bodies) == 2 and bodies[-1]["model"] == MODEL and bodies[-1]["store"] is False
        parts = next(row["content"] for row in reversed(bodies[-1]["input"]) if row.get("role") == "user")
        assert next(part for part in parts if part["type"] == "input_image")["image_url"] == "data:image/png;base64," + encoded
        assert_absent_from_profile(services, IMAGE_SENTINEL, encoded, QUESTION, ANSWER)
        assert services.registry["case_previews"].jobs[preview["id"]].image is None
        current = client.get(f"/api/v1/cases/sessions/{case['id']}").json()
        assert "omitted from Save" in current["messages"][0]["content"]
        # Later text discussion never replays the image.
        client.post(f"/api/v1/cases/sessions/{case['id']}/discuss", json={
            "revision": current["revision"], "request_id": "later-text", "message": "General learning only"})
        assert "input_image" not in json.dumps(bodies[-1]) and encoded not in json.dumps(bodies[-1])
        current = client.get(f"/api/v1/cases/sessions/{case['id']}").json()
        saved = client.post(f"/api/v1/cases/sessions/{case['id']}/save", json={"revision": current["revision"]}).json()
        assert saved["saved"] and not saved["dirty"]
        assert_absent_from_profile(services, IMAGE_SENTINEL, encoded)
        assert manager.status()["live_provider_verified"] is False
    with TestClient(create_app(profile)) as restarted:
        reopened = restarted.get(f"/api/v1/cases/sessions/{case['id']}").json()
        assert QUESTION in reopened["messages"][0]["content"] and ANSWER in reopened["messages"][1]["content"]
        assert "omitted from Save" in reopened["messages"][0]["content"]
        assert encoded not in json.dumps(reopened)


def test_unknown_account_cannot_prepare_or_send_and_no_fallback(tmp_path):
    app = create_app(tmp_path / "unverified-image")
    services = app.state.services
    manager, bodies = asyncio.run(connect(services, supported=False))
    with TestClient(app) as client:
        case = client.post("/api/v1/cases/sessions", json={"text": "Synthetic case"}).json()
        path = f"/api/v1/cases/sessions/{case['id']}/attachments/prepare"
        response = client.post(path, headers=headers(case))
        assert response.status_code == 409 and response.json()["error"]["code"] == "image_capabilities_unverified"
        assert not bodies and manager.connections()["selected_provider"] == "codex"
    assert_absent_from_profile(services, IMAGE_SENTINEL, QUESTION)


def test_actual_runtime_go_denial_keeps_public_nonretryable_error_before_io(tmp_path, monkeypatch):
    app = create_app(tmp_path / "go-policy-denied")
    services = app.state.services
    calls = []
    def denied_http(request):
        calls.append("http")
        raise AssertionError("Policy denial must precede provider HTTP")
    async def denied_credentials(provider):
        calls.append("credentials")
        raise AssertionError("Policy denial must precede credentials")
    manager = ProviderManager(services.paths, http_transport=httpx.MockTransport(denied_http))
    manager._settings["selected_provider"] = "opencode-go"
    manager._settings["connections"]["opencode-go"] = {"api_key": "synthetic-only"}
    manager._catalogs["opencode-go"] = {"mimo-v2.6-pro"}
    monkeypatch.setattr(manager, "_access_token", denied_credentials)
    services.registry["provider"] = manager
    with TestClient(app) as client:
        case = client.post("/api/v1/cases/sessions", json={"text": QUESTION}).json()
        capability = client.get("/api/v1/cases/capabilities").json()["image_interpretation"]
        assert capability["code"] == "learning_use_unverified" and not capability["retryable"]
        image_denial = client.post(f"/api/v1/cases/sessions/{case['id']}/attachments/prepare", headers=headers(case))
        assert image_denial.status_code == 403 and not image_denial.json()["error"]["retryable"]
        response = client.post(f"/api/v1/cases/sessions/{case['id']}/discuss", json={
            "revision": 1, "request_id": "go-denied", "message": IMAGE_SENTINEL})
        frames = decode_sse(response.text)
        error = frames[-1]["payload"]["error"]
        assert frames[-1]["type"] == "failed"
        assert error == {"code": "learning_use_unverified",
            "message": learning_usage("opencode-go")["message"], "retryable": False}
        assert calls == [] and manager.connections()["selected_provider"] == "opencode-go"
        current = client.get(f"/api/v1/cases/sessions/{case['id']}").json()
        assert not any(row["role"] == "assistant" for row in current["messages"])
        assert_absent_from_profile(services, IMAGE_SENTINEL, QUESTION)


@pytest.mark.parametrize("condition", ["model", "account", "revision", "cancel", "malformed", "limit"])
def test_image_send_guards_do_not_infer_or_retain(tmp_path, condition):
    app = create_app(tmp_path / condition)
    services = app.state.services
    manager, bodies = asyncio.run(connect(services))
    with TestClient(app) as client:
        case = client.post("/api/v1/cases/sessions", json={"text": "Synthetic case"}).json()
        if condition in ("malformed", "limit"):
            raw = b"\x89PNG\r\n\x1a\ninvalid" if condition == "malformed" else b"x" * (8 * 1024 * 1024 + 1)
            response = upload(client, case, raw)
            assert response.status_code in (400, 413, 422)
        else:
            preview = upload(client, case).json()
            if condition == "account":
                asyncio.run(manager.disconnect("codex"))
            if condition == "cancel":
                client.delete(f"/api/v1/cases/attachments/{preview['id']}")
            response = client.post(f"/api/v1/cases/attachments/{preview['id']}/discuss-image", json={
                "revision": 99 if condition == "revision" else 1, "request_id": "guarded-image",
                "message": QUESTION, "model": "unapproved" if condition == "model" else MODEL})
            assert response.status_code == 409
            client.delete(f"/api/v1/cases/attachments/{preview['id']}")
        assert len(bodies) == 1
        assert_absent_from_profile(services, IMAGE_SENTINEL, base64.b64encode(image()).decode(), QUESTION, ANSWER)


@pytest.mark.asyncio
async def test_actual_sdk_cases_api_cancel_clears_pinned_image_and_late_result(tmp_path):
    app = create_app(tmp_path / "image-cancel")
    services = app.state.services
    blocked = asyncio.Event()
    class PausedImageResponse(httpx.AsyncByteStream):
        async def __aiter__(self):
            frame = {"type": "response.output_text.delta", "delta": "Synthetic partial", "item_id": "synthetic",
                     "output_index": 0, "content_index": 0, "sequence_number": 1}
            yield ("data: " + json.dumps(frame) + "\n\n").encode()
            blocked.set()
            await asyncio.Event().wait()
    manager, bodies = await connect(services)
    # Swap only controlled HTTP; the existing Hermes + SDK consumer remains real.
    manager._http_transport = httpx.MockTransport(lambda request: httpx.Response(200,
        headers={"content-type": "text/event-stream"}, stream=PausedImageResponse()))
    manager._transport = None
    router = create_router(services)
    repository = services.registry["cases"]
    previews = services.registry["case_previews"]
    case = repository.start(StartCase(text="Synthetic cancellation case"))
    job = previews.preflight(case["id"], 1, ContextScope(kind=Scope.TEMPORARY_CASE, entity_id=case["id"]), "synthetic.png", "Image", "image")
    previews.start(job, image())
    endpoint = next(route.endpoint for route in router.routes if route.path.endswith("/attachments/{preview_id}/discuss-image"))
    response = await endpoint(job.id, ImageDiscussion(revision=1, request_id="cancel-image", message=QUESTION, model=MODEL))
    iterator = response.body_iterator
    started = decode_sse(await anext(iterator))[0]
    assert decode_sse(await anext(iterator))[0]["type"] == "answer.delta"
    pending = asyncio.create_task(anext(iterator))
    await asyncio.wait_for(blocked.wait(), 2)
    cancel = next(route.endpoint for route in router.routes if route.path.endswith("/runs/{run_id}/cancel"))
    result = await cancel(started["run_id"])
    assert result["status"] == "cancelled"
    assert decode_sse(await asyncio.wait_for(pending, 2))[0]["type"] == "cancelled"
    with pytest.raises(StopAsyncIteration):
        await anext(iterator)
    assert job.image is None and repository._runs[started["run_id"]].iterator is None
    current = repository.get(case["id"])
    assert not any(row["role"] == "assistant" for row in current["messages"])
    assert_absent_from_profile(services, IMAGE_SENTINEL, base64.b64encode(image()).decode(), QUESTION, ANSWER)
