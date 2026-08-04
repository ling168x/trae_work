:: ============================================================
:: Perf Recorder GUI - Launcher
:: ============================================================
@echo off
chcp 65001 >nul
setlocal

set SCRIPT_DIR=%~dp0
set PYTHON=python

echo ============================================================
echo   Perf Recorder GUI - Launching...
echo ============================================================
echo.

:: --- Check Python ---
%PYTHON% --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.10+.
    pause
    exit /b 1
)

:: --- Check PyQt5 ---
%PYTHON% -c "import PyQt5" >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARN] PyQt5 not installed. Installing...
    pip install PyQt5 matplotlib
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install PyQt5. Please run: pip install PyQt5 matplotlib
        pause
        exit /b 1
    )
)

:: --- Launch GUI ---
echo Starting Perf Recorder GUI...
%PYTHON% "%SCRIPT_DIR%gui_app.py"

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] GUI exited with error.
    pause
)