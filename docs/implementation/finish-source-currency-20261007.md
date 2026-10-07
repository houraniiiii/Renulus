# Source-currentness finish review — October 7, 2026

**Scope:** integration base `ea73f4dcdb90f4f67e0fb2d948939cc213f95ffd`,
`renulus-foundations` **1.1.2**, 47 source records, 178 questions, 38 cases,
27 `update_sources` cells and four `objective_mismatch` holds. This is a dated
evidence/decision report under the single register [SOURCES.md](../SOURCES.md).
Only that register and this report belong to the source lane. No pack, mapping,
original source file, rights record or previous receipt was changed.

## What this review resolves

The October 5 report's unavailable publisher checks now have successful
Crossmark results for 14 publications. Two previously unrecorded relationships
were recovered: the IKMG Figure 1 correction and the ISTH diagnostic PLASMIC
score correction. Known AAV, CKD-MBD and urine-eosinophil notices now have
specific correction text and an item-scope comparison. ESE, CUAJ, ERKNet and
ISPD official publication routes narrow previously unresolved edition questions.
Hyperkalaemia migration is already complete in 1.1.2; repeating it is unnecessary.

These results permit **bounded metadata/correction-impact decisions** below.
They do not certify every recommendation in a work, establish complete topic
coverage or change `needs_currency_review` in an immutable pack. No retrieved
record identified a retraction of a baseline; this is a bounded observation,
not proof of absence. A Crossmark current record is a publisher status result,
not evidence that a clinical guideline is the newest for every scope.

Recovered before fresh checking:

- [October 5 source report](finalise-source-currency.md), including failed
  publisher reads and the bounded NLM query's known false negatives.
- [October 4 locator review](../../content/reviews/source-check-wave2-final.md).
- [1.1.2 receipt](../../content/reviews/renulus-foundations-1.1.2.json),
  [required cells](../../content/required-cells/renulus-foundations-1.1.2.json),
  [launch mapping](../../content/mappings/esen-eph-2026-10-05-launch1.json), and
  [audit](finalise-audit-699938f2.md).

**Check date for all fresh results below: 2026-10-07.** Publication dates are
separate. Direct public reads and indexed primary-source text are identified
where access differs. Restricted readers were not bypassed. No source corpus
was downloaded/imported, and no private profile or provider was used. Prior
locator reviews retain their original dates and assistant-review status.

## Correction findings the content lane can use now

| Work / exact notice | Newly established correction scope | Existing item comparison and action |
| --- | --- | --- |
| K05 AAV: [July 2024 full-guideline corrigendum](https://doi.org/10.1016/j.kint.2024.04.003), read via [KDIGO's public notice PDF](https://kdigo.org/wp-content/uploads/2024/01/KDIGO-2024-ANCA-Vasculitis-Guideline-Corrigendum.pdf); [February 2025 corrigendum](https://doi.org/10.1016/j.kint.2024.10.004), text recovered from the [author institution publication record](https://ohiostate.elsevierpure.com/en/publications/corrigendum-to-kdigo-2024-clinical-practice-guideline-for-the-man-2/) | July: Figures 6–8/13 and PP 9.3.1.9/9.3.3.1, including the plasma-exchange groups' conjunction and removal of a severity parenthetical. February: supporting ARR for SCr >5.7 mg/dL changes 6% to 16%; Figure 12 associates **lower**, not higher, creatinine with relapse. The author record says the article was corrected online. | `RN-AAV-001`, `RN11-T16-001`, `RN-CASE-VASCULITIS` cite diagnosis PP 9.1.1; `RN11-T16-003` cites monitoring PP 9.2.3.1. They do not teach the corrected ARR, creatinine direction or induction algorithms. No key reversal identified from these notices. Attach both relationships in the next source revision. Exact retained-PDF incorporation is unverified; the May 2024 path alone cannot prove incorporation of February 2025. Executive-summary DOI `.2024.04.004` is a separate notice. |
| K13 CKD-MBD: [full-guideline erratum](https://doi.org/10.1016/j.kisu.2017.10.001), [primary notice](https://pmc.ncbi.nlm.nih.gov/articles/PMC6341011/), online 2017-11-17 / December 2017 issue | Supplementary Table S21, Di Iorio 2012/2013 comparator, is calcium **carbonate**, not acetate. The notice states the supplement was amended and work-group conclusions did not change. | Both K13 records cite recommendations 3.1.4, 3.2.3, 4.1.1, 4.1.3/6, 4.1.5, 4.2.1/2, not the trial comparator. The previously unknown correction's scope is now resolved; no existing-key change indicated by it. Original-file incorporation remains separate. DOI `10.1016/j.kint.2017.10.001` concerns the executive summary, not this full guideline. |
| Urine eosinophils: [2018 correction](https://doi.org/10.2215/CJN.05270418), [primary notice](https://pmc.ncbi.nlm.nih.gov/articles/PMC6032594/), online 2018-05-30 / issue 2018-07-06 | Indexed primary notice removes an erroneous denominator from the Results sentence identifying 133 biopsy-proven AIN cases. It does not report a sensitivity/specificity recalculation. Direct PMC reader challenged. | `RN11-T11-002` teaches that a negative urine-eosinophil test does not exclude AIN and gives no cohort count or accuracy percentage. No key reversal identified. Keep the study dated; it is not treatment evidence. |
| **New relationship:** IKMG [author correction](https://doi.org/10.1038/s41581-018-0102-7), [publisher notice](https://www.nature.com/articles/s41581-018-0102-7), online 2018-12-19 / February 2019 issue | Figure 1 key changes “Amyloid microtubules” to “Microtubules.” The original DOI's Crossmark lists this update. | Read the pack's seven questions `RN11-T02-001`, `RN11-T11-001`, `RN11-T18-001`–`004`, `RN11-T22-004`, and `RN11-CASE-PROXIMAL`. None reproduces the label. Biopsy/amyloid questions require tissue typing rather than treating a coincident clone as causal. Add the correction relationship; no key change follows from this figure-label notice. The separate 2026 consensus comparison remains below. |
| **New relationship:** ISTH diagnostic [erratum](https://doi.org/10.1111/jth.15304), [publisher text](https://onlinelibrary.wiley.com/doi/10.1111/jth.15304), online 2021-04-20 / May 2021 issue | Table 1's intermediate PLASMIC likelihood row should refer to score **5**, not 6; the high-score row remains 6–7. Confirmed by indexed publisher notice and Crossmark relationship. | `RN11-T15-001`, `RN11-T15-002`, `RN11-T15-004`, `RN11-T23-002`, `RN11-CASE-TMA` do not calculate PLASMIC or use that row. They cover syndrome recognition, pretreatment ADAMTS13, inhibitor interpretation and plasma-exchange mechanism. No key reversal from this notice. Add the relationship; keep the 2025 treatment update distinct. |
| Hyponatraemia: [July 2014 correction](https://doi.org/10.1530/EJE-13-1020e), [publisher record](https://academic.oup.com/ejendo/article/171/1/X1/6661472) and [ESE directory](https://www.ese-hormones.org/publications/directory/ese-clinical-guideline-for-the-management-of-hyponatraemia/) | ESE explicitly links the March 2014 guideline and July correction. Indexed publisher notice corrects a Table 7 respiratory-disorder description and the SI-unit presentation of the hyperglycaemia sodium equation. | Current sodium items use diagnostic/treatment sections 6.2, 6.3 and 7; `RN11-T03-004` concerns hyperglycaemic hyponatraemia but does not calculate that equation. Do not add a calculation from OCR. No later same-scope final was identified in the checked ESE catalogue. This narrows the old unresolved edition claim; it does not re-review every sodium-treatment number. |
| ISPD peritonitis: [2023 correction](https://doi.org/10.1177/08968608231166870), online 2023-03-29; [2024 correction](https://doi.org/10.1177/08968608241251453), online 2024-04-21 | Indexed publisher notices: 2023 Figure 8 amends the enterococcal algorithm; 2024 Table 1 corrects the refractory-peritonitis effluent threshold from an erroneous 100 to **0.1 × 10^9/L**, after five days of appropriate therapy. | Pack's source ID already includes `corrected`; retain **both** notices. The 1.1.2 review covers initial peritonitis recognition, not the enterococcal regimen or refractory-outcome algorithm. No new treatment key is established here. |

For these comparisons, “no key reversal identified” means the stated correction
does not intersect the existing assessed fact. It is not a new full-guideline
review or a right to redistribute the corrected source.

## Complete source-record disposition

Every pack source ID appears below. “Current” in a **Crossmark** column means
that exact deposited publication record returned *Document is current* on the
check date. “Unavailable” is an unknown result, never a negative correction or
retraction search. The [KDIGO catalogue](https://kdigo.org/guidelines/) and each
linked topic establish final/draft/chapter identity separately.

| Pack source IDs | Official edition / status evidence | Publisher/correction disposition and scope |
| --- | --- | --- |
| `K01-2024`, `K01-2024-expansion`, `K01-2024-launch-locators` | [CKD topic](https://kdigo.org/guidelines/ckd-evaluation-and-management/): 2024 final; focused Chapter 3 update underway. | [Full-guideline Crossmark](https://crossmark.crossref.org/dialog/?doi=10.1016/j.kint.2023.10.018): current. Close previously unread publisher status for this edition; no draft substitution. |
| `K02-2026`, `K02-2026-launch-locators` | [Anemia topic](https://kdigo.org/guidelines/anemia-in-ckd/): January 2026 final. | [Crossmark](https://crossmark.crossref.org/dialog/?doi=10.1016/j.kint.2025.06.006): current. The separate ERBP-commentary correction `10.1093/ndt/gfag192` identified in the October 5 report is not a correction to this guideline; not re-read here. |
| `K03-2025`, `K03-2025-expansion` | [ADPKD topic](https://kdigo.org/guidelines/autosomal-dominant-polycystic-kidney-disease-adpkd/): 2025 final. | [Crossmark](https://crossmark.crossref.org/dialog/?doi=10.1016/j.kint.2024.07.009): current. Close previously unread publication-status query. |
| `K05-2024-amended`, `K05-2024-expansion` | [AAV topic](https://kdigo.org/guidelines/antineutrophilic-cytoplasmic-antibody-anca-associated-vasculitis-aav/): 2024, replacing GD Chapter 9. | [Crossmark](https://crossmark.crossref.org/dialog/?doi=10.1016/j.kint.2023.10.008): updates available, July 2024 and February 2025. Scoped impact above; preserve amended-file and notice identities separately. |
| `K06-2024`, `K06-2024-expansion` | [Lupus topic](https://kdigo.org/guidelines/lupus-nephritis/): 2024, replacing GD Chapter 10. | [Full-guideline Crossmark](https://crossmark.crossref.org/dialog/?doi=10.1016/j.kint.2023.09.002): current. Do not confuse its executive-summary DOI. |
| `K08-2021-remaining`, `K08-2021-remaining-expansion` | [GD topic](https://kdigo.org/guidelines/gd/): 2021 remaining chapters 1/3/5/6/7/8/11; IgAN/IgAV and childhood NS 2025 replace 2/4, AAV and lupus 2024 replace 9/10. | [Crossmark](https://crossmark.crossref.org/dialog/?doi=10.1016/j.kint.2021.05.021): current publication record **despite chapter replacement**. Preserve exclusions of old summaries, figures and tables for replaced topics. |
| `K09-2022`, `K09-2022-expansion` | [Diabetes topic](https://kdigo.org/guidelines/diabetes-ckd/): explicitly identifies 2022 as current guideline; 2026 draft under revision after review. | [Crossmark](https://crossmark.crossref.org/dialog/?doi=10.1016/j.kint.2022.06.008): current. Draft and incretin commentary are separate evidence types. |
| `K10-2012`, `K10-2012-expansion` | [AKI/AKD topic](https://kdigo.org/guidelines/acute-kidney-injury/): 2012 final; 2026 draft preparing for publication. The misleading 2021 link is not a new final. | Final identity checked; comprehensive publisher correction status not closed. Keep foundational mechanisms dated. New anticoagulation/treatment content needs exact current-scope support; a draft is not the replacement. |
| `K11-2021`, `K11-2021-expansion` | [BP topic](https://kdigo.org/guidelines/blood-pressure-in-ckd/): 2021 final. | [Full-guideline Crossmark](https://crossmark.crossref.org/dialog/?doi=10.1016/j.kint.2020.11.003): current. Overlap with CKD 2024 and dialysis BP remains scope-specific. |
| `K13-2017`, `K13-2017-expansion` | [CKD-MBD topic](https://kdigo.org/guidelines/ckd-mbd/): 2017 update. | [Crossmark](https://crossmark.crossref.org/dialog/?doi=10.1016/j.kisu.2017.04.001): December 2017 erratum. Comparator correction and present-item impact resolved above. |
| `K15-2017-donor` | [Donor topic](https://kdigo.org/guidelines/living-kidney-donor/) and [publication identity](https://pubmed.ncbi.nlm.nih.gov/28742762/): 2017 final. | [Crossmark](https://crossmark.crossref.org/dialog/?doi=10.1097/TP.0000000000001769): data unavailable. Latest listed KDIGO donor final is established; complete correction status/current donor-policy review is not. |
| `K16-2020`, `K16-2020-expansion` | [Candidate topic](https://kdigo.org/guidelines/transplant-candidate/): 2020 final. | [Crossmark](https://crossmark.crossref.org/dialog/?doi=10.1097/TP.0000000000003136): data unavailable. Candidate scope cannot stand for post-transplant aftercare. Objective repair below does not require a fabricated new source. |
| `G02-hyperkalemia-2023` | Historical snapshot retained in 1.1.2; no active item reference in that release. | Preserve identity and past-attempt provenance. **Already replaced for active teaching references**, not a new blocker. |
| `G02-hyperkalemia-2026-07` | [Active UKKA route](https://www.ukkidney.org/health-professionals/guidelines/treatment-acute-hyperkalaemia-adults-0): page publication 2023-12-19; linked file updated July 2026; review 2026-10-19. | The July file and page date are different metadata. Five questions and one case already migrated in 1.1.2. Review is not overdue on October 7. Detailed changes remain the October 5 content receipt's work, not a fresh re-review. |
| `G01-hyponatremia-2014`, `G01-hyponatremia-2014-expansion` | [ESE directory](https://www.ese-hormones.org/publications/directory/ese-clinical-guideline-for-the-management-of-hyponatraemia/): March 2014 final and July 2014 correction. | Known correction relationship and catalogue route resolved above. No later same-scope final identified there; no claim of exhaustive literature currency. |
| `G01-ERKNet-dRTA-2021` | [ERKNet dRTA page](https://www.erknet.org/guidelines-pathways/tubulopathies/distal-renal-tubular-acidosis) explicitly lists the 2021 practice points, DOI `10.1093/ndt/gfab171`, journal 36:1585–1596. Indexed official text read; direct reader returned 403. | [Crossmark](https://crossmark.crossref.org/dialog/?doi=10.1093/ndt/gfab171): unavailable. The official listed edition is now identified; all-notice/current-treatment closure remains unproved. |
| `G02-haemodialysis-2019` | [UKKA HD page](https://www.ukkidney.org/health-professionals/guidelines/haemodialysis): publication 2019-07-01, review 2024-07-01. | [Crossmark](https://crossmark.crossref.org/dialog/?doi=10.1186/s12882-019-1527-3): current, online 2019-10-17. Clinical review **overdue**. Retain scoped adequacy/clearance evidence; modern access/infection claims use their own sources. |
| `G02-peritoneal-dialysis-2017` | [UKKA catalogue](https://www.ukkidney.org/health-professionals/guidelines/guidelines-commentaries?page=2): publication 2017-06-01, review 2022-06-01. | [Crossmark](https://crossmark.crossref.org/dialog/?doi=10.1186/s12882-017-0687-2): current, online 2017-11-16. Clinical review **overdue**; current infection scope has separate ISPD records. |
| `G02-pregnancy-renal-2019` | [UKKA pregnancy page](https://www.ukkidney.org/health-professionals/guidelines/pregnancy-and-renal-disease): publication 2019-09-01, review 2024-09-01. | [Crossmark](https://crossmark.crossref.org/dialog/?doi=10.1186/s12882-019-1560-2): current, online 2019-10-31. Clinical review **overdue**. Do not refresh drug/obstetric recommendations from publication status alone. |
| `L01-CUA-stones-2022` | [CUAJ guideline catalogue](https://cuaj.ca/index.php/journal/guidelines): June 2022 medical-stone guideline; [article](https://cuaj.ca/index.php/journal/article/view/7872) publication 2022-03-11, final issue 16(6):175–188. | Publisher catalogue now directly readable. Final and EPUB draft are separate links. No newer same-topic CUA final identified there; full notice completeness not established. [EAU Urolithiasis](https://uroweb.org/guidelines/urolithiasis) is a separate 2026 full update, not evidence CUA has retired this work. |
| `L01-CUA-ureteral-2021` | [CUAJ catalogue](https://cuaj.ca/index.php/journal/guidelines): December 2021 full text; [article](https://cuaj.ca/index.php/journal/article/view/7581) publication 2021-08-24, issue 15(12):E676–E690. | Same catalogue/notice limits as stones. Reproduction requires CUA's permission under the catalogue statement; no permission inferred from successful reading. Modern EU treatment comparison remains separate. |
| `L01-IKMG-evaluation-2019` | Original [DOI](https://doi.org/10.1038/s41581-018-0077-4), 2019 issue; [Crossmark](https://crossmark.crossref.org/dialog/?doi=10.1038/s41581-018-0077-4) lists December 2018 correction. | New correction scope resolved above. [European consensus executive summary](https://pubmed.ncbi.nlm.nih.gov/42338690/), DOI `10.1093/ckj/sfag163`, published 2026-05-26 / June issue, is distinct new diagnostic/treatment evidence. See remaining comparison below; no formal retirement of IKMG established. |
| `L01-ISTH-TTP-diagnosis-2020` | [ISTH official directory](https://www.isth.org/page/TTPGuidelines?hhsearchterms=%22guidelines%22) lists 2020 diagnosis/treatment separately and the 2025 focused treatment update. | [Crossmark](https://crossmark.crossref.org/dialog/?doi=10.1111/jth.15006): May 2021 erratum, impact above. [June 18, 2025 ISTH update announcement](https://www.isth.org/news/703888/ISTH-publishes-new-update-to-guidelines-for-TTP-management-.htm) does not establish a new diagnostic edition. |
| `L01-urine-eosinophils-2013` | 2013 diagnostic study plus [2018 correction](https://doi.org/10.2215/CJN.05270418). | Specific correction wording now recovered above. Retain limited diagnostic-discrimination scope and historical date. |
| `G07-NG112-2024-launch` | [NICE NG112](https://www.nice.org.uk/guidance/ng112): published 2018-10-31, updated/reviewed 2024-12-12. Public overview read successfully using unauthenticated HTTP after web-reader failure. | 2024 changes include methenamine recommendations; existing 1.1.2 receipt covers selected recurrent-UTI locators. No new unrestricted NICE processing rights. |
| `G01-Alport-2024-launch` | [Publisher issue](https://academic.oup.com/ndt/issue/40/6): 2024 guideline, 2025 journal issue 40(6):1091–1106, DOI `10.1093/ndt/gfae265`; [ERKNet-hosted author document](https://www.erknet.org/fileadmin/Guidelines/Torra_et_al.__2024__Diagnosis__management_and_treatment_of_the_Alport_syndrome.pdf). | [Crossmark](https://crossmark.crossref.org/dialog/?doi=10.1093/ndt/gfae265): unavailable. Preserve distinction from the version of record used for 1.1.2's Q4/Q6/Q8/Q9/Q16/Q19 review. Publisher notice completeness unverified. |
| `L01-ISPD-peritonitis-2022-corrected-launch` | [ISPD directory](https://ispd.org/guidelines/) now readable: adult peritonitis 2022, distinct from pediatric 2024. | [Crossmark](https://crossmark.crossref.org/dialog/?doi=10.1177/08968608221080586): both 2023 and 2024 corrections. Initial diagnosis scope retained; corrections detailed above. |
| `L01-ISPD-catheter-2023-launch` | [ISPD directory](https://ispd.org/guidelines/): catheter infection 2023. | [Crossmark](https://crossmark.crossref.org/dialog/?doi=10.1177/08968608231172740): current, online 2023-05-26. Later teaching, nutrition and loss-from-PD documents have different scopes. |
| `G02-HD-access-2025-launch` | [UKKA catalogue](https://www.ukkidney.org/health-professionals/guidelines/guidelines-commentaries): access guideline 2023, review 2028-04-05; 2025 journal publication of this guideline. | [Crossmark](https://crossmark.crossref.org/dialog/?doi=10.1186/s12882-025-04374-y): current, online 2025-08-14. Keep guideline and publication dates separate. Does not cover all dialysis-unit operations. |
| `L01-BK-consensus-2024-launch` | [Original publication](https://pubmed.ncbi.nlm.nih.gov/38605438/): online 2024-04-12 / September 2024 issue. | [Crossmark](https://crossmark.crossref.org/dialog/?doi=10.1097/TP.0000000000004976): current. Linked correspondence is not an erratum. Scope reviewed in 1.1.2 remains narrower than all viral transplant care. |
| `L01-US-MEC-2024-launch` | [CDC's current US MEC hub](https://www.cdc.gov/contraception/hcp/usmec/index.html) retains 2024; [MMWR](https://www.cdc.gov/mmwr/volumes/73/rr/rr7304a1.htm), 2024-08-08, includes CKD. | [Crossmark](https://crossmark.crossref.org/dialog/?doi=10.15585/mmwr.rr7304a1): unavailable. Current agency edition identified; no complete notice clearance. US supplementary evidence, not an EU-wide rule or complete sexual-health source. |
| `G07-NG43-2016-launch` | [NICE NG43](https://www.nice.org.uk/guidance/ng43): published 2016-02-24; current overview read via unauthenticated HTTP. | No new update/review date was displayed in the checked overview. Preserve the dated transition scope and the 1.1.2 locator review; do not invent surveillance clearance. |
| `G07-NG31-2015-launch` | [NICE NG31](https://www.nice.org.uk/guidance/ng31): published 2015-12-16; current overview covers the last 2–3 days of life. | No new update/review date displayed. Its last-days scope must not replace the broader conservative-kidney-care pathway. |
| `L01-AIN-treatment-review-2025-launch` | [Publication](https://pubmed.ncbi.nlm.nih.gov/40814598/), 2025 / August issue, DOI `10.1016/j.ekir.2025.05.009`. | [Crossmark](https://crossmark.crossref.org/dialog/?doi=10.1016/j.ekir.2025.05.009): current. Systematic review, not guideline; retained treatment uncertainty does not justify universal steroid advice. |

## Disposition of all 27 currency-review cells

These are instructions for the next content review, not changes to pack 1.1.2.
Each row accounts for its exact `update_sources.source_ids` via the source table
above. All dates/statuses refer to the bounded October 7 check. **Metadata
resolved** means the listed final and publisher status are checked, with known
notice impact assigned for that cell's used scopes; it does not mean a human-reviewed current-content
flag, complete coverage, or perpetual freshness. Named remaining gaps are not
silently converted into success.

| Cell | Exact contributing source records | Disposition for content owner |
| --- | --- | --- |
| T01 | `G02-pregnancy-renal-2019`, `K01-2024-expansion`, `K01-2024-launch-locators`, `K09-2022-expansion` | CKD/diabetes final and publication metadata resolved. Pregnancy review remains overdue; keep its context and date separate. |
| T02 | `G01-Alport-2024-launch`, `G07-NG112-2024-launch`, `K01-2024`, `K01-2024-expansion`, `K08-2021-remaining-expansion`, `K11-2021-expansion`, `K15-2017-donor`, `L01-BK-consensus-2024-launch`, `L01-IKMG-evaluation-2019` | CKD/BP/remaining-GD/BK/NG112 edition evidence resolved; attach IKMG correction and compare 2026 MGRS evidence. Alport/donor notice status remains unavailable. |
| T03 | `G01-hyponatremia-2014`, `G01-hyponatremia-2014-expansion` | Listed edition and known correction scope resolved through ESE/publisher evidence. Preserve the 2014 + correction identity; no new sodium calculation or treatment review claimed. |
| T04 | `G01-ERKNet-dRTA-2021`, `G02-hyperkalemia-2026-07`, `K01-2024`, `L01-CUA-stones-2022` | July 2026 hyperkalaemia migration already complete; CKD status checked. ERKNet/CUA now identify listed editions; full notice/current-treatment closure remains limited. |
| T05 | `G01-ERKNet-dRTA-2021`, `K13-2017`, `K13-2017-expansion`, `L01-CUA-stones-2022` | CKD-MBD comparator correction impact resolved for current facts. dRTA/CUA listed editions identified; notice/current-treatment gaps remain. |
| T06 | `K01-2024`, `K10-2012`, `K10-2012-expansion`, `L01-CUA-ureteral-2021` | CKD status resolved; AKI remains 2012 final while 2026 is draft. CUA ureteral catalogue recovered. Keep the older-mechanism and EU-treatment comparison scopes explicit. |
| T07 | `G01-hyponatremia-2014`, `G02-hyperkalemia-2026-07`, `K10-2012-expansion` | Hyperkalaemia migration already complete and ESE correction resolved. AKI final/draft identity resolved; complete AKI notice status remains unproved. |
| T08 | `K01-2024`, `K01-2024-expansion`, `K02-2026`, `K02-2026-launch-locators`, `K11-2021-expansion` | Metadata resolved for CKD 2024, anemia 2026 and BP 2021. Retain inherited locator reviews; no ERBP-commentary correction misattributed to KDIGO. |
| T09 | `K01-2024`, `K01-2024-expansion`, `K01-2024-launch-locators`, `K11-2021`, `K11-2021-expansion` | Metadata resolved for CKD 2024 and BP 2021. Check the existing item-specific measurement/target context when recording the next content disposition. |
| T10 | `K05-2024-amended`, `K06-2024`, `K08-2021-remaining`, `K08-2021-remaining-expansion` | Metadata and known AAV-notice impact resolved for current scopes. Preserve GD chapter replacements and both AAV correction relationships; no retained-byte update inferred. |
| T11 | `G01-ERKNet-dRTA-2021`, `K09-2022-expansion`, `L01-AIN-treatment-review-2025-launch`, `L01-CUA-stones-2022`, `L01-IKMG-evaluation-2019`, `L01-urine-eosinophils-2013` | AIN review status and urine-eosinophil correction scope resolved. Add IKMG notice and compare MGRS 2026; dRTA/CUA status limits remain. Do not reopen the previously removed urease claim as an active item. |
| T12 | `K03-2025`, `K03-2025-expansion` | Metadata resolved for ADPKD 2025. No notice listed by the retrieved current publisher record; retain dated locator review. |
| T13 | `G01-ERKNet-dRTA-2021`, `K10-2012-expansion`, `L01-CUA-stones-2022`, `L01-CUA-ureteral-2021` | AKI/dRTA/CUA listed editions identified. Remaining issue is scoped older-guidance/current-EU treatment comparison and incomplete notice checks, not an unidentified replacement year. |
| T14 | `K01-2024`, `K01-2024-expansion`, `K09-2022`, `K09-2022-expansion`, `K11-2021` | Metadata resolved for CKD 2024, diabetes 2022 and BP 2021. Diabetes 2026 remains draft; do not replace the final with it. |
| T15 | `K06-2024-expansion`, `K08-2021-remaining-expansion`, `L01-ISTH-TTP-diagnosis-2020` | Lupus/remaining-GD metadata and ISTH diagnostic correction impact resolved. Add the 2021 PLASMIC notice; the 2025 treatment update is a separate scope. |
| T16 | `K05-2024-amended`, `K05-2024-expansion`, `K06-2024`, `K06-2024-expansion`, `K08-2021-remaining-expansion` | Metadata and AAV correction impact resolved for existing diagnosis/monitoring items. Retain lupus final, GD exclusions and both AAV notices. |
| T17 | `G02-HD-access-2025-launch`, `G07-NG112-2024-launch`, `K06-2024-expansion`, `K08-2021-remaining-expansion`, `K10-2012-expansion`, `K16-2020`, `K16-2020-expansion`, `L01-BK-consensus-2024-launch`, `L01-CUA-ureteral-2021`, `L01-ISPD-catheter-2023-launch`, `L01-ISPD-peritonitis-2022-corrected-launch` | Access, BK, NICE and adult ISPD edition/correction routes resolved; retain both peritonitis notices. Candidate/AKI notice limits remain. Repair the cancer item mapping; it does not provide infection coverage. |
| T18 | `L01-IKMG-evaluation-2019` | New IKMG correction impact resolved. Remaining named task is comparison of the eight existing records with 2026 MGRS diagnostic evidence; no wholesale retirement established. |
| T19 | `G07-NG31-2015-launch`, `K01-2024`, `K01-2024-expansion`, `K01-2024-launch-locators`, `K03-2025`, `K08-2021-remaining-expansion`, `K09-2022-expansion`, `K10-2012`, `K10-2012-expansion`, `K11-2021`, `K11-2021-expansion`, `L01-BK-consensus-2024-launch`, `L01-US-MEC-2024-launch` | CKD/ADPKD/diabetes/BP/BK final/status evidence resolved. AKI, CDC notice limits and NICE last-days scope remain distinct; this is not full pharmacotherapy/palliative coverage. |
| T20 | `G02-HD-access-2025-launch`, `G02-haemodialysis-2019`, `G02-hyperkalemia-2026-07`, `G02-peritoneal-dialysis-2017`, `K01-2024`, `L01-ISPD-catheter-2023-launch`, `L01-ISPD-peritonitis-2022-corrected-launch` | Hyperkalaemia already migrated; access and adult ISPD sources now have official edition/status routes. HD/PD review remains overdue. Repair the two initiation-objective mismatches below. |
| T21 | `K15-2017-donor`, `K16-2020`, `K16-2020-expansion` | Donor 2017 and candidate 2020 remain KDIGO listed finals; their Crossmark data is unavailable. Use candidate-risk scope for the moved cancer item; no aftercare/regimen clearance. |
| T22 | `G02-HD-access-2025-launch`, `G02-pregnancy-renal-2019`, `K06-2024`, `K06-2024-expansion`, `K08-2021-remaining`, `K08-2021-remaining-expansion`, `L01-IKMG-evaluation-2019`, `L01-ISPD-catheter-2023-launch`, `L01-ISPD-peritonitis-2022-corrected-launch` | Lupus/remaining-GD/access/ISPD status evidence resolved. Add IKMG correction and compare MGRS 2026; pregnancy review overdue. Retain pathology scope distinctions. |
| T23 | `G02-haemodialysis-2019`, `G02-peritoneal-dialysis-2017`, `K10-2012-expansion`, `L01-ISTH-TTP-diagnosis-2020` | ISTH diagnostic correction impact resolved. HD/PD clinical review remains overdue, AKI notice status incomplete. Citrate mechanism needs a matching objective; it cannot count as an apheresis-indication assessment. |
| T24 | `G02-pregnancy-renal-2019`, `G07-NG43-2016-launch`, `K01-2024`, `K01-2024-expansion`, `K15-2017-donor`, `L01-US-MEC-2024-launch` | CDC/NICE transition edition identities checked; pregnancy review overdue and donor/CDC notice status limited. Preserve jurisdiction and population scope. |
| T25 | `G02-haemodialysis-2019`, `G02-peritoneal-dialysis-2017`, `K01-2024`, `K01-2024-expansion`, `K01-2024-launch-locators`, `K10-2012-expansion`, `K11-2021-expansion` | CKD/BP metadata resolved; HD/PD current publication records do not remove overdue clinical review. AKI remains 2012 final; no unverified 2026-final label. |
| T26 | `G07-NG31-2015-launch`, `K01-2024`, `K01-2024-expansion`, `K01-2024-launch-locators`, `K08-2021-remaining-expansion`, `K10-2012-expansion`, `K11-2021-expansion`, `K15-2017-donor` | CKD/BP/remaining-GD metadata resolved. AKI/donor notice status incomplete; NICE NG31 concerns last days, not all conservative kidney care. |
| T27 | `G02-pregnancy-renal-2019`, `G07-NG31-2015-launch`, `G07-NG43-2016-launch`, `K01-2024-expansion`, `K01-2024-launch-locators`, `K08-2021-remaining-expansion`, `K09-2022-expansion`, `K10-2012-expansion`, `L01-BK-consensus-2024-launch`, `L01-CUA-ureteral-2021`, `L01-ISTH-TTP-diagnosis-2020`, `L01-US-MEC-2024-launch` | Mixed source set accounted for: CKD/diabetes/GD/BK/ISTH status or notice impact resolved; pregnancy overdue, AKI/CUA/CDC notice limits and NICE transition/last-days boundaries remain. |

## Four objective holds: concrete repairs

All four audit holds are `objective_mismatch`; none is diagnosed as a false
source fact. These proposals use the existing reviewed locators. The content
owner must review mappings and preserve immutable item/family/key identities as
required by the pack contract. A metadata timestamp cannot repair the objective.

| Held item, version 1 | Existing assessed fact and locator | Proposed repair and coverage consequence |
| --- | --- | --- |
| `RN11-T20-001` | Urea target alone does not establish adequate overall dialysis care when fluid/nutritional problems persist. `G02-haemodialysis-2019`, Guideline 1. | Move from initiation objective `T20.O01` to ongoing-care `T20.O02`. Keep the dated foundational source and review-overdue metadata. Do not count it as evidence of initiation competency. |
| `RN11-T20-003` | Pre/post urea 20/6 gives a 70% URR. HD 2019, Appendix 1, printed p26. | Prefer `T23.O01` (solute clearance/modality concepts) over `T20.O01`; reconcile primary/secondary topic and existing objective wording. `T20.O02` alone would be a less precise repair. No new regimen claim is needed for this arithmetic. |
| `RN11-T17-004` | Cancer in remission needs individual transplant-candidate risk assessment. `K16-2020-expansion`, Recommendations 11.2.2, 11.2.3.2, 11.2.4, ppS63–64. | Use `T21.O02` candidate-risk assessment and appropriate T21 primary/secondary topic rather than infection-risk `T17.O01`. Do not count the moved item as infection coverage. No waiting-time rule was newly reviewed here. |
| `RN11-T23-004` | Citrate anticoagulation acts through circuit ionized-calcium chelation. `K10-2012-expansion`, 5.3.2. | Existing `T23.O02` asks for disease-specific apheresis indications and treatment risk, which this mechanism does not assess. Add/use an accurately scoped circuit-anticoagulation objective, or rewrite the assessment against a verified apheresis indication. A bare topic remap is insufficient. Preserve the apheresis coverage gap until a genuine assessed fact fills it. |

## Remaining product work and evidence limits

1. **MGRS comparison is concrete, not an unexplained old-source flag.** The 2026
   European consensus executive summary is identified by DOI
   `10.1093/ckj/sfag163`, PMID 42338690, PMCID PMC13284707. Its publication date
   is May 26, 2026; June is the issue date. The October 5 report already read
   the publisher's Table 9/diagnostic discussion on renal/assay-dependent FLC,
   serum-test sensitivity and tissue assessment. That finding is inherited,
   not relabeled as a fresh read: this run's OUP/PMC/author-repository readers
   failed or challenged, while indexed primary metadata was available. Compare
   the eight IKMG-linked records listed above with the new diagnostic evidence
   before claiming the whole MGRS scope current. Do not infer clone-directed
   treatment, complete appendix review or formal retirement of IKMG.
2. **Overdue UKKA review remains visible.** HD/PD publication status is now
   checked, but replacement of current access/infection claims requires the
   appropriate 2025 access / 2022–2024 ISPD scopes. Pregnancy's clinical review
   remains overdue. Stable calculations/mechanisms can be reviewed specifically;
   the expiry is not proof that every item is false or that the work was retired.
3. **Unavailable notices are bounded gaps.** Alport, dRTA, donor, candidate and
   US MEC did not return Crossmark data; AKI and CUA full notice completeness
   was not established. Official current-edition evidence and inherited locator
   reviews remain useful. Absence of Crossmark data does not itself invalidate
   a key or require inventing an external approval panel.
4. **No new rights or content adoption.** NICE/EAU/CUA/KDIGO and user-owned
   material retain their per-source restrictions in SOURCES.md. A successful
   public read or a newly found correction is not indexing, model-input or
   redistribution permission. No imported originals or hashes were refreshed.
5. **Coverage still needs the content lane.** Metadata closure and four repaired
   mappings cannot alone turn the audit's partial domains or General-only items
   into complete ESENeph coverage. Nothing here changes Flow, models, the approved
   stack, temporary-case handling or historical attempts.

## Reproducible local verification and handoff

All working evidence is external at
`C:/rn-finish-20261007/evidence/sources/`:

- `recovered-inputs.json`: base and SHA-256 identities of recovered inputs.
- `pack-hold-map.json`: exact 27 source-ID sets and four objective holds.
- `crossmark-eight.json`, `crossmark-eleven.json`: fixed, explicit DOI-list
  reads with UTC time, HTTP result, short status excerpt and notice links;
  no crawling, periodic job, provider use or stored guideline body.
- `kdigo-publication-links.json`: eight canonical-page publication routes.
- `additional-findings.json`: original notes for other bounded public reads,
  correction/item impact and failed access routes; no copied source corpus.
- `verify-source-report.py`, `verification.json`, `diff-check.txt`: narrow
  offline report/source-ID/lease and unchanged-input checks.

Verification uses the existing public Python interpreter at
`C:/Users/karol/Documents/t3-workspaces/Renulus-wt-integration/.venv/Scripts/python.exe`
with one process. No application, engine, model, installer or broad suite runs.
The exact commands are the interpreter plus the external verification script,
`git diff --check`, and Git status/diff review for these two leased Markdown files.
The offline check passed: 47 source snapshots accounted for exactly once,
27 exact topic/source sets, four holds, 13 unchanged recovered inputs and
16 existing local Markdown targets. These checks establish documentation
consistency and lease preservation, not clinical validity or working product flows.
Early findings were sent to the integration parent before this commit so the
content lane can repair mappings and correction provenance without waiting for
the full report. The parent owns integration, content release and final acceptance.
