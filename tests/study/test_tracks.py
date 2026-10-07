"""Content-owned track consumers, with real SQLite and an original-pack journey."""
from copy import deepcopy
from datetime import date
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from renulus.server import create_app
from renulus.storage import utc_now

ROOT = Path(__file__).resolve().parents[2]
TODAY = date(2026, 10, 5)


class ProgrammeContent:
    def __init__(self):
        self.topics = [{"id": topic, "title": title,
                        "objectives": [{"id": topic + "-objective", "text": title + " objective"}]}
                       for topic, title in (("ckd", "CKD"), ("dialysis", "Dialysis"),
                                            ("transplantation", "Transplantation"), ("support", "Curriculum support"))]
        self.metadata = [{"id": "general_nephrology", "title": "General nephrology", "available": True},
            {"id": "esen_eph", "title": "ESENeph preparation", "version": "synthetic-2026-10-05",
             "checked_on": "2026-10-05", "available": True, "status": "partial",
             "exam_simulation_available": False, "available_questions": 2,
             "aligned_objective_ids": ["ckd-objective", "dialysis-objective"],
             "supporting_objective_ids": ["support-objective"],
             "domains": [{"id": "mapped-domain", "label": "Mapped domain", "status": "partial",
                          "available_questions": 2, "alignments": [{"id": "mapped-alignment",
                          "questions": [{"id": "ckd-q", "version": 1}, {"id": "dialysis-q", "version": 1}]}]}]}]

    def list_topics(self):
        return deepcopy(self.topics)

    def track_metadata(self):
        return deepcopy(self.metadata)


def app_with_content(profile, content):
    app = create_app(profile, source_root=ROOT)
    app.state.services.registry["content"] = content
    return app


def goals(track="eseneph", topic_ids=None):
    return {"hours_per_week": 4, "exam_date": "2027-03-01",
            "topic_ids": topic_ids or [], "track": track}


def add_answer(services, identifier, topic, question, *, correct=False, version=1, family=None):
    services.db.execute("INSERT INTO learning_evidence VALUES(?,?,?,?,?,?)",
        (identifier, "assessment-answer", topic, question, json.dumps({
            "question_id": question, "question_version": version, "family_id": family or question,
            "objective_id": topic + "-objective", "objective_ids": [topic + "-objective"],
            "correct": correct, "score_bucket": "fresh"}), utc_now()))


def test_track_change_filters_automatic_plan_and_keeps_manual_goals_across_restart(tmp_path):
    content = ProgrammeContent()
    app = app_with_content(tmp_path, content)
    study = app.state.services.get("study")
    general = {r["topic_id"]: r for r in study.propose(TODAY)["activities"]}
    study.change_activity(general["transplantation"]["id"], {"due_date": "2026-10-20"})
    study.change_activity(general["support"]["id"], {"state": "skipped"})
    study.change_activity(general["ckd"]["id"], {"state": "completed"})
    assert study.save_goals(goals()) == goals()
    proposed = study.propose(TODAY)
    automatic = [r for r in proposed["activities"] if not r["manual_override"]]
    assert {r["topic_id"] for r in automatic} == {"ckd", "dialysis"}
    assert all(r["objective_id"] == r["topic_id"] + "-objective" for r in automatic)
    assert all(r["reason"]["mapping_version"] == content.metadata[1]["version"] for r in automatic)
    assert general["dialysis"]["id"] not in {r["id"] for r in proposed["activities"]}
    # Filtering preserves canonical records; no preference change deletes old work.
    assert general["dialysis"]["id"] in {r["id"] for r in study.list_activities()}
    moved = next(r for r in proposed["activities"] if r["id"] == general["transplantation"]["id"])
    assert moved["outside_selection"] and moved["due_date"] == "2026-10-20"
    with TestClient(app_with_content(tmp_path, content)) as client:
        home = client.get("/api/v1/study/home").json()
        assert home["goals"] == goals()
        assert home["tracks"] == content.track_metadata()
        assert home["selection"]["topic_ids"] == ["ckd", "dialysis"]
        regenerated = client.post("/api/v1/study/plan/propose").json()["activities"]
        assert {r["id"] for r in regenerated} == {r["id"] for r in proposed["activities"]}
        for state, topic in (("skipped", "support"), ("completed", "ckd")):
            row = next(r for r in regenerated if r["id"] == general[topic]["id"])
            assert row["state"] == state and row["manual_override"]
        assert client.put("/api/v1/study/goals", json=goals("general", ["support"])).status_code == 200
        filtered = client.get("/api/v1/study/plan").json()
        assert filtered["selection"]["topic_ids"] == ["support"]
        assert not any(r["reason"].get("track") == "esen_eph" and not r["manual_override"] for r in filtered["activities"])


@pytest.mark.parametrize("topic", ["support", "transplantation", "retired-topic"])
def test_unmapped_and_missing_saved_topics_wait_without_general_fallback(tmp_path, topic):
    study = app_with_content(tmp_path, ProgrammeContent()).state.services.get("study")
    study.save_goals(goals(topic_ids=[topic]))
    result = study.propose(TODAY)
    assert result["status"] == "waiting-topics"
    assert result["activities"] == []
    assert study.goals() == goals(topic_ids=[topic])
    assert study.home()["selection"]["topic_ids"] == []


def test_mapped_mistakes_require_active_exact_pins_and_latest_family_answer(tmp_path):
    app = app_with_content(tmp_path, ProgrammeContent())
    services = app.state.services
    add_answer(services, "wrong-ckd", "ckd", "ckd-q")
    add_answer(services, "excluded-question", "ckd", "curriculum-only-q")
    add_answer(services, "old-version", "ckd", "ckd-q", version=2, family="different-family")
    add_answer(services, "wrong-dialysis", "dialysis", "dialysis-q")
    add_answer(services, "corrected-dialysis", "dialysis", "dialysis-q", correct=True)
    study = services.get("study")
    study.save_goals(goals())
    reviews = [r for r in study.propose(TODAY)["activities"] if r["kind"] == "mistake-review"]
    assert len(reviews) == 1
    assert reviews[0]["reason"]["question_id"] == "ckd-q"
    assert reviews[0]["reason"]["question_version"] == 1
    assert reviews[0]["reason"]["track"] == "esen_eph"
    assert study.progress()["groups"]["fresh"] == {"answered": 5, "correct": 1}


def test_unavailable_producer_preserves_preference_and_manual_row_without_mapped_claim(tmp_path):
    content = ProgrammeContent()
    app = app_with_content(tmp_path, content)
    study = app.state.services.get("study")
    row = study.propose(TODAY)["activities"][0]
    study.change_activity(row["id"], {"due_date": "2026-10-25"})
    study.save_goals(goals())
    content.metadata[1] = {"id": "esen_eph", "title": "ESENeph preparation", "available": False,
                           "reason": "No eligible active reviewed questions remain", "exam_simulation_available": False}
    result = study.propose(TODAY)
    assert result["status"] == "track-unavailable"
    assert len(result["activities"]) == 1
    assert result["activities"][0]["outside_selection"]
    assert study.home()["goals"] == goals()
    # The older producer seam must have the same honest unavailable behaviour.
    content.track_metadata = None
    assert study.propose(TODAY)["status"] == "track-unavailable"


def test_content_pin_withdrawal_hides_automatic_review_but_keeps_manual_override(tmp_path):
    content = ProgrammeContent()
    app = app_with_content(tmp_path, content)
    study = app.state.services.get("study")
    study.save_goals(goals())
    add_answer(app.state.services, "wrong-ckd", "ckd", "ckd-q")
    row = next(r for r in study.propose(TODAY)["activities"] if r["kind"] == "mistake-review")
    content.metadata[1]["domains"][0]["alignments"][0]["questions"] = [{"id": "dialysis-q", "version": 1}]
    assert row["id"] not in {r["id"] for r in study.plan()["activities"]}
    assert study.change_activity(row["id"], {"due_date": "2026-10-21"})["outside_selection"]
    kept = next(r for r in study.plan()["activities"] if r["id"] == row["id"])
    assert kept["outside_selection"] and kept["manual_override"]


def test_real_content_metadata_assessment_plan_home_and_restart(tmp_path):
    app = create_app(tmp_path, source_root=ROOT)
    with TestClient(app) as client:
        tracks = client.get("/api/v1/content/tracks").json()
        track = next(t for t in tracks if t["id"] == "esen_eph")
        assert track["available"] and not track["exam_simulation_available"]
        assert client.put("/api/v1/study/goals", json=goals()).status_code == 200
        home = client.get("/api/v1/study/home").json()
        assert home["tracks"] == tracks
        expected = {t["id"] for t in home["topics"]
                    if any(o["id"] in track["aligned_objective_ids"] for o in t["objectives"])}
        assert set(home["selection"]["topic_ids"]) == expected
        started = client.post("/api/v1/assessment/start", json={"count": 1,
            "selector": {"track": "esen_eph"}, "idempotency_key": "study-track-real-start"})
        assert started.status_code == 200, started.text
        session = started.json()
        item = session["current_item"]
        question = app.state.services.get("content").get_question_version(item["question_id"], item["question_version"])
        wrong = next(o["id"] for o in item["options"] if o["id"] not in question["correct_option_ids"])
        answer = client.post("/api/v1/assessment/sessions/" + session["id"] + "/answer", json={
            "item_id": item["id"], "option_ids": [wrong], "idempotency_key": "study-track-real-answer"})
        assert answer.status_code == 200, answer.text
        proposed = client.post("/api/v1/study/plan/propose").json()
        review = next(r for r in proposed["activities"] if r["kind"] == "mistake-review")
        assert review["reason"]["question_id"] == item["question_id"]
        assert review["objective_id"] in track["aligned_objective_ids"]
        assert review["reason"]["mapping_version"] == track["version"]
        assert set(r["topic_id"] for r in proposed["activities"]) <= expected
        saved = client.patch("/api/v1/study/plan/" + review["id"], json={"due_date": "2027-02-20"})
        assert saved.status_code == 200
    with TestClient(create_app(tmp_path, source_root=ROOT)) as restarted:
        home = restarted.get("/api/v1/study/home").json()
        assert home["goals"] == goals()
        assert home["progress"]["groups"]["fresh"] == {"answered": 1, "correct": 0}
        rows = restarted.post("/api/v1/study/plan/propose").json()["activities"]
        retained = next(r for r in rows if r["id"] == review["id"])
        assert retained["due_date"] == "2027-02-20" and retained["manual_override"]
        assert home["tracks"] == tracks
