# H24 memory-worker settlement

2026-10-10. Owned implementation on `codex/opencode-foundations`, from the
Design C baseline `c2bd896420fb88f76d63ca576414dbbba182f4c2`. The current user
instruction authorizes this implementation and the existing public test seams;
the earlier research-only wording in the planning snapshots is historical.

Scope: `runtime/renulus/memory/service.py`, `runtime/renulus/memory/api.py`,
`tests/memory/test_settlement.py` and this note. Shared server, recovery and
Electron files are parent-owned. No engine, canonical schema or provider was
replaced. No installation, default launcher, live subscription, private profile,
push or tracker operation was performed.

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

Receipts are `receipts/red-01b.txt`, `red-02.txt` through `red-11.txt`, and the
corresponding `green-01.txt` through `green-11.txt`. The initial `red-01.txt`
was a fixture warm-up timeout, not the reproduced bug; initialization was moved
outside the controlled interval before `red-01b` reproduced the actual failure.
Additional regression cases cover normal completion, public Stop, commit-first
Stop, no late canonical publication and recovery after successful settlement.
The pre-shutdown-callback checkpoint passed 33 focused/service checks. Final
regression and independent review results will be appended before handoff.

Python syntax checks pass. This checkout has no configured Python typechecker,
and neither mypy nor pyright is installed in the managed interpreter.

## Parent integration obligations

1. Preserve the server's reverse dependency order: memory settlement must finish
   before provider/helper teardown. `memory/api.py` now registers the dedicated
   callback, so its ordinary bounded timeout does not unwind `server.py`'s
   lifespan. A coordinator must still preserve that callback/loop during a
   blocked shutdown; external task cancellation or force termination does not
   establish settlement.
2. Electron currently stops the backend child before awaiting it; on Windows,
   `apps/desktop/electron/upstream/backend-child.ts` invokes `taskkill /T /F`.
   Parent should add an authenticated drain acknowledgement before termination,
   retain the backend handle/profile on timeout, and keep control/status replies
   reachable. Sequence `apps/desktop/electron/main.ts` and `backend.ts` so their
   connection teardown cannot remove the drain path. No launcher/updater edit is
   needed or included here.
3. Keep `Recovery.mutation()`'s memory guard fail-fast. Any future asynchronous
   quiescence wait must precede knowledge, preview, memory and SQLite locks and
   hold logical admission ownership through the mutation. Do not use permanent
   `close()` as a temporary backup pause.
4. `Recovery.rebuild()` calls `memory.reindex()` outside `mutation()`. Parent
   should coordinate rebuild with the same profile settlement/admission policy
   and expose blocked status rather than interpreting a timeout as an empty
   active set. These shared recovery changes are not part of this lane.

No hidden UI, native Windows shutdown, packaging or real subscription acceptance
is claimed by the service receipts. Parent owns the assembled hidden UI check
and shared shutdown integration; forced termination remains a distinct outcome.
