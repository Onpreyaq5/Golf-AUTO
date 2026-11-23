@echo off
chcp 65001 <nul >nul
setlocal EnableExtensions
set "BOT=%USERPROFILE%\Desktop\ระบบบอท โพสต์ไม้กอล์ฟอัตโนมัติ"
set "PY=%BOT%\venv\Scripts\python.exe"
set "PYTHONIOENCODING=utf-8"
if not exist "%PY%" goto :nobot
cd /d "%BOT%\app"
title ดูการทำงานสด
echo ==================================================
echo   ดูการทำงานสด
echo ==================================================
echo แสดงบันทึกการทำงานของบอท 40 บรรทัดล่าสุด แล้วแสดงบรรทัดใหม่ต่อไปเรื่อย ๆ
echo ปิดหน้าต่างนี้หรือกด Ctrl+C เมื่อดูเสร็จ บอทไม่หยุดตาม
echo.
set "LOGF=%BOT%\logs\bot.log"
if not exist "%LOGF%" (
  echo ยังไม่มีไฟล์ bot.log
  goto :done
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Console]::OutputEncoding=[Text.Encoding]::UTF8; Get-Content -LiteralPath $env:LOGF -Tail 40 -Wait -Encoding UTF8"

:done
echo.
echo ---- เสร็จแล้ว กดปุ่มใดก็ได้เพื่อปิดหน้าต่างนี้ ----
pause >nul
exit /b 0

:cancel
echo.
echo ยกเลิกแล้ว ไม่ได้ทำอะไร
pause
exit /b 0

:badnum
echo.
echo พิมพ์ได้เฉพาะตัวเลข ลองใหม่อีกครั้ง
pause
exit /b 1

:nobot
echo ไม่เจอระบบบอทที่ %BOT%
echo อย่าย้ายหรือเปลี่ยนชื่อโฟลเดอร์ "ระบบบอท โพสต์ไม้กอล์ฟอัตโนมัติ" บน Desktop
pause
exit /b 1
