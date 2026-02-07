################################################################################
#                          BasicServer - 基础服务器类
################################################################################
import os
import shutil
import platform
import datetime
import traceback
import subprocess
from copy import deepcopy
from loguru import logger
from random import randint
from HostModule.HttpManager import HttpManager
from HostModule.NetsManager import NetsManager
from VNCConsole.VNCSManager import WebsocketUI
from VNCConsole.VNCSManager import VNCSManager
from MainObject.Config.HSConfig import HSConfig
from MainObject.Config.IMConfig import IMConfig
from MainObject.Config.PortData import PortData
from MainObject.Config.SDConfig import SDConfig
from MainObject.Config.VMBackup import VMBackup
from MainObject.Config.VMPowers import VMPowers
from MainObject.Config.WebProxy import WebProxy
from MainObject.Public.HWStatus import HWStatus
from MainObject.Public.ZMessage import ZMessage
from MainObject.Config.VMConfig import VMConfig
from MainObject.Config.IPConfig import IPConfig
from MainObject.Server.HSStatus import HSStatus
from HostServer.OCInterfaceAPI import SSHTerminal
from HostServer.OCInterfaceAPI import PortForward


class BasicServer:
    # 初始化 ########################################################################
    def __init__(self, config: HSConfig, **kwargs):
        # 宿主机配置 =====================================================
        self.hs_config: HSConfig | None = config
        # 虚拟机配置 =====================================================
        self.vm_saving: dict[str, VMConfig] = {}
        self.vm_remote: VNCSManager | None | str = None
        # 数据库引用 =====================================================
        self.save_data = kwargs.get('db', None)
        # 网络管理 =======================================================
        self.http_manager = None
        self.port_forward = None
        self.web_terminal = None
        # 加载数据 =======================================================
        self.__load__(**kwargs)
        # 日志系统配置 ===================================================
        self.init_log()

    # 转换字典 ######################################################################
    def __save__(self):
        return {
            "hs_config": self.hs_config.__save__(),
            "vm_saving": {
                k: v.__save__()
                for k, v in self.vm_saving.items()
            }
        }

    # 加载数据 ######################################################################
    def __load__(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    # ###############################################################################
    # 内置的方法 ####################################################################
    # ###############################################################################

    # 配置日志系统 ##################################################################
    def init_log(self) -> None:
        try:
            if self.hs_config.server_name:
                # 为每个主机创建独立的日志文件
                log_file = f"./DataSaving/log-{self.hs_config.server_name}.log"
                logger.add(
                    log_file,
                    rotation="10 MB",
                    retention="7 days",
                    compression="zip",
                    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
                    level="INFO"
                )
                logger.info(
                    f"[{self.hs_config.server_name}] 日志系统已初始化"
                )
        except Exception as e:
            logger.error(f"日志系统初始化失败: {e}")

    # 清理过期日志 ##################################################################
    def cron_log(self, days: int = 7) -> int:
        if self.save_data and self.hs_config.server_name:
            return self.save_data.del_hs_logger(self.hs_config.server_name, days)
        return 0

    # 添加日志记录 ##################################################################
    def push_log(self, log: ZMessage):
        try:
            # 使用loguru记录日志
            log_level = "ERROR" if not log.success else "INFO"
            log_msg = (
                f"[{self.hs_config.server_name}] "
                f"{log.actions}: {log.message}"
            )

            if log_level == "ERROR":
                logger.error(log_msg)
            else:
                logger.info(log_msg)

            # 立即保存到数据库
            if self.save_data and self.hs_config.server_name:
                self.save_data.add_hs_logger(
                    self.hs_config.server_name, log
                )
        except Exception as e:
            logger.error(f"添加日志失败: {e}")

    # 获取7z文件路径 ################################################################
    def path_zip(self) -> str:
        if "zip_exec" in self.hs_config.extend_data:
            return self.hs_config.extend_data["zip_exec"]
        system = platform.system().lower()
        if system == "windows":
            return os.path.join("HostConfig", "7zipwinx64", "7z.exe")
        elif system == "linux":
            return os.path.join("HostConfig", "7ziplinx64", "7zz")
        elif system == "darwin":  # macOS
            return os.path.join("HostConfig", "7zipmacu2b", "7zz")
        else:
            raise OSError(f"不支持的操作系统: {system}")

    # 保存主机状态数据 ##############################################################
    def host_get(self) -> list[HSStatus]:
        if self.save_data and self.hs_config.server_name:
            return self.save_data.get_hs_status(self.hs_config.server_name)
        return []

    # 保存主机状态数据 ##############################################################
    def host_set(self, hs_status: HSStatus | HWStatus) -> bool:
        if self.save_data and self.hs_config.server_name:
            try:
                success = self.save_data.add_hs_status(
                    self.hs_config.server_name,
                    hs_status.__save__() \
                        if isinstance(hs_status, HSStatus) \
                        else hs_status
                )
                if success:
                    logger.debug(
                        f"[{self.hs_config.server_name}] 主机状态已保存"
                    )
                return success
            except Exception as e:
                logger.error(
                    f"[{self.hs_config.server_name}] 保存数据失败: {e}"
                )
                return False
        return False

    # 保存日志到数据库 ##############################################################
    def logs_set(self, in_logs) -> bool:
        if self.save_data and self.hs_config.server_name:
            try:
                # 保存VM配置数据
                success = self.save_data.add_hs_logger(
                    self.hs_config.server_name, in_logs)
                if success:
                    logger.debug(f"[{self.hs_config.server_name}] 主机日志已保存")
                return success
            except Exception as e:
                logger.error(f"[{self.hs_config.server_name}] 保存数据失败: {e}")
                return False
        return False

    # 保存虚拟机状态到数据库 ########################################################
    def vm_status_set(self, vm_uuid: str, status_name: str) -> bool:
        """保存虚拟机操作状态到数据库
        :param vm_uuid: 虚拟机UUID
        :param status_name: 状态名称（启动/关机/强制关机/强制重启/暂停/恢复/重装/改密/修改配置）
        :return: 是否成功
        """
        if self.save_data and self.hs_config.server_name:
            try:
                from MainObject.Public.HWStatus import HWStatus
                import time
                # 创建状态对象
                hw_status = HWStatus()
                hw_status.vm_state = status_name
                hw_status.on_update = int(time.time())
                # 保存到数据库
                success = self.save_data.add_vm_status(
                    self.hs_config.server_name,
                    vm_uuid,
                    hw_status
                )
                if success:
                    logger.debug(
                        f"[{self.hs_config.server_name}] 虚拟机 {vm_uuid} "
                        f"状态 '{status_name}' 已保存"
                    )
                return success
            except Exception as e:
                logger.error(
                    f"[{self.hs_config.server_name}] 保存虚拟机状态失败: {e}"
                )
                return False
        return False

    # 保存数据到数据库 ##############################################################
    def data_set(self) -> bool:
        if self.save_data and self.hs_config.server_name:
            try:
                # 保存VM配置数据
                success = self.save_data.set_vm_saving(
                    self.hs_config.server_name, self.vm_saving)
                if success:
                    logger.debug(f"[{self.hs_config.server_name}] 虚拟机配置已保存")
                return success
            except Exception as e:
                logger.error(f"[{self.hs_config.server_name}] 保存数据失败: {e}")
                return False
        return False

    # 从数据库重新加载数据 ##########################################################
    def data_get(self) -> bool:
        if self.save_data and self.hs_config.server_name:
            try:
                # 从数据库获取虚拟机配置
                vm_saving_data = self.save_data.get_vm_saving(
                    self.hs_config.server_name
                )
                if vm_saving_data:
                    self.vm_saving = {}
                    for vm_uuid, vm_config in vm_saving_data.items():
                        if isinstance(vm_config, dict):
                            self.vm_saving[vm_uuid] = VMConfig(**vm_config)
                        else:
                            self.vm_saving[vm_uuid] = vm_config
                return True
            except Exception as e:
                logger.error(
                    f"[{self.hs_config.server_name}] "
                    f"从数据库加载数据失败: {e}"
                )
                return False
        return False

    # 判断是否为远程宿主机 ##########################################################
    def web_flag(self) -> bool:
        """判断是否为远程主机"""
        return self.hs_config.server_addr not in ["localhost", "127.0.0.1", ""]

    # ###############################################################################
    # 可重载方法 ####################################################################
    # ###############################################################################

    # 获取虚拟机配置 ################################################################
    def VMSelect(self, select: str) -> VMConfig | None:
        if select in self.vm_saving:
            return self.vm_saving[select]
        return None

    # 获取当前主机所有虚拟机已分配的IP地址 ##########################################
    def IPCollect(self) -> set:
        allocated = set()
        for vm_uuid, vm_config in self.vm_saving.items():
            for nic_name, nic_config in vm_config.nic_all.items():
                if nic_config.ip4_addr:
                    allocated.add(nic_config.ip4_addr.strip())
                if nic_config.ip6_addr:
                    allocated.add(nic_config.ip6_addr.strip())
        return allocated

    # 查找端口 ######################################################################
    def PortsGet(self, vm_uuid: str, vm_port: int) -> int:
        vm_conf = self.VMSelect(vm_uuid)
        if vm_conf is None:
            return 0
        try:
            all_port = vm_conf.nat_all
            for now_port in all_port:
                if now_port.lan_port == vm_port:
                    return now_port.wan_port
        except Exception as e:
            logger.warning(f"无法获取SSH端口: {vm_port}: {str(e)}")
            return 0
        return 0

    # 端口映射 ######################################################################
    def PortsMap(self, map_info: PortData, flag=True) -> ZMessage:
        try:
            logger.info(f"[{self.hs_config.server_name}] 开始端口映射操作: {map_info.wan_port} -> {map_info.lan_addr}:{map_info.lan_port}")
            nc_server = NetsManager(
                self.hs_config.i_kuai_addr,
                self.hs_config.i_kuai_user,
                self.hs_config.i_kuai_pass)
            nc_server.login()
        except ConnectionError as e:
            logger.error(f"[{self.hs_config.server_name}] 网络连接失败: {e}")
            return ZMessage(success=False, action="PortsMap", message=f"网络连接失败: {e}")
        except Exception as e:
            logger.error(f"[{self.hs_config.server_name}] 端口映射初始化失败: {e}")
            return ZMessage(success=False, action="PortsMap", message=str(e))
        # 提取端口列表 ==============================================================
        port_result = nc_server.get_port()
        wan_list = []
        # 检查端口是否被占用 ========================================================
        if port_result and isinstance(port_result, dict):
            now_list = port_result.get('Data', {})
            if isinstance(now_list, dict):
                now_list = now_list.get('data', [])
                if isinstance(now_list, list):
                    wan_list = [int(i.get("wan_port", 0)) \
                                for i in now_list if isinstance(i, dict)]
        # 检查端口范围是否正确 ======================================================
        if self.hs_config.ports_start == "" or self.hs_config.ports_close == "":
            return ZMessage(
                success=False, action="PortsMap", message="主机端口范围配置错误")
        num_port = int(self.hs_config.ports_close) - int(self.hs_config.ports_start)
        if num_port <= 0 or num_port <= len(wan_list):
            return ZMessage(
                success=False, action="PortsMap", message="主机端口可用数量不够")
        # 检查端口是否被占用 ========================================================
        if map_info.wan_port in wan_list:
            return ZMessage(
                success=False, action="PortsMap", message="端口已被占用")
        # 自动分配未使用的端口 ======================================================
        if map_info.wan_port == 0 or map_info.wan_port == "":
            # 随机分配一个端口
            map_info.wan_port = randint(
                self.hs_config.ports_start, self.hs_config.ports_close)
            # 如果被占用，继续随机分配
            while map_info.wan_port in wan_list:
                map_info.wan_port = randint(
                    self.hs_config.ports_start, self.hs_config.ports_close)
        # 添加端口映射 ==============================================================
        if flag:
            result = nc_server.add_port(map_info.wan_port, map_info.lan_port,
                                        map_info.lan_addr, map_info.nat_tips)
        # 删除端口映射 ==============================================================
        else:
            result = nc_server.del_port(map_info.lan_port, map_info.lan_addr)
        # 返回结果 ==================================================================
        action_text = "添加" if flag else "删除"
        status_text = "成功" if result else "失败"
        logger.info(f"[{self.hs_config.server_name}] 端口映射{action_text}{status_text}: {map_info.wan_port} -> {map_info.lan_addr}:{map_info.lan_port}")
        hs_result = ZMessage(
            success=result, action="ProxyMap",
            messages=str(map_info.wan_port) + "端口%s操作%s" % (action_text, status_text))
        self.data_set()
        self.logs_set(hs_result)
        return hs_result

    # 反向代理 ######################################################################
    def ProxyMap(self, pm_info: WebProxy, vm_uuid: str,
                 in_apis: HttpManager, in_flag=True) -> ZMessage:
        try:
            logger.info(f"[{self.hs_config.server_name}] 开始反向代理操作: {pm_info.web_addr} -> {pm_info.lan_addr}:{pm_info.lan_port}")
            # 检查虚拟机是否存在 ========================================================
            vm_config = self.vm_saving.get(vm_uuid)
            if not vm_config:
                logger.warning(f"[{self.hs_config.server_name}] 虚拟机不存在: {vm_uuid}")
                return ZMessage(success=False,
                                action="ProxyMap",
                                message="虚拟机不存在")
        except Exception as e:
            logger.error(f"[{self.hs_config.server_name}] 反向代理操作失败: {e}", exc_info=True)
            return ZMessage(success=False, action="ProxyMap", message=str(e))
        # 获取虚拟机端口 ============================================================
        if self.hs_config.server_addr.split(":")[0] not in \
                ["localhost", "127.0.0.1", ""]:
            pm_info.lan_port = self.PortsGet(vm_uuid, pm_info.lan_port)
            pm_info.lan_addr = self.hs_config.server_addr
            if pm_info.lan_port == 0 and in_flag:
                return ZMessage(
                    success=False, action="ProxyMap",
                    message="当主机为远程IP时，必须先添加NAT映射才能代理<br/>"
                            "当前映射的本地端口缺少NAT映射，请先添加映射")
        # 检查变量存在 ==============================================================
        if not hasattr(vm_config, 'web_all') or vm_config.web_all is None:
            vm_config.web_all = []
        # 添加代理 ==================================================================
        if in_flag:
            # 检查域名是否已存在 ----------------------------------------------------
            for proxy in vm_config.web_all:
                if proxy.web_addr == pm_info.web_addr:
                    return ZMessage(success=False, action="ProxyMap",
                                    message=f'域名 {pm_info.web_addr} 已存在')
            # 添加代理 --------------------------------------------------------------
            result = in_apis.create_web(
                (pm_info.lan_port, pm_info.lan_addr),
                pm_info.web_addr, pm_info.is_https)
            vm_config.web_all.append(pm_info) if result else None
        # 删除代理 =================================================================
        else:
            result = in_apis.remove_web(pm_info.web_addr)
            vm_config.web_all.remove(pm_info) if result else None
        # 保存到数据库 =============================================================
        self.data_set()
        hs_result = ZMessage(
            success=result, action="ProxyMap",
            messages=pm_info.web_addr + "%s操作%s" % (
                "添加" if in_flag else "删除",
                "成功" if result else "失败"))
        self.logs_set(hs_result)
        return hs_result

    # 网络检查 ######################################################################
    def NetCheck(self, vm_conf: VMConfig) -> tuple:
        try:
            logger.info(f"[{self.hs_config.server_name}] 开始网络配置检查: {vm_conf.vm_uuid}")
            ip_config = IPConfig(
                self.hs_config.ipaddr_maps,
                self.hs_config.ipaddr_dnss
            )
            allocated_ips = self.IPCollect()
            logger.debug(f"[{self.hs_config.server_name}] 已分配IP列表: {allocated_ips}")
            result = ip_config.check_and_allocate(vm_conf, allocated_ips)
            logger.info(f"[{self.hs_config.server_name}] 网络配置检查完成")
            return result
        except ValueError as e:
            logger.error(f"[{self.hs_config.server_name}] 网络配置参数错误: {e}")
            return vm_conf, ZMessage(success=False, action="NetCheck", message=f"配置参数错误: {e}")
        except Exception as e:
            logger.error(f"[{self.hs_config.server_name}] 网络检查失败: {e}", exc_info=True)
            return vm_conf, ZMessage(
                success=False,
                action="NetCheck",
                message=str(e)
            )

    # 网络静态绑定 ##################################################################
    def NetiKuai(self, ip, mac, uuid, flag=True, dns1=None, dns2=None) -> ZMessage:
        try:
            nc_server = NetsManager(
                self.hs_config.i_kuai_addr,
                self.hs_config.i_kuai_user,
                self.hs_config.i_kuai_pass
            )
            nc_server.login()
            if flag:
                nc_server.add_dhcp(
                    ip, mac, comment=uuid, lan_dns1=dns1, lan_dns2=dns2
                )
                nc_server.add_arps(ip, mac)
            else:
                nc_server.del_dhcp(ip)
                nc_server.del_arps(ip)
            return ZMessage(success=True, action="NCStatic")
        except Exception as e:
            logger.error(f"网络静态绑定失败: {e}")
            return ZMessage(
                success=False,
                action="NCStatic",
                message=str(e)
            )

    # ###############################################################################
    # 分支的方法 ####################################################################
    # ###############################################################################

    vnc_type = ["VMWareSetup", "vSphereESXi", "HyperVSetup", "PromoxSetup"]
    tty_type = ["OCInterface", "LxContainer"]

    # 远程桌面初始化[禁止重载] ######################################################
    def VMLoader(self) -> bool:
        if self.hs_config.server_type in BasicServer.vnc_type:
            return self.VMLoader_VNC()
        elif self.hs_config.server_type in BasicServer.tty_type:
            return self.VMLoader_TTY()
        return True

    # 远程桌面VNC连接初始化 =========================================================
    def VMLoader_VNC(self) -> bool:
        try:
            cfg_name = "vnc-" + self.hs_config.server_name
            cfg_full = "DataSaving/" + cfg_name + ".cfg"
            if os.path.exists(cfg_full):
                os.remove(cfg_full)
            tp_remote = WebsocketUI(self.hs_config.remote_port, cfg_name)
            self.vm_remote = VNCSManager(tp_remote)
            self.vm_remote.start()
            return True
        except Exception as e:
            logger.warning(f"VNC服务启动失败: {str(e)}")
            return False

    # 远程桌面TTY连接初始化 =========================================================
    def VMLoader_TTY(self) -> bool:
        if not self.web_terminal:
            self.web_terminal = SSHTerminal(self.hs_config)
        # 初始化HttpManager
        if not self.http_manager:
            hostname = getattr(self.hs_config, 'server_name', '')
            config_filename = f"vnc-{hostname}.txt"
            self.http_manager = HttpManager(config_filename)
            self.http_manager.launch_vnc(self.hs_config.remote_port)
            self.http_manager.launch_web()
        # 初始化端口转发管理器
        if not self.port_forward:
            self.port_forward = PortForward.PortForward(self.hs_config)
        return True

    # 网络动态绑定 ##################################################################
    def IPBinder(self, vm_conf: VMConfig, flag=True) -> ZMessage:
        if self.hs_config.server_type in BasicServer.vnc_type:
            return self.IPBinder_ROS(vm_conf, flag)
        elif self.hs_config.server_type in BasicServer.tty_type:
            return self.IPBinder_MAN(vm_conf, flag)
        return ZMessage(success=False, action="IPCreate")

    # 通过爱快绑定 ==================================================================
    def IPBinder_ROS(self, vm_conf: VMConfig, flag=True) -> ZMessage:
        # 创建网卡 ==================================================================
        # 遍历所有网络适配器->绑定静态IP ============================================
        all_success = True
        error_message = ""

        for nic_name, nic_conf in vm_conf.nic_all.items():
            try:
                logger.info(
                    f"[API] 绑定静态IP: {nic_conf.ip4_addr} -> {nic_conf.mac_addr}")
                nc_result = self.NetiKuai(
                    nic_conf.ip4_addr,
                    nic_conf.mac_addr,
                    vm_conf.vm_uuid,
                    flag=flag,
                    dns1=self.hs_config.ipaddr_dnss[0],
                    dns2=self.hs_config.ipaddr_dnss[1]
                )
                if nc_result.success:
                    logger.success(f"[API] 静态IP绑定成功: {nic_conf.ip4_addr}")
                else:
                    logger.warning(f"[API] 静态IP绑定失败: {nc_result.message}")
                    all_success = False
                    if not error_message:
                        error_message = nc_result.message
            except Exception as e:
                logger.error(f"[API] 静态IP绑定异常: {str(e)}")
                all_success = False
                if not error_message:
                    error_message = str(e)

        if all_success:
            return ZMessage(
                success=True,
                action="NCStatic",
                message="所有网卡IP绑定成功"
            )
        else:
            return ZMessage(
                success=False,
                action="NCStatic",
                message=f"部分网卡IP绑定失败: {error_message}"
            )

    # 手动实现绑定 ==================================================================
    def IPBinder_MAN(self, vm_conf: VMConfig, flag=True) -> ZMessage:
        return ZMessage(success=False, action="IPBinder_MAN", message="请补全实现")

    # 更新网卡 ######################################################################
    def IPUpdate(self, vm_conf: VMConfig, vm_last: VMConfig) -> ZMessage:
        if self.hs_config.server_type in BasicServer.ros_type:
            return self.IPUpdate_ROS(vm_conf, vm_last)
        elif self.hs_config.server_type in BasicServer.man_type:
            return self.IPUpdate_MAN(vm_conf, vm_last)
        return ZMessage(success=False, action="IPCreate")

    # 通过爱快绑定 ==================================================================
    def IPUpdate_ROS(self, vm_conf: VMConfig, vm_last: VMConfig) -> ZMessage:
        # 删除旧的网络绑定 ==========================================================
        if vm_last is not None:
            for nic_name in vm_last.nic_all:
                nic_data = vm_last.nic_all[nic_name]
                self.NetiKuai(
                    nic_data.ip4_addr, nic_data.mac_addr,
                    vm_last.vm_uuid, False)
        # 添加新的网络绑定 ==========================================================
        for nic_name in vm_conf.nic_all:
            nic_data = vm_conf.nic_all[nic_name]
            self.NetiKuai(
                nic_data.ip4_addr, nic_data.mac_addr,
                vm_conf.vm_uuid, True,
                nic_data.dns_addr[0] if len(nic_data.dns_addr) > 0 else "119.29.29.29",
                nic_data.dns_addr[1] if len(nic_data.dns_addr) > 1 else "223.5.5.5"
            )
        return ZMessage(success=True, action="VMUpdate")

    # 手动实现绑定 ==================================================================
    def IPUpdate_MAN(self, vm_conf: VMConfig, vm_last: VMConfig) -> ZMessage:
        return ZMessage(success=False, action="IPUpdate_MAN", message="请补全实现")

    # ###############################################################################
    # TTY容器专用方法（LXContainer、OCInterface）####################################
    # ###############################################################################

    # 同步端口转发配置（TTY容器专用）################################################
    def syn_port_TTY(self):
        try:
            # 判断是否为远程主机
            is_remote = self.web_flag()

            # 如果是远程主机，先建立SSH连接
            if is_remote:
                success, message = self.port_forward.connect_ssh()
                if not success:
                    logger.error(f"SSH连接失败，无法同步端口转发: {message}")
                    return

            # 获取系统中已有的端口转发
            existing_forwards = self.port_forward.list_ports(is_remote)
            existing_map = {}  # {(lan_addr, lan_port): forward_info}
            for forward in existing_forwards:
                key = (forward.lan_addr, forward.lan_port)
                existing_map[key] = forward

            # 获取配置中需要的端口转发
            required_forwards = {}  # {(lan_addr, lan_port): (wan_port, vm_name)}
            for vm_name, vm_conf in self.vm_saving.items():
                if not hasattr(vm_conf, 'nat_all'):
                    continue

                for port_data in vm_conf.nat_all:
                    key = (port_data.lan_addr, port_data.lan_port)
                    required_forwards[key] = (port_data.wan_port, vm_name)

            # 删除不需要的转发
            removed_count = 0
            for key, forward in existing_map.items():
                if key not in required_forwards:
                    # 这个转发不在配置中，删除它
                    if self.port_forward.remove_port_forward(
                            forward.wan_port, forward.protocol, is_remote
                    ):
                        removed_count += 1
                        logger.info(
                            f"删除多余的端口转发: {forward.protocol} "
                            f"{forward.wan_port} -> "
                            f"{forward.lan_addr}:{forward.lan_port}"
                        )

            # 添加缺少的转发
            added_count = 0
            for key, (wan_port, vm_name) in required_forwards.items():
                lan_addr, lan_port = key

                # 检查是否已存在
                if key in existing_map:
                    existing_forward = existing_map[key]
                    # 如果wan_port不同，需要先删除旧的再添加新的
                    if existing_forward.wan_port != wan_port:
                        self.port_forward.remove_port_forward(
                            existing_forward.wan_port,
                            existing_forward.protocol,
                            is_remote
                        )
                        logger.info(
                            f"端口映射变更，删除旧转发: "
                            f"{existing_forward.protocol} "
                            f"{existing_forward.wan_port} -> "
                            f"{lan_addr}:{lan_port}"
                        )
                    else:
                        # 端口转发已存在且配置正确，跳过
                        continue

                # 添加新的端口转发
                success, error = self.port_forward.add_port_forward(
                    lan_addr, lan_port, wan_port, "TCP", is_remote, vm_name
                )

                if success:
                    added_count += 1
                    logger.info(
                        f"添加端口转发: TCP {wan_port} -> "
                        f"{lan_addr}:{lan_port} ({vm_name})"
                    )
                else:
                    logger.error(
                        f"添加端口转发失败: TCP {wan_port} -> "
                        f"{lan_addr}:{lan_port}, 错误: {error}"
                    )

            logger.info(
                f"端口转发同步完成: 删除 {removed_count} 个，"
                f"添加 {added_count} 个"
            )

            # 关闭SSH连接
            if is_remote:
                self.port_forward.close_ssh()
        except Exception as e:
            logger.error(f"同步端口转发时出错: {str(e)}")
            import traceback
            traceback.print_exc()

    # 更新网络配置（TTY容器专用）####################################################
    def IPUpdate_TTY(self, vm_conf: VMConfig, vm_last: VMConfig) -> ZMessage:
        """更新网络配置（TTY容器专用）"""
        self.IPBinder(vm_last, False)
        self.IPBinder(vm_conf, True)
        return ZMessage(success=True, action="VMUpdate")

    # 端口映射管理（TTY容器专用）####################################################
    def PortsMap_TTY(self, map_info: PortData, flag=True) -> ZMessage:
        """端口映射管理（TTY容器专用）"""
        # 判断是否为远程主机（排除 SSH 转发模式）
        is_remote = (self.hs_config.server_addr not in ["localhost", "127.0.0.1", ""] and
                     not self.hs_config.server_addr.startswith("ssh://"))

        # 如果是远程主机，先建立SSH连接
        if is_remote:
            success, message = self.port_forward.connect_ssh()
            if not success:
                return ZMessage(
                    success=False, action="PortsMap",
                    message=f"SSH 连接失败: {message}")

        # 如果wan_port为0，自动分配一个未使用的端口
        if map_info.wan_port == 0:
            map_info.wan_port = self.port_forward.allocate_port(is_remote)
        else:
            # 检查端口是否已被占用
            existing_ports = self.port_forward.get_host_ports(is_remote)
            if map_info.wan_port in existing_ports:
                if is_remote:
                    self.port_forward.close_ssh()
                return ZMessage(
                    success=False, action="PortsMap",
                    message=f"端口 {map_info.wan_port} 已被占用")

        # 执行端口映射操作
        if flag:
            success, error = self.port_forward.add_port_forward(
                map_info.lan_addr, map_info.lan_port, map_info.wan_port,
                "TCP", is_remote, map_info.nat_tips)

            if success:
                hs_message = f"端口 {map_info.wan_port} 成功映射到 {map_info.lan_addr}:{map_info.lan_port}"
                hs_success = True
            else:
                if is_remote:
                    self.port_forward.close_ssh()
                return ZMessage(
                    success=False, action="PortsMap",
                    message=f"端口映射失败: {error}")
        else:
            self.port_forward.remove_port_forward(
                map_info.wan_port, "TCP", is_remote)
            hs_message = f"端口 {map_info.wan_port} 映射已删除"
            hs_success = True

        hs_result = ZMessage(
            success=hs_success, action="PortsMap",
            message=hs_message)
        self.logs_set(hs_result)

        # 关闭 SSH 连接
        if is_remote:
            self.port_forward.close_ssh()

        return hs_result

    # 删除备份文件（TTY容器专用）####################################################
    def RMBackup_TTY(self, vm_name: str, vm_back: str = "") -> ZMessage:
        """删除备份文件（TTY容器专用）"""
        # 删除虚拟机备份文件
        del_files = []
        if os.path.exists(self.hs_config.backup_path):
            try:
                # 扫描备份目录
                for bk_file in os.listdir(self.hs_config.backup_path):
                    # 检查文件名是否以虚拟机名开头
                    if bk_file.startswith(f"{vm_name}_") and \
                            (bk_file == vm_back or vm_back == ""):
                        bk_path = os.path.join(
                            self.hs_config.backup_path, bk_file)
                        os.remove(bk_path)
                        del_files.append(bk_file)
                        logger.info(f"删除备份: {bk_file}")
            except Exception as e:
                logger.warning(f"扫描备份目录失败: {str(e)}")

        # 记录删除的备份文件
        logger.info(f"共删除 {len(del_files)} 个备份文件")
        return ZMessage(success=True,
                        message=f"已删除 {len(del_files)} 个备份文件")

    # 删除挂载目录（TTY容器专用）####################################################
    def RMMounts_TTY(self, vm_name: str, vm_imgs: str = "") -> ZMessage:
        """删除挂载目录（TTY容器专用）"""
        if vm_imgs != "":
            return ZMessage(
                success=True, action="RMMounts",
                message="指定磁盘已删除")

        # 删除容器挂载路径
        if not self.hs_config.extern_path:
            pass  # 没有配置挂载路径，跳过
        else:
            ct_path = f"{self.hs_config.extern_path}/{vm_name}"
            try:
                if os.path.exists(ct_path):
                    import shutil
                    shutil.rmtree(ct_path)
                    logger.info(f"删除挂载路径: {ct_path}")
            except Exception as e:
                logger.warning(f"删除挂载失败 {ct_path}: {str(e)}")

        # 返回结果
        return ZMessage(success=True, action="RMMounts", message="删除成功")

    # ###############################################################################
    # 需实现方法 ####################################################################
    # ###############################################################################

    # 执行定时任务 ##################################################################
    def Crontabs(self) -> bool:
        hs_status = HSStatus()
        self.host_set(hs_status)
        return True

    # 宿主机状态 ####################################################################
    def HSStatus(self) -> HWStatus:
        status_list = self.host_get()
        if len(status_list) > 0:
            # 将 dict 重新构造成 HWStatus 对象
            raw = status_list[-1]
            hw = HWStatus()
            # 如果 raw 是字典，则遍历设置属性
            if isinstance(raw, dict):
                for k, v in raw.items():
                    setattr(hw, k, v)
            # 如果 raw 已经是 HWStatus 对象，直接返回
            elif isinstance(raw, HWStatus):
                return raw
            return hw
        # 如果没有记录，返回空状态
        return HWStatus()

    # 初始宿主机 ####################################################################
    def HSCreate(self) -> ZMessage:
        hs_result = ZMessage(success=True, action="HSCreate")
        self.logs_set(hs_result)
        return hs_result

    # 还原宿主机 ####################################################################
    def HSDelete(self) -> ZMessage:
        hs_result = ZMessage(success=True, action="HSDelete")
        self.logs_set(hs_result)
        return hs_result

    # 读取宿主机 ####################################################################
    def HSLoader(self) -> ZMessage:
        self.VMLoader()
        hs_result = ZMessage(
            success=True,
            action="HSLoader",
            message="宿主机加载成功")
        self.logs_set(hs_result)
        return hs_result

    # 卸载宿主机 ####################################################################
    def HSUnload(self) -> ZMessage:
        hs_result = ZMessage(
            success=True,
            action="HSUnload",
            message="VM Rest服务器已停止",
        )
        self.logs_set(hs_result)
        return hs_result

    # 虚拟机扫描 ####################################################################
    def VMDetect(self) -> ZMessage:
        pass

    # 创建虚拟机 ####################################################################
    def VMCreate(self, vm_conf: VMConfig) -> ZMessage:
        try:
            logger.info(f"[{self.hs_config.server_name}] 开始创建虚拟机: {vm_conf.vm_uuid}")
            logger.info(f"  - 虚拟机名称: {vm_conf.vm_name}")
            logger.info(f"  - CPU核心数: {vm_conf.cpu_num}")
            logger.info(f"  - 内存大小: {vm_conf.mem_num}MB")
            logger.info(f"  - 网卡数量: {len(vm_conf.nic_all)}")
            logger.info(f"  - 系统镜像: {vm_conf.os_name}")
            
            # 只有在所有操作都成功后才保存配置到vm_saving
            self.vm_saving[vm_conf.vm_uuid] = vm_conf
            # 保存到数据库 =====================================================
            self.data_set()
            # 返回结果 =========================================================
            logger.success(f"[{self.hs_config.server_name}] 虚拟机创建成功: {vm_conf.vm_uuid}")
            hs_result = ZMessage(
                success=True, action="VMCreate", message="虚拟机创建成功")
            self.logs_set(hs_result)
            return hs_result
        except Exception as e:
            logger.error(f"[{self.hs_config.server_name}] 虚拟机创建失败: {e}", exc_info=True)
            return ZMessage(success=False, action="VMCreate", message=str(e))

    # 配置虚拟机 ####################################################################
    def VMUpdate(self, vm_conf: VMConfig, vm_last: VMConfig) -> ZMessage:
        # 保存到数据库 =========================================================
        self.data_set()
        
        # 保存虚拟机状态
        self.vm_status_set(vm_conf.vm_uuid, "修改配置")
        
        # 记录日志 =============================================================
        hs_result = ZMessage(
            success=True, action="VMUpdate",
            message=f"虚拟机 {vm_conf.vm_uuid} 配置已更新")
        self.logs_set(hs_result)
        return hs_result

    # 虚拟机状态 ####################################################################
    def VMStatus(self, vm_name: str = "",
                 s_t: int = None, e_t: int = None) -> dict[str, list[HWStatus]]:
        if self.save_data and self.hs_config.server_name:
            all_status = self.save_data.get_vm_status(
                self.hs_config.server_name, start_timestamp=s_t,
                end_timestamp=e_t)
            
            # 如果指定了vm_name，检查是否需要从API获取实际状态
            if vm_name:
                vm_status_list = all_status.get(vm_name, [])
                
                # 如果没有状态记录或最新状态为未知，尝试从API获取实际状态
                if not vm_status_list or (vm_status_list and 
                    hasattr(vm_status_list[-1], 'vm_status') and 
                    vm_status_list[-1].vm_status in ['未知', 'unknown', '', None]):
                    try:
                        # 调用子类实现的获取实际状态方法
                        actual_status = self.VMStatusAPI(vm_name)
                        if actual_status:
                            logger.info(f"从API获取虚拟机 {vm_name} 实际状态: {actual_status}")
                            # 如果获取到实际状态，返回包含实际状态的列表
                            if vm_status_list:
                                vm_status_list[-1].vm_status = actual_status
                            else:
                                # 创建新的状态记录
                                new_status = HWStatus()
                                new_status.vm_status = actual_status
                                new_status.timestamp = datetime.datetime.now().timestamp()
                                vm_status_list = [new_status]
                    except Exception as e:
                        logger.warning(f"从API获取虚拟机状态失败: {str(e)}")
                
                return {vm_name: vm_status_list}
            
            # 如果没有指定vm_name，对所有虚拟机检查状态
            for vm_uuid in self.vm_saving.keys():
                vm_status_list = all_status.get(vm_uuid, [])
                
                # 如果没有状态记录或最新状态为未知，尝试从API获取实际状态
                if not vm_status_list or (vm_status_list and 
                    hasattr(vm_status_list[-1], 'vm_status') and 
                    vm_status_list[-1].vm_status in ['未知', 'unknown', '', None]):
                    try:
                        actual_status = self.VMStatusAPI(vm_uuid)
                        if actual_status:
                            logger.info(f"从API获取虚拟机 {vm_uuid} 实际状态: {actual_status}")
                            if vm_status_list:
                                vm_status_list[-1].vm_status = actual_status
                            else:
                                new_status = HWStatus()
                                new_status.vm_status = actual_status
                                new_status.timestamp = datetime.datetime.now().timestamp()
                                vm_status_list = [new_status]
                            all_status[vm_uuid] = vm_status_list
                    except Exception as e:
                        logger.warning(f"从API获取虚拟机 {vm_uuid} 状态失败: {str(e)}")
            
            return all_status
        return {}

    # 虚拟机截图 ####################################################################
    def VMScreen(self, vm_name: str = "") -> str:
        return ""

    # 获取虚拟机实际状态（从API）####################################################
    def VMStatusAPI(self, vm_name: str) -> str:
        """
        从虚拟化平台API获取虚拟机实际状态
        子类需要实现此方法以返回虚拟机的实际运行状态
        返回值示例: "运行中", "已关机", "暂停", "未知" 等
        """
        return ""

    # 删除虚拟机 ####################################################################
    def VMDelete(self, vm_name: str, rm_back=True) -> ZMessage:
        try:
            logger.info(f"[{self.hs_config.server_name}] 开始删除虚拟机: {vm_name}")
            vm_saving = os.path.join(self.hs_config.system_path, vm_name)
            # 删除虚拟文件 ==============================================================
            if os.path.exists(vm_saving):
                logger.info(f"[{self.hs_config.server_name}] 删除虚拟机文件: {vm_saving}")
                shutil.rmtree(vm_saving)
            # 删除存储信息 ==============================================================
            if vm_name in self.vm_saving:
                logger.info(f"[{self.hs_config.server_name}] 从配置中移除虚拟机: {vm_name}")
                del self.vm_saving[vm_name]
            # 保存到数据库 ==============================================================
            self.data_set()
            logger.success(f"[{self.hs_config.server_name}] 虚拟机删除成功: {vm_name}")
            hs_result = ZMessage(success=True, action="VMDelete", message=f"虚拟机 {vm_name} 已删除")
            self.logs_set(hs_result)
            return hs_result
        except PermissionError as e:
            logger.error(f"[{self.hs_config.server_name}] 删除虚拟机权限不足: {e}")
            return ZMessage(success=False, action="VMDelete", message=f"权限不足: {e}")
        except Exception as e:
            logger.error(f"[{self.hs_config.server_name}] 删除虚拟机失败: {e}", exc_info=True)
            return ZMessage(success=False, action="VMDelete", message=str(e))

    # 虚拟机电源 ####################################################################
    def VMPowers(self, vm_name: str, p: VMPowers) -> ZMessage:
        # 映射电源操作到状态名称
        power_status_map = {
            VMPowers.S_START: "启动",
            VMPowers.S_CLOSE: "关机",
            VMPowers.H_CLOSE: "强制关机",
            VMPowers.H_RESET: "强制重启",
            VMPowers.A_PAUSE: "暂停",
            VMPowers.A_WAKED: "恢复"
        }
        
        # 保存虚拟机状态
        status_name = power_status_map.get(p, "未知操作")
        logger.info(f"[{self.hs_config.server_name}] 虚拟机电源操作: {vm_name} - {status_name}")
        self.vm_status_set(vm_name, status_name)
        
        return ZMessage(
            success=False, action="VMPowers",
            message="操作成功完成")

    # 安装虚拟机 ####################################################################
    def VMSetups(self, vm_conf: VMConfig) -> ZMessage:
        # 保存虚拟机状态
        self.vm_status_set(vm_conf.vm_uuid, "重装")
        pass

    # 设置虚拟机密码 ################################################################
    def VMPasswd(self, vm_name: str, os_pass: str) -> ZMessage:
        vm_config = self.VMSelect(vm_name)
        if vm_config is None:
            return ZMessage(
                success=False, action="Password",
                message="虚拟机不存在")
        # 使用__save__()方法创建新配置，避免copy.deepcopy的问题
        ap_config_dict = vm_config.__save__()
        ap_config = VMConfig(**ap_config_dict)
        ap_config.os_pass = os_pass
        
        # 保存虚拟机状态
        self.vm_status_set(vm_name, "改密")
        
        return self.VMUpdate(ap_config, vm_config)

    # 备份虚拟机 ####################################################################
    def VMBackup(self, vm_name: str, vm_tips: str) -> ZMessage:
        bak_time = datetime.datetime.now()
        bak_name = vm_name + "-" + bak_time.strftime("%Y%m%d%H%M%S") + ".7z"
        org_path = os.path.join(self.hs_config.system_path, vm_name)
        zip_path = os.path.join(self.hs_config.backup_path, bak_name)
        try:
            logger.info(f"[{self.hs_config.server_name}] 开始备份虚拟机: {vm_name}")
            logger.info(f"  - 备份文件: {bak_name}")
            logger.info(f"  - 备份说明: {vm_tips}")
            self.VMPowers(vm_name, VMPowers.H_CLOSE)

            # 获取7z可执行文件路径
            seven_zip = self.path_zip()
            if not os.path.exists(seven_zip):
                raise FileNotFoundError(f"7z可执行文件不存在: {seven_zip}")

            # 使用subprocess调用7z进行压缩
            # 命令格式: 7z a -t7z <压缩包路径> <源目录>
            cmd = [seven_zip, "a", "-t7z", zip_path, org_path]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                raise Exception(f"7z压缩失败: {result.stderr}")

            self.VMPowers(vm_name, VMPowers.S_START)
            self.vm_saving[vm_name].backups.append(
                VMBackup(
                    backup_name=bak_name,
                    backup_time=bak_time,
                    backup_tips=vm_tips
                )
            )
            self.data_set()
            logger.success(f"[{self.hs_config.server_name}] 虚拟机备份成功: {bak_name}")
            return ZMessage(success=True, action="VMBackup", message=f"备份成功: {bak_name}")
        except FileNotFoundError as e:
            logger.error(f"[{self.hs_config.server_name}] 备份文件未找到: {e}")
            self.VMPowers(vm_name, VMPowers.S_START)
            return ZMessage(success=False, action="VMBackup", message=f"文件未找到: {e}")
        except Exception as e:
            logger.error(f"[{self.hs_config.server_name}] 虚拟机备份失败: {e}", exc_info=True)
            self.VMPowers(vm_name, VMPowers.S_START)
            return ZMessage(success=False, action="VMBackup", message=str(e))

    # 恢复虚拟机 ####################################################################
    def Restores(self, vm_name: str, vm_back: str) -> ZMessage:
        org_path = os.path.join(self.hs_config.system_path, vm_name)
        zip_path = os.path.join(self.hs_config.backup_path, vm_back)
        try:
            logger.info(f"[{self.hs_config.server_name}] 开始恢复虚拟机: {vm_name}")
            logger.info(f"  - 备份文件: {vm_back}")
            self.VMPowers(vm_name, VMPowers.H_CLOSE)
            shutil.rmtree(org_path)
            os.makedirs(org_path)

            # 获取7z可执行文件路径
            seven_zip = self.path_zip()
            if not os.path.exists(seven_zip):
                raise FileNotFoundError(f"7z可执行文件不存在: {seven_zip}")

            # 使用subprocess调用7z进行解压
            # 命令格式: 7z x <压缩包路径> -o<输出目录> -y
            cmd = [seven_zip, "x", zip_path, f"-o{self.hs_config.system_path}", "-y"]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                raise Exception(f"7z解压失败: {result.stderr}")

            self.VMPowers(vm_name, VMPowers.S_START)
            logger.success(f"[{self.hs_config.server_name}] 虚拟机恢复成功: {vm_name}")
            return ZMessage(success=True, action="Restores", message=f"恢复成功: {vm_name}")
        except FileNotFoundError as e:
            logger.error(f"[{self.hs_config.server_name}] 恢复文件未找到: {e}")
            self.VMPowers(vm_name, VMPowers.S_START)
            return ZMessage(success=False, action="Restores", message=f"文件未找到: {e}")
        except Exception as e:
            logger.error(f"[{self.hs_config.server_name}] 虚拟机恢复失败: {e}", exc_info=True)
            self.VMPowers(vm_name, VMPowers.S_START)
            return ZMessage(success=False, action="Restores", message=str(e))

    # VM镜像挂载 ####################################################################
    def HDDMount(self, vm_name: str, vm_imgs: SDConfig, in_flag=True) -> ZMessage:
        if vm_name not in self.vm_saving:
            return ZMessage(
                success=False, action="HDDMount", message="虚拟机不存在")
        old_conf = deepcopy(self.vm_saving[vm_name])
        # 关闭虚拟机 ===============================================================
        self.VMPowers(vm_name, VMPowers.H_CLOSE)
        if in_flag:  # 挂载磁盘 ====================================================
            vm_imgs.hdd_flag = 1
            self.vm_saving[vm_name].hdd_all[vm_imgs.hdd_name] = vm_imgs
        else:  # 卸载磁盘 ==========================================================
            if vm_imgs.hdd_name not in self.vm_saving[vm_name].hdd_all:
                self.VMPowers(vm_name, VMPowers.S_START)
                return ZMessage(
                    success=False, action="HDDMount", message="磁盘不存在")
            self.vm_saving[vm_name].hdd_all[vm_imgs.hdd_name].hdd_flag = 0
        # 保存配置 =================================================================
        self.VMUpdate(self.vm_saving[vm_name], old_conf)
        self.data_set()
        action_text = "挂载" if in_flag else "卸载"
        return ZMessage(
            success=True,
            action="HDDMount",
            message=f"磁盘{action_text}成功")

    # ISO镜像挂载 ###################################################################
    def ISOMount(self, vm_name: str, vm_imgs: IMConfig, in_flag=True) -> ZMessage:
        if vm_name not in self.vm_saving:
            return ZMessage(
                success=False, action="ISOMount", message="虚拟机不存在")

        old_conf = deepcopy(self.vm_saving[vm_name])
        # 关闭虚拟机
        logger.info(f"[{self.hs_config.server_name}] 准备{'挂载' if in_flag else '卸载'}ISO: {vm_imgs.iso_name}")
        self.VMPowers(vm_name, VMPowers.H_CLOSE)

        if in_flag:  # 挂载ISO =================================================
            # 使用iso_file作为文件名检查
            iso_full = os.path.join(self.hs_config.dvdrom_path, vm_imgs.iso_file)  # 使用dvdrom_path存储光盘镜像
            if not os.path.exists(iso_full):
                self.VMPowers(vm_name, VMPowers.S_START)
                logger.error(f"[{self.hs_config.server_name}] ISO文件不存在: {iso_full}")
                return ZMessage(
                    success=False, action="ISOMount", message="ISO镜像文件不存在")

            # 检查挂载名称是否已存在
            if vm_imgs.iso_name in self.vm_saving[vm_name].iso_all:
                self.VMPowers(vm_name, VMPowers.S_START)
                return ZMessage(
                    success=False, action="ISOMount", message="挂载名称已存在")

            # 使用iso_name作为key存储
            self.vm_saving[vm_name].iso_all[vm_imgs.iso_name] = vm_imgs
            logger.info(f"[{self.hs_config.server_name}] ISO挂载成功: {vm_imgs.iso_name} -> {vm_imgs.iso_file}")
        else:
            # 卸载ISO ==========================================================
            if vm_imgs.iso_name not in self.vm_saving[vm_name].iso_all:
                self.VMPowers(vm_name, VMPowers.S_START)
                return ZMessage(
                    success=False, action="ISOMount", message="ISO镜像不存在")

            # 从字典中移除
            del self.vm_saving[vm_name].iso_all[vm_imgs.iso_name]
            logger.info(f"[{self.hs_config.server_name}] ISO卸载成功: {vm_imgs.iso_name}")

        # 保存配置 =============================================================
        self.VMUpdate(self.vm_saving[vm_name], old_conf)
        self.data_set()

        # 启动虚拟机
        self.VMPowers(vm_name, VMPowers.S_START)

        action_text = "挂载" if in_flag else "卸载"
        return ZMessage(
            success=True,
            action="ISOMount",
            message=f"ISO镜像{action_text}成功")

    # 磁盘移交检查 ##################################################################
    def HDDCheck(self, vm_name: str, vm_imgs: SDConfig, ex_name: str) -> ZMessage:
        # 原始设备是否存在===========================================================
        if vm_name not in self.vm_saving:
            return ZMessage(
                success=False, action="HDDTrans", message="原始虚拟机不存在")
        # 目标设备是否存在===========================================================
        if ex_name not in self.vm_saving:
            return ZMessage(
                success=False, action="HDDTrans", message="目标虚拟机不存在")
        # 检查磁盘是否存在 ==========================================================
        if vm_imgs.hdd_name not in self.vm_saving[vm_name].hdd_all:
            return ZMessage(
                success=False, action="HDDTrans", message="待移交磁盘不存在")
        # 检查磁盘挂载状态 ==========================================================
        hdd_conf = self.vm_saving[vm_name].hdd_all[vm_imgs.hdd_name]
        if getattr(hdd_conf, 'hdd_flag', 0) == 1:
            return ZMessage(
                success=False, action="HDDTrans", message="请在先卸载此磁盘")
        return ZMessage(success=True, action="HDDTrans", message="磁盘可以移交")

    # 移交所有权 ####################################################################
    def HDDTrans(self, vm_name: str, vm_imgs: SDConfig, ex_name: str) -> ZMessage:
        # 检查情况 ==================================================================
        check_result = self.HDDCheck(vm_name, vm_imgs, ex_name)
        if not check_result.success:
            return check_result
        # 执行操作 ==================================================================
        old_path = os.path.join(self.hs_config.system_path, vm_name)
        new_path = os.path.join(self.hs_config.system_path, ex_name)
        old_file = os.path.join(old_path, vm_name + "-" + vm_imgs.hdd_name + ".vmdk")
        new_file = os.path.join(new_path, ex_name + "-" + vm_imgs.hdd_name + ".vmdk")
        try:
            # 从源虚拟机移除磁盘配置
            self.vm_saving[vm_name].hdd_all.pop(vm_imgs.hdd_name)
            # 移动物理文件
            if os.path.exists(old_file):
                shutil.move(old_file, new_file)
                logger.info(f"[{self.hs_config.server_name}] 磁盘文件"
                            f"已从 {old_file} 移动到 {new_file}")
            else:
                logger.warning(f"[{self.hs_config.server_name}] "
                               f"源磁盘文件 {old_file} 不存在")
            # 添加到目标虚拟机（保持未挂载状态）
            vm_imgs.hdd_flag = 0
            self.vm_saving[ex_name].hdd_all[vm_imgs.hdd_name] = vm_imgs
            # 保存配置
            self.data_set()
            logger.info(
                f"[{self.hs_config.server_name}] 磁盘 {vm_imgs.hdd_name} "
                f"已从虚拟机 {vm_name} 移交到 {ex_name}")
            return ZMessage(success=True, action="HDDTrans", message="磁盘移交成功")
        except Exception as e:
            logger.error(f"[{self.hs_config.server_name}] 磁盘移交失败: {str(e)}")
            return ZMessage(success=False, action="HDDTrans", message=str(e))

    # 移除备份 ######################################################################
    def RMBackup(self, vm_name: str, vm_back: str) -> ZMessage:
        bak_path = os.path.join(self.hs_config.backup_path, vm_back)
        if not os.path.exists(bak_path):
            return ZMessage(
                success=False, action="RMBackup",
                message="备份文件不存在")
        os.remove(bak_path)
        return ZMessage(
            success=True, action="RMBackup",
            message="备份文件已删除")

    # 加载备份 ######################################################################
    def LDBackup(self, vm_back: str = "") -> ZMessage:
        for vm_name in self.vm_saving:
            self.vm_saving[vm_name].backups = []
        bal_nums = 0
        for bak_name in os.listdir(self.hs_config.backup_path):
            # 只处理.7z备份文件
            if not bak_name.endswith(".7z"):
                continue
            bal_nums += 1
            # 去掉.7z后缀再解析
            name_without_ext = bak_name[:-3]  # 移除.7z
            parts = name_without_ext.split("-")
            if len(parts) < 2:
                logger.warning(f"备份文件名格式不正确: {bak_name}")
                continue
            vm_name = parts[0]
            vm_time = parts[1]
            if vm_name in self.vm_saving:
                try:
                    self.vm_saving[vm_name].backups.append(
                        VMBackup(
                            backup_name=bak_name,
                            backup_time=datetime.datetime.strptime(
                                vm_time, "%Y%m%d%H%M%S")
                        )
                    )
                except ValueError as e:
                    logger.error(f"解析备份时间失败 {bak_name}: {e}")
                    continue
        self.data_set()
        return ZMessage(
            success=True,
            action="LDBackup",
            message=f"{bal_nums}个备份文件已加载")

    # 移除磁盘 ######################################################################
    def RMMounts(self, vm_name: str, vm_imgs: str) -> ZMessage:
        if vm_name not in self.vm_saving:
            return ZMessage(
                success=False, action="RMMounts", message="虚拟机不存在")
        if vm_imgs not in self.vm_saving[vm_name].hdd_all:
            return ZMessage(
                success=False, action="RMMounts", message="虚拟盘不存在")
        # 获取虚拟磁盘数据 ===============================================
        hd_data = self.vm_saving[vm_name].hdd_all[vm_imgs]
        hd_path = os.path.join(
            self.hs_config.system_path, vm_name,
            vm_name + "-" + hd_data.hdd_name + ".vmdk")
        # 卸载虚拟磁盘 ===================================================
        if hd_data.hdd_flag == 1:
            self.HDDMount(vm_name, hd_data, False)
        # 从配置中移除 ===================================================
        self.vm_saving[vm_name].hdd_all.pop(vm_imgs)
        self.data_set()
        # 删除物理文件 ===================================================
        if os.path.exists(hd_path):
            os.remove(hd_path)
        # 返回结果 =======================================================
        return ZMessage(
            success=True, action="RMMounts",
            message="磁盘删除成功")

    # 查找显卡 ######################################################################
    def GPUShows(self) -> dict[str, str]:
        return {}

    # 转移用户 ######################################################################
    def Transfer(self, vm_name: str, new_owner: str,
                 keep_access: bool = False) -> ZMessage:
        # 检查虚拟机是否存在
        if vm_name not in self.vm_saving:
            return ZMessage(
                success=False,
                action="Transfer",
                message="虚拟机不存在"
            )

        vm_config = self.vm_saving[vm_name]
        owners = vm_config.own_all.copy()

        # 检查新所有者是否已经在所有者列表中
        if new_owner == owners[0]:
            return ZMessage(
                success=False,
                action="Transfer",
                message="用户已经是虚拟机所有者"
            )

        # 获取当前主所有者
        current_primary_owner = owners[0]

        # 移交所有权：将新所有者移到第一位
        owners.remove(new_owner) if new_owner in owners else None
        owners.insert(0, new_owner)

        # 如果不保留原所有者权限，从列表中移除原主所有者
        if not keep_access and current_primary_owner in owners:
            owners.remove(current_primary_owner)

        # 更新所有者列表
        vm_config.own_all = owners

        # 保存配置
        self.data_set()

        logger.info(
            f"[{self.hs_config.server_name}] 虚拟机 {vm_name} 所有权从 {current_primary_owner} 移交给 {new_owner}，保留权限: {keep_access}")

        return ZMessage(
            success=True,
            action="Transfer",
            message=f"虚拟机所有权已成功移交给 {new_owner}"
        )

    # 虚拟机控制台 ##################################################################
    def VMRemote(self, vm_uuid: str, ip_addr: str = "127.0.0.1") -> ZMessage:
        try:
            if vm_uuid not in self.vm_saving:
                return ZMessage(
                    success=False,
                    action="VCRemote",
                    message="虚拟机不存在"
                )
            # 检查VNC端口和密码 =====================================================
            if self.vm_saving[vm_uuid].vc_port == "":
                logger.warning(
                    f"[VCRemote] {vm_uuid} 的 vc_port 为空"
                )
                return ZMessage(
                    success=False,
                    action="VCRemote",
                    message="VNC端口为空"
                )
            if self.vm_saving[vm_uuid].vc_pass == "":
                logger.warning(
                    f"[VCRemote] {vm_uuid} 的 vc_pass 为空"
                )
                return ZMessage(
                    success=False,
                    action="VCRemote",
                    message="VNC密码为空"
                )
            return ZMessage(success=True)
        except Exception as e:
            logger.error(f"虚拟机控制台访问失败: {e}")
            traceback.print_exc()
            return ZMessage(
                success=False,
                action="VCRemote",
                message=str(e)
            )
