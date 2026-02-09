import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Form, Input, Button, Alert } from 'antd'
import { UserOutlined, LockOutlined, MailOutlined, UserAddOutlined, CheckCircleOutlined, CloseCircleOutlined, BulbOutlined, BulbFilled, BgColorsOutlined } from '@ant-design/icons'
import api from '@/utils/apis.ts'
import { useTheme } from '@/contexts/ThemeContext'

/**
 * 注册表单数据接口
 */
interface RegisterForm {
  username: string
  email: string
  password: string
  confirm_password: string
}

/**
 * 注册页面组件
 * 与WebDesigns/register.html保持一致的布局和样式
 */
function UserPostin() {
  const navigate = useNavigate()
  const { theme, toggleTheme, transparentMode, toggleTransparentMode } = useTheme()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string>('')
  const [success, setSuccess] = useState<string>('')

  /**
   * 处理注册提交
   * 对应静态页面的表单提交逻辑
   */
  const handleSubmit = async (values: RegisterForm) => {
    try {
      setLoading(true)
      setError('')
      setSuccess('')
      
      // 调用注册API - 对应静态页面的 /register 接口
      const response = await api.post('/register', {
        username: values.username,
        email: values.email,
        password: values.password,
      })
      
      // 处理响应
      if (response.code === 200) {
        setSuccess(response.msg || '注册成功！')
        // 2秒后跳转到登录页
        setTimeout(() => {
          navigate('/login')
        }, 2000)
      } else {
        setError(response.msg || '注册失败')
      }
    } catch (error: any) {
      setError(error.response?.data?.msg || '注册失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="register-page-container"
      style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '100vh',
        padding: '32px 0',
        background: transparentMode 
          ? `var(--bg-primary) url('https://images.524228.xyz/') center/cover no-repeat`
          : 'var(--bg-primary)',
      }}
    >
      {/* 主题切换按钮组 - 右上角 */}
      <div
        style={{
          position: 'fixed',
          top: '24px',
          right: '24px',
          display: 'flex',
          gap: '12px',
          zIndex: 1000,
        }}
      >
        {/* 透明模式切换按钮 */}
        <Button
          onClick={toggleTransparentMode}
          size="large"
          icon={<BgColorsOutlined />}
          style={{
            background: transparentMode ? 'linear-gradient(to right, #2563eb, #6366f1)' : 'var(--bg-card)',
            color: transparentMode ? '#ffffff' : 'var(--text-primary)',
            border: '1px solid var(--border-primary)',
            borderRadius: '12px',
            boxShadow: 'var(--shadow-glass)',
            backdropFilter: 'blur(20px)',
            WebkitBackdropFilter: 'blur(20px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '48px',
            height: '48px',
            padding: 0,
            transition: 'all 0.3s',
          }}
          title={transparentMode ? '关闭透明模式' : '开启透明模式'}
        />
        
        {/* 暗黑模式切换按钮 */}
        <Button
          onClick={toggleTheme}
          size="large"
          icon={theme === 'dark' ? <BulbFilled /> : <BulbOutlined />}
          style={{
            background: theme === 'dark' ? 'linear-gradient(to right, #2563eb, #6366f1)' : 'var(--bg-card)',
            color: theme === 'dark' ? '#ffffff' : 'var(--text-primary)',
            border: '1px solid var(--border-primary)',
            borderRadius: '12px',
            boxShadow: 'var(--shadow-glass)',
            backdropFilter: 'blur(20px)',
            WebkitBackdropFilter: 'blur(20px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '48px',
            height: '48px',
            padding: 0,
            transition: 'all 0.3s',
          }}
          title={theme === 'dark' ? '切换到浅色模式' : '切换到暗黑模式'}
        />
      </div>
      {/* 注册卡片容器 */}
      <div
        className="register-card glass-card"
        style={{
          background: 'var(--bg-card)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          borderRadius: '16px',
          boxShadow: 'var(--shadow-glass)',
          padding: '32px',
          width: '100%',
          maxWidth: '448px',
          border: '1px solid var(--border-primary)',
        }}
      >
        {/* 头部图标和标题 */}
        <div className="text-center mb-8">
          <div className="flex justify-center mb-4">
            <div className="bg-gradient-to-br from-blue-500 to-indigo-600 p-4 rounded-2xl shadow-lg">
              <UserAddOutlined className="text-white text-5xl" />
            </div>
          </div>
          <h1 className="text-3xl font-bold text-gray-800 dark:text-gray-100 mb-2">用户注册</h1>
          <p className="text-gray-600 dark:text-gray-300 flex items-center justify-center gap-2">
            <span className="iconify" data-icon="mdi:server-network"></span>
            OpenIDCS 虚拟化管理平台
          </p>
        </div>

        {/* 注册表单 */}
        <Form
          name="register"
          onFinish={handleSubmit}
          autoComplete="off"
          layout="vertical"
          className="space-y-4"
        >
          {/* 用户名输入框 */}
          <Form.Item
            label={
              <span className="flex items-center gap-2 text-sm font-medium text-gray-700">
                <UserOutlined className="text-blue-500" />
                用户名
              </span>
            }
            name="username"
            rules={[
              { required: true, message: '请输入用户名' },
              { min: 3, max: 20, message: '用户名长度为3-20位' },
              { pattern: /^[a-zA-Z0-9_]+$/, message: '只能包含字母、数字或下划线' },
            ]}
          >
            <Input
              className="px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent shadow-sm transition-all duration-200"
              placeholder="3-20位字母、数字或下划线"
            />
          </Form.Item>

          {/* 邮箱输入框 */}
          <Form.Item
            label={
              <span className="flex items-center gap-2 text-sm font-medium text-gray-700">
                <MailOutlined className="text-blue-500" />
                邮箱
              </span>
            }
            name="email"
            rules={[
              { required: true, message: '请输入邮箱' },
              { type: 'email', message: '请输入有效的邮箱地址' },
            ]}
          >
            <Input
              className="px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent shadow-sm transition-all duration-200"
              placeholder="请输入邮箱地址"
            />
          </Form.Item>

          {/* 密码输入框 */}
          <Form.Item
            label={
              <span className="flex items-center gap-2 text-sm font-medium text-gray-700">
                <LockOutlined className="text-blue-500" />
                密码
              </span>
            }
            name="password"
            rules={[
              { required: true, message: '请输入密码' },
              { min: 6, message: '密码至少6位字符' },
            ]}
          >
            <Input.Password
              className="px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent shadow-sm transition-all duration-200"
              placeholder="至少6位字符"
            />
          </Form.Item>

          {/* 确认密码输入框 */}
          <Form.Item
            label={
              <span className="flex items-center gap-2 text-sm font-medium text-gray-700">
                <LockOutlined className="text-blue-500" />
                确认密码
              </span>
            }
            name="confirm_password"
            dependencies={['password']}
            rules={[
              { required: true, message: '请确认密码' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('password') === value) {
                    return Promise.resolve()
                  }
                  return Promise.reject(new Error('两次输入的密码不一致'))
                },
              }),
            ]}
          >
            <Input.Password
              className="px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent shadow-sm transition-all duration-200"
              placeholder="请再次输入密码"
            />
          </Form.Item>

          {/* 错误提示 */}
          {error && (
            <Alert
              message={error}
              type="error"
              icon={<CloseCircleOutlined />}
              showIcon
              closable
              onClose={() => setError('')}
              className="mb-4"
            />
          )}

          {/* 成功提示 */}
          {success && (
            <Alert
              message={success}
              type="success"
              icon={<CheckCircleOutlined />}
              showIcon
              className="mb-4"
            />
          )}

          {/* 注册按钮 */}
          <Form.Item className="mb-0">
            <Button
              type="primary"
              htmlType="submit"
              loading={loading}
              icon={<UserAddOutlined />}
              className="w-full bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 h-12 text-base font-semibold rounded-lg shadow-md hover:shadow-lg transition-all duration-300"
            >
              注 册
            </Button>
          </Form.Item>

          {/* 底部链接 */}
          <div className="text-center pt-4">
            <Link to="/login" className="text-sm text-blue-600 hover:text-blue-700">
              已有账号？立即登录
            </Link>
          </div>
        </Form>
      </div>
    </div>
  )
}

export default UserPostin
