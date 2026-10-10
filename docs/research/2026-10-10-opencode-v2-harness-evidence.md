# OpenCode v2 harness evidence for the Renulus comparison

2026-10-10. Research only, using public first-party source. Subject: the actual
OpenCode v2 implementation in `anomalyco/opencode`, not the archived Go CLI,
a similarly named fork, the OpenCode Go subscription alone, or the v1 runtime.
This note supplies the OpenCode column for the 15 axes in the existing
[Renulus/Hermes comparison](2026-10-10-backend-harness-comparison.md).

## Identity and version boundary

The comparison baseline is official branch `v2` resolved with `git ls-remote`
to **`55dde8810d8a859c0a21e42491ae7d5801fb49ef`**, whose core and root packages
identify source version **2.0.26**. Its public commit patch records an author
time of **October 10, 2026, 00:07:51 UTC** (October 10, 02:07:51 in Warsaw).
The source uses Bun workspace packaging and Effect; the branch's root catalogue
pins Effect **4.0.0-rc.118**. [OC01], [OC02], [branch-commit].

The highest v2 semantic-version tag returned by the official remote during this
inspection was `v2.0.26`, pointing to
`9b4ec5714d481559990db0a816d5dec19541a814`. That commit's patch is titled
`release: v2.0.26` and dated **October 8, 2026, 19:45:43 UTC**. The GitHub
page for that tag also exposes that timestamp. This is separate from the public
distribution observation: GitHub `releases/latest` redirected to **v1.18.35**,
and the npm registry returned **1.18.35** for `opencode-ai/latest` while
`opencode-ai/2.0.26` returned “version not found”. These are dated metadata
observations, not a claim that v2 is the default public npm release, that every
v2 asset is available, or that this source was installed or tested.
[tag-commit], [tag-release], [default-release], [npm-latest], [npm-v2].

A direct raw-source comparison of 19 selected files showed why the branch and tag
must remain distinct: core loop, step, retry, compaction, execution, reasoning
replay, session schema, read tool, job registry and desktop service files were
identical; the branch updated Effect imports/dependencies and had further
subagent-service, token-sharing and embedded-SDK changes. The branch's SDK
registers supplied plugins before restart recovery; the tag's host differs.
All table source IDs below pin the **branch commit**, not a moving branch name.
This bounded comparison is not an exhaustive diff between releases.
[OC02], [OC07], [OC12], [OC44], [tag-commit].

## Cells for the augmented table

“Inspected core” means the first-party core service/tool/plugin inventory, schema,
and relevant implementation paths at this pinned revision. It does not establish
absence across the whole extension ecosystem. A plugin, example, protocol
capability or possibility is not attributed as a built-in Renulus-equivalent
learning flow. Registered internal plugins are stock implementation entries,
not merely community example files. [OC12].

| Axis | OpenCode v2 cell | Primary evidence |
| --- | --- | --- |
| Core execution | Full TypeScript/Effect agent loop through @opencode/ai: durable admitted inputs, repeated model/tool steps, concurrent local tool fibers and per-session execution coordination. Application services can host and customise this core. | [OC03], [OC04], [OC41] |
| Desktop/backend boundary | Electron desktop connects to a managed CLI background server; terminal/web clients share the typed server/protocol/client contracts. ACP is implemented. The SDK can embed the same server router in-process without opening a network listener. | [OC05], [OC06], [OC07], [OC38] |
| Providers, authentication and model selection | Broad provider registry, API-key/OAuth integrations, optional local-provider discovery and configurable models/variants. Includes Console login, ChatGPT token sharing and legacy Codex login. It does not impose Renulus’s fixed two-subscription/five-model policy; account-specific availability was not tested. | [OC08], [OC09], [OC10], [OC11], [OC13] |
| Tools, skills, MCP and delegation | Registered shell/file/search/browser tools, filesystem or URL skills, MCP tools/prompts/resources and child-session subagents. Build/Plan/General/Explore agents are built in; foreground/background delegation has permission and depth checks. These capabilities are registered internal plugins. | [OC12], [OC13], [OC14], [OC15], [OC16], [OC33], [OC42] |
| Streaming, cancellation and recovery | Streams provider and tool events with fiber cancellation, bounded retry/continuation logic and overflow recovery. Durable execution claims let the managed server resume orphaned turns after restart. This recovery is explicitly at least once, so external effects can repeat. | [OC03], [OC04], [OC17], [OC18], [OC41] |
| Context management | Auto/manual/overflow compaction uses model limits, provider usage anchors plus estimates, configurable buffers and recent-context retention. Supports summary or provider-native checkpoints. Unknown windows do not trigger automatic compaction; native availability depends on the route policy. | [OC19], [OC24], [OC43], [OC44] |
| Reasoning and prompt caching | Retains reasoning parts and replays model-bound provider state only when compatible. Its AI layer applies provider-aware cache hints; requests carry session-affinity cache keys. Actual cache hits and account capabilities were not measured. | [OC20], [OC21], [OC22], [OC24] |
| Documents and OCR | The read tool handles numbered text and sends PDFs/images directly as model file content. Requests check modality capabilities and bound image payloads. No stock OCR extraction, durable passage store or document-ingestion index was identified in inspected built-ins. | [OC23], [OC24], [OC12] |
| Retrieval and evidence | File/regex search, web search/fetch, MCP resources and local/Git reference repositories provide agent context. No Renulus-style canonical Library passage/revision/rights service or hybrid document retrieval index was identified in the inspected core. | [OC12], [OC15], [OC25], [OC26], [OC27], [OC29] |
| Learner memory | Global/project AGENTS.md, skills, durable instructions and saved session history provide context. No learner-fact extraction, semantic memory index, correction or recapture-suppression service was identified in inspected core/built-ins. A memory extension would be separate functionality. | [OC12], [OC16], [OC28], [OC29] |
| Conversation persistence and retention | Stores sessions/messages and durable queued work in SQLite; supports fork, import/export and recursive deletion. Historical event-log retention is optional. Embedded SDK defaults to an in-memory database, requiring a configured file database for lasting history. | [OC29], [OC30], [OC31], [OC32], [OC37], [OC07], [OC40] |
| Assessment and generated practice | Prompts, custom agents and tools can implement workflows. No stock contract for reviewed question banks, version-pinned answer keys, deterministic educational scoring, assistance buckets or saved educational tests was identified in inspected core. These require application/plugin functionality. | [OC12], [OC29], [OC33] |
| Personalisation and study planning | Agents, skills and instructions customise workflows; coding Plan mode constrains edits and persists switch reminders. No learner goals, mastery records, mistake-first curriculum or adaptive study planner was identified in the inspected core. | [OC16], [OC28], [OC29], [OC33] |
| Background scheduling | Background shell/subagent jobs retain notification markers. Interrupted sessions/subagents can resume after restart; running shell jobs are cancelled. Periodic reference refresh exists. No calendar/cron recurrence contract was identified in Job API; educational scheduling needs application/plugin support. | [OC13], [OC18], [OC27], [OC34], [OC45] |
| Upstream maintenance | MIT source with separate core/server/protocol/client/SDK packages. V2 changes plugin and server/client contracts from V1, requiring integration migration. This comparison pins a source snapshot labelled 2.0.26; it is distinct from the registry/default release labelled 1.18.35. | [OC01], [OC02], [OC35], [OC36] |

## Qualifications that affect interpretation

- **Full loop and recovery:** the runner drains durable input and repeats logical
  steps; each attempt streams the provider and executes returned tools in scoped
  fibers. Execution starts with a write-ahead claim, and deliberate stop differs
  from shutdown because shutdown preserves the claim. Restart recovery explicitly
  permits repeated external effects. Source presence does not prove crash behavior
  on this Windows installation. [OC03], [OC04], [OC18], [OC41].
- **Provider breadth is not subscription equivalence:** registered providers
  include local and hosted integrations. Console device login, ChatGPT token
  sharing and the separately labelled legacy Codex methods are different code
  paths. Token sharing filters a fallback model set and forces summary compaction;
  native compaction support elsewhere in core must not be attributed to every
  account or route. None of these paths establishes availability of Renulus's five
  selected model IDs for a real account. [OC08], [OC09], [OC10], [OC11], [OC44].
- **Measured context is still partly estimated:** the current provider's most
  recent reported token usage anchors the budget; later text/tools/media are
  estimated. Unknown windows do not automatically trigger compaction. Summary
  and provider-native replacements are separate paths, and a compaction agent can
  select a different configured model. No claim of exact token counting or
  zero-cost compaction follows. [OC19], [OC43].
- **Cache support is route-specific:** the AI package deliberately skips inline
  cache markers on protocols that use implicit or other cache mechanisms. Request
  affinity and prompt-cache keys are constructed in core; actual hits, pricing
  benefits, reasoning quality and provider response identity were not tested.
  [OC20], [OC21], [OC22], [OC24].
- **Media is direct model input, not a document library:** PDF/image file content
  is forwarded to the selected model, with capability checks and image bounds.
  This does not establish local OCR, page/passage extraction, embeddings, revision
  replacement or evidence-rights checks. File/regex/web/MCP/reference facilities
  are evidenced, while a Renulus-equivalent Library RAG service was not identified
  in the inspected core. [OC12], [OC15], [OC23], [OC24], [OC25], [OC26], [OC27].
- **Persistence has three distinct meanings:** the standard CLI supplies a file
  database; the embedded SDK defaults to `:memory:`; historical bus event-payload
  retention defaults to false and is optional. Session/message projections,
  instructions, queued inputs and execution claims still have canonical SQLite
  tables. Event-driven durable sessions do not mean every historical bus payload
  is retained by default. [OC07], [OC29], [OC30], [OC32], [OC40], [OC41].
- **Archive should not be inferred from a column:** the schema retains
  `time_archived` and imports can restore it, but the inspected v2 session update
  contract exposes title, metadata and permissions. This note does not assert an
  implemented Archive action from that storage field. Recursive deletion is
  separately implemented. [OC29], [OC31], [OC37], [OC39].
- **Background scheduling:** the Job service manages effects,
  wait/background/cancel and recovery notification state. On restart, shell jobs
  still marked running are reported cancelled; session/subagent executions can
  resume separately. Reference refresh is periodic. No calendar/cron task contract
  or nightly educational publication flow was identified in the inspected Job API.
  [OC13], [OC18], [OC27], [OC34].
- **Domain limits are bounded findings:** durable session instructions and
  coding Plan mode are implemented. Learner-fact authority, assessment keys and
  scoring, mastery/goal records and adaptive curriculum flows were not identified
  in the inspected stock inventory/schema. This is not a claim that a custom agent,
  MCP server or third-party plugin could never add them. [OC12], [OC28], [OC29], [OC33].

No packages were installed; no application/service, inference, live account,
credentials, learner profile, private correspondence or archived project was
used. Source files were read from the public repository, including an in-memory
source snapshot. No upstream tests or application tests were run. The comparison
establishes inspectable implementation paths, not educational efficacy, clinical
accuracy, live provider behavior, Windows acceptance or production reliability.

## Immutable primary-source bibliography

Every OC source below is in official `anomalyco/opencode` at
`55dde8810d8a859c0a21e42491ae7d5801fb49ef`. File anchors and cited line bounds
were checked against that source snapshot. Additional ranges named in descriptions
are in the same immutable file.
- [OC01] — `packages/core/package.json:1–41`; Core package version, MIT declaration and runtime exports.
- [OC02] — `package.json:3–95`; Monorepo version, Bun workspace and Effect dependency.
- [OC03] — `packages/core/src/session/runner/llm.ts:54–296`; Durable input drain and repeated model steps.
- [OC04] — `packages/core/src/session/runner/step.ts:77–170`; Provider stream, concurrent tool fibers and cancellation.
- [OC05] — `packages/server/src/routes.ts:52–141`; Shared service graph and standalone/embedded routes.
- [OC06] — `packages/desktop/src/main/service/background-service.ts:32–91`; Electron adoption/start of the managed CLI service.
- [OC07] — `packages/sdk/src/internal/host.ts:28–73`; Embedded router, lifecycle, plugins, recovery and in-memory default.
- [OC08] — `packages/core/src/plugin/provider.ts:1–68`; Registered provider plugins, including local-provider integrations.
- [OC09] — `packages/core/src/plugin/provider/openai.ts:22–228`; Legacy Codex browser/device OAuth registration.
- [OC10] — `packages/core/src/plugin/provider/chatgpt.ts:94–99`; ChatGPT token-sharing OAuth registration.
- [OC11] — `packages/core/src/plugin/provider/opencode.ts:101–177`; OpenCode Console device OAuth and refresh.
- [OC12] — `packages/core/src/plugin/internal.ts:216–270`; Stock internal plugin/tool registration inventory.
- [OC13] — `packages/core/src/tool/plugin/subagent.ts:29–200`; Foreground/background child sessions, model choice, permissions and depth limits.
- [OC14] — `packages/core/src/permission.ts:87–111`; Ordered allow/ask/deny rule evaluation and permission service.
- [OC15] — `packages/core/src/mcp/index.ts:113–138`; MCP connections, tools, prompts and resources.
- [OC16] — `packages/core/src/config/plugin/skill.ts:77–125`; Configured directory/URL skills and SKILL.md discovery.
- [OC17] — `packages/core/src/session/runner/retry.ts:31–91`; Retry policy, bounded Retry-After, timeout limits and hooks.
- [OC18] — `packages/core/src/session/execution/restart.ts:23–240`; Restart claims, attempt budget, at-least-once qualification, running-shell cancellation and subagent recovery.
- [OC19] — `packages/core/src/session/compaction.ts:195–250`; Auto/manual/overflow and native/summary compaction selection; token accounting at 868–923 in the same file.
- [OC20] — `packages/core/src/session/runner/to-llm-message.ts:153–229`; Reasoning/provider-state replay conditions.
- [OC21] — `packages/ai/src/cache-policy.ts:1–67`; Provider-aware cache hint policy and protocol qualifications.
- [OC22] — `packages/core/src/session/affinity.ts:3–8`; Parent/fork session affinity.
- [OC23] — `packages/core/src/tool/plugin/read.ts:39–185`; Stock text/image/PDF read behavior; model content conversion at 175–185.
- [OC24] — `packages/core/src/session/model-request.ts:122–301`; Media capability checks; image budget at 189–215 and cache key at 278–301.
- [OC25] — `packages/core/src/tool/plugin/websearch.ts:20–64`; Selected-integration web search, permission and typed results.
- [OC26] — `packages/core/src/tool/plugin/webfetch.ts:12–37`; Web fetch formats and bounded output contract.
- [OC27] — `packages/core/src/reference.ts:51–112`; Local/Git reference repositories and periodic refresh.
- [OC28] — `packages/core/src/config/plugin/instruction.ts:23–77`; Global/project AGENTS.md discovery and watching.
- [OC29] — `packages/core/src/session/sql.ts:22–176`; SQLite session/message/projection, pending work and inbox tables.
- [OC30] — `packages/core/src/bus.ts:175–203`; Historical event-payload retention is optional and defaults false.
- [OC31] — `packages/core/src/session.ts:367–377`; Recursive child-session deletion and execution/transport cleanup.
- [OC32] — `packages/cli/src/database-path.ts:4–13`; CLI file-backed database path selection.
- [OC33] — `packages/core/src/plugin/plan.ts:14–95`; Coding Plan mode, edit constraints and allowed plan directory; durable reminders at 55–95.
- [OC34] — `packages/core/src/job.ts:95–207`; Process-local background jobs and durable notification markers.
- [OC35] — `services/www/src/docs/content/migrate-v1.mdx:8–39`; Official source-pinned V2 plugin/server/client migration contract.
- [OC36] — `LICENSE:1–21`; MIT licence.
- [OC37] — `packages/core/src/session/transfer.ts:38–143`; Session import/export representation and import restoration.
- [OC38] — `services/www/src/docs/content/cli/acp.mdx:80–87`; Official source-pinned ACP private-server and stdio transport documentation.
- [OC39] — `packages/protocol/src/groups/session.ts:362–378`; Mutable session API fields; no archive setter in this inspected endpoint.
- [OC40] — `packages/cli/src/server-process.ts:100–109`; CLI passes its selected file path to the server.
- [OC41] — `packages/core/src/session/execution.ts:76–140`; Write-ahead execution claims committed with execution events.
- [OC42] — `packages/core/src/plugin/agent.ts:76–118`; Built-in Build, General and Explore agents.
- [OC43] — `packages/core/src/session/compaction.ts:868–923`; Provider token anchors, estimates and window reserve policy.
- [OC44] — `packages/core/src/plugin/provider/chatgpt.ts:295–321`; Token-sharing model filter and explicit summary-only compaction policy.
- [OC45] — `packages/core/src/session/execution/restart.ts:101–135`; Running background shell jobs are cancelled after server restart, separately from resumed session executions.

Metadata sources are first-party and were inspected on October 10, 2026; the
registry/latest endpoints are moving observations, whereas the commit links are
immutable identities.

- [Official v2 branch commit patch][branch-commit].
- [Official v2.0.26 tag commit patch][tag-commit].
- [Official GitHub v2.0.26 tag release page][tag-release].
- [Official GitHub default latest-release redirect][default-release].
- [Official npm latest-version metadata][npm-latest].
- [Official npm exact 2.0.26 version query][npm-v2].
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
[OC18]: https://github.com/anomalyco/opencode/blob/55dde8810d8a859c0a21e42491ae7d5801fb49ef/packages/core/src/session/execution/restart.ts#L23-L240
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
[branch-commit]: https://github.com/anomalyco/opencode/commit/55dde8810d8a859c0a21e42491ae7d5801fb49ef.patch
[tag-commit]: https://github.com/anomalyco/opencode/commit/9b4ec5714d481559990db0a816d5dec19541a814.patch
[tag-release]: https://github.com/anomalyco/opencode/releases/tag/v2.0.26
[default-release]: https://github.com/anomalyco/opencode/releases/latest
[npm-latest]: https://registry.npmjs.org/opencode-ai/latest
[npm-v2]: https://registry.npmjs.org/opencode-ai/2.0.26

