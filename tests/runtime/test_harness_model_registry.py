"""Public registry/Authority/Provider ports; evidence and HTTP are synthetic."""
import asyncio
import base64
from dataclasses import replace
import hashlib
import json
import threading
from uuid import uuid4

import httpx
import pytest

from renulus.contracts import ApiError
from renulus.runtime.harness_configuration import (
    CandidateHealth, ConfigurationAuthority, ConfigurationSpec, ConnectionReference,
    RestartBoundary, RolePolicy, RouteLimits,
)
from renulus.runtime.harness_deployment import DeploymentEvidence
from renulus.runtime.harness_domain import (
    DomainBinding, DomainCallbacks, DomainCancellation, DomainCancelled, DomainRequest,
)
from renulus.runtime.harness_gateway import GatewayBounds
from renulus.runtime.harness_model_registry import (
    HarnessModelRegistry, ModelRegistryBounds, ModelRunAuthority,
)
from renulus.runtime.manager import ProviderManager
from renulus.runtime.protected import ConnectionStore
from renulus.storage.database import Database


CAPS = ("text", "tools")
LIMITS = RouteLimits(input_tokens=100, output_tokens=32, window_tokens=150)
GATEWAY = GatewayBounds(max_request_bytes=8192, max_response_bytes=8192, timeout_seconds=2)
BOUNDS = ModelRegistryBounds(max_runs=2, max_plans_per_run=4, max_owned=1,
    max_retained_bytes=200000, max_manifest_bytes=32768, max_frame_bytes=65536)
SYSTEM = "Trusted synthetic nephrology education."
PROMPT = "Explain synthetic CKD."


class OwnedTransport(httpx.AsyncBaseTransport):
    def __init__(self, state):
        self.state, self.closed = state, False

    async def handle_async_request(self, request):
        assert not self.closed
        self.state["sent"].append(request.content)
        assert request.headers["authorization"] == "Bearer " + self.state["credential"]
        return httpx.Response(200, headers={"content-type": "text/event-stream"},
            content=b'data: {"choices":[{"delta":{"content":"Synthetic answer"}}]}\n\ndata: [DONE]\n\n')

    async def aclose(self):
        assert not self.closed
        self.closed = True


@pytest.fixture
async def registry(app_paths):
    credential = uuid4().hex
    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"data": [{"id": "mimo-v2.6-pro"}]})))
    await manager.connect_go(credential, select=True)
    route = await manager.prepare_harness_route("mimo-v2.6-pro")
    db = Database(app_paths.state / "model-registry.sqlite")
    authority = ConfigurationAuthority(db)
    spec = ConfigurationSpec(connection=ConnectionReference(provider=route.provider_id,
        credential_reference=route.credential_ref, credential_revision=route.credential_epoch,
        selected_model=route.catalog_model_id), registry_hash="a" * 64,
        roles=(RolePolicy(purpose="explain", output_tokens=32, dispatch_limit=4),), capabilities=CAPS)
    version = authority.stage(spec)
    assert authority.validate(version, lambda candidate: CandidateHealth(
        configuration_version=candidate.version, grant_epoch=candidate.grant_epoch,
        registry_hash=candidate.spec.registry_hash))
    authority.activate(version, RestartBoundary(admission_closed=True, runtime_stopped=True,
        domain_settled=True), expected_effective=None)
    authority.open_admission(version, registry_hash=spec.registry_hash, grant_epoch=0)
    binding = DomainBinding("learning_run", "1", "native_session", "native_input", "learning_run")
    authority.begin_run(binding.operation_id, "explain", capability_scope=CAPS,
        operation_model=route.catalog_model_id)
    state = {"credential": credential, "sent": [], "transports": [], "counted": [], "connections": []}

    def current(*, conn=None):
        state["connections"].append(conn)
        if state.get("error"):
            raise state["error"]

    admission = ModelRunAuthority(binding, version, "explain", route.catalog_model_id,
        CAPS, DomainCancellation(), current)

    async def count(body, manifest):
        state["counted"].append(body)
        return 20  # Explicit synthetic inclusive evidence, not a production tokenizer.

    state["admission"] = admission
    state["evidence"] = DeploymentEvidence("synthetic_exact_account", route, LIMITS, CAPS,
        "synthetic_limits_v1", "synthetic_caps_v1", "synthetic_inclusive_counter_v1", count)

    def transport(actual):
        assert replace(actual, catalogue_listed=None) == replace(route, catalogue_listed=None)
        owner = OwnedTransport(state)
        state["transports"].append(owner)
        return owner

    settings = dict(resolve_run=lambda _: state["admission"], evidence=lambda _: state["evidence"],
        http_transport=transport, gateway_bounds=GATEWAY, bounds=BOUNDS)
    module = HarnessModelRegistry(manager, authority, **settings)
    yield module, binding, authority, manager, route, state, settings
    await module.close(1)
    await manager.close()


def request(binding, command, payload):
    return DomainRequest(uuid4().hex, binding, command, payload)


async def invoke(module, binding, command, payload):
    actual = request(binding, command, payload)
    grant = await module.authorize(actual)
    assert grant is not None
    assert grant.check_current() is True
    return await grant.handler(actual, DomainCancellation())


def native(turn=0):
    messages = [{"role": "user", "content": [{"type": "text", "text": PROMPT}]}]
    for index in range(turn):
        messages.extend([
            {"role": "assistant", "content": [{"type": "tool-call", "id": f"call_{index}",
                "name": "renulus_library_retrieve", "arguments_json": '{"query":"CKD"}'}]},
            {"role": "tool", "content": [{"type": "tool-result", "id": f"call_{index}",
                "output_text": '{"status":"ready","passages":[]}'}]},
        ])
    return {"version": 1, "system": SYSTEM, "messages": messages,
        "tools": [{"name": "renulus_library_retrieve", "description": "Retrieve eligible teaching",
            "parameters_json": '{"type":"object","properties":{"query":{"type":"string"}}}'}]}


def wire(route, turn=0):
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": PROMPT}]
    for index in range(turn):
        messages.extend([
            {"role": "assistant", "content": None, "tool_calls": [{"id": f"call_{index}",
                "type": "function", "function": {"name": "renulus_library_retrieve", "arguments": '{"query":"CKD"}'}}]},
            {"role": "tool", "tool_call_id": f"call_{index}", "content": '{"status":"ready","passages":[]}'},
        ])
    body = json.dumps({"model": route.wire_model_id, "stream": True, "max_completion_tokens": 32,
        "messages": messages, "tools": [{"type": "function", "function": {
            "name": "renulus_library_retrieve", "description": "Retrieve eligible teaching",
            "parameters": {"type": "object", "properties": {"query": {"type": "string"}}}}}]}, indent=2).encode()
    return {"method": "POST", "url": route.endpoint, "headers": {"content-type": "application/json"},
        "body_base64": base64.b64encode(body).decode()}, body


async def prepare(module, binding, turn=0):
    plan = await invoke(module, binding, "model.prepare", {})
    await invoke(module, binding, "model.manifest", {"manifest": native(turn)})
    return plan


async def test_primary_proves_exact_body_sends_once_and_guards_canonical_publication(registry):
    module, binding, authority, _, route, state, _ = registry
    plan = await prepare(module, binding)
    envelope, body = wire(route)
    result = await invoke(module, binding, "model.dispatch",
        {"dispatch_id": plan["dispatch_id"], "serialized_request": envelope})
    permit = authority.permit(result["permit_id"])
    assert permit["state"] == "confirmed" and permit["request_kind"] == "primary"
    assert permit["payload_hash"] == hashlib.sha256(body).hexdigest()
    assert state["counted"] == state["sent"] == [body]
    assert len(state["transports"]) == 1 and state["transports"][0].closed
    assert authority.run(binding.operation_id)["spent_dispatches"] == 1
    with authority.db.transaction() as conn:
        module.require_publication(binding, conn=conn)
        assert state["connections"][-1] is conn
    assert module.status().owned == 0


async def test_two_native_continuations_own_new_steps_permits_and_fresh_transports(registry):
    module, binding, authority, _, route, state, _ = registry
    prior = None
    steps, dispatches = [], []
    for turn in range(3):
        plan = await prepare(module, binding, turn)
        assert plan["request_kind"] == ("primary" if turn == 0 else "tool-continuation")
        assert plan.get("continuation_of") == prior
        envelope, _ = wire(route, turn)
        result = await invoke(module, binding, "model.dispatch",
            {"dispatch_id": plan["dispatch_id"], "serialized_request": envelope})
        permit = authority.permit(result["permit_id"])
        assert module.status().receipts[-1].continuation_of == prior
        assert permit["state"] == "confirmed"
        steps.append(permit["step_id"])
        dispatches.append(plan["dispatch_id"])
        prior = result["permit_id"]
    assert len(set(steps)) == len(set(dispatches)) == 3
    assert authority.run(binding.operation_id)["spent_dispatches"] == len(state["sent"]) == 3
    assert len(state["transports"]) == 3 and all(owner.closed for owner in state["transports"])
    with authority.db.transaction() as conn:
        module.require_publication(binding, conn=conn)
    assert len(module.status().receipts) == 3


@pytest.mark.parametrize("change", [
    {"binding": DomainBinding("other_run", "1", "native_session", "native_input", "other_run")},
    {"configuration_version": "b" * 64}, {"purpose": "generated-practice"},
    {"operation_model": "minimax-m2.7"}, {"operation_model": None},
    {"required_capabilities": ("text",)}, {"required_capabilities": ("text", "tools", "image")},
])
async def test_owner_snapshot_must_equal_canonical_run_pins_before_any_work(registry, change):
    module, binding, authority, _, _, state, _ = registry
    state["admission"] = replace(state["admission"], **change)
    with pytest.raises(ApiError) as denied:
        await invoke(module, binding, "model.prepare", {})
    assert denied.value.code == "model_registry_authority_unbound"
    assert not state["counted"] and not state["transports"] and not state["sent"]
    assert authority.run(binding.operation_id)["spent_dispatches"] == 0


async def test_awaited_count_cannot_change_the_proven_http_body_or_headers(registry):
    module, binding, _, _, route, state, _ = registry
    entered, release = asyncio.Event(), asyncio.Event()
    original = state["evidence"].counter

    async def count(body, manifest):
        entered.set()
        await release.wait()
        return await original(body, manifest)

    state["evidence"] = replace(state["evidence"], counter=count)
    plan = await prepare(module, binding)
    envelope, body = wire(route)
    task = asyncio.create_task(invoke(module, binding, "model.dispatch",
        {"dispatch_id": plan["dispatch_id"], "serialized_request": envelope}))
    await asyncio.wait_for(entered.wait(), 2)
    envelope["body_base64"] = base64.b64encode(body.replace(b"CKD", b"AKI")).decode()
    envelope["headers"]["content-length"] = str(len(body))
    release.set()
    await task
    assert state["counted"] == state["sent"] == [body]


async def test_created_transport_is_closed_even_if_gateway_refuses_before_client_start(registry):
    module, binding, authority, _, route, state, settings = registry

    def factory(actual):
        owner = settings["http_transport"](actual)
        authority.revoke("purpose:explain")
        return owner

    scoped = HarnessModelRegistry(module.manager, authority, **{**settings, "http_transport": factory})
    plan = await prepare(scoped, binding)
    envelope, _ = wire(route)
    with pytest.raises(ApiError) as denied:
        await invoke(scoped, binding, "model.dispatch",
            {"dispatch_id": plan["dispatch_id"], "serialized_request": envelope})
    assert denied.value.code == "authority_revoked"
    assert len(state["transports"]) == 1 and state["transports"][0].closed
    assert not state["sent"] and authority.run(binding.operation_id)["spent_dispatches"] == 0
    assert (await scoped.close(0)).state == "settled"


async def test_factory_cannot_reuse_a_disposed_owner_for_a_native_continuation(registry):
    module, binding, authority, _, route, state, settings = registry
    cached = []

    def factory(actual):
        if not cached:
            cached.append(settings["http_transport"](actual))
        return cached[0]

    scoped = HarnessModelRegistry(module.manager, authority, **{**settings, "http_transport": factory})
    for turn in range(2):
        plan = await prepare(scoped, binding, turn)
        envelope, _ = wire(route, turn)
        if turn == 0:
            await invoke(scoped, binding, "model.dispatch",
                {"dispatch_id": plan["dispatch_id"], "serialized_request": envelope})
        else:
            with pytest.raises(ApiError) as denied:
                await invoke(scoped, binding, "model.dispatch",
                    {"dispatch_id": plan["dispatch_id"], "serialized_request": envelope})
            assert denied.value.code == "model_registry_transport_reused"
    assert authority.run(binding.operation_id)["spent_dispatches"] == len(state["sent"]) == 1
    await scoped.close(0)


@pytest.mark.parametrize("fault", ["missing", "counter", "count", "limits", "capabilities"])
async def test_unknown_evidence_never_allocates_http_or_debits(registry, fault):
    module, binding, authority, _, route, state, _ = registry
    if fault == "missing":
        state["evidence"] = None
    elif fault == "counter":
        state["evidence"] = replace(state["evidence"], counter=None)
    elif fault == "limits":
        state["evidence"] = replace(state["evidence"], limits=RouteLimits())
    elif fault == "capabilities":
        state["evidence"] = replace(state["evidence"], capabilities=("text",))
    else:
        async def unknown(body, manifest):
            return None
        state["evidence"] = replace(state["evidence"], counter=unknown)
    with pytest.raises(ApiError):
        plan = await prepare(module, binding)
        envelope, _ = wire(route)
        await invoke(module, binding, "model.dispatch",
            {"dispatch_id": plan["dispatch_id"], "serialized_request": envelope})
    assert not state["transports"] and not state["sent"]
    assert authority.run(binding.operation_id)["spent_dispatches"] == 0


async def test_close_and_repeated_caller_cancellation_retain_actual_counter_settlement(registry):
    module, binding, authority, _, route, state, _ = registry
    entered, finalized = asyncio.Event(), asyncio.Event()
    release, cpu_settled = threading.Event(), threading.Event()
    loop = asyncio.get_running_loop()

    def cpu_count():
        try:
            loop.call_soon_threadsafe(entered.set)
            release.wait()
            return 20
        finally:
            cpu_settled.set()

    async def count(body, manifest):
        try:
            return await asyncio.to_thread(cpu_count)
        finally:
            finalized.set()

    state["evidence"] = replace(state["evidence"], counter=count)
    plan = await prepare(module, binding)
    actual = request(binding, "model.dispatch", {"dispatch_id": plan["dispatch_id"],
        "serialized_request": wire(route)[0]})
    grant = await module.authorize(actual)
    task = asyncio.create_task(grant.handler(actual, DomainCancellation()))
    try:
        await asyncio.wait_for(entered.wait(), 2)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        closed = await module.close(0)
        assert closed.state == "closing" and closed.owned == 1
        assert (await module.settlement(0)).owned == 1
        assert not finalized.is_set() and not cpu_settled.is_set() and not task.done()
        with pytest.raises(DomainCancelled):
            grant.check_current()
    finally:
        release.set()
        try:
            await task
        except asyncio.CancelledError:
            pass
    assert task.cancelled()
    assert finalized.is_set() and cpu_settled.is_set() and (await module.settlement(0)).state == "settled"
    assert not state["transports"] and authority.run(binding.operation_id)["spent_dispatches"] == 0


@pytest.mark.parametrize("cancel_observer", [False, True])
async def test_revoked_http_retains_transport_finalizer_and_sanitizes_guard_error(registry, cancel_observer):
    module, binding, authority, _, route, state, settings = registry
    entered, closing, release = asyncio.Event(), asyncio.Event(), asyncio.Event()

    class HeldTransport(OwnedTransport):
        async def handle_async_request(self, actual):
            state["sent"].append(actual.content)
            entered.set()
            await asyncio.Event().wait()

        async def aclose(self):
            closing.set()
            await release.wait()
            await super().aclose()

    def factory(actual):
        owner = HeldTransport(state)
        state["transports"].append(owner)
        return owner

    scoped = HarnessModelRegistry(module.manager, authority, **{**settings, "http_transport": factory})
    plan = await prepare(scoped, binding)
    task = asyncio.create_task(invoke(scoped, binding, "model.dispatch",
        {"dispatch_id": plan["dispatch_id"], "serialized_request": wire(route)[0]}))
    await asyncio.wait_for(entered.wait(), 2)
    state["error"] = ApiError("memory_support_budget", "SYNTHETIC_PRIVATE_GUARD_CANARY", 409, False)
    await asyncio.wait_for(closing.wait(), 2)
    if cancel_observer:
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
    assert scoped.status().owned == 1 and not task.done()
    assert not state["transports"][0].closed
    release.set()
    if cancel_observer:
        with pytest.raises(asyncio.CancelledError):
            await task
    else:
        with pytest.raises(ApiError) as denied:
            await task
        assert (denied.value.code, denied.value.status, denied.value.retryable) == (
            "memory_support_budget", 409, False)
        assert "CANARY" not in str(denied.value)
    assert state["transports"][0].closed and scoped.status().owned == 0
    assert authority.run(binding.operation_id)["spent_dispatches"] == len(state["sent"]) == 1
    state.pop("error")
    with pytest.raises(ApiError):
        await invoke(scoped, binding, "model.prepare", {})
    await scoped.close(0)


@pytest.mark.parametrize("code,status,retryable", [
    ("memory_support_budget", 409, False), ("memory_answer_resolver_unavailable", 503, True),
])
@pytest.mark.parametrize("phase", ["before_work", "queued", "replay"])
async def test_authenticated_callback_rechecks_sanitized_error_on_work_publication_and_replay(
        registry, code, status, retryable, phase):
    module, binding, authority, _, route, state, _ = registry
    plan = await prepare(module, binding)
    entered, release, delivered = asyncio.Event(), asyncio.Event(), asyncio.Event()
    wires = []
    identity = {"profile_id": "synthetic_profile", "store_id": "synthetic_store",
        "generation": "synthetic_generation", "token": "synthetic_private_token"}

    async def send(wire_, callback_id):
        entered.set()
        await release.wait()
        wires.append(json.loads(callbacks.publication_wire(callback_id)))
        delivered.set()

    callbacks = DomainCallbacks(identity, module.authorize, send, max_inflight=1,
        max_records=4, max_bytes=500000, max_frame=65536)
    actual = request(binding, "model.dispatch", {"dispatch_id": plan["dispatch_id"],
        "serialized_request": wire(route)[0]})
    frame = {**identity, **binding.__dict__, "kind": "domain_request", "callback_id": actual.callback_id,
        "command": actual.command, "payload": actual.payload}
    error = ApiError(code, "SYNTHETIC_PRIVATE_CHECK_PAYLOAD_CANARY", status, retryable)
    if phase == "before_work":
        state["error"] = error
    callbacks.accept(frame)
    await asyncio.wait_for(entered.wait(), 2)
    if phase == "queued":
        state["error"] = error
    release.set()
    await asyncio.wait_for(delivered.wait(), 2)
    if phase == "replay":
        assert wires[-1]["outcome"] == "committed_reference"
        state["error"] = error
        delivered.clear()
        callbacks.accept(frame)
        await asyncio.wait_for(delivered.wait(), 2)
    assert wires[-1]["outcome"] == "uncertain_after_disconnect"
    assert wires[-1]["error"] == {"code": code, "status": status, "retryable": retryable}
    assert "CANARY" not in json.dumps(wires)
    assert "result" not in wires[-1]
    assert authority.run(binding.operation_id)["spent_dispatches"] == (0 if phase == "before_work" else 1)
    assert len(state["sent"]) == (0 if phase == "before_work" else 1)


async def test_owner_may_issue_equivalent_snapshot_with_a_new_local_current_closure(registry):
    module, binding, _, _, route, state, _ = registry
    plan = await invoke(module, binding, "model.prepare", {})
    original = state["admission"].current
    state["admission"] = replace(state["admission"], current=lambda *, conn=None: original(conn=conn))
    await invoke(module, binding, "model.manifest", {"manifest": native()})
    await invoke(module, binding, "model.dispatch",
        {"dispatch_id": plan["dispatch_id"], "serialized_request": wire(route)[0]})
    assert len(state["sent"]) == 1


async def test_close_and_release_keep_held_success_grants_closed_after_payload_discard(registry):
    module, binding, authority, _, route, state, _ = registry
    plan = await prepare(module, binding)
    actual = request(binding, "model.dispatch", {"dispatch_id": plan["dispatch_id"],
        "serialized_request": wire(route)[0]})
    grant = await module.authorize(actual)
    await grant.handler(actual, DomainCancellation())
    assert module.status().receipts[0].body_bytes == len(state["sent"][0])
    assert module.status().retained_bytes < 8192
    assert grant.check_current() is True
    with pytest.raises(ApiError):
        module.release(binding)
    assert (await module.close(0)).state == "settled"
    with pytest.raises(DomainCancelled):
        grant.check_current()
    authority.settle_run(binding.operation_id)
    module.release(binding)
    assert module.status().runs == module.status().retained_bytes == 0
    with pytest.raises(DomainCancelled):
        grant.check_current()
    with pytest.raises(DomainCancelled):
        await grant.handler(actual, DomainCancellation())


async def test_failed_proof_discards_payload_reservation_and_cannot_be_retried(registry):
    module, binding, authority, _, route, state, _ = registry
    plan = await prepare(module, binding)
    envelope, body = wire(route)
    envelope["body_base64"] = base64.b64encode(body.replace(b"CKD", b"AKI")).decode()
    with pytest.raises(ApiError) as denied:
        await invoke(module, binding, "model.dispatch",
            {"dispatch_id": plan["dispatch_id"], "serialized_request": envelope})
    assert denied.value.code == "deployment_manifest_mismatch"
    assert module.status().retained_bytes < 8192
    with pytest.raises(ApiError):
        await invoke(module, binding, "model.prepare", {})
    with authority.db.transaction() as conn, pytest.raises(ApiError):
        module.require_publication(binding, conn=conn)
    assert not state["counted"] and not state["transports"] and not state["sent"]


@pytest.mark.parametrize("change", [
    {"max_retained_bytes": 1}, {"max_manifest_bytes": 1}, {"max_frame_bytes": 1},
])
async def test_explicit_byte_capacity_denies_before_counter_factory_or_debit(registry, change):
    module, binding, authority, _, route, state, settings = registry
    scoped = HarnessModelRegistry(module.manager, authority, **{**settings, "bounds": replace(BOUNDS, **change)})
    with pytest.raises(ApiError):
        plan = await prepare(scoped, binding)
        await invoke(scoped, binding, "model.dispatch",
            {"dispatch_id": plan["dispatch_id"], "serialized_request": wire(route)[0]})
    assert not state["counted"] and not state["transports"] and not state["sent"]
    assert authority.run(binding.operation_id)["spent_dispatches"] == 0
    await scoped.close(0)


async def test_cancel_is_idempotent_before_first_preparation_and_never_creates_a_plan(registry):
    module, binding, authority, _, _, state, _ = registry
    module.cancel(binding)
    module.cancel(binding)
    with pytest.raises(DomainCancelled):
        await invoke(module, binding, "model.prepare", {})
    assert module.status().plans == 0
    assert not state["transports"] and authority.run(binding.operation_id)["spent_dispatches"] == 0


async def test_unknown_evidence_cannot_refresh_an_expired_pinned_codex_connection(app_paths):
    reference = str(uuid4())
    ConnectionStore(app_paths.root, app_paths.state).save({"version": 1, "host_id": "synthetic_host",
        "selected_provider": "codex", "selected_models": {"codex": "gpt-6.1-sol"},
        "connections": {"codex": {"client_id": "synthetic_client", "access_token": uuid4().hex,
            "refresh_token": uuid4().hex, "expires_at": 1}}, "credential_metadata": {
            "codex": {"reference": reference, "epoch": 0, "authentication_required": False}}})
    calls = []

    def no_refresh(request_):
        calls.append(str(request_.url))
        return httpx.Response(503)

    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(no_refresh))
    authority = ConfigurationAuthority(Database(app_paths.state / "expired-registry.sqlite"))
    connection = ConnectionReference(provider="codex", credential_reference=reference,
        credential_revision=0, selected_model="gpt-6.1-sol")
    spec = ConfigurationSpec(connection=connection, registry_hash="a" * 64, capabilities=("text",))
    version = authority.stage(spec)
    authority.validate(version, lambda candidate: CandidateHealth(configuration_version=candidate.version,
        grant_epoch=candidate.grant_epoch, registry_hash=candidate.spec.registry_hash))
    authority.activate(version, RestartBoundary(admission_closed=True, runtime_stopped=True,
        domain_settled=True), expected_effective=None)
    authority.open_admission(version, registry_hash=spec.registry_hash, grant_epoch=0)
    binding = DomainBinding("expired_root", "1", "native_session", "native_input", "expired_root")
    # A synthetic canonical pin represents a previously admitted root whose
    # protected credential expired; this does not assert fresh bootstrap health.
    authority.begin_run(binding.operation_id, "explain", capability_scope=("text",),
        operation_model=connection.selected_model)
    admission = ModelRunAuthority(binding, version, "explain", connection.selected_model,
        ("text",), DomainCancellation(), lambda *, conn=None: None)
    module = HarnessModelRegistry(manager, authority, resolve_run=lambda _: admission,
        evidence=lambda _: None, http_transport=lambda _: pytest.fail("Unknown evidence allocated HTTP"),
        gateway_bounds=GATEWAY, bounds=BOUNDS)
    try:
        with pytest.raises(ApiError) as denied:
            await invoke(module, binding, "model.prepare", {})
        assert denied.value.code == "deployment_evidence_unknown"
        assert calls == [] and authority.run(binding.operation_id)["spent_dispatches"] == 0
    finally:
        await module.close(0)
        await manager.close()


@pytest.mark.parametrize("mutation,code", [
    ("evidence", "deployment_evidence_stale"), ("credential", "connection_changed"),
    ("capability", "capability_revoked"), ("budget", "memory_support_budget"),
])
async def test_after_counter_await_rechecks_pins_before_http_factory_or_debit(registry, mutation, code):
    module, binding, authority, manager, route, state, _ = registry
    entered, release = asyncio.Event(), asyncio.Event()

    async def count(body, manifest):
        entered.set()
        await release.wait()
        return 20

    state["evidence"] = replace(state["evidence"], counter=count)
    plan = await prepare(module, binding)
    task = asyncio.create_task(invoke(module, binding, "model.dispatch",
        {"dispatch_id": plan["dispatch_id"], "serialized_request": wire(route)[0]}))
    await asyncio.wait_for(entered.wait(), 2)
    if mutation == "evidence":
        state["evidence"] = replace(state["evidence"], limits_revision="changed_immutable_artifact")
    elif mutation == "credential":
        await manager.connect_go(uuid4().hex, select=True)
    elif mutation == "capability":
        authority.revoke("tools")
    else:
        state["error"] = ApiError(code, "PRIVATE_COUNT_BOUNDARY_CANARY", 409, False)
    release.set()
    with pytest.raises(ApiError) as denied:
        await task
    assert denied.value.code == code and "CANARY" not in str(denied.value)
    assert not state["transports"] and not state["sent"]
    assert authority.run(binding.operation_id)["spent_dispatches"] == 0


async def test_publication_checks_every_consumed_permit_in_supplied_connection(registry):
    module, binding, authority, _, route, state, _ = registry
    for turn in range(3):
        plan = await prepare(module, binding, turn)
        await invoke(module, binding, "model.dispatch",
            {"dispatch_id": plan["dispatch_id"], "serialized_request": wire(route, turn)[0]})
    statements = []
    with authority.db.transaction() as conn:
        conn.set_trace_callback(statements.append)
        module.require_publication(binding, conn=conn)
        assert state["connections"][-1] is conn
    # Actual SQLite execution in the caller's transaction includes every permit
    # check; a root-only check cannot satisfy this observation.
    checks = [statement for statement in statements
        if "SELECT * FROM harness_configuration_attempts WHERE permit_id=" in statement]
    assert len(checks) == 3
    assert all(any(receipt.permit_id in check for check in checks) for receipt in module.status().receipts)
    authority.revoke("tools")
    with authority.db.transaction() as conn, pytest.raises(ApiError) as denied:
        module.require_publication(binding, conn=conn)
    assert denied.value.code == "capability_revoked"


async def test_one_unfinished_plan_and_dedicated_capacity_are_enforced_before_effects(registry):
    module, binding, authority, _, _, state, settings = registry
    plan = await invoke(module, binding, "model.prepare", {})
    with pytest.raises(ApiError):
        await invoke(module, binding, "model.prepare", {})
    await invoke(module, binding, "model.manifest", {"manifest": native()})
    with pytest.raises(ApiError):
        await invoke(module, binding, "model.manifest", {"manifest": native()})
    with pytest.raises(ApiError):
        await invoke(module, binding, "model.dispatch", {"dispatch_id": "another_plan", "serialized_request": {}})
    assert module.status().plans == 1 and module.status().phases[0][1] == plan["dispatch_id"]
    assert not state["counted"] and not state["transports"]
    assert authority.run(binding.operation_id)["spent_dispatches"] == 0
    assert await module.authorize(request(binding, "model.admit_input", {})) is None


@pytest.mark.parametrize("kind", ["child", "auxiliary", "restart"])
async def test_child_auxiliary_and_restart_need_separate_admission(registry, kind):
    module, binding, authority, _, route, state, settings = registry
    if kind == "child":
        authority.begin_child("child_run", binding.operation_id, "explain", capability_scope=CAPS)
        actual = replace(binding, operation_id="child_run", cancellation_id="child_run")
        state["admission"] = replace(state["admission"], binding=actual)
        expected = "model_registry_kind_unavailable"
    elif kind == "auxiliary":
        authority.begin_run("summary_run", "summary", capability_scope=CAPS, operation_model=route.catalog_model_id)
        actual = replace(binding, operation_id="summary_run", cancellation_id="summary_run")
        state["admission"] = replace(state["admission"], binding=actual, purpose="summary")
        expected = "model_registry_kind_unavailable"
    else:
        plan = await prepare(module, binding)
        await invoke(module, binding, "model.dispatch",
            {"dispatch_id": plan["dispatch_id"], "serialized_request": wire(route)[0]})
        module = HarnessModelRegistry(module.manager, authority, **settings)
        actual, expected = binding, "model_registry_recovery_unavailable"
    with pytest.raises(ApiError) as denied:
        await invoke(module, actual, "model.prepare", {})
    assert denied.value.code == expected
    assert len(state["sent"]) == (1 if kind == "restart" else 0)
    if kind == "restart":
        await module.close(0)


async def test_one_canonical_operation_cannot_acquire_a_second_native_input_plan(registry):
    module, binding, authority, _, _, state, _ = registry
    await invoke(module, binding, "model.prepare", {})
    changed = replace(binding, input_id="another_native_input")
    state["admission"] = replace(state["admission"], binding=changed)
    with pytest.raises(ApiError) as denied:
        await invoke(module, changed, "model.prepare", {})
    assert denied.value.code == "model_registry_authority_changed"
    assert module.status().runs == module.status().plans == 1
    assert authority.run(binding.operation_id)["spent_dispatches"] == 0


async def test_close_seals_a_handler_scheduled_before_its_owned_worker_starts(registry):
    module, binding, authority, _, _, state, _ = registry
    actual = request(binding, "model.prepare", {})
    grant = await module.authorize(actual)
    handler = asyncio.create_task(grant.handler(actual, DomainCancellation()))
    closing = asyncio.create_task(module.close(0))
    with pytest.raises(DomainCancelled):
        await handler
    await closing
    assert (await module.settlement(0)).state == "settled"
    assert module.status().plans == module.status().owned == 0
    assert not state["counted"] and not state["transports"] and not state["sent"]
    assert authority.run(binding.operation_id)["spent_dispatches"] == 0


async def test_close_discards_prepared_payload_after_queued_registration_settles(registry):
    module, binding, authority, _, _, state, _ = registry
    await invoke(module, binding, "model.prepare", {})
    actual = request(binding, "model.manifest", {"manifest": native()})
    grant = await module.authorize(actual)
    handler = asyncio.create_task(grant.handler(actual, DomainCancellation()))
    closing = asyncio.create_task(module.close(0))
    with pytest.raises(DomainCancelled):
        await handler
    await closing
    observed = await module.settlement(0)
    assert observed.state == "settled" and observed.owned == 0
    assert observed.phases[0][2] == "cancelled" and observed.retained_bytes < 8192
    assert not state["counted"] and not state["transports"] and not state["sent"]
    assert authority.run(binding.operation_id)["spent_dispatches"] == 0


async def test_retained_evidence_metadata_is_charged_before_preparation_is_published(registry):
    module, binding, authority, _, _, state, _ = registry
    state["evidence"] = replace(state["evidence"], limits_revision="x" * BOUNDS.max_retained_bytes)
    with pytest.raises(ApiError) as denied:
        await invoke(module, binding, "model.prepare", {})
    assert denied.value.code == "model_registry_capacity"
    assert module.status().retained_bytes <= BOUNDS.max_retained_bytes
    assert not state["counted"] and not state["transports"] and not state["sent"]
    assert authority.run(binding.operation_id)["spent_dispatches"] == 0
    assert (await module.close(0)).retained_bytes <= BOUNDS.max_retained_bytes


async def test_consumed_prepare_grant_cannot_allocate_another_continuation_on_replay(registry):
    module, binding, authority, _, route, state, _ = registry
    actual = request(binding, "model.prepare", {})
    grant = await module.authorize(actual)
    plan = await grant.handler(actual, DomainCancellation())
    await invoke(module, binding, "model.manifest", {"manifest": native()})
    await invoke(module, binding, "model.dispatch",
        {"dispatch_id": plan["dispatch_id"], "serialized_request": wire(route)[0]})
    with pytest.raises(ApiError) as denied:
        await grant.handler(actual, DomainCancellation())
    assert denied.value.code == "model_registry_callback_consumed"
    assert module.status().plans == 1
    assert authority.run(binding.operation_id)["spent_dispatches"] == len(state["sent"]) == 1


def test_release_of_unbound_input_reports_only_a_sanitized_authority_error(registry):
    module, binding, _, _, _, _, _ = registry
    unbound = replace(binding, input_id="PRIVATE_UNBOUND_INPUT_CANARY")
    with pytest.raises(ApiError) as denied:
        module.release(unbound)
    assert denied.value.code == "model_registry_authority_unbound"
    assert "CANARY" not in str(denied.value)


async def test_rejected_callback_cannot_discard_another_handlers_active_proof(registry):
    module, binding, authority, _, route, state, settings = registry
    scoped = HarnessModelRegistry(module.manager, authority,
        **{**settings, "bounds": replace(BOUNDS, max_owned=2)})
    entered, release = asyncio.Event(), asyncio.Event()
    counter = state["evidence"].counter

    async def count(body, manifest):
        entered.set()
        await release.wait()
        return await counter(body, manifest)

    state["evidence"] = replace(state["evidence"], counter=count)
    plan = await prepare(scoped, binding)
    task = asyncio.create_task(invoke(scoped, binding, "model.dispatch",
        {"dispatch_id": plan["dispatch_id"], "serialized_request": wire(route)[0]}))
    try:
        await asyncio.wait_for(entered.wait(), 2)
        retained = scoped.status().retained_bytes
        with pytest.raises(ApiError) as denied:
            await invoke(scoped, binding, "model.prepare", {})
        assert denied.value.code == "model_registry_phase_invalid"
        assert scoped.status().phases[0][2] == "proving"
        assert scoped.status().retained_bytes == retained and scoped.status().owned == 1
    finally:
        release.set()
        await task
        await scoped.close(0)
    assert authority.run(binding.operation_id)["spent_dispatches"] == len(state["sent"]) == 1


async def test_binding_observation_isolates_held_worker_and_receipts_without_admitting_unknown(registry):
    module, binding, authority, _, route, state, settings = registry
    other = replace(binding, operation_id="other_learning_run", cancellation_id="other_learning_run",
        session_id="other_session", input_id="other_input")
    authority.begin_run(other.operation_id, "explain", capability_scope=CAPS,
        operation_model=route.catalog_model_id)
    admissions = {binding: state["admission"], other: replace(state["admission"],
        binding=other, cancellation=DomainCancellation())}
    resolved = []

    def resolve(actual):
        resolved.append(actual)
        return admissions.get(actual)

    scoped = HarnessModelRegistry(module.manager, authority, **{**settings, "resolve_run": resolve,
        "bounds": replace(BOUNDS, max_owned=2, max_retained_bytes=400000)})
    entered, release = asyncio.Event(), asyncio.Event()
    counter = state["evidence"].counter
    calls = 0

    async def count(body, manifest):
        nonlocal calls
        calls += 1
        if calls == 1:
            entered.set()
            await release.wait()
        return await counter(body, manifest)

    state["evidence"] = replace(state["evidence"], counter=count)
    first = await prepare(scoped, binding)
    task = asyncio.create_task(invoke(scoped, binding, "model.dispatch",
        {"dispatch_id": first["dispatch_id"], "serialized_request": wire(route)[0]}))
    try:
        await asyncio.wait_for(entered.wait(), 2)
        second = await prepare(scoped, other)
        await invoke(scoped, other, "model.dispatch",
            {"dispatch_id": second["dispatch_id"], "serialized_request": wire(route)[0]})
        resolved_before = list(resolved)
        first_observation, second_observation = scoped.status(binding), scoped.status(other)
        assert first_observation.owned == 1 and first_observation.receipts == ()
        assert first_observation.phases[0][2] == "proving"
        assert second_observation.owned == 0 and len(second_observation.receipts) == 1
        assert second_observation.phases[0][2] == "confirmed"
        assert second_observation.receipts[0].dispatch_id == second["dispatch_id"]
        global_observation = scoped.status()
        assert global_observation.runs == global_observation.plans == 2
        assert global_observation.owned == 1 and len(global_observation.receipts) == 1
        unknown = scoped.status(replace(binding, input_id="unknown_input"))
        assert unknown.runs == unknown.plans == unknown.owned == unknown.retained_bytes == 0
        assert unknown.phases == unknown.receipts == () and resolved == resolved_before
        closed = await scoped.close(0)
        assert closed.state == scoped.status(other).state == "closing"
        assert scoped.status(replace(binding, input_id="unknown_input")).state == "closing"
        assert scoped.status(other).owned == 0 and scoped.status(binding).owned == 1
    finally:
        release.set()
        try:
            await task
        except DomainCancelled:
            pass
        await scoped.close(0)
    assert authority.run(other.operation_id)["spent_dispatches"] == len(state["sent"]) == 1


async def test_oversized_callback_reply_retains_consumed_permit_after_real_transport_settlement(registry):
    module, binding, authority, _, route, state, settings = registry

    class LargeReply(OwnedTransport):
        async def handle_async_request(self, actual):
            await super().handle_async_request(actual)
            payload = b'data: {"choices":[{"delta":{"content":"' + b"x" * 4000 + b'"}}]}\n\ndata: [DONE]\n\n'
            return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=payload)

    def factory(actual):
        owner = LargeReply(state)
        state["transports"].append(owner)
        return owner

    scoped = HarnessModelRegistry(module.manager, authority, **{**settings, "http_transport": factory,
        "bounds": replace(BOUNDS, max_frame_bytes=4096)})
    try:
        plan = await prepare(scoped, binding)
        with pytest.raises(ApiError) as denied:
            await invoke(scoped, binding, "model.dispatch",
                {"dispatch_id": plan["dispatch_id"], "serialized_request": wire(route)[0]})
        assert denied.value.code == "model_registry_capacity"
        observed = scoped.status(binding)
        assert observed.owned == 0 and observed.phases[0][2] == "failed"
        assert len(observed.receipts) == 1 and state["transports"][0].closed
        assert authority.permit(observed.receipts[0].permit_id)["state"] == "confirmed"
        assert authority.run(binding.operation_id)["spent_dispatches"] == len(state["sent"]) == 1
        with pytest.raises(ApiError):
            await invoke(scoped, binding, "model.prepare", {})
    finally:
        await scoped.close(0)
