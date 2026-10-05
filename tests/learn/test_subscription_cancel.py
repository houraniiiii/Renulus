"""Real Hermes/SDK cancellation with synthetic streams and isolated SQLite."""
import asyncio
from importlib import import_module
import ipaddress
import json
import socket
import time
from contextlib import aclosing
from pathlib import Path

import httpx
import pytest

from renulus.contracts import ContextScope, Scope
from renulus.server import create_app

MODEL = "gpt-6-astra"
PROMPT = "SYNTHETIC_CANCEL_PROMPT_NEVER_CAPTURE Dialysis learning exercise"
PARTIAL = "SYNTHETIC_CANCEL_PARTIAL_NEVER_SAVE"


@pytest.fixture(autouse=True)
def no_external_sockets(monkeypatch):
    for name in ("connect", "connect_ex"):
        original = getattr(socket.socket, name)

        def local_only(sock, address, _original=original):
            assert isinstance(address, tuple) and ipaddress.ip_address(address[0]).is_loopback
            return _original(sock, address)

        monkeypatch.setattr(socket.socket, name, local_only)


class PendingBody(httpx.AsyncByteStream):
    def __init__(self):
        self.waiting = asyncio.Event()
        self.closed = asyncio.Event()

    async def __aiter__(self):
        event = {"type": "response.output_text.delta", "delta": PARTIAL, "item_id": "synthetic",
                 "output_index": 0, "content_index": 0, "sequence_number": 1}
        yield ("data: " + json.dumps(event) + "\n\n").encode()
        self.waiting.set()
        await asyncio.Event().wait()

    async def aclose(self):
        self.closed.set()


def setup_app(tmp_path):
    # Prepare the public SDK resource before measuring readiness of its mock stream.
    import_module("openai.resources.responses")
    body, requests = PendingBody(), []

    def serve(request):
        assert request.url == "https://api.openai.com/v1/responses"
        assert json.loads(request.content)["model"] == MODEL
        requests.append(request)
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=body)

    app = create_app(tmp_path, token="synthetic-local-token",
        source_root=Path(__file__).resolve().parents[2])
    services = app.state.services
    memory = services.registry["memory"]
    services.registry["knowledge"] = services.registry["memory"] = None
    services.registry["retrieval"] = None
    provider = services.registry["provider"]
    provider._http_transport = httpx.MockTransport(serve)
    provider._settings["connections"]["codex"] = {"client_id": "synthetic-client",
        "access_token": "synthetic-plan-token", "expires_at": time.time() + 600}
    provider._settings["selected_provider"] = "codex"
    provider._catalogs["codex"] = {MODEL}
    provider._save()
    # Warm synchronous Hermes imports before arming a short cancellation deadline.
    provider.context.plan([{"role": "user", "content": "Synthetic teaching"}],
        provider="codex", model=MODEL)
    return app, provider, memory, body, requests


def assert_retained_input_only(services, learn, run, memory, *, state):
    if run.thread_id:
        thread = learn.get_thread(run.thread_id)
        assert thread["runs"][0]["state"] == state
        assert [(row["role"], row["content"]) for row in thread["messages"]] == [("user", PROMPT)]
    else:
        assert services.db.fetch_all("SELECT * FROM learn_threads") == []
    memory.repository.scan()
    assert services.db.fetch_all("SELECT * FROM learning_evidence") == []
    assert memory.repository.jobs() == []
    assert memory._engine is None and memory._embedding is None
    assert learn.active == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", [Scope.STUDY, Scope.TEMPORARY_CASE])
@pytest.mark.parametrize("stop", ["explicit", "consumer-task", "both"])
async def test_pending_sdk_cancel_distinguishes_local_stop_from_consumer_task(tmp_path, monkeypatch, scope, stop):
    app, provider, memory, body, requests = setup_app(tmp_path)
    services, learn = app.state.services, app.state.services.registry["learn"]
    _, run = learn.prepare(PROMPT, ContextScope(kind=scope), None, "dialysis", "direct", "cancel-test")
    flow = []

    async def collect():
        async with aclosing(learn.answer(run, PROMPT, "direct", "dialysis")) as stream:
            async for event in stream:
                flow.append(event)

    task = asyncio.create_task(collect())
    control = None
    release = asyncio.Event()
    try:
        await asyncio.wait_for(body.waiting.wait(), 15)
        if stop == "explicit":
            result = await learn.cancel(run.id)
            assert result["state"] == "cancelled"
            await asyncio.wait_for(task, 5)
            assert flow[-1].type == "cancelled"
            assert sum(event.type in {"completed", "error", "cancelled"} for event in flow) == 1
        else:
            if stop == "both":
                # Complete the local state transition while delaying its public adapter cancel.
                entered = asyncio.Event()
                original = provider.cancel

                async def delayed_cancel(identifier):
                    entered.set()
                    await release.wait()
                    return await original(identifier)

                monkeypatch.setattr(provider, "cancel", delayed_cancel)
                control = asyncio.create_task(learn.cancel(run.id))
                await asyncio.wait_for(entered.wait(), 5)
            task.cancel()
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, 5)
            if control:
                assert (await asyncio.wait_for(control, 5))["state"] == "cancelled"
            assert all(event.type not in {"completed", "error", "cancelled"} for event in flow)
        assert [event.sequence for event in flow] == list(range(1, len(flow) + 1))
        assert body.closed.is_set() and len(requests) == 1
        assert provider.status()["active_runs"] == []
        assert not provider.status()["live_provider_verified"]
        assert_retained_input_only(services, learn, run, memory,
            state="interrupted" if stop == "consumer-task" else "cancelled")
        if scope == Scope.TEMPORARY_CASE:
            for path in tmp_path.rglob("*"):
                if path.is_file():
                    assert PROMPT.encode() not in path.read_bytes()
                    assert PARTIAL.encode() not in path.read_bytes()
    finally:
        release.set()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        if control:
            await asyncio.gather(control, return_exceptions=True)
        await provider.close()
        await memory.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("close_at", ["started", "delta"])
async def test_closing_learn_iterator_releases_run_and_never_commits_partial(tmp_path, close_at):
    app, provider, memory, body, requests = setup_app(tmp_path)
    services, learn = app.state.services, app.state.services.registry["learn"]
    _, run = learn.prepare(PROMPT, ContextScope(kind=Scope.STUDY), None, "dialysis", "direct", "close-test")
    stream = learn.answer(run, PROMPT, "direct", "dialysis")
    try:
        while (await anext(stream)).type != close_at:
            pass
    finally:
        await stream.aclose()
    assert len(requests) == (1 if close_at == "delta" else 0)
    assert body.closed.is_set() is (close_at == "delta")
    assert provider.status()["active_runs"] == []
    assert_retained_input_only(services, learn, run, memory, state="interrupted")
    await provider.close()
    await memory.close()


@pytest.mark.asyncio
async def test_public_learn_stop_finishes_asgi_with_one_terminal_and_no_partial_capture(tmp_path):
    app, provider, memory, body, requests = setup_app(tmp_path)
    services, learn = app.state.services, app.state.services.registry["learn"]
    task = None
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                base_url="http://127.0.0.1", headers={"x-renulus-token": "synthetic-local-token"}) as local:
            task = asyncio.create_task(local.post("/api/v1/learn/ask", json={
                "question": PROMPT, "scope": {"kind": "study"}, "topic_id": "dialysis"}))
            await asyncio.wait_for(body.waiting.wait(), 15)
            run_id = services.db.fetch_one("SELECT id FROM learn_runs WHERE state='running'")["id"]
            run = learn.active[run_id]
            stopped = await local.post("/api/v1/learn/runs/" + run_id + "/cancel")
            assert stopped.json()["state"] == "cancelled"
            response = await asyncio.wait_for(task, 5)
            assert response.status_code == 200
            flow = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
            assert flow[-1]["type"] == "cancelled"
            assert [event["sequence"] for event in flow] == list(range(1, len(flow) + 1))
            assert sum(event["type"] in {"completed", "error", "cancelled"} for event in flow) == 1
        assert len(requests) == 1 and body.closed.is_set()
        assert provider.status()["active_runs"] == []
        assert_retained_input_only(services, learn, run, memory, state="cancelled")
    finally:
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await provider.close()
        await memory.close()


@pytest.mark.asyncio
async def test_local_cancel_wins_over_late_provider_failure(tmp_path):
    app, provider, memory, body, requests = setup_app(tmp_path)
    services, learn = app.state.services, app.state.services.registry["learn"]

    class LateFailure:
        async def stream(self, messages, **kwargs):
            yield PARTIAL
            await learn.cancel(kwargs["run_id"])
            raise RuntimeError("SYNTHETIC_PROVIDER_FAILURE_MUST_NOT_SURFACE_AFTER_STOP")

        async def cancel(self, identifier):
            return True

    services.registry["provider"] = LateFailure()
    _, run = learn.prepare(PROMPT, ContextScope(kind=Scope.STUDY), None, "dialysis", "direct", "late-failure")
    flow = [event async for event in learn.answer(run, PROMPT, "direct", "dialysis")]
    assert flow[-1].type == "cancelled"
    assert sum(event.type in {"completed", "error", "cancelled"} for event in flow) == 1
    assert "SYNTHETIC_PROVIDER_FAILURE" not in json.dumps([event.model_dump() for event in flow])
    assert_retained_input_only(services, learn, run, memory, state="cancelled")
    await provider.close()
    await memory.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", [Scope.STUDY, Scope.TEMPORARY_CASE])
@pytest.mark.parametrize("close_at", ["started", "delta"])
async def test_closing_public_response_body_closes_inner_learn_run(tmp_path, scope, close_at):
    from renulus.learn.api import Ask, create_router

    app, provider, memory, body, requests = setup_app(tmp_path)
    services = app.state.services
    router = create_router(services)
    endpoint = next(route.endpoint for route in router.routes if route.path == "/learn/ask")
    learn = services.registry["learn"]
    stream = None
    try:
        response = await endpoint(Ask(question=PROMPT, scope=ContextScope(kind=scope)),
                                  idempotency_key="response-close")
        stream = response.body_iterator
        while True:
            chunk = await anext(stream)
            event = json.loads(next(line[6:] for line in chunk.splitlines()
                                    if line.startswith("data: ")))
            if event["type"] == close_at:
                break
        run = learn.active[event["run_id"]]
        await stream.aclose()
        # Closing the public response must await inner cleanup, without relying
        # on async-generator garbage collection or an event-loop turn.
        assert provider.status()["active_runs"] == []
        assert body.closed.is_set() is (close_at == "delta")
        assert len(requests) == (1 if close_at == "delta" else 0)
        assert_retained_input_only(services, learn, run, memory, state="interrupted")
        if scope == Scope.TEMPORARY_CASE:
            for path in tmp_path.rglob("*"):
                if path.is_file():
                    assert PROMPT.encode() not in path.read_bytes()
                    assert PARTIAL.encode() not in path.read_bytes()
    finally:
        if stream:
            await stream.aclose()
        await provider.close()
        await memory.close()
