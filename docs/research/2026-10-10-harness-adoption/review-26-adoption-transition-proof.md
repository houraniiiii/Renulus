# Review 26 — Bounded adoption transition and proof

**Final accuracy qualification:** startup-order statements here describe the inspected branch `55dde881`. [Review28](review-28-accuracy-audit.md) verified that published SDK 2.0.26 starts recovery before supplied plugins register; the branch does the reverse. Plugin registration alone is not a proven gate for the published artifact.

October 10, 2026. Research only; no runtime tests or inference. Read the [provisional synthesis](../2026-10-10-harness-foundation-recommendation.md) and reviews [21](review-21-hermes-first-design.md), [22](review-22-pi-first-design.md), [23](review-23-opencode-first-design.md), [24](review-24-challenge-hermes-preference.md), [25](review-25-challenge-runtime-combination.md); their claims supplied leads. Primary source pins: Renulus 528025ff, bundled Hermes af90026a, Pi **1.1.0** abe508e1, OpenCode **v2/2.0.26 source** 55dde881. References below contain full immutable revisions and one-based raw-file ranges.

**Conclusion — judgment:** evaluate pi-durable as the sole execution owner through a bounded compatibility adapter before moving saved conversations. Preserve existing Python domain services and client flows; Pi durable remains experimental. [P-status] Its task machinery justifies the candidate only if adoption retains that machinery while proving dispatch correlation, purge, canonical reconciliation and Windows ownership. This proposes a path, not a foundation switch.

Five verified facts constrain the transition:

1. Renulus’s Provider returns strings; its Hermes transport removes tools, rejects tool-call output and disables SDK retries. Wrapping that iterator cannot establish an agent loop. Existing run/cancel routes provide a compatibility surface. [R-port][R-codec][R-tool][R-api]
2. Pi’s HarnessOptions injects Models, registry and optional environment. Admission commits before returning, but duplicate request IDs check submission type, not payload equality. This establishes neither drop-in **full-agent injection** nor restart-stable dispatch-claim propagation. A Hermes/AgentSession instance is not the documented injected unit. [P-options][P-admit][P-reconcile]
3. Reopen initially dispatches nothing; progress conveniences enable global scheduling. Generation’s request phase calls Models again; ordinary beforeRequest hook failures are reported without blocking. Stream dispatch does not explicitly pass task ID/attempt. Conservative tool replay is a separate, real contract. [P-open][P-resume][P-request][P-stream][P-hooks][P-tool]
4. Existing Library retrieval rechecks canonical revisions after search. Generated-practice publication checks a request digest and records its result transactionally; reviewed scoring commits pinned assessment records. These remain domain authority, not runtime transcripts. [R-library][R-publish][R-score]
5. Pi’s write union lacks conversation/entry deletion; retiring rewindable documents retains revisions. Renulus’s backup uses an explicit table/credential exclusion policy. A second operational store therefore needs coordinated purge, migrations and recovery manifests. [P-writes][P-retire][R-backup]

**Smallest real proof — proposed after implementation authorisation:** one headless generated-practice batch, with one owned evidence child, actual Pi admission/tasks/SQLite and the existing Python validator/publisher. Use scripted typed model/tool events and synthetic text/PDF/image fixtures across glomerular disease, dialysis and transplantation. Children are host-defined tasks/tools, not assumed stock CLI subagents. This proves integration semantics; real engines, subscriptions and educational quality require separate evidence.

Bind request IDs to payload digests and each dispatch to conversation/task/attempt/purpose, route and grant. Demonstrate model-tool-result continuation, visible rejection, client detach/reattach and Stop settlement. Inject failures before dispatch, after dispatch with an unknown outcome, and after canonical publication before runtime acknowledgment. Reopen observationally, then **submit unrelated new work while old generation remains interrupted**: global scheduling must not bypass the old dispatch gate. Reconcile the publication receipt without duplicating it. Race source deletion and cancellation against publication; report the committed winner. Purge a fork and retired document, then restore with tombstones. Exercise a managed Windows host and Python worker with one profile owner and developer runtimes absent; Pi itself supplies no cross-process lock. [P-resume][P-storage]

Conformance must count parent/child/summary/memory dispatches: one attempted request for authentication/quota/model/image rejection, zero for broker-construction failure, and no fallback. A hook exception cannot authorize dispatch.

Keep the selected subscription and exactly Codex gpt-6.1-sol/gpt-6-astra/gpt-6-luna or Go mimo-v2.6-pro/deepseek-v4.1-flash. Preserve the retry-disabled proof baseline. The dated rejection rule concerns authentication/quota/model/image errors; general transient-network/restart policy remains unresolved. DC16 specifically preserves validated work without automatically restarting billed/model work. Replaying deterministic validation or receipt reconciliation requires fresh fences; it is not generation replay. [R-models][R-rule][DC16]

**Migration seams — proposal:** retain canonical SQLite/originals, Mem0 OSS/Qdrant, Docling HybridChunker, FastEmbed and LanceDB. [R-stack] Extend the private generation codec to typed assistant/tool messages, usage, continuity and terminal outcomes; reuse protected authentication/selection assets without copying credentials. Models must call this transport, not recursively invoke the old orchestrator. Give owned Python commands operation IDs, payload digests, revision/cancellation fences and durable receipts/outbox reconciliation across stores.

Keep existing HTTP/SSE routes and original readers as client adapters; translate harness snapshots/events and explicit cancellation, with stable run IDs and snapshot resynchronization. Completion follows canonical publication, not merely agent settlement. Move workflow orchestration at its owner boundary, including auxiliary generation, rather than stacking Pi around existing autonomous runners. Preserve Library, reviewed Test, Memory correction/deletion, Study and Updates flows. Treat saved-by-default/Archive as its unfinished migration: map canonical chat IDs to operational conversations, stage history conversion and cover temporary derivatives, backup/restore and deletion before importing real history. Temporary payloads and child derivatives stay volatile. [R-api][R-retention]

**Backout and reversal conditions — judgment:** keep canonical schemas readable by the previous application until compatibility proofs pass. Stop admission, settle owned workers and reconcile receipts before switching owners; park unfinished generation for explicit disposition. Never restore an old snapshot over newer learning records. Reject Pi durable if dispatch identity requires bypassing its runner, purge cannot cover forks/revisions through a maintainable adapter, reconciliation cannot resolve committed effects, or Windows ownership fails. Hermes’s Python embedding or OpenCode’s plugin-before-recovery seam could reverse the recommendation if they pass the same contracts with retained machinery. Pi agent-core remains a different option with an explicitly missing durable coordinator. [H-options][O-host]

Later extensions can add DC16 batch checkpoints, scoped parallel children and occurrence-ID scheduled work through the same owner. Enable compaction and memory generation only after their dispatch/conformance checks pass. No source inspection establishes approved-model tool support, package/artifact correspondence or native lifecycle acceptance; those remain adoption evidence, not inferred readiness.

[P-status]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/README.md#L1-L7
[R-port]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/generation.py#L8-L15
[R-codec]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/runtime/hermes.py#L66-L113
[R-tool]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/runtime/hermes.py#L129-L149
[R-api]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/runtime/api.py#L123-L138
[P-options]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/types.ts#L453-L469
[P-admit]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/submissions.ts#L53-L60
[P-reconcile]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/submissions.ts#L155-L162
[P-open]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/scheduler.ts#L238-L269
[P-resume]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/types.ts#L571-L590
[P-request]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/generation.ts#L184-L209
[P-stream]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/generation.ts#L365-L410
[P-hooks]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/scheduler.ts#L1131-L1143
[P-tool]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/tool.ts#L85-L110
[R-library]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/knowledge/repository.py#L531-L565
[R-publish]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/assessment/generated_repository.py#L228-L249
[R-score]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/assessment/repository.py#L251-L303
[P-writes]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/types.ts#L708-L724
[P-retire]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/storage/sqlite/storage.ts#L914-L928
[R-backup]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/storage/backup.py#L19-L45
[P-storage]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/README.md#L536-L545
[R-models]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/runtime/policy.py#L10-L20
[R-rule]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/DECISIONS.md#L142-L152
[DC16]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/planning/DESIGN_C_IMPLEMENTATION_SPEC.md#L678-L695
[R-stack]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/DECISIONS.md#L48-L54
[R-retention]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/DECISIONS.md#L23
[H-options]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/run_agent.py#L263-L312
[O-host]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/sdk/src/internal/host.ts#L30-L68

**Handoff:** memo docs/research/2026-10-10-harness-adoption/review-26-adoption-transition-proof.md; conclusion: conditional Pi durable transition through preserved domain/client seams; strongest fact: new submissions enable global scheduling; unresolved risk: restart-stable dispatch correlation and complete purge without replacing the adopted machinery.
