"""Actual immutable 1.2 -> 1.3 content/assessment seam; no engine or provider."""
import json

from renulus.assessment.contracts import AnswerRequest, Selector, StartRequest
from renulus.assessment.repository import AssessmentRepository
from renulus.content.api import create_router
from renulus.content.repository import ContentRepository
from renulus.services import Services
from renulus.storage import AppPaths

from .conftest import ROOT


def test_application_release_preserves_scored_history_and_bootstraps_successors(database, tmp_path):
    module = ROOT / "runtime/renulus/assessment"
    database.apply_migration("assessment-001", (module / "schema.sql").read_text(encoding="utf-8"))
    for migration in sorted((module / "migrations").glob("*.sql")):
        database.apply_migration("assessment-" + migration.stem, migration.read_text(encoding="utf-8"))
    packs = ROOT / "content/packs"
    content = ContentRepository(database, packs)
    content.install_pack(packs / "renulus-foundations/1.2.0")
    services = Services(AppPaths.create(tmp_path / "synthetic-profile"), database)
    services.registry.update(content=content, content_pack_root=packs)
    services.registry["content_pack_selection"] = {"version": "1.3.0"}
    assessment = AssessmentRepository(services)
    session = assessment.start(StartRequest(idempotency_key="application-old-session", count=50,
                                           selector=Selector(topic_ids=["T11"])))
    target = "RN11-T11-001"
    # Use the ordinary presentation/answer sequence, without seeding attempts.
    for ordinal in range(session["item_count"]):
        item = session["current_item"]
        question = content.get_question_version(item["question_id"], int(item["question_version"]))
        request = AnswerRequest(idempotency_key=f"application-old-answer-{ordinal}",
                                item_id=item["id"], option_ids=[question["answer"]])
        answered = assessment.answer(session["id"], request)
        session = answered["session"]
        if item["question_id"] == target:
            break
    else:
        raise AssertionError("The historical rationale-correction item was not presented")

    assert item["question_version"] == "1" and answered["feedback"]["correct"]
    before_attempts = database.fetch_all("SELECT * FROM assessment_attempts ORDER BY id")
    before_body = database.fetch_one(
        "SELECT body_json FROM content_question_versions WHERE question_id=? AND version=1", (target,))
    before_scores = assessment.aggregates()
    old_count = database.fetch_one("SELECT COUNT(*) n FROM content_packs")["n"]

    create_router(services)
    upgraded = services.registry["content"]
    assert services.registry["content_bootstrap"]["reason"] == "newer_bundled_release"
    assert upgraded.active_manifest()["version"] == "1.3.0"
    assert len(upgraded.list_question_summaries()) == 230
    assert len(upgraded.list_cases()) == 52
    assert database.fetch_all("SELECT * FROM assessment_attempts ORDER BY id") == before_attempts
    assert database.fetch_one(
        "SELECT body_json FROM content_question_versions WHERE question_id=? AND version=1", (target,)) == before_body
    assert assessment.aggregates() == before_scores
    feedback = assessment.review(session["id"], item["id"])["feedback"][0]
    assert feedback["correct"] and feedback["correct_option_ids"] == ["A"]
    assert feedback["content_status"]["status"] == "withdrawn"
    notice = feedback["content_status"]["withdrawal"]
    assert notice["replacement_version"] == 2 and "rationale" in notice["reason"].lower()
    successor = upgraded.get_question_version(target, 2)
    assert successor["answer"] == "A"
    assert "Review medications and acquired/inherited causes" not in successor["rationale"]
    selected = {q["id"]: q["version"] for q in upgraded.list_question_summaries()}
    assert selected[target] == 2
    assert all(selected[f"RN14-{prefix}-{i:03}"] == 1
               for prefix in ("GBM", "PKD-GEN") for i in range(1, 5))
    assert assessment.answer(session["id"], request) == answered

    reopened = Services(services.paths, database)
    reopened.registry["content_pack_root"] = packs
    reopened.registry["content_pack_selection"] = {"version": "1.3.0"}
    create_router(reopened)
    assert reopened.registry["content_bootstrap"]["reason"] == "active_version_not_older"
    assert database.fetch_one("SELECT COUNT(*) n FROM content_packs")["n"] == old_count + 1
    retained = AssessmentRepository(reopened).review(session["id"], item["id"])["feedback"][0]
    assert retained == feedback
    # The stored original key and rationale remain their immutable historical bytes.
    assert json.loads(before_body["body_json"])["answer"] == "A"
