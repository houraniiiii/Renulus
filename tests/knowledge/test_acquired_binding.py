"""Synthetic acquired receipts through the real Knowledge journal/import seam."""
import hashlib
import json

import pytest

from renulus.contracts import ContextScope, Scope
from renulus.knowledge.acquired import EVIDENCE_PREFIX
from renulus.retrieval.literature import licensed_article
from test_acquired import Case, offline
from test_repository import repository


REVIEWED = {"publication_status": "final", "latest_final_verified": True,
            "content_reviewed": True}


def binding(case):
    return {"pmcid": "PMC90001", "edition": case.name,
            "original_sha256": case.items[0]["sha256"]}


def review(repository, identifier, identity, changes=None, *, scope=None, evidence=None):
    return repository.update_source_status({"contract_version": 1,
        "event_id": identifier, "source_id": "L02", "identity": identity,
        "changes": REVIEWED if changes is None else changes,
        "scope": scope or {}, "evidence": [{"inspected": True}] if evidence is None else evidence})


def revision(repository, result):
    row = repository.db.fetch_one("SELECT * FROM knowledge_revisions WHERE id=?",
                                  (result["revision_id"],))
    return row, json.loads(row["metadata_json"])


def test_exact_review_before_selected_import_promotes_verified_original_and_queue(repository, tmp_path):
    case = Case(tmp_path / "collection")
    originals = (case.xml.read_bytes(), case.meta.read_bytes())
    collection = case.register(repository)
    assert review(repository, "exact-before-import", binding(case))["state"] == "no-match"
    result = collection.import_selected(case.selected)["results"][0]
    assert result["status"] == "queued"
    row, metadata = revision(repository, result)
    assert metadata["original_sha256"] == case.items[0]["sha256"] != row["sha256"]
    assert metadata["edition"] == case.name
    assert all(metadata[key] == value for key, value in REVIEWED.items())
    evidence = json.loads(next(note[len(EVIDENCE_PREFIX):] for note in metadata["notes"]
                               if note.startswith(EVIDENCE_PREFIX)))
    assert evidence["original_sha256"] == metadata["original_sha256"]
    assert evidence["derivative_sha256"] == row["sha256"]
    assert evidence["currentness"] == "unknown"
    entry = next(entry for entry in collection.list()["entries"] if entry["id"] == case.selected[0])
    assert entry["metadata"]["original_sha256"] == metadata["original_sha256"]
    repository.run_job(result["job"]["id"])
    assert repository.get_job(result["job"]["id"])["state"] == "ready"
    passages = repository.retrieve("transplant", scope=ContextScope(kind=Scope.STUDY),
                                   current_only=True)["passages"]
    assert {passage["document_id"] for passage in passages} == {result["document_id"]}
    repeated = collection.import_selected(case.selected)["results"][0]
    assert repeated["job"]["id"] == result["job"]["id"]
    assert (case.xml.read_bytes(), case.meta.read_bytes()) == originals


def test_one_bound_review_promotes_only_matching_version_in_selected_batch(repository, tmp_path):
    case = Case(tmp_path / "collection")
    other = Case(case.root, version=2)
    assert case.items[0]["sha256"] == other.items[0]["sha256"]
    case.items.extend(other.items)
    review(repository, "version-one-review", binding(case))
    collection = case.register(repository)
    results = collection.import_selected(case.selected)["results"]
    assert len(results) == 2 and all(result["status"] == "queued" for result in results)
    assert len({result["document_id"] for result in results}) == 2
    metadata = {value["edition"]: value for _, value in
                (revision(repository, result) for result in results)}
    assert all(metadata[case.name][key] == value for key, value in REVIEWED.items())
    assert metadata[other.name]["publication_status"] == "unknown"
    assert not metadata[other.name]["latest_final_verified"] and not metadata[other.name]["content_reviewed"]


@pytest.mark.parametrize("review_kind", ["unbound", "other-edition", "other-original", "derivative"])
def test_broad_and_other_file_reviews_allow_import_without_promoting_currentness(repository, tmp_path, review_kind):
    case = Case(tmp_path / "collection")
    identity = binding(case)
    if review_kind == "unbound":
        identity = {"pmcid": "PMC90001"}
    elif review_kind == "other-edition":
        identity["edition"] = "PMC90001.2"
    elif review_kind == "other-original":
        identity["original_sha256"] = "0" * 64
    else:
        text = licensed_article(case.xml.read_bytes(), "PMC90001")["text"]
        identity["original_sha256"] = hashlib.sha256(text.encode()).hexdigest()
        assert identity["original_sha256"] != case.items[0]["sha256"]
    review(repository, "unmatched-review", identity)
    collection = case.register(repository)
    result = collection.import_selected(case.selected)["results"][0]
    assert result["status"] == "queued"
    _, metadata = revision(repository, result)
    assert metadata["original_sha256"] == case.items[0]["sha256"]
    assert metadata["publication_status"] == "unknown"
    assert not metadata["latest_final_verified"] and not metadata["content_reviewed"]


@pytest.mark.parametrize("restriction", ["retracted", "repository_removed", "access_changed"])
@pytest.mark.parametrize("notice_kind", ["unbound", "other-edition-and-topic"])
def test_publication_denials_and_unmatched_clearing_prevent_selected_import(repository, tmp_path, restriction, notice_kind):
    case = Case(tmp_path / "collection")
    review(repository, "exact-positive", binding(case))
    identity, scope = {"pmcid": "PMC90001"}, {}
    if notice_kind == "other-edition-and-topic":
        identity = {**binding(case), "edition": "PMC90001.2", "original_sha256": "0" * 64}
        scope = {"topic_ids": ["unrelated-topic"]}
    review(repository, "publication-denial", identity, {restriction: True}, scope=scope)
    review(repository, "unbound-clearing", {"pmcid": "PMC90001"},
           {restriction: False, **REVIEWED})
    review(repository, "other-file-clearing", {**binding(case), "original_sha256": "1" * 64},
           {restriction: False, **REVIEWED})
    collection = case.register(repository)
    result = collection.import_selected(case.selected)["results"][0]
    assert result["code"] == "article_status_unavailable"
    assert repository.list_documents()["documents"] == []
    assert repository.db.fetch_all("SELECT id FROM knowledge_jobs") == []


@pytest.mark.parametrize("restriction", ["retracted", "repository_removed", "access_changed"])
def test_exact_review_can_clear_publication_restriction_before_import(repository, tmp_path, restriction):
    case = Case(tmp_path / "collection")
    review(repository, "publication-denial", {"pmcid": "PMC90001"}, {restriction: True})
    review(repository, "exact-clearing", binding(case), {restriction: False, **REVIEWED})
    collection = case.register(repository)
    result = collection.import_selected(case.selected)["results"][0]
    assert result["status"] == "queued"
    _, metadata = revision(repository, result)
    assert not metadata[restriction]
    assert all(metadata[key] == value for key, value in REVIEWED.items())


@pytest.mark.parametrize("notice_kind,blocked", [("unbound", True), ("exact", True), ("other-edition", False)])
def test_supersession_is_version_specific_when_notice_has_a_binding(repository, tmp_path, notice_kind, blocked):
    case = Case(tmp_path / "collection")
    identity = {"pmcid": "PMC90001"} if notice_kind == "unbound" else binding(case)
    if notice_kind == "other-edition":
        identity["edition"] = "PMC90001.2"
    review(repository, "supersession", identity, {"superseded": True})
    collection = case.register(repository)
    result = collection.import_selected(case.selected)["results"][0]
    if blocked:
        assert result["code"] == "article_status_unavailable"
        assert repository.list_documents()["documents"] == []
    else:
        assert result["status"] == "queued"
        assert not revision(repository, result)[1]["superseded"]


@pytest.mark.parametrize("bound", [False, True])
@pytest.mark.parametrize("unknown", [False, True])
def test_publication_currentness_invalidations_survive_unbound_positive_retry(repository, tmp_path, bound, unknown):
    case = Case(tmp_path / "collection")
    review(repository, "exact-review", binding(case))
    identity = {"pmcid": "PMC90001"}
    if bound:
        identity = {**binding(case), "edition": "PMC90001.2"}
    changes = {"latest_final_verified": False, "content_reviewed": False}
    if unknown:
        changes["publication_status"] = "unknown"
    review(repository, "invalidation", identity, changes,
           evidence=[{"inspected": True}] if unknown else [])
    review(repository, "unbound-positive-retry", {"pmcid": "PMC90001"})
    collection = case.register(repository)
    result = collection.import_selected(case.selected)["results"][0]
    assert result["status"] == "queued"
    _, metadata = revision(repository, result)
    assert metadata["publication_status"] == ("unknown" if unknown else "final")
    assert not metadata["latest_final_verified"] and not metadata["content_reviewed"]


def test_changed_original_with_same_derivative_requires_a_new_exact_review(repository, tmp_path):
    case = Case(tmp_path / "collection")
    old_hash = case.items[0]["sha256"]
    review(repository, "review-original", binding(case))
    collection = case.register(repository)
    first = collection.import_selected(case.selected)["results"][0]
    assert first["status"] == "queued"
    case.xml.write_bytes(case.xml.read_bytes().replace(b"FIGURE_SENTINEL", b"UPDATED_FIGURE_SENTINEL"))
    case.record["xml_url"] = case.record["xml_url"].split("?")[0] + "?md5=" + hashlib.md5(case.xml.read_bytes()).hexdigest()
    case.change_record()
    case.items[0] = case.receipt(case.xml, "fulltext-jats", 1)
    collection = case.register(repository)
    second = collection.import_selected(case.selected)["results"][0]
    assert second["status"] == "queued"
    assert first["document_id"] == second["document_id"]
    assert first["revision_id"] != second["revision_id"]
    old_row, old_metadata = revision(repository, first)
    new_row, new_metadata = revision(repository, second)
    assert old_row["sha256"] == new_row["sha256"]
    assert old_metadata["original_sha256"] == old_hash != new_metadata["original_sha256"]
    assert new_metadata["original_sha256"] == case.items[0]["sha256"]
    assert old_metadata["content_reviewed"] and not new_metadata["content_reviewed"]
    assert new_metadata["publication_status"] == "unknown" and not new_metadata["latest_final_verified"]


def test_legacy_provenance_binding_preserves_same_proof_dedup(repository, tmp_path):
    case = Case(tmp_path / "collection")
    collection = case.register(repository)
    first = collection.import_selected(case.selected)["results"][0]
    _, metadata = revision(repository, first)
    metadata.pop("original_sha256", None)  # Simulate a pre-field acquired revision.
    repository.db.execute("UPDATE knowledge_revisions SET metadata_json=? WHERE id=?",
                          (json.dumps(metadata), first["revision_id"]))
    assert review(repository, "legacy-exact-review", binding(case))["revisions"] == 1
    repeated = collection.import_selected(case.selected)["results"][0]
    assert repeated["job"]["id"] == first["job"]["id"]
    assert revision(repository, repeated)[1]["content_reviewed"]
    assert len(repository.db.fetch_all("SELECT id FROM knowledge_revisions")) == 1
