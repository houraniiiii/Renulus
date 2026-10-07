# Foundations 1.4.0: bounded depth publication

Checked 2026-10-07. Assistant-authored and assistant-reviewed; no independent
human review, source-wide clinical-currentness clearance, practical certification
or installed acceptance. Research follows the primary-source research skill.

The additive **1.4.0 authored snapshot** is prepared with canonical pack SHA256
`26392c93fffb32fc4f3582ad39bbdfe4d37266fbad8c3ffda492fe394440230d`.
It adds coherent teaching and assessment for three previously named gaps: adult
kidney-recipient CMV prevention/medicine safety; anti-GBM response, toxicity,
infection prevention and timing; and three intradialytic emergencies. Existing
BK, anti-GBM initial-treatment and HD hypotension teaching retains its credit.

Parent must regenerate `runtime/renulus/content/source_register_ids.json` from
the amended `docs/SOURCES.md` before activation: the old bundled register lacks
G09. This lane leaves that runtime file untouched. Content validation used the
existing `known_register_ids` parameter with IDs parsed from the canonical source
register, including G09; it did not weaken schema or clinical-review checks.
Activation, integrated application tests, native acceptance and release remain
parent work. No installed/provider checks were repeated.

## Inputs, counts and immutable preservation

Lane base: `120bd180d0433f2e1ea023a99ccbaa28320f8515`. Proposal inputs:
HD `e98787c12685f25d991d25e18ee440d3f1ef5061`, CMV original
`a5064d47edcd12947ed2b3ece19b9602ccf663ba` (lane cherry-pick `b651c7c9`),
anti-GBM original `96c5039c7dee81b5895a72d778bdd3e61851e67e` (lane `0138c97c`).
Parent reports matching proposal integrations `72cefcfe`, `30f6297e`, `d97350a7`.
The publication commit is standalone on top of those proposal contents; parent
does not need to cherry-pick these lane proposal commits again.

| Records | Inherited exactly from 1.3.0 | New | 1.4.0 |
| --- | ---: | ---: | ---: |
| Reserved questions | 230 | 19 | 249 |
| Staged teaching cases | 52 | 6 | 58 |
| Immutable source snapshots | 69 | 8 | 77 |
| External artifact review rows | 83 | 25 | 108 |
| External source review rows | 22 | 8 | 30 |

There are still 27 topics and 57 objective definitions. All 230 inherited
question objects, 52 case objects and 69 source objects are deep-equal, including
versions, options, answers, rationale, families and keys. Withdrawals are inherited
unchanged. Topic versions advance from 5 to 6 only to select the new mapping;
every other topic field and objective definition remains exact. All 42 files in
the seven predecessor pack directories match their base Git blobs byte for byte.
The external receipt also verifies 50 protected files in total, including prior
mappings, required-cell receipts and the launch criteria. No predecessor bytes,
targets, runtime, tests, renderer, packaging or current handoff were edited.

## Exact additions and review disposition

Every assessment has five original options, a rationale for each, a distinct
reserved family and an exact key/distractor review. The review receipt retains
all 29 raw proposal review records (25 artifacts and four source-only records),
plus normalized validator rows and exact copies of each new authored artifact.
Clinical skill names are translated to the existing validator vocabulary only;
this is not additional clinical evidence. Claim paths, exact option text and
rationales, stage teaching, narrative/reveal/prompts and objective-source links
were checked against the supplied records. Source references alone were not
counted as a review.

| Question ID suffix (prefix RN15-) | Key | Reviewed locus / distinction |
| --- | --- | --- |
| HD-001 | C | BC Renal 2.2, printed p2: suspected air and immediate protective response |
| HD-002 | B | BC Renal 2.10, pp8–9: haemolysis recognition despite initially preserved/high BP |
| HD-003 | D | Saha/Allon, Hemolysis final paragraph: potassium risk from circuit blood |
| HD-004 | A | BC Renal 2.16.1 p15; UKKA STOP pp4–5: bleeding despite absent pressure alarm |
| HD-005 | C | BC Renal 2.16.1 p15: the stem explicitly establishes contamination |
| CMV-001 | B | Consensus sec3 and sec18: paired donor/recipient IgG risk |
| CMV-002 | D | Consensus sec14, sec26, sec30: reliable weekly preemptive delivery |
| CMV-003 | C | Consensus sec6, sec14, sec17, sec30: assay/specimen/local threshold limits |
| CMV-004 | B | Consensus sec21/Table 5 and sec65: changing renal function and dose review |
| CMV-005 | E | Consensus sec9/sec25: new absorption concerns during prophylaxis |
| CMV-006 | A | Consensus sec16/sec31: qualified weekly surveillance after prophylaxis |
| CMV-007 | C | EMA SmPC 4.4/4.5 Table 1: measured tacrolimus exposure around letermovir |
| CMV-008 | B | EMA 4.1; consensus sec12/sec66: prevention does not establish treatment or HSV/VZV cover |
| GBM-001 | B | KDIGO Figure 98, S232: parallel organ/antibody/blood-count monitoring |
| GBM-002 | D | KDIGO Figures 98/99, S232/S234: leukopenia and treatment review |
| GBM-003 | A | KDIGO S233 and PP1.8.4 S104: qualified TMP-SMX consideration |
| GBM-004 | E | KDIGO 1.8, PP1.8.2–3 S104: clinically appropriate screening/Strongyloides risk |
| GBM-005 | C | KDIGO PP11.2.3 S233: usual durations with activity/toxicity limits |
| GBM-006 | B | KDIGO PP11.2.7 S234: sustained undetectable antibodies, not time since diagnosis |

The six accessible text cases have independent staged teaching, new reveals,
prompts and debriefs, rather than repackaged reserved-bank rationales:

- `RN15-CASE-HD-AIR`, `RN15-CASE-HD-HAEMOLYSIS`,
  `RN15-CASE-HD-DISCONNECTION`: three stages each, partial `T20.O02` only.
- `RN15-CASE-CMV-PREVENTION`: four stages, `T17.O02` and `T27.O02`.
- `RN15-CASE-CMV-MEDICINES`: four stages, `T17.O02`, `T19.O01`, `T27.O02`.
- `RN15-CASE-GBM-SAFETY`: five stages, `T10.O02`.

One substantive proposal correction was necessary: Leon's initial narrative now
explicitly states donor CMV IgG positive / recipient negative (D+/R−). Its exact
review copy changed with it. He remains 59 years, 74 kg, on day 4; the subsequent
EU letermovir discussion therefore has an explicit scenario basis. No assessment
key, option or drug dose changed. The HD BC source scope now records the resolved
G09 allocation; raw proposal register/publication holds describe its earlier
state. Other proposal files remain unchanged.

## Recovered primary evidence and clinical boundaries

No new network acquisition was needed. Prior primary receipts were recovered
first, original files retained externally and exact missing local passages read.
The new evidence directory totals approximately 2.24 MB, including two selected
KDIGO page images; no repeated whole-document copy or private material was added.

**HD.** [BC Renal's official complications PDF](https://www.bcrenal.ca/resource-gallery/Documents/Provincial-Guideline_HD_Complications.pdf)
prints July 2026, despite a stale March 2025 indexed date. Reviewed physical p4
(2.2), pp10–11 (2.10) and p17 (2.16.1), corresponding to printed pp2, 8–9, 15.
Suspected air/haemolysis warrant interrupting treatment and withholding circuit
blood; the disconnection item applies no-return specifically to contaminated
blood. This does not establish a universal no-return rule for all bleeding or
cardiac arrest. Positioning, aspiration, transfusion thresholds and complete
water-system/device protocols are excluded. Canadian nursing guidance supplements
EU education; local trained response and device instructions remain necessary.

[UKKA STOP 2023](https://www.ukkidney.org/sites/renal.org/files/STOP%20Guidance%202023%20Final.pdf),
physical pp4–5, supports access visibility and alarm limitations. Its April 2026
review date is overdue; it does not refresh UKKA2019 or inherit currency from
later vascular-access guidance. The [NDT 2025 review](https://academic.oup.com/ndt/article/40/11/2046/8202812),
Box 1 and “Additional first actions,” corroborates the air/haemolysis exception.
The [Saha/Allon 2017 review](https://pmc.ncbi.nlm.nih.gov/articles/PMC5293333/),
Hemolysis final paragraph, supplies the potassium mechanism and cluster-investigation
reasoning. Publisher/indexed access and incomplete notice/rights clearance remain
as recorded; neither paper is relabelled an EU guideline.

**CMV.** Reused the [fourth international consensus](https://doi.org/10.1097/TP.0000000000005374),
retained public XML `PMC12180710.xml`: exact sections in the table and sec25–31,
sec12 and sec65 were reviewed. Preserve local assay/specimen thresholds, dependable
weekly preemptive testing, renal-dose review and the weak/low-quality qualification
for postprophylaxis weekly surveillance. Six-month consensus prophylaxis is not
silently equated to a medicine's product-specific stop instruction.

The retained [EMA English Prevymis product information](https://www.ema.europa.eu/en/documents/product-information/prevymis-epar-product-information_en.pdf)
was checked at sections 4.1–4.5, physical pp2, 4, 5, 12–13. The adult kidney slice
requires D+/R− and at least 40 kg; start by day 7 and continue through day 200.
The label also includes eligible paediatric recipients, outside this adult unit.
Tacrolimus/ciclosporin interactions require concentration monitoring and specialist
adjustment, not a universal percentage dose change. No ESRD/dialysis dose,
resistant/breakthrough treatment, national availability or intravenous protocol
is inferred. The retained English revision date is 2025-12-12; later translation
dates do not establish a new English label. The known historical IV-filter notice
does not become a reviewed IV-use protocol here.

**Anti-GBM.** Reused the [official KDIGO combined guideline](https://kdigo.org/wp-content/uploads/2024/05/KDIGO-2021-Glomerular-Diseases-Guideline_English_2024-Chapter-Updates.pdf).
Physical p109/S104, p237/S232 Figure 98, p238/S233 and p239/S234 Figure 99 and
PP11.2.7 were read locally; both figures were visually inspected. This supplements
the proposal's indexed reading with selected retained-byte verification. It does
not establish complete correction incorporation or clinical latest status.
Chapter 1/11 remain dated baselines; replaced chapters 2/4/9/10 remain excluded.

Preserve the indirect-evidence qualification for TMP-SMX consideration, contextual
infection screening/Strongyloides assessment accompanying urgent treatment,
individual review of leukopenia, usual rather than rigid cyclophosphamide/steroid
durations, and at least six months of sustained antibody negativity before
transplantation. No numerical toxicity threshold, drug dose, rescue regimen or
complete transplant clearance is added. Crossmark metadata is not clinical
currentness evidence.

### Source snapshots and separate rights

New IDs are `RN15-HD-SRC-BCR-202607`, `RN15-HD-SRC-UKKA-STOP-2023`,
`RN15-HD-SRC-NDT-2025`, `RN15-HD-SRC-CJASN-2017`,
`RN15-CMV-SOURCE-CONSENSUS-2025-20261007`,
`RN15-CMV-SOURCE-EMA-PREVYMIS-20261007`, `RN15-GBM-SRC-TREATMENT` and
`RN15-GBM-SRC-PREVENTION`. No old scope/date snapshot was rewritten.

G09 was free and is now BC Renal in the single source register. BC's
[use terms](https://www.bcrenal.ca/resource-gallery/Documents/About_BCR_Guidelines.pdf)
permit personal, clinical, non-commercial downloads; commercial reproduction
requires permission. KDIGO and the CMV consensus retain their recorded
CC BY-NC-ND/publisher conditions, UKKA and other publishers their distinct terms,
and EMA its own reuse limits. Original Renulus teaching is CC BY 4.0; this does
not relicense source prose, figures, tables, algorithms or full documents.
No third-party full material is in Git, and no access control was bypassed.

## Mapping and unresolved coverage

New mapping: `content/mappings/esen-eph-2026-10-07-depth2.json`. Its official
curriculum/blueprint evidence, hashes and actual October 5 checked date remain
unchanged. Five alignment rows change: `glomerular_diagnosis`, `hd_clearance`,
`hd_emergency`, `transplant_prevention`, `transplant_aftercare_gap`. Every other
alignment is exact. CMV teaching is shared between prevention/aftercare while
its eight assessment pins count once in aftercare. HD retains hypotension;
new `T20.O02` credit is a partial ongoing-care facet, not a forced `T23.O01`
emergency objective. No extra objective or arbitrary count quota was invented.

The receipt selects 245 mapped questions and 71 five-option questions. All eleven
domains stay partial; all 27 source-currency cells stay open. Existing CKD/urine,
cardiovascular/diabetes and urology family shortfalls remain 2, 1 and 4. Broad
anti-GBM dosing/prophylaxis/toxicity protocols, refractory disease, complete
transplant assessment, image histology, full HD prescription/home-HD/water-system
and emergency procedures, resistant CMV and wider recipient care remain gaps.
Required-cell targets and original review minima were not lowered. There are no
objective-link holds or objectives lacking a case link; this is structural
coverage evidence, not complete clinical teaching or examination readiness.

## Validation and handoff evidence

The successful bounded publication process used the existing `publish_snapshot`,
`validate_pack`, `validate_revision` against all seven ancestors,
`validate_review_evidence` and `check_required_cells.build_manifest`. Early draft
attempts stopped before publication on an overbroad alignment-status assertion,
the absent runtime G09 register entry and an inherited mapping-check-date
constraint; the final run preserves the existing supporting facet/date and uses
the explicit canonical register. No invalid draft entered the pack directory.
No pytest, server, model/engine/provider, installer or native application ran.

External evidence root: `C:/rn-finish-20261007/evidence/depth-publication`:

- `verification.json`: pack digest, seven ancestor hashes, new IDs, exact inherited
  counts, 50 base-blob comparisons and mapping/review outcomes.
- `renulus-foundations-1.4.0-review.json`: 108 artifact rows, 30 source rows, exact
  authored records and all original proposal reviews. SHA256
  `e5271ec5c20827bb78419c8f34cd230902d33165327a37d4d5287c2045303990`.
- `recovered-primary-identities.json`, `kdigo-selected-pages.json`,
  `kdigo-physical-237.png`, `kdigo-physical-239.png`: local targeted reading.

The mandatory inherited receipt remains untouched:
`C:/rn-finish-20261007/evidence/content-application/release/renulus-foundations-1.3.0-review.json`,
SHA256 `b9b259157b77e62b20995677ac8478afc39a1c828107c7283a6851d091f39c43`.
Recovered primary SHA256 identities (no repeated download):

| External original | SHA256 |
| --- | --- |
| BC July 2026 complications PDF | `a4b8e92617e098674aa37f5dc4c188c56c6bbf02852f36cf1deb608b84bc174f` |
| BC use terms | `084c14d5accb785ef5319271c264e7e79e267d63c65df3698493de9925a38baf` |
| UKKA STOP 2023 | `3c5c772d9bc4df58e839955ec9f5f3bc7031d0a48bff7367151fdf32a9dcc438` |
| CMV consensus XML | `5e9508b814eadde6b06cc1cabbd96f2f1ed23dcb1e783718c8c5fd2f619759a9` |
| EMA English product information | `db4998a6cb590006789107af9f09c4196d815ed441a57d076042c2223b8d34a9` |
| KDIGO retained combined PDF | `8ed871ec098c7eba1cfb0ff6bf2355a6c422166b2691aac138f0273307b2acff` |

Authoring is reproducible with `content/authoring/author_depth2.py --evidence-dir`
pointing outside the tree and `--prior-review` pointing to the inherited receipt.
Proposal hashes pin exact reviewed input; paired HD hashes allow only the known
CRLF/LF forms required by `.gitattributes`. Existing differing immutable outputs
are refused. Parent can cherry-pick the standalone publication commit, regenerate
the runtime source-register derivative, and then run its integrated activation
checks. This report does not approve that activation or any clinical-currentness
claim on its behalf.
