# Library responsiveness under queued imports

October 5, 2026. Bounded implementation on `build/library-responsiveness`,
based on `8c98bd117e4898335e8b5ab97d99c626b1aa8180`, in
`E:/Renulus-native-delivery/desktop-20261005/library-responsiveness`.
The parent integration checkout advanced separately to `4b1d2b71`; its wrapper,
native application, profile, schema, packaging and publication remain parent owned.

## Diagnosis and native evidence

The initial normal installed Library list and local retrieval requests exceeded
30 seconds while the durable queue and cold CPU helpers were active. This was
not a permanent pipeline hang: parent aggregate evidence at 03:20:59 UTC showed
516 ready documents and 12,610 passages, up from 481 and 11,755.
After other heavy engine processes stopped at 03:19, the normal Library refresh
initiated at 03:23 succeeded, reporting 547 ready, 6,759 queued and one processing.
The actual visible page is **25**, not the earlier API audit's limit of 100.
The parent retried the same local query at 03:26:49 and reported success at
03:27:33: eight Inspect Citation controls and no empty-result or timeout notice.
These observations are parent supplied; this branch did not access that profile.

A separate code defect is reproducible regardless of that recovery. New event
barriers against the exact pre-fix repository/engines read from Git at `8c98bd11`
made metadata reads time out while query embedding or Lance search remained
blocked. The old list100 path opened **404 SQLite connections** in the same
synthetic revision-detail regression. Three selected new tests failed as expected
in 12.81 seconds; the baseline modules were compiled in memory, without resetting
any checkout. This establishes contention and connection overhead, not a measured
native latency improvement or permanent installed-app failure.

## Scoped change

- Repository metadata operations no longer own the lock during query embedding,
  native search, import staging/FTS or physical cleanup. Lance operations retain
  their own serial lock, with index-before-metadata ordering for recovery.
- Metadata pages use one SQLite read snapshot and batch revision/count/cleanup
  reads for the selected rows. Listing, detail, citation and retrieval avoid
  loading structured extraction JSON. Original lookup also avoids extraction JSON.
- Imports embed and stage at most 64 passages per batch, then build FTS once.
  Large JSON preparation happens outside the publication lock. SQLite passage
  insertion, active revision selection and ready status remain one atomic commit.
- Canonical scope, cancellation, deletion and latest revision are checked between
  expensive stages. Retrieval checks active version, rights, source status, scope
  and page exclusions again after both embedding and search.
- FastEmbed's shared lazy model construction and complete embedding iterator are
  serialized. Existing manifest/hash validation precedes construction; an already
  loaded model is reused without hashing its artifacts again on every batch.
  This makes no assumption that concurrent ONNX inference is safe.
- When an engine owns the index lock, cancellation/deletion retain durable cleanup
  tasks and immediately exclude canonical content. Existing cleanup_pending
  reporting remains truthful; import completion/recovery or explicit cleanup
  retries physical removal. No permissions or source/case privacy guard is relaxed.

Only repository.py, engines.py, three targeted knowledge test files and this note
change. No renderer, shared storage/schema, source originals, helper artifacts,
provider configuration, installed backend or actual user profile changes.

## Verification

Commands below use the existing pinned interpreter (no dependency installation):

```powershell
$python = 'C:/Users/karol/Documents/t3-workspaces/Renulus-wt-integration/.venv/Scripts/python.exe'
& $python -m pytest tests/knowledge/test_repository.py tests/knowledge/test_document_pages.py tests/knowledge/test_worker.py tests/knowledge/test_source_status.py tests/knowledge/test_passage_citation.py -q --tb=short
& $python -m pytest tests/knowledge/test_library_responsiveness.py tests/knowledge/test_document_pages.py tests/knowledge/test_passage_citation.py tests/retrieval -q --tb=short
& $python -m pytest tests/knowledge/test_document_pages.py -q --tb=short
$env:RENULUS_RESPONSIVENESS_HELPERS = 'C:/Users/karol/Documents/t3-workspaces/Renulus-wt-integration/.local/runtime/integration/helpers'
& $python -m pytest tests/knowledge/test_library_responsiveness_offline.py -q --tb=short --basetemp=E:/Renulus-native-delivery/desktop-20261005/library-responsiveness/.local/test-offline
git diff --check
```

Results: initial targeted run **50 passed / 79.12 s**; combined concurrency,
metadata, citation and retrieval run **124 passed / 90.73 s**; final page run
**4 passed / 11.59 s**. These runs overlap and are not additive. The final page
run adds a SQLite authorizer regression that denies extraction_json/original_path
reads with a 2 MiB synthetic extraction, covering limits 25 and 100.
The parallel worker's dedicated concurrency run passed **31 / 10.23 s**, including
actual Library router lifespan, durable worker progress during engine barriers,
source-status races, cancellation, staging failure and atomic publication.

The opt-in selected-engine check passed **1 / 63.96 s** with real
Docling-core HybridChunker, BAAI/bge-small-en-v1.5 CPU FastEmbed and LanceDB.
It used an isolated synthetic profile, one ready note and 100 queued notes;
metadata stayed available during a blocked query and real retrieval succeeded
after release. Existing public helpers were shared read-only, with external
connections forbidden. It did not load a Docling PDF/OCR converter or use
Mem0, providers, downloaded helpers, private data or the installed app.

## Remaining acceptance

The installed build and freeze remain unchanged. The parent must review this
commit before choosing a new product freeze, rebuilding, and checking normal
installed Library25, local retrieval and citation inspection with its active queue.
Cold engine I/O, CPU contention, serialized native search/FTS and metadata volume
can still increase request time; this patch does not promise a 30-second retrieval
bound or uninterrupted metadata during explicit backup/restore/index rebuild.
Native steady-state gates now pass independently of this patch.
