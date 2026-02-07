import React, {useEffect, useState} from 'react'
import {
    Button,
    Modal,
    Form,
    Input,
    Select,
    InputNumber,
    message,
    Card,
    Row,
    Col,
    Tabs,
    Space,
    Tag,
    Tooltip
} from 'antd'
import {
    PlusOutlined,
    ReloadOutlined,
    DeleteOutlined,
    EditOutlined,
    PlayCircleOutlined,
    StopOutlined,
    ScanOutlined,
    CloudSyncOutlined,
    InfoCircleOutlined,
    CloudServerOutlined,
    GlobalOutlined,
    SettingOutlined,
    FolderOutlined,
    DatabaseOutlined,
    CopyOutlined,
    ExclamationCircleOutlined
} from '@ant-design/icons'
import {useNavigate} from 'react-router-dom'
import api from '@/utils/apis.ts'

// 主机配置接口
interface HostConfig {
    server_type?: string
    server_addr?: string
    server_user?: string
    server_pass?: string
    filter_name?: string
    images_path?: string
    dvdrom_path?: string
    system_path?: string
    backup_path?: string
    extern_path?: string
    launch_path?: string
    server_port?: number
    network_nat?: string
    network_pub?: string
    i_kuai_addr?: string
    i_kuai_user?: string
    i_kuai_pass?: string
    ports_start?: number
    ports_close?: number
    remote_port?: number
    limits_nums?: number
    system_maps?: Record<string, [string, string]>
    images_maps?: Record<string, string>
    ipaddr_maps?: Record<string, any>
    ipaddr_dnss?: string[]
    public_addr?: string[]
    extend_data?: any
}

// 主机数据接口
interface Host {
    name: string
    type: string
    addr: string
    status: string
    vm_count: number
    config?: HostConfig
}

// 主机状态接口
interface HostStatus {
    cpu_usage?: number
    cpu_total?: number
    cpu_model?: string
    cpu_heats?: number
    cpu_power?: number
    mem_usage?: number
    mem_total?: number
    ext_usage?: Record<string, [number, number]>
    network_a?: number
    network_u?: number
    network_d?: number
    gpu_usage?: Record<string, number>
    gpu_total?: number
    status?: string
}

// 引擎类型配置接口
interface EngineTypeConfig {
    enabled: boolean
    description: string
    messages?: string[]
    options?: Record<string, string>
}

// 系统映射行接口
interface SystemMapRow {
    id: string
    systemName: string
    systemFile: string
    minSize: string
}

// 镜像映射行接口
interface ImageMapRow {
    id: string
    displayName: string
    fileName: string
}

// IP地址池配置行接口
interface IpaddrMapRow {
    id: string
    setName: string
    vers: string
    type: string
    gate: string
    mask: string
    fromIp: string
    nums: number
}

/**
 * 主机管理页面
 */
function HostManage() {
    // 路由导航
    const navigate = useNavigate()

    // 状态管理
    const [hosts, setHosts] = useState<Record<string, Host>>({})
    const [hostsStatus, setHostsStatus] = useState<Record<string, HostStatus>>({})
    const [engineTypes, setEngineTypes] = useState<Record<string, EngineTypeConfig>>({})
    const [loading, setLoading] = useState(false)
    const [modalVisible, setModalVisible] = useState(false)
    const [editMode, setEditMode] = useState<'add' | 'edit'>('add')
    const [currentHost, setCurrentHost] = useState<string>('')
    const [form] = Form.useForm()

    // 用于跟踪最新的主机列表，避免闭包问题
    const hostsRef = React.useRef(hosts)

    useEffect(() => {
        hostsRef.current = hosts
    }, [hosts])

    // 动态配置状态
    const [systemMaps, setSystemMaps] = useState<SystemMapRow[]>([])
    const [imageMaps, setImageMaps] = useState<ImageMapRow[]>([])
    const [ipaddrMaps, setIpaddrMaps] = useState<IpaddrMapRow[]>([])
    const [selectedHostType, setSelectedHostType] = useState<string>('')

    // 加载引擎类型
    const loadEngineTypes = async () => {
        try {
            const result = await api.getEngineTypes()
            if (result.code === 200) {
                // 确保result.data是对象类型
                const data = result.data || {}
                if (typeof data === 'object' && !Array.isArray(data)) {
                    setEngineTypes(data as Record<string, EngineTypeConfig>)
                }
            }
        } catch (error) {
            console.error('加载引擎类型失败:', error)
        }
    }

    // 加载主机列表
    const loadHosts = async () => {
        try {
            setLoading(true)
            const result = await api.getServerDetail()
            if (result.code === 200 && result.data) {
                setHosts(result.data as unknown as Record<string, Host>)

                // 并行加载所有主机状态
                const statusPromises = Object.keys(result.data).map(name =>
                    api.getServerStatus(name).catch(() => null)
                )
                const statusResults = await Promise.all(statusPromises)

                // 构建状态映射
                const statusMap: Record<string, HostStatus> = {}
                Object.keys(result.data).forEach((name, index) => {
                    const statusResult = statusResults[index] as any
                    if (statusResult && statusResult.code === 200) {
                        statusMap[name] = statusResult.data
                    }
                })
                setHostsStatus(statusMap)
            }
        } catch (error) {
            message.error('加载主机列表失败')
        } finally {
            setLoading(false)
        }
    }

    // 初始加载
    useEffect(() => {
        loadEngineTypes()
        loadHosts()
    }, [])

    // 定时刷新状态 - 刷新主机列表和状态，确保is_enabled等字段实时更新
    useEffect(() => {
        const refreshHostsAndStatus = async () => {
            try {
                // 1. 刷新主机列表（包含is_enabled状态）
                const hostsResult = await api.getServerDetail()
                if (hostsResult.code === 200 && hostsResult.data) {
                    setHosts(hostsResult.data as unknown as Record<string, Host>)
                    
                    // 2. 并行刷新所有主机状态
                    const hostNames = Object.keys(hostsResult.data)
                    if (hostNames.length > 0) {
                        const statusPromises = hostNames.map(name =>
                            api.getServerStatus(name).catch(() => null)
                        )
                        const statusResults = await Promise.all(statusPromises)

                        // 构建状态映射
                        const statusMap: Record<string, HostStatus> = {}
                        hostNames.forEach((name, index) => {
                            const statusResult = statusResults[index] as any
                            if (statusResult && statusResult.code === 200) {
                                statusMap[name] = statusResult.data
                            }
                        })
                        setHostsStatus(statusMap)
                    }
                }
            } catch (error) {
                console.error('刷新主机数据失败:', error)
            }
        }

        // 只通过定时器执行，不立即执行
        const interval = setInterval(refreshHostsAndStatus, 10000)

        return () => clearInterval(interval)
    }, [])

    // 复制到剪贴板
    const copyToClipboard = (text: string) => {
        navigator.clipboard.writeText(text).then(() => {
            message.success(`已复制: ${text}`)
        }).catch(() => {
            message.error('复制失败')
        })
    }

    // 打开添加主机对话框
    const handleAdd = () => {
        setEditMode('add')
        setCurrentHost('')
        setSelectedHostType('')
        form.resetFields()
        setSystemMaps([{id: Date.now().toString(), systemName: '', systemFile: '', minSize: ''}])
        setImageMaps([{id: Date.now().toString(), displayName: '', fileName: ''}])
        setIpaddrMaps([{
            id: Date.now().toString(),
            setName: '',
            vers: 'ipv4',
            type: 'nat',
            gate: '',
            mask: '',
            fromIp: '',
            nums: 0
        }])
        setModalVisible(true)
    }

    // 打开编辑主机对话框
    const handleEdit = async (name: string) => {
        try {
            const result = await api.getServerDetailByName(name)
            if (result.code === 200 && result.data) {
                const hostData = result.data as unknown as Host
                setEditMode('edit')
                setCurrentHost(name)
                setSelectedHostType(hostData.type)

                const config = hostData.config || {}

                // 设置表单值
                form.setFieldsValue({
                    name: name,
                    type: hostData.type,
                    server_addr: config.server_addr,
                    server_user: config.server_user,
                    server_pass: config.server_pass,
                    filter_name: config.filter_name,
                    images_path: config.images_path,
                    dvdrom_path: config.dvdrom_path,
                    system_path: config.system_path,
                    backup_path: config.backup_path,
                    extern_path: config.extern_path,
                    launch_path: config.launch_path,
                    server_port: config.server_port,
                    network_nat: config.network_nat,
                    network_pub: config.network_pub,
                    i_kuai_addr: config.i_kuai_addr,
                    i_kuai_user: config.i_kuai_user,
                    i_kuai_pass: config.i_kuai_pass,
                    ports_start: config.ports_start,
                    ports_close: config.ports_close,
                    remote_port: config.remote_port,
                    limits_nums: config.limits_nums,
                    ipaddr_dnss: (config.ipaddr_dnss || []).join(', '),
                    public_addr: (config.public_addr || []).join(', '),
                    extend_data: config.extend_data ? JSON.stringify(config.extend_data, null, 2) : ''
                })

                // 加载系统映射
                const systemMapsData: SystemMapRow[] = []
                if (config.system_maps) {
                    Object.entries(config.system_maps).forEach(([systemName, [systemFile, minSize]]) => {
                        systemMapsData.push({
                            id: Date.now().toString() + Math.random(),
                            systemName,
                            systemFile,
                            minSize
                        })
                    })
                }
                setSystemMaps(systemMapsData.length > 0 ? systemMapsData : [{
                    id: Date.now().toString(),
                    systemName: '',
                    systemFile: '',
                    minSize: ''
                }])

                // 加载镜像映射
                const imageMapsData: ImageMapRow[] = []
                if (config.images_maps) {
                    Object.entries(config.images_maps).forEach(([displayName, fileName]) => {
                        imageMapsData.push({
                            id: Date.now().toString() + Math.random(),
                            displayName,
                            fileName: fileName as string
                        })
                    })
                }
                setImageMaps(imageMapsData.length > 0 ? imageMapsData : [{
                    id: Date.now().toString(),
                    displayName: '',
                    fileName: ''
                }])

                // 加载IP地址池配置
                const ipaddrMapsData: IpaddrMapRow[] = []
                if (config.ipaddr_maps) {
                    Object.entries(config.ipaddr_maps).forEach(([setName, ipConfig]: [string, any]) => {
                        ipaddrMapsData.push({
                            id: Date.now().toString() + Math.random(),
                            setName,
                            vers: ipConfig.vers || 'ipv4',
                            type: ipConfig.type || 'nat',
                            gate: ipConfig.gate || '',
                            mask: ipConfig.mask || '',
                            fromIp: ipConfig.from || '',
                            nums: ipConfig.nums || 0
                        })
                    })
                }
                setIpaddrMaps(ipaddrMapsData.length > 0 ? ipaddrMapsData : [{
                    id: Date.now().toString(),
                    setName: '',
                    vers: 'ipv4',
                    type: 'nat',
                    gate: '',
                    mask: '',
                    fromIp: '',
                    nums: 0
                }])

                setModalVisible(true)
            }
        } catch (error) {
            message.error('加载主机信息失败')
        }
    }

    // 提交表单
    const handleSubmit = async (values: any) => {
        try {
            // 构建系统映射
            const system_maps: Record<string, [string, string]> = {}
            systemMaps.forEach(row => {
                if (row.systemName && row.systemFile) {
                    system_maps[row.systemName] = [row.systemFile, row.minSize || '0']
                }
            })

            // 构建镜像映射
            const images_maps: Record<string, string> = {}
            imageMaps.forEach(row => {
                if (row.displayName && row.fileName) {
                    images_maps[row.displayName] = row.fileName
                }
            })

            // 构建IP地址池配置
            const ipaddr_maps: Record<string, any> = {}
            ipaddrMaps.forEach(row => {
                if (row.setName && row.fromIp && row.nums > 0) {
                    ipaddr_maps[row.setName] = {
                        vers: row.vers,
                        type: row.type,
                        gate: row.gate,
                        mask: row.mask,
                        from: row.fromIp,
                        nums: row.nums
                    }
                }
            })

            // 解析扩展数据
            let extend_data = {}
            if (values.extend_data) {
                try {
                    extend_data = JSON.parse(values.extend_data)
                } catch (e) {
                    message.error('扩展数据JSON格式错误')
                    return
                }
            }

            const config: HostConfig = {
                server_type: values.type,
                server_addr: values.server_addr,
                server_user: values.server_user,
                server_pass: values.server_pass,
                filter_name: values.filter_name,
                images_path: values.images_path,
                dvdrom_path: values.dvdrom_path,
                system_path: values.system_path,
                backup_path: values.backup_path,
                extern_path: values.extern_path,
                launch_path: values.launch_path,
                server_port: values.server_port,
                network_nat: values.network_nat,
                network_pub: values.network_pub,
                i_kuai_addr: values.i_kuai_addr,
                i_kuai_user: values.i_kuai_user,
                i_kuai_pass: values.i_kuai_pass,
                ports_start: values.ports_start,
                ports_close: values.ports_close,
                remote_port: values.remote_port,
                limits_nums: values.limits_nums,
                system_maps,
                images_maps,
                ipaddr_maps,
                ipaddr_dnss: values.ipaddr_dnss ? values.ipaddr_dnss.split(',').map((s: string) => s.trim()).filter((s: string) => s) : [],
                public_addr: values.public_addr ? values.public_addr.split(',').map((s: string) => s.trim()).filter((s: string) => s) : [],
                extend_data
            }

            if (editMode === 'add') {
                await api.createServer(values.name, values.type, config)
                message.success('主机添加成功')
            } else {
                await api.updateServer(currentHost, config)
                message.success('主机更新成功')
            }

            setModalVisible(false)
            loadHosts()
        } catch (error: any) {
            message.error(error.message || '操作失败')
        }
    }

    // 删除主机
    const handleDelete = async (name: string) => {
        try {
            await api.deleteServer(name)
            message.success('主机删除成功')
            loadHosts()
        } catch (error) {
            message.error('删除主机失败')
        }
    }

    // 切换主机状态（启用/禁用）
    const handleToggle = async (name: string, enable: boolean) => {
        // 如果是禁用操作，弹出确认对话框
        if (!enable) {
            Modal.confirm({
                title: '确认禁用主机',
                icon: <ExclamationCircleOutlined style={{color: '#faad14'}}/>,
                content: (
                    <div>
                        <p>确定要禁用主机 <strong>"{name}"</strong> 吗？</p>
                        <p style={{color: '#ff4d4f', marginTop: 8}}>
                            禁用后：
                        </p>
                        <ul style={{marginTop: 4, paddingLeft: 20}}>
                            <li>该主机的虚拟机操作将不可用</li>
                            <li>系统将不再自动更新该主机状态</li>
                            <li>运行中的虚拟机不会被关闭</li>
                        </ul>
                    </div>
                ),
                okText: '确认禁用',
                okType: 'danger',
                cancelText: '取消',
                mask: false,
                onOk: async () => {
                    try {
                        await api.toggleServerPower(name, enable)
                        message.success('主机已禁用')
                        loadHosts()
                    } catch (error) {
                        message.error('禁用失败')
                    }
                }
            })
        } else {
            // 启用操作直接执行
            try {
                await api.toggleServerPower(name, enable)
                message.success('主机已启用')
                loadHosts()
            } catch (error) {
                message.error('启用失败')
            }
        }
    }

    // 扫描虚拟机
    const handleScanVMs = async (name: string) => {
        try {
            const result = await api.scanVMs(name)
            if (result.code === 200) {
                const data = result.data || {}
                message.success(`扫描完成：扫描到 ${data.scanned || 0} 台虚拟机，新增 ${data.added || 0} 台`)
                loadHosts()
            } else {
                message.error(result.msg || '扫描失败')
            }
        } catch (error) {
            message.error('扫描失败')
        }
    }

    // 扫描备份
    const handleScanBackups = async (name: string) => {
        try {
            await api.scanBackups(name)
            message.success('备份扫描成功')
            loadHosts()
        } catch (error) {
            message.error('扫描失败')
        }
    }

    // 格式化字节大小（已注释，暂未使用）
    // const formatBytes = (bytes: number, decimals = 2) => {
    //     if (bytes === 0) return '0 B'
    //     const k = 1024
    //     const dm = decimals < 0 ? 0 : decimals
    //     const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
    //     const i = Math.floor(Math.log(bytes) / Math.log(k))
    //     return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i]
    // }

    // 获取进度条颜色
    const getProgressColor = (percent: number) => {
        if (percent >= 90) return '#ef4444'
        if (percent >= 75) return '#f97316'
        if (percent >= 50) return '#eab308'
        return '#22c55e'
    }

    // 渲染主机卡片
    const renderHostCard = (name: string, host: Host) => {
        const status = hostsStatus[name]
        const typeInfo = engineTypes[host.type] || {}

        // 计算资源使用率
        const cpuPercent = status ? Math.min(status.cpu_usage || 0, 100) : 0
        const memPercent = status && status.mem_total ? Math.min((status.mem_usage || 0) / status.mem_total * 100, 100) : 0
        const memUsageGB = status ? ((status.mem_usage || 0) / 1024).toFixed(1) : '0.0'
        const memTotalGB = status ? ((status.mem_total || 0) / 1024).toFixed(1) : '0.0'

        // 获取第一个磁盘
        let diskPercent = 0
        let diskUsageGB = 0
        let diskTotalGB = 0
        // let diskName = '系统盘'  // 暂未使用
        if (status?.ext_usage) {
            const disks = Object.entries(status.ext_usage)
            if (disks.length > 0) {
                const [_name, [total, used]] = disks[0]
                // diskName = _name
                diskTotalGB = (total / 1024)
                diskUsageGB = (used / 1024)
                diskPercent = total > 0 ? Math.min((used / total * 100), 100) : 0
            }
        }

        // 网络带宽
        const networkA = status?.network_a || 1000 // Mbps
        const maxBandwidth = networkA * 1024 / 8 // KB/s
        const networkU = status?.network_u || 0 // KB/s
        const networkD = status?.network_d || 0 // KB/s
        const networkUPercent = Math.min((networkU / maxBandwidth * 100), 100)
        const networkDPercent = Math.min((networkD / maxBandwidth * 100), 100)

        // GPU使用率
        let gpuPercent = 0
        if (status?.gpu_usage) {
            const gpuKeys = Object.keys(status.gpu_usage)
            if (gpuKeys.length > 0) {
                gpuPercent = Math.min(status.gpu_usage[gpuKeys[0]] || 0, 100)
            }
        }

        // CPU温度和功耗
        // const cpuTemp = status?.cpu_heats || 0  // 暂未使用
        // const cpuPower = status?.cpu_power || 0  // 暂未使用
        // const cpuTempPercent = Math.min((cpuTemp / 100 * 100), 100)  // 暂未使用

        return (
            <Card
                key={name}
                className="glass-card mb-4 hover:shadow-lg transition-shadow"
                title={
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <div
                                className="w-12 h-12 bg-gradient-to-br from-blue-500 to-blue-600 rounded-lg flex items-center justify-center">
                                <CloudServerOutlined className="text-white text-2xl"/>
                            </div>
                            <div>
                                <div className="font-semibold text-gray-800 dark:text-gray-100">{name}</div>
                                <div className="text-sm text-gray-500 dark:text-gray-400">{typeInfo.description || host.type}</div>
                            </div>
                        </div>
                        <Tag color={host.status === 'active' ? 'success' : 'error'}>
                            {host.status === 'active' ? '已启用' : '已禁用'}
                        </Tag>
                    </div>
                }
                extra={
                    <Space>
                        <Button
                            type="link"
                            onClick={() => navigate(`/hosts/${name}/vms`)}
                            title="虚拟机管理"
                            disabled={host.status !== 'active'}
                        >
                            管理
                        </Button>
                        <Button
                            type="text"
                            icon={<CloudSyncOutlined/>}
                            onClick={() => handleScanBackups(name)}
                            title="扫描备份"
                            disabled={host.status !== 'active'}
                        />
                        <Button
                            type="text"
                            icon={<ScanOutlined/>}
                            onClick={() => handleScanVMs(name)}
                            title="扫描虚拟机"
                            disabled={host.status !== 'active'}
                        />
                        <Button
                            type={host.status === 'active' ? 'default' : 'primary'}
                            danger={host.status === 'active'}
                            icon={host.status === 'active' ? <StopOutlined/> : <PlayCircleOutlined/>}
                            onClick={() => handleToggle(name, host.status !== 'active')}
                        >
                            {host.status === 'active' ? '禁用' : '启用'}
                        </Button>
                        <Button
                            type="text"
                            icon={<EditOutlined/>}
                            onClick={() => handleEdit(name)}
                            title="编辑"
                            disabled={host.status !== 'active'}
                        />
                        <Button
                            type="text"
                            danger
                            icon={<DeleteOutlined/>}
                            title="删除"
                            disabled={host.status !== 'active'}
                            onClick={() => {
                                Modal.confirm({
                                    title: '确认删除',
                                    icon: <DeleteOutlined style={{color: 'red'}}/>,
                                    content: `确定要删除主机 "${name}" 吗？此操作不可恢复。`,
                                    okText: '确认删除',
                                    okType: 'danger',
                                    cancelText: '取消',
                                    mask: false,
                                    onOk: () => handleDelete(name)
                                })
                            }}
                        />
                    </Space>
                }
            >
                <Row gutter={16} style={{display: 'flex', flexWrap: 'nowrap'}}>
                    {/* 左侧：基本信息 */}
                    <Col span={8} style={{minWidth: '240px', flexShrink: 0, flexGrow: 0}}>
                        <div className="space-y-1 text-xs">
                            <div className="flex justify-between items-center">
                                <span className="text-gray-600 dark:text-gray-400">主机连接IP:</span>
                                <span className="truncate dark:text-gray-200">{host.addr || '未配置'}</span>
                            </div>
                            <div className="flex justify-between items-start">
                                <span className="text-gray-600 dark:text-gray-400">公共公共IP:</span>
                                <div className="text-right max-w-[60%]">
                                    {host.config?.public_addr && host.config.public_addr.length > 0 ? (
                                        host.config.public_addr.map((ip, idx) => (
                                            <div key={idx} className="flex items-center justify-end gap-1 mb-1">
                                                <span className="truncate dark:text-gray-200">{ip}</span>
                                                <Tooltip title="复制">
                                                    <CopyOutlined
                                                        className="text-gray-400 hover:text-blue-600 cursor-pointer text-xs"
                                                        onClick={() => copyToClipboard(ip)}/>
                                                </Tooltip>
                                            </div>
                                        ))
                                    ) : (
                                        <span>未配置</span>
                                    )}
                                </div>
                            </div>
                            <div className="flex justify-between items-center">
                                <span className="text-gray-600 dark:text-gray-400">访问端口:</span>
                                <span className="dark:text-gray-200">{host.config?.server_port && host.config.server_port > 0 ? host.config.server_port : '未配置'}</span>
                            </div>
                            <div className="flex justify-between items-center">
                                <span className="text-gray-600 dark:text-gray-400">桌面端口:</span>
                                <span className="dark:text-gray-200">{host.config?.remote_port || '未配置'}</span>
                            </div>
                            <div className="flex justify-between items-center">
                                <span className="text-gray-600 dark:text-gray-400">虚拟机前缀:</span>
                                <span className="truncate dark:text-gray-200">{host.config?.filter_name || '未配置'}</span>
                            </div>
                            <div className="flex justify-between items-center">
                                <span className="text-gray-600 dark:text-gray-400">虚拟机数量:</span>
                                <span className="dark:text-gray-200"
                                >{host.vm_count || 0} / {host.config?.limits_nums || 0} 台</span>
                            </div>
                            <div className="flex justify-between items-center">
                                <span className="text-gray-600 dark:text-gray-400">内网网桥:</span>
                                <span className="dark:text-gray-200">{host.config?.network_nat || '未配置'}</span>
                            </div>
                            <div className="flex justify-between items-center">
                                <span className="text-gray-600 dark:text-gray-400">公网网桥:</span>
                                <span className="dark:text-gray-200">{host.config?.network_pub || '未配置'}</span>
                            </div>
                            <div className="flex justify-between items-center">
                                <span className="text-gray-600 dark:text-gray-400">端口范围:</span>
                                <span className="dark:text-gray-200"
                                >{host.config?.ports_start && host.config?.ports_close ? `${host.config.ports_start}-${host.config.ports_close}` : '未配置'}</span>
                            </div>
                            <div className="flex justify-between items-center">
                                <span className="text-gray-600 dark:text-gray-400">爱快地址:</span>
                                <span className="truncate dark:text-gray-200">{host.config?.i_kuai_addr || '未配置'}</span>
                            </div>
                            <div className="flex justify-between items-center">
                                <span className="text-gray-600 dark:text-gray-400">模板数:</span>
                                <span className="dark:text-gray-200"
                                >系统盘 {host.config?.system_maps && Object.keys(host.config.system_maps).length > 0 ? Object.keys(host.config.system_maps).length : 0} / 光盘 {host.config?.images_maps && Object.keys(host.config.images_maps).length > 0 ? Object.keys(host.config.images_maps).length : 0} 个</span>
                            </div>
                            {/*<div className="flex justify-between items-start">*/}
                            {/*    <span className="text-gray-600 dark:text-gray-400">DNS:</span>*/}
                            {/*    <div className="text-right max-w-[80%]">*/}
                            {/*        <span className="dark:text-gray-200"*/}
                            {/*        >{host.config?.ipaddr_dnss && host.config.ipaddr_dnss.length > 0 ? host.config.ipaddr_dnss.join(',') : '未配置'}</span>*/}
                            {/*    </div>*/}
                            {/*</div>*/}
                            {/*<div>*/}
                            {/*    {host.config?.ipaddr_maps && Object.keys(host.config.ipaddr_maps).length > 0 ? (*/}
                            {/*        Object.entries(host.config.ipaddr_maps).slice(0, 1).map(([name, config]: [string, any]) => (*/}
                            {/*            <div key={name} className="space-y-0.5">*/}
                            {/*                /!* 第一行：起始IP + 最大分配数量 *!/*/}
                            {/*                <div className="flex justify-between">*/}
                            {/*                    <div className="flex items-center space-x-2">*/}
                            {/*                        <span className="text-gray-500 text-xs">IP</span>*/}
                            {/*                        <span className="truncate text-xs dark:text-gray-200">{config.from}</span>*/}
                            {/*                    </div>*/}
                            {/*                    <div className="flex items-center space-x-2">*/}
                            {/*                        <span className="text-gray-500 text-xs">分配</span>*/}
                            {/*                        <span className="text-xs dark:text-gray-200">{config.nums} 个</span>*/}
                            {/*                    </div>*/}
                            {/*                </div>*/}
                            {/*                /!* 第二行：网关 + 掩码 *!/*/}
                            {/*                <div className="flex justify-between">*/}
                            {/*                    <div className="flex items-center space-x-2">*/}
                            {/*                        <span className="text-gray-500 text-xs">IP</span>*/}
                            {/*                        <span className="truncate text-xs dark:text-gray-200">{config.gate}</span>*/}
                            {/*                    </div>*/}
                            {/*                    <div className="flex items-center space-x-2">*/}
                            {/*                        <span className="text-gray-500 text-xs">/</span>*/}
                            {/*                        <span className="text-xs dark:text-gray-200">{config.mask}</span>*/}
                            {/*                    </div>*/}
                            {/*                </div>*/}
                            {/*            </div>*/}
                            {/*        ))*/}
                            {/*    ) : (*/}
                            {/*        <div className="ml-2 text-xs text-gray-500 ">未配置</div>*/}
                            {/*    )}*/}
                            {/*</div>*/}

                        </div>
                    </Col>

                    {/* 右侧：资源状态 */}
                    <Col span={16} style={{overflow: 'hidden', flexGrow: 1, flexShrink: 1, minWidth: 0}}>
                        {status ? (
                            <div className="space-y-5" style={{width: '100%'}}>
                                {/* CPU */}
                                <div style={{minWidth: 0}}>
                                    <div className="flex justify-between text-xs mb-1">
                                        <span className="text-gray-600 truncate"
                                              title={status.cpu_model || '核心使用率'}>{status.cpu_model || '核心使用率'}</span>
                                        <span
                                            className="font-bold whitespace-nowrap">{status.cpu_total || 0}核 {cpuPercent.toFixed(1)}%</span>
                                    </div>
                                    <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
                                        <div className="h-2 transition-all"
                                             style={{width: `${cpuPercent}%`, backgroundColor: getProgressColor(cpuPercent)}}></div>
                                    </div>
                                </div>

                                {/* 内存 */}
                                <div style={{minWidth: 0}}>
                                    <div className="flex justify-between text-xs mb-1">
                                        <span className="text-gray-600 truncate">内存使用率</span>
                                        <span
                                            className="font-bold whitespace-nowrap">{memUsageGB}GB/{memTotalGB}GB {memPercent.toFixed(1)}%</span>
                                    </div>
                                    <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
                                        <div className="h-2 transition-all"
                                             style={{width: `${memPercent}%`, backgroundColor: getProgressColor(memPercent)}}></div>
                                    </div>
                                </div>

                                {/* 磁盘 */}
                                <div style={{minWidth: 0}}>
                                    <div className="flex justify-between text-xs mb-1">
                                        <span className="text-gray-600 truncate">硬盘使用率</span>
                                        <span
                                            className="font-bold whitespace-nowrap">{diskUsageGB.toFixed(1)}GB/{diskTotalGB.toFixed(1)}GB {diskPercent.toFixed(1)}%</span>
                                    </div>
                                    <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
                                        <div className="h-2 transition-all"
                                             style={{width: `${diskPercent}%`, backgroundColor: getProgressColor(diskPercent)}}></div>
                                    </div>
                                </div>

                                {/* 网络 */}
                                <div style={{minWidth: 0}}>
                                    <div className="flex justify-between text-xs mb-1">
                                        <span className="text-gray-600 truncate">网络使用率</span>
                                        <span className="font-bold whitespace-nowrap">↑{(networkU / 1024).toFixed(1)}MB/s ↓{(networkD / 1024).toFixed(1)}MB/s</span>
                                    </div>
                                    <div className="w-full bg-gray-200 rounded-full h-2 flex gap-0.5 overflow-hidden">
                                        <div className="bg-blue-500 h-2 transition-all"
                                             style={{width: `${networkUPercent / 2}%`}}></div>
                                        <div className="bg-green-500 h-2 transition-all"
                                             style={{width: `${networkDPercent / 2}%`}}></div>
                                    </div>
                                </div>

                                {/* GPU */}
                                <div style={{minWidth: 0}}>
                                    <div className="flex justify-between text-xs mb-1">
                                        <span className="text-gray-600 truncate">显卡使用率</span>
                                        <span
                                            className="font-bold whitespace-nowrap">{status.gpu_total || 0}个 {gpuPercent.toFixed(1)}%</span>
                                    </div>
                                    <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
                                        <div className="h-2 transition-all"
                                             style={{width: `${gpuPercent}%`, backgroundColor: getProgressColor(gpuPercent)}}></div>
                                    </div>
                                </div>

                                {/* 温度/功耗 */}
                                {/*<div style={{ width: '100%' }}>*/}
                                {/*    <div className="flex justify-between text-xs mb-1">*/}
                                {/*        <span className="text-gray-600 truncate">温度/功耗</span>*/}
                                {/*        <span className="font-bold whitespace-nowrap">{cpuTemp}℃ {cpuPower}W</span>*/}
                                {/*    </div>*/}
                                {/*    <div style={{ width: '100%' }}>*/}
                                {/*        <Progress percent={cpuTempPercent} strokeColor={getProgressColor(cpuTempPercent)} showInfo={false} size="small" style={{ width: '100%' }}/>*/}
                                {/*    </div>*/}
                                {/*</div>*/}
                            </div>
                        ) : (
                            <div className="text-center text-gray-400 py-8 text-xs">暂无状态数据</div>
                        )}
                    </Col>
                </Row>
            </Card>
        )
    }

    return (
        <div className="p-6">
            {/* 页面标题 */}
            <div className="mb-6">
                <h1 className="text-3xl font-bold text-gray-800 dark:text-gray-100 flex items-center gap-3">
                    <CloudServerOutlined className="text-blue-600"/>
                    物理主机管理
                </h1>
                <p className="text-gray-600 dark:text-gray-400 mt-1">管理所有虚拟化主机</p>
            </div>

            {/* 操作栏 */}
            <div className="glass-card p-4 mb-6 flex items-center justify-between">
                <Space>
                    <Button type="primary" icon={<PlusOutlined/>} onClick={handleAdd}>
                        添加主机
                    </Button>
                    <Button icon={<ReloadOutlined/>} onClick={loadHosts}>
                        刷新
                    </Button>
                </Space>
                <div className="text-sm text-gray-600 dark:text-gray-300 flex items-center gap-2">
                    <InfoCircleOutlined/>
                    共 <span className="font-medium text-gray-800 dark:text-gray-100">{Object.keys(hosts).length}</span> 个主机
                </div>
            </div>

            {/* 主机列表 */}
            {loading ? (
                <div className="text-center py-16">
                    <div className="text-gray-400 text-4xl mb-4">⏳</div>
                    <p className="text-gray-500">加载中...</p>
                </div>
            ) : Object.keys(hosts).length === 0 ? (
                <div className="text-center py-16">
                    <div className="text-gray-300 text-6xl mb-4">📦</div>
                    <p className="text-gray-500 mb-4">暂无主机</p>
                    <Button type="primary" onClick={handleAdd}>添加第一个主机</Button>
                </div>
            ) : (
                <div className="grid grid-cols-[repeat(auto-fill,minmax(800px,1fr))] gap-4">
                    {Object.entries(hosts).map(([name, host]) => (
                        <div key={name}>
                            {renderHostCard(name, host)}
                        </div>
                    ))}
                </div>
            )}

            {/* 添加/编辑主机对话框 */}
            <Modal
                title={editMode === 'add' ? '添加主机' : '编辑主机'}
                open={modalVisible}
                onCancel={() => setModalVisible(false)}
                onOk={() => form.submit()}
                width={900}
                okText="保存"
                cancelText="取消"
            >
                <Form form={form} layout="vertical" onFinish={handleSubmit}>
                    <Tabs
                        items={[
                            {
                                key: 'basic',
                                label: <span><SettingOutlined/> 基本配置</span>,
                                children: (
                                    <div className="max-h-[500px] overflow-y-auto pr-2">
                                        <Row gutter={16}>
                                            <Col span={12}>
                                                <Form.Item name="name" label="服务器名称"
                                                           rules={[{required: true, message: '请输入服务器名称'}]}>
                                                    <Input placeholder="例如: host1" disabled={editMode === 'edit'}/>
                                                </Form.Item>
                                            </Col>
                                            <Col span={12}>
                                                <Form.Item name="type" label="服务器类型"
                                                           rules={[{required: true, message: '请选择服务器类型'}]}>
                                                    <Select
                                                        placeholder="请选择类型"
                                                        onChange={(value) => setSelectedHostType(value)}
                                                    >
                                                        {Object.entries(engineTypes).map(([type, config]) =>
                                                            config.enabled ? (
                                                                <Select.Option key={type} value={type}>
                                                                    {config.description} ({type})
                                                                </Select.Option>
                                                            ) : null
                                                        )}
                                                    </Select>
                                                </Form.Item>
                                            </Col>
                                        </Row>

                                        {/* 主机类型信息提示 */}
                                        {selectedHostType && engineTypes[selectedHostType] && (
                                            <div className="mb-4">
                                                {engineTypes[selectedHostType].messages && engineTypes[selectedHostType].messages!.length > 0 && (
                                                    <div
                                                        className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 mb-3">
                                                        <h5 className="text-sm font-medium text-yellow-800 mb-2">注意事项</h5>
                                                        <ul className="text-sm text-yellow-700 space-y-1 list-disc list-inside">
                                                            {engineTypes[selectedHostType].messages!.map((msg, idx) => (
                                                                <li key={idx}>{msg}</li>
                                                            ))}
                                                        </ul>
                                                    </div>
                                                )}
                                                {engineTypes[selectedHostType].options && Object.keys(engineTypes[selectedHostType].options!).length > 0 && (
                                                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                                                        <h5 className="text-sm font-medium text-blue-800 mb-2">可选配置项</h5>
                                                        <div className="text-sm text-blue-700 space-y-1">
                                                            {Object.entries(engineTypes[selectedHostType].options!).map(([key, desc]) => (
                                                                <div key={key}>
                                                                    <strong>{key}:</strong> {desc}
                                                                </div>
                                                            ))}
                                                        </div>
                                                    </div>
                                                )}
                                            </div>
                                        )}

                                        <Row gutter={16}>
                                            <Col span={12}>
                                                <Form.Item name="server_addr" label="服务器地址">
                                                    <Input placeholder="例如: localhost:8697"/>
                                                </Form.Item>
                                            </Col>
                                            <Col span={12}>
                                                <Form.Item name="server_user" label="服务器用户">
                                                    <Input placeholder="例如: root"/>
                                                </Form.Item>
                                            </Col>
                                        </Row>

                                        <Row gutter={16}>
                                            <Col span={12}>
                                                <Form.Item name="server_pass" label="服务器密码">
                                                    <Input.Password placeholder="服务器密码"/>
                                                </Form.Item>
                                            </Col>
                                            <Col span={12}>
                                                <Form.Item name="filter_name" label="虚拟机前缀">
                                                    <Input placeholder="过滤器名称"/>
                                                </Form.Item>
                                            </Col>
                                        </Row>

                                        <Row gutter={16}>
                                            <Col span={12}>
                                                <Form.Item name="server_port" label="服务访问端口">
                                                    <InputNumber placeholder="例如: 443" min={0} max={65535}
                                                                 className="w-full"/>
                                                </Form.Item>
                                            </Col>
                                            <Col span={12}>
                                                <Form.Item name="public_addr" label="服务器公网IP">
                                                    <Input placeholder="例如: 192.168.1.1, 2001:db8::1"/>
                                                </Form.Item>
                                            </Col>
                                        </Row>

                                        <Row gutter={16}>
                                            <Col span={12}>
                                                <Form.Item name="network_nat" label="共享IP设备名">
                                                    <Input placeholder="例如: nat"/>
                                                </Form.Item>
                                            </Col>
                                            <Col span={12}>
                                                <Form.Item name="network_pub" label="独立IP设备名">
                                                    <Input placeholder="例如: pub"/>
                                                </Form.Item>
                                            </Col>
                                        </Row>
                                    </div>
                                )
                            },
                            {
                                key: 'storage',
                                label: <span><FolderOutlined/> 存储路径</span>,
                                children: (
                                    <div className="max-h-[500px] overflow-y-auto pr-2">
                                        <Row gutter={16}>
                                            <Col span={12}>
                                                <Form.Item name="images_path" label="模板存储路径">
                                                    <Input placeholder="例如: /data/images"/>
                                                </Form.Item>
                                            </Col>
                                            <Col span={12}>
                                                <Form.Item name="dvdrom_path" label="光盘存储路径">
                                                    <Input placeholder="例如: /data/iso"/>
                                                </Form.Item>
                                            </Col>
                                        </Row>

                                        <Row gutter={16}>
                                            <Col span={12}>
                                                <Form.Item name="system_path" label="系统存储路径">
                                                    <Input placeholder="例如: /data/system"/>
                                                </Form.Item>
                                            </Col>
                                            <Col span={12}>
                                                <Form.Item name="backup_path" label="备份存储路径">
                                                    <Input placeholder="例如: /data/backup"/>
                                                </Form.Item>
                                            </Col>
                                        </Row>

                                        <Row gutter={16}>
                                            <Col span={12}>
                                                <Form.Item name="extern_path" label="数据存储路径">
                                                    <Input placeholder="例如: /data/extern"/>
                                                </Form.Item>
                                            </Col>
                                            <Col span={12}>
                                                <Form.Item name="launch_path" label="程序启动路径">
                                                    <Input placeholder="虚拟化程序路径"/>
                                                </Form.Item>
                                            </Col>
                                        </Row>
                                    </div>
                                )
                            },
                            {
                                key: 'network',
                                label: <span><GlobalOutlined/> 网络配置</span>,
                                children: (
                                    <div className="max-h-[500px] overflow-y-auto pr-2">
                                        <h4 className="font-medium mb-3">爱快OS配置</h4>
                                        <Row gutter={16}>
                                            <Col span={8}>
                                                <Form.Item name="i_kuai_addr" label="爱快OS地址">
                                                    <Input placeholder="例如: http://192.168.1.1"/>
                                                </Form.Item>
                                            </Col>
                                            <Col span={8}>
                                                <Form.Item name="i_kuai_user" label="爱快OS用户名">
                                                    <Input placeholder="爱快OS管理员用户名"/>
                                                </Form.Item>
                                            </Col>
                                            <Col span={8}>
                                                <Form.Item name="i_kuai_pass" label="爱快OS密码">
                                                    <Input.Password placeholder="爱快OS管理员密码"/>
                                                </Form.Item>
                                            </Col>
                                        </Row>

                                        <h4 className="font-medium mb-3 mt-4">端口配置</h4>
                                        <Row gutter={16}>
                                            <Col span={6}>
                                                <Form.Item name="ports_start" label="TCP端口起始">
                                                    <InputNumber placeholder="例如: 10000" min={0} max={65535}
                                                                 className="w-full"/>
                                                </Form.Item>
                                            </Col>
                                            <Col span={6}>
                                                <Form.Item name="ports_close" label="TCP端口结束">
                                                    <InputNumber placeholder="例如: 20000" min={0} max={65535}
                                                                 className="w-full"/>
                                                </Form.Item>
                                            </Col>
                                            <Col span={6}>
                                                <Form.Item name="remote_port" label="VNC服务端口">
                                                    <InputNumber placeholder="例如: 5900" min={0} max={65535}
                                                                 className="w-full"/>
                                                </Form.Item>
                                            </Col>
                                            <Col span={6}>
                                                <Form.Item name="limits_nums" label="虚拟机数量限制">
                                                    <InputNumber placeholder="例如: 100" min={0} className="w-full"/>
                                                </Form.Item>
                                            </Col>
                                        </Row>

                                        <h4 className="font-medium mb-3 mt-4">DNS服务器配置</h4>
                                        <Form.Item name="ipaddr_dnss" label="DNS服务器（多个用逗号分隔）">
                                            <Input placeholder="例如: 8.8.8.8, 8.8.4.4"/>
                                        </Form.Item>
                                    </div>
                                )
                            },
                            {
                                key: 'advanced',
                                label: <span><DatabaseOutlined/> 高级配置</span>,
                                children: (
                                    <div className="max-h-[500px] overflow-y-auto pr-2">
                                        <h4 className="font-medium mb-3">系统映射配置</h4>
                                        <div className="space-y-2 mb-4">
                                            {systemMaps.map((row, index) => (
                                                <div key={row.id} className="bg-gray-50 p-3 rounded-lg">
                                                    <Row gutter={8}>
                                                        <Col span={8}>
                                                            <Input
                                                                placeholder="系统名称"
                                                                value={row.systemName}
                                                                onChange={(e) => {
                                                                    const newMaps = [...systemMaps]
                                                                    newMaps[index].systemName = e.target.value
                                                                    setSystemMaps(newMaps)
                                                                }}
                                                            />
                                                        </Col>
                                                        <Col span={8}>
                                                            <Input
                                                                placeholder="镜像文件"
                                                                value={row.systemFile}
                                                                onChange={(e) => {
                                                                    const newMaps = [...systemMaps]
                                                                    newMaps[index].systemFile = e.target.value
                                                                    setSystemMaps(newMaps)
                                                                }}
                                                            />
                                                        </Col>
                                                        <Col span={6}>
                                                            <Input
                                                                placeholder="最低大小(GB)"
                                                                value={row.minSize}
                                                                onChange={(e) => {
                                                                    const newMaps = [...systemMaps]
                                                                    newMaps[index].minSize = e.target.value
                                                                    setSystemMaps(newMaps)
                                                                }}
                                                            />
                                                        </Col>
                                                        <Col span={2}>
                                                            <Button
                                                                danger
                                                                icon={<DeleteOutlined/>}
                                                                onClick={() => setSystemMaps(systemMaps.filter(m => m.id !== row.id))}
                                                            />
                                                        </Col>
                                                    </Row>
                                                </div>
                                            ))}
                                            <Button
                                                type="dashed"
                                                icon={<PlusOutlined/>}
                                                onClick={() => setSystemMaps([...systemMaps, {
                                                    id: Date.now().toString(),
                                                    systemName: '',
                                                    systemFile: '',
                                                    minSize: ''
                                                }])}
                                                block
                                            >
                                                添加系统映射
                                            </Button>
                                        </div>

                                        <h4 className="font-medium mb-3 mt-4">ISO镜像映射配置</h4>
                                        <div className="space-y-2 mb-4">
                                            {imageMaps.map((row, index) => (
                                                <div key={row.id} className="bg-gray-50 p-3 rounded-lg">
                                                    <Row gutter={8}>
                                                        <Col span={11}>
                                                            <Input
                                                                placeholder="显示名称"
                                                                value={row.displayName}
                                                                onChange={(e) => {
                                                                    const newMaps = [...imageMaps]
                                                                    newMaps[index].displayName = e.target.value
                                                                    setImageMaps(newMaps)
                                                                }}
                                                            />
                                                        </Col>
                                                        <Col span={11}>
                                                            <Input
                                                                placeholder="ISO文件名"
                                                                value={row.fileName}
                                                                onChange={(e) => {
                                                                    const newMaps = [...imageMaps]
                                                                    newMaps[index].fileName = e.target.value
                                                                    setImageMaps(newMaps)
                                                                }}
                                                            />
                                                        </Col>
                                                        <Col span={2}>
                                                            <Button
                                                                danger
                                                                icon={<DeleteOutlined/>}
                                                                onClick={() => setImageMaps(imageMaps.filter(m => m.id !== row.id))}
                                                            />
                                                        </Col>
                                                    </Row>
                                                </div>
                                            ))}
                                            <Button
                                                type="dashed"
                                                icon={<PlusOutlined/>}
                                                onClick={() => setImageMaps([...imageMaps, {
                                                    id: Date.now().toString(),
                                                    displayName: '',
                                                    fileName: ''
                                                }])}
                                                block
                                            >
                                                添加镜像映射
                                            </Button>
                                        </div>

                                        <h4 className="font-medium mb-3 mt-4">IP地址池配置</h4>
                                        <div className="space-y-2 mb-4">
                                            {ipaddrMaps.map((row, index) => (
                                                <div key={row.id} className="bg-gray-50 p-3 rounded-lg">
                                                    <Row gutter={8} className="mb-2">
                                                        <Col span={6}>
                                                            <Input
                                                                placeholder="配置名称"
                                                                value={row.setName}
                                                                onChange={(e) => {
                                                                    const newMaps = [...ipaddrMaps]
                                                                    newMaps[index].setName = e.target.value
                                                                    setIpaddrMaps(newMaps)
                                                                }}
                                                            />
                                                        </Col>
                                                        <Col span={4}>
                                                            <Select
                                                                value={row.vers}
                                                                onChange={(value) => {
                                                                    const newMaps = [...ipaddrMaps]
                                                                    newMaps[index].vers = value
                                                                    setIpaddrMaps(newMaps)
                                                                }}
                                                                className="w-full"
                                                            >
                                                                <Select.Option value="ipv4">IPv4</Select.Option>
                                                                <Select.Option value="ipv6">IPv6</Select.Option>
                                                            </Select>
                                                        </Col>
                                                        <Col span={4}>
                                                            <Select
                                                                value={row.type}
                                                                onChange={(value) => {
                                                                    const newMaps = [...ipaddrMaps]
                                                                    newMaps[index].type = value
                                                                    setIpaddrMaps(newMaps)
                                                                }}
                                                                className="w-full"
                                                            >
                                                                <Select.Option value="nat">NAT</Select.Option>
                                                                <Select.Option value="pub">PUB</Select.Option>
                                                            </Select>
                                                        </Col>
                                                        <Col span={8}>
                                                            <InputNumber
                                                                placeholder="数量"
                                                                value={row.nums}
                                                                onChange={(value) => {
                                                                    const newMaps = [...ipaddrMaps]
                                                                    newMaps[index].nums = value || 0
                                                                    setIpaddrMaps(newMaps)
                                                                }}
                                                                min={1}
                                                                className="w-full"
                                                            />
                                                        </Col>
                                                        <Col span={2}>
                                                            <Button
                                                                danger
                                                                icon={<DeleteOutlined/>}
                                                                onClick={() => setIpaddrMaps(ipaddrMaps.filter(m => m.id !== row.id))}
                                                            />
                                                        </Col>
                                                    </Row>
                                                    <Row gutter={8}>
                                                        <Col span={8}>
                                                            <Input
                                                                placeholder="起始IP地址"
                                                                value={row.fromIp}
                                                                onChange={(e) => {
                                                                    const newMaps = [...ipaddrMaps]
                                                                    newMaps[index].fromIp = e.target.value
                                                                    setIpaddrMaps(newMaps)
                                                                }}
                                                            />
                                                        </Col>
                                                        <Col span={8}>
                                                            <Input
                                                                placeholder="网关地址"
                                                                value={row.gate}
                                                                onChange={(e) => {
                                                                    const newMaps = [...ipaddrMaps]
                                                                    newMaps[index].gate = e.target.value
                                                                    setIpaddrMaps(newMaps)
                                                                }}
                                                            />
                                                        </Col>
                                                        <Col span={8}>
                                                            <Input
                                                                placeholder="子网掩码"
                                                                value={row.mask}
                                                                onChange={(e) => {
                                                                    const newMaps = [...ipaddrMaps]
                                                                    newMaps[index].mask = e.target.value
                                                                    setIpaddrMaps(newMaps)
                                                                }}
                                                            />
                                                        </Col>
                                                    </Row>
                                                </div>
                                            ))}
                                            <Button
                                                type="dashed"
                                                icon={<PlusOutlined/>}
                                                onClick={() => setIpaddrMaps([...ipaddrMaps, {
                                                    id: Date.now().toString(),
                                                    setName: '',
                                                    vers: 'ipv4',
                                                    type: 'nat',
                                                    gate: '',
                                                    mask: '',
                                                    fromIp: '',
                                                    nums: 0
                                                }])}
                                                block
                                            >
                                                添加IP地址池
                                            </Button>
                                        </div>

                                        <h4 className="font-medium mb-3 mt-4">API扩展选项</h4>
                                        <Form.Item name="extend_data" label="扩展数据 (JSON格式)">
                                            <Input.TextArea rows={4} placeholder='{"key": "value"}'/>
                                        </Form.Item>
                                    </div>
                                )
                            }
                        ]}
                    />
                </Form>
            </Modal>
        </div>
    )
}

export default HostManage