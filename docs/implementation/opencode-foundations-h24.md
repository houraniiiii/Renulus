# H24 memory-worker settlement

2026-10-10. Owned implementation on `codex/opencode-foundations`, from the
Design C baseline `c2bd896420fb88f76d63ca576414dbbba182f4c2`. The current user
instruction authorizes this implementation and the existing public test seams;
the earlier research-only wording in the planning snapshots is historical.

The integration task expanded this lane from memory to the connected shutdown path. Owned
files are `runtime/renulus/memory/{service,api,providers}.py`,
`runtime/renulus/{server,services}.py`, `runtime/renulus/runtime/api.py`,
`apps/desktop/electron/backend{,.test}.ts`, `tests/memory/test_settlement.py`,
`tests/integration/test_memory_shutdown.py`, the narrow owner-restart fixture in
`tests/study/test_today_journey.py`, and this note. Parent owns `main.ts`
and the assembled hidden UI check. No engine, canonical schema or provider was
replaced. No installation, default launcher, live subscription, private profile,
push or tracker operation was performed. Memory checkpoint:
`fc69a8e6111fe71f5a72f1535140a9c89c73f5b6` (36 tests passed).

## Behavior and contract

- Executor-thread leases survive cancellation of the awaiting coroutine. Only
  the actual function's return through its finalizers releases the lease.
  The existing default executor and context propagation are retained; no new
  engine, executor service or process was introduced.
- Recovery refuses active capture, processing, unsettled threads and incomplete
  shutdown. A cancelled coroutine or an empty active-run set is not settlement.
- `close(timeout=5.0)` seals admission, cancels background and directly invoked
  processing, and drains the same owned work before releasing engines. Five
  seconds is the selected default observation bound, not a worker-kill limit.
  Timeout raises retryable `ApiError('memory_close_timeout', ..., 503, True)`;
  the original loop/provider replies and profile ownership must remain alive.
  Repeated close calls observe the same drain and do not redispatch extraction.
- Cancellation of a close observer does not cancel the drain. Extraction and
  rebuild threads remain leased; final engine closure also runs off the loop.
  Startup, capture admission, retry, reindex and recall refuse a closing owner
  with `memory_stopping`. New queued captures cannot overlap the finalization of
  a previously cancelled extractor.
- Extractor provider admission is revoked on coroutine cancellation or close.
  Canonical commit/cancellation guards retain their existing authority. An
  interrupted shutdown job retains the existing restart semantics; explicit
  user Stop stays terminal and committed capture wins over a later Stop.
- The memory router now registers `shutdown()` for application teardown.
  It retries bounded observations of the same drain, keeping the lifespan and
  reply loop alive instead of allowing `memory_close_timeout` to escape into
  provider teardown. Its total wait is intentionally unbounded if a worker
  cannot settle. Public `close()` remains bounded for interactive callers.
- Application teardown defers its own cancellation until settlement. The shared
  Services drain is retained across request timeouts and cancelled observers;
  the server lifespan also retains its wait. A failed callback is an explicit
  `runtime_shutdown_failed` response and a blocked lifespan, never settlement.
- Public `reindex()` refuses outstanding extraction/processing/rebuild ownership
  before taking the engine lock, including the cancelled extractor's finalizer.
  It retains a lease for its own real synchronous lifetime. Ordinary canonical
  edits remain allowed during rebuild and the existing epoch guard still wins.
  `Recovery.rebuild()` already maps this retryable error to blocked; no recovery
  implementation change was needed.
- Provider admission is rechecked on the reply loop immediately before dispatch,
  covering cancellation between the extractor's check and queued generation.

## Connected application shutdown

`POST /api/v1/runtime/shutdown` requires the configured app session token and a
bounded optional `timeout_seconds` (default 5, maximum 30). The first request
permanently seals ordinary HTTP admission. Subsequent requests observe the same
drain. Timeout returns HTTP 503 / `runtime_shutdown_pending`; failure returns
HTTP 503 / `runtime_shutdown_failed`. Success is exactly
`{"state":"settled","api_version":1}`. Authenticated GET on the same path
reports open, draining, settled or failed. Health, meta and runtime status remain
reachable; shutdown/status are neutral while a Test is active.

The drain first seals admission and calls synchronous signal-only hooks. Memory
begins its retained drain immediately; the library worker receives `stop(0)`.
All producer shutdown callbacks then start before any join is awaited, including
the library worker's `stop(None)` off the event loop. A held library join cannot
delay memory cancellation or allow another extraction/provider attempt.

Admitted HTTP handlers retain ownership even after their client disconnects.
Shutdown signals disconnect without abandoning the actual handler: an accepted
Library import must finish its real file/SQLite work before acknowledgement.
After all producers and admitted requests settle, provider/helper dependencies
close in reverse dependency order. Control/status requests remain available
without policy reconciliation writes during drain. A bounded observer timeout
does not cancel or reorder this shared drain.

For a ready owned backend, Electron `stop()` posts the authenticated request over
the owned loopback port, with an independent eight-second deadline covering
headers and body decoding. Only a valid successful settlement acknowledgement
allows existing process termination, followed by the unchanged 15-second actual
death wait. Failure, timeout, invalid reply and late reply retain the same
backend handle for retry. A child that never reached authenticated readiness may
still be aborted, with the existing actual-death wait.

Parent changed `main.ts` to await `backend.stop()` before closing frontend
connections. Its rejection path retains the frontend/profile and offers retry;
it no longer advises force closure. This lane inspected that change but did not
edit or commit it. Backend source is stable for the parent UI worker to rebuild
both backend and main. Installed/native acceptance is not inferred from tests.

The separate [UI lane's run 06](opencode-foundations-ui.md) subsequently rebuilt
the renderer and Electron entries, launched a fresh hidden backend including
`f6bdb589`, and observed normal close in **1.126 seconds** with no forced or
remaining PIDs. Source and all 54 build artifact hashes stayed unchanged through
launch and close. Its receipts are under
`C:/Renulus/scratch/oc-foundations/ui/`, including
`native-lifecycle-06.receipt.json` and `native-ui-06.summary.json`. This verifies
the normal connected desktop path with the parent's `main.ts` sequencing. Held
worker timeout/retry is covered by this lane's application and backend tests;
the UI lane did not inject that timeout.

The final [UI lane's run 07](opencode-foundations-ui.md) rebuilt and launched a
fresh hidden backend with Services correction `756c8ebc`. It reached readiness
in **19.326 seconds**, checked the ordinary New chat route, and closed normally
in **0.740 seconds** at **21:22:32.510 UTC**, with no forced or remaining owned
PIDs. All 505 source records and 54 artifacts remained unchanged through the
run; `262e7e3e` changed only the Today test during that interval. Receipts are
`native-lifecycle-07.receipt.json` and `native-ui-07.summary.json` in the same
UI scratch directory. This was a fresh synthetic profile, not retained-state
reopen evidence; the controller could not resume the former profile. Two HTTP
409 diagnostics are retained, so this does not claim a clean console. The
closed-task replay branch is covered by the public service regression below.

## Red/green evidence

Managed interpreter: `C:/Renulus/dev/python/Scripts/python.exe`; synthetic state
and retained command receipts: `C:/Renulus/scratch/oc-foundations/h24/`.
Tests use real SQLite and public memory/recovery operations, with a bounded,
event-controlled extractor/index double. A synthetic tokenizer initializes the
existing embedding adapter, but these settlement tests do not load a model or
claim actual Mem0/Qdrant inference acceptance.

Each numbered cycle added one behavioral scenario before its implementation:

| Cycle | Red observation | Green behavior |
| --- | --- | --- |
| 01 | Recovery entered after coroutine cancellation while extraction still ran | Thread/finalizer lease blocks recovery |
| 02 | Shutdown still admitted new capture | Admission closes before drain |
| 03 | Public Retry was not cancelled by close | All processing owners participate in drain |
| 04 | Observer timeout cancelled the settlement future; close retry failed | Observer lifetime is separate from drain lifetime |
| 05 | Public close did not support an explicit observation bound | Bounded error with retained ownership and retry |
| 06 | Engine finalizer could not get its event-loop reply | Final engine release runs off the loop |
| 07 | Cancelled rebuild lost its recovery protection | Rebuild thread shares the settlement lease |
| 08 | Closed owner could restart worker/index/recall | Engine and worker admission stays closed |
| 09 | Cancelled extractor still had provider admission | Late provider work is revoked |
| 10 | Retry dispatched another extraction before cancelled work settled | Next work remains queued without another attempt |
| 11 | Registered app shutdown escaped on bounded close timeout | Registered callback waits for settlement before downstream teardown |
| 12 | Active Test policy rejected authenticated runtime shutdown | Shutdown/status are neutral and ordinary admission remains closed |
| 13 | Cancelling the memory application callback abandoned its wait | Application cancellation defers through thread finalizers |
| 14 | A provider call began after Stop between thread check and dispatch | Reply-loop admission check refuses the outbound attempt |
| 15 | Public reindex acquired engines while cancelled extraction remained | Recovery fails closed; ordinary rebuild/edit epoch behavior preserved |
| 16 | Cancelling the server lifespan unwound its drain observer | Lifespan keeps reply capacity until actual memory settlement |
| 17 | A successful acknowledgement left the library worker running | Existing library worker is joined before acknowledgement |
| 18 | An app without a configured session could invoke shutdown | Shutdown requires a configured, matching token |
| 19 | Callback failure escaped as generic HTTP 500 | Explicit failed drain, retained admission and blocked application owner |
| 20 | Shutdown acknowledged while an accepted Library original writer was held | Connected and cancelled-client requests retain real writer ownership through settlement |
| 21 | An unbounded library join left existing memory provider admission open | Signal admission closure immediately, then join producers before releasing dependencies |
| 22 | Replacing a consumer provider adapter made shutdown fail on its capability-only status | Cancellation and final release retain the same registered provider instance |
| 23 | Repeating completed close from a new loop scheduled a callback on the closed original loop | Read an already-settled drain result directly; pending ownership is unchanged |
| 24 | Replaying completed application shutdown from a new loop scheduled a callback on the closed original loop | Observe completed Services drain status directly; retain pending ownership and permanent closed admission |

Receipts are `receipts/red-01b.txt`, `red-02.txt` through `red-11.txt`, and the
corresponding `green-01.txt` through `green-11.txt`. The initial `red-01.txt`
was a fixture warm-up timeout, not the reproduced bug; initialization was moved
outside the controlled interval before `red-01b` reproduced the actual failure.
Additional regression cases cover normal completion, public Stop, commit-first
Stop, no late canonical publication and recovery after successful settlement.
The first expanded memory regression passed **39 tests** (`green-15b.txt`).
The application integration checks passed through cycle 21. `red-20b.txt`
reproduces premature acknowledgement during an actual original-file write;
`green-20c.txt` records all eight application cases then present passing.
`red-21.txt` reproduces provider dispatch while the library join is held;
`green-21.txt` passes with no outbound attempt and closed public memory admission.
The cycle-21 shutdown regression (`final-shutdown.txt`) passed **38 tests**
across application shutdown, memory settlement, Test policy and runtime auth.
The first full run at `ecc3367b` then stalled in the retained generated-practice
test because the new cancellation hook read a replacement consumer adapter's
capability-only status. This was an H24 callback ownership regression, not a
baseline failure. `red-22.txt` reproduces the explicit failed drain; `green-22.txt`
passes after binding cancellation to the same provider instance as final release.
Only that verified synthetic pytest process was stopped to replace its loaded
runtime; this run has no full-suite totals (`full-final.txt`).
The correction passes all ten shutdown integration cases and the actual retained
practice journey that exposed it: **11 passed** (`green-22b.txt`).
The broad shard later exposed a second H24 regression in the real Qdrant privacy
scanner's teardown: it calls `asyncio.run(memory.close())` after the TestClient
loop already completed that same drain. `red-23.txt` reproduces the closed-loop
error through public close; the two-line completion check passes `green-23.txt`.
`green-23b.txt` / `green-23b.xml` record **33 passed** across all memory settlement,
application shutdown and privacy-scanner cases. No task is reset, transferred or
restarted: pending drains retain their original loop and worker ownership. This
adds one test beyond the original 2,437-case coverage inventory.
The final Study journey then exposed the same completed-task observation issue
in `Services.shutdown`. `red-24.txt` reproduces it through two authenticated
shutdown calls from successive loops. `green-24.txt` passes after guarding only
the wait on an incomplete task; completed failed drains still return their
existing explicit error, and no owner is restarted or handed to another loop.
`green-24b.txt` / `.xml` record **34 passed in 97.17 seconds**, covering all
memory settlement, application shutdown and real privacy-scanner cases. The
source/test-only correction is `756c8ebc`; it adds a second case beyond the
original inventory. The Today fixture additionally reuses the same closed app
for ordinary writes. With the closed-loop error fixed, its exact follow-up
fails with 503 instead of 200 (`cycle24-today-old-fixture.txt`); a fresh
application owner over the same SQLite profile is required, without reopening
the old owner's admission. The integration task explicitly extended this lane
to that fixture. Commit `262e7e3e` discards the returned closed application and
creates a fresh application over the same profile for the second TestClient.
All original score, manual-change, preferences and restart assertions remain.
`cycle24-today-green.txt` / `.xml` record **1 passed in 7.60 seconds**, with no
external network attempts and unchanged source hashes throughout the run. This
is H24 fixture compatibility repair, not a baseline waiver.
The earlier combined affected run collected at `36777c27` finished with
**219 passed, 7 skipped, 1 failed** (`regression-final.txt`). Its single failure
is the parent-owned route inventory fixture treating the authenticated neutral
shutdown endpoint as a non-neutral route (expected 409; received 401).
Cycle 15 initially over-restricted canonical edits during rebuild; the existing
epoch test caught that regression. The final lease-based guard restores those
edits (`green-15b.txt`). `red-12.txt` was an import setup error; `red-12b.txt`
reproduced the actual Test policy failure.

Electron receipts are under `h24/backend/`: five sequential red/green cycles
cover handshake-before-kill, pending/retry, acknowledgement validation,
independent deadline and startup abort during readiness decoding. Additional
regressions cover stalled decoding, late replies, failure variants, shared stop
and idempotence. `12-final-vitest.txt`: **36 tests passed** in backend and existing
backend-child tests, including a real owned Windows child-death check.
`12-final-typecheck.txt`: desktop TypeScript checking passed.
`receipts/integrated-desktop-typecheck.txt` also passed after the parent main.ts
quit sequencing change. Electron backend bytes remain at `36777c27`; cycles
20/21 change Python runtime bytes and require restarting the hidden backend.

A broad Python run was attempted with external networking disabled and all
optional RENULUS environment inputs removed. It was stopped after early errors;
this is not a full-suite pass. A fail-fast rerun identified the first failure:
the assessment fixture installs only content/updates/assessment but unconditional
feature-router construction needs learn/cases. Executing the original baseline
server from `c2bd8964` with that same fixture module inventory reproduces
`capability_unavailable: Learn is not ready` before startup.
Receipts: `full-first-failure.txt` and `baseline-assessment-fixture.txt`.
`baseline-fixture-matrix.txt` additionally runs the original baseline server
source and current server with the same six reduced module inventories:
assessment, Updates, Updates/Library, Knowledge only, Content only and
Content/assessment. Every pair fails before lifespan with the same
`capability_unavailable: Learn is not ready`. These are fixture assembly failures;
no unrelated feature or fixture changes are included in this lane.

The final full run uses `run_full_final.py` from the synthetic lane directory,
managed Python, cleared `RENULUS_*` inputs, disabled plugin autoload and an
external-socket guard. Its H24 source checkpoint is
`29d147869056c14b80b1cdfe0026e0b705454990`; other foundation lanes remain shared
working changes. Per-test events and the current node are retained alongside
the complete output, so errors do not end the run and a stall is identifiable.
Parent updated the authenticated neutral route inventory after collection. The
complete latest inventory file passed **41 tests** (`inventory-final.txt` and
`inventory-final.xml`). Parent reports the integrated production checkpoint
`9a10562a`, including H01 `b5101da0` and main/inventory `1a228c29`; the full run
started before those commits, with H24 runtime bytes unchanged since `29d14786`.

The integration task subsequently authorized two isolated shards for untouched
directories. The original process continued through its assigned prefix. Coverage ownership is
447 assessment/backup cases from that process, 1,076 cases/content/knowledge/
learn/retrieval cases in shard A, and 914 integration/memory/regression/runtime/
study/Updates cases in shard B. Each has its own basetemp and no-external-socket
runner. `backend-coverage-plan.json` records the exact disjoint inventory. Four
auto-generated ZIP-byte parameter IDs differ only in embedded ZIP timestamps;
explicit one-to-one aliases were verified by comparing every other byte.
`unique-coverage.json` counts only the assigned owner of each node, so subsequent
duplicate work in the original process cannot inflate the total. These runs
loaded memory before cycle 23; the 33-case focused receipt records the correction.

`baseline-extra-failures.txt` reruns the saved-case generated-practice cancellation
and both legacy-backup current-version failures with all six H24 Python modules
loaded from `c2bd8964` in memory. All three failures reproduce unchanged; no
repository files were replaced. `baseline-table-proposal.txt` proves the stale
table inventory test, fixture and runtime registry are each byte-identical to
the same baseline. These failures remain distinct from the fixed H24 close bug.

Parent then reproduced both legacy-backup failures and the table proposal
failure in a complete read-only Git archive of `c2bd8964`: **3 failed in 31.28
seconds**, with identical `current_version: 2` versus `1` and five missing-table
differences. Receipts are `C:/Renulus/scratch/oc-foundations/parent/`:
`baseline-backend.txt`, `baseline-backend.xml` and
`baseline-backend-receipt.json`. A later segmented legacy-history backup case
has the same version expectation mismatch. Its test, recovery and content
sources are unchanged from baseline; running it with all six pre-H24 modules
reproduces **1 failed in 24.01 seconds** (`baseline-segmented-version.txt`/`.xml`).
The search readiness/context test also inserts the literal `now` into an
assessment timestamp; reconciliation rejects it as invalid ISO format. That
exact failure reproduces with all six pre-H24 modules: **1 failed in 7.20
seconds** (`baseline-search-clock.txt`/`.xml`). Its fixture and assessment
repository remain byte-identical to baseline.
Three Learn discovery fallback cases also reproduce with the six pre-H24
modules: **3 failed in 16.58 seconds** (`baseline-learn-discovery.txt`/`.xml`).
Their memory double supplies `{"id":"one"}` without a revision or canonical
fact, so the existing `MemoryContext.capture` guard refuses it before a
completed explanation. The test, Learn service and memory-context guard are
unchanged from baseline. No product behavior was weakened to satisfy these
fixture expectations.
Four runtime catalogue/capability assertions also reproduce without H24:
inference-auth catalogue status **1 failed in 8.00 seconds**
(`baseline-image-catalogue.txt`/`.xml`), plus two failed-auth availability
variants and one transient-refresh capability expectation **3 failed in 5.78
seconds** (`baseline-provider-status.txt`/`.xml`). These retain `available` or
`supported` where the tests expect `unknown`; their correctness is a separate
baseline follow-up, not a change made to complete H24.
`baseline-source-checks.json` records baseline and checkout SHA-256 values for
15 relevant test/implementation files, including the provider manager, auth,
policy and Hermes adapter; all 15 are byte-identical to `c2bd`.

The assessment fixture repair is parent-owned commit `e57e4d89`. Its focused
receipts under `C:/Renulus/scratch/oc-foundations/af/` record **40 passed / 5
failed**, followed by **6 passed** (one overlapping tracer). Matching the exact
nodeids yields **45 distinct passing cases**, with no missing or additional
cases. `backend-reconciliation.json` and this lane's
`latest-coverage-reconciliation.json` retain that as subsequent repair evidence;
they do not overwrite the original broad-run failures or imply a fresh single
45-case pass. The parent-owned Updates fixture follow-up similarly preserves
its initial failures separately. Its `uf/r4/junit.xml` and `session.json` contain
the exact **86 Updates nodeids: 85 passed, 1 failed in 254.67 seconds**. Every
node has a final teardown report, with no external network attempts and stable
source hashes. The real scheduler cancellation and application lifespan cases
pass with actual Learn/Cases/Assessment owners in the fixture assembly.

That run resolves 68 of the 69 original Updates missing-owner failures. The
remaining node now reaches its substantive assertion:
`test_detect_review_exact_copy_invalidate_and_restart_preserve_other_topics`
expects four eligible Library documents but receives none at line 149, before
shutdown. With the repaired fixture and all six H24 Python modules loaded from
`c2bd8964`, the same assertion fails in **10.37 seconds**
(`baseline-updates-current-documents.txt` / `.xml`). This rules out the H24
shutdown changes as its cause; it is not a full-baseline archive pass or a
waiver of the unresolved eligibility assertion. No retrieval behavior or
acceptance assertion was changed in this lane.

The parent then authorized UF's narrow fixture correction: after correction
notices invalidate currency, explicitly re-review each exact acquired copy
through the existing API. All assertions remain. `uf/r5/junit.xml` and
`session.json` record that same case **passing in 10.39 seconds**, without
external network attempts or production changes. The exact union of `r4` and
`r5` therefore has **86 distinct passing Updates cases**, including all 12
scheduler cases. The 85/1 full-run result and the earlier baseline reproduction
remain preserved; this is a subsequent fixture repair, not an 86-pass rerun.

The latest collection has **2,439 cases**, including the public-close
and application-shutdown replay regressions. Final H24 production is `756c8ebc`
(including memory `f6bdb589`). Electron backend bytes remain at `36777c27`.

Python syntax checks pass. This checkout has no configured Python typechecker,
and neither mypy nor pyright is installed in the managed interpreter.

## Complete raw backend coverage

All **2,437 assigned nodeids have final teardown reports**, with no missing or
duplicated ownership. These are unique-case outcomes; a case whose body passes
but teardown fails is counted once as an error.

| Assigned owner | Unique cases | Passed | Skipped | Failed | Error |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original assessment/backup prefix | 447 | 383 | 16 | 15 | 33 |
| Shard A: cases/content/knowledge/learn/retrieval | 1,076 | 977 | 89 | 9 | 1 |
| Shard B: integration/memory/regression/runtime/study/Updates | 914 | 816 | 22 | 76 | 0 |
| Total raw assigned coverage | 2,437 | 2,176 | 127 | 100 | 34 |

The raw 134 failing/error cases consist of 119 missing-Learn fixture assembly
cases (45 Assessment, 2 Content, 3 Library, 69 Updates), 3 backup version
expectations, 1 saved-case practice cancellation, 3 discovery memory-pin
fixtures, 1 table proposal, 1 search timestamp, 4 provider capability/status
assertions, and the 2 H24 completed-task replay regressions fixed in cycles 23
and 24. The baseline reproductions and subsequent repair receipts above remain
separate from these original outcomes; this is not a full-suite green claim.

The assigned prefix completed at **20:59:39.997 UTC**, 2,639.26 seconds after its
first test phase. Shard A exited with pytest status 1 after **1,533.22 seconds**;
shard B exited with status 1 after **2,239.14 seconds**. Shard A's pytest terminal
summary says 978 passed plus one teardown error; the unique ledger counts that
same affected case once, producing 977 passed and one error above.

After all required cases finished, the parent integration instruction explicitly
authorized terminating only discarded duplicate test execution. The original
runner had no cooperative stop hook. Its command hashes, creation timestamps,
PID 32848 launcher and PID 45276 actual runner were verified before stopping
45276. The launcher then exited, and no descendants remained. This happened at
**21:12:36 UTC** and is an **operator interruption of synthetic pytest work**,
not application or worker settlement. No unfinished duplicate case contributes
to coverage. All profiles and receipts were preserved. Evidence:
`assigned-prefix-completion.json`, `process-identities-before-cleanup.json`,
`duplicate-run-interruption.json` and `final-process-audit.json` (zero remaining
task-owned Python processes at the audit). The subsequent Today run also exited
naturally; `final-process-audit-after-today.json` confirms zero remaining
H24-owned Python processes at **21:21:54 UTC**.
The last baseline probe also exited naturally; its subsequent process audit
(`final-process-audit-after-baseline.json`) again found zero H24-owned Python
processes. `raw-receipt-sha256.json` freezes hashes for all 17 raw coverage,
ownership and cleanup receipt files.

`unique-coverage.json` preserves raw assigned outcomes;
`latest-coverage-reconciliation.json` adds exact subsequent repairs and the two
new tests; `latest-case-outcomes.json` maps every one of the 2,439 current nodeids
to its outcome receipt and original broad owner/outcome;
`latest-unresolved-failures.json` retains each unresolved nodeid,
current failure and original failure phases. Including the separately passing
Today fixture repair, the core H24 affected set has **234 distinct cases:
227 passed, 7 skipped, no failures/errors**.
`combined-affected-reconciliation.json` also includes the 86 actual Updates
scheduler/lifespan cases, for **320 distinct cases: 313 passed, 7 skipped,
no failures or errors**.

After exact AF, H24, Today and UF receipt reconciliation, all **2,439** current
cases have an outcome: **2,294 passed, 127 skipped and 18 classified failures**.
There are zero errors, missing cases or unclassified failures. This projection
combines disjoint original owners and explicit later repairs; it is not a new
single-pass result. The remaining failures are:

| Remaining family | Cases | Evidence |
| --- | ---: | --- |
| Content/Library reduced module fixture missing Learn | 5 | Identical baseline/current module-inventory probes |
| Backup current-version expectation | 3 | Two full baseline archive cases; one six-module baseline probe |
| Saved-case generated-practice cancellation | 1 | Six-module baseline probe |
| Discovery memory records lack canonical revision | 3 | Six-module baseline probe and identical test/guard sources |
| Stale table proposal inventory | 1 | Full baseline archive reproduction |
| Search fixture literal `now` timestamp | 1 | Six-module baseline probe and identical sources |
| Provider catalogue/capability expectations | 4 | Six-module baseline probes and identical provider sources |

`integrated-source-boundary.json` verifies all 18 paths recorded by UF's final
`r5` receipt still match their tested hashes, and confirms 2,439 unique entries
in `latest-case-outcomes.json`. The fixture repair remains owned by the UF lane;
this lane commits only its own implementation, Today compatibility fixture and
evidence note.

## Integration constraints and validation limits

1. Keep `Recovery.mutation()`'s memory guard fail-fast. Any future asynchronous
   quiescence wait must precede knowledge, preview, memory and SQLite locks and
   hold logical admission ownership through the mutation. Do not use permanent
   `close()` as a temporary backup pause.
2. Preserve the event loop during a blocked drain. An uncooperative native worker
   may keep application shutdown blocked indefinitely. Bounded caller errors
   are deliberate; there is no forced termination fallback or fake empty set.
3. Preserve the parent `main.ts` shutdown ordering. The integrated hidden UI
   run 07 covers these stable production bytes; its lifecycle evidence belongs
   to the parent lane and is distinct from service tests and held-worker tests.

No hidden UI, packaging, physical Windows dialog or real subscription acceptance
is claimed by this lane's service receipts. Forced termination remains a distinct
outcome. First checkpoint review found no standards violations and two spec gaps
(application-callback cancellation and queued provider dispatch); cycles 13 and
14 reproduce and fix those gaps. Expanded standards review found no hard
violations; its optional lease-bookkeeping consolidation is deferred. Expanded
spec review identified admitted-request ownership (cycle 20), and parent review
identified delayed admission closure (cycle 21). The latest independent spec
review found no remaining concrete blocker in request ownership and shutdown
phases. The complete disjoint backend inventory now has teardown receipts for
all 2,437 original cases. Subsequent fixture repair receipts remain separate
from those raw outcomes.
