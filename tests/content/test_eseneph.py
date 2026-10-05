# SPDX-License-Identifier: MIT
"""Real original release and canonical SQLite; no source fetch or model/helper."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys

from fastapi.testclient import TestClient
import pytest

from renulus.content.repository import ContentRepository
from renulus.content.validation import PackValidationError, validate_pack
from renulus.server import create_app
from .helpers import PACK, read, refresh, write

ROOT = Path(__file__).parents[2]
PRIOR = PACK.parent / "1.1.0"
RELEASE = PACK.parent / "1.1.1"
MAPPING = ROOT / "content/mappings/esen-eph-2026-10-05.json"
REVIEW = ROOT / "content/reviews/renulus-foundations-1.1.1.json"
sys.path.insert(0, str(ROOT / "tools/content"))
import author_eseneph as author
from revision_checks import validate_review_evidence, validate_revision


@pytest.fixture
def mapped(repository):
    repository.install_pack(RELEASE)
    return repository


def track(repository):
    return next(t for t in repository.track_metadata() if t["id"] == "esen_eph")


def all_keys(value):
    if isinstance(value, dict):
        return set(value) | set().union(*(all_keys(v) for v in value.values()))
    if isinstance(value, list):
        return set().union(*(all_keys(v) for v in value))
    return set()


def test_release_reproduces_and_preserves_all_published_bank_bytes(tmp_path):
    reproduced = tmp_path / "reproduced"
    mapping, review = tmp_path / "mapping.json", tmp_path / "review.json"
    author.publish(reproduced, mapping, review)
    author.publish(reproduced, mapping, review)
    for path in RELEASE.iterdir():
        assert path.read_bytes() == (reproduced / path.name).read_bytes()
    assert mapping.read_bytes() == MAPPING.read_bytes()
    assert review.read_bytes() == REVIEW.read_bytes()
    for name in ("questions.json", "cases.json", "sources.json", "coverage.json"):
        assert (RELEASE / name).read_bytes() == (PRIOR / name).read_bytes()
    old_topics = {t["id"]: t for t in read(PRIOR, "topics.json")}
    for topic in read(RELEASE, "topics.json"):
        old = old_topics[topic["id"]]
        assert topic["version"] == old["version"] + 1
        assert {k: v for k, v in topic.items() if k not in ("version", "mapping")} == {
            k: v for k, v in old.items() if k not in ("version", "mapping")}
    pack = validate_pack(RELEASE)
    assert pack.manifest["programme_mappings"] == [read(MAPPING.parent, MAPPING.name)]
    predecessors = [validate_pack(PACK.parent / v) for v in ("1.0.0", "1.0.1", "1.1.0")]
    assert [validate_revision(pack, p)["version"] for p in predecessors] == ["1.0.0", "1.0.1", "1.1.0"]
    assert validate_review_evidence(pack, REVIEW, predecessors) == 0
    with pytest.raises(PackValidationError, match="lack source/key review evidence"):
        validate_review_evidence(pack, REVIEW)


def test_publisher_rejects_invalid_draft_before_creating_release(tmp_path):
    prior = validate_pack(PRIOR).bundle
    invalid = deepcopy(author.programme())
    invalid["domains"][0]["indicative_questions"] += 1
    topics = deepcopy(prior["topics"])
    for topic in topics:
        topic["version"] = 2
        topic["mapping"].update(esen_eph="partially_mapped", mapping_version=author.DATE)
    destination = tmp_path / "never-published"
    with pytest.raises(PackValidationError, match="blueprint counts"):
        author.base.publish_snapshot(destination, version=author.VERSION, topics=topics,
            sources=prior["sources"], cases=prior["cases"], questions=prior["questions"],
            target_topics=prior["coverage"]["target_topics"], minimum_questions=150,
            published_on=author.DATE, programme_mappings=[invalid])
    assert not destination.exists()
    assert not list(tmp_path.glob(".renulus-author-*"))


def test_publisher_refuses_to_replace_published_mapping_evidence(tmp_path):
    target = tmp_path / "existing.json"
    target.write_text('{"original":"preserve"}', encoding="utf-8")
    before = target.read_bytes()
    with pytest.raises(SystemExit, match="Refusing to change"):
        author.write_evidence(target, author.programme())
    assert target.read_bytes() == before


@pytest.mark.parametrize("mutation,match", [
    ("weights", "blueprint counts"), ("future_date", "after publication"),
    ("missing_hash", "pin hash"), ("unknown_objective", "Unknown aligned objective"),
    ("wrong_version", "Unknown selected questions version"), ("cross_domain", "inflate two blueprint domains"),
    ("gap_claim", "gap cannot claim"), ("missing_domain", "Every blueprint domain"),
    ("unknown_page", "curriculum page"), ("support_as_exam", "Curriculum support cannot"),
    ("selected_exclusion", "Excluded question"), ("topic_date", "Partial topic mapping"),
    ("human_claim", "Manifest schema"), ("exam_claim", "Manifest schema"),
])
def test_forged_or_unsupported_mapping_is_rejected(tmp_path, mutation, match):
    path = tmp_path / mutation
    shutil.copytree(RELEASE, path)
    manifest = read(path, "manifest.json")
    p = manifest["programme_mappings"][0]
    rows = p["alignments"]
    if mutation == "weights":
        p["domains"][0]["indicative_questions"] += 1
    elif mutation == "future_date":
        p["checked_on"] = "2026-10-06"
    elif mutation == "missing_hash":
        del p["evidence"][1]["sha256"]
    elif mutation == "unknown_objective":
        rows[0]["objective_ids"].append("unknown-objective")
    elif mutation == "wrong_version":
        rows[0]["questions"][0]["version"] = 99
    elif mutation == "cross_domain":
        rows[0]["objective_ids"].append("T04.O01")
        rows[0]["questions"].append({"id": "RN-K-001", "version": 1})
    elif mutation == "gap_claim":
        next(r for r in rows if r["status"] == "gap")["objective_ids"] = ["T04.O01"]
    elif mutation == "missing_domain":
        p["alignments"] = [r for r in rows if r["domain_id"] != "urology"]
    elif mutation == "unknown_page":
        rows[0]["curriculum_reference"]["pages"] = [100]
    elif mutation == "support_as_exam":
        rows[-1]["domain_id"] = "other"
    elif mutation == "selected_exclusion":
        p["excluded_questions"][0]["id"] = "RN-K-001"
    elif mutation == "topic_date":
        topics = read(path, "topics.json")
        topics[0]["mapping"]["mapping_version"] = "wrong-version"
        write(path, "topics.json", topics)
        refresh(path)
        manifest = read(path, "manifest.json")
    elif mutation == "human_claim":
        p["independent_human_review"] = True
    elif mutation == "exam_claim":
        p["exam_simulation_available"] = True
    write(path, "manifest.json", manifest)
    with pytest.raises(PackValidationError, match=match):
        validate_pack(path)


@pytest.mark.parametrize("usage", ["practice", "evaluation_reserved"])
def test_generated_or_reserved_evaluation_cannot_inflate_mapped_bank(tmp_path, usage):
    path = tmp_path / usage
    shutil.copytree(RELEASE, path)
    questions = read(path, "questions.json")
    questions[0]["usage"] = usage
    write(path, "questions.json", questions)
    refresh(path)
    with pytest.raises(PackValidationError, match="Only the reviewed bank"):
        validate_pack(path)


def test_mapping_evidence_must_use_current_register_and_exact_review(tmp_path):
    known = {s["register_id"] for s in validate_pack(RELEASE).bundle["sources"]}
    with pytest.raises(PackValidationError, match="Unknown SOURCES register ID for programme"):
        validate_pack(RELEASE, known_register_ids=known)
    review = read(REVIEW.parent, REVIEW.name)
    review["programme_mapping"]["evidence_sha256"]["C01-linked-blueprint-20261005"] = "0" * 64
    path = tmp_path / "tampered-review.json"
    write(tmp_path, path.name, review)
    with pytest.raises(PackValidationError, match="Programme review evidence"):
        validate_review_evidence(validate_pack(RELEASE), path, [validate_pack(PRIOR)])


def test_partial_track_is_exact_key_free_and_does_not_claim_full_exam(mapped):
    m = track(mapped)
    assert m["available"] and m["status"] == "partial"
    assert m["available_questions"] == m["available_families"] == 152
    assert m["unmapped_questions"] == 8 and m["available_cases"] == 26
    assert len(m["aligned_objective_ids"]) == 55
    assert m["supporting_objective_ids"] == ["T26.O02"] and not m["unaligned_objective_ids"]
    assert m["option_count_distribution"] == {"4": 152}
    assert m["format_compatible_questions"] == 0 and m["exam"]["options_per_question"] == 5
    assert not any(m[k] for k in ("exam_simulation_available", "independent_human_review", "official_endorsement"))
    assert m["review_counts"] == {"assistant_reviewed": 152, "human_reviewed": 0}
    assert len(m["domains"]) == 11 and sum(d["indicative_questions"] for d in m["domains"]) == 200
    assert sum(d["available_questions"] for d in m["domains"]) == 152
    domains = {d["id"]: d for d in m["domains"]}
    assert domains["peritoneal_dialysis"]["available_questions"] == 2
    assert domains["hemodialysis"]["family_shortfall"] == 11
    assert all(d["status"] == "partial" for d in m["domains"])
    gaps = {r["id"] for d in m["domains"] for r in d["alignments"] if r["status"] == "gap"}
    assert {"sexual_health_gap", "transition_gap", "pd_infection_gap", "transplant_aftercare_gap"} <= gaps
    private = {"stem", "options", "answer", "rationale", "explanation", "correct_option_ids", "source_records"}
    assert not private.intersection(all_keys(m))
    summaries = mapped.list_question_summaries(track="esen_eph")
    assert len(summaries) == 152 and not private.intersection(all_keys(summaries))
    assert len(mapped.list_question_summaries()) == 160
    assert len(mapped.list_question_summaries(domain="T17", track="esen_eph")) == 3
    assert mapped.list_question_summaries(topic_id="T03", domain="T04", track="esen_eph") == []
    assert mapped.list_question_summaries(track="unsupported-track") == []
    assert {p["id"] for p in m["excluded_questions"]}.isdisjoint(q["id"] for q in summaries)
    assert all(q["kind"] != "question" for q in mapped.teaching_material())


def test_withdrawal_recomputes_counts_and_objectives_from_canonical_snapshot(mapped, database, tmp_path):
    before = mapped.get_question_version("RN-ANEMIA-001", 1)
    mapped.withdraw_question("RN-ANEMIA-001", 1, "Synthetic review hold")
    m = track(mapped)
    assert m["available_questions"] == 151
    assert "T08.O03" not in m["aligned_objective_ids"] and "T08.O03" in m["unaligned_objective_ids"]
    assert next(d for d in m["domains"] if d["id"] == "bone_anemia")["available_questions"] == 8
    reopened = ContentRepository(database, tmp_path / "missing-public-assets")
    assert track(reopened) == m
    pinned = reopened.get_question_version("RN-ANEMIA-001", 1)
    assert pinned["answer"] == before["answer"] and pinned["source_records"] == before["source_records"]
    for q in ("RN-EVID-001", "RN11-T26-001", "RN11-T26-003", "RN11-T26-004"):
        reopened.withdraw_question(q, 1, "Synthetic generic-support hold")
    assert track(reopened)["supporting_objective_ids"] == []
    assert "T26.O02" in track(reopened)["unaligned_objective_ids"]


@pytest.mark.parametrize("reader", ["track_metadata", "list_question_summaries"])
@pytest.mark.parametrize("change", ["activate_prior", "withdraw_question"])
def test_track_read_keeps_one_snapshot_during_another_committed_write(mapped, monkeypatch, reader, change):
    read_current = (mapped.track_metadata if reader == "track_metadata" else
                    lambda: mapped.list_question_summaries(track="esen_eph"))
    before = read_current()
    read_rows = mapped._active_rows
    changed = False

    def change_between_manifest_and_rows(name, connection=None):
        nonlocal changed
        if connection is not None and not changed:
            changed = True
            # This writer uses a separate canonical connection while the reader
            # holds its snapshot. WAL permits the commit without a worker thread.
            if change == "activate_prior":
                mapped.install_pack(PRIOR)
            else:
                mapped.withdraw_question("RN-ANEMIA-001", 1, "Synthetic concurrent review hold")
        return read_rows(name, connection)

    monkeypatch.setattr(mapped, "_active_rows", change_between_manifest_and_rows)
    assert read_current() == before
    assert changed
    assert read_current() != before
    if change == "activate_prior":
        assert not track(mapped)["available"]
        assert mapped.list_question_summaries(track="esen_eph") == []
    else:
        assert track(mapped)["available_questions"] == 151
        assert len(mapped.list_question_summaries(track="esen_eph")) == 151


def test_exhausted_or_inactive_bank_cannot_advertise_available_assessment(mapped):
    pins = mapped.list_question_summaries(track="esen_eph")
    with mapped.db.transaction() as conn:
        for q in pins:
            mapped._withdraw_question(conn, q["id"], q["version"], "Synthetic mapped-bank hold")
    m = track(mapped)
    assert not m["available"] and m["available_questions"] == 0 and m["reason"]
    assert mapped.list_question_summaries(track="esen_eph") == []
    assert m["format_compatible_questions"] == 0 and m["supporting_objective_ids"] == ["T26.O02"]
    mapped.withdraw_pack("renulus-foundations", "1.1.1", "Synthetic pack hold")
    assert not track(mapped)["available"] and track(mapped)["status"] == "not_formally_mapped"
    assert mapped.get_question_version("RN-CKD-001", 1)["answer"]


def test_old_unmapped_pack_and_topic_tags_do_not_invent_track(repository, tmp_path):
    assert not track(repository)["available"]
    repository.install_pack(PRIOR)
    assert track(repository)["status"] == "not_formally_mapped"
    assert repository.list_question_summaries(track="esen_eph") == []
    path = tmp_path / "unsupported-tags"
    shutil.copytree(PRIOR, path)
    topics = read(path, "topics.json")
    topics[0]["mapping"].update(esen_eph="partially_mapped", mapping_version=author.DATE)
    write(path, "topics.json", topics)
    refresh(path)
    with pytest.raises(PackValidationError, match="Partial topic mapping needs"):
        validate_pack(path)


def test_public_http_payload_and_track_selection_use_real_producer(tmp_path, monkeypatch):
    monkeypatch.setattr("renulus.server.MODULE_ORDER", ("content",))
    app = create_app(tmp_path / "synthetic-profile", token="synthetic-test-token")
    with TestClient(app, headers={"x-renulus-token": "synthetic-test-token"}) as client:
        response = client.get("/api/v1/content/tracks")
        assert response.status_code == 200 and isinstance(response.json(), list)
        assert response.json() == app.state.services.registry["content"].track_metadata()
        assert len(client.get("/api/v1/content/questions?track=esen_eph").json()) == 152
        assert len(client.get("/api/v1/content/questions?track=general_nephrology").json()) == 160
        assert client.get("/api/v1/content/questions/RN-CKD-001/versions/1").status_code == 404


def test_mapping_activation_preserves_committed_attempts_and_historical_feedback(tmp_path, monkeypatch):
    monkeypatch.setattr("renulus.server.MODULE_ORDER", ("content", "assessment"))
    profile = tmp_path / "synthetic-assessment-profile"
    app = create_app(profile)
    content = app.state.services.registry["content"]
    content.install_pack(PRIOR)
    with TestClient(app) as client:
        response = client.post("/api/v1/assessment/start", json={"idempotency_key": "pre-mapping-session", "count": 1,
                               "selector": {"topic_ids": ["T08"], "track": "general_nephrology"}})
        assert response.status_code == 200, response.text
        session = response.json()
        row = app.state.services.db.fetch_one("SELECT question_id,question_version FROM assessment_items WHERE id=?",
                                               (session["current_item"]["id"],))
        key = content.get_question_version(row["question_id"], int(row["question_version"]))["answer"]
        answered = client.post(f"/api/v1/assessment/sessions/{session['id']}/answer", json={
            "idempotency_key": "pre-mapping-answer", "item_id": session["current_item"]["id"], "option_ids": [key]})
        assert answered.status_code == 200 and answered.json()["feedback"]["correct"]
        before = [dict(r) for r in app.state.services.db.fetch_all("SELECT * FROM assessment_attempts")]
        feedback = client.get(f"/api/v1/assessment/sessions/{session['id']}/review").json()["feedback"]
        content.install_pack(RELEASE)
        assert [dict(r) for r in app.state.services.db.fetch_all("SELECT * FROM assessment_attempts")] == before
        assert client.get(f"/api/v1/assessment/sessions/{session['id']}/review").json()["feedback"] == feedback
        new = client.post("/api/v1/assessment/start", json={"idempotency_key": "mapped-preparation-session", "count": 2,
                            "selector": {"track": "esen_eph"}})
        assert new.status_code == 200 and new.json()["item_count"] == 2, new.text
    restarted = create_app(profile)
    with TestClient(restarted) as client:
        assert [dict(r) for r in restarted.state.services.db.fetch_all("SELECT * FROM assessment_attempts")] == before
        assert client.get(f"/api/v1/assessment/sessions/{session['id']}/review").json()["feedback"] == feedback
