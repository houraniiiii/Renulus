"""Operation ownership at the public callback and managed-process seams."""
import asyncio
from dataclasses import asdict
import json
import pytest

from renulus.runtime.harness_domain import DomainBinding, DomainCallbacks, DomainGrant
from renulus.runtime.harness_process import ManagedHarnessProcess
from tests.runtime.test_harness_domain import config, wait_domain


IDENTITY = {"protocol": "renulus-harness/1", "profile_id": "synthetic-profile",
            "store_id": "synthetic-runtime", "generation": "synthetic-generation",
            "token": "synthetic-token"}
BINDINGS = {name: DomainBinding(name, "attempt-1", "session-" + name,
                               "input-" + name, "cancel-" + name)
            for name in ("learning-first", "learning-second")}


def frame(operation):
    return {**IDENTITY, **asdict(BINDINGS[operation]), "kind": "domain_request",
            "callback_id": "callback-" + operation, "command": "synthetic.extract",
            "payload": {"topic": "synthetic learning"}}


async def wait_inactive(status, operation):
    async with asyncio.timeout(2):
        while status(operation_id=operation)["active"]:
            await asyncio.sleep(0)


async def test_operation_status_retains_handler_finalizer_and_queued_publication():
    entered = {operation: asyncio.Event() for operation in BINDINGS}
    finish = {operation: asyncio.Event() for operation in BINDINGS}
    writing = {operation: asyncio.Event() for operation in BINDINGS}
    capacity = {operation: asyncio.Event() for operation in BINDINGS}
    finalizing, finalize = asyncio.Event(), asyncio.Event()
    sent = []

    async def handler(request, cancellation):
        operation = request.binding.operation_id
        try:
            entered[operation].set()
            await finish[operation].wait()
            return {"answer": operation}
        finally:
            if operation == "learning-first":
                finalizing.set()
                await finalize.wait()

    async def authority(request):
        return DomainGrant(request.binding, handler, lambda: True)

    async def send(wire, callback_id):
        operation = json.loads(wire)["operation_id"]
        writing[operation].set()
        await capacity[operation].wait()
        sent.append(json.loads(wire))

    callbacks = DomainCallbacks(IDENTITY, authority, send, max_inflight=2,
                                max_records=4, max_bytes=40000, max_frame=4096)
    settlement = None
    try:
        for operation in BINDINGS:
            callbacks.accept(frame(operation))
        await asyncio.wait_for(asyncio.gather(*(event.wait() for event in entered.values())), 2)
        first = callbacks.status(operation_id="learning-first")
        second = callbacks.status(operation_id="learning-second")
        assert first["active"] == second["active"] == 1
        assert first["retained"] == second["retained"] == 1
        assert first["bytes"] > 0 and second["bytes"] > 0
        assert first["bytes"] + second["bytes"] == callbacks.status()["bytes"]
        assert callbacks.status()["active"] == callbacks.status()["retained"] == 2
        assert callbacks.status(operation_id="unknown") == {
            "active": 0, "retained": 0, "bytes": 0, "accepting": True}

        finish["learning-first"].set()
        await asyncio.wait_for(finalizing.wait(), 2)
        assert callbacks.status(operation_id="learning-first")["active"] == 1
        finalize.set()
        await asyncio.wait_for(writing["learning-first"].wait(), 2)
        assert callbacks.result("callback-learning-first")["outcome"] == "committed_reference"
        assert callbacks.status(operation_id="learning-first")["active"] == 1
        settlement = asyncio.create_task(callbacks.settled())
        await asyncio.sleep(0)
        assert not settlement.done() and not sent

        capacity["learning-first"].set()
        await wait_inactive(callbacks.status, "learning-first")
        await asyncio.sleep(0)  # Let legacy aggregate task-bookkeeping callbacks run.
        assert callbacks.status(operation_id="learning-second")["active"] == 1
        assert callbacks.status()["active"] == 1
        assert [value["operation_id"] for value in sent] == ["learning-first"]
        finish["learning-second"].set()
        capacity["learning-second"].set()
        await asyncio.wait_for(settlement, 2)
        for operation in BINDINGS:
            assert callbacks.status(operation_id=operation)["active"] == 0
            assert callbacks.status(operation_id=operation)["retained"] == 1
        assert callbacks.status()["active"] == 0
        assert set(callbacks.status()) == {"active", "retained", "bytes", "accepting"}
    finally:
        finalize.set()
        for event in (*finish.values(), *capacity.values()):
            event.set()
        await asyncio.wait_for(callbacks.settled(), 2)
        if settlement is not None:
            await settlement


async def test_operation_status_retains_replay_until_its_publication_settles():
    capacity, writing = asyncio.Event(), asyncio.Event()
    capacity.set()
    effects = []

    async def handler(request, cancellation):
        effects.append(request.callback_id)
        return {"answer": "synthetic answer"}

    async def authority(request):
        return DomainGrant(request.binding, handler, lambda: True)

    async def send(wire, callback_id):
        writing.set()
        await capacity.wait()

    callbacks = DomainCallbacks(IDENTITY, authority, send, max_inflight=2,
                                max_records=4, max_bytes=40000, max_frame=4096)
    try:
        for operation in BINDINGS:
            callbacks.accept(frame(operation))
        await asyncio.wait_for(callbacks.settled(), 2)
        retained = callbacks.status(operation_id="learning-first")
        capacity.clear()
        writing.clear()
        callbacks.accept(frame("learning-first"))
        await asyncio.wait_for(writing.wait(), 2)
        assert callbacks.status(operation_id="learning-first") == {**retained, "active": 1}
        assert callbacks.status(operation_id="learning-second")["active"] == 0
        assert callbacks.status()["active"] == 0  # Existing aggregate excludes the auxiliary slot.
        assert effects == ["callback-learning-first", "callback-learning-second"]
        capacity.set()
        await asyncio.wait_for(callbacks.settled(), 2)
        assert callbacks.status(operation_id="learning-first") == retained
    finally:
        capacity.set()
        await asyncio.wait_for(callbacks.settled(), 2)


async def test_process_operation_status_keeps_finalizer_and_nested_operation_separate(tmp_path):
    entered = {operation: asyncio.Event() for operation in BINDINGS}
    finish = {operation: asyncio.Event() for operation in BINDINGS}
    finalizing, finalize = asyncio.Event(), asyncio.Event()

    async def handler(request, cancellation):
        operation = request.binding.operation_id
        try:
            entered[operation].set()
            await finish[operation].wait()
            if operation == "learning-second":
                nested = await process.request("session.prompt", {"text": "Synthetic extraction"},
                    "nested-learning-second", "attempt-1", 2)
                return {"answer": nested["result"]["text"]}
            return {"answer": "synthetic first answer"}
        finally:
            if operation == "learning-first":
                finalizing.set()
                await finalize.wait()

    async def authority(request):
        return DomainGrant(request.binding, handler, lambda: True)

    process = ManagedHarnessProcess(domain_authority=authority)
    await process.start(config(tmp_path, max_inflight=2, max_domain_inflight=2))
    try:
        await process.request("session.get", {"emit_only": True, "callbacks": [
            {**asdict(binding), "callback_id": "callback-" + operation}
            for operation, binding in BINDINGS.items()]}, "observe", "attempt-1", 2)
        await asyncio.wait_for(asyncio.gather(*(event.wait() for event in entered.values())), 2)
        assert process.domain_status(operation_id="learning-first")["active"] == 1
        assert process.domain_status(operation_id="learning-second")["active"] == 1
        finish["learning-first"].set()
        await asyncio.wait_for(finalizing.wait(), 2)
        assert process.cancel_domain("cancel-learning-first") == 1
        finish["learning-second"].set()
        await wait_inactive(process.domain_status, "learning-second")
        assert process.domain_result("callback-learning-second")["result"] == {
            "answer": "Synthetic extraction result."}
        assert process.domain_status(operation_id="learning-first")["active"] == 1
        assert (await process.close(0.1))["state"] == "blocked"
        assert (await process.settlement(0.01))["state"] == "pending"
        assert process.domain_status(operation_id="learning-first")["active"] == 1
        assert process.domain_status(operation_id="learning-second")["active"] == 0
        finalize.set()
        assert (await process.settlement(2))["state"] == "settled"
        assert process.domain_result("callback-learning-first")["outcome"] == "cancelled_settled"
        assert process.domain_status(operation_id="learning-first")["active"] == 0
        assert process.domain_status(operation_id="learning-first")["accepting"] is False
    finally:
        finalize.set()
        for event in finish.values():
            event.set()
        await process.close(2)


async def test_process_operation_status_retains_both_replies_behind_a_full_pipe(tmp_path):
    entered = {operation: asyncio.Event() for operation in BINDINGS}
    finish = asyncio.Event()

    async def handler(request, cancellation):
        entered[request.binding.operation_id].set()
        await finish.wait()
        return {"answer": request.binding.operation_id}

    async def authority(request):
        return DomainGrant(request.binding, handler, lambda: True)

    process = ManagedHarnessProcess(domain_authority=authority)
    await process.start(config(tmp_path, max_domain_inflight=2,
                               boot_settings={"test": {"read_pause": 1.5}}))
    try:
        await process.request("session.get", {"emit_only": True, "callbacks": [
            {**asdict(binding), "callback_id": "callback-" + operation}
            for operation, binding in BINDINGS.items()]}, "observe", "attempt-1", 0.01)
        await asyncio.wait_for(asyncio.gather(*(event.wait() for event in entered.values())), 2)
        # The public synthetic peer pauses reads; this frame fills the owned pipe.
        await process.request("session.prompt", {"text": "x" * 200000}, "pipe-filler", "1", 0.01)
        finish.set()
        for operation in BINDINGS:
            assert (await wait_domain(process, "callback-" + operation))["outcome"] == "committed_reference"
            observed = process.domain_status(operation_id=operation)
            assert observed["active"] == observed["retained"] == 1
            assert observed["bytes"] > 0
        assert process.domain_status()["active"] == 2
        assert process.cancel_domain("cancel-learning-first") == 1
        async with asyncio.timeout(3):
            while True:
                reply = await process.request("host.status", {}, "observe-pipe", "1", 2)
                outcomes = reply["result"]["domain_results"]
                if len(outcomes) == 2:
                    break
                await asyncio.sleep(0)
        delivered = {value["operation_id"]: value for value in outcomes}
        assert delivered["learning-first"]["outcome"] == "cancelled_settled"
        assert "result" not in delivered["learning-first"]
        assert delivered["learning-second"]["outcome"] == "committed_reference"
        for operation in BINDINGS:
            await wait_inactive(process.domain_status, operation)
        assert (await process.close(2))["state"] == "closed"
        assert (await process.settlement(0))["state"] == "settled"
    finally:
        finish.set()
        await process.close(2)


def test_filtered_process_status_before_start_preserves_the_default_projection():
    process = ManagedHarnessProcess()
    assert process.domain_status() == {"active": 0, "retained": 0}
    assert process.domain_status(operation_id="unknown") == {
        "active": 0, "retained": 0, "bytes": 0, "accepting": False}


@pytest.mark.parametrize("traffic", ["overload", "conflict"])
async def test_operation_status_tracks_unretained_auxiliary_reply_ownership(traffic):
    entered, finish, writing, capacity = (asyncio.Event() for _ in range(4))

    async def handler(request, cancellation):
        entered.set()
        await finish.wait()
        return {"answer": "synthetic answer"}

    async def authority(request):
        return DomainGrant(request.binding, handler, lambda: True)

    async def send(wire, callback_id):
        if json.loads(wire)["operation_id"] == "learning-second":
            writing.set()
            await capacity.wait()

    callbacks = DomainCallbacks(IDENTITY, authority, send, max_inflight=1,
                                max_records=4, max_bytes=40000, max_frame=4096)
    try:
        callbacks.accept(frame("learning-first"))
        await asyncio.wait_for(entered.wait(), 2)
        rejected = frame("learning-second")
        if traffic == "conflict":
            rejected["callback_id"] = "callback-learning-first"
        callbacks.accept(rejected)
        await asyncio.wait_for(writing.wait(), 2)
        assert callbacks.status(operation_id="learning-second") == {
            "active": 1, "retained": 0, "bytes": 0, "accepting": True}
        assert callbacks.status(operation_id="learning-first")["active"] == 1
        assert callbacks.status()["active"] == callbacks.status()["retained"] == 1
        callbacks.seal()
        assert callbacks.status(operation_id="learning-second")["active"] == 1
        assert callbacks.status(operation_id="learning-second")["accepting"] is False
        capacity.set()
        await wait_inactive(callbacks.status, "learning-second")
    finally:
        capacity.set()
        finish.set()
        await asyncio.wait_for(callbacks.settled(), 2)
