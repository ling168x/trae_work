@echo off
title 工具 - 环境安装

echo ============================================
echo   工具 - 环境依赖安装
echo ============================================
echo.

echo [1/4] 检查 Python 环境...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: 未检测到 Python, 请先安装 Python 3.8+
    echo 下载: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo        Python OK

echo.
echo [2/4] 检查 pip...
python -m pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo pip 不可用, 尝试安装...
    python -m ensurepip --default-pip
)
echo        pip OK

echo.
echo [3/4] 升级 pip...
python -m pip install --upgrade pip -q
echo        pip 已更新

echo.
echo [4/4] 安装项目依赖...
echo.
python -m pip install -r "%~dp0requirements.txt"
if %errorlevel% neq 0 (
    echo.
    echo 错误: 依赖安装失败
    echo 可尝试国内镜像:
    echo   python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    pause
    exit /b 1
)

echo.
echo ============================================
echo    安装完成!
echo ============================================
echo.
echo 下一步: 双击 start.bat 启动复盘采集
echo.
pause
