"""Real source-built OpenCode SDK through the owned Python/Node IPC boundary."""
from pathlib import Path
import asyncio
from contextlib import asynccontextmanager
import json
import os
import subprocess
import pytest

from renulus.runtime.harness_process import HarnessProcessConfig, ManagedHarnessProcess
from renulus.runtime.harness_profile import prepare_harness_profile


REPO = Path(__file__).resolve().parents[2]
NODE = Path(os.environ.get("RENULUS_HARNESS_NODE", ""))
pytestmark = pytest.mark.skipif(
    not os.environ.get("RENULUS_HARNESS_NODE") or not NODE.is_absolute() or not NODE.is_file()
    or not (REPO / "packages/harness/node_modules/@opencode/sdk/package.json").is_file(),
    reason="Opt in with RENULUS_HARNESS_NODE pointing to the reviewed Node 26.4.0/cohort artifact.",
)


def config(tmp_path, *, scripted=False, **settings):
    entry = ("test/fixtures/scripted-host.mjs" if scripted else "src/main.mjs")
    return HarnessProcessConfig(
        node_executable=NODE, host_entry=REPO / "packages/harness" / entry,
        profile_root=tmp_path / "profile", profile_id="synthetic-profile",
        store_id="synthetic-runtime", domain_store_id="synthetic-domain",
        domain_path="state/renulus.sqlite", start_timeout=30,
        boot_settings=settings,
    )


async def request(process, command, payload=None, operation="observe", attempt="1"):
    result = await process.request(command, payload or {}, operation, attempt, 5)
    async with asyncio.timeout(10):
        while result["outcome"] == "accepted_pending":
            await asyncio.sleep(0.02)
            result = await process.query_result(result["request_id"])
    return result


async def test_default_sdk_entry_is_observable_but_cannot_activate_or_dispatch(tmp_path):
    process = ManagedHarnessProcess()
    try:
        ready = await process.start(config(tmp_path))
        assert ready["state"] == "policy_blocked"
        status = await request(process, "host.status")
        assert status["outcome"] == "committed_reference"
        assert status["result"]["state"] == "policy_blocked"
        rejected = await request(process, "host.activate", {"configuration_id": "synthetic-policy-v1"})
        assert rejected["outcome"] == "rejected_before_admission"
        assert rejected["error"]["code"] == "harness_policy_blocked"
        rejected = await request(process, "session.create", {"title": "Blocked CKD lesson"})
        assert rejected["outcome"] == "rejected_before_admission"
        assert rejected["error"]["code"] == "harness_policy_blocked"
    finally:
        closed = await process.close(15)
    assert closed == {"state": "closed", "outcome": "cancelled_settled"}


async def terminal_session(process, session_id):
    async with asyncio.timeout(15):
        while True:
            response = await request(process, "session.get", {"session_id": session_id})
            assert response["outcome"] == "committed_reference", response
            session = response["result"]["session"]
            if session.get("outcome") in {"succeeded", "failed", "interrupted"}:
                return session
            await asyncio.sleep(0.05)


async def test_real_sdk_turn_reopens_same_input_and_transcript_without_inference(tmp_path):
    process = ManagedHarnessProcess()
    settings = config(tmp_path, scripted=True)
    try:
        ready = await process.start(settings)
        assert ready["state"] == "policy_blocked"
        status = (await request(process, "host.status"))["result"]
        assert status["modelCalls"] == 0
        assert Path(status["runtimePath"]) == NODE.parent
        activated = await request(process, "host.activate", {"configuration_id": "synthetic-policy-v1"})
        assert activated["result"]["state"] == "ready"
        created = await request(process, "session.create", {"title": "Synthetic CKD learning"}, "create-1")
        session_id = created["result"]["session"]["id"]
        submitted = await request(process, "session.prompt", {
            "session_id": session_id, "text": "Explain this synthetic CKD lesson.",
            "configuration_id": "synthetic-policy-v1",
        }, "learning-1", "attempt-1")
        receipt = submitted["result"]
        assert receipt["sessionId"] == session_id
        assert receipt["operationId"] == "learning-1"
        assert receipt["attemptId"] == "attempt-1"
        assert "executionId" not in receipt
        before = await terminal_session(process, session_id)
        assert before["outcome"] == "succeeded"
        messages = (await request(process, "session.messages", {"session_id": session_id}))["result"]["messages"]
        user = next(message for message in messages if message["type"] == "user")
        assert user["id"] == receipt["inputId"]
        assert next(message for message in messages if message["type"] == "assistant")["content"][0]["text"] == "Synthetic CKD learning answer."
        assert (await request(process, "host.status"))["result"]["modelCalls"] == 1
        assert (await process.close(15))["state"] == "closed"
        process = ManagedHarnessProcess()
        reopened = await process.start(settings)
        assert reopened["generation"] != ready["generation"]
        assert reopened["state"] == "policy_blocked"
        assert (await request(process, "session.get", {"session_id": session_id}))["result"]["session"] == before
        assert (await request(process, "session.messages", {"session_id": session_id}))["result"]["messages"] == messages
        assert (await request(process, "host.status"))["result"]["modelCalls"] == 0
    finally:
        closed = await process.close(15)
    assert closed["state"] == "closed"


async def test_wrong_configuration_cannot_write_a_prompt_or_call_the_model(tmp_path):
    process = ManagedHarnessProcess()
    try:
        await process.start(config(tmp_path, scripted=True))
        await request(process, "host.activate", {"configuration_id": "synthetic-policy-v1"})
        created = await request(process, "session.create", {"title": "Electrolyte learning"}, "create")
        session_id = created["result"]["session"]["id"]
        rejected = await request(process, "session.prompt", {
            "session_id": session_id, "text": "This must not be dispatched.",
            "configuration_id": "wrong-policy",
        }, "wrong-policy", "attempt-1")
        assert rejected["outcome"] == "rejected_before_admission"
        assert rejected["error"]["code"] == "configuration_mismatch"
        assert (await request(process, "host.status"))["result"]["modelCalls"] == 0
        assert (await request(process, "session.messages", {"session_id": session_id}))["result"]["messages"] == []
    finally:
        assert (await process.close(15))["state"] == "closed"


class Wire:
    """Test the public wire directly where supervisor-generated IDs cannot collide."""
    def __init__(self, child, boot):
        self.child = child
        self.identity = {key: boot[key] for key in ("protocol", "profile_id", "store_id", "generation", "token")}

    def frame(self, request_id, command, payload=None, **identity):
        return {**self.identity, "kind": "request", "operation_id": request_id,
                "attempt_id": "1", "request_id": request_id, "command": command,
                "payload": payload or {}, **identity}

    async def send(self, *frames):
        for frame in frames:
            self.child.stdin.write(json.dumps(frame, separators=(",", ":")).encode() + b"\n")
        await self.child.stdin.drain()

    async def read(self):
        async with asyncio.timeout(15):
            line = await self.child.stdout.readline()
            assert line, "Real Node IPC exited before replying."
            return json.loads(line)


@asynccontextmanager
async def wire_host(tmp_path, **settings):
    selection = config(tmp_path, scripted=True)
    root = selection.profile_root
    prepare_harness_profile(root, profile_id=selection.profile_id,
                            domain_store_id=selection.domain_store_id,
                            runtime_store_id=selection.store_id, domain_path=selection.domain_path)
    boot = {"protocol": "renulus-harness/1", "profile_id": selection.profile_id,
            "store_id": selection.store_id, "generation": "synthetic-wire-generation",
            "token": "synthetic-wire-token", "root": str(root),
            "domain_store_id": selection.domain_store_id, "domain_path": selection.domain_path, **settings}
    env = {key: os.environ[key] for key in ("SYSTEMROOT", "WINDIR") if key in os.environ}
    env["PATH"] = str(NODE.parent)
    for key, directory in {"HOME": "home", "USERPROFILE": "home", "APPDATA": "config",
                           "LOCALAPPDATA": "local", "XDG_CONFIG_HOME": "config",
                           "XDG_DATA_HOME": "data", "XDG_CACHE_HOME": "cache",
                           "XDG_STATE_HOME": "state", "XDG_RUNTIME_DIR": "run",
                           "TEMP": "temp", "TMP": "temp"}.items():
        owned = root / directory
        owned.mkdir(parents=True, exist_ok=True)
        env[key] = str(owned)
    env["RENULUS_HARNESS_BOOT"] = json.dumps(boot)
    child = await asyncio.create_subprocess_exec(
        str(NODE), str(selection.host_entry), cwd=root, env=env,
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE, limit=1_048_576,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    async def drain_stderr():
        while await child.stderr.read(65536):
            pass
    stderr = asyncio.create_task(drain_stderr())
    wire = Wire(child, boot)
    try:
        assert (await wire.read())["kind"] == "ready"
        yield wire
    finally:
        if child.returncode is None:
            try:
                await wire.send(wire.frame("fixture-close", "host.close"))
            except (BrokenPipeError, ConnectionError):
                pass
        async with asyncio.timeout(15):
            await child.stdout.read()
            await child.wait()
            await stderr


async def test_conflicting_request_identity_cannot_replay_or_redispatch_old_work(tmp_path):
    async with wire_host(tmp_path) as wire:
        await wire.send(wire.frame("activate", "host.activate", {"configuration_id": "synthetic-policy-v1"}))
        assert (await wire.read())["outcome"] == "committed_reference"
        original = wire.frame("create", "session.create", {"title": "Original lesson"})
        await wire.send(original)
        committed = await wire.read()
        assert committed["outcome"] == "committed_reference"
        for changed in ({"operation_id": "different"}, {"attempt_id": "2"},
                        {"command": "session.get"}, {"payload": {"title": "Changed lesson"}}):
            await wire.send({**original, **changed})
            rejected = await wire.read()
            assert rejected["outcome"] == "rejected_before_admission"
            assert rejected["error"]["code"] == "request_id_conflict"
            assert rejected["operation_id"] == changed.get("operation_id", original["operation_id"])
            assert rejected["attempt_id"] == changed.get("attempt_id", original["attempt_id"])
        await wire.send(original)
        assert await wire.read() == committed


async def test_identical_pending_wire_request_is_acknowledged_without_redispatch(tmp_path):
    async with wire_host(tmp_path) as wire:
        await wire.send(wire.frame("activate", "host.activate", {"configuration_id": "synthetic-policy-v1"}))
        await wire.read()
        await wire.send(wire.frame("create", "session.create", {"title": "One submitted input"}))
        session_id = (await wire.read())["result"]["session"]["id"]
        prompt = wire.frame("prompt", "session.prompt", {
            "session_id": session_id, "configuration_id": "synthetic-policy-v1", "text": "Submit only once.",
        })
        await wire.send(prompt, prompt)
        pending = await wire.read()
        assert pending["outcome"] == "accepted_pending"
        assert pending["request_id"] == "prompt"
        committed = await wire.read()
        assert committed["outcome"] == "committed_reference"
        await wire.send(wire.frame("messages", "session.messages", {"session_id": session_id}))
        messages = (await wire.read())["result"]["messages"]
        assert [message["id"] for message in messages if message["type"] == "user"] == [committed["result"]["inputId"]]


async def test_node_invalid_identifiers_never_reach_model_or_transcript(tmp_path):
    async with wire_host(tmp_path) as wire:
        await wire.send(wire.frame("activate", "host.activate", {"configuration_id": "synthetic-policy-v1"}))
        await wire.read()
        await wire.send(wire.frame("create", "session.create", {"title": "Identity validation"}))
        session_id = (await wire.read())["result"]["session"]["id"]
        for field, value in (("operation_id", "has space"), ("attempt_id", "x" * 257), ("request_id", "has space")):
            invalid = wire.frame("invalid", "session.prompt", {
                "configuration_id": "synthetic-policy-v1", "session_id": session_id,
                "text": "Must not become an input.",
            })
            await wire.send({**invalid, field: value})
        await wire.send(wire.frame("messages", "session.messages", {"session_id": session_id}))
        messages = await wire.read()
        assert messages["request_id"] == "messages"
        assert messages["result"]["messages"] == []
        await wire.send(wire.frame("status", "host.status"))
        status = await wire.read()
        assert status["request_id"] == "status"
        assert status["result"]["modelCalls"] == 0


async def test_close_reply_follows_all_admitted_replies_under_pipe_backpressure(tmp_path):
    async with wire_host(tmp_path, test={"hold_ms": 1000}) as wire:
        await wire.send(wire.frame("activate", "host.activate", {"configuration_id": "synthetic-policy-v1"}))
        await wire.read()
        await wire.send(wire.frame("create", "session.create", {"title": "Close ordering"}))
        session_id = (await wire.read())["result"]["session"]["id"]
        await wire.send(wire.frame("prompt", "session.prompt", {
            "session_id": session_id, "configuration_id": "synthetic-policy-v1", "text": "Synthetic held input",
        }))
        await wire.read()
        for index in range(50):
            await wire.send(wire.frame(f"started-{index}", "host.status"))
            if (await wire.read())["result"]["modelCalls"] == 1:
                break
            await asyncio.sleep(0.02)
        else:
            pytest.fail("Synthetic model did not start.")
        await wire.send(wire.frame("cancel", "session.cancel", {"session_id": session_id}))
        await asyncio.sleep(0.03)
        data = [wire.frame(f"large-{index}", "session.create", {"title": "Synthetic " + "x" * 180000}) for index in range(3)]
        await wire.send(*data, wire.frame("close", "host.close"))
        await asyncio.sleep(0.1)  # Stop observing briefly so the real output pipe applies pressure.
        replies = []
        while True:
            response = await wire.read()
            replies.append(response)
            if response["request_id"] == "close":
                break
        assert {response["request_id"] for response in replies} == {"cancel", "large-0", "large-1", "large-2", "close"}
        assert replies[-1]["outcome"] == "cancelled_settled"
        assert all(response["outcome"] != "accepted_pending" for response in replies)
        await asyncio.wait_for(wire.child.wait(), 5)
        assert wire.child.returncode == 0


async def test_node_result_capacity_rejects_further_work_but_preserves_controls(tmp_path):
    process = ManagedHarnessProcess()
    try:
        await process.start(config(tmp_path, scripted=True, ipc={"max_result_records": 3}))
        await request(process, "host.activate", {"configuration_id": "synthetic-policy-v1"})
        created = await request(process, "session.create", {"title": "Bounded record lesson"}, "create")
        session_id = created["result"]["session"]["id"]
        saved = await request(process, "session.get", {"session_id": session_id})
        assert saved["outcome"] == "committed_reference"
        for index in range(50):
            rejected = await request(process, "session.create", {"title": "Must not be created"}, f"exhausted-{index}")
            assert rejected["outcome"] == "rejected_before_admission"
            assert rejected["error"]["code"] == "result_capacity"
        assert await process.query_result(saved["request_id"]) == saved
        status = await request(process, "host.status")
        assert status["result"]["state"] == "ready"
        assert status["result"]["modelCalls"] == 0
    finally:
        assert (await process.close(15))["state"] == "closed"


async def test_node_retained_reply_bytes_exhaust_before_record_count(tmp_path):
    process = ManagedHarnessProcess()
    try:
        await process.start(config(tmp_path, scripted=True, ipc={
            "max_frame_bytes": 4096, "max_result_records": 256, "max_result_bytes": 16384,
        }))
        activated = await request(process, "host.activate", {"configuration_id": "synthetic-policy-v1"})
        assert activated["outcome"] == "committed_reference"
        for index in range(12):
            result = await request(process, "session.create", {"title": "Synthetic " + "x" * 2400}, f"create-{index}")
            if result["outcome"] == "rejected_before_admission":
                assert result["error"]["code"] == "result_capacity"
                break
            assert result["outcome"] == "committed_reference", result
        else:
            pytest.fail("Node retained replies exceeded their byte budget.")
        assert (await request(process, "host.status"))["result"]["modelCalls"] == 0
    finally:
        assert (await process.close(15))["state"] == "closed"


async def test_node_inflight_admission_rejects_excess_and_keeps_status_available(tmp_path):
    process = ManagedHarnessProcess()
    try:
        await process.start(config(tmp_path, scripted=True, ipc={"max_inflight": 1}))
        await request(process, "host.activate", {"configuration_id": "synthetic-policy-v1"})
        pending = [asyncio.create_task(request(process, "session.create", {"title": f"Lesson {i}"}, f"create-{i}")) for i in range(6)]
        status = await request(process, "host.status")
        responses = await asyncio.gather(*pending)
        assert status["outcome"] == "committed_reference"
        assert any(response.get("error", {}).get("code") == "overloaded" for response in responses)
        assert any(response["outcome"] == "committed_reference" for response in responses)
        for response in responses:
            assert await process.query_result(response["request_id"]) == response
    finally:
        assert (await process.close(15))["state"] == "closed"


async def held_learning_turn(process):
    await request(process, "host.activate", {"configuration_id": "synthetic-policy-v1"})
    created = await request(process, "session.create", {"title": "Synthetic glomerular learning"}, "held-create")
    session_id = created["result"]["session"]["id"]
    submitted = await request(process, "session.prompt", {
        "session_id": session_id, "text": "Explain a synthetic learning case.",
        "configuration_id": "synthetic-policy-v1",
    }, "held-prompt")
    assert submitted["outcome"] == "committed_reference"
    async with asyncio.timeout(10):
        while (await request(process, "host.status"))["result"]["modelCalls"] != 1:
            await asyncio.sleep(0.02)
    return session_id


async def test_cancel_remains_pending_until_native_interruption_settles(tmp_path):
    process = ManagedHarnessProcess()
    try:
        await process.start(config(tmp_path, scripted=True, test={"hold_ms": 1000}))
        session_id = await held_learning_turn(process)
        pending = await process.request("session.cancel", {"session_id": session_id}, "cancel", "1", 0.02)
        assert pending["outcome"] == "accepted_pending"
        assert (await request(process, "host.status"))["outcome"] == "committed_reference"
        async with asyncio.timeout(5):
            while True:
                result = await process.query_result(pending["request_id"])
                if result["outcome"] != "accepted_pending":
                    break
                await asyncio.sleep(0.02)
        assert result["outcome"] == "cancelled_settled"
        assert result["result"]["interrupted"] is True
        assert (await terminal_session(process, session_id))["outcome"] == "interrupted"
        assert (await request(process, "host.status"))["result"]["modelCalls"] == 1
    finally:
        assert (await process.close(15))["state"] == "closed"


async def test_close_timeout_reports_blocked_until_actual_sdk_drain_and_exit(tmp_path):
    process = ManagedHarnessProcess()
    try:
        await process.start(config(tmp_path, scripted=True, test={"hold_ms": 1000}))
        await held_learning_turn(process)
        pending = await process.request("host.close", {}, "drain", "1", 0.02)
        assert pending["outcome"] == "accepted_pending"
        assert (await process.close(0.02))["state"] == "blocked"
        status = await request(process, "host.status")
        assert status["result"]["state"] == "blocked"
        assert status["result"]["outcome"] == "uncertain_after_disconnect"
        assert (await process.query_result(pending["request_id"]))["outcome"] == "accepted_pending"
        assert (await process.close(15))["state"] == "closed"
        assert (await process.query_result(pending["request_id"]))["outcome"] == "cancelled_settled"
    finally:
        assert (await process.close(15))["state"] == "closed"


async def test_reopened_held_work_requires_explicit_complete_recovery_admission(tmp_path):
    process = ManagedHarnessProcess()
    try:
        await process.start(config(tmp_path, scripted=True, test={"hold_ms": 600}))
        session_id = await held_learning_turn(process)
        assert (await process.close(0.02))["state"] == "blocked"
        assert (await process.close(15))["state"] == "closed"
        process = ManagedHarnessProcess()
        await process.start(config(tmp_path, scripted=True))
        status = (await request(process, "host.status"))["result"]
        assert status["heldSessionIds"] == [session_id]
        assert status["modelCalls"] == 0
        await request(process, "host.activate", {"configuration_id": "synthetic-policy-v1"})
        rejected = await request(process, "host.recover", {"configuration_id": "synthetic-policy-v1", "session_ids": []})
        assert rejected["outcome"] == "rejected_before_admission"
        assert rejected["error"]["code"] == "recovery_admission_mismatch"
        assert (await request(process, "host.status"))["result"]["modelCalls"] == 0
        recovered = await request(process, "host.recover", {"configuration_id": "synthetic-policy-v1", "session_ids": [session_id]})
        assert recovered["outcome"] == "committed_reference"
        assert (await terminal_session(process, session_id))["outcome"] == "succeeded"
        status = (await request(process, "host.status"))["result"]
        assert status["modelCalls"] == 1
        assert status["heldSessionIds"] == []
    finally:
        assert (await process.close(15))["state"] == "closed"


async def test_native_transcript_cursor_pages_reopen_with_the_latest_turn(tmp_path):
    process = ManagedHarnessProcess()
    settings = config(tmp_path, scripted=True, test={"answers": ["CKD answer", "AKI answer", "Electrolyte answer"]})
    try:
        await process.start(settings)
        await request(process, "host.activate", {"configuration_id": "synthetic-policy-v1"})
        created = await request(process, "session.create", {"title": "Nephrology learning"}, "create")
        session_id = created["result"]["session"]["id"]
        receipts = []
        for turn in range(1, 4):
            receipt = await request(process, "session.prompt", {
                "session_id": session_id, "configuration_id": "synthetic-policy-v1",
                "text": f"Synthetic lesson {turn}",
            }, f"learning-{turn}")
            receipts.append(receipt["result"]["inputId"])
            for observation in range(100):
                messages = (await request(process, "session.messages", {"session_id": session_id}))["result"]["messages"]
                assistants = [message for message in messages if message["type"] == "assistant"]
                if len(assistants) == turn and messages[-1].get("outcome") == "succeeded":
                    break
                await asyncio.sleep(0.05)
            else:
                pytest.fail(f"Turn {turn} did not complete: {messages!r}")
        before = messages
        assert [message["id"] for message in before if message["type"] == "user"] == receipts
        first = await request(process, "session.messages", {"session_id": session_id, "limit": 2, "order": "asc"})
        page = first["result"]
        assert page["messages"] == before[:2]
        assert isinstance(page["cursor"]["next"], str)
        cursor = page["cursor"]["next"]
        assert (await process.close(15))["state"] == "closed"
        process = ManagedHarnessProcess()
        await process.start(settings)
        after = list(page["messages"])
        while cursor:
            page = (await request(process, "session.messages", {"session_id": session_id, "limit": 2, "cursor": cursor}))["result"]
            assert len(page["messages"]) <= 2
            after.extend(page["messages"])
            cursor = page["cursor"].get("next")
        assert after == before
        assert [message for message in after if message["type"] == "assistant"][-1]["content"][0]["text"] == "Electrolyte answer"
        assert (await request(process, "host.status"))["result"]["modelCalls"] == 0
    finally:
        assert (await process.close(15))["state"] == "closed"
