# Python-owned final subscription HTTP gateway

2026-10-11. Providers lane, branch `codex/oc-harness-gateway-h04`, assigned
checkout `C:/Users/karol/.codex/worktrees/oc-providers/repo`. Final prerequisite
is parent `8fed6092fe282b8475654e93ea2b28a37a45789f`. Original implementation
`428c818feb2343cf9a21765887cc7da209e9a413` was verified on
`9a1893eb7ddb0bc7aa0c492ee375e83a285d82fd`, which contains provider preparation
`07da2a3e0d6c7b6cec77212fe1d82bb61322d74f`. It is carried forward without
rewriting that published commit as `8fb793737d00a8576ccebd51c2c6d21aa99732cd`.
The final owned patch binds the newer H04 continuation and permit-purpose gates.
This change owns only
`runtime/renulus/runtime/harness_gateway.py`,
`tests/runtime/test_harness_gateway.py` and this evidence note.

## Exact public interface

```python
@dataclass(frozen=True)
class GatewayBounds:
    max_request_bytes: int
    max_response_bytes: int
    timeout_seconds: float

HarnessGateway(
    manager: ProviderManager | None,
    authority: ConfigurationAuthority | None,
    *,
    cancellation: DomainCancellation | None,
    check_current: Callable[[], bool] | None,
    http_transport: httpx.AsyncBaseTransport | None,
    bounds: GatewayBounds,
)

await gateway.dispatch(
    run_id: str,
    step_id: str,
    route: SubscriptionRoute,
    serialized_request: dict,
    *,
    limits: RouteLimits,
    input_tokens: int,
    required_capabilities: tuple[str, ...],
    request_kind: str,
    continuation_of: str | None = None,
) -> dict
```

The real provider class is `ProviderManager`. The gateway uses only its public
`require_harness_route`, `credential_for_harness` and
`observe_harness_stream_error` methods. It does not select a model, create a run,
read private manager fields or obtain authority from serialized model arguments.
Missing actual manager, configuration authority, domain cancellation, current
guard or explicit HTTP transport denies before reservation.

The parent must bind the existing H04 run and stable purpose to its resolved
role model, prepare the corresponding protected manager route, supply actual
`RouteLimits`, and account for the complete final serialized input. The current
guard is synchronous and must return exactly `True` while the binding is valid.
The configuration `ConnectionReference` must match provider, protected reference
and credential epoch. This module does not introduce another role selector.

The gateway reserves one durable permit through `admit`, then calls
`mark_dispatched` once immediately before its owned HTTP IO. Parent composition
must not reserve a second permit for the same send. The exact body SHA-256 binds
both operations. Output must be explicit and bounded: Codex Responses uses
`max_output_tokens`; Go chat uses `max_completion_tokens`. H04 enforces the input,
output, context reserve/window and shared dispatch budget.

Tool continuation requires a new step, `request_kind="tool-continuation"`, and
the previous confirmed transport `permit_id` from the same run. A confirmed
permit means the buffered HTTP transport finished. It does not establish native
model terminal success, tool success, account modality or learning publication.
The parent owns those observations and terminal settlement. Other request kinds
are subject to the existing H04 allowlist and purpose policy. There is no retry
parameter, fallback or same-step resend.

The final gateway requires the actual parent H04 public interfaces
`admit(..., continuation_of=...)` and
`require_current(..., permit_id=..., conn=...)`. It forwards the explicit
continuation reference at admission and binds every current check after
reservation to the owned permit. This preserves the permit's dispatch purpose
even when a run includes auxiliary requests. The owned permit remains bound
through idle HTTP, response buffering and finalization, then is cleared when
dispatch ownership ends. There is no fallback to the earlier H04 API. The parent
publication transaction must recheck the same permit through `require_current`
with its supplied canonical connection, after native terminal success.

Each gateway owns its injected transport through finalization. Production
composition should explicitly supply `httpx.AsyncHTTPTransport(retries=0)`;
custom transports are trusted and must perform one send without hidden retries.
Do not share this transport with unrelated owners. Bounds allow request sizes
1..32 MiB, response sizes 1..16 MiB and a finite positive timeout up to 300 seconds.
The parent must choose smaller bounds compatible with its IPC frame capacity.

## Native wire and response envelopes

Exactly four request keys are permitted:

```json
{
  "method": "POST",
  "url": "<exact selected SubscriptionRoute.endpoint>",
  "headers": {"content-type": "application/json"},
  "body_base64": "<base64 of native HttpClientRequest.body.body>"
}
```

The pinned `createSubscriptionAdapter` dispatch Effect receives the actual
serialized `HttpClientRequest`. It requires POST, exact endpoint, no query
parameters and a `Uint8Array` body. The gateway independently checks the same
endpoint, H04 protocol/model and exact native wire model. It rejects envelope
authority, extra auth/cookies/host headers, WS, redirects, alternate endpoints,
oversized input, duplicate/nonfinite JSON, hidden replay/retention/compaction,
hosted tools, multiple completions and priority service-tier widening.

Recognized optional safe headers are exact content length,
`accept: text/event-stream`, `accept-encoding: identity`,
`user-agent: Renulus/0.1.0`, and a bounded Go `x-opencode-session`. The owned
HTTP request reconstructs these values. Authorization is injected only after
resolving the protected credential in Python and revalidating the route.
`trust_env=False` and `follow_redirects=False` prevent ambient proxy settings
and redirected credential dispatch. No default transport is constructed.

The successful result has four keys:

```json
{
  "status": 200,
  "headers": {"content-type": "text/event-stream"},
  "body_base64": "<complete bounded raw SSE bytes>",
  "permit_id": "<durable transport receipt>"
}
```

There is no text decoding/re-encoding between native serialization and HTTP IO,
or between the buffered provider bytes and native reconstruction. Actual native
consumption is verified with the public pinned API:

```typescript
HttpClientResponse.fromWeb(request, new Response(
  Buffer.from(result.body_base64, "base64"),
  { status: result.status, headers: result.headers },
));
```

HTTP 200 requires uncompressed SSE. Response bytes are bounded while reading;
cookies, locations and arbitrary response headers never return to Node. Non-200
bodies are closed unread, including oversized/compressed 401 bodies. Status-only
401/403 invalidates the credential-epoch access observation through the public
manager API; 429 and known SSE failure machine codes use the same public error
mapping. Provider prose and arbitrary transport/current-guard exceptions are
not exposed. Raw, escaped JSON and split text-delta credential echoes are
refused. Successful transport does not automatically record capability success.

The current/domain/configuration/credential gates are checked before IO, during
buffering, while headers/body are idle, and after actual finalization. A
50-millisecond cooperative monitor cancels the worker once on cancellation,
revocation or deadline. Repeated caller cancellation cannot abandon or
re-cancel the HTTP finalizer. The busy slot and durable attempt remain owned
until the worker has really settled. A non-cooperative finalizer remains owned;
the timeout does not falsely declare it settled. Failed/uncertain sends are not
automatically replayed.

## Red/green receipts

All receipts and synthetic profiles are under
`C:/Renulus/scratch/oc-h02-h08/providers/gateway/`. The table refers to files in
`receipts/`. Counts describe each run; overlapping green cases are not added.

| Cycle | Red receipt | Green receipt | Behavior |
| --- | --- | --- | --- |
| c01 | c01-red.xml: module absent, one collection error | c01-green.xml: 1 passed | Protected successful POST and one H04 permit |
| c02 | c02-red.xml: 15 failed | c02-green.xml: 16 passed | Reject envelope/URL/auth/WS/fallback/size authority |
| c03 | c03-red.xml: 14 failed | c03-green.xml: 15 passed | Exact model/stream/output/body identity |
| c04 | c04-red.xml: 7 failed | c04-green.xml: 8 passed | Redirect/auth/rate/server/size/echo/read refusal and no replay |
| c05 | c05-red.xml: 4 failed | c05-green.xml: 4 passed | Cancellation/revocation retains actual HTTP finalizer |
| c06 | c06-red.xml: 4 failed | c06-green.xml: 4 passed | Confirmed same-run continuation reference |
| c07 | c07-red.xml: 1 failed | c07-green.xml: 2 passed | HTTP200 failed SSE uses machine code without provider prose |
| c08 | c08-red.xml: 5 failed | c08-green.xml: 7 passed | Reject serialized budget widening; native local-server checks |
| c09 | c09-red.xml: 7 failed | c09-green.xml: 7 passed | Valid finite transport bounds |
| c10 | c10-red.xml: 1 failed | c10-green.xml: 1 passed | Parent guard diagnostics cannot escape |
| c11 | c11-red.xml: 2 failed | c11-green.xml: 5 passed | Escaped/split credential echoes refused; native roundtrips retained |
| c12 | c12-red-02.xml: 2 failed | c12-green.xml: 9 passed | 401 invalidation independent of untrusted body decoding/bounds |
| c13 | c13-red.xml: 1 failed | c13-green.xml: 1 passed | Explicit continuation retains summary purpose after a primary in the same run |
| c14 | c14-red.xml: 2 failed | c14-green.xml: 2 passed | Auxiliary permit purpose revocation blocks both late response and idle HTTP |

`c12-red.xml` preserves the initial compressed fixture that HTTPX decoded while
constructing a mock response. `c12-red-02.xml` uses an actual AsyncByteStream
and records both meaningful pre-fix failures. Earlier `final-owned.xml` records
86 passes before the final two 401 cases; it is not evidence for all final 88.
Additional final regression cases exercise already implemented behavior: missing
dependencies, limits/proof/current route, stale credential epoch, revocations,
same-step suppression, idle-header deadline, chunk bounds and duplicate JSON.

The four inherited provider discrepancies were already committed in provider
preparation. Their exact baseline/current test IDs and separate four-case
red/green receipts remain in
[the provider preparation ledger](opencode-providers-preparation.md#exact-retained-four-case-redgreen-ledger).
This gateway does not change those tests or their expectations.

## Connected native synthetic HTTP proof

`test_pinned_native_tool_and_image_roundtrip_uses_actual_loopback_http` executes
twice, for Codex Responses and Go chat. `native-01.xml` records both passing
cases; they also run in the complete owned suite. An actual pinned Node child
uses `createSubscriptionAdapter` and `LLMClient.generate`; its final serialized
HTTP bytes travel to this gateway through a test-only stdin/stdout exchange.
An explicit synthetic transport maps the validated remote route to an owned
async loopback HTTP server. Its inner transport is actual
`httpx.AsyncHTTPTransport(retries=0)`. There is no production loopback bypass.

The native first response emits `native-call`; the next native request carries
its matching tool result and inline PNG. Both final wire bodies pass the managed
Python `validate_harness_images` decoder. Each protocol records two image
validations, two actual local HTTP requests, two durable permits and final native
text `Synthetic gateway answer`. The selected wire model and matching tool
call/result IDs are asserted on the actual received HTTP JSON. The protected
synthetic credential stays in Python and is checked at the local HTTP seam; it
is not supplied to Node.

The pinned cohort is unchanged: source
`4b6fea2875e4f2e3e8a8fee181803e54f7056845`, source-built packages 2.0.26,
managed Node 26.4.0. The ignored declared
`packages/harness/node_modules` junction points to
`C:/Renulus/scratch/ocf/cohort/node_modules`. No private profile, live provider
call, account credential, acquisition or provider charge was used.

## Final verification and remaining composition

The final H04-bound gateway was verified on parent prerequisite `8fed6092`:

```powershell
& 'C:/Renulus/dev/python/Scripts/python.exe' -m pytest tests/runtime/test_harness_gateway.py `
  --basetemp=C:/Renulus/scratch/oc-h02-h08/providers/gateway/final-h04 `
  --junitxml=C:/Renulus/scratch/oc-h02-h08/providers/gateway/receipts/final-h04.xml `
  --tb=line -q
```

Result: **91 passed, zero skipped**, in 24.57 seconds. This includes both pinned
native tool/image local-HTTP roundtrips and the three new H04 behaviors. Exact
new test IDs are
`test_explicit_continuation_preserves_its_permit_purpose_in_a_mixed_run` and
`test_dispatched_permit_purpose_is_rechecked_after_or_during_http[response]` /
`[idle]`. Each red/green command selected its corresponding test function from
`tests/runtime/test_harness_gateway.py`, used `--tb=line -q`, wrote its
`receipts/c13-red.xml`, `c13-green.xml`, `c14-red.xml` or `c14-green.xml`, and
used the corresponding `gateway/c13-red`, `c13-green`, `c14-red` or `c14-green`
basetemp directory. No broad suite was rerun for this H04 update.

The original implementation on `9a1893eb` ran the following commands. Those
historical receipts are retained and do not establish a broad-suite result for
the newer parent prerequisite:

```powershell
& 'C:/Renulus/dev/python/Scripts/python.exe' -m pytest tests/runtime/test_harness_gateway.py `
  --basetemp=C:/Renulus/scratch/oc-h02-h08/providers/gateway/final-owned-02 `
  --junitxml=C:/Renulus/scratch/oc-h02-h08/providers/gateway/receipts/final-owned-02.xml `
  --tb=line -q

$env:RENULUS_HARNESS_NODE='C:/Renulus/scratch/ocf/tools/node-v26.4.0-win-x64/node.exe'
& 'C:/Renulus/dev/python/Scripts/python.exe' -m pytest tests/runtime `
  --basetemp=C:/Renulus/scratch/oc-h02-h08/providers/gateway/final-runtime `
  --junitxml=C:/Renulus/scratch/oc-h02-h08/providers/gateway/receipts/final-runtime.xml `
  --tb=line -q

$env:RENULUS_LIBRARY_HELPERS='C:/Renulus/dev/helper-assets'
& 'C:/Renulus/dev/python/Scripts/python.exe' -m pytest tests/runtime/test_harness_library.py `
  --basetemp=C:/Renulus/scratch/oc-h02-h08/providers/gateway/final-library `
  --junitxml=C:/Renulus/scratch/oc-h02-h08/providers/gateway/receipts/final-library.xml `
  --tb=line -q
```

The original owned suite passed **88 cases, zero skipped**, in 27.01 seconds. This
includes both pinned native local-HTTP tool/image roundtrips. The full runtime
sweep collected 488 cases: **454 passed, zero failures, 34 setup errors**, in
370.43 seconds. All 88 gateway cases and all four retained provider discrepancy
cases passed in that sweep. Every setup error was
`KeyError: RENULUS_LIBRARY_HELPERS` in the parent-owned Library fixture. The
third command reruns the Library test file with declared public helper assets;
**41 passed, zero skipped**, in 55.81 seconds. That includes the 34 setup-error
cases and seven cases already green in the broad sweep. All 488 distinct runtime
cases therefore have passing evidence across these two runs; this is not a fresh
fully configured 488-case sweep. No protected source or test was modified.

Standards/specification review was local, without agents. The staged whitespace
check passed. No manager/configuration/Services/IPC/host, database/migration,
dependency lock or ticket/status edits were made. The work is committed locally;
no push is part of this handoff.

This checkout consumes the parent's committed `8fed6092` prerequisite without
authoring any shared changes. Parent-owned Services/host/IPC must bind
this gateway into authenticated `model.dispatch`, derive the run/purpose/current
route from the trusted native binding, calculate final-body input tokens, and
own native terminal success, publication and cancellation settlement. The
test-only exchange is not production DomainClient assembly.

Synthetic limits and token proofs demonstrate enforced boundaries, not measured
account/model limits or tokenizer acceptance. Documented modality remains
separate from account availability and credential-epoch observations. Base64
expands the SSE bytes; parent IPC capacity must include that expansion and
framing metadata. Account access, image interpretation, complete saved
production composition and Windows package validation remain downstream gates.
H03 and H02-H08 are not claimed accepted by this change.

## Exact Node boundary

The authorized contract is implemented in `packages/harness/src/gateway-adapter.ts`
and its dedicated tests/fixture. Parent owns the actual host,
learning-host, server, IPC command registration, current role selection, native
context hook and terminal/publication guard. No entry-point cutover is included.
The actual public `DomainClient.request` and pinned
`createSubscriptionAdapter` dispatch Effect are the underlying seams.

```typescript
interface SerializedSubscriptionHttp {
  readonly method: "POST";
  readonly url: string;
  readonly headers: Readonly<Record<string, string>>;
  readonly body_base64: string;
}

interface TrustedGatewayPreparation {
  readonly dispatch_id: string;
  readonly binding: DomainBinding;
  readonly role: {
    readonly version: string;
    readonly purpose: string;
    readonly model_id: string;
    readonly output_tokens: number;
    readonly dispatch_limit: number;
  };
  readonly request_kind: "primary" | "tool-continuation";
  readonly continuation_of?: string;
  readonly route: SubscriptionRoute;
  readonly native_capabilities: Model.Capabilities;
  readonly limits: {
    readonly input_tokens: number;
    readonly output_tokens: number;
    readonly window_tokens: number;
  };
  readonly required_capabilities: readonly string[];
  readonly bounds: {
    readonly max_request_bytes: number;
    readonly max_response_bytes: number;
    readonly max_frame_bytes: number;
  };
}

async function createGatewayAdapter(options: {
  readonly domain: DomainClient;
  readonly beforePrepare: (binding: DomainBinding) =>
    Effect.Effect<TrustedGatewayPreparation, AIError>;
  readonly validateImages: (binding: DomainBinding, images: readonly InlineImage[]) =>
    Effect.Effect<void, AIError>;
}): Promise<{
  readonly client: LLMClientShape;
  prepare(
    trustedNativeBinding: DomainBinding,
    request: LLMRequest,
    settings?: StreamOptions,
  ): Effect.Effect<LLMRequest, AIError>;
  receipt(request: LLMRequest): Readonly<{
    dispatch_id: string;
    permit_id: string;
  }> | undefined;
  close(): Promise<void>;
}>;
```

`DomainBinding` has exactly `operation_id`, `attempt_id`, `session_id`, `input_id`
and `cancellation_id`. The role fields above project the existing H04 binding;
the module does not resolve another role or use `request.model` as authority.
`beforePrepare` runs for every primary/continuation before subscription-adapter
preparation. Parent derives its result from the owning binding and its current
configuration/run. Preparation creates no durable transport permit.

Parent's post-preparation native-context hook invokes
`adapter.prepare(binding, finalContextRequest, prepared.options)` and admits the
returned request identity. The adapter updates the native `LLMRequest.model` and
explicit output ceiling to the trusted role route, retains per-request dispatch
metadata and delegates through a per-request `createSubscriptionAdapter`. The
composition client accepts only registered request identities, once. There is
no global static route override or default network executor. Parent must also
apply trusted native model/capabilities before any upstream capability filter
that could remove image inputs; a post-preparation hook cannot restore discarded
content.

The Domain payload wraps the exact Python wire envelope:

```typescript
domain.request(trustedNativeBinding, "model.dispatch", {
  dispatch_id: trustedPreparation.dispatch_id,
  serialized_request: {
    method: request.method,
    url: request.url,
    headers: request.headers,
    body_base64: Buffer.from(request.body.body).toString("base64"),
  },
});
```

`dispatch_id` is a parent-created opaque correlation key registered against the
full authenticated binding and one trusted run/step preparation. It grants no
authority by itself. The Python command handler accepts only those two payload
keys, resolves the registered record and revalidates current authority. It never
accepts run, step, purpose, role, route, limits, required capabilities, token
proof or continuation authority from model arguments or echoed metadata.
Stale, unknown, mismatched, repeated and overlapping preparations fail closed.
For a continuation the registered record identifies the explicit previous
same-run transport permit and a fresh step.

The handler accounts for the exact final serialized body after all native
transformations, including tool definitions/results and images, then supplies
its trusted `input_tokens` to the Python dispatch signature above. Node token
numbers are not accepted as proof. The gateway independently checks endpoint,
protocol, model, output ceiling and body identity before its single H04 admit
and final dispatch mark.

The terminal Domain outcome must be `committed_reference` with exactly the
gateway's safe `status`, `headers`, `body_base64` and `permit_id` result. The
module's local `bufferedHttp` wrapper validates the outcome, canonical base64,
bounds, safe headers and permit identity before calling actual
`HttpClientResponse.fromWeb`. Accepted-pending, errors, cancellation, disconnect,
uncertain acknowledgement and malformed results cannot become native responses
or publication receipts. Custom HTTP/WS, fallback, unbound calls and compaction
remain refused. Cancellation forwards through the Domain request and retains
ownership until settlement. The parent must configure IPC frame capacity for
base64 expansion plus identity/framing overhead.

`receipt(request)` exposes the verified transport permit for that bound request.
It is not terminal model success. Parent publication still requires its strict
native terminal check and permit-bound current H04/domain checks inside the
canonical publication transaction. Parent subsequently reported its strict native
terminal fix green; this lane does not modify that implementation or replace its
terminal/publication checks.

## Node implementation and evidence

The Node change is based on full gateway prerequisite
`4fbaf23cfa993e1f32e273f8e9169ae29cccf4c1`, preceded by
`8fb793737d00a8576ccebd51c2c6d21aa99732cd` on parent
`8fed6092fe282b8475654e93ea2b28a37a45789f`. Parent reports the Python changes
consumed as `29e03c7b` and `9c30e29b`. It also requires the pinned public
`createSubscriptionAdapter`, `DomainClient`, `LLMRequest.update`,
`GenerationOptions`, and `HttpClientResponse.fromWeb` seams already in this
baseline. No dependency, host, learning-host, IPC, server, configuration,
Services, shared-contract or entry-point change is part of the Node commit.

The factory requires a real bound `DomainClient` and both trusted callbacks.
It snapshots and freezes binding/preparation data, validates role/route/bounds
consistency, and runs `beforePrepare` for each primary/continuation. The actual
`Model.Capabilities` shape from `@opencode/schema/model` is `{ tools: boolean,
input: readonly string[], output: readonly string[] }`. Parent supplies that
projection from its existing selector. The module checks actual images/tools
against it at preparation and consumption; it does not select a second role or
estimate account availability. The selected provider's native model replaces
the model supplied by the incoming request. The explicit role output ceiling
is serialized as `max_completion_tokens` for Go and `max_output_tokens` for
Codex, then rechecked on the final bytes. No second budget/admission exists.

Only the exact returned request identity can be consumed, once, through either
`generate` or `stream`. Clones, repeated/concurrent use, custom HTTP/WS, direct
compact and requests after close fail closed. Final native images travel through
the supplied parent decoder before `model.dispatch`. The gateway payload has
exactly the two documented keys; role, purpose, route, continuation, limits,
capabilities and token proof never become model-envelope authority.

Bounds are positive safe integers. `max_request_bytes` caps the final serialized
HTTP body, `max_response_bytes` caps decoded SSE bytes, and `max_frame_bytes`
caps the serialized outgoing payload and token-free authenticated outcome
(including newline). The **parent must also configure the existing
`DomainClient`/IPC full-frame limits**, accounting for base64 expansion,
authenticated identity, binding, callback, token and JSON framing. The module
uses no private Domain fields and cannot introspect its configured limits. A
valid 512,000-character synthetic reply passed at its exact declared decoded
byte bound with a 1 MiB full Domain frame.

Only a terminal `committed_reference` result with exactly `status: 200`,
`headers: { "content-type": "text/event-stream" }`, canonical nonempty
`body_base64` and an opaque `permit_id` becomes native HTTP. Redirects, unsafe
headers, malformed/noncanonical bodies, oversize results and noncommitted
outcomes cannot yield a receipt. `receipt(request)` returns a frozen
`{ dispatch_id, permit_id }` after safe transport reconstruction, including after
the native operation's finalizer. This proves transport settlement only; parent
must still verify strict native terminal success and current permit-bound
publication authority.

Interruption forwards an owned AbortSignal to `DomainClient.request` and waits
for the actual terminal callback. Close refuses new work, cancels this module's
owned IO, waits for outstanding preparation/native finalizers, and then disposes
its per-request native runtimes. It never seals or disconnects the shared Domain
client. Close during image validation waits for the supplied validation Effect
to settle and refuses the still-unsent HTTP request. Parent callbacks must own
their cancellation/finalization; this module cannot abandon their Effects or
invent an earlier settlement. Rejected, cancelled, disconnected or uncertain
IO cannot be replayed using the consumed request. Diagnostic failures are
sanitized and synthetic authentication/credential canaries are excluded from
test output and receipts.

All Node receipts are under
`C:/Renulus/scratch/oc-h02-h08/providers/node-gateway/receipts`. Each red/green
pair below ran its one named public behavioral test, using the pinned Node and
the command template shown below. Every red has **1 failed**, every green
**1 passed**, with no skipped or cancelled cases.

| Cycle | Public behavior | Red / green receipts |
| --- | --- | --- |
| n01 | Native HTTP serialization, exact two-key payload, bound receipt | `n01-red.xml` / `n01-green.xml` |
| n02 | Single use of exact prepared identity across generate/stream | `n02-red.xml` / `n02-green.xml` |
| n03 | Incoherent and repeated trusted preparations refused | `n03-red.xml` / `n03-green.xml` |
| n04 | Safe exact response, canonical base64 and byte/frame bounds | `n04-red.xml` / `n04-green.xml` |
| n05 | Final transformed request/payload bounds | `n05-red.xml` / `n05-green.xml` |
| n06 | HTTP/WS settings cannot escape at prepare/consume | `n06-red.xml` / `n06-green.xml` |
| n07 | Interruption and close retain IO through real callback settlement | `n07-red.xml` / `n07-green.xml` |
| n08 | Close waits for pending preparation and refuses late request | `n08-red.xml` / `n08-green.xml` |
| n09 | Actual native images/tools require trusted modalities | `n09-red.xml` / `n09-green.xml` |
| n10 | Preparation diagnostics sanitized; real dependencies required | `n10-red.xml` / `n10-green.xml` |
| n11 | Binding/preparation snapshots and fresh same-subscription role route | `n11-red.xml` / `n11-green.xml` |
| n12 | Mutated bound input cannot widen trusted modalities | `n12-red.xml` / `n12-green.xml` |
| n14 | Partial limit/capability records fail closed | `n14-red.xml` / `n14-green.xml` |
| n15 | Close during image validation prevents unsent IO | `n15-red.xml` / `n15-green.xml` |
| n16 | Synchronous trusted-hook failure releases preparation ownership | `n16-red.xml` / `n16-green.xml` |

`native-tools-images.xml` separately passed the actual pinned native client for
Go chat and Codex Responses: emitted tool calls, their paired native results,
managed Python-decoded images and fresh primary/continuation preparations;
**four model.dispatch requests, four decoder validations and four receipts**.
`large-bound-proof.xml` passed the large canonical reply proof.
`outcomes-stream-close.xml` passed two additional tests for pending/noncommitted
outcomes/no replay and close-only buffered-stream cancellation. Those extra
proofs were already green through the implemented public seams, not fabricated
red cycles. Final dedicated verification: **19 passed, zero skipped**, 11.34 s,
in `final-dedicated.xml`. Consumer typecheck exited 0; its output is
`final-typecheck.txt`. The full Harness suite completed before the disk-space
pause: **52 passed, zero skipped or cancelled**, 53.50 s, in
`final-harness.xml`. Source/test files were preserved unchanged across that
pause; no profile or broad test run was repeated after space recovery. The
handoff/source/receipt hash manifest is `final-node-source.json` in the same
receipt directory. The implementation worker performed a local source check
against the contract and lane ownership; this was not an independent review.
The parent's later specification review found the P2 error-category defect
documented below. Independent review and parent integration remain separate
from the module test receipts.

From `packages/harness`, the exact focused test command template was:

```powershell
& 'C:/Renulus/scratch/ocf/tools/node-v26.4.0-win-x64/node.exe' --test --test-name-pattern='<named behavior prefix>' --test-reporter=junit test/gateway-adapter.test.mjs > C:/Renulus/scratch/oc-h02-h08/providers/node-gateway/receipts/<cycle>-<red-or-green>.xml
```

Final dedicated suite and consumer typecheck:

```powershell
& 'C:/Renulus/scratch/ocf/tools/node-v26.4.0-win-x64/node.exe' --test --test-reporter=junit --test-reporter-destination=C:/Renulus/scratch/oc-h02-h08/providers/node-gateway/receipts/final-dedicated.xml test/gateway-adapter.test.mjs
& 'C:/Renulus/scratch/ocf/tools/node-v26.4.0-win-x64/node.exe' node_modules/typescript/bin/tsc --noEmit > C:/Renulus/scratch/oc-h02-h08/providers/node-gateway/receipts/final-typecheck.txt
```

The completed full-suite command was:

```powershell
& 'C:/Renulus/scratch/ocf/tools/node-v26.4.0-win-x64/node.exe' --test --test-concurrency=1 --test-reporter=junit --test-reporter-destination=C:/Renulus/scratch/oc-h02-h08/providers/node-gateway/receipts/final-harness.xml test/*.test.mjs
```

These are native module/public-Domain-seam proofs with synthetic callbacks and
the actual managed image parser. Parent still owns actual gateway command
registration/preparation map, final body token accounting, applying the trusted
preparation before native filtering, ConfigurationAuthority lifecycle, strict
terminal/publication checks and saved host composition. No live provider call, installation, credential
profile copy or account/package acceptance occurred. H03 and H02-H08 remain open.

## P2 safe error-channel repair — 2026-10-11

The parent reviewed `ccfd4de61e4347b6cadd89535e0c37113abbe320` and found that
`bufferedHttp` refused Python's safe authentication failure, then `ownedIO`
replaced the native typed error with generic `InvalidRequest`. This focused
repair changes only `src/gateway-adapter.ts`, its dedicated public tests and
this note. The public factory, preparation, client and receipt signatures are
unchanged. Successful HTTP/SSE reconstruction still requires the exact bounded
200 result described above.

Only a bounded authenticated terminal `rejected_before_admission` outcome with
no result and an exact safe code/status pair gets a fixed native error. That
Domain label does not establish whether Python's durable permit was sent; the
parent owns that state. Cancelled, uncertain, contradictory or unknown outcomes
and mismatched statuses remain generic denials.

| Python safe code | Status | Native reason |
| --- | --- | --- |
| `authentication_required` | 401 | `Authentication` |
| `subscription_limit` | 429 | `RateLimit` |
| `model_unavailable`, `model_not_found`, `model_access_denied`, `account_model_unsupported` | 409 | `InvalidRequest` with fixed model/input refresh guidance |
| `unsupported_image_input`, `image_input_not_supported`, `unsupported_input_modality`, `unsupported_modality` | 409 | Same fixed `InvalidRequest` guidance |
| `provider_stream_failed`, `provider_unavailable` | 503 | `ProviderInternal` |
| `transport_unavailable` | 503 | `Transport` (`http`, `request`) |

These codes/statuses come from Python `policy.py` and `HarnessGateway` public
failure handling. The pinned SDK has no dedicated model-unavailable reason.
Native typed `QuotaExceeded` remains `QuotaExceeded`; Python's unified
subscription limit remains `RateLimit`. Preparation and owned Promise failures
rebuild the same allowlisted native categories and fixed messages as the
existing provider adapter. A bound entry retains only the reconstructed safe
failure so native sanitization cannot erase known model/input guidance. No
provider body, prose, headers, URL, cause, retry delay or recovery instruction
is retained. Reason-shaped plain objects cannot grant a category.

Effect interruptions remain interruptions. Failed requests have no receipt,
cannot replay, do not retry even when the Domain error carries `retryable: true`,
and retain the original callback/native finalizer ownership. Authentication
errors do not become reconstructed HTTP responses.

Each focused cycle executed one public behavior: **one failing red then one
passing green**, zero skipped or cancelled cases. Receipts are under the same
`C:/Renulus/scratch/oc-h02-h08/providers/node-gateway/receipts` directory.

| Cycle | Behavior | Receipts |
| --- | --- | --- |
| n17 | Safe 401 retains `Authentication` through native generate/stream, no receipt/replay | `n17-red.xml`, `n17-green.xml` |
| n18 | Safe subscription 429 retains `RateLimit`, no retry | `n18-red.xml`, `n18-green.xml` |
| n19 | Trusted typed preparation errors retain categories and strip canaries | `n19-red.xml`, `n19-green.xml` |
| n20 | Known model/input rejection retains safe guidance after native sanitization | `n20-red.xml`, `n20-green.xml` |
| n21 | Safe provider/transport errors retain categories and omit retry instructions | `n21-red.xml`, `n21-green.xml` |

Two additional controls were already green: exact code/status/outcome checking
and typed owned-IO canary stripping, including a reason-shaped plain object.
`p2-dedicated.xml` records **26 passed, zero failures/skips/cancels, 10.55 s**.
Consumer typecheck exited zero (`p2-typecheck.txt`). No broad Harness rerun or
new SDK profile was used. The earlier 52-case receipt belongs to the original
module bytes. Exact commands, from `packages/harness`:

```powershell
& 'C:/Renulus/scratch/ocf/tools/node-v26.4.0-win-x64/node.exe' --test --test-reporter=junit --test-reporter-destination=C:/Renulus/scratch/oc-h02-h08/providers/node-gateway/receipts/p2-dedicated.xml test/gateway-adapter.test.mjs
& 'C:/Renulus/scratch/ocf/tools/node-v26.4.0-win-x64/node.exe' node_modules/typescript/bin/tsc --noEmit > C:/Renulus/scratch/oc-h02-h08/providers/node-gateway/receipts/p2-typecheck.txt
```

## One trusted preparation before native media filtering — 2026-10-11

This extension follows `307a43d79a03c9413b6bdd15b4627634abbf7393` and preserves
its safe typed errors. It implements the parent's committed `5500341e`
`PrimaryModelPreparation` interface in the gateway-owned module, tests and
fixture. No host, IPC, configuration, provider-adapter, manifest-builder,
dependency or entry-point source is changed. Its exact added interface is:

```typescript
export interface GatewayPrimaryPreparation {
  readonly resolved: SessionRunnerModel.Resolved;
  readonly prepare: (
    request: LLMRequest,
    settings: StreamOptions,
    unfiltered: LLMRequest,
  ) => Effect.Effect<LLMRequest, AIError>;
}

// New GatewayAdapter member; existing direct prepare remains available.
preparePrimary(
  binding: DomainBinding,
  resolved: SessionRunnerModel.Resolved,
): Effect.Effect<GatewayPrimaryPreparation, AIError>;

// Optional factory option; mandatory for preparePrimary.
readonly registerManifest?: (
  plan: Readonly<TrustedGatewayPreparation>,
  unfiltered: LLMRequest,
) => Effect.Effect<void, AIError>;
```

All Effects have a closed environment (`R = never`). Missing registration denies
before `beforePrepare` is invoked. Successful early preparation calls the
trusted selector once, freezes its plan, consumes one dispatch identity and
creates one native subscription adapter. `SessionRunnerModel.resolved` receives
that adapter model, the trusted native capabilities and limits
`{ input: input_tokens, output: role.output_tokens, context: window_tokens }`.
The catalogue `Model.Ref` is projected explicitly from the same route. The
incoming resolved model, capabilities, transport and compaction do not grant
authority. Only its cost metadata is cloned. The result, capabilities and
limits are frozen; no WS or opaque compaction setting is inherited.

Parent applies `resolved` before native shaping, captures its admitted context
after context hooks and selection but before `unsupportedParts`/`boundImages`,
then invokes this result's `prepare` after native preparation. The closure
reuses the original plan and adapter, checks final route/output/settings/media,
registers the manifest once, rechecks after registration and binds the returned
request identity. Calling top-level `gateway.prepare` at that point would
allocate a different plan and must not be part of this composition. The final
explicit output stays at or below the role ceiling; a smaller native limit is
preserved and a missing limit is supplied from the role. The final native
serialized bytes remain bounded and carry exactly the original dispatch ID.
No second budget, token estimate or admission is introduced.

`registerManifest` is a trusted parent callback. Parent composes its imported
`captureNativeManifest` builder and authenticated internal `model.manifest`
registration there, binding evidence to `plan.dispatch_id`. This module neither
builds a competing manifest nor accepts one from `model.dispatch` arguments.
The callback receives a plain request-shaped snapshot whose media has `.source`
and `.mediaType`, without `.inline()` methods, plus exactly the surviving native
tool definitions. It must reject lost/unproven media, invalid projections and
stale authority. Parent owns route provider metadata namespace interpretation,
imageIngress, final body input measurement and Python preparation registration.

**Construction prerequisite discovered by the actual-media fixture:** pinned
`LLMRequest.update(request, { ...structuredClone(snapshot) })` rejects plain
cloned media with `Schema validation failed`. Keep the third argument as plain
data, structurally projected from `{ ...request, ...snapshot, tools: clonedTools }`
at the trusted host seam; do not invoke the native constructor for that evidence.
The actual final native request retains its native instances. The agreed
`LLMRequest` callback type is unchanged; the evidence is never passed to a
native client. This exact representation passed the supplied callback in the
fixture. Parent was notified before finalization.

The closure is single-use, including a failed registration; concurrent reuse
cannot trigger another callback or send. Registration runs uninterruptibly
through its actual Effect finalizer. Interrupt requests and close wait for it
to settle, then dispose unsent native work and refuse IO. The callback must
implement cooperative cancellation/current checks through its supplied domain
binding and settle boundedly: this gateway cannot force an uncooperative callback
to finish. It accepts no detached registration work. Typed errors are rebuilt
with the existing safe categories/messages, and interruption stays interruption.
Close retains unused native adapters until disposal. Parent owns unused trusted
preparation-map retirement when native shaping fails before the late closure.

The actual source-built 2.0.26 fixture runs `SessionModelRequest.layer` with
public `PluginHooks` registration and an explicitly injected transport that
denies WS. Its Layer requires only `PluginHooks.Service` and
`SessionModelTransport.Service`; no host/store/profile dependency was acquired.
It exercises actual context and model.request hooks, tool renaming with native
definition identity, plain PNG evidence, native surviving tools and buffered
HTTP generation for both selected Go and Codex routes. One selector, one manifest
registration and one HTTP dispatch are observed per early preparation. The Go
order is selector → context hook → model.request hook → manifest → trusted image
validator → dispatch. Synthetic callbacks prove composition of these public
seams, not the parent's strict builder, saved store or private IPC assembly.

Each behavioral cycle ran one focused red followed by one green, with one
failure/pass respectively and zero skips/cancels. Receipts remain under
`C:/Renulus/scratch/oc-h02-h08/providers/node-gateway/receipts`.

| Cycle | Public behavior | Red / green receipts |
| --- | --- | --- |
| n22 | Early trusted native capabilities and one plan through actual hooks, manifest and HTTP | `n22-red.xml` / `n22-green.xml` |
| n23 | Reject changed final route/output/custom HTTP before registration | `n23-red.xml` / `n23-green.xml` |
| n24 | Interruption and close retain actual registration/finalizer ownership | `n24-red.xml` / `n24-green.xml` |
| n25 | Post-registration route check uses frozen authority despite shared model mutation | `n25-red.xml` / `n25-green.xml` |
| n26 | Preserve a smaller final native output ceiling | `n26-red.xml` / `n26-green.xml` |

Additional controls were already green: missing mandatory callback, malformed
or unsupported raw snapshots, concurrent single use, output/settings/media
mutation during registration, sanitized registration errors and no replay.
`primary-controls.xml` retains the initial fixture construction failure
(7 passed / 3 failed). `primary-controls-fixed.xml` records its corrected
plain projection (10 passed / 0 failed); the later Codex native fixture is
included in the final dedicated run. `primary-dedicated.xml` records
**37 passed, zero failures/skips/cancels, 11.47 s**; consumer typecheck exited
zero (`primary-typecheck.txt`). Earlier P2 and full Harness receipts remain
separately attributed to their original commits. No broad Harness rerun or
profile-heavy proof was used for this extension. Exact final commands, from
`packages/harness`:

```powershell
& 'C:/Renulus/scratch/ocf/tools/node-v26.4.0-win-x64/node.exe' --test --test-reporter=junit --test-reporter-destination=C:/Renulus/scratch/oc-h02-h08/providers/node-gateway/receipts/primary-dedicated.xml test/gateway-adapter.test.mjs
& 'C:/Renulus/scratch/ocf/tools/node-v26.4.0-win-x64/node.exe' node_modules/typescript/bin/tsc --noEmit > C:/Renulus/scratch/oc-h02-h08/providers/node-gateway/receipts/primary-typecheck.txt
```

Source and receipt hashes are recorded in `primary-handoff.json` beside those
receipts after the coherent local commit. The worker checked lane ownership and
the contract locally; no independent review is claimed. Parent `5500341e` is the
host application prerequisite, and its scoped context/model resolution must
reuse the same preparation before history provenance to close the saved-model
identity gap. Parent still owns current/role/permit checks, auxiliary denial,
final output and body proof, native terminal/publication authority and the full
connected route. No live provider call, credentials, installation or account/
package acceptance occurred. H03 and H02-H08 acceptance remain open.
