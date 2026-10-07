# SPDX-License-Identifier: MIT
"""Publish original, partial ESENeph alignment without rewriting the broad bank.

The curated pins below were checked against the actual item stems, keys and
case stages. Numbered IDs are expanded for authoring only; selection at runtime
uses the resulting immutable explicit pins, never a topic-tag inference.
"""

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runtime"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import author_foundations as base
from renulus.content.validation import validate_pack
from revision_checks import validate_revision

DATE = "2026-10-05"
VERSION = "1.1.1"
PRIOR = ROOT / "content/packs/renulus-foundations/1.1.0"
CURRICULUM = "C01-renal-curriculum-2022"
BLUEPRINT = "C01-linked-blueprint-20261005"
HUB = "C01-esen-eph-hub-20261005"


def qids(prefix, *numbers):
    return [f"{prefix}-{n:03}" for n in numbers]


def objectives(*topics):
    return [f"{t}.O{n:02}" for t, numbers in topics for n in numbers]


def pins(ids):
    return [{"id": id, "version": 1} for id in sorted(ids)]


def alignment(id, domain, label, pages, objective_ids=(), questions=(), cases=(), *, note, gaps, section="3.5"):
    supporting = domain is None
    return {
        "id": id, "domain_id": domain, "label": label,
        "relation": "curriculum_support" if supporting else "exam_domain",
        "status": "supporting" if supporting else "partial" if questions or cases else "gap",
        "objective_ids": sorted(objective_ids), "questions": pins(questions), "cases": pins(cases),
        "curriculum_reference": {"source_id": CURRICULUM, "section": section, "pages": list(pages)},
        "scope_note": note, "gaps": list(gaps),
    }


def programme():
    # Original display labels; counts transcribed from page 1 of the exact
    # blueprint linked by the official hub. The PDF itself has no revision date.
    domain_rows = [
        ("glomerular_interstitial", "Glomerular and interstitial disorders", 30),
        ("acute_biochemistry", "Acute injury, acute support, fluid and biochemical disorders", 26),
        ("ckd_urine", "CKD and urinary abnormalities", 24),
        ("bone_anemia", "Bone and anemia complications", 12),
        ("cardiovascular_diabetes", "Cardiovascular, blood pressure and diabetes care", 20),
        ("urology", "Stones, urinary infection and obstruction", 14),
        ("inherited_rare", "Inherited and uncommon disorders", 14),
        ("peritoneal_dialysis", "Peritoneal dialysis", 8),
        ("hemodialysis", "Hemodialysis", 14),
        ("transplantation", "Kidney transplantation", 14),
        ("other", "Other clinical and care domains", 24),
    ]
    rows = [
        alignment("glomerular_diagnosis", "glomerular_interstitial", "Urine, serology and tissue interpretation", [30],
            objectives(("T10", [1]), ("T02", [2]), ("T22", [1, 2])),
            qids("RN-GN", 1, 2, 4) + qids("RN11-T10", 2) + qids("RN11-T02", 2) + qids("RN11-T22", 1, 3, 4),
            ["RN-CASE-NEPHROTIC", "RN-CASE-LUPUS"],
            note="Diagnostic decisions and sampling limitations; the pathology items use text, not diagnostic images.",
            gaps=["No reviewed IgA/IgAV or anti-GBM-specific assessment; no image-based histology assessment."]),
        alignment("glomerular_management", "glomerular_interstitial", "Disease response and competing treatment risks", [30],
            objectives(("T10", [1, 2]), ("T27", [2])), qids("RN-GN", 3) + qids("RN11-T10", 1, 3, 4) + qids("RN11-T27", 4),
            ["RN11-CASE-NEPHROTIC-RISK"],
            note="FSGS, membranous response, infection-related reasoning and thrombosis/bleeding tradeoffs.",
            gaps=["No complete disease-by-disease induction, maintenance, relapse or drug-monitoring bank."]),
        alignment("systemic_immune", "glomerular_interstitial", "Systemic inflammation and microvascular injury", [30],
            objectives(("T16", [1, 2]), ("T15", [1, 2])), ["RN-AAV-001", "RN-LN-001"] + qids("RN11-T16", 1, 2, 3, 4) + qids("RN11-T15", 1, 2, 3, 4),
            ["RN-CASE-VASCULITIS", "RN-CASE-LUPUS", "RN11-CASE-LUPUS-REASSESSMENT", "RN11-CASE-TMA"],
            note="Lupus, AAV and TMA recognition/etiology are selected contexts within the curriculum's immune/systemic scope.",
            gaps=["No comprehensive complement-disease treatment or anti-GBM pathway."]),
        alignment("tubular_interstitial", "glomerular_interstitial", "Tubular localization and interstitial-injury reasoning", [28, 30],
            objectives(("T11", [1, 2])), qids("RN11-T11", 1, 2, 3, 4),
            ["RN11-CASE-PROXIMAL", "RN11-CASE-STONE-ACID"],
            note="Proximal losses, drug-related glycosuria, AIN test limits and acidification interpretation; these are not four AIN treatment items.",
            gaps=["No comprehensive interstitial treatment course or inherited salt-wasting assessment."]),
        alignment("paraprotein", "glomerular_interstitial", "Nonalbumin proteins and renal deposition workup", [30, 32, 33],
            objectives(("T18", [1, 2]), ("T02", [1])), qids("RN11-T18", 1, 2, 3, 4) + qids("RN11-T02", 1),
            ["RN11-CASE-PROXIMAL"],
            note="MGRS and amyloid investigation; assignment is an assistant interpretation of the immune/systemic curriculum context.",
            gaps=["No comprehensive cancer-treatment toxicity, myeloma or clone-directed therapy assessment."]),
        alignment("apheresis", "glomerular_interstitial", "Plasma exchange as a distinct mechanism", [30],
            objectives(("T23", [2])), ["RN11-T23-002"], ["RN11-CASE-TMA"],
            note="A TTP plasma-exchange distinction; the case prompts etiologic and urgent specialist reasoning.",
            gaps=["No complete disease-specific plasma-exchange indication or complication matrix."]),
        alignment("aki_staging", "acute_biochemistry", "Acute injury definitions and staging", [28, 29],
            objectives(("T06", [1])), qids("RN-AKI", 1, 2, 3) + qids("RN11-T06", 1, 3), ["RN-CASE-AKI"],
            note="Creatinine/urine-output definitions and limits of an unknown baseline.",
            gaps=["No exhaustive etiologic AKI differential or all post-AKI outcomes."]),
        alignment("aki_management", "acute_biochemistry", "Cause review, recovery and medicine-related AKI", [29],
            objectives(("T06", [2]), ("T19", [1])), qids("RN-AKI", 4, 5, 6) + qids("RN11-T06", 2, 4) + ["RN11-T19-001"],
            ["RN-CASE-AKI", "RN11-CASE-OBSTRUCTION"],
            note="Diuretics, low-dose dopamine, fractional excretion limits, follow-up and hemodynamic drug interactions.",
            gaps=["No complete shock/sepsis resuscitation, hepatorenal or tumor-lysis bank."]),
        alignment("changing_filtration", "acute_biochemistry", "Measurements during changing kidney function", [29],
            objectives(("T01", [1])), ["RN11-T01-003"], ["RN11-CASE-CARDIORENAL"],
            note="Non-steady-state estimates and acute medication decisions.",
            gaps=["No measured-clearance or kinetic-estimation curriculum."]),
        alignment("acute_support", "acute_biochemistry", "Acute support delivery and cessation", [29, 34],
            objectives(("T07", [1, 2])), qids("RN11-T07", 1, 2, 3, 4),
            ["RN11-CASE-CRRT-DELIVERY"],
            note="Circulatory tolerance, dose arithmetic, downtime and stopping support. The citrate question's apheresis-objective link is not counted as direct alignment.",
            gaps=["No comprehensive acute-access procedure, circuit troubleshooting or poisoning/toxin assessment; citrate item needs an objective-metadata revision before formal inclusion."]),
        alignment("water_sodium", "acute_biochemistry", "Water, sodium and correction reasoning", [28],
            objectives(("T03", [1, 2])), qids("RN-NA", 1, 2, 3) + qids("RN11-T03", 1, 2, 3, 4), ["RN-CASE-HYPONA"],
            note="Tonicity, urine dilution, effective volume and monitored correction.",
            gaps=["No reviewed hypernatremia or diabetes-insipidus assessment."]),
        alignment("potassium_acidosis", "acute_biochemistry", "Potassium and metabolic acid-base patterns", [28],
            objectives(("T04", [1, 2])), qids("RN-K", 1, 2, 3, 4) + qids("RN-AB", 1, 2) + qids("RN11-T04", 1, 2, 3, 4),
            ["RN-CASE-HYPERK", "RN-CASE-ACIDOSIS", "RN11-CASE-STONE-ACID"],
            note="Hyperkalemia, redistribution/removal, CKD alkali monitoring and selected gap/RTA interpretation.",
            gaps=["No systematic hypokalemia, metabolic alkalosis or mixed respiratory/acid-base bank."]),
        alignment("ckd_classification", "ckd_urine", "Chronicity, filtration markers and urine quantification", [29],
            objectives(("T08", [1]), ("T01", [1, 2]), ("T02", [1])), qids("RN-CKD", 1, 2, 3, 4) + qids("RN11-T08", 1, 4) + qids("RN11-T01", 1, 2, 4) + qids("RN11-T02", 3, 4),
            ["RN-CASE-CKD", "RN11-CASE-HOME-BP"],
            note="Marker/measurement limitations support CKD decisions; they do not establish every foundational science objective.",
            gaps=["No complete persistent-hematuria workup or structural CKD differential."]),
        alignment("ckd_progression", "ckd_urine", "Progression risk and longitudinal protection", [29, 30],
            objectives(("T08", [2])), qids("RN-CKD", 5, 6) + qids("RN11-T08", 2, 3), ["RN-CASE-CKD", "RN11-CASE-HOME-BP"],
            note="Risk-tool applicability, SGLT2 protection and change evaluation.",
            gaps=["No full cause-specific longitudinal CKD management or complications matrix."]),
        alignment("advanced_ckd", "ckd_urine", "Preparing for replacement therapy", [29, 30],
            objectives(("T20", [1, 2])), qids("RN-DIAL", 1, 2, 3), ["RN-CASE-DIALYSIS"],
            note="Clinical initiation and anticipatory planning; not proof of maintenance dialysis competence.",
            gaps=["No complete education/modality/access selection bank."]),
        alignment("bone", "bone_anemia", "Mineral and bone trend interpretation", [29, 30],
            objectives(("T05", [1, 2])), qids("RN-MBD", 1, 2, 3) + qids("RN11-T05", 1, 2, 3, 4), ["RN-CASE-MBD"],
            note="PTH/calcium/phosphate, binder exposure and low-turnover concerns.",
            gaps=["No comprehensive fracture, osteoporosis or calciphylaxis assessment."]),
        alignment("anemia", "bone_anemia", "Anemia investigation and ESA goals", [29, 30],
            objectives(("T08", [3, 4])), qids("RN-ANEMIA", 1, 2),
            note="Two exact reviewed items; no anemia teaching case is claimed.",
            gaps=["No comprehensive iron-treatment, ESA hyporesponse, transfusion or HIF-PHI bank."]),
        alignment("blood_pressure", "cardiovascular_diabetes", "Blood pressure validity and tolerance", [32],
            objectives(("T09", [1, 2])), qids("RN-BP", 1, 2) + qids("RN11-T09", 1, 2, 3, 4), ["RN11-CASE-HOME-BP", "RN-CASE-DIABETES"],
            note="Measurement settings, masked patterns and tolerated treatment.",
            gaps=["No complete secondary-hypertension, renovascular or emergency-treatment bank."]),
        alignment("diabetes", "cardiovascular_diabetes", "Diabetes protection and treatment interpretation", [32],
            objectives(("T14", [1, 2])), qids("RN-DM", 1, 2, 3) + qids("RN11-T14", 1, 2, 3, 4), ["RN-CASE-DIABETES", "RN11-CASE-CARDIORENAL"],
            note="Selected kidney-protective mechanisms, metformin, fasting and HbA1c limitations.",
            gaps=["No complete insulin adjustment, pancreatic transplantation or diabetes complication bank."]),
        alignment("cardiorenal", "cardiovascular_diabetes", "Cardiac/kidney risk and shared care", [32],
            objectives(("T27", [1, 2])), qids("RN11-T27", 1, 3), ["RN11-CASE-CARDIORENAL"],
            note="Albuminuria risk and medication benefit versus manageable potassium.",
            gaps=["No comprehensive heart-failure, ischemia or dialysis cardiovascular assessment."]),
        alignment("obstruction", "urology", "An infected obstructed system", [31],
            objectives(("T13", [1])), ["RN11-T13-001"], ["RN11-CASE-OBSTRUCTION"],
            note="Urgent source-control reasoning.", gaps=["No complete chronic obstruction, congenital tract or imaging pathway."]),
        alignment("stones", "urology", "Stone composition and metabolic prevention", [31],
            objectives(("T13", [2])), qids("RN11-T13", 2, 3, 4), ["RN11-CASE-STONE-ACID"],
            note="Selected calcium, oxalate, citrate and urine-pH mechanisms.", gaps=["No complete stone-procedure or metabolic differential bank."]),
        alignment("urinary_infection_gap", "urology", "Routine and recurrent urinary infection", [31],
            note="The obstructed sepsis case does not cover uncomplicated/recurrent UTI.", gaps=["No dedicated reviewed recurrent UTI assessment or teaching case."]),
        alignment("adpkd", "inherited_rare", "ADPKD progression and family considerations", [30, 31],
            objectives(("T12", [1, 2])), qids("RN-PKD", 1, 2) + qids("RN11-T12", 1, 2, 3, 4), ["RN-CASE-ADPKD"],
            note="ADPKD imaging/progression, family history and treatment monitoring.", gaps=["No complete cascade-testing or genetic-variant interpretation bank."]),
        alignment("other_inherited_gap", "inherited_rare", "Genetic and metabolic disease beyond ADPKD", [28, 31],
            note="A cystic-topic tag does not establish the wider rare/genetic curriculum.", gaps=["No dedicated Alport, Fabry, cystinosis, primary hyperoxaluria or inherited salt-wasting bank."]),
        alignment("pd_clearance", "peritoneal_dialysis", "PD transport, residual function and fluid removal", [34],
            objectives(("T20", [2]), ("T23", [1])), qids("RN11-T20", 2, 4), ["RN11-CASE-PD-VOLUME"],
            note="Two PD-specific questions plus a volume/clearance case.", gaps=["No complete PD prescription or ultrafiltration-failure algorithm."]),
        alignment("pd_infection_gap", "peritoneal_dialysis", "PD infection and catheter complications", [34],
            note="General infection teaching is not PD-peritonitis coverage.", gaps=["No reviewed peritonitis, exit-site/tunnel infection or PD access-failure assessment."]),
        alignment("hd_clearance", "hemodialysis", "HD dose, modalities and overall adequacy", [34],
            objectives(("T23", [1])), qids("RN11-T23", 1, 3),
            note="Diffusion/convection and membrane differences; no HD-focused staged case is claimed. Existing urea/adequacy questions point to a dialysis-initiation objective and are excluded from formal alignment.",
            gaps=["No complete maintenance/home-HD prescription, water-quality or complication case bank; two adequacy items need objective-metadata revisions."]),
        alignment("hd_emergency", "hemodialysis", "Urgent removal after a missed HD treatment", [34],
            objectives(("T20", [1])), ["RN-DIAL-004"],
            note="One maintenance-HD emergency item; general hyperkalemia items remain in the acute domain.", gaps=["No complete intradialytic emergency bank."]),
        alignment("hd_access_gap", "hemodialysis", "HD access and unit operation", [34, 35],
            note="Preparing for access does not establish catheter insertion or access troubleshooting.", gaps=["No access infection, thrombosis, aneurysm, catheter insertion or water-system assessment."]),
        alignment("transplant_candidates", "transplantation", "Candidate and donor eligibility", [34, 35],
            objectives(("T21", [1, 2])), qids("RN-TX", 1, 2, 3) + qids("RN11-T21", 1, 3),
            ["RN-CASE-TRANSPLANT", "RN11-CASE-DONOR-GOALS"],
            note="Preemptive assessment, candidate comorbidity and selected donor measurements. The cancer-remission item has an infection-objective link and is excluded from direct alignment.", gaps=["No deceased-donor selection/allocation or complete candidate-assessment bank; cancer item needs an objective-metadata revision."]),
        alignment("transplant_prevention", "transplantation", "Sensitization and pretransplant infection planning", [33, 34],
            objectives(("T21", [2]), ("T17", [1, 2])), ["RN-TX-004", "RN11-T21-002", "RN11-T17-001", "RN11-T17-003"], ["RN-CASE-TRANSPLANT"],
            note="HLA-antibody reassessment and infection/vaccine timing before transplant.", gaps=["No posttransplant virology, prophylaxis or immunosuppressant-level assessment."]),
        alignment("donor_choice", "transplantation", "Voluntary donation and future pregnancy", [35],
            objectives(("T21", [2]), ("T24", [1])), ["RN11-T21-004", "RN11-T24-003"], ["RN11-CASE-DONOR-GOALS"],
            note="Autonomy and selected donor counseling, not a national legal qualification.", gaps=["No complete donor psychosocial or jurisdiction-specific legal assessment."]),
        alignment("transplant_aftercare_gap", "transplantation", "Transplant dysfunction and longer-term care", [34],
            note="Candidate questions cannot stand in for recipient aftercare.", gaps=["No reviewed rejection, BK/CMV, immunosuppressant toxicity, graft vascular or obstructive complication bank."]),
        alignment("prescribing", "other", "Kidney-aware prescribing and transitions", [29, 32],
            objectives(("T19", [1, 2]), ("T27", [1])), qids("RN-DRUG", 1, 2) + qids("RN11-T19", 2, 3, 4) + ["RN11-T27-002"],
            ["RN-CASE-AKI", "RN-CASE-ACIDOSIS", "RN-CASE-ADPKD", "RN11-CASE-CARDIORENAL", "RN11-CASE-NEPHROTIC-RISK"],
            note="Dose metrics, non-GFR influences, combinations, OTC exposures and restart responsibility.", gaps=["No complete pharmacokinetic, drug-level or dialysis-removal bank."]),
        alignment("infection", "other", "Infection assessment around immune treatment", [33],
            objectives(("T17", [1, 2])), ["RN11-T17-002"], ["RN-CASE-TRANSPLANT", "RN11-CASE-LUPUS-REASSESSMENT", "RN11-CASE-OBSTRUCTION"],
            note="HBV risk and selected case infection reasoning; pretransplant vaccine items are counted only in the transplant domain.",
            gaps=["No complete infection-prevention, opportunistic infection or dialysis virology bank."]),
        alignment("pregnancy", "other", "Kidney assessment and tissue decisions in pregnancy", [33, 34],
            objectives(("T24", [1, 2]), ("T22", [2]), ("T27", [2])), qids("RN11-T24", 1, 2) + ["RN11-T22-002"], ["RN11-CASE-PREGNANCY"],
            note="Creatinine/eGFR limits, superimposed preeclampsia and selected biopsy decisions.", gaps=["No complete prepregnancy, transplant pregnancy, pregnancy immunosuppression or HELLP assessment."]),
        alignment("nutrition", "other", "Nutritional context and restriction tradeoffs", [30],
            objectives(("T25", [1, 2])), ["RN-NUTR-001"] + qids("RN11-T25", 1, 2, 3, 4),
            ["RN-CASE-SUPPORTIVE", "RN11-CASE-PD-VOLUME", "RN11-CASE-CRRT-DELIVERY"],
            note="Adult, frailty, pediatric growth and acute-support nutrition contexts.", gaps=["No complete dialysis diet, rehabilitation or nutritional-assessment bank."]),
        alignment("supportive_care", "other", "Conservative care and changing goals", [33],
            objectives(("T26", [1]), ("T24", [2])), ["RN-CARE-001", "RN11-T26-002", "RN11-T24-004"], ["RN-CASE-SUPPORTIVE"],
            note="Active conservative care, frailty and revisiting preferences.", gaps=["No complete symptom-prescribing or dialysis-withdrawal assessment."]),
        alignment("procedure_decisions", "other", "Procedure indications and limitations", [35],
            objectives(("T22", [1, 2])), ["RN11-T22-002"], ["RN-CASE-NEPHROTIC", "RN-CASE-LUPUS", "RN11-CASE-PREGNANCY"],
            section="3.6", note="Selected biopsy decisions; a second link within Other does not double-count its question. Text learning cannot certify hands-on procedure competence.",
            gaps=["No technical catheter insertion, asepsis, consent or procedural-complication assessment."]),
        alignment("sexual_health_gap", "other", "Fertility, contraception and sexual health", [33],
            note="Pregnancy and donor counseling do not establish sexual-health coverage.", gaps=["No dedicated reviewed contraception, fertility or sexual dysfunction assessment/case."]),
        alignment("transition_gap", "other", "Transition to adult kidney care", [33],
            note="A pediatric nutrition item does not establish adolescent transition coverage.", gaps=["No reviewed transition-care or young-adult transplant adherence assessment/case."]),
        alignment("end_of_life_gap", "other", "Care during dying and dialysis withdrawal", [33],
            note="A conservative-care definition and goals discussion are not a terminal-care bank.", gaps=["No dedicated terminal symptom, withdrawal or end-of-life medication assessment/case."]),
        alignment("critical_appraisal_support", None, "Evidence interpretation for learning", [14],
            objectives(("T26", [2])), ["RN-EVID-001"] + qids("RN11-T26", 1, 3, 4),
            section="3.2", note="Generic curriculum research/critical-appraisal support; no exam-domain assignment is inferred for these four questions.",
            gaps=["Not counted as ESENeph blueprint coverage."]),
    ]
    rights = "Public reference metadata only. No open redistribution licence verified; source PDFs, prose, figures and official examination questions are not included."
    return {
        "id": "esen_eph", "version": DATE, "title": "ESENeph preparation — partial curriculum alignment",
        "checked_on": DATE, "status": "partial",
        "method": "Assistant read of the exact hub-linked blueprint, 2022 content-of-learning/procedure/generic references, original objectives, question stems/keys and case stages. Explicit pinned links record supported scope and missing depth; this is Renulus's interpretation.",
        "reviewer_kind": "assistant", "independent_human_review": False,
        "official_endorsement": False, "exam_simulation_available": False,
        "excluded_questions": [
            {"id": id, "version": 1, "category": "curriculum_support",
             "reason": "Generic research/critical-appraisal support; no supported blueprint-domain assignment."}
            for id in ["RN-EVID-001", "RN11-T26-001", "RN11-T26-003", "RN11-T26-004"]
        ] + [
            {"id": id, "version": 1, "category": "objective_mismatch", "reason": reason}
            for id, reason in [
                ("RN11-T23-004", "Citrate anticoagulation mechanism is linked to an apheresis-indication objective."),
                ("RN11-T20-001", "Overall HD adequacy is linked to a dialysis-initiation objective."),
                ("RN11-T20-003", "Urea reduction arithmetic is linked to a dialysis-initiation objective."),
                ("RN11-T17-004", "Cancer remission in candidate assessment is linked to an infection-risk objective."),
            ]
        ],
        "evidence": [
            {"id": HUB, "register_id": "C01", "title": "European Specialty Examination in Nephrology",
             "edition": "Live official hub checked 2026-10-05; not an independently dated blueprint edition", "kind": "exam_format",
             "url": "https://www.thefederation.uk/examinations/european-specialty-examination-nephrology", "checked_on": DATE, "rights_note": rights},
            {"id": BLUEPRINT, "register_id": "C01", "title": "SCE in Nephrology Blueprint",
             "edition": "Undated two-page PDF currently linked by the ESENeph hub; historical SCE title retained", "kind": "blueprint",
             "url": "https://www.thefederation.uk/sites/default/files/uploads/Specialty%20Certificate%20Examination%20in%20Nephrology%20blueprint.pdf",
             "sha256": "20e0d68613b660c9df1669a0958ec594e5cc317ea4f6e261ad9e994154482d9c", "page_count": 2, "checked_on": DATE, "rights_note": rights},
            {"id": CURRICULUM, "register_id": "C01", "title": "Renal Medicine 2022 curriculum",
             "edition": "2022; implemented August 2022; official hub-linked 58-page PDF checked 2026-10-05", "kind": "curriculum",
             "url": "https://www.thefederation.uk/sites/default/files/Renal%2520Medicine%25202022%2520Curriculum%2520FINAL.pdf",
             "sha256": "1723591e724a1d27e40e80648c5c2854a2ac3dad211dcbc7fd077d02b9d74d16", "page_count": 58, "checked_on": DATE,
             "rights_note": rights + " The UK training curriculum is a reference, not every EU doctor's national programme."},
        ],
        "exam": {"source_id": HUB, "papers": 2, "questions_per_paper": 100, "total_questions": 200,
                 "minutes_per_paper": 180, "options_per_question": 5,
                 "weight_note": "Page 1 gives indicative counts across both papers; actual composition may vary. This pack has four-choice SBAs and cannot reproduce a best-of-five full exam."},
        "domains": [{"id": id, "label": label, "indicative_questions": count,
                     "source_id": BLUEPRINT, "source_page": 1} for id, label, count in domain_rows],
        "alignments": rows,
    }


def write_evidence(path, body):
    target = Path(path)
    raw = (json.dumps(body, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    if target.exists() and target.read_bytes() != raw:
        raise SystemExit(f"Refusing to change published mapping evidence: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(raw)


def review_evidence(mapping):
    return {
        "schema_version": 1, "pack_id": "renulus-foundations", "pack_version": VERSION,
        "checked_on": DATE,
        "method": "Assistant formal curriculum/item alignment review. Existing clinical source/key reviews are inherited without a new clinical-source currency claim.",
        "independent_human_review": False,
        "inherited_review": "All 160 questions, 26 cases and their exact clinical source/key snapshots are unchanged from 1.1.0. That release and its predecessor review evidence remain unchanged.",
        "access_limits": "Only the public official hub-linked curriculum and blueprint were read for mapping. No primary source originals, official sample questions, exam bank or restricted teaching content is distributed. No independent clinician review.",
        "sources": [], "items": [],
        "programme_mapping": {
            "id": mapping["id"], "version": mapping["version"], "checked_on": mapping["checked_on"],
            "evidence_sha256": {s["id"]: s["sha256"] for s in mapping["evidence"] if "sha256" in s},
            "excluded_question_ids": sorted(p["id"] for p in mapping["excluded_questions"]),
        },
    }


def publish(path, mapping_path=None, review_path=None):
    prior = validate_pack(PRIOR)
    mapping = programme()
    topics = deepcopy(prior.bundle["topics"])
    for topic in topics:
        topic["version"] += 1
        topic["mapping"].update(esen_eph="partially_mapped", mapping_version=DATE)
    result = base.publish_snapshot(
        Path(path), version=VERSION, topics=topics, sources=prior.bundle["sources"],
        cases=prior.bundle["cases"], questions=prior.bundle["questions"],
        target_topics=prior.bundle["coverage"]["target_topics"],
        minimum_questions=prior.bundle["coverage"]["minimum_questions"],
        published_on=DATE, programme_mappings=[mapping],
    )
    validate_revision(validate_pack(path), prior)
    if mapping_path is not None:
        write_evidence(mapping_path, mapping)
    if review_path is not None:
        write_evidence(review_path, review_evidence(mapping))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "content/packs/renulus-foundations" / VERSION)
    parser.add_argument("--mapping-output", type=Path, default=ROOT / "content/mappings/esen-eph-2026-10-05.json")
    parser.add_argument("--review-output", type=Path, default=ROOT / "content/reviews/renulus-foundations-1.1.1.json")
    args = parser.parse_args()
    print(json.dumps(publish(args.output, args.mapping_output, args.review_output), indent=2))
