@echo off
chcp 65001 <nul >nul
setlocal EnableExtensions
set "BOT=%USERPROFILE%\Desktop\ระบบบอท โพสต์ไม้กอล์ฟอัตโนมัติ"
set "PY=%BOT%\venv\Scripts\python.exe"
set "PYTHONIOENCODING=utf-8"
if not exist "%PY%" goto :nobot
cd /d "%BOT%\app"
title โพสต์รายการทันที
echo ==================================================
echo   โพสต์รายการทันที
echo ==================================================
echo โพสต์รายการเดียวทันที ไม่รอคิว
echo กลุ่มทดสอบ = ไม่นับว่าโพสต์จริงแล้ว    กลุ่มจริง = ต้องพิมพ์ yes ยืนยัน
echo.
"%PY%" -m pmbot status -n 15 <nul
echo.
set "ID="
set /p "ID=พิมพ์เลขรายการ ตัวเลขหลัง # แล้วกด Enter ว่างไว้ = ยกเลิก: "
if not defined ID goto :cancel
for /f "delims=0123456789" %%a in ("%ID%") do goto :badnum
echo.
echo 1 = กลุ่มทดสอบ    2 = กลุ่มจริง
choice /c 12 /n /m "เลือก 1 หรือ 2: "
if errorlevel 2 goto :live
"%PY%" -m pmbot post %ID% --target test
goto :done
:live
set "OK="
set /p "OK=จะโพสต์รายการ #%ID% ลงกลุ่มจริงทันที พิมพ์ yes แล้วกด Enter เพื่อยืนยัน: "
if /i not "%OK%"=="yes" goto :cancel
"%PY%" -m pmbot post %ID% --target live --yes

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
