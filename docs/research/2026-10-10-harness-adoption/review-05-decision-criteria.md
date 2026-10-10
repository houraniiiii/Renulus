# Review 05 — adoption gates for a harness-first Renulus

**Synthesis clarification:** references below to disabling all automatic generative retries describe the conservative adoption-proof baseline. The October 6 confirmed rule specifically concerns actual authentication, quota, model and image rejection without automatic retry/fallback; transient-network and restart policies remain separate proposals. [Review09](review-09-route-control-authentication.md) resolves this scope. This distinction qualifies the earlier shorthand, rather than establishing a broader ban.

2026-10-10. Research only; source contracts inspected, no candidate execution or account validation. Baselines: Renulus `528025ff`; bundled Hermes `af90026a`; inspected upstream Hermes `dce1e9b3`; Pi v1.1.0 `abe508e1`; OpenCode v2 `55dde881`, whose manifest declares 2.0.26. Full immutable revisions appear in the links below. Public/default npm 1.18.35 and historical Pi 0.73 are outside this comparison. [V1][V2][V3]

**Conclusion — architectural judgment.** Preserve Renulus’s canonical domain services behind a policy-controlled, client-independent harness boundary. Pi leads as a greenfield toolkit, Hermes as an assembled general agent, and OpenCode v2 as a durable coding platform. Current adoption must be decided by enforceable constraints; neither prior selection nor feature breadth establishes a winner.

The latest user instruction makes data, retrieval, tools, execution and subagents primary, with the application as one client. It reopens foundation evaluation, not implementation permission. Retained constraints still apply; the prior Hermes selection governs implementation but cannot settle this reopened comparison. The following gates translate confirmed requirements into proposed acceptance criteria. [R1][R2][R3][R4][R5]

| Must pass | Required evidence |
| --- | --- |
| Client independence and extensibility | The agent loop, tool registration, retrieval adapters and child orchestration run outside Electron; clients receive explicit progress, result, failure and cancellation contracts. |
| Delivery and ownership | App-managed Windows runtime; no owner-hosted service/inference, doctor-managed GPU/Docker/generative server, or new mandatory generation API. Small bundled CPU OCR/embedding helpers remain allowed. Adopted code and helpers retain licences and provenance. |
| Generation policy everywhere | Only Codex GPT 6.1 Sol/GPT 6 Astra/GPT 6 Luna or OpenCode Go MiMo V2.6 Pro/DeepSeek V4.1 Flash, within the selected subscription. No silent fallback or automatic generative retries; catalogues remain advisory. Apply the same checks to children, summaries and memory extraction. Optional paid retrieval connections remain explicitly enabled and separate. |
| Domain and evidence authority | Preserve Mem0 OSS, Docling/HybridChunker, FastEmbed and LanceDB OSS as reusable services. Local SQLite owns source, learner and assessment records; indexes/transcripts cannot replace that authority. Retrieval enforces revision, rights, currentness and passage/page provenance. |
| Retention and controlled effects | Save conversations by default; offer Archive and explicit temporary mode, with scope inherited by children and derivatives. Demonstrate cancellation, permission mediation, inspect/edit/delete and rebuild; use idempotent canonical mutations. |
| Educational behavior | Connected flows across nephrology, separate Chat/Explain and Test, deterministic reviewed-bank assessment versus generated practice. Coding capability or successful generation does not establish educational quality. |

**Four decisive verified facts.**

1. Renulus’s adapter disables model tools and SDK retries and explicitly avoids general-agent startup. **Implication:** the existing Hermes integration does not establish an active general harness. [R6][R7]
2. Current Hermes documents three client protocols driving the same `AIAgent`; delegation constructs child `AIAgent` instances. **Implication:** an assembled general-agent foundation exists, but this neither proves Renulus policy compliance nor transfers current behavior to its older bundled pin. [H1][H2]
3. Pi’s SDK accepts host-supplied model, settings, session, resource and tool boundaries. CLI MCP requires explicit SDK setup; subagents are an example extension. **Implication:** strong composition contracts, with additional assembly responsibility. [P1][P2][P3]
4. OpenCode v2’s embedded host defaults to in-memory storage and starts suspended-session recovery; that recovery explicitly permits repeated external effects. **Implication:** durable execution requires deliberate retention, generation-policy and idempotency integration. [O1][O2]

**Discriminating criteria — judgments, not a feature tally.**

| Decision being made | Leading fit and tradeoff |
| --- | --- |
| Greenfield best toolkit | **Pi:** explicit host ownership; Renulus supplies the product orchestration and packaging. |
| Best mature general agent | **Hermes:** assembled client/session/delegation lifecycle. “Mature” means assembled scope here, not measured reliability. |
| Best current Renulus adoption path | **Preserve domain services behind a replaceable harness.** Hermes’s Python compatibility and Pi’s explicit host seams are competing advantages; neither has demonstrated all gates. |
| Richest durable coding platform | **OpenCode v2:** embedded service graph and restart machinery; adoption needs an educational reason for that complexity and control of repeated effects. |

Borrow Pi’s host-controlled interfaces, Hermes’s coherent child/session lifecycle, and OpenCode’s durable admission concepts where justified. These are design proposals, not authorisation to transplant implementations wholesale.

Challenge assumptions that SDK equals CLI, “local” equals doctor-ready packaging, saved transcripts equal learner memory, existing integration equals active harness, or restart recovery equals permissible retry/exactly-once effects.

The decisive uncertainty is whether a candidate can enforce policy before **every** model/tool action while retaining canonical authority. Later reviews must establish route/retry control, child scope, retention and Windows delivery. Conformance evidence for those gates would change the conclusion; this source review supplies no runtime or account proof. Relaxing automatic retry requires an explicit user decision.

**Handoff:** `docs/research/2026-10-10-harness-adoption/review-05-decision-criteria.md`. Conclusion: choose controllable boundaries before platform breadth; preserve domain services. Strongest fact: current Renulus deliberately disables model tools, so the Hermes name does not prove harness adoption. Unresolved risk: policy enforcement across auxiliary generation, children and restart recovery.

[R1]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/DECISIONS.md#L15-L33
[R2]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/DECISIONS.md#L39-L61
[R3]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/DECISIONS.md#L142-L152
[R4]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/planning/ARCHITECTURE.md#L45-L63
[R5]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/planning/ARCHITECTURE.md#L128-L144
[R6]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/runtime/hermes.py#L66-L113
[R7]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/runtime/hermes.py#L1-L1
[H1]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/website/docs/developer-guide/programmatic-integration.md#L9-L17
[H2]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/tools/delegate_tool.py#L270-L304
[P1]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/sdk.md#L98-L108
[P2]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/sdk.md#L114-L116
[P3]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/examples/extensions/subagent/README.md#L1-L52
[O1]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/sdk/src/internal/host.ts#L30-L60
[O2]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/session/execution/restart.ts#L23-L61
[V1]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/packaging/runtime/hermes-source.json#L1-L5
[V2]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/package.json#L1-L4
[V3]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/package.json#L1-L5

