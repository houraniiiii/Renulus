"""Synthetic consumer checks against M8's key-free track metadata contract."""
from copy import deepcopy
import json

import pytest

from conftest import SyntheticContentRepository
from renulus.assessment.contracts import Selector


BASE = "/api/v1/assessment"
COVERAGE_NOTE = ("Partial assistant mapping of synthetic original learning content. "
                 "No clinician review, curriculum mastery or exam simulation is established.")


class MappedContentRepository(SyntheticContentRepository):
    """Explicit synthetic pins; no topic-name inference or clinical content."""
    def __init__(self):
        super().__init__()
        variant = deepcopy(self.versions[("synthetic-dialysis", 1)])
        variant["id"] = "synthetic-dialysis-variant"
        variant["stem"] = "Synthetic dialysis variant: select the marked token."
        self.versions[(variant["id"], 1)] = variant
        self.active[variant["id"]] = 1
        self.mapped_pins = {("synthetic-dialysis", 1), (variant["id"], 1),
                            ("synthetic-transplant", 1)}

    def list_question_summaries(self, topic_id=None, domain=None, track=None):
        if track not in (None, "general_nephrology", "esen_eph"):
            return []
        questions = super().list_question_summaries(topic_id, domain)
        return [q for q in questions if (q["id"], q["version"]) in self.mapped_pins] \
            if track == "esen_eph" else questions

    def track_metadata(self):
        general = self.list_question_summaries()
        mapped = self.list_question_summaries(track="esen_eph")
        domains = []
        for id, label, topic, indicative in (
                ("synthetic-haemodialysis", "Haemodialysis fixture domain", "dialysis", 4),
                ("synthetic-transplantation", "Transplantation fixture domain", "transplant", 3),
                ("synthetic-gap", "Uncovered fixture domain", None, 2)):
            questions = [q for q in mapped if q["topic_id"] == topic]
            families = len({q["family_id"] for q in questions})
            domains.append({"id": id, "label": label, "indicative_questions": indicative,
                            "available_questions": len(questions), "available_families": families,
                            "family_shortfall": indicative - families,
                            "status": "partial" if questions else "gap"})
        return [{"id": "general_nephrology", "title": "General nephrology",
                 "available": bool(general), "available_questions": len(general),
                 "available_families": len({q["family_id"] for q in general}),
                 "exam_simulation_available": False, "domains": []},
                {"id": "esen_eph", "title": "ESENeph preparation",
                 "available": bool(mapped), "available_questions": len(mapped),
                 "available_families": len({q["family_id"] for q in mapped}),
                 "status": "partial", "checked_on": "2026-10-05",
                 "coverage_note": COVERAGE_NOTE, "exam_simulation_available": False,
                 "format_compatible_questions": 0, "domains": domains,
                 **({"reason": "No eligible active questions remain in the mapped track"} if not mapped else {})}]


@pytest.fixture
def mapped_content(app):
    content = MappedContentRepository()
    app.state.services.registry["content"] = content
    return content


def launch(client, key, count=10, **selector):
    return client.post(BASE + "/start", json={"idempotency_key": key, "count": count,
                                             "selector": {"track": "esen_eph", **selector}})


def assert_no_content(value):
    if isinstance(value, dict):
        assert not {"stem", "answer", "correct_option_ids", "rationale", "explanation", "options"} & value.keys()
        for child in value.values():
            assert_no_content(child)
    elif isinstance(value, list):
        for child in value:
            assert_no_content(child)


def test_legacy_adapter_is_explicitly_unmapped_even_if_it_ignores_track(client, content, monkeypatch):
    original = content.list_question_summaries
    monkeypatch.setattr(content, "list_question_summaries",
                        lambda **kwargs: original(track=None))
    general = client.get(BASE + "/catalog").json()
    assert general["available_families"] == 3
    esen = next(t for t in general["tracks"] if t["id"] == "esen_eph")
    assert esen["available"] is False
    assert esen["status"] == "not_formally_mapped"
    assert esen["reason"] and esen["exam_simulation_available"] is False
    assert esen["available_questions"] == esen["available_families"] == 0
    catalog = client.get(BASE + "/catalog", params={"track": "esen_eph"}).json()
    assert catalog["track"] == "esen_eph"
    assert catalog["available_questions"] == catalog["available_families"] == 0
    assert launch(client, "legacy-track-unavailable").status_code == 409
    assert_no_content(catalog)


def test_empty_legacy_general_pool_is_not_advertised_as_available(client, content):
    content.active.clear()
    catalog = client.get(BASE + "/catalog").json()
    assert not any(t["available"] for t in catalog["tracks"])
    assert catalog["available_questions"] == catalog["available_families"] == 0


def test_catalog_consumes_content_counts_and_indicative_gaps_without_keys(client, mapped_content, app, monkeypatch):
    expected = mapped_content.track_metadata()
    def no_question_lookup(*args):
        pytest.fail("The catalog must never resolve a question's stem or key")
    monkeypatch.setattr(mapped_content, "get_question_version", no_question_lookup)
    catalog = client.get(BASE + "/catalog", params={"track": "esen_eph"}).json()
    assert catalog["tracks"] == expected
    assert catalog["coverage_note"] == COVERAGE_NOTE
    assert catalog["available_questions"] == 3
    assert catalog["available_families"] == 2
    assert {d["id"]: d["available_families"] for d in catalog["domains"]} == {
        "dialysis": 1, "glomerular": 0, "transplant": 1}
    track = catalog["tracks"][1]
    assert track["checked_on"] == "2026-10-05"
    assert track["format_compatible_questions"] == 0
    assert [d["family_shortfall"] for d in track["domains"]] == [3, 2, 2]
    assert track["domains"][-1]["status"] == "gap"
    assert catalog["complete_exam_available"] is False
    assert_no_content(catalog)
    for table in ("assessment_items", "assessment_exposure", "assessment_attempts"):
        assert app.state.services.db.fetch_all("SELECT * FROM " + table) == []


def test_track_projection_cannot_publish_future_stems_or_keys(client, mapped_content, monkeypatch):
    raw = mapped_content.track_metadata()
    raw[1]["stem"] = "CATALOG_STEM_SENTINEL"
    raw[1]["correct_option_ids"] = ["CATALOG_KEY_SENTINEL"]
    raw[1]["domains"][0]["alignments"] = [{"options": ["CATALOG_OPTION_SENTINEL"]}]
    raw[1]["domains"][0]["rationale"] = "CATALOG_RATIONALE_SENTINEL"
    raw[1]["exam_simulation_available"] = True
    monkeypatch.setattr(mapped_content, "track_metadata", lambda: raw)
    catalog = client.get(BASE + "/catalog").json()
    assert "SENTINEL" not in json.dumps(catalog)
    assert_no_content(catalog)
    assert all(t["exam_simulation_available"] is False for t in catalog["tracks"])


def test_mapping_metadata_cannot_override_review_and_source_key_checks(client, mapped_content):
    for id, version in mapped_content.mapped_pins:
        mapped_content.versions[(id, version)]["review"]["source_key_checked"] = False
    catalog = client.get(BASE + "/catalog", params={"track": "esen_eph"}).json()
    assert catalog["available_questions"] == catalog["available_families"] == 0
    assert launch(client, "unchecked-mapped-questions").status_code == 409


@pytest.mark.parametrize("track", ["esen_eph", "general_nephrology", "unknown-programme"])
def test_unavailable_or_unknown_tracks_cannot_launch_even_with_permissive_summaries(
        client, mapped_content, monkeypatch, track):
    rows = mapped_content.track_metadata()
    for row in rows:
        if row["id"] == track:
            row["available"] = False
            row["reason"] = "Synthetic explicit unavailable state"
    original = mapped_content.list_question_summaries
    monkeypatch.setattr(mapped_content, "track_metadata", lambda: rows)
    monkeypatch.setattr(mapped_content, "list_question_summaries", lambda **kwargs: original())
    catalog = client.get(BASE + "/catalog", params={"track": track}).json()
    assert catalog["available_families"] == catalog["available_questions"] == 0
    response = launch(client, "unavailable-selected-track", track=track)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "insufficient_coverage"


def test_mapped_selection_uses_distinct_families_and_preserves_score_pins(client, mapped_content, app):
    response = launch(client, "mapped-distinct-families")
    assert response.status_code == 200, response.text
    session = response.json()
    assert session["selector"]["track"] == "esen_eph"
    assert session["coverage"]["track_title"] == "ESENeph preparation"
    assert session["coverage"]["note"] == COVERAGE_NOTE
    assert session["coverage"]["insufficient_count"] is True
    assert session["coverage"]["complete_exam_available"] is False
    assert session["item_count"] == 2
    items = app.state.services.db.fetch_all("SELECT * FROM assessment_items")
    assert {(i["question_id"], int(i["question_version"])) for i in items} <= mapped_content.mapped_pins
    assert len({i["family_id"] for i in items}) == 2
    assert {i["topic_id"] for i in items} == {"dialysis", "transplant"}
    assert all(i["question_version"] == i["key_version"] == i["family_version"] == "1" for i in items)
    replay = launch(client, "mapped-distinct-families").json()
    assert replay == session
    assert len(app.state.services.db.fetch_all("SELECT * FROM assessment_sessions")) == 1


def test_topic_and_domain_filters_never_guess_programme_alignment(client, mapped_content, app):
    catalog = app.state.services.registry["assessment"].catalog(
        Selector(track="esen_eph", topic_ids=["transplant"]))
    assert catalog["available_families"] == 1
    assert launch(client, "mapped-topic-gap", topic_ids=["glomerular"]).status_code == 409
    assert launch(client, "no-domain-inference", domain_ids=["synthetic-haemodialysis"]).status_code == 409
    session = launch(client, "mapped-topic-selection", topic_ids=["transplant"]).json()
    assert session["item_count"] == 1
    assert session["current_item"]["topic_id"] == "transplant"


def test_correction_does_not_map_new_versions_or_rewrite_historical_scores(client, mapped_content):
    session = launch(client, "mapped-before-correction", count=1, topic_ids=["dialysis"]).json()
    item = session["current_item"]
    assert item["question_id"] == "synthetic-dialysis"
    answer = {"idempotency_key": "mapped-pinned-answer", "item_id": item["id"], "option_ids": ["a"]}
    path = BASE + "/sessions/" + session["id"]
    assert client.post(path + "/answer", json=answer).json()["feedback"]["correct"] is True
    mapped_content.correct(item["question_id"])
    catalog = client.get(BASE + "/catalog", params={"track": "esen_eph"}).json()
    assert catalog["available_questions"] == 2
    retained = client.get(path + "/review").json()["feedback"][0]
    assert retained["item"]["question_version"] == retained["item"]["key_version"] == "1"
    assert retained["correct_option_ids"] == ["a"] and retained["correct"] is True
    assert retained["content_status"]["status"] == "corrected"
    next_session = launch(client, "mapped-after-correction", count=1, topic_ids=["dialysis"]).json()
    assert next_session["current_item"]["question_id"] == "synthetic-dialysis-variant"
    assert next_session["current_item"]["repeat"] is True
    assert client.post(path + "/answer", json=answer).json()["feedback"]["correct"] is True
    assert client.get(BASE + "/aggregates").json()["reviewed"]["fresh"]["correct"] == 1


def test_withdrawal_makes_mapped_track_unavailable_without_losing_retained_results(client, mapped_content):
    session = launch(client, "mapped-before-withdrawal", count=1).json()
    path = BASE + "/sessions/" + session["id"]
    response = client.post(path + "/answer", json={"idempotency_key": "mapped-withdrawn-answer",
                           "item_id": session["current_item"]["id"], "option_ids": ["a"]})
    assert response.json()["feedback"]["correct"] is True
    for id, version in mapped_content.mapped_pins:
        mapped_content.withdraw(id, version)
    catalog = client.get(BASE + "/catalog", params={"track": "esen_eph"}).json()
    assert catalog["available_families"] == 0
    assert catalog["tracks"][1]["available"] is False
    assert catalog["tracks"][1]["domains"][0]["family_shortfall"] == 4
    assert launch(client, "mapped-after-withdrawal").status_code == 409
    retained = client.get(path + "/review").json()["feedback"][0]
    assert retained["correct"] is True and retained["correct_option_ids"] == ["a"]
    assert retained["content_status"]["status"] == "withdrawn"
