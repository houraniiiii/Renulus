# OpenCode Go learning eligibility and client identity

Reviewed on **2026-10-05 UTC**, in isolated branch `build/go-eligibility`,
based on `14bb101f6308b2f1eae681ac7b5124fddd716bc3`. This is a scoped
follow-up to [provider acceptance](provider-acceptance.md) and
[Connections UX](connections-auth-evidence.md).

**Release decision: Go learning eligibility is unresolved, so Renulus blocks
Go generation.** A saved key or an available approved model is account evidence
only. Neither enables educational requests. This decision is implemented in
the runtime policy and the existing Connections page; it has no environment,
request, model, credential or user setting override.

## Primary source and interpretation

The current official [Go documentation](https://opencode.ai/docs/go/) describes
OpenCode and other coding agents producing similar requests. Its client
requirements include typical coding-agent traffic, an app-specific User-Agent,
and a stable `x-opencode-session` per conversation for routing and caching.
It documents both selected Go model IDs and their chat-completions endpoint.

The official repository source was checked independently through GitHub:
[immutable go.mdx](https://github.com/anomalyco/opencode/blob/083ed266e058dc3d2d1b377ff5540859d79de110/packages/web/src/content/docs/go.mdx).
The latest commit affecting this file observed during review was
`083ed266e058dc3d2d1b377ff5540859d79de110`, committed
**2026-09-28 at 11:34:04 UTC**. The isolated UTF-8/LF capture has SHA-256
`9d65189de9517ff518a76c462f247b286cc21e7cabb0fa30aa2f08c832520c1d`.
The source lookup used `gh api` for the official repository contents and
`commits?path=packages/web/src/content/docs/go.mdx&per_page=1`.

The documentation does not explicitly ban every non-coding use, but it does
not establish eligibility for Renulus educational traffic. Renulus therefore
does not assume permission. The documented validation of newer Hermes builds
does not establish plan eligibility or acceptance of this controlled adapter.
No vendor/account message was sent, and no actual subscription request was made.

The owner-selected model IDs remain exactly:

| Connection | Allowed IDs | Release learning policy |
| --- | --- | --- |
| Codex | `gpt-6.1-sol`, `gpt-6-astra`, `gpt-6-luna` | Existing app-approved route; account availability still requires verification |
| OpenCode Go | `mimo-v2.6-pro`, `deepseek-v4.1-flash` | Unresolved; generation blocked |

## Implemented boundary

`GET /api/v1/connections` and runtime status add `learning_use` to each existing
connection row. For Go it reports `status: unresolved`,
`generation_allowed: false`, `code: learning_use_unverified`, a safe message,
the official policy URL and the review date. The existing account status and
model catalogue remain separate. Codex reports `app_approved`, which describes
the app route rather than a live account or model proof.

Selecting Go, connecting with `select: true`, manager generation/compaction,
and direct Hermes generation all fail before token refresh, auxiliary work or
provider I/O. The error is `learning_use_unverified`, non-retryable, with
HTTP 403 where returned as a JSON API error. A stream returns its existing
error event envelope. The gate applies to every context scope and purpose;
even a request labelled coding cannot bypass the educational product policy.

Legacy saved Go selection and protected records are preserved. The app does
not switch to Codex, clear another selected provider or change the allowlist.
An explicitly entered Go key can still check and save account metadata with
`select: false`; refresh and disconnect remain available. Neither metadata
operation sends a learning prompt. Learn retains a failed durable study input
and failed-run state, using the existing storage behavior. Temporary runtime
requests leave no new files or persistent Hermes state.

Connections displays **Learning requests paused** alongside account status.
It hides Use Go unless the release capability explicitly says confirmed and
allowed; a server omitting the capability also leaves Go paused. A legacy
selected Go connection is visibly paused. Key saving, policy/account links,
model checks and disconnection reuse the existing Flow primitives. Codex sign-in
and explicit selection remain independent.

## Truthful transport identity

Metadata and approved transport requests identify the app as
`User-Agent: Renulus/0.1.0`. They do not send an OpenCode client version or claim
to be a coding agent. The controlled adapter reuses the original
`agent.opencode_affinity.opencode_session_headers` helper in the attributed
Hermes baseline `af90026aa09949579bd423d24def3d38f743cde0`; upstream files,
licence and patch provenance are unchanged.

For a hypothetical later approved Go route, durable conversations derive an
opaque UUIDv5 from the existing profile host identity, scope kind and entity ID.
The header remains stable across turns and app restart, differs across
conversations, and contains no raw entity, question or case text. Temporary
and unclassified requests receive a fresh in-memory UUID per run, regardless
of any supplied entity ID, with no new state file. Metadata checks have their
own one-shot IDs. Compaction inherits its parent request session through a
context-local value; summary and primary traffic share that header. An upstream
ambient identity attempting to replace the app identity is rejected.

Go generation remains blocked in production despite this header implementation.
Protocol tests use a named **test-only simulated future eligibility** fixture,
synthetic credentials and HTTPX MockTransport. The fixture does not alter any
model ID or authorize a live request. Production has no fake answer path.

## Reproduction and acceptance limits

Run in this checkout with the integration CPython 3.14 environment,
`PYTHONDONTWRITEBYTECODE=1`, `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`:

```text
python -m pytest tests/runtime/test_go_eligibility.py tests/runtime/test_provider.py tests/runtime/test_auth_api.py tests/runtime/test_codex_stream.py tests/runtime/test_images_context.py tests/runtime/test_provider_acceptance.py tests/learn -q --basetemp .local/runtime/go-eligibility/final --tb=short
```

The default-gate tests prohibit external sockets while allowing the loopback
required by Windows asyncio. They cover every scope and purpose, metadata
checks, direct transport denial, selected-provider preservation, temporary
file equality, the real local ASGI error contract and failed Learn retention.
Hypothetical transport checks use the actual SDK and pinned Hermes code,
including restart-stable opaque session IDs, compaction affinity and rejection
of a changed ambient identity.

Renderer reproduction from `apps/desktop`:

```text
node node_modules/vitest/vitest.mjs run src/platform/ConnectionsPage.test.tsx
node node_modules/typescript/bin/tsc --noEmit
```

**135 runtime/auth/provider/context/Learn checks passed** in 111.69 seconds
on CPython 3.14, with one existing Starlette/httpx deprecation warning.
**45 mounted Connections journeys passed** and the TypeScript check passed.
These cover absent/unresolved/unsupported/denied eligibility, connected account
status, legacy selected Go, explicit hypothetical selection, cleared keys,
safe public links, and existing Codex start/retry/cancel/expiry recovery.
`git diff --check` passed. Current integration `23f11902` had no changes to
these owned existing files since the lane base when the handoff was checked.

No actual account login, credential exchange, live catalogue, model generation,
image interpretation, native installer or subscription acceptance is claimed.
Real Go educational eligibility is still a release blocker for that route;
enabling it requires primary-provider evidence and a reviewed code decision,
followed by separately authorized user-owned account/model acceptance.
Tickets #2/#5 remain open for the unproved live acceptance.

Integration needs one scoped cherry-pick and a refreshed runtime/renderer
package snapshot. There are no new dependencies, schema migrations, module
registrations, auth protocol changes or shared platform edits. The additive
`learning_use` field requires no change to existing generation interfaces.

## Integrated cross-module regression, 2026-10-05 UTC

The follow-up ran from fresh isolated branch `build/runtime-cross-module`,
base **314c0e6e308160d5df0557edc44a4a3b900f64d4**, the integrated Go guard.
The tested runtime/modules and existing test files were unchanged through
parent **6abd3ae9b0d0eebe7ba4468290312f3c4286d7f9** when compared at
**01:09 UTC**. No main, integration, shared consumer, packaging or renderer
files were edited by this check.

The affected default suite passed **295 checks in 207.53 seconds**, with one
existing Starlette/httpx deprecation warning. It covers foundation,
Cases/Learn handoff, reviewed/generated assessment, Cases attachments and
retention, Memory repositories/API/workers, Learn retention/discovery and the
runtime/auth/context/provenance boundaries. Existing synthetic Go protocol
tests retain their explicitly named future-eligibility fixture; the new
integrated Go tests do not enable that fixture.

```text
python -m pytest tests/integration/test_foundation.py tests/integration/test_case_learn_handoff.py tests/assessment tests/cases tests/memory tests/learn tests/runtime/test_go_eligibility.py tests/runtime/test_provider.py tests/runtime/test_auth_api.py tests/runtime/test_codex_stream.py tests/runtime/test_images_context.py tests/runtime/test_provider_acceptance.py tests/runtime/test_protected_helpers.py tests/runtime/test_hermes_provenance.py -q --ignore=tests/cases/test_offline_attachment_flow.py --ignore=tests/memory/test_mem0_real.py --basetemp .local/runtime/cross-module/pytest --tb=short
```

The new `tests/runtime/test_cross_module_generation.py` passed **5 producer
checks**, with **1 explicit expected failure** for pending shared consumer
presentation, in 22.86 seconds. The real app factory, module repositories,
SQLite, runtime ProviderManager, pinned Hermes conversion and actual SDK are
used with HTTPX MockTransport. External sockets are prohibited, allowing
Windows asyncio loopback only.

- Controlled Codex completes real Cases discussion, Cases-to-Learn Explain
  and Cases-to-generated-practice handoffs with the exact selected Sol ID.
  Those case-derived flows remain temporary; the marker is absent from files,
  study threads, saved cases, generated persistent sessions and memory jobs.
- Legacy selected Go denies the same flows with zero provider requests, no
  subscription switch, no successful terminal and no temporary persistence.
- The actual registered Mem0 LLM bridge consumes the controlled Codex route
  and propagates the Go non-retryable gate before model I/O.
- Actual Mem0 OSS, the pinned Hermes memory backend, local Qdrant and the
  SQLite outbox leave Go capture failed with no generated facts and no
  provider calls. Only the vector delegate is synthetic; no FastEmbed model
  or helper asset is loaded. This is route/outbox evidence, not embedding
  semantic or model inference proof. Mem0 can wrap the safe gate error, so
  the existing outbox may report the generic memory_capture_failed code.

```text
python -m pytest tests/runtime/test_cross_module_generation.py -q -rx --basetemp .local/runtime/cy --junitxml .local/runtime/cross-module/producer.xml --tb=short
```

Use the offline/bytecode variables above, plus `MEM0_TELEMETRY=false`,
`OMP_NUM_THREADS=2`, `MKL_NUM_THREADS=2`; do not set asset/source override
variables for these checks. A short owned native-test profile avoids pytest
function-name directories pushing Qdrant past Windows path-length limits.
The actual local Qdrant check emits its expected payload-index warning.

**Pending shared acceptance is not counted as a pass.** Real local route probes
found four consumer presentation gaps despite the working runtime gate:

| Consumer | Observed result with blocked legacy Go | Required shared-owner change |
| --- | --- | --- |
| Generated practice capability | available:true based only on account/catalogue | Honor learning_use and explain paused eligibility |
| Cases discussion error | case_discussion_failed, retryable:true | Preserve controlled learning_use_unverified and non-retryable status in safe mapping |
| Generated practice error | practice_generation_failed, retryable:true | Preserve the same controlled gate, including capability preflight |
| Learn error | learning_use_unverified, retryable:true | Preserve ApiError.retryable instead of hardcoding true |

The requests are recorded on parent issue #1 in
[comment5986334331](https://github.com/houraniiiii/Renulus/issues/1#issuecomment-5986334331)
and [comment5986373346](https://github.com/houraniiiii/Renulus/issues/1#issuecomment-5986373346).
The owned consumer acceptance check first proves zero egress/no temporary
marker persistence, then explicitly reports the remaining gaps as expected
failure. It becomes a pass when all four shared behaviors are corrected; it
does not silently accept their current values. No production runtime
regression or need to weaken/rewrite the release gate was found.

No backup/portable/native lease or large engine benchmark was repeated.
There was no live account request, credential acquisition, asset download,
model inference or native installer claim. Parent should apply its consumer
fix, rerun the new focused file and refresh the final runtime/renderer package
capture; live-provider acceptance remains separate.
