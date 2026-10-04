# Original Renulus learning content

`packs/renulus-foundations/1.0.0` is an original, versioned CC BY 4.0 pack: 27
topic identities, 56 original objectives, 14 staged synthetic cases and 52
single-best-answer items. R01 in `docs/SOURCES.md` is its origin. Only labels
and topic IDs from the historical reference taxonomy are adopted; its original
questions, data and runtime were never imported. Objectives and cases here are
newly authored. Primary sources supply medical facts and locators, not copied
prose, figures, algorithms or questions.

The bank covers CKD (including anemia), AKI, dialysis, transplantation,
glomerular disease, potassium/acidosis, sodium/water, CKD-MBD, blood pressure,
diabetic kidney disease, ADPKD, drug stewardship, nutrition, supportive care,
vasculitis and lupus kidney involvement. `coverage.json` records actual
case/item/objective links and gaps across the whole taxonomy. A topic label or
case tag alone is not evidence that its objectives have been covered. Formal
ESENeph mappings, sufficient examination-length sessions and a complete
curriculum are absent.

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
python tools/content/validate_pack.py content/packs/renulus-foundations/1.0.0
python -m pytest tests/content -q
```

`tools/content/author_foundations.py` retains the original authoring source and
can reproduce the same snapshot. It refuses to overwrite differing published
files. A correction is a new question version with the same stable family ID,
and a new pack revision selecting it. Key corrections identify their predecessor
and withdraw it atomically during activation. Historical versions remain
available for pinned attempt evidence. Withdrawal prevents new selection, not
historical resolution. Never silently update a published JSON snapshot.

The integrator applies `runtime/renulus/content/schema.sql` through the canonical
ledger. Content adds no alternate service, provider, model, private dataset or
engine dependency. Packaging must include the selected pack directory and may
set `services.registry['content_pack_root']` before creating its router.
Scoped licence terms are in `content/LICENSE`; source rights remain independent.
