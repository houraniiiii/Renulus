# Hermes adoption for Renulus

Accessed **2026-10-04**. Planning and public-source inspection only; no upstream
code, installer, test, authentication flow or inference was executed. Public
source was acquired under ignored `.local/research/`. The user's latest
instruction confirms the Hermes fork and all seven round 3 recommendations;
older planning files that call them proposals are superseded by that instruction.
Implementation choices below remain engineering recommendations.

**Adopt the verified upstream, with a narrow application boundary.** The intended
project is [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent).
The `main` head returned during this review was
[`af90026aa09949579bd423d24def3d38f743cde0`](https://github.com/NousResearch/hermes-agent/commit/af90026aa09949579bd423d24def3d38f743cde0),
committed **2026-10-04 13:49:41 UTC**. This immutable snapshot, not moving `main`,
anchors the findings. Its actual [LICENSE][license] is MIT, copyright 2025 Nous
Research: retain the copyright and permission notice with reused code. Dependency
and content licences remain separate. MIT permits this downstream fork; it does
not establish subscription entitlement or medical-content reuse rights.

**Reuse the engine; keep product rules in Renulus.** Hermes already exposes
`run_agent.AIAgent`, streaming/event callbacks, interruption, provider transports,
tool dispatch, compaction and session persistence. Its documented integration
surfaces include Python embedding, ACP, TUI JSON-RPC and HTTP/SSE. The HTTP server
is a gateway to the general agent, with session, tool and browser-control
surfaces; it is not an education-specific restricted backend. [Agent API][agent],
[integration documentation][integration], [HTTP adapter][http].

The minimal controlled entry is native Python
`AIAgent(...).run_conversation(...)` in a Renulus-owned child process. Supply an
explicit provider/model, `enabled_toolsets=[]` initially, context, retention
class and streaming callbacks; retain upstream interruption and `close()`.
A small process contract can expose start/continue, stream, cancel and completion
without rewriting the loop in .NET or requiring owner-operated hosting.

**An existing desktop shell is relevant:** upstream `apps/desktop` already uses
Electron/React, bundles Python 3.14, and launches
`hermes serve --host 127.0.0.1 --port 0`. Reuse its process-lifecycle and packaging
modules if adopting Electron; its general-agent workspace is not established as
a better doctor interface. Keep the proposed controlled entry instead of exposing
stock management routes. Renderer selection remains after product logic.
[Desktop manifest][desktop-package], [backend launch module][desktop-backend],
[desktop documentation][desktop-readme].

**Subscription integration is partly reusable.** The Go plugin already declares
`opencode-go`, `OPENCODE_GO_API_KEY` and
`https://opencode.ai/zen/go/v1`. The [official Go endpoint table][go] includes
`mimo-v2.6-pro` and `deepseek-v4.1-flash`. However, the plugin's auxiliary default
is `glm-5`, outside Renulus's allowlist. Auxiliary selection also has catalog
and fallback logic. Configuring the main model alone is insufficient.
[Go implementation][go-code], [auxiliary resolver][aux].

Hermes's Codex provider uses Responses and maintains its own OAuth store, separate
from the Codex application's credentials. Its pinned authentication code uses a
fixed client ID and `https://chatgpt.com/backend-api/codex`. Current [OpenAI plan
usage documentation][siwc] describes app registration and consent; its
[inference contract][siwc-inference] requires the public
`https://api.openai.com/v1/responses`, `store:false`, `stream:true`, and an
account-specific model catalog. These are different integration contracts.
Reuse the transport where compatible, but adapt authentication and endpoint
resolution to that documented flow; do not transplant another application's
tokens. The optional Codex app-server runtime introduces another agent/tool and
history layer, so leave it disabled. [Hermes authentication][auth],
[auth constants][auth-constants], [Responses transport][responses],
[app-server thread creation][codex-thread].

Enforce exact provider/model pairs at every outbound model call, including
compaction, titles, vision and memory extraction: Codex `gpt-6.1-sol`,
`gpt-6-astra`, `gpt-6-luna`; Go `mimo-v2.6-pro`, `deepseek-v4.1-flash`. Intersect
them with account availability. Automatic selection and manual override operate
inside the selected subscription; exhaustion or unsupported input produces a
recoverable error. Pin auxiliary routes and reject unapproved fallback routes.
Do not infer attachment support or entitlement from a catalog entry.

**Controlled tools are feasible, but defaults are unsuitable.** Source selection
distinguishes `enabled_toolsets=None` (all) from an explicit list; the conversation
loop validates requested tools against `valid_tool_names`. This is a useful
enforcement seam. It is not an OS sandbox. [Tool selection][tool-selection],
[call validation][tool-validation].

Start with an empty list, then register only bounded Renulus actions: retrieve
eligible passages, fetch approved public sources and propose structured learning
updates. Exclude terminal, arbitrary filesystem access, browser/computer control,
code execution, delegation, messaging, cron, plugin installation and skill
authoring. Enforce the same allowlist at dispatch, including deferred tools.
Use a separate Renulus home and sanitized environment, disable context-file
loading and lazy installation, and load only packaged, reviewed plugins/skills.
Do not start the stock gateway or allow local configuration to expand authority.
Plugin discovery and imports happen during initialization, before a model's
tool call, so hiding UI controls alone cannot establish this boundary.
[Initialization][init], [plugin discovery][plugins].

**Retention needs an explicit runtime policy.** Built-in memory defaults to
editable `MEMORY.md`/`USER.md`; background review is enabled. `skip_memory=True`
does not prohibit the built-in store when the memory toolset is explicitly
enabled. Session persistence is independent: the stock HTTP factory always passes
`session_db=self._ensure_session_db()`. Bare `AIAgent` defaults to no database,
but recall can open one later. No complete public no-save contract is established
by the reviewed switches. [HTTP factory][http-factory], [defaults][defaults],
[memory initialization][init], [recall helper][agent].

The transient baseline is `session_db=None`, `skip_memory=True`,
`skip_background_review=True`, `skip_context_files=True`,
`save_trajectories=False`, with memory/recall tools excluded. These reduce
side effects; the additional write paths below still require enforcement.

More critically, error handling writes request-body debug dumps after secret
redaction, and large tool results spill into `cache/spillover`. Neither is a
guarantee that raw case details are absent. Document extraction also has temporary
file paths. Disabling history, verbose logging or trajectory export alone cannot
meet explicit Save. [Request dumps][dumps], [spill storage][spill],
[document extraction][extract].

Add a retention policy honored by persistence, recall, compaction archives,
diagnostics, spills, attachments and memory hooks. Case and unclassified input
remain transient until explicit Save; do not rely solely on an LLM to classify
sensitivity. Disable native memory, background review, skill mutation, external
memory providers and trajectory export for those sessions. Save promotes only
the selected case/attachments into application-owned records. Ordinary study
history can reuse SessionDB. Automatically retain editable learning evidence,
preferences and abstract takeaways through a separate structured contract;
raw cases must never become implicit long-term memory. Reuse the memory-provider
interface for access to canonical Renulus records, rather than maintain two
competing stores. [Memory interface][memory-interface], [persistence][persistence].

**Library and current evidence need application logic, not another model stack.**
Hermes supplies SQLite/FTS5 session search, bounded file memory, document-to-text
extraction and image plumbing. Core recall does not require an embedding model.
Its optional Mem0 configuration introduces separate LLM/embedder/vector-store
dependencies; do not enable it. Reuse extraction behind imported-document IDs,
then add provenance, page/section locators, rights, versions and library search
with SQLite FTS5. Scanned PDFs and image interpretation need a verified route
through an allowed model; disable hosted Firecrawl OCR. [Search][search],
[extraction][extract], [Mem0 configuration][mem0].

Reuse the keyless DDGS search adapter, but add selected-source fetching, date
checks and passage citation rules. DDGS supplies search, not document extraction;
disable automatic provider discovery/rescue and paid extraction routes. Queries
must contain educational concepts, not case details. Retrieval failure must
remain visible. [DDGS source][ddgs], [web routing][web], [rescue routing][rescue].

Supermemory remains a candidate. Its maintained Hermes plugin is now external;
at [commit `91405dd00fdf2a0b3515b25c25557598f6793299`][sm-commit], source defaults
to hosted Supermemory and `auto_capture:true`, sending completed turns through
`documents.add`. Hosted use requires another account; local use requires its
server. Neither is necessary for the initial library or learning records.
Leave it disabled; any future adoption must establish permitted hosting,
dependencies and retention first. [Plugin source][sm-code], [setup][sm-readme].

**Native Windows is now an upstream path.** The current guide documents native
Windows 10/11 and optional WSL; the upstream MSIX has the narrower Windows 11
22H2 requirement. Source includes Windows stdio handling. The package metadata
allows older Python for upgrading, but explicitly identifies **3.14** as the
supported runtime. Package the chosen native runtime and required dependencies;
do not make doctors install WSL, Git or a developer toolchain. Upstream's support
claim is not a completed Renulus installation test. [Windows guide][windows],
[stdio implementation][stdio], [dependency manifest][dependencies].

**Maintain the fork inside the sole Renulus repository.** Recommend a pristine
vendored upstream snapshot plus a small, documented patch series for policy,
retention and authentication, with Renulus's adapter and learning modules outside
it. Record upstream URL, commit, archive digest and notices. Update by acquiring
the next pinned archive in an isolated worktree, reviewing the upstream diff,
reapplying patches and passing the same acceptance checks. Keep the last working
pin for rollback. Disable upstream self-update in the installed product. This
preserves `origin → houraniiiii/Renulus`, independent history and one release
owner without another remote or a separately administered fork repository.

The high-impact release gates are subscription/authentication compatibility,
enforcement of model/tool/retention policies, and native Windows packaging with
the agreed inputs. No new major user question is needed. Deliver actual usable
stages, with no single-subject restriction:

1. **Working Explain application:** native launch, subscription onboarding,
   direct/guided explanation, automatic/manual model selection, source inspection,
   cancellation and recoverable limits across CKD, glomerular disease, dialysis
   and transplantation. Verify forbidden calls cannot dispatch.
2. **Working cases and library:** text/PDF/images, explicit case Save, reusable
   study documents and citations. Synthetic case markers must be absent from
   durable files after ordinary completion, forced errors, compaction and restart.
3. **Working learning cycle:** separate deterministic reviewed-bank assessment
   and generated practice, editable memory, adaptive plan, free exploration and
   resume. Hermes supplies orchestration; scoring, curriculum and progress are
   Renulus-owned rules.
4. **Complete maintained product:** compact Ask/Resume/review/updates home,
   current-source workflows, coverage review, installation, upgrade/restore and
   accessibility. Each stage requires working user journeys, not a feature list.

**Source matrix — all URLs accessed 2026-10-04.** “Reuse” is an engineering
classification of inspected interfaces, not a test result. Hermes links are
pinned to `af90026aa09949579bd423d24def3d38f743cde0`.

| Area | Inspected primary source / exact locator | Source fact and proposed treatment |
| --- | --- | --- |
| Identity and licence | [Repository commit](https://github.com/NousResearch/hermes-agent/commit/af90026aa09949579bd423d24def3d38f743cde0), [LICENSE][license] | **Reuse unchanged:** MIT engine with notices; keep upstream provenance. |
| Agent and headless use | [run_agent.py, constructor][agent], [integration guide][integration], [API server][http] | **Reuse unchanged:** agent loop, callbacks and interruption; **adapt:** narrow local host contract. No versioned standalone SDK compatibility guarantee was established. |
| Existing desktop modules | [Electron/React manifest][desktop-package], [native headless launch][desktop-backend], [desktop README][desktop-readme] | **Reuse candidate:** native runtime lifecycle and packaging already exist. Retain Python; restrict the backend boundary before reusing the general-agent shell. |
| Go subscription | [Go provider profile][go-code], [official endpoint table][go], [auxiliary resolver][aux] | **Configure/adapt:** existing Go transport; remove `glm-5` helper default and enforce exact allowlist. |
| Codex subscription | [auth_codex.py][auth], [auth_constants.py][auth-constants], [Responses transport][responses], [OpenAI registration overview][siwc], [inference contract][siwc-inference] | **Adapt:** app-owned consent/authentication and public endpoint; existing legacy OAuth support does not establish compatibility. |
| Optional Codex runtime | [Codex app-server thread creation][codex-thread] | **Disable:** separately managed threads/tools; reviewed creation path does not request ephemeral storage. |
| Tool control and plugins | [model_tools.py, `_select_tool_names`][tool-selection], [validation][tool-validation], [initialization][init], [plugin discovery][plugins] | **Configure + enforce:** explicit allowlist and packaged extensions; preserve validation, prevent broader discovery/dispatch. |
| Memory and skills | [defaults][defaults], [memory initialization][init], [MemoryProvider][memory-interface] | **Configure/adapt:** disable automatic raw capture/self-improvement; reuse extension interface for editable learning records and reviewed teaching skills. |
| Persistence and compaction | [session persistence][persistence], [context compressor][compressor], [compression coordinator][compression], [recall helper][agent] | **Reuse ordinary-session mechanisms; patch transient policy:** summarization and retained/archived history are different operations. |
| Non-history writes | [request debug writer][dumps], [tool-result spills][spill], [temporary extraction][extract] | **Patch:** no unsaved-case content in diagnostics, cache or retained extraction files. Secret redaction is insufficient. |
| Search and embeddings | [session search][search], [Mem0 configuration][mem0] | **Reuse FTS5 primitives:** no embedding requirement for this route. **Missing:** a provenance-aware study-library index. |
| Evidence lookup | [DDGS adapter][ddgs], [web selection][web], [rescue][rescue] | **Reuse/configure:** search adapter; **adapt:** selected-source fetch, freshness and query filtering. DDGS has no extraction backend. |
| PDF and image input | [read_extract.py][extract], [vision tools][vision], [dependency manifest][dependencies] | **Reuse/configure:** extraction/image handling; **verify/adapt:** scanned PDFs, locators, transient processing, model capabilities. |
| Supermemory candidate | [external plugin commit][sm-commit], [source][sm-code], [README][sm-readme] | **Do not adopt:** additional service plus default automatic turn capture; no necessity demonstrated. |
| Native Windows | [native guide][windows], [Windows stdio code][stdio], [pyproject.toml][dependencies] | **Reuse platform support; package and verify:** WSL is optional, Python 3.14 is the supported runtime, MSIX/source support differs. |
| Educational product | [upstream architecture](https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/website/docs/developer-guide/architecture.md) compared with Renulus's confirmed brief | **Missing application logic:** reviewed assessment, curriculum, learning evidence, library rights/provenance and adaptive-study rules. No clinical or educational efficacy inferred. |

[license]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/LICENSE
[agent]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/run_agent.py#L263-L331
[integration]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/website/docs/developer-guide/programmatic-integration.md
[http]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/gateway/platforms/api_server.py
[http-factory]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/gateway/platforms/api_server.py#L2416-L2440
[desktop-package]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/apps/desktop/package.json
[desktop-backend]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/apps/desktop/electron/backend-command.ts
[desktop-readme]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/apps/desktop/README.md
[go]: https://opencode.ai/docs/go/
[go-code]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/plugins/model-providers/opencode-zen/__init__.py
[aux]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/agent/auxiliary_client.py#L781-L835
[siwc]: https://developers.openai.com/siwc/token-sharing-open-source
[siwc-inference]: https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference
[auth]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/hermes_cli/auth_codex.py
[auth-constants]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/hermes_cli/auth_constants.py#L70-L91
[responses]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/agent/transports/codex.py#L711-L729
[codex-thread]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/agent/transports/codex_app_server_session.py#L263-L304
[tool-selection]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/model_tools.py#L315-L341
[tool-validation]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/agent/turn_tool_validation.py#L73-L145
[init]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/agent/agent_init.py
[plugins]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/hermes_cli/plugins_discovery.py
[defaults]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/hermes_cli/config_defaults.py
[dumps]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/agent/agent_runtime_helpers.py#L1593-L1640
[spill]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/tools/tool_result_storage.py
[extract]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/tools/read_extract.py
[memory-interface]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/agent/memory_provider.py
[persistence]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/agent/session_persistence.py#L435-L533
[search]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/tools/session_search_tool.py
[mem0]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/plugins/memory/mem0/README.md
[ddgs]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/plugins/web/ddgs/provider.py
[web]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/tools/web_tools.py
[rescue]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/tools/web_tools_rescue.py
[sm-commit]: https://github.com/supermemoryai/hermes-supermemory/commit/91405dd00fdf2a0b3515b25c25557598f6793299
[sm-code]: https://github.com/supermemoryai/hermes-supermemory/blob/91405dd00fdf2a0b3515b25c25557598f6793299/__init__.py
[sm-readme]: https://github.com/supermemoryai/hermes-supermemory/blob/91405dd00fdf2a0b3515b25c25557598f6793299/README.md
[windows]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/website/docs/user-guide/windows-native.md
[stdio]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/hermes_cli/stdio.py
[dependencies]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/pyproject.toml
[compressor]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/agent/context_compressor.py
[compression]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/agent/conversation_compression.py
[vision]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/tools/vision_tools.py
