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
echo  [5] 启动 API 查询服务
echo  [6] 采集今日数据 + 启动 API
echo  [7] 仅输出 JSON (不入库)
echo  [0] 退出
echo.
echo ============================================

set /p choice=请选择操作 (0-7): 

if "%choice%"=="1" goto collect_today
if "%choice%"=="2" goto collect_date
if "%choice%"=="3" goto query_date
if "%choice%"=="4" goto query_stock
if "%choice%"=="5" goto start_api
if "%choice%"=="6" goto collect_and_api
if "%choice%"=="7" goto json_only
if "%choice%"=="0" goto quit

echo 无效选择, 请输入 0-7
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
echo 开始采集 %input_date% 的复盘数据...
echo ----------------------------------------
cd /d "%~dp0"
python main.py --date %input_date% --pretty
echo.
echo ----------------------------------------
echo 采集完成!
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

:start_api
echo.
echo 启动 API 查询服务...
echo ----------------------------------------
echo 服务地址: http://localhost:5000
echo 接口文档: http://localhost:5000/
echo.
echo 按 Ctrl+C 停止服务
echo ----------------------------------------
echo.
cd /d "%~dp0"
python app.py
pause
goto :eof

:collect_and_api
echo.
echo [步骤1] 采集今日复盘数据...
echo ----------------------------------------
cd /d "%~dp0"
python main.py --pretty
echo.
echo ----------------------------------------
echo [步骤2] 启动 API 查询服务...
echo ----------------------------------------
echo 服务地址: http://localhost:5000
echo 按 Ctrl+C 停止服务
echo ----------------------------------------
echo.
python app.py
pause
goto :eof

:json_only
echo.
echo 采集今日数据 (仅输出JSON, 不入库)...
echo ----------------------------------------
cd /d "%~dp0"
python main.py --no-db --pretty
echo.
echo ----------------------------------------
pause
goto :eof

:quit
exit /b 0
