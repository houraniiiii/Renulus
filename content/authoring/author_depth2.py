# SPDX-License-Identifier: MIT
"""Publish the bounded 1.4.0 additive snapshot using existing content tools only.

No networking, activation, database, test runner, provider or native application.
External review receipts remain outside Git; original source bodies are never copied.
"""
import argparse
from copy import deepcopy
from functools import partial
from hashlib import sha1, sha256
import json
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/content"))
import author_foundations as base
import author_eseneph as eseneph
import check_required_cells as required_cells
from author_depth import write_immutable
from check_required_cells import build_manifest
from revision_checks import validate_revision, validate_review_evidence
from renulus.content.validation import validate_pack

DATE = "2026-10-07"
VERSION = "1.4.0"
MAPPING_VERSION = "2026-10-07-depth2"
BASE = "120bd180d0433f2e1ea023a99ccbaa28320f8515"
PACKS = ROOT / "content/packs/renulus-foundations"
VERSIONS = ("1.0.0", "1.0.1", "1.1.0", "1.1.1", "1.1.2", "1.2.0", "1.3.0")
PROPOSALS = ROOT / "content/proposals/depth-20261007"
PINS = {
    "hd/cases": "ebaba2114bae1103bee20aa8e19fb4d5574ad3fd2b02c38498e90487d37734a4",
    "hd/questions": "a4fb244605547168a7e8de1245801c2119d0f18469ce4d4a7f4c0dbd46f28f1a",
    "hd/reviews": "ceee63436d6cac960db70486aa35c776a9b5462b0b50028e8d11c48aed1aa4aa",
    "hd/sources": "6adec6308527cd0bc8f73a2081edf272e5057e692e073962e453a8eba8b52b6e",
    "cmv/cases": "35bb733a601eddff8aaa3115aa001b7a232b6b6da4522cd6fc2a586fc8e478de",
    "cmv/questions": "a0f5adb5e4b83ebbdde5a2b57dec5036d7dd53102b32be034478b900a6c86c84",
    "cmv/reviews": "ee5395bd3514092dd5b7568a6e47804ecd54fde3d10f3ecf71e249c347a8947c",
    "cmv/sources": "fe2f733993dc17b655ad96c1c2fe22507f9c41c5d70956aad0d9562976344651",
    "antigbm/cases": "8b51560d3a3e870be5e1431ba18450ded4471a5355272c1b22e6a11ad1a16178",
    "antigbm/questions": "162cec8b0d434e0e685b0cc7efe8ed636e827c9d34a8163e0e87de0dae45672f",
    "antigbm/reviews": "d7e5cff2d90fa60d7e5da36c82de19a3c9773e85601c5885cd1d55dc79858e27",
    "antigbm/sources": "e49e925dfb31224f6db86dc84b76e5f34e47b807b0a63b579d0b0c9e422a77e7",
}
# Git's declared eol=lf normalizes the original HD lane's CRLF JSON on checkout.
# Both hashes identify the same reviewed text; no other byte change is accepted.
LF_PINS = {
    "hd/cases": "2ae032ebbbb5b97c13c1d392deab5fa1444db56b47c8b601da3d18ffe3a7ca8d",
    "hd/questions": "15bd86b04c680b9e05a8eead9d8e568ceff6819688dd9d1dc6c47f41a1a8bb4d",
    "hd/reviews": "c2c3d9e725459021188498a86e6fe40cd35d849989688cc90b4d550b63c0b0ab",
    "hd/sources": "81aebbd94e1870602e8c98a8d53769dcf6574d9c8d7f556136c2be585d7f6618",
}


def raw(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def pinned(path, digest, lf_digest=None):
    data = Path(path).read_bytes()
    if sha256(data).hexdigest() not in {digest, lf_digest}:
        raise ValueError(f"Reviewed input changed: {path}")
    return json.loads(data)


def protected_bytes():
    """Compare predecessor bytes directly with base Git blobs, before and after."""
    paths = ["content/packs", "content/mappings", "content/required-cells", "content/schema",
             "docs/implementation/finish-launch-criteria-20261007.md"]
    tree = subprocess.check_output(["git", "ls-tree", "-r", BASE, "--", *paths], cwd=ROOT, text=True)
    result = {}
    for line in tree.splitlines():
        header, name = line.split("\t", 1)
        digest = header.split()[2]
        data = (ROOT / name).read_bytes()
        actual = sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        if actual != digest:
            raise ValueError(f"Protected predecessor bytes differ from base: {name}")
        result[name] = {"git_blob": digest, "sha256": sha256(data).hexdigest()}
    return result


def at(item, path):
    parts = path.strip("/").split("/") if path.startswith("/") else re.findall(r"[^.\[\]]+", path)
    for part in parts:
        item = item[int(part)] if isinstance(item, list) else item[part]
    return item


def checked_reviews(lanes):
    """Check exact reviewed claims/options/stages, then adapt vocabulary only."""
    result = []
    for lane, data in lanes.items():
        rows = {r.get("artifact_id", r["id"]): r for r in data["reviews"]}
        for item in data["questions"] + data["cases"]:
            r = rows[item["id"]]
            question = "answer" in item
            for claim in r.get("authored_claims", []):
                assert at(item, claim["path"]) == claim["text"]
            for claim in r.get("claims", []):
                assert at(item, claim["field"]) == claim["authored_claim"]
            if question:
                options = {o["id"]: o for o in item["options"]}
                key = options[item["answer"]]
                if lane == "hd":
                    assert r["key_review"]["answer"] == item["answer"]
                    assert r["key_review"]["text"] == key["text"]
                    reviews = r["option_reviews"]
                    assert len(reviews) == len(options)
                    for v in reviews:
                        assert (v["text"], v["rationale"]) == (options[v["option_id"]]["text"], options[v["option_id"]]["rationale"])
                elif lane == "cmv":
                    assert r["key_review"]["exact_option"] == key
                    assert r["answer"] == item["answer"]
                    assert len(r["distractor_review"]) == len(options) - 1
                    for v in r["distractor_review"]:
                        assert (v["exact_text"], v["rejected_because"]) == (options[v["option_id"]]["text"], options[v["option_id"]]["rationale"])
                else:
                    assert r["key"] == item["answer"] and r["key_text"] == key["text"]
                    assert len(r["distractor_check"]) == len(options)
                    for v in r["distractor_check"]:
                        assert (v["option_text"], v["authored_rationale"]) == (options[v["option_id"]]["text"], options[v["option_id"]]["rationale"])
            elif lane in {"hd", "cmv"}:
                stage_rows = r["stage_reviews" if lane == "hd" else "stage_review"]
                assert len(stage_rows) == len(item["stages"])
                for stage, v in zip(item["stages"], stage_rows):
                    assert stage["id"] == v["stage_id"]
                    assert stage["narrative"] == v["authored_narrative" if lane == "hd" else "narrative"]
                    assert stage["prompts"] == v["prompts"]
                    claims = v["authored_claims" if lane == "hd" else "teaching_claims"]
                    assert len(claims) == len(stage["teaching_points"])
                    for claim in claims:
                        assert at(item, claim.get("path", claim.get("field"))) == claim.get("text", claim.get("authored_claim"))
                if lane == "hd":
                    assert [v["text"] for v in r["take_home_review"]] == item["take_home"]
            if lane != "hd":
                assert r["source_locators"] == item["sources"]
                assert {v["objective_id"] for v in r["objective_support"]} == set(item["objective_ids"])
                norm = lambda refs: {(v["source_id"], v["locator"]) for v in refs}
                for support in r["objective_support"]:
                    refs = item["sources"] if question else [ref for s in item["stages"] if s["id"] in support["stage_ids"] for ref in s["sources"]]
                    assert norm(refs) == norm(support["source_locators"])
            checked_claim = r.get("checked_claim", item.get("rationale", item.get("summary")))
            entry = dict(id=item["id"], version=item["version"], kind="question" if question else "case",
                reviewed_on=DATE, reviewer_kind="assistant", independent_human_review=False,
                source_locators=deepcopy(item["sources"]), checked_claim=checked_claim,
                skill="common_reasoning" if question else "mixed_domain_reasoning",
                key_text=key["text"] if question else None, proposal_review=deepcopy(r),
                exact_authored_record=deepcopy(item),
                integration_disposition="Exact authored claims, key and every distractor, stage/reveal/debrief, source loci, notice limits and separate rights reviewed. No independent human or source-wide currentness clearance.")
            if item["id"] == "RN15-HD-003":
                entry["skill"] = "mechanism"
            if item["id"] in {"RN15-CMV-001", "RN15-GBM-001"}:
                entry["skill"] = "interpretation"
            entry["objective_support"] = deepcopy(r.get("objective_support", [dict(
                objective_id="T20.O02", checked_claim="Partial ongoing-care safety and patient communication only; no full modality/preferences or T23.O01 emergency coverage.",
                source_locators=item["sources"], **({} if question else {"stage_ids": [s["id"] for s in item["stages"]]}))]))
            result.append(entry)
    assert len(result) == 25
    return result


def programme(prior, lanes):
    mapping = deepcopy(prior.manifest["programme_mappings"][0])
    # The official mapping evidence retains its actual inherited check date.
    mapping.update(version=MAPPING_VERSION)
    mapping["method"] += " Additive depth2 review: CMV prevention/medicine safety, anti-GBM follow-up and three HD emergency reasoning units; all domains remain partial."
    rows = {r["id"]: r for r in mapping["alignments"]}
    specs = {
        "hd_emergency": ("hd", "Intradialytic emergencies and urgent removal",
            "Existing hypotension credit is retained. Three staged cases and five distinct items add air embolism, haemolysis and access/disconnection bleeding recognition and immediate response reasoning. New credit is partial T20.O02 ongoing-care safety only; T20.O01/T23.O01 are inherited pins, not newly satisfied emergency objectives.",
            "Complete intradialytic emergency coverage, positioning/aspiration, resuscitation, transfusion decisions, device-specific operation, other emergencies and practical certification remain incomplete."),
        "glomerular_diagnosis": ("antigbm", None,
            "Six further anti-GBM items and a five-stage case add response/toxicity monitoring, qualified infection prevention, leukopenia review, usual treatment durations and the sustained-antibody-negativity transplant interval under T10.O02.",
            "Anti-GBM drug doses, numerical toxicity thresholds, complete adverse-effect/prophylaxis protocols, refractory disease and complete transplant assessment remain incomplete. Image-based histology and complete disease-specific treatment/monitoring pathways remain incomplete."),
        "transplant_aftercare_gap": ("cmv", None,
            "Eight CMV items and two four-stage cases add adult kidney-recipient serologic risk, prevention strategy/logistics, renal-dose review, EU letermovir conditions/interactions and qualified postprophylaxis surveillance. Existing BK credit remains. No T21 pretransplant objective credit is added.",
            "Comprehensive CMV prescribing, breakthrough/resistant CMV treatment, other recipient infections, rejection regimens, malignancy aftercare, allocation and long-term management remain incomplete."),
    }
    for identity, (lane, label, scope, gap) in specs.items():
        row = rows[identity]
        if label:
            row["label"] = label
        for kind in ("questions", "cases"):
            row[kind] += [dict(id=i["id"], version=i["version"]) for i in lanes[lane][kind]]
        row["objective_ids"] = sorted(set(row["objective_ids"]) | {o for kind in ("questions", "cases") for i in lanes[lane][kind] for o in i["objective_ids"]})
        row["scope_note"] += " " + scope
        row["gaps"] = [gap]
    row = rows["transplant_prevention"]
    row["cases"] += [dict(id=i["id"], version=i["version"]) for i in lanes["cmv"]["cases"]]
    row["objective_ids"] = sorted(set(row["objective_ids"]) | {"T19.O01", "T27.O02"})
    row["scope_note"] += " Shared CMV cases add posttransplant risk/prevention and medicine monitoring under T17.O02/T19.O01/T27.O02; the eight assessment pins count in transplant_aftercare_gap. T21 remains pretransplant only."
    row["gaps"] = ["Complete posttransplant virology, medicine-specific prophylaxis protocols and immunosuppression regimens remain incomplete; the bounded CMV cases do not cover resistant/breakthrough treatment or all recipients/viruses."]
    rows["hd_clearance"]["scope_note"] += " The shared hd_emergency facet now teaches the three named emergencies; this does not establish complete operational protocols."
    rows["hd_clearance"]["gaps"] = ["Full maintenance/home-HD prescription, water quality, general machine-alarm protocols, complete disconnection/air/haemolysis procedures and procedural competence remain incomplete."]
    assert all(rows[k]["status"] == "partial" for k in specs)
    assert [r["status"] for r in mapping["alignments"]] == [r["status"] for r in prior.manifest["programme_mappings"][0]["alignments"]]
    return mapping


def publish(evidence_dir, prior_review_path):
    evidence_dir = Path(evidence_dir).resolve()
    if evidence_dir.is_relative_to(ROOT.resolve()):
        raise ValueError("Evidence must stay outside the worktree")
    evidence_dir.mkdir(parents=True, exist_ok=True)
    # The CLI already supports an explicit canonical register. Older authoring
    # helpers call their imported validator without forwarding that parameter.
    # Supply it at those two caller aliases only; do not alter runtime files or
    # validation rules. Parent must regenerate the bundled runtime register.
    register_text = (ROOT / "docs/SOURCES.md").read_text(encoding="utf-8")
    register_ids = re.findall(r"^\| ([A-Z][0-9]{2}) [–—-]", register_text, re.MULTILINE)
    assert "G09" in register_ids and len(register_ids) == len(set(register_ids))
    content_validate = partial(validate_pack, known_register_ids=register_ids)
    base.validate_pack = content_validate
    required_cells.validate_pack = content_validate
    protected = protected_bytes()
    prior_review = pinned(prior_review_path, "b9b259157b77e62b20995677ac8478afc39a1c828107c7283a6851d091f39c43")
    lanes = {lane: {kind: pinned(PROPOSALS/f"{lane}/{kind}.json", PINS[f"{lane}/{kind}"], LF_PINS.get(f"{lane}/{kind}"))
             for kind in ("questions", "cases", "sources", "reviews")} for lane in ("hd", "cmv", "antigbm")}
    additions = {kind: [i for d in lanes.values() for i in d[kind]] for kind in ("questions", "cases", "sources")}
    assert [len(additions[k]) for k in ("questions", "cases", "sources")] == [19, 6, 8]
    ancestors = [content_validate(PACKS/v) for v in VERSIONS]
    prior = ancestors[-1]
    assert prior.sha256 == "19ea87bc7922328e18158652788550cdc7ca7590ccd128aa9e3dcc94fedc5ddc"
    mapping = programme(prior, lanes)
    topics = deepcopy(prior.bundle["topics"])
    for t in topics:
        t["version"] += 1
        t["mapping"]["mapping_version"] = MAPPING_VERSION
    reviewed = checked_reviews(lanes)
    review = eseneph.review_evidence(mapping)
    review.update(pack_version=VERSION, checked_on=DATE,
        method="Bounded assistant reading of recovered primary-source receipts and exact authored teaching/key/distractor review; targeted retained KDIGO/EMA/consensus passages rechecked without acquisition. Prior 83 item and 22 source review rows retained exactly.",
        access_limits="No new downloads or notice surveillance. Original rights and dated_final_baseline remain. KDIGO selected retained pages checked, not all corrections; BC/UK/US sources supplement EU education. No independent human review, full curriculum, practical certification or clinical-latest clearance.",
        sources=deepcopy(prior_review["sources"])+deepcopy(additions["sources"]),
        items=deepcopy(prior_review["items"])+reviewed,
        depth_review_items=reviewed, proposal_reviews={lane: d["reviews"] for lane, d in lanes.items()},
        inherited_review_sha256="b9b259157b77e62b20995677ac8478afc39a1c828107c7283a6851d091f39c43",
        proposal_sha256=PINS,
        integration_findings=[
            "Leon D+/R- condition added explicitly before application of EU letermovir kidney indication; adult >=40 kg, start by day 7 and through day 200 preserved. Label also includes eligible paediatric recipients, outside this adult slice. No CMV key changed.",
            "G09 was free and now registers BC Renal with separate restricted source terms. Earlier proposal publication_gate is historical; no remaining allocation collision.",
            "HD no-return applies to suspected air/haemolysis and explicitly contaminated disconnection circuits, not every bleed/arrest. UKKA2019 and STOP2023 overdue review remain distinct from later access guidance.",
            "Retained KDIGO combined PDF SHA256 8ed871ec098c7eba1cfb0ff6bf2355a6c422166b2691aac138f0273307b2acff: physical109/S104,237/S232 Fig98,238/S233,239/S234 Fig99 and PP11.2.7 checked locally; figures visually inspected. This supplements the original indexed review and closes the selected-byte reading gap only, not complete correction/currentness review.",
            "TMP-SMX consideration retains indirect-evidence qualification; screening is clinically appropriate/contextual, leukopenia requires individual treatment review, usual duration is not a rigid stop rule; transplant interval is sustained undetectable antibodies >=6months."])
    assert len(prior_review["items"]) == 83 and len(prior_review["sources"]) == 22
    if "question_skill_coverage" in review:
        del review["question_skill_coverage"]
    with TemporaryDirectory(prefix="depth2-stage-", dir=evidence_dir) as temporary:
        staged = Path(temporary)/"pack"
        base.publish_snapshot(staged, version=VERSION, topics=topics,
            sources=deepcopy(prior.bundle["sources"])+additions["sources"],
            questions=deepcopy(prior.bundle["questions"])+additions["questions"],
            cases=deepcopy(prior.bundle["cases"])+additions["cases"],
            target_topics=prior.bundle["coverage"]["target_topics"],
            minimum_questions=prior.bundle["coverage"]["minimum_questions"], published_on=DATE,
            programme_mappings=[mapping], withdrawals=deepcopy(prior.manifest["withdrawals"]))
        pack = content_validate(staged)
        ancestry = [validate_revision(pack, a) for a in ancestors]
        review_path = Path(temporary)/"review.json"
        review_path.write_bytes(raw(review))
        review_count = validate_review_evidence(pack, review_path, ancestors)
        receipt = build_manifest(staged, review_path)
        assert receipt["adopted_bank_minima_met"] and not receipt["objective_link_holds"]
        assert not receipt["objective_cells_without_case_links"]
        assert all(r["update_sources"]["status"] == "needs_currency_review" for r in receipt["topic_cells"])
        assert all(r["status"] == "partial" for r in receipt["programme"]["domains"])
        assert review_count == 108 and len(review["sources"]) == 30
        for kind in ("questions", "cases", "sources"):
            assert pack.bundle[kind][:len(prior.bundle[kind])] == prior.bundle[kind]
        for old, new in zip(prior.bundle["topics"], pack.bundle["topics"]):
            expected = deepcopy(old)
            expected["version"] += 1
            expected["mapping"]["mapping_version"] = MAPPING_VERSION
            assert new == expected
        assert review["items"][:83] == prior_review["items"]
        assert review["sources"][:22] == prior_review["sources"]
        assert mapping["evidence"] == prior.manifest["programme_mappings"][0]["evidence"]
        assert protected_bytes() == protected
        summary = dict(valid=True, pack=receipt["pack"], counts=receipt["counts"], sources=len(pack.bundle["sources"]),
            inherited=dict(questions=230, cases=52, sources=69, review_items=83, review_sources=22),
            added={k:len(v) for k,v in additions.items()}, review_rows=review_count,
            source_review_rows=len(review["sources"]), ancestry=ancestry,
            new_ids={k:[i["id"] for i in v] for k,v in additions.items()},
            mapping_version=MAPPING_VERSION, mapped_questions=receipt["programme"]["available_questions"],
            five_option_questions=receipt["programme"]["format_compatible_questions"],
            old_byte_equality=True, protected_files=protected, unchanged_inherited_records=True,
            unchanged_old_keys_options_families=True, unchanged_objective_definitions=True,
            topic_change="Version +1 and new programme mapping reference only", currency_cells_remaining=27,
            all_domains_partial=True, independent_human_review=False, complete_content_coverage=False,
            register_validation="Explicit IDs parsed from docs/SOURCES.md through existing known_register_ids parameter; bundled runtime G09 registration remains parent integration work.",
            runtime_activation="not performed", proposal_sha256=PINS,
            files={p.name:sha256(p.read_bytes()).hexdigest() for p in staged.iterdir()})
        blobs = {PACKS/VERSION/p.name:p.read_bytes() for p in staged.iterdir()}
        blobs[ROOT/f"content/mappings/esen-eph-{MAPPING_VERSION}.json"] = raw(mapping)
        blobs[ROOT/f"content/required-cells/renulus-foundations-{VERSION}.json"] = raw(receipt)
        blobs[evidence_dir/f"renulus-foundations-{VERSION}-review.json"] = raw(review)
        blobs[evidence_dir/"verification.json"] = raw(summary)
        for path, data in blobs.items():
            if path.exists() and path.read_bytes() != data:
                raise ValueError(f"Refusing to replace immutable artifact: {path}")
        for path, data in blobs.items():
            write_immutable(path, data)
        assert protected_bytes() == protected
    return {k:v for k,v in summary.items() if k not in {"protected_files", "proposal_sha256", "files"}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--prior-review", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(publish(args.evidence_dir, args.prior_review), indent=2))
