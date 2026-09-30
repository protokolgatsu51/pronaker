@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ===============================================
echo  Name Table Generator - build_installer.bat
echo ===============================================
echo.

if not exist venv\Scripts\activate.bat (
    echo ERROR: venv not found. Run this from inside your nametag_generator
    echo folder, and make sure you've already done "pip install -r requirements.txt".
    pause
    exit /b 1
)
call venv\Scripts\activate.bat

echo [1/5] Installing PyInstaller...
pip install pyinstaller --quiet
if errorlevel 1 (
    echo ERROR: pip install pyinstaller failed.
    pause
    exit /b 1
)

echo [2/5] Locating the Playwright package's driver files...
for /f "delims=" %%A in ('python -c "import playwright, os; print(os.path.join(os.path.dirname(playwright.__file__), 'driver'))"') do set "PW_DRIVER=%%A"
if not exist "!PW_DRIVER!" (
    echo ERROR: Could not find Playwright's driver folder at:
    echo   !PW_DRIVER!
    echo Make sure "pip install -r requirements.txt" completed successfully.
    pause
    exit /b 1
)
echo   Found: !PW_DRIVER!

echo [3/5] Locating the downloaded Chromium browser...
set "PW_BROWSERS=%LOCALAPPDATA%\ms-playwright"
if not exist "!PW_BROWSERS!" (
    echo ERROR: Could not find !PW_BROWSERS!
    echo Run "playwright install chromium" first, then re-run this script.
    pause
    exit /b 1
)
echo   Found: !PW_BROWSERS!

echo [4/5] Cleaning previous build...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
del /q NameTableGenerator.spec 2>nul

echo [5/5] Running PyInstaller (this takes a few minutes)...
pyinstaller ^
  --name "NameTableGenerator" ^
  --onedir ^
  --windowed ^
  --add-data "templates;templates" ^
  --add-data "static;static" ^
  --add-data "assets;assets" ^
  --add-data "fonts;fonts" ^
  --add-data "!PW_DRIVER!;playwright\driver" ^
  --add-data "!PW_BROWSERS!;ms-playwright" ^
  --hidden-import "generate" ^
  --hidden-import "generate_html" ^
  --hidden-import "paths" ^
  --collect-all "playwright" ^
  app.py

if errorlevel 1 (
    echo.
    echo BUILD FAILED. Scroll up for the PyInstaller error.
    pause
    exit /b 1
)

echo.
echo ===============================================
echo  Build finished: dist\NameTableGenerator\
echo  Try it:  dist\NameTableGenerator\NameTableGenerator.exe
echo  Next:    open installer.iss in Inno Setup and click Compile
echo            to produce a single Setup.exe you can share/install.
echo ===============================================
pause
