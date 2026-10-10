# Renulus backend/harness versus Hermes Agent, Pi and OpenCode v2

2026-10-10. Source inspection against Renulus `528025ff0b22477c12ee1512e0e7d15297a6e888`
and the adopted Hermes revision `af90026aa09949579bd423d24def3d38f743cde0`,
recorded in `packaging/runtime/hermes-source.json:2-4`. Current public Hermes
`main` was independently resolved with `git ls-remote` to
`dce1e9b37581dd62e480a9064dc04a709c2940d3` on October 10, 2026. This review
uses the bundled source for exact reuse analysis, and current official docs and
selected immutable source files for upstream evolution; it is not an exhaustive
diff of every intervening upstream change. References below are repository-relative
`file:line` ranges. Implementation is primary evidence; plans describe intended
behavior separately. No learning profiles, credentials or archives were read.
The focused synthetic runtime tests described below were run without live
inference or an installed app launch. Domain engine tests were inspected only.

## Added comparison baselines

The October 10 extension adds Pi and OpenCode v2 on the original 15 axes.
Two independent source researchers inspected the added harnesses. Their public
source review does not establish installed acceptance, performance or educational
quality; the prior Renulus test result below remains separately scoped.
An independent third subagent audited decisive implementation claims against
the pinned sources. It found no material factual errors; its three wording and
citation refinements were applied, including explicit shell-job cancellation
after an OpenCode restart and external voluntary Pi session sharing.

| Harness | Exact comparison baseline | Version qualification |
| --- | --- | --- |
| Renulus | `528025ff0b22477c12ee1512e0e7d15297a6e888` | Implemented source in this worktree. |
| Hermes | Adopted `af90026aa09949579bd423d24def3d38f743cde0`; selected current sources at `dce1e9b37581dd62e480a9064dc04a709c2940d3` | Pinned adoption plus the previously recorded October 10 upstream inspection. |
| Pi | `earendil-works/pi`, tag `v1.1.0`, revision `abe508e1b89912adde45528136c3221eb69acdd7` | The published package is `@earendil-works/pi-coding-agent` 1.1.0. The older `@mariozechner` package is not this comparison baseline. |
| OpenCode v2 | `anomalyco/opencode`, `v2` branch snapshot `55dde8810d8a859c0a21e42491ae7d5801fb49ef` | `packages/core/package.json` declares 2.0.26. The public changelog and npm default were still 1.18.35 at inspection; no default published v2 release is inferred. |

The Pi package manifest, npm package metadata and Git tag were checked directly.
OpenCode's version is backed by its immutable v2 manifest and `git ls-remote`;
`opencode-ai/2.0.26` was not present in the public npm registry. The public
changelog reports 1.18.35 on October 6, 2026. Sources:
[Pi manifest][pi-manifest], [OpenCode v2 manifest][opencode-v2-manifest],
[OpenCode public changelog][opencode-changelog].

The deeper adoption study also verified a published `@opencode/sdk` 2.0.26
artifact (Effect rc.112, no gitHead), distinct from the inspected v2 branch
(Effect rc.118) and v2.0.26 tag. A nonpublished default CLI v2 does not mean
there are no published v2 SDK artifacts. See
[review03](2026-10-10-harness-adoption/review-03-opencode-runtime.md).
The final accuracy review verified a material startup-order difference: the
published SDK begins recovery before supplied plugins register, while the
inspected branch registers them first. See
[review28](2026-10-10-harness-adoption/review-28-accuracy-audit.md).
The completed thirty-agent [foundation recommendation](2026-10-10-harness-foundation-recommendation.md)
uses these distinctions in its adoption gates.
Pi also includes a separate experimental durable library; the cells below now
distinguish it from agent-core, AgentSession and the CLI subagent example.
See [review10](2026-10-10-harness-adoption/review-10-execution-durability-cancellation.md)
and [review11](2026-10-10-harness-adoption/review-11-canonical-data-authority.md).

## Expanded 15-axis comparison

The two added columns describe the exact source baselines above. **Not identified
in inspected core** is a bounded finding about stock implementation contracts,
not a claim about every extension. Model input, indexed documents, transcript
retention and structured learner memory are separate capabilities.

| Area | Hermes Agent | Our implementation (Renulus) | Pi 1.1.0 | OpenCode v2 — inspected source 2.0.26 | Assessment |
| --- | --- | --- | --- | --- | --- |
| Core execution | AIAgent model → tools → results loop. [loop] | ProviderManager streams generation; product modules orchestrate retrieval, memory and records. [R01] | TypeScript agent-core model/tool/result loop; AgentSession adds resources and conversation lifecycle. Separate experimental pi-durable adds committed submissions, generation and tool tasks. [P03], [P07], [PD01], [PD02] | TypeScript/Effect model/tool loop with durable queued inputs, concurrent local tools and per-session execution coordination. [OC03], [OC04], [OC41] | Renulus currently bypasses the general Hermes loop. |
| Desktop/backend boundary | General agent through desktop, HTTP/SSE, JSON-RPC and ACP. [integration] | Electron-owned Python child; narrow authenticated loopback FastAPI API. [R02] | In-process Node/Bun SDK or JSONL RPC child; host supplies its product UI and domain API. [P07], [P08], [P33] | Electron uses a managed CLI server; terminal/web share typed contracts. ACP and an optional in-process embedded router are implemented. [OC05], [OC06], [OC07], [OC38] | Our API and domain workflow boundary are Renulus-owned. |
| Providers, authentication and model selection | Provider registry, configurable models, credentials and auxiliary routing. [providers] | Two subscriptions/five approved models; own OAuth/DPAPI; deterministic Automatic selection. [R03] | OAuth/API keys and compatible endpoints; explicit/scoped models, saved defaults and available provider defaults. [P09], [P10], [P11] | Broad provider registry, API keys/OAuth, configurable models/variants and optional local discovery. Console, ChatGPT token-sharing and legacy Codex paths are separate. [OC08], [OC09], [OC10], [OC11], [OC13] | Our requested route policy is deliberately narrower. |
| Tools, skills, MCP and delegation | Model-callable tools, skills, MCP and subagents. [tools], [skills] | Tools disabled; actions are application functions. [R04] | File/shell tools and skills; CLI bundles MCP, SDK must add it. Parallel by default with sequential overrides; coding-agent subagents are an example. Separate pi-durable supplies task-owned child conversations; host-defined roles/delegation remain distinct. [PD01] [P04], [P05], [P07], [P12], [P13], [P15], [P47] | Stock shell/file/search/browser tools, skills, MCP tools/prompts/resources and permission-scoped child-session subagents, including background delegation. [OC12], [OC13], [OC14], [OC15], [OC16], [OC42] | Developer skills/control MCP are not product model tools. |
| Streaming, cancellation and recovery | Interrupts, tool progress, retry/fallback and recovery. [loop] | Async deltas, ordered events, cancellation and cleanup; no SDK retries/fallback. [R05] | Streamed session/tool events, abort and queued steering. Transient agent retries default to three with an initial two-second delay; overflow recovery is separate. Separate pi-durable persists work and conservatively classifies interrupted tool replay; generation recovery can still resend. [PD02], [PD03], [PD05], [P07], [P16], [P17], [P18], [P20] | Streaming, fiber cancellation, bounded retries and overflow recovery. Durable execution claims support restart recovery with at-least-once semantics: external effects can repeat. [OC03], [OC04], [OC17], [OC18], [OC41] | Current cancellation is implemented; recovery breadth differs. |
| Context management | Model-aware context engines, usage anchors and lifecycle compression. [context] | Reused compressor; rough estimates; 32,768-token cap; 24,000 trigger; selected-route summary. [R06] | Model-aware compaction uses provider usage plus estimates. Default response reserve 16,384 tokens and retained recent context 20,000 tokens; branch summaries and overrides. [P19], [P20], [P21] | Model-window-aware compaction with provider usage anchors plus estimates; summary/native checkpoints depend on route policy. Unknown windows skip automatic triggering. [OC19], [OC24], [OC43], [OC44] | Our app budget is conservative, not a verified model limit. |
| Reasoning and prompt caching | Provider-specific reasoning replay and cache support. [current-codex], [context] | Text deltas; Codex replay/cache identities stripped; Go session affinity retained. [R07] | Typed thinking/signatures and provider-specific replay/cache options. Eligible cache warming defaults to active runs and makes additional provider requests. [P21], [P22], [P23], [P24] | Compatible model-bound reasoning replay, provider-aware cache hints and session-affinity keys. Actual cache hits/provider capabilities were not measured. [OC20], [OC21], [OC22], [OC24] | Explicit caching/continuity is only partly reused. |
| Documents and OCR | General file extraction and optional hosted extraction/OCR in the pin. | Managed offline Docling/HybridChunker, CPU OCR and passage/page mapping. [R08] | Text/image read tool with resize/truncation; no PDF/OCR pipeline established in that tool. Additional extraction requires tools/extensions. [P25], [P14] | Read sends PDFs/images directly as model file content after capability checks. No local OCR, extracted-passage store or ingestion index established in inspected built-ins. [OC23], [OC24], [OC12] | File/image input does not equal an indexed Library. |
| Retrieval and evidence | Agent-callable web, file and session search. | LanceDB hybrid retrieval, canonical revision/eligibility checks and passage citations. [R09] | File search/read and MCP resources. No canonical corpus, revision checks or passage-citation store established in inspected coding-agent contracts. [P26], [P27], [P13], [P07] | File/web/MCP search and local/Git reference repositories; no Renulus-style canonical passage/revision/rights service or hybrid document index identified in inspected core. [OC12], [OC15], [OC25], [OC26], [OC27], [OC29] | Our evidence rules are application-specific. |
| Learner memory | Curated files plus optional lifecycle-integrated memory providers. [memory-providers] | SQLite facts/outbox; adapted Mem0/Qdrant/FastEmbed; edits/deletion/rebuild. [R10] | Transcripts, compaction summaries and instruction files; no structured learner-fact capture/correction/vector-memory service established in stock contracts. [P28], [P29], [P07], [P19] | AGENTS.md, skills, durable instructions and sessions; no learner-fact extraction, semantic index or correction/suppression service identified in inspected built-ins. [OC12], [OC16], [OC28], [OC29] | Our canonical deduplication is text equality, not semantic consolidation. |
| Conversation persistence and retention | SQLite session/message state. | Own SQLite/backup authority; Case explicit-save/follow-ups temporary. [R11] | Automatic local JSONL session trees; resume/fork and no-session/in-memory modes. Compaction retains transcript entries. Separate experimental pi-durable supports SQLite/JSONL task and document storage; retirement does not establish transcript purge. [PD01], [PD04] Install telemetry and opt-in analytics have separate settings; voluntary public session sharing is an external workflow. [P29], [P30], [P31], [P32], [P38], [P41] | CLI uses file-backed SQLite for sessions and queued work; fork/import/export/deletion. Embedded SDK defaults to in-memory storage. Historical event-log retention is optional. [OC07], [OC29], [OC30], [OC31], [OC32], [OC37], [OC40] | Saved-by-default Case/Archive migration remains pending. |
| Assessment and generated practice | General agent facilities, without our reviewed-bank/scoring contracts. | Versioned bank, deterministic scoring, separate practice; max five generated items. [R12] | General generation and extension APIs; no reviewed-bank, answer-key/scoring or saved-test contract established in inspected tools/SDK. [P07], [P26] | General custom-agent/tool workflows; no reviewed educational bank, versioned answer keys, deterministic scoring or saved-test contract identified in inspected core. [OC12], [OC29], [OC33] | Saved Test versions, final submission/timing and larger batches remain planned. |
| Personalisation and study planning | General cross-session memory/recall. | Deterministic mistake-first/topic-coverage plan; latest 2,000 evidence rows. [R13] | Instructions, prompts, skills, settings and extension state; no built-in curriculum/mastery/study-plan contract established. [P28], [P14], [P09], [P07] | Custom agents, skills and instructions; coding Plan mode constrains edits. No learner-goal, mastery or adaptive study-planner service identified in inspected core. [OC16], [OC28], [OC29], [OC33] | Projects and generated daily suggestions remain new work. |
| Background scheduling | General recurring/one-shot/event-triggered agent or script jobs. | Opt-in Updates checks while app runs, durable job state and bounded retries. [R14] | No recurring-job contract established in coding-agent SDK/CLI. Hosts/extensions arrange recurrence; pi-durable is a separate task library. [P33], [P07], [P34] | Background jobs retain notification markers; interrupted sessions/subagents can resume, but running shell jobs are cancelled on restart. Periodic reference refresh exists; no calendar/cron contract identified in the inspected Job API. [OC13], [OC18], [OC27], [OC34], [OC45] | Current Updates scheduling is not nightly test generation. |
| Upstream maintenance | Pinned source plus current upstream checks; Mem0 has moved to external plugin. [mem0-catalogue], [memory-providers] | Recorded Hermes pin/patches; memory imports the older backend path. [R15] | MIT toolkit, pinned here to released 1.1.0. Managed installer pins transitive dependencies; npm-only installation differs. Examples and separate packages need their own assessment. [P01], [P02], [P36], [P37] | MIT, separate core/server/protocol/client/SDK packages; v2 changes integration contracts. Pinned v2 branch declares 2.0.26; default CLI was 1.18.35. SDK 2.0.26 is published, with dependency/source identity requiring separate proof. [OC01], [OC02], [OC35], [OC36] | Upstream refresh requires explicit compatibility work. |

The [Pi evidence note](2026-10-10-pi-harness-evidence.md) and
[OpenCode v2 evidence note](2026-10-10-opencode-v2-harness-evidence.md) preserve
the exact source ranges and qualifications behind the new cells. The detailed
Renulus/Hermes tables below preserve the implementation analysis and its limits.
R01–R15 link to each row's principal Renulus source; its additional ranges
are recorded below. Pi's install telemetry defaults to enabled while analytics
defaults to disabled; voluntary public session sharing is separate. A blanket
claim that all Pi builds are telemetry-free is not supported [P38], [P39], [P41].
OpenCode's standard CLI database and embedded SDK in-memory default are distinct;
optional historical event retention is separate from session/message persistence
[OC07], [OC29], [OC30], [OC32].

[R01]: /C:/Users/karol/.codex/worktrees/a11f/repo/runtime/renulus/runtime/manager.py:399
[R02]: /C:/Users/karol/.codex/worktrees/a11f/repo/runtime/renulus/server.py:19
[R03]: /C:/Users/karol/.codex/worktrees/a11f/repo/runtime/renulus/runtime/policy.py:12
[R04]: /C:/Users/karol/.codex/worktrees/a11f/repo/runtime/renulus/runtime/hermes.py:81
[R05]: /C:/Users/karol/.codex/worktrees/a11f/repo/runtime/renulus/runtime/manager.py:399
[R06]: /C:/Users/karol/.codex/worktrees/a11f/repo/runtime/renulus/runtime/context.py:13
[R07]: /C:/Users/karol/.codex/worktrees/a11f/repo/runtime/renulus/runtime/hermes.py:83
[R08]: /C:/Users/karol/.codex/worktrees/a11f/repo/runtime/renulus/knowledge/engines.py:138
[R09]: /C:/Users/karol/.codex/worktrees/a11f/repo/runtime/renulus/knowledge/engines.py:454
[R10]: /C:/Users/karol/.codex/worktrees/a11f/repo/runtime/renulus/memory/engine.py:67
[R11]: /C:/Users/karol/.codex/worktrees/a11f/repo/runtime/renulus/storage/database.py:17
[R12]: /C:/Users/karol/.codex/worktrees/a11f/repo/runtime/renulus/assessment/repository.py:76
[R13]: /C:/Users/karol/.codex/worktrees/a11f/repo/runtime/renulus/study/service.py:15
[R14]: /C:/Users/karol/.codex/worktrees/a11f/repo/runtime/renulus/updates/scheduling.py:103
[R15]: /C:/Users/karol/.codex/worktrees/a11f/repo/packaging/runtime/hermes-source.json:2

[P01]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/package.json#L1-L4
[P02]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/README.md#L13-L21
[P03]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/agent/src/agent-loop.ts#L163-L320
[P04]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/agent/src/agent.ts#L243-L253
[P05]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/agent/src/agent-loop.ts#L508-L522
[P06]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/sdk.ts#L195-L205
[P07]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/sdk.md#L26-L56
[P08]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/rpc.md#L1-L18
[P09]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/models.md#L3-L35
[P10]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/providers.md#L1-L18
[P11]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/model-resolver.ts#L622-L704
[P12]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/extensions/index.ts#L1-L14
[P13]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/mcp.md#L1-L3
[P14]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/skills.md#L3-L7
[P15]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/examples/extensions/subagent/README.md#L1-L52
[P16]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/agent-session.ts#L2431-L2443
[P17]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/agent-session.ts#L3705-L3712
[P18]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/settings-manager.ts#L1010-L1028
[P19]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/compaction/compaction.ts#L120-L141
[P20]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/agent-session.ts#L3003-L3046
[P21]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/settings.md#L9-L21
[P22]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/ai/src/types.ts#L215-L230
[P23]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/ai/src/api/openai-codex-responses.ts#L547-L596
[P24]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/cache-warmer.ts#L204-L250
[P25]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/tools/read.ts#L90-L156
[P26]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/tools/index.ts#L118-L179
[P27]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/tools/grep.ts#L50-L78
[P28]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/configuration.md#L7-L47
[P29]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/session-manager.ts#L975-L985
[P30]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/session-manager.ts#L1793-L1805
[P31]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/sessions.md#L5-L52
[P32]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/session-format.md#L1-L30
[P33]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/cli-integration.md#L1-L18
[P34]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/README.md#L78-L113
[P35]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/security.md#L1-L25
[P36]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/LICENSE#L1-L21
[P37]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/README.md#L168-L179
[P38]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/settings.md#L162-L169
[P39]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/settings-manager.ts#L1164-L1175
[P40]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/telemetry.ts#L1-L12
[P41]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/README.md#L58-L69
[P42]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/ai/src/providers/opencode-go.ts#L1-L22
[P43]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/model-runtime.ts#L987-L1026
[P44]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/ai/src/auth/oauth/openai-codex.ts#L17-L35
[P45]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/compaction.md#L25-L41
[P46]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/provider-attribution.ts#L36-L76
[P47]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/sdk.md#L114-L116

[OC01]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/package.json#L1-L41
[OC02]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/package.json#L3-L95
[OC03]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/session/runner/llm.ts#L54-L296
[OC04]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/session/runner/step.ts#L77-L170
[OC05]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/server/src/routes.ts#L52-L141
[OC06]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/desktop/src/main/service/background-service.ts#L32-L91
[OC07]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/sdk/src/internal/host.ts#L28-L73
[OC08]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/plugin/provider.ts#L1-L68
[OC09]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/plugin/provider/openai.ts#L22-L228
[OC10]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/plugin/provider/chatgpt.ts#L94-L99
[OC11]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/plugin/provider/opencode.ts#L101-L177
[OC12]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/plugin/internal.ts#L216-L270
[OC13]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/tool/plugin/subagent.ts#L29-L200
[OC14]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/permission.ts#L87-L111
[OC15]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/mcp/index.ts#L113-L138
[OC16]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/config/plugin/skill.ts#L77-L125
[OC17]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/session/runner/retry.ts#L31-L91
[OC18]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/session/execution/restart.ts#L23-L61
[OC19]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/session/compaction.ts#L195-L250
[OC20]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/session/runner/to-llm-message.ts#L153-L229
[OC21]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/ai/src/cache-policy.ts#L1-L67
[OC22]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/session/affinity.ts#L3-L8
[OC23]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/tool/plugin/read.ts#L39-L185
[OC24]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/session/model-request.ts#L122-L301
[OC25]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/tool/plugin/websearch.ts#L20-L64
[OC26]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/tool/plugin/webfetch.ts#L12-L37
[OC27]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/reference.ts#L51-L112
[OC28]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/config/plugin/instruction.ts#L23-L77
[OC29]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/session/sql.ts#L22-L176
[OC30]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/bus.ts#L175-L203
[OC31]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/session.ts#L367-L377
[OC32]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/cli/src/database-path.ts#L4-L13
[OC33]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/plugin/plan.ts#L14-L95
[OC34]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/job.ts#L95-L207
[OC35]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/services/www/src/docs/content/migrate-v1.mdx#L8-L39
[OC36]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/LICENSE#L1-L21
[OC37]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/session/transfer.ts#L38-L143
[OC38]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/services/www/src/docs/content/cli/acp.mdx#L80-L87
[OC39]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/protocol/src/groups/session.ts#L362-L378
[OC40]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/cli/src/server-process.ts#L100-L109
[OC41]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/session/execution.ts#L76-L140
[OC42]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/plugin/agent.ts#L76-L118
[OC43]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/session/compaction.ts#L868-L923
[OC44]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/plugin/provider/chatgpt.ts#L295-L321
[OC45]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/session/execution/restart.ts#L101-L135

## Central finding

Renulus has its own application orchestration and selectively reuses Hermes
components. It does not instantiate `AIAgent`, run `run_conversation`, or enter
the Hermes tool loop. The adapter states this boundary explicitly and supplies
no tools. Learn, Cases, practice, memory extraction and compaction share the
Renulus `ProviderManager` seam. This is a specialised learning harness with real
Hermes reuse, rather than the full Hermes agent behind a different renderer
(`runtime/renulus/runtime/hermes.py:1,20-45,65-103,129-143`;
`runtime/renulus/runtime/manager.py:38-55,121-131,385-419`;
`runtime/renulus/generation.py:1-15`).

The original architecture called for reusing the agent loop and not building
another loop (`docs/planning/ARCHITECTURE.md:27-35,324-329`). The delivered F0
record explicitly documents the narrower transport reuse
(`docs/implementation/runtime-evidence.md:23-30`). Renulus has not implemented
a competing autonomous tool loop; it owns application workflow orchestration.
The implementation and the stronger original agent-reuse wording should be
reconciled if future work depends on general Hermes agent behavior.

## Core harness comparison

| Area | Hermes implementation | Implemented Renulus behavior | Assessment and primary evidence |
| --- | --- | --- | --- |
| Execution core | `AIAgent` admits a turn and enters the model/tool/result loop. It owns prompt assembly, tool dispatch, retries, session lifecycle and memory hooks. | Custom `ProviderManager.events()` makes a streamed generation request, optionally preceded by compaction. Product modules orchestrate retrieval, persistence and memory. | Largest functional difference. Exact upstream seam: `upstream/hermes/agent/turn_facade.py:22-45`; downstream: `runtime/renulus/runtime/manager.py:399-531`. Current [agent loop documentation][loop] describes the same execution boundary. |
| Local application boundary | General integration protocols drive the same agent: ACP, TUI JSON-RPC and HTTP/SSE. | Electron owns a Python child running a narrow FastAPI product API, with explicit profile, loopback binding, per-session token, host/origin checks, typed errors and module migrations. Reuses upstream child teardown/startup modules. | Appropriate product boundary, but it is Renulus's API and not the stock Hermes gateway. `runtime/renulus/server.py:19-63,85-125`; `apps/desktop/electron/backend.ts:18-49,75-82`; [Hermes integration protocols][integration]. |
| Providers and account ownership | Shared provider registry/resolver, plugins, configuration/environment precedence, API modes and auxiliary routing. | Exactly two selected subscriptions and five allowed model IDs; own OAuth/PKCE/OIDC connection flow and profile-bound Windows DPAPI records. Actual Hermes Responses/Chat Completions request builders are reused. | Policy is deliberately narrower. Own authentication remains separate from request-builder reuse. `runtime/renulus/runtime/policy.py:12-22`; `runtime/renulus/runtime/auth.py:71-155,186-266`; `runtime/renulus/runtime/protected.py:60-95`; `runtime/renulus/runtime/hermes.py:65-103`; [upstream resolution][providers]. |
| Automatic model selection | General configurable provider/model selection and optional fallback machinery. | Explicit choice, then saved choice, then first catalogue-listed allowed model; if none is listed, the first allowed model is attempted. Failures do not choose a replacement provider/model. | Automatic is deterministic routing, not a task/capability-aware selector. `runtime/renulus/runtime/manager.py:309-327`; `runtime/renulus/runtime/policy.py:12-15`; [upstream resolution][providers]. |
| Tools, skills, MCP and delegation | Model-callable tools, on-demand skills, MCP integrations and subagents are available through the general agent. | Generation strips tool schemas and rejects automation responses. Search, memory and assessment actions are application functions. There is no active Renulus runtime skill loader/MCP dispatcher/subagent planner. | Deliberate restriction; vendoring source does not activate its capabilities. Repository development skills and the developer Renulus control MCP are not model tools inside the product. `runtime/renulus/runtime/hermes.py:81,94,98-99,129-143`; `runtime/renulus/runtime/policy.py:53-59`; [tools][tools] and [skills][skills]. |
| Streaming and cancellation | Agent loop supports interruptible calls, tool progress, conversation recovery and configurable retry/fallback paths. | Async SDK deltas, ordered application events, per-run cancellation, pending-task/iterator cleanup, connection-change checks and redacted errors. SDK automatic retries are disabled. | Core cancellation is implemented; broad recovery/tool steering is not inherited. No retry/fallback is a deliberate policy choice, not evidence of a broken integration. `runtime/renulus/runtime/hermes.py:105-151`; `runtime/renulus/runtime/manager.py:299-307,399-574`; [agent loop][loop]. |
| Context and compaction | Context engines, configurable/model-aware windows, provider usage anchors and compression integrated into the agent lifecycle. | Reuses `ContextCompressor`, overrides its summary dispatch onto the same selected approved route and keeps results volatile. Uses a 32,768-token application budget, 24,000-token trigger and 4,096 output reservation, with rough estimation. | Real reuse, but no verified model-window capacity or provider usage anchor in this adapter. The conservative application cap may leave available context unused. Summary failure preserves inputs and blocks primary generation. `runtime/renulus/runtime/context.py:13-15,53-105,125-152`; `runtime/renulus/runtime/manager.py:360-383,462-494`; [current context implementation][context]. |
| Reasoning and caching | Provider transports support reasoning replay, prompt-cache identities and provider-specific context behavior; the agent maintains conversation state. | Text-answer deltas only; encrypted reasoning replay is disabled. Codex prompt-cache keys/retention and native context-management fields are removed. Go's session-affinity header is retained, with stable IDs for persistent entities. | Explicit provider caching/continuity machinery is only partly reused. Do not infer that provider-side automatic caching is absent. `runtime/renulus/runtime/hermes.py:83-88,113-151`; `runtime/renulus/runtime/manager.py:329-336`; `upstream/hermes/agent/transports/codex.py:25-51`; [context/caching][context]. |
| Route verification | General provider execution and credential/transport resolution. | Checks requested model allowlist and sends exactly that ID. Records safe provider-reported model IDs; a different reported ID still yields a completed event while not granting verified-capability evidence. | Request policy is stronger than response enforcement. A response model mismatch is observable but accepted. `runtime/renulus/runtime/manager.py:515-526`; `tests/runtime/test_response_identity.py:76-87`. This is an implementation behavior, not evidence of an actual provider substitution. |

## Current upstream evolution

Four inspected current files differ from the bundled baseline after normalising
line endings: `agent/turn_facade.py`, both reused transport files and
`agent/context_compressor.py`. The compressor also includes Renulus's recorded
local patch, so its inequality alone is not a measure of upstream divergence.
The current turn facade still delegates to `agent.conversation_loop.run_conversation`.
No upstream update or replacement was performed. Immutable sources:
[turn facade][current-turn], [Responses transport][current-codex],
[Chat Completions transport][current-chat], [compressor][current-context].

Current Hermes no longer exposes the adopted
`plugins/memory/mem0/_backend.py` source path. Its [Mem0 catalogue record][mem0-catalogue]
points to the external `mem0ai/mem0` repository, revision
`43849c6e9d4d773b83a8144b6373aedc67241a5d`,
`integrations/hermes-plugin-mem0`, plugin version `1.3.0`. Current
[memory-provider documentation][memory-providers] confirms catalog installation.
Renulus loads the older backend file directly
(`runtime/renulus/memory/engine.py:67-82`). A future source refresh therefore
needs an explicit adapter/provenance migration; dropping a new upstream tree
in place would not preserve this import. This finding does not invalidate the
working pinned backend or approve the external plugin's default runtime setup.

Renulus has built a substantial application domain layer around selected Hermes
seams. Its document library, learner records, assessment rules and study planning
are Renulus implementations. Learner memory reuses Hermes's Mem0 OSS backend
operations, but replaces initialization and does not adopt the unrestricted
turn-sync plugin. Those distinctions matter when assessing how much of Hermes
is actually reused (`runtime/renulus/memory/engine.py:1-5,67-82,117-148`).

## Domain comparison

| Area | Pinned Hermes implementation | Implemented Renulus behavior | Limits, differences and remaining work | Primary evidence |
| --- | --- | --- | --- | --- |
| Documents and OCR | General `read_file` extraction: standard-library DOCX/XLSX/notebooks; optional `firecrawl-anydoc` for PDF and additional formats. Scanned PDF handling can use configured hosted OCR, otherwise returns a missing-content warning. | Docling conversion and HybridChunker, offline FastEmbed embeddings, CPU RapidOCR ONNX models, structured passages and page/region locators. Text/Markdown, PDF/images and selected Office inputs have implemented extraction paths. | OCR confidence is unavailable. Durable images can preserve an original and become ready with no readable passages; ready does not universally mean searchable. General CSV/HTML/XML adapters remain planned. Extraction does not establish embedded-reader support or extraction quality across real clinical documents. | Hermes `upstream/hermes/tools/read_extract.py:1-4,30-38,153-208`; Renulus `runtime/renulus/knowledge/engines.py:138-224,262-290,298-319,345-386`; gaps `docs/planning/DESIGN_C_IMPLEMENTATION_SPEC.md:343-346`. |
| Library RAG and citations | File extraction and session full-text search are general agent facilities; they are not the canonical Library/revision/passages service Renulus implements. | Native LanceDB FTS plus vector retrieval, reciprocal-rank fusion, canonical revision prefiltering and post-search SQLite rechecks. Citation results carry passage text, source/revision IDs, locators, rights and original-file access. Imports publish an active revision only after extraction and index preparation. | No retrieval-quality benchmark is established by these source paths. A source with any replaced topic is conservatively excluded until passage-level replacement masks exist. Current-only retrieval adds reviewed/final/latest/date checks; ordinary retrieval has weaker currency requirements. This is an application RAG service, not evidence that Hermes itself executes a retrieval tool loop. | Hermes `upstream/hermes/hermes_state_search.py:1-4`; Renulus `runtime/renulus/knowledge/engines.py:454-463`; `runtime/renulus/knowledge/repository.py:299-370,509-592`. |
| Memory storage and engine reuse | Bounded curated `MEMORY.md`/`USER.md` plus pluggable providers; Mem0 supports platform, self-hosted HTTP and in-process OSS backends. Its OSS constructor rebuilds changed-dimension collections and constructs its own configuration. | SQLite `memory_facts`, revisions and source links are authoritative. A subclass replaces Hermes OSSBackend initialization with explicit owned Mem0 history/Qdrant paths, offline 384-dimensional BGE embeddings and the selected subscription generation seam. Inherited add/search operations are used. | Renulus does not instantiate the full Hermes Mem0MemoryProvider lifecycle. Mem0/Qdrant is a derivative, not the learner-record authority. Its BM25 helper is disabled and memory search uses `rerank=False`; document retrieval has a separate hybrid index. | Hermes `upstream/hermes/tools/memory_tool_store.py:1-4,89-105`; `upstream/hermes/plugins/memory/mem0/_backend.py:19-26,44-55,114-155,158-180`; Renulus `runtime/renulus/memory/schema.sql:1-27`; `runtime/renulus/memory/engine.py:101-168`. |
| Automatic learner capture | Mem0 plugin asynchronously syncs user/assistant turns, truncates individual messages (default 450 characters), and can skip a turn when a prior sync remains busy. Recall has a short wait and can return no context. | Durable SQLite outbox scans eligible committed learning evidence, validates producer scope/fingerprint, claims jobs, cancels late results and stores failures for explicit retry. Structured interest/assessment records need no inference; general points use real Mem0 extraction through the scoped provider seam. | Extraction is a remote generative operation when required, despite local storage. Each extraction uses a fresh transient index and accepts ADD results; canonical deduplication is normalized text equality plus kind/topic, not semantic reconciliation across existing learner records. An empty extracted list can still complete a job. Failed jobs need retry; `automatic_capture=True` is not a claim that every job succeeded. | Hermes `upstream/hermes/plugins/memory/mem0/__init__.py:40-43,291-322`; Renulus `runtime/renulus/memory/engine.py:179-186`; `runtime/renulus/memory/repository.py:70-89,169-260,271-346`; `runtime/renulus/memory/service.py:160-230,312-322`. |
| Correction, deletion and index repair | Hermes exposes provider update/delete operations and backend configuration, with curated-file safeguards. These are general memory operations. | Expected revisions protect canonical edits; suppression prevents recapture from corrected/deleted sources. Edits invalidate the derived index; purge closes the engine, removes generations and truncates WAL. Rebuild stages a fresh Mem0 generation and switches only if the canonical epoch is unchanged. Recall resolves engine IDs back to the current SQLite revision. Library also rebuilds staged Lance generations from canonical eligible passages. | Whole-memory rebuilds and synchronous recall-triggered repair can become costly with growth; this inspection provides no performance measurement. Cleanup may report `purge_pending`; that state must not be interpreted as physical erasure completed. Canonical edit history is intentionally retained unless separately purged; derivative engine history/messages are removed. | Hermes `upstream/hermes/plugins/memory/mem0/_backend.py:32-38`; Renulus `runtime/renulus/memory/repository.py:122-167`; `runtime/renulus/memory/service.py:74-104,233-310`; `runtime/renulus/knowledge/repository.py:103-149`. |
| Canonical records and recovery | Hermes SessionDB owns agent session metadata, transcripts, model configuration and FTS, with WAL and compression-parent chains. | Renulus has its own application SQLite authority with foreign keys, checked atomic migrations, secure-delete settings, shared evidence and deletion ledger. Canonical exports allowlist learning tables/preferences, omit credentials/connection state/derived indexes, and restore through deletion reconciliation. Original bytes require an appropriate full backup. | Source-of-truth reuse is limited: domain records are not Hermes SessionDB records. A fresh restore cannot know deletions that happened after an old backup. JSON export omits originals and structured extraction JSON. Schema/table/original-format allowlists need coordinated migration for the new C records. | Hermes `upstream/hermes/hermes_state.py:2-5`; Renulus `runtime/renulus/storage/database.py:17-58,79-111`; `runtime/renulus/storage/backup.py:19-45,59-97,177-204,262-316`; migration gaps `docs/planning/DESIGN_C_IMPLEMENTATION_SPEC.md:352-355`. |
| Reviewed assessments | The inspected upstream memory/session/file services provide general agent facilities; the reviewed content, scoring and learning-evidence contracts here are Renulus services. | Pins question/key/family versions and snapshots; hides keys before commit; uses transactional idempotency, deterministic option comparison and separate fresh/assisted/repeat buckets. Assistance and exposure are durable. Source/content changes can block new answers while preserving history. | Existing `mode` means reviewed/generated, not Study/Test. A session is a quiz run and an attempt is one committed question answer. Saved tests and immutable test versions, durable unsubmitted Test choices, final submission/timing and the new Test assistance policy remain C work. Structural content review status does not establish independent human clinical validation. | `runtime/renulus/assessment/schema.sql:1-58`; `runtime/renulus/assessment/repository.py:76-132,178-220,251-329,352-380`; planned changes `docs/planning/DESIGN_C_IMPLEMENTATION_SPEC.md:347-351,598-678`. |
| Generated practice | General generation could be orchestrated using agent capabilities; the typed practice repository, pinned generated keys and assessment separation are Renulus additions. | Scoped generation can retrieve eligible Library passages, validate JSON/count/source indices and recheck revisions before publishing. Persistent ordinary practice has separate generated sessions/items/attempts; case-derived practice remains volatile. | Default three, maximum five questions. Current publication starts a practice session directly. Validation proves shape and cited-index bounds, not that a generated key/rationale is correct or supported by its citation. Saved Ready tests, 10/20-question batches, user test import/refinement, chat-to-test identity and nightly tests remain planned. | `runtime/renulus/assessment/generated_contracts.py:9-14`; `runtime/renulus/assessment/generated_repository.py:114-153,175-185,228-255`; `runtime/renulus/assessment/generated_streaming.py:86-99,194-231`; `runtime/renulus/assessment/migrations/002_generated.sql:1-29`; C tickets `docs/planning/DESIGN_C_IMPLEMENTATION_SPEC.md:678-752`. |
| Study, progress and personalization | Hermes has general memory and cron primitives; curriculum goals, reviewed-question progress and study scheduling are Renulus-specific domain logic. | Global goals and tracks, deterministic mistake-first then topic-coverage planning, manual activity changes, resume suggestions and reviewed-result buckets. Conversations are explicitly treated as interest rather than mastery. | This is rule-based adaptation, not model-generated daily personalization or a measured mastery model. `StudyService.evidence()` reads only the latest 2,000 evidence rows, so its progress/planning view can omit older records as history grows. Projects, scoped project goals and daily generated suggestions are new C work. | Hermes `upstream/hermes/cron/jobs.py:1-2`; Renulus `runtime/renulus/study/service.py:15-25,77-105,142-206,208-234`; plans `docs/planning/DESIGN_C_IMPLEMENTATION_SPEC.md:325-338,483-502,548-561`. |
| Case retention and attachments | General transcripts/document caching exist upstream; Renulus adds explicit case ownership, synthetic teaching stages, saved originals and scoped educational handoffs. | New sessions live in memory. Explicit Save writes a guarded current snapshot, permitted user/assistant messages and originals. An edited/follow-up saved case becomes temporary again. Delete records a tombstone; no-save extraction uses bounded byte streams and excludes case payloads from Library indexing and learner capture. | Material mismatch with the later confirmed decision: saved-by-default conversations and Archive are not implemented by this Case path. Saved-case Explain/practice handoffs are still temporary. Passing the old no-save tests proves the old contract, not completion of C retention migration. | Hermes `upstream/hermes/gateway/platforms/base.py:1529-1547`; Renulus `runtime/renulus/cases/repository.py:33-57,218-239,306-346,356-386,431-470`; `runtime/renulus/knowledge/engines.py:298-319`; `runtime/renulus/memory/models.py:15-19`; confirmed target/gap `docs/planning/DESIGN_C_IMPLEMENTATION_SPEC.md:40,325,334-336,448-465`. |
| Updates and source currency | Hermes's general cron and file/search facilities are reusable primitives; Renulus implements the publication identity and review-state domain. | Source-register link checks, explicitly tracked publication byte digests, literature metadata checks, opt-in app-running scheduling, dated failures, evidence-backed review journal and affected-version flags. Reviewed exact-source changes propagate to Library metadata through a durable seam. | Link/digest changes mean review needed, not automatic determination of the latest clinically correct edition. Link checks cannot discover a same-URL body change unless that publication is tracked for digests. Reviewer is learner or assistant; reviewed does not imply independent human review. This does not supply the planned nightly generated tests. | Hermes `upstream/hermes/cron/jobs.py:1-2`; Renulus `runtime/renulus/updates/service.py:38-61,96-150`; `runtime/renulus/updates/publications.py:56-66,96-123`; `runtime/renulus/updates/reviews.py:22-58,84-125`; `runtime/renulus/updates/scheduling.py:1,103-144`; `runtime/renulus/updates/impact.py:13-26,46-61`. |

## Renulus runtime verification from the initial comparison

On the inspected Renulus commit, this bounded existing-test selection completed:

`tests/runtime/test_hermes_provenance.py`,
`tests/runtime/test_images_context.py`, and
`tests/runtime/test_response_identity.py`.

Result: **37 passed, 1 failed in 16.14 seconds**. The existing shared public
Python environment was used with this worktree's runtime explicitly selected,
bytecode/cache writing disabled and fresh synthetic test state at
`C:/Renulus/scratch/backend-comparison-20261010-a11f`. Requests used synthetic
HTTP transports; no real subscription generation was attempted. This selection
checks actual Hermes/SDK conversion, compaction/cancellation, source provenance
and route metadata; it is not full backend, installed-app or engine acceptance.

The failing test is
`test_inference_auth_failure_invalidates_catalogue_without_image_claim`
at `tests/runtime/test_images_context.py:314`. A synthetic Go authentication
rejection correctly becomes `authentication_required` and clears catalogue
and observed capability data. However, `_model_status()` uses presence of the
retained connection record to report `availability=available`, even in that
authentication-failed state. The test expects `availability=unknown`.
The primary connection status and the model availability disagree
(`runtime/renulus/runtime/manager.py:90-109,556-559`). No implementation or
test expectation was changed by this research request.

The separate response-identity tests also pass while explicitly asserting that
a differing provider-reported model ID is accepted as a completion. Their
success confirms current behavior; it does not prove enforcement of response
model identity (`tests/runtime/test_response_identity.py:76-87`).

## Domain test evidence (inspected only)

These are descriptions of test code, not fresh passing results. Previously
recorded installed/live receipts need their own bounded verification; their
presence in documentation does not extend what a synthetic test proves.

| Test evidence | Meaning and limitation |
| --- | --- |
| `tests/knowledge/test_repository.py:39-44,51-64,123-159` | Exercises real LanceDB behavior and canonical/race/rebuild rules with synthetic extraction and embeddings; does not prove Docling or embedding quality. |
| `tests/knowledge/test_offline_engines.py:20-34,64-76,97-117` | Requires an explicit provisioned offline profile, otherwise skips. Exercises actual text/PDF/image engines, source locators and retrieval on simple synthetic inputs; not a representative clinical-corpus quality study. |
| `tests/memory/test_mem0_real.py:35-67,74-120,126-155` | Requires offline assets/packages, otherwise skips. Checks actual Mem0/QdrantLocal/FastEmbed, correction/deletion/history/restart. The extraction test uses a synthetic provider response; it proves scoped plumbing, not a live subscription or accuracy of generated memories. |
| `tests/cases/test_retention.py:122-153,197-227,335-361`; `tests/cases/test_offline_attachment_flow.py:115-120,193-202` | Proves explicit-save/volatile-follow-up/tombstone semantics and conditional actual no-payload-write attachment extraction. Old retention success would not satisfy saved-by-default C behavior. |
| `tests/assessment/test_assessment.py:224-269`; `tests/assessment/test_generated.py:89-171`; `tests/assessment/conftest.py:19-35` | Checks scoring separation, atomicity, assistance, invalid generation and no-save rules with a synthetic content adapter/provider. Does not establish exam coverage or validity of generated questions. |
| `tests/study/test_today_journey.py:37-74`; `tests/study/test_study.py:70`; `tests/updates/test_updates.py:10-33`; `tests/updates/test_review_currency.py:47-153`; `tests/updates/test_scheduling.py:69-140` | Checks deterministic study continuity, mocked source-change/review identity and scheduling rules. These tests do not verify today's external publication state or educational effectiveness. |

## Actionable interpretation for integration

- Preserve the canonical/derived split and scope checks when extending Hermes
  reuse. Calling this an unchanged Hermes memory implementation would conceal
  the restricted initialization, evidence outbox and custom record authority.
- Prioritize the already specified C migration: saved-by-default cases, projects,
  saved-test/version identity, final Test submission/timers, larger generated
  batches and nightly tests. They are concrete missing flows, not UI-only work
  (`docs/planning/DESIGN_C_IMPLEMENTATION_SPEC.md:325-355`).
- Treat semantic memory consolidation, the 2,000-row Study evidence cap and
  whole-index rebuild cost as inspectable engineering limitations. Their severity
  needs requirements/performance evidence; do not silently label them failed
  production behavior.
- Report ready Library originals, ready retrieval indexes, completed memory
  captures and reviewed sources separately. These states have different meaning,
  and syntactic validation alone cannot establish clinical or educational quality.

Core engineering priorities from this review are recommendations, not new
confirmed requirements: resolve contradictory post-auth model availability;
decide how response model identities/aliases should be verified; adopt measured
token usage where the approved routes provide it; and account for the Mem0
source relocation before an upstream refresh. If autonomous educational tools
are desired later, evaluate the existing Hermes loop behind a narrow product
tool allowlist while retaining Renulus's canonical records and scope controls.
This review authorises no such implementation and adds no new dependencies.

## Public primary sources

These pages were inspected on October 10, 2026. Moving documentation supplements
the immutable source comparison; it is not itself an installed-functionality test.

[loop]: https://hermes-agent.nousresearch.com/docs/developer-guide/agent-loop
[integration]: https://hermes-agent.nousresearch.com/docs/developer-guide/programmatic-integration
[providers]: https://hermes-agent.nousresearch.com/docs/developer-guide/provider-runtime
[context]: https://hermes-agent.nousresearch.com/docs/developer-guide/context-compression-and-caching
[tools]: https://hermes-agent.nousresearch.com/docs/user-guide/features/tools
[skills]: https://hermes-agent.nousresearch.com/docs/user-guide/features/skills
[memory-providers]: https://hermes-agent.nousresearch.com/docs/user-guide/features/memory-providers
[mem0-catalogue]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/plugin-catalog/mem0.yaml
[current-turn]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/agent/turn_facade.py
[current-codex]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/agent/transports/codex.py
[current-chat]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/agent/transports/chat_completions.py
[current-context]: https://github.com/NousResearch/hermes-agent/blob/dce1e9b37581dd62e480a9064dc04a709c2940d3/agent/context_compressor.py
[pi-manifest]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/package.json
[opencode-v2-manifest]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/package.json
[opencode-changelog]: https://opencode.ai/changelog

[PD01]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/README.md
[PD02]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/submissions.ts#L53-L175
[PD03]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/tool.ts#L85-L116
[PD04]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/types.ts#L708-L724
[PD05]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/generation.ts#L184-L209

