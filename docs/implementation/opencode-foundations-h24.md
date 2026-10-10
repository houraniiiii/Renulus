# H24 memory-worker settlement

2026-10-10. Owned implementation on `codex/opencode-foundations`, from the
Design C baseline `c2bd896420fb88f76d63ca576414dbbba182f4c2`. The current user
instruction authorizes this implementation and the existing public test seams;
the earlier research-only wording in the planning snapshots is historical.

The user expanded this lane from memory to the connected shutdown path. Owned
files are `runtime/renulus/memory/{service,api,providers}.py`,
`runtime/renulus/{server,services}.py`, `runtime/renulus/runtime/api.py`,
`apps/desktop/electron/backend{,.test}.ts`, `tests/memory/test_settlement.py`,
`tests/integration/test_memory_shutdown.py` and this note. Parent owns `main.ts`
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

The drain preserves reverse callback dependency order and additionally joins
the existing library ingestion worker with `stop(None)` off the event loop.
That worker previously lived only in a nested router lifespan, which would
otherwise run after the desktop acknowledgement. Memory settlement completes
before provider/helper release. A bounded observer does not change that order.

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

Receipts are `receipts/red-01b.txt`, `red-02.txt` through `red-11.txt`, and the
corresponding `green-01.txt` through `green-11.txt`. The initial `red-01.txt`
was a fixture warm-up timeout, not the reproduced bug; initialization was moved
outside the controlled interval before `red-01b` reproduced the actual failure.
Additional regression cases cover normal completion, public Stop, commit-first
Stop, no late canonical publication and recovery after successful settlement.
The first expanded memory regression passed **39 tests** (`green-15b.txt`).
The new application integration checks passed individually through cycle 19;
the combined affected regression run is in progress at this source checkpoint.
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

A broad Python run was attempted with external networking disabled and all
optional RENULUS environment inputs removed. It was stopped after early errors;
this is not a full-suite pass. A fail-fast rerun identified the first failure:
the assessment fixture installs only content/updates/assessment but unconditional
feature-router construction needs learn/cases. Executing the original baseline
server from `c2bd8964` with that same fixture module inventory reproduces
`capability_unavailable: Learn is not ready` before startup.
Receipts: `full-first-failure.txt` and `baseline-assessment-fixture.txt`.

Python syntax checks pass. This checkout has no configured Python typechecker,
and neither mypy nor pyright is installed in the managed interpreter.

## Integration constraints and validation limits

1. Keep `Recovery.mutation()`'s memory guard fail-fast. Any future asynchronous
   quiescence wait must precede knowledge, preview, memory and SQLite locks and
   hold logical admission ownership through the mutation. Do not use permanent
   `close()` as a temporary backup pause.
2. Preserve the event loop during a blocked drain. An uncooperative native worker
   may keep application shutdown blocked indefinitely. Bounded caller errors
   are deliberate; there is no forced termination fallback or fake empty set.
3. Parent must include its `main.ts` change in the integrated checkpoint and
   rebuild the hidden application from these stable sources. Hidden UI evidence
   belongs to the parent lane and must be reported separately from service tests.

No hidden UI, packaging, physical Windows dialog or real subscription acceptance
is claimed by this lane's service receipts. Forced termination remains a distinct
outcome. First checkpoint review found no standards violations and two spec gaps
(application-callback cancellation and queued provider dispatch); cycles 13 and
14 reproduce and fix those gaps. Expanded checkpoint review is pending.
