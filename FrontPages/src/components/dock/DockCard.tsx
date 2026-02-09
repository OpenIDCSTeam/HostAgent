import React from 'react'
import { Card, Tag, Row, Col, Tooltip, Button, Dropdown } from 'antd'
import {
    DesktopOutlined,
    PoweroffOutlined,
    EditOutlined,
    DeleteOutlined,
    PlayCircleOutlined,
    PauseCircleOutlined,
    RedoOutlined,
    ThunderboltOutlined,
    MoreOutlined,
    GlobalOutlined,
    EyeOutlined
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

    const isRunning = powerStatus === 'STARTED'

    return (
        <Card
            hoverable
            className="glass-effect h-full flex flex-col"
            styles={{ body: { padding: 16, flex: 1, display: 'flex', flexDirection: 'column' } }}
        >
            <div className="mb-4">
                <div className="flex justify-between items-start">
                    <div className="flex gap-3 items-center">
                        <div className="w-12 h-12 rounded-lg flex items-center justify-center bg-gradient-to-br from-purple-600 to-purple-800 shadow-lg shadow-purple-500/30">
                            <DesktopOutlined className="text-2xl text-white" />
                        </div>
                        <div>
                            <h3 className="m-0 text-base font-semibold text-gray-900 dark:text-white truncate max-w-[150px]" title={uuid}>
                                {uuid}
                            </h3>
                            <p className="m-0 text-xs text-gray-500 dark:text-gray-400">
                                {config.os_name || '未知系统'}
                            </p>
                        </div>
                    </div>
                    <Tag color={statusInfo.color} className={statusInfo.className}>
                        {statusInfo.text}
                    </Tag>
                </div>
                {hostName && (
                    <div className="mt-2">
                        <Tag color="blue">{hostName}</Tag>
                    </div>
                )}
            </div>

            {/* Resources */}
            <Row gutter={[8, 8]} className="mb-4">
                <Col span={12}>
                    <div className="text-xs text-gray-500">
                        CPU: <strong className="text-gray-700 dark:text-gray-300">{config.cpu_num || 0} 核</strong>
                    </div>
                </Col>
                <Col span={12}>
                    <div className="text-xs text-gray-500">
                        内存: <strong className="text-gray-700 dark:text-gray-300">{formatMemory(config.mem_num)}</strong>
                    </div>
                </Col>
                <Col span={12}>
                    <div className="text-xs text-gray-500">
                        硬盘: <strong className="text-gray-700 dark:text-gray-300">{formatDisk(config.hdd_num)}</strong>
                    </div>
                </Col>
                <Col span={12}>
                    <div className="text-xs text-gray-500">
                        显存: <strong className="text-gray-700 dark:text-gray-300">{formatMemory(config.gpu_mem)}</strong>
                    </div>
                </Col>
            </Row>

            {/* Ports */}
            <div className="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg mb-4">
                <Row gutter={[8, 8]}>
                    <Col span={12}>
                        <div className="text-xs text-gray-500">
                            NAT端口: <strong className="text-gray-700 dark:text-gray-300">{config.nat_num || 0}个</strong>
                        </div>
                    </Col>
                    <Col span={12}>
                        <div className="text-xs text-gray-500">
                            Web代理: <strong className="text-gray-700 dark:text-gray-300">{config.web_num || 0}个</strong>
                        </div>
                    </Col>
                </Row>
            </div>

            {/* Network */}
            <div className="p-3 bg-blue-50/50 dark:bg-blue-900/20 border border-blue-100 dark:border-blue-800 rounded-lg mb-4">
                <div className="text-xs font-semibold text-blue-600 dark:text-blue-400 mb-2">
                    <GlobalOutlined className="mr-1" /> 网卡信息
                </div>
                <div className="text-xs space-y-1">
                    <div className="flex">
                        <span className="text-gray-500 w-12 shrink-0">IPv4:</span>
                        <span className="font-mono text-gray-700 dark:text-gray-300 truncate">{ipv4}</span>
                    </div>
                    <div className="flex">
                        <span className="text-gray-500 w-12 shrink-0">IPv6:</span>
                        <span className="font-mono text-gray-700 dark:text-gray-300 truncate">
                            {ipv6 !== '-' ? ipv6 : '未配置'}
                        </span>
                    </div>
                </div>
            </div>

            <div className="flex justify-end gap-2 mt-auto pt-4 border-t border-gray-100 dark:border-gray-700">
                <Tooltip title="查看详情">
                    <Button 
                        type="text" 
                        icon={<EyeOutlined />} 
                        onClick={() => onDetail(uuid)}
                    />
                </Tooltip>
                <Tooltip title="VNC控制台">
                    <Button 
                        type="text" 
                        icon={<DesktopOutlined />} 
                        onClick={() => onVnc(uuid)}
                        disabled={!isRunning}
                    />
                </Tooltip>
                <Tooltip title="电源操作">
                    <Button 
                        type="text" 
                        icon={<PoweroffOutlined className={isRunning ? 'text-green-500' : 'text-gray-400'} />} 
                        onClick={() => onPower(uuid)}
                    />
                </Tooltip>
                <Tooltip title="编辑配置">
                    <Button 
                        type="text" 
                        icon={<EditOutlined />} 
                        onClick={() => onEdit(uuid)}
                    />
                </Tooltip>
                <Tooltip title="删除虚拟机">
                    <Button 
                        type="text" 
                        danger
                        icon={<DeleteOutlined />} 
                        onClick={() => onDelete(uuid)}
                    />
                </Tooltip>
            </div>
        </Card>
    )
}

export default DockCard
