# Existing backup gate classification — 2026-10-28

## Result

All **22 failures and 4 setup errors are pre-existing, unchanged** at the starting commit. Introduced failures: **0**; introduced fixed: **0**; introduced remaining: **0**. No source or test expectations were changed. The existing backup gate remains red; this classification does not pass BF07.

## Reproduction

- Baseline: clean detached `git worktree add H:/wt-base 1a40d9fc`, full commit `1a40d9fc0813eac1672e21427a5a0430933d3aa4`.
- Comparison: shared `codex/backend-finalisation` Python source, including its recovery/frontier changes and migrations 006–010; parallel TS work was left untouched.
- Interpreter: `C:/Renulus/dev/python/Scripts/python.exe`; each file ran separately in a background runner with `-B -m pytest <file> -q --tb=short --basetemp=<unique-directory> --junitxml=<file>`.
- Both revisions used `RENULUS_RECOVERY_HELPERS=C:/Renulus/dev/helper-assets`, `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, and `PYTHONPATH=<selected-checkout>/runtime`. Import checks resolved `renulus.server` inside the selected checkout.
- All profiles and inputs were synthetic. The first two completed files used H: profiles. The interrupted derived-state run on each revision was retried on G: because H: is USB storage; all remaining profiles used unique G: directories on both revisions. Interrupted runs contribute no counts.
- Complete logs and JUnit records: baseline first two files `H:/s11-baseline-2c6b5f`, remaining files `G:/s11-baseline-5011ef`; comparison first two files `H:/s11-current-93cd09`, remaining files and the two regression gates `G:/s11-current-952ce8`.

## Per-file comparison

Counts are passed / failed / errors. Every file below is under `tests/backup/`.

| File | Baseline | Branch | Classification |
| --- | --- | --- | --- |
| `test_attachment_cleanup.py` | 2 / 1 / 0 | 2 / 1 / 0 | pre-existing, unchanged |
| `test_content_release_compatibility.py` | 0 / 2 / 0 | 0 / 2 / 0 | pre-existing, unchanged |
| `test_derived_state_exclusion.py` | 8 / 2 / 0 | 8 / 2 / 0 | pre-existing, unchanged |
| `test_failure_recovery.py` | 6 / 4 / 0 | 6 / 4 / 0 | pre-existing, unchanged |
| `test_offline_engine_round_trip.py` | 0 / 1 / 0 | 0 / 1 / 0 | pre-existing, unchanged |
| `test_prepare_delivery_profile.py` | 2 / 2 / 0 | 2 / 2 / 0 | pre-existing, unchanged |
| `test_round_trip.py` | 12 / 3 / 0 | 12 / 3 / 0 | pre-existing, unchanged |
| `test_saved_case_originals.py` | 6 / 1 / 0 | 6 / 1 / 0 | pre-existing, unchanged |
| `test_segmented_engine_and_history.py` | 0 / 2 / 0 | 0 / 2 / 0 | pre-existing, unchanged |
| `test_segmented_guards.py` | 29 / 2 / 0 | 29 / 2 / 0 | pre-existing, unchanged |
| `test_segmented_recovery.py` | 14 / 2 / 0 | 14 / 2 / 0 | pre-existing, unchanged |
| `test_recovery_capacity_sidecar.py` | 1 / 0 / 4 | 1 / 0 / 4 | pre-existing, unchanged |
| **Total** | **80 / 22 / 4** | **80 / 22 / 4** | **26 pre-existing; 0 introduced** |

## Exact failed/error test IDs

Each ID below is relative to `tests/backup/`. All 26 outcomes reproduce on baseline and branch with the same observed cause.

| Test ID | Baseline | Branch | Classification | One-line cause |
| --- | --- | --- | --- | --- |
| `test_attachment_cleanup.py::test_rollback_preserves_original_and_journal_never_exports` | failed | failed | pre-existing, unchanged | Fixture reopens a profile while its original Library owner is retained; index_owner_busy. |
| `test_content_release_compatibility.py::test_legacy_100_backup_keeps_historical_keys_and_sessions_without_downgrading_current_target[json]` | failed | failed | pre-existing, unchanged | Historical question equality includes mutable current_version: source is 1, current target is 2. |
| `test_content_release_compatibility.py::test_legacy_100_backup_keeps_historical_keys_and_sessions_without_downgrading_current_target[zip]` | failed | failed | pre-existing, unchanged | Historical question equality includes mutable current_version: source is 1, current target is 2. |
| `test_derived_state_exclusion.py::test_download_keeps_canonical_note_history_but_excludes_local_engine_state[json]` | failed | failed | pre-existing, unchanged | Fixture reopens a profile while its original Library owner is retained; index_owner_busy. |
| `test_derived_state_exclusion.py::test_download_keeps_canonical_note_history_but_excludes_local_engine_state[zip]` | failed | failed | pre-existing, unchanged | Fixture reopens a profile while its original Library owner is retained; index_owner_busy. |
| `test_failure_recovery.py::test_pending_rollback_keeps_move_identity_and_blocks_operations_until_restart` | failed | failed | pre-existing, unchanged | Fixture reopens a profile while its original Library owner is retained; index_owner_busy. |
| `test_failure_recovery.py::test_database_commit_failure_rolls_back_all_promotions_and_deletion_cleanup` | failed | failed | pre-existing, unchanged | Global db.transaction fault injection also raises Synthetic commit failure during recovery_guard cleanup. |
| `test_failure_recovery.py::test_abrupt_process_exit_uses_sqlite_receipt_to_roll_back_or_complete_file_journal[before_receipt]` | failed | failed | pre-existing, unchanged | Crash child opens the still-owned target; index_owner_busy exits 1 before the expected injected exit 79/80. |
| `test_failure_recovery.py::test_abrupt_process_exit_uses_sqlite_receipt_to_roll_back_or_complete_file_journal[after_commit]` | failed | failed | pre-existing, unchanged | Crash child opens the still-owned target; index_owner_busy exits 1 before the expected injected exit 79/80. |
| `test_offline_engine_round_trip.py::test_actual_cpu_library_and_manual_note_zip_restore_retrieve_edit_delete` | failed | failed | pre-existing, unchanged | Deletion succeeds but reports cleanup_pending=True; assertion expects immediate physical cleanup. |
| `test_prepare_delivery_profile.py::test_guarded_http_library_delivery_retains_originals_journal_and_queue_without_learner_history[1]` | failed | failed | pre-existing, unchanged | Corrupt backup is correctly refused, then scratch cleanup raises WinError 32 on retained knowledge-native-owner. |
| `test_prepare_delivery_profile.py::test_guarded_http_library_delivery_retains_originals_journal_and_queue_without_learner_history[2]` | failed | failed | pre-existing, unchanged | Corrupt backup is correctly refused, then scratch cleanup raises WinError 32 on retained knowledge-native-owner. |
| `test_round_trip.py::test_parent_rebuild_contracts_persist_passage_counts_and_keep_index_pointer_local[False]` | failed | failed | pre-existing, unchanged | Fixture reopens a profile while its original Library owner is retained; index_owner_busy. |
| `test_round_trip.py::test_parent_rebuild_contracts_persist_passage_counts_and_keep_index_pointer_local[True]` | failed | failed | pre-existing, unchanged | Fixture reopens a profile while its original Library owner is retained; index_owner_busy. |
| `test_round_trip.py::test_real_http_download_raw_preview_restore_and_honest_missing_rebuild_seam` | failed | failed | pre-existing, unchanged | Fixture reopens a profile while its original Library owner is retained; index_owner_busy. |
| `test_saved_case_originals.py::test_newer_saved_case_deletion_suppresses_metadata_and_all_parts_on_old_restore` | failed | failed | pre-existing, unchanged | Backup requested after TestClient shutdown closed the Library; index_close_pending is raised. |
| `test_segmented_engine_and_history.py::test_segmented_legacy_bank_and_learner_history_keep_latest_target_selection` | failed | failed | pre-existing, unchanged | Historical question equality includes mutable current_version: source is 1, current target is 2. |
| `test_segmented_engine_and_history.py::test_actual_cpu_segmented_library_note_restore_retrieve_cite_edit_delete` | failed | failed | pre-existing, unchanged | Library rebuild is partial with retired-index cleanup pending; helper asserts complete. |
| `test_segmented_guards.py::test_version2_restart_receipt_preserves_file_outcome_and_five_digit_staged_identity[before_receipt]` | failed | failed | pre-existing, unchanged | Crash child opens the still-owned target; index_owner_busy exits 1 before the expected injected exit 79/80. |
| `test_segmented_guards.py::test_version2_restart_receipt_preserves_file_outcome_and_five_digit_staged_identity[after_commit]` | failed | failed | pre-existing, unchanged | Crash child opens the still-owned target; index_owner_busy exits 1 before the expected injected exit 79/80. |
| `test_segmented_recovery.py::test_product_api_streams_large_canonical_library_and_rebases_verified_originals` | failed | failed | pre-existing, unchanged | Fixture reopens a profile while its original Library owner is retained; index_owner_busy. |
| `test_segmented_recovery.py::test_legacy_json_and_zip_default_stay_usable_and_status_exposes_versioned_limits` | failed | failed | pre-existing, unchanged | Fixture reopens a profile while its original Library owner is retained; index_owner_busy. |
| `test_recovery_capacity_sidecar.py::test_capacity_experiment_preserves_unicode_citation_and_journal_with_real_schema` | error | error | pre-existing, unchanged | Shared capacity fixture aborts: isolated legacy measurement exits 1 before any of the four checks run. |
| `test_recovery_capacity_sidecar.py::test_late_segment_corruption_rolls_back_all_scratch_records` | error | error | pre-existing, unchanged | Shared capacity fixture aborts: isolated legacy measurement exits 1 before any of the four checks run. |
| `test_recovery_capacity_sidecar.py::test_experimental_descriptor_cannot_reach_sibling_owner_state` | error | error | pre-existing, unchanged | Shared capacity fixture aborts: isolated legacy measurement exits 1 before any of the four checks run. |
| `test_recovery_capacity_sidecar.py::test_experimental_record_budget_refuses_without_partial_stage` | error | error | pre-existing, unchanged | Shared capacity fixture aborts: isolated legacy measurement exits 1 before any of the four checks run. |

The capacity fixture reports only the isolated child failure, not its inner traceback. Its four errors are therefore classified by the reproduced fixture failure; no unobserved inner exception is asserted.

## Required regression gates

- `tests/backup/test_restore_frontier.py`: **24 passed**, 0 failed/errors/skips.
- `tests/integration/test_design_c_migration.py`: **13 passed**, 0 failed/errors/skips.

The branch gate total for the 12 affected files plus these two files is **117 passed, 22 failed, 4 errors**, with no skips. The failures/errors are exactly the 26 reproduced at baseline. These scoped totals do not rerun or claim the full backup suite.

## Scope and remaining work

No introduced failures require repair. Retained ownership, deletion-frontier/native-mapping refusal and historical-content behavior were preserved. The pre-existing fixture/lifetime, immediate-cleanup expectations, mutable content metadata and capacity-experiment failures remain open and unchanged under S11. No `packages/**` edits, migration additions, provider calls or push were made. The clean detached baseline worktree was removed with `git worktree remove --force H:/wt-base`; its path no longer exists.
