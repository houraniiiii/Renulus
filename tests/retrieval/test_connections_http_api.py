import asyncio
import gzip
import json
import os

from fastapi.testclient import TestClient
import httpx
import pytest

from renulus.contracts import ApiError
from renulus.retrieval.connections import RetrievalConnections
from renulus.retrieval.http import OfficialHTTP, public_link
from renulus.retrieval.service import RetrievalService
from renulus.runtime.protected import ConnectionStore, WindowsDPAPI
from renulus.server import create_app
from .conftest import ROOT, SyntheticProtector
from .fixtures import europe


def test_separate_protected_namespace_profile_redaction_and_failed_save(services, monkeypatch):
    protector = SyntheticProtector()
    subscription = ConnectionStore(services.paths.root, services.paths.state, protector)
    subscription.save({"version": 1, "selected_provider": "codex", "connections": {"codex": {"api_key": "SYNTHETIC_SUBSCRIPTION_DO_NOT_READ"}}})
    original = subscription.path.read_bytes()
    retrieval = RetrievalConnections(services.paths, protector=protector)
    assert retrieval.settings["connections"] == {} and retrieval.store.path != subscription.path
    assert retrieval.store.entropy != subscription.entropy
    retrieval.configure("brave", api_key="SYNTHETIC_OWN_RETRIEVAL", enabled=False)
    assert b"SYNTHETIC_OWN_RETRIEVAL" not in retrieval.store.path.read_bytes()
    assert subscription.path.read_bytes() == original
    reopened = RetrievalConnections(services.paths, protector=protector)
    assert reopened.config("brave")["api_key"] == "SYNTHETIC_OWN_RETRIEVAL"
    def fail_save(settings):
        raise ApiError("protected_storage_failed", "Synthetic protection failure", 503)
    monkeypatch.setattr(reopened.store, "save", fail_save)
    with pytest.raises(ApiError):
        reopened.configure("brave", api_key="SYNTHETIC_UNSAVED", enabled=True)
    assert reopened.config("brave")["api_key"] == "SYNTHETIC_OWN_RETRIEVAL" and reopened.config("brave")["enabled"] is False


@pytest.mark.skipif(os.name != "nt", reason="Actual Windows DPAPI proof")
def test_native_windows_dpapi_own_synthetic_key_and_wrong_namespace(services):
    retrieval = RetrievalConnections(services.paths)
    retrieval.configure("ncbi", api_key="SYNTHETIC_DPAPI_ONLY", enabled=False)
    ciphertext = retrieval.store.path.read_bytes()
    assert b"SYNTHETIC_DPAPI_ONLY" not in ciphertext
    assert RetrievalConnections(services.paths).config("ncbi")["api_key"] == "SYNTHETIC_DPAPI_ONLY"
    with pytest.raises(ApiError) as wrong:
        WindowsDPAPI().unprotect(ciphertext, b"different-profile-and-namespace")
    assert wrong.value.code == "protected_storage_failed"


@pytest.mark.parametrize("url", ["http://www.ebi.ac.uk/search", "https://www.ebi.ac.uk.evil.test/search", "https://user:secret@www.ebi.ac.uk/search", "https://127.0.0.1/search", "https://10.0.0.1/search", "https://localhost/search", "https://machine.local/search", "https://[::1]/search", "https://www.ebi.ac.uk:444/search", "https://api.tavily.com/search#fragment"])
def test_fixed_endpoint_and_public_link_guards_reject_before_http(url):
    calls = []
    client = OfficialHTTP(transport=httpx.MockTransport(lambda request: calls.append(request)))
    with pytest.raises(ApiError) as error:
        asyncio.run(client.request("GET", url))
    assert error.value.code == "unsafe_retrieval_url" and calls == []
    if "ebi.ac.uk.evil" not in url and "#fragment" not in url:
        assert public_link(url) is None


def test_redirect_no_follow_decoded_size_and_error_body_redaction():
    calls = []
    def redirect(request):
        calls.append(request)
        return httpx.Response(302, headers={"Location": "http://127.0.0.1/private"})
    client = OfficialHTTP(transport=httpx.MockTransport(redirect))
    with pytest.raises(ApiError) as error:
        asyncio.run(client.json("GET", "https://api.exa.ai/search"))
    assert error.value.code == "retrieval_redirect_blocked" and len(calls) == 1
    body = gzip.compress(b"A" * 100000)
    client = OfficialHTTP(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=body, headers={"Content-Encoding": "gzip"})))
    with pytest.raises(ApiError) as size:
        asyncio.run(client.request("GET", "https://api.exa.ai/search", max_bytes=4096))
    assert size.value.code == "retrieval_size_limit"
    client = OfficialHTTP(transport=httpx.MockTransport(lambda request: httpx.Response(401, json={"credential": "SYNTHETIC_SECRET_BODY"})))
    with pytest.raises(ApiError) as auth:
        asyncio.run(client.json("GET", "https://api.exa.ai/search"))
    assert auth.value.code == "retrieval_authentication_required" and "SYNTHETIC_SECRET_BODY" not in str(auth.value)


def test_slow_source_has_total_deadline_and_cancellation(monkeypatch):
    from renulus.retrieval import http
    completed = []
    async def slow(request):
        await asyncio.sleep(1)
        completed.append(True)
        return httpx.Response(200, json={})
    monkeypatch.setattr(http, "TOTAL_SECONDS", 0.02)
    client = OfficialHTTP(transport=httpx.MockTransport(slow))
    with pytest.raises(ApiError) as error:
        asyncio.run(client.json("GET", "https://api.exa.ai/search"))
    assert error.value.code == "retrieval_unavailable" and error.value.retryable is True and completed == []


def test_actual_core_router_validation_redacts_extra_case_payloads_and_secrets(services, monkeypatch):
    from renulus.retrieval import api as retrieval_api
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=europe())
    # Inject before the production module registrar captures its service. Adding
    # a duplicate router after create_app leaves the original route first.
    monkeypatch.setattr(retrieval_api, "RetrievalService", lambda actual: RetrievalService(
        actual, transport=httpx.MockTransport(handler), protector=SyntheticProtector()))
    app = create_app(services.paths.root, token="SYNTHETIC_SESSION", source_root=ROOT)
    actual = app.state.services
    service = actual.registry["retrieval"]
    client = TestClient(app, headers={"x-renulus-token": "SYNTHETIC_SESSION"})
    for field in ("query", "question", "case_text", "url"):
        response = client.post("/api/v1/retrieval/discover", json={"topic_id": "T21", "scope": {"kind": "study"}, field: "PRIVATE_SYNTHETIC_SENTINEL"})
        assert response.status_code == 422 and response.json()["error"]["code"] == "invalid_request"
        assert "PRIVATE_SYNTHETIC" not in response.text and calls == []
    response = client.put("/api/v1/retrieval/connections/tavily", json={"api_key": "SYNTHETIC_EXPLICIT_KEY", "enabled": False})
    assert response.status_code == 200 and "SYNTHETIC_EXPLICIT_KEY" not in response.text and calls == []
    assert response.json()["selected_tool"] is None
    configured = next(row for row in response.json()["connections"] if row["provider"] == "tavily")
    assert configured["configured"] is True and configured["auth_status"] == "not_checked"
    response = client.post("/api/v1/retrieval/connections/select", json={"provider": "tavily"})
    assert response.status_code == 409 and calls == []
    for kind in ("temporary-case", "saved-case", "unclassified"):
        response = client.post("/api/v1/retrieval/discover", json={"topic_id": "T21", "scope": {"kind": kind, "entity_id": "PRIVATE_SYNTHETIC"}})
        assert response.status_code == 403 and response.json()["error"]["code"] == "retrieval_scope_blocked" and calls == []
    response = client.post("/api/v1/retrieval/discover", json={"topic_id": "T21", "scope": {"kind": "study"}})
    assert response.status_code == 200 and len(calls) == 1
    assert response.json()["topic_label"] == service.topic("T21")["label"]
    assert client.get("/api/v1/retrieval/connections", headers={"x-renulus-token": "wrong"}).status_code == 401


@pytest.mark.parametrize("provider,payload", [("europe-pmc", {"resultList": {"result": "invalid"}}), ("pubmed", {"esearchresult": "invalid"}), ("brave", {}), ("tavily", {"results": [{}]}), ("exa", {"results": None})])
def test_bad_source_schemas_never_invent_success_or_leak_body(services, provider, payload):
    service = RetrievalService(services, transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload)), protector=SyntheticProtector())
    async def run():
        if provider in ("brave", "tavily", "exa"):
            await service.configure(provider, api_key="SYNTHETIC_KEY", enabled=True)
            await service.select(provider)
        with pytest.raises(ApiError) as error:
            await service.discover("T21", scope={"kind": "study"}, provider=provider)
        assert error.value.code == "retrieval_invalid_response"
    asyncio.run(run())
    row = next(row for row in service.status()["connections"] if row["provider"] == provider)
    assert row["auth_status"] == "retrieval_invalid_response" and not row.get("last_success_at")
