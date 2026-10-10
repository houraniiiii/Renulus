**Review 22 — Pi-first harness design**

**Final accuracy qualification:** generic beforeRequest failures are reported without enforcing rejection, but initial beforeTool exceptions block the call. Safe replay bypasses initial beforeTool and argument validation; every domain executor needs fresh argument and authority checks. See [review28](review-28-accuracy-audit.md).

October 10, 2026. Research only; reviews 01–20, including the completed [client-interface review](review-20-clients-workspaces-and-harness-interface.md), informed this design. Decisive assertions were checked in raw primary source. Renulus pin: `528025ff0b22477c12ee1512e0e7d15297a6e888`; Pi v1.1.0 pin: `abe508e1b89912adde45528136c3221eb69acdd7`. No execution, installation or provider acceptance was performed.

**Conclusion — judgment:** choose **pi-durable behind a pinned Renulus adapter** as the strongest Pi-first adoption unit. It alone owns agent execution. Do not layer AgentSession or agent-core as another owner: AgentSession’s [concrete JSONL manager][session] and core’s [memory queues][queue] would duplicate lifecycle responsibilities without supplying durable admission. Experimental churn requires pinning API, schema and dependencies together; it does not by itself disqualify this design. This proposes evaluation, not a foundation switch.

Five verified facts determine the design:

1. `Harness.open(storage, options, context)` requires a registry and injected `Models`; an execution environment is optional. Typed documents and phase-based tasks are library contracts. The package depends on pi-ai/Chord, without coding-agent/agent-core. This permits domain-neutral composition. [open][options][documents][tasks][deps]
2. Submission admission commits before acknowledgment. Reusing a conversation/request ID checks submission **type**, not payload equality. Renulus must additionally bind IDs to payload digests and reject conflicts. [admit][reconcile]
3. Reopen dispatches nothing initially, but submit/wait/abort conveniences enable scheduling globally. A recovered generation `request` phase can resend independently of error retries. Attach must use read-only inspection, with a separate transport gate for recovered inference. [reopen][resume][generation]
4. Tools commit validated intent, default replay to unsafe, and rerun only when recorded/current policies both permit it. Arguments are revalidated after tool hooks. However, ordinary hook errors are reported and execution continues: throwing from `beforeRequest` is **not** a rejection gate. Enforce generation policy in the injected transport. [tool][hooks]
5. Ownership is separate from history ancestry. Storage writes expose document retirement without conversation/entry deletion; rewindable retirement preserves revisions. Saved transcripts therefore need an additional migration/purge contract and storage-level deletion work. [ownership][writes][retire]

**Proposed small interface** — symbolic domain types, not implemented code:

```ts
type StartSpec = { requestId: string; conversationId: string;
  workflow: { id: string; version: number }; inputRefs: string[] };
type RunEvent = { seq: number; runId: RunId; attemptId: string;
  childId?: RunId; state: RunState; artifactRefs: string[] };
interface RenulusHarness {
  start(spec: StartSpec): Promise<RunReceipt>;
  events(runId: RunId, afterSeq?: number): AsyncIterable<RunEvent>;
  input(runId: RunId, reply: InputReply): Promise<InputReceipt>;
  cancel(runId: RunId, scope: CancelScope): Promise<CancelReceipt>;
  resume(runId: RunId, mode: "attach" | "safe" | "retry_generation"):
    Promise<RunReceipt>;
}
// Private owned-process seam; commands are a versioned discriminated union.
interface DomainPort {
  invoke(command: DomainCommand, context: ScopedInvocation): Promise<DomainReceipt>;
  receipt(operationId: string): Promise<DomainReceipt | undefined>;
}
```

`StartSpec` names a registered workflow/version, request ID, conversation and input references; trusted policy derives grants, retention and route. `RunEvent` carries sequence, run/attempt/child identity, state and artifact references. For example, a client starts a ten-question practice-set workflow, follows progress, cancels, then receives the actual settled publication/cancellation outcome. Reconnecting attaches without generation; detaching does not cancel.

**Hidden implementation — proposal:** one managed local Node host per learner profile opens pi-durable; Desktop, CLI and scheduled invocations share its authenticated IPC interface and profile lock. Upstream requires single-process storage ownership. [storage] A managed Python child executes bounded domain commands over versioned JSON records through pipes, with request IDs, cancellation, structured failures and size limits. It imports existing domain modules, including the [attributed Hermes Mem0 adapter][mem0] and [Docling/FastEmbed/LanceDB engines][engines][lance]; it owns no second agent loop.

Library evidence/revisions/rights, learner facts/suppression, Chat/Cases retention, Study/Test and reviewed keys/exposure remain canonical Python/SQLite responsibilities. Workers submit generated draft artifacts, never scores or reviewed status. Runtime documents hold checkpoints, grants and receipts; transcripts and indexes remain operational/derived. Cross-store publication uses canonical outbox/receipt reconciliation and revision/cancellation fences, not assumed shared atomicity. Temporary conversations require volatile storage and no durable payload-bearing children; saved-default/Archive needs the existing migration.

| Dependency category | Proposed strategy |
| --- | --- |
| In-process | Keep pure policies/scoring with their domain module; no transport abstraction for pure computation. |
| Local-substitutable | SQLite/files and managed CPU engines use isolated fixtures/substitutes; actual engine acceptance remains separate. |
| Owned Python IPC | Typed DomainPort with pipe production adapter and in-memory test adapter. |
| True external generation | Inject selected-subscription transport and scripted test transport through Models. |

The adapter opens `Harness.open(store, { registry, models: brokerModels, settings: { retry: { enabled: false }, compaction: { enabled: false } } }, context)` without ambient CLI discovery or generic shell tools. The host must propagate trusted task/attempt/purpose identity into the broker, reserve aggregate child/request budgets, and commit a one-use dispatch claim before inference. Unknown claims and all recovered model phases await explicit Retry in adoption proofs. This correlation/recovery gate needs proof beyond the upstream Models interface. [models] Apply the exact five-model/selected-subscription policy to children, summaries and Mem0 extraction. Preserve visible authentication/quota/model/image rejection and the zero-SDK-retry proof baseline; general transient/restart policy remains unresolved. [rule][transport]

Create owned child conversations through durable tasks; narrow grants and retention, supervise cancellation and validate typed results. The [foreground/background demonstrations][children] are examples, not a shipped Renulus coordinator. Add occurrence-ID scheduling and Windows wake/lifecycle handling; due work enters the same owner. Existing Python runners must surrender autonomous model redispatch; deterministic outbox processing can remain domain-owned. DC16 checkpoints validated batches, reconciles safe deterministic work and requires explicit Retry for renewed billed/model work. [dc16]

**Tradeoff and reversal evidence — judgment:** Pi’s explicit composition favors flexibility, but Renulus must build client event replay, approval/input handling and scheduling. Its watcher supplies [snapshots, not event replay][watch]; OpenCode already offers an [embedded router][oc], so this is a real adoption cost. Borrow permission/action and reconnect patterns from [review 19](review-19-capability-policy-and-extension-scope.md) and review 20; directly import only the chosen Pi packages and retained Python assets. Treat extensions as trusted application code; this design supplies no sandbox.

Reject this recommendation if the pinned adapter cannot prevent recovered inference, purge forked/rewindable copies, reconcile canonical effects, or package Windows shutdown with one owner reliably. Synthetic duplicate-start, hook-failure, cancellation/publication, reconnect and DC16 crash proofs would strengthen it; exact-model tool streaming and educational quality across nephrology need separate evidence. Freeze MIT notices, full locks, schema migrations and artifact hashes; [experimental API churn][experimental] makes every upgrade deliberate.

Handoff: `docs/research/2026-10-10-harness-adoption/review-22-pi-first-design.md`. Conclusion: conditional pi-durable as sole execution owner, with a narrow Python seam. Strongest fact: durable admission/tool intent and injected Models coexist. Unresolved risk: recovery gating and purge remain unproved.

[session]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/session-manager.ts#L975-L1007
[queue]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/agent/src/agent.ts#L143-L174
[open]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/harness.ts#L411-L435
[options]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/types.ts#L453-L469
[tasks]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/types.ts#L170-L260
[deps]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/package.json#L105-L112
[admit]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/submissions.ts#L53-L60
[reconcile]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/submissions.ts#L148-L185
[resume]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/types.ts#L571-L590
[generation]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/generation.ts#L184-L209
[tool]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/tool.ts#L62-L110
[hooks]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/scheduler.ts#L1131-L1143
[ownership]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/types.ts#L269-L298
[writes]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/types.ts#L708-L724
[retire]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/storage/sqlite/storage.ts#L899-L925
[mem0]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/memory/engine.py#L67-L82
[engines]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/knowledge/engines.py#L92-L148
[lance]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/knowledge/engines.py#L394-L417
[rule]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/DECISIONS.md#L142-L152
[transport]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/runtime/hermes.py#L104-L116
[children]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/README.md#L414-L459
[dc16]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/planning/DESIGN_C_IMPLEMENTATION_SPEC.md#L678-L695
[watch]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/README.md#L276-L323
[oc]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/sdk/src/internal/host.ts#L30-L68
[experimental]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/README.md#L1-L7
[documents]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/types.ts#L41-L113
[reopen]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/scheduler.ts#L238-L269
[storage]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/README.md#L536-L545
[models]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/ai/src/models.ts#L250-L372
