"""H04 behavior through the canonical configuration, role and permit interface."""
from renulus.storage.database import Database
import pytest
from renulus.contracts import ApiError
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier
import subprocess
import sys
import types

from renulus.runtime.harness_configuration import (
    ConfigurationAuthority, ConfigurationSpec, ConnectionReference, RouteLimits, RolePolicy,
    CandidateHealth, RestartBoundary, AttemptPolicy,
)

ROLE_FIXTURES = json.loads((Path(__file__).parent / "fixtures" / "harness_roles.json").read_text())


@pytest.mark.parametrize("fixture", ROLE_FIXTURES, ids=lambda value: value["purpose"])
@pytest.mark.parametrize("provider,selected", [
    ("codex", "gpt-6.1-sol"), ("codex", "gpt-6-astra"), ("codex", "gpt-6-luna"),
    ("opencode-go", "mimo-v2.6-pro"), ("opencode-go", "deepseek-v4.1-flash")])
def test_role_fixture_inherits_exact_user_selection_without_quality_ranking(tmp_path, fixture, provider, selected):
    authority = ConfigurationAuthority(Database(tmp_path / "canonical.sqlite"))
    connection = ConnectionReference(provider=provider, credential_reference="synthetic-connection",
                                     credential_revision=7, selected_model=selected)
    inherited = authority.stage(ConfigurationSpec(connection=connection, registry_hash="a" * 64))
    explicit = authority.stage(ConfigurationSpec(connection=connection, registry_hash="a" * 64,
        roles=(RolePolicy(purpose=fixture["purpose"], model_id=selected),)))
    for version in (inherited, explicit):
        binding = authority.resolve_role(version, fixture["purpose"], catalogue=())
        assert binding.model_id == selected
        assert binding.dispatch_limit == fixture["dispatches"]
        assert binding.output_tokens == 4096
        assert binding.connection.credential_revision == 7


@pytest.mark.parametrize("catalogue,expected", [
    (("deepseek-v4.1-flash", "mimo-v2.6-pro"), "mimo-v2.6-pro"),
    (("unapproved", "deepseek-v4.1-flash"), "deepseek-v4.1-flash"),
    ((), "mimo-v2.6-pro"), (("gpt-6.1-sol",), "mimo-v2.6-pro")])
def test_automatic_uses_allowlist_order_filtered_by_catalogue_membership(tmp_path, catalogue, expected):
    authority = ConfigurationAuthority(Database(tmp_path / "canonical.sqlite"))
    version = authority.stage(ConfigurationSpec(connection=ConnectionReference(provider="opencode-go",
        credential_reference="connection-go", credential_revision=1), registry_hash="a" * 64))
    assert authority.resolve_role(version, "explain", catalogue=catalogue).model_id == expected


def test_authorized_override_precedence_and_subscription_rejection(tmp_path):
    authority = ConfigurationAuthority(Database(tmp_path / "canonical.sqlite"))
    version = authority.stage(ConfigurationSpec(connection=ConnectionReference(provider="codex",
        credential_reference="connection-codex", credential_revision=1, selected_model="gpt-6-luna"),
        roles=(RolePolicy(purpose="explain", model_id="gpt-6-astra"),), registry_hash="a" * 64))
    assert authority.resolve_role(version, "explain", parent_model="gpt-6.1-sol").model_id == "gpt-6-astra"
    assert authority.resolve_role(version, "explain", parent_model="gpt-6-luna",
                                  operation_model="gpt-6.1-sol").model_id == "gpt-6.1-sol"
    assert authority.resolve_role(version, "case-discuss", parent_model="gpt-6-astra").model_id == "gpt-6-astra"
    with pytest.raises(ApiError) as error:
        authority.resolve_role(version, "explain", operation_model="mimo-v2.6-pro")
    assert error.value.code == "model_not_allowed"


@pytest.fixture
def configured(tmp_path):
    authority = ConfigurationAuthority(Database(tmp_path / "canonical.sqlite"))
    connection = ConnectionReference(provider="opencode-go", credential_reference="connection-go",
                                     credential_revision=1)
    spec = ConfigurationSpec(connection=connection, registry_hash="a" * 64,
                             capabilities=("library-read",))
    version = activate(authority, spec)
    limits = RouteLimits(input_tokens=8192, output_tokens=2048, window_tokens=10240)
    return authority, spec, version, connection, limits


@pytest.fixture(scope="module")
def pre004_module():
    """Create upgrade fixtures through the previously committed public authority."""
    root = Path(__file__).resolve().parents[2]
    path = "runtime/renulus/runtime/harness_configuration.py"
    # This blob is shared by lane 22c52fa1 and integrated a85e1ee0. No lane commit is needed.
    source = subprocess.check_output(["git", "cat-file", "blob",
        "fe17e466f6de7b5392a06eea272a29b4509539af"], cwd=root, text=True)
    module = types.ModuleType("renulus.runtime._h04_pre004")
    module.__package__ = "renulus.runtime"
    module.__file__ = str(root / path)
    sys.modules[module.__name__] = module
    try:
        exec(compile(source, module.__file__, "exec"), module.__dict__)
        yield module
    finally:
        del sys.modules[module.__name__]


@pytest.fixture
def pre004_configured(tmp_path, pre004_module):
    module = pre004_module
    authority = module.ConfigurationAuthority(Database(tmp_path / "pre004.sqlite"))
    connection = module.ConnectionReference(provider="opencode-go",
        credential_reference="connection-go", credential_revision=1)
    spec = module.ConfigurationSpec(connection=connection, registry_hash="a" * 64,
        roles=(module.RolePolicy(purpose="title", dispatch_limit=1),
               module.RolePolicy(purpose="summary", dispatch_limit=0)),
        attempts=module.AttemptPolicy(retries=1, retryable_errors=("transport_unavailable",)))
    version = authority.stage(spec)
    assert authority.validate(version, lambda candidate: module.CandidateHealth(
        configuration_version=candidate.version, grant_epoch=candidate.grant_epoch,
        registry_hash=candidate.spec.registry_hash))
    authority.activate(version, module.RestartBoundary(admission_closed=True, runtime_stopped=True,
        domain_settled=True), expected_effective=None)
    authority.open_admission(version, registry_hash=spec.registry_hash, grant_epoch=0)
    limits = RouteLimits(input_tokens=8192, output_tokens=2048, window_tokens=10240)
    return authority, connection, limits


def test_upgrade_confirmed_receipt_replays_without_dispatch_or_lock(pre004_configured):
    previous, connection, limits = pre004_configured
    previous.begin_run("foreground", "explain")
    first = previous.admit("foreground", "title", payload_hash="1" * 64,
        request_kind="title", connection=connection, limits=limits, input_tokens=100)
    previous.mark_dispatched(first["permit_id"], connection=connection, limits=limits,
        input_tokens=100, payload_hash="1" * 64)
    previous.complete(first["permit_id"], "confirmed", result_reference="saved-title")
    upgraded = ConfigurationAuthority(previous.db)
    receipt = upgraded.admit("foreground", "title", payload_hash="1" * 64,
        request_kind="title", connection=connection, limits=limits, input_tokens=100)
    assert receipt["permit_id"] == first["permit_id"]
    assert receipt["dispatch_purpose"] == "title"
    assert receipt["result_reference"] == "saved-title"
    assert receipt["dispatch_allowed"] is False
    assert upgraded.run("foreground")["spent_dispatches"] == 1


@pytest.mark.parametrize("purpose,limit", [("title", 1), ("summary", 0)])
def test_upgrade_rejects_historical_reservations_beyond_purpose_budget(pre004_configured, purpose, limit):
    previous, connection, limits = pre004_configured
    previous.begin_run("foreground", "explain")
    permits = [previous.admit("foreground", "auxiliary-" + str(index), payload_hash="1" * 64,
        request_kind=purpose, connection=connection, limits=limits, input_tokens=100)
        for index in range(limit + 1)]
    upgraded = ConfigurationAuthority(previous.db)
    with pytest.raises(ApiError) as error:
        upgraded.mark_dispatched(permits[-1]["permit_id"], connection=connection, limits=limits,
            input_tokens=100, payload_hash="1" * 64)
    assert error.value.code == "dispatch_budget_exhausted"
    assert upgraded.permit(permits[-1]["permit_id"])["state"] == "reserved"
    if limit:
        allowed = upgraded.mark_dispatched(permits[0]["permit_id"], connection=connection, limits=limits,
            input_tokens=100, payload_hash="1" * 64)
        assert allowed["dispatch_allowed"] is True
    assert upgraded.run("foreground")["spent_dispatches"] == limit + 1


def test_one_permit_summary_does_not_receive_free_precompaction(configured):
    authority, spec, version, connection, limits = configured
    authority.begin_run("summary", "summary")
    with pytest.raises(ApiError) as error:
        authority.admit("summary", "first", payload_hash="1" * 64, request_kind="summary",
                        connection=connection, limits=limits, input_tokens=8193)
    assert error.value.code == "request_does_not_fit"
    assert authority.run("summary")["spent_dispatches"] == 0
    authority.admit("summary", "first", payload_hash="1" * 64, request_kind="summary",
                    connection=connection, limits=limits, input_tokens=100)
    with pytest.raises(ApiError) as error:
        authority.admit("summary", "second", payload_hash="2" * 64, request_kind="compaction",
                        connection=connection, limits=limits, input_tokens=100)
    assert error.value.code == "dispatch_budget_exhausted"


def test_titles_degrade_deterministically_and_zero_cap_prevents_auxiliary_dispatch(configured):
    authority, spec, version, connection, limits = configured
    with pytest.raises(ApiError) as error:
        authority.begin_run("title", "title", operation_model="mimo-v2.6-pro")
    assert error.value.code == "role_disabled"
    new = activate(authority, spec.model_copy(update={"roles": (RolePolicy(purpose="title"),)}), expected=version)
    authority.begin_run("title-parent", "explain")
    with pytest.raises(ApiError) as error:
        authority.admit("title-parent", "title", payload_hash="1" * 64, request_kind="title",
                        connection=connection, limits=limits, input_tokens=100)
    assert error.value.code == "dispatch_budget_exhausted"
    assert authority.run("title-parent")["spent_dispatches"] == 0


@pytest.mark.parametrize("purpose,limit", [("title", 1), ("summary", 0)])
def test_auxiliary_role_budget_applies_inside_foreground_allowance(configured, purpose, limit):
    authority, spec, version, connection, limits = configured
    activate(authority, spec.model_copy(update={"roles": (RolePolicy(purpose=purpose, dispatch_limit=limit),)}), expected=version)
    authority.begin_run("foreground", "explain")
    for index in range(limit):
        authority.admit("foreground", "auxiliary-" + str(index), payload_hash="1" * 64,
            request_kind=purpose, connection=connection, limits=limits, input_tokens=100)
    with pytest.raises(ApiError) as error:
        authority.admit("foreground", "over-limit", payload_hash="2" * 64,
            request_kind=purpose, connection=connection, limits=limits, input_tokens=100)
    assert error.value.code == "dispatch_budget_exhausted"
    assert authority.run("foreground")["spent_dispatches"] == limit
    authority.admit("foreground", "primary", payload_hash="3" * 64,
        request_kind="primary", connection=connection, limits=limits, input_tokens=100)
    assert authority.run("foreground")["spent_dispatches"] == limit + 1


@pytest.mark.parametrize("limit", [1, 2])
def test_relabelled_retry_keeps_original_purpose_budget(configured, limit):
    authority, spec, version, connection, limits = configured
    activate(authority, spec.model_copy(update={
        "roles": (RolePolicy(purpose="title", dispatch_limit=limit),),
        "attempts": AttemptPolicy(retries=1, retryable_errors=("transport_unavailable",)),
    }), expected=version)
    authority.begin_run("foreground", "explain")
    first = authority.admit("foreground", "title", payload_hash="1" * 64,
        request_kind="title", connection=connection, limits=limits, input_tokens=100)
    authority.mark_dispatched(first["permit_id"], connection=connection, limits=limits,
        input_tokens=100, payload_hash="1" * 64)
    authority.complete(first["permit_id"], "failed", failure_code="transport_unavailable")
    if limit == 1:
        with pytest.raises(ApiError) as error:
            authority.admit("foreground", "title", payload_hash="1" * 64,
                request_kind="transport-fallback", connection=connection, limits=limits,
                input_tokens=100, retry_of=first["permit_id"])
    else:
        retried = authority.admit("foreground", "title", payload_hash="1" * 64,
            request_kind="transport-fallback", connection=connection, limits=limits,
            input_tokens=100, retry_of=first["permit_id"])
        assert retried["retry_number"] == 1
        with pytest.raises(ApiError) as error:
            authority.admit("foreground", "another-title", payload_hash="2" * 64,
                request_kind="title", connection=connection, limits=limits, input_tokens=100)
    assert error.value.code == "dispatch_budget_exhausted"
    assert authority.run("foreground")["spent_dispatches"] == limit


@pytest.mark.parametrize("kind", ["retry", "continuation"])
def test_inherited_auxiliary_purpose_revocation_blocks_dispatch_and_publication(configured, kind):
    authority, spec, version, connection, limits = configured
    activate(authority, spec.model_copy(update={
        "roles": (RolePolicy(purpose="title", dispatch_limit=3, output_tokens=512),),
        "attempts": AttemptPolicy(retries=1, retryable_errors=("transport_unavailable",)),
    }), expected=version)
    authority.begin_run("foreground", "explain")
    first = authority.admit("foreground", "title", payload_hash="1" * 64,
        request_kind="title", connection=connection, limits=limits, input_tokens=100)
    authority.mark_dispatched(first["permit_id"], connection=connection, limits=limits,
        input_tokens=100, payload_hash="1" * 64)
    if kind == "retry":
        authority.complete(first["permit_id"], "failed", failure_code="transport_unavailable")
        derived = authority.admit("foreground", "title", payload_hash="1" * 64,
            request_kind="transport-fallback", connection=connection, limits=limits,
            input_tokens=100, retry_of=first["permit_id"])
    else:
        authority.complete(first["permit_id"], "confirmed", result_reference="tool-result")
        derived = authority.admit("foreground", "after-title-tool", payload_hash="1" * 64,
            request_kind="tool-continuation", connection=connection, limits=limits,
            input_tokens=100, continuation_of=first["permit_id"])
    assert derived["dispatch_purpose"] == "title"
    assert derived["output_tokens"] == 512
    authority.revoke("purpose:title")
    with pytest.raises(ApiError) as error:
        authority.mark_dispatched(derived["permit_id"], connection=connection, limits=limits,
            input_tokens=100, payload_hash="1" * 64)
    assert error.value.code == "authority_revoked"
    with authority.db.transaction() as conn:
        with pytest.raises(ApiError) as error:
            authority.require_current("foreground", permit_id=derived["permit_id"], conn=conn)
        assert error.value.code == "authority_revoked"
    assert authority.permit(derived["permit_id"])["state"] == "reserved"


@pytest.mark.parametrize("purpose", ["title", "summary"])
def test_exact_auxiliary_continuation_spends_original_purpose_budget(configured, purpose):
    authority, spec, version, connection, limits = configured
    activate(authority, spec.model_copy(update={
        "roles": (RolePolicy(purpose=purpose, dispatch_limit=2),),
    }), expected=version)
    authority.begin_run("foreground", "explain")
    first = authority.admit("foreground", "auxiliary", payload_hash="1" * 64,
        request_kind=purpose, connection=connection, limits=limits, input_tokens=100)
    authority.mark_dispatched(first["permit_id"], connection=connection, limits=limits,
        input_tokens=100, payload_hash="1" * 64)
    authority.complete(first["permit_id"], "confirmed", result_reference="tool-result")
    with pytest.raises(ApiError) as error:
        authority.admit("foreground", "ambiguous", payload_hash="2" * 64,
            request_kind="tool-continuation", connection=connection, limits=limits, input_tokens=100)
    assert error.value.code == "continuation_identity_required"
    continuation = authority.admit("foreground", "after-tool", payload_hash="2" * 64,
        request_kind="tool-continuation", connection=connection, limits=limits, input_tokens=100,
        continuation_of=first["permit_id"])
    assert continuation["dispatch_purpose"] == purpose
    assert continuation["retry_number"] == 0
    authority.mark_dispatched(continuation["permit_id"], connection=connection, limits=limits,
        input_tokens=100, payload_hash="2" * 64)
    authority.complete(continuation["permit_id"], "confirmed", result_reference="continued-result")
    with pytest.raises(ApiError) as error:
        authority.admit("foreground", "over-limit", payload_hash="3" * 64,
            request_kind="tool-continuation", connection=connection, limits=limits, input_tokens=100,
            continuation_of=continuation["permit_id"])
    assert error.value.code == "dispatch_budget_exhausted"
    assert authority.run("foreground")["spent_dispatches"] == 2


def test_continuation_retry_jointly_spends_root_and_purpose_limits(configured):
    authority, spec, version, connection, limits = configured
    activate(authority, spec.model_copy(update={
        "roles": (RolePolicy(purpose="title", dispatch_limit=3),),
        "attempts": AttemptPolicy(foreground_dispatches=3, retries=1,
            retryable_errors=("transport_unavailable",)),
    }), expected=version)
    authority.begin_run("foreground", "explain")
    first = authority.admit("foreground", "title", payload_hash="1" * 64,
        request_kind="title", connection=connection, limits=limits, input_tokens=100)
    authority.mark_dispatched(first["permit_id"], connection=connection, limits=limits,
        input_tokens=100, payload_hash="1" * 64)
    authority.complete(first["permit_id"], "confirmed", result_reference="tool-result")
    continuation = authority.admit("foreground", "after-tool", payload_hash="2" * 64,
        request_kind="tool-continuation", connection=connection, limits=limits, input_tokens=100,
        continuation_of=first["permit_id"])
    authority.mark_dispatched(continuation["permit_id"], connection=connection, limits=limits,
        input_tokens=100, payload_hash="2" * 64)
    authority.complete(continuation["permit_id"], "failed", failure_code="transport_unavailable")
    retry = authority.admit("foreground", "after-tool", payload_hash="2" * 64,
        request_kind="transport-fallback", connection=connection, limits=limits, input_tokens=100,
        retry_of=continuation["permit_id"])
    assert retry["dispatch_purpose"] == "title"
    assert retry["retry_number"] == 1
    authority.mark_dispatched(retry["permit_id"], connection=connection, limits=limits,
        input_tokens=100, payload_hash="2" * 64)
    authority.complete(retry["permit_id"], "confirmed", result_reference="retry-result")
    for kind in ("primary", "title"):
        with pytest.raises(ApiError) as error:
            authority.admit("foreground", kind + "-over-limit", payload_hash="3" * 64,
                request_kind=kind, connection=connection, limits=limits, input_tokens=100)
        assert error.value.code == "dispatch_budget_exhausted"
    assert authority.run("foreground")["spent_dispatches"] == 3


@pytest.mark.parametrize("root_limit,purpose_limit", [(2, 3), (3, 2)])
def test_parent_siblings_and_cancelled_reservations_keep_both_budgets_after_reopen(
        configured, root_limit, purpose_limit):
    authority, spec, version, connection, limits = configured
    activate(authority, spec.model_copy(update={
        "roles": (RolePolicy(purpose="title", dispatch_limit=purpose_limit),),
        "attempts": AttemptPolicy(foreground_dispatches=root_limit),
    }), expected=version)
    authority.begin_run("parent", "explain")
    authority.begin_child("first-child", "parent", "evidence-review")
    authority.begin_child("second-child", "parent", "evidence-review")
    parent = authority.admit("parent", "title", payload_hash="1" * 64, request_kind="title",
        connection=connection, limits=limits, input_tokens=100)
    child = authority.admit("first-child", "title", payload_hash="2" * 64, request_kind="title",
        connection=connection, limits=limits, input_tokens=100)
    authority.complete(parent["permit_id"], "cancelled_before_send")
    reopened = ConfigurationAuthority(authority.db)
    assert reopened.permit(child["permit_id"])["dispatch_purpose"] == "title"
    with pytest.raises(ApiError) as error:
        reopened.admit("second-child", "title", payload_hash="3" * 64, request_kind="title",
            connection=connection, limits=limits, input_tokens=100)
    assert error.value.code == "dispatch_budget_exhausted"
    assert reopened.run("parent")["spent_dispatches"] == 2
    if root_limit == 3:
        reopened.admit("second-child", "primary", payload_hash="4" * 64, request_kind="child",
            connection=connection, limits=limits, input_tokens=100)
        assert reopened.run("parent")["spent_dispatches"] == 3


@pytest.mark.parametrize("target", ["other-run", "child-route", "new-version"])
def test_continuation_cannot_cross_owning_run_config_or_route(configured, target):
    authority, spec, version, connection, limits = configured
    authority.begin_run("source", "explain")
    first = authority.admit("source", "first", payload_hash="1" * 64, request_kind="primary",
        connection=connection, limits=limits, input_tokens=100)
    authority.mark_dispatched(first["permit_id"], connection=connection, limits=limits,
        input_tokens=100, payload_hash="1" * 64)
    authority.complete(first["permit_id"], "confirmed", result_reference="tool-result")
    if target == "child-route":
        authority.begin_child(target, "source", "evidence-review", operation_model="deepseek-v4.1-flash")
    else:
        if target == "new-version":
            connection = connection.model_copy(update={"credential_revision": 2,
                "selected_model": "deepseek-v4.1-flash"})
            activate(authority, spec.model_copy(update={"connection": connection}), expected=version)
        authority.begin_run(target, "explain")
    with pytest.raises(ApiError) as error:
        authority.admit(target, "after-tool", payload_hash="2" * 64, request_kind="tool-continuation",
            connection=connection, limits=limits, input_tokens=100, continuation_of=first["permit_id"])
    assert error.value.code == "continuation_authority_mismatch"
    with pytest.raises(ApiError) as error:
        authority.require_current(target, permit_id=first["permit_id"])
    assert error.value.code == "permit_authority_mismatch"
    assert authority.run("source")["spent_dispatches"] == 1


@pytest.mark.parametrize("state", ["reserved", "dispatched", "failed", "uncertain"])
def test_continuation_requires_confirmed_prior_permit(configured, state):
    authority, spec, version, connection, limits = configured
    authority.begin_run("foreground", "explain")
    first = authority.admit("foreground", "first", payload_hash="1" * 64, request_kind="primary",
        connection=connection, limits=limits, input_tokens=100)
    if state != "reserved":
        authority.mark_dispatched(first["permit_id"], connection=connection, limits=limits,
            input_tokens=100, payload_hash="1" * 64)
    if state in {"failed", "uncertain"}:
        authority.complete(first["permit_id"], state,
            failure_code="transport_unavailable" if state == "failed" else None)
    with pytest.raises(ApiError) as error:
        authority.admit("foreground", "after-tool", payload_hash="2" * 64, request_kind="tool-continuation",
            connection=connection, limits=limits, input_tokens=100, continuation_of=first["permit_id"])
    assert error.value.code == "continuation_not_confirmed"
    assert authority.run("foreground")["spent_dispatches"] == 1


def test_upgrade_ambiguous_auxiliary_continuation_fails_closed(pre004_configured):
    previous, connection, limits = pre004_configured
    previous.begin_run("foreground", "explain")
    first = previous.admit("foreground", "title", payload_hash="1" * 64, request_kind="title",
        connection=connection, limits=limits, input_tokens=100)
    previous.mark_dispatched(first["permit_id"], connection=connection, limits=limits,
        input_tokens=100, payload_hash="1" * 64)
    previous.complete(first["permit_id"], "confirmed", result_reference="tool-result")
    ambiguous = previous.admit("foreground", "after-tool", payload_hash="2" * 64,
        request_kind="tool-continuation", connection=connection, limits=limits, input_tokens=100)
    upgraded = ConfigurationAuthority(previous.db)
    assert upgraded.permit(ambiguous["permit_id"])["dispatch_purpose"] is None
    with pytest.raises(ApiError) as error:
        upgraded.mark_dispatched(ambiguous["permit_id"], connection=connection, limits=limits,
            input_tokens=100, payload_hash="2" * 64)
    assert error.value.code == "dispatch_purpose_unavailable"
    with pytest.raises(ApiError) as error:
        upgraded.admit("foreground", "new", payload_hash="3" * 64, request_kind="primary",
            connection=connection, limits=limits, input_tokens=100)
    assert error.value.code == "dispatch_purpose_unavailable"
    assert upgraded.run("foreground")["spent_dispatches"] == 2


def test_upgrade_relabelled_retry_inherits_prior_purpose_and_spent_limit(pre004_configured):
    previous, connection, limits = pre004_configured
    previous.begin_run("foreground", "explain")
    first = previous.admit("foreground", "title", payload_hash="1" * 64, request_kind="title",
        connection=connection, limits=limits, input_tokens=100)
    previous.mark_dispatched(first["permit_id"], connection=connection, limits=limits,
        input_tokens=100, payload_hash="1" * 64)
    previous.complete(first["permit_id"], "failed", failure_code="transport_unavailable")
    retry = previous.admit("foreground", "title", payload_hash="1" * 64, request_kind="transport-fallback",
        connection=connection, limits=limits, input_tokens=100, retry_of=first["permit_id"])
    upgraded = ConfigurationAuthority(previous.db)
    assert upgraded.permit(retry["permit_id"])["dispatch_purpose"] == "title"
    with pytest.raises(ApiError) as error:
        upgraded.mark_dispatched(retry["permit_id"], connection=connection, limits=limits,
            input_tokens=100, payload_hash="1" * 64)
    assert error.value.code == "dispatch_budget_exhausted"
    assert upgraded.run("foreground")["spent_dispatches"] == 2


@pytest.mark.parametrize("outcome", ["uncertain", "failed"])
def test_default_policy_never_retries_uncertain_or_rejected_dispatch(configured, outcome):
    authority, spec, version, connection, limits = configured
    authority.begin_run("run", "explain")
    permit = authority.admit("run", "first", payload_hash="1" * 64, request_kind="primary",
                             connection=connection, limits=limits, input_tokens=100)
    authority.mark_dispatched(permit["permit_id"], connection=connection, limits=limits,
                              input_tokens=100, payload_hash="1" * 64)
    authority.complete(permit["permit_id"], outcome,
        failure_code="authentication_required" if outcome == "failed" else None)
    with pytest.raises(ApiError) as error:
        authority.admit("run", "first", payload_hash="1" * 64, request_kind="recovery",
            retry_of=permit["permit_id"], connection=connection, limits=limits, input_tokens=100)
    assert error.value.code == ("dispatch_uncertain" if outcome == "uncertain" else "retry_not_allowed")
    assert authority.run("run")["spent_dispatches"] == 1


def test_restart_preserves_uncertainty_and_confirmed_receipts_are_not_redispatched(configured):
    authority, spec, version, connection, limits = configured
    authority.begin_run("run", "explain")
    for step in ("sent", "confirmed", "reserved"):
        permit = authority.admit("run", step, payload_hash="1" * 64, request_kind="primary",
                                 connection=connection, limits=limits, input_tokens=100)
        if step != "reserved":
            authority.mark_dispatched(permit["permit_id"], connection=connection, limits=limits,
                                      input_tokens=100, payload_hash="1" * 64)
        if step == "confirmed":
            authority.complete(permit["permit_id"], "confirmed", result_reference="answer-reference")
        if step == "sent":
            sent = permit["permit_id"]
        if step == "reserved":
            reserved = permit["permit_id"]
    reopened = ConfigurationAuthority(authority.db)
    reopened.reconcile_restart(RestartBoundary(admission_closed=True, runtime_stopped=True, domain_settled=True))
    assert reopened.permit(sent)["state"] == "uncertain"
    assert reopened.permit(reserved)["state"] == "cancelled_before_send"
    assert reopened.validate(version, healthy)
    reopened.open_admission(version, registry_hash=spec.registry_hash, grant_epoch=0)
    receipt = reopened.admit("run", "confirmed", payload_hash="1" * 64, request_kind="primary",
                             connection=connection, limits=limits, input_tokens=100)
    assert receipt["state"] == "confirmed"
    assert receipt["result_reference"] == "answer-reference"
    assert receipt["dispatch_allowed"] is False
    assert reopened.run("run")["spent_dispatches"] == 3


def test_parallel_reservations_cannot_overspend_one_permit(configured):
    authority, spec, version, connection, limits = configured
    authority.begin_run("bundle", "daily_suggestions")
    def reserve(step):
        try:
            return authority.admit("bundle", step, payload_hash="1" * 64, request_kind="generate",
                connection=connection, limits=limits, input_tokens=100)["state"]
        except ApiError as error:
            return error.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(reserve, ("first", "second")))
    assert sorted(outcomes) == ["dispatch_budget_exhausted", "reserved"]
    assert authority.run("bundle")["spent_dispatches"] == 1


@pytest.mark.parametrize("changed", ["connection", "payload", "fit", "unknown"])
def test_final_request_mutation_cannot_bypass_admitted_identity_and_caps(configured, changed):
    authority, spec, version, connection, limits = configured
    authority.begin_run("run", "explain")
    permit = authority.admit("run", "first", payload_hash="1" * 64, request_kind="primary",
                             connection=connection, limits=limits, input_tokens=100)
    expected = {"connection": "connection_changed", "payload": "payload_changed",
                "fit": "request_does_not_fit", "unknown": "route_limits_unknown"}[changed]
    with pytest.raises(ApiError) as error:
        authority.mark_dispatched(permit["permit_id"],
            connection=connection.model_copy(update={"credential_revision": 2}) if changed == "connection" else connection,
            limits=RouteLimits() if changed == "unknown" else limits,
            payload_hash="2" * 64 if changed == "payload" else "1" * 64,
            input_tokens=8193 if changed == "fit" else 100)
    assert error.value.code == expected
    assert authority.permit(permit["permit_id"])["state"] == "reserved"


@pytest.mark.parametrize("flag", ["generation_open", "recovery_open", "package_acquisition_open",
                                  "mcp_startup_open", "live_store_writer"])
def test_candidate_open_effect_or_second_runtime_writer_is_rejected(configured, flag):
    authority, spec, version, connection, limits = configured
    candidate = authority.stage(spec.model_copy(update={"registry_hash": "b" * 64}))
    assert not authority.validate(candidate, lambda value: healthy(value).model_copy(update={flag: True}))
    assert authority.status()["effective"] == version
    assert authority.status()["failure_code"] == "candidate_not_closed"


def test_candidate_activation_compare_and_swap_and_revocation_epoch(configured):
    authority, spec, version, connection, limits = configured
    stale = authority.stage(spec.model_copy(update={"registry_hash": "b" * 64}))
    assert authority.validate(stale, healthy)
    newer = authority.stage(spec.model_copy(update={"registry_hash": "c" * 64}))
    assert authority.validate(newer, healthy)
    boundary = RestartBoundary(admission_closed=True, runtime_stopped=True, domain_settled=True)
    with pytest.raises(ApiError) as error:
        authority.activate(stale, boundary, expected_effective=version)
    assert error.value.code == "activation_conflict"
    authority.revoke("library-read")
    with pytest.raises(ApiError) as error:
        authority.activate(newer, boundary, expected_effective=version)
    assert error.value.code == "activation_conflict"
    assert authority.status()["effective"] == version


def test_child_cannot_widen_scope_and_parent_revocation_blocks_publication(configured):
    authority, spec, version, connection, limits = configured
    authority.begin_run("parent", "explain", capability_scope=("library-read",))
    with pytest.raises(ApiError) as error:
        authority.begin_child("wide", "parent", "evidence-review", capability_scope=("memory-read",))
    assert error.value.code == "scope_widening"
    authority.begin_child("child", "parent", "evidence-review", capability_scope=("library-read",))
    authority.revoke("purpose:explain")
    with pytest.raises(ApiError) as error:
        authority.require_current("child", required_capabilities=("library-read",))
    assert error.value.code == "authority_revoked"


def test_rejected_active_health_closes_admission_until_healthy_restart(configured):
    authority, spec, version, connection, limits = configured
    assert not authority.validate(version, lambda value: healthy(value).model_copy(update={"healthy": False}))
    assert authority.status()["admission_open"] is False
    with pytest.raises(ApiError) as error:
        authority.begin_run("run", "explain")
    assert error.value.code == "configuration_not_active"
    assert authority.validate(version, healthy)
    authority.open_admission(version, registry_hash=spec.registry_hash, grant_epoch=0)
    assert authority.begin_run("run", "explain")["version"] == version


def test_close_admission_busy_preserves_pointers_until_owner_settles(configured):
    authority, spec, version, connection, limits = configured
    authority.begin_run("root", "explain")
    permit = authority.admit("root", "primary", payload_hash="1" * 64,
        request_kind="primary", connection=connection, limits=limits, input_tokens=100)
    failed = authority.stage(spec.model_copy(update={"registry_hash": "b" * 64}))
    assert not authority.validate(failed, lambda candidate: healthy(
        candidate, registry_hash="c" * 64))
    requested = authority.stage(spec.model_copy(update={"registry_hash": "d" * 64}))
    reopened = ConfigurationAuthority(Database(authority.db.path))
    before = reopened.activation_snapshot()
    before_status = reopened.status()

    with pytest.raises(ApiError) as error:
        reopened.close_admission(expected_effective=version,
            requested_version=requested, grant_epoch=0)

    assert (error.value.code, error.value.status, error.value.retryable) == (
        "harness_configuration_busy", 409, True)
    assert reopened.activation_snapshot() == before
    assert reopened.permit(permit["permit_id"])["state"] == "reserved"
    reopened.mark_dispatched(permit["permit_id"], connection=connection, limits=limits,
        input_tokens=100, payload_hash="1" * 64)
    reopened.complete(permit["permit_id"], "confirmed", result_reference="answer")
    with pytest.raises(ApiError) as finalizing:
        reopened.close_admission(expected_effective=version,
            requested_version=requested, grant_epoch=0)
    assert finalizing.value.code == "harness_configuration_busy"
    assert reopened.status() == before_status
    reopened.settle_run("root")
    assert reopened.close_admission(expected_effective=version,
        requested_version=requested, grant_epoch=0)["pinned_runs"] == []


def test_exact_model_revocation_blocks_parent_and_child_dispatch(configured):
    authority, spec, version, connection, limits = configured
    authority.begin_run("parent", "explain")
    authority.begin_child("child", "parent", "evidence-review")
    authority.revoke("model:mimo-v2.6-pro")
    with pytest.raises(ApiError) as error:
        authority.admit("child", "first", payload_hash="1" * 64, request_kind="child",
                        connection=connection, limits=limits, input_tokens=100)
    assert error.value.code == "authority_revoked"
    assert authority.run("parent")["spent_dispatches"] == 0


def test_late_confirmed_receipt_reconciles_uncertainty_without_reviving_publication(configured):
    authority, spec, version, connection, limits = configured
    authority.begin_run("run", "explain", capability_scope=("library-read",))
    permit = authority.admit("run", "first", payload_hash="1" * 64, request_kind="primary",
                             connection=connection, limits=limits, input_tokens=100)
    authority.mark_dispatched(permit["permit_id"], connection=connection, limits=limits,
                              input_tokens=100, payload_hash="1" * 64)
    authority.complete(permit["permit_id"], "uncertain")
    authority.revoke("library-read")
    receipt = authority.complete(permit["permit_id"], "confirmed", result_reference="late-answer")
    assert receipt["state"] == "confirmed"
    assert receipt["dispatch_allowed"] is False
    assert receipt["result_reference"] == "late-answer"
    with pytest.raises(ApiError) as error:
        authority.require_current("run", required_capabilities=("library-read",))
    assert error.value.code == "capability_revoked"
    assert authority.run("run")["spent_dispatches"] == 1


def healthy(candidate, *, registry_hash=None):
    from renulus.runtime.harness_configuration import CandidateHealth
    return CandidateHealth(configuration_version=candidate.version, grant_epoch=candidate.grant_epoch,
                           registry_hash=registry_hash or candidate.spec.registry_hash)


def activate(authority, spec, *, expected=None):
    from renulus.runtime.harness_configuration import CandidateHealth, RestartBoundary
    version = authority.stage(spec)
    assert authority.validate(version, healthy)
    authority.activate(version, RestartBoundary(admission_closed=True, runtime_stopped=True,
                                                domain_settled=True), expected_effective=expected)
    authority.open_admission(version, registry_hash=spec.registry_hash,
                             grant_epoch=authority.revocation_overlay()["epoch"])
    return version


def test_revocation_during_probe_rejects_stale_candidate_health(tmp_path):
    from renulus.runtime.harness_configuration import (ConfigurationAuthority, ConfigurationSpec,
        ConnectionReference, CandidateHealth)
    authority = ConfigurationAuthority(Database(tmp_path / "canonical.sqlite"))
    version = authority.stage(ConfigurationSpec(connection=ConnectionReference(provider="codex",
        credential_reference="connection-codex", credential_revision=1), registry_hash="a" * 64))
    def probe(candidate):
        authority.revoke("library-read")
        return healthy(candidate)
    assert authority.validate(version, probe) is False
    assert authority.status()["failure_code"] == "candidate_authority_stale"


def test_reserved_dispatch_and_publication_recheck_current_revocation(tmp_path):
    from renulus.runtime.harness_configuration import (ConfigurationAuthority, ConfigurationSpec,
        ConnectionReference, RouteLimits)
    authority = ConfigurationAuthority(Database(tmp_path / "canonical.sqlite"))
    connection = ConnectionReference(provider="codex", credential_reference="connection-codex",
                                     credential_revision=1)
    activate(authority, ConfigurationSpec(connection=connection, registry_hash="a" * 64,
                                        capabilities=("library-read",)))
    authority.begin_run("transplant", "explain", capability_scope=("library-read",))
    limits = RouteLimits(input_tokens=8192, output_tokens=2048, window_tokens=10240)
    permit = authority.admit("transplant", "first", payload_hash="1" * 64, request_kind="primary",
        connection=connection, limits=limits, input_tokens=100, required_capabilities=("library-read",))
    assert permit["state"] == "reserved"
    assert permit["dispatch_allowed"] is False
    authority.revoke("library-read")
    with pytest.raises(ApiError) as error:
        authority.mark_dispatched(permit["permit_id"], connection=connection, limits=limits,
                                   input_tokens=100, payload_hash="1" * 64)
    assert error.value.code == "capability_revoked"
    with authority.db.transaction() as conn:
        with pytest.raises(ApiError) as error:
            authority.require_current("transplant", required_capabilities=("library-read",), conn=conn)
        assert error.value.code == "capability_revoked"
        assert authority.revocation_overlay(conn=conn) == {"epoch": 1, "revoked": ["library-read"]}


def test_explicit_same_route_retry_is_separately_debited_and_capped(tmp_path):
    from renulus.runtime.harness_configuration import (ConfigurationAuthority, ConfigurationSpec,
        ConnectionReference, RouteLimits, AttemptPolicy)
    authority = ConfigurationAuthority(Database(tmp_path / "canonical.sqlite"))
    connection = ConnectionReference(provider="opencode-go", credential_reference="connection-go",
                                     credential_revision=1)
    activate(authority, ConfigurationSpec(connection=connection, registry_hash="a" * 64,
        attempts=AttemptPolicy(retries=1, retryable_errors=("transport_unavailable",))))
    authority.begin_run("glomerular", "explain")
    limits = RouteLimits(input_tokens=8192, output_tokens=2048, window_tokens=10240)
    first = authority.admit("glomerular", "first", payload_hash="1" * 64, request_kind="primary",
                            connection=connection, limits=limits, input_tokens=100)
    authority.mark_dispatched(first["permit_id"], connection=connection, limits=limits,
                              input_tokens=100, payload_hash="1" * 64)
    authority.complete(first["permit_id"], "failed", failure_code="transport_unavailable")
    retry = authority.admit("glomerular", "first", payload_hash="1" * 64,
        request_kind="transport-fallback", connection=connection, limits=limits, input_tokens=100,
        retry_of=first["permit_id"])
    assert retry["retry_number"] == 1
    assert retry["route"]["model_id"] == first["route"]["model_id"]
    authority.mark_dispatched(retry["permit_id"], connection=connection, limits=limits,
                              input_tokens=100, payload_hash="1" * 64)
    authority.complete(retry["permit_id"], "failed", failure_code="transport_unavailable")
    with pytest.raises(ApiError) as error:
        authority.admit("glomerular", "first", payload_hash="1" * 64,
            request_kind="recovery", connection=connection, limits=limits, input_tokens=100,
            retry_of=retry["permit_id"])
    assert error.value.code == "retry_not_allowed"
    assert authority.run("glomerular")["spent_dispatches"] == 2


def test_child_slots_are_released_only_after_attempt_settlement(tmp_path):
    from renulus.runtime.harness_configuration import (ConfigurationAuthority, ConfigurationSpec,
        ConnectionReference, RouteLimits)
    authority = ConfigurationAuthority(Database(tmp_path / "canonical.sqlite"))
    connection = ConnectionReference(provider="codex", credential_reference="connection-codex",
                                     credential_revision=1)
    activate(authority, ConfigurationSpec(connection=connection, registry_hash="a" * 64))
    authority.begin_run("electrolytes", "explain")
    authority.begin_child("first-child", "electrolytes", "evidence-review")
    authority.begin_child("second-child", "electrolytes", "evidence-review")
    with pytest.raises(ApiError) as error:
        authority.begin_child("third-child", "electrolytes", "evidence-review")
    assert error.value.code == "child_concurrency_exhausted"
    with pytest.raises(ApiError) as error:
        authority.begin_child("grandchild", "first-child", "evidence-review")
    assert error.value.code == "child_depth_exhausted"
    permit = authority.admit("first-child", "first", payload_hash="1" * 64, request_kind="child",
        connection=connection, limits=RouteLimits(input_tokens=8192, output_tokens=2048,
                                                 window_tokens=10240), input_tokens=100)
    with pytest.raises(ApiError) as error:
        authority.settle_run("first-child")
    assert error.value.code == "run_not_settled"
    authority.complete(permit["permit_id"], "cancelled_before_send")
    authority.settle_run("first-child")
    assert authority.begin_child("third-child", "electrolytes", "evidence-review")["parent_id"] == "electrolytes"


def test_parent_children_and_tool_continuation_share_durable_dispatch_allowance(tmp_path):
    from renulus.runtime.harness_configuration import (ConfigurationAuthority, ConfigurationSpec,
        ConnectionReference, AttemptPolicy, RouteLimits)
    authority = ConfigurationAuthority(Database(tmp_path / "canonical.sqlite"))
    connection = ConnectionReference(provider="opencode-go", credential_reference="connection-go",
                                     credential_revision=1)
    activate(authority, ConfigurationSpec(connection=connection, registry_hash="a" * 64,
        capabilities=("library-read",), attempts=AttemptPolicy(foreground_dispatches=3)))
    authority.begin_run("dialysis", "explain", capability_scope=("library-read",))
    authority.begin_child("evidence", "dialysis", "evidence-review", capability_scope=("library-read",))
    limits = RouteLimits(input_tokens=8192, output_tokens=2048, window_tokens=10240)
    first = authority.admit("dialysis", "first", payload_hash="1" * 64, request_kind="primary",
                            connection=connection, limits=limits, input_tokens=100)
    authority.mark_dispatched(first["permit_id"], connection=connection, limits=limits,
                              input_tokens=100, payload_hash="1" * 64)
    authority.complete(first["permit_id"], "confirmed", result_reference="answer-first")
    child = authority.admit("evidence", "child-first", payload_hash="2" * 64, request_kind="child",
                            connection=connection, limits=limits, input_tokens=100)
    authority.mark_dispatched(child["permit_id"], connection=connection, limits=limits,
                              input_tokens=100, payload_hash="2" * 64)
    authority.complete(child["permit_id"], "confirmed", result_reference="evidence-report")
    continuation = authority.admit("dialysis", "after-tool", payload_hash="3" * 64,
        request_kind="tool-continuation", connection=connection, limits=limits, input_tokens=100)
    assert continuation["output_tokens"] == 2048
    assert continuation["retry_number"] == 0
    assert authority.run("dialysis")["spent_dispatches"] == 3
    with pytest.raises(ApiError) as error:
        authority.admit("dialysis", "too-many", payload_hash="4" * 64, request_kind="compaction",
                        connection=connection, limits=limits, input_tokens=100)
    assert error.value.code == "dispatch_budget_exhausted"


def test_busy_run_keeps_immutable_policy_and_revocation_narrows_it_after_reopen(tmp_path):
    from renulus.runtime.harness_configuration import (
        ConfigurationAuthority, ConfigurationSpec, ConnectionReference, ContextPolicy,
        AttemptPolicy, ChildPolicy, InputHash,
    )
    database = Database(tmp_path / "canonical.sqlite")
    authority = ConfigurationAuthority(database)
    spec = ConfigurationSpec(connection=ConnectionReference(provider="codex",
        credential_reference="connection-codex", credential_revision=1), registry_hash="a" * 64,
        capabilities=("library-read", "memory-read"),
        inputs=(InputHash(kind="skill", name="education", sha256="b" * 64),),
        context=ContextPolicy(requested_window_tokens=131072), attempts=AttemptPolicy(),
        children=ChildPolicy())
    original = activate(authority, spec)
    authority.begin_run("ckd-run", "explain", capability_scope=("library-read", "memory-read"))
    replacement = activate(authority, spec.model_copy(update={"registry_hash": "c" * 64}), expected=original)
    authority.revoke("memory-read")
    reopened = ConfigurationAuthority(database)
    assert reopened.run("ckd-run")["version"] == original
    assert reopened.run("ckd-run")["effective_capabilities"] == ["library-read"]
    assert reopened.status()["effective"] == replacement
    assert reopened.configuration(original) == spec
    with pytest.raises(Exception):
        reopened.configuration(original).context.requested_window_tokens = 262144


def test_disabled_role_cannot_be_revived_by_an_allowed_operation_override(tmp_path):
    from renulus.runtime.harness_configuration import (
        ConfigurationAuthority, ConfigurationSpec, ConnectionReference, RolePolicy,
    )
    authority = ConfigurationAuthority(Database(tmp_path / "canonical.sqlite"))
    version = authority.stage(ConfigurationSpec(connection=ConnectionReference(
        provider="opencode-go", credential_reference="connection-go", credential_revision=1),
        registry_hash="a" * 64, roles=(RolePolicy(purpose="explain", enabled=False),)))
    with pytest.raises(ApiError) as error:
        authority.resolve_role(version, "explain", catalogue=("deepseek-v4.1-flash",),
                               operation_model="deepseek-v4.1-flash")
    assert error.value.code == "role_disabled"


def test_interrupted_activation_returns_to_known_version_with_admission_closed(tmp_path):
    from renulus.runtime.harness_configuration import (
        ConfigurationAuthority, ConfigurationSpec, ConnectionReference, CandidateHealth,
        RestartBoundary,
    )
    database = Database(tmp_path / "canonical.sqlite")
    authority = ConfigurationAuthority(database)
    spec = ConfigurationSpec(connection=ConnectionReference(provider="codex",
        credential_reference="connection-codex", credential_revision=1), registry_hash="a" * 64)
    original = authority.stage(spec)
    authority.validate(original, healthy)
    boundary = RestartBoundary(admission_closed=True, runtime_stopped=True, domain_settled=True)
    authority.activate(original, boundary, expected_effective=None)
    authority.open_admission(original, registry_hash="a" * 64, grant_epoch=0)
    candidate = authority.stage(spec.model_copy(update={"registry_hash": "b" * 64}))
    authority.validate(candidate, healthy)
    authority.activate(candidate, boundary, expected_effective=original)
    reopened = ConfigurationAuthority(database)
    reopened.reconcile_restart(boundary)
    assert reopened.status() == {"requested": candidate, "effective": original,
        "failed": candidate, "failure_code": "activation_interrupted", "admission_open": False}
    with pytest.raises(Exception, match="configuration"):
        reopened.open_admission(original, registry_hash="b" * 64, grant_epoch=0)


def test_failed_candidate_keeps_healthy_effective_version_after_reopen(tmp_path):
    from renulus.runtime.harness_configuration import (
        ConfigurationAuthority, ConfigurationSpec, ConnectionReference, CandidateHealth,
        RestartBoundary,
    )

    database = Database(tmp_path / "canonical.sqlite")
    authority = ConfigurationAuthority(database)
    root = ConnectionReference(provider="opencode-go", credential_reference="connection-go",
                               credential_revision=1)
    original = authority.stage(ConfigurationSpec(connection=root, registry_hash="a" * 64))
    authority.validate(original, healthy)
    authority.activate(original, RestartBoundary(admission_closed=True, runtime_stopped=True,
                                                domain_settled=True), expected_effective=None)
    authority.open_admission(original, registry_hash="a" * 64, grant_epoch=0)
    replacement = authority.stage(ConfigurationSpec(connection=root, registry_hash="b" * 64))
    authority.validate(replacement, lambda candidate: healthy(candidate, registry_hash="c" * 64))

    reopened = ConfigurationAuthority(database)
    assert reopened.status() == {"requested": replacement, "effective": original,
                                 "failed": replacement, "failure_code": "registry_mismatch",
                                 "admission_open": True}


def test_activation_snapshot_pins_root_and_child_with_coherent_policy(configured):
    authority, spec, version, _, _ = configured
    authority.begin_run("root", "explain")
    authority.begin_child("child", "root", "summary")
    requested_spec = spec.model_copy(update={"roles": (
        RolePolicy(purpose="explain", output_tokens=1024),)})
    requested = authority.stage(requested_spec)
    authority.revoke("library-read")

    snapshot = authority.activation_snapshot()

    assert snapshot == {"requested": requested, "effective": version,
        "previous": None, "activating": None, "failed": None, "failure_code": None,
        "admission_open": True, "grant_epoch": 1, "revoked": ["library-read"],
        "configuration": spec, "requested_configuration": requested_spec,
        "pinned_runs": [
            {"run_id": "child", "purpose": "summary", "version": version},
            {"run_id": "root", "purpose": "explain", "version": version}]}


def test_close_admission_closes_only_gate_and_survives_reopen(configured):
    authority, spec, version, _, _ = configured
    failed = authority.stage(spec.model_copy(update={"registry_hash": "b" * 64}))
    assert not authority.validate(failed, lambda candidate: healthy(
        candidate, registry_hash="c" * 64))
    requested = authority.stage(spec.model_copy(update={"registry_hash": "d" * 64}))
    before = authority.activation_snapshot()

    closed = authority.close_admission(expected_effective=version,
        requested_version=requested, grant_epoch=0)

    assert closed == {**before, "admission_open": False}
    assert closed["failed"] == failed
    reopened = ConfigurationAuthority(Database(authority.db.path))
    assert reopened.activation_snapshot() == closed
    assert reopened.close_admission(expected_effective=version,
        requested_version=requested, grant_epoch=0) == closed
    with pytest.raises(ApiError) as error:
        reopened.begin_run("after-seal", "explain")
    assert error.value.code == "configuration_not_active"


@pytest.mark.parametrize("changed", ["effective", "requested", "grant_epoch", "activating"])
def test_close_admission_rejects_changed_activation_authority(configured, changed):
    authority, spec, version, _, _ = configured
    expected = {"expected_effective": version, "requested_version": version, "grant_epoch": 0}
    replacement_spec = spec.model_copy(update={"registry_hash": "b" * 64})
    if changed == "effective":
        replacement = activate(authority, replacement_spec, expected=version)
        expected["requested_version"] = replacement
    elif changed == "requested":
        authority.stage(replacement_spec)
    elif changed == "grant_epoch":
        authority.revoke("library-read")
    else:
        replacement = authority.stage(replacement_spec)
        assert authority.validate(replacement, healthy)
        authority.activate(replacement, RestartBoundary(admission_closed=True,
            runtime_stopped=True, domain_settled=True), expected_effective=version)
        expected.update(expected_effective=replacement, requested_version=replacement)
    before = authority.activation_snapshot()
    reopened = ConfigurationAuthority(Database(authority.db.path))

    with pytest.raises(ApiError) as error:
        reopened.close_admission(**expected)

    assert error.value.code == ("candidate_authority_stale"
        if changed == "grant_epoch" else "activation_conflict")
    assert reopened.activation_snapshot() == before


@pytest.mark.parametrize("grant_epoch", [False, 0.0])
def test_close_admission_rejects_noninteger_epoch(configured, grant_epoch):
    authority, _, version, _, _ = configured
    before = authority.activation_snapshot()
    with pytest.raises(ApiError) as error:
        authority.close_admission(expected_effective=version,
            requested_version=version, grant_epoch=grant_epoch)
    assert error.value.code == "candidate_authority_stale"
    assert authority.activation_snapshot() == before


def test_close_admission_requires_staged_request(tmp_path):
    authority = ConfigurationAuthority(Database(tmp_path / "canonical.sqlite"))
    before = authority.activation_snapshot()
    with pytest.raises(ApiError) as error:
        authority.close_admission(expected_effective=None, requested_version=None, grant_epoch=0)
    assert error.value.code == "activation_conflict"
    assert authority.activation_snapshot() == before


def test_activation_snapshot_unconfigured_and_pending_selection_after_reopen(tmp_path):
    authority = ConfigurationAuthority(Database(tmp_path / "canonical.sqlite"))
    assert authority.activation_snapshot() == {"requested": None, "effective": None,
        "previous": None, "activating": None, "failed": None, "failure_code": None,
        "admission_open": False, "grant_epoch": 0, "revoked": [],
        "configuration": None, "requested_configuration": None, "pinned_runs": []}
    spec = ConfigurationSpec(connection=ConnectionReference(provider="opencode-go",
        credential_reference="connection-go", credential_revision=1), registry_hash="a" * 64)
    version = authority.stage(spec)
    authority.revoke("library-read")
    closed = authority.close_admission(expected_effective=None,
        requested_version=version, grant_epoch=1)
    assert closed["configuration"] is None
    assert closed["requested_configuration"] == spec
    assert closed["admission_open"] is False
    assert authority.validate(version, healthy)
    authority.activate(version, RestartBoundary(admission_closed=True,
        runtime_stopped=True, domain_settled=True), expected_effective=None)
    reopened = ConfigurationAuthority(Database(authority.db.path))
    assert reopened.activation_snapshot() == {**closed, "effective": version,
        "activating": version, "configuration": spec}


@pytest.mark.parametrize("owner", ["root", "child"])
@pytest.mark.parametrize("attempt_state", [
    "reserved", "dispatched", "confirmed", "failed", "uncertain", "cancelled_before_send"])
def test_close_admission_pins_attempt_owner_until_explicit_settlement(
        configured, owner, attempt_state):
    authority, spec, version, connection, limits = configured
    authority.begin_run("root", "explain")
    if owner == "child":
        authority.begin_child("child", "root", "summary")
    permit = authority.admit(owner, "step", payload_hash="1" * 64, request_kind="primary",
        connection=connection, limits=limits, input_tokens=100)
    if attempt_state not in {"reserved", "cancelled_before_send"}:
        authority.mark_dispatched(permit["permit_id"], connection=connection, limits=limits,
            input_tokens=100, payload_hash="1" * 64)
    if attempt_state not in {"reserved", "dispatched"}:
        authority.complete(permit["permit_id"], attempt_state)
    requested = authority.stage(spec.model_copy(update={"registry_hash": "b" * 64}))
    reopened = ConfigurationAuthority(Database(authority.db.path))
    before = reopened.activation_snapshot()
    assert [pin["run_id"] for pin in before["pinned_runs"]] == (
        ["child", "root"] if owner == "child" else ["root"])

    with pytest.raises(ApiError) as busy:
        reopened.close_admission(expected_effective=version,
            requested_version=requested, grant_epoch=0)
    assert (busy.value.code, busy.value.status, busy.value.retryable) == (
        "harness_configuration_busy", 409, True)
    assert reopened.activation_snapshot() == before
    assert reopened.permit(permit["permit_id"])["state"] == attempt_state
    if attempt_state in {"reserved", "dispatched"}:
        with pytest.raises(ApiError) as unsettled:
            reopened.settle_run(owner)
        assert unsettled.value.code == "run_not_settled"
    else:
        reopened.settle_run(owner)
        if owner == "child":
            assert reopened.activation_snapshot()["pinned_runs"] == [
                {"run_id": "root", "purpose": "explain", "version": version}]
            reopened.settle_run("root")
        assert reopened.close_admission(expected_effective=version,
            requested_version=requested, grant_epoch=0)["pinned_runs"] == []


def test_close_admission_includes_old_pins_after_current_owner_settles(configured):
    authority, spec, original, _, _ = configured
    authority.begin_run("old-root", "explain")
    authority.begin_child("old-child", "old-root", "summary")
    current = activate(authority, spec.model_copy(update={"registry_hash": "b" * 64}),
        expected=original)
    authority.begin_run("current-root", "explain")
    authority.settle_run("current-root")
    reopened = ConfigurationAuthority(Database(authority.db.path))
    before = reopened.activation_snapshot()
    assert before["effective"] == current
    assert before["pinned_runs"] == [
        {"run_id": "old-child", "purpose": "summary", "version": original},
        {"run_id": "old-root", "purpose": "explain", "version": original}]
    with pytest.raises(ApiError) as error:
        reopened.close_admission(expected_effective=current,
            requested_version=current, grant_epoch=0)
    assert error.value.code == "harness_configuration_busy"
    assert reopened.activation_snapshot() == before


@pytest.mark.parametrize("contender", ["run", "requested", "grant_epoch"])
def test_close_admission_serializes_with_independent_current_authority(configured, contender):
    authority, spec, version, _, _ = configured
    independent = ConfigurationAuthority(Database(authority.db.path))
    barrier = Barrier(2)

    def compete():
        barrier.wait(timeout=5)
        try:
            if contender == "run":
                return independent.begin_run("racing-root", "explain")
            if contender == "requested":
                return independent.stage(spec.model_copy(update={"registry_hash": "b" * 64}))
            return independent.revoke("library-read")
        except ApiError as error:
            return error.code

    def seal():
        barrier.wait(timeout=5)
        try:
            return authority.close_admission(expected_effective=version,
                requested_version=version, grant_epoch=0)
        except ApiError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as workers:
        competing = workers.submit(compete)
        sealing = workers.submit(seal)
        result, closed = competing.result(timeout=10), sealing.result(timeout=10)
    snapshot = independent.activation_snapshot()
    assert snapshot["effective"] == version
    if isinstance(closed, dict):
        assert closed["requested"] == version and closed["grant_epoch"] == 0
        assert closed["pinned_runs"] == [] and closed["admission_open"] is False
        assert snapshot["admission_open"] is False
        if contender == "run":
            assert result == "configuration_not_active"
    else:
        assert closed == {"run": "harness_configuration_busy",
            "requested": "activation_conflict",
            "grant_epoch": "candidate_authority_stale"}[contender]
        assert snapshot["admission_open"] is True
        if contender == "run":
            assert result["version"] == version
            assert snapshot["pinned_runs"] == [
                {"run_id": "racing-root", "purpose": "explain", "version": version}]
    if contender == "requested":
        assert snapshot["requested"] == result
    elif contender == "grant_epoch":
        assert snapshot["grant_epoch"] == result == 1


def test_activation_snapshot_stays_coherent_during_staging_and_revocation(configured):
    authority, spec, _, _, _ = configured
    independent = ConfigurationAuthority(Database(authority.db.path))
    alternate = spec.model_copy(update={"registry_hash": "b" * 64})
    versions = {authority.stage(spec): spec, authority.stage(alternate): alternate}
    barrier = Barrier(2)

    def change():
        barrier.wait(timeout=5)
        for index in range(8):
            independent.stage(spec if index % 2 else alternate)
            independent.revoke("capability-" + str(index))

    def observe():
        barrier.wait(timeout=5)
        return [authority.activation_snapshot() for _ in range(8)]

    with ThreadPoolExecutor(max_workers=2) as workers:
        changing, observing = workers.submit(change), workers.submit(observe)
        changing.result(timeout=10)
        snapshots = observing.result(timeout=10)
    for snapshot in snapshots:
        assert snapshot["requested_configuration"] == versions[snapshot["requested"]]
        assert snapshot["configuration"] == spec
        assert snapshot["grant_epoch"] == len(snapshot["revoked"])
    assert authority.activation_snapshot()["grant_epoch"] == 8


def test_begin_run_in_commits_the_pinned_run_with_the_callers_transaction(configured):
    authority, spec, version, connection, limits = configured
    with authority.db.transaction() as conn:
        run = authority.begin_run_in(conn, "atomic-admission", "explain",
            expected_version=version, capability_scope=("library-read",),
            catalogue=("deepseek-v4.1-flash", "mimo-v2.6-pro"))
        assert conn.in_transaction
        assert run == {
            "run_id": "atomic-admission", "version": version, "root_id": "atomic-admission",
            "parent_id": None, "purpose": "explain", "state": "active",
            "dispatch_limit": 12, "spent_dispatches": 0,
            "effective_capabilities": ["library-read"],
            "route": {"provider": "opencode-go", "credential_reference": "connection-go",
                "credential_revision": 1, "model_id": "mimo-v2.6-pro",
                "output_tokens": 4096, "endpoint": "https://opencode.ai/zen/go/v1",
                "protocol": "chat-completions"},
        }
    assert authority.run("atomic-admission") == run
    assert authority.activation_snapshot()["pinned_runs"] == [
        {"run_id": "atomic-admission", "purpose": "explain", "version": version}]


def test_begin_run_in_rejects_a_requested_version_that_is_not_effective(configured):
    authority, spec, version, connection, limits = configured
    requested = authority.stage(spec.model_copy(update={"registry_hash": "b" * 64}))
    before = authority.activation_snapshot()
    with pytest.raises(ApiError) as error:
        with authority.db.transaction() as conn:
            authority.begin_run_in(conn, "stale-admission", "explain", expected_version=requested)
    assert error.value.code == "activation_conflict"
    assert authority.activation_snapshot() == before
    with pytest.raises(ApiError) as missing:
        authority.run("stale-admission")
    assert missing.value.code == "run_missing"


def test_begin_run_in_requires_an_active_caller_transaction(configured):
    authority, spec, version, connection, limits = configured
    before = authority.activation_snapshot()
    with closing(authority.db.connect()) as conn:
        with pytest.raises(ApiError) as error:
            authority.begin_run_in(conn, "unowned-admission", "explain", expected_version=version)
        assert error.value.code == "configuration_transaction_required"
        assert not conn.in_transaction
    assert authority.activation_snapshot() == before


def test_begin_run_in_rejects_a_foreign_database_with_identical_configuration(configured, tmp_path):
    authority, spec, version, connection, limits = configured
    foreign = ConfigurationAuthority(Database(tmp_path / "foreign.sqlite"))
    assert activate(foreign, spec) == version
    before = authority.activation_snapshot()
    foreign_before = foreign.activation_snapshot()
    with pytest.raises(ApiError) as error:
        with foreign.db.transaction() as conn:
            authority.begin_run_in(conn, "foreign-admission", "explain", expected_version=version)
    assert error.value.code == "configuration_connection_mismatch"
    assert authority.activation_snapshot() == before
    assert foreign.activation_snapshot() == foreign_before


def test_begin_run_in_rolls_back_with_rejected_outer_publication(configured):
    authority, spec, version, connection, limits = configured
    before = authority.activation_snapshot()
    with pytest.raises(RuntimeError, match="publication rejected"):
        with authority.db.transaction() as conn:
            run = authority.begin_run_in(conn, "rolled-back-owner", "explain",
                expected_version=version, capability_scope=("library-read",))
            assert run["state"] == "active"
            raise RuntimeError("publication rejected")
    assert authority.activation_snapshot() == before
    with pytest.raises(ApiError) as error:
        authority.run("rolled-back-owner")
    assert error.value.code == "run_missing"


def test_begin_run_in_duplicate_rolls_back_other_admissions_without_replacing_owner(configured):
    authority, spec, version, connection, limits = configured
    retained = authority.begin_run("retained-owner", "explain", capability_scope=("library-read",))
    before = authority.activation_snapshot()
    with pytest.raises(ApiError) as error:
        with authority.db.transaction() as conn:
            authority.begin_run_in(conn, "partial-owner", "summary", expected_version=version)
            authority.begin_run_in(conn, "retained-owner", "explain", expected_version=version,
                                   operation_model="deepseek-v4.1-flash")
    assert error.value.code == "run_already_exists"
    assert authority.run("retained-owner") == retained
    assert authority.activation_snapshot() == before
    with pytest.raises(ApiError) as missing:
        authority.run("partial-owner")
    assert missing.value.code == "run_missing"


def test_begin_run_in_uses_only_the_supplied_connection(configured, monkeypatch):
    authority, spec, version, connection, limits = configured
    def unavailable_connection():
        pytest.fail("Admission must use the caller's canonical connection")

    with authority.db.transaction() as conn:
        with monkeypatch.context() as guard:
            guard.setattr(authority.db, "connect", unavailable_connection)
            run = authority.begin_run_in(conn, "single-connection", "explain", expected_version=version)
            assert conn.in_transaction
    assert authority.run("single-connection") == run


@pytest.mark.parametrize("closed_by", ["seal", "unhealthy", "restart"])
def test_begin_run_in_requires_healthy_open_admission(configured, closed_by):
    authority, spec, version, connection, limits = configured
    if closed_by == "seal":
        authority.close_admission(expected_effective=version, requested_version=version, grant_epoch=0)
    elif closed_by == "unhealthy":
        assert not authority.validate(version, lambda candidate: CandidateHealth(
            configuration_version=version, grant_epoch=candidate.grant_epoch,
            registry_hash=spec.registry_hash, healthy=False))
    else:
        authority.reconcile_restart(RestartBoundary(
            admission_closed=True, runtime_stopped=True, domain_settled=True))
    before = authority.activation_snapshot()
    with pytest.raises(ApiError) as error:
        with authority.db.transaction() as conn:
            authority.begin_run_in(conn, "closed-admission", "explain", expected_version=version)
    assert error.value.code == "configuration_not_active"
    assert authority.activation_snapshot() == before


@pytest.mark.parametrize("change,error_code", [
    ("scope", "scope_widening"), ("disabled", "role_disabled"),
    ("purpose", "purpose_not_allowed"), ("model", "model_not_allowed")])
def test_begin_run_in_preserves_scope_and_role_rejections(configured, change, error_code):
    authority, spec, version, connection, limits = configured
    scope, purpose, model = (), "explain", None
    if change == "scope":
        scope = ("foreign-capability",)
    elif change == "disabled":
        purpose = "title"
    elif change == "purpose":
        purpose = "invented-role"
    else:
        model = "gpt-6.1-sol"
    before = authority.activation_snapshot()
    with pytest.raises(ApiError) as error:
        with authority.db.transaction() as conn:
            authority.begin_run_in(conn, "invalid-admission", purpose, expected_version=version,
                                   capability_scope=scope, operation_model=model)
    assert error.value.code == error_code
    assert authority.activation_snapshot() == before


@pytest.mark.parametrize("catalogue,expected", [
    (("deepseek-v4.1-flash", "mimo-v2.6-pro"), "mimo-v2.6-pro"),
    (("unapproved", "deepseek-v4.1-flash"), "deepseek-v4.1-flash"),
    ((), "mimo-v2.6-pro"), (("gpt-6.1-sol",), "mimo-v2.6-pro")])
def test_begin_run_in_preserves_automatic_allowlist_order(configured, catalogue, expected):
    authority, spec, version, connection, limits = configured
    with authority.db.transaction() as conn:
        run = authority.begin_run_in(conn, "automatic-owner", "explain", expected_version=version,
                                   catalogue=catalogue)
    assert run["route"]["model_id"] == expected
    assert authority.configuration(version).connection.selected_model is None
    assert authority.run("automatic-owner") == run


def test_begin_run_in_rejects_an_ended_caller_transaction(configured):
    authority, spec, version, connection, limits = configured
    with authority.db.transaction() as conn:
        pass
    before = authority.activation_snapshot()
    with pytest.raises(ApiError) as error:
        authority.begin_run_in(conn, "ended-admission", "explain", expected_version=version)
    assert error.value.code == "configuration_transaction_required"
    assert authority.activation_snapshot() == before


def test_begin_run_in_accepts_an_independent_connection_to_the_same_canonical_database(configured):
    authority, spec, version, connection, limits = configured
    canonical = Database(authority.db.path)
    with canonical.transaction() as conn:
        run = authority.begin_run_in(conn, "same-database", "explain", expected_version=version)
    assert authority.run("same-database") == run


def test_begin_run_in_rejects_the_former_effective_version_after_activation(configured):
    authority, spec, version, connection, limits = configured
    current = activate(authority, spec.model_copy(update={"registry_hash": "b" * 64}), expected=version)
    before = authority.activation_snapshot()
    with pytest.raises(ApiError) as error:
        with authority.db.transaction() as conn:
            authority.begin_run_in(conn, "former-version", "explain", expected_version=version)
    assert error.value.code == "activation_conflict"
    assert authority.activation_snapshot() == before
    with authority.db.transaction() as conn:
        admitted = authority.begin_run_in(conn, "current-version", "explain", expected_version=current)
    assert authority.run("current-version") == admitted
    assert admitted["version"] == current


@pytest.mark.parametrize("operation_model,expected", [
    (None, "deepseek-v4.1-flash"), ("mimo-v2.6-pro", "mimo-v2.6-pro")])
def test_begin_run_in_preserves_explicit_role_budget_output_and_override(configured, operation_model, expected):
    authority, spec, version, connection, limits = configured
    current = activate(authority, spec.model_copy(update={"roles": (RolePolicy(
        purpose="explain", model_id="deepseek-v4.1-flash", dispatch_limit=2, output_tokens=1536),)}),
        expected=version)
    with authority.db.transaction() as conn:
        run = authority.begin_run_in(conn, "explicit-role", "explain", expected_version=current,
                                   operation_model=operation_model)
    assert run["dispatch_limit"] == 2
    assert run["route"]["output_tokens"] == 1536
    assert run["route"]["model_id"] == expected
    assert run["route"]["credential_reference"] == "connection-go"
    assert run["route"]["credential_revision"] == 1
    assert authority.run("explicit-role") == run
