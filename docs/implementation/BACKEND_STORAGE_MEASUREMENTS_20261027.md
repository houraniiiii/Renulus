# BF07 Python storage measurements — 2026-10-27

**synthetic, uncalibrated.** These measurements do not calibrate or confirm D05's
proposed 100 decimal GB default or the requested 50–150 GB envelope.

## Observed bytes

Printed by `tests/workers/test_native_storage_growth.py` with `-s` during the
S6b continuation on 2026-10-28:

| Operation | Phase | Logical | Allocated | Unique | Peak allocated |
| --- | --- | ---: | ---: | ---: | ---: |
| Library append | Before | 70356211 | 70370720 | 70370720 | 70422056 |
| Library append | After | 70381169 | 70422056 | 70422056 | 70422056 |
| Rebuild | Before | 70381169 | 70422056 | 70422056 | 70474432 |
| Rebuild | After | 70400183 | 70453640 | 70453640 | 70474432 |
| Compaction | Before | 70400183 | 70453640 | 70453640 | 70453640 |
| Compaction | After | 70400183 | 70453640 | 70453640 | 70453640 |

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

Continuation measurement gate: **1 passed in 43.20 s**. The table is from this
run, using a unique `G:/s6b-growth-*` test directory and the pre-provisioned
`C:/Renulus/dev/helper-assets` directory. The earlier checkpoint run passed in
18.49 s; metadata-size differences are actual observations, not fixed baselines.

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

## S6b continuation verification — 2026-10-28

- `tests/workers/test_native_storage.py`: **1 passed**. Patched caller-available
  bytes refuse a new reservation with `storage_waiting_space` without changing
  status; unsettled work stays charged and settlement transfers cleanup debt.
- The existing real Mem0/Qdrant delete/history/restart/reindex journey, canonical
  history purge, newer-tombstone reconciliation and failed physical purge/rebuild
  checks: **4 passed**. Real local Qdrant and FastEmbed verify history removal,
  deleted-fact absence after reopen and the canonical deletion marker. The
  reconciliation check verifies consumption of an already-present tombstone;
  the locked-generation check preserves debt until cleanup succeeds.
- All checks use synthetic profiles and the selected pre-provisioned assets,
  with `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` for engine journeys.
- `pytest tests/backup tests/integration/test_design_c_migration.py -q`:
  **174 passed, 22 failed, 4 errors in 1673.68 s**. This was one run, with
  `RENULUS_RECOVERY_HELPERS=C:/Renulus/dev/helper-assets` and a unique G: base
  directory. All **24** `test_restore_frontier.py` cases and all **13** Design C
  migration cases passed. There were no skipped engine tests. The required
  existing-backup gate is **not green**, so this continuation does not complete
  BF07 acceptance.

The failed existing checks, grouped by file, are retained explicitly:

| File under `tests/backup/` | Failed | Errors |
| --- | ---: | ---: |
| `test_attachment_cleanup.py` | 1 | 0 |
| `test_content_release_compatibility.py` | 2 | 0 |
| `test_derived_state_exclusion.py` | 2 | 0 |
| `test_failure_recovery.py` | 4 | 0 |
| `test_offline_engine_round_trip.py` | 1 | 0 |
| `test_prepare_delivery_profile.py` | 2 | 0 |
| `test_round_trip.py` | 3 | 0 |
| `test_saved_case_originals.py` | 1 | 0 |
| `test_segmented_engine_and_history.py` | 2 | 0 |
| `test_segmented_guards.py` | 2 | 0 |
| `test_segmented_recovery.py` | 2 | 0 |
| `test_recovery_capacity_sidecar.py` | 0 | 4 |

Visible tracebacks include `index_owner_busy` when a fixture opens the same
profile while its original Library owner is retained (including crash children),
and historical-content equality assertions comparing `current_version=1` with
the current target's `current_version=2`. The four capacity errors share a
fixture whose isolated legacy measurement exits 1 before the checks run; its
synthetic artifacts remain at
`G:/s6b-backup-981c3ba8ae934810bb5b37b708566c94/capacity0/bench`.
These observations do not classify every failure. The existing fixture/lifecycle,
content expectation and capacity failures need separate resolution; no ownership
policy was weakened or historical-content behavior changed to satisfy them.
S6b required no further Python implementation changes to pass its frontier,
reservation, growth and purge checks; the interrupted implementation is retained.
