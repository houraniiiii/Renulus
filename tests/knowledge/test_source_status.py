import copy

import pytest

from renulus.contracts import ApiError
from renulus.knowledge.models import SourceMetadata
from test_repository import repository, import_note, STUDY, SyntheticEmbedder, SyntheticExtractor


def event(identifier, identity, changes, source_id="L02", scope=None):
    return {"contract_version": 1, "event_id": identifier, "source_id": source_id,
            "identity": identity, "changes": changes, "scope": scope or {},
            "evidence": [{"url": "https://example.org/notice", "locator": "Synthetic notice",
                          "finding": "Synthetic source-status check", "checked_on": "2026-10-04", "inspected": True}],
            "reason": "Synthetic application check; no scientific currency claim"}


def metadata(doi, **kwargs):
    return SourceMetadata(source_id="L02", doi=doi, canonical_url="https://doi.org/" + doi,
                          publication_status="final", latest_final_verified=True, content_reviewed=True, **kwargs)


def test_exact_article_status_is_idempotent_and_does_not_retract_a_family(repository):
    affected = import_note(repository, "Affected glomerular teaching", metadata=metadata("10.1234/original"))
    other = import_note(repository, "Other glomerular teaching", metadata=metadata("10.1234/other"))
    notice = event("notice-one", {"doi": "10.1234/original"}, {"retracted": True})
    assert repository.update_source_status(notice)["revisions"] == 1
    assert repository.update_source_status(notice)["state"] == "applied"
    assert len(repository.db.fetch_all("SELECT * FROM knowledge_source_status_events")) == 1
    hits = repository.retrieve("glomerular", scope=STUDY)["passages"]
    assert {hit["document_id"] for hit in hits} == {other["document_id"]}
    changed = repository.get_document(affected["document_id"])["revisions"][0]["metadata"]
    assert changed["retracted"] and not changed["latest_final_verified"]
    conflicting = copy.deepcopy(notice)
    conflicting["changes"] = {"retracted": False}
    with pytest.raises(ApiError) as caught:
        repository.update_source_status(conflicting)
    assert caught.value.code == "source_status_conflict"


def test_status_before_import_replays_and_older_retry_cannot_override_later_review(repository):
    old = event("older", {"doi": "10.1234/later"}, {"retracted": True})
    assert repository.update_source_status(old)["state"] == "no-match"
    body = dict(metadata=metadata("10.1234/later"), idempotency_key="source-note")
    note = import_note(repository, "Later transplant teaching", **body)
    assert repository.get_document(note["document_id"])["revisions"][0]["metadata"]["retracted"]
    current = event("newer", {"doi": "10.1234/later"}, {"retracted": False,
                    "publication_status": "final", "latest_final_verified": True})
    repository.update_source_status(current)
    repository.update_source_status(old)
    assert import_note(repository, "Later transplant teaching", **body)["revision_id"] == note["revision_id"]
    changed = repository.get_document(note["document_id"])["revisions"][0]["metadata"]
    assert not changed["retracted"] and changed["latest_final_verified"]
    assert repository.retrieve("transplant", scope=STUDY)["passages"]


def test_observed_byte_change_invalidates_review_without_claiming_a_new_edition(repository):
    note = import_note(repository, "Dialysis guidance", metadata=SourceMetadata(
        source_id="K01", canonical_url="https://example.org/guide.pdf", edition="Recorded edition",
        publication_status="final", latest_final_verified=True, content_reviewed=True))
    change = event("bytes-changed", {"canonical_url": "https://example.org/guide.pdf"},
                   {"latest_final_verified": False, "content_reviewed": False}, source_id="K01")
    change["evidence"] = {"kind": "publication-digest", "previous_sha256": "a" * 64}
    assert repository.update_source_status(change)["state"] == "applied"
    changed = repository.get_document(note["document_id"])["revisions"][0]["metadata"]
    assert changed["edition"] == "Recorded edition" and changed["publication_status"] == "final"
    assert not changed["latest_final_verified"] and not changed["content_reviewed"]
    assert repository.retrieve("dialysis", scope=STUDY, current_only=True)["passages"] == []


def test_restored_older_no_match_event_cannot_override_newer_recorded_review(repository, monkeypatch):
    from renulus.knowledge import source_status
    old = event("restored-older", {"doi": "10.1234/restored"}, {"retracted": True})
    monkeypatch.setattr(source_status, "utc_now", lambda: "2026-10-04T18:00:00+00:00")
    assert repository.update_source_status(old)["state"] == "no-match"
    saved = repository.db.fetch_one("SELECT * FROM knowledge_source_status_events WHERE id=?", (old["event_id"],))
    repository.db.execute("DELETE FROM knowledge_source_status_events WHERE id=?", (old["event_id"],))
    monkeypatch.setattr(source_status, "utc_now", lambda: "2026-10-04T20:00:00+00:00")
    new = event("retained-newer", {"doi": "10.1234/restored"},
                {"retracted": False, "publication_status": "final", "latest_final_verified": True})
    assert repository.update_source_status(new)["state"] == "no-match"
    # A canonical backup merge inserts the older event later while retaining
    # its original recorded time. Physical row order is not review authority.
    repository.db.execute("INSERT INTO knowledge_source_status_events VALUES(?,?,?,?,?)",
        tuple(saved[key] for key in ("id", "source_id", "request_hash", "payload_json", "created_at")))
    note = import_note(repository, "Restored glomerular teaching", metadata=metadata("10.1234/restored"))
    repository.update_source_status(old)
    current = repository.get_document(note["document_id"])["revisions"][0]["metadata"]
    assert not current["retracted"] and current["latest_final_verified"]
    assert repository.retrieve("glomerular", scope=STUDY)["passages"]


def test_unknown_identity_scope_and_unreviewed_promotions_are_not_published(repository):
    import_note(repository, "Kidney teaching", metadata=metadata("10.1234/scope"))
    unresolved = event("unmapped-page", {"doi": "10.1234/scope"},
                       {"excluded_pages": [2]}, scope={"locators": ["Unmapped chapter"]})
    assert repository.update_source_status(unresolved)["state"] == "no-match"
    pinned = event("pack-only", {"pinned_source_id": "source-item"}, {"superseded": True})
    assert repository.update_source_status(pinned)["state"] == "no-match"
    bad = event("promotion", {"doi": "10.1234/scope"}, {"content_reviewed": True})
    bad["evidence"] = []
    with pytest.raises(ApiError):
        repository.update_source_status(bad)
    bad = event("conflict", {"doi": "10.1234/scope", "canonical_url": "https://doi.org/10.1234/wrong"}, {"retracted": True})
    with pytest.raises(ApiError):
        repository.update_source_status(bad)
    assert repository.retrieve("kidney", scope=STUDY)["passages"]


def test_actual_updates_review_outbox_changes_library_currency_and_survives_retry(tmp_path):
    from renulus.server import create_app
    from renulus.storage import utc_now
    services = create_app(tmp_path).state.services
    knowledge, updates = services.get("knowledge"), services.get("updates")
    knowledge.extractor, knowledge.embedder = SyntheticExtractor(), SyntheticEmbedder()
    url = "https://kdigo.org/synthetic-iga-guideline.pdf"
    note = import_note(knowledge, "Synthetic glomerular learning source", metadata=SourceMetadata(
        source_id="K03", canonical_url=url, publication_status="final", latest_final_verified=True, content_reviewed=True))
    services.db.execute("INSERT INTO update_entries(id,source_id,external_id,title,url,kind,discovered_at,review_state,summary,source_metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?)",
        ("synthetic-currency", "K03", "synthetic-currency", "Synthetic publisher change", url,
         "source-change", utc_now(), "pending", "Synthetic unreviewed notice", "{}"))
    result = updates.review("synthetic-currency", "Synthetic replacement annotation", ["T10"],
        "assistant", "reviewed", target={"register_id": "K03", "canonical_url": url},
        changes={"superseded": True}, evidence=event("unused", {}, {})["evidence"])
    assert result["review"]["library_sync_state"] == "applied"
    assert knowledge.get_document(note["document_id"])["revisions"][0]["metadata"]["superseded"]
    assert knowledge.retrieve("glomerular", scope=STUDY)["passages"] == []
    repeated = updates.reviews.sync_entry("synthetic-currency")
    assert repeated["changes"][0]["state"] == "applied"
    assert len(services.db.fetch_all("SELECT * FROM knowledge_source_status_events")) == 1
    knowledge.index.close()
