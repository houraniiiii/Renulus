[CmdletBinding()]
param(
    [string]$Revision = 'a5488b2df636d5b45d945e611e6c6a61436a92c2',
    [ValidateSet('Plan', 'Package', 'Install', 'Proof')][string]$Phase = 'Plan',
    [switch]$AcceptedFreeze,
    [switch]$NativeSlotReleased,
    [string]$Source = 'E:/Renulus-native-delivery/desktop-20261005/repo',
    [string]$PreparationRoot = 'E:/Renulus-native-delivery/desktop-20261005/preparation/restage-a5488b2d-20261005'
)
$ErrorActionPreference = 'Stop'
$renulusExternalRoot = [IO.Path]::GetFullPath('E:/Renulus-native-delivery/desktop-20261005')
$renulusPreviousRevision = 'ebb2db2e5080f4d42eaf31c2eb63711797704df0'

function Assert-RestageGate([string]$Commit, [string]$Action, [bool]$Accepted, [bool]$SlotReleased) {
    if ($Commit -notmatch '^[0-9a-f]{40}$' -or $Commit -eq $renulusPreviousRevision) {
        throw 'Supply a new exact parent revision; preserve the previous frozen delivery.'
    }
    if ($Action -ne 'Plan' -and -not $Accepted) { throw 'Only Plan is available until the parent accepts this exact freeze.' }
    if ($Action -eq 'Proof' -and -not $SlotReleased) { throw 'Parent must release the native app slot before serial proof.' }
}

function Assert-PublicGeneratedPath([string]$Value, [switch]$Fresh) {
    if (-not [IO.Path]::IsPathFullyQualified($Value)) { throw 'Use an absolute generated path.' }
    $absolute = [IO.Path]::GetFullPath($Value)
    if (-not $absolute.StartsWith($renulusExternalRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Generated outputs must stay below the exact authorised E delivery root.'
    }
    $relative = $absolute.Substring($renulusExternalRoot.Length + 1)
    $first = $relative.Split([char[]]@([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar))[0]
    if ($first -notmatch '^(preparation|payloads|environment|temporary|proofs|source-[0-9a-f]{8}|matching-[0-9a-f]{8}|installed-[0-9a-f]{8})$') {
        throw 'The path is not a public generated directory; data and repository outputs are excluded.'
    }
    $cursor = $absolute
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            $item = Get-Item -LiteralPath $cursor -Force
            if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Generated output may not traverse a reparse path.' }
        }
        $cursor = Split-Path -Parent $cursor
    }
    if ($Fresh -and (Test-Path -LiteralPath $absolute)) { throw 'Use a fresh output; preserve every existing checkpoint.' }
    return $absolute
}

function Invoke-RestageCommand([string]$Executable, [string[]]$Arguments, [string]$LogPrefix) {
    & $Executable @Arguments 1> ($LogPrefix + '.stdout.log') 2> ($LogPrefix + '.stderr.log')
    if ($LASTEXITCODE -ne 0) { throw ('Command exited ' + $LASTEXITCODE + '; inspect ' + $LogPrefix + '.stderr.log') }
}

# Dot-sourcing is for the boundary tests; it performs no I/O or phase invocation.
if ($MyInvocation.InvocationName -eq '.') { return }
Assert-RestageGate $Revision $Phase ([bool]$AcceptedFreeze) ([bool]$NativeSlotReleased)
$renulusDesktop = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$renulusTag = $Revision.Substring(0, 8)
$renulusPreparation = Assert-PublicGeneratedPath $PreparationRoot
$renulusArchive = Join-Path $renulusPreparation 'inputs/python-3.14.4-embed-amd64.zip'
$renulusBasePayload = Join-Path $renulusExternalRoot 'payloads/backend-ebb2db2e'
$renulusOutput = Join-Path $renulusExternalRoot ('matching-' + $renulusTag)
$renulusSnapshot = Join-Path $renulusExternalRoot ('source-' + $renulusTag)
$renulusInstall = Join-Path $renulusExternalRoot ('installed-' + $renulusTag)
$renulusPython = 'C:/Users/karol/Documents/t3-workspaces/Renulus-wt-integration/.venv/Scripts/python.exe'
$renulusEnvironment = Split-Path -Parent (Split-Path -Parent $renulusPython)
if ($Phase -in @('Plan', 'Package')) {
    foreach ($target in @($renulusOutput, $renulusSnapshot, $renulusInstall,
        (Join-Path $renulusExternalRoot ('payloads/backend-' + $renulusTag)),
        (Join-Path $renulusExternalRoot ('environment/node-' + $renulusTag)),
        (Join-Path $renulusExternalRoot ('temporary/build-' + $Revision)))) {
        $null = Assert-PublicGeneratedPath $target -Fresh
    }
    if (-not (Test-Path -LiteralPath $renulusArchive -PathType Leaf)) { throw 'The checksum-verified preparation archive is missing.' }
}
$renulusRun = Assert-PublicGeneratedPath (Join-Path $renulusPreparation ('runs/' + $renulusTag + '-' + $Phase.ToLowerInvariant() + '-' + [Guid]::NewGuid().ToString('N').Substring(0, 8))) -Fresh
New-Item -ItemType Directory -Path $renulusRun | Out-Null
$renulusTemporary = Join-Path $renulusRun 'temporary'
New-Item -ItemType Directory -Path $renulusTemporary | Out-Null
$renulusSettings = @{ TEMP = $renulusTemporary; TMP = $renulusTemporary; PYTHONDONTWRITEBYTECODE = '1' }
$renulusSavedSettings = @{}
try {
    # These values belong only to this controller process and its children.
    # Never attach proof to a caller's real app/profile or print session tokens.
    foreach ($name in @('RENULUS_SOURCE_DESKTOP', 'RENULUS_BACKEND_URL', 'RENULUS_SESSION_TOKEN', 'RENULUS_PROFILE', 'RENULUS_PDF_FIXTURE_ONLY')) { $renulusSettings[$name] = $null }
    if ($Phase -eq 'Proof') {
        $renulusSettings['RENULUS_PACKAGED_EXECUTABLE'] = Join-Path $renulusInstall 'Renulus Development.exe'
        $renulusSettings['RENULUS_INSTALLED_PROOF'] = '1'
        $renulusSettings['RENULUS_EXPECT_SOURCE_REVISION'] = $Revision
        $renulusSettings['RENULUS_NATIVE_EVIDENCE_ROOT'] = Join-Path $renulusExternalRoot 'proofs'
        foreach ($name in @('RENULUS_EXPECT_STARTUP_WINDOW', 'RENULUS_EXPECT_SOURCE_BRIDGE', 'RENULUS_PROVE_WARM_RESTART', 'RENULUS_NATIVE_SERIAL', 'RENULUS_EXPECT_PRODUCT_BACKUP')) { $renulusSettings[$name] = '1' }
    }
    foreach ($name in $renulusSettings.Keys) {
        $renulusSavedSettings[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
        [Environment]::SetEnvironmentVariable($name, $renulusSettings[$name], 'Process')
    }
    $renulusResult = [ordered]@{ phase = $Phase; requested_revision = $Revision; accepted_freeze = [bool]$AcceptedFreeze; source = $Source; public_base_payload = $renulusBasePayload; output = $renulusOutput; install = $renulusInstall; reports = $renulusRun; previous_product = $renulusPreviousRevision; external_launcher_fix = 'parent-owned 4b1d2b71'; controller_sha256 = (Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant(); stage_driver_sha256 = (Get-FileHash -LiteralPath (Join-Path $PSScriptRoot 'stage-delivery.py') -Algorithm SHA256).Hash.ToLowerInvariant(); private_profile_use = $false; status = 'pending' }
    if ($Phase -in @('Plan', 'Package')) {
        $renulusStageArguments = @('-B', (Join-Path $PSScriptRoot 'stage-delivery.py'), '--source', $Source, '--revision', $Revision, '--payload', $renulusBasePayload, '--snapshot', $renulusSnapshot, '--output', $renulusOutput, '--environment', $renulusEnvironment, '--helpers', (Join-Path $renulusBasePayload 'helper-assets'), '--python-archive', $renulusArchive, '--package', 'installer')
        if ($Phase -eq 'Plan') { $renulusStageArguments += '--plan-only' }
        Invoke-RestageCommand $renulusPython $renulusStageArguments (Join-Path $renulusRun 'stage')
        if ($Phase -eq 'Plan') {
            $renulusPlan = Get-Content -LiteralPath (Join-Path $renulusRun 'stage.stdout.log') -Raw | ConvertFrom-Json
            if (-not $renulusPlan.plan_only -or $renulusPlan.source_revision -ne $Revision) { throw 'Read-only plan did not match the requested revision.' }
            $renulusResult['plan_only'] = $true
        }
    } elseif ($Phase -eq 'Install') {
        $null = Assert-PublicGeneratedPath $renulusInstall -Fresh
        $renulusInstaller = Join-Path $renulusOutput 'Renulus-Development-0.1.0-windows-x64-setup.exe'
        $renulusPowerShell = (Get-Command pwsh.exe -ErrorAction Stop).Source
        Invoke-RestageCommand $renulusPowerShell @('-NoProfile', '-File', (Join-Path $PSScriptRoot 'test-installer.ps1'), '-Installer', $renulusInstaller, '-Target', $renulusInstall, '-SourceRevision', $Revision, '-InstallOnly') (Join-Path $renulusRun 'install')
        $renulusPackage = Get-Content -LiteralPath (Join-Path $renulusOutput 'delivery-provenance.json') -Raw | ConvertFrom-Json
        if ($renulusPackage.source_revision -ne $Revision -or
            (Get-FileHash -LiteralPath (Join-Path $renulusInstall 'Renulus Development.exe') -Algorithm SHA256).Hash.ToLowerInvariant() -ne $renulusPackage.executable_sha256 -or
            (Get-FileHash -LiteralPath (Join-Path $renulusInstall 'resources/app.asar') -Algorithm SHA256).Hash.ToLowerInvariant() -ne $renulusPackage.app_asar_sha256) {
            throw 'The fresh installed executable/ASAR differs from the matching package.'
        }
    } else {
        if (-not (Test-Path -LiteralPath $renulusSettings['RENULUS_PACKAGED_EXECUTABLE'] -PathType Leaf)) { throw 'The fresh matching installation is missing.' }
        $renulusNode = (Get-Command node.exe -ErrorAction Stop).Source
        # Lifecycle/helper baselines are already dated in the retained ebb2db2e
        # reports. The parent requested a focused matching-install journey.
        $renulusResult['proof_scope'] = 'matching-installed opening/Flow, PDF physical page 2, source bridge and real format-2 Save/Cancel; prior lifecycle/helper baseline retained separately'
        foreach ($script in @('native-journeys.mjs')) {
            Invoke-RestageCommand $renulusNode @((Join-Path $PSScriptRoot $script)) (Join-Path $renulusRun ([IO.Path]::GetFileNameWithoutExtension($script)))
        }
    }
    $renulusResult['status'] = 'complete'
    $renulusResult | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $renulusRun 'controller-evidence.json') -Encoding utf8
    $renulusResult | ConvertTo-Json -Depth 4 -Compress
} catch {
    if ($renulusResult) {
        $renulusResult['status'] = 'failed'
        $renulusResult['error'] = $_.Exception.Message
        $renulusResult | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $renulusRun 'controller-evidence.json') -Encoding utf8
    }
    throw
} finally {
    foreach ($name in $renulusSavedSettings.Keys) { [Environment]::SetEnvironmentVariable($name, $renulusSavedSettings[$name], 'Process') }
}
