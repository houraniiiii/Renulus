"""Real Learn/SQLite/Europe PMC normalization with controlled HTTP, no live calls."""
import asyncio
import ipaddress
import json
from pathlib import Path
import socket

import httpx
import pytest

from renulus.contracts import ApiError, ContextScope, Scope
from renulus.retrieval.service import RetrievalService
from renulus.server import create_app

ROOT = Path(__file__).resolve().parents[2]
TITLE = "SYNTHETIC_DISCOVERY_METADATA_NEVER_SAVED_5741"
ANSWER = "A synthetic explanation without checked sources."


@pytest.fixture(autouse=True)
def no_public_network(monkeypatch):
    # Permit only Windows asyncio's local self-pipe; HTTP uses MockTransport.
    for name in ("connect", "connect_ex"):
        original = getattr(socket.socket, name)
        def guarded(self, address, _original=original):
            if isinstance(address, tuple):
                try:
                    if ipaddress.ip_address(address[0]).is_loopback:
                        return _original(self, address)
                except ValueError:
                    pass
            raise AssertionError("Public network calls are forbidden in Learn tests")
        monkeypatch.setattr(socket.socket, name, guarded)


class Provider:
    def __init__(self):
        self.calls, self.cancelled = [], []

    async def stream(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        yield ANSWER

    async def cancel(self, run_id):
        self.cancelled.append(run_id)


class LocalKnowledge:
    def __init__(self, results=None):
        self.calls = []
        self.results = list(results or [{"passages": []}])

    async def retrieve(self, query, **kwargs):
        self.calls.append((query, kwargs))
        return self.results.pop(0) if len(self.results) > 1 else self.results[0]


def metadata():
    return {"resultList": {"result": [{"id": str(10001 + index), "source": "MED",
        "title": TITLE + str(index), "authorString": "Synthetic Author",
        "firstPublicationDate": "2026-09-01", "doi": "10.0000/synthetic",
        "pmcid": "PMC10001", "isOpenAccess": "Y"} for index in range(7)]}}


@pytest.fixture
def build(tmp_path):
    def make(handler=None):
        app = create_app(tmp_path / "profile", source_root=ROOT)
        services = app.state.services
        services.db.apply_migration("retrieval-001",
            (ROOT / "runtime/renulus/retrieval/schema.sql").read_text(encoding="utf-8"))
        requests = []
        async def controlled(request):
            requests.append(request)
            if handler:
                result = handler(request)
                return await result if asyncio.iscoroutine(result) else result
            return httpx.Response(200, json=metadata())
        retrieval = RetrievalService(services, transport=httpx.MockTransport(controlled))
        provider, knowledge = Provider(), LocalKnowledge()
        services.registry.update(retrieval=retrieval, provider=provider, knowledge=knowledge, memory=None)
        return app, services, provider, knowledge, requests
    return make


def prepare(services, *, topic="T08", kind=Scope.STUDY):
    learn = services.get("learn")
    question = "SYNTHETIC_RAW_QUESTION_NEVER_IN_NETWORK_7319"
    _, run = learn.prepare(question, ContextScope(kind=kind, entity_id="SYNTHETIC_ENTITY_NO_EGRESS"),
                           None, topic, "direct", "discovery-test")
    return learn, run, question


async def collect(learn, run, question, topic="T08"):
    return [item async for item in learn.answer(run, question, "direct", topic)]


def assert_unverified(flow):
    sources = next(item for item in flow if item.type == "sources")
    assert sources.payload == {"citations": [], "verification": "not-verified"}
    assert flow[-1].type == "completed"
    assert flow[-1].payload["citations"] == []
    assert not any(item.type == "error" for item in flow)


@pytest.mark.asyncio
@pytest.mark.parametrize("topic", ["T06", "T20", "T21"])
async def test_one_generic_topic_request_is_discovery_only_and_not_stored(build, tmp_path, topic):
    _, services, provider, knowledge, requests = build()
    # Even a selected paid tool cannot redirect automatic Explain discovery.
    settings = services.get("retrieval").connections.settings
    settings["selected_provider"] = "tavily"
    settings["connections"]["tavily"] = {"enabled": True, "api_key": "SYNTHETIC_KEY_UNUSED"}
    learn, run, question = prepare(services, topic=topic)
    flow = await collect(learn, run, question, topic)
    assert_unverified(flow)
    assert len(knowledge.calls) == 2
    assert knowledge.calls[0][1]["topic_id"] == topic
    assert "topic_id" not in knowledge.calls[1][1]
    assert len(requests) == 1
    request = requests[0]
    label = services.get("retrieval").topic(topic)["label"]
    assert request.method == "GET" and request.url.host == "www.ebi.ac.uk"
    assert request.url.path.endswith("/search")
    assert dict(request.url.params) == {"query": 'TITLE_ABS:"' + label + '"',
        "format": "json", "resultType": "core", "pageSize": "5"}
    assert question not in str(request.url) and run.scope.entity_id not in str(request.url)
    assert "SYNTHETIC_KEY" not in str(request.headers)
    discovered = next(item for item in flow if item.type == "discovered-literature").payload
    assert discovered["topic_id"] == topic and discovered["topic_label"] == label
    assert discovered["provider"] == "europe-pmc" and discovered["queried_at"]
    assert discovered["verification"] == "discovery-only"
    assert discovered["passage_evidence"] is discovered["latest_final_verified"] is False
    assert len(discovered["records"]) == 5
    assert discovered["records"][0]["url"] == "https://pubmed.ncbi.nlm.nih.gov/10001/"
    assert discovered["records"][0]["publication_date"] == "2026-09-01"
    assert TITLE not in provider.calls[0][1]["system"]
    assert "the explanation is not source-verified" in provider.calls[0][1]["system"]
    assert learn.get_thread(run.thread_id)["messages"][-1]["citations"] == []
    assert services.db.fetch_all("SELECT * FROM retrieval_imports") == []
    assert services.db.fetch_all("SELECT * FROM knowledge_documents") == []
    assert services.db.fetch_one("SELECT requests FROM retrieval_usage WHERE provider='europe-pmc'")["requests"] == 1
    for path in tmp_path.rglob("*"):
        if path.is_file():
            assert TITLE.encode() not in path.read_bytes()


@pytest.mark.asyncio
@pytest.mark.parametrize("unfiltered", [False, True])
async def test_local_passages_in_either_attempt_prevent_public_discovery(build, unfiltered):
    _, services, provider, _, requests = build()
    passage = {"id": "synthetic-local-passage", "text": "Synthetic eligible local source text"}
    services.registry["knowledge"] = LocalKnowledge(
        ([{"passages": []}] if unfiltered else []) + [{"passages": [passage]}])
    learn, run, question = prepare(services)
    flow = await collect(learn, run, question)
    assert requests == []
    assert not any("literature" in item.type for item in flow)
    assert next(item for item in flow if item.type == "sources").payload == {
        "citations": [passage], "verification": "retrieved"}
    assert passage["text"] in provider.calls[0][1]["system"]
    assert learn.get_thread(run.thread_id)["messages"][-1]["citations"] == [passage]


@pytest.mark.asyncio
@pytest.mark.parametrize("topic", [None, "SYNTHETIC_ARBITRARY_TOPIC_821"])
async def test_free_or_unknown_topics_never_become_public_queries(build, topic):
    _, services, _, _, requests = build()
    learn, run, question = prepare(services, topic=topic)
    flow = await collect(learn, run, question, topic)
    assert_unverified(flow)
    assert requests == []
    assert not any("literature" in item.type for item in flow)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", [Scope.TEMPORARY_CASE, Scope.UNCLASSIFIED])
async def test_case_scopes_never_discover_or_write_learning_records(build, tmp_path, kind):
    _, services, _, knowledge, requests = build()
    learn, run, question = prepare(services, kind=kind)
    flow = await collect(learn, run, question)
    assert_unverified(flow)
    assert requests == knowledge.calls == []
    assert not any("literature" in item.type or item.type.startswith("memory") for item in flow)
    assert learn.list_threads() == []
    assert services.db.fetch_all("SELECT * FROM learning_evidence") == []
    assert services.db.fetch_all("SELECT * FROM retrieval_usage") == []
    for path in tmp_path.rglob("*"):
        if path.is_file():
            assert question.encode() not in path.read_bytes()


def test_saved_case_scope_is_rejected_before_discovery_or_storage(build):
    _, services, provider, knowledge, requests = build()
    with pytest.raises(ApiError, match="matching case"):
        prepare(services, kind=Scope.SAVED_CASE)
    assert requests == provider.calls == knowledge.calls == []
    assert services.get("learn").list_threads() == []


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["offline", "limit", "malformed"])
async def test_discovery_failures_allow_an_honest_completed_explanation(build, failure):
    def handler(request):
        if failure == "offline":
            raise httpx.ConnectError("SYNTHETIC_ERROR_DETAIL_NOT_EXPOSED", request=request)
        return httpx.Response(429 if failure == "limit" else 200, json={"unexpected": []})
    _, services, provider, _, requests = build(handler)
    class Memory:
        def retrieve(self, *args, **kwargs):
            return {"context": "Synthetic learner preference", "records": [{"id": "one"}]}
        def notify(self):
            assert services.db.fetch_one("SELECT state FROM learn_runs WHERE id=?", (run.id,))["state"] == "completed"
            raise RuntimeError("Synthetic capture notification failure")
    services.registry["memory"] = Memory()
    learn, run, question = prepare(services)
    flow = await collect(learn, run, question)
    assert_unverified(flow)
    assert len(requests) == len(provider.calls) == 1
    failure_event = next(item for item in flow if item.type == "literature-discovery-unavailable")
    assert failure_event.payload["topic_id"] == "T08"
    assert "not source-verified" in failure_event.payload["message"]
    assert "SYNTHETIC_ERROR_DETAIL" not in json.dumps(failure_event.payload)
    assert {"memory", "memory-capture-unavailable"}.issubset({item.type for item in flow})
    assert not any(item.type == "discovered-literature" for item in flow)
    assert learn.get_thread(run.thread_id)["runs"][0]["state"] == "completed"


@pytest.mark.asyncio
async def test_cancel_during_local_retrieval_never_starts_discovery(build):
    _, services, provider, knowledge, requests = build()
    entered, release = asyncio.Event(), asyncio.Event()
    async def retrieve(*args, **kwargs):
        entered.set()
        await release.wait()
        return {"passages": []}
    knowledge.retrieve = retrieve
    learn, run, question = prepare(services)
    task = asyncio.create_task(collect(learn, run, question))
    await asyncio.wait_for(entered.wait(), 2)
    await learn.cancel(run.id)
    release.set()
    flow = await asyncio.wait_for(task, 2)
    assert flow[-1].type == "cancelled"
    assert requests == provider.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("stop", ["cancel", "delete", "disconnect", "timeout"])
async def test_pending_discovery_is_cancelled_and_cannot_publish_late_results(build, monkeypatch, stop):
    entered, abandoned = asyncio.Event(), asyncio.Event()
    async def handler(request):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            abandoned.set()
    if stop == "timeout":
        monkeypatch.setattr("renulus.learn.service.LITERATURE_TIMEOUT_SECONDS", 0.05)
    _, services, provider, _, requests = build(handler)
    learn, run, question = prepare(services)
    task = asyncio.create_task(collect(learn, run, question))
    await asyncio.wait_for(entered.wait(), 2)
    if stop == "cancel":
        await learn.cancel(run.id)
    elif stop == "delete":
        await learn.delete_thread(run.thread_id)
    elif stop == "disconnect":
        task.cancel()
    if stop == "disconnect":
        with pytest.raises(asyncio.CancelledError):
            await task
    else:
        flow = await asyncio.wait_for(task, 2)
        assert not any(item.type == "discovered-literature" for item in flow)
        if stop == "timeout":
            assert_unverified(flow)
            assert next(item for item in flow if item.type == "literature-discovery-unavailable").payload["code"] == "literature_discovery_timeout"
        else:
            assert flow[-1].type == "cancelled"
            assert not any(item.type == "literature-discovery-unavailable" for item in flow)
    assert abandoned.is_set() and len(requests) == 1
    assert len(provider.calls) == (1 if stop == "timeout" else 0)
    assert services.db.fetch_all("SELECT * FROM retrieval_imports") == []
    assert run.id not in learn.active
    if stop == "delete":
        assert learn.list_threads() == []
    else:
        thread = learn.get_thread(run.thread_id)
        assert thread["runs"][0]["state"] == {"cancel": "cancelled", "disconnect": "interrupted", "timeout": "completed"}[stop]
        assert len(thread["messages"]) == (2 if stop == "timeout" else 1)


@pytest.mark.asyncio
async def test_real_sse_api_idempotent_replay_does_not_repeat_discovery(build):
    app, services, _, _, requests = build()
    body = {"question": "Synthetic study question", "topic_id": "T08", "scope": {"kind": "study"}}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        first = await client.post("/api/v1/learn/ask", json=body, headers={"Idempotency-Key": "synthetic-replay"})
        replay = await client.post("/api/v1/learn/ask", json=body, headers={"Idempotency-Key": "synthetic-replay"})
    assert first.status_code == replay.status_code == 200
    flow = [json.loads(line[6:]) for line in first.text.splitlines() if line.startswith("data: ")]
    assert "discovered-literature" in {item["type"] for item in flow}
    assert flow[-1]["type"] == "completed"
    assert "discovered-literature" not in replay.text and '"replayed":true' in replay.text
    assert len(requests) == 1
    assert len(services.get("learn").get_thread(flow[-1]["payload"]["thread_id"])["messages"]) == 2
