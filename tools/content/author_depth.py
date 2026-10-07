# SPDX-License-Identifier: MIT
"""Publish immutable foundations 1.2.0; all staging/review receipts stay outside Git.

This reproduces original authored content without network, models or app execution.
The parent alone owns activation and installed acceptance.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import author_foundations as base
import author_eseneph as mapping_base
import depth_material as material
from revision_checks import validate_review_evidence, validate_revision
from renulus.content.validation import PackValidationError, validate_pack

ROOT = base.ROOT
VERSION = "1.2.0"
DATE = material.DATE
MAPPING_VERSION = "2026-10-07-depth1"
PRIOR = ROOT / "content/packs/renulus-foundations/1.1.2"
RELEASE = PRIOR.parent / VERSION
MAPPING_PATH = ROOT / f"content/mappings/esen-eph-{MAPPING_VERSION}.json"
NEW_OBJECTIVE = dict(id="T23.O03", text="Explain regional citrate anticoagulation, calcium and acid-base monitoring, and dependence on a validated circuit protocol.")

# Stable family, key and choice values survive these meaning-checked metadata changes.
CORRECTIONS = {
    "RN11-T20-001": ("T20.O02", "hd_clearance", "common_reasoning", material.HD,
        "Overall adequacy concerns ongoing dialysis care rather than the decision to initiate dialysis."),
    "RN11-T20-003": ("T23.O01", "hd_clearance", "interpretation", material.HD,
        "URR arithmetic measures solute clearance; the existing secondary T23 tag permits this explicit objective."),
    "RN11-T17-004": ("T21.O02", "transplant_candidates", "common_reasoning", material.CANDIDATE,
        "Cancer remission is a transplant-candidate risk question, not an infection-risk question."),
    "RN11-T23-004": ("T23.O03", "acute_support", "mechanism", material.CITRATE,
        "The new explicit objective addresses regional anticoagulation and its monitoring; an apheresis-indication objective did not."),
}

# Each row is a finite teaching/assessment increment, not a newly invented full-domain quota.
CELL_ROWS = [
    ("iga_diagnosis_risk", "glomerular_interstitial", "glomerular_diagnosis", "IGA", "IGA",
     ["Biopsy versus serum markers", "Risk despite sub-1-g/day proteinuria", "Prediction versus treatment selection", "IgAV prevention versus treatment"],
     "IgAN/IgAV diagnosis, risk and treatment-reasoning cells now have four questions and a three-stage case.",
     "Anti-GBM-specific assessment, image-based histology and full disease-specific treatment/monitoring pathways remain absent."),
    ("established_cdi", "acute_biochemistry", "water_sodium", "DI", "DI",
     ["Water access and omitted DDAVP", "Circulatory resuscitation", "Serial sodium and urine monitoring", "Fluid adjustment after antidiuresis"],
     "Established adult CDI and decompensated hypernatremia now have a focused question/case set.",
     "Initial DI diagnosis, nephrogenic DI, pregnancy CDI, and the complete hypernatremia differential/correction curriculum remain absent."),
    ("longitudinal_ckd_risk", "ckd_urine", "ckd_progression", "CKD", "CKD-RISK",
     ["Five-year risk and referral", "Two-year risk and preparation", "Meaningful eGFR change", "Doubling of ACR"],
     "Serial measurement interpretation and risk-based referral/preparation are explicitly assessed and taught.",
     "Full cause-specific longitudinal care, persistent-hematuria workup and a complete modality-selection curriculum remain incomplete."),
    ("anemia_response", "bone_anemia", "anemia", "ANEMIA", "ANEMIA-RESPONSE",
     ["Investigating iron depletion", "Iron during systemic infection", "ESA hyporesponsiveness", "Transfusion and sensitization tradeoffs"],
     "Iron-cause assessment, infection interruption, ESA-response review and individualized transfusion reasoning are added.",
     "Complete iron/ESA/HIF-PHI dosing, formulation-specific safety, fracture/osteoporosis and calciphylaxis teaching remain incomplete."),
    ("kidney_protection_review", "cardiovascular_diabetes", "diabetes", "CARDIO", "KIDNEY-PROTECTION",
     ["SGLT2 interruption and restart", "Early filtration response", "nsMRA potassium eligibility", "Avoiding dual RAS blockade"],
     "Kidney-protection response, acute interruption and potassium-related safety have a linked case and assessment set.",
     "Insulin adjustment, pancreatic transplantation, comprehensive secondary hypertension and cardiovascular emergency pathways remain incomplete."),
    ("asymptomatic_bacteriuria", "urology", "urinary_infection_gap", "ASB", "BACTERIURIA",
     ["Nonpregnant diabetes", "Pregnancy exception", "Mucosa-traumatizing procedure exception", "Long-term catheter and pyuria"],
     "ASB context and procedural/pregnancy exceptions extend the existing recurrent-UTI content.",
     "Acute upper-tract UTI, resistance-specific doses, complete stone intervention and chronic/congenital obstruction pathways remain incomplete."),
    ("gitelman_reasoning", "inherited_rare", "other_inherited_gap", "GS", "SALT-WASTING",
     ["Salt-wasting phenotype", "Molecular confirmation and uncertainty", "Linked magnesium/potassium replacement", "Adjunct treatment and volume tradeoff"],
     "Gitelman phenotype, confirmation and treatment tradeoffs extend Alport teaching without borrowing ADPKD objectives.",
     "Fabry, cystinosis, primary hyperoxaluria, complete Bartter/HNF1B differential and full inherited-disease management remain absent or incomplete."),
    ("pd_response_and_access", "peritoneal_dialysis", "pd_infection_gap", "PD", "PD-RESPONSE",
     ["Corrected refractory-definition units", "Improving versus failing day-five response", "Relapse classification", "Fungal access management"],
     "The corrected refractory definition and response/relapse/fungal catheter decisions are now taught and assessed.",
     "Complete organism-specific drug regimens/doses, Enterococcus Figure 8 treatment, mechanical catheter issues, prescription and ultrafiltration failure remain incomplete."),
    ("hd_delivery_and_tolerance", "hemodialysis", "hd_clearance", "HD", "HD-ADEQUACY",
     ["Symptomatic hypotension response", "Staged fluid removal and schedule", "Changing residual clearance", "Dialysate temperature review"],
     "HD delivery and tolerance now have a dedicated three-stage case and four five-option questions plus corrected existing adequacy/URR pins.",
     "Full maintenance/home-HD prescription, water quality, machine alarms, disconnection/air/haemolysis emergencies and procedural competence remain incomplete."),
    ("bk_aftercare_decisions", "transplantation", "transplant_aftercare_gap", "BK", "BK-DECISIONS",
     ["Assay-consistent confirmation", "Structured immunosuppression reduction", "Unsupported routine antiviral agents", "Context-dependent biopsy"],
     "BK aftercare now includes confirmatory intervals, reduction/monitoring tradeoffs, unsupported drugs and biopsy reasoning.",
     "Other recipient infections including comprehensive CMV prophylaxis, rejection regimens, malignancy aftercare, allocation and long-term management remain incomplete."),
    ("pregnancy_surveillance", "other", "pregnancy", "PREG", "PREGNANCY-SURVEILLANCE",
     ["Creatinine rather than invalid eGFR", "Superimposed pre-eclampsia assessment", "Proteinuria baseline", "Aspirin and continuing surveillance"],
     "Pregnancy measurement, prevention and assessment triggers have a dedicated case and four-question set.",
     "Complete transplant-pregnancy pharmacology, HELLP/delivery decisions, fertility, rehabilitation, terminal symptom prescribing and the broader other-domain curriculum remain incomplete."),
]


def sources(prior):
    old = {s["id"]: s for s in prior.bundle["sources"]}
    rows=[]

    def add(identity, register, title, edition, url, canonical, scope, check, rights):
        rows.append(dict(id=identity, register_id=register, title=title, edition=edition,
            publication_status="final", url=url, canonical_topic_url=canonical,
            checked_on=DATE, check_status="locator_checked", currency="dated_final_baseline",
            scope=scope, rights_note=rights + " Original Renulus expression only; no source prose, tables, figures, official questions or permission to ingest/redistribute the source is bundled.",
            check_note=check + " Scoped content check on 2026-10-07, not complete corrected-current clearance. Publication-record status and overdue guideline review are separate."))

    def clone(identity, original, scope, check):
        s=old[original]
        add(identity, s["register_id"], s["title"], s["edition"], s["url"],
            s["canonical_topic_url"], scope, check, "Underlying publication rights retained.")

    add(material.IGA,"K04","KDIGO IgAN/IgAV: diagnosis and risk reasoning","2025 final; 2026 commentary is a separate publication",
        "https://kdigo.org/wp-content/uploads/2026/04/KDIGO-2025-IgAN-IgAV-Guideline.pdf",
        "https://kdigo.org/guidelines/iga-nephropathy/",
        "Biopsy, proteinuria risk, limits of prediction/MEST-C treatment selection and prevention in extrarenal IgAV; no current new-drug comparison.",
        "Official PDF and topic page read: PP 1.2.1, 1.4.1.1, 1.4.2.1, 1.4.2.3 and recommendation 1.9.1.1. Uses the replacement chapter rather than GD 2021 chapter 2.",
        "KDIGO/Elsevier CC BY-NC-ND source rights retained; factual reference only.")
    add(material.DI,"L01","Society for Endocrinology inpatient management of cranial diabetes insipidus",
        "2018 clinical guidance; adults with established CDI only",
        "https://doi.org/10.1530/EC-18-0154", "https://pmc.ncbi.nlm.nih.gov/articles/PMC6013691/",
        "Hospital water/DDAVP continuity, volume resuscitation, serial sodium/urine monitoring and coordinated fluid replacement; not initial diagnosis, pregnancy or post-pituitary operative management.",
        "Official society page indexed guidance checked; direct society PDF returned 403. Full primary article recovered from Europe PMC PMC6013691 XML, SHA256 0295afdd0ac89d8e1a2a0d656f66da6286b18816ce8956357d5c03f180ba4025. Read Scope, Risk stratification, Organisational guidance and decompensated CDI recommendations.",
        "Society for Endocrinology/Bioscientifica source rights retained.")
    clone(material.CKD,"K01-2024", "Longitudinal measurement/risk and selected kidney-protection safety; not all CKD care.",
        "Official PDF read: PP 2.1.3-2.1.5, recommendation 2.2.1, PP 2.2.1-2.2.4, recommendation 3.6.4, PP 3.7.2-3.7.3, recommendation 3.8.1, PP 3.8.3 and 5.4.1-5.4.2.")
    clone(material.ANEMIA,"K02-2026", "Cause investigation, iron during infection, ESA hyporesponsiveness/target and transfusion tradeoffs; no drug-dose algorithm.",
        "Official 2026 PDF read: PP 1.2.1-1.2.3, 2.8, 3.7.1, Table 9, recommendation 3.3.1 and PP 4.1-4.5. 2026 final retained as the edition.")
    add(material.ASB,"L01","IDSA asymptomatic bacteriuria guideline","2019 final; US society guidance, population/context scoped",
        "https://www.idsociety.org/practice-guideline/asymptomatic-bacteriuria/",
        "https://www.idsociety.org/practice-guideline/asymptomatic-bacteriuria/",
        "ASB in nonpregnant diabetes, pregnancy, long-term catheter and mucosa-traumatizing endourological procedures; not acute UTI or antimicrobial dosing.",
        "Official IDSA full guidance read: definition and sections III, VI, XI and XIII. The page labels the guideline current; this is not a complete correction/retraction investigation.",
        "IDSA/OUP rights retained; no EAU material or EAU software-use permission claimed.")
    add(material.GS,"L01","KDIGO Gitelman syndrome consensus conference report",
        "Kidney International 2017; 91:24-33; conference consensus, not a new KDIGO graded guideline",
        "https://kdigo.org/wp-content/uploads/2017/02/KDIGO-Gitelman-conf-report.pdf",
        "https://kdigo.org/conferences/gitelman/", "Phenotype/differential, genetic confirmation and replacement/adjunct tradeoffs; not a comprehensive rare-disease bank.",
        "Official PDF and conference page read: Diagnosis and Table 2 (pp25-26), Treatment (pp28-29), Management/follow-up. Historical dated consensus retained without blanket current-treatment clearance.",
        "KDIGO/Elsevier publication and attributed components retain their rights.")
    clone(material.PD,"L01-ISPD-peritonitis-2022-corrected-launch",
        "Corrected refractory definition, improving/failing trajectory, relapse and fungal access decision; excludes Enterococcus treatment and doses.",
        "Publisher indexed primary passages read: Table 1, Refractory peritonitis and Fungal peritonitis. Direct DOI/full-text opens timed out; no full corrected-PDF hash obtained. Read official 2024 one-page corrigendum https://journals.sagepub.com/doi/pdf/10.1177/08968608241251453?download=true: >0.1 x 10^9/L replaces erroneous >100 x 10^9/L. The separate 2023 correction DOI 10.1177/08968608231166870 to Figure 8 remains outside this teaching scope.")
    clone(material.HD,"G02-haemodialysis-2019", "Dose interpretation, residual clearance, fluid tolerance, hypotension and temperature; no water-system or comprehensive emergency protocol.",
        "Primary publisher text read: Guideline 1 including incremental schedules, Guideline 4.1 and its rationale, and Appendix URR. UKKA catalogue review date 2024-07-01 is overdue; article publication status cannot clear that review obligation.")
    clone(material.BK,"L01-BK-consensus-2024-launch", "Plasma confirmation/assay limits, reduction strategy, unsupported agents and biopsy reasoning in adult recipients.",
        "Primary full text recovered through Europe PMC PMC11335089; XML SHA256 a193a7d1749e107fecc986f15454700fb0b480c8f1e1e3605aa43fc9213a89ef. Tables 5-7 and pathology/diagnostics read; direct DOI/PMC access failed. Clinical/immunological risk qualifies management.")
    clone(material.PREG,"G02-pregnancy-renal-2019", "Pregnancy measurements, aspirin, proteinuria and superimposed pre-eclampsia assessment triggers; no full obstetric management protocol.",
        "Primary publisher text read: 4.1.1-4.1.3, 4.2.2-4.2.3, 4.3.1, 4.4.5-4.4.7. UKKA review date 2024-09-01 is overdue; retained as a dated baseline, not refreshed current clinical clearance.")
    clone(material.CITRATE,"K10-2012-expansion", "Regional citrate mechanism and protocol-dependent monitoring only; no 2026 AKI treatment or liver-failure contraindication claim.",
        "Official final 2012 PDF read: section 5.3.2 rationale and Table 19, printed pp97-98. Calcium chelation, systemic calcium/acid-base handling and modality/flow-specific protocols support the new objective. No 2026 draft recommendation is adopted.")
    clone(material.CANDIDATE,"K16-2020-expansion", "Meaning check for unchanged historical cancer-remission candidate item; not a new cancer-specific waiting-time regimen.",
        "Official PDF section 11, recommendations 11.2.2, 11.2.3.2 and 11.2.4: timing/candidacy interpreted with cancer type, stage, remission and relevant teams. Primary/secondary topic identity and historical choices retained.")
    # Relationships supplied by the separate sources lane are recorded as such.
    # These snapshots do not silently re-point unchanged historical question citations.
    clone("L01-IKMG-2019-correction-20261007","L01-IKMG-evaluation-2019",
        "Correction relationship only; not new microtubular-lesion assessment or source-wide clearance.",
        "Sources-lane report docs/implementation/finish-source-currency-20261007.md: original DOI 10.1038/s41581-018-0077-4 has correction DOI 10.1038/s41581-018-0102-7, online 2018-12-19, https://www.nature.com/articles/s41581-018-0102-7. Figure 1 key is Microtubules, not Amyloid microtubules. Direct content-lane web retrieval failed; this is the supplied primary finding. The report checked RN11-T02-001, RN11-T11-001, RN11-T18-001 through -004, RN11-T22-004 and RN11-CASE-PROXIMAL: none reproduces the label, so this notice requires no key change. Do not equate all microtubules with amyloid. Comparison with the separate MGRS 2026 consensus DOI 10.1093/ckj/sfag163 remains open.")
    clone("L01-ISTH-2020-correction-20261007","L01-ISTH-TTP-diagnosis-2020",
        "Correction relationship only; no new PLASMIC scoring item or blanket clearance of TTP treatment guidance.",
        "Sources-lane report docs/implementation/finish-source-currency-20261007.md: original DOI 10.1111/jth.15006 has erratum DOI 10.1111/jth.15304, online 2021-04-20, May issue, https://onlinelibrary.wiley.com/doi/10.1111/jth.15304. PLASMIC intermediate likelihood is score 5 (5-24%), not 6; high 6-7 is unchanged. Content lane verified indexed publisher relationship, not the entire corrected original. Sources lane checked RN11-T15-001, RN11-T15-002, RN11-T15-004, RN11-T23-002 and RN11-CASE-TMA: none uses that row, so this notice requires no key change. The 2025 treatment update is separate.")
    clone("K05-2024-corrections-20261007", "K05-2024-amended",
        "Two correction relationships and existing-item overlap only; no new induction or plasma-exchange treatment claim.",
        "Sources-lane report docs/implementation/finish-source-currency-20261007.md: original DOI 10.1016/j.kint.2023.10.008 has full-guideline notices 10.1016/j.kint.2024.04.003 (July 2024: Figures 6-8/13 and PP9.3.1.9/9.3.3.1) and 10.1016/j.kint.2024.10.004 (February 2025: PP9.3.1.9 supporting ARR 6 to 16 percent; Figure12 LOWER creatinine with relapse). RN-AAV-001, RN11-T16-001 and RN-CASE-VASCULITIS cite PP9.1.1; RN11-T16-003 cites PP9.2.3.1. No key reversal follows from those notices. The source lane read the KDIGO notice and Ohio State publisher-linked record; retained PDF incorporation remains unverified. Executive-summary notice 10.1016/j.kint.2024.04.004 is separate.")
    clone("K13-2017-correction-20261007", "K13-2017",
        "Full-guideline erratum relationship and existing-item overlap only; no new treatment comparison.",
        "Sources-lane report docs/implementation/finish-source-currency-20261007.md: original DOI 10.1016/j.kisu.2017.04.001 has erratum 10.1016/j.kisu.2017.10.001, online 2017-11-17, December issue, primary notice PMC6341011. Supplementary Table S21 Di Iorio 2012/2013 comparator is calcium carbonate, not acetate; work-group conclusions unchanged. Existing K13-linked items do not compare that trial comparator, so no key change follows. Retained-file incorporation is unverified. Executive-summary notice 10.1016/j.kint.2017.10.001 is separate.")
    clone("L01-urine-eosinophils-correction-20261007", "L01-urine-eosinophils-2013",
        "Diagnostic-study correction relationship and RN11-T11-002 overlap only; not AIN treatment guidance.",
        "Sources-lane report docs/implementation/finish-source-currency-20261007.md: correction DOI 10.2215/CJN.05270418, online 2018-05-30, July issue, primary notice PMC6032594, removes denominator 566 from the sentence identifying 133 biopsy-proven AIN cases. RN11-T11-002 teaches that a negative urine-eosinophil result does not exclude AIN; it uses no cohort count or accuracy percentage. This correction does not invert its key. Indexed primary notice was read by the sources lane; no new source-wide current-treatment clearance.")
    return rows


def corrected_questions(prior):
    questions, evidence = deepcopy(prior.bundle["questions"]), []
    for item in questions:
        if item["id"] not in CORRECTIONS:
            continue
        objective, _, skill, source, reason = CORRECTIONS[item["id"]]
        before=deepcopy(item)
        item["version"] += 1
        item["key_version"] = item["version"]
        item["objective_ids"] = [objective]
        item["review"] = deepcopy(material.REVIEW)
        item["review"]["method"] = "Objective/citation metadata revision after source/meaning review. Answer, choices, rationale, family and primary/secondary topic IDs are unchanged. " + reason
        for ref in item["sources"]:
            ref["source_id"] = source
        evidence.append(dict(id=item["id"], version=item["version"], kind="question", reviewed_on=DATE,
            reviewer_kind="assistant", independent_human_review=False, skill=skill,
            source_locators=deepcopy(item["sources"]), checked_claim=reason,
            key_text=next(o["text"] for o in item["options"] if o["id"] == item["answer"]),
            objective_support=[dict(objective_id=objective, checked_claim=reason,
                source_locators=deepcopy(item["sources"]))],
            metadata_revision=dict(previous_version=before["version"],
                previous_objective_ids=before["objective_ids"], selected_objective_ids=[objective],
                answer_choices_unchanged=True, primary_secondary_topics_unchanged=True,
                source_currency_clearance=False)))
    return questions, evidence


def programme(prior, questions, cases):
    mapping=deepcopy(prior.manifest["programme_mappings"][0])
    mapping["version"]=MAPPING_VERSION
    # Contract requires evidence dates == mapping checked_on. Preserve the actual
    # 2026-10-05 official-document check; do not fabricate a fresh official fetch.
    mapping["method"]=("Original-content alignment reviewed 2026-10-07 against unchanged official curriculum/blueprint evidence checked 2026-10-05. "
        "Eleven finite depth cells and four corrected objective pins; all domains remain partial. Official documents/endorsement were not newly verified.")
    mapping["exam"]["weight_note"]=("Indicative official counts are reference weights, not a new launch quota. "
        "This release mixes 178 historical four-option items with 44 new five-option items; it cannot supply a full best-of-five examination.")
    mapping["excluded_questions"]=[p for p in mapping["excluded_questions"] if p["id"] not in CORRECTIONS]
    rows={r["id"]:r for r in mapping["alignments"]}
    def append(row, kind, items):
        for item in items:
            pin=dict(id=item["id"],version=item["version"])
            if pin not in row[kind]:
                row[kind].append(pin)
            row["objective_ids"]=sorted(set(row["objective_ids"]) | set(item["objective_ids"]))
    for _,_,alignment,prefix,case_suffix,_,note,gap in CELL_ROWS:
        row=rows[alignment]
        append(row,"questions",[q for q in material.QUESTIONS if q["id"].startswith("RN13-"+prefix+"-")])
        append(row,"cases",[c for c in material.CASES if c["id"]=="RN13-CASE-"+case_suffix])
        row["scope_note"] += " " + note
        row["gaps"]=[gap]
    for item in questions:
        if item["id"] in CORRECTIONS:
            append(rows[CORRECTIONS[item["id"]][1]],"questions",[item])
    append(rows["acute_support"],"cases",[c for c in cases if c["id"]=="RN13-CASE-CITRATE"])
    rows["acute_support"]["gaps"]=["Citrate mechanism/monitoring now has an explicit objective and case. Comprehensive acute access, circuit troubleshooting and poisoning/toxin assessment remain incomplete."]
    rows["transplant_candidates"]["gaps"]=["Cancer-remission candidate metadata is corrected. Deceased-donor allocation and the complete candidate-assessment bank remain incomplete."]
    # Share a teaching case with supported aligned objectives, never count a
    # question in two different exam domains.
    append(rows["hd_emergency"],"cases",[c for c in cases if c["id"]=="RN13-CASE-HD-ADEQUACY"])
    rows["hd_emergency"]["gaps"]=["The new case teaches symptomatic hypotension. Air embolism, haemolysis, disconnection bleeding and the full intradialytic emergency bank remain incomplete."]
    return mapping


def review(mapping, new_sources, revisions):
    result=mapping_base.review_evidence(mapping)
    result.update(pack_version=VERSION, checked_on=DATE,
        method="Assistant primary-source, single-key/four-distractor and explicit case-stage/objective review of 44 original five-option questions, 12 three-stage synthetic cases and four metadata/citation-only question revisions. No independent clinician review or educational efficacy claim.",
        inherited_review="174 questions and 38 cases from 1.1.2 remain byte-equivalent records. Four selected questions advance to version 2 with unchanged choices, keys, families and primary/secondary topics. All 47 previous source records remain byte-equivalent; earlier packs/mappings/reviews are preserved.",
        access_limits="Public official/publisher references and eligible Europe PMC full-text mirrors only. No credentials, user originals, provider calls or restricted exam bank. Some direct PDF/publisher requests failed; successful mirror/indexed passage reading is identified per source. No source-wide corrected-current clearance is inferred.",
        sources=new_sources, items=deepcopy(material.EVIDENCE)+revisions,
        source_currency_holds={
            "inherited_report":"docs/implementation/finalise-source-currency.md",
            "sources_lane_report":"docs/implementation/finish-source-currency-20261007.md",
            "all_topic_update_cells_remain_open":True,
            "parent_scoped_findings":[
                "CKD-MBD DOI 10.1016/j.kisu.2017.10.001: Supplementary Table S21 Di Iorio comparator calcium carbonate; supplied finding does not change conclusions or establish source-wide clearance.",
                "Urine eosinophils DOI 10.2215/CJN.05270418: remove denominator 566 from 133-AIN sentence; supplied finding does not invert RN11-T11-002 key.",
                "AAV 2025 correction: PP9.3.1.9 ARR 6 to 16 percent; Figure12 lower creatinine relapse risk. Existing cited PP9.1.1/9.2.3.1 are outside those supplied changes.",
                "IKMG Figure1 and ISTH PLASMIC erratum relationships are explicit new source snapshots. Sources-lane overlap checks found no reproduced error in the named existing items; no key changes. Retained corrected bytes and MGRS 2026 comparison remain separate.",
            ],
            "limit":"Parent-relayed source findings retain their stated scope; no new clearance of every item or source, no refresh of inherited metadata."},
        launch_depth={
            "cell_definition":"A bounded original four-question/five-option assessment set plus an independently written three-stage teaching case, with primary locators and explicit objective support. This is an increment definition, not a substitute for all domain gaps.",
            "cells":[dict(id=i,domain_id=d,alignment_id=a,learning_outcomes=outcomes,
                question_pins=[dict(id=q["id"],version=1) for q in material.QUESTIONS if q["id"].startswith("RN13-"+p+"-")],
                case_pin=dict(id="RN13-CASE-"+c,version=1), scope=note, remaining_gap=gap)
                for i,d,a,p,c,outcomes,note,gap in CELL_ROWS],
            "additional_citrate_case":"RN13-CASE-CITRATE", "new_objective":NEW_OBJECTIVE,
            "complete_domain_coverage":False, "exam_simulation_available":False})
    return result


def write_immutable(path, raw):
    path=Path(path)
    if path.exists() and path.read_bytes()!=raw:
        raise ValueError(f"Refusing to overwrite immutable artifact: {path}")
    path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists():
        path.write_bytes(raw)


def validate_depth_evidence(pack, evidence):
    """Check declared finite-cell and stage links, never infer clinical truth."""
    selected = {(i["id"], i["version"]): i for kind in ("questions", "cases")
                for i in pack.bundle[kind]}
    reviews = {(r["id"], r["version"]): r for r in evidence["items"]}
    for key, row in reviews.items():
        item = selected[key]
        support = row.get("objective_support", [])
        if (len(support) != len(item["objective_ids"])
                or {s["objective_id"] for s in support} != set(item["objective_ids"])):
            raise PackValidationError(f"Depth objective evidence mismatch: {key}")
        stages = {s["id"]: s for s in item.get("stages", [])}
        for claim in support:
            if not claim.get("checked_claim") or not claim.get("source_locators"):
                raise PackValidationError(f"Depth objective claim lacks evidence: {key}")
            expected = item["sources"]
            if stages:
                stage_ids = claim.get("stage_ids", [])
                if not stage_ids or not set(stage_ids).issubset(stages):
                    raise PackValidationError(f"Depth objective stage missing: {key}")
                expected = [ref for sid in stage_ids for ref in stages[sid]["sources"]]
            normalize = lambda refs: {(r["source_id"], r["locator"]) for r in refs}
            if normalize(claim["source_locators"]) != normalize(expected):
                raise PackValidationError(f"Depth objective locator differs from stage: {key}")
    mapping = pack.manifest["programme_mappings"][0]
    alignments = {r["id"]: r for r in mapping["alignments"]}
    seen_questions = set()
    for cell in evidence["launch_depth"]["cells"]:
        row = alignments[cell["alignment_id"]]
        if row["domain_id"] != cell["domain_id"] or not cell["remaining_gap"]:
            raise PackValidationError("Depth cell must preserve its domain and remaining gap")
        qs = cell["question_pins"]
        case_pin = cell["case_pin"]
        case = selected[(case_pin["id"], case_pin["version"])]
        if (len(qs) != 4 or len(cell["learning_outcomes"]) != 4
                or len(case["stages"]) != 3 or case_pin not in row["cases"]):
            raise PackValidationError("Depth cell lacks its four outcomes/questions or three-stage case")
        for pin in qs:
            key = (pin["id"], pin["version"])
            question = selected[key]
            if (key in seen_questions or pin not in row["questions"]
                    or len(question["options"]) != 5
                    or not set(question["objective_ids"]).issubset(case["objective_ids"])):
                raise PackValidationError(f"Depth assessment/case objective link missing: {key}")
            seen_questions.add(key)
    domains = {c["domain_id"] for c in evidence["launch_depth"]["cells"]}
    if domains != {d["id"] for d in mapping["domains"]}:
        raise PackValidationError("Depth increment lacks a programme domain")
    return {"cells": len(evidence["launch_depth"]["cells"]), "questions": len(seen_questions),
            "case_objective_links": sum(len(r["objective_support"]) for r in reviews.values()
                                         if r["kind"] == "case")}


def publish(evidence_dir, output=RELEASE, mapping_output=MAPPING_PATH):
    evidence_dir=Path(evidence_dir).resolve()
    if evidence_dir.is_relative_to(ROOT.resolve()):
        raise ValueError("All staging and execution evidence must be outside the worktree")
    evidence_dir.mkdir(parents=True,exist_ok=True)
    prior=validate_pack(PRIOR)
    questions,revisions=corrected_questions(prior)
    questions += deepcopy(material.QUESTIONS)
    cases=deepcopy(prior.bundle["cases"])+deepcopy(material.CASES)
    new_sources=sources(prior)
    mapping=programme(prior,questions,cases)
    topics=deepcopy(prior.bundle["topics"])
    for topic in topics:
        topic["version"]+=1
        topic["mapping"]["mapping_version"]=MAPPING_VERSION
        if topic["id"]=="T23":
            topic["objectives"].append(deepcopy(NEW_OBJECTIVE))
    evidence=review(mapping,new_sources,revisions)
    review_path=evidence_dir / "renulus-foundations-1.2.0-review.json"
    # Validate the complete candidate before any published file is written.
    with TemporaryDirectory(prefix="depth-stage-",dir=evidence_dir) as temporary:
        staged=Path(temporary)/"pack"
        result=base.publish_snapshot(staged,version=VERSION,topics=topics,
            sources=deepcopy(prior.bundle["sources"])+new_sources, questions=questions,cases=cases,
            target_topics=prior.bundle["coverage"]["target_topics"],
            minimum_questions=prior.bundle["coverage"]["minimum_questions"],
            published_on=DATE,programme_mappings=[mapping])
        pack=validate_pack(staged)
        checked_prior=[validate_pack(PRIOR.parent/v) for v in ("1.0.0","1.0.1","1.1.0","1.1.1","1.1.2")]
        for ancestor in checked_prior:
            validate_revision(pack,ancestor)
        staged_review=Path(temporary)/"review.json"
        staged_review.write_text(json.dumps(evidence,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
        validate_review_evidence(pack,staged_review,checked_prior)
        validate_depth_evidence(pack,evidence)
        blobs={Path(output)/p.name:p.read_bytes() for p in sorted(staged.iterdir())}
        blobs[Path(mapping_output)]=(json.dumps(mapping,indent=2,ensure_ascii=False)+"\n").encode("utf-8")
        blobs[review_path]=staged_review.read_bytes()
        for path,raw in blobs.items():
            if path.exists() and path.read_bytes()!=raw:
                raise ValueError(f"Refusing to overwrite immutable artifact: {path}")
        for path,raw in blobs.items():
            write_immutable(path,raw)
    return dict(result,review_path=str(review_path),new_questions=44,new_cases=12,
                metadata_revisions=list(CORRECTIONS),runtime_activation="parent-owned, not performed")


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir",required=True,type=Path)
    parser.add_argument("--output",type=Path,default=RELEASE)
    parser.add_argument("--mapping-output",type=Path,default=MAPPING_PATH)
    args=parser.parse_args()
    print(json.dumps(publish(args.evidence_dir,args.output,args.mapping_output),indent=2))
