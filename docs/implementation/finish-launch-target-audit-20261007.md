# Launch-target decision aid — October 7, 2026

**Disposition:** the original measurable bank minima are met. Complete required
launch coverage is **not presently decidable from the adopted manifest and its
criterion code**. There is a finite inventory, but no complete depth/currency
acceptance predicate. This does not discharge S6.01, make partial ESENeph coverage
complete, or establish that the remaining work is exclusively external.

Read-only audit of frozen parent `b8a3c177945268706227ea3b8355c2fcd5d6bafb`, branch
`codex/finish-launch-target-audit-20261007`, worktree
`C:/rn-finish-20261007/lanes/launch-target-audit`. The only write is this report.
Parent owns packaging, native acceptance, tests, engines and providers. Findings
below concern the frozen source; no later installation or parent activity is inferred.

**Evidence and authority.** AGENTS, README, PROJECT_BRIEF, WORKSPACE and DECISIONS
retain broad nephrology, General plus ESENeph, separate teaching/assessment and
source/rights boundaries. The plan requires measurable targets before authoring
and forbids lowering them at release: [IMPLEMENTATION_PLAN:202–223](../planning/IMPLEMENTATION_PLAN.md#L202).
S6 requires a matrix of explanation/evidence, questions, cases and update sources,
explicit launch scope and every required cell met, while permitting genuinely
additional future content: [plan:297–319](../planning/IMPLEMENTATION_PLAN.md#L297).
The current audit preserves that obligation as S6.01, not an optional aspiration:
[finish-audit:235](finish-audit-20261007.md#L235).

Reference abbreviations used below, with line numbers fixed at the parent:

- **M** — [1.3.0 required-cell manifest](../../content/required-cells/renulus-foundations-1.3.0.json).
- **C** — [check_required_cells.py](../../tools/content/check_required_cells.py).
- **P** — [runtime programme derivation](../../runtime/renulus/content/programmes.py).
- **A** — [1.3.0 content application report](finish-content-application-20261007.md).
- **S** — [October 7 source/currency report](finish-source-currency-20261007.md).

**Original finite requirements and their current evidence.**

The protected baseline is pack 1.1.0, canonical SHA256
`3f0b712fad056a8857fb9fc913432914cad599096c28aa96fd35e7515076c670`.
Its October 4 adoption is commit `a6ed4959`; October 5 reconciliation/target guards
are `4cb04976`. Provenance is explicit in M:10–110 and
[content-evidence:270–304](content-evidence.md#L270), rather than inferred from
the later 200-question reference blueprint.

| Required inventory or criterion | Provenance / exact meaning | At frozen parent |
| --- | --- | --- |
| All 27 target topics, T01–T27 | 1.1.0 [coverage:3–31](../../content/packs/renulus-foundations/1.1.0/coverage.json#L3); M:13–40 | All retained, each with primary-topic assessment and objective-linked teaching cases. |
| Original 56 objective identities | T01–T27 each O01/O02, plus T08.O03/O04; M:42–98. Current rows also include the added T23.O03. | All retained; all 57 current objectives have both question and case pins. No unlinked topic objectives, no objective-case gaps, no objective-mismatch holds (M:3987–6007). Links establish coverage evidence, not mastery or full teaching depth. |
| At least 150 reserved assessment questions | 1.1.0 coverage:32; [author_expansion:1222–1228](../../tools/content/author_expansion.py#L1222) | 230; generated practice/evaluation items do not satisfy this criterion. The 108 expansion items are included in the total, not an additional 108-question quota. |
| At least four original-expansion questions and two reviewed skill types per topic | 1.1.0 review rows and [skill matrix:2468](../../content/reviews/renulus-foundations-1.1.0.json#L2468); author_expansion:1270–1272; C:42–67,130–155 | Exactly four original-expansion pins per topic; two or three skill types each. Successor reviews preserve this evidence. No additional bank-minimum deficit. |
| At least one teaching case per topic with an explicit related objective | C:53–69; stronger than mere primary/secondary case tags in the runtime pack validator | Every topic meets it; 52 cases total. No separately adopted total-case or per-objective-case quota is supplied (M:6006). |
| Explanation/evidence linkage for each topic | C:58–72: case plus source links, including teaching-stage citations | All 27 are `linked`. This is not a complete standalone explanation for every topic/objective; reserved rationales cannot supply teaching-mode explanations. |
| Update-source inventory for each topic | M topic rows / C:58–75; latest-final, notices and scope obligations in SOURCES:190–200 | All 27 have identified sources; their union is 61 currently linked snapshots. All 27 remain `needs_currency_review`; all 61 snapshots are `dated_final_baseline`. Pack total is 69, including eight records outside this current link union. |
| Reviewed original content, immutable identity/history and honest ESENeph availability | Plan S3; [revision_checks:21–60,64–143](../../tools/content/revision_checks.py#L21) | Assistant source/key review is recorded; no human-review/efficacy claim. 1.3.0 source upgrade/history evidence is accepted within its recorded scope; matching installed acceptance remains separate. |

1.3.0 identity is `19ea87bc7922328e18158652788550cdc7ca7590ccd128aa9e3dcc94fedc5ddc`.
M:112–120 reports 27 topics / 57 objectives / 230 questions / 52 cases,
`adopted_bank_minima_met=true`, `complete_content_coverage=false`.
This audit read the committed receipt and projected its JSON; it did not rebuild it.

**What the criterion code actually decides.**

| Code location | Behavior and consequence |
| --- | --- |
| C:21–35,130–135 | Pins and checks the 1.1.0 baseline hash; validates pack and baseline; checks revision against baseline. `validate_revision` protects adopted target-topic membership, minimum question count and objective IDs, plus immutable records/source snapshots and corrections. These guards do not define sufficient clinical depth. |
| C:37–59 | Uses only `assessment_reserved` questions; per-topic question counts use primary topic. Cases qualify by objective intersection, not tags alone. Only `objective_mismatch` exclusions are removed from objective/source support; such questions still enter total/per-topic/expansion counts. There are zero such holds now. |
| C:42–67,136–155 | Expansion credit comes from the original 1.1.0 review IDs/versions, not every later addition. Revised original IDs require `--review-evidence` with matching reviewed successor pins. Four questions and two distinct skill types are hardcoded minima. |
| C:70–86 | `explanations_evidence=linked` iff a qualifying case exists and the union of relevant question/case/stage source IDs is nonempty. Objective teaching status is `linked` iff a case pin exists; no complete-explanation quality/depth test is performed. |
| C:87–90 | `met` is total reserved questions >= baseline minimum AND, for every current topic, questions/cases/expansion all `met_minimum` AND no unlinked objective IDs. It does not require every objective to have both a question and a case, independently gate explanation status, or consult currency/domain completeness. The current receipt nevertheless has both links for all 57 objectives. |
| C:60,73–75,92,107,119,178–183 | Currency status is unconditionally `needs_currency_review`, regardless of dated-source count or newer review evidence. Receipt `checked_on` is pack publication date, not a fresh source check. `complete_content_coverage` and receipt `exam_simulation_available` are always false. Printed currency-cell count is simply `len(topic_cells)`. Twenty-seven is not a measured count of failed fresh checks or independent source failures. |
| C:124–126; P:112–119,140–153 | `remaining_cells` includes every domain alignment, not only empty ones. Active exam alignment is always `partial` when any selected question/case exists, otherwise `gap`. A domain is `partial` if any active alignment is partial, otherwise `gap`. Neither path can derive `complete`, even if more content is added. Gap prose is carried through, not evaluated as a checklist. |
| P:150–174 | Family shortfall is `max(0, indicative_questions - unique_families)`; five-option compatibility counts option lengths. Programme status is copied from authored mapping metadata. Neither count establishes depth, format validity beyond length, full simulation or a launch quota. |
| C:158–184 | Defaults select historical 1.1.1, not 1.3.0. `--check` compares exact JSON bytes; mismatch/error returns 2. Successful build/equality returns 0 with `valid=true`; it does not fail merely because `met` is false, and complete coverage is always false. `valid` is not release acceptance. No invocation of this code was made here. |

The runtime pack validator separately enforces source/key review metadata, actual
coverage consistency, the declared global count and per-target question/case tags
([validation.py:148–209](../../runtime/renulus/content/validation.py#L148)).
The authoring receipt tightens case linkage to objectives. Neither validator
establishes clinical truth by accepting structured evidence.

**Finite ESENeph inventory versus undefined completion depth.**

The original mapping uses a dated 2022, 58-page curriculum and an undated,
SCE-titled two-page blueprint linked by the official hub; exact hashes/pages and
October 5 check dates survive in M:6929–6964. These are reference provenance,
not a newly dated 2026 curriculum. The mapping explicitly says the 200-question
exam weights are not a launch quota ([mapping:38–81](../../content/mappings/esen-eph-2026-10-07-application1.json#L38)).

There are **43 exam-domain alignment cells**, all with at least one question and
one case, all partial, plus one separate curriculum-support alignment. M's
`remaining_cells` excludes that support alignment. Eight historically empty
`*_gap` facets now have pins; their IDs do not mean they are still empty.
The current 226 mapped questions exclude four General-only appraisal questions;
52 mapped questions have five options. No full examination simulation is accepted.

| Domain | Exact alignment-cell IDs (M starting line) | Mapped questions / unique case pins in domain |
| --- | --- | --- |
| Glomerular/interstitial | `glomerular_diagnosis`, `glomerular_management`, `systemic_immune`, `tubular_interstitial`, `paraprotein`, `apheresis` (7072) | 41 / 11 |
| Acute/biochemistry | `aki_staging`, `aki_management`, `changing_filtration`, `acute_support`, `water_sodium`, `potassium_acidosis` (7132) | 38 / 10 |
| CKD/urine | `ckd_classification`, `ckd_progression`, `advanced_ckd` (7192) | 22 / 5 |
| Bone/anemia | `bone`, `anemia` (7222) | 13 / 3 |
| Cardiovascular/diabetes | `blood_pressure`, `diabetes`, `cardiorenal` (7242) | 19 / 5 |
| Urology | `obstruction`, `stones`, `urinary_infection_gap` (7272) | 10 / 4 |
| Inherited/rare | `adpkd`, `other_inherited_gap` (7302) | 16 / 4 |
| PD | `pd_clearance`, `pd_infection_gap` (7322) | 8 / 3 |
| HD | `hd_clearance`, `hd_emergency`, `hd_access_gap` (7342) | 13 / 3 |
| Transplantation | `transplant_candidates`, `transplant_prevention`, `donor_choice`, `transplant_aftercare_gap` (7372) | 18 / 4 |
| Other | `prescribing`, `infection`, `pregnancy`, `nutrition`, `supportive_care`, `procedure_decisions`, `sexual_health_gap`, `transition_gap`, `end_of_life_gap` (7412) | 28 / 19 |

Cases may support multiple domains; those counts must not be summed into a pack
total. The only nonzero indicative family shortfalls are CKD 2, cardiovascular 1,
urology 4 and HD 1 (M:6989–7050). Adding eight families would not prove completion;
these are reference-weight differences and say nothing about the missing substance.

The gap prose contains concrete unassessed scopes: anti-GBM doses/toxicity and
transplant timing (M:7072), initial/nephrogenic DI and hypernatremia (7172),
Fabry/cystinosis/primary hyperoxaluria (7312), HD air/haemolysis/disconnection
emergencies (7352), and CMV/rejection/long-term aftercare (7402). These remain
content work; they are not all access blockers. However, phrases such as
"complete disease-by-disease" (7082), "exhaustive etiologic AKI differential"
(7132), and "complete inherited-disease differential" (7302) supply no bounded
objective/claim list, required depth, case/question sufficiency or stopping rule.

Some negatives are alignment-local, not reliable bank-wide absence statements:
`tubular_interstitial` still says no inherited salt-wasting assessment (M:7102),
while 1.2.0 added Gitelman; `transplant_prevention` says no posttransplant virology
assessment (7382), while BK aftercare is present in another alignment. See
[content README:35–42](../../content/README.md#L35). Reconcile the scope of such
notes against pins before treating them as additional missing units. Their
overlap does not establish comprehensive salt-wasting or virology coverage.

**Accepted work to retain, with supersession of old open notes.**

- Original-bank minima and broad-topic presence are accepted evidence; four
  mismatched objective versions were repaired in 1.2.0, including T23.O03 and
  its citrate case. The earlier six missing objective-case links are gone.
  Sources: M:6005–6007; [content README:27–57](../../content/README.md#L27).
- Hyperkalaemia migration was already complete in 1.1.2 (S:18). 1.2.0 recorded
  scoped IKMG/ISTH/AAV/MBD/urine-eosinophil relationships and both PD notices;
  their existence should not be reopened merely because currency labels stay open.
- The eight-record MGRS diagnostic comparison, source adoption and narrowing of
  both ancillary-rationale copies are resolved by 1.3.0 (A:27–85,170–175).
  Eleven questions/two cases have reviewed successors without answer reversal.
  A:3–12 records parent review and an actual source repository upgrade/history
  check. The older "not yet adopted" in SOURCES:169–170 and rationale action in
  finish-audit:265–266 are superseded for this bounded task; they are not fresh blockers.
- The accepted cb59/1.2.0 installation and core learning/recovery scopes remain
  credited. Source eligible-body retrieval and installed explicit Updates review
  already passed. The latter had zero linked bank versions and no source-status
  changes, so it did not prove affected-item correction effects
  ([Updates report:24–36](finish-updates-review-20261007.md#L24)).

**Remaining internal obligations and genuine external limitations.**

| Obligation / limitation | Exact disposition at frozen parent |
| --- | --- |
| Deliver 1.3.0 and preserve corrected/history consumers | Parent-owned matching package/installed activation, displayed rationale-only replacement, pinned feedback/history and shared consumers remain required. A:3–12,157–161 already credit source upgrade checks; [FINISH:31–37](FINISH_20261007.md#L31) still selects cb59/1.2.0. Do not repeat accepted source work merely to manufacture another aggregate. |
| Affected-source correction effects and connected learning | S5.04/S5.05 and S6.02 still need their remaining actual affected-item/feedback/history/eligibility and stale/exact-copy effects; the installed unrelated research review does not close them. See [finish-audit:228–236](finish-audit-20261007.md#L228). They are engineering/acceptance obligations, separate from curriculum volume. |
| Apply source dispositions to the exact current claims | The 47-record S report describes 1.1.2. Current M has 61 linked snapshots and 1.3.0 has 69 total. Reconcile successor/added scopes with their review evidence; do not mechanically apply the old topic/source table to the new union. Metadata review, clinical claim review and immutable-copy verification have different outcomes (S:104–112; A:42–47). |
| UKKA overdue clinical review | HD 2019 and PD 2017 affect current T20/T23/T25; pregnancy 2019 affects T01/T22/T24/T27 by M's exact source links. Publication status was checked, but continued listing does not resolve overdue clinical review. Scoped review against newer access/infection/pregnancy evidence is internal content work; expiry alone proves neither false keys nor wholesale retirement (S:171–175; SOURCES:151–158). |
| Named unavailable publisher notices | S:176–180 records unavailable Crossmark for Alport, dRTA, donor, candidate and US MEC. Current links: Alport T02; dRTA T04/T05/T11/T13; donor T02/T21/T24/T26; candidate T17/T21; US MEC T19/T24/T27. These are bounded external evidence failures/unknowns, not proof no notice exists and not a requirement to obtain Crossmark specifically. Prior accessible locators retain their scope. |
| Incomplete AKI/CUA notice and treatment review | AKI links T06/T07/T13/T17/T19/T23/T25/T26/T27; CUA stones T04/T05/T11/T13; ureteral T06/T13/T17/T27. S:176–180 says notice completeness was not established. This mixes remaining review with access limits; it is not evidence that all associated work is externally blocked. Keep final/draft and jurisdiction/treatment scope distinct. |
| Exact corrected originals | S:47–48,181–184 does not prove retained PDFs incorporate later corrections. The unresolved item is exact-copy evidence, not automatically a missing question or demonstrated external-access impossibility. Do not change original hashes or historical snapshots to match a notice. |
| Official ESENeph refresh | [finalise-esen-eph:415–440](finalise-esen-eph.md#L415) records preserved hash/page checks but a later October 5 hub/two-PDF refresh returning 403. That dated access limit remains distinct from the valid retained references. No fresh official-2026 edition or endorsement may be inferred. |
| Restricted/member/third-party material | SOURCES:18–22,85–97,178–197 separates reading, processing and redistribution rights. User download/permission may be an external dependency for a particular chosen file; no adopted finite bank minimum requires redistribution of ERA/official exam material or all source-register candidates. No complete coverage claim follows from collection admission/import counts. |
| Broader unassessed teaching content | The named scopes in M:7070–7500 and A:162–169 remain substantive internal content work. Existing four-items-plus-case increments demonstrate progress, not an adopted per-facet sufficiency rule. Full MGRS appendix/treatment is unreviewed broader scope; the eight-record diagnostic task is resolved. |

The current currency mapping above is a lightweight projection of M's exact
source-ID arrays, not a new clinical review. S identifies useful resolved edition/
notice evidence for T08/T09/T10/T12/T14/T16, among others (S:123–131); this prevents
calling every topic an external failure. It still does not clear their complete
current-claim review. Known unknowns remain excluded from default current-guidance
retrieval under [SOURCES:190–201](../SOURCES.md#L190).

T18 illustrates why the labels cannot be used as a work counter: its current
source set is only the new IKMG/MGRS diagnostic-application pair (M:2431 onward).
The previously named eight-record comparison/adoption is done, yet C still emits
`needs_currency_review`. A dated, scoped disposition must distinguish that closed
task from any remaining current-claim acceptance; rerunning the same comparison
cannot make this unconditional flag change.

**Decision the parent can make from this audit.**

Preserve three separate findings: (1) original finite bank minima met;
(2) required source/clinical depth and specified installed effects unresolved;
(3) complete launch-depth sufficiency not defined by the available criterion.
The inventory is finite; the missing acceptance rule must not be replaced with
either endless authoring toward an unlimited curriculum or a fabricated pass.

The remaining specification task is to reconcile the existing adopted objectives
and named gap scopes into explicit required claim/evidence/question/case/update
acceptance, preserving all already required targets and recording their provenance.
For each required cell the record needs a bounded scope, sufficient evidence and
review disposition, current-source/notice/copy limits and an observable completion
condition. Recover any prior adopted definition first; this audit found no such
complete rule in the scoped files. The plan permits additional future content,
but these files do not classify every broad gap as required launch versus future
depth. This audit does not make that classification or authorise dropping any gap.

Only after that evidentiary reconciliation can criterion changes faithfully
express completion; merely removing hardcoded false/partial states, accepting
counts as depth, changing the blueprint quota or renaming partial as complete
would not satisfy S3/S6. Retain S6.01 and complete-release status as open meanwhile.
No new human panel, signing, clean-PC or full-exam quota prerequisite is introduced.

**Audit method and lease.** Numbered text/Git reads and PowerShell JSON projections
only; review/test/provider outcomes above are attributed to existing reports.
No clinical research sweep, network, imports, criterion execution, tests, engines,
providers, application/native actions, GitHub writes or private-state reads.
Git whitespace and explicit single-file scope checks are the handoff checks.
No planning, manifest, source register, code or previous audit is edited.
