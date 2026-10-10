# Updates fixture repair — 2026-10-10

Worktree: `C:/Users/karol/.codex/worktrees/opencode-foundations/repo`.
Branch: `codex/opencode-foundations`.
H24 source checkpoint: `756c8ebc622eef85b39dd8fbff1abbba264df2b9`.
This is the authorised Updates fixture follow-up within H24 verification.
The parent reviewed the completed patch and integrated four fixture files and
this note. No production or scheduling-test source is changed.

## Fixture changes

The autouse fixture and the three local module-order overrides now install the
real Learn, Cases and Assessment owners alongside their existing modules.
Design C constructs conversation routes unconditionally. Its startup recovery
also needs `assessment_test_jobs`, and request-time attempt reconciliation needs
the Assessment migrations. The assembly follows the accepted assessment repair
in `e57e4d89`; the two Library fixtures retain their Knowledge owner and existing
synthetic extraction/embedding boundaries.

The correction-feedback test still installs its intended `1.1.2` pack. A temporary
factory wrapper constructs real `Services` and supplies the existing
`content_pack_root`/`content_pack_selection` contract before bootstrap. The wrapper
is restored immediately after app construction. This avoids installing `1.1.2`
after automatic `1.4.2` activation, with no version-policy or assertion changes.

All **155 existing assertions** in the three edited test files are AST-identical
to the pre-repair checkpoint: application acceptance 64, acquired currency 49,
correction invalidation 42. All four Python files parse and scoped
`git diff --check` passes. Initial evidence: `fixture-checks.json` and
`fixture.diff`; final evidence including the eligibility follow-up:
`fixture-checks-final.json` and `fixture-final.diff`.

## Raw receipts

All paths in this section are beneath
`C:/Renulus/scratch/oc-foundations/uf/`. Each run has its own fresh profile under
`rN/p`, `rN.txt` console log, and `rN/{events.jsonl,nodeids.json,junit.xml,source.json,session.json}`.
The event stream retains every setup/call/teardown outcome and full failure text.
`source.json` records the checkpoint, managed interpreter and SHA-256 hashes.

| Receipt | Change tested | Passed | Failed | Errors/skips | Runner seconds |
| --- | --- | ---: | ---: | ---: | ---: |
| `r1` | Original fixtures; five scoped cases | 0 | 5 | 0 / 0 | 39.98 |
| `r2` | Learn/Cases owners added | 1 | 4 | 0 / 0 | 25.37 |
| `r3` | Assessment owner and historical selection added | 5 | 0 | 0 / 0 | 21.34 |
| `r4` | Complete `tests/updates` suite | 85 | 1 | 0 / 0 | 255.02 |
| `r5` | Sole failed case after exact-copy re-review setup | 1 | 0 | 0 / 0 | 10.79 |

The same five nodeids appear in all three scoped runs (prefix `tests/updates/`):

- `test_scheduling.py::test_cancel_and_shutdown_abort_transport_and_remain_inspectable`
- `test_scheduling.py::test_app_lifespan_runs_overdue_opt_in_and_aborts_it_on_shutdown`
- `test_application_acceptance.py::test_manual_selected_free_routes_offline_restart_and_forbidden_inputs`
- `test_acquired_version_currency.py::test_library_version_choices_round_trip_through_actual_review_api`
- `test_correction_invalidation.py::test_correction_refreshes_real_feedback_without_rewriting_committed_answers_keys_or_scores`

All five original failures stopped at `ConversationRepository` with
`ApiError: Learn is not ready`, before exercising their intended behavior.
In `r2`, direct scheduler cancellation/shutdown passed; lifespan and application
acceptance failed on missing `assessment_test_jobs`, the acquired-copy API failed
on unavailable attempt storage, and correction feedback reached the expected
`ContentConflict: A newly published question must advance its version`.
`r3` executes all five original cases successfully, including real H24 lifespan
shutdown and unchanged history/scoring assertions.

`baseline-checks.json` compares the original four fixtures and five relevant
conversation/Assessment/content implementation files against `c2bd8964`:
all nine are byte-identical before this repair. These are inherited fixture
assembly/bootstrap mismatches; no new H24 production failure was reproduced by
the five focused cases.

The complete `tests/updates` run is `r4`: **85 passed, 1 failed, 0 errors,
0 skipped**, with 86 collected cases, 254.67 pytest seconds and 255.02 runner
seconds. This is one complete run, not a union of focused green receipts.

| Test file under `tests/updates/` | Passed | Failed |
| --- | ---: | ---: |
| `test_acquired_version_currency.py` | 17 | 0 |
| `test_application_acceptance.py` | 1 | 1 |
| `test_correction_invalidation.py` | 9 | 0 |
| `test_literature_refresh.py` | 28 | 0 |
| `test_publications.py` | 6 | 0 |
| `test_review_currency.py` | 8 | 0 |
| `test_scheduling.py` | 12 | 0 |
| `test_updates.py` | 4 | 0 |

The sole failure retained in `r4` is
`tests/updates/test_application_acceptance.py::test_detect_review_exact_copy_invalidate_and_restart_preserve_other_topics`,
then line 149: `current_documents(api)` returned an empty set instead of the four
eligible document IDs. Later assertions in that initial run were not executed.
The failure was reported to the parent during the run; the authorised targeted
classification and fixture repair below resolve it without production changes.

`reconciliation.json` contains outcomes and failures for every exact nodeid in
all four raw receipts: **101 executions, 86 distinct cases**. The same five red
tracers pass in both `r3` and `r4`. All 12 scheduler cases pass in the full run.
The four fixture hashes match both green-tracer and full-run source manifests;
all eight recorded production hashes are unchanged across every run and final
verification. Parent advanced HEAD through `200f0627` during this work; the tested
H24 bytes remain those recorded at `756c8ebc`.

## Exact-copy eligibility follow-up

The initial fixture submitted nonempty `correction` together with positive
`latest_final_verified`/`content_reviewed` flags. `SourceReviews.reviewed_changes`
deliberately clears both flags when recording a correction. A separate subsequent
review must attest the exact corrected edition and original SHA-256. The existing
correction-invalidation tests also assert this rule.

Read-only inspection of the retained `r4` synthetic database found all four copies
with correct publication/edition/hash identity and retrieval rights, but both
currency flags false and the correction reference retained. This concrete state
is preserved in `eligibility-red-state.json`. The Updates review rule, Library
source-status journal and eligibility implementation are each byte-identical to
`c2bd8964`, with SHA-256 comparisons in that receipt. The test setup omitted the
required later attestation; it did not expose a new H24 eligibility defect.

The six-line follow-up changes only the body of the failed test in
`test_application_acceptance.py`. After recording all correction notices for a
publication, it uses the existing review API to attest each exact corrected copy.
Both T08 copies are attested after their notices, because either notice revokes
both copies. Correction records, original expected values and all 155 assertions
remain intact. No shared helper, module assembly or production code changed in
this follow-up. `eligibility.diff` is the isolated review delta.

Only the failed case was rerun: `r5` at `200f0627` records **1 passed, 0 failed,
0 errors, 0 skipped**, in 10.39 pytest seconds. The entire case now executes,
including later byte invalidation, restart, retained correction facts and exact
copy reconfirmation. `reconciliation-followup.json` matches that nodeid to the
sole `r4` failure: **86 distinct cases now have passing evidence**, comprising
85 passes in the complete run plus one targeted repair pass. This is combined
evidence, not a fresh green 86-case run. The parent explicitly requested this
targeted rerun because no shared fixture changed.

The follow-up reconciliation verifies all eight recorded production hashes across
`r1`–`r5`, and confirms that only this one test function differs between `r4` and
`r5`; all other top-level AST nodes and every existing assertion are unchanged.

## Review and hashes

Two read-only scoped reviews are preserved in `reviews.md`. Standards review
found zero documented violations and one optional duplication suggestion: the
correction test's explicit module order now matches the autouse fixture. The
existing explicit override was retained to keep this repair focused on the
provided assembly sites. Spec review found zero implementation findings; that
review preceded full-run completion. The six-line eligibility follow-up received
a separate read-only standards/spec review after `r5`: no material findings on
either axis. That review verified exact publication/edition/hash targeting, all
64 unchanged assertions in this test file, the unchanged production currency
rules and all 18 current source hashes in the `r5` receipt. The parent also
reviewed the diff and retained its bounded single-journey rerun as separate
evidence. Review did not execute another suite.

`receipt-sha256.json` records full hashes for all raw receipts, the runner,
reconciliation, assertion checks, baseline checks, reviews and fixture diff.
`followup-sha256.json` separately preserves the targeted repair evidence and final
diff/checks, without replacing the initial receipts. Selected SHA-256 values:

| Artifact | SHA-256 |
| --- | --- |
| `fixture.diff` | `5510fb4d14dc4c6a3bb5962862d6165ce721edc1c383cd81f673c2b4d54ab0a5` |
| `eligibility.diff` | `6d7a560ab009dede5355b51c2c6c3abda73e847133d87a92e3e7da10aaf86970` |
| `fixture-final.diff` | `dcd812122661af162c8ab343d3cfc27b4130f6d621b31f24350165673e6b7745` |
| `r4/events.jsonl` | `4b98d614ddb4a38ac10b8bd036188820e9d5415acd189a3f93ebdcf5f327b5d4` |
| `r5/events.jsonl` | `4b20a17a7f51dccc68e7e552aaea4c532084975408e27727752c898baf4982d9` |
| `reconciliation.json` | `bf88c847d735f736aa8fd80a302682ce87b2b550ec1828aa0608d96fe9b057fb` |
| `reconciliation-followup.json` | `197b05e6b67d576d99360c6051f509e93c870c088564e174bfaa0094ece8ca3c` |
| `tests/updates/conftest.py` | `f5cbe4b55cb57a370037634d76c5ae495ea47dd4432826ec2fdddca3b1b487a8` |
| `tests/updates/test_application_acceptance.py` | `834494c21f084e0e2d8c8fd216cb574bab727371ef898ec563af3a5195364924` |
| `tests/updates/test_acquired_version_currency.py` | `d6d7dcb69fe7026ba4e1a9a03bf8bfbd1c0019713a730cefd225aba81496487b` |
| `tests/updates/test_correction_invalidation.py` | `e3f9d6c2389d51ea7788e2e90547862569813c30fd87394a1f4664a733f7e0c4` |

## Guarded execution

The owned `run_updates.py` was written after reading the original
`h24/run_shard.py` guard pattern. It uses
`C:/Renulus/dev/python/Scripts/python.exe`, removes optional `RENULUS_*` inputs,
disables pytest plugin autoload, explicitly loads `pytest_asyncio.plugin`,
disables pytest caching and Python bytecode writes, and sets offline helper
flags with owned cache paths. External socket/DNS operations are blocked.
All five receipts report zero external-network attempts and unchanged
source hashes during each run. No live provider, download, private profile or
`live_official_check.py` execution is part of this validation.

The full command, from the worktree above, is:

```powershell
& C:/Renulus/dev/python/Scripts/python.exe -B -u C:/Renulus/scratch/oc-foundations/uf/run_updates.py r4 tests/updates
```

The targeted follow-up uses the same runner with `r5` and the exact nodeid above.
Runner invocation creates a new receipt directory and refuses to reuse it.
This follow-up does not overwrite the original broad-run failures or resolve
provider, backup, Learn or separately owned Today fixture failures.
