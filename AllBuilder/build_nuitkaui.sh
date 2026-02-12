#!/bin/bash
# OpenIDCS Client - Nuitka打包脚本 (Linux/Mac)
# 使用Nuitka将项目打包成独立可执行文件

echo "========================================"
echo "OpenIDCS Client - Nuitka打包工具"
echo "========================================"
echo ""

# 切换到项目根目录
cd ..
echo "项目根目录: $(pwd)"
echo ""

# 检查Python是否安装
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未找到Python3，请先安装Python3"
    exit 1
fi

# 检查主脚本是否存在
if [ ! -f "HostServer.py" ]; then
    echo "[错误] 找不到HostServer.py"
    exit 1
fi

# 检查Nuitka是否安装
if ! python3 -m nuitka --version &> /dev/null; then
    echo "[提示] Nuitka未安装，正在安装..."
    python3 -m pip install -U nuitka
    if [ $? -ne 0 ]; then
        echo "[错误] Nuitka安装失败"
        exit 1
    fi
    echo "[成功] Nuitka安装完成"
    echo ""
fi

# 询问是否清理旧的构建
if [ -d "build_nuitka" ]; then
    echo "发现旧的构建目录"
    read -p "是否清理旧的构建目录? (y/n): " clean
    if [ "$clean" = "y" ] || [ "$clean" = "Y" ]; then
        echo "正在清理..."
        rm -rf build_nuitka
        echo "清理完成"
        echo ""
    fi
fi

echo "========================================"
echo "开始打包..."
echo "========================================"
echo ""
echo "这可能需要几分钟时间，请耐心等待..."
echo ""

# 使用配置文件打包（Linux/Mac版本需要调整一些选项）
python3 -m nuitka \
    --standalone \
    --onefile \
    --jobs=8 \
    --assume-yes-for-downloads \
    --show-progress \
    --show-memory \
    --output-dir=build_nuitka \
    --output-filename=OpenIDCS-Client \
    --enable-plugin=anti-bloat \
    --include-package=flask \
    --include-package=loguru \
    --include-package=requests \
    --include-package=psutil \
    --include-package=GPUtil \
    --include-package=cpuinfo \
    --include-package=setuptools \
    --include-package=py7zr \
    --include-package=pyvmomi \
    --include-package=pylxd \
    --include-package=docker \
    --include-package=jinja2 \
    --include-package=werkzeug \
    --include-package=click \
    --include-package=itsdangerous \
    --include-package=markupsafe \
    --include-package=HostModule \
    --include-package=HostServer \
    --include-package=MainObject \
    --include-package=VNCConsole \
    --include-package=Websockify \
    --nofollow-import-to=tkinter \
    --nofollow-import-to=test \
    --nofollow-import-to=unittest \
    --include-data-dir=WebDesigns=WebDesigns \
    --include-data-dir=VNCConsole/Sources=VNCConsole/Sources \
    --include-data-dir=HostConfig=HostConfig \
    --include-data-file=HostConfig/HostManage.sql=HostConfig/HostManage.sql \
    MainServer.py

if [ $? -ne 0 ]; then
    echo ""
    echo "========================================"
    echo "[错误] 打包失败"
    echo "========================================"
    exit 1
fi

echo ""
echo "========================================"
echo "[成功] 打包完成!"
echo "输出目录: build_nuitka"
echo "========================================"
echo ""

# 显示生成的文件
if [ -f "build_nuitka/OpenIDCS-Client" ]; then
    echo "可执行文件: build_nuitka/OpenIDCS-Client"
    ls -lh "build_nuitka/OpenIDCS-Client"
    
    # 添加执行权限
    chmod +x "build_nuitka/OpenIDCS-Client"
    echo "已添加执行权限"
fi

echo ""
echo "完成!"
