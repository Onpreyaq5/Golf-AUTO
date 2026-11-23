@echo off
chcp 65001 <nul >nul
title ติดตั้งรายงานประจำวัน
echo ติดตั้งงาน PMGolfBot-DailyReport ส่งรายงานทาง Telegram ทุกวัน 21:30
set "BOTPY=%USERPROFILE%\Desktop\ระบบบอท โพสต์ไม้กอล์ฟอัตโนมัติ\venv\Scripts\python.exe"
if exist "%BOTPY%" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-daily-report.ps1" -Python "%BOTPY%"
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-daily-report.ps1"
)
echo.
echo ---- เสร็จแล้ว กดปุ่มใดก็ได้เพื่อปิด ----
pause >nul
