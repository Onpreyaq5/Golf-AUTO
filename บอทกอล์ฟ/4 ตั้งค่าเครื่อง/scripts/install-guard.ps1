# Copies the guard into <BotDir>\guard and registers task PMGolfBot-Guard (every 5 min,
# runs in the logged-on user's session so it can see windows). Use -Uninstall to remove.
param(
    [Parameter(Mandatory = $true)][string]$BotDir,
    [switch]$Uninstall
)
$ErrorActionPreference = 'Stop'
$TaskName = 'PMGolfBot-Guard'

if ($Uninstall) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Removed task $TaskName (guard folder kept)."
    exit 0
}

if (-not (Test-Path (Join-Path $BotDir 'venv\Scripts\python.exe'))) {
    throw "Bot venv not found under $BotDir"
}

$src = $PSScriptRoot
$dst = Join-Path $BotDir 'guard'
New-Item -ItemType Directory -Force -Path $dst | Out-Null
Copy-Item (Join-Path $src 'guard.ps1'), (Join-Path $src 'guard_helper.py') -Destination $dst -Force

$guardPs1 = Join-Path $dst 'guard.ps1'
$arg = "-NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$guardPs1`" -BotDir `"$BotDir`""
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arg
$every5 = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5)
$logon = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 4) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger @($every5, $logon) `
    -Principal $principal -Settings $settings -Force | Out-Null

Write-Host "Installed $TaskName -> $guardPs1"
Write-Host "Running one check now..."
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $guardPs1 -BotDir $BotDir
Write-Host "Done. Log: $dst\guard.log"
