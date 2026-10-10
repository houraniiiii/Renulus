# Pi and OpenCode v2: side-conversation findings and evidence

Recorded: 2026-10-10. Status: research and architectural recommendation, not an adopted foundation decision or implementation approval.

This note consolidates the substantive findings, qualifications, corrections and proposed integration approach from the side conversation. It is separate from the main-thread foundation study. No subagents were used or consulted in this side conversation. Evidence came from upstream source, upstream documentation, public release/package metadata and bounded inspection of Renulus source. No harness was installed or executed, no model provider was called, and no comparative performance or reliability test was run.

The user explicitly requested this record. The recording change is limited to this new note. Existing main-thread research, decisions, implementation and workspace configuration are not changed by it. Renulus HEAD at recording was 528025ff0b22477c12ee1512e0e7d15297a6e888; the checkout already contained main-thread documentation changes.

## Recommendation and its status

The side conversation recommends **evaluating direct adoption of OpenCode v2's embedded runtime, configured through Renulus plugins and a small integration module**, for the full requested combination of tools, MCP, skills, execution loops, subagents, instructions and context management.

This is an architectural fit judgment: more of that combination is already connected in OpenCode. It is not a measured claim that OpenCode is faster, more reliable or cheaper to maintain. Pi remains attractive for a deliberately small, custom execution architecture, especially one that needs a general durable task/state-machine abstraction.

The recommendation is conditional on a connected Windows integration proof using the exact selected build. If adapting OpenCode requires replacing its runner, persistence or child coordination, reconsider Pi: that would remove much of the expected benefit of direct reuse. The existing confirmed Hermes foundation is not superseded by this note. The main-thread Pi proposal and this side-conversation OpenCode proposal remain research recommendations until the owner selects an approach.

## Questions examined and corrections retained

The user asked whether the main thread's Pi justification actually distinguished Pi from OpenCode v2. The quoted justification relied on Pi's durable conversation/task/tool machinery and injected model/registry interfaces as a good place for Renulus's domain and subscription policies.

The correction is that these capabilities do not establish a unique Pi advantage. OpenCode v2 also has durable execution coordination, child sessions, configurable models/tools, plugin interfaces and an embedding interface. The narrower Pi advantage supported by the source is a smaller initial composition with fewer coding-workspace assumptions. [OpenCode execution][O-EXECUTION], [subagents][O-SUBAGENT], [plugins][O-PLUGIN], [embedded host][O-HOST], [Pi harness types][P-HARNESS-TYPES]

The user also described Pi as simpler/faster and recalled an OpenCode engineer saying everything was designed as a plugin. The simplicity claim was separated into initial core size versus total Renulus implementation effort. The speed claim was not accepted without comparable v2 measurements. No original interview was identified; source inspection substantiates extensive plugin composition, not an unlimited claim that every runtime concern is independently replaceable as a plugin. [OpenCode plugin domains][O-PLUGIN], [internal plugins][O-INTERNAL], [instance graph][O-INSTANCE]

The final follow-up distinguished three adoption choices: borrowing ideas, extracting internal source modules, and embedding the runtime with selected capabilities. The recommendation is the third approach. The reasoning and implementation proposal are preserved below.

## Inspected versions and provenance

| Evidence target | Exact snapshot | Qualification |
| --- | --- | --- |
| Pi source | earendil-works/pi, abe508e1b89912adde45528136c3221eb69acdd7 | Pinned source used for the Pi findings. |
| Pi release | v1.1.0, published 2026-10-07 at 22:26:31 UTC | Release metadata was checked; this does not establish API stability. [Release][P-RELEASE] |
| Pi Durable package | @earendil-works/pi-durable 1.1.0 | Metadata declares Node >=22.19.0; dependencies include pi-ai, chord, diff and typebox. [Package metadata][P-PACKAGE] |
| OpenCode v2 source | anomalyco/opencode, 4b6fea2875e4f2e3e8a8fee181803e54f7056845 | Primary final source snapshot; commit dated 2026-10-10 at 08:39:37 UTC. [Commit][O-COMMIT] |
| Earlier OpenCode source inspected | 55dde8810d8a859c0a21e42491ae7d5801fb49ef | Final snapshot is three commits ahead. Changes include Effect 4.0.1, related generated schema/client changes, location lifecycle and packaging work. [Comparison][O-COMPARE] |
| Published OpenCode SDK observed | @opencode/sdk 2.0.26 | Depends on matching 2.0.26 OpenCode packages and Effect 4.0.0-rc.112. [Package metadata][O-PACKAGE] |
| OpenCode v2.0.26 tag source | 9b4ec5714d481559990db0a816d5dec19541a814 | Inspected separately from the newer v2 source. [Tag host][O-TAG-HOST], [tag Promise entry][O-TAG-PROMISE] |

The v2 source branch, release-tag source and published SDK must not be treated as the same artifact. Published SDK existence was verified, so “v2 is only source with no SDK package” would be inaccurate. The side conversation did not independently unpack and execute the published tarball. Source/tag and package metadata establish different, bounded facts.

A material startup-order difference was identified. At the inspected 2.0.26 tag, the Promise entry creates the host and subsequently registers supplied host plugins; the host starts recovery during construction. In the newer source, supplied plugins reach the host and are registered before recovery is started. This is a source-level ordering concern for startup policy, not an observed policy escape in a running installation. Verify the actual selected artifact and policy installation before recovery. [Tagged Promise startup][O-TAG-PROMISE], [tagged host][O-TAG-HOST], [current Promise startup][O-PROMISE], [current host][O-HOST]

## Renulus context established by inspection

Renulus is a Windows learning harness for EU nephrologists, with the application intended as a client of reusable capabilities. The project requires broad nephrology coverage, existing selected subscriptions, no owner-hosted inference service, and no doctor-managed GPU/Docker/model server. Its approved data stack includes SQLite canonical records, Mem0 with a derived local Qdrant index, Docling/HybridChunker, FastEmbed and LanceDB. These project constraints remain separate from a proposed execution-engine change. [Project brief][R-BRIEF], [workspace rules][R-WORKSPACE]

The allowed model routes remain Codex GPT 6.1 Sol, GPT 6 Astra and GPT 6 Luna, and OpenCode Go MiMo V2.6 Pro and DeepSeek V4.1 Flash. Library support for a provider does not prove working subscription authentication or account-specific model availability. Those require integration verification without adding an unselected model or paid generative API fallback. [Project operating model][R-BRIEF]

The inspected implementation already has substantial domain functionality, but its generation interface is narrower than the requested full harness:

| Local evidence | Observed behavior | Implication |
| --- | --- | --- |
| Provider protocol | stream returns an asynchronous iterator of text strings, plus status/cancel operations. [Protocol][R-GENERATION] | A full harness needs observable tool, execution and child-session state in addition to text output. |
| Hermes subscription transport | Uses Hermes wire conversion, passes tools=None, removes tools/tool_choice and rejects returned automation/tool calls. [Transport][R-TRANSPORT] | The current route is deliberately constrained; adding a full agent loop requires a real integration change. |
| Context adapter | Reuses Hermes compression through an approved summary route and a Renulus budget/instruction policy. [Context adapter][R-CONTEXT] | If OpenCode owns a future conversation lifecycle, avoid leaving two independent compressors responsible for that same conversation. |

These observations do not mean Renulus lacks retrieval, memory, assessment or source policy. Those existing modules are candidates to retain behind tools. They also do not measure the quality of the current app or of either proposed harness.

## Capability comparison

“Pi” must be qualified: its agent core, normal AgentSession SDK and experimental Durable harness are different integration choices. The table distinguishes them instead of assuming that every feature of every Pi layer arrives automatically in one durable bundle.

| Concern | Pi at the inspected revision | OpenCode v2 at the inspected revision | Consequence for Renulus |
| --- | --- | --- | --- |
| Small execution core | Agent core exposes model streaming, context transformation and tool lifecycle/control interfaces. [Agent core][P-AGENT] | Embedded runtime assembles a wider backend. [Host][O-HOST] | Pi is a smaller basis for custom assembly. |
| Durable operation | Durable has committed conversations, task checkpoints, submissions and recovery. [Durable overview][P-DURABLE] | Execution claims and restart recovery are explicit runtime machinery. [Execution][O-EXECUTION], [restart][O-RESTART] | Durability is not unique to Pi. |
| Normal session SDK | AgentSession composes model runtime, session manager, resources, tools and extension binding. [SDK][P-SDK] | SDK provides a host/client interface over the assembled in-process router. [SDK][O-SDK] | Compare complete integration paths, not only minimal loops. |
| Custom tools | Durable registry supports schema-defined executors; coding tools are installed explicitly. [Harness types][P-HARNESS-TYPES], [registry][P-REGISTRY] | Plugin tool editors register executable tools with schemas. [Tool interface][O-TOOL] | Existing Renulus functions can become native tools in either. |
| MCP | Normal Pi SDK requires explicit wiring of relevant factories/binding; CLI behavior is not automatically all SDK behavior. [SDK][P-SDK] | Core MCP module handles server lifecycle, tools, prompts/resources and authentication, including remote OAuth/stdio paths. [MCP][O-MCP] | OpenCode supplies more connected MCP plumbing; actual servers still need validation. |
| Skills and instructions | Normal SDK uses its resource loader. Experimental Durable app reuses skill/project-context loading in a prompt extension. [SDK][P-SDK], [durable prompt][P-PROMPT] | Skill instruction integration and a session instruction ledger are present. [Skills][O-SKILLS], [instructions][O-INSTRUCTIONS] | Pi Durable reuse is possible, but do not assume normal extension loading transfers unchanged. |
| Context management | Durable has compaction tasks/hooks; normal AgentSession has its own session/context behavior. [Compaction][P-COMPACTION], [SDK][P-SDK] | Runtime has compaction, context hooks and a customizable compaction result. [Compaction][O-COMPACTION], [session hooks][O-SESSION-HOOKS] | Select one conversation-context owner and adapt it for evidence-based learning. |
| Subagents | Durable supports task-owned conversations; its experimental app includes a foreground subagent tool. A separate normal coding-agent example uses subprocesses. [Durable child tool][P-SUBAGENT], [subprocess example][P-SUBAGENT-EXAMPLE] | Built-in child sessions support foreground/background operation, depth checks and permissions. [Subagents][O-SUBAGENT] | Neither “Pi has no subagents” nor “all Pi subagents are the same” is accurate. |
| Permission workflow | Durable offers tool hooks; a Renulus approval workflow needs explicit host composition. [Tool execution][P-TOOL] | allow/ask/deny rules, request/reply and saved permission machinery exist. [Permissions][O-PERMISSION] | More reusable approval coordination exists in OpenCode; domain checks remain Renulus's responsibility. |
| Provider/model policy | Models are supplied; registry and hooks allow customization. [Harness types][P-HARNESS-TYPES] | Model/provider transforms and runtime model interfaces allow customization. [Model registry][O-MODEL], [plugins][O-PLUGIN] | Neither automatically enforces Renulus's complete subscription policy. |
| Durable custom workflows | Durable explicitly exposes owned tasks, checkpoints and task graphs. [Task/storage types][P-TYPES] | Inspected machinery is organized around sessions, jobs and agent execution. [Execution][O-EXECUTION], [restart][O-RESTART] | Pi has a clearer general durable-workflow abstraction; this is not proof OpenCode cannot support workflows. |
| Non-coding minimum | Storage, models and registry are supplied; filesystem/process environment is optional. [Harness types][P-HARNESS-TYPES] | Location/directory and a larger instance graph are part of composition. [Instance][O-INSTANCE] | Pi has fewer assumptions to configure at the start. |
| Existing client support | Durable exposes committed views/events; its experimental app demonstrates rendering those views. [Experimental application][P-APP] | SDK exposes session/event interfaces and owns runtime cleanup. [SDK][O-SDK] | Both permit Renulus to have its own client. |
| Deletion and retention | The inspected Durable StorageWrite contract lacks conversation/entry deletion operations. [Storage writes][P-TYPES] | Session removal recursively handles children and coordinates teardown. [Session removal][O-SESSION] | Complete Renulus deletion still needs coverage across domain records, originals, indexes and backups. |
| Stability evidence | Durable is explicitly experimental with potential API changes between releases. [Durable overview][P-DURABLE] | The inspected v2 source and published SDK differ materially. [Version evidence above][O-PACKAGE] | Pin and test either path; do not infer maturity from feature count. |
| Speed/reliability | No comparable current measurement established superiority. | No comparable current measurement established superiority. | Recommendation is architectural, pending operational evidence. |

## What the three Pi paths actually provide

The minimal agent core supplies an agent loop and customization of streaming, context conversion/transformation and tool processing. It should not be equated with the normal coding-agent's whole session application or with Durable's persisted scheduler. [Agent implementation][P-AGENT]

The normal AgentSession SDK has its own model/runtime, session manager, resource loader and extension integration. It can select or replace tools and resource discovery. MCP/codemode/tool-search behavior needs the documented factories and binding rather than assuming CLI startup happens in the SDK. Its session persistence is not the same contract as Durable's store/task scheduler. [AgentSession SDK][P-SDK]

Durable is a separate experimental harness using explicit storage, model access and an extension registry. Its registry always installs built-in generation, tool and compaction tasks; those built-in task names cannot simply be replaced through a registry extension. Extensibility therefore has defined limits in Pi too. [Durable overview][P-DURABLE], [registry implementation][P-REGISTRY]

An actual experimental application already combines Durable with Pi model/auth/settings components, SQLite, a TUI and subagents. Its prompt module reuses skills and project-context instructions. That is stronger evidence than a hypothetical integration sketch. However, the application explicitly omits normal extension loading, images, login UI, session-picker and some navigation features. Its session lock belongs to that application; do not assume every custom Durable host receives that locking mechanism from the generic storage interface. [Application scope and lock][P-APP], [prompt reuse][P-PROMPT]

The foreground Durable subagent tool creates or reuses a task-owned child conversation and uses a stable request identifier. It removes its own delegation extension from the child's inherited agent configuration. The separate coding-agent subprocess example is useful design evidence but represents another mechanism. [Durable child tool][P-SUBAGENT], [subprocess example][P-SUBAGENT-EXAMPLE]

## Meaning of “cleaner minimal non-coding foundation”

For Pi Durable, supplied models means a host-provided model interface; supplied storage means a backend satisfying its durable storage contract; supplied tools means registered executable functions. Its optional execution environment concerns filesystem and process operations. Custom tools such as search_library and read_passage can call Renulus's existing modules without installing the built-in read/write/edit/bash toolset. The harness still executes tools and models and persists state. [Harness configuration/types][P-HARNESS-TYPES], [environment documentation][P-DURABLE]

“Environment optional” does not mean no disk use, no executable code or a security sandbox. A storage implementation can use disk, and a custom executor can access resources through its own code. The privileges and access checks of those executors still matter. [Execution API][P-HARNESS-TYPES], [Pi security model][P-SECURITY]

For OpenCode, the service graph is the interconnected collection assembled for an instance. Besides the desired harness modules, it contains filesystem, shell, PTY, formatter, VCS, worktree, snapshot and location-watcher modules. This is source evidence about composition; it does not measure idle CPU, memory or startup cost, or prove every possible feature actively performs work on every request. [Instance graph][O-INSTANCE]

OpenCode sessions use a Location/directory. A directory without Git or Mercurial is supported and receives an identity derived from its directory. A proposed Renulus integration can use a managed local runtime directory and session metadata for its own identifiers. A study topic need not become a Git repository or a separate filesystem project. [Project resolution][O-PROJECT], [session metadata and instances][O-SDK]

Thus Pi's advantage here is fewer coding-specific defaults to adapt. It is not proof of a smaller finished Renulus system: connecting our required persistence, permission, MCP, delegation and client behavior may outweigh the smaller starting core. That tradeoff is the main architectural inference behind the OpenCode recommendation.

## How far OpenCode's plugin design goes

The Promise plugin API supports ordinary async/await setup, cleanup, hooks and reload, alongside the Effect interface. Transform domains include agents, tools, skills, MCP, providers/models, commands, references, integrations, VCS and web search. Runtime hooks can adjust provider setup, session context and retry decisions. Tools carry executable functions and schemas. [Plugin API][O-PLUGIN], [plugin context][O-PLUGIN-CONTEXT], [tools][O-TOOL]

This supports a Renulus plugin/profile for much of the product adaptation. Deeper integration can use the embedded host's service-replacement interface; that requires understanding the relevant internal contracts rather than assuming all replacements are ordinary plugins. [Embedded host][O-HOST], [server composition][O-ROUTES], [Effect SDK][O-EFFECT]

There are structural limits. Built-in plugin groups have startup ordering, and repository-config removal cannot disable two guarded internal plugin identities: the OpenCode provider connection and configuration policy. The database/schema, instance graph and execution coordination also remain runtime machinery. “Everything is a plugin” is useful shorthand for extensibility, not an accurate literal description of complete decoupling. [Internal plugin groups/guards][O-INTERNAL], [supervisor][O-SUPERVISOR]

Core Instance has a no-discovery option for upward/global configuration and boot-time instruction/plugin discovery. It leaves built-in plugins intact, honors explicit file-backed requests, and does not disable instruction loading triggered later by file reads. The SDK's session-selected configuration returns plugins; it is not a generic expose-every-core-option interface. A Renulus host must configure the actual discovery/services path deliberately. [Instance options][O-INSTANCE], [SDK instance configuration][O-INSTANCES]

Selecting capabilities is different from removing their implementation/dependencies. Disabling a coding tool does not prove the filesystem/shell graph or its packages disappear from a build. The proposed initial adoption retains the supported runtime dependency closure and trims exposed capabilities; physical pruning is justified only by a measured need and a supported composition route.

## Recovery, policy and lifecycle evidence

### Durable execution does not imply exactly-once external effects

OpenCode writes an execution claim with turn-start state. Stop and shutdown have distinct claim behavior. Interruption acknowledgement is distinct from waiting for idle or settlement; accepting cancellation is not proof that all owned work has settled. Its restart code explicitly documents at-least-once recovery; an external side effect may repeat after a crash. Running background shell work is marked cancelled during recovery rather than universally replayed. Child completion can be reconciled and wake a parent. An embedding host must also ensure recovery does not compete with another live owner of the same database. [Execution coordination][O-EXECUTION], [restart implementation][O-RESTART]

Pi commits a tool's intent before executing. Unsafe replay is the default. The recovery path reruns a call only if both recorded and current replay policies are safe; otherwise it settles an interrupted result. Initial calls run argument preparation/validation and beforeTool handling. A replay-safe recovery path does not repeat the entire initial hook/validation path. Renulus executors should therefore recheck current domain permissions/eligibility and implement idempotency where effects can repeat. [Durable tool task][P-TOOL]

These are different recovery contracts, not a blanket reliability ranking. Renulus needs explicit behavior for partial tool output, cancellation, orphaned work and side effects under its selected engine.

### A customization hook is not automatically a fail-closed policy gate

Pi's general hook runner reports ordinary handler errors and continues unless cancellation applies. Its beforeTool path separately converts failures into a blocked call. Therefore a throwing beforeRequest hook alone is not evidence of reliable model-route denial. [Scheduler hook dispatch][P-SCHEDULER], [tool checks][P-TOOL]

OpenCode's hook failure types explicitly reserve a rejecting failure channel for tool execute.before. Provider/model transforms and request hooks are useful customization points, but their existence does not demonstrate complete denial behavior under plugin failure, reload, recovery or auxiliary requests. [Hook contracts][O-HOOKS], [model registry][O-MODEL], [model request construction][O-MODEL-REQUEST]

The proposed Renulus rule is to enforce selected subscription/model/tool policy where actual provider dispatch and domain execution occur. Validate ordinary turns, child agents, title generation, compaction, retries and resumed work. A filtered model menu or a hidden tool schema is insufficient evidence on its own. This is a proposed engineering requirement, not a claim either upstream currently enforces Renulus-specific rules.

### Startup, instance selection and storage ownership

Current OpenCode SDK instance selection reconstructs plugin configuration from saved session metadata before capability use, including recovery. Same key and Location share an instance; a different Location separates it. The selection mechanism is explicitly not authorization or storage isolation. Default SDK storage is in-memory unless a persistent database path is supplied. [SDK lifecycle documentation][O-SDK], [instance implementation][O-INSTANCES]

Renulus should own the lifetime of one managed local harness host for the relevant profile/store. Startup must install required policy before resumed work, and shutdown must close owned resources. The appropriate Windows host process, Node/Bun/Electron compatibility and native dependency packaging were not proven in this side chat. The SDK's in-process transport does establish that an externally listening daemon is not inherently required. [Host implementation][O-HOST]

### Context, instructions and deletion

OpenCode has a persistent session instruction ledger with handling across context lifecycle changes. Its compaction implementation includes coding-oriented defaults. Session hooks allow context changes and a supplied compaction result, but changing the primary agent prompt alone does not establish that every summarization path now follows Renulus learning rules. [Instruction lifecycle][O-INSTRUCTIONS], [compaction implementation][O-COMPACTION], [session hook contract][O-SESSION-HOOKS]

Pi also has real compaction tasks and customization hooks. Conversation reset/compaction and retention/deletion must be distinguished. The inspected storage-write union does not expose deletion of conversation/entry records; this is a gap to design or verify, not proof that a host could never delete stored data. [Pi compaction][P-COMPACTION], [storage contract][P-TYPES]

OpenCode's recursive session-removal path is useful machinery, but does not automatically delete Renulus source originals, learner records, derived memory/vector indexes or backup copies. End-to-end retention remains a Renulus responsibility whichever execution engine is used. [Session removal][O-SESSION]

## Speed, simplicity and maintenance claims

The benchmark found in Pi's repository discussion compared Pi 0.80.6 with OpenCode 1.17.20 on Windows, using a small number of coding/MCP runs. It reported lower prompt/context traffic for Pi and discussed caching/configuration complications. It did not test OpenCode v2 or this Renulus design, and its author limited the generality of the results. It cannot substantiate “Pi is faster than OpenCode v2 for Renulus.” [Firsthand benchmark report][BENCHMARK]

Unmeasured in this side conversation: Windows cold start, steady-state memory, bundle size, model/tool overhead after Renulus configuration, time to first output, retrieval latency, cancellation latency, failure rates, recovery correctness in the packaged product, upgrade burden and long-term maintenance cost.

The relevant simplicity question is total complexity owned by Renulus. A smaller upstream core can require more integration code; a broader runtime can require more adaptation and dependency knowledge. The recommendation weighs those opposing costs based on the requested feature set. No numerical score or agent-vote count was used as proof.

## Recommended adoption method

| Method | Work Renulus would own | Judgment |
| --- | --- | --- |
| Borrow ideas only | Rebuild coordination, persistence integration, permissions, delegation and context lifecycle. | Poor starting choice if the goal is to reuse a full harness. |
| Extract selected internal files | Reconnect shared state, dependency and lifecycle assumptions; maintain a divergent runtime. | Avoid as the initial approach. |
| Embed the supported runtime and select capabilities | Implement Renulus policy, tools and domain integration while retaining upstream coordination. | Recommended proof candidate. |
| Adopt the entire OpenCode application | Carry its application/client flows alongside Renulus's own product. | Not required by the harness goal. |

Use an exact version/build, retain upstream attribution and patch provenance, and prefer the supported SDK/plugin interfaces. If a small core patch is necessary, keep it explicit and separately reviewable; do not treat a growing source fork as cost-free. A package pin must identify the complete relevant dependency set, not merely a moving v2 branch. [Published dependency set][O-PACKAGE], [embedded interface][O-HOST]

“Directly, but only needed parts” means selecting the tools, agents, integrations and product-facing behavior Renulus needs while keeping the runtime's required implementation connected. It does not initially mean copying a runner file and a tool registry out of the repository.

## Proposed ownership and integration

This is a proposal, not an implemented architecture or newly confirmed dependency selection.

| Owner | Responsibilities |
| --- | --- |
| OpenCode execution runtime | Agent loop, operational sessions/transcripts, tool execution lifecycle, execution events, child coordination, recovery and conversation context lifecycle. |
| Renulus harness module | Local host startup/storage/shutdown; a small caller interface for submit, resume, observe, permission response and cancel; mapping of Renulus identifiers to sessions. |
| Renulus plugins and executors | Learning roles, instructions, selected-model configuration, domain tools, evidence-aware context preparation, learning summaries and enforcement at dispatch/execution. |
| Existing Renulus Python domain modules | Document ingestion, source eligibility/currentness, retrieval, learner memory, reviewed assessment, learning records and canonical storage. |
| Desktop and future clients | Presentation and user interaction through the harness/domain interfaces, without implementing another agent loop. |

The harness should be usable without the desktop UI. A bundled local TypeScript host with defined IPC to existing Python modules is a possible packaging arrangement; the process/runtime choice is still an engineering decision to verify. “Local host” does not imply an owner-operated online service or setup work for doctors.

Use native tool registration for internal functions such as search_library, read_passage and get_learning_progress. Use MCP where an external compatible integration benefits from MCP. Avoid adding a protocol hop to every internal function without a concrete need.

Keep one authoritative owner for each record type. OpenCode can own execution/session state while Renulus owns library/learning records, linked by identifiers. Do not maintain two writable authoritative transcripts or a parallel custom scheduler merely to wrap the SDK. Ordinary deterministic operations, such as listing library items or recording a reviewed answer, should not require an agent turn just to cross a module interface.

If OpenCode is adopted for a conversation, migrate context ownership deliberately from the current Hermes adapter; do not run two independently authoritative compaction loops for it. Preserve reusable domain modules and source policies rather than rewriting them in TypeScript solely because the execution engine changes language.

Start with a managed runtime directory and learning identities in Renulus records/session metadata. Restrict unnecessary coding tools and discovery, replace coding-specific instructions and summary behavior, select only approved integrations, and retain the upstream dependency graph until measurements justify further pruning. Directory or instance keys are not an access-control sandbox.

The small Renulus interface should hide actual lifecycle and policy complexity. It should not become a large one-to-one facade over every upstream method, nor a speculative universal adapter for engines that have not been selected. The codebase-design skill informed this interface recommendation; it did not supply evidence of upstream behavior.

## What to retain from Pi if OpenCode is selected

These are design lessons, not a proposal to install both execution engines:

- Explicit capability assembly: keep the visible model/tool/role set small and intentional.
- Clear dependency injection: keep provider policy and domain executors supplied by Renulus.
- Small context inputs: include relevant source passages and instructions deliberately; measure prompt overhead.
- Explicit replay semantics: classify effectful operations and make retries/idempotency visible in executor contracts.
- A small client interface over durable state: clients should display execution rather than reconstruct its lifecycle.
- Clear ownership of child work and cancellation: verify foreground/background behavior through the selected engine's actual contract.

Pi's durable task/state-machine abstraction remains a reason to reconsider it if arbitrary persisted workflows become a dominant requirement. It is not automatically necessary to add a second task engine for the currently stated agent needs.

## Proof needed before an adoption decision

No item below was executed in this side conversation. These are proposed checks, not completed acceptance evidence or a request to run paid providers.

1. Package the exact candidate for Windows with managed dependencies and no doctor setup; verify clean startup, lifetime ownership, shutdown and persistent reopen.
2. Run a connected learning flow using real tool interfaces: retrieve eligible passages, cite sources, delegate a bounded child task and stream parent/child progress.
3. Verify selected-model/subscription policy for primary turns, children, titles, compaction, retry and recovery; fail closed when the required route or policy module is unavailable.
4. Exercise cancellation and interruption at model streaming, tool execution, child waiting and result persistence. Observe settlement and recovery, including repeated external-effect handling.
5. Compact a long educational conversation while preserving source identifiers, relevant facts, learner corrections and open questions; reacquire required instructions correctly.
6. Verify domain tool rights and source eligibility at execution time, including resumed/replayed work and changes in eligibility.
7. Verify deletion/temporary-conversation behavior across runtime state, canonical records, originals, derived indexes and backup policy.
8. Measure cold start, memory, package size, prompt/tool overhead and interaction latency on the selected configuration. Compare equivalent workflows if performance determines the choice.
9. Identify every required upstream patch and the supported upgrade path. Reconsider the foundation if the changes replace the core machinery being adopted.

A first connected proof can establish integration feasibility, but it does not justify narrowing Renulus's product to one nephrology topic or claim whole-product acceptance. Subsequent verification must span varied domains and required text/PDF/image workflows.

## Recording validation

The document's citation definitions were checked for missing, unused and duplicate references. Formatting checks covered trailing whitespace and the final newline. All five cited Renulus files were compared with the recorded commit and matched after line-ending normalization. The repository's read-only workspace check, python -B scripts/check_workspace.py, passed. These are documentation/workspace checks, not evidence that either proposed harness integration has been implemented or tested.

## Evidence index

All upstream code links below are pinned to inspected commits. Registry and release links identify the exact version observed. Local implementation evidence links use the inspected Renulus commit, making the claims independent of later working-tree changes. The links support the adjacent claims above; recommendations and proposed checks are explicitly identified as inference or future work.

[P-RELEASE]: https://github.com/earendil-works/pi/releases/tag/v1.1.0
[P-PACKAGE]: https://registry.npmjs.org/@earendil-works%2Fpi-durable/1.1.0
[P-AGENT]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/agent/src/agent.ts
[P-SDK]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/sdk.md
[P-SECURITY]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/docs/security.md
[P-DURABLE]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/README.md
[P-HARNESS-TYPES]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/types.ts
[P-REGISTRY]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/registry.ts
[P-TOOL]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/tool.ts
[P-SCHEDULER]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/scheduler.ts#L1131-L1143
[P-TYPES]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/types.ts
[P-COMPACTION]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/durable/src/harness/compaction.ts
[P-APP]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/experimental/durable/README.md
[P-PROMPT]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/experimental/durable/prompt.ts
[P-SUBAGENT]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/src/experimental/durable/subagent.ts
[P-SUBAGENT-EXAMPLE]: https://github.com/earendil-works/pi/blob/abe508e1b89912adde45528136c3221eb69acdd7/packages/coding-agent/examples/extensions/subagent/README.md
[O-COMMIT]: https://github.com/anomalyco/opencode/commit/4b6fea2875e4f2e3e8a8fee181803e54f7056845
[O-COMPARE]: https://github.com/anomalyco/opencode/compare/55dde8810d8a859c0a21e42491ae7d5801fb49ef...4b6fea2875e4f2e3e8a8fee181803e54f7056845
[O-PACKAGE]: https://registry.npmjs.org/@opencode%2Fsdk/2.0.26
[O-TAG-HOST]: https://github.com/anomalyco/opencode/blob/9b4ec5714d481559990db0a816d5dec19541a814/packages/sdk/src/internal/host.ts
[O-TAG-PROMISE]: https://github.com/anomalyco/opencode/blob/9b4ec5714d481559990db0a816d5dec19541a814/packages/sdk/src/promise.ts
[O-SDK]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/sdk/README.md
[O-HOST]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/sdk/src/internal/host.ts
[O-PROMISE]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/sdk/src/promise.ts
[O-EFFECT]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/sdk/src/effect/opencode.ts
[O-INSTANCES]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/sdk/src/internal/instances.ts
[O-ROUTES]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/server/src/routes.ts
[O-INSTANCE]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/instance.ts
[O-PROJECT]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/project.ts#L317-L358
[O-PLUGIN]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/plugin/src/README.md
[O-PLUGIN-CONTEXT]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/plugin/src/promise/plugin.ts
[O-TOOL]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/plugin/src/promise/tool.ts
[O-SESSION-HOOKS]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/plugin/src/promise/session.ts
[O-INTERNAL]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/plugin/internal.ts
[O-SUPERVISOR]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/plugin/supervisor.ts
[O-HOOKS]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/plugin/hooks.ts
[O-MODEL]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/model.ts
[O-MODEL-REQUEST]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/model-request.ts
[O-EXECUTION]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/execution.ts
[O-RESTART]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/execution/restart.ts
[O-SUBAGENT]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/tool/plugin/subagent.ts
[O-PERMISSION]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/permission.ts
[O-COMPACTION]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/compaction.ts
[O-INSTRUCTIONS]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/instructions.ts
[O-SESSION]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session.ts
[O-MCP]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/mcp/index.ts
[O-SKILLS]: https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/skill/instructions.ts
[BENCHMARK]: https://github.com/earendil-works/pi/discussions/6646
[R-BRIEF]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/PROJECT_BRIEF.md
[R-WORKSPACE]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/docs/WORKSPACE.md
[R-GENERATION]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/generation.py
[R-TRANSPORT]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/runtime/hermes.py
[R-CONTEXT]: https://github.com/houraniiiii/Renulus/blob/528025ff0b22477c12ee1512e0e7d15297a6e888/runtime/renulus/runtime/context.py
