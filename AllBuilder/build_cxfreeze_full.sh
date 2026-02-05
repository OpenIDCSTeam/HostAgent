#!/bin/bash
################################################################################
# OpenIDCS-Client 完整打包脚本 (Python 后端 + React 前端)
# 使用 cx-Freeze 打包
# 支持 Linux 和 macOS
################################################################################

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印函数
print_header() {
    echo -e "${BLUE}============================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}============================================================${NC}"
    echo
}

print_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# 获取项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

print_header "OpenIDCS-Client 完整打包流程"
echo "Python 后端 + React 前端"
echo

################################################################################
# 步骤 1：检查环境
################################################################################

print_header "[步骤 1/5] 检查环境..."

# 检查 Python
if ! command -v python3 &> /dev/null; then
    print_error "Python3 未安装"
    echo "请安装 Python 3.7 或更高版本"
    exit 1
fi
print_success "Python 已安装"
python3 --version
echo

# 检查 Node.js
if ! command -v node &> /dev/null; then
    print_error "Node.js 未安装"
    echo "请从 https://nodejs.org/ 下载并安装 Node.js LTS 版本"
    exit 1
fi
print_success "Node.js 已安装"
node --version
npm --version
echo

# 检查 cx-Freeze
if ! python3 -c "import cx_Freeze" &> /dev/null; then
    print_warning "cx-Freeze 未安装"
    echo
    read -p "是否安装 cx-Freeze? (y/n): " install
    if [[ "$install" == "y" || "$install" == "Y" ]]; then
        print_info "正在安装 cx-Freeze..."
        python3 -m pip install cx-Freeze
        if [ $? -ne 0 ]; then
            print_error "cx-Freeze 安装失败"
            exit 1
        fi
        print_success "cx-Freeze 安装成功"
    else
        echo "取消打包"
        exit 1
    fi
else
    print_success "cx-Freeze 已安装"
fi
echo

################################################################################
# 步骤 2：构建 React 前端
################################################################################

print_header "[步骤 2/5] 构建 React 前端..."

cd "$PROJECT_ROOT/FrontPages"

# 检查 node_modules 是否存在
if [ ! -d "node_modules" ]; then
    print_info "首次构建，正在安装前端依赖..."
    npm install
    if [ $? -ne 0 ]; then
        print_error "前端依赖安装失败"
        exit 1
    fi
    print_success "前端依赖安装完成"
    echo
fi

# 构建前端
print_info "正在构建 React 前端..."
npm run build
if [ $? -ne 0 ]; then
    echo
    print_error "前端构建失败"
    echo "请检查前端代码是否有错误"
    exit 1
fi

echo
print_success "前端构建完成"
print_info "输出目录: FrontPages/dist/"
echo

################################################################################
# 步骤 3：复制前端产物到后端静态目录
################################################################################

print_header "[步骤 3/5] 复制前端产物到后端静态目录..."

cd "$PROJECT_ROOT"

# 创建静态目录（如果不存在）
if [ ! -d "static" ]; then
    print_info "创建 static 目录..."
    mkdir -p static
fi

# 清空旧的静态文件
print_info "清理旧的静态文件..."
rm -rf static/*

# 复制前端构建产物
print_info "复制前端构建产物..."
cp -r FrontPages/dist/* static/
if [ $? -ne 0 ]; then
    print_error "复制前端产物失败"
    exit 1
fi

print_success "前端产物复制完成"
print_info "目标目录: static/"
echo

# 显示复制的文件
print_info "静态文件列表:"
ls -1 static/
echo

################################################################################
# 步骤 4：打包 Python 后端
################################################################################

print_header "[步骤 4/5] 打包 Python 后端..."

cd "$PROJECT_ROOT/AllBuilder"

# 清理旧的构建
if [ -d "$PROJECT_ROOT/BuildCache/cxfreeze" ]; then
    print_info "清理旧的构建目录..."
    rm -rf "$PROJECT_ROOT/BuildCache/cxfreeze"
fi

# 开始打包
print_info "正在打包 Python 后端（包含 React 前端）..."
print_info "这可能需要几分钟时间，请耐心等待..."
echo

python3 build_cxfreeze.py build

if [ $? -ne 0 ]; then
    echo
    print_header "[ERROR] 后端打包失败"
    echo
    echo "可能的原因:"
    echo "1. 缺少必要的 Python 依赖包"
    echo "2. build_cxfreeze.py 配置有误"
    echo "3. 磁盘空间不足"
    echo
    echo "请检查错误信息并重试"
    exit 1
fi

echo
print_success "后端打包完成"
print_info "输出目录: BuildCache/cxfreeze/"
echo

################################################################################
# 步骤 5：创建发布包
################################################################################

print_header "[步骤 5/5] 创建发布包..."

cd "$PROJECT_ROOT/BuildCache"

# 检查构建输出是否存在
EXECUTABLE_NAME="OpenIDCS-Client"
if [ ! -f "cxfreeze/$EXECUTABLE_NAME" ]; then
    print_error "找不到可执行文件"
    print_info "路径: BuildCache/cxfreeze/$EXECUTABLE_NAME"
    exit 1
fi

# 获取版本号（从 build_cxfreeze.py 中读取）
VERSION=$(grep "PROJECT_VERSION" "$PROJECT_ROOT/AllBuilder/build_cxfreeze.py" | cut -d'"' -f2)
if [ -z "$VERSION" ]; then
    VERSION="1.0.0"
fi

# 获取系统类型
OS_TYPE=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)

# 创建发布包文件名
RELEASE_NAME="OpenIDCS-Client-v${VERSION}-${OS_TYPE}-${ARCH}-cxfreeze.tar.gz"

# 删除旧的发布包
if [ -f "$RELEASE_NAME" ]; then
    print_info "删除旧的发布包..."
    rm -f "$RELEASE_NAME"
fi

# 创建发布包
print_info "正在创建发布包..."
print_info "文件名: $RELEASE_NAME"
tar -czf "$RELEASE_NAME" -C cxfreeze .
if [ $? -ne 0 ]; then
    print_warning "发布包创建失败"
    print_info "您可以手动压缩 BuildCache/cxfreeze/ 目录"
else
    print_success "发布包创建完成"
fi
echo

################################################################################
# 完成
################################################################################

print_header "[SUCCESS] 打包完成！"
echo
echo "输出信息:"
echo "  - 可执行文件: BuildCache/cxfreeze/$EXECUTABLE_NAME"
echo "  - 发布包: BuildCache/$RELEASE_NAME"
echo

# 显示文件大小
if [ -f "cxfreeze/$EXECUTABLE_NAME" ]; then
    SIZE=$(du -h "cxfreeze/$EXECUTABLE_NAME" | cut -f1)
    echo "文件大小:"
    echo "  - 可执行文件: $SIZE"
fi

if [ -f "$RELEASE_NAME" ]; then
    SIZE=$(du -h "$RELEASE_NAME" | cut -f1)
    echo "  - 发布包: $SIZE"
fi
echo

echo "下一步:"
echo "  1. 测试可执行文件: cd BuildCache/cxfreeze && ./$EXECUTABLE_NAME"
echo "  2. 访问 http://localhost:1880 测试应用"
echo "  3. 如果测试通过，可以分发发布包"
echo
print_header "============================================================"

# 询问是否立即测试
read -p "是否立即测试可执行文件? (y/n): " test
if [[ "$test" == "y" || "$test" == "Y" ]]; then
    echo
    print_info "启动应用..."
    cd "$PROJECT_ROOT/BuildCache/cxfreeze"
    ./$EXECUTABLE_NAME &
    echo
    print_info "应用已启动"
    print_info "请访问 http://localhost:1880 测试"
    echo
fi
