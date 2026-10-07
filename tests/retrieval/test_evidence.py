"""Synthetic public source gateway and real read-only journal projection."""
import asyncio
import hashlib
import json
from pathlib import Path

import httpx
import pytest

from renulus.contracts import ApiError, ContextScope, Scope
from renulus.knowledge.repository import KnowledgeRepository
from renulus.knowledge.models import SourceMetadata, own_text_rights
from renulus.retrieval.service import RetrievalService
from .conftest import ROOT, SyntheticProtector
from .fixtures import PMCID, article, europe

STUDY = ContextScope(kind=Scope.STUDY)


def setup(services, *, raw=None, changes=None, discovery=None):
    calls = []
    raw = article() if raw is None else raw
    def handler(request):
        calls.append(request)
        assert request.method == "GET" and request.url.host == "www.ebi.ac.uk"
        if request.url.path.endswith("/search"):
            if request.url.params["query"].startswith("PMCID:"):
                assert request.url.params["query"] == "PMCID:" + PMCID
            elif discovery is not None:
                return httpx.Response(200, json=discovery(request))
            return httpx.Response(200, json=europe(**(changes or {})))
        assert request.url.path.endswith("/" + PMCID + "/fullTextXML")
        return httpx.Response(200, content=raw)
    class Index:
        path = services.paths.indexes / "unused-evidence-index"
        def remove(self, *_):
            pytest.fail("Evidence must never mutate an index")
    knowledge = KnowledgeRepository(services, extractor=object(), embedder=object(), index=Index())
    services.registry["knowledge"] = knowledge
    services.db.apply_migration("knowledge-002", (ROOT / "runtime/renulus/knowledge/migrations/002-source-status.sql").read_text(encoding="utf-8"))
    gateway = RetrievalService(services, transport=httpx.MockTransport(handler), protector=SyntheticProtector())
    return gateway, knowledge, calls


def test_dated_body_passage_rights_and_jats_locus_without_library_import(services):
    raw = article(body='<fig><p>EXCLUDED_FIGURE</p></fig><p specific-use="third-party">EXCLUDED_THIRD_PARTY</p>')
    gateway, knowledge, calls = setup(services, raw=raw)
    gateway.connections.settings["selected_provider"] = "tavily"
    result = asyncio.run(gateway.evidence("T21", scope=STUDY))
    assert len(calls) == 3 and calls[0].url.params["query"] == 'TITLE_ABS:"Kidney transplantation" AND OPEN_ACCESS:y sort_date:y'
    assert calls[1].url.params["query"] == "PMCID:" + PMCID
    passage = result["passages"][0]
    assert passage["text"] == "Kidney study paragraph with synthetic observations."
    assert passage["locators"] == [{"kind": "jats", "item_id": "/article/body/sec[1]/p[1]",
        "section": "Results", "char_start": 0, "char_end": len(passage["text"])}]
    assert passage["publication_date"] == "2026-09-01" and passage["retrieved_at"]
    assert passage["metadata"]["original_sha256"] == hashlib.sha256(raw).hexdigest()
    assert passage["canonical_url"] == "https://europepmc.org/articles/" + PMCID
    assert passage["verification"] == result["verification"] == "dated-research"
    assert passage["latest_final_verified"] is passage["metadata"]["content_reviewed"] is False
    for operation in ("display", "cache", "model_input", "derivation"):
        assert passage["rights"][operation] is True
    for operation in ("index", "embedding", "evaluation", "redistribution"):
        assert passage["rights"][operation] is False
    assert "Synthetic Author" in passage["rights"]["attribution"]
    assert services.db.fetch_all("SELECT * FROM retrieval_imports") == []
    assert services.db.fetch_all("SELECT * FROM knowledge_documents") == []
    assert services.db.fetch_all("SELECT * FROM knowledge_passages") == []
    assert knowledge.check_evidence(result["passages"], scope=STUDY, current_only=True)["eligible_ids"] == []


@pytest.mark.parametrize("topic_id", ["T10", "T21"])
def test_oa_date_query_finds_body_when_general_discovery_has_no_eligible_rows(services, topic_id, monkeypatch):
    label = next(row["label"] for row in services.registry["content"].list_topics() if row["id"] == topic_id)
    general_query = 'TITLE_ABS:"' + label + '"'
    evidence_query = general_query + " AND OPEN_ACCESS:y sort_date:y"
    ineligible = [europe(id=str(20001 + i), pmcid=None, isOpenAccess="N")["resultList"]["result"][0]
                  for i in range(5)]
    eligible = europe()["resultList"]["result"] + [
        europe(id="20002", pmcid="PMC20002", firstPublicationDate="2025-09-01")["resultList"]["result"][0]]
    def discovery(request):
        assert dict(request.url.params) == {"query": request.url.params["query"],
            "format": "json", "resultType": "core", "pageSize": "5"}
        assert request.url.params["query"] in (general_query, evidence_query)
        rows = eligible if request.url.params["query"] == evidence_query else ineligible
        return {"hitCount": len(rows), "resultList": {"result": rows}}
    monkeypatch.setenv("TAVILY_API_KEY", "AMBIENT_SYNTHETIC_KEY")
    gateway, _, calls = setup(services, discovery=discovery)
    private_scope = ContextScope(kind=Scope.STUDY, entity_id="PRIVATE_SYNTHETIC_QUESTION_AND_CASE")
    async def run():
        await gateway.configure("tavily", api_key="EXPLICIT_SYNTHETIC_KEY", enabled=True)
        await gateway.select("tavily")
        general = await gateway.discover(topic_id, scope=private_scope)
        assert len(general["records"]) == 5
        assert all(not row["open_access"] and not row["pmcid"] for row in general["records"])
        assert len(calls) == 1 and calls[0].url.params["query"] == general_query
        calls.clear()
        return await gateway.evidence(topic_id, scope=private_scope)
    result = asyncio.run(run())
    assert len(calls) == 3
    assert calls[0].url.params["query"] == evidence_query
    assert calls[1].url.params["query"] == "PMCID:" + PMCID
    assert calls[2].url.path.endswith("/" + PMCID + "/fullTextXML")
    outgoing = " ".join(str(call.url) + str(call.headers) + call.content.decode() for call in calls)
    assert all(value not in outgoing for value in ("PRIVATE_SYNTHETIC", "AMBIENT_SYNTHETIC", "EXPLICIT_SYNTHETIC"))
    assert result["passages"][0]["text"] == "Kidney study paragraph with synthetic observations."
    assert result["passages"][0]["metadata"]["topic_ids"] == [topic_id]
    assert result["verification"] == "dated-research" and result["latest_final_verified"] is False
    assert services.db.fetch_all("SELECT provider,requests,credits FROM retrieval_usage") == [
        {"provider": "europe-pmc", "requests": 4, "credits": 0}]
    for table in ("retrieval_imports", "knowledge_documents", "knowledge_revisions", "knowledge_passages"):
        assert services.db.fetch_all("SELECT * FROM " + table) == []


@pytest.mark.parametrize("count", [0, 5, 6])
def test_filtered_search_stops_without_eligible_rows_in_first_five(services, count):
    rows = [europe(id=str(20001 + i), pmcid=None, isOpenAccess="N")["resultList"]["result"][0]
            for i in range(min(count, 5))]
    if count == 6:
        rows += europe()["resultList"]["result"]
    gateway, _, calls = setup(services, discovery=lambda _: {"hitCount": count, "resultList": {"result": rows}})
    with pytest.raises(ApiError) as error:
        asyncio.run(gateway.evidence("T10", scope=STUDY))
    assert error.value.code == "no_eligible_public_evidence"
    assert len(calls) == 1 and calls[0].url.params["pageSize"] == "5"
    assert services.db.fetch_all("SELECT requests,credits FROM retrieval_usage") == [{"requests": 1, "credits": 0}]


@pytest.mark.parametrize("scope", [Scope.TEMPORARY_CASE, Scope.SAVED_CASE, Scope.UNCLASSIFIED, Scope.LIBRARY,
                                  Scope.REVIEWED_ASSESSMENT, Scope.GENERATED_PRACTICE])
def test_automatic_evidence_scope_denial_precedes_requests_and_writes(services, scope):
    gateway, _, calls = setup(services)
    before = {str(path): path.read_bytes() for path in services.paths.root.rglob("*") if path.is_file()}
    with pytest.raises(ApiError):
        asyncio.run(gateway.evidence("T21", scope=ContextScope(kind=scope)))
    assert calls == [] and services.db.fetch_all("SELECT * FROM retrieval_usage") == []
    assert before == {str(path): path.read_bytes() for path in services.paths.root.rglob("*") if path.is_file()}


@pytest.mark.parametrize("changes,raw,code,requests", [
    ({"license": "cc by-nc"}, None, "article_permission_required", 2),
    ({"isRetracted": "Y"}, None, "no_eligible_public_evidence", 1),
    ({}, article(licence="https://creativecommons.org/licenses/by-nc/4.0/"), "article_permission_required", 3),
    ({}, article().replace(b"<year>2026</year>", b"<year>unknown</year>"), "article_date_required", 3),
    ({}, article().replace(b"<body>", b"<no-body>").replace(b"</body>", b"</no-body>"), "article_text_unavailable", 3),
    ({"commentCorrectionList": {"commentCorrection": [{"type": "Erratum in", "source": "MED", "id": "10002"}]}}, None, "article_review_required", 3),
    ({"pubTypeList": {"pubType": ["Preprint"]}}, None, "article_review_required", 3),
    ({}, article(article_type="preprint"), "article_review_required", 3),
])
def test_automatic_fulltext_denial_is_explicit_without_import(services, changes, raw, code, requests):
    gateway, _, calls = setup(services, changes=changes, raw=raw)
    with pytest.raises(ApiError) as error:
        asyncio.run(gateway.evidence("T21", scope=STUDY))
    assert error.value.code == code and len(calls) == requests
    assert services.db.fetch_all("SELECT * FROM retrieval_imports") == []
    assert services.db.fetch_all("SELECT * FROM knowledge_documents") == []


@pytest.mark.parametrize("changes,raw,code,requests", [
    ({"license": "cc by-nc"}, None, "article_permission_required", 2),
    ({"isOpenAccess": "N"}, None, "article_permission_required", 2),
    ({"isRetracted": "Y"}, None, "article_retracted", 2),
    ({"pmcid": "PMC20002"}, None, "article_identity_mismatch", 2),
    ({}, article(licence="https://creativecommons.org/licenses/by-nc/4.0/"), "article_permission_required", 3),
    ({}, article(pmcid="PMC20002"), "article_identity_mismatch", 3),
    ({}, article().replace(b"10.0000/synthetic", b"10.0000/other"), "article_identity_mismatch", 3),
    ({"commentCorrectionList": {"commentCorrection": [{"type": "Erratum in", "source": "MED", "id": "10002"}]}}, None, "article_review_required", 3),
])
def test_selected_candidate_checks_metadata_and_xml_without_trying_alternates(services, changes, raw, code, requests):
    rows = europe()["resultList"]["result"] + europe(id="20002", pmcid="PMC20002")["resultList"]["result"]
    gateway, _, calls = setup(services, raw=raw, changes=changes,
        discovery=lambda _: {"hitCount": 2, "resultList": {"result": rows}})
    with pytest.raises(ApiError) as error:
        asyncio.run(gateway.evidence("T10", scope=STUDY))
    assert error.value.code == code and len(calls) == requests
    assert calls[1].url.params["query"] == "PMCID:" + PMCID
    assert sum(call.url.path.endswith("/fullTextXML") for call in calls) == requests - 2
    assert services.db.fetch_all("SELECT requests,credits FROM retrieval_usage") == [{"requests": requests, "credits": 0}]
    for table in ("retrieval_imports", "knowledge_documents", "knowledge_revisions", "knowledge_passages"):
        assert services.db.fetch_all("SELECT * FROM " + table) == []


@pytest.mark.parametrize("restriction", ["none", "not-current", "inactive", "not-ready", "excluded-page",
    "display", "cache", "model_input", "derivation", "correction", "retracted", "superseded", "reserved"])
def test_read_only_local_projection_rechecks_revision_permissions_currency_and_pages(services, restriction):
    _, knowledge, _ = setup(services)
    metadata = SourceMetadata(publication_status="final", latest_final_verified=True, content_reviewed=True,
        topic_ids=["T21"]).model_dump()
    rights = own_text_rights().model_dump()
    if restriction in ("display", "cache", "model_input", "derivation"):
        rights[restriction] = False
    if restriction == "not-current":
        metadata["latest_final_verified"] = False
    if restriction == "excluded-page":
        metadata["excluded_pages"] = [1]
    if restriction == "correction":
        metadata.update(correction="Synthetic unreviewed corrected copy", content_reviewed=False)
    if restriction in ("retracted", "superseded"):
        metadata[restriction] = True
    services.db.execute("INSERT INTO knowledge_documents VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        ("synthetic-doc", "Synthetic source", "R02", "personal-library", None, int(restriction == "reserved"),
         None if restriction == "inactive" else "synthetic-rev", "synthetic-rev", None, "2026-10-06", "2026-10-06"))
    services.db.execute("INSERT INTO knowledge_revisions(id,document_id,ordinal,status,sha256,media_type,bytes,metadata_json,rights_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
        ("synthetic-rev", "synthetic-doc", 1, "failed" if restriction == "not-ready" else "ready", "a" * 64,
         "text/plain", 1, json.dumps(metadata), json.dumps(rights), "2026-10-06"))
    services.db.execute("INSERT INTO knowledge_passages VALUES(?,?,?,?,?,?,?)",
        ("synthetic-passage", "synthetic-rev", 0, "Synthetic paragraph", "Synthetic paragraph", '[{"page":1}]', "[]"))
    references = [{"id": "synthetic-passage", "document_id": "synthetic-doc", "document_revision": "synthetic-rev"}]
    tables = ("knowledge_documents", "knowledge_revisions", "knowledge_passages", "knowledge_source_status_events")
    before = {table: services.db.fetch_all("SELECT * FROM " + table) for table in tables}
    checked = knowledge.check_evidence(references, scope=STUDY, topic_id="T21", current_only=True)
    assert checked["eligible_ids"] == (["synthetic-passage"] if restriction == "none" else [])
    assert before == {table: services.db.fetch_all("SELECT * FROM " + table) for table in tables}


@pytest.mark.parametrize("changes", [{"retracted": True}, {"superseded": True},
    {"publication_status": "draft"}, {"correction": "Synthetic correction; bytes not yet reviewed"}])
def test_read_only_projection_obeys_reviewed_journal_without_changing_records(services, changes):
    gateway, knowledge, _ = setup(services)
    citations = asyncio.run(gateway.evidence("T21", scope=STUDY))["passages"]
    # The event is synthetic inspected evidence, not a forged live publisher claim.
    knowledge.update_source_status({"contract_version": 1, "event_id": "synthetic-evidence-restriction",
        "source_id": "L03", "identity": {"doi": "10.0000/synthetic"}, "changes": changes,
        "evidence": {"kind": "reviewed-publication", "reviewer": "learner", "reviewed_at": "2026-10-06T00:00:00+00:00",
            "references": [{"url": "https://europepmc.org/articles/PMC10001", "locator": "Synthetic notice",
                "finding": "Synthetic reviewed source restriction", "checked_on": "2026-10-06", "inspected": True}]}})
    before = services.db.fetch_all("SELECT * FROM knowledge_source_status_events")
    assert knowledge.check_evidence(citations, scope=STUDY)["eligible_ids"] == []
    assert services.db.fetch_all("SELECT * FROM knowledge_source_status_events") == before
    assert services.db.fetch_all("SELECT * FROM knowledge_documents") == []
