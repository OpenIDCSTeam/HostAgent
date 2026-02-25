import ipaddress
from typing import Optional
from MainObject.Public.ZMessage import ZMessage

class IPStatus:
    def __init__(self):
        self.ip_gate = ""
        self.ip_mask = ""
        self.ip_from = ""
        self.ip_nums = 0
        self.ip_vers = ""
        self.ip_type = ""

class IPConfig:
    """IP地址分配管理类"""

    def __init__(self, ipaddr_maps: dict, ipaddr_ddns: list):
        """
        初始化IP配置管理器
        :param ipaddr_maps: IP地址池配置
        :param ipaddr_ddns: DNS服务器列表
        """
        self.ipaddr_maps = ipaddr_maps or {}
        self.ipaddr_ddns = ipaddr_ddns or []

    def allocate_ip(self, ip_version: str, nic_type: str, allocated_ips: set) -> Optional[dict]:
        """
        从IP地址池中分配IP地址
        :param ip_version: IP版本 (ipv4/ipv6)
        :param nic_type: 网卡类型 (nat/pub)
        :param allocated_ips: 已分配的IP集合
        :return: 分配结果字典，包含ip、gate、mask，失败返回None
        """
        for set_name, ip_set_config in self.ipaddr_maps.items():
            # 检查是否匹配IP版本和网卡类型
            if ip_set_config.get("vers") != ip_version or ip_set_config.get("type") != nic_type:
                continue

            from_ip = ip_set_config.get("from", "")
            nums = ip_set_config.get("nums", 0)

            if not from_ip or nums <= 0:
                continue

            # 尝试分配IP
            try:
                base_ip = ipaddress.ip_address(from_ip)
                for i in range(nums):
                    candidate_ip = str(base_ip + i)
                    if candidate_ip not in allocated_ips:
                        return {
                            "ip": candidate_ip,
                            "gate": ip_set_config.get("gate", ""),
                            "mask": ip_set_config.get("mask", "")
                        }
            except (ValueError, ipaddress.AddressValueError):
                continue

        return None

    def check_and_allocate(self, vm_config, allocated_ips: set) -> tuple:
        """
        检查并自动分配虚拟机网卡IP地址
        :param vm_config: 虚拟机配置对象
        :param allocated_ips: 已分配的IP集合
        :return: (更新后的虚拟机配置, 操作结果消息)
        """
        for nic_name, nic_config in vm_config.nic_all.items():
            need_ipv4 = not nic_config.ip4_addr or nic_config.ip4_addr.strip() == ""
            need_ipv6 = not nic_config.ip6_addr or nic_config.ip6_addr.strip() == ""

            if not need_ipv4 and not need_ipv6:
                continue

            nic_type = nic_config.nic_type if nic_config.nic_type else "nat"

            # 分配IPv4
            if need_ipv4:
                ipv4_result = self.allocate_ip("ipv4", nic_type, allocated_ips)
                if ipv4_result is None:
                    return vm_config, ZMessage(
                        success=False,
                        action="NetCheck",
                        message=f"无法为网卡 {nic_name} 分配IPv4地址，类型: {nic_type}，所有IP已被占用或无可用IP段配置"
                    )
                nic_config.ip4_addr = ipv4_result["ip"]
                # 设置网关和掩码
                if ipv4_result.get("gate"):
                    nic_config.gateway = ipv4_result["gate"]
                if ipv4_result.get("mask"):
                    nic_config.netmask = ipv4_result["mask"]
                if self.ipaddr_ddns:
                    nic_config.dns_addr = self.ipaddr_ddns
                    nic_config.send_mac()


            # 分配IPv6（失败不报错）
            if need_ipv6:
                ipv6_result = self.allocate_ip("ipv6", nic_type, allocated_ips)
                if ipv6_result is not None:
                    nic_config.ip6_addr = ipv6_result["ip"]
                    nic_config.send_mac()

        return vm_config, ZMessage(
            success=True,
            action="NetCheck",
            message="网络配置检查完成"
        )
