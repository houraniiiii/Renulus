"""Preserve committed learning while activating the mapped T18 teaching slice."""
from renulus.assessment.contracts import AnswerRequest, Selector, StartRequest
from renulus.assessment.repository import AssessmentRepository
from renulus.cases.models import StartCase
from renulus.cases.repository import CaseRepository
from renulus.content.api import create_router
from renulus.content.programmes import programme_metadata
from renulus.content.repository import ContentRepository
from renulus.services import Services
from renulus.storage import AppPaths

from .conftest import ROOT


def test_treatment_injury_upgrade_preserves_attempt_and_maps_new_teaching(database, tmp_path):
    for name in ("assessment", "cases"):
        module = ROOT / "runtime/renulus" / name
        database.apply_migration(name + "-001", (module / "schema.sql").read_text(encoding="utf-8"))
        for migration in sorted((module / "migrations").glob("*.sql")):
            database.apply_migration(name + "-" + migration.stem,
                                     migration.read_text(encoding="utf-8"))
    packs = ROOT / "content/packs"
    content = ContentRepository(database, packs)
    content.install_bundled_release(packs / "renulus-foundations/1.4.0")
    services = Services(AppPaths.create(tmp_path / "synthetic-profile"), database)
    services.registry.update(content=content, content_pack_root=packs)
    assessment = AssessmentRepository(services)
    session = assessment.start(StartRequest(idempotency_key="t18-old-session", count=1,
                                           selector=Selector(topic_ids=["T06"])))
    item = session["current_item"]
    question = content.get_question_version(item["question_id"], item["question_version"])
    request = AnswerRequest(idempotency_key="t18-old-answer", item_id=item["id"],
                            option_ids=[question["answer"]])
    answered = assessment.answer(session["id"], request)
    attempts = database.fetch_all("SELECT * FROM assessment_attempts ORDER BY id")
    scores = assessment.aggregates()
    historical = database.fetch_all("SELECT question_id,version,body_json FROM content_question_versions")
    old_topics = database.fetch_all("SELECT topic_id,version,body_json FROM content_topics")

    create_router(services)
    content = services.registry["content"]
    assert content.active_manifest()["version"] == "1.4.2"
    assert services.registry["content_bootstrap"]["reason"] == "newer_bundled_release"
    assert database.fetch_all("SELECT * FROM assessment_attempts ORDER BY id") == attempts
    assert assessment.aggregates() == scores
    current = {(row["question_id"], row["version"]): row["body_json"] for row in
               database.fetch_all("SELECT question_id,version,body_json FROM content_question_versions")}
    assert all(current[(row["question_id"], row["version"])] == row["body_json"] for row in historical)
    topics = {(row["topic_id"], row["version"]): row["body_json"] for row in
              database.fetch_all("SELECT topic_id,version,body_json FROM content_topics")}
    assert all(topics[(row["topic_id"], row["version"])] == row["body_json"] for row in old_topics)
    summaries = content.list_question_summaries(topic_id="T18", track="esen_eph")
    assert {"RN16-T18-001", "RN16-T18-002"} <= {row["id"] for row in summaries}
    assert all(not {"stem", "options", "answer", "rationale"}.intersection(row) for row in summaries)
    for identifier, answer in (("RN16-T18-001", "C"), ("RN16-T18-002", "B")):
        record = content.get_question_version(identifier, 1)
        assert record["answer"] == answer and len(record["options"]) == 5
        assert content.get_source(record["sources"][0]["source_id"])["register_id"] == "G06"
    programme = programme_metadata(content.active_manifest(), content.list_topics(),
                                   content.list_cases(), content.list_questions())[1]
    assert programme["available_questions"] == 247
    assert programme["unmapped_questions"] == 4
    assert programme["version"] == "2026-10-07-treatment-injury"
    assert not programme["exam_simulation_available"] and not programme["official_endorsement"]
    domain = next(row for row in programme["domains"] if row["id"] == "glomerular_interstitial")
    alignment = next(row for row in domain["alignments"] if row["id"] == "cancer-treatment-kidney-injury")
    assert alignment["objective_ids"] == ["T18.O01"]
    assert alignment["cases"] == [{"id": "RN16-CASE-T18-TREATMENT-INJURY", "version": 1}]

    cases = CaseRepository(services)
    authored = content.get_case("RN16-CASE-T18-TREATMENT-INJURY")
    case = cases.start(StartCase(kind="teaching", teaching_case_id=authored["id"]))
    assert case["scope"]["kind"] == "temporary-case" and not case["saved"]
    assert case["teaching"]["revealed_count"] == 1
    assert "teaching_points" not in case["teaching"]["stages"][0]
    for _ in authored["stages"]:
        case = cases.reveal(case["id"], case["revision"])
    assert case["teaching"]["debriefed"]
    assert case["teaching"]["take_home"] == authored["take_home"]
    for actual, expected in zip(case["teaching"]["stages"], authored["stages"], strict=True):
        assert actual["teaching_points"] == expected["teaching_points"]
        assert actual["sources"] == expected["sources"]
    cases.close(case["id"], case["revision"])
    assert cases.list_saved() == []
    assert database.fetch_one("SELECT count(*) n FROM case_sessions")["n"] == 0

    reopened = Services(services.paths, database)
    reopened.registry["content_pack_root"] = packs
    create_router(reopened)
    assert reopened.registry["content_bootstrap"]["reason"] == "active_version_not_older"
    again = AssessmentRepository(reopened)
    assert again.answer(session["id"], request) == answered
    assert again.aggregates() == scores
    assert database.fetch_all("SELECT * FROM assessment_attempts ORDER BY id") == attempts
