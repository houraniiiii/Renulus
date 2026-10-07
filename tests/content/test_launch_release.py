# SPDX-License-Identifier: MIT
"""Release bytes and real canonical activation, without providers or helpers."""
import json
from pathlib import Path
import sys

from renulus.content.repository import ContentRepository
from renulus.content.validation import validate_pack

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "tools/content"))
import author_launch_gaps as author
import check_required_cells as cells


def test_launch_release_reproduces_and_closes_actual_drafted_links(tmp_path):
    destination = tmp_path / "reproduced"
    mapping, review = tmp_path / "mapping.json", tmp_path / "review.json"
    author.publish(destination, mapping, review)
    for path in author.RELEASE.iterdir():
        assert path.read_bytes() == (destination / path.name).read_bytes()
    assert mapping.read_bytes() == author.MAPPING_PATH.read_bytes()
    assert review.read_bytes() == author.REVIEW_PATH.read_bytes()
    report = cells.build_manifest(author.RELEASE)
    receipt = ROOT / "content/required-cells/renulus-foundations-1.1.2.json"
    assert report == json.loads(receipt.read_text(encoding="utf-8"))
    assert report["counts"] == {"topics": 27, "objectives": 56, "assessment_questions": 178, "cases": 38}
    assert report["adopted_bank_minima_met"] is True
    assert report["objective_cells_without_case_links"] == []
    assert report["programme"]["available_questions"] == 170
    assert report["complete_content_coverage"] is False
    assert report["programme"]["exam_simulation_available"] is False
    rows = {r["id"]: r for r in report["programme"]["remaining_cells"]}
    for identity in author.FACETS:
        assert rows[identity]["status"] == "partial"
        assert rows[identity]["question_count"] >= 2
        assert rows[identity]["case_count"] >= 1
        assert rows[identity]["gaps"]
    assert all(row["status"] == "partial" for row in rows.values())
    assert all(row["gaps"] for row in rows.values())


def test_citation_update_keeps_keys_sources_and_families_after_restart(database):
    repository = ContentRepository(database, author.RELEASE.parent.parent)
    repository.install_pack(author.PRIOR)
    old = {identity: repository.get_question_version(identity, 1)
           for identity in author.HYPER_QUESTIONS}
    case_sql = "SELECT body_json FROM content_case_versions WHERE case_id=? AND version=1"
    old_case = database.fetch_one(case_sql, (author.HYPER_CASE,))["body_json"]
    repository.install_pack(author.RELEASE)
    restarted = ContentRepository(database, author.RELEASE.parent.parent)
    for identity, historical in old.items():
        assert restarted.get_question_version(identity, 1) == {**historical, "current_version": 2}
        selected = restarted.get_question_version(identity, 2)
        for field in ("stem", "options", "answer", "family_id", "objective_ids"):
            assert selected[field] == historical[field]
        assert {s["source_id"] for s in selected["sources"]} == {author.HYPER_SOURCE}
    assert database.fetch_one(case_sql, (author.HYPER_CASE,))["body_json"] == old_case
    assert restarted.get_case(author.HYPER_CASE)["version"] == 2
    assert all("G02-hyperkalemia-2023" != s["source_id"]
               for s in restarted.get_case(author.HYPER_CASE)["sources"])
    prior, release = validate_pack(author.PRIOR), validate_pack(author.RELEASE)
    assert release.bundle["sources"][:len(prior.bundle["sources"])] == prior.bundle["sources"]
