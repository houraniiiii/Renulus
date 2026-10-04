# SPDX-License-Identifier: MIT
"""Authoring checks layered on the maintained runtime pack validator.

These checks verify evidence consistency and immutable ancestry. They do not
replace the assistant's medical reading or the canonical transactional loader.
"""
import json
from pathlib import Path

from renulus.content.validation import PackValidationError, canonical_json


def _pinned_sources(bundle, item):
    identities = {c["source_id"] for c in item.get("sources", [])}
    for stage in item.get("stages", []):
        identities.update(c["source_id"] for c in stage["sources"])
    return [s for s in bundle["sources"] if s["id"] in identities]


def validate_revision(pack, predecessor):
    if pack.manifest["id"] != predecessor.manifest["id"]:
        raise PackValidationError("Revision must retain pack identity")
    version = lambda v: tuple(int(n) for n in v.split("."))
    if version(pack.manifest["version"]) <= version(predecessor.manifest["version"]):
        raise PackValidationError("Revision must advance pack version")
    withdrawals = {(w["question_id"], w["version"]): w for w in pack.manifest["withdrawals"]}
    for kind in ("topics", "cases", "questions"):
        selected = {i["id"]: i for i in pack.bundle[kind]}
        for old in predecessor.bundle[kind]:
            item = selected.get(old["id"])
            if item is None:
                if kind == "questions" and (old["id"], old["version"]) in withdrawals:
                    continue
                raise PackValidationError(f"Additive revision loses an unwithdrawn {kind} record: {old['id']}")
            if item["version"] < old["version"]:
                raise PackValidationError(f"Revision selects an older item: {old['id']}")
            if item["version"] == old["version"]:
                if canonical_json(item) != canonical_json(old):
                    raise PackValidationError(f"Immutable published record changed: {old['id']}")
                if kind != "topics" and canonical_json(_pinned_sources(pack.bundle, item)) != canonical_json(
                        _pinned_sources(predecessor.bundle, old)):
                    raise PackValidationError(f"Immutable source snapshot changed: {old['id']}")
            if kind == "questions":
                if item["family_id"] != old["family_id"]:
                    raise PackValidationError(f"Published family changed: {old['id']}")
                if item["answer"] != old["answer"] or item["options"] != old["options"]:
                    correction = item.get("correction", {})
                    withdrawal = withdrawals.get((old["id"], old["version"]), {})
                    if (correction.get("previous_version") != old["version"]
                            or withdrawal.get("replacement_version") != item["version"]):
                        raise PackValidationError(f"Changed key/choices require predecessor correction and withdrawal: {old['id']}")
    return {"version": predecessor.manifest["version"], "sha256": predecessor.sha256}


def validate_review_evidence(pack, path, predecessors=()):
    try:
        evidence = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PackValidationError(f"Cannot read review evidence: {exc}") from exc
    if (evidence.get("schema_version") != 1
            or evidence.get("pack_id") != pack.manifest["id"]
            or evidence.get("pack_version") != pack.manifest["version"]
            or evidence.get("independent_human_review") is not False):
        raise PackValidationError("Review evidence identity/method mismatch")
    if not evidence.get("method") or not evidence.get("access_limits"):
        raise PackValidationError("Review evidence must state method and access limits")
    selected = {(i["id"], i["version"]): i for kind in ("questions", "cases") for i in pack.bundle[kind]}
    inherited = set()
    for prior in predecessors:
        for kind in ("questions", "cases"):
            for item in prior.bundle[kind]:
                key = (item["id"], item["version"])
                if key in selected and canonical_json(item) == canonical_json(selected[key]):
                    inherited.add(key)
    rows = evidence.get("items", [])
    identities = [(e.get("id"), e.get("version")) for e in rows]
    if len(identities) != len(set(identities)):
        raise PackValidationError("Duplicate review evidence identity")
    if set(selected) - inherited - set(identities):
        raise PackValidationError("New published items lack source/key review evidence")
    source_rows = evidence.get("sources", [])
    source_ids = [s.get("id") for s in source_rows]
    if len(source_ids) != len(set(source_ids)):
        raise PackValidationError("Duplicate source review evidence identity")
    sources = {s["id"]: s for s in pack.bundle["sources"]}
    inherited_sources = {s["id"] for prior in predecessors for s in prior.bundle["sources"]}
    if set(sources) - inherited_sources - set(source_ids):
        raise PackValidationError("New published sources lack review evidence")
    for row in source_rows:
        source = sources.get(row.get("id"))
        if source is None or any(row.get(field) != source[field]
                                 for field in ("register_id", "url", "edition", "check_note")):
            raise PackValidationError("Source review evidence does not match the pinned source metadata")
    for key, e in zip(identities, rows):
        item = selected.get(key)
        if item is None:
            raise PackValidationError(f"Review evidence references an unselected item: {key}")
        if (e.get("source_locators") != item["sources"]
                or e.get("reviewer_kind") != "assistant"
                or e.get("independent_human_review") is not False
                or e.get("reviewed_on") != item["review"]["reviewed_on"]
                or not e.get("checked_claim")):
            raise PackValidationError(f"Review evidence source/method mismatch: {key}")
        if "answer" in item:
            answer = next(o["text"] for o in item["options"] if o["id"] == item["answer"])
            if e.get("key_text") != answer or e.get("kind") != "question":
                raise PackValidationError(f"Review evidence key mismatch: {key}")
        elif e.get("kind") != "case" or e.get("key_text") is not None:
            raise PackValidationError(f"Case evidence must not invent a deterministic key: {key}")
    return len(rows)
