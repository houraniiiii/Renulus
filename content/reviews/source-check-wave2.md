# M8 original content wave 2: bounded source check

2026-10-04 · Assistant source check (`assistant_reviewed`;
`independent_human_review: false`). Research evidence for original authoring,
not a pack approval or a permanent current-guidance label.

Read the worktree README, PROJECT_BRIEF, WORKSPACE and AGENTS, plus the newer
active-main SOURCES register, including K15, literature access, KDIGO rights and
correction/currency rules. Method: primary-source `web.run` discovery, then
read-only public HTTPS where the web reader failed; installed PyMuPDF 1.27.2.3
read the official PDF in memory. No source originals were saved.

**Urine eosinophils / AIN.** Muriithi, Nasr and Leung, CJASN 2013;8:1857–1862,
DOI `10.2215/CJN.01330213`, PMID 24052222, [PMC3817898][study]. The
[primary abstract in Europe PMC's PubMed record][study-record] describes a
retrospective adult study pairing Hansel-stained urine testing with native kidney
biopsy within one week. Its conclusions report eosinophils across several kidney
diagnoses and poor discrimination of AIN from acute tubular necrosis/other
diagnoses. This supports the draft's limited claim that urine eosinophils are
weak alone; numerical diagnostic performance was not re-audited.

**Correction scope verified.** [The full primary notice][notice], DOI
`10.2215/CJN.05270418`, PMID 29848506, PMCID PMC6032594, was published online
May 30, 2018 (issue July 6, 2018); [metadata explicitly links the original][notice-record].
It corrects one sentence in the second paragraph of Results: delete the
denominator phrase “of 566,” retaining the statement that 133 patients had AIN
on biopsy. The notice specifies no replacement diagnostic-performance table or
recalculated sensitivity/specificity. Do not derive an analytic-cohort prevalence
from the erroneous 133/566 wording. This resolves the correction's stated scope,
not an audit of every original number.

**KDIGO living donor locators.** [Official 2017 guideline][kdigo],
DOI `10.1097/TP.0000000000001769`; title page: August 2017. Below, PDF pages are
one-based physical pages; S-pages are printed journal pages. Facts are
paraphrased; the numbered statements remain a dated 2017 baseline.

| Recommendations | Checked teaching facts | Locator |
| --- | --- | --- |
| 2.1–2.3 | Private consent; confirm decision capacity; substitute consent only exceptionally after ethical/legal review. | Ch. 2, S27 / PDF 33 |
| 2.4–2.8 | Explain individual risks/uncertainty; confirm comprehension; allow deliberation; protect confidential withdrawal (2.7); assist communicating refusal (2.8). | S27 / PDF 33 |
| 5.1–5.4 | Use indexed GFR, initially eGFRcr; confirm using mGFR, creatinine clearance, creatinine–cystatin C eGFR, or repeat eGFRcr. | Ch. 5, S35 / PDF 41 |
| 5.6; 5.7; 5.8 | GFR ≥90 acceptable; 60–89 individualized by overall risk/program threshold; <60 excludes. Units: mL/min/1.73 m². | S36 / PDF 42 |
| 6.1–6.3 | Assess albumin, not total protein; screen with random ACR; confirm timed AER, or repeat ACR if unavailable. | Ch. 6, S42 / PDF 48 |
| 6.4; 6.5; 6.6 | AER <30 acceptable; 30–100 individualized; >100 excludes (mg/day). | S42 / PDF 48 |
| 15.1–15.2; 15.4–15.6 | Ask pregnancy plans/history; exclude pregnancy; future conception alone does not exclude; assess prior hypertensive pregnancy risks. | Ch. 15, S78 / PDF 84 |
| 15.8 | Avoid pregnancy from donor approval through recovery; confirm negative quantitative β-hCG immediately before donation. | S78 / PDF 84 |
| 15.9 (2C); 15.10–15.11 | Counsel about greater gestational hypertension/preeclampsia likelihood, long-term risks after prior hypertensive pregnancy, and reducing future pregnancy complications. | S78 / PDF 84 |

GFR/albumin thresholds concern the relevant kidney measure, not automatic
overall donor acceptance. Chapter 2 supports capable, voluntary donor choice;
its rationale defers minimum age to local law (S28 / PDF 34), rather than
establishing a universal adult-age rule. Listed recommendations are ungraded
except 15.9 (2C).

**Access/use limits and failures.** The web reader hit a PMC browser challenge
and rejected the KDIGO PDF above its 10 MB limit. Europe PMC fullTextXML returned
HTTP 500 for both study and correction. Direct PMC study access also returned a
challenge; the study check therefore used its primary abstract. The correction's
`?report=xml` route returned readable full HTML (HTTP 200), closing the scope
check. KDIGO initially returned HTTP 406; a normal browser User-Agent/Accept
request returned HTTP 200 and a readable 115-page PDF, 11,027,378 bytes.
SHA-256: `1548b463d047befbdcaf349a7a4c0df4969b85f03554a8abf6c41dc1195e0440`.

KDIGO's file-specific notice is CC BY-NC-ND 4.0 (S8 / PDF 14); the correction
carries ASN copyright, and metadata does not classify either article as OA.
Public readability is not redistribution permission. Only original fact notes
and citation locators belong here; third-party prose/figures retain their terms.
No exhaustive subsequent-evidence, retraction or supersession clearance was
performed; failed access checks do not refresh source currency.

[study]: https://pmc.ncbi.nlm.nih.gov/articles/PMC3817898/
[study-record]: https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DOI%3A10.2215%2FCJN.01330213&format=json&resultType=core
[notice]: https://pmc.ncbi.nlm.nih.gov/articles/PMC6032594/?report=xml
[notice-record]: https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=EXT_ID:29848506%20AND%20SRC:MED&format=json&resultType=core
[kdigo]: https://kdigo.org/wp-content/uploads/2017/07/2017-KDIGO-LD-GL.pdf
