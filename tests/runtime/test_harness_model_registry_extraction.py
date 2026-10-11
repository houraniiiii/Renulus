"""Standalone extraction through the real Registry/Authority/Manager public ports."""
import asyncio
import base64
from dataclasses import replace
import hashlib
import json
from uuid import uuid4

import httpx
import pytest

from renulus.contracts import ApiError
from renulus.runtime.harness_configuration import (
    CandidateHealth, ConfigurationAuthority, ConfigurationSpec, ConnectionReference,
    RestartBoundary, RolePolicy, RouteLimits,
)
from renulus.runtime.harness_deployment import DeploymentEvidence
from renulus.runtime.harness_domain import DomainBinding, DomainCancellation, DomainCancelled, DomainRequest
from renulus.runtime.harness_gateway import GatewayBounds
from renulus.runtime.harness_model_registry import HarnessModelRegistry, ModelRegistryBounds, ModelRunAuthority
from renulus.runtime.manager import ProviderManager
from renulus.storage.database import Database


SYSTEM = "Extract eligible synthetic learning facts."
USER = "Committed synthetic CKD answer."
LIMITS = RouteLimits(input_tokens=100, output_tokens=32, window_tokens=150)


@pytest.fixture
async def extraction(app_paths, request):
    options = getattr(request, "param", {})
    caps = options.get("caps", ("text",))
    purpose = options.get("purpose", "memory-extraction")
    state = {"sent": [], "counted": [], "transports": [], "connections": [], "credentials": 0}
    credential = uuid4().hex
    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(
        lambda _: httpx.Response(200, json={"data": [{"id": "mimo-v2.6-pro"}]})))
    await manager.connect_go(credential, select=True)
    route = await manager.prepare_harness_route("mimo-v2.6-pro")
    authority = ConfigurationAuthority(Database(app_paths.state / "extraction.sqlite"))
    spec = ConfigurationSpec(connection=ConnectionReference(provider=route.provider_id,
        credential_reference=route.credential_ref, credential_revision=route.credential_epoch,
        selected_model=route.catalog_model_id), registry_hash="a" * 64, capabilities=caps,
        roles=(RolePolicy(purpose=purpose, output_tokens=32, dispatch_limit=options.get("limit", 1)),))
    version = authority.stage(spec)
    assert authority.validate(version, lambda candidate: CandidateHealth(configuration_version=candidate.version,
        grant_epoch=candidate.grant_epoch, registry_hash=candidate.spec.registry_hash))
    authority.activate(version, RestartBoundary(admission_closed=True, runtime_stopped=True,
        domain_settled=True), expected_effective=None)
    authority.open_admission(version, registry_hash=spec.registry_hash, grant_epoch=0)
    binding = DomainBinding("memory_extract", "1", "stateless_operation", "eligible_publication", "memory_extract")
    authority.begin_run(binding.operation_id, purpose, capability_scope=caps, operation_model=route.catalog_model_id)

    def current(*, conn=None):
        state["connections"].append(conn)
        if state.get("error"):
            raise state["error"]

    state["admission"] = ModelRunAuthority(binding, version, purpose, route.catalog_model_id,
        caps, DomainCancellation(), current)

    async def count(body, manifest):
        state["counted"].append(body)
        return 20  # Explicit synthetic inclusive counter; no production token claim.

    state["evidence"] = DeploymentEvidence("synthetic_exact_extraction", route, LIMITS, caps,
        "synthetic_limits", "synthetic_caps", "synthetic_inclusive_counter", count)
    actual_credential = manager.credential_for_harness

    def credential_for_harness(actual):
        state["credentials"] += 1
        return actual_credential(actual)

    manager.credential_for_harness = credential_for_harness

    class Transport(httpx.AsyncBaseTransport):
        def __init__(self):
            self.closed = False

        async def handle_async_request(self, request_):
            if self.closed or request_.headers["authorization"] != "Bearer " + credential:
                raise RuntimeError("Synthetic protected transport mismatch")
            state["sent"].append(request_.content)
            return httpx.Response(200, headers={"content-type": "text/event-stream"},
                content=b'data: {"choices":[{"delta":{"content":"Synthetic fact"}}]}\n\ndata: [DONE]\n\n')

        async def aclose(self):
            assert not self.closed, "Synthetic transport was finalized twice"
            if state.get("close_entered"):
                state["close_entered"].set()
                await state["close_release"].wait()
            self.closed = True

    def transport(actual):
        assert replace(actual, catalogue_listed=None) == replace(route, catalogue_listed=None)
        owner = Transport()
        state["transports"].append(owner)
        return owner

    settings = dict(resolve_run=lambda _: state["admission"], evidence=lambda _: state["evidence"],
        http_transport=transport, gateway_bounds=GatewayBounds(
            max_request_bytes=8192, max_response_bytes=8192, timeout_seconds=2),
        bounds=ModelRegistryBounds(max_runs=2, max_plans_per_run=4, max_owned=1,
            max_retained_bytes=200000, max_manifest_bytes=32768, max_frame_bytes=65536))
    module = HarnessModelRegistry(manager, authority, **settings)
    yield module, binding, authority, manager, route, state, settings
    await module.close(1)
    await manager.close()


async def invoke(module, binding, command, payload):
    request = DomainRequest(uuid4().hex, binding, command, payload)
    grant = await module.authorize(request)
    assert grant is not None and grant.check_current() is True
    return await grant.handler(request, DomainCancellation())


def manifest():
    return {"version": 1, "system": SYSTEM, "messages": [
        {"role": "user", "content": [{"type": "text", "text": USER}]}], "tools": []}


def wire(route):
    body = json.dumps({"model": route.wire_model_id, "stream": True, "max_completion_tokens": 32,
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": USER}]}).encode()
    return {"method": "POST", "url": route.endpoint, "headers": {"content-type": "application/json"},
        "body_base64": base64.b64encode(body).decode()}, body


async def test_extraction_owns_one_primary_permit_and_supplied_connection_publication(extraction):
    module, binding, authority, _, route, state, _ = extraction
    plan = await invoke(module, binding, "model.prepare", {})
    assert plan["role"]["purpose"] == "memory-extraction" and plan["role"]["dispatch_limit"] == 1
    assert plan["native_capabilities"] == {"tools": False, "input": ["text"], "output": ["text"]}
    assert plan["request_kind"] == "primary" and "continuation_of" not in plan
    assert state["credentials"] == 0
    with authority.db.transaction() as conn, pytest.raises(ApiError, match="unavailable"):
        module.require_publication(binding, conn=conn)
    await invoke(module, binding, "model.manifest", {"manifest": manifest()})
    envelope, body = wire(route)
    result = await invoke(module, binding, "model.dispatch",
        {"dispatch_id": plan["dispatch_id"], "serialized_request": envelope})
    permit = authority.permit(result["permit_id"])
    assert permit["state"] == "confirmed" and permit["dispatch_purpose"] == "memory-extraction"
    assert permit["request_kind"] == "primary" and permit["payload_hash"] == hashlib.sha256(body).hexdigest()
    assert state["sent"] == state["counted"] == [body]
    assert len(state["transports"]) == 1 and state["transports"][0].closed
    assert authority.run(binding.operation_id)["spent_dispatches"] == 1
    with authority.db.transaction() as conn:
        module.require_publication(binding, conn=conn)
        assert state["connections"][-1] is conn
    assert module.status().owned == 0 and len(module.status().receipts) == 1
    with pytest.raises(ApiError) as denied:
        await invoke(module, binding, "model.prepare", {})
    assert denied.value.code == "model_registry_capacity"
    assert len(state["sent"]) == 1
    authority.settle_run(binding.operation_id)
    module.release(binding)
    assert module.status().runs == 0


@pytest.mark.parametrize("extraction", [
    {"limit": 2}, {"limit": 0}, {"caps": ("text", "tools")}, {"caps": ("text", "image")},
], indirect=True)
async def test_extraction_denies_wider_canonical_policy_before_evidence_or_credentials(extraction):
    module, binding, authority, _, _, state, _ = extraction
    with pytest.raises(ApiError) as denied:
        await invoke(module, binding, "model.prepare", {})
    assert denied.value.code == "model_registry_kind_unavailable"
    assert not state["sent"] and not state["transports"] and not state["counted"]
    assert state["credentials"] == 0 and module.status().plans == 0
    assert authority.run(binding.operation_id)["spent_dispatches"] == 0


async def test_extraction_unknown_evidence_denies_without_credentials_or_http(extraction):
    module, binding, authority, _, _, state, _ = extraction
    state["evidence"] = None
    with pytest.raises(ApiError) as denied:
        await invoke(module, binding, "model.prepare", {})
    assert denied.value.code == "deployment_evidence_unknown"
    assert state["credentials"] == 0 and not state["transports"] and not state["sent"]
    assert not module.status().receipts and authority.run(binding.operation_id)["spent_dispatches"] == 0
    with authority.db.transaction() as conn, pytest.raises(ApiError):
        module.require_publication(binding, conn=conn)


async def test_extraction_missing_manifest_and_replayed_callback_cannot_publish(extraction):
    module, binding, authority, _, route, state, _ = extraction
    plan = await invoke(module, binding, "model.prepare", {})
    payload = {"dispatch_id": plan["dispatch_id"], "serialized_request": wire(route)[0]}
    with pytest.raises(ApiError) as denied:
        await invoke(module, binding, "model.dispatch", payload)
    assert denied.value.code == "model_registry_phase_invalid"
    assert not state["sent"] and state["credentials"] == 0
    await invoke(module, binding, "model.manifest", {"manifest": manifest()})
    await invoke(module, binding, "model.dispatch", payload)
    with pytest.raises(ApiError) as denied:
        await invoke(module, binding, "model.dispatch", payload)
    assert denied.value.code == "model_registry_phase_invalid" and len(state["sent"]) == 1
    assert authority.run(binding.operation_id)["spent_dispatches"] == 1


async def test_fresh_registry_does_not_recover_a_spent_extraction_run(extraction):
    module, binding, authority, manager, route, state, settings = extraction
    plan = await invoke(module, binding, "model.prepare", {})
    await invoke(module, binding, "model.manifest", {"manifest": manifest()})
    await invoke(module, binding, "model.dispatch",
        {"dispatch_id": plan["dispatch_id"], "serialized_request": wire(route)[0]})
    reopened = HarnessModelRegistry(manager, authority, **settings)
    try:
        with pytest.raises(ApiError) as denied:
            await invoke(reopened, binding, "model.prepare", {})
        assert denied.value.code == "model_registry_recovery_unavailable"
        assert reopened.status().plans == 0 and len(state["sent"]) == 1
    finally:
        await reopened.close(0)


@pytest.mark.parametrize("extraction", [{"purpose": "compaction"}, {"purpose": "summary"}, {"purpose": "title"}], indirect=True)
async def test_extraction_extension_does_not_admit_other_auxiliary_roots(extraction):
    module, binding, _, _, _, state, _ = extraction
    with pytest.raises(ApiError) as denied:
        await invoke(module, binding, "model.prepare", {})
    assert denied.value.code == "model_registry_kind_unavailable"
    assert state["credentials"] == 0 and not state["transports"]


async def test_extraction_child_is_denied_even_with_matching_text_policy(extraction):
    module, binding, authority, _, route, state, _ = extraction
    child = replace(binding, operation_id="child_extract", cancellation_id="child_extract")
    authority.begin_child(child.operation_id, binding.operation_id, "memory-extraction",
        capability_scope=("text",), operation_model=route.catalog_model_id)
    state["admission"] = replace(state["admission"], binding=child)
    with pytest.raises(ApiError) as denied:
        await invoke(module, child, "model.prepare", {})
    assert denied.value.code == "model_registry_kind_unavailable"
    assert state["credentials"] == 0 and not state["transports"]


async def test_extraction_cancel_retains_actual_transport_finalizer_before_settlement(extraction):
    module, binding, authority, _, route, state, _ = extraction
    state["close_entered"], state["close_release"] = asyncio.Event(), asyncio.Event()
    plan = await invoke(module, binding, "model.prepare", {})
    await invoke(module, binding, "model.manifest", {"manifest": manifest()})
    task = asyncio.create_task(invoke(module, binding, "model.dispatch",
        {"dispatch_id": plan["dispatch_id"], "serialized_request": wire(route)[0]}))
    try:
        await asyncio.wait_for(state["close_entered"].wait(), 2)
        assert module.status().owned == 1 and not module.status().receipts
        module.cancel(binding)
        task.cancel()  # Observer cancellation cannot abandon the underlying worker.
        closing = await module.close(0)
        assert closing.state == "closing" and closing.owned == 1 and closing.retained_bytes > 0
        assert not state["transports"][0].closed and not task.done()
        with authority.db.transaction() as conn, pytest.raises(DomainCancelled):
            module.require_publication(binding, conn=conn)
        state["close_release"].set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 2)
        assert (await module.settlement(1)).state == "settled" and module.status().owned == 0
        assert state["transports"][0].closed and not module.status().receipts
        assert authority.run(binding.operation_id)["spent_dispatches"] == 1 and len(state["sent"]) == 1
    finally:
        state["close_release"].set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
