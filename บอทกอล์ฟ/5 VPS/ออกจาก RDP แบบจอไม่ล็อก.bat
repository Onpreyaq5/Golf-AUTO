@echo off
chcp 65001 <nul >nul
title ออกจาก RDP แบบจอไม่ล็อก
echo ==================================================
echo   ออกจาก Remote Desktop โดยจอไม่ล็อก บอทยังทำงานต่อ
echo ==================================================
echo ใช้ปุ่มนี้ทุกครั้งที่จะออกจาก VPS  ห้ามกดปุ่ม X ปิดหน้าต่าง RDP
echo (กด X = จอล็อก = บอทอ่าน LINE และเซฟรูปไม่ได้)
echo.
echo จะมีหน้าต่างขอสิทธิ์ ให้กด Yes แล้วหน้าต่าง RDP จะหลุดเอง ถือว่าปกติ
pause
powershell -NoProfile -Command "Start-Process powershell -Verb RunAs -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File','\"%~dp0scripts\rdp-exit.ps1\"')"
