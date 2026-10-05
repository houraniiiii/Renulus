"""One real Today API journey using the bundled original pack and isolated SQLite."""
from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from renulus.server import create_app

ROOT = Path(__file__).resolve().parents[2]


def seeded_app(profile):
    app = create_app(profile, source_root=ROOT)
    with TestClient(app) as api:
        initial = api.get("/api/v1/study/home").json()
        assert len(initial["topics"]) == len(app.state.services.get("content").list_topics())
        started = api.post("/api/v1/assessment/start", json={
            "count": 1, "selector": {"topic_ids": ["T03"]},
            "idempotency_key": "today-final-reviewed-start"})
        assert started.status_code == 200, started.text
        session = started.json()
        item = session["current_item"]
        key = app.state.services.get("content").get_question_version(item["question_id"], item["question_version"])
        wrong = next(option["id"] for option in item["options"] if option["id"] not in key["correct_option_ids"])
        answered = api.post("/api/v1/assessment/sessions/" + session["id"] + "/answer", json={
            "item_id": item["id"], "option_ids": [wrong], "idempotency_key": "today-final-reviewed-answer"})
        assert answered.status_code == 200, answered.text
        assert answered.json()["feedback"]["correct"] is False
        assert api.get("/api/v1/study/home").json()["progress"]["groups"]["fresh"] == {"answered": 1, "correct": 0}
        proposed = api.post("/api/v1/study/plan/propose").json()
        review = next(row for row in proposed["activities"] if row["kind"] == "mistake-review")
        assert review["topic_id"] == "T03"
        assert review["reason"]["question_id"] == item["question_id"]
    return app, session["id"], review["id"]


def test_reviewed_mistake_manual_changes_preferences_reload_and_propose_keep_original_scores(tmp_path):
    profile = tmp_path / "today-final"
    app, session_id, review_id = seeded_app(profile)
    with TestClient(app) as api:
        saved_goals = {"hours_per_week": 4, "exam_date": "2027-03-01",
                       "track": "eseneph", "topic_ids": ["T03", "T21"]}
        saved = api.put("/api/v1/study/goals", json=saved_goals)
        assert saved.status_code == 200
        assert saved.json() == saved_goals
        moved_date = (date.today() + timedelta(days=8)).isoformat()
        moved = api.patch("/api/v1/study/plan/" + review_id, json={"due_date": moved_date})
        assert moved.status_code == 200
        assert moved.json()["due_date"] == moved_date and moved.json()["manual_override"]
        rows = api.post("/api/v1/study/plan/propose").json()["activities"]
        others = [row for row in rows if row["id"] != review_id and row["state"] == "planned"]
        skipped = api.patch("/api/v1/study/plan/" + others[0]["id"], json={"state": "skipped"})
        completed = api.patch("/api/v1/study/plan/" + others[1]["id"], json={"state": "completed"})
        assert skipped.status_code == completed.status_code == 200
        expected = {review_id: ("planned", moved_date),
                    others[0]["id"]: ("skipped", others[0]["due_date"]),
                    others[1]["id"]: ("completed", others[1]["due_date"])}
    # Restart the real app on only this journey's profile; proposal must preserve manual facts.
    with TestClient(create_app(profile, source_root=ROOT)) as restarted:
        home = restarted.get("/api/v1/study/home").json()
        assert home["goals"] == saved_goals
        assert home["progress"]["groups"]["fresh"] == {"answered": 1, "correct": 0}
        rows = restarted.post("/api/v1/study/plan/propose").json()["activities"]
        for row in rows:
            if row["id"] in expected:
                assert (row["state"], row["due_date"]) == expected[row["id"]]
                assert row["manual_override"]
        assert expected.keys() <= {row["id"] for row in rows}
        reviewed = restarted.get("/api/v1/assessment/sessions/" + session_id + "/review").json()
        assert reviewed["feedback"][0]["correct"] is False


if __name__ == "__main__":
    import argparse
    import json
    import uvicorn
    parser = argparse.ArgumentParser(description="Isolated Today UI proof; original pack, no provider calls")
    parser.add_argument("--profile", required=True)
    parser.add_argument("--port", required=True, type=int)
    args = parser.parse_args()
    app, session_id, review_id = seeded_app(Path(args.profile).resolve())
    app = create_app(Path(args.profile).resolve(), source_root=ROOT)
    print(json.dumps({"topics": 27, "fresh_score": "0/1", "review_topic": "T03", "review_id": review_id}), flush=True)
    uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False, log_level="warning")
