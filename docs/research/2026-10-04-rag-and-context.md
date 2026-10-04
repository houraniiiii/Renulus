# RAG, embedded search and Hermes context reuse

Research date: **2026-10-04**. Public documentation, source and package metadata
inspection; no library installation, model download, inference or performance
test. Recommendations below preserve the original source-review judgements.
The user has accepted app-managed CPU embeddings/OCR with no doctor-managed
runtime. Generative work retains the existing subscription/model constraints.

**Decision follow-up (2026-10-04):** the user selected FastEmbed + LanceDB OSS
and Hermes context management within the approved starting stack. Framework and
database alternatives below are retained evidence, not additional dependencies.
See the [stack evidence](2026-10-04-starting-stack-evidence.md) and
[planning architecture](../planning/ARCHITECTURE.md). Integration checks remain
future work.

## Findings that change the choice

1. **Reuse Hermes for conversation context.** It already has separate memory and
   context-engine extension points. Adding another complete agent framework is
   unnecessary for the requested capabilities.
2. **LanceDB is the strongest embedded retrieval candidate in this comparison.**
   Its open engine supports local full-text and vector retrieval, hybrid fusion
   and filters. It can take explicit vectors, leaving model selection under
   Renulus control. Its native Windows wheel is published. This is a fit judgement,
   not a measured claim that it is more accurate or reliable than competitors.
3. **FastEmbed is a suitable CPU embedding candidate.** It runs ONNX models
   without a model server or mandatory GPU. Package and model licences must be
   recorded separately. Doctor-facing model selection is unnecessary.
4. **Keep Haystack and LlamaIndex as alternative orchestration choices.** Both
   provide real reusable code, but neither eliminates the need for document,
   memory, provenance and retention decisions. Do not install both by default.
5. **An integration listing does not establish current compatibility.** The
   listed LanceDB–Haystack bridge targets Haystack 2.x and its latest PyPI release
   observed was from 2024, while current Haystack is 3.3. This is a concrete reason
   to consider direct LanceDB calls through a small component instead.

## Reuse the existing Hermes interfaces

This review uses the already inspected immutable Hermes snapshot
[`af90026aa09949579bd423d24def3d38f743cde0`](https://github.com/NousResearch/hermes-agent/tree/af90026aa09949579bd423d24def3d38f743cde0).
It is a source reference, not an imported Renulus implementation.

| Existing surface | Reusable work | Renulus-specific boundary |
| --- | --- | --- |
| `MemoryProvider` | Initialisation/shutdown, prompt block, background prefetch, turn sync, memory tools and lifecycle hooks | Eligible learning evidence, per-user/source/scope filtering and canonical-record revisions |
| `ContextEngine` and built-in compressor | Token accounting, compaction, tool-result pruning; optional request-only `select_context` and post-turn observation | Budget allocation across learner facts, documents and current conversation; temporary-case retention |
| Mem0 plugin OSS mode | In-process engine creation, search/add/update/delete, asynchronous recall, failure circuit breaker | Approved model transport, CPU embedder, durable writes and safe deletion/reindexing |

The [memory interface](https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/agent/memory_provider.py)
allows one external memory provider; built-in memory remains additive.
The [context-engine contract](https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/website/docs/developer-guide/context-engine-plugin.md)
also selects one engine. `select_context` changes one outgoing request, not stored
history. Its default/error behaviour is fail-open, and the completion hook is
best-effort. Therefore these hooks are useful for context selection but must not
be the sole enforcement point for no-save retention or guaranteed capture.

The [Mem0 README](https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/plugins/memory/mem0/README.md)
distinguishes hosted platform, self-hosted HTTP and **in-process OSS** modes.
The last is relevant to Renulus; Docker is not required by that mode. Source
inspection establishes specific adaptation work:

- The [provider](https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/plugins/memory/mem0/__init__.py)
  searches by `user_id`; Renulus also needs retention, source, revision and
  purpose constraints. Automatic sync includes user and assistant text, with a
  default 450-character per-message cap. It can skip a new sync when the previous
  writer remains busy after a five-second join. Use eligible evidence and a
  durable, idempotent queue for saved learning; never silently treat this
  best-effort sync as the progress ledger.
- The [OSS backend](https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/plugins/memory/mem0/_backend.py)
  forwards vector-store, LLM, embedder and version config, but not arbitrary
  memory settings such as a Renulus-owned history path. It already registers a
  custom LLM class, demonstrating a concrete extension seam. Renulus should
  route extraction through its approved generation adapter, not copy the stock
  OpenAI API defaults.
- That backend recreates Qdrant collections or drops a pgvector table when
  embedding dimensions change. Replace this with versioned index rebuild and
  atomic activation from canonical records; changing an embedder must not erase
  the user's memory authority.
- The [setup provider registry](https://github.com/NousResearch/hermes-agent/blob/af90026aa09949579bd423d24def3d38f743cde0/plugins/memory/mem0/_oss_providers.py)
  offers OpenAI/Ollama LLMs and embedders, and Qdrant/pgvector stores. CPU FastEmbed
  and Renulus subscription transport are not established as turnkey wizard
  choices. This is an adapter task, not proof that setting `mode: oss` completes
  Renulus integration.

Keep exact learner progress, assessment attempts, preferences, provenance and
deletion markers in Renulus's canonical SQLite records. A memory engine can
extract and retrieve candidate facts; it should not decide scores or become an
independent authority for what the user has learned.

## Embedded search comparison

| Candidate | Public engine licence | Fit for a bundled Windows application | Main limitation in this use |
| --- | --- | --- | --- |
| **LanceDB OSS** | Apache-2.0 | In-process Python/Rust/TypeScript; local disk; native full-text, vector and hybrid retrieval | Additional Arrow/native dependencies; versioned storage needs explicit physical cleanup |
| **Chroma** | Apache-2.0 | Python `PersistentClient` is available; Windows wheel published | Its own current client docstring prefers server-backed use for production; cloud search features must not be assumed available in the embedded path |
| **Qdrant local mode** | Apache-2.0 | Same Python API without a server; local persistence | Explicitly positioned for small data/demos/tests; warns above 20,000 points; payload indexes have no effect locally |
| **sqlite-vec + SQLite FTS5** | MIT/Apache-2.0 for sqlite-vec | Small native SQLite extension, Windows support; close to existing canonical storage | Pre-v1 breaking-change warning; Renulus must assemble hybrid ranking, chunk/document handling and lifecycle |

Sources: [LanceDB source/licence](https://github.com/lancedb/lancedb/tree/7f5933594f42eeeec1ce73a7ce8e0cd0113cbd82),
[Chroma client source](https://github.com/chroma-core/chroma/blob/e5c22977da46f9410c2e8f2aea54c45d84d29299/chromadb/__init__.py),
[Chroma licence](https://github.com/chroma-core/chroma/blob/e5c22977da46f9410c2e8f2aea54c45d84d29299/LICENSE),
[Qdrant local source](https://github.com/qdrant/qdrant-client/blob/cf747f4b6fa71ba35dfb467931f3fa65f2cdf263/qdrant_client/local/qdrant_local.py),
[Qdrant licence](https://github.com/qdrant/qdrant-client/blob/cf747f4b6fa71ba35dfb467931f3fa65f2cdf263/LICENSE),
[sqlite-vec source and licences](https://github.com/asg017/sqlite-vec/tree/04d28bd21773981e2d266bbf6aa4efbd011eb4f6).

LanceDB's [hybrid API](https://docs.lancedb.com/search/hybrid-search) accepts separate
text and vector inputs and uses reciprocal-rank fusion by default. That fusion
does not require another model call. Use the
[native full-text index](https://docs.lancedb.com/search/full-text-search), rather
than inheriting a legacy Tantivy recipe without checking its Windows support.
Filter by eligible document revision and scope before selecting answer context.

Deletion needs care: [LanceDB deletion](https://docs.lancedb.com/tables/update)
initially excludes rows from queries, while physical content can remain in
versioned files. OSS compaction/cleanup is application-managed; the documented
default retention is seven days. Set an explicit purge policy and account for
[old table versions](https://docs.lancedb.com/tables/versioning). Temporary cases
must never enter this persistent index in the first place. This is not a reason
to reject LanceDB; it is a concrete requirement for the adapter and acceptance
tests.

Chroma's [cloud Search API](https://docs.trychroma.com/cloud) advertises advanced
hybrid ranking. This research does not establish that identical capabilities
are exposed through the selected local `PersistentClient`; do not promise them
from a cloud feature list. Chroma remains a credible alternative if one shared
store materially reduces Mem0 integration work and its desktop tests pass.

## CPU embeddings without a model service

[FastEmbed](https://github.com/qdrant/fastembed) is Apache-2.0 and uses ONNX Runtime.
Its quick start downloads a model automatically. Renulus should instead package
or explicitly provision a pinned, checksummed model into an app-owned directory,
then use local files, controlled worker/thread limits and explicit offline
behaviour. Do not let each framework select/download its own embedding model.

For the proposed Python stack, use **one managed embedding component**, with one
model identity per index version, for document and memory embeddings where
appropriate. An app-owned Node/stdio worker is also compatible with the product
if that boundary saves more work; a process boundary is not a doctor setup step.
Using FastEmbed does not require Qdrant as the database. Either supply its vectors
directly to LanceDB or reuse a verified framework integration. Avoid independent
model downloads/sessions selected implicitly by each framework.

Useful initial evaluation candidates are `BAAI/bge-small-en-v1.5` (MIT,
384 dimensions, 512-token window) and a longer-context permissive alternative
such as `nomic-ai/nomic-embed-text-v1.5` (Apache-2.0). The former is a small baseline,
not a claim of current best performance. The
[supported-model table](https://qdrant.github.io/fastembed/examples/Supported_Models/)
lists small/quantised candidates, model sizes and licences; these are model
artifact sizes, not peak RAM or total installer size. Confirm exact converted
weights and tokenizer terms against the [BGE model card](https://huggingface.co/BAAI/bge-small-en-v1.5)
and [Nomic model card](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5).

Chunk lengths must respect the selected model's tokenizer and limit. A 512-token
embedder does not meaningfully embed an arbitrarily long guideline section just
because an API accepts the string. Preserve table headers, units and source
locators, then test abbreviations, paraphrases, cross-topic questions and
superseded-source filtering. Do not silently add a neural reranker; start with
hybrid fusion and add one only if measured benefit justifies its footprint and
separately reviewed weights.

## RAG framework comparison

**Haystack** is Apache-2.0 and offers explicit reusable converters, splitting,
embedding, retrieval and ranking components. Its
[DocumentSplitter](https://docs.haystack.deepset.ai/docs/documentsplitter) preserves
metadata and adds source/page information; correct original extraction is still
necessary. [Custom components](https://docs.haystack.deepset.ai/docs/custom-components)
can wrap a small direct-library boundary without adopting Haystack's agent loop.
Its [integration catalogue](https://haystack.deepset.ai/integrations) includes
deepset-maintained Docling, Kreuzberg and FastEmbed components. The existence of
[Mem0](https://docs.haystack.deepset.ai/docs/mem0memorystore) and
[Cognee](https://docs.haystack.deepset.ai/docs/cogneememorystore) memory wrappers
does not eliminate those engines' model/deployment requirements.

The Kreuzberg integration listing must not be assumed to cover the newer Xberg
API/package. The [ingestion investigation](2026-10-04-document-ingestion.md)
records the successor/version boundary and the previous line's short LTS window.

Haystack's current [3.3.0 release](https://github.com/deepset-ai/haystack/releases/tag/v3.3.0)
includes concrete retrieval, PDF and citation-offset fixes. This is maintenance
evidence, not a guarantee of no bugs. Its
[telemetry](https://docs.haystack.deepset.ai/docs/telemetry) is enabled by default;
disable it for the controlled Renulus runtime. Do not confuse the Apache OSS
framework with the separately offered enterprise platform.

The community [LanceDB integration](https://haystack.deepset.ai/integrations/lancedb)
is authored by Alan Meeson, not marked as deepset-maintained. Its
[manifest](https://github.com/alanmeeson/lancedb-haystack/blob/main/pyproject.toml)
targets Haystack 2.x and includes Tantivy, DuckDB, pandas and Arrow. PyPI reports
[`lancedb-haystack` 0.1.1](https://pypi.org/project/lancedb-haystack/0.1.1/)
uploaded 2024-10-20. Verify compatibility before reuse; a direct LanceDB component
may be less work than carrying this bridge's extra dependencies. No incompatibility
was demonstrated by execution in this research.

**LlamaIndex core** is MIT and remains a useful alternative if its ingestion
pipeline and chosen reader/store integrations reduce glue code. Its
[ingestion pipeline](https://developers.llamaindex.ai/python/framework/module_guides/loading/ingestion_pipeline/)
provides transformations, caching, document hashing and vector-store integration.
The [source](https://github.com/run-llama/llama_index/blob/962940ddc079cc21701d28d1237c84c82a7c5164/llama-index-core/llama_index/core/ingestion/pipeline.py)
defaults to a splitter plus `Settings.embed_model`; explicitly choose the
embedder, transformations and caches instead of using defaults. Incremental
library import must not use a whole-corpus deletion strategy accidentally.

The inspected upsert path deletes previous document/vector entries before
processing their replacement; it is not atomic revision activation. Renulus
still needs staged replacement that preserves the active revision on failure.
Also, `disable_cache=True` does not disable writes to attached document/vector
stores. Temporary-case processing must bypass persistent stores as well as
transformation caches. These behaviours follow from the pinned pipeline source
above and are reasons to reuse its primitives behind an explicit boundary.

The current [LlamaIndex README](https://github.com/run-llama/llama_index/blob/962940ddc079cc21701d28d1237c84c82a7c5164/README.md)
says the company's primary focus has shifted toward LlamaParse, LiteParse and
document benchmarks while leaving the OSS toolkit available. This is a
maintenance-direction signal, not evidence of abandonment. LlamaParse is a
separate service and not part of the MIT core engine. For Renulus, use explicit
core/integration packages and no hosted parsing dependency.

**Recommendation:** start with the maintained extraction/chunking/search engine
APIs through Hermes, but do not infer minimum total work from small API size.
Docling's document model and HybridChunker already supply significant structure;
LanceDB supplies indexing and fusion. Where hashing, ingestion caches and
document/vector-store coordination would otherwise become custom generic code,
compare **selected LlamaIndex core ingestion components** first. Haystack is the
alternative when component routing/branching is the main need. Compare real
adapter coverage, dependencies, failure handling and installed size; do not
install both by default or write a new generic pipeline framework.

Also compare selected AnythingLLM/Kotaemon modules and reduced-model QMD rather
than rejecting their useful parts because their complete apps are a poor fit.
The [synthesis reuse table](2026-10-04-context-framework-recommendation.md)
separates existing generic functionality, coupling costs and Renulus-specific
rules. This source review establishes candidates and concrete seams; measured
integration effort remains an implementation result.

## Package evidence and limits

### Additional graph/reasoning retrieval candidates

[PageIndex](https://github.com/VectifyAI/PageIndex) is a genuine MIT alternative
for navigating long documents through a hierarchical index and model-guided
retrieval. The current README documents local indexing/retrieval, not only a
cloud client. “Local” still uses configured LLM calls for refinement and search;
its example API-key/model defaults are outside Renulus's selected route.
Its [manifest](https://github.com/VectifyAI/PageIndex/blob/main/pyproject.toml)
includes LiteLLM, OpenAI Agents, PDF readers and an alpha development classifier.
Treat it as a possible targeted tool for a long textbook or guideline after
subscription adaptation, not the default low-latency library/personal-memory
engine. Its FinanceBench result is vendor-reported financial-document evidence,
not nephrology performance, OCR coverage or a comparison run for Renulus.

[LightRAG](https://github.com/HKUDS/LightRAG) is MIT and offers graph-based retrieval
with configurable storage/model routes. Its current documentation separates
EXTRACT, QUERY, KEYWORDS and VLM roles and reports incorporating multimodal
RAG-Anything work. Every generative role needs Renulus's model boundary; graph
construction/deletion introduces additional derived state to manage. It remains
a credible graph-RAG comparison if plain hybrid retrieval fails cross-document
questions, but no evidence here establishes that the extra graph processing is
necessary for Renulus's first working flows.

The separate [RAG-Anything manifest](https://github.com/HKUDS/RAG-Anything/blob/main/pyproject.toml)
declares MIT for its code but also requires `mineru[core]>=3.4.1` and
`lightrag-hku<1.5`. Its [README](https://github.com/HKUDS/RAG-Anything) allows other
parsers, but selecting one in configuration does not by itself remove the
declared MinerU package dependency. Thus the root MIT label is insufficient to
clear a distribution bundle; the parser/model terms and version constraints
need separate review. This strengthens the case for a smaller explicitly
selected ingestion/retrieval stack. These three candidates received bounded
source/manifest triage, not the deeper adapter audit applied to the primary
shortlist.

### Observed releases

Versions below are observed releases, **not a dependency lock**. A pure-Python
wheel does not establish compatibility of all its transitive native dependencies.
Public PyPI JSON metadata was cached under ignored
`.local/research/context-frameworks-2026-10-04/`.

| Package | Observed stable version | Upload date | Windows evidence |
| --- | --- | --- | --- |
| [haystack-ai](https://pypi.org/project/haystack-ai/3.3.0/) | 3.3.0 | 2026-10-01 | Universal Python wheel; manifest lists Python 3.14 |
| [llama-index-core](https://pypi.org/project/llama-index-core/0.14.25/) | 0.14.25 | 2026-09-21 | Universal Python wheel |
| [lancedb](https://pypi.org/project/lancedb/0.39.0/#files) | 0.39.0 | 2026-09-21 | `cp310-abi3-win_amd64` wheel |
| [chromadb](https://pypi.org/project/chromadb/1.5.9/#files) | 1.5.9 | 2026-05-05 | `cp39-abi3-win_amd64` wheel |
| [qdrant-client](https://pypi.org/project/qdrant-client/1.19.1/) | 1.19.1 | 2026-09-16 | Universal Python wheel |
| [sqlite-vec](https://pypi.org/project/sqlite-vec/0.1.9/#files) | 0.1.9 | 2026-03-31 | `py3-none-win_amd64` wheel |
| [fastembed](https://pypi.org/project/fastembed/0.8.1/) | 0.8.1 | 2026-09-22 | Universal Python wheel; manifest has Python 3.14 dependency branches |

Further metadata checks found Windows CPython 3.14 wheels for
[ONNX Runtime 1.30.0](https://pypi.org/project/onnxruntime/1.30.0/#files),
[Arrow 25.0.1](https://pypi.org/project/pyarrow/25.0.1/#files),
[NumPy 2.5.3](https://pypi.org/project/numpy/2.5.3/#files) and
[pydantic-core 2.49.0](https://pypi.org/project/pydantic-core/2.49.0/#files), plus an
ABI3 Windows wheel for [tokenizers 0.23.2](https://pypi.org/project/tokenizers/0.23.2/#files).
This reduces a packaging uncertainty around Hermes's proposed Python 3.14
baseline; it does not prove that these versions form a compatible resolved set
or work in an installed Electron application.

GitHub API metadata requests returned unauthenticated rate-limit errors. Public
raw files, primary documentation, package metadata and `git ls-remote` were used
instead. No private GitHub/account state was needed. The immutable heads cited
above and cached metadata make the source inspection reproducible; runtime,
retrieval quality, clean-machine installation and purge tests remain S0/S2/S4
work under the existing implementation plan.
