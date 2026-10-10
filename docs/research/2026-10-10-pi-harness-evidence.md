# Pi harness evidence for the Renulus comparison — 2026-10-10

Research scope: the released **Pi coding agent and its agent-core/pi-ai toolkit**,
not Raspberry Pi, a community fork, or capabilities provided by a host such as
OpenClaw. This note supplies the Pi column for the existing
[Renulus/Hermes comparison](2026-10-10-backend-harness-comparison.md).
It records source-level behavior; no application, provider inference or tests
were run. It does not propose a foundation switch or adopt dependencies.

## Identity and frozen comparison version

Canonical repository: **earendil-works/pi**, historically badlogic/pi-mono.
The current npm package is **@earendil-works/pi-coding-agent**. Its package
manifest identifies version **1.1.0** [P01]; the root overview names the
coding-agent, agent-core, pi-ai and separate durable packages [P02].
The GitHub [1.1.0 release][release] is dated **October 7, 2026** and was marked
latest when inspected on October 10. The public npm registry's `latest` tag
also resolved to 1.1.0; its publication time was
**2026-10-07T22:16:26.802Z** [npm-metadata]. The npm publication time and GitHub
release creation time are separate events.

Immutable comparison pin: **v1.1.0 → abe508e1b89912adde45528136c3221eb69acdd7**,
resolved using public `git ls-remote` and corroborated by the release page.
All comparative implementation links below use this full commit, not main.
Main was separately observed at
`42a3497d03ad17e308a2299fa824727894f2c0ec`; its postrelease behavior is not
silently attributed to 1.1.0. Moving pi.dev documentation/landing pages and the
historical npm namespace are not the evidence baseline.

## Table cells for the parent comparison

| Axis | Pi 1.1.0 cell | Primary evidence |
| --- | --- | --- |
| Core execution | TypeScript Agent/agent-core runs model → tools → results → model, with streaming events and steering/follow-up queues. The coding-agent AgentSession adds resources, persistent sessions, compaction and retry orchestration around that core. | [P03], [P04], [P07] |
| Desktop/backend boundary | Node.js/Bun SDK embeds the session in process; JSONL RPC controls a long-lived child process. Interactive, print and JSON modes use the same agent. An application host supplies its product UI and domain API. | [P07], [P08], [P33] |
| Providers, authentication and model selection | Multiple providers support OAuth, API keys/environment credentials and compatible endpoints. Startup uses explicit/scoped models, saved defaults, then available provider defaults. Selection and thinking are configurable; this is broader routing policy than Renulus’s approved subscription/model allowlist. | [P09], [P10], [P11], [P42] |
| Tools, skills, MCP and delegation | Built-in file/shell tools and Agent Skills. v1.1.0 CLI bundles MCP/codemode/tool-search extensions; SDK hosts add them explicitly. Core tool batches default to parallel, with sequential overrides. Subagent delegation is an optional example/package, not a stock coding-agent tool. | [P04], [P05], [P12], [P13], [P14], [P15], [P47] |
| Streaming, cancellation and recovery | Session/model/tool events stream to hosts; abort stops agent work, retries and summaries. Transient failures have configurable agent retries: enabled by default, maximum three, starting at two seconds. Context overflow has separate compaction/retry handling; agent_end need not mean settlement. | [P07], [P16], [P17], [P18], [P20] |
| Context management | Model-window-aware compaction uses provider usage plus estimated trailing messages, with estimates after invalidating context edits. Defaults reserve 16,384 tokens and retain 20,000 recent tokens; manual/automatic compaction, branch summaries, model overrides and extension-provided summaries are supported. | [P19], [P20], [P21] |
| Reasoning and prompt caching | pi-ai preserves typed thinking/signatures and provider-specific replay; cache retention and session identities reach supported adapters. Coding-agent also has eligible cache-warming requests during active runs by default, configurable off/idle. Warming is provider usage, not free local bookkeeping. | [P21], [P22], [P23], [P24] |
| Documents and OCR | The built-in read tool reads UTF-8 text or sends supported images as model attachments, with resize/truncation handling. Its inspected implementation has no PDF/OCR parsing pipeline. PDF skills are instructions/examples; extraction integrations require additional tools or extensions. | [P25], [P14] |
| Retrieval and evidence | Available filesystem search/read tools and MCP resources support retrieval; external services require configuration or extensions. The inspected coding-agent interfaces do not provide Renulus’s canonical corpus, embeddings, revision/currentness checks or passage-citation database. | [P26], [P27], [P13], [P07] |
| Learner memory | Sessions, compaction summaries and AGENTS/system files retain context. The inspected stock coding-agent contracts do not implement structured learner facts, automatic semantic memory capture, correction workflows or a vector memory service; hosts/extensions must supply them. | [P28], [P29], [P07], [P19] |
| Conversation persistence and retention | Sessions save automatically as local JSONL trees; resume/fork/tree navigation and no-session/in-memory modes are supported. Compaction changes projected context while retaining transcript entries. This is session storage rather than Renulus’s learning-retention contract; telemetry/sharing need separate qualification. | [P29], [P30], [P31], [P32], [P38], [P41] |
| Assessment and generated practice | General model generation and tool/extension APIs can support custom practice workflows. The inspected SDK and built-in tool set do not define a reviewed question bank, immutable answer-key/scoring service or saved-test contract; those would be application functionality. | [P07], [P26] |
| Personalisation and study planning | Instruction files, prompts, skills and extension state can tailor behavior; model/thinking defaults and scoped cycling are configurable. These general controls do not establish a built-in learning-goal, curriculum, mastery or study-plan subsystem in the inspected coding-agent contracts. | [P28], [P14], [P09], [P07] |
| Background scheduling | Coding-agent CLI/SDK runs when invoked; the inspected interfaces expose no recurring-job/cron contract. Hosts or extensions arrange recurring execution. The separate pi-durable library resumes durable tasks; its task scheduler is not a shipped nightly study service. | [P33], [P07], [P34] |
| Upstream maintenance | MIT monorepo at earendil-works/pi, historically badlogic/pi-mono. Coding-agent 1.1.0 released October 7, 2026. The managed installer pins transitive dependencies; direct npm installation does not. Separate toolkit packages, experiments and examples require their own integration assessment. | [P01], [P02], [P36], [P37] |

## Decisive qualifications

**Core versus session/product wrapper.** Agent core owns a repeated model/tool
loop, streamed events and queued steering/follow-up inputs [P03][P04]. The
coding-agent SDK constructs an Agent, ModelRuntime, SessionManager,
SettingsManager and resource loader, with injectable host boundaries [P06].
AgentSession owns the conversation, active resources, compaction and recovery
[P07]. RPC is a strict JSONL child-process protocol, not an HTTP product API
[P08]; the host must build Renulus-like product services. The four CLI modes
share the agent/session/tool stack [P33].

**Built-in MCP is real in this release.** The CLI registers MCP, codemode,
tool-search and llama.cpp as built-in extensions [P12]. MCP accepts stdio and
streamable HTTP; its tools may be direct, deferred, available through codemode,
or hidden, and MCP resources are exposed [P13]. Codemode/tool-search start
inactive and can be activated explicitly or through the MCP exposure setup.
SDK hosts must supply the built-in extension factories and bind extensions;
a plain createAgentSession does not imply the CLI's MCP setup [P07][P13].
Subagent code exists under examples and needs explicit loading/installation
[P15]. Neither an example shipped in the npm tarball nor a community package
becomes a default coding-agent capability merely by existing [P01][P15].

**Parallel execution must not be described using old Pi defaults.** Agent
constructor defaults toolExecution to parallel [P04]. A globally sequential
setting, or any tool in the batch marked executionMode sequential, makes the
whole batch sequential [P05]. This is an execution-order rule, not evidence
that tools are safe to run concurrently in every host application.

**Provider choice and authentication.** Built-in routes support provider-specific
OAuth/API-key behavior, custom compatible endpoints and configured/environment
credentials [P09][P10]. Codex's implementation includes authorization-code/PKCE,
device-auth endpoints and refresh-token exchange [P44]. OpenCode Go has a
built-in provider using OPENCODE_API_KEY [P42]. Stock startup selects explicit
CLI/scoped choices, saved defaults, then available provider defaults [P11]; the
SDK also restores a configured model from session history [P06]. Optional
virtual-model routing can choose a physical model for each request and requires
credentials for the routed provider [P43]. None of these source paths proves
availability of Renulus's exact five approved models or access on an account;
there was no live login or subscription test.

**Retries, cancellation and settled state.** Agent retries default to enabled,
three retries and a 2,000 ms initial delay [P18]. Transient errors and context
overflow have separate recovery paths; overflow/eligible final truncation gets
at most one compact-and-retry recovery attempt [P17][P20][P45]. Abort stops agent
work, retry waits, compaction and branch summaries, then waits for idle [P16].
agent_end only ends a low-level run. RPC/SDK clients use agent_settled or idle
waiting for completion after retries, compaction or queued work [P07][P08].
This source review does not prove successful recovery against a live provider.

**Context and caching are distinct.** The compaction budget uses the selected
model window. Valid provider usage anchors estimates, trailing messages are
estimated, and context edits/compaction invalidate stale usage anchors [P19].
The default reserve is 16,384 tokens; recent retained context is 20,000 tokens.
Both can be overridden for an exact provider/model key; these are policy
budgets, not assertions of model capacity [P19][P45]. Extensions can cancel
compaction or return their own summary [P20]. pi-ai carries signed/opaque
thinking replay, cache-retention options and session identifiers [P22][P23].
Coding-agent also makes real provider requests to warm eligible caches, with
one output token requested and usage recorded. The default mode is streaming;
idle warming is a separate choice and off disables warming [P21][P24]. Default
warming requires a known cache lifetime and sufficient estimated savings;
it is not an unconditional request for every model [P21][P24].

**Domain absence claims are intentionally scoped.** The built-in read path either
reads UTF-8 text or sends a supported image attachment; no PDF parser/OCR engine
is present in that inspected path [P25]. The PDF entry in skill documentation is
sample instruction content, not a bundled PDF extraction dependency [P14].
Filesystem grep/read/find and configured MCP integrations can perform retrieval
[P26][P27][P13]. The inspected coding-agent factory, tool list and context-file
contracts describe general agent facilities [P06][P26][P28]. They do not establish
a Renulus-equivalent Library/revision/citation database, canonical learner-fact
service, reviewed question-bank/scoring contract or curriculum/study subsystem.
This is not a repository-wide assertion that no extension could implement one.
Model-generated text is not reviewed assessment functionality or educational
quality evidence.

**The separate durable package is not the coding-agent session contract.** The
same monorepo includes pi-durable [P02], which is not listed among coding-agent's
direct dependencies [P01]. Its README describes typed JSON documents,
transactional conversation/task records, SQLite/JSONL storage and task
resumption [P34]. Its subagent demonstrations still define a subagent extension
[P34]. Those typed JSON documents are application state, not proof of medical
PDF ingestion, OCR, RAG or learner records. Its task scheduler resumes durable
work; it does not by itself establish a recurring cron/nightly study service.
This table does not attribute that alternative harness's persistence/recovery
contract to the shipped coding-agent JSONL SessionManager.

## Persistence, telemetry and sharing qualification

SessionManager maintains an append-only id/parentId JSONL tree. Automatic
persistence starts when there is a user/assistant conversation entry; setup-only
startup need not create a transcript file [P29]. Compaction/navigation resolves
model context from the active branch without deleting abandoned transcript
history. no-session/SessionManager.inMemory disables transcript-file persistence
[P30][P31]; it is not a promise that configuration, credentials or other host
state will never be written [P06][P28]. Nor is local transcript storage a claim
that model input never leaves the machine.

The exact immutable 1.1.0 coding-agent README fetched for this review has
**voluntary external OSS session sharing at raw lines 58–69**: it directs users
to pi-share-hf and a Hugging Face account/CLI [P41]. This paragraph does not state
an automatic eligible-OSS session-upload default or an OSS eligibility gate.
The inspected settings state enableInstallTelemetry defaults **true**, covering
install/update reporting and selected provider attribution; enableAnalytics
defaults **false** [P38][P39]. PI_TELEMETRY overrides the install-telemetry setting,
with 0/false disabling that flag [P40]. Provider attribution is gated by that
flag, while OpenCode session-affinity headers have a separate purpose [P46].

**Automatic eligible-OSS transcript telemetry and its exact opt-out/gating were
not verified in these frozen sources.** They must not be asserted solely from
a moving landing page or the voluntary sharing paragraph. Equally, this review
does not assert that all Pi sessions are purely local, that all builds have no
session telemetry, or that install-telemetry opt-out controls external session
uploaders. A differently rendered README/hosted distribution needs its own
immutable implementation source before that behavior is added to the table.

## Maintenance and evidence limits

The root licence is MIT with Mario Zechner's copyright [P36]. Release/source
adoption must preserve that notice and review third-party terms separately.
The managed installer uses an install lock for transitive dependencies;
ordinary npm installation does not pin them [P37]. A release tag alone is not a
complete reproducible dependency closure for arbitrary npm installs. The package
manifest also excludes selected client/experimental build paths, while listing
some server/client packages only as dev dependencies; examples, experimental
paths and libraries must be evaluated on their own rather than treated as a
shipped desktop product [P01].

Only public primary sources were used: official repository/release/registry data,
immutable source and in-repository documentation. Public source was read without
installing packages, starting services, accessing private profiles/credentials,
reading the inherited archive, calling model providers, committing or pushing.
No tests were run and no operational, retrieval-quality, clinical-correctness or
educational-effectiveness claim is made. Negative domain claims are bounded to
the inspected core/SDK/tool/configuration contracts. The fixed source ranges in
the bibliography were checked against fetched raw-file line counts; web
renderers can normalize blank lines and report different display line numbers.

## Primary-source bibliography

Every P source below is pinned to abe508e1b89912adde45528136c3221eb69acdd7.

- **P01 — Coding-agent release/package boundaries.** `packages/coding-agent/package.json`, raw file lines 1–4, 49–73, 77–80. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/package.json#L1-L4); [immutable range 2](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/package.json#L49-L73); [immutable range 3](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/package.json#L77-L80).
- **P02 — Canonical Pi overview and package identities.** `README.md`, raw file lines 13–21, 37–43, 72–86. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/README.md#L13-L21); [immutable range 2](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/README.md#L37-L43); [immutable range 3](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/README.md#L72-L86).
- **P03 — Agent core model/tool/queue loop.** `packages/agent/src/agent-loop.ts`, raw file lines 163–320. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/agent/src/agent-loop.ts#L163-L320).
- **P04 — Core defaults including parallel tool execution.** `packages/agent/src/agent.ts`, raw file lines 243–253. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/agent/src/agent.ts#L243-L253).
- **P05 — Sequential override for an entire tool batch.** `packages/agent/src/agent-loop.ts`, raw file lines 508–522. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/agent/src/agent-loop.ts#L508-L522).
- **P06 — SDK session defaults and core construction.** `packages/coding-agent/src/core/sdk.ts`, raw file lines 195–205, 411–446. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/sdk.ts#L195-L205); [immutable range 2](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/sdk.ts#L411-L446).
- **P07 — SDK ownership, lifecycle and explicit built-in extensions.** `packages/coding-agent/docs/sdk.md`, raw file lines 26–56, 62–116. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/sdk.md#L26-L56); [immutable range 2](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/sdk.md#L62-L116).
- **P08 — RPC subprocess, framing and agent_settled semantics.** `packages/coding-agent/docs/rpc.md`, raw file lines 1–18, 22–56, 58–71. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/rpc.md#L1-L18); [immutable range 2](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/rpc.md#L22-L56); [immutable range 3](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/rpc.md#L58-L71).
- **P09 — Provider/model choices, credentials and catalog.** `packages/coding-agent/docs/models.md`, raw file lines 3–35. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/models.md#L3-L35).
- **P10 — Provider authentication and API-key routes.** `packages/coding-agent/docs/providers.md`, raw file lines 1–18, 31–48. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/providers.md#L1-L18); [immutable range 2](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/providers.md#L31-L48).
- **P11 — Stock startup model-selection order.** `packages/coding-agent/src/core/model-resolver.ts`, raw file lines 622–704. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/model-resolver.ts#L622-L704).
- **P12 — CLI built-in extension registrations.** `packages/coding-agent/src/extensions/index.ts`, raw file lines 1–14. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/extensions/index.ts#L1-L14).
- **P13 — MCP transport, exposure/resources and SDK qualification.** `packages/coding-agent/docs/mcp.md`, raw file lines 1–3, 189–204, 236–246, 270–272. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/mcp.md#L1-L3); [immutable range 2](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/mcp.md#L189-L204); [immutable range 3](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/mcp.md#L236-L246); [immutable range 4](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/mcp.md#L270-L272).
- **P14 — Agent Skills loading; PDF text is a sample skill.** `packages/coding-agent/docs/skills.md`, raw file lines 3–7, 24–45, 57–65. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/skills.md#L3-L7); [immutable range 2](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/skills.md#L24-L45); [immutable range 3](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/skills.md#L57-L65).
- **P15 — Optional subprocess subagent example and installation.** `packages/coding-agent/examples/extensions/subagent/README.md`, raw file lines 1–52. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/examples/extensions/subagent/README.md#L1-L52).
- **P16 — Abort agent, retry, compaction and branch summary.** `packages/coding-agent/src/core/agent-session.ts`, raw file lines 2431–2443. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/agent-session.ts#L2431-L2443).
- **P17 — Transient error/retry preparation and cancellation.** `packages/coding-agent/src/core/agent-session.ts`, raw file lines 3705–3712, 3758–3808. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/agent-session.ts#L3705-L3712); [immutable range 2](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/agent-session.ts#L3758-L3808).
- **P18 — Agent-level retry defaults.** `packages/coding-agent/src/core/settings-manager.ts`, raw file lines 1010–1028. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/settings-manager.ts#L1010-L1028).
- **P19 — Compaction defaults, usage accounting and threshold.** `packages/coding-agent/src/core/compaction/compaction.ts`, raw file lines 120–141, 184–269. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/compaction/compaction.ts#L120-L141); [immutable range 2](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/compaction/compaction.ts#L184-L269).
- **P20 — Bounded overflow recovery and extension compaction hooks.** `packages/coding-agent/src/core/agent-session.ts`, raw file lines 3003–3046, 3124–3166. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/agent-session.ts#L3003-L3046); [immutable range 2](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/agent-session.ts#L3124-L3166).
- **P21 — Thinking/cache warming, compaction and retry settings.** `packages/coding-agent/docs/settings.md`, raw file lines 9–21, 66–87, 117–133. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/settings.md#L9-L21); [immutable range 2](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/settings.md#L66-L87); [immutable range 3](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/settings.md#L117-L133).
- **P22 — Cache/session options and signed thinking blocks.** `packages/ai/src/types.ts`, raw file lines 215–230, 407–414. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/ai/src/types.ts#L215-L230); [immutable range 2](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/ai/src/types.ts#L407-L414).
- **P23 — Codex reasoning replay, session cache key and tool fields.** `packages/ai/src/api/openai-codex-responses.ts`, raw file lines 547–596. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/ai/src/api/openai-codex-responses.ts#L547-L596).
- **P24 — Warming eligibility, timers and real one-token provider request.** `packages/coding-agent/src/core/cache-warmer.ts`, raw file lines 204–250, 300–348. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/cache-warmer.ts#L204-L250); [immutable range 2](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/cache-warmer.ts#L300-L348).
- **P25 — Built-in text/image read implementation.** `packages/coding-agent/src/core/tools/read.ts`, raw file lines 90–156. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/tools/read.ts#L90-L156).
- **P26 — Built-in coding/read-only tool factories.** `packages/coding-agent/src/core/tools/index.ts`, raw file lines 118–179. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/tools/index.ts#L118-L179).
- **P27 — Filesystem/ripgrep search tool seam.** `packages/coding-agent/src/core/tools/grep.ts`, raw file lines 50–78. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/tools/grep.ts#L50-L78).
- **P28 — Instruction/system/resource files.** `packages/coding-agent/docs/configuration.md`, raw file lines 7–47. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/configuration.md#L7-L47).
- **P29 — Append-only JSONL tree and automatic conversation persistence.** `packages/coding-agent/src/core/session-manager.ts`, raw file lines 975–985, 1160–1188. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/session-manager.ts#L975-L985); [immutable range 2](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/session-manager.ts#L1160-L1188).
- **P30 — Continuation and in-memory mode.** `packages/coding-agent/src/core/session-manager.ts`, raw file lines 1793–1805. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/session-manager.ts#L1793-L1805).
- **P31 — Default saved sessions, branching, compaction and no-session mode.** `packages/coding-agent/docs/sessions.md`, raw file lines 5–52. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/sessions.md#L5-L52).
- **P32 — JSONL tree location, deletion and format migrations.** `packages/coding-agent/docs/session-format.md`, raw file lines 1–30. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/session-format.md#L1-L30).
- **P33 — Interactive, print, JSON and RPC mode boundaries.** `packages/coding-agent/docs/cli-integration.md`, raw file lines 1–18. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/cli-integration.md#L1-L18).
- **P34 — Separate durable library; typed state/tasks and subagent examples.** `packages/durable/README.md`, raw file lines 78–113, 414–459. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/README.md#L78-L113); [immutable range 2](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/README.md#L414-L459).
- **P35 — Host/process permissions and extension boundary.** `packages/coding-agent/docs/security.md`, raw file lines 1–25. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/security.md#L1-L25).
- **P36 — MIT and Mario Zechner copyright.** `LICENSE`, raw file lines 1–21. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/LICENSE#L1-L21).
- **P37 — Managed install lock versus direct npm transitive resolution.** `README.md`, raw file lines 168–179. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/README.md#L168-L179).
- **P38 — Default install telemetry and opt-in analytics settings.** `packages/coding-agent/docs/settings.md`, raw file lines 162–169. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/settings.md#L162-L169).
- **P39 — Install telemetry defaults true; analytics defaults false.** `packages/coding-agent/src/core/settings-manager.ts`, raw file lines 1164–1175. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/settings-manager.ts#L1164-L1175).
- **P40 — PI_TELEMETRY override for install telemetry.** `packages/coding-agent/src/core/telemetry.ts`, raw file lines 1–12. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/telemetry.ts#L1-L12).
- **P41 — Voluntary external public session-sharing direction.** `packages/coding-agent/README.md`, raw file lines 58–69. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/README.md#L58-L69).
- **P42 — Built-in OpenCode Go provider and API-key auth.** `packages/ai/src/providers/opencode-go.ts`, raw file lines 1–22. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/ai/src/providers/opencode-go.ts#L1-L22).
- **P43 — Optional virtual-model request routing.** `packages/coding-agent/src/core/model-runtime.ts`, raw file lines 987–1026. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/model-runtime.ts#L987-L1026).
- **P44 — Built-in Codex OAuth implementation.** `packages/ai/src/auth/oauth/openai-codex.ts`, raw file lines 17–35, 148–193. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/ai/src/auth/oauth/openai-codex.ts#L17-L35); [immutable range 2](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/ai/src/auth/oauth/openai-codex.ts#L148-L193).
- **P45 — Compaction trigger, single recovery attempt and per-model overrides.** `packages/coding-agent/docs/compaction.md`, raw file lines 25–41, 431–463. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/compaction.md#L25-L41); [immutable range 2](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/compaction.md#L431-L463).
- **P46 — Install telemetry-gated attribution and independent session headers.** `packages/coding-agent/src/core/provider-attribution.ts`, raw file lines 36–76. [immutable range 1](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/core/provider-attribution.ts#L36-L76).

- **P47 — Direct CLI-versus-SDK built-in MCP boundary.** `packages/coding-agent/docs/sdk.md`, raw file lines 114–116. [immutable range](https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/sdk.md#L114-L116).

Release/catalog metadata (moving metadata, captured October 10, 2026):

- [GitHub 1.1.0 release][release] — release date, latest marker and source tag.
- [Current npm registry metadata][npm-metadata] — latest dist-tag, 1.1.0 publication time.
- [Version-specific npm package metadata][npm-version] — package name/version/repository/engines/licence.

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
[release]: https://github.com/earendil-works/pi/releases/tag/v1.1.0
[npm-metadata]: https://registry.npmjs.org/@earendil-works/pi-coding-agent
[npm-version]: https://registry.npmjs.org/@earendil-works/pi-coding-agent/1.1.0

