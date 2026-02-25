from cx_Freeze import setup, Executable

# 设置你的程序名称和版本
program_name = "Open IDC Service Client"
program_version = "1.0"

# 指定你的主程序文件
main_script = "MainServer.py"

# 配置 cx_Freeze
setup(
    name=program_name,
    version=program_version,
    description="Open IDC Service Client",
    executables=[Executable(main_script, icon="HostConfig/HostManage.ico")],
    options={
        "build_exe": {
            # 包含的文件和模块
            "include_files": [
                "WebDesigns",
                ("VNCConsole/Sources", "VNCConsole/Sources"),
                ("HostConfig/HostManage.sql", "HostConfig/HostManage.sql")
            ],
            "packages": [
                "GPUtil",
                "psutil",
                "cpuinfo",
                "pywin32",
                "setuptools",
                "pythonnet",
                "requests",
                "flask",
                "websockify",
                "loguru",
            ],
            "includes": [
                "setuptools._distutils",
                "setuptools._distutils.spawn",
                "setuptools._distutils.core",
                "setuptools._distutils.util",
            ],
            # 添加初始化脚本
            "include_msvcr": True,
            # 排除的文件和模块
            "excludes": [],
            "zip_include_packages": ["*"],
            "zip_exclude_packages": [],
            # 目标平台（可选,通常自动检测）
        }
    }
)