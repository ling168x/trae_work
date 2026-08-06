@echo off
chcp 65001 >nul
title PyWxDump 微信聊天记录提取工具

echo ============================================================
echo   PyWxDump 微信聊天记录提取工具
echo   基于 SharpWxDump Python 版 (pywxdump v3.1)
echo ============================================================
echo.
echo  ⚠ 注意: 步骤1需要【以管理员身份运行】！
echo     如果当前不是管理员模式，请右键此文件选择"以管理员身份运行"
echo.
echo  [1] 步骤1: 提取密钥 (需管理员权限)
echo  [2] 步骤2: 解密并导出全部聊天记录
echo  [3] 一键执行 (1+2)
echo  [0] 退出
echo.
set /p choice="请选择 [1/2/3/0]: "

if "%choice%"=="1" goto extract
if "%choice%"=="2" goto decrypt
if "%choice%"=="3" goto all
if "%choice%"=="0" goto end
goto end

:extract
echo.
echo ════════════════════════════════════════════════════════════
echo   步骤1: 提取数据库密钥
echo ════════════════════════════════════════════════════════════
echo.
echo   请确保已登录微信！
echo.
python extract_keys.py
if %errorlevel% neq 0 (
    echo.
    echo   [失败] 密钥提取失败，请检查：
    echo   1. 是否以管理员身份运行
    echo   2. 微信是否已登录
    echo   3. 杀毒软件是否阻止了内存读取
    echo.
    echo   备选方案: 手动运行以下命令
    echo     wxdump info
    echo   将输出中的密钥手动填入 extracted_keys.json
)
pause
goto end

:decrypt
echo.
echo ════════════════════════════════════════════════════════════
echo   步骤2: 解密数据库并导出聊天记录
echo ════════════════════════════════════════════════════════════
echo.
if not exist "extracted_keys.json" (
    echo   [错误] 未找到 extracted_keys.json
    echo   请先执行步骤1提取密钥！
    pause
    goto end
)
python decrypt_all.py
pause
goto end

:all
echo.
echo ════════════════════════════════════════════════════════════
echo   一键执行: 提取密钥 + 解密 + 导出
echo ════════════════════════════════════════════════════════════
echo.
echo   [1/2] 提取密钥...
python extract_keys.py
if %errorlevel% neq 0 (
    echo   [失败] 密钥提取失败，请以管理员身份重新运行！
    pause
    goto end
)
echo.
echo   [2/2] 解密并导出...
python decrypt_all.py
pause
goto end

:end