@echo off
chcp 65001 >nul

cd /d "%~dp0"

if not exist venv (
    echo 正在创建虚拟环境...
    python -m venv venv
)

echo 正在激活虚拟环境...
call venv\Scripts\activate.bat

echo 正在安装依赖...
pip install pandas openpyxl beautifulsoup4 >nul 2>&1

echo 正在启动性能测试工具...
python -m android_perf_tool.gui

pause