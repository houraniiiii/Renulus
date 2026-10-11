"""Named summary-repair accounting through public Authority and canonical SQLite.

Candidate health and restart flags below are synthetic policy setup, not evidence
of native activation or settlement. No model transport or auxiliary producer runs.
"""

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
    provider="opencode-go",
    credential_reference="synthetic-summary-connection",
    credential_revision=1,
    selected_model="mimo-v2.6-pro",
)
LIMITS = RouteLimits(input_tokens=8192, output_tokens=2048, window_tokens=10240)
RUN_ID = "summary-repair-root"
SUMMARY_HASH = "b" * 64
TOOL_HASH = "c" * 64
PRIMARY_HASH = "d" * 64


def configured_authority(tmp_path, *, root_dispatches, compaction_dispatches):
    authority = ConfigurationAuthority(Database(tmp_path / "canonical.sqlite"))
    spec = ConfigurationSpec(
        connection=CONNECTION,
        registry_hash="a" * 64,
        roles=(RolePolicy(purpose="compaction", dispatch_limit=compaction_dispatches),),
        attempts=AttemptPolicy(
            foreground_dispatches=root_dispatches,
            retries=1,
            retryable_errors=("summary_invalid",),
        ),
    )
    version = authority.stage(spec)
    assert authority.validate(
        version,
        lambda candidate: CandidateHealth(
            configuration_version=candidate.version,
            grant_epoch=candidate.grant_epoch,
            registry_hash=candidate.spec.registry_hash,
        ),
    )
    authority.activate(
        version,
        RestartBoundary(admission_closed=True, runtime_stopped=True, domain_settled=True),
        expected_effective=None,
    )
    authority.open_admission(
        version,
        registry_hash=spec.registry_hash,
        grant_epoch=authority.revocation_overlay()["epoch"],
    )
    authority.begin_run(RUN_ID, "explain")
    return authority, version


def reserve(authority, step_id, request_kind, payload_hash, *, retry_of=None, continuation_of=None):
    return authority.admit(
        RUN_ID,
        step_id,
        payload_hash=payload_hash,
        request_kind=request_kind,
        connection=CONNECTION,
        limits=LIMITS,
        input_tokens=100,
        retry_of=retry_of,
        continuation_of=continuation_of,
    )


def finish(authority, permit, *, outcome="confirmed", failure_code=None):
    dispatched = authority.mark_dispatched(
        permit["permit_id"],
        connection=CONNECTION,
        limits=LIMITS,
        input_tokens=100,
        payload_hash=permit["payload_hash"],
    )
    assert dispatched["state"] == "dispatched"
    assert dispatched["dispatch_allowed"] is True
    return authority.complete(permit["permit_id"], outcome, failure_code=failure_code)


def test_summary_repair_exhausts_compaction_budget_across_sqlite_reopen(tmp_path):
    authority, version = configured_authority(tmp_path, root_dispatches=4, compaction_dispatches=2)
    original = reserve(authority, "compact", "compaction", SUMMARY_HASH)
    finish(authority, original, outcome="failed", failure_code="summary_invalid")

    repair = reserve(
        authority, "compact", "summary-repair", SUMMARY_HASH, retry_of=original["permit_id"]
    )
    assert repair["request_kind"] == "summary-repair"
    assert repair["dispatch_purpose"] == "compaction"
    assert repair["retry_number"] == 1
    assert repair["state"] == "reserved"
    assert authority.run(RUN_ID)["spent_dispatches"] == 2
    finish(authority, repair)

    authority = ConfigurationAuthority(Database(tmp_path / "canonical.sqlite"))
    assert authority.run(RUN_ID)["version"] == version
    assert authority.run(RUN_ID)["spent_dispatches"] == 2
    restored = authority.permit(repair["permit_id"])
    assert restored["state"] == "confirmed"
    assert restored["dispatch_purpose"] == "compaction"
    assert restored["retry_number"] == 1
    with pytest.raises(ApiError) as error:
        reserve(
            authority,
            "after-repair-tool",
            "tool-continuation",
            TOOL_HASH,
            continuation_of=repair["permit_id"],
        )
    assert error.value.code == "dispatch_budget_exhausted"
    assert authority.run(RUN_ID)["spent_dispatches"] == 2

    primary = reserve(authority, "answer", "primary", PRIMARY_HASH)
    assert primary["dispatch_purpose"] == "explain"
    finish(authority, primary)
    assert authority.run(RUN_ID)["spent_dispatches"] == 3


def test_summary_repair_exhausts_root_budget_with_compaction_allowance_remaining(tmp_path):
    authority, _ = configured_authority(tmp_path, root_dispatches=2, compaction_dispatches=4)
    original = reserve(authority, "compact", "compaction", SUMMARY_HASH)
    finish(authority, original, outcome="failed", failure_code="summary_invalid")
    repair = reserve(
        authority, "compact", "summary-repair", SUMMARY_HASH, retry_of=original["permit_id"]
    )
    assert repair["dispatch_purpose"] == "compaction"
    finish(authority, repair)

    run = authority.run(RUN_ID)
    assert run["dispatch_limit"] == 2
    assert run["spent_dispatches"] == 2
    assert authority.resolve_role(run["version"], "compaction").dispatch_limit == 4
    with pytest.raises(ApiError) as continuation_error:
        reserve(
            authority,
            "after-repair-tool",
            "tool-continuation",
            TOOL_HASH,
            continuation_of=repair["permit_id"],
        )
    assert continuation_error.value.code == "dispatch_budget_exhausted"
    with pytest.raises(ApiError) as primary_error:
        reserve(authority, "answer", "primary", PRIMARY_HASH)
    assert primary_error.value.code == "dispatch_budget_exhausted"
    assert authority.run(RUN_ID)["spent_dispatches"] == 2


def test_summary_repair_continuation_and_relabelled_retry_keep_compaction_debits(tmp_path):
    authority, version = configured_authority(tmp_path, root_dispatches=5, compaction_dispatches=4)
    original = reserve(authority, "compact", "compaction", SUMMARY_HASH)
    finish(authority, original, outcome="failed", failure_code="summary_invalid")
    repair = reserve(
        authority, "compact", "summary-repair", SUMMARY_HASH, retry_of=original["permit_id"]
    )
    assert repair["retry_number"] == 1
    finish(authority, repair)

    continuation = reserve(
        authority,
        "after-repair-tool",
        "tool-continuation",
        TOOL_HASH,
        continuation_of=repair["permit_id"],
    )
    assert continuation["dispatch_purpose"] == "compaction"
    assert continuation["retry_number"] == 0
    finish(authority, continuation, outcome="failed", failure_code="summary_invalid")

    authority = ConfigurationAuthority(Database(tmp_path / "canonical.sqlite"))
    assert authority.run(RUN_ID)["spent_dispatches"] == 3
    assert authority.permit(continuation["permit_id"])["state"] == "failed"
    retry = reserve(
        authority,
        "after-repair-tool",
        "primary",
        TOOL_HASH,
        retry_of=continuation["permit_id"],
    )
    assert retry["request_kind"] == "primary"
    assert retry["dispatch_purpose"] == "compaction"
    assert retry["retry_number"] == 1
    assert retry["run_id"] == RUN_ID
    assert retry["root_id"] == RUN_ID
    assert retry["version"] == version
    assert retry["route"] == continuation["route"]
    assert authority.run(RUN_ID)["spent_dispatches"] == 4
    finish(authority, retry)

    with pytest.raises(ApiError) as error:
        reserve(
            authority,
            "after-retry-tool",
            "tool-continuation",
            PRIMARY_HASH,
            continuation_of=retry["permit_id"],
        )
    assert error.value.code == "dispatch_budget_exhausted"
    assert authority.run(RUN_ID)["spent_dispatches"] == 4
    primary = reserve(authority, "answer", "primary", PRIMARY_HASH)
    assert primary["retry_number"] == 0
    assert primary["dispatch_purpose"] == "explain"
    finish(authority, primary)
    assert authority.run(RUN_ID)["spent_dispatches"] == 5
