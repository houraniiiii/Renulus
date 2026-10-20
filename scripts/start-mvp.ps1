[CmdletBinding()]
param(
    [Alias('Profile', 'ProfilePath')]
    [string]$UserDataDirectory = '',
    [switch]$AccessibilityTesting,
    [switch]$CheckOnly,
    [switch]$ShowErrorDialog
)

$ErrorActionPreference = 'Stop'
$renulusWorkspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$renulusDesktop = Join-Path $renulusWorkspace 'apps/desktop'
$renulusExecutable = Join-Path $renulusDesktop 'node_modules/electron/dist/electron.exe'
$renulusVenvPython = Join-Path $renulusWorkspace '.venv/Scripts/python.exe'

try {
    foreach ($renulusRequired in @('dist/index.html', 'dist-electron/main.cjs')) {
        if (-not (Test-Path -LiteralPath (Join-Path $renulusDesktop $renulusRequired) -PathType Leaf)) {
            throw 'Build apps/desktop with npm run build before starting the MVP source app.'
        }
    }
    if (-not (Test-Path -LiteralPath $renulusExecutable -PathType Leaf)) {
        throw 'The Electron executable is missing under apps/desktop/node_modules.'
    }
    $renulusPython = if (-not [string]::IsNullOrWhiteSpace($env:RENULUS_PYTHON)) {
        [IO.Path]::GetFullPath($env:RENULUS_PYTHON)
    } else {
        $renulusVenvPython
    }
    if (-not [IO.Path]::IsPathRooted($renulusPython) -or
        -not (Test-Path -LiteralPath $renulusPython -PathType Leaf)) {
        throw 'The contributor Python runtime (.venv/Scripts/python.exe) is missing.'
    }
    if ([string]::IsNullOrWhiteSpace($UserDataDirectory)) {
        $UserDataDirectory = if (-not [string]::IsNullOrWhiteSpace($env:RENULUS_PROFILE)) {
            $env:RENULUS_PROFILE
        } else {
            Join-Path $renulusWorkspace '.local/runtime/desktop-user'
        }
    }
    if (-not [IO.Path]::IsPathRooted($UserDataDirectory) -or $UserDataDirectory -match '[\x00-\x1f]') {
        throw 'Choose an absolute local folder for this learning profile.'
    }
    $UserDataDirectory = [IO.Path]::GetFullPath($UserDataDirectory)
    if ($UserDataDirectory -eq [IO.Path]::GetPathRoot($UserDataDirectory)) {
        throw 'The learning profile cannot be a drive root.'
    }
    $renulusArguments = @('"' + $renulusDesktop + '"')
    if ($AccessibilityTesting) { $renulusArguments += '--force-renderer-accessibility' }
    if ($CheckOnly) {
        Write-Output ('Renulus MVP source launcher checked: ' + $renulusExecutable)
        Write-Output ('Profile: ' + $UserDataDirectory)
        Write-Output ('Python: ' + $renulusPython)
        Write-Output 'No application was launched. Runtime and account availability require an app run.'
        exit 0
    }
    $env:RENULUS_PROFILE = $UserDataDirectory
    $env:RENULUS_PYTHON = $renulusPython
    Remove-Item Env:ELECTRON_RUN_AS_NODE -ErrorAction SilentlyContinue
    Remove-Item Env:RENULUS_BACKEND_URL -ErrorAction SilentlyContinue
    Remove-Item Env:RENULUS_BACKGROUND_HARNESS_SETTINGS -ErrorAction SilentlyContinue
    Remove-Item Env:RENULUS_BACKGROUND_HARNESS_LEARNING -ErrorAction SilentlyContinue
    $renulusLaunch = @{
        FilePath = $renulusExecutable
        WorkingDirectory = $renulusWorkspace
        WindowStyle = 'Normal'
        PassThru = $true
        ArgumentList = $renulusArguments
    }
    $renulusProcess = Start-Process @renulusLaunch
    Write-Output ('Opened Renulus MVP learning app (process ' + $renulusProcess.Id + ').')
    exit 0
} catch {
    [Console]::Error.WriteLine('Renulus: ' + $_.Exception.Message)
    if ($ShowErrorDialog -and -not $CheckOnly) {
        try {
            Add-Type -AssemblyName System.Windows.Forms
            [void][System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'Renulus could not start')
        } catch { [Console]::Error.WriteLine('Renulus startup details are available in this launcher output.') }
    }
    exit 1
}
