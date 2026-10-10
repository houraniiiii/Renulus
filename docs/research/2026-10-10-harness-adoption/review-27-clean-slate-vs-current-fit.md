# Review 27 — Clean slate versus current Renulus fit

October 10, 2026. Research only. Read reviews 01–25 and the [provisional synthesis](../2026-10-10-harness-foundation-recommendation.md), particularly competing designs [21](review-21-hermes-first-design.md)/[23](review-23-opencode-first-design.md) and critiques [24](review-24-challenge-hermes-preference.md)/[25](review-25-challenge-runtime-combination.md). Decisive assertions below were independently checked against pinned primary files. Links specify full revisions and one-based raw-file ranges. No runtime or provider acceptance was performed.

**Recommendation — architectural judgment:** Pi is the strongest domain-neutral foundation and my recommended direction for actual Renulus: evaluate **Pi 1.1.0's separate pi-durable library as the sole execution owner**, retaining Python domain services. Existing assets change the adoption boundary more than the preferred architecture. Durable is a conditional candidate, not production-ready adoption or permission to change the recorded foundation. Agent-core is a different, smaller execution unit; its queues do not supply durable admission [P-core].

Five verified facts carry this conclusion:

1. **Renulus's substantial investment is separable from its agent loop.** Its transport supplies no tools, removes tool declarations and disables SDK retries [R-transport]. Library search rechecks canonical rights/revisions after index retrieval; reviewed scoring commits attempts, evidence and receipts in one transaction [R-search][R-score]. Mem0 loads an attributed Hermes backend source unit [R-memory]. Thus preserving these assets does not require choosing Hermes's full execution loop.

2. **Pi durable supplies genuine reusable machinery.** It requires injected Models and a registry, permits an optional execution environment, and depends on pi-ai/Chord rather than coding-agent/agent-core [P-options][P-package]. Submission acknowledgment follows a storage commit; duplicate request IDs check type, not payload equality [P-admission]. Tool execution records intent first, defaults replay to unsafe, and requires both recorded/current policies to permit replay [P-tool]. These are library contracts, not stock AgentSession behavior or CLI subagent examples.

3. **Durable's policy and retention gaps are structural.** A recovered generation request phase calls inference independently of the error-retry toggle [P-generation]. Ordinary beforeRequest hook failures are reported and execution continues [P-hooks]. StorageWrite exposes no conversation/entry deletion; retirement removes revision bytes only for current-only documents [P-writes][P-retire]. The API is explicitly experimental [P-experimental]. Conservative tool replay therefore proves neither generation control nor coordinated purge.

4. **OpenCode v2 is the strongest integrated alternative.** Its SDK owns an in-process transport, accepts layer replacements and registers plugins before startup recovery [O-host]. Recovery explicitly permits repeated external effects, while sessions require project/directory identity [O-restart][O-session]. Published SDK 2.0.26 exists, with Effect rc.112 and no gitHead; inspected branch 55dde881 declares rc.118 [O-registry][O-version]. Publication does not establish artifact/source correspondence. Its client machinery is an adoption advantage; its identity/recovery defaults are adaptation work.

5. **Hermes has a real proximity advantage with policy costs.** Bundled af90026a accepts routes, toolsets, session storage and budgets in its Python constructor [H-constructor]. Inspected dce1e9b3 can fall back from a distinct summary model after access/quota failure [H-summary]. That latter fact concerns the inspected upstream, not evidence of today's Renulus behavior. Existing Python packaging stages dependencies/helpers, so reuse benefits every contender [R-staging].

For a clean domain-neutral harness, Pi's injected models/tools/state give the clearest composition boundary to me. OpenCode adds project identity; Hermes's full agent requires containing auxiliary summary routing [P-options][O-session][H-summary]. This is a composition judgment, not a performance comparison. Once durable tasks are required, starting with agent-core merely moves task ownership, checkpoints and admission into new host code [P-core][P-admission]. However, “avoids rebuilding the coordinator” must be narrowed: durable still needs a Renulus client protocol, request-digest binding and generation dispatch correlation. A generic Models interface does not prove task/attempt correlation [P-models].

For current Renulus, preserve Mem0 OSS, Docling/HybridChunker, FastEmbed, LanceDB and canonical SQLite/originals [R-decisions]. Python proximity legitimately reduces serialization boundaries for Hermes; attributing every domain asset to that loop would be sunk-cost reasoning. Conversely, calling Pi a simple swap would ignore its additional managed Node host, Python cancellation boundary and separate operational store [P-package][P-status]. Keep source/learner/assessment authority canonical; reconcile runtime/domain commits through receipts/outbox, rather than assuming shared atomicity. Saved-default/Archive migration remains incomplete [R-retention]. Borrow OpenCode's embedded-client pattern for optional application/CLI clients and retain Renulus's attributed Hermes memory adapter to preserve engine reuse [O-host][R-memory]. Neither requires another execution owner.

My recommendation changes under concrete conditions:

- **Choose OpenCode v2 instead** if Pi's purge, migrations or dispatch correlation require replacing its task/storage machinery, while a verified OpenCode domain profile passes those contracts with its existing runner intact. Test a crash after canonical commit/before runtime acknowledgment, fork purge/restore, and rejected generation during restart. Pre-start layer replacement is a real alternative seam [O-host].
- **Choose Hermes instead** if controlled full-loop Python embedding passes the same generation, purge, receipts and Windows proofs with a bounded patch surface, while the JS/Python bridge requires duplicated domain checks or cannot settle owned workers. An explicitly changed Python-only headless deployment requirement would also favor Hermes. Existing staging alone proves neither result [H-constructor][R-staging].
- **Choose Pi agent-core instead of durable** if durable cannot meet retention/recovery contracts and a deliberately owned coordinator is demonstrably preferable; or if the owner explicitly removes durable-job requirements. It must not be presented as equivalent shipped machinery [P-core].

The four synthesis gates remain blocking: actual generation recovery/correlation, coordinated purge/migration, canonical reconciliation and single-owner native Windows packaging. Preserve the selected Codex/Go five-model boundary and visible authentication/quota/model/image rejection without retries/fallback [R-decisions][R-rule]. Adoption proofs keep SDK retries disabled and recovered inference gated; general transient-network/restart policy remains unresolved. DC16 separately requires preserved validated test work without automatically restarting billed/model work; safe deterministic reconciliation is different [R-dc16]. Exact-model tool support, native delivery and educational quality across nephrology remain untested by this review.

[R-transport]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/runtime/hermes.py#L80-L143
[R-search]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/knowledge/repository.py#L531-L592
[R-score]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/assessment/repository.py#L251-L303
[R-memory]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/memory/engine.py#L67-L82
[R-staging]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/apps/desktop/scripts/stage-backend.py#L205-L237
[R-decisions]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/DECISIONS.md#L39-L54
[R-retention]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/DECISIONS.md#L23
[R-rule]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/DECISIONS.md#L142-L152
[R-dc16]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/planning/DESIGN_C_IMPLEMENTATION_SPEC.md#L678-L695
[P-core]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/agent/src/agent.ts#L113-L174
[P-options]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/types.ts#L453-L469
[P-package]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/package.json#L105-L112
[P-admission]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/submissions.ts#L53-L175
[P-tool]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/tool.ts#L85-L110
[P-generation]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/generation.ts#L184-L209
[P-hooks]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/scheduler.ts#L1131-L1143
[P-writes]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/types.ts#L708-L724
[P-retire]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/storage/sqlite/storage.ts#L914-L926
[P-status]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/README.md#L536-L545
[P-experimental]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/README.md#L1-L7
[P-models]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/ai/src/models.ts#L316-L340
[O-host]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/sdk/src/internal/host.ts#L18-L70
[O-restart]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/session/execution/restart.ts#L46-L61
[O-session]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/session/sql.ts#L22-L35
[O-registry]: https://registry.npmjs.org/@opencode%2Fsdk/2.0.26
[O-version]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/package.json#L81-L85
[H-constructor]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/run_agent.py#L263-L312
[H-summary]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/agent/context_compressor.py#L4301-L4325

Handoff: docs/research/2026-10-10-harness-adoption/review-27-clean-slate-vs-current-fit.md. Conclusion: Pi for both scenarios; pi-durable conditionally first. Strongest fact: current Renulus rejects tool execution while preserving reusable canonical domain services. Unresolved risk: durable adoption may require replacing the machinery whose reuse motivates it.
