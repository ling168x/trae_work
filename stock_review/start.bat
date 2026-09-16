@echo off
title 股票复盘工具

echo ============================================
echo    股票复盘工具
echo ============================================
echo.
echo  [1] 采集今日复盘数据
echo  [2] 采集指定日期数据
echo  [3] 查询指定日期复盘 (从数据库)
echo  [4] 查询个股历史入选记录
echo  [5] 同步全量历史K线 (首次运行)
echo  [6] 增量更新K线 (日常更新)
echo  [7] 查看同步状态
echo  [8] 启动 API 查询服务
echo  [9] 仅输出 JSON (不入库)
echo  [0] 退出
echo.
echo ============================================

set /p choice=请选择操作 (0-9): 

if "%choice%"=="1" goto collect_today
if "%choice%"=="2" goto collect_date
if "%choice%"=="3" goto query_date
if "%choice%"=="4" goto query_stock
if "%choice%"=="5" goto full_sync
if "%choice%"=="6" goto incr_update
if "%choice%"=="7" goto sync_status
if "%choice%"=="8" goto start_api
if "%choice%"=="9" goto json_only
if "%choice%"=="0" goto quit

echo 无效选择, 请输入 0-9
pause
goto :eof

:collect_today
echo.
echo 开始采集今日复盘数据...
echo ----------------------------------------
cd /d "%~dp0"
python main.py --pretty
echo.
echo ----------------------------------------
echo 采集完成! 数据已保存到 stock_review.db
echo.
pause
goto :eof

:collect_date
echo.
set /p input_date=请输入交易日期 (YYYY-MM-DD): 
echo.
cd /d "%~dp0"
python main.py --date %input_date% --pretty
echo.
pause
goto :eof

:query_date
echo.
cd /d "%~dp0"
python query.py --dates
echo.
set /p q_date=请输入要查询的日期 (YYYY-MM-DD): 
echo.
python query.py --date %q_date%
echo.
pause
goto :eof

:query_stock
echo.
set /p q_code=请输入股票代码 (如 000001): 
echo.
cd /d "%~dp0"
python query.py --stock %q_code%
echo.
pause
goto :eof

:full_sync
echo.
echo 开始全量同步历史K线数据 (约需较长时间)...
echo ----------------------------------------
cd /d "%~dp0"
python sync.py --full
echo.
echo ----------------------------------------
echo 同步完成!
echo.
pause
goto :eof

:incr_update
echo.
echo 增量更新最近2天K线数据...
echo ----------------------------------------
cd /d "%~dp0"
python sync.py --update
echo.
echo ----------------------------------------
echo 更新完成!
echo.
pause
goto :eof

:sync_status
echo.
cd /d "%~dp0"
python sync.py --status
echo.
pause
goto :eof

:start_api
echo.
echo 启动 API 查询服务...
echo ----------------------------------------
echo 服务地址: http://localhost:5000
echo 按 Ctrl+C 停止服务
echo ----------------------------------------
echo.
cd /d "%~dp0"
python app.py
pause
goto :eof

:json_only
echo.
cd /d "%~dp0"
python main.py --no-db --pretty
echo.
pause
goto :eof

:quit
exit /b 0
