from datetime import date
import json

from fastapi.testclient import TestClient

from renulus.server import create_app
from renulus.storage import utc_now


class Content:
    def list_topics(self):
        return [{"id": "ckd", "title": "CKD"}, {"id": "dialysis", "title": "Dialysis"},
                {"id": "transplantation", "title": "Transplantation"}]


def evidence(services, id, topic, correct, **flags):
    services.db.execute("INSERT INTO learning_evidence VALUES(?,?,?,?,?,?)",
        (id, "assessment-answer", topic, id, json.dumps({"question_id": id,
          "correct": correct, **flags}), utc_now()))


def test_mistake_priority_manual_edit_and_restart(tmp_path):
    app = create_app(tmp_path)
    services = app.state.services
    services.registry["content"] = Content()
    evidence(services, "wrong-dialysis", "dialysis", False)
    service = services.registry["study"]
    result = service.propose(date(2026, 10, 4))
    first = result["activities"][0]
    assert first["kind"] == "mistake-review"
    assert first["topic_id"] == "dialysis"
    service.change_activity(first["id"], {"due_date": "2026-10-08", "state": "skipped"})
    service.propose(date(2026, 10, 4))
    with TestClient(create_app(tmp_path)) as client:
        rows = client.get("/api/v1/study/plan").json()["activities"]
        moved = next(row for row in rows if row["id"] == first["id"])
        assert moved["due_date"] == "2026-10-08"
        assert moved["state"] == "skipped"
        assert moved["manual_override"]
        assert len({row["id"] for row in rows}) == len(rows)


def test_progress_separates_observed_groups_and_ignores_chat_volume(tmp_path):
    app = create_app(tmp_path)
    services = app.state.services
    evidence(services, "fresh-wrong", "ckd", False)
    evidence(services, "assisted-right", "ckd", True, assisted=True)
    evidence(services, "repeat-right", "dialysis", True, repeat=True)
    services.db.execute("INSERT INTO learning_evidence VALUES(?,?,?,?,?,?)",
        ("interest", "study-interest", "transplantation", None, "{}", utc_now()))
    groups = services.registry["study"].progress()["groups"]
    assert groups == {"fresh": {"answered": 1, "correct": 0},
                      "assisted": {"answered": 1, "correct": 1},
                      "repeat": {"answered": 1, "correct": 1}}


def test_confirmed_completion_is_idempotent_and_new_home_has_no_fake_progress(tmp_path):
    app = create_app(tmp_path)
    services = app.state.services
    services.registry["content"] = Content()
    service = services.registry["study"]
    assert service.home()["resume"] == []
    assert service.home()["progress"]["groups"]["fresh"]["answered"] == 0
    activity = service.propose(date(2026, 10, 4))["activities"][0]
    service.change_activity(activity["id"], {"state": "completed"})
    service.change_activity(activity["id"], {"state": "completed"})
    assert len(services.db.fetch_all("SELECT * FROM learning_evidence WHERE kind='study-completion'")) == 1


def test_progress_follows_committed_assessment_bucket_and_legacy_assisted_priority(tmp_path):
    services = create_app(tmp_path).state.services
    evidence(services, "assisted-repeat", "ckd", True, assisted=True, repeat=True, score_bucket="assisted")
    evidence(services, "legacy-assisted-repeat", "dialysis", False, assisted=True, repeat=True)
    evidence(services, "canonical-repeat", "transplantation", True, repeat=False, score_bucket="repeat")
    assert services.get("study").progress()["groups"] == {
        "fresh": {"answered": 0, "correct": 0},
        "assisted": {"answered": 2, "correct": 1},
        "repeat": {"answered": 1, "correct": 1},
    }
