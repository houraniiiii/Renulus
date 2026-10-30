"""BF01 synthetic-only broker proof; no doctor profile or external HTTP."""
from __future__ import annotations

import asyncio
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Event, Thread
import time
from types import SimpleNamespace
from uuid import uuid4

import httpx
from pydantic import ValidationError
import pytest

from renulus.runtime.manager import ProviderManager
from renulus.runtime.policy import ALLOWED_MODELS
from renulus.runtime.provider_adapter import subscription_route
from renulus.worker_contracts import Identity, OutputGrant, ProcessIdentity, Revisions, payload_digest
from renulus.workers.broker import BrokerRefused, ProtectedBroker
from renulus.workers.broker_models import (BrokerBounds, BrokerLaunch, CredentialAuthority, NativeHeader, NativeRequest,
    TransportPlan, TransportRoute)

SECRET = "SYNTHETIC_BF01_CREDENTIAL_SENTINEL_7c19"
DONE = b'data: {"choices":[{"delta":{"content":"Synthetic dialysis"}}]}\n\ndata: [DONE]\n\n'
REVISIONS = Revisions(configuration=2, grant=3, context=4, deletion=5, cancellation=6)
ENDPOINT = "http://127.0.0.1:9/chat/completions"


def credential_authority(fixture, action, provider="opencode-go"):
    return CredentialAuthority(authority_id="authority_" + uuid4().hex, source="settings",
        action=action, provider_id=provider, identity=Identity(**fixture.launch.identity.model_dump(),
            operation_id="settings", attempt_id="settings", request_id="settings_" + uuid4().hex),
        revisions=fixture.launch.revisions, retention=fixture.launch.retention,
        credential_ref=fixture.manager._credential_refs[provider],
        credential_revision=fixture.manager._credential_epochs[provider],
        expires_at_ms=int(time.time() * 1000) + 60000)


class Chunks(httpx.AsyncByteStream):
    def __init__(self, *chunks):
        self.chunks = chunks or (DONE,)
        self.closed = False

    async def __aiter__(self):
        for chunk in self.chunks:
            yield chunk

    async def aclose(self):
        self.closed = True


def response(body=DONE, *, status=200, headers=None, stream=None):
    return httpx.Response(status, headers={"content-type": "text/event-stream", **(headers or {})},
                          stream=stream if stream is not None else Chunks(body))


@pytest.fixture
def synthetic(tmp_path):
    """Only this explicit synthetic launch can inject an HTTP transport.

    Windows DPAPI encrypts the isolated account fixture using the production
    ConnectionStore entropy/namespace. No AppPaths.create/Database/Services or
    personal profile discovery is involved.
    """
    def make(handler=None, *, endpoint=ENDPOINT, provider="opencode-go", bounds=None):
        root = tmp_path / ("profile_" + uuid4().hex)
        state = root / "state"
        manager = ProviderManager(SimpleNamespace(root=root, state=state))
        manager._settings["connections"] = {provider: {"access_token": SECRET}}
        if provider == "codex":
            manager._settings["connections"][provider].update(expires_at=time.time() + 3600,
                refresh_token="SYNTHETIC_REFRESH_SENTINEL", client_id="synthetic-client")
        manager._settings["selected_provider"] = provider
        manager._settings["selected_models"] = {provider: ALLOWED_MODELS[provider][0]}
        manager._credential_epochs[provider] = 8
        manager._save()
        identity = ProcessIdentity(profile_id="profile_synthetic", domain_store_id="domain_synthetic",
            runtime_store_id="runtime_synthetic", authority_epoch=7, process_generation="pg_" + uuid4().hex)
        launch = BrokerLaunch(identity=identity, revisions=REVISIONS, retention="temporary",
            profile_root=str(root), state_root=str(state), native_manifest_sha256="a" * 64,
            registry_sha256="b" * 64, bounds=bounds or BrokerBounds(timeout_seconds=3),
            synthetic_endpoints=(endpoint,))
        calls = []
        def serve(request):
            # Store no credential-bearing Request/headers, even in test state.
            calls.append((str(request.url), request.content,
                          request.headers.get("authorization") == "Bearer " + SECRET))
            return handler(request) if handler else response(headers={
                "authorization": SECRET, "set-cookie": SECRET, "x-untrusted": SECRET})
        broker = ProtectedBroker(launch, manager=manager,
            synthetic_transport=httpx.MockTransport(serve))
        return SimpleNamespace(broker=broker, launch=launch, manager=manager, calls=calls, root=root,
                               provider=provider, endpoint=endpoint)
    return make


def plan(fixture, *, body=None, headers=None, endpoint=None, permit=None):
    model = ALLOWED_MODELS[fixture.provider][0]
    codex = fixture.provider == "codex"
    if body is None:
        # Deliberate native whitespace/order: the broker must not reserialize.
        body = ('{ "stream": true, "model": "' + model + '", "' +
            ("max_output_tokens" if codex else "max_completion_tokens") + '": 32, "' +
            ("input" if codex else "messages") + '": [] }').encode()
    safe_headers = headers if headers is not None else {"content-type": "application/json",
        "accept-encoding": "identity", "accept": "text/event-stream", "user-agent": "Renulus/0.1.0"}
    endpoint = endpoint or fixture.endpoint
    envelope = {"method": "POST", "url": endpoint, "headers": safe_headers,
                "body_base64": base64.b64encode(body).decode()}
    return TransportPlan(permit_id=permit or uuid4().hex, admission_receipt="receipt_" + uuid4().hex,
        identity=Identity(**fixture.launch.identity.model_dump(), operation_id="op_synthetic",
            attempt_id="attempt_synthetic", request_id="req_" + uuid4().hex),
        revisions=REVISIONS, retention="temporary",
        route=TransportRoute(provider_id=fixture.provider, model_id=model, wire_model_id=model,
            endpoint=endpoint, protocol="openai-responses" if codex else "openai-chat",
            credential_ref=fixture.manager._credential_refs[fixture.provider], credential_revision=8),
        native_manifest_sha256="a" * 64, registry_sha256="b" * 64,
        request_sha256=hashlib.sha256(body).hexdigest(), request_bytes=len(body),
        envelope_sha256=payload_digest(envelope), max_output_tokens=32,
        expires_at_ms=int(time.time() * 1000) + 60000,
        output=OutputGrant(artifact_handle="output_" + uuid4().hex, artifact_revision=1, max_bytes=4096,
            expires_at_ms=int(time.time() * 1000) + 60000, reservation_id="reserved", intent_id="intent"),
        serialized_request=NativeRequest(method="POST", url=endpoint,
            headers=tuple(NativeHeader(name=k, value=v) for k, v in safe_headers.items()),
            body_base64=envelope["body_base64"]))


def assert_private(execution, caplog=None, capsys=None):
    exposed = execution.result.model_dump_json() + repr(execution)
    if caplog:
        exposed += caplog.text
    if capsys:
        captured = capsys.readouterr()
        exposed += captured.out + captured.err
    assert SECRET not in exposed
    assert base64.b64encode(SECRET.encode()).decode() not in exposed
    assert "authorization" not in execution.result.model_dump_json().lower()


async def test_exact_native_bytes_one_permit_and_protected_refs_only(synthetic, caplog, capsys):
    fixture = synthetic()
    request = plan(fixture)
    result = await fixture.broker.execute(request, check_current=lambda: True)
    assert result.result.outcome == "committed_reference"
    assert result.result.effect == "response_received"
    assert result.body == DONE
    assert fixture.calls == [(fixture.endpoint, base64.b64decode(request.serialized_request.body_base64), True)]
    artifact = result.result.artifact
    assert artifact.artifact_handle == request.output.artifact_handle
    assert artifact.bytes == len(DONE) and artifact.artifact_sha256 == hashlib.sha256(DONE).hexdigest()
    assert_private(result, caplog, capsys)
    assert SECRET.encode() not in fixture.manager.store.path.read_bytes()
    metadata = fixture.broker.credential_metadata().model_dump_json()
    assert SECRET not in metadata and "access_token" not in metadata and "refresh_token" not in metadata
    again = await fixture.broker.execute(request, check_current=lambda: True)
    assert again.result.code == "transport_permit_replayed" and len(fixture.calls) == 1


async def test_real_http_loopback_uses_exact_explicit_launch_allowlist(synthetic, monkeypatch):
    received = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            received.append((self.path, self.rfile.read(int(self.headers["content-length"])),
                             self.headers.get("authorization") == "Bearer " + SECRET))
            self.send_response(200)
            self.send_header("content-type", "text/event-stream")
            self.send_header("content-length", str(len(DONE)))
            self.send_header("authorization", SECRET)
            self.end_headers()
            self.wfile.write(DONE)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        endpoint = f"http://127.0.0.1:{server.server_port}/chat/completions"
        fixture = synthetic(endpoint=endpoint)
        broker = ProtectedBroker(fixture.launch, manager=fixture.manager)
        monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
        monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
        monkeypatch.setenv("ALL_PROXY", "http://127.0.0.1:1")
        monkeypatch.setenv("OPENAI_API_KEY", "AMBIENT_FORBIDDEN")
        request = plan(fixture)
        execution = await broker.execute(request, check_current=lambda: True)
        assert execution.result.outcome == "committed_reference" and execution.body == DONE
        assert received == [("/chat/completions", base64.b64decode(request.serialized_request.body_base64), True)]
        assert_private(execution)
    finally:
        await asyncio.to_thread(server.shutdown)
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.parametrize("endpoint", ["http://localhost:9/chat/completions",
    "http://127.0.0.2:9/chat/completions", "http://127.0.0.1:9/chat/completions?q=secret",
    "http://127.0.0.1:9/chat/completions#secret", "https://127.0.0.1:9/chat/completions",
    "http://user:password@127.0.0.1:9/chat/completions", "http://127.0.0.1:9/other"])
def test_synthetic_launch_cannot_allow_arbitrary_endpoints(tmp_path, endpoint):
    launch = BrokerLaunch(identity=ProcessIdentity(profile_id="p", domain_store_id="d", runtime_store_id="r",
        authority_epoch=1, process_generation=uuid4().hex), revisions=REVISIONS, retention="temporary",
        profile_root=str(tmp_path), state_root=str(tmp_path / "state"), native_manifest_sha256="a" * 64,
        registry_sha256="b" * 64, synthetic_endpoints=(endpoint,))
    with pytest.raises(BrokerRefused, match="broker_launch_invalid"):
        ProtectedBroker(launch)


@pytest.mark.parametrize("provider,model", [(p, m) for p, models in ALLOWED_MODELS.items() for m in models])
def test_product_validator_accepts_only_exact_five_selected_routes_without_http(synthetic, provider, model):
    fixture = synthetic(provider=provider, endpoint=(
        "http://127.0.0.1:9/responses" if provider == "codex" else ENDPOINT))
    native = subscription_route(provider, model, credential_ref=fixture.manager._credential_refs[provider],
                                 credential_epoch=8, catalogue=None)
    launch = fixture.launch.model_copy(update={"synthetic_endpoints": ()})
    broker = ProtectedBroker(launch, manager=fixture.manager)
    request = plan(fixture, endpoint=native.endpoint)
    body = base64.b64decode(request.serialized_request.body_base64).replace(
        ALLOWED_MODELS[provider][0].encode(), model.encode())
    request = plan(fixture, endpoint=native.endpoint, body=body)
    request = request.model_copy(update={"route": request.route.model_copy(update={"model_id": model,
                                                                                "wire_model_id": model})})
    assert broker._validate(request)[0] == body
    assert fixture.calls == []


def test_lazy_activation_immutable_models_and_stub_refused_in_product(synthetic, monkeypatch):
    fixture = synthetic()
    request = plan(fixture)
    with pytest.raises(ValidationError):
        request.route.model_id = "unapproved"
    with pytest.raises(ValidationError):
        request.serialized_request.headers[0].value = "malicious"
    assert SECRET not in repr(request)
    dumped = request.model_dump(mode="json")
    dumped["token"] = SECRET
    with pytest.raises(ValidationError):
        TransportPlan.model_validate_json(json.dumps(dumped))
    monkeypatch.setattr(ProviderManager, "__init__", lambda *args, **kwargs: pytest.fail("Unexpected profile read"))
    broker = ProtectedBroker(fixture.launch)
    assert broker.manager is None
    with pytest.raises(BrokerRefused, match="broker_launch_invalid"):
        ProtectedBroker(fixture.launch.model_copy(update={"synthetic_endpoints": ()}),
                        synthetic_transport=httpx.MockTransport(lambda request: response()))


@pytest.mark.parametrize("mutate,code", [
    (lambda p: p.model_copy(update={"native_manifest_sha256": "c" * 64}), "transport_binding_mismatch"),
    (lambda p: p.model_copy(update={"registry_sha256": "c" * 64}), "transport_binding_mismatch"),
    (lambda p: p.model_copy(update={"request_sha256": "c" * 64}), "transport_digest_mismatch"),
    (lambda p: p.model_copy(update={"envelope_sha256": "c" * 64}), "transport_digest_mismatch"),
    (lambda p: p.model_copy(update={"request_bytes": p.request_bytes + 1}), "transport_digest_mismatch"),
    (lambda p: p.model_copy(update={"retention": "saved"}), "transport_binding_mismatch"),
    (lambda p: p.model_copy(update={"identity": p.identity.model_copy(update={"process_generation": "stale"})}), "transport_binding_mismatch"),
    (lambda p: p.model_copy(update={"identity": p.identity.model_copy(update={"domain_store_id": "other"})}), "transport_binding_mismatch"),
    (lambda p: p.model_copy(update={"identity": p.identity.model_copy(update={"runtime_store_id": "other"})}), "transport_binding_mismatch"),
    (lambda p: p.model_copy(update={"identity": p.identity.model_copy(update={"authority_epoch": 0})}), "transport_binding_mismatch"),
    (lambda p: p.model_copy(update={"route": p.route.model_copy(update={"credential_revision": 7})}), "credential_changed"),
    (lambda p: p.model_copy(update={"route": p.route.model_copy(update={"credential_ref": "other"})}), "credential_changed"),
    (lambda p: p.model_copy(update={"route": p.route.model_copy(update={"wire_model_id": "other"})}), "transport_route_invalid"),
    (lambda p: p.model_copy(update={"route": p.route.model_copy(update={"model_id": "other"})}), "transport_route_invalid"),
    (lambda p: p.model_copy(update={"expires_at_ms": 0}), "transport_expired"),
    (lambda p: p.model_copy(update={"revisions": p.revisions.model_copy(update={"grant": 0})}), "stale_revision"),
])
async def test_host_bindings_refuse_before_any_http(synthetic, mutate, code):
    fixture = synthetic()
    execution = await fixture.broker.execute(mutate(plan(fixture)), check_current=lambda: True)
    assert execution.result.outcome == "rejected_before_admission"
    assert execution.result.code == code and execution.result.effect == "not_sent"
    assert fixture.calls == []


@pytest.mark.parametrize("headers", [
    {"content-type": "application/json", "authorization": SECRET},
    {"content-type": "application/json", "x-api-key": SECRET},
    {"content-type": "application/json", "cookie": SECRET},
    {"content-type": "application/json", "host": "other"},
    {"content-type": "application/json", "x-opencode-session": "invalid\r\nheader"},
    {"content-type": "application/json", "content-length": "1"},
    {"content-type": "application/json", "accept-encoding": "gzip"},
])
async def test_model_supplied_headers_and_auth_never_reach_transport(synthetic, headers):
    fixture = synthetic()
    execution = await fixture.broker.execute(plan(fixture, headers=headers), check_current=lambda: True)
    assert execution.result.code == "gateway_invalid_request" and fixture.calls == []
    assert_private(execution)


@pytest.mark.parametrize("body", [
    b'{"model":"mimo-v2.6-pro","model":"mimo-v2.6-pro","stream":true,"max_completion_tokens":32}',
    b'{"model":"mimo-v2.6-pro","stream":true,"max_completion_tokens":32,"temperature":NaN}',
    b'{"model":"mimo-v2.6-pro","stream":true,"max_completion_tokens":32,"temperature":1e999}',
    b'{"model":"mimo-v2.6-pro","stream":true,"max_completion_tokens":32,"headers":{}}',
    b'{"model":"mimo-v2.6-pro","stream":true,"max_completion_tokens":32,"previous_response_id":"x"}',
    b'{"model":"mimo-v2.6-pro","stream":true,"max_completion_tokens":33}',
    b'{"model":"mimo-v2.6-pro","stream":true,"max_completion_tokens":true}',
    b'{"model":"mimo-v2.6-pro","stream":false,"max_completion_tokens":32}',
    b'{"model":"mimo-v2.6-pro","stream":true,"max_completion_tokens":32,"tools":[{"type":"web_search"}]}',
    b'{"model":"mimo-v2.6-pro","stream":true,"max_completion_tokens":32,"fallback":"other"}',
    b'[]', b'\xff',
])
async def test_exact_json_validation_rejects_unsafe_wire(synthetic, body):
    fixture = synthetic()
    execution = await fixture.broker.execute(plan(fixture, body=body), check_current=lambda: True)
    assert execution.result.code == "gateway_invalid_request" and fixture.calls == []


async def test_current_guard_required_and_rechecked_immediately_before_send(synthetic):
    fixture = synthetic()
    execution = await fixture.broker.execute(plan(fixture), check_current=None)
    assert execution.result.code == "broker_authority_unbound" and not fixture.calls
    checks = 0
    def current():
        nonlocal checks
        checks += 1
        return checks < 2
    execution = await fixture.broker.execute(plan(fixture), check_current=current)
    assert execution.result.effect == "not_sent" and checks >= 2 and fixture.calls == []


@pytest.mark.parametrize("kind", ["raw", "base64", "escaped", "split-delta", "split-choice", "error"])
async def test_credential_echo_sse_suppresses_entire_artifact(synthetic, kind, caplog, capsys):
    if kind == "base64":
        payload = ('data: ' + json.dumps({"delta": base64.b64encode(SECRET.encode()).decode()}) + '\n\n').encode()
    elif kind == "escaped":
        payload = ('data: {"delta":"' + ''.join('\\u%04x' % ord(c) for c in SECRET) + '"}\n\n').encode()
    elif kind in ("split-delta", "split-choice"):
        pieces = (SECRET[:15], SECRET[15:])
        values = ({"delta": piece} if kind == "split-delta" else
            {"choices": [{"delta": {"content": piece}}]} for piece in pieces)
        payload = ''.join('data: ' + json.dumps(value) + '\n\n' for value in values).encode()
    elif kind == "error":
        payload = ('data: ' + json.dumps({"error": {"message": SECRET}}) + '\n\n').encode()
    else:
        payload = ('data: ' + json.dumps({"delta": SECRET}) + '\n\n').encode()
    fixture = synthetic(lambda request: response(stream=Chunks(payload[:9], payload[9:])))
    execution = await fixture.broker.execute(plan(fixture), check_current=lambda: True)
    assert execution.body == b"" and execution.result.artifact is None
    assert execution.result.outcome == "uncertain_after_disconnect" and len(fixture.calls) == 1
    assert_private(execution, caplog, capsys)


async def test_expired_codex_does_not_implicitly_refresh(synthetic, monkeypatch):
    fixture = synthetic(provider="codex", endpoint="http://127.0.0.1:9/responses")
    fixture.manager._settings["connections"]["codex"]["expires_at"] = 0
    async def forbidden(*args, **kwargs):
        pytest.fail("Implicit refresh/credential accessor invoked")
    monkeypatch.setattr(fixture.manager, "_access_token", forbidden)
    monkeypatch.setattr(fixture.manager, "credential_for_harness", forbidden)
    execution = await fixture.broker.execute(plan(fixture), check_current=lambda: True)
    assert execution.result.code == "authentication_required" and fixture.calls == []


async def test_http_redirect_and_auth_errors_never_read_or_return_sensitive_headers(synthetic):
    for status in (302, 401, 429, 500):
        fixture = synthetic(lambda request: response(SECRET.encode(), status=status,
            headers={"location": "https://other.invalid/?token=" + SECRET, "authorization": SECRET}))
        execution = await fixture.broker.execute(plan(fixture), check_current=lambda: True)
        assert execution.body == b"" and execution.result.artifact is None and len(fixture.calls) == 1
        assert execution.result.effect in {"uncertain", "response_received"}
        assert_private(execution)


async def test_response_reservation_and_encoding_bounds(synthetic):
    for headers, body in [({}, b"x" * 4097), ({"content-encoding": "gzip"}, DONE),
                          ({"content-type": "application/json"}, DONE), ({}, b"data: invalid\n\n")]:
        fixture = synthetic(lambda request: response(body, headers=headers))
        execution = await fixture.broker.execute(plan(fixture), check_current=lambda: True)
        assert execution.result.artifact is None and execution.body == b""
        assert len(fixture.calls) == 1


class Blocked(Chunks):
    def __init__(self):
        super().__init__()
        self.entered = asyncio.Event()
        self.closing = asyncio.Event()
        self.finish_close = asyncio.Event()
    async def __aiter__(self):
        self.entered.set()
        await asyncio.Future()
        yield b"unreachable"
    async def aclose(self):
        self.closing.set()
        await self.finish_close.wait()
        self.closed = True


@pytest.mark.parametrize("stop", ["event", "caller", "revoke", "scope-close", "credential-revision"])
async def test_cancel_revoke_retains_lease_until_actual_http_cleanup(synthetic, stop):
    stream = Blocked()
    fixture = synthetic(lambda request: response(stream=stream))
    request = plan(fixture)
    cancelled = Event()
    task = asyncio.create_task(fixture.broker.execute(request, check_current=lambda: True, cancel=cancelled))
    await asyncio.wait_for(stream.entered.wait(), 2)
    if stop == "event":
        cancelled.set()
        assert fixture.broker.cancel(request.permit_id) is True
    elif stop == "caller":
        task.cancel()
    elif stop == "revoke":
        fixture.broker.revoke(REVISIONS.model_copy(update={"grant": 4}))
    elif stop == "scope-close":
        fixture.broker.close()
    else:
        fixture.manager._credential_epochs[fixture.provider] += 1
    await asyncio.wait_for(stream.closing.wait(), 2)
    assert not task.done() and fixture.broker.query(request.permit_id) is None
    task.cancel()
    task.cancel()  # Repeated Stop/caller cancellation cannot abandon finalizers.
    await asyncio.sleep(0.04)
    assert not task.done() and not stream.closed
    stream.finish_close.set()
    execution = await asyncio.wait_for(task, 2)
    assert stream.closed and execution.result.settlement == "settled"
    assert execution.result.effect == "uncertain" and execution.body == b""
    assert fixture.broker.query(request.permit_id) == execution.result
    replay = await fixture.broker.execute(request, check_current=lambda: True)
    assert replay.result.code == "transport_permit_replayed" and len(fixture.calls) == 1


async def test_timeout_retains_uncertainty_and_permit_across_scope_reopen(synthetic):
    stream = Blocked()
    fixture = synthetic(lambda request: response(stream=stream), bounds=BrokerBounds(timeout_seconds=1))
    request = plan(fixture)
    task = asyncio.create_task(fixture.broker.execute(request, check_current=lambda: True))
    await asyncio.wait_for(stream.entered.wait(), 2)
    await asyncio.wait_for(stream.closing.wait(), 2)
    assert not task.done()
    stream.finish_close.set()
    execution = await task
    assert execution.result.outcome == "uncertain_after_disconnect"
    assert execution.result.code == "transport_timeout" and execution.result.effect == "uncertain"
    fixture.broker.close()
    reopened = ProtectedBroker(fixture.launch, manager=fixture.manager,
        synthetic_transport=httpx.MockTransport(lambda request: pytest.fail("Resent uncertain request")))
    execution = await reopened.execute(request, check_current=lambda: True)
    assert execution.result.code == "transport_permit_replayed" and len(fixture.calls) == 1


async def test_network_exception_redacted_and_not_retried(synthetic, caplog, capsys):
    def fail(request):
        raise httpx.ConnectError(SECRET, request=request)
    fixture = synthetic(fail)
    request = plan(fixture)
    execution = await fixture.broker.execute(request, check_current=lambda: True)
    assert execution.result.outcome == "uncertain_after_disconnect"
    assert execution.result.code == "transport_failed" and len(fixture.calls) == 1
    assert_private(execution, caplog, capsys)


async def test_return_guard_suppresses_late_success(synthetic):
    current = True
    class Late(Chunks):
        async def aclose(self):
            nonlocal current
            current = False
            await super().aclose()
    fixture = synthetic(lambda request: response(stream=Late()))
    execution = await fixture.broker.execute(plan(fixture), check_current=lambda: current)
    assert execution.result.artifact is None and execution.body == b"" and len(fixture.calls) == 1


async def test_operation_bound_manifest_scopes_share_process_permit_tombstones(synthetic):
    fixture = synthetic()
    request = plan(fixture)
    first = await fixture.broker.execute(request, check_current=lambda: True)
    assert first.result.outcome == "committed_reference"
    scope = ProtectedBroker(fixture.launch.model_copy(update={"native_manifest_sha256": "d" * 64}),
        manager=fixture.manager, synthetic_transport=httpx.MockTransport(lambda request: response()))
    duplicate = request.model_copy(update={"native_manifest_sha256": "d" * 64})
    assert (await scope.execute(duplicate, check_current=lambda: True)).result.code == "transport_permit_replayed"
    fresh = plan(fixture).model_copy(update={"native_manifest_sha256": "d" * 64})
    assert (await scope.execute(fresh, check_current=lambda: True)).result.outcome == "committed_reference"


async def test_no_tombstone_eviction_and_monotonic_revoke(synthetic):
    fixture = synthetic(bounds=BrokerBounds(timeout_seconds=2, permit_count=1))
    original = plan(fixture)
    assert (await fixture.broker.execute(original, check_current=lambda: True)).result.network_started
    assert (await fixture.broker.execute(plan(fixture), check_current=lambda: True)).result.code == "transport_capacity"
    assert (await fixture.broker.execute(original, check_current=lambda: True)).result.code == "transport_permit_replayed"
    with pytest.raises(BrokerRefused, match="stale_revision"):
        fixture.broker.revoke(REVISIONS.model_copy(update={"grant": 2}))
    assert len(fixture.calls) == 1


async def test_sync_adapter_runs_on_worker_thread(synthetic):
    fixture = synthetic()
    execution = await asyncio.to_thread(fixture.broker.execute_sync, plan(fixture), check_current=lambda: True)
    assert execution.result.outcome == "committed_reference"
    with pytest.raises(BrokerRefused, match="broker_sync_in_async_loop"):
        fixture.broker.execute_sync(plan(fixture), check_current=lambda: True)


async def test_direct_credential_commands_preserve_namespace_refs_and_other_selection(synthetic, monkeypatch):
    fixture = synthetic()
    manager = fixture.manager
    manager._settings["selected_provider"] = "codex"
    manager._settings["selected_models"]["codex"] = "gpt-6-astra"
    original_ref = manager._credential_refs["opencode-go"]
    original_path, original_entropy = manager.store.path, manager.store.entropy
    async def catalog(provider, token):
        assert token == SECRET
        return set(ALLOWED_MODELS[provider])
    monkeypatch.setattr(manager, "_fetch_catalog", catalog)
    for action in ("connect", "refresh", "forget"):
        result = await fixture.broker.credential_command(action, "opencode-go", check_current=lambda: True,
            authority=credential_authority(fixture, action),
            secret_reader=(lambda: SECRET) if action == "connect" else None)
        assert SECRET not in result.model_dump_json()
        assert manager._credential_refs["opencode-go"] == original_ref
        assert manager._settings["selected_provider"] == "codex"
        assert manager._settings["selected_models"]["codex"] == "gpt-6-astra"
        assert (manager.store.path, manager.store.entropy) == (original_path, original_entropy)
    reopened = ProviderManager(SimpleNamespace(root=fixture.root, state=fixture.root / "state"))
    assert reopened._credential_refs["opencode-go"] == original_ref
    assert reopened._credential_epochs["opencode-go"] > 8
    assert reopened._settings["selected_provider"] == "codex"
    assert SECRET.encode() not in manager.store.path.read_bytes()


async def test_direct_credential_command_guard_and_failure_are_redacted(synthetic, monkeypatch):
    fixture = synthetic()
    with pytest.raises(BrokerRefused, match="broker_authority_unbound"):
        await fixture.broker.credential_command("refresh", "opencode-go", check_current=lambda: False,
            authority=credential_authority(fixture, "refresh"))
    async def fail(*args, **kwargs):
        raise RuntimeError(SECRET)
    monkeypatch.setattr(fixture.manager, "refresh", fail)
    with pytest.raises(BrokerRefused) as denied:
        await fixture.broker.credential_command("refresh", "opencode-go", check_current=lambda: True,
            authority=credential_authority(fixture, "refresh"))
    assert SECRET not in str(denied.value) and denied.value.code == "credential_command_failed"


async def test_explicit_activation_and_no_account_never_probe_or_fallback(synthetic):
    fixture = synthetic()
    empty_root = fixture.root / "empty_owned_profile"
    launch = fixture.launch.model_copy(update={"profile_root": str(empty_root),
        "state_root": str(empty_root / "state"),
        "identity": fixture.launch.identity.model_copy(update={"process_generation": "pg_" + uuid4().hex})})
    broker = ProtectedBroker(launch, synthetic_transport=httpx.MockTransport(
        lambda request: pytest.fail("No-account path attempted HTTP")))
    request = plan(fixture).model_copy(update={"identity": Identity(**launch.identity.model_dump(),
        operation_id="op", attempt_id="attempt", request_id="request")})
    assert (await broker.execute(request, check_current=lambda: True)).result.code == "broker_not_activated"
    assert broker.manager is None and not empty_root.exists()
    with pytest.raises(BrokerRefused, match="broker_authority_unbound"):
        broker.activate_credentials(check_current=lambda: False)
    manager = broker.activate_credentials(check_current=lambda: True)
    assert manager._settings["selected_provider"] is None
    request = plan(fixture).model_copy(update={"identity": request.identity,
        "route": request.route.model_copy(update={"credential_ref": manager._credential_refs[fixture.provider],
                                                  "credential_revision": 0})})
    execution = await broker.execute(request, check_current=lambda: True)
    assert execution.result.code == "authentication_required" and execution.result.effect == "not_sent"
    assert not empty_root.exists()
    assert not any(row.configured or row.usable or row.selected for row in broker.credential_metadata().credentials)
