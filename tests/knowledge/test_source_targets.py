from fastapi.testclient import TestClient

from renulus.server import create_app
from test_repository import repository, import_note
from test_source_version import acquired


def test_version_choices_exclude_bodies_deleted_reserved_and_unbound_files(repository):
    current = import_note(repository, "PRIVATE_SYNTHETIC_BODY", metadata=acquired("PMC1234567.1", "a" * 64), process=False)
    gone = import_note(repository, "DELETED_SYNTHETIC_BODY", metadata=acquired("PMC1234567.2", "b" * 64), process=False)
    repository.delete_document(gone["document_id"])
    import_note(repository, "RESERVED_SYNTHETIC_BODY", metadata=acquired("PMC1234567.3", "c" * 64), reserved=True, process=False)
    import_note(repository, "UNBOUND_SYNTHETIC_BODY", metadata=acquired("PMC1234567.4", None), process=False)
    import_note(repository, "OTHER_ARTICLE_BODY", process=False)
    result = repository.source_status.version_targets("L02", {"pmcid": "PMC1234567"})
    assert result["limit"] == 100 and not result["truncated"]
    assert len(result["versions"]) == 1
    version = result["versions"][0]
    assert version["document_id"] == current["document_id"]
    assert version["original_sha256"] == "a" * 64 and version["status"] == "queued"
    assert set(version) == {"document_id", "revision_id", "title", "status", "edition",
                           "original_sha256", "canonical_url", "doi", "pmid", "pmcid"}
    assert repository.source_status.version_targets("L02", {"pmcid": "PMC9876543"})["versions"] == []


def test_version_choice_limit_is_enforced_before_metadata_deserialization(repository):
    for n in range(101):
        import_note(repository, "Synthetic version choice", process=False,
            metadata=acquired("PMC1234567." + str(n + 1), format(n, "064x")))
    result = repository.source_status.version_targets("L02", {"pmcid": "PMC1234567"})
    assert result["truncated"] and len(result["versions"]) == 100
    assert len({item["revision_id"] for item in result["versions"]}) == 100


def test_production_version_choice_route_validates_exact_identity_without_worker_startup(tmp_path):
    app = create_app(tmp_path / "profile")
    knowledge = app.state.services.registry["knowledge"]
    import_note(knowledge, "Synthetic kidney source", process=False,
        metadata=acquired("PMC1234567.1", "a" * 64))
    client = TestClient(app)
    route = "/api/v1/library/source-versions"
    response = client.get(route, params={"source_id": "L02", "pmcid": "PMC1234567"})
    assert response.status_code == 200 and len(response.json()["versions"]) == 1
    for params in ({"source_id": "L02"}, {"source_id": "family", "pmcid": "PMC1234567"},
                   {"source_id": "L02", "pmcid": "invalid"},
                   {"source_id": "L02", "pmcid": "PMC1234567", "canonical_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC9876543/"}):
        assert client.get(route, params=params).status_code == 422
