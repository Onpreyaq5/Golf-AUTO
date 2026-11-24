@echo off
chcp 65001 <nul >nul
setlocal EnableExtensions
set "VENV=%USERPROFILE%\Desktop\ระบบบอท โพสต์ไม้กอล์ฟอัตโนมัติ\venv\Scripts"
title เพิ่มผู้ดูแล Telegram
if not exist "%VENV%\python.exe" goto :nobot
echo ให้คนนั้นพิมพ์ /whoami ในกลุ่มเพื่อดูเลขของตัวเอง แล้วเอาเลขมาใส่
set "ID="
set /p "ID=เลขประจำตัว แล้วกด Enter ว่างไว้ = ยกเลิก: "
if not defined ID exit /b 0
set "ID=%ID:"=%"
for /f "delims=0123456789" %%a in ("%ID%") do goto :badnum
"%VENV%\python.exe" "%~dp0telegram_control.py" --add-admin "%ID%"
echo ถ้าติดตั้งตัวรับคำสั่งไว้แล้ว ให้กดถอนแล้วติดตั้งใหม่ รายชื่อใหม่จึงมีผล
echo.
echo ---- เสร็จแล้ว กดปุ่มใดก็ได้เพื่อปิด ----
pause >nul
exit /b 0

:badnum
echo ใส่ได้เฉพาะตัวเลข
pause
exit /b 1

:nobot
echo ไม่เจอระบบบอทบนเครื่องนี้ ต้องติดตั้งที่เครื่องบอท
pause
exit /b 1
