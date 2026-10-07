"""Real content/assessment/case records for the additive 1.3 -> 1.4 slice."""
from renulus.assessment.contracts import AnswerRequest, Selector, StartRequest
from renulus.assessment.repository import AssessmentRepository
from renulus.cases.models import StartCase
from renulus.cases.repository import CaseRepository
from renulus.content.api import create_router
from renulus.content.repository import ContentRepository
from renulus.services import Services
from renulus.storage import AppPaths

from .conftest import ROOT

NEW_CASES = {
    "RN15-CASE-GBM-SAFETY", "RN15-CASE-HD-AIR", "RN15-CASE-HD-HAEMOLYSIS",
    "RN15-CASE-HD-DISCONNECTION", "RN15-CASE-CMV-PREVENTION", "RN15-CASE-CMV-MEDICINES",
}
NEW_QUESTIONS = {f"RN15-{prefix}-{i:03}" for prefix, count in
                 (("GBM", 6), ("HD", 5), ("CMV", 8)) for i in range(1, count + 1)}


def test_depth2_upgrade_keeps_answer_history_and_exposes_six_staged_cases(database, tmp_path):
    for name in ("assessment", "cases"):
        module = ROOT / "runtime/renulus" / name
        database.apply_migration(name + "-001", (module / "schema.sql").read_text(encoding="utf-8"))
        for migration in sorted((module / "migrations").glob("*.sql")):
            database.apply_migration(name + "-" + migration.stem,
                                     migration.read_text(encoding="utf-8"))
    packs = ROOT / "content/packs"
    content = ContentRepository(database, packs)
    content.install_bundled_release(packs / "renulus-foundations/1.3.0")
    services = Services(AppPaths.create(tmp_path / "synthetic-profile"), database)
    services.registry.update(content=content, content_pack_root=packs)
    assessment = AssessmentRepository(services)
    session = assessment.start(StartRequest(idempotency_key="depth2-existing-session", count=1,
                                           selector=Selector(topic_ids=["T06"])))
    item = session["current_item"]
    question = content.get_question_version(item["question_id"], int(item["question_version"]))
    request = AnswerRequest(idempotency_key="depth2-existing-answer", item_id=item["id"],
                            option_ids=[question["answer"]])
    answered = assessment.answer(session["id"], request)
    before = database.fetch_all("SELECT * FROM assessment_attempts ORDER BY id")
    scores = assessment.aggregates()
    historical = database.fetch_all("SELECT question_id,version,body_json FROM content_question_versions")

    create_router(services)
    content = services.registry["content"]
    assert content.active_manifest()["version"] == "1.4.0"
    assert services.registry["content_bootstrap"]["reason"] == "newer_bundled_release"
    assert database.fetch_all("SELECT * FROM assessment_attempts ORDER BY id") == before
    assert assessment.aggregates() == scores
    current = {(row["question_id"], row["version"]): row["body_json"] for row in
               database.fetch_all("SELECT question_id,version,body_json FROM content_question_versions")}
    assert all(current[(row["question_id"], row["version"])] == row["body_json"] for row in historical)
    assert NEW_QUESTIONS <= {row["id"] for row in content.list_question_summaries(track="esen_eph")}
    assert content.get_source("RN15-HD-SRC-BCR-202607")["register_id"] == "G09"

    cases = CaseRepository(services)
    assert NEW_CASES <= {row["id"] for row in cases.list_teaching()}
    for identifier in sorted(NEW_CASES):
        authored = content.get_case(identifier)
        case = cases.start(StartCase(kind="teaching", teaching_case_id=identifier))
        assert not case["saved"] and case["scope"]["kind"] == "temporary-case"
        assert case["teaching"]["revealed_count"] == 1
        assert "teaching_points" not in case["teaching"]["stages"][0]
        for _ in authored["stages"]:
            case = cases.reveal(case["id"], case["revision"])
        assert case["teaching"]["debriefed"]
        assert case["teaching"]["take_home"] == authored["take_home"]
        for shown, source in zip(case["teaching"]["stages"], authored["stages"], strict=True):
            assert shown["teaching_points"] == source["teaching_points"]
            assert shown["sources"] == source["sources"]
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
    assert database.fetch_all("SELECT * FROM assessment_attempts ORDER BY id") == before
