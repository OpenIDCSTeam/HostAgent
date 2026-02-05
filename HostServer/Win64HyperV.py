#######################################################
# Hyper-V虚拟机管理模块
# 支持Windows Hyper-V虚拟机的创建、管理、电源控制等功能
#######################################################

import os
import shutil
import datetime
import subprocess
import traceback
from copy import deepcopy
from loguru import logger

from HostServer.BasicServer import BasicServer
from VNCConsole.VNCSManager import VNCSManager
from HostServer.Win64HyperVAPI.HyperVAPI import HyperVAPI
from MainObject.Config.HSConfig import HSConfig
from MainObject.Config.IMConfig import IMConfig
from MainObject.Config.SDConfig import SDConfig
from MainObject.Config.VMPowers import VMPowers
from MainObject.Public.HWStatus import HWStatus
from MainObject.Public.ZMessage import ZMessage
from MainObject.Config.VMConfig import VMConfig
from MainObject.Config.VMBackup import VMBackup


class HostServer(BasicServer):
    """Hyper-V宿主机服务类"""

    # ===============================================================================
    # 宿主机服务
    # ===============================================================================

    # 初始化 ########################################################################
    def __init__(self, config: HSConfig, **kwargs):
        super().__init__(config, **kwargs)
        super().__load__(**kwargs)
        # 添加变量 =================================================================
        # 初始化Hyper-V API连接
        self.hyperv_api = HyperVAPI(
            host=self.hs_config.server_addr,
            user=self.hs_config.server_user,
            password=self.hs_config.server_pass,
            port=self.hs_config.server_port if not self.hs_config == "" else 5985,
            use_ssl=False
        )

        # VNC远程控制（Hyper-V使用增强会话模式，但保留接口兼容性）
        self.vm_remote: VNCSManager | None = None

    # ===============================================================================
    # 宿主机管理
    # ===============================================================================
    # 定时任务 ######################################################################
    def Crontabs(self) -> bool:
        try:
            # 专用操作 =============================================================
            # 获取远程主机状态 =====================================================
            hw_status = self.HSStatus()

            # 保存主机状态到数据库 =================================================
            if hw_status:
                from MainObject.Server.HSStatus import HSStatus
                hs_status = HSStatus()
                hs_status.hw_status = hw_status
                self.host_set(hs_status)
                logger.debug(f"[{self.hs_config.server_name}] 远程主机状态已保存")

            # 通用操作 =============================================================
            return True
        except Exception as e:
            logger.error(f"[{self.hs_config.server_name}] 定时任务执行失败: {str(e)}")
            traceback.print_exc()
            return False

    # 获取宿主机状态 ################################################################
    def HSStatus(self) -> HWStatus:
        try:
            # 连接到Hyper-V服务器 =====================================================
            connect_result = self.hyperv_api.connect()
            if not connect_result.success:
                logger.error(f"无法连接到Hyper-V获取状态: {connect_result.message}")
                return super().HSStatus()

            # 获取远程主机状态信息 =====================================================
            host_status = self.hyperv_api.get_host_status()

            # 断开Hyper-V连接 ==========================================================
            self.hyperv_api.disconnect()

            # 解析并构建状态对象 =======================================================
            if host_status:
                hw_status = HWStatus()
                hw_status.cpu_usage = host_status.get("cpu_usage_percent", 0)
                hw_status.mem_usage = int(host_status.get("memory_used_mb", 0))
                hw_status.mem_total = int(host_status.get("memory_total_mb", 0))
                hw_status.hdd_usage = 0  # Hyper-V需要额外查询存储使用率
                hw_status.hdd_total = 0
                logger.debug(
                    f"[{self.hs_config.server_name}] 远程主机状态: "
                    f"CPU={hw_status.cpu_usage}%, "
                    f"MEM={hw_status.mem_usage}MB/{hw_status.mem_total}MB"
                )
                return hw_status
            else:
                # 未获取到状态数据处理 =================================================
                logger.warning(f"[{self.hs_config.server_name}] 未能获取到主机状态数据")
                return HWStatus()

        # 异常处理 =================================================================
        except Exception as e:
            logger.error(f"获取Hyper-V主机状态失败: {str(e)}")
            traceback.print_exc()

        # 通用操作 =================================================================
        return super().HSStatus()

    # 初始化宿主机 ##################################################################
    def HSCreate(self) -> ZMessage:
        """初始化宿主机"""
        try:
            # 专用操作 ==============================================================
            # Hyper-V不需要初始化操作，主机已经存在

            # 通用操作 ==============================================================
            return super().HSCreate()

        except Exception as e:
            logger.error(f"初始化宿主机失败: {str(e)}")
            traceback.print_exc()
            return ZMessage(success=False, action="HSCreate", message=str(e))

    # 还原宿主机 ####################################################################
    def HSDelete(self) -> ZMessage:
        """还原宿主机"""
        try:
            # 专用操作 ==============================================================
            # Hyper-V不需要还原操作

            # 通用操作 ==============================================================
            return super().HSDelete()

        except Exception as e:
            logger.error(f"还原宿主机失败: {str(e)}")
            traceback.print_exc()
            return ZMessage(success=False, action="HSDelete", message=str(e))

    # 加载宿主机 ####################################################################
    def HSLoader(self) -> ZMessage:
        """加载宿主机"""
        try:
            # 专用操作 ==============================================================
            # 测试连接到Hyper-V
            result = self.hyperv_api.connect()
            if result.success:
                self.hyperv_api.disconnect()
                logger.info(f"成功连接到Hyper-V主机: {self.hs_config.server_addr}")
            else:
                logger.error(f"无法连接到Hyper-V主机: {result.message}")
                return result
            # 通用操作 ==============================================================
            return super().HSLoader()
        except Exception as e:
            logger.error(f"加载宿主机失败: {str(e)}")
            traceback.print_exc()
            return ZMessage(success=False, action="HSLoader", message=str(e))

    # 卸载宿主机 ####################################################################
    def HSUnload(self) -> ZMessage:
        try:
            # 断开Hyper-V连接========================================================
            self.hyperv_api.disconnect()
            # 停止VNC服务
            if self.vm_remote:
                try:
                    self.vm_remote.stop()
                except Exception as e:
                    logger.warning(f"停止VNC服务失败: {str(e)}")
            # 通用操作 ==============================================================
            return super().HSUnload()
        except Exception as e:
            logger.error(f"卸载宿主机失败: {str(e)}")
            traceback.print_exc()
            return ZMessage(success=False, action="HSUnload", message=str(e))

    # ================================================================================
    # 虚拟机管理
    # ================================================================================

    # 获取虚拟机状态 #################################################################
    def VMStatus(self, vm_name: str = "", s_t: int = None,
                 e_t: int = None) -> dict[str, list[HWStatus]]:
        """获取虚拟机状态"""
        try:
            # 专用操作 ===============================================================
            # Hyper-V的虚拟机状态通过API实时获取

            # 通用操作 ===============================================================
            return super().VMStatus(vm_name, s_t, e_t)

        except Exception as e:
            logger.error(f"获取虚拟机状态失败: {str(e)}")
            traceback.print_exc()
            return {}

    # 获取虚拟机实际状态（从API）==============================================
    def VMStatusAPI(self, vm_name: str) -> str:
        """从Hyper-V API获取虚拟机实际状态"""
        try:
            connect_result = self.hyperv_api.connect()
            if not connect_result.success:
                return ""
            
            vm_info = self.hyperv_api.get_vm_info(vm_name)
            self.hyperv_api.disconnect()
            
            if vm_info:
                state = vm_info.get('State', 0)
                # 映射Hyper-V状态到中文状态
                # State: 2=Running, 3=Off, 9=Paused, 32768=Paused-Critical
                state_map = {
                    2: '运行中',
                    3: '已关机',
                    9: '已暂停',
                    32768: '已暂停'
                }
                return state_map.get(state, '未知')
        except Exception as e:
            logger.warning(f"从API获取虚拟机 {vm_name} 状态失败: {str(e)}")
            try:
                self.hyperv_api.disconnect()
            except:
                pass
        return ""

    # 扫描虚拟机 ####################################################################
    def VMDetect(self) -> ZMessage:
        """扫描虚拟机"""
        # 专用操作 =============================================================
        try:
            # 连接到Hyper-V服务器 =================================================
            connect_result = self.hyperv_api.connect()
            if not connect_result.success:
                return connect_result

            # 获取过滤前缀配置 =====================================================
            filter_prefix = self.hs_config.filter_name if self.hs_config else ""

            # 获取所有虚拟机列表 ===================================================
            vms_list = self.hyperv_api.list_vms(filter_prefix)

            # 初始化计数器 =========================================================
            scanned_count = len(vms_list)
            added_count = 0

            # 遍历处理每个虚拟机 ===================================================
            for vm_info in vms_list:
                # 提取虚拟机名称 ===================================================
                vm_name = vm_info.get("name", "")
                if not vm_name:
                    continue
                # 检查虚拟机是否已存在 =============================================
                if vm_name in self.vm_saving:
                    continue
                # 创建默认虚拟机配置对象 ===========================================
                default_vm_config = VMConfig()
                default_vm_config.vm_uuid = vm_name
                default_vm_config.cpu_num = vm_info.get("cpu", 1)
                default_vm_config.mem_num = vm_info.get("memory_mb", 1024)

                # 添加到虚拟机配置字典 =============================================
                self.vm_saving[vm_name] = default_vm_config
                added_count += 1

                # 记录扫描日志 =====================================================
                log_msg = ZMessage(
                    success=True,
                    action="VScanner",
                    message=f"发现并添加虚拟机: {vm_name}",
                    results={
                        "vm_name": vm_name,
                        "cpu": vm_info.get("cpu", 0),
                        "memory_mb": vm_info.get("memory_mb", 0),
                        "state": vm_info.get("state", "unknown")
                    }
                )
                self.push_log(log_msg)

            # 断开Hyper-V连接 =====================================================
            self.hyperv_api.disconnect()

            # 保存配置到数据库 =====================================================
            if added_count > 0:
                success = self.data_set()
                if not success:
                    return ZMessage(
                        success=False, action="VScanner",
                        message="保存扫描的虚拟机到数据库失败")

            # 返回扫描结果 =========================================================
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
            # 异常处理 =============================================================
            logger.error(f"扫描虚拟机失败: {str(e)}")
            traceback.print_exc()
            self.hyperv_api.disconnect()
            return ZMessage(success=False, action="VScanner",
                            message=f"扫描虚拟机时出错: {str(e)}")

    # 创建虚拟机 ####################################################################
    def VMCreate(self, vm_conf: VMConfig) -> ZMessage:
        """创建虚拟机"""
        logger.info(f"[{self.hs_config.server_name}] 开始创建虚拟机: {vm_conf.vm_uuid}")
        logger.info(f"  - CPU: {vm_conf.cpu_num}核, 内存: {vm_conf.mem_num}MB")
        logger.info(f"  - 网卡数量: {len(vm_conf.nic_all)}, 系统镜像: {vm_conf.os_name}")
        
        # 网络检查和IP分配 =====================================================
        vm_conf, net_result = self.NetCheck(vm_conf)
        if not net_result.success:
            logger.error(f"[{self.hs_config.server_name}] 虚拟机 {vm_conf.vm_uuid} 网络检查失败: {net_result.message}")
            return net_result

        # 绑定IP地址 ===========================================================
        self.IPBinder(vm_conf, True)
        logger.debug(f"[{self.hs_config.server_name}] 虚拟机 {vm_conf.vm_uuid} IP地址已绑定")

        # 专用操作 =============================================================
        try:
            # 连接到Hyper-V服务器 =================================================
            connect_result = self.hyperv_api.connect()
            if not connect_result.success:
                return connect_result

            # 创建虚拟机实例 =======================================================
            logger.info(f"[{self.hs_config.server_name}] 正在创建虚拟机实例: {vm_conf.vm_uuid}")
            create_result = self.hyperv_api.create_vm(vm_conf, self.hs_config)
            if not create_result.success:
                logger.error(f"[{self.hs_config.server_name}] 虚拟机实例创建失败: {create_result.message}")
                self.hyperv_api.disconnect()
                return create_result
            logger.info(f"[{self.hs_config.server_name}] 虚拟机实例创建成功: {vm_conf.vm_uuid}")

            # 安装操作系统（如果指定了镜像）=========================================
            if vm_conf.os_name:
                logger.info(f"[{self.hs_config.server_name}] 开始安装系统: {vm_conf.os_name}")
                install_result = self.VMSetups(vm_conf)
                if not install_result.success:
                    # 安装失败时清理虚拟机 =========================================
                    logger.error(f"[{self.hs_config.server_name}] 系统安装失败，清理虚拟机: {vm_conf.vm_uuid}")
                    self.hyperv_api.delete_vm(vm_conf.vm_uuid)
                    self.hyperv_api.disconnect()
                    return install_result
                logger.info(f"[{self.hs_config.server_name}] 系统安装完成: {vm_conf.os_name}")

            # 启动虚拟机 ===========================================================
            logger.info(f"[{self.hs_config.server_name}] 正在启动虚拟机: {vm_conf.vm_uuid}")
            self.hyperv_api.power_on(vm_conf.vm_uuid)

            # 断开Hyper-V连接 =====================================================
            self.hyperv_api.disconnect()

            logger.info(f"[{self.hs_config.server_name}] 虚拟机 {vm_conf.vm_uuid} 创建成功")

        except Exception as e:
            # 异常处理 =============================================================
            logger.error(f"创建虚拟机失败: {str(e)}")
            traceback.print_exc()
            self.hyperv_api.disconnect()

            # 记录失败日志 =========================================================
            hs_result = ZMessage(
                success=False, action="VMCreate",
                message=f"虚拟机创建失败: {str(e)}")
            self.logs_set(hs_result)
            return hs_result

        # 通用操作 =============================================================
        return super().VMCreate(vm_conf)

    # 安装虚拟机系统 ################################################################
    def VMSetups(self, vm_conf: VMConfig) -> ZMessage:
        """安装虚拟机系统"""
        # 专用操作 =============================================================
        try:
            # 构建镜像文件完整路径 =================================================
            image_file = os.path.join(self.hs_config.images_path, vm_conf.os_name)

            # 检查镜像文件是否存在 =================================================
            if not os.path.exists(image_file):
                return ZMessage(
                    success=False, action="VInstall",
                    message=f"镜像文件不存在: {image_file}")

            # 获取文件扩展名判断镜像类型 ===========================================
            file_ext = os.path.splitext(vm_conf.os_name)[1].lower()

            # 处理ISO镜像 ==========================================================
            if file_ext in ['.iso']:
                # 获取ISO路径 ======================================================
                iso_path = image_file

                # 挂载ISO到虚拟机 ==================================================
                attach_result = self.hyperv_api.attach_iso(vm_conf.vm_uuid, iso_path)
                if not attach_result.success:
                    return attach_result

                logger.info(f"ISO镜像 {vm_conf.os_name} 已挂载到虚拟机 {vm_conf.vm_uuid}")

            # 处理磁盘镜像 =========================================================
            elif file_ext in ['.vhdx', '.vhd']:
                # 构建虚拟机磁盘目标路径 ===========================================
                vm_path = os.path.join(self.hs_config.system_path, vm_conf.vm_uuid)
                vm_disk_path = os.path.join(vm_path, "Virtual Hard Disks", f"{vm_conf.vm_uuid}.vhdx")

                # 创建目标目录 =====================================================
                os.makedirs(os.path.dirname(vm_disk_path), exist_ok=True)

                # 复制磁盘镜像文件 =================================================
                shutil.copy(image_file, vm_disk_path)
                logger.info(f"磁盘镜像已复制到: {vm_disk_path}")

            # 返回安装成功 =========================================================
            return ZMessage(success=True, action="VInstall",
                            message="系统安装完成")

        except Exception as e:
            # 异常处理 =============================================================
            logger.error(f"安装虚拟机失败: {str(e)}")
            traceback.print_exc()
            return ZMessage(success=False, action="VInstall",
                            message=f"安装失败: {str(e)}")

    # 更新虚拟机配置 ################################################################
    def VMUpdate(self, vm_conf: VMConfig, vm_last: VMConfig) -> ZMessage:
        """更新虚拟机配置"""
        logger.info(f"[{self.hs_config.server_name}] 开始更新虚拟机配置: {vm_conf.vm_uuid}")
        logger.info(f"  - CPU: {vm_last.cpu_num} -> {vm_conf.cpu_num}核")
        logger.info(f"  - 内存: {vm_last.mem_num} -> {vm_conf.mem_num}MB")
        logger.info(f"  - 硬盘: {vm_last.hdd_num} -> {vm_conf.hdd_num}GB")
        
        # 网络检查和IP分配 =====================================================
        vm_conf, net_result = self.NetCheck(vm_conf)
        if not net_result.success:
            logger.error(f"[{self.hs_config.server_name}] 虚拟机 {vm_conf.vm_uuid} 网络检查失败: {net_result.message}")
            return net_result

        # 绑定IP地址 ===========================================================
        self.IPBinder(vm_conf, True)

        # 专用操作 =============================================================
        try:
            # 连接到Hyper-V服务器 =================================================
            connect_result = self.hyperv_api.connect()
            if not connect_result.success:
                return connect_result

            # 检查虚拟机是否存在 ===================================================
            if vm_conf.vm_uuid not in self.vm_saving:
                self.hyperv_api.disconnect()
                return ZMessage(
                    success=False, action="VMUpdate",
                    message=f"虚拟机 {vm_conf.vm_uuid} 不存在")

            # 更新虚拟机配置存储 ===================================================
            self.vm_saving[vm_conf.vm_uuid] = vm_conf

            # 关闭虚拟机以便修改配置 ===============================================
            logger.info(f"[{self.hs_config.server_name}] 关闭虚拟机以修改配置: {vm_conf.vm_uuid}")
            self.hyperv_api.power_off(vm_conf.vm_uuid, force=True)

            # 检查是否需要重装系统 =================================================
            if vm_conf.os_name != vm_last.os_name and vm_last.os_name != "":
                logger.info(f"[{self.hs_config.server_name}] 系统镜像变更: {vm_last.os_name} -> {vm_conf.os_name}")
                install_result = self.VMSetups(vm_conf)
                if not install_result.success:
                    self.hyperv_api.disconnect()
                    return install_result

            # 更新CPU和内存配置 ====================================================
            if vm_conf.cpu_num != vm_last.cpu_num or vm_conf.mem_num != vm_last.mem_num:
                logger.info(f"[{self.hs_config.server_name}] 更新CPU/内存配置: CPU={vm_conf.cpu_num}, MEM={vm_conf.mem_num}MB")
                update_result = self.hyperv_api.update_vm_config(vm_conf.vm_uuid, vm_conf)
                if not update_result.success:
                    logger.error(f"[{self.hs_config.server_name}] CPU/内存配置更新失败: {update_result.message}")
                    self.hyperv_api.disconnect()
                    return update_result
                logger.info(f"[{self.hs_config.server_name}] CPU/内存配置更新成功")

            # 检查是否需要扩容硬盘 =================================================
            if vm_conf.hdd_num > vm_last.hdd_num:
                logger.info(f"[{self.hs_config.server_name}] 开始扩容系统磁盘: {vm_last.hdd_num}GB -> {vm_conf.hdd_num}GB")
                try:
                    # 获取虚拟机主磁盘路径
                    vm_path = os.path.join(self.hs_config.system_path, vm_conf.vm_uuid)
                    vm_disk_path = os.path.join(vm_path, "Virtual Hard Disks", f"{vm_conf.vm_uuid}.vhdx")
                    
                    if os.path.exists(vm_disk_path):
                        # 使用PowerShell扩容磁盘
                        expand_size = (vm_conf.hdd_num - vm_last.hdd_num) * 1024 * 1024 * 1024  # 转换为字节
                        expand_cmd = f"Resize-VHD -Path '{vm_disk_path}' -SizeBytes {vm_conf.hdd_num * 1024 * 1024 * 1024}"
                        expand_result = self.hyperv_api._run_powershell(expand_cmd)
                        
                        if expand_result.success:
                            logger.info(f"[{self.hs_config.server_name}] 磁盘扩容成功: {vm_conf.hdd_num}GB")
                        else:
                            logger.error(f"[{self.hs_config.server_name}] 磁盘扩容失败: {expand_result.message}")
                    else:
                        logger.warning(f"[{self.hs_config.server_name}] 磁盘文件不存在，跳过扩容: {vm_disk_path}")
                except Exception as disk_err:
                    logger.error(f"[{self.hs_config.server_name}] 磁盘扩容异常: {str(disk_err)}")

            # 更新网络配置 =========================================================
            network_result = self.IPUpdate(vm_conf, vm_last)
            if not network_result.success:
                self.hyperv_api.disconnect()
                return ZMessage(
                    success=False, action="VMUpdate",
                    message=f"虚拟机 {vm_conf.vm_uuid} 网络配置更新失败: {network_result.message}")

            # 启动虚拟机 ===========================================================
            start_result = self.hyperv_api.power_on(vm_conf.vm_uuid)
            if not start_result.success:
                self.hyperv_api.disconnect()
                return ZMessage(
                    success=False, action="VMUpdate",
                    message=f"虚拟机 {vm_conf.vm_uuid} 启动失败: {start_result.message}")

            # 断开Hyper-V连接 =====================================================
            self.hyperv_api.disconnect()

        except Exception as e:
            # 异常处理 =============================================================
            logger.error(f"更新虚拟机配置失败: {str(e)}")
            traceback.print_exc()
            self.hyperv_api.disconnect()
            return ZMessage(
                success=False, action="VMUpdate",
                message=f"虚拟机配置更新失败: {str(e)}")

        # 通用操作 =============================================================
        return super().VMUpdate(vm_conf, vm_last)

    # 删除虚拟机 ####################################################################
    def VMDelete(self, vm_name: str, rm_back=True) -> ZMessage:
        """删除虚拟机"""
        logger.info(f"[{self.hs_config.server_name}] 开始删除虚拟机: {vm_name}")
        
        # 专用操作 =============================================================
        try:
            # 查询虚拟机配置 =======================================================
            vm_conf = self.VMSelect(vm_name)
            if vm_conf is None:
                logger.error(f"[{self.hs_config.server_name}] 虚拟机不存在: {vm_name}")
                return ZMessage(
                    success=False,
                    action="VMDelete",
                    message=f"虚拟机 {vm_name} 不存在")

            # 连接到Hyper-V服务器 =================================================
            connect_result = self.hyperv_api.connect()
            if not connect_result.success:
                return connect_result

            # 解除网络IP绑定 =======================================================
            logger.info(f"[{self.hs_config.server_name}] 解除虚拟机 {vm_name} 的IP绑定")
            self.IPBinder(vm_conf, False)

            # 删除虚拟机及其文件 ===================================================
            logger.info(f"[{self.hs_config.server_name}] 正在删除虚拟机及其文件: {vm_name}")
            delete_result = self.hyperv_api.delete_vm(vm_name, remove_files=True)

            # 断开Hyper-V连接 =====================================================
            self.hyperv_api.disconnect()

            # 检查删除结果 =========================================================
            if not delete_result.success:
                logger.error(f"[{self.hs_config.server_name}] 虚拟机删除失败: {delete_result.message}")
                return delete_result
            
            logger.info(f"[{self.hs_config.server_name}] 虚拟机 {vm_name} 删除成功")

        except Exception as e:
            # 异常处理 =============================================================
            logger.error(f"删除虚拟机失败: {str(e)}")
            traceback.print_exc()
            self.hyperv_api.disconnect()
            return ZMessage(
                success=False, action="VMDelete",
                message=f"删除虚拟机失败: {str(e)}")

        # 通用操作 =============================================================
        super().VMDelete(vm_name, rm_back)
        return ZMessage(success=True, action="VMDelete", message="虚拟机删除成功")

    # 虚拟机电源管理 ################################################################
    def VMPowers(self, vm_name: str, power: VMPowers) -> ZMessage:
        """虚拟机电源管理"""
        # 专用操作 =============================================================
        try:
            # 连接到Hyper-V服务器 =================================================
            connect_result = self.hyperv_api.connect()
            if not connect_result.success:
                return connect_result

            # 根据电源操作类型执行相应命令 =========================================
            if power == VMPowers.S_START:
                # 启动虚拟机 =======================================================
                hs_result = self.hyperv_api.power_on(vm_name)
            elif power == VMPowers.H_CLOSE:
                # 强制关闭虚拟机 ===================================================
                hs_result = self.hyperv_api.power_off(vm_name, force=True)
            elif power == VMPowers.A_PAUSE:
                # 暂停虚拟机 =======================================================
                hs_result = self.hyperv_api.suspend(vm_name)
            elif power == VMPowers.A_WAKED:
                # 恢复虚拟机 =======================================================
                hs_result = self.hyperv_api.resume(vm_name)
            elif power == VMPowers.H_RESET or power == VMPowers.S_RESET:
                # 重启虚拟机 =======================================================
                hs_result = self.hyperv_api.reset(vm_name)
            else:
                # 不支持的电源操作 =================================================
                hs_result = ZMessage(
                    success=False, action="VMPowers",
                    message=f"不支持的电源操作: {power}")

            # 断开Hyper-V连接 =====================================================
            self.hyperv_api.disconnect()

            # 记录操作日志 =========================================================
            self.logs_set(hs_result)

        except Exception as e:
            # 异常处理 =============================================================
            logger.error(f"虚拟机电源操作失败: {str(e)}")
            traceback.print_exc()
            self.hyperv_api.disconnect()

            # 记录失败日志 =========================================================
            hs_result = ZMessage(
                success=False, action="VMPowers",
                message=f"电源操作失败: {str(e)}")
            self.logs_set(hs_result)

        # 通用操作 =============================================================
        super().VMPowers(vm_name, power)
        return hs_result

    # 设置虚拟机密码 ################################################################
    def VMPasswd(self, vm_name: str, os_pass: str) -> ZMessage:
        """设置虚拟机密码"""
        try:
            # 检查虚拟机是否存在 ===================================================
            if vm_name not in self.vm_saving:
                logger.error(f"虚拟机 {vm_name} 不存在")
                return ZMessage(success=False, action="VMPasswd", message=f"虚拟机 {vm_name} 不存在")

            # 连接到Hyper-V服务器 =================================================
            hyper_v = HyperVAPI(
                host=self.hs_config.hs_host,
                user=self.hs_config.hs_user,
                password=self.hs_config.hs_pass
            )
            
            conn_result = hyper_v.connect()
            if not conn_result.success:
                logger.error(f"连接Hyper-V失败: {conn_result.message}")
                return ZMessage(success=False, action="VMPasswd", message=conn_result.message)

            # 获取虚拟机配置中的用户名 =============================================
            vm_config = self.vm_saving[vm_name]
            username = getattr(vm_config, 'os_user', 'Administrator')  # 默认Administrator
            
            # 设置虚拟机密码 =======================================================
            result = hyper_v.set_vm_password(vm_name, username, os_pass)
            
            # 断开Hyper-V连接 =====================================================
            hyper_v.disconnect()
            
            # 检查设置结果 =========================================================
            if result.success:
                logger.info(f"虚拟机 {vm_name} 密码设置成功")
                
                # 更新配置中的密码 =================================================
                self.vm_saving[vm_name].os_pass = os_pass
                
                # 保存配置到数据库 =================================================
                self.vm_saving.save()
                
                # 通用操作 =========================================================
                return super().VMPasswd(vm_name, os_pass)
            else:
                logger.error(f"设置虚拟机密码失败: {result.message}")
                return ZMessage(success=False, action="VMPasswd", message=result.message)

        except Exception as e:
            logger.error(f"设置虚拟机密码失败: {str(e)}")
            traceback.print_exc()
            return ZMessage(success=False, action="VMPasswd", message=str(e))

    # ============================================================================== #
    # 备份恢复
    # ============================================================================== #

    # 备份虚拟机 ####################################################################
    def VMBackup(self, vm_name: str, vm_tips: str) -> ZMessage:
        """备份虚拟机（创建快照）"""
        # 专用操作 =============================================================
        try:
            # 生成备份时间戳和名称 =================================================
            bak_time = datetime.datetime.now()
            bak_name = vm_name + "-" + bak_time.strftime("%Y%m%d%H%M%S")

            # 连接到Hyper-V服务器 =================================================
            connect_result = self.hyperv_api.connect()
            if not connect_result.success:
                return connect_result

            # 创建虚拟机快照 =======================================================
            snapshot_result = self.hyperv_api.create_snapshot(
                vm_name,
                bak_name,
                vm_tips
            )

            # 断开Hyper-V连接 =====================================================
            self.hyperv_api.disconnect()

            # 检查快照创建结果 =====================================================
            if not snapshot_result.success:
                return snapshot_result

            # 记录备份信息到配置 ===================================================
            if vm_name in self.vm_saving:
                self.vm_saving[vm_name].backups.append(
                    VMBackup(
                        backup_name=bak_name,
                        backup_time=bak_time,
                        backup_tips=vm_tips
                    )
                )
                # 保存配置到数据库 =================================================
                self.data_set()

            # 返回备份成功 =========================================================
            return ZMessage(success=True, action="VMBackup",
                            message=f"虚拟机备份成功: {bak_name}")

        except Exception as e:
            # 异常处理 =============================================================
            logger.error(f"备份虚拟机失败: {str(e)}")
            traceback.print_exc()
            self.hyperv_api.disconnect()
            return ZMessage(success=False, action="VMBackup",
                            message=f"备份失败: {str(e)}")

    # 恢复虚拟机 ####################################################################
    def Restores(self, vm_name: str, vm_back: str) -> ZMessage:
        """恢复虚拟机（恢复快照）"""
        # 专用操作 =============================================================
        try:
            # 连接到Hyper-V服务器 =================================================
            connect_result = self.hyperv_api.connect()
            if not connect_result.success:
                return connect_result

            # 恢复到指定快照 =======================================================
            restore_result = self.hyperv_api.revert_snapshot(vm_name, vm_back)

            # 断开Hyper-V连接 =====================================================
            self.hyperv_api.disconnect()

            # 检查恢复结果 =========================================================
            if not restore_result.success:
                return restore_result

            # 返回恢复成功 =========================================================
            return ZMessage(success=True, action="Restores",
                            message=f"虚拟机恢复成功: {vm_back}")

        except Exception as e:
            # 异常处理 =============================================================
            logger.error(f"恢复虚拟机失败: {str(e)}")
            traceback.print_exc()
            self.hyperv_api.disconnect()
            return ZMessage(success=False, action="Restores",
                            message=f"恢复失败: {str(e)}")

    # 加载备份列表 ##################################################################
    def LDBackup(self, vm_back: str = "") -> ZMessage:
        """加载备份列表（从快照）"""
        try:
            # 专用操作 =============================================================
            # 连接到Hyper-V服务器 =================================================
            connect_result = self.hyperv_api.connect()
            if not connect_result.success:
                return connect_result

            # 清空现有备份记录 =====================================================
            for vm_name in self.vm_saving:
                self.vm_saving[vm_name].backups = []

            # 初始化计数器 =========================================================
            bal_nums = 0

            # 遍历所有虚拟机获取快照 ===============================================
            for vm_name in self.vm_saving:
                try:
                    # 获取虚拟机快照列表 ===========================================
                    snapshots_result = self.hyperv_api.list_snapshots(vm_name)

                    # 解析快照列表 =================================================
                    if snapshots_result.success and snapshots_result.results:
                        snapshots = snapshots_result.results.get('snapshots', [])

                        # 遍历每个快照 =============================================
                        for snapshot in snapshots:
                            snapshot_name = snapshot.get('name', '')
                            snapshot_time = snapshot.get('created_time')

                            # 添加快照到备份列表 =======================================
                            if snapshot_name:
                                self.vm_saving[vm_name].backups.append(
                                    VMBackup(
                                        backup_name=snapshot_name,
                                        backup_time=snapshot_time if snapshot_time else datetime.datetime.now(),
                                        backup_tips=snapshot.get('notes', '')
                                    )
                                )
                                bal_nums += 1
                except Exception as e:
                    # 单个虚拟机快照获取失败处理 ===================================
                    logger.warning(f"获取虚拟机 {vm_name} 快照失败: {str(e)}")
                    continue

            # 断开Hyper-V连接 ======================================================
            self.hyperv_api.disconnect()

            # 保存配置到数据库 =====================================================
            self.data_set()

            # 返回加载结果 =========================================================
            return ZMessage(
                success=True,
                action="LDBackup",
                message=f"{bal_nums}个备份快照已加载")

        except Exception as e:
            # 异常处理 =============================================================
            logger.error(f"加载备份失败: {str(e)}")
            traceback.print_exc()
            self.hyperv_api.disconnect()
            return ZMessage(
                success=False, action="LDBackup",
                message=f"加载备份失败: {str(e)}")

    # 删除备份 ######################################################################
    def RMBackup(self, vm_name: str, vm_back: str = "") -> ZMessage:
        """移除备份（删除快照）"""
        try:
            # 专用操作 =============================================================
            # 从备份名称中提取虚拟机名称
            parts = vm_back.split("-")
            if len(parts) < 2:
                return ZMessage(
                    success=False, action="RMBackup",
                    message="备份名称格式不正确")

            vm_name = parts[0]

            # 连接到Hyper-V
            connect_result = self.hyperv_api.connect()
            if not connect_result.success:
                return connect_result

            # 删除快照
            delete_result = self.hyperv_api.delete_snapshot(vm_name, vm_back)

            # 断开连接
            self.hyperv_api.disconnect()

            if not delete_result.success:
                return delete_result

            # 从配置中移除备份记录
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
            logger.error(f"删除备份失败: {str(e)}")
            traceback.print_exc()
            self.hyperv_api.disconnect()
            return ZMessage(
                success=False, action="RMBackup",
                message=f"删除备份失败: {str(e)}")

    # ============================================================================== #
    # 存储管理
    # ============================================================================== #

    # 挂载虚拟硬盘 ##################################################################
    def HDDMount(self, vm_name: str, vm_imgs: SDConfig, in_flag=True) -> ZMessage:
        """挂载/卸载虚拟硬盘"""
        action_text = "挂载" if in_flag else "卸载"
        logger.info(f"[{self.hs_config.server_name}] 开始{action_text}虚拟硬盘: {vm_name} - {vm_imgs.hdd_name}")
        
        # 专用操作 =============================================================
        try:
            # 检查虚拟机是否存在 ===================================================
            if vm_name not in self.vm_saving:
                return ZMessage(
                    success=False, action="HDDMount", message="虚拟机不存在")

            # 备份原始配置 =========================================================
            old_conf = deepcopy(self.vm_saving[vm_name])

            # 连接到Hyper-V服务器 =================================================
            connect_result = self.hyperv_api.connect()
            if not connect_result.success:
                return connect_result

            # 关闭虚拟机以便操作磁盘 ===============================================
            self.hyperv_api.power_off(vm_name, force=True)

            # 执行挂载或卸载操作 ===================================================
            if in_flag:
                # 挂载磁盘操作 =====================================================
                logger.info(f"[{self.hs_config.server_name}] 正在添加磁盘: {vm_imgs.hdd_name}, 大小: {vm_imgs.hdd_size}GB")
                add_result = self.hyperv_api.add_disk(
                    vm_name,
                    vm_imgs.hdd_size,
                    vm_imgs.hdd_name
                )
                if not add_result.success:
                    logger.error(f"[{self.hs_config.server_name}] 磁盘添加失败: {add_result.message}")
                    self.hyperv_api.disconnect()
                    return add_result
                logger.info(f"[{self.hs_config.server_name}] 磁盘添加成功: {vm_imgs.hdd_name}")

                # 更新磁盘配置 =====================================================
                vm_imgs.hdd_flag = 1
                self.vm_saving[vm_name].hdd_all[vm_imgs.hdd_name] = vm_imgs
            else:
                # 卸载磁盘操作 =====================================================
                if vm_imgs.hdd_name not in self.vm_saving[vm_name].hdd_all:
                    self.hyperv_api.power_on(vm_name)
                    self.hyperv_api.disconnect()
                    return ZMessage(
                        success=False, action="HDDMount", message="磁盘不存在")

                # 从虚拟机中移除磁盘 ===============================================
                remove_result = self.hyperv_api.remove_disk(
                    vm_name,
                    vm_imgs.hdd_name
                )
                if not remove_result.success:
                    self.hyperv_api.power_on(vm_name)
                    self.hyperv_api.disconnect()
                    return remove_result

                # 更新磁盘配置状态 =================================================
                self.vm_saving[vm_name].hdd_all[vm_imgs.hdd_name].hdd_flag = 0

            # 启动虚拟机 ===========================================================
            self.hyperv_api.power_on(vm_name)

            # 断开Hyper-V连接 =====================================================
            self.hyperv_api.disconnect()

            # 保存配置到数据库 =====================================================
            self.VMUpdate(self.vm_saving[vm_name], old_conf)
            self.data_set()

            # 返回操作结果 =========================================================
            action_text = "挂载" if in_flag else "卸载"
            return ZMessage(
                success=True,
                action="HDDMount",
                message=f"磁盘{action_text}成功")

        except Exception as e:
            # 异常处理 =============================================================
            logger.error(f"磁盘操作失败: {str(e)}")
            traceback.print_exc()
            self.hyperv_api.disconnect()
            return ZMessage(
                success=False, action="HDDMount",
                message=f"磁盘操作失败: {str(e)}")

    # 挂载ISO镜像 ###################################################################
    def ISOMount(self, vm_name: str, vm_imgs: IMConfig, in_flag=True) -> ZMessage:
        """挂载/卸载ISO镜像"""
        action_text = "挂载" if in_flag else "卸载"
        logger.info(f"[{self.hs_config.server_name}] 开始{action_text}ISO镜像: {vm_name} - {vm_imgs.iso_name}")
        
        # 专用操作 ==================================================================
        try:
            # 检查虚拟机是否存在 ====================================================
            if vm_name not in self.vm_saving:
                return ZMessage(
                    success=False, action="ISOMount", message="虚拟机不存在")

            # 备份原始配置 ==========================================================
            old_conf = deepcopy(self.vm_saving[vm_name])

            # 连接到Hyper-V服务器 ===================================================
            connect_result = self.hyperv_api.connect()
            if not connect_result.success:
                return connect_result

            # 记录操作日志 ==========================================================
            logger.info(f"准备{'挂载' if in_flag else '卸载'}ISO: {vm_imgs.iso_name}")

            # 关闭虚拟机以便操作ISO =================================================
            self.hyperv_api.power_off(vm_name, force=True)

            # 执行挂载或卸载操作 ====================================================
            if in_flag:
                # 挂载ISO操作 =======================================================
                # 构建ISO文件路径 ===================================================
                iso_path = os.path.join(self.hs_config.dvdrom_path, vm_imgs.iso_file)

                # 检查ISO文件是否存在 ===============================================
                if not os.path.exists(iso_path):
                    self.hyperv_api.power_on(vm_name)
                    self.hyperv_api.disconnect()
                    return ZMessage(
                        success=False, action="ISOMount", message="ISO文件不存在")

                # 挂载ISO到虚拟机 ===================================================
                attach_result = self.hyperv_api.attach_iso(vm_name, iso_path)
                if not attach_result.success:
                    self.hyperv_api.power_on(vm_name)
                    self.hyperv_api.disconnect()
                    return attach_result

                # 检查挂载名称是否已存在 ============================================
                if vm_imgs.iso_name in self.vm_saving[vm_name].iso_all:
                    self.hyperv_api.power_on(vm_name)
                    self.hyperv_api.disconnect()
                    return ZMessage(
                        success=False, action="ISOMount", message="挂载名称已存在")

                # 保存ISO配置 =======================================================
                self.vm_saving[vm_name].iso_all[vm_imgs.iso_name] = vm_imgs
                logger.info(f"ISO挂载成功: {vm_imgs.iso_name} -> {vm_imgs.iso_file}")
            else:
                # 卸载ISO操作 =======================================================
                # 检查ISO是否存在 ===================================================
                if vm_imgs.iso_name not in self.vm_saving[vm_name].iso_all:
                    self.hyperv_api.power_on(vm_name)
                    self.hyperv_api.disconnect()
                    return ZMessage(
                        success=False, action="ISOMount", message="ISO镜像不存在")

                # 卸载ISO ===========================================================
                detach_result = self.hyperv_api.detach_iso(vm_name)
                if not detach_result.success:
                    logger.warning(f"ISO卸载警告: {detach_result.message}")

                # 删除ISO配置 =======================================================
                del self.vm_saving[vm_name].iso_all[vm_imgs.iso_name]
                logger.info(f"ISO卸载成功: {vm_imgs.iso_name}")

            # 启动虚拟机 ============================================================
            self.hyperv_api.power_on(vm_name)

            # 断开Hyper-V连接 =======================================================
            self.hyperv_api.disconnect()

            # 保存配置到数据库 ======================================================
            self.VMUpdate(self.vm_saving[vm_name], old_conf)
            self.data_set()

            # 返回操作结果 ==========================================================
            action_text = "挂载" if in_flag else "卸载"
            return ZMessage(
                success=True,
                action="ISOMount",
                message=f"ISO镜像{action_text}成功")

        except Exception as e:
            # 异常处理 ==============================================================
            logger.error(f"ISO操作失败: {str(e)}")
            traceback.print_exc()
            self.hyperv_api.disconnect()
            return ZMessage(
                success=False, action="ISOMount",
                message=f"ISO操作失败: {str(e)}")

    # 移除磁盘 ######################################################################
    def RMMounts(self, vm_name: str, vm_imgs: str) -> ZMessage:
        """
        删除虚拟机磁盘
        
        Args:
            vm_name: 虚拟机名称
            vm_imgs: 磁盘名称
            
        Returns:
            ZMessage: 操作结果消息
        """
        try:
            # 检查虚拟机是否存在 =====================================================
            if vm_name not in self.vm_saving:
                return ZMessage(
                    success=False, action="RMMounts", message="虚拟机不存在")
            
            # 检查磁盘是否存在 ======================================================
            if vm_imgs not in self.vm_saving[vm_name].hdd_all:
                return ZMessage(
                    success=False, action="RMMounts", message="虚拟盘不存在")

            # 获取虚拟磁盘数据 ======================================================
            hd_data = self.vm_saving[vm_name].hdd_all[vm_imgs]
            
            # 记录操作日志 ==========================================================
            logger.info(f"开始删除虚拟机 {vm_name} 的磁盘: {vm_imgs}")

            # 卸载虚拟磁盘 ==========================================================
            if hd_data.hdd_flag == 1:
                logger.info(f"磁盘 {vm_imgs} 已挂载，先执行卸载操作")
                unmount_result = self.HDDMount(vm_name, hd_data, False)
                if not unmount_result.success:
                    logger.error(f"磁盘卸载失败: {unmount_result.message}")
                    return unmount_result

            # 构建磁盘文件路径 ======================================================
            disk_path = hd_data.hdd_path
            if not os.path.isabs(disk_path):
                # 如果是相对路径，构建完整路径
                vm_dir = os.path.join(self.hs_config.vm_path, vm_name)
                disk_path = os.path.join(vm_dir, disk_path)
            
            # 删除物理磁盘文件 ======================================================
            if os.path.exists(disk_path):
                try:
                    logger.info(f"删除磁盘文件: {disk_path}")
                    os.remove(disk_path)
                    logger.info(f"磁盘文件删除成功: {disk_path}")
                except Exception as file_err:
                    logger.warning(f"删除磁盘文件失败: {str(file_err)}")
                    # 文件删除失败不影响配置删除，继续执行
            else:
                logger.warning(f"磁盘文件不存在，跳过删除: {disk_path}")

            # 从配置中移除磁盘 ======================================================
            self.vm_saving[vm_name].hdd_all.pop(vm_imgs)
            logger.info(f"从配置中移除磁盘: {vm_imgs}")
            
            # 保存配置到数据库 ======================================================
            self.data_set()

            # 返回成功结果 ==========================================================
            return ZMessage(
                success=True, action="RMMounts",
                message="磁盘删除成功")

        except Exception as e:
            # 异常处理 ==============================================================
            logger.error(f"删除磁盘失败: {str(e)}")
            traceback.print_exc()
            return ZMessage(
                success=False, action="RMMounts",
                message=f"删除磁盘失败: {str(e)}")

    # 查找显卡 ######################################################################
    def GPUShows(self) -> dict[str, str]:
        """
        查询GPU设备列表
        
        Returns:
            dict[str, str]: GPU设备字典，键为GPU名称，值为GPU状态
        """
        try:
            # 连接到Hyper-V服务器 ==============================================
            connect_result = self.hyperv_api.connect()
            if not connect_result.success:
                logger.error(f"[{self.hs_config.server_name}] 无法连接到Hyper-V查询GPU: {connect_result.message}")
                return {}

            # 查询GPU设备 =======================================================
            gpu_data = self.hyperv_api.get_gpu_devices()
            
            # 断开Hyper-V连接 ===================================================
            self.hyperv_api.disconnect()
            
            # 解析GPU数据并构建返回字典 =========================================
            gpu_dict = {}
            if gpu_data and "gpus" in gpu_data:
                for idx, gpu in enumerate(gpu_data["gpus"]):
                    gpu_name = gpu.get("Name", f"GPU_{idx}")
                    gpu_type = gpu.get("Type", "Unknown")
                    
                    if gpu_type == "Partitionable":
                        # GPU分区虚拟化
                        available = gpu.get("Available", 0)
                        total = gpu.get("Total", 0)
                        status = f"可用分区: {available}/{total}"
                    elif gpu_type == "DDA":
                        # 离散设备分配
                        status = gpu.get("Status", "Unknown")
                    else:
                        status = "Unknown"
                    
                    gpu_dict[gpu_name] = status
                    logger.info(f"[{self.hs_config.server_name}] 发现GPU: {gpu_name} - {status}")
            
            # 返回GPU设备字典 ===================================================
            return gpu_dict

        except Exception as e:
            # 异常处理 ==========================================================
            logger.error(f"[{self.hs_config.server_name}] 查询GPU设备失败: {str(e)}")
            logger.error(traceback.format_exc())
            return {}

    # 虚拟机截图 ####################################################################
    def VMScreen(self, vm_name: str = "") -> str:
        try:
            # 连接到Hyper-V
            connect_result = self.hyperv_api.connect()
            if not connect_result.success:
                logger.error(f"[{self.hs_config.server_name}] 无法连接到Hyper-V获取截图: {connect_result.message}")
                return ""
            # 使用PowerShell获取虚拟机截图
            # 1. 确保虚拟机正在运行
            vm_status = self.hyperv_api.get_vm_status(vm_name)
            if not vm_status.success or vm_status.results.get("status") != "Running":
                self.hyperv_api.disconnect()
                logger.warning(f"[{self.hs_config.server_name}] 虚拟机 {vm_name} 未运行，无法获取截图")
                return ""
            # 2. 生成临时文件路径
            import tempfile
            import os
            import glob
            temp_dir = tempfile.gettempdir()

            # 3. 执行PowerShell命令获取截图
            powershell_command = f"Save-VMScreenshot -Name '{vm_name}' -Path '{temp_dir}' -FileType PNG"
            if self.hs_config.server_addr not in ["localhost", "127.0.0.1", ""]:
                powershell_command += f" -ComputerName '{self.hs_config.server_addr}'"

            screenshot_result = self.hyperv_api._run_powershell(powershell_command)
            self.hyperv_api.disconnect()
            if not screenshot_result.success:
                logger.error(f"[{self.hs_config.server_name}] 获取虚拟机截图失败: {screenshot_result.message}")
                return ""
            # 4. 查找生成的截图文件（Save-VMScreenshot会自动生成带时间戳的文件名）
            screenshot_pattern = os.path.join(temp_dir, f"{vm_name}_*.png")
            screenshot_files = glob.glob(screenshot_pattern)

            if not screenshot_files:
                logger.error(f"[{self.hs_config.server_name}] 未找到截图文件: {screenshot_pattern}")
                return ""
            # 获取最新的截图文件
            screenshot_path = max(screenshot_files, key=os.path.getctime)
            # 5. 读取截图文件并转换为base64
            if os.path.exists(screenshot_path):
                with open(screenshot_path, "rb") as f:
                    import base64
                    screenshot_base64 = base64.b64encode(f.read()).decode('utf-8')

                # 6. 删除临时文件
                os.remove(screenshot_path)

                logger.info(f"[{self.hs_config.server_name}] 成功获取虚拟机 {vm_name} 截图")
                return screenshot_base64
            else:
                logger.error(f"[{self.hs_config.server_name}] 截图文件不存在: {screenshot_path}")
                return ""
        except Exception as e:
            logger.error(f"[{self.hs_config.server_name}] 获取虚拟机截图时出错: {str(e)}")
            try:
                self.hyperv_api.disconnect()
            except:
                pass
            return ""

    # 虚拟机控制台 ##################################################################
    def VMRemote(self, vm_uuid: str, ip_addr: str = "127.0.0.1") -> ZMessage:
        """获取虚拟机远程连接URL"""
        try:
            # 检查虚拟机是否存在
            if vm_uuid not in self.vm_saving:
                return ZMessage(
                    success=False,
                    action="VCRemote",
                    message=f"虚拟机 {vm_uuid} 不存在")

            # 连接到Hyper-V
            connect_result = self.hyperv_api.connect()
            if not connect_result.success:
                return ZMessage(
                    success=False,
                    action="VCRemote",
                    message=f"无法连接到Hyper-V: {connect_result.message}")

            try:
                # 获取虚拟机GUID
                get_guid_command = f"(Get-VM -Name '{vm_uuid}').Id.Guid"
                guid_result = self.hyperv_api._run_powershell(get_guid_command)

                if not guid_result.success or not guid_result.message:
                    return ZMessage(
                        success=False,
                        action="VCRemote",
                        message=f"无法获取虚拟机GUID: {guid_result.message}")

                # 解析GUID（去除前后空格和换行）
                vm_guid = guid_result.message.strip()

                # 获取密码并加密
                password = self.hs_config.server_pass

                # 使用Password51.ps1加密密码
                ps1_path = os.path.join("HostConfig", "Password51.ps1")
                encrypt_command = f"powershell -ExecutionPolicy Bypass -Command \". '{ps1_path}'; Encrypt-RDP-Password -Password \\\"{password}\\\"\""

                encrypt_result = subprocess.run(
                    encrypt_command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace'
                )

                if encrypt_result.returncode != 0:
                    logger.error(f"密码加密失败: {encrypt_result.stderr}")
                    logger.error(f"命令: {encrypt_command}")
                    return ZMessage(
                        success=False,
                        action="VCRemote",
                        message=f"密码加密失败: {encrypt_result.stderr}")

                # 提取加密后的密码哈希（去除可能的多余输出）
                password_hash = encrypt_result.stdout.strip()
                logger.info(f"密码加密原始输出: {encrypt_result.stdout}")
                logger.info(f"密码哈希: {password_hash}")

                # 构建远程连接URL
                remote_url = (
                    f"http://localhost:{self.hs_config.remote_port}/Myrtille/?"
                    f"__EVENTTARGET=&"
                    f"__EVENTARGUMENT=&"
                    f"vmGuid={vm_guid}&"
                    f"server={self.hs_config.server_addr}&"
                    f"user={self.hs_config.server_user}&"
                    f"passwordHash={password_hash}&"
                    f"width=1024&"
                    f"height=768&"
                    f"connect=Connect%21&"
                    f"vmEnhancedMode=checked"
                )

                logger.info(f"虚拟机 {vm_uuid} 远程连接URL已生成")

                return ZMessage(
                    success=True,
                    action="VCRemote",
                    message=remote_url
                )

            finally:
                # 断开连接
                self.hyperv_api.disconnect()

        except Exception as e:
            traceback.print_exc()
            logger.error(f"获取远程连接URL失败: {str(e)}")
            return ZMessage(
                success=False,
                action="VCRemote",
                message=f"获取远程连接URL失败: {str(e)}"
            )

    # 更新网络配置 ##################################################################
    def IPUpdate(self, vm_conf: VMConfig, vm_last: VMConfig) -> ZMessage:
        """更新Hyper-V虚拟机网络配置"""
        try:
            # 确保已连接到Hyper-V
            if not self.hyperv_api.session and not self.hyperv_api.is_local:
                connect_result = self.hyperv_api.connect()
                if not connect_result.success:
                    return ZMessage(
                        success=False, action="IPUpdate",
                        message=f"无法连接到Hyper-V: {connect_result.message}")

            vm_name = vm_conf.vm_uuid

            # 获取当前网络适配器列表（用于对比）
            existing_adapters = []
            if vm_last and vm_last.nic_all:
                existing_adapters = list(vm_last.nic_all.keys())

            # 获取新配置的网络适配器列表
            new_adapters = []
            if vm_conf.nic_all:
                new_adapters = list(vm_conf.nic_all.keys())

            all_success = True
            error_message = ""

            # 删除不再需要的网络适配器
            for nic_name in existing_adapters:
                if nic_name not in new_adapters:
                    # 删除该网络适配器
                    adapter_result = self.hyperv_api.remove_network_adapter(vm_name, nic_name)
                    if not adapter_result.success:
                        all_success = False
                        if not error_message:
                            error_message = f"删除网络适配器 {nic_name} 失败: {adapter_result.message}"
                        logger.warning(f"删除网络适配器 {nic_name} 失败: {adapter_result.message}")

            # 添加或更新网络适配器
            for nic_name in new_adapters:
                nic_data = vm_conf.nic_all[nic_name]

                # 根据网卡类型确定虚拟交换机
                nic_switch = None
                if nic_data.nic_type == "nat":
                    nic_switch = self.hs_config.network_nat if self.hs_config.network_nat else None
                elif nic_data.nic_type == "pub":
                    nic_switch = self.hs_config.network_pub if self.hs_config.network_pub else None

                if not nic_switch:
                    all_success = False
                    if not error_message:
                        error_message = f"网卡 {nic_name} 未找到对应的虚拟交换机配置 (nic_type={nic_data.nic_type})"
                    logger.warning(f"网卡 {nic_name} 未找到对应的虚拟交换机配置 (nic_type={nic_data.nic_type})")
                    continue

                # 检查是新增还是更新
                if nic_name in existing_adapters:
                    # 更新现有网络适配器
                    adapter_result = self.hyperv_api.set_network_adapter(
                        vm_name,
                        nic_switch,
                        nic_data.mac_addr,
                        nic_name
                    )
                    if adapter_result.success:
                        logger.info(f"网络适配器 {nic_name} 更新成功")
                    else:
                        all_success = False
                        if not error_message:
                            error_message = f"网络适配器 {nic_name} 更新失败: {adapter_result.message}"
                        logger.warning(f"网络适配器 {nic_name} 更新失败: {adapter_result.message}")
                else:
                    # 添加新的网络适配器
                    adapter_result = self.hyperv_api.add_network_adapter(
                        vm_name,
                        nic_switch,
                        nic_data.mac_addr,
                        nic_name
                    )
                    if adapter_result.success:
                        logger.info(f"网络适配器 {nic_name} 添加成功")
                    else:
                        all_success = False
                        if not error_message:
                            error_message = f"网络适配器 {nic_name} 添加失败: {adapter_result.message}"
                        logger.warning(f"网络适配器 {nic_name} 添加失败: {adapter_result.message}")

            if all_success:
                return ZMessage(success=True, action="IPUpdate", message="网络配置更新成功")
            else:
                return ZMessage(success=False, action="IPUpdate", message=f"网络配置更新失败: {error_message}")

        except Exception as e:
            logger.error(f"更新网络配置失败: {str(e)}")
            traceback.print_exc()
            return ZMessage(success=False, action="IPUpdate", message=f"网络配置更新失败: {str(e)}")
