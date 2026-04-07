"""
用户认证和权限管理模块
提供密码加密、用户认证、权限检查等功能
"""
import bcrypt
import secrets
import json
from typing import Optional, Dict, Any, Callable
from functools import wraps
from flask import session, request, redirect, url_for, jsonify
from loguru import logger
from MainObject.Config.WebUsers import WebUser

# 全局Bearer Token验证器（由HostServer.py启动时注入）
_bearer_token_getter: Callable[[], str] = lambda: ""

# 全局数据库getter（由MainServer.py启动时注入，用于require_permission权限查询）
_db_getter: Callable[[], Any] = lambda: None


def init_bearer_validator(getter: Callable[[], str]):
    """初始化Bearer Token验证器，由HostServer.py启动时调用注入"""
    global _bearer_token_getter
    _bearer_token_getter = getter
    logger.info("[UserManager] Bearer Token验证器已注入")


def init_db_getter(getter: Callable[[], Any]):
    """初始化数据库getter，由MainServer.py启动时调用注入"""
    global _db_getter
    _db_getter = getter
    logger.info("[UserManager] 数据库getter已注入")


def _verify_bearer_token(auth_header: str) -> bool:
    """验证Bearer Token是否有效"""
    if not auth_header.startswith('Bearer '):
        return False
    token = auth_header[7:]
    expected = _bearer_token_getter()
    return bool(token and expected and token == expected)


class UserManager:
    """用户认证管理类"""

    @staticmethod
    def hash_password(password: str) -> str:
        """密码加密（使用bcrypt）"""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """验证密码"""
        try:
            # 兼容旧的SHA256哈希（64位十六进制字符串）
            if len(hashed) == 64 and all(c in '0123456789abcdef' for c in hashed):
                import hashlib
                return hashlib.sha256(password.encode()).hexdigest() == hashed
            # bcrypt验证
            return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
        except Exception as e:
            logger.error(f"[UserManager] 密码验证异常: {e}")
            return False

    @staticmethod
    def generate_token(length: int = 32) -> str:
        """生成随机token"""
        return secrets.token_urlsafe(length)

    @staticmethod
    def get_current_user_from_session() -> Optional[Dict[str, Any]]:
        """从session获取当前用户信息"""
        if session.get('logged_in') and session.get('user_id'):
            return {
                'id': session.get('user_id'),
                'username': session.get('username'),
                'is_admin': session.get('is_admin', False),
                'is_token_login': session.get('is_token_login', False),
                'assigned_hosts': session.get('assigned_hosts', [])
            }
        return None

    @staticmethod
    def set_user_session(user_data: Dict[str, Any], is_token_login: bool = False):
        """设置用户session"""
        session['logged_in'] = True
        session['user_id'] = user_data.get('id')
        session['username'] = user_data.get('username')
        session['is_admin'] = user_data.get('is_admin', False)
        session['is_token_login'] = is_token_login
        
        # 设置assigned_hosts
        assigned_hosts = user_data.get('assigned_hosts', [])
        if isinstance(assigned_hosts, str):
            try:
                assigned_hosts = json.loads(assigned_hosts)
            except Exception as e:
                logger.warning(f"[UserManager] 解析assigned_hosts失败: {e}")
                assigned_hosts = []
        session['assigned_hosts'] = assigned_hosts

    @staticmethod
    def clear_session():
        """清除session"""
        session.clear()


def require_login(f):
    """需要登录的装饰器（用户登录或Token登录）"""
    @wraps(f)
    def decorated(*args, **kwargs):
        # 检查Bearer Token（必须验证Token值）
        auth_header = request.headers.get('Authorization', '')
        if _verify_bearer_token(auth_header):
            # Token认证通过，继续执行
            return f(*args, **kwargs)
        # 临时token（财务系统插件跳转）：格式为 temp:<sha256>
        if auth_header.startswith('Bearer temp:'):
            # 只要格式正确就放行，具体权限由各接口内部检查
            return f(*args, **kwargs)
        
        # 检查Session登录
        if session.get('logged_in'):
            return f(*args, **kwargs)
        
        # 未登录
        logger.warning(f"[UserManager] 未授权访问: {request.path}")
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({'code': 401, 'msg': '未授权访问', 'data': None}), 401
        return redirect(url_for('login'))
    
    return decorated


def require_admin(f):
    """需要管理员权限的装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        # 检查Bearer Token（必须验证Token值）
        auth_header = request.headers.get('Authorization', '')
        if _verify_bearer_token(auth_header):
            return f(*args, **kwargs)
        
        # 检查用户是否为管理员
        current_user = UserManager.get_current_user_from_session()
        if current_user and (current_user.get('is_admin') or current_user.get('is_token_login')):
            return f(*args, **kwargs)
        
        # 无权限
        logger.warning(f"[UserManager] 权限不足，需要管理员权限: {request.path}, 用户: {session.get('username', '未知')}")
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({'code': 403, 'msg': '需要管理员权限', 'data': None}), 403
        return redirect(url_for('dashboard'))
    
    return decorated


def require_permission(permission: str):
    """
    需要特定权限的装饰器
    :param permission: 权限字段名，对应 WebUser 中的布尔字段，如 'can_create_vm'、'can_delete_vm' 等
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            # Token登录拥有所有权限（必须验证Token值）
            auth_header = request.headers.get('Authorization', '')
            if _verify_bearer_token(auth_header):
                return f(*args, **kwargs)

            current_user = UserManager.get_current_user_from_session()
            if not current_user:
                logger.warning(f"[UserManager] 未登录访问需要权限 {permission} 的接口: {request.path}")
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({'code': 401, 'msg': '未授权访问', 'data': None}), 401
                return redirect(url_for('login'))

            # 管理员拥有所有权限
            if current_user.get('is_admin') or current_user.get('is_token_login'):
                return f(*args, **kwargs)

            # 从数据库获取完整用户信息，检查具体权限字段
            db = _db_getter()
            if db is None:
                logger.error(f"[UserManager] 数据库未注入，无法检查权限 {permission}")
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({'code': 500, 'msg': '权限服务不可用', 'data': None}), 500
                return redirect(url_for('dashboard'))

            user_id = current_user.get('id')
            full_user = db.get_user_by_id(user_id)
            if not full_user:
                logger.warning(f"[UserManager] 用户 {user_id} 不存在，拒绝权限 {permission}")
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({'code': 403, 'msg': f'需要{permission}权限', 'data': None}), 403
                return redirect(url_for('dashboard'))

            if not full_user.get(permission):
                logger.warning(f"[UserManager] 用户 {full_user.get('username')} 缺少权限 {permission}: {request.path}")
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({'code': 403, 'msg': f'需要{permission}权限', 'data': None}), 403
                return redirect(url_for('dashboard'))

            return f(*args, **kwargs)

        return decorated
    return decorator


def check_host_access(hs_name: str, user_data: Dict[str, Any]) -> bool:
    """
    检查用户是否有访问指定主机的权限
    :param hs_name: 主机名称
    :param user_data: 用户数据（包含assigned_hosts字段）
    :return: 是否有权限
    """
    # 管理员或Token登录有所有权限
    if user_data.get('is_admin') or user_data.get('is_token_login'):
        return True
    
    # 检查分配的主机列表
    assigned_hosts = user_data.get('assigned_hosts', [])
    if isinstance(assigned_hosts, str):
        try:
            assigned_hosts = json.loads(assigned_hosts)
        except Exception as e:
            logger.warning(f"[UserManager] 解析assigned_hosts失败: {e}")
            assigned_hosts = []
    
    return hs_name in assigned_hosts


def check_vm_permission(action: str, user_data: Dict[str, Any]) -> tuple[bool, str]:
    """
    检查用户是否有虚拟机操作权限
    :param action: 操作类型（create/delete/modify）
    :param user_data: 用户数据
    :return: (是否有权限, 错误信息)
    """
    # 管理员或Token登录有所有权限
    if user_data.get('is_admin') or user_data.get('is_token_login'):
        return True, ""
    
    # 检查用户是否启用
    if not user_data.get('is_active'):
        return False, "用户已被禁用"
    
    # 检查具体权限
    if action == 'create' and not user_data.get('can_create_vm'):
        return False, "没有创建虚拟机的权限"
    elif action == 'delete' and not user_data.get('can_delete_vm'):
        return False, "没有删除虚拟机的权限"
    elif action == 'modify' and not user_data.get('can_modify_vm'):
        return False, "没有修改虚拟机的权限"
    
    return True, ""


def check_resource_quota(user_data: Dict[str, Any], **resources) -> tuple[bool, str]:
    """
    检查用户资源配额
    :param user_data: 用户数据
    :param resources: 要使用的资源（cpu, ram, ssd, gpu等）
    :return: (是否可用, 错误信息)
    """
    # 管理员或Token登录无资源限制
    if user_data.get('is_admin') or user_data.get('is_token_login'):
        return True, ""
    
    # 检查各项资源
    for resource, amount in resources.items():
        if amount <= 0:
            continue
        
        quota_key = f"quota_{resource}"
        used_key = f"used_{resource}"
        
        quota = user_data.get(quota_key, 0)
        used = user_data.get(used_key, 0)
        
        if used + amount > quota:
            resource_names = {
                'cpu': 'CPU核心',
                'ram': '内存',
                'ssd': '磁盘',
                'gpu': 'GPU显存',
                'nat_ports': 'NAT端口',
                'web_proxy': 'WEB代理',
                'nat_ips': '内网IP',
                'pub_ips': '公网IP',
                'traffic': '流量',
                'bandwidth_up': '上行带宽',
                'bandwidth_down': '下行带宽'
            }
            name = resource_names.get(resource, resource)
            return False, f"{name}配额不足，已使用{used}/{quota}"
    
    return True, ""


class EmailService:
    """邮件服务类（使用Resend API）"""
    
    def __init__(self, api_key: str = "", from_email: str = ""):
        self.api_key = api_key
        self.from_email = from_email
    
    def send_verification_email(self, to_email: str, username: str, verify_url: str) -> bool:
        """
        发送验证邮件
        :param to_email: 收件人邮箱
        :param username: 用户名
        :param verify_url: 验证链接
        :return: 是否成功
        """
        if not self.api_key or not self.from_email:
            logger.warning("邮件服务未配置")
            return False
        
        try:
            import requests
            
            response = requests.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "from": self.from_email,
                    "to": [to_email],
                    "subject": "OpenIDCS - 邮箱验证",
                    "html": f"""
                    <h2>欢迎注册 OpenIDCS</h2>
                    <p>您好 {username}，</p>
                    <p>请点击下面的链接验证您的邮箱：</p>
                    <p><a href="{verify_url}">{verify_url}</a></p>
                    <p>如果您没有注册账号，请忽略此邮件。</p>
                    <p>此链接24小时内有效。</p>
                    """
                }
            )
            
            if response.status_code == 200:
                logger.info(f"验证邮件已发送到 {to_email}")
                return True
            else:
                logger.error(f"发送邮件失败: {response.text}")
                return False
        except Exception as e:
            logger.error(f"发送邮件异常: {e}")
            return False
    
    def send_test_email(self, to_email: str, subject: str = "OpenIDCS - 测试邮件", body: str = None) -> bool:
        """
        发送测试邮件
        :param to_email: 收件人邮箱
        :param subject: 邮件标题
        :param body: 邮件正文（纯文本）
        :return: 是否成功
        """
        try:
            import requests
            
            # 如果没有提供正文，使用默认模板
            if body is None:
                html_content = f"""
                <h2>测试邮件</h2>
                <p>您好，</p>
                <p>这是一封来自 OpenIDCS 系统的测试邮件。</p>
                <p>如果您收到这封邮件，说明邮件服务配置正常。</p>
                <p>测试时间: {self._get_current_time()}</p>
                <p>OpenIDCS 系统</p>
                """
            else:
                # 将纯文本转换为HTML格式（保留换行）
                html_content = body.replace('\n', '<br>')
            
            response = requests.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "from": self.from_email,
                    "to": [to_email],
                    "subject": subject,
                    "html": html_content
                }
            )
            
            if response.status_code == 200:
                logger.info(f"测试邮件已发送到 {to_email}")
                return True
            else:
                logger.error(f"发送测试邮件失败: {response.text}")
                return False
        except Exception as e:
            logger.error(f"发送测试邮件异常: {e}")
            return False
    
    def _get_current_time(self) -> str:
        """获取当前时间字符串"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def send_password_reset_email(self, to_email: str, username: str, reset_link: str) -> bool:
        """
        发送密码重置邮件
        :param to_email: 收件人邮箱
        :param username: 用户名
        :param reset_link: 重置链接
        :return: 是否成功
        """
        if not self.api_key or not self.from_email:
            logger.warning("邮件服务未配置")
            return False
        
        try:
            import requests
            
            response = requests.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "from": self.from_email,
                    "to": [to_email],
                    "subject": "OpenIDCS - 密码重置",
                    "html": f"""
                    <h2>密码重置请求</h2>
                    <p>您好 {username}，</p>
                    <p>我们收到了您的密码重置请求。</p>
                    <p>请点击下面的链接重置您的密码：</p>
                    <p><a href="{reset_link}">{reset_link}</a></p>
                    <p>如果您没有请求重置密码，请忽略此邮件。</p>
                    <p>此链接24小时内有效。</p>
                    """
                }
            )
            
            if response.status_code == 200:
                logger.info(f"密码重置邮件已发送到 {to_email}")
                return True
            else:
                logger.error(f"发送密码重置邮件失败: {response.text}")
                return False
        except Exception as e:
            logger.error(f"发送密码重置邮件异常: {e}")
            return False
    
    def send_email_change_verification_email(self, to_email: str, username: str, verify_url: str) -> bool:
        """
        发送邮箱变更验证邮件
        :param to_email: 收件人邮箱
        :param username: 用户名
        :param verify_url: 验证链接
        :return: 是否成功
        """
        if not self.api_key or not self.from_email:
            logger.warning("邮件服务未配置")
            return False
        
        try:
            import requests
            
            response = requests.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "from": self.from_email,
                    "to": [to_email],
                    "subject": "OpenIDCS - 邮箱变更验证",
                    "html": f"""
                    <h2>邮箱变更验证</h2>
                    <p>您好 {username}，</p>
                    <p>我们收到了您的邮箱变更请求。</p>
                    <p>请点击下面的链接验证您的新邮箱地址：</p>
                    <p><a href="{verify_url}">{verify_url}</a></p>
                    <p>验证成功后，您的账号邮箱将更新为此邮箱地址。</p>
                    <p>如果您没有请求变更邮箱，请忽略此邮件。</p>
                    <p>此链接24小时内有效。</p>
                    """
                }
            )
            
            if response.status_code == 200:
                logger.info(f"邮箱变更验证邮件已发送到 {to_email}")
                return True
            else:
                logger.error(f"发送邮箱变更验证邮件失败: {response.text}")
                return False
        except Exception as e:
            logger.error(f"发送邮箱变更验证邮件异常: {e}")
            return False