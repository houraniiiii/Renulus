# CMV prevention and monitoring proposal — 2026-10-07

Completed a bounded, original adult kidney-recipient CMV teaching and assessment
slice for the shared **D32/D34** gap: **8 five-option questions, 2 four-stage
teaching cases, 2 new immutable source snapshots and 12 review records**. These
are integration proposals, not a published pack or a declaration that either
alignment is complete. The existing BK unit is credited without duplication.

Lease: `content/proposals/depth-20261007/cmv/{questions,cases,sources,reviews}.json`
and this report only. Worktree `C:/rn-finish-20261007/lanes/depth-cmv`, branch
`codex/finish-depth-cmv-20261007`, base
`120bd180d0433f2e1ea023a99ccbaa28320f8515`. Parent preserves accepted installed0d4
and owns packs, mapping, coverage, source-register application, tests, publication
and matching installed/native acceptance.

## Recovered evidence and primary-source research

Read the workspace instructions, README, project brief, workspace/source/decision
records, [finite criteria](finish-launch-criteria-20261007.md), current 1.3.0
records and schema, and [content-application report](finish-content-application-20261007.md).
The [prior currency report](finalise-source-currency.md) had identified the 2025
CMV publication but expressly left viral thresholds, drugs/doses and corrections
unreviewed. Existing `RN12-BK-*`, `RN13-BK-*` and their teaching cases already
establish the bounded BK unit. No old originals, private data or archived MVP
material were opened. The research skill was used with a separate, bounded EMA
research assistant; the lane authored and reviewed the integrated proposal.

The [Transplantation Society's official announcement](https://tts.org/9-tts/general/1616-fourth-international-consensus-guidelines-on-the-management-of-cytomegalovirus-in-solid-organ-transplantation)
still identifies the fourth international consensus. Its
[publication record](https://pubmed.ncbi.nlm.nih.gov/40200403/) is Kotton et al.,
*Transplantation* 2025;109(7):1066–1110, DOI
[10.1097/TP.0000000000005374](https://doi.org/10.1097/TP.0000000000005374),
online April 9, issue July 1, 2025. Missing clinical loci were read in the
[primary full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC12180710/) and its
[Europe PMC XML](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12180710/fullTextXML),
not inferred from metadata. Section identifiers below refer to that exact XML;
`p[n]` means the nth direct paragraph child of the named section.

No same-work correction/retraction was identified in inspected PubMed/PMC records
or targeted title/DOI notice searches. Direct access to the publisher article
failed. This is a bounded notice observation, **not proof that no notice exists**,
not a corrected-PDF-byte comparison and not whole-topic currency clearance.
Crossmark was not used to infer clinical currency.

The [EMA Prevymis EPAR](https://www.ema.europa.eu/en/medicines/human/EPAR/prevymis)
displayed English product information updated **2025-12-12**, revision **18**,
with procedure **N/0000304418 dated 2025-12-05**, checked October 7. The
[English SmPC](https://www.ema.europa.eu/en/documents/product-information/prevymis-epar-product-information_en.pdf)
has an unpopulated section-10 revision date; later translation dates were not
treated as later English clinical revisions. Tablet SmPC printed pages match
one-based PDF pages. The [EMA DHPC listing](https://www.ema.europa.eu/en/medicines/dhpc/prevymis)
contains the September 11, 2020 IV filter notice. Its listing and corresponding
current-label passages were checked; the separate notice PDF was not acquired.
This does not clear every national safety notice or the IV administration scope.

## Exact authored scope and review

| New question | Key | Reviewed claim and primary locus |
| --- | --- | --- |
| `RN15-CMV-001@1` | B | Donor/recipient risk strata and why a negative DNA test does not replace serostatus; consensus sec3/p[1], p[5], sec18/p[1]. |
| `RN15-CMV-002@1` | D | A deliverable preemptive programme versus prophylaxis; result ownership, at least weekly testing for 12–16 weeks and continuing-risk qualification; sec14/p[1], p[3], sec26, sec30. |
| `RN15-CMV-003@1` | C | Consistent assay/specimen, local thresholds and low-level-result uncertainty; sec6, sec14/p[1]–p[2], sec17/p[1], sec30. |
| `RN15-CMV-004@1` | B | Reassessing valganciclovir indication and renal-dose basis as graft function changes; no fixed dose or arbitrary mini-dosing; sec21/Table 5, sec65/p[1]. |
| `RN15-CMV-005@1` | E | Routine testing during appropriate prophylaxis versus new absorption/adherence concerns; sec9/p[1], sec25. |
| `RN15-CMV-006@1` | A | Increased-risk postprophylaxis surveillance, weekly 8–12 weeks, retaining weak/low-certainty qualification; sec16, sec31. |
| `RN15-CMV-007@1` | C | Tacrolimus concentration monitoring during letermovir coadministration and discontinuation; separate ciclosporin interaction review; EMA tablet sections 4.4–4.5, pp.5, 7, 12–13. |
| `RN15-CMV-008@1` | B | EU letermovir prophylaxis indication versus treatment and other-herpesvirus coverage; EMA 4.1 p.2, consensus sec12/p[2], sec32 and adult sec66. |

Question keys, all four distractors, rationales and field-level authored claims
are preserved verbatim in `reviews.json`, with their supporting loci, review date,
notice dispositions and rights. The single-key reasoning is explicit; a source
link alone is not represented as review. Review is **assistant review only**.

`RN15-CASE-CMV-PREVENTION@1` provides accessible teaching on risk, prevention
choice, assay interpretation and the end-of-course handover. Its R+ and D−/R−
comparisons distinguish recipient aftercare populations. Four stages provide
narratives, prompts, new information, revealed teaching points and a final debrief.

`RN15-CASE-CMV-MEDICINES@1` teaches renal-dose reassessment, intolerance strategy,
letermovir interaction planning and reassessment of new symptoms. The adult case
weighs 74 kg and starts oral letermovir on day 6, preserving the EU indication's
**at least 40 kg** and **start by day 7, continue through day 200** conditions
([SmPC 4.1–4.2, pp.2, 4](https://www.ema.europa.eu/en/documents/product-information/prevymis-epar-product-information_en.pdf#page=4)).
The consensus's broader discussion of intolerance-driven switches does not make
every later switch a labelled schedule. The teaching explicitly preserves this
distinction, and the distinct consensus six-month recommendation is not converted
into a universal drug stop date.

Interaction teaching includes the first two weeks after starting **and stopping**
letermovir and route changes. It supplies no universal tacrolimus reduction or
fixed antiviral dose. The source research additionally recovered letermovir's
renal/IV limitations, but those are outside this proposal's adopted teaching
scope; it does not imply that all formulations or dialysis situations are covered.

All cases are invented; no patient data, official examination item, copied source
algorithm or primary figure is used. Assessment remains `assessment_reserved`;
cases remain `teaching`, with self-contained explanations independent of the bank.
Objective support is limited to **T17.O02, T19.O01 and T27.O02**, with exact stage
links in reviews. No pretransplant T21 objective is used as aftercare evidence.

## Immutable snapshots, rights and evidence

New source IDs are `RN15-CMV-SOURCE-CONSENSUS-2025-20261007` (`L01`) and
`RN15-CMV-SOURCE-EMA-PREVYMIS-20261007` (`G06`). Both use the current source record
schema and `dated_final_baseline`; no source/update cell is cleared. No existing
ID, published pack, source record, mapping, target or root manifest was changed.

All raw public evidence is outside Git at
`C:/rn-finish-20261007/evidence/depth-cmv/`:

| Artifact | SHA-256 / purpose |
| --- | --- |
| `PMC12180710.xml` | `5e9508b814eadde6b06cc1cabbd96f2f1ed23dcb1e783718c8c5fd2f619759a9` — inspected consensus primary XML. |
| `prevymis-epar-product-information_en.pdf` | `db4998a6cb590006789107af9f09c4196d815ed441a57d076042c2223b8d34a9` — exact inspected English SmPC. |
| `ema-review.md` | Delegated primary research, locators, version/notice findings, retrieval limits and rights. |
| `acquisition.json` | Public URLs, hashes, dates and source-specific rights. |
| `static-shape-check.json` | JSON/text/static-shape receipt; no application validation. |

The consensus is **CC BY-NC-ND 4.0**, retained as an external research reference.
It is not relicensed as Renulus content. The
[EMA legal notice](https://www.ema.europa.eu/en/about-us/about-website/legal-notice)
permits attributed reproduction of EMA-owned material subject to exclusions,
including third-party content. Public availability does not remove those limits.
Only original Renulus educational expression and bounded factual support are in
the proposal; original teaching uses the existing `content/LICENSE` CC BY 4.0.
No source body, translated guideline, table or raw download is committed.

## Static checks and integration residue

Standard-library checks read JSON and text only: array/record shape against the
observed 1.3 examples and schema contract; required fields and allowed values;
five unique options and a valid single key; source/objective/stage references;
review-to-authored-text equality; unique new identities and no collision with
1.3.0. `git diff --check` supplies whitespace review. No project runtime imports,
application tests, models, engines, providers, installers, native control,
dependency changes, GitHub writes or publication were performed. Parent still
owns actual pack validation and integration acceptance.

The proposed shared CMV reasoning slice now has teaching, assessment, stages,
claim/key/distractor review and dated evidence. Parent must review and integrate
its exact scope once across D32/D34. Preserve existing BK credit. The following
remain distinct and unresolved: deceased-donor allocation; rejection regimens;
malignancy aftercare; broader long-term recipient care; other infections;
comprehensive CMV treatment, resistant/refractory disease, immune-assay-guided
strategies and full drug/dialysis/IV prescribing. The undefined boundary of
“comprehensive” CMV coverage remains for the parent's A01 reconciliation.
Source notice completeness and wider clinical currency are not certified here.
