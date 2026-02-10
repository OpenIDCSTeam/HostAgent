# OCInterface - Docker容器管理服务器 ############################################
# 提供Docker容器的创建、管理和监控功能
################################################################################
import os
import time
import shutil
import datetime
import traceback
import subprocess
from loguru import logger
from HostServer.BasicServer import BasicServer
from MainObject.Config.HSConfig import HSConfig
from MainObject.Config.IMConfig import IMConfig
from MainObject.Config.SDConfig import SDConfig
from MainObject.Config.VMBackup import VMBackup
from MainObject.Config.VMPowers import VMPowers
from MainObject.Public.ZMessage import ZMessage
from MainObject.Config.VMConfig import VMConfig
from MainObject.Config.PortData import PortData
from MainObject.Public.HWStatus import HWStatus
from HostServer.OCInterfaceAPI.OCIConnects import OCIConnects
from HostServer.OCInterfaceAPI.PortForward import PortForward
from docker.errors import NotFound


class HostServer(BasicServer):
    # 读取宿主机 ###############################################################
    def __init__(self, config: HSConfig, **kwargs):
        super().__init__(config, **kwargs)
        self.web_terminal = None
        self.oci_connects = None
        self.ssh_forwards = None
        self.http_manager = None
        self.port_forward = None

    # 连接到 Docker 服务器 #####################################################
    def api_conn(self) -> tuple:
        if not self.oci_connects:
            self.oci_connects = OCIConnects(self.hs_config)
        return self.oci_connects.connect_docker()

    # 同步端口转发配置 #########################################################
    def syn_port(self):
        return self.syn_port_TTY()

    # 构建容器配置 #############################################################
    def oci_conf(self, vm_conf: VMConfig) -> dict:
        # 创建基础配置 ==========================================
        config = {
            "environment": {},
            "volumes": {},
            # 必需参数，使容器可以交互运行
            "stdin_open": True,  # -i: 保持 STDIN 打开
            "tty": True,  # -t: 分配伪终端
            # 特权模式，让容器拥有几乎与宿主机相同的权限
            "privileged": True,
            # 共享内存大小，避免某些应用运行问题
            "shm_size": "1024m",
            # 添加容器能力
            "cap_add": [
                "SYS_ADMIN",  # 系统管理权限
                "SYS_PTRACE"  # 进程调试权限
            ],
        }
        # CPU 限制 ==============================================
        if vm_conf.cpu_num > 0:
            config["nano_cpus"] = int(vm_conf.cpu_num * 1e9)
        # CPU 份额 ==============================================
        if vm_conf.cpu_per > 0:
            config["cpu_shares"] = int(vm_conf.cpu_per * 10)
        # 内存限制 (转换为字节) =================================
        if vm_conf.mem_num > 0:
            config["mem_limit"] = f"{vm_conf.mem_num}m"
        # 挂载配置 ==============================================
        if self.hs_config.extern_path:
            # 确保基础目录存在
            base_path = f"{self.hs_config.extern_path}/{vm_conf.vm_uuid}"
            os.makedirs(f"{base_path}/root", exist_ok=True)
            os.makedirs(f"{base_path}/user", exist_ok=True)
            # 挂载 root 目录
            config["volumes"][f"{base_path}/root"] = {
                "bind": "/root",
                "mode": "rw"
            }
            # 挂载 user 目录
            config["volumes"][f"{base_path}/user"] = {
                "bind": "/home/user",
                "mode": "rw"
            }
            logger.info(f"Configured volumes for {vm_conf.vm_uuid}:")
            logger.info(f"  {base_path}/root:/root")
            logger.info(f"  {base_path}/user:/home/user")
        return config

    # 解析Docker容器统计信息 ###################################################
    def get_info(self, stats: dict, vm_uuid: str) -> HWStatus:
        """
        解析Docker容器统计信息，转换为HWStatus对象

        :param stats: Docker容器统计信息
        :param vm_uuid: 虚拟机UUID
        :return: HWStatus对象
        """
        import time

        hw_status = HWStatus()
        hw_status.on_update = int(time.time())
        hw_status.ac_status = VMPowers.STARTED

        try:
            # CPU使用率计算
            cpu_stats = stats.get('cpu_stats', {})
            precpu_stats = stats.get('precpu_stats', {})

            cpu_delta = cpu_stats.get('cpu_usage', {}).get('total_usage', 0) - \
                        precpu_stats.get('cpu_usage', {}).get('total_usage', 0)
            system_delta = cpu_stats.get('system_cpu_usage', 0) - \
                           precpu_stats.get('system_cpu_usage', 0)

            online_cpus = cpu_stats.get('online_cpus', 0)
            if online_cpus == 0:
                online_cpus = len(cpu_stats.get('cpu_usage', {}).get('percpu_usage', []))

            hw_status.cpu_total = online_cpus

            if system_delta > 0 and cpu_delta > 0:
                cpu_percent = (cpu_delta / system_delta) * online_cpus * 100.0
                hw_status.cpu_usage = int(cpu_percent)
            else:
                hw_status.cpu_usage = 0

            # 内存使用情况
            memory_stats = stats.get('memory_stats', {})
            mem_usage = memory_stats.get('usage', 0)
            mem_limit = memory_stats.get('limit', 0)

            hw_status.mem_total = int(mem_limit / (1024 * 1024))  # 转换为MB
            hw_status.mem_usage = int(mem_usage / (1024 * 1024))  # 转换为MB

            # 网络流量统计
            networks = stats.get('networks', {})
            total_rx = 0
            total_tx = 0

            for interface, net_stats in networks.items():
                total_rx += net_stats.get('rx_bytes', 0)
                total_tx += net_stats.get('tx_bytes', 0)

            # 转换为MB
            hw_status.flu_usage = int((total_rx + total_tx) / (1024 * 1024))
            hw_status.network_d = int(total_rx / (1024 * 1024))
            hw_status.network_u = int(total_tx / (1024 * 1024))

            # 磁盘IO统计
            blkio_stats = stats.get('blkio_stats', {})
            io_service_bytes = blkio_stats.get('io_service_bytes_recursive', [])

            total_read = 0
            total_write = 0
            for entry in io_service_bytes:
                if entry.get('op') == 'Read':
                    total_read += entry.get('value', 0)
                elif entry.get('op') == 'Write':
                    total_write += entry.get('value', 0)

            hw_status.hdd_usage = int((total_read + total_write) / (1024 * 1024))  # 转换为MB

            logger.debug(f"[{self.hs_config.server_name}] 容器 {vm_uuid} 状态: "
                         f"CPU={hw_status.cpu_usage}%, "
                         f"MEM={hw_status.mem_usage}/{hw_status.mem_total}MB, "
                         f"NET={hw_status.flu_usage}MB")

        except Exception as e:
            logger.error(f"[{self.hs_config.server_name}] 解析容器 {vm_uuid} 统计信息失败: {e}")
            traceback.print_exc()

        return hw_status

    # 定时任务 #################################################################
    def Crontabs(self) -> bool:
        """
        定时任务：获取所有容器的性能状态并保存到数据库
        """
        # 先执行父类的定时任务（保存宿主机状态）
        super().Crontabs()

        # 获取所有容器的性能状态
        try:
            # 连接到 Docker 服务器
            client, result = self.api_conn()
            if not result.success:
                logger.warning(f"[{self.hs_config.server_name}] Crontabs: Docker连接失败，跳过容器状态采集")
                return True

            # 遍历vm_saving中的所有容器
            for vm_uuid, vm_config in self.vm_saving.items():
                try:
                    # 获取容器对象
                    container = self.oci_connects.get_container(vm_uuid)
                    if not container:
                        logger.debug(f"[{self.hs_config.server_name}] Crontabs: 容器 {vm_uuid} 不存在，跳过")
                        continue

                    # 检查容器是否在运行
                    container.reload()
                    if container.status != "running":
                        logger.debug(f"[{self.hs_config.server_name}] Crontabs: 容器 {vm_uuid} 未运行，跳过")
                        continue

                    # 获取容器统计信息（stream=False表示只获取一次）
                    stats = container.stats(stream=False)

                    # 解析统计信息并创建HWStatus对象
                    hw_status = self.get_info(stats, vm_uuid)

                    # 保存到数据库
                    if self.save_data and self.hs_config.server_name:
                        success = self.save_data.add_vm_status(
                            self.hs_config.server_name,
                            vm_uuid,
                            hw_status
                        )
                        if success:
                            logger.debug(f"[{self.hs_config.server_name}] Crontabs: 容器 {vm_uuid} 状态已保存")
                        else:
                            logger.warning(f"[{self.hs_config.server_name}] Crontabs: 容器 {vm_uuid} 状态保存失败")

                except Exception as e:
                    logger.error(f"[{self.hs_config.server_name}] Crontabs: 处理容器 {vm_uuid} 时出错: {e}")
                    traceback.print_exc()
                    continue

            return True

        except Exception as e:
            logger.error(f"[{self.hs_config.server_name}] Crontabs: 容器状态采集失败: {e}")
            traceback.print_exc()
            return True  # 即使失败也返回True，避免影响其他定时任务

    # 宿主机状态 ###############################################################
    def HSStatus(self) -> HWStatus:
        """获取宿主机状态"""
        # 专用操作 =============================================================
        try:
            # 连接到 Docker 服务器
            client, result = self.api_conn()
            if not result.success:
                logger.error(f"无法连接到Docker获取状态: {result.message}")
                return super().HSStatus()
            
            # 获取 Docker 主机信息
            try:
                info = client.info()
                
                # 创建 HWStatus 对象
                hw_status = HWStatus()
                
                # CPU 信息
                if 'NCPU' in info:
                    hw_status.cpu_total = info['NCPU']
                
                # 内存信息
                if 'MemTotal' in info:
                    hw_status.mem_total = int(info['MemTotal'] / (1024 * 1024))  # 转换为MB
                
                # 获取系统信息（如果可用）
                if 'SystemStatus' in info and info['SystemStatus']:
                    for item in info['SystemStatus']:
                        if len(item) >= 2:
                            key, value = item[0], item[1]
                            # 解析 CPU 使用率
                            if 'CPU' in key and '%' in value:
                                try:
                                    hw_status.cpu_usage = int(float(value.replace('%', '').strip()))
                                except Exception as e:
                                    traceback.print_exc()
                                    pass
                            # 解析内存使用
                            elif 'Memory' in key and 'GiB' in value:
                                try:
                                    mem_used = float(value.split('/')[0].replace('GiB', '').strip())
                                    hw_status.mem_usage = int(mem_used * 1024)  # 转换为MB
                                except Exception as e:
                                    traceback.print_exc()
                                    pass
                
                return hw_status
                
            except Exception as e:
                logger.error(f"获取Docker主机状态失败: {str(e)}")
                traceback.print_exc()
                return super().HSStatus()
                
        except Exception as e:
            logger.error(f"获取Docker主机状态失败: {str(e)}")
            traceback.print_exc()
        
        # 通用操作 =============================================================
        return super().HSStatus()

    # 加载主机配置 #############################################################
    def HSLoader(self) -> ZMessage:
        # 连接到Docker服务器 ===================================================
        client, result = self.api_conn()
        if not result.success:
            return result
        result = super().HSLoader()
        # 同步端口转发配置 =====================================================
        self.syn_port()
        # 通用操作 =============================================================
        return result

    # 卸载宿主机 ###############################################################
    def HSUnload(self) -> ZMessage:
        # 专用操作 =============================================================
        if self.web_terminal:
            self.web_terminal = None
        # 断开 Docker 连接 =====================================================
        if self.oci_connects:
            self.oci_connects.disconnect_docker()
            self.oci_connects = None
        # 关闭 SSH 转发连接 ====================================================
        if self.ssh_forwards:
            self.ssh_forwards.close()
        # 通用操作 =============================================================
        return super().HSUnload()

    # 网络检查 #################################################################
    # 检查并自动分配虚拟机网卡IP地址
    # :param vm_conf: 虚拟机配置对象
    #  :return: (更新后的虚拟机配置, 操作结果消息)
    def NetCheck(self, vm_conf: VMConfig) -> tuple:
        logger.info(f"[{self.hs_config.server_name}] 开始网络检查: {vm_conf.vm_uuid}")
        # 连接到 Docker 服务器
        client, result = self.api_conn()
        if not result.success:
            logger.error(f"[{self.hs_config.server_name}] 网络检查失败: Docker连接失败")
            return vm_conf, result

        try:
            # 获取所有已分配的IP地址（包括其他虚拟机）
            allocated_ips = self.IPCollect()

            # 检查是否有重复的网卡类型（禁止同一容器分配多个相同类型的网卡）
            nic_types = {}
            for nic_name, nic_conf in vm_conf.nic_all.items():
                if nic_conf.nic_type in nic_types:
                    logger.warning(f"[{self.hs_config.server_name}] 网卡类型冲突: {nic_name} 和 {nic_types[nic_conf.nic_type]} 都是 {nic_conf.nic_type} 类型")
                    return vm_conf, ZMessage(
                        success=False,
                        action="NetCheck",
                        message=f"禁止为同一容器分配多个相同类型的网卡。"
                                f"网卡 {nic_name} 和 {nic_types[nic_conf.nic_type]} 都是 {nic_conf.nic_type} 类型"
                    )
                nic_types[nic_conf.nic_type] = nic_name

            # 排除当前虚拟机自己的IP地址，避免误判为冲突
            current_vm_ips = set()
            for nic_name, nic_conf in vm_conf.nic_all.items():
                if nic_conf.ip4_addr and nic_conf.ip4_addr.strip():
                    current_vm_ips.add(nic_conf.ip4_addr.strip())

            # 只保留其他虚拟机的IP地址
            other_vms_ips = allocated_ips - current_vm_ips

            # 遍历虚拟机的所有网卡
            for nic_name, nic_conf in vm_conf.nic_all.items():
                # 检查是否需要分配IP
                need_ipv4 = not nic_conf.ip4_addr or nic_conf.ip4_addr.strip() == ""

                if not need_ipv4:
                    # 如果已经有IP，检查是否被其他虚拟机占用
                    if nic_conf.ip4_addr.strip() in other_vms_ips:
                        logger.error(f"[{self.hs_config.server_name}] IP冲突: {nic_conf.ip4_addr} 已被其他虚拟机使用")
                        return vm_conf, ZMessage(
                            success=False,
                            action="NetCheck",
                            message=f"网卡 {nic_name} 的IP地址 {nic_conf.ip4_addr} 已被其他虚拟机使用"
                        )
                    logger.debug(f"[{self.hs_config.server_name}] 网卡 {nic_name} 已有IP: {nic_conf.ip4_addr}")
                    continue

                # 获取Docker网络名称
                nic_keys = "network_" + nic_conf.nic_type
                if not hasattr(self.hs_config, nic_keys) or getattr(self.hs_config, nic_keys, "") == "":
                    return vm_conf, ZMessage(
                        success=False,
                        action="NetCheck",
                        message=f"网卡 {nic_name} 的网络类型 {nic_conf.nic_type} 未在主机配置中定义"
                    )

                network_name = getattr(self.hs_config, nic_keys)

                # 获取Docker网络对象
                try:
                    network = client.networks.get(network_name)
                except Exception as e:
                    return vm_conf, ZMessage(
                        success=False,
                        action="NetCheck",
                        message=f"无法获取Docker网络 {network_name}: {str(e)}"
                    )

                # 获取网络的IPAM配置
                ipam_config = network.attrs.get('IPAM', {}).get('Config', [])
                if not ipam_config:
                    return vm_conf, ZMessage(
                        success=False,
                        action="NetCheck",
                        message=f"Docker网络 {network_name} 没有IPAM配置"
                    )

                # 获取网络中已使用的IP地址
                network_allocated_ips = set()
                containers = network.attrs.get('Containers', {})
                for container_id, container_info in containers.items():
                    ipv4_addr = container_info.get('IPv4Address', '')
                    if ipv4_addr:
                        # 移除CIDR后缀（如 /16）
                        ip_only = ipv4_addr.split('/')[0]
                        network_allocated_ips.add(ip_only)

                # 合并所有已分配的IP（其他虚拟机的IP + 当前网络中已使用的IP）
                all_allocated = other_vms_ips | network_allocated_ips

                # 查找对应的ipaddr_maps配置
                ipaddr_config = None
                for map_name, map_config in self.hs_config.ipaddr_maps.items():
                    if map_config.get('type') == nic_conf.nic_type:
                        ipaddr_config = map_config
                        break

                if not ipaddr_config:
                    return vm_conf, ZMessage(
                        success=False,
                        action="NetCheck",
                        message=f"网卡 {nic_name} 的网络类型 {nic_conf.nic_type} 未在ipaddr_maps中配置"
                    )

                # 从ipaddr_maps配置中获取IP分配范围
                ip_from = ipaddr_config.get('from', '')
                ip_nums = ipaddr_config.get('nums', 0)
                ip_gate = ipaddr_config.get('gate', '')
                ip_mask = ipaddr_config.get('mask', '')

                if not ip_from or ip_nums <= 0:
                    return vm_conf, ZMessage(
                        success=False,
                        action="NetCheck",
                        message=f"网卡 {nic_name} 的ipaddr_maps配置不完整（缺少from或nums）"
                    )

                # 从网络的子网中分配IP（根据ipaddr_maps的范围）
                ip_allocated = False
                try:
                    import ipaddress

                    # 解析起始IP地址
                    start_ip = ipaddress.ip_address(ip_from)

                    # 生成可用的IP地址列表（从起始IP开始，数量为nums）
                    available_ips = []
                    current_ip = start_ip
                    for i in range(ip_nums):
                        available_ips.append(str(current_ip))
                        current_ip += 1

                    # 遍历可用IP地址
                    for ip_str in available_ips:
                        # 跳过网关地址和已分配的IP
                        if ip_str == ip_gate or ip_str in all_allocated:
                            continue

                        # 分配这个IP
                        nic_conf.ip4_addr = ip_str
                        if ip_gate:
                            nic_conf.nic_gate = ip_gate
                        # 设置子网掩码
                        if ip_mask:
                            nic_conf.nic_mask = ip_mask
                        # 设置DNS
                        if self.hs_config.ipaddr_dnss:
                            nic_conf.dns_addr = self.hs_config.ipaddr_dnss
                        # 更新MAC地址
                        nic_conf.send_mac()

                        # 将新分配的IP添加到当前虚拟机IP集合和其他虚拟机IP集合中
                        # 避免后续网卡分配到相同IP
                        current_vm_ips.add(ip_str)
                        other_vms_ips.add(ip_str)

                        ip_allocated = True
                        logger.info(
                            f"[{self.hs_config.server_name}] 为网卡 {nic_name} 自动分配IP: {ip_str} "
                            f"(网络: {network_name}, 范围: {ip_from} - {available_ips[-1]})")
                        break

                except Exception as e:
                    logger.error(f"[{self.hs_config.server_name}] 处理IP分配时出错: {str(e)}", exc_info=True)
                    return vm_conf, ZMessage(
                        success=False,
                        action="NetCheck",
                        message=f"处理IP分配时出错: {str(e)}")

                # 如果没有分配到IP，返回失败
                if not ip_allocated:
                    logger.error(f"[{self.hs_config.server_name}] 无法为网卡 {nic_name} 分配IP，网络 {network_name} 无可用IP")
                    return vm_conf, ZMessage(
                        success=False,
                        action="NetCheck",
                        message=f"无法为网卡 {nic_name} 分配IP地址，"
                                f"Docker网络 {network_name} 中的所有IP已被占用或无可用IP"
                    )

            logger.info(f"[{self.hs_config.server_name}] 网络配置检查完成: {vm_conf.vm_uuid}")
            return vm_conf, ZMessage(
                success=True,
                action="NetCheck",
                message="网络配置检查完成"
            )

        except Exception as e:
            logger.error(f"[{self.hs_config.server_name}] 网络检查时出错: {str(e)}", exc_info=True)
            return vm_conf, ZMessage(
                success=False,
                action="NetCheck",
                message=f"网络检查失败: {str(e)}"
            )


    # 虚拟机扫描 ###############################################################
    def VMDetect(self) -> ZMessage:
        logger.info(f"[{self.hs_config.server_name}] 开始扫描Docker容器")
        # 专用操作 =============================================================
        client, result = self.api_conn()
        if not result.success:
            logger.error(f"[{self.hs_config.server_name}] 容器扫描失败: Docker连接失败")
            return result
        try:
            # 获取所有容器列表（包括停止的）
            containers = client.containers.list(all=True)
            # 使用主机配置的filter_name作为前缀过滤
            filter_prefix = self.hs_config.filter_name if self.hs_config else ""
            scanned_count = 0
            added_count = 0
            for container in containers:
                container_name = container.name
                # 前缀过滤
                if filter_prefix and not container_name.startswith(filter_prefix):
                    continue
                scanned_count += 1
                # 检查是否已存在
                if container_name in self.vm_saving:
                    continue
                # 创建默认虚拟机配置
                default_vm_config = VMConfig()
                default_vm_config.vm_uuid = container_name
                # 添加到服务器的虚拟机配置中
                self.vm_saving[container_name] = default_vm_config
                added_count += 1
            # 保存到数据库
            if added_count > 0:
                success = self.data_set()
                if not success:
                    logger.error(f"[{self.hs_config.server_name}] 保存扫描结果到数据库失败")
                    return ZMessage(
                        success=False, action="VScanner",
                        message="Failed to save scanned containers to database")
            logger.info(f"[{self.hs_config.server_name}] 容器扫描完成: 扫描{scanned_count}个，新增{added_count}个")
            return ZMessage(
                success=True,
                action="VScanner",
                message=f"扫描完成。共扫描到{scanned_count}个容器，新增{added_count}个容器配置。",
                results={
                    "scanned": scanned_count,
                    "added": added_count,
                    "prefix_filter": filter_prefix
                }
            )
        except Exception as e:
            logger.error(f"[{self.hs_config.server_name}] 扫描容器时出错: {str(e)}", exc_info=True)
            return ZMessage(
                success=False, action="VScanner",
                message=f"扫描容器时出错: {str(e)}")

    def IPUpdate(self, vm_conf: VMConfig, vm_last: VMConfig) -> ZMessage:
        return self.IPUpdate_TTY(vm_conf, vm_last)

    # 网络动态绑定 #############################################################
    def IPBinder_MAN(self, vm_conf: VMConfig, flag=True) -> ZMessage:
        # 连接服务 =============================================
        client, result = self.api_conn()
        if not result.success:
            return result
        # 获取容器 =============================================
        try:
            container = client.containers.get(vm_conf.vm_uuid)
        except NotFound:
            return ZMessage(
                success=False, action="NCCreate",
                message=f"容器 {vm_conf.vm_uuid} 不存在")
        # 配置网络 =============================================
        # 跟踪已处理的网络，避免重复连接同一网络
        processed_networks = set()
            # 断开默认bridge网络（容器创建时会自动连接）============
        if flag:
            try:
                default_net = client.networks.get('bridge')
                default_net.disconnect(container, force=True)
                logger.info(f"容器 已断开默认bridge网络")
            except Exception as e:
                logger.warning(f"断开默认网络失败: {str(e)}")
                traceback.print_exc()
        for nic_name, nic_conf in vm_conf.nic_all.items():
            # 获取配置 =========================================
            nic_keys = "network_" + nic_conf.nic_type
            if not hasattr(self.hs_config, nic_keys):
                if getattr(self.hs_config, nic_keys, "") == "":
                    logger.warning(f"主机网络{nic_keys}未配置")
                    continue
            nic_main = getattr(self.hs_config, nic_keys)
            # 检查是否已经处理过这个网络
            if nic_main in processed_networks:
                logger.warning(
                    f"跳过重复网络连接: {vm_conf.vm_uuid}，"
                    f"网卡 {nic_name} 使用相同网络类型")
                continue
            # 连接容器网络 =====================================
            try:
                nic_apis = client.networks.get(nic_main)
                if flag:
                    nic_apis.connect(
                        container,
                        ipv4_address=nic_conf.ip4_addr
                    )
                    # 标记此网络已处理
                    processed_networks.add(nic_main)
                else:
                    nic_apis.disconnect(container, force=True)
                logger.info(
                    f"{"连接" if flag else "删除"}容器网络 "
                    f"{vm_conf.vm_uuid}-{nic_name}: "
                    f"{nic_conf.ip4_addr}")
            except Exception as e:
                logger.warning(f"{"连接" if flag else "删除"}"
                               f"容器网络失败: {str(e)}")
                traceback.print_exc()
        # 返回结果 =============================================
        return ZMessage(
            success=True,
            action="NCCreate",
            message="网络配置成功")

    # 创建虚拟机 ###############################################################
    def VMCreate(self, vm_conf: VMConfig) -> ZMessage:
        logger.info(f"[{self.hs_config.server_name}] 开始创建容器: {vm_conf.vm_uuid}")
        logger.info(f"  - 镜像: {vm_conf.os_name}")
        logger.info(f"  - CPU: {vm_conf.cpu_num}核")
        logger.info(f"  - 内存: {vm_conf.mem_num}MB")
        logger.info(f"  - 网卡数量: {len(vm_conf.nic_all)}个")
        # 网络检查 =============================================================
        vm_conf, results = self.NetCheck(vm_conf)
        if not results.success:
            logger.error(f"[{self.hs_config.server_name}] 容器创建失败: 网络检查未通过")
            return results
        # 专用操作 =============================================================
        client, result = self.api_conn()
        if not result.success:
            logger.error(f"[{self.hs_config.server_name}] 容器创建失败: Docker连接失败")
            return result
        try:
            try:  # 容器是否存在 ==========================================
                client.containers.get(vm_conf.vm_uuid)
                return ZMessage(
                    success=False, action="VMCreate",
                    message=f"Container {vm_conf.vm_uuid} already exists")
            except NotFound:
                pass  # 容器不存在，继续创建
            # 加载容器镜像 ================================================
            install_result = self.VMSetups(vm_conf)
            if not install_result.success:
                raise Exception(f"无法加载镜像: {install_result.message}")
            # 构建容器配置 ================================================
            container_config = self.oci_conf(vm_conf)
            container = client.containers.create(
                image=vm_conf.os_name,
                name=vm_conf.vm_uuid,
                detach=True,
                hostname=vm_conf.vm_uuid,
                **container_config
            )
            self.IPBinder(vm_conf, True)
            # 启动容器 =========================================================
            container.start()
            self.VMPasswd(vm_conf.vm_uuid, vm_conf.os_pass)
            logger.success(f"[{self.hs_config.server_name}] 容器创建成功: {vm_conf.vm_uuid}")
        # 捕获所有异常 =========================================================
        except Exception as e:
            logger.error(f"[{self.hs_config.server_name}] 容器创建失败: {vm_conf.vm_uuid} - {str(e)}", exc_info=True)
            hs_result = ZMessage(
                success=False, action="VMCreate",
                message=f"容器创建失败: {str(e)}")
            self.logs_set(hs_result)
            return hs_result
        # 通用操作 =============================================================
        return super().VMCreate(vm_conf)

    # 安装虚拟机 ###############################################################
    def VMSetups(self, vm_conf: VMConfig) -> ZMessage:
        # 专用操作 =============================================================
        client, result = self.api_conn()
        if not result.success:
            return result

        try:
            image_name = vm_conf.os_name

            # 判断是否为 tar/tar.gz 文件
            if image_name.endswith('.tar') or image_name.endswith('.tar.gz'):
                # 从本地 tar 文件加载镜像
                image_file = f"{self.hs_config.images_path}/{image_name}"

                if not os.path.exists(image_file):
                    return ZMessage(
                        success=False, action="VInstall",
                        message=f"Image file not found: {image_file}")

                logger.info(f"Loading image from {image_file}")

                with open(image_file, 'rb') as f:
                    client.images.load(f.read())

                # 获取加载的镜像名称（从 tar 中提取）
                # 这里假设镜像名称与文件名相同（去掉后缀）
                vm_conf.os_name = image_name.replace('.tar.gz', '').replace('.tar', '')

                logger.info(f"Image loaded successfully: {vm_conf.os_name}")
            else:
                # 从 Docker Hub 或本地镜像库加载
                try:
                    # 先检查本地是否存在
                    client.images.get(image_name)
                    logger.info(f"Image {image_name} already exists locally")
                except NotFound:
                    # 本地不存在，尝试拉取
                    logger.info(f"Pulling image {image_name} from registry")
                    client.images.pull(image_name)
                    logger.info(f"Image {image_name} pulled successfully")

            return ZMessage(success=True, action="VInstall")

        except Exception as e:
            return ZMessage(
                success=False, action="VInstall",
                message=f"Failed to install image: {str(e)}")

    # 配置虚拟机 ###############################################################
    def VMUpdate(self, vm_conf: VMConfig, vm_last: VMConfig) -> ZMessage:
        logger.info(f"[{self.hs_config.server_name}] 开始更新容器配置: {vm_conf.vm_uuid}")
        # 通用操作 =============================================================
        vm_conf, net_result = self.NetCheck(vm_conf)
        if not net_result.success:
            logger.error(f"[{self.hs_config.server_name}] 容器更新失败: 网络检查未通过")
            return net_result
        # 专用操作 =============================================================
        client, result = self.api_conn()
        if not result.success:
            logger.error(f"[{self.hs_config.server_name}] 容器更新失败: Docker连接失败")
            return result
        try:
            container_name = vm_conf.vm_uuid
            try:  # 获取容器 ===================================================
                container = client.containers.get(container_name)
            except NotFound:
                return ZMessage(
                    success=False, action="VMUpdate",
                    message=f"Container {container_name} does not exist")
            # 停止容器 =========================================================
            if container.status == "running":
                self.VMPowers(container_name, VMPowers.H_CLOSE)
            # 重装系统（如果系统镜像改变）======================================
            if vm_conf.os_name != vm_last.os_name and vm_last.os_name != "":
                # 删除旧容器 ===================================================
                container.remove()
                # 重新创建 =====================================================
                return self.VMCreate(vm_conf)
            # 检查是否需要更新资源配置
            cpu_changed = vm_conf.cpu_num != vm_last.cpu_num
            ram_changed = vm_conf.mem_num != vm_last.mem_num
            # 更新资源配置 =====================================================
            if cpu_changed or ram_changed:
                # 使用 docker update 接口动态更新容器资源限制
                new_conf = {}
                # CPU 限制
                if cpu_changed and vm_conf.cpu_num > 0:
                    new_conf['nano_cpus'] = int(vm_conf.cpu_num * 1e9)
                # 内存限制（转换为字节）
                if ram_changed and vm_conf.mem_num > 0:
                    new_conf['mem_limit'] = f"{vm_conf.mem_num}m"
                # 执行更新
                if new_conf:
                    container.update(**new_conf)
                    logger.info(f"容器 {container_name} 配置更新: {new_conf}")
                # 如果容器正在运行，需要重启以应用资源限制变更
                if container.status == "running":
                    self.VMPowers(container_name, VMPowers.H_RESET)
                    logger.info(f"容器 {container_name} 已重启以应用资源限制")
            # 更新网络配置 ======================================================
            network_result = self.IPUpdate(vm_conf, vm_last)
            if not network_result.success:
                return ZMessage(
                    success=False, action="VMUpdate",
                    message=f"网络配置更新失败: {network_result.message}")

            # 更新密码
            self.VMPowers(container_name, VMPowers.S_START)
            self.VMPasswd(vm_conf.vm_uuid, vm_conf.os_pass)
            logger.success(f"[{self.hs_config.server_name}] 容器配置更新成功: {container_name}")
            hs_result = ZMessage(
                success=True, action="VMUpdate",
                message=f"容器 {container_name} 配置更新成功")
            self.logs_set(hs_result)
            return hs_result
        except Exception as e:
            logger.error(f"[{self.hs_config.server_name}] 容器更新失败: {container_name} - {str(e)}", exc_info=True)
            return ZMessage(
                success=False, action="VMUpdate",
                message=f"容器更新失败: {str(e)}")

    # 删除虚拟机 ###############################################################
    def VMDelete(self, vm_name: str, rm_back=True) -> ZMessage:
        logger.info(f"[{self.hs_config.server_name}] 开始删除容器: {vm_name} (删除备份: {rm_back})")
        # 专用操作 =============================================================
        client, result = self.api_conn()
        if not result.success:
            logger.error(f"[{self.hs_config.server_name}] 容器删除失败: Docker连接失败")
            return result
        # 获取虚拟机配置 =======================================================
        vm_conf = self.VMSelect(vm_name)
        if vm_conf is None:
            logger.warning(f"[{self.hs_config.server_name}] 容器配置不存在: {vm_name}")
            return ZMessage(
                success=False, action="VMDelete",
                message=f"容器 {vm_name} 不存在")
        # 停止并删除容器 =======================================================
        try:
            container = client.containers.get(vm_name)
            # 停止容器
            if container.status == "running":
                self.VMPowers(vm_name, VMPowers.H_CLOSE)
            # 删除容器（包括卷）
            container.remove(v=True, force=True)
            logger.info(f"[{self.hs_config.server_name}] 容器已删除: {vm_name}")
        except NotFound:
            logger.warning(f"[{self.hs_config.server_name}] 容器在Docker中不存在: {vm_name}")
        except Exception as e:
            logger.error(f"[{self.hs_config.server_name}] 删除容器失败: {vm_name} - {str(e)}", exc_info=True)
            return ZMessage(
                success=False, action="VMDelete",
                message=f"删除容器失败: {str(e)}")
        # 删除以容器名开头的镜像 =======================================
        try:
            images = client.images.list()
        except Exception as e:
            logger.warning(f"获取镜像列表失败: {str(e)}")
            traceback.print_exc()
            images = []
        # 遍历并删除镜像 ===============================================
        deleted_images = []
        # 将vm_name转换为小写，因为恢复时创建的镜像tag是小写的
        vm_name_lower = vm_name.lower()

        for image in images:
            # 检查镜像是否有以vm_name开头的tag
            has_matching_tag = False
            matching_tags = []

            for tag in image.tags:
                # 提取镜像名称（去掉:latest等后缀）
                image_name = tag.split(':')[0] if ':' in tag else tag
                # 转换为小写进行比较（因为Docker镜像tag在恢复时被转为小写）
                image_name_lower = image_name.lower()
                # 检查镜像名是否以vm_name开头（不区分大小写）
                if image_name_lower.startswith(vm_name_lower):
                    has_matching_tag = True
                    matching_tags.append(tag)

            # 如果找到匹配的tag，删除整个镜像
            if has_matching_tag:
                try:
                    client.images.remove(image.id, force=True)
                    deleted_images.extend(matching_tags)
                    logger.info(f"删除镜像: {', '.join(matching_tags)} ({image.id[:12]})")
                except Exception as img_err:
                    logger.warning(f"删除镜像 {image.id[:12]} 失败: {str(img_err)}")
                    traceback.print_exc()

        if deleted_images:
            logger.info(f"[{self.hs_config.server_name}] 共删除 {len(deleted_images)} 个镜像标签")
        # 删除备份 =====================================================
        if rm_back:
            logger.info(f"[{self.hs_config.server_name}] 删除容器备份和挂载: {vm_name}")
            self.RMBackup(vm_name, "")
            self.RMMounts(vm_name, "")
        # 通用操作 =============================================================
        logger.success(f"[{self.hs_config.server_name}] 容器删除完成: {vm_name}")
        return super().VMDelete(vm_name)

    # 虚拟机电源 ###############################################################
    def VMPowers(self, vm_name: str, power: VMPowers) -> ZMessage:
        power_map = {
            VMPowers.S_START: "启动",
            VMPowers.H_CLOSE: "强制关机",
            VMPowers.S_CLOSE: "正常关机",
            VMPowers.S_RESET: "正常重启",
            VMPowers.H_RESET: "强制重启",
            VMPowers.A_PAUSE: "暂停",
            VMPowers.A_WAKED: "恢复"
        }
        logger.info(f"[{self.hs_config.server_name}] 容器电源操作: {vm_name} - {power_map.get(power, '未知')}")
        
        # 先调用父类方法设置中间状态
        super().VMPowers(vm_name, power)
        
        # 专用操作 =============================================================
        client, result = self.api_conn()
        if not result.success:
            logger.error(f"[{self.hs_config.server_name}] 电源操作失败: Docker连接失败")
            return result
        try:
            container = client.containers.get(vm_name)

            if power == VMPowers.S_START:
                if container.status != "running":
                    container.start()
                    logger.success(f"[{self.hs_config.server_name}] 容器已启动: {vm_name}")
                else:
                    logger.info(f"[{self.hs_config.server_name}] 容器已在运行: {vm_name}")

            elif power == VMPowers.H_CLOSE or power == VMPowers.S_CLOSE:
                logger.info(f"Attempting to stop container {vm_name} with current status: {container.status}")

                if container.status == "running":
                    container.stop(timeout=30 if power == VMPowers.S_CLOSE else 5)  # 增加超时时间到30秒
                    logger.info(f"Container {vm_name} stopped successfully from running state")
                elif container.status == "paused":
                    # 如果容器处于暂停状态，先恢复再停止
                    container.unpause()
                    logger.info(f"Container {vm_name} resumed from paused state")
                    container.stop(timeout=30 if power == VMPowers.S_CLOSE else 5)
                    logger.info(f"Container {vm_name} stopped successfully after resuming")
                elif container.status in ["exited", "dead", "created"]:
                    # 容器已经停止或处于非运行状态，无需操作
                    logger.info(f"Container {vm_name} is already in {container.status} state, no action needed")
                elif container.status == "restarting":
                    # 如果容器正在重启，等待重启完成后停止
                    logger.info(f"Container {vm_name} is restarting, waiting before stopping...")
                    time.sleep(5)  # 等待5秒
                    container.stop(timeout=30 if power == VMPowers.S_CLOSE else 5)
                    logger.info(f"Container {vm_name} stopped successfully after restarting")
                else:
                    # 处理未知状态
                    logger.warning(f"Container {vm_name} has unknown status: {container.status}, attempting force stop")
                    try:
                        container.stop(timeout=30 if power == VMPowers.S_CLOSE else 5)
                        logger.info(f"Container {vm_name} force stopped successfully")
                    except Exception as force_stop_error:
                        logger.error(f"Force stop failed for container {vm_name}: {str(force_stop_error)}")
                        traceback.print_exc()
                        return ZMessage(
                            success=False, action="VMPowers",
                            message=f"无法停止容器 {vm_name}，当前状态: {container.status}，强制停止也失败")

            elif power == VMPowers.S_RESET or power == VMPowers.H_RESET:
                if container.status == "running":
                    container.restart(timeout=30 if power == VMPowers.S_RESET else 5)  # 增加超时时间到30秒
                elif container.status == "paused":
                    # 如果容器处于暂停状态，先恢复再重启
                    container.unpause()
                    container.restart(timeout=30 if power == VMPowers.S_RESET else 5)
                else:
                    container.start()
                logger.info(f"Container {vm_name} restarted")

            elif power == VMPowers.A_PAUSE:
                if container.status == "running":
                    container.pause()
                    logger.info(f"Container {vm_name} paused")
                elif container.status == "paused":
                    logger.info(f"Container {vm_name} is already paused")
                else:
                    logger.warning(f"Cannot pause container {vm_name} with status: {container.status}")
                    return ZMessage(
                        success=False, action="VMPowers",
                        message=f"无法暂停容器 {vm_name}，当前状态: {container.status}")

            elif power == VMPowers.A_WAKED:
                if container.status == "paused":
                    container.unpause()
                    logger.info(f"Container {vm_name} resumed from pause")
                elif container.status == "running":
                    logger.info(f"Container {vm_name} is already running")
                else:
                    logger.warning(f"Cannot resume container {vm_name} with status: {container.status}")
                    return ZMessage(
                        success=False, action="VMPowers",
                        message=f"无法恢复容器 {vm_name}，当前状态: {container.status}")

            logger.success(f"[{self.hs_config.server_name}] 电源操作成功: {vm_name} - {power_map.get(power, '未知')}")
            hs_result = ZMessage(success=True, action="VMPowers")
            self.logs_set(hs_result)

        except NotFound:
            logger.error(f"[{self.hs_config.server_name}] 容器不存在: {vm_name}")
            hs_result = ZMessage(
                success=False, action="VMPowers",
                message=f"Container {vm_name} does not exist")
            self.logs_set(hs_result)
            return hs_result
        except Exception as e:
            error_msg = f"电源操作失败: {str(e)}"
            logger.error(f"[{self.hs_config.server_name}] 电源操作失败: {vm_name} - {str(e)}", exc_info=True)

            # 提供更具体的错误诊断信息
            if "permission" in str(e).lower():
                error_msg += " (可能是权限不足，请检查Docker守护进程权限)"
            elif "timeout" in str(e).lower():
                error_msg += " (操作超时，容器可能无响应)"
            elif "conflict" in str(e).lower():
                error_msg += " (容器状态冲突，可能有其他操作正在进行)"
            elif "not found" in str(e).lower():
                error_msg += " (Docker API无法找到容器)"

            hs_result = ZMessage(
                success=False, action="VMPowers",
                message=error_msg)
            self.logs_set(hs_result)
            return hs_result

        # 通用操作 =============================================================
        return hs_result

    # 获取虚拟机实际状态（从API）==============================================
    def GetPower(self, vm_name: str) -> str:
        """从Docker API获取容器实际状态"""
        try:
            client, result = self.api_conn()
            if not result.success:
                return ""
            
            container = client.containers.get(vm_name)
            container.reload()
            
            # 映射Docker状态到中文状态
            state_map = {
                'running': '运行中',
                'exited': '已关机',
                'paused': '已暂停',
                'dead': '已关机',
                'created': '已关机',
                'restarting': '重启中'
            }
            return state_map.get(container.status, '未知')
        except NotFound:
            logger.warning(f"容器 {vm_name} 不存在")
            return ""
        except Exception as e:
            logger.warning(f"从API获取容器 {vm_name} 状态失败: {str(e)}")
        return ""

    # 设置虚拟机密码 ###########################################################
    def VMPasswd(self, vm_name: str, os_pass: str) -> ZMessage:
        logger.info(f"[{self.hs_config.server_name}] 开始设置容器密码: {vm_name}")
        # 专用操作 =============================================================
        client, result = self.api_conn()
        if not result.success:
            logger.error(f"[{self.hs_config.server_name}] 设置密码失败: Docker连接失败")
            return result

        try:
            container = client.containers.get(vm_name)

            if container.status != "running":
                return ZMessage(
                    success=False, action="Password",
                    message=f"容器 {vm_name} 未运行，请先启动容器")

            # 执行命令设置root密码
            exec_result = container.exec_run(
                cmd=["sh", "-c", f"echo 'root:{os_pass}' | chpasswd"],
                stdin=True
            )

            if exec_result.exit_code != 0:
                output = exec_result.output.decode() if exec_result.output else "未知错误"
                return ZMessage(
                    success=False, action="Password",
                    message=f"设置密码失败: {output}")

            logger.success(f"[{self.hs_config.server_name}] 容器root密码已更新: {vm_name}")

            hs_result = ZMessage(success=True, action="Password", message="密码设置成功")
            self.logs_set(hs_result)
            return hs_result

        except NotFound:
            logger.error(f"[{self.hs_config.server_name}] 容器不存在: {vm_name}")
            return ZMessage(
                success=False, action="Password",
                message=f"容器 {vm_name} 不存在")
        except Exception as e:
            logger.error(f"[{self.hs_config.server_name}] 设置密码失败: {vm_name} - {str(e)}", exc_info=True)
            return ZMessage(
                success=False, action="Password",
                message=f"设置密码失败: {str(e)}")

    # 备份虚拟机 ###############################################################
    def VMBackup(self, vm_name: str, vm_tips: str) -> ZMessage:
        logger.info(f"[{self.hs_config.server_name}] 开始备份容器: {vm_name} (备注: {vm_tips})")
        # 专用操作 =============================================================
        client, result = self.api_conn()
        if not result.success:
            logger.error(f"[{self.hs_config.server_name}] 备份失败: Docker连接失败")
            return result
        vm_conf = self.VMSelect(vm_name)
        if not vm_conf:
            logger.error(f"[{self.hs_config.server_name}] 备份失败: 容器配置不存在 - {vm_name}")
            return ZMessage(
                success=False,
                action="Backup",
                message="虚拟机不存在")
        try:
            # 获取容器 ===================================================
            containers = client.containers.get(vm_name)
            # 检查容器是否正在运行
            is_running = containers.status == "running"
            if is_running:  # 先停止容器以确保数据一致性
                containers.stop(timeout=30)
                logger.info(f"容器 {vm_name} 已停止")
            # 构建备份文件名 =============================================
            bak_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            bak_file = f"{vm_name}_{bak_time}.tar.gz"
            bak_path = f"{self.hs_config.backup_path}/{bak_file}"
            cmd_exec = f"docker export {vm_name} | gzip > \"{bak_path}\""
            bak_flag = False
            # 远程主机：使用SSH连接执行docker export命令 =================
            if self.web_flag():
                logger.info(f"检测到远程主机，使用SSH连接进行备份")
                # 建立SSH连接 --------------------------------------------
                bak_flag, message = self.port_forward.connect_ssh()
                if not bak_flag:
                    raise Exception(f"SSH连接失败: {message}")
                # 远程备份路径 -------------------------------------------
                logger.info(f"在远程服务器执行备份命令: {cmd_exec}")
                bak_flag, out, err = self.port_forward.execute_command(
                    cmd_exec, is_remote=True)
                # 关闭SSH连接 --------------------------------------------
                self.port_forward.close_ssh()
                logger.info(f"容器 {vm_name} 远程备份完成: {bak_path}")
            # 本地主机 ===================================================
            else:  # 本地主机：使用docker export命令通过管道压缩为tar.gz
                # 确保备份目录存在 =======================================
                os.makedirs(self.hs_config.backup_path, exist_ok=True)
                # 使用docker export命令导出并通过gzip压缩 ================
                logger.info(f"开始备份容器 {vm_name} 到 {bak_path}")
                result = subprocess.run(
                    cmd_exec, shell=True, capture_output=True, text=True)
                # 检查备份结果 -------------------------------------------
                if result.returncode == 0:
                    bak_flag = True
                logger.info(
                    f"容器 {vm_name} 备份完成，"
                    f"文件大小: "
                    f"{os.path.getsize(bak_path) / 1024 / 1024:.2f} MB")
            # 检查备份结果 -----------------------------------------------
            if not bak_flag:
                return ZMessage(
                    success=False, action="VMBackup",
                    message=f"备份失败: {vm_name}")
            else:
                vm_conf.backups.append(VMBackup(
                    backup_time=datetime.datetime.now(),
                    backup_name=bak_file,
                    backup_hint=vm_tips,
                    old_os_name=vm_conf.os_name
                ))
            # 如果容器之前在运行，重新启动 ===============================
            if is_running:
                containers.start()
                logger.info(f"容器 {vm_name} 已重新启动")
            # 记录备份结果 ===============================================
            logger.success(f"[{self.hs_config.server_name}] 容器备份成功: {vm_name} -> {bak_file}")
            hs_result = ZMessage(
                success=True, action="VMBackup",
                message=f"容器备份成功，文件: {bak_file}",
                results={"backup_file": bak_file, "backup_path": bak_path}
            )
            self.vm_saving[vm_name] = vm_conf
            self.logs_set(hs_result)
            self.data_set()
            return hs_result
        # 处理异常 =======================================================
        except NotFound:
            logger.error(f"[{self.hs_config.server_name}] 容器不存在: {vm_name}")
            return ZMessage(
                success=False, action="VMBackup",
                message=f"容器 {vm_name} 不存在")
        # 处理其他异常 ===================================================
        except Exception as e:
            logger.error(f"[{self.hs_config.server_name}] 备份容器失败: {vm_name} - {str(e)}", exc_info=True)
            return ZMessage(
                success=False, action="VMBackup",
                message=f"备份失败: {str(e)}")

    # 恢复虚拟机 ###############################################################
    def Restores(self, vm_name: str, vm_back: str) -> ZMessage:
        logger.info(f"[{self.hs_config.server_name}] 开始恢复容器: {vm_name} <- {vm_back}")
        # 连接接口 =============================================================
        client, result = self.api_conn()
        if not result.success:
            logger.error(f"[{self.hs_config.server_name}] 恢复失败: Docker连接失败")
            return result
        # 获取VM配置 ===========================================================
        vm_conf = self.VMSelect(vm_name)
        if not vm_conf:
            return ZMessage(
                success=False, action="Restores",
                message=f"容器 {vm_name} 不存在")
        # 获取备份信息 =========================================================
        vb_conf = None
        for vb_item in vm_conf.backups:
            if vb_item.backup_name == vm_back:
                vb_conf = vb_item
                break
        if not vb_conf:
            return ZMessage(
                success=False, action="Restores",
                message=f"备份 {vm_back} 不存在")
        # 完整路径 =============================================================
        backup_file = f"{self.hs_config.backup_path}/{vm_back}"
        # 检查备份文件是否存在 =================================================
        file_exists = False
        # 远程主机：使用SSH检查文件是否存在 ====================================
        if self.web_flag():
            success, message = self.port_forward.connect_ssh()
            if not success:
                return ZMessage(
                    success=False, action="Restores",
                    message=f"SSH连接失败: {message}")
            check_cmd = f"test -f \"{backup_file}\" && echo '1' || echo '0'"
            success, stdout, stderr = self.port_forward.execute_command(
                check_cmd, is_remote=True)
            if success and stdout.strip() == '1':
                file_exists = True
            self.port_forward.close_ssh()
        # 本地主机：直接检查文件是否存在 =======================================
        else:
            file_exists = os.path.exists(backup_file)
        # 处理备份文件不存在 ===================================================
        if not file_exists:
            return ZMessage(
                success=False, action="Restores",
                message=f"备份文件不存在: {vm_back}")
        # 恢复容器 =============================================================
        try:
            # 删除容器 =========================================================
            try:  # 检查目标容器是否已存在
                container = client.containers.get(vm_name)
                # 如果容器正在运行，先停止
                if container.status == "running":
                    container.stop(timeout=5)
                # 删除容器
                container.remove(force=True)
                logger.info(f"已删除旧容器 {vm_name}")
            except NotFound:
                pass
            # 开始恢复 =========================================================
            logger.info(f"开始恢复容器 {vm_name}，"
                        f"备份文件: {backup_file}")
            # 选择恢复方式 =====================================================
            if self.web_flag():
                logger.info(f"从远程主机恢复备份")
                # Docker镜像名称必须是小写
                image_tag = vm_back.split('.')[0].lower()
                self.port_forward.connect_ssh()
                # 构建docker import命令 ========================================
                import_cmd = (f"gunzip -c \"{backup_file}\" "
                              f"| docker import - {image_tag}")
                # 导入镜像 =====================================================
                success, stdout, stderr = self.port_forward.execute_command(
                    import_cmd, is_remote=True)
                # 关闭SSH连接 ==================================================
                self.port_forward.close_ssh()
                # 检查导入是否成功 =============================================
                if not success:
                    raise Exception(f"远程导入镜像失败: {stderr}")
                # 使用导入的镜像 ===============================================
                try:
                    image = client.images.get(image_tag)
                except Exception as e:
                    traceback.print_exc()
                    logger.info(f"无法导入镜像: {image_tag} {e}")
                    return ZMessage(
                        success=False, action="Restores",
                        message=f"无法导入镜像: {image_tag}")
            # 本地主机：直接读取文件导入 =======================================
            else:
                # 使用docker import直接导入tar.gz为镜像 ------------------------
                if backup_file.endswith('.tar.gz'):
                    with open(backup_file, 'rb') as f:
                        # import_image会读取文件并创建镜像
                        image = client.images.load(f.read())[0]
                    logger.info(f"从备份文件导入镜像: {image.id}")
                # 直接导入tar文件 ----------------------------------------------
                elif backup_file.endswith('.tar'):

                    with open(backup_file, 'rb') as f:
                        image = client.images.load(f.read())[0]
                    logger.info(f"从备份文件导入镜像: {image.id}")
                # 未知备份文件格式 ---------------------------------------------
                else:
                    raise Exception(f"未知备份文件格式: {backup_file}")
            # 构建容器配置 =================================================
            container_config = self.oci_conf(vm_conf)
            # 从备份恢复的镜像没有默认CMD，需要指定启动命令
            container = client.containers.create(
                image=image.id,
                name=vm_name,
                command=["/sbin/init"],  # 使用init作为默认启动命令
                detach=True,
                hostname=vm_name,
                **container_config
            )
            # 网络配置 ======================================================
            network_result = self.IPBinder(vm_conf, flag=True)
            if not network_result.success:
                logger.warning(f"网络配置失败: {network_result.message}")
            # 启动容器 ======================================================
            container.start()
            vm_conf.os_name = vb_conf.old_os_name
            logger.info(f"容器 {vm_name} 恢复成功")
            # 保存配置 ======================================================
            self.vm_saving[vm_name] = vm_conf
            logger.success(f"[{self.hs_config.server_name}] 容器恢复成功: {vm_name} <- {vm_back}")
            hs_result = ZMessage(
                success=True, action="Restores",
                message=f"容器恢复成功: {vm_name}",
                results={"container_id": container.id, "image_id": image.id}
            )
            self.logs_set(hs_result)
            self.data_set()
            return hs_result
        # 处理异常 ==========================================================
        except Exception as e:
            logger.error(f"[{self.hs_config.server_name}] 恢复容器失败: {vm_name} - {str(e)}", exc_info=True)
            return ZMessage(
                success=False, action="Restores",
                message=f"恢复失败: {str(e)}")

    # VM镜像挂载 ###############################################################
    def HDDMount(self, vm_name: str, vm_imgs: SDConfig, in_flag=True) -> ZMessage:
        # 专用操作 =============================================================
        # Docker容器不支持动态挂载/卸载磁盘
        return ZMessage(
            success=False, action="HDDMount",
            message="Docker容器不支持动态磁盘挂载")

    # ISO镜像挂载 ##############################################################
    def ISOMount(self, vm_name: str, vm_imgs: IMConfig, in_flag=True) -> ZMessage:
        # 专用操作 =============================================================
        # Docker 容器不需要 ISO 挂载，返回成功但不执行操作
        return ZMessage(
            success=True, action="ISOMount",
            message="Docker containers do not support ISO mounting")

    # 虚拟机远程访问 ###########################################################
    def VMRemote(self, vm_uuid: str, ip_addr: str = "127.0.0.1") -> ZMessage:
        # 专用操作 =============================================================
        if vm_uuid not in self.vm_saving:
            return ZMessage(
                success=False,
                action="VCRemote",
                message="虚拟机不存在")
        # 获取虚拟机配置 =======================================================
        vm_conf = self.vm_saving[vm_uuid]
        container_name = vm_conf.vm_uuid
        # 获取虚拟机SSH端口 ====================================================
        wan_port = None
        try:
            all_port = vm_conf.nat_all
            for now_port in all_port:
                if now_port.lan_port == 22:
                    wan_port = now_port.wan_port
                    break
        except Exception as e:
            logger.warning(f"无法获取SSH端口: {container_name}: {str(e)}")
        if not wan_port and self.hs_config.server_pass == "":
            return ZMessage(
                success=False,
                action="VCRemote",
                message="当未设置主机密码时，必须添加一个端口映射到22端口<br/>"
                        "未找到当前虚拟机22端口对应端口映射信息，无法继续")
        # 2. 获取主机外网IP ====================================================
        if len(self.hs_config.public_addr) == 0:
            return ZMessage(
                success=False,
                action="VCRemote",
                message="主机外网IP不存在")
        public_ip = self.hs_config.public_addr[0]
        if public_ip in ["localhost", "127.0.0.1", ""]:
            public_ip = "127.0.0.1"  # 默认使用本地
        # 3. 启动tty会话web ====================================================
        tty_port, token = self.web_terminal.open_tty(
            self.hs_config, wan_port, vm_uuid)
        if tty_port <= 0:
            return ZMessage(
                success=False,
                action="VCRemote",
                message="启动tty会话失败"
            )
        # 4. 添加SSH代理 ========================================================
        try:
            # 使用新的SSH代理管理方法
            target_ip = "127.0.0.1"  # ttyd运行在本机
            success = self.http_manager.create_vnc(token, target_ip, tty_port)
            if not success:
                self.web_terminal.stop_tty(tty_port)  # 清理tty
                return ZMessage(
                    success=False,
                    action="VCRemote",
                    message="添加SSH代理失败")
        except Exception as e:
            logger.error(f"SSH代理配置失败: {str(e)}")
            traceback.print_exc()
            self.web_terminal.stop_tty(tty_port)
            return ZMessage(
                success=False,
                action="VCRemote",
                message=f"SSH代理配置失败: {str(e)}")
        # 5. 构造返回URL =======================================================
        vnc_port = self.hs_config.remote_port  # SSH代理统一使用1884端口
        url = f"http://{public_ip}:{vnc_port}/{token}"
        logger.info(
            f"VMRemote for {vm_uuid}: "
            f"SSH({public_ip}:{wan_port}) "
            f"-> tty({tty_port}) -> proxy(/{token}) -> {url}")
        # 6. 返回结果 ==========================================================
        return ZMessage(
            success=True,
            action="VCRemote",
            message=url,
            results={
                "tty_port": tty_port,
                "token": token,
                "vnc_port": vnc_port,
                "url": url,
                "ssh_port": wan_port
            }
        )

    # 查找显卡 #################################################################
    def PCIShows(self) -> dict[str, str]:
        # 专用操作 =============================================================
        # Docker 容器不需要 GPU 管理，返回空字典
        # 通用操作 =============================================================
        return {}

    # 端口映射 #################################################################
    def PortsMap(self, map_info: PortData, flag=True) -> ZMessage:
        return self.PortsMap_TTY(map_info, flag)

    # 删除VM备份 ###############################################################
    def RMBackup(self, vm_name: str, vm_back: str = "") -> ZMessage:
        return self.RMBackup_TTY(vm_name, vm_back)

    # 删除容器挂载路径 #########################################################
    def RMMounts(self, vm_name: str, vm_imgs: str = "") -> ZMessage:
        return self.RMMounts_TTY(vm_name, vm_imgs)
