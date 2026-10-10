# Review 25 — Challenge to runtime replacement and combination

October 10, 2026. Source inspection only; no execution or inference. Read reviews 01–20 and the [main study](../2026-10-10-harness-foundation-recommendation.md), then checked decisive assertions against pinned primary files. Baselines: Renulus `528025ff`; bundled/upstream Hermes `af90026a`/`dce1e9b3`; Pi **1.1.0** `abe508e1`; OpenCode **v2/2.0.26** `55dde881` [O-identity]. Full revisions and inspected raw-file line ranges appear below.

**Conclusion — engineering judgment:** reject combining all three execution runtimes. Prefer one local managed owner of agent execution and recovery, using Renulus’s existing domain services. Pi or OpenCode could replace Hermes on demonstrated integration advantages; being newer, modular or durable does not establish those advantages. The earlier Hermes selection supplies no technical tie-breaker. This review selects no migration.

Five verified facts constrain adoption:

1. **The existing integration is not an adopted general loop.** Renulus passes `tools=None`, strips tool definitions and disables SDK retries [R-loop]. Hermes exposes provider, toolset, session and budget controls [H-agent], but defaults to three outer attempts and five recovery cycles [H-retry]. Consequently, keeping Hermes also needs substantial policy integration; preserving its name alone solves nothing.

2. **Pi offers different adoption units with different authority.** Agent-core injects streaming, context transforms and tool hooks [P-agent]. AgentSession’s SessionManager owns a JSONL context tree [P-session]. Separately, pi-durable owns committed conversations, documents and generation/tool tasks, with request-ID reconciliation [P-durable], [P-admit]; it is absent from coding-agent dependencies [P-deps]. Its unsafe-by-default tool replay is real [P-tool], while its recovered request handler still invokes generation [P-generation]. Its API is experimental; the write union lacks conversation/entry deletion, and rewindable retirement preserves revisions [P-experimental], [P-writes], [P-retire]. Pi-durable is a candidate harness, not a proven durability decorator for another loop. The coding-agent subprocess subagent is an example requiring loading [P-child].

3. **OpenCode supplies integrated ownership with consequential defaults.** Its embedded host supplies an owned in-process transport, defaults to memory storage and starts suspended-session recovery [O-host]. Execution claims survive shutdown; recovery explicitly permits repeated external effects [O-claim], [O-restart]. Sessions require project/directory identity [O-session]. These are useful built-ins, but adopting the SDK also adopts a service graph and recovery assumptions; a durable claim does not establish canonical publication correctness.

4. **Published v2 SDK and inspected v2 source are separate identities.** Registry reads on October 10 confirmed published `@opencode/sdk@2.0.26`, Effect rc.112 and no `gitHead`; the branch declares rc.118. Default CLI 1.18.35 neither disproves SDK publication nor proves branch/artifact equivalence [O-registry], [O-version], [O-cli]. This calls for artifact correspondence, not an unsupported claim that v2 is unavailable or unreliable.

5. **Learning authority and scheduling remain domain work.** Renulus already transactionally scores pinned reviewed items and resolves memory/index hits to current canonical records [R-score], [R-memory], [R-library]. Hermes has general cron [H-cron]; Pi’s task resumption and OpenCode’s Job interface do not establish the nightly learner contract [P-durable], [O-job]. DC19 requires day deduplication, bounded catch-up, disable/cancel and stale-input checks [R-nightly]. No inspected runtime contract establishes those learning behaviors or educational quality.

**Combination critique — inference:** a Hermes loop inside Pi inside OpenCode would introduce competing session identifiers, context/compaction boundaries, provider dispatch and recovery policies, tool catalogues and permission decisions. A parent could record cancellation while another owner resumes generation; one store could retire a document while another retains its transcript. Reconciling these outcomes becomes Renulus work. Pi/OpenCode plus Python domain workers can be justified; retaining all three loops adds translation and ownership boundaries without an identified requirement. Costs include serialized tool/evidence results, cancellation propagation, settlement/event ordering, dependency packaging and coordinated purge. No latency or memory measurement is claimed [H-agent], [P-session], [P-durable], [O-host].

**Necessary proposed boundaries:** committed run admission; observable events/snapshots; cancellation acceptance and settlement; trusted scope/model/tool policy; canonical effect receipts and outbox reconciliation. Separate SQLite stores do not share atomic commits. Keep originals and source/learner/assessment authority in Renulus SQLite, with Mem0 OSS, Docling/HybridChunker, FastEmbed and LanceDB derived services [R-assets]. Saved-by-default/Archive remains an incomplete migration [R-retention]. Retaining the attributed Hermes Mem0 adapter [R-adapter] does not require retaining Hermes’s execution loop. A universal runtime interchange framework, three-way session synchronization or a new distributed broker has no demonstrated need here.

Borrow Pi’s content/details and replay/ownership distinctions [P-result], [P-tool], [P-ownership], OpenCode’s admission/settlement and scoped lifecycle patterns [O-claim], [O-lifecycle], and Hermes’s Python integration [H-agent] where useful. Pattern borrowing creates no runtime dependency. Importing maintained code means accepting its package/dependency closure, schema/API updates and compatibility tests. Consider Pi agent-core/controlled AgentSession, pi-durable, and OpenCode’s embedded graph as explicit alternative units; assess a smaller retained adapter independently.

Every generative purpose keeps the exact selected-subscription/model boundary [R-models]. The October 6 rule covers visible authentication/quota/model/image rejection without automatic retries/fallback [R-rule]. Keep the current retry-disabled proof baseline; general transient-network/restart policy remains unresolved. DC16 separately requires preserved validated test work after cancellation/restart **without automatically restarting billed/model work** [R-generation]. Safe deterministic validation or receipt reconciliation differs from repeating generation.

**Counterevidence and unresolved risk:** Pi becomes preferable if its chosen unit proves controlled parent/child dispatch, generation-recovery gating, purge/migration and Windows ownership with fewer intrusive changes than Hermes isolation. OpenCode becomes preferable if reproducible SDK/source identity, neutral directory mapping, child settlement/reconnect and DC16 gating preserve existing domain receipts. Hermes becomes preferable if its Python embedding satisfies the same controls with less maintained machinery. Those are future acceptance comparisons, not measurements. Exact subscription tool calling and native Windows behavior remain untested; coding capability supplies no nephrology-quality evidence.


Primary sources: immutable GitHub files; anchors specify inspected one-based raw-file lines. Registry observations are separately dated October 10, 2026.

[R-loop]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/runtime/hermes.py#L80-L113
[H-agent]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/run_agent.py#L263-L312
[H-retry]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/agent/agent_init.py#L1465-L1476
[P-agent]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/agent/src/agent.ts#L113-L141
[P-session]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/session-manager.ts#L976-L1007
[P-durable]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/README.md#L71-L113
[P-admit]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/submissions.ts#L149-L175
[P-deps]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/package.json#L49-L73
[P-tool]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/tool.ts#L82-L110
[P-generation]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/generation.ts#L184-L209
[P-experimental]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/README.md#L1-L7
[P-writes]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/types.ts#L708-L724
[P-retire]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/storage/sqlite/storage.ts#L899-L925
[O-host]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/sdk/src/internal/host.ts#L30-L68
[O-claim]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/session/execution.ts#L76-L145
[O-restart]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/session/execution/restart.ts#L23-L61
[O-session]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/session/sql.ts#L22-L35
[O-registry]: https://registry.npmjs.org/@opencode%2Fsdk/2.0.26
[O-identity]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/package.json#L1-L8
[P-child]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/examples/extensions/subagent/README.md#L1-L52
[O-version]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/package.json#L76-L85
[O-cli]: https://registry.npmjs.org/opencode-ai/latest
[R-score]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/assessment/repository.py#L251-L303
[R-memory]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/memory/service.py#L278-L310
[R-library]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/knowledge/repository.py#L531-L565
[H-cron]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/cron/jobs.py#L787-L798
[O-job]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/job.ts#L95-L113
[R-nightly]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/planning/DESIGN_C_IMPLEMENTATION_SPEC.md#L738-L752
[R-assets]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/DECISIONS.md#L48-L53
[R-retention]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/DECISIONS.md#L23
[R-adapter]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/memory/engine.py#L67-L82
[P-result]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/agent/src/types.ts#L424-L445
[P-ownership]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/types.ts#L264-L279
[O-lifecycle]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/plugin.ts#L126-L179
[R-models]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/runtime/policy.py#L11-L20
[R-rule]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/DECISIONS.md#L142-L152
[R-generation]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/planning/DESIGN_C_IMPLEMENTATION_SPEC.md#L678-L695

Handoff: `docs/research/2026-10-10-harness-adoption/review-25-challenge-runtime-combination.md`. Conclusion: one execution/recovery owner, with selective code or pattern reuse. Strongest fact: conservative Pi tool replay does not gate recovered generation. Unresolved risk: maintaining recovery, purge and canonical receipts across the selected runtime/domain boundary.
