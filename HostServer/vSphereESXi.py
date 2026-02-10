# vSphereESXi - VMware ESXi虚拟化平台管理 ########################################
# 提供ESXi虚拟机的创建、管理和监控功能
################################################################################
import datetime
from loguru import logger
from HostServer.BasicServer import BasicServer
from HostServer.vSphereESXiAPI.vSphereAPI import vSphereAPI
from HostModule.HttpManager import HttpManager
from MainObject.Config.HSConfig import HSConfig
from MainObject.Config.IMConfig import IMConfig
from MainObject.Config.SDConfig import SDConfig
from MainObject.Config.VMPowers import VMPowers
from MainObject.Public.HWStatus import HWStatus
from MainObject.Public.ZMessage import ZMessage
from MainObject.Config.VMConfig import VMConfig
from MainObject.Config.VMBackup import VMBackup


class HostServer(BasicServer):
    # 宿主机服务 ###############################################################
    def __init__(self, config: HSConfig, **kwargs):
        super().__init__(config, **kwargs)
        super().__load__(**kwargs)
        # 添加变量 =============================================================
        # 解析system_path获取数据存储名称
        # system_path格式: datastore1/system
        datastore_name = "datastore1"  # 默认值
        if self.hs_config.system_path and '/' in self.hs_config.system_path:
            datastore_name = self.hs_config.system_path.split('/')[0]
        elif self.hs_config.system_path:
            datastore_name = self.hs_config.system_path

        # 初始化vSphere API连接
        self.esxi_api = vSphereAPI(
            host=self.hs_config.server_addr,
            user=self.hs_config.server_user,
            password=self.hs_config.server_pass,
            port=self.hs_config.server_port if hasattr(self.hs_config, 'server_port') else 443,
            datastore_name=datastore_name
        )

    # 辅助方法 - 获取虚拟机存储目录 =============================================
    def _get_vm_directory(self) -> str:
        """
        从system_path获取虚拟机存储目录
        例如: "datastore1/system" -> "system"
        """
        if self.hs_config.system_path and '/' in self.hs_config.system_path:
            return self.hs_config.system_path.split('/', 1)[1]
        return ""  # 空字符串表示数据存储根目录

    # 辅助方法 - 连接ESXi并执行操作 ============================================
    def _execute_with_connection(self, operation_name: str, operation_func):
        """
        统一的连接管理模式：连接ESXi、执行操作、断开连接、处理异常
        
        :param operation_name: 操作名称（用于日志和错误消息）
        :param operation_func: 操作函数，接收self作为参数
        :return: ZMessage结果
        """
        try:
            # 连接ESXi =========================================================
            connect_result = self.esxi_api.connect()
            if not connect_result.success:
                return connect_result
            
            # 执行操作 =========================================================
            result = operation_func()
            
            # 断开连接 =========================================================
            self.esxi_api.disconnect()
            
            return result
            
        except Exception as e:
            # 异常处理 =========================================================
            logger.error(f"{operation_name}失败: {str(e)}")
            import traceback
            traceback.print_exc()
            try:
                self.esxi_api.disconnect()
            except:
                pass
            return ZMessage(
                success=False, 
                action=operation_name,
                message=f"{operation_name}失败: {str(e)}")

    # 辅助方法 - 检查虚拟机是否存在 ============================================
    def _check_vm_exists(self, vm_name: str) -> tuple:
        """
        检查虚拟机是否存在
        
        :param vm_name: 虚拟机名称
        :return: (是否存在, 虚拟机配置或None)
        """
        if vm_name not in self.vm_saving:
            return False, None
        return True, self.vm_saving[vm_name]

    # 读取远程 ######################################################################
    # 初始化WebMKS远程控制台（使用HttpManager反向代理）
    # :returns: 是否成功
    # ###############################################################################
    def VMLoader_VNC(self) -> bool:
        # ===== 新的WebMKS方式（使用HttpManager） =====
        cfg_name = "vmk_" + self.hs_config.server_name + ".txt"
        self.http_manager = HttpManager(
            cfg_name, "vmk",
            self.hs_config.public_addr[0] \
                if len(self.hs_config.public_addr) > 0 \
                else "127.0.0.1")
        self.vm_remote = "done"
        self.http_manager.launch_vnc(self.hs_config.remote_port)
        logger.info(
            f"[{self.hs_config.server_name}] "
            f"WebMKS远程控制台已初始化"
            f"（HttpManager端口: {self.hs_config.remote_port}）")
        return True

    # 宿主机任务 ===============================================================
    def Crontabs(self) -> bool:
        # 专用操作 =============================================================
        # 获取远程ESXi主机状态并保存
        try:
            # 获取主机状态 =====================================================
            hw_status = self.HSStatus()
            if hw_status:
                from MainObject.Server.HSStatus import HSStatus
                hs_status = HSStatus()
                hs_status.hw_status = hw_status
                
                # 保存状态 =====================================================
                self.host_set(hs_status)
                logger.debug(f"[{self.hs_config.server_name}] ESXi远程主机状态已更新")
                
        except Exception as e:
            # 异常处理 =========================================================
            logger.error(f"[{self.hs_config.server_name}] 获取ESXi远程主机状态失败: {str(e)}")
            import traceback
            traceback.print_exc()
            
        # 通用操作 =============================================================
        # 调用父类方法同步虚拟机状态
        return super().Crontabs()

    # 宿主机状态 ===============================================================
    def HSStatus(self) -> HWStatus:
        # 专用操作 =============================================================
        # 获取远程ESXi主机状态
        try:
            # 连接到ESXi =======================================================
            connect_result = self.esxi_api.connect()
            if not connect_result.success:
                logger.error(f"无法连接到ESXi获取状态: {connect_result.message}")
                return super().HSStatus()

            # 获取主机状态 =====================================================
            host_status = self.esxi_api.get_host_status()

            # 断开连接 =========================================================
            self.esxi_api.disconnect()

            # 构建状态对象 =====================================================
            if host_status:
                hw_status = HWStatus()
                hw_status.cpu_usage = host_status.get("cpu_usage_percent", 0)
                hw_status.ram_usage = host_status.get("memory_usage_percent", 0)
                hw_status.hdd_usage = 0  # ESXi需要额外查询存储使用率
                hw_status.cpu_total = host_status.get("cpu_total", 0)
                hw_status.mem_total = host_status.get("memory_total_mb", 0)
                hw_status.mem_usage = host_status.get("memory_used_mb", 0)
                logger.debug(f"[{self.hs_config.server_name}] 获取ESXi远程主机状态成功")
                return hw_status
                
        except Exception as e:
            # 异常处理 =========================================================
            logger.error(f"获取ESXi主机状态失败: {str(e)}")
            import traceback
            traceback.print_exc()

        # 通用操作 =============================================================
        return super().HSStatus()

    # 初始宿主机 ===============================================================
    def HSCreate(self) -> ZMessage:
        # 专用操作 =============================================================
        # ESXi不需要初始化操作，主机已经存在
        # 通用操作 =============================================================
        return super().HSCreate()

    # 还原宿主机 ===============================================================
    def HSDelete(self) -> ZMessage:
        # 专用操作 =============================================================
        # ESXi不需要还原操作
        # 通用操作 =============================================================
        return super().HSDelete()

    # 读取宿主机 ===============================================================
    def HSLoader(self) -> ZMessage:
        # 专用操作 =============================================================
        try:
            # 测试连接到ESXi ===================================================
            result = self.esxi_api.connect()
            if result.success:
                self.esxi_api.disconnect()
                logger.info(f"成功连接到ESXi主机: {self.hs_config.server_addr}")
            else:
                logger.error(f"无法连接到ESXi主机: {result.message}")
                return result
                
        except Exception as e:
            # 异常处理 =========================================================
            logger.error(f"连接ESXi主机失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return ZMessage(success=False, action="HSLoader", message=str(e))

        # 通用操作 =============================================================
        return super().HSLoader()

    # 卸载宿主机 ===============================================================
    def HSUnload(self) -> ZMessage:
        # 专用操作 =============================================================
        try:
            # 断开ESXi连接 =====================================================
            self.esxi_api.disconnect()
        except Exception as e:
            # 异常处理 =========================================================
            logger.error(f"断开ESXi连接失败: {str(e)}")
            import traceback
            traceback.print_exc()
            
        # 通用操作 =============================================================
        return super().HSUnload()

    # 虚拟机列出 ===============================================================
    def VMStatus(self, vm_name: str = "",
                 s_t: int = None, e_t: int = None) -> dict[str, list[HWStatus]]:

        # 专用操作 =============================================================
        # ESXi的虚拟机状态通过API实时获取
        # 通用操作 =============================================================
        return super().VMStatus(vm_name)

    # 获取虚拟机实际状态（从API）==============================================
    def GetPower(self, vm_name: str) -> str:
        """从vSphere ESXi API获取虚拟机实际状态"""
        try:
            connect_result = self.esxi_api.connect()
            if not connect_result.success:
                return ""
            
            vm_status = self.esxi_api.get_vm_status(vm_name)
            self.esxi_api.disconnect()
            
            if vm_status:
                power_state = vm_status.get('power_state', '')
                # 映射vSphere状态到中文状态
                state_map = {
                    'poweredOn': '运行中',
                    'poweredOff': '已关机',
                    'suspended': '已暂停'
                }
                return state_map.get(power_state, '未知')
        except Exception as e:
            logger.warning(f"从API获取虚拟机 {vm_name} 状态失败: {str(e)}")
            try:
                self.esxi_api.disconnect()
            except:
                pass
        return ""

    # 虚拟机扫描 ===============================================================
    def VMDetect(self) -> ZMessage:
        # 专用操作 =============================================================
        try:
            # 连接到ESXi =======================================================
            connect_result = self.esxi_api.connect()
            if not connect_result.success:
                return connect_result

            # 获取虚拟机列表 ===================================================
            # 使用主机配置的filter_name作为前缀过滤
            filter_prefix = self.hs_config.filter_name if self.hs_config else ""
            vms_list = self.esxi_api.list_vms(filter_prefix)

            scanned_count = len(vms_list)
            added_count = 0

            # 处理每个虚拟机 ===================================================
            for vm_info in vms_list:
                vm_name = vm_info.get("name", "")
                if not vm_name:
                    continue

                # 检查是否已存在 ===============================================
                if vm_name in self.vm_saving:
                    continue

                # 创建默认虚拟机配置 ===========================================
                default_vm_config = VMConfig()
                default_vm_config.vm_uuid = vm_name
                default_vm_config.cpu_num = vm_info.get("cpu", 1)
                default_vm_config.mem_num = vm_info.get("memory_mb", 1024)

                # 添加到服务器的虚拟机配置中 ===================================
                self.vm_saving[vm_name] = default_vm_config
                added_count += 1

                # 记录日志 =====================================================
                log_msg = ZMessage(
                    success=True,
                    action="VScanner",
                    message=f"发现并添加虚拟机: {vm_name}",
                    results={
                        "vm_name": vm_name,
                        "cpu": vm_info.get("cpu", 0),
                        "memory_mb": vm_info.get("memory_mb", 0),
                        "power_state": vm_info.get("power_state", "unknown")
                    }
                )
                self.push_log(log_msg)

            # 断开连接 =========================================================
            self.esxi_api.disconnect()

            # 保存到数据库 =====================================================
            if added_count > 0:
                success = self.data_set()
                if not success:
                    return ZMessage(
                        success=False, action="VScanner",
                        message="Failed to save scanned DockManage to database")

            # 返回成功消息 =====================================================
            return ZMessage(
                success=True,
                action="VScanner",
                message=f"扫描完成。共扫描到{scanned_count}台虚拟机，新增{added_count}台虚拟机配置。",
                results={
                    "scanned": scanned_count,
                    "added": added_count,
                    "prefix_filter": filter_prefix
                }
            )

        except Exception as e:
            # 异常处理 =========================================================
            logger.error(f"扫描虚拟机失败: {str(e)}")
            import traceback
            traceback.print_exc()
            try:
                self.esxi_api.disconnect()
            except:
                pass
            return ZMessage(success=False, action="VScanner",
                            message=f"扫描虚拟机时出错: {str(e)}")

        # 通用操作 =============================================================
        # return ZMessage(success=False, action="VScanner", message="Not implemented")

    # 创建虚拟机 ===============================================================
    def VMCreate(self, vm_conf: VMConfig) -> ZMessage:
        # 网络检查和IP分配 =====================================================
        vm_conf, net_result = self.NetCheck(vm_conf)
        if not net_result.success:
            return net_result
        self.IPBinder(vm_conf, True)

        # 专用操作 =============================================================
        try:
            logger.info(f"[{self.hs_config.server_name}] 开始创建虚拟机: {vm_conf.vm_uuid}")
            logger.info(f"  - CPU: {vm_conf.cpu_num}核, 内存: {vm_conf.mem_num}MB, 磁盘: {vm_conf.hdd_num}GB")
            logger.info(f"  - 网卡数量: {len(vm_conf.nic_all)}, 系统镜像: {vm_conf.os_name}")
            
            # 连接到ESXi =======================================================
            connect_result = self.esxi_api.connect()
            if not connect_result.success:
                logger.error(f"[{self.hs_config.server_name}] 连接ESXi失败: {connect_result.message}")
                return connect_result

            # 创建虚拟机 =======================================================
            create_result = self.esxi_api.create_vm(vm_conf, self.hs_config)
            if not create_result.success:
                logger.error(f"[{self.hs_config.server_name}] 创建虚拟机失败: {create_result.message}")
                self.esxi_api.disconnect()
                return create_result
            logger.info(f"[{self.hs_config.server_name}] 虚拟机 {vm_conf.vm_uuid} 创建成功")

            # 安装系统 =========================================================
            if vm_conf.os_name:
                install_result = self.VMSetups(vm_conf)
                if not install_result.success:
                    # 安装失败，删除虚拟机
                    self.esxi_api.delete_vm(vm_conf.vm_uuid)
                    self.esxi_api.disconnect()
                    return install_result

            # 启动虚拟机 =======================================================
            logger.info(f"[{self.hs_config.server_name}] 启动虚拟机 {vm_conf.vm_uuid}")
            self.esxi_api.power_on(vm_conf.vm_uuid)

            # 断开连接 =========================================================
            self.esxi_api.disconnect()

            logger.info(f"[{self.hs_config.server_name}] 虚拟机 {vm_conf.vm_uuid} 创建完成并已启动")

        except ConnectionError as e:
            # 网络连接异常 =====================================================
            logger.error(f"[{self.hs_config.server_name}] 虚拟机创建失败 - 网络连接错误: {str(e)}")
            import traceback
            traceback.print_exc()
            try:
                self.esxi_api.disconnect()
            except:
                pass
            hs_result = ZMessage(
                success=False, action="VMCreate",
                message=f"网络连接失败: {str(e)}")
            self.logs_set(hs_result)
            return hs_result
        except PermissionError as e:
            # 权限异常 =========================================================
            logger.error(f"[{self.hs_config.server_name}] 虚拟机创建失败 - 权限不足: {str(e)}")
            import traceback
            traceback.print_exc()
            try:
                self.esxi_api.disconnect()
            except:
                pass
            hs_result = ZMessage(
                success=False, action="VMCreate",
                message=f"权限不足: {str(e)}")
            self.logs_set(hs_result)
            return hs_result
        except Exception as e:
            # 其他异常 =========================================================
            logger.error(f"[{self.hs_config.server_name}] 虚拟机创建失败 - 未预期错误: {str(e)}")
            import traceback
            traceback.print_exc()
            try:
                self.esxi_api.disconnect()
            except:
                pass
            hs_result = ZMessage(
                success=False, action="VMCreate",
                message=f"虚拟机创建失败: {str(e)}")
            self.logs_set(hs_result)
            return hs_result

        # 通用操作 =============================================================
        result = super().VMCreate(vm_conf)

        # ===== 旧的VNC远程访问配置（已注释） =====
        # if result.success:
        #     try:
        #         remote_result = self.VMRemote(vm_conf.vm_uuid)
        #         if remote_result.success:
        #             logger.info(f"虚拟机 {vm_conf.vm_uuid} VNC远程访问配置成功")
        #         else:
        #             logger.warning(f"虚拟机 {vm_conf.vm_uuid} VNC远程访问配置失败: {remote_result.message}")
        #     except Exception as e:
        #         logger.warning(f"配置VNC远程访问时出错: {str(e)}")

        return result

    # 安装虚拟机 ===============================================================
    def VMSetups(self, vm_conf: VMConfig) -> ZMessage:
        # 专用操作 =============================================================
        # 注意：硬盘已经在create_vm时分配，这里只需要返回成功
        # 如果需要额外的安装步骤（如配置cloud-init等），可以在这里添加
        try:
            logger.info(f"虚拟机 {vm_conf.vm_uuid} 系统安装完成（硬盘已在创建时分配）")
            return ZMessage(success=True, action="VInstall",
                            message="系统安装完成")
        except Exception as e:
            # 异常处理 =========================================================
            logger.error(f"安装虚拟机失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return ZMessage(success=False, action="VInstall",
                            message=f"安装失败: {str(e)}")

        # 通用操作 =============================================================
        # return super().VInstall(vm_conf)

    # 配置虚拟机 ===============================================================
    def VMUpdate(self, vm_conf: VMConfig, vm_last: VMConfig) -> ZMessage:
        # 网络检查 =============================================================
        vm_conf, net_result = self.NetCheck(vm_conf)
        if not net_result.success:
            return net_result
        self.IPBinder(vm_conf, True)

        # 专用操作 =============================================================
        try:
            # 连接到ESXi =======================================================
            connect_result = self.esxi_api.connect()
            if not connect_result.success:
                return connect_result

            # 检查虚拟机是否存在 ===============================================
            if vm_conf.vm_uuid not in self.vm_saving:
                self.esxi_api.disconnect()
                return ZMessage(
                    success=False, action="VMUpdate",
                    message=f"虚拟机 {vm_conf.vm_uuid} 不存在")

            # 更新虚拟机配置存储 ===============================================
            self.vm_saving[vm_conf.vm_uuid] = vm_conf

            # 关闭虚拟机 =======================================================
            # ESXi需要关机才能修改配置
            self.esxi_api.power_off(vm_conf.vm_uuid)

            # 重装系统 =========================================================
            if vm_conf.os_name != vm_last.os_name and vm_last.os_name != "":
                install_result = self.VMSetups(vm_conf)
                if not install_result.success:
                    self.esxi_api.disconnect()
                    return install_result

            # 更新CPU和内存配置 ================================================
            if vm_conf.cpu_num != vm_last.cpu_num or vm_conf.mem_num != vm_last.mem_num:
                update_result = self.esxi_api.update_vm_config(vm_conf.vm_uuid, vm_conf)
                if not update_result.success:
                    self.esxi_api.disconnect()
                    return update_result

            # 更新硬盘 =========================================================
            if vm_conf.hdd_num > vm_last.hdd_num:
                logger.info(f"[{self.hs_config.server_name}] 开始扩容虚拟机 {vm_conf.vm_uuid} 磁盘: {vm_last.hdd_num}GB -> {vm_conf.hdd_num}GB")
                try:
                    # 调用ESXi API扩容主磁盘
                    expand_result = self.esxi_api.expand_disk(vm_conf.vm_uuid, vm_conf.hdd_num)
                    if expand_result.success:
                        logger.info(f"[{self.hs_config.server_name}] 虚拟机 {vm_conf.vm_uuid} 磁盘扩容成功")
                    else:
                        logger.error(f"[{self.hs_config.server_name}] 虚拟机 {vm_conf.vm_uuid} 磁盘扩容失败: {expand_result.message}")
                        self.esxi_api.disconnect()
                        return expand_result
                except Exception as disk_e:
                    logger.error(f"[{self.hs_config.server_name}] 磁盘扩容异常: {str(disk_e)}")
                    import traceback
                    traceback.print_exc()

            # 更新网卡设备 =====================================================
            network_result = self.esxi_api.update_network_adapters(vm_conf.vm_uuid, vm_conf, vm_last, self.hs_config)
            if not network_result.success:
                self.esxi_api.disconnect()
                return ZMessage(
                    success=False, action="VMUpdate",
                    message=f"虚拟机 {vm_conf.vm_uuid} 网卡设备更新失败: {network_result.message}")

            # 更新网络绑定 =====================================================
            binding_result = self.IPUpdate(vm_conf, vm_last)
            if not binding_result.success:
                self.esxi_api.disconnect()
                return ZMessage(
                    success=False, action="VMUpdate",
                    message=f"虚拟机 {vm_conf.vm_uuid} 网络绑定更新失败: {binding_result.message}")

            # 启动虚拟机 =======================================================
            start_result = self.esxi_api.power_on(vm_conf.vm_uuid)
            if not start_result.success:
                self.esxi_api.disconnect()
                return ZMessage(
                    success=False, action="VMUpdate",
                    message=f"虚拟机 {vm_conf.vm_uuid} 启动失败: {start_result.message}")

            # 断开连接 =========================================================
            self.esxi_api.disconnect()

        except Exception as e:
            # 异常处理 =========================================================
            logger.error(f"虚拟机配置更新失败: {str(e)}")
            import traceback
            traceback.print_exc()
            try:
                self.esxi_api.disconnect()
            except:
                pass
            return ZMessage(
                success=False, action="VMUpdate",
                message=f"虚拟机配置更新失败: {str(e)}")

        # 通用操作 =============================================================
        return super().VMUpdate(vm_conf, vm_last)

    # 删除虚拟机 ===============================================================
    def VMDelete(self, vm_name: str, rm_back=True) -> ZMessage:
        # 专用操作 =============================================================
        try:
            logger.info(f"[{self.hs_config.server_name}] 开始删除虚拟机: {vm_name}")
            
            # 检查虚拟机是否存在 ===============================================
            vm_conf = self.VMSelect(vm_name)
            if vm_conf is None:
                logger.warning(f"[{self.hs_config.server_name}] 虚拟机 {vm_name} 不存在")
                return ZMessage(
                    success=False,
                    action="VMDelete",
                    message=f"虚拟机 {vm_name} 不存在")

            # 连接到ESXi =======================================================
            connect_result = self.esxi_api.connect()
            if not connect_result.success:
                logger.error(f"[{self.hs_config.server_name}] 连接ESXi失败: {connect_result.message}")
                return connect_result

            # 删除网络绑定 =====================================================
            logger.info(f"[{self.hs_config.server_name}] 删除虚拟机 {vm_name} 的网络绑定")
            self.IPBinder(vm_conf, False)

            # 删除虚拟机 =======================================================
            logger.info(f"[{self.hs_config.server_name}] 从ESXi删除虚拟机 {vm_name}")
            delete_result = self.esxi_api.delete_vm(vm_name)

            # 断开连接 =========================================================
            self.esxi_api.disconnect()
            
            # 更新配置 =========================================================
            self.vm_saving.pop(vm_name)
            self.data_set()
            
            if not delete_result.success:
                logger.error(f"[{self.hs_config.server_name}] 删除虚拟机失败: {delete_result.message}")
                return delete_result
            
            logger.info(f"[{self.hs_config.server_name}] 虚拟机 {vm_name} 删除成功")

        except Exception as e:
            # 异常处理 =========================================================
            logger.error(f"[{self.hs_config.server_name}] 删除虚拟机 {vm_name} 失败: {str(e)}", exc_info=True)
            import traceback
            traceback.print_exc()
            try:
                self.esxi_api.disconnect()
            except:
                pass
            return ZMessage(
                success=False, action="VMDelete",
                message=f"删除虚拟机失败: {str(e)}")

        # 通用操作 =============================================================
        super().VMDelete(vm_name)
        return ZMessage(success=True, action="VMDelete", message="虚拟机删除成功")

    # 虚拟机电源 ===============================================================
    def VMPowers(self, vm_name: str, power: VMPowers) -> ZMessage:
        # 专用操作 =============================================================
        original_flag = None
        try:
            # 先调用父类方法设置中间状态
            parent_result = super().VMPowers(vm_name, power)
            original_flag = parent_result.results.get("original_flag") if parent_result.results else None
            
            # 连接到ESXi =======================================================
            connect_result = self.esxi_api.connect()
            if not connect_result.success:
                # 连接失败，回退状态
                if original_flag is not None:
                    self.vm_saving[vm_name].vm_flag = original_flag
                    self.data_set()
                return connect_result

            # 执行电源操作 =====================================================
            if power == VMPowers.S_START:
                hs_result = self.esxi_api.power_on(vm_name)
            elif power == VMPowers.H_CLOSE:
                hs_result = self.esxi_api.power_off(vm_name)
            elif power == VMPowers.S_CLOSE:
                # 软关机：使用power_off但标记为软关机，启动监控线程
                hs_result = ZMessage(success=True, action="VMPowers", message="正在等待系统软关机")
                # 启动持续监控（5分钟内每5秒检查一次状态）
                self._monitor_soft_power_operation(vm_name, VMPowers.S_CLOSE, VMPowers.ON_STOP)
            elif power == VMPowers.A_PAUSE:
                hs_result = self.esxi_api.suspend(vm_name)
            elif power == VMPowers.S_RESET:
                # 软重启：使用reset但启动监控线程
                hs_result = self.esxi_api.reset(vm_name)
                if hs_result.success:
                    # 启动持续监控（5分钟内每5秒检查一次状态）
                    self._monitor_soft_power_operation(vm_name, VMPowers.S_RESET, VMPowers.ON_STOP)
            elif power == VMPowers.H_RESET:
                hs_result = self.esxi_api.reset(vm_name)
            else:
                hs_result = ZMessage(
                    success=False, action="VMPowers",
                    message=f"不支持的电源操作: {power}")

            # 断开连接 =========================================================
            self.esxi_api.disconnect()

            # 如果操作失败，回退状态
            if not hs_result.success and original_flag is not None:
                logger.error(f"[{self.hs_config.server_name}] 虚拟机电源操作失败，回退状态: {vm_name}")
                self.vm_saving[vm_name].vm_flag = original_flag
                self.data_set()
            elif hs_result.success and power not in [VMPowers.S_CLOSE, VMPowers.S_RESET]:
                # 对于非软关机/软重启操作，操作成功后异步刷新虚拟机状态（延迟3秒后执行）
                import threading
                def delayed_refresh():
                    import time
                    time.sleep(3)  # 等待3秒让虚拟机状态稳定
                    self._refresh_vm_status(vm_name)
                
                refresh_thread = threading.Thread(target=delayed_refresh, daemon=True)
                refresh_thread.start()

            # 记录日志 =========================================================
            self.logs_set(hs_result)

        except Exception as e:
            # 异常处理 =========================================================
            logger.error(f"电源操作失败: {str(e)}")
            import traceback
            traceback.print_exc()
            try:
                self.esxi_api.disconnect()
            except:
                pass
            
            # 回退状态
            if original_flag is not None:
                self.vm_saving[vm_name].vm_flag = original_flag
                self.data_set()
            
            hs_result = ZMessage(
                success=False, action="VMPowers",
                message=f"电源操作失败: {str(e)}")
            self.logs_set(hs_result)

        # 通用操作 =============================================================
        return hs_result

    # 设置虚拟机密码 ===========================================================
    def VMPasswd(self, vm_name: str, os_pass: str) -> ZMessage:
        # 专用操作 =============================================================
        # ESXi通过guest tools设置密码，这里使用父类的实现
        # 通用操作 =============================================================
        return super().VMPasswd(vm_name, os_pass)

    # 备份虚拟机 ===============================================================
    def VMBackup(self, vm_name: str, vm_tips: str) -> ZMessage:
        # 专用操作 =============================================================
        try:
            # 生成备份名称 =========================================================
            bak_time = datetime.datetime.now()
            bak_name = vm_name + "-" + bak_time.strftime("%Y%m%d%H%M%S")

            # 连接到ESXi =======================================================
            connect_result = self.esxi_api.connect()
            if not connect_result.success:
                return connect_result

            # 创建快照作为备份 =====================================================
            snapshot_result = self.esxi_api.create_snapshot(
                vm_name,
                bak_name,
                vm_tips
            )

            # 断开连接 =========================================================
            self.esxi_api.disconnect()

            if not snapshot_result.success:
                return snapshot_result

            # 记录备份信息 =========================================================
            if vm_name in self.vm_saving:
                self.vm_saving[vm_name].backups.append(
                    VMBackup(
                        backup_name=bak_name,
                        backup_time=bak_time,
                        backup_tips=vm_tips
                    )
                )
                self.data_set()

            return ZMessage(success=True, action="VMBackup",
                            message=f"虚拟机备份成功: {bak_name}")

        except Exception as e:
            # 异常处理 =========================================================
            logger.error(f"备份失败: {str(e)}")
            import traceback
            traceback.print_exc()
            try:
                self.esxi_api.disconnect()
            except:
                pass
            return ZMessage(success=False, action="VMBackup",
                            message=f"备份失败: {str(e)}")

        # 通用操作 =============================================================
        # return super().VMBackup(vm_name, vm_tips)

    # 恢复虚拟机 ===============================================================
    def Restores(self, vm_name: str, vm_back: str) -> ZMessage:
        # 专用操作 =============================================================
        try:
            # 连接到ESXi =======================================================
            connect_result = self.esxi_api.connect()
            if not connect_result.success:
                return connect_result

            # 恢复快照 =========================================================
            restore_result = self.esxi_api.revert_snapshot(vm_name, vm_back)

            # 断开连接 =========================================================
            self.esxi_api.disconnect()

            if not restore_result.success:
                return restore_result

            return ZMessage(success=True, action="Restores",
                            message=f"虚拟机恢复成功: {vm_back}")

        except Exception as e:
            # 异常处理 =========================================================
            logger.error(f"恢复失败: {str(e)}")
            import traceback
            traceback.print_exc()
            try:
                self.esxi_api.disconnect()
            except:
                pass
            return ZMessage(success=False, action="Restores",
                            message=f"恢复失败: {str(e)}")

        # 通用操作 =============================================================
        # return super().Restores(vm_name, vm_back)

    # VM镜像挂载 ===============================================================
    def HDDMount(self, vm_name: str, vm_imgs: SDConfig, in_flag=True) -> ZMessage:
        # 专用操作 =============================================================
        try:
            # 检查虚拟机是否存在 ===============================================
            if vm_name not in self.vm_saving:
                return ZMessage(
                    success=False, action="HDDMount", message="虚拟机不存在")

            # 连接到ESXi =======================================================
            connect_result = self.esxi_api.connect()
            if not connect_result.success:
                return connect_result

            # 关闭虚拟机 =======================================================
            self.esxi_api.power_off(vm_name)

            if in_flag:  # 挂载磁盘 =============================================
                # 添加磁盘 =====================================================
                add_result = self.esxi_api.add_disk(
                    vm_name,
                    vm_imgs.hdd_size,
                    vm_imgs.hdd_name
                )
                if not add_result.success:
                    self.esxi_api.disconnect()
                    return add_result

                vm_imgs.hdd_flag = 1
                self.vm_saving[vm_name].hdd_all[vm_imgs.hdd_name] = vm_imgs
            else:  # 卸载磁盘 ===================================================
                if vm_imgs.hdd_name not in self.vm_saving[vm_name].hdd_all:
                    self.esxi_api.power_on(vm_name)
                    self.esxi_api.disconnect()
                    return ZMessage(
                        success=False, action="HDDMount", message="磁盘不存在")

                # 卸载磁盘
                logger.info(f"[{self.hs_config.server_name}] 卸载虚拟机 {vm_name} 的磁盘: {vm_imgs.hdd_name}")
                remove_result = self.esxi_api.remove_disk(vm_name, vm_imgs.hdd_name)
                if not remove_result.success:
                    logger.warning(f"[{self.hs_config.server_name}] 磁盘卸载失败: {remove_result.message}")
                self.vm_saving[vm_name].hdd_all[vm_imgs.hdd_name].hdd_flag = 0

            # 启动虚拟机 =======================================================
            self.esxi_api.power_on(vm_name)

            # 断开连接 =========================================================
            self.esxi_api.disconnect()

            # 保存配置 =========================================================
            self.data_set()

            action_text = "挂载" if in_flag else "卸载"
            return ZMessage(
                success=True,
                action="HDDMount",
                message=f"磁盘{action_text}成功")

        except Exception as e:
            # 异常处理 =========================================================
            logger.error(f"磁盘操作失败: {str(e)}")
            import traceback
            traceback.print_exc()
            try:
                self.esxi_api.disconnect()
            except:
                pass
            return ZMessage(
                success=False, action="HDDMount",
                message=f"磁盘操作失败: {str(e)}")

        # 通用操作 =============================================================
        # return super().HDDMount(vm_name, vm_imgs, in_flag)

    # ISO镜像挂载 ==============================================================
    def ISOMount(self, vm_name: str, vm_imgs: IMConfig, in_flag=True) -> ZMessage:
        # 专用操作 =============================================================
        try:
            # 检查虚拟机是否存在 ===============================================
            if vm_name not in self.vm_saving:
                return ZMessage(
                    success=False, action="ISOMount", message="虚拟机不存在")

            # 连接到ESXi =======================================================
            connect_result = self.esxi_api.connect()
            if not connect_result.success:
                return connect_result

            logger.info(f"准备{'挂载' if in_flag else '卸载'}ISO: {vm_imgs.iso_name}")

            # 关闭虚拟机 =======================================================
            self.esxi_api.power_off(vm_name)

            if in_flag:  # 挂载ISO =============================================
                # 构建ISO文件路径 =============================================
                # dvdrom_path格式: datastore1/images
                if self.hs_config.dvdrom_path and '/' in self.hs_config.dvdrom_path:
                    images_parts = self.hs_config.dvdrom_path.split('/', 1)
                    iso_datastore = images_parts[0]
                    iso_dir = images_parts[1]
                else:
                    iso_datastore = self.esxi_api.datastore_name
                    iso_dir = "images"

                iso_path = f"[{iso_datastore}] {iso_dir}/{vm_imgs.iso_file}"
                logger.info(f"[{self.hs_config.server_name}] 挂载ISO到虚拟机 {vm_name}: {iso_path}")

                # 挂载ISO =======================================================
                attach_result = self.esxi_api.attach_iso(vm_name, iso_path)
                if not attach_result.success:
                    self.esxi_api.power_on(vm_name)
                    self.esxi_api.disconnect()
                    return attach_result

                # 检查挂载名称是否已存在 =======================================
                if vm_imgs.iso_name in self.vm_saving[vm_name].iso_all:
                    self.esxi_api.power_on(vm_name)
                    self.esxi_api.disconnect()
                    return ZMessage(
                        success=False, action="ISOMount", message="挂载名称已存在")

                self.vm_saving[vm_name].iso_all[vm_imgs.iso_name] = vm_imgs
                logger.info(f"ISO挂载成功: {vm_imgs.iso_name} -> {vm_imgs.iso_file}")
            else:  # 卸载ISO ===================================================
                if vm_imgs.iso_name not in self.vm_saving[vm_name].iso_all:
                    self.esxi_api.power_on(vm_name)
                    self.esxi_api.disconnect()
                    return ZMessage(
                        success=False, action="ISOMount", message="ISO镜像不存在")

                # 卸载ISO（设置为空）
                logger.info(f"[{self.hs_config.server_name}] 卸载虚拟机 {vm_name} 的ISO: {vm_imgs.iso_name}")
                detach_result = self.esxi_api.detach_iso(vm_name)
                if not detach_result.success:
                    logger.warning(f"[{self.hs_config.server_name}] ISO卸载失败: {detach_result.message}")
                del self.vm_saving[vm_name].iso_all[vm_imgs.iso_name]
                logger.info(f"[{self.hs_config.server_name}] ISO卸载成功: {vm_imgs.iso_name}")

            # 启动虚拟机 =======================================================
            self.esxi_api.power_on(vm_name)

            # 断开连接 =========================================================
            self.esxi_api.disconnect()

            # 保存配置 =========================================================
            self.data_set()

            action_text = "挂载" if in_flag else "卸载"
            return ZMessage(
                success=True,
                action="ISOMount",
                message=f"ISO镜像{action_text}成功")

        except Exception as e:
            # 异常处理 =========================================================
            logger.error(f"ISO操作失败: {str(e)}")
            import traceback
            traceback.print_exc()
            try:
                self.esxi_api.disconnect()
            except:
                pass
            return ZMessage(
                success=False, action="ISOMount",
                message=f"ISO操作失败: {str(e)}")

        # 通用操作 =============================================================
        # return super().ISOMount(vm_name, vm_imgs, in_flag)

    # 加载备份 =================================================================
    def LDBackup(self, vm_back: str = "") -> ZMessage:
        # 专用操作 =============================================================
        try:
            # 连接到ESXi =======================================================
            connect_result = self.esxi_api.connect()
            if not connect_result.success:
                return connect_result

            # 清空现有备份记录 =====================================================
            for vm_name in self.vm_saving:
                self.vm_saving[vm_name].backups = []

            bal_nums = 0

            # 遍历所有虚拟机，获取快照信息 =======================================
            for vm_name in self.vm_saving:
                vm = self.esxi_api.get_vm(vm_name)
                if not vm or not hasattr(vm, 'snapshot') or not vm.snapshot:
                    continue

                # 递归获取所有快照 =============================================
                snapshots = self._get_all_snapshots(vm.snapshot.rootSnapshotList)

                for snapshot in snapshots:
                    bal_nums += 1
                    # 解析快照名称（格式：vm_name-YYYYMMDDHHmmss）
                    snap_name = snapshot.name
                    parts = snap_name.split("-")
                    if len(parts) >= 2:
                        try:
                            snap_time = datetime.datetime.strptime(parts[-1], "%Y%m%d%H%M%S")
                            self.vm_saving[vm_name].backups.append(
                                VMBackup(
                                    backup_name=snap_name,
                                    backup_time=snap_time,
                                    backup_tips=snapshot.description
                                )
                            )
                        except ValueError:
                            logger.warning(f"无法解析快照时间: {snap_name}")

            # 断开连接 =========================================================
            self.esxi_api.disconnect()

            # 保存配置 =========================================================
            self.data_set()

            return ZMessage(
                success=True,
                action="LDBackup",
                message=f"{bal_nums}个备份快照已加载")

        except Exception as e:
            # 异常处理 =========================================================
            logger.error(f"加载备份失败: {str(e)}")
            import traceback
            traceback.print_exc()
            try:
                self.esxi_api.disconnect()
            except:
                pass
            return ZMessage(
                success=False, action="LDBackup",
                message=f"加载备份失败: {str(e)}")

        # 通用操作 =============================================================
        # return super().LDBackup(vm_back)

    # 辅助方法 - 递归获取所有快照 ============================================
    def _get_all_snapshots(self, snapshot_list):
        """递归获取所有快照"""
        snapshots = []
        for snapshot in snapshot_list:
            snapshots.append(snapshot)
            if hasattr(snapshot, 'childSnapshotList') and snapshot.childSnapshotList:
                snapshots.extend(self._get_all_snapshots(snapshot.childSnapshotList))
        return snapshots

    # 移除备份 =================================================================
    def RMBackup(self, vm_name: str, vm_back: str = "") -> ZMessage:
        # 专用操作 =============================================================
        try:
            # 从备份名称中提取虚拟机名称 =======================================
            parts = vm_back.split("-")
            if len(parts) < 2:
                return ZMessage(
                    success=False, action="RMBackup",
                    message="备份名称格式不正确")

            vm_name = parts[0]

            # 连接到ESXi =======================================================
            connect_result = self.esxi_api.connect()
            if not connect_result.success:
                return connect_result

            # 删除快照 =========================================================
            delete_result = self.esxi_api.delete_snapshot(vm_name, vm_back)

            # 断开连接 =========================================================
            self.esxi_api.disconnect()

            if not delete_result.success:
                return delete_result

            # 从配置中移除备份记录 =============================================
            if vm_name in self.vm_saving:
                self.vm_saving[vm_name].backups = [
                    b for b in self.vm_saving[vm_name].backups
                    if b.backup_name != vm_back
                ]
                self.data_set()

            return ZMessage(
                success=True, action="RMBackup",
                message="备份快照已删除")

        except Exception as e:
            # 异常处理 =========================================================
            logger.error(f"删除备份失败: {str(e)}")
            import traceback
            traceback.print_exc()
            try:
                self.esxi_api.disconnect()
            except:
                pass
            return ZMessage(
                success=False, action="RMBackup",
                message=f"删除备份失败: {str(e)}")

        # 通用操作 =============================================================
        # return super().RMBackup(vm_back)

    # 移除磁盘 =================================================================
    def RMMounts(self, vm_name: str, vm_imgs: str) -> ZMessage:
        # 专用操作 =============================================================
        try:
            # 检查虚拟机是否存在 ===============================================
            if vm_name not in self.vm_saving:
                return ZMessage(
                    success=False, action="RMMounts", message="虚拟机不存在")
            if vm_imgs not in self.vm_saving[vm_name].hdd_all:
                return ZMessage(
                    success=False, action="RMMounts", message="虚拟盘不存在")

            # 获取虚拟磁盘数据 =================================================
            hd_data = self.vm_saving[vm_name].hdd_all[vm_imgs]

            # 卸载虚拟磁盘 =====================================================
            if hd_data.hdd_flag == 1:
                unmount_result = self.HDDMount(vm_name, hd_data, False)
                if not unmount_result.success:
                    return unmount_result

            # 从配置中移除 =====================================================
            self.vm_saving[vm_name].hdd_all.pop(vm_imgs)
            self.data_set()

            # 从ESXi中删除磁盘文件
            logger.info(f"[{self.hs_config.server_name}] 从ESXi删除虚拟机 {vm_name} 的磁盘文件: {vm_imgs}")
            try:
                connect_result = self.esxi_api.connect()
                if connect_result.success:
                    delete_file_result = self.esxi_api.delete_disk_file(vm_name, vm_imgs)
                    if not delete_file_result.success:
                        logger.warning(f"[{self.hs_config.server_name}] 删除磁盘文件失败: {delete_file_result.message}")
                    self.esxi_api.disconnect()
            except Exception as del_e:
                logger.warning(f"[{self.hs_config.server_name}] 删除磁盘文件异常: {str(del_e)}")

            return ZMessage(
                success=True, action="RMMounts",
                message="磁盘删除成功")

        except Exception as e:
            # 异常处理 =========================================================
            logger.error(f"删除磁盘失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return ZMessage(
                success=False, action="RMMounts",
                message=f"删除磁盘失败: {str(e)}")

        # 通用操作 =============================================================
        # return super().RMMounts(vm_name, vm_imgs)

    # 查找PCI设备 =================================================================
    def PCIShows(self) -> dict[str, 'VFConfig']:
        """获取可用的PCI直通设备列表
        Returns:
            dict: {pci_id: VFConfig}
        """
        from MainObject.Config.VFConfig import VFConfig
        try:
            logger.info(f"[{self.hs_config.server_name}] 开始获取PCI设备列表")
            connect_result = self.esxi_api.connect()
            if not connect_result.success:
                logger.error(f"[{self.hs_config.server_name}] ESXi连接失败: {connect_result.message}")
                return {}

            try:
                from pyVmomi import vim
                host = self.esxi_api.get_host()
                if not host:
                    self.esxi_api.disconnect()
                    return {}

                device_dict = {}
                passthru_map = {}

                # 构建直通状态映射
                if hasattr(host.config, 'pciPassthruInfo'):
                    for info in host.config.pciPassthruInfo:
                        passthru_map[info.id] = info.passthruEnabled

                # 遍历所有PCI设备
                if hasattr(host, 'hardware') and hasattr(host.hardware, 'pciDevice'):
                    for pci_device in host.hardware.pciDevice:
                        # 仅列出已启用直通的设备
                        pci_id = pci_device.id
                        passthru_enabled = passthru_map.get(pci_id, False)
                        if not passthru_enabled:
                            continue

                        device_name = getattr(pci_device, 'deviceName', '') or getattr(pci_device, 'vendorName', 'Unknown')
                        device_dict[pci_id] = VFConfig(
                            gpu_uuid=pci_id,
                            gpu_mdev="ESXi_Passthrough",
                            gpu_hint=device_name
                        )
                        logger.info(f"[{self.hs_config.server_name}] 发现可直通设备: {pci_id} - {device_name}")

                self.esxi_api.disconnect()
                return device_dict

            except Exception as api_error:
                logger.error(f"[{self.hs_config.server_name}] 获取PCI设备失败: {str(api_error)}")
                traceback.print_exc()
                try:
                    self.esxi_api.disconnect()
                except:
                    pass
                return {}

        except Exception as e:
            logger.error(f"[{self.hs_config.server_name}] 获取PCI设备列表失败: {str(e)}")
            return {}

    # PCI设备直通 ==============================================================
    def PCISetup(self, vm_name: str, config, pci_key: str, in_flag=True):
        """ESXi PCI设备直通 - 通过pyVmomi添加/移除VirtualPCIPassthrough"""
        from MainObject.Public.ZMessage import ZMessage
        try:
            if vm_name not in self.vm_saving:
                return ZMessage(success=False, action="PCISetup", message="虚拟机不存在")

            from MainObject.Config.VMPowers import VMPowers
            vm_config = self.vm_saving[vm_name]
            if vm_config.vm_flag not in [VMPowers.ON_STOP, VMPowers.UNKNOWN]:
                return ZMessage(success=False, action="PCISetup", message="PCI直通需要先关闭虚拟机")

            connect_result = self.esxi_api.connect()
            if not connect_result.success:
                return ZMessage(success=False, action="PCISetup", message=f"ESXi连接失败: {connect_result.message}")

            try:
                from pyVmomi import vim
                vm = self.esxi_api.get_vm(vm_name)
                if not vm:
                    self.esxi_api.disconnect()
                    return ZMessage(success=False, action="PCISetup", message="虚拟机未在ESXi中找到")

                config_spec = vim.vm.ConfigSpec()

                if in_flag:
                    # 添加PCI直通设备
                    pci_id = config.gpu_uuid
                    backing = vim.vm.device.VirtualPCIPassthrough.DeviceBackingInfo()
                    backing.id = pci_id
                    backing.deviceId = ""

                    passthrough = vim.vm.device.VirtualPCIPassthrough()
                    passthrough.backing = backing

                    device_change = vim.vm.device.VirtualDeviceSpec()
                    device_change.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
                    device_change.device = passthrough

                    config_spec.deviceChange = [device_change]
                else:
                    # 移除PCI直通设备
                    pci_id = config.gpu_uuid
                    for device in vm.config.hardware.device:
                        if isinstance(device, vim.vm.device.VirtualPCIPassthrough):
                            if hasattr(device.backing, 'id') and device.backing.id == pci_id:
                                device_change = vim.vm.device.VirtualDeviceSpec()
                                device_change.operation = vim.vm.device.VirtualDeviceSpec.Operation.remove
                                device_change.device = device
                                config_spec.deviceChange = [device_change]
                                break

                task = vm.ReconfigVM_Task(config_spec)
                self.esxi_api._wait_for_task(task)
                self.esxi_api.disconnect()

            except Exception as api_err:
                try:
                    self.esxi_api.disconnect()
                except:
                    pass
                return ZMessage(success=False, action="PCISetup", message=str(api_err))

            # 调用基类写入配置
            return super().PCISetup(vm_name, config, pci_key, in_flag)

        except Exception as e:
            logger.error(f"[{self.hs_config.server_name}] PCI直通操作失败: {str(e)}")
            return ZMessage(success=False, action="PCISetup", message=str(e))

    # 查找USB设备 ==============================================================
    def USBShows(self) -> dict[str, 'USBInfos']:
        """获取ESXi主机上的USB设备列表"""
        from MainObject.Config.USBInfos import USBInfos
        try:
            connect_result = self.esxi_api.connect()
            if not connect_result.success:
                return {}

            try:
                host = self.esxi_api.get_host()
                if not host:
                    self.esxi_api.disconnect()
                    return {}

                usb_dict = {}
                # 通过host.hardware.usbDevice获取USB设备
                if hasattr(host.hardware, 'usbDevice'):
                    for usb_dev in host.hardware.usbDevice:
                        vid = format(usb_dev.vendor, '04x')
                        pid = format(usb_dev.product, '04x')
                        name = getattr(usb_dev, 'description', '') or f"USB {vid}:{pid}"
                        key = f"{vid}:{pid}"
                        usb_dict[key] = USBInfos(
                            vid_uuid=vid, pid_uuid=pid, usb_hint=name)
                        logger.info(f"[{self.hs_config.server_name}] 发现USB设备: {key} - {name}")

                self.esxi_api.disconnect()
                return usb_dict

            except Exception as api_err:
                logger.error(f"[{self.hs_config.server_name}] 获取USB设备失败: {str(api_err)}")
                try:
                    self.esxi_api.disconnect()
                except:
                    pass
                return {}

        except Exception as e:
            logger.error(f"[{self.hs_config.server_name}] 获取USB设备列表失败: {str(e)}")
            return {}

    # USB设备直通 ==============================================================
    def USBSetup(self, vm_name: str, usb_info, usb_key: str, in_flag=True):
        """ESXi USB设备直通 - 通过pyVmomi添加/移除VirtualUSB"""
        from MainObject.Public.ZMessage import ZMessage
        try:
            if vm_name not in self.vm_saving:
                return ZMessage(success=False, action="USBSetup", message="虚拟机不存在")

            connect_result = self.esxi_api.connect()
            if not connect_result.success:
                return ZMessage(success=False, action="USBSetup", message=f"ESXi连接失败: {connect_result.message}")

            try:
                from pyVmomi import vim
                vm = self.esxi_api.get_vm(vm_name)
                if not vm:
                    self.esxi_api.disconnect()
                    return ZMessage(success=False, action="USBSetup", message="虚拟机未在ESXi中找到")

                config_spec = vim.vm.ConfigSpec()

                if in_flag:
                    # 添加USB设备
                    backing = vim.vm.device.VirtualUSB.USBBackingInfo()
                    backing.vendor = int(usb_info.vid_uuid, 16)
                    backing.product = int(usb_info.pid_uuid, 16)

                    usb_device = vim.vm.device.VirtualUSB()
                    usb_device.backing = backing
                    usb_device.connected = True

                    device_change = vim.vm.device.VirtualDeviceSpec()
                    device_change.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
                    device_change.device = usb_device
                    config_spec.deviceChange = [device_change]
                else:
                    # 移除USB设备
                    vid = int(usb_info.vid_uuid, 16)
                    pid = int(usb_info.pid_uuid, 16)
                    for device in vm.config.hardware.device:
                        if isinstance(device, vim.vm.device.VirtualUSB):
                            if hasattr(device.backing, 'vendor') and \
                               device.backing.vendor == vid and device.backing.product == pid:
                                device_change = vim.vm.device.VirtualDeviceSpec()
                                device_change.operation = vim.vm.device.VirtualDeviceSpec.Operation.remove
                                device_change.device = device
                                config_spec.deviceChange = [device_change]
                                break

                task = vm.ReconfigVM_Task(config_spec)
                self.esxi_api._wait_for_task(task)
                self.esxi_api.disconnect()

            except Exception as api_err:
                try:
                    self.esxi_api.disconnect()
                except:
                    pass
                return ZMessage(success=False, action="USBSetup", message=str(api_err))

            # 更新虚拟机配置中的USB设备列表（不触发VMUpdate）
            vm_conf = self.vm_saving[vm_name]
            if in_flag:
                # 添加USB设备到配置
                if usb_key not in vm_conf.usb_all:
                    vm_conf.usb_all[usb_key] = usb_info
                    logger.info(f"[{self.hs_config.server_name}] 添加USB设备到配置: {usb_key}")
            else:
                # 从配置中移除USB设备
                if usb_key in vm_conf.usb_all:
                    del vm_conf.usb_all[usb_key]
                    logger.info(f"[{self.hs_config.server_name}] 从配置中移除USB设备: {usb_key}")

            logger.info(f"[{self.hs_config.server_name}] USB设备{'添加' if in_flag else '移除'}成功: {usb_key}")
            return ZMessage(success=True, action="USBSetup", message="USB设备操作成功")

        except Exception as e:
            logger.error(f"[{self.hs_config.server_name}] USB直通操作失败: {str(e)}")
            return ZMessage(success=False, action="USBSetup", message=str(e))

    # 虚拟机截图 ===============================================================
    def VMScreen(self, vm_name: str = "") -> str:
        """获取虚拟机截图
        
        :param vm_name: 虚拟机名称
        :return: base64编码的截图字符串，失败则返回空字符串
        """
        try:
            logger.info(f"[{self.hs_config.server_name}] 开始获取虚拟机 {vm_name} 截图")
            
            # 检查虚拟机是否存在 ===============================================
            if vm_name not in self.vm_saving:
                logger.error(f"[{self.hs_config.server_name}] 虚拟机 {vm_name} 不存在")
                return ""
            
            # 连接到ESXi =======================================================
            connect_result = self.esxi_api.connect()
            if not connect_result.success:
                logger.error(f"[{self.hs_config.server_name}] 无法连接到ESXi获取截图: {connect_result.message}")
                return ""
            
            # 获取虚拟机对象 ===================================================
            vm = self.esxi_api.get_vm(vm_name)
            if not vm:
                self.esxi_api.disconnect()
                logger.error(f"[{self.hs_config.server_name}] 未找到虚拟机 {vm_name}")
                return ""
            
            # 检查虚拟机是否正在运行 ===========================================
            if vm.runtime.powerState != "poweredOn":
                self.esxi_api.disconnect()
                logger.warning(f"[{self.hs_config.server_name}] 虚拟机 {vm_name} 未运行，无法获取截图")
                return ""
            
            # 使用vSphere API获取截图 =========================================
            import tempfile
            import os
            import base64
            
            temp_dir = tempfile.gettempdir()
            screenshot_path = os.path.join(temp_dir, f"{vm_name}_screenshot.png")
            
            # 使用vSphere API的CreateScreenshot_Task方法获取截图
            screenshot_result = self.esxi_api.get_vm_screenshot(vm_name, screenshot_path)
            
            # 断开连接 =========================================================
            self.esxi_api.disconnect()
            
            if not screenshot_result.success:
                logger.error(f"[{self.hs_config.server_name}] 获取虚拟机截图失败: {screenshot_result.message}")
                return ""
            
            # 读取截图文件并转换为base64 =======================================
            if os.path.exists(screenshot_path):
                with open(screenshot_path, "rb") as f:
                    screenshot_base64 = base64.b64encode(f.read()).decode('utf-8')
                
                # 删除临时文件 =================================================
                os.remove(screenshot_path)
                
                logger.info(f"[{self.hs_config.server_name}] 成功获取虚拟机 {vm_name} 截图")
                return screenshot_base64
            else:
                logger.error(f"[{self.hs_config.server_name}] 截图文件不存在: {screenshot_path}")
                return ""
                
        except Exception as e:
            # 异常处理 =========================================================
            logger.error(f"[{self.hs_config.server_name}] 获取虚拟机截图时出错: {str(e)}")
            import traceback
            traceback.print_exc()
            try:
                self.esxi_api.disconnect()
            except:
                pass
            return ""

    # WebMKS远程访问 ###########################################################
    def VMRemote(self, vm_uuid: str, ip_addr: str = "127.0.0.1") -> ZMessage:
        """
        获取虚拟机WebMKS远程访问链接
        
        :param vm_uuid: 虚拟机UUID
        :return: 包含访问URL的ZMessage
        """
        # 专用操作 =============================================================
        try:
            # 1. 检查虚拟机是否存在
            if vm_uuid not in self.vm_saving:
                return ZMessage(
                    success=False,
                    action="VMRemote",
                    message="虚拟机不存在")

            # 2. 连接到ESXi
            connect_result = self.esxi_api.connect()
            if not connect_result.success:
                return ZMessage(
                    success=False,
                    action="VMRemote",
                    message=f"无法连接到ESXi: {connect_result.message}")

            # 3. 获取WebMKS票据
            ticket_result = self.esxi_api.get_webmks_ticket(vm_uuid)
            self.esxi_api.disconnect()

            if not ticket_result.success:
                return ZMessage(
                    success=False,
                    action="VMRemote",
                    message=f"获取WebMKS票据失败: {ticket_result.message}")

            ticket_data = ticket_result.results
            ticket = ticket_data.get('ticket', '')
            host = self.hs_config.server_addr
            port = ticket_data.get('port', 443)

            # 4. 生成随机token（用于代理路径）
            import random
            import string
            token = ''.join(random.choices(string.ascii_letters + string.digits, k=16))

            # 5. 构建WebMKS WebSocket URL
            # WebMKS URL格式: wss://host:port/ticket/ticket_string
            webmks_url = f"wss://{host}:{port}/ticket/{ticket}"

            # 6. 添加HTTP代理（使用proxy_ssh方法）
            # 注意：这里复用proxy_ssh方法，实际上是代理WebSocket连接
            try:
                success = self.http_manager.create_vnc(token, host, port, ticket)
                if not success:
                    return ZMessage(
                        success=False,
                        action="VMRemote",
                        message="添加WebMKS代理失败")
            except Exception as e:
                logger.error(f"WebMKS代理配置失败: {str(e)}")
                return ZMessage(
                    success=False,
                    action="VMRemote",
                    message=f"WebMKS代理配置失败: {str(e)}")

            # 7. 获取主机外网IP
            if len(self.hs_config.public_addr) == 0:
                return ZMessage(
                    success=False,
                    action="VMRemote",
                    message="主机外网IP不存在")

            public_ip = self.hs_config.public_addr[0]
            if public_ip in ["localhost", "127.0.0.1", ""]:
                public_ip = "127.0.0.1"  # 默认使用本地

            # 8. 构造返回URL
            remote_port = self.hs_config.remote_port
            url = f"http://{public_ip}:{remote_port}/{token}"

            logger.info(
                f"VMRemote for {vm_uuid}: "
                f"WebMKS({host}:{port}) "
                f"-> proxy(/{token}) -> {url}")

            # 9. 返回结果
            return ZMessage(
                success=True,
                action="VMRemote",
                message=url,
                results={
                    "token": token,
                    "remote_port": remote_port,
                    "url": url,
                    "webmks_url": webmks_url,
                    "ticket": ticket
                }
            )

        except Exception as e:
            logger.error(f"获取WebMKS远程访问失败: {str(e)}")
            return ZMessage(
                success=False,
                action="VMRemote",
                message=f"获取WebMKS远程访问失败: {str(e)}")

        # 通用操作 =============================================================
        # return super().VMRemote(vm_uuid)
