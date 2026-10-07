# SPDX-License-Identifier: MIT
"""Original, source-checked expansion using the existing question/publisher tools.

The released 1.0.0 snapshots, including embedded source metadata, stay identical.
Only independently expressed medical facts and synthetic scenarios are published.
No manual, examination-bank item or primary-source prose is reproduced.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import author_foundations as base

ROOT = base.ROOT
DATE = base.DATE
ORIGINAL_QUESTIONS = deepcopy(base.QUESTIONS)
ORIGINAL_CASES = deepcopy(base.CASES)
TOPICS = deepcopy(base.TOPICS)
SOURCES = deepcopy(base.SOURCES)
NEW_QUESTIONS = []
NEW_CASES = []
EVIDENCE = []
_QUESTION_POOL = deepcopy(ORIGINAL_QUESTIONS)
_CASE_POOL = deepcopy(ORIGINAL_CASES)


def source(sid, rid, title, edition, url, topic_url, scope, check_note):
    SOURCES.append({
        "id": sid, "register_id": rid, "title": title, "edition": edition,
        "publication_status": "final", "url": url, "canonical_topic_url": topic_url,
        "checked_on": DATE, "check_status": "locator_checked",
        "currency": "dated_final_baseline", "scope": scope,
        "rights_note": "Factual reference and citation metadata only. The primary document keeps its own terms; its prose, algorithms, figures and questions are neither distributed nor relicensed. This is not permission to import it into another AI workflow.",
        "check_note": check_note,
    })


CKD, AKI, GD, MBD, BP, DM, PKD, AAV, LN, TX, DONOR, K, NA = (
    "K01-2024-expansion", "K10-2012-expansion", "K08-2021-remaining-expansion",
    "K13-2017-expansion", "K11-2021-expansion", "K09-2022-expansion",
    "K03-2025-expansion", "K05-2024-expansion", "K06-2024-expansion",
    "K16-2020-expansion", "K15-2017-donor",
    "G02-hyperkalemia-2026-07", "G01-hyponatremia-2014-expansion",
)
HD, PD, PREG, STONE, OBSTRUCT, MGRS, TTP, RTA, EOS = (
    "G02-haemodialysis-2019", "G02-peritoneal-dialysis-2017",
    "G02-pregnancy-renal-2019", "L01-CUA-stones-2022",
    "L01-CUA-ureteral-2021", "L01-IKMG-evaluation-2019",
    "L01-ISTH-TTP-diagnosis-2020", "G01-ERKNet-dRTA-2021",
    "L01-urine-eosinophils-2013",
)

# New IDs prevent edits to source_records already pinned by 1.0.0 questions.
for sid, old_id, scope in [
    (CKD, base.CKD, "Adult CKD measurement, risk, medicines, nutrition, monitoring and supportive care; no sole-current status claimed."),
    (AKI, base.AKI, "Dated 2012 final: staging, diagnostic context, hemodynamics and KRT physiology/delivery. The 2026 draft is not substituted."),
    (GD, base.GD, "Remaining 2021 chapters 1, 3, 5, 6 and 7: biopsy/urine interpretation, membranous disease, adult MCD/FSGS, infection evaluation. Replaced IgAN, childhood nephrotic, ANCA and lupus scope excluded."),
    (MBD, base.MBD, "Dated 2017 final: adaptive PTH, turnover markers, binder and active-vitamin-D risks."),
    (BP, base.BP, "Dated 2021 final: standardized/out-of-office measurement and individualized treatment tolerance."),
    (DM, base.DM, "Dated 2022 final: SGLT2 hemodynamics, HbA1c limitations and metformin monitoring. No 2026 draft-derived key."),
    (PKD, base.PKD, "2025 final: familial diagnosis, imaging-based progression, tolvaptan and aneurysm-screening reasoning."),
    (AAV, base.AAV, "2024 amended final: interpret ANCA in phenotype and balance biopsy with treatment urgency; no copied induction algorithm."),
    (LN, base.LN, "2024 final: biopsy activity/chronicity, hydroxychloroquine, response monitoring and TMA diagnostic pathways; no copied treatment algorithm."),
    (TX, base.TX, "Dated 2020 candidate final: vaccination, active infection, HLA assessment and individualized cancer risk. No recipient drug regimen."),
    (K, base.K, "July 2026 updated UK final: sampling, redistribution/removal, medication contributors and hypoglycemia/rebound monitoring. Review due October 2026."),
    (NA, base.NA, "Dated 2014 European final and identified erratum: hypotonicity, urine measurements, diuretic confounding and water-diuresis correction risk."),
]:
    old = next(s for s in base.SOURCES if s["id"] == old_id)
    source(sid, old["register_id"], old["title"], old["edition"], old["url"],
           old["canonical_topic_url"], scope,
           "Assistant checked the primary public sections/numbered recommendations cited by the expansion. Some KDIGO recommendations were checked through exact indexed official material where the PDF parser failed. New scope record; original source snapshots are preserved.")

updated_k = next(s for s in SOURCES if s["id"] == K)
updated_k.update({
    "edition": "October 2023 final; July 2026 update; review due October 2026",
    "url": "https://www.ukkidney.org/sites/default/files/documents/FINAL%20VERSION%20-%20UKKA%20CLINICAL%20PRACTICE%20GUIDELINE%20-%20MANAGEMENT%20OF%20HYPERKALAEMIA%20IN%20ADULTS%20-%20UPDATED%20JULY%202026_0.pdf",
    "canonical_topic_url": "https://www.ukkidney.org/health-professionals/guidelines/treatment-acute-hyperkalaemia-adults-0",
    "check_note": "Assistant opened the 180-page primary final PDF. Frontmatter confirms July 2026; printed pages 5 and 7 describe updated chronic-binder guidance and weaker calcium evidence grading. Cited sampling/treatment-monitoring sections checked separately. Original 2023 source metadata remains unchanged for inherited items.",
})
next(s for s in SOURCES if s["id"] == CKD)["check_note"] = (
    "Assistant checked numbered primary recommendations and sections, including in-memory reading of the official 199-page PDF: printed S151 (marker error), S154-S155 (urine measurement/monitoring), S165 (medicine measurement/dosing summary), and S247 (medicine mechanisms). Some other KDIGO locator checks used indexed official material after browser-parser failure. Source originals are not stored or distributed; no exhaustive currency clearance.")

source(DONOR, "K15", "KDIGO living kidney donor", "2017 final",
       "https://kdigo.org/wp-content/uploads/2017/07/2017-KDIGO-LD-GL.pdf",
       "https://kdigo.org/guidelines/living-kidney-donor/",
       "Dated donor baseline: measured/estimated GFR, autonomy, albuminuria and pregnancy counseling; not recipient therapy.",
       "Assistant read the official primary 2017 PDF in memory: recommendations 2.1-2.8 (printed S27), 5.1-5.8 (S35-S36), 6.1-6.6 (S42), and 15.1-15.11 (S78). Thresholds and scope are donor-specific. No source original is stored; dated baseline, not an exhaustive subsequent-evidence clearance.")
source(HD, "G02", "Renal Association clinical practice guideline on haemodialysis", "2019 final",
       "https://bmcnephrol.biomedcentral.com/articles/10.1186/s12882-019-1527-3",
       "https://www.ukkidney.org/health-professionals/guidelines/guidelines-commentaries",
       "Dated primary UK guideline: urea-dose interpretation, fluid removal, residual function and clearance physiology. No claim that every 2019 prescription remains current.",
       "Primary BMC guideline DOI/title/year and sections 1, 2, 4 and appendices checked; article CC BY terms remain independent.")
source(PD, "G02", "Renal Association clinical practice guideline on peritoneal dialysis in adults and children", "2017 final",
       "https://bmcnephrol.biomedcentral.com/articles/10.1186/s12882-017-0687-2",
       "https://www.ukkidney.org/health-professionals/guidelines/guidelines-commentaries",
       "Dated primary UK baseline limited to membrane transport, ultrafiltration and residual kidney function. No peritonitis antibiotic regimen or current adequacy certification.",
       "Primary BMC guideline title/DOI and membrane/ultrafiltration sections checked. Later treatment-specific guidance must be assessed separately.")
source(PREG, "G02", "Clinical practice guideline on pregnancy and renal disease", "2019 final",
       "https://bmcnephrol.biomedcentral.com/articles/10.1186/s12882-019-1560-2",
       "https://www.ukkidney.org/health-professionals/guidelines/guidelines-commentaries",
       "Dated primary UK baseline: serum creatinine rather than eGFR, superimposed preeclampsia assessment and biopsy timing.",
       "Assistant checked primary recommendations 4.1.1, 4.4.5-4.4.6 and 4.8.1 in the published BMC guideline.")
source(STONE, "L01", "Canadian Urological Association guideline: evaluation and medical management of kidney stones", "2022 update",
       "https://cuaj.ca/index.php/journal/article/view/7872",
       "https://doi.org/10.5489/cuaj.7872",
       "Primary Canadian guideline facts for metabolic evaluation, dietary calcium and low-pH uric acid stones; jurisdiction and edition retained.",
       "Official CUAJ catalogue title/year/DOI and primary indexed full-text sections checked; direct PDF parsing failed. Copyright (c) 2022 CUAJ. L01 is bibliography/reference provenance, not an open full-text or AI reuse grant.")
source(OBSTRUCT, "L01", "Canadian Urological Association guideline: management of ureteral calculi", "2021 full-text final",
       "https://cuaj.ca/index.php/journal/article/view/7581",
       "https://doi.org/10.5489/cuaj.7581",
       "Primary Canadian baseline: infected obstruction and limits of expectant management; no borrowed intervention algorithm.",
       "Official CUAJ title/year/DOI and obstructive-pyelonephritis/renal-impairment sections checked. Source text is not distributed.")
source(MGRS, "L01", "IKMG consensus: evaluation of monoclonal gammopathy of renal significance", "2019 final (published online 2018)",
       "https://www.nature.com/articles/s41581-018-0077-4",
       "https://doi.org/10.1038/s41581-018-0077-4",
       "Dated diagnostic consensus: renal biopsy, light-chain proximal tubulopathy and interpretation of monoclonal tests. No clone-directed regimen.",
       "Assistant read the primary author-repository copy at https://discovery.ucl.ac.uk/10064523/1/s41581-018-0077-4.pdf, printed pages 45-56. No exhaustive currency clearance or treatment review claimed.")
source(TTP, "L01", "ISTH guidelines for the diagnosis of thrombotic thrombocytopenic purpura", "2020 final diagnostic guideline",
       "https://pmc.ncbi.nlm.nih.gov/articles/PMC8146131/",
       "https://doi.org/10.1111/jth.15006",
       "Primary diagnosis baseline: pretreatment ADAMTS13 sampling, severe deficiency and time-critical evaluation. 2025 focused treatment changes are not copied into this diagnostic scope.",
       "Primary author manuscript/indexed guideline checked. The 2025 focused update retains 2020 iTTP recommendations and changes congenital treatment; no congenital treatment key authored here. L01 does not assert open redistribution rights.")
source(RTA, "G01", "ERKNet/ESPN distal renal tubular acidosis clinical practice points", "2021 final",
       "https://academic.oup.com/ndt/article/36/9/1585/6259151",
       "https://doi.org/10.1093/ndt/gfab171",
       "Primary European consensus: normal-anion-gap acidosis, urine acidification, stone risk and distinction from proximal wasting.",
       "Primary NDT consensus diagnostic/pathophysiology sections checked. Public reading availability is not a blanket AI-processing or redistribution permission.")
source(EOS, "L01", "Utility of urine eosinophils in the diagnosis of acute interstitial nephritis", "2013 original biopsy-linked diagnostic study; 2018 correction checked",
       "https://pmc.ncbi.nlm.nih.gov/articles/PMC3817898/",
       "https://doi.org/10.2215/CJN.01330213",
       "Original diagnostic-accuracy study; a negative or positive urine-eosinophil result does not alone establish or exclude AIN. No steroid-efficacy claim.",
       "Assistant checked the primary PubMed/Europe PMC abstract and the full correction notice (DOI 10.2215/CJN.05270418, PMID 29848506, https://pmc.ncbi.nlm.nih.gov/articles/PMC6032594/?report=xml). The notice removes the erroneous denominator phrase in one Results sentence; no replacement performance table is specified. The qualitative weak-discrimination claim is checked; numeric performance is not re-audited. Original full text remained browser-blocked. A dated study is not a current treatment guideline.")


def q(topic, number, objective, source_id, locator, stem, correct, wrong, rationale,
      *, secondary=(), skill="interpretation", extra_sources=(), calculation=None):
    identity = f"RN11-{topic}-{number:03d}"
    base.q(identity, topic, objective, source_id, locator, stem, correct, wrong,
           rationale, secondary=secondary, difficulty="integration" if secondary else "application",
           items=_QUESTION_POOL)
    item = _QUESTION_POOL[-1]
    item["sources"].extend(base.cite(s, loc) for s, loc in extra_sources)
    item["review"]["method"] = (
        "Assistant primary section/locator check, units and single-key/distractor review; "
        f"original synthetic {skill} scenario. Evidence identity: {identity}. No independent human review.")
    NEW_QUESTIONS.append(item)
    EVIDENCE.append({"id": identity, "version": 1, "kind": "question",
                     "skill": skill, "source_locators": deepcopy(item["sources"]),
                     "reviewed_on": DATE, "reviewer_kind": "assistant",
                     "key_text": correct, "checked_claim": rationale,
                     "calculation": calculation, "independent_human_review": False})


# First coherent increment: two questions per topic, including all earlier gaps.
q("T01", 1, 2, CKD, "Table 31, printed S247: reversible inhibition of tubular creatinine secretion; Section 1.2.2",
  "Creatinine rises shortly after trimethoprim is started, while cystatin C and urine findings are unchanged. Which mechanism could explain discordant filtration estimates?",
  "Inhibited tubular creatinine secretion without a matching fall in filtration.",
  [("Increased creatinine production is an obligatory effect of any antibiotic.", "This is not the characteristic trimethoprim effect."),
   ("A higher creatinine must mean the same proportional reduction in measured GFR.", "Secretion is a non-GFR determinant of creatinine."),
   ("Normal cystatin C proves that all kidney adverse effects can be ignored.", "A possible marker effect does not exclude concurrent toxicity or potassium changes.")],
  "Creatinine includes a secretion component. A secretion inhibitor can alter creatinine-based eGFR without an equivalent filtration change; assess the whole clinical pattern rather than automatically diagnosing or excluding AKI.", secondary=("T19",), skill="mechanism")
q("T01", 2, 1, CKD, "Practice Point 4.2.4: nonindexed eGFR in extremes of body weight",
  "For a drug dosed using absolute GFR, an adult has indexed eGFR 45 mL/min/1.73 m2 and body surface area 1.20 m2. What is the corresponding nonindexed estimate?",
  "About 31 mL/min.",
  [("45 mL/min regardless of body size.", "The reported estimate is normalized to 1.73 m2."),
   ("About 65 mL/min.", "Dividing by the smaller body surface area reverses the conversion."),
   ("About 54 mL/min.", "Multiplying by 1.20 alone leaves the normalization uncorrected.")],
  "Absolute GFR is estimated as 45 x 1.20 / 1.73 = 31.2 mL/min. Check the medicine's specified dosing metric and the precision required; the conversion does not remove estimation error.", secondary=("T19",), calculation={"expression": "45 * 1.20 / 1.73", "result": 31.21387283236994, "unit": "mL/min"})
q("T02", 1, 1, MGRS, "Monoclonal immunoglobulin testing; urine protein electrophoresis",
  "Urine PCR is 3.8 g/g but ACR is 0.25 g/g. Which interpretation should guide the next investigation?",
  "Much of the measured protein is nonalbumin; investigate its type and source.",
  [("The low ACR excludes important proteinuria.", "ACR measures albumin, whereas PCR includes other proteins."),
   ("The discrepancy alone proves diabetic glomerular disease.", "Diabetes is not established by a nonalbumin protein pattern."),
   ("A monoclonal malignancy is proven without further testing.", "A discrepancy is a clue, not a clonal diagnosis.")],
  "Marked total protein with much less albumin raises a nonalbumin-protein question, including tubular or light-chain protein. Electrophoresis/immunofixation and clinical assessment can characterize it; do not infer a clone from the ratio alone.", secondary=("T18",))
q("T02", 2, 2, GD, "Practice Point 1.3.1: urine sediment in glomerular disease",
  "AKI, dysmorphic urinary erythrocytes and erythrocyte casts are found together. What can the sediment establish most directly?",
  "A glomerular inflammatory pattern that warrants etiologic evaluation.",
  [("The exact histologic class is already known.", "Sediment cannot distinguish all glomerular lesions."),
   ("Urinary infection is the only plausible cause.", "Casts and dysmorphism direct attention to glomerular bleeding."),
   ("A normal ultrasound would exclude the suspected process.", "Normal anatomy does not exclude microscopic glomerular disease.")],
  "Active sediment localizes a kidney process and increases urgency. Serology, chronology and often tissue are still needed to identify its cause and treatment pathway.", secondary=("T10", "T06"))
q("T03", 1, 1, NA, "Recommendations 6.3.1.1-6.3.1.2; urine-osmolality interpretation",
  "Serum sodium is 123 mmol/L with low measured serum osmolality. Urine osmolality is 70 mOsm/kg. What does the urine result suggest?",
  "Water excretion is relatively unsuppressed; consider water intake relative to solute intake.",
  [("It is the concentrated urine expected from persistent strong antidiuresis.", "Urine below 100 mOsm/kg is dilute."),
   ("It proves adrenal insufficiency.", "A dilute result does not diagnose a specific endocrine disorder."),
   ("It converts hypotonic hyponatremia into pseudohyponatremia.", "Measured serum hypotonicity has already been established.")],
  "Very dilute urine in hypotonic hyponatremia points toward water intake exceeding available solute-dependent excretory capacity rather than sustained antidiuresis. The intake history and clinical context still matter.", skill="mechanism")
q("T03", 2, 2, NA, "Section 7.4.4: sudden urine-output increase during correction",
  "After volume replacement for hyponatremia, urine output rises abruptly and the urine becomes dilute. Why should sodium monitoring intensify?",
  "A water diuresis can make sodium rise faster than the prescribed-fluid calculation predicts.",
  [("Dilute urine guarantees that sodium will remain unchanged.", "Loss of electrolyte-free water can raise serum sodium."),
   ("Only administered sodium can increase serum sodium.", "Water loss can change the concentration without added sodium."),
   ("The event proves a new fixed diagnosis of diabetes insipidus.", "Resolution of a volume stimulus can suppress antidiuresis transiently.")],
  "Restoring volume can remove a nonosmotic antidiuretic stimulus. Abrupt water excretion is a warning for unintended overcorrection and calls for close urine-output and sodium review.", secondary=("T07",), skill="mechanism")
q("T04", 1, 1, K, "Guidelines 15.1-15.3: sampling and pseudohyperkalemia",
  "An unexpected potassium of 6.4 mmol/L is reported from a visibly hemolyzed sample in a well adult. What is the safest interpretation?",
  "Possible sample artifact requires prompt appropriate repeat assessment; do not dismiss true hyperkalemia.",
  [("Hemolysis proves the patient's potassium is normal.", "It can cause artifact but does not exclude a simultaneous real disturbance."),
   ("The result proves a chronic need for dialysis.", "A compromised single sample cannot establish this."),
   ("A normal ECG removes the need to check the potassium.", "ECG sensitivity for hyperkalemia is limited.")],
  "Release of intracellular potassium during sampling can elevate the measured value. Repeat using an appropriate collection method while assessing urgency, risk factors and ECG; a suspected artifact is not a safety clearance.", secondary=("T02",))
q("T04", 2, 2, RTA, "Diagnosis and pathophysiology: normal-anion-gap acidosis and impaired urine acidification",
  "An adult with preserved filtration has pH 7.30, Na 140, Cl 112 and bicarbonate 18 mmol/L, normal albumin, hypokalemia and persistent urine pH 6.4. Infection and diarrhea are excluded. Which pattern fits best?",
  "Normal-anion-gap acidosis with impaired distal urinary acidification.",
  [("A primary high-anion-gap process is proven by these electrolytes.", "The calculated gap is 10 mmol/L, within a usual reference range."),
   ("Alkaline urine excludes a kidney acidification problem.", "Inappropriate failure to acidify urine during acidosis is the clue."),
   ("Hypokalemia excludes renal tubular acidosis.", "Distal RTA commonly includes potassium depletion.")],
  "The anion gap is 140 - 112 - 18 = 10 mmol/L. Persistent inappropriately high urine pH during systemic acidosis, after relevant confounders are excluded, supports a distal acidification defect; a single urine pH alone is insufficient.", secondary=("T11", "T13"), calculation={"expression": "140 - 112 - 18", "result": 10, "unit": "mmol/L"})
q("T05", 1, 1, MBD, "Recommendation 4.2.1 and rationale: adaptive PTH response",
  "In nondialysis CKD, PTH is mildly above the assay range on one occasion, with normal calcium and phosphate. Which reasoning is most appropriate?",
  "Assess trends and modifiable drivers; a modest rise can be adaptive.",
  [("Any elevation proves autonomous parathyroid disease.", "CKD-related adaptation and modifiable factors are alternatives."),
   ("Immediately normalize PTH with active vitamin D regardless of trend.", "A single mild elevation is not that indication."),
   ("PTH has no relevance until dialysis begins.", "Its trend is part of nondialysis CKD-MBD evaluation.")],
  "The optimal nondialysis PTH concentration is not established. A rising or persistently elevated value prompts evaluation of phosphate exposure, calcium and vitamin D status, rather than automatic normalization of a single result.", skill="common_reasoning")
q("T05", 2, 2, MBD, "Recommendations 4.1.3 and 4.1.6: hypercalcemia and calcium-based binders",
  "A dialysis patient receiving a calcium-based binder develops repeated hypercalcemia and low PTH. What treatment concern should be reviewed?",
  "Excess calcium exposure and possible low-turnover bone disease.",
  [("Low PTH requires still more calcium binder to stimulate turnover.", "Additional calcium can suppress PTH further."),
   ("Phosphate control makes calcium exposure irrelevant.", "Binder benefit must be balanced against calcium-related harm."),
   ("One low PTH result alone establishes the exact bone histology.", "Markers inform probability; they do not perfectly identify histology.")],
  "Review the serial biochemical pattern and calcium-containing therapies. Guidelines favor avoiding hypercalcemia and restricting calcium-based binder exposure; low turnover is a concern, not a biopsy-free certainty.", secondary=("T20",), skill="mechanism")
q("T06", 1, 1, AKI, "Table 2; Recommendation 2.1.2: urine-output staging",
  "An adult with a patent catheter produces 0.25 mL/kg/h of urine for 14 consecutive hours. Creatinine has not yet risen. Which AKI stage is supported by urine output?",
  "Stage 2.",
  [("No AKI can be identified without a creatinine rise.", "Urine output is an independent staging criterion."),
   ("Stage 1 only, because creatinine is stable.", "Less than 0.5 mL/kg/h for at least 12 hours meets stage 2."),
   ("Stage 3 from this duration alone.", "The less-than-0.3 criterion requires at least 24 hours, or anuria for at least 12 hours.")],
  "Fourteen hours below 0.5 mL/kg/h meets stage 2. Despite the low rate, the duration does not meet the stage-3 oliguria threshold. Examine causes and trends without waiting for creatinine to catch up.", secondary=("T07",))
q("T06", 2, 2, AKI, "Sections 2.3 and 3.5: cause evaluation and diuretic effects on fractional sodium excretion",
  "After a loop diuretic, a patient with AKI has fractional sodium excretion of 2.5%. What is the best use of this result?",
  "Interpret it with treatment timing and the clinical pattern; it does not independently classify the cause.",
  [("It proves tubular necrosis despite the diuretic.", "Diuresis changes sodium handling and can confound the test."),
   ("It excludes reduced effective circulating volume.", "A confounded urinary index cannot reliably exclude that state."),
   ("It establishes a need for immunosuppression.", "This index does not identify an immune lesion.")],
  "Urinary indices are contextual measurements. Medication exposure, CKD, timing, urine sediment and hemodynamics must be integrated before attributing AKI to a mechanism.", secondary=("T19",), skill="common_reasoning")
q("T07", 1, 2, AKI, "Recommendation 5.6.2: continuous versus standard intermittent KRT",
  "A ventilated adult needs KRT and remains dependent on substantial vasopressor support. Which modality consideration is best supported?",
  "Continuous KRT can permit more gradual fluid/solute management in hemodynamic instability.",
  [("Intermittent treatment is mandatory in every ICU patient.", "Hemodynamic tolerance influences modality choice."),
   ("Continuous treatment has proven universal survival superiority.", "The recommendation does not establish that claim."),
   ("Vasopressors eliminate any indication for kidney support.", "Instability changes delivery, not the presence of an indication.")],
  "The dated KDIGO final suggests continuous rather than standard intermittent KRT for unstable patients. Modality supports tolerability and goals; it should not be presented as a guaranteed survival advantage.", secondary=("T23", "T20"))
q("T07", 2, 1, AKI, "Recommendation 5.8.4; rationale: prescribed versus delivered CRRT dose",
  "CRRT is prescribed at 25 mL/kg/h, but frequent circuit downtime reduces delivery. Which assessment is most useful?",
  "Review actual delivered clearance and downtime rather than the prescription alone.",
  [("The written prescription guarantees the intended clearance.", "Treatment interruptions reduce delivered dose."),
   ("Only the filter brand determines delivery.", "Time on treatment, flow and circuit function matter."),
   ("Any higher dose must improve survival proportionally.", "Intensive dosing beyond standard targets has not shown that relationship.")],
  "The 2012 final recommends delivered effluent of 20-25 mL/kg/h for CRRT and notes that a higher prescription may be needed to achieve it. Delivery, interruptions and the whole patient's needs require review.", secondary=("T23",))
q("T08", 1, 1, CKD, "Tables 1-3 and Figure 2: CGA classification",
  "Repeated eGFR is 24 mL/min/1.73 m2 for a year, with ACR 12 mg/g. Which interpretation is correct?",
  "CKD G4 A1 is present; little albuminuria does not negate low filtration.",
  [("ACR in A1 excludes CKD.", "Persistent GFR below 60 independently meets CKD criteria."),
   ("A1 makes the underlying cause diabetic nephropathy.", "The categories do not establish cause."),
   ("The GFR category is G3b because albuminuria is low.", "GFR and albuminuria categories are assigned separately.")],
  "CGA retains separate cause, GFR and albuminuria information. A1 describes albumin excretion, not an assurance of normal filtration or negligible risk.", secondary=("T02",))
q("T08", 2, 2, CKD, "Recommendation 2.2.1; Practice Points 2.2.4-2.2.5, printed S155: risk-equation population limits",
  "A kidney-failure risk equation validated in CKD G3-G5 is applied to a young adult with G1 and an inherited disorder. What is the main concern?",
  "The equation may be used outside its validated population.",
  [("Any kidney equation is calibrated identically at every GFR.", "Transportability must be evaluated."),
   ("A numerical output removes uncertainty about prognosis.", "A precise number can still be poorly calibrated."),
   ("The disorder can be excluded if the output is small.", "Prediction tools do not establish or exclude diagnosis.")],
  "Use a tool suited to the population, outcome and time horizon. G3-G5 models need not be valid in G1-G2 or every inherited condition; disease-specific prognostic assessment can be more appropriate.", secondary=("T12", "T26"), skill="common_reasoning")
q("T09", 1, 1, BP, "Recommendations 1.1 and 1.2: standardized and out-of-office BP",
  "Routine clinic BP is repeatedly high, but validated home readings are much lower. Which step best resolves the discrepancy before intensifying treatment?",
  "Check measurement technique and obtain standardized/out-of-office confirmation.",
  [("Treat the largest clinic value as interchangeable with a standardized target.", "Routine and standardized measurements are not interchangeable."),
   ("Discard all home readings solely because they differ.", "They may reveal a white-coat pattern if properly measured."),
   ("Diagnose resistant hypertension from one encounter.", "Measurement and adherence issues need assessment first.")],
  "Technique, setting and repeated readings influence interpretation. Validated home or ambulatory BP complements standardized office BP and can expose white-coat or masked patterns.", skill="common_reasoning")
q("T09", 2, 2, CKD, "Practice Point 3.6.4: creatinine response to RAS inhibition",
  "Two weeks after an ACE inhibitor is started, creatinine has increased by 15%, potassium is normal and BP is tolerated. Which interpretation is best?",
  "A modest hemodynamic change alone does not mandate stopping treatment.",
  [("Any creatinine rise proves irreversible toxic tubular injury.", "RAS inhibition alters glomerular hemodynamics."),
   ("The response eliminates the need for subsequent monitoring.", "Kidney function, potassium and tolerance still require review."),
   ("The dose must be escalated immediately to normalize creatinine.", "Creatinine normalization is not the titration goal.")],
  "The CKD practice point favors continuing ACEi/ARB unless creatinine rises by more than 30% within four weeks, while evaluating symptoms, volume, potassium and other causes. This threshold is a review aid, not permission to ignore a deteriorating patient.", secondary=("T19",), skill="mechanism")
q("T10", 1, 2, GD, "Practice Point 6.2.1.1: secondary FSGS",
  "Biopsy shows an FSGS lesion in an adult with a clear adaptive cause, without nephrotic syndrome. Which reasoning is most appropriate?",
  "Treat the cause and provide supportive care; the lesion alone does not justify primary-FSGS immunosuppression.",
  [("Every FSGS lesion represents the same immune disease.", "FSGS is a lesion with several mechanisms."),
   ("High-dose glucocorticoids are indicated solely by the word FSGS.", "Secondary FSGS is not treated as primary FSGS."),
   ("Proteinuria can be ignored once a cause is identified.", "Supportive risk reduction and monitoring remain important.")],
  "Clinical phenotype and mechanism distinguish primary FSGS from secondary/adaptive lesions. KDIGO advises against immunosuppression for secondary FSGS; diagnosis-specific supportive management is still active care.", skill="mechanism")
q("T10", 2, 1, GD, "Practice Point 3.1.1: nephrotic syndrome with positive anti-PLA2R",
  "An adult has nephrotic syndrome and strongly positive anti-PLA2R antibodies, with a compatible clinical picture. Which statement about diagnostic biopsy is correct?",
  "Membranous nephropathy may be diagnosed without biopsy in this defined setting.",
  [("Positive anti-PLA2R excludes every associated condition.", "Evaluation for associated conditions remains relevant."),
   ("No serologic result can ever alter the biopsy decision.", "This is a recognized disease-specific exception."),
   ("The antibody level alone fixes treatment regardless of risk.", "Treatment requires risk and clinical assessment.")],
  "The remaining membranous guideline permits a nonbiopsy diagnosis in nephrotic syndrome with positive anti-PLA2R. This does not remove assessment for associated conditions or every potential reason for tissue examination.", secondary=("T22",))
q("T11", 1, 1, MGRS, "Light-chain proximal tubulopathy; Fanconi syndrome",
  "A nondiabetic adult has glycosuria despite normal plasma glucose, hypophosphatemia and nonalbumin proteinuria. Which localization is most plausible?",
  "A proximal tubular reabsorptive defect.",
  [("Isolated failure of glomerular albumin selectivity.", "The combined glucose/phosphate losses indicate tubular handling."),
   ("An isolated distal hydrogen-ion secretion defect explains all findings.", "That does not explain the proximal solute losses."),
   ("A normal blood glucose excludes a kidney glucose-handling problem.", "Normoglycemic glycosuria is the clue to abnormal reabsorption.")],
  "Combined inappropriate proximal solute losses suggest a Fanconi-type pattern. Review medications and acquired/inherited causes; monoclonal light-chain proximal tubulopathy is one possible acquired cause, not a diagnosis from this pattern alone.", secondary=("T18",), skill="mechanism")
q("T11", 2, 2, EOS, "Results and discussion: biopsy-reference diagnostic accuracy",
  "AKI begins after a new medicine. Urine eosinophils are negative. What is the best interpretation regarding interstitial nephritis?",
  "The negative test does not reliably exclude AIN; continue contextual evaluation.",
  [("Negative urine eosinophils rule out drug-related AIN.", "Sensitivity was poor in the biopsy-linked study."),
   ("The test establishes acute tubular injury as the only alternative.", "It does not independently identify another lesion."),
   ("Negative urine eosinophils prove that the new medicine is safe to continue.", "Drug risk assessment cannot rest on this result alone.")],
  "Urine eosinophils are a weak discriminator in biopsy-referenced data. Review exposure timing, competing causes, urine findings and whether tissue would change management; neither a positive nor negative result settles AIN.", secondary=("T19", "T06"), skill="common_reasoning")
q("T12", 1, 1, PKD, "Chapter 1: diagnostic approach in adults without a known family history",
  "An adult has a convincing bilateral cystic phenotype but no known affected parent. What does the negative family history establish?",
  "It does not exclude ADPKD; phenotype and, when indicated, genetic evaluation remain relevant.",
  [("ADPKD is impossible unless both parents are affected.", "Autosomal dominant inheritance does not require two affected parents."),
   ("All bilateral cysts must therefore be simple age-related cysts.", "Distribution, age and extrarenal findings matter."),
   ("A family history is more definitive than all imaging information.", "Family recognition can be incomplete and variants may arise de novo.")],
  "Unrecognized familial disease and a de novo variant are possible. Use age, imaging phenotype, differential diagnosis and appropriate counseling rather than treating an absent history as exclusion.", skill="common_reasoning")
q("T12", 2, 2, PKD, "Chapter 4: progression assessment and Mayo imaging classification",
  "An adult with ADPKD has preserved eGFR but substantially enlarged kidneys for age. Why can imaging still inform disease-modifying treatment assessment?",
  "Structural progression risk can become apparent before a marked fall in filtration.",
  [("Preserved eGFR proves that rapid progression is impossible.", "Filtration may be preserved during structural progression."),
   ("Kidney size alone mandates tolvaptan without phenotype or risk review.", "Classification, atypical anatomy and other prognostic information must be considered."),
   ("Any cyst volume has the same meaning at every age.", "Age and size-normalized classification affect interpretation.")],
  "Age-adjusted structural assessment complements filtration trends when evaluating progression risk. It supports, rather than replaces, patient-specific eligibility, contraindication and monitoring discussions.", skill="mechanism")
q("T13", 1, 1, OBSTRUCT, "Conservative management: obstructive pyelonephritis and suspected septic stone",
  "An adult has fever, hypotension and an obstructing ureteral stone with hydronephrosis. Which principle is most appropriate?",
  "Urgent antibiotics, resuscitation and drainage/source-control assessment are required.",
  [("Observe until the stone passes because all small stones are benign.", "Infected obstruction is not routine expectant-management territory."),
   ("Antibiotics remove the obstruction, so drainage assessment is unnecessary.", "Antibiotics do not provide mechanical decompression."),
   ("Normal contralateral kidney function eliminates the sepsis risk.", "An infected obstructed unit can threaten the patient regardless of the other kidney.")],
  "Suspected infected obstruction requires urgent coordinated source control. Definitive stone treatment is planned around infection stabilization; the scenario is not an indication to wait for spontaneous passage.", secondary=("T17", "T07"))
q("T13", 2, 2, STONE, "Dietary calcium section: calcium oxalate stone prevention",
  "A recurrent calcium oxalate stone former proposes avoiding nearly all dietary calcium. What mechanism should inform counseling?",
  "Calcium with meals can bind intestinal oxalate; very low intake can increase oxalate absorption.",
  [("Every calcium-containing food necessarily raises stone risk.", "Dietary calcium and supplements/timing have different implications."),
   ("Oxalate absorption is independent of intestinal calcium.", "Luminal binding affects absorption."),
   ("Low calcium is required regardless of skeletal health or diet.", "Prevention balances recurrence risk and nutrition.")],
  "Maintain an appropriate normal dietary calcium intake rather than indiscriminate restriction. Meals provide an opportunity for oxalate binding; tailor supplements and other measures to the metabolic assessment.", secondary=("T25",), skill="mechanism")
q("T14", 1, 1, DM, "Practice Point 1.3.5 and rationale: reversible eGFR decrease with SGLT2 inhibitors",
  "A stable adult has a modest early eGFR dip after starting an SGLT2 inhibitor, without hypotension or illness. What mechanism is relevant?",
  "Altered tubuloglomerular feedback and intraglomerular hemodynamics.",
  [("The change necessarily means destructive tubular toxicity.", "A reversible hemodynamic effect is recognized."),
   ("The medicine must have increased glucose production in the kidney.", "That does not explain the characteristic filtration response."),
   ("The finding proves treatment failure without needing follow-up.", "Early hemodynamic change and long-term benefit are distinct.")],
  "Increased distal sodium delivery can restore feedback and reduce intraglomerular pressure. A modest reversible dip is generally not a reason to stop, but review volume, symptoms and an unexpectedly large decline.", secondary=("T01", "T19"), skill="mechanism")
q("T14", 2, 2, DM, "Practice Point 2.1.2: HbA1c accuracy in advanced CKD",
  "A dialysis patient receiving an ESA has frequent high glucose readings despite a low HbA1c. Which explanation should be considered?",
  "Altered erythrocyte survival/turnover can make HbA1c less reliable.",
  [("HbA1c is unaffected by anemia or ESA treatment.", "Red-cell dynamics can alter the glycation signal."),
   ("A low HbA1c proves the glucose meter is wrong.", "Discordance needs investigation rather than dismissal."),
   ("Glucose monitoring cannot add useful information in dialysis.", "Direct monitoring can help assess discordant glycemic markers.")],
  "Advanced CKD, anemia and treatments affecting red cells reduce HbA1c reliability. Use glucose monitoring or CGM when appropriate to assess the actual pattern and treatment risk.", secondary=("T20", "T08"), skill="mechanism")
q("T15", 1, 1, TTP, "Diagnostic context: thrombocytopenia, microangiopathic hemolysis and organ injury",
  "Thrombocytopenia, schistocytes, elevated LDH, low haptoglobin and AKI appear together. What process requires urgent assessment?",
  "Thrombotic microangiopathy, with rapid evaluation of its cause.",
  [("Isolated CKD erythropoietin deficiency explains the full pattern.", "It does not explain fragmentation hemolysis and thrombocytopenia."),
   ("Schistocytes alone establish complement-mediated disease.", "Several TMA mechanisms can share this finding."),
   ("The syndrome can be ignored until all kidney biopsy results return.", "Some causes are time-critical.")],
  "The combination suggests microangiopathic hemolysis and TMA rather than routine CKD anemia. Evaluate the phenotype, ADAMTS13 and competing secondary causes urgently; the syndrome is not its etiologic label.", secondary=("T06", "T16"))
q("T15", 2, 2, TTP, "Recommendation 1: high pretest probability and pretreatment ADAMTS13 sample",
  "TTP is strongly suspected. Why obtain an ADAMTS13 sample before plasma exchange or plasma administration if feasible without delaying care?",
  "Replacement plasma can change the diagnostic measurement.",
  [("Sampling must delay treatment until a result is available.", "Time-critical treatment should not await the result in a high-probability presentation."),
   ("ADAMTS13 has no role in distinguishing TMA mechanisms.", "Severe deficiency is central to TTP assessment."),
   ("Plasma exchange cannot affect measured enzyme activity.", "It replaces plasma constituents.")],
  "Collect pretreatment diagnostic blood promptly, then follow the urgent specialist pathway. Sampling before replacement improves interpretability; it is not a reason to delay indicated treatment.", secondary=("T23",), skill="mechanism")
q("T16", 1, 1, AAV, "Practice Point 9.1.1: compatible phenotype and positive MPO/PR3 antibodies",
  "A low-positive ANCA is found incidentally without compatible kidney, lung or systemic findings. Which interpretation is best?",
  "Serology alone does not establish organ-threatening ANCA-associated vasculitis.",
  [("Any positive assay mandates induction immunosuppression.", "Clinical phenotype and differential diagnosis matter."),
   ("The result excludes all nonvasculitic causes of later AKI.", "Serology does not eliminate alternative causes."),
   ("A kidney biopsy is mandatory solely because the assay is positive.", "The indication depends on the clinical presentation.")],
  "Interpret antibody specificity, magnitude and pretest probability together. The urgency recommendation concerns a compatible rapidly deteriorating presentation; an isolated result is not that phenotype.", secondary=("T02",), skill="common_reasoning")
q("T16", 2, 2, LN, "Diagnosis and kidney biopsy assessment: activity and chronicity",
  "A lupus kidney biopsy reports both active inflammation and chronic scarring. Why does the distinction matter?",
  "Potentially reversible inflammatory injury and established damage affect expected treatment benefit differently.",
  [("Scarring predicts full reversibility with more immunosuppression.", "Established damage is not equivalent to active inflammation."),
   ("The class name makes activity/chronicity information unnecessary.", "These features add clinically relevant information."),
   ("An antibody titer provides the same tissue information.", "Serology does not substitute for histologic damage assessment.")],
  "Tissue assessment informs what can plausibly respond and what may represent irreversible injury. Interpret class, activity, chronicity, clinical severity and treatment risks together rather than equating all impaired function with active immune disease.", secondary=("T10", "T22"))
q("T17", 1, 1, TX, "Section 10: active infections and transplant timing",
  "A listed transplant candidate develops an active serious infection. What is the key implication for proceeding with transplantation?",
  "Treat/control the active infection and reassess timing with the transplant team.",
  [("Immunosuppression will reliably eradicate the infection.", "It can worsen infection."),
   ("The listing decision makes new infection information irrelevant.", "Candidate suitability is reassessed as circumstances change."),
   ("Any remote treated infection creates an automatic permanent exclusion.", "Active and successfully treated historical disease are different.")],
  "Active infection generally warrants delaying transplantation until treated, with condition-specific specialist judgment. Distinguish infection control from permanent exclusion based on a past diagnosis.", secondary=("T21",))
q("T17", 2, 2, GD, "Practice Points 1.8.1-1.8.2: infection screening around immunosuppression",
  "Before substantial immunosuppression for glomerular disease, what is the main reason to review hepatitis B infection markers as well as vaccination history?",
  "Prior or current infection can create reactivation risk that vaccine history alone does not resolve.",
  [("Vaccination history proves that infection markers can be ignored.", "It does not replace infection-status assessment."),
   ("Hepatitis B testing identifies the histologic glomerular class by itself.", "Screening informs infection risk and possible associated disease."),
   ("Reactivation is possible only in dialysis patients.", "Immunosuppression can create risk outside dialysis.")],
  "Infection screening is part of treatment-harm prevention. Assess appropriate HBV serology and other indicated infections; prevention or specialist monitoring depends on the actual infection status and planned treatment.", secondary=("T10",), skill="mechanism")
q("T18", 1, 1, MGRS, "Definition and evaluation of MGRS",
  "A small monoclonal clone does not meet myeloma criteria, but kidney injury may be caused by its immunoglobulin. Which principle is correct?",
  "A small clone can still produce clinically important nephrotoxic protein.",
  [("Only a clone meeting myeloma criteria can harm the kidney.", "MGRS was defined to address organ injury from smaller clones."),
   ("Every monoclonal protein found in CKD proves MGRS.", "Coincidental monoclonal gammopathy is possible."),
   ("Clone size alone identifies the kidney lesion.", "Renal characterization is still required.")],
  "The pathogenic properties of the protein and its kidney effect matter, not clone burden alone. Establish whether the clone and renal lesion are linked; do not treat incidental gammopathy as proof.", skill="mechanism")
q("T18", 2, 2, MGRS, "Renal biopsy evaluation: light microscopy, immunofluorescence and electron microscopy",
  "Suspected MGRS is being evaluated. Why is light microscopy alone often insufficient for the kidney biopsy?",
  "Immunoglobulin identity and ultrastructural deposit patterns can be essential to lesion classification.",
  [("All monoclonal lesions have the same light-microscopic appearance.", "The renal spectrum is heterogeneous."),
   ("A serum monoclonal spike specifies the tissue deposit pattern.", "Blood findings do not establish renal localization or structure."),
   ("Electron microscopy replaces all clinical and hematologic information.", "Tissue and clonal evaluation must be integrated.")],
  "Appropriate light microscopy, immunofluorescence and electron microscopy can distinguish deposition and other monoclonal-associated patterns. Correlate tissue findings with the circulating clone and alternative kidney causes.", secondary=("T22", "T02"))
q("T19", 1, 1, AKI, "Sections 2.3 and 3.1: medication-related hemodynamic AKI",
  "During vomiting, a patient takes a diuretic, ACE inhibitor and NSAID. Which combined mechanism can impair filtration?",
  "Volume depletion plus altered afferent/efferent vascular support of glomerular pressure.",
  [("All three medicines necessarily cause the same direct tubular crystal injury.", "Their hemodynamic effects differ."),
   ("An ACE inhibitor guarantees preserved filtration despite dehydration.", "Efferent effects can matter during reduced perfusion."),
   ("A normal prior creatinine prevents hemodynamic AKI.", "Acute perfusion changes can affect a previously normal kidney.")],
  "Reduced perfusion, NSAID-related loss of prostaglandin-mediated afferent support and RAS-blockade effects on efferent tone can combine. Evaluate volume and the medication history without assuming every creatinine rise is intrinsic tubular injury.", secondary=("T06", "T03"), skill="mechanism", extra_sources=((CKD, "Table 31, printed S247; Practice Point 3.6.4: NSAIDs and RAS-inhibition kidney-function assessment"),))
q("T19", 2, 2, CKD, "Practice Point 4.3.2: temporary discontinuation and restart communication",
  "Kidney-protective medication is temporarily interrupted during acute illness. What should the handoff include?",
  "The reason, monitoring and explicit conditions/responsibility for restarting.",
  [("A temporary hold is automatically a permanent stop.", "Unintended long-term discontinuation can lose benefit."),
   ("Restart should occur on a fixed date regardless of recovery.", "Recovery, kidney function and treatment-specific risks matter."),
   ("Only the drug name is needed in the discharge summary.", "The action plan and responsible clinician must be clear.")],
  "An interruption is a monitored plan, not a silent deletion from therapy. Document why it occurred, what needs reassessment and who will ensure appropriate resumption.", secondary=("T27",), skill="common_reasoning")
q("T20", 1, 1, HD, "Guideline 1: dialysis dose and clinical assessment",
  "A hemodialysis patient reaches the unit's urea-dose target but remains overloaded and poorly nourished. Which conclusion is correct?",
  "Meeting a small-solute metric does not establish adequate overall dialysis care.",
  [("The urea metric guarantees acceptable volume and nutrition.", "These are separate dimensions."),
   ("Volume symptoms cannot be kidney related if urea clearance is sufficient.", "Solute clearance and fluid management are different."),
   ("No prescription review is needed after a target is reached.", "Clinical response and other needs remain relevant.")],
  "Urea-dose metrics describe part of treatment. Assess symptoms, volume, nutrition, residual function, treatment tolerance and patient goals rather than declaring adequacy from one number.", secondary=("T25", "T23"), skill="common_reasoning")
q("T20", 2, 2, PD, "Section 4: membrane function and ultrafiltration; fast transport",
  "A fast peritoneal solute transporter has poor ultrafiltration during long glucose dwells. What mechanism can explain this?",
  "Rapid glucose absorption dissipates the osmotic gradient earlier.",
  [("Fast solute transport guarantees sustained fluid removal at every dwell length.", "Solute transport and sustained osmotic driving force differ."),
   ("Glucose cannot cross the peritoneal membrane.", "Its absorption changes the gradient."),
   ("Residual urine output is the only determinant of peritoneal ultrafiltration.", "Membrane characteristics and prescription also matter.")],
  "Faster small-solute/glucose transport can shorten effective osmotic fluid removal during a prolonged glucose dwell. Use membrane testing and clinical assessment to tailor the prescription; the mechanism does not dictate one universal regimen.", secondary=("T23",), skill="mechanism")
q("T21", 1, 1, DONOR, "Recommendations 5.6-5.8: donor GFR selection",
  "A prospective living donor has confirmed GFR 52 mL/min/1.73 m2. Which donor-specific principle applies in the dated KDIGO guideline?",
  "GFR below 60 is not an acceptable donation level in that guideline.",
  [("Any GFR sufficient to avoid dialysis is sufficient for donation.", "Donor protection uses a different decision threshold."),
   ("Recipient need automatically overrides donor kidney risk.", "Donor safety and autonomy are independent requirements."),
   ("An incidental normal ACR negates the low GFR.", "Albuminuria and filtration are assessed separately.")],
  "Living-donor assessment is not the same as CKD dialysis timing. The 2017 final excludes GFR below 60; values 60-89 require individualized risk assessment, and at least 90 is generally acceptable within the overall evaluation.", secondary=("T08",))
q("T21", 2, 2, TX, "Section 19: HLA-antibody assessment and sensitizing events",
  "A transplant candidate receives a blood transfusion after the last HLA-antibody assessment. What information should reach the transplant team?",
  "The new sensitizing event, so immunologic assessment can be updated.",
  [("A previous negative antibody test remains definitive forever.", "Sensitization can change over time."),
   ("Transfusion immediately proves that transplantation is impossible.", "It informs risk and testing, not automatic permanent exclusion."),
   ("Only the hemoglobin response matters to transplant planning.", "The exposure also has immunologic implications.")],
  "Pregnancy, transfusion and prior transplantation can alter HLA sensitization. Communicate intervening events so current antibody/crossmatch information can support candidate planning.", secondary=("T27",), skill="mechanism")
q("T22", 1, 1, GD, "Chapter 5: adult minimal change disease diagnosis",
  "An adult has nephrotic syndrome and little abnormality on light microscopy. Why does this not alone establish minimal change disease?",
  "Immunofluorescence and electron microscopy are needed to characterize the lesion and exclude alternatives.",
  [("Near-normal light microscopy excludes a glomerular cause.", "Some important lesions have limited light-microscopic change."),
   ("Proteinuria magnitude specifies the histology without tissue studies.", "Different lesions can cause nephrotic syndrome."),
   ("A normal ultrasound substitutes for ultrastructural evaluation.", "Anatomic imaging does not show podocyte ultrastructure.")],
  "Adult MCD is a biopsy diagnosis requiring the whole pathology assessment. A limited light-microscopic description cannot exclude an immune deposit process or characterize foot-process changes.", secondary=("T10",))
q("T22", 2, 2, PREG, "Recommendation 4.8.1: kidney biopsy during pregnancy",
  "During early pregnancy, new kidney findings may require a treatment that depends on histology. Which biopsy principle is best supported?",
  "Consider biopsy in the first or early second trimester if histology will change management.",
  [("Pregnancy makes biopsy appropriate at any gestation without risk review.", "Timing and procedural risks matter."),
   ("Biopsy is prohibited in every pregnancy regardless of likely benefit.", "The guideline allows a carefully selected indication."),
   ("A biopsy is needed merely to confirm that creatinine is elevated.", "The information must have management value.")],
  "Balance the expected management benefit with maternal/fetal context, timing and procedural risk in a specialist plan. The recommendation is conditional on histology changing care, not an automatic response to an abnormal test.", secondary=("T24", "T10"))
q("T23", 1, 1, HD, "Appendices: diffusion, convection and dialysis clearance",
  "Which description best distinguishes convection from diffusion in extracorporeal solute removal?",
  "Convection transports solute with filtered water; diffusion follows a concentration gradient.",
  [("Convection occurs without any water movement.", "Solvent movement is central to convection."),
   ("Diffusion is defined by a pressure-driven fluid flux alone.", "Diffusive transfer is driven by concentration differences."),
   ("Both mechanisms guarantee identical clearance for every molecular size.", "Membrane and molecule properties affect their clearances.")],
  "Solvent drag and concentration-driven transfer are distinct mechanisms that can coexist. Membrane permeability, flows, molecular size and delivered treatment time determine practical clearance.", secondary=("T20",), skill="mechanism")
q("T23", 2, 2, TTP, "Recommendation 1 and rationale: plasma exchange in suspected TTP",
  "Why is ordinary hemodialysis not an equivalent substitute for plasma exchange in a high-probability TTP pathway?",
  "Plasma exchange removes/replaces plasma constituents; dialysis primarily targets dialyzable solutes and fluid.",
  [("Both procedures remove every plasma antibody to the same extent.", "Their targets and replacement effects differ."),
   ("Hemodialysis supplies ADAMTS13 by definition.", "Standard dialysis does not replace plasma enzyme."),
   ("Any treatment that lowers urea necessarily treats the TTP mechanism.", "A urea change does not address the plasma-mediated process.")],
  "The urgent TTP pathway is directed at the disease mechanism, including deficient ADAMTS13 and inhibitory antibodies in immune disease. Kidney support may also be required, but it does not replace disease-specific specialist treatment.", secondary=("T15", "T20"), skill="mechanism")
q("T24", 1, 1, PREG, "Recommendation 4.1.1: renal function assessment in pregnancy",
  "A pregnant patient has a creatinine-based laboratory eGFR. Which principle should guide kidney-function assessment?",
  "Use serum creatinine and clinical trends; standard eGFR equations are not validated for pregnancy.",
  [("The automated eGFR is calibrated identically in pregnancy and nonpregnancy.", "Pregnancy changes physiology and equation validity."),
   ("Normal nonpregnant creatinine ranges settle all pregnancy assessments.", "Pregnancy-associated filtration affects interpretation."),
   ("Urine protein is a direct replacement for filtration assessment.", "It measures a different kidney feature.")],
  "The guideline recommends serum creatinine because routine eGFR estimates are invalid in pregnancy. Interpret serial values with gestation, prior function, proteinuria and clinical context.", secondary=("T01",))
q("T24", 2, 2, PREG, "Recommendations 4.4.5-4.4.6: superimposed preeclampsia",
  "A patient with proteinuric CKD develops new hypertension and organ dysfunction after 20 weeks of pregnancy. What should be considered?",
  "Superimposed preeclampsia, rather than attributing every change to baseline CKD.",
  [("Existing proteinuria excludes preeclampsia.", "Baseline CKD complicates but does not exclude the diagnosis."),
   ("Any proteinuria change alone proves a histologic lupus flare.", "Obstetric and other kidney causes need assessment."),
   ("The automated eGFR can independently distinguish the two diagnoses.", "It is not validated in pregnancy and cannot determine cause.")],
  "New maternal findings after 20 weeks can indicate superimposed preeclampsia. Use the whole maternal/fetal assessment and the prior CKD phenotype; no single protein measurement resolves the differential.", secondary=("T09", "T27"))
q("T25", 1, 1, CKD, "Recommendation 3.3.1.1: protein intake in adults with nondialysis CKD G3-G5",
  "A clinic copies a nondialysis CKD protein target into every hemodialysis diet plan. What is the central reasoning error?",
  "The recommendation is being transferred to a different treatment/nutritional population.",
  [("Protein needs are identical across dialysis and nondialysis states.", "Treatment, catabolism and nutritional stability change the context."),
   ("A lower intake must always produce a better outcome.", "Restriction can have nutritional harms."),
   ("Nutritional assessment is unnecessary once a numerical target exists.", "Targets require individualized assessment.")],
  "The 0.8 g/kg/day CKD recommendation concerns nondialysis adults with G3-G5. Do not use it as a universal dialysis prescription; assess nutritional state, treatment and dietetic needs.", secondary=("T20",), skill="common_reasoning")
q("T25", 2, 2, CKD, "Practice Points 3.3.1.3 and 3.3.1.5: nutritional instability and frailty",
  "A frail adult with CKD has unintentional weight loss and poor intake. Which issue takes priority before intensifying dietary restriction?",
  "Assess malnutrition, function and whether restriction would add harm.",
  [("The lowest possible protein intake is always safest.", "Nutritional instability changes the balance."),
   ("Body mass alone excludes loss of muscle or malnutrition.", "Weight and composition/function are different."),
   ("A diet target can be chosen without the patient's circumstances.", "Symptoms, intake and goals affect a useful plan.")],
  "Nutritionally unstable or frail patients need individualized support. A restriction aimed at kidney risk can undermine muscle, function or intake when applied without assessment.", secondary=("T24", "T26"), skill="common_reasoning")
q("T26", 1, 2, CKD, "Guideline grading key: recommendation strength and certainty; evidence interpretation",
  "In a synthetic two-year trial, events occur in 4% of controls and 3% of treated participants. What absolute reduction and approximate NNT follow?",
  "1 percentage point; NNT 100 over two years.",
  [("25 percentage points; NNT 4.", "This confuses relative reduction with absolute risk difference."),
   ("1 percentage point; NNT 1.", "A proportion of 0.01 has a reciprocal of 100."),
   ("The NNT is 100 regardless of follow-up or baseline risk.", "NNT is specific to the outcome, population and time horizon.")],
  "For the explicitly synthetic data, ARR = 0.04 - 0.03 = 0.01, and NNT = 1 / 0.01 = 100 over two years. A 25% relative reduction is a different quantity and does not convey the absolute benefit alone.", skill="interpretation", calculation={"expression": "1 / (0.04 - 0.03)", "result": 99.99999999999999, "unit": "people over two years"})
q("T26", 2, 1, CKD, "Practice Points 5.5.1-5.5.2; Table 43: comprehensive conservative care",
  "A well-informed patient chooses conservative kidney care and later asks to revisit dialysis. Which approach best respects the care plan?",
  "Continue active supportive care and review the person's evolving goals and options.",
  [("The earlier decision permanently removes the right to discuss options.", "Preferences and circumstances can change."),
   ("Conservative care means no symptom treatment or follow-up.", "It is an active care pathway."),
   ("The team must start dialysis solely because preferences changed.", "Review informed goals, indications and burdens rather than bypassing assessment.")],
  "Supportive care and advance planning remain active and revisable. Reassess goals, expected benefits, burdens and clinical circumstances through shared decision-making.", secondary=("T20",), skill="common_reasoning")
q("T27", 1, 2, CKD, "Practice Point 3.6.3: hyperkalemia management during RAS inhibition",
  "A stable CKD patient benefits from RAS inhibition but develops manageable hyperkalemia. What should the shared kidney/cardiac medication review consider?",
  "Address potassium contributors and feasible control measures before automatically withdrawing beneficial therapy.",
  [("Any potassium increase demands a permanent stop without review.", "The guideline favors treating hyperkalemia where possible."),
   ("Kidney and cardiovascular effects never need to be weighed together.", "The same therapy can affect both organ risks."),
   ("Treatment benefit makes severe uncontrolled hyperkalemia safe.", "Uncontrolled or dangerous hyperkalemia requires urgent reassessment.")],
  "Review diet, supplements, interacting medicines, volume and potassium-control options with the relevant clinicians. Preserve benefit when safely feasible; uncontrolled hyperkalemia or symptomatic hypotension can change that decision.", secondary=("T04", "T19"), skill="common_reasoning")
q("T27", 2, 1, CKD, "Section 1.2.2, sources of error in eGFRcr-cys, printed S151: inflammation and exogenous steroid use",
  "A patient receiving glucocorticoids during a highly inflammatory illness has discordant creatinine/cystatin-C estimates. What should guide a high-stakes dosing decision?",
  "Review non-GFR influences and obtain a more appropriate estimate or measured GFR when needed.",
  [("Cystatin C is immune to all non-GFR influences.", "Inflammation and exogenous steroid exposure can affect its interpretation."),
   ("The lower estimate automatically reveals the cause of kidney disease.", "Discordance does not establish etiology."),
   ("Averaging unrelated results removes every source of bias.", "The individual marker limitations and required precision matter.")],
  "Both markers have non-GFR determinants. Integrate muscle mass, inflammation and medications; use combined or measured approaches as appropriate to the decision rather than treating either marker as universally definitive.", secondary=("T01", "T19"), skill="mechanism")


# Final additive breadth: two further distinct questions for every topic.
q("T01", 3, 1, CKD, "Practice Point 4.2.5: filtration estimates outside steady state",
  "During evolving AKI, creatinine rises from 80 to 180 micromol/L in 36 hours. The laboratory reports eGFR 35. What limits using that number as today's drug-clearance measurement?",
  "The creatinine concentration is not at steady state, so the estimate can lag changing filtration.",
  [("Indexing to 1.73 m2 converts the result into measured clearance.", "Body-size indexing does not correct the changing marker concentration."),
   ("A single cystatin-C result would remove all uncertainty during critical illness.", "Alternative markers also have kinetics and non-GFR determinants."),
   ("The laboratory number establishes the same GFR for the preceding 36 hours.", "A changing concentration does not describe a constant clearance.")],
  "An equation fitted to stable marker concentrations does not instantaneously track a rapid filtration change. Review trajectory, urine output, the medicine and required precision; use an appropriate monitoring/dosing plan.", secondary=("T06", "T19"), skill="mechanism")
q("T01", 4, 2, CKD, "Section 1.2.2; printed S151: reduced muscle mass as a non-GFR determinant",
  "After a prolonged catabolic illness, an adult's creatinine-based eGFR rises as muscle mass falls. Which interpretation best fits these data?",
  "Reduced creatinine generation can mimic improved filtration.",
  [("The change quantifies structural recovery of the kidney.", "Creatinine production has changed, so that conclusion is unsupported."),
   ("Muscle loss should increase creatinine generation and lower eGFR.", "Loss of muscle generally reduces creatinine generation."),
   ("The eGFR trend can replace assessment of functional and nutritional recovery.", "Filtration estimates and physical recovery measure different things.")],
  "A lower creatinine can reflect less production rather than better clearance. Compare the clinical course and other appropriate filtration information, especially before interpreting the change as recovery or increasing a narrow-range drug dose.", secondary=("T25", "T19"), skill="mechanism")
q("T02", 3, 1, CKD, "Practice Points 1.3.1.2-1.3.1.3; Table 16, printed S154: urine measurement variability",
  "An adult's first elevated ACR was sampled just after strenuous exercise during a urinary infection. What is the best next interpretation step?",
  "Confirm quantitative albuminuria under suitable conditions, preferably with a first-morning sample.",
  [("Assign a chronic albuminuria category from this result alone.", "Temporary influences and chronicity require assessment."),
   ("Replace the quantitative ACR with a visual dipstick estimate.", "That loses measurement precision rather than confirming the result."),
   ("Ignore all future urine testing because both confounders are present.", "Confounding prompts confirmation, not abandonment of evaluation.")],
  "Exercise and symptomatic urinary infection can raise urinary protein/albumin. Repeat appropriate measurement after evaluating transient factors, and interpret persistence with the clinical phenotype.", secondary=("T08", "T17"), skill="common_reasoning")
q("T02", 4, 1, CKD, "Table 16, printed S154: low urinary creatinine excretion and ACR/PCR",
  "Two adults excrete the same daily urine albumin, but one has much lower creatinine excretion from low muscle mass. How can their spot ACRs differ?",
  "The adult with lower creatinine excretion can have a higher ACR for the same albumin loss.",
  [("The creatinine denominator cannot affect a ratio.", "The ratio changes when its denominator changes."),
   ("The higher ACR must establish a different glomerular lesion.", "A denominator effect does not identify histology."),
   ("A lower creatinine denominator necessarily lowers ACR.", "It raises the ratio for a given albumin amount.")],
  "ACR helps account for urine concentration, but creatinine excretion varies with body composition and other factors. If the discrepancy matters, assess sample/collection quality and the need for timed excretion rather than equating the ratio with a histologic diagnosis.", secondary=("T01", "T25"), skill="mechanism")
q("T03", 3, 1, NA, "Section 6.3: urine sodium and effective arterial volume in hypotonic hyponatremia",
  "A patient with edema has hypotonic hyponatremia, urine osmolality 520 mOsm/kg and urine sodium 12 mmol/L without recent diuretics. Which explanation is compatible with the pattern?",
  "Low effective arterial volume can sustain antidiuresis despite expanded total extracellular fluid.",
  [("Edema establishes maximally dilute urine.", "The measured urine is concentrated."),
   ("A low urine sodium proves that the patient has no excess extracellular fluid.", "Effective arterial volume and total extracellular volume are different."),
   ("The results alone distinguish heart failure from cirrhosis.", "Both can produce this physiologic pattern.")],
  "A low urine sodium can reflect sodium retention in low effective arterial volume. Edematous states can therefore coexist with antidiuresis and hypotonic hyponatremia; establish the cause from the whole assessment.", secondary=("T27",), skill="mechanism")
q("T03", 4, 1, NA, "Section 6.2: exclude nonhypotonic hyponatremia; glucose as an effective osmole",
  "Sodium is 128 mmol/L during marked hyperglycemia, and measured serum osmolality is elevated. Which reasoning should precede a hypotonic-hyponatremia algorithm?",
  "Assess effective osmolality and glucose-related water shifts; low sodium does not by itself establish hypotonicity.",
  [("A low sodium concentration establishes low serum osmolality.", "The measured osmolality contradicts that assumption."),
   ("Hyperglycemia can lower sodium only through laboratory assay interference.", "It can also shift water between compartments."),
   ("Urine sodium alone determines the serum tonicity.", "Serum effective osmoles must be assessed first.")],
  "Extracellular glucose can draw water out of cells and lower the measured sodium concentration while increasing tonicity. Distinguish this from true hypotonic and analytical pseudohyponatremia before applying a diagnostic pathway.", secondary=("T14",), skill="common_reasoning")
q("T04", 3, 1, K, "Section II: insulin-glucose redistribution and serial potassium/glucose monitoring",
  "Potassium falls after insulin-glucose treatment, but little potassium has yet left the body. What explains the need for continued monitoring and an elimination plan?",
  "Redistribution can wear off, while insulin can also cause delayed hypoglycemia.",
  [("The measured fall quantifies potassium removed in the urine.", "Insulin primarily shifts potassium into cells."),
   ("Normal potassium immediately after treatment excludes later recurrence.", "Rebound can follow redistribution without adequate removal."),
   ("Glucose monitoring ends as soon as potassium first improves.", "Glycemic risk can persist beyond the initial response.")],
  "Shifting and removal are different treatment mechanisms. Reassess potassium and glucose over the treatment window, address contributors and select appropriate potassium removal according to the clinical situation.", secondary=("T07", "T14"), skill="mechanism")
q("T04", 4, 2, RTA, "Diagnostic/pathophysiology sections: normal-anion-gap acidosis versus additional unmeasured anions",
  "An adult has sodium 140, chloride 104 and bicarbonate 12 mmol/L, with albumin 4.0 g/dL. Using an anion gap that excludes potassium, which finding argues against isolated normal-gap RTA?",
  "The calculated anion gap is 24 mmol/L, suggesting additional unmeasured anions.",
  [("The calculated gap is 12 mmol/L because it equals bicarbonate.", "The gap is sodium minus chloride and bicarbonate."),
   ("The calculated gap is 8 mmol/L, proving isolated chloride accumulation.", "Those numbers do not produce a gap of 8."),
   ("The gap is 128 mmol/L, obtained by subtracting bicarbonate alone.", "Chloride must also be subtracted.")],
  "For these synthetic results, 140 - 104 - 12 = 24 mmol/L. A raised gap prompts assessment for an additional process rather than attributing all acidosis to a normal-gap tubular disorder; local reference intervals and albumin matter.", secondary=("T11", "T06"), calculation={"expression": "140 - 104 - 12", "result": 24, "unit": "mmol/L"})
q("T05", 3, 1, MBD, "Recommendation 3.2.3, printed p15: extremes of PTH and bone-specific alkaline phosphatase",
  "A dialysis patient's PTH and bone-specific alkaline phosphatase are both markedly low. Which interpretation is best supported?",
  "Low bone turnover is a concern, but these markers do not provide a complete histologic diagnosis.",
  [("The results establish high-turnover bone disease.", "The direction of both markers argues against that interpretation."),
   ("Normal phosphate would exclude every bone disorder.", "Phosphate is not a complete measure of turnover."),
   ("A low PTH proves osteoporosis is absent.", "Turnover and fracture/osteoporosis assessment are different questions.")],
  "Markedly high or low PTH or bone-specific alkaline phosphatase can help predict turnover. Interpret the pattern with trends, treatment and fracture concerns; tissue can be considered when its result would change management.", secondary=("T20", "T22"))
q("T05", 4, 2, MBD, "Recommendations 3.1.4 and 4.1.5, printed p16: serial assessment and phosphate-lowering decisions",
  "An adult with CKD G3b has repeatedly normal phosphate. A binder is proposed solely to prevent a future rise. What does the dated 2017 guideline emphasize?",
  "Phosphate-lowering decisions should follow progressively or persistently elevated phosphate and the overall biochemical picture.",
  [("Every reduction of normal phosphate has demonstrated outcome benefit.", "Preventive lowering in this setting is not established."),
   ("A single PTH result makes phosphate trends irrelevant.", "CKD-MBD parameters should be interpreted together over time."),
   ("A calcium-based binder cannot contribute to calcium loading.", "Calcium exposure is part of the treatment balance.")],
  "Avoid transferring the management of overt hyperphosphatemia to a normal value without evidence of benefit. Review serial phosphate, calcium, PTH, diet and potential treatment harms together.", secondary=("T08", "T19"), skill="common_reasoning")
q("T06", 3, 1, AKI, "Sections 2.1-2.3: baseline, chronology and evaluation of AKI",
  "Creatinine is 240 micromol/L on admission, with no prior result available. Which conclusion is justified by this value alone?",
  "Kidney dysfunction is present, but the value alone cannot distinguish acute from chronic dysfunction or assign a creatinine-ratio AKI stage.",
  [("The value establishes CKD G4 lasting at least three months.", "Duration is unknown and the concentration does not establish chronicity."),
   ("Stage 3 AKI is established by comparison with an assumed normal baseline.", "An unsupported baseline can misclassify the episode."),
   ("A lack of previous tests rules out AKI.", "It creates uncertainty rather than excluding acute dysfunction.")],
  "Seek prior information, chronology, urine output, urine findings and reversible causes. A single abnormal concentration can be clinically urgent without establishing its duration or a baseline-relative stage.", secondary=("T08", "T01"), skill="common_reasoning")
q("T06", 4, 2, AKI, "Recommendation 3.4.2 and Section 3.4 rationale: diuretics and AKI outcomes",
  "A loop diuretic increases urine output in volume-overloaded AKI, while creatinine and metabolic abnormalities continue to worsen. What does the urine response establish?",
  "Fluid removal may improve, but the response does not prove recovery of filtration or elimination of a KRT indication.",
  [("More urine necessarily means that GFR has normalized.", "Diuresis and solute clearance are different outcomes."),
   ("The response demonstrates that diuretics reverse the underlying kidney injury.", "A urine-volume response does not establish injury reversal."),
   ("All further biochemical monitoring can be replaced by urine volume.", "Electrolyte, acid-base and clearance needs still matter.")],
  "Diuretics can be useful for overload, but urine output after a drug challenge is not synonymous with recovered kidney function. Reassess the whole physiologic need for support and the cause of AKI.", secondary=("T07", "T19"), skill="mechanism")
q("T07", 3, 1, AKI, "Recommendation 5.8.4: delivered effluent rate in CRRT",
  "For an explicitly selected dosing weight of 80 kg, what delivered effluent rate corresponds to 25 mL/kg/h before accounting for interruptions?",
  "2,000 mL/h.",
  [("320 mL/h.", "Weight is multiplied by the dose per kilogram, not divided into it."),
   ("25 mL/h.", "The per-kilogram rate has not been scaled to weight."),
   ("48,000 mL/h.", "That is the 24-hour volume at 2,000 mL/h, not the hourly rate.")],
  "The dimensional calculation is 80 kg x 25 mL/kg/h = 2,000 mL/h. Dosing-weight choice, circuit delivery and interruptions still need assessment; an arithmetic prescription is not proof of adequate delivered treatment.", secondary=("T23",), calculation={"expression": "80 * 25", "result": 2000, "unit": "mL/h"})
q("T07", 4, 2, AKI, "Recommendation 5.2.1: stopping kidney replacement therapy",
  "After improving AKI, a team considers stopping KRT. Which assessment most directly answers whether support is still needed?",
  "Whether intrinsic kidney function can meet current solute, electrolyte and fluid needs, consistent with the goals of care.",
  [("Whether creatinine has reached the laboratory reference interval.", "Support can become unnecessary before complete normalization."),
   ("Whether the patient has received a fixed number of treatments.", "Recovery and physiologic needs vary."),
   ("Whether one urine collection exceeds a numerical volume without other data.", "Urine volume alone does not establish adequate clearance and balance.")],
  "A monitored trial off support is based on recovered capacity and present needs, not a universal creatinine or treatment-count rule. Plan reassessment for recurrent fluid or metabolic problems.", secondary=("T26",), skill="common_reasoning")
q("T08", 3, 2, CKD, "Practice Point 2.1.3, printed S155: change in eGFR beyond expected variability",
  "A stable CKD patient's eGFR falls from 60 to 44 mL/min/1.73 m2 on follow-up. Which interpretation best follows the 2024 monitoring practice point?",
  "The fall exceeds 20% and warrants evaluation rather than being dismissed as ordinary variability.",
  [("The decline proves irreversible progression without checking context.", "The cause of a meaningful change still needs evaluation."),
   ("Only a fall of more than 50% merits investigation.", "The practice point uses a lower monitoring threshold."),
   ("The change is 16%, obtained by treating the absolute difference as a percentage.", "The baseline-relative fall is 16/60, about 27%.")],
  "The synthetic decrease is about 26.7%. Evaluate timing, illness, medicines, measurement and progression; a monitoring trigger identifies a need to investigate, not an automatic cause.", secondary=("T19", "T06"), calculation={"expression": "(60 - 44) / 60 * 100", "result": 26.666666666666668, "unit": "percent"})
q("T08", 4, 1, CKD, "Practice Point 2.1.5, printed S155: doubling of ACR",
  "ACR increases from 100 to 220 mg/g during CKD monitoring. Which response best fits the guideline's variability principle?",
  "Evaluate the more-than-doubling and its clinical/sample context, even though both results remain in A2.",
  [("Remaining in the same category makes the change uninformative.", "A meaningful within-category change can still warrant evaluation."),
   ("The result alone establishes a new biopsy diagnosis.", "Albuminuria change does not specify histology."),
   ("The ACR is now a filtration measurement.", "Albumin excretion and filtration remain distinct features.")],
  "Category boundaries do not capture every meaningful trend. A doubling exceeds expected laboratory variability according to the practice point; assess persistence, confounders and the underlying process.", secondary=("T02",), skill="common_reasoning")
q("T09", 3, 2, BP, "Practice Point 3.1.2: less intensive treatment with symptomatic postural hypotension",
  "An adult with CKD has standardized seated systolic BP 128 mmHg but recurrent symptomatic standing hypotension and falls. What should guide further treatment intensity?",
  "Individualize the target and review tolerability, medicines and the postural pattern.",
  [("The seated value alone requires intensification until it is below 120.", "The recommended target is conditional on tolerability."),
   ("The standing symptoms are irrelevant if seated technique is standardized.", "Standardization does not remove a tolerability problem."),
   ("All kidney-protective treatment should be permanently abandoned without review.", "The problem requires a specific assessment and balanced plan.")],
  "A population BP target is not an instruction to ignore symptomatic hypotension. Review reversible contributors, treatment burden and the patient's priorities when deciding a tolerable intensity.", secondary=("T19", "T24"), skill="common_reasoning")
q("T09", 4, 1, BP, "Recommendation 1.2 and rationale: out-of-office BP and masked hypertension",
  "Standardized clinic BP is acceptable, but repeated validated home readings are high. What does this discrepancy warrant?",
  "Confirmation of technique and the out-of-office pattern, including possible masked hypertension.",
  [("The clinic result automatically invalidates every home result.", "Out-of-office measurements provide complementary information."),
   ("White-coat hypertension is established by higher readings at home.", "That term describes the opposite directional pattern."),
   ("A new drug should be chosen before reviewing measurement validity.", "Confirming the pattern helps avoid treating measurement error.")],
  "Valid home or ambulatory readings can uncover hypertension absent from the clinic visit. Establish the reproducible pattern and its context before selecting an individualized management plan.", secondary=("T08",), skill="interpretation")


q("T10", 3, 2, GD, "Figure 30 caption, printed S130; Practice Point 3.3.4, S133: immunologic response can precede clinical remission",
  "During treatment of PLA2R-associated membranous nephropathy, antibodies become undetectable but proteinuria persists early in follow-up. What is the best interpretation?",
  "Immunologic improvement can precede the clinical proteinuria response; assess the longitudinal pattern before declaring failure.",
  [("Persistent proteinuria proves that antibody production is unchanged.", "The antibody measurement shows a different trend."),
   ("Undetectable antibodies establish complete structural recovery immediately.", "A serologic response is not instant repair of the filtration barrier."),
   ("The antibody result makes kidney function and proteinuria follow-up unnecessary.", "Clinical response and complications still require monitoring.")],
  "Serologic activity and clinical recovery have different time courses. Integrate serial antibodies, proteinuria, albumin, filtration and treatment exposure rather than treating one early discordant measurement as a definitive outcome.", secondary=("T02", "T26"), skill="mechanism")
q("T10", 4, 1, GD, "Practice Point 7.1.2.1 and Figure 57, printed S173-S174: bacterial infection-related glomerulonephritis",
  "An adult with active bacterial endocarditis develops AKI and a nephritic urine pattern. Which reasoning should guide the glomerular evaluation?",
  "Infection-related injury belongs in the differential, and infection control is central to the assessment.",
  [("Nephritic urine findings exclude infection as a kidney mechanism.", "Infection can cause immune-mediated glomerular injury."),
   ("The kidney findings establish a primary sterile immune disease before other data.", "The active infection changes the differential and treatment risks."),
   ("An active infection can be left untreated until the urine sediment normalizes.", "The infection itself requires timely management.")],
  "Glomerular inflammation does not imply an infection-independent disease. Establish the infectious and renal phenotype, consider tissue when useful, and coordinate infection treatment rather than reflexively treating every nephritic presentation identically.", secondary=("T17", "T06"), skill="common_reasoning")
q("T11", 3, 1, DM, "Section 1.3: SGLT2 inhibition and proximal glucose reabsorption",
  "A patient taking an SGLT2 inhibitor has glycosuria with normal current plasma glucose, but no phosphate, bicarbonate or other inappropriate solute losses. What is the most direct explanation to consider?",
  "The medicine's intended inhibition of proximal glucose reabsorption.",
  [("Glycosuria alone establishes generalized Fanconi syndrome.", "Other proximal losses and the medication context matter."),
   ("A distal acidification defect directly prevents glucose reabsorption.", "Glucose reabsorption occurs upstream in the proximal tubule."),
   ("Normal current glucose excludes drug-mediated glycosuria.", "The drug alters the renal glucose threshold.")],
  "An isolated finding can reflect a selected transporter effect rather than generalized tubular dysfunction. Interpret urine glucose with medicines, blood glucose and the other solute-handling features.", secondary=("T14", "T19"), skill="mechanism")
q("T11", 4, 2, RTA, "Clinical diagnosis, printed p1586; Urine pH, p1588: systemic acid-base context and inappropriate acidification",
  "A urine pH of 6.6 is found on one spot sample. Serum bicarbonate is normal. Which interpretation of distal RTA is justified?",
  "The spot pH alone is insufficient; interpret acidification in the systemic acid-base and clinical context.",
  [("Any urine pH above 6 establishes distal RTA.", "One urine pH lacks the acid-base and clinical context needed for diagnosis."),
   ("A urine pH result identifies the patient's serum anion gap.", "The serum gap requires separate blood measurements."),
   ("One urine pH measurement proves a proximal glucose-reabsorption defect.", "Urine acidity does not establish inappropriate proximal glucose loss.")],
  "The classic dRTA pattern involves normal-gap metabolic acidosis with inappropriate urine acidification. One alkaline result without that context is not diagnostic; persistent stone or tubular features warrant appropriate further assessment. Normal bicarbonate alone is not used here to exclude every acidification defect.", secondary=("T04", "T13"), skill="common_reasoning")
q("T12", 3, 2, PKD, "Practice Points 4.1.4.2-4.1.4.4, printed S121: aquaresis, hydration and temporary interruption",
  "An adult with ADPKD taking tolvaptan develops vomiting and cannot maintain oral fluid intake. Which treatment mechanism makes the interruption plan relevant?",
  "Continued aquaresis can worsen water loss when replacement intake is inadequate.",
  [("Tolvaptan directly replaces the fluid lost through vomiting.", "It increases free-water excretion rather than replacing water."),
   ("A normal previous sodium result excludes later dehydration risk.", "Risk changes when intake and losses change."),
   ("A temporary interruption necessarily ends all future disease-modifying treatment.", "Recovery and safe resumption can be assessed under an explicit plan.")],
  "An aquaretic treatment requires access to and adequate intake of water. Follow the patient-specific sick-day/interruption instructions and reassess hydration and resumption; do not infer safety from a prior normal laboratory value.", secondary=("T03", "T19"), skill="mechanism")
q("T12", 4, 1, PKD, "Recommendation 6.1.2 and Practice Point 6.1.8, printed S150: ICA screening risk and informed choice",
  "An adult with ADPKD reports a first-degree relative with subarachnoid hemorrhage. What does this history change?",
  "It strengthens the indication for a guideline-informed aneurysm-screening discussion and risk assessment.",
  [("Preserved eGFR removes aneurysm risk from consideration.", "The extrarenal risk is not determined by filtration alone."),
   ("The family event proves that the patient has an aneurysm.", "It is a risk feature, not the patient's imaging diagnosis."),
   ("Every person with ADPKD requires immediate invasive angiography.", "Screening eligibility, modality and preferences require assessment.")],
  "Personal/family vascular history changes screening decisions. Discuss benefits, limitations and consequences, including treatment eligibility and life expectancy, with the relevant team; a risk feature is not a positive test.", secondary=("T24", "T26"), skill="common_reasoning")
q("T13", 3, 2, STONE, "Index patient: uric acid stones; low urine pH and solubility",
  "A recurrent uric acid stone former has persistently acidic urine without marked hyperuricemia. Which mechanism is still relevant to recurrence?",
  "Low urine pH reduces uric acid solubility, so a normal serum urate does not exclude the stone mechanism.",
  [("Serum urate alone fully determines urinary uric acid solubility.", "Urine pH and concentration also matter."),
   ("Uric acid is most soluble in strongly acidic urine.", "Acidity favors the less soluble protonated form."),
   ("Stone composition can be inferred from serum urate without examining the stone.", "Serum chemistry does not replace composition analysis.")],
  "Low pH can be a major determinant of uric acid stones. Use composition and urine evaluation to guide an individualized prevention plan rather than requiring marked hyperuricemia before considering the mechanism.", secondary=("T04", "T14"), skill="mechanism")
q("T13", 4, 2, STONE, "Dietary sodium section: sodium intake and urinary calcium",
  "A calcium stone former has high urinary sodium and calcium on a suitable metabolic collection. Why is sodium intake relevant to prevention?",
  "Higher sodium intake can increase urinary calcium loss.",
  [("Dietary sodium affects only blood pressure, never calcium handling.", "Sodium intake and calciuria are linked."),
   ("The finding means dietary calcium must be eliminated.", "Normal dietary calcium remains part of balanced prevention."),
   ("A high urinary calcium concentration by itself identifies a parathyroid adenoma.", "Several dietary and metabolic mechanisms can produce it.")],
  "Review sodium intake alongside urine volume, calcium, oxalate and other risk factors. Addressing high sodium can help reduce calciuria without indiscriminate calcium restriction or assuming a single endocrine cause.", secondary=("T09", "T25"), skill="mechanism")
q("T14", 3, 2, DM, "Recommendation 4.1.1; Figure 27: metformin eligibility and eGFR-based adjustment",
  "An adult with type 2 diabetes has persistently stable eGFR 27 mL/min/1.73 m2 while still taking metformin. Which action fits the 2022 kidney-diabetes guidance?",
  "Discontinue metformin and review suitable alternatives because eGFR is persistently below 30.",
  [("Continue an unchanged dose because serum glucose is controlled.", "Glycemic efficacy does not resolve reduced-clearance safety."),
   ("Increase the dose to compensate for the lower GFR.", "Reduced clearance does not justify that adjustment."),
   ("Use the glucose level alone to determine eligibility.", "Kidney function is part of the eligibility/dosing assessment.")],
  "The guideline's metformin recommendation starts at eGFR 30, with dose adjustment and monitoring above that threshold. Below 30, use an alternative plan; distinguish a persistent state from an acute evolving illness requiring its own review.", secondary=("T19", "T08"))
q("T14", 4, 1, DM, "Practice Point 1.3.3: SGLT2 inhibitors during fasting, surgery or critical illness",
  "An adult taking an SGLT2 inhibitor is preparing for surgery with prolonged fasting. Why does a planned temporary hold matter even if glucose is not markedly high?",
  "Fasting and illness can increase ketosis risk during SGLT2 inhibition.",
  [("Only severe hyperglycemia makes ketosis possible in this setting.", "Ketosis can occur without marked glucose elevation."),
   ("The hold is intended to reverse all established CKD benefit permanently.", "It addresses an acute treatment-specific risk."),
   ("A hold needs no documented resumption plan.", "Failure to reassess resumption can cause unintended long-term discontinuation.")],
  "Surgery/fasting changes treatment safety. Coordinate the treatment-specific interruption and restart plan rather than applying routine outpatient continuation to an acute risk period.", secondary=("T19", "T27"), skill="mechanism", extra_sources=((CKD, "Practice Point 4.3.2: restart communication"),))
q("T15", 3, 1, LN, "Practice Point 10.3.1.1 and rationale, printed S47-S48: TMA etiologic assessment",
  "A lupus kidney biopsy shows thrombotic microangiopathy. What does that histologic pattern establish about the cause?",
  "It establishes a pattern of microvascular injury, but not a single mechanism such as complement-mediated disease.",
  [("It independently proves severe ADAMTS13 deficiency.", "That requires the appropriate diagnostic measurement."),
   ("It rules out antiphospholipid or other secondary mechanisms.", "Different pathways can produce the pattern."),
   ("All patients with the pattern have the same treatment indication.", "Etiologic evaluation affects the disease-directed plan.")],
  "A TMA lesion needs clinical/laboratory mechanism assessment. Lupus-associated presentations can involve different pathways; tissue morphology alone does not select a universal plasma/complement treatment.", secondary=("T16", "T22"), skill="common_reasoning")
q("T15", 4, 2, TTP, "Introduction and Recommendation 1: severe ADAMTS13 deficiency and inhibitor assessment",
  "In a compatible TMA syndrome, pretreatment ADAMTS13 activity is 4% with an inhibitor detected. Which diagnosis does the result most strongly support?",
  "Immune-mediated TTP.",
  [("Routine erythropoietin-deficiency anemia of CKD.", "It does not explain severe enzyme deficiency with an inhibitor."),
   ("A complement mechanism is established solely by the presence of AKI.", "AKI does not override the disease-specific ADAMTS13 evidence."),
   ("The TMA is excluded because the kidney is involved.", "Kidney involvement does not exclude TTP.")],
  "Severe pretreatment ADAMTS13 deficiency, conventionally below 10%, is central to TTP assessment. An inhibitor supports an immune mechanism in the appropriate phenotype; interpret it through the urgent specialist pathway.", secondary=("T23", "T06"))
q("T16", 3, 2, AAV, "Practice Point 9.2.3.1 and accompanying explanation, printed S93: ANCA monitoring limitations",
  "An adult with treated AAV remains clinically well, but ANCA stays positive. Which response best fits the biomarker's limitations?",
  "Use clinical and organ-specific monitoring; persistence alone is not a sufficient reason to escalate immunosuppression.",
  [("The positive result establishes an organ-threatening relapse today.", "A biomarker association is not the same as active organ disease."),
   ("Normal symptoms make future kidney/urine monitoring unnecessary.", "Silent or evolving organ findings still warrant surveillance."),
   ("Every change in titer identifies the exact histologic lesion.", "Serology does not supply tissue-level information.")],
  "ANCA can inform relapse risk but is insufficient by itself to direct an individual's treatment escalation. Review symptoms, kidney trend, urine findings and the broader assessment while preserving appropriate follow-up.", secondary=("T02", "T26"), skill="common_reasoning")
q("T16", 4, 1, LN, "Practice Point 10.2.5.2.1, Figure 12 and Section 10.2.5.3, printed S46-S47: unsatisfactory response",
  "After lupus nephritis treatment, proteinuria persists and it is unclear whether inflammation remains active. What can a targeted repeat-biopsy discussion help resolve?",
  "Whether residual activity, chronic damage or another lesion better explains the incomplete response.",
  [("Proteinuria alone quantifies current histologic activity.", "Residual protein loss can have more than one explanation."),
   ("A repeat biopsy guarantees that more immunosuppression will help.", "Its findings may support a different conclusion."),
   ("A prior class label makes subsequent tissue information irrelevant.", "The lesion and balance of activity/chronicity can evolve.")],
  "First review treatment exposure, adherence and the clinical course. When the active-versus-damage distinction would change management, tissue reassessment can add information; do not equate persistent proteinuria with a fixed amount of treatable inflammation.", secondary=("T10", "T22"), skill="common_reasoning")
q("T17", 3, 2, TX, "Recommendation 10.7.2.1, printed S61: live vaccination interval before transplantation",
  "A transplant candidate received a live vaccine five days before a proposed elective transplant. Which timing issue should be coordinated with the transplant team?",
  "The guideline recommends completing live vaccination at least four weeks before transplantation.",
  [("Live vaccination and nonlive vaccination have identical timing constraints.", "The infection risk under immunosuppression differs."),
   ("A live vaccine is equivalent to an active serious infection in every recipient.", "The issue is a timing/risk assessment, not that diagnosis."),
   ("A listing decision makes vaccination timing irrelevant.", "Planned immunosuppression changes the safety context.")],
  "Review vaccine type, dates and the anticipated immunosuppression interval. The candidate guideline uses a minimum four-week interval for live vaccines; condition-specific specialist planning remains necessary.", secondary=("T21", "T19"))
q("T17", 4, 1, TX, "Recommendations 11.2.2, 11.2.3.2 and 11.2.4, printed S63-S64: cancer and candidate timing",
  "A transplant candidate previously completed cancer treatment and is in remission. Which reasoning best fits candidate assessment?",
  "Assess cancer type/stage, remission course and transplant-related recurrence risk with the relevant teams.",
  [("Any previous cancer creates automatic permanent exclusion.", "History and active disease are not interchangeable."),
   ("The kidney-failure diagnosis makes recurrence risk irrelevant.", "Immunosuppression and competing outcomes must be considered."),
   ("A single universal waiting interval applies to every treated malignancy.", "Tumor-specific prognosis and circumstances differ.")],
  "Candidate decisions are individualized and multidisciplinary. Distinguish active malignancy from treated disease and balance recurrence, waiting and kidney-failure risks rather than using one historical label as the entire decision.", secondary=("T18", "T21", "T26"), skill="common_reasoning")
q("T18", 3, 2, MGRS, "Monoclonal immunoglobulin testing: kidney clearance and free light-chain interpretation",
  "In advanced CKD, both serum free light-chain concentrations are raised with only a modest ratio shift. What should precede declaring a clonal disorder?",
  "Interpret the assay, kidney function and appropriate reference context alongside electrophoresis/immunofixation and the clinical picture.",
  [("Any elevation of both chains proves monoclonality.", "Reduced clearance can raise polyclonal light-chain concentrations."),
   ("Free light-chain interpretation is independent of kidney clearance.", "Kidney dysfunction affects these measurements."),
   ("A mildly abnormal ratio establishes the renal biopsy lesion.", "Blood tests do not identify the tissue pattern or causality.")],
  "Reduced kidney clearance complicates free light-chain interpretation, and assays/reference contexts differ. Use the whole monoclonal and renal evaluation rather than inferring a pathogenic clone from one modestly shifted result.", secondary=("T08", "T22"), skill="mechanism")
q("T18", 4, 1, MGRS, "Renal biopsy evaluation: amyloid typing and limits of coincident monoclonal gammopathy",
  "Kidney tissue contains amyloid, and a small monoclonal component is also found in blood. What is needed before attributing the amyloid to that clone?",
  "Appropriate tissue amyloid typing and correlation with the clonal findings.",
  [("The serum component alone establishes AL amyloidosis.", "A monoclonal component can coexist with another amyloid type."),
   ("Congo red identifies the precursor protein without further assessment.", "It identifies an amyloid pattern, not every protein type."),
   ("The size of the monoclonal component directly determines the tissue protein identity.", "Concentration does not establish deposit composition.")],
  "The precursor protein matters to mechanism and treatment. Use appropriate pathology typing, with specialized methods where needed, rather than equating coincident monoclonal gammopathy with proven AL renal amyloidosis.", secondary=("T22", "T02"), skill="common_reasoning")


q("T19", 3, 1, CKD, "Section 4.2; Practice Points 4.2.2-4.2.4: dosing metric, precision and body-size indexing",
  "A medicine's dosing instructions specify an absolute clearance in mL/min, while the laboratory reports eGFR in mL/min/1.73 m2. What needs checking before copying the number into the dose table?",
  "The requested clearance metric, body-size indexing and precision appropriate to that medicine.",
  [("The two units describe identical quantities at every body size.", "One is normalized to a standard body surface area."),
   ("Every creatinine-clearance estimate is numerically identical to any eGFR equation.", "The metrics and estimation methods can differ."),
   ("A dose table removes the need to assess changing kidney function.", "A stable estimate may not represent an evolving acute illness.")],
  "Match the drug's specified metric and units rather than treating all kidney estimates as interchangeable. Account for body size and estimation uncertainty, with a more accurate approach when the therapeutic decision requires it.", secondary=("T01",), skill="common_reasoning")
q("T19", 4, 2, CKD, "Practice Point 4.3.1; Table 31: complete medication review and kidney-risk contributors",
  "A CKD patient reports no new prescriptions, but a transition-of-care review finds an OTC NSAID and a potassium-containing salt substitute. What does this illustrate?",
  "A prescription-only list can miss clinically relevant kidney and potassium exposures.",
  [("Nonprescription products cannot interact with kidney treatment.", "Their biological effects do not depend on prescription status."),
   ("The word natural establishes the absence of adverse effects.", "Marketing labels do not define kidney safety."),
   ("The two exposures establish the sole cause of every laboratory change.", "They are contributors to evaluate, not automatic exclusive causality.")],
  "Review OTC products, supplements and diet-related exposures alongside prescriptions. Reconcile the complete list with kidney function, potassium and the clinical course, especially when several clinicians are involved.", secondary=("T04", "T25"), skill="common_reasoning", extra_sources=((BP, "Practice Point 2.1.2: potassium-rich salt substitutes"),))
q("T20", 3, 1, HD, "Appendix 1, printed p26: urea reduction ratio definition",
  "Correctly sampled pre- and post-hemodialysis urea concentrations are 20 and 6 mmol/L. What is the unadjusted urea reduction ratio?",
  "70%.",
  [("30%.", "That is the fraction remaining, not the reduction."),
   ("14%.", "The absolute concentration difference must be divided by the predialysis concentration."),
   ("233%.", "Dividing the fall by the postdialysis value uses the wrong denominator.")],
  "URR = (20 - 6) / 20 x 100 = 70%. This arithmetic depends on valid sampling and is not a complete measure of adequacy, fluid balance, residual function or nutrition.", secondary=("T23", "T26"), calculation={"expression": "(20 - 6) / 20 * 100", "result": 70, "unit": "percent"})
q("T20", 4, 2, PD, "Section 3, Guidelines 3.1 and 3.2.1, printed p9: urinary/peritoneal and total small-solute clearance",
  "A PD prescription and measured peritoneal clearance are unchanged, but residual kidney clearance falls. What can happen to total small-solute clearance?",
  "It can fall because the kidney contribution has decreased.",
  [("It must remain fixed because the peritoneal prescription is fixed.", "Total clearance includes more than the peritoneal contribution."),
   ("The peritoneal component necessarily doubles to compensate automatically.", "Compensation is not guaranteed."),
   ("The lost contribution affects water only, never solute clearance.", "Residual kidney function contributes to both.")],
  "A fixed prescription is not a fixed total delivered treatment when residual function changes. Reassess clinical response and both clearance components rather than interpreting the bag regimen in isolation.", secondary=("T23",), skill="mechanism")
q("T21", 3, 1, DONOR, "Recommendations 6.1-6.6, printed S42: donor albuminuria measurement and selection",
  "A potential living donor has confirmed albumin excretion 55 mg/day and otherwise favorable initial results. What does the donor guideline advise for this albuminuria range?",
  "Individualize eligibility using the full risk profile and the program's acceptable-risk threshold.",
  [("Accept automatically because the GFR is normal.", "Albuminuria contributes information beyond GFR."),
   ("Exclude automatically using the guideline's greater-than-100 mg/day category.", "55 mg/day is in the intermediate 30-100 range."),
   ("Use total urine protein as an interchangeable donor albumin measurement.", "The guideline specifies albumin and appropriate confirmation.")],
  "The dated donor guidance treats AER 30-100 mg/day as an individualized decision, not automatic acceptance or rejection. Confirm the measurement and consider the candidate's overall future risk and program criteria.", secondary=("T02", "T08"))
q("T21", 4, 2, DONOR, "Recommendations 2.1-2.8, printed S27: voluntary consent and confidential withdrawal",
  "A medically suitable donor privately says family pressure is making consent difficult and asks to withdraw. What principle should guide the team?",
  "Protect voluntary choice and confidential withdrawal, with support for communicating the decision.",
  [("Medical suitability makes consent concerns secondary to the recipient's need.", "Suitability does not replace a voluntary decision."),
   ("The earlier evaluation commits the donor to completing the operation.", "A donor may reconsider and withdraw."),
   ("The family should receive every private reason before withdrawal is accepted.", "The guidance protects confidentiality.")],
  "Living donation requires informed, capable and voluntary choice. A favorable medical evaluation is not authorization to override a donor's decision; privacy and a supported exit are part of the process.", secondary=("T26",), skill="common_reasoning")
q("T22", 3, 1, GD, "Section 1.1, printed S89; Chapter 6.1, S162: biopsy sampling and the focal nature of FSGS",
  "Only three glomeruli are represented in a small biopsy, and none shows segmental sclerosis. What limits the conclusion that FSGS is excluded?",
  "A focal lesion can be missed by limited sampling.",
  [("Focal means every glomerulus must contain the lesion.", "That is the opposite of focal involvement."),
   ("A normal ultrasound proves that the biopsy sample is representative.", "Imaging does not establish microscopic sampling adequacy."),
   ("The absence of the lesion in a small sample specifies another diagnosis.", "A negative limited sample does not identify an alternative cause.")],
  "Sampling adequacy and clinicopathologic correlation matter when lesions affect only some glomeruli. Interpret the whole specimen, ultrastructure and phenotype with renal pathology rather than turning a limited negative sample into absolute exclusion.", secondary=("T10",), skill="common_reasoning")
q("T22", 4, 2, MGRS, "Renal biopsy evaluation: electron microscopy and additional methods when routine immunofluorescence is unrevealing",
  "Routine immunofluorescence is unrevealing, but tissue/clinical findings still suggest a deposition process. Which contribution can a renal-pathology review add?",
  "Ultrastructural assessment and selected additional testing can clarify deposits or a masked pattern.",
  [("Negative routine immunofluorescence excludes every deposition disorder.", "Some relevant lesions need additional methods."),
   ("A blood monoclonal result makes further tissue characterization unnecessary.", "The renal lesion and the circulating protein still need correlation."),
   ("Electron microscopy establishes the whole hematologic clone independently.", "It describes tissue structure, not every aspect of clonal evaluation.")],
  "Complementary pathology methods answer different questions. If the pattern and routine tests disagree, review specimen adequacy, ultrastructure and appropriate specialized techniques with the pathologist rather than treating one method as exhaustive.", secondary=("T18", "T02"))
q("T23", 3, 1, HD, "Membrane flux and haemodiafiltration, convective-clearance rationale, printed p12: membrane permeability and solute size",
  "Two dialysis treatments achieve similar urea dose metrics but use membranes with different larger-solute permeability. What can be inferred about all solute removal?",
  "Similar urea metrics do not establish identical clearance of larger molecules.",
  [("Urea is a complete proxy for every molecular size.", "Different molecules interact differently with membrane and flow properties."),
   ("Membrane permeability affects water only, never solutes.", "It influences which solutes can cross the membrane."),
   ("A larger molecule must always diffuse faster than urea.", "Size can limit diffusive transport.")],
  "A small-solute dose metric does not characterize the entire clearance spectrum. Molecular size, membrane properties, treatment mechanism and delivery influence removal; assess the outcome relevant to the clinical question.", secondary=("T20",), skill="interpretation")
q("T23", 4, 2, AKI, "Section 5.3.2 and citrate-anticoagulation rationale: calcium chelation",
  "What mechanism chiefly produces regional anticoagulation when citrate is used in an extracorporeal kidney-support circuit?",
  "Chelation lowers ionized calcium in the circuit, impairing calcium-dependent coagulation.",
  [("Citrate supplies a higher circuit ionized calcium concentration.", "Its anticoagulant effect involves the opposite change."),
   ("Citrate removes all platelets by diffusion across the filter.", "That is not the regional anticoagulation mechanism."),
   ("Citrate acts only by cooling the circuit.", "Its principal effect is biochemical rather than temperature-mediated.")],
  "Circuit calcium and systemic calcium are separate monitoring concerns. The mechanism does not remove the need for an appropriate protocol, calcium support and review of metabolic handling; no patient-specific prescription is established by this question.", secondary=("T07", "T05"), skill="mechanism")
q("T24", 3, 1, DONOR, "Recommendations 15.4 and 15.9, printed S78: future pregnancy and donor counseling",
  "A potential living donor hopes to become pregnant after recovery. Which counseling approach matches the 2017 donor guidance?",
  "Future pregnancy alone does not exclude donation, but discuss the increased likelihood of gestational hypertension or preeclampsia.",
  [("Future conception is an automatic lifelong exclusion criterion.", "The guideline does not support exclusion solely for that intention."),
   ("Donation has no pregnancy-related risk information worth discussing.", "The guideline recommends specific counseling."),
   ("A normal predonation BP guarantees no later hypertensive pregnancy disorder.", "Baseline findings cannot eliminate all future risk.")],
  "Separate eligibility from informed risk counseling. Review prior pregnancy/vascular history, plans and timing with the donor and appropriate teams; provide information for a voluntary decision rather than guaranteeing an outcome.", secondary=("T21", "T09"), skill="common_reasoning")
q("T24", 4, 2, CKD, "Practice Points 5.4.1 and 5.5.1: composite assessment and supportive-care decisions",
  "An older adult with advanced CKD and frailty asks whether a risk-equation output alone determines that dialysis is the best option. What is the best response?",
  "It informs planning, while symptoms, function, competing risks, expected burdens and the person's goals inform the treatment decision.",
  [("A numerical risk output establishes the person's treatment preference.", "Preferences require discussion rather than prediction."),
   ("Chronological age alone determines that supportive care is compulsory.", "Decisions are individualized."),
   ("The equation predicts the individual's dialysis benefit without further assessment.", "Kidney-failure risk is not the same as treatment benefit.")],
  "Prediction supports preparation but cannot replace a composite clinical and preference assessment. Offer the applicable dialysis and comprehensive conservative-care options with revisable shared planning.", secondary=("T08", "T20", "T26"), skill="common_reasoning")
q("T25", 3, 1, BP, "Practice Point 2.1.2: potassium-rich salt substitutes in impaired potassium excretion",
  "An adult with advanced CKD replaces table salt with a potassium-rich substitute to lower sodium intake. Which tradeoff should the kidney/dietetic review address?",
  "Lower sodium exposure can be accompanied by an unsafe potassium load when excretion is impaired.",
  [("A sodium-reduction label establishes kidney safety regardless of ingredients.", "The replacement ingredient has its own biological effects."),
   ("Salt substitutes contain no electrolytes.", "Some contain substantial potassium salts."),
   ("The choice eliminates the need to review other potassium contributors.", "Medicines, supplements and the overall diet still matter.")],
  "A useful dietary substitution must fit the person's kidney function and potassium-handling capacity. Examine ingredients and the whole intake/medicine pattern rather than treating one nutrient goal as the entire plan.", secondary=("T04", "T09", "T19"), skill="mechanism")
q("T25", 4, 2, CKD, "Practice Point 3.3.1.4, printed S157: protein intake in children with CKD",
  "A 14-year-old with CKD and poor growth is given the adult protein-restriction plan without pediatric dietetic assessment. Which guideline principle has been missed?",
  "Protein should not be restricted in children with CKD because of the risk of growth impairment.",
  [("Adult dietary targets apply unchanged throughout growth.", "Developmental needs alter the nutritional balance."),
   ("Impaired kidney function makes linear growth unimportant.", "Growth remains a key pediatric outcome."),
   ("A lower intake is always safer if a diet is called kidney-protective.", "Restriction can cause developmental and nutritional harm.")],
  "The CKD guideline distinguishes pediatric growth needs from adult restriction strategies. Obtain age-appropriate nutritional assessment and support rather than automatically transferring an adult target.", secondary=("T24",), skill="common_reasoning")
q("T26", 3, 2, CKD, "Guideline grading key: strength 2 and certainty C",
  "A guideline statement is graded 2C. Which interpretation is appropriate?",
  "It is a conditional recommendation supported by low-certainty evidence, requiring attention to individual circumstances and preferences.",
  [("It is a strong recommendation with high-certainty evidence.", "That describes a different strength/certainty combination."),
   ("The label means 2% of patients benefit and 3% experience harm.", "The grade is not an effect-size estimate."),
   ("It removes the need to discuss differing reasonable choices.", "Conditional recommendations make individual variation especially relevant.")],
  "Recommendation strength and certainty are separate dimensions. A grade does not state the magnitude of benefit or substitute for assessing applicability, alternatives and values.", secondary=("T24",), skill="interpretation")
q("T26", 4, 2, CKD, "Methods: outcome selection, evidence profiles and certainty; synthetic outcome-interpretation exercise",
  "An explicitly synthetic eight-week dietary trial lowers serum urea but does not measure kidney-failure events, symptoms or nutritional harms. Which conclusion is directly supported?",
  "The measured urea outcome changed; the trial does not establish long-term clinical benefit or its benefit-harm balance.",
  [("Kidney-failure prevention is proven by the urea change alone.", "That outcome was not measured."),
   ("A favorable biomarker change excludes nutritional harm.", "Potential harms need measurement and assessment."),
   ("The eight-week result establishes the same effect over every follow-up period.", "Time horizon and outcome relevance matter.")],
  "Distinguish an observed surrogate result from unmeasured patient-important outcomes. This synthetic exercise asserts no real trial result; it illustrates why outcome choice, duration and harms affect evidence interpretation.", secondary=("T25",), skill="common_reasoning")
q("T27", 3, 1, CKD, "Chapter 3.14 and relative/absolute risk overview: albuminuria and cardiovascular risk",
  "An adult has preserved eGFR but persistent severely increased albuminuria. Why should cardiovascular assessment remain part of kidney care?",
  "Albuminuria contributes risk information that preserved filtration does not erase.",
  [("An eGFR above 60 guarantees negligible cardiovascular risk.", "Filtration is only one part of the risk assessment."),
   ("Albuminuria is relevant only after dialysis begins.", "It informs risk before kidney failure."),
   ("The albuminuria category alone establishes which cardiac diagnosis is present.", "A risk marker is not a specific cardiac diagnosis.")],
  "Kidney and cardiovascular risk assessment uses more than one marker and the whole clinical profile. Preserved eGFR should not lead to dismissal of persistent albuminuria or associated preventive-care needs.", secondary=("T02", "T09", "T14"), skill="common_reasoning")
q("T27", 4, 2, GD, "Practice Point 1.7.1: thromboprophylaxis and individual bleeding risk in nephrotic syndrome",
  "An adult with nephrotic membranous disease has substantial thrombosis risk but also a recent serious gastrointestinal bleed. Which principle governs prophylactic anticoagulation assessment?",
  "Weigh thromboembolism risk against the person's serious-bleeding risk rather than using proteinuria or albumin alone.",
  [("All nephrotic patients need the same prophylaxis regardless of bleeding history.", "Patient-specific bleeding risk changes the balance."),
   ("A high thrombosis risk makes anticoagulation-related bleeding impossible.", "Both risks can be present."),
   ("Prophylaxis and treatment of an established thromboembolic event are identical decisions.", "They have different clinical contexts and indications.")],
  "The remaining glomerular guidance bases prophylaxis on thrombotic risk exceeding estimated serious-bleeding risk. Assess the competing risks and clinical circumstances; this scenario does not supply a patient-specific drug or dose.", secondary=("T10", "T19", "T26"), skill="common_reasoning")


def case(identity, topic, secondary, objectives, title, summary, stages, take_home):
    base.case(identity, topic, list(secondary), list(objectives), title, summary, stages, take_home, items=_CASE_POOL)
    item = _CASE_POOL[-1]
    item["review"]["method"] = (
        "Assistant primary section and cross-domain scenario check; stage-to-source review; "
        f"synthetic patient and original teaching discussion. Evidence identity: {identity}.")
    NEW_CASES.append(item)
    EVIDENCE.append({"id": identity, "version": 1, "kind": "case",
                     "skill": "mixed_domain_reasoning",
                     "source_locators": deepcopy(item["sources"]),
                     "reviewed_on": DATE, "reviewer_kind": "assistant",
                     "key_text": None, "checked_claim": " | ".join(take_home),
                     "calculation": None, "independent_human_review": False})


stage = base.stage
case("RN11-CASE-PROXIMAL", "T11", ("T18", "T02", "T22"),
     ("T11.O01", "T18.O01", "T18.O02", "T02.O02", "T22.O01"),
     "Protein that an albumin test misses",
     "Localize tubular losses and investigate a possible monoclonal kidney lesion without assuming causality.", [
    stage("A synthetic 61-year-old has fatigue, hypophosphatemia and urinary glucose despite normal plasma glucose. PCR is 2.9 g/g and ACR is 0.18 g/g.",
          ["Which findings localize the problem?", "What does the ACR/PCR discrepancy add?"],
          ["The glucose/phosphate pattern suggests inappropriate proximal losses.",
           "Total protein substantially exceeding albumin calls for characterization of nonalbumin proteins rather than dismissal of proteinuria."],
          MGRS, "Light-chain proximal tubulopathy; monoclonal immunoglobulin testing"),
    stage("Blood and urine testing identify a small monoclonal component. There is no established hematologic malignancy diagnosis.",
          ["Can a small clone matter to the kidney?", "Which alternative interpretation must remain open?"],
          ["A small clone can produce a pathogenic protein; malignancy thresholds do not define renal harmlessness.",
           "A monoclonal component can also be incidental. The circulating protein must be linked to the renal process."],
          MGRS, "Definition and evaluation of MGRS"),
    stage("A kidney/hematology discussion considers tissue assessment and the patient's procedural risk.",
          ["What does biopsy add beyond a serum spike?", "Which pathology methods may be needed?"],
          ["Tissue can characterize the renal lesion and help establish the link with the clone.",
           "Light microscopy, appropriate immunofluorescence and electron microscopy are complementary; a single method can miss relevant features."],
          MGRS, "Renal biopsy evaluation"),
], ["A normal glucose concentration does not explain away glycosuria.",
    "A monoclonal result is a lead to investigate, not automatic renal causality."])

case("RN11-CASE-OBSTRUCTION", "T13", ("T17", "T06", "T07", "T27"),
     ("T13.O01", "T17.O02", "T06.O02", "T27.O02"),
     "Sepsis behind an obstructed collecting system",
     "Connect infection, obstruction and kidney support; separate urgent source control from later stone prevention.", [
    stage("A synthetic adult has flank pain, fever, hypotension and imaging-confirmed obstruction. The contralateral kidney looks normal.",
          ["What makes this different from uncomplicated renal colic?", "Does the other kidney remove the urgency?"],
          ["Suspected infected obstruction requires urgent coordinated resuscitation, antibiotics and drainage assessment.",
           "A normal other kidney does not eliminate a dangerous infected obstructed source."],
          OBSTRUCT, "Conservative management: obstructive pyelonephritis"),
    stage("Urine output falls and potassium begins to rise while the source-control plan is organized.",
          ["Which problems must be assessed in parallel?", "Which action addresses the source rather than only a biochemical consequence?"],
          ["Assess circulation, urine output, electrolytes and evolving AKI while treating infection and obstruction.",
           "KRT can support urgent physiologic needs, but it does not mechanically drain the infected urinary tract."],
          AKI, "Sections 2.3 and 5.1: cause evaluation and emergent KRT indications"),
    stage("After recovery, the patient asks whether the stone should be managed exactly like an asymptomatic stone found incidentally.",
          ["How should the episode be documented for follow-up?", "Which decisions belong after stabilization?"],
          ["Record the infection/obstruction episode and the intervention, with a clear urology/kidney follow-up handoff.",
           "Definitive stone management and recurrence assessment follow the acute source-control episode rather than replacing it."],
          OBSTRUCT, "Obstructive pyelonephritis: definitive treatment after infection treatment"),
], ["Treat the obstructed infected source as well as systemic consequences.",
    "Kidney support and urologic source control solve different problems."])

case("RN11-CASE-TMA", "T15", ("T16", "T06", "T23", "T27"),
     ("T15.O01", "T15.O02", "T23.O02", "T27.O02"),
     "A syndrome is not yet its mechanism",
     "Recognize TMA and protect diagnostic sampling while coordinating urgent specialist treatment.", [
    stage("A synthetic adult has thrombocytopenia, schistocytes, biochemical hemolysis and acute kidney dysfunction.",
          ["Which syndrome does the combination suggest?", "Which etiologic labels cannot yet be assumed?"],
          ["The combination suggests a thrombotic microangiopathy.",
           "TTP, complement-mediated disease and secondary mechanisms can overlap clinically; renal injury alone does not distinguish them."],
          TTP, "Introduction: TTP/HUS distinction and ADAMTS13"),
    stage("The hematology team considers TTP highly probable and urgent plasma exchange.",
          ["Which diagnostic sample should be obtained first if promptly feasible?", "Should care wait for the laboratory result?"],
          ["Collect ADAMTS13 activity/inhibitor testing before replacement plasma changes the measurement.",
           "The high-probability urgent pathway does not wait for the result; sampling and treatment must be coordinated without harmful delay."],
          TTP, "Recommendation 1, steps 1-2"),
    stage("The pretreatment sample shows severe ADAMTS13 deficiency with an inhibitor. The patient also needs support for a dangerous electrolyte disturbance.",
          ["How does the result refine the mechanism?", "Why are kidney support and plasma exchange not interchangeable?"],
          ["Severe deficiency with an inhibitor supports immune-mediated TTP in the compatible syndrome.",
           "Kidney support treats fluid/solute consequences; the plasma-directed pathway addresses a different disease mechanism."],
          TTP, "Introduction and Recommendation 1: severe deficiency and inhibitor evaluation"),
], ["TMA recognition is the start of etiologic assessment.",
    "Preserve pretreatment evidence without delaying time-critical specialist care."])

case("RN11-CASE-STONE-ACID", "T11", ("T04", "T13", "T05"),
     ("T11.O01", "T04.O02", "T13.O02", "T05.O01"),
     "An acidification defect behind recurrent stones",
     "Integrate persistent urine findings, acid-base measurements and calcium-phosphate stones.", [
    stage("A synthetic adult has recurrent calcium-phosphate stones, hypokalemia and low serum bicarbonate. There is no diarrhea or current urinary infection.",
          ["What kidney mechanism belongs in the differential?", "What information distinguishes a pattern from a confirmed diagnosis?"],
          ["Consider a distal acidification defect alongside other causes.",
           "Confirm the systemic acid-base pattern and persistent inappropriate urine pH rather than diagnosing from one alkaline sample."],
          RTA, "Diagnosis and pathophysiology"),
    stage("Repeat results show a normal anion gap and urine pH remaining above 6 during systemic acidosis.",
          ["Why is urine pH inappropriate here?", "How does this differ from proximal solute wasting?"],
          ["A functioning acidification response should lower urine pH during acidosis; confounders and timing must be checked.",
           "Normoglycemic glycosuria and phosphate wasting point to a different tubular localization and need separate assessment."],
          RTA, "Diagnostic criteria; proximal versus distal acidification defects"),
    stage("Stone testing reports hypocitraturia, and the patient asks why the kidney team is also asking about bone health.",
          ["How can acid-base and stone/bone findings connect?", "Why is treatment more than removing the latest stone?"],
          ["The acidification disorder can accompany hypocitraturia, calcium-phosphate stones and skeletal effects.",
           "An individualized metabolic plan addresses the underlying disorder and recurrence risk, with monitoring of electrolytes and nutrition."],
          STONE, "Index patient 2: calcium phosphate stones and distal RTA"),
], ["Persistent acid-base and urine patterns can localize a tubular disorder.",
    "Stone composition, citrate and bone concerns can be parts of the same process."])

case("RN11-CASE-PD-VOLUME", "T20", ("T23", "T03", "T25"),
     ("T20.O02", "T23.O01", "T25.O02"),
     "Small-solute clearance and fluid balance diverge",
     "Interpret peritoneal transport and residual kidney function without reducing dialysis care to one metric.", [
    stage("A synthetic peritoneal dialysis patient has an acceptable small-solute metric but increasing edema and declining daily urine output.",
          ["Which contributions to fluid removal should be reviewed?", "What does the small-solute result fail to establish?"],
          ["Review peritoneal ultrafiltration, residual kidney function, intake and the clinical volume state.",
           "One clearance metric cannot establish satisfactory fluid balance or overall treatment."],
          PD, "Sections 3-4: solute clearance and ultrafiltration/fluid management"),
    stage("Membrane testing indicates fast solute transport, and a long glucose dwell yields little net ultrafiltration.",
          ["What happens to the glucose osmotic gradient?", "Which information helps tailor the prescription?"],
          ["Faster glucose absorption can dissipate the driving gradient early in a long dwell.",
           "Transport characteristics, delivered exchanges, fluid response and patient circumstances guide prescription review."],
          PD, "Section 4: fast transport and ultrafiltration"),
    stage("The patient has also lost appetite. A relative suggests severe fluid and protein restriction without involving the dialysis team.",
          ["How should symptoms and nutrition affect the next plan?", "What would make a follow-up plan assessable?"],
          ["Balance volume management with nutrition, treatment tolerance and the person's priorities.",
           "Define monitoring of symptoms, weight/volume, ultrafiltration and residual function, with responsibility for reassessment."],
          HD, "Guidelines 1 and 4.1: holistic adequacy and fluid assessment"),
], ["Fluid balance and small-solute clearance are related but different outcomes.",
    "Changes in residual function and membrane transport should trigger a whole-patient review."])

case("RN11-CASE-PREGNANCY", "T24", ("T01", "T08", "T09", "T22", "T27"),
     ("T24.O01", "T24.O02", "T01.O01", "T22.O02", "T27.O02"),
     "When baseline CKD complicates pregnancy assessment",
     "Use pregnancy-valid kidney measurements and reassess new maternal changes without automatic attribution.", [
    stage("A synthetic pregnant adult with CKD is referred at 12 weeks. The laboratory prints an eGFR beside the serum creatinine.",
          ["Which filtration information is appropriate to follow?", "Which baseline measurements will help later interpretation?"],
          ["Pregnancy normally increases filtration and lowers serum creatinine, so a value ordinary outside pregnancy can require assessment in pregnancy.",
           "Use serum creatinine and its trend; routine eGFR equations are not validated in pregnancy.",
           "Document prior kidney function, proteinuria, BP and the clinical phenotype with obstetric/kidney coordination."],
          PREG, "Recommendation 4.1.1"),
    stage("At 16 weeks, unexplained new findings make a histologic diagnosis potentially important to treatment.",
          ["What management question should justify biopsy?", "How does timing enter the risk-benefit discussion?"],
          ["Ask whether tissue will change management rather than merely confirm an abnormal result.",
           "The guideline permits selected biopsy in the first or early second trimester with a specialist risk-benefit assessment."],
          PREG, "Recommendation 4.8.1"),
    stage("Later, after 20 weeks, new hypertension and maternal organ dysfunction develop.",
          ["Which obstetric-kidney differential must be revisited?", "Why does existing proteinuria not settle the issue?"],
          ["Consider superimposed preeclampsia and assess the full maternal/fetal picture.",
           "Baseline CKD/proteinuria complicates interpretation but does not exclude a new pregnancy-associated process."],
          PREG, "Recommendations 4.4.5-4.4.6"),
], ["Pregnancy changes the validity of familiar kidney measurements.",
    "A prior CKD diagnosis does not explain every later maternal abnormality."])


case("RN11-CASE-CARDIORENAL", "T27", ("T14", "T19", "T08", "T04", "T01"),
     ("T27.O01", "T27.O02", "T14.O01", "T19.O02", "T01.O01"),
     "A changing kidney estimate during heart and diabetes treatment",
     "Separate expected hemodynamics from intercurrent illness and make a coordinated medication plan.", [
    stage("A synthetic adult with diabetic CKD and heart failure starts an SGLT2 inhibitor. At early review the creatinine has risen slightly, symptoms are stable and the patient has no postural dizziness.",
          ["Which treatment effect belongs in the interpretation?", "What would make the same laboratory change more concerning?"],
          ["A modest reversible hemodynamic filtration change can follow SGLT2 inhibition; the laboratory trend needs its clinical context.",
           "Volume loss, hypotension, new illness or a disproportionate decline changes the assessment. A recognizable early effect does not exclude another problem."],
          DM, "Practice Points 1.3.4-1.3.5: volume assessment and reversible eGFR dip"),
    stage("Weeks later, vomiting and poor intake occur. Creatinine is now rising rapidly, and several medicines still have doses selected from the earlier stable eGFR.",
          ["Why is the printed eGFR less secure for current dosing?", "How should the team approach the medicine list?"],
          ["A changing marker concentration can lag the evolving filtration state; the number is not a measured instantaneous clearance.",
           "Review the acute physiology, each medicine's indication/clearance and interacting exposures. Use appropriate monitoring rather than copying the old outpatient doses."],
          CKD, "Practice Points 4.2.5 and 4.3.1: nonsteady-state dosing and medication review"),
    stage("After recovery, discharge planning involves kidney, diabetes and heart teams. Some treatments were held and potassium needs reassessment.",
          ["Which details prevent an accidental permanent discontinuation?", "What makes the cross-specialty plan coherent?"],
          ["Record why each hold occurred, what recovery/monitoring is required, and who will decide and communicate resumption.",
           "Balance continuing indications with potassium, BP, volume and kidney trends in one reconciled plan that the patient can follow."],
          CKD, "Practice Points 3.6.3 and 4.3.2: potassium review and restart communication"),
], ["A filtration estimate is interpreted with its kinetics and clinical setting.",
    "A temporary hold needs a visible reassessment and resumption plan across teams."])

case("RN11-CASE-NEPHROTIC-RISK", "T10", ("T02", "T22", "T26", "T27", "T19"),
     ("T10.O02", "T02.O01", "T26.O02", "T27.O02", "T19.O02"),
     "Different signals during nephrotic recovery",
     "Integrate serologic response, protein loss and competing thrombosis/bleeding risks without equating one marker with the whole outcome.", [
    stage("A synthetic adult with PLA2R-associated membranous disease has falling antibody levels after treatment, while urine protein remains substantial at the next early visit.",
          ["Are immunologic and clinical response the same event?", "Which trends belong together at review?"],
          ["Immunologic improvement can precede recovery of the protein-leak phenotype.",
           "Follow antibodies, proteinuria, serum albumin, filtration and complications with treatment exposure rather than labeling one early mismatch as definitive failure."],
          GD, "Figure 30 caption, printed S130; Practice Point 3.3.4, S133: immunologic monitoring and clinical-response lag"),
    stage("The patient has marked hypoalbuminemia but also a recently treated serious gastrointestinal bleed. Preventive anticoagulation is raised at the multidisciplinary review.",
          ["Which competing risks determine the prophylaxis discussion?", "Why is an albumin threshold alone insufficient?"],
          ["Estimate thromboembolism risk against serious-bleeding risk in this individual.",
           "A nephrotic risk marker does not remove the importance of recent bleeding, the clinical course or a distinction between prevention and treatment of a confirmed event."],
          GD, "Practice Point 1.7.1, printed S101; Practice Point 3.4.5, S138: individualized thromboprophylaxis balance"),
    stage("At follow-up, the patient asks whether improved antibodies mean all kidney and general follow-up can stop.",
          ["Which outcomes still need observation?", "How can uncertainty be explained without inventing a predicted recovery date?"],
          ["Clinical protein loss, filtration, nutrition and complications can evolve after a serologic change.",
           "Explain the observed trends and the next review criteria. Distinguish what has improved from outcomes that remain unresolved."],
          GD, "Chapter 3.3: longitudinal membranous response and complication assessment"),
], ["Clinical and immunologic response can follow different time courses.",
    "Disease-related clotting risk and treatment-related bleeding risk need a shared individualized decision."])

case("RN11-CASE-DONOR-GOALS", "T21", ("T02", "T24", "T09", "T26", "T01"),
     ("T21.O01", "T21.O02", "T02.O01", "T24.O01", "T26.O01"),
     "Measurements, future pregnancy and a voluntary donor decision",
     "Use donor-specific kidney measurements and counseling while protecting a capable person's freedom to choose.", [
    stage("A synthetic potential donor has favorable confirmed GFR, but a high initial ACR was collected after exercise. Subsequent confirmed albumin excretion is 42 mg/day.",
          ["Why confirm the initial measurement?", "Which donor albuminuria category applies to the confirmed result?"],
          ["Sample conditions and the creatinine denominator can affect a ratio; donor assessment uses appropriate confirmation.",
           "AER 30-100 mg/day is an individualized donor-risk decision. Favorable GFR does not make the albumin finding irrelevant."],
          DONOR, "Recommendations 6.1-6.6, printed S42: donor albumin assessment"),
    stage("The candidate hopes for a future pregnancy and has questions about whether donation is automatically prohibited.",
          ["What distinguishes eligibility from risk counseling?", "Which pregnancy risks need an informed discussion?"],
          ["Future conception alone does not exclude donation; the complete profile and timing are assessed.",
           "Discuss the greater likelihood of gestational hypertension or preeclampsia and review relevant prior pregnancy/vascular history without guaranteeing an outcome."],
          DONOR, "Recommendations 15.4-15.11, printed S78: future pregnancy and counseling"),
    stage("In a private conversation, the candidate describes family pressure and says they are not sure they want to proceed.",
          ["What must remain voluntary after medical evaluation?", "How should a withdrawal request be handled?"],
          ["A medical-risk assessment does not replace informed voluntary consent.",
           "Protect confidential withdrawal and support communication with the family; the recipient's need does not override the donor's choice."],
          DONOR, "Recommendations 2.1-2.8, printed S27: consent and withdrawal"),
], ["Donor thresholds concern defined measures within a broader individualized assessment.",
    "Medical suitability, counseling and voluntary choice are separate essential parts of the decision."])

case("RN11-CASE-HOME-BP", "T09", ("T08", "T02", "T01", "T26", "T27"),
     ("T09.O01", "T08.O01", "T08.O02", "T02.O01", "T26.O02"),
     "When measurement settings change the kidney-risk picture",
     "Confirm BP and urine trends before using categories and predictions to build a follow-up plan.", [
    stage("A synthetic adult with established CKD has standardized clinic BP 118/72 mmHg, while a week of home readings averages 148/85. The home device and technique have not yet been checked.",
          ["What must be verified before interpreting the discrepancy?", "Which out-of-office pattern could matter if it is confirmed?"],
          ["Review device validation, cuff fit, timing and technique, with appropriate repeat/home or ambulatory assessment.",
           "Higher reproducible out-of-office readings can reveal masked hypertension; a reassuring clinic visit does not settle the whole pattern."],
          BP, "Recommendations 1.1-1.2 and rationale: standardized and complementary out-of-office BP"),
    stage("The initial ACR was 430 mg/g during a symptomatic urinary infection. A suitable repeat is 180 mg/g. eGFR has remained near 58 for more than a year.",
          ["Which part of the CKD picture is already chronic?", "How should the changing albumin result be documented?"],
          ["Persistent filtration below 60 establishes chronic dysfunction independently of the high initial ACR.",
           "Record measurement conditions and quantitative trends. Infection can affect albumin measurements, and one category should not be treated as the permanent maximum."],
          CKD, "Tables 1-3 and Table 16, printed S154: CKD classification and urine variability"),
    stage("After measurements are reconciled, the clinic proposes a kidney-failure risk estimate and coordinated vascular-risk review.",
          ["What should be explained about a prediction tool?", "What makes the follow-up plan more useful than a single score?"],
          ["State the predicted outcome, time horizon and validated population; a numerical probability does not establish a causal diagnosis or treatment preference.",
           "Link the observed BP, albumin and filtration pattern to agreed monitoring and modifiable risks, with clear responsibility for reassessment."],
          CKD, "Recommendation 2.2.1 and Practice Points 2.2.4-2.2.5: risk-model application"),
], ["Measurement validity comes before category and prediction interpretation.",
    "BP, albumin and filtration supply related but different information for coordinated kidney and vascular care."])

case("RN11-CASE-CRRT-DELIVERY", "T07", ("T23", "T06", "T05", "T25", "T26"),
     ("T07.O01", "T07.O02", "T23.O01", "T25.O02", "T26.O01"),
     "The prescribed circuit and the support actually delivered",
     "Connect dose arithmetic, circuit function, recovery and nutrition during acute kidney support.", [
    stage("A synthetic critically ill adult receives CRRT prescribed at 25 mL/kg/h, but circuit downtime totals eight hours in the first 24-hour period.",
          ["What average rate would that schedule deliver if flow is otherwise as prescribed?", "Which operational problems should be investigated?"],
          ["The time-averaged delivery is 25 x 16/24, about 16.7 mL/kg/h. A written prescription is not proof of the intended delivered dose.",
           "Review access, interruptions, circuit clotting and actual flows, alongside metabolic/fluid needs and the method of dose measurement."],
          AKI, "Recommendation 5.8.4 and rationale: delivered CRRT dose and interruptions"),
    stage("The team reviews a regional-citrate protocol as part of a circuit strategy and asks why calcium measurements are included.",
          ["How does citrate affect circuit coagulation?", "Why must circuit and systemic calcium be distinguished?"],
          ["Citrate lowers available ionized calcium in the circuit, impairing calcium-dependent coagulation.",
           "The patient's systemic calcium and metabolic handling still require protocol-guided support/monitoring. A circuit mechanism does not establish a safe patient-specific prescription by itself."],
          AKI, "Section 5.3.2: citrate anticoagulation mechanism and monitoring"),
    stage("Later the acute illness improves. Laboratory values look acceptable on support, and the family asks whether sharply restricting protein would avoid any further KRT.",
          ["How should readiness to stop support be assessed?", "What is the nutritional reasoning error?"],
          ["Assess whether intrinsic function can meet current solute, electrolyte and fluid needs; corrected results during support do not independently prove recovery.",
           "Do not make nutritional deprivation a substitute for needed support. Recovery, intake and the acute nutritional state deserve their own assessment."],
          AKI, "Recommendations 5.2.1 and 3.3.3: stopping KRT and avoiding protein restriction to delay it"),
], ["Delivered time and circuit behavior matter as much as the nominal dose.",
    "Recovery assessment and nutritional support should not be reduced to an on-treatment laboratory value."])

case("RN11-CASE-LUPUS-REASSESSMENT", "T16", ("T10", "T15", "T22", "T17", "T26"),
     ("T16.O01", "T16.O02", "T15.O01", "T22.O02", "T17.O02"),
     "An incomplete response is a question to investigate",
     "Distinguish residual immune activity, chronic injury and a new vascular pattern before equating proteinuria with a treatment choice.", [
    stage("A synthetic adult treated for lupus nephritis has persistent proteinuria. The team is unsure whether treatment exposure was adequate and whether chronic damage explains part of the result.",
          ["Which information should be reviewed before declaring refractory inflammation?", "When might tissue reassessment have value?"],
          ["Review adherence, treatment exposure and the serial clinical/urine/kidney-function pattern.",
           "Consider repeat biopsy when distinguishing active inflammation, chronicity or another lesion would change management; it is not mandatory for every abnormal follow-up sample."],
          LN, "Practice Point 10.2.5.2.1, Figure 12 and Section 10.2.5.3, printed S46-S47"),
    stage("Reassessment tissue includes a TMA pattern. New thrombocytopenia and hemolysis prompt a coordinated hematology/kidney review.",
          ["What does the pattern establish?", "Which mechanism still needs investigation?"],
          ["It identifies microvascular injury, not a single causal pathway.",
           "Assess TTP/ADAMTS13, antiphospholipid and complement-related or other secondary mechanisms in the clinical context. The tissue label alone does not choose a universal treatment."],
          LN, "Practice Point 10.3.1.1 and rationale, printed S47-S48: lupus with TMA"),
    stage("While an individualized treatment plan is considered, the team reconciles infection testing, vaccination and past exposures with the patient.",
          ["Why is historical vaccination alone not the whole safety assessment?", "How can disease urgency and infection risk be coordinated?"],
          ["Prior/current infections and reactivation risk require appropriate testing and exposure review; vaccine history answers a different question.",
           "Coordinate kidney, hematology and infection expertise around the actual findings and urgency rather than treating a positive historical label as automatic lifelong exclusion from care."],
          GD, "Practice Points 1.8.1-1.8.2: infection screening around immunosuppression"),
], ["Persistent proteinuria is not a direct readout of current histologic activity.",
    "A new TMA pattern needs etiologic assessment alongside the person's immune and infection context."])


def selected_items(per_topic, extra_cases):
    questions = ORIGINAL_QUESTIONS + [q for q in NEW_QUESTIONS
                                      if int(q["id"].rsplit("-", 1)[1]) <= per_topic]
    cases = ORIGINAL_CASES + NEW_CASES[:extra_cases]
    return questions, cases


def selected_sources(questions, cases):
    cited = {c["source_id"] for item in questions + cases for c in item["sources"]}
    for item in cases:
        cited.update(c["source_id"] for s in item["stages"] for c in s["sources"])
    return [s for s in SOURCES if s["id"] in cited]


def publish(path: Path, *, version="1.0.1", per_topic=2, extra_cases=6):
    questions, cases = selected_items(per_topic, extra_cases)
    if len(questions) < (100 if per_topic == 2 else 150) or len(NEW_CASES[:extra_cases]) != extra_cases:
        raise ValueError("The chosen increment has not completed its authored breadth target")
    result = base.publish_snapshot(
        path, version=version, topics=TOPICS, sources=selected_sources(questions, cases), cases=cases, questions=questions,
        target_topics=[t["id"] for t in TOPICS], minimum_questions=100 if per_topic == 2 else 150)
    return result


def review_evidence(*, version, per_topic, extra_cases):
    questions, cases = selected_items(per_topic, extra_cases)
    chosen = {q["id"] for q in NEW_QUESTIONS
              if int(q["id"].rsplit("-", 1)[1]) <= per_topic}
    chosen.update(c["id"] for c in NEW_CASES[:extra_cases])
    evidence = {
        "schema_version": 1, "pack_id": "renulus-foundations", "pack_version": version,
        "checked_on": DATE, "method": "Assistant primary public locator check, original scenario/key/distractor and numeric review.",
        "independent_human_review": False,
        "inherited_review": "Unchanged 1.0.0 items retain their recorded review and exact source snapshots.",
        "access_limits": "Some primary PMC/publisher pages blocked browser parsing; publicly indexed primary material and official/author-repository copies were used where recorded. No source originals or prose are stored here.",
        "sources": [{"id": s["id"], "register_id": s["register_id"],
                     "url": s["url"], "edition": s["edition"],
                     "check_note": s["check_note"]}
                    for s in selected_sources(questions, cases) if s["id"] not in {x["id"] for x in base.SOURCES}],
        "items": [e for e in EVIDENCE if e["id"] in chosen],
    }
    if version == "1.1.0":
        evidence["inherited_review"] = "Unchanged 1.0.0 and 1.0.1 items retain their recorded review and exact item/source snapshots. The 1.0.1 review evidence file is unchanged."
        evidence["primary_review_notes"] = ["source-check-wave2.md", "source-check-wave2-final.md"]
        reviewed = {e["id"]: e for e in evidence["items"] if e["kind"] == "question"}
        evidence["question_skill_coverage"] = {
            "scope": "question_review_rows",
            "counts": dict(sorted(Counter(e["skill"] for e in reviewed.values()).items())),
            "by_topic": {t["id"]: dict(sorted(Counter(reviewed[q["id"]]["skill"]
                          for q in questions if q["id"] in reviewed and q["topic_id"] == t["id"]).items()))
                         for t in TOPICS},
        }
    return evidence


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", choices=("1.0.1", "1.1.0"), default="1.0.1")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    final = args.version == "1.1.0"
    output = args.output or ROOT / "content/packs/renulus-foundations" / args.version
    result = publish(output, version=args.version, per_topic=4 if final else 2, extra_cases=12 if final else 6)
    evidence_path = ROOT / "content/reviews" / f"renulus-foundations-{args.version}.json"
    evidence = review_evidence(version=args.version, per_topic=4 if final else 2, extra_cases=12 if final else 6)
    raw = (json.dumps(evidence, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    if evidence_path.exists() and evidence_path.read_bytes() != raw:
        raise SystemExit(f"Refusing to alter published review evidence: {evidence_path}")
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    if not evidence_path.exists():
        evidence_path.write_bytes(raw)
    print(json.dumps(result, indent=2))
