import json
import secrets
import traceback
import threading

from loguru import logger

from HostModule.HttpManager import HttpManager
from HostServer.BasicServer import BasicServer
from MainObject.Config.HSConfig import HSConfig
from MainObject.Server.HSEngine import HEConfig
from MainObject.Config.VMConfig import VMConfig
from MainObject.Config.WebProxy import WebProxy
from MainObject.Public.ZMessage import ZMessage
from HostModule.DataManager import DataManager


class HostManage:
    # 初始化 #####################################################################
    def __init__(self):
        self.engine: dict[str, BasicServer] = {}
        self.logger: list[ZMessage] = []
        self.bearer: str = ""  # 先初始化saving变量
        self.saving = DataManager("./DataSaving/hostmanage.db")
        self.proxys: HttpManager | None = None
        # 删除 self.web_all，不再使用全局代理列表
        self.set_conf()

    # 字典化 #####################################################################
    def __save__(self):
        return {
            "engine": {
                string: server.__save__() for string, server in self.engine.items()
            },
            "logger": [
                logger.__save__() for logger in self.logger
            ],
            "bearer": self.bearer
        }

    # 加载全局配置 ###############################################################
    def set_conf(self):
        global_config = self.saving.get_ap_config()
        self.bearer = global_config.get("bearer", "")
        # 如果Token为空，自动生成一个新的Token
        if not self.bearer:
            self.bearer = secrets.token_hex(8)
            # 保存到数据库
            self.saving.set_ap_config(bearer=self.bearer)
            logger.info(f"[HostManage] 自动生成新Token: {self.bearer}")

    # 设置/重置访问Token #########################################################
    def set_pass(self, bearer: str = "") -> str:
        if bearer:
            self.bearer = bearer
        else:
            # 生成16位随机Token（包含字母和数字）
            self.bearer = secrets.token_hex(8)
        # 保存到数据库
        self.saving.set_ap_config(bearer=self.bearer)
        return self.bearer

    # 验证Token ##################################################################
    def aka_pass(self, token: str) -> bool:
        return token and token == self.bearer

    # 获取主机 ###################################################################
    def get_host(self, hs_name: str) -> BasicServer | None:
        if hs_name not in self.engine:
            return None
        return self.engine[hs_name]

    # ========================================================================
    # 添加主机
    # ========================================================================
    def add_host(self, hs_name: str, hs_type: str, hs_conf: HSConfig) -> ZMessage:
        """
        添加新主机到管理系统
        
        Args:
            hs_name: 主机名称
            hs_type: 主机类型（如VMWareSetup、LxContainer等）
            hs_conf: 主机配置对象
            
        Returns:
            ZMessage: 操作结果
        """
        try:
            # 检查主机是否已存在 ================================================
            if hs_name in self.engine:
                logger.warning(f'[添加主机] 主机已存在: {hs_name}')
                return ZMessage(success=False, message="主机已添加")
            
            # 检查主机类型是否支持 ==============================================
            if hs_type not in HEConfig:
                logger.warning(f'[添加主机] 不支持的主机类型: {hs_type}')
                return ZMessage(success=False, message="不支持的主机类型")
            
            # 设置server_name（关键！）=========================================
            hs_conf.server_name = hs_name
            logger.info(f'[添加主机] 开始添加主机: {hs_name}, 类型: {hs_type}')
            
            # 创建主机实例 ======================================================
            try:
                self.engine[hs_name] = HEConfig[hs_type]["Imported"](hs_conf, db=self.saving)
            except Exception as e:
                logger.error(f'[添加主机] 创建主机实例失败: {e}')
                traceback.print_exc()
                return ZMessage(success=False, message=f"创建主机实例失败: {str(e)}")
            
            # 初始化主机 ========================================================
            try:
                self.engine[hs_name].HSCreate()
                self.engine[hs_name].HSLoader()
            except Exception as e:
                logger.error(f'[添加主机] 初始化主机失败: {e}')
                traceback.print_exc()
                # 清理已创建的实例
                if hs_name in self.engine:
                    del self.engine[hs_name]
                return ZMessage(success=False, message=f"初始化主机失败: {str(e)}")
            
            # 保存主机配置到数据库 ==============================================
            try:
                self.saving.set_hs_config(hs_name, hs_conf)
                logger.info(f'[添加主机] 主机添加成功: {hs_name}')
            except Exception as e:
                logger.error(f'[添加主机] 保存主机配置失败: {e}')
                traceback.print_exc()
                # 不影响主要功能，记录错误即可
            
            return ZMessage(success=True, message="主机添加成功")
            
        except Exception as e:
            # 捕获所有异常 ======================================================
            logger.error(f'[添加主机] 添加主机失败: {e}')
            traceback.print_exc()
            return ZMessage(success=False, message=f"添加主机失败: {str(e)}")

    # ========================================================================
    # 删除主机
    # ========================================================================
    def del_host(self, server):
        """
        从管理系统中删除主机
        
        Args:
            server: 主机名称
            
        Returns:
            bool: 删除是否成功
        """
        try:
            # 检查主机是否存在 ==================================================
            if server not in self.engine:
                logger.warning(f'[删除主机] 主机不存在: {server}')
                return False
            
            logger.info(f'[删除主机] 开始删除主机: {server}')
            
            # 卸载主机 ==========================================================
            try:
                if hasattr(self.engine[server], 'HSUnload'):
                    self.engine[server].HSUnload()
            except Exception as e:
                logger.error(f'[删除主机] 卸载主机失败: {e}')
                traceback.print_exc()
                # 继续删除流程
            
            # 从引擎中删除主机 ==================================================
            del self.engine[server]
            
            # 从数据库删除主机配置 ==============================================
            try:
                self.saving.del_hs_config(server)
                logger.info(f'[删除主机] 主机删除成功: {server}')
            except Exception as e:
                logger.error(f'[删除主机] 删除数据库配置失败: {e}')
                traceback.print_exc()
                # 不影响主要功能，记录错误即可
            
            return True
            
        except Exception as e:
            # 捕获所有异常 ======================================================
            logger.error(f'[删除主机] 删除主机失败: {e}')
            traceback.print_exc()
            return False

    # ========================================================================
    # 修改主机配置
    # ========================================================================
    def set_host(self, hs_name: str, hs_conf: HSConfig) -> ZMessage:
        """
        修改主机配置
        
        Args:
            hs_name: 主机名称
            hs_conf: 新的主机配置对象
            
        Returns:
            ZMessage: 操作结果
        """
        try:
            # 检查主机是否存在 ==================================================
            if hs_name not in self.engine:
                logger.warning(f'[修改主机] 主机未找到: {hs_name}')
                return ZMessage(success=False, message="主机未找到")
            
            logger.info(f'[修改主机] 开始修改主机配置: {hs_name}')
            
            # 保存原有的虚拟机配置 ==============================================
            old_server = self.engine[hs_name]
            old_vm_saving = old_server.vm_saving
            
            # 设置server_name（关键！）=========================================
            hs_conf.server_name = hs_name
            
            # 重新创建主机实例 ==================================================
            try:
                self.engine[hs_name] = HEConfig[hs_conf.server_type]["Imported"](hs_conf, db=self.saving)
            except Exception as e:
                logger.error(f'[修改主机] 创建新主机实例失败: {e}')
                traceback.print_exc()
                # 恢复原有实例
                self.engine[hs_name] = old_server
                return ZMessage(success=False, message=f"创建新主机实例失败: {str(e)}")
            
            # 恢复虚拟机配置（状态数据已在数据库中）============================
            self.engine[hs_name].vm_saving = old_vm_saving
            
            # 卸载并重新加载主机 ================================================
            try:
                self.engine[hs_name].HSUnload()
                self.engine[hs_name].HSLoader()
            except Exception as e:
                logger.error(f'[修改主机] 重新加载主机失败: {e}')
                traceback.print_exc()
                # 恢复原有实例
                self.engine[hs_name] = old_server
                return ZMessage(success=False, message=f"重新加载主机失败: {str(e)}")
            
            # 保存主机配置到数据库 ==============================================
            try:
                self.saving.set_hs_config(hs_name, hs_conf)
                logger.info(f'[修改主机] 主机配置修改成功: {hs_name}')
            except Exception as e:
                logger.error(f'[修改主机] 保存主机配置失败: {e}')
                traceback.print_exc()
                # 不影响主要功能，记录错误即可
            
            return ZMessage(success=True, message="主机更新成功")
            
        except Exception as e:
            # 捕获所有异常 ======================================================
            logger.error(f'[修改主机] 修改主机失败: {e}')
            traceback.print_exc()
            return ZMessage(success=False, message=f"修改主机失败: {str(e)}")

    # ========================================================================
    # 主机电源控制（启用/禁用）
    # ========================================================================
    def pwr_host(self, hs_name: str, hs_flag: bool) -> ZMessage:
        """
        控制主机的启用/禁用状态
        
        Args:
            hs_name: 主机名称
            hs_flag: True=启用，False=禁用
            
        Returns:
            ZMessage: 操作结果
        """
        try:
            # 检查主机是否存在 ==================================================
            if hs_name not in self.engine:
                logger.warning(f'[主机电源控制] 主机未找到: {hs_name}')
                return ZMessage(success=False, message="主机未找到")
            
            server = self.engine[hs_name]
            
            # 更新主机配置的启用状态 ============================================
            if hasattr(server, 'hs_config') and server.hs_config:
                server.hs_config.enable_host = hs_flag
                logger.info(f'[主机电源控制] 主机 {hs_name} 启用状态已更新为: {hs_flag}')
            
            # 执行启用/禁用操作 ================================================
            try:
                if hs_flag:
                    # 启用主机 ====================================================
                    server.HSLoader()
                    logger.info(f'[主机电源控制] 主机 {hs_name} 已启用')
                else:
                    # 禁用主机 ====================================================
                    server.HSUnload()
                    logger.info(f'[主机电源控制] 主机 {hs_name} 已禁用')
            except Exception as e:
                logger.error(f'[主机电源控制] 执行启用/禁用操作失败: {e}')
                traceback.print_exc()
                return ZMessage(success=False, message=f"操作失败: {str(e)}")
            
            # 保存主机配置到数据库 ==============================================
            try:
                self.saving.set_hs_config(hs_name, server.hs_config)
            except Exception as e:
                logger.error(f'[主机电源控制] 保存主机配置失败: {e}')
                traceback.print_exc()
            
            return ZMessage(success=True, message=f"主机{'启用' if hs_flag else '禁用'}成功")
            
        except Exception as e:
            # 捕获所有异常 ======================================================
            logger.error(f'[主机电源控制] 修改主机状态失败: {e}')
            traceback.print_exc()
            return ZMessage(success=False, message=f"修改主机状态失败: {str(e)}")

    # ========================================================================
    # 加载信息
    # ========================================================================
    def all_load(self):
        """
        从数据库加载所有信息
        包括：全局日志、HTTP代理、主机配置、虚拟机配置等
        """
        try:
            logger.info('[加载配置] 开始加载系统配置')
            
            # 加载全局日志 ======================================================
            try:
                self.logger = []
                global_logs = self.saving.get_hs_logger()
                for log_data in global_logs:
                    self.logger.append(ZMessage(**log_data) if isinstance(log_data, dict) else log_data)
                logger.debug(f'[加载配置] 已加载 {len(self.logger)} 条全局日志')
            except Exception as e:
                logger.error(f'[加载配置] 加载全局日志失败: {e}')
                traceback.print_exc()
            
            # 启动HTTP实例 ======================================================
            try:
                self.proxys = HttpManager()
                self.proxys.config_all()
                self.proxys.launch_web()
                logger.debug('[加载配置] HTTP代理服务已启动')
            except Exception as e:
                logger.error(f'[加载配置] 启动HTTP代理服务失败: {e}')
                traceback.print_exc()
            
            # 加载所有主机配置 ==================================================
            try:
                host_configs = self.saving.all_hs_config()
                logger.debug(f'[加载配置] 找到 {len(host_configs)} 个主机配置')
                
                for host_config in host_configs:
                    try:
                        hs_name = host_config["hs_name"]
                        logger.debug(f'[加载配置] 开始加载主机: {hs_name}')
                        
                        # 重建 HSConfig 对象 ==========================================
                        hs_conf_data = dict(host_config)
                        
                        # 解析JSON字段 ============================================
                        hs_conf_data["extend_data"] = json.loads(host_config["extend_data"]) if host_config["extend_data"] else {}
                        hs_conf_data["system_maps"] = json.loads(host_config["system_maps"]) if host_config.get("system_maps") else {}
                        hs_conf_data["images_maps"] = json.loads(host_config["images_maps"]) if host_config.get("images_maps") else {}
                        hs_conf_data["public_addr"] = json.loads(host_config["public_addr"]) if host_config.get("public_addr") else []
                        hs_conf_data["server_dnss"] = json.loads(host_config["server_dnss"]) if host_config.get("server_dnss") else []
                        hs_conf_data["ipaddr_maps"] = json.loads(host_config["ipaddr_maps"]) if host_config.get("ipaddr_maps") else {}
                        hs_conf_data["ipaddr_dnss"] = json.loads(host_config["ipaddr_dnss"]) if host_config.get("ipaddr_dnss") else ["119.29.29.29", "223.5.5.5"]
                        
                        # 加载enable_host字段 ========================================
                        hs_conf_data["enable_host"] = bool(host_config.get("enable_host", 1))
                        
                        # 移除数据库字段，只保留配置字段 ============================
                        for field in ["id", "hs_name", "created_at", "updated_at"]:
                            hs_conf_data.pop(field, None)
                        
                        hs_conf = HSConfig(**hs_conf_data)
                        # 设置 server_name（关键！）=================================
                        hs_conf.server_name = hs_name
                        
                        # 获取主机完整数据 ==========================================
                        host_full_data = self.saving.get_ap_server(hs_name)
                        
                        # 转换 vm_saving 字典为 VMConfig 对象 =======================
                        vm_saving_converted = {}
                        vm_count = len(host_full_data.get("vm_saving", {}))
                        logger.info(f'[加载配置] 主机 {hs_name} 从数据库加载了 {vm_count} 个虚拟机配置')
                        
                        for vm_uuid, vm_config in host_full_data["vm_saving"].items():
                            if isinstance(vm_config, dict):
                                vm_saving_converted[vm_uuid] = VMConfig(**vm_config)
                            else:
                                vm_saving_converted[vm_uuid] = vm_config
                            logger.debug(f'[加载配置]   - 虚拟机: {vm_uuid}')
                            
                            # 创建Web代理 ==========================================
                            for web_data in vm_saving_converted[vm_uuid].web_all:
                                try:
                                    self.proxys.create_web(
                                        (web_data.lan_port, web_data.lan_addr),
                                        web_data.web_addr, is_https=web_data.is_https
                                    )
                                except Exception as e:
                                    logger.error(f'[加载配置] 创建Web代理失败: {e}')
                                    traceback.print_exc()
                        
                        # 创建 BaseServer 实例 ========================================
                        if hs_conf.server_type in HEConfig:
                            server_class = HEConfig[hs_conf.server_type]["Imported"]
                            self.engine[hs_name] = server_class(
                                hs_conf,
                                db=self.saving,
                                vm_saving=vm_saving_converted
                            )
                            
                            # 加载主机（如果启用）================================
                            enable_host = getattr(hs_conf, 'enable_host', True)
                            if enable_host:
                                try:
                                    self.engine[hs_name].HSLoader()
                                    logger.debug(f'[加载配置] 主机 {hs_name} 已加载')
                                except Exception as e:
                                    logger.error(f'[加载配置] 加载主机 {hs_name} 失败: {e}')
                                    traceback.print_exc()
                            else:
                                logger.debug(f'[加载配置] 主机 {hs_name} 已禁用，跳过加载')
                        else:
                            logger.warning(f'[加载配置] 不支持的主机类型: {hs_conf.server_type}')
                            
                    except Exception as e:
                        logger.error(f'[加载配置] 加载主机 {hs_name} 失败: {e}')
                        traceback.print_exc()
                        # 继续加载其他主机
                        
                logger.info(f'[加载配置] 系统配置加载完成，共加载 {len(self.engine)} 个主机')
                
                # 异步初始化虚拟机 ============================================
                self._async_init_vms()
                
            except Exception as e:
                logger.error(f'[加载配置] 加载主机配置失败: {e}')
                traceback.print_exc()
                
        except Exception as e:
            # 捕获所有异常 ======================================================
            logger.error(f'[加载配置] 加载数据时出错: {e}')
            traceback.print_exc()

    # ========================================================================
    # 异步初始化虚拟机
    # ========================================================================
    def _async_init_vms(self):
        """
        异步初始化所有主机的虚拟机
        在后台线程中扫描和初始化虚拟机，避免阻塞系统启动
        """
        def init_vms_thread():
            try:
                logger.info('[异步初始化] 开始异步初始化虚拟机')
                logger.info(f'[异步初始化] 当前已加载 {len(self.engine)} 个主机')
                
                # 遍历所有启用的主机
                for hs_name, server in self.engine.items():
                    try:
                        # 检查主机是否启用
                        if hasattr(server, 'hs_config') and server.hs_config:
                            enable_host = getattr(server.hs_config, 'enable_host', True)
                            if not enable_host:
                                logger.debug(f'[异步初始化] 跳过禁用的主机: {hs_name}')
                                continue
                        
                        # 记录当前虚拟机数量
                        current_vm_count = len(server.vm_saving)
                        logger.info(f'[异步初始化] 主机 {hs_name} 当前有 {current_vm_count} 个虚拟机')
                        
                        # 检查主机是否支持虚拟机扫描
                        if not hasattr(server, 'VMDetect'):
                            logger.debug(f'[异步初始化] 主机 {hs_name} 不支持虚拟机扫描')
                            continue
                        
                        logger.info(f'[异步初始化] 开始扫描主机 {hs_name} 的虚拟机')
                        
                        # 扫描虚拟机
                        result = server.VMDetect()
                        
                        if result.success:
                            new_vm_count = len(server.vm_saving)
                            logger.info(f'[异步初始化] 主机 {hs_name} 虚拟机扫描完成: {result.message}')
                            logger.info(f'[异步初始化] 主机 {hs_name} 现在有 {new_vm_count} 个虚拟机（之前 {current_vm_count} 个）')
                        else:
                            logger.warning(f'[异步初始化] 主机 {hs_name} 虚拟机扫描失败: {result.message}')
                        
                    except Exception as e:
                        logger.error(f'[异步初始化] 初始化主机 {hs_name} 的虚拟机失败: {e}')
                        traceback.print_exc()
                        # 继续处理其他主机
                
                logger.info('[异步初始化] 虚拟机异步初始化完成')
                
            except Exception as e:
                logger.error(f'[异步初始化] 异步初始化虚拟机失败: {e}')
                traceback.print_exc()
        
        # 创建并启动后台线程
        init_thread = threading.Thread(target=init_vms_thread, daemon=True, name='VMInitThread')
        init_thread.start()
        logger.info('[异步初始化] 虚拟机初始化线程已启动（后台运行）')

    # ========================================================================
    # 保存信息
    # ========================================================================
    def all_save(self) -> bool:
        """
        保存所有信息到数据库
        包括：全局日志、主机配置、虚拟机配置等
        
        Returns:
            bool: 保存是否成功
        """
        try:
            logger.debug('[保存配置] 开始保存系统配置')
            success = True
            
            # 保存全局日志 ======================================================
            try:
                if self.logger:
                    self.saving.set_hs_logger(None, self.logger)
                    logger.debug(f'[保存配置] 已保存 {len(self.logger)} 条全局日志')
            except Exception as e:
                logger.error(f'[保存配置] 保存全局日志失败: {e}')
                traceback.print_exc()
                success = False
            
            # 保存每个主机的配置数据 ============================================
            for hs_name, server in self.engine.items():
                try:
                    result = server.data_set()
                    if not result:
                        logger.warning(f'[保存配置] 主机 {hs_name} 配置保存失败')
                        success = False
                except Exception as e:
                    logger.error(f'[保存配置] 保存主机 {hs_name} 配置失败: {e}')
                    traceback.print_exc()
                    success = False
            
            # 关闭Web服务器 ====================================================
            try:
                if self.proxys is not None:
                    self.proxys.closed_web()
                    logger.debug('[保存配置] Web服务器已关闭')
            except Exception as e:
                logger.error(f'[保存配置] 关闭Web服务器失败: {e}')
                traceback.print_exc()
                # 不影响整体保存结果
            
            if success:
                logger.info('[保存配置] 系统配置保存成功')
            else:
                logger.warning('[保存配置] 系统配置保存部分失败')
            
            return success
            
        except Exception as e:
            # 捕获所有异常 ======================================================
            logger.error(f'[保存配置] 保存数据时出错: {e}')
            traceback.print_exc()
            return False

    # 退出程序 ###################################################################
    def all_exit(self):
        for server in self.engine:
            self.engine[server].HSUnload()

    # 扫描虚拟机 #################################################################
    def vms_scan(self, hs_name: str, prefix: str = "") -> ZMessage:
        """
        扫描主机上的虚拟机并保存到数据库
        :param hs_name: 主机名称
        :param prefix: 虚拟机名称前缀过滤（如果为空，则使用主机配置的filter_name）
        :return: 操作结果
        """
        if hs_name not in self.engine:
            return ZMessage(success=False, message=f"Host {hs_name} not found")

        server = self.engine[hs_name]

        # 检查主机是否启用
        enable_host = getattr(server.hs_config, 'enable_host', True) if server.hs_config else True
        if not enable_host:
            return ZMessage(success=False, message=f"主机 {hs_name} 已禁用，无法扫描虚拟机")

        # 检查是否支持VScanner方法
        if not hasattr(server, 'VScanner'):
            return ZMessage(success=False, message="Host does not support VM scanning")

        # 如果指定了prefix参数，临时修改主机配置的filter_name
        original_filter_name = None
        if prefix:
            original_filter_name = server.hs_config.filter_name if server.hs_config else None
            if server.hs_config:
                server.hs_config.filter_name = prefix

        try:
            # 调用服务器的VScanner方法
            result = server.VMDetect()
            return result
        finally:
            # 恢复原始的filter_name
            if original_filter_name is not None and server.hs_config:
                server.hs_config.filter_name = original_filter_name

    # 添加全局代理 ###################################################################
    def add_proxy(self, proxy_data: dict) -> ZMessage:
        """
        添加全局代理配置（已废弃，请使用虚拟机的代理配置）
        :param proxy_data: 代理配置数据字典
        :return: 操作结果
        """
        return ZMessage(success=False, message="此函数已废弃，请使用 admin_add_proxy 或 add_vm_proxy_config")

    # 删除全局代理 ###################################################################
    def del_proxy(self, web_addr: str) -> ZMessage:
        """
        删除全局代理配置（已废弃，请使用虚拟机的代理配置）
        :param web_addr: 代理域名
        :return: 操作结果
        """
        return ZMessage(success=False, message="此函数已废弃，请使用 admin_delete_proxy 或 delete_vm_proxy_config")

    # ========================================================================
    # 定时任务
    # ========================================================================
    def exe_cron(self):
        """
        执行定时任务
        注意：状态数据已通过 DataManage 立即保存，无需在定时任务中保存
        """
        try:
            # 遍历所有主机，执行定时任务 ==========================================
            for server_name in self.engine:
                try:
                    server = self.engine[server_name]
                    
                    # 检查主机是否启用 ============================================
                    if hasattr(server, 'hs_config') and server.hs_config:
                        enable_host = getattr(server.hs_config, 'enable_host', True)
                        if not enable_host:
                            logger.debug(f'[Cron] 跳过禁用的主机: {server_name}')
                            continue
                    
                    # 执行主机的定时任务 ==========================================
                    logger.debug(f'[Cron] 执行主机 {server_name} 的定时任务')
                    server.Crontabs()
                    
                except Exception as e:
                    # 单个主机的定时任务失败不影响其他主机 ======================
                    logger.error(f'[Cron] 主机 {server_name} 定时任务执行失败: {e}')
                    traceback.print_exc()
            
            # 清理已删除虚拟机的状态数据 ==========================================
            try:
                self._cleanup_deleted_vm_status()
            except Exception as e:
                logger.error(f'[Cron] 清理已删除虚拟机状态数据失败: {e}')
                traceback.print_exc()
            
            # 重新计算所有用户的资源配额 ==========================================
            try:
                self._recalculate_user_quotas()
            except Exception as e:
                logger.error(f'[Cron] 重新计算用户资源配额失败: {e}')
                traceback.print_exc()
            
            logger.debug('[Cron] 定时任务执行完成')
            
        except Exception as e:
            # 捕获整个定时任务的异常 ============================================
            logger.error(f'[Cron] 定时任务执行失败: {e}')
            traceback.print_exc()
    
    def _recalculate_user_quotas(self):
        """
        遍历所有虚拟机和容器，重新计算用户资源配额
        只有虚拟机/容器 own_all 列表中的第一个用户才占用配额
        """
        try:
            # 获取所有用户
            all_users = self.saving.get_all_users()
            if not all_users:
                return
            
            # 初始化所有用户的资源使用量为0
            user_resources = {}
            for user in all_users:
                user_resources[user['username']] = {
                    'user_id': user['id'],
                    'cpu': 0,
                    'ram': 0,
                    'ssd': 0,
                    'gpu': 0,
                    'traffic': 0,
                    'nat_ports': 0,
                    'web_proxy': 0,
                    'bandwidth_up': 0,
                    'bandwidth_down': 0
                }
            
            # 遍历所有主机的所有虚拟机和容器
            for server_name, server in self.engine.items():
                if not hasattr(server, 'vm_saving'):
                    continue
                
                for vm_uuid, vm_config in server.vm_saving.items():
                    # 获取虚拟机/容器的第一个所有者
                    owners = getattr(vm_config, 'own_all', [])
                    if not owners:
                        continue
                    
                    first_owner = owners[0]
                    
                    # 跳过admin用户
                    if first_owner == 'admin':
                        continue
                    
                    # 如果用户不在用户列表中，跳过
                    if first_owner not in user_resources:
                        continue
                    
                    # 累加该用户的资源使用量
                    user_resources[first_owner]['cpu'] += getattr(vm_config, 'cpu_num', 0)
                    # 虚拟机的mem_num字段单位是MB，需要转换为GB存储到用户表
                    ram_mb = getattr(vm_config, 'mem_num', 0)
                    user_resources[first_owner]['ram'] += ram_mb
                    # 虚拟机的hdd_num字段单位是MB，需要转换为GB存储到用户表
                    hdd_mb = getattr(vm_config, 'hdd_num', 0)
                    user_resources[first_owner]['ssd'] += hdd_mb
                    # 虚拟机的gpu_mem字段单位是MB，需要转换为GB存储到用户表
                    gpu_mem_mb = getattr(vm_config, 'gpu_mem', 0)
                    user_resources[first_owner]['gpu'] += gpu_mem_mb
                    # 虚拟机的flu_num字段单位是MB，需要转换为GB存储到用户表
                    flu_mb = getattr(vm_config, 'flu_num', 0)
                    user_resources[first_owner]['traffic'] += flu_mb
                    user_resources[first_owner]['nat_ports'] += getattr(vm_config, 'nat_num', 0)
                    user_resources[first_owner]['web_proxy'] += getattr(vm_config, 'web_num', 0)
                    # 虚拟机的speed_u和speed_d字段单位是Mbps，直接使用
                    user_resources[first_owner]['bandwidth_up'] += getattr(vm_config, 'speed_u', 0)
                    user_resources[first_owner]['bandwidth_down'] += getattr(vm_config, 'speed_d', 0)
            
            # 更新所有用户的资源使用量
            for username, resources in user_resources.items():
                self.saving.update_user_resource_usage(
                    resources['user_id'],
                    used_cpu=resources['cpu'],
                    used_ram=resources['ram'],
                    used_ssd=resources['ssd'],
                    used_gpu=resources['gpu'],
                    used_traffic=resources['traffic'],
                    used_nat_ports=resources['nat_ports'],
                    used_web_proxy=resources['web_proxy'],
                    used_bandwidth_up=resources['bandwidth_up'],
                    used_bandwidth_down=resources['bandwidth_down']
                )
            
            logger.debug('[Cron] 用户资源配额重新计算完成')
            
        except Exception as e:
            logger.error(f'[Cron] 重新计算用户配额失败: {e}')
            traceback.print_exc()

    def _cleanup_deleted_vm_status(self):
        """
        清理已删除虚拟机的状态数据
        遍历数据库中的vm_status表，删除不存在于vm_saving中的虚拟机状态
        """
        try:
            logger.debug('[Cron] 开始清理已删除虚拟机的状态数据')
            
            # 获取所有主机配置
            all_hosts = self.saving.all_hs_config()
            
            # 构建所有现有虚拟机的集合 (主机名, 虚拟机UUID)
            existing_vms = set()
            for host_config in all_hosts:
                hs_name = host_config['hs_name']
                vm_saving = self.saving.get_vm_saving(hs_name)
                for vm_uuid in vm_saving.keys():
                    existing_vms.add((hs_name, vm_uuid))
            
            # 获取数据库中所有虚拟机状态
            conn = self.saving.get_db_sqlite()
            try:
                cursor = conn.execute("SELECT DISTINCT hs_name, vm_uuid FROM vm_status")
                db_vms = cursor.fetchall()
                
                deleted_count = 0
                for hs_name, vm_uuid in db_vms:
                    if (hs_name, vm_uuid) not in existing_vms:
                        # 这个虚拟机不存在于vm_saving中，说明已被删除，清理其状态数据
                        if self.saving.delete_vm_status(hs_name, vm_uuid):
                            deleted_count += 1
                            logger.debug(f'[Cron] 已清理已删除虚拟机状态: 主机={hs_name}, 虚拟机={vm_uuid}')
                
                if deleted_count > 0:
                    logger.info(f'[Cron] 清理完成，共删除 {deleted_count} 个已删除虚拟机的状态数据')
                else:
                    logger.debug('[Cron] 没有需要清理的虚拟机状态数据')
                    
            finally:
                conn.close()
                
        except Exception as e:
            logger.error(f'[Cron] 清理已删除虚拟机状态数据失败: {e}')
            import traceback
            traceback.print_exc()

    def recalculate_user_quotas(self):
        """
        公共方法：手动触发用户资源配额重新计算
        可用于立即更新用户资源使用统计
        """
        logger.info('[手动] 触发用户资源配额重新计算')
        self._recalculate_user_quotas()
        logger.info('[手动] 用户资源配额重新计算完成')
