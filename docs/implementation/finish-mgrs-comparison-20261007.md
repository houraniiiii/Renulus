# Eight-item MGRS diagnostic comparison — October 7, 2026

**Result:** the seven existing answer keys and the teaching case's diagnostic
propositions remain supported in this bounded comparison. **No changed key is
indicated.** The 2026 reading blocker is resolved through an official full-text
endpoint. One ancillary rationale clause still lacks direct support from the
compared passages; it is identified below. This is not an all-clear for content
issue 20, the whole T18 domain, or a new source/current-content release.

Reviewed **renulus-foundations 1.2.0** at integrated commit
`cb59beb20dcaa80abd129097018f7232e5c1085a`, in branch
`codex/final-mgrs-review-20261007`. Scope is exactly the seven questions and one
case citing `L01-IKMG-evaluation-2019`. Every question has item, family and key
version **1**; the case has version **1**. This is assistant source/claim review,
not independent human review. Only this new report is proposed for Git; the
parent owns source records and immutable content adoption. Installer manufacture
does not depend on this report.

## Recovered evidence and successful reading route

Read AGENTS, README, project brief and workspace instructions first. Recovered
the [October 7 source report](finish-source-currency-20261007.md), its linked
[October 5 report](finalise-source-currency.md), the eight integrated records and
the pack's existing source snapshot before making fresh requests. The October 5
report records a read of Table 9 and diagnostic discussion through
`https://oup.silverchair-cdn.com/article-minimal/8694705`; it did not read the full
consensus appendix. The October 7 source lane preserved that limited finding and
reported OUP/PMC reader failures and an author-repository 503. Its external
`evidence/sources/additional-findings.json` was recovered too. The already
resolved IKMG correction is inherited; it was not researched again here.

The recovered Silverchair URL returned a web-reader access error once in this
lane. Instead of repeating the failed OUP/PMC/repository routes, an ordinary
unauthenticated request to the official [Europe PMC full-text XML][new-xml]
returned **HTTP 200 on 2026-10-07 at 13:31:22 UTC**. The response identifies
**DOI 10.1093/ckj/sfag163, PMID 42338690, PMCID PMC13284707** (full-text version
`PMC13284707.1`), matching the
[publisher record][new-publisher] and [PubMed identity][new-pubmed]. Publication
is May 26, 2026; June is the issue date. This is Sprangers et al.'s *Executive
summary of the European consensus report on the diagnosis and treatment of
monoclonal gammopathy of renal significance*, Clinical Kidney Journal 19(6).
The XML carries the authors' **CC BY 4.0** notice. The appendix was not retrieved.

The old work is Leung et al., *The evaluation of monoclonal gammopathy of renal
significance*, Nature Reviews Nephrology 15, 45–59 (2019),
[DOI 10.1038/s41581-018-0077-4][old-doi]. The [UCL author-repository PDF][old-pdf]
already named in the pack's October 4 check note was freshly readable as text.
Page-image requests timed out; no visual/table-layout verification is claimed.
Old locators below therefore use **one-based physical pages of that 15-page
PDF**, with named sections, rather than inferred printed-page numbering.

New locators are exact section/table IDs in the successful XML. For example,
`sec2/p[4]` means the fourth **direct** paragraph child of section `sec2`, not
paragraphs nested in a table. `sec2` is Chapter 1, `sec3` Chapter 2, and `sec4`
the executive summary's Chapters 3–9 discussion. The LCPT paragraphs refer to
Chapter 8 of the full report but are read here in the executive summary.
PMC section links below are navigation targets; the fresh passage evidence is
the successful Europe PMC XML, not a claim that the challenged PMC reader worked.

## Exact eight-row comparison

**Unchanged—supported** means the existing keyed proposition, options and stated
scenario survive this comparison. **Unsupported** below concerns the explicitly
identified extra clause, not a reversed key. No source or key is changed by this
document. New-source statements in this table are concise paraphrases.

| Integrated item and assessed claim | Old claim and exact IKMG locator | New claim and exact 2026 locator | Disposition and consequence |
| --- | --- | --- | --- |
| **RN11-T02-001**, key **C**. PCR 3.8 g/g versus ACR 0.25 g/g calls for characterization of nonalbumin protein, without diagnosing a clone from the discrepancy. [Question file](../../content/packs/renulus-foundations/1.2.0/questions.json), line 3150. | Urine electrophoresis separates albumin and globular protein; immunofixation identifies immunoglobulins. *Monoclonal immunoglobulin testing*, PDF pp10–11. [Old][old-pdf] | ACR alone misses light-chain proteinuria; PCR and ACR/PCR guide additional urine evaluation. Chapter 1, **sec2/p[2]**. [New][new-ch1] | **Unchanged—supported; no changed key.** This is targeted evaluation of a specific discrepancy. The item does not order screening in all CKD or make a negative blood test exclusionary. |
| **RN11-T11-001**, key **A**. Normoglycemic glycosuria, hypophosphatemia and nonalbumin proteinuria favor a proximal reabsorptive defect; the pattern alone does not establish LCPT. Question file, line 4208. | LCPT has crystalline/noncrystalline forms; Fanconi can be partial. *Lesions with organized deposits*, PDF pp4–5; metabolic evaluation in **Fig. 4**, PDF p11. [Old][old-pdf] | LCPT can present with incomplete Fanconi features; adult Fanconi warrants serum/urine light-chain evaluation. **sec4/p[11]–p[13]**. [New][new-nonamyloid] | **Key unchanged—supported. Ancillary clause unsupported in this comparison:** the rationale's separate medication/acquired/inherited-cause instruction needs its own evidence or narrower wording. Neither the key nor the distractors require complete Fanconi or prove LCPT. |
| **RN11-T18-001**, key **C**. A small clone can produce nephrotoxic protein even below myeloma criteria; renal causality must be established. Question file, line 5036. | Renal injury can arise below malignancy thresholds; gammopathy and CKD may be unrelated. **Box 1**, PDF p3; *When to perform a renal biopsy*, PDF p9. [Old][old-pdf] | Nephrotoxic monoclonal protein can injure kidneys below malignancy criteria; CKD/MGUS may coexist incidentally. **sec1/p[1]; sec2/p[1]**. [New][new-intro] | **Unchanged—supported; no changed key.** No clone-burden cutoff, automatic causality, treatment indication or regimen is asserted by the key. |
| **RN11-T18-002**, key **D**. Immunoglobulin identity and ultrastructure can be necessary for lesion classification; light microscopy alone is insufficient. Question file, line 5093. | Morphology, immunostaining, ultrastructure and clinical data are integrated. *Renal biopsy evaluation*, PDF pp9–10; **Fig. 4**, PDF p11. [Old][old-pdf] | LM/IF/EM remain complementary; EM is advised, with lesion-specific necessity. **sec2/p[3]; Table 2 (tbl2)**. [New][new-ch1] | **Unchanged—supported; no changed key.** The stem concerns evaluation of a biopsy and says “often”; the answer says “can be essential.” It does not mandate biopsy or EM without qualification for every patient. |
| **RN11-T18-003**, key **A**. A modest FLC-ratio shift in advanced CKD needs assay, renal-function and reference-context interpretation with other findings. Question file, line 8264. | Renal clearance and assay differences affect FLC interpretation. *Monoclonal immunoglobulin testing*, PDF pp11–12. [Old][old-pdf] | FLC interpretation depends on eGFR and assay, including calibrator drift and proposed revised intervals. **sec2/p[4]; Table 4 and footnote (tbl4, tbl4fn1); Table 9 (tbl9)**. [New][new-ch1] | **Unchanged—supported; no changed key.** No numeric interval is embedded in this question. Its context-dependent answer does not inherit an old fixed reference range. Do not add a number to this item merely to update its citation. |
| **RN11-T18-004**, key **B**. Amyloid plus a small circulating monoclonal component requires tissue typing and clonal correlation. Question file, line 8324. | Ancillary amyloid typing distinguishes deposit constituents and misleading immunoglobulin staining. *Renal biopsy evaluation*, **Table 2**, PDF p10. [Old][old-pdf] | Concurrent MIg and Congo-red positivity do not establish AL; type the tissue protein. Chapter 2, **sec3/p[3]**. [New][new-amyloid] | **Unchanged—supported; no changed key.** Appropriate typing with specialized methods where needed remains the best answer; neither a serum spike nor Congo red alone settles precursor identity. |
| **RN11-T22-004**, key **B**. Negative routine IF does not exhaust evaluation of a suspected deposition process; additional pathology methods can clarify it. Question file, line 8804. | Protease IF and EM can reveal deposits missed by routine methods. *Renal biopsy evaluation*, PDF pp9–10; **Table 2**, PDF p10. [Old][old-pdf] | Negative routine IF can require pronase-treated tissue and EM; light-chain restriction alone does not prove monoclonality. **sec2/p[3]; tbl2; sec4/p[11]; tbl9**. [New][new-ch1] | **Unchanged—supported; no changed key.** The answer requests selected additional evaluation; it does not turn restricted staining into proof of a pathogenic clone or claim EM establishes the hematologic clone. |
| **RN11-CASE-PROXIMAL**, teaching case, **no answer key**. Stage 1: proximal losses and PCR 2.9/ACR 0.18 g/g. Stage 2: investigate a small monoclonal component while retaining incidental gammopathy. Stage 3: discuss tissue contribution, complementary methods and procedural risk. [Case file](../../content/packs/renulus-foundations/1.2.0/cases.json), line 1454. | Stage 1: LCPT/testing, PDF pp4–5, 10–11. Stage 2: definition/incidental gammopathy, pp3, 9. Stage 3: biopsy evaluation, pp9–11; older diagnostic wording emphasizes biopsy. [Old][old-pdf] | Prior rows support stages 1–3. Complete Fanconi plus MIg and abnormal serum/urine FLC can establish LCPT without biopsy, except atypical features such as severe proteinuria/rapid deterioration. **sec4/p[12]**, alongside **sec2/p[2]–p[3]**. [New][new-nonamyloid] | **Teaching propositions unchanged—supported, with a named boundary.** The case neither establishes complete Fanconi and abnormal serum/urine FLC nor mandates biopsy. A small component alone does not satisfy the exception. Do not infer whether 2.9 g/g satisfies “severe” here; that is not resolved by the passage. Any later extension deciding biopsy must teach the exception explicitly. |

## Diagnostic contrasts and remaining action

The 2026 Chapter 1 discussion rejects universal CKD monoclonal screening and
routine biopsy for MGUS/CKD; negative serum testing cannot exclude MGRS
(`sec2/p[1], p[3]–p[4]`). [Primary passage][new-ch1] These distinctions do not
reverse the selected investigation questions: none asks for population-wide
screening, unconditional biopsy or exclusion after negative serum testing.

The FLC, negative-IF/monoclonality and LCPT-biopsy contrasts are explicitly
accounted for in the relevant rows. In particular, the case should not inherit
an unconditional biopsy rule from an older general locator or from Table 9
read without the specific LCPT discussion. The existing case avoids that rule.
This is a comparison of the actual text, not permission to add a diagnostic
algorithm or clone-directed treatment.

**The exact remaining source-support issue is RN11-T11-001's non-key sentence:**
“Review medications and acquired/inherited causes.” Its localization key is
supported, but the compared MGRS passages do not establish that wider
differential instruction. This is a scope-of-evidence constraint, not a current
reader failure and not evidence that the sentence is false. The parent can
either attach a directly checked Fanconi differential source in a future
immutable release, or narrow the rationale to the supported proposition, for
example: *The combined findings suggest proximal solute loss. Investigate a
possible light-chain cause; these findings alone do not establish LCPT.* No
additional differential research or pack edit was performed in this lane.

For the parent's content disposition: **zero changed keys required; seven
supported retained keys; one supported retained teaching case; one ancillary
rationale clause needing source support or narrowing.** No assessed proposition
is left unsupported solely because the new source was unreadable. The previous
access blocker can therefore close, while the named rationale action remains.
The 2026 source and item-specific locators still need parent-owned adoption;
this report does not refresh the pack's October 4 source snapshot or its review
flags. It does not close general source currency, full-appendix interpretation,
all MGRS pathology, treatment, or content issue 20's broader clinical scope.

## Evidence and handoff boundary

External evidence directory: `C:/rn-finish-20261007/evidence/mgrs/`.

- `access.json`: successful endpoint, HTTP result and UTC retrieval time.
- `sfag163-europepmc.xml`: official response; SHA-256
  `d405af8506f148513c3586d81933b0b74105b79ec76a08cfced2a7713e69c980`.
- `diagnostic-passages.json`: exact XPath-indexed passages used for comparison,
  retained externally with the original XML's source and rights context.
- `eight-items.json`: exact seven questions and one case extracted from 1.2.0,
  including original options, rationales, stages and source locators.
- `input-hashes.json`: read-input identities, including the integrated pack.
- `research-receipt.json`: dated access outcomes, locator map and dispositions.
- `commit-receipt.json`: final commit and working-tree handoff evidence.

Question-file SHA-256:
`c37f09788245a2b20690b38bd42bd86c86524a27c5271f583d1d78ab93832c6d`.
Case-file SHA-256:
`517cda7650421614fb316d0be523112bfd3891ac55954724017926d2a51645a9`.
Source-file SHA-256:
`3296c655c34dc238b9d4c9a6cff1da1bbe5f0d513a9a5ed3c6c766f1b9718e70`.

Only the authorized report is committed. Handoff checks are the exact eight
record identities, input hashes, `git diff --check`, branch and working-tree
status. No application tests, content imports, model/provider calls, native
operations, GitHub activity, runtime changes, source-register edits or pack
edits are part of this work. Primary bodies remain outside Git. The research
skill's primary-source/report method was applied directly within this bounded
lane; no additional model/agent work was started.

[old-doi]: https://doi.org/10.1038/s41581-018-0077-4
[old-pdf]: https://discovery.ucl.ac.uk/10064523/1/s41581-018-0077-4.pdf
[new-publisher]: https://academic.oup.com/ckj/article/19/6/sfag163/8694705
[new-pubmed]: https://pubmed.ncbi.nlm.nih.gov/42338690/
[new-xml]: https://www.ebi.ac.uk/europepmc/webservices/rest/PMC13284707/fullTextXML
[new-intro]: https://pmc.ncbi.nlm.nih.gov/articles/PMC13284707/#sec1
[new-ch1]: https://pmc.ncbi.nlm.nih.gov/articles/PMC13284707/#sec2
[new-amyloid]: https://pmc.ncbi.nlm.nih.gov/articles/PMC13284707/#sec3
[new-nonamyloid]: https://pmc.ncbi.nlm.nih.gov/articles/PMC13284707/#sec4
