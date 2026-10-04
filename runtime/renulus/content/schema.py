# SPDX-License-Identifier: MIT
"""JSON Schema 2020-12 contract, validated by the maintained jsonschema library."""

TEXT = {"type": "string", "minLength": 1}
IDENT = {"type": "string", "pattern": r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$"}
DATE = {"type": "string", "format": "date"}
VERSION = {"type": "integer", "minimum": 1}


def array(items, minimum=0):
    return {"type": "array", "items": items, "minItems": minimum}


def obj(properties, optional=()):
    return {"type": "object", "properties": properties,
            "required": [k for k in properties if k not in optional],
            "additionalProperties": False}


REVIEW = obj({
    "status": {"enum": ["assistant_reviewed", "human_reviewed", "draft"]},
    "reviewer": TEXT, "reviewer_kind": {"enum": ["assistant", "human"]},
    "reviewed_on": DATE, "method": TEXT,
    "source_key_checked": {"type": "boolean"},
    "independent_human_review": {"type": "boolean"},
})
CITATION = obj({"source_id": IDENT, "locator": TEXT})
COMMON = {
    "id": IDENT, "version": VERSION, "topic_id": IDENT,
    "secondary_topic_ids": array(IDENT),
    "objective_ids": array(IDENT, 1),
    "license": {"const": "CC-BY-4.0"},
    "original": {"const": True},
    "sources": array(CITATION, 1), "review": REVIEW,
}
QUESTION = obj({
    **COMMON, "family_id": IDENT, "family_version": VERSION, "key_version": VERSION,
    "kind": {"const": "single_best_answer"},
    "usage": {"enum": ["assessment_reserved", "practice", "evaluation_reserved"]},
    "stem": TEXT,
    "options": array(obj({"id": IDENT, "text": TEXT, "rationale": TEXT}), 4),
    "answer": IDENT, "rationale": TEXT,
    "difficulty": {"enum": ["foundation", "application", "integration"]},
    "correction": obj({"previous_version": VERSION, "reason": TEXT}),
}, optional=("correction",))
CASE = obj({
    **COMMON, "synthetic": {"const": True}, "usage": {"const": "teaching"},
    "title": TEXT, "summary": TEXT,
    "stages": array(obj({"id": IDENT, "narrative": TEXT,
                         "prompts": array(TEXT, 1),
                         "teaching_points": array(TEXT, 1),
                         "sources": array(CITATION, 1)}), 2),
    "take_home": array(TEXT, 1),
})
TOPIC = obj({
    "id": IDENT, "version": VERSION, "label": TEXT, "description": TEXT,
    "objectives": array(obj({"id": IDENT, "text": TEXT}), 2),
    "mapping": obj({"general_nephrology": {"const": True},
                     "esen_eph": {"const": "not_formally_mapped"}}),
    "license": {"const": "CC-BY-4.0"},
})
SOURCE = obj({
    "id": IDENT, "register_id": {"type": "string", "pattern": r"^[KGERCL][0-9]{2}$"},
    "title": TEXT, "edition": TEXT,
    "publication_status": {"const": "final"},
    "url": {"type": "string", "format": "uri", "pattern": "^https://"},
    "canonical_topic_url": {"type": "string", "format": "uri", "pattern": "^https://"},
    "checked_on": DATE,
    "check_status": {"enum": ["locator_checked", "check_failed"]},
    "currency": {"enum": ["catalogue_final_checked", "dated_final_baseline"]},
    "scope": TEXT, "rights_note": TEXT, "check_note": TEXT,
})
WITHDRAWAL = obj({
    "question_id": IDENT, "version": VERSION, "reason": TEXT,
    "replacement_version": VERSION,
}, optional=("replacement_version",))
MANIFEST = obj({
    "schema_version": {"const": 1}, "repository_contract": {"const": 1},
    "id": IDENT, "version": {"type": "string", "pattern": r"^[0-9]+\.[0-9]+\.[0-9]+$"},
    "state": {"const": "published"}, "published_on": DATE,
    "title": TEXT, "license": {"const": "CC-BY-4.0"},
    "authors": array(TEXT, 1), "attribution": TEXT,
    "source_register": {"const": "docs/SOURCES.md"},
    "files": obj({name: obj({"path": TEXT, "sha256": {"type": "string",
                  "pattern": "^[a-f0-9]{64}$"}})
                  for name in ("topics", "sources", "cases", "questions", "coverage")}),
    "claims": obj({"complete_curriculum": {"const": False},
                   "complete_esen_eph_blueprint": {"const": False},
                   "independent_human_review": {"type": "boolean"}}),
    "withdrawals": array(WITHDRAWAL),
})
COVERAGE_ROW = obj({
    "topic_id": IDENT, "objective_ids": array(IDENT),
    "case_ids": array(IDENT), "question_ids": array(IDENT),
    "covered_objective_ids": array(IDENT), "gap_objective_ids": array(IDENT),
    "review_counts": obj({"assistant_reviewed": {"type": "integer", "minimum": 0},
                          "human_reviewed": {"type": "integer", "minimum": 0}}),
})
COVERAGE = obj({
    "taxonomy_version": {"const": 1}, "target_topics": array(IDENT, 6),
    "minimum_questions": {"type": "integer", "minimum": 1},
    "topics": array(COVERAGE_ROW, 1),
})
BUNDLE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    **obj({"manifest": MANIFEST, "topics": array(TOPIC, 1),
           "sources": array(SOURCE, 1), "cases": array(CASE, 1),
           "questions": array(QUESTION, 1), "coverage": COVERAGE}),
}
