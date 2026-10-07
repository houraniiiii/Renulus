# E06 import preparation — October 5, 2026

**The exact pending E06 set now has a validated 28-file import plan, totalling
7,477,667 bytes: 22 PPTX, five DOCX and one XLSX.** These supported files span
23 parent DOIs. All 29 reviewed proposals span 24 parent DOIs in Pediatric
Nephrology, journal 467. Receipt 487 remains outside the import entries because
its EMF part returns `unsafe_office` (422). No real original was admitted to any
profile in this lane.

This bounded follow-up used branch `build/finalise-source-adoption`, baseline
`9d26f1eedf31cd488b9aab5837a105ee152d9efa`, and the exact publisher-scope report,
review JSON and individual proposals identified by report-only commit
`e5d0d4d00fb89b7941bc8c67116684eec9033018`. The review JSON's report commit was
independently checked. The earlier component report is already in the baseline;
no previous report was imported again. Existing source register, runtime,
schemas, selected engines, Flow interface and subscription policy were unchanged.

The worker-owned ignored handoff consists of `.local/e06-source-adoption-plan.json`,
`.local/e06-source-adoption-verification.json`, `.local/e06-source-adoption-audit.json`,
`.local/prepare-e06-source-adoption.py` and
`.local/verify-e06-source-adoption-evidence.py`. The preparer has no actual
adoption mode; its API verification uses generated synthetic OOXML bytes only.
The frozen plan SHA256 is:

`d346fc4b7b82a724dfe7cf2b276ddd0ff3e83b99535957ab68f9437567b27e05`

The synthetic verification receipt SHA256 is:

`5ae29dbc57d4a8ddf5c4ca2b6b71fffaf20616fd41c311223fcbaa23ac2194b0`

Each import entry retains its exact original path, SHA256, byte size, filename,
source ID, parent DOI, canonical article and official supplement URLs, authors,
publication/acquisition/check dates, CC BY notice and policy references. Its
options are copied unchanged from the individual proposal. Keys retain
`office-adoption:E06:<original-sha256>`; the plan also records the expected
request hash used by the current repository's idempotency binding. Dates and
options must remain frozen on retries. Attribution preserves the author/source,
DOI, licence link, original change notice and supplied component credits.

| Operation | Per-file proposal retained |
| --- | --- |
| Display, local cache, index, embedding, model input, derivation | True |
| Evaluation, redistribution | False |

The rights rationale remains the inherited dated combination of the actual
article CC BY notice, exact official DOI-linked supplement association and
publisher scope evidence. It is a supported applicability inference; the
current sample agreement was not asserted to be each older article's signed
agreement. This follow-up reconciled the supplied evidence rather than
reopening acquisition or making a new blanket journal grant. Full primary
references and component qualifications remain in the ignored plan.

The 28 candidate receipt lines are 415, 418, 422, 423, 433, 437, 442, 444, 445,
446, 454, 456, 458, 464, 470, 472, 474, 478, 482, 490, 492, 501, 503, 505, 507,
522, 533 and 538. Receipt 487 is recorded separately as a format hold, with
supported publisher scope and no import instruction. The exact existing
classified plan and queued receipt were read as metadata only: their 29 E07/L03
files have zero original-hash or idempotency-key overlap with this E06 batch.
Their originals and learning-profile records were not inspected or repeated.

| Observed check | Outcome |
| --- | --- |
| Serial identity, size and unchanged-original checks | All 29 matched; no sibling discovery or manifest edits |
| Fresh inert Office validation at the current baseline | 28 accepted; receipt 487 refused with `unsafe_office` (422) |
| Current import-options model and unchanged-proposal checks | All 29 valid and exact |
| Generated synthetic Office files through the supported API | All 28 accepted as queued; canonical rights, attribution, metadata and app-owned synthetic bytes verified |
| Exact API retries in the same process and after reopening the synthetic profile | 28 in each pass returned the same document, revision and job |
| Same key with changed options | All 28 returned `idempotency_conflict` (409) |
| Refused synthetic requests | Nine checks added no durable rows: four required permissions, temporary scope, EMF, malformed OOXML, missing options and invalid session |
| Final synthetic state | 28 queued jobs, zero passages, no derived index |
| Frozen-plan audit | Plan/receipt hashes, unchanged input snapshots, exact metadata copies and all 28 synthetic originals/rights reconciled |

Identity and current-format preparation took 7.040 seconds; the synthetic API
checks took 47.083 seconds. Both used the existing integration Python environment
with bytecode writes disabled. An audit guard prohibited external network,
child/native launches, credential-file opens and heavy engine imports. No
application lifespan, ingestion worker, extraction, OCR, embedding, provider
request or native application ran. The public environment emitted a
Starlette/httpx deprecation warning; it did not fail these checks and no
dependencies were changed. These are admission and persistence checks, not
installed-app or full end-to-end acceptance.

Qualifications remain explicit. Receipt 464 retains two visually unread WDP
credit parts; receipt 487 retains the unread EMF part. The three parts were not
decoded. Receipts 423 and 456 preserve BioRender creation/creator/link credits
and the completed-graphic restriction; no standalone icon permission is added.
Receipt 505 preserves its unnamed template permission reminder. The original
notices and any subsequently discovered component exception continue to apply.
Receipts 522 and 533 retain `historical_legacy_review_required`. Every entry
retains `latest_final_verified=false` and `content_reviewed=false`; no
currentness, clinical accuracy, assessment-key review, evaluation or
redistribution approval is claimed.

The parent owns actual adoption while the native app and backend are closed.
Pin the plan hash, recheck each exact original immediately before submission
and reconcile any target idempotency binding against its expected request hash.
Submit unchanged raw bytes to `POST /api/v1/library/import/file` with the filename
and JSON-encoded options headers; do not enter the application lifespan or
start ingestion during admission. Verify returned canonical rights/attribution
and app-owned originals, then record actual conversion, original access,
locators and search readiness under the parent's helper/native slot. The
worker did not read the real learning profile, so newer target admissions
remain a parent preflight check. Queue admission alone establishes no useful
extraction, embedding or retrieval result.

Only this report is versioned. Exact source identities, imported synthetic
proof state and preparer/audit scripts stay in this worktree's ignored `.local`.
No source originals, acquisition manifests, other sessions, account state or
native installation were written; no push, merge or deployment was performed.
