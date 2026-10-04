# SPDX-License-Identifier: MIT
"""Authoring source for original CC BY 4.0 content, not a model-generated bank.

Publication is reproducible and refuses to overwrite a differing published pack.
Medical facts were checked by the assistant against the locators in sources.json.
No primary-source prose, figures, tables or restricted questions are reproduced.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runtime"))
from renulus.content.validation import coverage_for, validate_pack

DATE = "2026-10-04"
PACK = ROOT / "content/packs/renulus-foundations/1.0.0"
REVIEW = {
    "status": "assistant_reviewed", "reviewer": "Renulus content lane assistant",
    "reviewer_kind": "assistant", "reviewed_on": DATE,
    "method": "Primary public recommendation/section check; single-key and distractor review; synthetic scenario review.",
    "source_key_checked": True, "independent_human_review": False,
}

# Stable IDs adopted from reference labels; descriptions and objectives are original.
TOPIC_ROWS = [
    ("T01", "Foundations of kidney science", "Relate filtration and tubular transport to clinical measurements.", "Explain how muscle mass and non-GFR determinants affect creatinine."),
    ("T02", "Clinical assessment and diagnostics", "Combine chronology, urine findings and imaging to frame a kidney problem.", "Choose a confirmatory test and explain what its result can and cannot establish."),
    ("T03", "Sodium, water and volume", "Classify hyponatremia using tonicity and urine measurements.", "Prioritize symptoms and control correction while treating a water or volume disorder."),
    ("T04", "Potassium and acid-base", "Separate cardiac protection, potassium redistribution and potassium removal.", "Evaluate CKD acidosis and monitor the effects of its treatment."),
    ("T05", "Mineral metabolism and bone", "Interpret calcium, phosphate and PTH trends together.", "Choose a CKD-MBD intervention with attention to dialysis status and treatment harms."),
    ("T06", "Acute kidney injury and acute kidney disease", "Recognize and stage AKI from creatinine and urine-output changes.", "Treat reversible causes, recognize urgent KRT needs and plan recovery follow-up."),
    ("T07", "Critical care nephrology", "Identify kidney-related disturbances requiring immediate monitored treatment.", "Select kidney support in the context of circulation, organ failure and treatment goals."),
    ("T08", "Chronic kidney disease", "Establish CKD chronicity and classify cause, GFR and albuminuria.", "Use progression risk and kidney-protective therapy to plan longitudinal care."),
    ("T09", "Hypertension and vascular kidney disease", "Interpret standardized and out-of-office blood pressure measurements.", "Individualize blood pressure treatment using symptoms, tolerance and comorbidity."),
    ("T10", "Glomerular diseases", "Integrate nephrotic or nephritic findings, serology and biopsy indications.", "Distinguish disease-specific treatment from supportive care and prevent treatment harms."),
    ("T11", "Tubular and interstitial disease", "Use urine and electrolyte findings to localize a tubular defect.", "Evaluate drug-related interstitial injury and assess alternatives to continued exposure."),
    ("T12", "Cystic and inherited kidney disease", "Assess ADPKD progression risk and discuss familial testing implications.", "Explain eligibility, adverse effects and monitoring of a disease-modifying treatment."),
    ("T13", "Stones and obstruction", "Recognize an obstructed or infected urinary tract requiring urgent evaluation.", "Connect stone composition and metabolic assessment to recurrence prevention."),
    ("T14", "Diabetes and metabolic kidney disease", "Select kidney-protective and glucose-lowering treatments within kidney-function limits.", "Monitor treatment effects and adjust therapy during acute illness or fasting."),
    ("T15", "Thrombotic microangiopathy and complement", "Integrate hemolysis, platelet count and kidney injury to recognize TMA.", "Distinguish urgent diagnostic pathways and explain when complement evaluation is relevant."),
    ("T16", "Kidney disease in systemic illness", "Recognize organ-threatening vasculitis and lupus-related kidney disease.", "Balance timely tissue diagnosis with the urgency of treating systemic disease."),
    ("T17", "Infection in nephrology", "Assess infection risks before kidney replacement or immunosuppression.", "Explain prevention, vaccination and evidence-based evaluation of a suspected infection."),
    ("T18", "Onconephrology and paraproteins", "Connect malignancy, monoclonal proteins and cancer treatment to kidney injury.", "Select appropriate hematologic and kidney investigations without attributing every AKI to cancer."),
    ("T19", "Medicines and nephrotoxicity", "Review kidney-function-dependent benefits, risks and interactions of prescribed drugs.", "Document monitoring and a restart plan when temporarily interrupting treatment."),
    ("T20", "Dialysis and kidney failure therapies", "Recognize clinical indications for dialysis without relying on a GFR cutoff alone.", "Plan modality, access and ongoing dialysis care with the person's preferences."),
    ("T21", "Kidney transplantation", "Plan timely transplant assessment and discuss preemptive transplantation.", "Assess candidate risks and infection-prevention needs before transplantation."),
    ("T22", "Procedures and interventional nephrology", "Explain the diagnostic value and limitations of kidney biopsy.", "Plan an intervention with attention to bleeding, infection and access complications."),
    ("T23", "Extracorporeal therapies and apheresis", "Explain solute clearance, fluid removal and modality constraints.", "Evaluate an apheresis indication against disease-specific evidence and treatment risk."),
    ("T24", "Life-course and special populations", "Adapt kidney assessment to age, pregnancy, frailty and developmental context.", "Explain population-specific treatment tradeoffs and transitions in care."),
    ("T25", "Nutrition, prevention and rehabilitation", "Tailor nutrition and activity advice to CKD stage and nutritional stability.", "Balance dietary restriction with function, growth and malnutrition risk."),
    ("T26", "Supportive care, ethics and evidence", "Discuss conservative kidney care and advance care planning using the person's goals.", "Distinguish a graded recommendation from a practice point and identify evidence limits."),
    ("T27", "Kidney interfaces with other specialties", "Relate kidney findings to cardiac, endocrine and intensive-care problems.", "Coordinate a shared care plan and specify which uncertainty requires another specialty."),
]
TOPICS = [{"id": t, "version": 1, "label": label,
           "description": f"General nephrology learning in {label.lower()}. Item coverage is reported separately.",
           "objectives": [{"id": f"{t}.O01", "text": a}, {"id": f"{t}.O02", "text": b}],
           "mapping": {"general_nephrology": True, "esen_eph": "not_formally_mapped"},
           "license": "CC-BY-4.0"} for t, label, a, b in TOPIC_ROWS]
TOPICS[7]["objectives"].extend([
    {"id": "T08.O03", "text": "Investigate anemia in CKD rather than assuming erythropoietin deficiency."},
    {"id": "T08.O04", "text": "Individualize ESA treatment goals while avoiding excessive hemoglobin targets."},
])

CKD, AKI, GD, TX, MBD, PKD, AAV, LN, DM, BP, K, NA, ANEMIA = (
    "K01-2024", "K10-2012", "K08-2021-remaining", "K16-2020",
    "K13-2017", "K03-2025", "K05-2024-amended", "K06-2024",
    "K09-2022", "K11-2021", "G02-hyperkalemia-2023",
    "G01-hyponatremia-2014", "K02-2026",
)

SOURCE_ROWS = [
    (CKD, "K01", "KDIGO CKD evaluation and management", "2024",
     "https://kdigo.org/wp-content/uploads/2026/04/KDIGO-2024-CKD-Guideline.pdf",
     "https://kdigo.org/guidelines/ckd-evaluation-and-management/",
     "Adult CKD classification, kidney protection, acidosis, drug stewardship and KRT planning."),
    (AKI, "K10", "KDIGO acute kidney injury", "2012 final",
     "https://kdigo.org/wp-content/uploads/2016/10/KDIGO-2012-AKI-Guideline-English.pdf",
     "https://kdigo.org/guidelines/acute-kidney-injury/",
     "Dated baseline: AKI definition/staging, diuretics, dopamine, urgent KRT and three-month follow-up. 2026 draft is not substituted."),
    (GD, "K08", "KDIGO glomerular diseases: remaining scope", "2021; 2024 chapter-update combined file",
     "https://kdigo.org/wp-content/uploads/2024/05/KDIGO-2021-Glomerular-Diseases-Guideline_English_2024-Chapter-Updates.pdf",
     "https://kdigo.org/guidelines/gd/",
     "Only chapters 1, 3, 5 and 6 used. Replaced IgAN, pediatric nephrotic, ANCA and lupus scope is excluded."),
    (TX, "K16", "KDIGO kidney transplant candidate", "2020",
     "https://kdigo.org/wp-content/uploads/2026/04/KDIGO-2020-Transplant-Candidate-Guideline.pdf",
     "https://kdigo.org/guidelines/transplant-candidate/",
     "Candidate referral, living-donor preemptive transplantation, obesity assessment and vaccination; no recipient drug regimen."),
    (MBD, "K13", "KDIGO CKD mineral and bone disorder", "2017 update",
     "https://kdigo.org/wp-content/uploads/2026/04/KDIGO-2017-CKD-MBD-Guideline.pdf",
     "https://kdigo.org/guidelines/ckd-mbd/",
     "Dated baseline: serial laboratory interpretation, phosphate decisions and active vitamin D in nondialysis adults."),
    (PKD, "K03", "KDIGO autosomal dominant polycystic kidney disease", "2025",
     "https://kdigo.org/wp-content/uploads/2026/04/KDIGO-2025-ADPKD-Guideline.pdf",
     "https://kdigo.org/guidelines/autosomal-dominant-polycystic-kidney-disease-adpkd/",
     "Adult tolvaptan eligibility, aquaresis education and volume-depletion interruption."),
    (AAV, "K05", "KDIGO ANCA-associated vasculitis", "2024 amended",
     "https://kdigo.org/wp-content/uploads/2024/05/KDIGO-2024-ANCA-Vasculitis-Guideline-Update.pdf",
     "https://kdigo.org/guidelines/antineutrophilic-cytoplasmic-antibody-anca-associated-vasculitis-aav/",
     "Diagnosis urgency in compatible PR3/MPO-positive, rapidly deteriorating disease; no copied induction algorithm."),
    (LN, "K06", "KDIGO lupus nephritis", "2024",
     "https://kdigo.org/wp-content/uploads/2024/01/KDIGO_2024_Lupus_Nephritis_Guideline.pdf",
     "https://kdigo.org/guidelines/lupus-nephritis/",
     "Consider biopsy in suspected lupus kidney involvement with substantial proteinuria; not a treatment-class algorithm."),
    (DM, "K09", "KDIGO diabetes management in CKD", "2022 final",
     "https://kdigo.org/wp-content/uploads/2022/10/KDIGO-2022-Clinical-Practice-Guideline-for-Diabetes-Management-in-CKD.pdf",
     "https://kdigo.org/guidelines/diabetes-ckd/",
     "Metformin kidney-function boundary; CKD 2024 used for overlapping SGLT2/MRA teaching. 2026 draft not used."),
    (BP, "K11", "KDIGO blood pressure in CKD", "2021",
     "https://kdigo.org/wp-content/uploads/2026/04/KDIGO-2021-Blood-Pressure-in-CKD-Guideline.pdf",
     "https://kdigo.org/guidelines/blood-pressure-in-ckd/",
     "Dated baseline: standardized office measurement and tolerance-qualified adult nondialysis target."),
    (K, "G02", "UK Kidney Association hyperkalemia in adults", "October 2023 final; review due October 2026",
     "https://www.ukkidney.org/sites/renal.org/files/FINAL%20VERSION%20-%20UKKA%20CLINICAL%20PRACTICE%20GUIDELINE%20-%20MANAGEMENT%20OF%20HYPERKALAEMIA%20IN%20ADULTS%20-%20191223.pdf",
     "https://www.ukkidney.org/health-professionals/guidelines/treatment-acute-hyperkalaemia-adults",
     "Dated UK guidance: ECG limitations, calcium, insulin-glucose monitoring and urgent dialysis. Reverification due, not proof of supersession."),
    (NA, "G01", "ESE/ESICM/ERA-EDTA hypotonic hyponatremia", "2014; July 2014 erratum identified",
     "https://academic.oup.com/ejendo/article/170/3/G1/6668028",
     "https://www.ese-hormones.org/publications/directory/ese-clinical-guideline-for-the-management-of-hyponatraemia/",
     "Dated European baseline: tonicity, urine osmolality and monitored initial treatment of severe symptoms. Does not claim a 2026 collaboration is final."),
    (ANEMIA, "K02", "KDIGO anemia in CKD", "2026 final",
     "https://kdigo.org/wp-content/uploads/2026/04/KDIGO-2026-Anemia-in-CKD-Guideline.pdf",
     "https://kdigo.org/guidelines/anemia-in-ckd/",
     "Initial anemia investigation and individualized ESA maintenance ceiling; no jurisdiction-specific prescribing."),
]
SOURCES = [{"id": sid, "register_id": rid, "title": title, "edition": edition,
            "publication_status": "final", "url": url, "canonical_topic_url": topic_url,
            "checked_on": DATE, "check_status": "locator_checked",
            "currency": "dated_final_baseline", "scope": scope,
            "rights_note": "Citation metadata and independently authored medical-fact teaching only. Primary text, tables, algorithms and figures are not distributed or relicensed. Source terms remain independent.",
            "check_note": "Assistant opened primary public guideline or exact indexed recommendation, checked the locators used and read the main SOURCES access rules. Dated evidence; no exhaustive literature/retraction clearance or independent human review claimed."}
           for sid, rid, title, edition, url, topic_url, scope in SOURCE_ROWS]


def cite(source, locator):
    return {"source_id": source, "locator": locator}


QUESTIONS = []


def q(id, topic, objective, source, locator, stem, correct, wrong, rationale, *, secondary=(), difficulty="application", items=None):
    assert len(wrong) == 3
    destination = QUESTIONS if items is None else items
    # Balanced fixed placement, reproducible across publication/reinstallation.
    key_index = len(destination) % 4
    choices = list(wrong)
    choices.insert(key_index, (correct, rationale))
    destination.append({
        "id": id, "version": 1, "family_id": id + ".family",
        "family_version": 1, "key_version": 1, "topic_id": topic,
        "secondary_topic_ids": list(secondary),
        "objective_ids": [f"{topic}.O{objective:02d}"],
        "license": "CC-BY-4.0", "original": True, "kind": "single_best_answer",
        "usage": "assessment_reserved", "stem": stem,
        "options": [{"id": chr(65 + i), "text": text, "rationale": reason}
                    for i, (text, reason) in enumerate(choices)],
        "answer": chr(65 + key_index), "rationale": rationale,
        "difficulty": difficulty, "sources": [cite(source, locator)], "review": dict(REVIEW),
    })


q("RN-CKD-001", "T08", 1, CKD, "Practice Points 1.1.3.1-1.1.3.2",
  "A previously well 48-year-old has a first eGFR result of 52 mL/min/1.73 m2 during gastroenteritis. There are no earlier results or structural findings. What is the best interpretation?",
  "Kidney dysfunction is present, but CKD chronicity is not yet established.",
  [("One eGFR below 60 proves CKD.", "An isolated result does not establish persistence for at least three months."),
   ("CKD can be excluded because the patient feels well.", "Symptoms do not reliably identify or exclude CKD."),
   ("The eGFR establishes the cause as diabetic kidney disease.", "A filtration estimate cannot establish the underlying cause.")],
  "Review prior results and other chronicity evidence, assess acute illness, and arrange appropriate repeat testing. A first abnormal result can reflect AKI or AKD; persistence or other evidence is needed to establish CKD.", secondary=("T02",))
q("RN-CKD-002", "T08", 1, CKD, "Tables 1-3: CKD, GFR and albuminuria categories",
  "Repeated measurements over six months show eGFR 34 mL/min/1.73 m2 and urine ACR 650 mg/g. The cause is still being investigated. Which GFR/albuminuria classification is correct?",
  "G3b A3",
  [("G3a A2", "G3a is 45-59 and A2 is 30-300 mg/g; neither matches these results."),
   ("G4 A3", "G4 requires an eGFR of 15-29, not 34."),
   ("G3b A1", "ACR 650 mg/g is severely increased albuminuria, not A1.")],
  "The persistent eGFR lies in G3b (30-44); ACR exceeds the A3 boundary of 300 mg/g. Describe cause separately rather than inferring it from these categories.", difficulty="foundation")
q("RN-CKD-003", "T08", 1, CKD, "Practice Point 1.3.1.2",
  "An adult without urinary infection has an incidental random urine ACR of 85 mg/g. Which sample is preferred to confirm this finding?",
  "A subsequent first-morning midstream urine ACR.",
  [("A urine dipstick alone.", "A less quantitative test does not adequately confirm an increased ACR."),
   ("Serum albumin alone.", "Serum albumin does not quantify albumin excretion in urine."),
   ("A creatinine measurement without another urine test.", "Filtration and albuminuria describe different aspects of kidney disease.")],
  "Confirm an increased random ACR with a first-morning sample and consider transient influences. Confirmation of albuminuria and establishment of CKD chronicity are related but separate tasks.", secondary=("T02",))
q("RN-CKD-004", "T08", 1, CKD, "Recommendation 1.1.2.1; Recommendation 1.2.2.1",
  "A stable adult with CKD, several chronic conditions and reduced muscle mass needs a more reliable GFR estimate for a treatment decision. Cystatin C testing is available. Which approach improves on creatinine alone?",
  "Estimate GFR using both creatinine and cystatin C, while considering non-GFR influences.",
  [("Assume a low creatinine proves normal filtration.", "Low muscle mass can lower creatinine despite impaired filtration."),
   ("Use the serum creatinine number as the GFR.", "A concentration is not a filtration rate."),
   ("Diagnose kidney failure solely from muscle wasting.", "Muscle wasting changes interpretation but does not itself diagnose kidney failure.")],
  "Combining filtration markers can improve estimation when creatinine is unreliable. Neither marker is free of non-GFR determinants; measured GFR may be needed if the remaining uncertainty affects a major decision.", secondary=("T01", "T02"))
q("RN-CKD-005", "T08", 2, CKD, "Recommendation 2.2.1; Practice Point 2.2.4",
  "A person with CKD G3b asks about the chance of kidney failure. Which approach best supports counseling and planning?",
  "Use an externally validated kidney-failure risk equation appropriate to this population.",
  [("Apply the same probability to everyone with G3b.", "Risk varies with factors including albuminuria and other equation inputs."),
   ("Predict dialysis timing from today's creatinine alone.", "One concentration does not provide a calibrated absolute-risk estimate."),
   ("Use a G3-G5 equation unchanged for every person with G1 disease.", "An equation's validated population and scope matter.")],
  "Validated absolute-risk estimates in CKD G3-G5 can support referral and preparation alongside clinical assessment. They estimate risk over a defined interval and do not predict an exact dialysis date.")
q("RN-CKD-006", "T08", 2, CKD, "Recommendation 3.7.2",
  "A stable adult without diabetes has CKD, eGFR 38 mL/min/1.73 m2 and ACR 480 mg/g despite appropriate care. There is no contraindication. Which statement about SGLT2 inhibition is supported by KDIGO 2024?",
  "It is recommended for kidney protection in this eGFR and albuminuria range even without diabetes.",
  [("It is useful only when diabetes is present.", "The adult CKD recommendation includes people without diabetes."),
   ("It should first be started after maintenance dialysis begins.", "This scenario is eligible nondialysis CKD; it does not establish use on dialysis."),
   ("Its only purpose is to lower serum glucose.", "Its kidney and cardiovascular effects extend beyond glucose lowering.")],
  "The recommendation covers adults with eGFR at least 20 and ACR at least 200 mg/g, or heart failure irrespective of albuminuria. Eligibility still requires individual safety assessment and counseling.")

q("RN-AKI-001", "T06", 1, AKI, "Recommendation 2.1.1",
  "Creatinine rises from 80 to 112 micromol/L in 36 hours after an acute illness. Urine output is not known. Does this meet the creatinine definition of AKI?",
  "Yes: the absolute increase exceeds 26.5 micromol/L within 48 hours.",
  [("No, because creatinine has not doubled.", "Doubling is not required for the AKI definition."),
   ("No, because urine output was not recorded.", "The creatinine criterion can establish AKI independently."),
   ("Yes, and the value alone establishes stage 3.", "This relative and absolute increase does not establish stage 3.")],
  "The increase is 32 micromol/L over 36 hours. It meets the absolute creatinine criterion even though the rise is less than 1.5-fold; staging and cause assessment still follow.", difficulty="foundation")
q("RN-AKI-002", "T06", 1, AKI, "Table 2: AKI staging",
  "In four days an adult's creatinine rises from 90 to 225 micromol/L. Urine output is maintained and no kidney replacement therapy has begun. What is the creatinine-based AKI stage?",
  "Stage 2",
  [("Stage 1", "A 2.5-fold rise exceeds the stage 1 relative-creatinine range."),
   ("Stage 3", "There is no threefold rise, qualifying absolute stage-3 level or initiation of KRT here."),
   ("No AKI because urine output is maintained.", "Nonoliguric AKI can satisfy the creatinine criteria.")],
  "225 divided by 90 is 2.5. A rise to 2.0-2.9 times baseline is stage 2 by creatinine; a higher urine-output stage would take precedence if present.", difficulty="foundation")
q("RN-AKI-003", "T06", 1, AKI, "Recommendation 2.1.1; Table 2",
  "A monitored adult produces 0.4 mL/kg/hour of urine for eight consecutive hours. Creatinine has not yet risen. Which interpretation is correct?",
  "This meets the urine-output criterion for stage 1 AKI.",
  [("AKI requires a creatinine rise as well.", "Either the creatinine or urine-output criterion can establish AKI."),
   ("Any low hourly output immediately establishes stage 3.", "Severity depends on the degree and duration of oliguria."),
   ("Eight hours of this output meets stage 2 by duration.", "The stage 2 oliguria duration is at least 12 hours.")],
  "Output below 0.5 mL/kg/hour for 6-12 hours meets stage 1. Check measurement reliability, perfusion and obstruction rather than waiting for creatinine to rise.", secondary=("T07",))
q("RN-AKI-004", "T06", 2, AKI, "Recommendations 3.4.1-3.4.2",
  "An adult with AKI is euvolemic and has no pulmonary edema. A colleague proposes furosemide solely to speed kidney recovery. What is the best response?",
  "Do not use a diuretic solely to treat AKI; consider it when managing volume overload.",
  [("Use high-dose furosemide to convert AKI into normal kidney function.", "Increased urine volume is not proof of recovery or a reason for routine diuretic treatment."),
   ("Diuretics are forbidden even with refractory fluid overload.", "Volume overload is an important exception to the general recommendation."),
   ("A diuretic makes cause assessment unnecessary.", "Reversible causes still need investigation and treatment.")],
  "Diuretics do not treat the underlying AKI simply by increasing urine output. Their appropriate role includes volume management, with response and hemodynamics monitored.")
q("RN-AKI-005", "T06", 2, AKI, "Recommendation 3.5.1",
  "A critically ill adult is offered low-dose dopamine specifically to prevent or treat AKI, rather than for a hemodynamic indication. Which statement is correct?",
  "Low-dose dopamine is not recommended for AKI prevention or treatment.",
  [("It is recommended because any rise in urine output proves protection.", "A physiologic urine-output effect does not establish improved kidney outcomes."),
   ("It replaces evaluation of hypotension and infection.", "Underlying systemic causes still require treatment."),
   ("It should be given to every oliguric patient before KRT decisions.", "There is no such prerequisite; urgent complications determine KRT need.")],
  "The KDIGO recommendation rejects low-dose dopamine as a kidney-protective AKI treatment. This does not replace clinical selection of vasoactive support for the patient's circulation.", secondary=("T07",))
q("RN-AKI-006", "T06", 2, AKI, "Recommendation 2.3.4",
  "An adult recovers sufficiently from AKI to leave hospital. What kidney-specific follow-up should remain in the plan even if creatinine improves?",
  "Reassess at about three months for resolution and new or worsened CKD, with earlier review when needed.",
  [("No follow-up is needed after any improvement.", "Improvement does not exclude persistent kidney disease or future risk."),
   ("Wait three months before checking any unresolved acute abnormality.", "The three-month reassessment does not postpone clinically necessary earlier review."),
   ("Label every AKI survivor as permanently dialysis dependent.", "Outcomes vary; reassessment should establish the actual recovery state.")],
  "A three-month reassessment distinguishes recovery from persistent or new CKD. Medication, electrolyte and clinical problems may require much earlier checks.", secondary=("T08",))

q("RN-DIAL-001", "T20", 1, CKD, "Practice Points 5.4.1-5.4.2; Table 41",
  "A well-informed adult with stable CKD G5 has eGFR 9 mL/min/1.73 m2, no uremic symptoms and manageable volume, potassium and nutrition. Which is the most appropriate dialysis decision principle?",
  "Use a composite clinical assessment and preferences rather than starting solely at this eGFR.",
  [("An eGFR of 9 mandates dialysis regardless of the person's condition.", "KDIGO does not define a single mandatory eGFR trigger."),
   ("Dialysis can never be discussed until severe symptoms develop.", "Education, modality discussion and access planning should precede an emergency."),
   ("A normal potassium excludes every future dialysis indication.", "Symptoms, volume, nutrition and other complications also matter.")],
  "Initiation considers symptoms, signs, quality of life, preferences, GFR and laboratory abnormalities together. Continue close surveillance and preparation rather than using a numeric cutoff alone.", secondary=("T08",))
q("RN-DIAL-002", "T20", 1, CKD, "Practice Point 5.4.2; Table 41",
  "A person with advanced CKD has persistent pulmonary congestion despite tolerated medical treatment. Which finding most directly supports discussing initiation of dialysis?",
  "Inability to control volume status medically.",
  [("A urine ACR result by itself.", "Albuminuria alone is not a dialysis initiation indication."),
   ("Age over 65 by itself.", "Age alone does not decide whether or when to initiate dialysis."),
   ("An unchanged eGFR excludes dialysis need.", "Clinically significant refractory complications can matter despite a stable estimate.")],
  "Uncontrollable volume status is a clinical indication to consider dialysis. The team should still assess the cause, treatment response, urgency and the person's goals.", secondary=("T27",))
q("RN-DIAL-003", "T20", 2, CKD, "Practice Point 5.4.3",
  "An adult's eGFR is 18 mL/min/1.73 m2 and validated two-year kidney-failure risk is 45%. What action is most appropriate now?",
  "Begin individualized planning for preemptive transplantation and/or dialysis access.",
  [("Defer all preparation until a dialysis emergency.", "Timely preparation can avoid an unplanned start."),
   ("Start dialysis solely because the risk estimate is 45%.", "Preparation thresholds are not automatic initiation thresholds."),
   ("Commit to one modality without discussing preferences.", "Modality and access decisions should reflect circumstances and preferences.")],
  "KDIGO supports preparation when GFR is below 15-20 or two-year KRT risk exceeds 40%. Planning is distinct from starting dialysis and includes transplant suitability and shared choice.", secondary=("T21",))
q("RN-DIAL-004", "T20", 1, K, "Guidelines 18.1-18.2",
  "A maintenance hemodialysis patient presents after a missed session with potassium 7.2 mmol/L and hyperkalemic ECG changes. Which statement correctly combines immediate and definitive management?",
  "Give indicated cardiac protection and arrange urgent dialysis; temporizing treatment does not remove the need for removal.",
  [("Calcium alone removes enough potassium to replace dialysis.", "Calcium protects the myocardium but does not lower total-body potassium."),
   ("Wait for the next routine dialysis appointment.", "Severe hyperkalemia needs urgent assessment and treatment."),
   ("Insulin permanently eliminates excess potassium.", "Insulin redistributes potassium; rebound is possible without removal.")],
  "Urgent dialysis provides potassium removal in this dialysis-dependent scenario. ECG-related calcium and appropriate temporizing measures address immediate risk while dialysis is arranged.", secondary=("T04", "T07"), difficulty="integration")

q("RN-TX-001", "T21", 1, TX, "Recommendation 1.1.1",
  "An adult with progressive CKD G4 is likely to need kidney replacement within a year and wishes to consider transplantation. When should transplant evaluation be initiated?",
  "Before dialysis, ideally allowing at least 6-12 months before anticipated initiation.",
  [("Only after five years of dialysis.", "Delaying evaluation can lose the opportunity for preemptive transplantation."),
   ("Only after an urgent dialysis start.", "Preparation should precede an emergency when feasible."),
   ("Never, because G4 automatically excludes transplant assessment.", "Progressive G4-G5 CKD is an appropriate setting for early assessment.")],
  "Early referral allows candidate assessment and possible living-donor work-up. Eligibility remains individualized; referral is not a guarantee of listing or transplantation.")
q("RN-TX-002", "T21", 1, TX, "Recommendation 1.4",
  "A medically suitable adult has a fully evaluated willing living donor and can receive a kidney before starting dialysis. Which option is preferred by the candidate guideline?",
  "Preemptive living-donor transplantation when feasible.",
  [("Dialysis must always precede any transplant.", "Dialysis is not a prerequisite for preemptive transplantation."),
   ("Exclude a living donor solely because the recipient has not dialyzed.", "This is not an exclusion criterion."),
   ("Cancel all recipient and donor risk assessment.", "Preemptive timing does not remove the need for careful evaluation.")],
  "For an eligible person with an eligible donor, a preemptive living-donor transplant is preferred. Medical, psychosocial and donor safety assessments remain essential.")
q("RN-TX-003", "T21", 2, TX, "Recommendations 7.1-7.1.1",
  "An adult referred for transplantation has obesity but no completed surgical or functional assessment. What is the most appropriate initial principle?",
  "Assess obesity-related risks individually rather than excluding solely because of obesity.",
  [("Every person with obesity is automatically ineligible.", "The guideline advises against exclusion solely on this basis."),
   ("Obesity has no relevance to operative assessment.", "Surgical risk, wound issues and overall health still need assessment."),
   ("Eligibility can be decided from BMI without other information.", "BMI is one aspect of an individualized candidate assessment.")],
  "Obesity warrants risk assessment and appropriate weight-management discussion. The question concerns obesity alone; it does not override center policies or other contraindications.")
q("RN-TX-004", "T21", 2, TX, "Recommendations 10.7.2-10.7.2.1",
  "A transplant candidate needs a live attenuated vaccine and transplantation is elective. Which plan is consistent with the candidate guideline?",
  "Complete indicated vaccination before transplant, leaving at least four weeks after a live vaccine.",
  [("Give the live vaccine routinely immediately after transplantation.", "Post-transplant immunosuppression changes the safety of live vaccines."),
   ("Ignore the vaccination history until after transplant.", "Pre-transplant assessment is an opportunity to complete indicated protection."),
   ("No vaccine is useful before transplantation.", "Candidate guidance explicitly supports recommended vaccines before transplant.")],
  "Plan indicated vaccines before immunosuppression. Live attenuated vaccines should be completed at least four weeks before transplantation; exact vaccine eligibility follows current specialist recommendations.", secondary=("T17",))

q("RN-GN-001", "T10", 1, GD, "Practice Point 1.1.1",
  "An adult with unexplained proteinuria and active urine sediment is being evaluated for glomerular disease. What best describes kidney biopsy's diagnostic role?",
  "It is the diagnostic reference standard, although selected diseases can be managed without it.",
  [("A biopsy is never useful if creatinine is normal.", "Important glomerular disease may be present with preserved filtration."),
   ("Any positive dipstick identifies the histologic diagnosis.", "A dipstick does not identify the glomerular lesion."),
   ("Every patient must be biopsied irrespective of risk or diagnostic context.", "The decision depends on diagnostic value, clinical context and risk.")],
  "Biopsy can establish lesion, activity and chronicity. It is not mandatory in every circumstance; the result must have clinical value and the procedure's risks must be considered.", secondary=("T22",))
q("RN-GN-002", "T10", 1, GD, "Practice Points 3.1.1-3.1.2",
  "An adult has nephrotic syndrome and positive anti-PLA2R antibodies in a compatible presentation. Which statement about diagnosing membranous nephropathy is correct?",
  "A biopsy is not required solely to confirm the diagnosis in this setting, but other reasons for biopsy may remain.",
  [("Positive anti-PLA2R excludes every associated condition.", "Evaluation for associated conditions remains appropriate irrespective of antibody status."),
   ("The antibody always establishes minimal change disease.", "Anti-PLA2R is associated with membranous nephropathy, not this histologic diagnosis."),
   ("The antibody automatically mandates immediate immunosuppression.", "Diagnosis does not by itself determine treatment intensity or timing.")],
  "The antibody can establish membranous nephropathy in a compatible nephrotic presentation. Consider atypical features, kidney function, associated conditions and whether tissue would answer another question.")
q("RN-GN-003", "T10", 2, GD, "Practice Point 6.2.1.1",
  "An adult has biopsy-proven adaptive secondary FSGS with an identified cause and no evidence of primary FSGS. What treatment principle is appropriate?",
  "Treat the cause and provide supportive care rather than routine primary-FSGS immunosuppression.",
  [("Use immunosuppression for every biopsy showing an FSGS lesion.", "FSGS is a lesion with different causes; the primary-disease treatment pathway is not universal."),
   ("Ignore blood pressure and proteinuria.", "Supportive kidney-protective care is important in secondary disease."),
   ("The biopsy proves there can be no underlying adaptive cause.", "The lesion must be interpreted with the clinical and pathologic context.")],
  "Secondary FSGS should not receive immunosuppression as though it were primary FSGS. Address the driver and kidney-protective measures; classification is central to the decision.")
q("RN-GN-004", "T10", 1, GD, "Practice Point 5.1.1",
  "A 43-year-old develops new nephrotic syndrome. Minimal change disease is suspected, but no biopsy has been performed. Which statement best fits the adult diagnostic pathway?",
  "Adult minimal change disease is a biopsy diagnosis.",
  [("Response to a diuretic establishes minimal change disease.", "Edema response does not identify the glomerular lesion."),
   ("Nephrotic-range proteinuria alone identifies the lesion.", "Several different diseases cause nephrotic syndrome."),
   ("The pediatric empirical pathway applies automatically to all adults.", "Adult and pediatric diagnostic pathways are not interchangeable.")],
  "In adults, diagnosing minimal change disease requires kidney biopsy. Clinical nephrotic syndrome is a presentation, not a specific histologic diagnosis.", secondary=("T22",))

q("RN-K-001", "T04", 1, K, "Guideline 16.2; STEP 1 cardiac protection",
  "An adult has severe hyperkalemia with a broad QRS attributed to hyperkalemia. What is the principal immediate purpose of intravenous calcium?",
  "Reduce cardiac electrical toxicity while potassium-lowering treatment is arranged.",
  [("Remove excess potassium from the body.", "Calcium does not provide potassium removal."),
   ("Shift potassium into cells for several hours.", "That is the purpose of redistribution therapies such as insulin, not calcium."),
   ("Replace all further ECG and potassium monitoring.", "Protection can be temporary and the underlying disturbance still needs treatment.")],
  "Calcium provides myocardial protection when indicated by toxic ECG changes. Treat hyperkalemia itself and reassess the ECG; protection is distinct from redistribution and removal.", secondary=("T07",))
q("RN-K-002", "T04", 1, K, "Guidelines 16.3.1-16.3.2; 17.1",
  "Potassium falls after insulin-glucose treatment for hyperkalemia. Which statement explains why potassium still needs repeated monitoring and a removal plan?",
  "Insulin shifts potassium intracellularly; rebound can occur as that effect wanes.",
  [("Insulin directly excretes potassium in every patient.", "It redistributes potassium rather than guaranteeing excretion."),
   ("A single improved potassium value proves permanent resolution.", "The cause can persist and potassium may rebound."),
   ("Giving glucose makes dialysis unnecessary in all circumstances.", "Glucose support does not decide whether potassium removal is needed.")],
  "Redistribution can temporarily improve the circulating concentration without resolving excess potassium. Reassess both biochemical response and the need for definitive removal.")
q("RN-K-003", "T04", 1, K, "Guideline 17.2",
  "An adult without diabetes receives insulin-glucose for severe hyperkalemia. Which monitoring plan is required?",
  "Serial blood glucose monitoring for several hours, as well as potassium reassessment.",
  [("No glucose checks because the person does not have diabetes.", "Nondiabetic patients can develop treatment-related hypoglycemia."),
   ("One glucose check immediately after infusion is sufficient.", "Hypoglycemia can develop later; UKKA specifies monitoring through six hours."),
   ("Measure HbA1c instead of monitoring blood glucose.", "HbA1c does not detect acute treatment-related hypoglycemia.")],
  "Hypoglycemia is a recognized insulin-treatment harm and may be delayed. UKKA recommends regular glucose checks over six hours; potassium monitoring addresses response and rebound separately.", secondary=("T19",))
q("RN-K-004", "T04", 1, K, "Guideline 14.1; rationale on ECG sensitivity",
  "A promptly confirmed potassium of 6.9 mmol/L is found in an adult whose first ECG shows no characteristic hyperkalemic changes. Which conclusion is safest?",
  "The normal ECG does not exclude dangerous hyperkalemia or remove the need for urgent management.",
  [("The potassium result is necessarily false because the ECG is normal.", "ECG sensitivity is insufficient to make that inference."),
   ("No further monitoring or assessment is needed.", "Severe biochemical hyperkalemia still requires urgent evaluation."),
   ("A normal ECG proves there can be no arrhythmia risk.", "Absence of classic changes does not establish safety.")],
  "The ECG helps assess immediate cardiac effects but does not reliably exclude severe hyperkalemia. Evaluate the confirmed result, clinical context and need for monitored treatment.", secondary=("T07",))
q("RN-AB-001", "T04", 2, CKD, "Practice Point 3.10.1",
  "A stable adult with CKD has repeatedly measured bicarbonate of 17 mmol/L after other explanations are evaluated. Which approach is consistent with KDIGO 2024?",
  "Consider pharmacologic treatment, with or without dietary intervention, for clinically important acidosis.",
  [("Ignore the result because all acidosis in CKD is harmless.", "A bicarbonate below 18 is given as an example of potentially important acidosis."),
   ("Give unlimited alkali without monitoring.", "Treatment can affect fluid status, blood pressure and electrolytes."),
   ("Promise that alkali is proven to prevent kidney failure in this individual.", "A practice point does not establish that outcome for an individual patient.")],
  "The guidance suggests considering treatment when acidosis has potential clinical implications, with bicarbonate below 18 mmol/L as an adult example. Evaluate the clinical context rather than treating an isolated number.", secondary=("T08",))
q("RN-AB-002", "T04", 2, CKD, "Practice Point 3.10.2",
  "An adult with CKD begins oral alkali for metabolic acidosis. What should follow-up include?",
  "Bicarbonate, potassium, blood pressure and fluid status, avoiding bicarbonate above the normal range.",
  [("Bicarbonate only, with no attention to volume or blood pressure.", "The treatment can adversely affect these domains."),
   ("Titrate to the highest bicarbonate possible.", "Overshooting the upper normal limit is not the treatment goal."),
   ("Stop monitoring potassium because alkali cannot affect it.", "Potassium is explicitly part of the monitoring recommendation.")],
  "Monitoring should assess correction and treatment harms. Achieving a bicarbonate value is not sufficient if blood pressure, potassium or congestion worsens.", secondary=("T08", "T19"))

q("RN-NA-001", "T03", 1, NA, "Section 6.2: confirmation of hypotonic hyponatremia",
  "An adult's sodium is 124 mmol/L, measured serum osmolality is 263 mOsm/kg, and there is no hyperglycemia or exogenous effective osmole. What category is established?",
  "Hypotonic hyponatremia.",
  [("Hypertonic hyponatremia.", "The measured osmolality is low in this specified setting."),
   ("A specific diagnosis of SIAD solely from serum values.", "Etiology requires further assessment, including urine data and exclusions."),
   ("Normal tonicity because sodium is above 120.", "Tonicity is not defined by that sodium cutoff.")],
  "The low measured osmolality confirms hypotonicity in the absence of another effective osmole. Serum findings classify the disorder but do not identify its cause by themselves.", difficulty="foundation")
q("RN-NA-002", "T03", 1, NA, "Recommendations 6.3.1.1-6.3.1.2 and diagnostic rationale",
  "In confirmed hypotonic hyponatremia, a contemporaneous urine osmolality is 70 mOsm/kg. Which interpretation is most appropriate?",
  "The urine is strongly diluted; consider excess water intake relative to available solute.",
  [("This alone proves persistent inappropriate antidiuresis.", "Markedly dilute urine does not support that conclusion."),
   ("The urine value has no diagnostic relevance.", "Urine osmolality is an early discriminator in the diagnostic pathway."),
   ("It establishes adrenal failure without additional tests.", "A urine osmolality cannot establish that endocrine diagnosis.")],
  "Urine osmolality at or below 100 indicates strongly suppressed antidiuresis and directs attention to water intake and solute availability. Clinical history and further evaluation still determine the cause.")
q("RN-NA-003", "T03", 2, NA, "Section 7.1.1-7.1.2: severe symptoms and first-day follow-up",
  "An adult with hypotonic hyponatremia has a seizure attributed to the sodium disturbance. What is the immediate treatment principle?",
  "Use monitored hypertonic saline to obtain a modest early rise and reassess symptoms, while limiting total correction.",
  [("Normalize sodium completely as fast as possible.", "Rapid excessive correction can cause osmotic demyelination."),
   ("Use fluid restriction alone while waiting for every etiologic test.", "Severe attributable neurologic symptoms require urgent treatment."),
   ("Give treatment without repeat sodium measurement.", "The response and cumulative correction need close monitoring.")],
  "Severe attributable symptoms justify urgent monitored hypertonic treatment. The initial goal is symptom control with a limited sodium rise; subsequent management must prevent overcorrection and address the cause.", secondary=("T07",))

q("RN-MBD-001", "T05", 1, MBD, "Recommendation 4.1.1",
  "A person with CKD has several changing PTH, calcium and phosphate results. What is the best basis for CKD-MBD treatment decisions?",
  "Interpret serial phosphate, calcium and PTH measurements together.",
  [("Treat only the latest PTH result regardless of other values.", "The parameters interact and a single result can mislead."),
   ("Ignore trends whenever one calcium measurement is normal.", "A normal value does not settle the overall CKD-MBD assessment."),
   ("Use serum creatinine as the only bone-treatment target.", "Creatinine does not replace assessment of mineral metabolism.")],
  "Serial joint assessment informs both the disturbance and the effects of treatment. An isolated value should not dictate an intervention without its clinical and biochemical context.")
q("RN-MBD-002", "T05", 2, MBD, "Recommendation 4.1.5",
  "An adult with CKD G3b has repeatedly normal phosphate levels. Which phosphate-lowering principle is supported?",
  "Base phosphate-lowering treatment on progressively or persistently elevated phosphate, rather than preventive binders for a normal value.",
  [("Every patient with G3b needs a binder even with normal phosphate.", "The guideline does not recommend this routine preventive strategy."),
   ("One historical high phosphate makes current trends irrelevant.", "Persistence and progression are part of the decision."),
   ("Phosphate treatment decisions need no attention to diet or other therapies.", "Treatments and sources of phosphate require individualized assessment.")],
  "Treatment decisions should be driven by sustained or progressive hyperphosphatemia and the overall CKD-MBD picture. This avoids assuming that treating a normal laboratory value improves outcomes.")
q("RN-MBD-003", "T05", 2, MBD, "Recommendation 4.2.2",
  "An adult with CKD G3b not on dialysis has a mildly increased PTH, without severe progressive hyperparathyroidism. What is the best principle regarding calcitriol?",
  "Do not use it routinely; first evaluate modifiable factors and the biochemical trend.",
  [("Calcitriol is mandatory for any PTH above the assay range.", "Routine active vitamin D use is not recommended in this population."),
   ("The dialysis and nondialysis treatment pathways are identical.", "The recommendations distinguish these settings."),
   ("Ignore calcium, phosphate and vitamin D status.", "These modifiable factors help interpret the elevated PTH.")],
  "Routine calcitriol or vitamin D analog treatment is discouraged in adult nondialysis G3a-G5 CKD. Selected G4-G5 patients with severe progressive hyperparathyroidism are a different situation.")

q("RN-BP-001", "T09", 1, BP, "Recommendation 1.1; Practice Point 3.1.1",
  "A rushed single office reading is 132/76 mmHg in an adult with CKD. A clinician wants to apply the KDIGO systolic target directly. What should be clarified first?",
  "Whether blood pressure was measured using a standardized office protocol.",
  [("The target applies unchanged to every measurement technique.", "Applying the standardized target to nonstandardized readings can be hazardous."),
   ("Diastolic pressure alone establishes the standardized systolic result.", "It cannot establish how the systolic measurement was obtained."),
   ("Albuminuria automatically corrects measurement error.", "Risk information does not standardize a blood pressure reading.")],
  "The target is tied to standardized measurement. Reassess technique and use appropriate complementary out-of-office readings rather than mechanically intensifying treatment from a rushed value.")
q("RN-BP-002", "T09", 2, BP, "Recommendation 3.1.1; Practice Point 3.1.2",
  "An adult with hypertension and nondialysis CKD develops symptomatic postural hypotension during treatment. Which interpretation of the systolic target is correct?",
  "The suggested standardized-office target below 120 mmHg is qualified by tolerance; less intensive treatment can be appropriate.",
  [("The target must be pursued despite symptomatic hypotension.", "Tolerance and symptoms are explicit qualifications."),
   ("All CKD blood pressure guidance is invalid if one patient cannot tolerate the target.", "Individual adaptation does not invalidate the population recommendation."),
   ("A nonstandardized reading below 120 guarantees safe treatment.", "Both measurement quality and clinical tolerance matter.")],
  "The 2021 recommendation suggests a standardized systolic target below 120 when tolerated. Symptomatic postural hypotension supports reconsidering treatment intensity and the person's circumstances.")

q("RN-DM-001", "T14", 1, DM, "Recommendation 4.1.1; Practice Point 4.1.3",
  "An adult with type 2 diabetes and stable CKD has eGFR 24 mL/min/1.73 m2. Which statement about metformin fits KDIGO diabetes guidance?",
  "This is below the eGFR range recommended for metformin; review discontinuation and alternatives.",
  [("Start metformin because it is recommended at every CKD stage.", "The guideline's recommended eGFR boundary is at least 30."),
   ("Double the dose to compensate for reduced filtration.", "Reduced kidney function does not justify increasing exposure."),
   ("The HbA1c alone overrides the kidney-function boundary.", "Glycemic need does not remove the safety constraint.")],
  "KDIGO recommends metformin in type 2 diabetes with CKD when eGFR is at least 30; below 30 it should be stopped. Choose an individualized alternative and assess whether an acute change contributes.", secondary=("T19",))
q("RN-DM-002", "T14", 1, CKD, "Recommendation 3.8.1; Practice Points 3.8.1-3.8.3",
  "An adult with type 2 diabetes has eGFR 42, normal potassium and persistent ACR 160 mg/g despite maximally tolerated RAS inhibition. Which additional kidney-protective class can be considered if appropriate?",
  "A nonsteroidal mineralocorticoid receptor antagonist with demonstrated kidney or cardiovascular benefit, with potassium monitoring.",
  [("Any MRA without checking potassium.", "Hyperkalemia risk and evidence for the selected agent matter."),
   ("A second RAS blocker added routinely.", "Combining ACE inhibitor and ARB therapy is not the recommended strategy."),
   ("No additional treatment is ever considered once a RAS inhibitor is used.", "Persistent albuminuria can justify layered kidney-protective treatment.")],
  "The recommendation applies to type 2 diabetes, eGFR above 25, normal potassium and albuminuria despite tolerated RAS blockade. Agent selection and ongoing potassium monitoring are essential.", secondary=("T19",))
q("RN-DM-003", "T14", 2, CKD, "Practice Point 3.7.2",
  "A person taking an SGLT2 inhibitor will undergo surgery with prolonged fasting. Which plan is reasonable?",
  "Temporarily withhold the SGLT2 inhibitor according to the perioperative plan and document when it can be restarted.",
  [("Continue regardless of fasting or illness.", "These circumstances can increase the risk of ketosis."),
   ("Permanently stop every kidney-protective medicine after any surgery.", "Temporary interruption and appropriate restarting are distinct decisions."),
   ("A normal glucose always excludes SGLT2-related ketosis.", "Glucose alone does not remove that risk.")],
  "Prolonged fasting, surgery and critical illness are settings in which withholding SGLT2 inhibition is reasonable. Follow the local perioperative protocol and a clear review/restart plan.", secondary=("T19",))

q("RN-PKD-001", "T12", 2, PKD, "Recommendation 4.1.1.1",
  "A 38-year-old with confirmed ADPKD has eGFR 54 and verified evidence of rapid progression. There is no contraindication to treatment. Which statement best fits tolvaptan selection?",
  "This is an appropriate setting for discussing tolvaptan after individualized benefit-risk assessment.",
  [("Tolvaptan is recommended for every incidental renal cyst.", "The diagnosis and risk of rapid progression must be established."),
   ("It can first be considered only after dialysis starts.", "Disease-modifying eligibility is defined before kidney replacement."),
   ("Risk assessment and safety monitoring are unnecessary.", "Treatment requires selection, education and monitoring.")],
  "The 2025 guideline recommends initiation in adults with ADPKD, eGFR at least 25 and risk of rapid progression. The scenario supplies those criteria; the decision still includes contraindications and monitoring burden.")
q("RN-PKD-002", "T12", 2, PKD, "Practice Points 4.1.4.2-4.1.4.4",
  "A person taking tolvaptan develops vomiting and cannot maintain adequate drinking. Which instruction is appropriate?",
  "Temporarily interrupt tolvaptan during the volume-depleting illness and seek advice on recovery and restarting.",
  [("Continue unchanged despite inability to replace water losses.", "Aquaresis can worsen volume depletion."),
   ("Restrict all drinking further to increase treatment effect.", "That increases dehydration risk rather than supporting safe treatment."),
   ("Replace the sick-day plan with an unsupervised higher dose.", "Dose escalation is not a response to volume depletion.")],
  "People using tolvaptan need an interruption plan for circumstances that prevent adequate water intake or cause volume depletion. Assess illness and hydration before deciding when treatment can resume.", secondary=("T06", "T19"))

q("RN-DRUG-001", "T19", 1, CKD, "Recommendation 3.6.4",
  "An adult with CKD and albuminuria is already taking an ACE inhibitor. Which proposal should be avoided?",
  "Add an ARB solely to intensify RAS blockade.",
  [("Check potassium after dose adjustment.", "Monitoring is appropriate; it is not the contraindicated proposal."),
   ("Review blood pressure and creatinine.", "These are appropriate safety and response checks."),
   ("Use the maximally tolerated dose of one indicated RAS inhibitor.", "Single-agent dose optimization differs from dual blockade.")],
  "Avoid combinations of ACE inhibitor, ARB and direct renin inhibitor in CKD. Greater blockade is not automatically better and can increase adverse effects.", secondary=("T08",))
q("RN-DRUG-002", "T19", 2, CKD, "Practice Point 4.3.2",
  "Several regular medicines are temporarily stopped during an acute dehydrating illness. What should be included before the person leaves acute care?",
  "A clear documented plan for reviewing and restarting appropriate medicines.",
  [("Assume all stopped medicines will restart automatically.", "Without a plan, beneficial treatment may remain unintentionally discontinued."),
   ("Discard the medication list to avoid confusion.", "Medication reconciliation and communication reduce rather than create uncertainty."),
   ("Restart every medicine immediately without checking the illness or kidney function.", "Restarting must consider recovery and drug-specific safety.")],
  "Temporary discontinuation requires explicit communication about reassessment and restart. This preserves benefit while avoiding unsafe resumption before recovery.", secondary=("T06",))
q("RN-NUTR-001", "T25", 1, CKD, "Recommendation 3.3.1.1; Practice Points 3.3.1.3 and 3.3.1.5",
  "A nutritionally stable adult with CKD G3b who is not on dialysis asks about usual protein intake. Which starting recommendation fits KDIGO 2024?",
  "About 0.8 g/kg/day, individualized with nutritional assessment.",
  [("A very high-protein diet is required for every nondialysis patient.", "Routine excessive protein is not recommended in this setting."),
   ("A very low-protein diet is safe for every frail or malnourished patient.", "Nutritional instability changes the risk-benefit assessment."),
   ("Dialysis and nondialysis protein needs are always identical.", "Dialysis changes protein losses and nutritional requirements.")],
  "The adult G3-G5 recommendation is approximately 0.8 g/kg/day. Avoid extrapolating it without assessment to dialysis, frailty, catabolism or malnutrition.", secondary=("T08",))
q("RN-CARE-001", "T26", 1, CKD, "Practice Points 5.5.1-5.5.2; Table 43",
  "After informed discussion, a person with kidney failure chooses comprehensive conservative care. What does this mean?",
  "Active symptom management, support and care planning without dialysis, aligned with the person's goals.",
  [("The person receives no further kidney care.", "Conservative care is active care, not abandonment."),
   ("The choice prevents every future discussion of goals.", "Preferences and circumstances can be reviewed."),
   ("It is identical to maintenance hemodialysis.", "The care approach does not include dialysis.")],
  "Comprehensive conservative care includes symptom-focused treatment, communication, psychological and social support, and planning. It is a positive care option that deserves the same attention to the person's priorities.", secondary=("T20", "T24"))
q("RN-EVID-001", "T26", 2, CKD, "Introduction: graded recommendations and ungraded practice points",
  "A learner finds a KDIGO practice point next to a graded recommendation. What distinction should guide interpretation?",
  "A practice point is ungraded practical guidance and should not be presented as a formally graded evidence recommendation.",
  [("Every practice point is necessarily backed by high-certainty trial evidence.", "The format does not establish that level of certainty."),
   ("An ungraded point has no possible practical value.", "Ungraded guidance can address useful questions not suited to systematic grading."),
   ("A recommendation grade proves an outcome for every individual.", "Population evidence still requires individual interpretation.")],
  "KDIGO distinguishes graded recommendations from ungraded practice points. Preserve the statement type, evidence limits and clinical context when teaching or citing either.")
q("RN-AAV-001", "T16", 2, AAV, "Practice Point 9.1.1",
  "An adult has a rapidly deteriorating kidney presentation compatible with small-vessel vasculitis, positive MPO-ANCA and low suspicion of an alternative mimic. Biopsy cannot be reported until tomorrow. Which principle is appropriate?",
  "Urgent specialist-directed treatment should not be delayed solely while awaiting biopsy or its report.",
  [("Always withhold treatment until histology is reported, regardless of deterioration.", "Delay can be inappropriate in this compatible, rapidly deteriorating scenario."),
   ("Any positive ANCA alone proves vasculitis in every patient.", "Clinical compatibility and alternative diagnoses still matter."),
   ("Biopsy has no diagnostic or prognostic role once treatment begins.", "Biopsy should still be considered and can provide valuable information.")],
  "The amended 2024 guidance balances the value of biopsy against urgent treatment in a compatible MPO/PR3-positive presentation. It does not license treatment solely from an isolated antibody result.", secondary=("T10", "T06"), difficulty="integration")
q("RN-LN-001", "T16", 1, LN, "Practice Point 10.1.1; Figure 1 diagnostic thresholds",
  "An adult with SLE has newly confirmed proteinuria of 0.8 g/day and abnormal urinary sediment. Kidney function is currently preserved. What is an appropriate next diagnostic consideration?",
  "Consider kidney biopsy as part of evaluation for lupus nephritis.",
  [("Preserved eGFR excludes lupus nephritis.", "Active kidney disease can occur before filtration falls."),
   ("Wait for nephrotic-range proteinuria before any further assessment.", "The guideline prompts consideration at lower proteinuria with the clinical context."),
   ("Serum complement alone establishes the histologic class.", "Serology does not determine the tissue classification.")],
  "The diagnostic pathway suggests considering biopsy at proteinuria at least 500 mg/day, while integrating urine, kidney function and clinical findings. Tissue can define disease and guide management; the threshold is not an isolated automatic rule.", secondary=("T10", "T22"))
q("RN-ANEMIA-001", "T08", 3, ANEMIA, "Practice Points 1.2.1-1.2.2",
  "An adult with CKD G4 has a newly recognized hemoglobin of 9.6 g/dL. What is an appropriate initial kidney-anemia investigation strategy?",
  "Assess a complete blood count, reticulocytes, ferritin and transferrin saturation; investigate further if the cause remains unclear.",
  [("Assume every low hemoglobin in CKD is erythropoietin deficiency.", "Iron deficiency, blood loss and other causes can coexist or predominate."),
   ("Start ESA solely from the eGFR without evaluating anemia.", "Anemia assessment and individualized treatment decisions are required."),
   ("A normal ferritin alone excludes all iron-related problems.", "Ferritin interpretation requires context and other iron indices.")],
  "The 2026 guidance starts with CBC, reticulocytes and iron indices. Persistent unexplained anemia needs a broader cause assessment rather than automatic attribution to CKD.")
q("RN-ANEMIA-002", "T08", 4, ANEMIA, "Recommendation 3.3.1; Practice Point 3.3.1",
  "An adult with anemia in CKD is treated with an ESA. Which maintenance-target principle is recommended in KDIGO 2026?",
  "Individualize the target while keeping hemoglobin below 11.5 g/dL.",
  [("Normalize hemoglobin to 15 g/dL in every adult.", "Routine high targets increase risk and are not recommended."),
   ("Ignore thrombotic and cardiovascular risks once treatment starts.", "Treatment benefits and harms remain part of target selection."),
   ("Use the same target and dose without follow-up in every patient.", "Both target and dosing require individual assessment and monitoring.")],
  "KDIGO 2026 recommends an ESA-treated adult hemoglobin target below 11.5 g/dL. Select the individual target by balancing symptoms and transfusion avoidance against treatment risks.")

CASES = []


def stage(narrative, prompts, points, source, locator):
    return {"narrative": narrative, "prompts": prompts, "teaching_points": points,
            "sources": [cite(source, locator)]}


def case(id, topic, secondary, objectives, title, summary, stages, take_home, *, items=None):
    numbered = [{"id": f"stage-{n + 1}", **s} for n, s in enumerate(stages)]
    source_map = {(s["source_id"], s["locator"]): s for st in stages for s in st["sources"]}
    destination = CASES if items is None else items
    destination.append({"id": id, "version": 1, "topic_id": topic,
                  "secondary_topic_ids": secondary, "objective_ids": objectives,
                  "license": "CC-BY-4.0", "original": True, "synthetic": True,
                  "usage": "teaching", "title": title, "summary": summary,
                  "stages": numbered, "take_home": take_home,
                  "sources": list(source_map.values()), "review": dict(REVIEW)})


case("RN-CASE-CKD", "T08", ["T02", "T09"],
     ["T08.O01", "T08.O02", "T02.O01"],
     "One abnormal result, a longer story",
     "Build chronicity, CGA classification and a kidney-protection plan from serial evidence.", [
    stage("A synthetic 57-year-old is referred with eGFR 47 and urine ACR 220 mg/g. The referral contains no prior laboratory results. The person had a febrile illness last week and feels better now.",
          ["What evidence establishes chronicity?", "Which acute or transient influences need checking?"],
          ["An isolated abnormal filtration or urine result does not establish CKD duration.",
           "Seek earlier measurements, structural history and a repeat-testing plan that also addresses possible acute disease."], CKD, "Practice Points 1.1.3.1-1.1.3.2"),
    stage("Earlier results are retrieved: eGFR was 46 and ACR 260 mg/g eight months ago. A first-morning ACR is now 240 mg/g, and eGFR remains 47. Blood pressure and the cause of disease are still being assessed.",
          ["How would you state the CGA classification without inventing the cause?", "What changes if the urine sample was taken during infection?"],
          ["Persistence establishes chronicity; the GFR and albuminuria categories here are G3a A2.",
           "Document cause as under evaluation. Use appropriately collected repeat urine measurements when transient factors could distort ACR."], CKD, "Tables 1-3; Practice Point 1.3.1.2"),
    stage("The person asks whether dialysis is inevitable and wants a clear plan. There is no diabetes, no contraindication to an SGLT2 inhibitor, and no current acute illness.",
          ["How would you explain absolute risk without predicting a dialysis date?", "Which kidney-protective options need shared discussion?"],
          ["A validated kidney-failure risk equation can support counseling in G3-G5; uncertainty and its time horizon should be explained.",
           "This eGFR and persistent ACR above 200 meet the adult CKD SGLT2 recommendation, including without diabetes. Combine treatment with cause assessment, BP care and monitoring."], CKD, "Recommendation 2.2.1; Recommendation 3.7.2"),
], ["Establish persistence before labeling chronic disease.", "CGA describes the condition; a risk equation adds calibrated prognosis."])

case("RN-CASE-AKI", "T06", ["T03", "T19", "T08"],
     ["T06.O01", "T06.O02", "T19.O02"],
     "An acute illness and a medication restart plan",
     "Recognize nonoliguric AKI, investigate reversible contributors and plan recovery.", [
    stage("A synthetic 64-year-old has had two days of vomiting and poor intake. Creatinine was 95 micromol/L last week and is 165 today. Urine is still being passed. Medicines include an ACE inhibitor and a diuretic.",
          ["Does maintained urine output exclude AKI?", "What information changes immediate assessment?"],
          ["The rise is about 1.74-fold within a week, meeting stage 1 by creatinine even without oliguria.",
           "Assess circulation, electrolytes, obstruction, intercurrent illness and medicine exposure. Avoid assuming that every acute rise has only one cause."], AKI, "Recommendation 2.1.1; Table 2; Recommendation 2.3.1"),
    stage("The adult has clinical evidence of volume depletion, no congestion, and no urgent electrolyte complication. A colleague asks whether furosemide should be used to improve the kidney result.",
          ["What does a diuretic treat in AKI?", "How would you assess response to the cause-directed plan?"],
          ["Do not use a diuretic simply to reverse AKI; volume overload is a separate indication.",
           "Treatment should address the identified cause and be reassessed using examination, kidney function, urine output and electrolytes."], AKI, "Recommendations 3.4.1-3.4.2; 2.3.1-2.3.2"),
    stage("After recovery the person is ready to leave acute care. Some regular medicines were temporarily withheld, and the discharge summary currently says only 'medications adjusted'.",
          ["What must a useful restart plan specify?", "What later kidney assessment remains necessary?"],
          ["Specify the medicines, reason for interruption, conditions for review/restart and who will check. A temporary change should not silently become a permanent loss of beneficial treatment.",
           "Arrange early review for unresolved issues and a three-month kidney assessment for resolution or new/worsened CKD."], CKD, "Practice Point 4.3.2"),
], ["Nonoliguric AKI is still AKI.", "Recovery planning includes medicine reconciliation and reassessment of kidney status."])
CASES[-1]["stages"][-1]["sources"].append(cite(AKI, "Recommendation 2.3.4"))
CASES[-1]["sources"].append(cite(AKI, "Recommendation 2.3.4"))

case("RN-CASE-DIALYSIS", "T20", ["T08", "T21", "T27"],
     ["T20.O01", "T20.O02"],
     "Preparing before a complication forces the choice",
     "Distinguish kidney replacement preparation from symptom-driven initiation.", [
    stage("A synthetic adult with progressive CKD has eGFR 17 and a two-year kidney-failure risk of 48%. Daily function is good and current biochemical abnormalities are manageable. No access or transplant assessment is underway.",
          ["What should be planned now?", "Does planning itself mean dialysis must start today?"],
          ["Discuss modality options, access preparation and preemptive transplant evaluation. The risk and GFR support preparation.",
           "Preparation is distinct from initiation and preserves choice before an emergency."], CKD, "Practice Point 5.4.3"),
    stage("Several months later the person develops increasing breathlessness and congestion despite tolerated treatment. The eGFR has changed little.",
          ["What must be reassessed besides the eGFR?", "Which complication can support dialysis initiation?"],
          ["Assess symptoms, volume, causes, treatment response, preferences and other abnormalities together.",
           "Inability to control volume status can support initiation even without a sudden eGFR change."], CKD, "Practice Points 5.4.1-5.4.2; Table 41"),
    stage("The person wants to remain at home if feasible and asks how dialysis will affect work and caregiving. A family member assumes there is only one acceptable modality.",
          ["What belongs in a shared modality discussion?", "How do you avoid treating a preference as a promise of suitability?"],
          ["Explain the available options, practical support, expected burden and the person's goals, with assessment of medical suitability.",
           "A preference directs evaluation; it does not erase modality constraints or the need for a safe access and training plan."], CKD, "Practice Point 5.4.1; Practice Point 5.5.1"),
], ["Use risk to prepare, and the full clinical picture to initiate.", "Kidney replacement decisions should preserve the person's informed choices."])

case("RN-CASE-TRANSPLANT", "T21", ["T17", "T20"],
     ["T21.O01", "T21.O02", "T17.O01"],
     "A year to prepare for transplantation",
     "Plan preemptive assessment, evaluate risks and use the vaccination window.", [
    stage("A synthetic 41-year-old with progressive CKD G4 expects to need kidney replacement within a year. A sibling has offered to learn about donation. The patient has not yet started dialysis.",
          ["When should recipient assessment start?", "What can early referral make possible?"],
          ["Initiate assessment early enough to allow 6-12 months before anticipated dialysis when feasible.",
           "Early recipient and donor assessment may allow preemptive living-donor transplantation; neither the offer nor referral guarantees eligibility."], TX, "Recommendations 1.1.1 and 1.4"),
    stage("The candidate also has obesity and is worried this makes assessment pointless. Other operative and functional information has not been gathered.",
          ["Which information is still needed?", "How would you discuss risk without declaring eligibility from BMI alone?"],
          ["Assess surgical suitability, body habitus, function and comorbidities with the transplant team.",
           "Do not exclude solely because of obesity; discuss modifiable risks and relevant center assessment criteria."], TX, "Recommendations 7.1-7.1.1"),
    stage("Review finds an indicated live attenuated vaccine has not been given. Transplant timing is elective and the candidate is not currently immunosuppressed.",
          ["How does anticipated immunosuppression affect the timing?", "What interval needs consideration before transplantation?"],
          ["Complete indicated vaccination in the pre-transplant window after checking vaccine-specific eligibility.",
           "Leave at least four weeks after a live vaccine before transplantation under the candidate guideline; use current specialist advice for the exact vaccine."], TX, "Recommendations 10.7.2-10.7.2.1"),
], ["Transplant preparation begins before dialysis.", "Risk assessment and prevention are part of candidate care, not an afterthought."])

case("RN-CASE-NEPHROTIC", "T10", ["T22", "T02"],
     ["T10.O01", "T22.O01"],
     "An antibody result and the purpose of biopsy",
     "Interpret a compatible membranous presentation without making serology answer every question.", [
    stage("A synthetic 52-year-old develops edema, proteinuria of 6.2 g/day and serum albumin 24 g/L. eGFR is 82. The person asks whether the normal filtration result means the kidneys are healthy.",
          ["What syndrome is present?", "What does preserved filtration fail to exclude?"],
          ["This is a nephrotic presentation needing cause assessment despite preserved filtration.",
           "Filtration, protein leakage and tissue diagnosis are different dimensions of kidney assessment."], GD, "Chapter 1; Practice Point 1.1.1"),
    stage("Anti-PLA2R antibodies are positive and the presentation is compatible with membranous nephropathy. There are no atypical serologic or clinical findings so far.",
          ["Is tissue required solely to establish this diagnosis?", "Which additional questions might tissue answer?"],
          ["In this compatible setting, a biopsy is not required solely to confirm membranous nephropathy.",
           "Tissue may still be useful for atypical features, kidney-function decline, prognosis or another unanswered clinical question."], GD, "Practice Point 3.1.1"),
    stage("The person assumes the positive antibody excludes every secondary association and means immunosuppression should begin immediately.",
          ["Which parts of the assessment remain open?", "How does a diagnosis differ from a treatment indication?"],
          ["Assess relevant associated conditions even with positive anti-PLA2R.",
           "Treatment decisions need risk assessment, disease course and safety considerations; antibody positivity is not an automatic prescription."], GD, "Practice Point 3.1.2; Chapter 3 risk assessment"),
], ["A positive disease marker may resolve one diagnostic question without resolving all others.", "Always state what a proposed biopsy is intended to change."])

case("RN-CASE-VASCULITIS", "T16", ["T10", "T06", "T22"],
     ["T16.O01", "T16.O02", "T10.O01"],
     "Biopsy matters, and so does the clock",
     "Balance urgent treatment and tissue diagnosis in rapidly progressive kidney vasculitis.", [
    stage("A synthetic 67-year-old has a creatinine rise from 105 to 360 micromol/L over a week, hematuria with casts, constitutional symptoms and new pulmonary symptoms.",
          ["What makes this a time-sensitive kidney presentation?", "What alternatives and extra-kidney involvement should be assessed?"],
          ["The rapid deterioration and nephritic findings require urgent specialist assessment.",
           "Evaluate for systemic vasculitis and important mimics, including infection; assess the pulmonary problem rather than assuming its cause."], AAV, "Diagnosis section; Practice Point 9.1.1"),
    stage("MPO-ANCA is positive. The multidisciplinary assessment finds a strongly compatible small-vessel vasculitis presentation and low suspicion of a mimic. Biopsy can be performed promptly but the report will be delayed.",
          ["How should the report delay affect urgent treatment?", "What qualifications prevent misuse of this principle?"],
          ["Treatment should not be delayed solely while awaiting biopsy or its report in this compatible rapidly deteriorating scenario.",
           "The rule depends on the full presentation and specialist assessment, not ANCA positivity alone."], AAV, "Practice Point 9.1.1"),
    stage("Treatment begins, and a trainee concludes that tissue no longer has any role. The patient asks why a biopsy is still being discussed.",
          ["What information can histology still provide?", "How would you explain the treatment-before-report decision?"],
          ["Biopsy can support diagnosis and characterize damage, activity and chronicity when safe and useful.",
           "Urgency and diagnostic value coexist: the decision to begin treatment does not imply the diagnosis is infallible or tissue is irrelevant."], AAV, "Practice Point 9.1.1; biopsy strategy"),
], ["Do not confuse a necessary urgent decision with diagnostic certainty.", "Tissue diagnosis and treatment timing answer related but different questions."])

case("RN-CASE-HYPERK", "T04", ["T20", "T07", "T19"],
     ["T04.O01", "T20.O01", "T07.O01"],
     "Protect, redistribute, remove and reassess",
     "Work through a severe potassium disturbance in a dialysis-dependent adult.", [
    stage("A synthetic maintenance hemodialysis patient missed treatment during an illness. Potassium is confirmed at 7.6 mmol/L and the ECG has a widening QRS. The patient is in a monitored acute-care setting.",
          ["Which treatment addresses immediate electrical toxicity?", "Why does an ECG abnormality change urgency?"],
          ["Indicated intravenous calcium protects the myocardium; it is not potassium removal.",
           "Treat the severe disturbance urgently with monitored care while arranging definitive removal."], K, "Guidelines 16.2 and 18.1-18.2"),
    stage("Insulin-glucose is given while urgent dialysis is being arranged. The first repeat potassium is lower and the person feels better.",
          ["What has insulin changed?", "Which adverse effect can appear after an initially reassuring check?"],
          ["Insulin shifts potassium into cells; the total potassium burden can remain.",
           "Monitor glucose for several hours for hypoglycemia and potassium for response and rebound."], K, "Guidelines 16.3 and 17.1-17.2"),
    stage("A team member suggests canceling dialysis because the potassium improved after redistribution. The patient has no functioning renal potassium-clearance reserve.",
          ["What treatment completes the removal step?", "What needs checking after dialysis and after recovery from the illness?"],
          ["Urgent dialysis supplies potassium removal in this severe dialysis-dependent scenario. A transient fall is not a substitute.",
           "Reassess potassium and the reason for the missed treatment; discuss a feasible plan for access to treatment during future illness."], K, "Guidelines 18.1-18.4"),
], ["Cardiac protection, redistribution and removal are distinct tasks.", "A response to treatment does not end monitoring."])

case("RN-CASE-HYPONA", "T03", ["T07", "T27"],
     ["T03.O01", "T03.O02", "T07.O01"],
     "The sodium number and the neurologic emergency",
     "Classify hypotonicity, treat severe symptoms and avoid uncontrolled correction.", [
    stage("A synthetic 46-year-old develops confusion and then a seizure. Sodium is 116 mmol/L, measured serum osmolality is 246 mOsm/kg, and glucose is normal. No exogenous effective osmole is identified.",
          ["How would you classify tonicity?", "Can all etiologic testing wait until after stabilization?"],
          ["The findings establish hypotonic hyponatremia in this specified setting.",
           "Severe attributable neurologic symptoms require urgent monitored treatment; collect relevant diagnostic samples promptly when feasible without delaying stabilization."], NA, "Sections 6.2 and 7.1.1"),
    stage("After initial monitored hypertonic treatment, symptoms improve with a modest sodium rise. The underlying medication and fluid-intake history are being reconstructed.",
          ["Why is immediate complete normalization not the goal?", "What should subsequent monitoring detect?"],
          ["The early goal is control of dangerous symptoms, while limiting cumulative correction to reduce demyelination risk.",
           "Frequent sodium reassessment and attention to urine output help identify an unexpectedly rapid rise."], NA, "Sections 7.1.2 and 7.5"),
    stage("Water excretion increases during recovery and sodium is rising faster than planned. The treating team reassesses the infusion and the correction trajectory.",
          ["What factors can cause correction to accelerate even after saline is stopped?", "What needs urgent senior review?"],
          ["An emerging water diuresis can accelerate sodium correction as the cause of antidiuresis resolves.",
           "Review cumulative correction, risk factors and the need for expert-directed measures to prevent or manage overcorrection. Exact rescue treatment belongs to the monitored clinical protocol."], NA, "Section 7.5: management of overly rapid correction"),
], ["Etiology matters, but severe symptoms set immediate priorities.", "The trajectory of correction is as important as the starting sodium."])

case("RN-CASE-ACIDOSIS", "T04", ["T08", "T19", "T27"],
     ["T04.O02", "T19.O01"],
     "Correcting acidosis without worsening congestion",
     "Evaluate persistent low bicarbonate and monitor benefits and harms of alkali.", [
    stage("A synthetic adult with CKD G4 has bicarbonate 16-17 mmol/L on repeated stable-state measurements. The clinical assessment is addressing alternative explanations and nutritional status. There is no acute cardiopulmonary emergency.",
          ["Why should chronic treatment not be selected from one result alone?", "What makes this a treatment discussion rather than an automatic prescription?"],
          ["Confirm persistence and assess the context of the acid-base disturbance.",
           "KDIGO suggests considering treatment for clinically important acidosis, with bicarbonate below 18 as an adult example; a practice point carries a different evidence status from a graded outcome claim."], CKD, "Practice Point 3.10.1"),
    stage("Oral alkali is chosen after discussion. Bicarbonate improves, but weight and blood pressure rise and ankle edema develops.",
          ["Does the improved bicarbonate prove treatment success?", "Which monitoring domains need attention?"],
          ["Biochemical correction must be balanced against treatment effects on fluid status and blood pressure.",
           "Review bicarbonate, potassium, BP and congestion, with adjustment of the plan rather than dose escalation based only on bicarbonate."], CKD, "Practice Point 3.10.2"),
    stage("The patient asks whether reaching a high bicarbonate value guarantees preservation of kidney function.",
          ["How would you describe the treatment goal and evidence limits?", "What would make the plan acceptable over time?"],
          ["Do not exceed the upper normal bicarbonate limit or promise an individual kidney-failure benefit.",
           "Aim for an appropriate individualized correction with tolerable fluid, potassium and BP effects and ongoing reassessment."], CKD, "Practice Points 3.10.1-3.10.2"),
], ["Monitor treatment harms alongside the number being corrected.", "Teach the evidence status without making a promise the source does not support."])

case("RN-CASE-MBD", "T05", ["T08", "T19"],
     ["T05.O01", "T05.O02"],
     "PTH is a trend, not a prescription",
     "Interpret CKD-MBD jointly and distinguish nondialysis decisions from dialysis pathways.", [
    stage("A synthetic adult with CKD G3b not on dialysis has a mildly increased PTH on one sample. Calcium is normal and phosphate has remained normal. A trainee proposes immediate calcitriol.",
          ["Which results and trends should be considered together?", "What modifiable contributors need assessment?"],
          ["Review serial calcium, phosphate and PTH rather than interpreting one PTH value alone.",
           "Consider vitamin D status, intake and other modifiable factors before deciding on treatment."], MBD, "Recommendations 4.1.1 and 4.2.1"),
    stage("Repeated values show only modest PTH elevation, with no severe progressive hyperparathyroidism and no hyperphosphatemia.",
          ["Is routine active vitamin D justified by this pattern?", "Would a preventive phosphate binder fit the guidance?"],
          ["Do not routinely prescribe calcitriol or analogs in nondialysis adult G3a-G5; severe progressive G4-G5 hyperparathyroidism is a distinct context.",
           "Phosphate-lowering treatment is driven by progressively or persistently elevated phosphate rather than a normal level."], MBD, "Recommendations 4.2.2 and 4.1.5"),
    stage("The patient wants a simple explanation of why repeat testing is useful when none of the numbers is dramatic.",
          ["What can a trend reveal that a single value cannot?", "How would you agree a follow-up plan without overpromising?"],
          ["Trends show persistence, direction and effects of interventions; calcium, phosphate and PTH influence each other.",
           "Explain the purpose of monitoring and the clinical changes that would prompt a different decision."], MBD, "Recommendations 3.1.4 and 4.1.1"),
], ["Use joint serial interpretation.", "An abnormal result does not always imply benefit from immediately lowering it."])

case("RN-CASE-DIABETES", "T14", ["T09", "T19", "T08"],
     ["T14.O01", "T14.O02", "T09.O01", "T19.O01"],
     "Layering protection and checking tolerance",
     "Plan treatment for diabetic CKD without treating every creatinine change as a reason to stop.", [
    stage("A synthetic adult with type 2 diabetes has eGFR 44, ACR 390 mg/g and hypertension. A rushed clinic BP reading is higher than the home readings. RAS blockade has been proposed.",
          ["How should the measurement discrepancy be evaluated?", "What baseline monitoring supports treatment?"],
          ["Use standardized office measurement and appropriate out-of-office information; a rushed value is not interchangeable with the standardized target.",
           "Review BP, kidney function, potassium and contraindications before treatment, and explain the monitoring plan."], BP, "Recommendations 1.1-1.2"),
    stage("After an indicated ACE inhibitor dose change, creatinine is 18% above baseline at two weeks, potassium remains normal and the person has no hypotensive symptoms.",
          ["Does this change alone require stopping the medicine?", "What should be checked before interpreting it?"],
          ["A rise below 30% in this time frame does not itself meet the KDIGO threshold prompting discontinuation; assess the full context and continue monitoring.",
           "Review volume, intercurrent illness, interacting medicines, potassium and tolerance rather than assuming the drug has caused irreversible injury."], CKD, "Practice Points 3.6.2-3.6.5"),
    stage("Persistent albuminuria remains, and the person asks about additional kidney-protective treatment and an upcoming operation with fasting.",
          ["What does layered treatment add to the discussion?", "What safety plan is needed if an SGLT2 inhibitor is used?"],
          ["Discuss an eligible SGLT2 inhibitor and, where appropriate, an evidence-based nonsteroidal MRA with potassium monitoring rather than adding dual RAS blockade.",
           "Explain interruption during prolonged fasting, surgery or critical illness and a documented restart review."], CKD, "Recommendations 3.7.1-3.7.2 and 3.8.1; Practice Point 3.7.2"),
], ["Measurement quality and tolerance are part of treatment selection.", "Layer protection while making monitoring and temporary interruption explicit."])

case("RN-CASE-ADPKD", "T12", ["T06", "T19"],
     ["T12.O01", "T12.O02", "T19.O02"],
     "Progression risk and the tolvaptan sick-day plan",
     "Connect disease-modifying eligibility to aquaresis education and interruption planning.", [
    stage("A synthetic 36-year-old with confirmed ADPKD has eGFR 62. Serial and imaging assessment supports rapid progression after other causes of declining kidney function are considered. The patient asks whether every person with cysts should take tolvaptan.",
          ["What establishes the appropriate treatment population?", "What eligibility and risk checks remain?"],
          ["Confirmed ADPKD and risk of rapid progression distinguish the eligible population from incidental cysts.",
           "The guideline recommends initiation in adults with eGFR at least 25 and rapid-progression risk, after contraindication and individualized benefit-risk assessment."], PKD, "Recommendation 4.1.1.1; Practice Points 4.1.1.1-4.1.2.1"),
    stage("The person starts treatment and reports frequent urination, thirst and nocturia. They have an occupation with occasional limited access to drinking water.",
          ["How would you explain the mechanism-related burden?", "What practical safety education should be given?"],
          ["Tolvaptan increases urinary water losses, so access to water and adequate replacement are central to tolerability and safety.",
           "Discuss daily activities, adverse effects, required liver monitoring and how to respond when water replacement or monitoring is not possible."], PKD, "Practice Points 4.1.4.1-4.1.5.1"),
    stage("During a vomiting illness the patient cannot drink enough. A friend suggests continuing the medicine because missed doses will always be dangerous.",
          ["What does the interruption plan say?", "What information should guide restarting?"],
          ["Interrupt treatment in volume-depleting illness or inability to compensate for aquaresis; this is the purpose of a sick-day plan.",
           "Seek advice, assess recovery and hydration, and document the conditions for resumption rather than continuing through dehydration."], PKD, "Practice Points 4.1.4.3-4.1.4.4"),
], ["Risk-based selection and monitoring are integral to disease-modifying treatment.", "An interruption plan protects the patient when usual hydration is not possible."])

case("RN-CASE-SUPPORTIVE", "T26", ["T20", "T24", "T25"],
     ["T26.O01", "T20.O02", "T24.O01", "T25.O02"],
     "What matters when treatment is burdensome",
     "Discuss active conservative care and avoid nutrition rules that ignore frailty.", [
    stage("A synthetic older adult with kidney failure, frailty and weight loss values comfort and time at home. They ask whether choosing not to start dialysis means their kidney team will stop seeing them.",
          ["How would you explain comprehensive conservative care?", "Which goals and support needs should be elicited?"],
          ["Conservative care is active symptom management and support without dialysis, not abandonment.",
           "Discuss goals, symptoms, function, family or social support and preferences for future care."], CKD, "Practice Points 5.5.1-5.5.2; Table 43"),
    stage("A family member proposes a very low-protein diet despite the person's poor appetite and ongoing weight loss.",
          ["How does nutritional instability change the decision?", "Who can help individualize the plan?"],
          ["A restrictive regimen can add harm in frailty or nutritional instability; do not apply nondialysis targets without assessing the patient.",
           "Use individualized dietetic assessment, balancing symptom control and nutrition with the person's goals."], CKD, "Practice Points 3.3.1.3 and 3.3.1.5"),
    stage("The person makes an informed conservative-care choice but wants the option to revisit preferences if circumstances change.",
          ["What should ongoing care and planning include?", "How can the team preserve agency?"],
          ["Continue symptom-focused care, support and advance care planning with clear contact and follow-up arrangements.",
           "Document the person's priorities and review them as circumstances change. Decisions should not be treated as a reason to withhold useful communication or care."], CKD, "Practice Points 5.5.1-5.5.2; Table 43"),
], ["Conservative kidney care is a positive active care plan.", "Nutrition and treatment burden should be judged in the person's life context."])

case("RN-CASE-LUPUS", "T16", ["T10", "T22"],
     ["T16.O01", "T10.O01", "T22.O01"],
     "Preserved filtration does not settle a lupus kidney question",
     "Use urine findings and tissue evaluation to investigate possible lupus nephritis.", [
    stage("A synthetic 29-year-old with SLE has preserved eGFR but newly detected urine protein and hematuria. They ask whether a normal creatinine rules out kidney involvement.",
          ["Which screening domains are relevant?", "What can creatinine alone fail to show?"],
          ["Assess urine, protein excretion, kidney function and relevant serology together.",
           "Preserved filtration does not exclude an active glomerular process."], LN, "Practice Point 10.1.1; Figure 1"),
    stage("Protein excretion is confirmed at 0.9 g/day and urinary sediment remains abnormal. There is no alternative explanation after initial assessment.",
          ["Why should biopsy be considered?", "Is the protein threshold a substitute for the full assessment?"],
          ["The diagnostic pathway suggests considering biopsy at proteinuria at least 500 mg/day in the appropriate context.",
           "Integrate the pattern, persistence, kidney function and clinical setting rather than treating one threshold as an automatic rule."], LN, "Figure 1; diagnosis section"),
    stage("The patient wants to understand why blood tests have not already specified the treatment pathway.",
          ["What information can tissue add?", "How would you explain the difference between suspicion and classification?"],
          ["Biopsy characterizes the kidney lesion and can assess activity and chronicity, supporting management decisions.",
           "Serology and urine findings can establish a reason to investigate without specifying the histologic class."], LN, "Diagnosis section; kidney biopsy assessment"),
], ["Normal filtration does not exclude lupus kidney involvement.", "Tissue evaluation can change what a kidney diagnosis means for treatment."])


def publish_snapshot(path: Path, *, version: str, topics, sources, cases, questions,
                     target_topics, minimum_questions: int, withdrawals=()):
    """Reuse the original publisher for additive, immutable content releases."""
    coverage = coverage_for(topics, cases, questions, target_topics, minimum_questions)
    bundle = {"topics": topics, "sources": sources, "cases": cases,
              "questions": questions, "coverage": coverage}
    blobs = {f"{name}.json": (json.dumps(body, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
             for name, body in bundle.items()}
    manifest = {
        "schema_version": 1, "repository_contract": 1, "id": "renulus-foundations",
        "version": version, "state": "published", "published_on": DATE,
        "title": "Renulus foundations: cross-domain original learning",
        "license": "CC-BY-4.0", "authors": ["Renulus contributors (assistant-authored initial pack)"],
        "attribution": f"Renulus foundations {version}, Renulus contributors, CC BY 4.0. Identify any subsequent changes. Primary medical sources retain their own rights.",
        "source_register": "docs/SOURCES.md",
        "files": {name: {"path": f"{name}.json",
                           "sha256": hashlib.sha256(blobs[f"{name}.json"]).hexdigest()} for name in bundle},
        "claims": {"complete_curriculum": False, "complete_esen_eph_blueprint": False,
                   "independent_human_review": False}, "withdrawals": list(withdrawals),
    }
    blobs["manifest.json"] = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
    for name, raw in blobs.items():
        target = path / name
        if target.exists() and target.read_bytes() != raw:
            raise SystemExit(f"Refusing to alter published snapshot: {target}. Publish a new version.")
    path.mkdir(parents=True, exist_ok=True)
    for name, raw in blobs.items():
        target = path / name
        if not target.exists():
            target.write_bytes(raw)
    pack = validate_pack(path)
    return {"pack": pack.manifest["id"], "version": pack.manifest["version"],
            "topics": len(topics), "objectives": sum(len(t["objectives"]) for t in topics),
            "questions": len(questions), "cases": len(cases), "sha256": pack.sha256}


def publish(path: Path):
    return publish_snapshot(path, version="1.0.0", topics=TOPICS, sources=SOURCES,
                            cases=CASES, questions=QUESTIONS,
                            target_topics=["T03", "T04", "T06", "T08", "T10", "T20", "T21"],
                            minimum_questions=40)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=PACK)
    args = parser.parse_args()
    print(json.dumps(publish(args.output), indent=2))
