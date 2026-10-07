# Bounded Updates topic discovery repair — October 7, 2026

Prepared on `codex/finish-topic-discovery-20261007` in
`C:/rn-finish-20261007/lanes/topic-discovery`, from clean base `4e4597a1`.
The lease covers only `runtime/renulus/updates/literature.py`, the new
`runtime/renulus/updates/topic_queries.py`,
`tests/updates/test_literature_refresh.py`, and this report.

## Problem and query contract

The parent's installed cb59beb2 receipt at
`C:/rn-finish-20261007/evidence/connected/updates-installed-cb59-01/result.json`
records an October 7 T11 check with state `checked`, zero records, zero hits and
no truncation. Its later `review_missing` journey failure does not turn that
successful empty search into a transport failure. The installed label is exactly
`Tubular and interstitial disease`; the prior query used that entire curriculum
heading as a title/abstract phrase. A curriculum heading is not necessarily a
phrase used in publications.

The new static table translates **24 exact installed ID/title pairs** into
bounded title/abstract concepts. Selection requires both components to match
exactly, including title case and whitespace. Renamed IDs, different titles,
custom topics and unlisted pairs retain the escaped literal title expression.
The existing service still requires every requested topic to be installed.
There is no label splitting, all-word intersection, fuzzy identity matching,
prompt/case input, model query generation, online expansion or query fallback.

T11 now produces this expression for the same October 7, 30-day window:

```text
(TITLE_ABS:"interstitial nephritis" OR TITLE_ABS:"tubulointerstitial nephritis" OR TITLE_ABS:"tubulointerstitial disease" OR TITLE_ABS:"renal tubular disorders" OR TITLE_ABS:"renal tubular acidosis" OR TITLE_ABS:"Fanconi syndrome" OR TITLE_ABS:"tubulopathy" OR TITLE_ABS:"tubulopathies" OR TITLE_ABS:"acute tubular injury") AND FIRST_PDATE:[2026-09-07 TO 2026-10-07] sort_date:y
```

T08, T10 and T21 already have useful literal terminology and keep their original
phrase queries. In particular the `86fdbe90` T21 relevance contract remains:

```text
TITLE_ABS:"Kidney transplantation" AND FIRST_PDATE:[2026-09-07 TO 2026-10-07] sort_date:y
```

All alternatives are grouped before the explicit date AND. General concepts
such as complement, nutrition or pregnancy additionally require a title/abstract
match for kidney, renal, hemodialysis, haemodialysis or peritoneal dialysis.
That kidney scope applies to every broad alternative. Specific renal concepts
such as interstitial nephritis, lupus nephritis and nephrolithiasis need no
extra generic kidney word. Every leaf uses a quoted `TITLE_ABS` phrase.

The one-request-per-distinct-topic behavior, maximum five selected topics,
1–90-day window, JSON/core metadata, 25-record cap, `sort_date:y`, visible
hit-count/truncation, pending review state, deduplication and dated failure
handling are unchanged. There is no pagination or retry. Exact-identity
refresh remains `EXT_ID:… AND SRC:…`, page size one, without topic/date/sort.
Abstracts and bodies are not retained by the metadata recorder.

## Bounded editorial review

The lane assistant checked the installed 1.2.0 topic labels/objectives against
the receipt's 27 installed options and reviewed the following search choices.
This is an engineering/editorial review of query scope, not an independent
clinical review or a claim of exhaustive coverage. The table is a small fixed
set of discovery concepts; it is not a curriculum ontology or a new taxonomy.
Exact emitted queries for all 27 topics are preserved in the external
`reviewed-queries.json` receipt.

| Installed topic | Selected concepts and relevance boundary |
| --- | --- |
| T01 Foundations of kidney science | Kidney-scoped physiology, anatomy, histology and tubular transport. |
| T02 Clinical assessment and diagnostics | Kidney-scoped diagnosis/diagnostics, biopsy, urinalysis and glomerular filtration. |
| T03 Sodium, water and volume | Kidney-scoped sodium disorders, water balance, fluid overload and volume depletion; selected US/UK spellings. |
| T04 Potassium and acid-base | Kidney-scoped potassium disorders, acidosis and alkalosis; selected US/UK spellings. |
| T05 Mineral metabolism and bone | Kidney-scoped mineral metabolism, bone disorder, hyperparathyroidism and osteodystrophy. |
| T06 Acute kidney injury and acute kidney disease | Either individual renal phrase; neither requires the entire compound heading. |
| T07 Critical care nephrology | Kidney-scoped critical/intensive care and sepsis. |
| T09 Hypertension and vascular kidney disease | Kidney-scoped hypertension, renovascular disease and renal artery stenosis. |
| T11 Tubular and interstitial disease | Interstitial/tubulointerstitial nephritis, tubular disease/disorders, acidosis, Fanconi syndrome, tubulopathies and acute tubular injury. No standalone interstitial or tubular alternative. |
| T12 Cystic and inherited kidney disease | Cystic/polycystic and inherited kidney disease, hereditary nephropathy and Alport syndrome. |
| T13 Stones and obstruction | Kidney stones, nephrolithiasis, urolithiasis, obstructive uropathy and hydronephrosis. No standalone stones or obstruction. |
| T14 Diabetes and metabolic kidney disease | Diabetic nephropathy or kidney-scoped diabetes, diabetic, metabolic syndrome and obesity concepts. |
| T15 Thrombotic microangiopathy and complement | Kidney-scoped TMA, complement and selected hemolytic uremic syndrome spellings. Complement alone is insufficient. |
| T16 Kidney disease in systemic illness | Lupus nephritis or kidney-scoped vasculitis, systemic sclerosis and scleroderma. |
| T17 Infection in nephrology | Kidney-scoped infection/infections and vaccination. |
| T18 Onconephrology and paraproteins | Onconephrology, MGRS written in full, cast nephropathy and paraprotein-related kidney disease. No unscoped cancer/paraprotein query. |
| T19 Medicines and nephrotoxicity | Nephrotoxicity/nephrotoxic/drug-induced kidney injury, or kidney-scoped drug dosing and pharmacokinetics. |
| T20 Dialysis and kidney failure therapies | Named dialysis modalities, kidney/renal replacement therapy and kidney failure. |
| T22 Procedures and interventional nephrology | Kidney/renal biopsy, dialysis access and interventional nephrology. |
| T23 Extracorporeal therapies and apheresis | Kidney-scoped apheresis, plasma exchange and extracorporeal therapy/therapies. |
| T24 Life-course and special populations | Kidney-scoped pregnancy, pediatric/paediatric, frailty, older adults and transition. |
| T25 Nutrition, prevention and rehabilitation | Kidney-scoped nutrition, diet, exercise, rehabilitation and prevention. |
| T26 Supportive care, ethics and evidence | Kidney-scoped supportive/conservative/palliative care, shared decisions, ethics and evidence-based practice. No generic evidence-only search. |
| T27 Kidney interfaces with other specialties | Cardiorenal, hepatorenal and pulmonary renal syndromes. |

Syntax facts reuse the primary documentation already recorded in
[the earlier Updates report](finish-updates-query-20261007.md):
[Europe PMC REST sorting](https://dev.europepmc.org/RestfulWebService),
[the official TITLE_ABS announcement](https://blog.europepmc.org/2024/01/europe-pmc-2023-a-year-in-review.html),
[Europe PMC phrase/Boolean help](https://europepmc.org/help), and
[the dated EMBL-EBI reference guide](https://dev.europepmc.org/docs/EBI_Europe_PMC_Web_Service_40_Reference.pdf).
No new documentation fetch or live article search was needed or performed.

## Single focused offline run

**28 passed, zero failed/errors/skips, 15.41 seconds**, exit 0. One invocation,
one Python process, only `tests/updates/test_literature_refresh.py`.
CPython 3.14.4, pytest 9.1.1, pytest-asyncio 1.4.0. The single warning is the
existing Starlette TestClient/httpx deprecation; no dependency was changed.
UTC start/end: `2026-10-07T14:26:36.036171+00:00` to
`2026-10-07T14:26:51.747949+00:00`; runner elapsed 15.712 seconds.

Exact command, from the lane worktree:

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
& 'C:/Users/karol/Documents/t3-workspaces/Renulus-wt-integration/.venv/Scripts/python.exe' -B 'C:/rn-finish-20261007/evidence/topic-discovery/run_offline_tests.py' 2>&1 | Tee-Object -FilePath 'C:/rn-finish-20261007/evidence/topic-discovery/pytest.stdout.log'
```

The retained runner disables plugin autoload, bytecode and pytest caching;
loads only pytest-asyncio plus its local transport guard; blocks real Updates
fetches, external sockets/DNS/datagrams, provider/engine imports and subprocess
launches. Guard violations: **zero**. Existing fixtures activate only content
and Updates. All SQLite profiles and pytest temporary files stay beneath the
external evidence root. The content bootstrap reads bundled teaching metadata;
there is no Library/source-body import or user-profile access.

The tests establish:

- Actual installed ID/title selection and outgoing queries for all 24 mapped
  headings, in batches of at most five, with positive and negative renal-topic
  examples and title-only/abstract-only matching.
- T11 nephritis, tubular disorders, Fanconi syndrome and tubular acidosis;
  rejection of interstitial lung disease, tubular adenoma and Fanconi anemia.
  Additional T06, sodium, complement and apheresis contrasts catch all-label
  matching and missing kidney scope. A phrase cannot span title and abstract.
- Strict ID/title pairing, case/whitespace-sensitive fallback, preserved T08,
  T10 and T21 queries, and the previous five quote/backslash/operator/Unicode
  escaping cases.
- API rejection of prompt, case-text and custom-query fields; unknown-topic
  private sentinel rejection before HTTP; six-topic and out-of-range windows
  rejected before HTTP. Exact 1-, 7-, 30- and 90-day date examples are retained.
- Zero results remain a successful check. Twenty-five returned records with
  26 hits expose truncation; duplicate selection does not make another request.
  Failures preserve the prior successful-check timestamp, and malformed or
  oversized metadata remains a failure. No automatic retry/pagination occurs.
- Pending metadata-only persistence, abstract/body exclusion, existing T21
  unrelated-title replay, deduplication and old-record exact refresh semantics.

The offline phrase/Boolean evaluator is deliberately small and independent of
the production term table. It verifies the emitted request contract against
synthetic examples; it is not Europe PMC's tokenizer, stemmer or server, and
does not establish live precision/recall or installed acceptance.

## Exact source and receipt identities

SHA-256 values of the three tested changed files:

| Path | SHA-256 |
| --- | --- |
| `runtime/renulus/updates/literature.py` | `f1c78e06e4f779f589893ed1c709d46a8d900eabda2c8cae39977520df7336a4` |
| `runtime/renulus/updates/topic_queries.py` | `2a250b19670727427111ebd0055bd6aac578f6228d9ea42cf1b1525b55bc096e` |
| `tests/updates/test_literature_refresh.py` | `52a3518346012fa8c7f1b5ce6a365aa652bdfd5874cd21003244258c87af976d` |

Raw evidence stays outside Git at
`C:/rn-finish-20261007/evidence/topic-discovery`. `source-hashes.json` also
identifies unchanged fixtures, topic labels and project configuration used by
the run. JUnit and console logs preserve the exact 28 test identities.

| Receipt | SHA-256 |
| --- | --- |
| `pytest.xml` | `c13bfdacc66a7916c9bd896a9c8da6a3e8ec43944ca69ad99686ebd235b908f2` |
| `pytest.stdout.log` | `29daf87d516563da7292c201e9ae8033706bd9494538b1028780d7f0176e8faf` |
| `run_offline_tests.py` | `4767fdea3373c9f60abe940703182fb221c531ab485eefc0978630c9e7a370db` |
| `test-run.json` | `b2d9ffe3de0bbb0abb5476b1bba73bd4aac6393983f07f18af451b265bb07835` |
| `reviewed-queries.json` | `ad5d0b4a8ea355bbfd72d20e046f091e43130735cde66572ae66b7d9c54a8d80` |

`git diff --check` passes. The implementation and tests were unchanged after
the successful run. `handoff.json` outside the checkout identifies the final
commit and clean branch state.

## Handoff and limits

The parent owns integration, live literature queries, the hidden installed
Updates review/affected-history journey and matching packaging. This lane
does not block its existing canonical-title continuation. Retrieval evidence,
literature/service, content, UI, schema, dependencies and GitHub are untouched.
No provider/model, engine, native app, paid usage or private state was accessed.

The mappings are deliberately selective and can miss publications using other
terms. Kidney-scoped broad concepts still need educational review of returned
metadata. A zero result remains valid; the repair does not guarantee a nonempty
October 7 T11 response. It changes future discovery queries only and does not
purge or reclassify previously discovered entries. Currentness, exhaustive
coverage, clinical relevance and full-text permission are separate judgments.
