# OpenCode foundation implementation handoff

2026-10-10. Branch `codex/opencode-foundations`, worktree
`C:/Users/karol/.codex/worktrees/opencode-foundations/repo`.

## Scope and inherited work

The owner requested subagent review of the completed Design C session and plans,
local integration/commits, the first important foundation tickets in a worktree,
the named implementation/TDD skills, and UI testing. The integration task chose
the independent **H01 and H24** frontier. Both are complete for their local
foundation acceptance. H02 is next; later migration, account,
context, role-routing and release tickets are not implicitly completed here.

The worktree starts from the final Design C handoff
`c2bd896420fb88f76d63ca576414dbbba182f4c2`. H00 is already repaired in that
baseline and was not reimplemented. The current planning documents now consume
the final mounted-App evidence rather than its earlier pending rerun.
The immutable 99-file research snapshot remains unchanged. Its manifest SHA-256
is `446ccf39b0d86afca914b36b43973759f14384771452dbfd2aaef39701901938`.
All 99 captured Git blobs match the manifest's committed hashes. This fresh
check corrects an earlier hash copied into the historical reconciliation note;
the historical text is retained with an explicit correction appended there.
See the [Design C handoff](DESIGN_C_OPENCODE_HANDOFF.md) and
[H00 reconciliation](../research/2026-10-10-opencode-integration/h00-handoff-reconciliation.md).

Six implementation/reconciliation lanes covered the current plans, source
cohort, contracts/profile preparation, Python/Node IPC, memory shutdown and
hidden UI verification. The parent integrated the real SDK facade and desktop
quit ordering. Independent standards and specification reviewers examined the
combined changes; lane reviews and red/green receipts are recorded separately.

## Implemented behavior

| Slice | Result | Primary evidence |
| --- | --- | --- |
| H01 | A persistent managed OpenCode host, actual SDK loop/native SQLite, prepared paired-store identities, policy-before-dispatch, held recovery, native cancellation, exclusive store ownership and bounded close. Authenticated Python/Node IPC binds all request identities, retains late replies, reserves control capacity and drains output before clean exit. | [Host evidence](opencode-foundations-h01.md), [IPC contract/evidence](opencode-foundations-ipc.md), [shared contracts](../../packages/contracts/harness.md) |
| H24 | Memory executor/finalizer ownership survives coroutine cancellation. Closing seals admission before joining producers, keeps providers/reply capacity alive, retains admitted request ownership, and releases dependencies only after actual settlement. The desktop requests an authenticated drain before terminating its owned backend. | [Memory and shutdown evidence](opencode-foundations-h24.md) |
| Design C regression | Existing Memory, Library, reader and unsent cited Chat behavior is checked through the hidden app-scoped controller, using managed CPU helper assets and a synthetic profile. | [UI evidence](opencode-foundations-ui.md) |

The runtime is source commit `4b6fea2875e4f2e3e8a8fee181803e54f7056845`,
source package label 2.0.26, Effect 4.0.1 and managed Node 26.4.0 x64. The
published SDK package with the same version label has a different graph and is
not substituted. The final copied closure contains 520 packages and 37,845 files;
inventory SHA-256 is
`146d6a4f63a1a699c749d4ede05cb8fa944181ea62e4dbf8dbd0f11ac3e6bd74`.
No Renulus upstream source-code patch was needed. Staged package metadata
rewrites, upstream dependency patches, hashes and licences are recorded in
[the provenance ledger](../../upstream/opencode/UPSTREAM.md) and
[patch register](../../upstream/opencode/PATCHES.md).

## Local commits

| Commit | Change |
| --- | --- |
| `fc69a8e6` | Retain memory-thread ownership through actual shutdown settlement |
| `36777c27` | Authenticated application drain and Electron backend settlement |
| `ecc3367b` | Seal producers before draining admitted HTTP/module work |
| `29d14786` | Keep cancellation and release bound to the registered provider owner |
| `b5101da0` | Pinned OpenCode host, paired contracts, native SDK tests and managed IPC |
| `1a228c29` | Desktop quit ordering and authenticated-neutral route inventory |
| `9a10562a` | Correct the stale Library supported-format test expectation |
| `ced998e6` | Keep Notes history actions behind the saved-revision refresh; align the Updates test with explicit false flags |
| `f6bdb589` | Make an already settled memory close repeatable after its original event loop exits |
| `b6a4a7da` | Clear open Notes history after successful deletion acknowledgement |
| `e57e4d89` | Assemble assessment fixtures with their required owners and select historical packs before bootstrap |
| `8c74f1e9` | Consolidate the hidden UI source, lifecycle and screenshot evidence |
| `756c8ebc` | Replay an already settled application drain after its original event loop exits |
| `262e7e3e` | Reopen the Today test with a fresh application owner over the same seeded profile |
| `200f0627` | Record hidden UI startup/close on the final H24 production bytes |
| `4b6e037b` | Finalize the memory/shutdown and exact backend coverage ledger |
| `936ca4aa` | Assemble Updates fixtures with real owners and review corrected exact copies |

These commits are local. The canonical Design C checkout and research checkout
were not reset or merged over; the isolated branch contains the final Design C
baseline and all implemented foundation changes.

## Validation ledger

Counts below identify individual runs; overlapping suites are not added together.

| Check | Result and receipt |
| --- | --- |
| Shared contracts and profile preparation | 102 passed, including concurrent initialization, real Windows junctions, finite JSON, schema parity and existing typed identity/retention checks; [contract evidence](../../packages/contracts/harness.md#bounded-validation-evidence) |
| Direct real SDK and store ownership | 13 passed, zero skipped; `C:/Renulus/scratch/oc-foundations/host/sdk-final-02.xml`; consumer typecheck passed |
| Python transport | 46 passed; `C:/Renulus/scratch/oc-foundations/ipc-sdk/receipt.json` |
| Actual Node SDK through Python IPC | 14 passed, zero skipped; `C:/Renulus/scratch/oc-foundations/ipc-sdk/final-sdk.xml`; tests are explicitly opt-in when the reviewed artifact is absent |
| Electron backend and child lifecycle | 36 passed, including an owned real Windows child-exit check; H24 backend receipts |
| H24 final focused shutdown checks | 34 passed across memory settlement, application shutdown and the real privacy-scanner teardown after both repeated-close repairs; `h24/receipts/green-24b.xml`. The Today restart fixture separately passed its unchanged assertions in `cycle24-today-green.xml` |
| Assembled active-Test route inventory | Passed with the new authenticated-neutral shutdown routes; `C:/Renulus/scratch/oc-foundations/parent/inventory-02.xml` |
| Notes display regressions | 9 passed, including the real HTTP/SQLite flow, after reproducing stale history following deletion; `parent/notes-delete-green.xml` |
| Assessment fixture repairs | All 45 affected nodeids have passing evidence across 40 initial passes and a six-case follow-up (one overlap); [fixture evidence](opencode-foundations-assessment-fixtures.md). This is not a fresh 45-case run |
| Updates fixture repairs | Full 86-case run: 85 passed, one failed; targeted correction/re-review follow-up: one passed. All 86 distinct cases have passing evidence, including all 12 scheduler cases. [Fixture evidence](opencode-foundations-updates-fixtures.md) preserves both runs and all 155 original assertions |
| Broad backend coverage | All 2,437 original cases have disjoint assigned outcomes: 2,176 passed, 127 skipped, 100 failed, 34 errors. Exact later repairs plus two new shutdown cases yield **2,294 passed, 127 skipped, 18 classified inherited failures** across 2,439 cases. This is reconciled evidence across runs, not a new full-suite pass |
| Complete configured desktop suite | **691 passed, 12 intentionally skipped, zero failures** across 65 files (62 passed, three opt-in files skipped); `parent/frontend-final-02.xml`. All repaired assessment and Notes cases executed. Source hashes identify the tested fixture and production files |
| Hidden UI journeys, lifecycle and layout | Actual Memory/Library/unsent cited Chat journeys passed, including reopen and 1000 × 720 outer-window/200% zoom checks. Run 06 verifies Notes deletion in the same mounted panel. Run 07 verifies startup/normal close on final H24 production bytes using a fresh synthetic profile; [UI evidence](opencode-foundations-ui.md) records exact diagnostics and limits |

The direct SDK tests use the actual upstream loop, store, execution, recovery and
public TestLLM adapter; only inference is synthetic. Transport-only subprocess
fixtures are labelled separately. UI tests use the existing domain backend and
managed Mem0/FastEmbed CPU assets. None of these results proves subscription
authentication, model quality, native installation or packaged release behavior.

The final desktop suite ran at `e57e4d89`; its captured fixture/production hashes
still match the checkout. The later Services-only production delta `756c8ebc`
has the 34-case service regression and UI run 07; the Today and Updates changes
are test fixtures with their own receipts. Desktop development build/tests used local Node
24.15.0. The separate managed OpenCode host proof used pinned Node 26.4.0, as
recorded in its cohort and IPC receipts. The final desktop typecheck and renderer/
Electron build passed. Run 07's normal close took **0.740 seconds**, with no
forced or remaining owned app processes. All eight run-07 controller requests
succeeded; two HTTP 409 messages remain recorded. Its previous controller
process had ended, so it uses a fresh owned profile and does not prove retained
state reopening; that evidence belongs to runs 03/04/06. Run 06's 1.126-second
normal close also passed. Fifty of its 51 controller requests succeeded; an
early history click before save readiness was retained as an operator error
and followed by a successful explicit wait. No general clean-console or
complete-accessibility claim is made.

The backend coverage ledger assigns 447 assessment/backup cases to the original
runner, 1,076 cases to shard A and 914 to shard B. Both shards exited naturally.
After every required case had teardown evidence, the original runner was
executing only duplicate cases. Its verified owned process was stopped under
the parent integration instruction; this is an operator interruption of
synthetic pytest execution, not an application-settlement proof. No unfinished
duplicate counts toward coverage. All profiles/receipts remain preserved and
the cleanup audits report zero remaining owned Python processes.

The exact case reconciliation is
`C:/Renulus/scratch/oc-foundations/h24/receipts/latest-coverage-reconciliation.json`.
The H24 affected core has 227 passed and seven skipped across 234 distinct
cases; adding the separate Updates cases yields 313 passed and seven skipped
across 320 distinct cases, with no unresolved failures/errors in that set.
These unions are not additional executed full-suite runs.

Remaining broad-suite failures are carried forward explicitly:

| Family | Cases | Evidence and follow-up |
| --- | ---: | --- |
| Content/Library fixture omits the required Learn owner | 5 | Baseline/current module-inventory probes agree; assemble actual owners before using these fixtures for H02 acceptance |
| Backup version expectations | 3 | Two cases reproduced in the full untouched baseline archive, one with baseline H24 modules; reconcile expected current schema/version under H18 |
| Saved-case generated-practice cancellation | 1 | Reproduced with baseline modules; investigate the existing generation/cancellation flow alongside H12 |
| Discovery fixtures supply memory records without canonical revisions | 3 | Baseline reproduction and unchanged sources; align fixtures with existing revision contracts during H05 work |
| Stale proposed-table inventory | 1 | Full untouched baseline archive reproduces the five omitted tables; update the recorded schema inventory with its owner |
| Search fixture uses literal `now` as an assessment timestamp | 1 | Baseline reproduction with unchanged sources; supply a valid synthetic timestamp in the search fixture |
| Provider catalogue/access/capability expectations | 4 | Baseline-module reproductions and identical provider sources; H03 must resolve documented support, access and credential-epoch behavior |

The 18 cases are inherited failures, not waived acceptance or an assertion that
all are harmless test-only mismatches. Their exact nodeids and original/current
outcomes are preserved in `latest-unresolved-failures.json` and the H24 ledger.

The scoped Markdown link check passes for 30 documents, 324 local links and 17
heading links, with zero issues. The broader
`scripts/check_workspace.py` reports 25 unresolved relative links inside two
unchanged files in `docs/implementation/opencode-plan-snapshot/source-documents/`.
Those links retain their original source-relative spelling in an intentionally
partial historical capture. No failure points to a changed current document.
The snapshot's byte/hash checks still pass; this task preserves it and records
the whole-workspace check as failed rather than changing historical source to
silence it. The checker and both source documents are byte-identical to
`c2bd8964`, and the same 25 targets are absent in the full baseline archive.
Receipt: `C:/Renulus/scratch/oc-foundations/parent/final-doc-validation.json`.

## Independent review disposition

Independent standards and specification reviews of `c2bd8964...9a10562a` plus
the planning clarification found no remaining material H01/H24 issue. They
covered the admission-before-join repair, end-to-end pagination, startup cleanup,
IPC identity/replay binding and the prepared/active/migration/restore boundary.
Separate reviewers also cleared the Notes refresh change and the first three
assessment fixture changes. A final bounded review of `f6bdb589`, `b6a4a7da` and
the five fixture files in `e57e4d89` found no material standards or specification
issue. That review checked the retained red/green evidence and independently
reconciled all 45 fixture nodeids and source hashes; it did not execute tests.
A subsequent bounded review also cleared `756c8ebc`, `262e7e3e` and the four
Updates fixture assembly/bootstrap changes on both axes. It checked the 34-case,
Today and five-case Updates receipts and preserved assertions. The final
six-line Updates exact-copy re-review setup received a further read-only review:
both axes found no material issue, all 64 assertions remained unchanged and
all 18 targeted-run source hashes matched. It is recorded separately with its
single-journey follow-up. Earlier findings were reproduced and
repaired rather than waived.

The parent also exported the untouched `c2bd8964` source and ran three inherited
failures against fresh synthetic state. Both legacy-backup cases reproduce the
same `current_version: 2` versus `1` assertion, and the contract inventory case
reproduces five later tables absent from its proposal fixture. Receipts are
`parent/baseline-backend.xml` and `baseline-backend-receipt.json`. The H24 lane's
separate baseline-module probe reproduces the generated-practice case cancellation.
These results identify inherited failures; they do not turn the broad suite green.

## Next integration boundary

[H02](../planning/opencode-v2/tickets/02-answer-with-an-eligible-library-passage.md)
connects a native retrieval tool to the existing Python Library, eligibility,
citation and conversation owners. Preserve current direct Library operations,
policy/context checks, completed-answer receipts and lost-ack reconciliation.
Keep migrated automatic memory capture off until H05 supplies its lineage proof.

H01 initializes a **prepared** manifest only. H02 must validate the actual domain
and runtime stores, select the initial active generation under the admission and
writer barrier, and reopen that validated selection before storing the first
saved conversation mapping. H06 uses this for legacy-history migration. H18 owns
complete paired backup/restore across migrated producers. This avoids a dependency
cycle between the first saved flow and the later full restore milestone.

Remaining explicit boundaries:

- The default Node entry has no production model adapter and stays policy-blocked.
  H03 supplies the selected subscription adapters; the fixture adapter is never a
  production fallback. The desktop still uses its existing execution path.
- Selective recovery is deferred. Current recovery requires the complete held
  selection, matching configuration and proven native/admitted-write quiescence.
- Fresh-checkout build automation has not been replayed end to end. The executed
  coherent cohort and its preparation procedure are recorded; packaging and
  relocation are separate acceptance.
- Twenty-nine copied packages have no recognized licence/notice file recorded
  by the materializer. Complete distribution notices and native dependency
  qualification remain H20 work. The existing upstream licence is preserved.
- H24 proves lifetime/settlement behavior, not every memory-quality, correction,
  lineage or paired-restore requirement. H05/H18 retain those responsibilities.
- The normal launcher, owner profile and credentials remain unchanged. H20/DC21
  default delivery, live account acceptance, deployment and pushes are not part
  of this batch.
