# Renulus decisions

Updated on 2026-10-10. The [recorded user answers](planning/2026-10-04-user-answers.md)
are the evidence for the new product decisions. Earlier assistant suggestions
remain proposals unless accepted here.

## Confirmed choices

### October 10 superseding harness direction and Design C closeout

The owner selected **OpenCode v2 for the next harness migration**, retaining
Design C and the Python domain/data services. OpenCode will own execution,
migrated transcripts, tools, children and context. The current working Hermes
adapters remain until their H-ticket replacements are connected; this selection
does not authorize migration implementation in the Design C task.

The Design C task completed the bounded connected UI closeout and committed
integration handoff at `c2bd8964`, including the H00 retrieval-guard repair. That
closeout did not pursue a separate exhaustive Hermes Windows release or default cutover.
DC21 final delivery is deferred to combined H20 acceptance, with all DC
requirements retained as regression obligations. The normal launcher, owner
profile and credentials stay unchanged. See the [scope amendment](planning/DESIGN_C_IMPLEMENTATION_SPEC.md#october-10-scope-amendment--connected-ui-and-opencode-handoff)
and [exact read-only planning snapshot](implementation/opencode-plan-snapshot/README.md).

The snapshot preserves proposed migration choices separately from confirmed
decisions and newer canonical work. It does not authorize new model roles,
plugins, MCP controls, schedules or configuration authorities here.

### October 10 first OpenCode foundation implementation authorisation

The owner's later instruction authorises the first important foundation tickets.
The integration task selected **H01 and H24** from
`c2bd896420fb88f76d63ca576414dbbba182f4c2` in the isolated foundation worktree.
Both now have **local foundation acceptance**, recorded in the
[implementation handoff](implementation/OPENCODE_FOUNDATIONS_HANDOFF.md).
The existing planned public domain/conversation and Harness test seams were
accepted by the instruction; no new seam approval or tracker publication was
needed. H00 is consumed. H02 is planned next, and the other uncompleted H tickets
remain planned. Live account, migrated-client and packaged acceptance remain open.

The [recorded instruction](planning/2026-10-04-user-answers.md#october-10-first-opencode-foundation-implementation-authorisation)
sets the lane, synthetic-state and hidden-testing boundaries. It supersedes the
historical research-only restriction for this first implementation wave;
DC21/H20 release gates and the immutable snapshot remain unchanged.

| Subject | Decision |
| --- | --- |
| Identity | Renulus; an independent open-source project. |
| Repository | `houraniiiii/Renulus`, with independent history beginning at bootstrap commit `8917ce4`. Its sole remote is `origin`. |
| Audience | Nephrologists practising in the EU; learning throughout specialisation is the central use. |
| Language | English first. Other EU-relevant languages may follow later. |
| Platform | Windows application only, for personal computers. |
| Breadth | Support education across nephrology for practising nephrologists. Single-subject-first scope, including acid–base-first, is explicitly rejected. |
| Curriculum | General nephrology topic organisation with an ESENeph examination track; national programme mappings where useful. No first national programme selected. |
| Purpose | Topic understanding, cases, examination preparation and guided study, supporting active learning and staying current. |
| Sessions | Short visits throughout the day and focused study sessions. |
| Modes | Separate Chat/Explain and Test. |
| Questions | Reviewed bank for scored assessment; generated questions for practice. |
| Memory | Automatically retain useful deduplicated learning points, progress and preferences; inspect/edit/delete controls are required. |
| Conversation retention | On October 9, the owner requested saved chats and context by default, an Archive option, and optional temporary conversations. This supersedes temporary-by-default case discussion context. The changed default and archiving remain implementation work; see the [dated preference](planning/2026-10-04-user-answers.md#october-9-conversation-retention-preference). |
| Personal library | Reusable uploaded study material, organised by topic with passage/page citations; separate from one-off cases. |
| Workspace sizing | On October 10, the owner confirmed an adjustable Workspace width, with a default wider than the current Design C prototype. ChatGPT/Codex, T3 Code and Hermes desktop layouts are interaction references. Exact widths and resize limits remain engineering choices; see the [dated Workspace decisions](planning/2026-10-04-user-answers.md#october-10-workspace-sizing-and-file-readers). |
| Workspace file readers | Render and read PDF, DOCX, CSV, XLSX, Markdown, HTML, XML and images within the Workspace. These are confirmed format requirements, not evidence of implemented preview or ingestion support. Additional formats remain unconfirmed. |
| Teaching behaviour | Direct Explain by default, with optional guided teaching and deeper explanations. |
| Study planning | Adaptive plan from goals, time, optional exam date and observed mistakes; free exploration and manual changes remain available. |
| Source lookup | Automatically look up selected reliable sources when evidence/freshness matters, with citations, dates and visible retrieval failure. |
| Source register | One development register in [SOURCES](SOURCES.md), covering public, non-commercial, member, institutional, personal and research access, with developer acquisition, user acquisition and update methods. |
| Source currency | Use the latest published final guidance for its scope, with corrigenda and chapter replacements. Drafts, superseded/expired guidance, retractions and unverified-current material must have distinct states. |
| ERA acquisition | The owner reports follow-up calls confirming ERA's willingness to support at least user-responsible downloading. Plan for doctors to obtain authorised ERA material through their own access and import it locally; record the supplied edition and applicable use scope. |
| Optional retrieval keys | Allow user-supplied API keys for web search, literature search and related retrieval tools. These are optional, explicitly enabled tool connections, including paid services where selected by the user; they do not change the subscription/model allowlist or create a paid generation fallback. |
| New chat | The October 9 C decisions replace introductory filler with a chosen-name greeting and "How can I help you today". Keep Attach and three actions (Explain a topic, Discuss a case, Quick practice), each revealing five daily personalised suggestions; remove Auto and the redundant navigation/follow-up copy. Details and adaptable interactions are in the C spec. |
| Interface target | On October 10, the owner selected Design C to replace the current Flow UI, incorporating the later navigation, chat, retention, Tests and Workspace decisions. The [Design C implementation spec](planning/DESIGN_C_IMPLEMENTATION_SPEC.md) is the consolidated ticket plan; its labelled planning defaults remain adaptable. |
| Daily practice | Interactive educational discussion of daily practice cases is in scope. |
| Input methods | Text, summaries, PDFs, images and other useful methods; typed-only scope is not accepted. |
| Updates | Guidelines and selected important research. |
| Models | Use existing models; no retraining or fine-tuning. |
| Subscription access | OpenCode Go and/or Codex subscriptions. |
| Allowed Codex models | GPT 6.1 Sol, GPT 6 Astra, GPT 6 Luna. |
| Allowed OpenCode Go models | MiMo V2.6 Pro, DeepSeek V4.1 Flash. |
| Model control | Automatic choice within the selected subscription and allowed/available models, with manual override; no silent subscription switch. |
| Operations | Open-source harness; the project owner will not host a service or model inference. |
| Background document models | Small CPU models for embeddings/OCR may be bundled and managed entirely by Renulus, with no GPU, Docker, model server or setup for doctors. Conversation and other generative work keep the selected subscription/model rules. |
| Backend preference | Straightforward integration of suitable existing components. |
| Harness direction | Renulus primarily provides data, retrieval, tools, execution and subagents, with the application as a client. The owner selected OpenCode v2 on October 10; the earlier Pi recommendation remains historical research. Initial H01/H24 implementation is now authorised as recorded above. |
| Backend foundation | OpenCode v2 is selected for the harness migration using supported embedding/configuration and minimal necessary changes. The Design C baseline still uses the attributed Hermes integration. Preserve reusable Python domain modules, upstream licences/provenance and working adapters until their replacements are connected. |
| Harness configurability | Models by purpose, routing/fallback policies, subagents, instructions, skills, MCP and plugins must be reliably adjustable. Target 128K–256K context with developed context/memory management; actual limits remain route-specific validation work and later tickets remain planned. |
| Future providers/local inference | Plan for additional providers and optional vLLM/Ollama connections later. This does not require doctors to run a model server, change current selected subscription defaults or authorise incidental inference/provider charges. |
| Learner-memory engine | Retain Mem0 OSS and its local Qdrant client; no Qdrant server is required. Existing code uses Hermes's in-process integration. The OpenCode plan retains the Python memory adapter and canonical records, routing extraction through the new harness when its owning slice is connected. |
| Document pipeline | Docling structured CPU conversion and Docling-core HybridChunker for ingestion, OCR, tables, chunking and source-item provenance. One primary pipeline; validate on varied nephrology material. |
| Embeddings | FastEmbed with a pinned app-managed CPU model and tokenizer. Exact weights remain an engineering selection; BGE-small is an evaluation baseline. |
| Document retrieval | LanceDB OSS for embedded full-text/vector search and hybrid ranking. |
| Personalised and conversation context | Retain canonical learner memory and its approved engines. Migrated conversations will have one OpenCode context owner replacing the Hermes compressor while preserving scope, evidence, corrections and retention. Keep the current hooks/compressor for unmigrated consumers. Hierarchical history ideas remain an evaluated strategy, not a confirmed algorithm. |
| Record authority | Canonical source and learner records stay in local SQLite. Mem0/Qdrant and LanceDB representations are derived and rebuildable. |
| Supermemory | Excluded from adoption by the user in the later 2026-10-04 research round; the reusable engine itself must be open source. Earlier evaluation remains dated evidence. |
| Delivery standard | Real working product. Prototypes inform production work; mock screens, hardcoded responses and disconnected modules do not establish completion. |
| Current Windows acceptance | On October 5, 2026 the owner chose an unsigned build installed and validated on the current Windows PC. A signing identity and a separate clean PC/VM are not required for this delivery. Matching source/artifact provenance, bundled runtime with developer tools absent from the app PATH, installation, shutdown/reopen, recovery and connected journeys remain required. Signing and separate clean-machine tests are optional future distribution work. |
| Development app control | On October 6, 2026 the owner requested app-scoped Playwright/Electron control through MCP so testing can continue while they use the same PC. Use hidden, non-focusable test windows, a separate synthetic profile and its owned backend. App screenshots and renderer input replace shared desktop control for UI work. Native Windows installation, dialogs and external handoffs retain separate acceptance scopes. See [app control](implementation/APP_CONTROL.md). |
| Historical October 6 delivery disposition | The owner accepted the then-runnable local Windows app with the selected Codex `subscription_limit` documented. That handover did not establish successful generation or full product validation. Its failed receipts remain historical; it is superseded by the resumed October 7 scope below. |
| Resumed October 7 delivery | The owner restored access and resumed full delivery, explicitly approving OpenCode Go personal-agent use and real validation of the exact selected models. Sol learning/capture and both Go Case discussions now have source evidence; installed acceptance remains separate. No model/subscription fallback or credential transport is authorised. Finish the connected flows, content coverage, Windows usability and matching release; see [current finish scope](implementation/FINISH_20261007.md). |
| Work organisation | Staged vertical implementation slices, clear module ownership, parallel worktree plan and multiple adversarial review waves. |
| Licensing | MIT for Renulus's own code; CC BY 4.0 for original Renulus teaching content. Permissive commercial reuse with attribution; third-party terms remain independent. |
| Design workflow | Figma with Impeccable and Interface Design. |
| Review | User and assistant lead review and validation using concrete evidence; no external-panel prerequisite. |
| Brand | C — Renal flow, with the selected teal treatment; modern medical, calm, precise and approachable, with a subtle renal reference. |
| Separation | Preserve the inherited clinical MVP and batch/research project outside the active repository. The normal desktop launcher opens Renulus; the optional legacy reference launcher stays separate. |
| Current scope | The first OpenCode foundation tickets H01/H24 have local acceptance from the completed Design C handoff `c2bd8964`. H02 is planned next; remaining tickets stay planned. Preserve the connected UI and Python domain owners. DC21 final default delivery remains deferred to H20. |
| Historical implementation heartbeat | The October 5 owner instruction selected one 20-minute heartbeat for that implementation run; its 15- and 30-minute predecessors are historical. This record does not create or reactivate an automation for the C handoff. |

## Unresolved work

H01/H24 have local host, store, IPC and worker-settlement evidence. Clean-checkout
reproduction, packaged delivery, production routing, memory/context migration
and complete paired-store recovery still require their later-ticket evidence.
The foundation handoff retains 18 classified inherited backend failures; it does
not claim a green broad suite. The stage/architecture documents remain
adjustable engineering baselines; product choices above stay confirmed. Current
working flows, actual acquired-data checks, selected-engine verification and
remaining delivery/account gates are recorded in `docs/implementation/` and
GitHub issues #1–#12. Earlier planning descriptions are not completion claims.

Hermes integration and Windows packaging, source/content acquisition, curriculum
mapping detail, attachment processing, memory deletion semantics and content
coverage require engineering work. Round 3 has settled the major interaction
behaviour. The later research round excludes Supermemory and accepts invisible,
app-managed CPU embeddings/OCR. The October 4 selection was **Hermes + Mem0
OSS + Docling/HybridChunker + FastEmbed + LanceDB OSS**. The later OpenCode choice
replaces the future execution foundation while retaining those data engines.
Compatible version pins, model artifacts, provider routing, CPU
footprint and retention/citation behaviour still need implementation evidence.
See the [framework comparison](research/2026-10-04-context-framework-recommendation.md)
and [decision evidence](research/2026-10-04-starting-stack-evidence.md).
No major user decision is currently pending; engineering checks are recorded in the
[planning decision queue](planning/DECISION_QUEUE.md).

The engineering baseline reuses Hermes's existing Electron/React desktop
foundation and Python runtime. SQLite holds canonical records; Mem0 provides
learner-memory processing, Docling/HybridChunker supplies structured passages,
FastEmbed supplies CPU vectors, and LanceDB supplies document hybrid search.
The earlier SQLite/FTS5-only library baseline is superseded. Selection does not
establish functioning integrations. Follow the [stage plan](planning/IMPLEMENTATION_PLAN.md),
[architecture](planning/ARCHITECTURE.md) and [parallel-work rules](planning/PARALLEL_WORK.md).

Earlier module proposals, UI studies and clinical MVP choices do not become
current requirements through preservation.

The October 10 Workspace requirements leave the exact default width, minimum
and maximum widths, behaviour on smaller windows and persistence of the user's
chosen width unresolved. Specify and verify the reader for each confirmed file
format, including supported image extensions. Visual preview and content
extraction for model use need separate implementation evidence; recording a
format does not establish either capability.

Licence selection is complete. Add licence files and scope notices with source
and content adoption before distribution. Preserved development tooling
retains its own licences, recorded in [third-party notices](../THIRD_PARTY_NOTICES.md).

The [source register](SOURCES.md) is the single current development list; dated
research shortlists do not override its edition and acquisition records. Individual
files still need their own provenance, currency and operation-specific use records.
No acquired teaching corpus, validated assessment set, educational-effectiveness
result or clinical-performance result is established by this cleanup.

## Dated evidence

On October 7, 2026 the owner resumed full delivery and explicitly confirmed
OpenCode Go use for Renulus as a personal learning agent. Remove the earlier
app-imposed learning-eligibility pause and its active warning copy. The app
approval is not a claim of a separate vendor confirmation. Validate the exact
`mimo-v2.6-pro` and `deepseek-v4.1-flash` models through the existing Renulus
connection, with the truthful Renulus User-Agent and stable conversation header.
Approved model catalogues are advisory; preserve the selected exact model and
report actual authentication, quota and model rejection without fallback.
Real account results and matching installed acceptance remain evidence tasks.
This supersedes the October 5 precautionary Go release decision.

On October 6, 2026 the app-scoped development controller completed a real
39-operation MCP journey with hidden, unfocused windows, synthetic Case
save/reopen without duplication, ESENeph track selection, cancelled native
backup and owned shutdown/disconnect cleanup. An interactive local MCP
client separately completed seven Library/control operations and normal
close. This is the default development control path while the owner uses
the PC. Existing-chat MCP code caching is recorded with a validated local
client alternative. These receipts establish source-app control; physical
dialogs, installed/live generation and PDF/image journeys keep separate
acceptance. See [the control report](implementation/app-control-20261006.md).

On October 6, 2026 the owner requested removal of image-input capability probes
and selection from the exact approved models inside Renulus. Codex model
catalogue presence is advisory: an approved exact model may be selected even
when omitted from the display catalogue. A real `gpt-6.1-sol` request through
the existing Renulus connection succeeded despite that omission. Connections
stores the chosen default model for Explain and generated practice; Cases can
override it within the same approved list. Documented text/image modalities
replace prerequisite probes. Actual authentication, quota, model or image
rejections remain visible without automatic retries, fallback models or
subscription changes. This supersedes the earlier observed-capability
prerequisite; it does not establish clinical image accuracy.

The [reference shelf](../references/README.md) preserves selected public-source
links, vocabulary and observations from earlier notes. Their recorded cutoffs
are part of their provenance. They are not confirmed product decisions, current
clinical advice or evidence of permission to use the underlying content.

The [workspace guide](WORKSPACE.md) records the independent repository and archive
boundary. The [brief](PROJECT_BRIEF.md) states the current product direction.
