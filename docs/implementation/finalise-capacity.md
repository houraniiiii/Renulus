# Capacity and recovery finalisation

October 5, 2026 UTC. Worktree: `C:/rn-finalise-20261005/lanes/capacity`;
branch: `codex/finalise-capacity`. The parent accepted the execution handoff and
the capacity slot is **released**. No execution remains in this lane.

The inherited fixture was preserved in
`2f13727b05f12b67018a9ab230f210cb0b1054ce` after confirming no capacity process
was active. The authorised parent revision
`b473ecb3d58ea7dabcef83bac8d0335a420d45ab` was then merged, including the reviewed
`35187437` runner repair integrated as `324af6f2`. The clean tested merge is
`ca2772a431f789606c703b9e908e17036e340918`. This later report changes documentation
only. The parent can cherry-pick the fixture commit and the report commit;
the integration merge is already present in the parent's history.

Only `tests/backup/test_recovery_capacity_sidecar.py` was changed. The product
measurement test, production recovery limits, runtime and content remain
unchanged by the lane. The parent's `test_prepare_delivery_profile.py` fix
arrived through the integration merge and remains parent-owned.

**Receipts are separate runs, with separate acceptance states.** P denotes
`C:/rn-finalise-20261005/capacity-267656f0-01/`; S denotes
`C:/rn-finalise-20261005/capacity-ca2772a4-sidecar-01/`.

| Receipt | Tested revision | UTC execution | Terminal / JUnit | Disposition |
| --- | --- | --- | --- | --- |
| P | `267656f0421c1e3e09931fb855c89becd1e1c415` | 15:13:21–15:18:15 | Exit 1; valid 9-case JUnit, 8 passed and 1 setup error | Complete, `source_unchanged=true`, no guard violations; `accepted_stage_pass=false`. Preserve the eight individually passed checks. |
| S | `ca2772a431f789606c703b9e908e17036e340918` | 15:55:42–15:56:49 | Exit 0; valid 5-case JUnit, 5 passed, no skips/errors/failures | Complete, `source_unchanged=true`, `accepted_stage_pass=true`; all three source checks true, no unexpected module sources or guard violations. |

S contains exactly 15 passed phase events: setup, call and teardown for each of
its five identities. The runner SHA-256 is
`58012d7a5945bf5d5053d567d647e75663489684925adfc74ae86de51ecd2b53`.
The tested fixture SHA-256 is
`b3dc7e8cc8d2be31525583ae708b279e98b9da1e8e3c401a4623dc8edc7f7c7b`.
The unchanged guard used a **12 GiB** disk floor (12,884,901,888 bytes), two CPU
threads, offline mode and fresh synthetic profiles. S observed a minimum
315,757,584,384 free bytes. There was one authorised execution of the five
sidecar identities; no completed product-capacity check was repeated.

The exact executed invocation was:

```powershell
& 'C:/Users/karol/Documents/t3-workspaces/Renulus-wt-integration/.venv/Scripts/python.exe' -B scripts/run_backend_regression.py --scratch C:/rn-finalise-20261005/capacity-ca2772a4-sidecar-01 --expect-commit ca2772a431f789606c703b9e908e17036e340918 --stage capacity tests/backup/test_recovery_capacity_sidecar.py
```

That scratch path is now an immutable receipt, not a retry destination. There
are no missing capacity identities or pending commands at this handoff.

The following set equals the **13 unique capacity identities** excluded by
`C:/rn-finalise-20261005/b4-8c6c4b18/inventory.json`, with no additions or omissions.
P supplies eight individually passed identities and S supplies five. This is a
reconciled identity ledger, not a newly executed aggregate 13-test stage.
The failed b4 application sweep is not relabelled, and these counts are not
added to its 1,214 application passes or to older capacity totals.

| Exact identity | Receipt | Verified phases |
| --- | --- | --- |
| `tests/backup/test_derived_state_exclusion.py::test_large_structured_extraction_is_omitted_before_budget_checks_but_passage_locators_survive[json]` | P | Passed setup, call and teardown |
| `tests/backup/test_derived_state_exclusion.py::test_large_structured_extraction_is_omitted_before_budget_checks_but_passage_locators_survive[zip]` | P | Passed setup, call and teardown |
| `tests/backup/test_recovery_capacity_sidecar.py::test_capacity_experiment_preserves_unicode_citation_and_journal_with_real_schema` | S | Passed setup, call and teardown |
| `tests/backup/test_recovery_capacity_sidecar.py::test_late_segment_corruption_rolls_back_all_scratch_records` | S | Passed setup, call and teardown |
| `tests/backup/test_recovery_capacity_sidecar.py::test_experimental_descriptor_cannot_reach_sibling_owner_state` | S | Passed setup, call and teardown |
| `tests/backup/test_recovery_capacity_sidecar.py::test_experimental_record_budget_refuses_without_partial_stage` | S | Passed setup, call and teardown |
| `tests/backup/test_recovery_capacity_sidecar.py::test_existing_capacity_workspace_is_refused_before_runtime_access` | S | Passed setup, call and teardown |
| `tests/backup/test_round_trip.py::test_catalogue_at_183891_rows_is_explicitly_omitted_without_reading_bulk_metadata` | P | Passed setup, call and teardown |
| `tests/backup/test_round_trip.py::test_oversized_learner_table_is_refused_before_materializing_it_for_either_export` | P | Passed setup, call and teardown |
| `tests/backup/test_segmented_capacity.py::test_product_disk_round_trip_measurement_refuses_whole_corpus_ram_growth` | P | Passed setup, call and teardown |
| `tests/backup/test_segmented_guards.py::test_actual_265_mib_synthetic_originals_exceed_legacy_budget_and_stream_into_fresh_profile` | P | Passed setup, call and teardown |
| `tests/backup/test_segmented_recovery.py::test_product_api_streams_large_canonical_library_and_rebases_verified_originals` | P | Passed setup, call and teardown |
| `tests/knowledge/test_api_collection.py::test_raw_file_upload_and_malformed_size_format_errors` | P | Passed setup, call and teardown |

Source relevance for P was checked against the integrated tested revision.
`git diff 267656f0 ca2772a4` is empty for `runtime/`, `upstream/hermes/`,
`content/`, `packaging/runtime/`, `pyproject.toml`, `uv.lock` and all six files
containing the eight preserved identities. The complete tests tree changed
because the sidecar, runner regressions and parent-owned compatibility checks
changed; the six relevant product-capacity test files did not.

| Unchanged source | Git tree/blob identity at P and S |
| --- | --- |
| `runtime` | `bdc119012dc26a55aff1378ef391f8402a804181` |
| `upstream/hermes` | `01eb1c8a37a5cec57e3099f5a7bf7713f4862456` |
| `content` | `4f07089704b6446dc859df368178bc84b6b4a122` |
| `packaging/runtime` | `c04717446e20ea71c95237fa2354838c35e98da7` |
| `pyproject.toml` | `df7ad2a92b0d8ac8136778ad7fbda0828e486156` |
| `uv.lock` | `6fc5f725e427e1da058ec330c233e5b5dea18825` |

The older completed receipt is preserved at
`C:/Renulus-native-delivery/desktop-20261005/repo/.local/backend-final-20261005T0301Z/capacity/`:
revision `e15e42913e35915b52592262e67ee56905fb84c2`, October 5
03:02:24–03:15:26 UTC, exit 0 and 13-case JUnit without skips/failures/errors.
Its verified JUnit SHA-256 is
`5862cc9c725a45687926908eab4db895878f840e0329255e4c29f1ca03d379d6`.
The inherited reconciliation records 39 passed phases and matching identity
sets. The measurement script, content/knowledge SQL schemas, database and legacy
backup implementation, `pyproject.toml` and `uv.lock` are byte-identical from
that revision through S. Those historical assertions do not establish today's
bootstrap choice or the current guard's 12 GiB floor: its recorded final C free
space was 11,697,520,640 bytes. The five newly validated sidecar identities
supersede reliance on the older fixture evidence without adding another five
to the ledger. The earlier receipt was not rerun.

The P setup error was the experimental scalar/row refusal:
“A scalar/row exceeds the experimental row bound before Python projection.”
A newer programme-mapping manifest exceeded the fixture's 16 KiB bound.
The fix selects immutable `renulus-foundations/1.1.0` through the existing
content bootstrap seam in every isolated worker. The test checks that the
staged database has exactly that pack and the exact published manifest.
This is explicitly a **historical experiment** with
`production_restore_supported=false`; current product restore checks continue
to bootstrap the current bundled release with their existing budgets.

| Historical S experiment setting | Exact limit/fixture |
| --- | --- |
| Documents / passages / passage text bytes | 3 / 32 / 512 |
| Row / segment bytes | 16,384 / 65,536 |
| Canonical / disk budget bytes | 2,097,152 / 1,073,741,824 |
| Record budget | 200,000; refusal test independently lowers it to 10 |
| Legacy result | Within bounds; 791,277 bytes, 515 records |
| Experimental staging result | Validated; 789,842 bytes across 13 segments |
| Source and staged canonical digest | `3ed6c46c7af5be611726f38d36afb8934dbc75f031a34ab995a88a0545a7f9e9` |

The experiment also validates Unicode text, physical citation locators,
headings, the source-status journal, late-corruption transaction rollback,
parent-path descriptor refusal and existing-workspace refusal. It omits derived
extraction/catalogue data and cannot promote a live profile or original.

The unchanged P product disk round trip used 156 synthetic documents,
12,000 passages and 1,536 text bytes per passage; it exported **40,812,491**
canonical bytes, **12,942** records and **16** segments. Export, preview and
restore traced Python peaks were **967,073**, **2,562,276** and **2,564,473**
bytes, each below the existing **16,777,216-byte** assertion. It restored
12,469 canonical records while retaining the required passages and source journal.
Other preserved checks omit a 20 MiB derived extraction before JSON/ZIP budget
checks, omit 183,891 acquisition catalogue rows without reading bulk metadata,
refuse an oversized learner table before materialisation, restore 9,000 cited
passages through the product API, and retain exact hashes for five 53 MiB
synthetic originals (265 MiB total) while the legacy original budget refuses them.
The upload check retains its 65 MiB admission refusal. These were existing
synthetic checks, not new scaling targets.

The S report confirms unchanged legacy limits: archive 301,989,888 bytes;
JSON 16,777,216; individual original 67,108,864; total originals 268,435,456;
manifest 1,048,576; 1,000 originals and 100,000 canonical records.
The experiment's 16 KiB row bound and the product measurement's 16 MiB Python
peak assertion have different roles. Neither was increased. No opt-in 13,000-
document run, actual helper/model inference, native application journey,
compression/provider acceptance or acquired/private-profile work was performed.
Installed product acceptance and derived-engine rebuild remain parent-owned.

The receipt retention/transfer manifest below identifies the **31 metadata and
report files** read at handoff. P and S are already outside this worktree.
R denotes the ignored `C:/rn-finalise-20261005/lanes/capacity/.local/finalise-capacity/`
reconciliation directory; the parent must preserve its two files before worktree
closure. Other relative paths below are beneath `C:/rn-finalise-20261005/`.
The parent's destination copy is pending; this lane does not claim a completed
copy. After transfer, matching paths, byte counts and SHA-256 values establish
receipt identity without repeating execution. The hashes cover receipt metadata
and the three measurement reports, not the synthetic databases, ZIPs, cache or
staged file bodies. The original historical receipt root above also remains
preserved independently. Brief handle closure was lifecycle recovery and did
not trigger another test invocation.

| Receipt path | Bytes | SHA-256 |
| --- | ---: | --- |
| `P/empty-gitconfig` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `P/events.jsonl` | 10421 | `24415cb67675ccecb98efcf8b4606751981c5a1217174845cd69558dc3fa2a40` |
| `P/internal.log` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `P/inventory.json` | 3693 | `51f045bc3c443a38b665f7a658de203c5b04e852f83c925278299e9462534a39` |
| `P/module-sources.json` | 10385 | `21bfd71c3cb2fae2dff7a2582d123486f15e6f116df08e6fa9aa098ce878a233` |
| `P/outcomes.json` | 2542 | `7aa414946e742003354619d77a1375113efbcff14405b9c2ef84107e7da44af1` |
| `P/resources.jsonl` | 1874 | `83f95e618f117d807d79cf50edaa32dfdcc934d6a9b77be045bfc85b421ed7b8` |
| `P/result.json` | 569 | `e3c27f13508d5f0b3d7ee8d09027c1ff5b71ce46e3d141602892d3de914f8c68` |
| `P/results.xml` | 9670 | `20a8c90a68751e523a28f6c95dbcb04bf50906b3358db83ea084b186d66f90f7` |
| `P/run.json` | 3231 | `1b77d4939f3add85381fd64fdd036628b72554fbe933c3021f204d203a618b54` |
| `P/session.json` | 209 | `6f3f075824ab06a5a279611cee88f468f8f3613b6ac6f9986e5f3a506cb560cb` |
| `S/empty-gitconfig` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `S/events.jsonl` | 3655 | `70b72c44706a5ba4fca8edb18a16aa19059bf2cb8a14fc5aca2c04fd310374d5` |
| `S/internal.log` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `S/inventory.json` | 2005 | `c356757e4b381f781d054a2c33d08b1b792ac5f2ee15e6a52109fc1cec9968ac` |
| `S/module-sources.json` | 1920 | `27624f5eacf03e3a55dcb59fe36a2788d249e892e307d7b2d0459b710cd502ed` |
| `S/outcomes.json` | 1368 | `5773f7e64a08e3562e475070f7b03658469fc6ad0782a2b30b8035e401c961a3` |
| `S/resources.jsonl` | 996 | `c6eaa8cfcee7ab29247d324278cab7384ebcd73848c680c14ca28309e500523b` |
| `S/result.json` | 716 | `cb6f364659d6089d1ceac9e597682580192a9be769dcc9d3c48723d72fc97669` |
| `S/results.xml` | 1012 | `d51f316aa0c4944da5492e98a2e064ee62fbe9b2d0d2a7c1be6ae774a2993324` |
| `S/run.json` | 2223 | `4c590c99b58572f7a67be7c5ce3277857bf1630851d2c31b9b0bf57f872fa156` |
| `S/session.json` | 209 | `80580ff00fce39e3f15127f1fbfe7031bccb4996fc0a45807cadf52474a8b416` |
| `capacity-267656f0-01.log` | 14196 | `8faf0e71abf236e835157be269b34ad1eab06f3b5544dee20dd210638d06e579` |
| `capacity-267656f0-01.terminal.json` | 263 | `5ae68e886c2dc6828aee97eb6abd9b1abe52fa4262734bacd712e027d994452e` |
| `capacity-ca2772a4-sidecar-01.log` | 1968 | `2ea016dc84e25944ba9738a18800c0efe67018a14167f570dd9ce96c5bd2458c` |
| `capacity-ca2772a4-sidecar-01.terminal.json` | 279 | `c145e29f6f04f66abe4c70ce94d7417f0581d97af12d8529a80fd8d8b4ae7707` |
| `P/pt/capacity0/bench/report.json` | 2754 | `25a232a7bee1098031b8bc0069ea4b302a71873dd08bd0b53ac27898c82bac10` |
| `P/pt/test_product_disk_round_trip_m0/product-capacity/product-report.json` | 5470 | `f05aed5c59e6c645adf70cc0979dc5b83edfbda8f71a15161e79a5d1ca885e00` |
| `S/pt/capacity0/bench/report.json` | 3467 | `e144f0fae89e377e4ded69412b12e90e9eee7bed5f1836a54bd936e4e5543881` |
| `R/recovered.json` | 9352 | `f0fd0a0da58f6eccd71b2688d0c64d29caa09167e1ea845bc59bfe762a1a7e45` |
| `R/recovered-source-blobs.json` | 1896 | `fdbcb07c60c92a3c38deab9ef05a5e6bf07817e0375dee63c596059936684710` |

