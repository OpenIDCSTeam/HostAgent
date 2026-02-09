import React from 'react'
import { Card, Tag, Row, Col, Tooltip, Button, Progress, Badge } from 'antd'
import {
    DesktopOutlined,
    PoweroffOutlined,
    EditOutlined,
    DeleteOutlined,
    GlobalOutlined,
    EyeOutlined,
    ClockCircleOutlined,
    DatabaseOutlined,
    ThunderboltOutlined,
    CloudServerOutlined,
    ApiOutlined,
    SafetyOutlined,
    PlayCircleOutlined,
    QuestionCircleOutlined,
    LoadingOutlined,
    PauseCircleOutlined
} from '@ant-design/icons'
import { VM_STATUS_MAP } from '@/constants/status'

interface DockCardProps {
    uuid: string
    vm: any // Using any for VM type for now to avoid duplicating interfaces
    hostName?: string
    onEdit: (uuid: string) => void
    onDelete: (uuid: string) => void
    onPower: (uuid: string) => void
    onVnc: (uuid: string) => void
    onDetail: (uuid: string) => void
}

const formatMemory = (mb?: number): string => {
    if (!mb) return '0 MB'
    if (mb >= 1024) return `${(mb / 1024).toFixed(1)} GB`
    return `${mb} MB`
}

const formatDisk = (mb?: number): string => {
    if (!mb) return '0 MB'
    if (mb >= 1024) return `${(mb / 1024).toFixed(1)} GB`
    return `${mb} MB`
}

const formatUptime = (seconds?: number): string => {
    if (!seconds) return '未运行'
    const days = Math.floor(seconds / 86400)
    const hours = Math.floor((seconds % 86400) / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    
    if (days > 0) return `${days}天${hours}小时`
    if (hours > 0) return `${hours}小时${minutes}分钟`
    return `${minutes}分钟`
}

const formatDate = (timestamp?: number): string => {
    if (!timestamp) return '未知'
    const date = new Date(timestamp * 1000)
    return date.toLocaleDateString('zh-CN', { 
        year: 'numeric', 
        month: '2-digit', 
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    })
}

const DockCard: React.FC<DockCardProps> = ({
    uuid,
    vm,
    hostName,
    onEdit,
    onDelete,
    onPower,
    onVnc,
    onDetail
}) => {
    const config = vm.config || {}
    const statusList = vm.status || []
    const firstStatus = statusList.length > 0 ? statusList[0] : { ac_status: 'UNKNOWN' }
    const powerStatus = firstStatus.ac_status || 'UNKNOWN'
    const statusInfo = VM_STATUS_MAP[powerStatus] || VM_STATUS_MAP.UNKNOWN

    const nicAll = config.nic_all || {}
    const firstNic = Object.values(nicAll)[0] || {}
    // @ts-ignore
    const ipv4 = firstNic.ip4_addr || '-'
    // @ts-ignore
    const ipv6 = firstNic.ip6_addr || '-'
    // @ts-ignore
    const macAddr = firstNic.mac_addr || '-'

    const isRunning = powerStatus === 'STARTED'
    
    // 从status中获取实际资源使用率
    const cpuTotal = firstStatus.cpu_total || config.cpu_num || 0
    const cpuUsage = firstStatus.cpu_usage || 0
    const cpuPercent = cpuTotal > 0 ? Math.round((cpuUsage / cpuTotal) * 100) : 0
    
    const memTotal = firstStatus.mem_total || config.mem_num || 0
    const memUsage = firstStatus.mem_usage || 0
    const memPercent = memTotal > 0 ? Math.round((memUsage / memTotal) * 100) : 0
    
    const hddTotal = firstStatus.hdd_total || config.hdd_num || 0
    const hddUsage = firstStatus.hdd_usage || 0
    const diskUsage = hddTotal > 0 ? Math.round((hddUsage / hddTotal) * 100) : 0
    
    // GPU使用率（如果有的话）
    const gpuTotal = firstStatus.gpu_total || 0
    const gpuUsageObj = firstStatus.gpu_usage || {}
    const gpuUsageValue = Object.values(gpuUsageObj)[0] || 0
    const gpuPercent = gpuTotal > 0 ? Math.round((Number(gpuUsageValue) / gpuTotal) * 100) : 0
    
    // 运行时长（秒）
    const uptime = firstStatus.uptime || 0
    const createTime = vm.create_time || 0

    // 根据电源状态获取图标和颜色
    const getStatusIcon = () => {
        switch (powerStatus) {
            case 'STARTED':
                return <PlayCircleOutlined className="text-green-600 dark:text-green-400" />
            case 'STOPPED':
                return <PoweroffOutlined className="text-red-600 dark:text-red-400" />
            case 'PAUSED':
                return <PauseCircleOutlined className="text-blue-600 dark:text-blue-400" />
            case 'STARTING':
            case 'STOPPING':
            case 'PAUSING':
            case 'RESUMING':
                return <LoadingOutlined className="text-yellow-600 dark:text-yellow-400" spin />
            default:
                return <QuestionCircleOutlined className="text-gray-500 dark:text-gray-400" />
        }
    }

    return (
        <Card
            hoverable
            className="glass-effect h-full flex flex-col"
            styles={{ 
                body: { 
                    padding: 0,
                    flex: 1, 
                    display: 'flex', 
                    flexDirection: 'column',
                    overflow: 'hidden'
                } 
            }}
        >
            {/* 头部区域 */}
            <div className="relative p-4 border-b border-gray-200/50 dark:border-gray-700/50">
                <div className="flex justify-between items-start">
                    <div className="flex gap-3 items-center flex-1 min-w-0">
                        <div className="w-12 h-12 rounded-xl flex items-center justify-center border border-purple-600/50 dark:border-purple-400/50 flex-shrink-0">
                            <DesktopOutlined className="text-2xl text-purple-600 dark:text-purple-400" />
                        </div>
                        <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                                <Tooltip title={uuid}>
                                    <h3 className="m-0 text-base font-bold text-gray-900 dark:text-white truncate">
                                        {uuid}
                                    </h3>
                                </Tooltip>
                                {hostName && (
                                    <Tag icon={<CloudServerOutlined />} color="blue" className="m-0 flex-shrink-0">
                                        {hostName}
                                    </Tag>
                                )}
                                <Tag color={statusInfo.color} className={statusInfo.className} icon={getStatusIcon()}>
                                    {statusInfo.text}
                                </Tag>
                            </div>
                            <div className="flex items-center gap-2">
                                <span className="text-xs text-gray-600 dark:text-gray-400">
                                    {config.os_name || '未知系统'}
                                </span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* 主体内容区域 */}
            <div className="flex-1 p-4 space-y-3 overflow-y-auto">
                {/* 资源配置 */}
                <div className="space-y-2">
                    <div className="text-xs font-semibold text-gray-700 dark:text-gray-300 flex items-center gap-1">
                        <DatabaseOutlined className="text-blue-500" />
                        资源配置
                    </div>
                    <Row gutter={[8, 8]}>
                        <Col span={12}>
                            <div className="p-2 rounded-lg border border-white/20 dark:border-gray-700/30">
                                <div className="flex items-center justify-between mb-1">
                                    <span className="text-xs text-gray-600 dark:text-gray-400">CPU</span>
                                    <span className="text-xs font-bold text-gray-900 dark:text-white">
                                        {cpuTotal} 核 {cpuPercent}%
                                    </span>
                                </div>
                                <Progress
                                    percent={cpuPercent}
                                    size="small"
                                    strokeColor={{ '0%': '#3b82f6', '100%': '#8b5cf6' }}
                                    showInfo={false}
                                />
                            </div>
                        </Col>
                        <Col span={12}>
                            <div className="p-2 rounded-lg border border-white/20 dark:border-gray-700/30">
                                <div className="flex items-center justify-between mb-1">
                                    <span className="text-xs text-gray-600 dark:text-gray-400">内存</span>
                                    <span className="text-xs font-bold text-gray-900 dark:text-white">
                                        {formatMemory(memUsage)} / {formatMemory(memTotal)}
                                    </span>
                                </div>
                                <Progress
                                    percent={memPercent}
                                    size="small"
                                    strokeColor={{ '0%': '#8b5cf6', '100%': '#ec4899' }}
                                    showInfo={false}
                                />
                            </div>
                        </Col>
                        <Col span={12}>
                            <div className="p-2 rounded-lg border border-white/20 dark:border-gray-700/30">
                                <div className="flex items-center justify-between mb-1">
                                    <span className="text-xs text-gray-600 dark:text-gray-400">硬盘</span>
                                    <span className="text-xs font-bold text-gray-900 dark:text-white">
                                        {formatMemory(hddUsage)} / {formatMemory(hddTotal)}
                                    </span>
                                </div>
                                <Progress
                                    percent={diskUsage}
                                    size="small"
                                    strokeColor={{ '0%': '#10b981', '100%': '#059669' }}
                                    showInfo={false}
                                />
                            </div>
                        </Col>
                        <Col span={12}>
                            <div className="p-2 rounded-lg border border-white/20 dark:border-gray-700/30">
                                <div className="flex items-center justify-between mb-1">
                                    <span className="text-xs text-gray-600 dark:text-gray-400">显存</span>
                                    <span className="text-xs font-bold text-gray-900 dark:text-white">
                                        {formatMemory(Number(gpuUsageValue) || 0)} / {formatMemory(config.gpu_mem || gpuTotal)}
                                    </span>
                                </div>
                                <Progress
                                    percent={gpuPercent}
                                    size="small"
                                    strokeColor={{ '0%': '#f59e0b', '100%': '#ef4444' }}
                                    showInfo={false}
                                />
                            </div>
                        </Col>
                    </Row>
                </div>

                {/* 运行状态 */}
                {isRunning && (
                    <div className="p-3 rounded-lg border border-green-200/50 dark:border-green-700/50">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <ThunderboltOutlined className="text-green-600 dark:text-green-400" />
                                <span className="text-xs font-semibold text-gray-700 dark:text-gray-300">运行时长</span>
                            </div>
                            <span className="text-sm font-bold text-green-700 dark:text-green-400">
                                {formatUptime(uptime)}
                            </span>
                        </div>
                    </div>
                )}

                {/* 网络端口 */}
                <div className="p-3 rounded-lg border border-white/20 dark:border-gray-700/30">
                    <div className="text-xs font-semibold text-gray-700 dark:text-gray-300 mb-2 flex items-center gap-1">
                        <ApiOutlined className="text-cyan-600 dark:text-cyan-400" />
                        网络端口
                    </div>
                    <Row gutter={[8, 8]}>
                        <Col span={12}>
                            <div className="flex items-center justify-between">
                                <span className="text-xs text-gray-600 dark:text-gray-400">NAT端口</span>
                                <span className="text-xs font-mono text-cyan-600 dark:text-cyan-400">
                                    {(config.nat_all || []).length} / {config.nat_num || 100}
                                </span>
                            </div>
                        </Col>
                        <Col span={12}>
                            <div className="flex items-center justify-between">
                                <span className="text-xs text-gray-600 dark:text-gray-400">Web代理</span>
                                <span className="text-xs font-mono text-purple-600 dark:text-purple-400">
                                    {(config.web_all || []).length} / {config.web_num || 100}
                                </span>
                            </div>
                        </Col>
                    </Row>
                </div>

                {/* 网卡信息 */}
                <div className="p-3 rounded-lg border border-white/20 dark:border-gray-700/30">
                    <div className="text-xs font-semibold text-gray-700 dark:text-gray-300 mb-2 flex items-center gap-1">
                        <GlobalOutlined className="text-indigo-600 dark:text-indigo-400" />
                        网卡信息
                    </div>
                    <div className="flex items-center gap-2">
                        <span className="text-xs text-gray-600 dark:text-gray-400 shrink-0">IP/MAC:</span>
                        <Tooltip title={`IPv4: ${ipv4} | IPv6: ${ipv6 !== '-' ? ipv6 : '未配置'} | MAC: ${macAddr}`}>
                            <span className="text-xs font-mono text-gray-900 dark:text-white truncate flex-1">
                                {ipv4} / {ipv6 !== '-' ? ipv6 : '未配置'} | {macAddr}
                            </span>
                        </Tooltip>
                    </div>
                </div>
            </div>

            {/* 底部操作栏 */}
            <div className="flex justify-end gap-2 p-3 border-t border-white/20 dark:border-gray-700/30">
                <Button 
                    type="link" 
                    size="small"
                    icon={<EyeOutlined />} 
                    onClick={() => onDetail(uuid)}
                    className="flex items-center gap-1 whitespace-nowrap"
                >
                    查看详情
                </Button>
                <Tooltip title="VNC控制台">
                    <Button 
                        type="text" 
                        size="small"
                        icon={<DesktopOutlined />} 
                        onClick={() => onVnc(uuid)}
                        disabled={!isRunning}
                        className="hover:bg-purple-50 dark:hover:bg-purple-900/30"
                    />
                </Tooltip>
                <Tooltip title="电源操作">
                    <Button 
                        type="text" 
                        size="small"
                        icon={<PoweroffOutlined className={isRunning ? 'text-green-500' : 'text-gray-400'} />} 
                        onClick={() => onPower(uuid)}
                        className="hover:bg-green-50 dark:hover:bg-green-900/30"
                    />
                </Tooltip>
                <Tooltip title="编辑配置">
                    <Button 
                        type="text" 
                        size="small"
                        icon={<EditOutlined />} 
                        onClick={() => onEdit(uuid)}
                        className="hover:bg-orange-50 dark:hover:bg-orange-900/30"
                    />
                </Tooltip>
                <Tooltip title="删除虚拟机">
                    <Button 
                        type="text" 
                        size="small"
                        danger
                        icon={<DeleteOutlined />} 
                        onClick={() => onDelete(uuid)}
                        className="hover:bg-red-50 dark:hover:bg-red-900/30"
                    />
                </Tooltip>
            </div>
        </Card>
    )
}

export default DockCard
