@echo off
chcp 65001 <nul >nul
setlocal EnableExtensions
set "BOT=%USERPROFILE%\Desktop\ระบบบอท โพสต์ไม้กอล์ฟอัตโนมัติ"
set "PY=%BOT%\venv\Scripts\python.exe"
set "PYTHONIOENCODING=utf-8"
if not exist "%PY%" goto :nobot
cd /d "%BOT%\app"
title ตรวจโพสต์ย้อนหลัง
echo ==================================================
echo   ตรวจโพสต์ย้อนหลัง
echo ==================================================
echo ไล่เช็กว่าทุกโพสต์ในห้อง LINE ตั้งแต่โพสต์ที่ระบุ ขึ้นกลุ่มเฟสครบ ไม่ซ้ำ เรียงตรง ข้อความตรง และมีรูป
echo ควรปิดบอทก่อนรัน แล้วเปิดใหม่หลังเสร็จ  เสร็จแล้วรายงานจะเปิดในเบราว์เซอร์
echo.
if exist "%BOT%\run\disabled.flag" goto :off_ok
echo คำเตือน: บอทยังเปิดอยู่ ควรใช้ 02 ปิดบอท ก่อน
choice /c YN /m "ทำต่อเลยไหม กด Y = ทำต่อ  N = ยกเลิก"
if errorlevel 2 goto :cancel
:off_ok
set "PID="
set /p "PID=เลขสินค้าของโพสต์แรกที่จะเริ่มเช็ก แล้วกด Enter ว่างไว้ = ยกเลิก: "
if not defined PID goto :cancel
for /f "delims=0123456789" %%a in ("%PID%") do goto :badnum
set "T="
set /p "T=เวลาของโพสต์นั้นใน LINE เช่น 10.42 ว่างไว้ได้: "
if not defined T goto :T_end
for /f "delims=0123456789." %%a in ("%T%") do goto :badnum
:T_end
set "S="
set /p "S=เลขสินค้าของโพสต์ก่อนหน้าในกลุ่มที่ไม่ต้องนับ ว่างไว้ได้: "
if not defined S goto :S_end
for /f "delims=0123456789" %%a in ("%S%") do goto :badnum
:S_end
set "ARGS=%PID%"
if defined T set "ARGS=%ARGS% --time %T%"
if defined S set "ARGS=%ARGS% --stop %S%"
"%PY%" -m pmbot verify %ARGS% --open

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
