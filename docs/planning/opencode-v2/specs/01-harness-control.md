# S1 — Configurable OpenCode execution harness

Status: reviewed specification. H01 has local foundation acceptance in the [implementation handoff](../../../implementation/OPENCODE_FOUNDATIONS_HANDOFF.md). H02 and the remaining configuration, routing, extension and release slices stay planned; their acceptance is not completed by the host foundation.

## Problem Statement

Renulus has working learning and data modules, but its generation interface emits text and rejects tool calls. Doctors and future clients need a coherent harness that can retrieve evidence, use tools, delegate bounded work and survive interruption. Model and extension controls must apply to all background work as reliably as to an ordinary answer.

## Solution

Embed the selected OpenCode v2 runtime behind one small Renulus harness interface. Reuse its execution, sessions, children and events. Keep Renulus's domain modules and current selected subscriptions. Offer inspectable, versioned configuration for purposes, models, instructions, skills, plugins and MCP connections. Changes have a validated activation result and current revocations apply immediately.

## User Stories

1. As a doctor, I want a cited answer that can retrieve evidence, so that the response uses my eligible material.
2. As a headless client, I want to submit and observe the same learning operation as the desktop, so that capabilities are independent of presentation.
3. As a doctor, I want to reopen a saved operation, so that I can see its actual progress and outcome.
4. As a doctor, I want Stop to cancel owned work and report settlement, so that late results are not mistaken for active work.
5. As a doctor, I want navigation and disconnection to have defined behavior, so that changing panes does not silently lose or duplicate work.
6. As a doctor, I want to choose my subscription and exact model, so that requests use my intended access.
7. As an administrator of my local profile, I want purpose-specific model settings, so that images, summaries and generation can be tuned independently.
8. As a doctor, I want unsupported required input reported explicitly, so that an image is not silently discarded.
9. As a doctor, I want authentication, quota and model rejections to remain visible, so that an error does not trigger an unexpected provider switch.
10. As a profile owner, I want bounded retry and fallback policies, so that additional attempts are intentional and observable.
11. As a doctor, I want child work to inherit narrower access and budgets, so that delegation respects the original scope.
12. As a profile owner, I want to inspect the effective configuration of a run, so that I can explain why a route or tool was selected.
13. As a profile owner, I want a failed configuration update to preserve a healthy version, so that adjustment does not leave a partly configured harness.
14. As a profile owner, I want a revoked grant to stop pending and resumed effects, so that old approvals cannot bypass current choices.
15. As a doctor, I want reviewed skills and instructions to load consistently, so that task guidance survives long conversations.
16. As a profile owner, I want explicit plugin activation, so that arbitrary files do not install executable extensions.
17. As a profile owner, I want to connect, disable and remove credentials for an MCP server separately, so that each action has a clear effect.
18. As a future local-inference user, I want an optional vLLM or Ollama connection, so that it uses the same route and capability controls.
19. As an ordinary doctor, I want the bundled harness to work without installing developer tools or a model server, so that optional integrations stay optional.
20. As a maintainer, I want a pinned upstream cohort and a small patch ledger, so that upgrades remain reviewable.

## Implementation Decisions

- The Harness module owns admission, observation, permission/resume decisions and cancellation semantics. The OpenCode implementation owns the loop, transcript, inbox/claims, tool lifecycle, children and recovery. Domain operations that do not need inference remain directly callable.
- One managed local host owns each persistent runtime store. A separate existing Python process owns domain engines and records. Readiness includes policy and domain availability, not merely a listening endpoint. Host shutdown waits for bounded settlement and prevents competing owners.
- H01 establishes a prepared paired-store manifest, without asserting either store is validated. H02 validates the actual stores and activates the initial selection before its first saved conversation mapping, including safe reopen and interrupted-activation reconciliation. H06 consumes this selection for legacy migration; H18 later proves complete paired backup/restore. Parsing the manifest does not validate the underlying stores.
- Reuse current conversation commands, run receipts and domain policy/context epochs. A separate in-memory runtime graph owns temporary sessions, children and volatile tool outputs; a selected instance in the persistent host is insufficient. Keep retained event payloads disabled initially and redact diagnostic attributes.
- The proof uses one source-built OpenCode dependency cohort. Published SDK 2.0.26 is not interchangeable with the newer inspected source. Pin build/runtime/native/WASM artifacts and licence provenance before acceptance. A successful source inspection is not packaged acceptance.
- One Configuration module stores immutable versions and the active pointer. Stage, validate, construct, health-check and activate a complete candidate. Preserve a known healthy version on failure. A session binds a version; current revocations narrow it. Credentials remain protected references outside session metadata.
- Candidate construction keeps generation, recovery, package acquisition and external MCP startup closed; verify the final effective registry after all transforms. It must not create a second writer to the live store. Reconcile crashes across readiness, active-pointer commitment and admission.
- Prefer restart-based activation behind admission/quiescence barriers initially. Preserve the current connection/catalog owner. Expose requested/effective/failed versions, and retain an active run's version until deliberate cancellation/migration. Releasing delayed recovery must not clear a fresh child's claim; prove the full sweep under quiescence before enabling selective deferral.
- Every model call obtains trusted purpose, scope, connection/model/endpoint/protocol identity, capability evidence and a bounded attempt allowance. Enforce these at actual dispatch, including primary, child, title, generation, summary repair, native compaction, transport fallback and recovery. Required policy failure causes zero dispatch.
- One policy is enforced at multiple transport seams: stateless plugin generation, native and managed AI-SDK calls, final HTTP requests, WebSocket handshake and reused-channel sends. Unadmitted/custom bypass paths remain disabled. A gate that prevents network calls but terminalizes a recovery claim is not a durable pause.
- Initial generative roles inherit the selected allowed model. Specialized choices need recorded evaluation; no ranking is inferred from model names. Deterministic titles and numerical assessment results remain usable without inference.
- Automatic follows existing allowlist order filtered by catalogue membership, then the first allowed ID; catalogue membership is a set, not a ranking. Disabled roles stay disabled before override resolution. Proposed defaults are twelve shared dispatch permits for a foreground/multi-stage operation, one for a standalone extraction/summary/narrative/daily-bundle/digest, zero for titles, child depth one/concurrency two, and a 4,096-token output allowance narrowed by route caps. Preserve the existing generation batch counter as an additional ceiling. These adjustable defaults require domain-fixture validation; they are not performance or quality claims.
- A standalone one-permit request must fit before dispatch or fail visibly; implicit pre-compaction cannot add a free request. Permit exhaustion preserves useful checkpoints and requires an explicit permitted continuation.
- A model continuation after a tool is a new step, not a retry. Each step is sent once initially; all steps/children/auxiliary requests debit the same parent allowance. Zero automatic retry/substitution is the default. Final assembled input, enforced output and combined-window checks cover every request kind, including hooks that remove an output limit.
- Resolve authorised operation override, then role override, parent and selected root. Preserve existing producer purposes and bounded workflow totals. Invalid overrides fail visibly. Each outbound attempt consumes a durable allowance; connection authentication failure invalidates access and observations even while a protected credential still exists.
- Capability records separate documented support, observed success/rejection and unknown status, and bind them to deployment and credential revisions. Catalog presence is not tool/vision/context proof. No incidental account probes or silent input substitution are introduced.
- Initial defaults preserve visible account/input rejection and no silent subscription switch. Configurable retries, repairs and substitutions declare qualifying errors, limits and attempt records. An uncertain post-dispatch timeout or restart does not automatically replay generation.
- Parent-to-child grants are intersected at execution. Bound depth, concurrency, requests, output and tool budgets. Permission approval is revalidated immediately before an effect, including an approval that waited while policy changed.
- Use native registration for internal domain tools; reuse MCP for selected external integrations. Tools receive host-derived scope/revision/cancellation envelopes. Keep Code Mode and generic coding tools disabled unless separately adopted and tested.
- Use versioned, authenticated owned-process IPC with bounded multiplexed requests and cancellation. Never hold canonical write transactions across generation or synchronously re-enter a host waiting on the same domain tool. Memory extraction begins from committed eligible publication as a separately admitted purpose operation. Test process death, queue pressure and shutdown in both directions.
- Bind frames to profile/store and process generation, operation/attempt and request identity; reject old-generation replies. Reserve control capacity for cancellation/revocation/settlement and reject overload before admission. The receive loop remains available while handlers await work; observation timeout never grants redispatch.
- Distinguish rejected-before-admission, accepted/pending, committed-reference, cancelled/settled and uncertain-after-disconnect. Command replies cannot inherit observation's drop-oldest behavior. Prohibit every cross-process wait inside canonical transactions and conversation/case/recovery physical locks; callbacks inside commits validate locally only. Close admission with a logical lease, drain remote work, then acquire engine guards. The drain attempt is bounded; ownership release requires actual settlement or remains blocked/uncertain.
- Instructions and skills carry versioned content and precedence. Retrieved text and model output cannot alter executable configuration or grant authority. Plugins are explicitly trusted code; manifests are not a sandbox. Disable ambient discovery and package acquisition in ordinary execution.
- Mandatory product/typed-operation constraints precede the explicit user request, which precedes optional role/skill guidance. Pin that guidance by content, reapply current mandatory revocations and require explicit migration for ordinary edits. A file-path cache does not establish content-version pinning.
- MCP connection identity includes endpoint and capability/schema identity. Disable blocks new access and settles owned work where possible; credential removal is separate. Uncertain remote effects remain visible and are not blindly repeated.
- Disable generic execute as well as MCP Code Mode initially. Recheck internal reconnect retries and adopted direct dispatch paths. Revocation is ordered against durable effect admission; it cannot undo an already admitted remote effect.
- Future optional provider descriptors reuse this control path. vLLM/Ollama compatibility is checked for the deployed model, chat template, modality, tools, structured output and context settings. This does not require the owner or doctors to host inference.
- Prefer public plugin interfaces, then supported host replacements. A core patch requires a demonstrated missing seam, an isolated test, upstream provenance and a removal condition. Replacing the loop, persistence machinery or child coordination triggers architectural reassessment.

## Testing Decisions

- Test external behavior through the public Harness/domain interface, using the same commands and observations as headless and desktop clients. Use existing cancellation, scoped runtime and cross-module tests as prior art.
- Supply a counting synthetic model transport at the dispatch seam. Exercise every call kind, forbidden child override, failed/missing/reloaded policy, incompatible input, changed endpoint, stale approval and recovery. Assert zero dispatch on denial and exact attempt counts otherwise.
- Test a complete tool round trip, foreground/background child outcomes, parent cancellation, lost observation and reconnect. Verify one terminal outcome and explicit cancellation settlement.
- Use hostile synthetic configuration directories and inert plugin/MCP fixtures to test discovery, activation failure, capability changes, disable and credentials removal. Do not use personal OpenCode state or real credentials.
- Treat native packaging, actual account authentication, model tool protocols and real performance as separately evidenced acceptance. Synthetic inference cannot establish them. Preserve the existing post-401 capability-status test failure until resolved.

## Out of Scope

Implementing the remaining planned harness slices in the initial H01/H24 batch; replacing approved data engines; a hosted Renulus service; mandatory local inference; automatic provider purchases; arbitrary untrusted code containment; adopting OpenCode's application UI; or claiming persistent Windows terminal support.

## Further Notes

The [integration plan](../../OPENCODE_V2_INTEGRATION_PLAN.md) carries the source/build candidates, current-work mapping and conditional patch ledger. Primary references and bounded checks are in [artifact/host evidence](../../../research/2026-10-10-opencode-integration/w1-03-artifact-host.md), [extension evidence](../../../research/2026-10-10-opencode-integration/w1-04-extensions.md) and [routing evidence](../../../research/2026-10-10-opencode-integration/w1-05-model-routing.md). The highest behavior test seam and ticket breakdown await the requested skill review before tracker publication.
