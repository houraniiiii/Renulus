"""Public saved-owner model pins; native observation is explicitly synthetic."""
from pathlib import Path
import asyncio
import json

import pytest
import httpx

from renulus.contracts import ApiError
from renulus.runtime.harness_domain import DomainBinding, DomainRequest, DomainCancellation, DomainCancelled
from renulus.runtime.harness_configuration import CandidateHealth, ConfigurationAuthority, ConfigurationSpec, ConnectionReference, RestartBoundary, RolePolicy
from renulus.runtime.harness_deployment import DeploymentEvidence
from renulus.runtime.harness_model_registry import HarnessModelRegistry
from renulus.runtime.manager import ProviderManager
from renulus.runtime.harness_learning import HarnessLearningOwner
from renulus.runtime.harness_process import HarnessProcessConfig
from tests.runtime.test_harness_learning_admission import saved_admission
from tests.runtime.test_harness_learning_current import AdmissionTransport
from tests.learn.test_harness_bridge import ScriptedTransport, active_shape
from tests.runtime.test_harness_model_registry import BOUNDS, GATEWAY, LIMITS, native, wire


class ObservedProcess:
    """Synthetic process port exposes native and callback ownership separately."""
    def __init__(self):
        self.execution = "active"
        self.callbacks = 1
        self.observed = asyncio.Event()
        self.exited = False

    async def request(self, command, payload, operation_id, attempt_id, timeout):
        assert command == "session.get"
        self.observed.set()
        return {"outcome": "committed_reference", "result": {"execution": self.execution,
            "session": {"id": payload["session_id"]}}}

    def domain_status(self, *, operation_id):
        return {"active": self.callbacks, "retained": 1}

    async def settlement(self, timeout):
        return {"state": "settled" if self.exited else "pending"}

    async def close(self, timeout):
        self.execution, self.callbacks, self.exited = "settled", 0, True
        return {"state": "closed"}


async def test_model_authority_exists_only_for_the_admitted_native_input(saved_admission):
    services, authority, _, repo, chat, request, version = saved_admission
    config = HarnessProcessConfig(node_executable=Path("G:/unused-node.exe"),
        host_entry=Path("G:/unused-host.mjs"), profile_root=services.paths.root,
        profile_id="synthetic-profile", store_id="synthetic-runtime",
        domain_store_id="synthetic-domain", domain_path="state/renulus.sqlite3")
    owner = HarnessLearningOwner(services, config, configuration_id=version,
        configuration_authority=authority)
    owner.bridge.active_manifest = active_shape
    transport = AdmissionTransport(owner)
    owner.bridge.transport = transport
    services.registry["learning_harness"] = owner.bridge
    entry, receipt = repo.streaming.begin("learning", chat["identity"]["id"], request)
    unknown = DomainBinding(receipt["run_id"], "1", "ses_unknown", "msg_unknown", receipt["run_id"])
    assert owner.resolve_model_run(unknown) is None
    stream = owner.bridge.answer(entry)
    try:
        assert (await anext(stream)).type == "started"
        assert (await anext(stream)).type == "progress"
        bound = owner.resolve_model_run(transport.binding)
        assert bound.binding == transport.binding
        assert bound.configuration_version == version
        assert bound.operation_model == "mimo-v2.6-pro"
        assert bound.purpose == "explain" and bound.required_capabilities == ("tools",)
        assert owner.resolve_model_run(transport.binding).cancellation is bound.cancellation
        with services.db.transaction() as conn:
            assert bound.current(conn=conn) is None
        assert owner.resolve_model_run(unknown) is None
    finally:
        await owner.bridge.cancel(receipt["run_id"])
        await stream.aclose()
        await repo.streaming.close()


async def test_learning_settlement_waits_for_native_and_callback_ownership(saved_admission):
    services, authority, _, repo, chat, request, version = saved_admission
    config = HarnessProcessConfig(node_executable=Path("G:/unused-node.exe"),
        host_entry=Path("G:/unused-host.mjs"), profile_root=services.paths.root,
        profile_id="synthetic-profile", store_id="synthetic-runtime",
        domain_store_id="synthetic-domain", domain_path="state/renulus.sqlite3")
    owner = HarnessLearningOwner(services, config, configuration_id=version,
        configuration_authority=authority)
    process = ObservedProcess()
    owner.process = process
    owner.bridge.active_manifest = active_shape
    transport = AdmissionTransport(owner)
    owner.bridge.transport = transport
    services.registry["learning_harness"] = owner.bridge
    entry, receipt = repo.streaming.begin("learning", chat["identity"]["id"], request)
    stream = owner.bridge.answer(entry)
    task = None
    try:
        await anext(stream)
        await anext(stream)
        task = asyncio.create_task(owner.settle_run(entry))
        await asyncio.wait_for(process.observed.wait(), 2)
        assert not task.done()
        assert authority.run(receipt["run_id"])["state"] == "active"
        process.execution = "settled"
        await asyncio.sleep(.1)
        assert not task.done()
        assert authority.run(receipt["run_id"])["state"] == "active"
        process.callbacks = 0
        await asyncio.wait_for(task, 2)
        assert authority.run(receipt["run_id"])["state"] == "settled"
        assert authority.activation_snapshot()["pinned_runs"] == []
    finally:
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await owner.bridge.cancel(receipt["run_id"])
        await stream.aclose()
        await repo.streaming.close()


async def test_admitted_learning_callback_rechecks_required_capability_revocation(saved_admission):
    services, authority, _, repo, chat, request, version = saved_admission
    config = HarnessProcessConfig(node_executable=Path("G:/unused-node.exe"),
        host_entry=Path("G:/unused-host.mjs"), profile_root=services.paths.root,
        profile_id="synthetic-profile", store_id="synthetic-runtime",
        domain_store_id="synthetic-domain", domain_path="state/renulus.sqlite3")
    owner = HarnessLearningOwner(services, config, configuration_id=version,
        configuration_authority=authority)
    owner.bridge.active_manifest = active_shape
    transport = AdmissionTransport(owner)
    owner.bridge.transport = transport
    services.registry["learning_harness"] = owner.bridge
    entry, receipt = repo.streaming.begin("learning", chat["identity"]["id"], request)
    stream = owner.bridge.answer(entry)
    try:
        await anext(stream)
        await anext(stream)
        grant = await owner.authorize(DomainRequest("capability-check", transport.binding, "learning.check", {}))
        assert grant.check_current() is True
        authority.revoke("tools")
        with pytest.raises(ApiError) as failure:
            grant.check_current()
        assert failure.value.code == "capability_revoked"
    finally:
        await owner.bridge.cancel(receipt["run_id"])
        await stream.aclose()
        await repo.streaming.close()


async def test_saved_model_factory_retains_counter_until_native_domain_and_registry_settle(saved_admission):
    services, authority, _, repo, chat, incoming, old_version = saved_admission
    manager = ProviderManager(services.paths, http_transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"data": [{"id": "mimo-v2.6-pro"}]})))
    await manager.connect_go("synthetic_factory_credential", select=True)
    route = await manager.prepare_harness_route("mimo-v2.6-pro")
    spec = ConfigurationSpec(connection=ConnectionReference(provider=route.provider_id,
        credential_reference=route.credential_ref, credential_revision=route.credential_epoch),
        registry_hash="a" * 64, capabilities=("text", "tools"),
        roles=(RolePolicy(purpose="explain", output_tokens=32),))
    version = authority.stage(spec)
    assert authority.validate(version, lambda candidate: CandidateHealth(
        configuration_version=candidate.version, grant_epoch=candidate.grant_epoch,
        registry_hash=candidate.spec.registry_hash))
    authority.activate(version, RestartBoundary(admission_closed=True, runtime_stopped=True,
        domain_settled=True), expected_effective=old_version)
    authority.open_admission(version, registry_hash=spec.registry_hash, grant_epoch=0)
    entered, release, finalized = (asyncio.Event() for _ in range(3))

    async def counter(body, manifest):
        try:
            entered.set()
            await release.wait()
            return 20  # Synthetic immutable account/count evidence only.
        finally:
            finalized.set()

    evidence = DeploymentEvidence("synthetic_factory_evidence", route, LIMITS, ("text", "tools"),
        "synthetic_limits", "synthetic_capabilities", "synthetic_counter", counter)

    def no_http(actual):
        pytest.fail("Cancelled proof must not create an HTTP owner.")

    def factory(resolve_run):
        return HarnessModelRegistry(manager, authority, resolve_run=resolve_run, evidence=lambda _: evidence,
            http_transport=no_http, gateway_bounds=GATEWAY, bounds=BOUNDS)

    config = HarnessProcessConfig(node_executable=Path("G:/unused-node.exe"),
        host_entry=Path("G:/unused-host.mjs"), profile_root=services.paths.root,
        profile_id="synthetic-profile", store_id="synthetic-runtime",
        domain_store_id="synthetic-domain", domain_path="state/renulus.sqlite3")
    owner = HarnessLearningOwner(services, config, configuration_id=version,
        configuration_authority=authority, model_registry_factory=factory)
    owner.bridge.active_manifest = active_shape
    transport, process = AdmissionTransport(owner), ObservedProcess()
    owner.bridge.transport, owner.process = transport, process
    process.execution, process.callbacks = "settled", 0
    services.registry["learning_harness"] = owner.bridge
    entry, receipt = repo.streaming.begin("learning", chat["identity"]["id"], incoming)
    stream, dispatch, observer = owner.bridge.answer(entry), None, None

    async def invoke(command, payload):
        request = DomainRequest(command, transport.binding, command, payload)
        grant = await owner.authorize(request)
        assert grant is not None and grant.check_current() is True
        return await grant.handler(request, DomainCancellation())

    try:
        await anext(stream)
        await anext(stream)
        plan = await invoke("model.prepare", {})
        await invoke("model.manifest", {"manifest": native()})
        serialized, _ = wire(route)
        dispatch = asyncio.create_task(invoke("model.dispatch", {"dispatch_id": plan["dispatch_id"],
            "serialized_request": serialized}))
        await asyncio.wait_for(entered.wait(), 2)
        observer = asyncio.create_task(owner.settle_run(entry, timeout=1))
        await asyncio.sleep(.05)
        assert not observer.done() and authority.run(receipt["run_id"])["state"] == "active"
        assert owner.model_registry.status(transport.binding).owned == 1
        observer.cancel()
        await asyncio.gather(observer, return_exceptions=True)
        assert authority.activation_snapshot()["pinned_runs"]
        await owner.bridge.cancel(receipt["run_id"])
        assert owner.model_bindings[receipt["run_id"]].cancellation.cancelled
        assert not finalized.is_set() and not dispatch.done()
        release.set()
        with pytest.raises(DomainCancelled):
            await dispatch
        assert (await owner.settle_run(entry, timeout=2))["state"] == "settled"
        assert (await owner.settle_run(entry, timeout=0))["state"] == "settled"
        assert finalized.is_set() and owner.model_registry.status(transport.binding).runs == 0
        assert authority.activation_snapshot()["pinned_runs"] == []
        assert authority.run(receipt["run_id"])["spent_dispatches"] == 0
        assert owner.resolve_model_run(transport.binding) is None
    finally:
        release.set()
        if dispatch is not None:
            await asyncio.gather(dispatch, return_exceptions=True)
        await owner.bridge.cancel(receipt["run_id"])
        await stream.aclose()
        await repo.streaming.close()
        await owner.model_registry.close(1)
        await manager.close()


async def test_generation_replacement_rejects_a_reused_registry_before_rebinding(saved_admission):
    services, authority, _, _, _, _, version = saved_admission
    manager = ProviderManager(services.paths)
    registries = []

    def factory(resolve_run):
        if not registries:
            registries.append(HarnessModelRegistry(manager, authority, resolve_run=resolve_run,
                evidence=lambda _: None, http_transport=lambda _: None, gateway_bounds=GATEWAY, bounds=BOUNDS))
        return registries[0]  # Explicit faulty assembly: reused generation owner.

    config = HarnessProcessConfig(node_executable=Path("G:/unused-node.exe"),
        host_entry=Path("G:/unused-host.mjs"), profile_root=services.paths.root,
        profile_id="synthetic-profile", store_id="synthetic-runtime",
        domain_store_id="synthetic-domain", domain_path="state/renulus.sqlite3")
    owner = HarnessLearningOwner(services, config, configuration_id=version,
        configuration_authority=authority, model_registry_factory=factory)
    prior = owner.process
    assert (await prior.settlement(0))["state"] == "settled"
    seal = owner.seal_new_runs(expected_effective=version)
    try:
        with pytest.raises(ApiError) as error:
            owner.replace_process(ObservedProcess(), configuration_id=version, seal=seal)
        assert error.value.code == "harness_owner_conflict"
        assert owner.process is prior and owner.bridge.transport is prior
        assert owner.model_registry is registries[0]
    finally:
        seal.release()
        await registries[0].close(0)
        await manager.close()


async def test_learning_close_seals_saved_admission_before_waiting_for_exit(saved_admission):
    services, authority, _, repo, chat, incoming, version = saved_admission
    entered, release = asyncio.Event(), asyncio.Event()

    class ClosingProcess:
        async def close(self, timeout):
            entered.set()
            await release.wait()
            return {"state": "closed"}

        def domain_status(self, *, operation_id):
            return {"active": 0}

    config = HarnessProcessConfig(node_executable=Path("G:/unused-node.exe"),
        host_entry=Path("G:/unused-host.mjs"), profile_root=services.paths.root,
        profile_id="synthetic-profile", store_id="synthetic-runtime",
        domain_store_id="synthetic-domain", domain_path="state/renulus.sqlite3")
    owner = HarnessLearningOwner(services, config, configuration_id=version,
        configuration_authority=authority)
    owner.process = ClosingProcess()
    owner.bridge.active_manifest = active_shape
    services.registry["learning_harness"] = owner.bridge
    closing, entry = asyncio.create_task(owner.close()), None
    try:
        await asyncio.wait_for(entered.wait(), 2)
        with pytest.raises(ApiError) as error:
            entry, _ = repo.streaming.begin("learning", chat["identity"]["id"], incoming)
        assert error.value.code == "runtime_stopping" and error.value.retryable
        assert authority.activation_snapshot()["pinned_runs"] == []
        assert not closing.done()
    finally:
        release.set()
        await closing
        if entry is not None:
            await owner.settle_run(entry)


async def test_cancel_before_first_model_callback_cannot_mint_fresh_authority(saved_admission):
    services, authority, _, repo, chat, incoming, version = saved_admission
    config = HarnessProcessConfig(node_executable=Path("G:/unused-node.exe"),
        host_entry=Path("G:/unused-host.mjs"), profile_root=services.paths.root,
        profile_id="synthetic-profile", store_id="synthetic-runtime",
        domain_store_id="synthetic-domain", domain_path="state/renulus.sqlite3")
    owner = HarnessLearningOwner(services, config, configuration_id=version,
        configuration_authority=authority)
    owner.bridge.active_manifest = active_shape
    transport = AdmissionTransport(owner)
    owner.bridge.transport = transport
    services.registry["learning_harness"] = owner.bridge
    entry, receipt = repo.streaming.begin("learning", chat["identity"]["id"], incoming)
    stream = owner.bridge.answer(entry)
    try:
        await anext(stream)
        await anext(stream)
        await owner.bridge.cancel(receipt["run_id"])
        with pytest.raises(ApiError) as error:
            owner.resolve_model_run(transport.binding)
        assert error.value.code == "harness_cancelled"
        assert authority.run(receipt["run_id"])["spent_dispatches"] == 0
    finally:
        await stream.aclose()
        await repo.streaming.close()


async def test_owner_close_settles_a_saved_run_whose_stream_is_still_paused(saved_admission):
    services, authority, _, repo, chat, incoming, version = saved_admission
    config = HarnessProcessConfig(node_executable=Path("G:/unused-node.exe"),
        host_entry=Path("G:/unused-host.mjs"), profile_root=services.paths.root,
        profile_id="synthetic-profile", store_id="synthetic-runtime",
        domain_store_id="synthetic-domain", domain_path="state/renulus.sqlite3")
    owner = HarnessLearningOwner(services, config, configuration_id=version,
        configuration_authority=authority)
    owner.process = ObservedProcess()
    owner.bridge.active_manifest = active_shape
    transport = AdmissionTransport(owner)
    owner.bridge.transport = transport
    services.registry["learning_harness"] = owner.bridge
    entry, receipt = repo.streaming.begin("learning", chat["identity"]["id"], incoming)
    stream = owner.bridge.answer(entry)
    try:
        await anext(stream)
        await anext(stream)
        owner.resolve_model_run(transport.binding)
        await owner.close()
        assert authority.run(receipt["run_id"])["state"] == "settled"
        assert authority.activation_snapshot()["pinned_runs"] == []
        assert owner.resolve_model_run(transport.binding) is None
    finally:
        await stream.aclose()
        await repo.streaming.close()


async def test_cleanup_failure_retains_lifecycle_pin_without_a_second_answer_terminal(saved_admission):
    services, _, _, repo, chat, incoming, version = saved_admission

    class FailedCleanupAuthority(ConfigurationAuthority):
        def settle_run(self, run_id):
            raise ApiError("synthetic_cleanup_failed", "Synthetic lifecycle failure.", 503, True)

    authority = FailedCleanupAuthority(services.db)
    config = HarnessProcessConfig(node_executable=Path("G:/unused-node.exe"),
        host_entry=Path("G:/unused-host.mjs"), profile_root=services.paths.root,
        profile_id="synthetic-profile", store_id="synthetic-runtime",
        domain_store_id="synthetic-domain", domain_path="state/renulus.sqlite3")
    owner = HarnessLearningOwner(services, config, configuration_id=version,
        configuration_authority=authority)

    class AdmittedTranscript(ScriptedTransport):
        async def request(self, command, payload, operation_id, attempt_id, timeout):
            response = await super().request(command, payload, operation_id, attempt_id, timeout)
            if command == "session.prompt":
                result = response["result"]
                binding = DomainBinding(operation_id, attempt_id, result["sessionId"], result["inputId"], operation_id)
                request = DomainRequest("synthetic-admission", binding, "learning.admit_input", {})
                grant = await owner.authorize(request)
                await grant.handler(request, DomainCancellation())
            return response

    owner.bridge.active_manifest = active_shape
    owner.bridge.transport = AdmittedTranscript()
    services.registry["learning_harness"] = owner.bridge
    entry, receipt = repo.streaming.begin("learning", chat["identity"]["id"], incoming)
    events = [json.loads(encoded.split("data: ", 1)[1])
        async for encoded in repo.streaming.events(entry, receipt)]
    assert [event["type"] for event in events if event["type"] in {"completed", "error", "cancelled"}] == ["completed"]
    assert repo.streaming.status("learning", chat["identity"]["id"], receipt["run_id"])["state"] == "completed"
    assert authority.activation_snapshot()["pinned_runs"]
    with pytest.raises(ApiError) as error:
        await owner.close()
    assert error.value.code == "synthetic_cleanup_failed"


async def test_learning_close_joins_queued_startup_before_reporting_closed(saved_admission):
    services, authority, _, _, _, _, version = saved_admission
    release = asyncio.Event()

    class StartupProcess:
        closed = False
        late_starts = 0

        async def start(self, config):
            if self.closed:
                self.late_starts += 1
            await release.wait()

        async def close(self, timeout):
            self.closed = True
            return {"state": "closed"}

        async def request(self, *args):
            return {"outcome": "committed_reference"}

    class StartupActivation:
        async def activate(self):
            pass  # Synthetic activation port; this test owns no native stores.

    config = HarnessProcessConfig(node_executable=Path("G:/unused-node.exe"),
        host_entry=Path("G:/unused-host.mjs"), profile_root=services.paths.root,
        profile_id="synthetic-profile", store_id="synthetic-runtime",
        domain_store_id="synthetic-domain", domain_path="state/renulus.sqlite3")
    owner = HarnessLearningOwner(services, config, configuration_id=version,
        configuration_authority=authority)
    process = StartupProcess()
    owner.process, owner.activation = process, StartupActivation()
    starting, closing = asyncio.create_task(owner.start()), asyncio.create_task(owner.close())
    try:
        await asyncio.sleep(.05)
        assert process.late_starts == 0
        assert not closing.done() or starting.done()
    finally:
        release.set()
        await asyncio.gather(starting, closing, return_exceptions=True)
