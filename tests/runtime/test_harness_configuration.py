"""H04 behavior through the canonical configuration, role and permit interface."""
from renulus.storage.database import Database
import pytest
from renulus.contracts import ApiError
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

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
