"""Actual Office extraction, SQLite and LanceDB; vectors are a controlled seam."""
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from renulus.knowledge.models import own_text_rights
from renulus.knowledge.office import OFFICE_MEDIA
from renulus.server import create_app
from test_office_conversion import make_office, office_extractor, offline_guard
from test_office_validation import package
from test_repository import SyntheticEmbedder


def client_for(path, extractor):
    app = create_app(path)
    repository = app.state.services.registry["knowledge"]
    repository.extractor, repository.embedder = extractor, SyntheticEmbedder()
    # No lifespan/native/helper warmup: drain explicit jobs through the repository.
    return TestClient(app), repository


def upload(api, path, **options):
    settings = {"title": "Synthetic supplement", "scope": {"kind": "personal-library"},
        "rights": own_text_rights().model_dump(), "idempotency_key": path.name, **options}
    return api.post("/api/v1/library/import/file", content=path.read_bytes(), headers={
        "x-renulus-filename": path.name, "x-renulus-import-options": json.dumps(settings)})


@pytest.mark.parametrize("suffix", OFFICE_MEDIA)
def test_durable_api_actual_extraction_retrieval_exact_citation_and_original(office_extractor, tmp_path, suffix):
    path = make_office(tmp_path / ("synthetic" + suffix))
    api, repository = client_for(tmp_path / "profile", office_extractor)
    try:
        response = upload(api, path)
        assert response.status_code == 202, response.text
        imported = response.json()
        assert imported["status"] == "queued"
        assert repository.run_job(imported["job"]["id"])["state"] == "ready"
        passages = api.post("/api/v1/library/retrieve", json={"query": "Synthetic", "scope": {"kind": "study"}}).json()["passages"]
        assert passages and all(p["document_revision"] == imported["revision_id"] for p in passages)
        for passage in passages:
            citation = api.get("/api/v1/library/revisions/" + imported["revision_id"] + "/citation", params={"passage_id": passage["id"]})
            assert citation.status_code == 200, citation.text
            assert citation.json()["locators"] == passage["locators"]
            assert all(locator["page"] is None for locator in passage["locators"])
            assert api.get("/api/v1/library/revisions/" + imported["revision_id"] + "/citation", params={"passage_id": passage["id"], "page": 1}).status_code == 404
        original = api.get("/api/v1/library/revisions/" + imported["revision_id"] + "/original")
        assert original.status_code == 200 and original.content == path.read_bytes()
        assert original.headers["content-type"] == OFFICE_MEDIA[suffix]
        replay = upload(api, path).json()
        assert replay["job"]["id"] == imported["job"]["id"]
        assert api.delete("/api/v1/library/documents/" + imported["document_id"]).status_code == 200
        assert repository.db.fetch_all("SELECT * FROM knowledge_passages") == []
        assert not list(repository.paths.library.rglob("original.*"))
    finally:
        repository.index.close()
        api.close()


def test_three_real_office_formats_restore_originals_and_canonical_locators_via_api(office_extractor, tmp_path):
    api, repository = client_for(tmp_path / "source", office_extractor)
    target_api, target = client_for(tmp_path / "restored", office_extractor)
    selected = []
    try:
        for suffix in OFFICE_MEDIA:
            path = make_office(tmp_path / ("backup" + suffix))
            response = upload(api, path)
            assert response.status_code == 202, response.text
            imported = response.json()
            assert repository.run_job(imported["job"]["id"])["state"] == "ready"
            selected.append((path.read_bytes(), imported))
        before = repository.db.fetch_all("SELECT id,locators_json FROM knowledge_passages ORDER BY id")
        download = api.get("/api/v1/data/backup?format_version=2")
        assert download.status_code == 200, download.text
        preview = target_api.post("/api/v1/data/backup/preview?format_version=2", content=download.content)
        assert preview.status_code == 200, preview.text
        checked = preview.json()
        restored = target_api.post("/api/v1/data/backup/restore", json={
            "preview_token": checked["preview_token"], "confirmed_exported_at": checked["exported_at"],
            "acknowledge_deletion_limits": True})
        assert restored.status_code == 200, restored.text
        assert restored.json()["restored_originals"] == 3
        assert target.db.fetch_all("SELECT id,locators_json FROM knowledge_passages ORDER BY id") == before
        for original, imported in selected:
            revision = imported["revision_id"]
            assert target_api.get("/api/v1/library/revisions/" + revision + "/original").content == original
            row = target.db.fetch_one("SELECT original_path,extraction_json FROM knowledge_revisions WHERE id=?", (revision,))
            assert Path(row["original_path"]).is_relative_to(target.paths.library)
            assert row["extraction_json"] is None  # Existing recovery contract omits rebuildable structure.
        for row in before:
            passage = target.db.fetch_one("SELECT revision_id FROM knowledge_passages WHERE id=?", (row["id"],))
            citation = target_api.get("/api/v1/library/revisions/" + passage["revision_id"] + "/citation", params={"passage_id": row["id"]})
            assert citation.status_code == 200, citation.text
            assert citation.json()["locators"] == json.loads(row["locators_json"])
    finally:
        repository.index.close()
        target.index.close()
        api.close()
        target_api.close()


def test_api_rejects_expanded_package_and_temporary_scope_before_durable_write(office_extractor, tmp_path):
    api, repository = client_for(tmp_path / "profile", office_extractor)
    path = tmp_path / "expanded.docx"
    path.write_bytes(package(extra={"word/padding.bin": b"A" * 100000}))
    try:
        refused = upload(api, path)
        assert refused.status_code == 413 and refused.json()["error"]["code"] == "office_container_limit"
        temporary = upload(api, path, scope={"kind": "temporary-case", "entity_id": "synthetic-case"})
        assert temporary.status_code == 409 and temporary.json()["error"]["code"] == "unsafe_import_scope"
        assert repository.db.fetch_all("SELECT * FROM knowledge_documents") == []
        assert not list(repository.paths.library.rglob("original.*"))
    finally:
        api.close()
