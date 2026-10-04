# Renulus product answers

Recorded on 2026-10-04 from the user's answers in rounds 1–3 and the subsequent
framework research and stack selection. This is a faithful
record of the substantive decisions, with conversational wording normalised for
project documentation. It supersedes earlier assistant assumptions about a
hosted service, browser/mobile delivery and a workflow that could not discuss
daily practice. Framework approval is recorded in its dated follow-up below;
application implementation is not authorised by this documentation request.

## Round 1 — initial product direction

| Answer | Confirmed direction |
| --- | --- |
| 1. Users and curriculum | Nephrologists practising in the EU. The first product is English only. Other languages relevant to the EU may be added later. |
| 2. Main purpose | Support all four activities: understanding topics, practising cases, preparing for examinations and following a study programme. The central purpose is assistance throughout education and learning during specialisation. |
| 3. Use throughout the day | Support short visits and focused sessions, with particular emphasis on active study, learning and staying up to date. |
| 4. Teaching behaviour | Separate Chat/Explain and Test modes. |
| 5. Questions | Use a reviewed question bank for scored assessment. Generated questions serve practice. |
| 6. Personalisation | Remember what matters without redundant information. The exact memory and retention rules still need design. |
| 7. Daily practice | The product is educational and interactive. Users should also be able to ask about cases encountered in daily practice. It should not be limited to static reports. |
| 8. Platform | Windows application is the final and only product platform. |
| 9. Operating model | Open-source harness application. The project owner will not host a service or run model inference for users. The previous hosted-service funding question was based on an incorrect assumption. |
| 10. Review and collaboration | The user and assistant will develop, review and validate the work together. Work should be direct and practical, without repeated generic medical disclaimers or an invented requirement for an external review panel. |

The existing name Renulus, selected C — Renal flow logo, calm and approachable
medical character, existing-model approach and no-retraining decision remain in
force. The user wants Figma design work informed by Impeccable and Interface
Design, and a straightforward backend that adopts suitable existing components.

## What round 1 did not decide

This section records the boundary at round 1. Round 2 below now settles the
subscription providers, model list, curriculum direction, input formats and
personal-PC target.

An open-source harness does not by itself select an API, subscription connection,
local model engine, endpoint or model. No mandatory local GPU or model download
has been requested. The author-operated inference service is excluded; the
connection methods and onboarding experience remain to be selected.

Daily-practice discussion is confirmed. Importing identifiable patient files,
persisting a clinical record or integrating with hospital systems has not been
requested. Input formats, source access and what crosses a model-provider boundary
remain concrete product decisions.

The EU audience does not select a particular examination, a validated curriculum
or a separate consultant/trainee interface. The retained taxonomy remains a
historical reference. No external question-bank delivery, permission or society
endorsement follows from these answers.

User-and-assistant review is the working process. It does not make generated
answers or question keys correct by declaration: source checks, reproducible
examples and observed software behaviour provide the evidence for each claim.

Research recommendations and unresolved decisions are tracked separately in
[the planning decisions](DECISION_QUEUE.md).

## Round 2 — confirmed decisions

Recorded later on 2026-10-04. These answers supersede conflicting suggestions
in the first planning/research notes.

| Answer | Confirmed decision |
| --- | --- |
| 1. Model access | Existing subscriptions through OpenCode Go and/or Codex. Allowed Codex models: **GPT 6.1 Sol, GPT 6 Astra, GPT 6 Luna**. Allowed OpenCode Go models: **MiMo V2.6 Pro, DeepSeek V4.1 Flash**. This is the explicit provider/model list; do not silently substitute models or add other providers. |
| 2. Curriculum | Accept the recommendation: general nephrology topic organisation with an **ESENeph examination track**, followed by specific national programme mappings where useful. No first national programme has been named. |
| 3. Inputs | Support multiple methods, including **text, summaries, PDFs and images**, with other useful formats within the intended broad input experience. A typed-only product or blanket attachment deferral was not accepted. Exact additional formats, size limits and processing behaviour remain engineering/design work. |
| 4. Staying current | Include **guidelines and selected important research**. |
| 5. Computers | Target **personal Windows computers**. |
| 6. Breadth and sequence | Renulus must support education across nephrology and be useful to practising nephrologists broadly. The proposal to perfect acid–base or any single subject first is **rejected**. Build reusable capabilities across domains; do not let a demonstration subject become the product scope. |

Broad capability does not claim an already complete reviewed bank or guaranteed
accuracy. Content coverage must be visible and developed across domains.
Technical testing may use individual examples, but feature acceptance must
include varied nephrology subjects and cross-topic questions.

Subscription choices are confirmed product requirements. Authentication,
account-specific model availability, usage-limit behaviour and attachment
capabilities still need implementation verification. No paid API fallback,
local-model requirement or automatic provider switching has been approved.

Round 2 does not adopt the earlier proposed session-only case retention,
automatic memory capture or offline behaviour merely by accepting input formats
and personal computers. These remain explicit design choices or proposals.

## Round 3 — all seven recommendations accepted

The user explicitly accepted every recommendation in the preceding seven-row
question round. These are confirmed product behaviour:

| Subject | Accepted decision |
| --- | --- |
| Model selection | Automatically choose among allowed, available models within the user's chosen subscription, with an easy manual override. Do not silently switch subscriptions or use an unapproved/billed fallback. |
| Learning memory | Automatically retain progress, preferences and useful deduplicated learning points. Users can inspect and edit them. |
| Raw case retention | Raw daily-practice cases and attachments persist only after an explicit Save. |
| Personal library | Users can add uploaded study documents to a reusable personal library, organised by topic, with passage/page references in answers. One-off case attachments remain separate. |
| Teaching | Explain answers directly by default. Offer optional guided teaching and deeper explanations. Test remains separate. |
| Study planning | Offer an adaptive plan using goals, available time, an optional exam date and observed mistakes. Preserve free exploration and manual changes. |
| Evidence lookup | Automatically look up selected reliable sources when evidence or freshness matters, with citations and dates. Indicate failed retrieval or unverified information. |
| Opening screen | A compact home with Ask, Resume, suggested review and relevant updates, plus quick access to topics and Test. |

Explicit-only case retention must also govern derived transcripts, extraction
caches and logs; this is its implementation consequence. It is not a promise
about provider-side storage. Routine local study chat history, deletion/export
mechanics and memory correction are engineering details to specify consistently.

## Implementation-planning instructions

The same request adds these confirmed directions:

- Build a **real, working product**. Design alternatives and prototypes may guide
  implementation, but completion means working software rather than a mock
  screen or placeholder response.
- Write comprehensive, concise implementation plans in stages, with vertical
  slices and clear module ownership so changes and parallel worktrees stay local.
- Use several subagent waves, second opinions and adversarial review. Ask the
  user only for major decisions that evidence or reasonable engineering judgement
  cannot resolve.
- Adopt a **Hermes fork** as the backend foundation, preserving its upstream
  attribution and licence. Inspect what it already supplies before adding code.
- Reuse maintained existing work. Rebuild only where needed or where a concrete
  comparison shows doing so is simpler.
- Evaluate **Supermemory** for context/memory, ingestion, PDF extraction,
  chunking, embeddings, retrieval and personalised context. It is a candidate,
  not an accepted new hosted dependency or an approved licence change.

This request authorises implementation planning and public-source investigation.
It does not itself start model inference, deploy services or implement the app.

## Ownership decision during implementation planning

The user explicitly selected permissive reuse with attribution:
**MIT for Renulus's own code; CC BY 4.0 for its original teaching content**.
Commercial reuse is allowed without requiring derivatives to remain open.
Third-party material retains its own terms. This does not relicense imported
publications, user-uploaded documents or vendor packages.

## Memory and document-framework research round

Recorded later on 2026-10-04. The user requested deep web, public social-media
and GitHub research into reusable frameworks for memory, document ingestion,
RAG, PDF extraction/chunking/embeddings/vector search, personalised context
injection and context management.

- **Drop Supermemory from consideration for adoption.** The user requires the
  reusable engine itself to be open source, rather than only a public client or
  plugin. This supersedes the earlier optional-candidate status; retain the
  earlier research as dated evidence.
- Prioritise reliable, maintained open-source components that can be adapted
  with minimal changes and compatible distribution terms. Build Renulus-specific
  functionality where it adds value or closes a demonstrated gap.
- The intended experience is routine, day-to-day use by clinicians throughout
  their nephrology learning. Background processing and configuration should be
  handled by the application; doctors should not need technical setup or ongoing
  system administration.
- **Small CPU models bundled and managed entirely by Renulus for embeddings
  and OCR are accepted.** No GPU, Docker, model server or model setup is required
  of doctors. Conversation and other generative work continue through the
  selected subscriptions and allowed models. This clarifies the earlier
  no-local-runtime requirement; it does not authorise local conversational LLMs.

This round authorises research and a concrete framework recommendation for
finalising the plan. It does not select a replacement framework by implication
or authorise application implementation, model downloads or provider calls.

## Starting-stack approval after the research

Recorded on 2026-10-04 after the completed research recommendation. The user
explicitly accepted the strongest starting stack and requested that the planning
files be updated and the evidence kept in research. This supersedes the earlier
unselected-candidate status for these components.

| Capability | Confirmed starting stack |
| --- | --- |
| Runtime and conversation context | **Hermes**, including its memory-provider hooks, context selection and compressor |
| Learner memory | **Mem0 OSS**, using the existing Hermes in-process integration |
| Document ingestion, PDFs, OCR and structured extraction | **Docling**, configured for CPU and app-managed local artifacts |
| Chunking | **Docling-core HybridChunker**, preserving structure and source-item references |
| Embeddings | **FastEmbed**, with an explicit bundled CPU embedding model |
| Document keyword/vector search and RAG retrieval | **LanceDB OSS**, using embedded hybrid search |

The recommendation retains **canonical SQLite records** under Renulus ownership.
The initial Mem0 integration uses its existing **local Qdrant client** as a
derived memory index; LanceDB serves the document library. This is an integration
baseline, not a request for a Qdrant server or a second record authority.

Exact package versions, embedding weights/tokenizer, OCR backend/language data
and Docling layout/table artifacts remain engineering selections to pin and
verify. BGE-small-en-v1.5 is a research baseline, not a newly confirmed model.
The selected generative subscription/model rules remain in force for chat,
memory extraction, summarisation and other generative background work.

Docling is the selected primary pipeline. A bounded comparison with LiteParse
can resolve a demonstrated packaging, resource or extraction problem; it does
not reopen the entire stack decision. Cognee and the other investigated engines
remain alternatives, not additional dependencies.

This approval authorises documenting the selected stack and its implementation
work in the plan. It does not start application implementation, installation,
model downloads, inference or deployment. Preserve the
[research recommendation](../research/2026-10-04-context-framework-recommendation.md),
its supporting investigations and the
[stack evidence record](../research/2026-10-04-starting-stack-evidence.md).

## Source register, ERA downloads and optional retrieval API keys

Recorded later on 2026-10-04 from the owner's source-acquisition follow-up.

- The owner reports several calls with ERA and states that ERA will agree to
  support the project, at least through users being responsible for downloading
  the material themselves. This is confirmed planning input from the owner;
  record the edition, delivery format and applicable use scope when material is
  obtained. Keep private correspondence and supplied restricted files outside
  the public repository.
- Maintain **one development source list**, covering all usable access levels,
  rather than a list limited to content that can be bundled publicly. Include
  developer acquisition and a concrete user acquisition method for every entry.
- Use the latest KDIGO guidance and reliable maintained literature sources,
  including the open full-text subset associated with PubMed. Do not present
  superseded, expired, retracted or unverified-current material as current.
  Distinguish the latest published final guideline from a newer public-review
  draft; track corrigenda and chapter-level replacement.
- Where possible, doctors should be able to download the same eligible material
  themselves from an official link or supported dataset/API and add it locally.
  Membership/institutional/user access belongs in the same register with its
  relevant acquisition conditions.
- **Optional user-supplied API keys are accepted for web search, literature
  search and related retrieval tools**, including user-selected paid services.
  The app must retain a useful route without optional keys. Activation, provider
  selection and usage/cost controls are explicit; there is no incidental paid
  usage or silent newly billed fallback.
- Retrieval-tool credentials do not authorise other generative models, paid
  model API fallbacks, owner-hosted inference or model training. The selected
  subscriptions/models and temporary-case boundaries remain in force.

The [single source register](../SOURCES.md) contains the dated primary-source
verification and acquisition methods. Specific adapter priorities and check
cadences are engineering recommendations; no API integration, acquired corpus
or implementation is established by this planning update.

## Starting local source collection

Recorded later on 2026-10-04 from the owner's file-storage follow-up.

- The owner has ERA Neph-Manual files and wants a concrete place to add them,
  along with future dataset downloads. This authorises preparing acquisition
  folders; no files have been supplied or imported by this step.
- The assistant prepared an external collection at
  `%USERPROFILE%\Documents\Renulus-data`, with the manual in
  `raw/E01-era-neph-manual/` and separate `raw/E02-era-mcqs/` storage. Other
  acquisition folders use the same source-register IDs. Original filenames and
  editions are preserved, with provenance notes under `metadata/`.
- Proposed engineering default for the installed application:
  `%LOCALAPPDATA%\Renulus`, with a configurable library location and isolated
  per-worktree development profiles. This is a storage recommendation in
  response to the question; runtime configuration and import remain unimplemented.

## Automated source acquisition responsibility

Recorded later on 2026-10-04 from the owner's acquisition instruction.

- ERA Neph-Manual E01 acquisition belongs to the owner; leave its files and
  folder alone.
- The assistant is responsible for acquiring the remaining source material,
  using parallel subagents in waves, direct terminal downloads and suitable
  browser tools where needed. This explicitly authorises actual public-source
  downloads into the external collection, not just further source planning.
- Record acquired originals, actual editions, access/processing conditions,
  hashes, query coverage and concrete acquisition gaps. A source page, API
  sample or unavailable export must not be reported as a complete dataset.
- This acquisition instruction does not implement the app, authorise incidental
  billed provider calls or restore unspecified private/archive datasets.
