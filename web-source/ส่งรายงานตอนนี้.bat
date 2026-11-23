@echo off
chcp 65001 <nul >nul
title ส่งรายงานตอนนี้
set "BOTPY=%USERPROFILE%\Desktop\ระบบบอท โพสต์ไม้กอล์ฟอัตโนมัติ\venv\Scripts\python.exe"
set "PY=python"
if exist "%BOTPY%" set "PY=%BOTPY%"
cd /d "%~dp0"
"%PY%" daily_report.py
echo.
echo ---- เสร็จแล้ว กดปุ่มใดก็ได้เพื่อปิด ----
pause >nul
