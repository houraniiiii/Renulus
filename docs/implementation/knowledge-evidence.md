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

Completed artifact acquisition: embedding 67,412,843 bytes;
Docling layout/TableFormer 384,434,829 bytes; OCR 31,749,509 bytes.
Validated lane profile is `.local/runtime/library-check/profile`; the separate
UI verification profile is `.local/runtime/library-ui/profile`. Both contain
only lane-managed public helper assets; no peer credentials/caches were copied.
All artifacts are ignored development state; no original document is committed.

API: `/api/v1/library` has capability, text/raw-file import, documents, jobs,
ordered SSE, cancellation, retrieval, citation/original, collection
preview/catalogue/selected import and cleanup routes. Raw-file upload validates
scope headers before reading the body; stock multipart pre-validation disk
spooling is intentionally avoided. Learn consumes `retrieve(query, topic_id,
scope=ContextScope)` returning `{passages:[...]}`.

Producer follow-up October 4, 2026 at 20:10 UTC:

- Initial backend/artifact commit `beecc7f7`; integrator reports `90d09cd0`.
- Follow-up producer `82b83750` adds catalogue annotations/section/chapter
  metadata, import status, F0 RapidOCR configuration, image full-page OCR,
  long-token callable and conservative replacement/currentness filters.
- Actual lane-local text and native PDF round trips passed with Docling
  2.133.0/core 2.99.0, FastEmbed 0.8.1, LanceDB 0.39.0, RapidOCR 3.9.2,
  ONNX Runtime 1.30.0, tokenizers 0.23.2 and OmegaConf 2.3.1.
  Only loopback OS sockets are allowed by the test guard; external sockets
  are denied. Page/bbox/size provenance and original bytes were checked.
- The direct-image test initially failed because Docling classified a
  one-line teaching image as a section heading; HybridChunker emits body
  passages. The chunking copy now uses a TextItem for that heading-only
  case, retaining the original extraction and OCR provenance. The actual
  image round trip then passed (76.64 seconds, separate cold process).
- The expanded application/API/worker suite passed 17 tests (13.41 seconds).
  It covers durable startup drain, interrupted-job resumption, removal of
  partial LanceDB rows while retaining originals, one serial CPU job,
  cancellation during extraction and of a waiting job, scoped ingestion,
  revision activation, idempotency, deletion and physical old-index cleanup.
- No shared schema was changed after `knowledge-001` adoption. One daemon
  CPU worker reads SQLite jobs; API requests only store/queue inputs and
  wake it. Router lifespan starts/recover/stops the worker. Queued jobs
  survive restart; processing jobs requeue after partial-index cleanup.
  Shutdown stops accepting jobs and gives an active native conversion a
  bounded five-second join; a hard process stop resumes on next startup.
- Full authorised catalogue registration succeeded: 183,891 distinct
  entries, no row errors, observed at about 20:07 UTC on October 4, 2026.
  This is metadata registration, not indexing or verified currentness.
  Acquisition metadata continues to evolve; counts are not global constants.
  Non-dict processing_scope/licence remain visible with unknown permission.
- All retrieval defaults exclude reserved, retracted, superseded, changed
  access, draft/preprint and replaced-topic sources. A source with any
  replaced topic is conservatively suppressed until reviewed passage masks
  exist. Manual unknown edition remains labelled unverified; current-only
  additionally requires final/latest/content-reviewed/non-overdue metadata.

Current limits: native conversions finish their in-flight CPU step before
cancellation frees resources; canonical guards prevent stale publication.
Temporary extraction is still disabled pending a real no-write stream proof.
Browser-native PDF viewing is implemented in the library UI; no PDF.js
dependency or exact-region overlay is claimed. The edition/currentness of
third-party acquisitions is not inferred from receipt or successful OCR.
