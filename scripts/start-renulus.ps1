[CmdletBinding()]
param(
    [string]$UserDataDirectory = '',
    [switch]$AccessibilityTesting,
    [switch]$CheckOnly,
    [switch]$ShowErrorDialog
)

$ErrorActionPreference = 'Stop'
$renulusWorkspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$renulusDesktop = Join-Path $renulusWorkspace 'apps/desktop'
$renulusDeliveryPath = Join-Path $renulusWorkspace '.local/delivery.json'

try {
    $renulusDelivery = $null
    if (Test-Path -LiteralPath $renulusDeliveryPath -PathType Leaf) {
        $renulusDelivery = Get-Content -LiteralPath $renulusDeliveryPath -Raw | ConvertFrom-Json
    }
    $renulusExecutable = $null
    $renulusArguments = @()
    if ($renulusDelivery -and $renulusDelivery.executable) {
        $renulusExecutable = [string]$renulusDelivery.executable
        if (-not [IO.Path]::IsPathRooted($renulusExecutable) -or
            [IO.Path]::GetFileName($renulusExecutable) -notmatch '^Renulus(?: Development)?[.]exe$') {
            throw 'The local delivery record must identify the built Renulus executable.'
        }
        if ([string]::IsNullOrWhiteSpace($UserDataDirectory) -and $renulusDelivery.profile) {
            $UserDataDirectory = [string]$renulusDelivery.profile
        }
    } else {
        $renulusExecutable = Join-Path $renulusDesktop 'node_modules/electron/dist/electron.exe'
        foreach ($renulusRequired in @('dist/index.html', 'dist-electron/main.cjs')) {
            if (-not (Test-Path -LiteralPath (Join-Path $renulusDesktop $renulusRequired) -PathType Leaf)) {
                throw 'Build apps/desktop with npm run build, or install the delivered Windows bundle first.'
            }
        }
        if (-not (Test-Path -LiteralPath (Join-Path $renulusWorkspace '.venv/Scripts/python.exe') -PathType Leaf)) {
            throw 'The contributor runtime is missing. Use the Windows bundle, or run uv sync for development.'
        }
        $renulusArguments = @('"' + $renulusDesktop + '"')
        if ([string]::IsNullOrWhiteSpace($UserDataDirectory)) {
            $UserDataDirectory = Join-Path $renulusWorkspace '.local/runtime/desktop-user'
        }
    }
    if (-not (Test-Path -LiteralPath $renulusExecutable -PathType Leaf)) {
        throw 'The Renulus executable is missing. Rebuild or restore the delivered bundle.'
    }
    if (-not [string]::IsNullOrWhiteSpace($UserDataDirectory)) {
        if (-not [IO.Path]::IsPathRooted($UserDataDirectory) -or $UserDataDirectory -match '[\x00-\x1f]') {
            throw 'Choose an absolute local folder for this learning profile.'
        }
        $UserDataDirectory = [IO.Path]::GetFullPath($UserDataDirectory)
        if ($UserDataDirectory -eq [IO.Path]::GetPathRoot($UserDataDirectory)) {
            throw 'The learning profile cannot be a drive root.'
        }
    }
    if ($AccessibilityTesting) { $renulusArguments += '--force-renderer-accessibility' }
    if ($CheckOnly) {
        Write-Output ('Renulus learning app launcher checked: ' + $renulusExecutable)
        Write-Output 'No application was launched. Runtime and account availability require an app run.'
        exit 0
    }
    if (-not [string]::IsNullOrWhiteSpace($UserDataDirectory)) {
        $env:RENULUS_PROFILE = $UserDataDirectory
    }
    Remove-Item Env:ELECTRON_RUN_AS_NODE -ErrorAction SilentlyContinue
    $renulusLaunch = @{ FilePath = $renulusExecutable; WorkingDirectory = $renulusWorkspace; WindowStyle = 'Hidden'; PassThru = $true }
    if ($renulusArguments.Count) { $renulusLaunch.ArgumentList = $renulusArguments }
    $renulusProcess = Start-Process @renulusLaunch
    Write-Output ('Opened Renulus learning app (process ' + $renulusProcess.Id + ').')
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
