@echo off
chcp 65001 <nul >nul
setlocal EnableExtensions
set "BOT=%USERPROFILE%\Desktop\ระบบบอท โพสต์ไม้กอล์ฟอัตโนมัติ"
set "SCRIPTS=%~dp0scripts"
if not exist "%BOT%\venv\Scripts\python.exe" goto :nobot
title ติดตั้งตัวเฝ้าเครื่อง
echo ==================================================
echo   ติดตั้งตัวเฝ้าเครื่อง (PMGolfBot-Guard ทุก 5 นาที)
echo ==================================================
echo - เตือน Telegram เมื่อจอถูกล็อก / ไม่เจอ LINE / ดิสก์เหลือน้อยกว่า 2 GB
echo - กางหน้าต่าง LINE คืนเองถ้าถูกย่อ
echo - สำรอง data\pmbot.db วันละครั้งไว้ที่โฟลเดอร์ backup เก็บ 7 วัน
echo - เตือนเมื่อมีรายการถูกข้าม (SKIPPED) เพิ่มขึ้น
echo - เตือนวันละครั้งถ้ายังไม่ได้ตั้ง Healthchecks
echo ไม่แก้ไขตัวบอทหรือฐานข้อมูลของบอท
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPTS%\install-guard.ps1" -BotDir "%BOT%"
echo.
echo ---- เสร็จแล้ว กดปุ่มใดก็ได้เพื่อปิดหน้าต่างนี้ ----
pause >nul
exit /b 0

:nobot
echo ไม่เจอระบบบอทที่ %BOT%
echo อย่าย้ายหรือเปลี่ยนชื่อโฟลเดอร์ "ระบบบอท โพสต์ไม้กอล์ฟอัตโนมัติ" บน Desktop
pause
exit /b 1
