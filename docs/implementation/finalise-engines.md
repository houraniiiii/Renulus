# Finalise excluded engine evidence — October 5, 2026

**Preparation only; no new engine run or installed proof is accepted here.**
The b4 regression excluded 19 unique engine identities. Exactly four overlap
the recovered terminal 19-test CPU run; 15 remain without a matching execution
receipt. A guarded serial command is prepared, held for the parent's explicit
slot and final content/source freeze. The current-bank delivery prerequisite
is repaired at `b473ecb3`; the wrapper now recognises that source snapshot
comparison and the integrated runner's exact adopted Hermes Mem0 module.
Capacity completion/release does not grant this lane an engine execution slot.

This lane owns only this report and ignored local engine preparation/receipts.
The prior 64-row audit, commit `7f6328c8324f668716f6340f942a23470524f175`,
remains separate and untouched. No source/test edit, model load, pytest
collection, native app launch, provider request or public asset copy was
performed while preparing this inventory. The October 5 bounded recovery
authorises committing meaningful preparation evidence in this report. The
previous Volta attempt reported an unsupported model; per the recovery
instruction, no engine execution ran. This recovery also performs no engine,
helper, native, compression, provider or application-test execution.

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
The prepared default invocation selects this list literally, without `-k`,
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

## Current source comparison

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
adding test counts. The default prepared command retains all 15 missing IDs.

## Prepared actual invocation and guards

`scripts/run_backend_regression.py` accepts only application/capacity/harness
stages and denies unreserved inference. **Do not pass `--stage engines` to it.**
The ignored wrapper below reuses its frozen `OfflineGuard`, `ReceiptPlugin`,
preopened `ReceiptFiles`, environment isolation and terminal reconciliation
with `allow_engines=True` only after explicit execution inputs. Source and test
files remain under their existing owners. The wrapper has only been checked
statically; no invocation/collection has been performed.

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

Prepared PowerShell command, to be filled with the parent's granted full freeze
and slot reference and executed exactly once in the assigned serial slot:

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
before/after and loaded Renulus/helper paths. If relevant overlapping source
changes at the final freeze, re-audit the four transfers; the prepared
`--selection all19` can then execute exactly all 19 b4 identities in one serial
run instead. Prior/future attempts remain separate, including failed runs.

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

## Concrete remaining inputs and gates

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
Readiness is **prepared, waiting for the parent's final content/source freeze
and explicit serial engine slot**. No new execution or acceptance is claimed.
