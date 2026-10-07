"""Actual SDK and Cases API proofs; synthetic images and controlled HTTP only."""
import asyncio
import base64
from io import BytesIO
import hashlib
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
from renulus.runtime.policy import ALLOWED_MODELS
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


async def connect(services, *, infer=None):
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
    return manager, bodies


def headers(case, *, mode="image"):
    return {"content-type": "image/png", "x-renulus-filename": "synthetic.png",
        "x-renulus-case-options": json.dumps({"revision": case["revision"], "mode": mode,
            "scope": {"kind": "temporary-case", "entity_id": case["id"]}})}


def upload(client, case, raw=None, *, mode="image", filename="synthetic.png", media_type="image/png"):
    path = f"/api/v1/cases/sessions/{case['id']}/attachments"
    options = headers(case, mode=mode)
    options.update({"x-renulus-filename": filename, "content-type": media_type})
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


def test_real_cases_api_actual_sdk_image_wire_explicit_save_retains_original(tmp_path):
    profile = tmp_path / "image-api"
    app = create_app(profile)
    services = app.state.services
    manager, bodies = asyncio.run(connect(services))
    with TestClient(app) as client:
        case = client.post("/api/v1/cases/sessions", json={"text": "Synthetic image learning"}).json()
        caps = client.get("/api/v1/cases/capabilities").json()["image_interpretation"]
        assert caps["supported"] and caps["models"] == list(ALLOWED_MODELS["codex"])
        assert caps["interpretation_verified"] is False
        preview = upload(client, case)
        assert preview.status_code == 202 and preview.headers["cache-control"] == "no-store"
        preview = preview.json()
        encoded = base64.b64encode(image()).decode()
        assert preview["image"]["data"] == encoded and preview["image_retained"] is False
        assert len(bodies) == 0  # Upload/preview never invokes a model.
        assert_absent_from_profile(services, IMAGE_SENTINEL, encoded, QUESTION, ANSWER)
        response = client.post(f"/api/v1/cases/attachments/{preview['id']}/discuss-image",
            json={"revision": 1, "request_id": "explicit-image", "message": QUESTION, "model": MODEL})
        assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
        frames = decode_sse(response.text)
        assert [frame["type"] for frame in frames] == ["started", "answer.delta", "completed"]
        assert frames[0]["payload"]["scope"]["kind"] == "temporary-case"
        assert len(bodies) == 1 and bodies[-1]["model"] == MODEL and bodies[-1]["store"] is False
        parts = next(row["content"] for row in reversed(bodies[-1]["input"]) if row.get("role") == "user")
        assert next(part for part in parts if part["type"] == "input_image")["image_url"] == "data:image/png;base64," + encoded
        assert_absent_from_profile(services, IMAGE_SENTINEL, encoded, QUESTION, ANSWER)
        assert services.registry["case_previews"].jobs[preview["id"]].image is None
        current = client.get(f"/api/v1/cases/sessions/{case['id']}").json()
        assert "omitted from Save" not in current["messages"][0]["content"]
        attachment = current["attachments"][0]
        assert attachment["filename"] == "synthetic.png" and attachment["media_type"] == "image/png"
        assert attachment["bytes"] == len(image()) and attachment["sha256"] == hashlib.sha256(image()).hexdigest()
        assert not attachment["saved"] and attachment["original_available"]
        assert encoded not in json.dumps(current)
        # Later text discussion never replays the image.
        client.post(f"/api/v1/cases/sessions/{case['id']}/discuss", json={
            "revision": current["revision"], "request_id": "later-text", "message": "General learning only"})
        assert "input_image" not in json.dumps(bodies[-1]) and encoded not in json.dumps(bodies[-1])
        current = client.get(f"/api/v1/cases/sessions/{case['id']}").json()
        saved = client.post(f"/api/v1/cases/sessions/{case['id']}/save", json={"revision": current["revision"]}).json()
        assert saved["saved"] and not saved["dirty"]
        assert saved["attachments"][0]["saved"] and saved["attachments"][0]["original_available"]
        binary = client.get(f"/api/v1/cases/sessions/{case['id']}/attachments/{attachment['id']}/original")
        assert binary.status_code == 200 and binary.content == image()
        assert binary.headers["cache-control"] == "no-store"
        assert manager.status()["live_provider_verified"] is False
    with TestClient(create_app(profile)) as restarted:
        reopened = restarted.get(f"/api/v1/cases/sessions/{case['id']}").json()
        assert QUESTION in reopened["messages"][0]["content"] and ANSWER in reopened["messages"][1]["content"]
        assert "omitted from Save" not in reopened["messages"][0]["content"]
        assert reopened["attachments"] == saved["attachments"]
        assert encoded not in json.dumps(reopened)
        binary = restarted.get(f"/api/v1/cases/sessions/{case['id']}/attachments/{attachment['id']}/original")
        assert binary.status_code == 200 and binary.content == image()
        assert binary.headers["cache-control"] == "no-store"


def test_ready_image_keep_stages_original_without_additional_model_call(tmp_path):
    app = create_app(tmp_path / "keep-image")
    services = app.state.services
    _, bodies = asyncio.run(connect(services))
    with TestClient(app) as client:
        case = client.post("/api/v1/cases/sessions", json={"text": "Synthetic kept image"}).json()
        preview = upload(client, case).json()
        stale = client.post(f"/api/v1/cases/attachments/{preview['id']}/keep", json={"revision": 99})
        assert stale.status_code == 409 and len(bodies) == 0
        kept = client.post(f"/api/v1/cases/attachments/{preview['id']}/keep", json={"revision": case["revision"]})
        assert kept.status_code == 200 and kept.headers["cache-control"] == "no-store"
        current = kept.json()
        attachment = current["attachments"][0]
        assert not current["saved"] and current["dirty"]
        assert not attachment["saved"] and attachment["original_available"]
        assert len(bodies) == 0 and current["messages"] == []
        assert base64.b64encode(image()).decode() not in json.dumps(current)
        binary = client.get(f"/api/v1/cases/sessions/{case['id']}/attachments/{attachment['id']}/original")
        assert binary.status_code == 200 and binary.content == image()
        assert_absent_from_profile(services, IMAGE_SENTINEL, base64.b64encode(image()).decode())
        closed = client.post(f"/api/v1/cases/sessions/{case['id']}/close", json={"revision": current["revision"]})
        assert closed.status_code == 200
        assert client.get(f"/api/v1/cases/sessions/{case['id']}/attachments/{attachment['id']}/original").status_code == 404
        assert len(bodies) == 0


@pytest.mark.parametrize("kind", ["png", "jpeg"])
def test_original_image_keep_save_restart_without_helpers_or_provider(tmp_path, kind):
    profile = tmp_path / ("disconnected-original-" + kind)
    app = create_app(profile)
    services = app.state.services
    services.registry.pop("knowledge", None)
    calls = []
    def forbidden(request):
        calls.append(request.url.path)
        raise AssertionError("Keeping an original must not call a provider")
    manager = ProviderManager(services.paths, http_transport=httpx.MockTransport(forbidden))
    services.registry["provider"] = manager
    if kind == "jpeg":
        buffer = BytesIO()
        Image.new("RGB", (12, 8), "white").save(buffer, format="JPEG")
        raw, media_type = buffer.getvalue(), "image/jpeg"
    else:
        raw, media_type = image(), "image/png"
    with TestClient(app) as client:
        case = client.post("/api/v1/cases/sessions", json={"text": "Synthetic disconnected original"}).json()
        capabilities = client.get("/api/v1/cases/capabilities").json()
        assert capabilities["originals"]["supported"] is True
        assert capabilities["originals"]["max_bytes"] == 8 * 1024 * 1024
        assert capabilities["originals"]["image_pixels"] == 16000000
        assert capabilities["image_interpretation"]["supported"] is False
        response = upload(client, case, raw, mode="original", filename="synthetic." + kind,
                          media_type=media_type)
        assert response.status_code == 202
        preview = response.json()
        assert preview["state"] == "ready" and preview["mode"] == "original"
        assert not preview["text"] and not preview["ocr"]
        denied = client.post(f"/api/v1/cases/attachments/{preview['id']}/discuss-image", json={
            "revision": case["revision"], "request_id": "original-not-discussion", "message": QUESTION, "model": MODEL})
        assert denied.status_code == 409 and calls == []
        kept = client.post(f"/api/v1/cases/attachments/{preview['id']}/keep", json={"revision": case["revision"]})
        assert kept.status_code == 200
        current = kept.json()
        attachment = current["attachments"][0]
        assert not attachment["saved"] and attachment["original_available"]
        assert attachment["sha256"] == hashlib.sha256(raw).hexdigest()
        assert base64.b64encode(raw).decode() not in json.dumps(current)
        assert services.db.fetch_all("SELECT * FROM case_attachment_parts") == []
        assert_absent_from_profile(services, IMAGE_SENTINEL, base64.b64encode(raw).decode())
        saved = client.post(f"/api/v1/cases/sessions/{case['id']}/save", json={"revision": current["revision"]})
        assert saved.status_code == 200 and saved.json()["attachments"][0]["saved"]
        original_path = f"/api/v1/cases/sessions/{case['id']}/attachments/{attachment['id']}/original"
        binary = client.get(original_path)
        assert binary.status_code == 200 and binary.content == raw
        assert binary.headers["cache-control"] == "no-store"
        assert binary.headers["content-type"] == media_type
        assert calls == [] and manager.status()["live_provider_verified"] is False
    with TestClient(create_app(profile)) as restarted:
        reopened = restarted.get(f"/api/v1/cases/sessions/{case['id']}").json()
        assert reopened["attachments"] == saved.json()["attachments"]
        assert base64.b64encode(raw).decode() not in json.dumps(reopened)
        assert restarted.get(original_path).content == raw


@pytest.mark.parametrize("condition", ["malformed", "too-large"])
def test_disconnected_original_image_denials_do_not_keep_bytes_or_call_provider(tmp_path, condition):
    app = create_app(tmp_path / ("original-denial-" + condition))
    services = app.state.services
    services.registry.pop("knowledge", None)
    with TestClient(app) as client:
        case = client.post("/api/v1/cases/sessions", json={"text": "Synthetic original guard"}).json()
        if condition == "malformed":
            response = upload(client, case, b"\x89PNG\r\n\x1a\ninvalid", mode="original")
            assert response.status_code in (400, 422)
        else:
            options = headers(case, mode="original")
            options["content-length"] = str(8 * 1024 * 1024 + 1)
            response = client.post(f"/api/v1/cases/sessions/{case['id']}/attachments/extract",
                                   headers=options, content=image())
            assert response.status_code == 413
        assert client.get(f"/api/v1/cases/sessions/{case['id']}").json()["attachments"] == []
        assert services.db.fetch_all("SELECT * FROM case_attachment_parts") == []
        assert_absent_from_profile(services, IMAGE_SENTINEL, base64.b64encode(image()).decode())


def test_documented_image_model_can_prepare_without_probe_or_provider_call(tmp_path):
    app = create_app(tmp_path / "unverified-image")
    services = app.state.services
    manager, bodies = asyncio.run(connect(services))
    with TestClient(app) as client:
        case = client.post("/api/v1/cases/sessions", json={"text": "Synthetic case"}).json()
        path = f"/api/v1/cases/sessions/{case['id']}/attachments/prepare"
        response = client.post(path, headers=headers(case))
        assert response.status_code == 201
        assert not bodies and manager.connections()["selected_provider"] == "codex"
    assert_absent_from_profile(services, IMAGE_SENTINEL, QUESTION)


def test_actual_runtime_go_text_route_is_active_without_claiming_image_support(tmp_path):
    app = create_app(tmp_path / "go-active")
    services = app.state.services
    calls = []
    def limited_http(request):
        calls.append(request)
        assert json.loads(request.content)["model"] == "mimo-v2.6-pro"
        return httpx.Response(429, json={"error": {"code": "rate_limit_exceeded"}})
    manager = ProviderManager(services.paths, http_transport=httpx.MockTransport(limited_http))
    manager._settings["selected_provider"] = "opencode-go"
    manager._settings["connections"]["opencode-go"] = {"access_token": "synthetic-only"}
    manager._catalogs["opencode-go"] = {"mimo-v2.6-pro"}
    services.registry["provider"] = manager
    with TestClient(app) as client:
        case = client.post("/api/v1/cases/sessions", json={"text": QUESTION}).json()
        capability = client.get("/api/v1/cases/capabilities").json()["image_interpretation"]
        assert not capability["supported"] and capability["code"] != "learning_use_unverified"
        image_denial = client.post(f"/api/v1/cases/sessions/{case['id']}/attachments/prepare", headers=headers(case))
        assert image_denial.status_code == 409 and calls == []
        response = client.post(f"/api/v1/cases/sessions/{case['id']}/discuss", json={
            "revision": 1, "request_id": "go-active", "message": IMAGE_SENTINEL})
        frames = decode_sse(response.text)
        error = frames[-1]["payload"]["error"]
        assert frames[-1]["type"] == "failed"
        assert error["code"] == "subscription_limit" and error["retryable"] is True
        assert len(calls) == 1 and manager.connections()["selected_provider"] == "opencode-go"
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
        assert len(bodies) == 0
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
