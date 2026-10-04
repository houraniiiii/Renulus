# Renulus implementation architecture

Planning baseline · 2026-10-04. **This is a real product.** The interfaces below
must lead to working Windows flows, real data and real integrations. No
application code is implemented by this document. Confirmed product choices
and the approved starting stack are in [DECISIONS](../DECISIONS.md). Exact
versions, helper artifacts and adapter details still need integration evidence.

## Logic before frameworks

The doctor chooses a subscription, asks or studies any nephrology topic, brings
documents or a case, inspects the evidence, practises, and retains useful
learning. Renulus coordinates that experience. Hermes supplies the agent
runtime; reviewed content and deterministic application rules supply assessment,
retention and progress behaviour.

Use one desktop application with a local backend process. Keep a small,
versioned interface between the UI and that process. The renderer does not
receive provider credentials, write databases or invoke arbitrary agent tools.
Local process communication is not an owner-hosted application service.

The Hermes fork is the runtime foundation. Reuse its agent loop, supported
provider integrations, context/session machinery and suitable tool interfaces
where source inspection and acceptance checks support them. Configure or adapt
existing behaviour before introducing a replacement. Source acquisition,
licensing, exact integration points and Windows packaging are S0 work.

The user-approved knowledge and memory stack is **Mem0 OSS + Docling with
Docling-core HybridChunker + FastEmbed + LanceDB OSS**, behind Hermes. Reuse
Hermes's context selection/compressor and existing in-process Mem0 integration.
Docling is the primary structured document pipeline. The
[research evidence](../research/2026-10-04-starting-stack-evidence.md) records
the source seams, licence scope and remaining gaps. Approval selects the
components; it does not make their defaults suitable or prove the installed app.

## Authoritative records

| Record | Owner | Invariant |
| --- | --- | --- |
| Connection profile | Runtime foundation | References protected credentials, allowed models and explicit subscription preference; optional web/literature tool profiles have separate activation, provider and usage limits. Secrets never enter the renderer or learning exports. |
| Topic/objective and programme mapping | Content | Stable identity with editioned general-nephrology/ESENeph mappings. Topic availability is not completion evidence. |
| Source and document revision | Knowledge | SOURCES register ID, acquisition/access class, permitted operations, edition/publication/review/check dates, final/draft/current status, corrections and whole-document/chapter replacement links; imported user copies retain their own terms. |
| Passage | Knowledge | References document revision and page/section; transformations preserve a trace to original text/image. |
| Learning thread | Learn | Local study conversation with referenced evidence and model/connection identity; no case payload is silently converted to an ordinary stored thread. |
| Case session | Cases | Explicit transient or saved state, with every derivative inheriting that state. |
| Question version and reviewed key | Content | Published immutable version; corrections create a new version and can withdraw the old one. |
| Attempt | Assessment | Committed answer, fixed question version, assistance/exposure status and deterministic result. Generated practice is separately identified. |
| Learning record | Memory | Canonical identity, provenance and revisions; distinct contextual lessons can share a concept. Editing replaces derived summaries rather than duplicating them. |
| Study plan/checkpoint | Study | References evidence and manual preferences; completion comes from actual activity, not generated assertions. |
| Update entry | Updates | Links a publication/revision, review state, affected topics and checked-through date. |

Store authoritative learner records locally. A search index or provider memory
is derived, not a second authority. Schema migrations, durable IDs, correction
and deletion semantics apply before multiple worktrees write feature data.
SQLite holds these canonical records. LanceDB document indexes and Mem0 memory
representations are rebuildable derivatives with canonical IDs and revisions.
Start Mem0 with its supported local Qdrant client; this embedded index requires
no Qdrant server. It is not another authority for progress or learner facts.

## Local disk locations

The [source register's storage convention](../SOURCES.md#local-collection-and-storage)
keeps developer acquisition originals outside the checkout under
`%USERPROFILE%\Documents\Renulus-data`. Treat this collection as input: imports
preserve originals and record their hashes/provenance. Importing a selected file
must not automatically ingest sibling folders or reserved evaluation items.

The proposed installed-app default is `%LOCALAPPDATA%\Renulus`. Keep imported
originals and extraction artifacts in `library/`, canonical SQLite records in
`state/`, rebuildable LanceDB/Qdrant indexes in `indexes/`, and bounded disposable
files in `cache/`. A configurable library location accommodates large collections;
all module paths resolve through one platform-owned storage interface. Exact
filenames, relocation behaviour and engine path enforcement are S0/S2 work.
Temporary-case derivatives remain volatile under the existing retention rules.

Development and verification use explicit `.local/runtime/<profile>/` roots per
worktree/run. Point Hermes, engines, renderer state and helpers at that isolated
profile; do not share installed-user databases or writable indexes. A source
collection can be read as an explicitly selected input, with each run owning its
derived state. The external collection folders now exist; this document does
not establish a working importer or create an installed-app profile.

## Modules and change ownership

These are modules within one product. Each vertical module owns UI, behaviour
and its records. Paths are planned ownership, not existing directories.

| ID | Module and common change request | Owned paths | Public interface |
| --- | --- | --- | --- |
| F0 | Runtime/platform: connection, cancellation, install or runtime fix | upstream/hermes/; runtime/renulus/runtime/; apps/desktop/src/platform/; apps/desktop/src/modules/connections/; packaging/ | Connect, capability report, run/cancel, runtime status. |
| M1 | Learn: explanation layout, direct/guided teaching | runtime/renulus/learn/; apps/desktop/src/modules/learn/ | Start/resume learning, ask, change teaching style, inspect answer references. |
| M2 | Knowledge/library: file import, PDF viewer, evidence retrieval | runtime/renulus/knowledge/; apps/desktop/src/modules/library/ | Import/remove document, retrieve eligible passages, open cited location, report ingestion state. |
| M3 | Cases: case input, staged teaching, saved/temporary cases | runtime/renulus/cases/; apps/desktop/src/modules/cases/ | Start/discuss/reveal, save/delete case, produce generic learning evidence. |
| M4 | Assessment: tests, generated practice, scoring/review | runtime/renulus/assessment/; apps/desktop/src/modules/assessment/ | Start attempt, commit answer, reveal feedback, review/cancel session. |
| M5 | Memory: retained knowledge, progress evidence, corrections | runtime/renulus/memory/; apps/desktop/src/modules/memory/ | Capture eligible learning, retrieve context, edit/delete/export records. |
| M6 | Study/home: goals, adaptive plan, resume and home content | runtime/renulus/study/; apps/desktop/src/modules/study/ | Read home summary, update goals, propose/override plan, resume activity. |
| M7 | Updates: guideline/research feed and affected learning | runtime/renulus/updates/; apps/desktop/src/modules/updates/ | Check sources, list reviewed updates, save/read item, flag affected content. |
| M8 | Content maintenance/delivery: authoring, installed packs and versions | tools/content/; content/; runtime/renulus/content/ | Validate/review/publish, install/activate/withdraw packs, resolve pinned topic/item/case versions. |

An integration owner owns packages/contracts/, runtime/renulus/storage/,
apps/desktop/src/shell/, apps/desktop/src/ui/, global lockfiles and root build
configuration and cross-module tests/fixtures. F0 authors Hermes patches in
reserved work; the integrator reviews/merges them and never edits the same files
concurrently. Feature workers request a narrow shared change instead of
creating competing storage, routing, tokens or dependency setups.

The selected components follow those ownership boundaries:

| Component | Responsible owner | Boundary |
| --- | --- | --- |
| Hermes memory/context interfaces and subscription transport | F0; M1/M5 consume the contract | One approved generative route for chat, extraction and compaction; policy before upstream hooks |
| Docling, HybridChunker and LanceDB document retrieval | M2 | Structured extraction, tokenizer-aware chunks, source locators, library index activation and physical cleanup |
| Mem0 OSS and its local Qdrant index | M5 | Eligible capture, engine-to-canonical ID mapping, learner recall, corrections, history purge and reindexing |
| FastEmbed and shared helper artifacts | F0 packages/configures; M2/M5 consume | Explicit model/tokenizer identity, controlled CPU inference, offline assets and app-owned paths |
| Canonical SQLite schemas and dependency pins | Integration owner, with M2/M5 proposals | One migration/lockfile coordinator; engines cannot become independent record authorities |

M2 and M5 request changes to F0's Hermes adapter instead of independently
patching upstream files. Publish compatible embedding dimensions/token limits
and source/record IDs before those workers integrate indexes.

## Small interfaces with explicit guarantees

Use versioned JSON request/result/event schemas for process communication,
generated into renderer and backend types. A request carries an ID, operation,
payload and explicit context scope. A running operation emits ordered progress,
answer deltas, source references and one terminal result, failure or cancellation.
The UI ignores late events from cancelled/superseded runs.

Context scope distinguishes ordinary study, personal-library documents,
temporary case, saved case, generated practice and reviewed assessment.
Scope is application-owned; neither model output nor a retrieved document can
change it. Pass IDs and permitted references across modules rather than copies
of every transcript. Content/tool output is data, not authority to change
retention, model selection, file permissions or scores.

Mutating operations use idempotency keys. Record an answer and its learning
evidence atomically or through a retryable local outbox so a crash cannot double
score or lose progress. Ingestion has explicit queued/processing/ready/failed/
cancelled states; incomplete chunks are excluded from retrieval.
Before any asynchronous result commits, transactionally check operation state,
record revision, context scope and deletion marker. If cancellation wins before
commit, persist no result; if commit already won, report that outcome rather
than pretend it was undone. Retries read the recorded outcome. Temporary-case
operation metadata remains volatile. Exercise delete-during-ingest,
edit-during-summary and cancel-during-answer races, then restart and reindex.

M8 owns installed content-pack manifests and active-version lookup. Activation
is transactional and validates compatibility/licence/review status. Retain
versions referenced by attempts; withdrawal prevents new use without removing
historical evidence. Assessment, Cases and Study use this one repository rather
than implement independent pack readers.

Sources return actual retrieved passages plus locators. An answer cannot label a
source as checked when retrieval failed. Retrieval respects source-use rules,
revision and learner scope. Do not feed reserved test items into Explain or
practice generation; record repeat/assisted status when exposure is known.

## The difficult behaviours belong in application logic

**Temporary cases.** Select scope before composer autosave, file processing or
any model call. Provide explicit temporary-case entry and keep unclassified
input volatile. Adding a case to a study thread creates a temporary branch;
do not append case facts to its durable history. Case → Explain → practice
handoffs inherit temporary scope even when referencing saved library material.
Temporary case text, attachments, extracted chunks,
thumbnails, model/tool messages and compaction summaries stay out of persistent
Hermes sessions, caches, telemetry, ordinary chat history, learning exports and
backups. Preserve user-owned source files. A later Save performs one explicit
transition into local case storage. If an upstream path cannot honour this,
disable that path or adapt it before enabling the flow.

Auto-memory can retain a general learning principle without retaining case
facts. Its input should be scoped general evidence, not an unrestricted raw
case transcript. Tests use synthetic sentinel details and inspect every
app-owned persistence path. This controls Renulus retention; it does not claim
control over OS paging or a remote provider's retention.

**Memory corrections and deletion.** Editing changes the canonical record and
invalidates summaries/index entries. Deletion removes live derived copies and
queued work, creates a deletion marker and suppresses automatic recapture from
the same retained evidence. Reconcile available newer markers before reindexing
restored records. An older backup restored alone on a new installation cannot
know subsequent deletions: expose its date/limits and require deliberate import.
Distinguish live retrieval removal from physical purge of indexes and backups.
Mem0's inspected deletion retains previous text in SQLite history; its adapter
must purge applicable history as well as vectors. LanceDB can retain deleted
rows in old table versions until physical cleanup; M2 owns that cleanup policy.
Changing embedding dimensions builds and validates a new index before switching
the active revision; do not reuse the stock plugin's collection recreation as
a migration. Durable eligible-memory jobs must survive busy workers and restart
rather than rely on best-effort turn sync.

**Model selection.** Automatic routing uses the selected subscription,
allowlist, account capability report and the operation's needs. Prefer a tested
default; offer manual choice. On unsupported input, exhausted quota, failed
authentication or unavailable model, retain work and give a concrete recovery
action. No cross-subscription switch or newly billed fallback is implicit.
Title generation, compaction, memory extraction and other generative background
work obey the same model rules. Embedding/OCR components are separate engineering
dependencies: evaluate licence, resource use, packaging, data egress and cost.
Small CPU models bundled and managed entirely by Renulus for embeddings/OCR are
explicitly accepted in the later research round. No extra paid provider,
mandatory external service, GPU or user-managed inference setup is implicit.
FastEmbed is the selected embedding runtime. Pin the model, converted ONNX
weights, tokenizer, hashes and licences; BGE-small is only a research baseline.
Likewise pin Docling's non-generative layout/table/OCR artifacts and validate
their complete CPU/RAM/installer footprint. Disable generative enrichment and
implicit cloud model/parser fallbacks. No additional neural reranker is selected.

**Assessment.** Score published keys in code. Freeze session item/key versions.
Commit answers before feedback and persist exposure/assistance before revealing
help or entering contextual Explain. Exposure follows stable item/family identity
across cancellation, restarts and corrected versions. Keep fresh-unassisted,
assisted and repeat aggregates separate; generated practice has its own records.
Corrections retain historical versions and flag affected results. Distributed
open-source items are not a secret examination system.

**Adaptive study.** Use observable attempts, repetitions, objectives and explicit
preferences. A conversation establishes interest; it does not prove competence.
Keep scheduling logic explainable and manually overridable.

## Retrieval and context choices

Use reviewed source metadata and eligible source text, plus material deliberately
added to the user's library. Preserve file hashes, revisions, page/section
references and extraction confidence. Image interpretation and OCR are separate
operations; unsupported or uncertain extraction is visible.
The [single source register](../SOURCES.md) owns current source families, verified
edition snapshots, access levels and acquisition methods. Resolve its stable
publisher/API entry points at acquisition; folder dates and search snippets do
not determine edition or final status. User downloads and keyed retrieval enter
the same provenance/eligibility pipeline. M2 owns sources, M7 checks currency,
and M8 reviews affected teaching content.

Source status is independent of access and licence. Exclude superseded chapters,
expired guidance and retracted material from current-guidance retrieval. New
drafts remain labelled and do not replace published finals. Corrections and
replacements flag affected bank items without rewriting historical attempts.
An unreachable source becomes check-failed/stale after its verification window;
do not continue to label it current merely because a local copy exists.

Search/source checks use generic topic queries and never raw case details.
Dates distinguish publication, review and last check. Background checks run
inside the user's app, within known connection limits. Release-hosted content
packs are static distribution, not a Renulus inference service.

Use Docling structured conversion and HybridChunker with the selected embedder's
tokenizer. Retain document-item IDs, physical page indexes, printed page labels,
sections and bounding boxes where available; flattening to Markdown alone must
not discard the source mapping. Keep table headers, units, captions and footnotes
associated with their chunks. OCR recognises text; chart or clinical-image
interpretation remains a separate model-dependent capability.

FastEmbed supplies explicit local vectors. LanceDB's native full-text/vector
search and hybrid fusion serve the library, filtering by eligible scope and
active document revision. Stage an import/replacement before activating it;
failed or cancelled work cannot publish incomplete passages or erase the previous
active revision. This supersedes FTS5-only document retrieval. SQLite remains
the canonical-record store.

Mem0 supplies learner-memory extraction/update/recall through the existing
Hermes OSS plugin, adapted to F0's approved generative transport and the explicit
FastEmbed configuration. Automatic captures are eligible learning evidence, not
unrestricted transcripts; exact assessment progress remains deterministic.
Budget source passages and learner facts separately using Hermes's existing
memory/context hooks. Those hooks do not replace retention enforcement.
Verify paraphrases, abbreviations, personalised recall, corrected notes and
superseded documents across domains.

The evidence route is a registered literature source or Hermes search adapter
(DDGS or an explicitly enabled user-keyed tool) → eligible canonical source →
controlled fetch or authorised user import → eligible extraction → revisioned
passages → retrieval → references. Prefer supported PubMed/PMC/Europe PMC and
publisher interfaces to general web search for literature. Search results are
discovery records; retrieved eligible source passages support answer citations.
Use Docling for PDFs and scanned text/OCR, Trafilatura for eligible HTML where
needed, and PDF.js for viewing/page rendering. pypdf remains a possible narrow
fallback, not the primary ingestion pipeline. Clinical image interpretation
requires a verified allowed subscription-model route. Optional keyed search and
literature tools are allowed when explicitly configured, with protected keys,
request/cost limits and visible quota/auth failures. Keep a key-free route and
do not activate another billed tool silently. Public-URL content retrieval
offered by an explicitly enabled registered search tool follows its rights,
privacy and usage limits. Implicit hosted-reader/OCR and unapproved generative
rescue-provider fallbacks remain disabled; private documents use the selected
local ingestion/OCR path. Vendor-generated Answer/Research/summary products are
not approved generative routes.
Block local-file/private-network access, including through URL redirects.
Before enabling temporary-case inputs, verify parser/OCR paths do not persist
payloads, rendered pages or extracted text. Docling's Tesseract CLI route writes
temporary images in the inspected source; adapt it or use a verified safe local
route. Deleting a temporary directory later does not satisfy no-save behaviour.

Supermemory is excluded from adoption by the user's later instruction. Its MIT
public repo/plugin does not supply the complete separately distributed engine.
Retain [the earlier evidence](../research/2026-10-planning/supermemory-fit.md).
The user explicitly approved the strongest stack from the
[replacement-framework research](../research/2026-10-04-context-framework-recommendation.md).
That selection supersedes the earlier FTS5/pypdf-first baseline and is recorded
in the [user answers](2026-10-04-user-answers.md). LiteParse remains a bounded
alternative for a demonstrated document/packaging gap; Cognee and other engines
are retained research alternatives. No second extractor, memory engine or
orchestration framework is part of the selected baseline.

## Framework selection and reuse test

The desktop renderer is subordinate to Hermes integration, rich document
viewing, accessible controls, cancellation and installability. Reuse maintained
UI primitives, viewers, extraction/search libraries and installer tooling.
Keep Renulus-specific authoring, assessment, context-scope and study rules in
their modules.

Before adding a subsystem, record: existing upstream capability; exact gap;
licence/runtime fit; smallest adaptation; and its acceptance test. A replacement
requires a concrete reason such as unsupported behaviour, demonstrably smaller
maintenance burden or an incompatible dependency. “Cleaner from scratch” alone
does not justify discarding maintained code.

The engineering baseline reuses **Hermes's existing Electron/React desktop
foundation and Python runtime**. Adopt suitable lifecycle, packaging and control
modules; adapt the doctor UI in TypeScript and connect a controlled Python child
process through narrow validated messages. Do not launch the general HTTP
gateway or build another agent loop.

During source import retain the upstream snapshot as reference and map its
desktop files into the active apps/desktop fork with source-path provenance.
Only the downstream app is built; the upstream snapshot is an update baseline,
not a separately maintained second application. Record relocation/patches so
future upstream diffs can be applied to the correct files.

Bundle the native runtime; doctors need no developer tooling. S0 verifies this
baseline on Windows and records dependency pins. Details live in
[the staged plan](IMPLEMENTATION_PLAN.md). A successful mock or typecheck alone
never establishes completion.
