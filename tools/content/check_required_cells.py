# SPDX-License-Identifier: MIT
"""Reconcile the adopted breadth targets with immutable content evidence.

This is an authoring receipt, not a clinician review or an app release gate.
No network, provider, private profile, model, OCR or external corpus is used.
"""

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runtime"))

from renulus.content.programmes import programme_metadata
from renulus.content.validation import PackValidationError, validate_pack
from revision_checks import validate_revision, validate_review_evidence

BASELINE = ROOT / "content/packs/renulus-foundations/1.1.0"
RELEASE = BASELINE.parent / "1.1.1"
MANIFEST = ROOT / "content/required-cells/renulus-foundations-1.1.1.json"
BASELINE_HASH = "3f0b712fad056a8857fb9fc913432914cad599096c28aa96fd35e7515076c670"


def pins(items):
    return [{"id": i["id"], "version": i["version"]} for i in sorted(items, key=lambda i: i["id"])]


def required_cells(pack, baseline, review):
    if baseline.sha256 != BASELINE_HASH:
        raise PackValidationError("Adopted 1.1.0 breadth baseline changed")
    if pack.manifest["version"] != baseline.manifest["version"]:
        validate_revision(pack, baseline)
    b = pack.bundle
    baseline_objectives = sorted(o["id"] for t in baseline.bundle["topics"] for o in t["objectives"])
    objectives = sorted(o["id"] for t in b["topics"] for o in t["objectives"])
    questions = [q for q in b["questions"] if q["usage"] == "assessment_reserved"]
    cases = b["cases"]
    sources = {s["id"]: s for s in b["sources"]}
    skills = {(i["id"], i["version"]): i["skill"] for i in review["items"]
              if i["kind"] == "question"}
    mapped = programme_metadata(b["manifest"], b["topics"], cases, questions)[1]
    held = {p["id"] for p in mapped.get("excluded_questions", [])
            if p["category"] == "objective_mismatch"}
    rows = []
    for topic in b["topics"]:
        topic_objectives = {o["id"] for o in topic["objectives"]}
        qs = [q for q in questions if q["topic_id"] == topic["id"]]
        additions = [q for q in qs if (q["id"], q["version"]) in skills]
        skill_counts = Counter(skills[(q["id"], q["version"])] for q in additions)
        # Secondary tags alone do not establish teaching/evidence coverage.
        cs = [c for c in cases if topic_objectives.intersection(c["objective_ids"])]
        tag_only = [c for c in cases if topic["id"] in [c["topic_id"], *c["secondary_topic_ids"]]]
        relevant = [q for q in qs if q["id"] not in held] + cs
        linked = {o for i in relevant for o in i["objective_ids"]} & topic_objectives
        source_ids = sorted({s["source_id"] for i in relevant for s in i["sources"]} |
                            {s["source_id"] for c in cs for stage in c["stages"] for s in stage["sources"]})
        dated = [id for id in source_ids if sources[id]["currency"] == "dated_final_baseline"]
        rows.append({
            "topic_id": topic["id"], "objective_ids": sorted(topic_objectives),
            "questions": {"status": "met_minimum" if qs else "missing", "pins": pins(qs)},
            "original_expansion": {
                "status": "met_minimum" if len(additions) >= 4 and len(skill_counts) >= 2 else "missing",
                "required_questions": 4, "required_skill_types": 2,
                "question_pins": pins(additions), "skill_counts": dict(sorted(skill_counts.items()))},
            "cases": {"status": "met_minimum" if cs else "missing", "pins": pins(cs),
                      "tag_only_case_ids": sorted(c["id"] for c in tag_only if c not in cs)},
            "explanations_evidence": {"status": "linked" if cs and source_ids else "missing",
                "meaning": "Cited teaching stages with an explicit topic objective; not a complete topic explanation.",
                "source_ids": source_ids},
            "update_sources": {"status": "needs_currency_review", "source_ids": source_ids,
                "dated_baseline_ids": dated,
                "meaning": "Pinned source candidates and dated checks. Latest finals, corrections and removals require separate evidence; no fresh check is inferred from pack publication."},
            "linked_objective_ids": sorted(linked),
            "unlinked_objective_ids": sorted(topic_objectives - linked),
        })
    objective_rows = []
    for objective_id in objectives:
        qs = [q for q in questions if q["id"] not in held and objective_id in q["objective_ids"]]
        cs = [c for c in cases if objective_id in c["objective_ids"]]
        objective_rows.append({
            "objective_id": objective_id, "question_pins": pins(qs), "case_pins": pins(cs),
            "teaching_evidence_status": "linked" if cs else "missing_case_link",
        })
    met = (len(questions) >= baseline.bundle["coverage"]["minimum_questions"]
           and all(r["questions"]["status"] == r["cases"]["status"] ==
                   r["original_expansion"]["status"] == "met_minimum"
                   and not r["unlinked_objective_ids"] for r in rows))
    return {
        "schema_version": 1, "checked_on": pack.manifest["published_on"],
        "scope": "Adopted original-bank breadth and remaining partial-curriculum cells",
        "pack": {"id": pack.manifest["id"], "version": pack.manifest["version"], "sha256": pack.sha256},
        "targets": {"baseline_version": "1.1.0", "baseline_sha256": BASELINE_HASH,
            "target_topic_ids": baseline.bundle["coverage"]["target_topics"],
            "objective_ids": baseline_objectives,
            "minimum_assessment_questions": baseline.bundle["coverage"]["minimum_questions"],
            "minimum_expansion_questions_per_topic": 4, "minimum_expansion_skill_types_per_topic": 2,
            "provenance": ["content/packs/renulus-foundations/1.1.0/coverage.json",
                "content/reviews/renulus-foundations-1.1.0.json", "tools/content/author_expansion.py",
                "docs/planning/IMPLEMENTATION_PLAN.md#s3--real-assessment-and-content-production",
                "docs/planning/IMPLEMENTATION_PLAN.md#s6--a-complete-installable-product"],
            "limit": "These are the existing measurable breadth minima. The 200-question indicative blueprint is reference evidence, not a newly imposed full-exam target. No absent launch depth target is invented."},
        "counts": {"topics": len(b["topics"]), "objectives": sum(len(t["objectives"]) for t in b["topics"]),
            "assessment_questions": len(questions), "cases": len(cases)},
        "adopted_bank_minima_met": met, "complete_content_coverage": False,
        "review_limit": "Assistant source/key review only; human review is not claimed or imposed as an additional acceptance prerequisite. Link counts do not establish complete depth or educational efficacy.",
        "topic_cells": rows,
        "objective_cells": objective_rows,
        "objective_cells_without_case_links": [r["objective_id"] for r in objective_rows if not r["case_pins"]],
        "objective_cell_limit": "Per-objective links expose missing teaching cases without silently turning a per-topic bank minimum into a new per-objective case quota. Reserved question rationales are not teaching-mode explanations.",
        "objective_link_holds": [p for p in mapped.get("excluded_questions", []) if p["category"] == "objective_mismatch"],
        "sources": [sources[id] for id in sorted({id for r in rows for id in r["update_sources"]["source_ids"]})],
        "programme": {"id": mapped["id"], "version": mapped.get("version"),
            "status": mapped["status"], "evidence": mapped.get("evidence", []),
            "available_questions": mapped.get("available_questions", 0),
            "format_compatible_questions": mapped.get("format_compatible_questions", 0),
            "exam_simulation_available": False, "official_endorsement": False,
            "domains": [{**{k: d[k] for k in ("id", "indicative_questions", "available_questions",
                        "available_families", "family_shortfall", "status")},
                        "available_cases": len({(p["id"], p["version"]) for r in d["alignments"] for p in r["cases"]})}
                        for d in mapped.get("domains", [])],
            "remaining_cells": [{"id": r["id"], "domain_id": r["domain_id"], "status": r["status"],
                "question_count": len(r["questions"]), "case_count": len(r["cases"]),
                "gaps": r["gaps"]} for d in mapped.get("domains", []) for r in d["alignments"]]},
    }


def build_manifest(release=RELEASE, review_evidence=None):
    baseline, pack = validate_pack(BASELINE), validate_pack(release)
    review_path = ROOT / "content/reviews/renulus-foundations-1.1.0.json"
    predecessors = [validate_pack(BASELINE.parent / version) for version in ("1.0.0", "1.0.1")]
    validate_review_evidence(baseline, review_path, predecessors)
    review = json.loads(review_path.read_text(encoding="utf-8"))
    # Breadth is the adopted 1.1.0 expansion, not every later reviewed question.
    # Only explicitly reviewed successor versions of those same IDs replace pins.
    selected = {q["id"]: q for q in pack.bundle["questions"]}
    revised = [row for row in review["items"] if row["kind"] == "question"
               and row["id"] in selected and row["version"] != selected[row["id"]]["version"]]
    if revised and review_evidence is None:
        raise PackValidationError("Revised original-expansion pins require --review-evidence")
    if review_evidence is not None:
        ancestors = [validate_pack(BASELINE.parent / v) for v in
                     ("1.0.0", "1.0.1", "1.1.0", "1.1.1", "1.1.2")
                     if tuple(map(int, v.split("."))) < tuple(map(int, pack.manifest["version"].split(".")))]
        validate_review_evidence(pack, review_evidence, ancestors)
        successors = {(row["id"], row["version"]): row for row in
                      json.loads(Path(review_evidence).read_text(encoding="utf-8"))["items"]}
        for row in revised:
            key = (row["id"], selected[row["id"]]["version"])
            if key not in successors:
                raise PackValidationError(f"Revised expansion pin lacks review: {key}")
            row.update(successors[key])
    return required_cells(pack, baseline, review)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, default=RELEASE, help="Selected immutable release; defaults to the historical 1.1.1 receipt")
    parser.add_argument("--output", type=Path, default=MANIFEST)
    parser.add_argument("--review-evidence", type=Path,
                        help="Reviewed successor pins, needed when original expansion items advance versions")
    parser.add_argument("--check", action="store_true", help="Compare the committed receipt without writing")
    args = parser.parse_args(argv)
    try:
        report = build_manifest(args.release, args.review_evidence)
        raw = (json.dumps(report, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        if args.check:
            if args.output.read_bytes() != raw:
                raise PackValidationError("Required-cell manifest differs from its pinned evidence")
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes(raw)
    except (OSError, ValueError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}))
        return 2
    print(json.dumps({"valid": True, "pack": report["pack"], "counts": report["counts"],
        "adopted_bank_minima_met": report["adopted_bank_minima_met"],
        "complete_content_coverage": False,
        "objective_cells_without_case_links": report["objective_cells_without_case_links"],
        "topic_update_source_cells_needing_review": len(report["topic_cells"]),
        "programme_cells_without_pinned_items": [r["id"] for r in report["programme"]["remaining_cells"] if r["status"] == "gap"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
