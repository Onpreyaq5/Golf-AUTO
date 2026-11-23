@echo off
chcp 65001 <nul >nul
title ตั้งค่า VPS
echo ==================================================
echo   ตั้งค่า VPS สำหรับบอทกอล์ฟ (ทำครั้งเดียว รันซ้ำได้)
echo ==================================================
echo - ตั้งเวลาเป็นเวลาไทย (บอทโพสต์ 08:00-22:00 ตามเวลาเครื่อง)
echo - ติดตั้ง Media Foundation ให้ LINE เปิดรูปได้
echo - RDP หลุดแล้วไม่ปิด session, Windows Update ไม่รีสตาร์ตเองตอนล็อกอินอยู่
echo - ไม่ sleep ไม่ล็อกจอ (ตั้งค่าเครื่องชุดเดียวกับเครื่องที่บ้าน)
echo.
echo จะมีหน้าต่างขอสิทธิ์ ให้กด Yes
pause
powershell -NoProfile -Command "Start-Process powershell -Verb RunAs -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-NoExit','-File','\"%~dp0scripts\setup-vps.ps1\"')"
