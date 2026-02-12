import React, { useEffect, useState } from 'react'
import {
    Modal,
    Form,
    Input,
    Select,
    InputNumber,
    message,
    Row,
    Col,
    Button,
    Space,
    Slider,
    Alert,
    Divider
} from 'antd'
import {
    PlusOutlined,
    DeleteOutlined,
    RadarChartOutlined,
    ThunderboltOutlined,
    DesktopOutlined,
    GlobalOutlined,
    ReloadOutlined
} from '@ant-design/icons'
import api from '@/utils/apis.ts'
import { VM_PERMISSION, hasPermission } from '@/types'

// Interfaces
interface UserQuota {
    quota_cpu: number
    used_cpu: number
    quota_ram: number
    used_ram: number
    quota_ssd: number
    used_ssd: number
    quota_nat_ips: number
    used_nat_ips: number
    quota_pub_ips: number
    used_pub_ips: number
    quota_traffic: number
    used_traffic: number
    quota_upload_bw: number
    used_upload_bw: number
    quota_download_bw: number
    used_download_bw: number
    quota_nat: number
    used_nat: number
    quota_web: number
    used_web: number
}

interface HostConfig {
    filter_name: string
    system_maps: Record<string, [string, number]>
    images_maps: Record<string, string>
    server_type: string
    ban_init: string[]
    ban_edit: string[]
    messages: string[]
}

interface DockCreateModalProps {
    open: boolean
    onCancel: () => void
    onSuccess: () => void
    hostName?: string
    vmUuid?: string
    isAdmin: boolean
    userQuota: UserQuota | null
    availableHosts: Record<string, any>
    userPermissions?: number
}

interface NicItem {
    key: number
    name: string
    type: string
}

const DockCreateModal: React.FC<DockCreateModalProps> = ({
    open,
    onCancel,
    onSuccess,
    hostName,
    vmUuid,
    isAdmin,
    userQuota,
    availableHosts,
    userPermissions
}) => {
    const [form] = Form.useForm()
    const isEditMode = !!vmUuid
    const [loading, setLoading] = useState(false)
    
    // Internal state
    const [nicList, setNicList] = useState<NicItem[]>([])
    const [nicCounter, setNicCounter] = useState(0)
    const [selectedHost, setSelectedHost] = useState<string>('')
    const [hostConfig, setHostConfig] = useState<HostConfig | null>(null)
    const [hostImages, setHostImages] = useState<Record<string, [string, number]>>({})
    const [gpuList, setGpuList] = useState<Record<string, string>>({})
    const [pciDeviceList, setPciDeviceList] = useState<Record<string, any>>({})
    const [usbDeviceList, setUsbDeviceList] = useState<Record<string, any>>({})
    const [selectedOsMinDisk, setSelectedOsMinDisk] = useState(0)
    const [saveConfirmVisible, setSaveConfirmVisible] = useState(false)
    const [pendingValues, setPendingValues] = useState<any>(null)
    const [vmPerms, setVmPerms] = useState<number>(userPermissions ?? VM_PERMISSION.FULL_MASK)

    // 编辑模式下的权限控制（管理员拥有全部权限）
    const canEditSys = isAdmin || hasPermission(vmPerms, VM_PERMISSION.SYS_EDITS)
    const canEditPwd = isAdmin || hasPermission(vmPerms, VM_PERMISSION.PWD_EDITS)
    const canEditVnc = isAdmin || hasPermission(vmPerms, VM_PERMISSION.VNC_EDITS)

    // 生成随机字符串
    const generateRandomString = (length: number) => {
        const letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
        const numbers = '0123456789'
        let result = ''
        result += letters.charAt(Math.floor(Math.random() * letters.length))
        result += numbers.charAt(Math.floor(Math.random() * numbers.length))
        const allChars = letters + numbers
        for (let i = result.length; i < length; i++) {
            result += allChars.charAt(Math.floor(Math.random() * allChars.length))
        }
        return result.split('').sort(() => Math.random() - 0.5).join('')
    }

    // 生成随机VNC端口
    const generateRandomVncPort = () => {
        return Math.floor(Math.random() * (6999 - 5900 + 1)) + 5900
    }

    // Helper for rendering slider + input
    const renderResourceInput = (
        name: string,
        label: string,
        min: number,
        max: number,
        step: number = 1,
        unit: string = '',
        disabled: boolean = false,
        quotaUsed: number = 0,
        quotaTotal: number = 0,
        showQuota: boolean = false
    ) => {
        const currentValue = Form.useWatch(name, form)
        
        return (
            <Form.Item label={label} style={{ marginBottom: 24 }}>
                {showQuota && !isAdmin && (
                    <div className="flex justify-between text-xs mb-2">
                        <span>当前: <strong>{currentValue}</strong> {unit}</span>
                        <span>可用: {Math.max(0, quotaTotal - quotaUsed)} {unit}</span>
                    </div>
                )}
                <Row gutter={16} align="middle">
                    <Col span={14}>
                        <Form.Item name={name} noStyle>
                            <Slider
                                min={min}
                                max={max}
                                step={step}
                                disabled={disabled}
                                onChange={(val) => form.setFieldValue(name, val)}
                                value={currentValue}
                            />
                        </Form.Item>
                    </Col>
                    <Col span={10}>
                        <Form.Item name={name} noStyle>
                            <InputNumber
                                min={min}
                                max={max}
                                step={step}
                                disabled={disabled}
                                style={{ width: '100%' }}
                                addonAfter={unit || undefined}
                            />
                        </Form.Item>
                    </Col>
                </Row>
                {/* Special hint for HDD */}
                {name === 'hdd_num' && selectedOsMinDisk > 0 && (
                    <div className="text-xs mt-1">
                        最小要求: {selectedOsMinDisk}GB
                    </div>
                )}
            </Form.Item>
        )
    }

    // Load host data
    const loadHostData = async (host: string) => {
        if (!host) {
            setHostImages({})
            setGpuList({})
            setHostConfig(null)
            return
        }
        try {
            // Load OS Images
            const imagesResult = await api.getOSImages(host)
            if (imagesResult.code === 200 && imagesResult.data) {
                setHostConfig(imagesResult.data as any)
setHostImages((imagesResult.data.system_maps || {}) as unknown as Record<string, [string, number]>)
            }

            // Load GPU List
            const gpuResult = await api.getGPUList(host)
            if (gpuResult.code === 200 && gpuResult.data) {
                setGpuList(gpuResult.data)
            } else {
                setGpuList({})
            }

            // Load PCI Device List
            const pciResult = await api.getPCIList(host)
            if (pciResult.code === 200 && pciResult.data) {
                setPciDeviceList(pciResult.data)
            } else {
                setPciDeviceList({})
            }

            // Load USB Device List
            const usbResult = await api.getUSBList(host)
            if (usbResult.code === 200 && usbResult.data) {
                setUsbDeviceList(usbResult.data)
            } else {
                setUsbDeviceList({})
            }
        } catch (error) {
            console.error('加载主机配置失败:', error)
            setHostImages({})
            setGpuList({})
            setPciDeviceList({})
            setUsbDeviceList({})
        }
    }

    // Initialize form
    useEffect(() => {
        if (open) {
            if (isEditMode && vmUuid) {
                loadVmDetails()
            } else {
                resetForm()
            }
        } else {
            form.resetFields()
            setNicList([])
            setSaveConfirmVisible(false)
        }
    }, [open, vmUuid])

    const loadVmDetails = async () => {
        const targetHost = hostName
        if (!targetHost || !vmUuid) {
            if (isEditMode && !targetHost) {
                message.error('未指定主机，无法加载虚拟机详情')
            }
            return
        }

        try {
            setLoading(true)
            await loadHostData(targetHost)
            setSelectedHost(targetHost)

            const result = await api.getVMDetail(targetHost, vmUuid)
            if (result.code === 200) {
                const vm = result.data as Record<string, any>
                const config = vm?.config || {}

                // 从API返回值更新用户权限
                const apiPerms = typeof vm?.user_permissions === 'number' ? vm.user_permissions : VM_PERMISSION.FULL_MASK
                setVmPerms(apiPerms)
                // 用局部变量判断权限（避免React state异步更新时序问题）
                const localCanEditSys = isAdmin || hasPermission(apiPerms, VM_PERMISSION.SYS_EDITS)
                const localCanEditPwd = isAdmin || hasPermission(apiPerms, VM_PERMISSION.PWD_EDITS)
                const localCanEditVnc = isAdmin || hasPermission(apiPerms, VM_PERMISSION.VNC_EDITS)
                
                const gpuId = config.gpu_id || ''
                let gpuMdev = ''
                let gpuRemark = ''
                if (gpuId && config.pci_all && config.pci_all[gpuId]) {
                    gpuMdev = config.pci_all[gpuId].gpu_mdev || ''
                    gpuRemark = config.pci_all[gpuId].gpu_hint || ''
                }
                const fluRst = config.flu_rst || [31, 10, 0]

                // USB Config
                let usbVid = ''
                let usbPid = ''
                let usbRemark = ''
                if (config.usb_all) {
                    const usbKeys = Object.keys(config.usb_all)
                    if (usbKeys.length > 0) {
                        const usb = config.usb_all[usbKeys[0]]
                        usbVid = usb.vid_uuid || ''
                        usbPid = usb.pid_uuid || ''
                        usbRemark = usb.usb_hint || ''
                    }
                }

                form.setFieldsValue({
                    host_name: targetHost,
                    vm_uuid_suffix: vmUuid,
                    os_name: localCanEditSys ? config.os_name : '',
                    os_pass: localCanEditPwd ? config.os_pass : '',
                    vc_pass: localCanEditVnc ? config.vc_pass : '',
                    vc_port: config.vc_port,
                    cpu_num: config.cpu_num,
                    cpu_per: config.cpu_per ?? 100,
                    mem_num: config.mem_num,
                    hdd_num: config.hdd_num,
                    hdd_iop: config.hdd_iop ?? 1000,
                    gpu_id: gpuId,
                    gpu_num: config.gpu_num || 0,
                    gpu_mem: config.gpu_mem,
                    gpu_mdev: gpuMdev,
                    gpu_remark: gpuRemark,
                    usb_vid: usbVid,
                    usb_pid: usbPid,
                    usb_remark: usbRemark,
                    speed_u: config.speed_u,
                    speed_d: config.speed_d,
                    nat_num: config.nat_num,
                    flu_num: config.flu_num,
                    flu_rst_day: fluRst[0],
                    flu_rst_limit: fluRst[1],
                    flu_rst_time: fluRst[2],
                    web_num: config.web_num,
                })

                // Set min disk requirement based on current OS
                if (config.os_name && result.data && (result.data as any).system_maps) {
                   // This logic is tricky because we need system_maps from hostConfig which might not be loaded yet
                   // We rely on loadHostData to populate hostImages
                }

                // NICs
                const nicAll = config.nic_all || {}
                const nics = Object.entries(nicAll).map(([name, nicConfig], index) => ({
                    key: index,
                    name,
                    type: (nicConfig as any).nic_type
                }))
                setNicList(nics)
                setNicCounter(nics.length)

                Object.entries(nicAll).forEach(([name, nicConfig], index) => {
                    const typedNic = nicConfig as any
                    form.setFieldsValue({
                        [`nic_name_${index}`]: name,
                        [`nic_type_${index}`]: typedNic.nic_type,
                        [`nic_ip_${index}`]: typedNic.ip4_addr,
                        [`nic_ip6_${index}`]: typedNic.ip6_addr,
                    })
                })
            } else {
                message.error(result.msg || '加载虚拟机详情失败')
            }
        } catch (error) {
            message.error('加载虚拟机详情失败')
            onCancel()
        } finally {
            setLoading(false)
        }
    }


    const isFieldDisabled = (fieldName: string) => {
        if (!hostConfig) return false
        const banList = isEditMode ? hostConfig.ban_edit : hostConfig.ban_init
        return banList && banList.includes(fieldName)
    }

    const handleAddNic = () => {
        if (userQuota) {
            const currentNatIps = nicList.filter(n => n.type === 'nat').length
            const currentPubIps = nicList.filter(n => n.type === 'pub').length
            const availableNatIps = userQuota.quota_nat_ips - userQuota.used_nat_ips
            const availablePubIps = userQuota.quota_pub_ips - userQuota.used_pub_ips

            if (currentNatIps >= availableNatIps && currentPubIps >= availablePubIps) {
                message.warning('IP配额已用完')
                return
            }

            let nextType = 'nat'
            if (currentNatIps >= availableNatIps) nextType = 'pub'

            const newNic = { key: nicCounter, name: `ethernet${nicCounter}`, type: nextType }
            setNicList([...nicList, newNic])
            
            setTimeout(() => {
                form.setFieldsValue({
                    [`nic_name_${nicCounter}`]: `ethernet${nicCounter}`,
                    [`nic_type_${nicCounter}`]: nextType
                })
            }, 0)
        } else {
            setNicList([...nicList, { key: nicCounter, name: `ethernet${nicCounter}`, type: 'nat' }])
        }
        setNicCounter(nicCounter + 1)
    }

    const handleRemoveNic = (key: number) => {
        setNicList(nicList.filter(n => n.key !== key))
    }

    const processSubmit = async (values: any) => {
        try {
            const targetHost = isEditMode ? hostName : (values.host_name || selectedHost)
            if (!targetHost) {
                message.error('请选择主机')
                return
            }

            const prefix = hostConfig?.filter_name || ''
            // Only add prefix if it's NOT edit mode and prefix isn't already there
            const fullUuid = isEditMode ? vmUuid! : (prefix + values.vm_uuid_suffix)

            const nicAll: Record<string, any> = {}
            if (!isEditMode) {
                nicList.forEach(nic => {
                    const nicName = values[`nic_name_${nic.key}`] || nic.name
                    nicAll[nicName] = {
                        nic_type: values[`nic_type_${nic.key}`] || 'nat',
                        ip4_addr: values[`nic_ip_${nic.key}`] || '',
                        ip6_addr: values[`nic_ip6_${nic.key}`] || ''
                    }
                })
            }

            const vmData: Record<string, any> = {
                vm_uuid: fullUuid,
                vc_port: values.vc_port,
                cpu_num: values.cpu_num,
                cpu_per: values.cpu_per,
                mem_num: values.mem_num,
                hdd_num: values.hdd_num,
                hdd_iop: values.hdd_iop,
                gpu_id: values.gpu_id,
                gpu_num: values.gpu_id ? 1 : 0,
                gpu_mem: values.gpu_mem,
                gpu_mdev: values.gpu_mdev,
                gpu_remark: values.gpu_remark,
                usb_vid: values.usb_vid,
                usb_pid: values.usb_pid,
                usb_remark: values.usb_remark,
                speed_u: values.speed_u,
                speed_d: values.speed_d,
                nat_num: values.nat_num,
                flu_num: values.flu_num,
                flu_rst: [
                    values.flu_rst_day, 
                    values.flu_rst_limit, 
                    values.flu_rst_time || Math.floor(Date.now() / 1000)
                ],
                web_num: values.web_num,
            }

            // 创建模式发送所有字段，编辑模式根据权限选择性发送
            if (!isEditMode) {
                vmData.os_name = values.os_name
                vmData.os_pass = values.os_pass
                vmData.vc_pass = values.vc_pass
                vmData.nic_all = nicAll
            } else {
                // 编辑模式：有权限则发送用户修改值，无权限不发送（后端从旧配置复制）
                if (canEditSys) vmData.os_name = values.os_name
                if (canEditPwd) vmData.os_pass = values.os_pass
                if (canEditVnc) vmData.vc_pass = values.vc_pass
                // 编辑模式不发送nic_all，网卡管理已移除
            }

            if (isEditMode) {
                const result = await api.updateVM(targetHost, vmUuid!, vmData)
                if (result.code === 200) {
                    message.success('更新成功')
                    setSaveConfirmVisible(false)
                    onSuccess()
                } else {
                    message.error(result.msg || '更新失败')
                }
            } else {
                const hide = message.loading('创建中...', 0)
                try {
                    const result = await api.createVM(targetHost, vmData as any)
                    hide()
                    if (result.code === 200) {
                        message.success('创建成功')
                        onSuccess()
                    } else {
                        message.error(result.msg || '创建失败')
                    }
                } catch (error) {
                    hide()
                    throw error
                }
            }
        } catch (error) {
            message.error('操作失败')
        }
    }

    const handleSubmit = async (values: any) => {
        if (isEditMode) {
            setPendingValues(values)
            setSaveConfirmVisible(true)
        } else {
        await processSubmit(values)
        }
    }

    const sectionTitleStyle: React.CSSProperties = {
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        marginBottom: 24,
        fontSize: 16,
        fontWeight: 600
    }

    const resetForm = async () => {
        form.resetFields()
        setNicList([])
        
        if (hostName) {
            setSelectedHost(hostName)
            form.setFieldsValue({ host_name: hostName })
            await loadHostData(hostName)
        } else {
            setSelectedHost('')
            setHostImages({})
            setGpuList({})
            setPciDeviceList({})
            setUsbDeviceList({})
        }

        form.setFieldsValue({
            vm_uuid_suffix: generateRandomString(8),
            os_pass: generateRandomString(8),
            vc_pass: generateRandomString(8),
            vc_port: generateRandomVncPort(),
            cpu_num: 2,
            cpu_per: 100,
            mem_num: 2048,
            hdd_num: 20480,
            hdd_iop: 1000,
            gpu_id: '',
            gpu_num: 0,
            gpu_mem: 128,
            gpu_mdev: '',
            gpu_remark: '',
            usb_vid: '',
            usb_pid: '',
            usb_remark: '',
            speed_u: 100,
            speed_d: 100,
            flu_num: 102400,
            flu_rst_day: 31,
            flu_rst_limit: 10,
            flu_rst_time: Math.floor(Date.now() / 1000),
            nat_num: 100,
            web_num: 100,
        })

        if (userQuota) {
            const availableNatIps = userQuota.quota_nat_ips - userQuota.used_nat_ips
            const availablePubIps = userQuota.quota_pub_ips - userQuota.used_pub_ips
            let defaultType = 'nat'
            if (availableNatIps <= 0 && availablePubIps > 0) defaultType = 'pub'
            
            if (availableNatIps > 0 || availablePubIps > 0) {
                const initialNic = { key: 0, name: 'ethernet0', type: defaultType }
                setNicList([initialNic])
                setNicCounter(1)
                form.setFieldsValue({
                    nic_name_0: 'ethernet0',
                    nic_type_0: defaultType
                })
            }
        } else {
            setNicList([{ key: 0, name: 'ethernet0', type: 'nat' }])
            setNicCounter(1)
            form.setFieldsValue({ nic_name_0: 'ethernet0', nic_type_0: 'nat' })
        }
    }

    return (
        <>
            <Modal
                title={
                    <div className="flex items-center gap-2">
                        <DesktopOutlined className="text-purple-600" />
                        <span>{isEditMode ? '编辑虚拟机' : '创建虚拟机'}</span>
                    </div>
                }
                open={open}
                onCancel={onCancel}
                onOk={() => form.submit()}
                width={900}
                maskClosable={false}
                confirmLoading={loading}
                styles={{ body: { padding: '24px 0 0 0' } }}
            >
                <Form form={form} layout="vertical" onFinish={handleSubmit} style={{ maxHeight: '70vh', overflowY: 'auto', padding: '0 24px' }}>
                    {!isEditMode && !hostName && (
                        <Form.Item name="host_name" label="选择主机" rules={[{ required: true }]}>
                            <Select 
                                onChange={(val) => {
                                    setSelectedHost(val)
                                    loadHostData(val)
                                }}
                                placeholder="请选择部署主机"
                            >
                                {Object.keys(availableHosts)
                                    .filter(h => availableHosts[h]?.enabled !== false)
                                    .map(h => (
                                        <Select.Option key={h} value={h}>{h}</Select.Option>
                                    ))}
                            </Select>
                        </Form.Item>
                    )}

                    <div className="modal-section">
                        <div style={sectionTitleStyle}>
                            <div className="w-8 h-8 rounded-lg section-icon-bg-purple flex items-center justify-center">
                                <DesktopOutlined />
                            </div>
                            <span>基本信息</span>
                        </div>

                        <Row gutter={24}>
                            <Col span={12}>
                                <Form.Item 
                                    label="虚拟机UUID" 
                                    required
                                >
                                    <Space.Compact style={{ width: '100%' }}>
                                        <Form.Item
                                            name="vm_uuid_suffix"
                                            noStyle
                                            rules={[{ required: true }]}
                                        >
                                            <Input 
                                                addonBefore={hostConfig?.filter_name} 
                                                disabled={isEditMode}
                                                placeholder="唯一标识符"
                                            />
                                        </Form.Item>
                                        {!isEditMode && (
                                            <Button 
                                                htmlType="button"
                                                icon={<ReloadOutlined />} 
                                                onClick={() => form.setFieldValue('vm_uuid_suffix', generateRandomString(8))}
                                                title="随机生成UUID"
                                            />
                                        )}
                                    </Space.Compact>
                                </Form.Item>
                            </Col>
                            <Col span={12}>
                                <Form.Item name="os_name" label="操作系统" rules={[{ required: !isEditMode || canEditSys }]}>
                                    <Select 
                                        placeholder={isEditMode && !canEditSys ? '无权限修改' : '选择系统镜像'}
                                        disabled={isEditMode && !canEditSys}
                                        getPopupContainer={triggerNode => triggerNode.parentNode}
                                        onChange={(val) => {
                                            if (hostImages) {
                                                const entry = Object.entries(hostImages).find(([_, [img]]) => img === val)
                                                if (entry) {
                                                    // entry is [osName, [imgFile, minDisk]]
                                                    const minDisk = entry[1][1] || 0
                                                    setSelectedOsMinDisk(minDisk)
                                                }
                                            }
                                    }}
                                    >
                                        {Object.entries(hostImages).map(([name, [file]]) => (
                                            <Select.Option key={file} value={file}>{name}</Select.Option>
                                        ))}
                                    </Select>
                                </Form.Item>
                            </Col>
                        </Row>
                        
                        <Row gutter={24}>
                            <Col span={8}>
                                <Form.Item label="系统密码">
                                    <Space.Compact style={{ width: '100%' }}>
                                        <Form.Item name="os_pass" noStyle>
                                            <Input.Password 
                                                placeholder={isEditMode && !canEditPwd ? '无权限查看/修改' : '系统登录密码'}
                                                disabled={isEditMode && !canEditPwd}
                                            />
                                        </Form.Item>
                                        <Button 
                                            htmlType="button"
                                            icon={<ReloadOutlined />} 
                                            onClick={() => form.setFieldValue('os_pass', generateRandomString(8))}
                                            title="随机生成密码"
                                            disabled={isEditMode && !canEditPwd}
                                        />
                                    </Space.Compact>
                                </Form.Item>
                            </Col>
                            <Col span={8}>
                                <Form.Item label="VNC密码">
                                    <Space.Compact style={{ width: '100%' }}>
                                        <Form.Item name="vc_pass" noStyle>
                                            <Input.Password 
                                                placeholder={isEditMode && !canEditVnc ? '无权限查看/修改' : 'VNC连接密码'}
                                                disabled={isEditMode && !canEditVnc}
                                            />
                                        </Form.Item>
                                        <Button 
                                            htmlType="button"
                                            icon={<ReloadOutlined />} 
                                            onClick={() => form.setFieldValue('vc_pass', generateRandomString(8))}
                                            title="随机生成密码"
                                            disabled={isEditMode && !canEditVnc}
                                        />
                                    </Space.Compact>
                                </Form.Item>
                            </Col>
                            <Col span={8}>
                                <Form.Item label="VNC端口">
                                    <Space.Compact style={{ width: '100%' }}>
                                        <Form.Item name="vc_port" noStyle>
                                            <InputNumber style={{ width: '100%' }} min={5900} max={6999} />
                                        </Form.Item>
                                        <Button 
                                            htmlType="button"
                                            icon={<ReloadOutlined />} 
                                            onClick={() => form.setFieldValue('vc_port', generateRandomVncPort())}
                                            title="随机生成端口"
                                        />
                                    </Space.Compact>
                                </Form.Item>
                            </Col>
                        </Row>
                    </div>

                    <div className="modal-section">
                        <div style={sectionTitleStyle}>
                            <div className="w-8 h-8 rounded-lg section-icon-bg-orange flex items-center justify-center">
                                <ThunderboltOutlined />
                            </div>
                            <span>资源配置</span>
                        </div>

                        <Row gutter={24}>
                            <Col span={12}>
                                {renderResourceInput(
                                    'cpu_num', 'CPU核心', 1, isAdmin ? 128 : (userQuota?.quota_cpu || 4), 1, '核',
                                    isFieldDisabled('cpu_num'), userQuota?.used_cpu || 0, userQuota?.quota_cpu || 0, true
                                )}
                            </Col>
                            <Col span={12}>
                                {renderResourceInput(
                                    'cpu_per', '最大可用率', 0, 100, 1, '%',
                                    isFieldDisabled('cpu_per')
                                )}
                            </Col>
                            <Col span={12}>
                                {renderResourceInput(
                                    'mem_num', '内存', 512, isAdmin ? 131072 : (userQuota?.quota_ram || 4096), 512, 'MB',
                                    isFieldDisabled('mem_num'), userQuota?.used_ram || 0, userQuota?.quota_ram || 0, true
                                )}
                            </Col>
                            <Col span={12}>
                                {renderResourceInput(
                                    'hdd_num', '硬盘', selectedOsMinDisk * 1024 || 10240, isAdmin ? 10485760 : (userQuota?.quota_ssd || 51200), 1024, 'MB',
                                    isFieldDisabled('hdd_num'), userQuota?.used_ssd || 0, userQuota?.quota_ssd || 0, true
                                )}
                            </Col>
                            <Col span={12}>
                                {renderResourceInput(
                                    'hdd_iop', '硬盘速率', 100, 50000, 100, 'IOPS',
                                    isFieldDisabled('hdd_iop')
                                )}
                            </Col>
                            <Col span={12}>
                                {renderResourceInput(
                                    'gpu_mem', '显存', 0, isAdmin ? 16384 : 128, 128, 'MB',
                                    isFieldDisabled('gpu_mem')
                                )}
                            </Col>
                        </Row>
                    </div>

                    <div className="modal-section">
                        <div style={sectionTitleStyle}>
                            <div className="w-8 h-8 rounded-lg section-icon-bg-red flex items-center justify-center">
                                <DesktopOutlined />
                            </div>
                            <span>PCI配置</span>
                        </div>
                        <Row gutter={24}>
                            <Col span={12}>
                                <Form.Item label="PCI直通" name="gpu_id">
                                    <Select allowClear placeholder="选择PCI设备" onChange={(val) => {
                                        if (val && pciDeviceList[val]) {
                                            const dev = pciDeviceList[val]
                                            form.setFieldsValue({
                                                gpu_mdev: dev.gpu_mdev || '',
                                                gpu_remark: dev.gpu_hint || ''
                                            })
                                        } else {
                                            form.setFieldsValue({ gpu_mdev: '', gpu_remark: '' })
                                        }
                                    }}>
                                        <Select.Option value="">无PCI直通</Select.Option>
                                        {Object.entries(pciDeviceList).map(([key, dev]: [string, any]) => (
                                            <Select.Option key={key} value={key}>{key} - {dev.gpu_hint || dev.gpu_uuid || ''}</Select.Option>
                                        ))}
                                        {Object.keys(pciDeviceList).length === 0 && Object.entries(gpuList).map(([id, name]) => (
                                            <Select.Option key={id} value={id}>{id} - {name}</Select.Option>
                                        ))}
                                    </Select>
                                </Form.Item>
                            </Col>
                            <Col span={12}>
                                <Form.Item label="MDEV / 备注">
                                    <Space.Compact style={{ width: '100%' }}>
                                        <Form.Item name="gpu_mdev" noStyle>
                                            <Input placeholder="vGPU/MDEV UUID" style={{ width: '60%' }} />
                                        </Form.Item>
                                        <Form.Item name="gpu_remark" noStyle>
                                            <Input placeholder="PCI备注信息" style={{ width: '40%' }} />
                                        </Form.Item>
                                    </Space.Compact>
                                </Form.Item>
                            </Col>
                        </Row>
                    </div>

                    <div className="modal-section">
                        <div style={sectionTitleStyle}>
                            <div className="w-8 h-8 rounded-lg section-icon-bg-blue flex items-center justify-center">
                                <ThunderboltOutlined />
                            </div>
                            <span>USB配置</span>
                        </div>
                        <Row gutter={24}>
                            <Col span={12}>
                                <Form.Item label="USB设备" name="usb_device_key">
                                    <Select allowClear placeholder="选择USB设备" onChange={(val) => {
                                        if (val && usbDeviceList[val]) {
                                            const dev = usbDeviceList[val]
                                            form.setFieldsValue({
                                                usb_vid: dev.vid_uuid || '',
                                                usb_pid: dev.pid_uuid || '',
                                                usb_remark: dev.usb_hint || ''
                                            })
                                        } else {
                                            form.setFieldsValue({ usb_vid: '', usb_pid: '', usb_remark: '' })
                                        }
                                    }}>
                                        <Select.Option value="">无USB直通</Select.Option>
                                        {Object.entries(usbDeviceList).map(([key, dev]: [string, any]) => (
                                            <Select.Option key={key} value={key}>{dev.usb_hint || `${dev.vid_uuid}:${dev.pid_uuid}`}</Select.Option>
                                        ))}
                                    </Select>
                                </Form.Item>
                            </Col>
                            <Col span={12}>
                                <Form.Item label="VID / PID">
                                    <Space.Compact style={{ width: '100%' }}>
                                        <Form.Item name="usb_vid" noStyle>
                                            <Input placeholder="VID (ex: 0403)" style={{ width: '50%' }} />
                                        </Form.Item>
                                        <Form.Item name="usb_pid" noStyle>
                                            <Input placeholder="PID (ex: 6001)" style={{ width: '50%' }} />
                                        </Form.Item>
                                    </Space.Compact>
                                </Form.Item>
                            </Col>
                        </Row>
                        <Row gutter={24}>
                            <Col span={12}>
                                <Form.Item label="备注" name="usb_remark">
                                    <Input placeholder="USB备注信息" />
                                </Form.Item>
                            </Col>
                        </Row>
                    </div>

                    <div className="modal-section">
                        <div style={sectionTitleStyle}>
                            <div className="w-8 h-8 rounded-lg section-icon-bg-green flex items-center justify-center">
                                <GlobalOutlined />
                            </div>
                            <span>网络与配额</span>
                        </div>

                        <Row gutter={24}>
                            <Col span={12}>
                                {renderResourceInput(
                                    'speed_u', '上传带宽', 1, isAdmin ? 10000 : (userQuota?.quota_upload_bw || 100), 1, 'Mbps',
                                    false, userQuota?.used_upload_bw || 0, userQuota?.quota_upload_bw || 0, true
                                )}
                            </Col>
                            <Col span={12}>
                                {renderResourceInput(
                                    'speed_d', '下载带宽', 1, isAdmin ? 10000 : (userQuota?.quota_download_bw || 100), 1, 'Mbps',
                                    false, userQuota?.used_download_bw || 0, userQuota?.quota_download_bw || 0, true
                                )}
                            </Col>
                        </Row>
                        <Row gutter={24}>
                            <Col span={12}>
                                {renderResourceInput(
                                    'flu_num', '流量限制', 0, 1024000, 1024, 'MB',
                                    isFieldDisabled('flu_num'), userQuota?.used_traffic || 0, userQuota?.quota_traffic || 0, true
                                )}
                            </Col>
                            <Col span={6}>
                                <Form.Item label="重置时间" name="flu_rst_day" style={{ marginBottom: 24 }}>
                                    <InputNumber min={1} max={365} style={{ width: '100%' }} addonAfter="天" />
                                </Form.Item>
                            </Col>
                            <Col span={6}>
                                <Form.Item label="达标限速" name="flu_rst_limit" style={{ marginBottom: 24 }}>
                                    <InputNumber min={1} max={1000} style={{ width: '100%' }} addonAfter="Mbps" />
                                </Form.Item>
                            </Col>
                        </Row>

                        <Divider style={{ margin: '12px 0 24px 0' }} />

                        <Row gutter={24}>
                            <Col span={12}>
                                {renderResourceInput(
                                    'nat_num', 'NAT端口数', 0, isAdmin ? 1000 : (userQuota?.quota_nat || 100), 1, '个',
                                    isFieldDisabled('nat_num'), userQuota?.used_nat || 0, userQuota?.quota_nat || 0, true
                                )}
                            </Col>
                            <Col span={12}>
                                {renderResourceInput(
                                    'web_num', 'Web代理数', 0, isAdmin ? 1000 : (userQuota?.quota_web || 10), 1, '个',
                                    isFieldDisabled('web_num'), userQuota?.used_web || 0, userQuota?.quota_web || 0, true
                                )}
                            </Col>
                        </Row>
                    </div>

                    {/* 编辑模式下隐藏网卡配置 */}
                    {!isEditMode && (
                    <div className="modal-section">
                        <div style={sectionTitleStyle}>
                            <div className="w-8 h-8 rounded-lg section-icon-bg-blue flex items-center justify-center">
                                <RadarChartOutlined />
                            </div>
                            <span>网卡配置</span>
                        </div>

                        {nicList.map((nic) => (
                            <Space.Compact key={nic.key} style={{ width: '100%', marginBottom: 12 }}>
                                <Form.Item name={`nic_name_${nic.key}`} initialValue={nic.name} noStyle>
                                    <Input style={{ width: 120 }} disabled />
                                </Form.Item>
                                <Form.Item name={`nic_type_${nic.key}`} initialValue="nat" noStyle>
                                    <Select style={{ width: 100 }}>
                                        <Select.Option value="nat">内网</Select.Option>
                                        <Select.Option value="pub">公网</Select.Option>
                                    </Select>
                                </Form.Item>
                                <Form.Item name={`nic_ip_${nic.key}`} noStyle>
                                    <Input placeholder="IPv4 (可选)" style={{ margin: '0 10px' }} />
                                </Form.Item>
                                <Form.Item name={`nic_ip6_${nic.key}`} noStyle>
                                    <Input placeholder="IPv6 (可选)" style={{ margin: '0 10px' }} />
                                </Form.Item>
                                <Button danger icon={<DeleteOutlined />} onClick={() => handleRemoveNic(nic.key)} />
                            </Space.Compact>
                        ))}
                        
                        <Button type="dashed" onClick={handleAddNic} block icon={<PlusOutlined />}>
                            添加网卡
                        </Button>
                    </div>
                    )}
                </Form>
            </Modal>

            <Modal
                title="确认保存"
                open={saveConfirmVisible}
                onCancel={() => setSaveConfirmVisible(false)}
                onOk={() => processSubmit(pendingValues)}
                okText="确认保存"
                cancelText="取消"
            >
                <Alert
                    message="保存确认"
                    description="确定要保存对虚拟机的修改吗？部分修改可能需要重启虚拟机才能生效。"
                    type="warning"
                    showIcon
                />
            </Modal>
        </>
    )
}

export default DockCreateModal
