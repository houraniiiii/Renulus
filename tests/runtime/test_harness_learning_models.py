"""Production saved learning over real IPC/SDK/HTTP; account evidence is synthetic.

Only ProviderManager account discovery, trusted inclusive count/evidence and the
external HTTP boundary are injected. Native model execution, deployment proof,
permits and canonical answer publication use their production public owners.
"""
import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
import hashlib
import inspect
import json
from pathlib import Path

import httpx
import pytest

from renulus.design_c_contracts import canonical_digest
from renulus.learn.conversation_models import NewConversation, Send
from renulus.runtime.harness_configuration import (
    AttemptPolicy, CandidateHealth, ConfigurationAuthority, ConfigurationSpec,
    ConnectionReference, ContextPolicy, RestartBoundary, RolePolicy, RouteLimits,
)
from renulus.runtime.harness_deployment import DeploymentEvidence
from renulus.runtime.harness_gateway import GatewayBounds
from renulus.runtime.harness_learning import HarnessLearningOwner
from renulus.runtime.harness_model_registry import HarnessModelRegistry, ModelRegistryBounds
from renulus.runtime.harness_process import HarnessProcessConfig, ManagedHarnessProcess
from renulus.runtime.manager import ProviderManager
from renulus.server import create_app
from test_harness_model_dispatch_sdk import ANSWER, HttpObserver, LoopbackHttp, NODE, offline


SOURCE = Path(__file__).resolve().parents[2]
MAIN = SOURCE / "packages/harness/src/main.mjs"
PROMPT = "Explain synthetic CKD learning: compare albuminuria and filtration."
CAPABILITIES = ("text", "tools")
LIMITS = RouteLimits(input_tokens=512, output_tokens=32, window_tokens=640)
GATEWAY = GatewayBounds(max_request_bytes=32768, max_response_bytes=8192, timeout_seconds=20)
BOUNDS = ModelRegistryBounds(max_runs=1, max_plans_per_run=1, max_owned=1,
    max_retained_bytes=300000, max_manifest_bytes=32768, max_frame_bytes=65536)


async def command(process, name, payload=None, *, operation="fixture-observation"):
    response = await process.request(name, payload or {}, operation, "1", 5)
    assert response["outcome"] == "committed_reference", response
    return response["result"]


def process_config(root, profile):
    return HarnessProcessConfig(node_executable=NODE, host_entry=MAIN, profile_root=root,
        profile_id=profile, store_id=profile + "-runtime", domain_store_id=profile + "-domain",
        domain_path="state/renulus.sqlite3", max_inflight=1, max_domain_inflight=1,
        max_frame_bytes=65536, start_timeout=40,
        boot_settings={"ipc": {"max_inflight": 1, "max_domain_inflight": 1,
            "max_frame_bytes": 65536}})


async def inspect_candidate(root):
    """Test-owned metadata assembly; no prompt or dispatch authority is supplied."""
    process = ManagedHarnessProcess()
    try:
        await process.start(process_config(root, "synthetic-registry-candidate"))
        inspection = await command(process, "host.inspect")
        assert {tool["name"] for tool in inspection["registry"]} == {
            "renulus_library_retrieve", "renulus_library_citation"}
        assert len(inspection["registry_hash"]) == 64
        return inspection
    finally:
        closed = await process.close(10)
        settled = await process.settlement(10)
        assert closed["state"] == "closed" and settled["state"] == "settled"
        assert process.domain_status()["active"] == 0


class InclusiveCounter:
    def __init__(self):
        self.entered, self.release, self.finalized = (asyncio.Event() for _ in range(3))
        self.finalizer_entered, self.finalizer_release = asyncio.Event(), asyncio.Event()
        self.finalizer_release.set()
        self.calls = []

    async def __call__(self, body, manifest):
        try:
            assert "nephrology education" in manifest.system
            assert {tool.name for tool in manifest.tools} == {
                "renulus_library_retrieve", "renulus_library_citation"}
            assert all(json.loads(tool.parameters_json)["type"] == "object" for tool in manifest.tools)
            assert any(part.type == "text" and part.text == PROMPT
                for message in manifest.messages for part in message.content)
            payload = json.loads(body)
            assert payload["model"] == "mimo-v2.6-pro"
            assert payload["stream"] is True and payload["max_completion_tokens"] == 32
            self.calls.append((body, manifest))
            self.entered.set()
            await self.release.wait()
            # Explicit synthetic attestation includes system, messages, ordinary
            # Library schemas and route/protocol framing. No tokenizer claim.
            return 200
        finally:
            self.finalizer_entered.set()
            await self.finalizer_release.wait()
            self.finalized.set()


class ObservedRegistry(HarnessModelRegistry):
    """Observe public commit/release boundaries, then delegate unchanged."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.publications, self.releases, self.requests = [], [], []

    async def authorize(self, request):
        self.requests.append(request)
        return await super().authorize(request)

    def require_publication(self, binding, *, conn):
        result = super().require_publication(binding, conn=conn)
        self.publications.append((binding, self.status(binding), conn is not None))
        return result

    def release(self, binding):
        self.releases.append((binding, self.status(binding), self.authority.run(binding.operation_id)))
        return super().release(binding)


@asynccontextmanager
async def learning_models(tmp_path):
    assert NODE.is_file(), "Pinned Node artifact is required; no install or substitute."
    services = create_app(tmp_path / "profile", source_root=SOURCE).state.services
    authority = ConfigurationAuthority(services.db)
    credential = "synthetic_learning_python_only_9386"
    manager = ProviderManager(services.paths, http_transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"data": [{"id": "mimo-v2.6-pro"}]})))
    services.registry["provider"] = manager
    counter = InclusiveCounter()
    observer = HttpObserver(credential)
    registries, transports, admissions = [], [], []
    owner = server = None
    try:
        # This explicit public API gap fails before starting any native process.
        # No dummy configuration, native identity or authority is fabricated.
        inspect.signature(HarnessLearningOwner).bind(services, process_config(services.paths.root,
            "synthetic-learning-models"), configuration_id=None, configuration_authority=authority,
            model_registry_factory=lambda resolve_run: None)
        await manager.connect_go(credential, select=True)
        manager.select("opencode-go", "mimo-v2.6-pro")
        route = await manager.prepare_harness_route()
        inspection = await inspect_candidate(tmp_path / "candidate")
        spec = ConfigurationSpec(connection=ConnectionReference(provider=route.provider_id,
            credential_reference=route.credential_ref, credential_revision=route.credential_epoch,
            selected_model=route.catalog_model_id), registry_hash=inspection["registry_hash"],
            roles=(RolePolicy(purpose="explain", model_id=route.catalog_model_id,
                output_tokens=32, dispatch_limit=1),), capabilities=CAPABILITIES,
            context=ContextPolicy(requested_window_tokens=640, reserve_tokens=8),
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
        server = await asyncio.start_server(observer.serve, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        evidence = DeploymentEvidence("synthetic_learning_account_v1", route, LIMITS, CAPABILITIES,
            "synthetic_immutable_limits_v1", "synthetic_capabilities_v1",
            "synthetic_system_messages_tools_route_framing_counter_v1", counter)

        def factory(resolve_run):
            def resolve(binding):
                admission = resolve_run(binding)
                if admission is not None:
                    assert resolve_run(binding) is admission  # Stable trusted closure/token.
                    admissions.append(admission)
                return admission

            def transport(actual):
                assert replace(actual, catalogue_listed=None) == replace(route, catalogue_listed=None)
                result = LoopbackHttp(actual, port)
                transports.append(result)
                return result

            result = ObservedRegistry(manager, authority, resolve_run=resolve,
                evidence=lambda actual: evidence, http_transport=transport,
                gateway_bounds=GATEWAY, bounds=BOUNDS)
            registries.append(result)
            return result

        owner = HarnessLearningOwner(services, process_config(services.paths.root,
            "synthetic-learning-models"), configuration_id=version, context_filtering=True,
            configuration_authority=authority, model_registry_factory=factory)
        owner.install()
        await owner.start()
        yield services, owner, authority, registries, transports, admissions, counter, observer
    finally:
        counter.release.set()
        counter.finalizer_release.set()
        observer.release.set()
        if owner is not None:
            await owner.close()
            assert (await owner.process.settlement(10))["state"] == "settled"
            assert owner.process.domain_status()["active"] == 0
        for registry in registries:
            assert (await registry.close(10)).owned == 0
        if server is not None:
            server.close()
            await server.wait_closed()
        if observer.handlers:
            await asyncio.gather(*observer.handlers)
        for transport in transports:
            assert transport.finalized.is_set()
        await manager.close()
        services.get("helpers").startup.close()


async def collect_events(repo, entry, receipt):
    async with asyncio.timeout(40):
        return [json.loads(encoded.split("data: ", 1)[1])
            async for encoded in repo.streaming.events(entry, receipt)]


async def test_production_saved_answer_has_one_proved_http_effect_and_actual_settlement(tmp_path, offline):
    async with learning_models(tmp_path) as (services, owner, authority, registries, transports,
            admissions, counter, observer):
        repo = services.get("conversations")
        chat = repo.create(NewConversation())
        request = Send(expected_revision=chat["revision"], text=PROMPT,
            request_id="synthetic-learning-model-proof")
        entry, receipt = repo.streaming.begin("learning", chat["identity"]["id"], request)
        run_id = entry["run"].id
        assert authority.run(run_id)["state"] == "active"
        pending = asyncio.create_task(collect_events(repo, entry, receipt))
        try:
            await asyncio.wait_for(counter.entered.wait(), 20)
            binding = admissions[-1].binding
            registry = registries[-1]
            assert binding.operation_id == binding.cancellation_id == run_id
            assert binding.attempt_id == "1"
            assert authority.run(run_id)["spent_dispatches"] == 0
            assert registry.status(binding).owned == 1 and not pending.done()
            assert owner.process.domain_status(operation_id=run_id)["active"] == 1
            live = await command(owner.process, "host.status", operation="held-counter-control")
            assert binding.session_id in live["activeSessionIds"]
            assert owner.bridge.completed(run_id) is None
            assert transports == [] and observer.calls == []
            counter.release.set()
            await asyncio.wait_for(observer.entered.wait(), 10)
            live = await command(owner.process, "host.status", operation="held-http-control")
            assert binding.session_id in live["activeSessionIds"] and not pending.done()
            assert authority.run(run_id)["spent_dispatches"] == 1
            assert registry.status(binding).owned == 1
            assert owner.process.domain_status(operation_id=run_id)["active"] == 1
            assert owner.bridge.completed(run_id) is None
        finally:
            counter.release.set()
            observer.release.set()
            await asyncio.gather(pending, return_exceptions=True)
        events = await pending
        assert events[-1]["type"] == "completed", events
        reference = events[-1]["payload"]["answer_reference"]
        saved = owner.bridge.completed(run_id)
        assert saved["publication_digest"] == canonical_digest(reference)
        assert {key: value for key, value in saved.items() if key != "publication_digest"} == reference
        assert reference["input_id"] == binding.input_id
        assert binding.input_id not in reference["message_ids"]
        assert reference["sha256"] == hashlib.sha256(ANSWER.encode()).hexdigest()
        assert reference["runtime"]["session_id"] == binding.session_id
        native = await command(owner.process, "session.get", {"session_id": binding.session_id})
        assert native["execution"] == "settled"
        page = await command(owner.process, "session.messages", {"session_id": binding.session_id})
        assert {binding.input_id, *reference["message_ids"]} <= {message["id"] for message in page["messages"]}
        assistants = [message for message in page["messages"] if message["id"] in reference["message_ids"]]
        assert assistants and all(message["model"]["providerID"] == "opencode-go"
            and message["model"]["id"] == "mimo-v2.6-pro" for message in assistants)
        assert owner.process.domain_status(operation_id=run_id)["active"] == 0
        assert registry.status(binding).owned == 0
        assert authority.run(run_id)["state"] == "settled"
        assert run_id not in repo.streaming.active
        assert registry.publications and all(current_conn for _, _, current_conn in registry.publications)
        assert [request.command for request in registry.requests] == [
            "model.prepare", "model.manifest", "model.dispatch"]
        assert registry.requests[0].payload == {}
        assert set(registry.requests[1].payload) == {"manifest"}
        assert set(registry.requests[2].payload) == {"dispatch_id", "serialized_request"}
        assert all(request.binding == binding for request in registry.requests)
        assert len(registry.releases) == 1
        released_binding, released, canonical = registry.releases[0]
        assert released_binding == binding and released.owned == 0 and canonical["state"] == "settled"
        assert len(released.receipts) == 1
        proof = released.receipts[0]
        assert proof.input_tokens == 200 and proof.request_kind == "primary" and proof.continuation_of is None
        body, manifest = counter.calls[0]
        assert proof.body_sha256 == hashlib.sha256(body).hexdigest() and proof.body_bytes == len(body)
        assert proof.input_manifest_sha256 == hashlib.sha256(manifest.model_dump_json().encode()).hexdigest()
        permit = authority.permit(proof.permit_id)
        assert permit["state"] == "confirmed" and permit["payload_hash"] == proof.body_sha256
        assert all(published_binding == binding and status.receipts == released.receipts
            for published_binding, status, _ in registry.publications)
        assert len(counter.calls) == len(transports) == len(observer.calls) == 1
        assert transports[0].sent == [body] and observer.calls[0]["body"] == body
        assert observer.calls[0]["authenticated"]
        assert observer.calls[0]["session_id"] == binding.session_id
        assert observer.calls[0]["request_line"] == "POST /zen/go/v1/chat/completions HTTP/1.1"
        assert b"synthetic_learning_python_only_9386" not in body
        public = json.dumps({"events": events, "native": native, "messages": page,
            "callbacks": [request.payload for request in registry.requests]})
        assert "synthetic_learning_python_only_9386" not in public
        assert counter.finalized.is_set() and transports[0].finalized.is_set()
        await asyncio.wait_for(observer.finalized.wait(), 5)
        assert not observer.handlers
        history = await owner.bridge.messages(chat["identity"]["id"])
        assert [item["role"] for item in history["items"]] == ["user", "assistant"]
        assert history["items"][1]["content"] == ANSWER
        replay_entry, replay_receipt = repo.streaming.begin("learning", chat["identity"]["id"], request)
        assert replay_entry is None
        replay = await collect_events(repo, replay_entry, replay_receipt)
        assert replay[-1]["payload"]["replayed"] is True
        assert len(counter.calls) == len(observer.calls) == 1
        assert authority.run(run_id)["spent_dispatches"] == 1


async def test_stop_retains_counter_finalizer_and_canonical_pin_without_http_or_publication(tmp_path, offline):
    async with learning_models(tmp_path) as (services, owner, authority, registries, transports,
            admissions, counter, observer):
        counter.finalizer_release.clear()
        repo = services.get("conversations")
        chat = repo.create(NewConversation())
        request = Send(expected_revision=chat["revision"], text=PROMPT,
            request_id="synthetic-learning-model-stop")
        entry, receipt = repo.streaming.begin("learning", chat["identity"]["id"], request)
        run_id = entry["run"].id
        pending = asyncio.create_task(collect_events(repo, entry, receipt))
        stop = None
        try:
            await asyncio.wait_for(counter.entered.wait(), 20)
            admission = admissions[-1]
            binding, registry = admission.binding, registries[-1]
            stop = asyncio.create_task(repo.streaming.cancel("learning", chat["identity"]["id"], run_id))
            async with asyncio.timeout(5):
                while not admission.cancellation.cancelled:
                    await asyncio.sleep(.01)
            counter.release.set()
            await asyncio.wait_for(counter.finalizer_entered.wait(), 5)
            assert not counter.finalized.is_set()
            assert registry.status(binding).owned == 1
            assert owner.process.domain_status(operation_id=run_id)["active"] == 1
            assert authority.run(run_id)["state"] == "active"
            assert authority.run(run_id)["spent_dispatches"] == 0
            assert owner.bridge.completed(run_id) is None
            assert registry.releases == [] and registry.publications == []
            assert observer.calls == [] and transports == []
            assert (await command(owner.process, "host.status", operation="held-finalizer-control"))["state"] == "ready"
            assert (await owner.settle_run(entry, timeout=0))["state"] == "pending"
            observation = asyncio.create_task(owner.settle_run(entry, timeout=5))
            await asyncio.sleep(0)
            observation.cancel()
            with pytest.raises(asyncio.CancelledError):
                await observation
            assert (await owner.settle_run(entry, timeout=0))["state"] == "pending"
            assert authority.run(run_id)["state"] == "active"
            assert registry.status(binding).owned == 1 and registry.releases == []
        finally:
            counter.release.set()
            counter.finalizer_release.set()
            observer.release.set()
            await asyncio.gather(pending, *([stop] if stop is not None else []), return_exceptions=True)
        events = await pending
        assert (await stop)["state"] == "cancelled"
        assert [event["type"] for event in events if event["type"] in {"completed", "error", "cancelled"}] == ["cancelled"]
        assert counter.finalized.is_set() and len(counter.calls) == 1
        assert observer.calls == [] and transports == []
        assert owner.bridge.completed(run_id) is None
        assert authority.run(run_id)["state"] == "settled"
        assert authority.run(run_id)["spent_dispatches"] == 0
        assert owner.process.domain_status(operation_id=run_id)["active"] == 0
        assert registry.status(binding).owned == 0
        assert registry.publications == [] and len(registry.releases) == 1
        _, released, canonical = registry.releases[0]
        assert released.owned == 0 and released.receipts == () and canonical["state"] == "settled"
        assert released.phases[0][2] == "cancelled"
        assert (await command(owner.process, "session.get", {"session_id": binding.session_id}))["execution"] == "settled"
        assert run_id not in repo.streaming.active
        history = await owner.bridge.messages(chat["identity"]["id"])
        assert [message["role"] for message in history["items"]] == ["user"]
        replay_entry, replay_receipt = repo.streaming.begin("learning", chat["identity"]["id"], request)
        assert replay_entry is None
        replay = await collect_events(repo, replay_entry, replay_receipt)
        assert replay[-1]["type"] == "error" and replay[-1]["payload"]["replayed"]
        assert len(counter.calls) == 1 and observer.calls == []
        assert authority.run(run_id)["spent_dispatches"] == 0
