"""Correction eligibility and immutable history; all publisher material is synthetic."""
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from renulus.contracts import ApiError, ContextScope, Scope
from renulus.knowledge.models import SourceMetadata
from renulus.server import create_app
from renulus.storage import utc_now
from test_acquired_version_currency import ARTICLE, library
from test_review_currency import reviewed, update


CURRENCY = {"publication_status": "final", "latest_final_verified": True, "content_reviewed": True}


def copies(service):
    repository = library(service)
    targets = [{**ARTICLE, "edition": "Synthetic edition", "original_sha256": digest * 64}
               for digest in ("a", "b")]
    documents = []
    for index, target in enumerate(targets):
        document = repository.import_text("Synthetic corrected-copy evidence " + str(index),
            metadata=SourceMetadata(source_id="L02", canonical_url=ARTICLE["canonical_url"],
                pmcid=ARTICLE["pmcid"], edition=target["edition"], original_sha256=target["original_sha256"],
                asset_role=["acquired-jats"], topic_ids=["IgAN"]))
        assert document["status"] == "ready", document
        documents.append(document)
        reviewed(service, update(service, "copy-" + str(index), source="L02"), target, CURRENCY)
    return repository, targets, documents


def current(repository):
    return {passage["document_id"] for passage in repository.retrieve("Synthetic evidence",
        scope=ContextScope(kind=Scope.STUDY), current_only=True)["passages"]}


def test_correction_revokes_all_copies_and_only_exact_corrected_copy_can_be_reconfirmed(tmp_path):
    service = create_app(tmp_path).state.services.registry["updates"]
    repository, targets, documents = copies(service)
    assert current(repository) == {document["document_id"] for document in documents}
    rights = service.db.fetch_all("SELECT id,rights_json FROM knowledge_revisions ORDER BY id")
    notice = update(service, "correction", source="L02")
    result = reviewed(service, notice, targets[0], {**CURRENCY, "correction": "Synthetic corrected recommendation"})
    assert result["review"]["changes"]["latest_final_verified"] is False
    assert result["review"]["changes"]["content_reviewed"] is False
    assert current(repository) == set()
    for document in documents:
        metadata = repository.get_document(document["document_id"])["revisions"][0]["metadata"]
        assert not metadata["latest_final_verified"] and not metadata["content_reviewed"]
        assert metadata["correction"] == "Synthetic corrected recommendation"
    unbound = update(service, "unbound-confirmation", source="L02")
    before = service.db.fetch_all("SELECT * FROM update_library_changes ORDER BY rowid")
    with pytest.raises(ApiError) as error:
        reviewed(service, unbound, ARTICLE, CURRENCY)
    assert error.value.code == "corrected_copy_review_required"
    assert service.get_entry(unbound)["review_state"] == "pending"
    assert service.db.fetch_all("SELECT * FROM update_library_changes ORDER BY rowid") == before
    corrected = update(service, "exact-confirmation", source="L02")
    reviewed(service, corrected, targets[1], CURRENCY)
    assert current(repository) == {documents[1]["document_id"]}
    assert service.db.fetch_all("SELECT id,rights_json FROM knowledge_revisions ORDER BY id") == rights
    # Replaying a prior request cannot undo a newer revocation of this copy.
    later = update(service, "second-correction", source="L02")
    reviewed(service, later, targets[0], {"correction": "Synthetic second correction"})
    reviewed(service, corrected, targets[1], CURRENCY)
    assert current(repository) == set()
    assert all(not row["status"]["content_reviewed"] for row in service.reviews.statuses("L02"))


@pytest.mark.parametrize("changes", [
    {"replaced_topics": ["IgAN"]}, {"superseded": True}, {"retracted": True},
    {"publication_status": "draft"}, {"publication_status": "preprint"},
], ids=["chapter-replacement", "whole-replacement", "retraction", "draft", "preprint"])
def test_material_source_states_revoke_review_without_touching_unrelated_publication(tmp_path, changes):
    service = create_app(tmp_path).state.services.registry["updates"]
    repository, targets, documents = copies(service)
    other = {**ARTICLE, "canonical_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC7654321/",
             "pmcid": "PMC7654321", "edition": "Other edition", "original_sha256": "c" * 64}
    unrelated = repository.import_text("Synthetic unrelated evidence", metadata=SourceMetadata(
        source_id="L02", canonical_url=other["canonical_url"], pmcid=other["pmcid"],
        edition=other["edition"], original_sha256=other["original_sha256"], asset_role=["acquired-jats"]))
    reviewed(service, update(service, "other", source="L02"), other, CURRENCY)
    identifier = update(service, "material-change", source="L02")
    result = reviewed(service, identifier, targets[0], changes)
    assert result["review"]["changes"]["content_reviewed"] is False
    assert current(repository) == {unrelated["document_id"]}
    for document in documents:
        metadata = repository.get_document(document["document_id"])["revisions"][0]["metadata"]
        assert not metadata["content_reviewed"] and not metadata["latest_final_verified"]
    status = next(row["status"] for row in service.reviews.statuses("L02") if row["target"].get("pmcid") == other["pmcid"])
    assert status["content_reviewed"] and status["latest_final_verified"]


def test_failed_outbox_replays_older_promotion_before_newer_invalidation(tmp_path):
    service = create_app(tmp_path).state.services.registry["updates"]
    first = update(service, "first", source="L02")
    promotion = reviewed(service, first, ARTICLE, CURRENCY)
    assert promotion["review"]["library_sync_state"] == "unavailable"
    second = update(service, "second", source="L02")
    result = reviewed(service, second, ARTICLE, {"correction": "Synthetic correction"})
    assert result["review"]["library_sync_state"] == "failed"
    assert result["review"]["library_sync_error"] == "prior_source_change_pending"
    calls, effective = [], {}
    def apply(event):
        calls.append(event)
        effective.update(event["changes"])
        return {"state": "applied", "event_id": event["event_id"], "revisions": 1}
    service.services.registry["update_source_status"] = apply
    assert all(row["state"] == "applied" for row in service.reviews.sync_entry(second)["changes"])
    assert calls[0]["event_id"] == promotion["review"]["id"]
    assert calls[1]["event_id"] == "invalidate:" + result["review"]["id"]
    assert calls[2]["event_id"] == result["review"]["id"]
    assert not effective["content_reviewed"] and not effective["latest_final_verified"]
    service.reviews.sync_entry(first)
    service.reviews.sync_entry(second)
    assert len(calls) == 3


def test_metadata_detection_revokes_same_article_review_without_claiming_retraction(tmp_path):
    service = create_app(tmp_path).state.services.registry["updates"]
    events = []
    service.services.registry["update_source_status"] = lambda event: events.append(event) or {"state": "applied", "revisions": 1}
    article = {"id": "111111", "source": "MED", "title": "Synthetic original article"}
    first = service.literature.record(article, ["IgAN"], utc_now())
    target = {"register_id": "L03", "canonical_url": "https://europepmc.org/article/MED/111111", "pmid": "111111"}
    reviewed(service, first["entry_id"], target, CURRENCY)
    changed = service.literature.record({**article, "isRetracted": "Y"}, ["IgAN"], utc_now())
    entry = service.get_entry(changed["entry_id"])
    assert changed["state"] == "changed" and entry["review_state"] == "pending" and entry["review"] is None
    status = service.reviews.statuses("L03")[0]["status"]
    assert not status["latest_final_verified"] and not status["content_reviewed"]
    assert "retracted" not in status
    assert events[-1]["changes"] == {"latest_final_verified": False, "content_reviewed": False}
    assert events[-1]["evidence"]["kind"] == "publication-digest"
    service.literature.record({"id": "999999", "source": "MED", "title": "Synthetic separate retraction notice", "isRetracted": "Y"}, [], utc_now())
    assert len(events) == 2  # A new notice cannot infer the affected original.


def test_correction_refreshes_real_feedback_without_rewriting_committed_answers_keys_or_scores(tmp_path, monkeypatch):
    monkeypatch.setattr("renulus.server.MODULE_ORDER", ("content", "assessment", "updates"))
    root = Path(__file__).resolve().parents[2]
    app = create_app(tmp_path, source_root=root)
    content = app.state.services.registry["content"]
    content.install_pack(root / "content/packs/renulus-foundations/1.1.2")
    with TestClient(app) as client:
        started = client.post("/api/v1/assessment/start", json={"idempotency_key": "correction-start", "count": 1, "selector": {"topic_ids": ["T20"]}})
        assert started.status_code == 200, started.text
        session = started.json()
        item = session["current_item"]
        question = content.get_question_version(item["question_id"], int(item["question_version"]))
        request = {"idempotency_key": "correction-answer", "item_id": item["id"], "option_ids": question["correct_option_ids"]}
        answered = client.post("/api/v1/assessment/sessions/" + session["id"] + "/answer", json=request)
        assert answered.status_code == 200, answered.text
        original_result = answered.json()
        db = app.state.services.db
        tables = (("assessment_attempts", "id"), ("assessment_commands", "idempotency_key"),
                  ("assessment_items", "id"), ("learning_evidence", "id"),
                  ("content_question_versions", "question_id,version"))
        snapshots = {table: db.fetch_all("SELECT * FROM " + table + " ORDER BY " + order) for table, order in tables}
        cited = {citation["source_id"] for citation in question["sources"]}
        source = next(row for row in question["source_records"] if row["register_id"] == "K01" and row["id"] in cited)
        service = app.state.services.registry["updates"]
        identifier = update(service, "assessment-correction", source="K01")
        reviewed(service, identifier, {"register_id": "K01", "canonical_url": source["url"]}, {"correction": "Synthetic correction; key re-review remains separate"})
        replay = client.post("/api/v1/assessment/sessions/" + session["id"] + "/answer", json=request).json()
        assert replay["feedback"]["source_currency"]["needs_re_review"] is True
        assert replay["feedback"]["source_currency"]["annotations"][0]["review_state"] == "reviewed"
        assert replay["feedback"]["correct_option_ids"] == original_result["feedback"]["correct_option_ids"]
        assert replay["feedback"]["correct"] == original_result["feedback"]["correct"]
        assert replay["feedback"]["committed_at"] == original_result["feedback"]["committed_at"]
        assert replay["session"]["scores"] == original_result["session"]["scores"]
        assert {table: db.fetch_all("SELECT * FROM " + table + " ORDER BY " + order) for table, order in tables} == snapshots
