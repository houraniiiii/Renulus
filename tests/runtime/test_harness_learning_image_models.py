"""Saved Explain image ingress starts at public Send before external ownership.

Connected native/HTTP verification uses synthetic account and immutable evidence;
the production saved owner, decoder, deployment and canonical permit stay real.
"""
import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
import hashlib
import json

import httpx

from renulus.design_c_contracts import canonical_digest
from renulus.learn.conversation_models import NewConversation, Send
from renulus.runtime.harness_configuration import (
    AttemptPolicy, CandidateHealth, ConfigurationAuthority, ConfigurationSpec,
    ConnectionReference, ContextPolicy, RestartBoundary, RolePolicy, RouteLimits,
)
from renulus.runtime.harness_deployment import DeploymentEvidence, NativeManifest
from renulus.runtime.harness_learning import HarnessLearningOwner
from renulus.runtime.manager import ProviderManager
from renulus.server import create_app
from test_harness_learning_models import (
    BOUNDS, GATEWAY, SOURCE, ObservedRegistry, collect_events, command, inspect_candidate, process_config,
)
from test_harness_model_dispatch_sdk import (
    ANSWER, IMAGE, PNG, PNG_SHA, HttpObserver, LoopbackHttp, NODE, offline,
)


PROMPT = "Explain this synthetic one-pixel PNG as a CKD learning illustration."
CAPABILITIES = ("text", "tools", "image")
LIMITS = RouteLimits(input_tokens=512, output_tokens=32, window_tokens=640)


class ImageCounter:
    def __init__(self):
        self.calls = []
        self.finalized = asyncio.Event()

    async def __call__(self, body, manifest):
        try:
            assert "nephrology education" in manifest.system
            assert {tool.name for tool in manifest.tools} == {
                "renulus_library_retrieve", "renulus_library_citation"}
            parts = [part for message in manifest.messages for part in message.content]
            assert any(part.type == "text" and part.text == PROMPT for part in parts)
            images = [part.model_dump(mode="json") for part in parts if part.type == "image"]
            assert images == [{"type": "image", "media_type": "image/png", "sha256": PNG_SHA,
                "bytes": 67, "detail": None}]
            payload = json.loads(body)
            assert payload["model"] == "mimo-v2.6-pro"
            assert payload["stream"] is True and payload["max_completion_tokens"] == 32
            wire_images = [part for message in payload["messages"]
                if isinstance(message.get("content"), list) for part in message["content"]
                if part.get("type") == "image_url"]
            assert len(wire_images) == 1
            assert wire_images[0]["image_url"]["url"] == "data:image/png;base64," + PNG
            assert wire_images[0]["image_url"].get("detail") is None
            self.calls.append((body, manifest))
            # Explicit synthetic inclusive evidence covers the exact image,
            # system/messages/Library schemas and route/protocol framing.
            return 200
        finally:
            self.finalized.set()


class ImageOwner(HarnessLearningOwner):
    """Observe real authenticated callbacks, including the actual managed decoder."""
    def __init__(self, *args, revoke_image=False, **kwargs):
        self.callbacks = []
        self.revoke_image = revoke_image
        self.revocations = []
        super().__init__(*args, **kwargs)

    async def authorize(self, request):
        self.callbacks.append(request)
        if self.revoke_image and request.command == "model.manifest":
            assert not self.revocations, "The native plan captures its manifest once."
            manifest = NativeManifest.model_validate(request.payload["manifest"])
            images = [part.model_dump(mode="json") for message in manifest.messages
                for part in message.content if part.type == "image"]
            assert images == [{"type": "image", "media_type": "image/png", "sha256": PNG_SHA,
                "bytes": 67, "detail": None}]
            self.revocations.append((request, self.configuration_authority.revoke("image")))
        return await super().authorize(request)


@asynccontextmanager
async def image_profile(tmp_path, *, revoke_image=False):
    assert NODE.is_file(), "The published pinned Node artifact is required."
    services = create_app(tmp_path / "profile", source_root=SOURCE).state.services
    authority = ConfigurationAuthority(services.db)
    credential = "synthetic_learning_image_python_only_4719"
    manager = ProviderManager(services.paths, http_transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"data": [{"id": "mimo-v2.6-pro"}]})))
    services.registry["provider"] = manager
    counter, observer = ImageCounter(), HttpObserver(credential)
    registries, transports, admissions = [], [], []
    owner = server = None
    try:
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
        evidence = DeploymentEvidence("synthetic_saved_image_account_v1", route, LIMITS, CAPABILITIES,
            "synthetic_image_limits_v1", "synthetic_image_capabilities_v1",
            "synthetic_image_system_tools_route_count_v1", counter)

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

            result = ObservedRegistry(manager, authority, resolve_run=resolve,
                evidence=lambda _: evidence, http_transport=transport, gateway_bounds=GATEWAY, bounds=BOUNDS)
            registries.append(result)
            return result

        owner = ImageOwner(services, process_config(services.paths.root, "synthetic-saved-image"),
            configuration_id=version, context_filtering=True, configuration_authority=authority,
            model_registry_factory=factory, revoke_image=revoke_image)
        owner.install()
        await owner.start()
        yield services, owner, authority, registries, transports, admissions, counter, observer
    finally:
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
        assert all(transport.finalized.is_set() for transport in transports)
        await manager.close()
        services.get("helpers").startup.close()


async def test_saved_explain_inline_png_is_proved_and_published_once(tmp_path, offline):
    request = Send(expected_revision=1, text=PROMPT,
        request_id="synthetic-saved-learning-image", images=(IMAGE,))
    assert request.model is None and request.image_preview_id is None and request.case_revision is None
    assert request.model_dump(mode="json")["images"] == [IMAGE]
    assert "images" not in Send(expected_revision=1, text=PROMPT,
        request_id="synthetic-text-without-image").model_dump(mode="json")
    async with image_profile(tmp_path) as (services, owner, authority, registries, transports,
            admissions, counter, observer):
        repo = services.get("conversations")
        chat = repo.create(NewConversation())
        request = request.model_copy(update={"expected_revision": chat["revision"]})
        entry, receipt = repo.streaming.begin("learning", chat["identity"]["id"], request)
        run_id = entry["run"].id
        assert entry["run"].scope.kind.value == "study"
        assert authority.run(run_id)["purpose"] == "explain"
        assert set(authority.run(run_id)["effective_capabilities"]) == set(CAPABILITIES)
        pending = asyncio.create_task(collect_events(repo, entry, receipt))
        try:
            await asyncio.wait_for(observer.entered.wait(), 20)
            binding, registry = admissions[-1].binding, registries[-1]
            assert set(admissions[-1].required_capabilities) == set(CAPABILITIES)
            assert authority.run(run_id)["spent_dispatches"] == 1
            assert owner.bridge.completed(run_id) is None
            assert binding.session_id in (await command(owner.process, "host.status"))["activeSessionIds"]
            decodes = [callback for callback in owner.callbacks if callback.command == "learning.validate_images"]
            assert len(decodes) == 1 and decodes[0].binding == binding
            assert decodes[0].payload == {"images": [IMAGE]}
            result = owner.process.domain_result(decodes[0].callback_id)
            assert result["outcome"] == "committed_reference" and result["result"] == {"validated": True}
        finally:
            observer.release.set()
            await asyncio.gather(pending, return_exceptions=True)
        events = await pending
        assert events[-1]["type"] == "completed", events
        reference = events[-1]["payload"]["answer_reference"]
        assert reference["input_id"] == binding.input_id
        assert reference["sha256"] == hashlib.sha256(ANSWER.encode()).hexdigest()
        saved = owner.bridge.completed(run_id)
        assert saved["publication_digest"] == canonical_digest(reference)
        assert {key: value for key, value in saved.items() if key != "publication_digest"} == reference
        assert (await command(owner.process, "session.get", {"session_id": binding.session_id}))["execution"] == "settled"
        page = await command(owner.process, "session.messages", {"session_id": binding.session_id})
        native_input = next(message for message in page["messages"] if message["id"] == binding.input_id)
        assert native_input["files"][0]["data"] == PNG and len(native_input["files"]) == 1
        assert native_input["files"][0]["source"] == {"type": "inline"}
        assistants = [message for message in page["messages"] if message["id"] in reference["message_ids"]]
        assert assistants and all(message["model"]["providerID"] == "opencode-go"
            and message["model"]["id"] == "mimo-v2.6-pro" for message in assistants)
        assert owner.process.domain_status(operation_id=run_id)["active"] == 0
        assert registry.status(binding).owned == 0 and authority.run(run_id)["state"] == "settled"
        assert len(registry.releases) == 1
        released = registry.releases[0][1]
        assert released.owned == 0 and len(released.receipts) == 1
        proof = released.receipts[0]
        body, manifest = counter.calls[0]
        assert proof.body_sha256 == hashlib.sha256(body).hexdigest() and proof.body_bytes == len(body)
        assert proof.input_manifest_sha256 == hashlib.sha256(manifest.model_dump_json().encode()).hexdigest()
        assert proof.input_tokens == 200 and proof.request_kind == "primary"
        permit = authority.permit(proof.permit_id)
        assert permit["state"] == "confirmed" and permit["payload_hash"] == proof.body_sha256
        assert registry.publications and all(status.receipts == released.receipts and supplied_conn
            for _, status, supplied_conn in registry.publications)
        assert len(counter.calls) == len(observer.calls) == len(transports) == 1
        assert observer.calls[0]["body"] == body and transports[0].sent == [body]
        assert observer.calls[0]["authenticated"] and observer.calls[0]["session_id"] == binding.session_id
        assert counter.finalized.is_set() and transports[0].finalized.is_set()
        await asyncio.wait_for(observer.finalized.wait(), 5)
        public = json.dumps({"callbacks": [callback.payload for callback in owner.callbacks],
            "events": events, "messages": page})
        assert "synthetic_learning_image_python_only_4719" not in public
        replay_entry, replay_receipt = repo.streaming.begin("learning", chat["identity"]["id"], request)
        assert replay_entry is None
        replay = await collect_events(repo, replay_entry, replay_receipt)
        assert replay[-1]["payload"]["replayed"]
        assert len(counter.calls) == len(observer.calls) == 1
        assert authority.run(run_id)["spent_dispatches"] == 1


async def test_image_revoked_at_native_manifest_denies_counter_http_and_saved_answer(tmp_path, offline):
    request = Send(expected_revision=1, text=PROMPT,
        request_id="synthetic-saved-learning-image-revoked", images=(IMAGE,))
    async with image_profile(tmp_path, revoke_image=True) as (services, owner, authority, registries,
            transports, admissions, counter, observer):
        repo = services.get("conversations")
        chat = repo.create(NewConversation())
        request = request.model_copy(update={"expected_revision": chat["revision"]})
        entry, receipt = repo.streaming.begin("learning", chat["identity"]["id"], request)
        run_id = entry["run"].id
        assert authority.run(run_id)["purpose"] == "explain"
        assert set(authority.run(run_id)["effective_capabilities"]) == set(CAPABILITIES)
        events = await collect_events(repo, entry, receipt)
        assert [event["type"] for event in events
            if event["type"] in {"completed", "error", "cancelled"}] == ["error"]
        assert len(owner.revocations) == 1
        callback, epoch = owner.revocations[0]
        binding, registry = callback.binding, registries[-1]
        assert binding == admissions[-1].binding and binding.operation_id == run_id
        assert authority.revocation_overlay() == {"epoch": epoch, "revoked": ["image"]}
        result = owner.process.domain_result(callback.callback_id)
        assert result["outcome"] == "uncertain_after_disconnect"
        assert result["error"] == {"code": "capability_revoked", "status": 409, "retryable": False}
        assert "result" not in result
        assert [request.command for request in registry.requests] == ["model.prepare", "model.manifest"]
        decodes = [request for request in owner.callbacks if request.command == "learning.validate_images"]
        # Native manifest registration precedes decoder/serialization; refusal
        # at this boundary must stop those later public callbacks entirely.
        assert decodes == []
        assert counter.calls == [] and not counter.finalized.is_set()
        assert transports == [] and observer.calls == [] and not observer.entered.is_set()
        assert authority.run(run_id)["spent_dispatches"] == 0
        assert owner.bridge.completed(run_id) is None and registry.publications == []
        assert authority.run(run_id)["state"] == "settled"
        assert registry.status(binding).owned == 0 and registry.status(binding).runs == 0
        assert owner.process.domain_status(operation_id=run_id)["active"] == 0
        assert len(registry.releases) == 1
        _, released, canonical = registry.releases[0]
        assert released.owned == 0 and released.receipts == () and canonical["state"] == "settled"
        assert (await command(owner.process, "session.get", {"session_id": binding.session_id}))["execution"] == "settled"
        page = await command(owner.process, "session.messages", {"session_id": binding.session_id})
        native_input = next(message for message in page["messages"] if message["id"] == binding.input_id)
        assert len(native_input["files"]) == 1 and native_input["files"][0]["data"] == PNG
        assert native_input["files"][0]["source"] == {"type": "inline"}
        history = await owner.bridge.messages(chat["identity"]["id"])
        assert [message["role"] for message in history["items"]] == ["user"]
        callbacks_before = len(owner.callbacks)
        replay_entry, replay_receipt = repo.streaming.begin("learning", chat["identity"]["id"], request)
        assert replay_entry is None
        replay = await collect_events(repo, replay_entry, replay_receipt)
        assert replay[-1]["type"] == "error" and replay[-1]["payload"]["replayed"]
        assert len(owner.callbacks) == callbacks_before
        assert counter.calls == [] and transports == [] and observer.calls == []
        assert authority.run(run_id)["spent_dispatches"] == 0
        public = json.dumps({"callbacks": [callback.payload for callback in owner.callbacks],
            "events": events, "messages": page, "error": result["error"]})
        assert "synthetic_learning_image_python_only_4719" not in public
