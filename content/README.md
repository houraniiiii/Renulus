# Original Renulus learning content

The latest authored pack is **1.2.0**: 27 topics, 57 objectives, 222 reserved
assessment questions and 50 staged synthetic teaching cases. It adds 44 original
five-option questions and 12 independent three-stage cases, with explanations
for every choice, primary-source locators and explicit case-stage support for
each objective. The new `T23.O03` objective addresses regional citrate
anticoagulation and protocol-dependent calcium/acid-base monitoring. Parent
integration owns runtime selection and installed acceptance.

Eleven finite teaching units add depth across every ESENeph domain: IgAN/IgAV,
established adult CDI, longitudinal CKD risk, anemia response, kidney-protection
safety, asymptomatic bacteriuria, Gitelman syndrome, PD response/catheter
decisions, HD delivery/tolerance, BK aftercare and pregnancy surveillance. Each
unit has four assessment items and a three-stage case; citrate has an additional
case. This is a concrete increment, not complete domain coverage. The mapping
retains named gaps in disease-specific treatment, doses, images/procedures,
rare conditions, dialysis operations and the wider curriculum.

The `2026-10-07-depth1` map selects **218 questions**. Four objective holds are
repaired in reviewed version-2 records: adequacy to `T20.O02`, URR to `T23.O01`,
cancer-remission candidate risk to `T21.O02`, and citrate to `T23.O03`. Their
stems, options, answer values, families and primary/secondary topic IDs are
unchanged. The four generic appraisal items remain General-only. Official
curriculum/blueprint evidence retains its actual October 5 check date. Only the
44 new questions use five options; all eleven domains remain partial and a
full examination simulation remains unavailable.

All 1.1.2 files, 47 source snapshots, 174 unchanged questions and 38 cases are
preserved. Seventeen scoped source snapshots bring the total to 64: twelve
support the new content/revised metadata and five record correction relationships
for IKMG, ISTH diagnosis, AAV, CKD-MBD and urine eosinophils. The new PD source
also records both peritonitis corrigenda and teaches the corrected units.
Correction-impact findings do not imply new keys, revised source originals or
complete clinical currency. All **27 update-source cells remain open**; MGRS
2026 comparison, overdue UKKA scopes and other named notice/current-treatment
limits remain separate. Original content is CC BY 4.0; clinical references
retain their own rights. No source bodies or restricted examination material
are bundled.

`tools/content/author_depth.py` reproduces the immutable pack and mapping without
network or inference. Staging, its 60-row item review and execution receipts
must remain outside Git. For this delivery, using the assigned public Python
interpreter, the authoring commands are:

```powershell
python -B tools/content/author_depth.py --evidence-dir C:/rn-finish-20261007/evidence/content/release
python -B tools/content/check_required_cells.py --release content/packs/renulus-foundations/1.2.0 --review-evidence C:/rn-finish-20261007/evidence/content/release/renulus-foundations-1.2.0-review.json --output C:/rn-finish-20261007/evidence/content/release/required-cells-1.2.0.json
```

The receipt checks all 57 objective-to-question/case links while retaining the
56 original objective targets and the original four expansion items/two skill
types per topic. It requires reviewed successor versions for revised expansion
items instead of silently losing their pins or counting new depth as original
expansion. The adopted bank minimum remains 150. Earlier required-cell receipts
still reproduce unchanged. Source/key/stage checks are assistant review and
consistency evidence, not independent clinical review or measured efficacy.

## Historical 1.1.2 authoring and integration record

The 1.1.2 release contains 27 topics, 56 objectives, 178 reserved
assessment questions and 38 staged synthetic teaching cases. It finishes the
interrupted finite draft with 18 original questions and 12 cases. The eight
previously empty mapped facets now have small, explicitly partial question/case
sets: recurrent UTI, Alport-spectrum investigation, PD infection/access, ongoing
HD access/unit care, BK recipient aftercare, contraception, adolescent transition
and last-days supportive care. All six previously absent objective-to-case links
are present. The adopted minimum remains 150; no target is reduced.

The dated `2026-10-05-launch1` ESENeph map selects 170 questions, keeps the
eight General-only exclusions, and retains the official evidence pins and
four-choice format limitation. It is partial preparation. Five hyperkalaemia
questions and one case advance only their citation versions to the already
present, directly checked July 2026 source. Historical keys, answer choices,
families, objectives, source snapshots and all earlier packs remain intact.
The 12 new scoped source records make 47 clinical references; they do not
clear the 27 update-source cells or the inherited correction holds.

`tools/content/author_launch_gaps.py` reproduces 1.1.2, its mapping and the
36-row source/key review evidence without network or inference. The new
`content/required-cells/renulus-foundations-1.1.2.json` receipt can be checked with
`python tools/content/check_required_cells.py --release content/packs/renulus-foundations/1.1.2 --output content/required-cells/renulus-foundations-1.1.2.json --check`.
The existing command without `--release` still reproduces the historical 1.1.1
receipt. See `docs/implementation/finalise-esen-eph.md` for the handoff and
bounded validation. Further depth, dose algorithms, rare-disease breadth and
source-wide currency work remain visible; they are not new manufacturing gates.

## Historical 1.1.1 authoring and integration record

`packs/renulus-foundations/1.1.1` is an original, versioned CC BY 4.0 pack: 27
topic identities, 56 original objectives, 26 staged synthetic cases and 160
single-best-answer items. It adds dated partial ESENeph mapping to the unchanged
1.1.0 bank. Released 1.0.0 (52 questions / 14 cases), 1.0.1 (106 questions / 20
cases) and 1.1.0 (160 questions / 26 cases) remain unchanged; their immutable
item and citation snapshots are retained. R01 in
`docs/SOURCES.md` is the pack origin. Only labels
and topic IDs from the historical reference taxonomy are adopted; its original
questions, data and runtime were never imported. Objectives and cases here are
newly authored. Primary sources supply medical facts and locators, not copied
prose, figures, algorithms or questions.

The bank covers CKD (including anemia), AKI, dialysis, transplantation,
glomerular disease, potassium/acidosis, sodium/water, CKD-MBD, blood pressure,
diabetic kidney disease, ADPKD, drug stewardship, nutrition, supportive care,
vasculitis, lupus, tubular/interstitial disease, stones/obstruction, TMA,
monoclonal kidney disease, pregnancy and extracorporeal mechanisms. `coverage.json` records actual
case/item/objective links and gaps across the whole taxonomy. A topic label or
case tag alone is not evidence that its objectives have been covered. All 27
topics and 56 objectives have explicit general item/case links inherited from
1.1.0; links do not establish mastery, complete depth or an examination blueprint.

The formal mapping checked October 5, 2026 pins the official hub-linked undated
blueprint and 2022 curriculum by PDF SHA-256, page and edition. It maps 152 exact
reviewed-bank question versions across 11 domains, 26 supporting cases and 55
objectives; one objective supplies generic curriculum support. Eight questions
remain General only: four appraisal items without an exam-domain assignment and
four objective mismatches requiring later reviewed metadata versions. All 160
questions still have four options, while the official examination uses five.
Every domain remains partial, with explicit missing facets and family capacity
shortfalls. Full exam simulation and complete blueprint coverage are unavailable.
Original mappings are in `mappings/esen-eph-2026-10-05.json` and the canonical
release manifest; source PDFs and official exam questions are not distributed.

`required-cells/renulus-foundations-1.1.1.json` reconciles the adopted 1.1.0
breadth targets with the immutable release and review evidence. The original
27 topics, 56 objective links, minimum 150 bank questions, four expansion
questions per topic and two reviewed skill types per topic remain required.
Those bank minima are met. Case cells require explicit objective links; secondary
tags alone cannot satisfy them. Cited teaching stages supply linked evidence,
not complete explanations of every topic. All 56 objectives have question
links; 50 have case links. Six objectives have no explicit teaching case,
including both CKD-anemia objectives. These individual cells remain visible.
The separate update-source cells
remain open: all 35 clinical source records are dated final baselines, not a
new latest-final/correction/retraction clearance. Eight programme facets have
no pinned items, and the HD domain has no focused staged case. The manifest
therefore reports `complete_content_coverage: false`. Official indicative
weights are not newly imposed full-exam minima. Human review is neither
invented nor added as a new acceptance prerequisite.

The 108 added questions include 36 mechanisms, 34 interpretation and 38 common
reasoning items, with four per topic and at least two skills per topic. The
review evidence JSON records this checked matrix. Twelve mixed-domain cases
connect kidney findings with medicines, infection, pathology, extracorporeal
delivery, nutrition, donor autonomy, pregnancy, cardiovascular signals and
patient goals. Each case has three cited stages.

Every item and case explicitly states `assistant_reviewed` and
`independent_human_review: false`. The assistant checked primary public
recommendation/section locators, the intended single key and distractors. This
is not a fabricated clinician review, independent review, efficacy study or
clinical-accuracy certification. Source metadata records exact final editions
and dated baselines. Current-source checks and revisions remain ongoing work.

The pack is public original content, not a secret exam. All bank questions use
`assessment_reserved`; they must never be indexed or retrieved into teaching,
Explain or generated practice. `ContentRepository.teaching_material()` exports
only objectives and teaching cases. Cases are synthetic authored resources;
this repository has no operation for saving a user's case.

Validate without network or inference:

```powershell
python tools/content/validate_pack.py content/packs/renulus-foundations/1.1.1 --predecessor content/packs/renulus-foundations/1.0.0 --predecessor content/packs/renulus-foundations/1.0.1 --predecessor content/packs/renulus-foundations/1.1.0 --review-evidence content/reviews/renulus-foundations-1.1.1.json
python tools/content/check_required_cells.py --check
python -m pytest tests/content -q
```

`tools/content/author_foundations.py` retains the original authoring source and
can reproduce the same snapshot. It refuses to overwrite differing published
files. A correction is a new question version with the same stable family ID,
and a new pack revision selecting it. Key corrections identify their predecessor
and withdraw it atomically during activation. Historical versions remain
available for pinned attempt evidence. Withdrawal prevents new selection, not
historical resolution. Never silently update a published JSON snapshot.

`tools/content/author_expansion.py` reuses that publisher for additive releases.
It refuses to change released pack or review-evidence bytes. Review files record
item keys, skill types, primary locators, dated checks and access limits. The CLI
checks those records and pinned source metadata against the payload and checks
immutable ancestry against each selected predecessor. It cannot perform the
medical reading or infer medical truth from a review flag. Source originals and
ERA bank/manual material are excluded.
Revision checks also reject reduced adopted topic/question targets or removal
of an existing objective identity, including after a topic version advances.

`tools/content/author_eseneph.py` reproduces the 1.1.1 release, original mapping
and mapping-review evidence. Questions, keys, cases, clinical source snapshots
and general coverage are byte-identical to 1.1.0. Topic mapping metadata advances
to version 2. Mapping review is an assistant interpretation of supported scope;
it is not a new clinical-source review or independent human review.

The integrator applies `runtime/renulus/content/schema.sql` through the canonical
ledger. Content adds no alternate service, provider, model, private dataset or
engine dependency. Packaging must include the selected pack directory and may
set `services.registry['content_pack_root']` before creating its router.
Scoped licence terms are in `content/LICENSE`; source rights remain independent.

Startup selects the highest numeric published bundle in the
`renulus-foundations` lineage. It installs on a fresh profile or upgrades an
older active version using the existing canonical SQLite transaction. It
preserves historical pins, inactive profiles, previously installed inactive or
withdrawn targets, newer active versions and different active lineages. Draft
and empty release folders are excluded. A corrupt published latest bundle or
immutable-version conflict leaves the existing bank intact and reports the
failed activation; it does not silently fall back to an older bundle.

The integrator may set an exact selection before router creation:

```python
services.registry["content_pack_selection"] = {
    "id": "renulus-foundations",
    "version": "1.1.1",
    "upgrade_from": ["1.0.0", "1.0.1", "1.1.0"],
}
```

Omitting `version` uses latest bundled selection. Omitting `upgrade_from` permits
any older active version in that lineage; an explicit list limits upgrades.
`GET /api/v1/content/bootstrap` and `services.registry["content_bootstrap"]`
return the startup outcome and any activation error without question content.
`GET /api/v1/content/manifest` remains the current active selection, including
later manual installs. Reactivating an eligible inactive bank requires an
explicit install; a withdrawn bank cannot be reactivated. No public question
stem/detail route is added.

`ContentRepository.track_metadata()` and `GET /api/v1/content/tracks` return
the same direct JSON list for General and ESENeph. Counts and objective support
come from active nonwithdrawn pins in one SQLite read snapshot. Public metadata
includes dated sources, explicit gaps, format limits and assistant-review status,
without stems, options, keys or learner records. `list_question_summaries` and
`GET /api/v1/content/questions?track=esen_eph` select only the 152 mapped
reviewed-bank pins; General remains 160. The existing `topic_id` and `domain`
filters still refer to stable topic IDs. Parent-owned assessment and Flow
consumers must preserve the partial-preparation and generated-practice labels.
