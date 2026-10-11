# SPDX-License-Identifier: MIT
"""Public process/transfer seam over real Node IPC; synthetic execution only."""
from pathlib import Path
import asyncio
import json
import os
import subprocess
from contextlib import asynccontextmanager

import pytest

from renulus.contracts import ApiError
from renulus.runtime.harness_process import HarnessProcessConfig, ManagedHarnessProcess
from renulus.runtime.harness_saved_transfer import HarnessSavedTransfer
from test_harness_saved_transfer import ALIASES, document, request_for
from renulus.design_c_contracts import canonical_digest

NODE = Path("C:/Renulus/scratch/ocf/tools/node-v26.4.0-win-x64/node.exe")
FIXTURE = Path(__file__).resolve().parents[2] / "packages/harness/test/fixtures/transfer-capacity-host.mjs"


class NativePipe:
    """Public authenticated protocol only, independently of Python validation."""
    def __init__(self, child, identity):
        self.child, self.identity = child, identity
        self.sequence = 0

    async def send(self, command, payload, operation="migration_synthetic", attempt="1", *, request_id=None):
        self.sequence += 1
        frame = {**self.identity, "kind": "request", "command": command, "payload": payload,
            "operation_id": operation, "attempt_id": attempt, "request_id": request_id or f"raw_{self.sequence}"}
        self.child.stdin.write(json.dumps(frame, ensure_ascii=False, separators=(",", ":")).encode() + b"\n")
        await self.child.stdin.drain()
        async with asyncio.timeout(3):
            result = json.loads(await self.child.stdout.readline())
        assert all(result[key] == frame[key] for key in (*self.identity, "operation_id", "attempt_id", "request_id"))
        return result

    async def release(self, request_id):
        self.child.stdin.write(json.dumps({**self.identity, "kind": "observation_release",
            "request_id": request_id}).encode() + b"\n")
        await self.child.stdin.drain()


@asynccontextmanager
async def native_pipe(tmp_path, **settings):
    root = tmp_path / "raw-profile"
    root.mkdir()
    identity = {"protocol": "renulus-harness/1", "profile_id": "profile_synthetic",
        "store_id": "runtime_synthetic", "generation": "raw_generation", "token": "synthetic_test_token"}
    boot = {**identity, "root": str(root), "domain_store_id": "domain_synthetic",
        "domain_path": "state/renulus.sqlite", **settings}
    environment = {key: os.environ[key] for key in ("SYSTEMROOT", "WINDIR") if key in os.environ}
    environment.update(RENULUS_HARNESS_BOOT=json.dumps(boot), PATH=str(NODE.parent),
        HOME=str(root), USERPROFILE=str(root), APPDATA=str(root), LOCALAPPDATA=str(root), TEMP=str(root), TMP=str(root))
    child = await asyncio.create_subprocess_exec(str(NODE), str(FIXTURE), cwd=root, env=environment,
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    peer = NativePipe(child, identity)
    try:
        assert json.loads(await asyncio.wait_for(child.stdout.readline(), 3))["kind"] == "ready"
        yield peer
    finally:
        if "fixture_gate_file" in settings:
            Path(settings["fixture_gate_file"]).write_text("release")
        assert (await peer.send("host.close", {}, operation="close"))["outcome"] == "cancelled_settled"
        await asyncio.wait_for(child.wait(), 3)
        assert child.returncode == 0, (await child.stderr.read()).decode()


def config(tmp_path, *, local_records=16, native_records=16, local_bytes=1048576, native_bytes=1048576, frame_bytes=65536, **settings):
    return HarnessProcessConfig(node_executable=NODE, host_entry=FIXTURE,
        profile_root=tmp_path / "profile", profile_id="profile_synthetic",
        store_id="runtime_synthetic", domain_store_id="domain_synthetic",
        domain_path="state/renulus.sqlite", max_result_records=local_records,
        max_frame_bytes=frame_bytes, max_result_bytes=local_bytes,
        boot_settings={"ipc": {"max_result_records": native_records,
            "max_frame_bytes": frame_bytes, "max_result_bytes": native_bytes}, **settings})


@pytest.mark.parametrize("limits", [{"local_records": 4}, {"native_records": 4},
    {"local_bytes": 32768, "frame_bytes": 4096}, {"native_bytes": 32768, "frame_bytes": 4096}])
async def test_capacity_refusal_precedes_the_first_native_stage(tmp_path, limits):
    process = ManagedHarnessProcess()
    await process.start(config(tmp_path, **limits))
    transfer = HarnessSavedTransfer(process, observation_timeout=2)
    source = document()
    try:
        with pytest.raises(ApiError) as denied:
            await transfer.stage(request_for(source), document=source)
        assert denied.value.code == "transfer_capacity"
        status = await process.request("host.status", {}, "status", "1", 2)
        assert status["result"] == {"state": "ready", "stages": 0, "imports": 0}
    finally:
        assert (await process.close(3))["state"] == "closed"
        await transfer.close()


def plan_for(source, *, parts=1):
    request = request_for(source)
    chunks = [source.decode()] if parts == 1 else [source[:1].decode(), source[1:].decode()]
    payloads = [{"sessionId": request.session_id, "bundleDigest": request.bundle_digest,
        "totalBytes": len(source), "partCount": len(chunks), "partIndex": index, "chunk": chunk}
        for index, chunk in enumerate(chunks)]
    sizes = [len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()) for payload in payloads]
    return request, {"sessionId": request.session_id, "bundleDigest": request.bundle_digest,
        "totalBytes": len(source), "partPayloadBytes": sizes}, payloads


async def test_cancelled_reserve_observers_keep_one_original_request_and_capacity(tmp_path):
    gate = tmp_path / "release-reserve"
    process = ManagedHarnessProcess()
    await process.start(config(tmp_path, local_records=5, native_records=5,
        fixture_hold_state="reserved", fixture_gate_file=str(gate)))
    transfer = HarnessSavedTransfer(process, observation_timeout=.05)
    source = document()
    request = request_for(source)
    try:
        with pytest.raises(ApiError) as expired:
            await transfer.stage(request, document=source)
        assert expired.value.code == "harness_migration_observation_timeout"
        assert transfer.status() == {"accepting": True, "active": 1}
        second = asyncio.create_task(transfer.stage(request, document=source))
        await asyncio.sleep(.01)
        second.cancel()
        with pytest.raises(asyncio.CancelledError):
            await second
        refused = await process.request("session.create", {"title": "Other"}, "other", "1", 2)
        assert refused["error"]["code"] == "result_capacity"
        assert (await process.request("host.status", {}, "status", "1", 2))["result"]["stages"] == 0
        gate.write_text("release")
        await transfer.settled()
        await transfer.stage(request, document=source)
        assert (await process.request("host.status", {}, "status2", "1", 2))["result"]["stages"] == 1
        assert await transfer.retire(request) == "retired"
    finally:
        gate.write_text("release")
        assert (await process.close(3))["state"] == "closed"
        await transfer.close()


async def test_metadata_reply_ceiling_keeps_uncertain_stage_and_reservation(tmp_path):
    process = ManagedHarnessProcess()
    await process.start(config(tmp_path, local_records=5, fixture_oversized_metadata=True))
    transfer = HarnessSavedTransfer(process, observation_timeout=2)
    source = document()
    try:
        for _ in range(2):
            with pytest.raises(ApiError) as uncertain:
                await transfer.stage(request_for(source), document=source)
            assert uncertain.value.code == "reply_too_large"
        assert (await process.request("host.status", {}, "status", "1", 2))["result"]["stages"] == 1
        refused = await process.request("session.create", {"title": "Other"}, "other", "1", 2)
        assert refused["error"]["code"] == "result_capacity"
        assert await transfer.retire(request_for(source)) == "retired"
    finally:
        assert (await process.close(3))["state"] == "closed"
        await transfer.close()


async def test_read_release_is_not_credit_for_unused_plan_slots(tmp_path):
    process = ManagedHarnessProcess()
    await process.start(config(tmp_path, local_records=6, native_records=6))
    request, plan, payloads = plan_for(document(), parts=2)
    try:
        reserved = await process.request("session.import.reserve", plan, request.migration_id, "1", 2)
        assert reserved["result"] == {"state": "reserved", "sessionId": request.session_id,
            "bundleDigest": request.bundle_digest, "partCount": 2,
            "planDigest": canonical_digest(["renulus-transfer-reservation/1", request.session_id, request.bundle_digest,
                len(document()), plan["partPayloadBytes"]])}
        unrelated = await process.request("session.get", {"session_id": "other"}, "other", "1", 2)
        assert unrelated["error"]["code"] == "result_capacity"
        stage = await process.request("session.import.stage", payloads[0], request.migration_id, "1", 2)
        assert stage["outcome"] == "committed_reference"
        target = {key: plan[key] for key in ("sessionId", "bundleDigest")}
        observed = await process.request("session.import.inspect", target, request.migration_id, "1", 2)
        assert await process.release_observation(observed["request_id"])
        # One consumed read is actually freed; two stages + import + second read
        # + retirement remain promised, rather than lending those slots.
        one = await process.request("session.create", {"title": "One"}, "one", "1", 2)
        assert one["outcome"] == "committed_reference"
        two = await process.request("session.create", {"title": "Two"}, "two", "1", 2)
        assert two["error"]["code"] == "result_capacity"
        assert (await process.request("session.import.stage", payloads[1], request.migration_id, "1", 2))["outcome"] == "committed_reference"
    finally:
        assert (await process.close(3))["state"] == "closed"


@pytest.mark.parametrize("limits", [{"local_records": 6}, {"native_records": 6}])
async def test_reserved_turn_finishes_despite_unrelated_receipts_then_retires_exactly(tmp_path, limits):
    process = ManagedHarnessProcess()
    await process.start(config(tmp_path, **limits))
    transfer = HarnessSavedTransfer(process, observation_timeout=2)
    source = document()
    request = request_for(source)
    try:
        retained = await process.request("session.create", {"title": "Retained"}, "other", "1", 2)
        assert retained["outcome"] == "committed_reference"
        await transfer.stage(request, document=source)
        competing = await process.request("session.create", {"title": "Competing"}, "competing", "1", 2)
        assert competing["outcome"] == "rejected_before_admission"
        assert competing["error"]["code"] == "result_capacity"
        assert await transfer.inspect(request) is None
        await transfer.commit(request)
        assert (await transfer.inspect(request)).message_count == 2
        assert await transfer.retire(request) == "retired"
        # Retirement erases only this operation, never competing retained work.
        assert await process.query_result(retained["request_id"]) == retained
        assert (await process.request("session.create", {"title": "After"}, "after", "1", 2))["outcome"] == "committed_reference"
        later_read = await process.request("session.get", {"session_id": request.session_id}, request.migration_id, "1", 2)
        assert await process.query_result(later_read["request_id"]) == later_read
        assert await process.release_observation(later_read["request_id"])
    finally:
        assert (await process.close(3))["state"] == "closed"
        await transfer.close()


async def test_reserved_multipart_import_readback_and_retirement_use_actual_sdk_without_dispatch(tmp_path):
    process = ManagedHarnessProcess()
    await process.start(config(tmp_path, fixture_native=True))
    transfer = HarnessSavedTransfer(process, observation_timeout=10)
    source = document("Synthetic transplantation résumé α𐀀. " * 2400)
    request = request_for(source)
    try:
        await transfer.stage(request, document=source)
        assert await transfer.inspect(request) is None
        await transfer.commit(request)
        readback = await transfer.inspect(request)
        assert readback.native_message_ids == ALIASES and readback.message_count == 2
        status = await process.request("host.status", {}, "status", "1", 2)
        assert status["result"]["stages"] > 1
        assert status["result"]["imports"] == 1 and status["result"]["modelCalls"] == 0
        assert await transfer.retire(request) == "retired"
    finally:
        assert (await process.close(10))["state"] == "closed"
        assert (await process.settlement(0))["state"] == "settled"
        await transfer.close()


async def test_native_reservation_counts_a_released_read_until_actual_publication_settles(tmp_path):
    gate = tmp_path / "release-publication"
    request, plan, _ = plan_for(document())
    async with native_pipe(tmp_path, ipc={"max_result_records": 5},
            fixture_hold_operation="held-read", fixture_hold_after=True, fixture_gate_file=str(gate)) as pipe:
        read = await pipe.send("session.get", {"session_id": "synthetic-read"}, operation="held-read")
        assert read["outcome"] == "committed_reference"
        await pipe.release(read["request_id"])
        refused = await pipe.send("session.import.reserve", plan)
        assert refused["error"]["code"] == "transfer_capacity"
        assert (await pipe.send("host.status", {}, operation="status"))["result"]["stages"] == 0
        gate.write_text("release")
        async with asyncio.timeout(3):
            while True:
                reserved = await pipe.send("session.import.reserve", plan)
                if reserved["outcome"] == "committed_reference":
                    break
                assert reserved["error"]["code"] == "transfer_capacity"
                await asyncio.sleep(.01)
        assert reserved["result"]["sessionId"] == request.session_id


async def test_native_plan_validation_and_replay_cannot_change_an_admitted_operation(tmp_path):
    request, plan, payloads = plan_for(document())
    async with native_pipe(tmp_path) as pipe:
        for malformed in ({**plan, "path": "never-read"}, {**plan, "totalBytes": True},
                {**plan, "partPayloadBytes": [False]}, {**plan, "partPayloadBytes": [49153]}):
            denied = await pipe.send("session.import.reserve", malformed)
            assert denied["outcome"] == "rejected_before_admission" and denied["error"]["code"] == "invalid_payload"
        reserved = await pipe.send("session.import.reserve", plan, request_id="stable_reservation")
        replay = await pipe.send("session.import.reserve", plan, request_id="stable_reservation")
        assert replay == reserved
        denied = await pipe.send("session.import.reserve", {**plan, "bundleDigest": "0" * 64})
        assert denied["error"]["code"] == "transfer_reservation_conflict"
        for changed, attempt in (({**payloads[0], "chunk": "x"}, "1"), (payloads[0], "other"),
                ({**payloads[0], "partIndex": False}, "1"), ({**payloads[0], "bundleDigest": "0" * 64}, "1")):
            denied = await pipe.send("session.import.stage", changed, attempt=attempt)
            assert denied["error"]["code"] == "transfer_reservation_conflict"
        assert (await pipe.send("host.status", {}, operation="status"))["result"]["stages"] == 0
        assert (await pipe.send("session.import.stage", payloads[0]))["result"]["complete"] is True


async def test_native_stage_frame_and_full_record_plan_deny_without_effect(tmp_path):
    request, plan, _ = plan_for(document("x" * 5000))
    async with native_pipe(tmp_path, ipc={"max_frame_bytes": 4096}) as pipe:
        denied = await pipe.send("session.import.reserve", plan)
        assert denied["error"]["code"] == "frame_too_large"
        _, edge, _ = plan_for(document())
        edge["partPayloadBytes"] = [512] * 256
        denied = await pipe.send("session.import.reserve", edge)
        assert denied["error"]["code"] == "transfer_capacity"
        assert (await pipe.send("host.status", {}, operation="status"))["result"]["stages"] == 0


async def test_definite_native_refusal_releases_only_the_unused_local_hold(tmp_path):
    process = ManagedHarnessProcess()
    await process.start(config(tmp_path, local_records=6, native_records=5))
    request, plan, payloads = plan_for(document())
    try:
        retained = await process.request("host.inspect", {}, "retained", "1", 2)
        denied = await process.request("session.import.reserve", plan, request.migration_id, "1", 2)
        assert denied["error"]["code"] == "transfer_capacity"
        assert await process.release_observation(retained["request_id"])
        reserved = await process.request("session.import.reserve", plan, request.migration_id, "1", 2)
        assert reserved["outcome"] == "committed_reference"
        assert (await process.request("session.import.stage", payloads[0], request.migration_id, "1", 2))["result"]["complete"] is True
    finally:
        assert (await process.close(3))["state"] == "closed"


async def test_retired_ack_does_not_free_native_hold_before_actual_reply_settlement(tmp_path):
    gate = tmp_path / "release-retirement"
    process = ManagedHarnessProcess()
    await process.start(config(tmp_path, local_records=5, native_records=5,
        fixture_hold_state="retired", fixture_hold_after=True, fixture_gate_file=str(gate)))
    transfer = HarnessSavedTransfer(process, observation_timeout=2)
    source = document()
    request, plan, _ = plan_for(source)
    try:
        await transfer.stage(request, document=source)
        assert await transfer.retire(request) == "retired"
        competing = await process.request("session.import.reserve", plan, "another_migration", "1", 2)
        assert competing["error"]["code"] == "transfer_capacity"
        assert (await process.close(.03))["state"] == "blocked"
        assert (await process.settlement(0))["state"] == "pending"
        gate.write_text("release")
        assert (await process.close(3))["state"] == "closed"
        assert (await process.settlement(0))["state"] == "settled"
    finally:
        gate.write_text("release")
        assert (await process.close(3))["state"] == "closed"
        await transfer.close()


async def test_stage_frame_and_256_part_record_cliffs_are_refused_before_staging(tmp_path):
    process = ManagedHarnessProcess()
    await process.start(config(tmp_path, frame_bytes=4096, local_records=256, native_records=256))
    try:
        request, oversized, _ = plan_for(document("x" * 5000))
        frame_denied = await process.request("session.import.reserve", oversized, request.migration_id, "1", 2)
        assert frame_denied["error"]["code"] == "frame_too_large"
        _, edge, _ = plan_for(document())
        edge["partPayloadBytes"] = [512] * 256
        count_denied = await process.request("session.import.reserve", edge, request.migration_id, "1", 2)
        assert count_denied["error"]["code"] == "transfer_capacity"
        assert (await process.request("host.status", {}, "status", "1", 2))["result"]["stages"] == 0
    finally:
        assert (await process.close(3))["state"] == "closed"


@pytest.mark.parametrize("limits", [{"local_bytes": 96000}, {"native_bytes": 96000}])
async def test_reserved_bytes_cannot_be_borrowed_by_unrelated_traffic(tmp_path, limits):
    process = ManagedHarnessProcess()
    await process.start(config(tmp_path, frame_bytes=16384, **limits))
    request, plan, payloads = plan_for(document())
    try:
        reserved = await process.request("session.import.reserve", plan, request.migration_id, "1", 2)
        assert reserved["outcome"] == "committed_reference"
        unrelated = await process.request("session.get", {"session_id": "other"}, "other", "1", 2)
        assert unrelated["error"]["code"] == "result_capacity"
        assert (await process.request("session.import.stage", payloads[0], request.migration_id, "1", 2))["result"]["complete"] is True
        assert (await process.request("operation.retire", {}, request.migration_id, "1", 2))["result"]["state"] == "retired"
        assert (await process.request("session.get", {"session_id": "after"}, "after", "1", 2))["outcome"] == "committed_reference"
    finally:
        assert (await process.close(3))["state"] == "closed"
