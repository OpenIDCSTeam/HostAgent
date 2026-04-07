import re
import random
import subprocess
from loguru import logger
from typing import Optional

from MainObject.Config.HSConfig import HSConfig
from MainObject.Public.ZMessage import ZMessage
from HostModule.SSHDManager import SSHDManager


class PortConfig:
    """端口转发信息"""

    def __init__(self, wan_port: int, lan_addr: str, lan_port: int,
                 protocol: str = "TCP", vm_name: str = "", pid: int = 0):
        self.wan_port = wan_port  # 外部端口
        self.lan_addr = lan_addr  # 内部IP地址
        self.lan_port = lan_port  # 内部端口
        self.protocol = protocol  # 协议类型（TCP/UDP）
        self.vm_name = vm_name  # 虚拟机名称
        self.pid = pid  # socat进程ID


class PortForward:
    """基于socat的端口转发管理API"""
    def __init__(self, hs_config: HSConfig):
        """
        初始化 Socat 端口转发 API
        :param hs_config: 宿主机配置对象
        """
        self.hs_config = hs_config
        self.ssh_forward = None

    # 执行命令 #################################################################
    def execute_command(self, cmd: str, is_remote: bool = False) -> tuple[bool, str, str]:
        """
        执行命令
        :param cmd: 命令字符串
        :param is_remote: 是否为远程执行
        :return: (是否成功, stdout, stderr)
        """
        try:
            if is_remote:
                # 远程执行
                if not self.ssh_forward:
                    return False, "", "SSH连接未建立"
                success, stdout, stderr = self.ssh_forward.execute_command(cmd)
                return success, stdout, stderr
            else:
                # 本地执行
                result = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True, timeout=10
                )
                return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", "命令执行超时"
        except Exception as e:
            return False, "", str(e)

    # 列出所有端口转发 #########################################################
    def list_ports(self, is_remote: bool = False) -> list[PortConfig]:
        """
        列出当前所有socat端口转发
        :param is_remote: 是否为远程主机
        :return: 端口转发信息列表
        """
        # 执行 ps -ef | grep socat，过滤掉grep和watch等命令
        success, stdout, stderr = self.execute_command(
            "ps -ef | grep 'socat TCP\\|socat UDP' | grep -v grep | grep -v watch", is_remote
        )

        if not success:
            logger.warning(f"获取socat进程列表失败: {stderr}")
            return []

        forwards = []

        # 解析每一行输出
        # 示例输出: root 108104 1 0 15:10 ? 00:00:00 socat TCP-LISTEN:24203,reuseaddr,fork TCP:172.19.0.100:22
        for line in stdout.strip().split('\n'):
            if not line:
                continue

            try:
                # 提取PID和命令
                parts = line.split()
                if len(parts) < 8:
                    continue

                # 查找socat命令的位置（必须是独立的socat，不是路径的一部分）
                socat_index = -1
                for i, part in enumerate(parts):
                    if part == 'socat' or part.endswith('/socat'):
                        socat_index = i
                        break

                if socat_index == -1:
                    continue

                # 获取socat命令参数
                # 格式: socat TCP-LISTEN:2222,reuseaddr,fork TCP:172.17.0.2:22
                # 或: socat UDP-LISTEN:2222,reuseaddr,fork UDP:172.17.0.2:22
                cmd_parts = parts[socat_index:]

                if len(cmd_parts) < 3:
                    continue

                # 解析监听端口（第一个参数）
                listen_part = cmd_parts[1]  # TCP-LISTEN:24203,reuseaddr,fork
                forward_part = cmd_parts[2]  # TCP:172.19.0.100:22

                # 验证这是一个端口转发命令（必须包含LISTEN和目标地址）
                if 'LISTEN:' not in listen_part:
                    continue

                # 提取协议和端口
                protocol = "TCP"
                wan_port = 0

                # 解析监听部分
                if "TCP-LISTEN:" in listen_part:
                    protocol = "TCP"
                    port_match = re.search(r'TCP-LISTEN:(\d+)', listen_part)
                    if port_match:
                        wan_port = int(port_match.group(1))
                elif "UDP-LISTEN:" in listen_part:
                    protocol = "UDP"
                    port_match = re.search(r'UDP-LISTEN:(\d+)', listen_part)
                    if port_match:
                        wan_port = int(port_match.group(1))

                if wan_port == 0:
                    continue

                # 解析转发目标
                lan_addr = ""
                lan_port = 0

                if protocol == "TCP" and "TCP:" in forward_part:
                    # 匹配 TCP:IP:PORT 格式，IP可以是任意格式（包括点分十进制）
                    target_match = re.search(r'TCP:([0-9.]+):(\d+)', forward_part)
                    if target_match:
                        lan_addr = target_match.group(1)
                        lan_port = int(target_match.group(2))
                elif protocol == "UDP" and "UDP:" in forward_part:
                    target_match = re.search(r'UDP:([0-9.]+):(\d+)', forward_part)
                    if target_match:
                        lan_addr = target_match.group(1)
                        lan_port = int(target_match.group(2))

                if not lan_addr or lan_port == 0:
                    continue

                # PID通常在第2列（索引1）
                try:
                    pid = int(parts[1])
                except (ValueError, IndexError):
                    logger.warning(f"无法解析PID: {line}")
                    continue

                forward_info = PortConfig(
                    wan_port=wan_port,
                    lan_addr=lan_addr,
                    lan_port=lan_port,
                    protocol=protocol,
                    pid=pid
                )
                forwards.append(forward_info)
                logger.debug(
                    f"发现端口转发: {protocol} {wan_port} -> {lan_addr}:{lan_port} (PID: {pid})"
                )

            except Exception as e:
                logger.warning(f"解析socat进程行失败: {line}, 错误: {str(e)}")
                continue

        return forwards

    # 获取已分配的端口列表 #####################################################
    def get_host_ports(self, is_remote: bool = False) -> set[int]:
        """
        获取主机已分配的端口列表
        :param is_remote: 是否为远程主机
        :return: 端口集合
        """
        forwards = self.list_ports(is_remote)
        return {forward.wan_port for forward in forwards}

    # 分配可用端口 ##############################################################
    def allocate_port(self, is_remote: bool = False) -> int:
        """
        自动分配可用端口
        :param is_remote: 是否为远程主机
        :return: 分配的端口号
        """
        wan_port = random.randint(self.hs_config.ports_start, self.hs_config.ports_close)
        existing_ports = self.get_host_ports(is_remote)
        max_attempts = 100
        attempts = 0
        while wan_port in existing_ports and attempts < max_attempts:
            wan_port = random.randint(self.hs_config.ports_start, self.hs_config.ports_close)
            attempts += 1
        return wan_port

    # 添加端口转发 ##############################################################
    def add_port_forward(self, container_ip: str, lan_port: int, wan_port: int,
                         protocol: str = "TCP", is_remote: bool = False,
                         vm_name: str = "") -> tuple[bool, str]:
        """
        添加端口转发规则
        :param container_ip: 容器IP地址
        :param lan_port: 容器端口
        :param wan_port: 主机端口
        :param protocol: 协议类型（TCP/UDP）
        :param is_remote: 是否为远程主机
        :param vm_name: 虚拟机名（用于日志）
        :return: (是否成功, 错误信息)
        """
        protocol = protocol.upper()
        if protocol not in ["TCP", "UDP"]:
            return False, f"不支持的协议类型: {protocol}"

        # 构建socat命令
        # 格式: nohup socat TCP-LISTEN:2222,reuseaddr,fork TCP:172.17.0.2:22 > /dev/null 2>&1 &
        cmd = (
            f"nohup socat {protocol}-LISTEN:{wan_port},reuseaddr,fork "
            f"{protocol}:{container_ip}:{lan_port} > /dev/null 2>&1 &"
        )

        # 执行命令
        success, stdout, stderr = self.execute_command(cmd, is_remote)

        if not success:
            return False, f"启动socat失败: {stderr}"

        # 等待一小段时间确保进程启动
        import time
        time.sleep(0.5)

        # 验证端口转发是否成功创建
        forwards = self.list_ports(is_remote)
        found = False
        for forward in forwards:
            if (forward.wan_port == wan_port and
                    forward.lan_addr == container_ip and
                    forward.lan_port == lan_port and
                    forward.protocol == protocol):
                found = True
                break

        if not found:
            return False, f"端口转发创建后未找到对应进程"

        logger.info(
            f"端口转发已添加: {protocol} {wan_port} -> {container_ip}:{lan_port}"
            + (f" ({vm_name})" if vm_name else "")
        )

        return True, ""

    # 删除端口转发 ##############################################################
    def remove_port_forward(self, wan_port: int, protocol: str = "TCP",
                            is_remote: bool = False) -> bool:
        """
        删除端口转发规则
        :param wan_port: 主机端口
        :param protocol: 协议类型（TCP/UDP）
        :param is_remote: 是否为远程主机
        :return: 是否成功
        """
        protocol = protocol.upper()

        # 查找对应的socat进程
        logger.info(f"正在查找端口 {wan_port} ({protocol}) 的转发进程...")
        forwards = self.list_ports(is_remote)

        logger.debug(f"当前共有 {len(forwards)} 个端口转发")
        for forward in forwards:
            logger.debug(
                f"  - {forward.protocol} {forward.wan_port} -> "
                f"{forward.lan_addr}:{forward.lan_port} (PID: {forward.pid})"
            )

        target_pids = []
        for forward in forwards:
            if forward.wan_port == wan_port and forward.protocol == protocol:
                target_pids.append(forward.pid)
                logger.info(
                    f"找到匹配的转发: {forward.protocol} {forward.wan_port} -> "
                    f"{forward.lan_addr}:{forward.lan_port} (PID: {forward.pid})"
                )

        if not target_pids:
            logger.warning(f"未找到端口 {wan_port} ({protocol}) 的转发进程")
            return False

        # 杀死进程
        all_success = True
        for pid in target_pids:
            logger.info(f"正在终止进程 PID {pid}...")
            cmd = f"kill {pid}"
            success, stdout, stderr = self.execute_command(cmd, is_remote)

            if success:
                logger.info(f"kill命令执行成功: PID {pid}")

                # 验证进程是否真的被终止
                import time
                time.sleep(0.5)

                # 检查进程是否还存在
                check_cmd = f"ps -p {pid} -o pid="
                check_success, check_stdout, check_stderr = self.execute_command(check_cmd, is_remote)

                if check_success and check_stdout.strip():
                    # 进程还存在，尝试强制终止
                    logger.warning(f"进程 {pid} 仍在运行，尝试强制终止...")
                    force_cmd = f"kill -9 {pid}"
                    force_success, force_stdout, force_stderr = self.execute_command(force_cmd, is_remote)

                    if force_success:
                        logger.info(f"已强制终止进程: PID {pid}")
                    else:
                        logger.error(f"强制终止进程失败: PID {pid}, 错误: {force_stderr}")
                        all_success = False
                else:
                    logger.info(f"已成功停止端口转发进程: PID {pid} ({protocol} {wan_port})")
            else:
                logger.warning(f"停止进程失败: PID {pid}, 错误: {stderr}")
                all_success = False

        return all_success

    # 删除指定容器的所有端口转发 ################################################
    def remove_container_forwards(self, container_ip: str, is_remote: bool = False) -> int:
        """
        删除指定容器的所有端口转发
        :param container_ip: 容器IP地址
        :param is_remote: 是否为远程主机
        :return: 删除的转发数量
        """
        forwards = self.list_ports(is_remote)
        removed_count = 0

        for forward in forwards:
            if forward.lan_addr == container_ip:
                if self.remove_port_forward(forward.wan_port, forward.protocol, is_remote):
                    removed_count += 1

        return removed_count

    # macvlan路由同步 ##########################################################
    def add_port_forward_macvlan(self, docker_net_name: str = "macvlan",
                                 macvlan_if: str = "macvlan_forward",
                                 is_remote: bool = False) -> tuple[bool, str]:
        """
        配置macvlan接口并同步Docker容器路由（替代socat的macvlan直通方案）
        :param docker_net_name: Docker网络名称
        :param macvlan_if: macvlan虚拟接口名称
        :param is_remote: 是否为远程主机
        :return: (是否成功, 消息)
        """
        # 获取物理网卡和外网IP
        phys_if = self.hs_config.network_pub
        if not phys_if:
            return False, "未配置物理网卡(network_pub)"

        # 优先使用 public_addr，其次使用 server_addr
        if self.hs_config.public_addr:
            host_ip = self.hs_config.public_addr[0]
        elif self.hs_config.server_addr:
            host_ip = self.hs_config.server_addr
        else:
            return False, "未配置外网IP(public_addr/server_addr)"

        # 确保 host_ip 带有子网掩码（默认 /24）
        if "/" not in str(host_ip):
            host_ip = f"{host_ip}/24"

        host_ip_only = host_ip.split("/")[0]

        # 若 phys_if 不是系统网卡（如 docker 网络名），通过默认路由获取真实物理网卡
        check_iface_cmd = f"test -d /sys/class/net/{phys_if}"
        iface_ok, _, _ = self.execute_command(check_iface_cmd, is_remote)
        if not iface_ok:
            route_cmd = "ip route show default"
            ok, route_out, _ = self.execute_command(route_cmd, is_remote)
            real_if = ""
            if ok and route_out.strip():
                # 格式: default via x.x.x.x dev eth0 ...
                tokens = route_out.split()
                for i, token in enumerate(tokens):
                    if token == "dev" and i + 1 < len(tokens):
                        real_if = tokens[i + 1]
                        break
            if real_if:
                phys_if = real_if
                logger.info(f"通过默认路由获取到真实物理网卡: {phys_if}")
            else:
                return False, f"network_pub '{phys_if}' 不是系统网卡，且无法通过默认路由获取物理网卡"

        logger.info(f"macvlan配置: 物理网卡={phys_if}, 外网IP={host_ip}, 接口={macvlan_if}, Docker网络={docker_net_name}")

        # 1. 创建macvlan接口（若不存在）
        check_cmd = f"test -d /sys/class/net/{macvlan_if}"
        iface_exists, _, _ = self.execute_command(check_cmd, is_remote)

        if not iface_exists:
            create_cmd = f"ip link add {macvlan_if} link {phys_if} type macvlan mode bridge"
            success, stdout, stderr = self.execute_command(create_cmd, is_remote)
            if not success:
                return False, f"创建macvlan接口失败: {stderr}"
            logger.info(f"已创建macvlan接口: {macvlan_if}")
        else:
            logger.info(f"macvlan接口 {macvlan_if} 已存在")

        # 2. 为macvlan接口配置IP（若未配置）
        check_ip_cmd = f"ip addr show dev {macvlan_if}"
        _, ip_out, _ = self.execute_command(check_ip_cmd, is_remote)

        if host_ip_only not in ip_out:
            add_ip_cmd = f"ip addr add {host_ip} dev {macvlan_if}"
            success, stdout, stderr = self.execute_command(add_ip_cmd, is_remote)
            if not success:
                return False, f"为macvlan接口添加IP失败: {stderr}"
            logger.info(f"已为 {macvlan_if} 添加IP: {host_ip}")
        else:
            logger.info(f"macvlan接口 {macvlan_if} 已配置IP {host_ip_only}")

        # 3. 启用macvlan接口
        up_cmd = f"ip link set {macvlan_if} up"
        success, stdout, stderr = self.execute_command(up_cmd, is_remote)
        if not success:
            return False, f"启用macvlan接口失败: {stderr}"

        # 4. 获取Docker网络中所有容器IP
        # 先验证网络是否存在，若不存在则创建 macvlan 网络
        check_net_cmd = f"docker network inspect {docker_net_name}"
        net_ok, net_out, _ = self.execute_command(check_net_cmd, is_remote)
        if not net_ok or not net_out.strip():
            # 获取宿主机IP所在网段作为 macvlan 子网
            host_ip_only = host_ip.split("/")[0]
            prefix = host_ip.split("/")[1] if "/" in host_ip else "24"
            # 计算网段（简单取前三段.0/prefix）
            parts_ip = host_ip_only.split(".")
            subnet = f"{parts_ip[0]}.{parts_ip[1]}.{parts_ip[2]}.0/{prefix}"
            gateway = f"{parts_ip[0]}.{parts_ip[1]}.{parts_ip[2]}.1"
            create_net_cmd = (
                f"docker network create -d macvlan "
                f"--subnet={subnet} --gateway={gateway} "
                f"-o parent={phys_if} {docker_net_name}"
            )
            logger.info(f"Docker网络 '{docker_net_name}' 不存在，正在创建: {create_net_cmd}")
            cn_ok, cn_out, cn_err = self.execute_command(create_net_cmd, is_remote)
            if not cn_ok:
                return False, f"创建Docker macvlan网络失败: {cn_err}"
            logger.info(f"已创建Docker macvlan网络: {docker_net_name}")

        inspect_cmd = f"docker network inspect {docker_net_name}"
        success, stdout, stderr = self.execute_command(inspect_cmd, is_remote)
        if not success:
            return False, f"获取Docker网络容器列表失败: {stderr}"
        import json as _json
        try:
            nets = _json.loads(stdout.strip())
            container_ips = []
            if nets and isinstance(nets, list):
                for cid, cinfo in nets[0].get("Containers", {}).items():
                    ip = cinfo.get("IPv4Address", "").split("/")[0]
                    if ip:
                        container_ips.append(ip)
        except Exception as e:
            return False, f"解析Docker网络容器列表失败: {e}"

        logger.info(f"Docker网络 {docker_net_name} 中的容器IP: {container_ips}")

        # 5. 获取当前macvlan路由
        route_cmd = f"ip route | grep 'dev {macvlan_if}'"
        success, stdout, stderr = self.execute_command(route_cmd, is_remote)
        # 允许无路由时返回空（不视为失败）
        existing_routes = []
        if stdout.strip():
            for line in stdout.strip().split("\n"):
                parts = line.strip().split()
                if parts:
                    existing_routes.append(parts[0])

        # 6. 添加缺失的路由
        added, removed = 0, 0
        for ip in container_ips:
            if ip not in existing_routes:
                add_route_cmd = f"ip route add {ip} dev {macvlan_if}"
                ok, _, err = self.execute_command(add_route_cmd, is_remote)
                if ok:
                    logger.info(f"已添加路由: {ip} -> {macvlan_if}")
                    added += 1
                else:
                    logger.warning(f"添加路由失败: {ip}, 错误: {err}")
            else:
                logger.debug(f"路由 {ip} 已存在，跳过")

        # 7. 删除已失效的路由（仅纯IP形式，不删除网段路由）
        import re as _re
        ip_pattern = _re.compile(r"^\d+\.\d+\.\d+\.\d+$")
        for route_ip in existing_routes:
            if ip_pattern.match(route_ip) and route_ip not in container_ips:
                del_route_cmd = f"ip route del {route_ip} dev {macvlan_if}"
                ok, _, err = self.execute_command(del_route_cmd, is_remote)
                if ok:
                    logger.info(f"已删除失效路由: {route_ip}")
                    removed += 1
                else:
                    logger.warning(f"删除路由失败: {route_ip}, 错误: {err}")

        msg = f"macvlan路由同步完成: 新增{added}条，删除{removed}条"
        logger.info(msg)
        return True, msg

    # iptables/nft端口转发 #####################################################
    def add_port_forward_firewall(self, container_ip: str, lan_port: int,
                                  wan_port: int, protocol: str = "TCP",
                                  is_remote: bool = False,
                                  vm_name: str = "") -> tuple[bool, str]:
        """
        通过iptables/nft添加端口转发规则（lxc/lxd类型使用）
        :param container_ip: 容器IP地址
        :param lan_port: 容器端口
        :param wan_port: 主机端口
        :param protocol: 协议类型（TCP/UDP）
        :param is_remote: 是否为远程主机
        :param vm_name: 虚拟机名（用于注释）
        :return: (是否成功, 错误信息)
        """
        from HostServer.OCInterfaceAPI.IPTablesAPI import IPTablesAPI
        iptables = IPTablesAPI(self.hs_config)
        # 复用已有SSH连接
        if is_remote and self.ssh_forward:
            iptables.ssh_forward = self.ssh_forward
        return iptables.add_port_mapping(
            container_ip, lan_port, wan_port, is_remote, vm_name)

    def remove_port_forward_firewall(self, container_ip: str, lan_port: int,
                                     wan_port: int,
                                     is_remote: bool = False) -> bool:
        """
        通过iptables/nft删除端口转发规则（lxc/lxd类型使用）
        :param container_ip: 容器IP地址
        :param lan_port: 容器端口
        :param wan_port: 主机端口
        :param is_remote: 是否为远程主机
        :return: 是否成功
        """
        from HostServer.OCInterfaceAPI.IPTablesAPI import IPTablesAPI
        iptables = IPTablesAPI(self.hs_config)
        if is_remote and self.ssh_forward:
            iptables.ssh_forward = self.ssh_forward
        return iptables.remove_port_mapping(
            container_ip, lan_port, wan_port, is_remote)

    def list_ports_firewall(self, is_remote: bool = False) -> list[PortConfig]:
        """
        获取iptables中已有的端口转发列表（lxc/lxd类型使用）
        :param is_remote: 是否为远程主机
        :return: 端口转发信息列表
        """
        from HostServer.OCInterfaceAPI.IPTablesAPI import IPTablesAPI
        iptables = IPTablesAPI(self.hs_config)
        if is_remote and self.ssh_forward:
            iptables.ssh_forward = self.ssh_forward

        try:
            cmd = "iptables -t nat -L PREROUTING -n --line-numbers"
            if is_remote:
                success, stdout, stderr = self.ssh_forward.execute_command(cmd)
            else:
                result = __import__('subprocess').run(
                    cmd.split(), capture_output=True, text=True)
                success = result.returncode == 0
                stdout = result.stdout
                stderr = result.stderr

            if not success:
                return []

            forwards = []
            for line in stdout.split('\n'):
                # 解析 DNAT 规则中的注释（格式：ip-wan-lan#vmname）
                if 'DNAT' not in line or 'dpt:' not in line:
                    continue
                try:
                    # 提取 wan_port
                    wan_match = re.search(r'dpt:(\d+)', line)
                    # 提取目标 ip:port
                    to_match = re.search(r'to:([0-9.]+):(\d+)', line)
                    if not wan_match or not to_match:
                        continue
                    wan_port = int(wan_match.group(1))
                    lan_addr = to_match.group(1)
                    lan_port = int(to_match.group(2))
                    # 提取 vm_name（注释中 # 后的部分）
                    vm_name = ""
                    comment_match = re.search(r'/\*[^#]*#([^*]+)\*/', line)
                    if comment_match:
                        vm_name = comment_match.group(1).strip()
                    forwards.append(PortConfig(
                        wan_port=wan_port,
                        lan_addr=lan_addr,
                        lan_port=lan_port,
                        protocol="TCP",
                        vm_name=vm_name
                    ))
                except Exception:
                    continue
            return forwards
        except Exception as e:
            logger.warning(f"获取iptables端口列表失败: {e}")
            return []

    def get_host_ports_firewall(self, is_remote: bool = False) -> set[int]:
        """获取iptables中已分配的端口集合（lxc/lxd类型使用）"""
        from HostServer.OCInterfaceAPI.IPTablesAPI import IPTablesAPI
        iptables = IPTablesAPI(self.hs_config)
        if is_remote and self.ssh_forward:
            iptables.ssh_forward = self.ssh_forward
        return iptables.get_host_ports(is_remote)

    # 连接SSH ##################################################################
    def connect_ssh(self, port: int = 22) -> tuple[bool, str]:
        """
        连接SSH（用于远程端口转发）
        :return: (是否成功, 消息)
        """
        self.ssh_forward = SSHDManager()
        success, message = self.ssh_forward.connect(
            hostname=self.hs_config.server_addr,
            username=self.hs_config.server_user,
            password=self.hs_config.server_pass,
            port=port
        )

        if not success:
            return False, message

        return True, "SSH连接成功"

    # 关闭SSH连接 ##############################################################
    def close_ssh(self):
        """关闭SSH连接"""
        if self.ssh_forward:
            self.ssh_forward.close()
            self.ssh_forward = None
