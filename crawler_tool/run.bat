@echo off
chcp 65001 >nul
title 通用爬虫工具

echo ===========================================
echo   通用爬虫工具 - Universal Crawler Tool
echo ===========================================
echo.

REM 切换到脚本所在目录
cd /d "%~dp0"

REM 检查 Python 环境
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)

REM 检查并安装依赖
echo [信息] 检查依赖...
pip install -r requirements.txt -q

if %errorlevel% neq 0 (
    echo [错误] 依赖安装失败，请手动执行: pip install -r requirements.txt
    pause
    exit /b 1
)

echo [信息] 启动程序...
python main.py

pause