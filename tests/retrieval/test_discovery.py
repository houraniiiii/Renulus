import asyncio
from concurrent.futures import ThreadPoolExecutor
import json

import httpx
import pytest

from renulus.contracts import ApiError, ContextScope, Scope
from renulus.retrieval.service import RetrievalService
from .conftest import SyntheticProtector
from .fixtures import europe

STUDY = ContextScope(kind=Scope.STUDY, entity_id="PRIVATE_SYNTHETIC_CASE_ENTITY")


def make(services, handler, **kwargs):
    return RetrievalService(services, transport=httpx.MockTransport(handler), protector=SyntheticProtector(), **kwargs)


def test_installed_topic_label_only_and_default_stays_keyfree(services, monkeypatch):
    for name in ("NCBI_API_KEY", "TAVILY_API_KEY", "BRAVE_API_KEY", "EXA_API_KEY"):
        monkeypatch.setenv(name, "AMBIENT_SYNTHETIC_DO_NOT_USE")
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=europe())
    service = make(services, handler)
    async def run():
        await service.configure("tavily", api_key="EXPLICIT_SYNTHETIC_KEY", enabled=True)
        await service.select("tavily")
        assert calls == []
        return await service.discover("T21", scope=STUDY)
    result = asyncio.run(run())
    assert len(calls) == 1 and calls[0].url.host == "www.ebi.ac.uk"
    label = next(row["label"] for row in services.registry["content"].list_topics() if row["id"] == "T21")
    assert calls[0].url.params["query"] == 'TITLE_ABS:"' + label + '"'
    outgoing = str(calls[0].url) + str(calls[0].headers) + calls[0].content.decode()
    assert all(secret not in outgoing for secret in ("PRIVATE_SYNTHETIC", "AMBIENT_SYNTHETIC", "EXPLICIT_SYNTHETIC"))
    assert result["topic_id"] == "T21" and result["topic_label"] == label
    assert result["passage_evidence"] is False and result["latest_final_verified"] is False
    assert result["records"][0]["retracted"] is None
    assert service.status()["connections"][0]["requests_used"] == 1
    assert "PRIVATE_SYNTHETIC" not in str(services.db.fetch_all("SELECT * FROM retrieval_usage"))


@pytest.mark.parametrize("kind", [Scope.TEMPORARY_CASE, Scope.SAVED_CASE, Scope.UNCLASSIFIED, Scope.REVIEWED_ASSESSMENT, Scope.GENERATED_PRACTICE])
def test_forbidden_contexts_reject_before_network_or_any_profile_write(services, kind):
    calls = []
    service = make(services, lambda request: calls.append(request))
    before = {str(path): path.read_bytes() for path in services.paths.root.rglob("*") if path.is_file()}
    with pytest.raises(ApiError) as error:
        asyncio.run(service.discover("T21", scope=ContextScope(kind=kind, entity_id="PRIVATE_SYNTHETIC_SENTINEL")))
    assert error.value.code == "retrieval_scope_blocked" and calls == []
    assert before == {str(path): path.read_bytes() for path in services.paths.root.rglob("*") if path.is_file()}


def test_unknown_topic_and_bad_response_are_visible(services):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"provider_debug": "SYNTHETIC_SECRET_BODY"})
    service = make(services, handler)
    with pytest.raises(ApiError) as unknown:
        asyncio.run(service.discover("PRIVATE_SYNTHETIC_QUESTION", scope=STUDY))
    assert unknown.value.code == "retrieval_topic_unknown" and calls == []
    with pytest.raises(ApiError) as malformed:
        asyncio.run(service.discover("T21", scope=STUDY))
    assert malformed.value.code == "retrieval_invalid_response"
    assert "SYNTHETIC_SECRET_BODY" not in str(malformed.value)
    row = next(row for row in service.status()["connections"] if row["provider"] == "europe-pmc")
    assert row["auth_status"] == "retrieval_invalid_response" and row["last_success_at"] is None


@pytest.mark.parametrize("provider", ["pubmed", "ncbi"])
def test_pubmed_primary_two_call_schema_and_explicit_optional_key(services, provider):
    calls = []
    def handler(request):
        calls.append(request)
        if request.url.path.endswith("esearch.fcgi"):
            return httpx.Response(200, json={"esearchresult": {"idlist": ["10001"], "count": "1"}})
        return httpx.Response(200, json={"result": {"uids": ["10001"], "10001": {"title": "Synthetic transplant study", "authors": [{"name": "Synthetic Author"}], "pubdate": "2026 Sep", "articleids": [{"idtype": "pmc", "value": "PMC10001"}], "pubtype": ["Journal Article"]}}})
    service = make(services, handler)
    async def run():
        await service.configure("ncbi", api_key="SYNTHETIC_NCBI", enabled=True)
        await service.select("ncbi")
        return await service.discover("T21", scope=STUDY, provider=provider)
    result = asyncio.run(run())
    assert len(calls) == 2 and all(request.url.host == "eutils.ncbi.nlm.nih.gov" for request in calls)
    for request in calls:
        assert request.url.params["db"] == "pubmed" and request.url.params["retmode"] == "json"
        assert request.url.params.get("api_key") == ("SYNTHETIC_NCBI" if provider == "ncbi" else None)
        assert "PRIVATE_SYNTHETIC" not in str(request.url)
    assert calls[0].url.params["term"].endswith('[Title/Abstract]') and calls[1].url.params["id"] == "10001"
    assert result["records"][0]["pmcid"] == "PMC10001" and result["records"][0]["retracted"] is None
    assert next(row for row in service.status()["connections"] if row["provider"] == provider)["requests_used"] == 2


def test_empty_pubmed_uses_one_actual_request(services):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"esearchresult": {"idlist": [], "count": "0"}})
    service = make(services, handler)
    assert asyncio.run(service.discover("T21", scope=STUDY, provider="pubmed"))["records"] == []
    assert len(calls) == 1
    assert next(row for row in service.status()["connections"] if row["provider"] == "pubmed")["requests_used"] == 1


@pytest.mark.parametrize("provider", ["brave", "tavily", "exa"])
def test_optional_vendor_exact_schema_pure_hermes_reuse_no_fallback(services, provider, monkeypatch):
    calls = []
    def handler(request):
        calls.append(request)
        if provider == "brave":
            data = {"web": {"results": [{"title": "Synthetic public paper", "url": "https://example.org/paper", "description": "Discovery snippet"}]}}
        else:
            data = {"results": [{"title": "Synthetic public paper", "url": "https://example.org/paper", "content": "Discovery snippet"}]}
        return httpx.Response(200, json=data)
    service = make(services, handler)
    async def run():
        await service.configure(provider, api_key="SYNTHETIC_APP_KEY", enabled=True)
        with pytest.raises(ApiError) as disabled:
            await service.discover("T21", scope=STUDY, provider=provider)
        assert disabled.value.code == "retrieval_tool_disabled" and not calls
        await service.select(provider)
        return await service.discover("T21", scope=STUDY, provider="selected-tool")
    result = asyncio.run(run())
    assert len(calls) == 1 and result["provider"] == provider
    assert result["records"][0]["url"] == "https://example.org/paper"
    assert result["records"][0]["passage_evidence"] is False
    request = calls[0]
    label = service.topic("T21")["label"]
    assert "PRIVATE_SYNTHETIC" not in str(request.url) + request.content.decode()
    if provider == "brave":
        assert request.method == "GET" and request.url.path == "/res/v1/web/search"
        assert request.url.params["q"] == label + " nephrology research"
        assert request.headers["X-Subscription-Token"] == "SYNTHETIC_APP_KEY"
    elif provider == "tavily":
        assert request.method == "POST" and request.url.path == "/search"
        assert request.headers["Authorization"] == "Bearer SYNTHETIC_APP_KEY"
        assert json.loads(request.content) == {"query": label + " nephrology research", "max_results": 5, "search_depth": "basic", "auto_parameters": False, "include_answer": False, "include_raw_content": False, "include_images": False, "include_usage": True}
    else:
        assert request.method == "POST" and request.url.path == "/search"
        assert request.headers["x-api-key"] == "SYNTHETIC_APP_KEY"
        assert json.loads(request.content) == {"query": label + " nephrology research", "numResults": 5, "type": "fast"}
    public = str(service.status())
    assert "SYNTHETIC_APP_KEY" not in public and service.status()["credit_caps_are_monetary_guarantee"] is False


def test_durable_atomic_budget_failures_count_and_utc_rollover(services):
    calls, day = [], ["2026-10-04"]
    def handler(request):
        calls.append(request)
        return httpx.Response(429, json={"key": "SYNTHETIC_SECRET_DO_NOT_RETURN"})
    service = make(services, handler, today=lambda: day[0])
    async def setup():
        await service.configure("exa", api_key="SYNTHETIC_APP_KEY", enabled=True, daily_request_limit=2, daily_credit_limit=2)
        await service.select("exa")
    asyncio.run(setup())
    for _ in range(2):
        with pytest.raises(ApiError) as error:
            asyncio.run(service.discover("T21", scope=STUDY, provider="exa"))
        assert error.value.code == "retrieval_provider_limit"
    restarted = make(services, handler, today=lambda: day[0])
    with pytest.raises(ApiError) as cap:
        asyncio.run(restarted.discover("T21", scope=STUDY, provider="exa"))
    assert cap.value.code == "retrieval_daily_limit" and len(calls) == 2
    row = next(row for row in restarted.status()["connections"] if row["provider"] == "exa")
    assert row["requests_used"] == row["credits_used"] == 2 and row["auth_status"] == "retrieval_daily_limit"
    day[0] = "2026-10-05"
    def reserve(_):
        try:
            restarted._reserve("exa", 1, 1)
            return True
        except ApiError:
            return False
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(reserve, range(8))) == 2
    assert services.db.fetch_one("SELECT requests,credits FROM retrieval_usage WHERE provider='exa' AND day='2026-10-05'") == {"requests": 2, "credits": 2}


def test_zero_credit_cap_and_failure_do_not_change_selection(services):
    calls = []
    service = make(services, lambda request: calls.append(request))
    async def run():
        await service.configure("tavily", api_key="SYNTHETIC", enabled=True, daily_credit_limit=0)
        await service.select("tavily")
        with pytest.raises(ApiError) as error:
            await service.discover("T21", scope=STUDY, provider="selected-tool")
        assert error.value.code == "retrieval_daily_limit"
    asyncio.run(run())
    assert calls == [] and service.status()["selected_tool"] == "tavily"


def test_vendor_result_cap_and_unsafe_links_are_discovery_only(services):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"results": [{"title": "Synthetic unsafe link", "url": "https://127.0.0.1/private"}, {"title": "Synthetic public link", "url": "https://example.org/paper", "publishedDate": "2026-09-01"}], "costDollars": {"total": 0.007}})
    service = make(services, handler)
    async def run():
        await service.configure("exa", api_key="SYNTHETIC_KEY", enabled=True)
        await service.select("exa")
        return await service.discover("T21", scope=STUDY, provider="exa", limit=20)
    result = asyncio.run(run())
    assert len(calls) == 1 and json.loads(calls[0].content)["numResults"] == 5
    assert [row["url"] for row in result["records"]] == ["https://example.org/paper"]
    assert result["records"][0]["publication_date"] == "2026-09-01"
    assert result["provider_usage"] == {"reported_cost_dollars": 0.007} and result["billing_verified"] is False
