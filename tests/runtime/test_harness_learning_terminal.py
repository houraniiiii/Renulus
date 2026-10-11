"""Saved completion waits for the actual execution, including tool continuations."""
import asyncio
import json
import os
from pathlib import Path
import subprocess

from renulus.contracts import ContextScope, Scope
from renulus.learn.conversation_models import NewConversation, Send
from renulus.runtime.harness_process import HarnessProcessConfig
from renulus.server import create_app


async def test_completed_tool_step_cannot_publish_before_current_execution_settles(tmp_path):
    from renulus.runtime.harness_learning import HarnessLearningOwner

    root = tmp_path / "profile"
    root.mkdir()
    assets = Path(os.environ["RENULUS_LIBRARY_HELPERS"]).resolve()
    subprocess.run(["powershell.exe", "-NoProfile", "-Command",
        f"New-Item -ItemType Junction -Path '{root / 'helpers'}' -Target '{assets}' | Out-Null"], check=True)
    services = create_app(root).state.services
    config = HarnessProcessConfig(node_executable=Path(os.environ["RENULUS_HARNESS_NODE"]),
        host_entry=Path(__file__).resolve().parents[2] / "packages/harness/test/fixtures/learning-terminal-host.mjs",
        profile_root=root, profile_id="synthetic-profile", store_id="synthetic-runtime",
        domain_store_id="synthetic-domain", domain_path="state/renulus.sqlite3",
        max_inflight=1, max_domain_inflight=1)
    owner = HarnessLearningOwner(services, config, configuration_id="synthetic-terminal", context_filtering=True)
    owner.install()
    pending = None

    async def request(command, payload, operation):
        response = await owner.process.request(command, payload, operation, "1", 5)
        assert response["outcome"] in {"committed_reference", "cancelled_settled"}, response
        return response["result"]

    try:
        await owner.start()
        source = await asyncio.to_thread(services.get("knowledge").import_text,
            "Synthetic CKD education considers albuminuria and filtration together.",
            scope=ContextScope(kind=Scope.LIBRARY))
        assert source["status"] == "ready", source
        repo = services.get("conversations")
        chat = repo.create(NewConversation())
        events = []

        async def answer(summary, key):
            entry, receipt = repo.streaming.begin("learning", summary["identity"]["id"],
                Send(expected_revision=summary["revision"], text="Explain synthetic CKD.", request_id=key))
            async for encoded in repo.streaming.events(entry, receipt):
                events.append(json.loads(encoded.split("data: ", 1)[1]))
            return events[-1]

        async with asyncio.timeout(60):
            first = await answer(chat, "terminal-first")
            assert first["type"] == "completed", events
            pending = asyncio.create_task(answer(first["payload"]["conversation"], "terminal-second"))
            while True:
                status = await request("host.status", {}, "terminal-proof")
                if status["modelCalls"] == 3:
                    break
                await asyncio.sleep(.02)
            assert status["activeSessionIds"], status
            assert status["observation"].get("execution") == "active", status["observation"]
            session = status["observation"]["session"]
            assert session["outcome"] == "succeeded"  # Retained from the first execution.
            messages = status["observation"]["messages"]
            current_user = [item for item in messages if item["type"] == "user"][-1]
            assert session["time"]["idle"] < current_user["time"]["created"]
            assert any(item["type"] == "assistant" and item["time"].get("completed") and
                any(part["type"] == "tool" and part["state"]["status"] == "completed"
                    for part in item.get("content", [])) for item in messages)
            # The continuation gate is confirmed closed, so this observation
            # interval cannot finish the current native execution.
            done, _ = await asyncio.wait({pending}, timeout=.5)
            assert not done, (await pending if done else events)
            assert not any(item["type"] in {"delta", "completed", "error"} for item in events
                if item["run_id"] != first["run_id"]), events
            await request("session.cancel", {"session_id": "synthetic-release-continuation"},
                "release-fixture-continuation")
            final = await pending
            assert final["type"] == "completed", json.dumps(events, indent=2)
            settled = await request("session.get", {"session_id": session["id"]}, "terminal-proof")
            assert settled["execution"] == "settled", settled
            resolved = await owner.bridge.resolve_completed(final["run_id"])
            assert resolved.text == "Partial synthetic explanation. Final synthetic explanation after Library."
            assert len(resolved.message_ids) == 2
            assert resolved.citations[0]["revision_id"] == source["revision_id"]
    finally:
        await request("session.cancel", {"session_id": "synthetic-release-continuation"},
            "cleanup-fixture-continuation")
        if pending is not None and not pending.done():
            await pending
        await owner.close()
        services.get("helpers").startup.close()
