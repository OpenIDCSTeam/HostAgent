# -*- coding: utf-8 -*-
# OpenIDCS Flask Server ###########################################################
# 提供主机和虚拟机管理的Web界面和API接口
################################################################################
import sys
import os
import secrets
import threading
import traceback
import json
from functools import wraps
from flask import Flask, request, jsonify, session, redirect, url_for, g, send_from_directory

from loguru import logger
from HostModule.HostManager import HostManage
from HostModule.RestManager import RestManager
from HostModule.UserManager import UserManager, require_login, require_admin, check_host_access, check_vm_permission, check_resource_quota, EmailService
from HostModule.DataManager import DataManager

# 获取项目根目录，兼容开发环境和打包后的环境
if getattr(sys, 'frozen', False):
    # 打包后的环境：从可执行文件所在目录查找
    project_root = os.path.dirname(sys.executable)
else:
    # 开发环境：从当前文件所在目录查找
    project_root = os.path.dirname(os.path.abspath(__file__))

# 配置模板和静态文件目录
# WebDesigns: 传统 Jinja2 模板（用于兼容旧页面）
# static: React 前端构建产物
template_folder = os.path.join(project_root, 'WebDesigns')
static_folder = os.path.join(project_root, 'static')

app = Flask(__name__, template_folder=template_folder, static_folder=static_folder, static_url_path='')
app.secret_key = secrets.token_hex(32)

# 全局主机管理实例
hs_manage = HostManage()

# 数据库实例
db = DataManager()

# 全局REST管理器实例
rest_manager = RestManager(hs_manage, db)

# 认证装饰器（保持向后兼容）###################################################
# 需要登录或Bearer Token认证的装饰器
################################################################################
def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # 检查Bearer Token
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
            if token and token == hs_manage.bearer:
                return f(*args, **kwargs)
        # 检查Session登录
        if session.get('logged_in'):
            return f(*args, **kwargs)
        # API请求返回JSON错误
        if request.is_json or request.path.startswith('/api/'):
            return rest_manager.api_response(401, '未授权访问', None)
        # 页面请求重定向到登录页
        return redirect(url_for('login'))
    return decorated


# 统一API响应格式包装器 #######################################################
def api_response_wrapper(code=200, msg='成功', data=None):
    return rest_manager.api_response(code, msg, data)


# 页面路由 ####################################################################
# React 前端路由处理
# 对于所有非 API 路由，返回 React 的 index.html，让前端路由接管

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_react_app(path):
    """
    提供 React 前端服务
    - 如果请求的是 API 路由，交给 API 处理器
    - 如果请求的是静态文件且存在，返回静态文件
    - 否则返回 index.html，让 React Router 处理路由
    """
    # API 路由由其他路由处理器接管
    if path.startswith('api/'):
        return {'error': 'API endpoint not found'}, 404
    
    # 检查是否是静态文件请求
    static_file_path = os.path.join(static_folder, path)
    if path and os.path.isfile(static_file_path):
        # 使用 send_from_directory 正确处理 MIME 类型
        response = send_from_directory(static_folder, path)
        
        # 显式设置JavaScript文件的MIME类型（修复Windows上的MIME类型问题）
        if path.endswith('.js'):
            response.headers['Content-Type'] = 'application/javascript; charset=utf-8'
        elif path.endswith('.mjs'):
            response.headers['Content-Type'] = 'application/javascript; charset=utf-8'
        elif path.endswith('.css'):
            response.headers['Content-Type'] = 'text/css; charset=utf-8'
        elif path.endswith('.json'):
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
        elif path.endswith('.woff2'):
            response.headers['Content-Type'] = 'font/woff2'
        elif path.endswith('.woff'):
            response.headers['Content-Type'] = 'font/woff'
        elif path.endswith('.ttf'):
            response.headers['Content-Type'] = 'font/ttf'
        
        return response
    
    # 返回 React 的 index.html
    index_path = os.path.join(static_folder, 'index.html')
    if os.path.isfile(index_path):
        return send_from_directory(static_folder, 'index.html')
    else:
        # 如果 React 前端未构建，返回提示信息
        return '''
        <html>
            <head><title>OpenIDCS - 前端未构建</title></head>
            <body style="font-family: Arial, sans-serif; padding: 50px; text-align: center;">
                <h1>⚠️ React 前端未构建</h1>
                <p>请先构建 React 前端：</p>
                <pre style="background: #f5f5f5; padding: 20px; border-radius: 5px; display: inline-block; text-align: left;">
cd FrontPages
npm install
npm run build
cd ..
mkdir -p static
cp -r FrontPages/dist/* static/
                </pre>
                <p>或使用一键打包脚本：</p>
                <pre style="background: #f5f5f5; padding: 20px; border-radius: 5px; display: inline-block; text-align: left;">
cd AllBuilder
./build_cxfreeze_full.bat  # Windows
./build_cxfreeze_full.sh   # Linux/Mac
                </pre>
            </body>
        </html>
        ''', 503


# 登录API ####################################################################
@app.route('/api/login', methods=['POST'])
def login():
    try:
        # POST登录处理
        data = request.get_json() or request.form
        login_type = data.get('login_type', 'token')
        
        if login_type == 'user':
            # 用户名密码登录
            username = data.get('username', '')
            password = data.get('password', '')
            
            if not username or not password:
                return api_response_wrapper(400, '用户名和密码不能为空')
            
            # 查询用户
            user_data = db.get_user_by_username(username)
            if not user_data:
                return api_response_wrapper(401, '用户名或密码错误')
            
            # 验证密码
            if not UserManager.verify_password(password, user_data['password']):
                return api_response_wrapper(401, '用户名或密码错误')
            
            # 检查用户是否启用
            if not user_data['is_active']:
                return api_response_wrapper(403, '用户已被禁用')
            
            # 检查邮箱验证状态
            system_settings = db.get_system_settings()
            if system_settings.get('email_verification_enabled') == '1' and not user_data['email_verified']:
                return api_response_wrapper(403, '请先验证邮箱后再登录')
            
            # 设置session
            UserManager.set_user_session(user_data, is_token_login=False)
            
            # 更新最后登录时间
            db.update_user_last_login(user_data['id'])
            
            return api_response_wrapper(200, '登录成功', {'redirect': '/admin'})
        
        else:
            # Token登录
            token = data.get('token', '')
            if token and token == hs_manage.bearer:
                # 获取真实的admin用户信息
                admin_user_data = db.get_user_by_username('admin')
                if admin_user_data:
                    # 确保admin用户是启用状态
                    if not admin_user_data.get('is_active', 1):
                        return api_response_wrapper(403, 'Admin用户已被禁用')
                    
                    # 设置session，标记为token登录
                    UserManager.set_user_session(admin_user_data, is_token_login=True)
                    
                    # 更新最后登录时间
                    db.update_user_last_login(admin_user_data['id'])
                    
                    return api_response_wrapper(200, '登录成功', {'redirect': '/admin'})
                else:
                    # 如果admin用户不存在，创建临时的admin session（兼容原有逻辑）
                    temp_admin_data = {
                        'id': 1,
                        'username': 'admin',
                        'is_admin': 1,
                        'is_active': 1,
                        'assigned_hosts': []
                    }
                    UserManager.set_user_session(temp_admin_data, is_token_login=True)
                    return api_response_wrapper(200, '登录成功', {'redirect': '/admin'})
            
            return api_response_wrapper(401, 'Token错误')
    except Exception as e:
        logger.error(f"登录失败: {e}")
        return api_response_wrapper(500, f'登录失败: {str(e)}')


# 退出登录API ################################################################
@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return api_response_wrapper(200, '退出成功')





# 用户注册API ################################################################
@app.route('/api/register', methods=['POST'])
def register():
    try:
        # POST注册处理
        data = request.get_json() or request.form
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        
        # 验证输入
        if not username or not email or not password:
            return api_response_wrapper(400, '用户名、邮箱和密码不能为空')
        
        if len(username) < 3 or len(username) > 20:
            return api_response_wrapper(400, '用户名长度必须在3-20个字符之间')
        
        # 禁止使用admin作为用户名
        if username.lower() == 'admin':
            return api_response_wrapper(400, '不能使用admin作为用户名')
        
        if len(password) < 6:
            return api_response_wrapper(400, '密码长度至少6个字符')
        
        # 检查用户名是否已存在
        if db.get_user_by_username(username):
            return api_response_wrapper(400, '用户名已存在')
        
        # 检查邮箱是否已存在
        if db.get_user_by_email(email):
            return api_response_wrapper(400, '邮箱已被注册')
        
        # 加密密码
        hashed_password = UserManager.hash_password(password)
        
        # 创建用户
        settings = db.get_system_settings()
        
        # 获取默认资源配置
        default_quotas = {
            'quota_cpu': int(settings.get('default_quota_cpu', 2)),
            'quota_ram': int(settings.get('default_quota_ram', 4)),
            'quota_ssd': int(settings.get('default_quota_ssd', 20)),
            'quota_gpu': int(settings.get('default_quota_gpu', 0)),
            'quota_nat_ports': int(settings.get('default_quota_nat_ports', 5)),
            'quota_web_proxy': int(settings.get('default_quota_web_proxy', 0)),
            'quota_bandwidth_up': int(settings.get('default_quota_bandwidth_up', 10)),
            'quota_bandwidth_down': int(settings.get('default_quota_bandwidth_down', 10)),
            'quota_traffic': int(settings.get('default_quota_traffic', 100)),
            # 默认权限
            'can_create_vm': settings.get('default_can_create_vm', '1') == '1',
            'can_modify_vm': settings.get('default_can_modify_vm', '1') == '1',
            'can_delete_vm': settings.get('default_can_delete_vm', '1') == '1',
            'is_admin': 0,  # 新用户默认不是管理员
            'is_active': 1,  # 新用户默认启用
            'assigned_hosts': '[]'  # 默认无分配主机
        }
        
        user_id = db.create_user(username, hashed_password, email, **default_quotas)
        if not user_id:
            return api_response_wrapper(500, '注册失败，请重试')
        
        # 检查是否需要邮箱验证
        settings = db.get_system_settings()
        if settings.get('email_verification_enabled') == '1':
            # 生成验证token
            verify_token = UserManager.generate_token()
            db.set_user_verify_token(user_id, verify_token)
            
            # 发送验证邮件
            email_service = EmailService(
                api_key=settings.get('resend_apikey', ''),
                from_email=settings.get('resend_email', '')
            )
            verify_url = f"{request.host_url}verify_email?token={verify_token}"
            email_service.send_verification_email(email, username, verify_url)
            
            return api_response_wrapper(200, '注册成功！请查收验证邮件')
        else:
            # 直接验证邮箱
            db.verify_user_email(user_id)
            return api_response_wrapper(200, '注册成功！请登录')
    except Exception as e:
        logger.error(f"注册失败: {e}")
        return api_response_wrapper(500, f'注册失败: {str(e)}')


# 验证邮箱 ####################################################################
@app.route('/verify_email')
def verify_email():
    try:
        token = request.args.get('token', '')
        if not token:
            return redirect('/?verified=error&msg=invalid_link')
        
        user_data = db.get_user_by_verify_token(token)
        if not user_data:
            return redirect('/?verified=error&msg=expired')
        
        # 验证邮箱
        if db.verify_user_email(user_data['id']):
            return redirect('/?verified=success')
        else:
            return redirect('/?verified=error&msg=failed')
    except Exception as e:
        logger.error(f"验证邮箱失败: {e}")
        return redirect('/?verified=error&msg=exception')

@app.route('/verify-email-change')
def verify_email_change():
    """验证邮箱变更"""
    try:
        token = request.args.get('token', '')
        if not token:
            return redirect('/profile?email_changed=error&msg=invalid_link')
        
        # 解析token中的邮箱地址
        import base64
        try:
            if ':' not in token:
                return redirect('/profile?email_changed=error&msg=invalid_format')
            
            email_base64, random_value = token.split(':', 1)
            
            # 解码base64邮箱
            email_bytes = base64.urlsafe_b64decode(email_base64 + '=' * (-len(email_base64) % 4))
            new_email = email_bytes.decode()
        except:
            return redirect('/profile?email_changed=error&msg=decode_failed')
        
        # 直接根据verify_token字段查找用户
        user_data = db.get_user_by_verify_token(token)
        if not user_data:
            return redirect('/profile?email_changed=error&msg=expired')
        if not new_email:
            return redirect('/profile?email_changed=error&msg=invalid_email')
        
        # 再次检查邮箱是否已被其他用户使用
        existing_user = db.get_user_by_email(new_email)
        if existing_user and existing_user['id'] != user_data['id']:
            return redirect('/profile?email_changed=error&msg=email_taken')
        
        # 更新用户邮箱
        success = db.update_user(user_data['id'], email=new_email)
        if success:
            # 清除验证token
            db.set_user_verify_token(user_data['id'], '')
            return redirect('/profile?email_changed=success')
        else:
            return redirect('/profile?email_changed=error&msg=update_failed')
            
    except Exception as e:
        logger.error(f"验证邮箱变更失败: {e}")
        return redirect('/profile?email_changed=error&msg=exception')

@app.route('/api/users/change-password', methods=['POST'])
@require_login
def change_password():
    """修改密码"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'code': 401, 'msg': '未登录'})
        
        data = request.get_json()
        new_password = data.get('new_password')
        confirm_password = data.get('confirm_password')
        
        if not new_password or not confirm_password:
            return jsonify({'code': 400, 'msg': '请填写完整信息'})
        
        if new_password != confirm_password:
            return jsonify({'code': 400, 'msg': '新密码与确认密码不一致'})
        
        if len(new_password) < 6:
            return jsonify({'code': 400, 'msg': '新密码长度不能少于6位'})
        
        # 更新密码
        success = db.update_user_password(user_id, UserManager.hash_password(new_password))
        if success:
            return jsonify({'code': 200, 'msg': '密码修改成功'})
        else:
            return jsonify({'code': 500, 'msg': '密码修改失败'})
            
    except Exception as e:
        logger.error(f"密码修改失败: {e}")
        return jsonify({'code': 500, 'msg': '密码修改失败'})


@app.route('/api/users/change-email', methods=['POST'])
@require_login
def change_email():
    """修改邮箱"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'code': 401, 'msg': '未登录'})
        
        data = request.get_json()
        new_email = data.get('new_email')
        
        if not new_email:
            return jsonify({'code': 400, 'msg': '请输入新邮箱地址'})
        
        # 验证邮箱格式
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, new_email):
            return jsonify({'code': 400, 'msg': '请输入有效的邮箱地址'})
        
        # 检查邮箱是否已被其他用户使用
        existing_user = db.get_user_by_email(new_email)
        if existing_user and existing_user['id'] != user_id:
            return jsonify({'code': 400, 'msg': '该邮箱已被其他用户使用'})
        
        # 获取当前用户信息用于生成token
        current_user = db.get_user_by_id(user_id)
        if not current_user:
            return jsonify({'code': 404, 'msg': '用户不存在'})
        
        # 生成包含base64邮箱和随机值的验证token
        import hashlib
        import time
        import base64
        
        # 生成随机值
        import secrets
        random_value = secrets.token_urlsafe(32)
        
        # 将邮箱地址进行base64编码作为token前半部分
        email_base64 = base64.urlsafe_b64encode(new_email.encode()).decode().rstrip('=')
        
        # 组合token: base64邮箱 + 随机值
        token = f"{email_base64}:{random_value}"
        
        # 将完整的token存储到verify_token字段
        db.set_user_verify_token(user_id, token)
        
        # 发送验证邮件
        settings = db.get_system_settings()
        if settings.get('resend_apikey') and settings.get('resend_email'):
            email_service = EmailService(
                api_key=settings.get('resend_apikey', ''),
                from_email=settings.get('resend_email', '')
            )
            
            # 生成验证链接，包含token
            verify_url = f"{request.host_url}verify-email-change?token={token}"
            
            # 获取用户名
            username = current_user.get('username', '用户')
            
            # 发送邮件
            if email_service.send_email_change_verification_email(new_email, username, verify_url):
                return jsonify({'code': 200, 'msg': '验证邮件已发送，请查收并点击验证链接完成邮箱修改'})
            else:
                return jsonify({'code': 500, 'msg': '验证邮件发送失败，请重试'})
        else:
            return jsonify({'code': 500, 'msg': '邮件服务未启用'})
            
    except Exception as e:
        logger.error(f"邮箱修改失败: {e}")
        return jsonify({'code': 500, 'msg': '邮箱修改失败，请重试'})
        return jsonify({'code': 500, 'msg': '邮箱修改失败'})


@app.route('/api/system/forgot-password', methods=['POST'])
@app.route('/api/forgot-password', methods=['POST'])
def forgot_password():
    """找回密码"""
    try:
        data = request.get_json()
        email = data.get('email')
        
        if not email:
            return jsonify({'code': 400, 'msg': '请输入邮箱地址'})
        
        # 检查是否启用了邮件验证
        system_settings = db.get_system_settings()
        if system_settings.get('email_verification_enabled') != '1':
            return jsonify({'code': 400, 'msg': '系统未启用邮件验证功能'})
        
        # 查找用户
        user_data = db.get_user_by_email(email)
        if not user_data:
            return jsonify({'code': 404, 'msg': '该邮箱未注册'})
        
        # 生成重置token
        reset_token = UserManager.generate_token()
        db.set_password_reset_token(user_data['id'], reset_token)
        
        # 发送重置邮件
        email_service = EmailService(
            api_key=system_settings.get('resend_apikey', ''),
            from_email=system_settings.get('resend_email', '')
        )
        reset_link = f"{request.host_url}reset-password?token={reset_token}"
        
        try:
            email_service.send_password_reset_email(email, user_data['username'], reset_link)
            return jsonify({'code': 200, 'msg': '密码重置邮件已发送，请查收'})
        except Exception as e:
            logger.error(f"发送重置邮件失败: {e}")
            return jsonify({'code': 500, 'msg': '发送重置邮件失败'})
        
    except Exception as e:
        logger.error(f"找回密码失败: {e}")
        return jsonify({'code': 500, 'msg': '找回密码失败'})



@app.route('/api/system/reset-password', methods=['POST'])
def reset_password():
    """重置密码"""
    try:
        data = request.get_json()
        token = data.get('token')
        new_password = data.get('new_password')
        confirm_password = data.get('confirm_password')
        
        if not token or not new_password or not confirm_password:
            return jsonify({'code': 400, 'msg': '请填写完整信息'})
        
        if new_password != confirm_password:
            return jsonify({'code': 400, 'msg': '密码与确认密码不一致'})
        
        if len(new_password) < 6:
            return jsonify({'code': 400, 'msg': '密码长度不能少于6位'})
        
        # 验证token
        user_data = db.get_user_by_reset_token(token)
        if not user_data:
            return jsonify({'code': 400, 'msg': '重置链接已过期或无效'})
        
        # 更新密码
        success = db.update_user_password(user_data['id'], UserManager.hash_password(new_password))
        if success:
            # 删除已使用的token
            db.delete_password_reset_token(token)
            return jsonify({'code': 200, 'msg': '密码重置成功'})
        else:
            return jsonify({'code': 500, 'msg': '密码重置失败'})
            
    except Exception as e:
        logger.error(f"密码重置失败: {e}")
        return jsonify({'code': 500, 'msg': '密码重置失败'})



# ============================================================================
# 系统管理API - /api/system/<option>
# ============================================================================

# 引擎类型 ########################################################################
@app.route('/api/system/engine', methods=['GET'])
@require_auth
def api_get_engine_types():
    """获取支持的主机引擎类型"""
    return rest_manager.get_engine_types()


# 保存配置 ########################################################################
@app.route('/api/system/saving', methods=['POST'])
@require_auth
def api_save_system():
    """保存系统配置"""
    return rest_manager.save_system()


# 保存配置（别名） ##################################################################
@app.route('/api/system/save', methods=['POST'])
@require_auth
def api_save_system_alias():
    """保存系统配置（别名路由）"""
    return rest_manager.save_system()


# 加载配置 ########################################################################
@app.route('/api/system/loader', methods=['POST'])
@require_auth
def api_load_system():
    """加载系统配置"""
    return rest_manager.load_system()


# 加载配置（别名） ##################################################################
@app.route('/api/system/load', methods=['POST'])
@require_auth
def api_load_system_alias():
    """加载系统配置（别名路由）"""
    return rest_manager.load_system()


# 系统统计 ########################################################################
@app.route('/api/system/statis', methods=['GET'])
@require_auth
def api_get_system_stats():
    """获取系统统计信息"""
    return rest_manager.get_system_stats()


# 获取当前Token ####################################################################
@app.route('/api/token/current', methods=['GET'])
@require_auth
def api_get_current_token():
    """获取当前的API Token"""
    try:
        return api_response_wrapper(200, '获取Token成功', {'token': hs_manage.bearer})
    except Exception as e:
        logger.error(f"获取Token失败: {e}")
        return api_response_wrapper(500, f'获取Token失败: {str(e)}')


# 设置Token ########################################################################
@app.route('/api/token/set', methods=['POST'])
@require_auth
def api_set_token():
    """设置新的API Token"""
    try:
        data = request.get_json()
        new_token = data.get('token', '')
        
        if not new_token:
            return api_response_wrapper(400, 'Token不能为空')
        
        # 设置新的Token
        hs_manage.set_pass(new_token)
        
        return api_response_wrapper(200, 'Token设置成功', {'token': hs_manage.bearer})
    except Exception as e:
        logger.error(f"设置Token失败: {e}")
        return api_response_wrapper(500, f'设置Token失败: {str(e)}')


# 重置Token ########################################################################
@app.route('/api/token/reset', methods=['POST'])
@require_auth
def api_reset_token():
    """重置API Token（生成新的随机Token）"""
    try:
        # 重置Token（不传参数会自动生成新Token）
        new_token = hs_manage.set_pass()
        
        return api_response_wrapper(200, 'Token重置成功', {'token': new_token})
    except Exception as e:
        logger.error(f"重置Token失败: {e}")
        return api_response_wrapper(500, f'重置Token失败: {str(e)}')


# 获取系统统计信息 ##################################################################
@app.route('/api/system/stats', methods=['GET'])
@require_auth
def api_get_stats():
    """获取系统统计信息（主机数量、虚拟机数量）"""
    try:
        host_count = len(hs_manage.engine)
        vm_count = sum(len(server.vm_saving) for server in hs_manage.engine.values())
        
        return api_response_wrapper(200, '获取统计信息成功', {
            'host_count': host_count,
            'vm_count': vm_count
        })
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        return api_response_wrapper(500, f'获取统计信息失败: {str(e)}')


# 获取日志 ########################################################################
@app.route('/api/system/logger/detail', methods=['GET'])
@require_auth
def api_get_logs():
    """获取日志记录"""
    return rest_manager.get_logs()


# 获取任务 ########################################################################
@app.route('/api/system/tasker', methods=['GET'])
@require_auth
def api_get_tasks():
    """获取任务记录"""
    return rest_manager.get_tasks()


# ============================================================================
# 主机管理API - /api/server/<option>/<key?>
# ============================================================================

# 主机列表 ########################################################################
@app.route('/api/server/detail', methods=['GET'])
@require_auth
def api_get_hosts():
    """获取主机列表（管理员看所有，普通用户看assigned_hosts）"""
    # 获取当前用户信息
    current_user = UserManager.get_current_user_from_session()
    if not current_user:
        return api_response_wrapper(401, '未授权访问')
    
    # Token登录或管理员返回所有主机
    if current_user.get('is_token_login') or current_user.get('is_admin'):
        return rest_manager.get_hosts()
    
    # 普通用户只返回assigned_hosts中的主机
    assigned_hosts = current_user.get('assigned_hosts', [])
    all_hosts_result = rest_manager.get_hosts()
    
    # 解析返回结果
    if hasattr(all_hosts_result, 'json'):
        all_hosts_data = all_hosts_result.json
    else:
        all_hosts_data = all_hosts_result
    
    if all_hosts_data.get('code') == 200:
        all_hosts = all_hosts_data.get('data', {})
        filtered_hosts = {k: v for k, v in all_hosts.items() if k in assigned_hosts}
        return api_response_wrapper(200, '成功', filtered_hosts)
    
    return all_hosts_result


# 主机详情 ########################################################################
@app.route('/api/server/detail/<hs_name>', methods=['GET'])
@require_admin
def api_get_host(hs_name):
    """获取单个主机详情"""
    return rest_manager.get_host(hs_name)


# 获取主机操作系统镜像列表（普通用户可访问）########################################
@app.route('/api/client/os-images/<hs_name>', methods=['GET'])
@require_auth
def api_get_os_images(hs_name):
    """获取主机的操作系统镜像列表（普通用户可访问）"""
    # 获取当前用户信息
    current_user = UserManager.get_current_user_from_session()
    if not current_user:
        return api_response_wrapper(401, '未授权访问')
    
    # 检查主机访问权限
    if not check_host_access(hs_name, current_user):
        return api_response_wrapper(403, '没有访问该主机的权限')
    
    return rest_manager.get_os_images(hs_name)


# 获取主机GPU设备列表（普通用户可访问）############################################
@app.route('/api/client/gpu-list/<hs_name>', methods=['GET'])
@require_auth
def api_get_gpu_list(hs_name):
    """获取主机的GPU设备列表（普通用户可访问）"""
    # 获取当前用户信息
    current_user = UserManager.get_current_user_from_session()
    if not current_user:
        return api_response_wrapper(401, '未授权访问')
    
    # 检查主机访问权限
    if not check_host_access(hs_name, current_user):
        return api_response_wrapper(403, '没有访问该主机的权限')
    
    return rest_manager.get_gpu_list(hs_name)


# 添加主机 ########################################################################
@app.route('/api/server/create', methods=['POST'])
@require_admin
def api_add_host():
    """添加主机"""
    return rest_manager.add_host()


# 修改主机 ########################################################################
@app.route('/api/server/update/<hs_name>', methods=['PUT'])
@require_admin
def api_update_host(hs_name):
    """修改主机配置"""
    return rest_manager.update_host(hs_name)


# 删除主机 ########################################################################
@app.route('/api/server/delete/<hs_name>', methods=['DELETE'])
@require_admin
def api_delete_host(hs_name):
    """删除主机"""
    return rest_manager.delete_host(hs_name)


# 电源控制 ########################################################################
@app.route('/api/server/powers/<hs_name>', methods=['POST'])
@require_admin
def api_host_enable(hs_name):
    """主机启用控制（启用/禁用）"""
    return rest_manager.host_enable(hs_name)


# 主机状态 ########################################################################
@app.route('/api/server/status/<hs_name>', methods=['GET'])
@require_auth
def api_get_host_status(hs_name):
    """获取主机状态"""
    return rest_manager.get_host_status(hs_name)


# ============================================================================
# 虚拟机管理API - /api/client/<option>/<key?>
# ============================================================================

# 虚拟机列表 ########################################################################
@app.route('/api/client/detail/<hs_name>', methods=['GET'])
@require_auth
def api_get_vms(hs_name):
    """获取主机下所有虚拟机"""
    # 检查主机访问权限
    current_user = UserManager.get_current_user_from_session()
    if not current_user:
        return api_response_wrapper(401, '未授权访问')
    
    # Token登录或管理员有所有权限
    if current_user.get('is_token_login') or current_user.get('is_admin'):
        return rest_manager.get_vms(hs_name)
    
    # 检查主机访问权限
    if not check_host_access(hs_name, current_user):
        return api_response_wrapper(403, '没有访问该主机的权限')
    
    return rest_manager.get_vms(hs_name)


# 虚拟机详情 ########################################################################
@app.route('/api/client/detail/<hs_name>/<vm_uuid>', methods=['GET'])
@require_auth
def api_get_vm(hs_name, vm_uuid):
    """获取单个虚拟机详情"""
    return rest_manager.get_vm(hs_name, vm_uuid)


# 创建虚拟机 ########################################################################
@app.route('/api/client/create/<hs_name>', methods=['POST'])
@require_auth
def api_create_vm(hs_name):
    """创建虚拟机"""
    return rest_manager.create_vm(hs_name)


# 修改虚拟机 ########################################################################
@app.route('/api/client/update/<hs_name>/<vm_uuid>', methods=['PUT'])
@require_auth
def api_update_vm(hs_name, vm_uuid):
    """修改虚拟机配置"""
    return rest_manager.update_vm(hs_name, vm_uuid)


# 删除虚拟机 ########################################################################
@app.route('/api/client/delete/<hs_name>/<vm_uuid>', methods=['DELETE'])
@require_auth
def api_delete_vm(hs_name, vm_uuid):
    """删除虚拟机"""
    return rest_manager.delete_vm(hs_name, vm_uuid)


# 虚拟机所有者管理 ########################################################################
@app.route('/api/client/owners/<hs_name>/<vm_uuid>', methods=['GET'])
@app.route('/api/client/owners/detail/<hs_name>/<vm_uuid>', methods=['GET'])
@require_auth
def api_get_vm_owners(hs_name, vm_uuid):
    """获取虚拟机所有者列表"""
    return rest_manager.get_vm_owners(hs_name, vm_uuid)


@app.route('/api/client/owners/<hs_name>/<vm_uuid>', methods=['POST'])
@require_auth
def api_add_vm_owner(hs_name, vm_uuid):
    """添加虚拟机所有者"""
    return rest_manager.add_vm_owner(hs_name, vm_uuid)


@app.route('/api/client/owners/<hs_name>/<vm_uuid>', methods=['DELETE'])
@require_auth
def api_remove_vm_owner(hs_name, vm_uuid):
    """删除虚拟机所有者"""
    return rest_manager.remove_vm_owner(hs_name, vm_uuid)


@app.route('/api/client/owners/<hs_name>/<vm_uuid>/transfer', methods=['POST'])
@require_auth
def api_transfer_vm_ownership(hs_name, vm_uuid):
    """移交虚拟机所有权"""
    return rest_manager.transfer_vm_ownership(hs_name, vm_uuid)


# 电源控制 ########################################################################
@app.route('/api/client/powers/<hs_name>/<vm_uuid>', methods=['POST'])
@require_auth
def api_vm_power(hs_name, vm_uuid):
    """虚拟机电源控制"""
    return rest_manager.vm_power(hs_name, vm_uuid)


# VNC控制台 ########################################################################
@app.route('/api/client/remote/<hs_name>/<vm_uuid>', methods=['GET'])
@require_auth
def api_vm_console(hs_name, vm_uuid):
    """获取虚拟机VNC控制台URL"""
    return rest_manager.vm_console(hs_name, vm_uuid)


# 虚拟机截图 ########################################################################
@app.route('/api/client/screenshot/<hs_name>/<vm_uuid>', methods=['GET'])
@require_auth
def api_vm_screenshot(hs_name, vm_uuid):
    """获取虚拟机截图"""
    return rest_manager.vm_screenshot(hs_name, vm_uuid)


# 修改密码 ########################################################################
@app.route('/api/client/password/<hs_name>/<vm_uuid>', methods=['POST'])
@require_auth
def api_vm_password(hs_name, vm_uuid):
    """修改虚拟机密码"""
    return rest_manager.vm_password(hs_name, vm_uuid)


# 虚拟机状态 ########################################################################
@app.route('/api/client/status/<hs_name>/<vm_uuid>', methods=['GET'])
@require_auth
def api_get_vm_status(hs_name, vm_uuid):
    """获取虚拟机状态"""
    return rest_manager.get_vm_status(hs_name, vm_uuid)


# 扫描虚拟机 ########################################################################
@app.route('/api/client/scaner/<hs_name>', methods=['POST'])
@require_auth
def api_scan_vms(hs_name):
    """扫描主机上的虚拟机"""
    return rest_manager.scan_vms(hs_name)


# 上报状态 ########################################################################
@app.route('/api/client/upload', methods=['POST'])
def api_vm_upload():
    """虚拟机上报状态数据（无需认证）"""
    return rest_manager.vm_upload()


# ============================================================================
# 虚拟机网络配置API - NAT端口转发
# ============================================================================

# 获取NAT规则 ########################################################################
@app.route('/api/client/natget/<hs_name>/<vm_uuid>', methods=['GET'])
@require_auth
def api_get_vm_nat_rules(hs_name, vm_uuid):
    """获取虚拟机NAT端口转发规则"""
    return rest_manager.get_vm_nat_rules(hs_name, vm_uuid)


# 添加NAT规则 ########################################################################
@app.route('/api/client/natadd/<hs_name>/<vm_uuid>', methods=['POST'])
@require_auth
def api_add_vm_nat_rule(hs_name, vm_uuid):
    """添加虚拟机NAT端口转发规则"""
    return rest_manager.add_vm_nat_rule(hs_name, vm_uuid)


# 删除NAT规则 ########################################################################
@app.route('/api/client/natdel/<hs_name>/<vm_uuid>/<int:rule_index>', methods=['DELETE'])
@require_auth
def api_delete_vm_nat_rule(hs_name, vm_uuid, rule_index):
    """删除虚拟机NAT端口转发规则"""
    return rest_manager.delete_vm_nat_rule(hs_name, vm_uuid, rule_index)


# ============================================================================
# 虚拟机网络配置API - IP地址管理
# ============================================================================

# 获取IP列表 ########################################################################
@app.route('/api/client/ipaddr/detail/<hs_name>/<vm_uuid>', methods=['GET'])
@require_auth
def api_get_vm_ip_addresses(hs_name, vm_uuid):
    """获取虚拟机IP地址列表"""
    return rest_manager.get_vm_ip_addresses(hs_name, vm_uuid)


# 添加IP地址 ########################################################################
@app.route('/api/client/ipaddr/create/<hs_name>/<vm_uuid>', methods=['POST'])
@require_auth
def api_add_vm_ip_address(hs_name, vm_uuid):
    """添加虚拟机IP地址"""
    return rest_manager.add_vm_ip_address(hs_name, vm_uuid)


# 删除IP地址 ########################################################################
@app.route('/api/client/ipaddr/delete/<hs_name>/<vm_uuid>/<int:ip_index>', methods=['DELETE'])
@require_auth
def api_delete_vm_ip_address(hs_name, vm_uuid, ip_index):
    """删除虚拟机IP地址"""
    return rest_manager.delete_vm_ip_address(hs_name, vm_uuid, ip_index)


# RESTful风格的IP地址管理API ########################################################################
@app.route('/api/hosts/<hs_name>/vms/<vm_uuid>/ip_addresses', methods=['GET'])
@require_auth
def api_get_vm_ip_addresses_rest(hs_name, vm_uuid):
    """获取虚拟机网卡列表（RESTful风格）"""
    return rest_manager.get_vm_ip_addresses(hs_name, vm_uuid)


@app.route('/api/hosts/<hs_name>/vms/<vm_uuid>/ip_addresses', methods=['POST'])
@require_auth
def api_add_vm_ip_address_rest(hs_name, vm_uuid):
    """添加虚拟机网卡（RESTful风格）"""
    return rest_manager.add_vm_ip_address(hs_name, vm_uuid)


@app.route('/api/hosts/<hs_name>/vms/<vm_uuid>/ip_addresses/<nic_name>', methods=['PUT'])
@require_auth
def api_update_vm_ip_address_rest(hs_name, vm_uuid, nic_name):
    """修改虚拟机网卡配置（RESTful风格）"""
    return rest_manager.update_vm_ip_address(hs_name, vm_uuid, nic_name)


@app.route('/api/hosts/<hs_name>/vms/<vm_uuid>/ip_addresses/<nic_name>', methods=['DELETE'])
@require_auth
def api_delete_vm_ip_address_rest(hs_name, vm_uuid, nic_name):
    """删除虚拟机网卡（RESTful风格）"""
    return rest_manager.delete_vm_ip_address(hs_name, vm_uuid, nic_name)


# ============================================================================
# 虚拟机网络配置API - 反向代理管理
# ============================================================================

# 获取所有代理配置 ####################################################################
@app.route('/api/client/proxys/list', methods=['GET'])
@require_auth
def api_list_all_user_proxys():
    """获取当前用户的所有反向代理配置列表"""
    return rest_manager.list_all_user_proxys()


# 获取代理配置 ########################################################################
@app.route('/api/client/proxys/detail/<hs_name>/<vm_uuid>', methods=['GET'])
@require_auth
def api_get_vm_proxy_configs(hs_name, vm_uuid):
    """获取虚拟机反向代理配置列表"""
    return rest_manager.get_vm_proxy_configs(hs_name, vm_uuid)


# 添加代理配置 ########################################################################
@app.route('/api/client/proxys/create/<hs_name>/<vm_uuid>', methods=['POST'])
@require_auth
def api_add_vm_proxy_config(hs_name, vm_uuid):
    """添加虚拟机反向代理配置"""
    return rest_manager.add_vm_proxy_config(hs_name, vm_uuid)


# 删除代理配置 ########################################################################
@app.route('/api/client/proxys/delete/<hs_name>/<vm_uuid>/<int:proxy_index>', methods=['DELETE'])
@require_auth
def api_delete_vm_proxy_config(hs_name, vm_uuid, proxy_index):
    """删除虚拟机反向代理配置"""
    return rest_manager.delete_vm_proxy_config(hs_name, vm_uuid, proxy_index)


# ============================================================================
# 管理员级别 - Web反向代理管理API
# ============================================================================

# 获取所有反向代理配置 ################################################################
@app.route('/api/admin/proxys/list', methods=['GET'])
@require_admin
def api_admin_list_all_proxys():
    """管理员获取所有反向代理配置列表"""
    return rest_manager.admin_list_all_proxys()


# 获取指定主机的所有反向代理 ##########################################################
@app.route('/api/admin/proxys/list/<hs_name>', methods=['GET'])
@require_admin
def api_admin_list_host_proxys(hs_name):
    """管理员获取指定主机的所有反向代理配置"""
    return rest_manager.admin_list_host_proxys(hs_name)


# 获取指定虚拟机的反向代理 ############################################################
@app.route('/api/admin/proxys/detail/<hs_name>/<vm_uuid>', methods=['GET'])
@require_admin
def api_admin_get_vm_proxys(hs_name, vm_uuid):
    """管理员获取指定虚拟机的反向代理配置"""
    return rest_manager.admin_get_vm_proxys(hs_name, vm_uuid)


# 添加反向代理配置 ####################################################################
@app.route('/api/admin/proxys/create/<hs_name>/<vm_uuid>', methods=['POST'])
@require_admin
def api_admin_add_proxy(hs_name, vm_uuid):
    """管理员添加反向代理配置"""
    return rest_manager.admin_add_proxy(hs_name, vm_uuid)


# 更新反向代理配置 ####################################################################
@app.route('/api/admin/proxys/update/<hs_name>/<vm_uuid>/<int:proxy_index>', methods=['PUT'])
@require_admin
def api_admin_update_proxy(hs_name, vm_uuid, proxy_index):
    """管理员更新反向代理配置"""
    return rest_manager.admin_update_proxy(hs_name, vm_uuid, proxy_index)


# 删除反向代理配置 ####################################################################
@app.route('/api/admin/proxys/delete/<hs_name>/<vm_uuid>/<int:proxy_index>', methods=['DELETE'])
@require_admin
def api_admin_delete_proxy(hs_name, vm_uuid, proxy_index):
    """管理员删除反向代理配置"""
    return rest_manager.admin_delete_proxy(hs_name, vm_uuid, proxy_index)


# ============================================================================
# 数据盘管理API
# ============================================================================
@app.route('/api/client/hdd/detail/<hs_name>/<vm_uuid>', methods=['GET'])
@require_auth
def api_get_vm_hdds(hs_name, vm_uuid):
    """获取虚拟机数据盘列表"""
    return rest_manager.get_vm_hdds(hs_name, vm_uuid)

@app.route('/api/client/hdd/mount/<hs_name>/<vm_uuid>', methods=['POST'])
@require_auth
def api_mount_vm_hdd(hs_name, vm_uuid):
    """挂载数据盘到虚拟机"""
    return rest_manager.mount_vm_hdd(hs_name, vm_uuid)


@app.route('/api/client/hdd/unmount/<hs_name>/<vm_uuid>', methods=['POST'])
@require_auth
def api_unmount_vm_hdd(hs_name, vm_uuid):
    """卸载虚拟机数据盘"""
    return rest_manager.unmount_vm_hdd(hs_name, vm_uuid)


@app.route('/api/client/hdd/transfer/<hs_name>/<vm_uuid>', methods=['POST'])
@require_auth
def api_transfer_vm_hdd(hs_name, vm_uuid):
    """移交数据盘所有权"""
    return rest_manager.transfer_vm_hdd(hs_name, vm_uuid)


@app.route('/api/client/hdd/delete/<hs_name>/<vm_uuid>', methods=['DELETE'])
@require_auth
def api_delete_vm_hdd(hs_name, vm_uuid):
    """删除虚拟机数据盘"""
    return rest_manager.delete_vm_hdd(hs_name, vm_uuid)


# ============================================================================
# ISO管理API
# ============================================================================
@app.route('/api/client/isos/detail/<hs_name>/<vm_uuid>', methods=['GET'])
@require_auth
def api_get_vm_isos(hs_name, vm_uuid):
    """获取虚拟机ISO挂载列表"""
    return rest_manager.get_vm_isos(hs_name, vm_uuid)

@app.route('/api/client/iso/mount/<hs_name>/<vm_uuid>', methods=['POST'])
@require_auth
def api_mount_vm_iso(hs_name, vm_uuid):
    """挂载ISO镜像到虚拟机"""
    return rest_manager.mount_vm_iso(hs_name, vm_uuid)


@app.route('/api/client/iso/unmount/<hs_name>/<vm_uuid>/<iso_name>', methods=['DELETE'])
@require_auth
def api_unmount_vm_iso(hs_name, vm_uuid, iso_name):
    """卸载虚拟机ISO镜像"""
    return rest_manager.unmount_vm_iso(hs_name, vm_uuid, iso_name)


# ============================================================================
# USB管理API
# ============================================================================
@app.route('/api/client/usb/mount/<hs_name>/<vm_uuid>', methods=['POST'])
@require_auth
def api_mount_vm_usb(hs_name, vm_uuid):
    """挂载USB设备到虚拟机"""
    return rest_manager.mount_vm_usb(hs_name, vm_uuid)


@app.route('/api/client/usb/delete/<hs_name>/<vm_uuid>/<usb_key>', methods=['DELETE'])
@require_auth
def api_unmount_vm_usb(hs_name, vm_uuid, usb_key):
    """卸载虚拟机USB设备"""
    return rest_manager.unmount_vm_usb(hs_name, vm_uuid, usb_key)


# ============================================================================
# 备份管理API
# ============================================================================
@app.route('/api/client/backup/detail/<hs_name>/<vm_uuid>', methods=['GET'])
@require_auth
def api_get_vm_backups(hs_name, vm_uuid):
    """获取虚拟机备份列表"""
    return rest_manager.get_vm_backups(hs_name, vm_uuid)

@app.route('/api/client/backup/create/<hs_name>/<vm_uuid>', methods=['POST'])
@require_auth
def api_create_vm_backup(hs_name, vm_uuid):
    """创建虚拟机备份"""
    return rest_manager.create_vm_backup(hs_name, vm_uuid)


@app.route('/api/client/backup/restore/<hs_name>/<vm_uuid>', methods=['POST'])
@require_auth
def api_restore_vm_backup(hs_name, vm_uuid):
    """还原虚拟机备份"""
    return rest_manager.restore_vm_backup(hs_name, vm_uuid)


@app.route('/api/client/backup/delete/<hs_name>/<vm_uuid>', methods=['DELETE'])
@require_auth
def api_delete_vm_backup(hs_name, vm_uuid):
    """删除虚拟机备份"""
    return rest_manager.delete_vm_backup(hs_name, vm_uuid)


@app.route('/api/server/backup/scan/<hs_name>', methods=['POST'])
@require_auth
def api_scan_backups(hs_name):
    """扫描主机备份文件"""
    return rest_manager.scan_backups(hs_name)


# ============================================================================
# 用户管理API - /api/users
# ============================================================================

@app.route('/api/system/recalculate-quotas', methods=['POST'])
@require_auth
def api_recalculate_quotas():
    """手动触发用户资源配额重新计算"""
    try:
        hs_manage.recalculate_user_quotas()
        return api_response_wrapper(200, '资源配额重新计算完成')
    except Exception as e:
        logger.error(f"手动重新计算资源配额失败: {e}")
        return api_response_wrapper(500, f'重新计算失败: {str(e)}')


@app.route('/api/users/current', methods=['GET'])
@require_auth
def api_get_current_user():
    """获取当前用户信息"""
    try:
        # # 检查Bearer Token
        # auth_header = axio.headers.get('Authorization', '')
        # if auth_header.startswith('Bearer '):
        #     # Token登录，返回管理员用户信息
        #     return api_response_wrapper(200, '获取成功', {
        #         'id': 1,
        #         'username': 'admin',
        #         'is_admin': True,
        #         'is_token_login': True,
        #         'used_cpu': 0,
        #         'used_ram': 0,
        #         'used_ssd': 0,
        #         'quota_cpu': 999999,
        #         'quota_ram': 999999,
        #         'quota_ssd': 999999,
        #         # 添加流量、带宽、NAT、WEB配额
        #         'used_traffic': 0,
        #         'quota_traffic': 999999,
        #         'used_upload_bw': 0,
        #         'quota_upload_bw': 1000,
        #         'used_download_bw': 0,
        #         'quota_download_bw': 1000,
        #         'used_nat': 0,
        #         'quota_nat': 100,
        #         'used_web': 0,
        #         'quota_web': 50,
        #         # 添加IP配额
        #         'used_nat_ips': 0,
        #         'quota_nat_ips': 10,
        #         'used_pub_ips': 0,
        #         'quota_pub_ips': 10,
        #         'assigned_hosts': []
        #     })
        
        # 检查Session登录
        if session.get('logged_in'):
            user_id = session.get('user_id')
            user_data = db.get_user_by_id(user_id)
            if user_data:
                # 计算IP使用量
                if rest_manager and hs_manage:
                    ip_usage = rest_manager._calculate_user_ip_usage(user_data.get('username', ''))
                    
                    # 添加IP使用量信息到用户数据
                    user_data['used_nat_ips'] = ip_usage['used_nat_ips']
                    user_data['used_pub_ips'] = ip_usage['used_pub_ips']
                
                # 移除敏感信息
                user_data.pop('password', None)
                user_data.pop('verify_token', None)
                # 解析JSON字段
                if isinstance(user_data.get('assigned_hosts'), str):
                    try:
                        user_data['assigned_hosts'] = json.loads(user_data['assigned_hosts'])
                    except:
                        user_data['assigned_hosts'] = []
                return api_response_wrapper(200, '获取成功', user_data)
        
        return api_response_wrapper(401, '未授权访问')
    except Exception as e:
        logger.error(f"获取当前用户信息失败: {e}")
        return api_response_wrapper(500, f'获取失败: {str(e)}')


@app.route('/api/users', methods=['GET'])
@require_admin
def api_get_users():
    """获取所有用户列表"""
    try:
        users = db.get_all_users()
        # 移除敏感信息
        for user in users:
            user.pop('password', None)
            user.pop('verify_token', None)
            # 解析JSON字段
            if isinstance(user.get('assigned_hosts'), str):
                try:
                    user['assigned_hosts'] = json.loads(user['assigned_hosts'])
                except:
                    user['assigned_hosts'] = []
        return api_response_wrapper(200, '获取成功', users)
    except Exception as e:
        logger.error(f"获取用户列表失败: {e}")
        return api_response_wrapper(500, f'获取失败: {str(e)}')


@app.route('/api/users', methods=['POST'])
@require_admin
def api_create_user():
    """创建新用户"""
    try:
        data = request.get_json()
        if not data:
            return api_response_wrapper(400, '无效的请求数据')
        
        # 获取必需字段
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        
        # 验证必需字段
        if not username or not email or not password:
            return api_response_wrapper(400, '用户名、邮箱和密码不能为空')
        
        if len(username) < 3 or len(username) > 20:
            return api_response_wrapper(400, '用户名长度必须在3-20个字符之间')
        
        # 禁止使用admin作为用户名
        if username.lower() == 'admin':
            return api_response_wrapper(400, '不能使用admin作为用户名')
        
        if len(password) < 6:
            return api_response_wrapper(400, '密码长度至少6个字符')
        
        # 检查用户名是否已存在
        if db.get_user_by_username(username):
            return api_response_wrapper(400, '用户名已存在')
        
        # 检查邮箱是否已存在
        if db.get_user_by_email(email):
            return api_response_wrapper(400, '邮箱已被注册')
        
        # 加密密码
        hashed_password = UserManager.hash_password(password)
        
        # 创建用户（只传入基本字段）
        user_id = db.create_user(username, hashed_password, email)
        if not user_id:
            return api_response_wrapper(500, '创建用户失败，请重试')
        
        # 准备要更新的其他字段
        update_data = {
            'is_admin': data.get('is_admin', 0),
            'is_active': data.get('is_active', 1),
            'can_create_vm': data.get('can_create_vm', 0),
            'can_modify_vm': data.get('can_modify_vm', 0),
            'can_delete_vm': data.get('can_delete_vm', 0),
            'quota_cpu': data.get('quota_cpu', 0),
            'quota_ram': data.get('quota_ram', 0),
            'quota_ssd': data.get('quota_ssd', 0),
            'quota_gpu': data.get('quota_gpu', 0),
            'quota_nat_ports': data.get('quota_nat_ports', 0),
            'quota_web_proxy': data.get('quota_web_proxy', 0),
            'quota_bandwidth_up': data.get('quota_bandwidth_up', 0),
            'quota_bandwidth_down': data.get('quota_bandwidth_down', 0),
            'quota_traffic': data.get('quota_traffic', 0),
            'assigned_hosts': data.get('assigned_hosts', [])
        }
        
        # 更新用户的权限和配额信息
        success = db.update_user(user_id, **update_data)
        if not success:
            # 如果更新失败，删除已创建的用户
            db.delete_user(user_id)
            return api_response_wrapper(500, '更新用户权限和配额失败')
        
        # 直接验证邮箱（管理员创建的用户不需要邮箱验证）
        db.verify_user_email(user_id)
        
        return api_response_wrapper(200, '用户创建成功', {'user_id': user_id})
        
    except Exception as e:
        logger.error(f"创建用户失败: {e}")
        return api_response_wrapper(500, f'创建失败: {str(e)}')


@app.route('/api/users/<int:user_id>', methods=['GET'])
@require_admin
def api_get_user(user_id):
    """获取单个用户信息"""
    try:
        user = db.get_user_by_id(user_id)
        if not user:
            return api_response_wrapper(404, '用户不存在')
        
        # 移除敏感信息
        user.pop('password', None)
        user.pop('verify_token', None)
        
        # 解析JSON字段
        if isinstance(user.get('assigned_hosts'), str):
            try:
                user['assigned_hosts'] = json.loads(user['assigned_hosts'])
            except:
                user['assigned_hosts'] = []
        
        return api_response_wrapper(200, '获取成功', user)
    except Exception as e:
        logger.error(f"获取用户信息失败: {e}")
        traceback.print_exc()
        return api_response_wrapper(500, f'获取失败: {str(e)}')


@app.route('/api/users/<int:user_id>', methods=['PUT'])
@require_admin
def api_update_user(user_id):
    """更新用户信息"""
    try:
        data = request.get_json()
        if not data:
            return api_response_wrapper(400, '无效的请求数据')
        
        # 更新用户
        success = db.update_user(user_id, **data)
        if success:
            return api_response_wrapper(200, '更新成功')
        else:
            return api_response_wrapper(500, '更新失败')
    except Exception as e:
        logger.error(f"更新用户失败: {e}")
        return api_response_wrapper(500, f'更新失败: {str(e)}')


@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@require_admin
def api_delete_user(user_id):
    """删除用户"""
    try:
        success = db.delete_user(user_id)
        if success:
            return api_response_wrapper(200, '删除成功')
        else:
            return api_response_wrapper(500, '删除失败')
    except Exception as e:
        logger.error(f"删除用户失败: {e}")
        return api_response_wrapper(500, f'删除失败: {str(e)}')


# ============================================================================
# 系统设置API
# ============================================================================

@app.route('/api/system/test-email', methods=['POST'])
@require_admin
def test_email():
    """测试邮件发送"""
    try:
        data = request.get_json()
        test_email = data.get('test_email')
        subject = data.get('subject', 'OpenIDCS - 测试邮件')
        body = data.get('body', '这是一封测试邮件')
        resend_email = data.get('resend_email')
        resend_apikey = data.get('resend_apikey')
        
        if not test_email or not resend_email or not resend_apikey:
            return jsonify({'code': 400, 'msg': '请提供完整的邮件配置信息'})
        
        if not subject or not body:
            return jsonify({'code': 400, 'msg': '请提供邮件标题和正文'})
        
        # 验证邮箱格式
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, test_email) or not re.match(email_pattern, resend_email):
            return jsonify({'code': 400, 'msg': '邮箱地址格式不正确'})
        
        # 发送测试邮件
        email_service = EmailService(
            api_key=resend_apikey,
            from_email=resend_email
        )
        
        success = email_service.send_test_email(test_email, subject, body)
        if success:
            return jsonify({'code': 200, 'msg': '测试邮件发送成功'})
        else:
            return jsonify({'code': 500, 'msg': '测试邮件发送失败'})
            
    except Exception as e:
        logger.error(f"测试邮件发送失败: {e}")
        return jsonify({'code': 500, 'msg': '测试邮件发送失败'})

@app.route('/api/system/settings', methods=['GET'])
@require_admin
def api_get_system_settings():
    """获取系统设置"""
    try:
        settings = db.get_system_settings()
        return api_response_wrapper(200, '获取成功', settings)
    except Exception as e:
        logger.error(f"获取系统设置失败: {e}")
        return api_response_wrapper(500, f'获取失败: {str(e)}')


@app.route('/api/system/settings', methods=['POST'])
@require_admin
def api_update_system_settings():
    """更新系统设置"""
    try:
        data = request.get_json()
        if not data:
            return api_response_wrapper(400, '无效的请求数据')
        
        success = db.update_system_settings(**data)
        if success:
            return api_response_wrapper(200, '更新成功')
        else:
            return api_response_wrapper(500, '更新失败')
    except Exception as e:
        logger.error(f"更新系统设置失败: {e}")
        return api_response_wrapper(500, f'更新失败: {str(e)}')


# ============================================================================
# 国际化/语言API
# ============================================================================

# 获取可用语言列表 ##################################################################
@app.route('/api/i18n/languages', methods=['GET'])
def api_get_available_languages():
    """获取所有可用的语言列表（无需认证）"""
    try:
        from HostModule.Translation import get_translation
        translation = get_translation()
        languages = translation.get_available_languages()
        
        # 返回语言列表及其显示名称
        # 语言代码到本地化名称的映射
        language_names = {
            'zh-cn': {'name': '简体中文', 'native': '简体中文'},
            'zh-tw': {'name': '繁體中文', 'native': '繁體中文'},
            'en-us': {'name': 'English', 'native': 'English'},
            'ja-jp': {'name': '日本語', 'native': '日本語'},
            'ko-kr': {'name': '한국어', 'native': '한국어'},
            'ar-ar': {'name': 'العربية', 'native': 'العربية'},
            'de-de': {'name': 'Deutsch', 'native': 'Deutsch'},
            'es-es': {'name': 'Español', 'native': 'Español'},
            'fr-fr': {'name': 'Français', 'native': 'Français'},
            'it-it': {'name': 'Italiano', 'native': 'Italiano'},
            'pt-br': {'name': 'Português', 'native': 'Português'},
            'ru-ru': {'name': 'Русский', 'native': 'Русский'},
            'hi-in': {'name': 'हिन्दी', 'native': 'हिन्दी'},
            'bn-bd': {'name': 'বাংলা', 'native': 'বাংলা'},
            'ur-pk': {'name': 'اردو', 'native': 'اردو'},
        }
        
        language_info = []
        for lang in languages:
            if lang in language_names:
                language_info.append({
                    'code': lang, 
                    'name': language_names[lang]['name'], 
                    'native': language_names[lang]['native']
                })
            else:
                # 对于未定义的语言，使用语言代码作为显示名称
                language_info.append({'code': lang, 'name': lang, 'native': lang})
        
        return api_response_wrapper(200, '获取成功', language_info)
    except Exception as e:
        logger.error(f"获取语言列表失败: {e}")
        return api_response_wrapper(500, f'获取失败: {str(e)}')


# 获取指定语言的翻译数据 ##############################################################
@app.route('/api/i18n/translations/<lang_code>', methods=['GET'])
def api_get_translations(lang_code):
    """获取指定语言的所有翻译数据（无需认证）"""
    try:
        from HostModule.Translation import get_translation
        translation = get_translation()
        translations = translation.get_language_data(lang_code)
        
        if not translations:
            return api_response_wrapper(404, f'语言 {lang_code} 不存在')
        
        return api_response_wrapper(200, '获取成功', translations)
    except Exception as e:
        logger.error(f"获取翻译数据失败: {e}")
        return api_response_wrapper(500, f'获取失败: {str(e)}')


# ============================================================================
# 定时任务
# ============================================================================
def cron_scheduler():
    """定时任务调度器，每分钟执行一次exe_cron"""
    try:
        hs_manage.exe_cron()
    except Exception as e:
        traceback.print_exc()
        logger.error(f"[Cron] 执行定时任务出错: {e}")

    # 设置下一次执行（60秒后）
    timer = threading.Timer(60, cron_scheduler)
    timer.daemon = True  # 设为守护线程，主程序退出时自动结束
    timer.start()


def start_cron_scheduler():
    """启动定时任务调度器，立即执行一次并开始定时循环（非阻塞）"""

    def initial_run():
        """初始执行，在单独线程中运行以避免阻塞启动"""
        try:
            hs_manage.exe_cron()
            logger.info("[Cron] 初始执行完成")
        except Exception as e:
            logger.error(f"[Cron] 初始执行出错: {e}")

        # 初始执行完成后，60秒后开始定时循环
        timer = threading.Timer(60, cron_scheduler)
        timer.daemon = True
        timer.start()

    logger.info("[Cron] 启动定时任务调度器...")
    # 在单独线程中执行初始化，不阻塞主程序启动
    init_thread = threading.Thread(target=initial_run, daemon=True)
    init_thread.start()
    logger.info("[Cron] 定时任务已启动（后台运行），每60秒执行一次")


# ============================================================================
# 启动服务
# ============================================================================
def init_app():
    """初始化应用"""
    # 加载已保存的配置
    try:
        logger.info("正在加载系统配置...")
        hs_manage.all_load()
        logger.info("系统配置加载完成")
    except Exception as e:
        logger.error(f"加载配置失败: {e}")
        # 如果是多进程相关错误，记录详细信息但不阻止启动
        if "multiprocessing" in str(e) or "process" in str(e).lower():
            logger.warning("检测到多进程相关错误，将在用户访问时重试加载")

    # 初始化翻译模块
    try:
        logger.info("正在加载翻译文件...")
        from HostModule.Translation import get_translation
        translation = get_translation()
        logger.info(f"翻译文件加载完成，已加载 {len(translation.get_available_languages())} 种语言")
    except Exception as e:
        logger.error(f"加载翻译文件失败: {e}")

    # 如果没有Token，生成一个
    if not hs_manage.bearer:
        hs_manage.set_pass()
        logger.info(f"已生成访问Token: {hs_manage.bearer}")

    # 初始化admin用户（如果不存在）
    try:
        admin_user = hs_manage.saving.get_user_by_username('admin')
        if not admin_user:
            # 使用token作为admin的密码
            admin_password = UserManager.hash_password(hs_manage.bearer)
            user_id = hs_manage.saving.create_user(
                username='admin',
                password=admin_password,
                email='admin@localhost',
                is_admin=True,
                is_active=True,
                email_verified=True,
                can_create_vm=True,
                can_modify_vm=True,
                can_delete_vm=True,
                # 设置默认配额（管理员不受限制）
                quota_cpu=9999,
                quota_ram=999999,
                quota_ssd=999999,
                quota_gpu=9999,
                quota_nat_ports=9999,
                quota_web_proxy=9999,
                quota_bandwidth_up=9999,
                quota_bandwidth_down=9999,
                quota_traffic=999999,
                assigned_hosts=[]
            )
            if user_id:
                logger.info(f"已创建admin用户，用户名: admin, 密码: {hs_manage.bearer}")
            else:
                logger.error("创建admin用户失败")
        else:
            logger.info("admin用户已存在，跳过创建")
    except Exception as e:
        logger.error(f"初始化admin用户失败: {e}")

    # 启动定时任务调度器
    try:
        start_cron_scheduler()
        logger.info("定时任务调度器启动成功")
    except Exception as e:
        logger.error(f"启动定时任务调度器失败: {e}")


if __name__ == '__main__':
    try:
        # 在Windows系统上支持多进程
        import multiprocessing
        multiprocessing.freeze_support()
        
        # 检测是否为打包后的环境
        is_frozen = getattr(sys, 'frozen', False)
        
        # ===== 首先配置 logger，确保日志系统正常工作 =====
        # 移除默认的 handler
        logger.remove()
        
        # 确保日志目录存在
        log_dir = os.path.join(project_root, 'DataSaving')
        os.makedirs(log_dir, exist_ok=True)
        
        # 添加控制台输出（始终显示）
        logger.add(
            sys.stderr,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            level="INFO"
        )
        
        # 添加文件输出
        log_file = os.path.join(log_dir, "log-main.log")
        logger.add(
            log_file,
            rotation="10 MB",
            retention="7 days",
            compression="zip",
            encoding="utf-8",
            level="DEBUG"
        )
        
        logger.info("=" * 60)
        logger.info("OpenIDCS Server 启动")
        logger.info(f"运行模式: {'打包模式 (Nuitka)' if is_frozen else '开发模式'}")
        logger.info(f"Python 版本: {sys.version}")
        logger.info(f"工作目录: {os.getcwd()}")
        logger.info(f"项目根目录: {project_root}")
        logger.info("=" * 60)
        
        # 初始化应用
        logger.info("正在初始化应用...")
        init_app()
        
        logger.info(f"\n{'=' * 60}")
        logger.info(f"OpenIDCS Server 启动中...")
        logger.info(f"运行模式: {'打包模式' if is_frozen else '开发模式'}")
        logger.info(f"访问地址: http://127.0.0.1:1880")
        logger.info(f"访问Token: {hs_manage.bearer}")
        logger.info(f"{'=' * 60}\n")
        
        # 打包后禁用调试模式，避免 Nuitka 兼容性问题
        if is_frozen:
            logger.info("使用生产模式启动 Flask 服务器...")
            app.run(host='0.0.0.0', port=1880, debug=False, use_reloader=False)
        else:
            # 开发环境可以使用调试模式和自动重载
            logger.info("使用调试模式启动 Flask 服务器（已启用自动重载）...")
            app.run(host='0.0.0.0', port=1880, debug=True, use_reloader=True)
    except KeyboardInterrupt:
        logger.info("\n程序被用户中断")
        sys.exit(0)
    except Exception as e:
        logger.error(f"\n程序启动失败: {e}")
        logger.error(f"错误详情:\n{traceback.format_exc()}")
        # 打包模式下，等待用户按键后再退出，以便查看错误信息
        if getattr(sys, 'frozen', False):
            input("\n按回车键退出...")
        sys.exit(1)