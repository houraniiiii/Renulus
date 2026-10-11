"""Reverse callbacks at the public owned Harness subprocess boundary."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import threading
import pytest

from renulus.runtime.harness_process import HarnessProcessConfig, ManagedHarnessProcess


def config(tmp_path, **settings):
    return HarnessProcessConfig(
        node_executable=Path(sys.executable),
        host_entry=Path(__file__).parent / "fixtures/domain_child.py",
        profile_root=tmp_path / "profile", profile_id="synthetic-profile",
        store_id="synthetic-runtime", domain_store_id="synthetic-domain",
        domain_path="state/renulus.sqlite", **settings,
    )


async def test_awaited_domain_callback_can_prompt_while_outer_request_waits(tmp_path):
    from renulus.runtime.harness_domain import DomainBinding, DomainGrant

    binding = DomainBinding("learning-1", "attempt-1", "native-session",
                            "native-input", "parent-cancel-1")
    process = None
    loop = asyncio.get_running_loop()
    pool = ThreadPoolExecutor(max_workers=1)

    async def handler(request, cancellation):
        cancellation.check_current()
        def extract():
            # Exactly one CPU slot awaits the live owning loop, never a new loop.
            future = asyncio.run_coroutine_threadsafe(process.request(
                "session.prompt", {"text": "Extract CKD learning"}, "extraction-1", "attempt-1", 2), loop)
            return future.result(timeout=3)
        nested = await loop.run_in_executor(pool, extract)
        cancellation.check_current()
        return {"answer": nested["result"]["text"]}

    async def authorize(request):
        return DomainGrant(binding, handler, lambda: True)

    process = ManagedHarnessProcess(domain_authority=authorize)
    await process.start(config(tmp_path, max_inflight=2, max_domain_inflight=1))
    try:
        response = await process.request("session.get", {}, "observe", "1", 2)
        assert response["result"]["domain"]["result"] == {
            "answer": "Synthetic extraction result."}
        assert process.domain_result("callback-1")["outcome"] == "committed_reference"
        assert process.domain_status()["active"] == 0
    finally:
        assert (await process.close(2))["state"] == "closed"
        pool.shutdown(wait=True)


async def test_close_and_process_death_keep_cpu_and_finalizer_owned_after_cancel(tmp_path):
    from renulus.runtime.harness_domain import DomainBinding, DomainGrant

    binding = DomainBinding("learning-1", "attempt-1", "native-session",
                            "native-input", "parent-cancel-1")
    entered = threading.Event()
    release = threading.Event()
    cleanup = asyncio.Event()
    finish_cleanup = asyncio.Event()

    def worker():
        entered.set()
        assert release.wait(5)
        return {"secret": "must never publish after cancel"}

    async def handler(request, cancellation):
        try:
            return await asyncio.to_thread(worker)
        finally:
            cleanup.set()
            await finish_cleanup.wait()

    async def authorize(request):
        return DomainGrant(binding, handler, lambda: True)

    process = ManagedHarnessProcess(domain_authority=authorize)
    await process.start(config(tmp_path))
    try:
        await process.request("session.get", {}, "observe", "1", 0.01)
        async with asyncio.timeout(2):
            while not entered.is_set():
                await asyncio.sleep(0.01)
        assert process.cancel_domain("parent-cancel-1") == 1
        assert (await process.close(0.1))["state"] == "blocked"
        assert (await process.settlement(0.01))["state"] == "pending"
        assert process.domain_status()["active"] == 1
        release.set()
        await asyncio.wait_for(cleanup.wait(), 2)
        assert (await process.settlement(0.01))["state"] == "pending"
        finish_cleanup.set()
        assert (await process.settlement(2))["state"] == "settled"
        result = process.domain_result("callback-1")
        assert result["outcome"] == "cancelled_settled"
        assert "result" not in result
        assert process.domain_status()["active"] == 0
    finally:
        release.set()
        finish_cleanup.set()
        await process.close(2)


async def wait_domain(process, callback_id):
    async with asyncio.timeout(2):
        while True:
            value = process.domain_result(callback_id)
            if value and value["outcome"] != "accepted_pending":
                return value
            await asyncio.sleep(0.01)


async def test_duplicates_cannot_repeat_an_effect_and_conflicts_are_rejected(tmp_path):
    from renulus.runtime.harness_domain import DomainBinding, DomainGrant

    binding = DomainBinding("learning-1", "attempt-1", "native-session",
                            "native-input", "parent-cancel-1")
    admitted = []

    async def handler(request, cancellation):
        admitted.append(request.payload["topic"])
        await asyncio.sleep(0.03)
        return {"topic": request.payload["topic"]}

    async def authorize(request):
        return DomainGrant(binding, handler, lambda: True)

    process = ManagedHarnessProcess(domain_authority=authorize)
    await process.start(config(tmp_path))
    try:
        await process.request("session.get", {"emit_only": True, "callbacks": [
            {}, {}, {"payload": {"topic": "dialysis"}},
        ]}, "observe", "1", 2)
        await wait_domain(process, "callback-1")
        # A later identical callback observes the original result only.
        await process.request("session.get", {"emit_only": True}, "replay", "1", 2)
        status = await process.request("host.status", {}, "status", "1", 2)
        assert admitted == ["CKD"]
        assert any(value.get("error", {}).get("code") == "callback_id_conflict"
                   for value in status["result"]["domain_results"])
        assert process.domain_result("callback-1")["result"] == {"topic": "CKD"}
    finally:
        await process.close(2)


async def test_callback_capacity_does_not_consume_control_or_evict_results(tmp_path):
    from renulus.runtime.harness_domain import DomainBinding, DomainGrant

    binding = DomainBinding("learning-1", "attempt-1", "native-session",
                            "native-input", "parent-cancel-1")
    entered = asyncio.Event()
    release = asyncio.Event()

    async def handler(request, cancellation):
        entered.set()
        await release.wait()
        return {"accepted": request.callback_id}

    async def authorize(request):
        return DomainGrant(binding, handler, lambda: True)

    process = ManagedHarnessProcess(domain_authority=authorize)
    await process.start(config(tmp_path, max_domain_inflight=1,
                               max_domain_result_records=1, max_domain_result_bytes=12000,
                               max_frame_bytes=4096))
    try:
        await process.request("session.get", {"emit_only": True}, "observe", "1", 2)
        await asyncio.wait_for(entered.wait(), 2)
        await process.request("session.get", {"emit_only": True,
                                               "callback_id": "overloaded"}, "overload", "1", 2)
        status = await process.request("host.status", {}, "status", "1", 2)
        assert any(value.get("error", {}).get("code") == "domain_overloaded"
                   for value in status["result"]["domain_results"])
        release.set()
        await wait_domain(process, "callback-1")
        await process.request("session.get", {"emit_only": True,
                                               "callback_id": "no-result-room"}, "capacity", "1", 2)
        status = await process.request("host.status", {}, "status", "1", 2)
        assert any(value.get("error", {}).get("code") == "domain_result_capacity"
                   for value in status["result"]["domain_results"])
        assert process.domain_result("callback-1")["result"] == {"accepted": "callback-1"}
        assert process.domain_result("overloaded") is None
        assert process.domain_status()["retained"] == 1
        assert process.domain_status()["bytes"] <= 12000
        assert (await process.close(2))["state"] == "closed"
    finally:
        release.set()
        await process.close(2)


async def test_actual_node_pump_roundtrip_awaits_a_domain_handler_with_nested_prompt(tmp_path):
    from renulus.runtime.harness_domain import DomainBinding, DomainGrant

    node = Path("C:/Renulus/scratch/ocf/tools/node-v26.4.0-win-x64/node.exe")
    if not node.is_file():
        pytest.skip("Reviewed Node 26.4.0 artifact unavailable.")
    binding = DomainBinding("learning-1", "attempt-1", "native-session",
                            "native-input", "parent-cancel-1")
    async def handler(request, cancellation):
        response = await process.request("session.prompt", {
            "session_id": "extraction-session", "text": "Extract learner observation",
            "configuration_id": "synthetic"}, "extraction", "1", 2)
        return {"answer": response["result"]["text"]}

    async def authority(request):
        return DomainGrant(binding, handler, lambda: True)

    process = ManagedHarnessProcess(domain_authority=authority)
    options = config(tmp_path)
    from dataclasses import replace
    options = replace(options, node_executable=node, host_entry=Path(__file__).resolve().parents[2]
                      / "packages/harness/test/fixtures/domain-host.mjs")
    await process.start(options)
    try:
        response = await process.request("session.get", {"session_id": "native-session"}, "observe", "1", 2)
        domain = response["result"]["session"]["domain"]
        assert domain["result"] == {"answer": "Synthetic extraction result."}
        status = await process.request("host.status", {}, "status", "1", 2)
        assert status["result"]["calls"] == 1
        assert status["result"]["callbacks"]["active"] == 0
    finally:
        assert (await process.close(2))["state"] == "closed"


@pytest.mark.parametrize("key", ["profile_id", "store_id", "generation", "token",
                               "operation_id", "attempt_id", "session_id", "input_id", "cancellation_id"])
async def test_foreign_transport_and_execution_bindings_cannot_dispatch(tmp_path, key):
    from renulus.runtime.harness_domain import DomainBinding, DomainGrant

    binding = DomainBinding("learning-1", "attempt-1", "native-session",
                            "native-input", "parent-cancel-1")
    visible = []
    async def handler(request, cancellation):
        visible.append(request.callback_id)
        return {"reference": "synthetic-reference"}
    async def authorize(request):
        return DomainGrant(binding, handler, lambda: True)

    process = ManagedHarnessProcess(domain_authority=authorize)
    await process.start(config(tmp_path))
    try:
        await process.request("session.get", {"emit_only": True, "callbacks": [
            {key: "foreign", "callback_id": "poisoned"}, {"callback_id": "valid"},
        ]}, "observe", "1", 2)
        await wait_domain(process, "valid")
        assert visible == ["valid"]
        assert process.domain_result("valid")["result"] == {"reference": "synthetic-reference"}
    finally:
        await process.close(2)


async def test_current_guard_is_checked_before_work_and_before_result_publication(tmp_path):
    from renulus.runtime.harness_domain import DomainBinding, DomainGrant

    binding = DomainBinding("learning-1", "attempt-1", "native-session",
                            "native-input", "parent-cancel-1")
    eligible = False
    entered = asyncio.Event()
    release = asyncio.Event()
    async def handler(request, cancellation):
        entered.set()
        await release.wait()
        return {"private": "stale learning text"}
    async def authorize(request):
        return DomainGrant(binding, handler, lambda: eligible)

    process = ManagedHarnessProcess(domain_authority=authorize)
    await process.start(config(tmp_path))
    try:
        initial = await process.request("session.get", {}, "observe", "1", 2)
        assert initial["result"]["domain"]["error"]["code"] == "domain_cancelled"
        assert not entered.is_set()
        eligible = True
        await process.request("session.get", {"emit_only": True, "callback_id": "later"}, "next", "1", 2)
        await asyncio.wait_for(entered.wait(), 2)
        eligible = False
        release.set()
        result = await wait_domain(process, "later")
        assert "result" not in result
        assert result["error"]["code"] == "domain_cancelled"
    finally:
        release.set()
        await process.close(2)


@pytest.mark.parametrize("value", [{"number": float("inf")}, {"text": "x" * 5000}])
async def test_invalid_or_oversized_handler_result_retains_structured_failure(tmp_path, value):
    from renulus.runtime.harness_domain import DomainBinding, DomainGrant

    binding = DomainBinding("learning-1", "attempt-1", "native-session",
                            "native-input", "parent-cancel-1")
    async def handler(request, cancellation):
        return value
    async def authority(request):
        return DomainGrant(binding, handler, lambda: True)
    process = ManagedHarnessProcess(domain_authority=authority)
    await process.start(config(tmp_path, max_frame_bytes=4096))
    try:
        response = await process.request("session.get", {}, "observe", "1", 2)
        assert response["result"]["domain"]["error"]["code"] == "domain_invalid_result"
        assert process.domain_status()["active"] == 0
        assert "result" not in process.domain_result("callback-1")
    finally:
        await process.close(2)


async def test_queued_result_rechecks_authority_when_pipe_capacity_becomes_available(tmp_path):
    from renulus.runtime.harness_domain import DomainBinding, DomainGrant

    binding = DomainBinding("learning-1", "attempt-1", "native-session",
                            "native-input", "parent-cancel-1")
    entered = asyncio.Event()
    release = asyncio.Event()
    async def handler(request, cancellation):
        entered.set()
        await release.wait()
        return {"private": "queued before revocation"}
    async def authority(request):
        return DomainGrant(binding, handler, lambda: True)

    process = ManagedHarnessProcess(domain_authority=authority)
    await process.start(config(tmp_path, boot_settings={"test": {"read_pause": 0.4}}))
    try:
        await process.request("session.get", {"emit_only": True}, "observe", "1", 0.01)
        await asyncio.wait_for(entered.wait(), 2)
        # The synthetic peer pauses input while this large frame fills its pipe.
        await process.request("session.prompt", {"text": "x" * 200000}, "extraction", "1", 0.01)
        release.set()
        await wait_domain(process, "callback-1")
        process.cancel_domain("parent-cancel-1")
        async with asyncio.timeout(2):
            while True:
                status = await process.request("host.status", {}, "status", "1", 2)
                outcomes = status["result"]["domain_results"]
                if outcomes:
                    break
                await asyncio.sleep(0.01)
        assert outcomes[0]["outcome"] == "cancelled_settled"
        assert "result" not in outcomes[0]
    finally:
        release.set()
        await process.close(2)


async def test_domain_errors_preserve_api_code_without_python_message_or_data(tmp_path):
    from renulus.contracts import ApiError
    from renulus.runtime.harness_domain import DomainBinding, DomainGrant

    binding = DomainBinding("learning-1", "attempt-1", "native-session",
                            "native-input", "parent-cancel-1")
    async def handler(request, cancellation):
        raise ApiError("library_source_not_ready", "Private synthetic document name", 409, True)
    async def authority(request):
        return DomainGrant(binding, handler, lambda: True)
    process = ManagedHarnessProcess(domain_authority=authority)
    await process.start(config(tmp_path))
    try:
        response = await process.request("session.get", {}, "observe", "1", 2)
        assert response["result"]["domain"]["error"] == {"code": "library_source_not_ready",
                                                         "status": 409, "retryable": True}
    finally:
        await process.close(2)


async def test_native_session_recovery_lookup_uses_authenticated_operation_only(tmp_path):
    from dataclasses import replace
    node = Path("C:/Renulus/scratch/ocf/tools/node-v26.4.0-win-x64/node.exe")
    if not node.is_file():
        pytest.skip("Reviewed Node artifact unavailable.")
    options = replace(config(tmp_path), node_executable=node,
                      host_entry=Path(__file__).resolve().parents[2]
                      / "packages/harness/test/fixtures/domain-host.mjs")
    process = ManagedHarnessProcess()
    await process.start(options)
    try:
        recovered = await process.request("session.find", {}, "original-run", "1", 2)
        assert recovered["result"]["sessions"] == [{"id": "recovered-native-session",
                                                     "operationId": "original-run"}]
        unknown = await process.request("session.find", {}, "unknown-run", "1", 2)
        assert unknown["result"]["sessions"] == []
        duplicate = await process.request("session.find", {}, "duplicate-run", "1", 2)
        assert duplicate["outcome"] == "rejected_before_admission"
        assert duplicate["error"]["code"] == "harness_session_identity_conflict"
        forged = await process.request("session.find", {"operation_id": "model-target"}, "original-run", "1", 2)
        assert forged["outcome"] == "rejected_before_admission"
        status = await process.request("host.status", {}, "status", "1", 2)
        assert status["result"]["calls"] == 0
    finally:
        assert (await process.close(2))["state"] == "closed"
