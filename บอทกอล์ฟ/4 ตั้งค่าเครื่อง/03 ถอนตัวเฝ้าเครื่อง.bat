@echo off
chcp 65001 <nul >nul
setlocal EnableExtensions
set "BOT=%USERPROFILE%\Desktop\ระบบบอท โพสต์ไม้กอล์ฟอัตโนมัติ"
set "SCRIPTS=%~dp0scripts"
title ถอนตัวเฝ้าเครื่อง
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPTS%\install-guard.ps1" -BotDir "%BOT%" -Uninstall
echo.
echo ---- เสร็จแล้ว กดปุ่มใดก็ได้เพื่อปิดหน้าต่างนี้ ----
pause >nul
exit /b 0
