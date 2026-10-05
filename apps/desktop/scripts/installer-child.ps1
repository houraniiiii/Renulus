# Use a per-child environment on both Windows PowerShell and PowerShell 7.
function New-InstallerChildInfo([string]$Executable, [string]$Arguments, [string]$TemporaryDirectory) {
    $info = New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName = $Executable
    $info.Arguments = $Arguments
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.WindowStyle = [Diagnostics.ProcessWindowStyle]::Hidden
    $info.EnvironmentVariables['TEMP'] = $TemporaryDirectory
    $info.EnvironmentVariables['TMP'] = $TemporaryDirectory
    return $info
}
