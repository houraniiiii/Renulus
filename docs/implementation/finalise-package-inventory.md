# Backend package inventory correction — October 5, 2026

The pinned builder drops both inventoried `.gitkeep` placeholders during its
directory copy. Backend `extraResources` now adds direct file mappings for
`.gitkeep` paths already recorded in the verified backend inventory. The actual
pinned matcher/copier passes the tiny synthetic regression.

Owned worktree: `C:/rn-finalise-20261005/lanes/packaging-inventory`. Branch:
`codex/finalise-packaging-inventory`. Product/source baseline:
`f3160c596eb3132fc7599c08d5973c3f7ddd9acb`. Read AGENTS, README, project brief,
workspace, decisions, packaging handoff and current continuation before editing.

## Concrete mismatch

The parent metadata-only receipt
`C:/Renulus-native-delivery/desktop-20261005/repo/.local/failed-package-file-delta.json`,
dated `2026-10-05T18:03:18.431169+00:00`, records 39,251 expected versus 39,249
actual files, no extra files and no size differences. Embedded inventory equals
staged inventory. Its only missing paths are:

| Public inventoried path | Bytes | Recorded SHA256 |
| --- | ---: | --- |
| `dependencies/rapidocr/models/.gitkeep` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `upstream/hermes/contributors/emails/.gitkeep` | 70 | `5cb2fe7af5e92ff923262060d477da6709e5843e7103a645fab73c6be8d20c20` |

These are existing receipt values, not a new full payload rehash or acceptance.
The parent confirms the real NSIS installer and win-unpacked completed; final
backend comparison failed. Failed executable and receipts remain preserved.

## Actual library evidence and minimal correction

Read the public pinned tree at
`C:/Renulus-native-delivery/desktop-20261005/environment/node-f3160c59/node_modules`.
Its electron-builder, app-builder-lib and builder-util manifests all identify
version `27.0.0-alpha.6` and MIT. No junction or dependency changes were needed.

- `builder-util/dist/fs.js:58`: `walk()` skips `.gitkeep` and `.DS_Store` before
  calling the supplied filter. Adding a positive glob cannot reverse that skip.
- `app-builder-lib/dist/fileMatcher.js:397`: `getFileMatchers()` converts the
  actual `extraResources` FileSet entries into matchers.
- `app-builder-lib/dist/fileMatcher.js:439`: `copyFiles()` uses the direct-file
  branch at line 449 to copy a file without invoking `copyDir()`/`walk()`.
- `app-builder-lib/dist/platformPackager.js:303`: product packaging invokes that
  same `copyFiles()` function for its extra resource matchers.

Hashes of the two inspected small library source files:

| Library file | SHA256 |
| --- | --- |
| `app-builder-lib/dist/fileMatcher.js` | `99ca159e7b4538c1405482ff45a6cc883cf32de5f12910fda42a78ef611ac5a1` |
| `builder-util/dist/fs.js` | `37f629c8073ebfe53de130a16468580936ef717e7ddab63bf5c015cdaaea7778` |

The config retains the existing backend directory mapping and appends explicit
source-file/destination-file mappings for inventory entries whose basename is
exactly `.gitkeep`. Paths must be relative slash-separated descendants; absolute,
drive, backslash, empty, dot and parent segments are refused before copying.
Unlisted placeholders receive no exception. The mapping uses existing bytes;
it neither manufactures placeholders nor edits the inventory. OS-file skips,
application whitelist, licence resources and public staging boundaries remain
unchanged. The staged and packaged full-byte checks in `stage-delivery.py:175`
and `stage-delivery.py:290` remain unchanged and mandatory.

## Small actual-copier proof

Run from this owned worktree with the existing public dependencies:

```powershell
$env:RENULUS_PACKAGING_POLICY_NODE_MODULES = 'C:/Renulus-native-delivery/desktop-20261005/environment/node-f3160c59/node_modules'
node --test apps/desktop/scripts/test-backend-extra-resources-policy.mjs
```

The script imports the actual pinned `getFileMatchers()` and `copyFiles()` and
loads the production config using a fresh synthetic bundle. It copies only its
own tiny backend fixture. Its invented 70-byte placeholder contains no original
repository correspondence. The eight intended fixture/manifest files total
**1,162 bytes**; a ninth unlisted synthetic placeholder is an exclusion control.

- Existing directory mapping reproduces exactly two missing placeholders. Even
  an explicit `.gitkeep` glob accepts them in the matcher but loses them in copy.
- Actual production config retains every intended file, including the zero-byte
  and 70-byte placeholders, with complete name/size/SHA256 equality. The unlisted
  placeholder stays excluded and its source bytes remain unchanged.
- Four invalid inventory paths are refused before copy.

Final result: **exit 0, 4 tests passed, 0 failed/skipped** (three subtests plus the
parent test), **2,168.1491 ms** total. Both owned JS files passed `node --check`;
`git diff --check` passed. All unique synthetic fixture directories were removed.
The first two development runs exposed a Windows-backslash refusal defect in
the new guard; the final guard uses `path.win32.sep` and all refusals pass.

## Owned files and parent handoff

Only these tracked paths are changed or added:

- `apps/desktop/electron-builder.config.cjs`
- `apps/desktop/scripts/test-backend-extra-resources-policy.mjs`
- `docs/implementation/finalise-package-inventory.md`

This is copy-policy proof, not installed-product acceptance or a full inventory
pass. Central source remains untouched under the engine lease. Parent owns the
actual pinned `--prepackaged` salvage and installer-only factory pass, including
any restoration from admitted public payload bytes and the existing final byte
comparison. No app rebuild, large copy/hash sweep, NSIS/compression, runtime
launch, installer/provider use, private-state access, download or GitHub action
occurred in this lane.
