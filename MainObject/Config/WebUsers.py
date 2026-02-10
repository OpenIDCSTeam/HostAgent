"""
Web用户模型
定义用户信息、权限和资源配额
"""
from typing import List, Dict, Any
from datetime import datetime
from MainObject.Config.UserMask import UserMask, FULL_MASK


class WebUser:
    """Web用户模型"""

    def __init__(
        self,
        id: int = 0,
        username: str = "",
        password: str = "",
        email: str = "",
        is_admin: bool = False,
        is_active: bool = True,
        email_verified: bool = False,
        verify_token: str = "",
        # 权限
        can_create_vm: bool = False,
        can_delete_vm: bool = False,
        can_modify_vm: bool = False,
        user_permission: int = FULL_MASK,
        # 资源配额
        quota_cpu: int = 0,
        quota_ram: int = 0,
        quota_ssd: int = 0,
        quota_gpu: int = 0,
        quota_nat_ports: int = 0,
        quota_web_proxy: int = 0,
        quota_nat_ips: int = 0,
        quota_pub_ips: int = 0,
        quota_bandwidth_up: int = 0,
        quota_bandwidth_down: int = 0,
        quota_traffic: int = 0,
        # 已使用资源
        used_cpu: int = 0,
        used_ram: int = 0,
        used_ssd: int = 0,
        used_gpu: int = 0,
        used_nat_ports: int = 0,
        used_web_proxy: int = 0,
        used_nat_ips: int = 0,
        used_pub_ips: int = 0,
        used_traffic: int = 0,
        # 分配的主机
        assigned_hosts: List[str] = None,
        # 时间戳
        created_at: str = "",
        updated_at: str = "",
        last_login: str = None,
        **kwargs
    ):
        self.id = id
        self.username = username
        self.password = password
        self.email = email
        self.is_admin = is_admin
        self.is_active = is_active
        self.email_verified = email_verified
        self.verify_token = verify_token

        # 权限
        self.can_create_vm = can_create_vm
        self.can_delete_vm = can_delete_vm
        self.can_modify_vm = can_modify_vm
        self.user_permission = user_permission
        # 资源配额
        self.quota_cpu = quota_cpu
        self.quota_ram = quota_ram
        self.quota_ssd = quota_ssd
        self.quota_gpu = quota_gpu
        self.quota_nat_ports = quota_nat_ports
        self.quota_web_proxy = quota_web_proxy
        self.quota_nat_ips = quota_nat_ips
        self.quota_pub_ips = quota_pub_ips
        self.quota_bandwidth_up = quota_bandwidth_up
        self.quota_bandwidth_down = quota_bandwidth_down
        self.quota_traffic = quota_traffic

        # 已使用资源
        self.used_cpu = used_cpu
        self.used_ram = used_ram
        self.used_ssd = used_ssd
        self.used_gpu = used_gpu
        self.used_nat_ports = used_nat_ports
        self.used_web_proxy = used_web_proxy
        self.used_nat_ips = used_nat_ips
        self.used_pub_ips = used_pub_ips
        self.used_traffic = used_traffic

        # 分配的主机
        self.assigned_hosts = assigned_hosts if assigned_hosts is not None else []

        # 时间戳
        self.created_at = created_at
        self.updated_at = updated_at
        self.last_login = last_login

    def __save__(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "id": self.id,
            "username": self.username,
            "password": self.password,
            "email": self.email,
            "is_admin": self.is_admin,
            "is_active": self.is_active,
            "email_verified": self.email_verified,
            "verify_token": self.verify_token,
            "can_create_vm": self.can_create_vm,
            "can_delete_vm": self.can_delete_vm,
            "can_modify_vm": self.can_modify_vm,
            "user_permission": self.user_permission,
            "quota_cpu": self.quota_cpu,
            "quota_ram": self.quota_ram,
            "quota_ssd": self.quota_ssd,
            "quota_gpu": self.quota_gpu,
            "quota_nat_ports": self.quota_nat_ports,
            "quota_web_proxy": self.quota_web_proxy,
            "quota_bandwidth_up": self.quota_bandwidth_up,
            "quota_bandwidth_down": self.quota_bandwidth_down,
            "quota_traffic": self.quota_traffic,
            "used_cpu": self.used_cpu,
            "used_ram": self.used_ram,
            "used_ssd": self.used_ssd,
            "used_gpu": self.used_gpu,
            "used_nat_ports": self.used_nat_ports,
            "used_web_proxy": self.used_web_proxy,
            "used_traffic": self.used_traffic,
            "assigned_hosts": self.assigned_hosts,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_login": self.last_login,
        }

    def to_dict(self, include_password: bool = False) -> Dict[str, Any]:
        """转换为字典（可选是否包含密码）"""
        data = self.__save__()
        if not include_password:
            data.pop("password", None)
            data.pop("verify_token", None)
        return data

    def get_user_mask(self) -> UserMask:
        """
        根据 user_permission 构建 UserMask 对象
        user_permission 为掩码数字（int）
        """
        if isinstance(self.user_permission, int):
            return UserMask(self.user_permission)
        elif isinstance(self.user_permission, dict):
            return UserMask(**self.user_permission)
        else:
            return UserMask.full()

    def check_resource_available(
        self, cpu: int = 0, ram: int = 0, ssd: int = 0, gpu: int = 0,
        nat_ports: int = 0, web_proxy: int = 0
    ) -> tuple[bool, str]:
        """
        检查资源是否可用
        :return: (是否可用, 错误信息)
        """
        if cpu > 0 and self.used_cpu + cpu > self.quota_cpu:
            return False, f"CPU配额不足，已使用{self.used_cpu}/{self.quota_cpu}核"
        if ram > 0 and self.used_ram + ram > self.quota_ram:
            return False, f"内存配额不足，已使用{self.used_ram}/{self.quota_ram}GB"
        if ssd > 0 and self.used_ssd + ssd > self.quota_ssd:
            return False, f"磁盘配额不足，已使用{self.used_ssd}/{self.quota_ssd}GB"
        if gpu > 0 and self.used_gpu + gpu > self.quota_gpu:
            return False, f"GPU配额不足，已使用{self.used_gpu}/{self.quota_gpu}GB"
        if nat_ports > 0 and self.used_nat_ports + nat_ports > self.quota_nat_ports:
            return False, f"NAT端口配额不足，已使用{self.used_nat_ports}/{self.quota_nat_ports}个"
        if web_proxy > 0 and self.used_web_proxy + web_proxy > self.quota_web_proxy:
            return False, f"WEB代理配额不足，已使用{self.used_web_proxy}/{self.quota_web_proxy}个"
        return True, ""

    def has_host_access(self, hs_name: str) -> bool:
        """检查用户是否有访问指定主机的权限"""
        if self.is_admin:
            return True
        return hs_name in self.assigned_hosts

    def __repr__(self):
        return f"<WebUser {self.username} (admin={self.is_admin})>"
