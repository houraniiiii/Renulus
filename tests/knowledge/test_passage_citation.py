"""Exact citation API journeys with SQLite and controlled synthetic extraction."""
import io
import json

from fastapi.testclient import TestClient
import pytest

from renulus.contracts import ApiError
from renulus.knowledge.engines import Extracted
from renulus.knowledge.models import own_text_rights
from renulus.server import create_app
from test_offline_engines import _pdf_bytes
from test_repository import SyntheticEmbedder
from test_source_status import event


LOCATORS = [
    [{"item_ref": "#/texts/0", "page": 2, "char_span": [0, 25]}],
    [{"item_ref": "#/texts/1", "page": 2, "char_span": [26, 50]},
     {"item_ref": "#/texts/2", "page": 3, "char_span": [0, 12]}],
]


class CitationExtractor:
    def extract_file(self, path, title):
        return Extracted([
            {"text": text, "context_text": text, "headings": [], "locators": locations}
            for text, locations in zip(["Synthetic glomerular note", "Synthetic dialysis note"], LOCATORS)
        ], {"synthetic": True})


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path / "profile")
    repository = app.state.services.registry["knowledge"]
    repository.extractor, repository.embedder = CitationExtractor(), SyntheticEmbedder()
    with TestClient(app) as api:
        repository.services.registry["knowledge_worker"].stop()
        yield api, repository


def import_source(client, key, **options):
    api, repository = client
    response = api.post("/api/v1/library/import/text", json={
        "text": "Synthetic original for citation rules", "title": "Synthetic source " + key,
        "scope": {"kind": "personal-library"}, "idempotency_key": key, **options})
    assert response.status_code == 202
    imported = response.json()
    assert repository.run_job(imported["job"]["id"])["state"] == "ready"
    return imported


def retrieved(api):
    response = api.post("/api/v1/library/retrieve", json={
        "query": "Synthetic", "scope": {"kind": "study"}})
    assert response.status_code == 200
    return response.json()["passages"]


def test_exact_passage_keeps_its_locators_separate_from_other_passages_on_the_same_page(client):
    api, _ = client
    imported = import_source(client, "exact-locations")
    hit = next(p for p in retrieved(api) if p["text"] == "Synthetic glomerular note")
    path = "/api/v1/library/revisions/" + imported["revision_id"] + "/citation"
    response = api.get(path, params={"passage_id": hit["id"], "page": 2})
    assert response.status_code == 200
    citation = response.json()
    assert citation["locators"] == LOCATORS[0]
    assert citation["passage_id"] == hit["id"]
    assert citation["document_revision"] == hit["document_revision"]
    assert citation["original_url"] == hit["original_url"]
    assert "passage_id=" + hit["id"] in citation["viewer_url"]

    # Legacy revision/page lookup deliberately retains the broader locations.
    legacy = api.get(path, params={"page": 2}).json()
    assert legacy["locators"] == [LOCATORS[0][0], LOCATORS[1][0]]
    assert "passage_id" not in legacy
    assert api.get(path).json()["locators"] == LOCATORS[0] + LOCATORS[1]


@pytest.mark.parametrize("changes", [
    {"retracted": True}, {"superseded": True}, {"access_changed": True},
    {"repository_removed": True}, {"publication_status": "draft"},
    {"publication_status": "preprint"}, {"replaced_topics": ["dialysis"]},
    {"excluded_pages": [2]},
])
def test_bound_passage_rechecks_current_eligibility_before_page_recovery(client, changes):
    api, repository = client
    imported = import_source(client, "eligibility-change", metadata={
        "source_id": "L02", "doi": "10.1234/synthetic-citation"})
    hit = next(p for p in retrieved(api) if p["text"] == "Synthetic glomerular note")
    assert repository.update_source_status(event("synthetic-notice",
        {"doi": "10.1234/synthetic-citation"}, changes))["revisions"] == 1
    path = "/api/v1/library/revisions/" + imported["revision_id"] + "/citation"
    for page in (None, 2, 99):
        params = {"passage_id": hit["id"]}
        if page is not None:
            params["page"] = page
        response = api.get(path, params=params)
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "passage_missing"
        assert "locators" not in response.json()
    # Existing historical revision lookup keeps its pre-passage contract.
    assert api.get(path).status_code == 200


def test_historical_passage_stays_pinned_and_other_revisions_or_documents_cannot_supply_it(client):
    api, _ = client
    initial = import_source(client, "cited-original")
    hit = next(p for p in retrieved(api) if p["document_revision"] == initial["revision_id"])
    replacement = import_source(client, "new-revision", document_id=initial["document_id"])
    unrelated = import_source(client, "unrelated-source")
    path = "/api/v1/library/revisions/" + initial["revision_id"] + "/citation"
    assert api.get(path, params={"passage_id": hit["id"]}).json()["locators"] == hit["locators"]
    for revision in (replacement["revision_id"], unrelated["revision_id"]):
        response = api.get("/api/v1/library/revisions/" + revision + "/citation",
                           params={"passage_id": hit["id"], "page": 99})
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "passage_missing"
    assert api.delete("/api/v1/library/documents/" + initial["document_id"]).status_code == 200
    response = api.get(path, params={"passage_id": hit["id"], "page": 2})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "citation_missing"


def test_missing_page_checks_only_the_bound_passage_and_recovery_retains_it(client):
    api, _ = client
    imported = import_source(client, "bound-page")
    hit = next(p for p in retrieved(api) if p["text"] == "Synthetic glomerular note")
    path = "/api/v1/library/revisions/" + imported["revision_id"] + "/citation"
    # Page 3 exists elsewhere in the revision, but not in the cited passage.
    assert api.get(path, params={"page": 3}).status_code == 200
    missing = api.get(path, params={"page": 3, "passage_id": hit["id"]})
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "page_missing"
    recovery = api.get(path, params={"passage_id": hit["id"]}).json()
    assert recovery["page"] is None
    assert recovery["locators"] == LOCATORS[0]
    assert recovery["passage_id"] == hit["id"]
    unknown = api.get(path, params={"page": 3, "passage_id": "passage_" + "0" * 32})
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "passage_missing"


@pytest.mark.parametrize("passage_id", [
    "", " ", "../passage", "passage_" + "a" * 31,
    "passage_" + "A" * 32, "passage_" + "a" * 32 + "\n", "x" * 1000,
])
def test_malformed_passage_identifiers_do_not_fall_back_to_revision_lookup(client, passage_id):
    api, repository = client
    imported = import_source(client, "invalid-passage")
    response = api.get("/api/v1/library/revisions/" + imported["revision_id"] + "/citation",
                       params={"passage_id": passage_id})
    assert response.status_code == 422
    assert "locators" not in response.json()
    with pytest.raises(ApiError) as caught:
        repository.citation(imported["revision_id"], passage_id=passage_id)
    assert caught.value.code == "invalid_passage_id"


@pytest.mark.parametrize("restriction", ["reserved", "display", "index", "embedding", "model_input"])
def test_reserved_or_permission_revoked_passage_cannot_supply_an_exact_citation(client, restriction):
    api, repository = client
    imported = import_source(client, "restricted-passage")
    hit = retrieved(api)[0]
    # Fixture-only revocation: no public per-operation rights editor exists.
    if restriction == "reserved":
        repository.db.execute("UPDATE knowledge_documents SET reserved=1 WHERE id=?", (imported["document_id"],))
    else:
        rights = own_text_rights().model_dump()
        rights[restriction] = False
        repository.db.execute("UPDATE knowledge_revisions SET rights_json=? WHERE id=?",
                              (json.dumps(rights), imported["revision_id"]))
    response = api.get("/api/v1/library/revisions/" + imported["revision_id"] + "/citation",
                       params={"passage_id": hit["id"], "page": 99})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "passage_missing"


@pytest.mark.parametrize("kind,media_type,page", [
    ("txt", "text/plain", None), ("pdf", "application/pdf", 1), ("png", "image/png", 1),
])
def test_import_retrieve_exact_citation_original_roundtrip_across_synthetic_formats(client, kind, media_type, page):
    api, repository = client
    if kind == "pdf":
        original = _pdf_bytes("Synthetic source citation fixture")
    elif kind == "png":
        from PIL import Image
        output = io.BytesIO()
        Image.new("RGB", (16, 16), "white").save(output, format="PNG")
        original = output.getvalue()
    else:
        original = b"Synthetic source citation fixture"
    locations = [{"item_ref": "#/texts/7", "page": page, "char_span": [4, 18]}]
    class FormatExtractor:
        def extract_file(self, path, title):
            return Extracted([{"text": "Synthetic source passage", "context_text": "Synthetic source passage",
                              "headings": [], "locators": locations}], {"synthetic": True})
    repository.extractor = FormatExtractor()
    response = api.post("/api/v1/library/import/file", content=original, headers={
        "x-renulus-filename": "synthetic." + kind,
        "x-renulus-import-options": json.dumps({"scope": {"kind": "personal-library"},
            "idempotency_key": "format-" + kind, "rights": own_text_rights().model_dump()})})
    assert response.status_code == 202
    imported = response.json()
    assert repository.run_job(imported["job"]["id"])["state"] == "ready"
    hit = retrieved(api)[0]
    params = {"passage_id": hit["id"]}
    if page is not None:
        params["page"] = page
    response = api.get("/api/v1/library/revisions/" + hit["document_revision"] + "/citation", params=params)
    assert response.status_code == 200
    citation = response.json()
    assert citation["locators"] == locations
    assert citation["page"] == page
    assert citation["passage_id"] == hit["id"]
    served = api.get(citation["original_url"])
    assert served.status_code == 200
    assert served.content == original
    assert served.headers["content-type"].startswith(media_type)
