# SPDX-License-Identifier: MIT
"""Automatic native capture preparation, isolated from parent activation.

Reuse the reviewed production main/real-engine context without changing it.
Account, evidence, inclusive counter and loopback inference are synthetic;
native saved publication, scanning, extraction, lineage and settlement are real.
No background producer is started: public scan/process_pending drive this slice.
"""
import asyncio

from renulus.contracts import ContextScope, Scope
from renulus.learn.conversation_models import NewConversation, Send
from renulus.memory.models import ManualFact
from test_harness_learning_models import collect_events, command
from test_harness_learning_native_extraction import (
    ANSWER, CORRECTION, POINT, PROMPT, ROOT_NOTE, native_memory, offline, pytestmark, saved_answer,
)


async def test_committed_native_answer_scan_queues_and_extracts_exactly_once(tmp_path, offline):
    async with native_memory(tmp_path) as (services, owner, memory, authority, registry,
            transports, admissions, counter, observer):
        _, reference = await saved_answer(services, owner, memory, authority)
        evidence_id = "learn-answer:" + reference["run_id"]
        assert len(observer.calls) == len(transports) == len(counter.calls) == 1
        assert observer.calls[0]["extracting"] is False
        assert memory.repository.jobs() == []

        # The saved stream has committed and settled. This is an ordinary
        # consumer scan, outside the native publisher and its transaction.
        memory.repository.scan()
        jobs = memory.repository.jobs()
        assert len(jobs) == 1, jobs
        job = jobs[0]
        assert job["evidence_id"] == evidence_id
        assert job["state"] == "queued" and job["attempts"] == 0
        memory.repository.scan()
        assert memory.repository.jobs() == jobs
        assert len(observer.calls) == len(transports) == len(counter.calls) == 1

        capture = asyncio.create_task(memory.process_pending())
        entered = asyncio.create_task(counter.entered.wait())
        try:
            done, _ = await asyncio.wait((entered, capture), timeout=60,
                return_when=asyncio.FIRST_COMPLETED)
            assert entered in done and entered.result(), {
                "job": memory.repository.job(job["id"]), "registry": registry.status(),
                "counter_calls": len(counter.calls), "capture_done": capture.done()}
            admitted = next(item for item in admissions if item.purpose == "memory-extraction")
            binding = admitted.binding
            assert admitted.required_capabilities == ("text",)
            assert authority.run(binding.operation_id)["spent_dispatches"] == 0
            assert registry.status(binding).owned == 1
            assert owner.process.domain_status(operation_id=binding.operation_id)["active"] == 1
            assert await command(owner.process, "model.extract.status",
                operation=binding.operation_id) == {"state": "active"}
            memory.repository.scan()
            assert len(memory.repository.jobs()) == 1
            assert memory.repository.job(job["id"])["state"] == "running"
            assert len(observer.calls) == len(transports) == 1  # Saved setup only.
        finally:
            entered.cancel()
            await asyncio.gather(entered, return_exceptions=True)
            counter.release.set()
        assert (await asyncio.wait_for(capture, 90))["processed"] == 1
        completed = memory.repository.job(job["id"])
        assert completed["state"] == "completed" and completed["attempts"] == 1
        points = [record for record in memory.repository.list() if record["source_id"] == evidence_id]
        assert len(points) == 1 and points[0]["text"] == POINT
        assert points[0]["sources"] == [{"source_key": "evidence:" + evidence_id}]
        assert authority.run(binding.operation_id)["state"] == "settled"
        assert authority.run(binding.operation_id)["spent_dispatches"] == 1
        assert registry.status(binding).owned == registry.status(binding).runs == 0
        assert owner.process.domain_status(operation_id=binding.operation_id)["active"] == 0
        assert owner.memory_captures.retained() == 0
        assert counter.finalized.is_set()
        assert [call["extracting"] for call in observer.calls] == [False, True]
        assert len(observer.calls) == len(transports) == len(counter.calls) == 2
        assert all(transport.finalized.is_set() for transport in transports)

        memory.repository.scan()
        assert memory.repository.jobs() == [completed]
        assert (await memory.process_pending())["processed"] == 0
        assert len(observer.calls) == len(transports) == len(counter.calls) == 2
        assert memory.repository.jobs() == [completed]
        assert await command(owner.process, "session.find",
            operation=binding.operation_id) == {"sessions": []}

        # Correcting an extracted point suppresses its real evidence source.
        # Completed receipts remain available, but scan/retry cannot recapture.
        corrected = await asyncio.to_thread(memory.edit, points[0]["id"], CORRECTION, 1)
        assert corrected["revision"] == 2 and not corrected["purge_pending"]
        memory.repository.scan()
        assert memory.repository.jobs() == [completed]
        assert (await memory.process_pending(retry=True))["processed"] == 0
        memory.repository.scan()
        assert memory.repository.jobs() == [completed]
        assert len(observer.calls) == len(transports) == len(counter.calls) == 2
        assert memory.repository.get(points[0]["id"])["text"] == CORRECTION
        assert POINT not in {record["text"] for record in memory.repository.list()}
        scope = ContextScope(kind=Scope.STUDY, entity_id=reference["thread_id"])
        recalled = await asyncio.to_thread(memory.retrieve, "CKD study", scope=scope)
        assert next(record for record in recalled["records"]
            if record["id"] == points[0]["id"])["revision"] == 2
        assert registry.status(binding).owned == 0 and owner.memory_captures.retained() == 0


async def test_incomplete_publication_and_corrected_support_scan_without_capture(tmp_path, offline):
    async with native_memory(tmp_path) as (services, owner, memory, authority, registry,
            transports, admissions, counter, observer):
        note = await asyncio.to_thread(memory.add, ManualFact(text=ROOT_NOTE,
            scope=ContextScope(kind=Scope.STUDY), idempotency_key="automatic-h05-root"))
        conversations = services.get("conversations")
        chat = conversations.create(NewConversation())
        entry, receipt = conversations.streaming.begin("learning", chat["identity"]["id"],
            Send(expected_revision=chat["revision"], text=PROMPT,
                request_id="automatic-h05-incomplete"))
        assert receipt["state"] == "running"
        # A genuine saved request exists; no completed answer has committed.
        # Scanning it must neither enqueue nor start native extraction.
        memory.repository.scan()
        assert memory.repository.jobs() == []
        assert not observer.calls and not transports and not counter.calls

        events = await collect_events(conversations, entry, receipt)
        assert events[-1]["type"] == "completed", events
        await owner.settle_run(entry)
        reference = events[-1]["payload"]["answer_reference"]
        evidence_id = "learn-answer:" + reference["run_id"]
        scope = ContextScope(kind=Scope.STUDY, entity_id=reference["thread_id"])
        assert reference["dependencies"] == [{"target": {"type": "memory_revision",
            "id": f"{note['id']}:1"}, "expected_revision": "1"}]
        assert authority.run(reference["run_id"])["state"] == "settled"
        material = memory.repository.material(evidence_id, scope, resolve_answer=False)
        assert material["infer"] is True and material["_answer"][1]["answer_reference"] == reference
        assert len(observer.calls) == len(transports) == len(counter.calls) == 1
        assert observer.calls[0]["extracting"] is False

        # The published reference was eligible, then its genuine r1 support
        # was corrected before the first consumer scan. No job may be created.
        corrected = await asyncio.to_thread(memory.edit, note["id"], CORRECTION, 1)
        assert corrected["revision"] == 2 and not corrected["purge_pending"]
        memory.repository.scan()
        assert memory.repository.jobs() == []
        assert (await memory.process_pending(retry=True))["processed"] == 0
        memory.repository.scan()
        assert memory.repository.jobs() == []
        assert len(observer.calls) == len(transports) == len(counter.calls) == 1
        assert not any(item.purpose == "memory-extraction" for item in admissions)
        assert not any(call["command"] == "model.extract" for call in owner.process.calls)
        assert owner.memory_captures.retained() == 0 and registry.status().owned == 0
        assert owner.process.domain_status()["active"] == 0
        assert POINT not in {record["text"] for record in memory.repository.list()}
        assert memory.repository.get(note["id"])["revision"] == 2
        history = await owner.bridge.messages(reference["thread_id"])
        assert "".join(item["content"] for item in history["items"]
            if item["id"] in reference["message_ids"]) == ANSWER
