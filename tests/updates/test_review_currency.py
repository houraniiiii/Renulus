"""Synthetic source review, exact original citations and local integration rules."""
import json
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from renulus.contracts import ApiError
from renulus.server import create_app
from renulus.storage import utc_now
from test_updates import SequenceFetcher, SYNTHETIC_EVIDENCE


def update(service, identifier="synthetic-update", source="K03", url="https://kdigo.org/synthetic-notice.pdf", kind="source-change"):
    service.db.execute("INSERT INTO update_entries(id,source_id,external_id,title,url,kind,discovered_at,review_state,summary,source_metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (identifier, source, identifier, "Synthetic publisher change", url, kind, utc_now(), "pending", "Synthetic unreviewed change", "{}"))
    return identifier


def original(service, kind, identifier, version, source, topic="IgAN", locator="Chapter 2, recommendation 1", stage_only=False):
    # Seed synthetic canonical snapshots through the existing immutable writer.
    # No real authored item or key is modified, and no pack review is invented.
    item = {"id": identifier, "version": version, "topic_id": topic, "secondary_topic_ids": [],
            "objective_ids": ["synthetic-objective"], "review": {"status": "human_reviewed", "reviewed_on": "2026-10-01"},
            "sources": [] if stage_only else [{"source_id": source["id"], "locator": locator}],
            "source_records": [source], "original": True, "license": "CC-BY-4.0"}
    if kind == "question":
        item.update({"family_id": identifier + "-family", "answer": "SYNTHETIC_FIXED_KEY",
                     "options": [{"id": "SYNTHETIC_FIXED_KEY"}], "stem": "SYNTHETIC_RESERVED_STEM",
                     "rationale": "Synthetic key provenance"})
        table, key = "content_question_versions", "question_id"
    else:
        item["stages"] = [{"id": "stage", "narrative": "Synthetic original teaching case",
                            "sources": [{"source_id": source["id"], "locator": locator}]}]
        table, key = "content_case_versions", "case_id"
    with service.db.transaction() as conn:
        service.services.registry["content"]._store(conn, table, key, item, family=kind == "question")
    return item


def reviewed(service, identifier, target, changes, *, evidence=None):
    return service.review(identifier, "Synthetic reviewed implication, not a real educational publication",
                          ["IgAN"], "learner", "reviewed", target=target, changes=changes,
                          evidence=evidence or SYNTHETIC_EVIDENCE)


def test_review_requires_inspected_evidence_without_backfilling_legacy_reviews(tmp_path):
    app = create_app(tmp_path)
    service = app.state.services.registry["updates"]
    identifier = update(service)
    client = TestClient(app)
    body = {"summary": "Synthetic review", "state": "reviewed"}
    assert client.post(f"/api/v1/updates/entries/{identifier}/review", json=body).json()["error"]["code"] == "review_evidence_required"
    evidence = [{**SYNTHETIC_EVIDENCE[0], "inspected": False}]
    assert client.post(f"/api/v1/updates/entries/{identifier}/review", json={**body, "evidence": evidence}).status_code == 422
    evidence = [{**SYNTHETIC_EVIDENCE[0], "checked_on": "2099-01-01"}]
    assert client.post(f"/api/v1/updates/entries/{identifier}/review", json={**body, "evidence": evidence}).status_code == 422
    assert service.get_entry(identifier)["review_state"] == "pending"
    legacy = update(service, "legacy")
    service.db.execute("UPDATE update_entries SET review_state='reviewed',reviewed_at='2025-01-01',reviewer='learner' WHERE id=?", (legacy,))
    assert service.get_entry(legacy)["review"] is None


def test_draft_final_correction_and_access_are_independent_of_check_dates(tmp_path):
    service = create_app(tmp_path).state.services.registry["updates"]
    final = {"register_id": "K03", "canonical_url": "https://kdigo.org/synthetic-final.pdf"}
    draft = {"register_id": "K03", "canonical_url": "https://kdigo.org/synthetic-draft.pdf"}
    original(service, "question", "synthetic-final-question", 1,
             {"id": "synthetic-final", "register_id": "K03", "url": final["canonical_url"]})
    first = update(service, "final")
    result = reviewed(service, first, final, {"publication_status": "final", "publication_date": "2021-07-01",
                                            "latest_final_verified": True, "content_reviewed": True})
    assert result["review"]["library_sync_state"] == "unavailable"
    assert service.get_entry(first)["publication_date"] is None
    draft_entry = update(service, "draft")
    reviewed(service, draft_entry, draft, {"publication_status": "draft", "publication_date": "2026-09-01"})
    assert service.affected.for_entry(draft_entry)["total"] == 0
    correction = update(service, "correction")
    reviewed(service, correction, final, {"correction": "Synthetic official corrigendum, recommendation 2", "revision_date": "2024-03-01"})
    access = update(service, "access")
    reviewed(service, access, final, {"access_changed": True, "repository_removed": True})
    statuses = {row["target"]["canonical_url"]: row["status"] for row in service.reviews.statuses("K03")}
    assert statuses[draft["canonical_url"]]["publication_status"] == "draft"
    final_state = statuses[final["canonical_url"]]
    assert final_state["publication_status"] == "final"
    assert final_state["publication_date"] == "2021-07-01"
    assert final_state["revision_date"] == "2024-03-01"
    assert final_state["correction"].startswith("Synthetic official")
    assert final_state["latest_final_verified"] is False
    assert "retracted" not in final_state  # Repository removal is not retraction.


def test_chapter_replacement_flags_pinned_versions_and_stage_citations_without_mutation(tmp_path):
    app = create_app(tmp_path)
    service = app.state.services.registry["updates"]
    source = {"id": "synthetic-gd-final", "register_id": "K03", "url": "https://kdigo.org/synthetic-gd.pdf"}
    for version in (1, 2):
        original(service, "question", "synthetic-q", version, source)
    original(service, "case", "synthetic-case", 1, source, stage_only=True)
    original(service, "question", "unaffected-q", 1, source, topic="FSGS", locator="Chapter 6")
    original(service, "case", "unrelated-case", 1, {**source, "id": "other-edition", "url": "https://kdigo.org/other-gd.pdf"})
    snapshots = service.db.fetch_all("SELECT question_id,version,body_json,sha256 FROM content_question_versions ORDER BY question_id,version")
    case_snapshots = service.db.fetch_all("SELECT * FROM content_case_versions ORDER BY case_id,version")
    # Synthetic historical-attempt sentinel: the update owner never writes it.
    service.db.execute("CREATE TABLE synthetic_attempt_history(id TEXT PRIMARY KEY,question_id TEXT,version INTEGER,committed_answer TEXT,result TEXT)")
    service.db.execute("INSERT INTO synthetic_attempt_history VALUES('attempt','synthetic-q',1,'SYNTHETIC_FIXED_KEY','unchanged-result')")
    attempts = service.db.fetch_all("SELECT * FROM synthetic_attempt_history")
    identifier = update(service)
    reviewed(service, identifier, {"register_id": "K03", "canonical_url": source["url"]},
             {"replaced_topics": ["IgAN"], "excluded_pages": [50, 51]})
    affected = service.affected.for_entry(identifier)
    assert affected["total"] == 3
    assert {(row["kind"], row["entity_id"], row["version"]) for row in affected["affected"]} == {
        ("question", "synthetic-q", 1), ("question", "synthetic-q", 2), ("case", "synthetic-case", 1)}
    assert all(row["locators"] == ["Chapter 2, recommendation 1"] for row in affected["affected"])
    assert service.db.fetch_all("SELECT question_id,version,body_json,sha256 FROM content_question_versions ORDER BY question_id,version") == snapshots
    assert service.db.fetch_all("SELECT * FROM content_case_versions ORDER BY case_id,version") == case_snapshots
    assert service.db.fetch_all("SELECT * FROM synthetic_attempt_history") == attempts
    result = TestClient(app).get("/api/v1/updates/affected/question/synthetic-q/versions/1")
    assert result.status_code == 200 and result.json()["needs_re_review"] is True
    assert "SYNTHETIC_FIXED_KEY" not in result.text and "SYNTHETIC_RESERVED_STEM" not in result.text
    assert TestClient(app).get("/api/v1/updates/affected/question/synthetic-q/versions/0").status_code == 422
    assert create_app(tmp_path).state.services.registry["updates"].affected.needs_re_review("question", "synthetic-q", 1)["needs_re_review"]


def test_retraction_requires_exact_original_article_and_never_flags_l03_family(tmp_path):
    app = create_app(tmp_path)
    service = app.state.services.registry["updates"]
    article = {"id": "synthetic-article-a", "register_id": "L03", "url": "https://europepmc.org/article/MED/111111"}
    other = {"id": "synthetic-article-b", "register_id": "L03", "url": "https://europepmc.org/article/MED/222222"}
    original(service, "question", "article-a-q", 1, article, topic="transplantation", locator="Results, table 2")
    original(service, "case", "article-a-case", 1, article, topic="transplantation", locator="Results, table 2")
    original(service, "question", "article-b-q", 1, other, topic="dialysis", locator="Discussion")
    identifier = update(service, "notice", source="L03", url="https://europepmc.org/article/MED/999999", kind="retraction")
    with pytest.raises(ApiError) as error:
        reviewed(service, identifier, {"register_id": "L03", "canonical_url": article["url"]}, {"retracted": True})
    assert error.value.code == "retraction_identity_required"
    with pytest.raises(ApiError):
        reviewed(service, identifier, {"register_id": "L03"}, {"retracted": True})
    assert service.affected.for_entry(identifier)["total"] == 0
    target = {"register_id": "L03", "canonical_url": article["url"], "pmid": "111111"}
    evidence = [{**SYNTHETIC_EVIDENCE[0], "url": "https://europepmc.org/article/MED/999999",
                 "finding": "Synthetic notice explicitly names original PMID 111111; notice PMID 999999 is distinct"}]
    reviewed(service, identifier, target, {"retracted": True}, evidence=evidence)
    assert service.affected.for_entry(identifier)["total"] == 2
    assert not service.affected.needs_re_review("question", "article-b-q", 1)["needs_re_review"]
    states = service.reviews.statuses("L03")
    assert states[0]["target"]["pmid"] == "111111" and states[0]["status"] == {"retracted": True, "latest_final_verified": False, "content_reviewed": False}
    # A conflicting original PMID/canonical URL cannot OR-match another article.
    invalid = {**target, "pmid": "222222"}
    with pytest.raises(ApiError):
        reviewed(service, identifier, invalid, {"retracted": True})


def test_library_callable_is_durable_explicit_and_idempotent(tmp_path):
    service = create_app(tmp_path).state.services.registry["updates"]
    identifier = update(service)
    target = {"register_id": "K03", "canonical_url": "https://kdigo.org/synthetic-final.pdf"}
    first = reviewed(service, identifier, target, {"publication_status": "final", "publication_date": "2021-07-01"})
    event_id = first["review"]["id"]
    assert first["review"]["library_sync_state"] == "unavailable"
    calls = []
    def update_source_status(change):
        calls.append(change)
        assert change["contract_version"] == 1
        assert change["event_id"] == event_id and change["source_id"] == "K03"
        assert change["identity"] == {"canonical_url": target["canonical_url"]}
        assert change["changes"]["publication_date"] == "2021-07-01"
        assert "checked_at" not in change["changes"]
        assert change["evidence"]["references"][0]["inspected"] is True
        return {"state": "applied", "matched_revisions": 1}
    service.services.registry["update_source_status"] = update_source_status
    assert service.reviews.sync_entry(identifier)["changes"][0]["state"] == "applied"
    assert service.reviews.sync_entry(identifier)["changes"][0]["state"] == "applied"
    assert len(calls) == 1
    assert reviewed(service, identifier, target, {"publication_status": "final", "publication_date": "2021-07-01"})["review"]["id"] == event_id
    assert len(calls) == 1
    later = reviewed(service, identifier, target, {"correction": "Synthetic new correction"})
    assert later["review"]["id"] != event_id
    # Replaying the earlier review cannot replace the newer correction head.
    assert reviewed(service, identifier, target, {"publication_status": "final", "publication_date": "2021-07-01"})["review"]["id"] == later["review"]["id"]


def test_parent_update_source_status_is_preferred_and_no_match_is_visible(tmp_path):
    service = create_app(tmp_path).state.services.registry["updates"]
    identifier = update(service)
    calls = []
    def update_source_status(event):
        calls.append(event)
        return {"state": "no-match", "matched_revisions": 0}
    service.services.registry["knowledge"] = SimpleNamespace(update_source_status=update_source_status)
    service.services.registry["apply_source_status"] = lambda event: pytest.fail("The compatibility hook cannot supersede the parent contract")
    result = reviewed(service, identifier, {"register_id": "K03", "canonical_url": "https://kdigo.org/synthetic-final.pdf"}, {"access_changed": True})
    assert result["review"]["library_sync_state"] == "no-match"
    assert result["library_changes"][0]["state"] == "no-match"
    assert calls[0]["changes"] == {"access_changed": True}
    assert service.reviews.sync_entry(identifier)["changes"][0]["state"] == "no-match"
    assert len(calls) == 2  # Later imports may now match; no-match stays retryable.


def test_article_identity_enrichment_retains_prior_publication_and_access_facts(tmp_path):
    service = create_app(tmp_path).state.services.registry["updates"]
    identifier = update(service, source="L03")
    target = {"register_id": "L03", "canonical_url": "https://europepmc.org/article/MED/111111"}
    reviewed(service, identifier, target, {"publication_status": "final", "publication_date": "2020-01-01", "access_changed": True})
    reviewed(service, identifier, {**target, "pmid": "111111"}, {"correction": "Synthetic correction notice"})
    states = service.reviews.statuses("L03")
    assert len(states) == 1 and states[0]["target"]["pmid"] == "111111"
    assert states[0]["status"] == {"publication_status": "final", "publication_date": "2020-01-01", "access_changed": True, "correction": "Synthetic correction notice", "latest_final_verified": False, "content_reviewed": False}


@pytest.mark.asyncio
async def test_byte_change_invalidates_only_exact_review_and_flags_pinned_history(tmp_path):
    service = create_app(tmp_path).state.services.registry["updates"]
    candidate = service.publications.candidates("K01")[0]
    publication = service.publications.track("K01", candidate["url"], "Synthetic digest permission")
    source = {"id": "synthetic-ckd", "register_id": "K01", "url": candidate["url"]}
    original(service, "question", "ckd-q", 1, source, topic="ckd", locator="Recommendation 1")
    original(service, "question", "other-ckd-q", 1, {**source, "id": "other-ckd", "url": "https://kdigo.org/another.pdf"}, topic="ckd")
    review_id = update(service, "dated-currency", source="K01")
    reviewed(service, review_id, {"register_id": "K01", "canonical_url": candidate["url"]},
             {"publication_status": "final", "publication_date": "2024-03-01", "latest_final_verified": True, "content_reviewed": True})
    calls = []
    service.services.registry["update_source_status"] = lambda change: calls.append(change) or {"state": "no-match", "matched_revisions": 0}
    service.fetcher = SequenceFetcher([b"%PDF-1.7 synthetic baseline", b"%PDF-1.7 synthetic altered publication"])
    assert (await service.publications.check(publication["id"], True))["state"] == "baseline"
    assert (await service.publications.check(publication["id"], True))["state"] == "changed"
    change = next(entry for entry in service.list_entries() if entry["kind"] == "publication-change")
    affected = service.affected.for_entry(change["id"])["affected"]
    assert len([row for row in affected if row["entity_id"] == "ckd-q"]) == 1
    assert not service.affected.needs_re_review("question", "other-ckd-q", 1)["needs_re_review"]
    status = service.reviews.statuses("K01")[0]["status"]
    assert status["publication_status"] == "final" and status["publication_date"] == "2024-03-01"
    assert status["latest_final_verified"] is False and status["content_reviewed"] is False
    assert calls[-1]["changes"] == {"latest_final_verified": False, "content_reviewed": False}
    assert calls[-1]["evidence"]["kind"] == "publication-digest"
    assert change["review"] is None and change["review_state"] == "pending"
    dismissed = service.review(change["id"], "Synthetic no material teaching implication", [], "learner", "dismissed")
    assert dismissed["review_state"] == "dismissed"
    assert all(row["state"] == "dismissed" for row in service.affected.for_entry(change["id"])["affected"])
