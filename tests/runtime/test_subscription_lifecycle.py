"""Synthetic subscription lifecycle; actual Hermes/SDK, no accounts or models."""
import asyncio
import copy
import ipaddress
import json
import socket
import time
from contextlib import aclosing

import httpx
import pytest

from renulus.contracts import ContextScope, Scope
from renulus.runtime.manager import ProviderManager

MODEL = "gpt-6-astra"
SCOPE = ContextScope(kind=Scope.TEMPORARY_CASE)
SENTINEL = "SYNTHETIC_SUBSCRIPTION_CASE_578_NEVER_RETAIN"


@pytest.fixture(autouse=True)
def no_external_sockets(monkeypatch):
    for name in ("connect", "connect_ex"):
        original = getattr(socket.socket, name)

        def local_only(sock, address, _original=original):
            assert isinstance(address, tuple) and ipaddress.ip_address(address[0]).is_loopback
            return _original(sock, address)

        monkeypatch.setattr(socket.socket, name, local_only)


def seed_astra(manager):
    manager._settings["connections"]["codex"] = {
        "client_id": "synthetic-client", "access_token": "synthetic-plan-token",
        "expires_at": time.time() + 600,
    }
    manager._settings["selected_provider"] = "codex"
    manager._catalogs["codex"] = {MODEL}
    manager._save()


def response(text="Synthetic compacted educational reference"):
    events = [
        {"type": "response.output_text.delta", "delta": text, "item_id": "synthetic",
         "output_index": 0, "content_index": 0, "sequence_number": 1},
        {"type": "response.completed", "sequence_number": 2,
         "response": {"id": "synthetic", "object": "response", "created_at": 1,
                      "status": "completed", "model": MODEL, "output": []}},
    ]
    return httpx.Response(200, headers={"content-type": "text/event-stream"},
        content="".join("data: " + json.dumps(event) + "\n\n" for event in events))


def long_conversation():
    content = ("CKD albuminuria; dialysis potassium; transplant rejection; "
               "glomerular haematuria; electrolyte sodium. " * 28)
    return [{"role": "user", "content": "Learn nephrology across domains."}] + [
        {"role": "user" if index % 2 == 0 else "assistant",
         "content": SENTINEL + str(index) + content}
        for index in range(42)
    ] + [{"role": "user", "content": "Explain the transplantation mechanism."}]


@pytest.mark.asyncio
@pytest.mark.parametrize("stop_at", ["started", "compaction-progress"])
async def test_stop_at_public_event_does_not_dispatch_compaction(app_paths, stop_at):
    requests = []

    def serve(request):
        assert request.url == "https://api.openai.com/v1/responses"
        requests.append(request)
        assert json.loads(request.content)["model"] == MODEL
        return response()

    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(serve))
    seed_astra(manager)
    messages = long_conversation()
    original = copy.deepcopy(messages)
    assert manager.context.plan(messages, provider="codex", model=MODEL).turns is not None
    before = {path: path.read_bytes() for path in app_paths.root.rglob("*") if path.is_file()}
    events = []
    async with aclosing(manager.events(messages, scope=SCOPE, run_id="stop-before-summary")) as stream:
        events.append(await anext(stream))
        assert events[-1].type == "started"
        if stop_at == "compaction-progress":
            events.append(await anext(stream))
            assert events[-1].type == "progress"
            assert events[-1].payload["stage"] == "compaction"
        assert await manager.cancel("stop-before-summary")
        events.extend([event async for event in stream])
    assert requests == []
    assert events[-1].type == "cancelled"
    assert [event.sequence for event in events] == list(range(1, len(events) + 1))
    assert len([event for event in events if event.type in {"completed", "error", "cancelled"}]) == 1
    assert not manager.status()["active_runs"] and not manager.status()["live_provider_verified"]
    assert not await manager.cancel("stop-before-summary")
    assert messages == original
    assert before == {path: path.read_bytes() for path in app_paths.root.rglob("*") if path.is_file()}
    retry = [event async for event in manager.events(
        [{"role": "user", "content": "Explain synthetic dialysis learning."}],
        scope=SCOPE, run_id="stop-before-summary")]
    assert retry[-1].type == "completed" and len(requests) == 1
    assert not manager.status()["active_runs"]


@pytest.mark.asyncio
@pytest.mark.parametrize("model,code", [
    ("gpt-6.1-sol", "model_unavailable"), ("gpt-6-luna", "model_unavailable"),
    ("unapproved-synthetic-model", "model_not_allowed"),
])
async def test_astra_only_catalogue_rejects_other_overrides_before_transport(app_paths, model, code):
    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(
        lambda request: pytest.fail("Unavailable override reached a provider")))
    seed_astra(manager)
    flow = [event async for event in manager.events(
        [{"role": "user", "content": "Synthetic educational input"}],
        scope=ContextScope(kind=Scope.STUDY), run_id="model-override", model=model)]
    assert [event.type for event in flow] == ["error"]
    assert flow[0].payload["code"] == code
    models = manager.connections()["connections"][0]["models"]
    assert [item["id"] for item in models if item["availability"] == "available"] == [MODEL]
    assert manager.connections()["selected_provider"] == "codex"
    assert not manager.status()["active_runs"] and not manager.status()["live_provider_verified"]


class PausedSSE(httpx.AsyncByteStream):
    def __init__(self):
        self.waiting = asyncio.Event()
        self.closed = asyncio.Event()

    async def __aiter__(self):
        event = {"type": "response.output_text.delta", "delta": "Synthetic unfinished reply",
                 "item_id": "synthetic", "output_index": 0, "content_index": 0,
                 "sequence_number": 1}
        yield ("data: " + json.dumps(event) + "\n\n").encode()
        self.waiting.set()
        await asyncio.Event().wait()

    async def aclose(self):
        self.closed.set()


@pytest.mark.asyncio
@pytest.mark.parametrize("stop", ["cancel", "consumer-task"])
async def test_pending_sdk_read_closes_without_inflight_or_capability_success(app_paths, stop):
    body = PausedSSE()
    requests = []

    def serve(request):
        requests.append(request)
        assert request.url == "https://api.openai.com/v1/responses"
        assert json.loads(request.content)["model"] == MODEL
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=body)

    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(serve))
    seed_astra(manager)
    manager.context.plan([{"role": "user", "content": "Synthetic teaching"}],
        provider="codex", model=MODEL)
    received = []

    async def collect():
        async with aclosing(manager.events([{"role": "user", "content": SENTINEL}],
                scope=SCOPE, run_id="pending-sdk")) as stream:
            async for event in stream:
                received.append(event)

    task = asyncio.create_task(collect())
    try:
        await asyncio.wait_for(body.waiting.wait(), 3)
        if stop == "cancel":
            assert await manager.cancel("pending-sdk")
            await asyncio.wait_for(task, 3)
            assert [event.type for event in received] == ["started", "delta", "cancelled"]
        else:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, 3)
        assert body.closed.is_set() and len(requests) == 1
        assert not manager.status()["active_runs"]
        assert not manager.status()["live_provider_verified"]
        astra = manager.connections()["connections"][0]["models"][1]
        assert astra["id"] == MODEL and astra["text_input"] == "unknown"
        assert not await manager.cancel("pending-sdk")
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await manager.close()


def decode(response):
    assert response.status_code == 200
    events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
    assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
    assert sum(event["type"] in {"completed", "error", "cancelled"} for event in events) == 1
    return events


def producer_app(app_paths, serve):
    from renulus.server import create_app

    app = create_app(app_paths.root, token="synthetic-local-token", source_root=app_paths.source_root)
    services = app.state.services
    memory = services.registry["memory"]
    # No lifespan or workers: exercise SQLite capture eligibility without loading helpers.
    services.registry["knowledge"] = services.registry["memory"] = None
    provider = services.registry["provider"]
    provider._http_transport = httpx.MockTransport(serve)
    return app, provider, memory


@pytest.mark.asyncio
@pytest.mark.parametrize("failure,code,topic", [
    ("auth", "authentication_required", "ckd"),
    ("quota", "subscription_limit", "transplant"),
    ("eof", "provider_stream_incomplete", "dialysis"),
])
async def test_astra_learn_failure_retry_and_durable_answer_capture_eligibility(app_paths, failure, code, topic):
    requests = []
    phase = {"fail": True}
    prompt = "SYNTHETIC_USER_PROMPT_NOT_MEMORY Explain " + topic + " education."
    answer = "SYNTHETIC_STUDY_REPLY Original " + topic + " concept exercise."

    def serve(request):
        assert request.url.host == "api.openai.com"
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"models": [{"slug": MODEL, "visibility": "list"}]})
        assert request.url.path == "/v1/responses"
        requests.append(request)
        assert json.loads(request.content)["model"] == MODEL
        if not phase["fail"]:
            return response(answer)
        if failure == "eof":
            return httpx.Response(200, headers={"content-type": "text/event-stream"},
                content="data: " + json.dumps({"type": "response.output_text.delta",
                    "delta": "SYNTHETIC_PARTIAL_REPLY_NEVER_CAPTURE", "item_id": "synthetic",
                    "output_index": 0, "content_index": 0, "sequence_number": 1}) + "\n\n")
        return httpx.Response(401 if failure == "auth" else 429,
            json={"error": {"message": SENTINEL + " synthetic-plan-token"}})

    app, provider, memory = producer_app(app_paths, serve)
    seed_astra(provider)
    headers = {"x-renulus-token": "synthetic-local-token"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
            base_url="http://127.0.0.1", headers=headers) as local:
        flow = decode(await local.post("/api/v1/learn/ask", json={
            "question": prompt, "scope": {"kind": "study"}, "topic_id": topic}))
        assert flow[-1]["type"] == "error" and flow[-1]["payload"]["code"] == code
        assert SENTINEL not in json.dumps(flow) and "synthetic-plan-token" not in json.dumps(flow)
        thread_id = flow[0]["payload"]["thread_id"]
        failed = (await local.get("/api/v1/learn/threads/" + thread_id)).json()
        assert [message["role"] for message in failed["messages"]] == ["user"]
        assert failed["messages"][0]["content"] == prompt
        assert failed["runs"][0]["state"] == "failed"
    services = app.state.services
    memory.repository.scan()
    assert services.db.fetch_all("SELECT * FROM learning_evidence") == []
    assert memory.repository.jobs() == [] and not provider.status()["active_runs"]
    await provider.close()
    await memory.close()
    restarted, provider, memory = producer_app(app_paths, serve)
    assert provider.connections()["selected_provider"] == "codex"
    assert provider.connections()["connections"][0]["status"] == "configured"
    phase["fail"] = False
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=restarted),
            base_url="http://127.0.0.1", headers=headers) as local:
        assert (await local.get("/api/v1/learn/threads/" + thread_id)).json()["messages"] == failed["messages"]
        assert (await local.post("/api/v1/connections/codex/refresh")).status_code == 200
        flow = decode(await local.post("/api/v1/learn/ask", json={
            "question": prompt, "scope": {"kind": "study"}, "topic_id": topic,
            "thread_id": thread_id}))
        assert flow[-1]["type"] == "completed"
        saved = (await local.get("/api/v1/learn/threads/" + thread_id)).json()
        assert [message["role"] for message in saved["messages"]] == ["user", "user", "assistant"]
        assert saved["messages"][-1]["content"] == answer
    repository = memory.repository
    repository.scan()
    jobs = [job for job in repository.jobs() if job["evidence_id"].startswith("learn-answer:")]
    assert len(jobs) == 1 and jobs[0]["state"] == "queued"
    scope = ContextScope(kind=Scope.STUDY, entity_id=thread_id)
    material = repository.material(jobs[0]["evidence_id"], scope)
    assert material["text"] == answer and material["infer"] is True
    assert "SYNTHETIC_USER_PROMPT_NOT_MEMORY" not in material["text"]
    repository.scan()
    assert repository.enqueue(jobs[0]["evidence_id"], scope)["id"] == jobs[0]["id"]
    assert len(requests) == 2 and not provider.status()["active_runs"]
    assert not provider.status()["live_provider_verified"]
    models = provider.connections()["connections"][0]["models"]
    assert [model["id"] for model in models if model["availability"] == "available"] == [MODEL]
    assert memory._engine is None and memory._embedding is None
    await provider.close()
    await memory.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("context", ["study", "temporary", "unclassified"])
async def test_astra_generated_practice_preserves_scope_and_excludes_unreviewed_memory(app_paths, context):
    requests = []
    batch = {"items": [{
        "stem": "Original synthetic dialysis token exercise",
        "options": [
            {"id": "a", "text": "Marked token", "rationale": "Original marked token"},
            {"id": "b", "text": "Other token", "rationale": "Original distractor"},
        ],
        "correct_option_id": "a", "explanation": "SYNTHETIC_UNREVIEWED_KEY_NOT_MEMORY",
        "hint": None, "source_indices": [],
    }]}

    def serve(request):
        assert request.url == "https://api.openai.com/v1/responses"
        requests.append(request)
        assert json.loads(request.content)["model"] == MODEL
        return response(json.dumps(batch))

    app, provider, memory = producer_app(app_paths, serve)
    seed_astra(provider)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
            base_url="http://127.0.0.1", headers={"x-renulus-token": "synthetic-local-token"}) as local:
        flow = decode(await local.post("/api/v1/assessment/practice/generate", json={
            "prompt": "SYNTHETIC_PROMPT_NOT_MEMORY Original token learning exercise.",
            "context": context, "count": 1, "topic_id": "dialysis",
            "idempotency_key": "astra-practice-" + context}))
        assert flow[-1]["type"] == "completed"
        assert "SYNTHETIC_UNREVIEWED_KEY_NOT_MEMORY" not in json.dumps(flow)
        session = flow[-1]["payload"]["session"]
        expected_scope = {"study": "generated-practice", "temporary": "temporary-case",
                          "unclassified": "unclassified"}[context]
        assert session["scope"]["kind"] == expected_scope
        answered = await local.post("/api/v1/assessment/practice/sessions/" + session["id"] + "/answer",
            json={"idempotency_key": "answer-" + context,
                  "item_id": session["current_item"]["id"], "option_ids": ["a"]})
        assert answered.status_code == 200
        assert answered.json()["feedback"]["verification"] == "generated-unreviewed"
        listed = (await local.get("/api/v1/assessment/practice/sessions")).json()["sessions"]
        assert len(listed) == (1 if context == "study" else 0)
    memory.repository.scan()
    assert app.state.services.db.fetch_all("SELECT * FROM learning_evidence") == []
    assert app.state.services.db.fetch_all("SELECT * FROM assessment_attempts") == []
    assert memory.repository.jobs() == []
    assert memory._engine is None and memory._embedding is None
    assert len(requests) == 1 and not provider.status()["active_runs"]
    assert not provider.status()["live_provider_verified"]
    if context != "study":
        for path in app_paths.root.rglob("*"):
            if path.is_file():
                data = path.read_bytes()
                assert b"SYNTHETIC_PROMPT_NOT_MEMORY" not in data
                assert b"SYNTHETIC_UNREVIEWED_KEY_NOT_MEMORY" not in data
    await provider.close()
    await memory.close()
