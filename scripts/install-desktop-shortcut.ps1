[CmdletBinding()]
param([string]$PreviousWorkspaceRoot = '')

$ErrorActionPreference = 'Stop'
$WorkspaceRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$LaunchScript = Join-Path $PSScriptRoot 'start-renulus.ps1'
$IconPath = Join-Path $WorkspaceRoot 'assets/brand/renulus.ico'
$DesktopDirectory = [Environment]::GetFolderPath('DesktopDirectory')
$ShortcutPath = Join-Path $DesktopDirectory 'Renulus.lnk'
$PowerShellPath = Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe'
$OldOwnedScript = [IO.Path]::GetFullPath((Join-Path (Split-Path $WorkspaceRoot -Parent) 'nephro-agent-os/integrations/desktop/start-renulus.ps1'))
$ShortcutShell = $null
$Shortcut = $null

try {
    $OwnedScripts = @($LaunchScript, $OldOwnedScript)
    if (-not [string]::IsNullOrWhiteSpace($PreviousWorkspaceRoot)) {
        if ($PreviousWorkspaceRoot -notmatch '^[A-Za-z]:[\\/]' -or
            $PreviousWorkspaceRoot -match '[\x00-\x1f]') {
            throw 'PreviousWorkspaceRoot must be an absolute local Windows folder path.'
        }
        $PreviousRoot = [IO.Path]::GetFullPath($PreviousWorkspaceRoot)
        $OwnedScripts += Join-Path $PreviousRoot 'scripts/start-renulus.ps1'
    }
    if (-not (Test-Path -LiteralPath $LaunchScript -PathType Leaf) -or
        -not (Test-Path -LiteralPath $IconPath -PathType Leaf)) {
        throw 'The Renulus wrapper and selected assets/brand/renulus.ico must exist before installing the shortcut.'
    }
    if (-not (Test-Path -LiteralPath $DesktopDirectory -PathType Container)) {
        throw 'The Windows desktop folder is unavailable.'
    }
    $Updating = Test-Path -LiteralPath $ShortcutPath -PathType Leaf
    $ShortcutShell = New-Object -ComObject WScript.Shell
    $Shortcut = $ShortcutShell.CreateShortcut($ShortcutPath)
    if ($Updating) {
        $FileArgument = [regex]::Match($Shortcut.Arguments, '(?i)(?:^|\s)-File\s+(?:"([^"]+)"|(\S+))')
        $ExistingScript = if ($FileArgument.Groups[1].Success) { $FileArgument.Groups[1].Value }
            else { $FileArgument.Groups[2].Value }
        if (-not $FileArgument.Success -or -not [IO.Path]::IsPathRooted($ExistingScript)) {
            throw 'The existing Renulus shortcut is unrelated to the owned launchers and was left unchanged.'
        }
        $ExistingScript = [IO.Path]::GetFullPath($ExistingScript)
        $OwnedMatch = @($OwnedScripts | Where-Object {
            $ExistingScript.Equals($_, [StringComparison]::OrdinalIgnoreCase)
        }).Count -gt 0
        if (-not $Shortcut.TargetPath.Equals($PowerShellPath, [StringComparison]::OrdinalIgnoreCase) -or
            -not $OwnedMatch) {
            throw 'The existing Renulus shortcut is unrelated to the owned launchers and was left unchanged.'
        }
    }
    $Shortcut.TargetPath = $PowerShellPath
    $Shortcut.Arguments = '-NoLogo -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $LaunchScript + '" -ShowErrorDialog'
    $Shortcut.WorkingDirectory = $WorkspaceRoot
    $Shortcut.IconLocation = $IconPath + ',0'
    $Shortcut.Description = 'Renulus - nephrology learning'
    $Shortcut.WindowStyle = 7
    $Shortcut.Save()
    $Action = if ($Updating) { 'Updated' } else { 'Created' }
    Write-Output ($Action + ' Renulus.lnk for the learning app and selected icon.')
} catch {
    [Console]::Error.WriteLine('Renulus shortcut: ' + $_.Exception.Message)
    exit 1
} finally {
    if ($null -ne $Shortcut) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($Shortcut) }
    if ($null -ne $ShortcutShell) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($ShortcutShell) }
}
