import json
import random

from MainObject.Config.BootOpts import BootOpts
from MainObject.Config.IMConfig import IMConfig
from MainObject.Config.NCConfig import NCConfig
from MainObject.Config.PortData import PortData
from MainObject.Config.SDConfig import SDConfig
from MainObject.Config.USBInfos import USBInfos
from MainObject.Config.UserMask import UserMask
from MainObject.Config.VFConfig import VFConfig
from MainObject.Config.VMBackup import VMBackup
from MainObject.Config.VMPowers import VMPowers
from MainObject.Config.WebProxy import WebProxy


class VMConfig:
    @staticmethod
    def random_conn_port():
        """生成随机VNC端口，范围5900-6999"""
        return str(random.randint(5900, 6999))

    # 初始化 #################################
    def __init__(self, **kwargs):
        # 机器配置 ===========================
        self.vm_uuid = ""  # 设置虚拟机名-UUID
        self.vm_flag = VMPowers.UNKNOWN  # PWR
        self.os_name = ""  # 设置SYS操作系统名
        self.os_pass = ""  # 设置SYS系统的密码
        # 远程连接 ===========================
        self.vc_port = self.random_conn_port()
        self.vc_pass = ""  # 分配VNC远程的密码
        # 资源配置 ===========================
        self.cpu_num = 2  # 分配的处理器核心数
        self.cpu_per = 0  # 分配处理器可用比例
        self.gpu_mem = 0  # 分配虚拟显存值(MB)
        self.mem_num = 2048  # 分配内存数-(MB)
        self.hdd_num = 8192  # 分配硬盘数-(MB)
        self.hdd_iop = 1000  # 分配硬盘可用IOP
        # 网络配置 ===========================
        self.speed_u = 100  # VM上行带宽(Mbps)
        self.speed_d = 100  # VM下行带宽(Mbps)
        self.nat_num = 100  # VM分配端口(默认)
        self.web_num = 100  # VM分配代理(默认)
        self.flu_num = 102400  # VM分配流量(M)
        # 31天后重置，超限10M，上次重置-时间戳
        self.flu_rst: list[int] = [31, 10, 10]
        # 附加配置 ===========================
        self.nic_all: dict[str, NCConfig] = {}
        self.hdd_all: dict[str, SDConfig] = {}
        self.iso_all: dict[str, IMConfig] = {}
        self.pci_all: dict[str, VFConfig] = {}
        self.usb_all: dict[str, USBInfos] = {}
        self.efi_all: list[BootOpts] = []
        self.nat_all: list[PortData] = []
        self.web_all: list[WebProxy] = []
        self.backups: list[VMBackup] = []
        self.own_all: dict[str, UserMask] = {
            "admin": UserMask(
                pwr_edits=True,  # 是否允许编辑电源
                pwd_edits=True,  # 是否允许编辑密码
                sys_edits=True,  # 是否允许编辑系统
                nic_edits=True,  # 是否允许编辑网卡
                iso_edits=True,  # 是否允许编辑光盘
                hdd_edits=True,  # 是否允许编辑硬盘
                net_edits=True,  # 是否允许编辑网络
                web_edits=True,  # 是否允许编辑网页
                vnc_edits=True,  # 是否允许控制桌面
                pci_edits=True,  # 是否允许编辑PCIe
                usb_edits=True,  # 是否允许编辑USBs
                vm_backup=True,  # 是否允许备份还原
                efi_edits=True,  # 是否允许管理启动
                vm_modify=True,  # 是否允许修改配置
                vm_delete=True,  # 是否允许删除实例
                firewalls=True,  # 是否可编辑防火墙
            )
        }

        # 加载数据 ===========================
        self.__load__(**kwargs)

    # 加载数据 ###############################
    def __load__(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        # 加载数据 ===========================
        nic_list = self.nic_all
        hdd_list = self.hdd_all
        gpu_list = self.pci_all
        usb_list = self.usb_all
        nat_list = self.nat_all
        web_list = self.web_all
        iso_list = self.iso_all
        bak_list = self.backups
        efi_list = self.efi_all
        self.nic_all = {}
        self.hdd_all = {}
        self.pci_all = {}
        self.usb_all = {}
        self.iso_all = {}
        self.nat_all = []
        self.web_all = []
        self.backups = []
        self.efi_all = []
        # 网卡数据 ===========================
        for nic in nic_list:
            nic_data = nic_list[nic]
            if type(nic_data) is dict:
                self.nic_all[nic] = NCConfig(
                    **nic_data)
            else:
                self.nic_all[nic] = nic_data
        # 硬盘数据 ===========================
        for hdd in hdd_list:
            hdd_data = hdd_list[hdd]
            if type(hdd_data) is dict:
                self.hdd_all[hdd] = SDConfig(
                    **hdd_data)
            else:
                self.hdd_all[hdd] = hdd_data
        # 显卡数据 ===========================
        for gpu in gpu_list:
            gpu_data = gpu_list[gpu]
            if type(gpu_data) is dict:
                self.pci_all[gpu] = VFConfig(
                    **gpu_data)
            else:
                self.pci_all[gpu] = gpu_data
        # USB数据 ===========================
        for usb in usb_list:
            usb_data = usb_list[usb]
            if type(usb_data) is dict:
                self.usb_all[usb] = USBInfos(
                    **usb_data)
            else:
                self.usb_all[usb] = usb_data
        # 镜像数据 ===========================
        for iso in iso_list:
            iso_data = iso_list[iso]
            if type(iso_data) is dict:
                self.iso_all[iso] = IMConfig(
                    **iso_data)
            else:
                self.iso_all[iso] = iso_data
        # 端口数据 ===========================
        for nat in nat_list:
            if type(nat) is dict:
                nat_obj = PortData()
                nat_obj.__load__(**nat)
                self.nat_all.append(nat_obj)
            else:
                self.nat_all.append(nat)
        # 代理数据 ===========================
        for web in web_list:
            if type(web) is dict:
                web_obj = WebProxy()
                web_obj.__load__(**web)
                self.web_all.append(web_obj)
            else:
                self.web_all.append(web)
        # 备份数据 ===========================
        for bak in bak_list:
            if type(bak) is dict:
                bak_obj = VMBackup()
                bak_obj.__load__(**bak)
                self.backups.append(bak_obj)
            else:
                self.backups.append(bak)
        # 启动项数据 ===========================
        for efi in efi_list:
            if type(efi) is dict:
                self.efi_all.append(BootOpts(**efi))
            elif isinstance(efi, BootOpts):
                self.efi_all.append(efi)
        if type(self.vm_flag) is str:
            self.vm_flag = VMPowers.from_json(self.vm_flag)
        # 所有者数据 ===========================
        own_data = self.own_all
        self.own_all = {}
        if isinstance(own_data, list):
            # 兼容旧格式: list[str] -> dict[str, UserMask(全权限)]
            for username in own_data:
                self.own_all[username] = UserMask.full()
        elif isinstance(own_data, dict):
            for username, mask_data in own_data.items():
                if isinstance(mask_data, UserMask):
                    self.own_all[username] = mask_data
                elif isinstance(mask_data, int):
                    # 掩码数字 -> UserMask
                    self.own_all[username] = UserMask(mask_data)
                elif isinstance(mask_data, dict):
                    # 字典格式 -> UserMask
                    self.own_all[username] = UserMask(**mask_data)
                else:
                    self.own_all[username] = UserMask.full()
        if not self.own_all:
            self.own_all = {"admin": UserMask.full()}

    # 读取数据 ###############################
    def __read__(self, data: dict):
        for key, value in data.items():
            if key in self.__dict__:
                setattr(self, key, value)

    # 转换字典 ###############################
    def __save__(self):
        return {
            "vm_uuid": self.vm_uuid,
            "os_name": self.os_name,
            "os_pass": self.os_pass,
            "vm_flag": str(self.vm_flag),
            # 资源配置 =======================
            "cpu_num": self.cpu_num,
            "cpu_per": self.cpu_per,
            "gpu_mem": self.gpu_mem,
            "mem_num": self.mem_num,
            "hdd_num": self.hdd_num,
            "hdd_iop": self.hdd_iop,
            # 网络配置 =======================
            "speed_u": self.speed_u,
            "speed_d": self.speed_d,
            "flu_num": self.flu_num,
            "flu_rst": self.flu_rst,
            "nat_num": self.nat_num,
            "web_num": self.web_num,
            # 远程连接 =======================
            "vc_port": self.vc_port,
            "vc_pass": self.vc_pass,
            # 网卡配置 =======================
            "nic_all": {
                k: v.__save__()
                if hasattr(v, '__save__')
                   and callable(
                    getattr(v, '__save__'))
                else v for k, v
                in self.nic_all.items()
            },
            # 硬盘配置 =======================
            "hdd_all": {
                k: v.__save__()
                if hasattr(v, '__save__')
                   and callable(
                    getattr(v, '__save__'))
                else v for k, v
                in self.hdd_all.items()},
            # 显卡配置 =======================
            "pci_all": {
                k: v.__save__()
                if hasattr(v, '__save__')
                   and callable(
                    getattr(v, '__save__'))
                else v for k, v
                in self.pci_all.items()},
            # USB配置 =======================
            "usb_all": {
                k: v.__save__()
                if hasattr(v, '__save__')
                   and callable(
                    getattr(v, '__save__'))
                else v for k, v
                in self.usb_all.items()},
            # 端口配置 =======================
            "nat_all": [
                n.__save__()
                if hasattr(n, '__save__')
                   and callable(
                    getattr(n, '__save__'))
                else n for n
                in self.nat_all],
            # 代理配置 =======================
            "web_all": [
                w.__save__()
                if hasattr(w, '__save__')
                   and callable(
                    getattr(w, '__save__'))
                else w for w in
                self.web_all],
            # 镜像配置 =======================
            "iso_all": {
                k: v.__save__()
                if hasattr(v, '__save__')
                   and callable(
                    getattr(v, '__save__'))
                else v for k, v
                in self.iso_all.items()},
            # 备份配置 =======================
            "backups": [
                b.__save__()
                if hasattr(b, '__save__')
                   and callable(
                    getattr(b, '__save__'))
                else b for b
                in self.backups],
            # 启动项配置 =======================
            "efi_all": [
                e.__save__()
                if hasattr(e, '__save__')
                   and callable(
                    getattr(e, '__save__'))
                else e for e
                in self.efi_all],
            # 所有者配置 =======================
            "own_all": {
                k: v._to_mask()
                if isinstance(v, UserMask)
                else v for k, v
                in self.own_all.items()
            },
        }

    # 转换字符 ###############################
    def __str__(self):
        return json.dumps(self.__save__())
