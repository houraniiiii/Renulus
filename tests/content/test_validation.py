# SPDX-License-Identifier: MIT
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from renulus.content.validation import PackValidationError, validate_pack
from .helpers import PACK, copy_pack, read, refresh, write


def test_real_pack_source_schema_keys_and_breadth():
    pack = validate_pack(PACK, known_register_ids={"K01", "K02", "K03", "K05", "K06",
                         "K08", "K09", "K10", "K11", "K13", "K16", "G01", "G02"})
    assert len(pack.bundle["topics"]) == 27
    assert sum(len(t["objectives"]) for t in pack.bundle["topics"]) == 56
    assert len(pack.bundle["questions"]) == 52
    assert len(pack.bundle["cases"]) == 14
    assert {q["review"]["status"] for q in pack.bundle["questions"]} == {"assistant_reviewed"}
    assert not pack.manifest["claims"]["independent_human_review"]
    gaps = {t["topic_id"] for t in pack.bundle["coverage"]["topics"] if not t["case_ids"] and not t["question_ids"]}
    assert gaps == {"T11", "T13", "T15", "T18", "T23"}
    assert all(c["synthetic"] for c in pack.bundle["cases"])


def test_clinical_key_regressions_checked_against_primary_locators():
    questions = {q["id"]: q for q in validate_pack(PACK).bundle["questions"]}
    # Concrete facts from K01 Tables 1-3, K10 Table 2, K16 1.4 and K02 3.3.1.
    expected = {
        "RN-CKD-002": "G3b A3",
        "RN-AKI-002": "Stage 2",
        "RN-TX-002": "Preemptive living-donor transplantation when feasible.",
        "RN-ANEMIA-002": "Individualize the target while keeping hemoglobin below 11.5 g/dL.",
    }
    for id, answer in expected.items():
        q = questions[id]
        assert next(o["text"] for o in q["options"] if o["id"] == q["answer"]) == answer
    assert "2.5" in questions["RN-AKI-002"]["rationale"]
    assert "32 micromol/L" in questions["RN-AKI-001"]["rationale"]
    assert "4.1.4.2" in questions["RN-PKD-002"]["sources"][0]["locator"]


def test_rejects_changed_file_even_if_json_is_parseable(tmp_path):
    path = copy_pack(tmp_path)
    with (path / "questions.json").open("a", encoding="utf-8") as file:
        file.write(" ")
    with pytest.raises(PackValidationError, match="Checksum"):
        validate_pack(path)


@pytest.mark.parametrize("mutation,match", [
    (lambda q: q.update(answer="not-a-choice"), "Key is not a choice"),
    (lambda q: q["options"].__setitem__(1, dict(q["options"][0])), "Schema|Duplicate"),
    (lambda q: q.update(objective_ids=["unregistered.objective"]), "objective"),
    (lambda q: q["sources"][0].update(source_id="not-a-source"), "Unknown source"),
    (lambda q: q["review"].update(status="draft"), "Unreviewed"),
    (lambda q: q["review"].update(independent_human_review=True), "human review"),
    (lambda q: q.update(key_version=2), "Key must pin"),
    (lambda q: q.update(correction={"previous_version": 1, "reason": "No advance"}), "advance"),
])
def test_rejects_invalid_source_review_key_and_version(tmp_path, mutation, match):
    path = copy_pack(tmp_path)
    questions = read(path, "questions.json")
    mutation(questions[0])
    write(path, "questions.json", questions)
    refresh(path)
    with pytest.raises(PackValidationError, match=match):
        validate_pack(path)


def test_rejects_fabricated_coverage(tmp_path):
    path = copy_pack(tmp_path)
    coverage = read(path, "coverage.json")
    coverage["topics"][0]["covered_objective_ids"] = coverage["topics"][0]["objective_ids"]
    coverage["topics"][0]["gap_objective_ids"] = []
    write(path, "coverage.json", coverage)
    refresh(path, coverage=False)
    with pytest.raises(PackValidationError, match="Coverage"):
        validate_pack(path)


@pytest.mark.parametrize("filename", ["../questions.json", "C:/private.json", "C:\\private.json", "/absolute.json"])
def test_rejects_paths_outside_pack_before_read(tmp_path, filename):
    path = copy_pack(tmp_path)
    manifest = read(path, "manifest.json")
    manifest["files"]["questions"]["path"] = filename
    write(path, "manifest.json", manifest)
    with pytest.raises(PackValidationError, match="Unsafe"):
        validate_pack(path)


def test_rejects_unknown_register_and_failed_source_check(tmp_path):
    with pytest.raises(PackValidationError, match="Unknown SOURCES"):
        validate_pack(PACK, known_register_ids={"R01"})
    path = copy_pack(tmp_path)
    sources = read(path, "sources.json")
    sources[0]["check_status"] = "check_failed"
    write(path, "sources.json", sources)
    refresh(path)
    with pytest.raises(PackValidationError, match="Unverified source"):
        validate_pack(path)


def test_rejects_duplicate_json_keys(tmp_path):
    path = copy_pack(tmp_path)
    manifest = read(path, "manifest.json")
    raw = (path / "questions.json").read_text(encoding="utf-8").replace('"answer": "A"', '"answer": "A", "answer": "B"', 1)
    (path / "questions.json").write_text(raw, encoding="utf-8")
    manifest["files"]["questions"]["sha256"] = hashlib.sha256(raw.encode()).hexdigest()
    write(path, "manifest.json", manifest)
    with pytest.raises(PackValidationError, match="Duplicate JSON key"):
        validate_pack(path)


def test_cli_real_source_register_and_nonzero_invalid_exit(tmp_path):
    root = Path(__file__).parents[2]
    command = [sys.executable, "-B", str(root / "tools/content/validate_pack.py")]
    result = subprocess.run([*command, str(PACK)], capture_output=True, text=True, check=True)
    assert json.loads(result.stdout)["valid"] is True
    path = copy_pack(tmp_path)
    (path / "manifest.json").write_text("{}", encoding="utf-8")
    result = subprocess.run([*command, str(path)], capture_output=True, text=True)
    assert result.returncode == 2
    assert json.loads(result.stdout)["valid"] is False
