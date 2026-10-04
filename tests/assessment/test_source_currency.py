"""Real original pack + Updates projection, with synthetic publisher bytes only."""
from pathlib import Path

from fastapi.testclient import TestClient

from renulus.server import create_app

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "content/packs/renulus-foundations/1.0.0"
BASE = "/api/v1/assessment"


class SyntheticPublisher:
    def __init__(self):
        self.observation = 0

    async def fetch(self, url, hosts, limit=2_000_000):
        self.observation += 1
        return b"%PDF-1.7 Synthetic currency fixture " + str(self.observation).encode(), {"content-type": "application/pdf"}, url


def currency_app(profile, token=None):
    app = create_app(profile, token=token, source_root=ROOT)
    services = app.state.services
    services.registry["content"].install_pack(PACK)
    services.registry["updates"].fetcher = SyntheticPublisher()
    return app


def start(client, key="currency-start", topic="T20"):
    response = client.post(BASE + "/start", json={"idempotency_key": key, "count": 1, "selector": {"topic_ids": [topic]}})
    assert response.status_code == 200, response.text
    return response.json()


def track_and_detect(app, client, session):
    services = app.state.services
    item = session["current_item"]
    question = services.registry["content"].get_question_version(item["question_id"], int(item["question_version"]))
    cited = {citation["source_id"] for citation in question["sources"]}
    source = next(source for source in question["source_records"] if source["register_id"] == "K01" and source["id"] in cited)
    updates = services.registry["updates"]
    publication = updates.publications.track("K01", source["url"], "Synthetic fixture digest permission; no live publisher review")
    route = "/api/v1/updates/publications/" + publication["id"] + "/check?force=true"
    assert client.post(route).json()["state"] == "baseline"
    assert client.post(route).json()["state"] == "changed"
    entry = next(row for row in updates.list_entries() if row["kind"] == "publication-change")
    return updates, entry, source, route


def review_notice(client, entry, source, state="reviewed"):
    body = {"state": state, "summary": "Synthetic publisher notice for software testing; no real educational review"}
    if state == "reviewed":
        body.update(target={"register_id": "K01", "canonical_url": source["url"]},
                    changes={"correction": "Synthetic correction reference"},
                    evidence=[{"url": source["url"], "locator": "Synthetic publisher fixture",
                               "finding": "Synthetic byte-change sequence only; no medical correctness claim",
                               "checked_on": "2026-10-04", "inspected": True}])
    response = client.post("/api/v1/updates/entries/" + entry["id"] + "/review", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def immutable_facts(app):
    db = app.state.services.db
    return {table: db.fetch_all("SELECT * FROM " + table + " ORDER BY " + order) for table, order in (
        ("assessment_attempts", "id"), ("assessment_commands", "idempotency_key"),
        ("learning_evidence", "id"), ("content_question_versions", "question_id,version"))} | {
        "snapshots": db.fetch_all("SELECT id,question_id,question_version,key_version,snapshot_json FROM assessment_items ORDER BY id")}


def test_detected_notice_appears_on_exact_pending_items_paused_sessions_and_history(tmp_path):
    app = currency_app(tmp_path / "profile")
    with TestClient(app) as client:
        session = start(client)
        other = start(client, "aki-currency-start", topic="T06")
        updates, entry, source, _ = track_and_detect(app, client, session)
        current = client.get(BASE + "/sessions/" + session["id"]).json()
        currency = current["current_item"]["source_currency"]
        assert currency["state"] == "available" and currency["needs_re_review"] is True
        assert all(row["pinned_source_id"] == source["id"] and row["entry_id"] == entry["id"] for row in currency["annotations"])
        assert currency["annotations"][0]["review_state"] == "pending"
        assert currency["annotations"][0]["locators"]
        assert app.state.services.registry["assessment"].currency.for_item({
            "question_id": session["current_item"]["question_id"], "question_version": "2"
        })["needs_re_review"] is False
        assert current["current_item"]["content_status"]["status"] == "current"
        assert current["source_currency"]["pending_affected_count"] == 1
        assert "correct_option_ids" not in current["current_item"] and "explanation" not in current["current_item"]
        assert client.get(BASE + "/sessions/" + other["id"]).json()["source_currency"]["needs_re_review"] is False
        paused = client.post(BASE + "/sessions/" + session["id"] + "/pause", json={"idempotency_key": "currency-pause"}).json()
        assert paused["current_item"] is None and paused["source_currency"]["affected_count"] == 1
        history = {row["id"]: row for row in client.get(BASE + "/sessions").json()["sessions"]}
        assert history[session["id"]]["source_currency"]["needs_re_review"] is True
        assert history[other["id"]]["source_currency"]["needs_re_review"] is False
        assert history[session["id"]]["current_item"] is None
        # The consumer used the published M7 seam, not source-family inference.
        assert currency["annotations"][0]["entry_id"] in {row["entry_id"] for row in updates.affected.needs_re_review("question", session["current_item"]["question_id"], 1)["annotations"]}


def test_review_and_dismissal_refresh_feedback_replays_without_rewriting_attempt_facts(tmp_path):
    profile = tmp_path / "profile"
    app = currency_app(profile)
    with TestClient(app) as client:
        session = start(client)
        item = session["current_item"]
        question = app.state.services.registry["content"].get_question_version(item["question_id"], 1)
        request = {"idempotency_key": "currency-answer", "item_id": item["id"], "option_ids": question["correct_option_ids"]}
        original = client.post(BASE + "/sessions/" + session["id"] + "/answer", json=request).json()
        facts = immutable_facts(app)
        assert all("source_currency" not in row["result_json"] for row in facts["assessment_commands"])
        updates, entry, source, _ = track_and_detect(app, client, session)
        detected = client.get(BASE + "/sessions/" + session["id"] + "/review").json()["feedback"][0]
        assert detected["source_currency"]["needs_re_review"] is True
        assert detected["correct_option_ids"] == original["feedback"]["correct_option_ids"]
        review_notice(client, entry, source)
        reviewed = client.post(BASE + "/sessions/" + session["id"] + "/answer", json=request).json()
        assert reviewed["feedback"]["source_currency"]["annotations"][0]["review_state"] == "reviewed"
        assert reviewed["feedback"]["source_currency"]["needs_re_review"] is True
        assert reviewed["feedback"]["correct"] == original["feedback"]["correct"]
        assert reviewed["session"]["scores"] == original["session"]["scores"]
        assert reviewed["feedback"]["committed_at"] == original["feedback"]["committed_at"]
        assert reviewed["feedback"]["item"] == original["feedback"]["item"]
        review_notice(client, entry, source, "dismissed")
        dismissed = client.get(BASE + "/sessions/" + session["id"] + "/review").json()["feedback"][0]
        assert dismissed["source_currency"]["needs_re_review"] is False
        assert dismissed["source_currency"]["annotations"][0]["state"] == "dismissed"
        assert dismissed["source_currency"]["annotations"][0]["review_state"] == "dismissed"
        assert dismissed["content_status"]["status"] == "current"
        assert dismissed["correct_option_ids"] == original["feedback"]["correct_option_ids"]
        assert immutable_facts(app) == facts
    reopened = currency_app(profile)
    with TestClient(reopened) as client:
        replay = client.post(BASE + "/sessions/" + session["id"] + "/answer", json=request).json()
        assert replay["feedback"]["source_currency"]["annotations"][0]["state"] == "dismissed"
        assert replay["feedback"]["correct_option_ids"] == original["feedback"]["correct_option_ids"]
        assert immutable_facts(reopened) == facts


def test_dismissing_one_notice_keeps_newer_change_and_unavailable_is_not_clear(tmp_path, monkeypatch):
    app = currency_app(tmp_path / "profile")
    with TestClient(app) as client:
        session = start(client)
        updates, entry, source, route = track_and_detect(app, client, session)
        assert client.post(route).json()["state"] == "changed"
        review_notice(client, entry, source, "dismissed")
        current = client.get(BASE + "/sessions/" + session["id"]).json()["current_item"]
        assert current["source_currency"]["needs_re_review"] is True
        assert {row["state"] for row in current["source_currency"]["annotations"]} == {"dismissed", "needs-re-review"}
        def unavailable(*args):
            raise RuntimeError("Synthetic projection unavailable")
        monkeypatch.setattr(updates.affected, "needs_re_review", unavailable)
        failed = client.get(BASE + "/sessions/" + session["id"]).json()
        assert failed["current_item"]["source_currency"] == {"state": "unavailable", "needs_re_review": None, "annotations": []}
        assert failed["source_currency"]["state"] == "unavailable"
        assert failed["source_currency"]["needs_re_review"] is None
        assert failed["current_item"]["content_status"]["status"] == "current"


def test_projection_identity_and_key_free_allowlist_are_checked(tmp_path, monkeypatch):
    app = currency_app(tmp_path / "profile")
    with TestClient(app) as client:
        session = start(client)
        updates, _, _, _ = track_and_detect(app, client, session)
        item = session["current_item"]
        original_lookup = updates.affected.needs_re_review
        def extended(*args):
            result = original_lookup(*args)
            result["annotations"][0].update(finding="PRIVATE_FINDING_SENTINEL", correct_option_ids=["PRIVATE_KEY_SENTINEL"])
            return result
        monkeypatch.setattr(updates.affected, "needs_re_review", extended)
        response = client.get(BASE + "/sessions/" + session["id"])
        assert response.json()["current_item"]["source_currency"]["needs_re_review"] is True
        assert "PRIVATE_FINDING_SENTINEL" not in response.text and "PRIVATE_KEY_SENTINEL" not in response.text
        def wrong_version(*args):
            result = original_lookup(*args)
            result["version"] += 1
            return result
        monkeypatch.setattr(updates.affected, "needs_re_review", wrong_version)
        assert client.get(BASE + "/sessions/" + session["id"]).json()["source_currency"]["state"] == "unavailable"
        app.state.services.registry.pop("updates")
        unavailable = client.get(BASE + "/sessions/" + session["id"]).json()["current_item"]
        assert unavailable["source_currency"]["needs_re_review"] is None
        question = app.state.services.registry["content"].get_question_version(item["question_id"], 1)
        answered = client.post(BASE + "/sessions/" + session["id"] + "/answer", json={
            "idempotency_key": "unavailable-answer", "item_id": item["id"], "option_ids": question["correct_option_ids"]})
        assert answered.status_code == 200 and answered.json()["feedback"]["correct"] is True
