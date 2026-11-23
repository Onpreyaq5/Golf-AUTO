@echo off
chcp 65001 <nul >nul
setlocal EnableExtensions
set "BOT=%USERPROFILE%\Desktop\ระบบบอท โพสต์ไม้กอล์ฟอัตโนมัติ"
set "PY=%BOT%\venv\Scripts\python.exe"
set "PYTHONIOENCODING=utf-8"
if not exist "%PY%" goto :nobot
cd /d "%BOT%\app"
title เปิดรายงาน
echo ==================================================
echo   เปิดรายงาน
echo ==================================================
echo เปิดหน้าเว็บรายการโพสต์ล่าสุด 150 รายการ พร้อมข้อความและรูป ใช้เทียบกับห้อง LINE
echo.
"%PY%" -m pmbot report --open

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
