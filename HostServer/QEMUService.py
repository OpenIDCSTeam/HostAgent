# QEMUServer - QEMU/KVM虚拟化平台管理 ##########################################
# 提供QEMU/KVM虚拟机的创建、管理和监控功能
# 依赖: pip install libvirt-python qemu-img（系统需安装qemu-kvm和libvirt）
# 支持本地和远程（通过libvirt+SSH）管理
################################################################################
import os
import re
import time
import base64
import shutil
import tempfile
import traceback
import subprocess
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
        self._conn = None       # libvirt连接对象（懒加载）
        self._use_libvirt = True  # 是否使用libvirt（否则降级为qemu命令行）

    # 获取libvirt连接 ==========================================================
    def _get_conn(self):
        """获取libvirt连接，懒加载"""
        if self._conn is not None:
            try:
                self._conn.getVersion()
                return self._conn
            except Exception:
                self._conn = None

        try:
            import libvirt
            addr = self.hs_config.server_addr or ""
            user = self.hs_config.server_user or "root"

            if addr in ["", "localhost", "127.0.0.1"]:
                uri = "qemu:///system"
            else:
                # 远程通过SSH连接
                uri = f"qemu+ssh://{user}@{addr}/system"

            self._conn = libvirt.open(uri)
            logger.info(f"[QEMU] libvirt连接成功: {uri}")
            return self._conn
        except ImportError:
            logger.warning("[QEMU] libvirt-python未安装，降级为命令行模式")
            self._use_libvirt = False
            return None
        except Exception as e:
            logger.warning(f"[QEMU] libvirt连接失败: {e}，降级为命令行模式")
            self._use_libvirt = False
            return None

    # 执行virsh命令（libvirt命令行工具）========================================
    def _virsh(self, *args, timeout: int = 60) -> tuple[bool, str, str]:
        """执行virsh命令"""
        try:
            addr = self.hs_config.server_addr or ""
            user = self.hs_config.server_user or "root"

            if addr in ["", "localhost", "127.0.0.1"]:
                cmd = ["virsh"] + list(args)
            else:
                cmd = ["virsh", "-c",
                       f"qemu+ssh://{user}@{addr}/system"] + list(args)

            logger.debug(f"[QEMU] virsh: {' '.join(cmd)}")
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout)
            return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
        except subprocess.TimeoutExpired:
            return False, "", f"命令超时({timeout}s)"
        except FileNotFoundError:
            return False, "", "virsh未找到，请安装libvirt-clients"
        except Exception as e:
            return False, "", str(e)

    # 执行qemu-img命令 =========================================================
    def _qemu_img(self, *args, timeout: int = 120) -> tuple[bool, str, str]:
        """执行qemu-img命令"""
        try:
            cmd = ["qemu-img"] + list(args)
            logger.debug(f"[QEMU] qemu-img: {' '.join(cmd)}")
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout)
            return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
        except FileNotFoundError:
            return False, "", "qemu-img未找到，请安装qemu-utils"
        except Exception as e:
            return False, "", str(e)

    # 获取虚拟机磁盘路径 =======================================================
    def _get_disk_path(self, vm_uuid: str, suffix: str = "") -> str:
        """获取虚拟机磁盘路径"""
        disk_dir = self.hs_config.system_path or "/var/lib/libvirt/images"
        name = f"{vm_uuid}{suffix}.qcow2"
        return os.path.join(disk_dir, name)

    # 生成libvirt XML定义 ======================================================
    def _build_domain_xml(self, vm_conf: VMConfig) -> str:
        """生成QEMU/KVM虚拟机的libvirt XML定义"""
        vm_uuid = vm_conf.vm_uuid
        cpu_num = vm_conf.cpu_num or 1
        mem_mb = vm_conf.mem_num or 512
        mem_kb = mem_mb * 1024
        disk_path = self._get_disk_path(vm_uuid)

        # 网络接口XML
        nic_xml = ""
        for nic_name, nic_conf in vm_conf.nic_all.items():
            bridge = self.hs_config.network_nat or "virbr0"
            mac = nic_conf.mac_addr or ""
            mac_xml = f'<mac address="{mac}"/>' if mac else ""
            nic_xml += f"""
        <interface type='bridge'>
          {mac_xml}
          <source bridge='{bridge}'/>
          <model type='virtio'/>
        </interface>"""

        # VNC端口（自动分配）
        vnc_port = -1  # -1表示自动分配

        xml = f"""<domain type='kvm'>
  <name>{vm_uuid}</name>
  <memory unit='KiB'>{mem_kb}</memory>
  <currentMemory unit='KiB'>{mem_kb}</currentMemory>
  <vcpu placement='static'>{cpu_num}</vcpu>
  <os>
    <type arch='x86_64' machine='pc-i440fx-latest'>hvm</type>
    <boot dev='hd'/>
    <boot dev='cdrom'/>
  </os>
  <features>
    <acpi/>
    <apic/>
  </features>
  <cpu mode='host-model'/>
  <clock offset='utc'/>
  <on_poweroff>destroy</on_poweroff>
  <on_reboot>restart</on_reboot>
  <on_crash>destroy</on_crash>
  <devices>
    <emulator>/usr/bin/qemu-system-x86_64</emulator>
    <disk type='file' device='disk'>
      <driver name='qemu' type='qcow2'/>
      <source file='{disk_path}'/>
      <target dev='vda' bus='virtio'/>
    </disk>
    <controller type='usb' model='ich9-ehci1'/>
    <controller type='virtio-serial'/>
    {nic_xml}
    <serial type='pty'>
      <target port='0'/>
    </serial>
    <console type='pty'>
      <target type='serial' port='0'/>
    </console>
    <graphics type='vnc' port='{vnc_port}' autoport='yes' listen='0.0.0.0'>
      <listen type='address' address='0.0.0.0'/>
    </graphics>
    <video>
      <model type='vga' vram='16384'/>
    </video>
    <memballoon model='virtio'/>
  </devices>
</domain>"""
        return xml

    # 宿主机任务 ===============================================================
    def Crontabs(self) -> bool:
        return super().Crontabs()

    # 宿主机状态 ===============================================================
    def HSStatus(self) -> HWStatus:
        addr = self.hs_config.server_addr or ""
        if addr in ["", "localhost", "127.0.0.1"]:
            # 本地：直接用父类 psutil 采集
            return super().HSStatus()
        # 远程：通过 SSH 执行命令获取宿主机状态
        try:
            hw = HWStatus()
            # CPU 核心数 =======================================================
            ok, stdout, _ = self._virsh("nodeinfo")
            if ok:
                for line in stdout.splitlines():
                    if "CPU(s):" in line:
                        try:
                            hw.cpu_total = int(line.split(":")[-1].strip())
                        except ValueError:
                            pass
                    elif "Memory size:" in line:
                        try:
                            val = line.split(":")[-1].strip()
                            hw.mem_total = int(
                                val.replace("KiB", "").strip()) // 1024
                        except ValueError:
                            pass
            # CPU 使用率（通过 SSH 执行 top 命令）==============================
            try:
                user = self.hs_config.server_user or "root"
                import subprocess
                result = subprocess.run(
                    ["ssh", "-o", "StrictHostKeyChecking=no",
                     "-o", "ConnectTimeout=5",
                     f"{user}@{addr}",
                     "top -bn1 | grep 'Cpu(s)' | awk '{print $2}'"],
                    capture_output=True, text=True, timeout=10)
                if result.returncode == 0 and result.stdout.strip():
                    hw.cpu_usage = int(float(result.stdout.strip()))
            except Exception:
                pass
            # 内存使用（通过 SSH 执行 free 命令）================================
            try:
                user = self.hs_config.server_user or "root"
                import subprocess
                result = subprocess.run(
                    ["ssh", "-o", "StrictHostKeyChecking=no",
                     "-o", "ConnectTimeout=5",
                     f"{user}@{addr}",
                     "free -m | awk 'NR==2{print $2,$3}'"],
                    capture_output=True, text=True, timeout=10)
                if result.returncode == 0 and result.stdout.strip():
                    parts = result.stdout.strip().split()
                    if len(parts) == 2:
                        hw.mem_total = int(parts[0])
                        hw.mem_usage = int(parts[1])
            except Exception:
                pass
            return hw
        except Exception as e:
            logger.error(f"[QEMU] 获取远程宿主机状态失败: {e}")
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
            ok, stdout, stderr = self._virsh("version")
            if not ok:
                return ZMessage(
                    success=False, action="HSLoader",
                    message=f"virsh不可用: {stderr}")
            logger.info(f"[QEMU] virsh版本: {stdout.splitlines()[0] if stdout else ''}")
            return super().HSLoader()
        except Exception as e:
            logger.error(f"[QEMU] 加载失败: {e}")
            return ZMessage(success=False, action="HSLoader", message=str(e))

    # 卸载宿主机 ===============================================================
    def HSUnload(self) -> ZMessage:
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
        return super().HSUnload()

    # 虚拟机状态 ===============================================================
    def VMStatus(self, vm_name: str = "",
                 s_t: int = None, e_t: int = None) -> dict[str, list[HWStatus]]:
        return super().VMStatus(vm_name, s_t, e_t)

    # 虚拟机扫描 ===============================================================
    def VMDetect(self) -> ZMessage:
        try:
            filter_prefix = self.hs_config.filter_name or ""
            ok, stdout, stderr = self._virsh("list", "--all", "--name")
            if not ok:
                return ZMessage(
                    success=False, action="VMDetect",
                    message=f"获取虚拟机列表失败: {stderr}")

            scanned_count = 0
            added_count = 0
            for line in stdout.splitlines():
                vm_name = line.strip()
                if not vm_name:
                    continue
                if filter_prefix and not vm_name.startswith(filter_prefix):
                    continue
                scanned_count += 1
                if vm_name in self.vm_saving:
                    continue
                new_conf = VMConfig()
                new_conf.vm_uuid = vm_name
                self.vm_saving[vm_name] = new_conf
                added_count += 1
                self.push_log(ZMessage(
                    success=True, action="VMDetect",
                    message=f"发现虚拟机: {vm_name}"))

            if added_count > 0:
                self.data_set()

            return ZMessage(
                success=True, action="VMDetect",
                message=f"扫描完成，共{scanned_count}台，新增{added_count}台",
                results={"scanned": scanned_count, "added": added_count})
        except Exception as e:
            logger.error(f"[QEMU] 扫描虚拟机失败: {e}")
            traceback.print_exc()
            return ZMessage(success=False, action="VMDetect", message=str(e))

    # 创建虚拟机 ===============================================================
    def VMCreate(self, vm_conf: VMConfig) -> ZMessage:
        try:
            logger.info(f"[QEMU] 开始创建虚拟机: {vm_conf.vm_uuid}")

            # 网络检查 =========================================================
            vm_conf, net_result = self.NetCheck(vm_conf)
            if not net_result.success:
                return net_result
            self.IPBinder(vm_conf, True)

            disk_path = self._get_disk_path(vm_conf.vm_uuid)
            disk_dir = os.path.dirname(disk_path)
            os.makedirs(disk_dir, exist_ok=True)

            # 创建系统磁盘 =====================================================
            if vm_conf.os_name:
                im_file = os.path.join(
                    self.hs_config.images_path or "", vm_conf.os_name)
                if os.path.exists(im_file):
                    # 基于镜像创建差量磁盘
                    ok, out, err = self._qemu_img(
                        "create", "-f", "qcow2",
                        "-b", im_file, "-F", "qcow2",
                        disk_path)
                    if not ok:
                        # 降级：直接复制
                        ok, out, err = self._qemu_img(
                            "convert", "-f", "qcow2", "-O", "qcow2",
                            im_file, disk_path)
                else:
                    ok, out, err = self._qemu_img(
                        "create", "-f", "qcow2", disk_path,
                        f"{vm_conf.hdd_num or 20}G")
            else:
                ok, out, err = self._qemu_img(
                    "create", "-f", "qcow2", disk_path,
                    f"{vm_conf.hdd_num or 20}G")

            if not ok:
                raise Exception(f"创建磁盘失败: {err}")

            # 生成并定义虚拟机（写临时文件后通过virsh define导入）=================
            xml = self._build_domain_xml(vm_conf)
            tmp_xml = tempfile.mktemp(suffix=".xml")
            try:
                with open(tmp_xml, "w", encoding="utf-8") as f:
                    f.write(xml)
                ok, out, err = self._virsh("define", tmp_xml)
            finally:
                if os.path.exists(tmp_xml):
                    os.remove(tmp_xml)

            if not ok:
                raise Exception(f"定义虚拟机失败: {err}")

            # 启动虚拟机 =======================================================
            self.VMPowers(vm_conf.vm_uuid, VMPowers.S_START)

            if not vm_conf.efi_all:
                vm_conf.efi_all = self.efi_build(vm_conf)

            return super().VMCreate(vm_conf)

        except Exception as e:
            logger.error(f"[QEMU] 创建虚拟机失败: {e}")
            traceback.print_exc()
            # 清理
            try:
                self._virsh("undefine", vm_conf.vm_uuid, "--remove-all-storage")
            except Exception:
                pass
            disk_path = self._get_disk_path(vm_conf.vm_uuid)
            if os.path.exists(disk_path):
                os.remove(disk_path)
            hs_result = ZMessage(
                success=False, action="VMCreate",
                message=f"虚拟机创建失败: {str(e)}")
            self.logs_set(hs_result)
            return hs_result

    # 安装虚拟机（重装系统）====================================================
    def VMSetups(self, vm_conf: VMConfig) -> ZMessage:
        """重装系统：删除旧磁盘，重新创建"""
        try:
            logger.info(f"[QEMU] 重装系统: {vm_conf.vm_uuid}")
            disk_path = self._get_disk_path(vm_conf.vm_uuid)

            # 停止虚拟机 =======================================================
            self._virsh("destroy", vm_conf.vm_uuid)
            time.sleep(2)

            # 删除旧磁盘 =======================================================
            if os.path.exists(disk_path):
                os.remove(disk_path)

            # 重新创建磁盘 =====================================================
            if vm_conf.os_name:
                im_file = os.path.join(
                    self.hs_config.images_path or "", vm_conf.os_name)
                if os.path.exists(im_file):
                    ok, out, err = self._qemu_img(
                        "create", "-f", "qcow2",
                        "-b", im_file, "-F", "qcow2", disk_path)
                else:
                    ok, out, err = self._qemu_img(
                        "create", "-f", "qcow2", disk_path,
                        f"{vm_conf.hdd_num or 20}G")
            else:
                ok, out, err = self._qemu_img(
                    "create", "-f", "qcow2", disk_path,
                    f"{vm_conf.hdd_num or 20}G")

            if not ok:
                return ZMessage(
                    success=False, action="VMSetups",
                    message=f"创建磁盘失败: {err}")

            # 重新启动 =========================================================
            self._virsh("start", vm_conf.vm_uuid)
            return ZMessage(success=True, action="VMSetups", message="系统重装成功")
        except Exception as e:
            logger.error(f"[QEMU] 重装系统失败: {e}")
            return ZMessage(success=False, action="VMSetups", message=str(e))

    # 配置虚拟机 ===============================================================
    def VMUpdate(self, vm_conf: VMConfig, vm_last: VMConfig) -> ZMessage:
        try:
            logger.info(f"[QEMU] 更新虚拟机配置: {vm_conf.vm_uuid}")

            # 网络检查 =========================================================
            vm_conf, net_result = self.NetCheck(vm_conf)
            if not net_result.success:
                return net_result
            self.IPUpdate(vm_conf, vm_last)

            # 停止虚拟机 =======================================================
            self._virsh("destroy", vm_conf.vm_uuid)
            time.sleep(2)

            # 重装系统 =========================================================
            if vm_conf.os_name != vm_last.os_name and vm_last.os_name:
                self.VMSetups(vm_conf)

            # 扩展磁盘 =========================================================
            if vm_conf.hdd_num > vm_last.hdd_num:
                disk_path = self._get_disk_path(vm_conf.vm_uuid)
                self._qemu_img(
                    "resize", disk_path, f"{vm_conf.hdd_num}G")

            # 重新生成XML并更新定义 ============================================
            xml = self._build_domain_xml(vm_conf)
            tmp_xml = tempfile.mktemp(suffix=".xml")
            try:
                with open(tmp_xml, "w", encoding="utf-8") as f:
                    f.write(xml)
                self._virsh("define", tmp_xml)
            finally:
                if os.path.exists(tmp_xml):
                    os.remove(tmp_xml)

            # 重新启动 =========================================================
            self._virsh("start", vm_conf.vm_uuid)
            # super().VMUpdate 会将 vm_conf 保存到 vm_saving
            return super().VMUpdate(vm_conf, vm_last)
        except Exception as e:
            logger.error(f"[QEMU] 更新虚拟机失败: {e}")
            traceback.print_exc()
            return ZMessage(success=False, action="VMUpdate", message=str(e))

    # 删除虚拟机 ===============================================================
    def VMDelete(self, vm_name: str, rm_back=True) -> ZMessage:
        try:
            logger.info(f"[QEMU] 删除虚拟机: {vm_name}")
            if vm_name not in self.vm_saving:
                return ZMessage(
                    success=False, action="VMDelete",
                    message=f"虚拟机 {vm_name} 不存在")

            vm_conf = self.vm_saving[vm_name]

            # 停止 =============================================================
            self._virsh("destroy", vm_name)
            time.sleep(2)

            # 解绑IP ===========================================================
            self.IPBinder(vm_conf, False)

            # 注销并删除存储 ===================================================
            ok, out, err = self._virsh(
                "undefine", vm_name, "--remove-all-storage")
            if not ok:
                # 尝试不删除存储
                self._virsh("undefine", vm_name)
                # 手动删除磁盘
                disk_path = self._get_disk_path(vm_name)
                if os.path.exists(disk_path):
                    os.remove(disk_path)

            return super().VMDelete(vm_name, rm_back)
        except Exception as e:
            logger.error(f"[QEMU] 删除虚拟机失败: {e}")
            traceback.print_exc()
            return ZMessage(success=False, action="VMDelete", message=str(e))

    # 虚拟机电源 ===============================================================
    def VMPowers(self, vm_name: str, power: VMPowers) -> ZMessage:
        try:
            parent_result = super().VMPowers(vm_name, power)
            original_flag = (parent_result.results.get("original_flag")
                             if parent_result.results else None)

            virsh_map = {
                VMPowers.S_START: ("start", vm_name),
                VMPowers.S_CLOSE: ("shutdown", vm_name),
                VMPowers.H_CLOSE: ("destroy", vm_name),
                VMPowers.S_RESET: ("reboot", vm_name),
                VMPowers.H_RESET: ("reset", vm_name),
                VMPowers.A_PAUSE: ("suspend", vm_name),
                VMPowers.A_WAKED: ("resume", vm_name),
            }

            msg_map = {
                VMPowers.S_START: ("启动成功", "启动失败"),
                VMPowers.S_CLOSE: ("正在软关机", "关机失败"),
                VMPowers.H_CLOSE: ("强制关机成功", "强制关机失败"),
                VMPowers.S_RESET: ("重启成功", "重启失败"),
                VMPowers.H_RESET: ("强制重启成功", "强制重启失败"),
                VMPowers.A_PAUSE: ("暂停成功", "暂停失败"),
                VMPowers.A_WAKED: ("恢复成功", "恢复失败"),
            }

            if power in virsh_map:
                cmd, arg = virsh_map[power]
                ok, out, err = self._virsh(cmd, arg)
                succ_msg, fail_msg = msg_map[power]
                hs_result = ZMessage(
                    success=ok, action="VMPowers",
                    message=succ_msg if ok else f"{fail_msg}: {err or out}")
                if ok and power == VMPowers.S_CLOSE:
                    self.soft_pwr(vm_name, VMPowers.S_CLOSE, VMPowers.ON_STOP)
                elif ok and power == VMPowers.S_RESET:
                    self.soft_pwr(vm_name, VMPowers.S_RESET, VMPowers.ON_STOP)
            else:
                hs_result = ZMessage(
                    success=False, action="VMPowers",
                    message=f"不支持的电源操作: {power}")

            if not hs_result.success and original_flag is not None:
                self.vm_saving[vm_name].vm_flag = original_flag
                self.data_set()
            elif hs_result.success and power not in [
                    VMPowers.S_CLOSE, VMPowers.S_RESET]:
                import threading
                def delayed_refresh():
                    time.sleep(3)
                    self.vm_loads(vm_name)
                threading.Thread(target=delayed_refresh, daemon=True).start()

            self.logs_set(hs_result)
            return hs_result
        except Exception as e:
            logger.error(f"[QEMU] 电源操作失败: {e}")
            traceback.print_exc()
            return ZMessage(success=False, action="VMPowers", message=str(e))

    # 获取虚拟机实际状态 =======================================================
    def GetPower(self, vm_name: str) -> str:
        """通过virsh domstate获取虚拟机状态"""
        try:
            ok, stdout, _ = self._virsh("domstate", vm_name)
            if ok:
                state = stdout.strip().lower()
                state_map = {
                    "running": "运行中",
                    "paused": "已暂停",
                    "shut off": "已关机",
                    "crashed": "已崩溃",
                    "pmsuspended": "已挂起",
                    "idle": "空闲",
                    "in shutdown": "关机中",
                }
                return state_map.get(state, "未知")
            return "未知"
        except Exception as e:
            logger.warning(f"[QEMU] 获取虚拟机状态失败: {e}")
            return "未知"

    # 虚拟机截图 ===============================================================
    def VMScreen(self, vm_name: str = "") -> str:
        """通过virsh screenshot截取虚拟机屏幕"""
        try:
            tmp_file = tempfile.mktemp(suffix=".ppm")
            ok, out, err = self._virsh(
                "screenshot", vm_name, tmp_file, timeout=15)
            if ok and os.path.exists(tmp_file):
                # 转换PPM为PNG
                png_file = tmp_file.replace(".ppm", ".png")
                try:
                    from PIL import Image
                    img = Image.open(tmp_file)
                    img.save(png_file, "PNG")
                    os.remove(tmp_file)
                    with open(png_file, "rb") as f:
                        data = f.read()
                    os.remove(png_file)
                    return "data:image/png;base64," + base64.b64encode(data).decode()
                except ImportError:
                    # 没有PIL，直接返回PPM的base64
                    with open(tmp_file, "rb") as f:
                        data = f.read()
                    os.remove(tmp_file)
                    return "data:image/x-portable-pixmap;base64," + base64.b64encode(data).decode()
            return ""
        except Exception as e:
            logger.warning(f"[QEMU] 截图失败: {e}")
            return ""

    # 修改密码（通过qemu-guest-agent）=========================================
    def VMPasswd(self, vm_name: str, os_pass: str) -> ZMessage:
        """通过virsh set-user-password修改虚拟机密码（需要qemu-guest-agent）"""
        try:
            if vm_name not in self.vm_saving:
                return ZMessage(
                    success=False, action="VMPasswd",
                    message="虚拟机不存在")
            vm_conf = self.vm_saving[vm_name]
            os_user = vm_conf.os_user or "root"

            ok, out, err = self._virsh(
                "set-user-password", vm_name, os_user, os_pass,
                timeout=30)
            if ok:
                vm_conf.os_pass = os_pass
                self.data_set()
                return ZMessage(
                    success=True, action="VMPasswd",
                    message="密码修改成功")
            return ZMessage(
                success=False, action="VMPasswd",
                message=f"密码修改失败（需要qemu-guest-agent）: {err or out}")
        except Exception as e:
            logger.error(f"[QEMU] 修改密码失败: {e}")
            return ZMessage(success=False, action="VMPasswd", message=str(e))

    # VNC获取 ==================================================================
    def VNCGets(self, vm_name: str) -> ZMessage:
        """获取VNC连接信息"""
        try:
            if vm_name not in self.vm_saving:
                return ZMessage(
                    success=False, action="VNCGets",
                    message="虚拟机不存在")

            ok, stdout, _ = self._virsh("vncdisplay", vm_name)
            if ok and stdout:
                # 格式: :0 或 127.0.0.1:0
                display = stdout.strip()
                if ":" in display:
                    parts = display.rsplit(":", 1)
                    display_num = int(parts[-1])
                    vnc_port = 5900 + display_num
                else:
                    vnc_port = 5900
            else:
                # 从domxml解析VNC端口
                ok2, xml_out, _ = self._virsh("dumpxml", vm_name)
                vnc_port = 5900
                if ok2:
                    match = re.search(r"port='(\d+)'", xml_out)
                    if match:
                        vnc_port = int(match.group(1))

            host = self.hs_config.server_addr or "localhost"
            if host in ["", "localhost", "127.0.0.1"]:
                host = "localhost"

            return ZMessage(
                success=True, action="VNCGets",
                message="VNC信息获取成功",
                results={
                    "host": host,
                    "port": vnc_port,
                    "type": "vnc"
                })
        except Exception as e:
            logger.error(f"[QEMU] 获取VNC信息失败: {e}")
            return ZMessage(success=False, action="VNCGets", message=str(e))

    # 备份虚拟机（快照+导出）==================================================
    def VMBackup(self, vm_name: str, vm_tips: str) -> ZMessage:
        try:
            if vm_name not in self.vm_saving:
                return ZMessage(
                    success=False, action="VMBackup",
                    message="虚拟机不存在")

            backup_dir = self.hs_config.backup_path or "./DataSaving/backups"
            os.makedirs(backup_dir, exist_ok=True)

            import datetime
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = os.path.join(
                backup_dir, f"{vm_name}_{ts}.qcow2")

            disk_path = self._get_disk_path(vm_name)
            if not os.path.exists(disk_path):
                return ZMessage(
                    success=False, action="VMBackup",
                    message="虚拟机磁盘文件不存在")

            # 使用qemu-img转换（压缩备份）
            ok, out, err = self._qemu_img(
                "convert", "-f", "qcow2", "-O", "qcow2",
                "-c", disk_path, backup_file, timeout=600)
            if ok:
                hs_result = ZMessage(
                    success=True, action="VMBackup",
                    message=f"备份成功: {backup_file}",
                    results={"backup_file": backup_file})
                self.logs_set(hs_result)
                return hs_result
            return ZMessage(
                success=False, action="VMBackup",
                message=f"备份失败: {err}")
        except Exception as e:
            logger.error(f"[QEMU] 备份失败: {e}")
            return ZMessage(success=False, action="VMBackup", message=str(e))

    # 恢复虚拟机 ===============================================================
    def Restores(self, vm_name: str, vm_back: str) -> ZMessage:
        try:
            backup_dir = self.hs_config.backup_path or "./DataSaving/backups"
            backup_file = os.path.join(backup_dir, vm_back)
            if not os.path.exists(backup_file):
                return ZMessage(
                    success=False, action="Restores",
                    message=f"备份文件不存在: {vm_back}")

            disk_path = self._get_disk_path(vm_name)
            # 停止虚拟机
            self._virsh("destroy", vm_name)
            time.sleep(2)

            # 恢复磁盘
            ok, out, err = self._qemu_img(
                "convert", "-f", "qcow2", "-O", "qcow2",
                backup_file, disk_path, timeout=600)
            if ok:
                self._virsh("start", vm_name)
                hs_result = ZMessage(
                    success=True, action="Restores",
                    message="恢复成功")
                self.logs_set(hs_result)
                return hs_result
            return ZMessage(
                success=False, action="Restores",
                message=f"恢复失败: {err}")
        except Exception as e:
            logger.error(f"[QEMU] 恢复失败: {e}")
            return ZMessage(success=False, action="Restores", message=str(e))

    # 硬盘挂载 =================================================================
    def HDDMount(self, vm_name: str, vm_imgs: SDConfig, in_flag=True) -> ZMessage:
        try:
            if vm_name not in self.vm_saving:
                return ZMessage(
                    success=False, action="HDDMount",
                    message="虚拟机不存在")

            disk_path = self._get_disk_path(
                vm_name, f"-{vm_imgs.hdd_name}")

            if in_flag:
                # 创建新磁盘
                if not os.path.exists(disk_path):
                    ok, out, err = self._qemu_img(
                        "create", "-f", "qcow2", disk_path,
                        f"{vm_imgs.hdd_size or 20}G")
                    if not ok:
                        return ZMessage(
                            success=False, action="HDDMount",
                            message=f"创建磁盘失败: {err}")

                # 热插拔磁盘（virsh attach-disk）
                ok, out, err = self._virsh(
                    "attach-disk", vm_name, disk_path,
                    "vdb", "--driver", "qemu",
                    "--subdriver", "qcow2",
                    "--persistent")
                if not ok:
                    return ZMessage(
                        success=False, action="HDDMount",
                        message=f"挂载磁盘失败: {err or out}")
                vm_imgs.hdd_flag = 1
                self.vm_saving[vm_name].hdd_all[vm_imgs.hdd_name] = vm_imgs
            else:
                # 卸载磁盘
                ok, out, err = self._virsh(
                    "detach-disk", vm_name, "vdb", "--persistent")
                if vm_imgs.hdd_name in self.vm_saving[vm_name].hdd_all:
                    self.vm_saving[vm_name].hdd_all[vm_imgs.hdd_name].hdd_flag = 0

            self.data_set()
            action_text = "挂载" if in_flag else "卸载"
            return ZMessage(
                success=True, action="HDDMount",
                message=f"磁盘{action_text}成功")
        except Exception as e:
            logger.error(f"[QEMU] 磁盘操作失败: {e}")
            return ZMessage(success=False, action="HDDMount", message=str(e))

    # ISO镜像挂载 ==============================================================
    def ISOMount(self, vm_name: str, vm_imgs: IMConfig, in_flag=True) -> ZMessage:
        try:
            if vm_name not in self.vm_saving:
                return ZMessage(
                    success=False, action="ISOMount",
                    message="虚拟机不存在")

            if in_flag:
                iso_full = os.path.join(
                    self.hs_config.dvdrom_path or "", vm_imgs.iso_file)
                if not os.path.exists(iso_full):
                    return ZMessage(
                        success=False, action="ISOMount",
                        message="ISO文件不存在")
                ok, out, err = self._virsh(
                    "attach-disk", vm_name, iso_full,
                    "hdc", "--type", "cdrom",
                    "--mode", "readonly", "--persistent")
                if not ok:
                    return ZMessage(
                        success=False, action="ISOMount",
                        message=f"挂载ISO失败: {err or out}")
                self.vm_saving[vm_name].iso_all[vm_imgs.iso_name] = vm_imgs
            else:
                ok, out, err = self._virsh(
                    "detach-disk", vm_name, "hdc", "--persistent")
                if vm_imgs.iso_name in self.vm_saving[vm_name].iso_all:
                    del self.vm_saving[vm_name].iso_all[vm_imgs.iso_name]

            self.data_set()
            action_text = "挂载" if in_flag else "卸载"
            return ZMessage(
                success=True, action="ISOMount",
                message=f"ISO{action_text}成功")
        except Exception as e:
            logger.error(f"[QEMU] ISO操作失败: {e}")
            return ZMessage(success=False, action="ISOMount", message=str(e))

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
        """通过virsh nodedev-list获取PCI设备"""
        try:
            ok, stdout, _ = self._virsh("nodedev-list", "--cap", "pci")
            if not ok:
                return {}
            pci_dict = {}
            for line in stdout.splitlines():
                dev = line.strip()
                if not dev:
                    continue
                ok2, info, _ = self._virsh("nodedev-dumpxml", dev)
                if ok2:
                    # 解析PCI信息
                    product_match = re.search(
                        r"<product id='([^']+)'>([^<]*)</product>", info)
                    vendor_match = re.search(
                        r"<vendor id='([^']+)'>([^<]*)</vendor>", info)
                    if product_match and vendor_match:
                        pci_id = dev
                        pci_dict[pci_id] = VFConfig(
                            pci_uuid=pci_id,
                            pci_name=f"{vendor_match.group(2)} {product_match.group(2)}")
            return pci_dict
        except Exception as e:
            logger.error(f"[QEMU] 获取PCI设备失败: {e}")
            return {}

    # 查找USB设备 =============================================================
    def USBShows(self) -> dict[str, USBInfos]:
        """通过virsh nodedev-list获取USB设备"""
        try:
            ok, stdout, _ = self._virsh("nodedev-list", "--cap", "usb_device")
            if not ok:
                return {}
            usb_dict = {}
            for line in stdout.splitlines():
                dev = line.strip()
                if not dev:
                    continue
                ok2, info, _ = self._virsh("nodedev-dumpxml", dev)
                if ok2:
                    vid_match = re.search(r"<vendor id='0x([0-9a-fA-F]+)'", info)
                    pid_match = re.search(r"<product id='0x([0-9a-fA-F]+)'", info)
                    name_match = re.search(r"<product[^>]*>([^<]+)</product>", info)
                    if vid_match and pid_match:
                        vid = vid_match.group(1)
                        pid = pid_match.group(1)
                        key = f"{vid}:{pid}"
                        usb_dict[key] = USBInfos(
                            vid_uuid=vid, pid_uuid=pid,
                            usb_hint=name_match.group(1) if name_match else key)
            return usb_dict
        except Exception as e:
            logger.error(f"[QEMU] 获取USB设备失败: {e}")
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
                # 生成USB设备XML
                usb_xml = f"""<hostdev mode='subsystem' type='usb' managed='yes'>
  <source>
    <vendor id='0x{ud_info.vid_uuid}'/>
    <product id='0x{ud_info.pid_uuid}'/>
  </source>
</hostdev>"""
                tmp_xml = tempfile.mktemp(suffix=".xml")
                try:
                    with open(tmp_xml, "w") as f:
                        f.write(usb_xml)
                    ok, out, err = self._virsh(
                        "attach-device", vm_name, tmp_xml, "--persistent")
                finally:
                    if os.path.exists(tmp_xml):
                        os.remove(tmp_xml)
                if ok:
                    vm_conf.usb_all[ud_keys] = ud_info
                    self.data_set()
                    return ZMessage(
                        success=True, action="USBSetup",
                        message="USB设备已添加")
                return ZMessage(
                    success=False, action="USBSetup",
                    message=f"添加USB失败: {err or out}")
            else:
                usb_xml = f"""<hostdev mode='subsystem' type='usb' managed='yes'>
  <source>
    <vendor id='0x{ud_info.vid_uuid}'/>
    <product id='0x{ud_info.pid_uuid}'/>
  </source>
</hostdev>"""
                tmp_xml = tempfile.mktemp(suffix=".xml")
                try:
                    with open(tmp_xml, "w") as f:
                        f.write(usb_xml)
                    ok, out, err = self._virsh(
                        "detach-device", vm_name, tmp_xml, "--persistent")
                finally:
                    if os.path.exists(tmp_xml):
                        os.remove(tmp_xml)
                if ok:
                    vm_conf.usb_all.pop(ud_keys, None)
                    self.data_set()
                    return ZMessage(
                        success=True, action="USBSetup",
                        message="USB设备已移除")
                return ZMessage(
                    success=False, action="USBSetup",
                    message=f"移除USB失败: {err or out}")
        except Exception as e:
            logger.error(f"[QEMU] USB操作失败: {e}")
            return ZMessage(success=False, action="USBSetup", message=str(e))
