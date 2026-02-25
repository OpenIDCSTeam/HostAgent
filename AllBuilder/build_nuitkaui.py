#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Nuitka打包脚本 - OpenIDCS Client
使用Nuitka将Flask应用打包成独立可执行文件
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

# 设置控制台编码（Windows）
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 项目配置
PROJECT_NAME = "OpenIDCS-Client"
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MAIN_SCRIPT = os.path.join(PROJECT_ROOT, "MainServer.py")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "BuildCache", "nuitka")
ICON_FILE = os.path.join(PROJECT_ROOT, "HostConfig/HostManage.ico")

# 需要包含的数据目录
DATA_DIRS = [
    "WebDesigns",
    "VNCConsole/Sources",
    "HostConfig",
]

# 需要包含的数据文件
DATA_FILES = [
    "HostConfig/HostManage.sql",
]

# 需要包含的Python包（核心依赖）
CORE_PACKAGES = [
    "flask",
    "loguru",
    "requests",
    "psutil",
    "GPUtil",
    "cpuinfo",
    "setuptools",  # 会自动包含，且可能依赖已移除的distutils
    "py7zr",
    "sqlite3",
    "email",
    "smtplib",
    "jinja2",
    "werkzeug",
    "click",
    "itsdangerous",
    "markupsafe",
]

# 可选包（如果已安装则包含）
OPTIONAL_PACKAGES = [
    "pythonnet",  # Windows .NET 支持
    "pyvmomi",    # VMware vSphere 支持
    "pylxd",      # LXD 容器支持
    "docker",     # Docker 容器支持
]

# 需要包含的模块
INCLUDE_MODULES = [
    "HostModule",
    "HostServer",
    "MainObject",
    "VNCConsole",
    "Websockify",
]

# 需要排除的包（减小体积）
EXCLUDE_PACKAGES = [
    "tkinter",
    "test",
    "unittest",
    "distutils",  # Python 3.12+ 已移除，避免依赖包尝试导入
    "setuptools.tests",
    "websockify",  # 排除外部的 websockify，使用本地的 Websockify 模块
]


def check_package_installed(package_name):
    """检查包是否已安装"""
    try:
        __import__(package_name)
        return True
    except ImportError:
        return False


def get_installed_packages():
    """获取已安装的可选包列表"""
    installed = []
    for package in OPTIONAL_PACKAGES:
        if check_package_installed(package):
            installed.append(package)
    return installed


def build_nuitka_command():
    """构建Nuitka命令行参数"""
    
    # 获取已安装的可选包
    installed_optional = get_installed_packages()
    all_packages = CORE_PACKAGES + installed_optional
    
    print("包含的包:")
    print(f"  核心包: {len(CORE_PACKAGES)} 个")
    for pkg in CORE_PACKAGES:
        print(f"    - {pkg}")
    
    if installed_optional:
        print(f"  可选包: {len(installed_optional)} 个")
        for pkg in installed_optional:
            print(f"    - {pkg} [已安装]")
    
    skipped = [pkg for pkg in OPTIONAL_PACKAGES if pkg not in installed_optional]
    if skipped:
        print(f"  跳过的包（未安装）: {len(skipped)} 个")
        for pkg in skipped:
            print(f"    - {pkg} (未安装)")
    print()
    
    # 获取CPU核心数用于并行编译
    cpu_count = os.cpu_count() or 8  # 如果无法获取，默认使用4
    
    cmd = [
        sys.executable,
        "-m", "nuitka",
        "--standalone",  # 独立模式，包含所有依赖
        "--onefile",  # 打包成单个可执行文件
        f"--output-dir={OUTPUT_DIR}",
        "--assume-yes-for-downloads",  # 自动下载依赖
        "--show-progress",  # 显示进度
        "--show-memory",  # 显示内存使用
        f"--jobs={cpu_count}",  # 使用多线程编译（根据CPU核心数）
        
        # Windows特定选项
        "--windows-console-mode=force",  # 强制显示控制台（确保可以看到日志和错误）
        # "--windows-console-mode=disable",  # 如果不需要控制台，取消上面的注释，使用这个
        
        # 图标
        f"--windows-icon-from-ico={ICON_FILE}",
        
        # 输出文件名
        f"--output-filename={PROJECT_NAME}.exe",
        
        # 启用插件
        "--enable-plugin=anti-bloat",  # 减小体积
        
        # 包含包
    ]
    
    # 添加需要包含的包（核心包 + 已安装的可选包）
    for package in all_packages:
        cmd.append(f"--include-package={package}")
    
    # 添加需要包含的模块
    for module in INCLUDE_MODULES:
        cmd.append(f"--include-package={module}")
    
    # 添加需要排除的包
    for package in EXCLUDE_PACKAGES:
        cmd.append(f"--nofollow-import-to={package}")
    
    # 添加数据目录
    for data_dir in DATA_DIRS:
        full_path = os.path.join(PROJECT_ROOT, data_dir)
        if os.path.exists(full_path):
            cmd.append(f"--include-data-dir={full_path}={data_dir}")
    
    # 添加数据文件
    for data_file in DATA_FILES:
        full_path = os.path.join(PROJECT_ROOT, data_file)
        if os.path.exists(full_path):
            cmd.append(f"--include-data-file={full_path}={data_file}")
    
    # 主脚本
    cmd.append(MAIN_SCRIPT)
    
    return cmd


def check_nuitka_installed():
    """检查Nuitka是否已安装"""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "nuitka", "--version"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print(f"[OK] Nuitka已安装: {result.stdout.strip()}")
            return True
        else:
            print("[ERROR] Nuitka未安装")
            return False
    except Exception as e:
        print(f"[ERROR] 检查Nuitka时出错: {e}")
        return False


def install_nuitka():
    """安装Nuitka"""
    print("正在安装Nuitka...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-U", "nuitka"],
            check=True
        )
        print("[OK] Nuitka安装成功")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Nuitka安装失败: {e}")
        return False


def clean_build_dir():
    """清理构建目录"""
    if os.path.exists(OUTPUT_DIR):
        print(f"清理构建目录: {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR)


def main():
    """主函数"""
    print("=" * 60)
    print(f"OpenIDCS Client - Nuitka打包工具")
    print("=" * 60)
    print()
    print(f"项目根目录: {PROJECT_ROOT}")
    print()
    
    # 切换到项目根目录
    os.chdir(PROJECT_ROOT)
    
    # 检查主脚本是否存在
    if not os.path.exists(MAIN_SCRIPT):
        print(f"[ERROR] 错误: 找不到主脚本 {MAIN_SCRIPT}")
        sys.exit(1)
    
    # 检查Nuitka
    if not check_nuitka_installed():
        response = input("是否安装Nuitka? (y/n): ")
        if response.lower() == 'y':
            if not install_nuitka():
                sys.exit(1)
        else:
            print("取消打包")
            sys.exit(1)
    
    # 清理旧的构建
    # response = input("是否清理旧的构建目录? (y/n): ")
    # if response.lower() == 'y':
    #     clean_build_dir()
    
    # 构建命令
    cmd = build_nuitka_command()
    
    print()
    print("=" * 60)
    print("开始打包...")
    print("=" * 60)
    print()
    print("执行命令:")
    print(" ".join(cmd))
    print()
    
    # 执行打包
    try:
        # 不使用 check=True，而是手动检查返回码，这样可以看到完整输出
        result = subprocess.run(cmd)
        print()
        if result.returncode == 0:
            print("=" * 60)
            print("[SUCCESS] 打包成功!")
            print(f"输出目录: {OUTPUT_DIR}")
            print("=" * 60)
        else:
            print("=" * 60)
            print(f"[ERROR] 打包失败，退出码: {result.returncode}")
            print("请查看上方的详细错误信息")
            print("=" * 60)
            sys.exit(1)
    except KeyboardInterrupt:
        print()
        print("打包已取消")
        sys.exit(1)


if __name__ == "__main__":
    main()
