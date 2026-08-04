:: ============================================================
:: Perf Recorder - Startup Script
:: ============================================================
@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
set PYTHON=python

echo ============================================================
echo   Perf Recorder - Android/iOS Performance Monitor
echo ============================================================
echo.

:: --- Check Python ---
%PYTHON% --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.10+ and add to PATH.
    pause
    exit /b 1
)

:: --- Check ADB ---
adb version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARN] ADB not found in PATH. Android device monitoring will not work.
)

:: --- Default Config ---
set APP_ID=com.example.game
set DURATION=60
set PROFILE=unity
set OUTPUT_DIR=%SCRIPT_DIR%reports

:: --- Parse Args ---
:parse_args
if "%~1"=="" goto :show_menu
if /i "%~1"=="--app"      set APP_ID=%~2 & shift & shift & goto :parse_args
if /i "%~1"=="-a"         set APP_ID=%~2 & shift & shift & goto :parse_args
if /i "%~1"=="--duration" set DURATION=%~2 & shift & shift & goto :parse_args
if /i "%~1"=="-d"         set DURATION=%~2 & shift & shift & goto :parse_args
if /i "%~1"=="--profile"  set PROFILE=%~2 & shift & shift & goto :parse_args
if /i "%~1"=="-p"         set PROFILE=%~2 & shift & shift & goto :parse_args
if /i "%~1"=="--output"   set OUTPUT_DIR=%~2 & shift & shift & goto :parse_args
if /i "%~1"=="-o"         set OUTPUT_DIR=%~2 & shift & shift & goto :parse_args
if /i "%~1"=="--help"     goto :show_help
if /i "%~1"=="-h"         goto :show_help
shift
goto :parse_args

:show_help
echo Usage: start_perf.bat [OPTIONS]
echo.
echo Options:
echo   -a, --app APP_ID       Target app package name (default: com.example.game)
echo   -d, --duration SEC     Recording duration in seconds (default: 60)
echo   -p, --profile NAME     Profile: unity ^| generic (default: unity)
echo   -o, --output DIR       Output directory for reports (default: .\reports)
echo   -h, --help             Show this help
echo.
echo Examples:
echo   start_perf.bat -a com.tencent.tmgp.sgame -d 300 -p unity
echo   start_perf.bat -a com.example.app -d 120 -p generic -o D:\reports
echo.
pause
exit /b 0

:show_menu
cls
echo ============================================================
echo   Perf Recorder - Quick Start
echo ============================================================
echo.
echo   Current Settings:
echo     App ID    : %APP_ID%
echo     Duration  : %DURATION%s
echo     Profile   : %PROFILE%
echo     Output    : %OUTPUT_DIR%
echo.
echo   [1] Start recording with current settings
echo   [2] Set App ID
echo   [3] Set Duration
echo   [4] Set Profile
echo   [5] List connected devices
echo   [6] List available packages
echo   [0] Exit
echo.
set /p CHOICE="   Enter choice: "

if "%CHOICE%"=="1" goto :start_recording
if "%CHOICE%"=="2" goto :set_appid
if "%CHOICE%"=="3" goto :set_duration
if "%CHOICE%"=="4" goto :set_profile
if "%CHOICE%"=="5" goto :list_devices
if "%CHOICE%"=="6" goto :list_packages
if "%CHOICE%"=="0" exit /b 0
goto :show_menu

:set_appid
set /p APP_ID="   Enter App package name: "
goto :show_menu

:set_duration
set /p DURATION="   Enter duration (seconds): "
goto :show_menu

:set_profile
echo   Profiles: unity, generic
set /p PROFILE="   Enter profile name: "
goto :show_menu

:list_devices
echo.
echo   Connected devices:
%PYTHON% -c "import sys; sys.path.insert(0, r'%SCRIPT_DIR%'); from perf_recorder.adb_bridge import AdbBridge; b=AdbBridge(); [print(f'     {d.serial}  [{d.state}]  {d.model}') for d in b.list_devices()]"
echo.
pause
goto :show_menu

:list_packages
echo.
echo   Installed packages:
adb shell pm list packages 2>nul | findstr /i "game unity"
echo.
pause
goto :show_menu

:start_recording
echo.
echo ============================================================
echo   Starting recording...
echo ============================================================
echo   App ID    : %APP_ID%
echo   Duration  : %DURATION%s
echo   Profile   : %PROFILE%
echo   Output    : %OUTPUT_DIR%
echo   Press Ctrl+C to stop early
echo ============================================================
echo.

%PYTHON% -c ^
"import sys; sys.path.insert(0, r'%SCRIPT_DIR%'); ^
from perf_recorder import PerfRecorderHost, SessionConfig; ^
from datetime import datetime; ^
host = PerfRecorderHost(db_path=r'%OUTPUT_DIR%\session.db'); ^
devices = host.discover_devices(); ^
print(f'Devices found: {len(devices)}'); ^
if not devices: ^
    print('[ERROR] No devices connected. Exiting.'); ^
    host.close(); ^
    sys.exit(1); ^
for d in devices: ^
    host.setup_device(d, r'%APP_ID%', profile_name=r'%PROFILE%'); ^
    print(f'  Setup: {d}'); ^
config = SessionConfig( ^
    app_id=r'%APP_ID%', ^
    duration_sec=%DURATION%, ^
    profile_name=r'%PROFILE%', ^
    device_serials=devices, ^
    tags={'started_by': 'bat_launcher'}, ^
); ^
result = host.run_session(config); ^
print(f'Recording finished: {result[\"sample_count\"]} samples'); ^
paths = host.export_report(r'%OUTPUT_DIR%', title=f'Perf Report - {datetime.now().strftime(\"%%Y-%%m-%%d %%H:%%M:%%S\")}'); ^
print(f'Reports: HTML={paths[\"html\"]}, CSV={paths[\"csv\"]}, JSON={paths[\"json\"]}'); ^
host.close()"

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Recording failed. Check the logs above.
) else (
    echo.
    echo ============================================================
    echo   Recording completed! Reports saved to: %OUTPUT_DIR%
    echo ============================================================
)

echo.
pause
goto :show_menu