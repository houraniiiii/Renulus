# SPDX-License-Identifier: MIT
"""Validate schema, files, declared review, keys, source IDs, versions and coverage.

This deterministic CLI verifies authoring invariants, not medical correctness.
No model, network request, credentials or raw source documents are used.
"""
import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runtime"))
from renulus.content.schema import BUNDLE_SCHEMA
from renulus.content.validation import PackValidationError, validate_pack
from revision_checks import validate_review_evidence, validate_revision


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pack", nargs="?", type=Path)
    parser.add_argument("--source-register", type=Path, default=ROOT / "docs/SOURCES.md")
    parser.add_argument("--predecessor", type=Path, action="append", default=[],
                        help="Check additive immutable ancestry against a released pack (repeatable)")
    parser.add_argument("--review-evidence", type=Path,
                        help="Check source/key evidence identity and coverage for newly authored items")
    parser.add_argument("--schema", action="store_true", help="Print the JSON Schema 2020-12 bundle contract")
    args = parser.parse_args(argv)
    if args.schema:
        print(json.dumps(BUNDLE_SCHEMA, indent=2))
        return 0
    if not args.pack:
        parser.error("Select a pack directory or --schema")
    try:
        text = args.source_register.read_text(encoding="utf-8")
        register_ids = re.findall(r"^\| ([A-Z][0-9]{2}) [–—-]", text, re.MULTILINE)
        if not register_ids:
            raise PackValidationError("No source IDs found in the selected SOURCES register")
        pack = validate_pack(args.pack, known_register_ids=register_ids)
        predecessors = [validate_pack(path, known_register_ids=register_ids) for path in args.predecessor]
        ancestry = [validate_revision(pack, prior) for prior in predecessors]
        review_rows = (validate_review_evidence(pack, args.review_evidence, predecessors)
                       if args.review_evidence else None)
    except (PackValidationError, OSError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}))
        return 2
    b = pack.bundle
    print(json.dumps({
        "valid": True, "id": pack.manifest["id"], "version": pack.manifest["version"],
        "sha256": pack.sha256, "topics": len(b["topics"]),
        "objectives": sum(len(t["objectives"]) for t in b["topics"]),
        "cases": len(b["cases"]), "questions": len(b["questions"]),
        "review_states": sorted({i["review"]["status"] for i in (*b["cases"], *b["questions"])}),
        "source_register_ids": sorted({s["register_id"] for s in b["sources"]}),
        "predecessors_checked": ancestry, "review_evidence_rows": review_rows,
        "topics_without_items": [t["topic_id"] for t in b["coverage"]["topics"]
                                 if not t["case_ids"] and not t["question_ids"]],
        "uncovered_objectives": [o for t in b["coverage"]["topics"] for o in t["gap_objective_ids"]],
        "clinical_review_limit": "Declared assistant source/key review; no independent human review or complete ESENeph mapping.",
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
