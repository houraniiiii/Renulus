# SPDX-License-Identifier: MIT
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from renulus.content.repository import ContentConflict, ContentRepository
from renulus.content.validation import PackValidationError, validate_pack
from .helpers import PACK, read, refresh, write

ROOT = Path(__file__).parents[2]
INCREMENT = PACK.parent / "1.0.1"
FINAL = PACK.parent / "1.1.0"
sys.path.insert(0, str(ROOT / "tools/content"))
import author_expansion as expansion
from revision_checks import validate_review_evidence, validate_revision


@pytest.fixture
def final_pack(tmp_path):
    path = tmp_path / "renulus-foundations/1.1.0"
    expansion.publish(path, version="1.1.0", per_topic=4, extra_cases=12)
    return path


def evidence_file(tmp_path):
    path = tmp_path / "review-110.json"
    path.write_text(json.dumps(expansion.review_evidence(
        version="1.1.0", per_topic=4, extra_cases=12)), encoding="utf-8")
    return path


def key_text(item):
    return next(o["text"] for o in item["options"] if o["id"] == item["answer"])


def test_final_has_broad_real_items_and_mixed_cases(final_pack, tmp_path):
    pack = validate_pack(final_pack)
    assert len(pack.bundle["questions"]) == 160
    assert len(pack.bundle["cases"]) == 26
    added = [q for q in pack.bundle["questions"] if q["id"].startswith("RN11-")]
    assert Counter(q["topic_id"] for q in added) == {t["id"]: 4 for t in pack.bundle["topics"]}
    assert len({q["stem"] for q in pack.bundle["questions"]}) == 160
    assert sorted(Counter(q["answer"] for q in pack.bundle["questions"]).values()) == [40] * 4
    assert all(q["usage"] == "assessment_reserved" for q in pack.bundle["questions"])
    assert all(not t["gap_objective_ids"] for t in pack.bundle["coverage"]["topics"])
    for case in pack.bundle["cases"][-6:]:
        assert case["synthetic"] and case["usage"] == "teaching"
        assert len(case["secondary_topic_ids"]) >= 3
        assert len(case["stages"]) == 3
        assert all(s["sources"] and len(s["teaching_points"]) >= 2 for s in case["stages"])
    priors = [validate_pack(PACK), validate_pack(INCREMENT)]
    assert [validate_revision(pack, p)["version"] for p in priors] == ["1.0.0", "1.0.1"]
    assert validate_review_evidence(pack, evidence_file(tmp_path), priors) == 120


def test_released_increment_bytes_and_evidence_survive_final_authoring(tmp_path):
    target = tmp_path / "reproduced-101"
    expansion.publish(target)
    assert validate_pack(target).sha256 == "515c3cef9c6387727d45c0098fe8d319be88d6162f81026ce68aeff9be4ac3e9"
    for file in INCREMENT.iterdir():
        assert (target / file.name).read_bytes() == file.read_bytes()
    expected = expansion.review_evidence(version="1.0.1", per_topic=2, extra_cases=6)
    raw = (json.dumps(expected, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    assert raw == (ROOT / "content/reviews/renulus-foundations-1.0.1.json").read_bytes()
    assert hashlib.sha256((INCREMENT / "manifest.json").read_bytes()).hexdigest() == "65bea4d4585ff856e63688e9418cac1745d03125deda301a978561370c5b3fd4"


def test_published_final_bytes_and_review_are_reproducible(final_pack):
    published = validate_pack(FINAL)
    assert published.sha256 == "3f0b712fad056a8857fb9fc913432914cad599096c28aa96fd35e7515076c670"
    assert hashlib.sha256((FINAL / "manifest.json").read_bytes()).hexdigest() == "85641e86ed3e3b5430737a45ad606e7e768357a2807dd542303b9b8e758a1fbe"
    for file in FINAL.iterdir():
        assert (final_pack / file.name).read_bytes() == file.read_bytes()
    evidence = ROOT / "content/reviews/renulus-foundations-1.1.0.json"
    expected = expansion.review_evidence(version="1.1.0", per_topic=4, extra_cases=12)
    assert evidence.read_bytes() == (json.dumps(expected, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    assert validate_review_evidence(published, evidence, [validate_pack(PACK), validate_pack(INCREMENT)]) == 120


def test_new_calculations_and_checked_key_locators(final_pack):
    items = {q["id"]: q for q in validate_pack(final_pack).bundle["questions"]}
    assert 140 - 104 - 12 == 24
    assert "24 mmol/L" in key_text(items["RN11-T04-004"])
    assert 80 * 25 == 2000
    assert key_text(items["RN11-T07-003"]) == "2,000 mL/h."
    assert round((60 - 44) / 60 * 100, 1) == 26.7
    assert "exceeds 20%" in key_text(items["RN11-T08-003"])
    assert (20 - 6) / 20 * 100 == 70
    assert key_text(items["RN11-T20-003"]) == "70%."
    assert key_text(items["RN11-T15-004"]) == "Immune-mediated TTP."
    assert "10.7.2.1" in items["RN11-T17-003"]["sources"][0]["locator"]
    assert "4.1.4.2-4.1.4.4" in items["RN11-T12-003"]["sources"][0]["locator"]
    assert "Figure 30 caption" in items["RN11-T10-003"]["sources"][0]["locator"]
    rta = items["RN11-T11-004"]
    assert "p1588" in rta["sources"][0]["locator"]
    assert "urease" not in json.dumps(rta).lower()
    assert "spot pH alone is insufficient" in key_text(rta)
    case = next(c for c in validate_pack(final_pack).bundle["cases"] if c["id"] == "RN11-CASE-CRRT-DELIVERY")
    assert round(25 * 16 / 24, 1) == 16.7
    assert "16.7" in case["stages"][0]["teaching_points"][0]


def test_real_lineage_activation_preserves_all_prior_private_snapshots(database, final_pack):
    repository = ContentRepository(database, PACK.parent.parent)
    repository.install_pack(PACK)
    original = {q["id"]: repository.get_question_version(q["id"], q["version"])
                for q in repository.list_question_summaries()}
    repository.install_pack(INCREMENT)
    before = {q["id"]: repository.get_question_version(q["id"], q["version"])
              for q in repository.list_question_summaries()}
    repository.install_pack(final_pack)
    restarted = ContentRepository(database, PACK.parent.parent)
    assert restarted.active_manifest()["version"] == "1.1.0"
    assert len(restarted.list_question_summaries()) == 160
    assert database.fetch_one("SELECT COUNT(*) n FROM content_packs")["n"] == 3
    assert database.fetch_one("SELECT COUNT(*) n FROM content_question_versions")["n"] == 160
    for identity, pinned in before.items():
        assert restarted.get_question_version(identity, 1) == pinned
    for identity, pinned in original.items():
        assert restarted.get_question_version(identity, 1) == pinned
    assert repository.install_pack(final_pack)["installed"] is False
    teaching = json.dumps(restarted.teaching_material())
    assert all(q["id"] not in teaching for q in restarted.list_question_summaries())
    assert "correct_option_ids" not in teaching
    references = restarted.references_for_source("K15")
    assert {"RN11-T21-003", "RN11-CASE-DONOR-GOALS"} <= {r["id"] for r in references}
    assert all(not ({"stem", "answer", "options", "rationale"} & r.keys()) for r in references)


def test_changed_increment_source_is_rejected_and_activation_rolls_back(database, final_pack):
    sources = read(final_pack, "sources.json")
    next(s for s in sources if s["id"] == expansion.CKD)["edition"] = "SYNTHETIC_CHANGED_EDITION"
    write(final_pack, "sources.json", sources)
    refresh(final_pack)
    with pytest.raises(PackValidationError, match="source snapshot"):
        validate_revision(validate_pack(final_pack), validate_pack(INCREMENT))
    repository = ContentRepository(database, PACK.parent.parent)
    repository.install_pack(INCREMENT)
    with pytest.raises(ContentConflict, match="Immutable version"):
        repository.install_pack(final_pack)
    assert repository.active_manifest()["version"] == "1.0.1"
    assert database.fetch_one("SELECT COUNT(*) n FROM content_question_versions")["n"] == 106


def test_changed_choices_require_new_correction_and_matching_withdrawal(final_pack):
    questions = read(final_pack, "questions.json")
    item = questions[0]
    item["version"] = item["key_version"] = 2
    item["options"][0]["rationale"] += " Synthetic wording check; intended medical key unchanged."
    write(final_pack, "questions.json", questions)
    refresh(final_pack)
    with pytest.raises(PackValidationError, match="correction and withdrawal"):
        validate_revision(validate_pack(final_pack), validate_pack(INCREMENT))
    item["correction"] = {"previous_version": 1, "reason": "Synthetic wording check"}
    manifest = read(final_pack, "manifest.json")
    manifest["withdrawals"] = [{"question_id": item["id"], "version": 1,
                                "reason": "Synthetic wording check", "replacement_version": 2}]
    write(final_pack, "questions.json", questions)
    write(final_pack, "manifest.json", manifest)
    refresh(final_pack)
    assert validate_revision(validate_pack(final_pack), validate_pack(INCREMENT))["version"] == "1.0.1"


def test_additive_revision_can_withdraw_an_item_without_deleting_its_history(database, final_pack, tmp_path):
    repository = ContentRepository(database, PACK.parent.parent)
    repository.install_pack(final_pack)
    path = tmp_path / "synthetic-withdrawal-pack"
    shutil.copytree(final_pack, path)
    questions = read(path, "questions.json")
    removed = questions.pop(0)
    pinned = repository.get_question_version(removed["id"], 1)
    manifest = read(path, "manifest.json")
    manifest["version"] = "1.1.1"
    write(path, "questions.json", questions)
    write(path, "manifest.json", manifest)
    refresh(path)
    with pytest.raises(PackValidationError, match="loses an unwithdrawn"):
        validate_revision(validate_pack(path), validate_pack(final_pack))
    manifest = read(path, "manifest.json")
    manifest["withdrawals"] = [{"question_id": removed["id"], "version": 1,
                                "reason": "Synthetic review withdrawal"}]
    write(path, "manifest.json", manifest)
    refresh(path)
    validate_revision(validate_pack(path), validate_pack(final_pack))
    repository.install_pack(path)
    assert len(repository.list_question_summaries()) == 159
    historic = repository.get_question_version(removed["id"], 1)
    assert historic["withdrawn"] and historic["answer"] == pinned["answer"]
    assert historic["source_records"] == pinned["source_records"]


def test_withdrawn_final_pack_cannot_be_reactivated_after_restart(database, final_pack):
    repository = ContentRepository(database, PACK.parent.parent)
    repository.install_pack(final_pack)
    pinned = repository.get_question_version("RN11-T20-003", 1)
    repository.withdraw_pack("renulus-foundations", "1.1.0", "Synthetic pack review hold")
    restarted = ContentRepository(database, PACK.parent.parent)
    assert restarted.active_manifest() is None
    assert restarted.list_question_summaries() == []
    assert restarted.get_question_version("RN11-T20-003", 1)["answer"] == pinned["answer"]
    with pytest.raises(ContentConflict, match="[Ww]ithdrawn"):
        restarted.install_pack(final_pack)


def test_final_cli_validates_both_released_predecessors(final_pack, tmp_path):
    result = subprocess.run([
        sys.executable, "-B", str(ROOT / "tools/content/validate_pack.py"), str(final_pack),
        "--predecessor", str(PACK), "--predecessor", str(INCREMENT),
        "--review-evidence", str(evidence_file(tmp_path)),
    ], capture_output=True, text=True, check=True)
    report = json.loads(result.stdout)
    assert report["valid"] and report["questions"] == 160 and report["cases"] == 26
    assert report["review_evidence_rows"] == 120
    assert [p["version"] for p in report["predecessors_checked"]] == ["1.0.0", "1.0.1"]


def test_machine_skill_coverage_matches_reviewed_rows_and_all_topics(final_pack, tmp_path):
    evidence = evidence_file(tmp_path)
    body = json.loads(evidence.read_text(encoding="utf-8"))
    summary = body["question_skill_coverage"]
    assert summary["scope"] == "question_review_rows"
    assert sum(summary["counts"].values()) == 108
    assert summary["counts"] == {"mechanism": 36, "interpretation": 34, "common_reasoning": 38}
    assert len(summary["by_topic"]) == 27
    assert all(sum(skills.values()) == 4 and len(skills) >= 2 for skills in summary["by_topic"].values())
    body["question_skill_coverage"]["counts"]["mechanism"] += 1
    evidence.write_text(json.dumps(body), encoding="utf-8")
    with pytest.raises(PackValidationError, match="skill coverage"):
        validate_review_evidence(validate_pack(final_pack), evidence, [validate_pack(PACK), validate_pack(INCREMENT)])
