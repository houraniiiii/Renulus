# Finalise excluded engine evidence — October 5, 2026

**The exact eight-ID r3 run passed, exit 0; the physical engine slot is
released.** At freeze `f3160c596eb3132fc7599c08d5973c3f7ddd9acb`, all eight
JUnit identities and 24 phases reconcile, with unchanged source and zero
guard violations. The original result records `complete=true` and
`accepted_stage_pass=true`. Only the ignored literal-Windows-null guard
correction separates the r2 and r3 wrappers; no product/test fixture changed.

The b4 regression's 19 exclusions still reconcile to exactly four transferred
historical IDs plus the 15 selected once in r1. r1 recorded seven raw passes,
six failures and two skips; its finalizer rejected recorder Git and left the
original preopened `result.json` empty. Its eight failed/skipped IDs were
selected once in each explicitly released r2 and r3 attempt. R2 remains six
failed/two skipped and nonaccepted. Every original receipt is preserved.
Current unique-ID evidence is exactly **4 historical transfers + 7 verified
raw r1 passes + 8 accepted r3 passes = 19 original exclusions**. No historical
or successful r1 identity was repeated. Neither r1 nor r2 is retroactively
accepted, and whole-suite totals must not be added.

This lane owns only this report and ignored local engine preparation/receipts.
The prior 64-row audit, commit `7f6328c8324f668716f6340f942a23470524f175`,
remains separate and untouched. No source/test edit, model load, pytest
collection, native app launch, provider request or public asset copy was
performed while preparing this inventory. The October 5 bounded recovery
authorises committing meaningful preparation evidence in this report. The
previous Volta attempt reported an unsupported model; per the recovery
instruction, no engine execution ran in that attempt. Static preparation
performed no engine/helper execution. The later explicitly released r1, r2
and r3 runs are recorded below; native, compression and provider work remain
outside this lane.

## Receipt provenance and unique identities

The exact b4 exclusions come from
`C:/rn-finalise-20261005/b4-8c6c4b18/inventory.json`, filtering
`items[].category == "engines"`; there is no separate excluded-nodeids file.
The receipt pins source `8c6c4b181281a0d5a6057ff032ab504f82f4e20e`,
branch `codex/finalise-backend-checks-8c6c4b18`, Python 3.14.4, and
harness SHA256 `a6d9aa12ef0da050907cf8da39939b09497c416929ab54c964224fa34bfdd034`.
It collected 1,271 unique IDs, selected 1,219 application IDs, and excluded
52: 19 engines, 13 capacity, 17 harness, two native and one external collection.

The terminal b4 receipts became available during this preparation. They record
completion at **2026-10-05 15:06:49 UTC**, exit 1, 1,214 passed and five failed;
JUnit contains 1,219 unique cases, five failures, no errors or skips.
`source_unchanged=false` and `accepted_stage_pass=false`. All 19 engine IDs
remain explicitly excluded. This is a completed failed application run,
not a clean current-freeze regression or any execution of the engine gap.

The recovered CPU run is
`C:/rn-finalise-20261005/parent/engines-50aac06c/run.json`,
`pinned-engines.xml` and `run.log`. It records source
`50aac06c4293c01c6d425b65e474a5d027250334`, start/finish
**2026-10-05 11:33:49–11:36:12 UTC**, exit 0, and 19 unique JUnit passes,
no failures/errors/skips, 138.873 seconds and seven warnings. The actual
selection was `test_offline_engines.py`, `test_chunk_budget.py`, and
`test_office_conversion.py`. Engine SHA256 is
`7df16dd6dd6c88c47d05a2bb95a48f5c7f74ff5dfb8e779e4376645519f70dd4`;
embedding fingerprint is
`25b40d98b74669a55bb1cc39fb0c53564deede37b1e221b24683dfd8f48455ba`,
and Docling fingerprint is
`dac182ddf8ecc911404169678fc29b116396cd82ba490bdae820e60f3b2ac5e0`.

| Receipt file | SHA256 |
| --- | --- |
| b4 `run.json` | `aefa2fa7d4ad6e578f6fb1322944da870588c57b58fe7c57621993e9ee1ed4cf` |
| b4 `inventory.json` | `3efb4d440e4e2895d5e5fe5e01d1ce0ca7020fc35c1e03ffc2cc993063f7ff63` |
| b4 `result.json` | `6a4dd6459f9a871839be031a4940b28e1ab3d7fff3a3df8e1a6c3543cf893b68` |
| b4 `session.json` | `528e0841782fd6723d2056f70cf15f3fcb2680b7406a768a6f6596bbf03ec160` |
| b4 `results.xml` | `1a26539447f9ef8b290b897b897ea14a5b8fab7264d634d8dcb33ed41571662b` |
| recovered `run.json` | `a6bb4d294a391ea4a0f30654fe200731cf9eba87bcd279c945a3798b768af771` |
| recovered `pinned-engines.xml` | `bc6a3de8227242c765cbe5a2e069714d9d1a22aeab5e87d08d8f0011c30ffba2` |
| recovered `run.log` | `5491acc2c9779e6d8335cfcb3312408f928f78fb75361ddbca0ae94321a476bd` |

The four overlapping historical passes are exactly:

```text
tests/knowledge/test_offline_engines.py::test_real_text_hybrid_roundtrip_and_shared_token_budget
tests/knowledge/test_offline_engines.py::test_real_docling_cpu_page_region_original_roundtrip[pdf]
tests/knowledge/test_offline_engines.py::test_real_docling_cpu_page_region_original_roundtrip[image]
tests/knowledge/test_chunk_budget.py::test_real_hybrid_table_split_reserves_heading_overhead_and_preserves_cells
```

The other 15 recovered passes are Office conversion/tokenizer identities
outside the b4 engine exclusions. They cannot fill the 15 different missing
IDs, prove Office embeddings or prove Mem0. Reconcile by node ID before
combining any totals; adding a suite's raw count to b4 duplicates identities
already selected as application checks. Installed behavior evidence belongs in
a separate mapping and never changes an unexecuted pytest ID to passed.

## Exact remaining 15 IDs

Every ID below was excluded by b4 and is absent from the recovered JUnit.
The original r1 invocation selected this list literally, without `-k`,
whole-directory discovery, deselection broadening or parallel workers.

```text
tests/backup/test_offline_engine_round_trip.py::test_actual_cpu_library_and_manual_note_zip_restore_retrieve_edit_delete
tests/backup/test_prepare_delivery_profile.py::test_guarded_http_library_delivery_retains_originals_journal_and_queue_without_learner_history[1]
tests/backup/test_prepare_delivery_profile.py::test_guarded_http_library_delivery_retains_originals_journal_and_queue_without_learner_history[2]
tests/backup/test_segmented_engine_and_history.py::test_actual_cpu_segmented_library_note_restore_retrieve_cite_edit_delete
tests/cases/test_offline_attachment_flow.py::test_actual_proven_byte_extractor_through_case_preview_apply_save_delete[pdf]
tests/cases/test_offline_attachment_flow.py::test_actual_proven_byte_extractor_through_case_preview_apply_save_delete[png]
tests/cases/test_offline_attachment_flow.py::test_actual_native_stream_after_approved_startup_has_no_filesystem_writes
tests/knowledge/test_byte_extraction.py::test_real_documentstream_text_native_scanned_pdf_and_image_never_write
tests/knowledge/test_byte_extraction.py::test_byte_scope_capability_requires_prepared_verified_helpers
tests/knowledge/test_library_responsiveness_offline.py::test_selected_text_engines_keep_metadata_available_during_query
tests/memory/test_mem0_real.py::test_actual_mem0_qdrant_fastembed_delete_history_restart_reindex
tests/memory/test_mem0_real.py::test_actual_mem0_extraction_uses_only_mocked_scoped_provider
tests/runtime/test_cross_module_generation.py::test_actual_mem0_oss_outbox_rejects_go_without_assets_or_model_calls
tests/runtime/test_helper_startup.py::test_actual_rapidocr_parser_accepts_local_root_and_two_thread_config
tests/runtime/test_windows_helpers.py::test_selected_cpu_stack_imports_and_native_embedded_store_roundtrips
```

## Baseline source comparison — historical preparation

The bounded recovery uses the supplied integrated baseline
`b473ecb3d58ea7dabcef83bac8d0335a420d45ab` at
`C:/Renulus-native-delivery/desktop-20261005/repo`. During static preparation
the observed parent HEAD advanced to
`698fb2c0bc6760388810d52e846f3a8392c38850`, with generated untracked `.vite/`.
Neither observation is an authorised final freeze or slot. All other agents'
edits and the audit lane's prior commit are preserved.

Two of the 12 files defining the 19 b4 exclusions changed at this baseline:
`test_prepare_delivery_profile.py` and `test_segmented_engine_and_history.py`.
The scoped comparison against `50aac06c` additionally identifies the repaired
runner and `test_content_release_compatibility.py`. The inspected knowledge,
memory, cases, runtime helpers, backup implementation, core server/storage/
services/contracts, packaging and dependency locks have no changes in that
comparison. The four recovered knowledge IDs and their inspected runtime/
helper inputs remain unchanged at `b473ecb3`; the receipt lists the exact
comparison scopes. Transfer to the parent's eventual freeze still requires
that comparison to be repeated. These four historical passes do not certify
the whole later application or matching installation.

| Source object | b4 recorded object | Preparation snapshot object |
| --- | --- | --- |
| `runtime` | `3212d73065592d598d27690151f7fb6a8a4ade2c` | `bdc119012dc26a55aff1378ef391f8402a804181` |
| `tests` | `15a7438040d0fa47960d06104e9515234798ce54` | `157dd6748fd4ffa8aa98c7e1fe9e2ee6bd8108cb` |
| `content` | `92124273440676d71e7cb00b4886d07f40c2a236` | `4f07089704b6446dc859df368178bc84b6b4a122` |
| `upstream/hermes` | `01eb1c8a37a5cec57e3099f5a7bf7713f4862456` | same |
| `packaging/runtime` | `c04717446e20ea71c95237fa2354838c35e98da7` | same |
| `pyproject.toml` | `df7ad2a92b0d8ac8136778ad7fbda0828e486156` | same |
| `uv.lock` | `6fc5f725e427e1da058ec330c233e5b5dea18825` | same |

The machine-readable preparation preserves every exact ID, normalized JUnit
identity, current test/harness SHA256, source object, scoped comparison and
public manifest revision in
`C:/rn-finalise-20261005/lanes/audit/.local/engines/engine-gap-plan.json`.
It is preparation evidence, not a model execution receipt. Its prior snapshot
metadata and the earlier static receipts remain preserved. The current bounded
recovery receipt is `.local/engines/preparation-recovery-b473ecb3.json`. The
historical supplementary storage/server/services/contracts comparison remains
in `.local/engines/source-and-helper-provenance.json`; the storage package
`runtime/renulus/storage` retains the unchanged tree
`da3308c1f7eaf8dc82e41734b21abf9f3a9e47e8`.

## Installed proof versus dedicated actual checks

Matching installed evidence must identify the frozen source, unsigned artifact
and installed byte hashes, bundled interpreter/dependencies, exact helper
manifest, OS-only app PATH, isolated synthetic profile and observed assertions.
Source/API tests using the reusable public developer interpreter establish
their recorded producer behavior; they do not establish installed bundling.
No matching installed proof has been supplied to this lane for the 15 gaps.

| Missing behavior / IDs | What matching installed proof can establish | Dedicated check still needed for the test identity or deeper assertion |
| --- | --- | --- |
| ZIP recovery and segmented recovery (two IDs) | Actual restore into a second isolated profile on this PC; original hashes, rights/locators, rebuild, citation/retrieval, manual-note edit/delete and reopen | Exact format-specific corruption, deletion/history purge and rebuilt-index assertions; unexecuted IDs stay unexecuted |
| HTTP delivery formats `[1]` and `[2]` (two IDs) | Current format-2 delivery retaining admitted Library originals, provenance/journal/queue while excluding learner/private state | Format-1 compatibility, tampered reserved-original refusal, filtered tombstones and source-state preservation. A format-2 installed journey does not cover format 1 |
| Cases preview/apply/Save/delete PDF and PNG (two IDs) | Real extraction and volatile preview/apply, explicit Save, citation-aware handoff, delete/cancellation and reopen retention behavior | Both media variants and sentinel scans; ordinary UI success alone does not prove byte absence from logs/history/indexes |
| Native stream no-write, DocumentStream no-write and helper capability lifecycle (three IDs) | Real temporary text/native PDF/scanned PDF/image extraction and visible availability before/after helper startup | Warm-before-input interception of file operations/connections, profile inventories/log sentinels, provenance stripping, explicit unavailable-after-close assertion |
| Responsiveness (one ID) | Library metadata/job state remains usable during actual retrieval/ingestion on this PC, with recorded timings | The selected-engine barrier assertion and 100 queued synthetic records; no claim of broad machine performance from one run |
| Mem0 Qdrant/FastEmbed lifecycle (one ID) | Actual local memory retrieval/reindex, edit/purge/delete, restart and absence of deleted facts | Derived generation deletion, Mem0/Qdrant history/vector sentinel purge and real 384-dimensional FastEmbed delegation |
| Mem0 scoped extraction (one ID) | A matching controlled provider fixture can prove the local producer scope/capture behavior | Actual Mem0 extraction with a deliberately mocked scoped provider; this does not establish live subscription generation |
| Mem0 Go outbox rejection (one ID) | Actual Go eligibility refusal with no provider requests | Dedicated outbox retry/rejection assertions. Its controlled 384-dimensional vectors do not prove embedding inference |
| RapidOCR parser (one ID) | Installed package configuration provenance and CPU thread settings | Actual parser with synthetic manifest metadata; this test does not construct OCR sessions |
| Windows helper imports/stores (one ID) | Bundled imports, CPU provider/CUDA absence and embedded native store compatibility | This test uses literal three-dimensional LanceDB/Qdrant vectors; it does not infer a model or perform Mem0 generation |

These product mappings can avoid repeating an already documented matching
installed journey. They do not erase dedicated negative assertions or justify
adding test counts. The original r1 command retained all 15 missing IDs.

## Original prepared r1 invocation and guards — historical

`scripts/run_backend_regression.py` accepts only application/capacity/harness
stages and denies unreserved inference. **Do not pass `--stage engines` to it.**
The ignored wrapper below reuses its frozen `OfflineGuard`, `ReceiptPlugin`,
preopened `ReceiptFiles`, environment isolation and terminal reconciliation
with `allow_engines=True` only after explicit execution inputs. Source and test
files remain under their existing owners. Before the first explicit slot
release, the wrapper was checked only statically. The subsequent bounded runs
are documented below.

The wrapper now calls the integrated runner's `unexpected_module_sources`
check. It admits `renulus.memory._vendored_hermes_backend` only from the exact
frozen `upstream/hermes/plugins/memory/mem0/_backend.py` path outside runtime.
It rejects a different name at that path, that name at a different path, and
unowned runtime paths. Terminal `source_checks` records HEAD, production,
tests/runner and source-object stability plus unexpected module sources.

Before helper copying/loading, an AST prerequisite requires the guarded
delivery fixture to capture `source_bank = current_bank_snapshot(client,
services)` and call `assert_current_bank(delivered, source_bank)`. This follows
the `b473ecb3` repair across later published content versions without treating
a hard-coded current version as the required bank identity.

The original prepared PowerShell command below records the r1 selection.
The executed r1 command and durable supervisor identity are in `r1-process.json`.
The repaired wrapper now requires the explicit eight-ID retry selection and
a separate short execution root; do not replay this historical command.

```powershell
$RenulusEngineArguments = @(
  '-I', '-B',
  'C:/rn-finalise-20261005/lanes/audit/.local/engines/run-engine-gap.py',
  '--expect-commit', '<parent-granted-40-character-freeze>',
  '--parent-serial-slot', '<parent-granted-slot-reference>',
  '--selection', 'remaining15',
  '--scratch', 'C:/rn-finalise-20261005/lanes/audit/.local/engines/r1'
)
& 'C:/Users/karol/Documents/t3-workspaces/Renulus-wt-integration/.venv/Scripts/python.exe' @RenulusEngineArguments 2>&1 |
  Tee-Object -FilePath 'C:/rn-finalise-20261005/lanes/audit/.local/engines/r1-terminal.log'
$RenulusEngineExit = $LASTEXITCODE
```

The wrapper expands the exact 15 IDs above into `pytest.main` arguments, followed
by `-q -ra --tb=short --durations=20 -p no:cacheprovider
-p pytest_asyncio.plugin --basetemp <scratch>/pt
--junitxml <scratch>/results.xml -o faulthandler_timeout=120
-o log_file=<scratch>/internal.log`. It checks selected and JUnit identities
with multiplicities, full setup/call/teardown, terminal exit/session, source
before/after and loaded Renulus/helper paths. Re-audit transfers if relevant
source changes. The repaired wrapper has no all-19 or remaining-15 replay
option; only `--selection r1-not-passed` is admitted. Prior/future attempts
remain separate, including failed runs.

Use public helpers from
`C:/Renulus-native-delivery/desktop-20261005/environment/helper-assets-3ff9b0d6`
as read-only inputs. Its three groups declare 19 files and **483,597,181 bytes**:
eight embedding files (67,412,843 bytes), eight Docling files (384,434,829) and
three OCR files (31,749,509). After slot grant, the frozen
`scripts/copy_helper_assets.py` verifies source sizes/hashes, copies into fresh
`<scratch>/profile/helpers`, verifies copies and writes the manifest last.
No asset acquisition or public cache modification is allowed. BGE-small
`BAAI/bge-small-en-v1.5` uses the pinned tokenizer, 384 dimensions and a
512-token model budget. Use the declared Docling Heron/tableformer/RapidOCR
artifacts; keep CPU execution and two threads.
The public manifest SHA256 is
`7d5375bf81d4c4dc3c5a9b6a1304d99286f465998a4e23ecc4da5a8103dcfa7d`.
Its embedding revision is `aa8f8b060edb00e03bfdd08813a2949946c8ba55`;
Docling revision is
`b20d1d5fe7f2e76a7d511cd3a7af334c8827974e8d70894288eedfcbcc5da3e0`;
OCR is `rapidocr-3.9.2-shipped-sha256`. These are recorded manifest declarations,
with full asset verification deferred to the serial slot.

The b4 package pins are Docling 2.133.0, Docling-core 2.99.0, FastEmbed 0.8.1,
LanceDB 0.39.0, Mem0ai 2.2.1, Qdrant-client 1.19.1, ONNX Runtime 1.30.0 and
tokenizers 0.23.2. The wrapper checks the recorded versions before models,
isolates TEMP/cache/Mem0/Hermes/appdata, removes inherited provider/proxy settings,
disables bytecode/plugins/telemetry and Hugging Face/Transformers networking,
and overrides the application runner's synthetic tokenizer with
`<scratch>/profile/helpers/fastembed/bge-small-en-v1.5/tokenizer.json`.

Fixture variables point only to the frozen source and owned scratch:

| Variable | Value |
| --- | --- |
| `RENULUS_KNOWLEDGE_TEST_PROFILE`, `RENULUS_CASES_HELPER_PROFILE` | `<scratch>/profile` |
| `RENULUS_MEMORY_HELPERS`, `RENULUS_RECOVERY_HELPERS`, `RENULUS_RESPONSIVENESS_HELPERS` | `<scratch>/profile/helpers` |
| `RENULUS_CASES_KNOWLEDGE_SOURCE` | exact frozen C checkout |
| `RENULUS_CASES_HELPER_MODULE`, `RENULUS_KNOWLEDGE_HELPER_MODULE` | frozen `runtime/renulus/runtime/helpers.py` |

One process runs sequentially, with two CPU threads, a 12 GiB disk floor and
no xdist. Scratch must be new and remain within the assigned lane. Python
audit guards resolve junction targets, deny writes outside scratch and private
profile/parent `.local` reads, prohibit external sockets/DNS and child
applications, permit recorder read-only Git and owned synthetic loopback
fixtures, and reserve parent ports 8787/5196. Windows OS metadata is warmed
before the guarded test phase for JUnit finalization. These are Python guards,
not an OS sandbox or a universal audit of native dependency system calls. The
selected test assertions and explicit app-managed paths supply further
evidence; do not certify unseen native behavior from the recorder alone.

Required new receipts are `<scratch>/run.json`, `inventory.json`,
`events.jsonl`, `resources.jsonl`, `session.json`, `outcomes.json`,
`module-sources.json`, `results.xml`, `result.json` and the terminal log.
Missing helpers, skips, partial phases, missing/finalization-failed JUnit,
identity mismatch, source movement or guard violations cannot pass. A failed
copy/preflight is not a test run and must retain its terminal failure without
claiming a terminal pytest receipt.

## Concrete inputs and gates — historical preparation

1. **Parent source/test prerequisite — source repair verified.** At
   `b473ecb3`, both `[1]`/`[2]` delivery IDs capture the source's current-bank
   snapshot and compare the delivered bank through the shared helpers in
   `test_content_release_compatibility.py`. The obsolete `1.1.0` current-bank
   assertion is removed. The wrapper's prerequisite accepts this repair
   and rejects the old fixture or either missing capture/comparison. These
   are source/recorder checks; no application assertion or engine ID has run.
   Historical bank snapshots remain distinct and preserved.
2. **Parent serial slot and exact freeze.** Supply the full commit/root and
   confirmation that final content is frozen and the heavy engine/native
   slot is exclusively available. Capacity release is not this confirmation.
   Refresh source/receipt identities and the four historical transfers against
   that freeze. An observed clean HEAD is not the slot grant.
3. **Actual evidence.** Execute or receive the exact guarded producer receipts
   for the missing IDs, audit failures/skips/negative assertions and matching
   installed behavior separately. Final engine coverage is a unique-ID set
   reconciliation, not a sum of raw suite sizes. Hand back the recorded
   interpreter/helpers/source, failed assertions and remaining unperformed
   behavior without substituting controlled vectors/provider fixtures for
   actual inference/live generation.
4. **Parent acceptance beyond this lane.** Matching unsigned Windows artifact/
   fresh installation, bundled runtime with OS-only app PATH, normal shutdown/
   reopen, actual required journeys and recovery on this PC remain required.
   Provider/live subscription work is parent-owned and is not initiated here.
   Signing and a separate clean PC/VM are optional future distribution work
   under decision `793eddb4`; neither blocks this delivery or needs further
   owner input.

The five failed b4 application IDs are retained in the ignored reconciliation
receipt. Two cold-subprocess checks reported `ValueError: No closing quotation`
in addition to the three current-bank mismatches; diagnose/recheck them through
the parent/backend owner. No remedy or subsequent pass is inferred here.
The preparation has created no new product failure or capability pass and
does not certify live/native/installed work that has not been observed.

Static preparation checks passed: unique inventory/JUnit reconciliation, exact
4/15 set difference, confirmation that the other 15 recovered Office IDs were
already selected by b4, function-name presence in source AST, exact report IDs,
and wrapper AST/compilation without execution. The receipts are
`C:/rn-finalise-20261005/lanes/audit/.local/engines/preparation-verification.json`
and `preparation-verification-final.json`. These checks neither collected
pytest tests nor imported or instantiated the selected engine packages.
The bounded recovery adds static positive/negative checks of the integrated
module-source function and the wrapper's bank prerequisite, with AST compilation
and exact unchanged 19/4/15 identity sets. Receipt:
`.local/engines/preparation-recovery-b473ecb3.json`. The old receipts remain
historical. The only tracked change eligible for this lane's recovery commit is
this preparation report; the wrapper, plan and receipts remain ignored.
That readiness record predates the parent's final release. Current terminal
evidence and the narrowly prepared retry follow.

## Final freeze, actual r1 terminal and slot release

The parent released `engine-final-f3160c59-20261005` at exact freeze
`f3160c596eb3132fc7599c08d5973c3f7ddd9acb`. Before launch, the four historical
IDs were reconciled against their original JUnit and unchanged inspected
runtime/helper/test inputs, including shared conftest paths. The immutable
proof is `.local/engines/final-freeze-reconciliation-f3160c59.json`; no historical
ID was repeated. The manifest and package pins matched; helpers were copied
and verified into fresh synthetic state without downloads.

Exactly one runner launched at **2026-10-05 16:19:47.368634 UTC**. The venv
launcher PID was **41104**, actual Python runner **31568**, supervisor **37692**,
and terminal observer session **91740**. The run receipt starts at
**16:20:01.730897 UTC**. The intervening critical-path handoff did not cancel
the child: the parent's duplicate-slot guard refused its own launch, then
ownership of the existing child was confirmed in `r1-handoff.json`. There was
no duplicate, termination or retry.

Pytest finished at **16:23:41.376327 UTC**, exit 1, in **214.410 seconds**.
Inventory and JUnit both contain exactly 15 unique selected identities; all
45 setup/call/teardown events reconcile. Results are **7 passed / 6 failed /
2 skipped**, no collection errors or JUnit errors. The minimum free disk was
**313,371,688,960 bytes**. Twelve in-session child-denial violations are retained.
The wrapper then rejected its own read-only Git finalization call because
Windows supplied `executable=None`; its override inspected only that field.
The physical process exited at **16:23:45.739010 UTC**, wrapper exit **1**.
`result.json` remains the original zero-byte preopened file. File existence in
`r1-exit.json` therefore does not imply a valid terminal result.

All three owned PIDs were subsequently observed absent. The engine slot is
released, recorded in `r1-slot-release.json`; the parent owns serial manufacture.
Independent post-terminal source reads at **16:37:48 UTC** confirmed HEAD,
tested input cleanliness, all recorded source objects and loaded module paths
still match the freeze. The exact adopted Hermes module is admitted. These
reads are recorded separately in `r1-reconciliation.json`; they do not repair
the original finalizer or turn the failed batch into an accepted stage pass.

The seven raw r1 passes have one matching JUnit case and three passing phases
each: ZIP recovery, segmented recovery, Library responsiveness, both Mem0
checks, Go outbox rejection, and RapidOCR parser configuration. Their exact
IDs are preserved in the reconciliation and excluded from retry. No installed
or live-provider claim follows from these source checks.

## Concrete failed/skipped assertions and minimum repair

| r1 identities | Actual observation | Minimum repair / evidence boundary |
| --- | --- | --- |
| HTTP delivery `[1]` and `[2]` | `test_prepare_delivery_profile.py:179` expected `backup_integrity`; the actual error was the production 60-character output-profile admission rule | The long pytest profile path fails before archive integrity or the delivered-bank comparison. Move execution/basetemp into a short owned C root. Preserve the production rule and both assertions. |
| Windows selected helper/store imports | Docling's `DoclingVersion` calls `platform.platform()`, then `_syscmd_ver` attempts a Windows metadata child and the strict guard denies it | Warm real `platform.platform()` and `platform.win32_ver()` before guard installation. Keep shell/Python/other child denial active during tests. No mocked OS data or test-phase shell admission. |
| Native-stream no-write and byte-scope capability | Startup imports were not all ready at Cases line 182; temporary extraction was false at byte-scope line 75 | These prerequisites are consistent with the denied Docling cold import. Keep the assertions and startup preparation intact. |
| DocumentStream no-write | Extraction returned the deliberately sanitised `extraction_failed` error at engines line 391 | The dependency-import failure is masked at this seam. Retain the failure and no-write assertion; this run does not establish a separate extraction algorithm defect. |
| PDF/PNG attachment flows | Both skip at Cases line 117: “The actual producer has not published its no-payload-write proof” | Producer capability is false after failed preparation. Do not bypass the capability gate or relabel either identity passed. |
| Wrapper finalization | Read-only recorder Git was denied after pytest ended; original terminal result stayed empty | Recognise the pinned Git executable, frozen recorder function's code identity, exact source cwd and enumerated read-only arguments, including Windows `executable=None`. No broad child exception. |

The necessary preparation repair is confined to the ignored wrapper. No
product or test change is justified or performed for these observed blockers.
Every original failure, skip and guard violation remains available in r1.

## Eight-ID r2 preparation and executed child arguments

The wrapper now accepts only `--selection r1-not-passed`, rehashes the original
r1 receipts and verifies phase-derived outcomes against exact JUnit identities.
Its selection is the **six failed plus two skipped IDs**, excluding all seven
raw passes and all four historical transfers. The plan contains the literal
eight-ID list and the original receipt hashes.

Receipt root: `.local/engines/r2`. Short execution root:
`C:/rn-ef2-1005`. Both were verified absent before the sole r2 launch.
Admission requires fresh absolute
roots, no traversal, no symlink/junction/reparse ancestors, a direct child of
the explicit parent, and a short task-owned C-root name. Profile, helpers,
TEMP/cache and pytest basetemp move to the short execution root; metadata,
events, JUnit and terminal results remain in the receipt root. The delivery
fixture's prospective `pt/engine-recovery0/bad` path is **38 characters**, below
the unchanged 60-character rule. Writes remain confined to those two roots,
with an intended null-device sink exception; its observed normalization defect
is retained below. UNC, private/parent reads, remote
network/DNS, parent preview ports and all unapproved children remain denied.

Real platform metadata warms before `OfflineGuard.install()`. The guard stays
installed throughout tests and finalization. Recorder Git admission uses the
exact executable/caller/cwd/read-only argument set; test-origin Git, mutating
Git, shells and Python children are denied. The integrated adopted-module and
dynamic current-bank prerequisites remain in force.

Static preparation checked AST compilation, the exact eight-ID selection,
rejection of a substituted passed ID, both owned write roots, outside/cross-
boundary write denial, recorder Git recognition and wrong caller/executable/
cwd/arguments rejection, shell/Python denial, remote sockets, parent preview
binds and parent `.local` reads. No guard was globally installed, root created,
pytest test collected, helper copied/loaded or engine/provider/native run
during preparation. Receipt: `retry-preparation-verification.json`.

After Package session 34733 terminated, the parent explicitly released
`engine-r2-f3160c59-20261005`. The four listed Package PIDs were observed absent
before launch. The immutable plan retains its preparation-time held flags;
the actual release and run are recorded in the separate process/run receipts.
The exact child arguments below were executed once by a durable supervisor
with no retry loop. This is a historical invocation; the roots now exist.

```powershell
$RenulusRetryArguments = @(
  '-I', '-B',
  'C:/rn-finalise-20261005/lanes/audit/.local/engines/run-engine-gap.py',
  '--expect-commit', 'f3160c596eb3132fc7599c08d5973c3f7ddd9acb',
  '--parent-serial-slot', 'engine-r2-f3160c59-20261005',
  '--selection', 'r1-not-passed',
  '--scratch', 'C:/rn-finalise-20261005/lanes/audit/.local/engines/r2',
  '--execution-root', 'C:/rn-ef2-1005'
)
& 'C:/Users/karol/Documents/t3-workspaces/Renulus-wt-integration/.venv/Scripts/python.exe' @RenulusRetryArguments
```

Original r1 process, plan snapshot, run, inventory, events, resources, session,
outcomes, module sources, JUnit, empty result, terminal log and exit receipts
are preserved. The plan and repair remain ignored; only this report is tracked.

## Actual r2 terminal, source verification and slot release

The supervisor launched at **2026-10-05 18:03:58.507324 UTC**. Observed Windows
creation identities were actual Python **32856** at **18:03:58.632989 UTC**,
venv launcher **22428** at **18:03:58.532287 UTC**, and supervisor **46364** at
**18:03:57.848606 UTC**. Auxiliary conhost **28192** belonged to the launcher.
Observer session **1310** returned actual exit **1**. Parent relationships,
creation identity and the command are durable in `r2-process.json` and
`r2-process-windows.json`; stdout/stderr are in `r2-terminal.log`.

The wrapper receipt starts at **18:04:11.369377 UTC**. Public helpers were
copied and verified into `C:/rn-ef2-1005/profile/helpers`: the same 19 files
and 483,597,181 bytes with pinned package/manifest identities. Real platform
metadata was warmed before guard installation; no Windows-metadata child
denial was recorded during r2. CPU limits remained two threads. Minimum free
disk was **298,948,669,440 bytes**, above the 12 GiB reserve.

Pytest terminated at **18:06:02.192041 UTC**, with **6 failed / 2 skipped /
0 passed**, no collection or JUnit errors. Its summary reports **107.09 seconds**;
JUnit records **107.083 seconds**. All eight unique inventory, outcome and
JUnit identities match the plan's exact r1-not-passed selection. All **24**
setup/call/teardown records reconcile; every setup and teardown passed. The
original seven passed r1 IDs and four historical overlaps are absent.

Finalization completed at **18:06:05.177772 UTC**. The original r2 result is
valid and nonempty: `complete=true`, `unique_ids_match=true`,
`source_unchanged=true`, `runner_error=null` and `accepted_stage_pass=false`.
All four source checks are true and `unexpected_module_sources={}`. The strict
guard remained installed through tests and finalization; the repaired exact
read-only Git recognition succeeded. The dynamic current-bank prerequisite
passed source admission, but delivery did not reach the bank comparison.

The physical child ended at **18:06:06.228713 UTC**. The supervisor fsynced
the terminal log and wrote `r2-exit.json` with exit **1** and elapsed
**127.721 seconds**, including launch/finalization. All four owned PIDs were
observed absent; the durable absence observation at **18:08:59 UTC** is in
`r2-slot-release.json`. The engine slot is released. No replacement, termination,
successful-ID repeat or expanded suite occurred.

Independent receipt/source reconciliation at **18:12:08 UTC** confirms parent
HEAD remains `f3160c596eb3132fc7599c08d5973c3f7ddd9acb`, tested paths are
clean, all ten source objects still match the final freeze, and the integrated
module-source callable reports no unexpected Renulus/helper paths. Wrapper and
plan hashes match their launch snapshots. Every original r1 hash, including its
zero-byte result and the four-ID overlap proof, remains unchanged. Reconciliation
imports no product/test/engine module and does not repair r1.

## r2 failure handoff — retain all eight nonpassed outcomes

| Exact r2 identities | Actual call assertion or skip | Actionable boundary for parent |
| --- | --- | --- |
| HTTP delivery `[1]` and `[2]` | Delivery line 105 enters the source fixture; recovery fixture line 128 asserts `imports.embedding.ready`, which is false | Helper cold import fails before archive integrity, the output-profile path check or delivered-bank assertions. The short-root repair is present; this run cannot certify delivery. |
| Native-stream no-write | Cases line 182 asserts all approved startup import groups are ready; false | Startup prerequisite remains failed. Preserve readiness; the no-write extraction loop was not reached. |
| Byte-scope capability | Byte extraction line 75 expects `temporary_extraction is True`; false | Capability refusal is consistent with failed approved imports. Preserve the assertion. |
| DocumentStream no-write | Dill `_dill.py:174` calls `get_file_type('r+b')`; line 165 opens `os.devnull`; byte-test line 39 raises `Temporary extraction attempted a file write` | This is a distinct rejection site after approved startup already failed, leaving dependencies cold. Correcting the guard may let existing startup warm Dill before this interceptor. No independent producer defect is established; preserve all no-payload-write assertions. |
| Windows helper/store imports | Docling → Transformers → Torch → Dill reaches the same `os.devnull` probe; wrapper line 232 rejects `SOURCE/nul` as outside both owned roots | The wrapper sink exception compares two different normalizations. Correct only that exact sink recognition; retain shell, remote/private/parent and arbitrary outside-write denial. Store roundtrips were not reached. |
| PDF and PNG attachment flows | Both skip at Cases line 117: “The actual producer has not published its no-payload-write proof” | The producer remains unavailable after failed preparation. Both skips remain unproven; preserve the capability gate. |

All **15** audit denials contain the same `SOURCE/nul` message. A post-terminal
stdlib path observation, without opening files or importing any dependency,
confirms the cause on this interpreter: `os.devnull == 'nul'`,
`str(Path('nul').resolve()) == r'\\.\NUL'`, while
`Path('nul').absolute().resolve() == SOURCE / 'nul'`. The wrapper computes the
latter for event targets and the former for its sink exception, so equality
is false. No denied shell, provider or remote event appears in r2 records.
These are Python-level guards, not a system-wide OS execution audit.

The minimum handoff is consistent exact Windows null-sink recognition in the
ignored guard, plus preserving real approved dependency warmup before temporary
input is placed under a write interceptor. This does not establish an extraction
algorithm defect or justify changing production path rules. Parent owns further
repair decisions. No wrapper, plan, product or test was edited during r2 or its
original reconciliation,
and no r3 is authorised or started. The unique-ID reconciliation remains four
historical transfers, seven raw r1 passes, six failures and two skips across the
original 19 excluded identities; both batches remain nonaccepted.

| Preserved r2 receipt | SHA256 |
| --- | --- |
| `r2/result.json` | `366e26ed149b355a7c1d6fe1bca2b7aa6100f1829ae1f21f7cb58411c6af040c` |
| `r2/results.xml` | `f67ffabfbba08ada507c996372963d83f070682261704b892701bfa5f8576d3c` |
| `r2/events.jsonl` | `9deed401325912599bf8969a529a684378299bbce40cc71a57a7641178cd6974` |
| `r2/module-sources.json` | `7c2bd051d310379fc22312c121c959e3c69fae0703120be1048ae3c525c57d98` |
| `r2-terminal.log` | `d84fc7397f43ea9f26837043f6b04b80ad15349428e4184f117b889b680c32d8` |
| `r2-exit.json` | `b51446367e8f92e2cd4131280cb3aff988baee2e9cc71b6e5505709defdda650` |
| `r2-slot-release.json` | `1670c7c529a6c04474bd0fc09eaef71263733b76614e7c9a1175ecc44ae1cc38` |
| `r2-reconciliation.json` | `0d748f061c84d1f233cf11d89de81874943a4681ad0dd0c14c2b441e41ba1177` |

Complete process, phase, source, guard and original-receipt hashes are in
`C:/rn-finalise-20261005/lanes/audit/.local/engines/r2-reconciliation.json`.
Only this report is tracked and eligible for the report commit.

## R3 guard-only preparation — historical

After the parent requested all six traces, the classification was narrowed:
there are two direct rejection sites, not six independent product defects.
The Windows-import trace ends in the wrapper's false null-sink denial.
DocumentStream ends in its own writable-open interceptor, but its fixture
already ran approved startup unsuccessfully. The same cold Dill import is
then retried inside the interceptor. The earlier claim that a wrapper fix
alone is insufficient was too strong: successful existing startup may warm
Dill before that boundary. Four other failures assert prerequisite readiness
or capability; two attachment IDs skip for missing producer proof. R2 does
not justify editing product startup, extraction or any test.

The only implementation change is in ignored `main.EngineGuard.audit`. On
Windows, writable `open` events whose raw target is the bare case-insensitive
token `nul` are admitted before normalization. Absolute/relative path aliases,
names with extensions/streams/trailing characters, explicit device paths and
filesystem mutations do not receive that exception. All ordinary paths still
require one of the two owned write roots. Child, network, private/profile,
parent-preview, source/freeze and finalization checks are unchanged. No parent
source or `test_prepare_delivery_profile.py` was edited. The original r2
wrapper bytes are preserved separately in `.local/engines/r2-wrapper.py` at
SHA256 `985d271c6f01e93faf2989d1d0bdf5f7f59243d06a0a129913115e5462ee81fe`.
The plan and every r2 receipt retain their original hashes.

The authorised tiny probe completed exit **0** at **2026-10-05 18:24:23 UTC**.
All **29 checks** passed. It exercised real `open('nul', 'r+b')` and
`open('nul', 'wb')` under the installed audit guard without denials. Simulated
ordinary/alias outside writes, null-named mutations, cross-boundary rename,
shell/Python/test-origin Git children, remote sockets and private/parent reads
were rejected. AST comparison confirms only the guard's audit method changed.
No product, test, dependency engine, helper or model module was imported; no
pytest or real engine execution occurred. Probe receipt:
`.local/engines/r3-null-probe/result.json`, SHA256
`1afbf1c98c7224804eaec0d93bde03d3c18b153c035a0e74af0aea12fb9b6d62`.
New ignored wrapper SHA256:
`f75cabe0a40ae78ffa4a093b3c97f85e72db0376e3dc6927e02318acd727b7f0`.

At **18:24:44 UTC**, no Python engine runner remained and the physical r2
slot was still released. Parent HEAD remained clean for tested inputs at
`f3160c596eb3132fc7599c08d5973c3f7ddd9acb`. The exact eight missing IDs equal
both r2's six failed/two skipped outcomes and the existing literal
`r1-not-passed` selection. All seven raw r1 passes and four historical IDs
remain excluded. Future roots `.local/engines/r3` and `C:/rn-ef3-1005` are
absent. Prepared arguments, exact IDs, hashes, classification and release
observation are in `.local/engines/r3-readiness.json`. No real r3 run is
authorised or started; the explicit parent slot is still required.

Prepared child command only:

```powershell
$RenulusR3Arguments = @(
  '-I', '-B',
  'C:/rn-finalise-20261005/lanes/audit/.local/engines/run-engine-gap.py',
  '--expect-commit', 'f3160c596eb3132fc7599c08d5973c3f7ddd9acb',
  '--parent-serial-slot', '<explicit-r3-slot>',
  '--selection', 'r1-not-passed',
  '--scratch', 'C:/rn-finalise-20261005/lanes/audit/.local/engines/r3',
  '--execution-root', 'C:/rn-ef3-1005'
)
& 'C:/Users/karol/Documents/t3-workspaces/Renulus-wt-integration/.venv/Scripts/python.exe' @RenulusR3Arguments
```

When a slot is explicitly released, use the same one-shot durable supervision
as r2 for process identity, terminal log and actual exit receipt. The wrapper
still requires fresh roots, exact source/freeze, clean tested inputs, matching
prior receipts, package/manifest provenance, the dynamic current-bank source
prerequisite and the integrated adopted-module callable before engines. Strict
guarding remains active through tests and read-only recorder finalization.

## Accepted r3 terminal and physical slot release

The parent explicitly released `engine-r3-f3160c59-20261005`. A one-shot
supervisor launched at **2026-10-05 18:32:36.563150 UTC**, after verifying no
existing runner, fresh `.local/engines/r3` and `C:/rn-ef3-1005` roots, exact
wrapper/plan hashes and immutable r1/r2 receipts. Its recorded child arguments
select only the eight original nonpassed IDs. Actual runner **44348**, launcher
**35528** and supervisor **31568** have durable Windows creation identities
in `r3-process-windows.json`; observer session is **26737**.

Pytest completed with **8 passed, 0 failed, 0 skipped, 0 errors**, eight
warnings and **324.60 seconds** in its terminal summary; JUnit records
**324.604 seconds**. All eight inventory/outcome/JUnit IDs and **24** complete
setup/call/teardown events match. Both delivery variants, native-stream,
PDF/PNG attachment flows, byte capability, DocumentStream no-write and
Windows helper/store checks passed. No previous successful ID was repeated.

Finalization at **18:38:21.308499 UTC** recorded exit **0**, `complete=true`,
`source_unchanged=true`, `accepted_stage_pass=true`, `unique_ids_match=true`,
`runner_error=null` and `guard_violations=[]`. HEAD, production, tests/runner
and source-object checks are all true; `unexpected_module_sources={}`.
The guard remained active through finalization. Minimum free disk was
**295,311,503,360 bytes**, above the 12 GiB reserve.

Physical terminal was **18:38:25.115622 UTC**, actual observer/supervisor
exit **0**, elapsed **348.552 seconds** including launch/finalization. All
three owned processes were observed absent; the engine slot was released
immediately to the parent. The durable physical absence observation at
**18:39:10 UTC** is `r3-slot-release.json`. No termination or automatic retry
occurred. Terminal log and actual exit receipt were fsynced by the supervisor.

Post-terminal reconciliation at **18:40:55 UTC** verified source objects,
module paths, exact IDs/phases, terminal hashes and all immutable r1/r2 bytes.
Parent HEAD still matched the freeze. R1's empty result and both failed
batches remain original and nonaccepted. The 19-ID reconciliation is the
disjoint evidence partition 4/7/8, not a claim of one accepted 19-case run.
No native application, installer, compression or live-provider assertion is
added by this lane.

| Terminal receipt | SHA256 |
| --- | --- |
| `r3/result.json` | `329ee5ac3cd0534c90023088d216e072a9164e7e64e64b7896558087afb15f8b` |
| `r3/results.xml` | `719942c681bef1c0ad289b356d5f1481a7120a57be4feea26ecbef663c2384a2` |
| `r3-terminal.log` | `8ace26c94ba0429a015b81ec02d11e10c6cc969ffbdd7fdeca95f55bc9f28b4c` |
| `r3-exit.json` | `ead12bde97e2a198db5101e141581b920a2ea3e8fcb2a0b2ea0dfd58747b1467` |
| `r3-reconciliation.json` | `633c42cc6c960d99336e54afc8ead54227bdca9e737649750949dddbd60a10e4` |

Full identity, JUnit, phase, source, guard, history and receipt-hash evidence
is `C:/rn-finalise-20261005/lanes/audit/.local/engines/r3-reconciliation.json`.
Only this report is tracked; ignored wrapper, plan snapshots and receipts
remain local.

Final handoff: the original **19 excluded IDs** have disjoint evidence from
**4 historical transfers, 7 verified raw r1 passes and 8 accepted r3 passes**.
Successful IDs were not repeated; the failed r1/r2 batches remain immutable
and nonaccepted. This reconciliation does not inflate a full-sweep count.

The parent subsequently reported its independent physical release receipt,
`.local/finalise-engine-r3-parent-release.json`, and the start of installer-only
compression. After the successful finalizer, it reported integration/push of
reviewed reports and packaging-copier policy as `3df2d9b3`, with actual app,
runtime, content, helpers and manifests byte-identical to frozen `f316`.
That is parent-provided post-run provenance. R3 retains its original full
`f3160c596eb3132fc7599c08d5973c3f7ddd9acb` terminal source checks and
`accepted_stage_pass=true`; later main HEAD changes cannot retroactively alter
the accepted receipt. No main read or further engine execution was performed
for this closing note. The engine lane is finished and its slot remains released.
