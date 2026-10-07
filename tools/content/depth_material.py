# SPDX-License-Identifier: MIT
"""Original 1.2.0 authoring data. Teaching text is CC BY 4.0; sources retain rights.

No network, engine, profile or publication side effects occur on import.
"""
from copy import deepcopy

DATE = "2026-10-07"
REVIEW = dict(status="assistant_reviewed", reviewer="Renulus content lane assistant",
    reviewer_kind="assistant", reviewed_on=DATE, source_key_checked=True,
    independent_human_review=False,
    method="Primary locator, objective meaning, single-key and all four distractors checked; original synthetic educational content. No independent human review.")
QUESTIONS, CASES, EVIDENCE = [], [], []

IGA = "K04-2025-depth"
DI = "L01-SfE-CDI-2018-depth"
CKD = "K01-2024-depth"
ANEMIA = "K02-2026-depth"
ASB = "L01-IDSA-ASB-2019-depth"
GS = "L01-KDIGO-Gitelman-2017-depth"
PD = "L01-ISPD-peritonitis-2022-depth"
HD = "G02-HD-2019-depth"
BK = "L01-BK-2024-depth"
PREG = "G02-pregnancy-2019-depth"
CITRATE = "K10-2012-citrate-depth"
CANDIDATE = "K16-2020-candidate-depth"


def cite(sid, locator):
    return {"source_id": sid, "locator": locator}


def q(suffix, topic, objectives, sid, locator, stem, key, wrong, explanation,
      *, secondary=(), skill="interpretation"):
    """Five genuine alternatives, each with an authored explanation."""
    assert len(wrong) == 4
    key_index = len(QUESTIONS) % 5
    choices = list(wrong)
    choices.insert(key_index, (key, explanation))
    identity = "RN13-" + suffix
    item = dict(id=identity, version=1, family_id=identity + ".family",
        family_version=1, key_version=1, topic_id=topic,
        secondary_topic_ids=list(secondary), objective_ids=list(objectives),
        license="CC-BY-4.0", original=True, kind="single_best_answer",
        usage="assessment_reserved", stem=stem,
        options=[dict(id=chr(65+i), text=t, rationale=r) for i,(t,r) in enumerate(choices)],
        answer=chr(65+key_index), rationale=explanation, difficulty="integration",
        sources=[cite(sid, locator)], review=deepcopy(REVIEW))
    QUESTIONS.append(item)
    EVIDENCE.append(dict(id=identity, version=1, kind="question", reviewed_on=DATE,
        reviewer_kind="assistant", independent_human_review=False,
        source_locators=deepcopy(item["sources"]), key_text=key, skill=skill,
        checked_claim=explanation,
        objective_support=[dict(objective_id=o, checked_claim=explanation,
                                source_locators=deepcopy(item["sources"])) for o in objectives],
        distractor_check="Each of the four alternative explanations is reviewed under the specific stem conditions; no all/none-of-the-above filler."))


def stage(narrative, prompts, points, sid, locator):
    return dict(narrative=narrative, prompts=prompts, teaching_points=points,
                sources=[cite(sid, locator)])


def case(suffix, topic, secondary, title, summary, stages, take_home, support):
    identity = "RN13-CASE-" + suffix
    numbered = [dict(id=f"stage-{n}", **s) for n,s in enumerate(stages,1)]
    refs = []
    for s in numbered:
        for ref in s["sources"]:
            if ref not in refs:
                refs.append(ref)
    item = dict(id=identity, version=1, topic_id=topic, secondary_topic_ids=list(secondary),
        objective_ids=[o for o,_,_ in support], license="CC-BY-4.0", original=True,
        synthetic=True, usage="teaching", title=title, summary=summary, stages=numbered,
        take_home=take_home, sources=refs, review=deepcopy(REVIEW))
    CASES.append(item)
    rows=[]
    for o,ns,claim in support:
        citations=[]
        for n in ns:
            for ref in numbered[n-1]["sources"]:
                if ref not in citations:
                    citations.append(ref)
        rows.append(dict(objective_id=o, stage_ids=[f"stage-{n}" for n in ns],
                         checked_claim=claim, source_locators=citations))
    EVIDENCE.append(dict(id=identity, version=1, kind="case", reviewed_on=DATE,
        reviewer_kind="assistant", independent_human_review=False, source_locators=refs,
        key_text=None, skill="mixed_domain_reasoning", objective_support=rows,
        checked_claim=" ".join(r["checked_claim"] for r in rows),
        review_limit="Open teaching discussion with explicit stage evidence; not a deterministic scored case or clinical outcome."))


q("IGA-001", "T10", ["T10.O01"], IGA, "Practice point 1.2.1, printed S15",
  "A 34-year-old has persistent microscopic hematuria and protein excretion of 0.8 g/day on repeat testing. IgA nephropathy is suspected; kidney biopsy has no identified contraindication. Which investigation can establish that diagnosis?",
  "Kidney biopsy interpreted with the clinical findings.",
  [("A raised serum IgA concentration alone.", "Serum IgA does not provide a validated diagnostic substitute for tissue."),
   ("A negative ANCA result alone.", "Excluding one competing serologic finding does not establish IgA deposition."),
   ("A fall in proteinuria after starting an ARB.", "Response to supportive therapy is not disease-specific proof."),
   ("Normal kidney size on ultrasound.", "Structural imaging does not identify the glomerular immune deposit.")],
  "Persistent urinary abnormalities make the suspicion actionable. IgAN requires tissue diagnosis, and the 2025 guideline supports considering biopsy at proteinuria of at least 0.5 g/day when IgAN is possible. Discuss procedural risk and how the result will change care; neither a serum marker nor a therapeutic response supplies the same information.", secondary=("T02","T22"))
q("IGA-002", "T10", ["T10.O02"], IGA, "Practice points 1.4.1.1 and 1.4.2.1, printed S17",
  "An adult with biopsy-confirmed IgAN has persistent proteinuria of 0.7 g/day and stable eGFR at two visits. What is the most defensible interpretation for follow-up?",
  "Progression risk remains clinically relevant and warrants a treatment and monitoring review.",
  [("Proteinuria below 1 g/day excludes meaningful progression risk.", "The reviewed risk threshold is lower than 1 g/day."),
   ("Two stable eGFR results establish lifetime protection.", "A short stable interval does not establish the long-term trajectory."),
   ("Kidney replacement therapy is indicated immediately by this proteinuria.", "Proteinuria informs risk and treatment, not an isolated dialysis trigger."),
   ("Proteinuria should be ignored once the biopsy establishes the diagnosis.", "Serial proteinuria remains a treatment-response and risk measurement.")],
  "Proteinuria at or above 0.5 g/day identifies increased risk in IgAN even with a reassuring short-term filtration trend. Revisit kidney protection, disease-specific options and serial measurements with the patient. This identifies a need for review, not an automatic drug choice or certainty of kidney failure.", secondary=("T08",), skill="common_reasoning")
q("IGA-003", "T10", ["T10.O02"], IGA, "Practice point 1.4.2.3, printed S19",
  "An IgAN prediction tool reports a high progression risk. A clinician proposes selecting an immunosuppressive drug solely from that number. What is the principal limitation?",
  "The tool estimates prognosis but has not been validated to select the response to a particular treatment.",
  [("The score directly measures drug susceptibility of mesangial cells.", "The model combines prognostic variables, not a pharmacologic response assay."),
   ("A high risk score makes treatment adverse effects irrelevant.", "Absolute risk does not remove treatment harms or patient preferences."),
   ("The score replaces repeated proteinuria and eGFR measurements.", "Risk and treatment decisions require reassessment over time."),
   ("The score establishes that the original biopsy was unnecessary.", "Prediction after tissue diagnosis is different from diagnosing IgAN.")],
  "Prediction and treatment effect are different questions. Use the model to discuss prognosis, then consider the clinical trajectory, treatment evidence, eligibility and harms. The guideline also cautions against using biopsy scores or crescents in isolation to dictate a regimen.", secondary=("T26",), skill="common_reasoning")
q("IGA-004", "T16", ["T10.O02"], IGA, "Recommendation 1.9.1.1, printed S29",
  "An adult has IgA vasculitis limited to the skin, with normal kidney function, no hematuria and no proteinuria. Systemic glucocorticoids are proposed solely to prevent future nephritis. Which response fits the reviewed evidence?",
  "Do not prescribe systemic glucocorticoids solely for nephritis prevention; arrange kidney surveillance.",
  [("Preventive systemic glucocorticoids are indicated in every case.", "A preventive renal benefit has not been established to justify routine exposure."),
   ("Normal urine today makes later kidney surveillance unnecessary.", "Present absence of nephritis does not exclude later kidney involvement."),
   ("The skin findings alone establish rapidly progressive glomerulonephritis.", "Kidney involvement and its trajectory have not been demonstrated."),
   ("Preventive cyclophosphamide is preferable to glucocorticoids.", "There is no demonstrated organ-threatening kidney indication in this presentation.")],
  "The kidney-prevention question must be separated from treating severe extrarenal disease. Systemic glucocorticoids are not recommended solely to prevent nephritis in isolated extrarenal IgAV. Continue clinical and urine assessment so new kidney findings lead to a fresh evaluation.", secondary=("T10","T17"))

q("DI-001", "T03", ["T03.O02"], DI, "Risk stratification; organisational guidance; established adult CDI scope",
  "A patient with established central diabetes insipidus is admitted with pneumonia and is temporarily unable to drink. A regular desmopressin dose is omitted. Why can sodium rise rapidly?",
  "Uncontrolled renal water loss is no longer offset by drinking, and omission of desmopressin compounds it.",
  [("Inability to drink automatically stops renal water excretion.", "Water access does not replace the missing antidiuretic signal."),
   ("Desmopressin omission causes sustained water retention.", "Omission permits dilute water loss in established AVP deficiency."),
   ("Every high sodium result in CDI proves sodium poisoning.", "Net water loss can raise sodium without an exogenous sodium load."),
   ("A normal sodium concentration on admission protects against later deterioration.", "A new loss of water access or treatment can rapidly change balance.")],
  "Thirst and access to water often compensate for AVP deficiency outside hospital. Illness, confusion or fasting can remove that protection. Admission planning must specify fluids, access to desmopressin, a usable administration route and monitoring; do not assume that an omitted oral medicine is harmless.", secondary=("T19","T27"), skill="mechanism")
q("DI-002", "T03", ["T03.O02"], DI, "Decompensated CDI: assessment and fluid resuscitation",
  "An adult with established CDI has sodium 158 mmol/L, tachycardia and hypotension with clinical intravascular depletion. Which fluid priority is appropriate?",
  "Restore intravascular volume with 0.9% sodium chloride before proceeding with controlled free-water replacement.",
  [("Withhold all fluid until sodium falls spontaneously.", "The circulation and ongoing water deficit require active monitored care."),
   ("Give desmopressin alone and postpone assessment of shock.", "Stopping water loss does not by itself restore intravascular volume."),
   ("Give a large fixed free-water load without haemodynamic monitoring.", "Initial circulatory resuscitation and subsequent sodium correction are distinct tasks."),
   ("Treat the high sodium with immediate fluid restriction.", "Fluid restriction aggravates the water deficit in this situation.")],
  "The initial priority is restoring perfusion in a volume-depleted patient. Subsequent fluid composition and rate must address maintenance, the water deficit and ongoing losses, with specialist input and serial sodium measurements. The high sodium does not justify leaving a depleted circulation untreated.", secondary=("T07",))
q("DI-003", "T03", ["T03.O02"], DI, "Decompensated CDI: monitoring sodium and urine output",
  "During active fluid resuscitation of decompensated established CDI, which monitoring plan best detects a changing correction trajectory?",
  "Measure sodium every four hours initially and track fluid input and urine output.",
  [("Check sodium only once after three days.", "Treatment can change water balance substantially within hours."),
   ("Use urine colour as the only measure of water balance.", "Colour cannot quantify sodium correction or circulatory status."),
   ("Stop recording urine output after the first desmopressin dose.", "The change in urine flow is central to subsequent fluid and dose decisions."),
   ("Use body weight alone to prove sodium correction is safe.", "Weight does not measure the rate of sodium change.")],
  "The Society for Endocrinology guidance specifies four-hourly sodium during resuscitation, then at least twelve-hourly until stable. Pair laboratory results with measured losses and clinical volume assessment. Monitoring intensity follows acuity; this is not the interval for every stable outpatient with CDI.", secondary=("T07",))
q("DI-004", "T03", ["T03.O02"], DI, "Decompensated CDI: optimising fluid replacement and DDAVP",
  "A resuscitated patient with established CDI receives desmopressin. Urine output falls sharply while a previously high water-replacement rate continues. What change in risk needs immediate reassessment?",
  "Rapid sodium reduction as administered water is retained after antidiuresis begins.",
  [("Desmopressin makes the fluid infusion incapable of changing sodium.", "The combination determines net water retention."),
   ("The prior urine-loss rate remains reliable for the next twenty-four hours.", "Desmopressin has changed the loss term in the balance."),
   ("Falling urine output proves new obstructive kidney failure.", "A treatment-induced antidiuretic response is an immediate alternative explanation."),
   ("Every fall in sodium requires stopping all future desmopressin permanently.", "Reassessment concerns the coordinated fluid and medication plan, not abandonment of required replacement.")],
  "Water replacement and desmopressin must be coordinated. Once dilute losses stop, continuing to replace the old loss rate can overshoot. Reassess sodium trajectory, current urine output and fluids with the treating team rather than using a static deficit calculation for the entire admission.", secondary=("T19",), skill="common_reasoning")

q("CKD-001", "T08", ["T08.O02"], CKD, "Recommendation 2.2.1; practice point 2.2.1, printed S155",
  "An adult with stable CKD G3b has a five-year kidney-failure risk of 6% from an externally validated equation. How should this inform care?",
  "Use the risk to support nephrology referral alongside eGFR, albuminuria and clinical findings.",
  [("Schedule dialysis immediately from the risk estimate alone.", "A future risk estimate is not a present clinical indication for dialysis."),
   ("Ignore the estimate until eGFR is below 15.", "Risk adds information before kidney failure develops."),
   ("Interpret 6% as a guaranteed date of kidney failure.", "The model estimates probability over a defined interval."),
   ("Apply the same equation without validation to all CKD G1 patients.", "Equations developed in G3-G5 may not be valid in G1-G2.")],
  "The 2024 guideline allows a five-year risk of 3-5% to inform referral. A 6% estimate exceeds that range but still needs clinical context and the correct model population. Discuss both uncertainty and the purpose of specialist review; the score does not select a modality.", secondary=("T02",))
q("CKD-002", "T08", ["T08.O02"], CKD, "Practice point 2.2.3; practice point 5.4.1",
  "A patient with CKD G4 has a validated two-year kidney-failure risk of 46%, without refractory symptoms or biochemical indications for dialysis. What does that risk chiefly support now?",
  "Modality education and preparation, including access or transplant planning as appropriate.",
  [("Immediate dialysis regardless of symptoms or preferences.", "Preparation thresholds do not replace clinical initiation criteria."),
   ("Deferring every discussion until an emergency admission.", "High near-term risk provides time-sensitive planning information."),
   ("A compulsory haemodialysis catheter for every patient.", "The appropriate modality and access require individualized decisions."),
   ("Excluding conservative kidney care from discussion.", "Goals and informed treatment choices remain relevant.")],
  "A two-year risk above 40% can inform the timing of kidney-replacement preparation. Education should cover realistic options and patient goals while transplantation and access work proceed when appropriate. Starting dialysis remains a separate composite clinical decision.", secondary=("T20","T21","T26"), skill="common_reasoning")
q("CKD-003", "T08", ["T08.O02"], CKD, "Practice points 2.1.3-2.1.4, printed S154",
  "An adult with CKD has eGFR fall from 48 to 35 mL/min/1.73 m2 on follow-up, without a newly started haemodynamically active drug. Which interpretation best guides the next step?",
  "The change exceeds expected variability and warrants evaluation of causes and confirmation of the trajectory.",
  [("Any change smaller than 50% is normal laboratory noise.", "This decline exceeds the guideline's general evaluation threshold."),
   ("The two measurements identify the exact histologic cause.", "A trend quantifies change but does not establish a lesion."),
   ("CKD progression is proven irreversible, so reversible causes need no review.", "Intercurrent illness, obstruction and medicines can contribute."),
   ("The patient must have started an SGLT2 inhibitor despite the stated history.", "Do not replace the actual medication history with an assumed explanation.")],
  "The decline is about 27%, exceeding the general greater-than-20% threshold for evaluation. Check chronology, clinical state, medicines and repeat measurements. A separate greater-than-30% consideration applies after haemodynamically active therapy; neither rule substitutes for clinical assessment.", secondary=("T02","T06"))
q("CKD-004", "T08", ["T08.O02"], CKD, "Practice point 2.1.5, printed S154",
  "A person with CKD has urine ACR increase from 18 to 40 mg/mmol on a subsequent test. What is the best response?",
  "Evaluate the more-than-doubling result in context and confirm the trend, including transient influences.",
  [("The increase is irrelevant because eGFR has not changed.", "Albuminuria and filtration supply complementary information."),
   ("One changed ACR establishes a particular glomerular diagnosis.", "Quantification alone does not establish disease identity."),
   ("Convert both results to mg/g before deciding whether the ratio doubled.", "Both results already use the same unit; their ratio is directly interpretable."),
   ("Immediately withdraw every kidney-protective medicine.", "Investigate the change before deciding which treatment, if any, needs adjustment.")],
  "The ACR has risen by more than twofold, exceeding expected laboratory variability and warranting evaluation. Review collection conditions and intercurrent illness, verify persistence, and reconsider risk and treatment. A single result is a signal to investigate rather than proof of permanent treatment failure.", secondary=("T02",))

q("ANEMIA-001", "T08", ["T08.O03"], ANEMIA, "Practice points 1.2.1-1.2.3; Figure 6",
  "A person with CKD G4 has falling haemoglobin, microcytosis, ferritin 14 micrograms/L and TSAT 9%. Which evaluation should accompany an iron-replacement discussion?",
  "Look for blood loss and other causes of iron deficiency rather than attributing the entire anemia to CKD.",
  [("No further assessment is needed because CKD always explains microcytosis.", "CKD does not exclude coexisting blood loss or nutritional deficiency."),
   ("A low ferritin proves immune haemolysis.", "Low iron stores do not establish haemolysis; its evaluation needs other evidence."),
   ("Normalizing haemoglobin with an ESA will identify the bleeding site.", "An erythropoietic response cannot localize a source of iron loss."),
   ("Defer investigation until dialysis starts.", "The anemia and depleted stores require assessment now.")],
  "Low ferritin and TSAT support iron deficiency. Review menstrual, gastrointestinal or urinary loss as appropriate, nutrition and the blood count/reticulocyte pattern. Iron treatment and cause investigation serve different purposes: replenishing stores does not explain why they became depleted.", secondary=("T02","T19"))
q("ANEMIA-002", "T19", ["T19.O01"], ANEMIA, "Practice point 2.8, printed S21",
  "A haemodialysis patient due for scheduled intravenous iron is admitted with systemic bacterial infection. Which action best reflects the 2026 anemia guidance?",
  "Consider temporarily suspending iron during the systemic infection and reassess when the acute illness resolves.",
  [("Give extra intravenous iron as treatment for the infection.", "Iron replacement does not treat the infectious cause."),
   ("Permanently prohibit iron after any infection.", "The guidance concerns a temporary interruption with reassessment."),
   ("Ignore the infection because haemodialysis eliminates treatment harms.", "Dialysis does not remove the need to review iron safety."),
   ("Replace iron immediately with a transfusion solely because a scheduled dose is missed.", "Transfusion requires its own clinical indication and benefit-harm assessment.")],
  "Systemic infection changes the timing discussion even if iron was previously indicated. Document the reason for holding treatment and a reassessment plan. This practice point does not make iron permanently contraindicated or establish an automatic transfusion indication.", secondary=("T08","T17"), skill="common_reasoning")
q("ANEMIA-003", "T08", ["T08.O03","T08.O04"], ANEMIA, "Practice point 3.7.1; Table 9, printed S59",
  "Haemoglobin remains low despite increasing ESA requirements in a dialysis patient. Iron availability, inflammation, occult bleeding and delivered dialysis have not been reassessed. What is the next reasoning priority?",
  "Identify and address reversible causes of ESA hyporesponsiveness before further treatment escalation.",
  [("Assume the ESA has no biological activity in every patient.", "An individual poor response does not establish universal ineffectiveness."),
   ("Escalate indefinitely without revisiting causes.", "Escalation can expose the patient to harms while a reversible driver remains untreated."),
   ("Use a normal haemoglobin target to overcome resistance.", "A higher target does not correct iron restriction or inflammation and adds risk."),
   ("Treat ferritin alone as proof that iron availability is adequate.", "Inflammation can complicate ferritin interpretation; the broader iron and clinical picture matters.")],
  "Hyporesponsiveness is a clinical signal. Iron deficiency or restriction, inflammation, blood loss and inadequate dialysis are among the causes to assess. The next intervention depends on what is found and on symptoms and treatment risks, rather than reflexive escalation to normalize haemoglobin.", secondary=("T19","T20"), skill="common_reasoning")
q("ANEMIA-004", "T19", ["T19.O01"], ANEMIA, "Practice points 4.1-4.5, printed S28",
  "A transplant-eligible adult with stable chronic CKD anemia asks whether every Hb below 90 g/L mandates transfusion. There is no acute haemorrhage or unstable coronary syndrome. What is the best answer?",
  "Base the decision on anemia-related symptoms, signs, alternatives and harms, including allosensitization.",
  [("Every Hb below 90 g/L requires transfusion irrespective of context.", "An arbitrary number alone does not settle chronic transfusion decisions."),
   ("Transfusion must never be used in a transplant candidate, even in life-threatening bleeding.", "Urgent stabilization can outweigh sensitization concerns; the stem is a stable chronic setting."),
   ("Leukocyte reduction guarantees that sensitization cannot occur.", "It does not justify treating the sensitization risk as absent."),
   ("The only relevant outcome is the post-transfusion laboratory number.", "Symptoms, clinical stability, future transplantation and other harms also matter.")],
  "A stable chronic decision should weigh benefit, symptoms and available treatments against transfusion harms. Avoid transfusion when feasible in transplant-eligible people to limit allosensitization. This is not a prohibition when rapid correction is required for an acute clinical emergency.", secondary=("T08","T21"))

q("CARDIO-001", "T14", ["T14.O02"], CKD, "Practice points 3.7.2-3.7.3, printed S158",
  "A person taking an SGLT2 inhibitor is admitted for major surgery with prolonged fasting. Which temporary treatment discussion is appropriate?",
  "Withhold the SGLT2 inhibitor during the fasting/perioperative risk period and document reassessment before restart.",
  [("Continue it because fasting abolishes ketosis risk.", "Fasting and surgery increase the concern for ketosis."),
   ("Double it to replace missed meals.", "It is not nutritional replacement and the situation increases treatment risk."),
   ("Permanently stop all kidney-protective treatment after any procedure.", "An acute interruption requires a recovery and restart plan."),
   ("Use urine glucose alone to establish safe continuation.", "Glycosuria does not establish hydration, nutrition or absence of ketoacidosis.")],
  "SGLT2 inhibition can increase vulnerability to ketosis during prolonged fasting, surgery or critical illness. Coordinate the interruption with the surgical/diabetes team and review recovery, intake and clinical status before restart. A sick-day plan needs a named review point so beneficial therapy is not forgotten.", secondary=("T19",), skill="common_reasoning")
q("CARDIO-002", "T14", ["T14.O02"], CKD, "Practice point 3.7.3 and practice point 2.1.4",
  "After starting an SGLT2 inhibitor, eGFR falls from 50 to 46 mL/min/1.73 m2. The patient feels well, has stable blood pressure and no volume depletion. Which interpretation is most appropriate?",
  "A small early reversible eGFR dip can occur and is not by itself a reason to stop treatment.",
  [("Any fall proves permanent toxic tubular necrosis.", "A haemodynamic dip is distinct from proven structural toxicity."),
   ("The result removes the need to consider later symptoms or larger changes.", "Clinical deterioration or substantial change still warrants assessment."),
   ("Increase diuretics solely to force eGFR back to baseline.", "This does not follow from the finding and may worsen depletion."),
   ("Diagnose kidney failure from this pair of results.", "Neither the values nor the stable presentation support that conclusion.")],
  "Interpret the magnitude, timing and clinical setting together. This approximately 8% change is compatible with an expected early effect, while symptoms, depletion or a substantially larger fall would require investigation. One laboratory shift should not erase an otherwise appropriate kidney-protection plan.", secondary=("T08","T19"))
q("CARDIO-003", "T14", ["T14.O01"], CKD, "Recommendation 3.8.1; practice point 3.8.3, printed S158-S159",
  "A person with type 2 diabetes, albuminuric CKD and eGFR 38 is taking a maximum tolerated ARB. Potassium is repeatedly 5.6 mmol/L. What must be addressed before adding a nonsteroidal mineralocorticoid receptor antagonist?",
  "The persistent hyperkalemia and suitability for safe potassium monitoring.",
  [("Albuminuria makes baseline potassium irrelevant.", "Normal potassium is part of the recommended treatment-selection conditions."),
   ("An eGFR above 25 eliminates hyperkalemia risk.", "Kidney function eligibility does not remove the potassium risk."),
   ("Stop measuring potassium once treatment starts.", "Regular monitoring is needed after initiation."),
   ("Add an ACE inhibitor to the ARB to correct the potassium.", "Dual RAS blockade is not a treatment for hyperkalemia and adds harm.")],
  "The potential benefit of an nsMRA does not override its safety conditions. Persistent hyperkalemia requires evaluation and management; initiation should follow an appropriate potassium assessment and monitoring plan. This item concerns eligibility and safety, not a drug-specific dosing algorithm.", secondary=("T04","T19"))
q("CARDIO-004", "T09", ["T09.O02"], CKD, "Recommendation 3.6.4, printed S157",
  "An adult with albuminuric CKD remains above the agreed blood-pressure goal on an ARB. Which proposed addition should be rejected on kidney-safety grounds?",
  "Adding an ACE inhibitor to create routine dual RAS blockade.",
  [("Checking adherence and tolerability before changing treatment.", "Those checks help explain apparent treatment failure."),
   ("Reviewing standardized and home blood-pressure results.", "Measurement context supports a defensible treatment decision."),
   ("Reassessing salt intake and volume status.", "These can contribute to persistent hypertension."),
   ("Selecting an appropriate non-RAS antihypertensive after clinical review.", "Other classes may be suitable; the contraindicated combination is the issue.")],
  "Combining ACE inhibition with an ARB is not a routine solution to residual albuminuria or hypertension. The CKD guideline advises avoiding combined ACEi, ARB and direct-renin-inhibitor therapy. Review the cause of uncontrolled pressure and choose treatment while accounting for potassium, kidney function and tolerance.", secondary=("T08","T19"), skill="common_reasoning")

q("ASB-001", "T17", ["T17.O02"], ASB, "Section VI: diabetes; definition of asymptomatic bacteriuria",
  "A nonpregnant woman with diabetes has a positive urine culture obtained at a routine visit. She has no urinary symptoms, fever or planned urologic procedure. What is the best antimicrobial decision?",
  "Do not prescribe antibiotics solely for the asymptomatic culture result.",
  [("Diabetes alone makes every positive culture an indication for antibiotics.", "The IDSA guideline recommends against treating ASB solely because of diabetes."),
   ("Treat until every surveillance culture is sterile.", "This exposes the patient to repeated harm without established benefit."),
   ("Use intravenous therapy because symptoms are absent.", "Absence of symptoms does not select a more aggressive treatment route."),
   ("Diagnose pyelonephritis solely from colony count.", "A culture result alone does not establish a symptomatic upper-tract syndrome.")],
  "Distinguish bacteriuria from symptomatic infection. In this nonpregnant, nonprocedural setting, diabetes does not supply a reason to treat ASB. Explain which new symptoms should prompt review and avoid a cycle of unnecessary cultures and antibiotics.", secondary=("T13","T14","T19"))
q("ASB-002", "T17", ["T17.O02"], ASB, "Section III: pregnancy",
  "A pregnant patient has confirmed asymptomatic bacteriuria at antenatal screening. Which principle differs from routine management of ASB in a nonpregnant adult?",
  "Pregnancy is an indication to treat with an appropriate culture-directed regimen.",
  [("No treatment is ever indicated without dysuria during pregnancy.", "Pregnancy is a specified exception to routine non-treatment of ASB."),
   ("Any antibiotic is suitable because there are no symptoms.", "Pregnancy, susceptibility, allergies and kidney function still affect selection."),
   ("A positive culture proves obstruction and mandates a nephrostomy.", "Bacteriuria alone does not establish an obstructed collecting system."),
   ("One result establishes a need for lifelong prophylaxis.", "Treatment of the current bacteriuria is different from an indefinite prevention plan.")],
  "The ASB guidance recommends screening and treatment in pregnancy. Choose an appropriate agent and duration under the pregnancy and local antimicrobial plan rather than copying treatment from an unrelated population. The exception does not turn the culture into evidence of sepsis or obstruction.", secondary=("T13","T24","T19"))
q("ASB-003", "T17", ["T17.O02"], ASB, "Section XIII: endourological procedures with mucosal trauma",
  "A patient without urinary symptoms is scheduled for an endoscopic urinary-tract procedure expected to cause mucosal trauma. Pre-procedure culture grows bacteria. What is the best infection-prevention approach?",
  "Use the culture to guide peri-procedural antimicrobial treatment before the mucosa-traumatizing procedure.",
  [("Ignore bacteriuria because symptoms are absent in every procedural setting.", "Mucosal trauma is a specified exception because of postoperative sepsis risk."),
   ("Use a prolonged empiric course without reviewing susceptibility.", "The guidance favours targeted treatment and a short peri-procedural course."),
   ("Start antibiotics only after postoperative shock develops.", "The preventive opportunity is before the procedure."),
   ("Treat every future positive culture indefinitely after the procedure.", "The indication is bounded to the procedural setting.")],
  "Procedure type changes the risk. Obtain and use culture information for an appropriate short peri-procedural regimen when mucosal trauma is expected. This rule does not apply indiscriminately to every diagnostic test, device or positive urine culture.", secondary=("T13","T22","T19"), skill="common_reasoning")
q("ASB-004", "T17", ["T17.O02"], ASB, "Section XI: indwelling catheters",
  "A clinically well adult with a long-term urinary catheter has bacteriuria and pyuria. There is no new localizing or systemic symptom and no planned invasive urologic procedure. Which interpretation is best?",
  "These findings alone do not justify antimicrobial treatment of catheter-associated asymptomatic bacteriuria.",
  [("Pyuria proves a symptomatic catheter infection regardless of presentation.", "Pyuria does not by itself distinguish ASB from infection."),
   ("A catheter makes indefinite suppressive antibiotics universally beneficial.", "Routine suppression brings resistance and other harms without established benefit."),
   ("Any positive culture establishes bloodstream infection.", "Bacteriuria does not establish bacteremia."),
   ("Routine broadening of antibiotics will permanently sterilize a chronic catheter.", "Recolonization is common and does not justify repeated broad treatment.")],
  "Assess the person and catheter indication, not the laboratory finding in isolation. New symptoms require evaluation for infection and other causes, but asymptomatic bacteriuria in a long-term catheter is not itself a treatment target. Avoid applying this answer to a septic or symptomatic patient.", secondary=("T13","T19"))

q("GS-001", "T11", ["T11.O01"], GS, "Diagnosis; Table 2, printed pages 25-26",
  "A young adult has persistent hypokalemic metabolic alkalosis, hypomagnesemia, low urinary calcium and low-normal blood pressure. No diuretic exposure is identified. Which inherited disorder best fits the pattern?",
  "Gitelman syndrome.",
  [("Distal renal tubular acidosis.", "Distal acidification failure produces metabolic acidosis rather than this alkalosis."),
   ("Liddle syndrome.", "Its sodium-retaining, hypertensive phenotype does not fit the salt-losing pattern."),
   ("Autosomal dominant polycystic kidney disease.", "This electrolyte pattern localizes a tubular transport problem, not a cystic structural disorder."),
   ("A primary glomerular nephrotic syndrome.", "The described electrolyte and urinary-calcium pattern is not explained by isolated glomerular protein loss.")],
  "The combination suggests a distal salt-transport defect, with renal potassium and magnesium loss. It supports testing for Gitelman syndrome but does not replace exposure assessment or genetic confirmation. A single low magnesium result would be much less specific than the combined phenotype.", secondary=("T12","T04"))
q("GS-002", "T11", ["T02.O02"], GS, "Diagnosis: genetic confirmation and differential, printed page 26",
  "A patient has a Gitelman-like biochemical phenotype. Which finding most directly establishes the molecular diagnosis?",
  "Biallelic pathogenic inactivating variants in SLC12A3, interpreted in the clinical context.",
  [("Any single variant of uncertain significance in SLC12A3.", "Uncertainty and recessive inheritance cannot be bypassed by finding one variant."),
   ("A normal ultrasound without genetic testing.", "Imaging can support the workup but does not establish the causal genotype."),
   ("One low potassium value after vomiting.", "An acquired transient cause can mimic part of the phenotype."),
   ("A hydrochlorothiazide challenge in every patient.", "The consensus discourages this diagnostic approach because of risks and the availability of genetic testing.")],
  "Gitelman syndrome usually reflects loss of the thiazide-sensitive sodium-chloride cotransporter. Genetic interpretation must consider pathogenicity and inheritance; one uncertain result is not confirmation. Revisit phenocopies and acquired causes when results and phenotype disagree.", secondary=("T12","T02"), skill="mechanism")
q("GS-003", "T19", ["T19.O01"], GS, "Treatment: magnesium replacement, printed page 28",
  "In confirmed Gitelman syndrome, hypokalemia persists despite potassium replacement and magnesium remains markedly low. Which explanation best supports reviewing magnesium treatment?",
  "Magnesium depletion can make potassium replacement less effective.",
  [("Magnesium has no relationship to potassium handling.", "The linked deficiencies are a central treatment consideration."),
   ("Potassium replacement permanently cures the inherited transport defect.", "Supplementation manages losses; it does not reverse the genotype."),
   ("More sodium restriction will necessarily correct the potassium.", "Gitelman syndrome is a salt-losing state; routine restriction can worsen depletion."),
   ("Normalizing potassium for one day proves further monitoring unnecessary.", "Ongoing losses and tolerability require continued review.")],
  "Review both electrolytes and the tolerated replacement regimen. Magnesium depletion contributes to refractory hypokalemia, while oral magnesium can be limited by gastrointestinal effects. Treatment is individualized, with attention to symptoms, rhythm risk and kidney function rather than unbounded supplement escalation.", secondary=("T11","T04"), skill="mechanism")
q("GS-004", "T19", ["T19.O01"], GS, "Treatment: potassium-sparing agents, printed page 29",
  "A patient with Gitelman syndrome and symptomatic low blood pressure is being considered for amiloride because supplements have been insufficient. Which tradeoff must be discussed?",
  "Potassium conservation may help, but additional sodium loss can worsen hypotension and volume depletion.",
  [("Potassium-sparing treatment cannot affect volume status.", "Distal sodium handling is relevant to its benefit and harm."),
   ("Low blood pressure proves an unlimited dose will be safe.", "It increases concern about tolerance, not protection from harm."),
   ("The medicine removes the need to follow potassium during AKI.", "Reduced kidney excretion can change treatment risk during acute illness."),
   ("It is a definitive genetic cure.", "The inherited transport defect remains.")],
  "An adjunct can improve potassium yet compound salt depletion. The starting plan therefore needs clinical review of pressure, volume and electrolytes, and a sick-day reassessment strategy. This is a treatment tradeoff, not a universal recommendation for the same agent or dose in every patient.", secondary=("T11","T09"), skill="common_reasoning")

q("PD-001", "T20", ["T20.O02"], PD, "Table 1, corrected by DOI 10.1177/08968608241251453 (2024)",
  "A PD patient remains unwell with cloudy effluent and a persistently high effluent leukocyte count after five days of appropriate antibiotics. Which cell-count expression matches the corrected refractory-peritonitis definition?",
  "More than 0.1 x 10^9/L, equivalent to more than 100 cells/microliter.",
  [("More than 100 x 10^9/L.", "That was the typographic error corrected in the 2024 notice."),
   ("More than 0.1 cells/microliter.", "That is one thousand times below 100 cells/microliter."),
   ("More than 100 cells/L.", "A liter contains one million microliters; the units are not interchangeable."),
   ("Any leukocyte at any time after the first antibiotic dose.", "The definition includes persistence after appropriate therapy, not immediate sterility.")],
  "The corrected threshold is 0.1 x 10^9/L = 100 x 10^6/L = 100 cells/microliter. Apply it with the clinical course, treatment adequacy and effluent appearance. A unit transcription error must not become a clinical threshold; this question does not replace assessment of a deteriorating patient.", secondary=("T17",))
q("PD-002", "T20", ["T20.O02"], PD, "Refractory peritonitis: effluent trajectory and catheter decisions",
  "On day five of appropriate PD-peritonitis antibiotics, a patient is clinically improving and effluent leukocytes have fallen from 2400 to 180 cells/microliter. Which interpretation best reflects the guideline's nuance?",
  "Specialist observation beyond day five can be considered when the count is moving toward normal and the patient is improving.",
  [("Day five alone mandates removal in every improving episode regardless of trajectory.", "The guidance permits a longer observation period in selected improving patients."),
   ("A falling count guarantees cure and permits stopping treatment now.", "Improvement is not complete resolution and does not establish cure."),
   ("The same observation strategy is appropriate during clinical deterioration.", "Deterioration can require earlier catheter removal and escalation."),
   ("The leukocyte trend makes organism and susceptibility results irrelevant.", "Treatment adequacy and organism-specific considerations still matter.")],
  "The day-five definition and the management decision are related but not identical. A favorable trajectory can justify continued close observation; persistent failure or deterioration supports catheter removal. Reassess symptoms, cultures and response rather than turning a calendar cutoff into an isolated rule.", secondary=("T17","T22"), skill="common_reasoning")
q("PD-003", "T17", ["T17.O02"], PD, "Table 1: relapsing, recurrent and repeat episodes",
  "A PD patient develops a second peritonitis episode with the same organism two weeks after completing treatment of the first episode. Which classification best fits?",
  "Relapsing peritonitis.",
  [("Recurrent peritonitis, defined by a different organism within four weeks.", "The second organism here is the same."),
   ("Repeat peritonitis, defined by the same organism more than four weeks later.", "The interval here is only two weeks after treatment completion."),
   ("Refractory peritonitis based solely on the new episode's timing.", "Refractory describes failure to clear during appropriate treatment, not this recurrence interval."),
   ("A new unrelated episode that requires no review of prior microbiology.", "Timing and organism identity specifically connect the episodes.")],
  "Use the end of the prior treatment course and organism identity when classifying recurrence. This is a relapsing pattern and should prompt review of the prior course and catheter strategy. Classification organizes decisions; it does not supply an organism-specific prescription.", secondary=("T20",))
q("PD-004", "T22", ["T22.O02"], PD, "Fungal peritonitis: catheter removal",
  "A symptomatic PD patient has yeast identified in dialysis effluent. What is the most appropriate access-related response alongside antifungal management?",
  "Arrange prompt catheter removal with the PD team and plan ongoing kidney support.",
  [("Apply the improving bacterial day-five observation rule to every fungal episode.", "Fungal peritonitis has a separate catheter-removal recommendation."),
   ("Retain the catheter until a month of unchanged symptoms has passed.", "Unnecessary delay exposes the patient to continuing infection risk."),
   ("Treat only the exit site and disregard the effluent finding.", "The infection is intraperitoneal, not established as an isolated exit-site problem."),
   ("Remove the catheter but assume no antifungal therapy is needed.", "Access removal and appropriate antifungal treatment are complementary.")],
  "The fungal-peritonitis recommendation calls for immediate catheter removal. Coordinate antifungal treatment, microbiology review and an alternative dialysis plan. Do not extrapolate a conservative approach for a selected improving bacterial episode to a different organism category.", secondary=("T17","T20"), skill="common_reasoning")

q("HD-001", "T20", ["T20.O02"], HD, "Guideline 4.1 and rationale: intradialytic hypotension",
  "During HD, a patient becomes dizzy and hypotensive while ultrafiltration is running. What is the immediate priority?",
  "Stop ultrafiltration, obtain prompt clinical assessment and restore haemodynamic stability under the unit protocol.",
  [("Increase ultrafiltration to achieve the target weight faster.", "That can further reduce effective circulating volume."),
   ("Wait for the next monthly adequacy measurement.", "Symptomatic instability needs immediate intervention."),
   ("Assume the machine's urea clearance means the event is harmless.", "Solute clearance does not establish circulatory tolerance."),
   ("Permanently abandon all future dialysis without reviewing the cause.", "Stabilization and cause assessment precede long-term prescription decisions.")],
  "Treat the unstable patient first. Ceasing fluid removal and appropriate positioning/fluid support are unit responses, with assessment for other causes such as bleeding, arrhythmia or infection. After recovery, review the prescription and target weight; recurrent events are not an acceptable cost of reaching a number.", secondary=("T07","T27"))
q("HD-002", "T20", ["T20.O02"], HD, "Guideline 4.1: avoiding excessive ultrafiltration",
  "A patient has large interdialytic gains and repeatedly becomes hypotensive when all excess fluid is removed in a short session. Which plan best addresses the competing needs?",
  "Review gains and target weight, and consider more time or sessions and staged fluid removal.",
  [("Maintain the same short session and progressively increase removal speed.", "That may worsen haemodynamic intolerance."),
   ("Accept permanent overload without discussing alternatives.", "Volume excess has symptoms and longer-term consequences."),
   ("Declare the target weight correct forever because it was once tolerated.", "Body composition and illness can change the appropriate target."),
   ("Use a single urea reduction ratio to calculate the entire fluid plan.", "A solute ratio does not determine volume tolerance.")],
  "Managing volume requires balancing overload against intradialytic injury and symptoms. The guideline supports addressing fluid gains, using a staged approach to target weight and augmenting the schedule when necessary. Include the patient's practical constraints rather than framing recurrent hypotension as nonadherence alone.", secondary=("T25","T27"), skill="common_reasoning")
q("HD-003", "T23", ["T23.O01"], HD, "Guideline 1.2: incremental schedules and residual function",
  "A patient receives an incremental HD schedule supported by measured residual kidney function. After an intercurrent illness, urine output falls substantially. Which response is best?",
  "Reassess residual clearance and the adequacy of the combined kidney-plus-dialysis prescription.",
  [("Keep the schedule unchanged because the original clearance measurement remains valid forever.", "Residual function can decline and materially alter total clearance."),
   ("Assume any urine volume proves adequate solute clearance.", "Urine volume and solute clearance are related but not equivalent."),
   ("Stop measuring dialysis delivery because the patient still urinates.", "Both treatment delivery and residual contribution matter."),
   ("Infer the exact residual urea clearance from blood pressure alone.", "Blood pressure does not quantify residual solute removal.")],
  "Incremental schedules rely on an ongoing contribution from native kidneys, not a historical label. Re-evaluate that contribution after illness and adjust treatment to the person's clearance, volume and symptom needs. Measured residual function should not be replaced by urine volume alone.", secondary=("T20",))
q("HD-004", "T20", ["T20.O02"], HD, "Guideline 4.1: dialysate temperature and hypotension rationale",
  "A unit reviews recurrent intradialytic hypotension and routinely uses dialysate at 37.5 degrees C. Which prescription feature is reasonable to review alongside fluid removal and target weight?",
  "Consider a cooler individualized temperature; the guideline recommends no higher than 36 degrees C if a standardized temperature is used.",
  [("Increase temperature routinely to 39 degrees C to prevent vasodilation.", "Heating does not provide the cooling strategy described in the guidance."),
   ("Temperature can never influence haemodynamic tolerance.", "The guideline specifically addresses temperature in fluid-management practice."),
   ("A cooler setting removes the need to investigate every hypotensive episode.", "It is one prescription measure, not a substitute for finding other causes."),
   ("Change temperature without discussing comfort or the patient's response.", "An individualized approach considers tolerability as well as pressure.")],
  "Temperature is a modifiable part of the prescription. Cooler dialysis can improve haemodynamic tolerance, but fluid-removal rate, target weight, illness and comfort still require review. The cited 2019 guideline is an overdue-review baseline; this item does not claim a newly validated universal temperature prescription.", secondary=("T27",), skill="common_reasoning")

q("BK-001", "T17", ["T17.O02"], BK, "Table 5: plasma DNAemia confirmation and monitoring",
  "A kidney recipient with stable graft function has a first plasma BK DNA result of 2600 copies/mL. Which next step best establishes the trajectory under the 2024 consensus?",
  "Repeat plasma testing within two to three weeks, using a consistent assay, and review the clinical context.",
  [("Call the single value biopsy-proven BK nephropathy.", "DNAemia is not a tissue diagnosis."),
   ("Wait one year because every value below 10000 is harmless.", "Persistent lower-level DNAemia can still be clinically important."),
   ("Compare the value directly with an uncalibrated urine assay from another laboratory.", "Specimen and assay differences can invalidate the apparent trend."),
   ("Treat one low-level result as proof of acute rejection.", "The result identifies viral DNA, not rejection.")],
  "For plasma loads in the 1000-10000 copies/mL range, a repeat within two to three weeks helps distinguish transient detection from persistence. Use the same specimen type and laboratory approach where possible. Subsequent action depends on persistence, magnitude, graft function and immunological risk.", secondary=("T21","T02"))
q("BK-002", "T19", ["T19.O01"], BK, "Table 7: reduction of immunosuppression; management context",
  "A kidney recipient has a verified plasma BK load above 10000 copies/mL, without concurrent rejection or high immunological risk. What is the principal treatment strategy in the consensus?",
  "A coordinated reduction of maintenance immunosuppression with virological and graft monitoring.",
  [("Increase every immunosuppressant to suppress the virus directly.", "Greater immunosuppression can impair antiviral immune control."),
   ("Stop every immunosuppressant abruptly without transplant-team review.", "Unstructured withdrawal creates avoidable rejection risk."),
   ("Rely on antibiotic prophylaxis while leaving the regimen unreviewed.", "Routine antibiotics do not address the viral immune-control problem."),
   ("Ignore the result until graft failure develops.", "The verified load supports intervention before advanced injury.")],
  "There is no broadly effective approved antiviral substitute for restoring appropriate immune control. Use a predefined transplant-team reduction strategy and monitor viral kinetics and graft status. The recommendation is qualified by immunological risk and concurrent rejection; it is not a universal unsupervised dose change.", secondary=("T21","T17"), skill="common_reasoning")
q("BK-003", "T19", ["T19.O01"], BK, "Table 7: agents not recommended for BK treatment",
  "A recipient with BK DNAemia is offered leflunomide as routine antiviral treatment instead of reviewing immunosuppression. Which response fits the 2024 consensus?",
  "Routine leflunomide is not recommended for this indication; review the established immunosuppression and monitoring strategy.",
  [("Leflunomide is proven superior to all immunosuppression-reduction strategies.", "The consensus does not support that efficacy claim."),
   ("A fluoroquinolone is the routinely recommended antiviral alternative.", "The consensus also advises against fluoroquinolones for BK prevention or treatment."),
   ("Cidofovir has established routine benefit without kidney toxicity concerns.", "The guidance does not recommend routine cidofovir; toxicity is relevant."),
   ("A negative bacterial culture makes any antiviral regimen effective.", "Bacterial culture results do not establish efficacy against BK polyomavirus.")],
  "Experimental plausibility does not establish clinical benefit. The consensus advises against leflunomide, cidofovir and fluoroquinolones for routine BK treatment. A difficult case requires specialist assessment of viral course, graft injury and rejection risk rather than assuming an off-label agent solves the tradeoff.", secondary=("T17","T21"), skill="common_reasoning")
q("BK-004", "T02", ["T02.O02"], BK, "Pathology/diagnostics recommendations: biopsy with DNAemia",
  "An adult kidney recipient has persistent BK DNAemia, stable graft function and no high immunological risk. Which statement about biopsy is most accurate?",
  "Biopsy is not invariably required in this setting; graft dysfunction or high immunological risk can change the decision.",
  [("Every positive plasma assay mandates an emergency biopsy.", "The consensus distinguishes stable low-risk adults from situations needing tissue assessment."),
   ("Biopsy is never useful once plasma BK DNA is detected.", "Tissue may clarify injury and competing diagnoses in a changed clinical context."),
   ("Plasma DNA quantification alone histologically distinguishes BK injury from rejection.", "Virology cannot supply the same information as histology."),
   ("A stable creatinine excludes every possible form of allograft injury.", "Stable function informs the decision but is not a universal exclusion test.")],
  "Testing should answer a management question. In stable adults without high immunological risk, routine biopsy is not required solely because DNAemia persists. A rising creatinine, proteinuria, hematuria or concern for rejection may make tissue assessment important; interpretation must integrate clinical and virological data.", secondary=("T21","T17","T22"))

q("PREG-001", "T24", ["T24.O01"], PREG, "Guideline 4.1.1: renal function in pregnancy",
  "A pregnant patient with CKD has a laboratory-reported eGFR next to her creatinine. Which measurement strategy is appropriate for monitoring kidney function during pregnancy?",
  "Follow serum creatinine and its clinical trajectory because standard eGFR equations are not valid in pregnancy.",
  [("Use the automatically reported eGFR as a validated pregnancy-specific result.", "The standard equation has not acquired validity merely by being printed."),
   ("Ignore creatinine because pregnancy prevents AKI.", "Pregnancy does not protect against kidney injury."),
   ("Diagnose the cause of kidney dysfunction from eGFR alone.", "A filtration estimate does not identify a cause."),
   ("Interpret every adult-normal creatinine as reassuring regardless of gestation or baseline.", "Pregnancy physiology and a change from baseline affect interpretation.")],
  "Pregnancy changes filtration and the relationship between creatinine and standard estimating equations. Use the actual creatinine trend, prior values and clinical findings with the obstetric-nephrology team. A value within a nonpregnant reference interval can still merit review in context.", secondary=("T01","T02"))
q("PREG-002", "T24", ["T24.O01"], PREG, "Guidelines 4.4.5-4.4.6: superimposed pre-eclampsia",
  "At 29 weeks, a woman with chronic hypertension and proteinuric CKD develops sustained BP 170/112 mmHg and a doubling of proteinuria from early pregnancy. What is the appropriate interpretation?",
  "Urgent assessment for superimposed pre-eclampsia is required; baseline CKD does not explain away the change.",
  [("Pre-eclampsia is excluded because proteinuria preceded pregnancy.", "Pre-existing proteinuria can obscure rather than exclude a superimposed process."),
   ("The change automatically proves a new primary glomerulonephritis.", "Several causes remain possible; the gestational and clinical context matters."),
   ("Defer assessment until after delivery because baseline hypertension was known.", "Severe new deterioration requires assessment now."),
   ("A proteinuria increase alone dictates a universal delivery time.", "Delivery decisions require maternal and fetal assessment beyond one measurement.")],
  "Severe hypertension and a substantial rise in proteinuria are assessment triggers in this population. Evaluate symptoms, maternal organ dysfunction, fetal status and alternative causes urgently. The trigger is not a complete diagnostic algorithm or an isolated rule for delivery timing.", secondary=("T09","T27"), skill="common_reasoning")
q("PREG-003", "T24", ["T24.O01"], PREG, "Guidelines 4.1.2-4.1.3: proteinuria quantification",
  "At an early pregnancy review, a patient with CKD needs baseline proteinuria quantified. Which approach is supported?",
  "A urine protein:creatinine or albumin:creatinine ratio; a routine 24-hour collection is not required.",
  [("Visual inspection of urine is an adequate quantitative baseline.", "Appearance does not quantify protein excretion."),
   ("A dipstick colour is interchangeable with a measured ratio for all follow-up.", "Formal quantification supports comparisons and clinical interpretation."),
   ("Every pregnant patient must complete a 24-hour collection before any assessment.", "The guideline supports spot ratios without routinely requiring a timed collection."),
   ("Proteinuria is uninterpretable in pregnancy and should never be measured.", "A baseline and trajectory contribute to pregnancy kidney assessment.")],
  "A quantified baseline helps distinguish later changes from pre-existing proteinuria. Use uPCR or uACR with units and timing recorded, and interpret subsequent results with the clinical picture. The method reduces collection burden while preserving a useful comparison.", secondary=("T02",))
q("PREG-004", "T24", ["T24.O02"], PREG, "Guideline 4.3.1: pre-eclampsia prophylaxis",
  "A pregnant patient with CKD has no contraindication to aspirin and asks about reducing pre-eclampsia risk. Which approach is supported by the renal-pregnancy guidance?",
  "Offer low-dose aspirin through the antenatal plan, with contraindications and timing reviewed by the team.",
  [("Aspirin guarantees that pre-eclampsia cannot occur.", "Risk reduction is not complete prevention."),
   ("Aspirin replaces blood-pressure and fetal-growth monitoring.", "Surveillance remains necessary despite preventive treatment."),
   ("Every pregnant patient with CKD should instead start an ACE inhibitor for prevention.", "ACE inhibitors are not recommended for treating hypertension in pregnancy."),
   ("Wait for a hypertensive emergency before discussing preventive care.", "Prevention is addressed earlier in the pregnancy plan.")],
  "The 2019 renal-pregnancy guideline recommends offering low-dose aspirin in CKD pregnancy to reduce pre-eclampsia risk. This is one part of coordinated antenatal care, with individual safety checks and ongoing surveillance. It does not guarantee an uncomplicated pregnancy or specify an entire obstetric protocol.", secondary=("T19","T09"), skill="common_reasoning")

case("IGA", "T10", ("T02","T08","T22","T16"),
  "Persistent urinary findings after visible hematuria resolves",
  "Separate a suspected glomerular diagnosis, tissue confirmation, prognosis and treatment selection.",
  [stage("A synthetic 41-year-old had visible hematuria during a respiratory illness. Six weeks later the urine remains microscopically bloody, protein excretion is 1.2 g/day and eGFR is 76. Serum IgA is mildly raised. No biopsy contraindication has been identified.",
      ["Which findings support a glomerular problem without proving its cause?", "What would tissue assessment add?"],
      ["The chronology is compatible with IgAN but not diagnostic; serum IgA is not a validated substitute for biopsy.", "Persistent proteinuria above the biopsy-consideration threshold supports a discussion of tissue diagnosis, procedural risks and the value of checking alternative causes."],
      IGA,"Practice point 1.2.1"),
   stage("Biopsy confirms IgAN. The patient sees a prognostic score and asks whether it specifies the best medicine. Proteinuria falls to 0.6 g/day with initial care, but the long-term course is unknown.",
      ["How do prognosis and predicted treatment benefit differ?", "What needs reassessment even after proteinuria improves?"],
      ["A prediction score estimates progression risk; it does not establish which particular treatment will work. Histology also needs clinical context rather than a drug choice from one score.", "Proteinuria of 0.6 g/day still warrants review under the 2025 risk framework. Follow proteinuria, eGFR trajectory, blood pressure, tolerability and the patient's priorities."],
      IGA,"Practice points 1.4.1.1 and 1.4.2.3"),
   stage("The patient asks whether the same medication reasoning would apply to a relative who has skin-limited IgA vasculitis and normal kidney tests.",
      ["Which distinction changes the discussion?", "Does absence of kidney disease today end surveillance?"],
      ["IgAN with kidney involvement and isolated extrarenal IgAV are different treatment settings. Systemic glucocorticoids should not be given solely to prevent nephritis in the latter.", "Continue appropriate kidney assessment over time. New hematuria, proteinuria or impaired function would create a new diagnostic and treatment question."],
      IGA,"Recommendation 1.9.1.1; diagnosis and monitoring scope")],
  ["Tissue diagnosis, risk prediction and selection of treatment answer different questions.", "Do not use a short stable interval or sub-1-g/day proteinuria as proof of no risk."],
  [("T10.O01",[1],"Persistent hematuria/proteinuria requires diagnosis beyond serum IgA."),
   ("T10.O02",[2,3],"Risk assessment supports individualized treatment and avoidance of unsupported preventive steroids.")])

case("DI", "T03", ("T07","T19","T27"),
  "A hospital transfer interrupts water and desmopressin access",
  "Follow changing water balance in established adult CDI through admission, resuscitation and recovery.",
  [stage("A synthetic adult with established CDI arrives from another ward drowsy during an acute infection. Water is out of reach and the medication transfer record omitted desmopressin. Sodium has risen from 143 to 154 mmol/L. Pulse is fast and the clinical examination suggests intravascular depletion.",
      ["Which preventable changes explain the new risk?", "What are the immediate assessment priorities?"],
      ["Loss of access to drinking and interruption of antidiuretic replacement can unmask uncontrolled water loss. Identify the usual regimen and contact the responsible endocrine team.", "Assess circulation, sodium, potassium, kidney function and measured input/output urgently. A depleted patient may not initially display striking polyuria."],
      DI,"Risk stratification and decompensated CDI: assessment"),
   stage("The team restores intravascular volume with isotonic saline and plans controlled water replacement. After desmopressin, high dilute urine output decreases substantially.",
      ["How does the fluid plan need to respond?", "Which observations should guide the next dose and fluid rate?"],
      ["A replacement rate chosen during uncontrolled losses can become excessive once antidiuresis begins. Reassess current urine output rather than continuing to replace the earlier rate.", "During resuscitation check sodium every four hours and follow clinical volume and fluid balance. Coordinate further desmopressin with the response under specialist care to avoid excessive sodium reduction."],
      DI,"Decompensated CDI: fluids, monitoring and DDAVP"),
   stage("The patient is alert, can swallow safely and is preparing for another ward transfer. The receiving team asks for a one-line diagnosis only.",
      ["What information would prevent recurrence?", "What should be individualized as acuity falls?"],
      ["Transfer the agreed desmopressin route and schedule, water-access needs, recent sodium trend, monitoring plan and responsible team. An isolated diagnosis does not ensure treatment delivery.", "Resume oral or nasogastric water when safe and adjust monitoring to clinical and biochemical stability. The guidance concerns established adult CDI; it does not establish a diagnostic water-deprivation test or a pregnancy regimen."],
      DI,"Organisational guidance; impaired consciousness; recovery fluid route")],
  ["Replace the lost care arrangements as well as the water deficit.", "Fluid and desmopressin decisions must follow the changing balance."],
  [("T03.O02",[1,2,3],"Coordinate monitored water-disorder treatment and correction as acuity changes."),
   ("T19.O02",[3],"Specify medication continuity, monitoring and the next responsible team after an interruption.")])

case("CKD-RISK", "T08", ("T02","T20","T21","T26"),
  "From a changed ACR to a preparation discussion",
  "Interpret longitudinal measurements and distinguish risk-based planning from starting dialysis.",
  [stage("A synthetic patient with established CKD G3b has ACR rise from 12 to 29 mg/mmol and eGFR fall from 42 to 32 over several months. They have not recently started haemodynamically active therapy. The patient assumes that all changes are inevitable.",
      ["Which changes warrant evaluation?", "What must be checked before calling the decline irreversible?"],
      ["The eGFR decline exceeds 20% and ACR has more than doubled. Both warrant evaluation rather than being dismissed as routine variability.", "Review timing, measurement conditions, illness, volume, medicines, urine findings and possible obstruction as indicated. Confirm the trajectory while addressing reversible causes."],
      CKD,"Practice points 2.1.3-2.1.5"),
   stage("After reassessment the clinician uses an externally validated equation suitable for CKD G3-G5. The five-year kidney-failure risk is 7%. The patient asks whether this is a forecast of a specific date.",
      ["How should the probability be explained?", "How can it change referral and multidisciplinary care?"],
      ["A probability over five years is not a promised outcome or date. Its usefulness depends on the model population and reliable inputs.", "The risk can support nephrology referral alongside eGFR, ACR and other findings. Different time horizons and thresholds inform referral, multidisciplinary support and replacement preparation; they should not be interchanged."],
      CKD,"Recommendation 2.2.1; practice points 2.2.1-2.2.4"),
   stage("Later, the two-year risk rises to 48%. The person has no refractory symptoms and wants time to understand home treatment, transplantation and conservative care.",
      ["Which preparations can begin?", "What additional evidence determines actual dialysis initiation?"],
      ["Discuss options and begin appropriate access/transplant preparation while incorporating goals and practical circumstances. High near-term risk gives planning time.", "Start dialysis from a composite of symptoms, signs, quality of life, preferences and biochemical/volume problems. Preparation is not an order to begin treatment solely because a model threshold was crossed."],
      CKD,"Practice points 2.2.3 and 5.4.1-5.4.2")],
  ["Measurement changes trigger investigation; risk estimates organize future care.", "Preparation and dialysis initiation are separate decisions."],
  [("T08.O02",[1,2,3],"Use serial measurements and validated risk for longitudinal care."),
   ("T20.O01",[3],"Separate planning thresholds from clinical dialysis indications.")])

case("ANEMIA-RESPONSE", "T08", ("T17","T19","T20","T21"),
  "An ESA dose rises while the reason for anemia changes",
  "Investigate iron deficiency, infection and treatment response before escalating anemia treatment.",
  [stage("A synthetic dialysis patient has Hb 88 g/L, low TSAT and falling ferritin. ESA requirements have increased. There has been no review of access losses, gastrointestinal symptoms, delivered dialysis or the reticulocyte count.",
      ["What is missing from the cause assessment?", "Why is increasing the dose alone an incomplete response?"],
      ["Revisit the blood count, reticulocytes and iron measures, then investigate blood loss, inflammation and other causes as indicated. Check actual dialysis delivery and treatment history.", "Hyporesponsiveness may reflect a reversible driver. An escalating ESA requirement is a reason to investigate, not proof that the haemoglobin target should be normalized."],
      ANEMIA,"Practice points 1.2.1-1.2.3 and 3.7.1; Table 9"),
   stage("Before the next scheduled iron dose, the patient develops a systemic infection. They ask whether every anemia treatment must now be stopped permanently.",
      ["Which decision is time-limited?", "How should the reassessment be documented?"],
      ["Consider temporarily suspending iron during systemic infection. This does not make replacement permanently inappropriate once its indication and safety are reassessed.", "Record the acute reason, follow-up clinical and iron/Hb measurements, and who will decide on resumption. Avoid substituting transfusion merely because an iron dose is deferred."],
      ANEMIA,"Practice point 2.8; practice point 4.1"),
   stage("After recovery the team discusses persistent anemia, possible transplantation and treatment goals. There is no haemorrhage or unstable coronary disease.",
      ["What changes the transfusion discussion?", "Which aim should guide ESA maintenance?"],
      ["Weigh symptoms, signs and alternatives against transfusion harms, including allosensitization in a transplant candidate. An arbitrary Hb threshold alone does not settle this chronic decision.", "Individualize an adult ESA maintenance target below 115 g/L. Discuss benefit and harm without treating a normal population haemoglobin as the required goal."],
      ANEMIA,"Recommendation 3.3.1; practice points 4.1-4.5")],
  ["A changing treatment response deserves a new cause assessment.", "Infection holds, transfusion decisions and ESA targets require distinct reasoning."],
  [("T08.O03",[1],"Investigate causes and reversible drivers of anemia/ESA hyporesponsiveness."),
   ("T08.O04",[1,3],"Avoid reflexive ESA escalation and excessive adult targets."),
   ("T19.O01",[2,3],"Review time-dependent iron/transfusion treatment risks.")])

case("KIDNEY-PROTECTION", "T14", ("T08","T09","T19"),
  "Layering kidney protection without losing the monitoring plan",
  "Distinguish an expected filtration response, potassium-limited treatment and an acute interruption.",
  [stage("A synthetic adult with T2D and albuminuric CKD starts an SGLT2 inhibitor alongside a tolerated ARB. eGFR changes from 44 to 40, while blood pressure, intake and symptoms remain stable.",
      ["What does the timing and magnitude suggest?", "What would make the result more concerning?"],
      ["A modest early reversible fall can occur. In this stable setting it does not automatically require discontinuation.", "Assess symptoms, volume depletion, intercurrent illness and the scale of any further change. Do not assume every future decline is benign simply because the first was small."],
      CKD,"Practice points 3.7.3 and 2.1.4"),
   stage("Albuminuria persists. An nsMRA is discussed, but potassium has been 5.5-5.7 mmol/L on repeated checks. Another suggestion is adding an ACE inhibitor to the ARB.",
      ["Which eligibility condition is missing?", "Why is dual RAS blockade not the alternative solution?"],
      ["An nsMRA decision includes normal potassium and capacity for ongoing monitoring; address hyperkalemia and contributing medicines before selection.", "Routine ACEi/ARB combination is discouraged because added harm can outweigh benefit. Review the complete regimen and choose a suitable strategy rather than combining drugs that intensify the same risk."],
      CKD,"Recommendation 3.8.1; practice point 3.8.3; recommendation 3.6.4"),
   stage("The patient later needs surgery and prolonged fasting. They have a temporary SGLT2 interruption but no documented restart discussion.",
      ["What belongs in the handoff?", "Why is a blanket permanent discontinuation also unsatisfactory?"],
      ["State the reason for withholding, clinical recovery and intake checks, and who will reassess restart. The perioperative/diabetes team should coordinate the plan.", "Acute ketosis risk justifies a temporary safety decision. Once the acute risk changes, reassess the long-term benefit and suitability so a useful medicine is not omitted indefinitely."],
      CKD,"Practice point 3.7.2; medication stewardship")],
  ["Use trend, symptoms and eligibility criteria together.", "Every temporary interruption needs a recovery review."],
  [("T14.O01",[2],"Select kidney-protective therapy within potassium and treatment-safety conditions."),
   ("T14.O02",[1,3],"Interpret early response and fasting-related interruption."),
   ("T09.O02",[2],"Avoid dual RAS blockade while reviewing potassium and treatment tolerance."),
   ("T19.O02",[3],"Specify a reassessment and restart plan.")])

case("BACTERIURIA", "T17", ("T13","T19","T22","T24"),
  "The same urine result has different implications before a procedure",
  "Work from symptoms and context rather than treating bacteriuria as a universal antibiotic indication.",
  [stage("A synthetic nonpregnant adult with diabetes feels well. A urine culture taken without urinary symptoms grows E. coli. There is no fever, flank pain or planned urinary procedure.",
      ["Is a symptomatic UTI established?", "What benefit-harm explanation should accompany the decision?"],
      ["Bacteriuria without attributable symptoms is not a symptomatic infection diagnosis. Diabetes alone does not justify treating ASB.", "Discuss antimicrobial adverse effects and resistance, and which new symptoms need assessment. Avoid repeated cultures solely to obtain a sterile result in an otherwise well person."],
      ASB,"Definition; Section VI"),
   stage("Months later the patient is scheduled for an endoscopic procedure expected to breach urinary mucosa. A pre-procedure culture again shows bacteriuria.",
      ["Why is the treatment decision now different?", "Which information should guide antibiotics?"],
      ["Mucosal trauma creates a setting in which untreated bacteriuria can increase postoperative sepsis risk. The earlier non-treatment decision does not settle this new context.", "Use a pre-procedure culture and susceptibility results for a suitable short peri-procedural regimen with the procedural team. Do not turn this into indefinite suppression after the indication ends."],
      ASB,"Section XIII recommendations 1-3"),
   stage("During discussion, the clinician considers two separate examples: antenatal ASB and bacteriuria in a well person with a long-term catheter.",
      ["Which is a treatment exception?", "Which finding does not by itself turn ASB into a symptomatic infection?"],
      ["Pregnancy is a screening/treatment exception; use an appropriate pregnancy-compatible regimen. Context matters even without urinary symptoms.", "Long-term catheter bacteriuria and pyuria alone do not establish symptomatic infection. New systemic or localizing symptoms require a fresh assessment, not automatic application of the well-patient rule."],
      ASB,"Sections III and XI")],
  ["First establish the syndrome, then check pregnancy and procedural exceptions.", "Pyuria or diabetes does not replace clinical assessment."],
  [("T17.O02",[1,2,3],"Evaluate ASB and its defined treatment exceptions."),
   ("T22.O02",[2],"Coordinate culture-directed prevention before mucosa-traumatizing intervention.")])

case("SALT-WASTING", "T11", ("T12","T04","T19","T02"),
  "Cramps, alkalosis and a transport phenotype",
  "Build an inherited salt-wasting differential and a tolerable replacement plan without overcalling a variant.",
  [stage("A synthetic 22-year-old has recurrent cramps, potassium 2.9 mmol/L, bicarbonate 32 mmol/L and magnesium 0.48 mmol/L. Blood pressure is low-normal and urinary calcium is low. Potassium loss remains inappropriately renal. No current diuretic use is reported.",
      ["Which nephron process could connect these findings?", "Which acquired causes still require an exposure and symptom history?"],
      ["The combined phenotype suggests a salt-losing tubulopathy such as Gitelman syndrome. Review the pattern across time, renal losses and clinical state rather than using one electrolyte alone.", "Ask about vomiting, diuretics, laxatives and other relevant exposures. A reported absence of one medicine is not a complete differential, and some inherited phenotypes overlap."],
      GS,"Diagnosis and differential; Table 2"),
   stage("Testing identifies one SLC12A3 variant of uncertain significance. The family asks whether every relative now has a confirmed diagnosis.",
      ["What would establish the recessive molecular diagnosis?", "How should uncertainty be handled?"],
      ["Biallelic pathogenic inactivating SLC12A3 variants can establish the molecular diagnosis. A single uncertain variant does not supply that evidence.", "Coordinate genetics interpretation, inheritance review and further testing as appropriate. Keep clinical treatment of electrolyte abnormalities separate from overstating molecular certainty; biopsy is not routinely the confirmatory test for a typical phenotype."],
      GS,"Diagnosis; genetic testing"),
   stage("After specialist evaluation the patient receives oral potassium and magnesium. Gastrointestinal intolerance limits magnesium, and an adjunct potassium-sparing agent is being considered despite postural symptoms.",
      ["Why treat magnesium as part of potassium management?", "Which tradeoff needs monitoring if an adjunct is used?"],
      ["Magnesium deficiency can impair potassium correction. Review formulation, tolerability and an individualized replacement plan instead of merely escalating tablets the patient cannot tolerate.", "Potassium-sparing agents may worsen sodium depletion and hypotension. Review pressure, volume, electrolytes, kidney function and an intercurrent-illness plan; no fixed dose fits every patient."],
      GS,"Treatment, printed pages 28-29")],
  ["Interpret a transport phenotype together with exposure history and genetics.", "Treatment must address linked losses and tolerability."],
  [("T11.O01",[1,2],"Localize a tubular transport phenotype and distinguish confirmation from suggestive findings."),
   ("T02.O02",[2],"Distinguish molecular confirmation from an uncertain variant and a suggestive phenotype."),
   ("T19.O01",[3],"Balance replacement and adjunct benefit against intolerance and salt depletion.")])

case("PD-RESPONSE", "T20", ("T17","T22"),
  "The fifth day of PD-peritonitis treatment",
  "Use corrected units, microbiology and response trends to reason about catheter management.",
  [stage("A synthetic PD patient has abdominal discomfort and cloudy effluent. After prompt assessment and appropriate antibiotics, the team reviews the response on day five. A printed handout incorrectly gives a refractory threshold of 100 x 10^9 leukocytes/L.",
      ["Which correction must be made before using this reference?", "What belongs beside the count in the assessment?"],
      ["The 2024 corrigendum changes that threshold to more than 0.1 x 10^9/L, or more than 100 cells/microliter, after five days of appropriate therapy. Keep the edition and correction relationship explicit.", "Review clinical response, effluent appearance, cell-count trajectory, organism and adequacy of antibiotics. A numerical definition alone does not capture clinical deterioration."],
      PD,"Table 1 and 2024 corrigendum DOI 10.1177/08968608241251453"),
   stage("One possible course is clear clinical improvement with leukocytes falling from 1900 to 140 cells/microliter. An alternative course is worsening pain, fever and an unchanged high count despite appropriate treatment.",
      ["How do these trajectories change the catheter discussion?", "Why is day five a review point rather than a substitute for judgement?"],
      ["Selected improving patients with a count moving toward normal may be observed longer under specialist review. A persistently failing or deteriorating course supports removal, sometimes before day five.", "The observation option requires continuing close assessment; it does not establish cure or permission to continue ineffective treatment indefinitely."],
      PD,"Refractory peritonitis"),
   stage("The discussion adds two distinct possibilities: the same organism returns three weeks after completing therapy, or yeast is identified in effluent during an episode.",
      ["How is the first pattern classified?", "Why is the second not managed by simply extending bacterial observation?"],
      ["The same organism within four weeks after treatment completion fits relapsing peritonitis and calls for review of microbiology, treatment and catheter strategy.", "Fungal peritonitis has its own recommendation for immediate catheter removal plus appropriate antifungal treatment. Arrange ongoing kidney support and do not transplant the improving-bacterial exception into this setting."],
      PD,"Table 1: relapsing episodes; Fungal peritonitis")],
  ["Correct unit errors before applying a definition.", "The clinical course and organism determine whether an observation exception is appropriate."],
  [("T20.O02",[1,2,3],"Review ongoing PD care from actual infection course."),
   ("T17.O02",[1,3],"Interpret infection definition, relapse timing and fungal findings."),
   ("T22.O02",[2,3],"Balance catheter retention/removal and continuing support.")])

case("HD-ADEQUACY", "T20", ("T23","T25","T27"),
  "The dose report looks satisfactory but the patient feels worse",
  "Connect solute measurements with fluid tolerance, nutrition and changing residual kidney function.",
  [stage("A synthetic HD patient meets the unit's small-solute metric but reports breathlessness, prolonged recovery after sessions and poor appetite. Fluid gains have increased after a recent illness. The team has not reassessed target weight.",
      ["Which dimensions are missing from the dose report?", "What should be reassessed after illness?"],
      ["Small-solute clearance does not establish adequate volume control, nutrition or treatment tolerance. Review symptoms, physical findings, intake and the patient's account of recovery.", "Target weight and residual function can change. Assess current volume status and actual treatment delivery rather than treating the original prescription as permanently appropriate."],
      HD,"Guidelines 1 and 4.1: dialysis dose and fluid assessment"),
   stage("During a session the patient develops symptomatic hypotension with ongoing ultrafiltration. The planned fluid target has not yet been reached.",
      ["What takes priority now?", "Which changes could reduce recurrence after stabilization?"],
      ["Stop ultrafiltration and obtain prompt assessment and stabilizing care under the unit protocol. Evaluate other causes of instability rather than assuming every event is purely a fluid-removal problem.", "Review gains, target weight, session length/frequency and dialysate temperature. A staged approach to fluid removal may be safer than forcing the full target through a short poorly tolerated session."],
      HD,"Guideline 4.1 and intradialytic hypotension rationale"),
   stage("A second discussion considers a patient on an incremental schedule whose urine output fell after infection. A correctly sampled pre/post urea pair is 24 and 9 mmol/L.",
      ["What does the URR calculation establish?", "How should a decline in residual function affect a previously acceptable schedule?"],
      ["URR is (24 - 9)/24, or 62.5%. It quantifies sampled urea reduction; its interpretation also needs sampling quality and the broader prescription, not an automatic conclusion about total care.", "Reassess measured residual clearance and total kidney-plus-dialysis provision. Urine volume alone is not a solute-clearance measurement, and an old residual estimate must not support an unchanged schedule after a material decline."],
      HD,"Appendix: URR definition; Guideline 1.2")],
  ["Measure delivery and clinical response separately, then integrate them.", "An adequacy number cannot justify continuing symptomatic hypotension."],
  [("T20.O02",[1,2,3],"Plan ongoing HD from volume, symptoms, tolerance and changing kidney contribution."),
   ("T23.O01",[3],"Calculate sampled solute reduction and explain its limits and residual-clearance context.")])

case("BK-DECISIONS", "T17", ("T21","T19","T02","T22"),
  "A low plasma viral result becomes a persistent trend",
  "Distinguish transient DNAemia, tissue diagnosis and the immune-control/rejection tradeoff.",
  [stage("A synthetic kidney recipient with stable function has plasma BK DNA of 3100 copies/mL. An earlier urine result came from another laboratory using a different assay. The patient is told these two values prove a rising plasma load.",
      ["Which comparison is invalid?", "How should persistence be checked?"],
      ["Urine and plasma values from different assays are not interchangeable trend points. Use consistent specimen and assay methods where possible.", "For plasma DNAemia in this intermediate range, repeat within two to three weeks and review graft function and immunological risk. One value does not establish biopsy-proven nephropathy."],
      BK,"Table 5 and quantitative assay interpretation"),
   stage("Repeat plasma results using the same assay remain elevated and then exceed 10000 copies/mL. There is no concurrent rejection or high immunological risk. A routine leflunomide course is proposed as a substitute for medication review.",
      ["What is the principal management strategy?", "Which claimed shortcut lacks support?"],
      ["The transplant team should review and reduce maintenance immunosuppression through a structured plan, with viral and graft monitoring. Avoid unsupervised cessation of every drug.", "Routine leflunomide, cidofovir and fluoroquinolones are not recommended for BK treatment in the consensus. Viral control must be balanced with rejection risk, not assumed from an off-label prescription."],
      BK,"Tables 6-7: management and agents not recommended"),
   stage("The clinician compares a stable low-risk recipient with another who develops graft dysfunction during DNAemia. The patient asks whether every positive assay automatically requires a biopsy.",
      ["When can tissue change management?", "Why cannot virology alone identify every cause of graft dysfunction?"],
      ["Biopsy is not required solely for DNAemia in a stable adult without high immunological risk. Dysfunction or increased rejection concern changes the balance and can make tissue assessment important.", "Integrate pathology, function, immune risk and viral results. A positive assay does not rule out concurrent disease, and immunosuppression changes require continued surveillance for rejection."],
      BK,"Pathology and diagnostics recommendations; management context")],
  ["Use a comparable series of measurements before interpreting a trend.", "Coordinate viral control with the risk of rejection."],
  [("T17.O02",[1,2],"Evaluate viral persistence using appropriate testing and context."),
   ("T19.O01",[2],"Review immunosuppression and unsupported antiviral alternatives."),
   ("T02.O02",[3],"Explain the distinct information and indications for biopsy.")])

case("PREGNANCY-SURVEILLANCE", "T24", ("T01","T02","T09","T19","T27"),
  "Establish a pregnancy baseline before interpreting deterioration",
  "Use valid measurements, preventive care and a coordinated response to new severe hypertension.",
  [stage("A synthetic patient with known proteinuric CKD attends at 11 weeks of pregnancy. The laboratory prints an eGFR beside creatinine. Her earlier records include a spot urine ACR but no pregnancy baseline.",
      ["Which kidney-function measure should be followed?", "How can baseline proteinuria be quantified without unnecessary collection burden?"],
      ["Use serum creatinine and its trajectory because standard eGFR equations are not valid during pregnancy. Interpret the value in gestational and clinical context.", "Measure uACR or uPCR with units recorded; a routine 24-hour collection is not required. A clear baseline makes later changes easier to interpret."],
      PREG,"Guidelines 4.1.1-4.1.3"),
   stage("The nephrology-obstetric team discusses preventive care, medications and the plan for surveillance. The patient has no aspirin contraindication.",
      ["Which preventive measure can be offered?", "Which continuing assessments does it not replace?"],
      ["Offer low-dose aspirin through the antenatal plan to reduce pre-eclampsia risk, with timing and individual contraindications reviewed.", "Keep blood-pressure, kidney/proteinuria and maternal/fetal surveillance in place. Risk reduction is not a guarantee and does not remove the need for specialist obstetric input."],
      PREG,"Guidelines 4.2.2-4.2.3 and 4.3.1"),
   stage("At 31 weeks the patient develops sustained severe hypertension and proteinuria is substantially higher than the early pregnancy measurement. Baseline hypertension and proteinuria had both been present.",
      ["What superimposed process must be assessed?", "Why is a rise in proteinuria not itself a complete delivery rule?"],
      ["Urgently assess for superimposed pre-eclampsia and maternal organ dysfunction while considering other causes. Pre-existing CKD cannot be used to dismiss a severe new change.", "Delivery timing and treatment require the complete maternal and fetal picture, clinical course and specialist discussion. Neither a familiar CKD label nor an isolated threshold replaces that assessment."],
      PREG,"Guidelines 4.4.5-4.4.7")],
  ["Document a valid early baseline.", "New severe findings require assessment even when hypertension and proteinuria predate pregnancy."],
  [("T24.O01",[1,3],"Adapt measurements and the differential to pregnancy."),
   ("T24.O02",[2,3],"Coordinate preventive care and population-specific treatment decisions.")])

case("CITRATE", "T23", ("T07","T05"),
  "The circuit calcium and the patient calcium are different measurements",
  "Explain regional citrate anticoagulation and its monitoring without prescribing a circuit protocol.",
  [stage("A synthetic critically ill adult is receiving continuous kidney support with a locally validated regional citrate protocol. A trainee asks why calcium in blood leaving the filter is intentionally lower than systemic ionized calcium.",
      ["What is the regional anticoagulant mechanism?", "Why must the sampling site be recorded?"],
      ["Citrate binds ionized calcium in the circuit, limiting calcium-dependent coagulation. This is a regional mechanism rather than proof that systemic calcium should be equally low.", "Circuit and systemic samples answer different questions. Label the site and interpret each result against the appropriate protocol before changing citrate or calcium delivery."],
      CITRATE,"Section 5.3.2 rationale: calcium chelation and protocol monitoring"),
   stage("The patient needs increasing calcium replacement and the clinical team is concerned about changing citrate handling. Acid-base and calcium measurements are being reviewed.",
      ["Which linked processes must be considered?", "Why would one circuit result be insufficient?"],
      ["Citrate delivery, extracorporeal loss, metabolism and calcium replacement jointly affect systemic calcium and acid-base balance. Reassess the patient's condition and the complete protocol with the critical-care team.", "A satisfactory circuit value does not establish safe systemic calcium or metabolic handling. Examine the relevant systemic/total calcium and acid-base trend rather than adjusting from an unlabeled isolated sample."],
      CITRATE,"Section 5.3.2 rationale and Table 19: citrate complications and monitoring"),
   stage("The trainee proposes applying the same citrate and calcium infusion rates to a different machine and prescription because the anticoagulant is the same.",
      ["What makes that transfer unsafe?", "What competence does this explanation establish?"],
      ["Regional citrate requires a validated protocol matched to modality, fluid composition and flow settings. Changing the system changes the balance of citrate and calcium delivery/removal.", "Understanding the mechanism and monitoring questions supports safe discussion; it does not establish competence to independently prescribe or adjust an unfamiliar circuit."],
      CITRATE,"Section 5.3.2: protocol matched to modality and flow settings")],
  ["Interpret circuit and systemic measurements separately.", "Use the validated local protocol and the whole metabolic picture."],
  [("T23.O03",[1,2,3],"Explain citrate's regional mechanism, calcium/acid-base monitoring and protocol dependence.")])
