@echo off
REM ============================================================================
REM OpenIDCS-Client 完整打包脚本 (Python 后端 + React 前端)
REM 使用 cx-Freeze 打包
REM ============================================================================

setlocal enabledelayedexpansion

echo ============================================================
echo OpenIDCS-Client 完整打包流程
echo Python 后端 + React 前端
echo ============================================================
echo.

REM 获取项目根目录
cd ..
set PROJECT_ROOT=%CD%
cd AllBuilder

REM ============================================================================
REM 步骤 1：检查环境
REM ============================================================================

echo [步骤 1/5] 检查环境...
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

REM 检查 Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js 未安装或未添加到 PATH
    echo 请从 https://nodejs.org/ 下载并安装 Node.js LTS 版本
    pause
    exit /b 1
)
echo [OK] Node.js 已安装
node --version
npm --version
echo.

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
REM 步骤 2：构建 React 前端
REM ============================================================================

echo ============================================================
echo [步骤 2/5] 构建 React 前端...
echo ============================================================
echo.

cd "%PROJECT_ROOT%\FrontPages"

REM 检查 node_modules 是否存在
if not exist "node_modules" (
    echo [INFO] 首次构建，正在安装前端依赖...
    call npm install
    if errorlevel 1 (
        echo [ERROR] 前端依赖安装失败
        pause
        exit /b 1
    )
    echo [OK] 前端依赖安装完成
    echo.
)

REM 构建前端
echo [INFO] 正在构建 React 前端...
call npm run build
if errorlevel 1 (
    echo.
    echo [ERROR] 前端构建失败
    echo 请检查前端代码是否有错误
    pause
    exit /b 1
)

echo.
echo [OK] 前端构建完成
echo 输出目录: FrontPages\dist\
echo.

REM ============================================================================
REM 步骤 3：复制前端产物到后端静态目录
REM ============================================================================

echo ============================================================
echo [步骤 3/5] 复制前端产物到后端静态目录...
echo ============================================================
echo.

cd "%PROJECT_ROOT%"

REM 创建静态目录（如果不存在）
if not exist "static" (
    echo [INFO] 创建 static 目录...
    mkdir static
)

REM 清空旧的静态文件
echo [INFO] 清理旧的静态文件...
if exist "static\*" (
    del /q /s "static\*" >nul 2>&1
    for /d %%p in ("static\*") do rmdir "%%p" /s /q >nul 2>&1
)

REM 复制前端构建产物
echo [INFO] 复制前端构建产物...
xcopy /E /I /Y "FrontPages\dist\*" "static\" >nul
if errorlevel 1 (
    echo [ERROR] 复制前端产物失败
    pause
    exit /b 1
)

echo [OK] 前端产物复制完成
echo 目标目录: static\
echo.

REM 显示复制的文件
echo [INFO] 静态文件列表:
dir /b "static"
echo.

REM ============================================================================
REM 步骤 4：打包 Python 后端
REM ============================================================================

echo ============================================================
echo [步骤 4/5] 打包 Python 后端...
echo ============================================================
echo.

cd "%PROJECT_ROOT%\AllBuilder"

REM 清理旧的构建
if exist "%PROJECT_ROOT%\BuildCache\cxfreeze" (
    echo [INFO] 清理旧的构建目录...
    rmdir /s /q "%PROJECT_ROOT%\BuildCache\cxfreeze" >nul 2>&1
)

REM 开始打包
echo [INFO] 正在打包 Python 后端（包含 React 前端）...
echo [INFO] 这可能需要几分钟时间，请耐心等待...
echo.

python build_cxfreeze.py build

if errorlevel 1 (
    echo.
    echo ============================================================
    echo [ERROR] 后端打包失败
    echo ============================================================
    echo.
    echo 可能的原因:
    echo 1. 缺少必要的 Python 依赖包
    echo 2. build_cxfreeze.py 配置有误
    echo 3. 磁盘空间不足
    echo.
    echo 请检查错误信息并重试
    pause
    exit /b 1
)

echo.
echo [OK] 后端打包完成
echo 输出目录: BuildCache\cxfreeze\
echo.

REM ============================================================================
REM 步骤 5：创建发布包
REM ============================================================================

echo ============================================================
echo [步骤 5/5] 创建发布包...
echo ============================================================
echo.

cd "%PROJECT_ROOT%\BuildCache"

REM 检查构建输出是否存在
if not exist "cxfreeze\OpenIDCS-Client.exe" (
    echo [ERROR] 找不到可执行文件
    echo 路径: BuildCache\cxfreeze\OpenIDCS-Client.exe
    pause
    exit /b 1
)

REM 获取版本号（从 build_cxfreeze.py 中读取）
set VERSION=1.0.0
for /f "tokens=2 delims==" %%a in ('findstr /C:"PROJECT_VERSION" "%PROJECT_ROOT%\AllBuilder\build_cxfreeze.py"') do (
    set VERSION=%%a
    set VERSION=!VERSION:"=!
    set VERSION=!VERSION: =!
)

REM 创建发布包文件名
set RELEASE_NAME=OpenIDCS-Client-v%VERSION%-winnt-x64-cxfreeze.zip

REM 删除旧的发布包
if exist "%RELEASE_NAME%" (
    echo [INFO] 删除旧的发布包...
    del /q "%RELEASE_NAME%"
)

REM 创建发布包
echo [INFO] 正在创建发布包...
echo [INFO] 文件名: %RELEASE_NAME%
powershell -Command "Compress-Archive -Path 'cxfreeze\*' -DestinationPath '%RELEASE_NAME%' -Force"
if errorlevel 1 (
    echo [WARN] 发布包创建失败（可能是 PowerShell 版本问题）
    echo [INFO] 您可以手动压缩 BuildCache\cxfreeze\ 目录
) else (
    echo [OK] 发布包创建完成
)
echo.

REM ============================================================================
REM 完成
REM ============================================================================

echo ============================================================
echo [SUCCESS] 打包完成！
echo ============================================================
echo.
echo 输出信息:
echo   - 可执行文件: BuildCache\cxfreeze\OpenIDCS-Client.exe
echo   - 发布包: BuildCache\%RELEASE_NAME%
echo.
echo 文件大小:
for %%A in ("%PROJECT_ROOT%\BuildCache\cxfreeze\OpenIDCS-Client.exe") do (
    set size=%%~zA
    set /a sizeMB=!size! / 1048576
    echo   - 可执行文件: !sizeMB! MB
)
if exist "%RELEASE_NAME%" (
    for %%A in ("%RELEASE_NAME%") do (
        set size=%%~zA
        set /a sizeMB=!size! / 1048576
        echo   - 发布包: !sizeMB! MB
    )
)
echo.
echo 下一步:
echo   1. 测试可执行文件: cd BuildCache\cxfreeze ^&^& OpenIDCS-Client.exe
echo   2. 访问 http://localhost:1880 测试应用
echo   3. 如果测试通过，可以分发发布包
echo.
echo ============================================================

REM 询问是否立即测试
set /p test="是否立即测试可执行文件? (y/n): "
if /i "%test%"=="y" (
    echo.
    echo [INFO] 启动应用...
    cd "%PROJECT_ROOT%\BuildCache\cxfreeze"
    start OpenIDCS-Client.exe
    echo.
    echo [INFO] 应用已启动
    echo [INFO] 请访问 http://localhost:1880 测试
    echo.
)

pause
