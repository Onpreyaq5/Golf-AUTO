@echo off
chcp 65001 <nul >nul
setlocal EnableExtensions
set "BOT=%USERPROFILE%\Desktop\ระบบบอท โพสต์ไม้กอล์ฟอัตโนมัติ"
set "PY=%BOT%\venv\Scripts\python.exe"
set "PYTHONIOENCODING=utf-8"
if not exist "%PY%" goto :nobot
cd /d "%BOT%\app"
title เซฟรูปรายการใหม่ทันที
echo ==================================================
echo   เซฟรูปรายการใหม่ทันที
echo ==================================================
echo เซฟรูปและจัดข้อความของทุกรายการที่ยังไม่มีรูปทันที โดยยังไม่โพสต์
echo ระหว่างนี้บอทยืมเมาส์ราว 15 วินาทีต่อรูป อย่าขยับเมาส์ และอย่าย่อหน้าต่าง LINE
echo.
choice /c YN /m "เริ่มเลยไหม กด Y = เริ่ม  N = ยกเลิก"
if errorlevel 2 goto :cancel
"%PY%" -m pmbot prepare

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
