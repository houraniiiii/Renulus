"""Actual native Library tool, private pipes and an owned Python CPU callback."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import threading

import pytest

from renulus.runtime.harness_domain import DomainBinding, DomainGrant
from renulus.runtime.harness_process import HarnessProcessConfig, ManagedHarnessProcess


NODE = Path("C:/Renulus/scratch/ocf/tools/node-v26.4.0-win-x64/node.exe")
FIXTURE = Path(__file__).resolve().parents[2] / "packages/harness/test/fixtures/native-domain-host.mjs"
PASSAGE = {
    "id": "passage_" + "1" * 32, "document_id": "doc_" + "2" * 32,
    "document_revision": "rev_" + "3" * 32,
    "text": "Synthetic eligible CKD educational passage.",
    "locators": [{"page": 2, "bbox": [0.1, 0.2, 0.3, 0.4]}],
}


def config(tmp_path):
    if not NODE.is_file():
        pytest.skip("Reviewed Node artifact unavailable.")
    return HarnessProcessConfig(node_executable=NODE, host_entry=FIXTURE,
        profile_root=tmp_path / "profile", profile_id="synthetic-profile",
        store_id="synthetic-runtime", domain_store_id="synthetic-domain",
        domain_path="state/renulus.sqlite", max_inflight=1, max_domain_inflight=1)


async def command(process, name, payload, operation, timeout=5):
    result = await process.request(name, payload, operation, "attempt-1", timeout)
    if result["outcome"] == "accepted_pending":
        async with asyncio.timeout(5):
            while result["outcome"] == "accepted_pending":
                await asyncio.sleep(0.01)
                result = await process.query_result(result["request_id"])
    assert result["outcome"] == "committed_reference", result
    return result["result"]


async def start_turn(process):
    await command(process, "host.activate", {"configuration_id": "synthetic"}, "activate")
    extraction = await command(process, "session.create", {"title": "Synthetic extraction"}, "extraction")
    learning = await command(process, "session.create", {"title": "Synthetic CKD learning"}, "learning")
    receipt = await command(process, "session.prompt", {
        "configuration_id": "synthetic", "session_id": learning["session"]["id"],
        "text": "Explain CKD with a Library passage."}, "learning")
    return learning["session"]["id"], extraction["session"]["id"], receipt


async def messages_containing(process, session_id, text):
    async with asyncio.timeout(5):
        while True:
            messages = await command(process, "session.messages", {"session_id": session_id}, "observe")
            if text in json.dumps(messages):
                return messages
            await asyncio.sleep(0.01)


async def thread_entered(event):
    async with asyncio.timeout(5):
        while not event.is_set():
            await asyncio.sleep(0.01)


async def test_native_library_callback_awaits_one_cpu_slot_nested_prompt(tmp_path):
    loop = asyncio.get_running_loop()
    admitted = asyncio.Event()
    entered, release = threading.Event(), threading.Event()
    handled = asyncio.Event()
    trusted = {}
    published = []
    guard_checks = []
    pool = ThreadPoolExecutor(max_workers=1)

    def current():
        guard_checks.append(True)
        return True

    async def handler(request, cancellation):
        assert request.command == "library.retrieve"
        assert request.payload == {"command": "library.retrieve",
            "arguments": {"query": "CKD", "limit": 1},
            "envelope": {"sessionId": trusted["binding"].session_id,
                "operationId": "learning", "attemptId": "attempt-1",
                "scope": {"kind": "study"}, "revisionIds": [PASSAGE["document_revision"]],
                "policyRevision": 0, "contextEpoch": 0, "cancellationEpoch": 0}}

        async def native_extraction():
            await command(process, "session.prompt", {"configuration_id": "synthetic",
                "session_id": trusted["extraction"], "text": "Extract CKD learning."}, "extraction")
            return await messages_containing(process, trusted["extraction"], "Synthetic extraction complete.")

        def worker():
            entered.set()
            assert release.wait(5)
            return asyncio.run_coroutine_threadsafe(native_extraction(), loop).result(timeout=8)

        try:
            cancellation.check_current()
            extracted = await loop.run_in_executor(pool, worker)
            assert "Synthetic extraction complete." in json.dumps(extracted)
            # Synthetic local commit seam: the owner still guards publication.
            cancellation.check_current()
            published.append(PASSAGE)
            return {"status": "ready", "passages": [PASSAGE]}
        finally:
            handled.set()

    async def authority(request):
        await admitted.wait()
        assert request.binding == trusted["binding"]
        return DomainGrant(trusted["binding"], handler, current)

    process = ManagedHarnessProcess(domain_authority=authority)
    await process.start(config(tmp_path))
    try:
        learning, extraction, receipt = await start_turn(process)
        trusted.update(binding=DomainBinding("learning", "attempt-1", learning, receipt["inputId"], "learning"),
                       extraction=extraction)
        admitted.set()
        await thread_entered(entered)
        status = await command(process, "host.status", {}, "control")
        assert learning in status["activeSessionIds"]
        assert status["synthetic"]["callback"]["active"] == 1
        assert status["synthetic"]["native"]["messageID"] != receipt["inputId"]
        assert status["synthetic"]["binding"] == trusted["binding"].__dict__
        assert status["synthetic"]["modelRequests"] == 1
        release.set()
        await asyncio.wait_for(handled.wait(), 8)
        messages = await messages_containing(process, learning, "Synthetic cited CKD explanation [1].")
        assert PASSAGE["text"] in json.dumps(messages)
        assert published == [PASSAGE]
        status = await command(process, "host.status", {}, "control")
        assert status["synthetic"]["modelRequests"] == 3
        assert status["synthetic"]["dependencies"] == [{"document_id": PASSAGE["document_id"],
            "document_revision": PASSAGE["document_revision"], "passage_id": PASSAGE["id"],
            "locators": PASSAGE["locators"]}]
        assert status["synthetic"]["checks"] == ["before_read", "before_return", "before_return"]
        assert len(guard_checks) >= 5
        found = await command(process, "session.find", {}, "learning")
        assert [item["id"] for item in found["sessions"]] == [learning]
    finally:
        release.set()
        admitted.set()
        assert (await process.close(8))["state"] == "closed"
        pool.shutdown(wait=True)


@pytest.mark.parametrize("race_close", [False, True])
async def test_native_cancellation_and_close_retain_python_cpu_and_finalizer(tmp_path, race_close):
    admitted, finalizing, finalized = asyncio.Event(), asyncio.Event(), asyncio.Event()
    entered, release = threading.Event(), threading.Event()
    trusted = {}
    pool = ThreadPoolExecutor(max_workers=1)
    loop = asyncio.get_running_loop()

    def worker():
        entered.set()
        assert release.wait(8)
        return {"status": "ready", "passages": [PASSAGE]}

    async def handler(request, cancellation):
        try:
            return await loop.run_in_executor(pool, worker)
        finally:
            finalizing.set()
            await finalized.wait()

    async def authority(request):
        await admitted.wait()
        assert request.binding == trusted["binding"]
        trusted["callback_id"] = request.callback_id
        return DomainGrant(trusted["binding"], handler, lambda: True)

    process = ManagedHarnessProcess(domain_authority=authority)
    await process.start(config(tmp_path))
    try:
        learning, _, receipt = await start_turn(process)
        trusted["binding"] = DomainBinding("learning", "attempt-1", learning, receipt["inputId"], "learning")
        admitted.set()
        await thread_entered(entered)
        cancel = await process.request("session.cancel", {"session_id": learning}, "learning", "attempt-1", 0.01)
        assert cancel["outcome"] == "accepted_pending"
        if race_close:
            assert (await process.close(0.05))["state"] == "blocked"
            assert (await process.settlement(0.01))["state"] == "pending"
        assert process.domain_status()["active"] == 1
        release.set()
        await asyncio.wait_for(finalizing.wait(), 5)
        if race_close:
            assert (await process.settlement(0.01))["state"] == "pending"
        else:
            assert (await process.query_result(cancel["request_id"]))["outcome"] == "accepted_pending"
        finalized.set()
        if not race_close:
            async with asyncio.timeout(5):
                while (await process.query_result(cancel["request_id"]))["outcome"] == "accepted_pending":
                    await asyncio.sleep(0.01)
            assert (await process.query_result(cancel["request_id"]))["outcome"] == "cancelled_settled"
        assert (await process.close(8))["state"] == "closed"
        outcome = await process.query_result(cancel["request_id"])
        # Native disposal may interrupt the concurrent cancel observation;
        # actual close/pipe/handler proof remains separate from that receipt.
        assert outcome["outcome"] in {"cancelled_settled", "uncertain_after_disconnect"}
        callback = process.domain_result(trusted["callback_id"])
        assert callback["outcome"] == "cancelled_settled"
        assert "result" not in callback
        assert process.domain_status()["active"] == 0
    finally:
        release.set()
        finalized.set()
        admitted.set()
        await process.close(8)
        pool.shutdown(wait=True)
