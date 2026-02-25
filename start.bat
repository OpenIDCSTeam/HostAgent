@echo off
chcp 65001 >nul
title OpenIDCS 前后端启动脚本

echo ========================================
echo   OpenIDCS 虚拟化管理平台
echo   前后端一键启动脚本
echo ========================================
echo.

:: 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到Python，请先安装Python 3.8+
    pause
    exit /b 1
)

:: 检查Node.js是否安装
node --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到Node.js，请先安装Node.js
    pause
    exit /b 1
)

echo [1/4] 检查环境...
echo ✓ Python已安装
echo ✓ Node.js已安装
echo.

:: 检查前端依赖是否已安装
if not exist "FrontPages\node_modules" (
    echo [2/4] 安装前端依赖...
    cd FrontPages
    call npm install
    if errorlevel 1 (
        echo [错误] 前端依赖安装失败
        cd ..
        pause
        exit /b 1
    )
    cd ..
    echo ✓ 前端依赖安装完成
) else (
    echo [2/4] 前端依赖已安装，跳过
)
echo.

echo [3/4] 启动Flask后端服务器（端口1880）...
start "OpenIDCS Backend" cmd /k "python RunHostServer.py"
timeout /t 3 >nul
echo ✓ 后端服务器已启动
echo.

echo [4/4] 启动React前端开发服务器（端口3000）...
cd FrontPages
start "OpenIDCS Frontend" cmd /k "npm run dev"
cd ..
echo ✓ 前端服务器已启动
echo.

echo ========================================
echo   启动完成！
echo ========================================
echo.
echo 后端地址: http://localhost:1880
echo 前端地址: http://localhost:3000
echo.
echo 提示：
echo - 前端会自动在浏览器中打开
echo - 首次启动请查看后端窗口获取Token
echo - 按Ctrl+C可停止对应的服务
echo.
echo 按任意键关闭此窗口...
pause >nul
