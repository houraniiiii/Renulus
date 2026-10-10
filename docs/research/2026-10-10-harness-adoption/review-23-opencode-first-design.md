**Review 23 — OpenCode v2 first: one execution owner, small caller interface**

**Final accuracy qualification:** startup-order statements here describe the inspected branch `55dde881`. [Review28](review-28-accuracy-audit.md) verified that published SDK 2.0.26 starts recovery before supplied plugins register; the branch does the reverse. Plugin registration alone is not a proven gate for the published artifact.

October 10, 2026. Source inspection. Reviews 01–20 supplied leads, including final [Review 20](review-20-clients-workspaces-and-harness-interface.md). Sources: OpenCode `55dde8810d8a859c0a21e42491ae7d5801fb49ef`; Renulus `528025ff0b22477c12ee1512e0e7d15297a6e888`. Links identify immutable files and one-based raw ranges.

**Conclusion — design judgment:** OpenCode v2's embedded SDK is the strongest OpenCode-first adoption unit: retain its admission, execution and child coordination behind one Renulus module. One graph gives desktop/headless callers admission and child coordination through a small interface. Recovery/routing containment and Windows packaging remain conditions; no replacement or implementation is selected.

Five verified contracts:

1. Embedding uses an owned in-process fetch. The host accepts layer replacements, defaults its database to memory, registers supplied plugins **before** starting suspended-session recovery, and owns shutdown. The Promise facade needs no CLI/listening server. [H][SDK]
2. Inbox admission reconciles identities; execution claims commit with start events. Stop releases claims while shutdown preserves them. Recovery expressly permits repeated external effects and assumes the previous owner is dead. Interrupt acceptance precedes settlement. [I][E][R]
3. Built-in delegation checks direct-child continuation and depth. Background jobs and observers outlive the launching plugin; completion inserts text into the parent's inbox and normally wakes it. Disposal does not cancel jobs; text does not establish artifact validity. [C][J][N]
4. Tools have schemas, progress and cancellation; transforms add/remove them. `codemode:false` exposes direct tools. `discovery:false` suppresses ambient boot discovery but retains built-ins; removal operations preserve guarded Console/policy plugins. [T][REG][V][PL][GUARD]
5. Historical event payloads default off. Aggregate replay differs from live subscription; `events.persist` enables retention. [B][SR]

**Proposed caller seam — schematic types, not upstream exports:**

```ts
type Start = {
  requestId: string; conversation: ConversationRef;
  workflow: "Chat" | "Cases" | "Study" | "Test";
  input: InputRefs;
};
type Event = { seq?: number; run: RunRef } & (
  | { type: "snapshot"; view: RunView }
  | { type: "text"; delta: string }
  | { type: "tool"; call: ToolCallView }
  | { type: "child"; child: RunRef }
  | { type: "artifact"; artifact: ArtifactRef }
  | { type: "settled"; outcome: Outcome }
);
interface Harness {
  start(spec: Start, grant: GrantHandle): Promise<RunRef>;
  events(run: RunRef, after?: number): AsyncIterable<Event>;
  cancel(run: RunRef): Promise<Outcome>;
}
const run = await harness.start(testRequest, selectedGrant);
for await (const event of harness.events(run, savedCursor)) render(event);
// The client's Stop action separately calls:
const winner = await harness.cancel(run);
// Private owned-Python seam; Commands maps names to input/output schemas.
interface DomainPort {
  invoke<K extends keyof Commands>(name: K, input: Commands[K]["input"],
    ctx: CallContext): Promise<Commands[K]["output"]>;
}
```

Model arguments cannot expand host grants. Acknowledgment follows durable admission; matching request ID/digest returns its receipt, conflicting content fails. Busy defaults to reject; explicit input/steer/follow-up follows Review 20. Detachment never cancels. Reconnect returns state/pending-input/artifact snapshots; progress/text may coalesce. Committed sequence is per run; gaps require snapshots. `Outcome` contains visible failure and canonical receipts; cancel waits for owned-child settlement and reports the durable winner. Session/busy-period mapping remains adapter work.

**Hidden implementation.** A profile lock admits one Windows execution owner. Embed with an absolute `execution.sqlite` path and retained events for saved conversations; temporary conversations use isolated volatile state without durable children. Map mandatory runtime project/directory IDs to owned execution locations, preserving educational Workspace identity. Retention migration/purge remain work. [LOC][SID]

Install reviewed plugins and a replacement `SessionRestart` layer before recovery; registration after `create()` is too late. Validate instance activation before admission. Reconcile receipts and park ambiguous generation for explicit Retry; OpenCode alone owns execution. Replace completion delivery to avoid waking interrupted/cancelled parents. Cap child/tool concurrency, intersect grants and fix routes. Borrow Pi durable's unsafe-by-default replay and separate ancestry/ownership **patterns**; its separate library is a real alternative, without assumed AgentSession wiring or a second imported coordinator. [PD][PO]

Remove editing/shell/Plan tools and coding agents; replace prompts with domain roles and deny `execute`. Code Mode combines tools and HTTP fetch: optional capability, distinct from coding prompts. Check later transforms/guarded integrations; an empty plugin array does not disable built-ins. [CM][REG][ORDER][GUARD]

**Python-domain adapters and dependency classes:**

| Dependency | Proposed seam and adapters |
| --- | --- |
| Pure policies/scoring | In-process inside Python; test real functions. |
| SQLite/files/managed CPU engines | Local-substitutable dependencies: isolated SQLite/files and synthetic fixtures. |
| Owned Python IPC | Typed command port; production framed IPC adapter and in-memory test adapter. |
| Selected generation providers | True external injected transport; approved production adapter and scripted test adapter. |

Directly reuse Python Library evidence/revisions/rights, learner facts/suppression, Chat/Cases retention, and Study/Test modules. Keep reviewed keys/exposure/scoring inside assessment; workers return generated drafts. Retrieval rechecks canonical eligibility; scoring commits attempts/evidence/receipts transactionally. SQLite/originals remain canonical; Mem0 OSS, Docling HybridChunker, FastEmbed and LanceDB remain managed assets. IPC commands carry operation/revision/scope/cancellation fences; receipts/outbox reconcile separate stores. Memory extraction shares the generation gate. The tool-disabled transport needs adaptation. [K][A][G][M]

**Disqualifying evidence and reversal tests.** Reject adoption if route/recovery containment requires rebuilding admission/runner/jobs. Every request must retain selected Codex `gpt-6.1-sol`/`gpt-6-astra`/`gpt-6-luna` or Go `mimo-v2.6-pro`/`deepseek-v4.1-flash`, without fallback. Disable title fallback, compaction repair and retries. The dated rejection rule concerns authentication/quota/model/image errors; general network/restart policy remains unresolved. Conservative proofs disable automatic generation replay. DC16 specifically preserves validated work without automatically restarting billed/model work; deterministic validation/publication replay requires fresh fences/receipts. [ROUTE][TF][CF][D][DC]

Require synthetic duplicate-start/reconnect, child-cancel, crash-after-commit, source-revocation and DC16 races; no unapproved generation or duplicate effect. Windows ownership/native dependencies/purge remain untested. Passing strengthens adoption; Pi durable achieving equivalent semantics with fewer overrides weakens preference. Published SDK 2.0.26 uses Effect rc.112 without gitHead; inspected source uses rc.118; default CLI 1.18.35 is separate. Artifact parity is unproved. No hosted/doctor-managed generative runtime is proposed; educational quality across nephrology needs separate evidence. [DIST][PIN][CLI]

[H]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/sdk/src/internal/host.ts#L18-L68
[SDK]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/sdk/src/promise.ts#L34-L68
[I]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/session/inbox.ts#L154-L201
[E]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/session/execution.ts#L26-L145
[R]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/session/execution/restart.ts#L23-L61
[C]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/tool/plugin/subagent.ts#L117-L255
[J]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/session/subagent-job.ts#L20-L66
[N]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/session/subagent-completion.ts#L21-L45
[T]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/plugin/src/promise/tool.ts#L11-L35
[V]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/instance.ts#L119-L156
[PL]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/plugin/supervisor.ts#L27-L56
[B]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/bus.ts#L156-L203
[SR]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/server/src/routes.ts#L99-L131
[PD]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/tool.ts#L85-L110
[PO]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/types.ts#L264-L298
[CM]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/codemode/tool.ts#L61-L78
[K]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/knowledge/repository.py#L509-L566
[A]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/assessment/repository.py#L251-L304
[G]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/runtime/hermes.py#L66-L114
[M]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/memory/providers.py#L63-L99
[TF]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/session/title.ts#L127-L133
[CF]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/session/compaction.ts#L281-L304
[D]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/DECISIONS.md#L143-L153
[DC]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/planning/DESIGN_C_IMPLEMENTATION_SPEC.md#L678-L695
[DIST]: https://registry.npmjs.org/@opencode%2Fsdk/2.0.26
[PIN]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/package.json#L80-L85
[REG]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/tool.ts#L225-L262
[GUARD]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/plugin/internal.ts#L272-L274
[ORDER]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/plugin/supervisor.ts#L147-L182
[ROUTE]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/runtime/policy.py#L10-L21
[CLI]: https://registry.npmjs.org/opencode-ai/latest
[LOC]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/schema/src/location.ts#L8-L27
[SID]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/session/sql.ts#L22-L35

Handoff: `docs/research/2026-10-10-harness-adoption/review-23-opencode-first-design.md`; conclusion: conditionally prefer embedded v2 for integrated execution/client depth; strongest fact: supplied plugins precede startup recovery; unresolved risk: gating restart and child/auxiliary generation without dismantling that runtime.

