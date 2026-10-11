# H02/H05 reverse domain IPC contract and evidence

October 11, 2026. Owned lane: codex/oc-domain-ipc, based on 74e3424b, with
parent activation prerequisite 96a29d11861f901bded2ea46c81cb20f948a194b
cherry-picked as 8c4dc0dd. The parent confirmed this protocol and leased only
the two transport files and dedicated callback modules/tests. No descendants,
provider calls, installed profiles or shared contract edits.
Published parent native prerequisites ce85b7c5, 63dde885, a884ef17 and
def4b12b were also consumed unchanged for transport types and connected testing.

## Primary source and seam

The [shared harness contract](../../packages/contracts/harness.md),
[H02](../planning/opencode-v2/tickets/02-answer-with-an-eligible-library-passage.md),
[H05](../planning/opencode-v2/tickets/05-complete-a-learning-turn-whose-memory-stays-corrected.md),
[H24](../planning/opencode-v2/tickets/24-keep-memory-worker-ownership-until-extraction-settles.md)
and [control specification](../planning/opencode-v2/specs/01-harness-control.md)
govern authority, independent capacity and actual settlement. Primary inspected
implementation is [Python transport](../../runtime/renulus/runtime/harness_process.py)
and [Node transport](../../packages/harness/src/ipc.ts). Existing public Harness
commands/subprocess observations are the accepted test seam; fault injection
uses only dedicated owned synthetic children. Research/TDD/implement skills were
read from the requested bundle. The user's no-descendants rule supersedes the
research/review skills' agent delegation defaults. Independent integrated review
belongs to the parent; this lane reviews standards and specification locally.

## Wire interface

One UTF-8 LF-terminated JSON object, protocol renulus-harness/1:

~~~json
{"kind":"domain_request","protocol":"renulus-harness/1","profile_id":"p","store_id":"runtime-store","generation":"process-generation","token":"private-transport-token","callback_id":"callback-1","operation_id":"learning-1","attempt_id":"attempt-1","session_id":"native-session","input_id":"native-user-input","cancellation_id":"trusted-parent-run","command":"library.retrieve","payload":{"command":"library.retrieve","arguments":{"query":"CKD"},"envelope":{}}}
~~~

All identity fields are mandatory. store_id is the runtime store; generation
is the process identity, independent of snapshot generation. input_id is the
actual native **user input ID**, never the tool's assistant message ID or tool
call ID. cancellation_id is the stable opaque parent operation/run cancellation
identity. The host resolves bindings from admitted run/native metadata.
Only command and payload may originate in model tool arguments. Transport token,
filesystem root, store descriptors and credentials never reach public observations.

domain_result echoes the complete transport/binding/callback identity, omits
command/payload, and carries outcome plus exactly one JSON object result or
error: {code, status?, retryable?}. Optional status is 400–599; optional
retryable is boolean. No Python exception messages, traces or private document
names are transmitted. Pending is an observation, never permission to replay work.
domain_cancel echoes the same identity and has no command/payload/body.
Unknown or mismatched identities, malformed bodies and non-finite JSON cannot
settle a callback. Cancellation results contain no handler value.

## Python interface

Definitions live in [harness_domain.py](../../runtime/renulus/runtime/harness_domain.py).

~~~python
DomainBinding(operation_id, attempt_id, session_id, input_id, cancellation_id)
DomainRequest(callback_id, binding: DomainBinding, command: str, payload: dict)
DomainGrant(binding: DomainBinding,
            handler: Callable[[DomainRequest, DomainCancellation], Awaitable[dict]],
            check_current: Callable[[], bool],
            cancellation: DomainCancellation | None = None)

process = ManagedHarnessProcess(
    domain_authority=async_resolve_request_to_trusted_grant_or_none)
process.domain_status()                   # active, retained, bytes, accepting
process.domain_result(callback_id)        # independent token-free snapshot or None
process.cancel_domain(cancellation_id)    # cooperative signal; matching count
await process.settlement(timeout)         # actual process/pipes AND finalizers
await process.close(timeout)              # also requires clean close receipt
~~~

DomainCancellation.cancelled is a thread-safe cooperative predicate, including
the supplied parent's cancellation token; cancel() revokes it; check_current()
invokes a synchronous local guard and raises DomainCancelled on cancellation or
a guard that does not return exactly True. The authority resolver is asynchronous
and runs in an owned task. It must resolve the command and complete binding from
trusted records/registries, ignoring tool payload authority. A returned grant
must match **all five** binding fields. Its handler must retain any async children,
CPU futures and finalizers until actual settlement. The transport never cancels
that ownership task to simulate completion.

Guard checks run before the handler, after it returns, and immediately before
the pipe write, covering queued results and replay. **The handler's canonical
commit must also invoke the parent's local guard in its own transaction.** No
remote work or awaited guard is permitted inside a canonical transaction or
physical conversation/recovery lock. A transport check does not establish a
canonical domain commit.

Configuration adds max_domain_inflight=4, max_domain_result_records=256,
max_domain_result_bytes=16777216. Admission reserves request bytes, identity
metadata and two maximum result frames. Results are retained as bounded wire
bytes, never evicted. Configured callback limits narrow the Node boot limits.
Callbacks have independent result/admission budgets; one auxiliary reply slot
bounds overload/conflict/replay output. Flooded non-admitted frames may receive
no additional acknowledgement while that slot is occupied; they never run a
handler. This is not a drop policy for an admitted command/result.

## Node interface

Definitions live in [domain-ipc.ts](../../packages/harness/src/domain-ipc.ts).

~~~typescript
runHarnessIpc(async (boot: HarnessBoot, domain: DomainClient) => host);
domain.request(binding: DomainBinding, command: string,
  payload: Readonly<Record<string, unknown>>,
  options?: { signal?: AbortSignal; callbackId?: string }): Promise<DomainOutcome>;
domain.state();              // active, retained, bytes, accepting
domain.result(callbackId);   // independent terminal result or undefined
domain.seal();               // close admission, cooperative cancellation
await domain.settled();      // owned callback observations and writes
~~~

Bindings use the same snake_case fields as Python. Optional callback ID is
trusted caller observation/idempotency state, never model authority. Reusing it
with the same request observes the original promise; a different digest rejects.
The normal factory generates fresh UUIDs. Node reservations independently bound
callback concurrency, record count, request bytes and maximum reply bytes.
Abort does not settle the callback early; it sends authenticated cancellation
and suppresses a late value until the terminal result actually arrives.
Disconnect yields uncertain outcomes, not clean cancellation proof.

Node host.close seals callbacks but keeps its receive pump live while native
and domain settlement wait. The Python pump schedules handlers and remains
available for nested native commands/results. Existing control and reserved
close lanes remain separate from callback/result capacity. No transport pump
awaits a domain handler inline. Priority cannot preempt bytes already written.

Recovery command session.find accepts exactly {}. Its only lookup target is
the authenticated request operation_id, passed to host.findSession(operationId).
The result is {sessions: [encoded native Session.Info]}, with zero or one entry;
duplicates reject with harness_session_identity_conflict. This does not expose
generic listing or allocate a session/input, prompt, or generate content. The
parent host performs the supported SDK scan and exact profile/store matching.

## Library composition and connected limits

The parent owns host.ts, Services/assembly and shared contracts. Library owns
domain-tools.ts and harness_library.py. Its agreed opaque payload is
{command, arguments, envelope} inside the authenticated frame. The parent
resolves the envelope and Python LibraryAuthority locally; it must verify any
echo against that resolution rather than accepting model-supplied scope/epochs.
Dependencies remain exact reference-only identities, with idempotent recording
and local publication validation in the caller transaction.

Synthetic tests prove actual Node/Python pipes and a callback awaiting another
prompt while the outer observation waits. This explicit nested tracer reserves
two data-command positions; callback concurrency is one. A CPU worker must use
the live owning loop (run_coroutine_threadsafe from its thread), never start
another loop or hold a physical domain lock across IPC. A single transport data
slot cannot admit two simultaneously owned data requests; ordinary native prompt
submission returns its durable input receipt before the turn finishes. Scheduling
standalone memory extraction after eligible committed publication remains the
parent/H05 responsibility. Native tool/SDK composition, actual Memory engines,
canonical Library authority, desktop and live account acceptance require their
own connected tests; the dedicated scripted child does not prove them.

The follow-on [native fixture](../../packages/harness/test/fixtures/native-domain-host.mjs)
and [public subprocess tests](../../tests/runtime/test_harness_native_domain.py)
do connect the actual pinned native SDK Library tool, private Node/Python pipes,
and an owned Python callback. The host's admitInput hook captures the immutable
user input binding before scheduling; Python matches it to the actual prompt
receipt rather than trusting the tool payload. The native assistant message ID
is independently asserted different from the input ID. A single CPU worker
awaits a nested native prompt and its observed result with max_inflight=1 and
max_domain_inflight=1, after the outer submit receipt frees its data position.
The outer Library tool remains pending during this work. The retrieved passage,
exact locators and reference-only dependencies survive native consumption.
Three TestLLM dispatches account for outer tool, nested extraction and outer
continuation; no provider runs. Python Library/Memory engines and real canonical
publication are not substituted by this synthetic callback.

Native cancellation without close remains pending through CPU and async finalizer
settlement, then returns cancelled_settled. When close races that cancel, native
runtime disposal can end the separate cancel receipt as uncertain_after_disconnect.
Close and public settlement still include actual domain finalization; a cancelled
callback publishes no value. Tests keep these command observations distinct.

## Red/green receipts

Owned receipts: C:/Renulus/scratch/oc-h02-h08/domain-ipc/.

| Slice | Red | Green |
| --- | --- | --- |
| Awaited nested callback | cycle01-red.xml: missing module | cycle01-green.xml: 1 passed |
| CPU/finalizer settlement | cycle02-red.xml: missing cancel seam | cycle02-green.xml: 2 passed |
| Duplicate/conflicting callback effect | cycle03-red.xml: effect repeated four times | cycle03-green.xml: 3 passed |
| Independent callback/results/control budgets | cycle04-red.xml: missing capacity config | cycle04-green.xml: 4 passed |
| Actual Node/Python factory/pump | cycle05-red.xml: no factory seam; initial green failed boot projection | cycle05b-green.xml: 1 passed |
| Delayed pipe publication | cycle06-red.xml: fixture observed status before reply; corrected cycle06b-red.xml: stale value published | cycle06-green.xml: 1 passed |
| Typed safe API failures | cycle07-red.xml: API identity replaced by generic error | cycle07-green.xml: 1 passed |
| Narrow authenticated recovery lookup | cycle08-red.xml: command not admitted | cycle08-green.xml: 1 passed, known/unknown/duplicate/forged payload |
| Node callback identity/capacity/abort | node-cycle02-red.txt: callback timed out | node-cycle02-green.txt: 2 passed |
| Actual native SDK, pipe callback and owned CPU/finalizer | cycle09-red.xml: dedicated fixture absent | cycle09b-green.xml: 2 passed; final-native-domain02.xml: 3 passed |

Earlier affected regression: python-regression01.xml, 169 passed; later
python-regression02.xml, 170 passed. Node native foundation/domain regression:
node-regression01.txt, 16 passed. TypeScript passed after the Unicode validation
compatibility repair. These are distinct runs, not a combined acceptance claim.
Final affected transport run final-transport02.xml: 66 passed, including a
ThreadPoolExecutor(max_workers=1) worker awaiting a native prompt through the live
owning loop. TypeScript passed after consuming the published native prerequisites.
Final Node foundation/Library/domain run final-node02.txt: 17 passed.
The initial cycle09-green.xml incorrectly expected a racing cancel's receipt to
prove clean cancellation, and final-native-domain01.xml incorrectly expected that
receipt to remain pending during runtime disposal. The corrected final native
run verifies actual domain settlement separately and adds cancellation without
concurrent close; all three cases passed in 12.86 seconds.
