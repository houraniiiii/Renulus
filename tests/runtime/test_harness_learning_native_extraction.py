# SPDX-License-Identifier: MIT
"""Real saved answer and Mem0 extraction through production main/SDK/IPC.

The original Services ProviderManager is retained. Account discovery, immutable
inclusive count/limits evidence and the official-URL-to-loopback HTTP seam are
synthetic. CPU engines, native history, capture binding, permits and publication
are real. Automatic native capture stays disabled; capture is explicit.
Configuration activation is test-owned metadata assembly with an actual closed
native inspector, not a profile bootstrap coordinator acceptance test.
"""
import asyncio
from contextlib import asynccontextmanager
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import subprocess

import httpx
import pytest

from renulus.contracts import ApiError, ContextScope, Scope
from renulus.learn.conversation_models import NewConversation, Send
from renulus.memory.models import ManualFact
from renulus.runtime.harness_configuration import (
    AttemptPolicy, CandidateHealth, ConfigurationAuthority, ConfigurationSpec,
    ConnectionReference, ContextPolicy, RestartBoundary, RolePolicy, RouteLimits,
)
from renulus.runtime.harness_deployment import DeploymentEvidence
from renulus.runtime.harness_gateway import GatewayBounds
from renulus.runtime.harness_learning import HarnessLearningOwner
from renulus.runtime.harness_model_registry import ModelRegistryBounds
from renulus.runtime.harness_process import ManagedHarnessProcess
from renulus.server import create_app
from test_harness_learning_models import (
    ObservedRegistry, collect_events, command, inspect_candidate, process_config,
)
from test_harness_model_dispatch_sdk import ANSWER, LoopbackHttp, NODE, offline


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows native harness")
SOURCE = Path(__file__).resolve().parents[2]
HELPERS = Path(os.environ.get("RENULUS_MEMORY_HELPERS", "C:/Renulus/dev/helper-assets")).resolve()
CREDENTIAL = "synthetic_native_capture_python_only_5281"
PROMPT = "SYNTHETIC_NATIVE_H05_PROMPT: Explain CKD albuminuria and filtration."
ROOT_NOTE = "Synthetic CKD study preference: compare albuminuria with filtration."
POINT = "SYNTHETIC_NATIVE_H05_POINT: Albuminuria and filtration are complementary CKD study concepts."
CORRECTION = "Synthetic corrected CKD preference: review current teaching sources."
CAPABILITIES = ("text", "tools")
LIMITS = RouteLimits(input_tokens=7168, output_tokens=256, window_tokens=8192)
GATEWAY = GatewayBounds(max_request_bytes=65536, max_response_bytes=8192, timeout_seconds=20)
BOUNDS = ModelRegistryBounds(max_runs=1, max_plans_per_run=1, max_owned=1,
    max_retained_bytes=800000, max_manifest_bytes=65536, max_frame_bytes=131072)


class ObservedProcess(ManagedHarnessProcess):
    """Observe actual public IPC calls; delegate identity and execution unchanged."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.calls = []
        self.hold_answer_read = False
        self.read_entered, self.read_release = asyncio.Event(), asyncio.Event()

    async def request(self, command, payload, operation_id, attempt_id, timeout):
        observed = {"command": command, "payload": deepcopy(payload),
            "operation_id": operation_id, "attempt_id": attempt_id, "responses": []}
        self.calls.append(observed)
        response = await super().request(command, payload, operation_id, attempt_id, timeout)
        observed["responses"].append(deepcopy(response))
        if command == "session.messages" and self.hold_answer_read:
            self.read_entered.set()
            await self.read_release.wait()
        return response

    async def query_result(self, request_id):
        response = await super().query_result(request_id)
        if response is not None:
            for observed in self.calls:
                if observed["responses"] and observed["responses"][0]["request_id"] == request_id:
                    observed["responses"].append(deepcopy(response))
                    break
        return response


class InclusiveCounter:
    """Explicit synthetic evidence over real complete serialized requests."""
    def __init__(self):
        self.calls = []
        self.process = None
        self.entered, self.release = asyncio.Event(), asyncio.Event()
        self.finalizer_entered, self.finalizer_release = asyncio.Event(), asyncio.Event()
        self.finalized = asyncio.Event()
        self.finalizer_release.set()

    async def __call__(self, body, manifest):
        extracting = not manifest.tools
        self.calls.append((body, manifest, extracting))
        payload = json.loads(body)
        assert payload["model"] == "mimo-v2.6-pro" and payload["stream"] is True
        assert payload["max_completion_tokens"] == 256
        assert all(part.type == "text" for message in manifest.messages for part in message.content)
        if not extracting:
            assert {tool.name for tool in manifest.tools} == {
                "renulus_library_retrieve", "renulus_library_citation"}
            assert ROOT_NOTE in manifest.system
            assert any(part.text == PROMPT for message in manifest.messages for part in message.content)
            return 200
        try:
            invoked = [call for call in self.process.calls if call["command"] == "model.extract"]
            assert len(invoked) == 1
            exact = invoked[0]["payload"]
            assert manifest.system == exact["system"]
            assert len(manifest.messages) == 1 and manifest.messages[0].role == "user"
            assert len(manifest.messages[0].content) == 1
            assert manifest.messages[0].content[0].text == exact["user"]
            assert ANSWER in exact["user"] and PROMPT not in exact["user"]
            assert manifest.tools == ()
            self.entered.set()
            await self.release.wait()
            # This attestation covers system, complete user text, absent tools/
            # images and route framing. It is not a production tokenizer claim.
            return 220
        finally:
            self.finalizer_entered.set()
            await self.finalizer_release.wait()
            self.finalized.set()


class ExtractionHttp:
    """Owned real HTTP; only the external inference response is synthetic."""
    def __init__(self):
        self.calls, self.handlers = [], set()

    async def serve(self, reader, writer):
        task = asyncio.current_task()
        self.handlers.add(task)
        try:
            head = await reader.readuntil(b"\r\n\r\n")
            lines = head.decode("ascii").split("\r\n")
            headers = {key.lower(): value for key, value in
                (line.split(": ", 1) for line in lines[1:] if line)}
            body = await reader.readexactly(int(headers["content-length"]))
            extracting = not json.loads(body).get("tools")
            self.calls.append({"body": body, "extracting": extracting,
                "authenticated": headers.get("authorization") == "Bearer " + CREDENTIAL,
                "request_line": lines[0], "session_id": headers.get("x-opencode-session")})
            text = json.dumps({"memory": [{"text": POINT}]}) if extracting else ANSWER
            events = [
                {"id": "synthetic_native_capture_response", "model": "mimo-v2.6-pro",
                    "choices": [{"index": 0, "delta": {"content": text}, "finish_reason": None}]},
                {"id": "synthetic_native_capture_response", "model": "mimo-v2.6-pro",
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
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


@asynccontextmanager
async def native_memory(tmp_path):
    assert NODE.is_file() and (HELPERS / "manifest.json").is_file()
    root = tmp_path / "profile"
    root.mkdir(exist_ok=True)
    if not (root / "helpers").exists():
        link, target = str(root / "helpers").replace("'", "''"), str(HELPERS).replace("'", "''")
        subprocess.run(["powershell.exe", "-NoProfile", "-Command",
            f"New-Item -ItemType Junction -Path '{link}' -Target '{target}' | Out-Null"],
            check=True, creationflags=subprocess.CREATE_NO_WINDOW)
    services = create_app(root, source_root=SOURCE, provider_http_transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"data": [{"id": "mimo-v2.6-pro"}]}))).state.services
    manager, memory = services.get("provider"), services.get("memory")
    authority = ConfigurationAuthority(services.db)
    counter, observer = InclusiveCounter(), ExtractionHttp()
    registries, transports, admissions = [], [], []
    owner = server = None
    try:
        version = authority.status()["effective"]
        if version is None:
            await manager.connect_go(CREDENTIAL, select=True)
            manager.select("opencode-go", "mimo-v2.6-pro")
        route = await manager.prepare_harness_route()
        if version is None:
            inspection = await inspect_candidate(tmp_path / "candidate")
            spec = ConfigurationSpec(connection=ConnectionReference(provider=route.provider_id,
                credential_reference=route.credential_ref, credential_revision=route.credential_epoch,
                selected_model=route.catalog_model_id), registry_hash=inspection["registry_hash"],
                roles=tuple(RolePolicy(purpose=purpose, model_id=route.catalog_model_id,
                    output_tokens=256, dispatch_limit=1) for purpose in ("explain", "memory-extraction")),
                capabilities=CAPABILITIES, context=ContextPolicy(requested_window_tokens=8192, reserve_tokens=8),
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
        else:
            spec = authority.configuration(version)
            assert spec.connection.credential_reference == route.credential_ref
            assert spec.connection.credential_revision == route.credential_epoch
            assert authority.status()["admission_open"]
        server = await asyncio.start_server(observer.serve, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        evidence = DeploymentEvidence("synthetic_native_capture_account_v1", route, LIMITS, CAPABILITIES,
            "synthetic_immutable_limits_v1", "synthetic_capabilities_v1",
            "synthetic_system_user_tools_images_route_framing_count_v1", counter)

        def factory(resolve_run):
            def resolve(binding):
                admitted = resolve_run(binding)
                if admitted is not None:
                    assert resolve_run(binding) is admitted
                    admissions.append(admitted)
                return admitted

            def transport(actual):
                assert replace(actual, catalogue_listed=None) == replace(route, catalogue_listed=None)
                result = LoopbackHttp(actual, port)
                transports.append(result)
                return result

            result = ObservedRegistry(manager, authority, resolve_run=resolve, evidence=lambda _: evidence,
                http_transport=transport, gateway_bounds=GATEWAY, bounds=BOUNDS)
            registries.append(result)
            return result

        # Mem0 2.2.1's selected additive system prompt alone is 34,276 bytes.
        # Bound its complete manifest/body and base64 wire without truncation.
        config = replace(process_config(root, "synthetic-native-capture"), max_frame_bytes=131072,
            boot_settings={"ipc": {"max_inflight": 1, "max_domain_inflight": 1, "max_frame_bytes": 131072}})
        owner = HarnessLearningOwner(services, config,
            configuration_id=version, configuration_authority=authority, model_registry_factory=factory,
            memory=memory, context_filtering=True)
        original = owner.process
        assert (await original.settlement(0))["state"] == "settled"
        seal = owner.seal_new_runs(expected_effective=version)
        try:
            process = ObservedProcess(domain_authority=owner.authorize)
            owner.replace_process(process, configuration_id=version, seal=seal)
        finally:
            seal.release()
        counter.process = process
        owner.install()  # Production composition binds Memory's factory once.
        await owner.start()
        assert services.get("provider") is manager
        yield services, owner, memory, authority, registries[-1], transports, admissions, counter, observer
    finally:
        counter.release.set()
        counter.finalizer_release.set()
        if owner is not None:
            owner.process.read_release.set()
        await memory.close(timeout=30)
        if owner is not None:
            await asyncio.wait_for(owner.close(), 30)
            assert (await owner.process.settlement(10))["state"] == "settled"
            assert owner.process.domain_status()["active"] == 0
        for registry in registries:
            assert (await registry.close(10)).owned == 0
        if server is not None:
            server.close()
            await server.wait_closed()
        if observer.handlers:
            await asyncio.gather(*observer.handlers)
        assert all(transport.finalized.is_set() for transport in transports)
        await manager.close()
        services.get("helpers").startup.close()


async def saved_answer(services, owner, memory, authority):
    note = await asyncio.to_thread(memory.add, ManualFact(text=ROOT_NOTE,
        scope=ContextScope(kind=Scope.STUDY), idempotency_key="native-h05-root"))
    repo = services.get("conversations")
    chat = repo.create(NewConversation())
    entry, receipt = repo.streaming.begin("learning", chat["identity"]["id"],
        Send(expected_revision=chat["revision"], text=PROMPT, request_id="native-h05-saved-answer"))
    events = await collect_events(repo, entry, receipt)
    assert events[-1]["type"] == "completed", events
    await owner.settle_run(entry)
    reference = events[-1]["payload"]["answer_reference"]
    pin = {"kind": "memory", "dependency": {"target": {"type": "memory_revision",
        "id": f"{note['id']}:1"}, "expected_revision": "1"},
        "retention": "saved", "content_class": "general_learning"}
    assert reference["inputs"] == [pin] and reference["dependencies"] == [pin["dependency"]]
    assert reference["sha256"] == hashlib.sha256(ANSWER.encode()).hexdigest()
    assert reference["input_id"] not in reference["message_ids"]
    assert authority.run(reference["run_id"])["spent_dispatches"] == 1
    assert authority.run(reference["run_id"])["state"] == "settled"
    assert memory.repository.jobs() == []  # No automatic native capture.
    return note, reference


async def test_saved_answer_extracts_once_through_native_gateway_and_real_memory(tmp_path, offline):
    async with native_memory(tmp_path) as (services, owner, memory, authority, registry,
            transports, admissions, counter, observer):
        note, reference = await saved_answer(services, owner, memory, authority)
        assert len(observer.calls) == len(transports) == len(counter.calls) == 1
        assert observer.calls[0]["extracting"] is False
        page = await command(owner.process, "session.messages", {"session_id": reference["runtime"]["session_id"]})
        owner.process.hold_answer_read = True
        resolution = asyncio.create_task(owner.resolve_completed_answer(reference))
        try:
            await asyncio.wait_for(owner.process.read_entered.wait(), 10)
            with services.db.quiesce_writes():
                pass
            with services.db.transaction() as conn:
                conn.execute("SELECT 1")
            await command(owner.process, "host.status", operation="native-h05-writer-free")
            assert not resolution.done()
        finally:
            owner.process.hold_answer_read = False
            owner.process.read_release.set()
        resolved = await resolution
        assert resolved["text"] == ANSWER and resolved["digest"] == reference["sha256"]
        assert resolved["input"] == {"version": 1, "inputs": reference["inputs"],
            "dependencies": reference["dependencies"]}
        scope = ContextScope(kind=Scope.STUDY, entity_id=reference["thread_id"])
        evidence_id = "learn-answer:" + reference["run_id"]
        job = memory.enqueue(evidence_id, scope)
        capture = asyncio.create_task(memory.process_pending())
        entered = asyncio.create_task(counter.entered.wait())
        try:
            done, _ = await asyncio.wait((entered, capture), timeout=60, return_when=asyncio.FIRST_COMPLETED)
            assert entered in done and entered.result(), {
                "job": memory.repository.job(job["id"]), "registry": registry.status(),
                "callbacks": [request.command for request in registry.requests],
                "counter_calls": len(counter.calls), "capture_done": capture.done()}
            admitted = next(admission for admission in admissions if admission.purpose == "memory-extraction")
            binding = admitted.binding
            assert binding.operation_id == binding.cancellation_id != reference["run_id"]
            assert binding.attempt_id == "1" and admitted.required_capabilities == ("text",)
            assert binding.session_id != reference["runtime"]["session_id"]
            assert binding.input_id != reference["input_id"]
            canonical = authority.run(binding.operation_id)
            assert canonical["purpose"] == "memory-extraction" and canonical["dispatch_limit"] == 1
            assert canonical["effective_capabilities"] == ["text"] and canonical["spent_dispatches"] == 0
            assert registry.status(binding).owned == 1
            assert owner.process.domain_status(operation_id=binding.operation_id)["active"] == 1
            assert await command(owner.process, "model.extract.status", operation=binding.operation_id) == {"state": "active"}
            assert not (await command(owner.process, "host.status"))["activeSessionIds"]
            assert not capture.done() and len(observer.calls) == len(transports) == 1
        finally:
            entered.cancel()
            await asyncio.gather(entered, return_exceptions=True)
            counter.release.set()
        assert (await asyncio.wait_for(capture, 90))["processed"] >= 1
        assert memory.repository.job(job["id"])["state"] == "completed"
        found = await asyncio.to_thread(memory.retrieve, POINT, scope=scope)
        point = next(record for record in found["records"] if record["source_id"] == evidence_id)
        assert point["text"] == POINT and point["revision"] == 1
        assert point["sources"] == [{"source_key": "evidence:" + evidence_id}]
        assert memory.status()["producer"] == "mem0-oss" and memory.status()["index"]["ready"]
        assert memory.repository.get(note["id"])["revision"] == 1
        assert authority.run(binding.operation_id)["state"] == "settled"
        assert authority.run(binding.operation_id)["spent_dispatches"] == 1
        assert registry.status(binding).owned == registry.status(binding).runs == 0
        assert owner.process.domain_status(operation_id=binding.operation_id)["active"] == 0
        assert owner.memory_captures.retained() == 0
        released = next(status for known, status, _ in registry.releases if known == binding)
        assert len(released.receipts) == 1
        proof = released.receipts[0]
        assert proof.request_kind == "primary" and proof.continuation_of is None and proof.input_tokens == 220
        body, manifest, extracting = counter.calls[1]
        assert extracting and proof.body_sha256 == hashlib.sha256(body).hexdigest()
        assert proof.body_bytes == len(body)
        assert proof.input_manifest_sha256 == hashlib.sha256(manifest.model_dump_json().encode()).hexdigest()
        assert authority.permit(proof.permit_id)["state"] == "confirmed"
        publications = [status for known, status, supplied in registry.publications
            if known == binding and supplied]
        # Generation preflight and the canonical Memory insertion both require
        # the same consumed receipt through a supplied transaction connection.
        assert len(publications) >= 2
        assert all(status.receipts == released.receipts for status in publications)
        invocation = next(call for call in owner.process.calls if call["command"] == "model.extract")
        terminal = invocation["responses"][-1]
        assert terminal["outcome"] == "committed_reference"
        assert terminal["result"]["receipt"] == {"dispatch_id": proof.dispatch_id, "permit_id": proof.permit_id}
        assert json.loads(terminal["result"]["text"]) == {"memory": [{"text": POINT}]}
        assert [request.command for request in registry.requests if request.binding == binding] == [
            "model.prepare", "model.manifest", "model.dispatch"]
        assert len(observer.calls) == len(transports) == len(counter.calls) == 2
        assert [call["extracting"] for call in observer.calls] == [False, True]
        assert transports[1].sent == [body] and observer.calls[1]["body"] == body
        assert all(call["authenticated"] for call in observer.calls)
        assert all(call["request_line"] == "POST /zen/go/v1/chat/completions HTTP/1.1" for call in observer.calls)
        assert CREDENTIAL.encode() not in body
        public = json.dumps({"native": page, "callbacks": [request.payload for request in registry.requests],
            "extraction": terminal["result"]})
        assert CREDENTIAL not in public
        assert counter.finalized.is_set() and all(transport.finalized.is_set() for transport in transports)
        assert await command(owner.process, "session.find", operation=binding.operation_id) == {"sessions": []}
        assert await command(owner.process, "session.messages", {"session_id": reference["runtime"]["session_id"]}) == page
        assert await command(owner.process, "model.extract.status", operation=binding.operation_id) == {"state": "unavailable"}
        repeated = memory.enqueue(evidence_id, scope)
        assert repeated["id"] == job["id"] and repeated["attempts"] == 1
        await memory.process_pending(retry=True)
        assert len(observer.calls) == len(counter.calls) == 2


async def test_revoked_support_retains_native_cpu_and_counter_until_settlement_without_send(tmp_path, offline):
    async with native_memory(tmp_path) as (services, owner, memory, authority, registry,
            transports, admissions, counter, observer):
        note, reference = await saved_answer(services, owner, memory, authority)
        page = await command(owner.process, "session.messages", {"session_id": reference["runtime"]["session_id"]})
        scope = ContextScope(kind=Scope.STUDY, entity_id=reference["thread_id"])
        evidence_id = "learn-answer:" + reference["run_id"]
        job = memory.enqueue(evidence_id, scope)
        counter.finalizer_release.clear()
        capture = asyncio.create_task(memory.process_pending())
        entered = asyncio.create_task(counter.entered.wait())
        try:
            done, _ = await asyncio.wait((entered, capture), timeout=60, return_when=asyncio.FIRST_COMPLETED)
            assert entered in done and entered.result(), {
                "job": memory.repository.job(job["id"]), "registry": registry.status(),
                "callbacks": [request.command for request in registry.requests]}
            admitted = next(admission for admission in admissions if admission.purpose == "memory-extraction")
            binding = admitted.binding
            assert admitted.required_capabilities == ("text",)
            assert binding.operation_id == binding.cancellation_id != reference["run_id"]
            assert await command(owner.process, "model.extract.status", operation=binding.operation_id) == {"state": "active"}
            corrected = await asyncio.to_thread(memory.edit, note["id"], CORRECTION, 1)
            assert corrected["revision"] == 2 and not corrected["purge_pending"]
            retired = memory.repository.job(job["id"])
            assert retired["state"] == "cancelled" and retired["error_code"] == "memory_dependency_revoked"
            # Let counting return; its real async finalizer stays owned. The
            # subsequent authority check must refuse effect admission.
            counter.release.set()
            await asyncio.wait_for(counter.finalizer_entered.wait(), 10)
            assert not counter.finalized.is_set()
            assert registry.status(binding).owned == 1
            assert owner.process.domain_status(operation_id=binding.operation_id)["active"] == 1
            assert owner.memory_captures.retained() == 1
            assert authority.run(binding.operation_id)["state"] == "active"
            assert authority.run(binding.operation_id)["spent_dispatches"] == 0
            assert len(observer.calls) == len(transports) == 1  # Saved setup only.
            assert not any(call["extracting"] for call in observer.calls)
            assert POINT not in {record["text"] for record in memory.repository.list()}
            with pytest.raises(ApiError) as recovery:
                with memory.recovery_guard():
                    pass
            assert recovery.value.code == "recovery_busy"
            with pytest.raises(ApiError) as closing:
                await memory.close(timeout=.05)
            assert closing.value.code == "memory_close_timeout"
            assert not counter.finalized.is_set() and registry.status(binding).owned == 1
            assert authority.run(binding.operation_id)["state"] == "active"
            assert await command(owner.process, "model.extract.status", operation=binding.operation_id) == {"state": "active"}
            assert not (await command(owner.process, "host.status"))["activeSessionIds"]
            assert POINT not in {record["text"] for record in memory.repository.list()}
        finally:
            entered.cancel()
            await asyncio.gather(entered, return_exceptions=True)
            counter.release.set()
            counter.finalizer_release.set()
            await memory.close(timeout=30)
            await asyncio.gather(capture, return_exceptions=True)
        assert counter.finalized.is_set()
        assert registry.status(binding).owned == registry.status(binding).runs == 0
        assert owner.process.domain_status(operation_id=binding.operation_id)["active"] == 0
        assert owner.memory_captures.retained() == 0
        canonical = authority.run(binding.operation_id)
        assert canonical["state"] == "settled" and canonical["spent_dispatches"] == 0
        released = next(status for known, status, _ in registry.releases if known == binding)
        assert released.receipts == () and released.owned == 0
        assert memory.repository.job(job["id"])["state"] == "cancelled"
        assert POINT not in {record["text"] for record in memory.repository.list()}
        assert len(observer.calls) == len(transports) == 1 and len(counter.calls) == 2
        assert await command(owner.process, "session.find", operation=binding.operation_id) == {"sessions": []}
        assert await command(owner.process, "model.extract.status", operation=binding.operation_id) == {"state": "unavailable"}
        assert await command(owner.process, "session.messages", {"session_id": reference["runtime"]["session_id"]}) == page

    # The same real native and canonical stores reopen. No source bytes or old
    # support may be republished by enqueue/retry, and reading history is allowed.
    async with native_memory(tmp_path) as (services, owner, memory, authority, registry,
            transports, admissions, counter, observer):
        history = await owner.bridge.messages(reference["thread_id"])
        selected = [item for item in history["items"] if item["id"] in reference["message_ids"]]
        assert "".join(item["content"] for item in selected) == ANSWER
        with pytest.raises(ApiError) as unavailable:
            await owner.resolve_completed_answer(reference)
        assert unavailable.value.code == "memory_answer_unavailable"
        with pytest.raises(ApiError) as refused:
            memory.enqueue(evidence_id, scope)
        assert refused.value.code == "memory_capture_suppressed"
        await memory.process_pending(retry=True)
        recalled = await asyncio.to_thread(memory.retrieve, "CKD learning", scope=scope)
        assert POINT not in recalled["context"]
        assert next(record for record in recalled["records"] if record["id"] == note["id"])["revision"] == 2
        assert memory.repository.job(job["id"])["state"] == "cancelled"
        assert not counter.calls and not observer.calls and not transports
        assert not any(call["command"] == "model.extract" for call in owner.process.calls)
