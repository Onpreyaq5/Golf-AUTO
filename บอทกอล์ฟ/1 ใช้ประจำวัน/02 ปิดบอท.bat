@echo off
chcp 65001 <nul >nul
setlocal EnableExtensions
set "BOT=%USERPROFILE%\Desktop\ระบบบอท โพสต์ไม้กอล์ฟอัตโนมัติ"
set "PY=%BOT%\venv\Scripts\python.exe"
set "PYTHONIOENCODING=utf-8"
if not exist "%PY%" goto :nobot
cd /d "%BOT%\app"
title ปิดบอท
echo ==================================================
echo   ปิดบอท
echo ==================================================
echo บอทจะทำขั้นที่ค้างอยู่ให้เสร็จก่อน แล้วหยุดอ่าน LINE และหยุดโพสต์
echo จะไม่กลับมาเองจนกว่าจะเปิดอีกครั้ง แม้รีบูตเครื่อง
echo เหมือนปุ่ม ปิดการทำงาน ในแผงควบคุม
echo.
if exist "%BOT%\run\disabled.flag" (
  echo บอทปิดอยู่แล้ว ไม่ต้องทำอะไร
  goto :done
)
choice /c YN /m "ยืนยันปิดบอท กด Y = ปิด  N = ไม่ปิด"
if errorlevel 2 goto :cancel
"%PY%" -c "import time; from pmbot import config; config.ensure_dirs(); config.DISABLED_FLAG.write_text(time.strftime('%%Y-%%m-%%d %%H:%%M:%%S') + ' bat file', encoding='utf-8')"
echo.
echo ส่งคำสั่งปิดแล้ว บอทจะหยุดหลังทำขั้นที่ค้างอยู่เสร็จ

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
