# Knowledge lane evidence — issue #6

Worktree `Renulus-wt-library`, branch `build/library-evidence`. Owned paths are
`runtime/renulus/knowledge/`, `apps/desktop/src/modules/library/`,
`tests/knowledge/` and this record. Shared contracts, storage and dependency
manifests remain with the integrator.

Implementation began October 4, 2026 at 19:28 UTC. The selected engines are
Docling CPU, Docling-core HybridChunker, explicit offline FastEmbed and embedded
LanceDB. SQLite owns documents, revisions, passages, jobs and cleanup work.
No cloud embeddings, generation, paid-provider calls or doctor-flow downloads.

Requested from runtime lane: shared model/tokenizer/dimensions and Docling
CPU helper artifacts. Requested shared dependency adoption: docling,
docling-core[chunking], fastembed, lancedb, pyarrow and tokenizers.

Rules being implemented: stage before activation, preserve a previous active
revision if replacement fails/cancels, check deletion/cancellation before commit,
filter canonical eligibility before retrieval, and physically prune LanceDB old
versions. Temporary/unclassified imports are disabled before any write until a
verified volatile extraction path exists.

Authorised collection is read only. Only metadata preview and explicit selected
entries are supported; there is no sibling scan. Acquisition manifest currently
contains at least one malformed JSON row; preview must report row errors and
preserve source ID/operation rights rather than inventing permission.

Initial checks: nine tests passed on Windows CPython 3.12.13 (16.18 seconds),
using real LanceDB 0.39.0 and deterministic extraction/embedding rule adapters.
These cover canonical scope/topic/currentness filters, reserved material,
idempotency, failed/cancelled replacement, extraction races, restart and
physical LanceDB old-version pruning. This is not a Docling/FastEmbed proof.

Development artifact acquisition code is in `knowledge/acquire_dev_assets.py`.
It uses official immutable HF commit URLs for Qdrant BGE and Docling Heron,
resolves the explicitly selected TableFormer v2.3.0 to a commit, and requires
RapidOCR 3.9.2's shipped SHA-256 values for versioned official RapidAI files.
No generative enrichment/artifacts are acquired. Per-file limit is 350 MiB;
combined limit 900 MiB. Output is F0's helper v1 groups manifest.

Initial artifact acquisition downloaded embedding (67,412,843 bytes) and
Docling layout/TableFormer (384,434,829 bytes). OCR acquisition encountered
a path check failure and is being corrected before real extraction.
All artifacts are ignored development state; no original document is committed.

API: `/api/v1/library` has capability, text/raw-file import, documents, jobs,
ordered SSE, cancellation, retrieval, citation/original, collection
preview/catalogue/selected import and cleanup routes. Raw-file upload validates
scope headers before reading the body; stock multipart pre-validation disk
spooling is intentionally avoided. Learn consumes `retrieve(query, topic_id,
scope=ContextScope)` returning `{passages:[...]}`.
