"""Final HTTP dispatch through real protected routes and durable H04 authority."""
import base64
import asyncio
import json
import os
from pathlib import Path
import time
from uuid import uuid4
from dataclasses import replace

import httpx
import pytest

from renulus.contracts import ApiError
from renulus.runtime.harness_configuration import (
    CandidateHealth, ConfigurationAuthority, ConfigurationSpec, ConnectionReference,
    RestartBoundary, RolePolicy, RouteLimits,
)
from renulus.runtime.harness_domain import DomainCancellation, DomainCancelled
from renulus.runtime.harness_gateway import GatewayBounds, HarnessGateway
from renulus.runtime.manager import ProviderManager
from renulus.runtime.protected import ConnectionStore
from renulus.runtime.provider_adapter import validate_harness_images
from renulus.storage.database import Database


@pytest.fixture
async def configured(app_paths, request):
    credential = uuid4().hex
    provider = getattr(request, "param", "opencode-go")
    if provider == "codex":
        store = ConnectionStore(app_paths.root, app_paths.state)
        store.save({"version": 1, "host_id": "synthetic-host", "selected_provider": "codex",
            "connections": {"codex": {"access_token": credential, "expires_at": time.time() + 600}}})
    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"data": [{"id": "mimo-v2.6-pro"}]})))
    if provider == "opencode-go":
        await manager.connect_go(credential, select=True)
    route = await manager.prepare_harness_route()
    authority = ConfigurationAuthority(Database(app_paths.state / "gateway.sqlite"))
    connection = ConnectionReference(provider=route.provider_id,
        credential_reference=route.credential_ref, credential_revision=route.credential_epoch,
        selected_model=route.catalog_model_id)
    spec = ConfigurationSpec(connection=connection, registry_hash="a" * 64,
        roles=(RolePolicy(purpose="explain", output_tokens=32),), capabilities=("library-read",))
    version = authority.stage(spec)
    assert authority.validate(version, lambda candidate: CandidateHealth(
        configuration_version=candidate.version, grant_epoch=candidate.grant_epoch,
        registry_hash=candidate.spec.registry_hash))
    authority.activate(version, RestartBoundary(admission_closed=True, runtime_stopped=True,
        domain_settled=True), expected_effective=None)
    authority.open_admission(version, registry_hash=spec.registry_hash, grant_epoch=0)
    authority.begin_run("learning-run", "explain", capability_scope=("library-read",))
    yield manager, authority, route, credential
    await manager.close()


def envelope(route, **body_changes):
    body = {"model": route.wire_model_id, "stream": True, "max_completion_tokens": 32,
            "messages": [{"role": "user", "content": "Explain synthetic dialysis"}], **body_changes}
    return {"method": "POST", "url": route.endpoint,
            "headers": {"content-type": "application/json", "user-agent": "Renulus/0.1.0",
                        "x-opencode-session": "synthetic-session"},
            "body_base64": base64.b64encode(json.dumps(body).encode()).decode()}


def gateway(configured, handler, **options):
    manager, authority, _, _ = configured
    settings = dict(cancellation=DomainCancellation(), check_current=lambda: True,
        http_transport=httpx.MockTransport(handler),
        bounds=GatewayBounds(max_request_bytes=4096, max_response_bytes=4096, timeout_seconds=3))
    return HarnessGateway(manager, authority, **{**settings, **options})


async def dispatch(client, route, request=None, **options):
    settings = dict(limits=RouteLimits(input_tokens=100, output_tokens=32, window_tokens=132),
        input_tokens=100, required_capabilities=("library-read",), request_kind="primary")
    return await client.dispatch(options.pop("run_id", "learning-run"), options.pop("step_id", "first-step"),
        route, envelope(route) if request is None else request, **{**settings, **options})


async def test_one_protected_post_returns_bounded_native_bytes_and_spends_one_permit(configured):
    manager, authority, route, credential = configured
    calls = []
    payload = b"data: [DONE]\n\n"

    def serve(request):
        calls.append(request)
        if request.headers.get("authorization") != "Bearer " + credential:
            pytest.fail("Final HTTP did not receive the protected credential", pytrace=False)
        assert authority.run("learning-run")["spent_dispatches"] == 1
        return httpx.Response(200, headers={"content-type": "text/event-stream",
            "set-cookie": "untrusted-provider-state"}, content=payload)

    result = await dispatch(gateway(configured, serve), route)
    assert len(calls) == 1 and str(calls[0].url) == route.endpoint
    assert result["status"] == 200
    assert result["headers"] == {"content-type": "text/event-stream"}
    assert base64.b64decode(result["body_base64"]) == payload
    assert authority.permit(result["permit_id"])["state"] == "confirmed"
    assert manager.harness_capabilities(route)["text_input"] == "unknown"
    if credential in json.dumps(result):
        pytest.fail("Credential leaked into the native result", pytrace=False)


@pytest.mark.parametrize("change", [
    {"method": "GET"}, {"method": "post"},
    {"url": "https://opencode.ai/zen/go/v1/chat/completions?model=other"},
    {"url": "wss://opencode.ai/zen/go/v1/chat/completions"},
    {"url": "https://synthetic.invalid/fallback"},
    {"headers": {"authorization": "Bearer synthetic-native-auth"}},
    {"headers": {"cookie": "synthetic-ambient-state"}},
    {"headers": {"host": "synthetic.invalid"}},
    {"headers": {"Content-Type": "application/json", "content-type": "application/json"}},
    {"fallback": True}, {"webSocket": {}}, {"route": {}}, {"input_tokens": 1},
    {"body_base64": "!invalid!"}, {"body_base64": "A" * 5500},
])
async def test_untrusted_envelope_cannot_change_transport_or_supply_authority(configured, change):
    _, authority, route, _ = configured
    calls = []
    client = gateway(configured, lambda request: calls.append(request) or httpx.Response(200))
    with pytest.raises(ApiError):
        await dispatch(client, route, {**envelope(route), **change})
    assert not calls and authority.run("learning-run")["spent_dispatches"] == 0


@pytest.mark.parametrize("failure", ["redirect", "auth", "rate", "server", "oversize", "credential", "read"])
async def test_rejected_or_uncertain_http_never_returns_credentials_or_replays(configured, failure):
    manager, authority, route, credential = configured
    calls = []

    def serve(request):
        calls.append(request)
        if failure == "read":
            raise httpx.ReadError("Synthetic connection interrupted")
        status = {"redirect": 302, "auth": 401, "rate": 429, "server": 503}.get(failure, 200)
        payload = b"x" * 4097 if failure == "oversize" else credential.encode()
        return httpx.Response(status, headers={"content-type": "text/event-stream",
            "location": "https://synthetic.invalid/redirect"}, content=payload)

    client = gateway(configured, serve)
    with pytest.raises(ApiError) as denied:
        await dispatch(client, route)
    if credential in str(denied.value):
        pytest.fail("Credential leaked into a gateway diagnostic", pytrace=False)
    with pytest.raises(ApiError):
        await dispatch(client, route)
    assert len(calls) == 1 and authority.run("learning-run")["spent_dispatches"] == 1
    authority.settle_run("learning-run")
    if failure == "auth":
        with pytest.raises(ApiError):
            manager.require_harness_route(route)


@pytest.mark.parametrize("change", [
    {"model": "deepseek-v4.1-flash"}, {"stream": False}, {"store": True},
    {"max_completion_tokens": None}, {"max_completion_tokens": True},
    {"max_completion_tokens": 33}, {"max_completion_tokens": 0},
    {"max_tokens": 1}, {"max_output_tokens": 1}, {"previous_response_id": "other-response"},
    {"context_management": []}, {"truncation": "auto"}, {"conversation": "other-session"},
    {"api_key": "synthetic-native-key"},
])
async def test_final_wire_identity_and_output_bound_are_checked_before_reservation(configured, change):
    _, authority, route, _ = configured
    calls = []
    with pytest.raises(ApiError):
        await dispatch(gateway(configured, lambda request: calls.append(request) or httpx.Response(200)),
                       route, envelope(route, **change))
    assert not calls and authority.run("learning-run")["spent_dispatches"] == 0


@pytest.mark.parametrize("source", ["domain", "task", "revocation", "check-current"])
async def test_cancellation_retains_request_ownership_until_actual_http_finalizer(configured, source):
    _, authority, route, _ = configured
    entered, closing, released = asyncio.Event(), asyncio.Event(), asyncio.Event()
    current = True
    cancellation = DomainCancellation()

    class HeldStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            entered.set()
            await asyncio.Event().wait()
            yield b"unreachable"

        async def aclose(self):
            closing.set()
            await released.wait()

    client = gateway(configured, lambda request: httpx.Response(200,
        headers={"content-type": "text/event-stream"}, stream=HeldStream()),
        cancellation=cancellation, check_current=lambda: current)
    task = asyncio.create_task(dispatch(client, route))
    try:
        await asyncio.wait_for(entered.wait(), 2)
        if source == "task":
            task.cancel()
        elif source == "domain":
            cancellation.cancel()
        elif source == "revocation":
            authority.revoke("library-read")
        else:
            current = False
        await asyncio.wait_for(closing.wait(), 2)
        task.cancel()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert not task.done(), "Cancellation ended ownership before the HTTP finalizer"
        with pytest.raises(ApiError):
            authority.settle_run("learning-run")
        released.set()
        with pytest.raises((ApiError, DomainCancelled, asyncio.CancelledError)):
            await asyncio.wait_for(asyncio.shield(task), 2)
        authority.settle_run("learning-run")
    finally:
        released.set()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize("reference", ["missing", "unknown", "other-run", "primary-overlay"])
async def test_continuation_requires_confirmed_same_run_transport_reference(configured, reference):
    _, authority, route, _ = configured
    calls = []
    client = gateway(configured, lambda request: calls.append(request) or httpx.Response(200,
        headers={"content-type": "text/event-stream"}, content=b"data: [DONE]\n\n"))
    first = await dispatch(client, route)
    authority.begin_run("other-run", "explain", capability_scope=("library-read",))
    with pytest.raises(ApiError):
        await dispatch(client, route, step_id="next-step",
            run_id="other-run" if reference == "other-run" else "learning-run",
            request_kind="primary" if reference == "primary-overlay" else "tool-continuation",
            continuation_of=None if reference == "missing" else "unknown" if reference == "unknown"
                else first["permit_id"])
    assert len(calls) == 1 and authority.run("learning-run")["spent_dispatches"] == 1
    assert authority.run("other-run")["spent_dispatches"] == 0


async def test_failed_sse_uses_machine_code_without_returning_provider_prose(configured):
    manager, authority, route, credential = configured
    payload = b"data: " + json.dumps({"type": "response.failed", "response": {"error": {
        "code": "invalid_api_key", "message": credential}}}).encode() + b"\n\n"
    client = gateway(configured, lambda request: httpx.Response(200,
        headers={"content-type": "text/event-stream"}, content=payload))
    with pytest.raises(ApiError) as denied:
        await dispatch(client, route)
    assert denied.value.code == "authentication_required"
    if credential in str(denied.value):
        pytest.fail("Provider prose leaked through a machine failure", pytrace=False)
    with pytest.raises(ApiError):
        manager.require_harness_route(route)
    authority.settle_run("learning-run")


@pytest.mark.parametrize("change", [{"n": 2}, {"best_of": 2}, {"background": True},
    {"tools": [{"type": "web_search"}]}, {"service_tier": "priority"}])
async def test_serialized_controls_cannot_expand_the_one_request_budget(configured, change):
    _, authority, route, _ = configured
    calls = []
    client = gateway(configured, lambda request: calls.append(request) or httpx.Response(200,
        headers={"content-type": "text/event-stream"}, content=b"data: [DONE]\n\n"))
    with pytest.raises(ApiError):
        await dispatch(client, route, envelope(route, **change))
    assert not calls and authority.run("learning-run")["spent_dispatches"] == 0


@pytest.mark.parametrize("change", [{"max_request_bytes": 0}, {"max_request_bytes": True},
    {"max_response_bytes": 0}, {"max_response_bytes": 100_000_000}, {"timeout_seconds": 0},
    {"timeout_seconds": float("nan")}, {"timeout_seconds": float("inf")}])
def test_invalid_transport_bounds_cannot_create_an_unowned_request(change):
    with pytest.raises(ApiError):
        GatewayBounds(**{**dict(max_request_bytes=4096, max_response_bytes=4096, timeout_seconds=3), **change})


async def test_parent_guard_failure_does_not_expose_arbitrary_diagnostics(configured):
    _, authority, route, credential = configured

    def broken_guard():
        raise ApiError("synthetic_callback_error", credential)

    with pytest.raises(ApiError) as denied:
        await dispatch(gateway(configured, None, check_current=broken_guard), route)
    assert denied.value.code == "gateway_authority_unbound"
    if credential in str(denied.value):
        pytest.fail("Guard diagnostics leaked a credential", pytrace=False)
    assert authority.run("learning-run")["spent_dispatches"] == 0


@pytest.mark.parametrize("encoding", ["escaped", "split"])
async def test_credential_echo_is_refused_after_sse_decoding_and_across_frames(configured, encoding):
    _, authority, route, credential = configured
    if encoding == "escaped":
        text = "".join("\\u%04x" % ord(character) for character in credential)
        payload = ('data: {"choices":[{"delta":{"content":"' + text + '"}}]}\n\n').encode()
    else:
        payload = b"".join(b"data: " + json.dumps({"choices": [{"delta": {"content": part}}]}).encode()
            + b"\n\n" for part in (credential[:16], credential[16:]))
    with pytest.raises(ApiError) as denied:
        await dispatch(gateway(configured, lambda request: httpx.Response(200,
            headers={"content-type": "text/event-stream"}, content=payload)), route)
    assert denied.value.code == "gateway_credential_echo"
    authority.settle_run("learning-run")


@pytest.mark.parametrize("dependency", ["manager", "authority", "cancellation", "check_current", "http_transport"])
async def test_missing_real_binding_denies_before_admission(configured, dependency):
    manager, authority, route, _ = configured
    calls = []
    settings = dict(manager=manager, authority=authority, cancellation=DomainCancellation(),
        check_current=lambda: True, http_transport=httpx.MockTransport(lambda request: calls.append(request)),
        bounds=GatewayBounds(4096, 4096, 3))
    settings[dependency] = None
    with pytest.raises(ApiError):
        await dispatch(HarnessGateway(**settings), route)
    assert not calls and authority.run("learning-run")["spent_dispatches"] == 0


@pytest.mark.parametrize("reason", ["input", "window", "unknown-limits", "invalid-proof", "other-model",
    "epoch", "capability", "purpose", "connection"])
async def test_parent_proof_and_current_pinned_authority_are_required(configured, reason):
    manager, authority, route, _ = configured
    options = {}
    if reason == "input":
        options["input_tokens"] = 101
    elif reason == "window":
        options["limits"] = RouteLimits(input_tokens=100, output_tokens=32, window_tokens=131)
    elif reason == "unknown-limits":
        options["limits"] = RouteLimits()
    elif reason == "invalid-proof":
        options["input_tokens"] = True
    elif reason == "other-model":
        route = await manager.prepare_harness_route("deepseek-v4.1-flash")
    elif reason == "epoch":
        route = replace(route, credential_epoch=route.credential_epoch + 1)
    else:
        authority.revoke({"capability": "library-read", "purpose": "purpose:explain",
                          "connection": "connection:" + route.credential_ref}[reason])
    calls = []
    with pytest.raises(ApiError):
        await dispatch(gateway(configured, lambda request: calls.append(request)), route, **options)
    assert not calls and authority.run("learning-run")["spent_dispatches"] == 0


@pytest.mark.parametrize("changed", [False, True])
async def test_confirmed_step_is_not_resent_after_lost_acknowledgement(configured, changed):
    _, authority, route, _ = configured
    calls = []
    client = gateway(configured, lambda request: calls.append(request) or httpx.Response(200,
        headers={"content-type": "text/event-stream"}, content=b"data: [DONE]\n\n"))
    first = await dispatch(client, route)
    with pytest.raises(ApiError):
        await dispatch(client, route, envelope(route, temperature=0) if changed else None)
    assert len(calls) == 1 and authority.run("learning-run")["spent_dispatches"] == 1
    assert authority.permit(first["permit_id"])["state"] == "confirmed"


@pytest.mark.parametrize("revocation", ["configuration", "credential", "domain"])
async def test_final_revalidation_suppresses_a_late_response(configured, revocation):
    manager, authority, route, _ = configured
    cancellation = DomainCancellation()

    def serve(request):
        if revocation == "configuration":
            authority.revoke("library-read")
        elif revocation == "credential":
            manager.observe_harness_result(route, code="authentication_required")
        else:
            cancellation.cancel()
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=b"data: [DONE]\n\n")

    with pytest.raises((ApiError, DomainCancelled)):
        await dispatch(gateway(configured, serve, cancellation=cancellation), route)
    assert authority.run("learning-run")["spent_dispatches"] == 1
    authority.settle_run("learning-run")


async def test_total_deadline_cancels_idle_headers_without_replay(configured):
    _, authority, route, _ = configured
    finalized = asyncio.Event()
    calls = []

    async def serve(request):
        calls.append(request)
        try:
            await asyncio.Event().wait()
        finally:
            finalized.set()

    client = gateway(configured, serve, bounds=GatewayBounds(4096, 4096, 0.1))
    with pytest.raises(ApiError) as denied:
        await dispatch(client, route)
    assert denied.value.code == "gateway_timeout" and finalized.is_set()
    with pytest.raises(ApiError):
        await dispatch(client, route)
    assert len(calls) == 1
    authority.settle_run("learning-run")


async def test_chunked_sse_stops_at_byte_bound_and_closes_before_settlement(configured):
    _, authority, route, _ = configured
    consumed = []
    closed = False

    class OversizedStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            for chunk in [b"data: ", b"x" * 4096, b"never-consumed"]:
                consumed.append(len(chunk))
                yield chunk

        async def aclose(self):
            nonlocal closed
            closed = True

    with pytest.raises(ApiError) as denied:
        await dispatch(gateway(configured, lambda request: httpx.Response(200,
            headers={"content-type": "text/event-stream"}, stream=OversizedStream())), route)
    assert denied.value.code == "gateway_response_too_large" and closed
    assert consumed == [6, 4096]
    authority.settle_run("learning-run")


async def test_transport_exception_canary_never_enters_diagnostics(configured, caplog):
    _, authority, route, credential = configured

    def serve(request):
        raise RuntimeError(credential)

    with pytest.raises(ApiError) as denied:
        await dispatch(gateway(configured, serve), route)
    assert denied.value.code == "transport_unavailable" and denied.value.retryable is False
    if credential in str(denied.value) + caplog.text:
        pytest.fail("Transport credential entered diagnostics", pytrace=False)
    authority.settle_run("learning-run")


async def test_ambiguous_duplicate_json_does_not_reach_the_provider(configured):
    _, authority, route, _ = configured
    request = envelope(route)
    body = base64.b64decode(request["body_base64"])
    request["body_base64"] = base64.b64encode(body[:-1] + b',"model":"mimo-v2.6-pro"}').decode()
    calls = []
    with pytest.raises(ApiError):
        await dispatch(gateway(configured, lambda request: calls.append(request)), route, request)
    assert not calls and authority.run("learning-run")["spent_dispatches"] == 0


@pytest.mark.parametrize("body", ["oversized", "compressed"])
async def test_http_401_invalidates_access_without_reading_untrusted_error_body(configured, body):
    manager, authority, route, _ = configured
    headers = {"content-type": "application/json"}
    if body == "compressed":
        headers["content-encoding"] = "gzip"

    class ErrorBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"x" * 4097

    with pytest.raises(ApiError) as denied:
        await dispatch(gateway(configured, lambda request: httpx.Response(401,
            headers=headers, stream=ErrorBody())), route)
    assert denied.value.code == "authentication_required"
    with pytest.raises(ApiError):
        manager.require_harness_route(route)
    authority.settle_run("learning-run")


NATIVE_GATEWAY_PROBE = r"""
import { createInterface } from 'node:readline';
import { Effect } from 'effect';
import { HttpClientResponse } from 'effect/http';
import { LLMRequest, Message, Media, ToolDefinition, GenerationOptions } from '@opencode/ai';
import { createSubscriptionAdapter } from './src/provider-adapter.ts';
const lines = createInterface({ input: process.stdin });
const exchange = value => new Promise(resolve => {
  lines.once('line', line => resolve(JSON.parse(line)));
  process.stdout.write(JSON.stringify(value) + '\n');
});
const adapter = await createSubscriptionAdapter({ route: JSON.parse(process.env.RENULUS_TEST_ROUTE),
  sessionId: 'synthetic-session',
  validateImages: images => Effect.promise(async () => {
    const reply = await exchange({ kind: 'images', images });
    if (!reply.valid) throw new Error('Synthetic decoder refused images');
  }),
  dispatch: (_route, request) => Effect.promise(async () => {
    const result = await exchange({ kind: 'http', request: { method: request.method, url: request.url,
      headers: request.headers, body_base64: Buffer.from(request.body.body).toString('base64') } });
    return HttpClientResponse.fromWeb(request, new Response(Buffer.from(result.body_base64, 'base64'),
      { status: result.status, headers: result.headers }));
  }),
});
try {
  const png = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAAAAAA6fptVAAAACklEQVR4nGNgAAAAAgABSK+kcQAAAABJRU5ErkJggg==';
  const messages = [Message.user([Message.text('Explain synthetic dialysis'),
    Message.media(Media.base64(png, 'image/png'))])];
  const tools = [ToolDefinition.make({ name: 'library_passage', description: 'Synthetic eligible teaching',
    inputSchema: { type: 'object', properties: {} } })];
  const make = messages => new LLMRequest({ model: adapter.model, system: [], messages, tools,
    generation: new GenerationOptions({ maxTokens: 32 }) });
  const first = await Effect.runPromise(adapter.client.generate(make(messages)));
  if (first.toolCalls.length !== 1) throw new Error('Missing synthetic native tool call');
  const call = first.toolCalls[0];
  const second = await Effect.runPromise(adapter.client.generate(make([...messages, Message.assistant([call]),
    Message.make({ role: 'tool', content: [{ type: 'tool-result', id: call.id, name: call.name,
      result: { type: 'text', value: 'Synthetic eligible dialysis passage' } }] })])));
  process.stdout.write(JSON.stringify({ kind: 'finished', text: second.text }) + '\n');
} catch { process.stdout.write(JSON.stringify({ kind: 'failed' }) + '\n'); process.exitCode = 1; }
finally { await adapter.close(); lines.close(); }
"""


def native_response(route, continuation):
    if route.provider_id == "codex":
        if continuation:
            events = [
                {"type": "response.output_item.added", "item": {"type": "message", "id": "message"}},
                {"type": "response.output_text.delta", "item_id": "message", "delta": "Synthetic gateway answer"},
                {"type": "response.output_item.done", "item": {"type": "message", "id": "message",
                    "content": [{"type": "output_text", "text": "Synthetic gateway answer"}]}},
            ]
        else:
            item = {"type": "function_call", "id": "tool-item", "call_id": "native-call",
                    "name": "library_passage", "arguments": "{}"}
            events = [{"type": "response.output_item.added", "item": item},
                      {"type": "response.output_item.done", "item": item}]
        events.append({"type": "response.completed", "response": {"id": "response",
            "model": route.wire_model_id, "status": "completed"}})
        suffix = b""
    else:
        delta = {"content": "Synthetic gateway answer"} if continuation else {"tool_calls": [{
            "index": 0, "id": "native-call", "type": "function",
            "function": {"name": "library_passage", "arguments": "{}"}}]}
        events = [{"id": "response", "model": route.wire_model_id, "choices": [{"index": 0,
            "delta": delta, "finish_reason": None}]}, {"id": "response", "model": route.wire_model_id,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop" if continuation else "tool_calls"}]}]
        suffix = b"data: [DONE]\n\n"
    return b"".join(b"data: " + json.dumps(event).encode() + b"\n\n" for event in events) + suffix


@pytest.mark.parametrize("configured", ["codex", "opencode-go"], indirect=True)
async def test_pinned_native_tool_and_image_roundtrip_uses_actual_loopback_http(configured, tmp_path):
    _, authority, route, credential = configured
    received, server_errors = [], []

    async def serve(reader, writer):
        try:
            head = await reader.readuntil(b"\r\n\r\n")
            headers = dict(line.split(b": ", 1) for line in head.split(b"\r\n")[1:-2])
            body = await reader.readexactly(int(headers[b"Content-Length"]))
            if headers.get(b"authorization") != b"Bearer " + credential.encode():
                server_errors.append("protected-credential-missing")
            received.append((head.split(b"\r\n")[0], json.loads(body)))
            payload = native_response(route, len(received) > 1)
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nConnection: close\r\n"
                         + b"Content-Length: " + str(len(payload)).encode() + b"\r\n\r\n" + payload)
            await writer.drain()
        except Exception:
            server_errors.append("synthetic-server-failed")
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(serve, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]

    class LoopbackTransport(httpx.AsyncBaseTransport):
        def __init__(self):
            self.transport = httpx.AsyncHTTPTransport(retries=0)

        async def handle_async_request(self, request):
            assert str(request.url) == route.endpoint
            local = httpx.Request(request.method, f"http://127.0.0.1:{port}" + request.url.path,
                                  headers=request.headers, content=await request.aread())
            return await self.transport.handle_async_request(local)

        async def aclose(self):
            await self.transport.aclose()

    environment = {"SystemRoot": os.environ["SystemRoot"], "TEMP": str(tmp_path), "TMP": str(tmp_path),
                   "RENULUS_TEST_ROUTE": json.dumps(route.descriptor())}
    process = await asyncio.create_subprocess_exec(
        "C:/Renulus/scratch/ocf/tools/node-v26.4.0-win-x64/node.exe", "--input-type=module", "-e",
        NATIVE_GATEWAY_PROBE, cwd=Path(__file__).resolve().parents[2] / "packages" / "harness",
        env=environment, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE, creationflags=0x08000000)
    permit = None
    validations = 0
    try:
        while True:
            line = await asyncio.wait_for(process.stdout.readline(), 30)
            assert line, "The pinned native probe ended without a terminal receipt"
            frame = json.loads(line)
            if frame["kind"] == "images":
                validate_harness_images(frame["images"])
                validations += 1
                result = {"valid": True}
            elif frame["kind"] == "http":
                client = gateway(configured, None, http_transport=LoopbackTransport())
                result = await dispatch(client, route, frame["request"],
                    step_id="native-next" if permit else "native-first",
                    request_kind="tool-continuation" if permit else "primary", continuation_of=permit)
                permit = result["permit_id"]
            else:
                assert frame == {"kind": "finished", "text": "Synthetic gateway answer"}
                break
            process.stdin.write(json.dumps(result).encode() + b"\n")
            await process.stdin.drain()
        assert await asyncio.wait_for(process.wait(), 5) == 0
        assert not server_errors and len(received) == validations == 2
        assert authority.run("learning-run")["spent_dispatches"] == 2
        assert all(body["model"] == route.wire_model_id for _, body in received)
        if route.provider_id == "codex":
            pair = [part for part in received[1][1]["input"] if part.get("type") in {"function_call", "function_call_output"}]
            assert pair[0]["call_id"] == pair[1]["call_id"] == "native-call"
        else:
            messages = received[1][1]["messages"]
            assert messages[1]["tool_calls"][0]["id"] == messages[2]["tool_call_id"] == "native-call"
    finally:
        if process.returncode is None:
            process.kill()
        await process.wait()
        server.close()
        await server.wait_closed()
