@echo off
chcp 65001 <nul >nul
setlocal EnableExtensions
set "BOT=%USERPROFILE%\Desktop\ระบบบอท โพสต์ไม้กอล์ฟอัตโนมัติ"
set "PY=%BOT%\venv\Scripts\python.exe"
set "PYTHONIOENCODING=utf-8"
if not exist "%PY%" goto :nobot
cd /d "%BOT%\app"
title ล็อกอินเฟสใหม่
echo ==================================================
echo   ล็อกอินเฟสใหม่
echo ==================================================
echo เปิด Edge โปรไฟล์ของบอท บอททำงานอยู่ก็เปิดได้ บอทจะหลบให้
echo ในหน้าต่าง Edge: ล็อกอินเอง ยืนยัน 2 ขั้นตอน สลับไปใช้เพจ Premium GOLF โปรโหมดสินค้า
echo เปิดกลุ่ม แล้วปิดหน้าต่าง Edge  บอทไม่เก็บและไม่พิมพ์รหัสผ่าน
echo.
"%PY%" -m pmbot fb-login

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
