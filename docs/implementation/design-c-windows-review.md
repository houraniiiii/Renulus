# Design C Windows delivery preparation review

2026-10-10. Report-only DC21 preparation; **DC21 remains open**.
Audited source: `434dc41a578279cf3639b002788cf84f57c430bb`, read with
`git show` from `C:/Renulus/dev/worktrees/dc02-contracts`. No merge was needed.
The parent is still integrating later feature commits; this is not a release
freeze or an audit of those later bytes.

Only this report was written. No build, packaging, installer, bootstrap, helper
proof, profile preparation, launcher, native app, provider or account operation
was executed. No private delivery pointer, owner profile or acquired collection
was inspected. Source reads were limited to the DC21 spec, delivery guidance and
the named delivery/bootstrap/reader/profile paths below. Tracked historical
receipts are evidence at their recorded revision, not fresh observations.

## Decision and existing capability

[DC21](../planning/DESIGN_C_IMPLEMENTATION_SPEC.md#dc21--package-validate-and-make-c-the-default)
depends on DC20 acceptance, then matching unsigned current-PC delivery, preserved
data/connections, bundled readers/helpers and explicit launcher promotion with
rollback. Current-PC unsigned delivery is the chosen scope; signing, a separate
clean machine and physical issue #21 observations are not implied.

The existing manufacture pipeline is reusable. It accepts a full Git commit,
builds a committed renderer/native snapshot, refreshes an admitted public CPython
payload, checks helper inventories, produces NSIS output and hashes the package.
The current installed verifier has useful artifact checks but obsolete Flow
journeys. Its success would not cover the new C readers, projects, whole attempts
or schema-1 upgrade by itself.

[RUNNING.md](RUNNING.md) records the supported `f1c49444` installation at
`C:/Renulus/app`, with the normal profile at `C:/Renulus/data/learning`.
That is a documented baseline, not a fresh check of either directory. The
[C App entry](../../apps/desktop/src/shell/App.tsx) already mounts
`desktop-shell design-c-shell` directly. No Flow/C switch was found in the
inspected main/App/ModuleOutlet/Vite entry paths. Remaining legacy adapters are
not automatically obsolete: remove them only after their replacement and deep
links pass DC20.

## Concrete blockers and missing evidence

| ID | Finding at the audited revision | Required action and acceptance |
| --- | --- | --- |
| W1 | Delivery paths predate the October 8 relocation. `delivery_paths.py:69` admits public inputs only below the historical C/E delivery roots or desktop `test-results`, with reparse rejection. `restage-delivery.ps1:8` defaults to the old repository and `:107` hardcodes an old integration Python path. Current documented `C:/Renulus/dev/node_modules` and `dev/helper-assets` are not directly admitted. | Parent names verified public payload, Python archive, wheels/environment, Electron/npm tree and NSIS/7-Zip cache. Either explicitly stage verified public bytes into an already admitted fresh location or make a narrow, tested path-contract change. Do not follow old compatibility junctions, broaden to arbitrary C:, or bypass the guards. Actual existence/bytes of old defaults were not checked here. |
| W2 | `native-evidence-directory.mjs:8` excludes `C:/Renulus/scratch/design-c/`; `verify-installed-product.mjs:60` specifically requires desktop `test-results`. `test-installer.ps1:45` puts evidence under the historic delivery root. | Adapt the parent-owned acceptance path before executing under the current synthetic-state requirement. Keep runtime profiles, cache, logs and helper working state under an exact owned Design C scratch root. Artifact manufacture may have a separately reserved release root. Arbitrary profiles/reparse paths remain denied. |
| W3 | `native-evidence.mjs:119` clicks Learn/Library/Cases/Test/Memory/Updates/Connections/Today as primary links. `verify-installed-product.mjs:350`, `:376` and `:569` drive old reviewed quiz/Today/temporary Case controls. `wait-for-flow-window.mjs:20` requires a visible native window and visible navigation. | A bounded C installed journey must use the actual C controls and support collapsed navigation. Reuse identity, inventory, OS-only PATH and shutdown checks. Keep hidden controller and separately authorized visible/native proofs distinct. Do not relabel the Flow receipt or run these scripts unchanged as DC21 acceptance. |
| W4 | The installed verifier's gate list (`:25`) covers legacy text/PDF/image/Office flows, not every C reader or whole-attempt/project transition. The available historical package receipts are for Flow revisions. | Produce a final-revision installed matrix for all eight C categories, saved/default and temporary retention, project scope, Notes/Goals, Study/Test, policy, jobs, recovery and normal reopen. Existing source proofs can qualify components but cannot establish installed parity. |
| W5 | `prepare_delivery_profile.py:29` intentionally whitelists Library/content only; `:416` rejects learner/config records in its fresh target. It omits chat/project/attempt state and credentials by design. | Never use this utility as a preserved-user-profile upgrade or rollback recipe. Use a complete synthetic legacy profile for in-place upgrade and actual supported JSON/ZIP1/ZIP2 recovery paths. Preserve a pre-upgrade snapshot; test rollback against that snapshot, not a migrated database. No expansion of this content-only tool is proposed. |
| W6 | `prove_offline_helpers.py:93` hardcodes `verified_on` to 2026-10-04. Its retained JSON is a development CPU proof, not a C installed receipt. Bootstrap copies verified assets; readiness/import checks do not perform OCR/retrieval. | Retain that historical proof. Add actual UTC/start/end, final source, executable/ASAR/runtime/helper hashes and isolated interpreter identity to the new release receipt. Prove real packaged native/scanned PDF extraction, CPU embedding/chunk retrieval and derived rebuild without downloads. A fresh invocation of the existing helper script must not be reported with its hardcoded date as a current installed proof. |
| W7 | `start-renulus.ps1:58` CheckOnly checks executable selection/existence, not artifact hashes, migration success or account availability. `resolveProfile` falls back to `%LOCALAPPDATA%/Renulus` when a packaged executable receives no explicit profile. | Parent promotion must pin executable and explicit intended profile, compare approved hashes first, retain the previous pointer, then separately verify actual startup/reopen. CheckOnly is a selector check only. All preparation uses synthetic state; owner-profile cutover stays a later parent-controlled action. |

These are identified source gaps or missing matching evidence, not observations
of a failed current installer. No package was attempted in this lane.

## Manufacture and artifact contract

Read [stage-delivery.py](../../apps/desktop/scripts/stage-delivery.py), especially
lines 34–164 and 237–300, together with
[electron-builder.config.cjs](../../apps/desktop/electron-builder.config.cjs).
`npm run pack:win` builds a directory (`--dir`); it is not the complete NSIS
delivery recipe. `stage-delivery.py --package installer` requires an explicit
pinned public tool cache and uses `--publish never`.

The byte comparison from `f1c49444` to this audit revision found **no changes**
in `pyproject.toml`, `uv.lock`, desktop `package.json`/`package-lock.json`, or
`packaging/runtime/helper-assets.json`. This supports evaluating source-only
refresh of an existing verified payload, not assuming any local payload is
valid. The final freeze must repeat the check against the payload's own
`source_revision`; changed locks require fresh selected wheels and proof.

The release record must retain:

| Artifact | Required identity/evidence |
| --- | --- |
| Source and tooling | Full final Git SHA; manifest/lock hashes; hash of each executed staging/acceptance driver; no unstaged source substitution. |
| `resources/backend/bundle.json` | Version 1, `embedded-cpython-windows-v1`, exact source revision, CPython 3.14.4/executable hash, bootstrap path, helper contract/copy hashes, dependency list and any explicit source-patch provenance. |
| `resources/backend/inventory.json` | Every listed relative path, size and SHA-256 matches; source blobs match the frozen Git snapshot, including all additive SQL migrations and new modules. Preserve `.gitkeep` direct mappings used by the current builder. |
| Renderer/native inside `app.asar` | `dist/renderer-provenance.json` and `dist-electron/native-provenance.json` name the same final SHA as backend; Electron 44.5.1 matches; main/preload bundle/source hashes match. `backend_adoption.source_sha256 == adopted_sha256`; no uncommitted packaging-lane patch. |
| Distribution | `delivery-provenance.json`, one installer with size/hash, unpacked and installed EXE/ASAR hashes, packaged backend inventory hash, installer exit/target/signature status. `native_launch: pending actual relocated native journey` is not acceptance. |
| Assets/notices | Renderer font/assets are local; all reader backend dependencies/DLLs are in inventory; Renulus/Hermes/content/CPython/Electron/Chromium and dependency/model notices are present in the delivered resources. |
| Acceptance | Per-gate outcome, exact source/artifact/profile scope, real UTC times, screenshots where relevant, normal shutdown ownership and preserved failures. Hidden/native/live/physical results retain separate qualification. |

[verify-installed-product.mjs:90](../../apps/desktop/scripts/verify-installed-product.mjs)
already compares manufacture/install/current hashes; lines 141–202 also verify
frozen drivers, installed source blobs and native provenance. Reuse these checks
instead of trusting the same version label or a successful build log.

The builder uses a revision-specific NSIS app ID, per-user/no-elevation install,
no auto-launch, no automatic shortcuts, `deleteAppDataOnUninstall: false`, no
signing and no publishing. Output names still contain “Renulus Development”.
That is a naming decision for the parent, not a signature or delivery failure;
record the exact actual name rather than inventing `Renulus.exe` in receipts.

## Bundled runtime, readers and offline evidence

[backend.ts:30](../../apps/desktop/electron/backend.ts) launches the packaged
`resources/backend/python/python.exe -I -B -X utf8 bootstrap.py` with explicit
profile/source root and an authenticated owned loopback backend. Development
attachment/runtime overrides do not select the packaged interpreter.
[profile.ts:17](../../apps/desktop/electron/profile.ts) allowlists child
environment variables. The bootstrap validates the reviewed/acquired helper
manifests before [copy_assets](../../scripts/copy_helper_assets.py) verifies
individual sizes/hashes, atomically replaces `.copying` files and writes the
manifest last. Actual first-start and warm-reopen evidence is still required.

The [helper contract](../../packaging/runtime/helper-assets.json) has 19 files,
483,597,181 bytes: embedding 8/67,412,843; Docling 8/384,434,829; OCR
3/31,749,509. The existing [offline proof](../../packaging/runtime/offline-helper-proof.json)
records October 4 Windows CPU embedding (384 dimensions), native/scanned PDF,
HybridChunker/page locators, LanceDB and zero observed network connection
attempts. It does not prove current installed C readers or Mem0 recovery.

The C [reader backend](../../runtime/renulus/knowledge/reader.py) dispatches
PDF/DOCX/XLSX/images and text categories. Its
[binary implementation](../../runtime/renulus/knowledge/reader_binary.py) uses
Pillow, pypdfium2/PDFium, python-docx and openpyxl; its
[text implementation](../../runtime/renulus/knowledge/reader_text.py) uses
markdown-it-py, defusedxml, and standard CSV/HTML parsing. The
[React reader](../../apps/desktop/src/modules/reader/Reader.tsx) requests local
reader payloads/assets; do not assume an Office installation or browser plugin
provides these capabilities. Source Sans 3 is imported locally in
[main.tsx](../../apps/desktop/src/main.tsx). Confirm their actual packaged bytes
and behavior with an OS-only child PATH, not the contributor dependency junction.

Required installed examples: PDF physical page, DOCX text/table/image, CSV rows,
XLSX sheet/cell, Markdown, inert HTML, inert XML, and PNG/JPEG/TIFF frame.
For each retain original hash and canonical reference, rendered pixels/text,
selection locator where supported, passage-to-draft without auto-send, and
close/reopen. Include corrupt/missing original, restricted/preview-only,
failed-extraction and active-Test refusal. Eight file categories do not imply
every file can be extracted or used for model input. New reader dependencies
must match the frozen lock/inventory and notices before acceptance.

The [desktop notices](../../apps/desktop/THIRD_PARTY_NOTICES.md) and
[helper terms](../../packaging/runtime/helper-notices.md) already identify the
required provenance, including the ANTLR supplement. Check actual included
licence resources at the final freeze; the older notice supplement is not proof
that an arbitrary newly manufactured bundle includes it.

## Parent execution recipe — commands, not actions taken

The following records the existing command interfaces. Parent supplies the final
freeze and exact verified inputs; placeholder paths are intentionally not
guessed. Resolve W1/W2 and accept the DC20 freeze first. No acquisition, package,
installation or runtime command below was run for this review.

Read-only source checks, with `$dcRevision` later replaced by the final freeze:

```powershell
$dcRepo = 'C:/Renulus/dev/repo'
$dcRevision = '434dc41a578279cf3639b002788cf84f57c430bb' # audit only; not a release freeze
git -C $dcRepo rev-parse --show-toplevel
git -C $dcRepo status --short
git -C $dcRepo show --no-patch --format=fuller $dcRevision
git -C $dcRepo diff --name-only f1c49444 $dcRevision -- pyproject.toml uv.lock apps/desktop/package.json apps/desktop/package-lock.json packaging/runtime/helper-assets.json
```

Use the Python driver directly to avoid the wrapper's hardcoded old interpreter.
`$dcPayload`, `$dcHelpers`, `$dcPythonArchive`, `$dcModules`, `$dcBuildCache`
are explicit parent-verified **public** inputs admitted by `delivery_paths.py`;
none is an installed app profile. `$dcDeliveryRoot` is a fresh parent-reserved
allowed release root; `$dcTag = $dcRevision.Substring(0, 8)`.

```powershell
$dcStage = Join-Path $dcRepo 'apps/desktop/scripts/stage-delivery.py'
$dcStageArgs = @(
  '--source', $dcRepo, '--revision', $dcRevision,
  '--delivery-root', $dcDeliveryRoot,
  '--payload', $dcPayload,
  '--snapshot', (Join-Path $dcDeliveryRoot ('source-' + $dcTag)),
  '--output', (Join-Path $dcDeliveryRoot ('matching-' + $dcTag)),
  '--environment', 'C:/Renulus/dev/python', '--helpers', $dcHelpers,
  '--python-archive', $dcPythonArchive, '--node-modules', $dcModules,
  '--build-cache', $dcBuildCache, '--package', 'installer'
)
& 'C:/Renulus/dev/python/Scripts/python.exe' -B $dcStage @dcStageArgs --plan-only
```

`--plan-only` validates source/paths/contracts/input presence and prints the
commands; it does not manufacture or verify the entire existing payload byte
inventory. Actual execution verifies the inventory before copying. After the
parent accepts the plan/freeze and reserves the serial build slot, the exact
manufacture command is the same invocation **without `--plan-only`**. The
PowerShell `restage-delivery.ps1 -Phase Plan` wrapper itself creates logs/temp
directories, so do not call it a no-write audit.

After W2 is fixed, the existing installation-only interface is:

```powershell
pwsh.exe -NoProfile -File (Join-Path $dcRepo 'apps/desktop/scripts/test-installer.ps1') `
  -Installer $dcInstaller -Target $dcFreshInstall -SourceRevision $dcRevision `
  -DeliveryRoot $dcDeliveryRoot -InstallOnly
```

`$dcInstaller` is the single hashed installer in delivery provenance;
`$dcFreshInstall` is an absent, admitted target. This runs NSIS, not the app;
it requires its own parent action. `-InstallOnly` is not a lifecycle proof.
Do not omit it and accidentally invoke the old native journey. Preserve all
previous installations/receipts.

The existing installed verifier's read-only interface is
`node apps/desktop/scripts/verify-installed-product.mjs --plan`.
Its `--run` requires `RENULUS_NATIVE_SLOT`, `RENULUS_EXPECT_SOURCE_REVISION`,
`RENULUS_INSTALLED_PROOF=1`, `RENULUS_PACKAGED_EXECUTABLE`,
`RENULUS_DELIVERY_PROVENANCE`, and `RENULUS_INSTALLER_EVIDENCE`; it rejects
profile/backend/token/development overrides. **Do not run it unchanged** under
this lease: W2/W3 and its native Save-dialog helper conflict with the required
hidden synthetic preparation boundary. The new C journey should reuse its
artifact validation and child environment, then use the app-scoped controller
as documented in [APP_CONTROL.md](APP_CONTROL.md).

The existing real helper-proof command interface, for a separately reserved
synthetic offline check, is:

```powershell
& $dcEmbeddedPython -I -B -X utf8 $dcHelperProofScript `
  --profile 'C:/Renulus/scratch/design-c/contracts/dc21-offline' `
  --output 'C:/Renulus/scratch/design-c/contracts/dc21-offline.json'
```

Here both executable and proof script must be inside the matching installed
backend, helper assets must already be provisioned through its bootstrap, and
the parent must establish an isolated child environment/OS-only PATH and fix or
externally qualify W6's receipt date. This command is a CPU proof, not an app
journey or a live provider check. Preserve a failed run and choose a fresh owned
profile for a new run; do not overwrite evidence to manufacture success.

## Upgrade, recovery, rollback and default gates

1. **Freeze:** close DC20 material findings with evidence against the final
   commit, including the later Notes/Case/Study work absent from this audit.
   Pin executed drivers and delivery manifests. Preserve the currently accepted
   release and its provenance; no launcher mutation during preparation.
2. **Synthetic old profile:** prepare a complete preserved schema-1 fixture,
   plus hashes/inventory before opening it with C. Include original Learn/Case
   IDs/messages, saved Case/Library originals, legacy assessment sessions and
   attempts, study preferences, memory and known deletions. Test in-place
   additive migration, restart/interruption and no duplication. Preserve the
   source fixture unchanged; do not obtain it by copying the owner profile.
3. **Current C state and recovery:** exercise saved/draft/archive/project/note
   links, immutable test versions and independent attempt/report pins, active
   timed/untimed attempts, job interruption, attachments and cleanup. Check
   supported JSON/schema-1/ZIP1/ZIP2 adapters, newer deletions, unavailable live
   references without erased immutable pins, originals and actual derived-index
   readiness. Temporary sentinels/IDs and raw fictionalisation inputs must be
   absent from database, files, exports, jobs and persisted UI preferences.
4. **Connections:** [ConnectionStore](../../runtime/renulus/runtime/protected.py)
   binds DPAPI entropy to the resolved profile path (lines 60–83). A data backup
   intentionally excludes credentials; moving a directory is not a connection
   migration. Synthetic disconnected tests do not prove a retained live account.
   Keep the eventual intended profile path stable; any owner-authorized move or
   account check needs the parent's separate scoped procedure. No credentials
   or provider calls are needed for this report/preparation.
5. **Installed acceptance:** compare source/package/install bytes; launch the
   installed binary with explicit synthetic profile, owned backend and OS-only
   PATH; verify cold helper provisioning, all reader categories, normal close,
   no remaining owned backend, and warm reopen with preserved state. Record
   hidden versus separately authorized native-dialog/live/physical scope.
6. **Rollback rehearsal:** retain the prior executable/pointer and a consistent
   pre-upgrade profile snapshot. Do not open a migrated C database with the old
   binary or assume the old app can restore schema-2 backups. Rehearse restoring
   the compatible synthetic snapshot before launching the old binary. Do not
   merge post-upgrade writes into the rollback snapshot automatically.
7. **Parent-only cutover:** once the matching release is accepted, preserve the
   old `.local/delivery.json` and owned shortcut metadata; select the exact new
   executable and explicit intended profile. The existing confirmation command
   is `powershell.exe -NoProfile -File scripts/start-renulus.ps1 -CheckOnly` from
   the canonical checkout. It does not run the app. Actual normal shortcut
   startup/reopen and source identity are a separate final check. Run
   `scripts/install-desktop-shortcut.ps1` only if its owned target needs repair;
   it writes the desktop shortcut and is not needed merely to change the
   delivery pointer. Update RUNNING/README/delivery status only from that evidence.

## Narrow follow-up proposal

No product-source fix was needed to produce this report. Following the parent's
review of the findings, the proposed implementation reservation is exactly
**these two existing files**:

- `apps/desktop/scripts/verify-installed-product.mjs`
- `apps/desktop/scripts/test-verify-installed-product.mjs`

Wait for the parent's exact-path acknowledgement before editing either file.
One release worker can update the isolated verifier after the parent freezes
the input/evidence-root contract. Preserve its artifact/receipt validators,
keep plan/import side-effect-free, add C gate definitions and an explicitly
hidden synthetic installed journey. Tests
should reject mismatched source/artifact receipts, owner/out-of-root profiles,
developer runtime attachment and incomplete gates; selectors must come from
observed C UI. This does not authorize those edits now.

Parent retains W1/W2 changes to shared path guards, staging/installer scripts,
launcher/default selection and any helper receipt correction. The separate
worker must not weaken frozen-source validation or duplicate a packaging
framework. Updating this existing driver is justified by W3/W4; after its connected
checks pass, installation, full migration and default promotion still require
their real receipts. This report closes no feature or delivery ticket.
