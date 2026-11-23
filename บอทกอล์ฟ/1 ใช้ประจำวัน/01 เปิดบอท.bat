@echo off
chcp 65001 <nul >nul
setlocal EnableExtensions
set "BOT=%USERPROFILE%\Desktop\ระบบบอท โพสต์ไม้กอล์ฟอัตโนมัติ"
set "PY=%BOT%\venv\Scripts\python.exe"
set "PYTHONIOENCODING=utf-8"
if not exist "%PY%" goto :nobot
cd /d "%BOT%\app"
title เปิดบอท
echo ==================================================
echo   เปิดบอท
echo ==================================================
echo ล้างสวิตช์ปิด แล้วเริ่มตัวคุมบอท supervisor ถ้ายังไม่ได้ทำงาน
echo เหมือนปุ่ม เปิดการทำงาน ในแผงควบคุม
echo.
"%PY%" -c "from pmbot import config, procs; config.DISABLED_FLAG.unlink(missing_ok=True); print('supervisor: already running' if procs.supervisor_alive() else 'supervisor: started (' + procs.start_supervisor() + ')')"
if errorlevel 1 goto :done
echo.
echo ส่งคำสั่งเปิดแล้ว รอ 10 วินาทีแล้วจะแสดงสถานะ...
timeout /t 10 /nobreak >nul
"%PY%" -m pmbot status -n 5

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
