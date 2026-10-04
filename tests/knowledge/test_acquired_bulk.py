"""Bounded registered bulk selection through real canonical jobs, offline only."""
import base64
import hashlib
import json
from pathlib import Path
from threading import Event
import time

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from renulus.contracts import ApiError, ContextScope, Scope
from renulus.knowledge.acquired import AcquiredLiterature
from renulus.knowledge.collection import MANIFEST
from renulus.knowledge.worker import IngestionWorker
from renulus.server import create_app
from test_acquired import Case, jats, offline
from test_repository import repository, SyntheticExtractor, SyntheticEmbedder


def collection_cases(repository, tmp_path, count=3):
    topics = ["T06", "T08", "T21", "T10", "T12", "T20", "T27", "T24"]
    cases = [Case(tmp_path / "collection", version=version) for version in range(1, count + 1)]
    for case, topic in zip(cases, topics):
        for item in case.items:
            item["topics"] = [{"topic_id": topic}]
    cases[0].items = [item for case in cases for item in case.items]
    return cases, cases[0].register(repository)


def test_bulk_pages_inspect_once_preserve_denials_domains_and_durable_jobs(repository, tmp_path, monkeypatch):
    cases, collection = collection_cases(repository, tmp_path, count=8)
    first = cases[0]
    bad = cases[3]
    bad.xml.write_bytes(jats(url="https://creativecommons.org/licenses/by-nc/4.0/"))
    bad.record["xml_url"] = bad.record["xml_url"].split("?")[0] + "?md5=" + hashlib.md5(bad.xml.read_bytes()).hexdigest()
    bad.meta.write_text(json.dumps(bad.record))
    first.items[6:8] = [bad.receipt(bad.xml, "fulltext-jats", 4), bad.receipt(bad.meta, "article-version-metadata", 4)]
    retracted = cases[4]
    retracted.record["is_retracted"] = True
    retracted.meta.write_text(json.dumps(retracted.record))
    first.items[9] = retracted.receipt(retracted.meta, "article-version-metadata", 5)
    for item in first.items[12:14]:
        item["licence"] = "CC BY-NC"
    for item in first.items[14:16]:
        item["reserved"] = True
    alternate = first.xml.with_name("alternate.xml")
    alternate.write_bytes(first.xml.read_bytes())
    alternate_receipt = first.receipt(alternate, "fulltext-jats", 1)
    alternate_receipt["topics"] = [{"topic_id": "T06"}]
    first.items.append(alternate_receipt)
    unrelated = first.xml.with_suffix(".pdf")
    unrelated.write_bytes(b"SYNTHETIC_UNSELECTED_SENTINEL")
    first.items.append(first.receipt(unrelated, "fulltext-pdf", 1))
    collection = first.register(repository)
    cases[5].xml.write_bytes(cases[5].xml.read_bytes() + b"\n")
    originals = {item["local_path"]: (first.root / item["local_path"]).read_bytes() for item in first.items}
    batches, allowed, manifest_reads = [], set(), []
    open_file, import_selected = Path.open, collection.import_selected
    def guarded_open(path, *args, **kwargs):
        if path.resolve().is_relative_to(first.root.resolve()):
            assert path.resolve() in allowed, "Only this page's matched originals may open"
            if path == first.root / MANIFEST:
                manifest_reads.append(path)
        return open_file(path, *args, **kwargs)
    def page(entry_ids, **kwargs):
        batches.append(entry_ids)
        allowed.clear()
        allowed.add((first.root / MANIFEST).resolve())
        for identifier in entry_ids:
            entry = repository.db.fetch_one("SELECT * FROM knowledge_catalogue WHERE id=?", (identifier,))
            allowed.add((first.root / entry["collection_path"]).resolve())
            edition = json.loads(entry["metadata_json"])["edition"]
            allowed.add(next(case.meta.resolve() for case in cases if case.name == edition))
        return import_selected(entry_ids, **kwargs)
    monkeypatch.setattr(collection, "import_selected", page)
    monkeypatch.setattr(collection, "register", lambda **kw: pytest.fail("Bulk must not register"))
    monkeypatch.setattr(collection, "preview", lambda **kw: pytest.fail("Bulk must not preview"))
    pages, cursor = [], None
    with monkeypatch.context() as reads:
        reads.setattr(Path, "open", guarded_open)
        for _ in range(8):
            result = collection.import_next(limit=2, cursor=cursor)
            pages.append(result)
            cursor = result["next_cursor"]
            if result["done"]:
                break
    assert pages[-1]["done"] and cursor is None
    attempted = [identifier for batch in batches for identifier in batch]
    assert attempted == sorted(set(attempted))
    assert len(manifest_reads) == len(pages) == 4
    assert sum(page["attempted"] for page in pages) == 7
    assert sum(page["newly_queued"] for page in pages) == 3
    assert sum(page["replayed"] for page in pages) == 1
    assert {r["code"] for page in pages for r in page["results"] if "code" in r} == {"article_permission_required", "article_retraction_unavailable", "source_hash_changed"}
    revisions = repository.db.fetch_all("SELECT * FROM knowledge_revisions")
    assert len(revisions) == 3
    assert {tuple(json.loads(row["metadata_json"])["topic_ids"]) for row in revisions} == {("T06",), ("T08",), ("T21",)}
    for row in revisions:
        metadata = json.loads(row["metadata_json"])
        receipt = next(item for item in first.items if item.get("article_version") == int(metadata["edition"].split(".")[1]) and item["artifact_type"] == "fulltext-jats")
        assert metadata["original_sha256"] == receipt["sha256"]
        assert metadata["publication_status"] == "unknown" and not metadata["content_reviewed"]
    assert collection.import_next(limit=2)["done"]
    assert len(repository.db.fetch_all("SELECT * FROM knowledge_jobs")) == 3
    worker = IngestionWorker(repository)
    try:
        worker.start()
        deadline = time.monotonic() + 15
        while any(repository.get_job(row["id"])["state"] != "ready" for row in repository.db.fetch_all("SELECT id FROM knowledge_jobs")) and time.monotonic() < deadline:
            time.sleep(0.05)
        assert all(row["state"] == "ready" for row in repository.db.fetch_all("SELECT state FROM knowledge_jobs"))
        assert worker.status()["cpu_workers"] == 1
        for topic in ("T06", "T08", "T21"):
            passages = repository.retrieve("transplant", topic_id=topic, scope=ContextScope(kind=Scope.STUDY))["passages"]
            assert len(passages) == 1
        assert not repository.retrieve("transplant", topic_id="T24", scope=ContextScope(kind=Scope.STUDY))["passages"]
    finally:
        worker.stop()
    assert originals == {path: (first.root / path).read_bytes() for path in originals}


@pytest.mark.parametrize("point", ["manifest", "inspection", "adoption"])
def test_bulk_cancellation_preserves_unattempted_candidates_and_resumes(repository, tmp_path, monkeypatch, point):
    cases, collection = collection_cases(repository, tmp_path)
    stop = Event()
    if point == "manifest":
        original = AcquiredLiterature.selections
        def cancelling(adapter, entries, **kwargs):
            stop.set()
            return original(adapter, entries, **kwargs)
        monkeypatch.setattr(AcquiredLiterature, "selections", cancelling)
    elif point == "inspection":
        original = AcquiredLiterature.inspect
        def cancelling(adapter, *args):
            article = original(adapter, *args)
            stop.set()
            return article
        monkeypatch.setattr(AcquiredLiterature, "inspect", cancelling)
    else:
        original = collection._import_acquired
        def cancelling(*args):
            result = original(*args)
            stop.set()
            return result
        monkeypatch.setattr(collection, "_import_acquired", cancelling)
    result = collection.import_next(limit=3, cancelled=stop.is_set)
    adopted = 1 if point == "adoption" else 0
    assert result["cancelled"] and not result["done"]
    assert result["attempted"] == result["newly_queued"] == adopted
    assert result["rejected"] == 0 and result["remaining"] == 3 - adopted
    assert collection.list(eligibility="inspection_required")["total"] == 3 - adopted
    monkeypatch.undo()
    resumed = collection.import_next(limit=3, cursor=result["next_cursor"])
    assert resumed["done"] and resumed["newly_queued"] == 3 - adopted
    assert len(repository.db.fetch_all("SELECT * FROM knowledge_jobs")) == 3


def test_bulk_cursor_is_filter_bound_and_legacy_batch_retry_remains_compatible(repository, tmp_path):
    cases, collection = collection_cases(repository, tmp_path)
    result = collection.import_next(limit=1, query="Synthetic")
    assert result["remaining"] == 2
    with pytest.raises(ApiError) as invalid:
        collection.import_next(limit=1, query="Other", cursor=result["next_cursor"])
    assert invalid.value.code == "invalid_collection_cursor"
    with pytest.raises(ApiError):
        collection.import_next(cursor="!")
    encoded = json.loads(base64.urlsafe_b64decode(result["next_cursor"] + "=" * (-len(result["next_cursor"]) % 4)))
    encoded["through"] = "../../private"
    with pytest.raises(ApiError):
        collection.import_next(query="Synthetic", cursor=base64.urlsafe_b64encode(json.dumps(encoded).encode()).decode())
    first = result["results"][0]
    old = collection.import_selected([first["entry_id"]])["results"][0]
    assert old["job"]["id"] == first["job"]["id"] and "replayed" not in old
    repository.cancel_job(first["job"]["id"])
    retry = collection.import_next(limit=3)
    assert retry["newly_queued"] == 3 and retry["done"]
    replaced = next(row for row in retry["results"] if row["entry_id"] == first["entry_id"])
    assert replaced["document_id"] == first["document_id"] and replaced["job"]["id"] != first["job"]["id"]


def test_bulk_publication_restriction_applies_across_domain_scopes(repository, tmp_path):
    cases, collection = collection_cases(repository, tmp_path)
    repository.update_source_status({"contract_version": 1, "event_id": "bulk-removal", "source_id": "L02",
        "identity": {"pmcid": "PMC90001"}, "changes": {"repository_removed": True},
        "scope": {"topic_ids": ["T27"]}, "evidence": [{"inspected": True}]})
    result = collection.import_next(limit=3)
    assert result["done"] and result["newly_queued"] == 0
    assert result["rejections"] == {"article_status_unavailable": 3}
    assert not repository.list_documents()["documents"]


def test_bulk_existing_job_skip_requires_edition_as_well_as_original_hash(repository, tmp_path):
    cases, collection = collection_cases(repository, tmp_path, count=2)
    rows = collection.list(eligibility="inspection_required")["entries"]
    by_edition = {row["metadata"]["edition"]: row for row in rows}
    assert cases[0].items[0]["sha256"] == cases[1].items[0]["sha256"]
    repository.update_source_status({"contract_version": 1, "event_id": "bulk-bound-review", "source_id": "L02",
        "identity": {"pmcid": "PMC90001", "edition": cases[0].name, "original_sha256": cases[0].items[0]["sha256"]},
        "changes": {"publication_status": "final", "latest_final_verified": True, "content_reviewed": True},
        "scope": {}, "evidence": [{"inspected": True}]})
    first = collection.import_selected([by_edition[cases[0].name]["id"]])["results"][0]
    # A stale catalogue binding to the other version must not suppress pending
    # inspection merely because both versions contain identical JATS bytes.
    repository.db.execute("UPDATE knowledge_catalogue SET document_id=?,job_id=? WHERE id=?",
        (first["document_id"], first["job"]["id"], by_edition[cases[1].name]["id"]))
    result = collection.import_next(limit=2)
    assert result["newly_queued"] == 1 and result["done"]
    second = result["results"][0]
    assert second["document_id"] != first["document_id"]
    metadata = json.loads(repository.db.fetch_one("SELECT metadata_json FROM knowledge_revisions WHERE id=?", (second["revision_id"],))["metadata_json"])
    assert metadata["edition"] == cases[1].name and metadata["original_sha256"] == cases[1].items[0]["sha256"]
    assert metadata["publication_status"] == "unknown" and not metadata["content_reviewed"]


def test_bulk_api_scope_limits_pages_and_disconnect_leave_durable_state(tmp_path, monkeypatch):
    app = create_app(tmp_path / "profile")
    repository = app.state.services.registry["knowledge"]
    repository.extractor, repository.embedder = SyntheticExtractor(), SyntheticEmbedder()
    cases, collection = collection_cases(repository, tmp_path)
    app.state.services.registry["knowledge_catalogue"].root = cases[0].root.resolve()
    endpoint = "/api/v1/library/collection/import-next"
    body = {"scope": {"kind": "personal-library"}, "limit": 1}
    with TestClient(app) as api:
        app.state.services.registry["knowledge_worker"].stop()
        assert api.post(endpoint, json={**body, "scope": {"kind": "temporary-case"}}).status_code == 409
        assert api.post(endpoint, json={**body, "limit": 251}).status_code == 422
        assert api.post(endpoint, json={**body, "source_id": "E01"}).status_code == 422
        literal = api.post(endpoint, json={**body, "query": "%"})
        assert literal.status_code == 202 and literal.json()["done"] and literal.json()["attempted"] == 0
        first = api.post(endpoint, json=body)
        assert first.status_code == 202 and first.json()["newly_queued"] == 1
        assert first.json()["remaining"] == 2
        started, captured = Event(), {}
        live_collection = app.state.services.registry["knowledge_catalogue"]
        bulk, inspect = live_collection.import_next, AcquiredLiterature.inspect
        def capture(**kwargs):
            captured["stop"] = kwargs["cancelled"].__self__
            return bulk(**kwargs)
        def blocked(adapter, *args):
            article = inspect(adapter, *args)
            started.set()
            assert captured["stop"].wait(5)
            return article
        async def disconnected(request):
            return request.url.path == endpoint and started.is_set()
        with monkeypatch.context() as disconnect:
            disconnect.setattr(live_collection, "import_next", capture)
            disconnect.setattr(AcquiredLiterature, "inspect", blocked)
            disconnect.setattr(Request, "is_disconnected", disconnected)
            stopped = api.post(endpoint, json={**body, "cursor": first.json()["next_cursor"]})
            assert stopped.status_code == 202 and stopped.json()["cancelled"]
            assert stopped.json()["attempted"] == stopped.json()["rejected"] == 0
        resumed = api.post(endpoint, json={**body, "limit": 2, "cursor": stopped.json()["next_cursor"]})
        assert resumed.status_code == 202 and resumed.json()["done"]
        assert resumed.json()["newly_queued"] == 2
        assert len(repository.db.fetch_all("SELECT * FROM knowledge_jobs WHERE state='queued'")) == 3
