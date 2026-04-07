# MemuAndroid - 逍遥安卓模拟器管理 #############################################
# 提供MEmu Game Emulator虚拟机的创建、管理和监控功能
# 依赖: memuc命令行工具（随逍遥模拟器安装）
# 参考: https://www.xyaz.cn/blog/20240116-231686.html
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
        # memuc可执行文件路径（从launch_path配置）
        self._memuc_path = None

    # 获取memuc路径 ============================================================
    def _get_memuc(self) -> str:
        """获取memuc可执行文件路径"""
        if self._memuc_path:
            return self._memuc_path
        launch = self.hs_config.launch_path or ""
        if os.path.isdir(launch):
            candidate = os.path.join(launch, "memuc.exe")
            if os.path.exists(candidate):
                self._memuc_path = candidate
                return self._memuc_path
        elif os.path.isfile(launch):
            self._memuc_path = launch
            return self._memuc_path
        # 尝试系统PATH
        self._memuc_path = "memuc"
        return self._memuc_path

    # 执行memuc命令 ============================================================
    def _memuc(self, *args, timeout: int = 60) -> tuple[bool, str, str]:
        """
        执行memuc命令行工具
        :return: (success, stdout, stderr)
        """
        try:
            memuc = self._get_memuc()
            cmd = [memuc] + list(args)
            logger.debug(f"[MEmu] 执行命令: {' '.join(cmd)}")

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
                timeout=timeout, encoding="utf-8", errors="replace", **kwargs)
            stdout = result.stdout.strip()
            stderr = result.stderr.strip()
            success = result.returncode == 0 and "ERROR" not in stdout.upper()
            return success, stdout, stderr
        except subprocess.TimeoutExpired:
            return False, "", f"命令超时({timeout}s)"
        except FileNotFoundError:
            return False, "", "memuc未找到，请检查launch_path配置"
        except Exception as e:
            return False, "", str(e)

    # 执行ADB命令（通过memuc adb）===============================================
    def _adb(self, vm_index: str, *args, timeout: int = 30) -> tuple[bool, str, str]:
        """通过memuc adb执行ADB命令，vm_index为纯数字索引"""
        return self._memuc("adb", "-i", str(vm_index), "--", *args, timeout=timeout)

    # 从vm_uuid提取纯数字索引 ==================================================
    @staticmethod
    def _extract_index(vm_uuid: str) -> str:
        """
        从vm_uuid（格式: memu_N 或纯数字N）中提取纯数字索引
        供memuc命令行使用
        """
        if vm_uuid.startswith("memu_"):
            return vm_uuid[5:]  # 去掉 'memu_' 前缀
        return vm_uuid

    # 获取模拟器索引 ============================================================
    def _get_vm_index(self, vm_name: str) -> str | None:
        """根据vm_name获取模拟器的纯数字索引（供memuc命令使用）"""
        if vm_name not in self.vm_saving:
            return None
        return self._extract_index(self.vm_saving[vm_name].vm_uuid)

    # 解析listvms输出 ===========================================================
    def _parse_listvms(self, stdout: str) -> list[dict]:
        """
        解析 memuc listvms 输出
        格式: index,title,top-level window handle,attach window handle,pid,disk usage
        """
        vms = []
        for line in stdout.splitlines():
            line = line.strip()
            if not line or line.startswith("index"):
                continue
            parts = line.split(",")
            if len(parts) >= 2:
                try:
                    vms.append({
                        "index": parts[0].strip(),
                        "title": parts[1].strip() if len(parts) > 1 else "",
                        "pid": parts[4].strip() if len(parts) > 4 else "0",
                        "disk": parts[5].strip() if len(parts) > 5 else "0",
                    })
                except (IndexError, ValueError):
                    pass
        return vms

    # 宿主机任务 ===============================================================
    def Crontabs(self) -> bool:
        return super().Crontabs()

    # 宿主机状态 ===============================================================
    def HSStatus(self) -> HWStatus:
        # 调用父类获取本地 psutil 数据
        hw = super().HSStatus()
        return hw

    # 初始宿主机 ===============================================================
    def HSCreate(self) -> ZMessage:
        return super().HSCreate()

    # 还原宿主机 ===============================================================
    def HSDelete(self) -> ZMessage:
        return super().HSDelete()

    # 读取宿主机 ===============================================================
    def HSLoader(self) -> ZMessage:
        try:
            ok, stdout, stderr = self._memuc("version")
            if not ok and "memuc未找到" in stderr:
                return ZMessage(
                    success=False, action="HSLoader",
                    message=f"memuc不可用: {stderr}")
            logger.info(f"[MEmu] memuc版本: {stdout}")
            return super().HSLoader()
        except Exception as e:
            logger.error(f"[MEmu] 加载失败: {e}")
            return ZMessage(success=False, action="HSLoader", message=str(e))

    # 卸载宿主机 ===============================================================
    def HSUnload(self) -> ZMessage:
        self._memuc_path = None
        return super().HSUnload()

    # 虚拟机状态 ===============================================================
    def VMStatus(self, vm_name: str = "",
                 s_t: int = None, e_t: int = None) -> dict[str, list[HWStatus]]:
        return super().VMStatus(vm_name, s_t, e_t)

    # 虚拟机扫描 ===============================================================
    def VMDetect(self) -> ZMessage:
        try:
            filter_prefix = self.hs_config.filter_name or ""
            ok, stdout, stderr = self._memuc("listvms")
            if not ok:
                return ZMessage(
                    success=False, action="VMDetect",
                    message=f"获取模拟器列表失败: {stderr or stdout}")

            vms = self._parse_listvms(stdout)
            scanned_count = len(vms)
            added_count = 0

            for vm in vms:
                title = vm["title"]
                index = vm["index"]
                # 使用title作为显示名，index作为vm_uuid
                vm_key = f"memu_{index}"
                if filter_prefix and not title.startswith(filter_prefix):
                    continue
                if vm_key in self.vm_saving:
                    continue
                new_conf = VMConfig()
                new_conf.vm_uuid = vm_key   # 使用 memu_N 格式，与 vm_saving 键一致
                new_conf.vm_name = title
                self.vm_saving[vm_key] = new_conf
                added_count += 1
                self.push_log(ZMessage(
                    success=True, action="VMDetect",
                    message=f"发现模拟器: {title} (索引:{index})"))

            if added_count > 0:
                self.data_set()

            return ZMessage(
                success=True, action="VMDetect",
                message=f"扫描完成，共{scanned_count}台，新增{added_count}台",
                results={"scanned": scanned_count, "added": added_count})
        except Exception as e:
            logger.error(f"[MEmu] 扫描模拟器失败: {e}")
            traceback.print_exc()
            return ZMessage(success=False, action="VMDetect", message=str(e))

    # 创建虚拟机 ===============================================================
    def VMCreate(self, vm_conf: VMConfig) -> ZMessage:
        try:
            logger.info(f"[MEmu] 开始创建模拟器: {vm_conf.vm_uuid}")

            # 网络检查 =========================================================
            vm_conf, net_result = self.NetCheck(vm_conf)
            if not net_result.success:
                return net_result
            self.IPBinder(vm_conf, True)

            # 确定安卓版本（从os_name解析，默认71=Android7.1）
            android_ver = "71"
            if vm_conf.os_name:
                ver_map = {
                    "android4.4": "44", "android5.1": "51",
                    "android7.1": "71", "android7.1_64": "76",
                    "44": "44", "51": "51", "71": "71", "76": "76"
                }
                android_ver = ver_map.get(
                    vm_conf.os_name.lower().replace(" ", ""), "71")

            # 创建模拟器实例 ===================================================
            ok, stdout, stderr = self._memuc("create", android_ver)
            if not ok:
                raise Exception(f"创建模拟器失败: {stderr or stdout}")

            # 解析新建的索引（memuc create 返回新实例索引）
            new_index = stdout.strip()
            if not new_index.isdigit():
                # 重新获取列表找到最新的
                ok2, out2, _ = self._memuc("listvms")
                if ok2:
                    vms = self._parse_listvms(out2)
                    if vms:
                        new_index = vms[-1]["index"]
                    else:
                        raise Exception("无法获取新建模拟器索引")
                else:
                    raise Exception("无法获取新建模拟器索引")

            # 使用 memu_N 格式作为统一的vm_uuid和存储键
            vm_key = f"memu_{new_index}"
            vm_conf.vm_uuid = vm_key

            # 配置CPU和内存 ====================================================
            if vm_conf.cpu_num:
                self._memuc("setconfigex", "-i", new_index,
                            "cpus", str(vm_conf.cpu_num))
            if vm_conf.mem_num:
                self._memuc("setconfigex", "-i", new_index,
                            "memory", str(vm_conf.mem_num))

            # 配置扩展参数（从extend_data读取）=================================
            extend = self.hs_config.extend_data or {}
            if "graphics_render_mode" in extend:
                self._memuc("setconfigex", "-i", new_index,
                            "graphics_render_mode",
                            str(extend["graphics_render_mode"]))
            if "enable_su" in extend:
                self._memuc("setconfigex", "-i", new_index,
                            "enable_su", str(extend["enable_su"]))
            if "fps" in extend:
                self._memuc("setconfigex", "-i", new_index,
                            "fps", str(extend["fps"]))

            # 重命名模拟器 =====================================================
            if vm_conf.vm_name:
                self._memuc("rename", "-i", new_index, vm_conf.vm_name)

            # 启动模拟器 =======================================================
            self._memuc("start", "-i", new_index, "-b")

            # 保存配置（super().VMCreate 会用 vm_conf.vm_uuid 作为键存入 vm_saving）
            if not vm_conf.efi_all:
                vm_conf.efi_all = self.efi_build(vm_conf)

            return super().VMCreate(vm_conf)

        except Exception as e:
            logger.error(f"[MEmu] 创建模拟器失败: {e}")
            traceback.print_exc()
            hs_result = ZMessage(
                success=False, action="VMCreate",
                message=f"模拟器创建失败: {str(e)}")
            self.logs_set(hs_result)
            return hs_result

    # 安装虚拟机（重装系统）====================================================
    def VMSetups(self, vm_conf: VMConfig) -> ZMessage:
        """重装：删除旧实例，重新创建"""
        try:
            vm_index = self._extract_index(vm_conf.vm_uuid)
            logger.info(f"[MEmu] 重装模拟器: 索引{vm_index}")
            # 先停止
            self._memuc("stop", "-i", vm_index)
            time.sleep(2)
            # 删除旧实例
            ok, out, err = self._memuc("remove", "-i", vm_index)
            if not ok:
                return ZMessage(
                    success=False, action="VMSetups",
                    message=f"删除旧实例失败: {err or out}")
            # 重新创建
            return self.VMCreate(vm_conf)
        except Exception as e:
            logger.error(f"[MEmu] 重装模拟器失败: {e}")
            return ZMessage(success=False, action="VMSetups", message=str(e))

    # 配置虚拟机 ===============================================================
    def VMUpdate(self, vm_conf: VMConfig, vm_last: VMConfig) -> ZMessage:
        try:
            logger.info(f"[MEmu] 更新模拟器配置: {vm_conf.vm_uuid}")
            vm_index = self._extract_index(vm_conf.vm_uuid)

            # 网络检查 =========================================================
            vm_conf, net_result = self.NetCheck(vm_conf)
            if not net_result.success:
                return net_result
            self.IPUpdate(vm_conf, vm_last)

            # 停止模拟器 =======================================================
            self._memuc("stop", "-i", vm_index)
            time.sleep(2)

            # 更新CPU/内存 =====================================================
            if vm_conf.cpu_num != vm_last.cpu_num:
                self._memuc("setconfigex", "-i", vm_index,
                            "cpus", str(vm_conf.cpu_num))
            if vm_conf.mem_num != vm_last.mem_num:
                self._memuc("setconfigex", "-i", vm_index,
                            "memory", str(vm_conf.mem_num))

            # 重命名 ===========================================================
            if vm_conf.vm_name and vm_conf.vm_name != vm_last.vm_name:
                self._memuc("rename", "-i", vm_index, vm_conf.vm_name)

            # 重装系统 =========================================================
            if vm_conf.os_name != vm_last.os_name and vm_last.os_name:
                self.VMSetups(vm_conf)
                return ZMessage(success=True, action="VMUpdate",
                                message="模拟器重装完成")

            # 重新启动 =========================================================
            self._memuc("start", "-i", vm_index, "-b")

            # super().VMUpdate 会用 vm_conf.vm_uuid 作为键保存到 vm_saving
            return super().VMUpdate(vm_conf, vm_last)
        except Exception as e:
            logger.error(f"[MEmu] 更新模拟器失败: {e}")
            traceback.print_exc()
            return ZMessage(success=False, action="VMUpdate", message=str(e))

    # 删除虚拟机 ===============================================================
    def VMDelete(self, vm_name: str, rm_back=True) -> ZMessage:
        try:
            logger.info(f"[MEmu] 删除模拟器: {vm_name}")
            if vm_name not in self.vm_saving:
                return ZMessage(
                    success=False, action="VMDelete",
                    message=f"模拟器 {vm_name} 不存在")

            vm_conf = self.vm_saving[vm_name]
            vm_index = self._extract_index(vm_conf.vm_uuid)

            # 停止 =============================================================
            self._memuc("stop", "-i", vm_index)
            time.sleep(2)

            # 解绑IP ===========================================================
            self.IPBinder(vm_conf, False)

            # 删除实例 =========================================================
            ok, out, err = self._memuc("remove", "-i", vm_index)
            if not ok:
                logger.warning(f"[MEmu] 删除实例失败: {err or out}")

            # 从配置中移除 =====================================================
            if vm_name in self.vm_saving:
                del self.vm_saving[vm_name]
            self.data_set()

            hs_result = ZMessage(
                success=True, action="VMDelete",
                message=f"模拟器 {vm_name} 已删除")
            self.logs_set(hs_result)
            return hs_result
        except Exception as e:
            logger.error(f"[MEmu] 删除模拟器失败: {e}")
            traceback.print_exc()
            return ZMessage(success=False, action="VMDelete", message=str(e))

    # 虚拟机电源 ===============================================================
    def VMPowers(self, vm_name: str, power: VMPowers) -> ZMessage:
        try:
            if vm_name not in self.vm_saving:
                return ZMessage(
                    success=False, action="VMPowers",
                    message=f"模拟器 {vm_name} 不存在")

            vm_index = self._extract_index(self.vm_saving[vm_name].vm_uuid)
            parent_result = super().VMPowers(vm_name, power)
            original_flag = (parent_result.results.get("original_flag")
                             if parent_result.results else None)

            power_map = {
                VMPowers.S_START: ("start", ["-i", vm_index, "-b"]),
                VMPowers.S_CLOSE: ("stop", ["-i", vm_index]),
                VMPowers.H_CLOSE: ("stop", ["-i", vm_index]),
                VMPowers.S_RESET: ("reboot", ["-i", vm_index]),
                VMPowers.H_RESET: ("reboot", ["-i", vm_index]),
            }

            if power in power_map:
                cmd, args = power_map[power]
                ok, out, err = self._memuc(cmd, *args)
                msg_map = {
                    VMPowers.S_START: ("启动成功", "启动失败"),
                    VMPowers.S_CLOSE: ("关机成功", "关机失败"),
                    VMPowers.H_CLOSE: ("强制关机成功", "强制关机失败"),
                    VMPowers.S_RESET: ("重启成功", "重启失败"),
                    VMPowers.H_RESET: ("强制重启成功", "强制重启失败"),
                }
                succ_msg, fail_msg = msg_map[power]
                hs_result = ZMessage(
                    success=ok, action="VMPowers",
                    message=succ_msg if ok else f"{fail_msg}: {err or out}")
            elif power == VMPowers.A_PAUSE:
                # MEmu不支持暂停，模拟为最小化
                hs_result = ZMessage(
                    success=False, action="VMPowers",
                    message="逍遥模拟器不支持暂停操作")
            elif power == VMPowers.A_WAKED:
                hs_result = ZMessage(
                    success=False, action="VMPowers",
                    message="逍遥模拟器不支持恢复操作")
            else:
                hs_result = ZMessage(
                    success=False, action="VMPowers",
                    message=f"不支持的电源操作: {power}")

            if not hs_result.success and original_flag is not None:
                self.vm_saving[vm_name].vm_flag = original_flag
                self.data_set()
            elif hs_result.success:
                import threading
                def delayed_refresh():
                    time.sleep(5)
                    self.vm_loads(vm_name)
                threading.Thread(target=delayed_refresh, daemon=True).start()

            self.logs_set(hs_result)
            return hs_result
        except Exception as e:
            logger.error(f"[MEmu] 电源操作失败: {e}")
            traceback.print_exc()
            return ZMessage(success=False, action="VMPowers", message=str(e))

    # 获取虚拟机实际状态 =======================================================
    def GetPower(self, vm_name: str) -> str:
        """通过memuc isvmrunning获取模拟器状态"""
        try:
            if vm_name not in self.vm_saving:
                return "未知"
            vm_index = self._extract_index(self.vm_saving[vm_name].vm_uuid)
            ok, stdout, _ = self._memuc("isvmrunning", "-i", vm_index)
            if ok:
                text = stdout.strip().lower()
                if "running" in text and "not" not in text:
                    return "运行中"
                elif "not running" in text:
                    return "已关机"
            return "未知"
        except Exception as e:
            logger.warning(f"[MEmu] 获取模拟器状态失败: {e}")
            return "未知"

    # 虚拟机截图 ===============================================================
    def VMScreen(self, vm_name: str = "") -> str:
        """通过ADB截取模拟器屏幕"""
        try:
            if vm_name not in self.vm_saving:
                return ""
            vm_index = self._extract_index(self.vm_saving[vm_name].vm_uuid)

            # 截图到模拟器内部
            self._adb(vm_index, "shell", "screencap", "-p",
                      "/sdcard/screen_cap.png", timeout=15)
            time.sleep(0.5)

            # 拉取到本地临时文件
            tmp_file = tempfile.mktemp(suffix=".png")
            ok, out, err = self._adb(
                vm_index, "pull", "/sdcard/screen_cap.png", tmp_file,
                timeout=15)

            if ok and os.path.exists(tmp_file):
                with open(tmp_file, "rb") as f:
                    data = f.read()
                os.remove(tmp_file)
                return "data:image/png;base64," + base64.b64encode(data).decode()
            return ""
        except Exception as e:
            logger.warning(f"[MEmu] 截图失败: {e}")
            return ""

    # 修改密码（Android锁屏PIN）================================================
    def VMPasswd(self, vm_name: str, os_pass: str) -> ZMessage:
        """通过ADB修改Android锁屏密码"""
        try:
            if vm_name not in self.vm_saving:
                return ZMessage(
                    success=False, action="VMPasswd",
                    message="模拟器不存在")
            vm_index = self._extract_index(self.vm_saving[vm_name].vm_uuid)
            # 设置锁屏PIN（需要root权限）
            ok, out, err = self._adb(
                vm_index, "shell",
                f"locksettings set-pin {os_pass}", timeout=15)
            if ok:
                self.vm_saving[vm_name].os_pass = os_pass
                self.data_set()
                return ZMessage(
                    success=True, action="VMPasswd",
                    message="锁屏密码修改成功")
            return ZMessage(
                success=False, action="VMPasswd",
                message=f"密码修改失败: {err or out}")
        except Exception as e:
            logger.error(f"[MEmu] 修改密码失败: {e}")
            return ZMessage(success=False, action="VMPasswd", message=str(e))

    # VNC获取（ADB端口信息）====================================================
    def VNCGets(self, vm_name: str) -> ZMessage:
        """获取ADB连接信息（逍遥模拟器通过ADB连接）"""
        try:
            if vm_name not in self.vm_saving:
                return ZMessage(
                    success=False, action="VNCGets",
                    message="模拟器不存在")
            vm_index = self._extract_index(self.vm_saving[vm_name].vm_uuid)
            # 逍遥模拟器ADB端口规则：第0个=21503，第N个=21503+N*10
            try:
                idx = int(vm_index)
                adb_port = 21503 + idx * 10
            except ValueError:
                adb_port = 21503
            host = self.hs_config.server_addr or "127.0.0.1"
            return ZMessage(
                success=True, action="VNCGets",
                message="ADB连接信息获取成功",
                results={
                    "host": host,
                    "port": adb_port,
                    "type": "adb",
                    "connect": f"adb connect {host}:{adb_port}"
                })
        except Exception as e:
            logger.error(f"[MEmu] 获取ADB信息失败: {e}")
            return ZMessage(success=False, action="VNCGets", message=str(e))

    # 备份虚拟机（导出OVA）=====================================================
    def VMBackup(self, vm_name: str, vm_tips: str) -> ZMessage:
        try:
            if vm_name not in self.vm_saving:
                return ZMessage(
                    success=False, action="VMBackup",
                    message="模拟器不存在")
            vm_index = self._extract_index(self.vm_saving[vm_name].vm_uuid)
            backup_dir = self.hs_config.backup_path or "./DataSaving/backups"
            os.makedirs(backup_dir, exist_ok=True)

            import datetime
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = os.path.join(
                backup_dir, f"{vm_name}_{ts}.ova")

            ok, out, err = self._memuc(
                "export", "-i", vm_index, backup_file, timeout=300)
            if ok:
                hs_result = ZMessage(
                    success=True, action="VMBackup",
                    message=f"备份成功: {backup_file}",
                    results={"backup_file": backup_file})
                self.logs_set(hs_result)
                return hs_result
            return ZMessage(
                success=False, action="VMBackup",
                message=f"备份失败: {err or out}")
        except Exception as e:
            logger.error(f"[MEmu] 备份失败: {e}")
            return ZMessage(success=False, action="VMBackup", message=str(e))

    # 恢复虚拟机（导入OVA）=====================================================
    def Restores(self, vm_name: str, vm_back: str) -> ZMessage:
        try:
            backup_dir = self.hs_config.backup_path or "./DataSaving/backups"
            backup_file = os.path.join(backup_dir, vm_back)
            if not os.path.exists(backup_file):
                return ZMessage(
                    success=False, action="Restores",
                    message=f"备份文件不存在: {vm_back}")

            ok, out, err = self._memuc("import", backup_file, timeout=300)
            if ok:
                hs_result = ZMessage(
                    success=True, action="Restores",
                    message="恢复成功，请重新扫描模拟器")
                self.logs_set(hs_result)
                return hs_result
            return ZMessage(
                success=False, action="Restores",
                message=f"恢复失败: {err or out}")
        except Exception as e:
            logger.error(f"[MEmu] 恢复失败: {e}")
            return ZMessage(success=False, action="Restores", message=str(e))

    # 硬盘挂载（Android不支持额外硬盘）=========================================
    def HDDMount(self, vm_name: str, vm_imgs: SDConfig, in_flag=True) -> ZMessage:
        return ZMessage(
            success=False, action="HDDMount",
            message="逍遥模拟器不支持挂载额外硬盘")

    # ISO镜像挂载（通过ADB推送APK）=============================================
    def ISOMount(self, vm_name: str, vm_imgs: IMConfig, in_flag=True) -> ZMessage:
        """通过ADB安装APK文件（替代ISO挂载）"""
        try:
            if vm_name not in self.vm_saving:
                return ZMessage(
                    success=False, action="ISOMount",
                    message="模拟器不存在")
            vm_index = self._extract_index(self.vm_saving[vm_name].vm_uuid)

            if in_flag:
                apk_path = os.path.join(
                    self.hs_config.dvdrom_path or "", vm_imgs.iso_file)
                if not os.path.exists(apk_path):
                    return ZMessage(
                        success=False, action="ISOMount",
                        message="APK文件不存在")
                ok, out, err = self._adb(
                    vm_index, "install", "-r", apk_path, timeout=120)
                if ok:
                    self.vm_saving[vm_name].iso_all[vm_imgs.iso_name] = vm_imgs
                    self.data_set()
                    return ZMessage(
                        success=True, action="ISOMount",
                        message="APK安装成功")
                return ZMessage(
                    success=False, action="ISOMount",
                    message=f"APK安装失败: {err or out}")
            else:
                # 卸载APK（需要包名）
                pkg = vm_imgs.iso_name
                ok, out, err = self._adb(
                    vm_index, "uninstall", pkg, timeout=30)
                if vm_imgs.iso_name in self.vm_saving[vm_name].iso_all:
                    del self.vm_saving[vm_name].iso_all[vm_imgs.iso_name]
                self.data_set()
                return ZMessage(
                    success=ok, action="ISOMount",
                    message="APK卸载成功" if ok else f"APK卸载失败: {err or out}")
        except Exception as e:
            logger.error(f"[MEmu] APK操作失败: {e}")
            return ZMessage(success=False, action="ISOMount", message=str(e))

    # 加载备份列表 =============================================================
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

    # 查找USB设备（通过ADB）===================================================
    def USBShows(self) -> dict[str, USBInfos]:
        """列出已连接的ADB设备"""
        try:
            ok, stdout, _ = self._memuc("adb", "--", "devices")
            if not ok:
                return {}
            usb_dict = {}
            for line in stdout.splitlines():
                line = line.strip()
                if not line or line.startswith("List"):
                    continue
                parts = line.split()
                if len(parts) >= 2 and parts[1] == "device":
                    serial = parts[0]
                    usb_dict[serial] = USBInfos(
                        vid_uuid=serial, pid_uuid="",
                        usb_hint=f"ADB设备: {serial}")
            return usb_dict
        except Exception as e:
            logger.error(f"[MEmu] 获取ADB设备失败: {e}")
            return {}

    # USB设备直通（ADB连接）===================================================
    def USBSetup(self, vm_name: str, ud_info, ud_keys: str,
                 in_flag=True) -> ZMessage:
        return ZMessage(
            success=False, action="USBSetup",
            message="逍遥模拟器USB直通请通过ADB管理")

    # 安装APK（扩展功能）======================================================
    def install_apk(self, vm_name: str, apk_path: str) -> ZMessage:
        """安装APK到模拟器"""
        try:
            if vm_name not in self.vm_saving:
                return ZMessage(success=False, action="InstallAPK",
                                message="模拟器不存在")
            vm_index = self._extract_index(self.vm_saving[vm_name].vm_uuid)
            ok, out, err = self._adb(
                vm_index, "install", "-r", apk_path, timeout=120)
            return ZMessage(
                success=ok, action="InstallAPK",
                message="APK安装成功" if ok else f"安装失败: {err or out}")
        except Exception as e:
            return ZMessage(success=False, action="InstallAPK", message=str(e))

    # 执行ADB Shell命令（扩展功能）=============================================
    def exec_shell(self, vm_name: str, shell_cmd: str) -> ZMessage:
        """在模拟器中执行Shell命令"""
        try:
            if vm_name not in self.vm_saving:
                return ZMessage(success=False, action="ExecShell",
                                message="模拟器不存在")
            vm_index = self._extract_index(self.vm_saving[vm_name].vm_uuid)
            ok, out, err = self._adb(
                vm_index, "shell", shell_cmd, timeout=30)
            return ZMessage(
                success=ok, action="ExecShell",
                message=out if ok else f"执行失败: {err or out}",
                results={"output": out})
        except Exception as e:
            return ZMessage(success=False, action="ExecShell", message=str(e))

    # 整理模拟器窗口 ===========================================================
    def sort_windows(self) -> ZMessage:
        """整理所有模拟器窗口排列"""
        try:
            ok, out, err = self._memuc("sortwin")
            return ZMessage(
                success=ok, action="SortWin",
                message="窗口整理完成" if ok else f"整理失败: {err or out}")
        except Exception as e:
            return ZMessage(success=False, action="SortWin", message=str(e))

    # 随机化设备信息 ===========================================================
    def randomize_device(self, vm_name: str) -> ZMessage:
        """随机化模拟器设备信息（v7.5.0+）"""
        try:
            if vm_name not in self.vm_saving:
                return ZMessage(success=False, action="Randomize",
                                message="模拟器不存在")
            vm_index = self._extract_index(self.vm_saving[vm_name].vm_uuid)
            ok, out, err = self._memuc("randomize", "-i", vm_index)
            return ZMessage(
                success=ok, action="Randomize",
                message="设备信息已随机化" if ok else f"随机化失败: {err or out}")
        except Exception as e:
            return ZMessage(success=False, action="Randomize", message=str(e))
