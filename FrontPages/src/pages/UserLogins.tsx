import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Form, Input, Button, Modal, message, Alert, Dropdown } from 'antd'
import { UserOutlined, LockOutlined, KeyOutlined, LoginOutlined, MailOutlined, InfoCircleOutlined, BulbOutlined, BulbFilled, BgColorsOutlined, TranslationOutlined, SwapOutlined } from '@ant-design/icons'
import { useUserStore } from '@/utils/data.ts'
import api from '@/utils/apis.ts'
import { useTheme } from '@/contexts/ThemeContext'
import { changeLanguage, getAvailableLanguages, getCurrentLanguage } from '@/utils/i18n.ts'
import type { MenuProps } from 'antd'

/**
 * 登录表单数据接口
 */
interface LoginForm {
  username: string
  password: string
}

/**
 * Token登录表单数据接口
 */
interface TokenLoginForm {
  token: string
}

/**
 * 找回密码表单数据接口
 */
interface ForgotPasswordForm {
  email: string
}

/**
 * 登录页面组件
 */
function UserLogins() {
  const navigate = useNavigate()
  const { setUser, setToken } = useUserStore()
  const { theme, toggleTheme, transparentMode, toggleTransparentMode } = useTheme()
  const [loading, setLoading] = useState(false)
  const [loginType, setLoginType] = useState<'user' | 'token'>('user') // 登录方式：用户登录或Token登录
  const [errorMsg, setErrorMsg] = useState('') // 错误提示信息
  const [forgotPasswordVisible, setForgotPasswordVisible] = useState(false) // 找回密码模态框显示状态
  const [forgotPasswordLoading, setForgotPasswordLoading] = useState(false) // 找回密码加载状态
  const [userForm] = Form.useForm() // 用户登录表单实例
  const [tokenForm] = Form.useForm() // Token登录表单实例
  const [forgotPasswordForm] = Form.useForm() // 找回密码表单实例
  const [currentLang, setCurrentLang] = useState('zh-cn') // 当前语言
  const [languages, setLanguages] = useState<any[]>([]) // 可用语言列表

  // 初始化语言状态
  useEffect(() => {
    setCurrentLang(getCurrentLanguage())
    setLanguages(getAvailableLanguages())

    // 监听语言变更事件
    const handleLangChange = (e: any) => {
      setCurrentLang(e.detail.language)
    }
    window.addEventListener('languageChanged', handleLangChange)
    
    // 监听语言列表加载完成事件（替代轮询）
    const handleLangsLoaded = (e: any) => {
      setLanguages(e.detail.languages)
      setCurrentLang(getCurrentLanguage())
    }
    window.addEventListener('languagesLoaded', handleLangsLoaded)
    
    return () => {
      window.removeEventListener('languageChanged', handleLangChange)
      window.removeEventListener('languagesLoaded', handleLangsLoaded)
    }
  }, [])

  // 语言菜单项
  const languageMenuItems: MenuProps['items'] = languages.map(lang => ({
    key: lang.code,
    label: lang.native || lang.name,
    icon: lang.code === currentLang ? <SwapOutlined /> : undefined,
  }))

  /**
   * 处理用户名密码登录提交
   */
  const handleUserLogin = async (values: LoginForm) => {
    try {
      setLoading(true)
      setErrorMsg('')
      
      // 调用登录API
      const response = await api.login({
        login_type: 'user',
        username: values.username,
        password: values.password,
      })
      
      // 保存用户信息和token
      if (response.data?.token) {
        setToken(response.data.token)
      }
      // 优先用后端返回的user_info，否则构造基础对象保证isAuthenticated=true
      const userInfo = response.data?.user_info || { username: values.username, is_admin: false }
      setUser(userInfo as any)
      
      message.success('登录成功')
      // 根据后端返回的redirect跳转，或根据is_admin判断
      const redirectTo = response.data?.redirect || (userInfo.is_admin ? '/dashboard' : '/user/dashboard')
      navigate(redirectTo)
    } catch (error: any) {
      const errMsg = error?.response?.data?.msg || '登录失败，请检查用户名和密码'
      setErrorMsg(errMsg)
      // 4秒后自动隐藏错误提示
      setTimeout(() => setErrorMsg(''), 4000)
      setLoading(false)
    }
  }

  /**
   * 处理Token登录提交
   */
  const handleTokenLogin = async (values: TokenLoginForm) => {
    try {
      setLoading(true)
      setErrorMsg('')
      
      // 调用登录API
      const response = await api.login({
        login_type: 'token',
        token: values.token,
      })
      
      // 保存用户信息和token
      if (response.data?.token) {
        setToken(response.data.token)
      }
      // 优先用后端返回的user_info，否则构造基础对象保证isAuthenticated=true
      const userInfo = response.data?.user_info || { username: 'admin', is_admin: true }
      setUser(userInfo as any)
      
      message.success('登录成功')
      const redirectTo = response.data?.redirect || '/dashboard'
      navigate(redirectTo)
    } catch (error: any) {
      const errMsg = error?.response?.data?.msg || 'Token登录失败，请检查Token是否正确'
      setErrorMsg(errMsg)
      // 4秒后自动隐藏错误提示
      setTimeout(() => setErrorMsg(''), 4000)
      setLoading(false)
    }
  }

  /**
   * 切换登录方式
   */
  const switchLoginType = (type: 'user' | 'token') => {
    setLoginType(type)
    setErrorMsg('')
  }

  /**
   * 打开找回密码模态框
   */
  const openForgotPasswordModal = () => {
    setForgotPasswordVisible(true)
    forgotPasswordForm.resetFields()
  }

  /**
   * 关闭找回密码模态框
   */
  const closeForgotPasswordModal = () => {
    setForgotPasswordVisible(false)
    forgotPasswordForm.resetFields()
  }

  /**
   * 处理找回密码提交
   */
  const handleForgotPassword = async (values: ForgotPasswordForm) => {
    try {
      setForgotPasswordLoading(true)
      
      // 调用找回密码API
      await api.forgotPassword(values.email)
      
      message.success('重置邮件已发送，请查收')
      // 3秒后自动关闭模态框
      setTimeout(() => {
        closeForgotPasswordModal()
      }, 3000)
    } catch (error: any) {
      const errorMessage = error?.response?.data?.msg || '发送失败，请重试'
      message.error(errorMessage)
    } finally {
      setForgotPasswordLoading(false)
    }
  }

  return (
    <div
      className="login-page-container"
      style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '100vh',
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
        {/* 语言切换按钮 */}
        <Dropdown
          menu={{
            items: languageMenuItems,
            onClick: ({key}) => changeLanguage(key)
          }}
          placement="bottomRight"
          overlayStyle={{
            zIndex: 20000,
            maxHeight: '400px',
            overflow: 'auto'
          }}
          getPopupContainer={(trigger) => trigger.parentElement || document.body}
        >
          <Button
            size="large"
            icon={<TranslationOutlined />}
            style={{
              background: 'var(--bg-card)',
              color: 'var(--text-primary)',
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
            title="切换语言"
          />
        </Dropdown>

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

      {/* 登录卡片 */}
      <div
        className="login-card glass-card"
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
        {/* 标题区域 */}
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          {/* Logo图标 */}
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 16 }}>
            <div
              style={{
                background: 'linear-gradient(to bottom right, #3b82f6, #6366f1)',
                padding: '16px',
                borderRadius: '16px',
                boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1)',
              }}
            >
              <svg
                style={{ width: 48, height: 48, color: 'white' }}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01"
                />
              </svg>
            </div>
          </div>
        <h1 className="text-3xl font-bold mb-2">
            OpenIDCS受控端
          </h1>
          <p style={{ color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
            <LockOutlined style={{ fontSize: 16 }} />
            虚拟化管理平台
          </p>
        </div>

        {/* 登录方式切换Tab */}
        <div
          style={{
            display: 'flex',
            gap: '8px',
            marginBottom: 24,
            background: 'var(--bg-secondary)',
            padding: '4px',
            borderRadius: '8px',
          }}
        >
          <button
            onClick={() => switchLoginType('user')}
            style={{
              flex: 1,
              padding: '8px 16px',
              borderRadius: '6px',
              border: 'none',
              cursor: 'pointer',
              transition: 'all 0.3s',
              background: loginType === 'user' ? 'linear-gradient(to right, #2563eb, #4f46e5)' : 'transparent',
              color: loginType === 'user' ? '#ffffff' : 'var(--text-primary)',
              fontFamily: 'var(--font-family)',
              fontSize: '14px',
              fontWeight: 500,
            }}
          >
            <UserOutlined style={{ marginRight: 4 }} />
            用户登录
          </button>
          <button
            onClick={() => switchLoginType('token')}
            style={{
              flex: 1,
              padding: '8px 16px',
              borderRadius: '6px',
              border: 'none',
              cursor: 'pointer',
              transition: 'all 0.3s',
              background: loginType === 'token' ? 'linear-gradient(to right, #2563eb, #4f46e5)' : 'transparent',
              color: loginType === 'token' ? '#ffffff' : 'var(--text-primary)',
              fontFamily: 'var(--font-family)',
              fontSize: '14px',
              fontWeight: 500,
            }}
          >
            <KeyOutlined style={{ marginRight: 4 }} />
            Token登录
          </button>
        </div>

        {/* 用户名密码登录表单 */}
        {loginType === 'user' && (
          <Form
            form={userForm}
            name="userLogin"
            onFinish={handleUserLogin}
            autoComplete="off"
            layout="vertical"
          >
            {/* 用户名输入框 */}
            <Form.Item
              label={
                <span style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 500, color: 'var(--text-primary)' }}>
                  <UserOutlined style={{ color: '#3b82f6' }} />
                  用户名
                </span>
              }
              name="username"
              rules={[{ required: true, message: '请输入用户名' }]}
            >
              <Input
                size="large"
                placeholder="请输入用户名"
                autoComplete="username"
                style={{
                  borderRadius: '8px',
                  boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
                }}
              />
            </Form.Item>

            {/* 密码输入框 */}
            <Form.Item
              label={
                <span style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 500, color: 'var(--text-primary)' }}>
                  <LockOutlined style={{ color: '#3b82f6' }} />
                  密码
                </span>
              }
              name="password"
              rules={[{ required: true, message: '请输入密码' }]}
            >
              <Input.Password
                size="large"
                placeholder="请输入密码"
                autoComplete="current-password"
                style={{
                  borderRadius: '8px',
                  boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
                }}
              />
            </Form.Item>

            {/* 错误提示 */}
            {errorMsg && (
              <Alert
                message={errorMsg}
                type="error"
                showIcon
                style={{ marginBottom: 16, borderRadius: '8px' }}
              />
            )}

            {/* 登录按钮 */}
            <Form.Item>
              <Button
                type="primary"
                htmlType="submit"
                loading={loading}
                block
                size="large"
                icon={<LoginOutlined />}
                style={{
                  background: 'linear-gradient(to right, #2563eb, #6366f1)',
                  border: 'none',
                  borderRadius: '8px',
                  fontWeight: 600,
                  height: '48px',
                  boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
                }}
              >
                登 录
              </Button>
            </Form.Item>

            {/* 底部链接 */}
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '14px' }}>
              <Link to="/register" style={{ color: 'var(--accent-primary)', textDecoration: 'none' }}>
                还没有账号？立即注册
              </Link>
              <a onClick={openForgotPasswordModal} style={{ color: 'var(--accent-primary)', cursor: 'pointer', textDecoration: 'none' }}>
                忘记密码？
              </a>
            </div>
          </Form>
        )}

        {/* Token登录表单 */}
        {loginType === 'token' && (
          <Form
            form={tokenForm}
            name="tokenLogin"
            onFinish={handleTokenLogin}
            autoComplete="off"
            layout="vertical"
          >
            {/* Token输入框 */}
            <Form.Item
              label={
                <span style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 500, color: 'var(--text-primary)' }}>
                  <KeyOutlined style={{ color: '#3b82f6' }} />
                  访问Token
                </span>
              }
              name="token"
              rules={[{ required: true, message: '请输入访问Token' }]}
            >
              <Input.Password
                size="large"
                placeholder="请输入访问Token"
                style={{
                  borderRadius: '8px',
                  boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
                }}
              />
            </Form.Item>

            {/* 错误提示 */}
            {errorMsg && (
              <Alert
                message={errorMsg}
                type="error"
                showIcon
                style={{ marginBottom: 16, borderRadius: '8px' }}
              />
            )}

            {/* 登录按钮 */}
            <Form.Item>
              <Button
                type="primary"
                htmlType="submit"
                loading={loading}
                block
                size="large"
                icon={<LoginOutlined />}
                style={{
                  background: 'linear-gradient(to right, #2563eb, #6366f1)',
                  border: 'none',
                  borderRadius: '8px',
                  fontWeight: 600,
                  height: '48px',
                  boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
                }}
              >
                登 录
              </Button>
            </Form.Item>

            {/* Token提示信息 */}
            <div
              style={{
                marginTop: 24,
                textAlign: 'center',
                fontSize: '14px',
                color: 'var(--text-secondary)',
              }}
            >
              <div
                className="glass-card"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 4,
                  background: 'var(--bg-secondary)',
                  backdropFilter: 'blur(10px)',
                  WebkitBackdropFilter: 'blur(10px)',
                  padding: '12px 16px',
                  borderRadius: '8px',
                  border: '1px solid var(--border-primary)',
                  color: 'var(--text-primary)',
                }}
              >
                <InfoCircleOutlined style={{ color: 'var(--accent-primary)' }} />
                <span style={{ color: 'var(--text-primary)' }}>启动服务时会在控制台显示访问Token</span>
              </div>
            </div>
          </Form>
        )}
      </div>

      {/* 找回密码模态框 */}
      <Modal
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div
              style={{
                width: 40,
                height: 40,
                background: '#2563eb',
                borderRadius: '8px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <MailOutlined style={{ color: 'white', fontSize: 20 }} />
            </div>
            <div>
              <div style={{ fontSize: 18, fontWeight: 600, color: 'var(--text-primary)' }}>找回密码</div>
              <div style={{ fontSize: 14, fontWeight: 400, color: 'var(--text-secondary)', marginTop: 2 }}>通过邮件重置您的密码</div>
            </div>
          </div>
        }
        open={forgotPasswordVisible}
        onCancel={closeForgotPasswordModal}
        footer={null}
        width={480}
      >
        <Form
          form={forgotPasswordForm}
          onFinish={handleForgotPassword}
          layout="vertical"
          style={{ marginTop: 24 }}
        >
          {/* 邮箱输入框 */}
          <Form.Item
            label="邮箱地址"
            name="email"
            rules={[
              { required: true, message: '请输入邮箱地址' },
              { type: 'email', message: '请输入有效的邮箱地址' },
            ]}
            extra="我们将向此邮箱发送密码重置链接"
          >
            <Input
              size="large"
              placeholder="请输入注册时使用的邮箱"
              style={{ borderRadius: '8px' }}
            />
          </Form.Item>

          {/* 按钮组 */}
          <Form.Item style={{ marginBottom: 0 }}>
            <div style={{ display: 'flex', gap: 12, paddingTop: 8 }}>
              <Button
                onClick={closeForgotPasswordModal}
                size="large"
                style={{ flex: 1, borderRadius: '8px' }}
              >
                取消
              </Button>
              <Button
                type="primary"
                htmlType="submit"
                loading={forgotPasswordLoading}
                size="large"
                icon={<MailOutlined />}
                style={{
                  flex: 1,
                  background: '#2563eb',
                  borderRadius: '8px',
                }}
              >
                发送重置邮件
              </Button>
            </div>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default UserLogins
