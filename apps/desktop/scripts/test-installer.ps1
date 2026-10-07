[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Installer,
    [Parameter(Mandatory = $true)][string]$Target,
    [Parameter(Mandatory = $true)][string]$SourceRevision,
    [string]$DeliveryRoot = 'C:/Renulus-native-delivery/desktop-20261005',
    [switch]$ExpectStartupWindow,
    [switch]$ExpectSourceBridge,
    [switch]$WarmRestart,
    [switch]$ViewerJourney,
    [switch]$InstallOnly,
    [switch]$SerialNative
)
$ErrorActionPreference = 'Stop'
$desktopRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$releaseRoot = [IO.Path]::GetFullPath((Join-Path $desktopRoot 'release'))
. (Join-Path $PSScriptRoot 'restage-delivery.ps1') -DeliveryRoot $DeliveryRoot
$externalRoot = Assert-DeliveryRoot $DeliveryRoot
. (Join-Path $PSScriptRoot 'installer-child.ps1')
function Assert-OwnedReleasePath([string]$Value) {
    if (-not [IO.Path]::IsPathFullyQualified($Value)) { throw 'An explicit absolute release path is required.' }
    $absolute = [IO.Path]::GetFullPath($Value)
    if (-not ($absolute.StartsWith($releaseRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -or $absolute.StartsWith($externalRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase))) { throw 'Installer and install target must stay in the desktop release tree or exact authorised C root; E checkpoints are preserved.' }
    if ($absolute.StartsWith($externalRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        $first = $absolute.Substring($externalRoot.Length + 1).Split([char[]]@([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar))[0]
        if ($first -notmatch '^(matching-[0-9a-f]{8}|installed-[0-9a-f]{8}|temporary|proofs)$') { throw 'Installer paths exclude repositories, data and other application state.' }
    }
    $cursor = $absolute
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            $item = Get-Item -LiteralPath $cursor -Force
            if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'A release path must not traverse a junction or symbolic link.' }
        }
        $cursor = Split-Path -Parent $cursor
    }
    return $absolute
}
$installerPath = Assert-OwnedReleasePath $Installer
$targetPath = Assert-OwnedReleasePath $Target
$temporaryPath = Assert-OwnedReleasePath (Join-Path $externalRoot ('temporary/install-' + [Guid]::NewGuid().ToString('N').Substring(0,8)))
if (-not (Test-Path -LiteralPath $installerPath -PathType Leaf)) { throw 'The completed installer is missing.' }
if (Test-Path -LiteralPath $targetPath) { throw 'Refusing an existing install directory; preserve previous output and use a fresh target.' }
if ($SourceRevision -notmatch '^[0-9a-f]{40}$') { throw 'An exact committed source revision is required.' }
$developerNode = (Get-Command node.exe -ErrorAction Stop).Source
$evidence = Assert-OwnedReleasePath (Join-Path $externalRoot ('proofs/installer-' + [Guid]::NewGuid().ToString('N').Substring(0, 8)))
New-Item -ItemType Directory -Path $evidence | Out-Null
$report = [ordered]@{
    checkedAt = [DateTime]::UtcNow.ToString('o')
    kind = 'unsigned-installer-execution'
    installer = $installerPath
    installerSha256 = (Get-FileHash -LiteralPath $installerPath -Algorithm SHA256).Hash.ToLowerInvariant()
    installerBytes = (Get-Item -LiteralPath $installerPath).Length
    signature = (Get-AuthenticodeSignature -LiteralPath $installerPath).Status.ToString()
    target = $targetPath
    installerTemporaryDirectory = $temporaryPath
    expectedSourceRevision = $SourceRevision
    limits = @('This actual Windows machine; no signed or clean-VM proof', 'Synthetic independent native profiles only', 'No provider login or inference', 'No uninstaller or callback-cleanup claim')
}
$failure = $null
try {
    $startedAt = [DateTime]::UtcNow
    New-Item -ItemType Directory -Path $temporaryPath | Out-Null
    # NSIS requires /D last. Target is guarded, absolute and intentionally fresh.
    $childInfo = New-InstallerChildInfo $installerPath ('/S /D=' + $targetPath) $temporaryPath
    $process = [Diagnostics.Process]::Start($childInfo)
    $process.WaitForExit(); $process.Refresh()
    $report.installSeconds = ([DateTime]::UtcNow - $startedAt).TotalSeconds
    $report.installExitCode = $process.ExitCode
    if ($process.ExitCode -ne 0) { throw ('NSIS exited ' + $process.ExitCode) }
    $installedExe = Join-Path $targetPath 'Renulus Development.exe'
    if (-not (Test-Path -LiteralPath $installedExe -PathType Leaf)) { throw 'NSIS did not create the expected installed executable.' }
    $report.installedExecutable = $installedExe
    $report.installedExecutableSha256 = (Get-FileHash -LiteralPath $installedExe -Algorithm SHA256).Hash.ToLowerInvariant()
    $report.installedAsarSha256 = (Get-FileHash -LiteralPath (Join-Path $targetPath 'resources/app.asar') -Algorithm SHA256).Hash.ToLowerInvariant()
    $contract = Get-Content -LiteralPath (Join-Path $targetPath 'resources/backend/bundle.json') -Raw | ConvertFrom-Json
    if ($contract.source_revision -ne $SourceRevision -or $contract.python.version -ne '3.14.4' -or $contract.format -ne 'embedded-cpython-windows-v1') { throw 'The installed embedded runtime contract does not match the requested committed source.' }
    $report.installedSourceRevision = $contract.source_revision
    if ($InstallOnly) {
        $report.kind = 'unsigned-installer-extraction-only'
        $report.nativeProof = 'Not run: resource coordination; no app/Python instance launched'
    } else {
    $env:RENULUS_PACKAGED_EXECUTABLE = $installedExe
    $env:RENULUS_INSTALLED_PROOF = '1'
    $env:RENULUS_EXPECT_SOURCE_REVISION = $SourceRevision
    $env:RENULUS_NATIVE_EVIDENCE_ROOT = Join-Path $externalRoot 'proofs'
    foreach ($setting in @(@('RENULUS_EXPECT_STARTUP_WINDOW', $ExpectStartupWindow), @('RENULUS_EXPECT_SOURCE_BRIDGE', $ExpectSourceBridge), @('RENULUS_PROVE_WARM_RESTART', $WarmRestart), @('RENULUS_NATIVE_SERIAL', $SerialNative))) {
        if ($setting[1]) { Set-Item -Path ('Env:' + $setting[0]) -Value '1' } else { Remove-Item -LiteralPath ('Env:' + $setting[0]) -ErrorAction SilentlyContinue }
    }
    & $developerNode (Join-Path $PSScriptRoot 'native-evidence.mjs') 2>&1 | Tee-Object -FilePath (Join-Path $evidence 'native.log')
    $report.nativeExitCode = $LASTEXITCODE
    if ($LASTEXITCODE -ne 0) { throw 'The installed no-dev-PATH native proof failed; inspect native.log.' }
    if ($ViewerJourney) {
        & $developerNode (Join-Path $PSScriptRoot 'native-journeys.mjs') 2>&1 | Tee-Object -FilePath (Join-Path $evidence 'journeys.log')
        $report.journeysExitCode = $LASTEXITCODE
        if ($LASTEXITCODE -ne 0) { throw 'The installed PDF/publisher journey failed; inspect journeys.log.' }
    }
    }
} catch { $failure = $_; $report.error = $_.Exception.Message }
finally {
    $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $evidence 'installer-evidence.json') -Encoding utf8
    $report | ConvertTo-Json -Depth 8
    Write-Output ('Installer evidence: ' + $evidence)
}
if ($failure) { throw $failure }
