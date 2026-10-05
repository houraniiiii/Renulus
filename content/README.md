# Original Renulus learning content

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
