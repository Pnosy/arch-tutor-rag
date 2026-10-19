@echo off
chcp 65001 >nul
cd /d %~dp0
python scripts\precheck.py
if errorlevel 1 echo.
pause
