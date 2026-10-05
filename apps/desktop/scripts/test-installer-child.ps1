[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'installer-child.ps1')
$beforeTemp, $beforeTmp = $env:TEMP, $env:TMP
$proofRoot = [IO.Path]::GetFullPath('E:/Renulus-native-delivery/desktop-20261005')
$temporary = Join-Path $proofRoot ('temporary/child-environment-' + [Guid]::NewGuid().ToString('N'))
$cursor = $temporary
while ($cursor) {
    if (Test-Path -LiteralPath $cursor) {
        if (((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Synthetic child proof may not traverse a reparse path.' }
    }
    $cursor = Split-Path -Parent $cursor
}
New-Item -ItemType Directory -Path $temporary | Out-Null
$childScript = @'
$ErrorActionPreference = 'Stop'
$actualTemporary = [IO.Path]::GetTempPath()
$marker = Join-Path $actualTemporary 'synthetic-child.txt'
[IO.File]::WriteAllText($marker, 'synthetic installer environment proof')
[ordered]@{ temp = $env:TEMP; tmp = $env:TMP; temporary = $actualTemporary; marker = $marker } | ConvertTo-Json -Compress
'@
$encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($childScript))
$shellExecutable = (Get-Process -Id $PID).Path
$info = New-InstallerChildInfo $shellExecutable ('-NoProfile -NonInteractive -EncodedCommand ' + $encoded) $temporary
$info.RedirectStandardOutput = $true
$info.RedirectStandardError = $true
$child = [Diagnostics.Process]::Start($info)
$stdout = $child.StandardOutput.ReadToEnd()
$stderr = $child.StandardError.ReadToEnd()
$child.WaitForExit()
if ($child.ExitCode -ne 0) { throw ('Synthetic child failed: ' + $stderr) }
$observed = $stdout | ConvertFrom-Json
foreach ($path in @($observed.temp, $observed.tmp, $observed.temporary)) {
    if ([IO.Path]::GetFullPath($path).TrimEnd([IO.Path]::DirectorySeparatorChar) -ne $temporary) { throw 'Child scratch environment escaped its reserved folder.' }
}
if ($env:TEMP -ne $beforeTemp -or $env:TMP -ne $beforeTmp) { throw 'The host temporary environment changed.' }
if ((Get-Content -LiteralPath $observed.marker -Raw) -ne 'synthetic installer environment proof') { throw 'The child did not write its scratch file in the assigned E folder.' }
$report = [ordered]@{ kind = 'actual-child-temporary-environment'; shell = $shellExecutable; shellVersion = $PSVersionTable.PSVersion.ToString(); childExitCode = $child.ExitCode; observed = $observed; hostEnvironmentUnchanged = $true; limits = @('Synthetic process only; actual NSIS execution remains a separate gate') }
$report | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $temporary 'evidence.json') -Encoding utf8
$report | ConvertTo-Json -Depth 5
