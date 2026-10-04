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
async def test_topic_checks_report_partial_failure_limits_and_no_case_egress(tmp_path):
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
