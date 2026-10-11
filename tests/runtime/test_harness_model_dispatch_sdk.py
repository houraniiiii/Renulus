"""Actual SDK/private IPC and owned HTTP; account/limits/counts are synthetic.

Trusted public hooks register actual native input and manifest. The HTTP boundary
alone remaps an exact approved subscription URL to an owned loopback socket.
"""
import asyncio
from contextlib import asynccontextmanager
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import socket

import httpx
import pytest

from renulus.contracts import ApiError
from renulus.runtime.harness_activation import HarnessProfileActivation
from renulus.runtime.harness_configuration import (
    AttemptPolicy, CandidateHealth, ConfigurationAuthority, ConfigurationSpec,
    ConnectionReference, ContextPolicy, RestartBoundary, RolePolicy, RouteLimits,
)
from renulus.runtime.harness_deployment import (
    DeploymentBinding, DeploymentEvidence, HarnessDeployment, NativeManifest,
)
from renulus.runtime.harness_domain import DomainCancellation, DomainGrant
from renulus.runtime.harness_gateway import GatewayBounds, HarnessGateway
from renulus.runtime.harness_process import HarnessProcessConfig, ManagedHarnessProcess
from renulus.runtime.manager import ProviderManager
from renulus.runtime.provider_adapter import validate_harness_images
from renulus.storage import AppPaths
from renulus.storage.database import Database


SOURCE = Path(__file__).resolve().parents[2]
HOST = SOURCE / "packages/harness/test/fixtures/model-dispatch-host.mjs"
NODE = Path(os.environ.get("RENULUS_HARNESS_NODE",
    "C:/Renulus/scratch/ocf/tools/node-v26.4.0-win-x64/node.exe")).resolve()
PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAAAAAA6fptVAAAACklEQVR4nGNgAAAAAgABSK+kcQAAAABJRU5ErkJggg=="
PNG_SHA = "eaa4a94ea300e0d2c775968cbe42f0b5b51ceafdeb73d64e9efddf6d4e880865"
IMAGE = {"type": "image", "media_type": "image/png", "data": PNG}
SYSTEM = "SYNTHETIC_TRUSTED_SYSTEM: Compare albuminuria and filtration for CKD learning."
PROMPT = "SYNTHETIC_NATIVE_INPUT: Explain this educational one-pixel CKD diagram."
ANSWER = "SYNTHETIC_SDK_HTTP_ANSWER: Albuminuria and filtration are complementary teaching concepts."
HISTORY = "Earlier synthetic CKD prompt"
TOOL_RESULT = '{"status":"ready","passages":[]}'
RUN, ATTEMPT = "synthetic_model_run", "synthetic_attempt"
CAPABILITIES = ("text", "tools", "image")
BOUNDS = GatewayBounds(max_request_bytes=32768, max_response_bytes=8192, timeout_seconds=20)
LIMITS = RouteLimits(input_tokens=220, output_tokens=32, window_tokens=256)


@pytest.fixture
def offline(monkeypatch):
    connect = socket.socket.connect

    def loopback_only(sock, address):
        if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1", "localhost"):
            return connect(sock, address)
        raise AssertionError("SDK deployment fixture attempted external network access")

    monkeypatch.setattr(socket.socket, "connect", loopback_only)


class LoopbackHttp(httpx.AsyncBaseTransport):
    """Real HTTP at the injected external boundary; the official route stays pinned."""
    def __init__(self, route, port):
        self.route, self.port = route, port
        self.inner = httpx.AsyncHTTPTransport(retries=0)
        self.sent = []
        self.finalized = asyncio.Event()

    async def handle_async_request(self, request):
        assert request.method == "POST" and str(request.url) == self.route.endpoint
        self.sent.append(request.content)
        local = httpx.Request("POST", f"http://127.0.0.1:{self.port}{request.url.raw_path.decode()}",
            headers={key: value for key, value in request.headers.items() if key != "host"},
            content=request.content)
        return await self.inner.handle_async_request(local)

    async def aclose(self):
        try:
            await self.inner.aclose()
        finally:
            self.finalized.set()


class HttpObserver:
    def __init__(self, credential):
        self.credential = credential
        self.calls = []
        self.entered, self.release, self.finalized = asyncio.Event(), asyncio.Event(), asyncio.Event()
        self.handlers = set()

    async def serve(self, reader, writer):
        task = asyncio.current_task()
        self.handlers.add(task)
        try:
            head = await reader.readuntil(b"\r\n\r\n")
            lines = head.decode("ascii").split("\r\n")
            headers = dict(line.split(": ", 1) for line in lines[1:] if line)
            headers = {key.lower(): value for key, value in headers.items()}
            body = await reader.readexactly(int(headers["content-length"]))
            self.calls.append({"request_line": lines[0], "body": body,
                "authenticated": headers.get("authorization") == "Bearer " + self.credential,
                "session_id": headers.get("x-opencode-session")})
            self.entered.set()
            await self.release.wait()
            events = [
                {"id": "synthetic_response", "model": "mimo-v2.6-pro", "choices": [
                    {"index": 0, "delta": {"content": ANSWER}, "finish_reason": None}]},
                {"id": "synthetic_response", "model": "mimo-v2.6-pro", "choices": [
                    {"index": 0, "delta": {}, "finish_reason": "stop"}]},
            ]
            response = ("".join("data: " + json.dumps(event) + "\n\n" for event in events)
                        + "data: [DONE]\n\n").encode()
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n"
                + f"Content-Length: {len(response)}\r\nConnection: close\r\n\r\n".encode() + response)
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()
            self.handlers.discard(task)
            self.finalized.set()


class TrustedModelRegistry:
    """Test-owned parent registry: actual native identity and immutable ordered phases."""
    def __init__(self, manager, authority, route, version, transport):
        self.manager, self.authority, self.route, self.version = manager, authority, route, version
        self.transport = transport
        self.session_id = self.binding = self.preparation = self.manifest = self.proof = None
        self.phase = "awaiting_input"
        self.requests, self.counter_bodies = [], []
        self.counter_entered, self.counter_release, self.counter_finalized = (asyncio.Event() for _ in range(3))
        self.cancellation = DomainCancellation()
        self.evidence = DeploymentEvidence("synthetic_fixture_evidence", route, LIMITS, CAPABILITIES,
            "synthetic_immutable_limits_v1", "synthetic_account_capabilities_v1",
            "synthetic_framing_system_history_schema_result_image_v1", self.count)
        self.deployment = HarnessDeployment(resolve=self.resolve, evidence=lambda _: self.evidence,
            check_current=self.check_preparation, max_request_bytes=BOUNDS.max_request_bytes)

    def current(self, binding, *, admission=False):
        self.cancellation.check_current()
        if (binding.operation_id != RUN or binding.attempt_id != ATTEMPT
                or binding.session_id != self.session_id or binding.cancellation_id != RUN
                or not binding.input_id or not (admission or binding == self.binding)):
            raise ApiError("fixture_native_binding_unavailable", "Native authority is unavailable.", 409)
        self.manager.require_harness_route(self.route)
        self.authority.require_current(RUN, required_capabilities=CAPABILITIES,
            connection=ConnectionReference(provider=self.route.provider_id,
                credential_reference=self.route.credential_ref, credential_revision=self.route.credential_epoch))
        return True

    async def resolve(self, binding):
        self.current(binding)
        role = self.authority.resolve_role(self.version, "explain", operation_model=self.route.catalog_model_id)
        return DeploymentBinding(binding, RUN, role, self.route)

    def check_preparation(self, preparation):
        self.current(preparation.binding)  # Deployment's injected current guard returns None.

    async def count(self, body, manifest):
        try:
            assert SYSTEM in manifest.system and "nephrology education" in manifest.system
            assert tuple(sorted(tool.name for tool in manifest.tools)) == (
                "renulus_library_citation", "renulus_library_retrieve")
            assert all(json.loads(tool.parameters_json)["type"] == "object" for tool in manifest.tools)
            parts = [part.model_dump(mode="json") for message in manifest.messages for part in message.content]
            assert any(part == {"type": "image", "media_type": "image/png", "sha256": PNG_SHA,
                "bytes": 67, "detail": None} for part in parts)
            assert any(part.get("text") == PROMPT for part in parts)
            assert any(part.get("text") == HISTORY for part in parts)
            assert any(part.get("type") == "tool-call" and part["id"] == "fixture_call_1" for part in parts)
            assert any(part.get("type") == "tool-result" and part["id"] == "fixture_call_1"
                and part["output_text"] == TOOL_RESULT for part in parts)
            payload = json.loads(body)
            assert payload["model"] == self.route.wire_model_id and payload["max_completion_tokens"] == 32
            assert payload["stream"] is True and PNG.encode() in body
            self.counter_bodies.append((body, manifest))
            self.counter_entered.set()
            await self.counter_release.wait()
            # Synthetic inclusive attestation: system17 + history9 + input19 +
            # schemas38 + call11 + result13 + image64 + route/protocol framing29.
            # Every component is pinned above; no character estimate/tokenizer claim.
            return 200
        finally:
            self.counter_finalized.set()

    async def authorize(self, request):
        admission = request.command == "model.admit_input" and self.phase == "awaiting_input"
        if not admission and request.binding != self.binding:
            return None
        return DomainGrant(request.binding, self.handle,
            lambda: self.current(request.binding, admission=admission), self.cancellation)

    async def handle(self, request, cancellation):
        self.requests.append(request)
        if request.command == "model.admit_input":
            assert self.phase == "awaiting_input" and request.payload == {}
            self.binding, self.phase = request.binding, "admitted"
            return {"admitted": True}
        if request.command == "model.prepare":
            assert self.phase == "admitted" and request.payload == {}
            self.preparation = await self.deployment.prepare(request.binding, required_capabilities=CAPABILITIES)
            self.phase = "prepared"
            return {"dispatch_id": self.preparation.id, "binding": asdict(request.binding),
                "role": {"version": self.version, "purpose": "explain", "model_id": self.route.catalog_model_id,
                    "output_tokens": self.preparation.output_tokens, "dispatch_limit": 1},
                "request_kind": "primary", "route": self.route.descriptor(),
                "native_capabilities": {"tools": True, "input": ["text", "image"], "output": ["text"]},
                "limits": LIMITS.model_dump(), "required_capabilities": list(CAPABILITIES),
                "bounds": {"max_request_bytes": BOUNDS.max_request_bytes,
                    "max_response_bytes": BOUNDS.max_response_bytes, "max_frame_bytes": 65536}}
        if request.command == "model.manifest":
            assert self.phase == "prepared" and set(request.payload) == {"manifest"}
            self.manifest = NativeManifest.from_payload(request.payload["manifest"])
            self.phase = "manifest_registered"
            return {"registered": True}
        if request.command != "model.dispatch":
            raise ApiError("fixture_command_unavailable", "Command is unavailable.", 409)
        assert self.phase == "manifest_registered" and set(request.payload) == {"dispatch_id", "serialized_request"}
        assert request.payload["dispatch_id"] == self.preparation.id
        self.phase = "dispatch_owned"
        self.proof = await self.deployment.prove(self.preparation, step_id="fixture_primary_step",
            request_kind="primary", serialized_request=request.payload["serialized_request"], manifest=self.manifest)

        def final_guard():
            cancellation.check_current()
            self.deployment.require_current(self.proof, body=self.proof.body)
            return True

        gateway = HarnessGateway(self.manager, self.authority, cancellation=cancellation,
            check_current=final_guard, http_transport=self.transport, bounds=BOUNDS)
        result = await gateway.dispatch(RUN, self.proof.step_id, self.route, request.payload["serialized_request"],
            limits=self.preparation.limits, input_tokens=self.proof.input_tokens,
            required_capabilities=self.preparation.required_capabilities, request_kind=self.proof.request_kind)
        self.phase = "settled"
        return result


async def command(process, name, payload=None, *, operation=RUN, timeout=10):
    response = await process.request(name, payload or {}, operation, ATTEMPT, timeout)
    assert response["outcome"] == "committed_reference", response
    return response["result"]


@asynccontextmanager
async def deployment_fixture(tmp_path):
    assert NODE.is_file(), "Pinned Node artifact is a prerequisite; no install or substitute."
    paths = AppPaths.create(tmp_path / "profile", SOURCE)
    database = Database(paths.database)
    authority = ConfigurationAuthority(database)
    credential = "synthetic_python_only_credential_9137"
    manager = ProviderManager(paths, http_transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"data": [{"id": "mimo-v2.6-pro"}]})))
    await manager.connect_go(credential, select=True)
    manager.select("opencode-go", "mimo-v2.6-pro")
    route = await manager.prepare_harness_route()
    validate_harness_images([IMAGE])  # Actual public Pillow decode before native dispatch.
    observer = HttpObserver(credential)
    server = await asyncio.start_server(observer.serve, "127.0.0.1", 0)
    transport = LoopbackHttp(route, server.sockets[0].getsockname()[1])
    registry = None

    async def authorize(request):
        return await registry.authorize(request) if registry else None

    process = ManagedHarnessProcess(domain_authority=authorize)
    try:
        config = HarnessProcessConfig(node_executable=NODE, host_entry=HOST, profile_root=paths.root,
            profile_id="synthetic-model-profile", store_id="synthetic-model-runtime",
            domain_store_id="synthetic-model-domain", domain_path="state/renulus.sqlite3",
            max_inflight=1, max_domain_inflight=1, max_frame_bytes=65536, start_timeout=40,
            boot_settings={"synthetic_system": SYSTEM, "synthetic_png": PNG,
                "ipc": {"max_inflight": 1, "max_domain_inflight": 1, "max_frame_bytes": 65536}})
        await process.start(config)
        inspection = await command(process, "host.inspect")
        assert {tool["name"] for tool in inspection["registry"]} == {
            "renulus_library_retrieve", "renulus_library_citation"}
        spec = ConfigurationSpec(connection=ConnectionReference(provider=route.provider_id,
            credential_reference=route.credential_ref, credential_revision=route.credential_epoch,
            selected_model=route.catalog_model_id), registry_hash=inspection["registry_hash"],
            roles=(RolePolicy(purpose="explain", output_tokens=32, dispatch_limit=1),),
            capabilities=CAPABILITIES, context=ContextPolicy(requested_window_tokens=256, reserve_tokens=8),
            attempts=AttemptPolicy(foreground_dispatches=1, retries=0))
        version = authority.stage(spec)
        fields = ("registry_hash", "generation_open", "recovery_open", "package_acquisition_open",
                  "mcp_startup_open", "live_store_writer")
        assert authority.validate(version, lambda candidate: CandidateHealth(
            configuration_version=candidate.version, grant_epoch=candidate.grant_epoch,
            **{key: inspection[key] for key in fields}))
        authority.activate(version, RestartBoundary(admission_closed=True, runtime_stopped=True,
            domain_settled=True), expected_effective=None)
        authority.open_admission(version, registry_hash=spec.registry_hash, grant_epoch=0)
        authority.begin_run(RUN, "explain", capability_scope=CAPABILITIES)
        registry = TrustedModelRegistry(manager, authority, route, version, transport)
        assert (await HarnessProfileActivation(database, process, config).activate()).state == "active"
        await command(process, "host.activate", {"configuration_id": version})
        session = (await command(process, "session.create", {"title": "Synthetic SDK deployment proof"}))["session"]
        registry.session_id = session["id"]
        yield process, registry, observer, transport, authority, manager, version
    finally:
        if registry:
            registry.counter_release.set()
        observer.release.set()
        closed = await process.close(10)
        settled = await process.settlement(10)
        server.close()
        await server.wait_closed()
        if observer.handlers:
            await asyncio.gather(*observer.handlers)
        await transport.aclose()
        await manager.close()
        assert closed["state"] == "closed" and settled["state"] == "settled"
        assert process.domain_status()["active"] == 0


async def test_actual_sdk_authenticated_deployment_sends_once_with_exact_body_and_settles(tmp_path, offline):
    async with deployment_fixture(tmp_path) as (process, registry, observer, transport, authority, _, version):
        pending = asyncio.create_task(command(process, "session.prompt", {"session_id": registry.session_id,
            "text": PROMPT, "images": [IMAGE], "configuration_id": version}, timeout=40))
        try:
            await asyncio.wait_for(registry.counter_entered.wait(), 15)
            live = await command(process, "host.status", operation="counter_control")
            assert registry.session_id in live["activeSessionIds"] and not pending.done()
            assert live["waitingSubmit"] and live["domainCallbacks"]["active"] == 1
            assert process.domain_status()["active"] == 1
            assert authority.run(RUN)["spent_dispatches"] == 0 and not observer.calls
            registry.counter_release.set()
            await asyncio.wait_for(observer.entered.wait(), 10)
            live = await command(process, "host.status", operation="http_control")
            assert registry.session_id in live["activeSessionIds"] and not pending.done()
            assert live["waitingSubmit"] and live["domainCallbacks"]["active"] == 1
            assert process.domain_status()["active"] == 1
            assert authority.run(RUN)["spent_dispatches"] == 1
            observer.release.set()
            accepted = await pending
        finally:
            registry.counter_release.set()
            observer.release.set()
            if not pending.done():
                await pending
        observed = await command(process, "session.get", {"session_id": registry.session_id})
        messages = (await command(process, "session.messages", {"session_id": registry.session_id}))["messages"]
        assistant = next(message for message in reversed(messages) if message["type"] == "assistant")
        assert observed["execution"] == "settled" and observed["session"]["outcome"] == "succeeded"
        assert "".join(part["text"] for part in assistant["content"] if part["type"] == "text") == ANSWER
        assert assistant["model"]["providerID"] == "opencode-go" and assistant["model"]["id"] == "mimo-v2.6-pro"
        assert registry.binding.input_id == accepted["inputId"] and assistant["id"] != accepted["inputId"]
        assert [request.command for request in registry.requests] == [
            "model.admit_input", "model.prepare", "model.manifest", "model.dispatch"]
        assert all(request.binding == registry.binding for request in registry.requests)
        assert len(observer.calls) == len(transport.sent) == len(registry.counter_bodies) == 1
        raw_body = observer.calls[0]["body"]
        assert raw_body == transport.sent[0] == registry.counter_bodies[0][0] == registry.proof.body
        assert hashlib.sha256(raw_body).hexdigest() == registry.proof.body_sha256
        assert registry.proof.input_tokens == 200 and registry.proof.output_tokens == 32
        assert registry.proof.preparation.evidence is registry.evidence
        assert observer.calls[0]["authenticated"] and observer.calls[0]["session_id"] == registry.session_id
        assert observer.calls[0]["request_line"] == "POST /zen/go/v1/chat/completions HTTP/1.1"
        result = process.domain_result(registry.requests[-1].callback_id)
        permit = authority.permit(result["result"]["permit_id"])
        assert permit["state"] == "confirmed" and permit["payload_hash"] == registry.proof.body_sha256
        assert authority.run(RUN)["spent_dispatches"] == 1
        status = await command(process, "host.status")
        assert status["replayBlocked"] and status["nativePreparations"] == 1 and status["imageValidations"] == 1
        assert status["manifestRegistrations"] == status["nativeRequests"] == 1
        assert status["gatewayReceipt"] == {"dispatch_id": registry.preparation.id, "permit_id": permit["permit_id"]}
        assert registry.counter_finalized.is_set() and observer.finalized.is_set() and transport.finalized.is_set()
        assert process.domain_status()["active"] == 0
        safe = json.dumps({"messages": messages, "status": status, "result": result,
            "requests": [request.payload for request in registry.requests]})
        assert "synthetic_python_only_credential_9137" not in safe


async def test_actual_sdk_stale_credential_after_counter_await_cannot_send_or_replay(tmp_path, offline):
    async with deployment_fixture(tmp_path) as (process, registry, observer, transport, authority, manager, version):
        pending = asyncio.create_task(command(process, "session.prompt", {"session_id": registry.session_id,
            "text": PROMPT, "images": [IMAGE], "configuration_id": version}, timeout=40))
        try:
            await asyncio.wait_for(registry.counter_entered.wait(), 15)
            live = await command(process, "host.status", operation="revocation_control")
            assert live["waitingSubmit"] and live["domainCallbacks"]["active"] == 1 and not pending.done()
            # The actual public credential replacement invalidates the admitted
            # revision while counting is awaiting, before any durable HTTP permit.
            await manager.connect_go("synthetic_replacement_credential_9138", select=True)
            registry.counter_release.set()
            await pending
        finally:
            registry.counter_release.set()
            if not pending.done():
                await pending
        observed = await command(process, "session.get", {"session_id": registry.session_id})
        messages = (await command(process, "session.messages", {"session_id": registry.session_id}))["messages"]
        assert observed["execution"] == "settled" and observed["session"]["outcome"] == "failed"
        assert not any(part.get("text") == ANSWER for message in messages for part in message.get("content", []))
        assert [request.command for request in registry.requests] == [
            "model.admit_input", "model.prepare", "model.manifest", "model.dispatch"]
        result = process.domain_result(registry.requests[-1].callback_id)
        # DomainCallbacks conservatively reports an admitted handler ApiError as
        # uncertain; the real permit ledger and HTTP observer prove zero effects.
        assert result["outcome"] == "uncertain_after_disconnect", result
        assert result["error"] == {"code": "connection_changed", "status": 409, "retryable": True}
        assert "result" not in result and registry.proof is None
        assert authority.run(RUN)["spent_dispatches"] == 0 and not observer.calls and not transport.sent
        status = await command(process, "host.status")
        assert status["replayBlocked"] and status["gatewayReceipt"] is None
        assert status["nativeRequests"] == status["nativePreparations"] == status["manifestRegistrations"] == 1
        assert registry.counter_finalized.is_set() and process.domain_status()["active"] == 0
        assert len(registry.counter_bodies) == 1
        safe = json.dumps({"messages": messages, "status": status, "result": result,
            "requests": [request.payload for request in registry.requests]})
        assert "synthetic_python_only_credential_9137" not in safe
        assert "synthetic_replacement_credential_9138" not in safe
