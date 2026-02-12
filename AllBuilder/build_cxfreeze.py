#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cx-Freeze打包脚本 - OpenIDCS Client
使用cx-Freeze将Flask应用打包成独立可执行文件
"""

import sys
import io

# 设置标准输出为 UTF-8 编码，解决 Windows 控制台中文显示问题
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import os
import subprocess
import shutil
from cx_Freeze import setup, Executable

# 项目根目录（提前定义，前端构建需要用到）
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
PROJECT_BASE_DIR = os.path.abspath(os.path.join(PROJECT_ROOT, ".."))

# ============================================================================
# 前端构建（自动构建React前端并复制到static目录）
# ============================================================================

def build_frontend():
    """构建React前端，直接输出到BuildCache/frontend目录"""
    frontend_dir = os.path.join(PROJECT_BASE_DIR, "FrontPages")
    out_dir = os.path.join(PROJECT_BASE_DIR, "BuildCache", "frontend")
    
    if not os.path.isdir(frontend_dir):
        print("[WARN] 前端目录 FrontPages 不存在，跳过前端构建")
        return False
    
    # 检查 node/npm 是否可用
    try:
        subprocess.run(["node", "--version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("[WARN] 未检测到 Node.js，跳过前端构建")
        return False
    
    print("============================================================")
    print("开始构建前端...")
    print("============================================================")
    
    # 清理旧的构建产物
    if os.path.isdir(out_dir):
        print("[INFO] 清理旧的构建产物...")
        shutil.rmtree(out_dir)
    
    # 安装依赖
    print("[INFO] 安装前端依赖 (npm install)...")
    result = subprocess.run(
        ["npm", "install"],
        cwd=frontend_dir,
        shell=(sys.platform == "win32"),
    )
    if result.returncode != 0:
        print("[ERROR] npm install 失败")
        return False
    print("[OK] 前端依赖安装完成")
    
    # 执行构建，通过 --outDir 直接指定输出到 BuildCache/frontend
    print(f"[INFO] 构建前端 (输出目录: {out_dir})...")
    result = subprocess.run(
        ["npm", "run", "build", "--", "--outDir", out_dir, "--emptyOutDir"],
        cwd=frontend_dir,
        shell=(sys.platform == "win32"),
    )
    if result.returncode != 0:
        print("[ERROR] 前端构建失败")
        return False
    
    if not os.path.isdir(out_dir):
        print("[ERROR] 前端构建产物目录不存在，构建可能失败")
        return False
    
    print("============================================================")
    print("前端构建完成!")
    print("============================================================")
    print("")
    return True

# 仅在执行 build 命令时触发前端构建
if "build" in sys.argv:
    build_frontend()

# 项目配置
PROJECT_NAME = "OpenIDCS-Client"
PROJECT_VERSION = "1.0.0"
PROJECT_DESCRIPTION = "OpenIDCS Flask Server - 虚拟机管理平台"
PROJECT_AUTHOR = "OpenIDCS Team"

# 将项目根目录添加到 Python 路径，使 cx_Freeze 能够找到项目模块
# 因为构建脚本在 AllBuilder 目录中运行，但项目模块在根目录
if PROJECT_BASE_DIR not in sys.path:
    sys.path.insert(0, PROJECT_BASE_DIR)

# 主脚本
MAIN_SCRIPT = os.path.join(PROJECT_BASE_DIR, "MainServer.py")

# 图标文件
ICON_FILE = os.path.join(PROJECT_BASE_DIR, "HostConfig/HostManage.ico")

# ============================================================================
# 需要包含的包和模块
# ============================================================================

# 核心依赖包（基于 requirements.txt）
PACKAGES = [
    # Web框架
    "flask",
    "werkzeug",
    "jinja2",
    "click",
    "itsdangerous",
    "markupsafe",
    
    # 日志
    "loguru",
    
    # HTTP请求
    "requests",
    "urllib3",
    "certifi",
    "charset_normalizer",
    "idna",
    
    # 系统监控
    "psutil",
    "GPUtil",
    "cpuinfo",
    
    # 压缩工具
    "py7zr",
    
    # 数据库
    "sqlite3",
    
    # 邮件
    "email",
    "smtplib",
    
    # 标准库（这些通常会自动包含，但显式列出以确保）
    "encodings",  # 必需：Python 编码支持
    "encodings.utf_8",
    "encodings.ascii",
    "encodings.latin_1",
    "encodings.idna",
    "json",
    "threading",
    "traceback",
    "secrets",
    "functools",
    "hashlib",
    "base64",
    "datetime",
    "pathlib",
    "shutil",
    "subprocess",
    "multiprocessing",
    "os",
    "sys",
    "re",
    "time",
    "socket",
    "ssl",
    "collections",
    "io",
    "typing",
    
    # 项目模块
    "HostModule",
    "HostServer",
    "MainObject",
    "VNCConsole",
    "Websockify",
]

# 可选包（如果已安装则包含，基于 requirements.txt）
OPTIONAL_PACKAGES = [
    "pyvmomi",    # VMware vSphere 支持
    "pylxd",      # LXD 容器支持
    "docker",     # Docker 容器支持
    "pywin32",    # Windows API（仅Windows）
    "pythonnet",  # Windows .NET 支持（仅Windows）
]

# 需要排除的包（减小体积）
EXCLUDES = [
    "tkinter",
    "test",
    "unittest",
    "setuptools",
    "pip",
    "wheel",
    "distutils",
    "numpy",
    "pandas",
    "matplotlib",
    "scipy",
    "IPython",
    "jupyter",
    "notebook",
    "pytest",
    "sphinx",
]

# ============================================================================
# 需要包含的数据文件和目录
# ============================================================================

INCLUDE_FILES = [
    # 前端构建产物（从BuildCache/frontend临时目录读取，打包后映射为static目录）
    (os.path.join(PROJECT_BASE_DIR, "BuildCache", "frontend"), "static") if os.path.exists(os.path.join(PROJECT_BASE_DIR, "BuildCache", "frontend")) else None,
    
    # VNC控制台
    (os.path.join(PROJECT_BASE_DIR, "VNCConsole/Sources"), "VNCConsole/Sources"),
    
    # Websockify 二进制文件
    (os.path.join(PROJECT_BASE_DIR, "Websockify/websocketproxy.exe"), "Websockify/websocketproxy.exe"),
    
    # 配置文件和工具
    (os.path.join(PROJECT_BASE_DIR, "HostConfig"), "HostConfig"),
    
    # 数据库初始化脚本
    (os.path.join(PROJECT_BASE_DIR, "HostConfig/HostManage.sql"), "HostConfig/HostManage.sql"),
]

# 过滤掉None值（不存在的文件）
INCLUDE_FILES = [f for f in INCLUDE_FILES if f is not None]

# ============================================================================
# 检查可选包是否已安装
# ============================================================================

def check_package_installed(package_name):
    """检查包是否已安装"""
    try:
        __import__(package_name)
        return True
    except ImportError:
        return False

# 添加已安装的可选包
installed_optional = []
for package in OPTIONAL_PACKAGES:
    if check_package_installed(package):
        PACKAGES.append(package)
        installed_optional.append(package)
        print(f"[INFO] 包含可选包: {package}")

# ============================================================================
# cx-Freeze构建选项
# ============================================================================

build_exe_options = {
    # 包含的包
    "packages": PACKAGES,
    
    # 排除的包
    "excludes": EXCLUDES,
    
    # 包含的文件
    "include_files": INCLUDE_FILES,
    
    # 优化级别（0=无优化，1=基本优化，2=完全优化）
    "optimize": 2,
    
    # 包含所有依赖的DLL
    "include_msvcr": True,
    
    # 构建目录（挪到项目根目录的 BuildCache 下）
    "build_exe": os.path.join(PROJECT_BASE_DIR, "BuildCache", "cxfreeze"),
    
    # 确保 encodings 和资源目录不被压缩到 zip
    "zip_include_packages": "*",
    "zip_exclude_packages": ["encodings", "VNCConsole", "Websockify"],
    
    # 静默模式（不显示警告）
    # "silent": True,
}

# ============================================================================
# 可执行文件配置
# ============================================================================

# Windows平台特定配置
if sys.platform == "win32":
    base = None  # "Win32GUI" 表示无控制台窗口，None 表示有控制台窗口
    
    executables = [
        Executable(
            script=MAIN_SCRIPT,
            base=base,
            target_name=f"{PROJECT_NAME}.exe",
            icon=ICON_FILE if os.path.exists(ICON_FILE) else None,
            # 版权信息
            copyright=f"Copyright (C) 2024 {PROJECT_AUTHOR}",
            # 快捷方式名称
            shortcut_name=PROJECT_NAME,
            # 快捷方式目录
            shortcut_dir="DesktopFolder",
        )
    ]
else:
    # Linux/Mac平台
    executables = [
        Executable(
            script=MAIN_SCRIPT,
            target_name=PROJECT_NAME,
        )
    ]

# ============================================================================
# setup配置
# ============================================================================

setup(
    name=PROJECT_NAME,
    version=PROJECT_VERSION,
    description=PROJECT_DESCRIPTION,
    author=PROJECT_AUTHOR,
    options={
        "build_exe": build_exe_options,
    },
    executables=executables,
)

# ============================================================================
# 后置步骤：确保前端构建产物复制到后端构建输出目录
# ============================================================================

if "build" in sys.argv:
    frontend = os.path.join(PROJECT_BASE_DIR, "BuildCache", "frontend")
    target_static = os.path.join(PROJECT_BASE_DIR, "BuildCache", "cxfreeze", "static")
    
    if os.path.isdir(frontend):
        # 如果目标目录已存在则先清理
        if os.path.isdir(target_static):
            shutil.rmtree(target_static)
        
        print("[INFO] 复制前端构建产物到后端输出目录...")
        shutil.copytree(frontend, target_static)
        print(f"[OK] 前端产物已复制到 {target_static}")
    else:
        print("[WARN] 前端构建产物不存在，跳过复制")

