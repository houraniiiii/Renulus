# H01 managed-child IPC transport

Scope: Python transport and Node IPC entry, based on
`c2bd896420fb88f76d63ca576414dbbba182f4c2`. The integration owner supplies the
actual source-built Node/OpenCode host, manifest verification and store lease.
The Python synthetic child proves transport behavior only. Separate opt-in tests
exercise the real SDK child through the Python supervisor with SDK TestLLM.

## Integration interface

Import `HarnessProcessConfig` and `ManagedHarnessProcess` from
`renulus.runtime.harness_process`. All five methods are asynchronous:

```python
process = ManagedHarnessProcess()
ready = await process.start(HarnessProcessConfig(
    node_executable=Path("C:/explicit/node.exe"),
    host_entry=Path("C:/explicit/host.mjs"),
    profile_root=Path("C:/explicit/owned/profile"),
    profile_id="profile-id", store_id="store-id",
    domain_store_id="domain-store-id", domain_path="state/renulus.sqlite",
))
reply = await process.request(
    "session.create", {"title": "Synthetic learning"},
    operation_id="operation-id", attempt_id="attempt-id", timeout=10,
)
later = await process.query_result(reply["request_id"])
closed = await process.close(timeout=10)
```

Configuration defaults: `max_inflight=8`, `max_control_inflight=4`,
`max_frame_bytes=1048576` (including newline), `start_timeout=10` seconds,
`max_result_records=256`, `max_result_bytes=16777216`.
`boot_settings` is an explicitly supplied JSON object merged into boot;
overriding the reserved identity/root fields is prohibited. Tests may supply
inert test settings here. Ambient settings and credentials are never copied.
`domain_store_id` and `domain_path` are also reserved explicit configuration;
the path is relative to the owned root and validated by the paired-store helper.

Before creating the child, `start` calls the shared
`prepare_harness_profile(root, profile_id=..., domain_store_id=...,
runtime_store_id=store_id, domain_path=...)`. It creates or verifies the prepared
selection at `state/harness/manifest.json`; no database is opened or marked valid.
The manifest pins source `4b6fea2875e4f2e3e8a8fee181803e54f7056845` and runtime
path `state/harness/opencode.sqlite`. Mismatching existing selections fail through
that helper. The Node host must independently verify the manifest before DB writes.

`start` returns the authenticated ready frame (without token). Invalid local
configuration raises `ValueError`; launch/readiness failures raise
`HarnessProcessError`. A live process is retained even on readiness failure and
must be settled with `close`. Each transport owns one generation: instantiate a
new transport after settlement to reopen the host. Keep the previous object if
its results still need querying. This prevents restarts from bypassing lifetime
retention limits or mixing generation-specific pipe tasks.

`request` returns a JSON dictionary, including all request identities except
the secret token, `outcome`, and `result` or structured `error`. Invalid commands,
payloads, overlarge frames and saturated admission are rejected before sending.
Data admission is bounded independently from reserved controls `host.status`,
`session.cancel`, `host.close`. `host.activate`, `host.recover`, `session.create`,
`session.prompt`, `session.get`, `session.messages` use data capacity.

A caller timeout returns `accepted_pending` with the original `request_id`.
It never resends or cancels the owned request. The returned `observation` is
`timeout`, and local `admission` distinguishes `transport_queued`,
`sent_unacknowledged`, `host_accepted`, and `rejected_before_admission`. A local
timeout does not establish host acceptance; only an authenticated host reply can.
`query_result` is a local lookup (unknown/unadmitted IDs return `None`), preserving
later replies for the object's lifetime. These observation fields are local;
the host's wire contract is unchanged.
Host `accepted_pending` replies also retain admission until a terminal reply.
Caller cancellation abandons only observation. Old/mismatched identities cannot
resolve a request. Process/pipe failure settles unresolved records as
`uncertain_after_disconnect`; it cannot establish rejection or successful drain.

`close` closes data admission, sends the reserved close command and bounds the
wait for actual child exit. It returns `{state, outcome, ...}`: successful
settlement is `closed` / `cancelled_settled`; a still-live or unproven drain is
`blocked` / `uncertain_after_disconnect`. It never kills the child or releases a
store lease. Later explicit `close` calls can observe settlement. Results and
process ownership survive a close timeout. The Node host alone owns store leases.

Both data and control have separate retained-record count and byte budgets.
Admission reserves room for a maximum reply, as well as pending request bytes
and identity metadata. Exhaustion returns `rejected_before_admission` with
`error.code=result_capacity`; it never evicts a prior reply. Local rejections
are returned directly without adding ledger entries. Close has its own single
reserved result/queue slot, so exhausted data and control ledgers cannot prevent
an explicit shutdown. The outbound queue is bounded and prioritizes waiting
controls; it cannot preempt bytes already in the pipe. Host/store reconciliation
and a fresh transport generation are required for work beyond a filled ledger.
The byte budget accounts for stored wire bytes and serialized identity metadata;
record counts also bound Python object overhead. The receiver retains original
reply bytes, so numeric normalization cannot expand the stored reply. Returned
snapshots are independent decoded values and omit the token. Caller-retained
snapshots are outside the transport's ledger budget.

## Wire contract

Private stdin/stdout carry one UTF-8 JSON object per LF-terminated frame. Stderr
is continuously drained separately and never parsed as protocol or persisted.
The Python child launcher uses explicit absolute executable/entry/root paths,
hidden Windows creation flags, a narrow OS environment allowlist and owned
home/config/cache/temp locations. Its PATH contains only the executable directory.

`RENULUS_HARNESS_BOOT` is JSON:

```json
{"protocol":"renulus-harness/1","profile_id":"p","store_id":"s","generation":"fresh-uuid","token":"fresh-secret","root":"C:/owned/profile","domain_store_id":"domain-id","domain_path":"state/renulus.sqlite"}
```

Python creates a new generation and token for each launch. Host startup emits
`{"kind":"ready", ...bootIdentities, "state":"ready"}` (state may express
policy-blocked readiness). Identity fields are `protocol`, `profile_id`,
`store_id`, `generation`, `token`; `root` is not an echoed identity.

Request: `{"kind":"request", ...bootIdentities, "operation_id":"o",
"attempt_id":"a", "request_id":"r", "command":"session.get",
"payload":{"session_id":"..."}}`.

Reply: `{"kind":"reply", ...bootIdentities, "operation_id":"o",
"attempt_id":"a", "request_id":"r", "outcome":"committed_reference",
"result":{...}}`. Allowed outcomes: `rejected_before_admission`,
`accepted_pending`, `committed_reference`, `cancelled_settled`,
`uncertain_after_disconnect`. Error replies contain an `error` object, with
at least a string `code`. Requests must always receive identity-complete replies;
command replies have no observation queue or drop-oldest policy.

The receive task stays available while callers await replies. No canonical
database, transaction, conversation lock or recovery lock is acquired here.
Callers must leave those physical locks before awaiting transport methods.

## Node entry and command payloads

`packages/harness/src/main.mjs` calls `runHarnessIpc` with the actual host factory
and explicit boot `{root, profile_id, store_id, domain_store_id, domain_path}`.
There is no provider/model adapter in this default entry: it starts observable
and policy-blocked, and cannot activate inference. The separate
`test/fixtures/scripted-host.mjs` supplies the SDK's counting TestLLM adapter.
Its status additions (`modelCalls`, `runtimePath`) are test evidence only.

| Command | Payload | Result |
| --- | --- | --- |
| `host.status` | `{}` | Native state/configuration/held/active IDs; while draining, `state: blocked`, `outcome: uncertain_after_disconnect`. |
| `host.activate` | `{configuration_id}` | Native status after activation. |
| `host.recover` | `{configuration_id, session_ids: [...]}` | Native status after admitting the complete held set; polling still determines completion. |
| `session.create` | `{title}` | `{session}` using native serialized session shape. |
| `session.prompt` | `{configuration_id, session_id, text}` | `{operationId, attemptId, sessionId, inputId}`. |
| `session.get` | `{session_id}` | `{session}`. |
| `session.messages` | `{session_id, limit?, order?, cursor?}` | `{messages, cursor}`; native opaque cursors and bounded paging. Cursor and order cannot be combined. |
| `session.cancel` | `{session_id}` | `{interrupted, outcome: cancelled_settled}` only after native interruption settlement. |
| `host.close` | `{}` | `{state: closed}` with `cancelled_settled` only after actual close settlement. |

Wire payload names use snake_case; native result fields retain SDK/host names.
`inputId` is the persisted inbox/user-message anchor, **not** an engine execution
ID. Operation, attempt and configuration correlation belong to saved input
metadata. The round-trip test compares the receipt with the saved user-message ID
and the same transcript after reopening. Native `wait()` is not treated as proof
that scheduled work has started or finished; tests poll terminal session state
(`succeeded`, `failed`, `interrupted`). A reply called `committed_reference` does
not establish a canonical domain commit.

Prompt configuration mismatch, recovery selection mismatch and non-quiescent
recovery are rejected before admission. Recovery is explicit, binds the whole
held set, and cannot be inferred from startup or activation. Wrong/stale boot
identities are ignored. A request ID binds its operation, attempt, command and
payload digest; conflicting reuse is rejected and an identical completed replay
returns the retained original bytes without another host invocation.
An identical still-pending replay receives an authenticated `accepted_pending`
acknowledgment; it does not occupy another record or dispatch the command again.

Node limits are explicitly configurable downward in boot `ipc`: `max_inflight`
(default/max 8), `max_control_inflight` (4), `max_result_records` (256 per lane),
`max_result_bytes` (16 MiB per lane), `max_frame_bytes` (1 MiB including LF).
Frame and byte limits have a 4096-byte minimum. Data/control ledgers reserve
pending request and maximum reply bytes plus metadata before dispatch, then retain
terminal reply bytes without eviction. Close has its own slot. Python limits
are separate; callers selecting a smaller Node frame cap must also budget their
requests accordingly. Shared pipe backpressure cannot preempt bytes already sent.
The input reader launches only admitted commands, keeps at most one partial
frame, and awaits each unretained rejection/replay write before reading more.
Admitted reply writes remain attached to bounded records. The transport keeps
active command promises and output write callbacks until they settle; normal
close drains both after SDK settlement before its final reply and clean exit.
Stdin/stdout disconnect starts the same owned SDK drain, without termination or
lease release by the transport. A failed native drain remains uncertain.

Request IDs use the shared 1..256-character identifier grammar. Invalid local
IDs are rejected by Python before sending. Node ignores malformed wire identities
before dispatch. Python authenticates each reply, strips the token, then calls
the shared `validate_command_outcome` before publishing it. Malformed terminal
frames, including an empty error code, do not settle or replace the eventual
valid reply. Ready frames remain a separate authenticated startup envelope.

## Validation

Tests exercise the five public methods through a real hidden subprocess.
Functional increments used one public failing scenario followed by minimal
implementation. Close reply/write ownership was refactored under a real-pipe
regression that passed both before and after that refactor. The tests
cover authenticated structured replies, timeouts/later lookup, reserved control
admission, process death, close timeout and later settlement, full stdin pipes,
outbound frame/shape validation, stale identities, bounded result ledgers,
readiness failures, isolated environment/no console, stable terminal outcomes,
concurrent start/close, malformed UTF-8/JSON/numbers and prepared-manifest boot.

Two independent reviews examined standards and specification behavior. The
readiness-envelope finding was repaired; a private request record centralizes
byte accounting. Public regressions reproduced and repaired four specification
findings: startup/close race, invalid normalized JSON escaping the receive loop,
numeric normalization exceeding retained-byte reservation, and settlement after
a direct `host.close` request.

Synthetic state is confined to
`C:/Renulus/scratch/oc-foundations/ipc`; fixtures launch the managed Python
interpreter as an inert stand-in executable, not a substitute OpenCode host.
The review agents used their separately owned scratch directories. The Node IPC
suite uses `C:/Renulus/scratch/oc-foundations/ipc-sdk`; actual SDK host internals,
cross-process store lease implementation and packaged Windows acceptance remain
parent-owned. The default entry stays policy-blocked; TestLLM is fixture-only.
Parent reports the isolated actual-host Node runtime at
`C:/Renulus/scratch/ocf/runtime/node.exe` is v26.4.0; this transport does not
substitute or discover a Node executable automatically.

Run the complete transport suite from the foundations worktree:

```powershell
& 'C:/Renulus/dev/python/Scripts/python.exe' -m pytest tests/runtime/test_harness_process.py -q --basetemp=C:/Renulus/scratch/oc-foundations/ipc/pytest -p no:cacheprovider
```

The first transport review follow-ups confirm both standards findings and all
four specification findings resolved. A later review reproduced and repaired the
empty-error-code defect through the shared validator, with public request-ID
validation added before dispatch. Shared-contract optional replies (bodyless
pending acknowledgments and `error: null` on a successful result) were also
reproduced red and repaired by removing a conflicting preliminary shape gate.
The final standards and specification reviews report no remaining material
findings in their scopes. The specification reviewer additionally probed concurrent
stdin EOF and stdout pressure and found no self-wait deadlock or unbounded queue.
There is no installed Python static type checker in this managed environment.
The parent asked to review before further staging/commit: the initial four-file
snapshot is staged, subsequent repairs are unstaged, and this lane has no commit.

Actual SDK tests are opt-in. Without `RENULUS_HARNESS_NODE` or the source-built
cohort packages, `tests/runtime/test_harness_sdk.py` skips. The reviewed local
run selects Node **v26.4.0**, and `packages/harness/node_modules` resolves to
`C:/Renulus/scratch/ocf/cohort/node_modules`. The cohort READY inventory is
`146d6a4f63a1a699c749d4ede05cb8fa944181ea62e4dbf8dbd0f11ac3e6bd74`.

Final lane validation on October 10, 2026: **46 Python transport tests passed**
(10.79 s), then **14 actual SDK IPC tests passed** (93.21 s) with the final
shared-outcome validator. The opt-out check reported **14 skipped**. Harness
TypeScript typecheck, all four owned Python files' compilation and scoped
`git diff --check` passed. The parent separately repaired SDK startup cleanup
while this final IPC run was active; the host API was unchanged and its focused
corruption/cleanup/reopen regression passed in the parent lane.

Machine-readable evidence and source hashes are at
`C:/Renulus/scratch/oc-foundations/ipc-sdk/receipt.json`; the final SDK JUnit
record is `C:/Renulus/scratch/oc-foundations/ipc-sdk/final-sdk.xml`.
The lane is stable for parent integration. This is IPC/SDK boundary evidence;
renderer and installed/package acceptance are parent-owned.

```powershell
$env:RENULUS_HARNESS_NODE = 'C:/Renulus/scratch/ocf/runtime/node.exe'
& 'C:/Renulus/dev/python/Scripts/python.exe' -m pytest tests/runtime/test_harness_process.py tests/runtime/test_harness_sdk.py -q --basetemp=C:/Renulus/scratch/oc-foundations/ipc-sdk/full -p no:cacheprovider
& $env:RENULUS_HARNESS_NODE packages/harness/node_modules/typescript/bin/tsc --noEmit -p packages/harness/tsconfig.json
```

The SDK tests cover policy-blocked default startup, explicit activation, prompt
configuration rejection without dispatch, native user-message receipt and
transcript persistence, runtime-only PATH, bounded record/byte/inflight admission,
actual cancellation and close settlement, explicit held recovery, and native
cursor pagination across reopen. They preserve native `idle` transcript records
as well as the six user/assistant messages from three turns. Wire-only scenarios
launch the same real SDK fixture with the same prepared-profile and owned-env
rules to test conflicting IDs, invalid identifiers and pipe backpressure; these
are tests of the public wire, not a second product execution host.
