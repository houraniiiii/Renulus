# SPDX-License-Identifier: MIT
"""Build 1.3.0 using existing static authoring/validation; never activate a pack.

Review receipts and staging stay in the supplied external evidence directory.
No networking, database, engine, provider or native execution is performed.
"""
import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/content"))
import author_foundations as base
import author_eseneph as eseneph
from author_depth import write_immutable
from check_required_cells import build_manifest
from revision_checks import validate_revision, validate_review_evidence
from renulus.content.validation import validate_pack
import application_material as material

VERSION = "1.3.0"
MAPPING_VERSION = "2026-10-07-application1"
PACKS = ROOT / "content/packs/renulus-foundations"
VERSIONS = ("1.0.0", "1.0.1", "1.1.0", "1.1.1", "1.1.2", "1.2.0")
MGRS = "L01-MGRS-2026-diagnostic-application"
IKMG = "L01-IKMG-2019-diagnostic-application"
ISTH = "L01-ISTH-2020-diagnostic-application"
OLD_IKMG = "L01-IKMG-evaluation-2019"
OLD_ISTH = "L01-ISTH-TTP-diagnosis-2020"
NARROW = "RN11-T11-001"
NARROW_TEXT = ("The combined findings suggest inappropriate proximal solute loss. Investigate a possible light-chain cause; "
               "these findings alone do not establish light-chain proximal tubulopathy.")
CORRECTION_REASON = ("Rationale-only evidence correction: narrow the unsupported ancillary differential instruction in the overall and keyed-option explanations. "
                     "Answer A, option identities/text, stem and family are unchanged; no scoring-key reversal.")


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def raw(body):
    return (json.dumps(body, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def pinned_input(path, expected):
    data = Path(path).read_bytes()
    if sha256(data).hexdigest() != expected:
        raise ValueError(f"Recovered evidence changed: {path}")
    return json.loads(data)


def new_sources(prior):
    old = {s["id"]: s for s in prior.bundle["sources"]}
    rows = []
    def clone(identity, previous, scope, note):
        s = deepcopy(old[previous])
        s.update(id=identity, checked_on=material.DATE, scope=scope, check_note=note,
                 check_status="locator_checked", currency="dated_final_baseline")
        rows.append(s)
    clone(IKMG, OLD_IKMG,
        "Seven diagnostic questions and the proximal-loss case compared with 2026 MGRS evidence; no clone-directed treatment or universal biopsy rule.",
        "Recovered finish-mgrs-comparison-20261007.md and its exact eight-item receipt: old UCL 15-page PDF physical-page locators and new XML loci agree at the stated scopes. "
        "Correction of original DOI 10.1038/s41581-018-0077-4 by DOI 10.1038/s41581-018-0102-7 (online 2018-12-19, February 2019 issue; https://www.nature.com/articles/s41581-018-0102-7): Figure 1 microtubular label is corrected. "
        "None of the selected items reproduces the erroneous label. Adopt the relationship, without claiming corrected original bytes or wholesale IKMG supersession. "
        "The 2026 executive-summary comparison supports the seven retained keys; RN11-T11-001's ancillary rationale is narrowed in version 2. No source-wide currency clearance.")
    clone(ISTH, OLD_ISTH,
        "Existing four diagnostic/TPE-mechanism questions and TMA case only; no PLASMIC scoring item, full treatment regimen or congenital TTP update.",
        "Recovered finish-source-currency-20261007.md, sources/additional-findings.json and the 1.2.0 correction snapshot. "
        "Original DOI 10.1111/jth.15006 is corrected by DOI 10.1111/jth.15304 (online 2021-04-20, May issue; https://onlinelibrary.wiley.com/doi/10.1111/jth.15304). "
        "The intermediate PLASMIC category uses score 5, not 6; the high category remains 6-7. RN11-T15-001, RN11-T15-002, RN11-T15-004, RN11-T23-002 and RN11-CASE-TMA do not use that row. "
        "Their propositions and keys are retained; successor citations now carry the correction relationship. Primary diagnosis reading is inherited from October 4, notice-impact review from October 7, not newly fetched. "
        "No whole corrected-file incorporation or 2025 treatment-scope clearance.")
    rows.append(dict(id=MGRS, register_id="L01",
        title="European MGRS consensus executive summary: diagnostic comparison",
        edition="2026 executive summary; published 2026-05-26, CKJ 19(6); DOI 10.1093/ckj/sfag163; PMC13284707.1",
        publication_status="final", url="https://academic.oup.com/ckj/article/19/6/sfag163/8694705",
        canonical_topic_url="https://doi.org/10.1093/ckj/sfag163", checked_on=material.DATE,
        check_status="locator_checked", currency="dated_final_baseline",
        scope="Exact seven diagnostic questions and proximal-loss case: protein characterization, causality, pathology, renal/assay-dependent FLC, amyloid typing and LCPT biopsy boundary. Full appendix and treatment are excluded.",
        rights_note="Authors 2026, published by OUP on behalf of ERA, CC BY 4.0 per recovered XML. Renulus contributes original expression only; no source body, tables or figures are bundled. Other referenced publications retain separate terms.",
        check_note="Recovered successful official Europe PMC fullTextXML https://www.ebi.ac.uk/europepmc/webservices/rest/PMC13284707/fullTextXML, HTTP 200 at 2026-10-07T13:31:22.9163425Z; SHA256 d405af8506f148513c3586d81933b0b74105b79ec76a08cfced2a7713e69c980. "
        "No new retrieval. Locators use exact XML IDs and direct paragraph-child indexes: sec1/p[1], sec2/p[1]-p[4], tbl2, tbl4 including tbl4fn1, tbl9, sec3/p[3], sec4/p[11]-p[13]. "
        "Seven retained keys supported; ancillary proximal rationale narrowed. The LCPT complete-Fanconi/MIg/abnormal serum-and-urine FLC biopsy exception and atypical-feature limits are preserved. "
        "No numeric FLC interval, universal CKD screening, unconditional biopsy, full-appendix review or clone-directed regimen is inferred."))
    clone(material.GBM, "K08-2021-remaining-expansion",
        "2021 Chapter 11 only: anti-GBM urgency, pulmonary boundary of the renal treatment exception, exchange endpoint and double-positive maintenance distinction. No doses or older AAV treatment regimen.",
        "Existing required-coverage gap and K08 edition/chapter evidence recovered before the narrow reading. Additional exact official indexed primary passages checked October 7: PP 11.1.1, recommendation 11.2.1 (S86); PP 11.2.1-11.2.2 and 11.2.4-11.2.5 (S87/S233). "
        "Official combined PDF reader was unavailable; full primary indexed text at https://kdigo.org/wp-content/uploads/2024/05/KDIGO-2021-Glomerular-Diseases-Guideline_English_2024-Chapter-Updates.pdf and https://kdigo.org/wp-content/uploads/2017/02/KDIGO-Glomerular-Diseases-Guideline-2021-English.pdf supplied these passages. "
        "Chapter 11 remains a dated baseline under SOURCES.md. Replaced chapters 2/4/9/10 are excluded; the double-positive item identifies a maintenance pathway without importing the old AAV regimen. No broad clinical-currency or notice-completeness claim.")
    clone(material.PKD, "K03-2025-expansion",
        "Adult family-testing counseling, known familial pathogenic variants, negative-panel limits and equivocal related-donor imaging. No complete variant classification, reproductive/pediatric screening or donor approval algorithm.",
        "Recovered prior K03 source/coverage review, then checked the needed primary PDF passages at https://kdigo.org/wp-content/uploads/2025/01/KDIGO-2025-ADPKD-Guideline.pdf: PP 1.3.1-1.3.3 (S22), 1.3.9 (S24/S67), 1.3.10-1.3.11 (S25/S68), 1.3.17-1.3.18 (S27; S67/S72-S73). "
        "Official text reader succeeded October 7; no new complete currentness or rights clearance. The 2026/04 rehosting of the same named guideline does not change its 2025 edition. Source restrictions, including CC BY-NC-ND, remain independent from original Renulus teaching.")
    # Pin the actually read primary file instead of suggesting that rehosted bytes were compared.
    rows[-1]["url"] = "https://kdigo.org/wp-content/uploads/2025/01/KDIGO-2025-ADPKD-Guideline.pdf"
    return rows


def revise(prior, mgrs):
    questions, cases = deepcopy(prior.bundle["questions"]), deepcopy(prior.bundle["cases"])
    prior_reviews = {r["id"]: r for r in read(ROOT / "content/reviews/renulus-foundations-1.1.0.json")["items"]}
    changed, evidence = [], []
    for item in questions + cases:
        old_ids = {r["source_id"] for r in item["sources"]}
        if not old_ids.intersection({OLD_IKMG, OLD_ISTH}):
            continue
        before = deepcopy(item)
        item["version"] += 1
        item["review"] = deepcopy(material.REVIEW)
        item["review"]["method"] = ("Application of recovered October 7 source comparison/correction impact to this immutable successor. "
            "Original diagnosis reading and historical keys are retained; no independent human or source-wide currency review. "
            + ("Ancillary overall/keyed-option rationale narrowed; answer and option text unchanged." if item["id"] == NARROW else "Content propositions retained at the specified scope."))
        if "answer" in item:
            item["key_version"] = item["version"]
            if OLD_IKMG in old_ids:
                finding = mgrs["locators"][item["id"]]
                item["sources"] = [material.cite(IKMG, finding["old"]), material.cite(MGRS,
                    "Executive-summary XML " + "; ".join(finding["new"]) + "; p[n] is a direct paragraph child")]
            else:
                for ref in item["sources"]:
                    if ref["source_id"] == OLD_ISTH:
                        ref["source_id"] = ISTH
            if item["id"] == NARROW:
                item["rationale"] = NARROW_TEXT
                next(o for o in item["options"] if o["id"] == item["answer"])["rationale"] = NARROW_TEXT
                item["correction"] = dict(previous_version=before["version"], reason=CORRECTION_REASON)
            support = [dict(objective_id=o, checked_claim=item["rationale"], source_locators=deepcopy(item["sources"])) for o in item["objective_ids"]]
            skill = prior_reviews[item["id"]]["skill"]
            key_text = next(o["text"] for o in item["options"] if o["id"] == item["answer"])
        else:
            for n, stage in enumerate(item["stages"]):
                for ref in stage["sources"]:
                    if ref["source_id"] == OLD_ISTH:
                        ref["source_id"] = ISTH
                    elif ref["source_id"] == OLD_IKMG:
                        ref.update(source_id=IKMG, locator=[
                            "UCL PDF physical pp4-5,10-11: LCPT and monoclonal immunoglobulin testing",
                            "UCL PDF physical p3 Box 1 and p9: definition and incidental gammopathy",
                            "UCL PDF physical pp9-11: renal biopsy evaluation"][n])
                if OLD_IKMG in old_ids:
                    stage["sources"].append(material.cite(MGRS, "Executive-summary XML " + [
                        "sec2/p[2]; sec4/p[11]-p[12]", "sec1/p[1]; sec2/p[1]",
                        "sec2/p[3]; tbl2; sec4/p[11]-p[12]"][n] + "; p[n] is a direct paragraph child"))
            if OLD_IKMG in old_ids:
                item["stages"][2]["teaching_points"].append(
                    "The 2026 consensus permits LCPT diagnosis without biopsy when complete Fanconi syndrome, a monoclonal immunoglobulin and abnormal serum and urine free light chains are established, unless atypical features require tissue assessment. This case does not establish those prerequisites; the protein quantity alone does not settle the exception.")
            item["sources"] = []
            for stage in item["stages"]:
                for ref in stage["sources"]:
                    if ref not in item["sources"]:
                        item["sources"].append(deepcopy(ref))
            stages_for = ({"T11.O01":[1], "T18.O01":[2], "T18.O02":[2,3], "T02.O02":[1,3], "T22.O01":[3]}
                if OLD_IKMG in old_ids else {"T15.O01":[1], "T15.O02":[2,3], "T23.O02":[2,3], "T27.O02":[2,3]})
            support = [dict(objective_id=o, stage_ids=[f"stage-{n}" for n in stages_for[o]],
                checked_claim=" ".join(p for n in stages_for[o] for p in item["stages"][n-1]["teaching_points"]),
                source_locators=[r for n in stages_for[o] for r in item["stages"][n-1]["sources"]]) for o in item["objective_ids"]]
            skill, key_text = "mixed_domain_reasoning", None
        evidence.append(dict(id=item["id"], version=item["version"], kind="question" if "answer" in item else "case",
            reviewed_on=material.DATE, reviewer_kind="assistant", independent_human_review=False,
            skill=skill, source_locators=deepcopy(item["sources"]), key_text=key_text,
            checked_claim=" ".join(s["checked_claim"] for s in support), objective_support=support,
            source_application=dict(previous_version=before["version"], answer_reversal=False,
                basis="finish-mgrs-comparison-20261007.md" if OLD_IKMG in old_ids else "finish-source-currency-20261007.md",
                limit="Exact diagnostic/notice-impact comparison only; no whole-topic currency clearance.")))
        changed.append(dict(id=item["id"], kind="question" if "answer" in item else "case", previous_version=before["version"],
            version=item["version"], key_version=item.get("key_version"), answer=item.get("answer"), family_id=item.get("family_id"),
            family_version=item.get("family_version"), source_ids=sorted({r["source_id"] for r in item["sources"]})))
    return questions, cases, evidence, changed


def programme(prior, questions, cases):
    mapping = deepcopy(prior.manifest["programme_mappings"][0])
    mapping["version"] = MAPPING_VERSION
    mapping["method"] = ("Assistant alignment review October 7: exact successor pins for MGRS/ISTH application plus two existing finite gaps, anti-GBM decisions and ADPKD family testing. "
        "Official curriculum/blueprint evidence retains its actual October 5 check date and hashes. All eleven domains remain partial.")
    mapping["exam"]["weight_note"] = ("Indicative counts are reference weights, not a new launch quota. The pack mixes 178 historical four-option items and 52 five-option items; no full examination simulation.")
    selected = {i["id"]: i for i in questions + cases}
    for row in mapping["alignments"]:
        for kind in ("questions", "cases"):
            for pin in row[kind]:
                pin["version"] = selected[pin["id"]]["version"]
    rows = {r["id"]: r for r in mapping["alignments"]}
    for cell in material.CELLS:
        row = rows[cell["alignment_id"]]
        assert cell["baseline_gap"] in row["gaps"], "This unit must address the recovered existing gap"
        newq = [q for q in material.QUESTIONS if q["id"].startswith(cell["prefix"])]
        newc = next(c for c in material.CASES if c["id"] == cell["case_id"])
        row["questions"] += [dict(id=q["id"], version=q["version"]) for q in newq]
        row["cases"].append(dict(id=newc["id"], version=1))
        row["objective_ids"] = sorted(set(row["objective_ids"]) | {o for i in newq+[newc] for o in i["objective_ids"]})
        row["scope_note"] += " " + cell["scope"]
        row["gaps"] = [cell["remaining_gap"]]
    rows["paraprotein"]["scope_note"] += " Relevant successor pins now carry the bounded 2026 MGRS diagnostic comparison; full treatment remains outside scope."
    # A teaching case can support the existing apheresis facet without double-counting its questions across domains.
    row = rows["apheresis"]
    row["cases"].append(dict(id="RN14-CASE-ANTI-GBM", version=1))
    row["objective_ids"] = sorted(set(row["objective_ids"]) | {"T23.O02"})
    row["scope_note"] += " Anti-GBM case stage 3 adds its disease-specific plasma-exchange endpoint; its questions count only in the glomerular domain."
    return mapping


def check_application(pack, review, prior):
    selected = {i["id"]: i for k in ("questions","cases") for i in pack.bundle[k]}
    for row in review["application_review_items"]:
        i = selected[row["id"]]
        claims = row["objective_support"]
        assert {c["objective_id"] for c in claims} == set(i["objective_ids"])
        for claim in claims:
            assert claim["checked_claim"]
            expected = i["sources"] if "answer" in i else [r for s in i["stages"] if s["id"] in claim["stage_ids"] for r in s["sources"]]
            norm = lambda refs: {(r["source_id"], r["locator"]) for r in refs}
            assert norm(claim["source_locators"]) == norm(expected)
    for old in prior.bundle["questions"]:
        new = selected[old["id"]]
        assert new["answer"] == old["answer"]
        assert [(o["id"],o["text"]) for o in new["options"]] == [(o["id"],o["text"]) for o in old["options"]]
        assert (new["family_id"],new["family_version"]) == (old["family_id"],old["family_version"])
    actual_changes = {i["id"] for kind in ("questions","cases") for i in prior.bundle[kind] if selected[i["id"]] != i}
    assert actual_changes == {r["id"] for r in review["changed_identities"]}
    assert sum(r["kind"] == "question" for r in review["changed_identities"]) == 11
    assert sum(r["kind"] == "case" for r in review["changed_identities"]) == 2
    assert pack.bundle["sources"][:len(prior.bundle["sources"])] == prior.bundle["sources"]
    assert pack.manifest["programme_mappings"][0]["evidence"] == prior.manifest["programme_mappings"][0]["evidence"]
    for cell in review["application_cells"]:
        row = next(r for r in pack.manifest["programme_mappings"][0]["alignments"] if r["id"] == cell["alignment_id"])
        case = selected[cell["case_pin"]["id"]]
        assert row["status"] == "partial" and cell["remaining_gap"]
        assert len(cell["question_pins"]) == len(cell["outcomes"]) == 4 and len(case["stages"]) == 3
        assert cell["case_pin"] in row["cases"]
        for p in cell["question_pins"]:
            q = selected[p["id"]]
            assert p in row["questions"] and len(q["options"]) == 5
            assert set(q["objective_ids"]).issubset(case["objective_ids"])
    assert "Review medications and acquired/inherited causes" not in json.dumps(selected[NARROW])
    return dict(new_questions=8, new_cases=2, revised_questions=11, revised_cases=2,
        retained_answers=len(prior.bundle["questions"]), preserved_source_snapshots=len(prior.bundle["sources"]),
        finite_units=2, all_currency_cells_open=True, runtime_activation="not performed")


def publish(evidence_dir, prior_evidence, mgrs_evidence, output=None, mapping_output=None, required_output=None):
    evidence_dir = Path(evidence_dir).resolve()
    if evidence_dir.is_relative_to(ROOT.resolve()):
        raise ValueError("Staging and review evidence must stay outside the worktree")
    prior_review = pinned_input(Path(prior_evidence) / "release/renulus-foundations-1.2.0-review.json",
        "3b6345f1f5cb5205ecb57e8ce6f259a4290e1823724d698c16216849165ddd7b")
    mgrs = pinned_input(Path(mgrs_evidence) / "research-receipt.json",
        "e11345ea81a85d34fbde086ae5d4a30ad54a3981db7ff998da749486df288709")
    ancestors = [validate_pack(PACKS / v) for v in VERSIONS]
    prior = ancestors[-1]
    if prior.sha256 != "8d19adbba339413cc3f59682f4db41b244c690649616dfacaf69973248970b9b":
        raise ValueError("Prior release differs from recovered evidence")
    evidence_dir.mkdir(parents=True, exist_ok=True)
    questions, cases, revisions, changed = revise(prior, mgrs)
    questions += deepcopy(material.QUESTIONS)
    cases += deepcopy(material.CASES)
    sources = new_sources(prior)
    mapping = programme(prior, questions, cases)
    topics = deepcopy(prior.bundle["topics"])
    for t in topics:
        t["version"] += 1
        t["mapping"]["mapping_version"] = MAPPING_VERSION
    review = eseneph.review_evidence(mapping)
    changed_ids = {r["id"] for r in revisions}
    new_reviews = revisions + deepcopy(material.EVIDENCE)
    cells = [dict(c, question_pins=[dict(id=q["id"],version=1) for q in material.QUESTIONS if q["id"].startswith(c["prefix"])],
        case_pin=dict(id=c["case_id"],version=1)) for c in material.CELLS]
    review.update(pack_version=VERSION, checked_on=material.DATE,
        method="Assistant application of recovered primary MGRS comparison and IKMG/ISTH correction impact, rationale narrowing, and source/key/stage review of two finite breadth units. Prior 1.2.0 review rows retain their original method/date.",
        inherited_review="All six earlier pack directories remain unchanged. 211 prior questions, 48 cases, 64 sources and all 57 objective definitions are preserved. Eleven question/two case successors retain stable identities; no answer or option text changes.",
        access_limits="Recovered exact evidence before any new reading. Only additional needed K08 Chapter 11 and K03 family/genetic passages checked; official full PDF reader failed for K08, so exact indexed primary text was used. No MGRS/notice refetch, full appendix, private originals, provider, or source-wide currency clearance.",
        sources=deepcopy(prior_review["sources"]) + sources,
        items=[r for r in deepcopy(prior_review["items"]) if r["id"] not in changed_ids] + new_reviews,
        application_review_items=new_reviews, application_cells=cells, changed_identities=changed,
        source_application=[dict(original_doi="10.1038/s41581-018-0077-4", notice_doi="10.1038/s41581-018-0102-7", source_id=IKMG,
            scope="Figure 1 label only; none of the selected eight records reproduces it; no answer reversal"),
            dict(original_doi="10.1111/jth.15006", notice_doi="10.1111/jth.15304", source_id=ISTH,
            scope="Table 1 intermediate PLASMIC row; none of the five selected records uses the row; no answer reversal")],
        source_currency_holds=dict(all_topic_update_cells_remain_open=True, retained_corrected_bytes_verified=False,
            resolved="Exact eight-record 2026 MGRS reading/comparison adopted; named ancillary rationale narrowed.",
            remaining="Full MGRS appendix/treatment, overdue UKKA scopes, unavailable notice statuses and complete corrected-copy incorporation retain their prior limits."))
    withdrawals = deepcopy(prior.manifest["withdrawals"]) + [dict(question_id=NARROW, version=1, replacement_version=2, reason=CORRECTION_REASON)]
    review_path = evidence_dir / "renulus-foundations-1.3.0-review.json"
    with TemporaryDirectory(prefix="application-stage-", dir=evidence_dir) as temp:
        staged = Path(temp) / "pack"
        result = base.publish_snapshot(staged, version=VERSION, topics=topics, sources=deepcopy(prior.bundle["sources"])+sources,
            questions=questions, cases=cases, target_topics=prior.bundle["coverage"]["target_topics"],
            minimum_questions=prior.bundle["coverage"]["minimum_questions"], published_on=material.DATE,
            programme_mappings=[mapping], withdrawals=withdrawals)
        pack = validate_pack(staged)
        ancestry = [validate_revision(pack, a) for a in ancestors]
        staged_review = Path(temp) / "review.json"
        staged_review.write_bytes(raw(review))
        review_count = validate_review_evidence(pack, staged_review, ancestors)
        checks = check_application(pack, review, prior)
        receipt = build_manifest(staged, staged_review)
        assert receipt["adopted_bank_minima_met"] and not receipt["objective_link_holds"]
        assert not receipt["objective_cells_without_case_links"]
        assert all(r["update_sources"]["status"] == "needs_currency_review" for r in receipt["topic_cells"])
        blobs = {Path(output or PACKS/VERSION)/p.name: p.read_bytes() for p in staged.iterdir()}
        blobs[Path(mapping_output or ROOT/f"content/mappings/esen-eph-{MAPPING_VERSION}.json")] = raw(mapping)
        blobs[Path(required_output or ROOT/f"content/required-cells/renulus-foundations-{VERSION}.json")] = raw(receipt)
        blobs[review_path] = raw(review)
        summary = dict(valid=True, pack=receipt["pack"], counts=receipt["counts"], sources=len(pack.bundle["sources"]),
            checks=checks, review_rows=review_count, ancestry=ancestry, changed_identities=changed,
            new_source_ids=[s["id"] for s in sources], application_cells=cells,
            mapped_questions=receipt["programme"]["available_questions"], five_option_questions=receipt["programme"]["format_compatible_questions"],
            currency_cells_remaining=len(receipt["topic_cells"]), complete_content_coverage=False,
            files={p.name:sha256(p.read_bytes()).hexdigest() for p in staged.iterdir()})
        blobs[evidence_dir/"verification.json"] = raw(summary)
        for p,b in blobs.items():
            if p.exists() and p.read_bytes() != b:
                raise ValueError(f"Refusing to overwrite immutable artifact: {p}")
        for p,b in blobs.items():
            write_immutable(p,b)
    return dict(result, sources=69, review_rows=review_count, **checks)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--prior-evidence", required=True, type=Path)
    parser.add_argument("--mgrs-evidence", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--mapping-output", type=Path)
    parser.add_argument("--required-output", type=Path)
    args = parser.parse_args()
    print(json.dumps(publish(args.evidence_dir, args.prior_evidence, args.mgrs_evidence,
        args.output, args.mapping_output, args.required_output), indent=2))
