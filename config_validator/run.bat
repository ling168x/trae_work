@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo ============================================================
echo   Config Table Validator
echo   Tool dir: %~dp0
echo   Config dir: d:\Client\template
echo ============================================================
echo.

python "%~dp0validate_config.py" -c "d:\Client\template" %*
set EXITCODE=%ERRORLEVEL%

echo.
echo ============================================================
if %EXITCODE% EQU 0 (
    echo   PASS - No errors found.
    echo   Report: %~dp0validate_report.md
) else (
    echo   WARN - %EXITCODE% errors found, check report:
    echo   %~dp0validate_report.md
)
echo ============================================================
pause
exit /b %EXITCODE%