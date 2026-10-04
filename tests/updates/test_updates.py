import json

import pytest

from renulus.contracts import ApiError
from renulus.server import create_app
from renulus.updates.fetch import SourceFetcher, public_url


class SequenceFetcher:
    def __init__(self, values):
        self.values = iter(values)
        self.urls = []
    async def fetch(self, url, hosts, limit=2_000_000):
        self.urls.append(url)
        value = next(self.values)
        if isinstance(value, Exception):
            raise value
        return value if isinstance(value, tuple) else (value, {"content-type": "text/html"}, url)


@pytest.mark.asyncio
async def test_source_change_is_deduplicated_and_needs_explicit_review(tmp_path):
    app = create_app(tmp_path)
    service = app.state.services.registry["updates"]
    before = b'<a href="https://kdigo.org/old.pdf">Guideline</a>'
    after = b'<a href="https://kdigo.org/old.pdf">Guideline</a><a href="https://kdigo.org/correction.pdf">Corrigendum</a>'
    service.fetcher = SequenceFetcher([before, after, after])
    assert (await service.check_source("K01", force=True))["state"] == "baseline"
    assert (await service.check_source("K01", force=True))["state"] == "changed"
    assert (await service.check_source("K01", force=True))["state"] == "unchanged"
    assert service.list_entries(reviewed_only=True) == []
    assert len(service.list_entries()) == 1
    item = service.list_entries()[0]
    service.review(item["id"], "Reviewed official correction; inspect the affected recommendation.",
                   ["ckd"], "learner", "reviewed")
    assert service.list_entries(reviewed_only=True)[0]["reviewed_at"]


@pytest.mark.asyncio
async def test_failed_fetch_keeps_last_success_and_reports_failed_state(tmp_path):
    app = create_app(tmp_path)
    service = app.state.services.registry["updates"]
    service.fetcher = SequenceFetcher([b'<a href="/guide.pdf">Guideline</a>', RuntimeError("offline")])
    await service.check_source("K01", force=True)
    previous = next(row for row in service.list_sources() if row["source_id"] == "K01")["last_success_at"]
    failed = await service.check_source("K01", force=True)
    assert failed["state"] == "failed"
    current = next(row for row in service.list_sources() if row["source_id"] == "K01")
    assert current["last_success_at"] == previous
    assert current["state"] == "failed"


@pytest.mark.asyncio
async def test_literature_queries_use_only_installed_topics_and_keep_metadata_unreviewed(tmp_path):
    app = create_app(tmp_path)
    services = app.state.services
    class Content:
        def list_topics(self):
            return [{"id": "ckd", "title": "chronic kidney disease"}]
    services.registry["content"] = Content()
    service = services.registry["updates"]
    body = json.dumps({"resultList": {"result": [{"id": "123", "source": "MED",
        "title": "An original synthetic research metadata record", "firstPublicationDate": "2026-10-01",
        "pubType": "journal article", "isOpenAccess": "N"}]}}).encode()
    fetcher = SequenceFetcher([body, body])
    service.fetcher = fetcher
    with pytest.raises(ApiError, match="Choose an installed topic"):
        await service.check_literature(["SYNTHETIC_CASE_DETAIL"])
    assert fetcher.urls == []
    assert (await service.check_literature(["ckd"]))["discovered"] == 1
    assert (await service.check_literature(["ckd"]))["discovered"] == 0
    assert "SYNTHETIC_CASE_DETAIL" not in "".join(fetcher.urls)
    assert service.list_entries()[0]["source_id"] == "L03"
    assert service.list_entries(reviewed_only=True) == []


@pytest.mark.asyncio
async def test_private_hosts_and_redirects_are_blocked(monkeypatch):
    import socket
    import httpx
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))])
    with pytest.raises(ApiError, match="Private network"):
        await public_url("https://official.example/source", {"official.example"})
    transport = httpx.MockTransport(lambda request: httpx.Response(302, headers={"Location": "http://127.0.0.1/private"}))
    with pytest.raises(ApiError, match="left the official host"):
        await SourceFetcher(transport).fetch("https://official.example/source", {"official.example"})
