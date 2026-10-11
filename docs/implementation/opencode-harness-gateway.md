# Python-owned final subscription HTTP gateway

2026-10-11. Providers lane, branch `codex/oc-harness-gateway`, assigned checkout
`C:/Users/karol/.codex/worktrees/oc-providers/repo`. Base
`9a1893eb7ddb0bc7aa0c492ee375e83a285d82fd` already contains provider preparation
`07da2a3e0d6c7b6cec77212fe1d82bb61322d74f`. This change owns only
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

From the assigned checkout, managed Python ran:

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

The final owned suite passed **88 cases, zero skipped**, in 27.01 seconds. This
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

This checkout does not assemble the parent's later `7646fb5a` continuation or
the actual Library LearningOwner composition. Parent-owned Services/host/IPC must bind
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
