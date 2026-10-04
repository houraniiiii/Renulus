"""Synthetic publisher sequences; no live providers or clinical-review claims."""
import hashlib
import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from renulus.contracts import ApiError
from renulus.server import create_app
from renulus.storage import AppPaths, Database
from renulus.updates.fetch import SourceFetcher
from test_updates import SequenceFetcher


def tracked(service):
    candidate = service.publications.candidates("K01")[0]
    return service.publications.track("K01", candidate["url"], "Synthetic public check permission")


@pytest.mark.asyncio
async def test_same_url_digest_change_without_changed_links_or_validators(tmp_path):
    service = create_app(tmp_path).state.services.registry["updates"]
    publication = tracked(service)
    before, after = b"%PDF-1.7 synthetic original", b"%PDF-1.7 synthetic correction"
    headers = {"content-type": "application/pdf", "etag": '"constant"', "last-modified": "Wed, 01 Oct 2025 10:00:00 GMT"}
    service.fetcher = SequenceFetcher([(body, headers, publication["url"]) for body in (before, after, after, before)])
    assert (await service.publications.check(publication["id"], True))["state"] == "baseline"
    assert (await service.publications.check(publication["id"], True))["state"] == "changed"
    assert (await service.publications.check(publication["id"], True))["state"] == "unchanged"
    entry = service.list_entries()[0]
    assert entry["url"] == publication["url"]
    assert entry["kind"] == "publication-change"
    assert entry["publication_date"] is None
    assert entry["source_metadata"]["previous_sha256"] == hashlib.sha256(before).hexdigest()
    assert entry["source_metadata"]["observed"]["sha256"] == hashlib.sha256(after).hexdigest()
    assert service.list_entries(reviewed_only=True) == []
    assert len(service.list_entries()) == 1
    # Returning to earlier bytes is another event, not swallowed by digest deduplication.
    assert (await service.publications.check(publication["id"], True))["state"] == "changed"
    assert len(service.list_entries()) == 2
    assert set(service.fetcher.urls) == {publication["url"]}
    with service.db.connect() as conn:
        dump = "\n".join(conn.iterdump())
    assert before.decode() not in dump and after.decode() not in dump


@pytest.mark.asyncio
async def test_failure_wrong_format_and_size_keep_last_success_and_digest(tmp_path):
    service = create_app(tmp_path).state.services.registry["updates"]
    publication = tracked(service)
    service.fetcher = SequenceFetcher([b"%PDF-1.7 synthetic", RuntimeError("offline"), b"<html>Sign in</html>", b"%PDF-" + b"x" * 16_000_000])
    baseline = await service.publications.check(publication["id"], True)
    for expected in ("publication_fetch_failed", "publication_format_changed", "publication_response_invalid"):
        failed = await service.publications.check(publication["id"], True)
        assert failed["state"] == "failed"
        assert failed["freshness"] == "stale"
        assert failed["error_code"] == expected
        assert failed["last_success_at"] == baseline["last_success_at"]
        assert failed["digest"] == baseline["digest"]
    assert service.list_entries() == []


def test_tracking_is_opt_in_registered_and_permission_bounded(tmp_path):
    service = create_app(tmp_path).state.services.registry["updates"]
    assert service.publications.list() == []
    for url, code in (("https://127.0.0.1/private.pdf", "source_host_blocked"),
                      ("https://kdigo.org/arbitrary.pdf?case=SYNTHETIC_PRIVATE_SENTINEL", "publication_not_registered")):
        with pytest.raises(ApiError) as error:
            service.publications.track("K01", url, "synthetic")
        assert error.value.code == code
    candidate = service.publications.candidates("K01")[0]
    with pytest.raises(ApiError) as error:
        service.publications.track("K01", candidate["url"], " " )
    assert error.value.code == "publication_permission_required"
    first = tracked(service)
    assert tracked(service)["id"] == first["id"]
    assert len(service.publications.list()) == 1
    service.publications.stop(first["id"])
    assert service.publications.list() == []


@pytest.mark.asyncio
async def test_fetcher_bounds_stream_and_anonymous_redirects():
    calls = []
    def publisher(request):
        calls.append(request)
        if request.url.path == "/start":
            return httpx.Response(302, headers={"location": "/publication.pdf", "set-cookie": "private=sentinel"})
        return httpx.Response(200, content=b"%PDF-" + b"x" * 1100)
    fetcher = SourceFetcher(httpx.MockTransport(publisher))
    with pytest.raises(ApiError) as error:
        await fetcher.fetch("https://publisher.example/start", {"publisher.example"}, limit=1024)
    assert error.value.code == "source_metadata_too_large"
    assert len(calls) == 2
    assert all("cookie" not in call.headers and "authorization" not in call.headers for call in calls)
    for redirect in ("https://user:password@publisher.example/publication.pdf", "https://publisher.example:444/publication.pdf", "https://127.0.0.1/private"):
        fetcher = SourceFetcher(httpx.MockTransport(lambda request: httpx.Response(302, headers={"location": redirect})))
        with pytest.raises(ApiError):
            await fetcher.fetch("https://publisher.example/start", {"publisher.example", "127.0.0.1"})


def insert_entries(service, count):
    with service.db.transaction() as conn:
        for index in range(count):
            conn.execute("INSERT INTO update_entries(id,source_id,external_id,title,url,kind,discovered_at,review_state,summary,source_metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (f"update_{index:04}", "K01", f"synthetic:{index}", "Synthetic update", "https://kdigo.org/guide.pdf",
                 "source-change", "2026-10-04T10:00:00+00:00", "pending", "Synthetic unreviewed change", "{}"))


def test_review_read_and_id_lookup_work_beyond_100_with_stable_pagination(tmp_path):
    app = create_app(tmp_path)
    service = app.state.services.registry["updates"]
    insert_entries(service, 301)
    client = TestClient(app)
    first = client.get("/api/v1/updates/entries?limit=100&state=pending").json()
    assert first["counts"]["pending"] == first["total"] == 301
    second = client.get(f"/api/v1/updates/entries?limit=100&state=pending&offset={first['next_offset']}").json()
    assert not set(item["id"] for item in first["entries"]) & set(item["id"] for item in second["entries"])
    assert client.get("/api/v1/updates/entries?limit=999999").status_code == 422
    reviewed = client.post("/api/v1/updates/entries/update_0000/review", json={"summary": "Synthetic educational review for the application-rule test", "state": "reviewed"})
    assert reviewed.status_code == 200
    assert reviewed.json()["id"] == "update_0000"
    assert client.get("/api/v1/updates/entries/update_0000").json()["review_state"] == "reviewed"
    assert client.post("/api/v1/updates/entries/update_0000/read").status_code == 200
    assert client.post("/api/v1/updates/entries/missing/read").status_code == 404
    assert client.post("/api/v1/updates/entries/missing/review", json={"summary": "synthetic", "state": "reviewed"}).status_code == 404


def test_populated_001_upgrades_and_restarts_without_rewriting_schema(tmp_path):
    paths = AppPaths.create(tmp_path)
    db = Database(paths.database)
    module = Path(__file__).parents[2] / "runtime/renulus/updates"
    schema = (module / "schema.sql").read_text(encoding="utf-8")
    db.apply_migration("updates-001", schema)
    db.execute("INSERT INTO update_source_checks(source_id,title,url,snapshot_status) VALUES('K01','Synthetic','https://kdigo.org/','dated snapshot')")
    db.execute("INSERT INTO update_entries(id,source_id,external_id,title,url,kind,discovered_at,review_state,summary,source_metadata_json) VALUES('old','K01','old','Synthetic','https://kdigo.org/','source-change','2025-01-01','reviewed','synthetic review','{}')")
    service = create_app(tmp_path).state.services.registry["updates"]
    publication = tracked(service)
    restarted = create_app(tmp_path).state.services.registry["updates"]
    assert restarted.get_entry("old")["review_state"] == "reviewed"
    assert restarted.publications.get(publication["id"])["state"] == "never-checked"
    assert db.fetch_one("SELECT checksum FROM migration_ledger WHERE name='updates-001'")["checksum"] == hashlib.sha256(schema.encode()).hexdigest()
