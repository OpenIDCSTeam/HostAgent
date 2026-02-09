import { useState, useEffect } from 'react'
import { useNavigate, Link, useSearchParams } from 'react-router-dom'
import { Form, Input, Button, message, Progress } from 'antd'
import { LockOutlined, EyeOutlined, EyeInvisibleOutlined } from '@ant-design/icons'
import api from '@/utils/apis.ts'

/**
 * 重置密码页面组件
 */
function UserPasswd() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [loading, setLoading] = useState(false)
  const [form] = Form.useForm()
  
  // 从URL获取token
  const token = searchParams.get('token')
  
  const [passwordStrength, setPasswordStrength] = useState({
    score: 0,
    text: '-',
    color: '#d9d9d9',
    percent: 0
  })
  const [confirmPasswordError, setConfirmPasswordError] = useState<string>('')

  /**
   * 检查token有效性
   */
  useEffect(() => {
    if (!token) {
      message.error('重置链接无效')
      setTimeout(() => {
        navigate('/login')
      }, 2000)
    }
  }, [token, navigate])

  /**
   * 计算密码强度
   */
  const calculatePasswordStrength = (password: string) => {
    let strength = 0
    let strengthText = '-'
    let strengthColor = '#d9d9d9'
    
    if (!password) {
      setPasswordStrength({ score: 0, text: '-', color: '#d9d9d9', percent: 0 })
      return
    }
    
    // 长度检查
    if (password.length >= 6) strength++
    if (password.length >= 10) strength++
    
    // 大小写字母
    if (/[a-z]/.test(password) && /[A-Z]/.test(password)) strength++
    
    // 数字
    if (/\d/.test(password)) strength++
    
    // 特殊字符
    if (/[^a-zA-Z\d]/.test(password)) strength++

    // 根据强度设置文本和颜色
    switch (strength) {
      case 0:
      case 1:
        strengthText = '弱'
        strengthColor = '#ff4d4f'
        break
      case 2:
      case 3:
        strengthText = '中等'
        strengthColor = '#faad14'
        break
      case 4:
      case 5:
        strengthText = '强'
        strengthColor = '#52c41a'
        break
    }

    const percentage = (strength / 5) * 100
    setPasswordStrength({
      score: strength,
      text: strengthText,
      color: strengthColor,
      percent: percentage
    })
  }

  /**
   * 重置密码
   */
  const handleResetPassword = async (values: { new_password: string; confirm_password: string }) => {
    try {
      setLoading(true)
      
      // 调用重置密码API
      const response = await api.resetPassword({
        token: token!,
        new_password: values.new_password,
        confirm_password: values.confirm_password
      })
      
      if (response.code === 200) {
        message.success('密码重置成功，请登录')
        setTimeout(() => {
          navigate('/login?reset=1')
        }, 1500)
      } else {
        message.error(response.msg || '密码重置失败')
      }
    } catch (error) {
      console.error('密码重置失败:', error)
      message.error('密码重置失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="h-auto flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-gray-900 dark:to-gray-800 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        {/* 顶部图标和标题 */}
        <div className="text-center">
          <div className="mx-auto h-16 w-16 bg-blue-600 dark:bg-blue-500 rounded-xl flex items-center justify-center shadow-lg">
            <LockOutlined className="text-white text-3xl" style={{ fontSize: 32 }} />
          </div>
          <h2 className="mt-6 text-3xl font-extrabold text-gray-900 dark:text-white">
            重置密码
          </h2>
          <p className="mt-2 text-sm text-gray-600 dark:text-gray-300">
            请输入您的新密码
          </p>
        </div>

        {/* 表单卡片 */}
        <div className="glass-card p-8">
          <Form
            form={form}
            name="resetPassword"
            onFinish={handleResetPassword}
            autoComplete="off"
            layout="vertical"
            className="space-y-6"
          >
            {/* 新密码输入框 */}
            <Form.Item
              label={
                <span className="text-sm font-medium text-gray-700 dark:text-gray-200">
                  新密码 <span className="text-red-500">*</span>
                </span>
              }
              name="new_password"
              rules={[
                { required: true, message: '请输入新密码' },
                { min: 6, message: '密码长度不能少于6位' },
              ]}
            >
              <Input.Password
                placeholder="请输入新密码（至少6位）"
                className="rounded-lg"
                iconRender={(visible) => (visible ? <EyeInvisibleOutlined /> : <EyeOutlined />)}
                onChange={(e) => calculatePasswordStrength(e.target.value)}
              />
            </Form.Item>

            {/* 确认密码输入框 */}
            <Form.Item
              label={
                <span className="text-sm font-medium text-gray-700 dark:text-gray-200">
                  确认新密码 <span className="text-red-500">*</span>
                </span>
              }
              name="confirm_password"
              dependencies={['new_password']}
              rules={[
                { required: true, message: '请再次输入新密码' },
                { min: 6, message: '密码长度不能少于6位' },
                ({ getFieldValue }) => ({
                  validator(_, value) {
                    if (!value || getFieldValue('new_password') === value) {
                      setConfirmPasswordError('')
                      return Promise.resolve()
                    }
                    setConfirmPasswordError('两次输入的密码不一致')
                    return Promise.reject(new Error('两次输入的密码不一致'))
                  },
                }),
              ]}
              validateStatus={confirmPasswordError ? 'error' : ''}
              help={confirmPasswordError}
            >
              <Input.Password
                placeholder="请再次输入新密码"
                className="rounded-lg"
                iconRender={(visible) => (visible ? <EyeInvisibleOutlined /> : <EyeOutlined />)}
                onChange={(e) => {
                  const newPassword = form.getFieldValue('new_password')
                  if (e.target.value && newPassword !== e.target.value) {
                    setConfirmPasswordError('两次输入的密码不一致')
                  } else {
                    setConfirmPasswordError('')
                  }
                }}
              />
            </Form.Item>

            {/* 密码强度指示器 */}
            <div>
              <div className="flex items-center justify-between text-sm mb-1">
                <span className="text-gray-600 dark:text-gray-300">密码强度</span>
                <span className="font-medium" style={{ color: passwordStrength.color }}>
                  {passwordStrength.text}
                </span>
              </div>
              <Progress
                percent={passwordStrength.percent}
                strokeColor={passwordStrength.color}
                showInfo={false}
                size="small"
              />
            </div>

            {/* 提交按钮 */}
            <Form.Item className="mb-0">
              <Button
                type="primary"
                htmlType="submit"
                loading={loading}
                block
                size="large"
                className="rounded-lg bg-blue-600 hover:bg-blue-700"
                icon={<LockOutlined />}
              >
                重置密码
              </Button>
            </Form.Item>

            {/* 返回登录链接 */}
            <div className="text-center">
              <Link 
                to="/login" 
                className="text-sm text-blue-600 dark:text-blue-400 hover:text-blue-500 dark:hover:text-blue-300 transition"
              >
                返回登录
              </Link>
            </div>
          </Form>
        </div>

        {/* 底部提示信息 */}
        <div className="text-center text-xs text-gray-500 dark:text-gray-400">
          <p>如果您遇到问题，请联系管理员</p>
        </div>
      </div>
    </div>
  )
}

export default UserPasswd