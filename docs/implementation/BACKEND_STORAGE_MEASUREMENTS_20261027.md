# BF07 Python storage measurements — 2026-10-27

**synthetic, uncalibrated.** These measurements do not calibrate or confirm D05's
proposed 100 decimal GB default or the requested 50–150 GB envelope.

## Observed bytes

Printed by `tests/workers/test_native_storage_growth.py` with `-s`:

| Operation | Phase | Logical | Allocated | Unique | Peak allocated |
| --- | --- | ---: | ---: | ---: | ---: |
| Library append | Before | 70335731 | 70350240 | 70350240 | 70401576 |
| Library append | After | 70360689 | 70401576 | 70401576 | 70401576 |
| Rebuild | Before | 70360689 | 70401576 | 70401576 | 70453944 |
| Rebuild | After | 70379694 | 70433152 | 70433152 | 70453944 |
| Compaction | Before | 70379694 | 70433152 | 70433152 | 70433152 |
| Compaction | After | 70379694 | 70433152 | 70433152 | 70433152 |

## Method and limits

- A fresh synthetic profile on G: uses the installed Python environment and
  pre-provisioned, manifest-verified CPU embedding assets. No provider or download
  is used. The shared helper source is read only; the embedding files are copied
  into the synthetic profile and included in its baseline measurement.
- Three small original text notes cover AKI, CKD and transplantation. The test
  uses the existing worker support artifact-grant helper for synthetic input
  byte metadata, then the production `KnowledgeRepository.import_text/run_job`
  flow, real FastEmbed, Docling-core chunking and LanceDB append/FTS.
- Rebuild calls `KnowledgeRepository.rebuild_index()`; compaction calls the
  production `LanceIndex.optimize()` adapter, including public verified-version
  cleanup with age zero and `delete_unverified=False`.
- `NativeStorage.measure()` inventories the entire synthetic profile before and
  after each operation and at entry/return of `stage`, `build_fts`, `optimize`
  and `prepare_retirement`. Logical, allocated and unique are the filesystem
  metadata results; peak is the maximum **observed allocated** total for that
  operation. These checkpoints capture generation overlap, but can miss shorter
  allocation peaks within SDK calls. They are lower bounds, not guarantees or
  reservation forecasts. Shared installed Python/runtime bytes are excluded.
- Retired-generation bytes remain charged. Existing #25/#26 retirement preserves
  old generations and cleanup debt; successful rebuild publication does not prove
  their reclamation or a bounded sustained-growth rate. The first measurement run
  reached all checkpoints, then full repository close refused retained retirement
  debt (`index_cleanup_pending`). Native current-index close is the test's
  teardown boundary; no recursive deletion or debt discharge is introduced.
- C: initially had less than the required 12 GiB free, so production admission
  correctly refused the first append. H: was selected without lowering the floor
  or fabricating available-space values; the final measurement used G:. Initial test setup also required fixing
  the import result's nested job ID; a concurrent import during edits was retried
  after the edits completed. Only the successful operation measurements above
  supply numbers.

Final measurement gate: **1 passed in 18.49 s**. The table is from this final run;
small metadata-size differences between runs are retained as actual observations.

## Python recovery boundary

Python remains the production canonical writer until BF08. Records/JSON and
format-1/format-2 backup restore reject a missing incoming deletion frontier with
`recovery_frontier_missing`, apply current typed deletions/suppression/correction
filters before inserting payloads, consult attachment tombstones before promoting
owned originals, and establish explicit-capture barriers consumed only by
deliberate Memory capture. Global Retry and automatic scan cannot consume them.

Incoming `learn_harness_*` links refuse with
`recovery_native_mapping_required`. Python cannot import or merge native
session/message/tool/child graphs, supply or apply the native owner's stable
mapping, validate complete graph/order closure, or activate a paired candidate.
Those operations remain owned by the TypeScript/native recovery route. No native
graph importer, production authority transfer or BF07/BF08 completion is claimed.
