param(
    [Parameter(Mandatory = $true)][string]$WorkspaceRoot,
    [int]$IntervalMinutes = 30
)
$ErrorActionPreference = 'Stop'
$runRoot = (Resolve-Path -LiteralPath $WorkspaceRoot).Path
$statePath = Join-Path $runRoot '.local/implementation-run.json'
$initialState = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
$nextAt = [DateTimeOffset]::Parse($initialState.started_utc).AddMinutes($IntervalMinutes)
while ($nextAt -le [DateTimeOffset]::UtcNow) { $nextAt = $nextAt.AddMinutes($IntervalMinutes) }
while (Test-Path -LiteralPath $statePath) {
    $runState = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
    if (-not $runState.active) { break }
    if ([DateTimeOffset]::UtcNow -gt [DateTimeOffset]::Parse($runState.deadline_utc)) { break }
    if ([DateTimeOffset]::UtcNow -ge $nextAt) {
        Push-Location -LiteralPath $runRoot
        try {
            & python scripts/implementation_queue.py heartbeat
        } finally { Pop-Location }
        $nextAt = $nextAt.AddMinutes($IntervalMinutes)
    }
    Start-Sleep -Seconds 15
}
