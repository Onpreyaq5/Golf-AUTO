# One-time Windows settings for the bot machine. Must run as Administrator.
# Changes: no sleep/hibernate on AC, no sign-in on wake, no lock-on-screensaver,
# Windows Update active hours 07:00-23:00. Screen may still turn off (that is fine).
# Does NOT touch passwords: set auto-login yourself (instructions printed at the end).
$ErrorActionPreference = 'Stop'

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
    ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { throw 'Run this as Administrator.' }

function Set-Step { param([string]$Name, [scriptblock]$Do)
    try { & $Do; Write-Host "[OK]   $Name" } catch { Write-Host "[FAIL] $Name : $($_.Exception.Message)" }
}

Set-Step 'Never sleep on AC power' { powercfg /change standby-timeout-ac 0 }
Set-Step 'Never hibernate on AC power' { powercfg /change hibernate-timeout-ac 0 }
Set-Step 'No sign-in required after wake' {
    powercfg /setacvalueindex SCHEME_CURRENT SUB_NONE CONSOLELOCK 0
    powercfg /setactive SCHEME_CURRENT
}
Set-Step 'Screensaver off and does not lock' {
    $k = 'HKCU:\Control Panel\Desktop'
    Set-ItemProperty $k -Name ScreenSaveActive -Value '0'
    Set-ItemProperty $k -Name ScreenSaverIsSecure -Value '0'
}
Set-Step 'Windows Update active hours 07:00-23:00' {
    $k = 'HKLM:\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings'
    if (-not (Test-Path $k)) { New-Item -Path $k -Force | Out-Null }  # -Force on an existing key wipes it
    Set-ItemProperty $k -Name SmartActiveHoursState -Value 0 -Type DWord
    Set-ItemProperty $k -Name ActiveHoursStart -Value 7 -Type DWord
    Set-ItemProperty $k -Name ActiveHoursEnd -Value 23 -Type DWord
}
Set-Step 'Dynamic Lock off' {
    $k = 'HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Winlogon'
    Set-ItemProperty $k -Name EnableGoodbye -Value 0 -Type DWord
}

Write-Host ''
Write-Host '--- Still to do by hand ---'
Write-Host '1) Auto-login: download Sysinternals Autologon (learn.microsoft.com/sysinternals/downloads/autologon),'
Write-Host '   run it, type your Windows password yourself, click Enable.'
Write-Host '2) BIOS/UEFI: set "Restore on AC Power Loss" (or "AC Recovery") = Power On.'
Write-Host '3) Use a LAN cable instead of Wi-Fi if possible; a small UPS if power cuts are common.'
Write-Host '4) Healthchecks: put your hc-ping.com URL in config.toml (the guard will remind daily until set).'
