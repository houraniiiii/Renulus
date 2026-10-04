import json

import pytest

from renulus.contracts import ApiError
from renulus.knowledge.models import SourceMetadata
from renulus.knowledge.source_status import validate_event
from test_repository import repository, import_note, STUDY
from test_source_status import event


def acquired(edition, digest, **kwargs):
    return SourceMetadata(source_id="L02", pmcid="PMC1234567",
        canonical_url="https://pmc.ncbi.nlm.nih.gov/articles/PMC1234567/",
        edition=edition, original_sha256=digest, asset_role=["acquired-jats"], **kwargs)


def reviewed(identifier, edition=None, digest=None, changes=None, scope=None):
    identity = {"pmcid": "PMC1234567"}
    if edition is not None or digest is not None:
        identity.update(edition=edition, original_sha256=digest)
    return event(identifier, identity, changes or {"publication_status": "final",
        "latest_final_verified": True, "content_reviewed": True}, scope=scope)


def test_current_review_is_bound_to_both_acquired_edition_and_original_hash(repository):
    documents = [import_note(repository, "Synthetic transplant review " + str(i),
        metadata=acquired(edition, digest)) for i, (edition, digest) in enumerate(
            [("PMC1234567.1", "a" * 64), ("PMC1234567.2", "b" * 64),
             ("PMC1234567.1", "c" * 64)])]
    assert repository.update_source_status(reviewed("unbound"))["state"] == "no-match"
    assert repository.retrieve("transplant", scope=STUDY, current_only=True)["passages"] == []
    result = repository.update_source_status(reviewed("version-one", "PMC1234567.1", "a" * 64))
    assert result["revisions"] == 1
    current = repository.retrieve("transplant", scope=STUDY, current_only=True)["passages"]
    assert {item["document_id"] for item in current} == {documents[0]["document_id"]}
    for document in documents[1:]:
        metadata = repository.get_document(document["document_id"])["revisions"][0]["metadata"]
        assert metadata["publication_status"] == "unknown"
        assert not metadata["content_reviewed"] and not metadata["latest_final_verified"]


@pytest.mark.parametrize("restriction", ["retracted", "repository_removed", "access_changed"])
def test_publication_restrictions_reach_all_versions_and_clear_only_the_reviewed_file(repository, restriction):
    documents = [import_note(repository, "Synthetic dialysis source " + str(i),
        metadata=acquired(edition, digest, topic_ids=[topic]))
        for i, (edition, digest, topic) in enumerate(
            [("PMC1234567.1", "a" * 64, "T19"), ("PMC1234567.2", "b" * 64, "T21")])]
    notice = reviewed("restriction", "PMC1234567.1", "a" * 64,
        {restriction: True}, scope={"topic_ids": ["T19"]})
    assert repository.update_source_status(notice)["revisions"] == 2
    for document in documents:
        metadata = repository.get_document(document["document_id"])["revisions"][0]["metadata"]
        assert metadata[restriction]
    assert repository.update_source_status(reviewed("unbound-clear", changes={restriction: False}))["state"] == "no-match"
    assert repository.update_source_status(reviewed("exact-clear", "PMC1234567.1", "a" * 64,
        {restriction: False}))["revisions"] == 1
    assert not repository.get_document(documents[0]["document_id"])["revisions"][0]["metadata"][restriction]
    assert repository.get_document(documents[1]["document_id"])["revisions"][0]["metadata"][restriction]


def test_exact_review_before_import_replays_and_historical_provenance_still_binds(repository):
    assert repository.update_source_status(reviewed("review-before-import", "PMC1234567.1", "a" * 64))["state"] == "no-match"
    evidence = {"adapter": "pmc-acquired-jats-v1", "article_version": "PMC1234567.1",
                "original_sha256": "a" * 64}
    metadata = acquired("PMC1234567.1", None,
        notes=["renulus-acquired-v1:" + json.dumps(evidence)])
    note = import_note(repository, "Synthetic glomerular review", metadata=metadata)
    assert repository.get_document(note["document_id"])["revisions"][0]["metadata"]["content_reviewed"]
    evidence["article_version"] = "PMC1234567.2"
    wrong = import_note(repository, "Synthetic different glomerular version",
        metadata=acquired("PMC1234567.1", None, notes=["renulus-acquired-v1:" + json.dumps(evidence)]))
    assert not repository.get_document(wrong["document_id"])["revisions"][0]["metadata"]["content_reviewed"]


@pytest.mark.parametrize("binding", [
    {"edition": "PMC1234567.1"}, {"original_sha256": "a" * 64},
    {"edition": " ", "original_sha256": "a" * 64},
    {"edition": "PMC1234567.1", "original_sha256": "A" * 64},
    {"edition": None, "original_sha256": None},
])
def test_partial_or_malformed_version_bindings_cannot_enter_the_journal(binding):
    payload = event("invalid-binding", {"pmcid": "PMC1234567", **binding}, {"content_reviewed": True})
    with pytest.raises(ApiError) as caught:
        validate_event(payload)
    assert caught.value.code == "source_status_invalid"
