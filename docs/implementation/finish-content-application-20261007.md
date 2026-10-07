# Immutable content application — October 7, 2026

**Result: `renulus-foundations` 1.3.0**, ready for parent review/integration.
Pack identity: `19ea87bc7922328e18158652788550cdc7ca7590ccd128aa9e3dcc94fedc5ddc`.
It contains 230 questions, 52 cases, 57 objectives and 69 source snapshots.
This is a bounded advance of #20, not complete content/currentness acceptance.
Installed cb59/1.2.0, E: state, binaries and runtime selection were not touched.

Branch `codex/finish-content-application-20261007`, base
`b13a90d62ec7de89426ea1cfb0a495987f7e28b9`, worktree
`C:/rn-finish-20261007/lanes/content-application`. Lease is `content/**` and this
one new report. Checkout population was confirmed complete before any writes.
Parent owns actual Updates effects, activation, integration and matching delivery.

## Source application and immutable identities

Recovered the 1.2.0 authoring/review/required-cell evidence, source-lane findings
and [MGRS comparison](finish-mgrs-comparison-20261007.md) before source work.
The exact MGRS XML and passages were already available; no MGRS/IKMG/ISTH refetch
or new currency sweep was performed. The full MGRS appendix remains unread.

| New source snapshot | Scope and exact relationship |
| --- | --- |
| `L01-MGRS-2026-diagnostic-application` | [DOI 10.1093/ckj/sfag163](https://doi.org/10.1093/ckj/sfag163), executive summary published May 26, 2026 / June issue; `PMC13284707.1`. Recovered [official XML](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC13284707/fullTextXML), SHA256 `d405af8506f148513c3586d81933b0b74105b79ec76a08cfced2a7713e69c980`. Eight-record diagnostic scope only. |
| `L01-IKMG-2019-diagnostic-application` | Original `10.1038/s41581-018-0077-4` plus [correction `10.1038/s41581-018-0102-7`](https://www.nature.com/articles/s41581-018-0102-7). Figure 1 label impact does not reverse the selected keys. Old UCL physical-page locators retained alongside 2026 citations. |
| `L01-ISTH-2020-diagnostic-application` | Original `10.1111/jth.15006` plus [erratum `10.1111/jth.15304`](https://onlinelibrary.wiley.com/doi/10.1111/jth.15304). Intermediate PLASMIC row is score 5; high row 6–7. Selected four questions/one case do not teach that row. No PLASMIC calculation or 2025 treatment update adopted. |
| `K08-2021-anti-GBM-application` | Already selected K08 family, new Chapter 11 scope: PP 11.1.1, recommendation 11.2.1, PP 11.2.1–11.2.2 and 11.2.4–11.2.5, printed S86–S87/S233. Exact [official indexed primary text](https://kdigo.org/wp-content/uploads/2024/05/KDIGO-2021-Glomerular-Diseases-Guideline_English_2024-Chapter-Updates.pdf) supplied missing passages after direct PDF-reader failures. Replaced chapters remain excluded. |
| `K03-2025-genetics-application` | Already read K03 family, additional [official 2025 PDF](https://kdigo.org/wp-content/uploads/2025/01/KDIGO-2025-ADPKD-Guideline.pdf) passages: PP 1.3.1–1.3.3 (S22/S61–S62), 1.3.9 (S24/S67), 1.3.10–1.3.11 (S25/S68), 1.3.17–1.3.18 (S27; S67/S72–S73). Adults, family testing and donor uncertainty only. |

All 64 previous source objects remain exactly equal, including their historical
dates and unresolved-at-the-time notes. Five new immutable records contain the
application dispositions. Source relationships use the existing source contract's
scope/check notes and are also explicit in the external review JSON; this does
not implement a new Updates event or source schema. Every new snapshot remains
`dated_final_baseline`; no `needs_currency_review` cell is cleared.

The following questions advance **item/key snapshot 1 → 2**, retaining family
identity/version 1, stem, answer value and every option ID/text. The existing
contract pins `key_version` to item version; an advanced key snapshot is not a
changed correct answer.

| Question | Retained answer | New 2026 locus or inherited ISTH scope |
| --- | --- | --- |
| `RN11-T02-001` | C | `sec2/p[2]` |
| `RN11-T11-001` | A | `sec4/p[11]`–`p[13]`; rationale narrowed |
| `RN11-T18-001` | C | `sec1/p[1]`, `sec2/p[1]` |
| `RN11-T18-002` | D | `sec2/p[3]`, `tbl2` |
| `RN11-T18-003` | A | `sec2/p[4]`, `tbl4`, `tbl4fn1`, `tbl9`; no numeric FLC interval added |
| `RN11-T18-004` | B | `sec3/p[3]` |
| `RN11-T22-004` | B | `sec2/p[3]`, `tbl2`, `sec4/p[11]`, `tbl9` |
| `RN11-T15-001` | A | ISTH diagnostic context/TMA recognition |
| `RN11-T15-002` | B | ISTH recommendation 1, pretreatment sampling |
| `RN11-T15-004` | D | ISTH introduction/recommendation 1, severe deficiency/inhibitor |
| `RN11-T23-002` | B | ISTH recommendation 1/rationale, exchange versus kidney support |

MGRS `p[n]` is the nth **direct paragraph child** of the named XML section.
`RN11-CASE-PROXIMAL` and `RN11-CASE-TMA` advance **1 → 2** with exact stage
references. The proximal case adds the complete-Fanconi/monoclonal-immunoglobulin/
abnormal-serum-and-urine-FLC biopsy exception and its atypical-feature boundary;
its scenario does not establish those prerequisites. The TMA teaching text is
unchanged. No case answer key is invented.

RN11-T11-001 now says, in both its overall and keyed-option rationale:

> The combined findings suggest inappropriate proximal solute loss. Investigate a possible light-chain cause; these findings alone do not establish light-chain proximal tubulopathy.

The current revision checker treats any option-object change, including a
rationale, as requiring a correction/replacement declaration. The new manifest
therefore declares withdrawal of **RN11-T11-001@1 in favour of @2**, explicitly
labelled **rationale-only / no scoring-key reversal**. This declaration is not
activated by this lane; @1 and its original key remain in all predecessor packs
for historical resolution. Parent should inspect the displayed correction reason
when reviewing later activation/history behavior.

## Existing finite gaps advanced

Selection came from the recovered 1.2.0 required-cell manifest and mapping, not
from indicative examination counts. The original minimum 150 and four expansion
items/two skill types per topic remain unchanged. Four authored questions per
unit describe this increment, not a new curriculum or examination quota.

| Existing alignment / domain | New version-1 identities | Explicit coverage |
| --- | --- | --- |
| `glomerular_diagnosis` / `glomerular_interstitial` | `RN14-GBM-001` (A), `002` (B), `003` (C), `004` (D); `RN14-CASE-ANTI-GBM` | Urgent suspected disease; pulmonary boundary of the conservative renal exception; exchange antibody endpoint; isolated versus double-positive maintenance reasoning. Objectives `T10.O01`, `T10.O02`, `T23.O02`. |
| `adpkd` / `inherited_rare` | `RN14-PKD-GEN-001` (E), `002` (A), `003` (B), `004` (C); `RN14-CASE-ADPKD-FAMILY` | Informed screening; targeted familial variant; unresolved negative-panel limits; equivocal related-donor investigation. Objective `T12.O01`. |

All eight are substantive original five-option single-best-answer questions with
individual distractor explanations. Both new cases have three original stages
with explicit objective/claim/source links. The anti-GBM case also supports the
existing `apheresis` alignment; its questions count only in the glomerular domain.
No question is double-counted across domains.

Mapping **`2026-10-07-application1`** updates all affected question/case pins,
these two gap descriptions and the relevant paraprotein scope note. Official
curriculum/blueprint dates and SHA256 values remain the October 5 evidence.
T01–T27 topic metadata advances 4 → 5 solely for this mapping version; all 57
objective definitions are unchanged. The required-cell receipt records **226
mapped questions / 52 five-option questions**, zero objective mismatch holds,
all 57 objective-to-case links, **11 partial domains / 27 open currency cells**.
The four General-only appraisal items remain excluded. Full exam simulation
and complete curriculum coverage remain false.

## Checks, reproduction and files

External evidence: `C:/rn-finish-20261007/evidence/content-application/`.
`candidate-01` is retained. `candidate-02` contains the final reviewed bytes;
release files match it. `release/renulus-foundations-1.3.0-review.json` has 83
review rows: 60 inherited 1.2.0 rows and 23 new application/authoring rows.
`release/verification.json` records ancestry, exact changed identities, source
IDs, finite cells and file hashes. `final-verification.json` records independent
static preservation, locator, mapping and lease checks; no clinical truth is
inferred from passing a JSON validator.

The existing `publish_snapshot`, `validate_pack`, `validate_revision`,
`validate_review_evidence` and `check_required_cells.build_manifest` are reused.
All six predecessors validate; 211 prior questions, 48 cases and all 64 sources
remain equal. All 222 historical answer values, all option texts and family
identities/versions are retained. All predecessor directories and historical
mapping/review/coverage files are unchanged. Source originals and passage bodies
remain external. Original teaching is CC BY 4.0; third-party terms remain separate.

Use the existing public interpreter
`C:/Users/karol/Documents/t3-workspaces/Renulus-wt-integration/.venv/Scripts/python.exe`,
`-B`, `PYTHONDONTWRITEBYTECODE=1`, `PYTHONUTF8=1`, one process:

```powershell
python -B content/authoring/author_application.py --evidence-dir C:/rn-finish-20261007/evidence/content-application/release --prior-evidence C:/rn-finish-20261007/evidence/content --mgrs-evidence C:/rn-finish-20261007/evidence/mgrs
python -B tools/content/check_required_cells.py --release content/packs/renulus-foundations/1.3.0 --review-evidence C:/rn-finish-20261007/evidence/content-application/release/renulus-foundations-1.3.0-review.json --output content/required-cells/renulus-foundations-1.3.0.json --check
python -B C:/rn-finish-20261007/evidence/content-application/verify_application.py
git diff --check
```

No application test collection, engine/model/provider execution, native operation,
activation, reinstall, GitHub write or external publication occurred. Runtime,
UI, schemas, dependencies, source register and other workers' paths are unchanged.
Committed file scope:

- `content/packs/renulus-foundations/1.3.0/`: `manifest.json`, `topics.json`,
  `questions.json`, `cases.json`, `sources.json`, `coverage.json`.
- `content/mappings/esen-eph-2026-10-07-application1.json`.
- `content/required-cells/renulus-foundations-1.3.0.json`.
- `content/authoring/author_application.py`, `application_material.py`.
- `content/README.md` and this report.

## Actionable remaining work

1. Parent review/integration and later activation must verify the rationale-only
   replacement notice, pinned historical feedback and shared consumers. This
   lane provides no installed or actual Updates-journey acceptance.
2. Anti-GBM doses, toxicity/prophylaxis, refractory disease and transplant timing;
   image-based histology and full disease pathways remain unassessed. Family
   testing still lacks full cascade delivery, variant classification/segregation,
   mosaicism and reproductive/pediatric testing. These gaps stay named in the map.
3. Other retained launch gaps include dialysis operations/emergencies, complete
   PD prescription, CMV/rejection/long-term transplant care, other rare diseases,
   and broader urology, cardiovascular, supportive and sexual-health units.
   Add source-supported units against their existing exact mapping gaps.
4. The bounded MGRS access/comparison and ancillary-rationale tasks are resolved
   here, but full MGRS appendix/treatment and broader source currency are not.
   Overdue UKKA HD/PD/pregnancy review, unavailable Alport/dRTA/donor/candidate/
   US-MEC notice status, AKI/CUA notice completeness and exact corrected-copy
   incorporation retain the [source report](finish-source-currency-20261007.md)
   limits. Metadata alone cannot clear those cells.
