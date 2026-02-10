import { useEffect, useState } from 'react'
import { Row, Col, Card, Button, Modal, Form, Input, Select, Slider, Progress, Tag, message, Space, Divider, Table, Tooltip } from 'antd'

import {
  DesktopOutlined,
  CloudServerOutlined,
  CheckCircleOutlined,
  PlusOutlined,
  PoweroffOutlined,
  MonitorOutlined,
  SettingOutlined,
  SaveOutlined,
  ThunderboltOutlined,
  RadarChartOutlined,
  HddOutlined,
  PlayCircleOutlined,
  GlobalOutlined,
  ApiOutlined,
  CloudOutlined,
  UploadOutlined,
  DownloadOutlined,
  DatabaseOutlined,
  MinusCircleOutlined,
  TeamOutlined,
  CloseCircleOutlined,
  SyncOutlined,
} from '@ant-design/icons'
import PageHeader from '@/components/PageHeader'
import { useNavigate } from 'react-router-dom'
import api from '@/utils/apis.ts'
import { useUserStore } from '@/utils/data.ts'

/**
 * 系统统计数据接口
 */
interface SystemStats {
  hosts_count: number
  vms_count: number
  users_count: number
  running_vms: number
  stopped_vms: number
  total_nat_ports: number
  total_web_proxy: number
}

/**
 * 主机信息接口
 */
interface HostInfo {
  server_name: string
  server_type: string
  server_addr: string
  status: string
  vms_count: number
  max_vms: number
  running_vms: number
  stopped_vms: number
  cpu_usage: number
  gpu_usage: number
  memory_usage: number
  disk_usage: number
  enabled: boolean
  last_check: string
}

/**
 * 用户资源配额接口
 */
interface UserQuota {
  used_cpu: number
  quota_cpu: number
  used_ram: number
  quota_ram: number
  used_ssd: number
  quota_ssd: number
  used_gpu: number
  quota_gpu: number
  used_traffic: number
  quota_traffic: number
  used_nat_ports: number
  quota_nat_ports: number
  used_web_proxy: number
  quota_web_proxy: number
  used_bandwidth_up: number
  quota_bandwidth_up: number
  used_bandwidth_down: number
  quota_bandwidth_down: number
  assigned_hosts: string[]
  can_create_vm: boolean
  used_nat_ips: number
  quota_nat_ips: number
  used_pub_ips: number
  quota_pub_ips: number
}

/**
 * 虚拟机配置接口
 */
interface VMConfig {
  cpu_num: number
  mem_num: number
  hdd_num: number
  gpu_mem: number
  os_name: string
  nat_num: number
  web_num: number
  nic_all: Record<string, any>
}

/**
 * 虚拟机状态接口
 */
interface VMStatus {
  ac_status: string
}

/**
 * 虚拟机信息接口
 */
interface VMInfo {
  uuid: string
  display_name: string
  host: string
  config: VMConfig
  status: VMStatus[]
  power: string
}

/**
 * Dashboard仪表盘页面组件
 */
function Dashboards() {
  const navigate = useNavigate()
  const { user } = useUserStore()
  const isAdmin = user?.is_admin || false

  // 管理员视图状态
  const [systemStats, setSystemStats] = useState<SystemStats>({
    hosts_count: 0,
    vms_count: 0,
    users_count: 0,
    running_vms: 0,
    stopped_vms: 0,
    total_nat_ports: 0,
    total_web_proxy: 0,
  })
  const [hosts, setHosts] = useState<Record<string, HostInfo>>({})

  // 普通用户视图状态
  const [userQuota, setUserQuota] = useState<UserQuota | null>(null)
  const [myVMs, setMyVMs] = useState<VMInfo[]>([])
  const [myVMCount, setMyVMCount] = useState(0)
  const [myRunningVMCount, setMyRunningVMCount] = useState(0)

  // 创建虚拟机模态框状态
  const [createVMModalVisible, setCreateVMModalVisible] = useState(false)
  const [createVMForm] = Form.useForm()
  const [availableHosts, setAvailableHosts] = useState<string[]>([])
  const [availableImages, setAvailableImages] = useState<string[]>([])
  
  // 新增状态：主机配置、UUID前缀、最小磁盘、网卡列表
  const [hostConfig, setHostConfig] = useState<any>(null)
  const [uuidPrefix, setUuidPrefix] = useState('')
  const [minDiskSize, setMinDiskSize] = useState(10)
  const [nicList, setNicList] = useState<Array<{ id: number; type: string; ip: string }>>([
    { id: 0, type: 'nat', ip: '' }
  ])
  const [nicCounter, setNicCounter] = useState(1)

  // 电源操作模态框状态
  const [powerModalVisible, setPowerModalVisible] = useState(false)
  const [currentPowerVM, setCurrentPowerVM] = useState<{ uuid: string; host: string; name: string }>({ uuid: '', host: '', name: '' })

  const [lastUpdate, setLastUpdate] = useState<string>('')

  /**
   * 加载管理员仪表板数据
   */
  const loadAdminDashboard = async () => {
    try {
      // 加载系统统计数据
      const statsResult = await api.get('/api/system/statis')
      if (statsResult.code === 200) {
        setSystemStats({
          hosts_count: statsResult.data.hosts_count || statsResult.data.host_count || 0,
          vms_count: statsResult.data.vms_count || statsResult.data.vm_count || 0,
          users_count: statsResult.data.users_count || 0,
          running_vms: statsResult.data.running_vms || statsResult.data.running_vm_count || 0,
          stopped_vms: statsResult.data.stopped_vms || 0,
          total_nat_ports: statsResult.data.total_nat_ports || 0,
          total_web_proxy: statsResult.data.total_web_proxy || 0,
        })
      }

      // 加载主机列表
      const hostsResult = await api.get('/api/server/detail')
      if (hostsResult.code === 200) {
        setHosts(hostsResult.data)
      }

      // 更新最后更新时间
      const now = new Date()
      setLastUpdate(now.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' }))
    } catch (error) {
      console.error('加载管理员数据失败:', error)
      message.error('加载数据失败')
    }
  }

  /**
   * 加载普通用户仪表盘数据
   */
  const loadUserDashboard = async () => {
    try {
      // 加载用户资源配额
      const userResult = await api.get('/api/users/current')
      if (userResult.code === 200) {
        setUserQuota(userResult.data)
        
        // 加载用户的虚拟机
        await loadUserVMs(userResult.data.assigned_hosts)
      }

      // 更新最后更新时间
      const now = new Date()
      setLastUpdate(now.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' }))
    } catch (error) {
      console.error('加载用户数据失败:', error)
      message.error('加载数据失败')
    }
  }

  /**
   * 加载用户的虚拟机列表
   */
  const loadUserVMs = async (assignedHosts: string[]) => {
    try {
      const allVMs: VMInfo[] = []
      let runningCount = 0

      // 从每个主机获取虚拟机
      for (const hostName of assignedHosts) {
        try {
          const vmsResult = await api.get(`/api/client/detail/${hostName}`)
          if (vmsResult.code === 200) {
            const vms = Object.entries(vmsResult.data || {})
            vms.forEach(([uuid, vm]: [string, any]) => {
              allVMs.push({ uuid, ...vm, host: hostName })
              if (vm.power === 'powered_on') runningCount++
            })
          }
        } catch (error) {
          console.error(`加载主机 ${hostName} 的虚拟机失败:`, error)
        }
      }

      setMyVMs(allVMs)
      setMyVMCount(allVMs.length)
      setMyRunningVMCount(runningCount)
    } catch (error) {
      console.error('加载用户虚拟机失败:', error)
    }
  }

  /**
   * 加载仪表盘数据
   */
  const loadDashboard = async () => {
    try {
      if (isAdmin) {
        await loadAdminDashboard()
      } else {
        await loadUserDashboard()
      }
    } catch (error) {
      console.error('加载仪表盘数据失败:', error)
    }
  }

  useEffect(() => {
    loadDashboard()

    // 定时刷新数据（每30秒）
    const interval = setInterval(loadDashboard, 30000)

    return () => {
      clearInterval(interval)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAdmin])

  /**
   * 保存所有配置
   */
  const handleSaveAll = async () => {
    try {
      const result = await api.post('/api/system/saving')
      if (result.code === 200) {
        message.success('配置已保存')
      } else {
        message.error(result.msg || '保存失败')
      }
    } catch (error) {
      console.error('保存配置失败:', error)
      message.error('保存失败')
    }
  }

  /**
   * 打开创建虚拟机模态框
   */
  const handleOpenCreateVM = async () => {
    if (!userQuota?.can_create_vm) {
      message.error('您没有创建虚拟机的权限')
      return
    }

    // 加载可用主机列表
    const hosts = userQuota.assigned_hosts || []
    setAvailableHosts(hosts)

    // 重置表单
    createVMForm.resetFields()
    setUuidPrefix('')
    setMinDiskSize(10)
    setNicList([{ id: 0, type: 'nat', ip: '' }])
    setNicCounter(1)
    setHostConfig(null)
    
    // 生成随机密码和VNC端口
    const randomPassword = generateRandomPassword()
    const randomVNCPort = Math.floor(Math.random() * (6999 - 5900 + 1)) + 5900
    
    createVMForm.setFieldsValue({
      os_pass: randomPassword,
      vc_pass: randomPassword,
      vc_port: randomVNCPort,
      cpu_num: 2,
      mem_num: 2,
      hdd_num: 20,
      gpu_mem: 128,
      flu_num: 100,
      speed_u: 100,
      speed_d: 100,
      web_num: 10,
      nat_num: 10,
    })

    setCreateVMModalVisible(true)
  }

  /**
   * 生成随机密码
   */
  const generateRandomPassword = () => {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*'
    let result = ''
    for (let i = 0; i < 12; i++) {
      result += chars.charAt(Math.floor(Math.random() * chars.length))
    }
    return result
  }

  /**
   * 添加网卡
   */
  const addNic = () => {
    setNicList([...nicList, { id: nicCounter, type: 'nat', ip: '' }])
    setNicCounter(nicCounter + 1)
  }

  /**
   * 移除网卡
   */
  const removeNic = (id: number) => {
    setNicList(nicList.filter(nic => nic.id !== id))
  }

  /**
   * 操作系统变更
   */
  const handleOsChange = (value: string) => {
    if (!hostConfig?.system_maps) return
    
    const entry = Object.entries(hostConfig.system_maps).find(([_, val]) => {
      const imageFile = Array.isArray(val) ? val[0] : val
      return imageFile === value
    })
    
    if (entry) {
      const config = entry[1]
      const minSize = Array.isArray(config) && config.length > 1 ? Number(config[1]) : 10
      setMinDiskSize(minSize)
      // 触发硬盘字段验证
      createVMForm.validateFields(['hdd_num'])
    }
  }

  /**
   * 加载主机的系统镜像
   */
  const handleHostChange = async (hostName: string) => {
    try {
      const result = await api.get(`/api/client/os-images/${hostName}`)
      if (result.code === 200 && result.data) {
        setHostConfig(result.data)
        
        // 设置UUID前缀
        const prefix = result.data.filter_name || ''
        setUuidPrefix(prefix ? (prefix.endsWith('-') ? prefix : prefix + '-') : '')
        
        // 设置可用镜像
        if (result.data.system_maps) {
          // system_maps 值可能是 [filename, minSize] 或 filename
          const images = Object.entries(result.data.system_maps).map(([name, val]) => {
             return {
               label: name,
               value: Array.isArray(val) ? val[0] : val
             }
          })
          setAvailableImages(images.map(i => i.value as string))
          // 同时也需要保存映射关系以供选择显示，这里简化处理，假设value即文件名
        }
      }
    } catch (error) {
      console.error('加载系统镜像失败:', error)
      message.error('加载系统镜像失败')
    }
  }

  /**
   * 创建虚拟机
   */
  const handleCreateVM = async () => {
    try {
      const values = await createVMForm.validateFields()
      
      // 构造完整UUID
      const fullUuid = uuidPrefix ? `${uuidPrefix}${values.uuid_suffix}` : values.uuid_suffix

      // 构造网卡配置
      const nicAll: any = {}
      nicList.forEach((nic, index) => {
        nicAll[`ethernet${index}`] = {
          nic_type: nic.type,
          ip4_addr: nic.ip || '',
        }
      })

      // 转换单位：GB -> MB
      const data = {
        ...values,
        uuid: fullUuid,
        mem_num: Math.round(values.mem_num * 1024),
        hdd_num: Math.round(values.hdd_num * 1024),
        gpu_mem: Math.round(values.gpu_mem),
        flu_num: Math.round(values.flu_num * 1024),
        nic_all: nicAll,
      }
      
      // 删除临时字段
      delete data.uuid_suffix

      const result = await api.post(`/api/client/create/${values.host_name}`, data)
      
      if (result.code === 200) {
        message.success('虚拟机创建成功')
        setCreateVMModalVisible(false)
        loadDashboard()
      } else {
        message.error(result.msg || '创建失败')
      }
    } catch (error) {
      console.error('创建虚拟机失败:', error)
      message.error('创建失败')
    }
  }

  /**
   * 打开电源操作模态框
   */
  const handleOpenPowerModal = (vm: VMInfo) => {
    setCurrentPowerVM({ uuid: vm.uuid, host: vm.host, name: vm.display_name || vm.uuid })
    setPowerModalVisible(true)
  }

  /**
   * 执行电源操作
   */
  const handlePowerAction = async (action: string) => {
    try {
      const result = await api.post(`/api/client/powers/${currentPowerVM.host}/${currentPowerVM.uuid}`, { action })
      
      if (result.code === 200) {
        message.success('操作成功')
        setPowerModalVisible(false)
        loadDashboard()
      } else {
        message.error(result.msg || '操作失败')
      }
    } catch (error) {
      console.error('电源操作失败:', error)
      message.error('操作失败')
    }
  }

  /**
   * 打开VNC控制台
   */
  const handleOpenVNC = async (vm: VMInfo) => {
    try {
      const result = await api.get(`/api/client/remote/${vm.host}/${vm.uuid}`)
      if (result.code === 200 && result.data) {
        window.open(result.data, `vnc_${vm.uuid}`, 'width=1024,height=768')
      } else {
        message.error('无法获取VNC控制台地址')
      }
    } catch (error) {
      console.error('打开VNC失败:', error)
      message.error('打开VNC失败')
    }
  }

  /**
   * 格式化内存显示
   */
  const formatMemory = (mb: number) => {
    if (!mb) return '0 MB'
    if (mb >= 1024) return `${(mb / 1024).toFixed(1)} GB`
    return `${mb} MB`
  }

  /**
   * 格式化存储容量显示
   */
  const formatStorage = (mb: number): string => {
    if (!mb) return '0 MB'
    if (mb < 1024) return `${mb} MB`
    const gb = mb / 1024
    if (gb < 1024) return `${gb.toFixed(1)} GB`
    const tb = gb / 1024
    return `${tb.toFixed(1)} TB`
  }

  /**
   * 获取虚拟机状态标签
   */
  const getVMStatusTag = (vm: VMInfo) => {
    const statusList = vm.status || []
    const firstStatus = statusList.length > 0 ? statusList[0] : { ac_status: 'UNKNOWN' }
    const powerStatus = firstStatus.ac_status || 'UNKNOWN'

    const statusMap: Record<string, { text: string; color: string }> = {
      STOPPED: { text: '已停止', color: 'default' },
      STARTED: { text: '运行中', color: 'success' },
      SUSPEND: { text: '已暂停', color: 'warning' },
      ON_STOP: { text: '停止中', color: 'processing' },
      ON_OPEN: { text: '启动中', color: 'processing' },
      CRASHED: { text: '已崩溃', color: 'error' },
      UNKNOWN: { text: '未知', color: 'default' },
    }

    const status = statusMap[powerStatus] || statusMap.UNKNOWN
    return <Tag color={status.color}>{status.text}</Tag>
  }

  /**
   * 渲染管理员视图
   */
  const renderAdminView = () => (
    <>
      {/* 统计卡片 - 5个核心指标 */}
      <Row gutter={[16, 16]} className="mb-4">
        {/* 主机数量 */}
        <Col xs={12} sm={8} lg={4} xl={4} style={{ display: 'flex' }}>
          <Card 
            className="glass-card hover:shadow-xl transition-all duration-300 hover:-translate-y-1 cursor-pointer"
            style={{
              background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(37, 99, 235, 0.05) 100%)',
              border: '1px solid rgba(59, 130, 246, 0.2)',
              borderRadius: '16px',
              height: '100%',
              width: '100%',
            }}
            onClick={() => navigate('/hosts')}
          >
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0" style={{
                background: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)'
              }}>
                <CloudServerOutlined className="text-white text-xl" />
              </div>
              <div className="min-w-0">
                <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">主机数量</div>
                <div className="text-2xl font-bold" style={{
                  background: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent'
                }}>
                  {systemStats.hosts_count}
                </div>
              </div>
            </div>
          </Card>
        </Col>
        
        {/* 虚拟机数量 */}
        <Col xs={12} sm={8} lg={4} xl={4} style={{ display: 'flex' }}>
          <Card 
            className="glass-card hover:shadow-xl transition-all duration-300 hover:-translate-y-1"
            style={{
              background: 'linear-gradient(135deg, rgba(139, 92, 246, 0.1) 0%, rgba(124, 58, 237, 0.05) 100%)',
              border: '1px solid rgba(139, 92, 246, 0.2)',
              borderRadius: '16px',
              height: '100%',
              width: '100%',
            }}
          >
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0" style={{
                background: 'linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)'
              }}>
                <DesktopOutlined className="text-white text-xl" />
              </div>
              <div className="min-w-0">
                <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">虚拟机数量</div>
                <div className="text-2xl font-bold" style={{
                  background: 'linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent'
                }}>
                  {systemStats.vms_count}
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-400">
                  <CheckCircleOutlined className="text-green-500 mr-1" />{systemStats.running_vms} 运行中
                </div>
              </div>
            </div>
          </Card>
        </Col>
        
        {/* 用户数量 */}
        <Col xs={12} sm={8} lg={4} xl={4} style={{ display: 'flex' }}>
          <Card 
            className="glass-card hover:shadow-xl transition-all duration-300 hover:-translate-y-1 cursor-pointer"
            style={{
              background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(5, 150, 105, 0.05) 100%)',
              border: '1px solid rgba(16, 185, 129, 0.2)',
              borderRadius: '16px',
              height: '100%',
              width: '100%',
            }}
            onClick={() => navigate('/settings')}
          >
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0" style={{
                background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)'
              }}>
                <TeamOutlined className="text-white text-xl" />
              </div>
              <div className="min-w-0">
                <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">用户数量</div>
                <div className="text-2xl font-bold" style={{
                  background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent'
                }}>
                  {systemStats.users_count}
                </div>
              </div>
            </div>
          </Card>
        </Col>
        
        {/* NAT端口数量 */}
        <Col xs={12} sm={8} lg={4} xl={4} style={{ display: 'flex' }}>
          <Card 
            className="glass-card hover:shadow-xl transition-all duration-300 hover:-translate-y-1"
            style={{
              background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.1) 0%, rgba(217, 119, 6, 0.05) 100%)',
              border: '1px solid rgba(245, 158, 11, 0.2)',
              borderRadius: '16px',
              height: '100%',
              width: '100%',
            }}
          >
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0" style={{
                background: 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)'
              }}>
                <ApiOutlined className="text-white text-xl" />
              </div>
              <div className="min-w-0">
                <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">NAT端口</div>
                <div className="text-2xl font-bold" style={{
                  background: 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent'
                }}>
                  {systemStats.total_nat_ports}
                </div>
              </div>
            </div>
          </Card>
        </Col>
        
        {/* WEB代理数量 */}
        <Col xs={12} sm={8} lg={4} xl={4} style={{ display: 'flex' }}>
          <Card 
            className="glass-card hover:shadow-xl transition-all duration-300 hover:-translate-y-1"
            style={{
              background: 'linear-gradient(135deg, rgba(6, 182, 212, 0.1) 0%, rgba(8, 145, 178, 0.05) 100%)',
              border: '1px solid rgba(6, 182, 212, 0.2)',
              borderRadius: '16px',
              height: '100%',
              width: '100%',
            }}
          >
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0" style={{
                background: 'linear-gradient(135deg, #06b6d4 0%, #0891b2 100%)'
              }}>
                <GlobalOutlined className="text-white text-xl" />
              </div>
              <div className="min-w-0">
                <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">WEB代理</div>
                <div className="text-2xl font-bold" style={{
                  background: 'linear-gradient(135deg, #06b6d4 0%, #0891b2 100%)',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent'
                }}>
                  {systemStats.total_web_proxy}
                </div>
              </div>
            </div>
          </Card>
        </Col>
        
        {/* 系统状态 */}
        <Col xs={12} sm={8} lg={4} xl={4} style={{ display: 'flex' }}>
          <Card 
            className="glass-card hover:shadow-xl transition-all duration-300 hover:-translate-y-1"
            style={{
              background: 'linear-gradient(135deg, rgba(34, 197, 94, 0.1) 0%, rgba(22, 163, 74, 0.05) 100%)',
              border: '1px solid rgba(34, 197, 94, 0.2)',
              borderRadius: '16px',
              height: '100%',
              width: '100%',
            }}
          >
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0" style={{
                background: 'linear-gradient(135deg, #22c55e 0%, #16a34a 100%)'
              }}>
                <CheckCircleOutlined className="text-white text-xl" />
              </div>
              <div className="min-w-0">
                <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">系统状态</div>
                <div className="text-lg font-bold text-green-600 dark:text-green-400">正常运行</div>
                <div className="text-xs text-gray-500 dark:text-gray-400">{lastUpdate}</div>
              </div>
            </div>
          </Card>
        </Col>
      </Row>

      {/* 主机列表表格 */}
      <Card 
        title={
          <div className="flex items-center gap-2">
            <CloudServerOutlined className="text-xl" />
            <span>主机列表</span>
          </div>
        }
        extra={
          <Space>
            <Button 
              icon={<SaveOutlined />} 
              onClick={handleSaveAll}
            >
              保存配置
            </Button>
            <Button 
              icon={<SyncOutlined />} 
              onClick={loadDashboard}
            >
              刷新
            </Button>
            <Button 
              type="primary" 
              icon={<PlusOutlined />} 
              onClick={() => navigate('/hosts')}
            >
              管理主机
            </Button>
          </Space>
        }
        className="glass-card mt-12"
        style={{ borderRadius: '16px' }}
      >
        <Table
          dataSource={Object.entries(hosts).map(([name, host]: [string, any]) => ({
            key: name,
            name: name,
            ...host,
          }))}
          columns={[
            {
              title: '主机名称',
              dataIndex: 'name',
              key: 'name',
              width: 160,
              fixed: 'left',
              render: (name: string, record: any) => (
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0" style={{
                    background: record.status === 'online' 
                      ? 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)'
                      : 'linear-gradient(135deg, #6b7280 0%, #4b5563 100%)'
                  }}>
                    <CloudServerOutlined className="text-white text-lg" />
                  </div>
                  <div>
                    <div className="font-semibold">{name}</div>
                    <div className="text-xs text-gray-500">{record.server_addr || record.addr || '-'}</div>
                  </div>
                </div>
              ),
            },
            {
              title: '类型',
              dataIndex: 'server_type',
              key: 'server_type',
              width: 120,
              render: (type: string) => (
                <Tag color={
                  type === 'VmwareWork' ? 'blue' :
                  type === 'vSphereESXi' ? 'purple' :
                  type === 'Containers' ? 'cyan' : 'default'
                }>
                  {type || '未知'}
                </Tag>
              ),
            },
            {
              title: '虚拟机',
              key: 'vms',
              width: 120,
              render: (_: any, record: any) => {
                const current = record.vms_count || record.vm_count || 0
                const max = record.max_vms || 50
                const percent = max > 0 ? Math.round((current / max) * 100) : 0
                return (
                  <div>
                    <div className="text-xs text-gray-500 mb-1">{current} / {max}</div>
                    <Progress percent={percent} size="small"
                      strokeColor={percent > 80 ? '#ef4444' : percent > 60 ? '#f59e0b' : '#22c55e'}
                      format={(p) => `${p || 0}%`}
                    />
                  </div>
                )
              },
            },
            {
              title: 'CPU',
              dataIndex: 'cpu_usage',
              key: 'cpu_usage',
              width: 120,
              render: (usage: number, record: any) => {
                const percent = usage || 0
                const used = record.cpu_used || '-'
                const total = record.cpu_total || '-'
                return (
                  <div>
                    <div className="text-xs text-gray-500 mb-1">{used} / {total}</div>
                    <Progress 
                      percent={percent} 
                      size="small"
                      strokeColor={percent > 80 ? '#ef4444' : percent > 60 ? '#f59e0b' : '#22c55e'}
                      format={(p) => `${(p || 0).toFixed(0)}%`}
                    />
                  </div>
                )
              },
            },
            {
              title: 'GPU',
              dataIndex: 'gpu_usage',
              key: 'gpu_usage',
              width: 120,
              render: (usage: number, record: any) => {
                const percent = usage || 0
                const used = record.gpu_used || '-'
                const total = record.gpu_total || '-'
                return (
                  <div>
                    <div className="text-xs text-gray-500 mb-1">{used} / {total}</div>
                    <Progress 
                      percent={percent} 
                      size="small"
                      strokeColor={percent > 80 ? '#ef4444' : percent > 60 ? '#f59e0b' : '#8b5cf6'}
                      format={(p) => `${(p || 0).toFixed(0)}%`}
                    />
                  </div>
                )
              },
            },
            {
              title: '内存',
              dataIndex: 'memory_usage',
              key: 'memory_usage',
              width: 120,
              render: (usage: number, record: any) => {
                const percent = usage || 0
                const used = record.memory_used || '-'
                const total = record.memory_total || '-'
                return (
                  <div>
                    <div className="text-xs text-gray-500 mb-1">{used} / {total}</div>
                    <Progress 
                      percent={percent} 
                      size="small"
                      strokeColor={percent > 80 ? '#ef4444' : percent > 60 ? '#f59e0b' : '#10b981'}
                      format={(p) => `${(p || 0).toFixed(0)}%`}
                    />
                  </div>
                )
              },
            },
            {
              title: '硬盘',
              dataIndex: 'disk_usage',
              key: 'disk_usage',
              width: 120,
              render: (usage: number, record: any) => {
                const percent = usage || 0
                const used = record.disk_used || '-'
                const total = record.disk_total || '-'
                return (
                  <div>
                    <div className="text-xs text-gray-500 mb-1">{used} / {total}</div>
                    <Progress 
                      percent={percent} 
                      size="small"
                      strokeColor={percent > 80 ? '#ef4444' : percent > 60 ? '#f59e0b' : '#06b6d4'}
                      format={(p) => `${(p || 0).toFixed(0)}%`}
                    />
                  </div>
                )
              },
            },
            {
              title: '状态',
              key: 'status',
              width: 100,
              render: (_: any, record: any) => {
                const status = record.status || 'unknown'
                const enabled = record.enabled !== false
                return (
                  <Space direction="vertical" size={0}>
                    <Tag color={
                      status === 'online' ? 'success' :
                      status === 'offline' ? 'error' : 'default'
                    }>
                      {status === 'online' ? '在线' : status === 'offline' ? '离线' : '未知'}
                    </Tag>
                    <span className="text-xs text-gray-500">
                      {enabled ? <CheckCircleOutlined className="text-green-500" /> : <CloseCircleOutlined className="text-red-500" />}
                      {enabled ? ' 已启用' : ' 已禁用'}
                    </span>
                  </Space>
                )
              },
            },
            {
              title: '操作',
              key: 'action',
              width: 120,
              fixed: 'right',
              render: (_: any, _record: any) => (
                <Space>
                  <Tooltip title="查看详情">
                    <Button 
                      type="primary" 
                      size="small"
                      icon={<SettingOutlined />}
                      onClick={() => navigate(`/hosts`)}
                    >
                      管理
                    </Button>
                  </Tooltip>
                </Space>
              ),
            },
          ]}
          pagination={false}
          scroll={{ x: 1000, y: 440 }}
          size="middle"
          locale={{ emptyText: '暂无主机数据' }}
        />
      </Card>

      {/* 快速操作 */}
      <div className="mt-6" style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
        <div style={{ flex: '1 1 0', minWidth: '120px', display: 'flex' }}>
          <Card
            hoverable
            className="glass-card hover:shadow-xl transition-all duration-300 hover:-translate-y-1 cursor-pointer"
            style={{
              borderRadius: '16px',
              height: '100%',
              width: '100%',
              border: '1px solid rgba(59, 130, 246, 0.2)',
            }}
            onClick={() => navigate('/hosts')}
          >
            <div className="flex flex-col items-center justify-center py-2 gap-2">
              <div className="w-14 h-14 rounded-2xl flex items-center justify-center" style={{
                background: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)'
              }}>
                <CloudServerOutlined className="text-white text-2xl" />
              </div>
              <div className="text-sm font-semibold">管理主机</div>
              <div className="text-xs text-gray-400 text-center">查看和管理所有物理主机</div>
            </div>
          </Card>
        </div>
        <div style={{ flex: '1 1 0', minWidth: '120px', display: 'flex' }}>
          <Card
            hoverable
            className="glass-card hover:shadow-xl transition-all duration-300 hover:-translate-y-1 cursor-pointer"
            style={{
              borderRadius: '16px',
              height: '100%',
              width: '100%',
              border: '1px solid rgba(139, 92, 246, 0.2)',
            }}
            onClick={() => navigate('/docks')}
          >
            <div className="flex flex-col items-center justify-center py-2 gap-2">
              <div className="w-14 h-14 rounded-2xl flex items-center justify-center" style={{
                background: 'linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)'
              }}>
                <DesktopOutlined className="text-white text-2xl" />
              </div>
              <div className="text-sm font-semibold">管理实例</div>
              <div className="text-xs text-gray-400 text-center">管理所有虚拟机实例</div>
            </div>
          </Card>
        </div>
        <div style={{ flex: '1 1 0', minWidth: '120px', display: 'flex' }}>
          <Card
            hoverable
            className="glass-card hover:shadow-xl transition-all duration-300 hover:-translate-y-1 cursor-pointer"
            style={{
              borderRadius: '16px',
              height: '100%',
              width: '100%',
              border: '1px solid rgba(245, 158, 11, 0.2)',
            }}
            onClick={() => navigate('/nat')}
          >
            <div className="flex flex-col items-center justify-center py-2 gap-2">
              <div className="w-14 h-14 rounded-2xl flex items-center justify-center" style={{
                background: 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)'
              }}>
                <ApiOutlined className="text-white text-2xl" />
              </div>
              <div className="text-sm font-semibold">管理端口</div>
              <div className="text-xs text-gray-400 text-center">NAT端口映射配置</div>
            </div>
          </Card>
        </div>
        <div style={{ flex: '1 1 0', minWidth: '120px', display: 'flex' }}>
          <Card
            hoverable
            className="glass-card hover:shadow-xl transition-all duration-300 hover:-translate-y-1 cursor-pointer"
            style={{
              borderRadius: '16px',
              height: '100%',
              width: '100%',
              border: '1px solid rgba(6, 182, 212, 0.2)',
            }}
            onClick={() => navigate('/proxy')}
          >
            <div className="flex flex-col items-center justify-center py-2 gap-2">
              <div className="w-14 h-14 rounded-2xl flex items-center justify-center" style={{
                background: 'linear-gradient(135deg, #06b6d4 0%, #0891b2 100%)'
              }}>
                <GlobalOutlined className="text-white text-2xl" />
              </div>
              <div className="text-sm font-semibold">管理代理</div>
              <div className="text-xs text-gray-400 text-center">WEB反向代理配置</div>
            </div>
          </Card>
        </div>
        <div style={{ flex: '1 1 0', minWidth: '120px', display: 'flex' }}>
          <Card
            hoverable
            className="glass-card hover:shadow-xl transition-all duration-300 hover:-translate-y-1 cursor-pointer"
            style={{
              borderRadius: '16px',
              height: '100%',
              width: '100%',
              border: '1px solid rgba(16, 185, 129, 0.2)',
            }}
            onClick={() => navigate('/users')}
          >
            <div className="flex flex-col items-center justify-center py-2 gap-2">
              <div className="w-14 h-14 rounded-2xl flex items-center justify-center" style={{
                background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)'
              }}>
                <TeamOutlined className="text-white text-2xl" />
              </div>
              <div className="text-sm font-semibold">管理用户</div>
              <div className="text-xs text-gray-400 text-center">用户账号与权限管理</div>
            </div>
          </Card>
        </div>
        <div style={{ flex: '1 1 0', minWidth: '120px', display: 'flex' }}>
          <Card
            hoverable
            className="glass-card hover:shadow-xl transition-all duration-300 hover:-translate-y-1 cursor-pointer"
            style={{
              borderRadius: '16px',
              height: '100%',
              width: '100%',
              border: '1px solid rgba(239, 68, 68, 0.2)',
            }}
            onClick={() => navigate('/logs')}
          >
            <div className="flex flex-col items-center justify-center py-2 gap-2">
              <div className="w-14 h-14 rounded-2xl flex items-center justify-center" style={{
                background: 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)'
              }}>
                <DatabaseOutlined className="text-white text-2xl" />
              </div>
              <div className="text-sm font-semibold">日志查看</div>
              <div className="text-xs text-gray-400 text-center">系统操作与审计日志</div>
            </div>
          </Card>
        </div>
        <div style={{ flex: '1 1 0', minWidth: '120px', display: 'flex' }}>
          <Card
            hoverable
            className="glass-card hover:shadow-xl transition-all duration-300 hover:-translate-y-1 cursor-pointer"
            style={{
              borderRadius: '16px',
              height: '100%',
              width: '100%',
              border: '1px solid rgba(107, 114, 128, 0.2)',
            }}
            onClick={() => navigate('/settings')}
          >
            <div className="flex flex-col items-center justify-center py-2 gap-2">
              <div className="w-14 h-14 rounded-2xl flex items-center justify-center" style={{
                background: 'linear-gradient(135deg, #6b7280 0%, #4b5563 100%)'
              }}>
                <SettingOutlined className="text-white text-2xl" />
              </div>
              <div className="text-sm font-semibold">系统设置</div>
              <div className="text-xs text-gray-400 text-center">全局参数与系统配置</div>
            </div>
          </Card>
        </div>
      </div>
    </>
  )

  /**
   * 渲染普通用户视图
   */
  const renderUserView = () => {
    if (!userQuota) return null

    return (
      <>
        {/* 资源使用情况 - 第一行 */}
        <Row gutter={[16, 16]} className="mb-4">
          <Col xs={12} sm={8} lg={4}>
            <Card className="glass-card hover:shadow-lg transition-shadow">
              <div className="flex items-center justify-between mb-3">
                <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-blue-600 rounded-lg flex items-center justify-center">
                  <ThunderboltOutlined className="text-white text-lg" />
                </div>
                <div className="text-right">
                  <div className="text-xs mb-1">CPU核心</div>
                  <div className="text-lg font-bold">
                    {userQuota.used_cpu}/{userQuota.quota_cpu}
                  </div>
                </div>
              </div>
              <Progress percent={Math.round((userQuota.used_cpu / userQuota.quota_cpu) * 100)} size="small" />
            </Card>
          </Col>
          <Col xs={12} sm={8} lg={4}>
            <Card className="glass-card hover:shadow-lg transition-shadow">
              <div className="flex items-center justify-between mb-3">
                <div className="w-10 h-10 bg-gradient-to-br from-pink-500 to-pink-600 rounded-lg flex items-center justify-center">
                  <PlayCircleOutlined className="text-white text-lg" />
                </div>
                <div className="text-right">
                  <div className="text-xs mb-1">GPU显存使用率</div>
                  <div className="text-lg font-bold">
                    {Math.round((userQuota.used_gpu / userQuota.quota_gpu) * 100)}%
                  </div>
                </div>
              </div>
              <Progress percent={Math.round((userQuota.used_gpu / userQuota.quota_gpu) * 100)} size="small" strokeColor="#ec4899" />
              <div className="text-xs mt-1">
                {(userQuota.used_gpu / 1024).toFixed(1)}/{(userQuota.quota_gpu / 1024).toFixed(1)}GB
              </div>
            </Card>
          </Col>
          <Col xs={12} sm={8} lg={4}>
            <Card className="glass-card hover:shadow-lg transition-shadow">
              <div className="flex items-center justify-between mb-3">
                <div className="w-10 h-10 bg-gradient-to-br from-green-500 to-green-600 rounded-lg flex items-center justify-center">
                  <RadarChartOutlined className="text-white text-lg" />
                </div>
                <div className="text-right">
                  <div className="text-xs mb-1">内存使用率</div>
                  <div className="text-lg font-bold">
                    {Math.round((userQuota.used_ram / userQuota.quota_ram) * 100)}%
                  </div>
                </div>
              </div>
              <Progress percent={Math.round((userQuota.used_ram / userQuota.quota_ram) * 100)} size="small" strokeColor="#10b981" />
              <div className="text-xs mt-1">
                {(userQuota.used_ram / 1024).toFixed(1)}/{(userQuota.quota_ram / 1024).toFixed(1)}GB
              </div>
            </Card>
          </Col>
          <Col xs={12} sm={8} lg={4}>
            <Card className="glass-card hover:shadow-lg transition-shadow">
              <div className="flex items-center justify-between mb-3">
                <div className="w-10 h-10 bg-gradient-to-br from-purple-500 to-purple-600 rounded-lg flex items-center justify-center">
                  <HddOutlined className="text-white text-lg" />
                </div>
                <div className="text-right">
                  <div className="text-xs mb-1">存储使用率</div>
                  <div className="text-lg font-bold">
                    {Math.round((userQuota.used_ssd / userQuota.quota_ssd) * 100)}%
                  </div>
                </div>
              </div>
              <Progress percent={Math.round((userQuota.used_ssd / userQuota.quota_ssd) * 100)} size="small" strokeColor="#8b5cf6" />
              <div className="text-xs mt-1">
                {(userQuota.used_ssd / 1024).toFixed(1)}/{(userQuota.quota_ssd / 1024).toFixed(1)}GB
              </div>
            </Card>
          </Col>
          <Col xs={12} sm={8} lg={4}>
            <Card className="glass-card hover:shadow-lg transition-shadow">
              <div className="flex items-center justify-between mb-3">
                <div className="w-10 h-10 bg-gradient-to-br from-yellow-500 to-yellow-600 rounded-lg flex items-center justify-center">
                  <GlobalOutlined className="text-white text-lg" />
                </div>
                <div className="text-right">
                  <div className="text-xs mb-1">流量</div>
                  <div className="text-lg font-bold">
                    {(userQuota.used_traffic / 1024).toFixed(1)}/{(userQuota.quota_traffic / 1024).toFixed(1)}GB
                  </div>
                </div>
              </div>
              <Progress percent={Math.round((userQuota.used_traffic / userQuota.quota_traffic) * 100)} size="small" strokeColor="#eab308" />
            </Card>
          </Col>
          <Col xs={12} sm={8} lg={4}>
            <Card className="glass-card hover:shadow-lg transition-shadow">
              <div className="flex items-center justify-between mb-3">
                <div className="w-10 h-10 bg-gradient-to-br from-indigo-500 to-indigo-600 rounded-lg flex items-center justify-center">
                  <ApiOutlined className="text-white text-lg" />
                </div>
                <div className="text-right">
                  <div className="text-xs mb-1">NAT端口</div>
                  <div className="text-lg font-bold">
                    {userQuota.used_nat_ports}/{userQuota.quota_nat_ports}
                  </div>
                </div>
              </div>
              <Progress percent={Math.round((userQuota.used_nat_ports / userQuota.quota_nat_ports) * 100)} size="small" strokeColor="#6366f1" />
            </Card>
          </Col>
        </Row>

        {/* 资源使用情况 - 第二行 */}
        <Row gutter={[16, 16]} className="mb-6">
          <Col xs={12} sm={8} lg={4}>
            <Card className="glass-card hover:shadow-lg transition-shadow">
              <div className="flex items-center justify-between mb-3">
                <div className="w-10 h-10 bg-gradient-to-br from-teal-500 to-teal-600 rounded-lg flex items-center justify-center">
                  <CloudOutlined className="text-white text-lg" />
                </div>
                <div className="text-right">
                  <div className="text-xs mb-1">WEB代理</div>
                  <div className="text-lg font-bold">
                    {userQuota.used_web_proxy}/{userQuota.quota_web_proxy}
                  </div>
                </div>
              </div>
              <Progress percent={Math.round((userQuota.used_web_proxy / userQuota.quota_web_proxy) * 100)} size="small" strokeColor="#14b8a6" />
            </Card>
          </Col>
          <Col xs={12} sm={8} lg={4}>
            <Card className="glass-card hover:shadow-lg transition-shadow">
              <div className="flex items-center justify-between mb-3">
                <div className="w-10 h-10 bg-gradient-to-br from-red-500 to-red-600 rounded-lg flex items-center justify-center">
                  <UploadOutlined className="text-white text-lg" />
                </div>
                <div className="text-right">
                  <div className="text-xs mb-1">上行带宽</div>
                  <div className="text-lg font-bold">
                    {userQuota.used_bandwidth_up}/{userQuota.quota_bandwidth_up}Mbps
                  </div>
                </div>
              </div>
              <Progress percent={Math.round((userQuota.used_bandwidth_up / userQuota.quota_bandwidth_up) * 100)} size="small" strokeColor="#ef4444" />
            </Card>
          </Col>
          <Col xs={12} sm={8} lg={4}>
            <Card className="glass-card hover:shadow-lg transition-shadow">
              <div className="flex items-center justify-between mb-3">
                <div className="w-10 h-10 bg-gradient-to-br from-cyan-500 to-cyan-600 rounded-lg flex items-center justify-center">
                  <DownloadOutlined className="text-white text-lg" />
                </div>
                <div className="text-right">
                  <div className="text-xs mb-1">下行带宽</div>
                  <div className="text-lg font-bold">
                    {userQuota.used_bandwidth_down}/{userQuota.quota_bandwidth_down}Mbps
                  </div>
                </div>
              </div>
              <Progress percent={Math.round((userQuota.used_bandwidth_down / userQuota.quota_bandwidth_down) * 100)} size="small" strokeColor="#06b6d4" />
            </Card>
          </Col>
          <Col xs={12} sm={8} lg={4}>
            <Card className="glass-card hover:shadow-lg transition-shadow">
              <div className="flex items-center justify-between mb-3">
                <div className="w-10 h-10 bg-gradient-to-br from-orange-500 to-orange-600 rounded-lg flex items-center justify-center">
                  <DatabaseOutlined className="text-white text-lg" />
                </div>
                <div className="text-right">
                  <div className="text-xs mb-1">我的虚拟机</div>
                  <div className="text-lg font-bold">{myVMCount}</div>
                </div>
              </div>
              <div className="text-xs">
                <CheckCircleOutlined className="text-green-500" /> 运行中: {myRunningVMCount}
              </div>
            </Card>
          </Col>
        </Row>

        {/* 我的虚拟机列表 */}
        <Card
          className="glass-card"
          title={<><DesktopOutlined className="mr-2" />我的虚拟机</>}
          extra={
            <Button type="primary" icon={<PlusOutlined />} onClick={handleOpenCreateVM}>
              创建虚拟机
            </Button>
          }
        >
          {myVMs.length === 0 ? (
            <div className="text-center py-8">
              <DesktopOutlined className="text-5xl mb-4" style={{ color: 'var(--text-tertiary)' }} />
              <p style={{ color: 'var(--text-secondary)' }}>暂无虚拟机</p>
              <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>请联系管理员为您分配权限</p>
            </div>
          ) : (
            <Row gutter={[16, 16]}>
              {myVMs.map((vm) => {
                const config = vm.config || {}
                const nicAll = config.nic_all || {}
                const firstNic = Object.values(nicAll)[0] as any || {}

                return (
                  <Col xs={24} lg={12} key={vm.uuid}>
                    <Card className="glass-card hover:shadow-lg transition-shadow">
                      <div className="flex items-start justify-between mb-4">
                        <div className="flex items-center gap-3">
                          <div className="w-12 h-12 bg-gradient-to-br from-purple-500 to-purple-600 rounded-lg flex items-center justify-center">
                            <DesktopOutlined className="text-white text-xl" />
                          </div>
                          <div>
                            <div className="font-semibold">{vm.display_name || vm.uuid}</div>
                            <div className="text-sm">{vm.host} - {config.os_name || '未知系统'}</div>
                          </div>
                        </div>
                        {getVMStatusTag(vm)}
                      </div>

                      {/* 基础资源信息 */}
                      <div className="grid grid-cols-2 gap-3 text-sm mb-4">
                        <div className="flex items-center gap-2">
                          <ThunderboltOutlined />
                          <span>CPU: <span className="font-medium">{config.cpu_num || 0} 核</span></span>
                        </div>
                        <div className="flex items-center gap-2">
                          <RadarChartOutlined />
                          <span>内存: <span className="font-medium">{formatMemory(config.mem_num)}</span></span>
                        </div>
                        <div className="flex items-center gap-2">
                          <HddOutlined />
                          <span>硬盘: <span className="font-medium">{formatMemory(config.hdd_num)}</span></span>
                        </div>
                        <div className="flex items-center gap-2">
                          <PlayCircleOutlined />
                          <span>显存: <span className="font-medium">{formatMemory(config.gpu_mem)}</span></span>
                        </div>
                      </div>

                      {/* 端口信息 */}
                      <div className="grid grid-cols-2 gap-3 text-sm mb-4 p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
                        <div className="flex items-center gap-2">
                          <ApiOutlined />
                          <span>NAT端口: <span className="font-medium">{config.nat_num || 0}个</span></span>
                        </div>
                        <div className="flex items-center gap-2">
                          <CloudOutlined />
                          <span>Web代理: <span className="font-medium">{config.web_num || 0}个</span></span>
                        </div>
                      </div>

                      {/* 网卡信息 */}
                      <div className="text-sm p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800 mb-4">
                        <div className="flex items-center gap-2 text-blue-700 dark:text-blue-400 font-medium mb-2">
                          <GlobalOutlined />
                          <span>网卡信息</span>
                        </div>
                        <div className="space-y-1 text-xs">
                          <div className="flex items-center gap-2">
                            <span className="w-12" style={{ color: 'var(--text-secondary)' }}>IPv4:</span>
                            <span className="font-mono">{firstNic.ip4_addr || '-'}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="w-12" style={{ color: 'var(--text-secondary)' }}>IPv6:</span>
                            <span className="font-mono">{firstNic.ip6_addr || '未配置'}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="w-12" style={{ color: 'var(--text-secondary)' }}>MAC:</span>
                            <span className="font-mono">{firstNic.mac_addr || '-'}</span>
                          </div>
                        </div>
                      </div>

                      {/* 操作按钮 */}
                      <div className="flex items-center justify-between pt-3 border-t border-gray-200 dark:border-gray-700">
                        <Button type="link" onClick={() => navigate(`/hosts/${vm.host}/vms/${vm.uuid}`)}>
                          查看详情
                        </Button>
                        <Space>
                          <Button icon={<MonitorOutlined />} onClick={() => handleOpenVNC(vm)}>
                            VNC控制台
                          </Button>
                          <Button icon={<PoweroffOutlined />} onClick={() => handleOpenPowerModal(vm)} />
                        </Space>
                      </div>
                    </Card>
                  </Col>
                )
              })}
            </Row>
          )}
        </Card>
      </>
    )
  }

  return (
    <div className="p-6 min-h-screen">
      {/* 页面标题 */}
      <PageHeader
        icon={<DesktopOutlined />}
        title="全局资源概览"
        subtitle="查看您的资源使用情况和配额信息"
      />

      {/* 根据用户角色渲染不同视图 */}
      {isAdmin ? renderAdminView() : renderUserView()}

      {/* 创建虚拟机模态框 */}
      <Modal
        title="创建虚拟机"
        open={createVMModalVisible}
        onCancel={() => setCreateVMModalVisible(false)}
        onOk={handleCreateVM}
        width={800}
        okText="创建"
        cancelText="取消"
      >
        <Form form={createVMForm} layout="vertical">
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item label="主机" name="host_name" rules={[{ required: true, message: '请选择主机' }]}>
                <Select placeholder="请选择主机" onChange={handleHostChange}>
                  {availableHosts.map((host) => (
                    <Select.Option key={host} value={host}>
                      {host}
                    </Select.Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item label="操作系统" name="os_name" rules={[{ required: true, message: '请选择操作系统' }]}>
                <Select placeholder="请先选择主机" onChange={handleOsChange}>
                  {availableImages.map((image) => (
                    <Select.Option key={image} value={image}>
                      {image}
                    </Select.Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={24}>
              <Form.Item label="虚拟机UUID" required>
                <Input.Group compact>
                  <Input 
                    style={{ width: '40%', textAlign: 'right', color: '#000', cursor: 'default' }}
                    value={uuidPrefix} 
                    disabled 
                    placeholder="前缀"
                  />
                  <Form.Item
                    name="uuid_suffix"
                    noStyle
                    rules={[{ required: true, message: '请输入UUID后缀' }]}
                  >
                    <Input style={{ width: '70%' }} placeholder="输入UUID后缀 (例如: my-vm-01)" />
                  </Form.Item>
                </Input.Group>
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item label="系统密码" name="os_pass">
                <Input.Password 
                  placeholder="自动生成密码" 
                  autoComplete="new-password"
                  data-lpignore="true"
                  data-form-type="other"
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item label="VNC密码" name="vc_pass">
                <Input.Password 
                  placeholder="与系统密码一致" 
                  autoComplete="new-password"
                  data-lpignore="true"
                  data-form-type="other"
                />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item label="VNC端口" name="vc_port">
            <Input type="number" placeholder="VNC端口" />
          </Form.Item>

          <Divider orientation="left">资源配置</Divider>
          
          <Form.Item 
            label={`CPU核心 (可用: ${userQuota ? userQuota.quota_cpu - userQuota.used_cpu : 0}个)`} 
            name="cpu_num" 
            initialValue={1}
          >
            <Slider min={1} max={userQuota ? Math.max(1, userQuota.quota_cpu - userQuota.used_cpu) : 1} marks={{ 1: '1', 4: '4', 8: '8', 16: '16' }} />
          </Form.Item>

          <Form.Item 
            label={`内存 (可用: ${userQuota ? formatStorage(userQuota.quota_ram - userQuota.used_ram) : '0MB'})`} 
            name="mem_num" 
            initialValue={1}
          >
            <Slider min={1} max={userQuota ? Math.max(1, Math.floor((userQuota.quota_ram - userQuota.used_ram) / 1024)) : 1} marks={{ 1: '1G', 4: '4G', 8: '8G', 16: '16G' }} />
          </Form.Item>

          <Form.Item 
            label={`硬盘 (可用: ${userQuota ? formatStorage(userQuota.quota_ssd - userQuota.used_ssd) : '0MB'})`} 
            name="hdd_num"
            initialValue={20}
            rules={[
              { required: true },
              { 
                validator: (_, value) => {
                  if (value < minDiskSize) {
                    return Promise.reject(new Error(`最小要求: ${minDiskSize}GB`))
                  }
                  return Promise.resolve()
                }
              }
            ]}
            extra={minDiskSize > 10 ? `当前系统最小要求: ${minDiskSize}GB` : ''}
          >
            <Slider min={10} max={userQuota ? Math.max(10, Math.floor((userQuota.quota_ssd - userQuota.used_ssd) / 1024)) : 10} marks={{ 10: '10G', 100: '100G', 500: '500G' }} />
          </Form.Item>

          <Form.Item label="GPU显存 (MB)" name="gpu_mem" initialValue={0}>
            <Slider min={0} max={16384} step={128} marks={{ 0: '0', 2048: '2G', 8192: '8G' }} />
          </Form.Item>

          <Form.Item label="下行带宽 (Mbps)" name="flu_num" initialValue={10}>
            <Slider min={1} max={100} marks={{ 1: '1M', 10: '10M', 50: '50M', 100: '100M' }} />
          </Form.Item>

          <Divider orientation="left">
            <div className="flex justify-between items-center w-full">
              <span>网卡配置</span>
              <Button type="dashed" size="small" onClick={addNic} icon={<PlusOutlined />}>添加网卡</Button>
            </div>
          </Divider>

          {nicList.map((nic, index) => (
            <Row key={nic.id} gutter={16} align="middle" className="mb-2">
              <Col span={8}>
                <span className="mr-2">eth{index}</span>
                <Select 
                  value={nic.type} 
                  onChange={val => {
                    const newList = [...nicList]
                    newList[index].type = val
                    setNicList(newList)
                  }}
                  style={{ width: 100 }}
                >
                  <Select.Option value="nat">NAT</Select.Option>
                  <Select.Option value="bridge">Bridge</Select.Option>
                </Select>
              </Col>
              <Col span={14}>
                <Input 
                  placeholder={nic.type === 'bridge' ? "指定IP (可选)" : "自动分配"}
                  value={nic.ip}
                  onChange={e => {
                    const newList = [...nicList]
                    newList[index].ip = e.target.value
                    setNicList(newList)
                  }}
                  disabled={nic.type === 'nat'}
                />
              </Col>
              <Col span={2}>
                {index > 0 && (
                  <Button 
                    type="text" 
                    danger 
                    icon={<MinusCircleOutlined />} 
                    onClick={() => removeNic(nic.id)} 
                  />
                )}
              </Col>
            </Row>
          ))}
        </Form>
      </Modal>

      {/* 电源操作模态框 */}
      <Modal
        title={`电源操作 - ${currentPowerVM.name}`}
        open={powerModalVisible}
        onCancel={() => setPowerModalVisible(false)}
        footer={null}
      >
        <Row gutter={[16, 16]}>
          <Col span={12}>
            <Button block type="primary" className="bg-green-500 hover:bg-green-600 dark:bg-green-600 dark:hover:bg-green-700" onClick={() => handlePowerAction('start')}>
              启动
            </Button>
          </Col>
          <Col span={12}>
            <Button block className="bg-yellow-500 hover:bg-yellow-600 dark:bg-yellow-600 dark:hover:bg-yellow-700 text-white" onClick={() => handlePowerAction('stop')}>
              关机
            </Button>
          </Col>
          <Col span={12}>
            <Button block type="primary" onClick={() => handlePowerAction('reset')}>
              重启
            </Button>
          </Col>
          <Col span={12}>
            <Button block onClick={() => handlePowerAction('pause')}>
              暂停
            </Button>
          </Col>
          <Col span={12}>
            <Button block type="primary" className="bg-indigo-500 hover:bg-indigo-600 dark:bg-indigo-600 dark:hover:bg-indigo-700" onClick={() => handlePowerAction('resume')}>
              恢复
            </Button>
          </Col>
          <Col span={12}>
            <Button block danger onClick={() => handlePowerAction('hard_stop')}>
              强制关机
            </Button>
          </Col>
          <Col span={12}>
            <Button block danger onClick={() => handlePowerAction('hard_reset')}>
              强制重启
            </Button>
          </Col>
        </Row>
      </Modal>
    </div>
  )
}

export default Dashboards
