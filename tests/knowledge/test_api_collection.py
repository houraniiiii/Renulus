import hashlib
import json
from pathlib import Path
import time

from fastapi.testclient import TestClient
import pytest

from renulus.contracts import ContextScope, Scope
from renulus.knowledge.collection import CollectionCatalogue, CATALOGUE, MANIFEST, VERIFICATION
from renulus.knowledge.models import own_text_rights
from renulus.server import create_app
from test_repository import SyntheticEmbedder, SyntheticExtractor


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path / "profile")
    repository = app.state.services.registry["knowledge"]
    repository.extractor, repository.embedder = SyntheticExtractor(), SyntheticEmbedder()
    with TestClient(app) as api:
        yield api, repository


def test_api_text_original_retrieve_and_single_terminal_sse(client):
    api, repository = client
    result = api.post("/api/v1/library/import/text", json={"title": "Synthetic nephrology study",
        "text": "Kidney transplantation immune rejection", "scope": {"kind": "personal-library"},
        "idempotency_key": "api-import"})
    assert result.status_code == 202
    result = result.json()
    event_response = api.get("/api/v1/library/jobs/" + result["job"]["id"] + "/events")
    events = [json.loads(x[6:]) for x in event_response.text.splitlines() if x.startswith("data: ")]
    assert events[-1]["type"] == "ready"
    assert sum(event["type"] in ("ready", "failed", "cancelled") for event in events) == 1
    assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
    hit = api.post("/api/v1/library/retrieve", json={"query": "rejection", "scope": {"kind": "study"}}).json()["passages"][0]
    assert hit["document_revision"] == result["revision_id"]
    original = api.get(hit["original_url"])
    assert original.text == "Kidney transplantation immune rejection"
    assert original.headers["cache-control"] == "no-store"
    assert api.delete("/api/v1/library/documents/" + result["document_id"]).json()["status"] == "deleted"
    assert api.get(hit["original_url"]).status_code == 404


def test_unsafe_raw_file_upload_is_rejected_before_stream_consumption(client):
    api, repository = client
    original_paths = set(repository.paths.root.rglob("*"))
    options = {"scope": {"kind": "temporary-case"}, "idempotency_key": "no-save"}
    response = api.post("/api/v1/library/import/file", content=b"PRIVATE_TEMPORARY_CASE_SENTINEL" * 100000,
        headers={"x-renulus-filename": "patient.txt", "x-renulus-import-options": json.dumps(options)})
    assert response.status_code == 409
    assert set(repository.paths.root.rglob("*")) == original_paths
    assert repository.list_documents()["documents"] == []


def test_raw_file_upload_and_malformed_size_format_errors(client, tmp_path):
    api, repository = client
    options = {"scope": {"kind": "personal-library"}, "idempotency_key": "raw",
               "rights": own_text_rights().model_dump()}
    headers = {"x-renulus-filename": "study.txt", "x-renulus-import-options": json.dumps(options)}
    assert api.post("/api/v1/library/import/file", content=b"Dialysis access", headers=headers).status_code == 202
    headers["x-renulus-filename"] = "malformed.pdf"
    assert api.post("/api/v1/library/import/file", content=b"not-a-pdf", headers=headers).json()["error"]["code"] == "malformed_pdf"
    headers["x-renulus-filename"] = "source.exe"
    assert api.post("/api/v1/library/import/file", content=b"data", headers=headers).status_code == 415
    path = tmp_path / "large.pdf"
    with path.open("wb") as stream:
        stream.truncate(65 * 1024 * 1024)
    with pytest.raises(Exception) as caught:
        repository.import_file(path, rights=own_text_rights())
    assert caught.value.code == "document_limit"


def test_explicit_catalogue_selection_hashes_rights_errors_and_reserved_exclusion(client, tmp_path):
    api, repository = client
    repository.services.registry["knowledge_worker"].stop()
    root = tmp_path / "collection"
    root.mkdir()
    source = root / "raw/R01/synthetic.txt"
    source.parent.mkdir(parents=True)
    source.write_text("Synthetic dialysis note")
    sibling = source.with_name("not-selected.txt")
    sibling.write_text("Do not recursively ingest this sibling")
    item = {"source_id": "R01", "title": "Original Renulus teaching", "local_path": "raw/R01/synthetic.txt",
        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "bytes": source.stat().st_size,
        "processing_scope": {name: True for name in ["display", "cache", "index", "embedding", "model_input"]},
        "licence": {"identifier": "CC-BY-4.0"}}
    manifest = root / MANIFEST
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps(item) + "\n{invalid-row\n" + json.dumps({**item, "source_id": "E02"}) + "\n")
    collection = CollectionCatalogue(repository, root)
    preview = collection.preview()
    assert preview["total"] == 2 and len(preview["errors"]) == 1
    assert collection.register()["catalogued"] == 2
    entries = collection.list()["entries"]
    selected = collection.import_selected([e["id"] for e in entries])
    assert selected["queued"] == 1
    assert any(x["status"] == "excluded" for x in selected["results"])
    assert repository.list_documents()["documents"][0]["source_id"] == "R01"
    assert repository.retrieve("dialysis", scope=ContextScope(kind=Scope.STUDY))["passages"] == []
    assert len(repository.list_documents()["documents"]) == 1
    assert source.read_text() == "Synthetic dialysis note" and sibling.is_file()


def test_manual_catalogue_is_not_current_or_indexed_and_uses_verification(client, tmp_path):
    _, repository = client
    root = tmp_path / "collection"
    path = root / "raw/E01/chapter.pdf"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"%PDF-1.4 synthetic source; catalogued, no extraction claim")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    catalogue = {"source_owner": "ERA", "receipt_date": "2026-10-04", "edition": None,
        "sections": [{"id": 95, "title": "Physiology", "chapters": [{"title": "Sodium",
            "files": [{"collection_path": str(path), "sha256": digest, "bytes": path.stat().st_size,
                        "categories": ["chapter"], "label": "CHAPTER DOWNLOAD"}]}]}]}
    target = root / CATALOGUE
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(catalogue))
    (root / VERIFICATION).write_text(json.dumps({"files": [{"path": str(path), "sha256": digest, "status": "valid_pdf"}]}))
    collection = CollectionCatalogue(repository, root)
    assert collection.register(source_id="E01")["indexed"] is False
    entry = collection.list()["entries"][0]
    assert entry["processing_status"] == "acquired"
    assert entry["metadata"]["latest_final_verified"] is False
    assert entry["metadata"]["publication_date"] is None
    assert entry["metadata"]["collection_section"] == "Physiology"
    assert entry["rights"]["redistribution"] is False
    assert repository.list_documents()["documents"] == []


def test_manifest_permission_strings_remain_visible_without_processing_permission(client, tmp_path):
    _, repository = client
    root = tmp_path / "collection"
    root.mkdir()
    source = root / "synthetic.txt"
    source.write_text("Acquired source with unverified processing rights")
    manifest = root / MANIFEST
    manifest.parent.mkdir(parents=True)
    rows = [
        {"source_id": "R01", "local_path": str(source), "processing_scope": "human reading only", "licence": "unverified"},
        {"source_id": "R02", "local_path": str(source), "processing_scope": None, "licence": None},
    ]
    manifest.write_text("\n".join(json.dumps(row) for row in rows))
    collection = CollectionCatalogue(repository, root)
    result = collection.register()
    assert result["catalogued"] == 2 and not result["errors"]
    entries = collection.list()["entries"]
    assert all(entry["eligibility"] == "permission_or_format_unavailable" for entry in entries)
    assert all(not entry["rights"]["index"] and not entry["rights"]["embedding"] for entry in entries)
    assert collection.import_selected([entry["id"] for entry in entries])["queued"] == 0
    assert repository.list_documents()["documents"] == []
