# Review 29 — Intent and scope audit

**Final accuracy qualification:** startup-order statements here describe the inspected branch `55dde881`. [Review28](review-28-accuracy-audit.md) verified that published SDK 2.0.26 starts recovery before supplied plugins register; the branch does the reverse. Plugin registration alone is not a proven gate for the published artifact.

October 10, 2026. Source inspection only. Reviewed the provisional synthesis and alternatives 21/23, critiques 24/25 and the recorded product decisions; followed decisive claims to primary files. Pins: Renulus `528025ff`; bundled Hermes `af90026a` (upstream comparison `dce1e9b3`); Pi **1.1.0** `abe508e1`; OpenCode **v2/2.0.26** `55dde881`. References contain complete immutable revisions and directly counted raw-file ranges. No implementation, installation, runtime launch or inference was performed.

**Conclusion — judgment:** the [provisional Pi direction](../2026-10-10-harness-foundation-recommendation.md) fits the owner's data/retrieval/tools/execution/subagents-first intent. Its proposed ownership and canonical-service boundaries could produce a real harness. The four blocking proofs establish necessary controls, but omit an explicit extension contract and independently callable data operations. Keep pi-durable as a proof candidate; calling it the best concrete foundation remains conditional. Research does not authorise replacing Hermes.

Five verified facts constrain that conclusion:

1. **The current adapter cannot supply the requested agent loop.** It passes `tools=None`, removes tool declarations, disables SDK retries and rejects returned tool calls. Renaming its text stream or exposing it headlessly preserves this limitation. [R-loop]
2. **Pi durable supplies substantive, domain-neutral machinery.** Its options inject Models and a registry, with an optional execution environment. Extensions register typed executable tools and tasks; generation/tool/compaction are built-ins. Its dependencies include pi-ai/Chord, rather than agent-core/coding-agent. This is a separate, explicitly experimental library, not demonstrated AgentSession integration or a supplied nephrology coordinator. [P-options][P-tools][P-registry][P-package][P-status]
3. **Its recovery contracts leave adoption work.** Tool intent defaults to unsafe replay; rerun requires both recorded/current policies to permit it. The generation request phase separately calls the model stream. Storage writes expose document retirement without conversation/entry deletion; rewindable retirement retains revisions. Durable tasks therefore do not establish DC16 compliance or coordinated purge. [P-tool][P-generation][P-writes][P-retire]
4. **Existing domain authority is reusable.** Retrieval rechecks active revisions, deletion, permissions and excluded pages after index search; reviewed answers, versioned attempts, learning evidence and replay receipts commit transactionally. Those services retain value under any execution owner. SQLite/originals and the selected Mem0 OSS/local Qdrant, Docling/HybridChunker, FastEmbed and LanceDB roles remain explicit decisions. [R-retrieval][R-score][R-assets]
5. **Both alternatives support genuine embedding.** Hermes exposes provider/model/toolset/session controls and callbacks. OpenCode's v2 host supplies owned fetch and lifecycle services, with supplied plugins registered before recovery. A published SDK 2.0.26 exists, but uses Effect rc.112 against this branch's rc.118; artifact correspondence remains unproved. Coding-oriented defaults do not alone disqualify either alternative. [H-constructor][O-host][O-registry][O-effect]

**Required distinguishing outcomes — proposed acceptance additions:**

| Outcome | Observable evidence |
| --- | --- |
| Data without conversation | An independent consumer imports/queries eligible synthetic material and obtains revision/passage/locator references without model dispatch, Electron or a created conversation. |
| Extension without app changes | Register a new bounded retrieval tool and child role through a versioned host contract; invoke them through the actual loop without editing renderer routes or executor internals. Invalid arguments/grants execute nothing. |
| Connected learning flow | Across glomerular disease, dialysis and transplantation fixtures, import text/PDF/image → retrieve → supervised evidence/review children → cited explanation and validated practice draft → canonical saved artifact. A separate reviewed-bank attempt retains its scoring/key boundary. |
| Client and recovery independence | A second minimal consumer attaches to the same run and artifacts. Detachment, cancellation settlement, restart and source replacement produce consistent receipts, with no unauthorised generation or stale publication. |

A scripted model can test orchestration, not actual approved-model tool support, extraction quality or educational quality. These outcomes should run through one bounded real integration; separate demonstrators of a registry, database and chat stream cannot establish the connected flow. The existing delivery and breadth decisions already require more than a single-topic demonstration. [R-product]

**Scope corrections — judgment:** publish a small capability/operation contract plus registered workflow IDs, inputs, events and artifacts; avoid freezing the harness around four app screens. Retain domain services rather than creating duplicate canonical stores or a universal runtime interchange framework. Durable admission is valuable for generated-test work; a passage query need not become a durable conversation. Pi still needs client events/input handling, scheduling and purge integration: the existence of tasks does not demonstrate less total maintained machinery.

An optional CLI, permanent daemon, remote hosting, plugin marketplace, arbitrary shell execution or mandatory MCP layer is not established by “application as client.” A managed local owner can start on demand. Preserve Windows delivery without owner-hosted inference, doctor-managed GPU/Docker/generative-server setup or mandatory paid generation APIs. Trusted reviewed extensions can be the initial surface; broader execution remains a proposed capability requiring a concrete use case. Design C, saved-default/Archive migration, temporary scope and the existing Windows app remain product obligations. [R-product]

Preserve all five exact models on the selected subscription for parents, children, summaries and memory extraction. The dated rejection rule covers authentication/quota/model/image errors; the conservative proof baseline disables retries, while general transient-network/restart policy remains unresolved. DC16 specifically preserves validated test work without automatically restarting billed/model work. Safe deterministic reconciliation is a different operation. [R-models][R-rule][DC16]

**Reversal conditions:** reject durable-first if its recovery/purge changes replace the task machinery adopted to avoid rebuilding it, or its proposed extension proof requires a second autonomous owner. Prefer OpenCode if its embedded coordination passes the same domain/route/recovery conditions with bounded overrides and verified artifacts; prefer Hermes if controlled Python embedding delivers those outcomes with less maintained machinery. These are prospective comparisons. Compare the observed maintained surface: a new ledger around Hermes, duplicate coordination around Pi tasks, or replaced OpenCode admission/recovery would each weaken its respective case. The four blocking proofs, approved-model continuation and native Windows ownership remain unverified.

[R-loop]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/runtime/hermes.py#L80-L143
[P-options]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/types.ts#L453-L469
[P-tools]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/types.ts#L208-L271
[P-registry]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/registry.ts#L9-L27
[P-package]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/package.json#L105-L112
[P-status]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/README.md#L1-L7
[P-tool]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/tool.ts#L85-L110
[P-generation]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/generation.ts#L184-L209
[P-writes]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/types.ts#L708-L724
[P-retire]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/storage/sqlite/storage.ts#L914-L925
[R-retrieval]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/knowledge/repository.py#L531-L592
[R-score]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/assessment/repository.py#L251-L304
[R-assets]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/DECISIONS.md#L48-L53
[H-constructor]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/run_agent.py#L263-L312
[O-host]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/sdk/src/internal/host.ts#L30-L70
[O-registry]: https://registry.npmjs.org/@opencode%2Fsdk/2.0.26
[O-effect]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/package.json#L81-L85
[R-product]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/DECISIONS.md#L13-L55
[R-models]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/runtime/policy.py#L10-L20
[R-rule]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/DECISIONS.md#L142-L152
[DC16]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/planning/DESIGN_C_IMPLEMENTATION_SPEC.md#L678-L695

**Handoff:** `docs/research/2026-10-10-harness-adoption/review-29-intent-and-scope-audit.md`; conclusion: Pi fits the direction, durable remains conditional pending extension/data/connected-flow proofs; strongest fact: current generation explicitly strips/rejects tools; unresolved risk: meeting recovery/purge requirements without rebuilding the execution owner.
