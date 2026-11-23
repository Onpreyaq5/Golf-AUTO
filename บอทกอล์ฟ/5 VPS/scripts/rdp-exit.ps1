# Leave a Remote Desktop session WITHOUT locking the screen.
# Moves this session to the console, so Windows keeps drawing the desktop and the
# bot can keep reading LINE and clicking. Closing RDP with the X button locks it.
# Needs Administrator (the .bat asks for it). ASCII only.
$ErrorActionPreference = 'Stop'
$sessionId = (Get-Process -Id $PID).SessionId
$tscon = Join-Path $env:WINDIR 'System32\tscon.exe'
if (-not (Test-Path $tscon)) { $tscon = Join-Path $env:WINDIR 'Sysnative\tscon.exe' }
Write-Host "Moving session $sessionId to console. Your RDP window will close now."
Start-Sleep -Seconds 2
& $tscon $sessionId /dest:console
if ($LASTEXITCODE -ne 0) {
    Write-Host "tscon failed (exit $LASTEXITCODE). Do NOT close RDP with X; ask the admin."
    Read-Host 'Press Enter'
}
