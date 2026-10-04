# M8 final-pack claims: bounded primary-source check

2026-10-04 · `assistant_reviewed: true`; `independent_human_review: false`.
Original research notes for authoring; no pack approval or permanent source
currency clearance. Source IDs follow active-main `docs/SOURCES.md`.

Method: read `tools/content/author_expansion.py` and its inherited primary URLs
in `author_foundations.py` without executing either. Opened the four official
PDFs with `web.run`, searched exact passages, and visually checked relevant
PDF pages, including referenced figures. All four were readable; no public-HTTP
fallback, installation or saved source original was needed. Printed S-pages
below are distinct from one-based physical PDF pages.

| Dated primary | Exact checked locator/pages | Original fact and authoring boundary |
| --- | --- | --- |
| [K03 — ADPKD 2025][adpkd], aquaresis | Ch. 4, Practice Points 4.1.4.2–4.1.4.4; S121 / PDF 122 | Tolvaptan increases urinary water loss. Teach replacement of those losses and temporary interruption when volume depleted or unable to drink/compensate. Limited water access, vomiting/diarrhea, fever and heat-related losses support a sick-day plan. These locators support the planned pause question; no precise dose is checked here. |
| [K03 — ADPKD 2025][adpkd], intracranial aneurysm (ICA) | Ch. 6.1, **Recommendation 6.1.2 (1D)** and Practice Point 6.1.8; S150 / PDF 151. Imaging: Practice Point 6.1.10; S152 / PDF 153 | Screening is recommended with personal SAH or family ICA/SAH/unexplained sudden death, provided treatment eligibility and reasonable life expectancy. Informed lower-risk patients preferring screening should have access. Screening imaging favors noncontrast time-of-flight MRA; CTA is an alternative. This supports risk assessment and informed choice, not universal invasive angiography. Recommendation 6.1.2 is distinct from the similarly numbered history-taking Practice Point. |
| [K05 — AAV 2024 amended file][aav], ANCA monitoring | Section 9.2.3, Practice Point 9.2.3.1 **and accompanying explanation**; S93 / PDF 24 | Persistent/rising ANCA or negative-to-positive conversion can inform relapse-risk assessment. The explanation characterizes predictive value as modest and cautions against using ANCA measurements to guide an individual's treatment. The point says to consider the association; it does not justify automatic immunosuppression escalation on serology alone or treating ANCA as irrelevant. |
| [K06 — Lupus nephritis 2024][lupus], unsatisfactory response | Section 10.2.5.2, Practice Point 10.2.5.2.1 and Figure 12; S46 / PDF 47. Activity/chronic-damage explanation: Section 10.2.5.3, S47 / PDF 48 | Check adherence and adequate treatment exposure; consider repeat biopsy when chronicity or another diagnosis is suspected. Clinical changes/proteinuria may reflect ongoing inflammation or chronic damage. Tissue can clarify an uncertain distinction before treatment decisions. Repeat biopsy is conditional, not mandatory for every incomplete response; its Figure 12 step is not a separate graded recommendation. |
| [K06 — Lupus nephritis 2024][lupus], TMA | Section 10.3.1, Practice Point 10.3.1.1 and rationale; S47–S48 / PDF 48–49 | TMA describes vascular endothelial injury with multiple possible causes. The discussion includes TTP, antiphospholipid syndrome, complement-mediated disease and other causes. A tissue TMA pattern does not itself prove complement etiology; further etiologic assessment informs management. No treatment algorithm or complement-drug choice is adopted here. |
| [K16 — Transplant candidate 2020][transplant], infection | Section 10.1, Recommendation 10.1.1 (1C) and rationale; S55 / PDF 58 | Active infection generally requires treatment and delaying transplantation. The statement expressly excepts hepatitis C; its explanation allows selected transplantation before antimicrobial-course completion after appropriate clinical improvement. Do not convert the general rule into permanent exclusion or an exception-free completion requirement. |
| [K16 — Transplant candidate 2020][transplant], vaccination | Section 10.7, Recommendations 10.7.2 and 10.7.2.1 (both 1B); S61 / PDF 64 | Complete live-attenuated vaccine series before transplantation; allow at least four weeks between live vaccination and transplantation. This is the exact general timing locator, not Section 10.2 (colonization). Current vaccine products/schedules and recipient immunosuppression are outside this check. |
| [K16 — Transplant candidate 2020][transplant], treated cancer | Section 11.2: 11.2.2, S63 / PDF 66; 11.2.3.2 (2D) and 11.2.4, S64 / PDF 67 | Timing after potentially curative treatment depends on cancer type/stage; any recommended waiting period starts at treatment completion. Remission decisions involve oncology, transplant clinicians and the patient/caregivers. A previous treated cancer does not imply universal permanent exclusion. Cancer-specific waiting years were not audited; active malignancy is a separate eligibility question. |

**Access and baseline limits.** These are locator checks of the specified
2025/2024/2020 editions, not an exhaustive search for later evidence, every
corrigendum, retraction or replacement. The 2026 upload directory does not make
ADPKD or transplant-candidate guidance a 2026 edition. No requested locator
remained inaccessible. Unverified additions include precise tolvaptan dosing,
ICA screening/rescreening intervals, cancer-specific waiting durations, current
vaccine schedules and recipient drug regimens; do not infer them from this note.

The files carry CC BY-NC-ND 4.0 notices: ADPKD PDF 14, AAV PDF 11, lupus PDF 12,
transplant candidate PDF 4. Terms/boilerplate differ by file. Public access is not
blanket adaptation or redistribution permission. Only independently expressed
facts and citation locators are recorded; source prose, figures and algorithms
retain their own terms.

[adpkd]: https://kdigo.org/wp-content/uploads/2026/04/KDIGO-2025-ADPKD-Guideline.pdf
[aav]: https://kdigo.org/wp-content/uploads/2024/05/KDIGO-2024-ANCA-Vasculitis-Guideline-Update.pdf
[lupus]: https://kdigo.org/wp-content/uploads/2024/01/KDIGO_2024_Lupus_Nephritis_Guideline.pdf
[transplant]: https://kdigo.org/wp-content/uploads/2026/04/KDIGO-2020-Transplant-Candidate-Guideline.pdf

## Additional source/key QA — 2026-10-04

Additional check on **2026-10-04** (session UTC date confirmed at 21:12).
Assistant review only: assistant_reviewed: true; independent_human_review: false.
This table adds original fact/locator checks without changing the preceding
review or the first-increment note. Editions remain dated baselines.

| Primary source / key | Exact checked locator and pages | Original checked fact or unresolved scope |
| --- | --- | --- |
| [HD 2019][hd-qa], DOI 10.1186/s12882-019-1527-3: URR | Appendix 1, urea clearance; journal/PDF p. 26 | URR is 100 × (1 − post/pre). Synthetic pre-urea 20 and post-urea 6 give **70%**. This arithmetic does not itself establish overall dialysis adequacy. |
| [HD 2019][hd-qa]: larger-solute removal | Membrane flux and haemodiafiltration, rationale: Convective clearance; journal/PDF p. 12. Solute-clearance rationale also pp. 5–6. | Urea-based metrics describe a small solute. Equal urea removal need not imply equal larger-molecule removal; membrane pore properties and diffusion/convection affect the clearance spectrum. |
| [PD 2017][pd-qa], DOI 10.1186/s12882-017-0687-2: residual function | Section 3, Guideline 3.1 and Guideline 3.2.1; journal/PDF p. 9 | Assessment includes urinary and peritoneal clearance. Loss of the residual kidney contribution can lower total clearance despite an unchanged peritoneal prescription. |
| [ERKNet/ESPN dRTA 2021][drta-qa], DOI 10.1093/ndt/gfab171: diagnosis | Clinical diagnosis, p. 1586 / PDF 2; Metabolic acidosis, p. 1587 / PDF 3; Urine pH, p. 1588 / PDF 4 | The classic phenotype combines normal-gap hyperchloremic metabolic acidosis with impaired urine acidification. |
| dRTA synthetic high-gap key | Independent arithmetic, interpreted against the preceding diagnostic passages | With potassium omitted, Na − (Cl + bicarbonate) = 140 − (104 + 12) = **24 mmol/L**. This argues against isolated classic normal-gap RTA, while leaving mixed disorders possible. The numbers are synthetic, not a case in the publication. |
| dRTA: urease-positive urinary infection qualifier | **Scope check incomplete:** no exact gfab171 locator established | The accessible 12-page main paper did not contain this qualifier; searches for urease/infection/bacteria were negative. Diagnostic supplements were not retrieved. Do not describe the requested infection-confound claim as verified against this primary in this check. |
| [KDIGO GD 2021 remaining scope][gd-qa]: anti-PLA2R response | PP 3.3.4: S133 / PDF 138. Explicit precedence statement: Figure 30 caption, S130 / PDF 135. | Antibody disappearance can precede clinical remission. PP 3.3.4 supports longitudinal monitoring; the explicit temporal claim should cite the caption too, rather than attributing it solely to that practice point. |
| GD: focal FSGS biopsy limitation | Section 1.1, tissue evaluation: S89 / PDF 94. Chapter 6.1 diagnostic discussion: S162 / PDF 167. | Focal/segmental lesions can escape a very small tissue sample. Absence of sclerosis in three sampled glomeruli cannot reliably exclude FSGS. The direct sampling rationale is in 1.1, not 6.1 alone. |
| GD: bacterial infection-related GN | Section 7.1.2, PP 7.1.2.1: S173 / PDF 178; Figure 57: S174 / PDF 179 | Treat the underlying infection and provide kidney supportive care. Antibiotics need not reverse established postinfectious GN; do not promise that infection treatment alone guarantees kidney recovery. |
| GD: prophylactic anticoagulation | PP 1.7.1: S101 / PDF 106. MN-specific corroboration: PP 3.4.5, S138 / PDF 143. | Balance thrombosis risk against patient-specific serious-bleeding risk. Nephrotic syndrome alone is not an automatic prophylaxis instruction. |
| [KDIGO MBD 2017][mbd-qa]: turnover markers | Recommendation 3.2.3 (2B): printed p. 15 / PDF 16 | Markedly high or low PTH **or** bone-specific alkaline phosphatase helps predict bone turnover. This is predictive evidence, not a definitive histologic diagnosis. |
| MBD: phosphate-lowering decision | Recommendation 4.1.5: printed p. 16 / PDF 17; comparison-table rationale, printed p. 19 / PDF 20 | Decisions depend on progressive/persistent phosphate elevation. The explanatory note rejects preventive lowering from normal phosphate as the treatment goal. |

**Method and access limits.** Read the relevant authoring locators only. Used
primary web PDF text for HD, PD and MBD. The BMC HD HTML reader
returned HTTP 500; direct publisher-PDF HTTP requests for HD/PD returned a
JavaScript challenge as HTML despite HTTP 200, not valid source PDFs. Their
available web-reader PDFs supported the checks above; this is not live-access
or currency clearance.

The web reader failed on the GD PDF and the dRTA publisher page (HTTP 403 for
[the latter][drta-publisher-qa]). Read the official GD PDF and ERKNet-hosted
published dRTA article by public HTTP in memory with installed PyMuPDF 1.27.2.3;
both returned genuine PDFs. GD Figure 57 was inspected as a transient in-memory
render because its treatment cells were not extractable text. No source
original, figure or algorithm was saved. The unresolved dRTA supplement/urease
scope check remains visible and does not refresh a verified/current label.

The GD checks use only remaining Chapters 1/3/6/7; replaced topics are excluded.
No subsequent-evidence, correction-completeness, retraction or overall currency
clearance is claimed. Source access and source terms remain separate from the
licence of these original notes; no source redistribution permission is inferred.

[hd-qa]: https://link.springer.com/content/pdf/10.1186/s12882-019-1527-3.pdf
[pd-qa]: https://link.springer.com/content/pdf/10.1186/s12882-017-0687-2.pdf
[drta-qa]: https://www.erknet.org/fileadmin/Guidelines/Trepiccione_et_al.__2021__CPR_dRTA.pdf
[drta-publisher-qa]: https://academic.oup.com/ndt/article/36/9/1585/6259151
[gd-qa]: https://kdigo.org/wp-content/uploads/2024/05/KDIGO-2021-Glomerular-Diseases-Guideline_English_2024-Chapter-Updates.pdf
[mbd-qa]: https://kdigo.org/wp-content/uploads/2026/04/KDIGO-2017-CKD-MBD-Guideline.pdf

## Prepublication disposition

The authoring assistant read the ERKNet-hosted primary PDF in memory using
installed pypdfium2 on October 4, 2026, confirming Clinical diagnosis (printed
p1586) and Urine pH (p1588). No source original was saved. RN11-T11-004 was
rewritten before release to test whether a single urine pH can establish dRTA
without the systemic acid-base context. The unverified urease-positive-infection
detail is absent from that item, its options and its rationale. Normal serum
bicarbonate is not used to exclude every acidification defect.

Final-wave item locators now cite the checked printed pages for URR, residual
kidney clearance, membrane transport, FSGS sampling and CKD-MBD. RN11-T10-003
and the nephrotic-recovery case cite the Figure 30 caption as well as Practice
Point 3.3.4; infection-related GN cites Practice Point 7.1.2.1 and Figure 57.
The mixed nephrotic case cites both general and membranous thromboprophylaxis
locators. These changes affect only previously unpublished final-wave items;
released 1.0.0/1.0.1 item and citation snapshots are unchanged.
