import { useEffect, useState } from 'react'
import { Table, Button, Space, Tag, Modal, Form, Input, InputNumber, message, Select, Card, Row, Col, Checkbox } from 'antd'
import { PlusOutlined, DeleteOutlined, EditOutlined, ReloadOutlined, GlobalOutlined, LockOutlined, UnlockOutlined, CloudServerOutlined } from '@ant-design/icons'
import api from '@/utils/apis.ts'
import type { ColumnsType } from 'antd/es/table'
import { ProxyConfig } from '@/types'
import PageHeader from '@/components/PageHeader'

/**
 * Web代理数据接口（扩展自ProxyConfig）
 */
interface WebProxy extends ProxyConfig {
  hostName: string
  vmUuid: string
  vmName?: string
}

/**
 * 主机数据接口
 */
interface Host {
  server_name: string
  server_type: string
}

/**
 * 虚拟机数据接口
 */
interface VM {
  vm_uuid: string
  vm_name: string
}

/**
 * Web反向代理管理页面（管理员）
 * 可以管理所有虚拟机的反向代理配置
 */
function HttpProxys() {
  // 状态管理
  const [proxies, setProxies] = useState<WebProxy[]>([])
  const [filteredProxies, setFilteredProxies] = useState<WebProxy[]>([])
  const [hosts, setHosts] = useState<Host[]>([])
  const [vms, setVms] = useState<{ [key: string]: VM[] }>({})
  const [loading, setLoading] = useState(false)
  const [modalVisible, setModalVisible] = useState(false)
  const [isEdit, setIsEdit] = useState(false)
  const [editingProxy, setEditingProxy] = useState<WebProxy | null>(null)
  
  // 筛选条件
  const [searchText, setSearchText] = useState('')
  const [hostFilter, setHostFilter] = useState('')
  const [protocolFilter, setProtocolFilter] = useState('')
  
  const [form] = Form.useForm()

  /**
   * 加载主机列表
   */
  const loadHosts = async () => {
    try {
      const response = await api.getHosts()
      if (response.code === 200) {
        // 确保hosts始终是数组
        const hostData = response.data
        setHosts(Array.isArray(hostData) ? hostData : [])
      }
    } catch (error) {
      console.error('加载主机列表失败:', error)
      setHosts([]) // 出错时设置为空数组
    }
  }

  /**
   * 加载指定主机的虚拟机列表
   */
  const loadVMsForHost = async (hostName: string) => {
    try {
      const response = await api.getVMs(hostName)
      if (response.code === 200) {
        setVms(prev => ({ ...prev, [hostName]: response.data || [] }))
        return response.data || []
      }
    } catch (error) {
      console.error('加载虚拟机列表失败:', error)
    }
    return []
  }

  /**
   * 加载代理列表（从所有虚拟机配置中获取）
   */
  const loadProxys = async () => {
    setLoading(true)
    try {
      // 1. 获取所有主机
      const hostsRes = await api.getHosts()
      if (hostsRes.code !== 200 || !hostsRes.data) {
        throw new Error('获取主机列表失败')
      }
      const hostsList = Object.keys(hostsRes.data)

      const allProxies: WebProxy[] = []

      // 2. 遍历主机获取VMs
      for (const hostName of hostsList) {
        try {
          const vmsRes = await api.getVMs(hostName)
          if (vmsRes.code === 200 && vmsRes.data) {
            const vms = Array.isArray(vmsRes.data) ? vmsRes.data : Object.values(vmsRes.data)
            
            // 3. 遍历VMs获取Proxies
            await Promise.all(vms.map(async (vm: any) => {
              const vmUuid = vm.config?.vm_uuid || vm.uuid
              const vmName = vm.config?.vm_name || vm.vm_name || vmUuid
              try {
                const proxyRes = await api.getProxyConfigs(hostName, vmUuid)
                if (proxyRes.code === 200 && proxyRes.data) {
                  proxyRes.data.forEach((p: ProxyConfig) => {
                    allProxies.push({
                      ...p,
                      hostName,
                      vmUuid,
                      vmName
                    })
                  })
                }
              } catch (e) {
                // 忽略单个虚拟机的错误
                console.error(`获取虚拟机 ${vmUuid} 的代理配置失败:`, e)
              }
            }))
          }
        } catch (e) {
          console.error(`获取主机 ${hostName} 数据失败`, e)
        }
      }

      setProxies(allProxies)
      setFilteredProxies(allProxies)
    } catch (error) {
      console.error('获取反向代理失败', error)
      message.error('获取数据失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadHosts()
    loadProxys()
  }, [])

  /**
   * 筛选代理列表
   */
  useEffect(() => {
    let filtered = [...proxies]
    
    // 搜索筛选
    if (searchText) {
      const search = searchText.toLowerCase()
      filtered = filtered.filter(proxy => 
        proxy.domain.toLowerCase().includes(search) ||
        (proxy.vmName && proxy.vmName.toLowerCase().includes(search))
      )
    }
    
    // 主机筛选
    if (hostFilter) {
      filtered = filtered.filter(proxy => proxy.hostName === hostFilter)
    }
    
    // 协议筛选
    if (protocolFilter) {
      if (protocolFilter === 'https') {
        filtered = filtered.filter(proxy => proxy.ssl_enabled)
      } else if (protocolFilter === 'http') {
        filtered = filtered.filter(proxy => !proxy.ssl_enabled)
      }
    }
    
    setFilteredProxies(filtered)
  }, [searchText, hostFilter, protocolFilter, proxies])

  /**
   * 计算统计数据
   */
  const statistics = {
    total: proxies.length,
    http: proxies.filter(p => !p.ssl_enabled).length,
    https: proxies.filter(p => p.ssl_enabled).length,
    hosts: new Set(proxies.map(p => p.hostName)).size
  }

  /**
   * 显示添加模态框
   */
  const showAddModal = () => {
    setIsEdit(false)
    setEditingProxy(null)
    form.resetFields()
    setModalVisible(true)
  }

  /**
   * 显示编辑模态框
   */
  const showEditModal = (proxy: WebProxy) => {
    setIsEdit(true)
    setEditingProxy(proxy)
    
    // 加载该主机的虚拟机列表
    loadVMsForHost(proxy.hostName).then(() => {
      form.setFieldsValue({
        host_name: proxy.hostName,
        vm_uuid: proxy.vmUuid,
        domain: proxy.domain,
        backend_ip: proxy.backend_ip,
        backend_port: proxy.backend_port,
        ssl_enabled: proxy.ssl_enabled,
        description: proxy.description
      })
    })
    
    setModalVisible(true)
  }

  /**
   * 处理主机选择变化
   */
  const handleHostChange = (hostName: string) => {
    form.setFieldValue('vm_uuid', undefined)
    if (hostName) {
      loadVMsForHost(hostName)
    }
  }

  /**
   * 创建或更新代理
   */
  const handleSubmit = async (values: any) => {
    try {
      if (isEdit && editingProxy) {
        // 编辑模式
        const response = await api.updateWebProxy(
          editingProxy.hostName,
          editingProxy.vmUuid,
          editingProxy.proxy_index,
          {
            domain: values.domain,
            backend_ip: values.backend_ip || '',
            backend_port: values.backend_port,
            ssl_enabled: values.ssl_enabled || false,
            description: values.description || ''
          }
        )
        if (response.code === 200) {
          message.success('代理更新成功')
          setModalVisible(false)
          form.resetFields()
          loadProxys()
        } else {
          message.error(response.msg || '更新失败')
        }
      } else {
        // 添加模式
        const response = await api.createWebProxy(
          values.host_name,
          values.vm_uuid,
          {
            domain: values.domain,
            backend_ip: values.backend_ip || '',
            backend_port: values.backend_port,
            ssl_enabled: values.ssl_enabled || false,
            description: values.description || ''
          }
        )
        if (response.code === 200) {
          message.success('代理创建成功')
          setModalVisible(false)
          form.resetFields()
          loadProxys()
        } else {
          message.error(response.msg || '创建失败')
        }
      }
    } catch (error) {
      message.error(isEdit ? '更新代理失败' : '创建代理失败')
    }
  }

  /**
   * 删除代理
   */
  const handleDelete = async (proxy: WebProxy) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除这个反向代理配置吗？',
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      mask: false,
      onOk: async () => {
        try {
          const response = await api.deleteWebProxy(
            proxy.hostName,
            proxy.vmUuid,
            proxy.proxy_index
          )
          if (response.code === 200) {
            message.success('删除成功')
            loadProxys()
          } else {
            message.error(response.msg || '删除失败')
          }
        } catch (error) {
          message.error('删除代理失败')
        }
      }
    })
  }

  /**
   * 表格列配置
   */
  const columns: ColumnsType<WebProxy> = [
    {
      title: '域名',
      dataIndex: 'domain',
      key: 'domain',
      render: (domain: string, record: WebProxy) => (
        <a
          href={`http${record.ssl_enabled ? 's' : ''}://${domain}`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-600 dark:text-blue-400 font-medium hover:underline"
        >
          {domain}
        </a>
      )
    },
    {
      title: '主机',
      dataIndex: 'hostName',
      key: 'hostName',
      render: (name: string) => <Tag color="blue">{name}</Tag>
    },
    {
      title: '虚拟机',
      dataIndex: 'vmName',
      key: 'vmName',
      render: (name: string) => <Tag color="default">{name || '-'}</Tag>
    },
    {
      title: '后端地址',
      key: 'backend',
      render: (_, record: WebProxy) => (
        <code className="text-sm ">
          {record.backend_ip || 'auto'}:{record.backend_port}
        </code>
      )
    },
    {
      title: '协议',
      key: 'protocol',
      render: (_, record: WebProxy) => (
        <Tag
          icon={record.ssl_enabled ? <LockOutlined /> : <UnlockOutlined />}
          color={record.ssl_enabled ? 'success' : 'default'}
        >
          {record.ssl_enabled ? 'HTTPS' : 'HTTP'}
        </Tag>
      )
    },
    {
      title: '状态',
      dataIndex: 'enabled',
      key: 'enabled',
      render: (enabled: boolean) => (
        <Tag color={enabled ? 'success' : 'error'}>
          {enabled ? '已启用' : '已禁用'}
        </Tag>
      )
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      render: (desc: string) => <span style={{ color: 'var(--text-secondary)' }}>{desc || '-'}</span>
    },
    {
      title: '操作',
      key: 'action',
      render: (_, record: WebProxy) => (
        <Space size="small">
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => showEditModal(record)}
          >
            编辑
          </Button>
          <Button
            type="link"
            size="small"
            danger
            icon={<DeleteOutlined />}
            onClick={() => handleDelete(record)}
          >
            删除
          </Button>
        </Space>
      )
    }
  ]

  return (
    <div className="p-6">
      {/* 页面标题 */}
      <PageHeader
        icon={<GlobalOutlined />}
        title="反向代理管理"
        subtitle="管理所有虚拟机的Web反向代理配置"
        actions={
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={showAddModal}
            size="large"
            className="gradient-button"
          >
            添加反向代理
          </Button>
        }
      />

      {/* 统计卡片 - 重新设计 */}
      <Row gutter={[16, 16]} className="mb-6">
        <Col xs={24} sm={12} md={6}>
          <Card 
            className="glass-card hover:shadow-xl transition-all duration-300 hover:-translate-y-1"
            style={{
              background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(37, 99, 235, 0.05) 100%)',
              border: '1px solid rgba(59, 130, 246, 0.2)',
              borderRadius: '16px'
            }}
          >
            <div className="flex items-center justify-between mb-3">
              <div className="w-12 h-12 rounded-xl flex items-center justify-center" style={{
                background: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)'
              }}>
                <GlobalOutlined className="text-white text-xl" />
              </div>
              <div className="text-right">
<div className="text-xs mb-1" style={{ color: 'var(--text-secondary)' }}>总代理数</div>
                <div className="text-3xl font-bold" style={{
                  background: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent'
                }}>
                  {statistics.total}
                </div>
              </div>
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card 
            className="glass-card hover:shadow-xl transition-all duration-300 hover:-translate-y-1"
            style={{
              background: 'linear-gradient(135deg, rgba(107, 114, 128, 0.1) 0%, rgba(75, 85, 99, 0.05) 100%)',
              border: '1px solid rgba(107, 114, 128, 0.2)',
              borderRadius: '16px'
            }}
          >
            <div className="flex items-center justify-between mb-3">
              <div className="w-12 h-12 rounded-xl flex items-center justify-center" style={{
                background: 'linear-gradient(135deg, #6b7280 0%, #4b5563 100%)'
              }}>
                <UnlockOutlined className="text-white text-xl" />
              </div>
              <div className="text-right">
<div className="text-xs mb-1" style={{ color: 'var(--text-secondary)' }}>HTTP代理</div>
                <div className="text-3xl font-bold" style={{
                  background: 'linear-gradient(135deg, #6b7280 0%, #4b5563 100%)',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent'
                }}>
                  {statistics.http}
                </div>
              </div>
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card 
            className="glass-card hover:shadow-xl transition-all duration-300 hover:-translate-y-1"
            style={{
              background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(5, 150, 105, 0.05) 100%)',
              border: '1px solid rgba(16, 185, 129, 0.2)',
              borderRadius: '16px'
            }}
          >
            <div className="flex items-center justify-between mb-3">
              <div className="w-12 h-12 rounded-xl flex items-center justify-center" style={{
                background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)'
              }}>
                <LockOutlined className="text-white text-xl" />
              </div>
              <div className="text-right">
<div className="text-xs mb-1" style={{ color: 'var(--text-secondary)' }}>HTTPS代理</div>
                <div className="text-3xl font-bold" style={{
                  background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent'
                }}>
                  {statistics.https}
                </div>
              </div>
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card 
            className="glass-card hover:shadow-xl transition-all duration-300 hover:-translate-y-1"
            style={{
              background: 'linear-gradient(135deg, rgba(139, 92, 246, 0.1) 0%, rgba(124, 58, 237, 0.05) 100%)',
              border: '1px solid rgba(139, 92, 246, 0.2)',
              borderRadius: '16px'
            }}
          >
            <div className="flex items-center justify-between mb-3">
              <div className="w-12 h-12 rounded-xl flex items-center justify-center" style={{
                background: 'linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)'
              }}>
                <CloudServerOutlined className="text-white text-xl" />
              </div>
              <div className="text-right">
<div className="text-xs mb-1" style={{ color: 'var(--text-secondary)' }}>主机数</div>
                <div className="text-3xl font-bold" style={{
                  background: 'linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent'
                }}>
                  {statistics.hosts}
                </div>
              </div>
            </div>
          </Card>
        </Col>
      </Row>

      {/* 筛选和搜索 - 优化设计 */}
      <Card 
        className="glass-card mb-6"
        style={{ borderRadius: '16px' }}
      >
        <Space size="middle" style={{ width: '100%', flexWrap: 'wrap' }}>
          <Input
            placeholder="🔍 搜索域名、虚拟机名称..."
            style={{ width: 300, borderRadius: '8px' }}
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            allowClear
          />
          <Select
            placeholder="所有主机"
            style={{ width: 150, borderRadius: '8px' }}
            value={hostFilter || undefined}
            onChange={setHostFilter}
            allowClear
          >
            {Array.isArray(hosts) && hosts.map(host => (
              <Select.Option key={host.server_name} value={host.server_name}>
                {host.server_name}
              </Select.Option>
            ))}
          </Select>
          <Select
            placeholder="所有协议"
            style={{ width: 120, borderRadius: '8px' }}
            value={protocolFilter || undefined}
            onChange={setProtocolFilter}
            allowClear
          >
            <Select.Option value="http">HTTP</Select.Option>
            <Select.Option value="https">HTTPS</Select.Option>
          </Select>
          <Button
            icon={<ReloadOutlined />}
            onClick={loadProxys}
            style={{ borderRadius: '8px' }}
          >
            刷新
          </Button>
        </Space>
      </Card>

      {/* 代理列表表格 - 优化设计 */}
      <Card 
        className="glass-card"
        style={{ borderRadius: '16px' }}
      >
        <Table
          columns={columns}
          dataSource={filteredProxies}
          rowKey={(record) => `${record.hostName}-${record.vmUuid}-${record.proxy_index}`}
          loading={loading}
          pagination={{
            pageSize: 10,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 条记录`
          }}
          locale={{
            emptyText: (
              <div style={{ padding: '48px 0', textAlign: 'center' }}>
                <GlobalOutlined style={{ fontSize: '5rem', color: 'var(--text-tertiary)' }} />
                <p className="mt-4 text-lg" style={{ color: 'var(--text-secondary)' }}>暂无反向代理配置</p>
                <Button 
                  type="primary" 
                  onClick={showAddModal} 
                  style={{ marginTop: '16px' }}
                  className="gradient-button"
                >
                  添加第一个代理
                </Button>
              </div>
            )
          }}
        />
      </Card>

      {/* 添加/编辑代理模态框 */}
      <Modal
        title={isEdit ? '编辑反向代理' : '添加反向代理'}
        open={modalVisible}
        onCancel={() => {
          setModalVisible(false)
          form.resetFields()
        }}
        onOk={() => form.submit()}
        width={600}
        okText={isEdit ? '保存' : '添加'}
        cancelText="取消"
        destroyOnHidden
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
        >
          <Form.Item
            name="host_name"
            label="主机"
            rules={[{ required: true, message: '请选择主机' }]}
          >
            <Select
              placeholder="请选择主机"
              onChange={handleHostChange}
              disabled={isEdit}
            >
              {Array.isArray(hosts) && hosts.map(host => (
                <Select.Option key={host.server_name} value={host.server_name}>
                  {host.server_name}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            name="vm_uuid"
            label="虚拟机"
            rules={[{ required: true, message: '请选择虚拟机' }]}
          >
            <Select
              placeholder="请先选择主机"
              disabled={isEdit || !form.getFieldValue('host_name')}
            >
              {(vms[form.getFieldValue('host_name')] || []).map(vm => (
                <Select.Option key={vm.vm_uuid} value={vm.vm_uuid}>
                  {vm.vm_name || vm.vm_uuid}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            name="domain"
            label="域名"
            rules={[{ required: true, message: '请输入域名' }]}
          >
            <Input placeholder="example.com" />
          </Form.Item>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="backend_ip"
                label="后端IP"
              >
                <Input placeholder="自动获取" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="backend_port"
                label="后端端口"
                rules={[{ required: true, message: '请输入后端端口' }]}
                initialValue={80}
              >
                <InputNumber
                  min={1}
                  max={65535}
                  style={{ width: '100%' }}
                  placeholder="80"
                />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            name="description"
            label="描述"
          >
            <Input.TextArea
              rows={3}
              placeholder="可选的描述信息"
            />
          </Form.Item>

          <Form.Item
            name="ssl_enabled"
            valuePropName="checked"
          >
            <Checkbox>启用HTTPS (SSL/TLS)</Checkbox>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default HttpProxys
