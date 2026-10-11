# SPDX-License-Identifier: MIT
"""Scripted IPC observations verify saved terminal behavior, not native settlement."""
import asyncio

import pytest
from fastapi.testclient import TestClient

from renulus.server import create_app
from test_harness_bridge import ScriptedTransport, collect, native_at
from test_harness_reconciliation import install


class ExecutionObservation(ScriptedTransport):
    """The public host transport can retain an older outcome while still active."""

    def __init__(self, *, execution="active", outcome="succeeded", lose_prompt_ack=False):
        super().__init__()
        self.execution = execution
        self.outcome = outcome
        self.observed = asyncio.Event()
        self.release = asyncio.Event()
        self.observations = 0
        self.operation_id = None
        self.lose_prompt_ack = lose_prompt_ack

    async def request(self, command, payload, operation_id, *args):
        if command == "session.get" and self.observations and self.execution != "settled":
            await self.release.wait()
        response = await super().request(command, payload, operation_id, *args)
        if command == "session.prompt":
            self.operation_id = operation_id
        if command == "session.get":
            if self.release.is_set():
                self.execution = "settled"
            response["result"]["execution"] = self.execution
            response["result"]["session"]["outcome"] = self.outcome
            # This retained prior idle is later than the current user timestamp.
            response["result"]["session"]["time"]["idle"] = 1791676800010
            self.observations += 1
            self.observed.set()
        if command == "session.messages":
            response["result"]["messages"][0]["metadata"] = {
                "operationId": self.operation_id,
                "attemptId": "1",
                "configurationId": "synthetic-policy-v1",
            }
        if command == "session.prompt" and self.lose_prompt_ack:
            self.lose_prompt_ack = False
            return {
                **{key: value for key, value in response.items() if key != "result"},
                "outcome": "uncertain_after_disconnect",
                "error": {"code": "process_disconnected"},
            }
        return response


async def test_stale_later_idle_cannot_complete_an_active_saved_execution(tmp_path):
    transport = ExecutionObservation()
    services, repo, bridge, _, identifier, request = native_at(tmp_path, transport)
    entry, receipt = repo.streaming.begin("learning", identifier, request)
    pending = asyncio.create_task(collect(repo.streaming, entry, receipt))
    try:
        await asyncio.wait_for(transport.observed.wait(), 2)
        done, _ = await asyncio.wait({pending}, timeout=.05)
        assert not done, pending.result() if done else "Execution remains active."
        assert bridge.completed(receipt["run_id"]) is None
        transport.release.set()
        events = await asyncio.wait_for(pending, 2)
        assert events[-1]["type"] == "completed", events
        assert (await bridge.resolve_completed(receipt["run_id"])).text == transport.answer_text
        assert transport.prompts == [request.text]
    finally:
        transport.release.set()
        await asyncio.wait_for(pending, 2)
        await services.shutdown()


@pytest.mark.parametrize("outcome,code", [
    ("failed", "harness_execution_failed"),
    ("interrupted", "harness_execution_interrupted"),
])
def test_reopened_lost_ack_records_settled_native_failure_without_resubmission(tmp_path, outcome, code):
    profile = tmp_path / "synthetic-terminal-reopen"
    transport = ExecutionObservation(execution="settled", outcome=outcome, lose_prompt_ack=True)
    app = create_app(profile)
    install(app, transport)
    with TestClient(app) as client:
        chat = client.post("/api/v1/conversations", json={}).json()
        route = "/api/v1/conversations/learning/" + chat["identity"]["id"]
        request = {
            "expected_revision": chat["revision"],
            "text": "Explain synthetic CKD after an uncertain receipt.",
            "request_id": "synthetic-terminal-lost-ack",
        }
        from test_harness_bridge import payloads
        events = payloads(client.post(route + "/messages", json=request))
        assert events[-1]["type"] == "error", events
        assert events[-1]["payload"]["code"] == "harness_command_uncertain", events
        run_id = events[-1]["run_id"]

    reopened = create_app(profile)
    _, bridge = install(reopened, transport)
    with TestClient(reopened) as client:
        histories = []
        for _ in range(2):
            history = client.get(route + "/messages")
            assert history.status_code == 200, history.text
            histories.append(history.json())
            status = client.get(route + "/runs/" + run_id)
            assert status.status_code == 200, status.text
            assert status.json()["state"] == "error", status.json()
            assert status.json()["error"]["code"] == code, status.json()
            assert status.json()["error"]["retryable"] is True, status.json()
            replay = payloads(client.post(route + "/messages", json=request))
            assert len(replay) == 1 and replay[0]["type"] == "error", replay
            assert replay[0]["run_id"] == run_id, replay
            assert replay[0]["payload"]["code"] == code, replay
            assert replay[0]["payload"]["replayed"] is True, replay
            assert bridge.completed(run_id) is None
            assert client.get(route + "/draft").json()["text"] == request["text"]
        assert histories[0] == histories[1]
        assert [(item["role"], item["content"]) for item in histories[0]["items"]] == [
            ("user", request["text"]),
        ]
    assert transport.calls.count("session.create") == 1
    assert transport.prompts == [request["text"]]
    assert "session.cancel" not in transport.calls
