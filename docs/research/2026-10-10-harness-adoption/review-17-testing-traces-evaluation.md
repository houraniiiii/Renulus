**Review 17 — Host events, tracing and deterministic acceptance**

October 10, 2026. Source inspection only; no tests, inference or application launches. Baselines: Renulus `528025ff`; bundled Hermes `af90026a`, inspected upstream `dce1e9b3`; Pi **1.1.0** `abe508e1`; OpenCode **v2 source 2.0.26** `55dde881`. Links pin full commits; ranges are raw-file line numbers. Existing notes supplied leads, not verification.

**Conclusion (judgment):** Prefer OpenCode v2 on this assigned axis for an extensible harness serving multiple clients: its event schemas and ordered aggregate log provide the clearest integrated host contract. Borrow Pi's inference injection, awaited lifecycle listeners and separate durable replay policy. Hermes's correlated hooks and child handles remain useful assets. This is an axis-specific recommendation, not an overall foundation selection or migration authorisation.

Five verified facts support that judgment:

1. **Hermes exposes correlated observation, with limits.** Bundled tool hooks carry task/session/tool/turn/API-request IDs, but terminal-hook exceptions are swallowed [H1]. Its child handles carry parent, correlation, provider/model and depth; the inspected upstream retains these fields [H2][H3]. Upstream's optional OTLP exporter maps monitoring events into spans [H4]; that is distinct from a committed domain-action receipt. Child tests replace construction/execution with fakes [H5].

2. **Pi core has explicit host/testing contracts.** `StreamFn` injects inference; request failures must become stream error/aborted messages [P1]. Typed tool events identify calls; parallel completion events and transcript artifacts have different ordering [P1][P2]. Core subscribers are awaited before idle [P3]. Coding-agent RPC additionally distinguishes low-level `agent_end` from `agent_settled` after automatic continuation [P4]. The subprocess subagent is an example extension, not a stock core lineage contract [P5].

3. **Pi durable is a real, separate adoption unit.** It commits tool intent before execution, defaults replay to unsafe, and reruns only when recorded and current policies both permit safe replay [P6]. Its generation request handler can issue inference on recovered request state [P7]. Conservative tool replay therefore does not itself prevent generation replay or prove integration with stock AgentSession.

4. **OpenCode v2 separates live events, history and settlement.** Schemas distinguish durable tool outcomes from ephemeral progress [O1]. Live subscription is volatile; aggregate log provides ordered replay/follow, but payload persistence defaults false [O2][O3]. Child creation records `parentID` and rejects continuing another parent's child [O4]. Interrupt acknowledges before cleanup; `awaitSettlement`/`awaitIdle` cover settlement [O5]. SDK logging exposes structured attributes/spans, while embedding exposes dependency replacements and defaults to an in-memory database [O6][O7].

5. **Existing tests expose useful race seams, not passing evidence here.** Pi injects a synthetic stream and blocks an async subscriber [P8]. OpenCode replaces Bus layers and pauses historical reads with Deferred barriers to exercise replay/live handoff [O8]. Hermes uses monkeypatching [H5]. Some Pi/Hermes examples also sleep; Renulus should use explicit barriers and controlled clocks for race assertions.

**Proposed acceptance contract:** keep a local trace envelope with run/attempt, parent/delegation-call, event sequence, selected/reported route, operation/revision and outcome. Record fixture/source hashes and exact artifact identities; use opaque references rather than prompt, credential or document payloads. Events explain execution; canonical SQLite receipts establish source, learner and assessment authority. Keep Mem0, Docling/HybridChunker, FastEmbed and LanceDB reusable behind their existing domain boundaries.

Use synthetic documents, learner records and questions, scripted inference streams, fake tools and explicit scheduling barriers:

- **Dispatch:** emit valid, unknown, malformed, blocked and concurrent calls. Assert validation/authorisation before actual dispatch, correlated outcomes, no execution for denied calls, no late progress after settlement, and defined transcript ordering. Distinguish requested, blocked, dispatched and committed states.
- **Child lineage:** interleave two parents and nested children. Assert parent/run/attempt/delegation linkage, restricted tool/source scope, approved route inheritance, rejection of foreign child handles, and completion/cancellation attributed to the correct tree.
- **Approved routes:** inspect every mocked request, including children, summaries, memory capture and background recovery. Exercise all five approved models and explicit auth/quota/model/image rejections; assert visible failure, no alternate model/subscription or extra generation. The dated rejection rule and current `max_retries=0` are exact evidence [R1][R2]; broader transient/restart policy remains unresolved; other-run proofs keep today's conservative baseline.
- **Cancellation:** pause before dispatch, during inference, after mutation/before receipt, and during child cleanup. Distinguish stop accepted from settled; fence late workers and assert one durable outcome. Race cancellation against publication and report the committed winner, without claiming cancellation undoes a committed effect.
- **Evidence provenance:** retrieve synthetic passages with revision/page/locator/access metadata, then replace, delete or revoke them before publication. Assert canonical eligibility rechecks, truthful citation/failure states and no stale index authority. Compare synthetic engine outputs with canonical records; mocked OCR/embedding cannot establish retrieval quality.
- **Restart/mutation:** interrupt after admission, after validated batches and after canonical commit/before acknowledgement. For 5/10/20-question jobs, DC16 specifically requires preserved validated work, zero automatically restarted billed/model work, recoverable drafts and idempotent publication [R3]. Replay safe deterministic validation/index work only under revision fences; reconcile mutations by operation key. Reject incomplete Ready sets; accepting a shorter set updates counts. Edits/deletions must survive index rebuilds and stale worker completion.

These are proposed unit/contract checks: fake inference plus real isolated SQLite transactions, adapter/event contracts and crash-boundary fixtures. Saved-by-default chat/Archive remains a migration target, not acceptance established by transcript persistence. Separate later real-provider checks must establish account entitlement, exact model/image behavior and request accounting; Windows acceptance must establish packaged shutdown/reopen, process termination and native handoffs. Neither proves educational quality: separately evaluate evidence support, question/key validity and learning outcomes across glomerular disease, dialysis, transplantation, AKI and electrolytes.

**Uncertainty/change evidence:** a Pi core-plus-durable integration meeting these contracts could overturn the scoped preference; failure to gate OpenCode recovery would weaken it. Published SDK 2.0.26 uses Effect rc.112 without gitHead; pinned source uses rc.118 [D1][D2]. Source/artifact compatibility and persistent-log configuration need proof. No performance or educational ranking is inferred.

[H1]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/agent/inline_tool_executors.py#L20-L58
[H2]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/agent/subagent_lifecycle.py#L49-L74
[H3]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/agent/subagent_lifecycle.py#L49-L74
[H4]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/agent/monitoring/otlp_exporter.py#L194-L271
[H5]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/tests/agent/test_subagent_lifecycle.py#L43-L83
[P1]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/agent/src/types.ts#L27-L47
[P2]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/agent/src/types.ts#L516-L538
[P3]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/agent/src/agent.ts#L258-L268
[P4]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/rpc.md#L58-L71
[P5]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/examples/extensions/subagent/README.md#L19-L65
[P6]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/tool.ts#L85-L116
[P7]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/generation.ts#L184-L209
[P8]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/agent/test/agent.test.ts#L361-L396
[O1]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/schema/src/session-event.ts#L507-L565
[O2]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/bus.ts#L121-L160
[O3]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/bus.ts#L174-L203
[O4]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/tool/plugin/subagent.ts#L164-L193
[O5]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/session/execution.ts#L26-L42
[O6]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/sdk/src/logging.ts#L40-L66
[O7]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/sdk/src/internal/host.ts#L25-L56
[O8]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/test/bus.test.ts#L630-L661
[R1]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/DECISIONS.md#L142-L152
[R2]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/runtime/hermes.py#L104-L116
[R3]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/planning/DESIGN_C_IMPLEMENTATION_SPEC.md#L678-L695
[D1]: https://registry.npmjs.org/@opencode%2fsdk/2.0.26
[D2]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/package.json#L46-L83

**Handoff:** `docs/research/2026-10-10-harness-adoption/review-17-testing-traces-evaluation.md`. Conclusion: OpenCode v2 for integrated host events; borrow Pi testing/replay seams. Strongest fact: ordered aggregate replay is separate from volatile live delivery. Unresolved risk: recovery may issue model work unless separately gated, violating DC16.

