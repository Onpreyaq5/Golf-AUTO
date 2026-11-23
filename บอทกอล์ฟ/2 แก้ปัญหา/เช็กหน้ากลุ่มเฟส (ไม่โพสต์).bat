@echo off
chcp 65001 <nul >nul
setlocal EnableExtensions
set "BOT=%USERPROFILE%\Desktop\ระบบบอท โพสต์ไม้กอล์ฟอัตโนมัติ"
set "PY=%BOT%\venv\Scripts\python.exe"
set "PYTHONIOENCODING=utf-8"
if not exist "%PY%" goto :nobot
cd /d "%BOT%\app"
title เช็กหน้ากลุ่มเฟส
echo ==================================================
echo   เช็กหน้ากลุ่มเฟส
echo ==================================================
echo เปิดหน้ากลุ่มแล้วเช็กว่ากล่องโพสต์เป็นชื่อเพจ โดยไม่โพสต์อะไร
echo 1 = กลุ่มทดสอบ    2 = กลุ่มจริง
echo.
choice /c 12 /n /m "เลือก 1 หรือ 2: "
if errorlevel 2 (set "TGT=live") else (set "TGT=test")
"%PY%" -m pmbot fb-check --target %TGT%

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
