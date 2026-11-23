# Golf bot machine guard. Runs every 5 minutes from Task Scheduler (task PMGolfBot-Guard).
# Checks: screen locked, LINE minimized/missing, low disk, nightly DB backup,
# new SKIPPED items, Healthchecks not configured. Alerts go out via guard_helper.py.
# ASCII only on purpose: Windows PowerShell 5.1 misreads UTF-8 files without BOM.
param([Parameter(Mandatory = $true)][string]$BotDir)

$ErrorActionPreference = 'Stop'
$MinFreeBytes = 2GB

$py = Join-Path $BotDir 'venv\Scripts\python.exe'
$helper = Join-Path $BotDir 'guard\guard_helper.py'
if (-not (Test-Path $py) -or -not (Test-Path $helper)) { exit 1 }

function Invoke-Helper {
    param([string[]]$HelperArgs)
    & $py -I $helper $BotDir @HelperArgs
}

Add-Type -Namespace PmGuard -Name Win -MemberDefinition @'
[DllImport("user32.dll")] public static extern bool IsIconic(System.IntPtr hWnd);
[DllImport("user32.dll")] public static extern bool ShowWindow(System.IntPtr hWnd, int nCmdShow);
'@

function Test-ScreenLocked {
    # LogonUI runs while the session is locked or at the sign-in screen.
    return [bool](Get-Process -Name LogonUI -ErrorAction SilentlyContinue)
}

function Restore-LineWindow {
    $line = @(Get-Process -Name LINE -ErrorAction SilentlyContinue)
    if ($line.Count -eq 0) { Invoke-Helper @('alert', 'line_missing'); return }
    foreach ($p in $line) {
        $h = $p.MainWindowHandle
        if ($h -ne [IntPtr]::Zero -and [PmGuard.Win]::IsIconic($h)) {
            [void][PmGuard.Win]::ShowWindow($h, 9)   # 9 = SW_RESTORE
            Invoke-Helper @('log', 'LINE window was minimized, restored')
        }
    }
}

function Test-Disk {
    $root = [System.IO.Path]::GetPathRoot($BotDir)
    $free = (New-Object System.IO.DriveInfo($root)).AvailableFreeSpace
    if ($free -lt $MinFreeBytes) {
        Invoke-Helper @('alert', 'disk', ("free {0:N1} GB on {1}" -f ($free / 1GB), $root))
    }
}

try {
    if (Test-ScreenLocked) {
        Invoke-Helper @('alert', 'locked')
    } else {
        Restore-LineWindow
    }
    Test-Disk
    Invoke-Helper @('backup')   # once per day; helper skips if today's copy exists
    Invoke-Helper @('skipped')
    Invoke-Helper @('hc')
} catch {
    Invoke-Helper @('log', ("guard.ps1 error: " + $_.Exception.Message))
    Invoke-Helper @('alert', 'guard_error', $_.Exception.Message)
    exit 1
}
