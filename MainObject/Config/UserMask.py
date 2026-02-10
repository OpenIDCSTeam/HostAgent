import enum


class MaskCode(enum.Enum):
    PWR_EDITS = 1
    PWD_EDITS = 2
    SYS_EDITS = 4
    NIC_EDITS = 8
    ISO_EDITS = 16
    HDD_EDITS = 32
    NET_EDITS = 64
    WEB_EDITS = 128
    VNC_EDITS = 256
    PCI_EDITS = 512
    USB_EDITS = 1024
    VM_BACKUP = 2048
    VM_GRANTS = 4096
    VM_MODIFY = 8192
    VM_DELETE = 16384
    FIREWALLS = 32768


# 属性名到MaskCode的映射
_FIELD_TO_MASK = {
    "pwr_edits": MaskCode.PWR_EDITS,
    "pwd_edits": MaskCode.PWD_EDITS,
    "sys_edits": MaskCode.SYS_EDITS,
    "nic_edits": MaskCode.NIC_EDITS,
    "iso_edits": MaskCode.ISO_EDITS,
    "hdd_edits": MaskCode.HDD_EDITS,
    "net_edits": MaskCode.NET_EDITS,
    "web_edits": MaskCode.WEB_EDITS,
    "vnc_edits": MaskCode.VNC_EDITS,
    "pci_edits": MaskCode.PCI_EDITS,
    "usb_edits": MaskCode.USB_EDITS,
    "vm_backup": MaskCode.VM_BACKUP,
    "vm_grants": MaskCode.VM_GRANTS,
    "vm_modify": MaskCode.VM_MODIFY,
    "vm_delete": MaskCode.VM_DELETE,
    "firewalls": MaskCode.FIREWALLS,
}

# 全权限掩码值 (所有位均为1)
FULL_MASK = 65535


class UserMask:
    def __init__(self, mask: int = 0, /, **kwargs):
        self.pwr_edits: bool = False  # 是否允许编辑电源
        self.pwd_edits: bool = False  # 是否允许编辑密码
        self.sys_edits: bool = False  # 是否允许编辑系统
        self.nic_edits: bool = False  # 是否允许编辑网卡
        self.iso_edits: bool = False  # 是否允许编辑光盘
        self.hdd_edits: bool = False  # 是否允许编辑硬盘
        self.net_edits: bool = False  # 是否允许编辑网络
        self.web_edits: bool = False  # 是否允许编辑网页
        self.vnc_edits: bool = False  # 是否允许控制桌面
        self.pci_edits: bool = False  # 是否允许编辑PCIe
        self.usb_edits: bool = False  # 是否允许编辑USBs
        self.vm_backup: bool = False  # 是否允许备份还原
        self.vm_grants: bool = False  # 是否允许管理用户
        self.vm_modify: bool = False  # 是否允许修改配置
        self.vm_delete: bool = False  # 是否允许删除实例
        self.firewalls: bool = False  # 是否可编辑防火墙
        if mask > 0:
            self.__mask__(mask)
        self.__load__(**kwargs)

    def __save__(self):
        return {
            "pwr_edits": self.pwr_edits,
            "pwd_edits": self.pwd_edits,
            "sys_edits": self.sys_edits,
            "nic_edits": self.nic_edits,
            "iso_edits": self.iso_edits,
            "hdd_edits": self.hdd_edits,
            "net_edits": self.net_edits,
            "web_edits": self.web_edits,
            "vnc_edits": self.vnc_edits,
            "pci_edits": self.pci_edits,
            "usb_edits": self.usb_edits,
            "vm_backup": self.vm_backup,
            "vm_grants": self.vm_grants,
            "vm_modify": self.vm_modify,
            "vm_delete": self.vm_delete,
            "firewalls": self.firewalls,
        }

    # 加载数据 ===============================
    def __load__(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    # 从掩码数字解码到当前对象 =================
    def __mask__(self, mask: int):
        """从掩码数字解码，设置对应的权限位"""
        for field, code in _FIELD_TO_MASK.items():
            setattr(self, field, bool(mask & code.value))

    # 导出当前掩码为数字 =======================
    def _to_mask(self) -> int:
        """将当前16个权限按位编码为整数"""
        mask = 0
        for field, code in _FIELD_TO_MASK.items():
            if getattr(self, field, False):
                mask |= code.value
        return mask

    # 从一个掩码粘贴到当前对象 =================
    def _to_data(self, in_mask: int):
        """从掩码数字解码并写入当前对象，返回当前对象的字典"""
        self.__mask__(in_mask)
        return self.__save__()

    # 检查是否拥有某项权限 =====================
    def has_permission(self, action: str) -> bool:
        """
        检查当前掩码是否拥有指定权限
        :param action: 权限名称，如 'pwr_edits', 'vm_delete' 等
        :return: 是否拥有该权限
        """
        return getattr(self, action, False)

    # 与另一个掩码做交集 =======================
    def intersect(self, other: 'UserMask') -> 'UserMask':
        """
        与另一个UserMask做权限交集（AND运算）
        返回一个新的UserMask对象
        """
        result = UserMask()
        for field in _FIELD_TO_MASK:
            setattr(result, field,
                    getattr(self, field, False) and getattr(other, field, False))
        return result

    # 全权限工厂方法 ===========================
    @staticmethod
    def full() -> 'UserMask':
        """返回一个拥有全部权限的UserMask对象"""
        return UserMask(FULL_MASK)

    @staticmethod
    def full_mask() -> int:
        """返回全权限掩码值 (65535)"""
        return FULL_MASK

    def __repr__(self):
        return f"<UserMask mask={self._to_mask()}>"