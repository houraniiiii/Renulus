[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][int]$AppProcessId,
    [Parameter(Mandatory = $true)][string]$ExpectedExecutable,
    [Parameter(Mandatory = $true)][ValidateSet('save', 'cancel')][string]$Action,
    [Parameter(Mandatory = $true)][string]$Target,
    [Parameter(Mandatory = $true)][string]$EvidencePath,
    [string]$DialogTitle = 'Save your Renulus backup'
)
$ErrorActionPreference = 'Stop'
$desktopRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$testRoot = [IO.Path]::GetFullPath((Join-Path $desktopRoot 'test-results'))
foreach ($outputPath in @($Target, $EvidencePath)) {
    $absolute = [IO.Path]::GetFullPath($outputPath)
    if (-not [IO.Path]::IsPathRooted($outputPath) -or -not $absolute.StartsWith($testRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Dialog output must stay in this lane test-results.' }
    $cursor = Split-Path -Parent $absolute
    while ($cursor.Length -ge $testRoot.Length) {
        if ((Test-Path -LiteralPath $cursor) -and ((Get-Item -LiteralPath $cursor).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Dialog target may not traverse a reparse path.' }
        $cursor = Split-Path -Parent $cursor
    }
}
$owner = Get-Process -Id $AppProcessId -ErrorAction Stop
if (-not [IO.Path]::GetFullPath($owner.Path).Equals([IO.Path]::GetFullPath($ExpectedExecutable), [StringComparison]::OrdinalIgnoreCase)) { throw 'The PID does not own the expected proof executable.' }
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName System.Drawing
Add-Type -TypeDefinition @'
using System; using System.Text; using System.Runtime.InteropServices;
public static class OwnedSaveDialogWindow {
  public delegate bool WindowCallback(IntPtr window, IntPtr parameter);
  [DllImport("user32.dll")] public static extern bool EnumWindows(WindowCallback callback, IntPtr parameter);
  [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr parent, WindowCallback callback, IntPtr parameter);
  [DllImport("user32.dll")] public static extern int GetDlgCtrlID(IntPtr window);
  [DllImport("user32.dll")] public static extern IntPtr GetParent(IntPtr window);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr window);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr window, StringBuilder value, int capacity);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr window, StringBuilder value, int capacity);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr window);
  [DllImport("user32.dll")] public static extern IntPtr SetActiveWindow(IntPtr window);
  [DllImport("user32.dll")] public static extern bool AttachThreadInput(uint first, uint second, bool attach);
  [DllImport("kernel32.dll")] public static extern uint GetCurrentThreadId();
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr window, out uint process);
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr window, uint message, IntPtr wParam, IntPtr lParam);
  [DllImport("user32.dll", CharSet=CharSet.Unicode, EntryPoint="SendMessageW")] public static extern IntPtr ReadText(IntPtr window, uint message, IntPtr capacity, StringBuilder text);
  [DllImport("user32.dll", EntryPoint="SendMessageW")] public static extern IntPtr SendMessage(IntPtr window, uint message, IntPtr wParam, IntPtr lParam);
  public static IntPtr FindOwnedDialog(uint owner, string title) {
    IntPtr found=IntPtr.Zero;
    EnumWindows((window,parameter)=>{
      uint process; GetWindowThreadProcessId(window,out process);
      if(process!=owner) return true;
      var kind=new StringBuilder(128); GetClassName(window,kind,128);
      if(kind.ToString()!="#32770") return true;
      var caption=new StringBuilder(256); GetWindowText(window,caption,256);
      if(caption.ToString()!=title) return true;
      found=window; return false;
    },IntPtr.Zero);
    return found;
  }
  public static IntPtr FindChild(IntPtr parent, uint owner, int identifier, string requiredClass) {
    IntPtr found=IntPtr.Zero;
    EnumChildWindows(parent,(window,parameter)=>{
      uint process; GetWindowThreadProcessId(window,out process);
      if(process!=owner || GetDlgCtrlID(window)!=identifier) return true;
      var kind=new StringBuilder(128); GetClassName(window,kind,128);
      if(kind.ToString()!=requiredClass) return true;
      found=window; return false;
    },IntPtr.Zero);
    return found;
  }
  public static string[] ChildMetadata(IntPtr parent, uint owner) {
    var values=new System.Collections.Generic.List<string>();
    EnumChildWindows(parent,(window,parameter)=>{
      uint process; GetWindowThreadProcessId(window,out process);
      if(process!=owner) return true;
      var kind=new StringBuilder(128); GetClassName(window,kind,128);
      var ancestor=GetParent(window); var ancestorKind=new StringBuilder(128); GetClassName(ancestor,ancestorKind,128);
      values.Add(kind.ToString()+" id="+GetDlgCtrlID(window)+" parent="+ancestorKind.ToString()+"/"+GetDlgCtrlID(ancestor)+" visible="+IsWindowVisible(window)+" handle="+window.ToInt64());
      return true;
    },IntPtr.Zero);
    return values.ToArray();
  }
  public static IntPtr FindCaptionButton(IntPtr parent, uint owner, string caption) {
    IntPtr found=IntPtr.Zero;
    EnumChildWindows(parent,(window,parameter)=>{
      uint process; GetWindowThreadProcessId(window,out process);
      if(process!=owner || !IsWindowVisible(window)) return true;
      var kind=new StringBuilder(128); GetClassName(window,kind,128);
      if(kind.ToString()!="Button") return true;
      var label=new StringBuilder(256); ReadText(window,0x000D,new IntPtr(256),label);
      if(label.ToString().Replace("&","").Trim()!=caption) return true;
      found=window; return false;
    },IntPtr.Zero);
    return found;
  }
}
'@
$report = [ordered]@{ kind = 'actual-owned-native-save-dialog'; appProcessId = $AppProcessId; action = $Action; dialogFound = $false; screenshot = 'not captured' }
$dialog = $null
function Find-Control($Root, [string]$Identifier) {
    return $Root.FindFirst([System.Windows.Automation.TreeScope]::Descendants, (New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::AutomationIdProperty, $Identifier)))
}
function Invoke-Control($Control) {
    if ($null -eq $Control) { throw 'Required native dialog control is unavailable.' }
    $pattern = $null
    if ($Control.Current.ControlType -eq [System.Windows.Automation.ControlType]::Button -and $Control.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern, [ref]$pattern)) { $pattern.Invoke(); return }
    $controlHandle = [IntPtr]$Control.Current.NativeWindowHandle
    [uint32]$controlOwner = 0
    [OwnedSaveDialogWindow]::GetWindowThreadProcessId($controlHandle, [ref]$controlOwner) | Out-Null
    $class = New-Object Text.StringBuilder(128)
    [OwnedSaveDialogWindow]::GetClassName($controlHandle, $class, 128) | Out-Null
    if ($controlOwner -eq $AppProcessId -and $class.ToString() -eq 'Button') {
        [OwnedSaveDialogWindow]::PostMessage($controlHandle, 0x00F5, [IntPtr]::Zero, [IntPtr]::Zero) | Out-Null; return
    }
    if ($Control.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern, [ref]$pattern)) { $pattern.Invoke(); return }
    throw 'The owned dialog control cannot be invoked safely.'
}
function Find-Dialog {
    $ownedHandle = [OwnedSaveDialogWindow]::FindOwnedDialog($AppProcessId, $DialogTitle)
    if ($ownedHandle -eq [IntPtr]::Zero) { return $null }
    return [System.Windows.Automation.AutomationElement]::FromHandle($ownedHandle)
}
try {
    $deadline = [DateTime]::UtcNow.AddSeconds(20)
    do { $dialog = Find-Dialog; if ($null -eq $dialog) { Start-Sleep -Milliseconds 100 } } while ($null -eq $dialog -and [DateTime]::UtcNow -lt $deadline)
    if ($null -eq $dialog) { throw 'The expected app-owned Windows Save dialog did not appear.' }
    $handle = [IntPtr]$dialog.Current.NativeWindowHandle
    [uint32]$nativeOwner = 0
    [OwnedSaveDialogWindow]::GetWindowThreadProcessId($handle, [ref]$nativeOwner) | Out-Null
    if ($nativeOwner -ne $AppProcessId) { throw 'Native dialog ownership changed.' }
    $report.dialogFound = $true; $report.nativeHandle = $handle.ToInt64()
    if ($Action -eq 'cancel') {
        $cancelHandle = [OwnedSaveDialogWindow]::FindChild($handle, $AppProcessId, 2, 'Button')
        $cancel = if ($cancelHandle -ne [IntPtr]::Zero) { [System.Windows.Automation.AutomationElement]::FromHandle($cancelHandle) } else { Find-Control $dialog '2' }
        Invoke-Control $cancel; $report.invoked = 'cancel'
    } else {
        $comboHandle = [OwnedSaveDialogWindow]::FindChild($handle, $AppProcessId, 1148, 'ComboBox')
        $combo = if ($comboHandle -ne [IntPtr]::Zero) { [System.Windows.Automation.AutomationElement]::FromHandle($comboHandle) } else { Find-Control $dialog '1148' }
        $editHandle = if ($comboHandle -ne [IntPtr]::Zero) { [OwnedSaveDialogWindow]::FindChild($comboHandle, $AppProcessId, 1001, 'Edit') } else { [IntPtr]::Zero }
        if ($editHandle -eq [IntPtr]::Zero) {
            # Current Windows uses an unnumbered ComboBox for the filename.
            $candidate = [OwnedSaveDialogWindow]::FindChild($handle, $AppProcessId, 1001, 'Edit')
            if ($candidate -ne [IntPtr]::Zero -and [OwnedSaveDialogWindow]::IsWindowVisible($candidate)) {
                $candidateParent = [OwnedSaveDialogWindow]::GetParent($candidate)
                $parentClass = New-Object Text.StringBuilder(128)
                [OwnedSaveDialogWindow]::GetClassName($candidateParent, $parentClass, 128) | Out-Null
                if ($parentClass.ToString() -eq 'ComboBox' -and [OwnedSaveDialogWindow]::GetDlgCtrlID($candidateParent) -in @(0,1148)) { $editHandle = $candidate; $comboHandle = $candidateParent }
            }
        }
        $edit = if ($editHandle -ne [IntPtr]::Zero) { [System.Windows.Automation.AutomationElement]::FromHandle($editHandle) } elseif ($combo) { Find-Control $combo '1001' } else { $null }
        if ($null -eq $edit) {
            $report.nativeControlMetadata = [OwnedSaveDialogWindow]::ChildMetadata($handle, $AppProcessId)
            # Record identifiers/types only; never read folder names or field values.
            $metadata = @()
            foreach ($control in $dialog.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)) {
                $current = $control.Current
                if ($current.ControlType -in @([System.Windows.Automation.ControlType]::Edit, [System.Windows.Automation.ControlType]::ComboBox, [System.Windows.Automation.ControlType]::Button)) {
                    $metadata += [ordered]@{ id = $current.AutomationId; class = $current.ClassName; type = $current.ControlType.ProgrammaticName; handle = $current.NativeWindowHandle }
                }
            }
            $report.controlMetadata = $metadata
            throw 'Native filename edit 1001 under combo 1148 was not found in the owned dialog.'
        }
        $report.filenameMetadata = [ordered]@{ id = $edit.Current.AutomationId; class = $edit.Current.ClassName; type = $edit.Current.ControlType.ProgrammaticName; handle = $edit.Current.NativeWindowHandle }
        $report.step = 'setting-filename'
        $valuePattern = $null
        if ($edit.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern, [ref]$valuePattern)) {
            $valuePattern.SetValue([IO.Path]::GetFullPath($Target)); $report.filenameMethod = 'UIA ValuePattern'
        } else {
            $editHandle = [IntPtr]$edit.Current.NativeWindowHandle
            [uint32]$editOwner = 0
            [OwnedSaveDialogWindow]::GetWindowThreadProcessId($editHandle, [ref]$editOwner) | Out-Null
            $editClass = New-Object Text.StringBuilder(128)
            [OwnedSaveDialogWindow]::GetClassName($editHandle, $editClass, 128) | Out-Null
            if ($editOwner -ne $AppProcessId -or $editClass.ToString() -ne 'Edit') { throw 'The native filename lacks both a supported ValuePattern and an owned Edit handle.' }
            # WM_SETTEXT alone does not update this modern dialog's filename cache.
            # Type into its own Edit control, so the ComboBox receives edit changes.
            [OwnedSaveDialogWindow]::SendMessage($editHandle, 0x00B1, [IntPtr]::Zero, [IntPtr](-1)) | Out-Null
            foreach ($character in [IO.Path]::GetFullPath($Target).ToCharArray()) {
                [OwnedSaveDialogWindow]::SendMessage($editHandle, 0x0102, [IntPtr][int]$character, [IntPtr]1) | Out-Null
            }
            $confirmed = New-Object Text.StringBuilder(32768)
            [OwnedSaveDialogWindow]::ReadText($editHandle, 0x000D, [IntPtr]32768, $confirmed) | Out-Null
            if ($confirmed.ToString() -ne [IO.Path]::GetFullPath($Target)) { throw 'The synthetic filename was not accepted by the native Edit control.' }
            $report.filenameMethod = 'owned Win32 Edit EM_SETSEL/WM_CHAR'
        }
        $saveHandle = [OwnedSaveDialogWindow]::FindChild($handle, $AppProcessId, 1, 'Button')
        $save = if ($saveHandle -ne [IntPtr]::Zero) { [System.Windows.Automation.AutomationElement]::FromHandle($saveHandle) } else { Find-Control $dialog '1' }
        if ($null -eq $save) { throw 'Native Save button 1 was not found.' }
        # Capture only the filename/buttons strip; folder listings are excluded.
        $ownThread = [OwnedSaveDialogWindow]::GetCurrentThreadId()
        [uint32]$unusedOwner = 0
        $dialogThread = [OwnedSaveDialogWindow]::GetWindowThreadProcessId($handle, [ref]$unusedOwner)
        [OwnedSaveDialogWindow]::AttachThreadInput($ownThread, $dialogThread, $true) | Out-Null
        try { [OwnedSaveDialogWindow]::SetActiveWindow($handle) | Out-Null; [OwnedSaveDialogWindow]::SetForegroundWindow($handle) | Out-Null }
        finally { [OwnedSaveDialogWindow]::AttachThreadInput($ownThread, $dialogThread, $false) | Out-Null }
        Start-Sleep -Milliseconds 100
        if ([OwnedSaveDialogWindow]::GetForegroundWindow() -eq $handle) {
            $fieldRect = $edit.Current.BoundingRectangle; $buttonRect = $save.Current.BoundingRectangle
            $left = [int][Math]::Min($fieldRect.Left, $buttonRect.Left); $top = [int][Math]::Min($fieldRect.Top, $buttonRect.Top)
            $right = [int][Math]::Max($fieldRect.Right, $buttonRect.Right); $bottom = [int][Math]::Max($fieldRect.Bottom, $buttonRect.Bottom)
            $bitmap = New-Object Drawing.Bitmap(($right - $left), ($bottom - $top))
            $graphics = [Drawing.Graphics]::FromImage($bitmap)
            try { $graphics.CopyFromScreen($left, $top, 0, 0, $bitmap.Size); $bitmap.Save($EvidencePath + '-filename.png', [Drawing.Imaging.ImageFormat]::Png); $report.screenshot = 'owned filename/save strip' }
            finally { $graphics.Dispose(); $bitmap.Dispose() }
        }
        $report.step = 'invoking-save'
        Invoke-Control $save; $report.invoked = 'save'; $report.filenameControl = 'owned ComboBox/' + [OwnedSaveDialogWindow]::GetDlgCtrlID($comboHandle) + '/Edit1001'
        if (Test-Path -LiteralPath $Target) {
            # Only this synthetic target can produce an overwrite confirmation.
            $confirm = $null; $confirmDeadline = [DateTime]::UtcNow.AddSeconds(5)
            do { $confirmHandle = [OwnedSaveDialogWindow]::FindOwnedDialog($AppProcessId, 'Confirm Save As'); if ($confirmHandle -ne [IntPtr]::Zero) { $confirm = [System.Windows.Automation.AutomationElement]::FromHandle($confirmHandle) } else { Start-Sleep -Milliseconds 100 } } while ($null -eq $confirm -and [DateTime]::UtcNow -lt $confirmDeadline)
            if ($confirm) {
                $report.step = 'confirming-synthetic-overwrite'
                $yes = $confirm.FindFirst([System.Windows.Automation.TreeScope]::Descendants, (New-Object System.Windows.Automation.AndCondition(
                    (New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::Button)),
                    (New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty, 'Yes'))
                )))
                $yesHandle = [OwnedSaveDialogWindow]::FindChild($confirmHandle, $AppProcessId, 6, 'Button')
                if ($yesHandle -eq [IntPtr]::Zero) { $yesHandle = [OwnedSaveDialogWindow]::FindCaptionButton($confirmHandle, $AppProcessId, 'Yes') }
                if ($null -eq $yes) { $yes = if ($yesHandle -ne [IntPtr]::Zero) { [System.Windows.Automation.AutomationElement]::FromHandle($yesHandle) } else { Find-Control $confirm 'CommandButton_6' } }
                if ($null -eq $yes) { $report.overwriteControlMetadata = [OwnedSaveDialogWindow]::ChildMetadata($confirmHandle, $AppProcessId) }
                Invoke-Control $yes; $report.overwriteConfirmed = $true
                Start-Sleep -Milliseconds 200
                if ([OwnedSaveDialogWindow]::FindOwnedDialog($AppProcessId, 'Confirm Save As') -ne [IntPtr]::Zero) {
                    $report.overwriteAutomationMetadata = @($confirm.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition) | ForEach-Object { [ordered]@{ id = $_.Current.AutomationId; class = $_.Current.ClassName; type = $_.Current.ControlType.ProgrammaticName; handle = $_.Current.NativeWindowHandle } })
                    throw 'The actual overwrite confirmation remained open after the Yes operation.'
                }
            }
        }
    }
} catch {
    $report.error = $_.Exception.Message
    if ($dialog) { [OwnedSaveDialogWindow]::PostMessage([IntPtr]$dialog.Current.NativeWindowHandle, 0x0010, [IntPtr]::Zero, [IntPtr]::Zero) | Out-Null }
} finally {
    $report | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath ($EvidencePath + '.json') -Encoding UTF8
    $report | ConvertTo-Json -Depth 5
}
if ($report.error) { exit 1 }
