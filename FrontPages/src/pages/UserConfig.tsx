import { useState, useEffect } from 'react'
import { Card, Form, Input, Button, message, Tag, Progress, Row, Col } from 'antd'
import { 
  UserOutlined, 
  MailOutlined, 
  LockOutlined, 
  SafetyOutlined,
  PieChartOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined
} from '@ant-design/icons'
import api from '@/utils/apis.ts'
import type { User } from '@/types'
import PageHeader from '@/components/PageHeader'

/**
 * 个人设置页面
 */
function UserConfig() {
  const [userProfile, setUserProfile] = useState<User | null>(null)
  const [loading, setLoading] = useState(false)
  const [emailForm] = Form.useForm()
  const [passwordForm] = Form.useForm()

  /**
   * 加载用户信息
   */
  useEffect(() => {
    loadUserProfile()
  }, [])

  /**
   * 获取用户信息
   */
  const loadUserProfile = async () => {
    try {
      const response = await api.getCurrentUser()
      if (response.code === 200 && response.data) {
        setUserProfile(response.data)
      }
    } catch (error) {
      message.error('加载用户信息失败')
    }
  }

  /**
   * 修改邮箱
   */
  const handleChangeEmail = async (values: any) => {
    try {
      setLoading(true)
      const response = await api.changeEmail(values.new_email)
      if (response.code === 200) {
        message.success(response.msg || '验证邮件已发送，请查收并点击验证链接完成邮箱修改')
        emailForm.resetFields()
      } else {
        message.error(response.msg || '邮箱修改失败')
      }
    } catch (error) {
      message.error('邮箱修改失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  /**
   * 修改密码
   */
  const handleChangePassword = async (values: any) => {
    try {
      setLoading(true)
      const response = await api.changePassword(values.new_password, values.confirm_password)
      if (response.code === 200) {
        message.success('密码修改成功')
        passwordForm.resetFields()
      } else {
        message.error(response.msg || '密码修改失败')
      }
    } catch (error) {
      message.error('密码修改失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  /**
   * 计算资源使用百分比
   */
  const calculatePercent = (used: number, quota: number): number => {
    return quota > 0 ? Math.round((used / quota) * 100) : 0
  }

  /**
   * 获取进度条颜色
   */
  const getProgressColor = (percent: number): string => {
    if (percent > 90) return '#ef4444'
    if (percent > 70) return '#f59e0b'
    return '#3b82f6'
  }

  if (!userProfile) {
    return <div className="text-center py-8">加载中...</div>
  }

  return (
    <div className="p-6 min-h-screen">
      {/* 页面标题 */}
      <PageHeader
        icon={<UserOutlined />}
        title="个人账户设置"
        subtitle="管理您的个人信息和账户设置"
      />

      <Row gutter={[24, 24]}>
        {/* 左侧：个人信息和修改功能 */}
        <Col xs={24} lg={16}>
          {/* 个人信息 */}
          <Card 
            title={
              <span className="flex items-center gap-2">
                <UserOutlined className="text-blue-600 dark:text-blue-400" />
                <span>个人信息</span>
              </span>
            }
            className="glass-card mb-6"
          >
            <Row gutter={[16, 16]}>
              <Col xs={24} md={12}>
                <div>
                  <label className="block text-sm font-medium mb-1">用户名</label>
                  <Input value={userProfile.username} disabled />
                </div>
              </Col>
              <Col xs={24} md={12}>
                <div>
                  <label className="block text-sm font-medium mb-1">邮箱地址</label>
                  <Input value={userProfile.email} disabled />
                </div>
              </Col>
              <Col xs={24}>
                <div>
                  <label className="block text-sm font-medium mb-1">注册时间</label>
                  <Input
                    value={userProfile.created_at ? new Date(userProfile.created_at).toLocaleString('zh-CN') : '未知'} 
                    disabled 
                  />
                </div>
              </Col>
            </Row>
          </Card>

          {/* 修改邮箱 */}
          <Card 
            title={
              <span className="flex items-center gap-2">
                <MailOutlined className="text-blue-600 dark:text-blue-400" />
                <span>修改邮箱</span>
              </span>
            }
            className="glass-card mb-6"
          >
            <Form form={emailForm} layout="vertical" onFinish={handleChangeEmail}>
              <Form.Item label="当前邮箱">
                <Input value={userProfile.email} disabled />
              </Form.Item>
              <Form.Item
                name="new_email"
                label={<span>新邮箱地址 <span className="text-red-500">*</span></span>}
                rules={[
                  { required: true, message: '请输入新邮箱地址' },
                  { type: 'email', message: '请输入有效的邮箱地址' }
                ]}
              >
                <Input placeholder="请输入新邮箱地址" />
              </Form.Item>
              <Form.Item>
                <Button type="primary" htmlType="submit" loading={loading} icon={<MailOutlined />}>
                  修改邮箱
                </Button>
              </Form.Item>
            </Form>
          </Card>

          {/* 修改密码 */}
          <Card 
            title={
              <span className="flex items-center gap-2">
                <LockOutlined className="text-blue-600 dark:text-blue-400" />
                <span>修改密码</span>
              </span>
            }
            className="glass-card"
          >
            <Form form={passwordForm} layout="vertical" onFinish={handleChangePassword}>
              <Form.Item
                name="new_password"
                label={<span>新密码 <span className="text-red-500">*</span></span>}
                rules={[
                  { required: true, message: '请输入新密码' },
                  { min: 6, message: '密码至少6个字符' }
                ]}
              >
                <Input.Password placeholder="请输入新密码（至少6位）" />
              </Form.Item>
              <Form.Item
                name="confirm_password"
                label={<span>确认新密码 <span className="text-red-500">*</span></span>}
                dependencies={['new_password']}
                rules={[
                  { required: true, message: '请确认新密码' },
                  ({ getFieldValue }) => ({
                    validator(_, value) {
                      if (!value || getFieldValue('new_password') === value) {
                        return Promise.resolve()
                      }
                      return Promise.reject(new Error('新密码与确认密码不一致'))
                    },
                  }),
                ]}
              >
                <Input.Password placeholder="请再次输入新密码" />
              </Form.Item>
              <Form.Item>
                <Button type="primary" htmlType="submit" loading={loading} icon={<LockOutlined />}>
                  修改密码
                </Button>
              </Form.Item>
            </Form>
          </Card>
        </Col>

        {/* 右侧：权限和配额信息 */}
        <Col xs={24} lg={8}>
          {/* 权限信息 */}
          <Card 
            title={
              <span className="flex items-center gap-2">
                <SafetyOutlined className="text-blue-600 dark:text-blue-400" />
                <span>权限信息</span>
              </span>
            }
            className="glass-card mb-6"
          >
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-2">虚拟机权限</label>
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm flex items-center gap-2">
                      {userProfile.can_create_vm ? <CheckCircleOutlined className="text-green-500" /> : <CloseCircleOutlined className="text-red-500" />}
                      创建虚拟机
                    </span>
                    <Tag color={userProfile.can_create_vm ? 'success' : 'error'}>
                      {userProfile.can_create_vm ? '已开启' : '已关闭'}
                    </Tag>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm flex items-center gap-2">
                      {userProfile.can_modify_vm ? <CheckCircleOutlined className="text-green-500" /> : <CloseCircleOutlined className="text-red-500" />}
                      编辑虚拟机
                    </span>
                    <Tag color={userProfile.can_modify_vm ? 'success' : 'error'}>
                      {userProfile.can_modify_vm ? '已开启' : '已关闭'}
                    </Tag>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm flex items-center gap-2">
                      {userProfile.can_delete_vm ? <CheckCircleOutlined className="text-green-500" /> : <CloseCircleOutlined className="text-red-500" />}
                      删除虚拟机
                    </span>
                    <Tag color={userProfile.can_delete_vm ? 'success' : 'error'}>
                      {userProfile.can_delete_vm ? '已开启' : '已关闭'}
                    </Tag>
                  </div>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">账户状态</label>
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm">管理员</span>
                    <Tag color={userProfile.is_admin ? 'purple' : 'default'}>
                      {userProfile.is_admin ? '是' : '否'}
                    </Tag>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm">已启用</span>
                    <Tag color={userProfile.is_active ? 'success' : 'error'}>
                      {userProfile.is_active ? '已启用' : '已禁用'}
                    </Tag>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm">已验证</span>
                    <Tag color={userProfile.email_verified ? 'success' : 'warning'}>
                      {userProfile.email_verified ? '已验证' : '未验证'}
                    </Tag>
                  </div>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">分配的主机</label>
                {userProfile.assigned_hosts && userProfile.assigned_hosts.length > 0 ? (
                  <div className="space-y-1">
                    {userProfile.assigned_hosts.map((host, index) => (
                      <div key={index} className="text-sm">• {host}</div>
                    ))}
                  </div>
                ) : (
                  <span className="text-xs">未分配主机</span>
                )}
              </div>
            </div>
          </Card>

          {/* 资源配额 */}
          <Card 
            title={
              <span className="flex items-center gap-2">
                <PieChartOutlined className="text-blue-600 dark:text-blue-400" />
                <span>资源配额</span>
              </span>
            }
            className="glass-card"
          >
            <div className="space-y-4">
              {/* CPU */}
              <div>
                <div className="flex items-center justify-between text-sm mb-1">
                  <span>CPU核心</span>
                  <span className="font-medium">
                    {userProfile.used_cpu}/{userProfile.quota_cpu} 核
                  </span>
                </div>
                <Progress 
                  percent={calculatePercent(userProfile.used_cpu, userProfile.quota_cpu)} 
                  strokeColor={getProgressColor(calculatePercent(userProfile.used_cpu, userProfile.quota_cpu))}
                  showInfo={false}
                />
              </div>

              {/* 内存 */}
              <div>
                <div className="flex items-center justify-between text-sm mb-1">
                  <span>内存使用率</span>
                  <span className="font-medium">
                    {calculatePercent(userProfile.used_ram || 0, userProfile.quota_ram || 0)}%
                  </span>
                </div>
                <Progress 
                  percent={calculatePercent(userProfile.used_ram || 0, userProfile.quota_ram || 0)} 
                  strokeColor={getProgressColor(calculatePercent(userProfile.used_ram || 0, userProfile.quota_ram || 0))}
                  showInfo={false}
                />
                <div className="text-xs mt-1">
                  {((userProfile.used_ram || 0) / 1024).toFixed(1)}/{((userProfile.quota_ram || 0) / 1024).toFixed(1)} GB
                </div>
              </div>

              {/* 磁盘 */}
              <div>
                <div className="flex items-center justify-between text-sm mb-1">
                  <span>存储使用率</span>
                  <span className="font-medium">
                    {calculatePercent(userProfile.used_ssd || 0, userProfile.quota_ssd || 0)}%
                  </span>
                </div>
                <Progress 
                  percent={calculatePercent(userProfile.used_ssd || 0, userProfile.quota_ssd || 0)} 
                  strokeColor={getProgressColor(calculatePercent(userProfile.used_ssd || 0, userProfile.quota_ssd || 0))}
                  showInfo={false}
                />
                <div className="text-xs mt-1">
                  {((userProfile.used_ssd || 0) / 1024).toFixed(1)}/{((userProfile.quota_ssd || 0) / 1024).toFixed(1)} GB
                </div>
              </div>

              {/* GPU（如果有） */}
              {userProfile.quota_gpu && userProfile.quota_gpu > 0 && (
                <div>
                  <div className="flex items-center justify-between text-sm mb-1">
                    <span>GPU显存使用率</span>
                    <span className="font-medium">
                      {calculatePercent(userProfile.used_gpu || 0, userProfile.quota_gpu)}%
                    </span>
                  </div>
                  <Progress 
                    percent={calculatePercent(userProfile.used_gpu || 0, userProfile.quota_gpu)} 
                    strokeColor={getProgressColor(calculatePercent(userProfile.used_gpu || 0, userProfile.quota_gpu))}
                    showInfo={false}
                  />
                  <div className="text-xs mt-1">
                    {((userProfile.used_gpu || 0) / 1024).toFixed(1)}/{(userProfile.quota_gpu / 1024).toFixed(1)} GB
                  </div>
                </div>
              )}

              {/* 流量 */}
              <div>
                <div className="flex items-center justify-between text-sm mb-1">
                  <span>流量</span>
                  <span className="font-medium">
                    {((userProfile.used_traffic || 0) / 1024).toFixed(1)}/{((userProfile.quota_traffic || 0) / 1024).toFixed(1)} GB
                  </span>
                </div>
                <Progress 
                  percent={calculatePercent(userProfile.used_traffic || 0, userProfile.quota_traffic || 0)} 
                  strokeColor={getProgressColor(calculatePercent(userProfile.used_traffic || 0, userProfile.quota_traffic || 0))}
                  showInfo={false}
                />
              </div>

              {/* 上行带宽 */}
              <div>
                <div className="flex items-center justify-between text-sm mb-1">
                  <span>上行带宽</span>
                  <span className="font-medium">
                    {userProfile.used_bandwidth_up || 0}/{userProfile.quota_bandwidth_up || 0} Mbps
                  </span>
                </div>
                <Progress 
                  percent={calculatePercent(userProfile.used_bandwidth_up || 0, userProfile.quota_bandwidth_up || 0)} 
                  strokeColor={getProgressColor(calculatePercent(userProfile.used_bandwidth_up || 0, userProfile.quota_bandwidth_up || 0))}
                  showInfo={false}
                />
              </div>

              {/* 下行带宽 */}
              <div>
                <div className="flex items-center justify-between text-sm mb-1">
                  <span>下行带宽</span>
                  <span className="font-medium">
                    {userProfile.used_bandwidth_down || 0}/{userProfile.quota_bandwidth_down || 0} Mbps
                  </span>
                </div>
                <Progress 
                  percent={calculatePercent(userProfile.used_bandwidth_down || 0, userProfile.quota_bandwidth_down || 0)} 
                  strokeColor={getProgressColor(calculatePercent(userProfile.used_bandwidth_down || 0, userProfile.quota_bandwidth_down || 0))}
                  showInfo={false}
                />
              </div>

              {/* NAT配额 */}
              <div>
                <div className="flex items-center justify-between text-sm mb-1">
                  <span>NAT配额</span>
                  <span className="font-medium">
                    {userProfile.used_nat_ports || 0}/{userProfile.quota_nat_ports || 0} 个
                  </span>
                </div>
                <Progress 
                  percent={calculatePercent(userProfile.used_nat_ports || 0, userProfile.quota_nat_ports || 0)} 
                  strokeColor={getProgressColor(calculatePercent(userProfile.used_nat_ports || 0, userProfile.quota_nat_ports || 0))}
                  showInfo={false}
                />
              </div>

              {/* WEB配额 */}
              <div>
                <div className="flex items-center justify-between text-sm mb-1">
                  <span>WEB配额</span>
                  <span className="font-medium">
                    {userProfile.used_web_proxy || 0}/{userProfile.quota_web_proxy || 0} 个
                  </span>
                </div>
                <Progress 
                  percent={calculatePercent(userProfile.used_web_proxy || 0, userProfile.quota_web_proxy || 0)} 
                  strokeColor={getProgressColor(calculatePercent(userProfile.used_web_proxy || 0, userProfile.quota_web_proxy || 0))}
                  showInfo={false}
                />
              </div>
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  )
}

export default UserConfig
