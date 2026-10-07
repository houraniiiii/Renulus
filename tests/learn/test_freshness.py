"""Complete Explain API/service with synthetic HTTP and provider responses only."""
import asyncio
import json

import httpx
import pytest

from renulus.contracts import ContextScope, Scope
from renulus.knowledge.repository import KnowledgeRepository
from renulus.learn.evidence import conversation_history
from renulus.retrieval.service import RetrievalService
from renulus.server import create_app
from test_discovery import ROOT, Provider, no_public_network


def europe(**changes):
    row = {"id": "10001", "source": "MED", "pmid": "10001", "pmcid": "PMC10001",
        "title": "Synthetic kidney article", "doi": "10.0000/synthetic",
        "firstPublicationDate": "2026-09-01", "isOpenAccess": "Y", "license": "cc by",
        "pubTypeList": {"pubType": ["Journal Article"]}}
    row.update(changes)
    return {"resultList": {"result": [row]}}


def article():
    return b'''<article article-type="research-article"><front><article-meta>
      <article-id pub-id-type="pmcid">PMC10001</article-id>
      <article-id pub-id-type="pmid">10001</article-id>
      <article-id pub-id-type="doi">10.0000/synthetic</article-id>
      <title-group><article-title>Synthetic kidney article</article-title></title-group>
      <pub-date><year>2026</year><month>9</month><day>1</day></pub-date>
      <permissions><copyright-holder>Synthetic Author</copyright-holder><license>
      <ext-link href="https://creativecommons.org/licenses/by/4.0/">CC BY</ext-link>
      </license></permissions></article-meta></front><body><sec><title>Results</title>
      <p>Synthetic body passage with kidney research observations.</p></sec></body></article>'''


@pytest.fixture
def flow(tmp_path):
    app = create_app(tmp_path / "profile", source_root=ROOT)
    services = app.state.services
    requests, local_calls = [], []
    class Index:
        path = services.paths.indexes / "unused-freshness-index"
    knowledge = KnowledgeRepository(services, extractor=object(), embedder=object(), index=Index())
    async def local(query, **kwargs):
        local_calls.append((query, kwargs))
        return {"passages": []}
    knowledge.retrieve = local
    async def transport(request):
        requests.append(request)
        if request.url.path.endswith("/search"):
            return httpx.Response(200, json=europe())
        return httpx.Response(200, content=article())
    gateway = RetrievalService(services, transport=httpx.MockTransport(transport))
    provider = Provider()
    services.registry.update(knowledge=knowledge, retrieval=gateway, provider=provider, memory=None)
    return app, services, knowledge, gateway, provider, requests, local_calls


def prepare(services, kind=Scope.STUDY):
    question = "Explain current kidney transplantation evidence SYNTHETIC_PRIVATE_QUERY_4821"
    learn = services.get("learn")
    _, run = learn.prepare(question, ContextScope(kind=kind), None, "T21", "direct", "freshness-test")
    return learn, run, question


async def collect(learn, run, question):
    return [item async for item in learn.answer(run, question, "direct", "T21")]


@pytest.mark.asyncio
async def test_fresh_explain_fetches_body_with_current_only_and_traceable_dates(flow):
    _, services, _, _, provider, requests, local_calls = flow
    learn, run, question = prepare(services)
    events = await collect(learn, run, question)
    assert events[-1].type == "completed" and len(requests) == 3
    assert len(local_calls) == 2 and all(call[1]["current_only"] is True for call in local_calls)
    assert all(question not in str(request.url) for request in requests)
    sources = [item.payload for item in events if item.type == "sources"][-1]
    assert sources["verification"] == "dated-research" and sources["latest_final_verified"] is False
    citation = sources["citations"][0]
    assert citation["text"] in provider.calls[0][1]["system"]
    assert citation["publication_date"] in provider.calls[0][1]["system"]
    assert citation["canonical_url"] in provider.calls[0][1]["system"]
    assert citation["locators"][0]["item_id"] in provider.calls[0][1]["system"]
    assert learn.get_thread(run.thread_id)["messages"][-1]["citations"] == sources["citations"]
    assert services.db.fetch_all("SELECT * FROM retrieval_imports") == []
    assert services.db.fetch_all("SELECT * FROM knowledge_documents") == []


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["offline", "no-rights", "timeout"])
async def test_fresh_retrieval_failure_is_visible_and_never_supplies_metadata_as_evidence(flow, monkeypatch, failure):
    _, services, _, gateway, provider, _, _ = flow
    async def handler(request):
        if failure == "offline":
            raise httpx.ConnectError("PRIVATE_TRANSPORT_DETAIL", request=request)
        if failure == "timeout":
            await asyncio.Event().wait()
        return httpx.Response(200, json=europe(license="cc by-nc"))
    gateway.http.transport = httpx.MockTransport(handler)
    if failure == "timeout":
        monkeypatch.setattr("renulus.learn.service.PUBLIC_EVIDENCE_TIMEOUT_SECONDS", 0.01)
    learn, run, question = prepare(services)
    events = await collect(learn, run, question)
    failed = next(item for item in events if item.type == "retrieval-failed")
    assert failed.payload["code"] in ("retrieval_unavailable", "article_permission_required", "source_evidence_timeout")
    assert "not source-verified" in failed.payload["message"]
    assert "PRIVATE_TRANSPORT_DETAIL" not in json.dumps(failed.payload)
    assert events[-1].type == "completed" and events[-1].payload["citations"] == []
    assert "Synthetic kidney article" not in provider.calls[0][1]["system"]
    assert failed.payload["code"] in provider.calls[0][1]["system"]
    if failure == "no-rights":
        assert "does not permit" in failed.payload["message"]


@pytest.mark.asyncio
async def test_stop_during_public_fulltext_cancels_without_answer_or_capture(flow):
    _, services, _, gateway, provider, _, _ = flow
    entered, abandoned = asyncio.Event(), asyncio.Event()
    async def handler(request):
        if request.url.path.endswith("/search"):
            return httpx.Response(200, json=europe())
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            abandoned.set()
    gateway.http.transport = httpx.MockTransport(handler)
    learn, run, question = prepare(services)
    task = asyncio.create_task(collect(learn, run, question))
    await asyncio.wait_for(entered.wait(), 2)
    await learn.cancel(run.id)
    events = await asyncio.wait_for(task, 2)
    assert abandoned.is_set() and events[-1].type == "cancelled"
    assert provider.calls == [] and len(learn.get_thread(run.thread_id)["messages"]) == 1
    assert services.db.fetch_all("SELECT * FROM learning_evidence") == []


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", [Scope.TEMPORARY_CASE, Scope.UNCLASSIFIED])
async def test_fresh_words_in_temporary_context_never_fetch_or_persist(flow, scope):
    _, services, _, _, _, requests, calls = flow
    learn, run, question = prepare(services, scope)
    events = await collect(learn, run, question)
    assert events[-1].type == "completed" and requests == calls == []
    assert learn.list_threads() == [] and services.db.fetch_all("SELECT * FROM retrieval_usage") == []
    for path in services.paths.root.rglob("*"):
        if path.is_file():
            assert question.encode() not in path.read_bytes()


@pytest.mark.asyncio
async def test_history_exclusion_uses_projection_and_preserves_stored_message(flow):
    _, services, knowledge, gateway, _, _, _ = flow
    citation = (await gateway.evidence("T21", scope=ContextScope(kind=Scope.STUDY)))["passages"][0]
    message = {"role": "assistant", "content": "SUPERSEDED_ANSWER_SENTINEL", "citations": [citation]}
    original = json.dumps(message, sort_keys=True)
    knowledge.check_evidence = lambda *args, **kwargs: {"state": "available", "eligible_ids": [], "metadata": {}}
    history = await conversation_history([message], knowledge, ContextScope(kind=Scope.STUDY), "T21", True)
    assert "SUPERSEDED_ANSWER_SENTINEL" not in history[0]["content"]
    assert "no longer eligible" in history[0]["content"] and json.dumps(message, sort_keys=True) == original


@pytest.mark.asyncio
async def test_source_change_during_answer_refuses_commit_and_capture(flow):
    _, services, knowledge, _, provider, _, _ = flow
    original_check = knowledge.check_evidence
    async def stream(messages, **kwargs):
        yield "A partial synthetic answer."
        knowledge.check_evidence = lambda *args, **kw: {"state": "available", "eligible_ids": [], "metadata": {}}
    provider.stream = stream
    learn, run, question = prepare(services)
    events = await collect(learn, run, question)
    assert events[-1].type == "error" and events[-1].payload["code"] == "explain_sources_changed"
    assert len(learn.get_thread(run.thread_id)["messages"]) == 1
    assert services.db.fetch_all("SELECT * FROM learning_evidence") == []
    knowledge.check_evidence = original_check


@pytest.mark.asyncio
async def test_fresh_sse_replay_reuses_citations_without_second_fetch(flow):
    app, services, _, _, _, requests, _ = flow
    body = {"question": "Explain current transplant evidence", "topic_id": "T21", "scope": {"kind": "study"}, "freshness": True}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        first = await client.post("/api/v1/learn/ask", json=body, headers={"Idempotency-Key": "fresh-api"})
        replay = await client.post("/api/v1/learn/ask", json=body, headers={"Idempotency-Key": "fresh-api"})
    assert first.status_code == replay.status_code == 200 and len(requests) == 3
    assert '"replayed":true' in replay.text
    events = [json.loads(line[6:]) for line in first.text.splitlines() if line.startswith("data: ")]
    assert events[-1]["payload"]["citations"][0]["source_kind"] == "public-article"
    replay_events = [json.loads(line[6:]) for line in replay.text.splitlines() if line.startswith("data: ")]
    assert replay_events[-1]["payload"]["citations"] == events[-1]["payload"]["citations"]


@pytest.mark.asyncio
async def test_source_change_during_memory_recall_blocks_provider_dispatch(flow):
    _, services, knowledge, _, provider, _, _ = flow
    class Memory:
        def retrieve(self, *args, **kwargs):
            knowledge.check_evidence = lambda *a, **kw: {"state": "available", "eligible_ids": [], "metadata": {}}
            return {"context": "", "records": []}
    services.registry["memory"] = Memory()
    learn, run, question = prepare(services)
    events = await collect(learn, run, question)
    assert events[-1].type == "error" and events[-1].payload["code"] == "explain_sources_changed"
    assert provider.calls == [] and len(learn.get_thread(run.thread_id)["messages"]) == 1
    assert services.db.fetch_all("SELECT * FROM learning_evidence") == []
