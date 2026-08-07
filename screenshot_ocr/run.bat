@echo off
cd /d "%~dp0"

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.8+ first.
    pause
    exit /b 1
)

if not exist .deps_installed (
    echo Installing dependencies...
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    if not errorlevel 1 (
        type nul > .deps_installed
        echo Done.
    ) else (
        echo [WARNING] Some deps failed.
    )
)

python screenshot_ocr.py
pause