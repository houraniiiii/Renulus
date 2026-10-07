[CmdletBinding()]
param(
    [string]$UserDataDirectory = '',
    [switch]$AccessibilityTesting,
    [switch]$CheckOnly,
    [switch]$ShowErrorDialog
)

# Optional archived reference only; the normal launcher opens the learning app.
$ErrorActionPreference = 'Stop'
$WorkspaceRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$PointerPath = Join-Path $WorkspaceRoot '.local/legacy-preview.json'

try {
    if (-not (Test-Path -LiteralPath $PointerPath -PathType Leaf)) {
        throw 'No local inherited reference preview is configured. Set archiveRoot in the ignored .local/legacy-preview.json to the preserved archive folder. A fresh Renulus clone contains no inherited application or runtime.'
    }
    try {
        $Pointer = Get-Content -LiteralPath $PointerPath -Raw | ConvertFrom-Json -ErrorAction Stop
    } catch {
        throw 'The ignored .local/legacy-preview.json must be valid JSON with an archiveRoot string.'
    }
    if ($Pointer -isnot [pscustomobject] -or $Pointer.archiveRoot -isnot [string] -or
        [string]::IsNullOrWhiteSpace($Pointer.archiveRoot)) {
        throw 'The ignored .local/legacy-preview.json must contain a nonempty archiveRoot string.'
    }
    if ($Pointer.archiveRoot -notmatch '^[A-Za-z]:[\/]' -or
        $Pointer.archiveRoot -match '[\x00-\x1f]') {
        throw 'archiveRoot must be an absolute local Windows folder path.'
    }
    $ArchiveRoot = [IO.Path]::GetFullPath($Pointer.archiveRoot).TrimEnd([char[]]'\/')
    $WorkspacePrefix = $WorkspaceRoot.TrimEnd([char[]]'\/') + [IO.Path]::DirectorySeparatorChar
    if ($ArchiveRoot.Equals($WorkspaceRoot, [StringComparison]::OrdinalIgnoreCase) -or
        $ArchiveRoot.StartsWith($WorkspacePrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'The inherited archive must stay outside the active Renulus workspace.'
    }
    if (-not (Test-Path -LiteralPath $ArchiveRoot -PathType Container)) {
        throw 'The configured inherited archive folder is missing. Restore or update the local archive pointer; this launcher never downloads or builds the application.'
    }
    $ArchiveLauncher = Join-Path $ArchiveRoot 'integrations/desktop/start-renulus.ps1'
    if (-not (Test-Path -LiteralPath $ArchiveLauncher -PathType Leaf)) {
        throw 'The inherited archive has no integrations/desktop/start-renulus.ps1. Point archiveRoot at the complete preserved baseline.'
    }

    # Inspect the script interface without executing the inherited application.
    $LauncherTokens = $null
    $LauncherErrors = $null
    $LauncherAst = [Management.Automation.Language.Parser]::ParseFile(
        $ArchiveLauncher, [ref]$LauncherTokens, [ref]$LauncherErrors)
    if ($LauncherErrors.Count -gt 0) {
        throw 'The archived launcher cannot be parsed. Restore the preserved launcher before opening the reference preview.'
    }
    $LauncherParameters = @($LauncherAst.ParamBlock.Parameters |
        ForEach-Object { $_.Name.VariablePath.UserPath })
    if ($LauncherParameters -notcontains 'UserDataDirectory' -or
        $LauncherParameters -notcontains 'AccessibilityTesting') {
        throw 'The archived launcher does not support the expected UserDataDirectory and AccessibilityTesting options.'
    }
    if ($CheckOnly) {
        Write-Output 'Renulus inherited reference preview: archive pointer and launcher interface checked. No application was started; build and runtime readiness were not tested.'
        exit 0
    }

    $InheritedParameters = @{}
    if ($PSBoundParameters.ContainsKey('UserDataDirectory')) {
        $InheritedParameters.UserDataDirectory = $UserDataDirectory
    }
    if ($PSBoundParameters.ContainsKey('AccessibilityTesting')) {
        $InheritedParameters.AccessibilityTesting = [bool]$AccessibilityTesting
    }
    Write-Output 'Opening Renulus inherited reference preview (archived clinical MVP). The independent learning application remains pending.'
    # The inherited script supplies --renulus-source-preview to Electron.
    # CheckOnly belongs to this wrapper and is never passed to that script.
    & $ArchiveLauncher @InheritedParameters
    if (-not $?) {
        throw 'The inherited reference launcher reported a failure.'
    }
    exit 0
} catch {
    [Console]::Error.WriteLine('Renulus inherited reference preview: ' + $_.Exception.Message)
    if ($ShowErrorDialog -and -not $CheckOnly) {
        try {
            Add-Type -AssemblyName System.Windows.Forms
            [void][System.Windows.Forms.MessageBox]::Show(
                'Inherited reference preview unavailable. See docs/WORKSPACE.md in the Renulus workspace for the local archive setup.',
                'Renulus inherited reference preview',
                [System.Windows.Forms.MessageBoxButtons]::OK,
                [System.Windows.Forms.MessageBoxIcon]::Warning)
        } catch {
            [Console]::Error.WriteLine('Renulus inherited reference preview: the error dialog could not be shown.')
        }
    }
    exit 1
}
