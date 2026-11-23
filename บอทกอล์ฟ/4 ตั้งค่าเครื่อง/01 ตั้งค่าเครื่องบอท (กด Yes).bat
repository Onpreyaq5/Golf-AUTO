@echo off
chcp 65001 <nul >nul
setlocal EnableExtensions
set "BOT=%USERPROFILE%\Desktop\ระบบบอท โพสต์ไม้กอล์ฟอัตโนมัติ"
set "SCRIPTS=%~dp0scripts"
title ตั้งค่าเครื่องบอท
echo ==================================================
echo   ตั้งค่าเครื่องบอท (ทำครั้งเดียว)
echo ==================================================
echo - ไม่ให้เครื่อง sleep / hibernate ตอนเสียบปลั๊ก
echo - ตื่นจาก sleep ไม่ต้องใส่รหัส, screensaver ไม่ล็อกจอ, ปิด Dynamic Lock
echo - Windows Update ห้ามรีสตาร์ตช่วง 07:00-23:00
echo ปิดจอเองได้ตามปกติ ไม่กระทบบอท
echo.
echo จะมีหน้าต่างขอสิทธิ์ผู้ดูแล ให้กด Yes
pause
powershell -NoProfile -Command "Start-Process powershell -Verb RunAs -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-NoExit','-File','\"%SCRIPTS%\setup-machine.ps1\"')"
exit /b 0
