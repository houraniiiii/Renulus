# Review 07 — Pi host tools, permissions and subagents

**Synthesis clarification:** references below to disabling all automatic generative retries describe the conservative adoption-proof baseline. The October 6 confirmed rule specifically concerns actual authentication, quota, model and image rejection without automatic retry/fallback; transient-network and restart policies remain separate proposals. [Review09](review-09-route-control-authentication.md) resolves this scope. This distinction qualifies the earlier shorthand, rather than establishing a broader ban.

This memo examines agent-core/AgentSession or the CLI subagent example. Pi also has a separate experimental durable library; its real admission/task/replay capabilities are evaluated in [review10](review-10-execution-durability-cancellation.md). They are not implicitly included in AgentSession.
2026-10-10. Scope: Pi 1.1.0 [V], `abe508e1b89912adde45528136c3221eb69acdd7`, against Renulus `528025ff0b22477c12ee1512e0e7d15297a6e888`. Earlier notes/reviews supplied leads; decisive files were read at these pins. Links specify inspected raw, one-based line ranges. Source inspection only: no execution, Windows acceptance or provider inference.

**Conclusion — judgment:** Pi offers a suitable typed execution core, but its example subagent is insufficient as Renulus's coordinator. An unspecified orchestrator usefully leaves domain authority with Renulus; for a harness centred on subagents, supplying that coordinator is material engineering work. Consider a controlled SDK host, but do not credit Pi with shipping the required orchestration. No foundation change is selected.

Five verified facts and their host implications:

1. **Tool integration is explicit and typed.** SDK options accept `customTools`, allowlists/exclusions and suppression of built-ins [A]. `ToolDefinition` supplies TypeBox parameters, optional output schema, execution-mode hints, cancellation and progress callbacks [B]. For non-TypeBox schemas, one coercion branch returns original arguments when checking the coerced value fails [B2]; this merits a targeted test. **Proposed host work:** bridge retrieval definitions to existing Python services, independently validate arguments/results, and return bounded passages with source/revision IDs, locators and currency. Scope comes from trusted run context, not model arguments. Retrieval already checks rights, active revisions, deletion and excluded pages against SQLite after index search [R1]. Preserve those checks rather than exposing raw index hits.

2. **Permission hooks do not supply a complete policy.** A `tool_call` handler can block; handlers may mutate arguments without subsequent revalidation [C1][C2]. Agent-core catches preflight rejection as a failed call, while an absent veto permits execution [C3]. A veto does not itself terminate siblings [C1]. Pi documents that tools/extensions use the process account's permissions and project trust does not restrict tool access [D]. **Proposed host work:** enforce capabilities/rights at the service boundary, validate final arguments and keep policy outside model input. Every child needs this policy. Arbitrary extension JavaScript requires trusted loading and an execution boundary compatible with personal Windows computers.

3. **Parallel tools and parallel agents are different layers.** Agent defaults to parallel tool execution [E]; any sequential tool makes its whole batch sequential [E2]. The subagent example adds its own queue: eight tasks, four simultaneous workers per invocation [F1][F2][F3]. Usage accumulates from completed assistant messages [G]; it does not enforce token/request budgets. **Proposed host work:** shared admission across conversations/nested delegations, maximum depth, cancellation-aware dequeueing, and parent/child request, token, elapsed-time and optional retrieval-service usage budgets. Reserve quotas before dispatch, reconcile usage on settlement, and define whether sibling failure cancels the group. Canonical mutations retain transactional controls; a parallel hint cannot authorize racing records.

4. **Subagents are an example with incomplete host inheritance.** The extension is absent from the CLI built-in list [H1][H2]. Its child launch uses a separate CLI process, `--no-session`, an agent-definition or dispatching-session model, and optional tool names [I]. It does not transfer SDK tool implementations or policy hooks. SDK sessions also require explicit factories/binding for CLI MCP facilities [J]. **Proposed architecture:** a controlled child-session factory sharing trusted definitions/policy while isolating context. Pi's nested `executeTool()` supplies validation/hooks and `parentToolCallId` [K]; tool nesting does not establish a durable child-agent lifecycle. Add run/parent IDs, ordered events, terminal outcomes and retention records. The example forwards completed-message snapshots, not a replayable child event stream [G].

5. **Cancellation remains cooperative.** Core passes the AbortSignal and awaits executor completion [L2]. The example connects it to SIGTERM and conditional SIGKILL; its queue does not check abort before assigning another item [L][F2]. Escalation tests `proc.killed`, not observed exit. **Proposed host work:** stop admission, cancel every owned request/tool/child, await settlement, and establish Windows process-tree cleanup if using subprocesses. Define transaction outcomes: interrupting a transcript does not establish rollback. These source paths do not prove successful Windows cancellation.

**Proposed host contract, not shipped behavior:** a trusted run context carries conversation/run/parent IDs, capabilities, source scope, the exact subscription/model, quotas, deadline and cancellation. The same context governs tool invocation, child dispatch and each model step. Child grants can narrow parent permissions; model-supplied arguments cannot enlarge them.

**Project tradeoff — judgment:** retain Mem0 OSS, Docling/HybridChunker, FastEmbed, LanceDB OSS and canonical SQLite behind the host. Existing source supplies CPU embedding, chunking and embedded index adapters [R2a][R2b]; Mem0 imports the attributed Hermes backend [R3]. Preserve that adapter where useful. Source, learner and reviewed-assessment authority remain distinct from transcripts/derived indexes. Saved-by-default conversations and Archive retain their separate migration requirement. Coding examples do not establish educational quality across nephrology.

Exact Codex/Go subscription/model restrictions must apply before every parent/child request; agent-definition overrides cannot bypass them. Under the retained no-automatic-generative-retry rule, sessions must disable provider/session retries and separately prevent overflow/truncation regeneration. Pi defaults session retries on [M] and implements a separate compact-and-retry path [N]. Changing this rule would be a labelled proposal.

**Uncertainty and reversal evidence:** approved-model tool-call compatibility, streaming budget enforcement, policy inheritance, partial parallel failure and Windows cleanup remain untested. A subsequently authorised synthetic SDK trial demonstrating final-argument rejection, shared budgets, stable parent/child events, no automatic regeneration and cancellation without orphan workers would strengthen adoption. Invasive loop/session patches for those controls would weigh against it. No benchmark or migration estimate is claimed.

[V]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/package.json#L1-L4
[A]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/sdk.ts#L64-L104
[B]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/extensions/types.ts#L574-L642
[B2]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/ai/src/utils/validation.ts#L317-L349
[C1]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/extensions/types.ts#L1426-L1435
[C2]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/extensions/types.ts#L1222-L1226
[C3]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/agent/src/agent-loop.ts#L725-L775
[D]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/security.md#L3-L19
[E]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/agent/src/agent.ts#L243-L253
[E2]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/agent/src/agent-loop.ts#L515-L522
[F1]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/examples/extensions/subagent/index.ts#L33-L36
[F2]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/examples/extensions/subagent/index.ts#L219-L237
[F3]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/examples/extensions/subagent/index.ts#L604-L667
[G]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/examples/extensions/subagent/index.ts#L353-L388
[H1]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/examples/extensions/subagent/README.md#L1-L52
[H2]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/extensions/index.ts#L1-L14
[I]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/examples/extensions/subagent/index.ts#L300-L350
[J]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/sdk.md#L114-L116
[K]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/extensions/types.ts#L367-L394
[L]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/examples/extensions/subagent/index.ts#L410-L424
[L2]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/agent/src/agent-loop.ts#L831-L844
[M]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/settings-manager.ts#L1010-L1028
[N]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/agent-session.ts#L2947-L3046
[R1]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/knowledge/repository.py#L509-L581
[R2a]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/knowledge/engines.py#L92-L148
[R2b]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/knowledge/engines.py#L394-L417
[R3]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/memory/engine.py#L67-L82

**Handoff:** `docs/research/2026-10-10-harness-adoption/review-07-pi-tools-subagents.md`; conclusion: good tool primitives, material coordinator work; strongest fact: example children receive CLI configuration rather than the parent's SDK tool/policy objects; unresolved risk: enforceable child policy/budgets and Windows cancellation.

