"""Integrated producer routes with synthetic HTTP; no helper assets or accounts."""
import asyncio
import ipaddress
import json
from pathlib import Path
import socket
import time
from uuid import uuid4

import httpx
import pytest

from renulus.contracts import ApiError, ContextScope, Scope
from renulus.runtime.policy import ALLOWED_MODELS
from renulus.server import create_app
from renulus.storage import utc_now

SENTINEL = "SYNTHETIC_CROSS_MODULE_CASE_NEVER_SAVE_5308"
SOURCE = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def no_external_sockets(monkeypatch):
    for name in ("connect", "connect_ex"):
        original = getattr(socket.socket, name)

        def loopback(sock, address, _original=original):
            assert isinstance(address, tuple) and ipaddress.ip_address(address[0]).is_loopback
            return _original(sock, address)

        monkeypatch.setattr(socket.socket, name, loopback)


def practice_output():
    return {"items": [{"stem": "Original synthetic token exercise",
        "options": [{"id": "a", "text": "Marked token", "rationale": "Original fixture"},
                    {"id": "b", "text": "Unmarked token", "rationale": "Original distractor"}],
        "correct_option_id": "a", "explanation": "Synthetic token explanation",
        "hint": "Inspect the token", "source_indices": []}]}


def codex_response(text):
    events = [{"type": "response.output_text.delta", "delta": text,
        "item_id": "synthetic-message", "output_index": 0, "content_index": 0, "sequence_number": 1},
        {"type": "response.completed", "sequence_number": 2,
         "response": {"id": "synthetic-response", "object": "response", "created_at": 1,
                      "status": "completed", "model": "gpt-6.1-sol", "output": []}}]
    return httpx.Response(200, headers={"content-type": "text/event-stream"},
        content="".join("data: " + json.dumps(event) + "\n\n" for event in events))


def producer_app(tmp_path, selected, *, reject=False):
    app = create_app(tmp_path / "profile", token="synthetic-local-token", source_root=SOURCE)
    services = app.state.services
    provider = services.registry["provider"]
    requests = []

    def serve(request):
        requests.append(request)
        assert request.headers["user-agent"] == "Renulus/0.1.0"
        body = json.loads(request.content)
        assert "tools" not in body and "context_management" not in body
        if selected == "codex":
            assert str(request.url) == "https://api.openai.com/v1/responses"
            assert body["model"] == "gpt-6.1-sol" and body["store"] is False
            instructions = body["instructions"]
        else:
            assert str(request.url) == "https://opencode.ai/zen/go/v1/chat/completions"
            assert body["model"] in ALLOWED_MODELS["opencode-go"]
            assert request.headers["x-opencode-session"]
            instructions = "\n".join(item["content"] for item in body["messages"] if item["role"] == "system")
        if reject:
            return httpx.Response(429, json={"error": {"code": "rate_limit_exceeded"}})
        text = (json.dumps(practice_output()) if "original generated practice" in instructions
                else json.dumps({"memory": [{"text": "Synthetic general glomerular learning point"}]})
                if "SYNTHETIC_MEMORY_SYSTEM" in instructions
                else "Synthetic cross-domain renal learning explanation")
        if selected == "codex":
            return codex_response(text)
        chunks = [{"id": "synthetic", "object": "chat.completion.chunk", "created": 1,
            "model": body["model"], "choices": [{"index": 0, "delta": {"content": delta},
            "finish_reason": reason}]} for delta, reason in [(text, None), (None, "stop")]]
        return httpx.Response(200, headers={"content-type": "text/event-stream"},
            content="".join("data: " + json.dumps(chunk) + "\n\n" for chunk in chunks))

    provider._http_transport = httpx.MockTransport(serve)
    provider._settings["connections"] = {
        "codex": {"client_id": "synthetic-client", "access_token": "synthetic-codex-token",
                  "expires_at": time.time() + 600},
        "opencode-go": {"access_token": "synthetic-go-token"}}
    provider._settings["selected_provider"] = selected
    provider._catalogs = {"codex": {"gpt-6.1-sol"}, "opencode-go": set(ALLOWED_MODELS["opencode-go"])}
    provider._save()
    # No helper instances or paid retrieval; the real consumers handle no source.
    services.registry["knowledge"] = None
    return app, provider, requests


def flow(response):
    assert response.status_code == 200, response.text
    events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
    assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
    assert sum(event["type"] in ("completed", "error", "failed", "cancelled") for event in events) == 1
    return events


def absent(profile, marker=SENTINEL):
    assert all(marker.encode() not in path.read_bytes() for path in profile.rglob("*") if path.is_file())


@pytest.mark.asyncio
@pytest.mark.parametrize("selected", ["codex", "opencode-go"])
async def test_real_cases_explain_and_generated_handoffs_preserve_scope_under_route_policy(tmp_path, selected):
    app, provider, requests = producer_app(tmp_path, selected)
    services = app.state.services
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1",
            headers={"x-renulus-token": "synthetic-local-token"}) as client:
        case = (await client.post("/api/v1/cases/sessions", json={"text": SENTINEL, "title": "Synthetic case"})).json()
        identifier = case["id"]
        discussed = flow(await client.post("/api/v1/cases/sessions/" + identifier + "/discuss",
            json={"revision": case["revision"], "request_id": "cross-discuss", "message": "Explain the mechanism"}))
        assert discussed[-1]["type"] == "completed"
        for target in ("explain", "generated-practice"):
            current = (await client.get("/api/v1/cases/sessions/" + identifier)).json()
            handoff = (await client.post("/api/v1/cases/sessions/" + identifier + "/handoff",
                json={"revision": current["revision"], "target": target, "question": "Review the synthetic mechanism"})).json()
            assert handoff["scope"]["kind"] == "temporary-case"
            if target == "explain":
                result = flow(await client.post("/api/v1/learn/ask", json={"question": handoff["question"],
                    "scope": handoff["scope"], "case_handoff_id": handoff["id"]}))
            else:
                result = flow(await client.post("/api/v1/assessment/practice/generate", json={
                    "prompt": handoff["question"], "count": 1, "context": "temporary",
                    "idempotency_key": "cross-practice", "case_handoff_id": handoff["id"]}))
            assert result[-1]["type"] == "completed"
        assert (await client.get("/api/v1/cases/saved")).json() == {"cases": []}
        assert (await client.get("/api/v1/learn/threads")).json() == {"threads": []}
        assert (await client.get("/api/v1/assessment/practice/sessions")).json() == {"sessions": []}
    assert len(requests) == 3
    assert provider.connections()["selected_provider"] == selected
    assert not provider.status()["active_runs"] and not provider.status()["live_provider_verified"]
    for table in ("learning_evidence", "memory_jobs", "assessment_generated_sessions", "assessment_attempts"):
        assert services.db.fetch_all("SELECT * FROM " + table) == []
    absent(services.paths.root)


@pytest.mark.asyncio
async def test_shared_consumers_surface_go_subscription_limit_without_fallback(tmp_path):
    app, provider, requests = producer_app(tmp_path, "opencode-go", reject=True)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1",
            headers={"x-renulus-token": "synthetic-local-token"}) as client:
        capabilities = (await client.get("/api/v1/assessment/practice/capabilities")).json()
        case = (await client.post("/api/v1/cases/sessions", json={"text": SENTINEL})).json()
        discussion = flow(await client.post("/api/v1/cases/sessions/" + case["id"] + "/discuss",
            json={"revision": case["revision"], "request_id": "presentation-gate", "message": "Explain the mechanism"}))
        practice = flow(await client.post("/api/v1/assessment/practice/generate", json={
            "prompt": "Synthetic token exercise", "count": 1, "context": "temporary",
            "idempotency_key": "presentation-practice"}))
        learn = flow(await client.post("/api/v1/learn/ask", json={
            "question": "Synthetic temporary learning", "scope": {"kind": "temporary-case"}}))
    assert len(requests) == 3 and not provider.status()["active_runs"]
    errors = [discussion[-1]["payload"]["error"], practice[-1]["payload"], learn[-1]["payload"]]
    absent(app.state.services.paths.root)
    assert capabilities["available"] is True and capabilities["code"] is None
    assert all(error["code"] == "subscription_limit" and error["retryable"] for error in errors)


@pytest.mark.asyncio
async def test_actual_mem0_oss_outbox_preserves_go_provider_failure_without_assets(tmp_path, monkeypatch):
    # Qdrant adds a collection tree below the profile. Keep this native fixture
    # short even when pytest uses a long Windows test-function directory name.
    app, provider, requests = producer_app(tmp_path.parent / ("m" + uuid4().hex[:8]), "opencode-go", reject=True)
    services = app.state.services
    memory = services.registry["memory"]

    class ControlledVectors:
        config = {"model_id": "BAAI/bge-small-en-v1.5", "dimensions": 384,
                  "fingerprint": "synthetic-vectors-not-embedding-proof"}

        def embed(self, text, memory_action="add"):
            return [1.0] + [0.0] * 383

        def embed_batch(self, texts, memory_action="add"):
            return [self.embed(text, memory_action) for text in texts]

    # Only the asset-dependent vector delegate is controlled. Actual Mem0 OSS,
    # pinned Hermes backend, local Qdrant, provider bridge and SQLite outbox run.
    monkeypatch.setattr(memory, "_get_embedding", lambda: ControlledVectors())
    scope = ContextScope(kind=Scope.STUDY, entity_id="synthetic-memory-study")
    payload = {"scope": scope.model_dump(mode="json"), "general_learning": True,
               "text": "Synthetic general glomerular education point"}
    services.db.execute("INSERT INTO learning_evidence VALUES(?,?,?,?,?,?)",
        ("synthetic-memory-evidence", "learning-point", "glomerular", scope.entity_id, json.dumps(payload), utc_now()))
    job = memory.enqueue("synthetic-memory-evidence", scope)
    try:
        outcome = await memory.process_pending()
        assert outcome == {"processed": 0}
        failed = memory.repository.job(job["id"])
        assert failed["state"] == "failed"
        assert memory.repository.list() == [] and requests
        assert all(json.loads(request.content)["model"] == "mimo-v2.6-pro" for request in requests)
        assert memory._engine.memory.__class__.__module__ == "mem0.memory.main"
        assert memory._engine.memory.vector_store.client._client.__class__.__name__ == "QdrantLocal"
        assert failed["error_code"] in {"memory_capture_failed", "subscription_limit"}
        assert provider.connections()["selected_provider"] == "opencode-go"
        assert not provider.status()["active_runs"] and not provider.status()["live_provider_verified"]
    finally:
        await memory.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("selected", ["codex", "opencode-go"])
async def test_real_mem0_registered_llm_bridge_consumes_approved_route_without_assets(tmp_path, selected):
    app, provider, requests = producer_app(tmp_path, selected)
    services = app.state.services
    # Import only the real registered bridge under its app-owned bootstrap.
    # No FastEmbed model, Docling model or Qdrant instance is constructed.
    from renulus.memory.engine import bootstrap
    bootstrap(services)
    from renulus.memory.providers import ApprovedLLM, generation_binding
    binding = {"services": services, "loop": asyncio.get_running_loop(),
               "scope": ContextScope(kind=Scope.STUDY, entity_id="synthetic-study"),
               "run_id": "synthetic-memory-bridge", "current": lambda: True}
    token = generation_binding.set(binding)
    try:
        bridge = ApprovedLLM()
        messages = [{"role": "system", "content": "SYNTHETIC_MEMORY_SYSTEM"},
                    {"role": "user", "content": "Synthetic general glomerular study point"}]
        result = json.loads(await asyncio.to_thread(bridge.generate_response, messages))
        assert result == {"memory": [{"text": "Synthetic general glomerular learning point"}]}
    finally:
        generation_binding.reset(token)
    assert len(requests) == 1
    assert provider.connections()["selected_provider"] == selected
    assert not provider.status()["active_runs"] and not provider.status()["live_provider_verified"]
