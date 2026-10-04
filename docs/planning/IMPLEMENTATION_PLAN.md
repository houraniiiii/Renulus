# Renulus staged implementation plan

2026-10-04 · Planning only. **Renulus is a real product. Every stage builds
working software that remains useful in the final application.** Figma concepts,
test fixtures and prototypes support decisions; none substitutes for working
connections, persistence, retrieval or assessment.

Rounds 1–3 and the subsequent starting-stack approval are recorded in
[user answers](2026-10-04-user-answers.md).
Use [architecture and module ownership](ARCHITECTURE.md) for changes to a
specific feature and [parallel work](PARALLEL_WORK.md) for worktree sequencing.
Only major unresolved user choices belong in [the decision queue](DECISION_QUEUE.md).

## Product and reuse commitments

- English-first Windows application for personal computers; broad nephrology
  learning, general topics and ESENeph. No subject-specific launch architecture.
- Separate direct/guided Explain, daily-practice and teaching cases, reviewed
  tests and labelled generated practice; real text/PDF/image input.
- Personal library, automatic editable learning memory, adaptive study,
  guidelines/research updates and a compact Ask/Resume/review/updates home.
- One [development source register](../SOURCES.md) across all access levels;
  latest-final editions, corrigenda, chapter replacement and authorised user
  downloads. Optional user-keyed web/literature retrieval is separately enabled
  from the selected generative subscriptions.
- Use the Hermes fork and the five selected models through the user's Codex
  and/or OpenCode Go subscriptions. No owner service/inference or model training.
- Adopt the approved **Mem0 OSS + Docling/HybridChunker + FastEmbed + LanceDB
  OSS** stack behind Hermes. Keep canonical records in SQLite and reuse Hermes
  context management. Initial Mem0 storage uses its embedded local Qdrant client.
- Bundle and manage CPU helpers inside the app; doctors need no GPU, Docker,
  model server or setup. Exact package/model/OCR artifacts need pinned evidence.
- Inspect upstream code before adding a subsystem. Retain upstream attribution,
  licences and revision provenance. Rebuild only an identified missing part or
  where a recorded comparison demonstrates a simpler maintainable result.

## Stages and dependencies

A stage is an integration milestone; a module is a continuing area of ownership.
Stages can contain parallel vertical slices. Stage completion requires an
observable working output, not merely merged scaffolding.

| Stage | Working result | Depends on | Principal owners |
| --- | --- | --- | --- |
| S0 — Adopt and prove the runtime | Pinned attributed Hermes, selected-stack packaging proof, controlled runtime, model capability report and cancellation | Confirmed brief, stack and source investigation | F0 + integration owner |
| S1 — Ask, explain and resume | Installed desktop opens, connects a selected subscription, answers across topics and resumes stored study work | S0 process/interface and persistence contract | M1 + F0 + design owner |
| S2 — Bring material and inspect evidence | Text/PDF/image ingestion, cited passages, reusable library and temporary/saved case behaviour | S1; M2/M3 can develop concurrently against frozen contracts | M2 + M3 + F0 |
| S3 — Test and learn from feedback | Original reviewed bank, real attempts, deterministic scoring, corrections and separate generated practice | S1 + versioned content contracts; content work begins during S0 | M4 + M8 |
| S4 — Remember and organise study | Correctable learning memory, evidence-based progress, adaptive plan and useful home | S2/S3 evidence and scope contracts | M5 + M6 |
| S5 — Stay current | Working source checks, reviewed guideline/research changes and links to affected learning | S2 source retrieval + M8 review + S4 records | M7 + M8 |
| S6 — Complete and release the product | Broad mapped content, finished cross-module flows, installer/update/restore, accessibility and documentation | Integrated S1–S5 | All owners; one release integrator |

Content, design and release engineering run throughout. S6 completes product
coverage and integration; it is not the first time earlier features become real.

## S0 — Adopt Hermes without losing its value

1. Record upstream URL, immutable source revision, licence, copyright and chosen
   maintained update baseline. Import the fork into a clearly owned source
   subtree; keep the Renulus origin and history. Do not replace this workspace
   with the old MVP or add its remotes.
   Add MIT code and CC BY 4.0 original-content scope notices, as selected by the
   user. Preserve third-party terms. Reuse the existing Hermes desktop lifecycle
   and packaging modules; record their relocation into the active desktop fork.
2. Map reused functions, configuration, small required patches and missing
   Renulus logic. Separate packaging/configuration changes from product modules.
   Keep upstream changes reviewable and small enough to update.
3. Run the minimal approved agent path in a controlled local process. Restrict
   enabled tools and secondary model calls in code/configuration. Disable
   unused general automation and any persistence inconsistent with case scope.
4. Establish versioned process schemas, durable IDs, one migration coordinator,
   per-worktree runtime directories and the first real storage path.
   Define optional retrieval-tool connection profiles with protected user keys,
   explicit activation, provider-specific quotas/request limits and usage/cost
   controls. Reuse suitable Hermes adapters; literature-source adapters follow
   the supported routes in SOURCES. Do not make a paid tool key a prerequisite
   or invoke billed providers incidentally during verification.
5. Prove installation and runtime start on a clean personal Windows machine.
   Establish the supported version/CPU baseline. Bundle necessary runtime
   dependencies; do not require doctors to set up a developer environment.
   Probe Docling native-text and local scanned-page OCR paths, FastEmbed offline
   loading, LanceDB local indexing and Mem0 local storage before depending on
   them in S2/S4. Verify image interpretation separately through the selected
   subscription paths.
6. Record a compatible package/source lock and artifact manifest for the selected
   stack: versions/revisions, hashes, tokenizer/language assets, native binaries,
   licences and app-owned paths. Inspect the exact Hermes/Mem0 package pair and
   map required transport, capture, deletion and reindex patches. Configure
   explicit CPU helpers and block default cloud embedders/parsers, generative
   enrichment and unapproved model fallback. M2/M5 consume these common contracts
   instead of selecting independent runtimes or downloading their own models.
   Set resource/latency targets and a shared synthetic corpus spanning CKD,
   dialysis, transplantation, glomerular disease and electrolytes/acid–base.

Define the release capability/coverage matrix in S0: exact five model identities,
advertised integrations, required input flows and broad topic objectives.
Each advertised subscription integration needs live evidence; every required
model-dependent flow needs a working approved subscription path. Account-specific
unavailability is an honest state, not a pass for a missing required capability.
Define database compatibility, refuse unsupported schema versions and prohibit
implicit downgrade. App rollback and restoring a data snapshot are different
operations; preserve newer deletion markers where available.

**Acceptance:** selected-subscription authentication, one real response per
available connection, honest unavailable-model status, streaming/cancel and
restart behaviour, no unapproved secondary model calls, and a synthetic
temporary-case sentinel absent from app-owned durable stores. Automated tests
may use recorded/fake providers; the live connection evidence is separate.
   No private credentials are read from another application's files.
The packaged helper components must load and perform a small extraction/OCR,
embedding and local-store round trip without developer tooling, a model server
or first-use asset downloads. Record installer footprint and peak CPU/RAM;
full document and memory correctness remain S2/S4 gates.

**Gate:** if native packaging or no-save isolation requires a substantial
unplanned rewrite, document the actual failing dependency before expanding
implementation. Resolve ordinary patches ourselves; escalate only a material
change to product operation, required software, costs or the chosen foundation.

## S1 — Real learning conversations

Build the production desktop shell, connection controls and learning view from
one design system. Explain answers directly; guided teaching is an explicit
interaction. Topic selection is unrestricted within nephrology. Add model
selection/override, streaming, stop/retry, source indicators and study history.
Use existing provider/session capabilities from Hermes through the F0 adapter.

The app stores deliberately scoped study threads locally and resumes them after
restart. Users can delete history. Set scope before autosave/import; unclassified
input stays volatile. Case input into a study thread branches into temporary
scope, which follows subsequent Explain/practice handoffs.
Source labels distinguish retrieved evidence from an answer not yet verified.

**Acceptance:** a doctor installs, connects, asks follow-ups in multiple domains,
switches teaching style, cancels, reopens and resumes. Offline/quota/auth errors
retain work with actionable recovery. No fake response is shipped behind Ask.
The development launcher targets this real build once it exists.

## S2 — Documents, evidence and daily cases

Develop library and cases in parallel with the same source/scope contract.
Use the selected Docling CPU conversion pipeline, Docling-core HybridChunker,
FastEmbed and LanceDB OSS. PDF.js supplies viewing/page rendering. Preserve
document-item references, original page/region locators and document revisions
through chunking and embedding; keep table headers, units and footnotes intact.
Use a chunk budget matched to the pinned embedder/tokenizer.

Stage extraction and indexing, then activate a completed eligible revision.
Failed/cancelled replacements retain the previous active revision. Retrieve
with LanceDB native full-text/vector search and hybrid fusion, including source
and scope filters. Reuse upstream/library transforms and ingestion primitives
where they save work; do not build another generic parser or vector engine.
Offer source-specific official download links and local import for authorised
ERA/member, institutional and personal material. Source identity, edition,
licence/use scope and current-status checks survive extraction and indexing.
Demonstrate the user-download journey with eligible public or synthetic files;
never use a shared developer membership as a distribution mechanism.
If Docling fails a defined resource/extraction target, compare LiteParse on the
same corpus with its chunking/provenance adapter. Keep one primary pipeline;
additional engines require a demonstrated gap and a recorded reuse decision.

Support direct text, text PDFs, scanned PDFs and image attachments. Distinguish
Docling/local OCR from clinical image interpretation. Route supported image
inputs through an allowed capable model; surface unavailable capability without
silently changing subscription or pretending extraction succeeded.

Library imports persist when deliberately added. Temporary case text, previews,
chunks, prompts, summaries and tool results do not enter persistent stores;
explicit Save changes that. Ask for relevant missing case facts. Add staged
synthetic teaching cases across different topic groups.

**Acceptance:** import synthetic documents, ask a source-grounded question, open
the exact cited page, replace/delete a document and observe updated retrieval.
Demonstrate successful text, text-PDF and scanned-PDF journeys through the
selected local pipeline, and image interpretation through a verified permitted
subscription path. Check page/region locators, reading order, extracted
units/tables and paraphrase/acronym retrieval across several documents and
editions. An unsupported-input message does not pass this gate.
Ask a freshness-sensitive Explain question without an upload: automatically
discover/fetch an eligible source, show its passage/dates, then repeat with
retrieval unavailable. No extra paid key or hosted reader is required.
Separately verify an explicitly selected retrieval-key adapter with synthetic
responses for auth/quota/cost-cap behaviour. Live optional-tool evidence uses
explicitly enabled access. All required learning flows retain a key-free path.
Handle malformed/encrypted/oversized files and cancellation. A temporary case
survives only the intended live session; a saved case resumes after restart.
No unsaved-case sentinel appears in logs, caches, memory, exports or backups,
including after forced errors, compaction, mode handoffs and crashes.
Inspect Docling/OCR temporary-file paths before enabling no-save cases; its
stock Tesseract CLI path writes rendered images. Deletion must remove eligible
derived rows and physically clean old LanceDB versions under the recorded
policy. Exercise delete-during-ingestion and prevent stale jobs from republishing.

## S3 — Real assessment and content production

Start original content authoring during S0, across the nephrology map. Reuse
maintained authoring/validation tooling; add the Renulus item schema, source
locators, review state and versioning. The user and assistant perform the review.
Published packs contain explicit topic coverage and original content-use terms.
Define measurable cross-domain targets before authoring: required objectives,
evidence/case/question coverage and review states. Missing material cannot be
hidden by lowering the target at release. M8 owns the runtime pack repository;
install and activate a real original reviewed pack through the app before
Assessment/Study acceptance. Preserve content versions referenced by attempts.

Build reviewed Test sessions, answer commitment, deterministic scoring, source
linked rationales, mistake review, pause/resume and assisted/repeat indicators.
Generated practice remains separately labelled and outside reviewed-score
aggregates. Do not retrieve reserved bank items into teaching context.

**Acceptance:** original reviewed items from varied domains produce reproducible
scores; a restart does not double-submit; hints are marked assisted; corrected
or withdrawn keys preserve and annotate historical attempts. Insufficient
published coverage is visible. Do not offer a complete exam simulation until
the chosen blueprint and required session length can actually be supplied.
Exposure follows stable item/family IDs across cancellation/restart and corrected
versions. Verify fresh-unassisted, assisted, repeat and generated-practice
aggregates remain separate after mode switching.

## S4 — Memory, progress and an adaptive study home

Reuse Hermes's in-process Mem0 OSS integration and context mechanisms. Route
Mem0 extraction/update generation through F0's approved subscription adapter,
configure the explicit FastEmbed model and use the local Qdrant client with
app-owned paths. Store canonical learning records and evidence in SQLite.
Use a durable idempotent capture queue; replace upstream best-effort sync that
can truncate/skip writes. Automatic capture receives eligible learning evidence.
Context injection uses relevant, scoped information within a budget. Merge duplicate records,
retain distinctions, and show provenance. Editing/deletion invalidates derived
summaries and retrieval entries, including queued regeneration.
Purge applicable Mem0 SQLite history as well as live vectors when deleting
records. Rebuild derived indexes from canonical records under a new index
version before activation; never recreate the live collection merely because
embedding dimensions change. Keep library evidence and learner facts distinct
in the context budget and show which retained record informs personalisation.

Combine objectives, attempts, mistakes, time and optional exam date into an
explainable plan. Users can move or skip activities and browse freely.
Home shows Ask, Resume, suggested review and relevant updates using real records.
Do not infer mastery from chat volume or display invented progress percentages.

**Acceptance:** a real mistake informs later study; a corrected learning record
changes subsequent context; deleted content stays excluded from live reindex,
queued capture and restore when a newer deletion ledger is available. An older
backup alone exposes its date and cannot promise later deletions.
Export versioned canonical records, provenance and eligible attachments without
credentials; restore them on a clean second installation and regenerate the
derived Mem0/Qdrant and LanceDB indexes using the recorded artifact identities.
Manual plan edits survive restart. Temporary-case facts do not become
personal memory. The home remains useful for a new user with no history.
Check abbreviation/paraphrase retrieval and personalised context across domains,
including corrected notes and superseded sources. Exercise deletion during
ingestion and correction during summarisation, then restart/reindex.
Check Mem0 history after correction/deletion, repeated capture without loss of
distinct lessons, subscription/quota failure recovery and local Qdrant behaviour
at the expected memory volume. Every generative background call uses the
selected subscription and exact allowed models.

## S5 — Current evidence and reviewed updates

Use selected official/publication sources, source-use eligibility and canonical
document identifiers. Run checks from the application at a bounded cadence;
save last-successful/failed check state. Prefer supported feeds/interfaces to
fragile page scraping. Requests contain topic queries rather than raw cases.
Use the latest-final and correction/retraction rules in SOURCES. Process
incremental literature updates and removals; track publisher guideline edition,
review/expiry and whole-document/chapter replacement. Preserve distinction
between a newly uploaded file, a new guideline edition and a public-review
draft. Follow current dataset distribution methods rather than deprecated FTP
assumptions. Optional search keys enrich discovery, not access rights.

Separate detected publication changes from reviewed educational update entries.
The assistant can draft an explanation of a change; publication through the
reviewed content workflow is explicit. Show publication, review and check dates,
affected objectives and source links. Keep preliminary findings distinguishable.

**Acceptance:** an eligible changed source is detected, reviewed, deduplicated,
displayed and connected to affected learning. Offline, failed fetch and stale
review states are accurate. A correction can flag a bank item without silently
rewriting its key or the learner's historical result.
Exercise a guideline chapter replacement, a draft published alongside a final,
a corrigendum and an article removal/retraction. None should leave superseded
passages labelled current; failed checks and restricted-source reimports are
visible and reproducible.

## S6 — A complete installable product

Maintain a coverage matrix for all adopted topic groups and ESENeph domains:
explanations/evidence, reviewed questions, cases and update sources. Define
launch coverage explicitly; track incomplete objectives and avoid claims that
the library already covers them. Expand breadth and depth together.

Run integrated journeys across domains and topics, including case → Explain →
practice/test → feedback → memory → plan → updates. Complete keyboard, screen
reader, text scaling, window resizing, loading/empty/error and reduced-motion
states. Compare implemented screens with Figma using the installed design skills.

Package signed releases with the selected dependency/model artifact inventory
and complete notices. Verify update authenticity and test install/upgrade/rollback,
database migration, backup/restore and
uninstall/data-retention behaviour. Use static release distribution; no owner
inference service is introduced. Publish plain-language onboarding and recovery.

**Acceptance:** a clean Windows installation completes the real journeys with
user-connected models, no developer tooling and no placeholder controls.
Every required cell in the adopted broad-domain coverage manifest is met;
unmet required coverage blocks complete-release status. Additional future
content may remain a roadmap item without redefining the target.
Release tests use synthetic data. Public signing identity/credentials are
obtained through the user's release setup, never invented or copied.

## Design and testing within every stage

Use Figma for complete flows and shared components. Impeccable guides clarity,
hierarchy and finishing; Interface Design guides consistent product controls
and tokens. Keep one design system and retain Renal flow. Prototype alternatives
against the same contracts and synthetic fixtures, then carry the chosen result
into production code.

Each slice includes a UI action, domain logic, persistence/integration, failure
handling and tests through its public interface. Unit/contract tests establish
rules; integration tests exercise real local storage and parsers; live-provider
and clean-machine checks establish those integrations separately. Tests do not
stand in for content review or a real Windows launch.

Use varied topics in every applicable acceptance batch, not one preferred
subject. A slice cannot be declared complete with hardcoded answers, simulated
citations, fake progress, unconnected buttons or untested save/delete behaviour.

## Engineering selections after upstream inspection

The starting stack below is explicitly user-approved. Other configuration
defaults are engineering choices; S0 records compatible pins and evidence-based
adjustments. Selection does not establish implementation or measured reliability.

| Area | Reuse/adoption decision | Remaining check |
| --- | --- | --- |
| Foundation | NousResearch/hermes-agent at research pin af90026aa09949579bd423d24def3d38f743cde0, retaining MIT notices and source layout | Revalidate the selected release/commit before import; record digest and patches. |
| Agent runtime | Existing Python AIAgent, callbacks/interruption, compatible provider transport, ordinary SessionDB and memory-provider interface | Patch policy/no-save behaviour across every write path; history-off alone is insufficient. |
| Subscriptions | Reuse transports and adapt to documented app-owned consent and exact provider/model pairs | Hermes's existing Codex authentication differs from documented plan access. Pin auxiliary routes: Go's helper default is outside the allowlist. |
| Tools | Bounded registry for eligible retrieval, source fetch and structured learning proposals | Disable general shell/computer control, messaging, uncontrolled plugins/skills, self-mutation and provider rescue; do not start the stock gateway. |
| Desktop | Reuse upstream Electron/React shell, lifecycle and packaging; adapt the Renulus UI in TypeScript and connect controlled Python through a narrow message interface | Native launch/lifecycle, package and document rendering; no second shell or .NET agent rewrite. |
| Canonical data/context | SQLite canonical Renulus records; Hermes memory-provider/context hooks and compressor | IDs, provenance/scope/version filters, context budgets and deletion/export/restore. |
| Learner memory | Mem0 OSS through the existing Hermes integration; local Qdrant client as the initial derived index | Exact plugin/engine compatibility, subscription adapter, durable capture, history purge and safe reindexing. |
| Documents/chunking | Docling structured CPU pipeline + Docling-core HybridChunker; PDF.js viewing/rendering | Exact OCR/layout/table artifacts, tokenizer limits, page/region/table fidelity, CPU footprint and no-save paths. LiteParse is a bounded alternative for a demonstrated gap. |
| Embeddings | FastEmbed with an explicit bundled CPU model shared where appropriate by M2/M5 | Pin model/ONNX/tokenizer hashes and terms, offline loading, dimensions and resource use; BGE-small remains an evaluation baseline. |
| Document retrieval | LanceDB OSS embedded full-text/vector search and hybrid fusion | Native index compatibility, eligible revision/scope filters, staged activation and physical cleanup of old versions. |
| Evidence | Supported registered literature/publisher interfaces, Hermes DDGS or explicitly enabled user-keyed search, bounded fetch/user import and maintained extraction | Latest-final/rights filters, corrections/removals, extraction quality, key-free journeys and no silently billed tool or generative fallback. |
| Supermemory | Excluded; preserve earlier research | The user-approved replacement stack and [decision evidence](../research/2026-10-04-starting-stack-evidence.md) supersede its candidate status. |
| CPU helper distribution | Small app-managed embeddings/OCR accepted; selected Docling artifacts must meet the CPU budget | Artifact-level terms/hashes, no-save behaviour, clean Windows packaging and no doctor setup. |
| Packaging | Reuse upstream Windows support and bundled Python 3.14 layout; preserve required dependencies | Clean-machine build; prefer existing bundling, using PyInstaller only if a demonstrated packaging gap warrants it. |

Initial engineering verification targets a currently supported Windows 11 x64
release. S0 records the actual OS/CPU support matrix; untested variants are not
advertised. No mandatory WSL, Docker, developer Python or local model server is
part of the product experience.

The [Hermes source review](../research/2026-10-planning/hermes-adoption.md)
records exact source locations, existing desktop modules and necessary patches.
The [Supermemory review](../research/2026-10-planning/supermemory-fit.md)
distinguishes its public MIT parts, separate engine and Windows release from
untested product claims.
The [stack evidence record](../research/2026-10-04-starting-stack-evidence.md)
links the approved choice to pinned engine/plugin/chunker source, observed
Windows artifacts, model/licence scope and S0/S2/S4 checks. Cognee, Hindsight,
Mnemosyne and other investigated engines remain alternatives, not extra layers.

Electron's [process model](https://www.electronjs.org/docs/latest/tutorial/process-model)
and [security guidance](https://www.electronjs.org/docs/latest/tutorial/security)
support the isolated renderer and controlled main/preload interface.
PDF.js provides a reusable [viewer/rendering platform](https://mozilla.github.io/pdf.js/)
under [Apache-2.0](https://github.com/mozilla/pdf.js/blob/master/LICENSE).
Trafilatura provides [HTML extraction/metadata](https://trafilatura.readthedocs.io/en/latest/)
under [Apache-2.0](https://raw.githubusercontent.com/adbar/trafilatura/master/LICENSE).
If needed, PyInstaller documents [bundled operation](https://pyinstaller.org/en/stable/operating-mode.html)
and its [distribution exception](https://pyinstaller.org/en/stable/license.html).
Preserve all dependency notices. Sources accessed 2026-10-04.
