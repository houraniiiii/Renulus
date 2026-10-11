"""Production saved Library/M5 tracer over native SDK, IPC and loopback HTTP.

Account discovery, route limits and inclusive counts are synthetic attestations.
The external HTTP boundary is loopback; Library, FastEmbed/LanceDB, native tools,
deployment permits and MemoryService publication are their real public owners.
"""
import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import subprocess

import httpx

from renulus.contracts import ContextScope, Scope
from renulus.design_c_contracts import Dependency, EligibleInput, Identity, canonical_digest
from renulus.learn.conversation_models import NewConversation, Send
from renulus.memory.lineage import AnswerInputs
from renulus.runtime.harness_configuration import (
    AttemptPolicy, CandidateHealth, ConfigurationAuthority, ConfigurationSpec,
    ConnectionReference, ContextPolicy, RestartBoundary, RolePolicy, RouteLimits,
)
from renulus.runtime.harness_deployment import DeploymentEvidence
from renulus.runtime.harness_gateway import GatewayBounds
from renulus.runtime.harness_learning import HarnessLearningOwner
from renulus.runtime.harness_model_registry import ModelRegistryBounds
from renulus.runtime.manager import ProviderManager
from renulus.server import create_app
from test_harness_learning_models import (
    ObservedRegistry, collect_events, command, inspect_candidate, process_config,
)
from test_harness_model_dispatch_sdk import LoopbackHttp, NODE, offline


SOURCE = Path(__file__).resolve().parents[2]
TEXT = (
    "Synthetic nephrology teaching note, without patient data.\n\n"
    "CKD learning compares albuminuria and filtration as complementary concepts.\n\n"
    "Dialysis adequacy discussion includes urea clearance and vascular access.\n\n"
    "Transplant rejection assessment considers biopsy alongside clinical context.\n\n"
    "Glomerular disease can present with hematuria and proteinuria."
)
PROMPT = "Use Library evidence to compare synthetic CKD, dialysis, transplant and glomerular learning."
QUERY = "CKD albuminuria filtration dialysis adequacy transplant rejection glomerular disease"
ANSWER = "Synthetic nephrology learning spans CKD markers, dialysis adequacy, transplant rejection and glomerular presentations [1]."
CALL_ID = "synthetic_library_call_1"
CAPABILITIES = ("text", "tools")
LIMITS = RouteLimits(input_tokens=512, output_tokens=64, window_tokens=640)
DISPATCH_LIMIT = 2


class LibraryHttp:
    """The first real response requests a tool; the next uses its native result."""
    def __init__(self, credential):
        self.credential = credential
        self.calls, self.handlers, self.errors = [], set(), []
        self.passages = None

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
            payload = json.loads(body)
            assert self.calls[-1]["authenticated"]
            assert payload["model"] == "mimo-v2.6-pro" and payload["stream"] is True
            if len(self.calls) == 1:
                assert not any(message["role"] == "tool" for message in payload["messages"])
                delta = {"tool_calls": [{"index": 0, "id": CALL_ID, "type": "function",
                    "function": {"name": "renulus_library_retrieve",
                        "arguments": json.dumps({"query": QUERY, "limit": 1})}}]}
                finish = "tool_calls"
            else:
                assert len(self.calls) == 2, "The bounded tracer has exactly two HTTP effects"
                tool = [message for message in payload["messages"] if message["role"] == "tool"]
                assert len(tool) == 1 and tool[0]["tool_call_id"] == CALL_ID
                result = json.loads(tool[0]["content"])
                assert result["status"] == "ready" and len(result["passages"]) == 1
                self.passages = result["passages"]
                assert self.passages[0]["locators"]
                assert all(word in self.passages[0]["text"] for word in (
                    "albuminuria", "Dialysis", "Transplant", "Glomerular"))
                delta, finish = {"content": ANSWER}, "stop"
            events = [{"id": "synthetic_library_response", "model": "mimo-v2.6-pro",
                "choices": [{"index": 0, "delta": current, "finish_reason": outcome}]}
                for current, outcome in ((delta, None), ({}, finish))]
            response = ("".join("data: " + json.dumps(event) + "\n\n" for event in events)
                + "data: [DONE]\n\n").encode()
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n"
                + f"Content-Length: {len(response)}\r\nConnection: close\r\n\r\n".encode() + response)
            await writer.drain()
        except Exception as error:
            self.errors.append(error)
        finally:
            writer.close()
            await writer.wait_closed()
            self.handlers.discard(task)


class LibraryCounter:
    """Synthetic inclusive count validates both actual immutable native inputs."""
    def __init__(self):
        self.calls = []

    async def __call__(self, body, manifest):
        assert "nephrology education" in manifest.system
        assert {tool.name for tool in manifest.tools} == {
            "renulus_library_retrieve", "renulus_library_citation"}
        assert all(json.loads(tool.parameters_json)["type"] == "object" for tool in manifest.tools)
        parts = [part for message in manifest.messages for part in message.content]
        assert any(part.type == "text" and part.text == PROMPT for part in parts)
        payload = json.loads(body)
        assert payload["max_completion_tokens"] == 64
        assert payload["model"] == "mimo-v2.6-pro" and payload["stream"] is True
        if self.calls:
            calls = [part for part in parts if part.type == "tool-call"]
            results = [part for part in parts if part.type == "tool-result"]
            assert len(calls) == len(results) == 1
            assert calls[0].id == results[0].id == CALL_ID
            assert calls[0].name == "renulus_library_retrieve"
            assert json.loads(calls[0].arguments_json) == {"query": QUERY, "limit": 1}
            assert json.loads(results[0].output_text)["passages"]
        self.calls.append((body, manifest))
        # Explicit synthetic inclusive attestations, including native system,
        # input, tool schemas/call/result and provider framing; no tokenizer claim.
        return 260 if len(self.calls) == 2 else 200


class PublicationRegistry(ObservedRegistry):
    def require_publication(self, binding, *, conn):
        result = super().require_publication(binding, conn=conn)
        assert conn.in_transaction
        for receipt in self.status(binding).receipts:
            permit = conn.execute("SELECT * FROM harness_configuration_attempts WHERE permit_id=?",
                (receipt.permit_id,)).fetchone()
            assert permit["state"] == "confirmed" and permit["run_id"] == binding.operation_id
            assert permit["payload_hash"] == receipt.body_sha256
        return result


@asynccontextmanager
async def library_models(tmp_path):
    assert NODE.is_file(), "Pinned Node artifact is required"
    root = tmp_path / "profile"
    root.mkdir()
    assets = Path(os.environ["RENULUS_LIBRARY_HELPERS"]).resolve()
    assert (assets / "manifest.json").is_file()
    subprocess.run(["powershell.exe", "-NoProfile", "-Command",
        f"New-Item -ItemType Junction -Path '{root / 'helpers'}' -Target '{assets}' | Out-Null"],
        check=True, capture_output=True)
    app = create_app(root, source_root=SOURCE)
    services = app.state.services
    services.get("helpers").startup.configure()
    authority = ConfigurationAuthority(services.db)
    credential = "synthetic_library_python_only_6372"
    manager = ProviderManager(services.paths, http_transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"data": [{"id": "mimo-v2.6-pro"}]})))
    services.registry["provider"] = manager
    counter, observer = LibraryCounter(), LibraryHttp(credential)
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
                output_tokens=64, dispatch_limit=DISPATCH_LIMIT),), capabilities=CAPABILITIES,
            context=ContextPolicy(requested_window_tokens=640, reserve_tokens=8),
            attempts=AttemptPolicy(foreground_dispatches=DISPATCH_LIMIT, retries=0))
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
        evidence = DeploymentEvidence("synthetic_library_account_v1", route, LIMITS, CAPABILITIES,
            "synthetic_immutable_limits_v1", "synthetic_capabilities_v1",
            "synthetic_inclusive_library_continuation_counter_v1", counter)

        def factory(resolve_run):
            def resolve(binding):
                admission = resolve_run(binding)
                if admission is not None:
                    assert resolve_run(binding) is admission
                    admissions.append(admission)
                return admission

            def transport(actual):
                assert replace(actual, catalogue_listed=None) == replace(route, catalogue_listed=None)
                result = LoopbackHttp(actual, port)
                transports.append(result)
                return result

            registry = PublicationRegistry(manager, authority, resolve_run=resolve,
                evidence=lambda actual: evidence, http_transport=transport,
                gateway_bounds=GatewayBounds(max_request_bytes=32768,
                    max_response_bytes=8192, timeout_seconds=20),
                bounds=ModelRegistryBounds(max_runs=1, max_plans_per_run=2, max_owned=1,
                    max_retained_bytes=300000, max_manifest_bytes=32768, max_frame_bytes=65536))
            registries.append(registry)
            return registry

        owner = HarnessLearningOwner(services, process_config(root, "synthetic-library-models"),
            configuration_id=version, memory=services.get("memory"), context_filtering=True,
            configuration_authority=authority, model_registry_factory=factory)
        owner.install()
        await owner.start()
        yield app, owner, authority, registries, transports, admissions, counter, observer
    finally:
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
        await services.get("memory").close()
        services.get("knowledge").index.close()
        services.get("helpers").startup.close()


async def test_production_saved_library_answer_has_native_continuation_m5_and_settled_permits(tmp_path, offline, record_property):
    async with library_models(tmp_path) as (app, owner, authority, registries, transports,
            admissions, counter, observer):
        services = app.state.services
        library = services.get("knowledge")
        source = await asyncio.to_thread(library.import_text, TEXT, title="Synthetic varied nephrology",
            scope=ContextScope(kind=Scope.LIBRARY), idempotency_key="library-model-tracer")
        assert source["status"] == "ready", source
        repo = services.get("conversations")
        chat = repo.create(NewConversation())
        entry, receipt = repo.streaming.begin("learning", chat["identity"]["id"],
            Send(expected_revision=chat["revision"], text=PROMPT, request_id="saved-library-model-tracer"))
        run_id = entry["run"].id
        identity = Identity(type="library_revision", id=source["revision_id"])
        with services.db.transaction() as conn:
            source_pin = owner.library.resolve_dependency(conn, identity, authority=owner.authority(entry))
        assert source_pin is not None
        events = await collect_events(repo, entry, receipt)
        assert not observer.errors, observer.errors
        assert events[-1]["type"] == "completed", json.dumps(events, indent=2)
        reference = events[-1]["payload"]["answer_reference"]
        binding, registry = admissions[-1].binding, registries[-1]
        assert binding.operation_id == binding.cancellation_id == run_id
        assert binding.attempt_id == "1" and reference["input_id"] == binding.input_id
        assert reference["runtime"]["session_id"] == binding.session_id
        assert reference["sha256"] == hashlib.sha256(ANSWER.encode()).hexdigest()
        assert len(observer.calls) == len(counter.calls) == len(transports) == 2
        assert [request.command for request in registry.requests] == [
            "model.prepare", "model.manifest", "model.dispatch",
            "model.prepare", "model.manifest", "model.dispatch"]
        assert all(request.binding == binding for request in registry.requests)
        assert all(call["authenticated"] and call["session_id"] == binding.session_id
            and call["request_line"] == "POST /zen/go/v1/chat/completions HTTP/1.1"
            for call in observer.calls)
        assert not observer.handlers
        for (body, _), transport, call in zip(counter.calls, transports, observer.calls, strict=True):
            assert transport.sent == [body] and call["body"] == body
            assert b"synthetic_library_python_only_6372" not in body

        assert len(reference["citations"]) == 1 and reference["inputs"] == []
        citation = reference["citations"][0]
        passage = observer.passages[0]
        assert citation["passage_id"] == passage["id"]
        assert citation["document_id"] == passage["document_id"] == source["document_id"]
        assert citation["revision_id"] == passage["document_revision"] == source["revision_id"]
        assert citation["locators"] == passage["locators"]
        opened = library.citation(source["revision_id"], passage_id=passage["id"])
        assert opened["locators"] == citation["locators"]
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            original = await client.get(opened["original_url"])
        assert original.status_code == 200 and original.text == TEXT

        dependency = Dependency(target=identity, expected_revision=source_pin)
        assert reference["dependencies"] == [dependency.model_dump(mode="json")]
        resolved = await owner.resolve_completed_answer(reference)
        assert resolved["text"] == ANSWER and resolved["digest"] == reference["sha256"]
        closure = AnswerInputs(dependencies=(dependency,))
        assert resolved["input"] == closure.model_dump(mode="json")
        saved = owner.bridge.completed(run_id)
        assert {key: value for key, value in saved.items() if key != "publication_digest"} == reference
        assert saved["publication_digest"] == resolved["publication_digest"]
        memory = services.get("memory")
        with services.db.transaction() as conn:
            eligible = memory.eligible_answer_references_in(conn, (reference,))
        assert eligible == (EligibleInput(kind="committed_evidence", dependency=Dependency(
            target=Identity(type="learning_evidence", id="learn-answer:" + run_id),
            expected_revision=saved["publication_digest"])),)
        evidence = services.db.fetch_one("SELECT * FROM learning_evidence WHERE id=?", ("learn-answer:" + run_id,))
        lineage = services.db.fetch_one("SELECT * FROM memory_answer_lineage WHERE evidence_id=?",
            ("learn-answer:" + run_id,))
        assert json.loads(evidence["payload_json"])["answer_reference"] == reference
        assert json.loads(lineage["manifest_json"]) == closure.model_dump(mode="json")
        assert lineage["state"] == "active" and lineage["project_id"] is None
        assert saved["publication_digest"] == canonical_digest({
            "evidence": evidence, "manifest": closure.model_dump(mode="json"), "project_id": None})
        assert memory.repository.jobs() == []

        native = await command(owner.process, "session.get", {"session_id": binding.session_id})
        assert native["execution"] == "settled"
        page = await command(owner.process, "session.messages", {"session_id": binding.session_id})
        native_ids = {message["id"] for message in page["messages"]}
        assert {binding.input_id, *reference["message_ids"]} <= native_ids
        assert binding.input_id not in reference["message_ids"] and len(reference["message_ids"]) == 2
        history = await owner.bridge.messages(chat["identity"]["id"])
        assert history["items"][-1]["role"] == "assistant" and history["items"][-1]["content"] == ANSWER
        assert services.db.fetch_all("SELECT * FROM learn_messages") == []
        assert len(services.db.fetch_all("SELECT * FROM learn_harness_mappings")) == 1
        assert len(services.db.fetch_all("SELECT * FROM learn_harness_answers")) == 1
        assert owner.process.domain_status(operation_id=run_id)["active"] == 0
        assert run_id not in repo.streaming.active
        assert authority.run(run_id)["state"] == "settled"
        assert authority.run(run_id)["spent_dispatches"] == 2
        assert registry.status(binding).owned == 0
        assert len(registry.releases) == 1
        _, released, canonical = registry.releases[0]
        assert released.owned == 0 and canonical["state"] == "settled"
        proofs = released.receipts
        assert len(proofs) == 2 and [proof.input_tokens for proof in proofs] == [200, 260]
        assert [proof.request_kind for proof in proofs] == ["primary", "tool-continuation"]
        assert proofs[0].continuation_of is None and proofs[1].continuation_of == proofs[0].permit_id
        for proof, (body, manifest) in zip(proofs, counter.calls, strict=True):
            assert proof.body_sha256 == hashlib.sha256(body).hexdigest() and proof.body_bytes == len(body)
            assert proof.input_manifest_sha256 == hashlib.sha256(manifest.model_dump_json().encode()).hexdigest()
            permit = authority.permit(proof.permit_id)
            assert permit["state"] == "confirmed" and permit["payload_hash"] == proof.body_sha256
        assert registry.publications and all(current_conn and current_binding == binding
            and status.receipts == proofs for current_binding, status, current_conn in registry.publications)
        record_property("connected_proof", json.dumps({
            "entry": str(SOURCE / "packages/harness/src/main.mjs"),
            "answer_reference": reference, "publication_digest": saved["publication_digest"],
            "lineage": closure.model_dump(mode="json"),
            "dispatches": [{"permit_id": proof.permit_id, "kind": proof.request_kind,
                "continuation_of": proof.continuation_of, "body_sha256": proof.body_sha256,
                "manifest_sha256": proof.input_manifest_sha256, "input_tokens": proof.input_tokens}
                for proof in proofs], "native_execution": native["execution"],
            "domain_active": owner.process.domain_status(operation_id=run_id)["active"],
            "canonical_run": authority.run(run_id)["state"], "citation_open": original.status_code,
            "publication_checks": len(registry.publications), "owned": released.owned,
            "evidence": "synthetic account/limits/inclusive counter; actual SDK/Library/M5/loopback HTTP",
        }))
