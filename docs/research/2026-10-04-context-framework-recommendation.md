# Open-source memory, document and context stack for Renulus

**Research round: 2026-10-04.** This document answers which existing engines and
frameworks Renulus should consider adopting with minimal adaptation. It preserves
the original recommendation and the subsequent user approval below; neither
establishes implementation. Public web, GitHub source/package metadata and public
community discussions were investigated. No application dependencies, models,
services or private data were installed or used.

The user explicitly **excluded Supermemory** and **accepted small CPU models
bundled and managed by Renulus for embeddings/OCR**, without GPU, Docker, model
server or setup for doctors. The selected subscriptions and exact conversational
model list remain unchanged. These decisions are recorded in
[the user answers](../planning/2026-10-04-user-answers.md).

## Decision follow-up — 2026-10-04

After this research, the user approved the strongest starting stack:
**Hermes + Mem0 OSS + Docling/HybridChunker + FastEmbed + LanceDB OSS**. The
[planning architecture](../planning/ARCHITECTURE.md) and
[implementation plan](../planning/IMPLEMENTATION_PLAN.md) now use that baseline.
The [stack evidence record](2026-10-04-starting-stack-evidence.md) connects the
selection to the original source inspections and outstanding checks.

Exact package/model/OCR artifacts and functioning integrations still need
verification. LiteParse and Cognee remain alternatives, not selected additional
engines. The approval is for planning/documentation; no package, model or
application implementation was installed by this update.

## What the product needs from these components

Renulus is a daily learning companion for nephrologists, not a tool for managing
a RAG deployment. A doctor should add material, ask questions, open evidence,
resume study and correct what the application remembers. Importing a document
must not require choosing a parser, vector database or embedding model.

Several distinct capabilities are often marketed together as “memory”:

| Capability | Example in Renulus | Appropriate authority |
| --- | --- | --- |
| Document ingestion | Extract a guideline, recognise a scan, preserve a table and its page | Original document plus versioned passages |
| Retrieval/RAG | Find evidence for a question, including paraphrases and abbreviations | Eligible source passages; an index is derived |
| Learner memory | Recall goals, explanation preferences and useful learning points | Editable, provenance-bearing learner records |
| Progress | Remember a reviewed question attempt and its actual result | Deterministic assessment records |
| Personalised context | Select relevant learner facts and evidence for this turn | Application scope and token budget |
| Conversation context management | Keep a long discussion coherent within the model window | Hermes conversation/context machinery |

A graph or vector memory engine does not establish mastery, source correctness,
or permission to retain a case. These distinctions are practical data ownership
requirements already present in the [architecture](../planning/ARCHITECTURE.md).

## Recommended adoption direction

Use **a small set of embedded open-source components behind Hermes**, with one
app-owned processing queue and one clinician-facing experience. The primary
selection and broader alternative are evaluated below; exact package/model pins
belong to the implementation acceptance record.

**The recommended configuration, now user-approved, is Hermes + Mem0 OSS + Docling
with its HybridChunker + FastEmbed + LanceDB.** Keep **LiteParse** as the named
lighter document alternative and **Cognee** as the named broader memory/RAG
alternative. This preference weights reusable document structure, table-aware
chunking and source locators alongside the desire to minimize new code; it does
not claim Docling has won a runtime comparison. LiteParse leads on parser-package
footprint; Docling leads on existing integration across extraction, structured
chunking and citations. Run the same bounded document comparison and select one
primary parser, rather than shipping both by default.

| Requested capability | Proposed first choice | Existing work reused | Main adaptation / top-level code licence |
| --- | --- | --- | --- |
| Learner memory | **Mem0 OSS** through Hermes's existing OSS plugin | Extraction/update/search engine and lifecycle integration | Approved generation transport, capture scope, durable writes, full deletion; **Apache-2.0** |
| PDF/image ingestion and OCR | **Docling**, explicitly configured for CPU/local artifacts | Structured document, page/region provenance, layout, tables, OCR adapters | Bundle artifacts; bound CPU/RAM; verify temporary-case paths; **MIT** |
| Chunking | **Docling-core HybridChunker** | Structural and token-budget splitting/merging, table-header handling | Pin the embedder's tokenizer; retain item-to-page mapping; **MIT** |
| Embeddings | **FastEmbed**, one explicit small model | ONNX CPU inference without a model server | Package weights/tokenizer; BGE-small is a baseline, not a final model decision; **Apache-2.0**, weights separate |
| Document search / RAG retrieval | **LanceDB OSS** | Local vectors, full-text search, filtering and hybrid fusion | Index revisions, source filters and physical cleanup; **Apache-2.0** |
| Personalised context injection | **Hermes memory/context hooks** | Prefetch, prompt blocks and request-context selection | Budget learner facts and source evidence separately; preserve upstream **MIT** |
| Long-conversation context management | **Hermes's compressor/context engine** | Token accounting, compaction and tool-result handling | Apply Renulus retention/source-selection rules; preserve upstream **MIT** |

Canonical learner/source records stay in Renulus's existing SQLite design.
For Mem0, start with its supported **local Qdrant client** rather than writing a
LanceDB memory adapter merely to make database names match. This is a small
embedded memory index, not a Qdrant server. LanceDB serves the larger document
library. Both are rebuildable derivatives, not competing record authorities.
Qdrant local mode's small-data limits remain a reason to test expected memory
volume. Consolidate onto one backend only if it actually reduces work.
[Mem0 local adapter](https://github.com/mem0ai/mem0/blob/abb81c88e1f738a8117d8293530fbc31a5ef8fd9/mem0/vector_stores/qdrant.py),
[local Qdrant limits](https://github.com/qdrant/qdrant-client/blob/cf747f4b6fa71ba35dfb467931f3fa65f2cdf263/qdrant_client/local/qdrant_local.py).

### Why Mem0 is the first memory choice

Choose the open **`Memory`/`AsyncMemory` engine**, distinct from the hosted
`MemoryClient`. Its extraction/update algorithm and storage adapters are public.
Hermes already supplies in-process integration, background recall and tools.
This is the clearest existing memory reuse seam in the investigation.
[Mem0 engine/licence](https://github.com/mem0ai/mem0/tree/abb81c88e1f738a8117d8293530fbc31a5ef8fd9),
[Hermes OSS integration](https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/plugins/memory/mem0/README.md).

It is an existing adapter to extend, not a zero-edit finished feature. The
plugin can truncate or skip captures, needs more scope filtering and recreates
the vector collection when dimensions change. Mem0 deletion removes live
vectors but retains previous text in SQLite history. Correct those behaviours
while retaining the engine. Explicitly replace hosted LLM/embedder defaults.
Memory extraction still consumes a generative call through the approved
subscription; embeddings do not perform that task. Detailed pinned evidence is
in [the memory investigation](2026-10-04-memory-engines.md) and
[Hermes audit](2026-10-04-rag-and-context.md).

### Why Docling and LiteParse are the document finalists

**Docling provides the more complete reusable document pipeline.** Its document
object and HybridChunker preserve structure and original-item references,
reducing custom table-aware chunking and citation-mapping work. This is relevant
to guidelines and research papers with units, multi-column text and tables.
These are capabilities, not a claim of correct extraction on every medical PDF.
[Docling engine](https://github.com/docling-project/docling/tree/v2.133.0),
[HybridChunker](https://github.com/docling-project/docling-core/blob/v2.99.0/docling_core/transforms/chunker/hybrid_chunker.py).

Its tradeoff is footprint. The inspected Heron layout and accurate TableFormer
weights alone total about **384 MB**, before OCR, Python/PyTorch and other
dependencies. That is artifact size, not RAM or installer size. Its separate
native pipeline is model-free but gives up reconstructed reading order,
headings and tables. Select the CPU artifact set deliberately; disable generative
enrichment. The accepted small-helper scope is not a finding that the full
standard bundle is small. [Pipeline/artifact evidence](2026-10-04-document-ingestion.md).

**LiteParse is the leading lighter alternative, with an actual open engine.**
It is separate from hosted LlamaParse. Its Rust/PDFium implementation supplies
geometric extraction, structured blocks, page coordinates and local Tesseract
OCR. The inspected Windows x64 wheel is about **12 MB compressed**; English OCR
data and the application runtime are additional. Missing OCR data triggers a
download unless Renulus packages it. LiteParse does not replace the whole
chunking/retrieval layer: compare total integration as well as binary size.
[Tagged engine](https://github.com/run-llama/liteparse/tree/python-v2.15.1/crates/liteparse),
[OCR assets](https://github.com/run-llama/liteparse/blob/python-v2.15.1/crates/liteparse/src/ocr/tesseract.rs).

For that lighter path, **Chonkie RecursiveChunker + TableChunker** offers MIT
prose/table chunking with explicit tokenizer support. Its existing LiteParse
adapter flattens text and loses page/box/block provenance, so use structured
LiteParse output and carry locators through a narrow adapter. Prose/table routing,
captions/footnotes and oversized-row handling remain work that Docling reduces.
**semchunk** is a smaller MIT text-only splitter with offsets, but does not supply
the table/document pipeline. These are alternatives to reimplementing chunking,
not extra requirements for the Docling path.
[Chonkie table code](https://github.com/feyninc/chonkie/blob/main/src/chonkie/chunker/table.py),
[LiteParse adapter](https://github.com/feyninc/chonkie/blob/main/src/chonkie/chef/liteparse.py),
[semchunk API](https://github.com/isaacus-dev/semchunk#usage-).

**Xberg is the third candidate** if consolidating extraction/chunking/embedding
is decisive. Its engine is MIT, but native dependencies have separate notices
and default caching needs controls. It succeeds Kreuzberg: the older v4 LTS
support window ends in December 2026. An unqualified recommendation to start
on "Kreuzberg" would conceal that short horizon.
[Xberg engine](https://github.com/xberg-io/xberg/tree/v1.3.3),
[LTS policy](https://docs.kreuzberg.dev/lts/),
[native notices](https://github.com/xberg-io/xberg/blob/v1.3.3/THIRD_PARTY_LICENSES.md).

### The more consolidated alternative: Cognee

If one broader framework is preferred, **Cognee is the closest shortlisted
substitute for the original Supermemory idea**. Its Apache-2.0 engine combines
ingestion, chunking, graph construction and recall using local SQLite, LanceDB
and Ladybug. It has a host-sampling adapter, but Renulus still needs the sampling
callback or a direct provider bridge.
[Cognee source](https://github.com/topoteretes/cognee/tree/b32d8afc59e1064d9291b9828a8a147be9cc8bab).

It ranks behind focused Mem0 reuse here because it adds a graph worker/native
database, more generative stages, and still needs robust extraction. Its default
pypdf reader does not itself attach original page numbers or perform OCR.
Graph provenance is useful, but does not automatically solve original-page
citations, no-save cases or complete deletion. Use Cognee instead of the focused
memory stack if relationship-aware retrieval earns its costs; do not layer both
memory engines without a concrete need.
[Windows/dependency details](https://github.com/topoteretes/cognee/blob/b32d8afc59e1064d9291b9828a8a147be9cc8bab/pyproject.toml),
[PDF reader](https://github.com/topoteretes/cognee/blob/b32d8afc59e1064d9291b9828a8a147be9cc8bab/cognee/modules/data/processing/document_types/PdfDocument.py).

**Hindsight** is the richer memory alternative: retain/recall/reflect and
temporal/entity retrieval, but native Windows delivery manages a PostgreSQL
process and separate worker environment. **Mnemosyne** is the lightweight
Hermes-native alternative: useful host-LLM bridge and SQLite retrieval, but
release/package version inconsistencies, fallback/capture defaults and limited
Windows execution evidence prevent ranking it first for reliability. Both
remain credible options, not extra required layers.
[Detailed evidence](2026-10-04-memory-engines.md).

### Licences and the closed-engine boundary

Supermemory's self-hosting docs confirm the user's concern: the server binary
comes from a separate non-public codebase. An open SDK/dashboard does not supply
the adoptable engine. Its exclusion is supported by primary evidence.
[Supermemory overview](https://github.com/supermemoryai/supermemory/blob/7cc19fa34683a4fe74166ee5d794d271a21b5a92/apps/docs/self-hosting/overview.mdx).

The first-choice code components have conventional permissive licences. Preserve
notices and inspect the actual model/native bundle; this is not blanket licence
clearance. Current Basic Memory, OpenViking's main engine and Honcho use AGPL;
KnowNote uses GPL. Current Marker has Apache code but separately restricted
model terms; current MinerU adds terms beyond plain Apache. These are inspected
version-specific findings, with exact sources in the memory and ingestion notes.
Copyleft is valid open source, but adds obligations to the intended permissive
distribution. Do not infer an engine licence from its SDK or an old comparison.

### Avoid rebuilding generic ingestion infrastructure

Small APIs do not prove the least total work. Compare the following boundaries
before writing generic hashing, caches or indexing plumbing. An app-managed
Node/stdio worker is acceptable if it simplifies delivery; Python-only is not
a product requirement.

| Reuse boundary | Existing work saved | Adapter/dependency cost | Disposition |
| --- | --- | --- | --- |
| Docling + HybridChunker + direct LanceDB | Parsing, structured chunks, item provenance, indexes and hybrid fusion | Connect canonical IDs, revision activation and job state; no generic job framework supplied | Preferred compact engine boundary; total effort not yet measured |
| Selected LlamaIndex core ingestion | Transformations, hashing, ingestion cache, docstore/vector-store coordination | Preserve locators; staged replacement and nonpersistent case processing remain explicit Renulus responsibilities | First candidate if generic lifecycle features would otherwise be written locally |
| Haystack components/pipeline | Converters, routing, splitting, embedding and retrieval composition | Community LanceDB bridge targets older Haystack; direct component may be needed | Alternative when pipeline routing warrants it; do not add both frameworks |
| AnythingLLM native embedder/LanceDB/memory modules | Cached model sessions, chunk/index operations, vector deletion and prompt selection | Imports settings, document-vector records, caches and splitter; adapt modules/worker | Useful MIT source donor; assess narrow modules separately from the whole app |
| Kotaemon library/file pipelines | Source/document/vector mappings, source filters, page metadata and evidence display | `ktem` database/provider-manager coupling; older constrained framework packages | Useful Apache source donor if an isolated module saves more work than its dependencies add |
| QMD library/stdio in reduced configuration | Collection indexing, lexical/vector retrieval, fusion and structured output | Prepared-text/page mapping; native Node packaging; bypass expansion and disable reranking | Conditional retrieval alternative, not PDF ingestion or learner memory |

The [RAG/context note](2026-10-04-rag-and-context.md) and
[comparable-project note](2026-10-04-comparable-projects-and-signals.md) give primary
API/source links. This compares reuse, not measured patch counts. Reuse engine
caches and transforms behind Renulus's source/scope rules. Build the product
rules, not another generic ingestion framework.

The reusable foundation is already unusually helpful:

- Hermes has memory-provider lifecycle hooks, background recall, turn observation
  and a separate context compressor/engine interface.
- Its Mem0 provider already has an **in-process OSS mode**, so a dedicated memory
  engine need not imply a Docker server or cloud memory service.
- LanceDB's open engine provides local full-text and vector search with hybrid
  fusion; FastEmbed can supply CPU-generated vectors without a model service.

These are source-backed capabilities, not a claim that the combination is already
integrated. The [RAG/context investigation](2026-10-04-rag-and-context.md) records
the exact Hermes source seams, framework alternatives, package evidence and
remaining adapters.

## Similar projects and what their adoption signals tell us

**AnythingLLM is the most useful broad product comparator.** Its public MIT
repository contains real local embeddings, LanceDB retrieval and personalised
memory injection. Borrow the hidden processing/workspace behaviour and selected
implementation patterns. The modules depend on its Node application, collector
and storage; adding that complete application beside Hermes is not a minimal
library integration. See its [memory injection code](https://github.com/Mintplex-Labs/anything-llm/blob/feb04ca0a57cda6d0b3a69c62578f0af44d388fc/server/utils/memories/index.js)
and [LanceDB implementation](https://github.com/Mintplex-Labs/anything-llm/blob/feb04ca0a57cda6d0b3a69c62578f0af44d388fc/server/utils/vectorDbProviders/lance/index.js).

**Kotaemon is the strongest Python application/framework comparator.** It has a
real reusable library and valuable source/page citation behaviour. However,
its [manifest](https://github.com/Cinnamon/kotaemon/blob/9ad3e4e49aa35b8acddd235918a5d9753c1cfdf9/libs/kotaemon/pyproject.toml)
constrains older LlamaIndex, Chroma, Gradio and provider packages. Reusing the
maintained underlying libraries may be easier than importing its whole stack.

**QMD is worth a conditional retrieval comparison.** It is a real MIT local
engine with library/CLI/stdio MCP boundaries and lexical/vector retrieval.
Its [default pipeline](https://github.com/tobi/qmd/blob/26b703c5daa8037df089a8104cbf7eeab4e51874/README.md)
also downloads a local generative query-expansion model, outside Renulus's
accepted generation route. Its typed-query interface can bypass expansion;
pair this with **`rerank: false`** to disable the separate default local reranker.
This reduced configuration needs its own quality evaluation; default-QMD results
do not establish its performance. It still needs PDF ingestion and
page mapping. Native Windows support work exists, but the inspected CI omits
Windows. It is not a complete memory/ingestion replacement.

| Other comparator | Useful lesson | Why it is not the primary dependency recommendation |
| --- | --- | --- |
| Open Notebook | Sources, notes, research notebooks and understandable shared-source deletion | Separate database/application services; the database has independent licence terms |
| Onyx | Source permissions, connector synchronisation and evidence retrieval | Substantial server stack; enterprise code has different terms |
| RAGFlow | Inspectable extraction, chunks and citations | Server/database infrastructure and a major release-candidate architecture transition |
| Khoj / Reor | Personal context, related notes and background assistance | AGPL terms and application/runtime coupling; Reor's observed maintenance is less recent |
| Jan | Native app/model/index packaging | Tauri/Rust components require another integration boundary beside Hermes/Electron |
| KnowNote | Especially close Electron/React + CPU embeddings + SQLite + citations/MCP architecture | GPL-3.0 code and a smaller/younger project; useful architecture reference, not MIT-only code to copy |

Exact source, licences, deployment manifests and maintenance snapshots for these
rows are in [the comparable-project investigation](2026-10-04-comparable-projects-and-signals.md).
Copyleft projects are open source; they are deprioritised because preserving their
obligations adds work to the intended permissive Renulus distribution, not because
their code is unavailable.

The public social-media search covered Reddit, Hacker News, X and Bluesky. Useful
verifiable discussions came from Reddit/HN; X/Bluesky did not yield evidence strong
enough to cite. Examples include the [Reor author launch discussion](https://news.ycombinator.com/item?id=39372159),
[Kotaemon adoption discussion](https://news.ycombinator.com/item?id=42571272), an
[AnythingLLM user's multi-document retrieval report](https://www.reddit.com/r/Rag/comments/1tyd87d/local_rag_over_300_pdfs_anythingllm_ollama/),
and the [KnowNote author's desktop announcement](https://www.reddit.com/r/LocalLLaMA/comments/1ptj78l/i_built_a_localfirst_notebooklmstyle_app_without/).
These support testing multi-document coverage, portability and absence of setup
friction. They do not establish comparative quality; author announcements and
single-user complaints are labelled as such in the evidence note.

Actual returned GitHub Trending pages supplied additional discovery signals:
[weekly all-language](https://github.com/trending?since=weekly) listed Hindsight
with 14,507 stars in the displayed weekly period;
[monthly Python](https://github.com/trending/python?since=monthly) listed Hindsight
(23,065), MarkItDown (10,741), PageIndex (3,177) and Docling (2,491) for the displayed
monthly period. These are mutable GitHub counters observed on the research date,
not a historical growth analysis. Popularity brought projects into the research;
licence, source boundary, Windows packaging and runtime dependencies determine
the recommendation.

## What should remain Renulus code

Adopting existing infrastructure still leaves a small set of product rules:

1. **Retention and eligibility:** decide ordinary study, library, temporary case,
   saved case and reserved assessment scope before processing; enforce that scope
   through every background task, cache and model call.
2. **Provenance and revisions:** stable source/passage/memory IDs; original page
   and region locators; current/superseded document status; evidence for a retained
   learning point.
3. **Correction and deletion:** cancel queued work, invalidate derived entries,
   retain deletion markers and stop deleted material being recaptured from old
   evidence. Do not mistake deletion from search for physical purge.
4. **Progress and teaching:** scores, observed mistakes, study scheduling and the
   distinction between an interest and demonstrated competence.
5. **Integration and UX:** background job states, cancellation, crash recovery,
   subscription quota/authentication handling, source display and an editable
   memory view.

These are the pieces that make Renulus useful to clinicians. There is no need to
write another PDF parser, embedding runtime, vector engine, generic memory
algorithm or agent loop.

## The background experience to require

**Library import:** hash and identify a revision → extract text/layout → OCR only
where needed → retain page/region metadata → chunk to the selected embedder's
limit → embed → activate the completed index revision. A failed or cancelled
import must not appear fully searchable. Resume work after restart without
duplicating documents.

**Question:** retrieve eligible evidence using keyword and semantic search;
retrieve relevant learner records separately; combine them within a budget;
let Hermes call an allowed subscription model; open citations against the actual
document revision. Source evidence and remembered learner preferences should
not be presented as interchangeable facts.

**Learning memory:** capture useful evidence in the background, deduplicate while
preserving meaningful distinctions, and make retained records visible and
correctable. Exact attempts and explicit preferences can be stored directly;
model-generated inferences require provenance and must not become invented
progress. Extraction/summarisation still consumes the chosen subscription's
quota, so queue it and recover cleanly rather than calling another provider.

**Temporary case:** keep raw content and derivatives out of persistent pipelines.
Some libraries automatically cache, log or retain history; configure or bypass
those paths before enabling temporary cases. Save performs the deliberate
transition. Generalised learning evidence may be retained under the existing
policy, without copying case facts into a profile.

**Packaging:** ship the runtime, native libraries and approved CPU model artifacts
as application-managed components. Limit worker concurrency, make progress and
retry understandable, and perform no first-use surprise model/server setup.
Local embeddings/OCR do not make subscription-based conversation offline.

## Bounded implementation checks for the approved stack

The existing S0/S2/S4 stages verify the selected stack on shared material. If it
fails a defined packaging, resource or quality target, compare the nearest
alternative using that same material. This is future implementation work; none
of these tests was run during this research.

| Check | Concrete evidence required |
| --- | --- |
| Clean Windows install | Launch/import/search on the supported Windows baseline without developer Python, Docker, WSL, GPU or a model server; record installer size, peak RAM and CPU behaviour |
| Broad document handling | Synthetic digital PDFs, scans, two-column text, tables/units, images and malformed/encrypted files across CKD, glomerular disease, dialysis, transplantation and electrolyte/acid–base topics |
| Retrieval and citations | Same questions across engines, including paraphrases, acronyms, conflicting editions and unanswerable questions; check retrieved passages and the exact opened page/region |
| Memory | Repeated preference, changed goal, corrected misconception and distinct lessons about one topic; verify deduplication without flattening context |
| Retention and recovery | Unsaved-case sentinel absent from every app-owned durable store; delete during ingestion, correct during memory extraction, restart, reindex and restore |
| Model boundary | Capture outbound calls; only selected subscription/model pairs for generation and local pinned CPU components for embeddings/OCR; no fallback cloud parser/embedder |
| Distribution | Package/module/model/native-binary licence inventory with notices and artifact hashes, including transitive dependencies actually shipped |

Define fixture and performance targets before testing. Validate the approved
stack on the complete installed experience and measured failures, not vendor
benchmark headlines. A failed retention, citation or installation check calls for
an adapter fix or the named alternative; it does not justify weakening the
accepted product behaviour.

## Evidence boundaries

This research can establish that code, APIs, licences and distribution artifacts
exist, and expose incompatibilities in defaults. It cannot establish clinical
accuracy, educational effectiveness, end-to-end Windows reliability or minimal
actual patch size without exercising a pinned implementation. Public social
discussion is a source of adoption signals and reported friction, not proof of
performance. Stars measure attention; they do not establish maintenance quality.

Current source pages and package registries can change. The supporting notes
record immutable source references where available and distinguish source
inspection from runtime evidence. Existing uncommitted planning work was
preserved; no commit, PR, deployment or provider call was requested or performed.
