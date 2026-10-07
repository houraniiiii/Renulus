$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'restage-delivery.ps1')
$refusals = 0
function Require-Refusal([scriptblock]$Action, [string]$Description = 'boundary') {
    try { & $Action | Out-Null } catch { $script:refusals += 1; return }
    throw ('Relocation boundary accepted ' + $Description + ': ' + $Action.ToString())
}
$expectedRoot = [IO.Path]::GetFullPath('C:/Renulus-native-delivery/desktop-20261005')
if ($renulusExternalRoot -ne $expectedRoot) { throw 'Controller output root was not relocated.' }
if ((Assert-DeliveryRoot $expectedRoot) -ne $expectedRoot) { throw 'Canonical C root was not accepted.' }
$namedRoot = Join-Path $expectedRoot 'deliveries/relocation-check-never-created'
if ((Assert-DeliveryRoot $namedRoot) -ne $namedRoot) { throw 'Named C root was not accepted.' }
foreach ($root in @('E:/Renulus-native-delivery/desktop-20261005', 'C:relative',
    (Join-Path $expectedRoot 'repo'), (Join-Path $expectedRoot 'data'),
    (Join-Path $expectedRoot 'profiles'), (Join-Path $expectedRoot 'credentials'),
    (Join-Path $expectedRoot 'deliveries'), (Join-Path $namedRoot 'extra'),
    (Join-Path $expectedRoot 'deliveries/Uppercase'), (Join-Path $expectedRoot 'deliveries/nul'),
    (Join-Path $expectedRoot 'deliveries/nul.txt'), (Join-Path $expectedRoot 'deliveries/alias.'))) {
    Require-Refusal { Assert-DeliveryRoot $root } $root
}
$fresh = Join-Path $expectedRoot 'matching-cafe1234/relocation-check-never-created'
$null = Assert-PublicGeneratedPath $fresh -Fresh
if (Test-Path -LiteralPath $fresh) { throw 'Read-only guard created an output.' }
foreach ($path in @('E:/Renulus-native-delivery/desktop-20261005/matching-cafe1234', 'C:/Renulus-native-delivery/desktop-20261005/repo/private', 'C:/Renulus-native-delivery/desktop-20261005/data/learning', 'C:/Renulus-native-delivery/desktop-20261005/profiles/native', 'C:/Renulus-native-delivery/desktop-20261005/credentials/auth.json', 'C:/Users/karol/.codex/auth.json', 'C:/Renulus-native-delivery/desktop-20261005-other/matching-cafe1234')) {
    Require-Refusal { Assert-PublicGeneratedPath $path } $path
}
foreach ($phase in @('Package', 'Install', 'Proof')) {
    Require-Refusal { Assert-RestageGate ('a' * 40) $phase $true $false }
}

# Load only the installer guard function from its AST. Do not evaluate the
# installer script's parameters, signature checks, child launch or proof flow.
$tokens = $null; $errors = $null
$installerFile = Join-Path $PSScriptRoot 'test-installer.ps1'
$installerAst = [Management.Automation.Language.Parser]::ParseFile($installerFile, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw 'Installer helper has parse errors.' }
$guard = $installerAst.Find({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Assert-OwnedReleasePath'}, $true)
if (-not $guard) { throw 'Installer path guard is missing.' }
. ([scriptblock]::Create($guard.Extent.Text))
$desktopRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$releaseRoot = Join-Path $desktopRoot 'release'
$externalRoot = $expectedRoot
$null = Assert-OwnedReleasePath (Join-Path $expectedRoot 'installed-cafe1234')
Require-Refusal { Assert-OwnedReleasePath 'E:/Renulus-native-delivery/desktop-20261005/installed-cafe1234' }
Require-Refusal { Assert-OwnedReleasePath 'C:/Renulus-native-delivery/desktop-20261005/data/learning' }
Require-Refusal { Assert-OwnedReleasePath 'C:/Renulus-native-delivery/desktop-20261005/repo/private' }
Require-Refusal { Assert-OwnedReleasePath 'C:/Renulus-native-delivery/desktop-20261005/credentials/auth.json' }
$renulusExternalRoot = Assert-DeliveryRoot $namedRoot
$externalRoot = $renulusExternalRoot
$null = Assert-PublicGeneratedPath (Join-Path $namedRoot 'matching-cafe1234/never-created') -Fresh
$null = Assert-OwnedReleasePath (Join-Path $namedRoot 'installed-cafe1234')
Require-Refusal { Assert-PublicGeneratedPath $fresh }
Require-Refusal { Assert-OwnedReleasePath (Join-Path $expectedRoot 'installed-cafe1234') }
if (Test-Path -LiteralPath $namedRoot) { throw 'Boundary checks created a delivery root.' }

# A real junction fixture stays inside the assigned ignored test-results. All
# metadata targets are synthetic; no application or credential file is opened.
$scratch = Join-Path $desktopRoot ('test-results/relocation-junction-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path (Join-Path $scratch 'temporary'), (Join-Path $scratch 'public-target'), (Join-Path $scratch 'deliveries') | Out-Null
New-Item -ItemType Junction -Path (Join-Path $scratch 'temporary/link') -Target (Join-Path $scratch 'public-target') | Out-Null
New-Item -ItemType Junction -Path (Join-Path $scratch 'deliveries/linked') -Target (Join-Path $scratch 'public-target') | Out-Null
$renulusAuthorizedRoot = [IO.Path]::GetFullPath($scratch)
$renulusExternalRoot = $renulusAuthorizedRoot
$externalRoot = $renulusAuthorizedRoot
Require-Refusal { Assert-DeliveryRoot (Join-Path $scratch 'deliveries/linked') }
Require-Refusal { Assert-PublicGeneratedPath (Join-Path $scratch 'temporary/link/never-created') }
Require-Refusal { Assert-OwnedReleasePath (Join-Path $scratch 'temporary/link/never-created') }
[pscustomobject]@{Status='passed'; RelocationRefusals=$refusals; OutputRoot=$expectedRoot; NamedRoot=$namedRoot; SyntheticJunctionRoot=$scratch; AppOrInstallerInvoked=$false; DeliveryOutputCreated=$false} | ConvertTo-Json -Compress
