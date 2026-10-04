from copy import deepcopy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from renulus.server import create_app


class SyntheticContentRepository:
    """M8 contract adapter with original local fixtures, never a prod bank."""
    def __init__(self):
        pack = json.loads((Path(__file__).parent / "fixtures/tiny-pack.json").read_text())
        self.topics = pack["topics"]
        self.versions = {}
        self.active = {}
        for raw in pack["questions"]:
            question = {**raw, "version": 1, "key_version": 1, "family_version": 1,
                "kind": "single_best_answer", "usage": "assessment_reserved",
                "objective_ids": [raw["topic_id"] + "-objective"],
                "options": [{"id": option, "text": "Token " + option,
                             "rationale": "PRIVATE_OPTION_RATIONALE_" + option}
                            for option in ("a", "b", "c", "d")],
                "answer": "a", "correct_option_ids": ["a"],
                "explanation": "PRIVATE_REVIEWED_KEY_SENTINEL",
                "hint": "An original synthetic hint",
                "sources": [{"source_id": "synthetic-original", "locator": "Fixture section 1"}],
                "difficulty": "foundation",
                "review": {"status": "assistant_reviewed", "source_key_checked": True},
                "withdrawn": False, "withdrawal": None}
            self.versions[(question["id"], 1)] = question
            self.active[question["id"]] = 1

    def list_topics(self):
        return deepcopy(self.topics)

    def list_question_summaries(self, topic_id=None, domain=None, track=None):
        if track not in (None, "general_nephrology"):
            return []
        fields = ("id", "version", "family_id", "family_version", "key_version",
                  "topic_id", "objective_ids", "difficulty", "usage", "review")
        result = []
        for id, version in self.active.items():
            question = self.versions[(id, version)]
            if not question["withdrawn"] and question["usage"] == "assessment_reserved":
                if (topic_id or domain) in (None, question["topic_id"]):
                    result.append({field: deepcopy(question[field]) for field in fields})
        return result

    def get_question_version(self, id, version):
        question = deepcopy(self.versions[(id, version)])
        question["current_version"] = self.active.get(id)
        return question

    def correct(self, id):
        original = self.versions[(id, 1)]
        corrected = {**deepcopy(original), "version": 2, "key_version": 2, "family_version": 2,
                     "answer": "b", "correct_option_ids": ["b"],
                     "explanation": "CORRECTED_KEY_SENTINEL"}
        self.versions[(id, 2)] = corrected
        self.active[id] = 2

    def withdraw(self, id, version=1):
        self.versions[(id, version)]["withdrawn"] = True
        self.versions[(id, version)]["withdrawal"] = {"reason": "Synthetic correction",
                                                      "replacement_version": None}
        if self.active.get(id) == version:
            del self.active[id]


@pytest.fixture
def content():
    return SyntheticContentRepository()


@pytest.fixture
def app(tmp_path, content):
    app = create_app(tmp_path / "profile")
    app.state.services.registry["content"] = content
    return app


@pytest.fixture
def client(app):
    with TestClient(app) as client:
        yield client
