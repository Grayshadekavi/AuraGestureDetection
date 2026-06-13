@echo off
title AuraGesture - Real-Time AI Launcher
echo ===================================================
echo   AuraGesture Real-Time AI Launcher
echo ===================================================
echo.
echo [*] Activating Python isolated virtual environment...
cd /d "%~dp0"
call "venv\Scripts\activate.bat"

echo [*] Launching your default web browser...
start http://127.0.0.1:5000

echo [*] Starting Django Gesture AI Server...
echo [!] (To shut down the app anytime, close this window or press Ctrl+C)
echo.
python manage.py runserver 0.0.0.0:5000
pause
