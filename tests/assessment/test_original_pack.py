"""Acceptance against M8's original teaching pack after its separate handoff."""
from pathlib import Path
import os

from fastapi.testclient import TestClient
import pytest

from renulus.server import create_app

ROOT = Path(__file__).resolve().parents[2]
PACK = Path(os.environ.get("RENULUS_ASSESSMENT_TEST_PACK",
            str(ROOT / "content/packs/renulus-foundations/1.0.0/manifest.json")))
BASE = "/api/v1/assessment"


@pytest.mark.skipif(not PACK.is_file(), reason="M8 original published pack has not been handed off")
def test_original_published_pack_produces_durable_cross_domain_reviewed_results(tmp_path):
    app = create_app(tmp_path / "original-pack-profile", source_root=ROOT)
    content = app.state.services.registry["content"]
    # Explicitly selected authored pack only; never ingest sibling directories.
    content.install_pack(PACK.resolve().parent)
    with TestClient(app) as client:
        catalog = client.get(BASE + "/catalog").json()
        assert sum(domain["available_families"] > 0 for domain in catalog["domains"]) >= 6
        assert catalog["complete_exam_available"] is False
        session = client.post(BASE + "/start", json={"idempotency_key": "original-pack-start",
                              "count": 50}).json()
        session_id = session["id"]
        seen_topics, first_request, first_response = set(), None, None
        for index in range(session["item_count"]):
            if index:
                session = client.get(BASE + f"/sessions/{session_id}").json()
            item = session["current_item"]
            assert "correct_option_ids" not in item
            seen_topics.add(item["topic_id"])
            key = content.get_question_version(item["question_id"], int(item["question_version"]))
            if index == 0:
                help_result = client.post(BASE + f"/sessions/{session_id}/help", json={
                    "idempotency_key": "original-pack-help", "item_id": item["id"], "kind": "sources"})
                assert help_result.status_code == 200
            request = {"idempotency_key": "original-pack-answer-" + str(index), "item_id": item["id"],
                       "option_ids": key["correct_option_ids"]}
            response = client.post(BASE + f"/sessions/{session_id}/answer", json=request)
            assert response.status_code == 200, response.text
            result = response.json()
            assert result["feedback"]["correct"] is True
            assert result["feedback"]["explanation"] == key["rationale"]
            assert all(source.get("url", "").startswith("https://") for source in result["feedback"]["sources"])
            assert all(source.get("checked_on") for source in result["feedback"]["sources"])
            if index == 0:
                first_request, first_response = request, result
        assert len(seen_topics) >= 6
        scores = result["session"]["scores"]["reviewed"]
        assert scores["assisted"]["answered"] == 1
        assert scores["fresh"]["answered"] == session["item_count"] - 1
        assert scores["repeat"]["answered"] == 0
        assert len(app.state.services.db.fetch_all("SELECT * FROM learning_evidence WHERE kind='assessment-answer'")) == session["item_count"]
    with TestClient(create_app(tmp_path / "original-pack-profile", source_root=ROOT)) as restarted:
        replay = restarted.post(BASE + f"/sessions/{session_id}/answer", json=first_request)
        assert replay.json() == first_response
        review = restarted.get(BASE + f"/sessions/{session_id}/review").json()
        assert len(review["feedback"]) == session["item_count"]
