**Review 20 — Clients, workspaces and the harness interface**

**Final accuracy qualification:** startup-order statements here describe the inspected branch `55dde881`. [Review28](review-28-accuracy-audit.md) verified that published SDK 2.0.26 starts recovery before supplied plugins register; the branch does the reverse. Plugin registration alone is not a proven gate for the published artifact.

2026-10-10. Source inspection; no runtime tests. Pins: Renulus `528025ff0b22477c12ee1512e0e7d15297a6e888`; bundled Hermes `af90026aa09949579bd423d24def3d38f743cde0`; inspected Hermes `dce1e9b37581dd62e480a9064dc04a709c2940d3`; Pi 1.1.0 `abe508e1b89912adde45528136c3221eb69acdd7`; OpenCode v2 source 2.0.26 `55dde8810d8a859c0a21e42491ae7d5801fb49ef`. Links identify immutable files and one-based raw-file ranges.

**Conclusion (judgment):** Prefer OpenCode v2 **on this client/execution-boundary axis**. Its shared router and service graph provide the clearest existing seam. Borrow Pi's explicit busy-input/settled semantics and durable replay classification; assess its durable library separately. Borrow Hermes's pending-question snapshots for reconnect. Retain Renulus's canonical services and selected Python engines. This does not select a replacement; Design C remains the desktop client direction.

Verified facts:

1. **Hermes already separates protocols from execution.** Upstream documents ACP, TUI JSON-RPC and HTTP/SSE driving the same AIAgent, with live-session subscriber attachment distinct from saved-session discovery ([protocols, lines 11–60][H1]). Its RPC replay returns pending questions, a process epoch and a truncation indication: [bundled lines 2586–2600][H2], [upstream lines 2334–2348][H3]. This supplies reconnect behavior, not durable event replay across process death.
2. **Pi's stock session is directly embeddable.** SDK and CLI modes share agent/session resources ([CLI lines 3–18][P1]). `AgentSession` exposes steer/follow-up queues; `abort()` waits for idle, while unsubscribing only removes a listener ([implementation lines 1364–1378][P2], [2211–2232][P3], [2402–2443][P4]). SDK documentation distinguishes `agent_settled` from lower-level `agent_end` and requires an explicit busy-input choice ([lines 62–94][P5]). Queues are [process memory, lines 143–174][P11], separate from saved context.
3. **Pi durable is a real additional adoption unit.** Admission commits and reconciles conversation/request IDs ([lines 53–60, 148–175][P6]); interrupted tools rerun only when recorded and current policies both declare replay safe ([lines 85–110][P7]). Its committed-state watcher reconnects from a snapshot rather than replaying history ([README lines 276–323][P8]). Storage requires one owning process ([lines 536–545][P9]). AgentSession integration remains unverified.
4. **OpenCode can host the same router without a network listener.** Server and embedded entry points share `makeRoutes` ([lines 80–105][O1]); the SDK returns an in-process fetch handler, session/workspace services and close operation. It defaults to memory storage and launches recovery after plugin registration ([host lines 30–68][O2]). Stock desktop discovers or starts the managed CLI server ([lines 32–91][O3]). This requires no internet-hosted Renulus service.
5. **OpenCode separates admission, pending work and interruption.** Its inbox persists admissions ([lines 154–201, 277–322][O4]); the protocol exposes `resume:false`, pending-input listing/cancellation and delivery changes ([lines 396–415][O5], [607–644][O6]). Interrupt acceptance precedes cleanup settlement ([lines 26–42][O7]). Historical event payload retention defaults off ([bus lines 174–203][O8]), so cursor-based replay needs an explicit retention choice.

**Proposed contract, not implemented behavior.** One worker per learner profile owns execution. Sessions hold context; runs execute workflows; attempts identify execution tries. Desktop, optional CLI and a Windows scheduled invocation connect to or bootstrap that same owner through authenticated loopback/IPC. A profile lock prevents competing writers. The scheduler submits a stable occurrence ID; required human input parks the run. Windows wake behavior needs acceptance.

Route clients and subagents through canonical domain services. Renulus constructs its API around one services/database instance ([lines 19–60][R1]). Keep SQLite/originals canonical; reuse [Mem0, Docling/HybridChunker, FastEmbed and LanceDB, lines 48–53][R6] through services; indexes remain derived. Harness transcripts/documents are operational records. Separate runtime/domain stores need receipts and outbox reconciliation, not assumed atomicity. A workspace identifies project/source scope independently of Git. OpenCode would add a TypeScript/Effect–Python boundary; Pi durable needs more host orchestration. Neither proves educational quality.

| Operation | Proposed semantics |
| --- | --- |
| `start(requestId, spec)` | Commit admission before acknowledgment; return session/run IDs. Pin workflow, scope, input references, retention, capabilities and allowed subscription/model. States: queued/running/awaiting_input/cancelling/interrupted/succeeded/failed/cancelled. Repeated ID plus matching payload returns the same receipt; conflicting payload fails. |
| `events(runId, afterSeq)` | Replay ordered persisted envelopes, then follow live updates. Include run/attempt/child IDs, sequence, type and payload; terminal means settled. Snapshot includes state, pending inputs and artifact references. A cursor gap requests resync. Detaching never cancels. |
| `input(runId, id, payload, mode)` | Explicit reject/steer/follow-up; record queued versus consumed. Clarification/approval answers target separate request IDs and settle once. Busy never implies a delivery choice. |
| `cancel(runId, scope)` | Record intent, fence stale workers and cancel owned children. Return accepted first; settled outcome later reports cancellation or already-completed publication. History forks do not determine cancellation ownership. |
| `resume(runId, mode)` | `attach` reconstructs state without generation; `continue_safe` permits classified deterministic work; explicit `retry_generation` creates an attempt retaining the selected route. |
| `artifacts(runId)` | Versioned manifests: ID, MIME/name/size, hash, run/attempt, canonical record reference, source revisions/citations, retention and draft/validated/published state. References open through scoped services; a transcript is not a scored assessment. |

Persist lifecycle/input/artifact/terminal events; coalesce text deltas with a recoverable snapshot. Canonical publication and receipts must agree. [Saved conversations, line 23][R5] and temporary-input inheritance remain rules. [DC16 lines 678–695][R2] specifically preserves validated generated-test batches after cancellation/restart, forbids automatically restarting billed/model work, excludes temporary inputs from durable jobs, and returns the durable publication/cancellation winner. Safe validation or idempotent publication replay is different from renewed generation.

The [dated rejection rule, lines 142–152][R3] covers authentication/quota/model/image errors; the [adapter, lines 104–116][R4] disables SDK retries. General network/restart policy remains unresolved; retain this conservative proof baseline. OpenCode's [restart recovery, lines 23–61][O9] and Pi durable's [request recovery, lines 184–209][P10] need explicit gating.

Uncertainties: Windows ownership/recovery, cross-store purge, and exact subscription routing remain untested. Published [SDK 2.0.26][D1] uses Effect rc.112 without gitHead; inspected [v2 source][D2] uses rc.118. [Default CLI 1.18.35][D3] is separate (checked October 10). Pi durable proving three clients, restart gating and canonical reconciliation—or ungateable OpenCode recovery—would change the preference. Require synthetic duplicate-start, reconnect, pending-answer, cancellation/publication and restart tests with zero unapproved generation replay.

Handoff: `docs/research/2026-10-10-harness-adoption/review-20-clients-workspaces-and-harness-interface.md`. Conclusion: prefer OpenCode v2's shared local boundary; borrow Pi semantics and retain canonical Renulus services. Strongest fact: the embedded host shares the router without a listener. Unresolved risk: default recovery can restart model work.

[H1]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/website/docs/developer-guide/programmatic-integration.md#L11-L60
[H2]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/tui_gateway/methods_session.py#L2586-L2600
[H3]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/tui_gateway/methods_session.py#L2334-L2348
[P1]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/cli-integration.md#L3-L18
[P2]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/agent-session.ts#L1364-L1378
[P3]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/agent-session.ts#L2211-L2232
[P4]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/agent-session.ts#L2402-L2443
[P5]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/sdk.md#L62-L94
[P6]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/submissions.ts#L53-L175
[P7]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/tool.ts#L85-L110
[P8]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/README.md#L276-L323
[P9]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/README.md#L536-L545
[P10]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/generation.ts#L184-L209
[O1]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/server/src/routes.ts#L80-L105
[O2]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/sdk/src/internal/host.ts#L30-L68
[O3]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/desktop/src/main/service/background-service.ts#L32-L91
[O4]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/session/inbox.ts#L154-L322
[O5]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/protocol/src/groups/session.ts#L396-L415
[O6]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/protocol/src/groups/session.ts#L607-L644
[O7]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/session/execution.ts#L26-L42
[O8]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/bus.ts#L174-L203
[R1]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/server.py#L19-L60
[R2]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/planning/DESIGN_C_IMPLEMENTATION_SPEC.md#L678-L695
[R3]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/DECISIONS.md#L142-L152
[R4]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/runtime/hermes.py#L104-L116
[D1]: https://registry.npmjs.org/@opencode/sdk/2.0.26
[D2]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/package.json#L76-L95
[D3]: https://registry.npmjs.org/opencode-ai/latest
[P11]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/agent/src/agent.ts#L143-L174
[O9]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/session/execution/restart.ts#L23-L61
[R5]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/DECISIONS.md#L23
[R6]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/DECISIONS.md#L48-L53
