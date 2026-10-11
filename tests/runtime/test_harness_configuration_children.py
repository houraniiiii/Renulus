"""H07 child policy admission through public Authority and canonical SQLite.

Health/restart flags are synthetic setup, not native child or settlement proof.
No registry, provider transport, native SDK or engine is loaded by this slice.
"""

from contextlib import closing

import pytest

from renulus.contracts import ApiError
from renulus.runtime.harness_configuration import (
    AttemptPolicy,
    CandidateHealth,
    ConfigurationAuthority,
    ConfigurationSpec,
    ConnectionReference,
    RestartBoundary,
    RolePolicy,
    RouteLimits,
)
from renulus.storage.database import Database


CONNECTION = ConnectionReference(
    provider="opencode-go", credential_reference="synthetic-child-connection",
    credential_revision=1, selected_model="mimo-v2.6-pro",
)
LIMITS = RouteLimits(input_tokens=8192, output_tokens=2048, window_tokens=10240)
PAYLOAD_HASH = "b" * 64


def configured_authority(tmp_path, *, root_limit=4, child_limit=2, child_enabled=True):
    authority = ConfigurationAuthority(Database(tmp_path / "canonical.sqlite"))
    spec = ConfigurationSpec(
        connection=CONNECTION, registry_hash="a" * 64,
        capabilities=("library-read", "memory-read"),
        roles=(
            RolePolicy(purpose="explain", output_tokens=3072, dispatch_limit=root_limit),
            RolePolicy(purpose="evidence-review", model_id="deepseek-v4.1-flash",
                       output_tokens=1024, dispatch_limit=child_limit, enabled=child_enabled),
        ),
        attempts=AttemptPolicy(foreground_dispatches=root_limit),
    )
    version = authority.stage(spec)
    assert authority.validate(version, lambda candidate: CandidateHealth(
        configuration_version=candidate.version, grant_epoch=candidate.grant_epoch,
        registry_hash=candidate.spec.registry_hash,
    ))
    authority.activate(version, RestartBoundary(
        admission_closed=True, runtime_stopped=True, domain_settled=True,
    ), expected_effective=None)
    authority.open_admission(version, registry_hash=spec.registry_hash, grant_epoch=0)
    return authority, spec, version


def test_supplied_transaction_admits_parent_and_configured_child_atomically(tmp_path):
    authority, _, version = configured_authority(tmp_path)
    with authority.db.transaction() as conn:
        authority.begin_run_in(conn, "parent", "explain", expected_version=version,
                               capability_scope=("library-read",))
        child = authority.begin_child_in(conn, "child", "parent", "evidence-review",
                                         capability_scope=("library-read",))
        assert child["version"] == version
        assert child["root_id"] == child["parent_id"] == "parent"
        assert child["purpose"] == "evidence-review"
        assert child["effective_capabilities"] == ["library-read"]
        assert child["route"]["model_id"] == "deepseek-v4.1-flash"
        assert child["route"]["output_tokens"] == 1024
        assert child["dispatch_limit"] == 2
    assert authority.run("child") == child
    assert authority.run("parent")["state"] == "active"


def reserve(authority, run_id, step_id):
    return authority.admit(run_id, step_id, payload_hash=PAYLOAD_HASH, request_kind="primary",
                           connection=CONNECTION, limits=LIMITS, input_tokens=100)


def mark_dispatched(authority, permit):
    return authority.mark_dispatched(permit["permit_id"], connection=CONNECTION, limits=LIMITS,
                                     input_tokens=100, payload_hash=PAYLOAD_HASH)


@pytest.mark.parametrize("state", [
    "reserved", "dispatched", "confirmed", "failed", "uncertain", "cancelled_before_send",
])
def test_own_dispatch_count_excludes_root_and_sibling_debits_in_every_state(tmp_path, state):
    authority, _, _ = configured_authority(tmp_path)
    authority.begin_run("parent", "explain")
    reserve(authority, "parent", "root-step")
    child = authority.begin_child("child", "parent", "evidence-review")
    authority.begin_child("sibling", "parent", "evidence-review")
    assert child["spent_dispatches"] == 1
    assert child["own_spent_dispatches"] == 0

    permit = reserve(authority, "child", "child-step")
    if state not in {"reserved", "cancelled_before_send"}:
        mark_dispatched(authority, permit)
    if state not in {"reserved", "dispatched"}:
        authority.complete(permit["permit_id"], state)
    authority = ConfigurationAuthority(Database(tmp_path / "canonical.sqlite"))
    assert authority.permit(permit["permit_id"])["state"] == state
    for run_id, own_spent in (("parent", 1), ("child", 1), ("sibling", 0)):
        projection = authority.run(run_id)
        assert projection["spent_dispatches"] == 2
        assert projection["own_spent_dispatches"] == own_spent


@pytest.mark.parametrize("revoked", [
    "purpose:explain", "model:mimo-v2.6-pro", "connection:synthetic-child-connection",
    "purpose:evidence-review", "model:deepseek-v4.1-flash",
])
def test_child_admission_rechecks_parent_and_child_revocations_without_partial_insert(tmp_path, revoked):
    authority, _, _ = configured_authority(tmp_path)
    authority.begin_run("parent", "explain", capability_scope=("library-read",))
    authority.revoke(revoked)
    with authority.db.transaction() as conn:
        with pytest.raises(ApiError) as error:
            authority.begin_child_in(conn, "denied", "parent", "evidence-review",
                                     capability_scope=("library-read",))
        assert error.value.code == "authority_revoked"
    with pytest.raises(ApiError) as missing:
        authority.run("denied")
    assert missing.value.code == "run_missing"
    with pytest.raises(ApiError) as delegated:
        authority.begin_child("also-denied", "parent", "evidence-review")
    assert delegated.value.code == "authority_revoked"


def test_child_and_uncommitted_parent_roll_back_with_outer_publication(tmp_path):
    authority, _, version = configured_authority(tmp_path)
    with pytest.raises(RuntimeError, match="synthetic publication refused"):
        with authority.db.transaction() as conn:
            authority.begin_run_in(conn, "parent", "explain", expected_version=version)
            authority.begin_child_in(conn, "child", "parent", "evidence-review")
            raise RuntimeError("synthetic publication refused")
    for run_id in ("parent", "child"):
        with pytest.raises(ApiError) as missing:
            authority.run(run_id)
        assert missing.value.code == "run_missing"


@pytest.mark.parametrize("connection_state,expected", [
    ("inactive", "configuration_transaction_required"),
    ("ended", "configuration_transaction_required"),
    ("closed", "configuration_transaction_required"),
    ("foreign", "configuration_connection_mismatch"),
])
def test_child_requires_an_active_transaction_on_the_same_database(tmp_path, connection_state, expected):
    authority, _, _ = configured_authority(tmp_path)
    authority.begin_run("parent", "explain")
    owner = authority
    if connection_state == "foreign":
        owner, _, _ = configured_authority(tmp_path / "foreign")
        owner.begin_run("parent", "explain")
    with closing(owner.db.connect()) as conn:
        if connection_state != "inactive":
            conn.execute("BEGIN IMMEDIATE")
        if connection_state == "ended":
            conn.commit()
        elif connection_state == "closed":
            conn.close()
        with pytest.raises(ApiError) as error:
            authority.begin_child_in(conn, "child", "parent", "evidence-review")
        assert error.value.code == expected
    with pytest.raises(ApiError) as missing:
        authority.run("child")
    assert missing.value.code == "run_missing"


def test_independent_supplied_connection_needs_no_second_writer_admission(tmp_path):
    authority, _, version = configured_authority(tmp_path)
    with closing(authority.db.connect()) as conn:
        conn.execute("BEGIN IMMEDIATE")
        # Public quiescence refuses any new managed writer. The already-owned
        # caller transaction can still admit and project its root and child.
        with authority.db.quiesce_writes():
            authority.begin_run_in(conn, "parent", "explain", expected_version=version)
            child = authority.begin_child_in(conn, "child", "parent", "evidence-review")
        conn.commit()
    assert authority.run("child") == child


@pytest.mark.parametrize("parent_state", ["missing", "settled"])
def test_child_requires_an_active_parent(tmp_path, parent_state):
    authority, _, _ = configured_authority(tmp_path)
    if parent_state == "settled":
        authority.begin_run("parent", "explain")
        authority.settle_run("parent")  # Synthetic policy owner has no native work.
    with authority.db.transaction() as conn:
        with pytest.raises(ApiError) as error:
            authority.begin_child_in(conn, "child", "parent", "evidence-review")
        assert error.value.code == "parent_unavailable"


def test_child_depth_and_concurrency_include_uncommitted_children(tmp_path):
    authority, _, _ = configured_authority(tmp_path)
    authority.begin_run("parent", "explain")
    with authority.db.transaction() as conn:
        authority.begin_child_in(conn, "first", "parent", "evidence-review")
        authority.begin_child_in(conn, "second", "parent", "evidence-review")
        with pytest.raises(ApiError) as concurrent:
            authority.begin_child_in(conn, "third", "parent", "evidence-review")
        assert concurrent.value.code == "child_concurrency_exhausted"
        with pytest.raises(ApiError) as depth:
            authority.begin_child_in(conn, "grandchild", "first", "evidence-review")
        assert depth.value.code == "child_depth_exhausted"
    for denied in ("third", "grandchild"):
        with pytest.raises(ApiError) as missing:
            authority.run(denied)
        assert missing.value.code == "run_missing"
    authority.settle_run("first")  # Only policy ownership exists in this fixture.
    assert authority.begin_child("third", "parent", "evidence-review")["parent_id"] == "parent"


def test_child_scope_intersects_current_parent_and_ancestor_revocations(tmp_path):
    authority, _, _ = configured_authority(tmp_path)
    scope = ("library-read", "memory-read")
    authority.begin_run("parent", "explain", capability_scope=scope)
    authority.begin_child("existing", "parent", "evidence-review", capability_scope=scope)
    authority.revoke("memory-read")
    assert authority.require_current("existing")["effective_capabilities"] == ["library-read"]
    with authority.db.transaction() as conn:
        with pytest.raises(ApiError) as wide:
            authority.begin_child_in(conn, "wide", "parent", "evidence-review",
                                     capability_scope=("memory-read",))
        assert wide.value.code == "scope_widening"
        narrow = authority.begin_child_in(conn, "narrow", "parent", "evidence-review",
                                          capability_scope=("library-read",))
    assert narrow["effective_capabilities"] == ["library-read"]
    with pytest.raises(ApiError) as revoked:
        authority.require_current("existing", required_capabilities=("memory-read",))
    assert revoked.value.code == "capability_revoked"
    authority.revoke("purpose:explain")
    with authority.db.transaction() as conn:
        with pytest.raises(ApiError) as ancestor:
            authority.begin_child_in(conn, "grandchild", "existing", "evidence-review")
        assert ancestor.value.code == "authority_revoked"


def test_child_uses_parent_immutable_configuration_while_a_new_spec_is_requested(tmp_path):
    authority, spec, version = configured_authority(tmp_path)
    authority.begin_run("parent", "explain")
    requested = authority.stage(spec.model_copy(update={
        "roles": (RolePolicy(purpose="evidence-review", model_id="mimo-v2.6-pro",
                             output_tokens=64, dispatch_limit=0),),
    }))
    child = authority.begin_child("child", "parent", "evidence-review")
    assert requested != version
    assert child["version"] == version
    assert child["route"]["model_id"] == "deepseek-v4.1-flash"
    assert child["route"]["output_tokens"] == 1024
    assert child["dispatch_limit"] == 2


@pytest.mark.parametrize("model,enabled,error_code", [
    ("mimo-v2.6-pro", True, None),
    ("gpt-6.1-sol", True, "model_not_allowed"),
    ("mimo-v2.6-pro", False, "role_disabled"),
])
def test_child_preserves_allowed_override_and_disabled_role_precedence(tmp_path, model, enabled, error_code):
    authority, _, _ = configured_authority(tmp_path, child_enabled=enabled)
    authority.begin_run("parent", "explain")
    with authority.db.transaction() as conn:
        if error_code:
            with pytest.raises(ApiError) as error:
                authority.begin_child_in(conn, "child", "parent", "evidence-review",
                                         operation_model=model)
            assert error.value.code == error_code
        else:
            child = authority.begin_child_in(conn, "child", "parent", "evidence-review",
                                             operation_model=model)
            assert child["route"]["model_id"] == "mimo-v2.6-pro"
            assert child["route"]["output_tokens"] == 1024
            assert child["dispatch_limit"] == 2


@pytest.mark.parametrize("root_limit,child_limit", [(3, 4), (5, 2)])
def test_child_own_counts_do_not_refund_or_bypass_shared_root_and_purpose_budgets(
    tmp_path, root_limit, child_limit,
):
    authority, _, _ = configured_authority(tmp_path, root_limit=root_limit, child_limit=child_limit)
    authority.begin_run("parent", "explain")
    root_permit = reserve(authority, "parent", "root-step")
    mark_dispatched(authority, root_permit)
    authority.complete(root_permit["permit_id"], "confirmed")
    authority.begin_child("first", "parent", "evidence-review")
    authority.begin_child("second", "parent", "evidence-review")
    cancelled = reserve(authority, "first", "cancelled-step")
    authority.complete(cancelled["permit_id"], "cancelled_before_send")
    second = reserve(authority, "second", "second-step")
    mark_dispatched(authority, second)
    authority.complete(second["permit_id"], "confirmed")
    authority = ConfigurationAuthority(Database(tmp_path / "canonical.sqlite"))
    for run_id in ("parent", "first", "second"):
        projection = authority.run(run_id)
        assert projection["spent_dispatches"] == 3
        assert projection["own_spent_dispatches"] == 1
    with pytest.raises(ApiError) as exhausted:
        reserve(authority, "first", "over-budget")
    assert exhausted.value.code == "dispatch_budget_exhausted"
    assert authority.run("first")["own_spent_dispatches"] == 1
    if root_limit == 5:
        # Purpose is exhausted with root allowance still available.
        reserve(authority, "parent", "remaining-root-step")
        assert authority.run("parent")["own_spent_dispatches"] == 2
        assert authority.run("first")["spent_dispatches"] == 4
