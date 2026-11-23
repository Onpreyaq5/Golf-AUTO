@echo off
chcp 65001 <nul >nul
setlocal EnableExtensions
set "BOT=%USERPROFILE%\Desktop\ระบบบอท โพสต์ไม้กอล์ฟอัตโนมัติ"
set "SCRIPTS=%~dp0scripts"
if not exist "%BOT%\guard\guard.log" (
  echo ยังไม่มีบันทึก ติดตั้งตัวเฝ้าเครื่องก่อน หรือรอ 5 นาที
  pause
  exit /b 1
)
start "" notepad.exe "%BOT%\guard\guard.log"
exit /b 0
