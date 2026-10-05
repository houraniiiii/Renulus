# Finalise packaging machinery — October 5, 2026

**The scoped NSIS factory correction and C delivery planning checks pass. Product
manufacture, Install and Proof remain held for the parent's final exact freeze
and serial slot release.** This report establishes packaging machinery only.

Owned worktree: `C:/rn-finalise-20261005/lanes/packaging`, branch
`build/finalise-packaging`, baseline
`9d26f1eedf31cd488b9aab5837a105ee152d9efa`. Issue #12 remains open. The
relocated central source is `C:/Renulus-native-delivery/desktop-20261005/repo`.
The legacy E source junction is not a manufacture output or public reuse input.

## Concrete correction and reuse

The preserved freeze55 report at
`e4538591:docs/implementation/office-image-delivery.md` records Plan exit 0 and
Package exit 1 after 2,676.4224572 seconds. Windows resolved factory
`multiUser.nsh` to stock NSIS `MultiUser.nsh`, which failed with
`MULTIUSER_EXECUTIONLEVEL not set`. The failed E archive, ASAR, logs and
preservation receipt remain historical evidence; this lane did not modify or
reuse their application bytes.

`restage-nsis.py` verifies electron-builder/app-builder-lib 27.0.0-alpha.6,
their MIT identity, the exact seven factory root include names and 30 pinned
factory/code/schema files. It copies those seven root includes unchanged into
a fresh compile directory. A generated include selects that directory and
requires the factory `initMultiUser` macro. Original Node dependencies and
NSIS templates stay unchanged.

The existing scoped adaptation remains narrow: only the current installer's
cache copy is redirected to the generated public policy directory; all other
factory copy operations retain their original behaviour. The app-running hook
checks the exact fresh install path without process discovery or closure.
Actual manufacture must produce independent factory/guard/cache compiler
markers; synthetic preflight markers are moved beneath `preflight/` and cannot
satisfy that gate.

Pinned NSIS/7-Zip archives are extracted into fresh generated tool directories,
with every extracted file compared to its archive bytes. The factory's local
toolset API and configuration schema are checked directly. Generated resources
carry the electron-builder MIT notice, NSIS licence and 7-Zip licence/COPYING.

The supported `ELECTRON_BUILDER_COMPRESSION_LEVEL=1` override retains the
factory's install-decodable BCJ filter. The full factory preflight precedes the
large backend inventory, copying, builds and installer compression. The new
pipeline revalidates all public backend bytes, checks the entire copied Node
tree except disposable build caches, refreshes backend source from the exact
freeze and builds renderer/native from that freeze. It verifies the packaged
backend inventory, native adoption parity and one matching installer before
writing delivery provenance. No production compression duration is claimed.

## C output boundaries

`-DeliveryRoot` defaults to
`C:/Renulus-native-delivery/desktop-20261005`. It can select one lower-case
named child, `C:/Renulus-native-delivery/desktop-20261005/deliveries/<name>`.
Arbitrary drives/roots, repository/data/profile/credential roots, device names
and reparse traversal are refused. The PowerShell guard also rejects raw
trailing-dot/space aliases before .NET path normalization.

The controller, Python staging paths, installer helper and packaging config
propagate the selected root. The builder receives `RENULUS_DELIVERY_ROOT`.
Source snapshot, refreshed backend, build dependencies, temporary/cache files,
package and fresh install all resolve under that C root. Explicit public inputs
can stay on E; E outputs and the E source junction are refused by the public
output guards. Existing desktop release/test-results support remains scoped
to those assigned generated directories.

The parent completed the unchanged public Node environment copy to C, reporting
623.53 MiB with zero mismatches/failures. Its receipt is
`C:/rn-finalise-20261005/parent/relocation/public-node-copy.json`; E remains
preserved. The controller defaults to that C public Node environment. This
lane did not duplicate the copy. The new Plan verified its factory pins and
Electron package/artifact identity; full Node byte inventories remain a Package
gate. E collection and learning-profile data are not inputs and were not moved.

Package, Install and Proof require an explicit full revision, accepted freeze
and parent serial-slot release. Historical delivered/freeze55 revisions are
refused for manufacture. Inherited `ELECTRON_RUN_AS_NODE` and app/profile/session
overrides are removed from controlled children. No native app or installer was
launched in this lane.

## Recovered attempt 03 and scoped checks

Interrupted session 43609 has no live session to resume. Its complete attempt03
receipts were recovered from
`apps/desktop/test-results/nsis-full-factory-03/`; no compiler run was repeated.
`preflight-evidence.json` says `passed`, with `installer_execution: false`.
SHA256: `c8ba3ea61d627eee7e03eb0337eb69b30e3ce13e1eb5f2c41bc069f5db225370`.

Recorded child exits are `[0, 0, 1, 0, 0, 0, 0]`: synthetic archive/extraction,
expected stock-include refusal, then uninstaller and installer preprocessing
and compilation. Positive compiles retain warnings-as-errors. The negative
probe removed only the generated factory copy, reproduced the preserved
warning, restored the copy and passed. Recorded child durations total about
11.326 seconds; this is not total preparation wall time.

| Synthetic compile-only output | Bytes | SHA256 |
| --- | ---: | --- |
| `preflight/uninstaller-compile-only.exe` | 185,675 | `32d1b1d55998150b71cb92497dccff74c35ffb456faf9df4e058a5636bfa30c7` |
| `preflight/installer-compile-only.exe` | 417,848 | `93ba7759fdc46799d1b4b1f5b8a7af6e32cd968b718f21f2938d1d4363631b22` |

These outputs were rehashed during receipt recovery; neither was executed.
Guard/cache/factory markers are preserved only under `preflight/`. Additional
receipts include `policy-provenance.json`, `builder-overrides.json`,
`preflight/stock-collision-refused.stdout.log` and the three `compiled-*.log`
files beneath `preflight/`.

Earlier completed evidence, retained without repeating the batches: 14 NSIS
regressions, 10 delivery checks, 17 PowerShell refusals and baseline Plan passed.
New relocation checks passed:

- `test-restage-relocation.py -v`: 10 tests, 7.757 seconds, including Node config
  evaluation with a synthetic backend fixture, selected-root confinement,
  forbidden data/credential/source paths and recovered receipts.
- `test-restage-relocation.ps1`: 31 boundary refusals, canonical/named C roots,
  held phases, isolated real synthetic junctions and an AST-extracted installer
  path guard. The installer script itself was not evaluated or launched.
- Six owned Python files parsed without execution/bytecode; both owned JS config
  and preflight files passed `node --check`; `git diff --check` passed.

The first two new PowerShell attempts failed on a trailing-dot root alias. Those
logs are preserved. The controller's raw-path correction passed attempt03.
New receipts are in the assigned ignored `apps/desktop/test-results/`:
`relocation-python.{stdout,stderr}.log`,
`relocation-powershell-attempt03.{stdout,stderr}.log`, and
`relocated-plan.json`. The last has SHA256
`2534e932e0914a0021c59e6dc042b89e16941b52651ccff50453dc575f40b143`.

The new read-only driver Plan uses baseline `9d26f1ee` solely for planning
evidence: it admitted C Node and E backend/archive/cache inputs, with snapshot,
backend, environment, temporary and output paths all on C. Those product
directories were verified absent; Plan created only its worktree receipt. This
is not the final product freeze or permission to manufacture this baseline.

## Public reuse inputs for the final freeze

| Purpose | Explicit input | Admission |
| --- | --- | --- |
| Read-only tooling interpreter | `C:/Users/karol/Documents/t3-workspaces/Renulus-wt-integration/.venv/Scripts/python.exe` | Existing public Python environment; no dependency rebuild |
| Public Node dependencies | `C:/Renulus-native-delivery/desktop-20261005/environment/node-3ff9b0d6/node_modules` | Parent's C copy; builder 27.0.0-alpha.6, Electron 44.5.1; full copy inventory at Package |
| Base embedded backend/dependencies | `E:/Renulus-native-delivery/desktop-20261005/payloads/backend-55d553d1` | Revalidate recorded inventory before copying; then refresh source from final freeze |
| Helper bytes | Same base payload's `helper-assets` | Reviewed 19 files / 483,597,181 bytes; artifact hashes/terms in its contract |
| Helper contract | Same base payload's `packaging/runtime/helper-assets.json` | SHA256 `3d8ba8f76428f2c7fc0348167dd9b8c70e2f47f29dbd6705e01a6c0fdea97fce`; must equal final committed contract |
| Embedded Python archive | `E:/Renulus-native-delivery/desktop-20261005/preparation/restage-office-image-20261005/inputs/python-3.14.4-embed-amd64.zip` | SHA256 `cda80a9b1e75c0f1b4f9872ca1b417f0d19bce32facc811aea9180e70fad5fb9` |
| Public tool cache | `E:/Renulus-native-delivery/desktop-20261005/preparation/restage-office-image-20261005/public-build-cache/electron-builder` | Only the pinned archives below; extracted files revalidated |

Within that cache:

- `nsis@1.2.1/nsis-bundle-3.12.tar.gz`: SHA256
  `56997fdefe25e7928a1a68b4583d08b240b66cf660234053b20131a74cc082f4`.
- `7zip@1.0.0/7zip-win-x64.tar.gz`: SHA256
  `be071f15bd6da2f78fe81c6ddef2009b0c4d8a51f36b780cb806c7e6df95e1b3`.
- Factory `multiUser.nsh`: SHA256
  `9aca256695c289ec8a875143101fae8c6236bc8c6a7cf369bbe8b4986e09c9cb`.

The historical base inventory hash is
`2c73d9a289c61e44ead2a6b9266214c3b258ba67d43e3587a976420ef322175f`.
This lane did not rehash the multi-GB backend or execute helpers. A changed final
Python lock, desktop manifest/lock, helper contract or native adoption source
causes admission to fail; those gates have not been relaxed.

## Planned commands after parent freeze and release

The following is a proposed recipe, not an executed manufacture. The parent
must first integrate this machinery and all product lane patches and supply
the accepted full SHA. Use PowerShell 7. Build tools come from a fresh Git
archive of that same SHA, so the native adoption guard compares exact frozen
source. The named C root separates new manufacture from existing public inputs.

```powershell
$renulusFinalRevision = '<parent released full 40-character SHA>'
if ($renulusFinalRevision -notmatch '^[0-9a-f]{40}$') { throw 'Final parent freeze required.' }
$renulusSource = 'C:/Renulus-native-delivery/desktop-20261005/repo'
$renulusRoot = 'C:/Renulus-native-delivery/desktop-20261005/deliveries/finalise-20261005'
$renulusTag = $renulusFinalRevision.Substring(0, 8)

# Load only the integrated boundary functions, without invoking a phase.
. (Join-Path $renulusSource 'apps/desktop/scripts/restage-delivery.ps1')
$renulusRoot = Assert-DeliveryRoot $renulusRoot
$renulusExternalRoot = $renulusRoot
$renulusPreparation = Assert-PublicGeneratedPath (Join-Path $renulusRoot 'preparation/restage-finalise-20261005')
$renulusTools = Assert-PublicGeneratedPath (Join-Path $renulusPreparation ('frozen-tools-' + $renulusTag)) -Fresh
$renulusToolArchive = Assert-PublicGeneratedPath (Join-Path $renulusPreparation ('frozen-tools-' + $renulusTag + '.tar')) -Fresh
New-Item -ItemType Directory -Path $renulusTools | Out-Null
& git.exe -C $renulusSource archive --format=tar ('--output=' + $renulusToolArchive) $renulusFinalRevision
if ($LASTEXITCODE -ne 0) { throw 'Final freeze archive failed.' }
& tar.exe -xf $renulusToolArchive -C $renulusTools
if ($LASTEXITCODE -ne 0) { throw 'Final freeze tools extraction failed.' }

$renulusController = Join-Path $renulusTools 'apps/desktop/scripts/restage-delivery.ps1'
$renulusArguments = @{
    Revision = $renulusFinalRevision
    Source = $renulusSource
    DeliveryRoot = $renulusRoot
    PreparationRoot = $renulusPreparation
    PublicBasePayload = 'E:/Renulus-native-delivery/desktop-20261005/payloads/backend-55d553d1'
    PublicPythonArchive = 'E:/Renulus-native-delivery/desktop-20261005/preparation/restage-office-image-20261005/inputs/python-3.14.4-embed-amd64.zip'
    PublicNodeModules = 'C:/Renulus-native-delivery/desktop-20261005/environment/node-3ff9b0d6/node_modules'
    PublicBuildCache = 'E:/Renulus-native-delivery/desktop-20261005/preparation/restage-office-image-20261005/public-build-cache/electron-builder'
}
& $renulusController -Phase Plan @renulusArguments

# Each remaining phase needs the parent's explicit release at execution time.
& $renulusController -Phase Package -AcceptedFreeze -NativeSlotReleased @renulusArguments
& $renulusController -Phase Install -AcceptedFreeze -NativeSlotReleased @renulusArguments
# Proof additionally needs the parent-owned C proof-root correction below.
& $renulusController -Phase Proof -AcceptedFreeze -NativeSlotReleased @renulusArguments
```

Expected paths below the selected C root:

| Artifact | Relative path |
| --- | --- |
| Exact renderer/native source snapshot | `source-<tag>` |
| Refreshed embedded backend | `payloads/backend-<tag>` |
| Verified per-build Node copy | `environment/node-<tag>/node_modules` |
| Temp, toolsets, policy and compiler evidence | `temporary/build-<full-sha>` |
| Matching package and provenance | `matching-<tag>` |
| Installer | `matching-<tag>/Renulus-Development-0.1.0-windows-x64-setup.exe` |
| Fresh install | `installed-<tag>` |
| Controller receipts | `preparation/restage-finalise-20261005/runs/<tag>-<phase>-<id>` |
| Synthetic installed Proof | `proofs/<kind>-<id>` |

`<tag>` is the first eight hex characters of the parent's exact freeze. No
failed E application archive/ASAR is an input to this recipe. No Package,
Install or Proof command above has run, and no old-baseline manufacture was
started. Avoid repeating large compression until the cheap factory gate passes.

## Owned files and remaining parent prerequisites

Changed/added scripts: `delivery_paths.py`, `restage-delivery.ps1`,
`stage-delivery.py`, `test-installer.ps1`, `restage-nsis.py`,
`restage-nsis-preflight.mjs`, `restage-builder-MIT.txt`,
`test-restage-nsis.py`, `test-restage-relocation.py`,
`test-restage-relocation.ps1`, `test-restage-delivery.ps1`,
`test_stage_delivery.py`, all under `apps/desktop/scripts/`.
The only additional code file is the packaging guard in
`apps/desktop/electron-builder.config.cjs`. This report is the assigned
`docs/implementation/finalise-packaging.md`. Parent Vite, native, product,
schema and migration files were not edited.

The parent-owned `native-evidence-directory.mjs` in the relocated integration
source still admits only the E external proofs root at this handoff. Before
final freeze/Proof, the parent must admit the selected C `DeliveryRoot/proofs`
with equivalent confinement/reparse guards; merely changing the canonical
E string would not support the named root in this recipe. This lane leaves
that ownership intact.

Remaining acceptance: final exact freeze admission, one actual Package, fresh
Install, serial matching-installed native/helper/product verification and
parent final acceptance. No live provider calls, signing setup, installer/native
execution, profile/account access, data movement, shortcut change, deployment,
push or merge occurred. Synthetic/targeted checks do not establish product
end-to-end acceptance, a signed release or a clean-machine result.
