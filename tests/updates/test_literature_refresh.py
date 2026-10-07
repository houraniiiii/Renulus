from datetime import date
import json
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient
import pytest

from renulus.server import create_app
from test_updates import SequenceFetcher, SYNTHETIC_EVIDENCE
from test_publications import insert_entries


ARTICLE = {"id": "111111", "source": "MED", "doi": "10.5555/synthetic-original",
           "title": "Synthetic old publication, not real research", "firstPublicationDate": "2010-01-01",
           "pubTypeList": {"pubType": ["Journal Article"]}, "isOpenAccess": "Y"}


def result(*articles, hits=None):
    return json.dumps({"hitCount": len(articles) if hits is None else hits,
                       "resultList": {"result": list(articles)}}).encode()


@pytest.fixture
def check_date(monkeypatch):
    class CheckDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 10, 7)
    monkeypatch.setattr("renulus.updates.literature.date", CheckDate)


@pytest.mark.asyncio
async def test_t21_query_scopes_recorded_unrelated_results_and_deduplicates(tmp_path, check_date):
    service = create_app(tmp_path).state.services.registry["updates"]
    # Titles from the parent's 035098b4 T21 UI receipt (updates-visible),
    # connected/connected-source-02/result.json. IDs are synthetic; no bodies
    # or live response are copied. This is a request-contract replay, not a
    # Europe PMC parser or proof of the corrected live result set.
    unrelated_titles = [
        "Codonopsis pilosula inulin-type fructan CPA ameliorates diarrhea-predominant "
        "irritable bowel syndrome via regulation of ER stress-induced autophagy and "
        "modulation of gut microbiota",
        "From molecular correction to functional rescue: delivery, tissue state, and "
        "immunobiology as the principal constraints on dystrophin-restoring therapy "
        "in Duchenne muscular dystrophy",
        "GULP1 Fuels Resistance to PD-1 Blockade through Lipid-Mediated Metabolic "
        "Reprogramming of Tumor-Associated Macrophages in Gastric Cancer",
    ]
    unrelated = [{"id": str(900001 + index), "source": "MED", "title": title}
                 for index, title in enumerate(unrelated_titles)]
    title_match = {"id": "900004", "source": "MED",
                   "title": "Synthetic kidney transplantation follow-up",
                   "firstPublicationDate": "2026-10-07"}
    abstract_match = {"id": "900005", "source": "MED",
                      "title": "Synthetic graft follow-up",
                      "firstPublicationDate": "2026-10-06",
                      "abstractText": "SYNTHETIC_ABSTRACT_ONLY kidney transplantation",
                      "fullText": "SYNTHETIC_BODY_MUST_NOT_PERSIST"}
    scoped_query = ('TITLE_ABS:"Kidney transplantation" AND '
                    'FIRST_PDATE:[2026-09-07 TO 2026-10-07] sort_date:y')
    legacy_query = '(Kidney transplantation) FIRST_PDATE:[2026-09-07 TO 2026-10-07]'

    class QueryReplay:
        def __init__(self):
            self.requests = []

        async def fetch(self, url, hosts, limit=2_000_000):
            parsed = urlparse(url)
            assert parsed.scheme == "https" and parsed.netloc == "www.ebi.ac.uk"
            assert parsed.path == "/europepmc/webservices/rest/search"
            assert hosts == {"www.ebi.ac.uk"} and limit == 2_000_000
            params = parse_qs(parsed.query)
            self.requests.append(params)
            responses = {legacy_query: result(*unrelated),
                         scoped_query: result(title_match, abstract_match, hits=40)}
            return responses[params["query"][0]], {"content-type": "application/json"}, url

    service.fetcher = QueryReplay()
    first = await service.check_literature(["T21", "T21"], days=30)
    entries = service.list_entries()
    assert {entry["external_id"] for entry in entries} == {"epmc:MED:900004", "epmc:MED:900005"}
    assert first["state"] == "checked" and first["discovered"] == 2
    assert first["checks"] == [{"topic_id": "T21", "state": "checked", "discovered": 2,
                                "records_checked": 2, "hit_count": 40, "truncated": True}]
    assert (await service.check_literature(["T21"], days=30))["discovered"] == 0
    assert service.fetcher.requests == [{"query": [scoped_query], "format": ["json"],
                                        "resultType": ["core"], "pageSize": ["25"]}] * 2
    assert len(service.list_entries()) == 2 and service.list_entries(reviewed_only=True) == []
    for entry in entries:
        assert entry["topic_ids"] == ["T21"] and entry["review_state"] == "pending"
        assert entry["source_metadata"]["reported_publication_status"] == "unknown"
    with service.db.connect() as conn:
        dump = "\n".join(conn.iterdump())
    assert "SYNTHETIC_ABSTRACT_ONLY" not in dump
    assert "SYNTHETIC_BODY_MUST_NOT_PERSIST" not in dump


@pytest.mark.asyncio
@pytest.mark.parametrize(("label", "phrase"), [
    ("chronic kidney disease", '"chronic kidney disease"'),
    ('Kidney "graft" follow-up', r'"Kidney \"graft\" follow-up"'),
    ('Tubular\\interstitial\\', r'"Tubular\\interstitial\\"'),
    ('Kidney\\" OR *:* OR TITLE_ABS:"cancer', r'"Kidney\\\" OR *:* OR TITLE_ABS:\"cancer"'),
    ('IgA & complement (C3): α/β + follow-up?', '"IgA & complement (C3): α/β + follow-up?"'),
])
async def test_canonical_topic_phrase_escaping_and_url_round_trip(tmp_path, check_date, label, phrase):
    service = create_app(tmp_path).state.services.registry["updates"]
    class Topics:
        def list_topics(self):
            return [{"id": "synthetic-topic", "title": label}]
    service.services.registry["content"] = Topics()
    service.fetcher = SequenceFetcher([result()])
    checked = await service.check_literature(["synthetic-topic"], days=7)
    assert checked["state"] == "checked" and checked["discovered"] == 0
    params = parse_qs(urlparse(service.fetcher.urls[0]).query)
    assert params == {"query": [f'TITLE_ABS:{phrase} AND FIRST_PDATE:[2026-09-30 TO 2026-10-07] sort_date:y'],
                      "format": ["json"], "resultType": ["core"], "pageSize": ["25"]}


@pytest.mark.asyncio
async def test_exact_refresh_older_than_100_retains_review_and_queues_changed_metadata(tmp_path):
    app = create_app(tmp_path)
    service = app.state.services.registry["updates"]
    original = service.literature.record(ARTICLE, ["T08"], "2010-01-02T00:00:00+00:00")
    old_id = original["entry_id"]
    service.review(old_id, "Synthetic prior review", ["T08"], "learner", "reviewed", evidence=SYNTHETIC_EVIDENCE)
    insert_entries(service, 251)
    assert old_id not in {row["id"] for row in service.list_entries()}
    changed = {**ARTICLE, "pubTypeList": {"pubType": ["Retracted Publication"]},
               "commentCorrectionList": {"commentCorrection": [{"id": "999999", "source": "MED", "type": "Retraction in"}]}}
    service.fetcher = SequenceFetcher([result(changed), result(changed), RuntimeError("offline"), result()])
    refreshed = await service.refresh_entry(old_id)
    assert refreshed["state"] == "changed"
    assert refreshed["entry"]["id"] == old_id and refreshed["entry"]["review_state"] == "reviewed"
    latest = refreshed["latest_entry"]
    assert latest["id"] != old_id and latest["review_state"] == "pending" and latest["kind"] == "retraction"
    assert latest["publication_date"] == "2010-01-01"
    assert service.affected.for_entry(latest["id"])["total"] == 0
    query = parse_qs(urlparse(service.fetcher.urls[0]).query)
    assert query["query"] == ["EXT_ID:111111 AND SRC:MED"]
    assert query["resultType"] == ["core"] and query["pageSize"] == ["1"]
    assert "sort" not in query
    assert "FIRST_PDATE" not in query["query"][0]
    assert (await service.refresh_entry(old_id))["state"] == "unchanged"
    prior = service.db.fetch_one("SELECT * FROM update_literature_records WHERE external_id='epmc:MED:111111'")
    failed = await service.refresh_entry(old_id)
    assert failed["state"] == "failed" and failed["entry"]["review_state"] == "reviewed"
    missing = await service.refresh_entry(old_id)
    assert missing["error"]["code"] == "literature_record_unavailable"
    current = service.db.fetch_one("SELECT * FROM update_literature_records WHERE external_id='epmc:MED:111111'")
    assert current["last_success_at"] == prior["last_success_at"]
    assert current["fingerprint"] == prior["fingerprint"]
    assert current["state"] == "failed"
    assert TestClient(app).get(f"/api/v1/updates/entries/{old_id}").json()["review_state"] == "reviewed"


@pytest.mark.asyncio
async def test_topic_checks_report_partial_failure_limits_and_no_case_egress(tmp_path, check_date):
    service = create_app(tmp_path).state.services.registry["updates"]
    class Topics:
        def list_topics(self):
            return [{"id": "ckd", "title": "chronic kidney disease"}, {"id": "dialysis", "title": "dialysis"}]
    service.services.registry["content"] = Topics()
    service.fetcher = SequenceFetcher([result(ARTICLE, hits=1000), RuntimeError("offline"), RuntimeError("offline")])
    with pytest.raises(Exception):
        await service.check_literature(["ckd", "SYNTHETIC_PATIENT_DETAILS"])
    assert not service.fetcher.urls
    checked = await service.check_literature(["ckd", "dialysis"])
    assert checked["state"] == "partial" and checked["discovered"] == 1
    assert checked["checks"][0]["truncated"] is True
    assert checked["checks"][0]["records_checked"] == 1
    assert checked["checks"][1]["state"] == "failed"
    assert [parse_qs(urlparse(url).query)["query"][0] for url in service.fetcher.urls] == [
        'TITLE_ABS:"chronic kidney disease" AND FIRST_PDATE:[2026-09-30 TO 2026-10-07] sort_date:y',
        'TITLE_ABS:"dialysis" AND FIRST_PDATE:[2026-09-30 TO 2026-10-07] sort_date:y',
    ]
    previous = next(row for row in service.literature.checks() if row["topic_id"] == "ckd")
    assert (await service.check_literature(["ckd"]))["state"] == "failed"
    current = next(row for row in service.literature.checks() if row["topic_id"] == "ckd")
    assert current["last_success_at"] == previous["last_success_at"]
    assert "SYNTHETIC_PATIENT_DETAILS" not in "".join(service.fetcher.urls)
    assert service.list_entries()[0]["source_metadata"]["reported_publication_status"] == "unknown"


@pytest.mark.asyncio
async def test_malformed_or_truncated_metadata_does_not_claim_no_results(tmp_path):
    service = create_app(tmp_path).state.services.registry["updates"]
    topic = service.services.registry["content"].list_topics()[0]["id"]
    service.fetcher = SequenceFetcher([b'{"error":"synthetic malformed result"}', result(*[ARTICLE] * 26)])
    for expected in ("literature_metadata_invalid", "literature_metadata_invalid"):
        checked = await service.check_literature([topic])
        assert checked["state"] == "failed" and checked["checks"][0]["error_code"] == expected
    assert service.list_entries() == []


@pytest.mark.asyncio
async def test_old_001_metadata_can_fail_refresh_without_advancing_success(tmp_path):
    service = create_app(tmp_path).state.services.registry["updates"]
    service.db.execute("INSERT INTO update_entries(id,source_id,external_id,title,url,kind,discovered_at,review_state,summary,source_metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?)",
        ("old", "L03", "epmc:MED:111111", "Synthetic old metadata", "https://europepmc.org/article/MED/111111",
         "research", "2010-01-01", "reviewed", "Synthetic dated review", json.dumps(ARTICLE)))
    service.fetcher = SequenceFetcher([RuntimeError("offline")])
    refreshed = await service.refresh_entry("old")
    assert refreshed["state"] == "failed" and refreshed["entry"]["review"] is None
    current = service.db.fetch_one("SELECT * FROM update_literature_records WHERE external_id='epmc:MED:111111'")
    assert current["state"] == "failed" and current["last_success_at"] is None
