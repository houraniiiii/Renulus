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

## Recovered finalisation wave — October 5, 2026

This bounded follow-up starts from local `601a72cd`. The parent handoff identifies
integration `50aac06c` at `C:/Renulus-native-delivery/desktop-20261005/repo`;
the E: repo path is a junction. Runtime fix `81737363` corresponds to integrated
`da726ac1`; consumer fix `601a72cd` corresponds to integrated `15f284b9`.
The owned runtime/Learn/test files compare equal between the corresponding
commits. Preserve those commits; only the new follow-up commit needs integration.

Existing receipts were recovered and parsed, without repeating the same-source
subscription sweep: `regression.xml` has 180 passes, `overrides.xml` 3 passes,
`consumer-focused.xml` 47 passes, and `consumer-learn-final.xml` 46 passes.
`consumer-regression.xml` retains its 128 tests and one readiness-timeout failure;
the later corrected Learn receipt remains the qualifying evidence described above.

The owner's October 5 decision supersedes the earlier release plan: **the current
target is an unsigned Windows build validated on this PC**. Required delivery
evidence includes the bundled runtime under OS-only PATH, matching source/build/
installation hashes, normal shutdown/reopen, and actual required journeys and
recovery. Code signing and a separate clean PC/VM are optional future distribution
work, not current completion gates. Earlier observations above remain historical.

### New defects and bounded fixes

1. Closing the public Learn response at `started` or `delta` did not await
   `LearnService.answer` cleanup. Study stayed `running`; temporary runs stayed
   active, and a delta-stage provider run remained registered until deferred
   async-generator cleanup. Four synthetic reproductions failed. The response
   producer now wraps the inner iterator in `contextlib.aclosing`, using the
   existing interrupted-state, provider-close and retention logic.
2. Learn's renderer replaced every streaming error's `retryable` value with
   `true` and always offered Try again. Two mounted reproductions failed for
   non-retryable learning/model refusals. It now preserves explicit `false` and
   omits that retry action. Existing Connections access and the question remain
   available. Quota errors retain deliberate retry; an older event omitting
   retryability keeps the existing compatibility behavior. No automatic retry
   or subscription change is added.

Changed paths are `runtime/renulus/learn/api.py`,
`tests/learn/test_subscription_cancel.py`,
`apps/desktop/src/modules/learn/index.tsx`,
`apps/desktop/src/modules/learn/lifecycle.test.tsx`, and this report.
Impeccable context/hardening guidance informed the error-state refinement;
Flow's existing primitives, layout, CSS and visual tokens are preserved.
The absent `modules/connections/` directory and actual platform-owned
Connections page remain with the parent.

### Follow-up verification and receipts

Receipt root: this worktree's ignored
`.local/runtime/finalise-subscriptions/wave2/`. Public CPython 3.14 and Node
24.15.0 reused the supplied environments; the desktop dependency junction points
to the supplied public Node modules. No dependencies or launcher were changed.

| Receipt | Result and meaning |
| --- | --- |
| `repro-api.xml` / `.log` | Four expected failures before the Learn close fix, 28.04 seconds. |
| `repro-renderer.xml` / `.log` | Two expected recovery-policy failures, two passing compatibility/quota cases; seven unrelated lifecycle cases deselected. |
| `final-api.xml` / `.log` | **5 passed**, 9 deselected, 52.30 seconds: four public response-body close cases plus the affected public ASGI Stop check. Immediate cleanup, one Stop terminal, retained study input, no partial answer/evidence/job and no temporary fixture sentinel. |
| `final-renderer.xml` / `.log` | **40 passed** across lifecycle, discovery and memory disclosure, 22.89 seconds. Retained thread/question, no automatic retry, fresh idempotency key on deliberate retry, non-retryable recovery, completion/Stop and disclosure regression. |
| `typecheck.log` | TypeScript `--noEmit` exit 0. |

The new Python checks refuse remote sockets and use the real Hermes/SDK through
HTTPX MockTransport, with no lifespan, workers or helpers. Renderer checks mount
the actual Learn/transport components with controlled fetch/SSE. No live account,
private profile, credentials, external source import, model/OCR workload or native
acceptance was exercised. The unchanged memory producer/engine fences retain the
prior evidence in `study-answer-memory-evidence.md`; they were inspected, not
retested with another heavy workload. These results are application evidence.

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
$env:MEM0_TELEMETRY='false'
& 'C:/Users/karol/Documents/t3-workspaces/Renulus-wt-integration/.venv/Scripts/python.exe' -m pytest tests/learn/test_subscription_cancel.py -k 'closing_public_response_body or public_learn_stop' -q --basetemp .local/runtime/finalise-subscriptions/wave2/final-api --tb=short --junitxml .local/runtime/finalise-subscriptions/wave2/final-api.xml
# From apps/desktop, using the supplied dependency junction:
node node_modules/vitest/vitest.mjs run src/modules/learn/lifecycle.test.tsx src/modules/learn/discovery.test.tsx src/modules/learn/memory-disclosure.test.tsx --maxWorkers 1
node node_modules/typescript/bin/tsc --noEmit
```

### Parent-owned practice close prerequisite

An additional isolated probe found the same missing awaited inner-close boundary
in `runtime/renulus/assessment/generated_streaming.py::sse_events`, outside this
wave's lease. Its source blob `2245c91af625ea61a3fe4e333806d790ce5998f4` is identical
at local `601a72cd` and parent `50aac06c`. Closing the public response at `started`
leaves the volatile run `running` with its prompt; closing at `progress` also
leaves its provider run active immediately after close. This observes cleanup
being deferred, not a successful durable commit or an unbounded live request.
Both probes produced zero persistent practice sessions, zero learning evidence
and no sentinel in fixture files.
The same source blob was also confirmed unchanged at the parent's later
`c8c8f967` checkpoint during this lane's final read-only check.

Probe and receipts: `wave2/observe-practice-close.py`,
`wave2/observe-practice-close.json`, and `.log`, all ignored synthetic scratch.
No assessment source was edited. Parent/assessment owner should wrap
`generate(repo, run, replay)` in `contextlib.aclosing` inside `sse_events`, then
check immediate cleanup at both boundaries and the existing explicit Stop path.
This is a concrete code prerequisite for reliable practice response closure,
separate from the externally blocked live account checks.

### Minimal parent-only live API/native checklist

Use the matching installed unsigned build on this PC after integrating the owned
fixes and the practice close prerequisite. The parent reserves the serial native/
helper slot. Use the owner's deliberately entered Renulus connection; do not copy
another app's credentials or move account state to a test profile. Native actions
use the app's existing local-auth bridge; API equivalents below carry only product
payloads. Keep a fresh proof ID, synthetic questions and explicit idempotency keys.
Record source/build/installed hashes, timestamps, public run/thread/job/fact IDs,
selected model, terminal codes and helper states, without tokens or private bodies.
All API paths in the checklist use the `/api/v1` prefix, including the shortened
paths in the table.

| Check | Supported action | Required receipt |
| --- | --- | --- |
| Installed preflight | Launch the matching installed executable with OS-only PATH. Read `GET /api/v1/health`, `/connections`, `/runtime/status`, `/memory/status`, and synthetic-job metadata from `/memory/jobs`. Connections explicitly selects Codex; parent refreshes its catalogue only when needed. | Bundled runtime starts without developer tools; exact source/artifact/install binding; selected subscription and current account-available allowed models. A catalogue is not a generation pass. |
| Direct Explain | New study, Direct explanation. Example: `SYNTHETIC <proof-id>: Explain glomerular filtration selectivity for educational study in at most 100 words.` API: `POST /api/v1/learn/ask` with `question`, `scope:{kind:'study'}`, `teaching_style:'direct'`, `topic_id:null`, and a fresh `Idempotency-Key` header. API may set `model` to the explicitly available approved ID. | Ordered SSE and exactly one `completed`; canonical `GET /learn/threads/{thread_id}` has one completed assistant answer. Source labels reflect actual retrieved passages or lack of verification. Replay that same key returns the recorded Learn result without another Explain request. Background capture is separately accounted for. |
| Guided follow-up | In the same thread choose Guided teaching and ask a short synthetic dialysis-learning question. API adds the original `thread_id` and `teaching_style:'guided'` with a new key. | One focused teaching question/adaptation, one completed run, preserved thread and teaching style. Native composer text must match the entire intended synthetic input before submission. |
| Generated practice | Test → generated practice, one synthetic transplantation question. `POST /api/v1/assessment/practice/generate` body: `prompt`, `count:1`, `context:'study'`, `topic_id:null`, `idempotency_key:<fresh key>`. Read the returned session and commit one answer through `/assessment/practice/sessions/{session_id}/answer` with `item_id`, `option_ids` and a new body key. | One completed validated session, generated/unreviewed feedback and no key reveal before answer/help. Reviewed attempts/score aggregates remain unchanged; generated keys create no learning evidence or memory capture. Reusing the generation key replays the recorded outcome. |
| Stop and temporary retention | During a distinct synthetic Explain pending stream, press Stop or `POST /learn/runs/{run_id}/cancel`; repeat for practice using `/assessment/practice/runs/{run_id}/cancel`. Use marked temporary input for the Explain stop probe (`scope:{kind:'temporary-case'}`), or native Cases → Explain with a synthetic temporary handoff. End that temporary context afterward. | If Stop wins before commit: one `cancelled` terminal, provider run released, no partial persisted result or capture, and no temporary study thread. If completion won first, record `completed` honestly. Practice response closure must also release its run immediately. Inspect only the synthetic proof's app-owned persistence/exports; temporary text and derivatives must be absent. |
| Automatic learning capture | Allow the successful short ordinary-study answer's normal worker to run. Read `/memory/jobs`, `/memory/facts`, and `/memory/status`; Memory → Refresh and inspect the matching synthetic provenance. Optionally search the retained point through `POST /memory/search` with `query`, `scope:{kind:'study'}`, `limit:10`. | A **completed** job for `evidence_id='learn-answer:<run_id>'`, at least one `kind='learning-point'` fact with `sources[].source_key='evidence:learn-answer:<run_id>'`, and ready recall distinguish actual Mem0/FastEmbed capture from saved text, a queued job or topic-only study interest. No manual Add learning is a capture proof. Capture may make additional selected-subscription requests and use its quota; record this separately. |
| Recovery and reopen | On a real quota/auth/stream failure, retain the question and recorded thread; recover through Connections, then deliberately retry with a fresh key. For failed capture, use Memory → Retry pending jobs / `POST /memory/retry` only after recovery. Close normally, confirm the owned app/backend stop, reopen the matching installation and resume the proof thread/Memory records. | No invented partial answer, silent fallback, repeated automatic model request or duplicate capture. The completed answer survives capture failure. Capture retry preserves source/scope/deletion/version fences. Retry processes **all failed jobs** and may rebuild the index, so first bound it to the authorised synthetic job set and native/helper slot. Existing terminal results remain stable after reopen. |

`topic_id:null` avoids initiating automatic external topic discovery in this
minimal subscription checklist. Local Library retrieval still applies its
operation-specific permissions and actual ready revisions; no new source import
is needed. Successful ordinary Explain/guided answers, generated practice and
temporary handoffs remain distinct scopes. Preserve Hermes, Docling/HybridChunker,
FastEmbed, LanceDB and Mem0, SQLite authority and the exact allowlist:
Codex `gpt-6.1-sol`, `gpt-6-astra`, `gpt-6-luna`; Go `mimo-v2.6-pro`,
`deepseek-v4.1-flash`. The checklist permits no fallback or borrowed provider.

### Honest outstanding gates

The last recorded account evidence remains October 5: Codex exposed only Astra;
the synthetic image attempt failed with `subscription_limit`, and the text run
was `failed / subscription_limit` at **06:28:56 UTC**. This wave made no account
request and cannot assert whether that allowance has since recovered. A quota
error is an externally blocked condition, not a passing live generation/capture
check; it does not justify a retry loop or another provider. Go learning use is
still `unresolved` and generation remains paused in code. Sol/Luna availability
and successful live input remain account-specific, not inferred from their names.

Parent still owns the practice close prerequisite, matching unsigned native
manufacture/installation, OS-only PATH proof, shutdown/reopen/recovery, and the
successful live Explain/guided/generated-practice/Stop/automatic-capture receipts.
Mem0 can report `memory_capture_failed` after wrapping an underlying quota/auth
failure; inspect the exact synthetic job and public connection state, preserve
the saved answer and retry only deliberately after recovery. No live-provider,
installed-build, helper-backed capture or clinical-quality pass is claimed here.
