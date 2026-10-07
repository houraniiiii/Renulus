"""Synthetic acquired files, real SQLite review/outbox and Library status seams."""
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from renulus.contracts import ContextScope, Scope
from renulus.knowledge.engines import Extracted
from renulus.knowledge.models import SourceMetadata
from renulus.knowledge.repository import KnowledgeRepository
from renulus.server import create_app
from test_review_currency import reviewed, update
from test_updates import SequenceFetcher, SYNTHETIC_EVIDENCE


ARTICLE = {
    "register_id": "L02",
    "canonical_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC1234567/",
    "pmcid": "PMC1234567",
}
BINDINGS = [("PMC1234567.1", "a" * 64), ("PMC1234567.1", "b" * 64),
            ("PMC1234567.2", "a" * 64)]


def test_acquired_versions_keep_separate_review_statuses_and_v1_outbox_after_restart(tmp_path):
    service = create_app(tmp_path).state.services.registry["updates"]
    events = []
    service.services.registry["update_source_status"] = lambda event: events.append(event) or {
        "state": "no-match", "revisions": 0}
    targets = [{**ARTICLE, "edition": edition, "original_sha256": digest}
               for edition, digest in BINDINGS] + [ARTICLE]
    results = []
    initial = {"publication_status": "final", "content_reviewed": True, "access_changed": True}
    for index, target in enumerate(targets):
        identifier = update(service, "version-" + str(index), source="L02")
        result = reviewed(service, identifier, target, initial)
        assert result["review"]["target"] == {**target, "topic_ids": [], "locators": []}
        results.append(result)
    states = service.reviews.statuses("L02")
    assert len(states) == len({row["target_key"] for row in states}) == 4
    for result, target, event in zip(results, targets, events):
        assert event["contract_version"] == 1
        assert event["event_id"] == result["review"]["id"]
        assert event["identity"] == {key: value for key, value in target.items() if key != "register_id"}
        assert event["evidence"]["references"][0]["inspected"] is True
    # Clearing one bound file never merges or clears another file's facts.
    clear = reviewed(service, results[0]["id"], targets[0], {"access_changed": False})
    states = service.reviews.statuses("L02")
    for row in states:
        same_file = (row["target"].get("edition"), row["target"].get("original_sha256")) == BINDINGS[0]
        assert row["status"]["access_changed"] is (not same_file)
        assert row["status"]["publication_status"] == "final"
    assert reviewed(service, results[0]["id"], targets[0], initial)["review"]["id"] == clear["review"]["id"]
    restarted = create_app(tmp_path).state.services.registry["updates"]
    assert restarted.reviews.statuses("L02") == states
    assert restarted.get_entry(results[0]["id"])["review"]["target"]["original_sha256"] == "a" * 64
    stored = [json.loads(row["payload_json"]) for row in restarted.db.fetch_all(
        "SELECT payload_json FROM update_library_changes ORDER BY rowid")]
    assert stored == events


@pytest.mark.parametrize("binding", [
    {"edition": "PMC1234567.1"}, {"original_sha256": "a" * 64},
    {"edition": "", "original_sha256": "a" * 64},
    {"edition": " \t", "original_sha256": "a" * 64},
    {"edition": "e" * 161, "original_sha256": "a" * 64},
    {"edition": "PMC1234567.1", "original_sha256": "A" * 64},
    {"edition": "PMC1234567.1", "original_sha256": "g" * 64},
    {"edition": "PMC1234567.1", "original_sha256": "a" * 63},
    {"edition": "PMC1234567.1", "original_sha256": "a" * 65},
    {"edition": None, "original_sha256": "a" * 64},
])
def test_invalid_acquired_binding_leaves_review_and_outbox_untouched(tmp_path, binding):
    app = create_app(tmp_path)
    service = app.state.services.registry["updates"]
    identifier = update(service, source="L02")
    result = TestClient(app).post(f"/api/v1/updates/entries/{identifier}/review", json={
        "summary": "Synthetic inspected evidence", "state": "reviewed",
        "target": {**ARTICLE, **binding}, "changes": {"content_reviewed": True},
        "evidence": SYNTHETIC_EVIDENCE})
    assert result.status_code == 422
    assert result.json()["error"]["code"] == "invalid_request"
    assert service.get_entry(identifier)["review_state"] == "pending"
    assert service.reviews.statuses("L02") == []
    assert service.db.fetch_one("SELECT count(*) AS total FROM update_reviews")["total"] == 0
    assert service.db.fetch_one("SELECT count(*) AS total FROM update_library_changes")["total"] == 0


def test_trimmed_edition_and_absent_binding_preserve_legacy_review(tmp_path):
    service = create_app(tmp_path).state.services.registry["updates"]
    identifier = update(service, source="L02")
    result = reviewed(service, identifier, {**ARTICLE, "edition": "  " + "e" * 160 + "  ",
        "original_sha256": "0" * 64}, {"content_reviewed": True})
    assert result["review"]["target"]["edition"] == "e" * 160
    legacy = update(service, "legacy-unbound", source="L02")
    result = reviewed(service, legacy, {**ARTICLE, "edition": None, "original_sha256": None},
                      {"publication_status": "draft"})
    assert "edition" not in result["review"]["target"]
    assert "original_sha256" not in result["review"]["target"]


def test_library_version_choices_round_trip_through_actual_review_api(tmp_path, monkeypatch):
    monkeypatch.setattr("renulus.server.MODULE_ORDER", ("content", "knowledge", "updates"))
    app = create_app(tmp_path)
    service = app.state.services.registry["updates"]
    repository = library(service)
    documents = []
    for edition, digest in BINDINGS:
        documents.append(repository.import_text("SYNTHETIC_PRIVATE_ACQUIRED_BODY_" + digest[0] + edition,
            title="Synthetic acquired choice " + digest[0] + edition,
            metadata=SourceMetadata(source_id="L02", canonical_url=ARTICLE["canonical_url"],
                pmcid=ARTICLE["pmcid"], edition=edition, original_sha256=digest, asset_role=["acquired-jats"])))
    client = TestClient(app)
    choices = client.get("/api/v1/library/source-versions", params={"source_id": "L02",
        "canonical_url": ARTICLE["canonical_url"], "pmcid": ARTICLE["pmcid"]})
    assert choices.status_code == 200
    page = choices.json()
    assert page["limit"] == 100 and not page["truncated"] and len(page["versions"]) == 3
    assert "Synthetic acquired choice" in choices.text
    assert "SYNTHETIC_PRIVATE_ACQUIRED_BODY_" not in choices.text and "original_path" not in choices.text
    selected = next(version for version in page["versions"] if version["original_sha256"] == "b" * 64)
    identifier = update(service, "selected-library-copy", source="L02")
    result = client.post(f"/api/v1/updates/entries/{identifier}/review", json={
        "summary": "Synthetic educational review of the chosen acquired copy", "state": "reviewed",
        "target": {**ARTICLE, "edition": selected["edition"], "original_sha256": selected["original_sha256"]},
        "changes": {"publication_status": "final", "latest_final_verified": True, "content_reviewed": True},
        "evidence": SYNTHETIC_EVIDENCE})
    assert result.status_code == 200 and result.json()["review"]["library_sync_state"] == "applied"
    for document, (edition, digest) in zip(documents, BINDINGS):
        metadata = repository.get_document(document["document_id"])["revisions"][0]["metadata"]
        assert metadata["content_reviewed"] is (document["revision_id"] == selected["revision_id"])
        assert metadata["edition"] == edition and metadata["original_sha256"] == digest


class SyntheticExtractor:
    def extract_file(self, path, title):
        text = path.read_text(encoding="utf-8")
        return Extracted([{"text": text, "context_text": text, "headings": [],
            "locators": [{"page": None, "char_span": [0, len(text)], "item_ref": "#/texts/0"}]}],
            {"synthetic": True})


class SyntheticEmbedder:
    model_id, dimensions, max_tokens = "synthetic-384", 384, 512

    def embed(self, texts, *, query=False):
        return [[1.0] + [0.0] * 383 for _ in texts]


def library(service):
    # Actual canonical SQLite/Library journal and LanceDB, with controlled
    # extraction/embeddings. This is application-rule proof, no model/network proof.
    root = Path(__file__).parents[2] / "runtime/renulus/knowledge"
    service.db.apply_migration("knowledge-001", (root / "schema.sql").read_text())
    for migration in sorted((root / "migrations").glob("*.sql")):
        service.db.apply_migration("knowledge-" + migration.stem, migration.read_text())
    repository = KnowledgeRepository(service.services, extractor=SyntheticExtractor(),
                                    embedder=SyntheticEmbedder())
    service.services.registry["knowledge"] = repository
    return repository


@pytest.mark.parametrize("restriction", ["retracted", "repository_removed", "access_changed"])
def test_real_library_outbox_promotes_and_clears_only_exact_file_but_restricts_all_versions(tmp_path, restriction):
    service = create_app(tmp_path).state.services.registry["updates"]
    repository = library(service)
    documents = []
    targets = [{**ARTICLE, "edition": edition, "original_sha256": digest}
               for edition, digest in BINDINGS]
    for index, target in enumerate(targets):
        metadata = SourceMetadata(source_id="L02", canonical_url=ARTICLE["canonical_url"],
            pmcid=ARTICLE["pmcid"], edition=target["edition"], original_sha256=target["original_sha256"],
            asset_role=["acquired-jats"], topic_ids=["IgAN" if index == 0 else "dialysis"])
        documents.append(repository.import_text("Synthetic transplant version " + str(index),
            scope=ContextScope(kind=Scope.LIBRARY), metadata=metadata))
        assert documents[-1]["status"] == "ready", documents[-1]
    currency = {"publication_status": "final", "latest_final_verified": True, "content_reviewed": True}
    identifier = update(service, "unbound-currency", source="L02")
    assert reviewed(service, identifier, ARTICLE, currency)["review"]["library_sync_state"] == "no-match"
    identifier = update(service, "exact-currency", source="L02")
    assert reviewed(service, identifier, targets[0], currency)["review"]["library_sync_state"] == "applied"
    study = ContextScope(kind=Scope.STUDY)
    current = repository.retrieve("transplant", scope=study, current_only=True)["passages"]
    assert {row["document_id"] for row in current} == {documents[0]["document_id"]}
    notice = update(service, "publication-restriction", source="L02")
    restricted_target = {**targets[0], "topic_ids": ["IgAN"]}
    reviewed(service, notice, restricted_target, {restriction: True})
    assert service.reviews.sync_entry(notice)["changes"][0]["result"]["revisions"] == 3
    assert repository.retrieve("transplant", scope=study, current_only=True)["passages"] == []
    clear = update(service, "exact-clear", source="L02")
    reviewed(service, clear, targets[0], {restriction: False, **currency})
    assert service.reviews.sync_entry(clear)["changes"][0]["result"]["revisions"] == 1
    for index, document in enumerate(documents):
        metadata = repository.get_document(document["document_id"])["revisions"][0]["metadata"]
        assert metadata[restriction] is (index != 0)
        assert metadata["latest_final_verified"] is (index == 0)
    current = repository.retrieve("transplant", scope=study, current_only=True)["passages"]
    assert {row["document_id"] for row in current} == {documents[0]["document_id"]}


@pytest.mark.asyncio
async def test_observed_publication_bytes_invalidate_every_bound_and_legacy_currency_review(tmp_path):
    service = create_app(tmp_path).state.services.registry["updates"]
    candidate = service.publications.candidates("K01")[0]
    publication = service.publications.track("K01", candidate["url"], "Synthetic digest permission")
    target = {"register_id": "K01", "canonical_url": candidate["url"]}
    targets = [{**target, "edition": edition, "original_sha256": digest}
               for edition, digest in BINDINGS] + [target]
    targets[0] = {**targets[0], "canonical_url": candidate["url"] + "#methods"}
    for index, exact in enumerate(targets):
        identifier = update(service, "currency-" + str(index), source="K01")
        reviewed(service, identifier, exact, {"publication_status": "final", "publication_date": "2024-03-01",
            "latest_final_verified": True, "content_reviewed": True, "correction": "Synthetic dated correction"})
    other = update(service, "unrelated-publication", source="K01")
    reviewed(service, other, {**target, "canonical_url": "https://kdigo.org/synthetic-other.pdf"},
             {"publication_status": "final", "latest_final_verified": True, "content_reviewed": True})
    service.fetcher = SequenceFetcher([b"%PDF-1.7 synthetic baseline", b"%PDF-1.7 synthetic changed bytes"])
    assert (await service.publications.check(publication["id"], True))["state"] == "baseline"
    assert (await service.publications.check(publication["id"], True))["state"] == "changed"
    states = service.reviews.statuses("K01")
    assert len(states) == 5
    for row in states:
        same_article = row["target"]["canonical_url"].split("#", 1)[0] == candidate["url"]
        assert row["status"]["latest_final_verified"] is (not same_article)
        assert row["status"]["content_reviewed"] is (not same_article)
        assert row["status"]["publication_status"] == "final"
        if same_article:
            assert row["status"]["publication_date"] == "2024-03-01"
            assert row["status"]["correction"] == "Synthetic dated correction"
    observed = json.loads(service.db.fetch_one(
        "SELECT payload_json FROM update_library_changes WHERE id LIKE 'observed:%'")["payload_json"])
    assert observed["identity"] == {"canonical_url": candidate["url"]}
    assert observed["evidence"]["kind"] == "publication-digest"
    assert observed["changes"] == {"latest_final_verified": False, "content_reviewed": False}
