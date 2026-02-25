import os
import shutil
import subprocess

import requests
from requests.auth import HTTPBasicAuth

from loguru import logger
from MainObject.Config.HSConfig import HSConfig
from MainObject.Config.VMConfig import VMConfig
from MainObject.Public.ZMessage import ZMessage
from MainObject.Config.VMPowers import VMPowers


class VRestAPI:
    def __init__(self,
                 host_addr="localhost:8697",
                 host_user="root",
                 host_pass="password",
                 host_path="",
                 ver_agent=21):
        self.host_addr = host_addr
        self.host_user = host_user
        self.host_pass = host_pass
        self.host_path = host_path
        self.ver_agent = ver_agent

    @staticmethod
    # 创建vmx文本 #########################################################
    # :param config: 配置字典
    # :param prefix: 前缀字符串
    # :return: vmx文本
    # #####################################################################
    def create_txt(config: dict, prefix: str = "") -> str:
        result = ""
        for key, value in config.items():
            if isinstance(value, dict):  # 如果值是字典，递归处理 =========
                new_prefix = f"{prefix}{key}." if prefix else f"{key}."
                result += VRestAPI.create_txt(value, new_prefix)
            else:  # 如果值不是字典，直接生成配置行 =======================
                full_key = f"{prefix}{key}" if prefix else key
                if type(value) == str:
                    result += f"{full_key} = \"{value}\"\n"
                else:
                    result += f"{full_key} = {value}\n"
        return result

    # VMRestAPI ###########################################################
    # 发送VMRest API请求
    # :param url: API端点路径 (如 /vms, /vms/{id}/power)
    # :param data: 请求体数据 (用于POST/PUT请求)
    # :param method: HTTP方法 (GET, POST, PUT, DELETE)
    # :return: ZMessage对象
    # #####################################################################
    def vmrest_api(self, url: str, data=None, m: str = "GET") -> ZMessage:
        full_url = f"http://{self.host_addr}/api{url}"
        auth = HTTPBasicAuth(self.host_user, self.host_pass)
        # 设置请求头 ======================================================
        head = {"Content-Type": "application/vnd.vmware.vmw.rest-v1+json"}
        methods = {"GET": requests.get, "POST": requests.post,
                   "PUT": requests.put, "DELETE": requests.delete}
        try:  # 无效请求 ==================================================
            if m.upper() not in methods:
                return ZMessage(success=False, actions="vmrest_api",
                                message=f"不支持的HTTP方法: {m}")
            # 发送请求 ====================================================
            response = methods[m.upper()](
                full_url, auth=auth, headers=head, json=data, timeout=30)
            response.raise_for_status()
            # 返回成功消息 ================================================
            return ZMessage(
                success=True, actions="vmrest_api", message="请求成功",
                results=response.json() if response.text else {})
        # 处理HTTP错误 ====================================================
        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP错误 {e.response.status_code}: {e.response.reason}"
            try:
                error_detail = e.response.json()
                error_msg += f" - {error_detail}"
            except Exception as parse_err:
                logger.debug(f"[VMWRestAPI] 解析错误响应JSON失败: {parse_err}")
                error_msg += f" - {e.response.text}"
            return ZMessage(success=False, actions="vmrest_api",
                            message=error_msg, execute=e)
        # 处理连接错误 ====================================================
        except requests.exceptions.ConnectionError as e:
            return ZMessage(success=False, actions="vmrest_api",
                            message=f"连接失败: 无法连接到 {self.host_addr}", execute=e)
        # 处理超时错误 ====================================================
        except requests.exceptions.Timeout as e:
            return ZMessage(success=False, actions="vmrest_api",
                            message=f"请求超时: 操作耗时过长", execute=e)
        # 处理其他请求异常 ================================================
        except requests.exceptions.RequestException as e:
            return ZMessage(success=False, actions="vmrest_api",
                            message=f"请求异常: {str(e)}", execute=e)
        # 处理所有其他异常 ================================================
        except Exception as e:
            return ZMessage(success=False, actions="vmrest_api",
                            message=f"未知错误: {type(e).__name__} - {str(e)}", execute=e)

    # VMRest电源操作API  ##################################################
    # 发送VMRest电源操作请求（PUT请求体为纯字符串）
    # :param url: API端点路径
    # :param power: 电源状态字符串 (on, off, shutdown, suspend, pause, unpause)
    # :return: ZMessage对象
    # #####################################################################
    def powers_api(self, url: str, power: str) -> ZMessage:
        full_url = f"http://{self.host_addr}/api{url}"
        auth = HTTPBasicAuth(self.host_user, self.host_pass)
        head = {"Content-Type": "application/vnd.vmware.vmw.rest-v1+json"}
        try:
            response = requests.put(
                full_url,
                auth=auth,
                headers=head,
                data=power,
                timeout=30  # 添加超时设置
            )
            response.raise_for_status()
            return ZMessage(
                success=True,
                actions="vmrest_api_power",
                message="电源操作成功",
                results=response.json() if response.text else {}
            )
        except requests.exceptions.HTTPError as e:
            # HTTP错误（4xx, 5xx）
            error_msg = f"HTTP错误 {e.response.status_code}: {e.response.reason}"
            try:
                error_detail = e.response.json()
                error_msg += f" - {error_detail}"
            except Exception as parse_err:
                logger.debug(f"[VMWRestAPI] 解析电源操作错误响应JSON失败: {parse_err}")
                error_msg += f" - {e.response.text}"
            return ZMessage(
                success=False,
                actions="vmrest_api_power",
                message=error_msg,
                execute=e
            )
        except requests.exceptions.ConnectionError as e:
            # 连接错误
            return ZMessage(
                success=False,
                actions="vmrest_api_power",
                message=f"连接失败: 无法连接到 {self.host_addr}，请检查VMware REST API服务是否启动",
                execute=e
            )
        except requests.exceptions.Timeout as e:
            # 超时错误
            return ZMessage(
                success=False,
                actions="vmrest_api_power",
                message=f"请求超时: 操作耗时过长，请稍后重试",
                execute=e
            )
        except requests.exceptions.RequestException as e:
            # 其他请求异常
            return ZMessage(
                success=False,
                actions="vmrest_api_power",
                message=f"请求异常: {str(e)}",
                execute=e
            )
        except Exception as e:
            # 捕获所有其他异常
            return ZMessage(
                success=False,
                actions="vmrest_api_power",
                message=f"未知错误: {type(e).__name__} - {str(e)}",
                execute=e
            )

    # 获取所有虚拟机列表 ##################################################
    # return: ZMessage对象
    # #####################################################################
    def return_vmx(self) -> ZMessage:
        return self.vmrest_api("/vms")

    # 选择虚拟机ID ########################################################
    # 根据虚拟机名称获取虚拟机ID
    # :param vm_name: 虚拟机名称
    # :return: 虚拟机ID，未找到返回空字符串
    # #####################################################################
    def select_vid(self, vm_name: str) -> str:
        result = self.return_vmx()
        if not result.success:
            return ""
        vms = result.results if isinstance(result.results, list) else []
        for vm in vms:
            # VMRest API返回的虚拟机信息包含id和path字段
            # 从path中提取虚拟机名称进行匹配
            vm_path = vm.get("path", "")
            vm_id = vm.get("id", "")
            # 方式1：直接匹配路径中的虚拟机名称
            if vm_name in vm_path:
                return vm_id
            # 方式2：提取.vmx文件名进行匹配
            import os
            vmx_name = os.path.splitext(os.path.basename(vm_path))[0]
            if vmx_name == vm_name:
                return vm_id
        return ""

    # 获取虚拟机电源状态 ##################################################
    # 获取指定虚拟机的电源状态
    # :param vm_name: 虚拟机名称
    # #####################################################################
    def powers_get(self, vm_name: str) -> ZMessage:
        vm_id = self.select_vid(vm_name)
        if not vm_id:
            return ZMessage(
                success=False,
                actions="get_powers",
                message=f"未找到虚拟机: {vm_name}"
            )
        return self.vmrest_api(f"/vms/{vm_id}/power")

    # 设置虚拟机电源状态 ##################################################
    # :param vm_name: 虚拟机名称
    # :param power_state: VMPowers枚举类型
    # :param vm_password: 加密虚拟机的密码（可选）
    # :return: ZMessage对象
    # #####################################################################
    def powers_set(self, vmx_name: str, power: VMPowers, vm_password: str = None) -> ZMessage:
        try:
            # 电源状态映射
            power_map = {
                VMPowers.S_START: "on",
                VMPowers.H_CLOSE: "off",
                VMPowers.A_PAUSE: "pause",
                VMPowers.A_WAKED: "unpause",
            }
            state_str = power_map.get(power, "on")
            vm_id = self.select_vid(vmx_name)
            if not vm_id:
                return ZMessage(
                    success=False,
                    actions="set_powers",
                    message=f"未找到虚拟机: {vmx_name}"
                )
            # 构建URL，如果有虚拟机密码则添加查询参数
            url = f"/vms/{vm_id}/power"
            if vm_password:
                # 对密码进行URL编码
                from urllib.parse import quote
                url += f"?vmPassword={quote(vm_password)}"
            # VMRest API要求PUT请求体为纯字符串
            return self.powers_api(url, state_str)
        except Exception as e:
            # 捕获powers_set方法内的所有异常
            return ZMessage(
                success=False,
                actions="set_powers",
                message=f"设置电源状态失败: {type(e).__name__} - {str(e)}",
                execute=e
            )

    # 注册虚拟机 ##########################################################
    # 注册虚拟机到VMware WorkstationAPI
    # :param vmx_path: .vmx文件的完整路径
    # :param vm_name: 虚拟机名称（可选，默认使用vmx文件名）
    # #####################################################################
    def loader_vmx(self, vmx_path: str, vm_name: str = None) -> ZMessage:
        import os
        if vm_name is None:
            # 从路径中提取虚拟机名称（不含扩展名）
            vm_name = os.path.splitext(os.path.basename(vmx_path))[0]
        return self.vmrest_api(
            "/vms/registration",
            {"name": vm_name, "path": vmx_path},
            "POST")

    # 删除虚拟机 ##########################################################
    # 从VMware Workstation中删除虚拟机
    # :param vm_name: 虚拟机名称
    # #####################################################################
    def delete_vmx(self, vm_name: str) -> ZMessage:
        vm_id = self.select_vid(vm_name)
        if not vm_id:
            return ZMessage(
                success=False,
                actions="delete_vmx",
                message=f"未找到虚拟机: {vm_name}"
            )
        return self.vmrest_api(f"/vms/{vm_id}", m="DELETE")

    # 获取虚拟机配置 ######################################################
    # 获取虚拟机配置信息
    # :param vm_name: 虚拟机名称
    # #####################################################################
    def config_get(self, vm_name: str) -> ZMessage:
        vm_id = self.select_vid(vm_name)
        if not vm_id:
            return ZMessage(
                success=False,
                actions="get_config",
                message=f"未找到虚拟机: {vm_name}"
            )
        return self.vmrest_api(f"/vms/{vm_id}")

    # 更新虚拟机配置 ######################################################
    # 更新虚拟机配置
    # :param vm_name: 虚拟机名称
    # :param config: 配置字典
    # #####################################################################
    def config_set(self, vm_name: str, config: dict) -> ZMessage:
        vm_id = self.select_vid(vm_name)
        if not vm_id:
            return ZMessage(
                success=False,
                actions="set_config",
                message=f"未找到虚拟机: {vm_name}"
            )
        return self.vmrest_api(f"/vms/{vm_id}", config, "PUT")

    # 更新VMX配置文件 ######################################################
    # 读取现有VMX文件内容，与新配置合并后返回
    # :param existing_vmx: 现有VMX文件内容
    # :param vm_conf: VMConfig对象
    # :return: 合并后的VMX内容
    # #####################################################################
    def update_vmx(self, existing_vmx: str, vm_conf: VMConfig, hs_config: HSConfig = None) -> str:
        # 生成新的配置内容
        new_vmx_content = self.create_vmx(vm_conf, hs_config)
        new_config_lines = new_vmx_content.strip().split('\n')
        white_list_conf = [
            "uuid.bios", "uuid.location", "vm.genid", "vm.genidX"
        ]
        # 解析现有VMX文件，只保留白名单中的字段
        existing_config = {}
        existing_lines = existing_vmx.strip().split('\n')

        for line in existing_lines:
            line = line.strip()
            if line and '=' in line and not line.startswith('#'):
                key_part = line.split('=')[0].strip()
                value_part = line.split('=', 1)[1].strip()
                # 只保留白名单中的字段
                if key_part in white_list_conf:
                    existing_config[key_part] = value_part

        # 解析新配置并创建更新后的配置
        updated_config = {}

        for line in new_config_lines:
            line = line.strip()
            if line and '=' in line and not line.startswith('#'):
                key_part = line.split('=')[0].strip()
                value_part = line.split('=', 1)[1].strip()
                # 使用新配置
                updated_config[key_part] = value_part

        # 将白名单中的字段添加到更新后的配置中
        for key, value in existing_config.items():
            updated_config[key] = value

        # 重新构建VMX内容
        result_lines = []
        for key, value in sorted(updated_config.items()):
            result_lines.append(f"{key} = {value}")

        return '\n'.join(result_lines) + '\n'

    # 获取网络列表 ########################################################
    # 获取所有虚拟网络
    # #####################################################################
    def return_net(self) -> ZMessage:
        return self.vmrest_api("/vmnet")

    # 创建虚拟机 ##########################################################
    # :param vm_conf: VMConfig对象
    # :return: 虚拟机名称
    # #####################################################################
    def create_vmx(self, vm_conf: VMConfig = None, hs_config: HSConfig = None) -> str:
        sys_system = {
            "windows11": "windows10-64",
            "win11": "windows10-64",
            "windows10": "windows9-64",
            "win10": "windows9-64",
            "windows8.1": "windows8-64",
            "windows81": "windows8-64",
            "win81": "windows8-64",
            "windows8": "windows8-64",
            "windows80": "windows8-64",
            "win80": "windows8-64",
            "windows07": "windows7-64",
            "win07": "windows7-64",
            "windowsvista": "winvista-64",
            "winvi": "winvista-64",
            "windowsxp": "winxppro-64",
            "winxp": "winxppro-64",
            "windows2025": "windows10Server-64",
            "win25": "windows9Server-64",
            "windows2022": "windows10Server-64",
            "win22": "windows9Server-64",
            "windows2019": "windows8Server-64",
            "win19": "windows8Server-64",
            "windows2016": "windows8Server-64",
            "win16": "windows8Server-64",
            "windows2012r2": "windows8Server-64",
            "win12r2": "windows8Server-64",
            "windows2012": "windows8Server-64",
            "win12": "windows8Server-64",
            "windows2008r2": "windows7Server-64",
            "win08r2": "windows7Server-64",
            "windows2008": "windows7Server-64",
            "win08": "windows7Server-64",
            "windows2003r2": "windowsNetServer-64",
            "win03r2": "windowsNetServer-64",
            "windows2003": "windowsNetServer-64",
            "win03": "windowsNetServer-64",
            "ubuntu": "ubuntu-64",
            "debian12": "debian12-64",
            "debian11": "debian11-64",
            "debian10": "debian10-64",
            "debian9": "debian9-64",
            "debian8": "debian8-64",
            "debian7": "debian7-64",
            "debian": "debian12-64",
            "centos8": "centos8-64",
            "centos7": "centos7-64",
            "centos6": "centos6-64",
            "centos": "centos8-64",
            "fedora": "fedora-64",
            "rockylinux-64": "rockylinux-64",
            "alpine": "other6xlinux-64",
            "mint": "other6xlinux-64",
            "archlinux": "other6xlinux-64",
            "opensuse": "other6xlinux-64",
            "tlinux": "other6xlinux-64",
            "arch": "other6xlinux-64",
            "zorin": "other6xlinux-64",
            "solus": "other6xlinux-64",
            "elementary": "other6xlinux-64",
            "pop": "other6xlinux-64",
            "deepin": "other6xlinux-64",
            "manjaro": "other6xlinux-64",
            "mx": "other6xlinux-64",
            "cachy": "other6xlinux-64",
            "endeavour": "other6xlinux-64",
            "linux": "other6xlinux-64",
            "macos12": "darwin18-64",
            "macos11": "darwin18-64",
            "macos1015": "darwin18-64",
            "macos1014": "darwin18-64",
            "solaris11": "solaris11-64",
            "solaris10": "solaris10-64",
            "rhel8": "rhel8-64",
            "rhel7": "rhel7-64",
            "rhel6": "rhel6-64",
        }
        hdd_select = {
            "windows11": "nvme0",
            "win11": "nvme0",
            "windows10": "nvme0",
            "win10": "nvme0",
            "windows81": "nvme0",
            "win81": "nvme0",
            "windows8": "nvme0",
            "win08": "nvme0",
        }
        # 获取系统类型 ============================================
        vmx_system = "other-64"
        for now_prefix in sys_system:
            if vm_conf.os_name.lower().startswith(now_prefix):
                vmx_system = sys_system[now_prefix]
                break
        # 获取磁盘类型 ============================================
        hdd_system = "scsi0"
        # for now_prefix in hdd_select:
        #     if vm_conf.os_name.lower().startswith(now_prefix):
        #         hdd_system = hdd_select[now_prefix]
        #         break
        # 生成VMX配置 =============================================
        vmx_config = {
            # 编码配置 ============================================
            ".encoding": "GBK",
            "config.version": "8",
            "virtualHW.version": str(self.ver_agent),
            # 基本配置 ============================================
            "displayName": vm_conf.vm_uuid,
            "firmware": "efi",
            "guestOS": vmx_system,
            # 硬件配置 ============================================
            "numvcpus": str(vm_conf.cpu_num),
            "cpuid.coresPerSocket": str(vm_conf.cpu_num),
            "memsize": str(vm_conf.mem_num),
            "mem.hotadd": "TRUE",
            "mks.enable3d": "TRUE",
            "svga.graphicsMemoryKB": str(vm_conf.gpu_mem * 1024),
            # 设备配置 ============================================
            "vmci0.present": "TRUE",
            "hpet0.present": "TRUE",
            "sata0.present": "TRUE",
            "usb.present": "TRUE",
            "ehci.present": "TRUE",
            "usb_xhci.present": "TRUE",
            "tools.syncTime": "TRUE",
            "floppy0.present": "FALSE",
            "nvram": vm_conf.vm_uuid + ".nvram",
            "virtualHW.productCompatibility": "hosted",
            "extendedConfigFile": vm_conf.vm_uuid + ".vmxf",
            # PCI桥接配置 =========================================
            "pciBridge0": {
                "present": "TRUE"
            },
            "pciBridge4": {
                "present": "TRUE",
                "virtualDev": "pcieRootPort",
                "functions": "8"
            },
            # 系统盘配置 ==========================================
            f"{hdd_system}:0": {
                "fileName": vm_conf.vm_uuid + ".vmdk",
                "present": "TRUE"
            },
            # 远程显示配置 ========================================
            "RemoteDisplay": {
                "vnc": {
                    "enabled": "TRUE",
                    "port": vm_conf.vc_port,
                    "password": vm_conf.vc_pass,
                }
            }
        }
        # if hdd_system == "nvme0":
        #     vmx_config["nvme0.present"] = "TRUE"
        nic_uuid = 0  # 网卡配置 ==========================================
        for nic_name, nic_data in vm_conf.nic_all.items():
            use_auto = nic_data.mac_addr is None or nic_data.mac_addr == ""
            nic_types = ""
            if nic_data.nic_type == 'nat':
                nic_types = hs_config.network_nat
            elif nic_data.nic_type == 'pub':
                nic_types = hs_config.network_pub
            vmx_config[f"ethernet{nic_uuid}"] = {
                "connectionType": nic_types,
                "addressType": "generated" if use_auto else "static",
                "address": nic_data.mac_addr if not use_auto else "",
                "virtualDev": "e1000e",
                "present": "TRUE",
                "txbw.limit": str(vm_conf.speed_u * 1024),
                "rxbw.limit": str(vm_conf.speed_d * 1024),
            }
            nic_uuid += 1
        hdd_nums = 1  # 数据磁盘 ==========================================
        for hdd_name, hdd_data in vm_conf.hdd_all.items():
            if hdd_data.hdd_flag == 0:
                continue
            vmx_disk = os.path.join(self.host_path, "vmware-vdiskmanager.exe")
            vmx_name = os.path.join(
                hs_config.system_path, vm_conf.vm_uuid,
                f"{vm_conf.vm_uuid}-{hdd_name}.vmdk")
            if os.path.exists(vmx_name):
                continue
            vmd_cmds = [vmx_disk, "-c", "-s", f"{hdd_data.hdd_size}MB",
                        "-a", "lsilogic", "-t", "0", vmx_name]
            subprocess.run(vmd_cmds, shell=True)
            vmx_config[f"{hdd_system}:{hdd_nums}"] = {
                "fileName": vm_conf.vm_uuid + f"-{hdd_name}.vmdk",
                "present": "TRUE"
            }
            hdd_nums += 1
        # 如果是NVME则重置ID ==============================================
        # if hdd_system == "nvme0":
        #     hdd_nums = 1
        # 光盘镜像 ========================================================
        for iso_name in vm_conf.iso_all:
            iso_data = vm_conf.iso_all[iso_name]
            iso_full = os.path.join(hs_config.dvdrom_path, iso_data.iso_file)  # 使用dvdrom_path存储光盘镜像
            vmx_config[f"scsi0:{str(hdd_nums)}"] = {
                "fileName": iso_full,
                "present": "TRUE",
                "deviceType": "cdrom-image"
            }
            hdd_nums += 1
        # 按efi_all顺序重新排列磁盘配置 ====================================
        vmx_config = self._apply_efi_order(vmx_config, vm_conf, hdd_system)
        return VRestAPI.create_txt(vmx_config)

    # 按efi_all顺序重新排列VMX磁盘配置 ####################################
    # :param vmx_config: 当前VMX配置字典
    # :param vm_conf: VMConfig对象
    # :param hdd_system: 磁盘控制器前缀（如scsi0）
    # :return: 重新排列后的VMX配置字典
    # #####################################################################
    def _apply_efi_order(self, vmx_config: dict, vm_conf: VMConfig,
                         hdd_system: str = "scsi0") -> dict:
        if not vm_conf.efi_all:
            return vmx_config
        # 收集所有磁盘/光盘条目（key -> 配置）
        disk_entries = {}  # efi_name -> (key, value)
        # 系统盘：vm_uuid.vmdk -> hdd_system:0
        sys_key = f"{hdd_system}:0"
        if sys_key in vmx_config:
            disk_entries[vm_conf.vm_uuid] = (sys_key, vmx_config[sys_key])
        # 数据盘：vm_uuid-hdd_name.vmdk -> hdd_system:N
        for hdd_name in vm_conf.hdd_all:
            for k, v in vmx_config.items():
                if isinstance(v, dict) and v.get("fileName", "").endswith(
                        f"{vm_conf.vm_uuid}-{hdd_name}.vmdk"):
                    disk_entries[f"{vm_conf.vm_uuid}-{hdd_name}"] = (k, v)
                    break
        # 光盘：iso_name -> scsi0:N
        for iso_name in vm_conf.iso_all:
            for k, v in vmx_config.items():
                if isinstance(v, dict) and v.get("deviceType") == "cdrom-image":
                    iso_data = vm_conf.iso_all[iso_name]
                    if iso_data.iso_file in v.get("fileName", ""):
                        disk_entries[iso_name] = (k, v)
                        break
        # 按efi_all顺序重新分配磁盘槽位
        ordered_entries = []
        for efi_item in vm_conf.efi_all:
            efi_name = efi_item.efi_name
            if efi_name in disk_entries:
                ordered_entries.append(disk_entries[efi_name])
        # 将未在efi_all中的磁盘追加到末尾
        efi_names = {e.efi_name for e in vm_conf.efi_all}
        for name, entry in disk_entries.items():
            if name not in efi_names:
                ordered_entries.append(entry)
        if not ordered_entries:
            return vmx_config
        # 移除旧的磁盘配置，按新顺序重新写入
        old_keys = {entry[0] for entry in disk_entries.values()}
        new_config = {k: v for k, v in vmx_config.items() if k not in old_keys}
        slot = 0
        for _, entry_val in ordered_entries:
            is_cdrom = isinstance(entry_val, dict) and \
                       entry_val.get("deviceType") == "cdrom-image"
            if is_cdrom:
                new_config[f"scsi0:{slot}"] = entry_val
            else:
                new_config[f"{hdd_system}:{slot}"] = entry_val
            slot += 1
        return new_config

    # 扩展VM磁盘 ##########################################################
    # :param vm_vmdk: VM磁盘文件路径
    # :param vm_size: VM磁盘大小
    # :return: ZMessage
    # #####################################################################
    def extend_hdd(self, vm_vmdk, vm_size) -> ZMessage:
        vm_disk = os.path.join(self.host_path, "vmware-vdiskmanager.exe")
        logger.info(f"[VMCreate] 开始扩展硬盘: {vm_size}MB")
        logger.debug(f"[VMCreate] 执行命令: {vm_disk} -x {vm_size}MB {vm_vmdk}")

        vm_exec = subprocess.Popen(
            [vm_disk, "-x", f"{vm_size}MB", vm_vmdk],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = vm_exec.communicate(timeout=60)
        if vm_exec.returncode != 0:
            error_msg = f"硬盘扩展失败: {stderr.strip() if stderr else ''}"
            logger.error(f"[VMCreate] {error_msg}")
        logger.info(f"[VMCreate] 硬盘扩展完成: {vm_size}MB")
        return ZMessage(
            success=True if vm_exec.returncode == 0 else False,
            actions="extend_hdd",
            message="硬盘扩展成功" if vm_exec.returncode == 0 \
                else f"硬盘扩展失败: {stderr.strip() if stderr else ''}")

    # 备份VM磁盘 ##########################################################
    # :param vmx_path: VMX文件路径
    def backup_vmx(self, vmx_path: str) -> ZMessage:
        pass

    # 重置VM磁盘 ##########################################################
    # :param vmx_path: VMX文件路径
    def resets_vmx(self, vmx_path: str) -> ZMessage:
        pass

    # 查找虚拟机VMX路径 ##################################################
    # 根据虚拟机名称查找VMX文件路径
    # :param vm_name: 虚拟机名称
    # :return: ZMessage对象，results中包含vm_path
    # #####################################################################
    def find_vmx_path(self, vm_name: str) -> ZMessage:
        try:
            # 获取虚拟机列表
            vm_info_result = self.return_vmx()
            if not vm_info_result.success:
                return ZMessage(
                    success=False,
                    actions="find_vmx_path",
                    message=f"获取虚拟机列表失败: {vm_info_result.message}"
                )
            
            # 查找匹配的虚拟机路径
            vm_path = ""
            for vm_info in vm_info_result.results:
                if vm_info.get("path", "").find(vm_name) > 0:
                    vm_path = vm_info.get("path", "")
                    break
            
            if not vm_path:
                return ZMessage(
                    success=False,
                    actions="find_vmx_path",
                    message=f"未找到虚拟机 {vm_name} 的VMX路径"
                )
            
            return ZMessage(
                success=True,
                actions="find_vmx_path",
                message="成功找到VMX路径",
                results={"vm_path": vm_path}
            )
            
        except Exception as e:
            error_msg = f"查找VMX路径时出错: {str(e)}"
            logger.error(f"[find_vmx_path] {error_msg}")
            return ZMessage(
                success=False,
                actions="find_vmx_path",
                message=error_msg,
                execute=e
            )

    # 执行vmrun命令 #######################################################
    def execute_vmrun(self, command: str, vm_path: str, args: list = None,
                     vc_user: str = None, vc_pass: str = None) -> ZMessage:
        try:
            vmrun_path = os.path.join(self.host_path, "vmrun.exe")
            if not os.path.exists(vmrun_path):
                return ZMessage(
                    success=False,
                    actions="execute_vmrun",
                    message="未找到vmrun.exe文件"
                )

            # 构建命令
            cmd = [vmrun_path, "-T", "ws"]

            # 如果提供了客户机凭据，添加认证参数
            if vc_user and vc_pass:
                cmd.extend(["-gu", vc_user, "-gp", vc_pass])
            
            # 添加命令和VMX路径
            cmd.append(command)
            cmd.append(vm_path)
            
            # 添加其他参数
            if args:
                cmd.extend(args)
            
            # 执行命令
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                encoding='utf-8', 
                errors='replace'
            )
            logger.info(f"[execute_vmrun] 成功执行vmrun命令: {command}")
            return ZMessage(
                success=True,
                actions="execute_vmrun",
                message="命令执行成功",
                results={"stdout": result.stdout, "stderr": result.stderr}
            )
            
        except Exception as e:
            error_msg = f"执行vmrun命令时出错: {str(e)}"
            logger.error(f"[execute_vmrun] {error_msg}")
            import traceback
            traceback.print_exc()
            return ZMessage(
                success=False,
                actions="execute_vmrun",
                message=error_msg,
                execute=e
            )

    # 虚拟机截图 ##########################################################
    # 使用vmrun命令获取虚拟机截图
    # :param vm_name: 虚拟机名称
    # :param screenshot_path: 截图保存路径
    # :param guest_user: 客户机用户名（可选）
    # :param guest_pass: 客户机密码（可选）
    # :return: ZMessage对象
    # #####################################################################
    def capture_screen(self, vm_name: str, screenshot_path: str,
                      guest_user: str = None, guest_pass: str = None) -> ZMessage:
        try:
            # 查找VMX路径
            vmx_result = self.find_vmx_path(vm_name)
            if not vmx_result.success:
                return vmx_result
            
            vm_path = vmx_result.results.get("vm_path", "")
            
            # 执行vmrun截图命令
            capture_result = self.execute_vmrun(
                "captureScreen",
                vm_path,
                [screenshot_path],
                guest_user,
                guest_pass
            )
            
            if not capture_result.success:
                return capture_result
            
            # 检查截图文件是否存在
            if not os.path.exists(screenshot_path):
                return ZMessage(
                    success=False,
                    actions="capture_screen",
                    message=f"截图文件不存在: {screenshot_path}"
                )
            
            logger.info(f"[capture_screen] 成功获取虚拟机截图: {screenshot_path}")
            return ZMessage(
                success=True,
                actions="capture_screen",
                message="截图成功",
                results={"screenshot_path": screenshot_path}
            )
            
        except Exception as e:
            error_msg = f"获取虚拟机截图时出错: {str(e)}"
            logger.error(f"[capture_screen] {error_msg}")
            import traceback
            traceback.print_exc()
            return ZMessage(
                success=False,
                actions="capture_screen",
                message=error_msg,
                execute=e
            )
