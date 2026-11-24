# Registers task PMGolfBot-Telegram: listens for commands in the Telegram group while the
# user is signed in (checked every 5 minutes, never two at once). -Uninstall stops and
# removes it. ASCII only (PowerShell 5.1). Does not start the golf bot.
param(
    [string]$Python = '',
    [switch]$Uninstall
)
$ErrorActionPreference = 'Stop'
$TaskName = 'PMGolfBot-Telegram'

if ($Uninstall) {
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Stop-ScheduledTask -TaskName $TaskName
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "Stopped and removed $TaskName"
    } else {
        Write-Host "$TaskName is not installed"
    }
    exit 0
}

if (-not $Python) {
    $cmd = Get-Command pythonw -ErrorAction SilentlyContinue
    if (-not $cmd) { throw 'pythonw not found. Pass -Python <path to pythonw.exe>.' }
    $Python = $cmd.Source
}
if (-not (Test-Path -LiteralPath $Python)) { throw "Not found: $Python" }

$keyFile = Join-Path $env:USERPROFILE '.pmgolf\telegram.json'
if (-not (Test-Path -LiteralPath $keyFile)) { throw "Missing $keyFile - install the key first." }

$script = Join-Path $PSScriptRoot 'telegram_control.py'
$action = New-ScheduledTaskAction -Execute $Python -Argument "`"$script`"" -WorkingDirectory $PSScriptRoot
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal `
    -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName
Write-Host "Installed $TaskName using $Python"
Write-Host "Log: $env:USERPROFILE\.pmgolf\control.log"
