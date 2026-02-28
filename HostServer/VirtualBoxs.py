# VirtualBoxs - Oracle VirtualBox 虚拟化平台管理 ################################
# 提供VirtualBox虚拟机的创建、管理和监控功能
# 依赖: pip install virtualbox
################################################################################
import os
import shutil
import subprocess
import traceback
import tempfile
import time
from copy import deepcopy
from loguru import logger
from HostServer.BasicServer import BasicServer
from MainObject.Config.HSConfig import HSConfig
from MainObject.Config.IMConfig import IMConfig
from MainObject.Config.SDConfig import SDConfig
from MainObject.Config.VFConfig import VFConfig
from MainObject.Config.VMPowers import VMPowers
from MainObject.Public.HWStatus import HWStatus
from MainObject.Public.ZMessage import ZMessage
from MainObject.Config.VMConfig import VMConfig
from MainObject.Config.USBInfos import USBInfos


class HostServer(BasicServer):
    # 宿主机服务 ===============================================================
    def __init__(self, config: HSConfig, **kwargs):
        super().__init__(config, **kwargs)
        super().__load__(**kwargs)
        self._vbox = None  # virtualbox.VirtualBox 实例（懒加载）

    # 获取VirtualBox实例（懒加载）=============================================
    def _get_vbox(self):
        """获取VirtualBox实例，懒加载"""
        if self._vbox is None:
            try:
                import virtualbox
                self._vbox = virtualbox.VirtualBox()
            except ImportError:
                raise RuntimeError(
                    "未安装virtualbox模块，请执行: pip install virtualbox")
        return self._vbox

    # 获取虚拟机对象 ===========================================================
    def _get_machine(self, vm_name: str):
        """根据名称获取VirtualBox Machine对象"""
        try:
            vbox = self._get_vbox()
            return vbox.find_machine(vm_name)
        except Exception:
            return None

    # 执行VBoxManage命令 =======================================================
    def _vboxmanage(self, *args, timeout: int = 60) -> tuple[bool, str, str]:
        """
        执行VBoxManage命令行工具
        :return: (success, stdout, stderr)
        """
        try:
            vboxmanage = self.hs_config.launch_path or "VBoxManage"
            if os.path.isdir(vboxmanage):
                # launch_path是目录，拼接可执行文件名
                import platform
                exe = "VBoxManage.exe" if platform.system() == "Windows" else "VBoxManage"
                vboxmanage = os.path.join(vboxmanage, exe)

            cmd = [vboxmanage] + list(args)
            logger.debug(f"[VirtualBox] 执行命令: {' '.join(cmd)}")

            # Windows隐藏窗口
            kwargs = {}
            import platform
            if platform.system() == "Windows":
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                si.wShowWindow = subprocess.SW_HIDE
                kwargs["startupinfo"] = si
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=timeout, **kwargs)
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", f"命令超时({timeout}s)"
        except FileNotFoundError:
            return False, "", "VBoxManage未找到，请检查launch_path配置"
        except Exception as e:
            return False, "", str(e)

    # 获取虚拟机路径 ===========================================================
    def _get_vm_path(self, vm_uuid: str) -> str:
        """获取虚拟机目录路径"""
        return os.path.join(self.hs_config.system_path, vm_uuid)

    # 检查虚拟机是否存在 =======================================================
    def _get_vm_flag(self, vm_name: str) -> tuple:
        """检查虚拟机是否存在，返回(是否存在, 虚拟机配置或None)"""
        if vm_name not in self.vm_saving:
            return False, None
        return True, self.vm_saving[vm_name]

    # 宿主机任务 ===============================================================
    def Crontabs(self) -> bool:
        return super().Crontabs()

    # 宿主机状态 ===============================================================
    def HSStatus(self) -> HWStatus:
        try:
            hw = HWStatus()
            # 通过VBoxManage获取宿主机信息
            ok, stdout, _ = self._vboxmanage("list", "hostinfo")
            if ok:
                for line in stdout.splitlines():
                    if "Processor count:" in line:
                        hw.cpu_num = int(line.split(":")[-1].strip())
                    elif "Memory size:" in line:
                        val = line.split(":")[-1].strip()
                        hw.mem_all = int(val.replace("MByte", "").strip())
            # 统计运行中的虚拟机数量
            hw.vm_nums = len(self.vm_saving)
            hw.vm_runs = sum(
                1 for v in self.vm_saving.values()
                if v.vm_flag == VMPowers.STARTED)
            self.host_set(hw)
            return hw
        except Exception as e:
            logger.error(f"[VirtualBox] 获取宿主机状态失败: {e}")
            return super().HSStatus()

    # 初始宿主机 ===============================================================
    def HSCreate(self) -> ZMessage:
        return super().HSCreate()

    # 还原宿主机 ===============================================================
    def HSDelete(self) -> ZMessage:
        return super().HSDelete()

    # 读取宿主机 ===============================================================
    def HSLoader(self) -> ZMessage:
        try:
            # 验证VBoxManage可用
            ok, stdout, stderr = self._vboxmanage("--version")
            if not ok:
                return ZMessage(
                    success=False, action="HSLoader",
                    message=f"VBoxManage不可用: {stderr}")
            logger.info(f"[VirtualBox] VBoxManage版本: {stdout.strip()}")
            return super().HSLoader()
        except Exception as e:
            logger.error(f"[VirtualBox] 加载失败: {e}")
            return ZMessage(success=False, action="HSLoader", message=str(e))

    # 卸载宿主机 ===============================================================
    def HSUnload(self) -> ZMessage:
        self._vbox = None
        return super().HSUnload()

    # 虚拟机状态 ===============================================================
    def VMStatus(self, vm_name: str = "",
                 s_t: int = None, e_t: int = None) -> dict[str, list[HWStatus]]:
        return super().VMStatus(vm_name, s_t, e_t)

    # 虚拟机扫描 ===============================================================
    def VMDetect(self) -> ZMessage:
        try:
            filter_prefix = self.hs_config.filter_name
            ok, stdout, stderr = self._vboxmanage("list", "vms")
            if not ok:
                return ZMessage(
                    success=False, action="VMDetect",
                    message=f"获取虚拟机列表失败: {stderr}")

            scanned_count = 0
            added_count = 0
            # 格式: "VMName" {uuid}
            for line in stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                # 解析名称
                if '"' not in line:
                    continue
                vm_name = line.split('"')[1]
                if filter_prefix and not vm_name.startswith(filter_prefix):
                    continue
                scanned_count += 1
                if vm_name in self.vm_saving:
                    continue
                self.vm_saving[vm_name] = VMConfig()
                added_count += 1
                self.push_log(ZMessage(
                    success=True, action="VMDetect",
                    message=f"发现并添加虚拟机: {vm_name}"))

            if added_count > 0:
                self.data_set()

            return ZMessage(
                success=True, action="VMDetect",
                message=f"扫描完成，共{scanned_count}台，新增{added_count}台",
                results={"scanned": scanned_count, "added": added_count})
        except Exception as e:
            logger.error(f"[VirtualBox] 扫描虚拟机失败: {e}")
            traceback.print_exc()
            return ZMessage(success=False, action="VMDetect", message=str(e))

    # 创建虚拟机 ===============================================================
    def VMCreate(self, vm_conf: VMConfig) -> ZMessage:
        try:
            logger.info(f"[VirtualBox] 开始创建虚拟机: {vm_conf.vm_uuid}")

            # 网络检查 =========================================================
            vm_conf, net_result = self.NetCheck(vm_conf)
            if not net_result.success:
                return net_result
            self.IPBinder(vm_conf, True)

            vm_path = self._get_vm_path(vm_conf.vm_uuid)
            os.makedirs(vm_path, exist_ok=True)

            # 1. 创建虚拟机 ====================================================
            ok, out, err = self._vboxmanage(
                "createvm",
                "--name", vm_conf.vm_uuid,
                "--basefolder", self.hs_config.system_path,
                "--register")
            if not ok:
                raise Exception(f"创建虚拟机失败: {err}")

            # 2. 设置CPU和内存 =================================================
            ok, out, err = self._vboxmanage(
                "modifyvm", vm_conf.vm_uuid,
                "--cpus", str(vm_conf.cpu_num),
                "--memory", str(vm_conf.mem_num),
                "--vram", str(max(vm_conf.gpu_mem or 16, 16)),
                "--acpi", "on",
                "--ioapic", "on",
                "--boot1", "disk",
                "--boot2", "dvd",
                "--boot3", "none")
            if not ok:
                raise Exception(f"设置VM参数失败: {err}")

            # 3. 创建存储控制器 ================================================
            ok, out, err = self._vboxmanage(
                "storagectl", vm_conf.vm_uuid,
                "--name", "SATA Controller",
                "--add", "sata",
                "--controller", "IntelAhci",
                "--portcount", "4")
            if not ok:
                raise Exception(f"创建存储控制器失败: {err}")

            # 4. 创建并挂载系统盘 ==============================================
            vdi_path = os.path.join(vm_path, f"{vm_conf.vm_uuid}.vdi")
            # 如果有镜像文件，先复制
            if vm_conf.os_name:
                im_file = os.path.join(
                    self.hs_config.images_path, vm_conf.os_name)
                if os.path.exists(im_file):
                    # 克隆镜像为VDI
                    ok, out, err = self._vboxmanage(
                        "clonemedium", im_file, vdi_path,
                        "--format", "VDI")
                    if not ok:
                        # 尝试直接创建空盘
                        logger.warning(f"[VirtualBox] 克隆镜像失败，创建空盘: {err}")
                        ok, out, err = self._vboxmanage(
                            "createmedium", "disk",
                            "--filename", vdi_path,
                            "--size", str(vm_conf.hdd_num * 1024),
                            "--format", "VDI")
                        if not ok:
                            raise Exception(f"创建虚拟磁盘失败: {err}")
                else:
                    ok, out, err = self._vboxmanage(
                        "createmedium", "disk",
                        "--filename", vdi_path,
                        "--size", str(vm_conf.hdd_num * 1024),
                        "--format", "VDI")
                    if not ok:
                        raise Exception(f"创建虚拟磁盘失败: {err}")
            else:
                ok, out, err = self._vboxmanage(
                    "createmedium", "disk",
                    "--filename", vdi_path,
                    "--size", str(vm_conf.hdd_num * 1024),
                    "--format", "VDI")
                if not ok:
                    raise Exception(f"创建虚拟磁盘失败: {err}")

            # 挂载系统盘 =======================================================
            ok, out, err = self._vboxmanage(
                "storageattach", vm_conf.vm_uuid,
                "--storagectl", "SATA Controller",
                "--port", "0",
                "--device", "0",
                "--type", "hdd",
                "--medium", vdi_path)
            if not ok:
                raise Exception(f"挂载系统盘失败: {err}")

            # 5. 配置网络 ======================================================
            nic_index = 1
            for nic_name, nic_conf in vm_conf.nic_all.items():
                if nic_index > 4:
                    break
                ok, out, err = self._vboxmanage(
                    "modifyvm", vm_conf.vm_uuid,
                    f"--nic{nic_index}", "bridged",
                    f"--bridgeadapter{nic_index}",
                    self.hs_config.network_nat or "eth0",
                    f"--macaddress{nic_index}",
                    nic_conf.mac_addr.replace(":", "").upper()
                    if nic_conf.mac_addr else "auto")
                nic_index += 1

            # 6. 启动虚拟机 ====================================================
            self.VMPowers(vm_conf.vm_uuid, VMPowers.S_START)

            # 填充启动项 =======================================================
            if not vm_conf.efi_all:
                vm_conf.efi_all = self.efi_build(vm_conf)

            return super().VMCreate(vm_conf)

        except Exception as e:
            logger.error(f"[VirtualBox] 创建虚拟机失败: {e}")
            traceback.print_exc()
            # 清理
            try:
                self._vboxmanage(
                    "unregistervm", vm_conf.vm_uuid, "--delete")
            except Exception:
                pass
            vm_path = self._get_vm_path(vm_conf.vm_uuid)
            if os.path.exists(vm_path):
                shutil.rmtree(vm_path, ignore_errors=True)
            hs_result = ZMessage(
                success=False, action="VMCreate",
                message=f"虚拟机创建失败: {str(e)}")
            self.logs_set(hs_result)
            return hs_result

    # 安装虚拟机 ===============================================================
    def VMSetups(self, vm_conf: VMConfig) -> ZMessage:
        """重装系统：删除旧盘，重新克隆镜像"""
        try:
            logger.info(f"[VirtualBox] 重装系统: {vm_conf.vm_uuid}")
            vm_path = self._get_vm_path(vm_conf.vm_uuid)
            vdi_path = os.path.join(vm_path, f"{vm_conf.vm_uuid}.vdi")

            # 先卸载旧盘
            self._vboxmanage(
                "storageattach", vm_conf.vm_uuid,
                "--storagectl", "SATA Controller",
                "--port", "0", "--device", "0",
                "--medium", "none")
            # 删除旧VDI
            if os.path.exists(vdi_path):
                self._vboxmanage("closemedium", "disk", vdi_path, "--delete")

            # 克隆新镜像
            im_file = os.path.join(
                self.hs_config.images_path, vm_conf.os_name)
            if os.path.exists(im_file):
                ok, out, err = self._vboxmanage(
                    "clonemedium", im_file, vdi_path, "--format", "VDI")
            else:
                ok, out, err = self._vboxmanage(
                    "createmedium", "disk",
                    "--filename", vdi_path,
                    "--size", str(vm_conf.hdd_num * 1024),
                    "--format", "VDI")
            if not ok:
                return ZMessage(
                    success=False, action="VMSetups",
                    message=f"创建磁盘失败: {err}")

            # 重新挂载
            ok, out, err = self._vboxmanage(
                "storageattach", vm_conf.vm_uuid,
                "--storagectl", "SATA Controller",
                "--port", "0", "--device", "0",
                "--type", "hdd", "--medium", vdi_path)
            if not ok:
                return ZMessage(
                    success=False, action="VMSetups",
                    message=f"挂载磁盘失败: {err}")

            return ZMessage(success=True, action="VMSetups", message="系统重装成功")
        except Exception as e:
            logger.error(f"[VirtualBox] 重装系统失败: {e}")
            return ZMessage(success=False, action="VMSetups", message=str(e))

    # 配置虚拟机 ===============================================================
    def VMUpdate(self, vm_conf: VMConfig, vm_last: VMConfig) -> ZMessage:
        try:
            logger.info(f"[VirtualBox] 更新虚拟机配置: {vm_conf.vm_uuid}")

            # 网络检查 =========================================================
            vm_conf, net_result = self.NetCheck(vm_conf)
            if not net_result.success:
                return net_result
            self.IPBinder(vm_conf, True)

            # 关机 =============================================================
            self.VMPowers(vm_conf.vm_uuid, VMPowers.H_CLOSE)
            time.sleep(2)

            # 更新CPU/内存 =====================================================
            ok, out, err = self._vboxmanage(
                "modifyvm", vm_conf.vm_uuid,
                "--cpus", str(vm_conf.cpu_num),
                "--memory", str(vm_conf.mem_num),
                "--vram", str(max(vm_conf.gpu_mem or 16, 16)))
            if not ok:
                logger.warning(f"[VirtualBox] 更新CPU/内存失败: {err}")

            # 重装系统 =========================================================
            if vm_conf.os_name != vm_last.os_name and vm_last.os_name != "":
                self.VMSetups(vm_conf)

            # 扩展硬盘 =========================================================
            if vm_conf.hdd_num > vm_last.hdd_num:
                vm_path = self._get_vm_path(vm_conf.vm_uuid)
                vdi_path = os.path.join(vm_path, f"{vm_conf.vm_uuid}.vdi")
                ok, out, err = self._vboxmanage(
                    "modifymedium", "disk", vdi_path,
                    "--resize", str(vm_conf.hdd_num * 1024))
                if not ok:
                    logger.warning(f"[VirtualBox] 扩展硬盘失败: {err}")

            # 更新网络 =========================================================
            self.IPUpdate(vm_conf, vm_last)
            nic_index = 1
            for nic_name, nic_conf in vm_conf.nic_all.items():
                if nic_index > 4:
                    break
                self._vboxmanage(
                    "modifyvm", vm_conf.vm_uuid,
                    f"--nic{nic_index}", "bridged",
                    f"--bridgeadapter{nic_index}",
                    self.hs_config.network_nat or "eth0")
                nic_index += 1

            # 启动 =============================================================
            self.VMPowers(vm_conf.vm_uuid, VMPowers.S_START)
            self.vm_saving[vm_conf.vm_uuid] = vm_conf

            return super().VMUpdate(vm_conf, vm_last)
        except Exception as e:
            logger.error(f"[VirtualBox] 更新虚拟机失败: {e}")
            traceback.print_exc()
            return ZMessage(success=False, action="VMUpdate", message=str(e))

    # 删除虚拟机 ===============================================================
    def VMDelete(self, vm_name: str, rm_back=True) -> ZMessage:
        try:
            logger.info(f"[VirtualBox] 删除虚拟机: {vm_name}")
            exists, vm_conf = self._get_vm_flag(vm_name)
            if not exists:
                return ZMessage(
                    success=False, action="VMDelete",
                    message=f"虚拟机 {vm_name} 不存在")

            # 关机 =============================================================
            self.VMPowers(vm_name, VMPowers.H_CLOSE)
            time.sleep(2)

            # 解绑IP ===========================================================
            self.IPBinder(vm_conf, False)

            # 注销并删除文件 ===================================================
            ok, out, err = self._vboxmanage(
                "unregistervm", vm_name, "--delete")
            if not ok:
                logger.warning(f"[VirtualBox] 注销虚拟机失败: {err}")

            return super().VMDelete(vm_name, rm_back)
        except Exception as e:
            logger.error(f"[VirtualBox] 删除虚拟机失败: {e}")
            traceback.print_exc()
            return ZMessage(success=False, action="VMDelete", message=str(e))

    # 虚拟机电源 ===============================================================
    def VMPowers(self, vm_name: str, power: VMPowers) -> ZMessage:
        try:
            power_map = {
                VMPowers.S_START: "启动",
                VMPowers.S_CLOSE: "关机",
                VMPowers.H_CLOSE: "强制关机",
                VMPowers.S_RESET: "重启",
                VMPowers.H_RESET: "强制重启",
                VMPowers.A_PAUSE: "暂停",
                VMPowers.A_WAKED: "恢复"
            }
            logger.info(
                f"[VirtualBox] 电源操作: {vm_name} - "
                f"{power_map.get(power, str(power))}")

            # 先调用父类设置中间状态
            parent_result = super().VMPowers(vm_name, power)
            original_flag = (parent_result.results.get("original_flag")
                             if parent_result.results else None)

            if power == VMPowers.S_START:
                # 无头模式启动
                ok, out, err = self._vboxmanage(
                    "startvm", vm_name, "--type", "headless")
                hs_result = ZMessage(
                    success=ok, action="VMPowers",
                    message="启动成功" if ok else f"启动失败: {err}")
            elif power == VMPowers.S_CLOSE:
                ok, out, err = self._vboxmanage(
                    "controlvm", vm_name, "acpipowerbutton")
                hs_result = ZMessage(
                    success=ok, action="VMPowers",
                    message="正在软关机" if ok else f"关机失败: {err}")
                if ok:
                    self.soft_pwr(vm_name, VMPowers.S_CLOSE, VMPowers.ON_STOP)
            elif power == VMPowers.H_CLOSE:
                ok, out, err = self._vboxmanage(
                    "controlvm", vm_name, "poweroff")
                hs_result = ZMessage(
                    success=ok, action="VMPowers",
                    message="强制关机成功" if ok else f"强制关机失败: {err}")
            elif power == VMPowers.S_RESET:
                ok, out, err = self._vboxmanage(
                    "controlvm", vm_name, "reset")
                hs_result = ZMessage(
                    success=ok, action="VMPowers",
                    message="重启成功" if ok else f"重启失败: {err}")
                if ok:
                    self.soft_pwr(vm_name, VMPowers.S_RESET, VMPowers.ON_STOP)
            elif power == VMPowers.H_RESET:
                self._vboxmanage("controlvm", vm_name, "poweroff")
                time.sleep(2)
                ok, out, err = self._vboxmanage(
                    "startvm", vm_name, "--type", "headless")
                hs_result = ZMessage(
                    success=ok, action="VMPowers",
                    message="强制重启成功" if ok else f"强制重启失败: {err}")
            elif power == VMPowers.A_PAUSE:
                ok, out, err = self._vboxmanage(
                    "controlvm", vm_name, "pause")
                hs_result = ZMessage(
                    success=ok, action="VMPowers",
                    message="暂停成功" if ok else f"暂停失败: {err}")
            elif power == VMPowers.A_WAKED:
                ok, out, err = self._vboxmanage(
                    "controlvm", vm_name, "resume")
                hs_result = ZMessage(
                    success=ok, action="VMPowers",
                    message="恢复成功" if ok else f"恢复失败: {err}")
            else:
                hs_result = ZMessage(
                    success=False, action="VMPowers",
                    message=f"不支持的电源操作: {power}")

            # 操作失败回退状态
            if not hs_result.success and original_flag is not None:
                self.vm_saving[vm_name].vm_flag = original_flag
                self.data_set()
            elif hs_result.success and power not in [
                    VMPowers.S_CLOSE, VMPowers.S_RESET]:
                import threading
                def delayed_refresh():
                    time.sleep(3)
                    self.vm_loads(vm_name)
                threading.Thread(
                    target=delayed_refresh, daemon=True).start()

            self.logs_set(hs_result)
            return hs_result
        except Exception as e:
            logger.error(f"[VirtualBox] 电源操作失败: {e}")
            traceback.print_exc()
            return ZMessage(success=False, action="VMPowers", message=str(e))

    # 获取虚拟机实际状态 =======================================================
    def GetPower(self, vm_name: str) -> str:
        """从VBoxManage获取虚拟机实际状态"""
        try:
            ok, stdout, _ = self._vboxmanage(
                "showvminfo", vm_name, "--machinereadable")
            if not ok:
                return "未知"
            for line in stdout.splitlines():
                if line.startswith("VMState="):
                    state = line.split("=")[1].strip().strip('"')
                    state_map = {
                        "running": "运行中",
                        "paused": "已暂停",
                        "poweroff": "已关机",
                        "saved": "已保存",
                        "aborted": "已中止",
                        "starting": "启动中",
                        "stopping": "关机中",
                        "restoring": "恢复中",
                        "saving": "保存中",
                    }
                    return state_map.get(state, "未知")
            return "未知"
        except Exception as e:
            logger.warning(f"[VirtualBox] 获取虚拟机状态失败: {e}")
            return "未知"

    # 虚拟机截图 ===============================================================
    def VMScreen(self, vm_name: str = "") -> str:
        """截取虚拟机屏幕，返回base64编码的PNG"""
        try:
            import base64
            tmp_file = tempfile.mktemp(suffix=".png")
            ok, out, err = self._vboxmanage(
                "controlvm", vm_name,
                "screenshotpng", tmp_file)
            if ok and os.path.exists(tmp_file):
                with open(tmp_file, "rb") as f:
                    data = f.read()
                os.remove(tmp_file)
                return "data:image/png;base64," + base64.b64encode(data).decode()
            return ""
        except Exception as e:
            logger.warning(f"[VirtualBox] 截图失败: {e}")
            return ""

    # 修改密码 =================================================================
    def VMPasswd(self, vm_name: str, os_pass: str) -> ZMessage:
        """通过VBoxManage guestcontrol修改虚拟机密码"""
        try:
            if vm_name not in self.vm_saving:
                return ZMessage(
                    success=False, action="VMPasswd",
                    message="虚拟机不存在")
            vm_conf = self.vm_saving[vm_name]
            # 使用guestcontrol执行密码修改命令
            ok, out, err = self._vboxmanage(
                "guestcontrol", vm_name, "run",
                "--exe", "/bin/bash",
                "--username", vm_conf.os_user or "root",
                "--password", vm_conf.os_pass or "",
                "--", "bash", "-c",
                f"echo '{vm_conf.os_user or 'root'}:{os_pass}' | chpasswd",
                timeout=30)
            if ok:
                vm_conf.os_pass = os_pass
                self.data_set()
                return ZMessage(
                    success=True, action="VMPasswd",
                    message="密码修改成功")
            return ZMessage(
                success=False, action="VMPasswd",
                message=f"密码修改失败: {err}")
        except Exception as e:
            logger.error(f"[VirtualBox] 修改密码失败: {e}")
            return ZMessage(success=False, action="VMPasswd", message=str(e))

    # VNC获取 ==================================================================
    def VNCGets(self, vm_name: str) -> ZMessage:
        """获取VNC连接信息（通过VRDE）"""
        try:
            if vm_name not in self.vm_saving:
                return ZMessage(
                    success=False, action="VNCGets",
                    message="虚拟机不存在")
            # 获取VRDE端口
            ok, stdout, _ = self._vboxmanage(
                "showvminfo", vm_name, "--machinereadable")
            vrde_port = 3389
            if ok:
                for line in stdout.splitlines():
                    if line.startswith("vrdeport="):
                        try:
                            vrde_port = int(
                                line.split("=")[1].strip().strip('"'))
                        except ValueError:
                            pass
            host = self.hs_config.server_addr or "localhost"
            return ZMessage(
                success=True, action="VNCGets",
                message="VNC信息获取成功",
                results={
                    "host": host,
                    "port": vrde_port,
                    "type": "rdp"
                })
        except Exception as e:
            logger.error(f"[VirtualBox] 获取VNC信息失败: {e}")
            return ZMessage(success=False, action="VNCGets", message=str(e))

    # 启用VRDE（远程桌面）======================================================
    def _enable_vrde(self, vm_name: str, port: int = 3389) -> bool:
        """为虚拟机启用VRDE远程桌面"""
        ok, out, err = self._vboxmanage(
            "modifyvm", vm_name,
            "--vrde", "on",
            "--vrdeport", str(port),
            "--vrdeauthtype", "null")
        return ok

    # 备份虚拟机 ===============================================================
    def VMBackup(self, vm_name: str, vm_tips: str) -> ZMessage:
        return super().VMBackup(vm_name, vm_tips)

    # 恢复虚拟机 ===============================================================
    def Restores(self, vm_name: str, vm_back: str) -> ZMessage:
        return super().Restores(vm_name, vm_back)

    # 硬盘挂载 =================================================================
    def HDDMount(self, vm_name: str, vm_imgs: SDConfig, in_flag=True) -> ZMessage:
        try:
            if vm_name not in self.vm_saving:
                return ZMessage(
                    success=False, action="HDDMount",
                    message="虚拟机不存在")
            self.VMPowers(vm_name, VMPowers.H_CLOSE)
            time.sleep(2)

            vm_path = self._get_vm_path(vm_name)
            vdi_path = os.path.join(
                vm_path, f"{vm_name}-{vm_imgs.hdd_name}.vdi")

            if in_flag:
                # 创建新磁盘
                if not os.path.exists(vdi_path):
                    ok, out, err = self._vboxmanage(
                        "createmedium", "disk",
                        "--filename", vdi_path,
                        "--size", str(vm_imgs.hdd_size * 1024),
                        "--format", "VDI")
                    if not ok:
                        self.VMPowers(vm_name, VMPowers.S_START)
                        return ZMessage(
                            success=False, action="HDDMount",
                            message=f"创建磁盘失败: {err}")
                # 找空闲端口
                port = self._find_free_sata_port(vm_name)
                ok, out, err = self._vboxmanage(
                    "storageattach", vm_name,
                    "--storagectl", "SATA Controller",
                    "--port", str(port),
                    "--device", "0",
                    "--type", "hdd",
                    "--medium", vdi_path)
                if not ok:
                    self.VMPowers(vm_name, VMPowers.S_START)
                    return ZMessage(
                        success=False, action="HDDMount",
                        message=f"挂载磁盘失败: {err}")
                vm_imgs.hdd_flag = 1
                self.vm_saving[vm_name].hdd_all[vm_imgs.hdd_name] = vm_imgs
            else:
                # 卸载磁盘
                port = self._find_hdd_port(vm_name, vm_imgs.hdd_name)
                if port >= 0:
                    self._vboxmanage(
                        "storageattach", vm_name,
                        "--storagectl", "SATA Controller",
                        "--port", str(port),
                        "--device", "0",
                        "--medium", "none")
                if vm_imgs.hdd_name in self.vm_saving[vm_name].hdd_all:
                    self.vm_saving[vm_name].hdd_all[
                        vm_imgs.hdd_name].hdd_flag = 0

            self.data_set()
            self.VMPowers(vm_name, VMPowers.S_START)
            action_text = "挂载" if in_flag else "卸载"
            return ZMessage(
                success=True, action="HDDMount",
                message=f"磁盘{action_text}成功")
        except Exception as e:
            logger.error(f"[VirtualBox] 磁盘操作失败: {e}")
            return ZMessage(success=False, action="HDDMount", message=str(e))

    # 查找空闲SATA端口 =========================================================
    def _find_free_sata_port(self, vm_name: str) -> int:
        """查找空闲的SATA端口号（从1开始，0为系统盘）"""
        ok, stdout, _ = self._vboxmanage(
            "showvminfo", vm_name, "--machinereadable")
        used_ports = {0}  # 0号端口为系统盘
        if ok:
            for line in stdout.splitlines():
                if line.startswith("SATA-") and "-0-0=" in line:
                    try:
                        port = int(line.split("-")[1])
                        used_ports.add(port)
                    except (ValueError, IndexError):
                        pass
        for p in range(1, 30):
            if p not in used_ports:
                return p
        return 1

    # 查找磁盘所在端口 =========================================================
    def _find_hdd_port(self, vm_name: str, hdd_name: str) -> int:
        """查找指定磁盘名称对应的SATA端口"""
        ok, stdout, _ = self._vboxmanage(
            "showvminfo", vm_name, "--machinereadable")
        if ok:
            for line in stdout.splitlines():
                if hdd_name in line and "SATA-" in line:
                    try:
                        port = int(line.split("-")[1])
                        return port
                    except (ValueError, IndexError):
                        pass
        return -1

    # ISO镜像挂载 ==============================================================
    def ISOMount(self, vm_name: str, vm_imgs: IMConfig, in_flag=True) -> ZMessage:
        try:
            if vm_name not in self.vm_saving:
                return ZMessage(
                    success=False, action="ISOMount",
                    message="虚拟机不存在")
            self.VMPowers(vm_name, VMPowers.H_CLOSE)
            time.sleep(2)

            if in_flag:
                iso_full = os.path.join(
                    self.hs_config.dvdrom_path, vm_imgs.iso_file)
                if not os.path.exists(iso_full):
                    self.VMPowers(vm_name, VMPowers.S_START)
                    return ZMessage(
                        success=False, action="ISOMount",
                        message="ISO文件不存在")
                # 挂载到IDE控制器（如不存在则先创建）
                self._ensure_ide_controller(vm_name)
                ok, out, err = self._vboxmanage(
                    "storageattach", vm_name,
                    "--storagectl", "IDE Controller",
                    "--port", "0", "--device", "0",
                    "--type", "dvddrive",
                    "--medium", iso_full)
                if not ok:
                    self.VMPowers(vm_name, VMPowers.S_START)
                    return ZMessage(
                        success=False, action="ISOMount",
                        message=f"挂载ISO失败: {err}")
                self.vm_saving[vm_name].iso_all[vm_imgs.iso_name] = vm_imgs
            else:
                self._ensure_ide_controller(vm_name)
                self._vboxmanage(
                    "storageattach", vm_name,
                    "--storagectl", "IDE Controller",
                    "--port", "0", "--device", "0",
                    "--medium", "none")
                if vm_imgs.iso_name in self.vm_saving[vm_name].iso_all:
                    del self.vm_saving[vm_name].iso_all[vm_imgs.iso_name]

            self.data_set()
            self.VMPowers(vm_name, VMPowers.S_START)
            action_text = "挂载" if in_flag else "卸载"
            return ZMessage(
                success=True, action="ISOMount",
                message=f"ISO{action_text}成功")
        except Exception as e:
            logger.error(f"[VirtualBox] ISO操作失败: {e}")
            return ZMessage(success=False, action="ISOMount", message=str(e))

    # 确保IDE控制器存在 ========================================================
    def _ensure_ide_controller(self, vm_name: str):
        """确保虚拟机有IDE控制器"""
        ok, stdout, _ = self._vboxmanage(
            "showvminfo", vm_name, "--machinereadable")
        if ok and "IDE Controller" not in stdout:
            self._vboxmanage(
                "storagectl", vm_name,
                "--name", "IDE Controller",
                "--add", "ide")

    # 加载备份 =================================================================
    def LDBackup(self, vm_back: str = "") -> ZMessage:
        return super().LDBackup(vm_back)

    # 移除备份 =================================================================
    def RMBackup(self, vm_name: str, vm_back: str = "") -> ZMessage:
        return super().RMBackup(vm_name, vm_back)

    # 移除磁盘 =================================================================
    def RMMounts(self, vm_name: str, vm_imgs: str) -> ZMessage:
        return super().RMMounts(vm_name, vm_imgs)

    # 查找PCI设备 =============================================================
    def PCIShows(self) -> dict[str, VFConfig]:
        return {}

    # 查找USB设备 =============================================================
    def USBShows(self) -> dict[str, USBInfos]:
        try:
            ok, stdout, _ = self._vboxmanage("list", "usbhost")
            if not ok:
                return {}
            usb_dict = {}
            vid, pid, name = "", "", ""
            for line in stdout.splitlines():
                line = line.strip()
                if line.startswith("VendorId:"):
                    vid = line.split(":")[-1].strip().replace("0x", "")
                elif line.startswith("ProductId:"):
                    pid = line.split(":")[-1].strip().replace("0x", "")
                elif line.startswith("Product:"):
                    name = line.split(":", 1)[-1].strip()
                elif line == "" and vid and pid:
                    key = f"{vid}:{pid}"
                    usb_dict[key] = USBInfos(
                        vid_uuid=vid, pid_uuid=pid, usb_hint=name)
                    vid, pid, name = "", "", ""
            return usb_dict
        except Exception as e:
            logger.error(f"[VirtualBox] 获取USB设备失败: {e}")
            return {}

    # USB设备直通 ==============================================================
    def USBSetup(self, vm_name: str, ud_info, ud_keys: str,
                 in_flag=True) -> ZMessage:
        try:
            if vm_name not in self.vm_saving:
                return ZMessage(
                    success=False, action="USBSetup",
                    message="虚拟机不存在")
            vm_conf = self.vm_saving[vm_name]
            if in_flag:
                # 添加USB过滤器
                ok, out, err = self._vboxmanage(
                    "usbfilter", "add", "0",
                    "--target", vm_name,
                    "--name", ud_info.usb_hint or ud_keys,
                    "--vendorid", ud_info.vid_uuid,
                    "--productid", ud_info.pid_uuid)
                if ok:
                    vm_conf.usb_all[ud_keys] = ud_info
                    self.data_set()
                    return ZMessage(
                        success=True, action="USBSetup",
                        message="USB设备已添加")
                return ZMessage(
                    success=False, action="USBSetup",
                    message=f"添加USB失败: {err}")
            else:
                # 移除USB过滤器（找到对应索引）
                ok, out, err = self._vboxmanage(
                    "usbfilter", "remove", "0",
                    "--target", vm_name)
                if ok:
                    vm_conf.usb_all.pop(ud_keys, None)
                    self.data_set()
                    return ZMessage(
                        success=True, action="USBSetup",
                        message="USB设备已移除")
                return ZMessage(
                    success=False, action="USBSetup",
                    message=f"移除USB失败: {err}")
        except Exception as e:
            logger.error(f"[VirtualBox] USB操作失败: {e}")
            return ZMessage(success=False, action="USBSetup", message=str(e))
