# QingzhouYun - 青洲云虚拟化平台 ###############################################
# 通过HTTP API管理青洲云平台的虚拟机
################################################################################
import time
import datetime
import traceback
import requests
from loguru import logger
from HostServer.BasicServer import BasicServer
from MainObject.Config.HSConfig import HSConfig
from MainObject.Config.IMConfig import IMConfig
from MainObject.Config.SDConfig import SDConfig
from MainObject.Config.USBInfos import USBInfos
from MainObject.Config.VFConfig import VFConfig
from MainObject.Config.VMBackup import VMBackup
from MainObject.Config.VMPowers import VMPowers
from MainObject.Config.PortData import PortData
from MainObject.Config.WebProxy import WebProxy
from MainObject.Public.HWStatus import HWStatus
from MainObject.Public.ZMessage import ZMessage
from MainObject.Config.VMConfig import VMConfig


class HostServer(BasicServer):
    # 宿主机服务 ###############################################################
    def __init__(self, config: HSConfig, **kwargs):
        super().__init__(config, **kwargs)
        super().__load__(**kwargs)
        # 添加变量 =============================================================
        self.api_token = None       # API认证Token
        self.api_expire = 0         # Token过期时间戳
        self.session = None         # requests会话

    # =========================================================================
    # 内部辅助方法
    # =========================================================================

    def _api_base(self) -> str:
        """获取API基础URL"""
        addr = self.hs_config.server_addr.rstrip('/')
        if not addr.startswith("http"):
            addr = f"https://{addr}"
        port = self.hs_config.server_port or 443
        if port not in (80, 443):
            addr = f"{addr}:{port}"
        return addr

    def _api_url(self, path: str) -> str:
        """拼接完整API地址"""
        return f"{self._api_base()}/api/{path.lstrip('/')}"

    def _get_session(self) -> requests.Session:
        """获取或创建HTTP会话"""
        if not self.session:
            self.session = requests.Session()
            self.session.verify = False
            self.session.headers.update({
                "Content-Type": "application/json",
                "Accept": "application/json"
            })
        return self.session

    def _ensure_auth(self) -> ZMessage:
        """确保API认证有效"""
        now = int(time.time())
        if self.api_token and now < self.api_expire - 60:
            return ZMessage(success=True, action="auth")
        return self._do_login()

    def _do_login(self) -> ZMessage:
        """执行API登录认证"""
        try:
            sess = self._get_session()
            resp = sess.post(self._api_url("auth/login"), json={
                "username": self.hs_config.server_user,
                "password": self.hs_config.server_pass
            }, timeout=15)
            data = resp.json()
            if resp.status_code == 200 and data.get("code") == 0:
                self.api_token = data["data"].get("token", "")
                self.api_expire = int(time.time()) + data["data"].get(
                    "expire", 3600)
                sess.headers["Authorization"] = f"Bearer {self.api_token}"
                logger.info(
                    f"[{self.hs_config.server_name}] 青洲云API认证成功")
                return ZMessage(success=True, action="auth")
            msg = data.get("msg", resp.text)
            logger.error(
                f"[{self.hs_config.server_name}] 青洲云API认证失败: {msg}")
            return ZMessage(
                success=False, action="auth", message=f"认证失败: {msg}")
        except Exception as e:
            logger.error(
                f"[{self.hs_config.server_name}] 青洲云API连接失败: {e}")
            return ZMessage(
                success=False, action="auth", message=f"连接失败: {e}")

    def _api_get(self, path: str, params: dict = None) -> dict:
        """发送GET请求"""
        auth = self._ensure_auth()
        if not auth.success:
            return {"code": -1, "msg": auth.message}
        try:
            resp = self._get_session().get(
                self._api_url(path), params=params, timeout=30)
            return resp.json()
        except Exception as e:
            logger.error(f"API GET {path} 失败: {e}")
            return {"code": -1, "msg": str(e)}

    def _api_post(self, path: str, payload: dict = None) -> dict:
        """发送POST请求"""
        auth = self._ensure_auth()
        if not auth.success:
            return {"code": -1, "msg": auth.message}
        try:
            resp = self._get_session().post(
                self._api_url(path), json=payload or {}, timeout=60)
            return resp.json()
        except Exception as e:
            logger.error(f"API POST {path} 失败: {e}")
            return {"code": -1, "msg": str(e)}

    def _api_put(self, path: str, payload: dict = None) -> dict:
        """发送PUT请求"""
        auth = self._ensure_auth()
        if not auth.success:
            return {"code": -1, "msg": auth.message}
        try:
            resp = self._get_session().put(
                self._api_url(path), json=payload or {}, timeout=60)
            return resp.json()
        except Exception as e:
            logger.error(f"API PUT {path} 失败: {e}")
            return {"code": -1, "msg": str(e)}

    def _api_delete(self, path: str, params: dict = None) -> dict:
        """发送DELETE请求"""
        auth = self._ensure_auth()
        if not auth.success:
            return {"code": -1, "msg": auth.message}
        try:
            resp = self._get_session().delete(
                self._api_url(path), params=params, timeout=30)
            return resp.json()
        except Exception as e:
            logger.error(f"API DELETE {path} 失败: {e}")
            return {"code": -1, "msg": str(e)}

    def _ok(self, data: dict) -> bool:
        """判断API响应是否成功"""
        return data.get("code") == 0

    def _msg(self, data: dict) -> str:
        """提取API响应消息"""
        return data.get("msg", data.get("message", "未知错误"))

    def _vm_id(self, vm_name: str) -> str:
        """获取虚拟机在平台上的ID"""
        vm_conf = self.vm_finds(vm_name)
        if vm_conf and hasattr(vm_conf, 'vm_data') and isinstance(
                getattr(vm_conf, 'vm_data', None), dict):
            return vm_conf.vm_data.get("platform_id", vm_name)
        return vm_name

    def _set_vm_id(self, vm_conf: VMConfig, platform_id: str):
        """保存平台ID到虚拟机配置"""
        if not hasattr(vm_conf, 'vm_data') or not isinstance(
                getattr(vm_conf, 'vm_data', None), dict):
            vm_conf.vm_data = {}
        vm_conf.vm_data["platform_id"] = platform_id

    # =========================================================================
    # 宿主机生命周期
    # =========================================================================

    # 宿主机任务 ###############################################################
    def Crontabs(self) -> bool:
        """定时任务：同步虚拟机状态和流量统计到数据库"""
        try:
            auth = self._ensure_auth()
            if not auth.success:
                logger.warning(
                    f"[{self.hs_config.server_name}] "
                    f"青洲云认证失败，跳过定时任务")
                return super().Crontabs()
            # 获取主机状态 =====================================================
            data = self._api_get("host/status")
            if self._ok(data):
                info = data.get("data", {})
                hw = HWStatus()
                hw.cpu_usage = int(info.get("cpu_usage", 0))
                hw.cpu_total = int(info.get("cpu_total", 0))
                hw.mem_total = int(info.get("mem_total", 0))
                hw.mem_usage = int(info.get("mem_usage", 0))
                hw.hdd_total = int(info.get("hdd_total", 0))
                hw.hdd_usage = int(info.get("hdd_usage", 0))
                hw.network_u = int(info.get("network_up", 0))
                hw.network_d = int(info.get("network_down", 0))
                self.host_set(hw)
            # 同步每台虚拟机状态和流量 =========================================
            for vm_name, vm_conf in self.vm_saving.items():
                try:
                    pid = self._vm_id(vm_name)
                    st = self._api_get(f"vm/{pid}/status")
                    if self._ok(st):
                        vm_info = st.get("data", {})
                        state = vm_info.get("status", "unknown")
                        state_map = {
                            "running": VMPowers.STARTED,
                            "stopped": VMPowers.STOPPED,
                            "suspended": VMPowers.SUSPEND,
                            "paused": VMPowers.SUSPEND,
                        }
                        vm_conf.vm_flag = state_map.get(
                            state, VMPowers.UNKNOWN)
                        # 写入虚拟机状态到数据库 -------------------------------
                        vm_hw = HWStatus()
                        vm_hw.ac_status = vm_conf.vm_flag
                        vm_hw.cpu_usage = int(vm_info.get("cpu_usage", 0))
                        vm_hw.cpu_total = vm_conf.cpu_num
                        vm_hw.mem_total = vm_conf.mem_num
                        vm_hw.mem_usage = int(vm_info.get("mem_usage", 0))
                        vm_hw.hdd_total = vm_conf.hdd_num
                        vm_hw.hdd_usage = int(vm_info.get("hdd_usage", 0))
                        vm_hw.network_u = int(vm_info.get("net_up", 0))
                        vm_hw.network_d = int(vm_info.get("net_down", 0))
                        vm_hw.flu_usage = int(
                            vm_info.get("traffic_used", 0))
                        vm_hw.flu_total = vm_conf.flu_num
                        self.vm_saves(vm_name, vm_hw)
                except Exception as e:
                    logger.warning(
                        f"[{self.hs_config.server_name}] "
                        f"同步虚拟机 {vm_name} 状态失败: {e}")
            self.data_set()
        except Exception as e:
            logger.error(
                f"[{self.hs_config.server_name}] 定时任务异常: {e}")
            traceback.print_exc()
        return super().Crontabs()

    # 宿主机状态 ###############################################################
    def HSStatus(self) -> HWStatus:
        """获取宿主机状态"""
        try:
            data = self._api_get("host/status")
            if self._ok(data):
                info = data.get("data", {})
                hw = HWStatus()
                hw.cpu_usage = int(info.get("cpu_usage", 0))
                hw.cpu_total = int(info.get("cpu_total", 0))
                hw.mem_total = int(info.get("mem_total", 0))
                hw.mem_usage = int(info.get("mem_usage", 0))
                hw.hdd_total = int(info.get("hdd_total", 0))
                hw.hdd_usage = int(info.get("hdd_usage", 0))
                hw.network_u = int(info.get("network_up", 0))
                hw.network_d = int(info.get("network_down", 0))
                return hw
        except Exception as e:
            logger.error(
                f"[{self.hs_config.server_name}] 获取主机状态失败: {e}")
        return super().HSStatus()

    # 初始宿主机 ###############################################################
    def HSCreate(self) -> ZMessage:
        auth = self._ensure_auth()
        if not auth.success:
            return auth
        return super().HSCreate()

    # 还原宿主机 ###############################################################
    def HSDelete(self) -> ZMessage:
        self.api_token = None
        self.session = None
        return super().HSDelete()

    # 读取宿主机 ###############################################################
    def HSLoader(self) -> ZMessage:
        auth = self._ensure_auth()
        if not auth.success:
            return auth
        return super().HSLoader()

    # 卸载宿主机 ###############################################################
    def HSUnload(self) -> ZMessage:
        self.api_token = None
        if self.session:
            try:
                self.session.close()
            except Exception:
                pass
        self.session = None
        return super().HSUnload()

    # =========================================================================
    # 虚拟机管理
    # =========================================================================

    # 虚拟机列出/状态 #########################################################
    def VMStatus(self, vm_name: str = "") -> dict[str, list[HWStatus]]:
        return super().VMStatus(vm_name)

    # 获取虚拟机实际状态 #######################################################
    def GetPower(self, vm_name: str) -> str:
        """从青洲云API获取虚拟机实际状态"""
        try:
            pid = self._vm_id(vm_name)
            data = self._api_get(f"vm/{pid}/status")
            if self._ok(data):
                state = data.get("data", {}).get("status", "")
                state_map = {
                    "running": "运行中", "stopped": "已关机",
                    "suspended": "已暂停", "paused": "已暂停",
                    "creating": "创建中", "reinstalling": "重装中",
                }
                return state_map.get(state, "未知")
        except Exception as e:
            logger.warning(f"获取虚拟机 {vm_name} 状态失败: {e}")
        return ""

    # 虚拟机扫描 ###############################################################
    def VMDetect(self) -> ZMessage:
        """扫描并发现青洲云上的虚拟机"""
        try:
            data = self._api_get("vm/list")
            if not self._ok(data):
                return ZMessage(
                    success=False, action="VScanner",
                    message=f"获取列表失败: {self._msg(data)}")
            vm_list = data.get("data", {}).get("list", [])
            prefix = self.hs_config.filter_name or ""
            scanned = added = 0
            for vm in vm_list:
                name = vm.get("name", "")
                vid = str(vm.get("id", ""))
                if prefix and not name.startswith(prefix):
                    continue
                scanned += 1
                if name in self.vm_saving:
                    continue
                nc = VMConfig()
                nc.vm_uuid = name
                nc.cpu_num = int(vm.get("cpu", 2))
                nc.mem_num = int(vm.get("memory", 2048))
                nc.hdd_num = int(vm.get("disk", 8192))
                nc.os_name = vm.get("os", "")
                self._set_vm_id(nc, vid)
                self.vm_saving[name] = nc
                added += 1
                self.push_log(ZMessage(
                    success=True, action="VScanner",
                    message=f"发现虚拟机: {name} (ID: {vid})"))
            if added > 0:
                self.data_set()
            return ZMessage(
                success=True, action="VScanner",
                message=f"扫描完成。共{scanned}台，新增{added}台。",
                results={"scanned": scanned, "added": added})
        except Exception as e:
            logger.error(f"扫描虚拟机失败: {e}")
            traceback.print_exc()
            return ZMessage(
                success=False, action="VScanner", message=str(e))

    # 创建虚拟机 ###############################################################
    def VMCreate(self, vm_conf: VMConfig) -> ZMessage:
        logger.info(
            f"[{self.hs_config.server_name}] 创建虚拟机: {vm_conf.vm_uuid}")
        try:
            # 网络检查 =========================================================
            vm_conf, net_result = self.NetCheck(vm_conf)
            if not net_result.success:
                return net_result
            # 查找系统镜像映射 =================================================
            os_image = vm_conf.os_name
            if os_image in self.hs_config.system_maps:
                os_image = self.hs_config.system_maps[os_image][0]
            # 构建创建参数 =====================================================
            payload = {
                "name": vm_conf.vm_uuid,
                "cpu": vm_conf.cpu_num,
                "memory": vm_conf.mem_num,
                "disk": vm_conf.hdd_num,
                "os_image": os_image,
                "password": vm_conf.os_pass or "Qz@123456",
                "bandwidth_up": vm_conf.speed_u,
                "bandwidth_down": vm_conf.speed_d,
                "traffic_limit": vm_conf.flu_num,
            }
            # 网卡IP配置 ======================================================
            nic_list = []
            for _, nic in vm_conf.nic_all.items():
                ni = {"type": nic.nic_type}
                if nic.ip4_addr:
                    ni["ipv4"] = nic.ip4_addr
                if nic.ip6_addr:
                    ni["ipv6"] = nic.ip6_addr
                if nic.mac_addr:
                    ni["mac"] = nic.mac_addr
                if nic.nic_gate:
                    ni["gateway"] = nic.nic_gate
                if nic.nic_mask:
                    ni["netmask"] = nic.nic_mask
                if nic.dns_addr:
                    ni["dns"] = nic.dns_addr
                nic_list.append(ni)
            if nic_list:
                payload["network"] = nic_list
            # 调用API ==========================================================
            data = self._api_post("vm/create", payload)
            if not self._ok(data):
                return ZMessage(
                    success=False, action="VMCreate",
                    message=f"创建失败: {self._msg(data)}")
            # 保存平台ID ======================================================
            vm_id = str(data.get("data", {}).get("id", ""))
            if vm_id:
                self._set_vm_id(vm_conf, vm_id)
            logger.info(f"  虚拟机创建成功, 平台ID: {vm_id}")
            # 路由器IP绑定 ====================================================
            ikuai = super().IPBinder(vm_conf, True)
            if not ikuai.success:
                logger.warning(f"路由器绑定失败: {ikuai.message}")
        except Exception as e:
            logger.error(f"虚拟机创建失败: {e}")
            traceback.print_exc()
            return ZMessage(
                success=False, action="VMCreate", message=str(e))
        self.data_set()
        return super().VMCreate(vm_conf)

    # 安装/重装虚拟机 ##########################################################
    def VMSetups(self, vm_conf: VMConfig) -> ZMessage:
        """重装虚拟机系统"""
        logger.info(
            f"[{self.hs_config.server_name}] 重装: {vm_conf.vm_uuid}")
        try:
            pid = self._vm_id(vm_conf.vm_uuid)
            os_image = vm_conf.os_name
            if os_image in self.hs_config.system_maps:
                os_image = self.hs_config.system_maps[os_image][0]
            data = self._api_post(f"vm/{pid}/reinstall", {
                "os_image": os_image,
                "password": vm_conf.os_pass or "Qz@123456",
            })
            if not self._ok(data):
                return ZMessage(
                    success=False, action="VInstall",
                    message=f"重装失败: {self._msg(data)}")
            logger.info(f"  虚拟机重装成功")
            return ZMessage(
                success=True, action="VInstall", message="重装成功")
        except Exception as e:
            logger.error(f"重装虚拟机失败: {e}")
            traceback.print_exc()
            return ZMessage(
                success=False, action="VInstall", message=str(e))

    # 配置虚拟机 ###############################################################
    def VMUpdate(self, vm_conf: VMConfig, vm_last: VMConfig) -> ZMessage:
        """修改虚拟机配置"""
        logger.info(
            f"[{self.hs_config.server_name}] 更新配置: {vm_conf.vm_uuid}")
        try:
            pid = self._vm_id(vm_conf.vm_uuid)
            vm_conf, net_result = self.NetCheck(vm_conf)
            if not net_result.success:
                return net_result
            # 构建更新参数 =====================================================
            up = {}
            if vm_conf.cpu_num != vm_last.cpu_num:
                up["cpu"] = vm_conf.cpu_num
            if vm_conf.mem_num != vm_last.mem_num:
                up["memory"] = vm_conf.mem_num
            if vm_conf.hdd_num != vm_last.hdd_num:
                up["disk"] = vm_conf.hdd_num
            if vm_conf.speed_u != vm_last.speed_u:
                up["bandwidth_up"] = vm_conf.speed_u
            if vm_conf.speed_d != vm_last.speed_d:
                up["bandwidth_down"] = vm_conf.speed_d
            if vm_conf.flu_num != vm_last.flu_num:
                up["traffic_limit"] = vm_conf.flu_num
            # 重装系统 =========================================================
            if vm_conf.os_name != vm_last.os_name and vm_last.os_name:
                r = self.VMSetups(vm_conf)
                if not r.success:
                    return r
            # 提交配置修改 =====================================================
            if up:
                data = self._api_put(f"vm/{pid}/config", up)
                if not self._ok(data):
                    return ZMessage(
                        success=False, action="VMUpdate",
                        message=f"配置更新失败: {self._msg(data)}")
            # 网络IP绑定更新 ===================================================
            super().IPBinder(vm_last, False)
            ikuai = super().IPBinder(vm_conf, True)
            if not ikuai.success:
                logger.warning(f"路由器绑定更新失败: {ikuai.message}")
            return super().VMUpdate(vm_conf, vm_last)
        except Exception as e:
            logger.error(f"更新配置失败: {e}")
            traceback.print_exc()
            return ZMessage(
                success=False, action="VMUpdate", message=str(e))

    # 删除虚拟机 ###############################################################
    def VMDelete(self, vm_name: str, rm_back=True) -> ZMessage:
        logger.info(
            f"[{self.hs_config.server_name}] 删除虚拟机: {vm_name}")
        try:
            pid = self._vm_id(vm_name)
            vm_conf = self.vm_finds(vm_name)
            if vm_conf:
                super().IPBinder(vm_conf, False)
            data = self._api_delete(f"vm/{pid}")
            if not self._ok(data):
                return ZMessage(
                    success=False, action="VMDelete",
                    message=f"删除失败: {self._msg(data)}")
            logger.info(f"  虚拟机 {vm_name} 已删除")
            return super().VMDelete(vm_name)
        except Exception as e:
            logger.error(f"删除虚拟机失败: {e}")
            traceback.print_exc()
            return ZMessage(
                success=False, action="VMDelete", message=str(e))

    # 虚拟机电源 ###############################################################
    def VMPowers(self, vm_name: str, power: VMPowers) -> ZMessage:
        """虚拟机电源管理"""
        super().VMPowers(vm_name, power)
        try:
            pid = self._vm_id(vm_name)
            action_map = {
                VMPowers.S_START: "start",
                VMPowers.S_CLOSE: "shutdown",
                VMPowers.H_CLOSE: "stop",
                VMPowers.S_RESET: "reboot",
                VMPowers.H_RESET: "reset",
                VMPowers.A_PAUSE: "suspend",
                VMPowers.A_WAKED: "resume",
            }
            action = action_map.get(power)
            if not action:
                return ZMessage(
                    success=False, action="VMPowers",
                    message=f"不支持的电源操作: {power}")
            data = self._api_post(f"vm/{pid}/power", {"action": action})
            if not self._ok(data):
                return ZMessage(
                    success=False, action="VMPowers",
                    message=f"电源操作失败: {self._msg(data)}")
            logger.info(f"虚拟机 {vm_name} 电源 {action} 成功")
            r = ZMessage(success=True, action="VMPowers")
            self.logs_set(r)
            return r
        except Exception as e:
            logger.error(f"电源操作失败: {e}")
            traceback.print_exc()
            r = ZMessage(
                success=False, action="VMPowers", message=str(e))
            self.logs_set(r)
            return r

    # 设置虚拟机密码 ###########################################################
    def VMPasswd(self, vm_name: str, os_pass: str) -> ZMessage:
        """修改虚拟机系统密码"""
        try:
            pid = self._vm_id(vm_name)
            data = self._api_post(
                f"vm/{pid}/password", {"password": os_pass})
            if not self._ok(data):
                return ZMessage(
                    success=False, action="Password",
                    message=f"修改密码失败: {self._msg(data)}")
            vm_conf = self.vm_finds(vm_name)
            if vm_conf:
                vm_conf.os_pass = os_pass
                self.data_set()
            logger.info(f"虚拟机 {vm_name} 密码已修改")
            return ZMessage(
                success=True, action="Password", message="密码修改成功")
        except Exception as e:
            logger.error(f"修改密码失败: {e}")
            return ZMessage(
                success=False, action="Password", message=str(e))

    # 虚拟机截图 ###############################################################
    def VMScreen(self, vm_name: str = "") -> str:
        """获取虚拟机屏幕截图（base64 PNG）"""
        try:
            pid = self._vm_id(vm_name)
            data = self._api_get(f"vm/{pid}/screenshot")
            if self._ok(data):
                return data.get("data", {}).get("image", "")
        except Exception as e:
            logger.error(f"获取截图失败: {e}")
        return ""

    # VNC远程控制 ##############################################################
    def VMRemote(self, vm_uuid: str,
                 ip_addr: str = "127.0.0.1") -> ZMessage:
        """获取VNC远程控制连接路径"""
        try:
            pid = self._vm_id(vm_uuid)
            data = self._api_get(f"vm/{pid}/vnc")
            if not self._ok(data):
                return ZMessage(
                    success=False, action="VCRemote",
                    message=f"获取VNC失败: {self._msg(data)}")
            vnc = data.get("data", {})
            url = vnc.get("url", "")
            token = vnc.get("token", "")
            port = vnc.get("port", 0)
            if not url and port:
                pub = self.hs_config.public_addr[0] \
                    if self.hs_config.public_addr else ip_addr
                url = f"wss://{pub}:{port}/websockify/?token={token}"
            return ZMessage(
                success=True, action="VCRemote", message=url,
                results={"url": url, "token": token, "port": port})
        except Exception as e:
            logger.error(f"获取VNC路径失败: {e}")
            return ZMessage(
                success=False, action="VCRemote", message=str(e))

    # =========================================================================
    # ISO镜像管理
    # =========================================================================

    def ISOList(self) -> list:
        """获取可用ISO镜像目录列表"""
        try:
            data = self._api_get("iso/list")
            if self._ok(data):
                return data.get("data", {}).get("list", [])
        except Exception as e:
            logger.error(f"获取ISO列表失败: {e}")
        return []

    # ISO镜像挂载 ##############################################################
    def ISOMount(self, vm_name: str,
                 vm_imgs: IMConfig, in_flag=True) -> ZMessage:
        act = "挂载" if in_flag else "卸载"
        try:
            pid = self._vm_id(vm_name)
            if in_flag:
                data = self._api_post(f"vm/{pid}/iso/mount", {
                    "iso_file": vm_imgs.iso_file,
                    "iso_name": vm_imgs.iso_name})
            else:
                data = self._api_post(f"vm/{pid}/iso/unmount", {
                    "iso_name": vm_imgs.iso_name})
            if not self._ok(data):
                return ZMessage(
                    success=False, action="ISOMount",
                    message=f"ISO{act}失败: {self._msg(data)}")
            if in_flag:
                self.vm_saving[vm_name].iso_all[
                    vm_imgs.iso_name] = vm_imgs
            else:
                self.vm_saving[vm_name].iso_all.pop(
                    vm_imgs.iso_name, None)
            self.data_set()
            return ZMessage(
                success=True, action="ISOMount",
                message=f"ISO{act}成功")
        except Exception as e:
            logger.error(f"ISO{act}失败: {e}")
            traceback.print_exc()
            return ZMessage(
                success=False, action="ISOMount", message=str(e))

    # =========================================================================
    # 备份管理
    # =========================================================================

    # 备份虚拟机 ###############################################################
    def VMBackup(self, vm_name: str, vm_tips: str) -> ZMessage:
        try:
            pid = self._vm_id(vm_name)
            vm_conf = self.vm_finds(vm_name)
            if not vm_conf:
                return ZMessage(
                    success=False, action="VMBackup",
                    message="虚拟机不存在")
            data = self._api_post(
                f"vm/{pid}/backup", {"description": vm_tips})
            if not self._ok(data):
                return ZMessage(
                    success=False, action="VMBackup",
                    message=f"备份失败: {self._msg(data)}")
            bak_id = str(data.get("data", {}).get(
                "backup_id",
                f"{vm_name}_{datetime.datetime.now():%Y%m%d_%H%M%S}"))
            vm_conf.backups.append(VMBackup(
                backup_time=datetime.datetime.now(),
                backup_name=bak_id,
                backup_hint=vm_tips,
                old_os_name=vm_conf.os_name))
            self.data_set()
            r = ZMessage(
                success=True, action="VMBackup",
                message=f"备份成功: {bak_id}",
                results={"backup_name": bak_id})
            self.logs_set(r)
            return r
        except Exception as e:
            logger.error(f"备份失败: {e}")
            traceback.print_exc()
            return ZMessage(
                success=False, action="VMBackup", message=str(e))

    # 恢复虚拟机 ###############################################################
    def Restores(self, vm_name: str, vm_back: str) -> ZMessage:
        try:
            pid = self._vm_id(vm_name)
            vm_conf = self.vm_finds(vm_name)
            if not vm_conf:
                return ZMessage(
                    success=False, action="Restores",
                    message="虚拟机不存在")
            vb = next(
                (b for b in vm_conf.backups
                 if b.backup_name == vm_back), None)
            if not vb:
                return ZMessage(
                    success=False, action="Restores",
                    message=f"备份 {vm_back} 不存在")
            data = self._api_post(
                f"vm/{pid}/restore", {"backup_id": vm_back})
            if not self._ok(data):
                return ZMessage(
                    success=False, action="Restores",
                    message=f"恢复失败: {self._msg(data)}")
            if vb.old_os_name:
                vm_conf.os_name = vb.old_os_name
            self.data_set()
            r = ZMessage(
                success=True, action="Restores",
                message=f"恢复成功: {vm_name}")
            self.logs_set(r)
            return r
        except Exception as e:
            logger.error(f"恢复失败: {e}")
            traceback.print_exc()
            return ZMessage(
                success=False, action="Restores", message=str(e))

    # 加载备份列表 #############################################################
    def LDBackup(self, vm_back: str = "") -> ZMessage:
        """从平台同步备份列表"""
        try:
            for vm_name, vm_conf in self.vm_saving.items():
                pid = self._vm_id(vm_name)
                data = self._api_get(f"vm/{pid}/backups")
                if self._ok(data):
                    vm_conf.backups = [
                        VMBackup(
                            backup_time=bk.get("created_at", 0),
                            backup_name=str(bk.get("id", "")),
                            backup_hint=bk.get("description", ""),
                            old_os_name=bk.get("os_name", ""))
                        for bk in data.get("data", {}).get("list", [])]
            self.data_set()
            return ZMessage(
                success=True, action="LDBackup",
                message="备份列表已同步")
        except Exception as e:
            logger.error(f"加载备份列表失败: {e}")
            return ZMessage(
                success=False, action="LDBackup", message=str(e))

    # 移除备份 #################################################################
    def RMBackup(self, vm_name: str, vm_back: str = "") -> ZMessage:
        """删除指定备份"""
        try:
            pid = self._vm_id(vm_name)
            data = self._api_delete(f"vm/{pid}/backup/{vm_back}")
            if not self._ok(data):
                return ZMessage(
                    success=False, action="RMBackup",
                    message=f"删除备份失败: {self._msg(data)}")
            vm_conf = self.vm_finds(vm_name)
            if vm_conf:
                vm_conf.backups = [
                    b for b in vm_conf.backups
                    if b.backup_name != vm_back]
                self.data_set()
            return ZMessage(
                success=True, action="RMBackup", message="备份已删除")
        except Exception as e:
            logger.error(f"删除备份失败: {e}")
            return ZMessage(
                success=False, action="RMBackup", message=str(e))

    # =========================================================================
    # 硬盘管理
    # =========================================================================

    # VM镜像挂载 ###############################################################
    def HDDMount(self, vm_name: str, vm_imgs: SDConfig,
                 in_flag=True) -> ZMessage:
        act = "挂载" if in_flag else "卸载"
        try:
            pid = self._vm_id(vm_name)
            if in_flag:
                data = self._api_post(f"vm/{pid}/disk/mount", {
                    "disk_name": vm_imgs.hdd_name,
                    "disk_size": vm_imgs.hdd_size})
            else:
                data = self._api_post(f"vm/{pid}/disk/unmount", {
                    "disk_name": vm_imgs.hdd_name})
            if not self._ok(data):
                return ZMessage(
                    success=False, action="HDDMount",
                    message=f"硬盘{act}失败: {self._msg(data)}")
            if in_flag:
                vm_imgs.hdd_flag = 1
                self.vm_saving[vm_name].hdd_all[
                    vm_imgs.hdd_name] = vm_imgs
            else:
                if vm_imgs.hdd_name in self.vm_saving[vm_name].hdd_all:
                    self.vm_saving[vm_name].hdd_all[
                        vm_imgs.hdd_name].hdd_flag = 0
            self.data_set()
            return ZMessage(
                success=True, action="HDDMount",
                message=f"硬盘{act}成功")
        except Exception as e:
            logger.error(f"硬盘{act}失败: {e}")
            return ZMessage(
                success=False, action="HDDMount", message=str(e))

    # 移除磁盘 #################################################################
    def RMMounts(self, vm_name: str, vm_imgs: str) -> ZMessage:
        """彻底删除磁盘"""
        try:
            pid = self._vm_id(vm_name)
            data = self._api_delete(f"vm/{pid}/disk/{vm_imgs}")
            if not self._ok(data):
                return ZMessage(
                    success=False, action="RMMounts",
                    message=f"删除磁盘失败: {self._msg(data)}")
            self.vm_saving[vm_name].hdd_all.pop(vm_imgs, None)
            self.data_set()
            return ZMessage(
                success=True, action="RMMounts",
                message=f"磁盘 {vm_imgs} 已删除")
        except Exception as e:
            logger.error(f"删除磁盘失败: {e}")
            return ZMessage(
                success=False, action="RMMounts", message=str(e))

    # =========================================================================
    # 端口映射 (NAT)
    # =========================================================================

    def PortsMap(self, map_info: PortData, flag=True) -> ZMessage:
        """端口映射：通过青洲云API创建/删除端口转发"""
        act = "添加" if flag else "删除"
        try:
            if flag:
                if map_info.wan_port == 0:
                    from random import randint
                    used = {n.wan_port for vc in self.vm_saving.values()
                            for n in vc.nat_all}
                    p = randint(
                        self.hs_config.ports_start or 10000,
                        self.hs_config.ports_close or 60000)
                    while p in used:
                        p = randint(
                            self.hs_config.ports_start or 10000,
                            self.hs_config.ports_close or 60000)
                    map_info.wan_port = p
                data = self._api_post("nat/create", {
                    "wan_port": map_info.wan_port,
                    "lan_port": map_info.lan_port,
                    "lan_addr": map_info.lan_addr,
                    "protocol": "tcp",
                    "description": map_info.nat_tips})
            else:
                data = self._api_post("nat/delete", {
                    "wan_port": map_info.wan_port,
                    "lan_addr": map_info.lan_addr,
                    "lan_port": map_info.lan_port})
            if not self._ok(data):
                return ZMessage(
                    success=False, action="PortsMap",
                    message=f"端口{act}失败: {self._msg(data)}")
            r = ZMessage(
                success=True, action="PortsMap",
                message=f"端口{map_info.wan_port}{act}成功")
            self.data_set()
            self.logs_set(r)
            return r
        except Exception as e:
            logger.error(f"端口{act}失败: {e}")
            return ZMessage(
                success=False, action="PortsMap", message=str(e))

    # =========================================================================
    # 网站代理 (Web Proxy)
    # =========================================================================

    def ProxyMap(self, pm_info: WebProxy, vm_uuid: str,
                 in_apis, in_flag=True) -> ZMessage:
        """网站反向代理：通过青洲云API创建/删除Web代理"""
        act = "添加" if in_flag else "删除"
        try:
            vm_conf = self.vm_finds(vm_uuid)
            if not vm_conf:
                return ZMessage(
                    success=False, action="ProxyMap",
                    message="虚拟机不存在")
            pid = self._vm_id(vm_uuid)
            if in_flag:
                for w in vm_conf.web_all:
                    if w.web_addr == pm_info.web_addr:
                        return ZMessage(
                            success=False, action="ProxyMap",
                            message=f"域名 {pm_info.web_addr} 已存在")
                data = self._api_post("web/create", {
                    "vm_id": pid,
                    "domain": pm_info.web_addr,
                    "lan_addr": pm_info.lan_addr,
                    "lan_port": pm_info.lan_port,
                    "is_https": pm_info.is_https,
                    "description": pm_info.web_tips})
                if self._ok(data):
                    vm_conf.web_all.append(pm_info)
            else:
                data = self._api_post("web/delete", {
                    "domain": pm_info.web_addr, "vm_id": pid})
                if self._ok(data):
                    vm_conf.web_all = [
                        w for w in vm_conf.web_all
                        if w.web_addr != pm_info.web_addr]
            if not self._ok(data):
                return ZMessage(
                    success=False, action="ProxyMap",
                    message=f"网站{act}失败: {self._msg(data)}")
            self.data_set()
            r = ZMessage(
                success=True, action="ProxyMap",
                message=f"域名{pm_info.web_addr}{act}成功")
            self.logs_set(r)
            return r
        except Exception as e:
            logger.error(f"网站{act}失败: {e}")
            return ZMessage(
                success=False, action="ProxyMap", message=str(e))

    # =========================================================================
    # IP绑定
    # =========================================================================

    def IPBinder(self, vm_conf: VMConfig, flag=True) -> ZMessage:
        """IP绑定：通过青洲云API和爱快路由器绑定/解绑IP"""
        act = "绑定" if flag else "解绑"
        try:
            pid = self._vm_id(vm_conf.vm_uuid)
            for _, nic in vm_conf.nic_all.items():
                if not nic.ip4_addr and not nic.ip6_addr:
                    continue
                pl = {"vm_id": pid, "nic_type": nic.nic_type}
                if nic.ip4_addr:
                    pl["ipv4"] = nic.ip4_addr
                if nic.ip6_addr:
                    pl["ipv6"] = nic.ip6_addr
                if nic.mac_addr:
                    pl["mac"] = nic.mac_addr
                if nic.nic_gate:
                    pl["gateway"] = nic.nic_gate
                if nic.nic_mask:
                    pl["netmask"] = nic.nic_mask
                ep = "ip/bind" if flag else "ip/unbind"
                data = self._api_post(ep, pl)
                if not self._ok(data):
                    logger.warning(
                        f"IP{act}失败: {nic.ip4_addr} - "
                        f"{self._msg(data)}")
            # 同时调用爱快绑定 =================================================
            if self.hs_config.i_kuai_addr:
                super().IPBinder(vm_conf, flag)
            return ZMessage(
                success=True, action="IPBinder",
                message=f"IP{act}完成")
        except Exception as e:
            logger.error(f"IP{act}失败: {e}")
            return ZMessage(
                success=False, action="IPBinder", message=str(e))

    # 查找显卡(云平台不适用) ###################################################
    def PCIShows(self) -> dict[str, str]:
        return {}

    # 直通PCI ###################################################################
    def PCISetup(self, vm_name: str, config: VFConfig, pci_key: str, in_flag=True) -> ZMessage:
        # 专用操作 =============================================================
        # TODO: 增加此主机需要执行的任务
        # 通用操作 =============================================================
        return super().PCISetup(vm_name, config, pci_key, in_flag)

    # 查找USB ###################################################################
    def USBShows(self) -> dict[str, USBInfos]:
        # 专用操作 =============================================================
        # TODO: 增加此主机需要执行的任务
        # 通用操作 =============================================================
        return super().USBShows()

    # 直通USB ###################################################################
    def USBSetup(self, vm_name: str, ud_info: USBInfos, ud_keys: str, in_flag=True) -> ZMessage:
        # 专用操作 =============================================================
        # TODO: 增加此主机需要执行的任务
        # 通用操作 =============================================================
        return super().USBSetup(vm_name, ud_info, ud_keys, in_flag)

    # 磁盘移交检查 ################################################################
    def HDDCheck(self, vm_name: str, vm_imgs: SDConfig, ex_name: str) -> ZMessage:
        # 专用操作 =============================================================
        # TODO: 增加此主机需要执行的任务
        # 通用操作 =============================================================
        return super().HDDCheck(vm_name, vm_imgs, ex_name)

    # 移交所有权 ################################################################
    def HDDTrans(self, vm_name: str, vm_imgs: SDConfig, ex_name: str) -> ZMessage:
        # 专用操作 =============================================================
        # TODO: 增加此主机需要执行的任务
        # 通用操作 =============================================================
        return super().HDDTrans(vm_name, vm_imgs, ex_name)