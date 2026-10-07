# SPDX-License-Identifier: MIT
"""Preserved targets and honest content cells; no provider or helper workload."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import shutil
import sys

import pytest

from renulus.content.validation import PackValidationError, validate_pack
from .helpers import read, refresh, write

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "tools/content"))
import check_required_cells as cells
from revision_checks import validate_revision


def test_required_manifest_reproduces_existing_targets_and_exposes_limits(tmp_path):
    manifest = cells.build_manifest()
    assert manifest == json.loads(cells.MANIFEST.read_text(encoding="utf-8"))
    assert manifest["counts"] == {"topics": 27, "objectives": 56, "assessment_questions": 160, "cases": 26}
    assert manifest["targets"]["minimum_assessment_questions"] == 150
    assert len(manifest["targets"]["target_topic_ids"]) == 27
    assert len(manifest["targets"]["objective_ids"]) == 56
    assert manifest["adopted_bank_minima_met"] is True
    assert manifest["complete_content_coverage"] is False
    assert len(manifest["objective_cells"]) == 56
    assert all(r["question_pins"] for r in manifest["objective_cells"])
    assert sum(bool(r["case_pins"]) for r in manifest["objective_cells"]) == 50
    assert manifest["objective_cells_without_case_links"] == [
        "T01.O02", "T08.O03", "T08.O04", "T09.O02", "T11.O02", "T25.O01"]
    assert all(r["update_sources"]["status"] == "needs_currency_review" for r in manifest["topic_cells"])
    assert all(r["explanations_evidence"]["status"] == "linked" for r in manifest["topic_cells"])
    assert len(manifest["objective_link_holds"]) == 4
    assert manifest["programme"]["available_questions"] == 152
    assert manifest["programme"]["format_compatible_questions"] == 0
    assert manifest["programme"]["exam_simulation_available"] is False
    assert all(d["status"] == "partial" for d in manifest["programme"]["domains"])
    assert next(d for d in manifest["programme"]["domains"] if d["id"] == "hemodialysis")["available_cases"] == 0
    gaps = {r["id"] for r in manifest["programme"]["remaining_cells"] if r["status"] == "gap"}
    assert {"pd_infection_gap", "sexual_health_gap", "transition_gap", "transplant_aftercare_gap"} <= gaps
    output = tmp_path / "synthetic-required-cells.json"
    assert cells.main(["--output", str(output)]) == 0
    assert output.read_bytes() == cells.MANIFEST.read_bytes()
    assert cells.main(["--output", str(output), "--check"]) == 0
    changed = read(tmp_path, output.name)
    changed["complete_content_coverage"] = True
    write(tmp_path, output.name, changed)
    assert cells.main(["--output", str(output), "--check"]) == 2


@pytest.mark.parametrize("reduction,match", [("topic", "target topic"), ("questions", "question target")])
def test_valid_pack_cannot_lower_predecessor_targets(tmp_path, reduction, match):
    path = tmp_path / "synthetic-lowered-target"
    shutil.copytree(cells.RELEASE, path)
    coverage = read(path, "coverage.json")
    if reduction == "topic":
        coverage["target_topics"].remove("T01")
    else:
        coverage["minimum_questions"] = 40
    write(path, "coverage.json", coverage)
    refresh(path)
    # This is a valid standalone snapshot: only the adoption history detects
    # lowering the target while all questions and historical IDs still exist.
    candidate = validate_pack(path)
    with pytest.raises(PackValidationError, match=match):
        validate_revision(candidate, validate_pack(cells.BASELINE))


def test_new_topic_version_cannot_remove_an_adopted_objective():
    prior, pack = validate_pack(cells.BASELINE), validate_pack(cells.RELEASE)
    bundle = deepcopy(pack.bundle)
    bundle["topics"][0]["objectives"].pop()
    with pytest.raises(PackValidationError, match="loses an adopted objective"):
        validate_revision(replace(pack, bundle=bundle), prior)


def test_secondary_case_tags_cannot_close_a_missing_required_case_cell():
    baseline, pack = validate_pack(cells.BASELINE), validate_pack(cells.RELEASE)
    bundle = deepcopy(pack.bundle)
    for case in bundle["cases"]:
        if any(o.startswith("T01.") for o in case["objective_ids"]):
            case["version"] += 1
            case["objective_ids"] = [o for o in case["objective_ids"] if not o.startswith("T01.")]
    review = json.loads((ROOT / "content/reviews/renulus-foundations-1.1.0.json").read_text(encoding="utf-8"))
    report = cells.required_cells(replace(pack, bundle=bundle), baseline, review)
    topic = next(r for r in report["topic_cells"] if r["topic_id"] == "T01")
    assert topic["cases"]["pins"] == []
    assert topic["cases"]["tag_only_case_ids"]
    assert topic["cases"]["status"] == topic["explanations_evidence"]["status"] == "missing"
    assert report["adopted_bank_minima_met"] is False
    assert report["counts"]["cases"] == 26


def test_bank_minimum_is_not_mistaken_for_current_source_evidence():
    manifest = cells.build_manifest()
    assert manifest["adopted_bank_minima_met"]
    for topic in manifest["topic_cells"]:
        assert topic["update_sources"]["source_ids"]
        assert topic["update_sources"]["status"] != "met_minimum"
    serialized = json.dumps(manifest)
    for key in ("stem", "options", "answer", "rationale", "teaching_points"):
        assert f'"{key}":' not in serialized
