# Workstation - VMware Workstation虚拟化平台管理 ###############################
# 提供VMware Workstation虚拟机的创建、管理和监控功能
################################################################################
import shutil
import string
import subprocess
import traceback
import tempfile
import random
import os
from loguru import logger
from HostServer.BasicServer import BasicServer
from MainObject.Config.HSConfig import HSConfig
from MainObject.Config.IMConfig import IMConfig
from MainObject.Config.SDConfig import SDConfig
from MainObject.Config.VMPowers import VMPowers
from MainObject.Public.HWStatus import HWStatus
from MainObject.Public.ZMessage import ZMessage
from MainObject.Config.VMConfig import VMConfig
from HostServer.WorkstationAPI.VMWRestAPI import VRestAPI


class HostServer(BasicServer):
    # 宿主机服务 ===============================================================
    def __init__(self, config: HSConfig, **kwargs):
        super().__init__(config, **kwargs)  # 传递 kwargs，确保 db 参数能正确传递
        super().__load__(**kwargs)
        self.vmrest_pid = None
        self.vmrest_api = VRestAPI(
            self.hs_config.server_addr,
            self.hs_config.server_user,
            self.hs_config.server_pass,
            self.hs_config.launch_path,
        )

    # 公共函数 - 获取虚拟机路径 ================================================
    def _get_vm_path(self, vm_uuid: str) -> str:
        """获取虚拟机目录路径"""
        return os.path.join(self.hs_config.system_path, vm_uuid)

    # 公共函数 - 获取VMX文件路径 ===============================================
    def _get_vmx_file(self, vm_uuid: str) -> str:
        """获取VMX文件完整路径"""
        return os.path.join(self._get_vm_path(vm_uuid), f"{vm_uuid}.vmx")

    # 公共函数 - 检查虚拟机是否存在 ============================================
    def _check_vm_exists(self, vm_name: str) -> tuple:
        """检查虚拟机是否存在，返回(是否存在, 虚拟机配置或None)"""
        if vm_name not in self.vm_saving:
            return False, None
        return True, self.vm_saving[vm_name]

    # 宿主机任务 ===============================================================
    def Crontabs(self) -> bool:
        # 专用操作 =============================================================
        # 通用操作 =============================================================
        return super().Crontabs()

    # 宿主机状态 ===============================================================
    def HSStatus(self) -> HWStatus:
        # 专用操作 =============================================================
        # 通用操作 =============================================================
        return super().HSStatus()

    # 初始宿主机 ===============================================================
    def HSCreate(self) -> ZMessage:
        # 专用操作 =============================================================
        # 通用操作 =============================================================
        return super().HSCreate()

    # 还原宿主机 ===============================================================
    def HSDelete(self) -> ZMessage:
        # 专用操作 =============================================================
        # 通用操作 =============================================================
        return super().HSDelete()

    # 读取宿主机 ===============================================================
    def HSLoader(self) -> ZMessage:
        try:
            # 专用操作 =========================================================
            # 启动VM Rest Server ===============================================
            vmrest_path = os.path.join(
                self.hs_config.launch_path, "vmrest.exe")
            
            # 检查文件是否存在 =================================================
            if not os.path.exists(vmrest_path):
                return ZMessage(success=False, action="HSLoader",
                                message=f"未找到vmrest.exe文件")
            
            # 配置后台运行隐藏窗口 =============================================
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
            # 启动进程 =========================================================
            self.vmrest_pid = subprocess.Popen(
                [vmrest_path],
                cwd=self.hs_config.launch_path,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW)
            
            # 通用操作 =========================================================
            return super().HSLoader()
            
        except Exception as e:
            # 异常处理 =========================================================
            logger.error(f"启动VM Rest Server失败: {str(e)}")
            traceback.print_exc()
            return ZMessage(success=False, action="HSLoader", message=str(e))

    # 卸载宿主机 ===============================================================
    def HSUnload(self) -> ZMessage:
        try:
            # 专用操作 =========================================================
            # 检查VM Rest Server是否运行 =======================================
            if self.vmrest_pid is None:
                return ZMessage(
                    success=False, action="HSUnload",
                    message="VM Rest Server未运行")
            
            # 尝试正常终止进程 =================================================
            try:
                self.vmrest_pid.terminate()
                self.vmrest_pid.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # 强制终止 =====================================================
                self.vmrest_pid.kill()
            finally:
                self.vmrest_pid = None
            
            # 通用操作 =========================================================
            return super().HSUnload()
            
        except Exception as e:
            # 异常处理 =========================================================
            logger.error(f"卸载VM Rest Server失败: {str(e)}")
            traceback.print_exc()
            return ZMessage(success=False, action="HSUnload", message=str(e))

    # 虚拟机列出 ===============================================================
    def VMStatus(self, vm_name: str = "",
                 s_t: int = None, e_t: int = None) -> dict[str, list[HWStatus]]:
        # 专用操作 =============================================================
        # 通用操作 =============================================================
        return super().VMStatus(vm_name)

    # 虚拟机扫描 ===============================================================
    def VMDetect(self) -> ZMessage:
        try:
            # 获取过滤前缀 =====================================================
            filter_prefix = self.hs_config.filter_name
            
            # 获取所有虚拟机列表 ===============================================
            vms_result = self.vmrest_api.return_vmx()
            if not vms_result.success:
                return ZMessage(
                    success=False, action="VMDetect",
                    message=f"获取虚拟机列表失败: {vms_result.message}")
            
            # 解析虚拟机列表 ===================================================
            vms_list = vms_result.results \
                if isinstance(vms_result.results, list) else []
            scanned_count = 0
            added_count = 0
            
            # 处理每个虚拟机 ===================================================
            for vm_info in vms_list:
                vm_path = vm_info.get("path", "")
                vm_id = vm_info.get("id", "")
                if not vm_path:
                    continue
                
                # 提取虚拟机名称 ===============================================
                vmx_name = os.path.splitext(os.path.basename(vm_path))[0]
                
                # 前缀过滤 =====================================================
                if filter_prefix and not vmx_name.startswith(filter_prefix):
                    continue
                
                scanned_count += 1
                
                # 检查是否已存在 ===============================================
                if vmx_name in self.vm_saving:
                    continue
                
                # 创建默认配置 =================================================
                default_vm_config = VMConfig()
                self.vm_saving[vmx_name] = default_vm_config
                added_count += 1
                
                # 记录日志 =====================================================
                log_msg = ZMessage(
                    success=True,
                    action="VMDetect",
                    message=f"发现并添加虚拟机: {vmx_name}",
                    results={
                        "vm_name": vmx_name,
                        "vm_id": vm_id,
                        "vm_path": vm_path}
                )
                self.push_log(log_msg)
            
            # 保存到数据库 =====================================================
            if added_count > 0:
                success = self.data_set()
                if not success:
                    return ZMessage(
                        success=False, action="VMDetect",
                        message="保存扫描的虚拟机到数据库失败")
            
            # 返回成功消息 =====================================================
            return ZMessage(
                success=True,
                action="VMDetect",
                message=f"扫描完成。"
                        f"共扫描到{scanned_count}台虚拟机，"
                        f"新增{added_count}台虚拟机配置。",
                results={
                    "scanned": scanned_count,
                    "added": added_count,
                    "prefix_filter": filter_prefix
                }
            )
            
        except Exception as e:
            # 异常处理 =========================================================
            logger.error(f"扫描虚拟机失败: {str(e)}")
            traceback.print_exc()
            return ZMessage(success=False, action="VMDetect", message=str(e))

    # 创建虚拟机 ===============================================================
    def VMCreate(self, vm_conf: VMConfig) -> ZMessage:
        try:
            # 网络检查 =========================================================
            vm_conf, net_result = self.NetCheck(vm_conf)
            if not net_result.success:
                return net_result
            
            # IP绑定 ===========================================================
            self.IPBinder(vm_conf, True)
            
            # 专用操作 =========================================================
            # 创建虚拟机目录 ===================================================
            vm_path = self._get_vm_path(vm_conf.vm_uuid)
            if not os.path.exists(vm_path):
                os.mkdir(vm_path)
            
            # 生成VMX配置文件 ==================================================
            vm_file = os.path.join(vm_path, vm_conf.vm_uuid)
            vm_text = self.vmrest_api.create_vmx(vm_conf, self.hs_config)
            with open(f"{vm_file}.vmx", "w") as vm_save_file:
                vm_save_file.write(vm_text)
            
            # 安装系统 =========================================================
            results = self.VMSetups(vm_conf)
            if not results.success:
                raise Exception(f"安装系统失败: {results.message}")
            
            # 注册虚拟机 =======================================================
            register_result = self.vmrest_api.loader_vmx(f"{vm_file}.vmx")
            if not register_result.success:
                raise Exception(f"注册虚拟机失败: {register_result.message}")
            
            # 启动虚拟机 =======================================================
            self.VMPowers(vm_conf.vm_uuid, VMPowers.S_START)
            
            # 通用操作 =========================================================
            return super().VMCreate(vm_conf)
            
        except Exception as e:
            # 异常处理 - 清理已创建的文件 =====================================
            logger.error(f"创建虚拟机失败: {str(e)}")
            traceback.print_exc()
            
            vm_path = self._get_vm_path(vm_conf.vm_uuid)
            if os.path.exists(vm_path):
                shutil.rmtree(vm_path)
            
            # 记录日志 =========================================================
            hs_result = ZMessage(
                success=False, action="VMCreate",
                message=f"虚拟机创建失败: {str(e)}")
            self.logs_set(hs_result)
            return hs_result

    # 安装虚拟机 ===============================================================
    def VMSetups(self, vm_conf: VMConfig) -> ZMessage:
        try:
            # 复制镜像文件 =====================================================
            vm_tail = vm_conf.os_name.split(".")[-1]
            im_file = os.path.join(self.hs_config.images_path, vm_conf.os_name)
            vm_file = os.path.join(
                self._get_vm_path(vm_conf.vm_uuid),
                f"{vm_conf.vm_uuid}.{vm_tail}")
            
            # 删除旧文件 =======================================================
            if os.path.exists(vm_file):
                os.remove(vm_file)
            
            # 复制镜像 =========================================================
            shutil.copy(im_file, vm_file)
            
            # 扩展硬盘 =========================================================
            return self.vmrest_api.extend_hdd(vm_file, vm_conf.hdd_num)
            
        except Exception as e:
            # 异常处理 =========================================================
            logger.error(f"安装虚拟机失败: {str(e)}")
            traceback.print_exc()
            return ZMessage(success=False, action="VMSetups", message=str(e))

    # 配置虚拟机 ===============================================================
    def VMUpdate(self, vm_conf: VMConfig, vm_last: VMConfig) -> ZMessage:
        try:
            # 网络检查 =========================================================
            vm_conf, net_result = self.NetCheck(vm_conf)
            if not net_result.success:
                return net_result
            
            # IP绑定 ===========================================================
            self.IPBinder(vm_conf, True)
            
            # 专用操作 =========================================================
            # 检查虚拟机是否存在 ===============================================
            exists, _ = self._check_vm_exists(vm_conf.vm_uuid)
            if not exists:
                return ZMessage(
                    success=False, action="VMUpdate",
                    message=f"虚拟机 {vm_conf.vm_uuid} 不存在")
            
            # 清理锁文件 =======================================================
            vm_saving = self._get_vm_path(vm_conf.vm_uuid)
            vm_locker = os.path.join(vm_saving, f"{vm_conf.vm_uuid}.vmx.lck")
            if os.path.exists(vm_locker):
                shutil.rmtree(vm_locker)
            
            # 更新配置存储 =====================================================
            self.vm_saving[vm_conf.vm_uuid] = vm_conf
            vm_path = os.path.join(vm_saving, vm_conf.vm_uuid)
            
            # 关闭虚拟机 =======================================================
            self.VMPowers(vm_conf.vm_uuid, VMPowers.H_CLOSE)
            
            # 重装系统 =========================================================
            if vm_conf.os_name != vm_last.os_name and vm_last.os_name != "":
                self.VMSetups(vm_conf)
            
            # 更新硬盘 =========================================================
            if vm_conf.hdd_num > vm_last.hdd_num:
                disk_file = f"{vm_path}.{vm_conf.os_name.split('.')[-1]}"
                self.vmrest_api.extend_hdd(disk_file, vm_conf.hdd_num)
            
            # 更新网卡 =========================================================
            network_result = self.IPUpdate(vm_conf, vm_last)
            if not network_result.success:
                return ZMessage(
                    success=False, action="VMUpdate",
                    message=f"虚拟机 {vm_conf.vm_uuid} "
                            f"网络配置更新失败: {network_result.message}")
            
            # 更新VMX文件 ======================================================
            vm_save_name = self._get_vmx_file(vm_conf.vm_uuid)
            if os.path.exists(vm_save_name):
                with open(vm_save_name, "r", encoding="utf-8") as vm_file:
                    existing_vmx_content = vm_file.read()
                    vm_text = self.vmrest_api.update_vmx(
                        existing_vmx_content, vm_conf, self.hs_config)
            else:
                vm_text = self.vmrest_api.create_vmx(vm_conf, self.hs_config)
            
            # 写入VMX文件 ======================================================
            with open(vm_save_name, "w", encoding="utf-8") as vm_save_file:
                vm_save_file.write(vm_text)
            
            # 启动虚拟机 =======================================================
            start_result = self.VMPowers(vm_conf.vm_uuid, VMPowers.S_START)
            if not start_result.success:
                return ZMessage(
                    success=False, action="VMUpdate",
                    message=f"虚拟机 {vm_conf.vm_uuid} "
                            f"启动失败: {start_result.message}")
            
            # 通用操作 =========================================================
            return super().VMUpdate(vm_conf, vm_last)
            
        except Exception as e:
            # 异常处理 =========================================================
            logger.error(f"更新虚拟机失败: {str(e)}")
            traceback.print_exc()
            return ZMessage(success=False, action="VMUpdate", message=str(e))

    # 删除虚拟机 ===============================================================
    def VMDelete(self, vm_name: str, rm_back=True) -> ZMessage:
        try:
            # 专用操作 =========================================================
            # 检查虚拟机是否存在 ===============================================
            exists, vm_conf = self._check_vm_exists(vm_name)
            if not exists:
                return ZMessage(
                    success=False,
                    action="VMDelete",
                    message=f"虚拟机 {vm_name} 不存在")
            
            # 关闭虚拟机 =======================================================
            self.VMPowers(vm_name, VMPowers.H_CLOSE)
            
            # 解绑IP ===========================================================
            self.IPBinder(vm_conf, False)
            
            # 清理锁文件 =======================================================
            vm_saving = self._get_vm_path(vm_name)
            vm_locker = os.path.join(vm_saving, f"{vm_name}.vmx.lck")
            if os.path.exists(vm_locker):
                shutil.rmtree(vm_locker)
            
            # 删除虚拟机 =======================================================
            hs_result = self.vmrest_api.delete_vmx(vm_name)
            
            # 通用操作 =========================================================
            super().VMDelete(vm_name)
            return hs_result
            
        except Exception as e:
            # 异常处理 =========================================================
            logger.error(f"删除虚拟机失败: {str(e)}")
            traceback.print_exc()
            return ZMessage(success=False, action="VMDelete", message=str(e))

    # 虚拟机电源 ===============================================================
    def VMPowers(self, vm_name: str, power: VMPowers) -> ZMessage:
        try:
            # 专用操作 =========================================================
            # 重启操作 =========================================================
            if power == VMPowers.H_RESET or power == VMPowers.S_RESET:
                self.vmrest_api.powers_set(vm_name, VMPowers.H_CLOSE)
                hs_result = self.vmrest_api.powers_set(vm_name, VMPowers.S_START)
            else:
                # 其他电源操作 =================================================
                hs_result = self.vmrest_api.powers_set(vm_name, power)
            
            # 记录日志 =========================================================
            self.logs_set(hs_result)
            
            # 通用操作 =========================================================
            super().VMPowers(vm_name, power)
            return hs_result
            
        except Exception as e:
            # 异常处理 =========================================================
            logger.error(f"虚拟机电源操作失败: {str(e)}")
            traceback.print_exc()
            return ZMessage(success=False, action="VMPowers", message=str(e))

    # 备份虚拟机 ===============================================================
    def VMBackup(self, vm_name: str, vm_tips: str) -> ZMessage:
        return super().VMBackup(vm_name, vm_tips)

    # 恢复虚拟机 ===============================================================
    def Restores(self, vm_name: str, vm_back: str) -> ZMessage:
        return super().Restores(vm_name, vm_back)

    # VM镜像挂载 ===============================================================
    def HDDMount(self, vm_name: str, vm_imgs: SDConfig, in_flag=True) -> ZMessage:
        return super().HDDMount(vm_name, vm_imgs, in_flag)

    # ISO镜像挂载 ==============================================================
    def ISOMount(self, vm_name: str, vm_imgs: IMConfig, in_flag=True) -> ZMessage:
        return super().ISOMount(vm_name, vm_imgs, in_flag)

    # 加载备份 =================================================================
    def LDBackup(self, vm_back: str = "") -> ZMessage:
        return super().LDBackup(vm_back)

    # 移除备份 =================================================================
    def RMBackup(self, vm_name: str, vm_back: str = "") -> ZMessage:
        return super().RMBackup(vm_name, vm_back)

    # 移除磁盘 =================================================================
    def RMMounts(self, vm_name: str, vm_imgs: str) -> ZMessage:
        return super().RMMounts(vm_name, vm_imgs)

    # 查找显卡 =================================================================
    def GPUShows(self) -> dict[str, str]:
        return {}

    # 虚拟机截图 ===============================================================
    def VMScreen(self, vm_name: str = "") -> str:
        try:
            # 检查虚拟机配置 ===================================================
            exists, vm_conf = self._check_vm_exists(vm_name)
            if not exists:
                logger.error(f"未找到虚拟机 {vm_name} 的配置")
                return ""
            
            # 生成临时文件路径 =================================================
            temp_dir = tempfile.gettempdir()
            path_img = os.path.join(temp_dir, f"{vm_name}_screenshot.png")
            
            # 确定客户机用户名 =================================================
            conf_usr = "administrator" if \
                vm_conf.os_name.lower().startswith("windows") else "root"
            
            # 获取截图 =========================================================
            capture_result = self.vmrest_api.capture_screen(
                vm_name,
                path_img,
                conf_usr,
                vm_conf.os_pass
            )
            if not capture_result.success:
                logger.error(f"获取截图失败: {capture_result.message}")
                return ""
            
            # 读取截图文件并转换为base64 =======================================
            if os.path.exists(path_img):
                import base64
                with open(path_img, "rb") as f:
                    shot_b64 = base64.b64encode(f.read()).decode('utf-8')
                
                # 删除临时文件 =================================================
                os.remove(path_img)
                logger.info(f"成功获取虚拟机 {vm_name} 截图")
                return shot_b64
            else:
                logger.error(f"截图文件不存在: {path_img}")
                return ""
                
        except Exception as e:
            # 异常处理 =========================================================
            logger.error(f"获取虚拟机截图失败: {str(e)}")
            traceback.print_exc()
            return ""

    # 获取虚拟机实际状态（从API）==============================================
    def VMStatusAPI(self, vm_name: str) -> str:
        """从VMWare Workstation API获取虚拟机实际状态"""
        try:
            result = self.vmrest_api.powers_get(vm_name)
            if result.success and result.results:
                power_state = result.results.get('power_state', '')
                # 映射VMWare状态到中文状态
                state_map = {
                    'poweredOn': '运行中',
                    'poweredOff': '已关机',
                    'suspended': '已暂停'
                }
                return state_map.get(power_state, '未知')
        except Exception as e:
            logger.warning(f"从API获取虚拟机 {vm_name} 状态失败: {str(e)}")
        return ""

    # 虚拟机控制台 =============================================================
    def VMRemote(self, vm_uuid: str, ip_addr: str = "127.0.0.1") -> ZMessage:
        try:
            # 检查端口和密码配置 ===============================================
            result = super().VMRemote(vm_uuid, ip_addr)
            if not result.success:
                return result
            
            # 检查VNC端口和密码 ================================================
            public_addr = self.hs_config.public_addr[0]
            if len(self.vm_saving[vm_uuid].vc_pass) == 0:
                public_addr = "127.0.0.1"
            
            # 生成随机密码 =====================================================
            rand_pass = ''.join(
                random.sample(string.ascii_letters + string.digits, 16))
            
            # 删除旧端口 =======================================================
            self.vm_remote.exec.del_port(
                ip_addr,
                int(self.vm_saving[vm_uuid].vc_port))
            
            # 添加新端口 =======================================================
            self.vm_remote.exec.add_port(
                ip_addr,
                int(self.vm_saving[vm_uuid].vc_port),
                rand_pass
            )
            
            # 返回结果 =========================================================
            return ZMessage(
                success=True,
                action="VMRemote",
                message=(
                    f"http://{public_addr}:{self.hs_config.remote_port}"
                    f"/vnc.html?autoconnect=true&path=websockify?"
                    f"token={rand_pass}"
                )
            )
            
        except Exception as e:
            # 异常处理 =========================================================
            logger.error(f"虚拟机远程控制失败: {str(e)}")
            traceback.print_exc()
            return ZMessage(
                success=False,
                action="VMRemote",
                message=str(e)
            )
