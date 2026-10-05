"""Connected Updates acceptance: real HTTP/SQLite/LanceDB, synthetic publisher bodies.

Only the external publisher, extraction and embedding boundaries are controlled.
No real educational review, provider, patient text or acquired corpus is used.
"""
import hashlib
import json
import time

from fastapi.testclient import TestClient
import httpx

from renulus.contracts import ContextScope, Scope
from renulus.knowledge.models import SourceMetadata
from renulus.knowledge.repository import KnowledgeRepository
from renulus.server import create_app
from renulus.updates.fetch import SourceFetcher
from test_acquired_version_currency import SyntheticEmbedder, SyntheticExtractor


ARTICLES = {
    "T06": ("PMC900006", "Acute kidney injury"),
    "T08": ("PMC900008", "Chronic kidney disease"),
    "T21": ("PMC900021", "Kidney transplantation"),
}


def article_url(pmcid):
    return f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/"


class Publisher:
    def __init__(self):
        self.notices = 0
        self.article_revision = 0
        self.offline = False
        self.requests = []

    def respond(self, request):
        self.requests.append(request)
        if self.offline:
            return httpx.Response(503)
        if request.url.host == "www.ebi.ac.uk":
            query = request.url.params["query"]
            topic = next(key for key, (_, title) in ARTICLES.items() if title.lower() in query.lower())
            return httpx.Response(200, json={"hitCount": 1, "resultList": {"result": [{
                "id": str(900000 + int(topic[1:])), "source": "MED",
                "title": "Synthetic metadata for " + ARTICLES[topic][1],
                "firstPublicationDate": "2026-10-04", "pubType": "journal article",
                "abstractText": "SYNTHETIC_ABSTRACT_MUST_NOT_BE_RETAINED",
            }]}})
        if "/articles/" in request.url.path:
            return httpx.Response(200, text=f"<html>Synthetic public article bytes {self.article_revision}</html>",
                                  headers={"etag": "unchanged-synthetic-validator"})
        links = [f'<a href="{article_url(pmcid)}">Synthetic guideline {title}</a>'
                 for pmcid, title in ARTICLES.values()]
        links += [f'<a href="https://pmc.ncbi.nlm.nih.gov/synthetic-notice-{index}.pdf">Synthetic correction</a>'
                  for index in range(self.notices)]
        return httpx.Response(200, text="".join(links), headers={"set-cookie": "synthetic_session=discard-me"})


def application(profile, monkeypatch, publisher):
    monkeypatch.setattr("renulus.server.MODULE_ORDER", ("content", "knowledge", "updates"))
    monkeypatch.setattr("renulus.knowledge.api.KnowledgeRepository", lambda services:
        KnowledgeRepository(services, extractor=SyntheticExtractor(), embedder=SyntheticEmbedder()))
    app = create_app(profile)
    app.state.services.registry["updates"].fetcher = SourceFetcher(httpx.MockTransport(publisher.respond))
    return app


def inspected(url):
    return [{"url": url, "locator": "Synthetic fixture status, section 1",
             "finding": "Synthetic inspected metadata for application-rule verification only",
             "checked_on": "2026-10-04", "inspected": True}]


def review(api, identifier, target, changes):
    result = api.post(f"/api/v1/updates/entries/{identifier}/review", json={
        "summary": "Synthetic reviewed implication; no real educational publication",
        "state": "reviewed", "target": target, "changes": changes,
        "evidence": inspected(target["canonical_url"]), "topic_ids": target.get("topic_ids", []),
    })
    assert result.status_code == 200, result.text
    assert result.json()["review"]["library_sync_state"] == "applied"
    return result.json()


def current_documents(api):
    result = api.post("/api/v1/library/retrieve", json={"query": "Synthetic currency",
        "scope": {"kind": "study"}, "current_only": True, "limit": 20})
    assert result.status_code == 200, result.text
    return {row["document_id"] for row in result.json()["passages"]}


def completed_run(api):
    for _ in range(200):
        status = api.get("/api/v1/updates/schedule").json()
        if not status["running"]:
            return status
        time.sleep(0.005)
    raise AssertionError("Controlled selected batch did not finish")


def test_detect_review_exact_copy_invalidate_and_restart_preserve_other_topics(tmp_path, monkeypatch):
    publisher = Publisher()
    app = application(tmp_path, monkeypatch, publisher)
    repository = app.state.services.registry["knowledge"]
    copies = {}
    for topic, (pmcid, title) in ARTICLES.items():
        for copy in range(2 if topic == "T08" else 1):
            body = f"SYNTHETIC_PRIVATE_BODY {title} currency copy {copy}"
            digest = hashlib.sha256(body.encode()).hexdigest()
            edition = pmcid + ".1"
            metadata = SourceMetadata(source_id="L02", canonical_url=article_url(pmcid),
                pmcid=pmcid, edition=edition, original_sha256=digest, asset_role=["acquired-jats"], topic_ids=[topic])
            imported = repository.import_text(body, title="Synthetic acquired " + title,
                scope=ContextScope(kind=Scope.LIBRARY), metadata=metadata)
            assert imported["status"] == "ready", imported
            copies[(topic, copy)] = {"document": imported, "target": {
                "register_id": "L02", "canonical_url": article_url(pmcid), "pmcid": pmcid,
                "edition": edition, "original_sha256": digest, "topic_ids": [topic]}}
    with TestClient(app) as api:
        assert len(api.get("/api/v1/content/topics").json()) == 27
        assert current_documents(api) == set()
        assert api.post("/api/v1/updates/sources/L02/check?force=true").json()["state"] == "baseline"
        # Actual official-link producer creates each pending notice; no seeded update records.
        for topic in ARTICLES:
            publisher.notices += 1
            assert api.post("/api/v1/updates/sources/L02/check?force=true").json()["state"] == "changed"
            assert api.post("/api/v1/updates/sources/L02/check?force=true").json()["state"] == "unchanged"
            pending = api.get("/api/v1/updates/entries?state=pending").json()
            assert pending["total"] == 1
            notice = pending["entries"][0]
            rejected = api.post(f"/api/v1/updates/entries/{notice['id']}/review", json={
                "summary": "Synthetic summary alone", "state": "reviewed"})
            assert rejected.status_code == 422
            assert api.get("/api/v1/updates/entries?state=reviewed").json()["total"] == list(ARTICLES).index(topic)
            review(api, notice["id"], copies[(topic, 0)]["target"], {
                "publication_status": "final", "publication_date": "2020-03-01",
                "latest_final_verified": True, "content_reviewed": True,
                "correction": "Synthetic independent corrigendum record"})
            if topic == "T08":
                review(api, notice["id"], copies[(topic, 1)]["target"], {
                    "publication_status": "final", "publication_date": "2020-03-01",
                    "latest_final_verified": True, "content_reviewed": True,
                    "correction": "Synthetic independent corrigendum record"})
        eligible = {copy["document"]["document_id"] for copy in copies.values()}
        assert current_documents(api) == eligible
        target = copies[("T08", 0)]["target"]
        choices = api.get("/api/v1/library/source-versions", params={
            "source_id": "L02", "canonical_url": target["canonical_url"], "pmcid": target["pmcid"]})
        assert choices.status_code == 200 and len(choices.json()["versions"]) == 2
        assert "SYNTHETIC_PRIVATE_BODY" not in choices.text and "original_path" not in choices.text
        tracked = api.post("/api/v1/updates/publications", json={"source_id": "L02",
            "url": target["canonical_url"], "permission_reference": "Synthetic anonymous digest permission"})
        assert tracked.status_code == 200, tracked.text
        path = "/api/v1/updates/publications/" + tracked.json()["id"] + "/check?force=true"
        assert api.post(path).json()["state"] == "baseline"
        publisher.article_revision = 1
        changed = api.post(path).json()
        assert changed["state"] == "changed" and changed["review_required"]
        unchanged = api.post(path).json()
        assert unchanged["state"] == "unchanged"
        pending = api.get("/api/v1/updates/entries?state=pending").json()
        assert pending["total"] == 1 and pending["entries"][0]["kind"] == "publication-change"
        assert pending["entries"][0]["library_changes"][0]["state"] == "applied"
        eligible.remove(copies[("T08", 0)]["document"]["document_id"])
        eligible.remove(copies[("T08", 1)]["document"]["document_id"])
        assert current_documents(api) == eligible
        publisher.offline = True
        failed = api.post(path).json()
        assert failed["state"] == "failed" and failed["freshness"] == "stale"
        assert failed["digest"] == unchanged["digest"] and failed["last_success_at"] == unchanged["last_success_at"]
        for copy in (0, 1):
            document = api.get("/api/v1/library/documents/" + copies[("T08", copy)]["document"]["document_id"]).json()
            metadata = document["revisions"][0]["metadata"]
            assert not metadata["content_reviewed"] and not metadata["latest_final_verified"]
            assert metadata["edition"] == copies[("T08", copy)]["target"]["edition"]
            assert metadata["original_sha256"] == copies[("T08", copy)]["target"]["original_sha256"]
            assert not metadata["access_changed"] and not metadata["retracted"]
        status = next(row for row in api.get("/api/v1/updates/sources/L02/status").json()["statuses"]
                      if row["target"]["pmcid"] == target["pmcid"])
        assert status["status"]["publication_status"] == "final"
        assert status["status"]["publication_date"] == "2020-03-01"
        assert status["status"]["correction"] == "Synthetic independent corrigendum record"
        assert not status["status"]["latest_final_verified"]
    with TestClient(application(tmp_path, monkeypatch, publisher)) as restarted:
        assert current_documents(restarted) == eligible
        pending = restarted.get("/api/v1/updates/entries?state=pending").json()
        assert pending["total"] == 1
        # Dismissal preserves the observation's currency invalidation.
        response = restarted.post("/api/v1/updates/entries/" + pending["entries"][0]["id"] + "/review",
            json={"summary": "", "state": "dismissed"})
        assert response.status_code == 200
        assert current_documents(restarted) == eligible
        assert restarted.get("/api/v1/updates/entries?state=reviewed").json()["total"] == 3
        # Deliberate re-review restores only the acquired hash selected again.
        review(restarted, pending["entries"][0]["id"], copies[("T08", 0)]["target"], {
            "publication_status": "final", "revision_date": "2026-10-04",
            "latest_final_verified": True, "content_reviewed": True})
        eligible.add(copies[("T08", 0)]["document"]["document_id"])
        assert current_documents(restarted) == eligible
        other = restarted.get("/api/v1/library/documents/" + copies[("T08", 1)]["document"]["document_id"]).json()
        assert other["revisions"][0]["metadata"]["content_reviewed"] is False
    assert all(not any(name in request.headers for name in ("authorization", "cookie", "proxy-authorization"))
               for request in publisher.requests)


def test_manual_selected_free_routes_offline_restart_and_forbidden_inputs(tmp_path, monkeypatch):
    publisher = Publisher()
    app = application(tmp_path, monkeypatch, publisher)
    selection = [{"kind": "source", "id": "K01"}] + [
        {"kind": "literature", "id": topic} for topic in ARTICLES]
    with TestClient(app) as api:
        initial = api.get("/api/v1/updates/schedule").json()
        assert initial["enabled"] is False and initial["cadence_hours"] == 24
        assert publisher.requests == []
        saved = api.put("/api/v1/updates/schedule", json={"enabled": False, "cadence_hours": 24, "selection": selection})
        assert saved.status_code == 200
        assert api.post("/api/v1/updates/schedule/check").status_code == 200
        successful = completed_run(api)
        assert successful["last_run"]["state"] == "checked"
        assert successful["last_run"]["checked"] == 4 and successful["last_run"]["failed"] == 0
        success_times = {(job["kind"], job["target_id"]): job["last_success_at"] for job in successful["jobs"]}
        page = api.get("/api/v1/updates/entries?state=pending").json()
        assert page["total"] == 3 and page["counts"]["reviewed"] == 0
        assert "SYNTHETIC_ABSTRACT_MUST_NOT_BE_RETAINED" not in json.dumps(page)
        publisher.offline = True
        assert api.post("/api/v1/updates/schedule/check").status_code == 200
        failed = completed_run(api)
        assert failed["last_run"]["state"] == "failed" and failed["last_run"]["failed"] == 4
        assert all(job["retry_count"] == 1 and job["state"] == "retry-wait" for job in failed["jobs"])
        assert {(job["kind"], job["target_id"]): job["last_success_at"] for job in failed["jobs"]} == success_times
        source = next(row for row in api.get("/api/v1/updates/sources").json()["sources"] if row["source_id"] == "K01")
        assert source["freshness"] == "stale" and source["state"] == "failed"
        before = len(publisher.requests)
        for extra in ({"api_key": "SYNTHETIC_NO_PAID_TOOL"}, {"case_text": "SYNTHETIC_CASE_DO_NOT_EGRESS"}):
            assert api.post("/api/v1/updates/literature/check", json={"topic_ids": ["T08"], **extra}).status_code == 422
            assert api.put("/api/v1/updates/schedule", json={"enabled": True, "selection": selection, **extra}).status_code == 422
        assert api.put("/api/v1/updates/schedule", json={"enabled": True,
            "selection": [{"kind": "source", "id": "E01"}]}).status_code == 400
        assert api.post("/api/v1/updates/literature/check", json={"topic_ids": ["SYNTHETIC_CASE_DO_NOT_EGRESS"]}).status_code == 400
        assert len(publisher.requests) == before
    with TestClient(application(tmp_path, monkeypatch, publisher)) as restarted:
        schedule = restarted.get("/api/v1/updates/schedule").json()
        assert schedule["enabled"] is False
        assert schedule["last_run"] == failed["last_run"]
        assert schedule["jobs"] == failed["jobs"]
        assert restarted.get("/api/v1/updates/entries?state=pending").json()["total"] == 3
    assert all(request.method == "GET" and request.url.host in ("kdigo.org", "www.ebi.ac.uk")
               for request in publisher.requests)
    assert all("SYNTHETIC_CASE_DO_NOT_EGRESS" not in str(request.url) for request in publisher.requests)
