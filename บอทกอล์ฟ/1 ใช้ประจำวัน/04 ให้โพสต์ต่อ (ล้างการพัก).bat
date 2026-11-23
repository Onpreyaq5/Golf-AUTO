@echo off
chcp 65001 <nul >nul
setlocal EnableExtensions
set "BOT=%USERPROFILE%\Desktop\ระบบบอท โพสต์ไม้กอล์ฟอัตโนมัติ"
set "PY=%BOT%\venv\Scripts\python.exe"
set "PYTHONIOENCODING=utf-8"
if not exist "%PY%" goto :nobot
cd /d "%BOT%\app"
title ให้โพสต์ต่อ
echo ==================================================
echo   ให้โพสต์ต่อ
echo ==================================================
echo ใช้หลังแก้ปัญหาที่บอทแจ้งแล้ว เช่น ล็อกอินเฟสใหม่ หรือลบโพสต์ที่ผิด
echo บอทจะล้างการพัก และคืนโพสต์ที่พักไว้เข้าคิวภายในไม่กี่วินาที
echo เหมือนปุ่ม ให้โพสต์ต่อ ในแผงควบคุม
echo.
"%PY%" -m pmbot resume

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
