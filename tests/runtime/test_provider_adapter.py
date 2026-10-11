"""Public subscription preparation; all credentials and transports are synthetic."""
import asyncio
import json
from uuid import uuid4

import httpx
import pytest

from renulus.runtime.manager import ProviderManager
from renulus.contracts import ApiError, ContextScope, Scope


@pytest.mark.asyncio
async def test_selected_default_prepares_exact_wire_route_without_credential_in_descriptor(app_paths, monkeypatch):
    canary = uuid4().hex
    monkeypatch.setenv("OPENAI_API_KEY", uuid4().hex)
    calls = []

    def serve(request):
        calls.append(request.url.path)
        return httpx.Response(200, json={"data": [{"id": "mimo-v2.6-pro"}]})

    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(serve))
    await manager.connect_go(canary, select=True)
    manager.select("opencode-go", "deepseek-v4.1-flash")
    route = await manager.prepare_harness_route()
    descriptor = route.descriptor()
    assert descriptor["provider_id"] == "opencode-go"
    assert descriptor["catalog_model_id"] == descriptor["wire_model_id"] == "deepseek-v4.1-flash"
    assert descriptor["endpoint"] == "https://opencode.ai/zen/go/v1/chat/completions"
    assert descriptor["protocol"] == "openai-chat"
    assert descriptor["catalogue_listed"] is False
    assert isinstance(descriptor["credential_ref"], str)
    if canary in json.dumps(descriptor) + repr(route) + json.dumps(manager.status()):
        pytest.fail("Credential leaked into a public route", pytrace=False)
    assert calls == ["/zen/go/v1/models"]


@pytest.mark.asyncio
async def test_harness_401_invalidates_reference_until_explicit_refresh_and_preserves_selection(app_paths):
    canary = uuid4().hex
    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"data": [{"id": "mimo-v2.6-pro"}]})))
    await manager.connect_go(canary, select=True)
    route = await manager.prepare_harness_route()
    if await manager.credential_for_harness(route) != canary:
        pytest.fail("Protected lookup returned the wrong credential", pytrace=False)
    manager.observe_harness_result(route, code="authentication_required")
    with pytest.raises(ApiError) as denied:
        await manager.credential_for_harness(route)
    assert denied.value.code == "connection_changed"
    with pytest.raises(ApiError) as blocked:
        await manager.prepare_harness_route()
    assert blocked.value.code == "authentication_required"
    await manager.refresh("opencode-go")
    fresh = await manager.prepare_harness_route()
    assert fresh.credential_epoch > route.credential_epoch
    assert manager.connections()["selected_provider"] == "opencode-go"
    with pytest.raises(ApiError):
        await manager.credential_for_harness(route)
    manager.observe_harness_result(route, code="authentication_required")
    assert manager.connections()["connections"][1]["status"] == "connected"


@pytest.mark.asyncio
async def test_old_completion_cannot_restore_observations_after_another_run_gets_401(app_paths):
    entered, release = asyncio.Event(), asyncio.Event()

    class ExternalInference:
        async def stream(self, provider, model, token, messages):
            if messages[0]["content"] == "Synthetic old answer":
                entered.set()
                await release.wait()
                yield {"type": "completed"}
            else:
                raise ApiError("authentication_required", "Synthetic authentication failure", 401)

    manager = ProviderManager(app_paths, transport=ExternalInference(), http_transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"data": [{"id": "mimo-v2.6-pro"}]})))
    await manager.connect_go(uuid4().hex, select=True)

    async def events(text, run):
        return [item async for item in manager.events([{"role": "user", "content": text}],
            scope=ContextScope(kind=Scope.TEMPORARY_CASE), run_id=run)]

    old = asyncio.create_task(events("Synthetic old answer", "old-answer"))
    try:
        await asyncio.wait_for(entered.wait(), 3)
        failed = await events("Synthetic denied answer", "denied-answer")
        assert failed[-1].payload["code"] == "authentication_required"
        release.set()
        flow = await asyncio.wait_for(old, 3)
        assert flow[-1].type == "error" and flow[-1].payload["code"] == "connection_changed"
        model = manager.connections()["connections"][1]["models"][0]
        assert model["text_input"] == "unknown"
        assert model["capability_evidence"]["text"] == "none"
        assert not manager.status()["completed_requests"]
    finally:
        release.set()
        await manager.close()
        await asyncio.gather(old, return_exceptions=True)


@pytest.mark.asyncio
async def test_explicit_refresh_401_invalidates_previously_observed_access(app_paths):
    denied = False

    def serve(request):
        return httpx.Response(401 if denied else 200, json={"data": [{"id": "mimo-v2.6-pro"}]})

    class SyntheticInference:
        async def stream(self, provider, model, token, messages):
            yield {"type": "completed"}

    manager = ProviderManager(app_paths, transport=SyntheticInference(), http_transport=httpx.MockTransport(serve))
    try:
        await manager.connect_go(uuid4().hex, select=True)
        [item async for item in manager.stream([{"role": "user", "content": "Synthetic renal learning"}],
            scope=ContextScope(kind=Scope.TEMPORARY_CASE), run_id="access-observation")]
        before = await manager.prepare_harness_route()
        assert manager.connections()["connections"][1]["models"][0]["text_input"] == "supported"
        denied = True
        with pytest.raises(ApiError):
            await manager.refresh("opencode-go")
        after = manager.connections()["connections"][1]["models"][0]
        assert after["availability"] == after["text_input"] == after["image_input"] == "unknown"
        assert after["credential_epoch"] > before.credential_epoch
        with pytest.raises(ApiError) as stale:
            await manager.credential_for_harness(before)
        assert stale.value.code == "connection_changed"
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_capability_report_and_observations_are_bound_to_the_prepared_route(app_paths):
    status = 200
    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(
        lambda request: httpx.Response(status, json={"data": [{"id": "mimo-v2.6-pro"}]})))
    try:
        await manager.connect_go(uuid4().hex, select=True)
        route = await manager.prepare_harness_route()
        before = manager.harness_capabilities(route)
        assert before["route"] == route.descriptor()
        assert before["documented_support"] == {"text": "unknown", "image": "unknown", "tools": "unknown"}
        assert before["tool_input"] == "unknown"
        manager.observe_harness_result(route, code="completed", images=True, tools=True)
        observed = manager.harness_capabilities(route)
        assert observed["text_input"] == observed["image_input"] == observed["tool_input"] == "supported"
        assert observed["capability_evidence"]["tools"] == "completed_request"
        assert not observed["image_interpretation_verified"]
        status = 503
        with pytest.raises(ApiError):
            await manager.refresh("opencode-go")
        transient = manager.harness_capabilities(route)
        assert transient["availability"] == "unknown"
        assert transient["credential_epoch"] == route.credential_epoch
        assert transient["image_input"] == transient["tool_input"] == "supported"
        manager.observe_harness_result(route, code="authentication_required")
        with pytest.raises(ApiError):
            manager.harness_capabilities(route)
        status = 200
        await manager.refresh("opencode-go")
        current = await manager.prepare_harness_route()
        manager.observe_harness_result(route, code="completed", images=True, tools=True)
        assert manager.harness_capabilities(current)["tool_input"] == "unknown"
        manager.observe_harness_result(current, code="unsupported_image_input", images=True)
        assert manager.harness_capabilities(current)["image_input"] == "account_unsupported"
        manager.observe_harness_result(current, code="model_access_denied")
        assert manager.connections()["connections"][1]["models"][0]["availability"] == "account_unsupported"
    finally:
        await manager.close()


def test_final_image_decoder_reuses_existing_mime_pixel_and_frame_limits():
    import base64
    from io import BytesIO

    from PIL import Image
    from renulus.runtime.provider_adapter import validate_harness_images

    def image(size=(1, 1), fmt="PNG"):
        buffer = BytesIO()
        Image.new("L", size).save(buffer, format=fmt)
        return {"type": "image", "media_type": "image/" + fmt.lower(),
                "data": base64.b64encode(buffer.getvalue()).decode("ascii")}

    valid = image()
    assert validate_harness_images([valid]) is None
    for images in [[{**valid, "media_type": "image/jpeg"}],
                   [image(size=(4001, 4000))], [valid] * 5,
                   [{**valid, "data": base64.b64encode(b"\x89PNG\r\n\x1a\n").decode("ascii")}],
                   [{"type": "text", "text": "Supply no image"}],
                   [{**valid, "data": uuid4().hex}]]:
        with pytest.raises(ApiError):
            validate_harness_images(images)


@pytest.mark.asyncio
async def test_gateway_public_revalidation_and_redacted_errors_require_no_private_access(app_paths):
    from renulus.runtime.provider_adapter import SubscriptionRoute

    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"data": [{"id": "mimo-v2.6-pro"}]})))
    try:
        await manager.connect_go(uuid4().hex, select=True)
        route = SubscriptionRoute(**(await manager.prepare_harness_route()).descriptor())
        assert manager.require_harness_route(route) is None
        manager.observe_harness_stream_error(route, "unsupported_image_input", images=True)
        assert manager.harness_capabilities(route)["image_input"] == "account_unsupported"
        canary = uuid4().hex
        request = httpx.Request("POST", route.endpoint)
        error = httpx.HTTPStatusError(canary, request=request, response=httpx.Response(401, request=request))
        public = manager.observe_harness_error(route, error)
        assert public.code == "authentication_required"
        if canary in str(public) + repr(public):
            pytest.fail("Credential leaked into a gateway error", pytrace=False)
        with pytest.raises(ApiError) as stale:
            manager.require_harness_route(route)
        assert stale.value.code == "connection_changed"
        await manager.refresh("opencode-go")
        current = await manager.prepare_harness_route()
        manager.observe_harness_stream_error(route, "invalid_api_key")
        assert manager.require_harness_route(current) is None
    finally:
        await manager.close()
