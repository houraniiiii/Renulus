# SPDX-License-Identifier: MIT
"""Validate the pack snapshot before any database transaction or retrieval."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator, FormatChecker

from .schema import BUNDLE_SCHEMA

MAX_FILE_BYTES = 8 * 1024 * 1024


class PackValidationError(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise PackValidationError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_json(path: Path):
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            raise PackValidationError(f"Pack file exceeds {MAX_FILE_BYTES} bytes: {path.name}")
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs,
                           parse_constant=lambda token: (_ for _ in ()).throw(
                               PackValidationError(f"Invalid JSON constant: {token}")))
        return value, hashlib.sha256(raw).hexdigest()
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PackValidationError(f"Cannot read {path.name}: {exc}") from exc


def _by_id(rows, kind):
    result = {}
    for row in rows:
        if row["id"] in result:
            raise PackValidationError(f"Duplicate {kind} identity: {row['id']}")
        result[row["id"]] = row
    return result


def coverage_for(topics, cases, questions, target_topics, minimum_questions):
    rows = []
    for topic in topics:
        items = [i for i in (*cases, *questions)
                 if topic["id"] in [i["topic_id"], *i["secondary_topic_ids"]]]
        objectives = sorted(o["id"] for o in topic["objectives"])
        covered = sorted({o for i in items for o in i["objective_ids"] if o in objectives})
        counts = Counter(i["review"]["status"] for i in items)
        rows.append({
            "topic_id": topic["id"], "objective_ids": objectives,
            "case_ids": sorted(i["id"] for i in items if i in cases),
            "question_ids": sorted(i["id"] for i in items if i in questions),
            "covered_objective_ids": covered,
            "gap_objective_ids": sorted(set(objectives) - set(covered)),
            "review_counts": {s: counts[s] for s in ("assistant_reviewed", "human_reviewed")},
        })
    return {"taxonomy_version": 1, "target_topics": sorted(target_topics),
            "minimum_questions": minimum_questions, "topics": rows}


@dataclass(frozen=True)
class ValidatedPack:
    bundle: dict
    sha256: str

    @property
    def manifest(self):
        return self.bundle["manifest"]


def validate_pack(path: str | Path, *, known_register_ids: Iterable[str] | None = None) -> ValidatedPack:
    root = Path(path).resolve()
    manifest, _ = _read_json(root / "manifest.json")
    # Validate the manifest first: do not follow attacker-controlled file paths.
    manifest_schema = BUNDLE_SCHEMA["properties"]["manifest"]
    validator = Draft202012Validator(manifest_schema, format_checker=FormatChecker())
    errors = list(validator.iter_errors(manifest))
    if errors:
        raise PackValidationError(f"Manifest schema: {errors[0].message}")
    bundle = {"manifest": manifest}
    paths = set()
    for name, entry in manifest["files"].items():
        filename = entry["path"]
        # Packs contain flat JSON snapshots. No drive paths, traversal, links or originals.
        if Path(filename).name != filename or ":" in filename or "\\" in filename or not filename.endswith(".json"):
            raise PackValidationError(f"Unsafe pack path: {filename}")
        target = root / filename
        if target.is_symlink() or target.resolve().parent != root or filename in paths:
            raise PackValidationError(f"Unsafe or duplicate pack path: {filename}")
        paths.add(filename)
        value, actual_hash = _read_json(target)
        if actual_hash != entry["sha256"]:
            raise PackValidationError(f"Checksum mismatch: {filename}")
        bundle[name] = value
    validator = Draft202012Validator(BUNDLE_SCHEMA, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(bundle), key=lambda e: str(list(e.path)))
    if errors:
        error = errors[0]
        raise PackValidationError(f"Schema at {list(error.path)}: {error.message}")
    topics = _by_id(bundle["topics"], "topic")
    sources = _by_id(bundle["sources"], "source")
    _by_id(bundle["cases"], "case")
    _by_id(bundle["questions"], "question")
    objectives = {}
    for topic in topics.values():
        for objective in topic["objectives"]:
            if objective["id"] in objectives:
                raise PackValidationError(f"Duplicate objective: {objective['id']}")
            objectives[objective["id"]] = topic["id"]
    known = set(known_register_ids) if known_register_ids is not None else None
    for source in sources.values():
        if known is not None and source["register_id"] not in known:
            raise PackValidationError(f"Unknown SOURCES register ID: {source['register_id']}")
        if source["check_status"] != "locator_checked":
            raise PackValidationError(f"Unverified source cannot support publication: {source['id']}")
        if source["checked_on"] > manifest["published_on"]:
            raise PackValidationError(f"Source check after publication: {source['id']}")
    for item in (*bundle["cases"], *bundle["questions"]):
        item_topics = [item["topic_id"], *item["secondary_topic_ids"]]
        if len(set(item_topics)) != len(item_topics) or any(t not in topics for t in item_topics):
            raise PackValidationError(f"Invalid topic links: {item['id']}")
        if any(objectives.get(o) not in item_topics for o in item["objective_ids"]):
            raise PackValidationError(f"Unknown or unrelated objective: {item['id']}")
        review = item["review"]
        if review["status"] == "draft" or not review["source_key_checked"]:
            raise PackValidationError(f"Unreviewed published item: {item['id']}")
        if (review["status"] == "assistant_reviewed") != (review["reviewer_kind"] == "assistant"):
            raise PackValidationError(f"Reviewer identity mismatch: {item['id']}")
        if review["reviewer_kind"] == "assistant" and review["independent_human_review"]:
            raise PackValidationError(f"Assistant review cannot claim human review: {item['id']}")
        if review["reviewed_on"] > manifest["published_on"]:
            raise PackValidationError(f"Review after publication: {item['id']}")
        citations = [*item["sources"]]
        if "stages" in item:
            citations.extend(s for stage in item["stages"] for s in stage["sources"])
            if len({s["id"] for s in item["stages"]}) != len(item["stages"]):
                raise PackValidationError(f"Duplicate case stage: {item['id']}")
        for citation in citations:
            if citation["source_id"] not in sources:
                raise PackValidationError(f"Unknown source locator: {item['id']}")
            if sources[citation["source_id"]]["checked_on"] > review["reviewed_on"]:
                raise PackValidationError(f"Review predates source check: {item['id']}")
        if "answer" in item:
            if item["key_version"] != item["version"]:
                raise PackValidationError(f"Key must pin the published item version: {item['id']}")
            options = _by_id(item["options"], "option")
            if item["answer"] not in options:
                raise PackValidationError(f"Key is not a choice: {item['id']}")
            normalized = [o["text"].strip().casefold() for o in options.values()]
            if len(set(normalized)) != len(normalized):
                raise PackValidationError(f"Duplicate answer choices: {item['id']}")
            if "correction" in item and item["correction"]["previous_version"] >= item["version"]:
                raise PackValidationError(f"Correction must advance version: {item['id']}")
    if manifest["claims"]["independent_human_review"] and any(
            not i["review"]["independent_human_review"] for i in (*bundle["cases"], *bundle["questions"])):
        raise PackValidationError("Pack human-review claim exceeds actual reviews")
    withdrawals = manifest["withdrawals"]
    if len({(w["question_id"], w["version"]) for w in withdrawals}) != len(withdrawals):
        raise PackValidationError("Duplicate withdrawal")
    selected = {(q["id"], q["version"]) for q in bundle["questions"]}
    if any((w["question_id"], w["version"]) in selected for w in withdrawals):
        raise PackValidationError("Withdrawn question cannot be selected in the same pack")
    coverage = bundle["coverage"]
    expected = coverage_for(bundle["topics"], bundle["cases"], bundle["questions"],
                            coverage["target_topics"], coverage["minimum_questions"])
    if coverage != expected:
        raise PackValidationError("Coverage does not match actual item/objective/review links")
    if len(bundle["questions"]) < coverage["minimum_questions"]:
        raise PackValidationError("Question coverage below declared target")
    for target in coverage["target_topics"]:
        if target not in topics or not any(q["topic_id"] == target for q in bundle["questions"]) or not any(
                target in [c["topic_id"], *c["secondary_topic_ids"]] for c in bundle["cases"]):
            raise PackValidationError(f"Required domain lacks cases/questions: {target}")
    return ValidatedPack(bundle=bundle, sha256=digest(bundle))
