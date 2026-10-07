# SPDX-License-Identifier: MIT
"""Original 1.3.0 teaching text is CC BY 4.0; primary references retain their terms.

Only two existing mapping gaps are extended. No network or execution side effects.
"""
from copy import deepcopy

DATE = "2026-10-07"
GBM = "K08-2021-anti-GBM-application"
PKD = "K03-2025-genetics-application"
REVIEW = dict(status="assistant_reviewed", reviewer="Renulus content application assistant",
    reviewer_kind="assistant", reviewed_on=DATE, source_key_checked=True,
    independent_human_review=False,
    method="Assistant primary-locator, single-best-key and four-distractor review; original synthetic teaching. Scope and remaining gaps are explicit; no independent clinical review.")
QUESTIONS, CASES, EVIDENCE = [], [], []


def cite(source, locator):
    return dict(source_id=source, locator=locator)


def q(suffix, topic, objective, source, locator, stem, key, wrong, explanation, *, secondary=(), skill="common_reasoning"):
    assert len(wrong) == 4
    position = len(QUESTIONS) % 5
    choices = list(wrong)
    choices.insert(position, (key, explanation))
    identity = "RN14-" + suffix
    item = dict(id=identity, version=1, family_id=identity + ".family", family_version=1,
        key_version=1, topic_id=topic, secondary_topic_ids=list(secondary), objective_ids=[objective],
        license="CC-BY-4.0", original=True, kind="single_best_answer", usage="assessment_reserved",
        stem=stem, options=[dict(id=chr(65+i), text=t, rationale=r) for i,(t,r) in enumerate(choices)],
        answer=chr(65+position), rationale=explanation, difficulty="integration",
        sources=[cite(source, locator)], review=deepcopy(REVIEW))
    QUESTIONS.append(item)
    EVIDENCE.append(dict(id=identity, version=1, kind="question", reviewed_on=DATE,
        reviewer_kind="assistant", independent_human_review=False, skill=skill,
        source_locators=deepcopy(item["sources"]), key_text=key, checked_claim=explanation,
        objective_support=[dict(objective_id=objective, checked_claim=explanation,
                                source_locators=deepcopy(item["sources"]))],
        distractor_check="Four plausible competing decisions, each explained for the stated scenario; no all/none-of-the-above options."))


def stage(narrative, prompts, points, source, locator):
    return dict(narrative=narrative, prompts=prompts, teaching_points=points, sources=[cite(source, locator)])


def case(suffix, topic, secondary, title, summary, stages, take_home, support):
    identity = "RN14-CASE-" + suffix
    numbered = [dict(id=f"stage-{i}", **s) for i,s in enumerate(stages,1)]
    refs = [r for s in numbered for r in s["sources"]]
    refs = [r for i,r in enumerate(refs) if r not in refs[:i]]
    item = dict(id=identity, version=1, topic_id=topic, secondary_topic_ids=list(secondary),
        objective_ids=[o for o,_,_ in support], license="CC-BY-4.0", original=True,
        synthetic=True, usage="teaching", title=title, summary=summary, stages=numbered,
        take_home=take_home, sources=refs, review=deepcopy(REVIEW))
    CASES.append(item)
    claims = [dict(objective_id=o, stage_ids=[f"stage-{n}" for n in ns], checked_claim=claim,
        source_locators=[r for n in ns for r in numbered[n-1]["sources"]]) for o,ns,claim in support]
    EVIDENCE.append(dict(id=identity, version=1, kind="case", reviewed_on=DATE,
        reviewer_kind="assistant", independent_human_review=False, skill="mixed_domain_reasoning",
        source_locators=refs, key_text=None, checked_claim=" ".join(c["checked_claim"] for c in claims),
        objective_support=claims, review_limit="Open teaching discussion, not a scored case or proof of competence."))


q("GBM-001", "T10", "T10.O01", GBM, "Chapter 11, PP 11.1.1 and 11.2.1; printed S86-S87 and S233",
  "A 29-year-old develops rapidly worsening kidney function, glomerular hematuria and alveolar hemorrhage. The specialist team strongly suspects anti-GBM disease. Serology is being processed and biopsy cannot be completed until tomorrow. Which approach best fits this level of suspicion?",
  "Coordinate urgent diagnostic sampling and start the specialist treatment pathway while confirmation proceeds.",
  [("Await the final biopsy report before considering disease-directed treatment.", "Waiting for full confirmation can allow further injury when suspicion is high."),
   ("Use dialysis alone until serology returns because it removes the cause of the pulmonary disease.", "Kidney support does not replace treatment directed at pathogenic antibodies and inflammation."),
   ("Begin supportive care and reassess only if proteinuria reaches the nephrotic range.", "The pulmonary-renal presentation and rapid decline already justify urgent action."),
   ("Defer treatment unless a second antibody sample confirms persistence after several weeks.", "Repeat testing over weeks is not the appropriate response to this time-critical syndrome.")],
  "High suspicion warrants treatment before confirmation is complete. Obtain diagnostic material promptly and coordinate nephrology, pulmonary and apheresis care without allowing a delayed biopsy to become an automatic treatment delay.", secondary=("T07","T16","T22"))

q("GBM-002", "T10", "T10.O02", GBM, "Chapter 11, Recommendation 11.2.1, printed S86; implementation discussion printed S233",
  "A person with confirmed anti-GBM disease needs dialysis at presentation. An adequate kidney biopsy shows 100% crescents. They also have active pulmonary hemorrhage. A colleague proposes withholding immunosuppression and plasma exchange solely because renal recovery is unlikely. Which finding most directly defeats that use of the guideline's conservative-treatment exception?",
  "The active pulmonary hemorrhage.",
  [("The need for dialysis itself.", "Dialysis dependence is part of the exception's renal context, not the feature that defeats it here."),
   ("The high proportion of crescents itself.", "The severe biopsy finding supports a poor renal prognosis but does not remove the pulmonary treatment indication."),
   ("The biopsy sample being adequate.", "Adequate sampling helps interpret the exception; it does not override active lung disease."),
   ("The absence of a previous episode of anti-GBM disease.", "A first episode does not determine whether pulmonary disease requires treatment.")],
  "The exception combines severe renal presentation and pathology with absence of pulmonary hemorrhage. This patient has lung bleeding, so that exception does not justify withholding treatment. Renal prognosis and the need to treat dangerous extrarenal disease are separate decisions.", secondary=("T07","T16"), skill="interpretation")

q("GBM-003", "T23", "T23.O02", GBM, "Chapter 11, PP 11.2.2, printed S87 and S233",
  "After a week of plasma exchange for confirmed anti-GBM disease, pulmonary symptoms improve, but circulating anti-GBM antibodies remain detectable. Treatment remains tolerable. Which finding is the guideline's disease-specific endpoint for the plasma-exchange course?",
  "Circulating anti-GBM antibodies becoming undetectable.",
  [("Completion of seven sessions regardless of the antibody result.", "A fixed session count does not establish removal of the pathogenic antibody."),
   ("The first day without supplemental oxygen.", "Pulmonary improvement is valuable but is not the stated antibody-directed endpoint."),
   ("The first fall in serum creatinine.", "Kidney function can change independently of antibody clearance."),
   ("A dialysis urea-reduction ratio above the unit target.", "A urea metric measures a different treatment effect.")],
  "The course is guided by disappearance of circulating anti-GBM antibodies. Improvement in symptoms, creatinine or dialysis clearance cannot substitute for that disease-specific measure; monitoring and treatment tolerance remain part of ongoing care.", secondary=("T10",), skill="mechanism")

q("GBM-004", "T10", "T10.O02", GBM, "Chapter 11, PP 11.2.4-11.2.5, printed S87 and S233; current AAV drug regimen not assessed",
  "Two people have completed initial treatment for anti-GBM glomerulonephritis and have entered remission. One was anti-GBM-positive alone; the other was also ANCA-positive. Which distinction matters when planning longer-term immunosuppression?",
  "Double positivity warrants an AAV maintenance plan; isolated anti-GBM disease generally does not require maintenance therapy.",
  [("Neither needs maintenance because anti-GBM remission overrides the ANCA-associated relapse concern.", "This ignores the guideline's explicit double-positive exception."),
   ("Both need indefinite cyclophosphamide because antibody-mediated disease always relapses.", "That is not the maintenance strategy and adds unsupported treatment exposure."),
   ("Only the isolated anti-GBM case needs maintenance because ANCA positivity protects against relapse.", "The risk distinction points in the opposite direction."),
   ("Use the highest initial creatinine alone to decide maintenance, regardless of serology.", "Initial renal severity does not replace the disease-specific distinction.")],
  "The double-positive group needs maintenance assessment along the AAV pathway. Do not extend the usual no-maintenance approach for isolated anti-GBM disease to that group. Selection and dosing of a current AAV regimen are outside this question.", secondary=("T16",))

q("PKD-GEN-001", "T12", "T12.O01", PKD, "PP 1.3.1-1.3.3, printed S22; diagnosis counseling discussion S61-S62",
  "A healthy 24-year-old whose parent has ADPKD asks about screening but is worried about the personal consequences of a diagnosis. There is no urgent clinical indication to test today. What is the best first response?",
  "Explore the person's preferences and explain benefits, limitations and possible consequences before agreeing on testing.",
  [("Arrange genetic testing immediately and discuss implications only if it is positive.", "Consent requires discussion before testing, not only after an unexpected result."),
   ("Advise against all screening because a presymptomatic diagnosis cannot have value.", "Potential value depends on the person's circumstances and preferences."),
   ("Ask the affected parent to decide whether this adult should be tested.", "The adult's own preferences should guide their decision."),
   ("Promise that a result cannot affect any aspect of life outside kidney care.", "That promise cannot be made; consequences vary by context and jurisdiction.")],
  "Counseling belongs before and after screening. Discuss what the result can clarify, what uncertainty may remain and the person's reasons for wanting or declining information; avoid jurisdiction-wide promises.", secondary=("T24",))

q("PKD-GEN-002", "T12", "T12.O01", PKD, "PP 1.3.9, printed S24 and S67",
  "A family has a laboratory-confirmed pathogenic PKD1 variant that explains the affected parent's typical ADPKD. An adult child, after counseling, wants molecular testing for that familial disease. There are no unusual features suggesting a second disorder. Which test is usually sufficient?",
  "Targeted testing for the known familial pathogenic variant.",
  [("Whole-genome sequencing is required before the known variant can be assessed.", "A resolved familial variant permits a more focused test in this setting."),
   ("Test only PKD2 because the parent has already been tested for PKD1.", "The relative's question concerns inheritance of the identified PKD1 variant."),
   ("Repeat the parent's test and infer the child's genotype from the result.", "A parental result does not determine whether this child inherited the variant."),
   ("Use normal serum creatinine as a molecular exclusion test.", "Filtration is not a test for the familial variant.")],
  "A known pathogenic familial variant makes targeted testing informative for the relative. This conclusion assumes that the variant explains the family phenotype; an atypical presentation can require broader evaluation.", secondary=("T02",), skill="interpretation")

q("PKD-GEN-003", "T12", "T12.O01", PKD, "PP 1.3.17-1.3.18, printed S27; discussion S67 and S72-S73",
  "An adult has a typical clinical and imaging diagnosis of ADPKD. A clinically accredited genetic panel identifies no pathogenic or likely pathogenic variant. What should be explained about this result?",
  "The negative panel does not by itself exclude inherited ADPKD or erase the clinical diagnosis.",
  [("The imaging diagnosis must be withdrawn because genetic panels detect every causal variant.", "Methods and classification have limits; a negative result is not complete exclusion."),
   ("All relatives can now be told that their familial risk is zero.", "An unresolved molecular cause does not establish absence of inherited disease."),
   ("Any uncertain variant on the report should be relabeled pathogenic to reconcile the findings.", "Uncertainty is not a licence to invent a pathogenic classification."),
   ("Kidney follow-up should stop until a molecular diagnosis is obtained.", "The clinical disease remains relevant even when genetic testing is inconclusive.")],
  "A typical phenotype can remain clinically diagnostic despite negative or uncertain genetic testing. Explain test limits and retain an appropriate clinical and family assessment rather than treating an unresolved result as proof against inheritance.", secondary=("T02",), skill="interpretation")

q("PKD-GEN-004", "T12", "T12.O01", PKD, "PP 1.3.10-1.3.11, printed S25; living-related donor discussion S68",
  "A 28-year-old relative of a person with ADPKD is considering living kidney donation. Initial imaging is equivocal and the family's genetic cause is unresolved. Which next approach best addresses the inherited-disease uncertainty?",
  "Seek specialist genetic evaluation to clarify the family diagnosis and the potential donor's status alongside the donor assessment.",
  [("Accept the donor because an equivocal scan is equivalent to exclusion.", "Equivocal imaging leaves a relevant question unresolved."),
   ("Exclude the donor permanently because any cyst proves ADPKD.", "A cyst finding needs contextual interpretation, not automatic diagnostic certainty."),
   ("Use one normal blood pressure measurement to settle the inherited-disease question.", "Blood pressure alone cannot exclude the familial disorder."),
   ("Approve donation if the recipient's disease progressed slowly.", "The recipient's course does not establish the relative's disease status or donation eligibility.")],
  "Genetic testing can be useful when imaging is equivocal, particularly for a potential related donor. Resolving that uncertainty contributes to assessment; no genetic result alone grants approval for donation.", secondary=("T21","T02"))

case("ANTI-GBM", "T10", ("T07","T16","T23"), "Urgency, antibodies and the exception",
  "Work through suspected anti-GBM disease, pulmonary treatment need and antibody-directed follow-up.", [
    stage("A synthetic adult has a rapidly progressive nephritic presentation and pulmonary bleeding. The team suspects anti-GBM disease; serology and tissue assessment are being arranged.",
      ["What should happen while confirmation is pending?", "How can sampling proceed without creating a treatment delay?"],
      ["High suspicion calls for rapid specialist treatment alongside diagnostic confirmation.", "Kidney support and disease-directed therapy address different parts of the problem."], GBM,
      "Chapter 11, PP 11.1.1 and 11.2.1; printed S86-S87, S233"),
    stage("The diagnosis is confirmed. Dialysis is required, and an adequate biopsy shows 100% crescents. Pulmonary hemorrhage continues.",
      ["Which elements of the conservative-treatment exception are present?", "Why does the lung finding alter its applicability?"],
      ["Severe renal pathology and dialysis dependence carry prognostic weight.", "The guideline exception also requires absence of pulmonary hemorrhage; active lung bleeding prevents using this exception to withhold treatment."], GBM,
      "Chapter 11, Recommendation 11.2.1, printed S86; implementation discussion S233"),
    stage("During treatment, symptoms improve before serum anti-GBM antibodies disappear. Later, a confirmed positive ANCA result prompts discussion of longer-term follow-up.",
      ["What guides the plasma-exchange endpoint?", "How does double positivity change the maintenance discussion?"],
      ["Follow circulating anti-GBM antibodies to disappearance rather than using symptomatic improvement as the exchange endpoint.", "Double-positive disease requires an AAV maintenance assessment. The usual isolated anti-GBM no-maintenance rule does not apply unchanged; this case does not select an AAV drug or dose."], GBM,
      "Chapter 11, PP 11.2.2 and 11.2.4-11.2.5; printed S87, S233")],
  ["Confirm promptly while acting on a high-probability emergency.", "Separate renal prognosis, pulmonary treatment need and relapse planning."],
  [("T10.O01",[1],"Integrate the pulmonary-renal presentation with urgent diagnostic confirmation."),
   ("T10.O02",[2,3],"Apply the treatment exception and distinguish maintenance needs in isolated and double-positive disease."),
   ("T23.O02",[3],"Relate plasma exchange to a disease-specific antibody endpoint.")])

case("ADPKD-FAMILY", "T12", ("T02","T21","T24"), "What a family result can establish",
  "Discuss informed screening, a resolved familial variant and the limits of negative testing.", [
    stage("A synthetic 25-year-old whose parent has ADPKD asks about testing. The person wants useful information but is uncertain about the personal implications of a diagnosis.",
      ["What belongs in counseling before screening?", "How should the person's preferences shape the next step?"],
      ["Explain benefits, limits and possible consequences before agreeing on screening; provide interpretation and next-step counseling afterward.", "The adult decides with appropriate support. Avoid promises about all jurisdictions or pressure based on the parent's preferences."], PKD,
      "PP 1.3.1-1.3.3, printed S22; diagnosis counseling S61-S62"),
    stage("The parent's accredited report is obtained. It identifies a pathogenic PKD1 variant consistent with the typical family phenotype. The adult chooses molecular testing.",
      ["Which testing approach now becomes informative?", "What assumption makes a focused test appropriate?"],
      ["Targeted testing for the known familial variant is usually sufficient in this resolved family.", "Check that the pathogenic variant explains the phenotype; unusual features may require broader evaluation."], PKD,
      "PP 1.3.9, printed S24 and S67"),
    stage("In a second, unrelated family, an adult with typical ADPKD has an unresolved negative panel. A young relative is considering donation and has equivocal imaging.",
      ["Why is this negative panel different from a targeted test in a genetically resolved family?", "What remains to clarify before donor eligibility can be considered?"],
      ["An unresolved negative or uncertain result does not exclude inherited ADPKD in someone with the typical phenotype.", "Specialist genetic assessment can help clarify equivocal imaging and related-donor risk. The overall donor evaluation remains necessary."], PKD,
      "PP 1.3.10-1.3.11 and 1.3.17-1.3.18; printed S25, S27; donor discussion S68")],
  ["A resolved familial variant and an unresolved negative panel answer different questions.", "Genetic information supports counseling and assessment without replacing the person's choice or the full donor evaluation."],
  [("T12.O01",[1,2,3],"Explain informed familial testing, targeted variants, unresolved negative results and potential donor uncertainty.")])

CELLS = [
    dict(id="anti_gbm_decisions", alignment_id="glomerular_diagnosis", domain_id="glomerular_interstitial",
         prefix="RN14-GBM-", case_id="RN14-CASE-ANTI-GBM",
         outcomes=["Treat high suspicion without waiting for completed confirmation", "Apply the pulmonary-hemorrhage boundary of the renal exception", "Use the antibody endpoint for exchange", "Distinguish double-positive maintenance needs"],
         baseline_gap="Anti-GBM-specific assessment, image-based histology and full disease-specific treatment/monitoring pathways remain absent.",
         scope="Four anti-GBM decision questions and a three-stage case add the previously absent disease-specific unit.",
         remaining_gap="Anti-GBM drug doses, adverse-effect/prophylaxis protocols, refractory disease and transplant timing are not assessed. Image-based histology and complete disease-specific treatment/monitoring pathways remain incomplete."),
    dict(id="adpkd_family_testing", alignment_id="adpkd", domain_id="inherited_rare",
         prefix="RN14-PKD-GEN-", case_id="RN14-CASE-ADPKD-FAMILY",
         outcomes=["Counsel before and after screening", "Use an established familial pathogenic variant", "Interpret an unresolved negative panel", "Clarify equivocal related-donor imaging"],
         baseline_gap="No complete cascade-testing or genetic-variant interpretation bank.",
         scope="Four family/genetic-testing questions and a three-stage case add targeted testing, negative-result limits, counseling and donor uncertainty.",
         remaining_gap="Full cascade-testing delivery, variant classification/segregation, mosaicism, reproductive/pediatric testing and the complete inherited-disease differential remain incomplete."),
]
