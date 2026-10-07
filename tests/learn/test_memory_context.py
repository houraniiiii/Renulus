"""Controlled scheduling with real Learn/Memory repositories and runtime orchestration.

No server, account, HTTP, Hermes compressor, embedding or memory engine is used.
The context planner and transport are explicit deterministic doubles.
"""
import asyncio
import copy
from pathlib import Path
import socket
from types import SimpleNamespace

import pytest

from renulus.contracts import ContextScope, Scope
from renulus.learn.service import LearnService
from renulus.memory.models import ManualFact
from renulus.memory.repository import MemoryRepository
from renulus.runtime.context import SUMMARY_INSTRUCTIONS
from renulus.runtime.manager import ProviderManager
from renulus.services import Services
from renulus.storage import AppPaths, Database


ROOT = Path(__file__).resolve().parents[2]
MODEL = "gpt-6.1-sol"
TOPIC = "T20"
QUESTION = "Explain this synthetic dialysis learning point."
OLD = "SYNTHETIC_OLD_MEMORY: compare dialysis mechanisms."
CORRECTED = "SYNTHETIC_CORRECTED_MEMORY: compare monitoring uncertainty."
SCOPE = ContextScope(kind=Scope.STUDY)


class CanonicalRecall:
    """Select a canonical record without a semantic index or background worker."""
    def __init__(self, repository, identifier):
        self.repository, self.identifier = repository, identifier
        self.notifications = 0

    def retrieve(self, *args, **kwargs):
        rows = [row for row in self.repository.list() if row["id"] == self.identifier]
        return {"records": rows, "context": "Opaque derivative text must not enter the prompt."}

    def notify(self):
        self.notifications += 1


class ControlledContext:
    """Exercise manager event boundaries, not the actual Hermes algorithm."""
    def __init__(self, compact=False):
        self.compact = compact

    def plan(self, messages, **kwargs):
        return SimpleNamespace(wire_messages=copy.deepcopy(messages), before=25000,
            turns=[{"role": "user", "content": "Earlier synthetic study discussion."}]
                if self.compact else None)

    def summary_messages(self, plan):
        return [{"role": "system", "content": SUMMARY_INSTRUCTIONS}, *plan.turns]

    def finish(self, plan, summary=None):
        messages = copy.deepcopy(plan.wire_messages)
        if summary is not None:
            messages.insert(1, {"role": "assistant", "content": "Volatile summary: " + summary})
        return {"messages": messages, "estimated_tokens_before": 25000,
                "estimated_tokens_after": 100, "compacted": summary is not None}

    def estimate(self, messages):
        return 100


class ControlledTransport:
    def __init__(self, pause=None):
        self.pause = pause
        self.entered, self.release = asyncio.Event(), asyncio.Event()
        self.calls, self.closed = [], []

    async def stream(self, provider, model, token, messages):
        assert (provider, model, token) == ("codex", MODEL, "synthetic-token")
        purpose = "compaction" if messages[0]["content"] == SUMMARY_INSTRUCTIONS else "explain"
        self.calls.append((purpose, copy.deepcopy(messages)))
        try:
            if purpose == "explain" and self.pause == "response":
                yield {"type": "delta", "text": "Already streamed synthetic fragment. "}
            if self.pause == purpose or (purpose == "explain" and self.pause == "response"):
                self.entered.set()
                await self.release.wait()
            yield {"type": "delta", "text": "Synthetic reference." if purpose == "compaction"
                   else "Synthetic final explanation."}
            yield {"type": "completed", "response_model": MODEL}
        finally:
            self.closed.append(purpose)


class ControlledKnowledge:
    def __init__(self, *, pause=False, revoke=False):
        self.checks, self.pause, self.revoke = 0, pause, revoke
        self.entered, self.release = asyncio.Event(), asyncio.Event()

    async def retrieve(self, *args, **kwargs):
        return {"passages": [{"id": "synthetic-passage", "text": "Synthetic source.",
                              "metadata": {}}]}

    async def check_evidence(self, citations, **kwargs):
        self.checks += 1
        # Initial eligibility, pre-dispatch, then the final awaited citation check.
        if self.checks == 3 and self.pause:
            self.entered.set()
            await self.release.wait()
        return {"state": "available", "eligible_ids": [] if self.checks == 3 and self.revoke
                else [row["id"] for row in citations], "metadata": {}}


def build(paths, monkeypatch, *, identifier=None, pause=None, compact=False):
    services = Services(paths, Database(paths.database))
    for module in ("learn", "memory"):
        services.db.apply_migration(module + "-001",
            (ROOT / "runtime/renulus" / module / "schema.sql").read_text(encoding="utf-8"))
    repository = MemoryRepository(services)
    if identifier is None:
        identifier = repository.add(ManualFact(text=OLD, scope=SCOPE, topic_id=TOPIC,
                                               idempotency_key="selected-note"))["id"]
    memory = CanonicalRecall(repository, identifier)
    transport = ControlledTransport(pause)
    manager = ProviderManager(paths, transport=transport)
    manager._context = ControlledContext(compact)
    manager._settings["selected_provider"] = "codex"
    manager._settings["connections"]["codex"] = {"synthetic": True}
    manager._catalogs["codex"] = {MODEL}

    async def access_token(provider):
        assert provider == "codex"
        return "synthetic-token"

    monkeypatch.setattr(manager, "_access_token", access_token)
    services.registry.update(provider=manager, memory=memory)
    learn = LearnService(services)
    return SimpleNamespace(services=services, repository=repository, memory=memory,
                           manager=manager, transport=transport, learn=learn, identifier=identifier)


@pytest.fixture
def setup(tmp_path, monkeypatch):
    def deny_network(*args, **kwargs):
        pytest.fail("Network is outside this controlled test")

    monkeypatch.setattr(socket.socket, "connect", deny_network)
    monkeypatch.setattr(socket.socket, "connect_ex", deny_network)
    paths = AppPaths.create(tmp_path / "synthetic-profile", ROOT)
    return lambda **kwargs: build(paths, monkeypatch, **kwargs)


def prepare(env, key="request", scope=SCOPE):
    return env.learn.prepare(QUESTION, scope, None, TOPIC, "direct", key)[1]


async def collect(env, run, *, fresh=False, on_memory=None):
    flow = []
    async for event in env.learn.answer(run, QUESTION, "direct", TOPIC, MODEL, freshness=fresh):
        flow.append(event)
        if event.type == "memory" and on_memory:
            on_memory()
    return flow


def change(env, action, identifier=None):
    identifier = identifier or env.identifier
    revision = env.repository.get(identifier)["revision"]
    if action == "edit":
        env.repository.edit(identifier, CORRECTED, revision)
    elif action == "delete":
        env.repository.delete(identifier, revision)
    else:
        assert action == "tombstone"
        # Restore can expose a retained row alongside a newer deletion marker.
        env.services.db.mark_deleted("memory_fact", identifier)


def assert_failed_without_capture(env, run, flow, code="explain_memory_changed"):
    assert flow[-1].type == "error" and flow[-1].payload["code"] == code
    assert flow[-1].payload["retryable"] is True
    thread = env.learn.get_thread(run.thread_id)
    assert [(row["role"], row["content"]) for row in thread["messages"]] == [("user", QUESTION)]
    assert thread["runs"][0]["state"] == "failed"
    assert thread["runs"][0]["error_code"] == code
    assert env.services.db.fetch_all("SELECT * FROM learning_evidence") == []
    assert env.services.db.fetch_all("SELECT * FROM memory_jobs") == []
    assert env.memory.notifications == 0
    assert env.learn.active == {} and env.manager.status()["active_runs"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("phase,action", [
    pytest.param(phase, action, id=f"{phase}-{action}")
    for phase in ("pre-dispatch", "compaction", "response", "commit")
    for action in ("edit", "delete")
])
async def test_recalled_revision_change_refuses_stale_answer(setup, phase, action):
    env = setup(pause=phase, compact=phase == "compaction")
    run = prepare(env)
    gate = env.transport
    if phase == "commit":
        gate = ControlledKnowledge(pause=True)
        env.services.registry["knowledge"] = gate
    task = None
    try:
        if phase == "pre-dispatch":
            flow = await collect(env, run, on_memory=lambda: change(env, action))
        else:
            task = asyncio.create_task(collect(env, run, fresh=phase == "commit"))
            await asyncio.wait_for(gate.entered.wait(), 5)
            change(env, action)
            gate.release.set()
            flow = await asyncio.wait_for(task, 5)
        assert_failed_without_capture(env, run, flow)
        purposes = [purpose for purpose, _ in env.transport.calls]
        assert purposes == ([] if phase == "pre-dispatch" else
                            ["compaction"] if phase == "compaction" else ["explain"])
        assert sorted(env.transport.closed) == sorted(purposes)
        if phase == "compaction":
            assert OLD not in str(env.transport.calls[0][1])
        if phase == "response":
            assert [item.payload["text"] for item in flow if item.type == "delta"] == [
                "Already streamed synthetic fragment. "]
    finally:
        gate.release.set()
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await env.manager.close()


@pytest.mark.asyncio
async def test_deletion_marker_wins_over_retained_canonical_row(setup):
    env = setup()
    run = prepare(env)
    try:
        flow = await collect(env, run, on_memory=lambda: change(env, "tombstone"))
        assert env.services.db.fetch_one("SELECT id FROM memory_facts WHERE id=?", (env.identifier,))
        assert_failed_without_capture(env, run, flow)
        assert env.transport.calls == []
    finally:
        await env.manager.close()


@pytest.mark.asyncio
async def test_unrelated_edit_does_not_invalidate_selected_memory(setup):
    env = setup(compact=True)
    other = env.repository.add(ManualFact(text="Unrelated synthetic note.", scope=SCOPE,
        topic_id="T08", idempotency_key="other-note"))["id"]
    run = prepare(env)
    try:
        flow = await collect(env, run, on_memory=lambda: change(env, "edit", other))
        assert flow[-1].type == "completed" and env.memory.notifications == 1
        assert [purpose for purpose, _ in env.transport.calls] == ["compaction", "explain"]
        primary = env.transport.calls[-1][1][0]["content"]
        assert OLD in primary and CORRECTED not in primary
        assert "Opaque derivative text" not in primary
    finally:
        await env.manager.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["edit", "delete"])
async def test_explicit_new_request_after_reopen_uses_only_current_memory(setup, action):
    original = setup()
    first = prepare(original, "before-change")
    try:
        flow = await collect(original, first, on_memory=lambda: change(original, action))
        assert_failed_without_capture(original, first, flow)
        assert original.transport.calls == []
    finally:
        await original.manager.close()
    reopened = setup(identifier=original.identifier)
    try:
        assert reopened.learn.get_thread(first.thread_id)["runs"][0]["state"] == "failed"
        run = prepare(reopened, "explicit-new-request")
        flow = await collect(reopened, run)
        assert flow[-1].type == "completed" and reopened.memory.notifications == 1
        assert len(reopened.transport.calls) == 1
        primary = reopened.transport.calls[0][1][0]["content"]
        assert OLD not in primary
        assert (CORRECTED in primary) == (action == "edit")
        assert [row["revision"] for row in reopened.repository.list()] == ([2] if action == "edit" else [])
    finally:
        await reopened.manager.close()


@pytest.mark.asyncio
async def test_source_freshness_guard_still_refuses_commit(setup):
    env = setup()
    env.services.registry["knowledge"] = ControlledKnowledge(revoke=True)
    run = prepare(env)
    try:
        flow = await collect(env, run, fresh=True)
        assert_failed_without_capture(env, run, flow, "explain_sources_changed")
        assert len(env.transport.calls) == 1
    finally:
        await env.manager.close()
