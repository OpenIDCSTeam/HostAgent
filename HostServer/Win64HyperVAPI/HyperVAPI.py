# Hyper-V API 实现 ###########################################################
# 通过PowerShell和WinRM远程管理Hyper-V虚拟机
################################################################################

import json
import subprocess
import traceback
import winrm
from typing import Optional, Dict, List, Any
from loguru import logger

from MainObject.Public.ZMessage import ZMessage
from MainObject.Config.VMConfig import VMConfig
from MainObject.Config.HSConfig import HSConfig
from MainObject.Config.VMPowers import VMPowers


# Hyper-V API类 ###############################################################
# 用于管理Hyper-V虚拟机
################################################################################
class HyperVAPI:
    # 初始化Hyper-V API ############################################################
    # :param host: Hyper-V主机地址
    # :param user: 用户名
    # :param password: 密码
    # :param port: WinRM端口（默认5985 HTTP，5986 HTTPS）
    # :param use_ssl: 是否使用SSL
    ################################################################################
    def __init__(self, host: str, user: str, password: str, port: int = 5985, use_ssl: bool = False):
        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self.use_ssl = use_ssl
        self.session: Optional[winrm.Session] = None
        self.is_local = (host in ['localhost', '127.0.0.1', '::1'])

    # 连接到Hyper-V主机 ############################################################
    def connect(self) -> ZMessage:
        try:
            if self.is_local:
                # 本地连接，不需要WinRM
                logger.info("使用本地PowerShell连接")
                return ZMessage(success=True, action="Connect", message="本地连接成功")

            # 远程连接使用WinRM
            protocol = 'https' if self.use_ssl else 'http'
            endpoint = f"{protocol}://{self.host}:{self.port}/wsman"

            self.session = winrm.Session(
                endpoint,
                auth=(self.user, self.password),
                transport='ntlm',
                server_cert_validation='ignore' if self.use_ssl else None
            )

            # 测试连接
            result = self._run_powershell("Get-VMHost")
            if result.success:
                logger.info(f"成功连接到Hyper-V主机: {self.host}")
                return ZMessage(success=True, action="Connect", message="连接成功")
            else:
                return ZMessage(success=False, action="Connect", message=f"连接失败: {result.message}")

        except Exception as e:
            logger.error(f"连接Hyper-V主机失败: {str(e)}")
            return ZMessage(success=False, action="Connect", message=str(e))

    # 断开连接 ####################################################################
    def disconnect(self):
        self.session = None
        logger.info("已断开Hyper-V连接")

    # 执行PowerShell命令 ###########################################################
    # :param command: PowerShell命令
    # :param parse_json: 是否解析JSON输出
    # :return: 执行结果
    ################################################################################
    def _run_powershell(self, command: str, parse_json: bool = False) -> ZMessage:
        try:
            if self.is_local:
                # 本地执行
                logger.info(f"执行本地PowerShell命令: {command}")
                result = subprocess.run(
                    ['powershell', '-Command', command],
                    capture_output=True,
                    text=True,
                    encoding='gbk',
                    errors='replace'
                )

                if result.returncode == 0:
                    output = result.stdout.strip()
                    if parse_json and output:
                        try:
                            data = json.loads(output)
                            return ZMessage(success=True, action="PowerShell", results=data)
                        except json.JSONDecodeError:
                            return ZMessage(success=True, action="PowerShell", message=output)
                    return ZMessage(success=True, action="PowerShell", message=output)
                else:
                    error = result.stderr.strip()
                    logger.error(f"PowerShell命令执行失败: {error}")
                    return ZMessage(success=False, action="PowerShell", message=error)
            else:
                # 远程执行
                if not self.session:
                    return ZMessage(success=False, action="PowerShell", message="未连接到远程主机")

                result = self.session.run_ps(command)

                if result.status_code == 0:
                    output = result.std_out.decode('utf-8').strip()
                    if parse_json and output:
                        try:
                            data = json.loads(output)
                            return ZMessage(success=True, action="PowerShell", results=data)
                        except json.JSONDecodeError:
                            return ZMessage(success=True, action="PowerShell", message=output)
                    return ZMessage(success=True, action="PowerShell", message=output)
                else:
                    error = result.std_err.decode('utf-8').strip()
                    logger.error(f"PowerShell命令执行失败: {error}")
                    return ZMessage(success=False, action="PowerShell", message=error)

        except Exception as e:
            logger.error(f"执行PowerShell命令异常: {str(e)}")
            return ZMessage(success=False, action="PowerShell", message=str(e))

    # 列出所有虚拟机 ###############################################################
    # :param filter_prefix: 名称前缀过滤
    # :return: 虚拟机列表
    ################################################################################
    def list_vms(self, filter_prefix: str = "") -> List[Dict[str, Any]]:
        try:
            command = """
            $vms = Get-VM
            $result = @()
            foreach ($vm in $vms) {
                $hdd = Get-VMHardDiskDrive -VM $vm
                $nic = Get-VMNetworkAdapter -VM $vm
                
                $hdd_info = @()
                if ($hdd) {
                    foreach ($h in $hdd) {
                         $size = 0
                         if ($h.Path -and (Test-Path $h.Path)) {
                             try {
                                 $vhd = Get-VHD -Path $h.Path -ErrorAction SilentlyContinue
                                 if ($vhd) { $size = $vhd.Size }
                             } catch {}
                         }
                         $hdd_info += @{
                             Path = $h.Path
                             Size = $size
                         }
                    }
                }

                $nic_info = @()
                if ($nic) {
                    foreach ($n in $nic) {
                         $nic_info += @{
                             Name = $n.Name
                             MacAddress = $n.MacAddress
                             SwitchName = $n.SwitchName
                             IPAddresses = $n.IPAddresses
                         }
                    }
                }

                $result += @{
                    Name = $vm.Name
                    State = $vm.State
                    ProcessorCount = $vm.ProcessorCount
                    MemoryStartup = $vm.MemoryStartup
                    Path = $vm.Path
                    HardDrives = $hdd_info
                    NetworkAdapters = $nic_info
                }
            }
            $result | ConvertTo-Json -Depth 4
            """
            result = self._run_powershell(command, parse_json=True)

            if not result.success:
                return []

            # 处理返回结果
            if result.results is None:
                return []

            vms = result.results
            if isinstance(vms, dict):
                vms = [vms]
            elif not isinstance(vms, list):
                # 如果是其他类型（如字符串等），视为无效数据
                return []

            # 过滤
            if filter_prefix:
                vms = [vm for vm in vms if isinstance(vm, dict) and vm.get('Name', '').startswith(filter_prefix)]

            # 转换格式
            vm_list = []
            for vm in vms:
                if not isinstance(vm, dict):
                    continue
                vm_list.append({
                    'name': vm.get('Name', ''),
                    'state': vm.get('State', 'Unknown'),
                    'cpu': vm.get('ProcessorCount', 1),
                    'memory_mb': vm.get('MemoryStartup', 0) // (1024 * 1024),
                    'path': vm.get('Path', ''),
                    'HardDrives': vm.get('HardDrives', []),
                    'NetworkAdapters': vm.get('NetworkAdapters', [])
                })

            return vm_list

        except Exception as e:
            logger.error(f"列出虚拟机失败: {str(e)}")
            return []

    # 获取虚拟机详细信息 ###########################################################
    # :param vm_name: 虚拟机名称
    # :return: 虚拟机信息
    ################################################################################
    def get_vm_info(self, vm_name: str) -> Optional[Dict[str, Any]]:
        try:
            command = f"Get-VM -Name '{vm_name}' | Select-Object * | ConvertTo-Json"
            result = self._run_powershell(command, parse_json=True)

            if result.success:
                return result.results
            return None

        except Exception as e:
            logger.error(f"获取虚拟机信息失败: {str(e)}")
            return None

    # 创建虚拟机 ##################################################################
    # :param vm_conf: 虚拟机配置
    # :param hs_config: 主机配置
    # :return: 操作结果
    ################################################################################
    def create_vm(self, vm_conf: VMConfig, hs_config: HSConfig) -> ZMessage:
        try:
            vm_name = vm_conf.vm_uuid
            vm_path = f"{hs_config.system_path}\\{vm_name}"
            vhd_dir = f"{vm_path}\\Virtual Hard Disks"

            # 构建创建命令（不指定交换机）
            # 如果 system_path 为空，则不指定 -Path 参数，让 Hyper-V 使用默认路径
            if hs_config.system_path:
                command = f"""
                New-VM -Name '{vm_name}' `
                    -MemoryStartupBytes {vm_conf.mem_num}MB `
                    -Generation 2 `
                    -Path '{hs_config.system_path}' `
                    -NoVHD

                Set-VM -Name '{vm_name}' -ProcessorCount {vm_conf.cpu_num}
                """
            else:
                return ZMessage(success=False, action="CreateVM",
                                message="主机系统路径为空，无法创建虚拟机")

            # 复制操作系统镜像作为系统盘
            if vm_conf.os_name and hs_config.images_path:
                source_image = f"{hs_config.images_path}\\{vm_conf.os_name}"
                system_disk = f"{vhd_dir}\\{vm_name}_system.vhdx"

                command += f"""
                # 创建虚拟硬盘目录
                New-Item -ItemType Directory -Path '{vhd_dir}' -Force | Out-Null

                # 复制操作系统镜像到_system.vhdx
                Copy-Item -Path '{source_image}' -Destination '{system_disk}' -Force

                # 添加系统盘（SCSI控制器，关联到虚拟机）
                Add-VMHardDiskDrive -VMName '{vm_name}' -Path '{system_disk}' -ControllerType SCSI -ControllerNumber 0 -ControllerLocation 0

                # 关闭安全启动并设置系统盘为第一启动项
                $systemDisk = Get-VMHardDiskDrive -VMName '{vm_name}' | Where-Object {{ $_.Path -eq '{system_disk}' }}
                Set-VMFirmware -VMName '{vm_name}' -EnableSecureBoot Off -FirstBootDevice $systemDisk
                """

            # 如果有硬盘大小配置，创建数据虚拟硬盘
            # if vm_conf.hdd_num > 0:
            #     data_disk = f"{vhd_dir}\\{vm_name}_data.vhdx"
            #     command += f"""
            #     New-VHD -Path '{data_disk}' -SizeBytes {vm_conf.hdd_num}GB -Dynamic
            #     Add-VMHardDiskDrive -VMName '{vm_name}' -Path '{data_disk}' -ControllerType SCSI -ControllerNumber 0 -ControllerLocation 1
            #     """

            # 删除默认网络适配器（Hyper-V默认会创建一个未连接的网卡）
            command += """
            # 删除默认网络适配器（Hyper-V默认会创建一个）
            Get-VMNetworkAdapter -VMName '{vm_name}' | Remove-VMNetworkAdapter
            """

            # 为所有网卡创建网络适配器
            if vm_conf.nic_all and len(vm_conf.nic_all) > 0:
                for nic_key, nic in vm_conf.nic_all.items():
                    # 根据网卡类型确定虚拟交换机
                    nic_switch = None
                    if nic.nic_type == "nat":
                        nic_switch = hs_config.network_nat if hs_config.network_nat else None
                    elif nic.nic_type == "pub":
                        nic_switch = hs_config.network_pub if hs_config.network_pub else None

                    if nic_switch:
                        # 使用配置中的网卡名称
                        nic_name = nic_key
                        add_cmd = f"Add-VMNetworkAdapter -VMName '{vm_name}' -SwitchName '{nic_switch}'"
                        if nic_name:
                            add_cmd += f" -Name '{nic_name}'"
                        command += f"\n{add_cmd}"
                        if nic.mac_addr:
                            if nic_name:
                                command += f"\nSet-VMNetworkAdapter -VMName '{vm_name}' -Name '{nic_name}' -StaticMacAddress '{nic.mac_addr}'"
                            else:
                                command += f"\nSet-VMNetworkAdapter -VMName '{vm_name}' -StaticMacAddress '{nic.mac_addr}'"
                    else:
                        logger.warning(f"网卡 {nic_key} 未找到对应的虚拟交换机配置 (nic_type={nic.nic_type})")

            result = self._run_powershell(command)

            if result.success:
                logger.info(f"虚拟机 {vm_name} 创建成功")
                
                # 如果配置了GPU，添加GPU PV支持 =====================================
                if vm_conf.gpu_num > 0:
                    logger.info(f"虚拟机 {vm_name} 配置了GPU，开始添加GPU PV支持...")
                    
                    # 获取可用的GPU设备列表
                    gpu_devices = self.get_gpu_devices()
                    if gpu_devices and "gpus" in gpu_devices and len(gpu_devices["gpus"]) > 0:
                        # 选择第一个可用的GPU（可以根据gpu_num选择特定GPU）
                        selected_gpu = None
                        for gpu in gpu_devices["gpus"]:
                            if gpu.get("Type") == "Partitionable":
                                available = gpu.get("Available", 0)
                                if available > 0:
                                    selected_gpu = gpu
                                    break
                        
                        if selected_gpu:
                            gpu_name = selected_gpu.get("Name", "")
                            logger.info(f"选择GPU: {gpu_name}")
                            
                            # 添加GPU PV适配器
                            gpu_percentage = 100 // vm_conf.gpu_num if vm_conf.gpu_num > 0 else 100
                            add_result = self.add_gpu_pv(vm_name, gpu_name, gpu_percentage)
                            
                            if add_result.success:
                                logger.info(f"虚拟机 {vm_name} GPU PV适配器添加成功")
                                
                                # 拷贝GPU驱动到虚拟机
                                if vm_conf.os_name:  # 只有在有系统盘时才拷贝驱动
                                    logger.info(f"开始拷贝GPU驱动到虚拟机 {vm_name}...")
                                    copy_result = self.copy_gpu_drivers(vm_name, gpu_name)
                                    
                                    if copy_result.success:
                                        logger.info(f"虚拟机 {vm_name} GPU驱动拷贝成功")
                                    else:
                                        logger.warning(f"虚拟机 {vm_name} GPU驱动拷贝失败: {copy_result.message}")
                            else:
                                logger.warning(f"虚拟机 {vm_name} GPU PV适配器添加失败: {add_result.message}")
                        else:
                            logger.warning(f"虚拟机 {vm_name} 未找到可用的GPU设备")
                    else:
                        logger.warning(f"虚拟机 {vm_name} 系统中没有可用的GPU设备")
                
                return ZMessage(success=True, action="CreateVM", message="虚拟机创建成功")
            else:
                return ZMessage(success=False, action="CreateVM", message=result.message)

        except Exception as e:
            logger.error(f"创建虚拟机失败: {str(e)}")
            return ZMessage(success=False, action="CreateVM", message=str(e))

    # 删除虚拟机 ##################################################################
    # :param vm_name: 虚拟机名称
    # :param remove_files: 是否删除文件
    # :return: 操作结果
    ################################################################################
    def delete_vm(self, vm_name: str, remove_files: bool = True) -> ZMessage:
        try:
            # 先停止虚拟机
            self.power_off(vm_name, force=True)

            # 删除虚拟机
            if remove_files:
                command = f"Remove-VM -Name '{vm_name}' -Force"
            else:
                command = f"Remove-VM -Name '{vm_name}' -Force"

            result = self._run_powershell(command)

            if result.success:
                logger.info(f"虚拟机 {vm_name} 删除成功")
                return ZMessage(success=True, action="DeleteVM", message="虚拟机删除成功")
            else:
                return ZMessage(success=False, action="DeleteVM", message=result.message)

        except Exception as e:
            logger.error(f"删除虚拟机失败: {str(e)}")
            return ZMessage(success=False, action="DeleteVM", message=str(e))

    # 启动虚拟机 ##################################################################
    def power_on(self, vm_name: str) -> ZMessage:
        try:
            command = f"Start-VM -Name '{vm_name}'"
            result = self._run_powershell(command)

            if result.success:
                logger.info(f"虚拟机 {vm_name} 已启动")
                return ZMessage(success=True, action="PowerOn", message="虚拟机已启动")
            else:
                return ZMessage(success=False, action="PowerOn", message=result.message)

        except Exception as e:
            logger.error(f"启动虚拟机失败: {str(e)}")
            return ZMessage(success=False, action="PowerOn", message=str(e))

    # 关闭虚拟机 ##################################################################
    def power_off(self, vm_name: str, force: bool = False) -> ZMessage:
        try:
            if force:
                command = f"Stop-VM -Name '{vm_name}' -Force"
            else:
                command = f"Stop-VM -Name '{vm_name}'"

            result = self._run_powershell(command)

            if result.success:
                logger.info(f"虚拟机 {vm_name} 已关闭")
                return ZMessage(success=True, action="PowerOff", message="虚拟机已关闭")
            else:
                return ZMessage(success=False, action="PowerOff", message=result.message)

        except Exception as e:
            logger.error(f"关闭虚拟机失败: {str(e)}")
            return ZMessage(success=False, action="PowerOff", message=str(e))

    # 暂停虚拟机 ##################################################################
    def suspend(self, vm_name: str) -> ZMessage:
        try:
            command = f"Suspend-VM -Name '{vm_name}'"
            result = self._run_powershell(command)

            if result.success:
                logger.info(f"虚拟机 {vm_name} 已暂停")
                return ZMessage(success=True, action="Suspend", message="虚拟机已暂停")
            else:
                return ZMessage(success=False, action="Suspend", message=result.message)

        except Exception as e:
            logger.error(f"暂停虚拟机失败: {str(e)}")
            return ZMessage(success=False, action="Suspend", message=str(e))

    # 恢复虚拟机 ##################################################################
    def resume(self, vm_name: str) -> ZMessage:
        try:
            command = f"Resume-VM -Name '{vm_name}'"
            result = self._run_powershell(command)

            if result.success:
                logger.info(f"虚拟机 {vm_name} 已恢复")
                return ZMessage(success=True, action="Resume", message="虚拟机已恢复")
            else:
                return ZMessage(success=False, action="Resume", message=result.message)

        except Exception as e:
            logger.error(f"恢复虚拟机失败: {str(e)}")
            return ZMessage(success=False, action="Resume", message=str(e))

    # 重启虚拟机 ##################################################################
    def reset(self, vm_name: str) -> ZMessage:
        try:
            command = f"Restart-VM -Name '{vm_name}' -Force"
            result = self._run_powershell(command)

            if result.success:
                logger.info(f"虚拟机 {vm_name} 已重启")
                return ZMessage(success=True, action="Reset", message="虚拟机已重启")
            else:
                return ZMessage(success=False, action="Reset", message=result.message)

        except Exception as e:
            logger.error(f"重启虚拟机失败: {str(e)}")
            return ZMessage(success=False, action="Reset", message=str(e))

    # 更新虚拟机配置 ###############################################################
    # :param vm_name: 虚拟机名称
    # :param vm_conf: 新配置
    # :return: 操作结果
    ################################################################################
    def update_vm_config(self, vm_name: str, vm_conf: VMConfig) -> ZMessage:
        try:
            command = f"""
            Set-VM -Name '{vm_name}' `
                -ProcessorCount {vm_conf.cpu_num} `
                -MemoryStartupBytes {vm_conf.mem_num}MB
            """

            result = self._run_powershell(command)

            if result.success:
                logger.info(f"虚拟机 {vm_name} 配置已更新")
                return ZMessage(success=True, action="UpdateConfig", message="配置更新成功")
            else:
                return ZMessage(success=False, action="UpdateConfig", message=result.message)

        except Exception as e:
            logger.error(f"更新虚拟机配置失败: {str(e)}")
            return ZMessage(success=False, action="UpdateConfig", message=str(e))

    # 创建快照 ####################################################################
    def create_snapshot(self, vm_name: str, snapshot_name: str, description: str = "") -> ZMessage:
        try:
            command = f"Checkpoint-VM -Name '{vm_name}' -SnapshotName '{snapshot_name}'"
            result = self._run_powershell(command)

            if result.success:
                logger.info(f"虚拟机 {vm_name} 快照 {snapshot_name} 创建成功")
                return ZMessage(success=True, action="CreateSnapshot", message="快照创建成功")
            else:
                return ZMessage(success=False, action="CreateSnapshot", message=result.message)

        except Exception as e:
            logger.error(f"创建快照失败: {str(e)}")
            return ZMessage(success=False, action="CreateSnapshot", message=str(e))

    # 恢复快照 ####################################################################
    def revert_snapshot(self, vm_name: str, snapshot_name: str) -> ZMessage:
        try:
            # 获取恢复前的虚拟机状态
            get_state_command = f"(Get-VM -Name '{vm_name}').State"
            state_result = self._run_powershell(get_state_command)

            was_running = False
            if state_result.success:
                vm_state = state_result.message.strip()
                was_running = vm_state == "Running"
                logger.info(f"恢复快照前虚拟机 {vm_name} 状态: {vm_state}")

            # 恢复快照
            command = f"Restore-VMSnapshot -Name '{snapshot_name}' -VMName '{vm_name}' -Confirm:$false"
            result = self._run_powershell(command)

            if result.success:
                logger.info(f"虚拟机 {vm_name} 已恢复到快照 {snapshot_name}")

                # 如果恢复前是运行状态，则自动开机
                if was_running:
                    logger.info(f"检测到恢复前虚拟机 {vm_name} 为运行状态，正在自动开机...")
                    import time
                    time.sleep(2)  # 等待快照恢复完全完成

                    power_on_result = self.power_on(vm_name)
                    if power_on_result.success:
                        logger.info(f"虚拟机 {vm_name} 已自动开机")
                        return ZMessage(success=True, action="RevertSnapshot",
                                        message="快照恢复成功，虚拟机已自动开机")
                    else:
                        logger.warning(f"虚拟机 {vm_name} 自动开机失败: {power_on_result.message}")
                        return ZMessage(success=True, action="RevertSnapshot",
                                        message=f"快照恢复成功，但自动开机失败: {power_on_result.message}")

                return ZMessage(success=True, action="RevertSnapshot", message="快照恢复成功")
            else:
                return ZMessage(success=False, action="RevertSnapshot", message=result.message)

        except Exception as e:
            logger.error(f"恢复快照失败: {str(e)}")
            return ZMessage(success=False, action="RevertSnapshot", message=str(e))

    # 删除快照 ####################################################################
    def delete_snapshot(self, vm_name: str, snapshot_name: str) -> ZMessage:
        try:
            command = f"Remove-VMSnapshot -VMName '{vm_name}' -Name '{snapshot_name}' -Confirm:$false"
            result = self._run_powershell(command)

            if result.success:
                logger.info(f"虚拟机 {vm_name} 快照 {snapshot_name} 已删除")
                return ZMessage(success=True, action="DeleteSnapshot", message="快照删除成功")
            else:
                return ZMessage(success=False, action="DeleteSnapshot", message=result.message)

        except Exception as e:
            logger.error(f"删除快照失败: {str(e)}")
            return ZMessage(success=False, action="DeleteSnapshot", message=str(e))

    # 添加虚拟硬盘 #################################################################
    def add_disk(self, vm_name: str, size_gb: int, disk_name: str) -> ZMessage:
        try:
            # 获取虚拟机路径
            vm_info = self.get_vm_info(vm_name)
            if not vm_info:
                return ZMessage(success=False, action="AddDisk", message="无法获取虚拟机信息")

            vm_path = vm_info.get('Path', '')
            vhd_path = f"{vm_path}\\Virtual Hard Disks\\{disk_name}.vhdx"

            command = f"""
            New-VHD -Path '{vhd_path}' -SizeBytes {size_gb}GB -Dynamic
            Add-VMHardDiskDrive -VMName '{vm_name}' -Path '{vhd_path}'
            """

            result = self._run_powershell(command)

            if result.success:
                logger.info(f"虚拟机 {vm_name} 添加磁盘 {disk_name} 成功")
                return ZMessage(success=True, action="AddDisk", message="磁盘添加成功")
            else:
                return ZMessage(success=False, action="AddDisk", message=result.message)

        except Exception as e:
            logger.error(f"添加磁盘失败: {str(e)}")
            return ZMessage(success=False, action="AddDisk", message=str(e))

    # 移除磁盘 =====================================================================
    def remove_disk(self, vm_name: str, disk_name: str) -> ZMessage:
        """从虚拟机中移除指定的磁盘"""
        try:
            # 获取虚拟机路径 =======================================================
            vm_info = self.get_vm_info(vm_name)
            if not vm_info:
                return ZMessage(success=False, action="RemoveDisk", message="无法获取虚拟机信息")

            vm_path = vm_info.get('Path', '')
            vhd_path = f"{vm_path}\\Virtual Hard Disks\\{disk_name}.vhdx"

            # 从虚拟机中移除磁盘 ===================================================
            command = f"""
            Get-VMHardDiskDrive -VMName '{vm_name}' | Where-Object {{$_.Path -eq '{vhd_path}'}} | Remove-VMHardDiskDrive
            """

            result = self._run_powershell(command)

            if result.success:
                logger.info(f"虚拟机 {vm_name} 移除磁盘 {disk_name} 成功")
                return ZMessage(success=True, action="RemoveDisk", message="磁盘移除成功")
            else:
                return ZMessage(success=False, action="RemoveDisk", message=result.message)

        except Exception as e:
            # 异常处理 =============================================================
            logger.error(f"移除磁盘失败: {str(e)}")
            traceback.print_exc()
            return ZMessage(success=False, action="RemoveDisk", message=str(e))

    # 挂载ISO #####################################################################
    def attach_iso(self, vm_name: str, iso_path: str) -> ZMessage:
        try:
            command = f"Add-VMDvdDrive -VMName '{vm_name}' -Path '{iso_path}'"
            result = self._run_powershell(command)

            if result.success:
                logger.info(f"虚拟机 {vm_name} ISO挂载成功")
                return ZMessage(success=True, action="AttachISO", message="ISO挂载成功")
            else:
                return ZMessage(success=False, action="AttachISO", message=result.message)

        except Exception as e:
            logger.error(f"挂载ISO失败: {str(e)}")
            return ZMessage(success=False, action="AttachISO", message=str(e))

    # 卸载ISO #####################################################################
    def detach_iso(self, vm_name: str) -> ZMessage:
        try:
            command = f"Get-VMDvdDrive -VMName '{vm_name}' | Remove-VMDvdDrive"
            result = self._run_powershell(command)

            if result.success:
                logger.info(f"虚拟机 {vm_name} ISO卸载成功")
                return ZMessage(success=True, action="DetachISO", message="ISO卸载成功")
            else:
                return ZMessage(success=False, action="DetachISO", message=result.message)

        except Exception as e:
            logger.error(f"卸载ISO失败: {str(e)}")
            return ZMessage(success=False, action="DetachISO", message=str(e))

    # 获取VNC端口 ##################################################################
    # Hyper-V使用增强会话模式，不是传统VNC
    # :param vm_name: 虚拟机名称
    # :return: 端口号
    ################################################################################
    def get_vnc_port(self, vm_name: str) -> Optional[int]:
        # Hyper-V不使用VNC，而是使用增强会话模式或RDP
        # 这里返回None，表示不支持VNC
        logger.warning("Hyper-V不支持VNC，请使用增强会话模式或RDP")
        return None

    # 设置网络适配器 ###############################################################
    # :param vm_name: 虚拟机名称
    # :param switch_name: 虚拟交换机名称
    # :param mac_address: MAC地址（可选）
    # :param adapter_name: 网卡名称（可选）
    # :return: 操作结果
    ################################################################################
    def set_network_adapter(self, vm_name: str, switch_name: str, mac_address: str = None, adapter_name: str = "") -> ZMessage:
        try:
            # 获取指定名称的网络适配器
            if adapter_name:
                get_cmd = f"Get-VMNetworkAdapter -VMName '{vm_name}' -Name '{adapter_name}' | Connect-VMNetworkAdapter -SwitchName '{switch_name}'"
            else:
                get_cmd = f"Get-VMNetworkAdapter -VMName '{vm_name}' | Select-Object -First 1 | Connect-VMNetworkAdapter -SwitchName '{switch_name}'"

            command = get_cmd

            if mac_address:
                if adapter_name:
                    command += f"\nSet-VMNetworkAdapter -VMName '{vm_name}' -Name '{adapter_name}' -StaticMacAddress '{mac_address}'"
                else:
                    command += f"\nSet-VMNetworkAdapter -VMName '{vm_name}' -StaticMacAddress '{mac_address}'"

            result = self._run_powershell(command)

            if result.success:
                logger.info(f"虚拟机 {vm_name} 网络适配器配置成功")
                return ZMessage(success=True, action="SetNetwork", message="网络配置成功")
            else:
                return ZMessage(success=False, action="SetNetwork", message=result.message)

        except Exception as e:
            logger.error(f"配置网络适配器失败: {str(e)}")
            return ZMessage(success=False, action="SetNetwork", message=str(e))

    # 添加网络适配器 ###############################################################
    # :param vm_name: 虚拟机名称
    # :param switch_name: 虚拟交换机名称
    # :param mac_address: MAC地址（可选）
    # :param adapter_name: 网卡名称（可选）
    # :return: 操作结果
    ################################################################################
    def add_network_adapter(self, vm_name: str, switch_name: str, mac_address: str = None, adapter_name: str = "") -> ZMessage:
        try:
            if adapter_name:
                # 有网卡名称：添加时直接指定名称
                add_cmd = f"Add-VMNetworkAdapter -VMName '{vm_name}' -SwitchName '{switch_name}' -Name '{adapter_name}'"

                command = add_cmd

                if mac_address:
                    command += f"\nSet-VMNetworkAdapter -VMName '{vm_name}' -Name '{adapter_name}' -StaticMacAddress '{mac_address}'"
            else:
                # 无网卡名称：先添加，然后获取并设置MAC地址
                command = f"$newAdapter = Add-VMNetworkAdapter -VMName '{vm_name}' -SwitchName '{switch_name}'"

                if mac_address:
                    command += f"\nSet-VMNetworkAdapter -VMNetworkAdapter $newAdapter -StaticMacAddress '{mac_address}'"

            result = self._run_powershell(command)

            if result.success:
                logger.info(f"虚拟机 {vm_name} 网络适配器添加成功")
                return ZMessage(success=True, action="AddNetwork", message="网络适配器添加成功")
            else:
                return ZMessage(success=False, action="AddNetwork", message=result.message)

        except Exception as e:
            logger.error(f"添加网络适配器失败: {str(e)}")
            return ZMessage(success=False, action="AddNetwork", message=str(e))

    # 删除网络适配器 ###############################################################
    # :param vm_name: 虚拟机名称
    # :param adapter_name: 网卡名称（可选，为空则删除所有）
    # :return: 操作结果
    ################################################################################
    def remove_network_adapter(self, vm_name: str, adapter_name: str = "") -> ZMessage:
        try:
            if adapter_name:
                command = f"Get-VMNetworkAdapter -VMName '{vm_name}' -Name '{adapter_name}' | Remove-VMNetworkAdapter"
            else:
                command = f"Get-VMNetworkAdapter -VMName '{vm_name}' | Remove-VMNetworkAdapter"

            result = self._run_powershell(command)

            if result.success:
                logger.info(f"虚拟机 {vm_name} 网络适配器删除成功")
                return ZMessage(success=True, action="RemoveNetwork", message="网络适配器删除成功")
            else:
                return ZMessage(success=False, action="RemoveNetwork", message=result.message)

        except Exception as e:
            logger.error(f"删除网络适配器失败: {str(e)}")
            return ZMessage(success=False, action="RemoveNetwork", message=str(e))

    # 获取主机状态 #################################################################
    def get_host_status(self) -> Optional[Dict[str, Any]]:
        try:
            command = """
            $host_info = Get-VMHost
            $cpu = Get-Counter '\\Processor(_Total)\\% Processor Time' | Select-Object -ExpandProperty CounterSamples | Select-Object -ExpandProperty CookedValue
            $mem = Get-Counter '\\Memory\\% Committed Bytes In Use' | Select-Object -ExpandProperty CounterSamples | Select-Object -ExpandProperty CookedValue

            @{
                cpu_usage_percent = [math]::Round($cpu, 2)
                memory_usage_percent = [math]::Round($mem, 2)
            } | ConvertTo-Json
            """

            result = self._run_powershell(command, parse_json=True)

            if result.success:
                return result.results
            return None

        except Exception as e:
            logger.error(f"获取主机状态失败: {str(e)}")
            return None

    # 磁盘扩容 #####################################################################
    # :param vm_name: 虚拟机名称
    # :param disk_path: 磁盘文件路径
    # :param new_size_gb: 新的磁盘大小（GB）
    # :return: 操作结果
    ################################################################################
    def resize_disk(self, vm_name: str, disk_path: str, new_size_gb: int) -> ZMessage:
        try:
            # 检查磁盘是否存在 =====================================================
            command = f"""
            if (Test-Path '{disk_path}') {{
                $vhd = Get-VHD -Path '{disk_path}'
                $currentSizeGB = [math]::Round($vhd.Size / 1GB, 2)
                Write-Output "CurrentSize:$currentSizeGB"
            }} else {{
                Write-Error "磁盘文件不存在"
            }}
            """
            
            result = self._run_powershell(command)
            if not result.success:
                return ZMessage(success=False, action="ResizeDisk", message="磁盘文件不存在")

            # 执行磁盘扩容 =========================================================
            command = f"Resize-VHD -Path '{disk_path}' -SizeBytes {new_size_gb}GB"
            result = self._run_powershell(command)

            if result.success:
                logger.info(f"虚拟机 {vm_name} 磁盘扩容成功: {disk_path} -> {new_size_gb}GB")
                return ZMessage(success=True, action="ResizeDisk", message="磁盘扩容成功")
            else:
                return ZMessage(success=False, action="ResizeDisk", message=result.message)

        except Exception as e:
            logger.error(f"磁盘扩容失败: {str(e)}")
            logger.error(traceback.format_exc())
            return ZMessage(success=False, action="ResizeDisk", message=str(e))

    # 卸载虚拟硬盘 #################################################################
    # :param vm_name: 虚拟机名称
    # :param disk_path: 磁盘文件路径
    # :return: 操作结果
    ################################################################################
    def detach_disk(self, vm_name: str, disk_path: str) -> ZMessage:
        try:
            # 查找并移除指定路径的磁盘 =============================================
            command = f"""
            $disk = Get-VMHardDiskDrive -VMName '{vm_name}' | Where-Object {{$_.Path -eq '{disk_path}'}}
            if ($disk) {{
                Remove-VMHardDiskDrive -VMName '{vm_name}' -ControllerType $disk.ControllerType -ControllerNumber $disk.ControllerNumber -ControllerLocation $disk.ControllerLocation
                Write-Output "磁盘卸载成功"
            }} else {{
                Write-Error "未找到指定磁盘"
            }}
            """
            
            result = self._run_powershell(command)

            if result.success:
                logger.info(f"虚拟机 {vm_name} 磁盘卸载成功: {disk_path}")
                return ZMessage(success=True, action="DetachDisk", message="磁盘卸载成功")
            else:
                return ZMessage(success=False, action="DetachDisk", message=result.message)

        except Exception as e:
            logger.error(f"卸载磁盘失败: {str(e)}")
            logger.error(traceback.format_exc())
            return ZMessage(success=False, action="DetachDisk", message=str(e))

    # 查询GPU设备 ##################################################################
    # :return: GPU设备列表
    ################################################################################
    def get_gpu_devices(self) -> Dict[str, Any]:
        try:
            # 查询GPU分区适配器（用于GPU虚拟化） ==================================
            command = """
            $gpus = @()
            
            # 查询物理GPU设备
            $physicalGPUs = Get-VMHostPartitionableGpu -ErrorAction SilentlyContinue
            if ($physicalGPUs) {
                foreach ($gpu in $physicalGPUs) {
                    $gpus += @{
                        Name = $gpu.Name
                        Type = "Partitionable"
                        Available = $gpu.PartitionCount - $gpu.PartitionsInUse
                        Total = $gpu.PartitionCount
                    }
                }
            }
            
            # 查询DDA（离散设备分配）GPU
            $ddaGPUs = Get-PnpDevice -Class Display -ErrorAction SilentlyContinue
            if ($ddaGPUs) {
                foreach ($gpu in $ddaGPUs) {
                    $gpus += @{
                        Name = $gpu.FriendlyName
                        Type = "DDA"
                        Status = $gpu.Status
                        InstanceId = $gpu.InstanceId
                    }
                }
            }
            
            @{gpus = $gpus} | ConvertTo-Json -Depth 3
            """
            
            result = self._run_powershell(command, parse_json=True)

            if result.success and result.results:
                logger.info("GPU设备查询成功")
                return result.results
            else:
                logger.warning("未找到GPU设备或不支持GPU虚拟化")
                return {"gpus": []}

        except Exception as e:
            logger.error(f"查询GPU设备失败: {str(e)}")
            logger.error(traceback.format_exc())
            return {"gpus": []}

    # 添加GPU PV适配器 ##############################################################
    # :param vm_name: 虚拟机名称
    # :param gpu_name: GPU设备名称
    # :param gpu_percentage: GPU资源分配百分比（默认100）
    # :return: ZMessage
    ################################################################################
    def add_gpu_pv(self, vm_name: str, gpu_name: str, gpu_percentage: int = 100) -> ZMessage:
        """
        为虚拟机添加GPU PV（分区虚拟化）适配器
        
        Args:
            vm_name: 虚拟机名称
            gpu_name: GPU设备名称
            gpu_percentage: GPU资源分配百分比（默认100）
            
        Returns:
            ZMessage: 操作结果
        """
        try:
            # 调用UpdatePV.ps1脚本添加GPU PV适配器
            script_path = f"{self._get_script_dir()}\\UpdatePV.ps1"
            
            command = f"""
            # 确保虚拟机已关闭
            $VM = Get-VM -Name '{vm_name}'
            if ($VM.State -ne 'Off') {{
                Stop-VM -Name '{vm_name}' -Force
                Start-Sleep -Seconds 3
            }}
            
            # 添加GPU分区适配器
            Add-VMGpuPartitionAdapter -VMName '{vm_name}'
            
            # 设置GPU资源分配
            $devider = [math]::round(100 / {gpu_percentage}, 2)
            
            Set-VMGpuPartitionAdapter -VMName '{vm_name}' `
                -MinPartitionVRAM ([math]::round(1000000000 / $devider)) `
                -MaxPartitionVRAM ([math]::round(1000000000 / $devider)) `
                -OptimalPartitionVRAM ([math]::round(1000000000 / $devider))
            
            Set-VMGPUPartitionAdapter -VMName '{vm_name}' `
                -MinPartitionEncode ([math]::round(18446744073709551615 / $devider)) `
                -MaxPartitionEncode ([math]::round(18446744073709551615 / $devider)) `
                -OptimalPartitionEncode ([math]::round(18446744073709551615 / $devider))
            
            Set-VMGpuPartitionAdapter -VMName '{vm_name}' `
                -MinPartitionDecode ([math]::round(1000000000 / $devider)) `
                -MaxPartitionDecode ([math]::round(1000000000 / $devider)) `
                -OptimalPartitionDecode ([math]::round(1000000000 / $devider))
            
            Set-VMGpuPartitionAdapter -VMName '{vm_name}' `
                -MinPartitionCompute ([math]::round(1000000000 / $devider)) `
                -MaxPartitionCompute ([math]::round(1000000000 / $devider)) `
                -OptimalPartitionCompute ([math]::round(1000000000 / $devider))
            
            Write-Output "GPU PV适配器添加成功"
            """
            
            result = self._run_powershell(command)
            
            if result.success:
                logger.info(f"虚拟机 {vm_name} GPU PV适配器添加成功")
                return ZMessage(success=True, action="AddGPUPV", message="GPU PV适配器添加成功")
            else:
                logger.error(f"添加GPU PV适配器失败: {result.message}")
                return ZMessage(success=False, action="AddGPUPV", message=result.message)
                
        except Exception as e:
            logger.error(f"添加GPU PV适配器失败: {str(e)}")
            logger.error(traceback.format_exc())
            return ZMessage(success=False, action="AddGPUPV", message=str(e))

    # 拷贝GPU驱动到虚拟机 ###########################################################
    # :param vm_name: 虚拟机名称
    # :param gpu_name: GPU设备名称
    # :return: ZMessage
    ################################################################################
    def copy_gpu_drivers(self, vm_name: str, gpu_name: str) -> ZMessage:
        """
        拷贝GPU驱动文件到虚拟机
        
        Args:
            vm_name: 虚拟机名称
            gpu_name: GPU设备名称
            
        Returns:
            ZMessage: 操作结果
        """
        try:
            # 调用UpdateDS.ps1脚本拷贝驱动
            script_path = f"{self._get_script_dir()}\\UpdateDS.ps1"
            
            command = f"""
            # 确保虚拟机已关闭
            $VM = Get-VM -Name '{vm_name}'
            if ($VM.State -ne 'Off') {{
                Stop-VM -Name '{vm_name}' -Force
                Start-Sleep -Seconds 3
            }}
            
            # 获取虚拟机的VHD路径
            $VHD = Get-VHD -VMId $VM.VMId
            
            # 挂载VHD
            $DriveLetter = (Mount-VHD -Path $VHD.Path -PassThru | Get-Disk | Get-Partition | Where-Object {{ $_.Type -eq 'Basic' -or $_.Type -eq 'NTFS' }} | Get-Volume | ForEach-Object DriveLetter)
            
            if (-not $DriveLetter) {{
                throw "无法挂载虚拟硬盘"
            }}
            
            # 拷贝GPU驱动文件
            $HostDriverPath = "C:\\Windows\\System32\\DriverStore\\FileRepository"
            $VMDriverPath = "$($DriveLetter):\\Windows\\System32\\HostDriverStore"
            
            # 创建目标目录
            New-Item -ItemType Directory -Path $VMDriverPath -Force | Out-Null
            
            # 查找GPU相关驱动
            $GPUDrivers = Get-ChildItem -Path $HostDriverPath -Recurse -Filter "*.inf" | Where-Object {{ $_.FullName -match "nv_" -or $_.FullName -match "amd" -or $_.FullName -match "igdlh" }}
            
            foreach ($driver in $GPUDrivers) {{
                $driverDir = $driver.Directory.FullName
                $targetDir = $VMDriverPath + "\\" + $driver.Directory.Name
                
                if (-not (Test-Path $targetDir)) {{
                    Copy-Item -Path $driverDir -Destination $VMDriverPath -Recurse -Force
                    Write-Output "已拷贝驱动: $($driver.Directory.Name)"
                }}
            }}
            
            # 卸载VHD
            Dismount-VHD -Path $VHD.Path
            
            Write-Output "GPU驱动拷贝成功"
            """
            
            result = self._run_powershell(command)
            
            if result.success:
                logger.info(f"虚拟机 {vm_name} GPU驱动拷贝成功")
                return ZMessage(success=True, action="CopyGPUDrivers", message="GPU驱动拷贝成功")
            else:
                logger.error(f"拷贝GPU驱动失败: {result.message}")
                return ZMessage(success=False, action="CopyGPUDrivers", message=result.message)
                
        except Exception as e:
            logger.error(f"拷贝GPU驱动失败: {str(e)}")
            logger.error(traceback.format_exc())
            return ZMessage(success=False, action="CopyGPUDrivers", message=str(e))

    # 获取脚本目录 ##################################################################
    # :return: 脚本目录路径
    ################################################################################
    def _get_script_dir(self) -> str:
        """获取hypervgpus脚本目录路径"""
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(current_dir)
        script_dir = os.path.join(parent_dir, "..", "HostConfig", "hypervgpus")
        return os.path.abspath(script_dir)

    # 检查磁盘信息 #################################################################
    # :param disk_path: 磁盘文件路径
    # :return: 磁盘信息字典
    ################################################################################
    def get_disk_info(self, disk_path: str) -> Optional[Dict[str, Any]]:
        try:
            # 获取VHD/VHDX文件信息 =================================================
            command = f"""
            if (Test-Path '{disk_path}') {{
                $vhd = Get-VHD -Path '{disk_path}'
                @{{
                    Path = $vhd.Path
                    VhdFormat = $vhd.VhdFormat
                    VhdType = $vhd.VhdType
                    FileSize = $vhd.FileSize
                    Size = $vhd.Size
                    MinimumSize = $vhd.MinimumSize
                    Attached = $vhd.Attached
                    DiskNumber = $vhd.DiskNumber
                    FragmentationPercentage = $vhd.FragmentationPercentage
                }} | ConvertTo-Json
            }} else {{
                Write-Error "磁盘文件不存在"
            }}
            """
            
            result = self._run_powershell(command, parse_json=True)

            if result.success and result.results:
                logger.info(f"磁盘信息查询成功: {disk_path}")
                return result.results
            else:
                logger.warning(f"磁盘文件不存在或查询失败: {disk_path}")
                return None

        except Exception as e:
            logger.error(f"检查磁盘信息失败: {str(e)}")
            logger.error(traceback.format_exc())
            return None

    # 移动磁盘文件 #################################################################
    # :param old_path: 原磁盘路径
    # :param new_path: 新磁盘路径
    # :return: 操作结果
    ################################################################################
    def move_disk_file(self, old_path: str, new_path: str) -> ZMessage:
        try:
            # 检查源文件是否存在 ===================================================
            command = f"""
            if (Test-Path '{old_path}') {{
                # 确保目标目录存在
                $targetDir = Split-Path '{new_path}' -Parent
                if (-not (Test-Path $targetDir)) {{
                    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
                }}
                
                # 移动文件
                Move-Item -Path '{old_path}' -Destination '{new_path}' -Force
                Write-Output "磁盘文件移动成功"
            }} else {{
                Write-Error "源磁盘文件不存在"
            }}
            """
            
            result = self._run_powershell(command)

            if result.success:
                logger.info(f"磁盘文件移动成功: {old_path} -> {new_path}")
                return ZMessage(success=True, action="MoveDisk", message="磁盘文件移动成功")
            else:
                return ZMessage(success=False, action="MoveDisk", message=result.message)

        except Exception as e:
            logger.error(f"移动磁盘文件失败: {str(e)}")
            logger.error(traceback.format_exc())
            return ZMessage(success=False, action="MoveDisk", message=str(e))

    # 删除磁盘文件 #################################################################
    # :param disk_path: 磁盘文件路径
    # :return: 操作结果
    ################################################################################
    def delete_disk_file(self, disk_path: str) -> ZMessage:
        try:
            # 删除磁盘文件 =========================================================
            command = f"""
            if (Test-Path '{disk_path}') {{
                Remove-Item -Path '{disk_path}' -Force
                Write-Output "磁盘文件删除成功"
            }} else {{
                Write-Output "磁盘文件不存在，无需删除"
            }}
            """
            
            result = self._run_powershell(command)

            if result.success:
                logger.info(f"磁盘文件删除成功: {disk_path}")
                return ZMessage(success=True, action="DeleteDisk", message="磁盘文件删除成功")
            else:
                return ZMessage(success=False, action="DeleteDisk", message=result.message)

        except Exception as e:
            logger.error(f"删除磁盘文件失败: {str(e)}")
            logger.error(traceback.format_exc())
            return ZMessage(success=False, action="DeleteDisk", message=str(e))

    # 设置虚拟机密码 ###############################################################
    # :param vm_name: 虚拟机名称
    # :param username: 用户名（默认Administrator）
    # :param password: 新密码
    # :return: 操作结果
    ################################################################################
    def set_vm_password(self, vm_name: str, username: str, password: str) -> ZMessage:
        try:
            # 检查虚拟机是否运行 ===================================================
            vm_info = self.get_vm_info(vm_name)
            if not vm_info:
                return ZMessage(success=False, action="SetPassword", message=f"虚拟机 {vm_name} 不存在")
            
            if vm_info.get('State') != 'Running':
                return ZMessage(success=False, action="SetPassword", message=f"虚拟机 {vm_name} 未运行，无法设置密码")

            # 使用PowerShell Direct设置密码 ========================================
            # PowerShell Direct允许在虚拟机内执行命令，无需网络连接
            command = f"""
            $VMName = '{vm_name}'
            $Username = '{username}'
            $Password = '{password}'
            
            try {{
                # 创建凭据对象（使用虚拟机当前凭据）
                $SecurePassword = ConvertTo-SecureString $Password -AsPlainText -Force
                
                # 使用Invoke-Command在虚拟机内执行密码修改命令
                $ScriptBlock = {{
                    param($User, $Pass)
                    $SecPass = ConvertTo-SecureString $Pass -AsPlainText -Force
                    $UserAccount = Get-LocalUser -Name $User -ErrorAction SilentlyContinue
                    if ($UserAccount) {{
                        $UserAccount | Set-LocalUser -Password $SecPass
                        Write-Output "密码设置成功"
                    }} else {{
                        Write-Output "用户不存在: $User"
                    }}
                }}
                
                # 尝试使用PowerShell Direct
                Invoke-Command -VMName $VMName -ScriptBlock $ScriptBlock -ArgumentList $Username, $Password -ErrorAction Stop
                
            }} catch {{
                Write-Error $_.Exception.Message
            }}
            """
            
            result = self._run_powershell(command)

            if result.success and "密码设置成功" in result.message:
                logger.info(f"虚拟机 {vm_name} 密码设置成功")
                return ZMessage(success=True, action="SetPassword", message="密码设置成功")
            else:
                return ZMessage(success=False, action="SetPassword", message=result.message)

        except Exception as e:
            logger.error(f"设置虚拟机密码失败: {str(e)}")
            logger.error(traceback.format_exc())
            return ZMessage(success=False, action="SetPassword", message=str(e))
