# SPDX-License-Identifier: MIT
"""Lost purge acknowledgment over actual main/SDK; account/HTTP are synthetic.

Only the lower acknowledgment observation is lost, after the real removal has
committed. The production learning_models helper and native effects are unchanged.
One saved setup dispatch is required; reconciliation/reopen have zero dispatches.
"""

import pytest

from renulus.contracts import ApiError
from renulus.learn.conversation_models import Mutation, NewConversation, Send
from renulus.runtime.harness_process import ManagedHarnessProcess
from test_harness_learning_models import PROMPT, collect_events, learning_models
from test_harness_model_dispatch_sdk import offline


class LostRemovalAcknowledgment(ManagedHarnessProcess):
    """Delegate actual requests; suppress one exact post-commit observation only."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.creates = []
        self.removals = []
        self.queries = []
        self.releases = []
        self.lost_request_id = None

    async def request(self, command, payload, operation_id, attempt_id, timeout):
        response = await super().request(command, payload, operation_id, attempt_id, timeout)
        if command == "session.create" and response["outcome"] == "committed_reference":
            self.creates.append((operation_id, attempt_id, dict(payload),
                response["result"]["session"]["id"]))
        if command == "session.remove":
            self.removals.append((operation_id, attempt_id, dict(payload), response["request_id"]))
            if self.lost_request_id is None:
                assert response["outcome"] == "committed_reference", response
                assert response["result"] == {"state": "removed", "sessionId": payload["sessionId"]}
                self.lost_request_id = response["request_id"]
                pending = {key: value for key, value in response.items() if key != "result"}
                pending.update(outcome="accepted_pending", admission="host_accepted", observation="timeout")
                return pending
        return response

    async def query_result(self, request_id):
        response = await super().query_result(request_id)
        self.queries.append(request_id)
        if request_id == self.lost_request_id:
            return None
        return response

    async def release_observation(self, request_id):
        result = await super().release_observation(request_id)
        self.releases.append((request_id, result))
        return result


async def read(process, name, payload=None, *, operation):
    response = await process.request(name, payload or {}, operation, "1", 5)
    assert response["outcome"] == "committed_reference", response
    assert await process.query_result(response["request_id"]) == response
    assert await process.release_observation(response["request_id"])
    return response["result"]


async def replace_settled_process(owner, process):
    seal = owner.seal_new_runs(expected_effective=owner.configuration_id)
    try:
        assert (await owner.process.close(10))["state"] == "closed"
        assert (await owner.process.settlement(10))["state"] == "settled"
        assert owner.process.domain_status()["active"] == 0
        owner.replace_process(process, configuration_id=owner.configuration_id, seal=seal)
        await owner.start()
    finally:
        seal.release()


async def test_lost_remove_ack_reconciles_absence_without_resend_and_stays_retired_on_reopen(tmp_path, offline):
    async with learning_models(tmp_path) as (services, owner, authority, registries, transports,
            admissions, counter, observer):
        process = LostRemovalAcknowledgment(domain_authority=owner.authorize)
        await replace_settled_process(owner, process)
        repo = services.get("conversations")
        original = NewConversation(title="Synthetic lost-ack saved owner")
        create_key = "purge-reconcile-original-create"
        chat = repo.create(original, create_key)
        other = repo.create(NewConversation(), "purge-reconcile-unaffected-owner")
        thread_id = chat["identity"]["id"]
        entry, receipt = repo.streaming.begin("learning", thread_id, Send(
            expected_revision=chat["revision"], text=PROMPT, request_id="purge-reconcile-saved-setup"))
        counter.release.set()
        observer.release.set()
        events = await collect_events(repo, entry, receipt)
        assert events[-1]["type"] == "completed", events
        run_id = entry["run"].id
        assert authority.run(run_id)["state"] == "settled"
        assert registries[-1].status().owned == 0
        assert owner.process.domain_status(operation_id=run_id)["active"] == 0
        assert len(counter.calls) == len(observer.calls) == len(transports) == 1
        assert authority.run(run_id)["spent_dispatches"] == 1
        assert len(process.creates) == 1
        operation, attempt, create_payload, session_id = process.creates[0]
        assert operation == run_id and attempt == "1"
        before = await read(process, "session.find", operation=run_id)
        assert [session["id"] for session in before["sessions"]] == [session_id]
        native = await read(process, "session.get", {"session_id": session_id}, operation=run_id)
        assert native["execution"] == "settled"
        transcript = await read(process, "session.messages", {"session_id": session_id}, operation=run_id)
        reference = events[-1]["payload"]["answer_reference"]
        assert {reference["input_id"], *reference["message_ids"]} <= {
            message["id"] for message in transcript["messages"]}
        revision = repo.get("learning", thread_id)["revision"]

        with pytest.raises(ApiError) as pending:
            await repo.delete("learning", thread_id, Mutation(expected_revision=revision),
                "purge-reconcile-delete")
        assert (pending.value.code, pending.value.status, pending.value.retryable) == (
            "harness_purge_pending", 503, True)
        purges = repo.migration_journal.pending_purges()
        assert len(purges) == 1
        purge = purges[0]
        manifest = owner.manifest()
        assert (purge.profile_id, purge.store_id, purge.session_id, purge.operation_id, purge.attempt_id,
            purge.state) == (manifest["profile_id"], manifest["runtime_store"]["store_id"],
                session_id, run_id, "1", "pending")
        assert process.removals == [(purge.purge_id, "1", {"sessionId": session_id}, process.lost_request_id)]
        assert process.lost_request_id in process.queries
        with pytest.raises(ApiError) as missing:
            repo.get("learning", thread_id)
        assert missing.value.code == "conversation_missing"
        with pytest.raises(ApiError) as retired:
            repo.create(original, create_key)
        assert (retired.value.code, retired.value.status) == ("command_terminal_unavailable", 410)
        with pytest.raises(ApiError) as sealed:
            repo.streaming.begin("learning", other["identity"]["id"], Send(
                expected_revision=other["revision"], text=PROMPT, request_id="purge-reconcile-blocked-send"))
        assert sealed.value.code == "harness_configuration_busy"
        assert (await read(process, "host.status", operation="purge-reconcile-live-control"))["state"] == "ready"
        assert (await read(process, "session.find", operation=run_id))["sessions"] == []
        assert len(counter.calls) == len(observer.calls) == 1

        await owner.purge_native_owners()
        assert len(process.removals) == 1, "Exact native absence must reconcile without resending session.remove."
        assert repo.migration_journal.pending_purges() == ()
        removed = repo.migration_journal.removed_purges()
        assert len(removed) == 1
        assert (removed[0].purge_id, removed[0].session_id, removed[0].operation_id, removed[0].state) == (
            purge.purge_id, session_id, run_id, "removed")
        with services.db.transaction() as conn:
            owner.check_new_run_in(conn)  # Reconciliation releases the retained deletion gate.
        same_generation = await process.request("session.create", create_payload, operation, attempt, 5)
        assert same_generation["outcome"] == "rejected_before_admission", same_generation
        assert same_generation["error"]["code"] == "operation_terminal_unavailable"
        assert (await read(process, "session.find", operation=run_id))["sessions"] == []

        generation = process.native_identity().generation
        await replace_settled_process(owner, ManagedHarnessProcess(domain_authority=owner.authorize))
        assert owner.process.native_identity().generation != generation
        reopened = await owner.process.request("session.create", create_payload, operation, attempt, 5)
        assert reopened["outcome"] == "rejected_before_admission", reopened
        assert reopened["error"]["code"] == "operation_terminal_unavailable"
        assert (await read(owner.process, "session.find", operation=run_id))["sessions"] == []
        with pytest.raises(ApiError) as replay:
            repo.create(original, create_key)
        assert (replay.value.code, replay.value.status) == ("command_terminal_unavailable", 410)
        with pytest.raises(ApiError) as deleted:
            repo.get("learning", thread_id)
        assert deleted.value.code == "conversation_missing"
        assert len(counter.calls) == len(observer.calls) == len(transports) == 1
        assert authority.run(run_id)["spent_dispatches"] == 1
        assert authority.run(run_id)["state"] == "settled"
        assert owner.process.domain_status()["active"] == 0
        assert registries[-1].status().owned == 0
        assert all(transport.finalized.is_set() for transport in transports)
        assert repo.migration_journal.pending_purges() == ()
