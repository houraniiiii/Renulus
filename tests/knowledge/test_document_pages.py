from fastapi.testclient import TestClient

from renulus.knowledge.models import SourceMetadata
from renulus.server import create_app
from test_repository import import_note, repository


def test_pages_deserialize_only_selected_documents_with_stable_ties(repository, monkeypatch):
    notes = [import_note(repository, "Synthetic nephrology page", title="Kidney " + str(n),
                         process=False) for n in range(9)]
    repository.db.execute("UPDATE knowledge_documents SET updated_at=?", ("2026-10-04T18:00:00+00:00",))
    expected = sorted(note["document_id"] for note in notes)
    actual_get = repository.get_document
    inspected = []
    def inspect(identifier, **options):
        inspected.append(identifier)
        return actual_get(identifier, **options)
    monkeypatch.setattr(repository, "get_document", inspect)
    first = repository.list_documents(limit=4)
    second = repository.list_documents(limit=4, offset=4)
    assert [row["id"] for row in first["documents"] + second["documents"]] == expected[:8]
    assert inspected == expected[:8]  # Counts never deserialize the other records.
    assert first["total"] == second["total"] == 9 and first["counts"] == {"queued": 9}
    assert repository.list_documents(limit=4, offset=40)["documents"] == []


def test_filters_follow_latest_revision_and_keep_global_counts(repository):
    cancelled = import_note(repository, "Synthetic note", title="Transplant source", process=False)
    repository.cancel_job(cancelled["job"]["id"])
    import_note(repository, "Replacement note", document_id=cancelled["document_id"],
                title="Transplant replacement", process=False)
    literal = import_note(repository, "Synthetic note", title="100% kidney_5\\review",
                          metadata=SourceMetadata(source_id="E06"), process=False)
    import_note(repository, "Synthetic note", title="1000 kidneyX5 review", process=False)
    gone = import_note(repository, "Synthetic note", title="Deleted study", process=False)
    repository.delete_document(gone["document_id"])
    assert repository.list_documents(limit=20, status="cancelled")["total"] == 0
    for query in ("100%", "kidney_5", "\\review", "E06"):
        result = repository.list_documents(limit=20, query=query, status="queued")
        assert result["total"] == 1 and result["documents"][0]["id"] == literal["document_id"]
        assert result["counts"] == {"queued": 3}
    assert repository.list_documents(query="' OR 1=1 --")["total"] == 0
    legacy = repository.list_documents()
    assert len(legacy["documents"]) == 3 and legacy["limit"] is None
    assert repository.list_documents(include_deleted=True)["counts"] == {"deleted": 1, "queued": 3}


def test_production_document_route_bounds_and_filter_contract(tmp_path):
    app = create_app(tmp_path / "profile")
    repository = app.state.services.registry["knowledge"]
    repository.import_text("Synthetic kidney note", title="Kidney study", process=False)
    client = TestClient(app)  # No worker or CPU helper startup needed for this read.
    response = client.get("/api/v1/library/documents", params={"limit": 25, "offset": 0, "query": "kidney", "status": "queued"})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1 and data["counts"] == {"queued": 1} and len(data["documents"]) == 1
    for params in ({"limit": 0}, {"limit": 101}, {"offset": -1}, {"query": "x" * 201}, {"status": "invented"}):
        failure = client.get("/api/v1/library/documents", params=params)
        assert failure.status_code == 422 and failure.json()["error"]["code"] == "invalid_request"
