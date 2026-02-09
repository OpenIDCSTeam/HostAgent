import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
    Button,
    message,
    Spin,
    Empty,
    Row,
    Col,
    Modal,
    Typography,
} from 'antd'
import {
    PlusOutlined,
    ReloadOutlined,
    ArrowLeftOutlined,
    RadarChartOutlined
} from '@ant-design/icons'
import api, { getHosts } from '@/utils/apis.ts'
import { useUserStore } from '@/utils/data.ts'
import DockCard from '@/components/dock/DockCard'
import DockCreateModal from '@/components/dock/DockCreateModal'
import DockPowerModal from '@/components/dock/DockPowerModal'

const { Title } = Typography

function DockManage() {
    const navigate = useNavigate()
    const { hostName } = useParams<{ hostName: string }>()
    const { user } = useUserStore()
    const isAdmin = user?.is_admin || false
    
    // State
    const [vms, setVMs] = useState<Record<string, any>>({})
    const [loading, setLoading] = useState(false)
    const [availableHosts, setAvailableHosts] = useState<Record<string, any>>({})
    const [userQuota, setUserQuota] = useState<any>(null)
    
    // Modals state
    const [createModalOpen, setCreateModalOpen] = useState(false)
    const [editVmUuid, setEditVmUuid] = useState<string | undefined>(undefined)
    
    const [powerModalOpen, setPowerModalOpen] = useState(false)
    const [powerVmUuid, setPowerVmUuid] = useState<string>('')
    const [powerHostName, setPowerHostName] = useState<string>('')

    // Initial data loading
    useEffect(() => {
        loadUserQuota()
        loadVMs()
        loadAvailableHosts()
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [hostName])

    const loadUserQuota = async () => {
        try {
            const result = await api.getCurrentUser()
            if (result.code === 200) {
                setUserQuota(result.data)
            }
        } catch (error) {
            console.error('获取用户配额失败:', error)
        }
    }

    const loadAvailableHosts = async () => {
        try {
            const result = await getHosts()
            if (result.code === 200 && result.data) {
                setAvailableHosts(result.data)
            }
        } catch (error) {
            console.error('加载主机列表失败:', error)
        }
    }

    const loadVMs = async () => {
        try {
            setLoading(true)
            let allVMs: Record<string, any> = {}
            const pathname = window.location.pathname

            if (hostName) {
                // Single host view
                const result = await api.getVMs(hostName)
                if (result.code === 200) {
                    allVMs = result.data || {}
                }
            } else {
                // All hosts view (System or User)
                const hostsRes = await getHosts()
                if (hostsRes.code === 200 && hostsRes.data) {
                    const hosts = Object.keys(hostsRes.data)
                    await Promise.all(hosts.map(async (host) => {
                        try {
                            const vmsRes = await api.getVMs(host)
                            if (vmsRes.code === 200 && vmsRes.data) {
                                Object.entries(vmsRes.data).forEach(([uuid, vm]) => {
                                    allVMs[`${host}-${uuid}`] = { ...vm, _host: host, _realUuid: uuid }
                                })
                            }
                        } catch (err) {
                            console.error(`获取主机 ${host} 的虚拟机失败`, err)
                        }
                    }))
                }
            }
            setVMs(allVMs)
        } catch (error) {
            message.error('加载虚拟机列表失败')
        } finally {
            setLoading(false)
        }
    }

    const handleScan = async () => {
        if (!hostName) return
        try {
            const hide = message.loading('正在扫描虚拟机...', 0)
            const result = await api.scanVMs(hostName)
            hide()
            if (result.code === 200) {
                message.success('扫描完成')
                loadVMs()
            } else {
                message.error(result.msg || '扫描失败')
            }
        } catch (error) {
            message.error('扫描虚拟机失败')
        }
    }

    // Handlers
    const handleCreate = () => {
        setEditVmUuid(undefined)
        setCreateModalOpen(true)
    }

    const handleEdit = (uuid: string, host?: string) => {
        const targetHost = host || hostName
        if (!targetHost) {
            message.error('无法确定主机信息')
            return
        }

        setPowerHostName(targetHost)
        setEditVmUuid(uuid)
        setCreateModalOpen(true)
    }

    const handleDelete = (uuid: string, host?: string) => {
        const targetHost = host || hostName
        if (!targetHost) return

        Modal.confirm({
            title: '确认删除',
            content: (
                <div>
                    <p>此操作将永久删除虚拟机 "<strong className="text-red-500">{uuid}</strong>" 且不可恢复</p>
                    <p className="mt-2 text-xs text-gray-500">请输入虚拟机名称以确认删除</p>
                </div>
            ),
            okText: '确认删除',
            okType: 'danger',
            cancelText: '取消',
            onOk: async () => {
                try {
                    const hide = message.loading('正在删除虚拟机...', 0)
                    const result = await api.deleteVM(targetHost, uuid)
                    hide()
                    if (result.code === 200) {
                        message.success('虚拟机已删除')
                        loadVMs()
                    } else {
                        message.error(result.msg || '删除失败')
                    }
                } catch (error) {
                    message.error('删除失败')
                }
            },
        })
    }

    const handleOpenPower = (uuid: string, host?: string) => {
        const targetHost = host || hostName
        if (!targetHost) return
        
        setPowerVmUuid(uuid)
        setPowerHostName(targetHost)
        setPowerModalOpen(true)
    }

    const handlePowerAction = async (action: string) => {
        if (!powerHostName || !powerVmUuid) return
        setPowerModalOpen(false)

        const actionMap: Record<string, string> = {
            start: '启动',
            stop: '关机',
            hard_stop: '强制关机',
            reset: '重启',
            hard_reset: '强制重启',
            pause: '暂停',
            resume: '恢复',
        }

        try {
            const hide = message.loading(`正在${actionMap[action]}虚拟机...`, 0)
            const result = await api.vmPower(powerHostName, powerVmUuid, action as any)
            hide()
            if (result.code === 200) {
                message.success(`${actionMap[action]}操作成功`)
                loadVMs()
            } else {
                message.error(result.msg || '操作失败')
            }
        } catch (error) {
            message.error('操作失败')
        }
    }

    const handleOpenVnc = async (uuid: string, host?: string) => {
        const targetHost = host || hostName
        if (!targetHost) return

        try {
            const hide = message.loading('获取VNC地址...', 0)
            const result = await api.getVMConsole(targetHost, uuid)
            hide()
            if (result.code === 200 && result.data) {
                window.open(result.data.console_url || (result.data as any), `vnc_${uuid}`, 'width=1024,height=768')
            } else {
                message.error('无法获取VNC地址')
            }
        } catch (error) {
            message.error('连接失败')
        }
    }

    const handleOpenDetail = (uuid: string, host?: string) => {
        const targetHost = host || hostName
        if (!targetHost) return
        
        // 跳转到详情页面
        navigate(`/hosts/${targetHost}/vms/${uuid}`)
    }

    return (
        <div className="p-6">
            <div className="page-header">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4 flex-1">
                        {hostName && (
                            <Button 
                                icon={<ArrowLeftOutlined />} 
                                onClick={() => navigate(-1)}
                            >
                                返回
                            </Button>
                        )}
                        <div className="flex-1">
                            <Title level={2} className="page-header-title">
                                <RadarChartOutlined />
                                {hostName ? `虚拟机管理 - ${hostName}` : '所有虚拟机'}
                            </Title>
                            <div className="page-header-subtitle">
                                管理和监控虚拟机实例
                            </div>
                        </div>
                    </div>
                    <div className="flex gap-3">
                        {hostName && (
                            <Button icon={<RadarChartOutlined />} onClick={handleScan}>
                                扫描
                            </Button>
                        )}
                        <Button icon={<ReloadOutlined />} onClick={loadVMs}>
                            刷新
                        </Button>
                        <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
                            创建虚拟机
                        </Button>
                    </div>
                </div>
            </div>

            {loading ? (
                <div className="flex justify-center items-center h-64">
                    <Spin size="large" />
                </div>
            ) : Object.keys(vms).length === 0 ? (
                <Empty description="暂无虚拟机" />
            ) : (
                <Row gutter={[16, 16]}>
                    {Object.entries(vms).map(([key, vm]) => (
                        <Col key={key} xs={24} sm={12} md={8} lg={6} xl={6}>
                            <DockCard
                                uuid={vm._realUuid || key} // Use real UUID if available
                                vm={vm}
                                hostName={vm._host || hostName}
                                onEdit={(uuid) => handleEdit(uuid, vm._host)}
                                onDelete={(uuid) => handleDelete(uuid, vm._host)}
                                onPower={(uuid) => handleOpenPower(uuid, vm._host)}
                                onVnc={(uuid) => handleOpenVnc(uuid, vm._host)}
                                onDetail={(uuid) => handleOpenDetail(uuid, vm._host)}
                            />
                        </Col>
                    ))}
                </Row>
            )}

            <DockCreateModal
                open={createModalOpen}
                onCancel={() => setCreateModalOpen(false)}
                onSuccess={() => {
                    setCreateModalOpen(false)
                    loadVMs()
                }}
                hostName={editVmUuid ? powerHostName : hostName} // Pass correct host context
                vmUuid={editVmUuid}
                isAdmin={isAdmin}
                userQuota={userQuota}
                availableHosts={availableHosts}
            />

            <DockPowerModal
                open={powerModalOpen}
                onCancel={() => setPowerModalOpen(false)}
                vmUuid={powerVmUuid}
                onAction={handlePowerAction}
            />
        </div>
    )
}

export default DockManage
