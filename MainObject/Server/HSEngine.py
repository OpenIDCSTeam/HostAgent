# HSEngine - 宿主机引擎配置 ######################################################
# 定义各种虚拟化平台的配置和限制
################################################################################
import HostServer.Workstation as WorkstationModule
import HostServer.LXContainer as LXContainerModule
import HostServer.OCInterface as OCInterfaceModule
import HostServer.vSphereESXi as vSphereESXiModule
from HostServer import ProxmoxQemu, Win64HyperV

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
            "1、不支持直通分配GPU设备，但可分配虚拟显存",
            "2、暂不支持获取虚拟机GPU使用率和显存使用率"
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
            "2、不支持挂载ISO镜像、不支持挂载额外的硬盘"
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
            "hdd", "iso"
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
            "2、不支持挂载ISO镜像、不支持挂载额外的硬盘"
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
            "hdd", "iso"
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
            "1、无法单独限制上下行带宽，取二者最低值分配"
        ],
        "Ban_Init": [],
        "Ban_Edit": [],
        "Tab_Lock": []
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
    # "VirtualBoxs": {
    #     "Descript": "PVE Runtime Platform",
    #     "isEnable": False,
    #     "Platform": ["Linux", "Windows"],
    #     "CPU_Arch": ["x86_64", "aarch64"],
    # },
    # "MemuAndroid": {
    #     "Descript": "XYAndroid Simulator",
    #     "isEnable": False,
    #     "Platform": ["Windows"],
    #     "CPU_Arch": ["x86_64"],
    #     "Optional": {
    #         "graphics_render_mode": "图形渲染模式(1:DirectX, 0:OpenGL)",
    #         "enable_su": "是否以超级用户权限启动",
    #         "enable_audio": "是否启用音频",
    #         "fps": "帧率"
    #     }
    # }
}