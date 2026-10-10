"""Public transport scenarios using owned, credential-free subprocesses."""
from pathlib import Path
import asyncio
import sys
import pytest

from renulus.runtime.harness_process import (
    HarnessProcessConfig, HarnessProcessError, ManagedHarnessProcess,
)


def config(tmp_path, **overrides):
    return HarnessProcessConfig(
        node_executable=Path(sys.executable),
        host_entry=Path(__file__).parent / "fixtures" / "harness_child.py",
        profile_root=tmp_path / "profile",
        profile_id="synthetic-profile", store_id="synthetic-store", **overrides,
        domain_store_id="synthetic-domain-store", domain_path="state/renulus.sqlite",
    )


async def test_owned_child_returns_authenticated_structured_reply_and_closes(tmp_path):
    process = ManagedHarnessProcess()
    ready = await process.start(config(tmp_path))
    try:
        response = await process.request("session.create", {"title": "Kidney physiology"},
                                         "learning-1", "attempt-1", timeout=2)
        assert ready["state"] == "ready"
        assert response["outcome"] == "committed_reference"
        assert response["result"] == {
            "command": "session.create", "payload": {"title": "Kidney physiology"}}
        assert response["profile_id"] == "synthetic-profile"
        assert response["store_id"] == "synthetic-store"
        assert response["generation"] == ready["generation"]
        assert response["operation_id"] == "learning-1"
        assert response["attempt_id"] == "attempt-1"
        assert "token" not in response
    finally:
        closed = await process.close(timeout=2)
    assert closed["state"] == "closed"
    assert closed["outcome"] == "cancelled_settled"


async def settled(process, request_id):
    async with asyncio.timeout(2):
        while True:
            result = await process.query_result(request_id)
            if result and result["outcome"] != "accepted_pending":
                return result
            await asyncio.sleep(0.01)


async def test_malformed_empty_error_code_cannot_settle_before_the_valid_reply(tmp_path):
    process = ManagedHarnessProcess()
    await process.start(config(tmp_path))
    try:
        pending = await process.request("session.get", {"empty_error_code": True, "delay": 0.15}, "o", "a", 0.04)
        assert pending["outcome"] == "accepted_pending"
        result = await settled(process, pending["request_id"])
        assert result["outcome"] == "committed_reference"
        assert result["result"]["command"] == "session.get"
    finally:
        assert (await process.close(2))["state"] == "closed"


@pytest.mark.parametrize("operation_id", ["has space", "x" * 257])
async def test_invalid_contract_identifier_is_rejected_without_child_dispatch(tmp_path, operation_id):
    process = ManagedHarnessProcess()
    await process.start(config(tmp_path))
    try:
        result = await process.request("session.get", {}, operation_id, "1", 0.04)
        assert result["outcome"] == "rejected_before_admission"
        assert result["error"]["code"] == "invalid_request"
        status = await process.request("host.status", {}, "status", "1", 1)
        assert status["result"]["received"].get("session.get", 0) == 0
    finally:
        assert (await process.close(2))["state"] == "closed"


@pytest.mark.parametrize("variant", ["bodyless_ack", "nullable_error"])
async def test_shared_contract_optional_reply_fields_are_accepted(tmp_path, variant):
    process = ManagedHarnessProcess()
    await process.start(config(tmp_path))
    try:
        response = await process.request("session.get", {"valid_reply_variant": variant, "delay": 0.15}, "o", "a", 0.04)
        assert response["admission"] == "host_accepted"
        assert response["outcome"] == ("accepted_pending" if variant == "bodyless_ack" else "committed_reference")
        result = await settled(process, response["request_id"])
        assert result["outcome"] == "committed_reference"
        assert result["result"]["command"] == "session.get"
    finally:
        assert (await process.close(2))["state"] == "closed"


async def test_observation_timeout_retains_later_reply_without_resending(tmp_path):
    process = ManagedHarnessProcess()
    await process.start(config(tmp_path))
    try:
        pending = await process.request("session.prompt", {"delay": 0.15}, "o", "a", 0.01)
        assert pending["outcome"] == "accepted_pending"
        status = await process.request("host.status", {}, "status", "a", 1)
        assert status["result"]["received"]["session.prompt"] == 1
        result = await settled(process, pending["request_id"])
        assert result["outcome"] == "committed_reference"
        assert result["request_id"] == pending["request_id"]
        assert await process.query_result("unknown") is None
    finally:
        await process.close(2)


async def test_full_child_input_pipe_does_not_extend_request_or_close_deadline(tmp_path):
    process = ManagedHarnessProcess()
    await process.start(config(tmp_path, boot_settings={"test": {"read_delay": 0.3}}))
    try:
        async with asyncio.timeout(0.15):
            pending = await process.request("session.prompt", {"text": "x" * 200000}, "o", "a", 0.01)
            assert pending["outcome"] == "accepted_pending"
            blocked = await process.close(0.01)
            assert blocked["state"] == "blocked"
        assert (await process.close(2))["state"] == "closed"
        assert (await process.query_result(pending["request_id"]))["outcome"] == "committed_reference"
    finally:
        await process.close(2)


async def test_data_pressure_reserves_control_capacity_and_keeps_every_reply(tmp_path):
    process = ManagedHarnessProcess()
    await process.start(config(tmp_path, max_inflight=2))
    try:
        pending = [await process.request("session.prompt", {"hold": True}, f"o-{i}", "a", 0)
                   for i in range(2)]
        rejected = await process.request("session.create", {}, "overload", "a", 1)
        assert rejected["outcome"] == "rejected_before_admission"
        assert rejected["error"]["code"] == "overloaded"
        status = await process.request("host.status", {}, "status", "a", 1)
        assert status["result"]["received"].get("session.create", 0) == 0
        cancelled = await process.request("session.cancel", {}, "cancel", "a", 1)
        assert cancelled["outcome"] == "cancelled_settled"
        for response in pending:
            assert (await settled(process, response["request_id"]))["outcome"] == "cancelled_settled"
        next_request = await process.request("session.get", {}, "next", "a", 1)
        assert next_request["outcome"] == "committed_reference"
    finally:
        await process.close(2)


async def test_child_exit_marks_all_pending_uncertain_and_preserves_committed_reply(tmp_path):
    process = ManagedHarnessProcess()
    await process.start(config(tmp_path))
    completed = await process.request("session.get", {}, "done", "a", 1)
    pending = await process.request("session.prompt", {"hold": True}, "held", "a", 0)
    crashed = await process.request("session.prompt", {"exit": True}, "crash", "a", 1)
    assert crashed["outcome"] == "uncertain_after_disconnect"
    assert (await process.query_result(pending["request_id"]))["outcome"] == "uncertain_after_disconnect"
    assert await process.query_result(completed["request_id"]) == completed
    rejected = await process.request("session.create", {}, "after-exit", "a", 1)
    assert rejected["outcome"] == "rejected_before_admission"
    assert (await process.close(1))["outcome"] == "uncertain_after_disconnect"


async def test_close_timeout_retains_live_ownership_until_later_close_settles(tmp_path):
    process = ManagedHarnessProcess()
    await process.start(config(tmp_path, boot_settings={"test": {"close_delay": 0.3}}))
    try:
        pending = await process.request("session.prompt", {"hold": True}, "held", "a", 0)
        async with asyncio.timeout(0.2):
            blocked = await process.close(0.01)
        assert blocked["state"] == "blocked"
        assert blocked["outcome"] == "uncertain_after_disconnect"
        status = await process.request("host.status", {}, "status", "a", 1)
        assert status["outcome"] == "committed_reference"
        rejected = await process.request("session.create", {}, "new", "a", 1)
        assert rejected["outcome"] == "rejected_before_admission"
        closed = await process.close(2)
        assert closed["state"] == "closed"
        assert closed["outcome"] == "cancelled_settled"
        assert (await process.query_result(pending["request_id"]))["outcome"] == "cancelled_settled"
    finally:
        await process.close(2)


@pytest.mark.parametrize("command,payload,expected", [
    ("shell.execute", {}, "invalid_request"),
    ("session.prompt", ["unstructured"], "invalid_request"),
    ("session.prompt", {"value": float("nan")}, "invalid_request"),
    ("session.prompt", {"text": "x" * 1024}, "frame_too_large"),
])
async def test_invalid_or_oversized_request_is_rejected_before_child_admission(
        tmp_path, command, payload, expected):
    process = ManagedHarnessProcess()
    await process.start(config(tmp_path, max_frame_bytes=1024))
    try:
        rejected = await process.request(command, payload, "invalid", "a", 0.1)
        assert rejected["outcome"] == "rejected_before_admission"
        assert rejected["error"]["code"] == expected
        status = await process.request("host.status", {}, "status", "a", 1)
        assert status["result"]["received"] == {"host.status": 1}
    finally:
        await process.close(2)


async def test_foreign_generation_identities_and_invalid_reply_shapes_cannot_resolve_request(tmp_path):
    process = ManagedHarnessProcess()
    await process.start(config(tmp_path))
    try:
        pending = await process.request("session.get", {"poison_replies": True, "delay": 0.1},
                                        "operation", "attempt", 0.02)
        assert pending["outcome"] == "accepted_pending"
        result = await settled(process, pending["request_id"])
        assert result["outcome"] == "committed_reference"
        assert result["result"]["command"] == "session.get"
    finally:
        await process.close(2)


@pytest.mark.parametrize("overrides", [
    {"node_executable": Path("node.exe")},
    {"host_entry": Path("host.mjs")},
    {"profile_root": Path("ambient-profile")},
    {"boot_settings": {"token": "override"}},
    {"max_inflight": 0},
    {"max_control_inflight": 0},
    {"max_frame_bytes": 0},
    {"profile_id": ""},
    {"start_timeout": float("inf")},
])
async def test_invalid_boot_configuration_is_rejected_without_launch(tmp_path, overrides, monkeypatch):
    from dataclasses import replace

    process = ManagedHarnessProcess()
    monkeypatch.chdir(tmp_path)
    try:
        with pytest.raises(ValueError):
            await process.start(replace(config(tmp_path), **overrides))
    finally:
        await process.close(2)


@pytest.mark.parametrize("malformed", ["oversized", "utf8", "json", "truncated", "nan", "surrogate", "overflow"])
async def test_broken_or_oversized_child_frame_preserves_uncertainty(tmp_path, malformed):
    process = ManagedHarnessProcess()
    await process.start(config(tmp_path, max_frame_bytes=1024))
    try:
        result = await process.request("session.get", {"bad_frame": malformed}, "o", "a", 1)
        assert result["outcome"] == "uncertain_after_disconnect"
        assert await process.query_result(result["request_id"]) == result
        assert (await process.close(1))["outcome"] == "uncertain_after_disconnect"
    finally:
        await process.close(2)


async def test_readiness_timeout_retains_ownership_and_rejects_early_data(tmp_path):
    process = ManagedHarnessProcess()
    try:
        with pytest.raises(HarnessProcessError):
            await process.start(config(tmp_path, start_timeout=0.02,
                                boot_settings={"test": {"ready_delay": 0.3}}))
        result = await process.request("session.create", {}, "early", "a", 1)
        assert result["outcome"] == "rejected_before_admission"
        with pytest.raises(HarnessProcessError):
            await process.start(config(tmp_path))
        status = await process.request("host.status", {}, "status", "a", 1)
        assert status["outcome"] == "committed_reference"
        assert (await process.close(2))["state"] == "closed"
    finally:
        await process.close(2)


async def test_child_environment_has_owned_roots_no_ambient_credentials_and_no_console(tmp_path, monkeypatch):
    for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "NODE_OPTIONS", "NODE_PATH",
                "RENULUS_HARNESS_BOOT", "RENULUS_AMBIENT_TEST_SETTING"):
        monkeypatch.setenv(key, "synthetic-do-not-inherit")
    process = ManagedHarnessProcess()
    await process.start(config(tmp_path, boot_settings={"test": {"explicit_setting": "opt-in"}}))
    try:
        response = await process.request("session.get", {"environment": True}, "env", "a", 1)
        result = response["result"]
        assert set(result["names"]).isdisjoint({"OPENAI_API_KEY", "ANTHROPIC_API_KEY",
                "NODE_OPTIONS", "NODE_PATH", "RENULUS_AMBIENT_TEST_SETTING"})
        assert result["explicit_setting"] == "opt-in"
        assert Path(result["path"]) == Path(sys.executable).parent
        root = (tmp_path / "profile").resolve()
        assert Path(result["cwd"]) == Path(result["root"]) == root
        assert all(value is not None and Path(value).is_relative_to(root)
                   for value in result["paths"].values())
        assert result["console"] is False
    finally:
        await process.close(2)


async def test_terminal_reply_is_stable_across_duplicate_or_late_pending_frames(tmp_path):
    process = ManagedHarnessProcess()
    await process.start(config(tmp_path))
    try:
        original = await process.request("session.get", {"duplicate_reply": True}, "o", "a", 1)
        await process.request("host.status", {}, "barrier", "a", 1)
        assert await process.query_result(original["request_id"]) == original
    finally:
        await process.close(2)


@pytest.mark.parametrize("budget,count", [("records", 2), ("bytes", 1)])
async def test_retained_results_bound_lifetime_admission_without_eviction(tmp_path, budget, count):
    process = ManagedHarnessProcess()
    await process.start(config(tmp_path, max_frame_bytes=1024,
                               max_result_records=2 if budget == "records" else 100,
                               max_result_bytes=4096 if budget == "records" else 2500))
    try:
        completed = [await process.request("session.get", {}, f"o{i}", "a", 1)
                     for i in range(count)]
        assert all(result["outcome"] == "committed_reference" for result in completed)
        for _ in range(25):
            rejected = await process.request("session.create", {}, "full", "a", 1)
            assert rejected["outcome"] == "rejected_before_admission"
            assert rejected["error"]["code"] == "result_capacity"
            assert await process.query_result(rejected["request_id"]) is None
        for result in completed:
            assert await process.query_result(result["request_id"]) == result
        status = await process.request("host.status", {}, "control", "a", 1)
        assert status["outcome"] == "committed_reference"
    finally:
        assert (await process.close(2))["state"] == "closed"


async def test_timeout_distinguishes_sent_unacknowledged_from_host_accepted(tmp_path):
    process = ManagedHarnessProcess()
    await process.start(config(tmp_path, boot_settings={"test": {"read_delay": 0.2}}))
    try:
        pending = await process.request("session.prompt", {"hold": True, "acknowledge": True},
                                        "o", "a", 0.01)
        assert pending["outcome"] == "accepted_pending"
        assert pending["admission"] == "sent_unacknowledged"
        assert pending["observation"] == "timeout"
        await process.request("host.status", {}, "barrier", "a", 1)
        acknowledged = await process.query_result(pending["request_id"])
        assert acknowledged["outcome"] == "accepted_pending"
        assert acknowledged["admission"] == "host_accepted"
        await process.request("session.cancel", {}, "cancel", "a", 1)
        assert (await settled(process, pending["request_id"]))["outcome"] == "cancelled_settled"
    finally:
        await process.close(2)


async def test_one_transport_owns_one_generation_and_cannot_accumulate_restarts(tmp_path):
    process = ManagedHarnessProcess()
    first = await process.start(config(tmp_path))
    assert (await process.close(2))["state"] == "closed"
    try:
        with pytest.raises(HarnessProcessError):
            await process.start(config(tmp_path))
    finally:
        await process.close(2)
    reopened = ManagedHarnessProcess()
    second = await reopened.start(config(tmp_path))
    try:
        assert first["generation"] != second["generation"]
    finally:
        await reopened.close(2)


async def test_request_before_start_is_explicitly_rejected_without_side_effects():
    process = ManagedHarnessProcess()
    result = await process.request("session.create", {}, "o", "a", 1)
    assert result["outcome"] == "rejected_before_admission"
    assert result["error"]["code"] == "not_started"
    assert await process.query_result(result["request_id"]) is None
    assert (await process.close(0))["state"] == "closed"


async def test_concurrent_start_cannot_launch_two_children_for_one_transport(tmp_path):
    process = ManagedHarnessProcess()
    try:
        outcomes = await asyncio.gather(process.start(config(tmp_path, start_timeout=0.5)),
                                        process.start(config(tmp_path, start_timeout=0.5)),
                                        return_exceptions=True)
        assert sum(isinstance(result, dict) and result["state"] == "ready"
                   for result in outcomes) == 1
        assert sum(isinstance(result, HarnessProcessError) for result in outcomes) == 1
    finally:
        await process.close(2)


async def test_readiness_requires_a_state_and_preserves_policy_blocked_state(tmp_path):
    process = ManagedHarnessProcess()
    try:
        result = await process.start(config(tmp_path, boot_settings={"test": {
            "ready_delay": 0.1, "malformed_ready": True, "ready_state": "policy_blocked"}}))
        assert result["state"] == "policy_blocked"
    finally:
        await process.close(2)


async def test_close_during_subprocess_creation_cannot_report_settled_then_admit_work(tmp_path):
    process = ManagedHarnessProcess()
    starting = asyncio.create_task(process.start(config(tmp_path)))
    await asyncio.sleep(0)
    try:
        closed = await process.close(2)
        await asyncio.gather(starting, return_exceptions=True)
        result = await process.request("session.create", {}, "after-close", "a", 1)
        assert closed["state"] == "closed"
        assert result["outcome"] == "rejected_before_admission"
    finally:
        await process.close(2)


async def test_compact_numeric_reply_does_not_expand_retained_bytes_and_block_spare_capacity(tmp_path):
    process = ManagedHarnessProcess()
    await process.start(config(tmp_path, max_frame_bytes=1024, max_result_bytes=4000))
    try:
        response = await process.request("session.get", {"compact_numbers": True}, "n", "a", 1)
        assert response["result"]["values"] == [1000000000000000] * 100
        second = await process.request("session.get", {}, "next", "a", 1)
        assert second["outcome"] == "committed_reference"
        assert await process.query_result(response["request_id"]) == response
        assert "token" not in response
    finally:
        await process.close(2)


async def test_direct_close_request_is_recognized_by_later_process_close(tmp_path):
    process = ManagedHarnessProcess()
    await process.start(config(tmp_path))
    try:
        result = await process.request("host.close", {}, "explicit-close", "a", 1)
        assert result["outcome"] == "cancelled_settled"
        await asyncio.sleep(0.05)
        assert (await process.close(2))["state"] == "closed"
    finally:
        await process.close(2)


async def test_child_starts_only_after_paired_selection_is_prepared_with_pending_validation(tmp_path):
    process = ManagedHarnessProcess()
    await process.start(config(tmp_path))
    try:
        response = await process.request("session.get", {"prepared_manifest": True}, "manifest", "a", 1)
        result = response["result"]
        manifest = result["manifest"]
        assert result["domain_store_id"] == "synthetic-domain-store"
        assert result["domain_path"] == "state/renulus.sqlite"
        assert manifest["profile_id"] == "synthetic-profile"
        assert manifest["state"] == "prepared"
        assert manifest["domain_store"]["store_id"] == "synthetic-domain-store"
        assert manifest["domain_store"]["validation"] == "pending"
        assert manifest["runtime_store"]["store_id"] == "synthetic-store"
        assert manifest["runtime_store"]["validation"] == "pending"
        assert manifest["runtime_store"]["path"] == "state/harness/opencode.sqlite"
        assert manifest["cohort_source"] == "4b6fea2875e4f2e3e8a8fee181803e54f7056845"
    finally:
        await process.close(2)
