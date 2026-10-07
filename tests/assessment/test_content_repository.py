"""Consumer integration through the real M8 repository, with original fixtures."""
import hashlib
import json

from fastapi.testclient import TestClient

from renulus.content.validation import coverage_for
from renulus.server import create_app

BASE = "/api/v1/assessment"
DOMAINS = ("dialysis", "glomerular", "transplant", "aki", "ckd", "electrolytes")


def synthetic_pack(path, correction=False):
    """Six-domain token exercises, not medical teaching or a distributable bank."""
    path.mkdir(parents=True)
    review = {"status": "assistant_reviewed", "reviewer": "Synthetic test author",
              "reviewer_kind": "assistant", "reviewed_on": "2026-10-04",
              "method": "Original token key and fixture locator checked locally",
              "source_key_checked": True, "independent_human_review": False}
    citation = {"source_id": "original-fixture", "locator": "Original token recipe, section 1"}
    topics, cases, questions = [], [], []
    for domain in DOMAINS:
        objectives = [{"id": domain + "-choose", "text": "Choose an original fixture token"},
                      {"id": domain + "-review", "text": "Review the original token key"}]
        topics.append({"id": domain, "version": 1, "label": domain + " fixture",
                       "description": "Synthetic application workflow without clinical facts",
                       "objectives": objectives, "license": "CC-BY-4.0",
                       "mapping": {"general_nephrology": True, "esen_eph": "not_formally_mapped"}})
        common = {"version": 1, "topic_id": domain, "secondary_topic_ids": [],
                  "objective_ids": [objective["id"] for objective in objectives],
                  "license": "CC-BY-4.0", "original": True, "sources": [citation], "review": review}
        cases.append({**common, "id": domain + "-fixture-case", "synthetic": True, "usage": "teaching",
                      "title": "Synthetic " + domain + " token case", "summary": "Original synthetic tokens",
                      "stages": [{"id": "stage-" + str(i), "narrative": "Original token stage",
                                  "prompts": ["Consider token a"], "teaching_points": ["Token a is marked"],
                                  "sources": [citation]} for i in (1, 2)], "take_home": ["Token choice is not clinical evidence"]})
        question = {**common, "id": domain + "-fixture-question", "family_id": domain + "-fixture-family",
                    "family_version": 1, "key_version": 1, "kind": "single_best_answer",
                    "usage": "assessment_reserved", "stem": "Original synthetic " + domain + ": choose token a",
                    "options": [{"id": option, "text": "Original token " + option,
                                 "rationale": "Original token " + option + " reasoning"} for option in "abcd"],
                    "answer": "a", "rationale": "Original marked token is a", "difficulty": "foundation"}
        if correction and domain == "dialysis":
            question.update(version=2, key_version=2, family_version=2, answer="b",
                            stem="Corrected original fixture: choose token b", rationale="Corrected token is b",
                            correction={"previous_version": 1, "reason": "Original synthetic correction"})
        questions.append(question)
    sources = [{"id": "original-fixture", "register_id": "K01", "title": "Original test token recipe",
                "edition": "Synthetic fixture v1; no medical content", "publication_status": "final",
                "url": "https://fixture.invalid/original", "canonical_topic_url": "https://fixture.invalid/original",
                "checked_on": "2026-10-04", "check_status": "locator_checked",
                "currency": "dated_final_baseline", "scope": "Original local test fixtures only",
                "rights_note": "Test author CC BY 4.0; no third-party text", "check_note": "Locally checked original token key"}]
    bundle = {"topics": topics, "cases": cases, "questions": questions, "sources": sources,
              "coverage": coverage_for(topics, cases, questions, DOMAINS, 6)}
    files = {}
    for name, value in bundle.items():
        payload = json.dumps(value).encode()
        (path / (name + ".json")).write_bytes(payload)
        files[name] = {"path": name + ".json", "sha256": hashlib.sha256(payload).hexdigest()}
    manifest = {"schema_version": 1, "repository_contract": 1, "id": "assessment-test-only",
                "version": "1.1.0" if correction else "1.0.0", "state": "published",
                "published_on": "2026-10-04", "title": "Original synthetic assessment fixture",
                "license": "CC-BY-4.0", "authors": ["Renulus test author"],
                "attribution": "Original synthetic test fixtures, CC BY 4.0. No clinical claims.",
                "source_register": "docs/SOURCES.md", "files": files,
                "claims": {"complete_curriculum": False, "complete_esen_eph_blueprint": False,
                           "independent_human_review": False},
                "withdrawals": [{"question_id": "dialysis-fixture-question", "version": 1,
                                  "reason": "Original synthetic correction", "replacement_version": 2}] if correction else []}
    (path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_real_content_repository_pack_scoring_corrections_and_restart(tmp_path):
    app = create_app(tmp_path / "profile")
    content = app.state.services.registry["content"]
    pack = synthetic_pack(tmp_path / "synthetic-pack")
    content.install_pack(pack)
    with TestClient(app) as client:
        start = client.post(BASE + "/start", json={"idempotency_key": "real-content-start", "count": 50}).json()
        assert start["item_count"] == 6 and start["coverage"]["insufficient_count"] is True
        rows = app.state.services.db.fetch_all("SELECT topic_id FROM assessment_items")
        assert {row["topic_id"] for row in rows} == set(DOMAINS)
        # Start across the pool selects aki first; choose an explicit dialysis
        # quiz to exercise the published correction and stable family identity.
        session = client.post(BASE + "/start", json={"idempotency_key": "dialysis-pack-start", "count": 1,
                              "selector": {"topic_ids": ["dialysis"]}}).json()
        body = {"idempotency_key": "real-content-answer", "item_id": session["current_item"]["id"], "option_ids": ["a"]}
        answered = client.post(BASE + f"/sessions/{session['id']}/answer", json=body)
        assert answered.status_code == 200, answered.text
        feedback = answered.json()["feedback"]
        assert feedback["sources"][0]["title"] == "Original test token recipe"
        assert feedback["sources"][0]["url"] == "https://fixture.invalid/original"
        assert feedback["sources"][0]["checked_on"] == "2026-10-04"
        assert content.teaching_material() and all(item["kind"] != "question" for item in content.teaching_material())
        content.install_pack(synthetic_pack(tmp_path / "corrected-pack", correction=True))
        retained = client.get(BASE + f"/sessions/{session['id']}/review").json()["feedback"][0]
        assert retained["content_status"]["status"] == "withdrawn"
        assert retained["content_status"]["withdrawal"]["replacement_version"] == 2
        assert retained["correct"] is True and retained["correct_option_ids"] == ["a"]
    reopened = create_app(tmp_path / "profile")
    with TestClient(reopened) as client:
        retained = client.get(BASE + f"/sessions/{session['id']}/review").json()["feedback"][0]
        assert retained["correct_option_ids"] == ["a"]
        next_session = client.post(BASE + "/start", json={"idempotency_key": "post-correction-start", "count": 1,
                                   "selector": {"topic_ids": ["dialysis"]}}).json()
        assert next_session["current_item"]["question_version"] == "2"
        assert next_session["current_item"]["repeat"] is True
        assert client.post(BASE + f"/sessions/{session['id']}/answer", json=body).json() == answered.json()
