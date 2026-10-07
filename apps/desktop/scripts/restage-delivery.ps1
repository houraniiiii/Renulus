[CmdletBinding()]
param(
    [string]$Revision,
    [ValidateSet('Plan', 'Package', 'Install', 'Proof')][string]$Phase = 'Plan',
    [switch]$AcceptedFreeze,
    [switch]$NativeSlotReleased,
    [string]$ResumeFrom,
    [string]$Source = 'C:/Renulus-native-delivery/desktop-20261005/repo',
    [string]$DeliveryRoot = 'C:/Renulus-native-delivery/desktop-20261005',
    [string]$PublicBasePayload = 'E:/Renulus-native-delivery/desktop-20261005/payloads/backend-55d553d1',
    [string]$PublicPythonArchive = 'E:/Renulus-native-delivery/desktop-20261005/preparation/restage-office-image-20261005/inputs/python-3.14.4-embed-amd64.zip',
    [string]$PublicNodeModules = 'C:/Renulus-native-delivery/desktop-20261005/environment/node-3ff9b0d6/node_modules',
    [string]$PublicBuildCache = 'E:/Renulus-native-delivery/desktop-20261005/preparation/restage-office-image-20261005/public-build-cache/electron-builder',
    [string]$PreparationRoot
)
$ErrorActionPreference = 'Stop'
$renulusAuthorizedRoot = [IO.Path]::GetFullPath('C:/Renulus-native-delivery/desktop-20261005')
$renulusExternalRoot = $renulusAuthorizedRoot
$renulusPreviousRevision = 'ebb2db2e5080f4d42eaf31c2eb63711797704df0'

function Assert-RestageGate([string]$Commit, [string]$Action, [bool]$Accepted, [bool]$SlotReleased) {
    if ($Commit -notmatch '^[0-9a-f]{40}$') {
        throw 'Supply a new exact parent revision; preserve the previous frozen delivery.'
    }
    if ($Action -ne 'Plan' -and $Commit -in @($renulusPreviousRevision, '3ff9b0d6145c8d52f4c9e9b0a3009f0fc351c4cc', '55d553d1d18026a0a490f4292c033ac1aadd2595')) { throw 'Historical checkpoints are preserved; manufacture must use the integrator final freeze.' }
    if ($Action -ne 'Plan' -and -not $Accepted) { throw 'Only Plan is available until the parent accepts this exact freeze.' }
    if ($Action -in @('Package', 'Install', 'Proof') -and -not $SlotReleased) { throw 'Parent must release the serial manufacture/native slot before this phase.' }
}

function Assert-DeliveryRoot([string]$Value) {
    if ($Value -notmatch '^[Cc]:[\\/]' -or $Value -match '[\x00-\x1f]') { throw 'DeliveryRoot requires an absolute local C SSD path.' }
    # .NET can trim a trailing dot before GetFullPath returns; reject aliases
    # before that normalisation so all three packaging guards agree.
    foreach ($part in ($Value -split '[\\/]+')) {
        if ($part -in @('.', '..') -or $part.EndsWith('.') -or $part.EndsWith(' ')) { throw 'DeliveryRoot may not use Windows path aliases or traversal.' }
    }
    $absolute = [IO.Path]::GetFullPath($Value)
    if ($absolute -ne $renulusAuthorizedRoot) {
        if (-not $absolute.StartsWith($renulusAuthorizedRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'DeliveryRoot must stay below the exact authorised C SSD root.' }
        $relative = $absolute.Substring($renulusAuthorizedRoot.Length + 1)
        if ($relative -cnotmatch '^deliveries[\\/][a-z0-9][a-z0-9._-]{0,63}$' -or $relative.EndsWith('.') -or (Split-Path -Leaf $absolute) -match '^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?$') { throw 'DeliveryRoot may only use a named deliveries child; repository/data/profile/credential roots are excluded.' }
    }
    $cursor = $absolute
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            if (((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'DeliveryRoot may not traverse a reparse path.' }
        }
        $cursor = Split-Path -Parent $cursor
    }
    if ((Test-Path -LiteralPath $absolute) -and -not (Test-Path -LiteralPath $absolute -PathType Container)) { throw 'DeliveryRoot must be a directory.' }
    return $absolute
}

function Assert-PublicGeneratedPath([string]$Value, [switch]$Fresh) {
    # Generated delivery paths are local drive paths. This also supports the
    # Windows PowerShell 5.1 runtime, which lacks Path.IsPathFullyQualified.
    if ($Value -notmatch '^[A-Za-z]:[\\/]' -or $Value -match '[\x00-\x1f]') { throw 'Use an absolute local generated path.' }
    $absolute = [IO.Path]::GetFullPath($Value)
    if (-not $absolute.StartsWith($renulusExternalRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Generated outputs must stay below the exact authorised C delivery root; E inputs remain preserved.'
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

function Set-RestageEnvironment([string]$Name, [AllowNull()][object]$Value) {
    # PowerShell coerces a null string argument to empty for this .NET API.
    # Vite distinguishes an absent loopback override from an invalid empty URL.
    if ($null -eq $Value) { Remove-Item -LiteralPath ('Env:' + $Name) -ErrorAction SilentlyContinue }
    else { [Environment]::SetEnvironmentVariable($Name, [string]$Value, 'Process') }
}

# Dot-sourcing is for the boundary tests; it performs no I/O or phase invocation.
if ($MyInvocation.InvocationName -eq '.') { return }
$renulusExternalRoot = Assert-DeliveryRoot $DeliveryRoot
Assert-RestageGate $Revision $Phase ([bool]$AcceptedFreeze) ([bool]$NativeSlotReleased)
$renulusDesktop = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$renulusTag = $Revision.Substring(0, 8)
if (-not $PreparationRoot) { $PreparationRoot = Join-Path $renulusExternalRoot 'preparation/restage-finalise-20261005' }
$renulusPreparation = Assert-PublicGeneratedPath $PreparationRoot
$renulusArchive = $PublicPythonArchive
$renulusBasePayload = $PublicBasePayload
$renulusOutput = Join-Path $renulusExternalRoot ('matching-' + $renulusTag)
$renulusSnapshot = Join-Path $renulusExternalRoot ('source-' + $renulusTag)
$renulusInstall = Join-Path $renulusExternalRoot ('installed-' + $renulusTag)
$renulusPython = 'C:/Users/karol/Documents/t3-workspaces/Renulus-wt-integration/.venv/Scripts/python.exe'
$renulusEnvironment = Split-Path -Parent (Split-Path -Parent $renulusPython)
if ($ResumeFrom) {
    if ($Phase -ne 'Package') { throw 'Only the failed pre-package renderer stage may be continued.' }
    $renulusFailedReceipt = Assert-PublicGeneratedPath $ResumeFrom
    if (-not $renulusFailedReceipt.StartsWith($renulusPreparation + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Resume requires a failed receipt in this preparation tree.' }
    $renulusFailed = Get-Content -LiteralPath $renulusFailedReceipt -Raw | ConvertFrom-Json
    if ($renulusFailed.status -ne 'failed' -or $renulusFailed.phase -ne 'Package' -or $renulusFailed.requested_revision -ne $Revision -or [IO.Path]::GetFullPath($renulusFailed.output) -ne $renulusOutput) { throw 'The failed receipt does not identify this exact package stage.' }
    $renulusSnapshot = Join-Path $renulusSnapshot ('continued-' + [Guid]::NewGuid().ToString('N').Substring(0, 8))
}
if ($Phase -in @('Plan', 'Package')) {
    foreach ($target in @($renulusOutput, $renulusSnapshot, $renulusInstall)) {
        $null = Assert-PublicGeneratedPath $target -Fresh
    }
    foreach ($target in @(
        (Join-Path $renulusExternalRoot ('payloads/backend-' + $renulusTag)),
        (Join-Path $renulusExternalRoot ('environment/node-' + $renulusTag)),
        (Join-Path $renulusExternalRoot ('temporary/build-' + $Revision)))) {
        if ($ResumeFrom) { $null = Assert-PublicGeneratedPath $target }
        else { $null = Assert-PublicGeneratedPath $target -Fresh }
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
    foreach ($name in @('RENULUS_SOURCE_DESKTOP', 'RENULUS_BACKEND_URL', 'RENULUS_SESSION_TOKEN', 'RENULUS_PROFILE', 'RENULUS_PDF_FIXTURE_ONLY', 'ELECTRON_RUN_AS_NODE')) { $renulusSettings[$name] = $null }
    if ($Phase -eq 'Proof') {
        $renulusSettings['RENULUS_PACKAGED_EXECUTABLE'] = Join-Path $renulusInstall 'Renulus Development.exe'
        $renulusSettings['RENULUS_INSTALLED_PROOF'] = '1'
        $renulusSettings['RENULUS_EXPECT_SOURCE_REVISION'] = $Revision
        $renulusSettings['RENULUS_NATIVE_EVIDENCE_ROOT'] = Join-Path $renulusExternalRoot 'proofs'
        foreach ($name in @('RENULUS_EXPECT_STARTUP_WINDOW', 'RENULUS_EXPECT_SOURCE_BRIDGE', 'RENULUS_PROVE_WARM_RESTART', 'RENULUS_NATIVE_SERIAL', 'RENULUS_EXPECT_PRODUCT_BACKUP')) { $renulusSettings[$name] = '1' }
    }
    foreach ($name in $renulusSettings.Keys) {
        $renulusSavedSettings[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
        Set-RestageEnvironment $name $renulusSettings[$name]
    }
    $renulusResult = [ordered]@{ phase = $Phase; requested_revision = $Revision; accepted_freeze = [bool]$AcceptedFreeze; source = $Source; delivery_root = $renulusExternalRoot; public_base_payload = $renulusBasePayload; public_node_modules = $PublicNodeModules; output = $renulusOutput; install = $renulusInstall; reports = $renulusRun; previous_product = $renulusPreviousRevision; external_launcher_fix = 'parent-owned 4b1d2b71'; controller_sha256 = (Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant(); stage_driver_sha256 = (Get-FileHash -LiteralPath (Join-Path $PSScriptRoot 'stage-delivery.py') -Algorithm SHA256).Hash.ToLowerInvariant(); private_profile_use = $false; status = 'pending' }
    if ($Phase -in @('Plan', 'Package')) {
        $renulusStageArguments = @('-B', (Join-Path $PSScriptRoot 'stage-delivery.py'), '--source', $Source, '--revision', $Revision, '--delivery-root', $renulusExternalRoot, '--payload', $renulusBasePayload, '--snapshot', $renulusSnapshot, '--output', $renulusOutput, '--environment', $renulusEnvironment, '--helpers', (Join-Path $renulusBasePayload 'helper-assets'), '--python-archive', $renulusArchive, '--package', 'installer', '--node-modules', $PublicNodeModules, '--build-cache', $PublicBuildCache)
        if ($ResumeFrom) { $renulusStageArguments += '--resume-staged'; $renulusResult['continued_failed_receipt'] = $renulusFailedReceipt }
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
        Invoke-RestageCommand $renulusPowerShell @('-NoProfile', '-File', (Join-Path $PSScriptRoot 'test-installer.ps1'), '-Installer', $renulusInstaller, '-Target', $renulusInstall, '-DeliveryRoot', $renulusExternalRoot, '-SourceRevision', $Revision, '-InstallOnly') (Join-Path $renulusRun 'install')
        $renulusPackage = Get-Content -LiteralPath (Join-Path $renulusOutput 'delivery-provenance.json') -Raw | ConvertFrom-Json
        if ($renulusPackage.source_revision -ne $Revision -or
            (Get-FileHash -LiteralPath (Join-Path $renulusInstall 'Renulus Development.exe') -Algorithm SHA256).Hash.ToLowerInvariant() -ne $renulusPackage.executable_sha256 -or
            (Get-FileHash -LiteralPath (Join-Path $renulusInstall 'resources/app.asar') -Algorithm SHA256).Hash.ToLowerInvariant() -ne $renulusPackage.app_asar_sha256) {
            throw 'The fresh installed executable/ASAR differs from the matching package.'
        }
    } else {
        if (-not (Test-Path -LiteralPath $renulusSettings['RENULUS_PACKAGED_EXECUTABLE'] -PathType Leaf)) { throw 'The fresh matching installation is missing.' }
        $renulusNode = (Get-Command node.exe -ErrorAction Stop).Source
        # The parent requested one fresh installed start/shutdown only. Its real
        # shortcut/learning queue check is separate from this synthetic owner.
        $renulusResult['proof_scope'] = 'one matching-installed isolated opening/Flow/backend/start/shutdown; previous full matrix retained under ebb2db2e'
        foreach ($script in @('native-replacement-evidence.mjs')) {
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
    foreach ($name in $renulusSavedSettings.Keys) { Set-RestageEnvironment $name $renulusSavedSettings[$name] }
}
