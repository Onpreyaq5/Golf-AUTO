# Registers task PMGolfBot-DailyReport: runs daily_report.py every day at -At (default 21:30)
# and sends the report to Telegram. -Uninstall removes it. ASCII only (PowerShell 5.1).
param(
    [string]$At = '21:30',
    [string]$Python = '',
    [switch]$Uninstall
)
$ErrorActionPreference = 'Stop'
$TaskName = 'PMGolfBot-DailyReport'

if ($Uninstall) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Removed $TaskName"
    exit 0
}

if (-not $Python) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $cmd) { throw 'Python not found. Pass -Python <path to python.exe>.' }
    $Python = $cmd.Source
}
$script = Join-Path $PSScriptRoot 'daily_report.py'
$action = New-ScheduledTaskAction -Execute $Python -Argument "`"$script`"" -WorkingDirectory $PSScriptRoot
$trigger = New-ScheduledTaskTrigger -Daily -At $At
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 20)
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal `
    -Settings $settings -Force | Out-Null
Write-Host "Installed $TaskName daily at $At using $Python"
