"""Canonical evidence-review children; public Authority/Registry, synthetic HTTP."""
import asyncio
from dataclasses import dataclass, replace

import pytest

from renulus.contracts import ApiError
from renulus.runtime.harness_domain import DomainCancellation, DomainCancelled, DomainRequest
from renulus.runtime.harness_model_registry import HarnessModelRegistry, ModelRunAuthority

from test_harness_model_registry import CAPS, OwnedTransport, invoke, prepare, registry, wire


@dataclass(repr=False)
class Family:
    module: HarnessModelRegistry
    root: object
    authority: object
    route: object
    state: dict
    admissions: dict
    settings: dict

    def child(self, *, purpose="evidence-review", name="evidence_child", capabilities=CAPS):
        binding = replace(self.root, operation_id=name, session_id=name + "_session",
            input_id=name + "_input", cancellation_id=name)
        with self.authority.db.transaction() as conn:
            canonical = self.authority.begin_child_in(conn, binding.operation_id,
                self.root.operation_id, purpose, capability_scope=capabilities,
                operation_model=self.route.catalog_model_id)
        parent = self.admissions[self.root]

        def current(*, conn=None):
            self.state.setdefault("child_connections", []).append(conn)
            parent.current(conn=conn)
            parent.cancellation.check_current()

        self.admissions[binding] = ModelRunAuthority(binding, canonical["version"], purpose,
            canonical["route"]["model_id"], tuple(canonical["effective_capabilities"]),
            DomainCancellation(), current)
        return binding


@pytest.fixture
async def family(registry):
    _, root, authority, manager, route, state, settings = registry
    state["credential_reads"] = 0
    protected_credential = manager.credential_for_harness

    def credential_for_harness(actual):
        state["credential_reads"] += 1
        return protected_credential(actual)

    manager.credential_for_harness = credential_for_harness
    admissions = {root: state["admission"]}
    settings = {**settings, "resolve_run": admissions.get}
    module = HarnessModelRegistry(manager, authority, **settings)
    yield Family(module, root, authority, route, state, admissions, settings)
    await module.close(1)


async def dispatch(family, binding, turn=0):
    plan = await prepare(family.module, binding, turn)
    result = await invoke(family.module, binding, "model.dispatch",
        {"dispatch_id": plan["dispatch_id"], "serialized_request": wire(family.route, turn)[0]})
    return plan, family.authority.permit(result["permit_id"])


async def test_root_then_evidence_child_and_continuation_share_durable_budget(family):
    root_plan, root_permit = await dispatch(family, family.root)
    assert root_plan["request_kind"] == root_permit["request_kind"] == "primary"
    child = family.child()
    child_plan, child_permit = await dispatch(family, child)
    continuation, continued_permit = await dispatch(family, child, 1)

    assert child_plan["request_kind"] == child_permit["request_kind"] == "child"
    assert child_plan["role"]["purpose"] == child_permit["dispatch_purpose"] == "evidence-review"
    assert "continuation_of" not in child_plan
    assert continuation["request_kind"] == continued_permit["request_kind"] == "tool-continuation"
    assert continuation["continuation_of"] == child_permit["permit_id"]
    assert continued_permit["dispatch_purpose"] == "evidence-review"
    assert len({root_permit["permit_id"], child_permit["permit_id"], continued_permit["permit_id"]}) == 3
    assert family.authority.run(family.root.operation_id)["spent_dispatches"] == 3
    assert family.authority.run(child.operation_id)["own_spent_dispatches"] == 2
    assert family.authority.run(family.root.operation_id)["own_spent_dispatches"] == 1
    assert len(family.state["sent"]) == 3
    assert all(owner.closed for owner in family.state["transports"])
    with family.authority.db.transaction() as conn:
        family.module.require_publication(child, conn=conn)
        assert family.state["child_connections"][-1] is conn
        family.module.require_publication(family.root, conn=conn)
    assert family.authority.run(child.operation_id)["state"] == "active"
    assert family.module.status().owned == 0


@pytest.mark.parametrize("purpose", ["explain", "summary", "memory-extraction"])
async def test_child_denies_other_canonical_purposes_before_credentials(family, purpose):
    child = family.child(purpose=purpose)
    with pytest.raises(ApiError) as denied:
        await invoke(family.module, child, "model.prepare", {})
    assert denied.value.code == "model_registry_kind_unavailable"
    assert family.module.status().runs == family.module.status().plans == 0
    assert family.state["credential_reads"] == 0 and not family.state["sent"]
    assert not family.state["transports"] and not family.state["counted"]
    assert family.authority.run(child.operation_id)["own_spent_dispatches"] == 0


@pytest.mark.parametrize("pin,value", [
    ("configuration_version", "f" * 64),
    ("operation_model", "deepseek-v4.1-flash"),
    ("required_capabilities", ("text",)),
])
async def test_child_denies_mismatched_trusted_pins_without_effect(family, pin, value):
    child = family.child()
    family.admissions[child] = replace(family.admissions[child], **{pin: value})
    with pytest.raises(ApiError) as denied:
        await invoke(family.module, child, "model.prepare", {})
    assert denied.value.code == "model_registry_authority_unbound"
    assert family.module.status().runs == 0 and family.state["credential_reads"] == 0
    assert not family.state["sent"] and not family.state["transports"]
    assert family.authority.run(child.operation_id)["own_spent_dispatches"] == 0


async def test_child_model_payload_cannot_override_trusted_purpose_model_or_scope(family):
    child = family.child()
    with pytest.raises(ApiError) as denied:
        await invoke(family.module, child, "model.prepare", {
            "purpose": "explain", "model_id": "deepseek-v4.1-flash",
            "required_capabilities": ["text", "tools", "image"],
        })
    assert denied.value.code == "model_registry_payload_invalid"
    assert family.module.status().plans == 0 and family.state["credential_reads"] == 0
    assert not family.state["sent"] and not family.state["transports"]
    assert family.authority.run(child.operation_id)["own_spent_dispatches"] == 0


async def test_child_unknown_evidence_denies_before_credentials_or_http(family):
    child = family.child()
    family.state["evidence"] = None
    with pytest.raises(ApiError) as denied:
        await invoke(family.module, child, "model.prepare", {})
    assert denied.value.code == "deployment_evidence_unknown"
    assert family.state["credential_reads"] == 0 and not family.state["transports"]
    assert not family.state["sent"] and not family.state["counted"]
    assert not family.module.status(child).receipts
    assert family.authority.run(child.operation_id)["own_spent_dispatches"] == 0
    with family.authority.db.transaction() as conn, pytest.raises(ApiError):
        family.module.require_publication(child, conn=conn)


async def test_fresh_registry_admits_unspent_child_but_cannot_recover_its_spent_attempt(family):
    await dispatch(family, family.root)
    child = family.child()
    fresh = HarnessModelRegistry(family.module.manager, family.authority, **family.settings)
    reopened = HarnessModelRegistry(family.module.manager, family.authority, **family.settings)
    try:
        plan, permit = await dispatch(replace(family, module=fresh), child)
        assert plan["request_kind"] == permit["request_kind"] == "child"
        assert family.authority.run(child.operation_id)["spent_dispatches"] == 2
        assert family.authority.run(child.operation_id)["own_spent_dispatches"] == 1
        credential_reads = family.state["credential_reads"]
        with pytest.raises(ApiError) as denied:
            await invoke(reopened, child, "model.prepare", {})
        assert denied.value.code == "model_registry_recovery_unavailable"
        assert reopened.status().runs == reopened.status().plans == 0
        assert family.state["credential_reads"] == credential_reads
        assert len(family.state["sent"]) == 2
    finally:
        await fresh.close(1)
        await reopened.close(1)


async def test_child_continuations_cannot_escape_shared_root_exhaustion(family):
    await dispatch(family, family.root)
    child = family.child()
    for turn in range(3):
        await dispatch(family, child, turn)
    credential_reads = family.state["credential_reads"]
    with pytest.raises(ApiError) as denied:
        await dispatch(family, child, 3)
    assert denied.value.code == "dispatch_budget_exhausted"
    assert family.authority.run(child.operation_id)["spent_dispatches"] == 4
    assert family.authority.run(child.operation_id)["own_spent_dispatches"] == 3
    assert family.authority.run(family.root.operation_id)["own_spent_dispatches"] == 1
    assert len(family.state["sent"]) == 4
    assert family.state["credential_reads"] == credential_reads
    assert all(owner.closed for owner in family.state["transports"])
    assert family.module.status().owned == 0
    with pytest.raises(ApiError) as replay:
        await invoke(family.module, child, "model.prepare", {})
    assert replay.value.code == "model_registry_phase_invalid"


@pytest.mark.parametrize("revocation,code", [
    ("purpose:explain", "authority_revoked"),
    ("model:mimo-v2.6-pro", "authority_revoked"),
    ("connection", "authority_revoked"),
    ("tools", "capability_revoked"),
])
async def test_held_child_dispatch_rechecks_ancestor_authority(family, revocation, code):
    child = family.child()
    plan = await prepare(family.module, child)
    request = DomainRequest("held_child_dispatch", child, "model.dispatch", {
        "dispatch_id": plan["dispatch_id"], "serialized_request": wire(family.route)[0],
    })
    grant = await family.module.authorize(request)
    if revocation == "connection":
        revocation += ":" + family.route.credential_ref
    family.authority.revoke(revocation)
    with pytest.raises(ApiError) as denied:
        await grant.handler(request, DomainCancellation())
    assert denied.value.code == code
    assert family.state["credential_reads"] == 0 and not family.state["sent"]
    assert not family.state["transports"] and family.module.status().owned == 0
    assert family.authority.run(child.operation_id)["own_spent_dispatches"] == 0


async def test_child_publication_guards_every_permit_and_retained_current_closure(family, monkeypatch):
    child = family.child()
    _, first = await dispatch(family, child)
    _, second = await dispatch(family, child, 1)
    observations = []
    canonical_current = family.authority.require_current

    def require_current(run_id, **kwargs):
        observations.append((run_id, kwargs.get("permit_id"), kwargs.get("conn")))
        return canonical_current(run_id, **kwargs)

    monkeypatch.setattr(family.authority, "require_current", require_current)
    with family.authority.db.transaction() as conn:
        family.module.require_publication(child, conn=conn)
        assert {(run_id, permit_id) for run_id, permit_id, _ in observations if permit_id} == {
            (child.operation_id, first["permit_id"]),
            (child.operation_id, second["permit_id"]),
        }
        assert all(connection is conn for _, _, connection in observations)
        assert family.state["child_connections"][-1] is conn
        assert family.state["connections"][-1] is conn
        family.state["error"] = ApiError("source_revoked", "Synthetic local eligibility denied", 409)
        with pytest.raises(ApiError) as denied:
            family.module.require_publication(child, conn=conn)
        assert denied.value.code == "source_revoked"
    family.state.pop("error")
    family.authority.revoke("purpose:explain")
    with family.authority.db.transaction() as conn, pytest.raises(ApiError) as revoked:
        family.module.require_publication(child, conn=conn)
    assert revoked.value.code == "authority_revoked"
    assert family.authority.run(child.operation_id)["state"] == "active"
    assert len(family.state["sent"]) == 2 and family.module.status(child).owned == 0


async def test_parent_cancel_retains_child_transport_until_actual_finalizer_settles(family):
    child = family.child()
    entered, released = asyncio.Event(), asyncio.Event()

    class HoldingTransport(OwnedTransport):
        async def aclose(self):
            entered.set()
            await released.wait()
            await super().aclose()

    def transport(_):
        owner = HoldingTransport(family.state)
        family.state["transports"].append(owner)
        return owner

    scoped = HarnessModelRegistry(family.module.manager, family.authority,
        **{**family.settings, "http_transport": transport})
    task = None
    try:
        plan = await prepare(scoped, child)
        task = asyncio.create_task(invoke(scoped, child, "model.dispatch", {
            "dispatch_id": plan["dispatch_id"], "serialized_request": wire(family.route)[0],
        }))
        await asyncio.wait_for(entered.wait(), 2)
        assert scoped.status(child).owned == 1 and not scoped.status(child).receipts
        family.admissions[family.root].cancellation.cancel()
        with family.authority.db.transaction() as conn, pytest.raises(DomainCancelled):
            scoped.require_publication(child, conn=conn)
        task.cancel()  # Cancelling the observer cannot abandon the HTTP owner.
        closing = await scoped.close(0)
        assert closing.state == "closing" and closing.owned == 1 and closing.retained_bytes > 0
        assert not task.done() and not family.state["transports"][0].closed
        with pytest.raises(ApiError) as pending:
            scoped.release(child)
        assert pending.value.code == "model_registry_settlement_pending"
        released.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 2)
        assert (await scoped.settlement(1)).state == "settled"
        assert family.state["transports"][0].closed and not scoped.status(child).receipts
        assert family.authority.run(child.operation_id)["own_spent_dispatches"] == 1
        assert len(family.state["sent"]) == 1
    finally:
        released.set()
        if task is not None:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await scoped.close(1)


async def test_child_receipts_stay_active_for_root_publication_then_release_leaf_first(family):
    await dispatch(family, family.root)
    child = family.child()
    _, permit = await dispatch(family, child)
    request = DomainRequest("retained_child_grant", child, "model.prepare", {})
    held = await family.module.authorize(request)
    with pytest.raises(ApiError) as pending:
        family.module.release(child)
    assert pending.value.code == "model_registry_settlement_pending"
    with pytest.raises(ApiError) as root_pending:
        family.authority.settle_run(family.root.operation_id)
    assert root_pending.value.code == "run_not_settled"
    with family.authority.db.transaction() as conn:
        family.module.require_publication(child, conn=conn)
        family.module.require_publication(family.root, conn=conn)
    assert family.authority.run(child.operation_id)["state"] == "active"
    assert family.module.status(child).receipts[0].permit_id == permit["permit_id"]
    family.authority.settle_run(child.operation_id)
    family.module.release(child)
    assert family.authority.permit(permit["permit_id"])["state"] == "confirmed"
    assert family.authority.run(child.operation_id)["state"] == "settled"
    assert family.module.status().runs == 1 and family.module.status(child).receipts == ()
    with pytest.raises(DomainCancelled):
        await held.handler(request, DomainCancellation())
    family.authority.settle_run(family.root.operation_id)
    family.module.release(family.root)
    assert family.module.status().runs == 0 and family.module.status().receipts == ()
    assert len(family.state["sent"]) == 2
