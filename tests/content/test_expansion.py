# SPDX-License-Identifier: MIT
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from renulus.content.repository import ContentConflict, ContentRepository
from renulus.content.validation import PackValidationError, validate_pack
from .helpers import PACK, read, refresh, write

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "tools/content"))
import author_expansion as expansion
from revision_checks import validate_review_evidence, validate_revision


@pytest.fixture
def increment(tmp_path):
    path = tmp_path / "renulus-foundations/1.0.1"
    expansion.publish(path)
    return path


def evidence_file(tmp_path, value=None):
    path = tmp_path / "review.json"
    body = value if value is not None else expansion.review_evidence(version="1.0.1", per_topic=2, extra_cases=6)
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def answer_text(question):
    return next(o["text"] for o in question["options"] if o["id"] == question["answer"])


def test_increment_has_real_breadth_and_source_key_evidence(increment, tmp_path):
    pack = validate_pack(increment)
    prior = validate_pack(PACK)
    assert len(pack.bundle["questions"]) == 106
    assert len(pack.bundle["cases"]) == 20
    assert len(pack.bundle["topics"]) == 27
    new = [q for q in pack.bundle["questions"] if q["id"].startswith("RN11-")]
    assert Counter(q["topic_id"] for q in new) == {t["id"]: 2 for t in pack.bundle["topics"]}
    assert len(set(q["stem"] for q in new)) == 54
    assert {q["usage"] for q in new} == {"assessment_reserved"}
    assert all(q["sources"] and q["review"]["source_key_checked"] for q in new)
    assert all(not t["gap_objective_ids"] for t in pack.bundle["coverage"]["topics"])
    assert validate_revision(pack, prior)["version"] == "1.0.0"
    assert validate_review_evidence(pack, evidence_file(tmp_path), [prior]) == 60


def test_original_authoring_and_released_bytes_remain_identical(tmp_path):
    output = tmp_path / "original"
    # Importing/using expansion authoring must not mutate the original pools.
    expansion.base.publish(output)
    assert validate_pack(output).sha256 == "8b63d8bd02402a03d68f84c21159700e1cc5806b72ffad6f0fca2baa28f0485e"
    for original in PACK.iterdir():
        assert (output / original.name).read_bytes() == original.read_bytes()
    assert hashlib.sha256((PACK / "manifest.json").read_bytes()).hexdigest() == "f2430000aa3f13b4e76fb0a379513469f70f0efc18a832bd131affa4f63e3154"


def test_numeric_and_mechanism_keys_do_not_drift(increment):
    rows = {q["id"]: q for q in validate_pack(increment).bundle["questions"]}
    assert answer_text(rows["RN11-T01-002"]) == "About 31 mL/min."
    assert round(45 * 1.20 / 1.73, 1) == 31.2
    assert answer_text(rows["RN11-T06-001"]) == "Stage 2."
    assert 140 - 112 - 18 == 10
    assert "Normal-anion-gap" in answer_text(rows["RN11-T04-002"])
    assert round(1 / (0.04 - 0.03)) == 100
    assert answer_text(rows["RN11-T26-001"]) == "1 percentage point; NNT 100 over two years."
    assert "osmotic gradient" in answer_text(rows["RN11-T20-002"])
    assert "does not reliably exclude AIN" in answer_text(rows["RN11-T11-002"])
    assert "Table 31" in rows["RN11-T01-001"]["sources"][0]["locator"]
    assert "2.2.4-2.2.5" in rows["RN11-T08-002"]["sources"][0]["locator"]


def test_real_activation_keeps_old_private_snapshot_and_family(database, increment):
    repository = ContentRepository(database, PACK.parent.parent)
    repository.install_pack(PACK)
    old = repository.get_question_version("RN-CKD-002", 1)
    repository.install_pack(increment)
    assert repository.active_manifest()["version"] == "1.0.1"
    assert len(repository.list_question_summaries()) == 106
    assert repository.get_question_version("RN-CKD-002", 1) == old
    assert repository.install_pack(increment)["installed"] is False
    restarted = ContentRepository(database, PACK.parent.parent)
    assert restarted.get_question_version("RN11-T13-001", 1)["family_id"] == "RN11-T13-001.family"
    teaching = json.dumps(restarted.teaching_material())
    assert all(q["id"] not in teaching for q in restarted.list_question_summaries())
    assert "correct_option_ids" not in teaching


def test_pinned_source_change_cannot_sneak_through_rehashed_pack(database, increment):
    sources = read(increment, "sources.json")
    next(s for s in sources if s["id"] == "K01-2024")["title"] = "SYNTHETIC_CHANGED_SOURCE_TITLE"
    write(increment, "sources.json", sources)
    refresh(increment)
    candidate = validate_pack(increment)
    with pytest.raises(PackValidationError, match="source snapshot"):
        validate_revision(candidate, validate_pack(PACK))
    repository = ContentRepository(database, PACK.parent.parent)
    repository.install_pack(PACK)
    with pytest.raises(ContentConflict, match="Immutable version"):
        repository.install_pack(increment)
    assert repository.active_manifest()["version"] == "1.0.0"
    assert database.fetch_one("SELECT COUNT(*) n FROM content_question_versions")["n"] == 52


@pytest.mark.parametrize("kind", ["missing", "wrong_key", "wrong_locator", "invented_review", "missing_source", "wrong_source"])
def test_review_evidence_rejects_missing_or_false_claims(increment, tmp_path, kind):
    body = deepcopy(expansion.review_evidence(version="1.0.1", per_topic=2, extra_cases=6))
    if kind == "missing":
        body["items"].pop(0)
    elif kind == "wrong_key":
        body["items"][0]["key_text"] = "SYNTHETIC_WRONG_KEY"
    elif kind == "wrong_locator":
        body["items"][0]["source_locators"][0]["locator"] = "SYNTHETIC_UNCHECKED_LOCATOR"
    elif kind == "invented_review":
        body["items"][0]["independent_human_review"] = True
    elif kind == "missing_source":
        body["sources"].pop(0)
    else:
        body["sources"][0]["edition"] = "SYNTHETIC_UNVERIFIED_EDITION"
    with pytest.raises(PackValidationError, match="evidence"):
        validate_review_evidence(validate_pack(increment), evidence_file(tmp_path, body), [validate_pack(PACK)])


def test_revision_cli_uses_real_register_and_review_evidence(increment, tmp_path):
    command = [sys.executable, "-B", str(ROOT / "tools/content/validate_pack.py"), str(increment),
               "--predecessor", str(PACK), "--review-evidence", str(evidence_file(tmp_path))]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    report = json.loads(result.stdout)
    assert report["valid"] and report["review_evidence_rows"] == 60
    assert report["predecessors_checked"][0]["version"] == "1.0.0"
    assert report["topics_without_items"] == report["uncovered_objectives"] == []


def test_publisher_refuses_an_altered_released_increment(increment):
    path = increment / "questions.json"
    old = path.read_bytes()
    path.write_bytes(old + b" ")
    with pytest.raises(SystemExit, match="Refusing to alter published snapshot"):
        expansion.publish(increment)
    assert path.read_bytes() == old + b" "
