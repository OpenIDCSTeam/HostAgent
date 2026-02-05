"""
RestManage - REST API管理模块
提供主机和虚拟机管理的API接口处理函数
"""
import json
import random
import string
import traceback
from functools import wraps
from flask import request, jsonify, session, redirect, url_for
from loguru import logger
import psutil

from MainObject.Config.HSConfig import HSConfig
from MainObject.Server.HSEngine import HEConfig
from MainObject.Config.VMConfig import VMConfig
from MainObject.Config.VMPowers import VMPowers
from MainObject.Config.NCConfig import NCConfig
from MainObject.Config.PortData import PortData
from MainObject.Config.WebProxy import WebProxy
from MainObject.Public.HWStatus import HWStatus
from HostModule.UserManager import UserManager, check_host_access, check_vm_permission, check_resource_quota


class RestManager:
    """REST API管理器 - 封装所有主机和虚拟机管理的API接口"""

    def __init__(self, hs_manage, db=None):
        """
        初始化RestManager
        
        Args:
            hs_manage: 主机管理对象，用于实际的主机和虚拟机操作
            db: 数据库实例，用于用户权限检查
        """
        self.hs_manage = hs_manage
        self.db = db

    # ========================================================================
    # 认证装饰器和响应函数
    # ========================================================================

    # 过滤被禁用的字段 ##################################################################
    # :param data: 原始数据字典
    # :param server_type: 服务器类型
    # :param mode: 'init' (创建) 或 'edit' (编辑)
    # :return: 过滤后的数据
    ####################################################################################
    def _filter_banned_fields(self, data: dict, server_type: str, mode: str = 'init') -> dict:
        """
        根据服务器类型过滤掉被禁用的字段
        
        Args:
            data: 原始数据字典
            server_type: 服务器类型 (如 'VMWareSetup', 'LxContainer', 'OCInterface' 等)
            mode: 'init' 表示创建模式，使用 Ban_Init；'edit' 表示编辑模式，使用 Ban_Edit
            
        Returns:
            过滤后的数据字典
        """
        # 获取服务器配置
        server_config = HEConfig.get(server_type, {})

        # 获取要禁止的字段列表
        banned_fields = []
        if mode == 'init':
            banned_fields = server_config.get('Ban_Init', [])
        elif mode == 'edit':
            banned_fields = server_config.get('Ban_Edit', [])

        # 过滤掉被禁用的字段
        filtered_data = {}
        for key, value in data.items():
            # 跳过被禁用的字段
            if key in banned_fields:
                continue
            filtered_data[key] = value

        return filtered_data

    @staticmethod
    # 认证装饰器，检查Bearer Token或Session登录 ########################################
    # :param f: 被装饰的函数
    # :return: 装饰后的函数
    ####################################################################################
    def require_auth(self, f):

        @wraps(f)
        def decorated(*args, **kwargs):
            # 检查Bearer Token
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                token = auth_header[7:]
                if token and token == self.hs_manage.bearer:
                    return f(*args, **kwargs)
            # 检查Session登录
            if session.get('logged_in'):
                return f(*args, **kwargs)
            # API请求返回JSON错误
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'code': 401, 'msg': '未授权访问', 'data': None}), 401
            # 页面请求重定向到登录页
            return redirect(url_for('login'))

        return decorated

    # 统一API响应格式 ####################################################################
    # :param code: 响应状态码，默认为200
    # :param msg: 响应消息，默认为'success'
    # :param data: 响应数据，默认为None
    # :return: JSON格式的响应对象
    # ####################################################################################
    def api_response(self, code=200, msg='success', data=None):
        """统一API响应格式"""
        return jsonify({'code': code, 'msg': msg, 'data': data})

    def _calculate_user_ip_usage(self, username):
        """计算用户的IP使用量"""
        if not username or not self.db:
            return {'used_nat_ips': 0, 'used_pub_ips': 0}

        # 如果是admin用户，返回0（不受配额限制）
        if username == 'admin':
            return {'used_nat_ips': 0, 'used_pub_ips': 0}

        # 获取用户信息
        user_data = self.db.get_user_by_username(username)
        if not user_data:
            return {'used_nat_ips': 0, 'used_pub_ips': 0}

        # 初始化计数器
        used_nat_ips = 0
        used_pub_ips = 0

        # 遍历所有主机的虚拟机，计算该用户的IP使用量
        for hs_name, server in self.hs_manage.engine.items():
            if not server:
                continue

            # 重新加载虚拟机配置
            try:
                server.data_get()
            except Exception as e:
                logger.error(f"[IP统计] 主机 {hs_name} 加载配置失败: {e}")
                continue

            # 遍历该主机下的所有虚拟机
            for vm_uuid, vm_config in server.vm_saving.items():
                if not vm_config:
                    continue

                # 检查虚拟机的所有者列表
                owners = getattr(vm_config, 'own_all', [])
                if username in owners:
                    # 只有主用户（第一个所有者）才占用IP配额
                    if owners[0] == username:
                        # 计算该虚拟机的IP数量
                        nic_all = getattr(vm_config, 'nic_all', {})
                        for nic_name, nic_config in nic_all.items():
                            nic_type = getattr(nic_config, 'nic_type', 'nat')
                            if nic_type == 'nat':
                                used_nat_ips += 1
                            elif nic_type == 'pub':
                                used_pub_ips += 1

        return {
            'used_nat_ips': used_nat_ips,
            'used_pub_ips': used_pub_ips
        }

    def _get_current_user(self):
        """获取当前用户信息"""
        # 检查Bearer Token
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            # Token登录，返回管理员权限
            return {
                'id': 1,
                'username': 'admin',
                'is_admin': True,
                'is_token_login': True
            }

        # 检查Session登录
        if self.db and session.get('logged_in'):
            user_id = session.get('user_id')
            user_data = self.db.get_user_by_id(user_id)
            if user_data:
                user_data['is_token_login'] = False
                return user_data

        return None

    def _check_host_permission(self, hs_name):
        """检查主机访问权限"""
        user_data = self._get_current_user()
        if not user_data:
            return False, self.api_response(401, '未授权访问')

        # 管理员或Token登录有所有权限
        if user_data.get('is_admin') or user_data.get('is_token_login'):
            return True, user_data

        # 检查主机访问权限
        if not check_host_access(hs_name, user_data):
            return False, self.api_response(403, '没有访问该主机的权限')

        return True, user_data

    def _check_vm_permission(self, action, hs_name):
        """检查虚拟机操作权限"""
        has_host_perm, user_data_or_response = self._check_host_permission(hs_name)
        if not has_host_perm:
            return False, user_data_or_response

        user_data = user_data_or_response

        # 检查虚拟机操作权限
        has_perm, error_msg = check_vm_permission(action, user_data)
        if not has_perm:
            return False, self.api_response(403, error_msg)

        return True, user_data

    def _check_vm_ownership(self, hs_name, vm_uuid, user_data):
        """检查虚拟机所有权"""
        # 管理员或Token登录有所有权限
        if user_data.get('is_admin') or user_data.get('is_token_login'):
            return True, None

        server = self.hs_manage.get_host(hs_name)
        if not server:
            return False, self.api_response(404, '主机不存在')

        vm_config = server.vm_saving.get(vm_uuid)
        if not vm_config:
            return False, self.api_response(404, '虚拟机不存在')

        # 检查用户是否是虚拟机的所有者
        owners = getattr(vm_config, 'own_all', [])
        current_username = user_data.get('username', '')

        if current_username not in owners:
            return False, self.api_response(403, '没有访问该虚拟机的权限')

        return True, None

    def _check_vm_delete_permission(self, hs_name, vm_uuid, user_data):
        """检查虚拟机删除权限（普通用户只能删除自己是主用户的虚拟机）"""
        # 管理员或Token登录有所有权限
        if user_data.get('is_admin') or user_data.get('is_token_login'):
            return True, None

        server = self.hs_manage.get_host(hs_name)
        if not server:
            return False, self.api_response(404, '主机不存在')

        vm_config = server.vm_saving.get(vm_uuid)
        if not vm_config:
            return False, self.api_response(404, '虚拟机不存在')

        # 检查用户是否是虚拟机的所有者
        owners = getattr(vm_config, 'own_all', [])
        current_username = user_data.get('username', '')

        if current_username not in owners:
            return False, self.api_response(403, '没有访问该虚拟机的权限')

        # 检查用户是否是主用户（第一个所有者）
        first_owner = owners[0] if owners else None
        if current_username != first_owner:
            return False, self.api_response(403, '只有主用户可以删除虚拟机')

        return True, None

    def _check_resource_quota(self, user_data, **resources):
        """检查资源配额"""
        has_quota, error_msg = check_resource_quota(user_data, **resources)
        if not has_quota:
            return False, self.api_response(403, error_msg)
        return True, None

    def _validate_vm_resources(self, data, user_data=None, min_disk_gb=10):
        """验证虚拟机资源配置
        
        Args:
            data: 虚拟机配置数据
            user_data: 用户数据（用于配额检查）
            min_disk_gb: 最小磁盘大小（GB），默认10GB
        """
        # CPU验证：最低1核，默认2核
        cpu_num = int(data.get('cpu_num', 2))
        if cpu_num < 1:
            return self.api_response(400, 'CPU核心数不能少于1核')
        data['cpu_num'] = cpu_num

        # 内存验证：最低1G（注意单位是MB）
        mem_num = int(data.get('mem_num', 2048))  # 默认2G
        if mem_num < 1024:  # 最低1G
            return self.api_response(400, '内存不能少于1GB')
        data['mem_num'] = mem_num

        # 显存验证：最低1G（注意单位是MB）
        gpu_mem = int(data.get('gpu_mem', 0))
        # if gpu_mem < 1024 and gpu_mem > 0:  # 如果使用GPU，最低1G
        #     return self.api_response(400, 'GPU显存不能少于1GB')
        data['gpu_mem'] = gpu_mem

        # 硬盘验证：使用传入的最小磁盘要求
        hdd_num = int(data.get('hdd_num', 8192))  # 默认8G
        min_disk_mb = min_disk_gb * 1024  # 转换为MB
        if hdd_num < min_disk_mb:
            return self.api_response(400, f'硬盘大小不能少于{min_disk_gb}GB')
        data['hdd_num'] = hdd_num

        # 检查镜像要求（如果提供了镜像）
        iso_all = data.get('iso_all', {})
        if iso_all:
            # 取第一个镜像的要求（从iso_hint中解析）
            for iso_name, iso_config in iso_all.items():
                if isinstance(iso_config, dict) and 'iso_hint' in iso_config:
                    try:
                        # 假设iso_hint中包含磁盘要求，格式如"最低8G"或"8GB"
                        import re
                        hint = iso_config['iso_hint']
                        match = re.search(r'(\d+)\s*[gG][bB]?', hint)
                        if match:
                            min_hdd = int(match.group(1)) * 1024  # 转换为MB
                            if hdd_num < min_hdd:
                                return self.api_response(400, f'硬盘大小不能少于镜像最低要求{match.group(0)}')
                    except:
                        pass  # 如果解析失败，跳过镜像要求检查

        # NAT数量验证：最低1，默认10
        nat_num = int(data.get('nat_num', 10))
        if nat_num < 1:
            return self.api_response(400, 'NAT端口数量不能少于1')
        data['nat_num'] = nat_num

        # Web代理数量验证：最低0，默认10
        web_num = int(data.get('web_num', 10))
        if web_num < 0:
            return self.api_response(400, 'Web代理数量不能少于0')
        data['web_num'] = web_num

        # 流量验证：最低0
        flu_num = int(data.get('flu_num', 0))
        if flu_num < 0:
            return self.api_response(400, '流量不能少于0')
        data['flu_num'] = flu_num

        # 带宽验证：最低0
        speed_u = int(data.get('speed_u', 0))
        speed_d = int(data.get('speed_d', 0))
        if speed_u < 0:
            return self.api_response(400, '上行带宽不能少于0')
        if speed_d < 0:
            return self.api_response(400, '下行带宽不能少于0')
        data['speed_u'] = speed_u
        data['speed_d'] = speed_d

        # 如果提供了用户数据，进行配额检查
        if user_data and not (user_data.get('is_admin') or user_data.get('is_token_login')):
            # 检查CPU配额
            quota_cpu = user_data.get('quota_cpu', 0)
            used_cpu = user_data.get('used_cpu', 0)
            if quota_cpu <= 0:
                return self.api_response(400, 'CPU配额为0，不允许创建虚拟机')
            if cpu_num > (quota_cpu - used_cpu):
                return self.api_response(400, f'CPU配额不足，需要{cpu_num}核，可用{quota_cpu - used_cpu}核')

            # 检查内存配额
            quota_ram = user_data.get('quota_ram', 0)
            used_ram = user_data.get('used_ram', 0)
            if quota_ram <= 0:
                return self.api_response(400, '内存配额为0，不允许创建虚拟机')
            if mem_num > (quota_ram - used_ram):
                return self.api_response(400,
                                         f'内存配额不足，需要{mem_num // 1024}GB，可用{(quota_ram - used_ram) // 1024}GB')

            # 检查硬盘配额
            quota_ssd = user_data.get('quota_ssd', 0)
            used_ssd = user_data.get('used_ssd', 0)
            if quota_ssd <= 0:
                return self.api_response(400, '硬盘配额为0，不允许创建虚拟机')
            if hdd_num > (quota_ssd - used_ssd):
                return self.api_response(400,
                                         f'硬盘配额不足，需要{hdd_num // 1024}GB，可用{(quota_ssd - used_ssd) // 1024}GB')

            # 检查GPU配额（如果使用GPU）
            if gpu_mem > 0:
                quota_gpu = user_data.get('quota_gpu', 0)
                used_gpu = user_data.get('used_gpu', 0)
                if quota_gpu <= 0:
                    return self.api_response(400, 'GPU配额为0，不允许创建虚拟机')
                if gpu_mem > (quota_gpu - used_gpu):
                    return self.api_response(400,
                                             f'GPU显存配额不足，需要{gpu_mem // 1024}GB，可用{(quota_gpu - used_gpu) // 1024}GB')

            # 检查流量配额
            quota_traffic = user_data.get('quota_traffic', 0)
            used_traffic = user_data.get('used_traffic', 0)
            if quota_traffic <= 0:
                return self.api_response(400, '流量配额为0，不允许创建虚拟机')
            if flu_num > (quota_traffic - used_traffic):
                return self.api_response(400, f'流量配额不足，需要{flu_num}GB，可用{quota_traffic - used_traffic}GB')

            # 检查上行带宽配额
            quota_upload_bw = user_data.get('quota_bandwidth_up', 0)
            used_upload_bw = user_data.get('used_bandwidth_up', 0)
            if quota_upload_bw <= 0:
                return self.api_response(400, '上行带宽配额为0，不允许创建虚拟机')
            if speed_u > (quota_upload_bw - used_upload_bw):
                return self.api_response(400,
                                         f'上行带宽配额不足，需要{speed_u}Mbps，可用{quota_upload_bw - used_upload_bw}Mbps')

            # 检查下行带宽配额
            quota_download_bw = user_data.get('quota_bandwidth_down', 0)
            used_download_bw = user_data.get('used_bandwidth_down', 0)
            if quota_download_bw <= 0:
                return self.api_response(400, '下行带宽配额为0，不允许创建虚拟机')
            if speed_d > (quota_download_bw - used_download_bw):
                return self.api_response(400,
                                         f'下行带宽配额不足，需要{speed_d}Mbps，可用{quota_download_bw - used_download_bw}Mbps')

            # 检查NAT端口配额
            quota_nat = user_data.get('quota_nat_ports', 0)
            used_nat = user_data.get('used_nat_ports', 0)
            if quota_nat <= 0:
                return self.api_response(400, 'NAT端口配额为0，不允许创建虚拟机')
            if nat_num > (quota_nat - used_nat):
                return self.api_response(400, f'NAT端口配额不足，需要{nat_num}个，可用{quota_nat - used_nat}个')

            # 检查Web代理配额
            quota_web = user_data.get('quota_web_proxy', 0)
            used_web = user_data.get('used_web_proxy', 0)
            if quota_web <= 0:
                return self.api_response(400, 'Web代理配额为0，不允许创建虚拟机')
            if web_num > (quota_web - used_web):
                return self.api_response(400, f'Web代理配额不足，需要{web_num}个，可用{quota_web - used_web}个')

            # 检查IP配额
            quota_nat_ips = user_data.get('quota_nat_ips', 0)
            quota_pub_ips = user_data.get('quota_pub_ips', 0)

            # 使用_calculate_user_ip_usage获取准确的IP使用量
            username = user_data.get('username', '')
            ip_usage = self._calculate_user_ip_usage(username)
            used_nat_ips = ip_usage.get('used_nat_ips', 0)
            used_pub_ips = ip_usage.get('used_pub_ips', 0)

            # 计算需要的IP数量
            nic_all = data.get('nic_all', {})
            nat_ips_needed = 0
            pub_ips_needed = 0
            for nic_name, nic_conf in nic_all.items():
                nic_type = nic_conf.get('nic_type', 'nat')
                if nic_type == 'nat':
                    nat_ips_needed += 1
                elif nic_type == 'pub':
                    pub_ips_needed += 1

            # 如果没有配置网卡，根据配额默认创建
            if nat_ips_needed == 0 and pub_ips_needed == 0:
                available_nat_ips = quota_nat_ips - used_nat_ips
                available_pub_ips = quota_pub_ips - used_pub_ips

                if available_nat_ips <= 0 and available_pub_ips <= 0:
                    return self.api_response(400, '无可用IP配额，不允许创建虚拟机')

                # 优先使用内网IP，如果没有则使用公网IP
                if available_nat_ips > 0:
                    nat_ips_needed = 1
                    data['nic_all'] = {'nic0': {'nic_type': 'nat'}}
                elif available_pub_ips > 0:
                    pub_ips_needed = 1
                    data['nic_all'] = {'nic0': {'nic_type': 'pub'}}
            else:
                # 检查内网IP配额
                if nat_ips_needed > 0:
                    if quota_nat_ips <= 0:
                        return self.api_response(400, '内网IP配额为0，不允许创建虚拟机')
                    if nat_ips_needed > (quota_nat_ips - used_nat_ips):
                        return self.api_response(400,
                                                 f'内网IP配额不足，需要{nat_ips_needed}个，可用{quota_nat_ips - used_nat_ips}个')

                # 检查公网IP配额
                if pub_ips_needed > 0:
                    if quota_pub_ips <= 0:
                        return self.api_response(400, '公网IP配额为0，不允许创建虚拟机')
                    if pub_ips_needed > (quota_pub_ips - used_pub_ips):
                        return self.api_response(400,
                                                 f'公网IP配额不足，需要{pub_ips_needed}个，可用{quota_pub_ips - used_pub_ips}个')

        return None  # 验证通过

    # ========================================================================
    # 系统管理API - /api/system/<option>
    # ========================================================================

    # 重置访问令牌 ########################################################################
    # :return: 包含新token的API响应
    # ####################################################################################
    def reset_token(self):
        """重置访问Token"""
        new_token = self.hs_manage.set_pass()
        return self.api_response(200, 'Token已重置', {'token': new_token})

    # 设置访问令牌 ########################################################################
    # :return: 包含设置token的API响应
    # ####################################################################################
    def set_token(self):
        """设置指定Token"""
        data = request.get_json() or {}
        new_token = data.get('token', '')
        result = self.hs_manage.set_pass(new_token)
        return self.api_response(200, 'Token已设置', {'token': result})

    # 获取访问令牌 ########################################################################
    # :return: 包含当前token的API响应
    # ####################################################################################
    def get_token(self):
        """获取当前Token"""
        return self.api_response(200, 'success', {'token': self.hs_manage.bearer})

    # 获取引擎类型 ########################################################################
    # :return: 包含支持的主机引擎类型列表的API响应
    # ####################################################################################
    def get_engine_types(self):
        """获取支持的主机引擎类型"""
        import platform

        # 获取当前系统平台和架构
        current_system = platform.system()
        current_arch = platform.machine()

        # 平台映射
        platform_map = {
            'Windows': 'Windows',
            'Linux': 'Linux',
            'Darwin': 'MacOS'
        }
        current_platform = platform_map.get(current_system, current_system)

        # 架构映射
        arch_map = {
            'AMD64': 'x86_64',
            'x86_64': 'x86_64',
            'aarch64': 'aarch64',
            'arm64': 'aarch64'
        }
        current_cpu_arch = arch_map.get(current_arch, current_arch)

        types_data = {}
        for engine_type, config in HEConfig.items():
            # 检查是否启用
            if not config.get('isEnable', False):
                continue

            # 如果isRemote为False，需要检查平台和架构是否匹配
            is_remote = config.get('isRemote', False)
            if not is_remote:
                supported_platforms = config.get('Platform', [])
                supported_archs = config.get('CPU_Arch', [])

                # 检查平台是否匹配
                if current_platform not in supported_platforms:
                    continue

                # 检查架构是否匹配
                if current_cpu_arch not in supported_archs:
                    continue

            types_data[engine_type] = {
                'name': engine_type,
                'description': config.get('Descript', ''),
                'enabled': config.get('isEnable', False),
                'platform': config.get('Platform', []),
                'arch': config.get('CPU_Arch', []),
                'is_remote': is_remote,
                'options': config.get('Optional', {}),
                'messages': config.get('Messages', [])
            }

        # 返回当前系统信息和可用的引擎类型
        return self.api_response(200, 'success', {
            'current_platform': current_platform,
            'current_arch': current_cpu_arch,
            'engine_types': types_data
        })

    # 保存系统配置 ########################################################################
    # :return: 保存结果的API响应
    # ####################################################################################
    def save_system(self):
        """保存系统配置"""
        if self.hs_manage.all_save():
            return self.api_response(200, '配置已保存')
        return self.api_response(500, '保存失败')

    # 加载系统配置 ########################################################################
    # :return: 加载结果的API响应或布尔值
    # ####################################################################################
    def load_system(self, return_api_response=True):
        """加载系统配置"""
        try:
            self.hs_manage.all_load()
            if return_api_response:
                return self.api_response(200, '配置已加载')
            return True
        except Exception as e:
            if return_api_response:
                return self.api_response(500, f'加载失败: {str(e)}')
            return False

    # 获取系统统计 ########################################################################
    # :return: 包含系统统计信息的API响应
    # ####################################################################################
    def get_system_stats(self):
        """获取系统统计信息"""
        total_vms = 0
        running_vms = 0

        for server in self.hs_manage.engine.values():
            total_vms += len(server.vm_saving)

            # 获取所有虚拟机状态
            all_vm_status = server.save_data.get_vm_status(server.hs_config.server_name)

            # 统计运行中的虚拟机数量
            for vm_uuid in server.vm_saving.keys():
                vm_status_list = all_vm_status.get(vm_uuid, [])
                if vm_status_list:
                    # 获取最新的状态
                    latest_status = vm_status_list[-1]
                    if latest_status.get('ac_status') == 1:  # VMPowers.STARTED = 0x1 = 1
                        running_vms += 1

        return self.api_response(200, 'success', {
            'host_count': len(self.hs_manage.engine),
            'vm_count': total_vms,
            'running_vm_count': running_vms
        })

    # 获取日志记录 ########################################################################
    # :return: 包含日志记录列表的API响应
    # ####################################################################################
    def get_logs(self):
        """获取日志记录"""
        try:
            hs_name = request.args.get('hs_name')
            limit = int(request.args.get('limit', 100))

            # 使用 DataManage 的 get_hs_logger 函数获取日志
            logs = self.hs_manage.saving.get_hs_logger(hs_name)

            # 处理日志数据并限制数量
            processed_logs = []
            for log_data in logs[:limit]:
                processed_log = {
                    'id': '',  # 可以添加rowid但暂时为空
                    'actions': log_data.get('actions', ''),
                    'message': log_data.get('message', '无消息内容'),
                    'success': log_data.get('success', True),
                    'results': log_data.get('results', {}),
                    'execute': log_data.get('execute', None),
                    'level': log_data.get('level', 'ERROR' if not log_data.get('success', True) else 'INFO'),
                    'timestamp': log_data.get('created_at'),
                    'host': hs_name or '系统',
                    'created_at': log_data.get('created_at')
                }
                processed_logs.append(processed_log)

            return self.api_response(200, '获取日志成功', processed_logs)
        except Exception as e:
            return self.api_response(500, f'获取日志失败: {str(e)}')

    # 获取任务记录 ########################################################################
    # :return: 包含任务记录列表的API响应
    # ####################################################################################
    def get_tasks(self):
        """获取任务记录"""
        try:
            hs_name = request.args.get('hs_name')
            limit = int(request.args.get('limit', 100))

            if not hs_name:
                return self.api_response(400, '主机名称不能为空')

            # 使用 DataManage 的 get_vm_tasker 函数获取任务
            tasks = self.hs_manage.saving.get_vm_tasker(hs_name)

            # 限制数量并返回
            limited_tasks = tasks[:limit]
            return self.api_response(200, '获取任务成功', limited_tasks)
        except Exception as e:
            return self.api_response(500, f'获取任务失败: {str(e)}')

    # ========================================================================
    # 主机管理API - /api/server/<option>/<key?>
    # ========================================================================

    # 获取主机列表 ########################################################################
    # :return: 包含所有主机信息的API响应
    # ####################################################################################
    def get_hosts(self):
        """获取所有主机列表"""
        hosts_data = {}
        for hs_name, server in self.hs_manage.engine.items():
            # 获取主机启用状态
            is_enabled = getattr(server.hs_config, 'is_enabled', True) if server.hs_config else True
            hosts_data[hs_name] = {
                'name': hs_name,
                'type': server.hs_config.server_type if server.hs_config else '',
                'addr': server.hs_config.server_addr if server.hs_config else '',
                'config': server.hs_config.__save__() if server.hs_config else {},
                'vm_count': len(server.vm_saving),
                'status': 'active' if is_enabled else 'disabled',  # 根据is_enabled返回状态
                'is_enabled': is_enabled  # 添加is_enabled字段
            }
        return self.api_response(200, 'success', hosts_data)

    # 获取主机详情 ########################################################################
    # :param hs_name: 主机名称
    # :return: 包含单个主机详细信息的API响应
    # ####################################################################################
    def get_host(self, hs_name):
        """获取单个主机详情"""
        server = self.hs_manage.get_host(hs_name)
        if not server:
            return self.api_response(404, '主机不存在')

        # 检查是否需要详细信息（通过查询参数控制）
        include_status = request.args.get('status', 'false').lower() == 'true'

        # 构建基础响应数据（快速获取）
        host_data = {
            'name': hs_name,
            'type': server.hs_config.server_type if server.hs_config else '',
            'addr': server.hs_config.server_addr if server.hs_config else '',
            'config': server.hs_config.__save__() if server.hs_config else {},
            'vm_count': len(server.vm_saving),
            'vm_list': list(server.vm_saving.keys()),
            'last_updated': getattr(server, '_status_cache_time', 0)
        }

        # 只有明确要求时才获取状态信息（避免每次调用都执行耗时的系统检查）
        if include_status:
            try:
                cached_status = getattr(server, '_status_cache', None)
                cache_time = getattr(server, '_status_cache_time', 0)

                # 检查缓存是否有效（30秒内的数据认为是新鲜的）
                import time
                current_time = int(time.time())
                if cached_status and (current_time - cache_time) < 30:
                    host_data['status'] = cached_status
                    host_data['status_source'] = 'cached'
                else:
                    # 获取新状态并缓存
                    status_obj = server.HSStatus()
                    if status_obj:
                        host_data['status'] = status_obj.__save__()
                        host_data['status_source'] = 'fresh'
                        # 缓存状态数据
                        server._status_cache = status_obj.__save__()
                        server._status_cache_time = current_time
                    else:
                        host_data['status'] = {}
                        host_data['status_source'] = 'unavailable'
            except Exception as e:
                host_data['status'] = {}
                host_data['status_source'] = 'error'
                host_data['status_error'] = str(e)
        else:
            host_data['status'] = None
            host_data['status_note'] = 'Use ?status=true to get detailed host status'

        return self.api_response(200, 'success', host_data)

    def get_os_images(self, hs_name):
        """获取主机的操作系统镜像列表（普通用户可访问）"""
        server = self.hs_manage.get_host(hs_name)
        if not server:
            return self.api_response(404, '主机不存在')

        # 获取system_maps和images_maps
        system_maps = {}
        images_maps = {}
        server_type = ''
        ban_init = []
        ban_edit = []
        messages = []

        if server.hs_config:
            if hasattr(server.hs_config, 'system_maps'):
                system_maps = server.hs_config.system_maps or {}
            if hasattr(server.hs_config, 'images_maps'):
                images_maps = server.hs_config.images_maps or {}
            if hasattr(server.hs_config, 'server_type'):
                server_type = server.hs_config.server_type or ''

        # 获取Ban_Init、Ban_Edit和Tab_Lock
        from MainObject.Server.HSEngine import HEConfig
        if server_type:
            server_config = HEConfig.get(server_type, {})
            ban_init = server_config.get('Ban_Init', [])
            ban_edit = server_config.get('Ban_Edit', [])
            messages = server_config.get('Messages', [])
            tab_lock = server_config.get('Tab_Lock', [])
        else:
            tab_lock = []

        # 获取filter_name用于UUID前缀
        filter_name = ''
        if server.hs_config and hasattr(server.hs_config, 'filter_name'):
            filter_name = server.hs_config.filter_name or ''

        return self.api_response(200, 'success', {
            'host_name': hs_name,
            'server_type': server_type,
            'filter_name': filter_name,
            'system_maps': system_maps,
            'images_maps': images_maps,
            'ban_init': ban_init,
            'ban_edit': ban_edit,
            'messages': messages,
            'tab_lock': tab_lock
        })

    # 添加主机 ########################################################################
    # :return: 主机添加结果的API响应
    # ####################################################################################
    def add_host(self):
        """添加主机"""
        data = request.get_json() or {}
        hs_name = data.get('name', '')
        hs_type = data.get('type', '')

        if not hs_name or not hs_type:
            return self.api_response(400, '主机名称和类型不能为空')

        # 构建配置
        config_data = data.get('config', {})
        config_data['server_type'] = hs_type

        # 调试日志：打印images_maps
        logger.debug(f"[add_host] 接收到的config_data.images_maps: {config_data.get('images_maps')}")
        logger.debug(f"[add_host] images_maps类型: {type(config_data.get('images_maps'))}")

        hs_conf = HSConfig(**config_data)
        hs_conf.server_name = hs_name  # 设置server_name，确保save_data能正常工作

        # 调试日志：打印HSConfig对象的images_maps
        logger.debug(f"[add_host] HSConfig.images_maps: {hs_conf.images_maps}")
        logger.debug(f"[add_host] HSConfig.images_maps类型: {type(hs_conf.images_maps)}")

        result = self.hs_manage.add_host(hs_name, hs_type, hs_conf)

        if result.success:
            self.hs_manage.all_save()
            return self.api_response(200, result.message)
        return self.api_response(400, result.message)

    # 修改主机配置 ########################################################################
    # :param hs_name: 主机名称
    # :return: 主机配置修改结果的API响应
    # ####################################################################################
    def update_host(self, hs_name):
        """修改主机配置"""
        data = request.get_json() or {}
        config_data = data.get('config', {})

        if not config_data:
            return self.api_response(400, '配置不能为空')

        hs_conf = HSConfig(**config_data)
        result = self.hs_manage.set_host(hs_name, hs_conf)

        if result.success:
            self.hs_manage.all_save()
            return self.api_response(200, result.message)
        return self.api_response(400, result.message)

    # 删除主机 ########################################################################
    # :param hs_name: 主机名称
    # :return: 主机删除结果的API响应
    # ####################################################################################
    def delete_host(self, hs_name):
        """删除主机"""
        if self.hs_manage.del_host(hs_name):
            self.hs_manage.all_save()
            return self.api_response(200, '主机已删除')
        return self.api_response(404, '主机不存在')

    # ========================================================================
    # 主机启用控制（启用/禁用）
    # ========================================================================
    # :param hs_name: 主机名称
    # :return: 主机启用控制结果的API响应
    # ========================================================================
    def host_enable(self, hs_name):
        """
        主机启用控制（启用/禁用）
        
        Args:
            hs_name: 主机名称
            
        Returns:
            API响应，包含操作结果
        """
        try:
            # 获取请求数据 ======================================================
            data = request.get_json() or {}
            enable = data.get('enable', True)
            
            logger.info(f'[主机启用控制] 主机: {hs_name}, 操作: {"启用" if enable else "禁用"}')
            
            # 调用HostManager执行启用/禁用操作 ==================================
            result = self.hs_manage.pwr_host(hs_name, enable)
            
            # 保存配置 ==========================================================
            if result.success:
                try:
                    self.hs_manage.all_save()
                    logger.info(f'[主机启用控制] 主机 {hs_name} 配置已保存')
                except Exception as e:
                    logger.error(f'[主机启用控制] 保存配置失败: {e}')
                    traceback.print_exc()
                    return self.api_response(500, f'操作成功但保存配置失败: {str(e)}')
                
                return self.api_response(200, result.message)
            else:
                logger.warning(f'[主机启用控制] 操作失败: {result.message}')
                return self.api_response(400, result.message)
                
        except Exception as e:
            # 捕获所有异常 ======================================================
            logger.error(f'[主机启用控制] 主机启用控制失败: {e}')
            traceback.print_exc()
            return self.api_response(500, f'主机启用控制失败: {str(e)}')

    # 获取主机状态 ########################################################################
    # :param hs_name: 主机名称
    # :return: 包含主机状态的API响应
    # ####################################################################################
    def get_host_status(self, hs_name):
        """获取主机状态"""
        server = self.hs_manage.get_host(hs_name)
        if not server:
            return self.api_response(404, '主机不存在')

        # 检查是否强制刷新缓存
        force_refresh = request.args.get('refresh', 'false').lower() == 'true'

        import time
        current_time = int(time.time())
        cache_time = getattr(server, '_status_cache_time', 0)
        cached_status = getattr(server, '_status_cache', None)

        # 检查缓存是否有效（600秒内的数据认为是新鲜的）
        if not force_refresh and cached_status and (current_time - cache_time) < 600:
            return self.api_response(200, 'success', {
                'status': cached_status,
                'source': 'cached',
                'cached_at': cache_time,
                'age_seconds': current_time - cache_time
            })

        # 如果没有缓存且不强制刷新，返回空状态
        if not force_refresh and not cached_status:
            return self.api_response(200, 'success', {
                'status': {},
                'source': 'no_data',
                'message': '暂无主机状态数据，请等待定时任务更新'
            })

        # 获取新状态（仅在强制刷新时）
        try:
            status = server.HSStatus()
            if status:
                status_data = status.__save__()
                # 更新缓存
                server._status_cache = status_data
                server._status_cache_time = current_time

                return self.api_response(200, 'success', {
                    'status': status_data,
                    'source': 'fresh' if force_refresh else 'auto_refreshed',
                    'cached_at': current_time,
                    'cache_duration': 60
                })
            else:
                return self.api_response(500, 'failed', {
                    'message': '无法获取主机状态',
                    'source': 'error'
                })
        except Exception as e:
            return self.api_response(500, 'failed', {
                'message': f'获取主机状态时出错: {str(e)}',
                'source': 'error'
            })

    # ========================================================================
    # 虚拟机管理API - /api/client/<option>/<key?>
    # ========================================================================

    # 获取虚拟机列表 ########################################################################
    # :param hs_name: 主机名称
    # :return: 包含主机下所有虚拟机信息的API响应
    # ####################################################################################
    def get_vms(self, hs_name):
        """获取主机下所有虚拟机"""
        server = self.hs_manage.get_host(hs_name)
        if not server:
            return self.api_response(404, '主机不存在')

        # 从数据库重新加载数据
        server.data_get()

        # 获取当前用户信息
        user_data = UserManager.get_current_user_from_session()
        is_admin = user_data.get('is_admin', False) if user_data else False
        is_token_login = user_data.get('is_token_login', False) if user_data else False
        current_username = user_data.get('username', '') if user_data else ''

        def serialize_obj(obj):
            """将对象序列化为可JSON化的格式"""
            if obj is None:
                return None
            if isinstance(obj, (str, int, float, bool)):
                return obj
            if isinstance(obj, dict):
                return {k: serialize_obj(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [serialize_obj(item) for item in obj]
            # 检查是否为函数对象
            if callable(obj):
                return f"<function: {getattr(obj, '__name__', 'unknown')}>"
            # 尝试调用__save__()方法
            if hasattr(obj, '__save__') and callable(obj.__save__):
                try:
                    return obj.__save__()
                except (TypeError, AttributeError):
                    pass
            # 尝试使用vars()获取属性字典
            try:
                return {k: serialize_obj(v) for k, v in vars(obj).items()}
            except (TypeError, AttributeError):
                return str(obj)

        vms_data = {}
        for vm_uuid, vm_config in server.vm_saving.items():
            # 权限过滤：普通用户只能看到自己拥有的虚拟机
            if not (is_admin or is_token_login):
                owners = getattr(vm_config, 'own_all', [])
                if current_username not in owners:
                    continue  # 跳过不属于当前用户的虚拟机
            # 从 DataManage 获取状态（直接从数据库读取）=================
            status = None
            if server.save_data and server.hs_config.server_name:
                all_vm_status = server.save_data.get_vm_status(server.hs_config.server_name)
                status = all_vm_status.get(vm_uuid, [])
                # 只取最新的一条状态
                if status and len(status) > 0:
                    status = [status[-1]]
            vms_data[vm_uuid] = {
                'uuid': vm_uuid,
                'config': serialize_obj(vm_config),
                'status': serialize_obj(status)
            }

        return self.api_response(200, 'success', vms_data)

    # 获取虚拟机详情 ########################################################################
    # :param hs_name: 主机名称
    # :param vm_uuid: 虚拟机UUID
    # :return: 包含单个虚拟机详细信息的API响应
    # ####################################################################################
    def get_vm(self, hs_name, vm_uuid):
        """获取单个虚拟机详情"""
        server = self.hs_manage.get_host(hs_name)
        if not server:
            return self.api_response(404, '主机不存在')

        vm_config = server.vm_saving.get(vm_uuid)
        if not vm_config:
            return self.api_response(404, '虚拟机不存在')

        # 权限验证：普通用户只能访问自己拥有的虚拟机
        user_data = UserManager.get_current_user_from_session()
        is_admin = user_data.get('is_admin', False) if user_data else False
        is_token_login = user_data.get('is_token_login', False) if user_data else False
        current_username = user_data.get('username', '') if user_data else ''

        if not (is_admin or is_token_login):
            owners = getattr(vm_config, 'own_all', [])
            if current_username not in owners:
                return self.api_response(403, '没有访问该虚拟机的权限')

        # 如果vm_config已经是字典则直接使用，否则调用__save__()方法
        if isinstance(vm_config, dict):
            config_data = vm_config
        elif hasattr(vm_config, '__save__') and callable(getattr(vm_config, '__save__', None)):
            config_data = vm_config.__save__()
        else:
            config_data = vm_config if vm_config else {}

        return self.api_response(200, 'success', {
            'uuid': vm_uuid,
            'config': config_data
        })

    # 获取虚拟机详情 ########################################################################
    # :param hs_name: 主机名称
    # :return: 虚拟机创建结果的API响应
    # ####################################################################################
    def create_vm(self, hs_name):
        """创建虚拟机"""
        # 检查主机访问权限
        has_host_perm, user_data_or_response = self._check_host_permission(hs_name)
        if not has_host_perm:
            return user_data_or_response

        user_data = user_data_or_response

        # 检查创建虚拟机权限
        has_vm_perm, user_data_or_response = self._check_vm_permission('create', hs_name)
        if not has_vm_perm:
            return user_data_or_response

        user_data = user_data_or_response

        server = self.hs_manage.get_host(hs_name)
        if not server:
            return self.api_response(404, '主机不存在')

        data = request.get_json() or {}

        # 获取system_maps，确定最小磁盘要求
        min_disk_gb = 10  # 默认10GB
        system_maps = {}
        if server.hs_config and hasattr(server.hs_config, 'system_maps'):
            system_maps = server.hs_config.system_maps or {}

        # 根据选择的操作系统获取最小磁盘要求
        # system_maps结构：{"Ubuntu22.04": ["ubuntu-22.04.iso", 20], ...}
        # [0]是镜像文件名，[1]是最小磁盘GB
        os_name = data.get('os_name', '')
        if os_name and os_name in system_maps:
            system_map = system_maps[os_name]
            if isinstance(system_map, list) and len(system_map) >= 2:
                try:
                    min_disk_gb = int(system_map[1])  # system_map[1]是最小磁盘大小（GB）
                except (ValueError, TypeError):
                    min_disk_gb = 10  # 解析失败使用默认值

        # 验证和设置资源限制（包含配额检查），传入最小磁盘要求
        validation_result = self._validate_vm_resources(data, user_data, min_disk_gb=min_disk_gb)
        if validation_result:
            return validation_result

        # 映射os_name为实际文件名
        original_os_name = data.get('os_name', '')
        if original_os_name and original_os_name in system_maps:
            system_map = system_maps[original_os_name]
            if isinstance(system_map, list) and len(system_map) >= 1:
                data['os_name'] = system_map[0]  # 获取映射的实际文件名

        # 根据服务器类型过滤被禁用的字段（创建模式 - Ban_Init）
        if server.hs_config and hasattr(server.hs_config, 'server_type'):
            server_type = server.hs_config.server_type
            data = self._filter_banned_fields(data, server_type, mode='init')

        # 处理网卡配置
        nic_all = {}
        nic_data = data.pop('nic_all', {})
        for nic_name, nic_conf in nic_data.items():
            nic_all[nic_name] = NCConfig(**nic_conf)
        # 创建虚拟机配置
        vm_config = VMConfig(**data, nic_all=nic_all)

        # 如果没有指定虚拟机名称，生成随机名称
        if not vm_config.vm_uuid or vm_config.vm_uuid == '':
            # 获取主机配置的前缀
            prefix = ''
            if server.hs_config and hasattr(server.hs_config, 'filter_name'):
                prefix = server.hs_config.filter_name or ''

            # 如果没有配置前缀，使用默认前缀 'vmx-'
            if not prefix:
                prefix = 'vmx-'
            elif not prefix.endswith('-'):
                # 如果前缀不以 '-' 结尾，添加 '-'
                prefix = prefix + '-'

            # 生成格式: <前缀><8位随机字符>
            random_suffix = ''.join(
                random.sample(string.ascii_letters + string.digits, 8))
            vm_config.vm_uuid = f'{prefix}{random_suffix}'

        # 设置虚拟机所有者
        if not (user_data.get('is_admin') or user_data.get('is_token_login')):
            # 普通用户创建虚拟机，设置所有者为用户名
            username = user_data.get('username', '')
            if username:
                vm_config.own_all = [username]
            else:
                # 如果没有用户名，保持默认值["admin"]
                pass
        else:
            # 管理员或token登录创建虚拟机，保持默认所有者["admin"]
            pass

        vm_config.vc_port = random.randint(10000, 59999)
        if vm_config.vc_pass == '':
            vm_config.vc_pass = ''.join(
                random.sample(string.ascii_letters + string.digits, 8))

        result = server.VMCreate(vm_config)

        # 如果创建成功，更新虚拟机第一个所有者的资源使用量
        if result and result.success:
            # 获取虚拟机的第一个所有者
            first_owner = vm_config.own_all[0] if vm_config.own_all else None

            # 计算资源使用量（使用vm_config的实际值，而不是data）
            cpu_needed = vm_config.cpu_num
            ram_needed = vm_config.mem_num
            ssd_needed = vm_config.hdd_num
            gpu_needed = vm_config.gpu_mem
            traffic_needed = vm_config.flu_num
            nat_ports_needed = vm_config.nat_num
            web_proxy_needed = vm_config.web_num
            bandwidth_up_needed = vm_config.speed_u
            bandwidth_down_needed = vm_config.speed_d

            # 计算IP数量（使用vm_config的nic_all）
            nat_ips_count = 0
            pub_ips_count = 0
            for nic_name, nic_conf in vm_config.nic_all.items():
                nic_type = getattr(nic_conf, 'nic_type', 'nat')
                if nic_type == 'nat':
                    nat_ips_count += 1
                elif nic_type == 'pub':
                    pub_ips_count += 1

            # 只有第一个所有者才占用配额（跳过admin用户）
            if first_owner and first_owner != 'admin':
                owner_user = self.db.get_user_by_username(first_owner)
                if owner_user:
                    self.db.update_user_resource_usage(
                        owner_user['id'],
                        used_cpu=owner_user.get('used_cpu', 0) + cpu_needed,
                        used_ram=owner_user.get('used_ram', 0) + ram_needed,
                        used_ssd=owner_user.get('used_ssd', 0) + ssd_needed,
                        used_gpu=owner_user.get('used_gpu', 0) + gpu_needed,
                        used_traffic=owner_user.get('used_traffic', 0) + traffic_needed,
                        used_nat_ports=owner_user.get('used_nat_ports', 0) + nat_ports_needed,
                        used_web_proxy=owner_user.get('used_web_proxy', 0) + web_proxy_needed,
                        used_bandwidth_up=owner_user.get('used_bandwidth_up', 0) + bandwidth_up_needed,
                        used_bandwidth_down=owner_user.get('used_bandwidth_down', 0) + bandwidth_down_needed
                        # 注意：IP使用量通过_calculate_user_ip_usage函数实时计算，无需在数据库中维护
                    )

        self.hs_manage.all_save()
        return self.api_response(200 if result and result.success else 400, result.message)

    # 修改虚拟机配置 ########################################################################
    # :param hs_name: 主机名称
    # :param vm_uuid: 虚拟机UUID
    # :return: 虚拟机配置修改结果的API响应
    # ####################################################################################
    def update_vm(self, hs_name, vm_uuid):
        """修改虚拟机配置"""
        # 检查主机访问权限
        has_host_perm, user_data_or_response = self._check_host_permission(hs_name)
        if not has_host_perm:
            return user_data_or_response

        user_data = user_data_or_response

        # 检查修改虚拟机权限
        has_vm_perm, user_data_or_response = self._check_vm_permission('modify', hs_name)
        if not has_vm_perm:
            return user_data_or_response

        user_data = user_data_or_response

        # 检查虚拟机所有权
        has_ownership, error_response = self._check_vm_ownership(hs_name, vm_uuid, user_data)
        if not has_ownership:
            return error_response

        server = self.hs_manage.get_host(hs_name)
        if not server:
            return self.api_response(404, '主机不存在')

        # 获取旧的虚拟机配置
        old_vm_config = None
        old_resource_usage = {'cpu': 0, 'ram': 0, 'ssd': 0, 'gpu': 0, 'traffic': 0, 'nat_ports': 0, 'web_proxy': 0,
                              'bandwidth_up': 0, 'bandwidth_down': 0, 'nat_ips': 0, 'pub_ips': 0}
        vm_owners = []
        if hasattr(server, 'vm_saving') and vm_uuid in server.vm_saving:
            old_vm_config = server.vm_saving[vm_uuid]
            if hasattr(old_vm_config, '__dict__'):
                old_resource_usage = {
                    'cpu': getattr(old_vm_config, 'cpu_num', 0),
                'ram': getattr(old_vm_config, 'mem_num', 0),
                    'ssd': getattr(old_vm_config, 'hdd_num', 0),
                    'gpu': getattr(old_vm_config, 'gpu_mem', 0),
                    'traffic': getattr(old_vm_config, 'flu_num', 0),
                    'nat_ports': getattr(old_vm_config, 'nat_num', 0),
                    'web_proxy': getattr(old_vm_config, 'web_num', 0),
                    'bandwidth_up': getattr(old_vm_config, 'speed_u', 0),
                    'bandwidth_down': getattr(old_vm_config, 'speed_d', 0),
                    'nat_ips': 0,
                    'pub_ips': 0
                }
                # 计算旧配置的IP数量
                old_nic_all = getattr(old_vm_config, 'nic_all', {})
                for nic_name, nic_conf in old_nic_all.items():
                    nic_type = getattr(nic_conf, 'nic_type', 'nat')
                    if nic_type == 'nat':
                        old_resource_usage['nat_ips'] += 1
                    elif nic_type == 'pub':
                        old_resource_usage['pub_ips'] += 1
                # 获取虚拟机的所有所有者
                vm_owners = getattr(old_vm_config, 'own_all', [])

        data = request.get_json() or {}
        data['vm_uuid'] = vm_uuid

        # 检查资源配额（非管理员用户）
        if not (user_data.get('is_admin') or user_data.get('is_token_login')):
            # 计算资源变化
            cpu_change = int(data.get('cpu_num', 0)) - old_resource_usage['cpu']
            ram_change = int(data.get('mem_num', 0)) - old_resource_usage['ram']
            ssd_change = int(data.get('hdd_num', 0)) - old_resource_usage['ssd']
            gpu_change = int(data.get('gpu_mem', 0)) - old_resource_usage['gpu']
            traffic_change = int(data.get('flu_num', 0)) - old_resource_usage['traffic']
            nat_ports_change = int(data.get('nat_num', 0)) - old_resource_usage.get('nat_ports', 0)
            web_proxy_change = int(data.get('web_num', 0)) - old_resource_usage.get('web_proxy', 0)
            bandwidth_up_change = int(data.get('speed_u', 0)) - old_resource_usage.get('bandwidth_up', 0)
            bandwidth_down_change = int(data.get('speed_d', 0)) - old_resource_usage.get('bandwidth_down', 0)

            # 计算IP数量变化
            nic_all = data.get('nic_all', {})
            new_nat_ips = 0
            new_pub_ips = 0
            for nic_name, nic_conf in nic_all.items():
                nic_type = nic_conf.get('nic_type', 'nat')
                if nic_type == 'nat':
                    new_nat_ips += 1
                elif nic_type == 'pub':
                    new_pub_ips += 1

            nat_ips_change = new_nat_ips - old_resource_usage.get('nat_ips', 0)
            pub_ips_change = new_pub_ips - old_resource_usage.get('pub_ips', 0)

            # 如果资源增加，检查配额
            if any(change > 0 for change in [cpu_change, ram_change, ssd_change, gpu_change, traffic_change,
                                             nat_ports_change, web_proxy_change, bandwidth_up_change,
                                             bandwidth_down_change,
                                             nat_ips_change, pub_ips_change]):
                has_quota, error_response = self._check_resource_quota(
                    user_data,
                    cpu=max(0, cpu_change),
                    ram=max(0, ram_change),
                    ssd=max(0, ssd_change),
                    gpu=max(0, gpu_change),
                    traffic=max(0, traffic_change),
                    nat_ports=max(0, nat_ports_change),
                    web_proxy=max(0, web_proxy_change),
                    bandwidth_up=max(0, bandwidth_up_change),
                    bandwidth_down=max(0, bandwidth_down_change),
                    nat_ips=max(0, nat_ips_change),
                    pub_ips=max(0, pub_ips_change)
                )
                if not has_quota:
                    return error_response

        # 处理网卡配置
        nic_all = {}
        nic_data = data.pop('nic_all', {})
        for nic_name, nic_conf in nic_data.items():
            nic_all[nic_name] = NCConfig(**nic_conf)

        # 根据服务器类型过滤被禁用的字段（编辑模式 - Ban_Edit）
        if server.hs_config and hasattr(server.hs_config, 'server_type'):
            server_type = server.hs_config.server_type
            data = self._filter_banned_fields(data, server_type, mode='edit')

        vm_config = VMConfig(**data, nic_all=nic_all)

        result = server.VMUpdate(vm_config, old_vm_config)

        # 如果更新成功，更新第一个所有者（排除admin）的资源使用量
        if result and result.success and vm_owners:
            # 使用vm_config的实际值计算资源变化
            cpu_change = vm_config.cpu_num - old_resource_usage['cpu']
            ram_change = vm_config.mem_num - old_resource_usage['ram']
            ssd_change = vm_config.hdd_num - old_resource_usage['ssd']
            gpu_change = vm_config.gpu_mem - old_resource_usage['gpu']
            traffic_change = vm_config.flu_num - old_resource_usage['traffic']
            nat_ports_change = vm_config.nat_num - old_resource_usage.get('nat_ports', 0)
            web_proxy_change = vm_config.web_num - old_resource_usage.get('web_proxy', 0)
            bandwidth_up_change = vm_config.speed_u - old_resource_usage.get('bandwidth_up', 0)
            bandwidth_down_change = vm_config.speed_d - old_resource_usage.get('bandwidth_down', 0)

            # 计算IP数量变化（使用vm_config的nic_all）
            new_nat_ips = 0
            new_pub_ips = 0
            for nic_name, nic_conf in vm_config.nic_all.items():
                nic_type = getattr(nic_conf, 'nic_type', 'nat')
                if nic_type == 'nat':
                    new_nat_ips += 1
                elif nic_type == 'pub':
                    new_pub_ips += 1

            nat_ips_change = new_nat_ips - old_resource_usage.get('nat_ips', 0)
            pub_ips_change = new_pub_ips - old_resource_usage.get('pub_ips', 0)

            # 只更新第一个所有者的配额（跳过admin用户）
            first_owner = vm_owners[0] if vm_owners else None
            if first_owner and first_owner != 'admin':
                # 根据用户名查询用户信息
                owner_user = self.db.get_user_by_username(first_owner)
                if owner_user:
                    self.db.update_user_resource_usage(
                        owner_user['id'],
                        used_cpu=owner_user.get('used_cpu', 0) + cpu_change,
                        used_ram=owner_user.get('used_ram', 0) + ram_change,
                        used_ssd=owner_user.get('used_ssd', 0) + ssd_change,
                        used_gpu=owner_user.get('used_gpu', 0) + gpu_change,
                        used_traffic=owner_user.get('used_traffic', 0) + traffic_change,
                        used_nat_ports=owner_user.get('used_nat_ports', 0) + nat_ports_change,
                        used_web_proxy=owner_user.get('used_web_proxy', 0) + web_proxy_change,
                        used_bandwidth_up=owner_user.get('used_bandwidth_up', 0) + bandwidth_up_change,
                        used_bandwidth_down=owner_user.get('used_bandwidth_down', 0) + bandwidth_down_change
                        # 注意：IP使用量通过_calculate_user_ip_usage函数实时计算，无需在数据库中维护
                    )

        if result and result.success:
            self.hs_manage.all_save()
            return self.api_response(200, result.message if result.message else '虚拟机更新成功')

        return self.api_response(400, result.message if result else '更新失败')

    # 删除虚拟机 ########################################################################
    # :param hs_name: 主机名称
    # :param vm_uuid: 虚拟机UUID
    # :return: 虚拟机删除结果的API响应
    # ####################################################################################
    def delete_vm(self, hs_name, vm_uuid):
        """删除虚拟机"""
        # 检查主机访问权限
        has_host_perm, user_data_or_response = self._check_host_permission(hs_name)
        if not has_host_perm:
            return user_data_or_response

        user_data = user_data_or_response

        # 检查删除虚拟机权限
        has_vm_perm, user_data_or_response = self._check_vm_permission('delete', hs_name)
        if not has_vm_perm:
            return user_data_or_response

        user_data = user_data_or_response

        # 检查虚拟机删除权限（普通用户只能删除自己是主用户的虚拟机）
        has_delete_perm, error_response = self._check_vm_delete_permission(hs_name, vm_uuid, user_data)
        if not has_delete_perm:
            return error_response

        server = self.hs_manage.get_host(hs_name)
        if not server:
            return self.api_response(404, '主机不存在')

        # 获取虚拟机配置以便释放资源
        vm_resource_usage = {'cpu': 0, 'ram': 0, 'ssd': 0, 'gpu': 0, 'traffic': 0, 'nat_ports': 0, 'web_proxy': 0,
                             'bandwidth_up': 0, 'bandwidth_down': 0, 'nat_ips': 0, 'pub_ips': 0}
        vm_owners = []
        if hasattr(server, 'vm_saving') and vm_uuid in server.vm_saving:
            vm_config = server.vm_saving[vm_uuid]
            if hasattr(vm_config, '__dict__'):
                vm_resource_usage = {
                    'cpu': getattr(vm_config, 'cpu_num', 0),
                'ram': getattr(vm_config, 'mem_num', 0),
                    'ssd': getattr(vm_config, 'hdd_num', 0),
                    'gpu': getattr(vm_config, 'gpu_mem', 0),
                    'traffic': getattr(vm_config, 'flu_num', 0),
                    'nat_ports': getattr(vm_config, 'nat_num', 0),
                    'web_proxy': getattr(vm_config, 'web_num', 0),
                    'bandwidth_up': getattr(vm_config, 'speed_u', 0),
                    'bandwidth_down': getattr(vm_config, 'speed_d', 0),
                    'nat_ips': 0,
                    'pub_ips': 0
                }
                # 计算IP数量
                nic_all = getattr(vm_config, 'nic_all', {})
                for nic_name, nic_conf in nic_all.items():
                    nic_type = getattr(nic_conf, 'nic_type', 'nat')
                    if nic_type == 'nat':
                        vm_resource_usage['nat_ips'] += 1
                    elif nic_type == 'pub':
                        vm_resource_usage['pub_ips'] += 1
                # 获取虚拟机的所有所有者
                vm_owners = getattr(vm_config, 'own_all', [])

        result = server.VMDelete(vm_uuid)

        # 如果删除成功，从数据库删除虚拟机状态数据
        if result and result.success and server.save_data:
            if hasattr(server.save_data, 'delete_vm_status'):
                delete_status_result = server.save_data.delete_vm_status(hs_name, vm_uuid)
                if delete_status_result:
                    logger.info(f"已从数据库删除虚拟机 {vm_uuid} 的状态数据")
                else:
                    logger.warning(f"删除虚拟机 {vm_uuid} 状态数据失败")
            else:
                logger.warning("save_data 对象不支持 delete_vm_status 方法")

        # 如果删除成功，释放第一个所有者（排除admin）的资源使用量
        if result and result.success and vm_owners:
            # 只释放第一个所有者的配额（跳过admin用户）
            first_owner = vm_owners[0] if vm_owners else None
            if first_owner and first_owner != 'admin':
                # 根据用户名查询用户信息
                owner_user = self.db.get_user_by_username(first_owner)
                if owner_user:
                    self.db.update_user_resource_usage(
                        owner_user['id'],
                        used_cpu=owner_user.get('used_cpu', 0) - vm_resource_usage['cpu'],
                        used_ram=owner_user.get('used_ram', 0) - vm_resource_usage['ram'],
                        used_ssd=owner_user.get('used_ssd', 0) - vm_resource_usage['ssd'],
                        used_gpu=owner_user.get('used_gpu', 0) - vm_resource_usage['gpu'],
                        used_traffic=owner_user.get('used_traffic', 0) - vm_resource_usage['traffic'],
                        used_nat_ports=owner_user.get('used_nat_ports', 0) - vm_resource_usage['nat_ports'],
                        used_web_proxy=owner_user.get('used_web_proxy', 0) - vm_resource_usage['web_proxy'],
                        used_bandwidth_up=owner_user.get('used_bandwidth_up', 0) - vm_resource_usage['bandwidth_up'],
                        used_bandwidth_down=owner_user.get('used_bandwidth_down', 0) - vm_resource_usage[
                            'bandwidth_down']
                        # 注意：IP使用量通过_calculate_user_ip_usage函数实时计算，无需在数据库中维护
                    )

        if result and result.success:
            self.hs_manage.all_save()
            return self.api_response(200, result.message if result.message else '虚拟机已删除')

        return self.api_response(400, result.message if result else '操作失败')

    # 获取虚拟机所有者列表 ########################################################################
    # :param hs_name: 主机名称
    # :param vm_uuid: 虚拟机UUID
    # :return: 包含虚拟机所有者列表的API响应
    # ####################################################################################
    def get_vm_owners(self, hs_name, vm_uuid):
        """获取虚拟机的所有者列表"""
        server = self.hs_manage.get_host(hs_name)
        if not server:
            return self.api_response(404, '主机不存在')

        vm_config = server.vm_saving.get(vm_uuid)
        if not vm_config:
            return self.api_response(404, '虚拟机不存在')

        owners = getattr(vm_config, 'own_all', [])

        # 获取每个所有者的详细信息
        owner_details = []
        for username in owners:
            user = self.db.get_user_by_username(username)
            if user:
                owner_details.append({
                    'username': username,
                    'email': user.get('email', ''),
                    'is_admin': user.get('is_admin', False)
                })
            else:
                # 用户不存在（可能是admin或已删除的用户）
                owner_details.append({
                    'username': username,
                    'email': '',
                    'is_admin': username == 'admin'
                })

        return self.api_response(200, 'success', {'owners': owner_details})

    # 添加虚拟机所有者 ########################################################################
    # :param hs_name: 主机名称
    # :param vm_uuid: 虚拟机UUID
    # :return: 添加所有者结果的API响应
    # ####################################################################################
    def add_vm_owner(self, hs_name, vm_uuid):
        """添加虚拟机所有者"""
        data = request.get_json() or {}
        username = data.get('username', '').strip()

        if not username:
            return self.api_response(400, '用户名不能为空')

        # 检查用户是否存在
        user = self.db.get_user_by_username(username)
        if not user and username != 'admin':
            return self.api_response(404, '用户不存在')

        server = self.hs_manage.get_host(hs_name)
        if not server:
            return self.api_response(404, '主机不存在')

        vm_config = server.vm_saving.get(vm_uuid)
        if not vm_config:
            return self.api_response(404, '虚拟机不存在')

        owners = getattr(vm_config, 'own_all', [])
        if username in owners:
            return self.api_response(400, '用户已经是所有者')

        owners.append(username)
        vm_config.own_all = owners

        # 注意：只有第一个所有者才占用配额，添加其他所有者不影响配额

        self.hs_manage.all_save()
        return self.api_response(200, '添加成功')

    # 删除虚拟机所有者 ########################################################################
    # :param hs_name: 主机名称
    # :param vm_uuid: 虚拟机UUID
    # :return: 删除所有者结果的API响应
    # ####################################################################################
    def remove_vm_owner(self, hs_name, vm_uuid):
        """删除虚拟机所有者"""
        data = request.get_json() or {}
        username = data.get('username', '').strip()

        if not username:
            return self.api_response(400, '用户名不能为空')

        server = self.hs_manage.get_host(hs_name)
        if not server:
            return self.api_response(404, '主机不存在')

        vm_config = server.vm_saving.get(vm_uuid)
        if not vm_config:
            return self.api_response(404, '虚拟机不存在')

        owners = getattr(vm_config, 'own_all', [])
        if username not in owners:
            return self.api_response(400, '用户不是所有者')

        # 不允许删除第一个所有者（主所有者）
        if len(owners) > 0 and owners[0] == username:
            return self.api_response(400, '不能删除主所有者（第一个所有者）')

        # 如果只有一个所有者，不允许删除
        if len(owners) <= 1:
            return self.api_response(400, '至少需要保留一个所有者')

        owners.remove(username)
        vm_config.own_all = owners

        # 注意：只有第一个所有者才占用配额，删除其他所有者不影响配额
        # 而且第一个所有者已经被禁止删除了

        self.hs_manage.all_save()
        return self.api_response(200, '删除成功')

    # 移交虚拟机所有权 ########################################################################
    # :param hs_name: 主机名称
    # :param vm_uuid: 虚拟机UUID
    # :return: 移交所有权结果的API响应
    # ####################################################################################
    def transfer_vm_ownership(self, hs_name, vm_uuid):
        """移交虚拟机所有权"""
        data = request.get_json() or {}
        new_owner = data.get('new_owner', '').strip()
        keep_access = data.get('keep_access', False)
        confirm_transfer = data.get('confirm_transfer', False)

        # 参数验证
        if not new_owner:
            return self.api_response(400, '新所有者用户名不能为空')

        if not confirm_transfer:
            return self.api_response(400, '必须确认移交所有权')

        # 获取当前用户信息 - 从session中获取认证用户
        current_username = session.get('username', '')

        # 检查主机是否存在
        server = self.hs_manage.get_host(hs_name)
        if not server:
            return self.api_response(404, '主机不存在')

        # 检查虚拟机是否存在
        vm_config = server.vm_saving.get(vm_uuid)
        if not vm_config:
            return self.api_response(404, '虚拟机不存在')

        # 检查当前用户是否是主所有者（第一个所有者）
        owners = getattr(vm_config, 'own_all', [])
        if not owners or owners[0] != current_username:
            return self.api_response(403, '只有主所有者可以移交虚拟机所有权')

        # 检查新用户是否存在
        new_user = self.db.get_user_by_username(new_owner)
        if not new_user and new_owner != 'admin':
            return self.api_response(404, f'用户 "{new_owner}" 不存在')

        # 检查新所有者是否具有该主机的访问权限（admin用户除外）
        if new_owner != 'admin':
            if not check_host_access(hs_name, new_user):
                return self.api_response(403, f'移交失败：新所有者 "{new_owner}" 没有访问主机 "{hs_name}" 的权限')

        # 检查新所有者的资源配额
        resource_usage = {
            'cpu': getattr(vm_config, 'cpu_num', 0),
                'ram': getattr(vm_config, 'mem_num', 0),
            'ssd': getattr(vm_config, 'hdd_num', 0),
            'gpu': getattr(vm_config, 'gpu_mem', 0),
            'traffic': getattr(vm_config, 'flu_num', 0),
            'nat_ports': getattr(vm_config, 'nat_num', 0),
            'web_proxy': getattr(vm_config, 'web_num', 0),
            'bandwidth_up': getattr(vm_config, 'speed_u', 0),
            'bandwidth_down': getattr(vm_config, 'speed_d', 0),
            'nat_ips': 0,
            'pub_ips': 0
        }

        # 计算IP数量
        nic_all = getattr(vm_config, 'nic_all', {})
        for nic_name, nic_conf in nic_all.items():
            nic_type = getattr(nic_conf, 'nic_type', 'nat')
            if nic_type == 'nat':
                resource_usage['nat_ips'] += 1
            elif nic_type == 'pub':
                resource_usage['pub_ips'] += 1

        # 检查新所有者配额是否足够（管理员用户不受限制）
        if new_owner != 'admin':
            has_quota, quota_error_msg = self._check_resource_quota(new_user, **resource_usage)
            if not has_quota:
                return self.api_response(400, f'移交失败：新所有者资源配额不足 - {quota_error_msg}')

        # 调用Transfer函数移交所有权
        result = server.Transfer(vm_uuid, new_owner, keep_access)
        if not result.success:
            return self.api_response(500, f'移交失败: {result.message}')

        # 保存配置
        self.hs_manage.all_save()

        # 处理资源配额变更
        try:
            # 如果不保留原所有者权限，需要调整资源配额
            if not keep_access:
                old_owner_user = self.db.get_user_by_username(current_username)
                new_owner_user = self.db.get_user_by_username(new_owner)

                if old_owner_user and new_owner_user:
                    # 获取虚拟机资源使用情况
                    resource_usage = {
                        'cpu': getattr(vm_config, 'cpu_num', 0),
                'ram': getattr(vm_config, 'mem_num', 0),
                        'ssd': getattr(vm_config, 'hdd_num', 0),
                        'gpu': getattr(vm_config, 'gpu_mem', 0),
                        'traffic': getattr(vm_config, 'flu_num', 0),
                        'nat_ports': getattr(vm_config, 'nat_num', 0),
                        'web_proxy': getattr(vm_config, 'web_num', 0),
                        'bandwidth_up': getattr(vm_config, 'speed_u', 0),
                        'bandwidth_down': getattr(vm_config, 'speed_d', 0),
                        'nat_ips': 0,
                        'pub_ips': 0
                    }

                    # 计算IP数量
                    nic_all = getattr(vm_config, 'nic_all', {})
                    for nic_name, nic_conf in nic_all.items():
                        nic_type = getattr(nic_conf, 'nic_type', 'nat')
                        if nic_type == 'nat':
                            resource_usage['nat_ips'] += 1
                        elif nic_type == 'pub':
                            resource_usage['pub_ips'] += 1

                    # 从原所有者配额中扣除
                    self.db.update_user_resource_usage(
                        old_owner_user['id'],
                        used_cpu=old_owner_user.get('used_cpu', 0) - resource_usage['cpu'],
                        used_ram=old_owner_user.get('used_ram', 0) - resource_usage['ram'],
                        used_ssd=old_owner_user.get('used_ssd', 0) - resource_usage['ssd'],
                        used_gpu=old_owner_user.get('used_gpu', 0) - resource_usage['gpu'],
                        used_traffic=old_owner_user.get('used_traffic', 0) - resource_usage['traffic'],
                        used_nat_ports=old_owner_user.get('used_nat_ports', 0) - resource_usage['nat_ports'],
                        used_web_proxy=old_owner_user.get('used_web_proxy', 0) - resource_usage['web_proxy'],
                        used_bandwidth_up=old_owner_user.get('used_bandwidth_up', 0) - resource_usage['bandwidth_up'],
                        used_bandwidth_down=old_owner_user.get('used_bandwidth_down', 0) - resource_usage[
                            'bandwidth_down']
                        # 注意：IP使用量通过_calculate_user_ip_usage函数实时计算，无需在数据库中维护
                    )

                    # 添加到新所有者配额中
                    self.db.update_user_resource_usage(
                        new_owner_user['id'],
                        used_cpu=new_owner_user.get('used_cpu', 0) + resource_usage['cpu'],
                        used_ram=new_owner_user.get('used_ram', 0) + resource_usage['ram'],
                        used_ssd=new_owner_user.get('used_ssd', 0) + resource_usage['ssd'],
                        used_gpu=new_owner_user.get('used_gpu', 0) + resource_usage['gpu'],
                        used_traffic=new_owner_user.get('used_traffic', 0) + resource_usage['traffic'],
                        used_nat_ports=new_owner_user.get('used_nat_ports', 0) + resource_usage['nat_ports'],
                        used_web_proxy=new_owner_user.get('used_web_proxy', 0) + resource_usage['web_proxy'],
                        used_bandwidth_up=new_owner_user.get('used_bandwidth_up', 0) + resource_usage['bandwidth_up'],
                        used_bandwidth_down=new_owner_user.get('used_bandwidth_down', 0) + resource_usage[
                            'bandwidth_down']
                        # 注意：IP使用量通过_calculate_user_ip_usage函数实时计算，无需在数据库中维护
                    )
        except Exception as e:
            logger.error(f"更新资源配额失败: {str(e)}")
            # 不影响主要功能，记录错误即可

        return self.api_response(200, f'虚拟机所有权已成功移交给 {new_owner}')

    # 虚拟机密码修改 ########################################################################
    # :param hs_name: 主机名称
    # :param vm_uuid: 虚拟机UUID
    # :return: 虚拟机密码修改结果的API响应
    # ####################################################################################
    def vm_password(self, hs_name, vm_uuid):
        """修改虚拟机密码"""
        # 检查主机访问权限
        has_host_perm, user_data_or_response = self._check_host_permission(hs_name)
        if not has_host_perm:
            return user_data_or_response

        user_data = user_data_or_response

        # 检查虚拟机操作权限
        has_vm_perm, user_data_or_response = self._check_vm_permission('modify', hs_name)
        if not has_vm_perm:
            return user_data_or_response

        user_data = user_data_or_response

        # 检查虚拟机所有权
        has_ownership, error_response = self._check_vm_ownership(hs_name, vm_uuid, user_data)
        if not has_ownership:
            return error_response

        server = self.hs_manage.get_host(hs_name)
        if not server:
            return self.api_response(404, '主机不存在')

        data = request.get_json() or {}
        new_password = data.get('password', '').strip()

        # 验证新密码是否提供
        if not new_password:
            return self.api_response(400, '新密码不能为空')
        # vm_conf = server.VMSelect(vm_uuid)
        # if not vm_conf:
        #     return self.api_response(404, '虚拟机不存在')
        result = server.VMPasswd(vm_uuid, new_password)
        if result and result.success:
            self.hs_manage.all_save()
            return self.api_response(200, result.message if result.message else '密码修改成功')

        return self.api_response(400, result.message if result else '密码修改失败')

    # 虚拟机控制台 ######################################################################
    # :param hs_name: 主机名称
    # :param vm_uuid: 虚拟机UUID
    # :return: 虚拟机电源控制结果的API响应
    # ####################################################################################
    def vm_power(self, hs_name, vm_uuid):
        """虚拟机电源控制"""
        # 检查主机访问权限
        has_host_perm, user_data_or_response = self._check_host_permission(hs_name)
        if not has_host_perm:
            return user_data_or_response

        user_data = user_data_or_response

        # 检查虚拟机操作权限
        has_vm_perm, user_data_or_response = self._check_vm_permission('power', hs_name)
        if not has_vm_perm:
            return user_data_or_response

        user_data = user_data_or_response

        # 检查虚拟机所有权
        has_ownership, error_response = self._check_vm_ownership(hs_name, vm_uuid, user_data)
        if not has_ownership:
            return error_response

        server = self.hs_manage.get_host(hs_name)
        if not server:
            return self.api_response(404, '主机不存在')

        data = request.get_json() or {}
        action = data.get('action', 'start')

        # 映射操作到VMPowers枚举
        power_map = {
            'start': VMPowers.S_START,
            'stop': VMPowers.S_CLOSE,
            'hard_stop': VMPowers.H_CLOSE,
            'reset': VMPowers.S_RESET,
            'hard_reset': VMPowers.H_RESET,
            'pause': VMPowers.A_PAUSE,
            'resume': VMPowers.A_WAKED
        }

        power_action = power_map.get(action)
        if not power_action:
            return self.api_response(400, f'不支持的操作: {action}')

        result = server.VMPowers(vm_uuid, power_action)

        if result and result.success:
            return self.api_response(200, result.message if result.message else f'电源操作 {action} 成功')

        return self.api_response(400, result.message if result else '操作失败')

    # 获取虚拟机VNC控制台URL ########################################################################
    # :param hs_name: 主机名称
    # :param vm_uuid: 虚拟机UUID
    # :return: 包含VNC控制台URL的API响应
    # ####################################################################################
    def vm_console(self, hs_name, vm_uuid):
        """获取虚拟机VNC控制台URL"""
        # 检查主机访问权限
        has_host_perm, user_data_or_response = self._check_host_permission(hs_name)
        if not has_host_perm:
            return user_data_or_response

        user_data = user_data_or_response

        # 检查虚拟机所有权
        has_ownership, error_response = self._check_vm_ownership(hs_name, vm_uuid, user_data)
        if not has_ownership:
            return error_response

        server = self.hs_manage.get_host(hs_name)
        if not server:
            return self.api_response(404, '主机不存在')
        try:
            result = server.VMRemote(vm_uuid)
            if not result.success:
                return self.api_response(400, result.message)
            console_url = result.message
            logger.info(f"[VNC控制台地址] {console_url}")
            if console_url:
                return self.api_response(200, '获取成功', console_url)
            return self.api_response(400, '无法获取VNC控制台地址')
        except Exception as e:
            traceback.print_exc()
            return self.api_response(500, f'获取VNC控制台失败: {str(e)}')

    # 获取虚拟机截图 ########################################################################
    # :param hs_name: 主机名称
    # :param vm_uuid: 虚拟机UUID
    # :return: 包含BASE64格式截图的API响应
    # ####################################################################################
    def vm_screenshot(self, hs_name, vm_uuid):
        """获取虚拟机截图"""
        # 检查主机访问权限
        has_host_perm, user_data_or_response = self._check_host_permission(hs_name)
        if not has_host_perm:
            return user_data_or_response

        user_data = user_data_or_response

        # 检查虚拟机所有权
        has_ownership, error_response = self._check_vm_ownership(hs_name, vm_uuid, user_data)
        if not has_ownership:
            return error_response

        server = self.hs_manage.get_host(hs_name)
        if not server:
            return self.api_response(404, '主机不存在')
        
        try:
            # 调用VMScreen方法获取BASE64格式的截图
            screenshot_base64 = server.VMScreen(vm_uuid)
            
            if screenshot_base64:
                logger.info(f"[虚拟机截图] 成功获取 {hs_name}/{vm_uuid} 的截图")
                return self.api_response(200, '获取截图成功', {'screenshot': screenshot_base64})
            else:
                logger.warning(f"[虚拟机截图] 无法获取 {hs_name}/{vm_uuid} 的截图")
                return self.api_response(400, '无法获取虚拟机截图，可能虚拟机未运行或不支持截图功能')
        except Exception as e:
            logger.error(f"[虚拟机截图] 获取截图时出错: {str(e)}")
            traceback.print_exc()
            return self.api_response(500, f'获取虚拟机截图失败: {str(e)}')

    # 获取虚拟机状态 ########################################################################
    # :param hs_name: 主机名称
    # :param vm_uuid: 虚拟机UUID
    # :return: 包含虚拟机状态的API响应
    # ####################################################################################
    def get_vm_status(self, hs_name, vm_uuid):
        """获取虚拟机状态"""
        server = self.hs_manage.get_host(hs_name)
        if not server:
            return self.api_response(404, '主机不存在')

        # 从请求参数中获取时间范围（分钟数，默认30分钟）
        time_range_minutes = request.args.get('limit', type=int, default=30)

        # 计算时间戳范围
        import time
        import inspect
        current_timestamp = int(time.time())
        start_timestamp = current_timestamp - (time_range_minutes * 60)  # 转换为秒

        # 检查VMStatus方法是否支持时间戳参数
        vm_status_sig = inspect.signature(server.VMStatus)
        if 'start_timestamp' in vm_status_sig.parameters:
            # 支持时间戳参数的服务器（如BasicServer）
            status_dict = server.VMStatus(vm_uuid, s_t=start_timestamp, e_t=current_timestamp)
        else:
            # 不支持时间戳参数的服务器（如Workstation, OCInterface等）
            status_dict = server.VMStatus(vm_uuid)

        # VMStatus返回dict[str, list[HWStatus]]，需要将每个HWStatus对象转换为字典
        if vm_uuid not in status_dict:
            return self.api_response(404, '虚拟机不存在')

        # 处理HWStatus列表
        status_list = status_dict[vm_uuid]

        result = []
        if status_list:
            for hw_status in status_list:
                if hw_status is not None:
                    # 检查是否已经是字典类型
                    if isinstance(hw_status, dict):
                        result.append(hw_status)
                    else:
                        # 如果是HWStatus对象，调用__save__()方法转换为字典
                        try:
                            result.append(hw_status.__save__())
                        except (TypeError, AttributeError):
                            # 如果__save__()失败，尝试使用vars()
                            result.append(vars(hw_status))
                else:
                    result.append(None)
        return self.api_response(200, 'success', result)

    # 扫描主机上的虚拟机 ########################################################################
    # :param hs_name: 主机名称
    # :return: 虚拟机扫描结果的API响应
    # ####################################################################################
    def scan_vms(self, hs_name):
        """扫描主机上的虚拟机"""
        server = self.hs_manage.get_host(hs_name)
        if server:
            # 扫描前先从数据库重新加载数据
            server.data_get()

        data = request.get_json() or {}
        prefix = data.get('prefix', '')  # 前缀过滤，为空则使用主机配置的filter_name

        result = self.hs_manage.vms_scan(hs_name, prefix)

        if result.success:
            # 保存系统配置
            self.hs_manage.all_save()
            return self.api_response(200, result.message, result.results)

        return self.api_response(400, result.message)

    # 虚拟机上报状态数据 ########################################################################
    # :return: 虚拟机状态上报结果的API响应（无需认证）
    # ####################################################################################
    def vm_upload(self):
        """虚拟机上报状态数据（无需认证）"""
        # 获取MAC地址参数
        mac_addr = request.args.get('nic', '')
        if not mac_addr:
            return self.api_response(400, 'MAC地址参数缺失')

        # 获取上报的状态数据
        status_data = request.get_json() or {}
        if not status_data:
            return self.api_response(400, '状态数据为空')

        logger.info(f"[虚拟机上报] 收到MAC地址: {mac_addr}")

        # 遍历所有主机，查找匹配MAC地址的虚拟机
        found = False
        for hs_name, server in self.hs_manage.engine.items():
            if not server:
                continue

            # 从数据库重新加载虚拟机配置
            try:
                server.data_get()
                # logger.info(f"[虚拟机上报] 主机 {hs_name} 已加载 {len(server.vm_saving)} 个虚拟机配置")
            except Exception as e:
                logger.error(f"[虚拟机上报] 主机 {hs_name} 加载配置失败: {e}")
                continue

            # 遍历该主机下的所有虚拟机配置
            for vm_uuid, vm_config in server.vm_saving.items():
                # 处理vm_config可能是字典或VMConfig对象的情况
                nic_all = vm_config.nic_all if hasattr(vm_config, 'nic_all') else vm_config.get('nic_all', {})

                logger.debug(f"[虚拟机上报] 检查虚拟机 {vm_uuid}, 网卡数量: {len(nic_all)}")

                # 检查虚拟机的网卡配置
                for nic_name, nic_config in nic_all.items():
                    # 处理nic_config可能是字典或NCConfig对象的情况
                    nic_mac = nic_config.mac_addr if hasattr(nic_config, 'mac_addr') else nic_config.get('mac_addr', '')

                    logger.debug(f"[虚拟机上报] 网卡 {nic_name} MAC: {nic_mac} vs 上报MAC: {mac_addr}")

                    if nic_mac.lower() == mac_addr.lower():
                        # 找到匹配的虚拟机，创建HWStatus对象
                        logger.info(f"[虚拟机上报] 找到匹配的虚拟机! 主机: {hs_name}, UUID: {vm_uuid}")
                        logger.debug(f"[虚拟机上报] 状态数据: {status_data}")
                        try:
                            # 添加上报时间戳（秒级）
                            import time
                            status_data['on_update'] = int(time.time())

                            hw_status = HWStatus(**status_data)
                            logger.debug(f"[虚拟机上报] HWStatus对象创建成功: {hw_status}")

                            # 直接使用 DataManage 保存状态（立即写入数据库）=================
                            if server.save_data and server.hs_config.server_name:
                                logger.debug(f"[虚拟机上报] 开始调用 DataManage.add_vm_status")
                                result = server.save_data.add_vm_status(server.hs_config.server_name, vm_uuid,
                                                                        hw_status)
                                logger.debug(f"[虚拟机上报] add_vm_status 返回结果: {result}")
                                # if result:
                                #     logger.success(f"[虚拟机上报] 状态已成功保存到数据库")
                                # else:
                                #     logger.warning(f"[虚拟机上报] 状态保存失败")
                                if not result:
                                    logger.warning(f"[虚拟机上报] 状态保存失败")
                            else:
                                logger.warning(
                                    f"[虚拟机上报] 警告: 数据库未初始化，save_data={server.save_data}, server_name={server.hs_config.server_name if server.hs_config else 'None'}")

                            found = True
                            # 获取虚拟机密码
                            vm_pass = vm_config.os_pass
                            return self.api_response(200, f'虚拟机 {vm_uuid} 状态已更新', {
                                'hs_name': hs_name,
                                'vm_uuid': vm_uuid,
                                'vm_pass': vm_pass
                            })
                        except Exception as e:
                            logger.error(f"[虚拟机上报] 状态数据处理失败: {e}")
                            return self.api_response(500, f'状态数据处理失败: {str(e)}')

        if not found:
            logger.warning(f"[虚拟机上报] 未找到MAC地址为 {mac_addr} 的虚拟机")
            return self.api_response(404, f'未找到MAC地址为 {mac_addr} 的虚拟机')

    # ========================================================================
    # 虚拟机网络配置API - NAT端口转发
    # ========================================================================

    # 获取虚拟机NAT端口转发规则 ########################################################################
    # :param hs_name: 主机名称
    # :param vm_uuid: 虚拟机UUID
    # :return: 包含NAT规则列表的API响应
    # ####################################################################################
    def get_vm_nat_rules(self, hs_name, vm_uuid):
        """获取虚拟机NAT端口转发规则"""
        server = self.hs_manage.get_host(hs_name)
        if not server:
            return self.api_response(404, '主机不存在')

        vm_config = server.vm_saving.get(vm_uuid)
        if not vm_config:
            return self.api_response(404, '虚拟机不存在')

        # 从vm_config中获取NAT规则
        nat_rules = []
        if hasattr(vm_config, 'nat_all') and vm_config.nat_all:
            for idx, rule in enumerate(vm_config.nat_all):
                if hasattr(rule, '__save__') and callable(rule.__save__):
                    nat_rules.append(rule.__save__())
                elif isinstance(rule, dict):
                    nat_rules.append(rule)
                else:
                    # 兼容旧格式
                    nat_rules.append({
                        'lan_port': getattr(rule, 'lan_port', 0),
                        'wan_port': getattr(rule, 'wan_port', 0),
                        'lan_addr': getattr(rule, 'lan_addr', ''),
                        'nat_tips': getattr(rule, 'nat_tips', '')
                    })

        return self.api_response(200, 'success', nat_rules)

    # 添加虚拟机NAT端口转发规则 ########################################################################
    # :param hs_name: 主机名称
    # :param vm_uuid: 虚拟机UUID
    # :return: NAT规则添加结果的API响应
    # ####################################################################################
    def add_vm_nat_rule(self, hs_name, vm_uuid):
        """添加虚拟机NAT端口转发规则"""
        server = self.hs_manage.get_host(hs_name)
        if not server:
            return self.api_response(404, '主机不存在')

        vm_config = server.vm_saving.get(vm_uuid)
        if not vm_config:
            return self.api_response(404, '虚拟机不存在')

        data = request.get_json() or {}

        # 创建PortData对象
        port_data = PortData()
        port_data.lan_port = data.get('lan_port', 0)
        port_data.wan_port = data.get('wan_port', 0)
        port_data.lan_addr = data.get('lan_addr', '')
        port_data.nat_tips = data.get('nat_tips', '')

        # 添加到vm_config
        if not hasattr(vm_config, 'nat_all') or vm_config.nat_all is None:
            vm_config.nat_all = []
        vm_config.nat_all.append(port_data)

        # 调用PortsMap创建端口映射
        try:
            result = server.PortsMap(map_info=port_data, flag=True)
            if not result.success:
                # 如果创建失败，从列表中移除
                vm_config.nat_all.pop()
                error_msg = result.message if hasattr(result, 'message') and result.message else '未知错误'
                return self.api_response(500, f'端口映射创建失败: {error_msg}')
        except Exception as e:
            # 如果创建失败，从列表中移除
            vm_config.nat_all.pop()
            traceback.print_exc()
            logger.error(f"创建端口映射失败: {e}")
            return self.api_response(500, f'端口映射创建失败: {str(e)}')

        self.hs_manage.all_save()
        return self.api_response(200, 'NAT规则添加成功')

    # 删除虚拟机NAT端口转发规则 ########################################################################
    # :param hs_name: 主机名称
    # :param vm_uuid: 虚拟机UUID
    # :param rule_index: NAT规则索引
    # :return: NAT规则删除结果的API响应
    # ####################################################################################
    def delete_vm_nat_rule(self, hs_name, vm_uuid, rule_index):
        """删除虚拟机NAT端口转发规则"""
        server = self.hs_manage.get_host(hs_name)
        if not server:
            return self.api_response(404, '主机不存在')

        vm_config = server.vm_saving.get(vm_uuid)
        if not vm_config:
            return self.api_response(404, '虚拟机不存在')

        if not hasattr(vm_config, 'nat_all') or not vm_config.nat_all:
            return self.api_response(404, 'NAT规则不存在')

        if rule_index < 0 or rule_index >= len(vm_config.nat_all):
            return self.api_response(404, 'NAT规则索引无效')

        # 获取要删除的端口映射信息
        port_data = vm_config.nat_all[rule_index]

        # 调用PortsMap删除端口映射
        try:
            if hasattr(port_data, 'lan_addr') and hasattr(port_data, 'lan_port') and hasattr(port_data, 'wan_port'):
                result = server.PortsMap(map_info=port_data, flag=False)
                if not result.success:
                    logger.warning(f'端口映射删除失败: {result.message}')
        except Exception as e:
            logger.error(f"删除端口映射失败: {e}")

        # 从列表中移除
        vm_config.nat_all.pop(rule_index)
        self.hs_manage.all_save()
        return self.api_response(200, 'NAT规则已删除')

    # ========================================================================
    # 虚拟机网络配置API - IP地址管理
    # ========================================================================

    # 获取虚拟机IP地址列表 ########################################################################
    # :param hs_name: 主机名称
    # :param vm_uuid: 虚拟机UUID
    # :return: 包含IP地址列表的API响应
    # ####################################################################################
    def get_vm_ip_addresses(self, hs_name, vm_uuid):
        """获取虚拟机网卡列表（IP地址管理）"""
        server = self.hs_manage.get_host(hs_name)
        if not server:
            return self.api_response(404, '主机不存在')

        vm_config = server.vm_saving.get(vm_uuid)
        if not vm_config:
            return self.api_response(404, '虚拟机不存在')

        # 从vm_config.nic_all中获取网卡列表
        nic_list = []
        if hasattr(vm_config, 'nic_all') and vm_config.nic_all:
            for nic_name, nic_config in vm_config.nic_all.items():
                nic_info = {
                    'nic_name': nic_name,
                    'mac_addr': nic_config.mac_addr if hasattr(nic_config, 'mac_addr') else '',
                    'ip4_addr': nic_config.ip4_addr if hasattr(nic_config, 'ip4_addr') else '',
                    'ip6_addr': nic_config.ip6_addr if hasattr(nic_config, 'ip6_addr') else '',
                    'nic_gate': nic_config.nic_gate if hasattr(nic_config, 'nic_gate') else '',
                    'nic_mask': nic_config.nic_mask if hasattr(nic_config, 'nic_mask') else '255.255.255.0',
                    'nic_type': nic_config.nic_type if hasattr(nic_config, 'nic_type') else '',
                    'dns_addr': nic_config.dns_addr if hasattr(nic_config, 'dns_addr') else []
                }
                nic_list.append(nic_info)

        return self.api_response(200, 'success', nic_list)

    # 添加虚拟机IP地址 ########################################################################
    # :param hs_name: 主机名称
    # :param vm_uuid: 虚拟机UUID
    # :return: IP地址添加结果的API响应
    # ####################################################################################
    def add_vm_ip_address(self, hs_name, vm_uuid):
        """添加虚拟机网卡（新增网卡）"""
        server = self.hs_manage.get_host(hs_name)
        if not server:
            return self.api_response(404, '主机不存在')

        vm_config = server.vm_saving.get(vm_uuid)
        if not vm_config:
            return self.api_response(404, '虚拟机不存在')

        data = request.get_json() or {}
        nic_type = data.get('nic_type', 'nat')

        # 检查用户IP配额
        from flask import session
        from HostModule.UserManager import check_resource_quota
        from HostModule.DataManager import DataManager

        db = DataManager()
        user_id = session.get('user_id')
        if user_id:
            user_data = db.get_user_by_id(user_id)
            if user_data:
                # 使用_calculate_user_ip_usage获取准确的IP使用量
                username = user_data.get('username', '')
                ip_usage = self._calculate_user_ip_usage(username)

                # 更新用户数据中的IP使用量
                user_data['used_nat_ips'] = ip_usage.get('used_nat_ips', 0)
                user_data['used_pub_ips'] = ip_usage.get('used_pub_ips', 0)

                # 根据网卡类型检查配额
                if nic_type == 'nat':
                    can_use, error_msg = check_resource_quota(user_data, nat_ips=1)
                    if not can_use:
                        return self.api_response(400, error_msg)
                elif nic_type == 'pub':
                    can_use, error_msg = check_resource_quota(user_data, pub_ips=1)
                    if not can_use:
                        return self.api_response(400, error_msg)

        # 从数据库读取vm_conf
        server.data_get()
        vm_config = server.vm_saving.get(vm_uuid)
        if not vm_config:
            return self.api_response(404, '虚拟机不存在')

        # 拷贝并修改vm_conf
        vm_config_dict = vm_config.__save__()
        old_vm_config = VMConfig(**vm_config_dict)

        # 生成新的网卡名称
        nic_index = len(vm_config.nic_all)
        nic_name = f"nic{nic_index}"
        while nic_name in vm_config.nic_all:
            nic_index += 1
            nic_name = f"nic{nic_index}"

        # 创建网卡配置
        nic_config = NCConfig(
            nic_type=data.get('nic_type', 'nat'),
            ip4_addr=data.get('ip4_addr', ''),
            ip6_addr=data.get('ip6_addr', ''),
            nic_gate=data.get('nic_gate', ''),
            nic_mask=data.get('nic_mask', '255.255.255.0'),
            dns_addr=data.get('dns_addr',
                              server.hs_config.ipaddr_dnss if hasattr(server.hs_config, 'ipaddr_dnss') else [])
        )

        # 如果没有填写IP地址，则自动分配
        if not nic_config.ip4_addr or nic_config.ip4_addr.strip() == '':
            # 调用NetCheck自动分配IP
            vm_config.nic_all[nic_name] = nic_config
            vm_config, net_result = server.NetCheck(vm_config)
            if not net_result.success:
                return self.api_response(400, f'自动分配IP失败: {net_result.message}')
        else:
            # 手动指定IP，生成MAC地址
            vm_config.nic_all[nic_name] = nic_config
            nic_config.mac_addr = nic_config.send_mac()

        # 执行NCCreate绑定静态IP
        nc_result = server.IPBinder(vm_config, True)
        if not nc_result.success:
            return self.api_response(400, f'绑定静态IP失败: {nc_result.message}')

        # 调用VMUpdate更新
        result = server.VMUpdate(vm_config, old_vm_config)

        if result and result.success:
            self.hs_manage.all_save()

            # 更新用户IP使用量 - 由于数据库中没有used_nat_ips和used_pub_ips字段，
            # IP使用量通过_calculate_user_ip_usage函数实时计算，无需在数据库中维护
            # 注意：IP配额检查会在操作时通过_calculate_user_ip_usage实时获取准确的使用量
            logger.info(f"网卡添加成功，IP使用量将通过实时计算更新")

            return self.api_response(200, f'网卡 {nic_name} 添加成功')

        return self.api_response(400, result.message if result else '添加网卡失败')

    # 删除虚拟机IP地址 ########################################################################
    # :param hs_name: 主机名称
    # :param vm_uuid: 虚拟机UUID
    # :param ip_index: IP地址索引
    # :return: IP地址删除结果的API响应
    # ####################################################################################
    def delete_vm_ip_address(self, hs_name, vm_uuid, nic_name):
        """删除虚拟机网卡"""
        server = self.hs_manage.get_host(hs_name)
        if not server:
            return self.api_response(404, '主机不存在')

        vm_config = server.vm_saving.get(vm_uuid)
        if not vm_config:
            return self.api_response(404, '虚拟机不存在')

        if not hasattr(vm_config, 'nic_all') or not vm_config.nic_all:
            return self.api_response(404, '网卡列表为空')

        if nic_name not in vm_config.nic_all:
            return self.api_response(404, f'网卡 {nic_name} 不存在')

        # 从数据库读取vm_conf
        server.data_get()
        vm_config = server.vm_saving.get(vm_uuid)
        if not vm_config:
            return self.api_response(404, '虚拟机不存在')

        # 删除网卡前，先记录网卡类型
        nic_config = vm_config.nic_all.get(nic_name)
        nic_type = nic_config.nic_type if nic_config else 'nat'

        # 拷贝并修改vm_conf
        vm_config_dict = vm_config.__save__()
        old_vm_config = VMConfig(**vm_config_dict)

        # 删除网卡
        del vm_config.nic_all[nic_name]

        # 调用VMUpdate更新
        result = server.VMUpdate(vm_config, old_vm_config)

        if result and result.success:
            # 确保数据保存成功
            save_success = self.hs_manage.all_save()
            if not save_success:
                logger.warning(f"删除网卡 {nic_name} 后保存数据失败")

            # 更新用户IP使用量 - 由于数据库中没有used_nat_ips和used_pub_ips字段，
            # IP使用量通过_calculate_user_ip_usage函数实时计算，无需在数据库中维护
            logger.info(f"网卡删除成功，IP使用量将通过实时计算更新")

            return self.api_response(200, f'网卡 {nic_name} 已删除')

        return self.api_response(400, result.message if result else '删除网卡失败')

    # 修改虚拟机网卡配置 ########################################################################
    # :param hs_name: 主机名称
    # :param vm_uuid: 虚拟机UUID
    # :param nic_name: 网卡名称
    # :return: 网卡修改结果的API响应
    # ####################################################################################
    def update_vm_ip_address(self, hs_name, vm_uuid, nic_name):
        """修改虚拟机网卡配置"""
        server = self.hs_manage.get_host(hs_name)
        if not server:
            return self.api_response(404, '主机不存在')

        vm_config = server.vm_saving.get(vm_uuid)
        if not vm_config:
            return self.api_response(404, '虚拟机不存在')

        if not hasattr(vm_config, 'nic_all') or not vm_config.nic_all:
            return self.api_response(404, '网卡列表为空')

        if nic_name not in vm_config.nic_all:
            return self.api_response(404, f'网卡 {nic_name} 不存在')

        data = request.get_json() or {}

        # 从数据库读取vm_conf
        server.data_get()
        vm_config = server.vm_saving.get(vm_uuid)
        if not vm_config:
            return self.api_response(404, '虚拟机不存在')

        # 拷贝并修改vm_conf
        vm_config_dict = vm_config.__save__()
        old_vm_config = VMConfig(**vm_config_dict)

        # 获取要修改的网卡
        nic_config = vm_config.nic_all[nic_name]

        # 更新网卡配置
        if 'ip4_addr' in data:
            nic_config.ip4_addr = data['ip4_addr']
        if 'ip6_addr' in data:
            nic_config.ip6_addr = data['ip6_addr']
        if 'nic_gate' in data:
            nic_config.nic_gate = data['nic_gate']
        if 'nic_mask' in data:
            nic_config.nic_mask = data['nic_mask']
        if 'nic_type' in data:
            nic_config.nic_type = data['nic_type']
        if 'dns_addr' in data:
            nic_config.dns_addr = data['dns_addr']

        # 如果修改了IP地址，需要重新生成MAC地址
        if 'ip4_addr' in data or 'ip6_addr' in data:
            nic_config.mac_addr = nic_config.send_mac()

        # 调用VMUpdate更新
        result = server.VMUpdate(vm_config, old_vm_config)

        if result and result.success:
            self.hs_manage.all_save()
            return self.api_response(200, f'网卡 {nic_name} 配置已更新')

        return self.api_response(400, result.message if result else '修改网卡失败')

    # ========================================================================
    # 虚拟机网络配置API - 反向代理管理
    # ========================================================================

    # 获取所有反向代理配置列表（统一函数） ########################################################################
    # :param filter_by_user: 是否按当前用户筛选（True=仅返回用户有权限的虚拟机代理，False=返回所有代理）
    # :return: 包含反向代理配置列表的API响应
    # ####################################################################################
    def list_all_proxys_unified(self, filter_by_user=False):
        """获取所有反向代理配置列表（可选择是否按用户筛选）"""
        try:
            # 如果需要按用户筛选，检查登录状态
            username = None
            if filter_by_user:
                username = session.get('username')
                if not username:
                    return self.api_response(401, '未登录')
            
            all_proxys = []
            
            # 遍历所有主机
            for hs_name, server in self.hs_manage.engine.items():
                # 遍历该主机的所有虚拟机
                for vm_uuid, vm_config in server.vm_saving.items():
                    # 如果需要按用户筛选，检查权限
                    if filter_by_user:
                        if not (hasattr(vm_config, 'own_all') and username in vm_config.own_all):
                            continue  # 跳过无权限的虚拟机
                    
                    # 获取该虚拟机的代理配置
                    if hasattr(vm_config, 'web_all') and vm_config.web_all:
                        for index, proxy in enumerate(vm_config.web_all):
                            proxy_dict = {
                                'host_name': hs_name,
                                'vm_uuid': vm_uuid,
                                'vm_name': getattr(vm_config, 'vm_name', vm_uuid),
                                'proxy_index': index,
                                'domain': getattr(proxy, 'web_addr', ''),
                                'backend_ip': getattr(proxy, 'lan_addr', ''),
                                'backend_port': getattr(proxy, 'lan_port', 80),
                                'ssl_enabled': getattr(proxy, 'is_https', False),
                                'description': getattr(proxy, 'web_tips', '')
                            }
                            all_proxys.append(proxy_dict)
            
            # 统一返回格式
            return self.api_response(200, 'success', {'list': all_proxys, 'total': len(all_proxys)})
        except Exception as e:
            logger.error(f"获取代理配置失败: {e}")
            return self.api_response(500, f'获取代理配置失败: {str(e)}')

    # 获取当前用户的所有反向代理配置列表（兼容接口） ########################################################################
    def list_all_user_proxys(self):
        """获取当前用户的所有反向代理配置列表"""
        return self.list_all_proxys_unified(filter_by_user=True)

    # 获取虚拟机反向代理配置列表 ########################################################################
    # :param hs_name: 主机名称
    # :param vm_uuid: 虚拟机UUID
    # :return: 包含反向代理配置列表的API响应
    # ####################################################################################
    def get_vm_proxy_configs(self, hs_name, vm_uuid):
        """获取虚拟机反向代理配置列表"""
        server = self.hs_manage.get_host(hs_name)
        if not server:
            return self.api_response(404, '主机不存在')

        vm_config = server.vm_saving.get(vm_uuid)
        if not vm_config:
            return self.api_response(404, '虚拟机不存在')

        # 从vm_config.web_all中获取代理配置列表
        proxy_list = []
        if hasattr(vm_config, 'web_all') and vm_config.web_all:
            for proxy in vm_config.web_all:
                # 将WebProxy对象的字段映射为前端期望的格式
                proxy_dict = {
                    'domain': getattr(proxy, 'web_addr', ''),
                    'backend_ip': getattr(proxy, 'lan_addr', ''),
                    'backend_port': getattr(proxy, 'lan_port', 80),
                    'ssl_enabled': getattr(proxy, 'is_https', False),
                    'description': getattr(proxy, 'web_tips', '')
                }
                proxy_list.append(proxy_dict)

        return self.api_response(200, 'success', proxy_list)

    # 添加虚拟机反向代理配置 ########################################################################
    # :param hs_name: 主机名称
    # :param vm_uuid: 虚拟机UUID
    # :return: 反向代理配置添加结果的API响应
    # ####################################################################################
    def add_vm_proxy_config(self, hs_name, vm_uuid):
        """添加虚拟机反向代理配置"""
        server = self.hs_manage.get_host(hs_name)
        if not server:
            return self.api_response(404, '主机不存在')
        data = request.get_json() or {}
        # 创建WebProxy对象
        proxy_config = WebProxy()
        proxy_config.web_addr = data.get('domain', '')
        proxy_config.lan_addr = data.get('backend_ip', '')
        proxy_config.lan_port = int(data.get('backend_port', 80))
        proxy_config.is_https = data.get('ssl_enabled', False)
        proxy_config.web_tips = data.get('description', '')
        # 调用ProxyMap添加代理
        result = server.ProxyMap(proxy_config, vm_uuid, self.hs_manage.proxys, in_flag=True)
        if not result.success:
            logger.error(f'添加代理失败: {result.message}')
            return self.api_response(500, f'添加代理失败: {result.message}')
        # 保存配置
        self.hs_manage.all_save()
        return self.api_response(200, '代理配置添加成功')

    # 删除虚拟机反向代理配置 ########################################################################
    # :param hs_name: 主机名称
    # :param vm_uuid: 虚拟机UUID
    # :param proxy_index: 反向代理配置索引
    # :return: 反向代理配置删除结果的API响应
    # ####################################################################################
    def delete_vm_proxy_config(self, hs_name, vm_uuid, proxy_index):
        """删除虚拟机反向代理配置"""
        server = self.hs_manage.get_host(hs_name)
        if not server:
            return self.api_response(404, '主机不存在')

        vm_config = server.vm_saving.get(vm_uuid)
        if not vm_config:
            return self.api_response(404, '虚拟机不存在')

        if not hasattr(vm_config, 'web_all') or not vm_config.web_all:
            return self.api_response(404, '代理配置不存在')

        if proxy_index < 0 or proxy_index >= len(vm_config.web_all):
            return self.api_response(404, '代理配置索引无效')

        # 获取要删除的代理配置
        proxy_config = vm_config.web_all[proxy_index]

        # 调用ProxyMap删除代理
        result = server.ProxyMap(proxy_config, vm_uuid, self.hs_manage.proxys, in_flag=False)
        if not result.success:
            return self.api_response(500, f'删除代理失败: {result.message}')

        # 保存配置
        self.hs_manage.all_save()
        return self.api_response(200, '代理配置已删除')

    # ========================================================================
    # 管理员级别 - Web反向代理管理API
    # ========================================================================

    # 获取所有反向代理配置 ################################################################
    # :return: 包含所有反向代理配置的API响应
    # ####################################################################################
    def admin_list_all_proxys(self):
        """管理员获取所有反向代理配置列表"""
        return self.list_all_proxys_unified(filter_by_user=False)

    # 获取指定主机的所有反向代理 ##########################################################
    # :param hs_name: 主机名称
    # :return: 包含指定主机所有反向代理配置的API响应
    # ####################################################################################
    def admin_list_host_proxys(self, hs_name):
        """管理员获取指定主机的所有反向代理配置"""
        server = self.hs_manage.get_host(hs_name)
        if not server:
            return self.api_response(404, '主机不存在')
        
        host_proxys = []
        
        # 遍历该主机的所有虚拟机
        for vm_uuid, vm_config in server.vm_saving.items():
            if hasattr(vm_config, 'web_all') and vm_config.web_all:
                for index, proxy in enumerate(vm_config.web_all):
                    proxy_dict = {
                        'host_name': hs_name,
                        'vm_uuid': vm_uuid,
                        'vm_name': getattr(vm_config, 'vm_name', vm_uuid),
                        'proxy_index': index,
                        'domain': getattr(proxy, 'web_addr', ''),
                        'backend_ip': getattr(proxy, 'lan_addr', ''),
                        'backend_port': getattr(proxy, 'lan_port', 80),
                        'ssl_enabled': getattr(proxy, 'is_https', False),
                        'description': getattr(proxy, 'web_tips', '')
                    }
                    host_proxys.append(proxy_dict)
        
        return self.api_response(200, 'success', {
            'list': host_proxys,
            'total': len(host_proxys)
        })

    # 获取指定虚拟机的反向代理 ############################################################
    # :param hs_name: 主机名称
    # :param vm_uuid: 虚拟机UUID
    # :return: 包含指定虚拟机反向代理配置的API响应
    # ####################################################################################
    def admin_get_vm_proxys(self, hs_name, vm_uuid):
        """管理员获取指定虚拟机的反向代理配置"""
        server = self.hs_manage.get_host(hs_name)
        if not server:
            return self.api_response(404, '主机不存在')

        vm_config = server.vm_saving.get(vm_uuid)
        if not vm_config:
            return self.api_response(404, '虚拟机不存在')

        proxy_list = []
        if hasattr(vm_config, 'web_all') and vm_config.web_all:
            for index, proxy in enumerate(vm_config.web_all):
                proxy_dict = {
                    'host_name': hs_name,
                    'vm_uuid': vm_uuid,
                    'vm_name': getattr(vm_config, 'vm_name', vm_uuid),
                    'proxy_index': index,
                    'domain': getattr(proxy, 'web_addr', ''),
                    'backend_ip': getattr(proxy, 'lan_addr', ''),
                    'backend_port': getattr(proxy, 'lan_port', 80),
                    'ssl_enabled': getattr(proxy, 'is_https', False),
                    'description': getattr(proxy, 'web_tips', '')
                }
                proxy_list.append(proxy_dict)

        return self.api_response(200, 'success', {
            'list': proxy_list,
            'total': len(proxy_list)
        })

    # 添加反向代理配置 ####################################################################
    # :param hs_name: 主机名称
    # :param vm_uuid: 虚拟机UUID
    # :return: 反向代理配置添加结果的API响应
    # ####################################################################################
    def admin_add_proxy(self, hs_name, vm_uuid):
        """管理员添加反向代理配置"""
        server = self.hs_manage.get_host(hs_name)
        if not server:
            return self.api_response(404, '主机不存在')

        vm_config = server.vm_saving.get(vm_uuid)
        if not vm_config:
            return self.api_response(404, '虚拟机不存在')

        data = request.get_json() or {}
        
        # 创建WebProxy对象
        from MainObject.Config.WebProxy import WebProxy
        proxy_config = WebProxy()
        proxy_config.web_addr = data.get('domain', '')
        proxy_config.lan_addr = data.get('backend_ip', '')
        proxy_config.lan_port = int(data.get('backend_port', 80))
        proxy_config.is_https = data.get('ssl_enabled', False)
        proxy_config.web_tips = data.get('description', '')

        # 验证域名不能为空
        if not proxy_config.web_addr:
            return self.api_response(400, '域名不能为空')

        # 检查域名是否已存在
        if hasattr(vm_config, 'web_all') and vm_config.web_all:
            for existing_proxy in vm_config.web_all:
                if getattr(existing_proxy, 'web_addr', '') == proxy_config.web_addr:
                    return self.api_response(400, f'域名 {proxy_config.web_addr} 已存在')

        # 调用ProxyMap添加代理
        result = server.ProxyMap(proxy_config, vm_uuid, self.hs_manage.proxys, in_flag=True)
        if not result.success:
            logger.error(f'添加代理失败: {result.message}')
            return self.api_response(500, f'添加代理失败: {result.message}')

        # 保存配置
        self.hs_manage.all_save()
        return self.api_response(200, '代理配置添加成功')

    # 更新反向代理配置 ####################################################################
    # :param hs_name: 主机名称
    # :param vm_uuid: 虚拟机UUID
    # :param proxy_index: 反向代理配置索引
    # :return: 反向代理配置更新结果的API响应
    # ####################################################################################
    def admin_update_proxy(self, hs_name, vm_uuid, proxy_index):
        """管理员更新反向代理配置"""
        server = self.hs_manage.get_host(hs_name)
        if not server:
            return self.api_response(404, '主机不存在')

        vm_config = server.vm_saving.get(vm_uuid)
        if not vm_config:
            return self.api_response(404, '虚拟机不存在')

        if not hasattr(vm_config, 'web_all') or not vm_config.web_all:
            return self.api_response(404, '代理配置不存在')

        if proxy_index < 0 or proxy_index >= len(vm_config.web_all):
            return self.api_response(404, '代理配置索引无效')

        data = request.get_json() or {}
        
        # 获取旧的代理配置
        old_proxy = vm_config.web_all[proxy_index]
        
        # 先删除旧的代理
        result = server.ProxyMap(old_proxy, vm_uuid, self.hs_manage.proxys, in_flag=False)
        if not result.success:
            return self.api_response(500, f'删除旧代理失败: {result.message}')

        # 创建新的WebProxy对象
        from MainObject.Config.WebProxy import WebProxy
        new_proxy = WebProxy()
        new_proxy.web_addr = data.get('domain', getattr(old_proxy, 'web_addr', ''))
        new_proxy.lan_addr = data.get('backend_ip', getattr(old_proxy, 'lan_addr', ''))
        new_proxy.lan_port = int(data.get('backend_port', getattr(old_proxy, 'lan_port', 80)))
        new_proxy.is_https = data.get('ssl_enabled', getattr(old_proxy, 'is_https', False))
        new_proxy.web_tips = data.get('description', getattr(old_proxy, 'web_tips', ''))

        # 验证域名不能为空
        if not new_proxy.web_addr:
            # 恢复旧的代理
            server.ProxyMap(old_proxy, vm_uuid, self.hs_manage.proxys, in_flag=True)
            return self.api_response(400, '域名不能为空')

        # 检查域名是否与其他代理冲突（排除当前索引）
        for i, existing_proxy in enumerate(vm_config.web_all):
            if i != proxy_index and getattr(existing_proxy, 'web_addr', '') == new_proxy.web_addr:
                # 恢复旧的代理
                server.ProxyMap(old_proxy, vm_uuid, self.hs_manage.proxys, in_flag=True)
                return self.api_response(400, f'域名 {new_proxy.web_addr} 已存在')

        # 添加新的代理
        result = server.ProxyMap(new_proxy, vm_uuid, self.hs_manage.proxys, in_flag=True)
        if not result.success:
            # 恢复旧的代理
            server.ProxyMap(old_proxy, vm_uuid, self.hs_manage.proxys, in_flag=True)
            return self.api_response(500, f'添加新代理失败: {result.message}')

        # 更新配置列表
        vm_config.web_all[proxy_index] = new_proxy

        # 保存配置
        self.hs_manage.all_save()
        return self.api_response(200, '代理配置更新成功')

    # 删除反向代理配置 ####################################################################
    # :param hs_name: 主机名称
    # :param vm_uuid: 虚拟机UUID
    # :param proxy_index: 反向代理配置索引
    # :return: 反向代理配置删除结果的API响应
    # ####################################################################################
    def admin_delete_proxy(self, hs_name, vm_uuid, proxy_index):
        """管理员删除反向代理配置"""
        server = self.hs_manage.get_host(hs_name)
        if not server:
            return self.api_response(404, '主机不存在')

        vm_config = server.vm_saving.get(vm_uuid)
        if not vm_config:
            return self.api_response(404, '虚拟机不存在')

        if not hasattr(vm_config, 'web_all') or not vm_config.web_all:
            return self.api_response(404, '代理配置不存在')

        if proxy_index < 0 or proxy_index >= len(vm_config.web_all):
            return self.api_response(404, '代理配置索引无效')

        # 获取要删除的代理配置
        proxy_config = vm_config.web_all[proxy_index]

        # 调用ProxyMap删除代理
        result = server.ProxyMap(proxy_config, vm_uuid, self.hs_manage.proxys, in_flag=False)
        if not result.success:
            return self.api_response(500, f'删除代理失败: {result.message}')

        # 从web_all中删除
        vm_config.web_all.pop(proxy_index)

        # 保存配置
        self.hs_manage.all_save()
        return self.api_response(200, '代理配置已删除')

    # ========================================================================
    # 数据盘管理API - /api/client/hdd/<action>/<hs_name>/<vm_uuid>
    # ========================================================================

    # 适配前端的新版数据盘管理接口 ########################################################

    def get_vm_hdds(self, hs_name, vm_uuid):
        """获取虚拟机数据盘列表"""
        server = self.hs_manage.get_host(hs_name)
        if not server:
            return self.api_response(404, '主机不存在')

        vm_config = server.vm_saving.get(vm_uuid)
        if not vm_config:
            return self.api_response(404, '虚拟机不存在')
            
        hdd_list = []
        if hasattr(vm_config, 'hdd_all'):
            # 必须保证顺序一致，以便通过索引删除
            for i, (name, hdd) in enumerate(vm_config.hdd_all.items()):
                info = {
                    'hdd_index': i,
                    'hdd_num': round(hdd.hdd_size / 1024, 2), # MB -> GB
                    'hdd_path': hdd.hdd_name
                }
                hdd_list.append(info)
                
        return self.api_response(200, '获取成功', hdd_list)


    # 挂载数据盘 ########################################################################
    # :param hs_name: 主机名称
    # :param vm_uuid: 虚拟机UUID
    # :return: API响应
    # ####################################################################################
    def mount_vm_hdd(self, hs_name, vm_uuid):
        """挂载数据盘到虚拟机"""
        server = self.hs_manage.get_host(hs_name)
        if not server:
            return self.api_response(404, '主机不存在')

        vm_config = server.vm_saving.get(vm_uuid)
        if not vm_config:
            return self.api_response(404, '虚拟机不存在')

        data = request.get_json() or {}
        hdd_name = data.get('hdd_name', '')
        hdd_size = data.get('hdd_size', 0)
        hdd_type = data.get('hdd_type', 0)

        if not hdd_name:
            return self.api_response(400, '磁盘名称不能为空')

        # 验证磁盘名称：只能包含数字、字母和下划线
        import re
        if not re.match(r'^[a-zA-Z0-9_]+$', hdd_name):
            return self.api_response(400, '磁盘名称只能包含数字、字母和下划线，不能包含特殊符号和中文')

        # 检查磁盘是否已存在
        hdd_config = None
        if hdd_name in vm_config.hdd_all:
            # 磁盘已存在，检查挂载状态
            existing_hdd = vm_config.hdd_all[hdd_name]
            hdd_flag = getattr(existing_hdd, 'hdd_flag', 0)

            if hdd_flag == 1:
                # 已挂载，不允许重复挂载
                return self.api_response(400, '磁盘已挂载，无需重复挂载')

            # 未挂载（hdd_flag=0），使用已有配置进行挂载
            hdd_config = existing_hdd
            logger.info(f"挂载已存在的未挂载磁盘: {hdd_name}")
        else:
            # 磁盘不存在，创建新磁盘
            if hdd_size < 1024:
                return self.api_response(400, '磁盘大小至少为1024MB')

            # 创建SDConfig对象
            from MainObject.Config.SDConfig import SDConfig
            hdd_config = SDConfig(hdd_name=hdd_name, hdd_size=hdd_size, hdd_type=hdd_type)
            logger.info(f"创建新磁盘: {hdd_name}, 大小: {hdd_size}MB, 类型: {hdd_type}")

        # 调用HDDMount挂载
        result = server.HDDMount(vm_uuid, hdd_config, in_flag=True)
        if not result.success:
            return self.api_response(500, f'挂载失败: {result.message}')

        # 如果是新磁盘，添加到vm_config.hdd_all
        if hdd_name not in vm_config.hdd_all:
            vm_config.hdd_all[hdd_name] = hdd_config

        # 保存配置
        self.hs_manage.all_save()
        return self.api_response(200, '数据盘挂载成功')

    # 卸载数据盘 ########################################################################
    # :param hs_name: 主机名称
    # :param vm_uuid: 虚拟机UUID
    # :return: API响应
    # ####################################################################################
    def unmount_vm_hdd(self, hs_name, vm_uuid):
        """卸载虚拟机数据盘"""
        server = self.hs_manage.get_host(hs_name)
        if not server:
            return self.api_response(404, '主机不存在')

        vm_config = server.vm_saving.get(vm_uuid)
        if not vm_config:
            return self.api_response(404, '虚拟机不存在')

        data = request.get_json() or {}
        hdd_name = data.get('hdd_name', '')

        if not hdd_name or hdd_name not in vm_config.hdd_all:
            return self.api_response(404, '数据盘不存在')

        hdd_config = vm_config.hdd_all[hdd_name]

        # 调用HDDMount卸载
        result = server.HDDMount(vm_uuid, hdd_config, in_flag=False)
        if not result.success:
            return self.api_response(500, f'卸载失败: {result.message}')

        # 保存配置
        self.hs_manage.all_save()
        return self.api_response(200, '数据盘已卸载')

    # 移交数据盘所有权 ##################################################################
    # :param hs_name: 主机名称
    # :param vm_uuid: 虚拟机UUID
    # :return: API响应
    # ####################################################################################
    def transfer_vm_hdd(self, hs_name, vm_uuid):
        """移交数据盘所有权到另一个虚拟机"""
        server = self.hs_manage.get_host(hs_name)
        if not server:
            return self.api_response(404, '主机不存在')

        vm_config = server.vm_saving.get(vm_uuid)
        if not vm_config:
            return self.api_response(404, '虚拟机不存在')

        data = request.get_json() or {}
        hdd_name = data.get('hdd_name', '')
        target_vm = data.get('target_vm', '')

        if not hdd_name or hdd_name not in vm_config.hdd_all:
            return self.api_response(404, '数据盘不存在')
        if not target_vm:
            return self.api_response(400, '目标虚拟机不能为空')

        # 检查目标虚拟机是否存在
        if target_vm not in server.vm_saving:
            return self.api_response(404, '目标虚拟机不存在')

        hdd_config = vm_config.hdd_all[hdd_name]

        # 调用HDDTrans移交所有权
        result = server.HDDTrans(vm_uuid, hdd_config, target_vm)
        if not result.success:
            return self.api_response(500, f'移交失败: {result.message}')

        # 保存配置
        self.hs_manage.all_save()
        return self.api_response(200, '数据盘所有权移交成功')

    # 删除数据盘 ########################################################################
    # :param hs_name: 主机名称
    # :param vm_uuid: 虚拟机UUID
    # :return: API响应
    # ####################################################################################
    def delete_vm_hdd(self, hs_name, vm_uuid):
        """删除虚拟机数据盘"""
        server = self.hs_manage.get_host(hs_name)
        if not server:
            return self.api_response(404, '主机不存在')

        vm_config = server.vm_saving.get(vm_uuid)
        if not vm_config:
            return self.api_response(404, '虚拟机不存在')

        data = request.get_json() or {}
        hdd_name = data.get('hdd_name', '')

        if not hdd_name or hdd_name not in vm_config.hdd_all:
            return self.api_response(404, '数据盘不存在')

        hdd_config = vm_config.hdd_all[hdd_name]

        # 调用RMMounts删除磁盘
        result = server.RMMounts(vm_uuid, hdd_name)
        if not result.success:
            return self.api_response(500, f'删除失败: {result.message}')

        # 保存配置
        self.hs_manage.all_save()
        return self.api_response(200, '数据盘已删除')

    # ========================================================================
    # ISO管理API - /api/client/iso/<action>/<hs_name>/<vm_uuid>
    # ========================================================================

    # 挂载ISO ########################################################################
    # :param hs_name: 主机名称
    # :param vm_uuid: 虚拟机UUID
    # :return: API响应
    # ####################################################################################
    def get_vm_isos(self, hs_name, vm_uuid):
        """获取虚拟机ISO挂载列表"""
        server = self.hs_manage.get_host(hs_name)
        if not server:
            return self.api_response(404, '主机不存在')

        vm_config = server.vm_saving.get(vm_uuid)
        if not vm_config:
            return self.api_response(404, '虚拟机不存在')

        iso_list = []
        if hasattr(vm_config, 'iso_all'):
            # 必须保证顺序一致，以便通过索引删除
            for i, (name, iso) in enumerate(vm_config.iso_all.items()):
                info = {
                    'iso_index': i,
                    'iso_path': iso.iso_file,
                    'iso_name': iso.iso_name,
                    'iso_hint': iso.iso_hint
                }
                iso_list.append(info)
        
        return self.api_response(200, '获取成功', iso_list)

    def mount_vm_iso(self, hs_name, vm_uuid):
        """挂载ISO镜像到虚拟机"""
        server = self.hs_manage.get_host(hs_name)
        if not server:
            return self.api_response(404, '主机不存在')

        vm_config = server.vm_saving.get(vm_uuid)
        if not vm_config:
            return self.api_response(404, '虚拟机不存在')

        data = request.get_json() or {}
        iso_name = data.get('iso_name', '')  # 挂载名称（英文+数字）
        iso_file = data.get('iso_file', '')  # ISO文件名（xxx.iso）
        iso_hint = data.get('iso_hint', '')  # 备注

        if not iso_name:
            return self.api_response(400, '挂载名称不能为空')

        if not iso_file:
            return self.api_response(400, 'ISO文件不能为空')

        # 创建IMConfig对象
        from MainObject.Config.IMConfig import IMConfig
        iso_config = IMConfig(
            iso_name=iso_name,
            iso_file=iso_file,
            iso_hint=iso_hint
        )

        # 调用ISOMount挂载
        result = server.ISOMount(vm_uuid, iso_config, in_flag=True)
        if not result.success:
            return self.api_response(500, f'挂载失败: {result.message}')

        # 保存配置
        self.hs_manage.all_save()
        return self.api_response(200, 'ISO挂载成功')

    # 卸载ISO ########################################################################
    # :param hs_name: 主机名称
    # :param vm_uuid: 虚拟机UUID
    # :param iso_index: ISO索引
    # :return: API响应
    # ####################################################################################
    def unmount_vm_iso(self, hs_name, vm_uuid, iso_name):
        """卸载虚拟机ISO镜像"""
        server = self.hs_manage.get_host(hs_name)
        if not server:
            return self.api_response(404, '主机不存在')

        vm_config = server.vm_saving.get(vm_uuid)
        if not vm_config:
            return self.api_response(404, '虚拟机不存在')

        if not hasattr(vm_config, 'iso_all') or not vm_config.iso_all:
            return self.api_response(404, 'ISO配置不存在')

        # iso_all现在是字典，使用iso_name作为key
        if iso_name not in vm_config.iso_all:
            return self.api_response(404, 'ISO不存在')

        iso_config = vm_config.iso_all[iso_name]

        # 调用ISOMount卸载
        result = server.ISOMount(vm_uuid, iso_config, in_flag=False)
        if not result.success:
            return self.api_response(500, f'卸载失败: {result.message}')

        # 保存配置
        self.hs_manage.all_save()
        return self.api_response(200, 'ISO已卸载')

    # ========================================================================
    # 备份管理API - /api/client/backup/<action>/<hs_name>/<vm_uuid>
    # ========================================================================

    # 获取备份列表 ####################################################################
    # :param hs_name: 主机名称
    # :param vm_uuid: 虚拟机UUID
    # :return: API响应
    # ####################################################################################
    def get_vm_backups(self, hs_name, vm_uuid):
        """获取虚拟机备份列表"""
        server = self.hs_manage.get_host(hs_name)
        if not server:
            return self.api_response(404, '主机不存在')

        vm_config = server.vm_saving.get(vm_uuid)
        if not vm_config:
            return self.api_response(404, '虚拟机不存在')

        backup_list = []
        if hasattr(vm_config, 'backups'):
            for i, backup in enumerate(vm_config.backups):
                # 格式化时间
                backup_time_str = str(backup.backup_time)
                
                info = {
                    'backup_index': i,
                    'backup_name': backup.backup_name,
                    'backup_path': '', # 暂时无法获取
                    'created_time': backup_time_str,
                    'size': '未知' # 暂时无法获取
                }
                backup_list.append(info)
        
        return self.api_response(200, '获取成功', backup_list)

    # 创建备份 ########################################################################
    # :param hs_name: 主机名称
    # :param vm_uuid: 虚拟机UUID
    # :return: API响应
    # ####################################################################################
    def create_vm_backup(self, hs_name, vm_uuid):
        """创建虚拟机备份"""
        server = self.hs_manage.get_host(hs_name)
        if not server:
            return self.api_response(404, '主机不存在')

        vm_config = server.vm_saving.get(vm_uuid)
        if not vm_config:
            return self.api_response(404, '虚拟机不存在')

        data = request.get_json() or {}
        vm_tips = data.get('vm_tips', '')

        if not vm_tips:
            return self.api_response(400, '备份说明不能为空')

        # 调用VMBackup创建备份
        result = server.VMBackup(vm_uuid, vm_tips)
        if not result.success:
            return self.api_response(500, f'备份失败: {result.message}')

        # 保存配置
        self.hs_manage.all_save()
        return self.api_response(200, '备份创建成功')

    # 还原备份 ########################################################################
    # :param hs_name: 主机名称
    # :param vm_uuid: 虚拟机UUID
    # :return: API响应
    # ####################################################################################
    def restore_vm_backup(self, hs_name, vm_uuid):
        """还原虚拟机备份"""
        server = self.hs_manage.get_host(hs_name)
        if not server:
            return self.api_response(404, '主机不存在')

        vm_config = server.vm_saving.get(vm_uuid)
        if not vm_config:
            return self.api_response(404, '虚拟机不存在')

        data = request.get_json() or {}
        vm_back = data.get('vm_back', '')

        if not vm_back:
            return self.api_response(400, '备份名称不能为空')

        # 调用Restores还原备份
        result = server.Restores(vm_uuid, vm_back)
        if not result.success:
            return self.api_response(500, f'还原失败: {result.message}')

        # 保存配置
        self.hs_manage.all_save()
        return self.api_response(200, '备份还原成功')

    # 删除备份 ########################################################################
    # :param hs_name: 主机名称
    # :param vm_uuid: 虚拟机UUID
    # :return: API响应
    # ####################################################################################
    def delete_vm_backup(self, hs_name, vm_uuid):
        """删除虚拟机备份"""
        server = self.hs_manage.get_host(hs_name)
        if not server:
            return self.api_response(404, '主机不存在')

        vm_config = server.vm_saving.get(vm_uuid)
        if not vm_config:
            return self.api_response(404, '虚拟机不存在')

        data = request.get_json() or {}
        vm_back = data.get('vm_back', '')

        if not vm_back:
            return self.api_response(400, '备份名称不能为空')

        # 调用RMBackup删除备份
        result = server.RMBackup(vm_uuid, vm_back)
        if not result.success:
            return self.api_response(500, f'删除失败: {result.message}')

        # 从backups中删除
        vm_config.backups = [b for b in vm_config.backups if b.backup_name != vm_back]

        # 保存配置
        self.hs_manage.all_save()
        return self.api_response(200, '备份已删除')

    # 扫描备份 ########################################################################
    # :param hs_name: 主机名称
    # :return: API响应
    # ####################################################################################
    def scan_backups(self, hs_name):
        """扫描主机备份文件"""
        server = self.hs_manage.get_host(hs_name)
        if not server:
            return self.api_response(404, '主机不存在')

        try:
            # 调用LDBackup扫描备份
            result = server.LDBackup("")

            # 保存配置
            self.hs_manage.all_save()
            return self.api_response(200, '备份扫描成功')
        except Exception as e:
            logger.error(f"扫描备份失败: {e}")
            return self.api_response(500, f'扫描失败: {str(e)}')

    # 获取全局反向代理配置列表 ########################################################################
    # :return: 包含全局反向代理配置列表的API响应
    # ####################################################################################
    def get_global_proxy_configs(self):
        """获取全局反向代理配置列表（从所有虚拟机配置获取，管理员权限）"""
        return self.list_all_proxys_unified(filter_by_user=False)

    # 添加全局反向代理配置 ########################################################################
    # :return: 全局反向代理配置添加结果的API响应
    # ####################################################################################
    def add_global_proxy_config(self):
        """添加全局反向代理配置（添加到指定虚拟机）"""
        try:
            data = request.get_json() or {}

            # 验证必填字段
            if not data.get('host_name'):
                return self.api_response(400, '主机名不能为空')
            if not data.get('vm_uuid'):
                return self.api_response(400, '虚拟机 UUID不能为空')
            if not data.get('domain'):
                return self.api_response(400, '域名地址不能为空')
            if not data.get('backend_ip'):
                return self.api_response(400, '内网地址不能为空')
            if not data.get('backend_port'):
                return self.api_response(400, '内网端口不能为空')

            hs_name = data.get('host_name')
            vm_uuid = data.get('vm_uuid')

            # 获取主机和虚拟机
            server = self.hs_manage.get_host(hs_name)
            if not server:
                return self.api_response(404, '主机不存在')

            vm_config = server.vm_saving.get(vm_uuid)
            if not vm_config:
                return self.api_response(404, '虚拟机不存在')

            # 创建WebProxy对象
            from MainObject.Config.WebProxy import WebProxy
            proxy_config = WebProxy()
            proxy_config.web_addr = data.get('domain', '')
            proxy_config.lan_addr = data.get('backend_ip', '')
            proxy_config.lan_port = int(data.get('backend_port', 80))
            proxy_config.is_https = data.get('ssl_enabled', False)
            proxy_config.web_tips = data.get('description', '')

            # 检查域名是否已存在
            if hasattr(vm_config, 'web_all') and vm_config.web_all:
                for existing_proxy in vm_config.web_all:
                    if getattr(existing_proxy, 'web_addr', '') == proxy_config.web_addr:
                        return self.api_response(400, f'域名 {proxy_config.web_addr} 已存在')

            # 调用ProxyMap添加代理
            result = server.ProxyMap(proxy_config, vm_uuid, self.hs_manage.proxys, in_flag=True)
            if not result.success:
                logger.error(f'添加代理失败: {result.message}')
                return self.api_response(500, f'添加代理失败: {result.message}')

            # 保存配置
            self.hs_manage.all_save()
            return self.api_response(200, '代理配置添加成功')

        except Exception as e:
            logger.error(f"添加全局代理配置失败: {e}")
            traceback.print_exc()
            return self.api_response(500, f'添加全局代理配置失败: {str(e)}')

    # 删除全局反向代理配置 ########################################################################
    # :param web_addr: 代理域名地址
    # :return: 全局反向代理配置删除结果的API响应
    # ####################################################################################
    def delete_global_proxy_config(self, hs_name, vm_uuid, proxy_index):
        """删除全局反向代理配置（从指定虚拟机删除）"""
        try:
            if not hs_name:
                return self.api_response(400, '主机名不能为空')
            if not vm_uuid:
                return self.api_response(400, '虚拟机 UUID不能为空')
            if proxy_index is None:
                return self.api_response(400, '代理索引不能为空')

            # 获取主机和虚拟机
            server = self.hs_manage.get_host(hs_name)
            if not server:
                return self.api_response(404, '主机不存在')

            vm_config = server.vm_saving.get(vm_uuid)
            if not vm_config:
                return self.api_response(404, '虚拟机不存在')

            if not hasattr(vm_config, 'web_all') or not vm_config.web_all:
                return self.api_response(404, '代理配置不存在')

            proxy_index = int(proxy_index)
            if proxy_index < 0 or proxy_index >= len(vm_config.web_all):
                return self.api_response(404, '代理配置索引无效')

            # 获取要删除的代理配置
            proxy_config = vm_config.web_all[proxy_index]

            # 调用ProxyMap删除代理
            result = server.ProxyMap(proxy_config, vm_uuid, self.hs_manage.proxys, in_flag=False)
            if not result.success:
                return self.api_response(500, f'删除代理失败: {result.message}')

            # 从web_all中删除
            vm_config.web_all.pop(proxy_index)

            # 保存配置
            self.hs_manage.all_save()
            return self.api_response(200, '代理配置已删除')

        except Exception as e:
            logger.error(f"删除全局代理配置失败: {e}")
            traceback.print_exc()
            return self.api_response(500, f'删除全局代理配置失败: {str(e)}')

    # 获取系统网卡IPv4地址列表 ########################################################################
    # :return: 包含网卡IPv4地址列表的API响应
    # ####################################################################################
