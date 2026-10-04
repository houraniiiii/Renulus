# Open memory and context engines for Renulus

Research date: **2026-10-04**. Public-source inspection only; no packages,
models or services were installed or run, no inference/provider calls were made,
and no private data or credentials were accessed. Recommendations below record
the source review before the subsequent user approval. This note covers memory
and context within the wider research round; ingestion/RAG has a separate note.

**Decision follow-up (2026-10-04):** the user selected Mem0 OSS through Hermes
as part of the approved starting stack. Cognee, Mnemosyne and Hindsight remain
alternatives. Preserve the source findings below; compatible pins, routing,
retention and runtime reliability remain untested. See the
[stack evidence](2026-10-04-starting-stack-evidence.md) and
[planning architecture](../planning/ARCHITECTURE.md).

The constraints are Hermes Python plus the existing Electron/React foundation,
native Windows delivery, no owner-hosted service, and generative work through
the selected Codex/OpenCode Go subscriptions and exact permitted models.
During this research the user explicitly accepted **small CPU models bundled
and entirely managed by Renulus for embeddings/OCR**, with no GPU, Docker,
model server or user setup. That permission does not authorize a local
generative model or a new paid API. The user also explicitly dropped
Supermemory. Existing planning documents may still describe its earlier status;
this research does not edit those documents.

## Recommendation

**Shortlist embedded Mem0 and Cognee. Start the engineering comparison with
Mem0 through the existing Hermes OSS integration.** Mem0 offers a smaller
personal-memory addition; Cognee covers more of the document-to-graph-to-context
pipeline. Both publish real Python engines under Apache-2.0. Neither is a
complete clinician product, and neither has an unchanged default configuration
that satisfies Renulus. [Mem0 engine][m-main], [Mem0 licence][m-license],
[Cognee package][c-package], [Cognee licence][c-license].

**Keep Mnemosyne as the lightweight Hermes-native alternative and Hindsight as
the richer, heavier alternative.** Mnemosyne already has a host-LLM bridge and
local SQLite retrieval; Hindsight offers evidence-linked memory and mature
retain/recall/reflect interfaces, but adds a managed local API process and
PostgreSQL. These are different engineering tradeoffs, not a benchmark ranking.
[Mnemosyne host bridge][n-host], [Hindsight integration][h-hermes],
[Hindsight database implementation][h-pg0].

There is no evidence here for a single permissively licensed, unchanged plugin
that handles all of Renulus's memory, scanned-document extraction, source-page
citations, subscription routing and temporary-case retention. **Reuse an engine
and the Hermes hooks; build the small application boundary that controls what
may enter memory, how it is retrieved, and how it is corrected.** That boundary
is product-specific work, not a reason to write another memory/search engine.

| Candidate configuration | What Renulus can reuse | Extra local machinery | Principal remaining gap | Research judgement |
| --- | --- | --- | --- | --- |
| **Mem0 OSS + local Qdrant client + explicit FastEmbed model** | Memory extraction/update/search, local vector storage, existing Hermes OSS backend | Same Python process; local files, embedding runtime | Subscription adapter; scope/provenance; durable capture; history purge; document pipeline remains separate | **First option for focused memory reuse** |
| **Cognee Python + SQLite + LanceDB + Ladybug** | Ingestion/chunking, graph extraction, memory/context APIs, retrieval and provenance deletion machinery | Native storage dependencies; graph worker subprocess | More model stages, native packaging, citation-preserving extraction, state/deletion coordination | **Broader alternative when graph/document unification earns its complexity** |
| **Mnemosyne + embeddings extra + controlled Hermes host bridge** | SQLite/FTS/vector recall, prefetch, host-driven consolidation, edit/export tools | SQLite extension and ONNX helper model | Transcript capture defaults, generative fallback, release/package mismatch, Windows validation | **Promising low-infrastructure alternative; prove reliability before choosing** |
| **Hindsight local + pg0 + local embeddings** | Retain/recall/reflect, source chunks, observations, temporal/entity retrieval, Hermes plugin | Separate API/worker environment and embedded PostgreSQL process | Installer/lifecycle footprint, subscription authentication adaptation, capture policy | **Strong feature set, higher packaging cost** |

The detailed sources and qualifications for each configuration follow. Local
databases and an app-owned child process are distinct from requiring the
project owner to host a service. A Python package labelled “embedded” can still
start servers or download models; those behaviours must be accounted for.

## Evidence, versions and maintenance

Immutable source snapshots anchor the findings. Release metadata was read from
public GitHub/PyPI endpoints; GitHub's unauthenticated API eventually returned
403 rate limits. Subsequent work used public raw files, repository pages,
in-memory public source archives and `git ls-remote`. A failed metadata request
is **not** evidence of inactivity. Stars below are approximate counts observed
on this date, not measured growth or proof of daily GitHub Trending placement.

| Project | Inspected snapshot / package or release evidence | Observed public activity |
| --- | --- | --- |
| Mem0 | [`abb81c88e1f738a8117d8293530fbc31a5ef8fd9`](https://github.com/mem0ai/mem0/commit/abb81c88e1f738a8117d8293530fbc31a5ef8fd9); Python **2.2.1**, uploaded **2026-09-25** ([PyPI metadata](https://pypi.org/pypi/mem0ai/2.2.1/json)) | ~66.6k stars; inspected commit 2026-10-01. GitHub “latest” returned **ts-v3.3.1**; that is not the Python version. |
| Cognee | [`b32d8afc59e1064d9291b9828a8a147be9cc8bab`](https://github.com/topoteretes/cognee/commit/b32d8afc59e1064d9291b9828a8a147be9cc8bab); [**v1.6.2**, 2026-09-29](https://github.com/topoteretes/cognee/releases/tag/v1.6.2) | ~31.3k stars; inspected commit 2026-10-01. |
| Mnemosyne | [`e871f39480b9b9156faa4396162f7ec1f3b11525`](https://github.com/mnemosyne-oss/mnemosyne/commit/e871f39480b9b9156faa4396162f7ec1f3b11525); release page shows [**v0.7.4**, 2026-10-03](https://github.com/mnemosyne-oss/mnemosyne/releases/tag/v0.7.4) | ~3.3k stars. **Version inconsistency:** PyPI latest stable is **3.15.1**, uploaded 2026-07-30; GitHub also lists a **v4.0.0b4** prerelease. Pin and reconcile artifacts before adopting. |
| Hindsight | [`f7dd3f4fd7420f7beec60c32c965e5e5cf7be066`](https://github.com/vectorize-io/hindsight/commit/f7dd3f4fd7420f7beec60c32c965e5e5cf7be066); [**v0.10.2**, 2026-09-29](https://github.com/vectorize-io/hindsight/releases/tag/v0.10.2) | ~45.3k stars; inspected commit 2026-10-02. |
| Graphiti | [`5d47d4d0182aa6350edeb435b734837a88ed9738`](https://github.com/getzep/graphiti/commit/5d47d4d0182aa6350edeb435b734837a88ed9738); [**v0.30.2**, 2026-09-08](https://github.com/getzep/graphiti/releases/tag/v0.30.2) | ~31.4k stars; inspected commit 2026-10-04. |
| Basic Memory | [`194afe165b3e7676496aaa53b70e39a78ea5aa4f`](https://github.com/basicmachines-co/basic-memory/commit/194afe165b3e7676496aaa53b70e39a78ea5aa4f); [**v0.23.2**, 2026-08-25](https://github.com/basicmachines-co/basic-memory/releases/tag/v0.23.2) | ~4.1k stars; inspected commit 2026-10-02. |
| OpenViking | [`9d9bc85e1f6a15afa7f23b0d7bf114a7c61cad14`](https://github.com/volcengine/OpenViking/commit/9d9bc85e1f6a15afa7f23b0d7bf114a7c61cad14); [**v0.4.23**, 2026-10-02](https://github.com/volcengine/OpenViking/releases/tag/v0.4.23) | ~39.2k stars; inspected commit 2026-10-03. |
| memU | [`2c050bc9681a4c0aff1af211a000e73d14f33356`](https://github.com/NevaMind-AI/memU/commit/2c050bc9681a4c0aff1af211a000e73d14f33356); latest API release result [**v1.5.1**, 2026-03-23](https://github.com/NevaMind-AI/memU/releases/tag/v1.5.1) | ~14.5k stars; main commit 2026-09-21 now describes a wiki/agent-history product. Do not mix the old release and current architecture. |
| Memvid | [`e6bd9f7b9c38cd8d5370fa0fc936ac1dcd751813`](https://github.com/memvid/memvid/commit/e6bd9f7b9c38cd8d5370fa0fc936ac1dcd751813); source Cargo version **2.0.140** | ~16.6k stars; commit 2026-07-14. Python SDK **2.0.160** uploaded 2026-05-27; separate component version, not a demonstrated matching core build. |
| Letta | [`5bcdd177d70fa2b31a754cfcd801e77b2e1ab16a`](https://github.com/letta-ai/letta/commit/5bcdd177d70fa2b31a754cfcd801e77b2e1ab16a); historical release [**0.16.8**, 2026-05-14](https://github.com/letta-ai/letta/releases/tag/0.16.8) | ~25.0k stars in old repository. September README redirects active work to **letta-ai/letta-code**. |

Dates above are not beyond the research cutoff. Search-rendered metadata was
sometimes stale: Cognee's indexed manifest said 1.6.1 while pinned raw source
said 1.6.2; Mnemosyne `/releases/latest` resolved to 0.7.3 in a cached result while
the release list showed 0.7.4. Prefer the explicit source SHA and artifact
metadata. No comparison here claims measured medical accuracy or clinician UX
reliability.

Social discovery included [a Hermes memory-provider discussion](https://www.reddit.com/r/hermesagent/comments/1w0vmzw/what_memory_service_are_you_using_with_hermes/),
[a memory-provider comparison thread](https://www.reddit.com/r/hermesagent/comments/1tms3g6/memory_providers_i_tested_them_all/)
and [a broad engine survey discussion](https://www.reddit.com/r/LocalLLaMA/comments/1r8cnwq/analyzed_8_agent_memory_systems_endtoend_heres/).
These supplied leads and failure hypotheses only. Product claims below are
grounded in the owning projects' source/docs, not endorsements or social
benchmark tables.

## 1. Mem0: best first comparison for focused embedded memory

### What is actually open and embeddable

The `mem0ai` package contains `Memory`/`AsyncMemory`, extraction and update
logic, embedding adapters and vector-store adapters. It is an engine, distinct
from the hosted `MemoryClient`. Apache-2.0 covers the inspected source. The
base dependency set includes Qdrant's Python client, OpenAI's SDK, SQLAlchemy
and PostHog; graph/server extras are not necessary for this proposed path.
[Engine][m-main], [manifest][m-package], [licence][m-license].

Its Qdrant adapter creates `QdrantClient(path=...)` when no server connection is
configured. Therefore **Mem0 does not inherently require a Qdrant server or
Docker**. Give it an explicit Renulus data directory rather than the upstream
`/tmp/qdrant` default. `on_disk=False` is not a no-save contract: the configuration
itself says it does not delete the database path. The adapter contains specific
Windows reset handling for open SQLite files. [Qdrant configuration][m-qconfig],
[Qdrant implementation][m-qdrant].

### Actual defaults and subscription work

The default LLM provider and embedder are both OpenAI. The inspected LLM adapter
defaults to `gpt-5-mini`; embeddings default to `text-embedding-3-small`. These
are not Renulus's approved configuration. Worse, the LLM adapter prefers an
ambient `OPENROUTER_API_KEY` when present. Construct explicit configuration and
an isolated app environment. [LLM provider config][m-lconfig],
[OpenAI adapter][m-openai], [embedding adapter][m-embed-openai].

The existing FastEmbed adapter is usable with a bundled CPU model, but its own
default is **`thenlper/gte-large`**, not a small model. Explicitly select a
candidate such as BGE-small and match vector dimensions. The implementation
currently passes only the model name to `TextEmbedding`; packaging must verify
how the chosen FastEmbed version resolves a prepackaged cache without downloads.
[FastEmbed adapter][m-fastembed].

For generation, reuse the selected subscription through Hermes rather than
configure an unrelated API client. Mem0 exposes `LlmFactory.register_provider`
and an `LLMBase` interface, but its Pydantic provider validator has a fixed
allowlist: registering a new name alone is not proven sufficient. A narrow
adapter/configuration patch is a concrete integration task. Its LangChain
adapter accepts a `BaseChatModel`, but adding LangChain solely for this bridge
would increase the dependency surface. [Factory][m-factory],
[provider validation][m-lconfig], [LangChain adapter][m-langchain].

`add(..., infer=False)` can store facts already extracted through Hermes;
embeddings still run, and `Memory` initializes its LLM client regardless. It
does not by itself eliminate provider setup or deliver inferred deduplication.
Prefer preserving Mem0's extraction/update algorithm if its adapter can be
made to use the approved runtime. [Memory construction and add][m-main].

### Existing Hermes reuse and remaining product work

The parallel Hermes audit identified an existing `mode: oss` backend, so the
comparison should begin there rather than with a new integration from scratch.
Its inspected backend forwards vector store, LLM, embedder and version
configuration, but not `history_db_path` or custom prompts. The audit also
identified user-only search scoping, capture of both speaker roles, a default
450-character sync limit, writes skipped when the previous worker remains
alive after a five-second wait, and destructive collection recreation when
embedding dimensions change. These are **reuse gaps in the plugin**, not proof
that the Mem0 engine inherently requires those behaviours.
[Pinned Hermes README][hermes-m-readme], [backend][hermes-m-backend],
[provider][hermes-m-provider].

This engine inspection is of **mem0ai 2.2.1**. The Hermes fork's dependency pin
and plugin revision must be checked together; this note does not establish
that every current-engine feature exists in its older pinned package or that
upgrading that package is a compatible drop-in change.

Retain its interfaces and tool plumbing; supply Renulus scope/provenance,
durable queued capture, explicit model routing, app-owned storage paths, and
versioned reindexing. New indexes should be built and checked before switching
the active revision. Temporary cases must never reach the durable sync path.
These are proposed adaptations, not work performed in this research.

Deletion needs special attention: `_delete_memory` removes the vector entry
but writes `prev_value` into SQLite history with a deletion marker. Updating
also retains old text. A successful delete therefore means removal from live
retrieval, not removal of all stored content. Renulus needs a targeted history
purge plus derivative/queue invalidation. [Deletion/update implementation][m-main],
[history-path default][m-base].

**Fit:** strong for learning preferences, prior learning points and personalised
recall. A medical document library still needs extraction, chunk locators,
document editions and source selection. Do not treat an extracted user memory
as a quoted guideline passage. Mem0's general memory API does not establish
that library workflow.

## 2. Cognee: broader reuse, more moving parts

### What Renulus gets

Cognee publishes the Python ingestion/memory engine under Apache-2.0, with
`remember`, `recall`, `improve` and `forget` surfaces. It can run locally with
embedded storage instead of Cognee Cloud. Its scope is closer to the originally
desired combined memory/context stack than Mem0's focused memory API.
[Product surfaces][c-docs], [licence][c-license].

The familiar “SQLite + LanceDB + Kuzu” description now needs correction. The
inspected configuration retains `GRAPH_DATABASE_PROVIDER="kuzu"`, but the
bundled `kuzu/__init__.py` imports **Ladybug**. On Windows the dependency is
pinned to **Ladybug 0.19.0**. A graph subprocess isolates the native engine;
Renulus must package and supervise it. This is not a separate user-managed
model/database service, but it is more than one pure-Python library.
[Storage defaults][c-env], [compatibility shim][c-kuzu],
[graph worker proxy][c-worker].

### Defaults that matter

The LLM default is `openai/gpt-5.6-luna`, outside Renulus's allowed list.
Extraction, summarisation, queries and image transcription can have distinct
routes. Configuring one foreground model does not constrain every background
call. Route all generative stages through the selected subscription and
disable unapproved fallbacks. [LLM configuration][c-llm].

No-key mode is not “no inference”: current configuration describes a local
GLiNER demo extraction path and BGE-small/FastEmbed embeddings. With a key or
explicit embedding settings the selection changes; the template explicitly
warns that configuring only a custom LLM can leave embeddings on OpenAI.
Set the local embedder explicitly. The newly accepted helper-model scope
covers embeddings/OCR, not an automatic replacement of subscription-based
extraction with GLiNER or a local generative model. [Environment template][c-env].

A real **MCP sampling adapter** can ask the host to perform text/structured
generation without another LLM API key. It validates/repairs returned JSON;
audio and image-description routes are not covered. This is a valuable reuse
seam, but only works if Renulus's host implements the required sampling callback
and routes it under the correct policy. Installing an MCP server alone does
not prove that connection. A direct Python host adapter may be simpler in the
Hermes fork. [Sampling implementation][c-sampling].

Haystack 3.3 already exposes `CogneeMemoryStore`, `CogneeWriter` and
`CogneeRetriever`. Its wrapper defaults to `GRAPH_COMPLETION` and
`self_improvement=True`, which means generative search and inline improvement.
For a Hermes-owned answer use raw retrieval such as `CHUNKS`, with deliberate
improvement scheduling. Its session tier avoids extraction on each write, but
is not evidence of RAM-only retention; `delete_all_memories` leaves that cache
untouched. A Haystack wrapper saves plumbing, not model calls or retention
design. [Haystack integration][c-haystack].

### Documents, deletion and Windows costs

The default `PdfDocument.read` uses **pypdf**, iterates pages and feeds extracted
strings into the chunker. It does not itself attach page numbers to those
strings or perform OCR. Cognee's default PDF ingestion is therefore not proof
of citation-preserving medical PDF understanding; verify the complete chunk
path or supply pre-extracted passages with page metadata.
[PDF implementation][c-pdf].

The dependency manifest distinguishes slim Docling conversion from full
PDF/image ML conversion, and provides optional RapidOCR. It also documents
specific Ladybug storage fixes, the 0.19.0 pin rather than 0.19.1, missing
Windows OpenSSL DLLs handled by a shim, and Python-version-sensitive ONNX
wheels. This is evidence of active maintenance **and** a meaningful native
packaging surface. Do not upgrade these components independently without
testing their on-disk formats and extension binaries. [Manifest][c-package].

Cognee has graph-provenance deletion that follows document and chunk references
and returns removed node/edge identities for derived-cache invalidation. That
is useful existing work. Renulus still needs to establish deletion of original
copies, session caches, summaries, queued jobs and backups as one product
operation. [Provenance deletion implementation][c-delete].

**Fit:** shortlist when graph relationships across library material and learning
history measurably improve the product. More comprehensive than Mem0, but
not obviously fewer edits once the Windows package, subscription bridge,
citations and retention requirements are included.

## 3. Mnemosyne: unusually close to Hermes, but inspect beyond the slogan

The MIT engine has one mandatory PyYAML dependency; SQLite comes from Python.
Its `embeddings` extra adds FastEmbed, ONNX Runtime and sqlite-vec. Keyword-only
operation is possible; the embedded default with helpers is
`BAAI/bge-small-en-v1.5`, with an explicit model cache path and thread settings.
No hosted memory account is required. [Manifest][n-package],
[embedding implementation][n-embeddings], [licence][n-license].

The first-class Hermes provider already implements prompt context, prefetch,
turn sync and tools. More importantly, `hermes_llm_adapter.py` routes
consolidation through `agent.auxiliary_client.call_llm(task="compression")`.
That is closer to the desired subscription reuse than a generic
OpenAI-compatible API example. [Provider documentation][n-provider-readme],
[host bridge][n-host].

There are material defaults to change:

- Turn sync stores user/assistant conversation content. Its helper limits are
  500/800 characters, and consolidation is enabled by default. Gate input before
  this path; a heuristic secret/noise classifier is not a temporary-case policy.
  [Provider source][n-provider].
- The host bridge returns `None` on failure and documents a local GGUF fallback.
  `local_llm.py` enables LLM handling by default and names a roughly 656 MB
  MiniCPM5 model. Do not install `[all]`/`[llm]` or allow that fallback. Make a
  failed subscription job retryable or visibly failed. The proposed host-only
  failure policy still needs implementation verification. [Bridge][n-host],
  [local LLM defaults][n-local], [extras][n-package].
- “Forget” has different meanings: ordinary memory deletion is separate from
  canonical-fact retirement, whose tool explicitly preserves history. Do not
  wire both to a clinician-facing Delete action. [Provider schemas][n-provider].

Media assets/page spans and a `remember_media` surface exist, with optional
PDFium/Pillow dependencies. This makes the project more than a preference
store, but it is not yet evidence that its media path meets Renulus's document
revision and original-page citation contract. [Media schema][n-media],
[package extras][n-package].

Maintenance is active, but release identity needs resolution: current source,
GitHub stable/prerelease tags and the latest stable PyPI package report
different version lines. The README also explicitly withdraws a previous
98.9% LongMemEval claim because reproducible methodology was absent and labels
other benchmark results as older builds. Its comparison table is not an
independent comparison and should not drive selection. The inspected CI's
main Python test matrix runs on Ubuntu; source-level Windows tests are not
equivalent to a shipped Windows application test.
[Releases][n-releases], [PyPI metadata][n-pypi], [README][n-readme], [CI][n-ci].

**Fit:** a serious third candidate, especially if minimal infrastructure is
decisive. Require a reproducible Windows package from a reconciled source/tag,
host-only generation and synthetic persistence/retrieval tests before ranking
it above Mem0. Small mandatory dependency count is not a reliability result.

## 4. Hindsight: rich memory with an app-owned local service

The MIT repository contains the real engine. Retain extracts structured facts;
recall combines semantic, lexical, temporal and graph retrieval; reflect adds
generation. Source documents/chunks can be returned with recalled facts, and
document IDs support replacement and bulk removal. Those are useful building
blocks for inspectable learning memory. [Licence][h-license],
[engine overview][h-readme], [document API][h-documents].

Native Windows x64 with `pg0` is explicitly documented. “Embedded” here means
an automatically started **PostgreSQL process**, not SQLite: the source imports
`pg0-embedded`, starts/stops it and obtains a local connection URI. PyPI exposes
a Windows x64 wheel. There is no inherent Docker requirement, but packaging
must include database binaries/extensions, orderly shutdown, migration,
backup and app-owned ports/data. [Installation][h-install],
[database lifecycle code][h-pg0], [pg0 wheel metadata][h-pg0-pypi].

The Hermes plugin's current maintainers describe a separate daemon environment
because Hindsight's full dependency tree conflicts with Hermes extras. It uses
an installed binary or a `uvx` fallback. Renulus should bundle the tested worker
environment rather than resolve packages on a doctor's computer. The plugin
also documents defaults such as cloud mode and automatic per-turn capture;
these require explicit local-mode and retention configuration.
[Hermes plugin documentation][h-hermes].

Hindsight documents `openai-codex` and `opencode-go` providers. **This does not
establish a finished Renulus subscription integration.** The actual Codex
adapter reads/writes Codex's `auth.json` and uses the ChatGPT backend endpoint.
It is not app-owned consent/authentication, and this research did not access
those files. Prefer an adapter to Renulus's approved Hermes connection rather
than copying another application's tokens. [Codex source][h-codex],
[auth implementation][h-auth].

The inspected defaults are `gpt-5.4-mini` for Codex and `deepseek-v4-flash` for
Go, neither the exact Renulus-approved choice. Pin every retain, consolidation,
reflect and refresh route. The default helper models include BGE-small
embeddings and a MiniLM cross-encoder reranker; disable or separately assess
reranking rather than treating approval of embedding/OCR helpers as permission
for every local model. [Configuration source][h-config],
[model documentation][h-models].

**Fit:** strong if richer memory reasoning is worth the installed footprint and
process lifecycle work. Its generative extraction, observation consolidation
and reflect calls consume the user's selected subscription capacity even when
there is no separately billed API. Recall plus original chunks can be reused
without making Hindsight the foreground answer generator. Raw source chunks
are useful provenance, but page-accurate PDF citations and no-save case handling
still need Renulus's boundary.

## Triage of the other requested engines

| Project | Open engine and licence scope | Why it is not in the first comparison |
| --- | --- | --- |
| **Basic Memory** | A real local Markdown/SQLite knowledge engine, with MCP and a Hermes integration. Current engine is **AGPL-3.0-or-later**, not permissive Apache/MIT; FastEmbed/sqlite-vec are in current dependencies. [Licence][b-license], [manifest][b-package], [README][b-readme]. | Technically attractive for editable notes and agent-created context. The engine licence introduces a distribution/combination decision for an MIT product, while its Markdown-first authority differs from Renulus's canonical records. AGPL is open source, not a closed engine; do not call it automatically compatible with an MIT-only combined distribution. |
| **OpenViking** | Current **main engine AGPLv3**; Rust CLI/examples Apache-2.0 and Hermes example plugin MIT. Filesystem-style hierarchical context, knowledge and skills are real features. [README and component licences][v-readme]. | A permissive plugin does not relicense its engine. The current quickstart calls for an OpenViking server and embedding/VLM providers; Windows desktop beta is described as an integration console. It is not evidence of a small embedded engine with no server lifecycle. |
| **Graphiti / Zep** | Graphiti is an Apache-2.0 temporal-graph library. Its README explicitly separates it from Zep's **proprietary Context Graph Engine** and managed user/conversation infrastructure. [README][g-readme], [licence][g-license]. | Graphiti can be reused without Zep, but does not supply Zep's whole product. Default OpenAI LLM/embeddings and graph storage need adaptation. Kuzu is explicitly deprecated upstream; an embedded FalkorDBLite option exists, so “always requires Docker” would be inaccurate. Its Windows package and surrounding memory/product work are not established here. |
| **Letta** | The old Apache-2.0 repository now redirects active development to **letta-code** and keeps the V1 API server in an archive branch. [Pinned relocation notice][l-readme], [current project](https://github.com/letta-ai/letta-code). | Do not recommend the historical PostgreSQL service as though it were the current architecture. Current Letta is another stateful-agent harness/app-server/desktop stack. Replacing or nesting the confirmed Hermes runtime is a larger change than adding a memory engine. |
| **memU** | Main now describes a compact agent-driven wiki and scheduled history-to-skills capture, including Hermes/Windows adapters. README says Apache-2.0, but the actual `LICENSE.txt` has a modified copyright-grant section and GitHub reports `NOASSERTION`. [README][u-readme], [actual licence][u-license]. | Old memory-service examples and the March release do not establish the current product. Its prominent setup uses a memu.so key; it also broadly reads agent history. A local-only path, scope controls and licence-text clarification would need verification before calling it a low-edit permissive core. `NOASSERTION` alone is not proof of a restrictive licence. |
| **Memvid** | The Rust **engine itself** is present under Apache-2.0. Default features include Tantivy lexical search and pure-Rust PDF extraction; vector/ONNX support is optional. Python and Node bindings exist. [Cargo manifest][mv-cargo], [README][mv-readme]. | A credible portable document/search component, not the same closed-engine problem as Supermemory. A Windows x64 Python SDK wheel is published. However, its append-only, immutable frames/time-travel model needs a demonstrated physical purge/compaction story for corrected/deleted learning data, and Hermes lifecycle/profile extraction remain integration work. Core/SDK versions differ; do not assume source/binary equivalence. [SDK artifact metadata][mv-pypi]. |
| **Honcho** | Public memory engine, current AGPL-3.0 according to its repository licence; hosted service and SDKs are separate surfaces. [Pinned licence][honcho-license], [project](https://github.com/plastic-labs/honcho). | Adds the same licence-scope decision plus a separate memory reasoning/storage subsystem. No advantage for Renulus's minimal-change Windows baseline was established in this triage. |
| **LangMem** | MIT library with functional memory primitives and a LangGraph store integration. Its example uses an in-memory store; persistent backends are a separate choice. [README][lm-readme], [licence][lm-license]. | Reusable extraction/consolidation ideas, but it does not remove the need for persistence, document ingestion, provider routing or a Hermes adapter. Adding LangGraph's surrounding abstractions solely for memory has no demonstrated advantage over the existing Hermes integration. |

Licence findings above describe the actual inspected components, not a blanket
clearance of every dependency, model weight, optional parser or hosted product.
For Mem0/Cognee preserve Apache notices and mark patches; for MIT components
preserve their notices. Do not relabel third-party code as Renulus's own MIT
code. The AGPL candidates are lower-friction to keep as optional separate tools
than to embed without a deliberate distribution decision; process separation
alone is not a legal conclusion.

## Supermemory: the user's reason for dropping it is confirmed

The project's own self-hosting overview explicitly distinguishes its open SDKs
and public repository from a self-hosted server binary built from a
**separate non-public codebase**. It also describes a lite licence limit, local
embedding defaults, a model supplied by the operator, telemetry, and hosted URL
reading. A public MIT repository and available local binary do not provide
the engine source required for Renulus's fork/reuse strategy. This is sufficient
to support excluding it; there is no reason to keep it as a required dependency.
[Pinned first-party overview][super-overview].

## Concrete adoption shape to compare

This is a proposed comparison, not an implementation instruction or a changed
architecture decision.

1. **Keep Hermes's conversation/context machinery.** Add one memory provider,
   not another agent loop. Retrieved memory is bounded context with record IDs,
   not instructions that can change permissions or retention.
2. **Mem0 option:** reuse the existing OSS plugin and local Qdrant client;
   explicitly configure a bundled small embedder; bridge extraction to the
   approved Hermes provider; forward app-owned paths/custom instructions; add
   scope, durable jobs and safe reindexing. Pair it with the maintained
   document/RAG pipeline selected by the companion investigation.
3. **Cognee option:** reuse its local storage and pipeline; pre-extract
   page-addressable document passages; return raw retrieval to Hermes; route
   every generative stage through the approved subscription. Compare the
   benefit of graph retrieval against the extra native storage/worker surface.
4. **One record authority:** source revisions and learner records stay under
   Renulus ownership. Engines hold derived representations with canonical IDs.
   Editing/deleting invalidates derivatives and queued work; deletion markers
   prevent recapture from retained evidence. Do not maintain competing
   authoritative copies in two engines.
5. **Personalisation stays distinct from evidence.** Preferences, goals,
   mistakes and learning points guide teaching. A source passage supports a
   medical statement. An inferred “memory” of a model answer does not become a
   guideline, verified competency or reviewed test key.

A reasonable common helper candidate is **FastEmbed + BGE-small-en-v1.5**:
FastEmbed is Apache-2.0 and uses ONNX; the upstream BGE-small model card declares
MIT. That makes it a packaging/evaluation candidate, not a new confirmed
model selection or proof of nephrology retrieval quality. Pin the actual ONNX
artifact, tokenizer, hash and notices, not just the upstream model name.
[FastEmbed project](https://github.com/qdrant/fastembed),
[BGE model card](https://huggingface.co/BAAI/bge-small-en-v1.5).

The user should see “Remembered learning”, “Library processing”, an editable
record and an understandable retry action. They should not see Qdrant,
embedding dimensions, graph databases, environment variables or model downloads.
Bundle helper assets and use app-owned directories; background work should be
bounded, cancellable and recoverable after restart. Do not silently degrade to
keyword-only search while advertising semantic recall.

## What would establish a reliable choice

Repository popularity and a benchmark number do not settle these checks. No
tests below were run in this research.

| Check | Concrete evidence required before adoption |
| --- | --- |
| Windows delivery | Fresh standard-user Windows install works without Python, Git, uv, Docker, build tools, manual model downloads or a separately configured server. Confirm the selected Python ABI and every native wheel/DLL. Record installed size, idle RAM, cold-start and import/recall latency. |
| Subscription correctness | Synthetic extraction, compaction and background jobs use only the selected subscription and allowed models. Auth expiry/quota exhaustion queues or fails clearly; no API, cross-subscription or local-generative fallback. |
| Scope and no-save | A temporary synthetic case sentinel never appears in history, memory, embeddings, graph nodes, chunk stores, logs or compaction after restart. Learning principles retained from it contain no raw case details. |
| Reliable capture | Crash/retry and overlapping turns cannot silently lose or duplicate learning evidence. Do not inherit the stock plugin's best-effort thread skipping as the product guarantee. |
| Corrections and deletion | Edit and delete a source while ingestion/consolidation runs; verify old text is absent from live derivatives and supported purge surfaces. Reindex/restart must not resurrect it. Inspect history stores as well as search results. |
| Useful retrieval | Use varied synthetic examples across CKD, transplantation, dialysis, glomerular disease, electrolytes and AKI. Test abbreviations, paraphrases, contradictions, obsolete guidance and irrelevant same-topic memories. Measure source accuracy and task usefulness, not just nearest-neighbour scores. |
| Citations | For digital and scanned multi-column PDFs, retrieved support opens the actual document revision/page. Preserve table headings, units and negations; show extraction failures instead of turning damaged text into confident evidence. |
| Background limits | Measure subscription tokens/calls and CPU time for extraction, improve/consolidation and query synthesis separately. A free engine can still consume substantial subscription quota. |

[m-main]: https://github.com/mem0ai/mem0/blob/abb81c88e1f738a8117d8293530fbc31a5ef8fd9/mem0/memory/main.py
[m-license]: https://github.com/mem0ai/mem0/blob/abb81c88e1f738a8117d8293530fbc31a5ef8fd9/LICENSE
[m-package]: https://github.com/mem0ai/mem0/blob/abb81c88e1f738a8117d8293530fbc31a5ef8fd9/pyproject.toml
[m-qconfig]: https://github.com/mem0ai/mem0/blob/abb81c88e1f738a8117d8293530fbc31a5ef8fd9/mem0/configs/vector_stores/qdrant.py
[m-qdrant]: https://github.com/mem0ai/mem0/blob/abb81c88e1f738a8117d8293530fbc31a5ef8fd9/mem0/vector_stores/qdrant.py
[m-lconfig]: https://github.com/mem0ai/mem0/blob/abb81c88e1f738a8117d8293530fbc31a5ef8fd9/mem0/llms/configs.py
[m-openai]: https://github.com/mem0ai/mem0/blob/abb81c88e1f738a8117d8293530fbc31a5ef8fd9/mem0/llms/openai.py
[m-embed-openai]: https://github.com/mem0ai/mem0/blob/abb81c88e1f738a8117d8293530fbc31a5ef8fd9/mem0/embeddings/openai.py
[m-fastembed]: https://github.com/mem0ai/mem0/blob/abb81c88e1f738a8117d8293530fbc31a5ef8fd9/mem0/embeddings/fastembed.py
[m-factory]: https://github.com/mem0ai/mem0/blob/abb81c88e1f738a8117d8293530fbc31a5ef8fd9/mem0/utils/factory.py
[m-langchain]: https://github.com/mem0ai/mem0/blob/abb81c88e1f738a8117d8293530fbc31a5ef8fd9/mem0/llms/langchain.py
[m-base]: https://github.com/mem0ai/mem0/blob/abb81c88e1f738a8117d8293530fbc31a5ef8fd9/mem0/configs/base.py
[hermes-m-readme]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/plugins/memory/mem0/README.md
[hermes-m-backend]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/plugins/memory/mem0/_backend.py
[hermes-m-provider]: https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/plugins/memory/mem0/__init__.py
[c-package]: https://github.com/topoteretes/cognee/blob/b32d8afc59e1064d9291b9828a8a147be9cc8bab/pyproject.toml
[c-license]: https://github.com/topoteretes/cognee/blob/b32d8afc59e1064d9291b9828a8a147be9cc8bab/LICENSE
[c-docs]: https://docs.cognee.ai/
[c-env]: https://github.com/topoteretes/cognee/blob/b32d8afc59e1064d9291b9828a8a147be9cc8bab/.env.template
[c-kuzu]: https://github.com/topoteretes/cognee/blob/b32d8afc59e1064d9291b9828a8a147be9cc8bab/kuzu/__init__.py
[c-worker]: https://github.com/topoteretes/cognee/blob/b32d8afc59e1064d9291b9828a8a147be9cc8bab/cognee/infrastructure/databases/graph/kuzu/subprocess/proxy.py
[c-llm]: https://github.com/topoteretes/cognee/blob/b32d8afc59e1064d9291b9828a8a147be9cc8bab/cognee/infrastructure/llm/config.py
[c-sampling]: https://github.com/topoteretes/cognee/blob/b32d8afc59e1064d9291b9828a8a147be9cc8bab/cognee/infrastructure/llm/structured_output_framework/litellm_instructor/llm/mcp_sampling/adapter.py
[c-haystack]: https://docs.haystack.deepset.ai/docs/cogneememorystore
[c-pdf]: https://github.com/topoteretes/cognee/blob/b32d8afc59e1064d9291b9828a8a147be9cc8bab/cognee/modules/data/processing/document_types/PdfDocument.py
[c-delete]: https://github.com/topoteretes/cognee/blob/b32d8afc59e1064d9291b9828a8a147be9cc8bab/cognee/modules/graph/methods/try_delete_data_by_graph_provenance.py
[n-host]: https://github.com/mnemosyne-oss/mnemosyne/blob/e871f39480b9b9156faa4396162f7ec1f3b11525/hermes_memory_provider/hermes_llm_adapter.py
[n-package]: https://github.com/mnemosyne-oss/mnemosyne/blob/e871f39480b9b9156faa4396162f7ec1f3b11525/pyproject.toml
[n-embeddings]: https://github.com/mnemosyne-oss/mnemosyne/blob/e871f39480b9b9156faa4396162f7ec1f3b11525/mnemosyne/core/embeddings.py
[n-license]: https://github.com/mnemosyne-oss/mnemosyne/blob/e871f39480b9b9156faa4396162f7ec1f3b11525/LICENSE
[n-provider-readme]: https://github.com/mnemosyne-oss/mnemosyne/blob/e871f39480b9b9156faa4396162f7ec1f3b11525/hermes_memory_provider/README.md
[n-provider]: https://github.com/mnemosyne-oss/mnemosyne/blob/e871f39480b9b9156faa4396162f7ec1f3b11525/hermes_memory_provider/__init__.py
[n-local]: https://github.com/mnemosyne-oss/mnemosyne/blob/e871f39480b9b9156faa4396162f7ec1f3b11525/mnemosyne/core/local_llm.py
[n-media]: https://github.com/mnemosyne-oss/mnemosyne/blob/e871f39480b9b9156faa4396162f7ec1f3b11525/mnemosyne/core/media.py
[n-releases]: https://github.com/mnemosyne-oss/mnemosyne/releases
[n-pypi]: https://pypi.org/pypi/mnemosyne-memory/json
[n-readme]: https://github.com/mnemosyne-oss/mnemosyne/blob/e871f39480b9b9156faa4396162f7ec1f3b11525/README.md
[n-ci]: https://github.com/mnemosyne-oss/mnemosyne/blob/e871f39480b9b9156faa4396162f7ec1f3b11525/.github/workflows/ci.yml
[h-hermes]: https://hermes-agent.nousresearch.com/docs/plugins/hindsight
[h-pg0]: https://github.com/vectorize-io/hindsight/blob/f7dd3f4fd7420f7beec60c32c965e5e5cf7be066/hindsight-api-slim/hindsight_api/pg0.py
[h-license]: https://github.com/vectorize-io/hindsight/blob/f7dd3f4fd7420f7beec60c32c965e5e5cf7be066/LICENSE
[h-readme]: https://github.com/vectorize-io/hindsight/blob/f7dd3f4fd7420f7beec60c32c965e5e5cf7be066/README.md
[h-documents]: https://hindsight.vectorize.io/developer/api/documents
[h-install]: https://hindsight.vectorize.io/developer/installation
[h-pg0-pypi]: https://pypi.org/pypi/pg0-embedded/0.15.2/json
[h-codex]: https://github.com/vectorize-io/hindsight/blob/f7dd3f4fd7420f7beec60c32c965e5e5cf7be066/hindsight-api-slim/hindsight_api/engine/providers/codex_llm.py
[h-auth]: https://github.com/vectorize-io/hindsight/blob/f7dd3f4fd7420f7beec60c32c965e5e5cf7be066/hindsight-api-slim/hindsight_api/engine/providers/codex_auth.py
[h-config]: https://github.com/vectorize-io/hindsight/blob/f7dd3f4fd7420f7beec60c32c965e5e5cf7be066/hindsight-api-slim/hindsight_api/config.py
[h-models]: https://hindsight.vectorize.io/developer/models
[b-license]: https://github.com/basicmachines-co/basic-memory/blob/194afe165b3e7676496aaa53b70e39a78ea5aa4f/LICENSE
[b-package]: https://github.com/basicmachines-co/basic-memory/blob/194afe165b3e7676496aaa53b70e39a78ea5aa4f/pyproject.toml
[b-readme]: https://github.com/basicmachines-co/basic-memory/blob/194afe165b3e7676496aaa53b70e39a78ea5aa4f/README.md
[v-readme]: https://github.com/volcengine/OpenViking/blob/9d9bc85e1f6a15afa7f23b0d7bf114a7c61cad14/README.md
[g-readme]: https://github.com/getzep/graphiti/blob/5d47d4d0182aa6350edeb435b734837a88ed9738/README.md
[g-license]: https://github.com/getzep/graphiti/blob/5d47d4d0182aa6350edeb435b734837a88ed9738/LICENSE
[l-readme]: https://github.com/letta-ai/letta/blob/5bcdd177d70fa2b31a754cfcd801e77b2e1ab16a/README.md
[u-readme]: https://github.com/NevaMind-AI/memU/blob/2c050bc9681a4c0aff1af211a000e73d14f33356/README.md
[u-license]: https://github.com/NevaMind-AI/memU/blob/2c050bc9681a4c0aff1af211a000e73d14f33356/LICENSE.txt
[mv-cargo]: https://github.com/memvid/memvid/blob/e6bd9f7b9c38cd8d5370fa0fc936ac1dcd751813/Cargo.toml
[mv-readme]: https://github.com/memvid/memvid/blob/e6bd9f7b9c38cd8d5370fa0fc936ac1dcd751813/README.md
[mv-pypi]: https://pypi.org/pypi/memvid-sdk/2.0.160/json
[honcho-license]: https://github.com/plastic-labs/honcho/blob/8e4df990d974c146a100e96ab4b3957a6591ceab/LICENSE
[lm-readme]: https://github.com/langchain-ai/langmem/blob/48e3c11f5bb527282c7d5339c6a87a0b35abccfc/README.md
[lm-license]: https://github.com/langchain-ai/langmem/blob/48e3c11f5bb527282c7d5339c6a87a0b35abccfc/LICENSE
[super-overview]: https://github.com/supermemoryai/supermemory/blob/7cc19fa34683a4fe74166ee5d794d271a21b5a92/apps/docs/self-hosting/overview.mdx
