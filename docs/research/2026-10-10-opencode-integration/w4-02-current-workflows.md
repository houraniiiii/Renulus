# W4-02 — Current generation, Home and nightly integration

2026-10-10. **Research/testing only; no product changes.** Research checkout: `528025ff0b22477c12ee1512e0e7d15297a6e888`. Implementation inspected/executed: **`76cfdff23e259700bec820e174c200540c7c1e1b`**, using its frozen git-archive export. Current-source citations use the [SHA-256/source map](current-source-map.md); additional repository paths below refer to that same commit and resolve with `git show 76cfdff:<path>`. Eight inspected implementation/test files matched those Git bytes. Planning documents came from the research checkout; the canonical checkout was untouched. Reviewed the required project documents, side-chat findings, [W3-03](w3-03-minimality-design-c.md), [plan](../../planning/OPENCODE_V2_INTEGRATION_PLAN.md), [S3](../../planning/opencode-v2/specs/03-workflows-migration.md), and H12/13/15/17.

**Executed finding: repair the current retrieval seam before claiming working generation.** The 24 selected existing tests produced **8 passes, 16 failures**. Six Home checks and two nightly future-boundary checks passed. All eleven generation checks failed; five further nightly checks failed while depending on generation. These failures do not establish broken downstream publication guards: those assertions were not reached successfully.

`SavedGenerationService._batch`, at `runtime/renulus/assessment/generation_service.py:379` ([source 05](current-source-map.md#source-05)), calls `retrieve(self, SimpleNamespace(...))`. The shared helper, `runtime/renulus/assessment/generated_streaming.py:89`, immediately calls `repo.guard_run(run)`, which this service does not implement. A direct provider-free probe reproduced `AttributeError: 'SavedGenerationService' object has no attribute 'guard_run'`. The existing five-question test returned `generation_failed`, checkpoint `calls:0`; the quota-budget test observed zero transport calls. Source/disable/restore tests awaiting transport startup timed out. **Proposed minimal repair:** give shared retrieval an explicit caller-supplied guard, bound here to job ID/execution and `_check` before/after retrieval. Preserve the legacy caller's guard; a no-op method would erase required checks. No repair was applied.

**Observed static contracts worth retaining.** The [generation service, source 05](current-source-map.md#source-05), already stores payload-checked creation keys, `saved-generation/1` checkpoints, validated items, source hashes/citations, action receipts, execution identity and predetermined test/version IDs. It assembles batches of at most five, rejects normalized duplicate stems/options, supports explicit shorter-count acceptance, and marks unfinished work interrupted on recovery without resubmitting it. Retry changes execution identity but retains items and the counter.

The existing limits are **12 batch calls per job**, three active jobs, 180 seconds per batch, 40 action receipts, 65,536 output characters, 96,000 input bytes and a 1 MiB checkpoint. The counter increments before provider dispatch and survives explicit retry; it is not a durable per-dispatch receipt and can consume a slot before input-size rejection. Auxiliary compaction can call the provider separately through `ProviderManager._finish_context` (`runtime/renulus/runtime/manager.py:360`, commit `76cfdff`), so 12 must not be advertised as a proven total inference-call ceiling.

**Correct the plan's missing-source-fence claim.** `_publish` calls `_check`, which checks policy, execution state, route/settings/context and every pinned source. `_source` checks canonical eligibility, passage/revision hashes, tombstones, rights, excluded pages and effective source status ([source 05](current-source-map.md#source-05), lines 332–377, 465–538). This runs within the same `BEGIN IMMEDIATE` transaction that calls `SavedTestRepository.publish_version` (`runtime/renulus/assessment/test_repository.py:227`, commit `76cfdff`) and records the published job. `runtime/renulus/storage/database.py:52` ([source 15](current-source-map.md#source-15)) also checks bound publication guards at entry/commit. This fence exists statically; the failing runtime selection does not prove its end-to-end operation. Preserve it across IPC, where Python context variables do not automatically carry authority.

**Home: executed reuse, with precise scope.** Six checks passed: concurrent refresh deduplication, eligible old-cache retention after quota failure, rejection after memory edit, cache invalidation after restore epoch, exclusion of case/key sentinels, and no restart replay. `runtime/renulus/study/home_service.py` ([source 20](current-source-map.md#source-20)) validates one fifteen-prompt bundle, rechecks canonical inputs when publishing/reading, and uses `daily_suggestions`, a 60-second timeout and 16,000-character bound. Its key includes day/timezone, **global** scope and settings/policy/context epochs; input dependencies are separately recorded. Project-specific filtering is not demonstrated. Preserve `runtime/renulus/learn/chat_test_service.py:101,165` (commit `76cfdff`): raw drafts pass through volatile fictionalisation and `publish_fictional_artifact`, rather than entering durable ordinary-generation inputs. UI/fictionalisation acceptance was not executed here.

**Nightly: existing occurrence ownership, qualified catch-up.** `runtime/renulus/study/nightly_service.py` ([source 21](current-source-map.md#source-21)) defaults off, polls while running, claims `nightly:YYYY-MM-DD` transactionally, advances `last_claimed_day`, then calls `create_nightly`. Long sleep selects the latest due date; it does not enumerate a backlog. Settings/timezone/epoch resets retain the frontier and rotate an eligibility token. Publication rechecks that token, preferences, current Home inputs and assessment policy. Claim-before-submit means a crash between transactions can consume a date without creating a job; unavailable context also consumes that date.

The two passing recovery tests establish that restart/recovery after the due time arms a **future** night, with no immediate catch-up. Sleep catch-up, disable-during-generation and restore-after-dispatch remain unproved by this run because generation failed first. Actual DST transitions were not tested. H17/S3 should explicitly distinguish an open process waking from sleep from cold restart; adding cold-start catch-up would change current behavior.

**Proposed integration and ticket corrections.** Keep M4's validators/checkpoints/publication, M6's Home eligibility/cache, and the nightly occurrence owner. Replace `_schedule`/provider-event execution in saved generation and Home with OpenCode submissions; return validated results through the existing canonical transactions. Extend existing job checkpoints with stable engine session/input IDs and per-attempt reserved/sent/uncertain/completed state. Reconcile a lost acknowledgement to existing publication receipts. Do not add another workflow or cron subsystem.

| Document | Required correction before implementation |
| --- | --- |
| [H12](../../planning/opencode-v2/tickets/12-publish-one-validated-five-question-saved-test.md) | First repair/retest retrieval; preserve the existing source/publication transaction and immutable version identity. Record current failures instead of inheriting earlier success claims. |
| [H13](../../planning/opencode-v2/tickets/13-resume-10-and-20-question-generation-without-duplicate-work.md) | Treat batches, explicit retry, shorter acceptance and 12-call budget as existing contracts. Add dispatch identities/uncertainty without resetting the counter or replaying validated batches. |
| [H15](../../planning/opencode-v2/tickets/15-generate-daily-suggestions-from-eligible-learning.md) | Adapt the working Home producer; specify global versus project scope. Preserve raw-draft fictionalisation and the shared saved-version result. |
| [H17](../../planning/opencode-v2/tickets/17-run-one-bounded-opt-in-nightly-practice-occurrence.md) | Reuse occurrences; distinguish sleep catch-up from future-only restart. Specify claim/delivery crash handling. [DC19](../../planning/DESIGN_C_IMPLEMENTATION_SPEC.md#dc19--opt-in-nightly-personalised-tests) does not require completion of Home UI: retain shared eligibility dependencies without an unnecessary whole-H15 scheduling dependency. |

**Next-wave gates:** rerun these exact failures after the narrow retrieval repair; then inject source revocation immediately before final commit, lost acknowledgements, dispatch uncertainty, host death and DST/clock changes through the adapted boundary. Upstream remains [source `4b6fea2` host](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/sdk/src/internal/host.ts), whose startup initiates recovery after registration. Its [restart implementation](https://github.com/anomalyco/opencode/blob/4b6fea2875e4f2e3e8a8fee181803e54f7056845/packages/core/src/session/execution/restart.ts) is at-least-once with a default ten-resumption budget; that is distinct from Renulus's twelve-call budget. Gate uncertain work before recovery. [SDK 2.0.26](https://registry.npmjs.org/@opencode%2Fsdk/2.0.26) declares matching packages and Effect rc.112; [tag `9b4ec57`](https://github.com/anomalyco/opencode/blob/9b4ec5714d481559990db0a816d5dec19541a814/packages/sdk/src/internal/host.ts) is a different artifact. No OpenCode execution, real provider, auth, install, service or clinical-quality proof is claimed.

**Exact checks.** Fixtures were inspected first: explicit temporary profiles, synthetic unexpired tokens/transports, disabled helper startup; Library fixtures replace extraction/embedding. Python was `C:/Renulus/dev/python/Scripts/python.exe`, version **3.14.4**. Environment: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, `PYTHONDONTWRITEBYTECODE=1`. Test cwd was `.local/research/opencode-v2-current-76cfdff` beneath this research checkout; the second command used `subprocess.run(..., timeout=150)`.

```text
C:/Renulus/dev/python/Scripts/python.exe -B -m pytest -p pytest_asyncio.plugin -p no:cacheprovider -q tests/assessment/test_saved_generation.py::test_real_selected_route_batches_publish_once_and_keep_keys_private[5] --tb=short
1 failed, 1 warning in 6.37s
```

Second argv: the same executable plus `-B -m pytest -p pytest_asyncio.plugin -p no:cacheprovider -q --tb=short -rA`, followed by these exact `file::suffix` expansions:

```text
tests/assessment/test_saved_generation.py:
test_real_selected_route_batches_publish_once_and_keep_keys_private[10]
test_real_selected_route_batches_publish_once_and_keep_keys_private[20]
test_short_second_batch_is_explicitly_accepted_once_with_every_count
test_invalid_second_batch_retains_prior_work_and_explicit_retry_only_deficit[cross_duplicate]
test_restart_retains_validated_checkpoint_and_never_starts_provider
test_bounded_explicit_retries_and_no_automatic_retry_on_quota
test_actual_library_retrieval_and_pinned_source_provenance
test_actual_source_changes_midstream_block_ready_and_preserve_draft[rights]
test_actual_source_changes_midstream_block_ready_and_preserve_draft[tombstone]
test_changes_during_provider_wait_prevent_stale_publication[epoch]

tests/study/test_design_c_nightly.py:
test_recovery_epoch_and_timezone_arm_future_boundary_only
test_concurrent_sleep_catchup_claims_only_latest_due_day
test_offline_day_consumed_without_retry_then_next_day_can_run
test_running_scheduler_job_cannot_publish_changed_eligibility[off]
test_final_publication_transaction_rechecks_context
test_enabled_restart_after_due_waits_for_next_future_night
test_actual_export_restore_epoch_collision_interrupts_and_waits_for_future_night

tests/study/test_home_suggestions.py:
test_repeated_concurrent_opens_one_real_selected_route_job_and_dated_cache
test_failure_keeps_prior_valid_cache_with_its_date_and_deduplicates[quota]
test_changed_canonical_inputs_or_epoch_settings_policy_block_publication[memory_edit]
test_cache_rechecks_deleted_memory_restore_and_policy_on_every_read[restore]
test_input_boundary_uses_only_eligible_canonical_memory_not_case_originals_or_keys
test_restart_and_cancellation_do_not_resume_provider_work

15 failed, 8 passed, 1 warning in 134.02s (0:02:14)
```

Both pytest processes exited 1; neither hit the process cap. Direct probe: with `PYTHONPATH=runtime`, managed Python `-B -` executed `asyncio.run(retrieve(object.__new__(SavedGenerationService), SimpleNamespace(scope=ContextScope(kind=Scope.GENERATED_PRACTICE), prompt='Synthetic nephrology learning', topic_id=None)))`, catching/asserting the AttributeError above. Other checks were read-only `Get-Content`/`rg`, Git baseline/status and eight-file byte comparisons, and public SHA/registry retrieval. No source was patched to make a test pass.
