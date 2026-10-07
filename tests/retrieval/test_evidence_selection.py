"""Bounded selection through the real gateway; no engines, providers or imports."""
import asyncio
import hashlib
import json
import os
from pathlib import Path

import httpx
import pytest

from renulus.contracts import ApiError
from renulus.retrieval.literature import licensed_article
from .fixtures import PMCID, article, europe
from .test_evidence import STUDY, setup


def candidate(number, **changes):
    return europe(id=str(number), pmid=str(number), pmcid="PMC" + str(number), **changes)["resultList"]["result"][0]


def body(number, **changes):
    return article(pmcid="PMC" + str(number), **changes).replace(
        b'pub-id-type="pmid">10001', f'pub-id-type="pmid">{number}'.encode())


def gateway_for(services, rows, *, metadata=None, bodies=None, fail=None):
    gateway, knowledge, _ = setup(services)
    calls = []
    async def handler(request):
        calls.append(request)
        assert request.method == "GET" and request.url.host == "www.ebi.ac.uk"
        assert "authorization" not in request.headers
        query = request.url.params.get("query", "")
        if query.startswith("TITLE_ABS:"):
            assert query.endswith(' AND OPEN_ACCESS:y sort_date:y')
            assert request.url.params["pageSize"] == "5"
            return httpx.Response(200, json={"resultList": {"result": rows}})
        if fail:
            response = await fail(request)
            if response is not None:
                return response
        if query.startswith("PMCID:"):
            pmcid = query.removeprefix("PMCID:")
            row = (metadata or {}).get(pmcid, next(row for row in rows if row["pmcid"] == pmcid))
            return httpx.Response(200, json={"resultList": {"result": [row]}})
        pmcid = request.url.path.split("/")[-2]
        assert request.url.path.endswith("/fullTextXML")
        raw = (bodies or {}).get(pmcid, body(int(pmcid[3:])))
        return httpx.Response(200, content=raw)
    gateway.http.transport = httpx.MockTransport(handler)
    return gateway, knowledge, calls


def assert_no_imports(services, calls):
    for table in ("retrieval_imports", "knowledge_documents", "knowledge_revisions", "knowledge_passages"):
        assert services.db.fetch_all("SELECT * FROM " + table) == []
    assert services.db.fetch_all("SELECT provider,requests,credits FROM retrieval_usage") == [
        {"provider": "europe-pmc", "requests": len(calls), "credits": 0}]


@pytest.mark.parametrize("licence", [None, "cc by-nc", "cc by-sa", "cc", ["cc by"]])
def test_metadata_rejection_skips_body_but_eligible_candidate_still_crosses_gateway(services, licence):
    rows = [candidate(10001, license=licence), candidate(10002), candidate(10003)]
    gateway, _, calls = gateway_for(services, rows)
    result = asyncio.run(gateway.evidence("T10", scope=STUDY))
    assert len(calls) == 3 and calls[1].url.params["query"] == "PMCID:PMC10002"
    receipt = result["acquisition"]
    assert receipt["selected_pmcid"] == "PMC10002" and len(receipt["checks"]) == 2
    assert receipt["checks"][0]["code"] == "article_permission_required"
    assert receipt["checks"][0]["stage"] == "discovery-metadata"
    assert result["discovery"]["records"][1]["fulltext_licence"] == "unverified"
    assert "PMC10001" in receipt["disclosure"] and "skipped" in receipt["disclosure"]
    assert receipt["disclosure"] in result["passages"][0]["rights"]["attribution"]
    assert receipt["disclosure"] in result["passages"][0]["metadata"]["notes"]
    assert_no_imports(services, calls)


@pytest.mark.parametrize("denial,expected_requests", [
    ("metadata-licence", 4), ("metadata-oa", 4), ("metadata-retracted", 4),
    ("xml-licence", 5), ("xml-exclusion", 5), ("xml-attribution", 5),
    ("date", 5), ("future-date", 5), ("body", 5), ("preliminary", 5),
    ("notice", 5), ("journal", 5), ("unavailable", 4),
])
def test_ineligible_first_body_does_not_hide_next_eligible_dated_body(services, denial, expected_requests):
    rows = [candidate(10001), candidate(10002), candidate(10003)]
    first_metadata = dict(rows[0])
    raw = article()
    if denial == "metadata-licence":
        first_metadata["license"] = "cc by-nc"
    if denial == "metadata-oa":
        first_metadata["isOpenAccess"] = "N"
    if denial == "metadata-retracted":
        first_metadata["isRetracted"] = "Y"
    if denial == "xml-licence":
        raw = article(licence="https://creativecommons.org/licenses/by-nc/4.0/")
    if denial == "xml-exclusion":
        raw = article(statement="Third-party material excluded. ")
    if denial == "xml-attribution":
        raw = raw.replace(b"<contrib-group>", b"<no-contrib>").replace(b"</contrib-group>", b"</no-contrib>")
        raw = raw.replace(b"copyright-statement", b"no-credit").replace(b"copyright-holder", b"no-holder")
    if denial in ("date", "future-date"):
        raw = raw.replace(b"<year>2026</year>", b"<year>unknown</year>" if denial == "date" else b"<year>9999</year>")
    if denial == "body":
        raw = raw.replace(b"<body>", b"<no-body>").replace(b"</body>", b"</no-body>")
    if denial == "preliminary":
        raw = article(article_type="preprint")
    if denial == "notice":
        first_metadata["commentCorrectionList"] = {"commentCorrection": [{"type": "Erratum in", "id": "10099", "source": "MED"}]}
    async def fail(request):
        if denial == "unavailable" and request.url.params.get("query") == "PMCID:" + PMCID:
            return httpx.Response(404)
    gateway, knowledge, calls = gateway_for(services, rows, metadata={PMCID: first_metadata}, bodies={PMCID: raw}, fail=fail)
    if denial == "journal":
        original_check = knowledge.check_evidence
        def restricted(passages, **kwargs):
            result = original_check(passages, **kwargs)
            if passages[0]["metadata"]["pmcid"] == PMCID:
                result["eligible_ids"] = []
            return result
        knowledge.check_evidence = restricted
    result = asyncio.run(gateway.evidence("T21", scope=STUDY))
    assert len(calls) == expected_requests
    assert result["acquisition"]["selected_pmcid"] == "PMC10002"
    assert [row["outcome"] for row in result["acquisition"]["checks"]] == ["skipped", "selected"]
    passage = result["passages"][0]
    assert passage["publication_date"] == "2026-09-01" and passage["retrieved_at"]
    assert passage["metadata"]["pmcid"] == "PMC10002"
    assert passage["locators"][0]["item_id"] == "/article/body/sec[1]/p[1]"
    assert passage["metadata"]["original_sha256"] == hashlib.sha256(body(10002)).hexdigest()
    assert passage["latest_final_verified"] is result["latest_final_verified"] is False
    assert passage["metadata"]["content_reviewed"] is False
    assert all(not passage["rights"][operation] for operation in ("index", "embedding", "evaluation", "redistribution"))
    assert services.db.fetch_one("SELECT error_code FROM retrieval_health WHERE provider='europe-pmc'")["error_code"] is None
    assert_no_imports(services, calls)


def test_five_denials_are_exhausted_once_and_sixth_candidate_is_never_requested(services):
    rows = [candidate(10001 + i) for i in range(6)]
    bodies = {row["pmcid"]: body(int(row["pmid"]), statement="Third-party material excluded. ") for row in rows[:5]}
    gateway, _, calls = gateway_for(services, rows, bodies=bodies)
    with pytest.raises(ApiError) as error:
        asyncio.run(gateway.evidence("T10", scope=STUDY))
    receipt = error.value.acquisition
    assert error.value.code == "article_permission_required"
    assert len(calls) == 11 and len(receipt["checks"]) == 5
    assert receipt["records_received"] == receipt["max_candidates"] == 5
    assert receipt["selected_pmcid"] is None
    assert all(row["code"] == "article_permission_required" for row in receipt["checks"])
    assert "No public body passage acquired" in error.value.message
    assert "PMC10006" not in str(calls)
    assert_no_imports(services, calls)


def test_duplicate_denied_candidate_is_not_requested_twice(services):
    rows = [candidate(10001), candidate(10001), candidate(10002)]
    gateway, _, calls = gateway_for(services, rows, bodies={PMCID: article(statement="Third-party material excluded.")})
    result = asyncio.run(gateway.evidence("T10", scope=STUDY))
    assert len(calls) == 5
    assert result["acquisition"]["checks"][1]["code"] == "duplicate_candidate"
    assert result["acquisition"]["selected_pmcid"] == "PMC10002"
    assert_no_imports(services, calls)


@pytest.mark.parametrize("failure,code,requests", [
    ("transport", "retrieval_unavailable", 2), ("rate", "retrieval_provider_limit", 2),
    ("auth", "retrieval_authentication_required", 2), ("redirect", "retrieval_redirect_blocked", 2),
    ("metadata", "retrieval_invalid_response", 2), ("xml", "article_xml_invalid", 3),
    ("budget", "retrieval_daily_limit", 1),
])
def test_non_article_failure_stops_selection_immediately(services, failure, code, requests):
    async def fail(request):
        if failure == "transport":
            raise httpx.ConnectError("synthetic unavailable", request=request)
        if failure in ("rate", "auth", "redirect"):
            return httpx.Response({"rate": 429, "auth": 403, "redirect": 302}[failure])
        if failure == "metadata":
            return httpx.Response(200, json={"resultList": {"result": "malformed"}})
    gateway, _, calls = gateway_for(services, [candidate(10001), candidate(10002)],
        bodies={PMCID: b'<!DOCTYPE article [<!ENTITY x "unsafe">]><article>&x;</article>'} if failure == "xml" else None, fail=fail)
    if failure == "budget":
        reserve = gateway._reserve
        def limited(provider, requests, credits):
            if calls:
                raise ApiError("retrieval_daily_limit", "Synthetic cap reached.", 429)
            return reserve(provider, requests, credits)
        gateway._reserve = limited
    with pytest.raises(ApiError) as error:
        asyncio.run(gateway.evidence("T10", scope=STUDY))
    assert error.value.code == code and len(calls) == requests
    assert len(error.value.acquisition["checks"]) == 1
    assert error.value.acquisition["checks"][0]["outcome"] == "failed"
    assert "No public body passage acquired" in error.value.message
    assert_no_imports(services, calls)


@pytest.mark.parametrize("stage", ["metadata", "body", "between-candidates"])
def test_cancellation_never_starts_another_candidate(services, stage):
    async def fail(request):
        is_metadata = request.url.path.endswith("/search")
        if (stage == "metadata" and is_metadata) or (stage == "body" and not is_metadata):
            raise asyncio.CancelledError()
    gateway, _, calls = gateway_for(services, [candidate(10001), candidate(10002)],
        bodies={PMCID: article(statement="Third-party material excluded.")}, fail=fail)
    if stage == "between-candidates":
        fetch = gateway.fetch_article
        async def cancel_after_denial(pmcid):
            try:
                return await fetch(pmcid)
            except ApiError:
                asyncio.get_running_loop().call_soon(asyncio.current_task().cancel)
                raise
        gateway.fetch_article = cancel_after_denial
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(gateway.evidence("T10", scope=STUDY))
    assert len(calls) == (2 if stage == "metadata" else 3)
    assert all("PMC10002" not in str(call.url) for call in calls)
    assert_no_imports(services, calls)


def test_recovered_public_body_replay_with_exact_primary_metadata(services):
    """Opt-in local receipt replay; synthetic ranking, no claim of live discovery."""
    evidence = os.environ.get("RENULUS_EVIDENCE_SELECTION_RECEIPTS")
    if not evidence:
        pytest.skip("Recovered public receipts are deliberately outside Git")
    root = Path(evidence)
    raw = (root.parent / "mgrs/sfag163-europepmc.xml").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "d405af8506f148513c3586d81933b0b74105b79ec76a08cfced2a7713e69c980"
    metadata_raw = (root / "recovered-mgrs-metadata.json").read_bytes()
    assert hashlib.sha256(metadata_raw).hexdigest() == "c781604ac32f57dd210a37c501c81dafc334f99313bc49db931d356b8c8ffa1a"
    row = json.loads(metadata_raw)["resultList"]["result"][0]
    gateway, _, calls = gateway_for(services, [candidate(10001, license="cc by-nc"), row], bodies={row["pmcid"]: raw})
    result = asyncio.run(gateway.evidence("T10", scope=STUDY))
    assert len(calls) == 3 and result["acquisition"]["selected_pmcid"] == "PMC13284707"
    assert result["passages"][0]["metadata"]["doi"] == "10.1093/ckj/sfag163"
    assert result["passages"][0]["metadata"]["original_sha256"] == hashlib.sha256(raw).hexdigest()
    assert result["passages"][0]["text"] and result["passages"][0]["publication_date"]
    # Retained OA articles with NC/ND terms still fail the unmodified JATS gate.
    for name, pmcid, expected_hash in [
        ("bk.xml", "PMC11335089", "a193a7d1749e107fecc986f15454700fb0b480c8f1e1e3605aa43fc9213a89ef"),
        ("di_xml.xml", "PMC6013691", "0295afdd0ac89d8e1a2a0d656f66da6286b18816ce8956357d5c03f180ba4025"),
    ]:
        denied = (root.parent / "content/primary" / name).read_bytes()
        assert hashlib.sha256(denied).hexdigest() == expected_hash
        with pytest.raises(ApiError) as error:
            licensed_article(denied, pmcid)
        assert error.value.code == "article_permission_required"
    assert_no_imports(services, calls)
    (root / "recovered-replay.json").write_text(json.dumps({
        "ranking": "synthetic", "live_body_reads": 0, "acquisition": result["acquisition"],
        "passages": [{key: value[key] for key in ("canonical_url", "publication_date", "retrieved_at", "locators", "verification", "latest_final_verified")} for value in result["passages"]],
        "body_sha256": hashlib.sha256(raw).hexdigest(), "library_imports": 0,
    }, indent=2) + "\n", encoding="utf-8")
