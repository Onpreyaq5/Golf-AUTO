@echo off
chcp 65001 <nul >nul
setlocal EnableExtensions
set "VENV=%USERPROFILE%\Desktop\ระบบบอท โพสต์ไม้กอล์ฟอัตโนมัติ\venv\Scripts"
title ถอนสั่งงานผ่าน Telegram
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-telegram-control.ps1" -Uninstall
echo.
echo ---- เสร็จแล้ว กดปุ่มใดก็ได้เพื่อปิด ----
pause >nul
exit /b 0
