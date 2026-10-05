$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'restage-delivery.ps1')
$script:renulusRefusals = 0
function Expect-Refusal([scriptblock]$Action, [string]$Message) {
    try { & $Action | Out-Null } catch { $script:renulusRefusals += 1; return }
    throw ('Expected refusal: ' + $Message)
}
$newRevision = 'a5488b2df636d5b45d945e611e6c6a61436a92c2'
Assert-RestageGate $newRevision 'Plan' $false $false
Expect-Refusal { Assert-RestageGate 'HEAD' 'Plan' $false $false } 'moving revision'
Expect-Refusal { Assert-RestageGate $renulusPreviousRevision 'Package' $true $true } 'previous frozen product'
foreach ($action in @('Package', 'Install', 'Proof')) {
    Expect-Refusal { Assert-RestageGate $newRevision $action $false $true } 'unaccepted freeze'
}
Expect-Refusal { Assert-RestageGate $newRevision 'Proof' $true $false } 'occupied native slot'
Assert-RestageGate $newRevision 'Proof' $true $true
foreach ($path in @('E:/Renulus-native-delivery/desktop-20261005/data/learning', 'E:/Renulus-native-delivery/desktop-20261005/repo/new-output', 'E:/Renulus-native-delivery/desktop-20261005-other/proofs/new', 'C:/unexpected-output', 'E:/Renulus-native-delivery/desktop-20261005/proofs/../../escape')) {
    Expect-Refusal { Assert-PublicGeneratedPath $path } 'private, source or escaped output'
}
$testRoot = Assert-PublicGeneratedPath (Join-Path $renulusExternalRoot ('temporary/restage-tests-' + [Guid]::NewGuid().ToString('N'))) -Fresh
New-Item -ItemType Directory -Path $testRoot | Out-Null
$sentinel = Join-Path $testRoot 'synthetic-checkpoint.txt'
[IO.File]::WriteAllText($sentinel, 'synthetic-public-checkpoint')
Expect-Refusal { Assert-PublicGeneratedPath $testRoot -Fresh } 'existing checkpoint'
if ([IO.File]::ReadAllText($sentinel) -ne 'synthetic-public-checkpoint') { throw 'Checkpoint changed during refusal.' }
$newPath = Join-Path $testRoot 'fresh-output'
$null = Assert-PublicGeneratedPath $newPath -Fresh
if (Test-Path -LiteralPath $newPath) { throw 'Path check created an output.' }
[pscustomobject]@{Status='passed'; BoundaryRefusals=$renulusRefusals; AcceptedPlan=$true; AcceptedReleasedProof=$true; PreservedSyntheticCheckpoint=$true; NoOutputFromPathCheck=$true; SyntheticFixture=$testRoot; AppOrBuildInvoked=$false} | ConvertTo-Json -Compress
