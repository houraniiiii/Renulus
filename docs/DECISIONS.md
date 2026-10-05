# Renulus decisions

Updated on 2026-10-05. The [recorded user answers](planning/2026-10-04-user-answers.md)
are the evidence for the new product decisions. Earlier assistant suggestions
remain proposals unless accepted here.

## Confirmed choices

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
| Case retention | Raw daily-practice cases and their attachments are retained only after explicit Save. |
| Personal library | Reusable uploaded study material, organised by topic with passage/page citations; separate from one-off cases. |
| Teaching behaviour | Direct Explain by default, with optional guided teaching and deeper explanations. |
| Study planning | Adaptive plan from goals, time, optional exam date and observed mistakes; free exploration and manual changes remain available. |
| Source lookup | Automatically look up selected reliable sources when evidence/freshness matters, with citations, dates and visible retrieval failure. |
| Source register | One development register in [SOURCES](SOURCES.md), covering public, non-commercial, member, institutional, personal and research access, with developer acquisition, user acquisition and update methods. |
| Source currency | Use the latest published final guidance for its scope, with corrigenda and chapter replacements. Drafts, superseded/expired guidance, retractions and unverified-current material must have distinct states. |
| ERA acquisition | The owner reports follow-up calls confirming ERA's willingness to support at least user-responsible downloading. Plan for doctors to obtain authorised ERA material through their own access and import it locally; record the supplied edition and applicable use scope. |
| Optional retrieval keys | Allow user-supplied API keys for web search, literature search and related retrieval tools. These are optional, explicitly enabled tool connections, including paid services where selected by the user; they do not change the subscription/model allowlist or create a paid generation fallback. |
| Home | Ask, Resume, suggested review and relevant updates; quick access to all topics and Test. |
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
| Backend foundation | Fork and adopt Hermes; retain upstream licence and acknowledge the fork. Reuse before building replacements. |
| Learner-memory engine | Mem0 OSS through Hermes's existing in-process integration. Initial derived memory storage uses its local Qdrant client; no Qdrant server is required. |
| Document pipeline | Docling structured CPU conversion and Docling-core HybridChunker for ingestion, OCR, tables, chunking and source-item provenance. One primary pipeline; validate on varied nephrology material. |
| Embeddings | FastEmbed with a pinned app-managed CPU model and tokenizer. Exact weights remain an engineering selection; BGE-small is an evaluation baseline. |
| Document retrieval | LanceDB OSS for embedded full-text/vector search and hybrid ranking. |
| Personalised and conversation context | Reuse Hermes memory-provider/context hooks and its existing compressor; Renulus controls scope, evidence and token budgets. |
| Record authority | Canonical source and learner records stay in local SQLite. Mem0/Qdrant and LanceDB representations are derived and rebuildable. |
| Supermemory | Excluded from adoption by the user in the later 2026-10-04 research round; the reusable engine itself must be open source. Earlier evaluation remains dated evidence. |
| Delivery standard | Real working product. Prototypes inform production work; mock screens, hardcoded responses and disconnected modules do not establish completion. |
| Work organisation | Staged vertical implementation slices, clear module ownership, parallel worktree plan and multiple adversarial review waves. |
| Licensing | MIT for Renulus's own code; CC BY 4.0 for original Renulus teaching content. Permissive commercial reuse with attribution; third-party terms remain independent. |
| Design workflow | Figma with Impeccable and Interface Design. |
| Review | User and assistant lead review and validation using concrete evidence; no external-panel prerequisite. |
| Brand | C — Renal flow, with the selected teal treatment; modern medical, calm, precise and approachable, with a subtle renal reference. |
| Separation | Preserve the inherited clinical MVP and batch/research project outside the active repository. The normal desktop launcher opens Renulus; the optional legacy reference launcher stays separate. |
| Current scope | Complete the backend, Flow frontend and connected Windows app in bounded parallel lanes and worktrees. GitHub issues hold the adjustable execution queue and evidence. |
| Heartbeat | Exactly one implementation heartbeat every 20 minutes, per the October 5 owner instruction; earlier 15- and 30-minute settings remain historical. |

## Unresolved work

Implementation is authorised and active. The stage/architecture documents remain
adjustable engineering baselines; product choices above stay confirmed. Current
working flows, actual acquired-data checks, selected-engine verification and
remaining delivery/account gates are recorded in `docs/implementation/` and
GitHub issues #1–#12. Earlier planning descriptions are not completion claims.

Hermes integration and Windows packaging, source/content acquisition, curriculum
mapping detail, attachment processing, memory deletion semantics and content
coverage require engineering work. Round 3 has settled the major interaction
behaviour. The later research round excludes Supermemory and accepts invisible,
app-managed CPU embeddings/OCR. The user subsequently selected **Hermes + Mem0
OSS + Docling/HybridChunker + FastEmbed + LanceDB OSS**. Component selection is
settled; compatible version pins, model artifacts, provider routing, CPU
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

Licence selection is complete. Add licence files and scope notices with source
and content adoption before distribution. Preserved development tooling
retains its own licences, recorded in [third-party notices](../THIRD_PARTY_NOTICES.md).

The [source register](SOURCES.md) is the single current development list; dated
research shortlists do not override its edition and acquisition records. Individual
files still need their own provenance, currency and operation-specific use records.
No acquired teaching corpus, validated assessment set, educational-effectiveness
result or clinical-performance result is established by this cleanup.

## Dated evidence

The [reference shelf](../references/README.md) preserves selected public-source
links, vocabulary and observations from earlier notes. Their recorded cutoffs
are part of their provenance. They are not confirmed product decisions, current
clinical advice or evidence of permission to use the underlying content.

The [workspace guide](WORKSPACE.md) records the independent repository and archive
boundary. The [brief](PROJECT_BRIEF.md) states the current product direction.
