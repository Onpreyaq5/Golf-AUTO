@echo off
chcp 65001 <nul >nul
setlocal EnableExtensions
set "BOT=%USERPROFILE%\Desktop\ระบบบอท โพสต์ไม้กอล์ฟอัตโนมัติ"
set "PY=%BOT%\venv\Scripts\python.exe"
set "PYTHONIOENCODING=utf-8"
if not exist "%PY%" goto :nobot
cd /d "%BOT%\app"
title เริ่มนับจากโพสต์นี้
echo ==================================================
echo   เริ่มนับจากโพสต์นี้
echo ==================================================
echo ตั้งจุดเริ่มครั้งเดียว: โพสต์นี้และทุกโพสต์หลังจากนี้ในห้อง LINE จะถูกโพสต์
echo ส่วนโพสต์ก่อนหน้าจะไม่ถูกโพสต์  ใช้ตอนเริ่มระบบใหม่เท่านั้น
echo.
set "PID="
set /p "PID=เลขสินค้า เช่น 133664 แล้วกด Enter ว่างไว้ = ยกเลิก: "
if not defined PID goto :cancel
for /f "delims=0123456789" %%a in ("%PID%") do goto :badnum
set "T="
set /p "T=เวลาของโพสต์ใน LINE เช่น 10.42 ว่างไว้ได้: "
if not defined T goto :T_end
for /f "delims=0123456789." %%a in ("%T%") do goto :badnum
:T_end
set "ARGS=%PID%"
if defined T set "ARGS=%ARGS% --time %T%"
choice /c YN /m "ยืนยัน กด Y = ทำเลย  N = ยกเลิก"
if errorlevel 2 goto :cancel
"%PY%" -m pmbot start-from %ARGS%

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
