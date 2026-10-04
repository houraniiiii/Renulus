from fastapi.testclient import TestClient

from renulus.server import create_app
from test_acquired import Case
from test_repository import SyntheticExtractor, SyntheticEmbedder


def test_existing_api_inspects_deliberate_selection_and_preserves_scope_and_batch_limits(tmp_path):
    case = Case(tmp_path / "collection")
    for item in case.items:
        item["topics"] = [{"topic_id": "T21", "topic": "Kidney transplantation"}]
    case.write()
    app = create_app(tmp_path / "profile")
    repository = app.state.services.registry["knowledge"]
    repository.extractor, repository.embedder = SyntheticExtractor(), SyntheticEmbedder()
    collection = app.state.services.registry["knowledge_catalogue"]
    collection.root = case.root.resolve()
    with TestClient(app) as api:
        app.state.services.registry["knowledge_worker"].stop()
        registered = api.post("/api/v1/library/collection/catalogue?source_id=L02")
        assert registered.status_code == 200 and registered.json()["catalogued"] == 2
        entries = api.get("/api/v1/library/collection/catalogue?source_id=L02").json()["entries"]
        entry = next(e for e in entries if e["eligibility"] == "inspection_required")
        assert not entry["rights"]["embedding"]
        assert entry["metadata"]["topic_ids"] == ["T21"]
        body = {"entry_ids": [entry["id"]], "scope": {"kind": "temporary-case"}}
        rejected = api.post("/api/v1/library/collection/import", json=body)
        assert rejected.status_code == 409 and not repository.list_documents()["documents"]
        body["scope"] = {"kind": "personal-library"}
        excessive = api.post("/api/v1/library/collection/import", json={**body, "entry_ids": [entry["id"]] * 251})
        assert excessive.status_code == 422 and not repository.list_documents()["documents"]
        imported = api.post("/api/v1/library/collection/import", json=body)
        assert imported.status_code == 202 and imported.json()["queued"] == 1
        first = imported.json()["results"][0]
        repeated = api.post("/api/v1/library/collection/import", json=body).json()["results"][0]
        assert repeated["job"]["id"] == first["job"]["id"]
        inspected = next(e for e in api.get("/api/v1/library/collection/catalogue?source_id=L02").json()["entries"] if e["id"] == entry["id"])
        assert inspected["eligibility"] == "eligible" and inspected["rights"]["embedding"]
        assert inspected["processing_status"] == "queued" and not inspected["metadata"]["latest_final_verified"]
        assert inspected["metadata"]["original_sha256"] == case.items[0]["sha256"]
        assert inspected["metadata"]["topic_ids"] == ["T21"]
        repository.run_job(first["job"]["id"])
        assert repository.get_job(first["job"]["id"])["state"] == "ready"
        query = {"query": "transplant rejection", "scope": {"kind": "study"}, "topic_id": "T21"}
        retrieved = api.post("/api/v1/library/retrieve", json=query)
        assert retrieved.status_code == 200
        assert {passage["document_id"] for passage in retrieved.json()["passages"]} == {first["document_id"]}
        assert api.post("/api/v1/library/retrieve", json={**query, "topic_id": "T08"}).json()["passages"] == []
        assert api.post("/api/v1/library/retrieve", json={**query, "current_only": True}).json()["passages"] == []
