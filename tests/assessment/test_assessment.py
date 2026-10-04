from concurrent.futures import ThreadPoolExecutor
import json

from fastapi.testclient import TestClient

from renulus.assessment.contracts import AnswerRequest, Command, HelpRequest
from renulus.contracts import ApiError
from renulus.server import create_app

BASE = "/api/v1/assessment"


def start(client, key="start-0001", count=3, **selector):
    response = client.post(BASE + "/start", json={"idempotency_key": key,
                           "count": count, "selector": selector})
    assert response.status_code == 200, response.text
    return response.json()


def answer(client, session, key="answer-0001", option="a"):
    return client.post(BASE + f"/sessions/{session['id']}/answer",
                       json={"idempotency_key": key, "item_id": session["current_item"]["id"],
                             "option_ids": [option]})


def test_chooser_spans_domains_reports_shortfall_and_never_leaks_keys(client, app):
    catalog = client.get(BASE + "/catalog").json()
    assert len(catalog["domains"]) == 3
    assert catalog["complete_exam_available"] is False
    session = start(client, count=10)
    assert session["item_count"] == 3
    assert session["coverage"]["insufficient_count"] is True
    assert session["scope"]["kind"] == "reviewed-assessment"
    db = app.state.services.db
    rows = db.fetch_all("SELECT topic_id,presented_at FROM assessment_items")
    assert {row["topic_id"] for row in rows} == {"dialysis", "glomerular", "transplant"}
    assert sum(row["presented_at"] is not None for row in rows) == 1
    assert "PRIVATE_" not in json.dumps(session)
    assert "correct_option_ids" not in session["current_item"]
    assert "rationale" not in json.dumps(session["current_item"])
    assert len(db.fetch_all("SELECT * FROM assessment_exposure")) == 1


def test_filter_and_track_do_not_invent_coverage(client):
    assert client.get(BASE + "/catalog", params={"track": ""}).status_code == 422
    session = start(client, topic_ids=["transplant", "missing"], count=2)
    assert session["current_item"]["topic_id"] == "transplant"
    assert session["coverage"]["missing_topic_ids"] == ["missing"]
    response = client.post(BASE + "/start", json={"idempotency_key": "empty-0001",
                           "selector": {"track": "esen_eph"}})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "insufficient_coverage"


def test_start_idempotency_conflicts_and_generated_is_separate(client, app):
    first = start(client)
    assert start(client) == first
    assert len(app.state.services.db.fetch_all("SELECT * FROM assessment_sessions")) == 1
    response = client.post(BASE + "/start", json={"idempotency_key": "start-0001", "count": 2})
    assert response.status_code == 409
    response = client.post(BASE + "/start", json={"idempotency_key": "generated-0001",
                                                "mode": "generated"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "generated_practice_unavailable"
    assert client.get(BASE + "/aggregates").json()["generated"]["answered"] == 0


def test_answer_commits_fixed_versions_score_and_evidence_once(client, app):
    session = start(client)
    response = answer(client, session)
    assert response.status_code == 200, response.text
    result = response.json()
    assert answer(client, session).json() == result
    assert result["feedback"]["correct"] is True
    assert result["feedback"]["score_bucket"] == "fresh"
    assert result["feedback"]["explanation"] == "PRIVATE_REVIEWED_KEY_SENTINEL"
    assert result["feedback"]["sources"][0]["locator"] == "Fixture section 1"
    db = app.state.services.db
    attempts = db.fetch_all("SELECT * FROM assessment_attempts")
    evidence = db.fetch_all("SELECT * FROM learning_evidence")
    assert len(attempts) == len(evidence) == 1
    assert attempts[0]["question_version"] == attempts[0]["key_version"] == "1"
    payload = json.loads(evidence[0]["payload_json"])
    assert evidence[0]["kind"] == "assessment-answer"
    assert evidence[0]["entity_id"] == attempts[0]["id"]
    assert evidence[0]["topic_id"] == session["current_item"]["topic_id"]
    assert payload["correct"] is True and payload["assisted"] is False and payload["repeat"] is False
    assert payload["session_id"] == session["id"]
    assert payload["attempt_id"] == attempts[0]["id"]
    assert payload["objective_id"] == session["current_item"]["topic_id"] + "-objective"
    assert "PRIVATE_" not in evidence[0]["payload_json"]
    assert "stem" not in payload and "correct_option_ids" not in payload
    assert answer(client, session, key="answer-0002").status_code == 409
    assert answer(client, session, option="b").status_code == 409


def test_evidence_failure_rolls_back_score_answer_exposure_and_retry(app, client):
    session = start(client)
    db = app.state.services.db
    db.execute("CREATE TRIGGER fail_evidence BEFORE INSERT ON learning_evidence "
               "BEGIN SELECT RAISE(ABORT, 'synthetic crash'); END")
    failed = answer(client, session)
    assert failed.status_code == 503
    assert failed.json()["error"]["code"] == "assessment_storage_failed"
    assert failed.json()["error"]["retryable"] is True
    assert "synthetic crash" not in failed.text
    assert db.fetch_all("SELECT * FROM assessment_attempts") == []
    assert db.fetch_all("SELECT * FROM learning_evidence") == []
    assert db.fetch_all("SELECT * FROM assessment_exposure WHERE kind IN ('answered','reviewed')") == []
    assert db.fetch_one("SELECT 1 FROM assessment_commands WHERE operation='answer'") is None
    db.execute("DROP TRIGGER fail_evidence")
    assert answer(client, session).status_code == 200
    assert len(db.fetch_all("SELECT * FROM learning_evidence")) == 1


def test_help_marks_assistance_before_return_and_cannot_reveal_key(client, app):
    session = start(client)
    path = BASE + f"/sessions/{session['id']}/help"
    request = {"idempotency_key": "help-0001", "item_id": session["current_item"]["id"],
               "kind": "sources"}
    result = client.post(path, json=request)
    assert result.status_code == 200
    assert client.post(path, json=request).json() == result.json()
    db = app.state.services.db
    assert db.fetch_one("SELECT assisted FROM assessment_items WHERE id=?",
                        (session["current_item"]["id"],))["assisted"] == 1
    assert len(db.fetch_all("SELECT * FROM assessment_exposure WHERE kind='sources'")) == 1
    assert "PRIVATE_" not in result.text
    assert answer(client, session).json()["feedback"]["score_bucket"] == "assisted"


def test_missing_authored_hint_does_not_fake_help_or_mark_assisted(client, content, app):
    for question in content.versions.values():
        question.pop("hint")
    session = start(client)
    response = client.post(BASE + f"/sessions/{session['id']}/help", json={
        "idempotency_key": "hint-0001", "item_id": session["current_item"]["id"], "kind": "hint"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "hint_unavailable"
    assert app.state.services.db.fetch_one("SELECT assisted FROM assessment_items WHERE id=?",
                                          (session["current_item"]["id"],))["assisted"] == 0


def test_review_is_commit_gated_and_mistakes_are_key_free(client):
    session = start(client)
    path = BASE + f"/sessions/{session['id']}/review"
    assert client.get(path).json()["feedback"] == []
    assert client.get(path, params={"item_id": session["current_item"]["id"]}).status_code == 409
    assert answer(client, session, option="b").json()["feedback"]["correct"] is False
    review = client.get(path, params={"mistakes_only": True}).json()
    assert len(review["feedback"]) == 1
    assert review["feedback"][0]["selected_option_ids"] == ["b"]
    mistakes = client.get(BASE + "/mistakes").json()
    assert len(mistakes["mistakes"]) == 1
    assert "PRIVATE_" not in json.dumps(mistakes)
    assert client.get(BASE + "/progress").json()["mastery_inferred"] is False


def test_pause_resume_restart_preserves_attempt_and_retry(client, app, content):
    session = start(client)
    original = answer(client, session).json()
    session_id = session["id"]
    paused = client.post(BASE + f"/sessions/{session_id}/pause", json={
        "idempotency_key": "pause-0001"}).json()
    assert paused["status"] == "paused" and paused["current_item"] is None
    reopened = create_app(app.state.services.paths.root)
    reopened.state.services.registry["content"] = content
    with TestClient(reopened) as second:
        assert second.get(BASE + f"/sessions/{session_id}").json()["answered_count"] == 1
        assert answer(second, session).json() == original
        resumed = second.post(BASE + f"/sessions/{session_id}/resume", json={
            "idempotency_key": "resume-0001"}).json()
        assert resumed["status"] == "active"
        assert resumed["current_item"]["ordinal"] == 2
        assert answer(second, resumed, key="answer-0002").status_code == 200
        ended = second.post(BASE + f"/sessions/{session_id}/end", json={
            "idempotency_key": "end-0001"}).json()
        assert ended["answered_count"] == 2 and ended["item_count"] == 3
        assert ended["current_item"] is None
        assert second.post(BASE + f"/sessions/{session_id}/resume", json={
            "idempotency_key": "resume-0002"}).status_code == 409


def test_cancelled_exposure_follows_family_across_corrected_versions(client, content):
    old = start(client, count=1, topic_ids=["dialysis"])
    client.post(BASE + f"/sessions/{old['id']}/end", json={"idempotency_key": "end-0001"})
    content.correct("synthetic-dialysis")
    new = start(client, key="start-0002", count=1, topic_ids=["dialysis"])
    assert new["current_item"]["question_version"] == "2"
    assert new["current_item"]["family_version"] == "2"
    assert new["current_item"]["repeat"] is True
    result = answer(client, new, option="b").json()
    assert result["feedback"]["score_bucket"] == "repeat"
    assert result["feedback"]["correct"] is True


def test_corrections_and_withdrawals_annotate_without_rewriting_history(client, content, app):
    old = start(client, count=1, topic_ids=["dialysis"])
    answer(client, old)
    pinned = app.state.services.db.fetch_one("SELECT snapshot_json FROM assessment_items")["snapshot_json"]
    content.correct("synthetic-dialysis")
    review_path = BASE + f"/sessions/{old['id']}/review"
    corrected = client.get(review_path).json()["feedback"][0]
    assert corrected["content_status"]["status"] == "corrected"
    assert corrected["correct"] is True and corrected["correct_option_ids"] == ["a"]
    assert corrected["explanation"] == "PRIVATE_REVIEWED_KEY_SENTINEL"
    content.withdraw("synthetic-dialysis", 1)
    withdrawn = client.get(review_path).json()["feedback"][0]
    assert withdrawn["content_status"]["status"] == "withdrawn"
    assert withdrawn["correct"] is True
    assert app.state.services.db.fetch_one("SELECT snapshot_json FROM assessment_items")["snapshot_json"] == pinned
    assert client.get(BASE + "/aggregates").json()["reviewed"]["fresh"]["correct"] == 1


def test_content_change_after_presentation_blocks_new_answer_without_losing_history(client, content, app):
    session = start(client, count=1, topic_ids=["dialysis"])
    content.withdraw("synthetic-dialysis")
    response = answer(client, session)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "content_changed"
    assert app.state.services.db.fetch_all("SELECT * FROM assessment_attempts") == []


def test_assisted_repeat_and_fresh_are_separate_and_generated_does_not_enter_scores(client):
    first = start(client, count=1, topic_ids=["dialysis"])
    answer(client, first)
    repeated = start(client, key="start-0002", count=1, topic_ids=["dialysis"])
    answer(client, repeated, key="answer-0002", option="b")
    assisted = start(client, key="start-0003", count=1, topic_ids=["glomerular"])
    client.post(BASE + f"/sessions/{assisted['id']}/help", json={"idempotency_key": "help-0001",
                 "item_id": assisted["current_item"]["id"], "kind": "hint"})
    answer(client, assisted, key="answer-0003")
    scores = client.get(BASE + "/aggregates").json()
    assert [scores["reviewed"][name]["answered"] for name in ("fresh", "assisted", "repeat")] == [1, 1, 1]
    assert [scores["reviewed"][name]["correct"] for name in ("fresh", "assisted", "repeat")] == [1, 1, 0]
    assert scores["generated"]["answered"] == 0


def test_parallel_answer_retries_commit_exactly_once(client, app):
    session = start(client)
    repository = app.state.services.registry["assessment"]
    request = AnswerRequest(idempotency_key="answer-parallel", item_id=session["current_item"]["id"],
                            option_ids=["a"])
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: repository.answer(session["id"], request), range(2)))
    assert results[0] == results[1]
    assert len(app.state.services.db.fetch_all("SELECT * FROM assessment_attempts")) == 1
    assert len(app.state.services.db.fetch_all("SELECT * FROM learning_evidence")) == 1


def test_help_answer_race_is_serialised_with_truthful_assistance(client, app):
    session = start(client)
    repository = app.state.services.registry["assessment"]
    item_id = session["current_item"]["id"]
    operations = [lambda: repository.help(session["id"], HelpRequest(
        idempotency_key="help-race", item_id=item_id, kind="sources")),
        lambda: repository.answer(session["id"], AnswerRequest(
        idempotency_key="answer-race", item_id=item_id, option_ids=["a"]))]
    def run(operation):
        try:
            return operation()
        except ApiError as error:
            return error.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        helped, answered = list(pool.map(run, operations))
    assert answered["feedback"]["assisted"] is (helped != "answer_already_committed")
    evidence = app.state.services.db.fetch_one("SELECT payload_json FROM learning_evidence")
    assert json.loads(evidence["payload_json"])["assisted"] == answered["feedback"]["assisted"]


def test_invalid_answers_and_scope_payloads_do_not_write(client, app):
    session = start(client)
    assert answer(client, session, option="unknown").status_code == 422
    response = client.post(BASE + "/start", json={"idempotency_key": "invalid-0001",
                           "scope": {"kind": "temporary-case"}, "count": 1})
    assert response.status_code == 422
    assert app.state.services.db.fetch_all("SELECT * FROM assessment_attempts") == []


def test_end_answer_race_retains_one_atomic_outcome(client, app):
    session = start(client)
    repository = app.state.services.registry["assessment"]
    operations = [lambda: repository.transition(session["id"], "end", Command(idempotency_key="end-race")),
                  lambda: repository.answer(session["id"], AnswerRequest(
                      idempotency_key="answer-end-race", item_id=session["current_item"]["id"], option_ids=["a"]))]
    def run(operation):
        try:
            return operation()
        except ApiError as error:
            return error.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        ended, answered = list(pool.map(run, operations))
    assert ended["status"] == "ended"
    attempts = app.state.services.db.fetch_all("SELECT * FROM assessment_attempts")
    evidence = app.state.services.db.fetch_all("SELECT * FROM learning_evidence")
    if answered == "session_not_active":
        assert attempts == evidence == []
    else:
        assert answered["feedback"]["correct"] is True
        assert len(attempts) == len(evidence) == 1
    assert repository.session(session["id"])["answered_count"] == len(attempts)
