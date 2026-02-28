# HSEngine - 宿主机引擎配置 ######################################################
# 定义各种虚拟化平台的配置和限制
################################################################################
import HostServer.Workstation as WorkstationModule
import HostServer.LXContainer as LXContainerModule
import HostServer.OCInterface as OCInterfaceModule
import HostServer.vSphereESXi as vSphereESXiModule
import HostServer.VirtualBoxs as VirtualBoxsModule
import HostServer.QEMUService as QEMUServerModule
import HostServer.MemuAndroid as MemuAndroidModule
from HostServer import ProxmoxQemu, Win64HyperV, QingzhouYun

HEConfig = {
    "VMWareSetup": {
        "Imported": WorkstationModule.HostServer,
        "Descript": "VMWare Workstation",
        "isEnable": True,
        "isRemote": False,
        "Platform": ["Windows"],
        "CPU_Arch": ["x86_64"],
        "Optional": {},
        "Messages": [
            "1、不支持PCI设备直通，但可分配虚拟显存",
            "2、支持USB设备直通"
        ],
        "Ban_Init": [
            "gpu_num"
        ],
        "Ban_Edit": [
            "gpu_num"
        ],
        "Tab_Lock": [
            "pci"
        ]
    },
    "LxContainer": {
        "Imported": LXContainerModule.HostServer,
        "Descript": "LinuxContainer Env",
        "isEnable": True,
        "isRemote": True,
        "Platform": ["Linux"],
        "CPU_Arch": ["x86_64", "aarch64"],
        "Optional": {},
        "Messages": [
            "1、不支持分配GPU设备，不支持设置显存的大小",
            "2、不支持挂载ISO镜像、不支持挂载额外的硬盘",
            "3、不支持PCI和USB设备直通"
        ],
        "Ban_Init": [
            "gpu_num", "gpu_mem",
        ],
        "Ban_Edit": [
            "gpu_num", "gpu_mem",
            "flu_num", "hdd_num",
            "speed_u", "speed_d",
        ],
        "Tab_Lock": [
            "hdd", "iso", "pci", "usb"
        ]
    },
    "OCInterface": {
        "Imported": OCInterfaceModule.HostServer,
        "Descript": "Docker Runtime Env",
        "isEnable": True,
        "isRemote": True,
        "Platform": ["Linux", "MacOS"],
        "CPU_Arch": ["x86_64", "aarch64"],
        "Optional": {},
        "Messages": [
            "1、不支持分配GPU设备，不支持设置显存的大小",
            "2、不支持挂载ISO镜像、不支持挂载额外的硬盘",
            "3、不支持PCI和USB设备直通"
        ],
        "Ban_Init": [
            "gpu_num", "gpu_mem",
        ],
        "Ban_Edit": [
            "gpu_num", "gpu_mem",
            "flu_num", "hdd_num",
            "speed_u", "speed_d",
        ],
        "Tab_Lock": [
            "hdd", "iso", "pci", "usb"
        ]
    },
    "vSphereESXi": {
        "Imported": vSphereESXiModule.HostServer,
        "Descript": "vSphereESXi Server",
        "isEnable": True,
        "isRemote": True,
        "Platform": ["Linux", "Windows", "MacOS"],
        "CPU_Arch": ["x86_64", "aarch64"],
        "Optional": {},
        "Messages": [],
        "Ban_Init": [],
        "Ban_Edit": [],
        "Tab_Lock": [
        ]
    },
    "HyperVSetup": {
        "Imported": Win64HyperV.HostServer,
        "Descript": "Windows HyperV x64",
        "isEnable": True,
        "isRemote": True,
        "Platform": ["Windows"],
        "CPU_Arch": ["x86_64"],
        "Messages": [
            "1、无法单独限制上下行带宽，取二者最低值分配",
            "2、不支持USB直通，支持GPU PV和DDA设备直通"
        ],
        "Ban_Init": [],
        "Ban_Edit": [],
        "Tab_Lock": [
            "usb"
        ]
    },
    "PromoxSetup": {
        "Imported": ProxmoxQemu.HostServer,
        "Descript": "ProxmoxVE Platform",
        "isEnable": True,
        "isRemote": True,
        "Platform": ["Linux", "Windows"],
        "CPU_Arch": ["x86_64", "aarch64"],
        "Messages": [],
        "Ban_Init": [],
        "Ban_Edit": [],
        "Tab_Lock": []
    },
    "QingzhouYun": {
        "Imported": QingzhouYun.HostServer,
        "Descript": "QingzhouYun Cloud",
        "isEnable": True,
        "isRemote": True,
        "Platform": ["Linux", "Windows", "MacOS"],
        "CPU_Arch": ["x86_64", "aarch64"],
        "Optional": {},
        "Messages": [
            "1、云平台不支持PCI/USB设备直通",
            "2、通过HTTP API远程管理虚拟机"
        ],
        "Ban_Init": [
            "gpu_num", "gpu_mem",
        ],
        "Ban_Edit": [
            "gpu_num", "gpu_mem",
        ],
        "Tab_Lock": [
            "pci", "usb"
        ]
    },
    "VirtualBoxs": {
        "Imported": VirtualBoxsModule.HostServer,
        "Descript": "Oracle VirtualBox",
        "isEnable": True,
        "isRemote": False,
        "Platform": ["Linux", "Windows", "MacOS"],
        "CPU_Arch": ["x86_64", "aarch64"],
        "Optional": {},
        "Messages": [
            "1、通过VBoxManage命令行管理虚拟机",
            "2、支持USB设备直通（需要VirtualBox扩展包）",
            "3、远程桌面通过VRDE（RDP协议）实现"
        ],
        "Ban_Init": [
            "gpu_num"
        ],
        "Ban_Edit": [
            "gpu_num"
        ],
        "Tab_Lock": [
            "pci"
        ]
    },
    "QEMUServer": {
        "Imported": QEMUServerModule.HostServer,
        "Descript": "QEMU/KVM Platform",
        "isEnable": True,
        "isRemote": True,
        "Platform": ["Linux"],
        "CPU_Arch": ["x86_64", "aarch64"],
        "Optional": {},
        "Messages": [
            "1、通过virsh/libvirt管理QEMU/KVM虚拟机",
            "2、支持PCI/USB设备直通",
            "3、VNC远程桌面（自动分配端口）",
            "4、修改密码需要虚拟机安装qemu-guest-agent"
        ],
        "Ban_Init": [],
        "Ban_Edit": [],
        "Tab_Lock": []
    },
    "MemuAndroid": {
        "Imported": MemuAndroidModule.HostServer,
        "Descript": "MEmu Game Emulator",
        "isEnable": True,
        "isRemote": False,
        "Platform": ["Windows"],
        "CPU_Arch": ["x86_64"],
        "Optional": {
            "graphics_render_mode": "图形渲染模式(1:DirectX, 0:OpenGL)",
            "enable_su": "是否以超级用户权限启动(1:是, 0:否)",
            "enable_audio": "是否启用音频(1:是, 0:否)",
            "fps": "帧率(如30, 60)"
        },
        "Messages": [
            "1、通过memuc命令行管理逍遥安卓模拟器",
            "2、不支持额外硬盘挂载，ISO挂载替换为APK安装",
            "3、不支持暂停/恢复操作",
            "4、VNC替换为ADB连接信息"
        ],
        "Ban_Init": [
            "gpu_num", "gpu_mem", "hdd_num",
            "speed_u", "speed_d"
        ],
        "Ban_Edit": [
            "gpu_num", "gpu_mem", "hdd_num",
            "speed_u", "speed_d"
        ],
        "Tab_Lock": [
            "hdd", "pci", "usb"
        ]
    }
}