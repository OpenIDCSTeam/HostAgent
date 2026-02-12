#!/bin/bash
# ============================================================================
# cx-Freeze 打包脚本 (Linux/Mac Shell版本)
# OpenIDCS Client - 前后端一键构建
# ============================================================================

set -e  # 遇到错误立即退出

echo "============================================================"
echo "OpenIDCS Client - cx-Freeze 打包工具 (Linux/Mac)"
echo "前后端一键构建"
echo "============================================================"
echo ""

# 获取脚本所在目录和项目根目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ============================================================================
# 步骤 1：检查环境
# ============================================================================

echo "[步骤 1/3] 检查环境..."
echo ""

# 检查Python是否安装
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python3未安装"
    exit 1
fi
echo "[OK] Python已安装"
python3 --version
echo ""

# 检查Node.js是否安装（前端构建需要）
if ! command -v node &> /dev/null; then
    echo "[WARN] Node.js未安装，将跳过前端构建"
    echo "[WARN] 如需构建前端，请先安装 Node.js: https://nodejs.org/"
    echo ""
else
    echo "[OK] Node.js已安装"
    node --version
    npm --version
    echo ""
fi

# 检查cx-Freeze是否安装
if ! python3 -c "import cx_Freeze" &> /dev/null; then
    echo "[WARN] cx-Freeze未安装"
    echo ""
    read -p "是否安装cx-Freeze? (y/n): " install
    if [ "$install" = "y" ] || [ "$install" = "Y" ]; then
        echo "正在安装cx-Freeze..."
        python3 -m pip install cx-Freeze
        echo "[OK] cx-Freeze安装成功"
    else
        echo "取消打包"
        exit 1
    fi
else
    echo "[OK] cx-Freeze已安装"
fi
echo ""

# ============================================================================
# 步骤 2：清理旧的构建
# ============================================================================

echo "[步骤 2/3] 清理旧的构建..."
echo ""

if [ -d "$PROJECT_ROOT/BuildCache/cxfreeze" ]; then
    echo "清理旧的构建目录..."
    rm -rf "$PROJECT_ROOT/BuildCache/cxfreeze"
fi
echo ""

# ============================================================================
# 步骤 3：开始打包（含前端构建）
# ============================================================================

echo "============================================================"
echo "[步骤 3/3] 开始打包（含前端自动构建）..."
echo "============================================================"
echo ""

cd "$SCRIPT_DIR"
python3 build_cxfreeze.py build

echo ""
echo "============================================================"
echo "[SUCCESS] 打包成功!"
echo "输出目录: BuildCache/cxfreeze/"
echo "============================================================"
echo ""

# 显示生成的文件
if [ -d "$PROJECT_ROOT/BuildCache/cxfreeze" ]; then
    echo "生成的文件:"
    ls -lh "$PROJECT_ROOT/BuildCache/cxfreeze/" | grep -E "OpenIDCS|^d"
    echo ""
fi

# 设置可执行权限
if [ -f "$PROJECT_ROOT/BuildCache/cxfreeze/OpenIDCS-Client" ]; then
    chmod +x "$PROJECT_ROOT/BuildCache/cxfreeze/OpenIDCS-Client"
    echo "[OK] 已设置可执行权限"
fi

echo ""
echo "下一步:"
echo "  1. 测试: cd BuildCache/cxfreeze && ./OpenIDCS-Client"
echo "  2. 访问 http://localhost:1880 测试应用"
echo ""
