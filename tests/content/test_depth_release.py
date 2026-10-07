# SPDX-License-Identifier: MIT
"""Narrow offline checks for the 1.2.0 authoring contract; no app/engine work."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

from renulus.content.validation import PackValidationError, validate_pack

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "tools/content"))
import author_depth as depth
import check_required_cells as cells
from revision_checks import validate_review_evidence


@pytest.fixture(scope="module")
def candidate(tmp_path_factory):
    # Run with an external --basetemp, as documented in the authoring command.
    folder = tmp_path_factory.mktemp("depth")
    result = depth.publish(folder / "evidence", folder / "pack", folder / "mapping.json")
    pack = validate_pack(folder / "pack")
    evidence = json.loads(Path(result["review_path"]).read_text(encoding="utf-8"))
    return folder, result, pack, evidence


def test_release_preserves_history_and_repairs_only_reviewed_objectives(candidate):
    _, _, pack, _ = candidate
    prior = validate_pack(depth.PRIOR)
    old_questions = {q["id"]: q for q in prior.bundle["questions"]}
    questions = {q["id"]: q for q in pack.bundle["questions"]}
    permitted = {"version", "key_version", "objective_ids", "review", "sources"}
    for identity, old in old_questions.items():
        current = questions[identity]
        if identity in depth.CORRECTIONS:
            assert {k for k in old if old[k] != current[k]} <= permitted
            assert current["version"] == old["version"] + 1
            assert current["objective_ids"] == [depth.CORRECTIONS[identity][0]]
        else:
            assert current == old
    assert pack.bundle["cases"][:38] == prior.bundle["cases"]
    assert pack.bundle["sources"][:47] == prior.bundle["sources"]
    assert len(pack.bundle["sources"]) == 64
    mapping = pack.manifest["programme_mappings"][0]
    assert len(mapping["excluded_questions"]) == 4
    assert all(p["category"] != "objective_mismatch" for p in mapping["excluded_questions"])
    assert mapping["checked_on"] == prior.manifest["programme_mappings"][0]["checked_on"]
    assert mapping["evidence"] == prior.manifest["programme_mappings"][0]["evidence"]


def test_finite_depth_has_pinned_cases_without_claiming_complete_domains(candidate):
    _, _, pack, evidence = candidate
    report = depth.validate_depth_evidence(pack, evidence)
    assert report["cells"] == 11 and report["questions"] == 44
    assert len([c for c in pack.bundle["cases"] if c["id"].startswith("RN13-")]) == 12
    assert len({q["family_id"] for q in pack.bundle["questions"]}) == 222
    assert all(q["usage"] == "assessment_reserved" for q in pack.bundle["questions"])
    assert all(c["usage"] == "teaching" and c["synthetic"] for c in pack.bundle["cases"])
    assert evidence["launch_depth"]["complete_domain_coverage"] is False
    assert evidence["source_currency_holds"]["all_topic_update_cells_remain_open"] is True
    citrate = next(c for c in pack.bundle["cases"] if c["id"] == "RN13-CASE-CITRATE")
    assert citrate["objective_ids"] == ["T23.O03"]
    assert len(citrate["stages"]) == 3


def test_selected_versions_count_original_breadth_without_counting_new_depth(candidate):
    folder, result, _, _ = candidate
    with pytest.raises(PackValidationError, match="require --review-evidence"):
        cells.build_manifest(folder / "pack")
    report = cells.build_manifest(folder / "pack", result["review_path"])
    assert report["counts"] == dict(topics=27, objectives=57, assessment_questions=222, cases=50)
    assert report["adopted_bank_minima_met"] is True
    assert report["objective_link_holds"] == []
    assert report["objective_cells_without_case_links"] == []
    assert len(report["targets"]["objective_ids"]) == 56  # original adopted IDs stay fixed
    assert len(report["objective_cells"]) == 57  # added objective is actually evaluated
    for row in report["topic_cells"]:
        pins = row["original_expansion"]["question_pins"]
        assert len(pins) == 4
        assert all(pin["id"].startswith("RN11-") for pin in pins)
        assert row["update_sources"]["status"] == "needs_currency_review"
    assert report["programme"]["available_questions"] == 218
    assert report["programme"]["format_compatible_questions"] == 44
    assert len(report["programme"]["domains"]) == 11
    assert all(d["status"] == "partial" for d in report["programme"]["domains"])
    assert report["programme"]["exam_simulation_available"] is False


@pytest.mark.parametrize("mutation", ["missing_stage", "wrong_stage_locator", "unsupported_objective"])
def test_depth_receipt_rejects_unsupported_case_claims(candidate, mutation):
    _, _, pack, original = candidate
    evidence = deepcopy(original)
    case_review = next(r for r in evidence["items"] if r["id"] == "RN13-CASE-CITRATE")
    claim = case_review["objective_support"][0]
    if mutation == "missing_stage":
        claim["stage_ids"] = ["stage-99"]
    elif mutation == "wrong_stage_locator":
        claim["source_locators"][0]["locator"] = "A different clinical claim"
    else:
        claim["objective_id"] = "T23.O02"
    with pytest.raises(PackValidationError, match="Depth objective"):
        depth.validate_depth_evidence(pack, evidence)


def test_remapped_question_cannot_reuse_its_unreviewed_old_pin(candidate, tmp_path):
    _, _, pack, original = candidate
    evidence = deepcopy(original)
    evidence["items"] = [r for r in evidence["items"] if r["id"] != "RN11-T23-004"]
    receipt = tmp_path / "missing-revision.json"
    receipt.write_text(json.dumps(evidence), encoding="utf-8")
    with pytest.raises(PackValidationError, match="lack source/key review"):
        validate_review_evidence(pack, receipt, [validate_pack(depth.PRIOR)])


def test_immutable_conflict_preflight_does_not_publish_partial_pack(tmp_path):
    mapping = tmp_path / "mapping.json"
    mapping.write_text("An existing different immutable mapping", encoding="utf-8")
    with pytest.raises(ValueError, match="Refusing to overwrite immutable"):
        depth.publish(tmp_path / "evidence", tmp_path / "pack", mapping)
    assert not (tmp_path / "pack").exists()
    assert not (tmp_path / "evidence/renulus-foundations-1.2.0-review.json").exists()
    assert mapping.read_text(encoding="utf-8") == "An existing different immutable mapping"
