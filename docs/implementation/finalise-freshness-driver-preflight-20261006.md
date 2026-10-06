# Freshness follow-on driver preflight — October 6, 2026

Prepared on `codex/freshness-driver-preflight-20261006` from
`0f2b29cb0ef2e318bd921dcea0660b304ee53d13`. The accepted production target remains
`699938f20efb6bbc2cf8df684cc5c6c3450e6eaf`.

The exclusive tracked lease is this new report. The only ignored handoff files
are `.local/freshness-driver-preflight-20261006/source.patch` and
`.local/freshness-driver-preflight-20261006/manifest.json` in this lane. Other
workers' files and the deployed preparation were preserved. Candidate source
was held in memory to derive the patch; no complete driver copy or candidate
deployment was written. No production code or accepted target was changed.

Read AGENTS, README, brief, workspace, decisions, planning stage/ownership guidance,
and relevant installed, Connected continuation, freshness/correction and response
observation delivery reports. The user now reports recovered passed Connected03
and a first Probe main_identity failure before catalogue/selection/thread/answer/
capture/provider: Playwright's process().pid identified Windows cmd.exe launcher22556.
The user reports zero new provider requests. These are parent-reported observations,
not receipts read or rebound here. Parent preserves the original failed Probe latch
and owns explicit continuation of the same first logical proof with pinned
pre-dispatch failure and separate driver02 latches; no quota retry is authorised
by this lane. Parent retains review, Probe/Journeys, the native serial slot and
acceptance. Completed Probe/Journeys receipts remain unavailable and unbound.
binding.template.json retains its null paths/hashes; no receipt was guessed.

The deployed source was inspected read-only at:
C:/Renulus-native-delivery/desktop-20261005/repo/apps/desktop/.local/freshness-correction-followon-20261006.

Three concrete seams are repaired in the proposed sibling. The PowerShell helper
assigns `$renulusOwners = ConvertFrom-Json -InputObject $Identities` without the
outer array wrapper, allowing foreach to receive individual JSON owners. All
PID/executable/creation-time checks, PID38448 refusal, identity-matched handles
and the shared 30,000 ms physical wait remain unchanged.

followon.mjs uses asynchronous execFile through Node's built-in promisify only for
Exit, and close awaits that result. Prelaunch/Inspect retain execFileSync. The
ordinary BrowserWindow.close call/error handling and existing 40,000 ms Exit
child timeout/15,000 ms other child timeouts remain. No app.close, forced
main/backend termination or retry is added. Async Exit allows Node/Playwright's
event loop to continue while the helper waits. The earlier starvation diagnosis
remains a parent hypothesis; this lane did not execute the repaired shutdown.

For both main-owner Inspect calls, followon.mjs now uses the actual Electron
`{ pid: process.pid, executable: process.execPath }` returned by
`application.evaluate`. It checks that executable against the exact installed EXE
and checks CIM's returned PID/executable before proceeding. The second Inspect
reuses the evaluated main PID alongside the existing observed backend child.
Both uses of application.process().pid are removed. current.application remains
assigned before identity validation, and the existing catch forwards current for
ordinary failure cleanup. The Windows launcher is never substituted for the
owned Electron main. No account/catalogue/selection/request or latch policy changes.

source-pins.json keeps the response observer under mirrored_helpers and records
the process helper under adapted_helpers with its actual hash and separate
inherited origin hash. prepared_driver records the actual repaired followon.mjs
hash and pre-repair source hash. The existing helper hash check covers both lists.
seal-preparation.ps1 is updated as text to emit that distinction rather than demand
that the repaired helper equal its historical mirror; the script was not run.
README and preparation manifest/checksum describe the sibling and actual identities.
All 17 selected frozen-source byte counts/SHA256 pins were verified directly against
Git blobs at the accepted revision and remain unchanged. These pins are a selected
reading inventory, with no complete-source qualification claim.

Source inspection found no obvious request-method or locator blocker. Frozen
Learn uses GET for resume, POST for Explain, the existing thread-row resume button,
Teaching style/Topic/Your follow-up labels, Scientific evidence status and public
passage/rights selectors. No method, locator or product refinement was added.

The patch has seven target paths, 68 insertions and 35 deletions. LF
code/Markdown and CRLF JSON/checksum bytes are preserved. Expected patched identities
below are in-memory postimages; the lane did not apply or execute them.

| Sibling relative file | Expected bytes | Expected SHA256 |
| --- | ---: | --- |
| `followon.mjs` | 26399 | `ba174fdc5098b0cafd83916f4071a852a00a3aa07ebda67d3f8f20b36374efcd` |
| `helpers/owned-processes.ps1` | 3225 | `7f2763576b84a6a16679428fa3c20a52bfb2d20f53704beb71d3e3ae1acb7ad8` |
| `source-pins.json` | 4963 | `280baf5695610ad0e31d4528d014ca7b49b3e0c8e0ad5827072acc3714059168` |
| `seal-preparation.ps1` | 7581 | `b1a1711a9377d17f87adcc2bb24ecdcd1b83c0faaedb58555ace21c28f1567f8` |
| `README.md` | 8629 | `a5a629690810732f3b039d4398f0ab7e9e9d74eea0a18aff3bf99c851c6cfec2` |
| `manifest.json` | 1798 | `723c1b5714f6e23ae23a54d0248f10dde813cc9fcc60e47cc05adc2c8850334c` |
| `manifest.sha256` | 81 | `adc85c93a7a7734bce7022c1b09ea475a78e1a5c113b962afde05e6025f0f5d3` |

binding.template.json (590 bytes), correction-reuse.md (10,958 bytes) and
helpers/response-observation.mjs (9,379 bytes) remain byte-identical. Complete
before/after hashes for all ten files are in the handoff manifest. The expected
sibling has ten files / 73,603 bytes, including eight payload files /
71,724 bytes. Its preparation manifest SHA256 is
`723c1b5714f6e23ae23a54d0248f10dde813cc9fcc60e47cc05adc2c8850334c`.
execution_performed, parent_acceptance_bound and correction_inputs_bound remain
false. Source/native admission, fresh evidence, correction/reuse and physical-close
acceptance remain parent work.

Preserve both ignored files before retiring the lane. Combined size is
27,971 bytes. The handoff manifest records the baseline/postimage bytes and hashes,
verified frozen pins, ownership/timing semantics and exact applicability scope.
It excludes its own hash; this committed report pins that identity.

| Ignored artifact | Bytes | SHA256 |
| --- | ---: | --- |
| source.patch | 17842 | `8bb6805fc8ea911396479ead28f4a2d33be8653b1de0cad83506b2171d56cfd4` |
| manifest.json | 10129 | `1a3f41672f37af44be09300372e401aff65108fddf4ff1d75b2c396dafb91f82` |

Only text/JSON inspection, byte/hash comparisons, Git blob reads and Git
applicability/whitespace checks were performed. The final read-only check explicitly
reported Checking patch for all seven paths and exited 0. Git from the ignored
subdirectory without a repository-relative --directory skips these patches;
use the repository root and --directory below. JavaScript syntax checks,
PowerShell AST parsing, tests/collection, application/dependency imports,
--plan/--run, native/process/helper commands, profiles/credentials, providers,
models/network, Go/fallback and account actions were not performed. All ten
baseline files were hashed again unchanged before sealing the handoff.

These complete parent application commands were not executed here. They copy
only the ten pinned preparation files into a new sibling; bindings, receipts,
profiles and dependency trees are excluded from that exact file list. The deployed
baseline remains read-only; an existing sibling is refused. Parent reviews and
preserves the handoff before application. No sealer or driver command is needed
to apply this already pinned preparation.

~~~powershell
$ErrorActionPreference = 'Stop'
$repairRoot = 'C:/rn-finalise-20261005/lanes/freshness-driver-preflight-20261006/.local/freshness-driver-preflight-20261006'
$deliveryRepo = 'C:/Renulus-native-delivery/desktop-20261005/repo'
$sourceRoot = "$deliveryRepo/apps/desktop/.local/freshness-correction-followon-20261006"
$siblingRelative = 'apps/desktop/.local/freshness-correction-followon-driver-repair-20261006'
$siblingRoot = Join-Path $deliveryRepo $siblingRelative
$repairManifestPath = Join-Path $repairRoot 'manifest.json'
$sourcePatch = Join-Path $repairRoot 'source.patch'
if ((Get-FileHash -LiteralPath $repairManifestPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne '1a3f41672f37af44be09300372e401aff65108fddf4ff1d75b2c396dafb91f82') { throw 'Repair manifest changed.' }
$repair = Get-Content -Raw -LiteralPath $repairManifestPath | ConvertFrom-Json
if ((Get-FileHash -LiteralPath $sourcePatch -Algorithm SHA256).Hash.ToLowerInvariant() -ne $repair.patch.sha256 -or (Get-Item -LiteralPath $sourcePatch).Length -ne $repair.patch.bytes) { throw 'Repair patch changed.' }
if (Test-Path -LiteralPath $siblingRoot) { throw 'Existing sibling is preserved; no implicit replacement or repeat.' }
foreach ($row in $repair.files) {
    $source = Join-Path $sourceRoot $row.relative_path
    if ((Get-Item -LiteralPath $source).Length -ne $row.before_bytes -or (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant() -ne $row.before_sha256) { throw ('Deployed baseline changed: ' + $row.relative_path) }
}
[IO.Directory]::CreateDirectory($siblingRoot) | Out-Null
foreach ($row in $repair.files) {
    $destination = Join-Path $siblingRoot $row.relative_path
    [IO.Directory]::CreateDirectory((Split-Path -Parent $destination)) | Out-Null
    Copy-Item -LiteralPath (Join-Path $sourceRoot $row.relative_path) -Destination $destination
}
& git -C $deliveryRepo -c core.autocrlf=false -c core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol apply "--directory=$siblingRelative" --check --verbose --whitespace=error $sourcePatch
if ($LASTEXITCODE -ne 0) { throw 'Sibling check failed; retain preparation for review.' }
& git -C $deliveryRepo -c core.autocrlf=false -c core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol apply "--directory=$siblingRelative" --whitespace=error $sourcePatch
if ($LASTEXITCODE -ne 0) { throw 'Sibling application failed; retain preparation for review.' }
foreach ($row in $repair.files) {
    $result = Join-Path $siblingRoot $row.relative_path
    if ((Get-Item -LiteralPath $result).Length -ne $row.after_bytes -or (Get-FileHash -LiteralPath $result -Algorithm SHA256).Hash.ToLowerInvariant() -ne $row.after_sha256) { throw ('Patched identity mismatch: ' + $row.relative_path) }
}
Write-Output 'Prepared sibling byte/hash comparison passed; runtime validation remains parent work.'
~~~

For retirement preservation, parent can use these separate unexecuted commands.
An existing preservation destination is refused. After retirement use the preserved
directory as repairRoot for application.

~~~powershell
$preservedRepair = 'C:/rn-finalise-20261005/preserved-lanes/freshness-driver-preflight-20261006'
if (Test-Path -LiteralPath $preservedRepair) { throw 'Existing preservation destination is preserved.' }
[IO.Directory]::CreateDirectory($preservedRepair) | Out-Null
foreach ($name in @('source.patch', 'manifest.json')) {
    Copy-Item -LiteralPath (Join-Path $repairRoot $name) -Destination (Join-Path $preservedRepair $name)
}
if ((Get-FileHash -LiteralPath (Join-Path $preservedRepair 'source.patch') -Algorithm SHA256).Hash.ToLowerInvariant() -ne '8bb6805fc8ea911396479ead28f4a2d33be8653b1de0cad83506b2171d56cfd4' -or (Get-FileHash -LiteralPath (Join-Path $preservedRepair 'manifest.json') -Algorithm SHA256).Hash.ToLowerInvariant() -ne '1a3f41672f37af44be09300372e401aff65108fddf4ff1d75b2c396dafb91f82') { throw 'Preserved handoff identity mismatch.' }
~~~

The report-only commit uses hooks disabled. The ignored patch/manifest are not
committed. Parent must retain both before retirement and bind only actual admitted
Probe/Journeys after completion. Existing failure evidence/latches, accepted699938f2
and all actual review/execution remain outside this repair's write scope.
