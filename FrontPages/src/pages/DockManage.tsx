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
    Input,
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
import PageHeader from '@/components/PageHeader'

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
    const [deleteModalOpen, setDeleteModalOpen] = useState(false)
    const [deleteVmUuid, setDeleteVmUuid] = useState<string>('')
    const [deleteHostName, setDeleteHostName] = useState<string>('')
    const [deleteConfirmInput, setDeleteConfirmInput] = useState<string>('')

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
                // 将enable_host字段映射为enabled
                const hostsWithEnabled = Object.entries(result.data).reduce((acc, [key, host]: [string, any]) => {
                    acc[key] = {
                        ...host,
                        enabled: host.enable_host !== false
                    }
                    return acc
                }, {} as Record<string, any>)
                setAvailableHosts(hostsWithEnabled)
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
                    // 过滤掉禁用的主机，不请求其虚拟机列表
                    const hosts = Object.keys(hostsRes.data).filter(
                        (host) => hostsRes.data[host].enable_host !== false
                    )
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
        // 检查主机是否被禁用
        if (availableHosts[hostName]?.enabled === false) {
            message.error('该主机已被禁用，无法扫描虚拟机')
            return
        }
        const hide = message.loading('正在扫描虚拟机...', 0)
        try {
            const result = await api.scanVMs(hostName)
            hide()
            if (result.code === 200) {
                message.success('扫描完成')
                loadVMs()
            } else {
                message.error(result.msg || '扫描失败')
            }
        } catch (error) {
            hide()
            message.error('扫描虚拟机失败')
        }
    }

    // Handlers
    const handleCreate = () => {
        // 检查主机是否被禁用
        if (hostName && availableHosts[hostName]?.enabled === false) {
            message.error('该主机已被禁用，无法创建虚拟机')
            return
        }
        setEditVmUuid(undefined)
        setCreateModalOpen(true)
    }

    const handleEdit = (uuid: string, host?: string) => {
        const targetHost = host || hostName
        if (!targetHost) {
            message.error('无法确定主机信息')
            return
        }

        // 检查主机是否被禁用
        if (availableHosts[targetHost]?.enabled === false) {
            message.error('该主机已被禁用，无法修改虚拟机')
            return
        }

        setPowerHostName(targetHost)
        setEditVmUuid(uuid)
        setCreateModalOpen(true)
    }

    const handleDelete = (uuid: string, host?: string) => {
        const targetHost = host || hostName
        if (!targetHost) return
        
        // 检查主机是否被禁用
        if (availableHosts[targetHost]?.enabled === false) {
            message.error('该主机已被禁用，无法删除虚拟机')
            return
        }
        
        setDeleteVmUuid(uuid)
        setDeleteHostName(targetHost)
        setDeleteConfirmInput('')
        setDeleteModalOpen(true)
    }

    const executeDelete = async () => {
        if (deleteConfirmInput !== deleteVmUuid) {
            message.error('输入的虚拟机名称不匹配')
            return
        }
        
        setDeleteModalOpen(false)
        const hide = message.loading('正在删除虚拟机...', 0)
        try {
            const result = await api.deleteVM(deleteHostName, deleteVmUuid)
            hide()
            if (result.code === 200) {
                message.success('虚拟机已删除')
                loadVMs()
            } else {
                message.error(result.msg || '删除失败')
            }
        } catch (error) {
            hide()
            message.error('删除失败')
        }
    }

    const handleOpenPower = (uuid: string, host?: string) => {
        const targetHost = host || hostName
        if (!targetHost) return
        
        // 检查主机是否被禁用
        if (availableHosts[targetHost]?.enabled === false) {
            message.error('该主机已被禁用，无法控制虚拟机电源')
            return
        }
        
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

        const hide = message.loading(`正在${actionMap[action]}虚拟机...`, 0)
        try {
            const result = await api.vmPower(powerHostName, powerVmUuid, action as any)
            hide()
            if (result.code === 200) {
                message.success(`${actionMap[action]}操作成功`)
                loadVMs()
            } else {
                message.error(result.msg || '操作失败')
            }
        } catch (error) {
            hide()
            message.error('操作失败')
        }
    }

    const handleOpenVnc = async (uuid: string, host?: string) => {
        const targetHost = host || hostName
        if (!targetHost) return

        const hide = message.loading('获取VNC地址...', 0)
        try {
            const result = await api.getVMConsole(targetHost, uuid)
            hide()
            if (result.code === 200 && result.data) {
                window.open(result.data.console_url || (result.data as any), `vnc_${uuid}`, 'width=1024,height=768')
            } else {
                message.error('无法获取VNC地址')
            }
        } catch (error) {
            hide()
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
            <PageHeader
                icon={<RadarChartOutlined />}
                title={hostName ? `虚拟机管理 - ${hostName}` : '所有虚拟机'}
                subtitle="管理和监控虚拟机实例"
                actions={
                    <>
                        {hostName && (
                            <Button 
                                icon={<RadarChartOutlined />} 
                                onClick={handleScan}
                                disabled={availableHosts[hostName]?.enabled === false}
                            >
                                扫描
                            </Button>
                        )}
                        <Button icon={<ReloadOutlined />} onClick={loadVMs}>
                            刷新
                        </Button>
                        <Button 
                            type="primary" 
                            icon={<PlusOutlined />} 
                            onClick={handleCreate}
                            disabled={hostName ? availableHosts[hostName]?.enabled === false : false}
                        >
                            创建虚拟机
                        </Button>
                        {hostName && (
                            <Button 
                                icon={<ArrowLeftOutlined />} 
                                onClick={() => navigate(-1)}
                            >
                                返回
                            </Button>
                        )}
                    </>
                }
            />

            {loading ? (
                <div className="flex justify-center items-center h-64">
                    <Spin size="large" />
                </div>
            ) : Object.keys(vms).length === 0 ? (
                <Empty description="暂无虚拟机" />
            ) : (
                <Row gutter={[16, 16]}>
                    {Object.entries(vms).map(([key, vm]) => {
                        const vmHost = vm._host || hostName
                        const isHostDisabled = vmHost ? availableHosts[vmHost]?.enabled === false : false
                        return (
                            <Col key={key} xs={24} sm={12} md={8} lg={6} xl={6} style={{ minWidth: 450 }}>
                                <DockCard
                                    uuid={vm._realUuid || key}
                                    vm={vm}
                                    hostName={vmHost}
                                    hostDisabled={isHostDisabled}
                                    onEdit={(uuid) => handleEdit(uuid, vm._host)}
                                    onDelete={(uuid) => handleDelete(uuid, vm._host)}
                                    onPower={(uuid) => handleOpenPower(uuid, vm._host)}
                                    onVnc={(uuid) => handleOpenVnc(uuid, vm._host)}
                                    onDetail={(uuid) => handleOpenDetail(uuid, vm._host)}
                                    style={{ minWidth: '500px' }}
                                />
                            </Col>
                        )
                    })}
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

            <Modal
                title="确认删除"
                open={deleteModalOpen}
                onCancel={() => setDeleteModalOpen(false)}
                onOk={executeDelete}
                okText="确认删除"
                okType="danger"
                cancelText="取消"
                mask={false}
                okButtonProps={{ disabled: deleteConfirmInput !== deleteVmUuid }}
            >
                <div>
                    <p>此操作将永久删除虚拟机 "<strong className="text-red-500">{deleteVmUuid}</strong>" 且不可恢复</p>
                    <p className="mt-2 mb-2 text-xs  ">请输入虚拟机名称以确认删除：</p>
                    <Input
                        placeholder="请输入虚拟机名称"
                        value={deleteConfirmInput}
                        onChange={(e) => setDeleteConfirmInput(e.target.value)}
                    />
                </div>
            </Modal>
        </div>
    )
}

export default DockManage
