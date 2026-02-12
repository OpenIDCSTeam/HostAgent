@echo off
REM ============================================================================
REM cx-Freeze 打包脚本 (Windows批处理版本)
REM OpenIDCS Client - 前后端一键构建
REM ============================================================================

setlocal enabledelayedexpansion

echo ============================================================
echo OpenIDCS Client - cx-Freeze 打包工具 (Windows)
echo 前后端一键构建
echo ============================================================
echo.

REM 获取脚本所在目录和项目根目录
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%\.."
set PROJECT_ROOT=%CD%
cd /d "%SCRIPT_DIR%"

REM ============================================================================
REM 步骤 1：检查环境
REM ============================================================================

echo [步骤 1/3] 检查环境...
echo.

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 未安装或未添加到 PATH
    pause
    exit /b 1
)
echo [OK] Python 已安装
python --version
echo.

REM 检查 Node.js（前端构建需要）
node --version >nul 2>&1
if errorlevel 1 (
    echo [WARN] Node.js 未安装，将跳过前端构建
    echo [WARN] 如需构建前端，请先安装 Node.js: https://nodejs.org/
    echo.
) else (
    echo [OK] Node.js 已安装
    node --version
    call npm --version
    echo.
)

REM 检查 cx-Freeze
python -c "import cx_Freeze" >nul 2>&1
if errorlevel 1 (
    echo [WARN] cx-Freeze 未安装
    echo.
    set /p install="是否安装 cx-Freeze? (y/n): "
    if /i "!install!"=="y" (
        echo 正在安装 cx-Freeze...
        python -m pip install cx-Freeze
        if errorlevel 1 (
            echo [ERROR] cx-Freeze 安装失败
            pause
            exit /b 1
        )
        echo [OK] cx-Freeze 安装成功
    ) else (
        echo 取消打包
        pause
        exit /b 1
    )
) else (
    echo [OK] cx-Freeze 已安装
)
echo.

REM ============================================================================
REM 步骤 2：清理旧的构建
REM ============================================================================

echo [步骤 2/3] 清理旧的构建...
echo.

if exist "%PROJECT_ROOT%\BuildCache\cxfreeze" (
    echo 清理旧的构建目录...
    rmdir /s /q "%PROJECT_ROOT%\BuildCache\cxfreeze" >nul 2>&1
)
echo.

REM ============================================================================
REM 步骤 3：开始打包（含前端构建）
REM ============================================================================

echo ============================================================
echo [步骤 3/3] 开始打包（含前端自动构建）...
echo ============================================================
echo.

cd /d "%SCRIPT_DIR%"
python build_cxfreeze.py build

if errorlevel 1 (
    echo.
    echo ============================================================
    echo [ERROR] 打包失败
    echo ============================================================
    pause
    exit /b 1
)

echo.
echo ============================================================
echo [SUCCESS] 打包成功!
echo 输出目录: BuildCache\cxfreeze\
echo ============================================================
echo.

REM 显示生成的文件
if exist "%PROJECT_ROOT%\BuildCache\cxfreeze" (
    echo 生成的文件:
    dir /b "%PROJECT_ROOT%\BuildCache\cxfreeze\*.exe"
    echo.
)

echo.
echo 下一步:
echo   1. 测试: cd BuildCache\cxfreeze ^&^& OpenIDCS-Client.exe
echo   2. 访问 http://localhost:1880 测试应用
echo.

pause
