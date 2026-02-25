import os
import ssl
import time
from typing import Optional, List, Dict, Any
from loguru import logger

try:
    from pyVim.connect import SmartConnect, Disconnect
    from pyVim.task import WaitForTask
    from pyVmomi import vim, vmodl
except ImportError:
    logger.error("pyvmomi库未安装，请运行: pip install pyvmomi")
    raise

from MainObject.Config.HSConfig import HSConfig
from MainObject.Config.VMConfig import VMConfig
from MainObject.Config.VMPowers import VMPowers
from MainObject.Public.ZMessage import ZMessage


class vSphereAPI:
    """vSphere ESXi API封装类"""

    def __init__(self, host: str, user: str, password: str, port: int = 443,
                 datastore_name: str = "datastore1"):
        """
        初始化vSphere API连接
        
        :param host: ESXi主机地址
        :param user: 用户名
        :param password: 密码
        :param port: API端口，默认443
        :param datastore_name: 数据存储名称
        """
        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self.datastore_name = datastore_name
        self.si = None  # ServiceInstance
        self.content = None

    def connect(self) -> ZMessage:
        """连接到ESXi主机"""
        try:
            # 禁用SSL证书验证（生产环境建议启用）
            context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
            context.verify_mode = ssl.CERT_NONE

            # 连接到ESXi
            self.si = SmartConnect(
                host=self.host,
                user=self.user,
                pwd=self.password,
                port=self.port,
                sslContext=context
            )

            if not self.si:
                return ZMessage(success=False, action="connect",
                                message="无法连接到ESXi主机")

            self.content = self.si.RetrieveContent()
            # logger.info(f"成功连接到ESXi主机: {self.host}")
            return ZMessage(success=True, action="connect",
                            message="连接成功")

        except Exception as e:
            logger.error(f"连接ESXi失败: {str(e)}")
            return ZMessage(success=False, action="connect",
                            message=f"连接失败: {str(e)}")

    def disconnect(self) -> ZMessage:
        """断开与ESXi的连接"""
        try:
            if self.si:
                Disconnect(self.si)
                self.si = None
                self.content = None
                # logger.info(f"已断开与ESXi主机的连接: {self.host}")
            return ZMessage(success=True, action="disconnect",
                            message="断开连接成功")
        except Exception as e:
            logger.error(f"断开连接失败: {str(e)}")
            return ZMessage(success=False, action="disconnect",
                            message=f"断开连接失败: {str(e)}")

    def _get_obj(self, vimtype, name: str = None):
        """
        获取vSphere对象
        
        :param vimtype: 对象类型（如vim.VirtualMachine）
        :param name: 对象名称，如果为None则返回所有对象
        :return: 对象或对象列表
        """
        if not self.content:
            return None

        container = self.content.viewManager.CreateContainerView(
            self.content.rootFolder, [vimtype], True)

        obj_list = container.view
        container.Destroy()

        if name:
            for obj in obj_list:
                if obj.name == name:
                    return obj
            return None
        return obj_list

    def _wait_for_task(self, task) -> ZMessage:
        """等待任务完成"""
        try:
            WaitForTask(task)
            if task.info.state == vim.TaskInfo.State.success:
                return ZMessage(success=True, action="task",
                                message="任务执行成功")
            else:
                error_msg = str(task.info.error) if task.info.error else "未知错误"
                return ZMessage(success=False, action="task",
                                message=f"任务失败: {error_msg}")
        except Exception as e:
            return ZMessage(success=False, action="task",
                            message=f"任务执行异常: {str(e)}")

    def get_vm(self, vm_name: str):
        """获取虚拟机对象"""
        return self._get_obj(vim.VirtualMachine, vm_name)

    def list_vms(self, filter_prefix: str = "") -> List[Dict[str, Any]]:
        """
        列出所有虚拟机
        
        :param filter_prefix: 名称前缀过滤
        :return: 虚拟机信息列表
        """
        vms = self._get_obj(vim.VirtualMachine)
        vm_list = []

        for vm in vms:
            if filter_prefix and not vm.name.startswith(filter_prefix):
                continue

            vm_info = {
                "name": vm.name,
                "power_state": vm.runtime.powerState,
                "guest_os": vm.config.guestFullName if vm.config else "Unknown",
                "cpu": vm.config.hardware.numCPU if vm.config else 0,
                "memory_mb": vm.config.hardware.memoryMB if vm.config else 0,
            }
            vm_list.append(vm_info)

        return vm_list

    def get_datastore(self, datastore_name: str = None):
        """获取数据存储对象"""
        ds_name = datastore_name or self.datastore_name
        return self._get_obj(vim.Datastore, ds_name)

    def get_resource_pool(self):
        """获取资源池"""
        host = self._get_obj(vim.HostSystem)
        if host and len(host) > 0:
            return host[0].parent.resourcePool
        return None

    def get_network(self, network_name: str):
        """获取网络对象"""
        networks = self._get_obj(vim.Network)
        for network in networks:
            if network.name == network_name:
                return network
        return None

    def create_vm(self, vm_conf: VMConfig, hs_config: HSConfig) -> ZMessage:
        """
        创建虚拟机
        
        :param vm_conf: 虚拟机配置
        :param hs_config: 主机配置
        :return: 操作结果
        """
        try:
            # 获取必要的对象
            datastore = self.get_datastore()
            if not datastore:
                return ZMessage(success=False, action="create_vm",
                                message=f"数据存储 {self.datastore_name} 不存在")

            resource_pool = self.get_resource_pool()
            if not resource_pool:
                return ZMessage(success=False, action="create_vm",
                                message="无法获取资源池")

            # 获取虚拟机文件夹
            vm_folder = self.content.rootFolder.childEntity[0].vmFolder

            # 创建虚拟机配置规格
            config_spec = vim.vm.ConfigSpec()
            config_spec.name = vm_conf.vm_uuid
            config_spec.memoryMB = vm_conf.mem_num
            config_spec.numCPUs = vm_conf.cpu_num
            config_spec.numCoresPerSocket = vm_conf.cpu_num
            config_spec.guestId = self._get_guest_id(vm_conf.os_name)

            # 设置UEFI固件
            config_spec.firmware = "efi"

            # ===== 旧的VNC远程桌面配置（已注释，改用WebMKS） =====
            # # 配置VNC远程桌面访问
            # # 从vm_conf获取VNC端口，如果没有则使用默认端口
            # config_spec.extraConfig = []
            #
            # # 基础系统配置
            # config_spec.extraConfig.append(
            #     vim.option.OptionValue(key='sched.cpu.latencySensitivity', value='normal')
            # )
            # config_spec.extraConfig.append(
            #     vim.option.OptionValue(key='tools.guest.desktop.autolock', value='TRUE')
            # )
            # config_spec.extraConfig.append(
            #     vim.option.OptionValue(key='hpet0.present', value='TRUE')
            # )
            # config_spec.extraConfig.append(
            #     vim.option.OptionValue(key='cpuid.coresPerSocket', value=str(vm_conf.cpu_num))
            # )
            # # VNC远程桌面配置
            # vnc_port = vm_conf.vc_port if hasattr(vm_conf, 'vc_port') and vm_conf.vc_port else 5900
            #
            # config_spec.extraConfig.append(
            #     vim.option.OptionValue(key='RemoteDisplay.vnc.enabled', value='TRUE')
            # )
            # config_spec.extraConfig.append(
            #     vim.option.OptionValue(key='RemoteDisplay.vnc.port', value=str(vnc_port))
            # )
            # config_spec.extraConfig.append(
            #     vim.option.OptionValue(key='RemoteDisplay.vnc.password', value=vm_conf.vc_pass)
            # )
            # config_spec.extraConfig.append(
            #     vim.option.OptionValue(key='RemoteDisplay.vnc.keyMap', value='en-us')
            # )
            # logger.info(f"已配置VNC远程桌面: 端口={vnc_port}")
            
            # ===== 新的WebMKS方式（无需在创建时配置，通过ticket动态访问） =====
            config_spec.extraConfig = []
            # 基础系统配置
            config_spec.extraConfig.append(
                vim.option.OptionValue(key='sched.cpu.latencySensitivity', value='normal')
            )
            config_spec.extraConfig.append(
                vim.option.OptionValue(key='tools.guest.desktop.autolock', value='TRUE')
            )
            config_spec.extraConfig.append(
                vim.option.OptionValue(key='hpet0.present', value='TRUE')
            )
            config_spec.extraConfig.append(
                vim.option.OptionValue(key='cpuid.coresPerSocket', value=str(vm_conf.cpu_num))
            )
            logger.info(f"虚拟机配置完成，将使用WebMKS进行远程访问")

            # 虚拟机文件位置
            # 从system_path获取虚拟机存储目录
            # system_path格式: datastore1/system
            vm_dir = ""
            if hs_config.system_path and '/' in hs_config.system_path:
                vm_dir = hs_config.system_path.split('/', 1)[1] + "/"

            files = vim.vm.FileInfo()
            files.vmPathName = f"[{self.datastore_name}] {vm_dir}{vm_conf.vm_uuid}/"
            config_spec.files = files

            # 添加SATA控制器
            sata_spec = vim.vm.device.VirtualDeviceSpec()
            sata_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
            sata_ctrl = vim.vm.device.VirtualAHCIController()
            sata_ctrl.key = 1000
            sata_ctrl.busNumber = 0
            sata_spec.device = sata_ctrl

            device_changes = [sata_spec]

            # 添加视频卡配置（显存）
            video_spec = self._create_video_card_spec(vm_conf.gpu_mem)
            device_changes.append(video_spec)
            
            # 添加GPU PCI直通配置 ===============================================
            if vm_conf.gpu_num > 0 and hasattr(vm_conf, 'gpu_id') and vm_conf.gpu_id:
                logger.info(f"配置GPU PCI直通: {vm_conf.gpu_id}")
                try:
                    # 创建PCI直通设备规格
                    pci_spec = vim.vm.device.VirtualDeviceSpec()
                    pci_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
                    
                    # 创建PCI直通设备
                    pci_device = vim.vm.device.VirtualPCIPassthrough()
                    pci_device.backing = vim.vm.device.VirtualPCIPassthrough.DeviceBackingInfo()
                    pci_device.backing.id = vm_conf.gpu_id
                    pci_device.backing.deviceId = vm_conf.gpu_id
                    pci_device.backing.systemId = ""
                    pci_device.backing.vendorId = -1
                    pci_device.backing.deviceName = ""
                    
                    pci_spec.device = pci_device
                    device_changes.append(pci_spec)
                    logger.info(f"GPU PCI直通配置已添加: {vm_conf.gpu_id}")
                except Exception as gpu_error:
                    logger.warning(f"GPU PCI直通配置失败: {str(gpu_error)}")
            
            # 添加硬盘（必须从镜像复制）
            if not vm_conf.os_name:
                return ZMessage(success=False, action="create_vm",
                                message="未指定系统镜像(os_name)，无法创建虚拟机")

            if not hs_config.images_path:
                return ZMessage(success=False, action="create_vm",
                                message="未配置镜像路径(images_path)，无法创建虚拟机")

            # 从images_path复制vmdk到虚拟机目录
            images_parts = hs_config.images_path.split('/', 1)
            images_datastore = images_parts[0] if len(images_parts) > 0 else self.datastore_name
            images_dir = images_parts[1] if len(images_parts) > 1 else "images"

            # 检查镜像文件是否存在
            logger.info(f"检查镜像文件: [{images_datastore}] {images_dir}/{vm_conf.os_name}")
            available_files = self.list_datastore_files(f"{images_dir}")

            # 确保available_files不为None
            if available_files is None:
                logger.error(f"无法列出镜像目录文件: {images_dir}")
                return ZMessage(success=False, action="create_vm",
                                message=f"无法访问镜像目录: {images_dir}")

            # 输出所有找到的文件（用于调试）
            logger.info(f"镜像目录中的所有文件: {available_files}")

            # 查找匹配的vmdk文件（排除-flat.vmdk，只看描述符文件）
            vmdk_descriptors = [f for f in available_files if f.endswith('.vmdk') and not f.endswith('-flat.vmdk')]
            logger.info(f"找到的vmdk描述符文件: {vmdk_descriptors}")

            # 检查os_name指定的描述符文件是否存在
            if vm_conf.os_name not in vmdk_descriptors:
                logger.error(f"镜像描述符文件不存在: {vm_conf.os_name}")
                logger.info(f"可用的vmdk镜像: {', '.join(vmdk_descriptors) if vmdk_descriptors else '无'}")
                return ZMessage(success=False, action="create_vm",
                                message=f"镜像文件 '{vm_conf.os_name}' 不存在。可用镜像: {', '.join(vmdk_descriptors[:5]) if vmdk_descriptors else '无'}")

            # 先创建虚拟机目录
            vm_folder_path = f"{vm_dir}{vm_conf.vm_uuid}"
            try:
                file_manager = self.content.fileManager
                datacenter = self.content.rootFolder.childEntity[0]
                file_manager.MakeDirectory(
                    name=f"[{self.datastore_name}] {vm_folder_path}",
                    datacenter=datacenter,
                    createParentDirectories=True
                )
                logger.info(f"创建虚拟机目录: [{self.datastore_name}] {vm_folder_path}")
            except vim.fault.FileAlreadyExists:
                logger.info(f"虚拟机目录已存在: [{self.datastore_name}] {vm_folder_path}")
            except Exception as e:
                logger.error(f"创建虚拟机目录失败: {str(e)}")
                return ZMessage(success=False, action="create_vm",
                                message=f"创建虚拟机目录失败: {str(e)}")

            # os_name应该包含完整的文件名（如 windows10ltsc21x64img-1.vmdk）
            source_path = f"[{images_datastore}] {images_dir}/{vm_conf.os_name}"
            dest_path = f"[{self.datastore_name}] {vm_folder_path}/{vm_conf.vm_uuid}.vmdk"

            logger.info(f"正在复制系统盘镜像: {source_path} -> {dest_path}")
            copy_result = self.copy_virtual_disk(source_path, dest_path)

            if not copy_result.success:
                return ZMessage(success=False, action="create_vm",
                                message=f"复制系统盘镜像失败: {copy_result.message}")

            # 添加已存在的磁盘
            disk_spec = vim.vm.device.VirtualDeviceSpec()
            disk_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add

            disk = vim.vm.device.VirtualDisk()
            disk.capacityInKB = vm_conf.hdd_num * 1024 * 1024  # 转换为KB
            disk.controllerKey = 1000
            disk.unitNumber = 0

            disk.backing = vim.vm.device.VirtualDisk.FlatVer2BackingInfo()
            disk.backing.diskMode = 'persistent'
            disk.backing.fileName = dest_path

            disk_spec.device = disk
            device_changes.append(disk_spec)
            logger.info(f"已添加系统盘: {dest_path}")

            # 添加网卡（根据nic_type分配网络）
            nic_key = 4000
            for nic_name, nic_conf in vm_conf.nic_all.items():
                # 确定网络名称：根据nic_type选择pub或nat网络
                if nic_conf.nic_type == "nat":
                    network_name = hs_config.network_nat if hasattr(hs_config, 'network_nat') else None
                elif nic_conf.nic_type == "pub":
                    network_name = hs_config.network_pub if hasattr(hs_config, 'network_pub') else None
                else:
                    logger.warning(f"未知的网卡类型: {nic_conf.nic_type}，跳过网卡 {nic_name}")
                    continue

                if not network_name:
                    logger.warning(f"未配置{nic_conf.nic_type}网络，跳过网卡 {nic_name}")
                    continue

                network = self.get_network(network_name)
                if not network:
                    logger.warning(f"网络 {network_name} 不存在，跳过网卡 {nic_name}")
                    continue

                nic_spec = vim.vm.device.VirtualDeviceSpec()
                nic_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
                nic = vim.vm.device.VirtualVmxnet3()
                nic.key = nic_key
                nic.addressType = 'manual'
                nic.macAddress = nic_conf.mac_addr

                # 网络连接
                nic.backing = vim.vm.device.VirtualEthernetCard.NetworkBackingInfo()
                nic.backing.network = network
                nic.backing.deviceName = network_name

                nic.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
                nic.connectable.startConnected = True
                nic.connectable.allowGuestControl = True
                nic.connectable.connected = True

                nic_spec.device = nic
                device_changes.append(nic_spec)

                logger.info(
                    f"已添加网卡 {nic_name}: 类型={nic_conf.nic_type}, 网络={network_name}, MAC={nic_conf.mac_addr}")
                nic_key += 1

            config_spec.deviceChange = device_changes

            # 创建虚拟机
            task = vm_folder.CreateVM_Task(config=config_spec, pool=resource_pool)
            result = self._wait_for_task(task)

            if result.success:
                logger.info(f"虚拟机 {vm_conf.vm_uuid} 创建成功")
                
                

            return result

        except Exception as e:
            logger.error(f"创建虚拟机失败: {str(e)}")
            return ZMessage(success=False, action="create_vm",
                            message=f"创建失败: {str(e)}")

    def delete_vm(self, vm_name: str) -> ZMessage:
        """
        删除虚拟机
        
        :param vm_name: 虚拟机名称
        :return: 操作结果
        """
        try:
            vm = self.get_vm(vm_name)
            if not vm:
                return ZMessage(success=False, action="delete_vm",
                                message=f"虚拟机 {vm_name} 不存在")

            # 如果虚拟机正在运行，先关闭
            if vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOn:
                power_result = self.power_off(vm_name)
                if not power_result.success:
                    return power_result
                time.sleep(2)  # 等待关机完成

            # 删除虚拟机
            task = vm.Destroy_Task()
            result = self._wait_for_task(task)

            if result.success:
                logger.info(f"虚拟机 {vm_name} 删除成功")

            return result

        except Exception as e:
            logger.error(f"删除虚拟机失败: {str(e)}")
            return ZMessage(success=False, action="delete_vm",
                            message=f"删除失败: {str(e)}")

    def power_on(self, vm_name: str) -> ZMessage:
        """开机"""
        try:
            vm = self.get_vm(vm_name)
            if not vm:
                return ZMessage(success=False, action="power_on",
                                message=f"虚拟机 {vm_name} 不存在")

            if vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOn:
                return ZMessage(success=True, action="power_on",
                                message="虚拟机已经在运行")

            task = vm.PowerOn()
            return self._wait_for_task(task)

        except Exception as e:
            logger.error(f"开机失败: {str(e)}")
            return ZMessage(success=False, action="power_on",
                            message=f"开机失败: {str(e)}")

    def power_off(self, vm_name: str) -> ZMessage:
        """关机"""
        try:
            vm = self.get_vm(vm_name)
            if not vm:
                return ZMessage(success=False, action="power_off",
                                message=f"虚拟机 {vm_name} 不存在")

            if vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOff:
                return ZMessage(success=True, action="power_off",
                                message="虚拟机已经关闭")

            task = vm.PowerOff()
            return self._wait_for_task(task)

        except Exception as e:
            logger.error(f"关机失败: {str(e)}")
            return ZMessage(success=False, action="power_off",
                            message=f"关机失败: {str(e)}")

    def suspend(self, vm_name: str) -> ZMessage:
        """挂起"""
        try:
            vm = self.get_vm(vm_name)
            if not vm:
                return ZMessage(success=False, action="suspend",
                                message=f"虚拟机 {vm_name} 不存在")

            task = vm.Suspend()
            return self._wait_for_task(task)

        except Exception as e:
            logger.error(f"挂起失败: {str(e)}")
            return ZMessage(success=False, action="suspend",
                            message=f"挂起失败: {str(e)}")

    def reset(self, vm_name: str) -> ZMessage:
        """重启"""
        try:
            vm = self.get_vm(vm_name)
            if not vm:
                return ZMessage(success=False, action="reset",
                                message=f"虚拟机 {vm_name} 不存在")

            task = vm.Reset()
            return self._wait_for_task(task)

        except Exception as e:
            logger.error(f"重启失败: {str(e)}")
            return ZMessage(success=False, action="reset",
                            message=f"重启失败: {str(e)}")

    def create_snapshot(self, vm_name: str, snapshot_name: str,
                        description: str = "") -> ZMessage:
        """
        创建快照
        
        :param vm_name: 虚拟机名称
        :param snapshot_name: 快照名称
        :param description: 快照描述
        :return: 操作结果
        """
        try:
            vm = self.get_vm(vm_name)
            if not vm:
                return ZMessage(success=False, action="create_snapshot",
                                message=f"虚拟机 {vm_name} 不存在")

            task = vm.CreateSnapshot(
                name=snapshot_name,
                description=description,
                memory=False,  # 不包含内存状态
                quiesce=False  # 不静默文件系统
            )
            result = self._wait_for_task(task)

            if result.success:
                logger.info(f"快照 {snapshot_name} 创建成功")

            return result

        except Exception as e:
            logger.error(f"创建快照失败: {str(e)}")
            return ZMessage(success=False, action="create_snapshot",
                            message=f"创建快照失败: {str(e)}")

    def revert_snapshot(self, vm_name: str, snapshot_name: str) -> ZMessage:
        """
        恢复快照
        
        :param vm_name: 虚拟机名称
        :param snapshot_name: 快照名称
        :return: 操作结果
        """
        try:
            vm = self.get_vm(vm_name)
            if not vm:
                return ZMessage(success=False, action="revert_snapshot",
                                message=f"虚拟机 {vm_name} 不存在")

            # 记录恢复前的电源状态
            was_powered_on = vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOn
            logger.info(f"恢复快照前虚拟机 {vm_name} 电源状态: {'开机' if was_powered_on else '关机'}")

            # 查找快照
            snapshot = self._find_snapshot(vm.snapshot.rootSnapshotList, snapshot_name)
            if not snapshot:
                return ZMessage(success=False, action="revert_snapshot",
                                message=f"快照 {snapshot_name} 不存在")

            task = snapshot.snapshot.Revert()
            result = self._wait_for_task(task)

            if result.success:
                logger.info(f"快照 {snapshot_name} 恢复成功")
                
                # 如果恢复前是开机状态，则自动开机
                if was_powered_on:
                    logger.info(f"检测到恢复前虚拟机 {vm_name} 为开机状态，正在自动开机...")
                    # 等待一小段时间，确保快照恢复完全完成
                    time.sleep(2)
                    
                    # 重新获取虚拟机对象（快照恢复后需要刷新）
                    vm = self.get_vm(vm_name)
                    if vm and vm.runtime.powerState != vim.VirtualMachinePowerState.poweredOn:
                        try:
                            power_on_task = vm.PowerOn()
                            power_on_result = self._wait_for_task(power_on_task)
                            if power_on_result.success:
                                logger.info(f"虚拟机 {vm_name} 已自动开机")
                                result.message = f"快照恢复成功，虚拟机已自动开机"
                            else:
                                logger.warning(f"虚拟机 {vm_name} 自动开机失败: {power_on_result.message}")
                                result.message = f"快照恢复成功，但自动开机失败: {power_on_result.message}"
                        except Exception as e:
                            logger.warning(f"虚拟机 {vm_name} 自动开机异常: {str(e)}")
                            result.message = f"快照恢复成功，但自动开机异常: {str(e)}"

            return result

        except Exception as e:
            logger.error(f"恢复快照失败: {str(e)}")
            return ZMessage(success=False, action="revert_snapshot",
                            message=f"恢复快照失败: {str(e)}")

    def delete_snapshot(self, vm_name: str, snapshot_name: str) -> ZMessage:
        """
        删除快照
        
        :param vm_name: 虚拟机名称
        :param snapshot_name: 快照名称
        :return: 操作结果
        """
        try:
            vm = self.get_vm(vm_name)
            if not vm:
                return ZMessage(success=False, action="delete_snapshot",
                                message=f"虚拟机 {vm_name} 不存在")

            # 查找快照
            snapshot = self._find_snapshot(vm.snapshot.rootSnapshotList, snapshot_name)
            if not snapshot:
                return ZMessage(success=False, action="delete_snapshot",
                                message=f"快照 {snapshot_name} 不存在")

            task = snapshot.snapshot.Remove(removeChildren=False)
            result = self._wait_for_task(task)

            if result.success:
                logger.info(f"快照 {snapshot_name} 删除成功")

            return result

        except Exception as e:
            logger.error(f"删除快照失败: {str(e)}")
            return ZMessage(success=False, action="delete_snapshot",
                            message=f"删除快照失败: {str(e)}")

    def _find_snapshot(self, snapshots, snapshot_name: str):
        """递归查找快照"""
        for snapshot in snapshots:
            if snapshot.name == snapshot_name:
                return snapshot
            if hasattr(snapshot, 'childSnapshotList'):
                result = self._find_snapshot(snapshot.childSnapshotList, snapshot_name)
                if result:
                    return result
        return None

    def add_disk(self, vm_name: str, size_mb: int, disk_name: str) -> ZMessage:
        """
        添加磁盘
        
        :param vm_name: 虚拟机名称
        :param size_mb: 磁盘大小（MB）
        :param disk_name: 磁盘名称
        :return: 操作结果
        """
        try:
            vm = self.get_vm(vm_name)
            if not vm:
                return ZMessage(success=False, action="add_disk",
                                message=f"虚拟机 {vm_name} 不存在")

            # 查找SATA控制器
            sata_controller = None
            for device in vm.config.hardware.device:
                if isinstance(device, vim.vm.device.VirtualAHCIController):
                    sata_controller = device
                    break

            if not sata_controller:
                return ZMessage(success=False, action="add_disk",
                                message="未找到SATA控制器")

            # 获取下一个可用的单元号
            unit_number = len([d for d in vm.config.hardware.device
                               if isinstance(d, vim.vm.device.VirtualDisk)])

            # 从虚拟机配置中获取实际的文件路径
            # vm.config.files.vmPathName 格式: [datastore1] system/esx_vvxqD47c/esx_vvxqD47c.vmx
            vm_path = vm.config.files.vmPathName
            # 提取目录部分（去掉.vmx文件名）
            if '/' in vm_path:
                # 分离数据存储名称和路径
                # 例如: "[datastore1] system/esx_vvxqD47c/esx_vvxqD47c.vmx" -> "system/esx_vvxqD47c/"
                path_parts = vm_path.split('] ', 1)
                if len(path_parts) == 2:
                    file_path = path_parts[1]  # "system/esx_vvxqD47c/esx_vvxqD47c.vmx"
                    vm_dir = '/'.join(file_path.split('/')[:-1])  # "system/esx_vvxqD47c"
                else:
                    vm_dir = vm_name
            else:
                vm_dir = vm_name

            # 创建磁盘规格
            disk_spec = vim.vm.device.VirtualDeviceSpec()
            disk_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
            disk_spec.fileOperation = vim.vm.device.VirtualDeviceSpec.FileOperation.create

            disk = vim.vm.device.VirtualDisk()
            # 将MB转换为KB：1 MB = 1024 KB
            disk.capacityInKB = size_mb * 1024
            disk.controllerKey = sata_controller.key
            disk.unitNumber = unit_number

            disk.backing = vim.vm.device.VirtualDisk.FlatVer2BackingInfo()
            disk.backing.diskMode = 'persistent'
            disk.backing.fileName = f"[{self.datastore_name}] {vm_dir}/{disk_name}.vmdk"
            disk.backing.thinProvisioned = True

            disk_spec.device = disk

            # 应用配置
            config_spec = vim.vm.ConfigSpec()
            config_spec.deviceChange = [disk_spec]

            task = vm.Reconfigure(config_spec)
            result = self._wait_for_task(task)

            if result.success:
                logger.info(f"磁盘 {disk_name} 添加成功，大小: {size_mb}MB，路径: [{self.datastore_name}] {vm_dir}/{disk_name}.vmdk")

            return result

        except Exception as e:
            logger.error(f"添加磁盘失败: {str(e)}")
            return ZMessage(success=False, action="add_disk",
                            message=f"添加磁盘失败: {str(e)}")

    def attach_iso(self, vm_name: str, iso_path: str) -> ZMessage:
        """
        挂载ISO
        
        :param vm_name: 虚拟机名称
        :param iso_path: ISO文件路径（数据存储路径格式）
        :return: 操作结果
        """
        try:
            vm = self.get_vm(vm_name)
            if not vm:
                return ZMessage(success=False, action="attach_iso",
                                message=f"虚拟机 {vm_name} 不存在")

            # 查找CD/DVD设备
            cdrom = None
            for device in vm.config.hardware.device:
                if isinstance(device, vim.vm.device.VirtualCdrom):
                    cdrom = device
                    break

            # 如果没有CD/DVD设备，创建一个
            if not cdrom:
                # 查找IDE控制器
                ide_controller = None
                for device in vm.config.hardware.device:
                    if isinstance(device, vim.vm.device.VirtualIDEController):
                        ide_controller = device
                        break

                if not ide_controller:
                    return ZMessage(success=False, action="attach_iso",
                                    message="未找到IDE控制器")

                cdrom_spec = vim.vm.device.VirtualDeviceSpec()
                cdrom_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add

                cdrom = vim.vm.device.VirtualCdrom()
                cdrom.controllerKey = ide_controller.key
                cdrom.unitNumber = 0

                cdrom.backing = vim.vm.device.VirtualCdrom.IsoBackingInfo()
                cdrom.backing.fileName = iso_path

                cdrom.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
                cdrom.connectable.startConnected = True
                cdrom.connectable.allowGuestControl = True
                cdrom.connectable.connected = True

                cdrom_spec.device = cdrom
            else:
                # 修改现有CD/DVD设备
                cdrom_spec = vim.vm.device.VirtualDeviceSpec()
                cdrom_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit
                cdrom_spec.device = cdrom

                cdrom.backing = vim.vm.device.VirtualCdrom.IsoBackingInfo()
                cdrom.backing.fileName = iso_path

                cdrom.connectable.startConnected = True
                cdrom.connectable.connected = True

            # 应用配置
            config_spec = vim.vm.ConfigSpec()
            config_spec.deviceChange = [cdrom_spec]

            task = vm.Reconfigure(config_spec)
            result = self._wait_for_task(task)

            if result.success:
                logger.info(f"ISO {iso_path} 挂载成功")
                logger.info(f"ISO {iso_path} 挂载成功")

            return result

        except Exception as e:
            logger.error(f"挂载ISO失败: {str(e)}")
            return ZMessage(success=False, action="attach_iso",
                            message=f"挂载ISO失败: {str(e)}")

    def update_vm_config(self, vm_name: str, vm_conf: VMConfig) -> ZMessage:
        """
        更新虚拟机配置
        
        :param vm_name: 虚拟机名称
        :param vm_conf: 新的虚拟机配置
        :return: 操作结果
        """
        try:
            vm = self.get_vm(vm_name)
            if not vm:
                return ZMessage(success=False, action="update_vm_config",
                                message=f"虚拟机 {vm_name} 不存在")

            # 创建配置规格
            config_spec = vim.vm.ConfigSpec()
            config_spec.memoryMB = vm_conf.mem_num
            config_spec.numCPUs = vm_conf.cpu_num
            
            # 处理GPU PCI直通配置 ==============================================
            device_changes = []
            
            # 查找现有的PCI直通设备
            existing_pci_devices = []
            for device in vm.config.hardware.device:
                if isinstance(device, vim.vm.device.VirtualPCIPassthrough):
                    existing_pci_devices.append(device)
            
            # 如果配置了GPU直通
            if vm_conf.gpu_num > 0 and hasattr(vm_conf, 'gpu_id') and vm_conf.gpu_id:
                logger.info(f"更新GPU PCI直通配置: {vm_conf.gpu_id}")
                
                # 移除旧的PCI直通设备
                for old_device in existing_pci_devices:
                    remove_spec = vim.vm.device.VirtualDeviceSpec()
                    remove_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.remove
                    remove_spec.device = old_device
                    device_changes.append(remove_spec)
                    logger.info(f"移除旧的PCI直通设备")
                
                # 添加新的PCI直通设备
                try:
                    pci_spec = vim.vm.device.VirtualDeviceSpec()
                    pci_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
                    
                    pci_device = vim.vm.device.VirtualPCIPassthrough()
                    pci_device.backing = vim.vm.device.VirtualPCIPassthrough.DeviceBackingInfo()
                    pci_device.backing.id = vm_conf.gpu_id
                    pci_device.backing.deviceId = vm_conf.gpu_id
                    pci_device.backing.systemId = ""
                    pci_device.backing.vendorId = -1
                    pci_device.backing.deviceName = ""
                    
                    pci_spec.device = pci_device
                    device_changes.append(pci_spec)
                    logger.info(f"添加新的GPU PCI直通配置: {vm_conf.gpu_id}")
                except Exception as gpu_error:
                    logger.warning(f"GPU PCI直通配置失败: {str(gpu_error)}")
            
            # 如果不需要GPU直通，移除现有的PCI直通设备
            elif existing_pci_devices:
                logger.info(f"移除GPU PCI直通配置")
                for old_device in existing_pci_devices:
                    remove_spec = vim.vm.device.VirtualDeviceSpec()
                    remove_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.remove
                    remove_spec.device = old_device
                    device_changes.append(remove_spec)
            
            # 如果有设备变更，添加到配置规格
            if device_changes:
                config_spec.deviceChange = device_changes

            # 应用配置
            task = vm.Reconfigure(config_spec)
            result = self._wait_for_task(task)

            if result.success:
                logger.info(f"虚拟机 {vm_name} 配置更新成功")

            return result

        except Exception as e:
            logger.error(f"更新虚拟机配置失败: {str(e)}")
            return ZMessage(success=False, action="update_vm_config",
                            message=f"更新配置失败: {str(e)}")

    def set_boot_order(self, vm_name: str, efi_all: list) -> ZMessage:
        """
        根据efi_all设置虚拟机启动顺序
        efi_type=False -> 硬盘，efi_type=True -> 光盘
        :param vm_name: 虚拟机名称
        :param efi_all: list[BootOpts]，启动项顺序列表
        :return: 操作结果
        """
        try:
            vm = self.get_vm(vm_name)
            if not vm:
                return ZMessage(success=False, action="set_boot_order",
                                message=f"虚拟机 {vm_name} 不存在")
            if not efi_all:
                return ZMessage(success=True, action="set_boot_order",
                                message="启动项列表为空，跳过设置")
            # 收集虚拟机设备
            disks = []
            cdroms = []
            for device in vm.config.hardware.device:
                if isinstance(device, vim.vm.device.VirtualDisk):
                    disks.append(device)
                elif isinstance(device, vim.vm.device.VirtualCdrom):
                    cdroms.append(device)
            # 按efi_all顺序构建启动项列表
            boot_order = []
            disk_idx = 0
            cdrom_idx = 0
            for efi_item in efi_all:
                if not efi_item.efi_type:  # HDD
                    if disk_idx < len(disks):
                        boot_disk = vim.vm.BootOptions.BootableDiskDevice()
                        boot_disk.deviceKey = disks[disk_idx].key
                        boot_order.append(boot_disk)
                        disk_idx += 1
                else:  # ISO/CDROM
                    if cdrom_idx < len(cdroms):
                        boot_cdrom = vim.vm.BootOptions.BootableCdromDevice()
                        boot_order.append(boot_cdrom)
                        cdrom_idx += 1
            if not boot_order:
                return ZMessage(success=True, action="set_boot_order",
                                message="无有效启动设备，跳过设置")
            boot_opts = vim.vm.BootOptions()
            boot_opts.bootOrder = boot_order
            config_spec = vim.vm.ConfigSpec()
            config_spec.bootOptions = boot_opts
            task = vm.Reconfigure(config_spec)
            result = self._wait_for_task(task)
            if result.success:
                logger.info(f"虚拟机 {vm_name} 启动顺序设置成功")
            return result
        except Exception as e:
            logger.error(f"设置启动顺序失败: {str(e)}")
            return ZMessage(success=False, action="set_boot_order",
                            message=f"设置启动顺序失败: {str(e)}")

    def update_network_adapters(self, vm_name: str, vm_conf: VMConfig, vm_last: VMConfig, hs_config: HSConfig) -> ZMessage:
        """
        更新虚拟机网卡配置
        
        :param vm_name: 虚拟机名称
        :param vm_conf: 新的虚拟机配置
        :param vm_last: 旧的虚拟机配置
        :param hs_config: 主机配置
        :return: 操作结果
        """
        try:
            vm = self.get_vm(vm_name)
            if not vm:
                return ZMessage(success=False, action="update_network_adapters",
                                message=f"虚拟机 {vm_name} 不存在")

            # 获取现有的网卡设备
            existing_nics = {}
            for device in vm.config.hardware.device:
                if isinstance(device, vim.vm.device.VirtualEthernetCard):
                    # 通过MAC地址识别网卡
                    existing_nics[device.macAddress] = device

            device_changes = []

            # 1. 删除旧配置中存在但新配置中不存在的网卡
            old_macs = {nic_conf.mac_addr for nic_conf in vm_last.nic_all.values()} if vm_last else set()
            new_macs = {nic_conf.mac_addr for nic_conf in vm_conf.nic_all.values()}
            
            for mac_addr in old_macs - new_macs:
                if mac_addr in existing_nics:
                    nic_spec = vim.vm.device.VirtualDeviceSpec()
                    nic_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.remove
                    nic_spec.device = existing_nics[mac_addr]
                    device_changes.append(nic_spec)
                    logger.info(f"删除网卡: MAC={mac_addr}")

            # 2. 添加新配置中存在但旧配置中不存在的网卡
            nic_key = 4000
            for nic_name, nic_conf in vm_conf.nic_all.items():
                if nic_conf.mac_addr not in old_macs:
                    # 确定网络名称
                    if nic_conf.nic_type == "nat":
                        network_name = hs_config.network_nat if hasattr(hs_config, 'network_nat') else None
                    elif nic_conf.nic_type == "pub":
                        network_name = hs_config.network_pub if hasattr(hs_config, 'network_pub') else None
                    else:
                        logger.warning(f"未知的网卡类型: {nic_conf.nic_type}，跳过网卡 {nic_name}")
                        continue

                    if not network_name:
                        logger.warning(f"未配置{nic_conf.nic_type}网络，跳过网卡 {nic_name}")
                        continue

                    network = self.get_network(network_name)
                    if not network:
                        logger.warning(f"网络 {network_name} 不存在，跳过网卡 {nic_name}")
                        continue

                    # 创建新网卡
                    nic_spec = vim.vm.device.VirtualDeviceSpec()
                    nic_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
                    nic = vim.vm.device.VirtualVmxnet3()
                    nic.key = nic_key
                    nic.addressType = 'manual'
                    nic.macAddress = nic_conf.mac_addr

                    # 网络连接
                    nic.backing = vim.vm.device.VirtualEthernetCard.NetworkBackingInfo()
                    nic.backing.network = network
                    nic.backing.deviceName = network_name

                    nic.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
                    nic.connectable.startConnected = True
                    nic.connectable.allowGuestControl = True
                    nic.connectable.connected = True

                    nic_spec.device = nic
                    device_changes.append(nic_spec)

                    logger.info(f"添加网卡 {nic_name}: 类型={nic_conf.nic_type}, 网络={network_name}, MAC={nic_conf.mac_addr}")
                    nic_key += 1

            # 3. 更新现有网卡（如果网络类型改变）
            for nic_name, nic_conf in vm_conf.nic_all.items():
                if nic_conf.mac_addr in old_macs and nic_conf.mac_addr in existing_nics:
                    # 检查是否需要更新网络
                    old_nic_conf = None
                    if vm_last:
                        for old_name, old_conf in vm_last.nic_all.items():
                            if old_conf.mac_addr == nic_conf.mac_addr:
                                old_nic_conf = old_conf
                                break
                    
                    # 如果网卡类型改变，需要更新网络连接
                    if old_nic_conf and old_nic_conf.nic_type != nic_conf.nic_type:
                        # 确定新的网络名称
                        if nic_conf.nic_type == "nat":
                            network_name = hs_config.network_nat if hasattr(hs_config, 'network_nat') else None
                        elif nic_conf.nic_type == "pub":
                            network_name = hs_config.network_pub if hasattr(hs_config, 'network_pub') else None
                        else:
                            continue

                        if not network_name:
                            continue

                        network = self.get_network(network_name)
                        if not network:
                            continue

                        # 更新网卡
                        nic_spec = vim.vm.device.VirtualDeviceSpec()
                        nic_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit
                        nic_spec.device = existing_nics[nic_conf.mac_addr]
                        
                        # 更新网络连接
                        nic_spec.device.backing = vim.vm.device.VirtualEthernetCard.NetworkBackingInfo()
                        nic_spec.device.backing.network = network
                        nic_spec.device.backing.deviceName = network_name
                        
                        device_changes.append(nic_spec)
                        logger.info(f"更新网卡 {nic_name}: 类型={nic_conf.nic_type}, 网络={network_name}, MAC={nic_conf.mac_addr}")

            # 如果有变更，应用配置
            if device_changes:
                config_spec = vim.vm.ConfigSpec()
                config_spec.deviceChange = device_changes

                task = vm.Reconfigure(config_spec)
                result = self._wait_for_task(task)

                if result.success:
                    logger.info(f"虚拟机 {vm_name} 网卡配置更新成功")

                return result
            else:
                logger.info(f"虚拟机 {vm_name} 网卡配置无变化")
                return ZMessage(success=True, action="update_network_adapters",
                                message="网卡配置无变化")

        except Exception as e:
            logger.error(f"更新网卡配置失败: {str(e)}")
            return ZMessage(success=False, action="update_network_adapters",
                            message=f"更新网卡配置失败: {str(e)}")

    def _create_video_card_spec(self, gpu_mem_mb: int) -> vim.vm.device.VirtualDeviceSpec:
        """
        创建视频卡设备规格（用于创建VM时配置显存）
        
        :param gpu_mem_mb: 显存大小（MB）
        :return: 视频卡设备规格
        """
        # 转换MB为KB（API要求）
        vram_kb = gpu_mem_mb * 1024
        
        # 创建视频卡设备
        video_card = vim.vm.device.VirtualVideoCard()
        video_card.videoRamSizeInKB = vram_kb
        video_card.enable3DSupport = True
        video_card.use3dRenderer = 'automatic'
        video_card.useAutoDetect = False
        video_card.numDisplays = 1
        video_card.key = 500
        
        # 创建设备配置规格
        video_spec = vim.vm.device.VirtualDeviceSpec()
        video_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
        video_spec.device = video_card
        
        logger.info(f"创建视频卡配置: 显存={gpu_mem_mb}MB (videoRamSizeInKB={vram_kb})")
        
        return video_spec

    def update_gpu_memory(self, vm_name: str, gpu_mem_mb: int) -> ZMessage:
        """
        更新虚拟机显存配置（用于已存在的VM）
        
        :param vm_name: 虚拟机名称
        :param gpu_mem_mb: 显存大小（MB）
        :return: 操作结果
        """
        try:
            vm = self.get_vm(vm_name)
            if not vm:
                return ZMessage(success=False, action="update_gpu_memory",
                                message=f"虚拟机 {vm_name} 不存在")

            # 转换MB为KB（API要求）
            vram_kb = gpu_mem_mb * 1024
            
            # 查找现有的视频卡设备
            video_card = None
            for device in vm.config.hardware.device:
                if isinstance(device, vim.vm.device.VirtualVideoCard):
                    video_card = device
                    break
            
            if not video_card:
                logger.warning(f"虚拟机 {vm_name} 未找到视频卡设备")
                return ZMessage(success=False, action="update_gpu_memory",
                                message="未找到视频卡设备")
            
            # 更新显存大小
            video_card.videoRamSizeInKB = vram_kb
            
            # 启用3D支持（可选）
            video_card.enable3DSupport = True
            video_card.use3dRenderer = 'automatic'
            
            # 创建设备配置规格
            dev_spec = vim.vm.device.VirtualDeviceSpec()
            dev_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit
            dev_spec.device = video_card
            
            # 创建虚拟机配置规格
            config_spec = vim.vm.ConfigSpec()
            config_spec.deviceChange = [dev_spec]
            
            # 应用配置
            task = vm.Reconfigure(config_spec)
            result = self._wait_for_task(task)

            if result.success:
                logger.info(f"虚拟机 {vm_name} 显存配置更新成功: {gpu_mem_mb}MB (videoRamSizeInKB={vram_kb})")

            return result

        except Exception as e:
            logger.error(f"更新显存配置失败: {str(e)}")
            return ZMessage(success=False, action="update_gpu_memory",
                            message=f"更新显存配置失败: {str(e)}")

    def _get_guest_id(self, os_name: str) -> str:
        """
        根据操作系统名称获取GuestId
        
        :param os_name: 操作系统名称
        :return: GuestId
        """
        os_lower = os_name.lower()

        # Ubuntu/Debian
        if 'ubuntu' in os_lower or 'debian' in os_lower:
            if '64' in os_lower or 'x64' in os_lower or 'amd64' in os_lower:
                return 'ubuntu64Guest'
            return 'ubuntuGuest'

        # CentOS/RHEL
        if 'centos' in os_lower or 'rhel' in os_lower or 'redhat' in os_lower:
            if '64' in os_lower or 'x64' in os_lower:
                return 'centos64Guest'
            return 'centosGuest'

        # Windows
        if 'windows' in os_lower or 'win' in os_lower:
            if '2019' in os_lower or '2022' in os_lower:
                return 'windows9Server64Guest'
            if '2016' in os_lower:
                return 'windows9Server64Guest'
            if '2012' in os_lower:
                return 'windows8Server64Guest'
            if '10' in os_lower or '11' in os_lower:
                return 'windows9_64Guest'
            if '64' in os_lower or 'x64' in os_lower:
                return 'windows7_64Guest'
            return 'windows7Guest'

        # 默认
        return 'otherGuest64'

    def get_vm_status(self, vm_name: str) -> Dict[str, Any]:
        """
        获取虚拟机状态
        
        :param vm_name: 虚拟机名称
        :return: 虚拟机状态信息
        """
        try:
            vm = self.get_vm(vm_name)
            if not vm:
                return {}

            status = {
                "name": vm.name,
                "power_state": str(vm.runtime.powerState),
                "guest_os": vm.config.guestFullName if vm.config else "Unknown",
                "cpu": vm.config.hardware.numCPU if vm.config else 0,
                "memory_mb": vm.config.hardware.memoryMB if vm.config else 0,
                "ip_address": vm.guest.ipAddress if vm.guest else "",
                "tools_status": str(vm.guest.toolsStatus) if vm.guest else "Unknown",
            }

            return status

        except Exception as e:
            logger.error(f"获取虚拟机状态失败: {str(e)}")
            return {}

    def get_host_status(self) -> Dict[str, Any]:
        """
        获取ESXi主机状态
        
        :return: 主机状态信息
        """
        try:
            host = self._get_obj(vim.HostSystem)
            if not host or len(host) == 0:
                return {}

            host = host[0]

            # CPU信息
            cpu_usage = host.summary.quickStats.overallCpuUsage or 0
            num_cpu_cores = host.summary.hardware.numCpuCores or 0
            cpu_mhz = host.summary.hardware.cpuMhz or 0
            cpu_total = num_cpu_cores * cpu_mhz

            # 内存信息
            memory_usage = host.summary.quickStats.overallMemoryUsage or 0
            memory_size = host.summary.hardware.memorySize or 0
            memory_total = memory_size / (1024 * 1024) if memory_size > 0 else 0

            status = {
                "name": host.name,
                "cpu_cores": num_cpu_cores,
                "cpu_usage_mhz": cpu_usage,
                "cpu_total_mhz": cpu_total,
                "cpu_usage_percent": round((cpu_usage / cpu_total) * 100, 2) if cpu_total > 0 else 0,
                "memory_usage_mb": memory_usage,
                "memory_total_mb": int(memory_total),
                "memory_usage_percent": round((memory_usage / memory_total) * 100, 2) if memory_total > 0 else 0,
                "connection_state": str(host.runtime.connectionState),
                "power_state": str(host.runtime.powerState),
            }

            return status

        except Exception as e:
            logger.error(f"获取主机状态失败: {str(e)}")
            return {}

    def list_datastore_files(self, folder_path: str = "ISO") -> List[str]:
        """
        列出数据存储中指定文件夹的文件
        
        :param folder_path: 文件夹路径（相对于数据存储根目录）
        :return: 文件名列表
        """
        try:
            datastore = self.get_datastore()
            if not datastore:
                logger.error(f"数据存储 {self.datastore_name} 不存在")
                return []

            # 获取数据存储浏览器
            browser = datastore.browser

            # 构建搜索规格
            search_spec = vim.host.DatastoreBrowser.SearchSpec()
            search_spec.matchPattern = ["*.iso", "*.vmdk", "*.vdi", "*.qcow2"]

            # 构建数据存储路径
            datastore_path = f"[{self.datastore_name}] {folder_path}"

            # 搜索文件
            task = browser.SearchDatastore_Task(datastorePath=datastore_path, searchSpec=search_spec)
            result = self._wait_for_task(task)

            if not result.success:
                logger.warning(f"搜索数据存储文件失败: {result.message}")
                return []

            # 获取文件列表
            files = []
            if task.info.result and hasattr(task.info.result, 'file'):
                for file_info in task.info.result.file:
                    files.append(file_info.path)

            logger.info(f"在 {datastore_path} 中找到 {len(files)} 个文件")
            return files

        except Exception as e:
            logger.warning(f"列出数据存储文件失败: {str(e)}")
            return []

    def copy_file_in_datastore(self, source_path: str, dest_path: str) -> ZMessage:
        """
        在数据存储内复制文件
        
        :param source_path: 源文件路径（数据存储格式：[datastore] path/file）
        :param dest_path: 目标文件路径（数据存储格式：[datastore] path/file）
        :return: 操作结果
        """
        try:
            datastore = self.get_datastore()
            if not datastore:
                return ZMessage(success=False, action="copy_file",
                                message=f"数据存储 {self.datastore_name} 不存在")

            # 获取文件管理器
            file_manager = self.content.fileManager

            # 获取数据中心
            datacenter = self.content.rootFolder.childEntity[0]

            # 复制文件
            task = file_manager.CopyDatastoreFile_Task(
                sourceName=source_path,
                sourceDatacenter=datacenter,
                destinationName=dest_path,
                destinationDatacenter=datacenter,
                force=False
            )

            result = self._wait_for_task(task)

            if result.success:
                logger.info(f"文件复制成功: {source_path} -> {dest_path}")

            return result

        except Exception as e:
            logger.error(f"复制文件失败: {str(e)}")
            return ZMessage(success=False, action="copy_file",
                            message=f"复制文件失败: {str(e)}")

    def copy_virtual_disk(self, source_path: str, dest_path: str) -> ZMessage:
        """
        复制虚拟磁盘（vmdk文件）
        使用VirtualDiskManager来正确复制vmdk及其关联的数据文件
        
        :param source_path: 源磁盘路径（数据存储格式：[datastore] path/file.vmdk）
        :param dest_path: 目标磁盘路径（数据存储格式：[datastore] path/file.vmdk）
        :return: 操作结果
        """
        try:
            # 获取虚拟磁盘管理器
            disk_manager = self.content.virtualDiskManager

            # 当直接连接到ESXi时，datacenter参数不是必需的
            # 根据VMware API文档：Not needed when invoked directly on ESX
            # 使用None可以避免路径解析问题

            # 复制虚拟磁盘
            task = disk_manager.CopyVirtualDisk_Task(
                sourceName=source_path,
                sourceDatacenter=None,  # ESXi直连时使用None
                destName=dest_path,
                destDatacenter=None,  # ESXi直连时使用None
                destSpec=None,  # None表示使用源磁盘的规格
                force=False
            )

            result = self._wait_for_task(task)

            if result.success:
                logger.info(f"虚拟磁盘复制成功: {source_path} -> {dest_path}")

            return result

        except Exception as e:
            logger.error(f"复制虚拟磁盘失败: {str(e)}")
            return ZMessage(success=False, action="copy_virtual_disk",
                            message=f"复制虚拟磁盘失败: {str(e)}")

    def get_webmks_ticket(self, vm_name: str) -> ZMessage:
        """
        获取WebMKS访问票据
        
        :param vm_name: 虚拟机名称
        :return: 包含ticket信息的ZMessage
        """
        try:
            vm = self.get_vm(vm_name)
            if not vm:
                return ZMessage(success=False, action="get_webmks_ticket",
                                message=f"虚拟机 {vm_name} 不存在")
            
            # 检查虚拟机是否开机
            if vm.runtime.powerState != vim.VirtualMachinePowerState.poweredOn:
                return ZMessage(success=False, action="get_webmks_ticket",
                                message=f"虚拟机 {vm_name} 未开机，无法获取WebMKS票据")
            
            # 获取WebMKS票据
            ticket = vm.AcquireTicket('webmks')
            
            if not ticket:
                return ZMessage(success=False, action="get_webmks_ticket",
                                message="获取WebMKS票据失败")
            
            logger.info(f"成功获取虚拟机 {vm_name} 的WebMKS票据")
            
            return ZMessage(success=True, action="get_webmks_ticket",
                            message="获取WebMKS票据成功",
                            results={
                                'ticket': ticket.ticket,
                                'host': ticket.host if ticket.host is not None else "",
                                'port': ticket.port,
                                'cfgFile': ticket.cfgFile
                            })
        
        except Exception as e:
            logger.error(f"获取WebMKS票据失败: {str(e)}")
            return ZMessage(success=False, action="get_webmks_ticket",
                            message=f"获取WebMKS票据失败: {str(e)}")

    def get_vm_screenshot(self, vm_name: str, screenshot_path: str) -> ZMessage:
        """
        获取虚拟机截图
        
        :param vm_name: 虚拟机名称
        :param screenshot_path: 截图保存路径
        :return: 操作结果
        """
        try:
            vm = self.get_vm(vm_name)
            if not vm:
                return ZMessage(success=False, action="get_vm_screenshot",
                                message=f"虚拟机 {vm_name} 不存在")
            
            # 检查虚拟机是否开机
            if vm.runtime.powerState != vim.VirtualMachinePowerState.poweredOn:
                return ZMessage(success=False, action="get_vm_screenshot",
                                message=f"虚拟机 {vm_name} 未开机，无法获取截图")
            
            # 使用CreateScreenshot_Task方法获取截图
            # 这个方法会在数据存储中创建一个截图文件
            task = vm.CreateScreenshot_Task()
            
            # 等待任务完成
            result = self._wait_for_task(task)
            
            if not result.success:
                return ZMessage(success=False, action="get_vm_screenshot",
                                message=f"创建截图任务失败: {result.message}")
            
            # 任务结果包含截图文件在数据存储中的路径
            screenshot_datastore_path = result.results
            
            # 从数据存储下载截图文件
            # 解析数据存储路径，格式：[datastore] path/to/screenshot.png
            if not screenshot_datastore_path or '[' not in screenshot_datastore_path:
                return ZMessage(success=False, action="get_vm_screenshot",
                                message="截图文件路径格式错误")
            
            # 提取数据存储名称和文件路径
            import re
            match = re.match(r'\[([^\]]+)\]\s*(.+)', screenshot_datastore_path)
            if not match:
                return ZMessage(success=False, action="get_vm_screenshot",
                                message="无法解析截图文件路径")
            
            datastore_name = match.group(1)
            file_path = match.group(2).strip()
            
            # 构建下载URL
            # ESXi的文件下载URL格式：https://host/folder/path?dcPath=ha-datacenter&dsName=datastore
            import urllib.parse
            download_url = (f"https://{self.host}/folder/{urllib.parse.quote(file_path)}"
                           f"?dcPath=ha-datacenter&dsName={urllib.parse.quote(datastore_name)}")
            
            # 使用requests下载文件
            import requests
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            response = requests.get(
                download_url,
                auth=(self.user, self.password),
                verify=False,
                timeout=30
            )
            
            if response.status_code != 200:
                return ZMessage(success=False, action="get_vm_screenshot",
                                message=f"下载截图文件失败，HTTP状态码: {response.status_code}")
            
            # 保存截图文件
            with open(screenshot_path, 'wb') as f:
                f.write(response.content)
            
            # 删除数据存储中的临时截图文件
            try:
                file_manager = self.content.fileManager
                datacenter = self._get_obj(vim.Datacenter)
                if isinstance(datacenter, list) and len(datacenter) > 0:
                    datacenter = datacenter[0]
                
                delete_task = file_manager.DeleteDatastoreFile_Task(
                    name=screenshot_datastore_path,
                    datacenter=datacenter
                )
                self._wait_for_task(delete_task)
            except Exception as e:
                logger.warning(f"删除临时截图文件失败: {str(e)}")
            
            logger.info(f"成功获取虚拟机 {vm_name} 的截图")
            return ZMessage(success=True, action="get_vm_screenshot",
                            message="获取截图成功")
        
        except Exception as e:
            logger.error(f"获取虚拟机截图失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return ZMessage(success=False, action="get_vm_screenshot",
                            message=f"获取虚拟机截图失败: {str(e)}")
