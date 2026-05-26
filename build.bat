@echo off
:: ═══════════════════════════════════════════════════════════════════════════
:: BulkWave Pro - Windows EXE Builder
:: Requires: pip install pyinstaller
:: Usage: Double-click this file or run from command prompt
:: ═══════════════════════════════════════════════════════════════════════════

title BulkWave Pro - Build Script

echo.
echo  ██╗    ██╗██╗  ██╗ █████╗ ████████╗███████╗██████╗ ██╗      █████╗ ███████╗████████╗
echo  ██║    ██║██║  ██║██╔══██╗╚══██╔══╝██╔════╝██╔══██╗██║     ██╔══██╗██╔════╝╚══██╔══╝
echo  ██║ █╗ ██║███████║███████║   ██║   ███████╗██████╔╝██║     ███████║███████╗   ██║
echo  ██║███╗██║██╔══██║██╔══██║   ██║   ╚════██║██╔══██╗██║     ██╔══██║╚════██║   ██║
echo  ╚███╔███╔╝██║  ██║██║  ██║   ██║   ███████║██████╔╝███████╗██║  ██║███████║   ██║
echo   ╚══╝╚══╝ ╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═════╝ ╚══════╝╚═╝  ╚═╝╚══════╝   ╚═╝
echo.
echo  Smart Bulk WhatsApp Automation  ^|  Build Script
echo  ════════════════════════════════════════════════════
echo.

:: ── Check Python ─────────────────────────────────────────────────────────────
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.10+ and add it to PATH.
    pause
    exit /b 1
)
echo [OK] Python found.

:: ── Check PyInstaller ─────────────────────────────────────────────────────────
python -c "import PyInstaller" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Installing PyInstaller...
    pip install pyinstaller
)
echo [OK] PyInstaller ready.

:: ── Install dependencies ──────────────────────────────────────────────────────
echo.
echo [STEP 1/3] Installing dependencies...
pip install -r requirements.txt --quiet
echo [OK] Dependencies installed.

:: ── Generate sample data (optional) ──────────────────────────────────────────
echo.
echo [STEP 2/3] Generating sample contacts file...
python create_sample.py
echo [OK] Sample data ready.

:: ── Build EXE ─────────────────────────────────────────────────────────────────
echo.
echo [STEP 3/3] Building Windows EXE...
echo           This may take 2-5 minutes. Please wait...
echo.

pyinstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name "BulkWave Pro" ^
    --icon "assets/icons/app.ico" ^
    --add-data "ui;ui" ^
    --add-data "services;services" ^
    --add-data "utils;utils" ^
    --add-data "assets;assets" ^
    --add-data "data;data" ^
    --hidden-import "customtkinter" ^
    --hidden-import "PIL._tkinter_finder" ^
    --hidden-import "pandas" ^
    --hidden-import "openpyxl" ^
    --hidden-import "selenium" ^
    --hidden-import "webdriver_manager" ^
    --collect-all "customtkinter" ^
    --collect-data "sv_ttk" ^
    --exclude-module "matplotlib" ^
    --exclude-module "scipy" ^
    --exclude-module "numpy.testing" ^
    main.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Build failed. See output above for details.
    pause
    exit /b 1
)

echo.
echo ═══════════════════════════════════════════════════════════════
echo  BUILD SUCCESSFUL!
echo  EXE location: dist\BulkWave Pro.exe
echo ═══════════════════════════════════════════════════════════════
echo.
echo  IMPORTANT: When distributing, include these alongside the EXE:
echo    - chrome_data\   (WhatsApp session - optional, user creates it)
echo    - data\          (database and exports)
echo    - assets\        (icons and images)
echo.
pause
