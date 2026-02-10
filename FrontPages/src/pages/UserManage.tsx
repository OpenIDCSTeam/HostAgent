import { useEffect, useState } from 'react'
import { Table, Button, Space, Tag, Modal, Form, Input, Checkbox, InputNumber, message, Popconfirm, Divider, Row, Col } from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, UserOutlined } from '@ant-design/icons'
import PageHeader from '@/components/PageHeader'
import api from '@/utils/apis.ts'
import type { ColumnsType } from 'antd/es/table'
import type { User } from '@/types'

/**
 * 主机数据接口
 */
interface Host {
  hs_name: string
  [key: string]: any
}

/**
 * 用户管理页面
 */
function UserManage() {
  const [users, setUsers] = useState<User[]>([])
  const [hosts, setHosts] = useState<Host[]>([])
  const [loading, setLoading] = useState(false)
  const [modalVisible, setModalVisible] = useState(false)
  const [editingUser, setEditingUser] = useState<User | null>(null)
  const [form] = Form.useForm()

  /**
   * 加载用户列表
   */
  const loadUsers = async () => {
    try {
      setLoading(true)
      const response = await api.getUsers()
      if (response.code === 200 && response.data) {
        setUsers(response.data)
      }
    } catch (error) {
      message.error('加载用户列表失败')
    } finally {
      setLoading(false)
    }
  }

  /**
   * 加载主机列表
   */
  const loadHosts = async () => {
    try {
      const response = await api.getHosts()
      if (response.code === 200 && response.data) {
        // 将对象转换为数组
        if (typeof response.data === 'object' && !Array.isArray(response.data)) {
          const hostsArray = Object.keys(response.data).map(hostName => ({
            hs_name: hostName,
            ...response.data![hostName]
          }))
          setHosts(hostsArray)
        } else if (Array.isArray(response.data)) {
          setHosts(response.data)
        }
      }
    } catch (error) {
      console.error('加载主机列表失败:', error)
    }
  }

  useEffect(() => {
    loadUsers()
    loadHosts()
  }, [])

  /**
   * 打开编辑对话框
   */
  const handleEdit = async (userId: number) => {
    const user = users.find(u => u.id === userId)
    if (user) {
        setEditingUser(user)
        
        // 将MB转换为GB显示
        form.setFieldsValue({
          ...user,
          quota_ram: Math.floor(user.quota_ram / 1024),
          quota_ssd: Math.floor(user.quota_ssd / 1024),
          quota_gpu: Math.floor(user.quota_gpu / 1024),
          quota_traffic: Math.floor(user.quota_traffic / 1024),
          password: '', // 清空密码字段
          assigned_hosts: user.assigned_hosts || []
        })
        setModalVisible(true)
    } else {
        message.error('未找到用户信息')
    }
  }

  /**
   * 提交表单
   */
  const handleSubmit = async (values: any) => {
    try {
      // 将GB转换为MB提交给后端
      const data = {
        ...values,
        is_admin: values.is_admin ? 1 : 0,
        is_active: values.is_active ? 1 : 0,
        can_create_vm: values.can_create_vm ? 1 : 0,
        can_modify_vm: values.can_modify_vm ? 1 : 0,
        can_delete_vm: values.can_delete_vm ? 1 : 0,
        quota_ram: Math.round(values.quota_ram * 1024),
        quota_ssd: Math.round(values.quota_ssd * 1024),
        quota_gpu: Math.round(values.quota_gpu * 1024),
        quota_traffic: Math.round(values.quota_traffic * 1024),
      }

      // 如果是编辑模式且密码为空，则删除密码字段
      if (editingUser && (!data.password || data.password.trim() === '')) {
        delete data.password
      }

      if (editingUser) {
        // 更新用户
        await api.updateUser(editingUser.id, data)
        message.success('用户更新成功')
      } else {
        // 创建用户
        await api.createUser(data)
        message.success('用户创建成功')
      }
      
      setModalVisible(false)
      setEditingUser(null)
      form.resetFields()
      loadUsers()
    } catch (error: any) {
      message.error(error.msg || (editingUser ? '更新用户失败' : '创建用户失败'))
    }
  }

  /**
   * 删除用户
   */
  const handleDelete = async (id: number) => {
    try {
      await api.deleteUser(id)
      message.success('用户删除成功')
      loadUsers()
    } catch (error) {
      message.error('删除用户失败')
    }
  }

  /**
   * 表格列配置
   */
  const columns: ColumnsType<User> = [
    {
      title: '用户名',
      dataIndex: 'username',
      key: 'username',
      width: 80,
    },
    {
      title: '邮箱',
      dataIndex: 'email',
      key: 'email',
      width: 160,
    },
    {
      title: '角色',
      dataIndex: 'is_admin',
      key: 'is_admin',
      width: 60,
      render: (is_admin: boolean) => (
        <Tag color={is_admin ? 'purple' : 'default'}>
          {is_admin ? '管理员' : '普通用户'}
        </Tag>
      ),
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 60,
      render: (is_active: boolean) => (
        <Tag color={is_active ? 'success' : 'error'}>
          {is_active ? '启用' : '禁用'}
        </Tag>
      ),
    },
    {
      title: '基础配额',
      key: 'basic_quota',
      width: 180,
      render: (_, record) => (
<div className="space-y-1 text-xs">
          <div className="flex justify-between gap-2">
            <span style={{ color: 'var(--text-secondary)' }}>CPU:</span>
            <span className="font-mono">{record.used_cpu || 0}/{record.quota_cpu}</span>
          </div>
          <div className="flex justify-between gap-2">
            <span style={{ color: 'var(--text-secondary)' }}>RAM:</span>
            <span className="font-mono">{Math.round((record.used_ram || 0) / 1024)}/{Math.round(record.quota_ram / 1024)}GB</span>
          </div>
          <div className="flex justify-between gap-2">
            <span style={{ color: 'var(--text-secondary)' }}>SSD:</span>
            <span className="font-mono">{Math.round((record.used_ssd || 0) / 1024)}/{Math.round(record.quota_ssd / 1024)}GB</span>
          </div>
          <div className="flex justify-between gap-2">
            <span style={{ color: 'var(--text-secondary)' }}>GPU ID:</span>
            <span className="font-mono">{record.gpu_ids || '0'}</span>
          </div>
        </div>
      ),
    },
    {
      title: 'GPU显存',
      key: 'gpu_quota',
      width: 120,
      render: (_, record) => (
        <div className="text-xs">
          <div className="flex justify-between gap-2">
            <span style={{ color: 'var(--text-secondary)' }}>GPU显存:</span>
            <span className="font-mono">{Math.round((record.used_gpu || 0) / 1024)}/{Math.round(record.quota_gpu / 1024)}GB</span>
          </div>
        </div>
      ),
    },
    {
      title: '带宽/流量',
      key: 'bandwidth_quota',
      width: 150,
      render: (_, record) => (
        <div className="space-y-1 text-xs">
          <div className="flex justify-between gap-2">
            <span style={{ color: 'var(--text-secondary)' }}>上行:</span>
            <span className="font-mono">{record.used_bandwidth_up || 0}/{record.quota_bandwidth_up}M</span>
          </div>
          <div className="flex justify-between gap-2">
            <span style={{ color: 'var(--text-secondary)' }}>下行:</span>
            <span className="font-mono">{record.used_bandwidth_down || 0}/{record.quota_bandwidth_down}M</span>
          </div>
          <div className="flex justify-between gap-2">
            <span style={{ color: 'var(--text-secondary)' }}>流量:</span>
            <span className="font-mono">{Math.round((record.used_traffic || 0) / 1024)}/{Math.round(record.quota_traffic / 1024)}GB</span>
          </div>
        </div>
      ),
    },
    {
      title: '网络服务',
      key: 'network_quota',
      width: 120,
      render: (_, record) => (
        <div className="space-y-1 text-xs">
          <div className="flex justify-between gap-2">
            <span style={{ color: 'var(--text-secondary)' }}>NAT:</span>
            <span className="font-mono">{record.used_nat_ports || 0}/{record.quota_nat_ports}</span>
          </div>
          <div className="flex justify-between gap-2">
            <span style={{ color: 'var(--text-secondary)' }}>WEB:</span>
            <span className="font-mono">{record.used_web_proxy || 0}/{record.quota_web_proxy}</span>
          </div>
        </div>
      ),
    },
    {
      title: 'IP配额',
      key: 'ip_quota',
      width: 120,
      render: (_, record) => (
        <div className="space-y-1 text-xs">
          <div className="flex justify-between gap-2">
            <span style={{ color: 'var(--text-secondary)' }}>内网IP:</span>
            <span className="font-mono">{record.used_nat_ips || 0}/{record.quota_nat_ips || 0}</span>
          </div>
          <div className="flex justify-between gap-2">
            <span style={{ color: 'var(--text-secondary)' }}>公网IP:</span>
            <span className="font-mono">{record.used_pub_ips || 0}/{record.quota_pub_ips || 0}</span>
          </div>
        </div>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      fixed: 'right',
      render: (_, record) => (
        <Space size="small">
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record.id)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确定要删除此用户吗？"
            description="删除后无法恢复！"
            onConfirm={() => handleDelete(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div className="p-6">
      {/* 页面标题 */}
      <PageHeader
        icon={<UserOutlined />}
        title="平台用户管理"
        subtitle="管理系统用户、权限和资源配额"
        actions={
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => {
              setEditingUser(null)
              form.resetFields()
              // 设置默认值
              form.setFieldsValue({
                is_active: true,
                can_create_vm: true,
                can_modify_vm: true,
                can_delete_vm: true,
                quota_cpu: 2,
                quota_ram: 4,
                quota_ssd: 50,
                quota_gpu: 0,
                quota_nat_ports: 5,
                quota_nat_ips: 5,
                quota_web_proxy: 2,
                quota_pub_ips: 2,
                quota_bandwidth_up: 100,
                quota_bandwidth_down: 100,
                quota_traffic: 500,
              })
              setModalVisible(true)
            }}
          >
            添加用户
          </Button>
        }
      />

      {/* 用户列表 */}
      <div className="glass-card" style={{
        backdropFilter: 'blur(10px)',
        WebkitBackdropFilter: 'blur(10px)'
      }}>

        
        <Table
          columns={columns}
          dataSource={users}
          rowKey="id"
          loading={loading}
          scroll={{ x: 1500 }}
          pagination={{
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 条`,
          }}
        />
      </div>

      {/* 创建/编辑用户对话框 */}
      <Modal
        title={editingUser ? '编辑用户' : '添加用户'}
        open={modalVisible}
        onCancel={() => {
          setModalVisible(false)
          setEditingUser(null)
          form.resetFields()
        }}
        onOk={() => form.submit()}
        width={800}
        style={{ top: 20 }}
        styles={{ body: { maxHeight: 'calc(100vh - 200px)', overflowY: 'auto' } }}
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          {/* 基本信息 */}
          <Divider orientation="left">基本信息</Divider>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="username"
                label="用户名"
                rules={[{ required: true, message: '请输入用户名' }]}
              >
                <Input placeholder="请输入用户名" disabled={!!editingUser} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="email"
                label="邮箱"
                rules={[
                  { required: true, message: '请输入邮箱' },
                  { type: 'email', message: '请输入有效的邮箱地址' },
                ]}
              >
                <Input placeholder="请输入邮箱" disabled={!!editingUser} />
              </Form.Item>
            </Col>
            <Col span={24}>
              <Form.Item
                name="password"
                label={editingUser ? '新密码（留空则不修改）' : '密码'}
                rules={editingUser ? [] : [
                  { required: true, message: '请输入密码' },
                  { min: 6, message: '密码至少6个字符' },
                ]}
              >
                <Input.Password placeholder={editingUser ? '留空则不修改' : '请输入密码'} />
              </Form.Item>
            </Col>
          </Row>

          {/* 角色和状态 */}
          <Divider orientation="left">角色和状态</Divider>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="is_admin" valuePropName="checked">
                <Checkbox>管理员</Checkbox>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="is_active" valuePropName="checked">
                <Checkbox>启用用户</Checkbox>
              </Form.Item>
            </Col>
          </Row>

          {/* 虚拟机权限 */}
          <Divider orientation="left">虚拟机权限</Divider>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="can_create_vm" valuePropName="checked">
                <Checkbox>允许创建虚拟机</Checkbox>
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="can_modify_vm" valuePropName="checked">
                <Checkbox>允许修改虚拟机</Checkbox>
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="can_delete_vm" valuePropName="checked">
                <Checkbox>允许删除虚拟机</Checkbox>
              </Form.Item>
            </Col>
          </Row>

          {/* 资源配额 */}
          <Divider orientation="left">资源配额</Divider>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="quota_cpu" label="CPU核心(个)">
                <InputNumber min={0} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="quota_ram" label="RAM内存(GB)">
                <InputNumber min={0} step={1} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="quota_ssd" label="HDD磁盘(GB)">
                <InputNumber min={0} step={1} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="quota_gpu" label="GPU显存(GB)">
                <InputNumber min={0} step={1} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="quota_nat_ports" label="NAT端口(个)">
                <InputNumber min={0} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="quota_nat_ips" label="内网IP(个)">
                <InputNumber min={0} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="quota_web_proxy" label="WEB代理(个)">
                <InputNumber min={0} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="quota_pub_ips" label="公网IP(个)">
                <InputNumber min={0} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="quota_bandwidth_up" label="上行带宽(Mbps)">
                <InputNumber min={0} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="quota_bandwidth_down" label="下行带宽(Mbps)">
                <InputNumber min={0} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={24}>
              <Form.Item name="quota_traffic" label="月流量(GB)">
                <InputNumber min={0} step={1} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>

          {/* 分配主机 */}
          <Divider orientation="left">分配主机</Divider>
          <Form.Item name="assigned_hosts">
            <Checkbox.Group>
              <Row>
                {hosts.map(host => (
                  <Col span={12} key={host.hs_name}>
                    <Checkbox value={host.hs_name}>{host.hs_name}</Checkbox>
                  </Col>
                ))}
              </Row>
            </Checkbox.Group>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default UserManage
