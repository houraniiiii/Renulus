# Review 02 — Pi 1.1.0 as a reusable harness core

**Synthesis clarification:** references below to disabling all automatic generative retries describe the conservative adoption-proof baseline. The October 6 confirmed rule specifically concerns actual authentication, quota, model and image rejection without automatic retry/fallback; transient-network and restart policies remain separate proposals. [Review09](review-09-route-control-authentication.md) resolves this scope. This distinction qualifies the earlier shorthand, rather than establishing a broader ban.

This memo examines agent-core/AgentSession or the CLI subagent example. Pi also has a separate experimental durable library; its real admission/task/replay capabilities are evaluated in [review10](review-10-execution-durability-cancellation.md). They are not implicitly included in AgentSession.
2026-10-10. Scope: released Pi 1.1.0 at `abe508e1b89912adde45528136c3221eb69acdd7`, against Renulus `528025ff0b22477c12ee1512e0e7d15297a6e888`. The pinned manifest declares 1.1.0 [V]. Existing comparison notes supplied leads; the assertions below were checked against primary source and its raw, one-based lines. This is source inspection, without runtime, provider or Windows acceptance testing. It reopens evaluation only.

**Conclusion (judgment):** Pi is a credible core for a domain harness. Its strongest adoption depth for Renulus would be the controlled **AgentSession SDK inside a Renulus-owned local host**, with the application consuming that host. Using agent-core alone gives the smallest interface but discards useful conversation lifecycle behavior. Stock CLI/RPC adoption brings more ambient configuration and coding policy. This supports considering Pi as a foundation candidate; it does not select it over Hermes or OpenCode or authorise a switch.

Four verified facts determine that conclusion:

1. **The smallest host boundary is real, but typed.** `AgentOptions` exposes `streamFn`, initial state, context/message conversion and before/after tool hooks [A]. A useful host supplies its exact model, prompt and tools, then uses prompting, event subscription, cancellation and idle waiting [A2][A3]. Tool executors receive arguments, cancellation and an update callback; results separate model-facing content from structured details [B2]. The transport must return Pi's `AssistantMessageEventStream`, encode request failures as stream events, and accept system/tool declarations inside the transcript rather than `context.systemPrompt/tools` [B]. Thus domain neutrality does not remove the provider-protocol adapter.

2. **AgentSession adds conversation machinery and a concrete persistence model.** The factory constructs model/auth runtime, settings, resources and session services; their explicit injection points include custom tools and an active-tool allowlist [C][C2]. AgentSession adds persistence, compaction, branching and queued work [D]. Its storage parameter is a concrete `SessionManager` with a private constructor and JSONL entry tree, rather than a generic SQLite storage interface [E]. `inMemory(..., entries)` can reconstruct externally held history [E2]. Adoption therefore needs host journaling/reconstruction or a storage change. Merely replacing `agent.state.messages` does not replace finalized session context [D]. Public event callbacks are invoked without awaiting their promises, so asynchronous host persistence needs its own completion barrier [D2]. The ordinary retry toggle does not govern the separate compaction/regeneration recovery path [L][L2]; preserving Renulus's no-automatic-generative-retry rule needs explicit adaptation.

3. **CLI facilities are not automatically SDK facilities.** In 1.1.0 the CLI really includes MCP, codemode and tool search. An SDK host must add their factories; MCP connects on `session_start`, requiring `bindExtensions()` [F]. Subagent delegation remains an example extension that runs separate Pi processes and requires explicit loading [G]. Borrowing that example does not supply a product-level delegation authority, durable task ownership or Renulus-specific child-agent budgets.

4. **RPC changes locality, not domain ownership.** It controls a long-lived local child through LF-delimited JSON records, with command IDs, events and backpressure. Prompt acceptance is distinct from completion; clients wait for `agent_settled` [H]. The inspected command union controls sessions/models/bash but exposes no remote custom-tool registration contract [I]. Tool implementations therefore need child-side extensions or another host bridge. Pi and its extensions run with their process account's permissions; neither `cwd` nor project trust is a sandbox [J]. These are local execution boundaries, not an owner-hosted service requirement.


**Work Renulus still owns (assessment):** exact subscription/model policy, tool permissions, delegation and client/session identities; source revision/rights checks and passage citations; learner corrections/deletion, reviewed-bank scoring and generated-practice separation. Saved-by-default conversations still need Archive, temporary mode and recovery semantics. Pi transcripts and summaries must remain distinct from canonical source, learner and assessment authority. The inspected interfaces do not establish educational quality across nephrology.

**Reuse recommendation:** retain the existing Python engine services behind a local typed tool/service bridge, preserving canonical SQLite transactions [R1]. Existing source contains app-managed CPU FastEmbed, Docling/HybridChunker and embedded LanceDB adapters [R2][R3][R4]. Mem0 is reusable, but its current adapter explicitly imports the vendored Hermes `OSSBackend`; replacement is not automatically independent of that code [R5]. Retaining an attributed adapter is preferable to rewriting these engines simply because the agent loop changes. This is source evidence of integration assets, not renewed quality or performance acceptance.

**Uncertainties and reversal evidence:** exact Codex/Go compatibility, Windows process lifecycle and SQLite replay consistency remain untested. An authorised seam check should cover abort/settlement, branching/restart and absence of automatic regeneration on failure or overflow; exact-model account acceptance remains separate. If these need invasive session patches or contradictory transcript authority, I would favour agent-core-only integration or another foundation. Clean adapters preserving those constraints would strengthen AgentSession adoption. No broader architecture audit was attempted.

All Pi links below use the full immutable commit; fragments specify inspected raw line ranges.

[V]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/package.json#L1-L4
[A]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/agent/src/agent.ts#L113-L149
[A2]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/agent/src/agent.ts#L257-L351
[A3]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/agent/src/agent.ts#L370-L410
[B]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/agent/src/types.ts#L22-L37
[B2]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/agent/src/types.ts#L424-L488
[C]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/sdk.ts#L48-L106
[C2]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/sdk.ts#L195-L205
[D]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/sdk.md#L26-L70
[D2]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/agent-session.ts#L1038-L1043
[E]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/session-manager.ts#L975-L1007
[E2]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/session-manager.ts#L1803-L1805
[F]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/sdk.md#L112-L116
[G]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/examples/extensions/subagent/README.md#L1-L52
[H]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/rpc.md#L3-L71
[I]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/modes/rpc/rpc-types.ts#L20-L74
[J]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/security.md#L3-L19
[L]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/agent-session.ts#L2947-L2953
[L2]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/agent-session.ts#L3003-L3046
[R1]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/storage/database.py#L17-L58
[R2]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/knowledge/engines.py#L92-L126
[R3]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/knowledge/engines.py#L129-L148
[R4]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/knowledge/engines.py#L394-L417
[R5]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/memory/engine.py#L67-L82

**Handoff:** memo `docs/research/2026-10-10-harness-adoption/review-02-pi-runtime.md`; conclusion: controlled AgentSession SDK is a credible local harness core; strongest fact: replaceable typed transport/tools; unresolved risk: preserving SQLite authority and zero automatic generative retries through session recovery.

