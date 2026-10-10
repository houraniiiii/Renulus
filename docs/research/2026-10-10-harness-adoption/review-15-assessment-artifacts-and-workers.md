**Review 15 — Assessment artifacts and domain workers**

October 10, 2026. Source inspection only. Links identify Renulus `528025ff`, bundled Hermes `af90026a`, upstream Hermes `dce1e9b3`, Pi **1.1.0** `abe508e1`, and OpenCode **v2** `55dde881`. Ranges are raw-file lines; plans describe future behavior.

**Conclusion (judgment):** For assessment workers, Pi’s SDK offers the clearest host-controlled boundary: explicit custom tools and loadouts leave publication and scoring with Renulus. Evaluate its separate durable library for recovery; borrow Hermes’s structured delegation and OpenCode’s child-job supervision. This scoped preference does not settle the whole-harness choice or authorise replacement.

Five verified facts carry this conclusion:

1. **Reviewed scoring is already domain-owned.** Renulus compares submitted options with the pinned key, transactionally records attempts/evidence/receipts, and separates fresh/assisted/repeat buckets [R1]. Presentation records family exposure before returning content; help records assistance before disclosure [R2], [R2h]. Bank eligibility accepts `assistant_reviewed` or `human_reviewed` plus `source_key_checked`; those labels do not establish independent clinical validation [R3].

2. **Generated practice has reusable structural gates.** Unique option IDs and a key naming one option are required [R4]. Retrieval excludes reserved assessments and ineligible rights/currentness; streaming checks count, evidence indices and source revisions before publication [R5], [R5v]. Feedback says `generated-unreviewed` [R6]. These checks establish neither evidential correctness nor educational quality.

3. **Hermes has custom-tool/delegation seams.** Its bundled registry accepts schema/handler/toolset registrations, and child toolsets inherit restrictions, although configured MCP inheritance can broaden a narrowed selection [H1], [H1t]. Both pins’ output-schema validation can make another model turn to repair invalid output [H2], [H2b]. Renulus strips tools and rejects tool responses [R7]; workers require new integration.

4. **Pi supports host loadouts; subagents and durability are distinct.** The SDK accepts `customTools`, explicit tool allowlists, exclusions and resource/session managers [P1]. Its subprocess subagent implementation is an example [P2]. Separately, `pi-durable` commits tool intent, defaults replay to unsafe, reruns interrupted tools only when stored/current policies both permit it, and reconciles submissions by request ID [P3], [P3r]. This library is a real adoption unit, not stock AgentSession wiring.

5. **OpenCode v2 supplies child jobs and tool hooks.** Plugins can add typed tools and reject execution before it runs [O1]. Native subagents check permission and support foreground/background child sessions, but completion is text, not a validated question artifact [O2], [O2j]. Restart recovery permits repeated external effects [O3]; it cannot guarantee unique saved-test publication.

**Proposed artifact contracts and roles**

Every artifact needs a schema version, stable identity, revision/content digest, producer/run identity, exact subscription/model, retention scope and dependency revisions. Workers receive scoped inputs and write proposals only.

| Artifact / worker | Contract and authority boundary |
| --- | --- |
| `EvidenceComparison` / evidence comparator | Claim-to-passage references with source/revision/digest, locator, edition/check date, allowed use and support/conflict/unresolved findings. Citations resolve through the source service; comparisons cannot declare currency or rights by themselves. |
| `QuestionDraft` / author | Topic/objective IDs, original stem/options, proposed key, rationale and evidence references. Origin remains generated/imported/personal; missing or ambiguous keys block Ready. No worker-selected reviewed status. |
| `ReviewReceipt` / critic | Pins the exact draft digest, identifies reviewer/type, records findings and proposed changes. Changes create another draft revision and invalidate earlier receipts. Assistant review never masquerades as independent human review. |
| `PracticeSetProposal` / assembler | Ordered draft revisions, requested/actual counts, coverage, duplicates and unresolved items. May propose key-free reviewed item IDs; canonical selection retains family/exposure policy. Partial sets require explicit acceptance of the displayed count. |
| `PublicationReceipt` / trusted domain service | Idempotency key plus request digest, dependency/cancellation fence, canonical test/version ID and actual terminal outcome. A transaction publishes one immutable version; chat cards and Tests reference that identity. Workers cannot publish scores or rewrite attempts. |

These are proposals implementing the C contract: immutable saved tests, attempts pinned to versions, separate origin/review quality/Study–Test mode, and no promotion of personal results into reviewed cohorts [C1]. Existing sessions start directly and lack this saved-test layer [C2]. Bank admission remains a separate authorised content workflow; Ready is structural usability, not bank review.

**Enforcement and tradeoffs (judgment)**

Expose eligible retrieval, draft submission and review submission tools. Withhold bank-key APIs, scoring, pack installation, SQL, shell and unrestricted files; the content repository explicitly treats keyed reads as trusted backend access [R8]. Apply the C disclosure gate to tools, chat, caches and command replays during unfinished Test; Study help records exposure first [C1]. The one-active-Test/export restrictions remain labelled planning defaults.

Keep SQLite canonical and reuse Mem0 OSS, Docling/HybridChunker, FastEmbed and LanceDB behind local interfaces [R9]. Hermes preserves Python proximity; Pi requires a local bridge and worker coordinator; OpenCode supplies more supervision but requires a confined plugin/service graph. Transcripts and derived indexes cannot become assessment authority. Use these contracts across nephrology domains; coding-agent capability proves no teaching quality.

Use the chosen subscription/five-model allowlist for every worker. Preserve the visible authentication/quota/model/image rejection rule and zero-SDK-retry baseline [R7], [R10]. For proofs, gate Hermes schema repair and Pi/OpenCode recovery requests; Pi durable can resend checkpointed generation independently of tool replay policy [P4]. Broader transient/restart policy is proposed. C requires validated checkpoints, cancellation fencing and no automatic restart of model work; temporary input crosses only as a validated fictional artifact or after explicit Save [C3], [C4].

Unresolved: no integrated Windows proof was run. Synthetic evidence covering stale/deleted sources, ambiguous keys, duplicate publication, cancellation and unfinished-Test disclosure could change this preference. Published `@opencode/sdk` 2.0.26 exists, but uses Effect rc.112 with no `gitHead`; the branch uses rc.118 [O4], [O4b]. Source and artifact identity need separate proof.


[R1]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/assessment/repository.py#L250-L304
[R2]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/assessment/repository.py#L120-L131
[R2h]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/assessment/repository.py#L308-L329
[R3]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/assessment/content.py#L15-L20
[R4]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/assessment/generated_contracts.py#L26-L55
[R5]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/assessment/generated_streaming.py#L87-L114
[R5v]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/assessment/generated_streaming.py#L219-L235
[R6]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/assessment/generated_repository.py#L328-L346
[R7]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/runtime/hermes.py#L80-L143
[R8]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/content/repository.py#L28-L34
[R9]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/DECISIONS.md#L48-L54
[R10]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/DECISIONS.md#L142-L152
[H1]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/tools/registry.py#L666-L685
[H1t]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/tools/delegate_tool_toolsets.py#L77-L123
[H2]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/tools/delegate_tool_child_run.py#L478-L518
[H2b]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/tools/delegate_tool_child_run.py#L478-L503
[P1]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/sdk.ts#L64-L103
[P2]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/examples/extensions/subagent/README.md#L1-L52
[P3]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/tool.ts#L85-L110
[P3r]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/submissions.ts#L149-L162
[P4]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/generation.ts#L184-L209
[O1]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/plugin/src/effect/tool.ts#L8-L59
[O2]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/tool/plugin/subagent.ts#L100-L151
[O2j]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/tool/plugin/subagent.ts#L184-L265
[O3]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/session/execution/restart.ts#L46-L61
[O4]: https://registry.npmjs.org/@opencode%2fsdk/2.0.26 "Exact-version metadata read October 10, 2026"
[O4b]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/package.json#L80-L85
[C1]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/planning/DESIGN_C_IMPLEMENTATION_SPEC.md#L232-L306
[C2]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/planning/DESIGN_C_IMPLEMENTATION_SPEC.md#L347-L351
[C3]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/planning/DESIGN_C_IMPLEMENTATION_SPEC.md#L678-L695
[C4]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/planning/DESIGN_C_IMPLEMENTATION_SPEC.md#L308-L315

Handoff: `docs/research/2026-10-10-harness-adoption/review-15-assessment-artifacts-and-workers.md`. Conclusion: prefer Pi’s worker boundary; preserve Renulus authority. Strongest fact: reviewed scoring/exposure already commit in domain transactions. Unresolved risk: recovery or late worker output bypassing publication/disclosure gates.
