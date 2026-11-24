@echo off
chcp 65001 <nul >nul
setlocal EnableExtensions
set "VENV=%USERPROFILE%\Desktop\ระบบบอท โพสต์ไม้กอล์ฟอัตโนมัติ\venv\Scripts"
title ติดตั้งสั่งงานผ่าน Telegram
if not exist "%VENV%\pythonw.exe" goto :nobot
echo ติดตั้งตัวรับคำสั่งจากกลุ่ม Telegram (ไม่เปิดบอท ไม่โพสต์)
echo สั่งได้เฉพาะคนที่อยู่ในรายชื่อผู้ดูแล
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-telegram-control.ps1" -Python "%VENV%\pythonw.exe"
echo.
echo ---- เสร็จแล้ว กดปุ่มใดก็ได้เพื่อปิด ----
pause >nul
exit /b 0

:nobot
echo ไม่เจอระบบบอทบนเครื่องนี้ ต้องติดตั้งที่เครื่องบอท
pause
exit /b 1
