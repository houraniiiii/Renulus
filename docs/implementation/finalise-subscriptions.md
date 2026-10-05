# Subscriptions finalisation — October 5, 2026

Bounded lane: `build/finalise-subscriptions`,
`C:/rn-finalise-20261005/lanes/subscriptions`, GitHub issue #2.
Baseline: `9d26f1eedf31cd488b9aab5837a105ee152d9efa`.
First runtime fix: `8173736394923e578224ff38f5acb57d6c1291eb`, preserved unchanged.
The subsequent exclusively leased consumer fixes and their separate commit
are recorded in the final section below.
This report accompanies the locally committed runtime fix and focused tests;
the final handoff and issue comment identify its commit SHA for parent cherry-pick.
No push, merge or native/account acceptance is part of this lane.

## Concrete fix

Cancelling a long explanation while the provider event iterator was suspended
at `started` or compaction-start `progress` still dispatched automatic summary
generation when the iterator resumed. Both reproductions failed against the
baseline: actual Hermes context planning and the OpenAI SDK dispatched one
deliberately synthetic `/v1/responses` request after Stop. The request never
left HTTPX MockTransport. Baseline reproduction: **2 failed in 41.80 seconds**.

`ProviderManager.events` now checks its stop flag immediately after both event
yields, before planning/launching further compaction work. It emits one
`cancelled` terminal and releases the run through the existing cleanup path.
The tests also retry using the released run ID and confirm that the original
input and pre-existing synthetic profile bytes are preserved. No new adapter,
runtime, model, fallback, schema, credential format or dependency is introduced.

Owned changed files:

- `runtime/renulus/runtime/manager.py` — two stop guards.
- `tests/runtime/test_subscription_lifecycle.py` — synthetic SDK, catalogue,
  cancellation, recovery, producer and capture-boundary checks.
- `docs/implementation/finalise-subscriptions.md` — this handoff.

## Observed checks

All new catalogue fixtures expose **only `gpt-6-astra`**. They do not represent
a live account. No new check enables Go learning eligibility. Existing regression
tests which simulate hypothetical Go approval remain distinctly synthetic;
the unchanged default eligibility checks still block its learning routes.

| Check | Meaningful outcome |
| --- | --- |
| Stop at the two public event boundaries | No summary/model request after Stop; one ordered cancellation terminal; original input/profile bytes preserved; run ID available for explicit retry. |
| Pending SDK read, explicit Stop or consumer-task cancellation | HTTP response body closes, pending read exits, active-run map empties; cancelled output does not establish text-input capability or live-provider verification. |
| Sol, Luna and an unapproved override with Astra-only catalogue | Requested unavailable/unapproved models are rejected before transport; selected subscription stays Codex; availability remains Astra-only. |
| Actual SDK → local ASGI Learn → SQLite, auth/quota/truncated stream | Input and failed run survive restart. Explicit refresh/retry stays on Astra/Codex and completes in the original thread. No partial answer becomes capture evidence. Synthetic CKD, transplantation and dialysis topics exercise the same seam. |
| Completed ordinary study → memory eligibility/outbox | One immutable answer reference resolves to the exact completed assistant answer, excludes the user's prompt and queues one deduplicated capture job. Memory engine and embedding helper remain uninitialised. This proves eligible capture input, not Mem0 extraction/index quality. |
| Actual SDK → generated practice in study/temporary/unclassified scope | Generated scoring/reveal stays separate from reviewed assessment; unreviewed keys produce no learning evidence or memory jobs. Temporary/unclassified prompts and keys are absent from app-owned fixture files. |

The combined regression passed **180 checks in 286.00 seconds**, including
the first ten new lifecycle/producer checks. Its one warning is the pre-existing
Starlette/httpx TestClient deprecation; no dependencies were rebuilt or changed.
The three additional catalogue-override checks passed separately in
**5.74 seconds** (ten unrelated owned checks deselected):
`pytest tests/runtime/test_subscription_lifecycle.py -k astra_only_catalogue_rejects -q`.
Together these final runs passed **183 distinct checks**, including all
13 new checks. The full command below now includes the three added overrides.
`git diff --check` passes. Checks use the existing public CPython 3.14 environment
and isolated profiles under this worktree's ignored `.local/runtime/`.
External sockets are denied in all new checks. No helper/model/native workload,
credentials, real learning profile, source collection or live provider is used.

Reproduction command (create the parent basetemp folder once in a fresh checkout):

```powershell
New-Item -ItemType Directory -Path .local/runtime/finalise-subscriptions -Force | Out-Null
$env:PYTHONDONTWRITEBYTECODE='1'
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
& 'C:/Users/karol/Documents/t3-workspaces/Renulus-wt-integration/.venv/Scripts/python.exe' -m pytest tests/runtime/test_subscription_lifecycle.py tests/runtime/test_provider.py tests/runtime/test_provider_acceptance.py tests/runtime/test_auth_api.py tests/runtime/test_codex_stream.py tests/runtime/test_images_context.py tests/runtime/test_go_eligibility.py tests/learn tests/assessment/test_generated.py tests/memory/test_repository.py -q --basetemp .local/runtime/finalise-subscriptions/regression --tb=short --junitxml .local/runtime/finalise-subscriptions/regression.xml
```

## Consumer gaps observed at the first handoff

These observations were sent to issue #2 via `gh --body-file`. The first
commit did not edit Learn, assessment, shared API/contract, migration or renderer
source. The parent subsequently leased the two consumer files exclusively to
this lane; their fixes are documented below.

1. **Learn's cancellation presenter:** an actual SDK pending read cancelled
   through `LearnService.cancel` closes correctly, sets both control/canonical
   states to `cancelled`, empties the provider and Learn active-run maps and
   creates zero memory jobs. Its consumer nevertheless receives
   `CancelledError` after only `started`, `sources`, `delta`; it receives no
   terminal SSE event. `runtime/renulus/learn/service.py` rethrows every provider
   cancellation. The parent must distinguish deliberate local cancellation from
   an externally cancelled consumer task and emit one terminal for the former.
   Silently ending the runtime text iterator would risk committing partial
   output after account disconnection and is not a safe fix at this boundary.
2. **Generated-practice recovery messages:** actual
   `runtime/renulus/assessment/generated_streaming.py::safe_error` maps
   `subscription_limit`, `capabilities_unverified`, `account_model_unsupported`,
   `provider_stream_incomplete` and `connection_changed` to
   `practice_generation_failed`. The parent/assessment owner needs to preserve
   known public provider codes/messages while redacting unknown errors.
3. **Connections ownership:** the assigned `apps/desktop/src/modules/connections/`
   directory is absent. The existing page is
   `apps/desktop/src/platform/ConnectionsPage.tsx`, outside this lane's assigned
   write scope. Any related presenter edits remain with the parent.

The ignored `observe-boundaries.py` receipt in this lane deliberately builds
an isolated synthetic profile and uses `PausedSSE`, `producer_app` and
`seed_astra` from the committed focused tests to exercise the first two gaps.
It is neither a production transport nor a live acceptance check.

## Remaining acceptance limits

The [owner's live connection record](live-connections-2026-10-05.md) remains
the dated evidence: intentional sign-in connected the accounts; Codex exposed
Astra only; image and text attempts reached `subscription_limit`. Successful
live generation, cancellation presentation, generated practice, image
interpretation and automatic end-to-end learning capture remain unproved.
This lane performs none of those live checks and does not claim installed
Windows or full end-to-end acceptance from its synthetic fixtures. Later parent
receipts can establish live acceptance separately from this lane's evidence.

The exact five-model allowlist, Go learning pause, source-operation boundaries,
Hermes foundation, SQLite record authority and selected document/embedding/memory
stack remain unchanged. The [prior adapter evidence](provider-acceptance.md)
and [Go eligibility evidence](go-eligibility.md) retain their dated primary-source
references; this lane did not re-research or relax those policies. The parent
continues to own ConnectionsPage, integration, native/live checks and final acceptance.

## Exclusively leased consumer extension — October 5, 2026

After the central Git checkout relocation/repair, the parent authorised a
second bounded commit based on `8173736394923e578224ff38f5acb57d6c1291eb`.
The first commit is not amended. This extension changes only:

- `runtime/renulus/learn/service.py`
- `runtime/renulus/assessment/generated_streaming.py`
- `tests/learn/test_subscription_cancel.py`
- `tests/assessment/test_provider_errors.py`
- this report

**Learn:** an explicit local Stop interrupts the provider read while the consumer
task remains alive. The handler checks the local cancel flag and the consumer
task's cancellation count, emits exactly one ordered `cancelled` terminal for
that case, and preserves the input without an assistant answer or capture
evidence. Actual consumer-task cancellation still propagates `CancelledError`,
including when it races an explicit Stop. An interrupted consumer does not emit
a synthetic terminal to a departed reader. Conditional state updates preserve
an already completed/cancelled canonical result.

The initial `started` event now sits inside the cleanup boundary. Closing a
Learn iterator there or after a delta closes its provider iterator when
supported, releases both active-run maps, and marks an unfinished persisted run
`interrupted`. A late provider exception after the local cancel flag is set
cannot replace cancellation with an error or commit a partial answer. Ordinary
iterator implementations without `aclose` keep their existing contract.

**Generated practice:** fourteen previously discarded public runtime codes now
retain their machine identity and retryability. They include quota, catalogue
verification, account/model rejection, connection change, truncated/failed
streams, protocol refusal, image gating and context/compaction/tool refusal.
Messages come from the explicit application-owned whitelist; no provider
message/body is forwarded even when it claims a recognised code. Unknown
exceptions/codes remain redacted, and the existing separate storage-failure
message remains intact. The public error envelope is unchanged.

The first reproduction run exposed the code/terminal/iterator problems; its
initial study stream also hit a five-second cold-SDK fixture deadline, which
was increased to fifteen seconds before final verification. No product timeout,
SDK retry, model route or fallback was relaxed.

Focused verification: **47 passed in 45.09 seconds**, using the actual Hermes
wire conversion, OpenAI SDK, HTTPX MockTransport, local ASGI routes and canonical
SQLite. The explicit Stop endpoint now produces one terminal SSE event. Study
and temporary-case cancellation, consumer cancellation, simultaneous Stop/task
cancellation, first-event/delta closure and late errors retain no partial answer
or capture job. Six practice SDK failure/recovery scenarios preserve actionable
errors, publish no failed practice, and require an explicit fresh request for
retry; successful synthetic practice stays generated/unreviewed on Astra.
Unknown and deliberately malicious synthetic error messages remain absent from
the response.

The combined Learn/assessment regression recorded **127 passed and one failed
in 246.52 seconds**. Its only failure was a fifteen-second test readiness
timeout waiting for the synthetic SDK pending read in the first study
cancellation fixture; no product-state assertion failed. The fixture now
disables optional literature retrieval and imports the public SDK responses
resource before its readiness timer. The corrected full Learn suite passed
**46 checks in 155.14 seconds**, including the previously timed-out case.
All **82 assessment checks** passed in the combined run; the fixture correction
does not change assessment code or tests. Together these receipts cover
**128 distinct passing Learn/assessment checks** without claiming that the
combined invocation itself was clean. Both regression runs emitted only the
existing Starlette/httpx TestClient deprecation warning.

Receipts are this worktree's ignored
`.local/runtime/finalise-subscriptions/consumer-focused.xml`,
`.local/runtime/finalise-subscriptions/consumer-regression.xml` and
`.local/runtime/finalise-subscriptions/consumer-learn-final.xml`.

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
& 'C:/Users/karol/Documents/t3-workspaces/Renulus-wt-integration/.venv/Scripts/python.exe' -m pytest tests/learn tests/assessment -q --basetemp .local/runtime/finalise-subscriptions/consumer-regression --tb=short --junitxml .local/runtime/finalise-subscriptions/consumer-regression.xml
& 'C:/Users/karol/Documents/t3-workspaces/Renulus-wt-integration/.venv/Scripts/python.exe' -m pytest tests/learn -q --basetemp .local/runtime/finalise-subscriptions/consumer-learn-final --tb=short --junitxml .local/runtime/finalise-subscriptions/consumer-learn-final.xml
```

All new checks block non-loopback sockets, use synthetic grants/catalogues and
run without helper/native tests, model inference, live providers, account or
learning-profile reads. No schema/contract or other module source changed.
This resolves the two consumer gaps from the first handoff at application-test
level; live app-owned generation, cancellation UI and memory acceptance remain
with the parent. The second commit's exact SHA is returned in the final handoff
and the concise issue #2 evidence comment.
