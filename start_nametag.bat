@echo off
title Name Table Generator
cd /d "%~dp0"

if not exist venv\Scripts\activate.bat (
    echo Could not find venv folder next to this file.
    echo Put start_nametag.bat inside your nametag_generator folder, next to app.py.
    pause
    exit /b
)

call venv\Scripts\activate.bat

echo Starting Name Table Generator...
echo (Keep this window open while you use it. Close it to stop the server.)
echo.

start "" http://localhost:5000
python app.py

pause
