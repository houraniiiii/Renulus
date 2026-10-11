"""Public process observations over real Node IPC; execution is synthetic."""
import asyncio
from pathlib import Path
import pytest

from renulus.runtime.harness_process import HarnessProcessConfig, ManagedHarnessProcess


NODE = Path("C:/Renulus/scratch/ocf/tools/node-v26.4.0-win-x64/node.exe")
FIXTURE = Path(__file__).resolve().parents[2] / "packages/harness/test/fixtures/observation-release-host.mjs"


def config(tmp_path, *, max_records=4, **settings):
    return HarnessProcessConfig(node_executable=NODE, host_entry=FIXTURE,
        profile_root=tmp_path / "profile", profile_id="synthetic-profile",
        store_id="synthetic-runtime", domain_store_id="synthetic-domain",
        domain_path="state/renulus.sqlite", max_result_records=max_records,
        max_frame_bytes=4096, max_result_bytes=65536,
        boot_settings={"ipc": {"max_result_records": max_records,
            "max_frame_bytes": 4096, "max_result_bytes": 65536}, **settings})


async def terminal(process, request_id):
    async with asyncio.timeout(3):
        while True:
            receipt = await process.query_result(request_id)
            if receipt and receipt["outcome"] != "accepted_pending":
                return receipt
            await asyncio.sleep(.001)


@pytest.mark.parametrize("max_records", [4, 256])
async def test_observed_reads_keep_polling_while_one_native_prompt_is_held(tmp_path, max_records):
    process = ManagedHarnessProcess()
    await process.start(config(tmp_path, max_records=max_records))
    try:
        prompt = await process.request("session.prompt", {"configuration_id": "synthetic",
            "session_id": "native-session", "text": "held synthetic inference"},
            "learning", "1", .02)
        assert prompt["outcome"] == "accepted_pending"
        # On the old public transport this intentionally reaches result_capacity,
        # demonstrating the behavior instead of failing on the absent new API.
        release = getattr(process, "release_observation", None)
        for index in range(1024):
            command = ("session.get", "session.messages", "host.status")[index % 3]
            payload = {} if command == "host.status" else {"session_id": "native-session"}
            receipt = await process.request(command, payload, "poll-" + str(index), "1", 2)
            assert receipt["outcome"] == "committed_reference", (index, receipt.get("error"), receipt)
            if release is not None:
                assert await release(receipt["request_id"])
            if command == "host.status":
                assert receipt["result"]["dispatches"] == 1
        assert await process.query_result(receipt["request_id"]) is None
        assert (await process.query_result(prompt["request_id"]))["outcome"] == "accepted_pending"
        cancelled = await process.request("session.cancel", {"session_id": "native-session"}, "stop", "1", 2)
        assert cancelled["outcome"] == "cancelled_settled"
        assert (await terminal(process, prompt["request_id"]))["outcome"] == "committed_reference"
    finally:
        assert (await process.close(3))["state"] == "closed"


@pytest.mark.parametrize("command,payload", [
    ("session.get", {"session_id": "native-session"}),
    ("session.messages", {"session_id": "native-session"}),
    ("session.find", {}), ("host.status", {}), ("host.inspect", {}),
])
async def test_terminal_allowed_reads_release_without_an_execution_dispatch(tmp_path, command, payload):
    process = ManagedHarnessProcess()
    await process.start(config(tmp_path))
    try:
        receipt = await process.request(command, payload, "read", "1", 2)
        assert receipt["outcome"] == "committed_reference"
        assert await process.release_observation(receipt["request_id"])
        assert await process.query_result(receipt["request_id"]) is None
        assert not await process.release_observation(receipt["request_id"])
        assert (await process.request("host.status", {}, "status", "1", 2))["result"]["dispatches"] == 0
    finally:
        assert (await process.close(3))["state"] == "closed"


async def test_pending_unobserved_uncertain_and_write_receipts_cannot_be_released(tmp_path):
    process = ManagedHarnessProcess()
    await process.start(config(tmp_path))
    try:
        created = await process.request("session.create", {"title": "Synthetic"}, "write", "1", 2)
        assert created["outcome"] == "committed_reference"
        assert not await process.release_observation(created["request_id"])
        pending = await process.request("session.get", {"session_id": "held-read"}, "pending", "1", .02)
        assert pending["outcome"] == "accepted_pending"
        assert not await process.release_observation(pending["request_id"])
        uncertain = await process.request("session.get", {"session_id": "uncertain"}, "uncertain", "1", 2)
        assert uncertain["outcome"] == "uncertain_after_disconnect"
        assert not await process.release_observation(uncertain["request_id"])
        cancelled = await process.request("session.cancel", {"session_id": "held-read"}, "stop", "1", 2)
        assert cancelled["outcome"] == "cancelled_settled"
        assert not await process.release_observation(cancelled["request_id"])
        # This later ordered status reply confirms delivery of the read's terminal
        # reply without observing it through the process API.
        status = await process.request("host.status", {}, "status", "1", 2)
        assert not status["result"]["readHeld"]
        assert not await process.release_observation(pending["request_id"])
        observed = await terminal(process, pending["request_id"])
        assert observed["outcome"] == "committed_reference"
        assert await process.release_observation(pending["request_id"])
        assert (await process.query_result(created["request_id"]))["result"] == created["result"]
        assert (await process.query_result(uncertain["request_id"]))["outcome"] == "uncertain_after_disconnect"
        assert not await process.release_observation("unknown")
        assert not await process.release_observation(None)
    finally:
        assert (await process.close(3))["state"] == "closed"


async def test_a_definite_read_refusal_can_release_its_observed_receipt(tmp_path):
    process = ManagedHarnessProcess()
    await process.start(config(tmp_path))
    try:
        receipt = await process.request("session.get", {"session_id": "invalid-read"}, "denied", "1", 2)
        assert receipt["outcome"] == "rejected_before_admission"
        assert await process.release_observation(receipt["request_id"])
        assert await process.query_result(receipt["request_id"]) is None
    finally:
        assert (await process.close(3))["state"] == "closed"


async def test_cancelled_release_observer_does_not_abandon_control_publication(tmp_path):
    process = ManagedHarnessProcess()
    await process.start(config(tmp_path))
    try:
        receipt = await process.request("session.get", {"session_id": "native-session"}, "read", "1", 2)
        release = asyncio.create_task(process.release_observation(receipt["request_id"]))
        await asyncio.sleep(0)
        release.cancel()
        with pytest.raises(asyncio.CancelledError):
            await release
        async with asyncio.timeout(2):
            while await process.query_result(receipt["request_id"]) is not None:
                await asyncio.sleep(.001)
        assert (await process.request("host.status", {}, "status", "1", 2))["outcome"] == "committed_reference"
    finally:
        assert (await process.close(3))["state"] == "closed"


async def test_close_retains_native_ownership_of_a_released_but_queued_reply(tmp_path):
    gate = tmp_path / "writer-released"
    process = ManagedHarnessProcess()
    await process.start(config(tmp_path, fixture_hold_operation="held-reply", fixture_gate_file=str(gate)))
    try:
        receipt = await process.request("session.get", {"session_id": "native-session"}, "held-reply", "1", 2)
        assert receipt["outcome"] == "committed_reference"
        assert await process.release_observation(receipt["request_id"])
        assert await process.query_result(receipt["request_id"]) is None
        assert (await process.close(.03))["state"] == "blocked"
        assert (await process.settlement(0))["state"] == "pending"
        gate.write_text("release", encoding="utf-8")
        assert (await process.close(3))["state"] == "closed"
        assert (await process.settlement(0))["state"] == "settled"
    finally:
        gate.write_text("release", encoding="utf-8")
        assert (await process.close(3))["state"] == "closed"


async def test_release_without_a_live_pipe_preserves_the_observed_receipt(tmp_path):
    process = ManagedHarnessProcess()
    await process.start(config(tmp_path))
    receipt = await process.request("session.get", {"session_id": "native-session"}, "read", "1", 2)
    assert (await process.close(3))["state"] == "closed"
    assert not await process.release_observation(receipt["request_id"])
    assert (await process.query_result(receipt["request_id"]))["result"] == receipt["result"]
