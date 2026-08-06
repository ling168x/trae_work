@echo off
chcp 65001 >nul
title WeChat Message Reader

echo.
echo ============================================
echo   WeChat Message Reader - 微信消息读取工具
echo ============================================
echo.

REM 检查 Python 是否安装
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python, 请先安装 Python 3.8+
    pause
    exit /b 1
)

REM 检查并安装依赖
echo [*] 正在检查依赖...
pip install -r requirements.txt --quiet

echo.
echo [*] 启动中...
echo.

python main.py

pause