# Backend finalisation implementation record - 27/28 October 2026

Authority: the owner's October 27 instruction to implement `docs/planning/BACKEND_FINALISATION_SPEC.md`, preserving the existing interface, records, selected engines,
subscriptions and models. Scope of this record: **BF00-BF07**. **BF08 (profile-wide authority handoff, matching bundle, populated migration, Electron/packaged
acceptance) was not requested and is not done.** No production cutover occurred: Python remains the canonical writer/dispatch authority of every owner profile and the
ordinary launcher; the TypeScript target runs only on isolated synthetic profiles. No owner profile, credential, paid provider or account was used.

Branch `codex/backend-finalisation` (from `codex/design-c-integration` at `1a40d9fc`), tracking PR [#30](https://github.com/houraniiiii/Renulus/pull/30), 54 commits after the
checkpoint `ac2d05f8`. This is **implementation evidence, not an acceptance declaration**: every item under "Open" below keeps its H/BF obligation open.

## Final verification (independent full run on the clean tree at `843f2f34`, nothing else running)

| Suite | Result |
| --- | --- |
| `tsc --noEmit`, `packages/backend` and `packages/harness` | clean |
| `packages/backend` build (`scripts/build.mjs`) + `node --test test/*.test.mjs` | 175 tests: **174 pass, 0 fail, 1 skipped** (real Node Library/Lance bridge variant, skipped by design) |
| `packages/harness` `test/*.test.mjs` | **162 / 162** |
| `packages/harness` child-authority/child-contract/domain-tools/native-context `.ts` | **44 / 44** |
| Python `tests/workers`, `tests/runtime/test_domain_process.py`, `tests/backup/test_restore_frontier.py` | **216 passed** |
| Existing `tests/backup` + `tests/integration/test_design_c_migration.py` | 26 pre-existing failures, **identical at baseline `1a40d9fc`**, none introduced (`BACKUP_GATE_CLASSIFICATION_20261028.md`) |

Test environment (all tests are synthetic): Node 26.4.0 at `C:/Renulus/scratch/ocf/tools/node-v26.4.0-win-x64`; Python `C:/Renulus/dev/python/Scripts/python.exe` via
`RENULUS_BACKEND_TEST_PYTHON`; `TEMP` on a drive with > 12 GiB free (the native reserve step enforces a 12 GiB floor; `C:` has about 11.5 GiB); `RENULUS_WORKER_TEST_HELPERS` and
`RENULUS_RECOVERY_HELPERS` = `C:/Renulus/dev/helper-assets`; `RENULUS_CHILD_AUTHORITY_TEST_ROOT`, `RENULUS_CHILD_CONTRACT_TEST_ROOT`, `RENULUS_LIBRARY_TEST_ROOT` = fresh scratch dirs;
`HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`. Run `node scripts/build.mjs` in `packages/backend` before the backend tests (`dist/` is git-ignored; `target-facade` runs the compiled bundle).
A real Windows libuv assertion occasionally aborts the child in `facade.test.mjs` 'real Python death blocks every facade route...' under heavy load (passes alone): known flaky.

## What is implemented (TS target on synthetic profiles; Python engines kept)

| Wave | Implemented and proven |
| --- | --- |
| BF00 | Node/Effect host, single `node:sqlite` writer thread, typed Python worker channel, schema/export/receipt/backup parity; owner/selector validation; shutdown settlement. Four migrations renumbered `007-evidence-reservations`, `008-legacy-history-import`, `009-temporary-save-intents`, `010-mcp-connections` (after `006-capability-effects`). |
| BF01 | Immutable plugin add/edit/disable/remove with dependency refusal, failed-candidate fallback, restart omission, held-on-timeout; dispatch with positive role budgets; protected credential broker (OAuth cancel bug fixed); grantable capabilities derived from the tool registry, per-capability revocation, tool-return fence on every learning tool; the registry seam `plugins/registry.ts`. |
| BF02 | Library upload/delete compatibility (bytes import, digest, reserve-before-publish), 12-format native journey, Notes propose-save-query-reopen, native-message Finder + `renulus_find`, one-time legacy history import (receipt, tombstone, resume), project/Archive closure. |
| BF03 | Native Adapters `skill`, `question`, `subagent`, models, rename; evidence tools with budgets/reservations and canonical restrictions; mediated worker HTTP; Code Mode `fetch` patch (hash-verified, provenance in `upstream/opencode/PATCHES.md`); credential-free MCP bridge with persistent connections and per-connection revoke; developer plugin (files/shell/worktree/browser ports) shipped Off, with direct approval/renewal commands. |
| BF04 | Temporary Save/disconnect lifecycle (both orderings, replay after restart, orphan reconciliation, scrub of freed pages), saved attachments/images, context profiles (128 000/256 000), connected compaction through the `compaction` dispatch purpose, `renulus_context_refs`/`renulus_history_range`, memory echo suppression. |
| BF05 | Study/Test fences, help exposure, deadlines, fictional receipt replay, import refinement, 5/10/20 generation with interrupted-job settlement, reviewed-pack validate/install/activate/withdraw, `renulus_study_help`/`renulus_practice_propose`; all producers run through native dispatch with a synthetic route/counter. |
| BF06 | Home/plan/progress/nightly/Updates Python-shape parity (17 routes compared against Python), Updates source/publication/literature checks through the broker, digest cannot confer review authority, `renulus_plan_propose`/`renulus_updates_read`. |
| BF07 | Read-only restore preview, additive restore preserving current data, stale-candidate refusal, incoming run claims terminalised, deletion-frontier/native-mapping refusals (Python), production `native.measure`/`native.retire`, rollback, selection command, original rebasing, measured growth table (synthetic, uncalibrated: `BACKEND_STORAGE_MEASUREMENTS_20261027.md`). |

## Independent review and diagnostic record

- **R1 (BF01-BF03, GPT 6.1 Sol xhigh)**: 7 findings; 6 accepted and fixed (MCP header echo, source/tool return fencing, evidence restrictions, Permission override collision,
  per-connection MCP revoke, browser patch provenance); 1 rejected: Library DELETE without `expected_revision_id` deliberately matches the unchanged UI/Python contract (document-level delete).
- **R2 (BF04-BF07)**: 9 findings, each reproduced or traced before fixing and all fixed (stale-candidate selection, temporary disconnect ordering, export fence during an active Test,
  Updates checks fetching tracked content, live run claims on restore, connected compaction wiring, legacy-import resume, Save replay after restart, interrupted generation settlement).
  The export/backup fence follows the Design C planning default; the plugin-inspection snapshot is exempt.
- **S18 (Opus 5.5 high)**: audited every native layer override; proved the Job/SessionExecution/PluginHooks/Permission compositions after the S0/S7/S12 fixes; added
  `override-composition.test.mjs` (fails on each historical regression).
- Orchestrator's own full runs found regressions that lane reports missed (`learning-target` 6/12, `memory-restore-barrier`, `target-facade`, `storage` fence, dispatch concurrency
  lockout after crashes); all fixed at the source.
- Provider notes: Kimi K3.1 returned HTTP 402 (insufficient credits) and was not used; no credits were purchased and no application model/route was changed.

## Open required work and known limits (not done, not hidden)

1. **BF08**: authority handoff, matching bundle/packaging, populated production migration, Electron launch, `verifyBinaries` in `main.ts`, selecting MCP and the developer plugin in the application entry (both are opt-in options that need the patched native build).
2. **Live account qualification (L)**: real Codex/OpenCode Go route, tokenizer/counter, tool and image capability, 128K/256K limits; the synthetic route proves wiring only.
3. **Physical Windows acceptance (W)**: dialogs/auth/original Open, no-follow/long-path proof for original publication, hidden-Electron browser attach provider for the developer browser (only the explicit
   "missing attachment" report is proven), developer settings loading (activation is not granted).
4. **Storage reclamation**: `native.retire` is fail-closed debt recording, not disk reclamation (needs a cross-stream fence); sustained bounded storage is not claimed. The 100 GB budget is uncalibrated.
   The recovery source marker hashes whole stores and can be slow on large profiles.
5. **MCP**: browser OAuth login (PKCE + loopback) is an open external handoff; tokens are supplied through the credential handoff command.
6. **Gaps accepted for now**: nightly retry/backoff (300 s/1800 s) not ported; `assessment.fictional.receipt` replays by idempotency key only (no source digest, by the privacy rule); domain-breadth journeys
   (electrolytes/acid-base, AKI, CKD, glomerular, transplant) were not run per domain, fixtures are synthetic; the Python additive restore refuses native links (`recovery_native_mapping_required`), the TS target owns the native merge.
7. **Existing backup gate** stays red from 26 failures that exist unchanged at the starting commit.
