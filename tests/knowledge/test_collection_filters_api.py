from fastapi.testclient import TestClient

from renulus.server import create_app
from test_acquired import Case


def test_registered_catalogue_api_filters_candidates_before_paging_without_body_reads(tmp_path, monkeypatch):
    case = Case(tmp_path / "collection")
    app = create_app(tmp_path / "profile")
    collection = app.state.services.registry["knowledge_catalogue"]
    collection.root = case.root.resolve()
    client = TestClient(app)
    assert client.post("/api/v1/library/collection/catalogue?source_id=L02").status_code == 200
    def no_file_probe(*args, **kwargs):
        raise AssertionError("Registered listing attempted a collection file read")
    monkeypatch.setattr(collection, "_path", no_file_probe)
    route = "/api/v1/library/collection/catalogue"
    response = client.get(route, params={"source_id": "L02", "eligibility": "inspection_required", "limit": 1})
    assert response.status_code == 200
    page = response.json()
    assert page["total"] == 1 and len(page["entries"]) == 1
    assert page["entries"][0]["eligibility"] == "inspection_required"
    assert client.get(route, params={"source_id": "L02", "eligibility": "inspection_required", "query": "SYNTHETIC_MISSING_%"}).json()["total"] == 0
    assert client.get(route, params={"source_id": "L02", "eligibility": "inspection_required", "offset": 1}).json()["entries"] == []
    assert app.state.services.registry["knowledge"].list_documents()["documents"] == []
    for params in ({"eligibility": "unsupported"}, {"query": "x" * 201}, {"offset": -1}, {"limit": 1001}):
        assert client.get(route, params=params).status_code == 422
