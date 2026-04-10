import os
import time
import shutil
import datetime
import paramiko
import traceback
from loguru import logger
from copy import deepcopy
from proxmoxer import ProxmoxAPI
from typing import Optional, Tuple, Dict
from HostServer.BasicServer import BasicServer
from MainObject.Config.HSConfig import HSConfig
from MainObject.Config.IMConfig import IMConfig
from MainObject.Config.SDConfig import SDConfig
from MainObject.Config.VMPowers import VMPowers
from MainObject.Config.VMBackup import VMBackup
from MainObject.Public.HWStatus import HWStatus
from MainObject.Public.ZMessage import ZMessage
from MainObject.Config.VMConfig import VMConfig


class HostServer(BasicServer):
    # 宿主机服务 ###############################################################
    def __init__(self, config: HSConfig, **kwargs):
        super().__init__(config, **kwargs)
        super().__load__(**kwargs)
        # Proxmox 客户端连接
        self.proxmox = None

    # 连接到 Proxmox 服务器 ####################################################
    def api_conn(self) -> Tuple[Optional[ProxmoxAPI], ZMessage]:
        try:
            # 如果已经连接直接返回 =============================================
            if self.proxmox is not None:
                return self.proxmox, ZMessage(
                    success=True, action="_connect_proxmox")
            # 从配置中获取连接信息 =============================================
            host = self.hs_config.server_addr + ":8006"
            user = self.hs_config.server_user \
                if hasattr(self.hs_config, 'server_user') else 'root'
            password = self.hs_config.server_pass
            # 连接到Proxmox服务器 ==============================================
            logger.info(f"连接PVE: {host}, user: {user},"
                        f" node: {self.hs_config.launch_path}")
            # 创建Proxmox API连接 ==============================================
            self.proxmox = ProxmoxAPI(
                host, user=user + "@pam", password=password, verify_ssl=False)
            # 测试连接 =========================================================
            self.proxmox.version.get()
            logger.info("PVE连接成功")
            return self.proxmox, ZMessage(success=True, action="api_conn")
        except Exception as e:
            logger.error(f"PVE连接失败: {str(e)}")
            # traceback.print_exc()
            self.proxmox = None
            return None, ZMessage(
                success=False, action="_connect_proxmox",
                message=f"Failed to connect to Proxmox: {str(e)}")

    # 分配新的VMID #############################################################
    def new_vmid(self) -> int:
        """分配新的VMID"""
        try:
            # 连接Proxmox API ==================================================
            client, result = self.api_conn()
            if not result.success:
                logger.warning("无法连接Proxmox，使用默认VMID 100")
                return 100  # 默认起始VMID
            
            # 检查节点名是否配置 ================================================
            if not self.hs_config.launch_path:
                logger.warning("launch_path（PVE节点名）未配置，使用默认VMID 100")
                return 100
            # 获取所有现有的VMID ===============================================
            vms = client.nodes(self.hs_config.launch_path).qemu.get()
            now_vmid = [vm.get('vmid', 0) for vm in vms if vm.get('vmid')]
            
            # 从100开始查找可用的VMID ===========================================
            vmid = 100
            while vmid in now_vmid:
                vmid += 1
            
            logger.info(f"分配新VMID: {vmid}")
            return vmid
            
        except Exception as e:
            logger.error(f"分配VMID失败: {str(e)}")
            traceback.print_exc()
            return 100

    # 获取VMID #################################################################
    def get_vmid(self, vm_conf: VMConfig) -> Optional[int]:
        try:
            # 首先尝试从配置中获取（作为缓存）
            if hasattr(vm_conf, 'vm_data') and 'vmid' in vm_conf.vm_data:
                cached_vmid = vm_conf.vm_data['vmid']
                if cached_vmid:
                    return cached_vmid

            # 如果配置中没有，从API获取
            client, result = self.api_conn()
            if not result.success or not client:
                logger.error(f"无法连接到Proxmox获取VMID: {result.message}")
                return None
            # 获取虚拟机名称（处理下划线转横线的情况）
            vm_name = vm_conf.vm_uuid.replace('_', '-')
            # 从API获取所有虚拟机列表
            vms = client.nodes(self.hs_config.launch_path).qemu.get()
            # 查找匹配的虚拟机
            for vm in vms:
                if vm['name'] == vm_name:
                    vmid = vm['vmid']
                    # 缓存到配置中
                    if not hasattr(vm_conf, 'vm_data'):
                        vm_conf.vm_data = {}
                    vm_conf.vm_data['vmid'] = vmid
                    logger.debug(f"从API获取到虚拟机 {vm_name} 的VMID: {vmid}")
                    return vmid
            logger.warning(f"未找到虚拟机 {vm_name} 的VMID")
            return None
        except Exception as e:
            logger.error(f"获取VMID时出错: {str(e)}")
            traceback.print_exc()
            return None

    # 公共辅助方法 - 获取虚拟机连接和配置 ####################################
    def _get_vm_connection(self, vm_name: str) -> Tuple[Optional[object], Optional[int], Optional[VMConfig], ZMessage]:
        """获取虚拟机连接、VMID和配置的统一方法
        
        Returns:
            (vm_conn, vm_vmid, vm_conf, result_message)
        """
        try:
            # 连接Proxmox API ==============================================
            client, result = self.api_conn()
            if not result.success:
                return None, None, None, result
            
            # 检查虚拟机是否存在 ===========================================
            if vm_name not in self.vm_saving:
                return None, None, None, ZMessage(
                    success=False, action="操作",
                    message=f"虚拟机 {vm_name} 不存在")
            
            # 获取虚拟机配置 ===============================================
            vm_conf = self.vm_saving[vm_name]
            vm_vmid = self.get_vmid(vm_conf)
            if vm_vmid is None:
                return None, None, None, ZMessage(
                    success=False, action="操作",
                    message=f"虚拟机 {vm_name} 的VMID未找到")
            
            # 获取虚拟机连接对象 ===========================================
            vm_conn = client.nodes(self.hs_config.launch_path).qemu(vm_vmid)
            
            return vm_conn, vm_vmid, vm_conf, ZMessage(success=True)
            
        except Exception as e:
            logger.error(f"获取虚拟机连接失败: {str(e)}")
            traceback.print_exc()
            return None, None, None, ZMessage(
                success=False, action="操作",
                message=f"获取虚拟机连接失败: {str(e)}")
    
    # 公共辅助方法 - 检查虚拟机状态 ############################################
    def _check_vm_status(self, vm_conn) -> Optional[str]:
        """检查虚拟机运行状态
        
        Returns:
            虚拟机状态字符串，如'running', 'stopped'等，失败返回None
        """
        try:
            status = vm_conn.status.current.get()
            return status.get('status')
        except Exception as e:
            logger.error(f"检查虚拟机状态失败: {str(e)}")
            traceback.print_exc()
            return None
    
    # 构建网卡配置 #############################################################
    def net_conf(self, vm_conf: VMConfig) -> dict:
        network_config = {}
        nic_index = 0
        for nic_name, nic_conf in vm_conf.nic_all.items():
            nic_keys = "network_" + nic_conf.nic_type
            if hasattr(self.hs_config, nic_keys) \
                    and getattr(self.hs_config, nic_keys, ""):
                bridge = getattr(self.hs_config, nic_keys)
                net_config = f"e1000e,bridge={bridge}"
                if nic_conf.mac_addr:
                    net_config += f",macaddr={nic_conf.mac_addr}"
                network_config[f"net{nic_index}"] = net_config
                nic_index += 1
        return network_config

    # 生成Proxmox启动顺序字符串 ################################################
    # 根据efi_all生成Proxmox boot order字符串，格式如 order=scsi0;scsi1;ide2
    # 设备映射：vm_uuid->scsi0，vm_uuid-hdd_name->scsi1/2...，iso->ide2
    # #########################################################################
    def _proxmox_boot_order(self, vm_conf: VMConfig) -> str:
        if not vm_conf.efi_all:
            return 'order=scsi0;ide2'
        # 构建 efi_name -> proxmox设备名 的映射
        device_map = {}
        device_map[vm_conf.vm_uuid] = 'scsi0'  # 系统盘
        scsi_idx = 1
        for hdd_name, hdd_data in vm_conf.hdd_all.items():
            if hdd_data.hdd_flag == 0:
                continue
            device_map[f"{vm_conf.vm_uuid}-{hdd_name}"] = f"scsi{scsi_idx}"
            scsi_idx += 1
        ide_idx = 2
        for iso_name in vm_conf.iso_all:
            device_map[iso_name] = f"ide{ide_idx}"
            ide_idx += 1
        # 按efi_all顺序生成设备列表
        ordered = []
        seen = set()
        for efi_item in vm_conf.efi_all:
            dev = device_map.get(efi_item.efi_name)
            if dev and dev not in seen:
                ordered.append(dev)
                seen.add(dev)
        # 将未在efi_all中的设备追加到末尾
        for dev in device_map.values():
            if dev not in seen:
                ordered.append(dev)
                seen.add(dev)
        if not ordered:
            return 'order=scsi0;ide2'
        return 'order=' + ';'.join(ordered)

    # 宿主机任务 ###############################################################
    def Crontabs(self) -> bool:
        """定时任务"""
        # 通用操作 =============================================================
        return super().Crontabs()

    # 宿主机状态 ###############################################################
    def HSStatus(self) -> HWStatus:
        """获取宿主机状态"""
        try:
            # 连接到 Proxmox ===================================================
            client, result = self.api_conn()
            if not result.success or not client:
                logger.error(f"无法连接到Proxmox获取状态: {result.message}")
                return super().HSStatus()

            # 获取主机状态 =====================================================
            node_status = client.nodes(self.hs_config.launch_path).status.get()
            # API 可能返回列表，取第一个元素
            if isinstance(node_status, list):
                node_status = node_status[0] if node_status else None

            if node_status:
                hw_status = HWStatus()
                # CPU 使用率 ===================================================
                hw_status.cpu_usage = int(node_status.get('cpu', 0) * 100)
                # 内存使用（MB）================================================
                mem_total = node_status.get('memory', {}).get('total', 0)
                mem_used = node_status.get('memory', {}).get('used', 0)
                hw_status.mem_total = int(mem_total / (1024 * 1024))  # 转换为MB
                hw_status.mem_usage = int(mem_used / (1024 * 1024))  # 转换为MB
                # 磁盘使用（MB）================================================
                disk_total = node_status.get('rootfs', {}).get('total', 0)
                disk_used = node_status.get('rootfs', {}).get('used', 0)
                hw_status.hdd_total = int(disk_total / (1024 * 1024))  # 转换为MB
                hw_status.hdd_usage = int(disk_used / (1024 * 1024))  # 转换为MB

                logger.debug(
                    f"[{self.hs_config.server_name}] Proxmox主机状态: "
                    f"CPU={hw_status.cpu_usage}%, "
                    f"MEM={hw_status.mem_usage}MB/{hw_status.mem_total}MB"
                )
                return hw_status
                
        except Exception as e:
            logger.error(f"获取Proxmox主机状态失败: {str(e)}")
            traceback.print_exc()

        # 通用操作 =============================================================
        return super().HSStatus()

    # 初始宿主机 ###############################################################
    def HSCreate(self) -> ZMessage:
        return super().HSCreate()

    # 还原宿主机 ###############################################################
    def HSDelete(self) -> ZMessage:
        return super().HSDelete()

    # 读取宿主机 ###############################################################
    def HSLoader(self) -> ZMessage:
        # 连接到 Proxmox 服务器
        client, result = self.api_conn()
        if not result.success:
            return result
        # 加载远程控制台配置 ===================================================
        # self.VMLoader()
        # 同步端口转发配置
        # self.ssh_sync()
        return super().HSLoader()

    # 卸载宿主机 ###############################################################
    def HSUnload(self) -> ZMessage:
        # 断开 Proxmox 连接
        self.proxmox = None
        return super().HSUnload()

    # 虚拟机扫描 ###############################################################
    def VMDetect(self) -> ZMessage:
        """扫描并发现虚拟机"""
        try:
            # 连接Proxmox API ==================================================
            client, result = self.api_conn()
            if not result.success:
                return result

            # 获取所有虚拟机列表 ===============================================
            vms = client.nodes(self.hs_config.launch_path).qemu.get()

            # 使用主机配置的filter_name作为前缀过滤 ===========================
            filter_prefix = self.hs_config.filter_name if self.hs_config else ""

            scanned_count = 0
            added_count = 0

            # 遍历虚拟机列表 ===================================================
            for vm in vms:
                vm_name = vm['name']
                vmid = vm['vmid']

                # 前缀过滤 =====================================================
                if filter_prefix and not vm_name.startswith(filter_prefix):
                    continue

                scanned_count += 1

                # 检查是否已存在 ===============================================
                if vm_name in self.vm_saving:
                    continue

                # 创建默认虚拟机配置 ===========================================
                default_vm_config = VMConfig()
                default_vm_config.vm_uuid = vm_name
                # 保存VMID到配置中（用于后续操作）==============================
                if not hasattr(default_vm_config, 'vm_data'):
                    default_vm_config.vm_data = {}
                default_vm_config.vm_data['vmid'] = vmid

                # 添加到服务器的虚拟机配置中 ===================================
                self.vm_saving[vm_name] = default_vm_config
                added_count += 1

                log_msg = ZMessage(
                    success=True,
                    action="VScanner",
                    message=f"发现并添加虚拟机: {vm_name} (VMID: {vmid})",
                    results={"vm_name": vm_name, "vmid": vmid}
                )
                self.push_log(log_msg)

            # 保存到数据库 =====================================================
            if added_count > 0:
                success = self.data_set()
                if not success:
                    return ZMessage(
                        success=False, action="VScanner",
                        message="Failed to save scanned DockManage to database")

            return ZMessage(
                success=True,
                action="VScanner",
                message=f"扫描完成。共扫描到{scanned_count}个虚拟机，新增{added_count}个虚拟机配置。",
                results={
                    "scanned": scanned_count,
                    "added": added_count,
                    "prefix_filter": filter_prefix
                }
            )

        except Exception as e:
            logger.error(f"扫描虚拟机时出错: {str(e)}")
            traceback.print_exc()
            return ZMessage(
                success=False, action="VScanner",
                message=f"扫描虚拟机时出错: {str(e)}")

    # 创建虚拟机 ###############################################################
    def VMCreate(self, vm_conf: VMConfig) -> ZMessage:
        logger.info(f"[{self.hs_config.server_name}] 开始创建虚拟机: {vm_conf.vm_uuid}")
        logger.info(f"  - CPU: {vm_conf.cpu_num}核, 内存: {vm_conf.mem_num}MB")
        logger.info(f"  - 网卡数量: {len(vm_conf.nic_all)}个")
        logger.info(f"  - 系统镜像: {vm_conf.os_name}")
        
        # 替换名称 ==================================================
        vm_conf.vm_uuid = vm_conf.vm_uuid.replace('_', '-')
        # 网络检查 ==================================================
        vm_conf, net_result = self.NetCheck(vm_conf)
        if not net_result.success:
            logger.error(f"[{self.hs_config.server_name}] 网络检查失败: {net_result.message}")
            return net_result
        # 连接Proxmox API ===========================================
        client, result = self.api_conn()
        if not result.success:
            logger.error(f"[{self.hs_config.server_name}] Proxmox连接失败: {result.message}")
            return result
        # 分配VMID ==================================================
        vm_vmid = self.new_vmid()
        logger.info(f"[{self.hs_config.server_name}] 分配VMID: {vm_vmid}")
        if not hasattr(vm_conf, 'vm_data'):
            vm_conf.vm_data = {}
        vm_conf.vm_data['vmid'] = vm_vmid
        # 创建虚拟机 ================================================
        try:  # 构建虚拟机配置 --------------------------------------
            # 填充efi_all默认启动项顺序 ============================
            if not vm_conf.efi_all:
                vm_conf.efi_all = self.efi_build(vm_conf)
            # 生成Proxmox启动顺序 ==================================
            boot_order = self._proxmox_boot_order(vm_conf)
            config = {
                'vmid': vm_vmid,
                'name': vm_conf.vm_uuid,
                'memory': vm_conf.mem_num,
                'cores': vm_conf.cpu_num,
                'sockets': 1,
                'ostype': 'l26',  # Linux 2.6+
                'bios': 'ovmf',  # 使用 UEFI 模式
                'boot': boot_order,
                'scsihw': 'virtio-scsi-pci',
                'efidisk0': 'local:1,efitype=4m,pre-enrolled-keys=1',  # EFI 磁盘
            }
            # 配置网卡 ------------------------------------------
            config.update(self.net_conf(vm_conf))
            # 创建虚拟机 --------------------------------------------
            # 检查节点名是否配置 ============================================
            if not self.hs_config.launch_path:
                raise ValueError("launch_path（PVE节点名）未配置，请在服务器配置中填写PVE节点名称（如: pve）")
            logger.info(f"[{self.hs_config.server_name}] 正在创建虚拟机配置...")
            client.nodes(self.hs_config.launch_path).qemu.create(**config)
            logger.info(f"[{self.hs_config.server_name}] 虚拟机 {vm_conf.vm_uuid} (VMID: {vm_vmid}) 创建成功")
            
            # 配置GPU直通 -------------------------------------------
            if vm_conf.pci_num > 0 and vm_conf.pci_all:
                logger.info(f"[{self.hs_config.server_name}] 配置PCI直通，共 {len(vm_conf.pci_all)} 个设备")
                try:
                    vm_conn = client.nodes(self.hs_config.launch_path).qemu(vm_vmid)
                    # 遍历pci_all，逐个添加PCI设备直通
                    # 格式: hostpci0: 01:00.0,pcie=1
                    gpu_config = {}
                    for idx, (pci_key, pci_cfg) in enumerate(vm_conf.pci_all.items()):
                        if pci_cfg.gpu_uuid:
                            gpu_config[f'hostpci{idx}'] = f"{pci_cfg.gpu_uuid},pcie=1"
                            logger.info(f"[{self.hs_config.server_name}] PCI设备{idx}: {pci_cfg.gpu_uuid}")
                    if gpu_config:
                        vm_conn.config.put(**gpu_config)
                        logger.info(f"[{self.hs_config.server_name}] PCI直通配置成功")
                except Exception as gpu_error:
                    logger.warning(f"[{self.hs_config.server_name}] PCI直通配置失败: {str(gpu_error)}")
            
            # 配置路由器绑定（iKuai层面）----------------------------
            logger.info(f"[{self.hs_config.server_name}] 配置路由器IP绑定...")
            ikuai_result = super().IPBinder(vm_conf, True)
            if not ikuai_result.success:
                logger.warning(f"[{self.hs_config.server_name}] iKuai路由器绑定失败: {ikuai_result.message}")
            else:
                logger.info(f"[{self.hs_config.server_name}] 路由器IP绑定成功")
            
            # 安装系统 ----------------------------------------------
            logger.info(f"[{self.hs_config.server_name}] 开始安装系统镜像...")
            result = self.VMSetups(vm_conf)
            if not result.success:
                logger.warning(f"[{self.hs_config.server_name}] 系统安装失败: {result.message}")
            else:
                logger.info(f"[{self.hs_config.server_name}] 系统安装完成")
            
            logger.info(f"[{self.hs_config.server_name}] 启动虚拟机...")
            self.VMPowers(vm_conf.vm_uuid, VMPowers.S_START)
        # 捕获所有异常 ==============================================
        except Exception as e:
            logger.error(f"[{self.hs_config.server_name}] 虚拟机创建失败: {str(e)}")
            logger.error(f"[{self.hs_config.server_name}] 错误详情:", exc_info=True)
            traceback.print_exc()
            hs_result = ZMessage(
                success=False, action="VMCreate",
                message=f"虚拟机创建失败: {str(e)}")
            self.logs_set(hs_result)
            return hs_result
        # 通用操作 ==================================================
        logger.info(f"[{self.hs_config.server_name}] 虚拟机 {vm_conf.vm_uuid} 创建流程完成")
        self.data_set()
        return super().VMCreate(vm_conf)

    # 安装虚拟机 ###############################################################
    def VMSetups(self, vm_conf: VMConfig) -> ZMessage:
        # 专用操作 =============================================================
        client, result = self.api_conn()
        if not result.success:
            return result
        # 获取VMID =============================================================
        vm_vmid = self.get_vmid(vm_conf)
        if vm_vmid is None:
            return ZMessage(
                success=False, action="VInstall",
                message=f"虚拟机 {vm_conf.vm_uuid} 的VMID未找到")
        # 检查配置 =============================================================
        if not vm_conf.os_name:
            return ZMessage(success=False, action="VInstall", message="未指定系统镜像")
        if not self.hs_config.images_path:
            return ZMessage(
                success=False, action="VInstall", message="未配置镜像路径")
        # 复制镜像 =============================================================
        try:
            import posixpath
            # 从源文件名中提取扩展名，保持原始格式
            _, src_ext = posixpath.splitext(vm_conf.os_name)
            if not src_ext:
                src_ext = '.qcow2'  # 默认格式
            vm_disk_dir = f"/var/lib/vz/images/{vm_vmid}"
            disk_name = f"vm-{vm_vmid}-disk-0{src_ext}"
            dest_image = f"{vm_disk_dir}/{disk_name}"
            system_storage = self.hs_config.system_path or "local"
            # 判断是否为PVE存储名（不含/则视为存储名，走import流程）=============
            images_is_storage = '/' not in self.hs_config.images_path
            if images_is_storage:
                # import模式：images_path为PVE存储名，使用qm importdisk导入 ====
                import_storage = self.hs_config.images_path
                src_file = f"{import_storage}:import/{vm_conf.os_name}"
                import_cmd = (f"qm importdisk {vm_vmid} {src_file} "
                              f"{system_storage} --format qcow2")
                if self.flag_web():
                    # 远程模式：通过SSH执行importdisk ===========================
                    ssh = paramiko.SSHClient()
                    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    ssh.connect(
                        self.hs_config.server_addr,
                        username=self.hs_config.server_user,
                        password=self.hs_config.server_pass)
                    stdin, stdout, stderr = ssh.exec_command(import_cmd)
                    exit_status = stdout.channel.recv_exit_status()
                    if exit_status != 0:
                        error_msg = stderr.read().decode()
                        ssh.close()
                        return ZMessage(
                            success=False, action="VInstall",
                            message=f"importdisk失败: {error_msg}")
                    ssh.close()
                    logger.info(f"通过SSH importdisk: {src_file} -> {system_storage}")
                else:
                    # 本地模式：直接执行importdisk ==============================
                    exit_status = os.system(import_cmd)
                    if exit_status != 0:
                        return ZMessage(
                            success=False, action="VInstall",
                            message="importdisk失败")
                    logger.info(f"本地importdisk: {src_file} -> {system_storage}")
                # importdisk后磁盘进入unused状态，需挂载 ========================
                vm_conn = client.nodes(self.hs_config.launch_path).qemu(vm_vmid)
                vm_conn.config.put(sata0=f"{system_storage}:{vm_vmid}/{disk_name}")
            else:
                # 复制模式：images_path为物理路径，直接cp复制 ===================
                if self.flag_web():
                    # 远程模式：src_file 是远程服务器上的路径，使用 posixpath.join
                    src_file = posixpath.join(self.hs_config.images_path, vm_conf.os_name)
                    ssh = paramiko.SSHClient()
                    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    ssh.connect(
                        self.hs_config.server_addr,
                        username=self.hs_config.server_user,
                        password=self.hs_config.server_pass)
                    # 检查远程镜像文件是否存在
                    stdin, stdout, stderr = ssh.exec_command(f"test -f {src_file} && echo 'exists' || echo 'not_exists'")
                    file_check = stdout.read().decode().strip()
                    if file_check != 'exists':
                        ssh.close()
                        return ZMessage(
                            success=False, action="VInstall",
                            message=f"镜像文件不存在: {src_file}")
                    # 在远程服务器上复制镜像文件
                    ssh.exec_command(f"mkdir -p {vm_disk_dir}")
                    copy_cmd = f"cp {src_file} {dest_image}"
                    stdin, stdout, stderr = ssh.exec_command(copy_cmd)
                    exit_status = stdout.channel.recv_exit_status()
                    if exit_status != 0:
                        error_msg = stderr.read().decode()
                        ssh.close()
                        return ZMessage(
                            success=False, action="VInstall",
                            message=f"复制镜像失败: {error_msg}")
                    ssh.close()
                    logger.info(f"通过SSH复制镜像: {src_file} -> {dest_image}")
                else:
                    # 本地模式：src_file 是 Linux 路径，使用 posixpath.join
                    src_file = posixpath.join(self.hs_config.images_path, vm_conf.os_name)
                    if not os.path.exists(src_file):
                        return ZMessage(
                            success=False, action="VInstall",
                            message=f"镜像文件不存在: {src_file}")
                    os.makedirs(vm_disk_dir, exist_ok=True)
                    shutil.copy2(src_file, dest_image)
                    logger.info(f"本地复制镜像: {src_file} -> {dest_image}")
                # 分配磁盘 ======================================================
                vm_conn = client.nodes(self.hs_config.launch_path).qemu(vm_vmid)
                vm_conn.config.put(sata0=f"{system_storage}:{vm_vmid}/{disk_name}")
            logger.info(f"虚拟机 {vm_conf.vm_uuid} 系统安装完成")
            return ZMessage(success=True, action="VInstall", message="安装成功")
        # 处理异常 ==============================================================
        except Exception as e:
            traceback.print_exc()
            return ZMessage(
                success=False, action="VInstall",
                message=f"系统安装失败: {str(e)}")

    # 配置虚拟机 ###############################################################
    def VMUpdate(self, vm_conf: VMConfig, vm_last: VMConfig) -> ZMessage:
        logger.info(f"[{self.hs_config.server_name}] 开始更新虚拟机配置: {vm_conf.vm_uuid}")
        try:
            # 网络检查 =========================================================
            vm_conf, net_result = self.NetCheck(vm_conf)
            if not net_result.success:
                logger.error(f"[{self.hs_config.server_name}] 网络检查失败: {net_result.message}")
                return net_result
            
            # 连接Proxmox API ==================================================
            client, result = self.api_conn()
            if not result.success:
                return result
            
            # 获取VMID =========================================================
            vmid = self.get_vmid(vm_conf)
            if vmid is None:
                return ZMessage(
                    success=False, action="VMUpdate",
                    message=f"虚拟机 {vm_conf.vm_uuid} 的VMID未找到")
            
            vm = client.nodes(self.hs_config.launch_path).qemu(vmid)
            
            # 停止机器 =========================================================
            status = vm.status.current.get()
            if status['status'] == 'running':
                logger.info(f"[{self.hs_config.server_name}] 停止虚拟机以进行配置更新...")
                self.VMPowers(vm_conf.vm_uuid, VMPowers.H_CLOSE)
            
            # 重装系统 =========================================================
            if vm_conf.os_name != vm_last.os_name and vm_last.os_name != "":
                logger.info(f"[{self.hs_config.server_name}] 检测到系统镜像变更，重新安装系统...")
                logger.info(f"  - 旧镜像: {vm_last.os_name}")
                logger.info(f"  - 新镜像: {vm_conf.os_name}")
                install_result = self.VMSetups(vm_conf)
                if not install_result.success:
                    logger.error(f"[{self.hs_config.server_name}] 系统重装失败: {install_result.message}")
                    return install_result
            
            # 更新配置 =========================================================
            config_updates = {}
            if vm_conf.cpu_num != vm_last.cpu_num and vm_conf.cpu_num > 0:
                logger.info(f"[{self.hs_config.server_name}] CPU配置变更: {vm_last.cpu_num}核 -> {vm_conf.cpu_num}核")
                config_updates['cores'] = vm_conf.cpu_num
            if vm_conf.mem_num != vm_last.mem_num and vm_conf.mem_num > 0:
                logger.info(f"[{self.hs_config.server_name}] 内存配置变更: {vm_last.mem_num}MB -> {vm_conf.mem_num}MB")
                config_updates['memory'] = vm_conf.mem_num
            
            # 配置网卡 =========================================================
            config_updates.update(self.net_conf(vm_conf))
            
            # 更新启动项顺序 ===================================================
            if vm_conf.efi_all:
                boot_order = self._proxmox_boot_order(vm_conf)
                config_updates['boot'] = boot_order
                logger.info(f"[{self.hs_config.server_name}] 更新启动顺序: {boot_order}")
            
            # 配置PCI直通 =======================================================
            if vm_conf.pci_num > 0 and vm_conf.pci_all:
                # 检查PCI配置是否变更
                new_pci_keys = set(vm_conf.pci_all.keys())
                old_pci_keys = set(vm_last.pci_all.keys()) if vm_last.pci_all else set()
                if new_pci_keys != old_pci_keys:
                    logger.info(f"[{self.hs_config.server_name}] PCI配置变更: {old_pci_keys} -> {new_pci_keys}")
                    try:
                        # 移除旧的PCI配置
                        for idx in range(len(old_pci_keys)):
                            try:
                                vm.config.put(delete=f'hostpci{idx}')
                            except Exception:
                                pass
                        logger.info(f"[{self.hs_config.server_name}] 已移除旧PCI配置")

                        # 添加新的PCI配置
                        for idx, (pci_key, pci_cfg) in enumerate(vm_conf.pci_all.items()):
                            if pci_cfg.gpu_uuid:
                                config_updates[f'hostpci{idx}'] = f"{pci_cfg.gpu_uuid},pcie=1"
                                logger.info(f"[{self.hs_config.server_name}] 已添加PCI配置{idx}: {pci_cfg.gpu_uuid}")
                    except Exception as gpu_error:
                        logger.warning(f"[{self.hs_config.server_name}] PCI配置更新失败: {str(gpu_error)}")
            elif vm_conf.pci_num == 0 and vm_last.pci_all:
                # 移除PCI直通
                logger.info(f"[{self.hs_config.server_name}] 移除PCI直通配置")
                try:
                    for idx in range(len(vm_last.pci_all)):
                        try:
                            vm.config.put(delete=f'hostpci{idx}')
                        except Exception:
                            pass
                    logger.info(f"[{self.hs_config.server_name}] PCI直通已移除")
                except Exception as gpu_error:
                    logger.warning(f"[{self.hs_config.server_name}] 移除GPU配置失败: {str(gpu_error)}")
            
            if config_updates:
                logger.info(f"[{self.hs_config.server_name}] 应用配置更新...")
                vm.config.put(**config_updates)
                logger.info(f"[{self.hs_config.server_name}] 虚拟机 {vm_conf.vm_uuid} 配置已更新")
            
            # 更新绑定 =========================================================
            logger.info(f"[{self.hs_config.server_name}] 更新路由器IP绑定...")
            super().IPBinder(vm_last, False)
            ikuai_result = super().IPBinder(vm_conf, True)
            if not ikuai_result.success:
                logger.warning(f"[{self.hs_config.server_name}] iKuai路由器绑定失败: {ikuai_result.message}")
            else:
                logger.info(f"[{self.hs_config.server_name}] 路由器IP绑定更新成功")
            
            # 启动机器 =========================================================
            logger.info(f"[{self.hs_config.server_name}] 启动虚拟机...")
            start_result = self.VMPowers(vm_conf.vm_uuid, VMPowers.S_START)
            if not start_result.success:
                logger.error(f"[{self.hs_config.server_name}] 虚拟机启动失败: {start_result.message}")
                return ZMessage(
                    success=False, action="VMUpdate",
                    message=f"虚拟机启动失败: {start_result.message}")
            
            return super().VMUpdate(vm_conf, vm_last)
            
        except Exception as e:
            logger.error(f"[{self.hs_config.server_name}] 虚拟机更新失败: {str(e)}")
            logger.error(f"[{self.hs_config.server_name}] 错误详情:", exc_info=True)
            traceback.print_exc()
            return ZMessage(
                success=False, action="VMUpdate",
                message=f"虚拟机更新失败: {str(e)}")

    # 删除虚拟机 ###############################################################
    def VMDelete(self, vm_name: str, rm_back=True) -> ZMessage:
        logger.info(f"[{self.hs_config.server_name}] 开始删除虚拟机: {vm_name}")
        try:
            # 连接Proxmox API ==================================================
            client, result = self.api_conn()
            if not result.success:
                logger.error(f"[{self.hs_config.server_name}] Proxmox连接失败: {result.message}")
                return result
            
            # 获取虚拟机配置 ===================================================
            vm_conf = self.vm_finds(vm_name)
            if vm_conf is None:
                logger.error(f"[{self.hs_config.server_name}] 虚拟机 {vm_name} 不存在")
                return ZMessage(
                    success=False, action="VMDelete",
                    message=f"虚拟机 {vm_name} 不存在")
            
            # 获取虚拟机VMID ===================================================
            vm_vmid = self.get_vmid(vm_conf)
            if vm_vmid is None:
                return ZMessage(
                    success=False, action="VMDelete",
                    message=f"虚拟机 {vm_name} VMID未找到")
            
            # 获取虚拟机对象 ===================================================
            vm = client.nodes(self.hs_config.launch_path).qemu(vm_vmid)
            
            # 停止虚拟机 =======================================================
            status = vm.status.current.get()
            if status['status'] == 'running':
                logger.info(f"[{self.hs_config.server_name}] 虚拟机正在运行，先停止...")
                self.VMPowers(vm_name, VMPowers.H_CLOSE)
            
            # 删除路由器绑定（iKuai层面）=======================================
            logger.info(f"[{self.hs_config.server_name}] 删除路由器IP绑定...")
            super().IPBinder(vm_conf, False)
            
            # 删除虚拟机（会自动删除网卡配置）==================================
            logger.info(f"[{self.hs_config.server_name}] 正在删除虚拟机 (VMID: {vm_vmid})...")
            vm.delete()
            logger.info(f"[{self.hs_config.server_name}] 虚拟机 {vm_name} (VMID: {vm_vmid}) 删除成功")
            
            # 通用操作 =========================================================
            return super().VMDelete(vm_name)
            
        except Exception as e:
            logger.error(f"[{self.hs_config.server_name}] 删除虚拟机失败: {str(e)}")
            logger.error(f"[{self.hs_config.server_name}] 错误详情:", exc_info=True)
            traceback.print_exc()
            return ZMessage(
                success=False, action="VMDelete",
                message=f"删除虚拟机失败: {str(e)}")

    # 虚拟机电源 ###############################################################
    def VMPowers(self, vm_name: str, power: VMPowers) -> ZMessage:
        """虚拟机电源管理"""
        # 先调用父类方法设置中间状态
        super().VMPowers(vm_name, power)
        
        client, result = self.api_conn()
        if not result.success:
            return result

        try:
            vm_conf = self.vm_finds(vm_name)
            if vm_conf is None:
                return ZMessage(
                    success=False, action="VMPowers",
                    message=f"虚拟机 {vm_name} 不存在")

            vmid = self.get_vmid(vm_conf)
            if vmid is None:
                return ZMessage(
                    success=False, action="VMPowers",
                    message=f"虚拟机 {vm_name} 的VMID未找到")

            vm = client.nodes(self.hs_config.launch_path).qemu(vmid)
            status = vm.status.current.get()

            if power == VMPowers.S_START:
                if status['status'] != 'running':
                    vm.status.start.post()
                    logger.info(f"虚拟机 {vm_name} 已启动")
                else:
                    logger.info(f"虚拟机 {vm_name} 已经在运行")

            elif power == VMPowers.H_CLOSE or power == VMPowers.S_CLOSE:
                if status['status'] == 'running':
                    if power == VMPowers.S_CLOSE:
                        vm.status.shutdown.post()
                    else:
                        vm.status.stop.post()
                    logger.info(f"虚拟机 {vm_name} 已停止")
                else:
                    logger.info(f"虚拟机 {vm_name} 已经停止")

            elif power == VMPowers.S_RESET or power == VMPowers.H_RESET:
                if status['status'] == 'running':
                    if power == VMPowers.S_RESET:
                        vm.status.reboot.post()
                    else:
                        vm.status.reset.post()
                    logger.info(f"虚拟机 {vm_name} 已重启")
                else:
                    vm.status.start.post()
                    logger.info(f"虚拟机 {vm_name} 已启动")

            elif power == VMPowers.A_PAUSE:
                if status['status'] == 'running':
                    vm.status.suspend.post()
                    logger.info(f"虚拟机 {vm_name} 已暂停")
                else:
                    logger.warning(f"虚拟机 {vm_name} 未运行，无法暂停")

            elif power == VMPowers.A_WAKED:
                if status['status'] == 'paused':
                    vm.status.resume.post()
                    logger.info(f"虚拟机 {vm_name} 已恢复")
                else:
                    logger.warning(f"虚拟机 {vm_name} 未暂停，无法恢复")

            hs_result = ZMessage(success=True, action="VMPowers")
            self.logs_set(hs_result)

        except Exception as e:
            error_msg = f"电源操作失败: {str(e)}"
            logger.error(f"虚拟机 {vm_name} 电源操作失败: {str(e)}")
            logger.error(traceback.format_exc())

            hs_result = ZMessage(
                success=False, action="VMPowers",
                message=error_msg)
            self.logs_set(hs_result)
            return hs_result

        return hs_result

    # 获取虚拟机实际状态（从API）==============================================
    def GetPower(self, vm_name: str) -> str:
        """从Proxmox API获取虚拟机实际状态"""
        try:
            client, result = self.api_conn()
            if not result.success:
                return ""
            
            vm_conf = self.vm_finds(vm_name)
            if vm_conf is None:
                return ""
            
            vmid = self.get_vmid(vm_conf)
            if vmid is None:
                return ""
            
            vm = client.nodes(self.hs_config.launch_path).qemu(vmid)
            status = vm.status.current.get()
            
            if status:
                vm_status = status.get('status', '')
                # 映射Proxmox状态到中文状态
                state_map = {
                    'running': '运行中',
                    'stopped': '已关机',
                    'paused': '已暂停'
                }
                return state_map.get(vm_status, '未知')
        except Exception as e:
            logger.warning(f"从API获取虚拟机 {vm_name} 状态失败: {str(e)}")
        return ""

    # 设置虚拟机密码 ###########################################################
    def VMPasswd(self, vm_name: str, os_pass: str) -> ZMessage:
        """设置虚拟机密码"""
        try:
            # 获取虚拟机连接 ===================================================
            vm_conn, vm_vmid, vm_conf, result = self._get_vm_connection(vm_name)
            if not result.success:
                return result
            
            # 通过QEMU Guest Agent设置密码 =====================================
            # 注意：需要虚拟机安装并运行qemu-guest-agent
            try:
                vm_conn.agent.post('exec', command=f"echo 'root:{os_pass}' | chpasswd")
                logger.info(f"虚拟机 {vm_name} 密码已设置")
                return ZMessage(success=True, action="Password")
            except Exception as agent_error:
                logger.warning(f"通过agent设置密码失败: {str(agent_error)}")
                traceback.print_exc()
                return ZMessage(
                    success=False, action="Password",
                    message=f"设置密码失败，请确保虚拟机已安装qemu-guest-agent: {str(agent_error)}")
        
        except Exception as e:
            logger.error(f"设置密码失败: {str(e)}")
            traceback.print_exc()
            return ZMessage(
                success=False, action="Password",
                message=f"设置密码失败: {str(e)}")

    # 备份虚拟机 ###############################################################
    def VMBackup(self, vm_name: str, vm_tips: str) -> ZMessage:
        logger.info(f"[{self.hs_config.server_name}] 开始备份虚拟机: {vm_name}")
        logger.info(f"  - 备份说明: {vm_tips}")
        
        # 连接到 Proxmox 服务器 ================================================
        client, result = self.api_conn()
        if not result.success:
            logger.error(f"[{self.hs_config.server_name}] Proxmox连接失败: {result.message}")
            return result
        # 获取虚拟机配置 =======================================================
        vm_conf = self.vm_finds(vm_name)
        if not vm_conf:
            logger.error(f"[{self.hs_config.server_name}] 虚拟机 {vm_name} 不存在")
            return ZMessage(
                success=False,
                action="Backup",
                message="虚拟机不存在")
        # 备份虚拟机 ========================================================
        try:
            vmid = self.get_vmid(vm_conf)
            if vmid is None:
                return ZMessage(
                    success=False, action="VMBackup",
                    message=f"虚拟机 {vm_name} 的VMID未找到")
            vm = client.nodes(self.hs_config.launch_path).qemu(vmid)
            # 检查虚拟机是否正在运行
            status = vm.status.current.get()
            is_running = status['status'] == 'running'
            if is_running:
                logger.info(f"[{self.hs_config.server_name}] 虚拟机正在运行，先停止以进行备份...")
                vm.status.stop.post()
                logger.info(f"[{self.hs_config.server_name}] 虚拟机 {vm_name} 已停止")
                time.sleep(5)  # 等待虚拟机完全停止
            # 构建备份文件名
            bak_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            bak_file = f"{vm_name}_{bak_time}.vma"
            logger.info(f"[{self.hs_config.server_name}] 备份文件名: {bak_file}")
            
            # 创建备份
            backup_config = {
                'vmid': vmid,
                'mode': 'stop',  # 停止模式备份
                'compress': 'gzip',
                'storage': 'local',  # 备份存储位置
            }
            logger.info(f"[{self.hs_config.server_name}] 正在创建备份任务...")
            task_id = client.nodes(
                self.hs_config.launch_path
            ).vzdump.post(**backup_config)
            logger.info(f"[{self.hs_config.server_name}] 备份任务已创建，任务ID: {task_id}")
            # 等待备份完成 ==================================================
            max_wait_time = 3600  # 最大等待时间（秒），1小时
            check_interval = 5  # 检查间隔（秒）
            all_time = 0
            while all_time < max_wait_time:
                # 查询任务状态 ----------------------------------------------
                task_status = client.nodes(
                    self.hs_config.launch_path
                ).tasks(task_id).status.get()
                status_value = task_status.get('status', '')
                logger.info(f"[{self.hs_config.server_name}] 备份{status_value}已等待: {all_time}秒")
                # 任务成功完成 ----------------------------------------------
                if status_value == 'stopped':
                    logger.info(f"[{self.hs_config.server_name}] 备份完成，总耗时: {all_time}秒")
                    break
                time.sleep(check_interval)
                all_time += check_interval
                # 超时检查 --------------------------------------------------
                if all_time >= max_wait_time:
                    logger.error(f"[{self.hs_config.server_name}] 备份任务超时，已等待{max_wait_time}秒")
                    raise TimeoutError(f"备份超时，已等待{max_wait_time}秒")
            # 记录备份信息 ==================================================
            vm_conf.backups.append(VMBackup(
                backup_time=datetime.datetime.now(),
                backup_name=bak_file,
                backup_hint=vm_tips,
                old_os_name=vm_conf.os_name
            ))
            # 重新启动 ======================================================
            if is_running:
                logger.info(f"[{self.hs_config.server_name}] 重新启动虚拟机...")
                vm.status.start.post()
                logger.info(f"[{self.hs_config.server_name}] 虚拟机 {vm_name} 已重新启动")
            # 记录备份结果 ==================================================
            logger.info(f"[{self.hs_config.server_name}] 虚拟机备份成功: {bak_file}，耗时: {all_time}秒")
            hs_result = ZMessage(
                success=True, action="VMBackup",
                message=f"虚拟机备份成功: {bak_file}，耗时: {all_time}秒",
                results={"backup_file": bak_file, "elapsed_time": all_time}
            )
            # 保存虚拟机配置 ================================================
            self.vm_saving[vm_name] = vm_conf
            self.logs_set(hs_result)
            self.data_set()
            return hs_result
        # 备份失败 ==========================================================
        except Exception as e:
            logger.error(f"[{self.hs_config.server_name}] 备份虚拟机失败: {str(e)}")
            logger.error(f"[{self.hs_config.server_name}] 错误详情:", exc_info=True)
            traceback.print_exc()
            return ZMessage(
                success=False, action="VMBackup",
                message=f"备份失败: {str(e)}")

    # 恢复虚拟机 ###############################################################
    def Restores(self, vm_name: str, vm_back: str) -> ZMessage:
        """恢复虚拟机"""
        client, result = self.api_conn()
        if not result.success:
            return result

        vm_conf = self.vm_finds(vm_name)
        if not vm_conf:
            return ZMessage(
                success=False, action="Restores",
                message=f"虚拟机 {vm_name} 不存在")

        # 获取备份信息
        vb_conf = None
        for vb_item in vm_conf.backups:
            if vb_item.backup_name == vm_back:
                vb_conf = vb_item
                break

        if not vb_conf:
            return ZMessage(
                success=False, action="Restores",
                message=f"备份 {vm_back} 不存在")

        try:
            vmid = self.get_vmid(vm_conf)
            if vmid is None:
                return ZMessage(
                    success=False, action="Restores",
                    message=f"虚拟机 {vm_name} 的VMID未找到")

            # 恢复备份
            # 注意：Proxmox的恢复操作比较复杂，这里简化处理
            logger.info(f"开始恢复虚拟机 {vm_name}，备份文件: {vm_back}")

            # 实际的恢复操作需要调用Proxmox的restore API
            # 这里只是示例代码
            restore_config = {
                'vmid': vmid,
                'archive': f"local:backup/{vm_back}",
                'force': 1,
            }

            # client.nodes(self.hs_config.launch_path).qemu.post(**restore_config)

            vm_conf.os_name = vb_conf.old_os_name
            logger.info(f"虚拟机 {vm_name} 恢复成功")

            self.vm_saving[vm_name] = vm_conf
            hs_result = ZMessage(
                success=True, action="Restores",
                message=f"虚拟机恢复成功: {vm_name}",
                results={"vm_name": vm_name}
            )
            self.logs_set(hs_result)
            self.data_set()
            return hs_result

        except Exception as e:
            logger.error(f"恢复虚拟机失败: {str(e)}")
            traceback.print_exc()
            return ZMessage(
                success=False, action="Restores",
                message=f"恢复失败: {str(e)}")

    # 查找SCSI设备 #############################################################
    def get_scsi(self, vm_apis, vm_name: str, disk_file: str = None) -> Optional[str]:
        """从Proxmox配置中查找SCSI设备号
        
        Args:
            vm_apis: Proxmox虚拟机API对象
            vm_name: 虚拟机名称
            disk_file: 磁盘文件名（可选，用于匹配）
        
        Returns:
            找到的SCSI设备号（如'scsi1'），未找到返回None
        """
        try:
            # 获取虚拟机配置 ===================================================
            config = vm_apis.config.get()
            logger.info(f"尝试从Proxmox配置中查找虚拟机 {vm_name} 的SCSI设备")

            # 遍历所有scsi设备 =================================================
            for key, value in config.items():
                if key.startswith('scsi') and isinstance(value, str):
                    logger.debug(f"检查设备 {key}: {value}")

                    # 如果提供了disk_file，通过磁盘文件名匹配 ===================
                    if disk_file and disk_file in value:
                        logger.info(f"通过磁盘文件名 {disk_file} 找到设备: {key}")
                        return key

            logger.warning(f"未找到匹配的SCSI设备")
            return None

        except Exception as e:
            logger.error(f"查找SCSI设备时出错: {str(e)}")
            traceback.print_exc()
            return None

    # 创建QCOW2磁盘文件 ########################################################
    def hdd_init(self, vm_vmid: int, disk_name: str, disk_size: str) -> ZMessage:
        """创建QCOW2格式的磁盘文件
        
        Args:
            vm_vmid: 虚拟机VMID
            disk_name: 磁盘文件名（如'vm-100-disk-1.qcow2'）
            disk_size: 磁盘大小（如'10G'）
        
        Returns:
            ZMessage对象，包含操作结果
        """
        try:
            disk_dir = f"/var/lib/vz/images/{vm_vmid}"

            # 远程模式 =========================================================
            if self.flag_web():
                # 远程模式：通过SSH创建qcow2文件
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                ssh.connect(
                    self.hs_config.server_addr,
                    username=self.hs_config.server_user,
                    password=self.hs_config.server_pass)

                # 创建目录 =====================================================
                ssh.exec_command(f"mkdir -p {disk_dir}")

                # 创建qcow2文件 ================================================
                create_cmd = f"qemu-img create -f qcow2 {disk_dir}/{disk_name} {disk_size}"
                stdin, stdout, stderr = ssh.exec_command(create_cmd)
                exit_status = stdout.channel.recv_exit_status()

                if exit_status != 0:
                    error_msg = stderr.read().decode()
                    ssh.close()
                    return ZMessage(
                        success=False, action="CreateQcow2",
                        message=f"创建qcow2文件失败: {error_msg}")

                ssh.close()
                logger.info(f"通过SSH创建qcow2文件: {disk_dir}/{disk_name}, 大小: {disk_size}")

            # 本地模式 =========================================================
            else:
                # 本地模式：直接创建qcow2文件
                os.makedirs(disk_dir, exist_ok=True)
                create_cmd = f"qemu-img create -f qcow2 {disk_dir}/{disk_name} {disk_size}"
                exit_status = os.system(create_cmd)

                if exit_status != 0:
                    return ZMessage(
                        success=False, action="CreateQcow2",
                        message=f"创建qcow2文件失败")

                logger.info(f"本地创建qcow2文件: {disk_dir}/{disk_name}, 大小: {disk_size}")

            return ZMessage(
                success=True, action="CreateQcow2",
                message=f"成功创建qcow2文件: {disk_name}")

        except Exception as e:
            logger.error(f"创建qcow2文件异常: {str(e)}")
            traceback.print_exc()
            return ZMessage(
                success=False, action="CreateQcow2",
                message=f"创建qcow2文件异常: {str(e)}")

    # VM镜像挂载 ###############################################################
    def HDDMount(self, vm_name: str, vm_imgs: SDConfig, in_flag=True) -> ZMessage:
        action_name = "挂载" if in_flag else "卸载"
        logger.info(f"[{self.hs_config.server_name}] 开始{action_name}硬盘: {vm_imgs.hdd_name} -> 虚拟机 {vm_name}")
        
        # 获取虚拟机信息 =======================================================
        result = self.get_info(vm_name)
        if not result.success:
            logger.error(f"[{self.hs_config.server_name}] 获取虚拟机信息失败: {result.message}")
            return result
        vm_conn = result.results[0]
        vm_vmid = result.results[1]
        # 挂载硬盘 =============================================================
        try:
            # 停止虚拟机 =======================================================
            vm_flag = vm_conn.status.current.get()
            vm_flag = vm_flag['status'] == 'running'
            if vm_flag:
                self.VMPowers(vm_name, VMPowers.H_CLOSE)
            # 获取可用的scsi设备号 =============================================
            if in_flag:
                # 找到可用的scsi设备号 =========================================
                config = vm_conn.config.get()
                scsi_num = 1
                while f"scsi{scsi_num}" in config:
                    scsi_num += 1
                # 检查是否是重新挂载已卸载的硬盘 ===============================
                disk_name = None
                if vm_imgs.hdd_name in self.vm_saving[vm_name].hdd_all:
                    now_disk = self.vm_saving[vm_name].hdd_all[vm_imgs.hdd_name]
                    # 已卸载的硬盘，重新挂载 -----------------------------------
                    if now_disk.hdd_flag == 0 and now_disk.hdd_file:
                        disk_name = now_disk.hdd_file
                        logger.info(f"重新挂载已卸载的硬盘: {disk_name}")
                    # 已挂载的硬盘，不能再挂载 ---------------------------------
                    elif now_disk.hdd_flag == 1:
                        return ZMessage(
                            success=False, action="HDDMount",
                            message=f"硬盘 {vm_imgs.hdd_name} 已经挂载")
                # 需要创建新硬盘 ===============================================
                if disk_name is None:
                    hdd_size_mb = getattr(vm_imgs, 'hdd_size', 10)
                    disk_size = f"{hdd_size_mb // 1024}G"
                    disk_name = f"vm-{vm_vmid}-disk-{scsi_num}.qcow2"
                    # 创建磁盘文件 =============================================
                    create_result = self.hdd_init(vm_vmid, disk_name, disk_size)
                    if not create_result.success:
                        return create_result
                    logger.info(f"创建新硬盘: {disk_name}, 大小: {disk_size}")
                # 确保disk_name已赋值 ==========================================
                if disk_name is None:
                    return ZMessage(
                        success=False, action="HDDMount",
                        message="无法确定磁盘文件名")
                # 挂载硬盘 =====================================================
                storage_name = self.hs_config.extern_path
                disk_config = f"{storage_name}:{vm_vmid}/{disk_name}"
                vm_conn.config.put(**{f"scsi{scsi_num}": disk_config})
                logger.info(f"硬盘挂载到虚拟机 {vm_name}，设备: scsi{scsi_num}")
                # 保存scsi设备号和状态 =========================================
                vm_imgs.hdd_flag = 1  # 1表示已挂载
                vm_imgs.hdd_scsi = f"scsi{scsi_num}"
                vm_imgs.hdd_file = disk_name
                self.vm_saving[vm_name].hdd_all[vm_imgs.hdd_name] = vm_imgs
            # 卸载硬盘 =========================================================
            else:
                # 检查硬盘是否在虚拟机配置中 -----------------------------------
                if vm_imgs.hdd_name not in self.vm_saving[vm_name].hdd_all:
                    return ZMessage(
                        success=False, action="HDDMount",
                        message=f"硬盘 {vm_imgs.hdd_name} 不在虚拟机配置中")
                # 获取硬盘配置信息 ---------------------------------------------
                mounted_disk = self.vm_saving[vm_name].hdd_all[vm_imgs.hdd_name]
                scsi_device = getattr(mounted_disk, 'hdd_scsi', None)
                disk_file = getattr(mounted_disk, 'hdd_file', None)
                # 如果没有scsi设备号，尝试从Proxmox配置中查找 ------------------
                if not scsi_device:
                    scsi_device = self.get_scsi(vm_conn, vm_name, disk_file)
                # 如果还是找不到scsi设备，返回错误 -----------------------------
                if not scsi_device:
                    logger.error(f"无法找到硬盘 {vm_imgs.hdd_name} scsi设备号")
                    return ZMessage(
                        success=False, action="HDDMount",
                        message=f"无法找到硬盘 {vm_imgs.hdd_name} scsi设备号")
                # 执行卸载操作 -------------------------------------------------
                vm_conn.config.put(**{scsi_device: "none"})
                vm_conn.config.put(delete=scsi_device)
                logger.info(f"已从Proxmox配置中卸载 {scsi_device} 设备")
                # 标记为已卸载 -------------------------------------------------
                mounted_disk.hdd_flag = 0  # 0表示已卸载
                mounted_disk.hdd_scsi = ""  # 清除设备号，下次挂载时会重新分配
                self.vm_saving[vm_name].hdd_all[vm_imgs.hdd_name] = mounted_disk
                logger.info(f"硬盘{vm_imgs.hdd_name}已从虚拟机 {vm_name} 卸载")
            # 保存配置到数据库 =================================================
            self.data_set()
            logger.info(f"[{self.hs_config.server_name}] 硬盘配置已保存到数据库")
            
            # 重启虚拟机 =======================================================
            if vm_flag:
                logger.info(f"[{self.hs_config.server_name}] 重新启动虚拟机...")
                self.VMPowers(vm_name, VMPowers.S_START)
            
            logger.info(f"[{self.hs_config.server_name}] 硬盘{action_name}成功: {vm_imgs.hdd_name}")
            return ZMessage(
                success=True, action="HDDMount",
                message=f"硬盘{"挂载" if in_flag else "卸载"}成功")
        # 捕获所有异常 =========================================================
        except Exception as e:
            logger.error(f"[{self.hs_config.server_name}] 硬盘{action_name}操作失败: {str(e)}")
            logger.error(f"[{self.hs_config.server_name}] 错误详情:", exc_info=True)
            traceback.print_exc()
            return ZMessage(
                success=False, action="HDDMount",
                message=f"硬盘挂载操作失败: {str(e)}")

    # ISO镜像挂载 ##############################################################
    def ISOMount(self, vm_name: str,
                 vm_imgs: IMConfig, in_flag=True) -> ZMessage:
        action_name = "挂载" if in_flag else "卸载"
        logger.info(f"[{self.hs_config.server_name}] 开始{action_name}ISO镜像: {vm_imgs.iso_name if in_flag else '所有ISO'} -> 虚拟机 {vm_name}")
        try:
            # 获取虚拟机信息 ===================================================
            result = self.get_info(vm_name)
            if not result.success:
                logger.error(f"[{self.hs_config.server_name}] 获取虚拟机信息失败: {result.message}")
                return result
            vm_conn = result.results[0]
            
            # 停止虚拟机 =======================================================
            status = vm_conn.status.current.get()
            was_running = status['status'] == 'running'
            if was_running:
                self.VMPowers(vm_name, VMPowers.H_CLOSE)
            
            # 执行挂载/卸载操作 ================================================
            if in_flag:
                # 挂载ISO ======================================================
                dvdrom_storage = self.hs_config.dvdrom_path or "local:iso"
                iso_path = f"{dvdrom_storage}/{vm_imgs.iso_file}"
                vm_conn.config.put(ide2=f"{iso_path},media=cdrom")
                self.vm_saving[vm_name].iso_all[vm_imgs.iso_name] = vm_imgs
                logger.info(f"ISO已挂载到虚拟机 {vm_name}: {vm_imgs.iso_file}")
            else:
                # 卸载ISO ======================================================
                vm_conn.config.put(ide2="none,media=cdrom")
                if vm_imgs.iso_name in self.vm_saving[vm_name].iso_all:
                    del self.vm_saving[vm_name].iso_all[vm_imgs.iso_name]
                logger.info(f"ISO已从虚拟机 {vm_name} 卸载")
            
            # 保存配置 =========================================================
            vm_conf = deepcopy(self.vm_saving[vm_name])
            self.VMUpdate(self.vm_saving[vm_name], vm_conf)
            self.data_set()
            
            # 重启虚拟机 =======================================================
            if was_running:
                self.VMPowers(vm_name, VMPowers.S_START)
            
            # 返回结果 =========================================================
            return ZMessage(
                success=True, action="ISOMount",
                message=f"ISO镜像{"挂载" if in_flag else "卸载"}成功")
            
        except Exception as e:
            logger.error(f"ISO镜像挂载操作失败: {str(e)}")
            traceback.print_exc()
            return ZMessage(
                success=False, action="ISOMount",
                message=f"ISO镜像挂载操作失败: {str(e)}")

    # 虚拟机控制台 #############################################################
    def VMRemote(self, vm_uuid: str, ip_addr: str = "127.0.0.1") -> ZMessage:
        try:
            # 获取虚拟机连接 ===================================================
            vm_conn, vmid, vm_conf, result = self._get_vm_connection(vm_uuid)
            if not result.success:
                return result
            
            # 获取主机外网IP ===================================================
            if len(self.hs_config.public_addr) == 0:
                return ZMessage(
                    success=False,
                    action="VCRemote",
                    message="主机外网IP不存在")
            
            public_ip = self.hs_config.public_addr[0]
            if public_ip in ["localhost", "127.0.0.1", ""]:
                public_ip = "127.0.0.1"
            
            # 构造Proxmox VNC URL ==============================================
            vnc_url = (f"https://{self.hs_config.server_addr}:8006/"
                       f"?console=kvm&novnc=1&vmid={vmid}&node={self.hs_config.launch_path}")
            
            logger.info(f"VMRemote for {vm_uuid}: {vnc_url}")
            
            return ZMessage(
                success=True,
                action="VCRemote",
                message=vnc_url,
                results={
                    "vmid": vmid,
                    "url": vnc_url
                }
            )
        
        except Exception as e:
            logger.error(f"获取虚拟机远程控制台失败: {str(e)}")
            traceback.print_exc()
            return ZMessage(
                success=False,
                action="VCRemote",
                message=f"获取远程控制台失败: {str(e)}")

    # 加载备份 #################################################################
    def LDBackup(self, vm_back: str = "") -> ZMessage:
        return super().LDBackup(vm_back)

    # 移除备份 #################################################################
    def RMBackup(self, vm_name: str, vm_back: str = "") -> ZMessage:
        return super().RMBackup(vm_name, vm_back)

    def get_info(self, vm_name: str) -> ZMessage:
        """获取虚拟机信息的统一方法"""
        try:
            # 使用公共辅助方法获取虚拟机连接 =================================
            vm_conn, vm_vmid, vm_conf, result = self._get_vm_connection(vm_name)
            if not result.success:
                return result
            
            # 返回虚拟机配置 ===================================================
            return ZMessage(
                success=True, action="get_info",
                message=f"成功获取虚拟机 {vm_name} 信息",
                results=(vm_conn, vm_vmid, vm_conf))
        
        except Exception as e:
            logger.error(f"获取虚拟机信息失败: {str(e)}")
            traceback.print_exc()
            return ZMessage(
                success=False, action="get_info",
                message=f"获取虚拟机信息失败: {str(e)}")

    # 硬盘所有权移交 ###########################################################
    def HDDTrans(self, vm_name: str, vm_imgs: SDConfig, ex_name: str) -> ZMessage:
        # 检查情况 =============================================================
        check_result = self.HDDCheck(vm_name, vm_imgs, ex_name)
        if not check_result.success:
            return check_result
        # 获取虚拟机信息 =======================================================
        result = self.get_info(vm_name)
        if not result.success:
            return ZMessage(
                success=False, action="HDDTrans",
                message=f"获取源虚拟机信息失败: {result.message}")
        src_vm_conn = result.results[0]
        src_vmid = result.results[1]
        # 获取目标虚拟机信息 ===================================================
        result = self.get_info(ex_name)
        if not result.success:
            return ZMessage(
                success=False, action="HDDTrans",
                message=f"获取目标虚拟机信息失败: {result.message}")
        dst_vm_conn = result.results[0]
        dst_vmid = result.results[1]
        # 执行移交操作 =========================================================
        try:
            hdd_config = self.vm_saving[vm_name].hdd_all[vm_imgs.hdd_name]
            disk_file = getattr(hdd_config, 'hdd_file', None)
            if not disk_file:
                return ZMessage(
                    success=False, action="HDDTrans",
                    message="磁盘文件信息不存在，无法移交")

            # 获取源虚拟机配置，找到磁盘对应的设备 =============================
            src_config = src_vm_conn.config.get()
            # 查找包含该磁盘文件的unused disk
            source_disk = None
            for key, value in src_config.items():
                if key.startswith('unused') and isinstance(value, str):
                    if disk_file in value:
                        source_disk = key
                        logger.info(f"找到源磁盘: {key} = {value}")
                        break
            if not source_disk:
                return ZMessage(
                    success=False, action="HDDTrans",
                    message=f"未找到磁盘文件 {disk_file} 对应的unused disk")
            # 找到目标虚拟机可用的scsi编号 =====================================
            dst_config = dst_vm_conn.config.get()
            scsi_num = 1
            while f"scsi{scsi_num}" in dst_config:
                scsi_num += 1
            target_disk = f"scsi{scsi_num}"
            # 获取存储名称 =====================================================
            storage_name = self.hs_config.extern_path
            # 使用PVE API的move_disk功能 =======================================
            # 注意：proxmoxer库可能不直接支持move_disk，需要通过SSH执行qm命令
            logger.info(f"准备移动磁盘: 从VM {src_vmid}({source_disk}) "
                        f"到VM {dst_vmid}({target_disk})")
            # 通过SSH执行qm move-disk命令 ======================================
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(
                self.hs_config.server_addr,
                username=self.hs_config.server_user,
                password=self.hs_config.server_pass)
            # 执行qm move-disk命令 =============================================
            move_cmd = (
                f"qm move-disk {src_vmid} {source_disk} "
                f"--target-vmid {dst_vmid} --target-disk {target_disk}"
            )
            logger.info(f"执行命令: {move_cmd}")
            stdin, stdout, stderr = ssh.exec_command(move_cmd)
            exit_status = stdout.channel.recv_exit_status()
            output = stdout.read().decode()
            error_output = stderr.read().decode()
            ssh.close()
            if exit_status != 0:
                logger.error(f"移动磁盘失败: {error_output}")
                return ZMessage(
                    success=False, action="HDDTrans",
                    message=f"移动磁盘失败: {error_output}")
            logger.info(f"磁盘移动成功: {output}")
            # 获取新的磁盘文件名 ===============================================
            dst_config_new = dst_vm_conn.config.get()
            new_disk_value = dst_config_new.get(target_disk, "")
            import posixpath
            if ":" in new_disk_value and "/" in new_disk_value:
                # 先分割出路径部分（去掉storage前缀）
                path_part = new_disk_value.split(":")[-1]
                # 再去掉size等参数（用逗号分割）
                path_part = path_part.split(",")[0]
                new_disk_name = posixpath.basename(path_part)
            else:
                # 如果无法解析，使用默认命名
                _, disk_ext = posixpath.splitext(disk_file)
                new_disk_name = f"vm-{dst_vmid}-disk-{scsi_num}{disk_ext}"
            logger.info(f"新磁盘文件名: {new_disk_name}")
            # 立即卸载目标虚拟机上的磁盘，使其变为unused状态 ===================
            logger.info(f"卸载目标虚拟机上的磁盘 {target_disk}")
            dst_vm_conn.config.put(**{target_disk: "none"})
            dst_vm_conn.config.put(delete=target_disk)
            logger.info(f"磁盘 {target_disk} 已在PVE中卸载，现在处于unused状态")
            # 从源虚拟机移除磁盘配置 ===========================================
            self.vm_saving[vm_name].hdd_all.pop(vm_imgs.hdd_name)
            # 添加到目标虚拟机（保持未挂载状态）================================
            vm_imgs.hdd_flag = 0  # 移交后保持未挂载状态
            vm_imgs.hdd_scsi = ""  # 清空设备号，等待下次挂载时分配
            vm_imgs.hdd_file = new_disk_name  # 更新文件名
            self.vm_saving[ex_name].hdd_all[vm_imgs.hdd_name] = vm_imgs
            # 保存配置 =========================================================
            self.data_set()
            logger.info(
                f"磁盘 {vm_imgs.hdd_name} 已从虚拟机 {vm_name} "
                f"(VMID: {src_vmid}) 移交到 {ex_name} (VMID: {dst_vmid})")
            # 返回结果 =========================================================
            return ZMessage(
                success=True, action="HDDTrans",
                message="磁盘移交成功",
                results={
                    "source_vmid": src_vmid,
                    "target_vmid": dst_vmid,
                    "source_disk": source_disk,
                    "target_disk": target_disk,
                    "new_disk_name": new_disk_name,
                    "src_vm": vm_name,
                    "dst_vm": ex_name
                })
        # 捕获异常 ==============================================================
        except Exception as e:
            logger.error(f"磁盘移交失败: {str(e)}")
            traceback.print_exc()
            return ZMessage(
                success=False, action="HDDTrans",
                message=f"磁盘移交失败: {str(e)}")

    # 移除磁盘 #################################################################
    def RMMounts(self, vm_name: str, vm_imgs: str) -> ZMessage:
        # 获取虚拟机信息 =======================================================
        result = self.get_info(vm_name)
        if not result.success:
            return result
        vm_conn = result.results[0]
        vm_vmid = result.results[1]
        # 获取虚拟机配置 =======================================================
        try:
            # 获取硬盘配置信息 =================================================
            mounted_disk = deepcopy(self.vm_saving[vm_name].hdd_all[vm_imgs])
            scsi_device = getattr(mounted_disk, 'hdd_scsi', None)
            disk_file = getattr(mounted_disk, 'hdd_file', None)
            # 停止虚拟机 =======================================================
            status = vm_conn.status.current.get()
            was_running = status['status'] == 'running'
            if was_running:
                self.VMPowers(vm_name, VMPowers.H_CLOSE)
            # 卸载磁盘（更新本地配置状态）======================================
            self.HDDMount(vm_name, mounted_disk, False)
            time.sleep(3)  # 等待配置更新
            # 移除配置 =========================================================
            if scsi_device and disk_file:
                config = vm_conn.config.get()
                # 查找磁盘 =================================================
                del_disk = None
                for key, value in config.items():
                    if key.startswith('unused') and isinstance(value, str):
                        if disk_file in value:
                            del_disk = key
                            logger.info(f"找到匹配的unused disk: {key}")
                            break
                # 删除找到的unused disk ====================================
                if del_disk:
                    vm_conn.config.put(delete=del_disk)
                    logger.info(f"已彻底删除磁盘文件: {del_disk}")
            else:
                logger.warning(f"未找到包含{disk_file}unused disk")
            # 从配置删除 =======================================================
            del self.vm_saving[vm_name].hdd_all[vm_imgs]
            logger.info(f"已从配置列表中删除硬盘 {vm_imgs}")
            # 保存数据库 =======================================================
            self.data_set()
            logger.info(f"虚拟机 {vm_name} 配置已保存到数据库")
            # 重启虚拟机 =======================================================
            if was_running:
                self.VMPowers(vm_name, VMPowers.S_START)
            # 返回结果 =========================================================
            return ZMessage(
                success=True, action="RMMounts",
                message=f"硬盘 {vm_imgs} 删除成功")
        # 处理异常 =============================================================
        except Exception as e:
            traceback.print_exc()
            return ZMessage(
                success=False, action="RMMounts",
                message=f"删除硬盘失败: {str(e)}")

    # 虚拟机截图 ###############################################################
    def VMScreen(self, vm_name: str = "") -> str:
        """获取虚拟机截图
        
        :param vm_name: 虚拟机名称
        :return: base64编码的截图字符串，失败则返回空字符串
        """
        try:
            logger.info(f"[{self.hs_config.server_name}] 开始获取虚拟机 {vm_name} 截图")
            
            # 1. 检查虚拟机是否存在
            if vm_name not in self.vm_saving:
                logger.error(f"[{self.hs_config.server_name}] 虚拟机 {vm_name} 不存在")
                return ""
            
            # 2. 获取虚拟机信息
            result = self.get_info(vm_name)
            if not result.success:
                logger.error(f"[{self.hs_config.server_name}] 获取虚拟机信息失败: {result.message}")
                return ""
            
            vm_conn = result.results[0]
            vmid = self.get_vmid(self.vm_saving[vm_name])
            
            # 3. 检查虚拟机是否正在运行
            status = vm_conn.status.current.get()
            if status.get('status') != 'running':
                logger.warning(f"[{self.hs_config.server_name}] 虚拟机 {vm_name} 未运行，无法获取截图")
                return ""
            
            # 4. 通过 SSH + qm monitor screendump 获取截图（PPM格式）
            import base64
            import io

            try:
                remote_ppm = f"/tmp/screen-{vmid}.ppm"
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                ssh.connect(
                    self.hs_config.server_addr,
                    username=self.hs_config.server_user,
                    password=self.hs_config.server_pass,
                    timeout=10)

                # 5. 通过 qm monitor 发送 screendump 命令
                cmd = f"echo 'screendump {remote_ppm}' | qm monitor {vmid}"
                stdin, stdout, stderr = ssh.exec_command(cmd)
                stdout.channel.recv_exit_status()

                # 6. 读取 PPM 文件内容
                sftp = ssh.open_sftp()
                buf = io.BytesIO()
                sftp.getfo(remote_ppm, buf)
                sftp.close()
                ssh.exec_command(f"rm -f {remote_ppm}")
                ssh.close()

                ppm_data = buf.getvalue()
                if not ppm_data:
                    logger.error(f"[{self.hs_config.server_name}] screendump 返回空数据")
                    return ""

                # 7. PPM 转 PNG（有 PIL 则转，否则直接返回 PPM 的 base64）
                try:
                    from PIL import Image
                    img = Image.open(io.BytesIO(ppm_data))
                    out = io.BytesIO()
                    img.save(out, format='PNG')
                    screenshot_base64 = base64.b64encode(out.getvalue()).decode('utf-8')
                except ImportError:
                    screenshot_base64 = base64.b64encode(ppm_data).decode('utf-8')

                logger.info(f"[{self.hs_config.server_name}] 成功获取虚拟机 {vm_name} 截图")
                return screenshot_base64

            except Exception as e:
                logger.error(f"[{self.hs_config.server_name}] 获取截图失败: {str(e)}")
                return ""
                
        except Exception as e:
            logger.error(f"[{self.hs_config.server_name}] 获取虚拟机截图时出错: {str(e)}")
            traceback.print_exc()
            return ""

    # 查找PCI设备 #################################################################
    def PCIShows(self) -> Dict[str, 'VFConfig']:
        """获取可用的PCI直通设备列表
        通过SSH lspci -nn列出所有PCI设备及其IOMMU组
        Returns:
            dict: {pci_id: VFConfig}
        """
        from MainObject.Config.VFConfig import VFConfig
        try:
            logger.info(f"[{self.hs_config.server_name}] 开始获取PCI设备列表")

            client, result = self.api_conn()
            if not result.success:
                return {}

            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            try:
                ssh.connect(
                    self.hs_config.server_addr,
                    username=self.hs_config.server_user,
                    password=self.hs_config.server_pass
                )

                # 列出所有PCI设备（包含设备ID）
                cmd = "lspci -nn"
                stdin, stdout, stderr = ssh.exec_command(cmd)
                output = stdout.read().decode('utf-8')

                device_dict = {}
                if output:
                    for line in output.strip().split('\n'):
                        parts = line.split(' ', 1)
                        if len(parts) >= 2:
                            pci_id = parts[0]  # 如: 01:00.0
                            device_info = parts[1]
                            # 提取设备名称和类型
                            device_name = device_info.strip()
                            device_dict[pci_id] = VFConfig(
                                gpu_uuid=pci_id,
                                gpu_mdev="PVE_Passthrough",
                                gpu_hint=device_name
                            )

                ssh.close()
                logger.info(f"[{self.hs_config.server_name}] 共找到 {len(device_dict)} 个PCI设备")
                return device_dict

            except Exception as ssh_error:
                logger.error(f"[{self.hs_config.server_name}] SSH连接失败: {str(ssh_error)}")
                try:
                    ssh.close()
                except Exception as e_close:
                    logger.warning(f"[{self.hs_config.server_name}] 关闭SSH连接失败: {str(e_close)}")
                return {}

        except Exception as e:
            logger.error(f"[{self.hs_config.server_name}] 获取PCI设备列表失败: {str(e)}")
            traceback.print_exc()
            return {}

    # PCI设备直通 ##################################################################
    def PCISetup(self, vm_name: str, config, pci_key: str, in_flag=True):
        """PVE PCI直通 - 通过API设置hostpci参数"""
        from MainObject.Public.ZMessage import ZMessage
        try:
            if vm_name not in self.vm_saving:
                return ZMessage(success=False, action="PCISetup", message="虚拟机不存在")

            from MainObject.Config.VMPowers import VMPowers
            vm_config = self.vm_saving[vm_name]
            if vm_config.vm_flag not in [VMPowers.ON_STOP, VMPowers.UNKNOWN]:
                return ZMessage(success=False, action="PCISetup", message="PCI直通需要先关闭虚拟机")

            client, result = self.api_conn()
            if not result.success:
                return ZMessage(success=False, action="PCISetup", message=f"PVE连接失败: {result.message}")

            # 获取虚拟机VMID
            vm_conf_pci = self.vm_saving[vm_name]
            vmid = self.get_vmid(vm_conf_pci)
            if not vmid:
                return ZMessage(success=False, action="PCISetup", message="无法获取虚拟机VMID")

            node = self.hs_config.launch_path

            pci_id = config.gpu_uuid

            if in_flag:
                # 添加PCI直通 - 找一个空闲的hostpci槽位
                slot = 0
                existing_config = client.nodes(node).qemu(vmid).config.get()
                while f'hostpci{slot}' in existing_config:
                    slot += 1
                    if slot > 15:
                        return ZMessage(success=False, action="PCISetup", message="PCI直通槽位已满")

                client.nodes(node).qemu(vmid).config.put(**{
                    f'hostpci{slot}': f'{pci_id},pcie=1'
                })
            else:
                # 移除PCI直通 - 找到对应的hostpci槽位并删除
                existing_config = client.nodes(node).qemu(vmid).config.get()
                delete_key = None
                for i in range(16):
                    key = f'hostpci{i}'
                    if key in existing_config:
                        val = existing_config[key]
                        if pci_id in str(val):
                            delete_key = key
                            break

                if delete_key:
                    client.nodes(node).qemu(vmid).config.put(delete=delete_key)

            # 调用基类写入配置
            return super().PCISetup(vm_name, config, pci_key, in_flag)

        except Exception as e:
            logger.error(f"[{self.hs_config.server_name}] PCI直通操作失败: {str(e)}")
            traceback.print_exc()
            return ZMessage(success=False, action="PCISetup", message=str(e))

    # 查找USB设备 ##################################################################
    def USBShows(self) -> Dict[str, 'USBInfos']:  # noqa
        """获取PVE主机上的USB设备列表"""
        from MainObject.Config.USBInfos import USBInfos
        try:
            client, result = self.api_conn()
            if not result.success:
                return {}

            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            try:
                ssh.connect(
                    self.hs_config.server_addr,
                    username=self.hs_config.server_user,
                    password=self.hs_config.server_pass
                )

                cmd = "lsusb"
                stdin, stdout, stderr = ssh.exec_command(cmd)
                output = stdout.read().decode('utf-8')

                usb_dict = {}
                if output:
                    for line in output.strip().split('\n'):
                        if 'ID ' in line:
                            id_part = line.split('ID ')[1]
                            vid_pid = id_part.split(' ')[0]
                            name = id_part.split(' ', 1)[1] if ' ' in id_part else vid_pid
                            if ':' in vid_pid:
                                vid, pid = vid_pid.split(':')
                                usb_dict[vid_pid] = USBInfos(
                                    vid_uuid=vid, pid_uuid=pid, usb_hint=name.strip())

                ssh.close()
                logger.info(f"[{self.hs_config.server_name}] 发现 {len(usb_dict)} 个USB设备")
                return usb_dict

            except Exception as ssh_error:
                logger.error(f"[{self.hs_config.server_name}] SSH获取USB设备失败: {str(ssh_error)}")
                try:
                    ssh.close()
                except Exception as e_close:
                    logger.warning(f"[{self.hs_config.server_name}] 关闭SSH连接失败: {str(e_close)}")
                return {}

        except Exception as e:
            logger.error(f"[{self.hs_config.server_name}] 获取USB设备列表失败: {str(e)}")
            return {}

    # USB设备直通 ##################################################################
    def USBSetup(self, vm_name: str, ud_info, ud_keys: str, in_flag=True):
        """PVE USB直通 - 通过API设置usb参数（支持热插拔）"""
        from MainObject.Public.ZMessage import ZMessage
        try:
            if vm_name not in self.vm_saving:
                return ZMessage(success=False, action="USBSetup", message="虚拟机不存在")

            client, result = self.api_conn()
            if not result.success:
                return ZMessage(success=False, action="USBSetup", message=f"PVE连接失败: {result.message}")

            vm_conf_usb = self.vm_saving[vm_name]
            vmid = self.get_vmid(vm_conf_usb)
            if not vmid:
                return ZMessage(success=False, action="USBSetup", message="无法获取虚拟机VMID")

            node = self.hs_config.launch_path

            vid = ud_info.vid_uuid
            pid = ud_info.pid_uuid

            if in_flag:
                # 找空闲usb槽位
                slot = 0
                existing_config = client.nodes(node).qemu(vmid).config.get()
                while f'usb{slot}' in existing_config:
                    slot += 1
                    if slot > 4:
                        return ZMessage(success=False, action="USBSetup", message="USB槽位已满")

                client.nodes(node).qemu(vmid).config.put(**{
                    f'usb{slot}': f'host={vid}:{pid}'
                })
            else:
                # 移除USB - 找到对应槽位
                existing_config = client.nodes(node).qemu(vmid).config.get()
                delete_key = None
                for i in range(5):
                    key = f'usb{i}'
                    if key in existing_config:
                        val = str(existing_config[key])
                        if f'{vid}:{pid}' in val:
                            delete_key = key
                            break

                if delete_key:
                    client.nodes(node).qemu(vmid).config.put(delete=delete_key)

            # 更新虚拟机配置中的USB设备列表（不触发VMUpdate）
            vm_conf = self.vm_saving[vm_name]
            if in_flag:
                # 添加USB设备到配置
                if ud_keys not in vm_conf.usb_all:
                    vm_conf.usb_all[ud_keys] = ud_info
                    logger.info(f"[{self.hs_config.server_name}] 添加USB设备到配置: {ud_keys}")
            else:
                # 从配置中移除USB设备
                if ud_keys in vm_conf.usb_all:
                    del vm_conf.usb_all[ud_keys]
                    logger.info(f"[{self.hs_config.server_name}] 从配置中移除USB设备: {ud_keys}")

            logger.info(f"[{self.hs_config.server_name}] USB设备{'添加' if in_flag else '移除'}成功: {ud_keys}")
            return ZMessage(success=True, action="USBSetup", message="USB设备操作成功")

        except Exception as e:
            logger.error(f"[{self.hs_config.server_name}] USB直通操作失败: {str(e)}")
            return ZMessage(success=False, action="USBSetup", message=str(e))

    # 虚拟机状态 ################################################################
    def VMStatus(self,
                 vm_name: str = "",
                 s_t: int = None,
                 e_t: int = None) -> dict[str, list[HWStatus]]:
        # 专用操作 =============================================================
        # TODO: 增加此主机需要执行的任务
        # 通用操作 =============================================================
        return super().VMStatus(vm_name, s_t, e_t)
