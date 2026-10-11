# SPDX-License-Identifier: MIT
"""Canonical policy settlement shares the caller's commit/rollback boundary."""
from contextlib import closing

import pytest

from renulus.contracts import ApiError
from renulus.runtime.harness_configuration import ConfigurationAuthority
from renulus.storage.database import Database
from test_harness_configuration import activate, configured


def test_settlement_is_rolled_back_or_committed_with_the_caller_transaction(configured):
    authority, _, _, _, _ = configured
    before = authority.begin_run("atomic-settlement", "explain")
    snapshot = authority.activation_snapshot()
    with pytest.raises(RuntimeError, match="publication rejected"):
        with authority.db.transaction() as conn:
            assert authority.settle_run_in(conn, "atomic-settlement") is None
            with pytest.raises(ApiError) as settled:
                authority.require_current("atomic-settlement", conn=conn)
            assert settled.value.code == "run_unavailable"
            assert conn.in_transaction
            raise RuntimeError("publication rejected")
    assert authority.run("atomic-settlement") == before
    assert authority.activation_snapshot() == snapshot
    with authority.db.transaction() as conn:
        assert authority.settle_run_in(conn, "atomic-settlement") is None
        assert conn.in_transaction
    assert authority.run("atomic-settlement") == {**before, "state": "settled"}
    assert authority.activation_snapshot() == {**snapshot, "pinned_runs": []}


def test_parent_settles_only_after_each_active_direct_child(configured):
    authority, _, _, _, _ = configured
    authority.begin_run("root", "explain")
    authority.begin_child("first-child", "root", "evidence-review")
    authority.begin_child("second-child", "root", "evidence-review")
    with authority.db.transaction() as conn:
        with pytest.raises(ApiError) as active_children:
            authority.settle_run_in(conn, "root")
        assert active_children.value.code == "run_not_settled"
        authority.settle_run_in(conn, "first-child")
        with pytest.raises(ApiError) as active_sibling:
            authority.settle_run_in(conn, "root")
        assert active_sibling.value.code == "run_not_settled"
        authority.settle_run_in(conn, "second-child")
        authority.settle_run_in(conn, "root")
    assert all(authority.run(run_id)["state"] == "settled"
        for run_id in ("first-child", "second-child", "root"))
    assert authority.activation_snapshot()["pinned_runs"] == []


@pytest.mark.parametrize("attempt_state", ["reserved", "dispatched"])
def test_unresolved_permit_blocks_settlement_without_changing_ownership(configured, attempt_state):
    authority, _, _, connection, limits = configured
    authority.begin_run("unresolved", "explain")
    permit = authority.admit("unresolved", "primary", payload_hash="1" * 64,
        request_kind="primary", connection=connection, limits=limits, input_tokens=100)
    if attempt_state == "dispatched":
        authority.mark_dispatched(permit["permit_id"], connection=connection,
            limits=limits, input_tokens=100, payload_hash="1" * 64)
    before, retained = authority.run("unresolved"), authority.permit(permit["permit_id"])
    snapshot = authority.activation_snapshot()
    with authority.db.transaction() as conn:
        with pytest.raises(ApiError) as unresolved:
            authority.settle_run_in(conn, "unresolved")
        assert unresolved.value.code == "run_not_settled"
    assert authority.run("unresolved") == before
    assert authority.permit(permit["permit_id"]) == retained
    assert authority.activation_snapshot() == snapshot
    outcome = "confirmed" if attempt_state == "dispatched" else "cancelled_before_send"
    authority.complete(permit["permit_id"], outcome)
    with authority.db.transaction() as conn:
        authority.settle_run_in(conn, "unresolved")
    assert authority.run("unresolved")["state"] == "settled"
    assert authority.run("unresolved")["spent_dispatches"] == before["spent_dispatches"] == 1


def test_repeated_settlement_and_compatible_wrapper_preserve_debits_and_revocation(configured):
    authority, _, _, connection, limits = configured
    authority.begin_run("charged", "explain", capability_scope=("library-read",))
    permit = authority.admit("charged", "primary", payload_hash="2" * 64,
        request_kind="primary", connection=connection, limits=limits, input_tokens=100)
    authority.mark_dispatched(permit["permit_id"], connection=connection,
        limits=limits, input_tokens=100, payload_hash="2" * 64)
    authority.complete(permit["permit_id"], "confirmed", result_reference="retained-answer")
    authority.revoke("library-read")
    before, retained = authority.run("charged"), authority.permit(permit["permit_id"])
    snapshot = authority.activation_snapshot()
    with authority.db.transaction() as conn:
        assert authority.settle_run_in(conn, "charged") is None
        assert authority.settle_run_in(conn, "charged") is None
    assert authority.settle_run("charged") is None
    assert authority.run("charged") == {**before, "state": "settled"}
    assert authority.run("charged")["spent_dispatches"] == 1
    assert authority.permit(permit["permit_id"]) == retained
    assert authority.activation_snapshot() == {**snapshot, "pinned_runs": []}
    assert authority.revocation_overlay() == {"epoch": 1, "revoked": ["library-read"]}


@pytest.mark.parametrize("ended", [False, True], ids=["no-transaction", "ended-transaction"])
def test_settlement_rejects_a_connection_without_an_active_transaction(configured, ended):
    authority, _, _, _, _ = configured
    before = authority.begin_run("unowned", "explain")
    if ended:
        with authority.db.transaction() as conn:
            pass
        with pytest.raises(ApiError) as invalid:
            authority.settle_run_in(conn, "unowned")
    else:
        with closing(authority.db.connect()) as conn:
            with pytest.raises(ApiError) as invalid:
                authority.settle_run_in(conn, "unowned")
            assert not conn.in_transaction
    assert invalid.value.code == "configuration_transaction_required"
    assert authority.run("unowned") == before


def test_foreign_transaction_cannot_settle_either_same_named_run(configured, tmp_path):
    authority, spec, _, _, _ = configured
    foreign = ConfigurationAuthority(Database(tmp_path / "foreign.sqlite"))
    activate(foreign, spec)
    before = authority.begin_run("same-name", "explain")
    foreign_before = foreign.begin_run("same-name", "explain")
    with foreign.db.transaction() as conn:
        with pytest.raises(ApiError) as invalid:
            authority.settle_run_in(conn, "same-name")
        assert invalid.value.code == "configuration_connection_mismatch"
        assert conn.in_transaction
    assert authority.run("same-name") == before
    assert foreign.run("same-name") == foreign_before


def test_an_independent_connection_to_the_canonical_database_can_settle(configured):
    authority, _, _, _, _ = configured
    before = authority.begin_run("same-database", "explain")
    canonical = Database(authority.db.path)
    with canonical.transaction() as conn:
        authority.settle_run_in(conn, "same-database")
    assert authority.run("same-database") == {**before, "state": "settled"}


def test_settlement_of_a_missing_run_preserves_existing_pins(configured):
    authority, _, _, _, _ = configured
    authority.begin_run("retained", "explain")
    snapshot = authority.activation_snapshot()
    with authority.db.transaction() as conn:
        with pytest.raises(ApiError) as missing:
            authority.settle_run_in(conn, "missing")
        assert missing.value.code == "run_missing"
    assert authority.activation_snapshot() == snapshot
