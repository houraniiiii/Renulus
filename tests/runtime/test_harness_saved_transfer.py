# SPDX-License-Identifier: MIT
"""Public synthetic process protocol; no native SDK/model/Owner proof."""
import asyncio
from dataclasses import replace
import hashlib
import json

import pytest

from renulus.contracts import ApiError
from renulus.learn.harness_migration import NativeReadback, TransferRequest
from renulus.runtime.harness_process import NativeProcessIdentity
from renulus.runtime.harness_saved_transfer import HarnessSavedTransfer


SESSION = "ses_39729055b0a67607c1a31f26bc9b23caf3614d947cab46c4507ee08e0843f6ec"
ALIASES = ("msg_2fbfc6fcf5f24433924991633fc7c804cd546b885e23fc35912939a121f822f3",
           "msg_3179ac6ee259548f5c678e725332f9ec0e172c54dd38cc59f4fe0cb50050d28e")


def document(text="Synthetic retained partial explanation. α"):
    value = {"format": "renulus.saved-session/1", "conversationId": "legacy_chat",
        "title": "Synthetic saved nephrology", "messages": [
            {"id": "user_1", "role": "user", "content": "Discuss transplant rejection.",
             "runId": "legacy_run", "createdAt": "2026-10-10T12:00:00Z", "citations": []},
            {"id": "assistant_1", "role": "assistant", "content": text,
             "runId": "legacy_run", "createdAt": "2026-10-10T12:00:01Z",
             "completedAt": "2026-10-10T12:00:02Z", "legacyOutcome": "interrupted",
             "citations": [{"passage_id": "synthetic_passage",
                            "locators": [{"kind": "pdf", "physical_page": 7}]}]}]}
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()


def request_for(source):
    return TransferRequest("migration_synthetic", "profile_synthetic", "runtime_synthetic",
        SESSION, hashlib.sha256(source).hexdigest())


class ControlledProcess:
    """Only the published request/query/release/identity seam is simulated."""
    def __init__(self):
        self.identity = NativeProcessIdentity(4321, "profile_synthetic", "runtime_synthetic", "generation_1")
        self.requests = []
        self.queries = []
        self.releases = []
        self.parts = {}
        self.imported = False
        self.replies = {}
        self.terminals = {}
        self.pending_command = None
        self.queried = asyncio.Event()
        self.hold_command = None
        self.request_gate = asyncio.Event()
        self.request_entered = asyncio.Event()
        self.release_gate = None
        self.release_entered = asyncio.Event()
        self.cancelled = []
        self.transform = None
        self.query_transform = None
        self.stage_delay = 0

    def native_identity(self):
        return self.identity

    async def request(self, command, payload, operation_id, attempt_id, timeout):
        entry = {"command": command, "payload": json.loads(json.dumps(payload)),
                 "operation_id": operation_id, "attempt_id": attempt_id,
                 "request_id": "request_" + str(len(self.requests))}
        self.requests.append(entry)
        if command == "session.import.stage" and self.stage_delay:
            await asyncio.sleep(self.stage_delay)
        if command == self.hold_command:
            self.request_entered.set()
            try:
                await self.request_gate.wait()
            except asyncio.CancelledError:
                self.cancelled.append(command)
                raise
        result = self.finish(entry)
        self.terminals[entry["request_id"]] = result
        if command == self.pending_command:
            result = {**result, "outcome": "accepted_pending", "result": {"state": "pending"}}
        self.replies[entry["request_id"]] = result
        return result

    def finish(self, entry):
        command, payload = entry["command"], entry["payload"]
        if command == "session.import.stage":
            assert len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()) <= 48 * 1024
            self.parts[(entry["operation_id"], payload["partIndex"])] = payload["chunk"]
            parts = [chunk for (operation, _), chunk in self.parts.items() if operation == entry["operation_id"]]
            result = {"state": "staged", "sessionId": payload["sessionId"],
                "bundleDigest": payload["bundleDigest"], "receivedParts": len(parts),
                "receivedBytes": sum(len(part.encode()) for part in parts),
                "complete": len(parts) == payload["partCount"]}
        elif command in {"session.import", "session.import.inspect"}:
            if command == "session.import":
                self.imported = True
            result = {"state": "verified" if self.imported else "absent",
                      "sessionId": payload["sessionId"], "bundleDigest": payload["bundleDigest"]}
            if self.imported:
                result["messageCount"] = 2
        elif command == "operation.retire":
            assert payload == {}
            result = {"state": "retired"}
        else:
            raise AssertionError("Unexpected command at the public seam: " + command)
        reply = {"protocol": "renulus-harness/1", "profile_id": self.identity.profile_id,
            "store_id": self.identity.store_id, "generation": self.identity.generation,
            "operation_id": entry["operation_id"], "attempt_id": entry["attempt_id"],
            "request_id": entry["request_id"], "kind": "reply",
            "outcome": "committed_reference", "result": result}
        return self.transform(command, reply) if self.transform else reply

    async def query_result(self, request_id):
        self.queries.append(request_id)
        self.queried.set()
        result = self.replies.get(request_id)
        return self.query_transform(result) if self.query_transform else result

    def publish_terminal(self, request_id):
        self.replies[request_id] = self.terminals[request_id]

    async def release_observation(self, request_id):
        self.releases.append(request_id)
        self.release_entered.set()
        if self.release_gate is not None:
            try:
                await self.release_gate.wait()
            except asyncio.CancelledError:
                self.cancelled.append("release")
                raise
        return True


@pytest.mark.asyncio
async def test_stage_sends_exact_unicode_bytes_in_bounded_serialized_parts():
    process = ControlledProcess()
    source = document('α𐀀\n"\\' * 14000)
    request = request_for(source)
    adapter = HarnessSavedTransfer(process, observation_timeout=0.2)
    await adapter.stage(request, document=source)
    sent = process.requests
    assert 1 < len(sent) <= 256
    assert b"".join(item["payload"]["chunk"].encode() for item in sent) == source
    assert [item["payload"]["partIndex"] for item in sent] == list(range(len(sent)))
    assert all(item["command"] == "session.import.stage" and
        item["operation_id"] == request.migration_id and item["attempt_id"] == "1" and
        item["payload"]["sessionId"] == SESSION and
        item["payload"]["bundleDigest"] == request.bundle_digest and
        item["payload"]["partCount"] == len(sent) and
        item["payload"]["totalBytes"] == len(source) for item in sent)


@pytest.mark.asyncio
async def test_exact_native_readback_and_retirement_use_the_reserved_operation_only():
    process = ControlledProcess()
    source = document()
    request = request_for(source)
    adapter = HarnessSavedTransfer(process, observation_timeout=0.2)
    await adapter.stage(request, document=source)
    assert await adapter.inspect(request) is None
    await adapter.commit(request)
    result = await adapter.inspect(request)
    assert result == NativeReadback(request, ALIASES, 2, 1, 1, "settled")
    await adapter.commit(request)
    assert [item["command"] for item in process.requests].count("session.import") == 1
    assert len(process.releases) == 2
    assert await adapter.retire(request) == "retired"
    assert await adapter.retire(request) == "retired"
    assert [item["command"] for item in process.requests].count("operation.retire") == 1
    with pytest.raises(ApiError) as refused:
        await adapter.stage(request, document=source)
    assert refused.value.code == "transfer_retired"


@pytest.mark.asyncio
async def test_pending_import_timeout_observes_original_request_without_resending():
    process = ControlledProcess()
    source = document()
    request = request_for(source)
    adapter = HarnessSavedTransfer(process, observation_timeout=0.03)
    await adapter.stage(request, document=source)
    process.pending_command = "session.import"
    with pytest.raises(ApiError) as timeout:
        await adapter.commit(request)
    assert timeout.value.code == "harness_migration_observation_timeout"
    command = process.requests[-1]
    assert command["command"] == "session.import"
    assert process.queries and set(process.queries) == {command["request_id"]}
    process.publish_terminal(command["request_id"])
    await adapter.commit(request)
    assert [item["command"] for item in process.requests].count("session.import") == 1
    assert command["request_id"] not in process.releases
    await adapter.close()


@pytest.mark.asyncio
async def test_cancelled_initial_observer_retains_request_until_actual_drain():
    process = ControlledProcess()
    source = document()
    request = request_for(source)
    adapter = HarnessSavedTransfer(process, observation_timeout=0.2)
    await adapter.stage(request, document=source)
    process.hold_command = "session.import"
    observer = asyncio.create_task(adapter.commit(request))
    await asyncio.wait_for(process.request_entered.wait(), 1)
    observer.cancel()
    with pytest.raises(asyncio.CancelledError):
        await observer
    closing = asyncio.create_task(adapter.close())
    try:
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(asyncio.shield(closing), 0.02)
        assert process.cancelled == []
        assert [item["command"] for item in process.requests].count("session.import") == 1
    finally:
        process.request_gate.set()
        await asyncio.wait_for(closing, 1)
    await adapter.commit(request)
    assert process.cancelled == []


@pytest.mark.asyncio
@pytest.mark.parametrize("defect,code", [
    ("digest", "harness_migration_conflict"), ("utf8", "harness_migration_source"),
    ("mutable", "harness_migration_source"), ("duplicate", "harness_migration_source"),
    ("role", "harness_migration_source"), ("messages", "harness_migration_budget"),
    ("bytes", "harness_migration_budget"), ("parts", "harness_migration_budget"),
])
async def test_invalid_or_over_budget_bundle_denies_before_any_request(defect, code):
    process = ControlledProcess()
    source = document()
    if defect == "utf8":
        source = b"\xff"
    elif defect == "mutable":
        source = bytearray(source)
    elif defect == "bytes":
        source = b"x" * (8 * 1024 * 1024 + 1)
    elif defect == "parts":
        source = document('"' * 3500000)
    elif defect in {"duplicate", "role", "messages"}:
        parsed = json.loads(source)
        if defect == "duplicate":
            parsed["messages"][1]["id"] = "user_1"
        elif defect == "role":
            parsed["messages"][1]["role"] = "tool"
        else:
            parsed["messages"] = [{**parsed["messages"][0], "id": "user_" + str(index)} for index in range(4097)]
        source = json.dumps(parsed).encode()
    request = request_for(source)
    if defect == "digest":
        request = replace(request, bundle_digest="0" * 64)
    adapter = HarnessSavedTransfer(process, observation_timeout=0.2)
    with pytest.raises(ApiError) as refusal:
        await adapter.stage(request, document=source)
    assert refusal.value.code == code
    assert process.requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize("defect", ["session", "digest", "count", "bool", "float", "missing", "extra", "absent_extra"])
async def test_inspection_never_accepts_approximate_native_readback(defect):
    process = ControlledProcess()
    source = document()
    request = request_for(source)
    adapter = HarnessSavedTransfer(process, observation_timeout=0.2)
    await adapter.stage(request, document=source)
    if defect != "absent_extra":
        await adapter.commit(request)
    def alter(command, reply):
        if command == "session.import.inspect":
            result = reply["result"]
            if defect == "session":
                result["sessionId"] = "ses_" + "0" * 64
            elif defect == "digest":
                result["bundleDigest"] = "0" * 64
            elif defect in {"count", "bool", "float"}:
                result["messageCount"] = {"count": 3, "bool": True, "float": 2.0}[defect]
            elif defect == "missing":
                del result["bundleDigest"]
            else:
                result["messageCount" if defect == "absent_extra" else "unknown"] = 0
        return reply
    process.transform = alter
    with pytest.raises(ApiError) as refusal:
        await adapter.inspect(request)
    assert refusal.value.code == "harness_migration_readback"
    await adapter.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("field,value", [("profile_id", "other_profile"),
    ("store_id", "other_store"), ("generation", "generation_2"), ("pid", 9876)])
async def test_native_scope_change_after_request_cannot_publish_readback(field, value):
    process = ControlledProcess()
    source = document()
    request = request_for(source)
    adapter = HarnessSavedTransfer(process, observation_timeout=0.2)
    await adapter.stage(request, document=source)
    def change(command, reply):
        process.identity = replace(process.identity, **{field: value})
        return reply
    process.transform = change
    with pytest.raises(ApiError) as refusal:
        await adapter.inspect(request)
    assert refusal.value.code == "harness_migration_identity"
    assert process.releases == []
    await adapter.close()


@pytest.mark.asyncio
async def test_uncertain_native_import_preserves_safe_code_and_never_resends():
    process = ControlledProcess()
    source = document()
    request = request_for(source)
    adapter = HarnessSavedTransfer(process, observation_timeout=0.2)
    await adapter.stage(request, document=source)
    def fail(command, reply):
        if command == "session.import":
            return {**reply, "outcome": "uncertain_after_disconnect",
                    "error": {"code": "transfer_native_failed", "message": "Untrusted bytes must not be exposed."}}
        return reply
    process.transform = fail
    for _ in range(2):
        with pytest.raises(ApiError) as failure:
            await adapter.commit(request)
        assert failure.value.code == "transfer_native_failed"
        assert "Untrusted bytes" not in str(failure.value)
    assert [item["command"] for item in process.requests].count("session.import") == 1
    assert process.releases == []
    await adapter.close()


@pytest.mark.asyncio
async def test_replacement_adapter_inspects_exact_source_before_any_possible_import():
    process = ControlledProcess()
    source = document()
    request = request_for(source)
    original = HarnessSavedTransfer(process, observation_timeout=0.03)
    await original.stage(request, document=source)
    process.pending_command = "session.import"
    with pytest.raises(ApiError):
        await original.commit(request)
    replacement = HarnessSavedTransfer(process, observation_timeout=0.2)
    try:
        await replacement.stage(request, document=source)
        assert await replacement.inspect(request) == NativeReadback(request, ALIASES, 2, 1, 1, "settled")
        await replacement.commit(request)
        assert [item["command"] for item in process.requests].count("session.import") == 1
    finally:
        for item in process.requests:
            process.publish_terminal(item["request_id"])
        await original.close()
        await replacement.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["operation_id", "attempt_id", "request_id", "generation", "store_id"])
async def test_pending_observation_rejects_misrouted_identity(field):
    process = ControlledProcess()
    source = document()
    request = request_for(source)
    adapter = HarnessSavedTransfer(process, observation_timeout=0.2)
    await adapter.stage(request, document=source)
    process.pending_command = "session.import.inspect"
    process.query_transform = lambda result: {**result, field: "wrong_identity"}
    with pytest.raises(ApiError) as refused:
        await adapter.inspect(request)
    assert refused.value.code == "harness_migration_response"
    assert len(process.queries) == 1 and process.releases == []
    await adapter.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [0, -1, True, float("inf"), float("nan"), 46])
async def test_observation_budget_must_be_explicit_finite_and_bounded(value):
    process = ControlledProcess()
    with pytest.raises(ValueError):
        HarnessSavedTransfer(process, observation_timeout=value)
    assert process.requests == []


@pytest.mark.asyncio
async def test_pending_retirement_preserves_staged_references_until_exact_ack():
    process = ControlledProcess()
    source = document()
    request = request_for(source)
    adapter = HarnessSavedTransfer(process, observation_timeout=0.2)
    await adapter.stage(request, document=source)
    await adapter.commit(request)
    def pending(command, reply):
        if command == "operation.retire":
            reply["result"] = {"state": "pending"}
        return reply
    process.transform = pending
    assert await adapter.retire(request) == "pending"
    assert await adapter.inspect(request) == NativeReadback(request, ALIASES, 2, 1, 1, "settled")
    process.transform = None
    assert await adapter.retire(request) == "retired"
    assert [item["command"] for item in process.requests].count("operation.retire") == 2
    await adapter.close()


@pytest.mark.asyncio
async def test_staging_capacity_is_retained_without_evicting_an_existing_operation():
    process = ControlledProcess()
    source = document()
    request = request_for(source)
    adapter = HarnessSavedTransfer(process, observation_timeout=0.2)
    for index in range(4):
        await adapter.stage(replace(request, migration_id="migration_" + str(index)), document=source)
    count = len(process.requests)
    with pytest.raises(ApiError) as refusal:
        await adapter.stage(replace(request, migration_id="migration_5"), document=source)
    assert refusal.value.code == "harness_migration_capacity" and len(process.requests) == count
    await adapter.stage(replace(request, migration_id="migration_0"), document=source)
    assert len(process.requests) == count
    await adapter.close()


@pytest.mark.asyncio
async def test_local_api_fault_code_status_and_retryability_are_preserved():
    process = ControlledProcess()
    source = document()
    request = request_for(source)
    adapter = HarnessSavedTransfer(process, observation_timeout=0.2)
    await adapter.stage(request, document=source)
    def fault(command, reply):
        if command == "session.import":
            raise ApiError("synthetic_resolver_unavailable", "Local authority fault.", 503, True)
        return reply
    process.transform = fault
    for _ in range(2):
        with pytest.raises(ApiError) as failure:
            await adapter.commit(request)
        assert (failure.value.code, failure.value.status, failure.value.retryable) == (
            "synthetic_resolver_unavailable", 503, True)
    assert [item["command"] for item in process.requests].count("session.import") == 1
    await adapter.close()


@pytest.mark.asyncio
async def test_one_stage_observation_deadline_covers_all_parts_and_retains_started_writes():
    process = ControlledProcess()
    process.stage_delay = 0.03
    source = document("x" * 110000)
    request = request_for(source)
    adapter = HarnessSavedTransfer(process, observation_timeout=0.05)
    try:
        with pytest.raises(ApiError) as expired:
            await adapter.stage(request, document=source)
        assert expired.value.code == "harness_migration_observation_timeout"
        assert 1 <= len(process.requests) < process.requests[0]["payload"]["partCount"]
    finally:
        await adapter.close()
    assert process.cancelled == []


@pytest.mark.asyncio
async def test_active_journal_reopen_can_retire_without_restaging_legacy_bytes():
    process = ControlledProcess()
    source = document()
    request = request_for(source)
    original = HarnessSavedTransfer(process, observation_timeout=0.2)
    await original.stage(request, document=source)
    await original.commit(request)
    await original.close()
    before = len(process.requests)
    reopened = HarnessSavedTransfer(process, observation_timeout=0.2)
    assert await reopened.retire(request) == "retired"
    assert [item["command"] for item in process.requests[before:]] == ["operation.retire"]
    assert process.requests[-1]["payload"] == {}
    await reopened.close()


@pytest.mark.asyncio
async def test_incomplete_stage_can_be_retired_after_actual_pending_request_settles():
    process = ControlledProcess()
    source = document()
    request = request_for(source)
    adapter = HarnessSavedTransfer(process, observation_timeout=0.03)
    process.pending_command = "session.import.stage"
    with pytest.raises(ApiError) as expired:
        await adapter.stage(request, document=source)
    assert expired.value.code == "harness_migration_observation_timeout"
    process.publish_terminal(process.requests[-1]["request_id"])
    await adapter.settled()
    assert await adapter.retire(request) == "retired"
    assert [item["command"] for item in process.requests] == ["session.import.stage", "operation.retire"]
    await adapter.close()


@pytest.mark.asyncio
async def test_opaque_retirement_keys_count_toward_capacity_and_are_not_evicted():
    process = ControlledProcess()
    request = request_for(document())
    adapter = HarnessSavedTransfer(process, observation_timeout=0.2)
    for index in range(256):
        assert await adapter.retire(replace(request, migration_id="migration_" + str(index))) == "retired"
    with pytest.raises(ApiError) as refusal:
        await adapter.retire(replace(request, migration_id="migration_256"))
    assert refusal.value.code == "harness_migration_capacity"
    assert len(process.requests) == 256
    assert await adapter.retire(replace(request, migration_id="migration_0")) == "retired"
    assert len(process.requests) == 256
    await adapter.close()


@pytest.mark.asyncio
async def test_aggregate_byte_capacity_refuses_new_stage_without_partial_admission():
    process = ControlledProcess()
    source = document("x" * (6 * 1024 * 1024))
    request = request_for(source)
    adapter = HarnessSavedTransfer(process, observation_timeout=5)
    await adapter.stage(replace(request, migration_id="migration_1"), document=source)
    await adapter.stage(replace(request, migration_id="migration_2"), document=source)
    before = len(process.requests)
    with pytest.raises(ApiError) as refusal:
        await adapter.stage(replace(request, migration_id="migration_3"), document=source)
    assert refusal.value.code == "harness_migration_capacity" and len(process.requests) == before
    await adapter.close()


@pytest.mark.asyncio
async def test_held_observation_release_expires_without_inventing_settlement():
    process = ControlledProcess()
    source = document()
    request = request_for(source)
    adapter = HarnessSavedTransfer(process, observation_timeout=0.03)
    await adapter.stage(request, document=source)
    await adapter.commit(request)
    process.release_gate = asyncio.Event()
    with pytest.raises(ApiError) as expired:
        await adapter.inspect(request)
    assert expired.value.code == "harness_migration_observation_timeout"
    assert process.release_entered.is_set() and process.cancelled == []
    closing = asyncio.create_task(adapter.close())
    try:
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(asyncio.shield(closing), 0.02)
    finally:
        process.release_gate.set()
        await asyncio.wait_for(closing, 1)
    assert process.cancelled == []
