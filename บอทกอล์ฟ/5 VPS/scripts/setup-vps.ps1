# One-time setup for a Windows VPS (Server 2019/2022 or Win 10/11) running the golf bot.
# Run as Administrator. Safe to run again. ASCII only (PowerShell 5.1).
# Also runs ..\..\4*\scripts\setup-machine.ps1 (no sleep, no lock, active hours).
$ErrorActionPreference = 'Stop'

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
    ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { throw 'Run this as Administrator.' }

$results = New-Object System.Collections.Generic.List[string]
function Set-Step { param([string]$Name, [scriptblock]$Do)
    try { & $Do; $results.Add("[OK]   $Name") } catch { $results.Add("[FAIL] $Name : $($_.Exception.Message)") }
}
$isServer = (Get-CimInstance Win32_OperatingSystem).ProductType -ne 1

Set-Step 'Time zone = Thailand (bot posts only 08:00-22:00 local time)' {
    Set-TimeZone -Id 'SE Asia Standard Time'
}
Set-Step 'Time sync with time.windows.com' {
    w32tm /config /manualpeerlist:time.windows.com /syncfromflags:manual /update | Out-Null
    Restart-Service w32time
    w32tm /resync | Out-Null
}
Set-Step 'High performance power plan' { powercfg /setactive SCHEME_MIN }

if ($isServer) {
    Set-Step 'Desktop Experience present (needed for LINE PC and Edge)' {
        if (-not (Test-Path "$env:WINDIR\explorer.exe")) { throw 'Server Core has no desktop: reinstall with Desktop Experience' }
    }
    Set-Step 'Install Media Foundation (LINE photos/viewer)' {
        $f = Get-WindowsFeature -Name Server-Media-Foundation
        if (-not $f.Installed) {
            $r = Install-WindowsFeature -Name Server-Media-Foundation
            if ($r.RestartNeeded -eq 'Yes') { $script:needReboot = $true }
        }
    }
    Set-Step 'Server Manager does not pop up at logon' {
        Get-ScheduledTask -TaskName ServerManager -ErrorAction SilentlyContinue | Disable-ScheduledTask | Out-Null
        New-ItemProperty 'HKLM:\SOFTWARE\Microsoft\ServerManager' -Name DoNotOpenServerManagerAtLogon `
            -Value 1 -PropertyType DWord -Force | Out-Null
    }
}

Set-Step 'RDP: never end or reset a disconnected session' {
    $k = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows NT\Terminal Services'
    New-Item -Path $k -Force | Out-Null
    foreach ($n in 'MaxDisconnectionTime', 'MaxIdleTime', 'MaxConnectionTime') {
        New-ItemProperty $k -Name $n -Value 0 -PropertyType DWord -Force | Out-Null
    }
    New-ItemProperty $k -Name fResetBroken -Value 0 -PropertyType DWord -Force | Out-Null
}
Set-Step 'Windows Update: no automatic reboot while user is logged on' {
    $k = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU'
    New-Item -Path $k -Force | Out-Null
    New-ItemProperty $k -Name NoAutoRebootWithLoggedOnUsers -Value 1 -PropertyType DWord -Force | Out-Null
}
Set-Step 'Microsoft Edge installed' {
    $edge = @("${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
              "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe") | Where-Object { Test-Path $_ }
    if (-not $edge) { throw 'Edge not found: install from microsoft.com/edge (Windows Server build)' }
}

$machine = Get-ChildItem (Join-Path $PSScriptRoot '..\..') -Directory |
    Where-Object { Test-Path (Join-Path $_.FullName 'scripts\setup-machine.ps1') } | Select-Object -First 1
if ($machine) {
    Write-Host '--- common machine settings ---'
    & (Join-Path $machine.FullName 'scripts\setup-machine.ps1')
} else {
    $results.Add('[FAIL] setup-machine.ps1 not found next to the VPS folder (copy folder "4 ...")')
}

Write-Host ''
Write-Host '--- VPS settings ---'
$results | ForEach-Object { Write-Host $_ }
if ($script:needReboot) { Write-Host ''; Write-Host '*** Restart the VPS once to finish Media Foundation. ***' }
Write-Host ''
Write-Host '--- Still to do by hand on the VPS ---'
Write-Host '1) Auto-logon: Sysinternals Autologon, type the VPS password yourself, Enable.'
Write-Host '2) Log in to LINE PC (use a separate LINE account for the bot) and open the OpenChat room.'
Write-Host '3) Log in to Facebook once in the bot Edge profile (button: login FB again), pass any checks.'
Write-Host '4) Leave RDP ONLY with the button "ออกจาก RDP แบบจอไม่ล็อก", never with the X button.'
