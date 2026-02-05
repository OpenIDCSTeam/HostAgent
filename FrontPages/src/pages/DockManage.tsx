import {useEffect, useState} from 'react'
import {useNavigate, useParams} from 'react-router-dom'
import {
    Card,
    Button,
    Space,
    Tag,
    Modal,
    Form,
    Input,
    Select,
    InputNumber,
    message,
    Spin,
    Empty,
    Row,
    Col,
    Tooltip,
    Checkbox,
    Alert,
    Typography,
    Slider,
} from 'antd'
import {
    PlusOutlined,
    ReloadOutlined,
    ArrowLeftOutlined,
    RadarChartOutlined,
    DesktopOutlined,
    PoweroffOutlined,
    EditOutlined,
    DeleteOutlined,
    EyeOutlined,
    PlayCircleOutlined,
    PauseCircleOutlined,
    RedoOutlined,
    ThunderboltOutlined,
    InfoCircleOutlined
} from '@ant-design/icons'
import api, {getHosts} from '@/utils/apis.ts'
import {useUserStore} from '@/utils/data.ts'

const {Text, Title} = Typography

/**
 * 虚拟机配置接口
 */
interface VMConfig {
    vm_uuid: string
    os_name: string
    os_pass?: string
    vc_pass?: string
    vc_port?: number
    cpu_num: number
    mem_num: number
    hdd_num: number
    gpu_num?: number
    gpu_mem?: number
    speed_u?: number
    speed_d?: number
    nat_num?: number
    flu_num?: number
    web_num?: number
    nic_all: Record<string, NicConfig>
}

/**
 * 网卡配置接口
 */
interface NicConfig {
    nic_type: string
    ip4_addr?: string
    ip6_addr?: string
    mac_addr?: string
}

/**
 * 虚拟机状态接口
 */
interface VMStatus {
    ac_status: string
}

/**
 * 虚拟机数据接口
 */
interface VM {
    config: VMConfig
    status: VMStatus[]
}

/**
 * 主机配置接口
 */
interface HostConfig {
    filter_name: string
    system_maps: Record<string, [string, number]>
    images_maps: Record<string, string>
    server_type: string
    ban_init: string[]
    ban_edit: string[]
    messages: string[]
}

/**
 * 用户配额接口
 */
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

/**
 * 虚拟机列表页面
 */
function DockManage() {
    const navigate = useNavigate()
    const {hostName} = useParams<{ hostName: string }>()
    const {user} = useUserStore() // 获取用户信息
    const isAdmin = user?.is_admin || false // 判断是否为管理员
    const [vms, setVMs] = useState<Record<string, VM>>({})
    const [loading, setLoading] = useState(false)
    const [modalVisible, setModalVisible] = useState(false)
    const [powerModalVisible, setPowerModalVisible] = useState(false)
    const [editMode, setEditMode] = useState<'add' | 'edit'>('add')
    const [currentVmUuid, setCurrentVmUuid] = useState('')
    const [hostConfig, setHostConfig] = useState<HostConfig | null>(null)
    const [userQuota, setUserQuota] = useState<UserQuota | null>(null)
    const [form] = Form.useForm()
    const [nicList, setNicList] = useState<Array<{ key: number; name: string; type: string }>>([])
    const [nicCounter, setNicCounter] = useState(0)
    const [selectedOsMinDisk, setSelectedOsMinDisk] = useState(0)
    const [availableHosts, setAvailableHosts] = useState<Record<string, any>>({})
    const [selectedHost, setSelectedHost] = useState('')
    const [hostImages, setHostImages] = useState<Record<string, [string, number]>>({})


    // 编辑保存确认模态框状态
    const [saveConfirmModalVisible, setSaveConfirmModalVisible] = useState(false)
    const [forceShutdownConfirmed, setForceShutdownConfirmed] = useState(false)
    const [pendingSubmitValues, setPendingSubmitValues] = useState<any>(null)

    // 状态文字映射
    const statusMap: Record<string, { text: string; color: string; className?: string; pulse?: boolean }> = {
        STOPPED: {
            text: '已停止',
            color: 'default',
            className: 'bg-gray-100 dark:bg-gray-700/40 text-gray-700 dark:text-gray-300 border-gray-300 dark:border-gray-600'
        },
        STARTED: {
            text: '运行中',
            color: 'success',
            className: 'bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300 border-green-300 dark:border-green-600',
            pulse: true
        },
        SUSPEND: {
            text: '已暂停',
            color: 'warning',
            className: 'bg-yellow-100 dark:bg-yellow-900/40 text-yellow-700 dark:text-yellow-300 border-yellow-300 dark:border-yellow-600'
        },
        ON_STOP: {
            text: '停止中',
            color: 'processing',
            className: 'bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 border-blue-300 dark:border-blue-600'
        },
        ON_OPEN: {
            text: '启动中',
            color: 'processing',
            className: 'bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 border-blue-300 dark:border-blue-600'
        },
        CRASHED: {
            text: '已崩溃',
            color: 'error',
            className: 'bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300 border-red-300 dark:border-red-600'
        },
        UNKNOWN: {
            text: '未知',
            color: 'default',
            className: 'bg-gray-100 dark:bg-gray-700/40 text-gray-700 dark:text-gray-300 border-gray-300 dark:border-gray-600'
        },
    }

    /**
     * 加载主机信息（获取system_maps等配置）
     */
    const loadHostInfo = async () => {
        if (!hostName) return
        try {
            const result = await api.get(`/api/client/os-images/${hostName}`)
            if (result.code === 200) {
                setHostConfig(result.data)
            }
        } catch (error) {
            console.error('加载主机信息失败:', error)
        }
    }

    /**
     * 加载用户配额信息
     */
    const loadUserQuota = async () => {
        try {
            const result = await api.get('/api/users/current')
            if (result.code === 200) {
                setUserQuota(result.data)
            }
        } catch (error) {
            console.error('获取用户配额失败:', error)
        }
    }

    /**
     * 加载可用主机列表
     */
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

    /**
     * 加载指定主机的系统镜像
     */
    const loadHostImages = async (host: string) => {
        if (!host) {
            setHostImages({})
            return
        }
        try {
            const result = await api.get(`/api/client/os-images/${host}`)
            if (result.code === 200 && result.data) {
                setHostConfig(result.data)
                setHostImages(result.data.system_maps || {})
            }
        } catch (error) {
            console.error('加载系统镜像失败:', error)
            setHostImages({})
        }
    }

    /**
     * 加载虚拟机列表
     */
    const loadVMs = async () => {
        try {
            setLoading(true)
            let allVMs: Record<string, VM> = {}
            const pathname = window.location.pathname

            if (hostName) {
                // 指定了主机：获取该主机的虚拟机
                const result = await api.get(`/api/client/detail/${hostName}`)
                if (result.code === 200) {
                    allVMs = result.data || {}
                }
            } else if (pathname.startsWith('/user/')) {
                // 用户视图：获取当前用户的虚拟机
                // 注意：这里暂时返回所有虚拟机，因为我们没有虚拟机的所有者信息
                // 后续可以根据实际情况修改为获取当前用户的虚拟机
                const hostsRes = await getHosts()
                if (hostsRes.code === 200 && hostsRes.data) {
                    const hosts = Object.keys(hostsRes.data)

                    await Promise.all(hosts.map(async (host) => {
                        try {
                            const vmsRes = await api.get(`/api/client/detail/${host}`)
                            if (vmsRes.code === 200 && vmsRes.data) {
                                // 将所有主机的虚拟机合并，使用 `${host}-${uuid}` 作为唯一键
                                Object.entries(vmsRes.data).forEach(([uuid, vm]) => {
                                    allVMs[`${host}-${uuid}`] = vm as VM
                                })
                            }
                        } catch (err) {
                            console.error(`获取主机 ${host} 的虚拟机失败`, err)
                        }
                    }))
                }
            } else {
                // 系统视图：获取所有主机的虚拟机
                const hostsRes = await getHosts()
                if (hostsRes.code === 200 && hostsRes.data) {
                    const hosts = Object.keys(hostsRes.data)

                    await Promise.all(hosts.map(async (host) => {
                        try {
                            const vmsRes = await api.get(`/api/client/detail/${host}`)
                            if (vmsRes.code === 200 && vmsRes.data) {
                                // 将所有主机的虚拟机合并，使用 `${host}-${uuid}` 作为唯一键
                                Object.entries(vmsRes.data).forEach(([uuid, vm]) => {
                                    allVMs[`${host}-${uuid}`] = vm as VM
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

    /**
     * 扫描虚拟机
     */
    const handleScan = async () => {
        if (!hostName) return
        try {
            const hide = message.loading('正在扫描虚拟机...', 0)
            const result = await api.post(`/api/client/scaner/${hostName}`, {})
            hide()
            if (result.code === 200) {
                const {scanned = 0, added = 0} = result.data || {}
                message.success(`扫描完成！扫描到 ${scanned} 台虚拟机，新增 ${added} 台`)
                loadVMs()
            } else {
                message.error(result.msg || '扫描失败')
            }
        } catch (error) {
            message.error('扫描虚拟机失败')
        }
    }

    useEffect(() => {
        loadHostInfo()
        loadUserQuota()
        loadVMs()
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [hostName])

    /**
     * 生成随机字符串（包含字母和数字）
     */
    const generateRandomString = (length: number): string => {
        const letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
        const numbers = '0123456789'

        // 确保至少包含一个字母和一个数字
        let result = ''
        result += letters.charAt(Math.floor(Math.random() * letters.length))
        result += numbers.charAt(Math.floor(Math.random() * numbers.length))

        const allChars = letters + numbers
        for (let i = result.length; i < length; i++) {
            result += allChars.charAt(Math.floor(Math.random() * allChars.length))
        }
        return result.split('').sort(() => Math.random() - 0.5).join('')
    }

    /**
     * 生成随机VNC端口
     */
    const generateRandomVncPort = (): number => {
        return Math.floor(Math.random() * (6999 - 5900 + 1)) + 5900
    }

    /**
     * 密码复杂度验证
     */
    const validatePassword = (_: any, value: string) => {
        if (!value) {
            return Promise.resolve() // 允许空密码（如果不强制）
        }
        if (value.length < 8) {
            return Promise.reject(new Error('密码长度至少8位'))
        }
        const hasLetter = /[a-zA-Z]/.test(value)
        const hasNumber = /[0-9]/.test(value)
        if (!hasLetter || !hasNumber) {
            return Promise.reject(new Error('密码必须包含字母和数字'))
        }
        return Promise.resolve()
    }

    /**
     * 检查字段是否被禁用
     */
    const isFieldDisabled = (fieldName: string) => {
        if (!hostConfig) return false
        const banList = editMode === 'add' ? hostConfig.ban_init : hostConfig.ban_edit
        return banList && banList.includes(fieldName)
    }

    /**
     * 检查资源配额
     */
    const checkResourceQuota = (): { canCreate: boolean; errors: string[] } => {
        if (!userQuota) return {canCreate: true, errors: []}
        const errors: string[] = []
        if (userQuota.quota_cpu <= 0 || userQuota.used_cpu >= userQuota.quota_cpu) {
            errors.push('CPU配额不足')
        }
        if (userQuota.quota_ram <= 0 || userQuota.used_ram >= userQuota.quota_ram) {
            errors.push('内存配额不足')
        }
        if (userQuota.quota_ssd <= 0 || userQuota.used_ssd >= userQuota.quota_ssd) {
            errors.push('硬盘配额不足')
        }
        const availableNatIps = userQuota.quota_nat_ips - userQuota.used_nat_ips
        const availablePubIps = userQuota.quota_pub_ips - userQuota.used_pub_ips
        if (availableNatIps <= 0 && availablePubIps <= 0) {
            errors.push('无可用IP配额')
        }
        return {canCreate: errors.length === 0, errors}
    }

    /**
     * 打开创建虚拟机对话框
     */
    const handleOpenCreate = async () => {
        const quotaCheck = checkResourceQuota()
        if (!quotaCheck.canCreate) {
            Modal.error({
                title: '配额不足',
                content: `无法创建虚拟机：${quotaCheck.errors.join('，')}`,
            })
            return
        }

        // 加载可用主机列表
        await loadAvailableHosts()

        setEditMode('add')
        setForceShutdownConfirmed(false)
        form.resetFields()

        // 如果当前页面指定了主机，则默认选中该主机
        if (hostName) {
            setSelectedHost(hostName)
            form.setFieldsValue({ host_name: hostName })
            await loadHostImages(hostName)
        } else {
            setSelectedHost('')
            setHostImages({})
        }

        // 生成随机UUID和密码
        const randomUuid = generateRandomString(8)
        const randomPass = generateRandomString(8)
        const randomPort = generateRandomVncPort()

        form.setFieldsValue({
            vm_uuid_suffix: randomUuid,
            os_pass: randomPass,
            vc_pass: randomPass,
            vc_port: randomPort,
            cpu_num: 2,
            mem_num: 2048,
            hdd_num: 20480,
            gpu_num: 0,
            gpu_mem: 128,
            speed_u: 100,
            speed_d: 100,
            flu_num: 102400,
            nat_num: 100,
            web_num: 100,
        })

        // 自动根据配额添加默认网卡
        if (userQuota) {
            const availableNatIps = userQuota.quota_nat_ips - userQuota.used_nat_ips
            const availablePubIps = userQuota.quota_pub_ips - userQuota.used_pub_ips
            let defaultType = 'nat'
            if (availableNatIps <= 0 && availablePubIps > 0) {
                defaultType = 'pub'
            }
            setNicList([{key: 0, name: 'ethernet0', type: defaultType}])
            setNicCounter(1)
            form.setFieldsValue({
                nic_name_0: 'ethernet0',
                nic_type_0: defaultType
            })
        } else {
            setNicList([{key: 0, name: 'ethernet0', type: 'nat'}])
            setNicCounter(1)
        }

        setModalVisible(true)
    }

    /**
     * 打开编辑虚拟机对话框
     */
    const handleOpenEdit = async (uuid: string, targetHostName?: string) => {
        const currentHostName = targetHostName || hostName
        if (!currentHostName) return
        try {
            const result = await api.get(`/api/client/detail/${currentHostName}/${uuid}`)
            if (result.code === 200) {
                const vm = result.data
                const config = vm.config || {}

                setEditMode('edit')
                setForceShutdownConfirmed(false)
                setCurrentVmUuid(uuid)

                // 分离UUID前缀和后缀
                const prefix = hostConfig?.filter_name || ''
                let suffix = uuid
                if (prefix && uuid.startsWith(prefix)) {
                    suffix = uuid.substring(prefix.length)
                }

                // 设置最小磁盘要求
                if (hostConfig?.system_maps && config.os_name) {
                    const entry = Object.values(hostConfig.system_maps).find(([img]) => img === config.os_name)
                    if (entry) {
                        setSelectedOsMinDisk(entry[1] || 0)
                    }
                }

                form.setFieldsValue({
                    vm_uuid_suffix: suffix,
                    os_name: config.os_name,
                    os_pass: config.os_pass,
                    vc_pass: config.vc_pass,
                    vc_port: config.vc_port,
                    cpu_num: config.cpu_num,
                    mem_num: config.mem_num,
                    hdd_num: config.hdd_num,
                    gpu_num: config.gpu_num,
                    gpu_mem: config.gpu_mem,
                    speed_u: config.speed_u,
                    speed_d: config.speed_d,
                    nat_num: config.nat_num,
                    flu_num: config.flu_num,
                    web_num: config.web_num,
                })

                // 加载网卡配置
                const nicAll = config.nic_all || {}
                const nics = Object.entries(nicAll).map(([name, nicConfig], index) => ({
                    key: index,
                    name,
                    type: (nicConfig as NicConfig).nic_type
                }))
                setNicList(nics as Array<{ key: number; name: string; type: string }>)
                setNicCounter(nics.length)

                // 设置网卡表单值
                Object.entries(nicAll).forEach(([name, nicConfig], index) => {
                    const typedNicConfig = nicConfig as NicConfig
                    form.setFieldsValue({
                        [`nic_name_${index}`]: name,
                        [`nic_type_${index}`]: typedNicConfig.nic_type,
                        [`nic_ip_${index}`]: typedNicConfig.ip4_addr,
                        [`nic_ip6_${index}`]: typedNicConfig.ip6_addr,
                    })
                })

                setModalVisible(true)
            }
        } catch (error) {
            message.error('加载虚拟机信息失败')
        }
    }

    /**
     * 添加网卡
     */
    const handleAddNic = () => {
        // 检查配额
        if (userQuota) {
            const currentNatIps = nicList.filter(n => n.type === 'nat').length
            const currentPubIps = nicList.filter(n => n.type === 'pub').length
            const availableNatIps = userQuota.quota_nat_ips - userQuota.used_nat_ips
            const availablePubIps = userQuota.quota_pub_ips - userQuota.used_pub_ips

            if (currentNatIps >= availableNatIps && currentPubIps >= availablePubIps) {
                message.warning('IP配额已用完，无法添加更多网卡')
                return
            }

            let nextType = 'nat'
            if (currentNatIps >= availableNatIps) nextType = 'pub'

            setNicList([...nicList, {key: nicCounter, name: `ethernet${nicCounter}`, type: nextType}])
            // 设置默认值
            setTimeout(() => {
                form.setFieldsValue({
                    [`nic_name_${nicCounter}`]: `ethernet${nicCounter}`,
                    [`nic_type_${nicCounter}`]: nextType
                })
            }, 0)
        } else {
            setNicList([...nicList, {key: nicCounter, name: `ethernet${nicCounter}`, type: 'nat'}])
        }
        setNicCounter(nicCounter + 1)
    }

    /**
     * 移除网卡
     */
    const handleRemoveNic = (key: number) => {
        setNicList(nicList.filter(nic => nic.key !== key))
    }

    /**
     * 提交虚拟机表单
     */
    const handleSubmit = async (values: any) => {
        // 创建模式下，使用选中的主机或表单中的主机
        const targetHost = editMode === 'add' ? (values.host_name || selectedHost) : hostName
        
        if (!targetHost) {
            message.error('请选择主机')
            return
        }

        // 编辑模式需要二次确认
        if (editMode === 'edit') {
            setPendingSubmitValues(values)
            setForceShutdownConfirmed(false)
            setSaveConfirmModalVisible(true)
            return
        }

        await processSubmit(values, targetHost)
    }

    /**
     * 处理实际的提交逻辑
     */
    const processSubmit = async (values: any, targetHost?: string) => {
        try {
            // 确定目标主机
            const submitHost = targetHost || hostName
            if (!submitHost) {
                message.error('请选择主机')
                return
            }

            // 构建完整UUID
            const prefix = hostConfig?.filter_name || ''
            const fullUuid = prefix + values.vm_uuid_suffix

            // 收集网卡配置
            const nicAll: Record<string, NicConfig> = {}
            nicList.forEach((nic) => {
                const nicName = values[`nic_name_${nic.key}`] || nic.name
                nicAll[nicName] = {
                    nic_type: values[`nic_type_${nic.key}`] || 'nat',
                    ip4_addr: values[`nic_ip_${nic.key}`] || '',
                    ip6_addr: values[`nic_ip6_${nic.key}`] || '',
                }
            })

            const vmData: VMConfig = {
                vm_uuid: fullUuid,
                os_name: values.os_name,
                os_pass: values.os_pass,
                vc_pass: values.vc_pass,
                vc_port: values.vc_port,
                cpu_num: values.cpu_num,
                mem_num: values.mem_num,
                hdd_num: values.hdd_num,
                gpu_num: values.gpu_num,
                gpu_mem: values.gpu_mem,
                speed_u: values.speed_u,
                speed_d: values.speed_d,
                nat_num: values.nat_num,
                flu_num: values.flu_num,
                web_num: values.web_num,
                nic_all: nicAll,
            }

            if (editMode === 'add') {
                // 先关闭模态框
                setModalVisible(false)
                // 再显示创建中消息
                const hide = message.loading('正在创建虚拟机...', 0)
                const result = await api.post(`/api/client/create/${submitHost}`, vmData)
                hide()
                if (result.code === 200) {
                    message.success('虚拟机创建成功')
                    loadVMs()
                } else {
                    message.error(result.msg || '创建失败')
                }
            } else {
                const result = await api.put(`/api/client/update/${submitHost}/${currentVmUuid}`, vmData)
                if (result.code === 200) {
                    message.success('虚拟机配置已保存')
                    setModalVisible(false)
                    setSaveConfirmModalVisible(false)
                    loadVMs()
                } else {
                    message.error(result.msg || '保存失败')
                }
            }
        } catch (error) {
            message.error('操作失败')
        }
    }

    /**
     * 确认保存编辑
     */
    const handleConfirmSave = () => {
        if (pendingSubmitValues) {
            processSubmit(pendingSubmitValues, hostName)
        }
    }

    // 保存当前操作的主机名
    const [currentHostName, setCurrentHostName] = useState<string>('')

    /**
     * 打开电源操作对话框
     */
    const handleOpenPower = (uuid: string, targetHostName?: string) => {
        setCurrentVmUuid(uuid)
        setCurrentHostName(targetHostName || hostName || '')
        setPowerModalVisible(true)
    }

    /**
     * 执行电源操作
     */
    const handlePowerAction = async (action: string) => {
        if (!currentHostName || !currentVmUuid) return

        setPowerModalVisible(false)

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
            const result = await api.post(`/api/client/powers/${currentHostName}/${currentVmUuid}`, {action})
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

    /**
     * 删除虚拟机
     */
    const handleDelete = (uuid: string, targetHostName?: string) => {
        const currentHostName = targetHostName || hostName
        Modal.confirm({
            title: '确认删除',
            content: (
                <div>
                    <p>此操作将永久删除虚拟机 "<strong style={{color: '#ff4d4f'}}>{uuid}</strong>" 且不可恢复</p>
                    <p style={{marginTop: 8, fontSize: 12, color: '#666'}}>请输入虚拟机名称以确认删除</p>
                </div>
            ),
            okText: '确认删除',
            okType: 'danger',
            cancelText: '取消',
            mask: false,
            onOk: async () => {
                if (!currentHostName) return
                try {
                    const hide = message.loading('正在删除虚拟机...', 0)
                    const result = await api.delete(`/api/client/delete/${currentHostName}/${uuid}`)
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

    /**
     * 打开VNC控制台
     */
    const handleOpenVnc = async (uuid: string, targetHostName?: string) => {
        const currentHostName = targetHostName || hostName
        if (!currentHostName) return
        try {
            const hide = message.loading('正在获取VNC控制台地址...', 0)
            const result = await api.get(`/api/client/remote/${currentHostName}/${uuid}`)
            hide()
            if (result.code === 200 && result.data) {
                window.open(result.data, `vnc_${uuid}`, 'width=1024,height=768')
            } else {
                message.error('无法获取VNC控制台地址')
            }
        } catch (error) {
            message.error('连接失败')
        }
    }

    /**
     * 格式化内存显示
     */
    const formatMemory = (mb?: number): string => {
        if (!mb) return '0 MB'
        if (mb >= 1024) return `${(mb / 1024).toFixed(1)} GB`
        return `${mb} MB`
    }

    /**
     * 格式化磁盘显示
     */
    const formatDisk = (mb?: number): string => {
        if (!mb) return '0 MB'
        if (mb >= 1024) return `${(mb / 1024).toFixed(1)} GB`
        return `${mb} MB`
    }

    /**
     * 渲染虚拟机卡片
     */
    const renderVMCard = (uuid: string, vm: VM, hostName?: string) => {
        const config = vm.config || {}
        const statusList = vm.status || []
        const firstStatus = statusList.length > 0 ? statusList[0] : {ac_status: 'UNKNOWN'}
        const powerStatus = firstStatus.ac_status || 'UNKNOWN'
        const statusInfo = statusMap[powerStatus] || statusMap.UNKNOWN

        const nicAll = config.nic_all || {}
        const firstNic = Object.values(nicAll)[0] || {}
        const ipv4 = firstNic.ip4_addr || '-'
        const ipv6 = firstNic.ip6_addr || '-'
        const macAddr = firstNic.mac_addr || '-'

        return (
            <Card
                key={uuid}
                hoverable
                className="glass-effect"
                style={{display: 'flex', flexDirection: 'column', width: '100%', height: '100%'}}
                styles={{body: {padding: 16, flex: 1, display: 'flex', flexDirection: 'column'}}}
                >
                    <div style={{marginBottom: 16}}>
                        <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start'}}>
                            <div style={{display: 'flex', gap: 12, alignItems: 'center'}}>
                                <div
                                    style={{
                                        width: 48,
                                        height: 48,
                                        background: 'linear-gradient(135deg, #9333ea 0%, #7e22ce 100%)',
                                        borderRadius: 8,
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        boxShadow: '0 2px 8px rgba(147, 51, 234, 0.3)',
                                    }}
                                >
                                    <DesktopOutlined style={{fontSize: 24, color: '#fff'}}/>
                                </div>
                                <div>
                                    <h3 className="text-gray-900 dark:text-white"
                                        style={{margin: 0, fontSize: 16, fontWeight: 600}}>{uuid}</h3>
                                    <p className="text-gray-700 dark:text-gray-300"
                                       style={{margin: 0, fontSize: 12}}>{config.os_name || '未知系统'}</p>
                                </div>
                            </div>
                            <Tag color={statusInfo.color} className={statusInfo.className}>{statusInfo.text}</Tag>
                        </div>
                        {hostName && (
                            <div style={{marginTop: 8}}>
                                <Tag color="blue">{hostName}</Tag>
                            </div>
                        )}
                    </div>

                    {/* 基础资源信息 */}
                    <Row gutter={[8, 8]} style={{marginBottom: 16}}>
                        <Col span={12}>
                            <div style={{fontSize: 12, color: 'var(--text-secondary)'}}>
                                CPU: <strong style={{color: 'var(--text-primary)'}}>{config.cpu_num || 0} 核</strong>
                            </div>
                        </Col>
                        <Col span={12}>
                            <div style={{fontSize: 12, color: 'var(--text-secondary)'}}>
                                内存: <strong
                                style={{color: 'var(--text-primary)'}}>{formatMemory(config.mem_num)}</strong>
                            </div>
                        </Col>
                        <Col span={12}>
                            <div style={{fontSize: 12, color: 'var(--text-secondary)'}}>
                                硬盘: <strong
                                style={{color: 'var(--text-primary)'}}>{formatDisk(config.hdd_num)}</strong>
                            </div>
                        </Col>
                        <Col span={12}>
                            <div style={{fontSize: 12, color: 'var(--text-secondary)'}}>
                                显存: <strong
                                style={{color: 'var(--text-primary)'}}>{formatMemory(config.gpu_mem)}</strong>
                            </div>
                        </Col>
                    </Row>

                    {/* 端口信息 */}
                    <div style={{padding: 12, background: 'var(--bg-tertiary)', borderRadius: 8, marginBottom: 16}}>
                        <Row gutter={[8, 8]}>
                            <Col span={12}>
                                <div style={{fontSize: 12, color: 'var(--text-secondary)'}}>
                                    NAT端口: <strong
                                    style={{color: 'var(--text-primary)'}}>{config.nat_num || 0}个</strong>
                                </div>
                            </Col>
                            <Col span={12}>
                                <div style={{fontSize: 12, color: 'var(--text-secondary)'}}>
                                    Web代理: <strong
                                    style={{color: 'var(--text-primary)'}}>{config.web_num || 0}个</strong>
                                </div>
                            </Col>
                        </Row>
                    </div>

                    {/* 网卡信息 */}
                    <div style={{
                        padding: 12,
                        background: 'rgba(0, 212, 255, 0.08)',
                        border: '1px solid rgba(0, 212, 255, 0.2)',
                        borderRadius: 8,
                        marginBottom: 16
                    }}>
                        <div style={{
                            fontSize: 12,
                            fontWeight: 600,
                            color: 'var(--accent-primary)',
                            marginBottom: 8
                        }}>网卡信息
                        </div>
                        <div style={{fontSize: 11}}>
                            <div style={{marginBottom: 4}}>
                                <span style={{
                                    color: 'var(--text-secondary)',
                                    width: 48,
                                    display: 'inline-block'
                                }}>IPv4:</span>
                                <span style={{fontFamily: 'monospace', color: 'var(--text-primary)'}}>{ipv4}</span>
                            </div>
                            <div style={{marginBottom: 4}}>
                                <span style={{
                                    color: 'var(--text-secondary)',
                                    width: 48,
                                    display: 'inline-block'
                                }}>IPv6:</span>
                                <span style={{
                                    fontFamily: 'monospace',
                                    color: 'var(--text-primary)'
                                }}>{ipv6 !== '-' ? ipv6 : '未配置'}</span>
                            </div>
                            <div>
                                <span style={{
                                    color: 'var(--text-secondary)',
                                    width: 48,
                                    display: 'inline-block'
                                }}>MAC:</span>
                                <span style={{fontFamily: 'monospace', color: 'var(--text-primary)'}}>{macAddr}</span>
                            </div>
                        </div>
                    </div>

                    {/* 操作按钮 */}
                    <div style={{
                        borderTop: '1px solid var(--border-primary)',
                        paddingTop: 12,
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center'
                    }}>
                        <Button
                            type="link"
                            icon={<EyeOutlined/>}
                            onClick={() => navigate(`/hosts/${hostName}/vms/${uuid}`)}
                        >
                            查看详情
                        </Button>
                        <Space size="small">
                            <Tooltip title="VNC控制台">
                                <Button
                                    size="small"
                                    icon={<DesktopOutlined/>}
                                    onClick={() => handleOpenVnc(uuid, hostName)}
                                />
                            </Tooltip>
                            <Tooltip title="电源管理">
                                <Button
                                    size="small"
                                    icon={<PoweroffOutlined/>}
                                    onClick={() => handleOpenPower(uuid, hostName)}
                                />
                            </Tooltip>
                            <Tooltip title="编辑">
                                <Button
                                    size="small"
                                    icon={<EditOutlined/>}
                                    onClick={() => handleOpenEdit(uuid, hostName)}
                                />
                            </Tooltip>
                            <Tooltip title="删除">
                                <Button
                                    size="small"
                                    danger
                                    icon={<DeleteOutlined/>}
                                    onClick={() => handleDelete(uuid, hostName)}
                                />
                            </Tooltip>
                        </Space>
                    </div>
                </Card>
        )
    }

    const vmCount = Object.keys(vms).length

    // 从复合键中提取主机名和原始UUID
    const extractHostAndUuid = (key: string) => {
        // 如果当前页面指定了主机名，直接使用它
        if (hostName) {
            return {hostName: hostName, uuid: key}
        }

        // 否则从复合键中提取（格式：host-uuid）
        // 只按第一个 - 分割，避免 UUID 中的 - 被错误处理
        const firstDashIndex = key.indexOf('-')
        if (firstDashIndex === -1) {
            return {hostName: hostName || '', uuid: key}
        }

        const host = key.substring(0, firstDashIndex)
        const uuid = key.substring(firstDashIndex + 1)
        return {hostName: host, uuid: uuid}
    }

    return (
        <div style={{
            padding: '32px',
            minHeight: '100vh'
        }}>
            {/* 面包屑导航 */}
            {/*<Breadcrumb*/}
            {/*  style={{ marginBottom: 16 }}*/}
            {/*  items={[*/}
            {/*    {*/}
            {/*      title: <Link to="/hosts">主机管理</Link>,*/}
            {/*    },*/}
            {/*    {*/}
            {/*      title: hostName || '所有主机',*/}
            {/*    },*/}
            {/*  ]}*/}
            {/*/>*/}

            {/* 页面标题 */}
            <div style={{marginBottom: '32px'}}>
                <Title
                    level={2}
                    style={{
                        margin: 0,
                        fontSize: '32px',
                        fontWeight: 700,
                        color: 'var(--text-primary)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '12px'
                    }}
                >
                    <DesktopOutlined style={{width: '36px', height: '36px', color: 'var(--accent-primary)'}}/>
                    虚拟实例管理
                </Title>
                <div style={{
                    marginTop: '8px',
                    fontSize: '14px',
                    color: 'var(--text-secondary)'
                }}>
                    管理主机 <strong style={{color: 'var(--text-primary)'}}>{hostName || '所有主机'}</strong> 下的所有虚拟机
                </div>
            </div>

            {/* 操作栏 */}
            <Card className="glass-effect" style={{marginBottom: 24}}>
                <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    flexWrap: 'wrap',
                    gap: 16
                }}>
                    <Space wrap>
                        <Button type="primary" icon={<PlusOutlined/>} onClick={handleOpenCreate}>
                            创建虚拟机
                        </Button>
                        <Button icon={<ReloadOutlined/>} onClick={loadVMs}>
                            刷新
                        </Button>
                        <Button icon={<RadarChartOutlined/>} onClick={handleScan} disabled={!hostName}>
                            扫描虚拟机
                        </Button>
                        <Button icon={<ArrowLeftOutlined/>} onClick={() => navigate('/hosts')}>
                            返回主机列表
                        </Button>
                    </Space>
                    <div style={{fontSize: 14, color: 'var(--text-primary)'}}>
                        共 <strong style={{color: 'var(--accent-primary)'}}>{vmCount}</strong> 台虚拟机
                    </div>
                </div>
            </Card>

            {/* 虚拟机列表 */}
            {loading ? (
                <div style={{textAlign: 'center', padding: 64}}>
                    <Spin size="large"/>
                    <p style={{marginTop: 16, color: 'var(--text-secondary)'}}>加载中...</p>
                </div>
            ) : vmCount === 0 ? (
                <Card className="glass-effect">
                    <Empty
                        description="暂无虚拟机"
                        image={Empty.PRESENTED_IMAGE_SIMPLE}
                    >
                        <Button type="primary" icon={<PlusOutlined/>} onClick={handleOpenCreate}>
                            创建第一台虚拟机
                        </Button>
                    </Empty>
                </Card>
            ) : (
                <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(400px, 1fr))',
                    gap: '16px'
                }}>
                    {Object.entries(vms).map(([key, vm]) => {
                        const {uuid: _uuid, hostName: vmHostName} = extractHostAndUuid(key)
                        return renderVMCard(_uuid, vm, vmHostName)
                    })}
                </div>
            )}

            {/* 创建/编辑虚拟机对话框 */}
            <Modal
                title={
                    <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '16px',
                        padding: '12px 0'
                    }}>
                        <div style={{
                            width: 56,
                            height: 56,
                            borderRadius: '16px',
                            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            boxShadow: '0 8px 24px rgba(102, 126, 234, 0.4)',
                            position: 'relative',
                            overflow: 'hidden'
                        }}>
                            <div style={{
                                position: 'absolute',
                                inset: 0,
                                background: 'radial-gradient(circle at 30% 30%, rgba(255,255,255,0.3) 0%, transparent 60%)'
                            }} />
                            <DesktopOutlined style={{ fontSize: 28, color: '#fff', position: 'relative', zIndex: 1 }} />
                        </div>
                        <div style={{ flex: 1 }}>
                            <div style={{
                                fontSize: 24,
                                fontWeight: 700,
                                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                                WebkitBackgroundClip: 'text',
                                WebkitTextFillColor: 'transparent',
                                backgroundClip: 'text',
                                letterSpacing: '-0.03em',
                                marginBottom: 4
                            }}>
                                {editMode === 'add' ? '创建虚拟机' : '编辑虚拟机'}
                            </div>
                            <div style={{
                                fontSize: 13,
                                color: 'var(--text-secondary)',
                                fontWeight: 500,
                                letterSpacing: '0.01em'
                            }}>
                                {editMode === 'add' ? '配置并部署新的虚拟实例' : '修改虚拟机配置参数'}
                            </div>
                        </div>
                    </div>
                }
                open={modalVisible}
                onCancel={() => setModalVisible(false)}
                onOk={() => form.submit()}
                width={1000}
                okText={editMode === 'add' ? '🚀 创建虚拟机' : '💾 保存配置'}
                cancelText="取消"
                okButtonProps={{
                    size: 'large',
                    style: {
                        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                        border: 'none',
                        height: 48,
                        borderRadius: 12,
                        fontWeight: 600,
                        fontSize: 15,
                        boxShadow: '0 8px 24px rgba(102, 126, 234, 0.4)',
                        transition: 'all 0.3s ease',
                        position: 'relative',
                        overflow: 'hidden'
                    }
                }}
                cancelButtonProps={{
                    size: 'large',
                    style: {
                        height: 48,
                        borderRadius: 12,
                        fontSize: 15,
                        fontWeight: 500
                    }
                }}
                styles={{
                    body: {
                        maxHeight: '75vh',
                        overflowY: 'auto',
                        overflowX: 'hidden',
                        padding: '32px 32px 16px',
                        background: 'linear-gradient(180deg, rgba(102, 126, 234, 0.02) 0%, transparent 100%)'
                    },
                    header: {
                        borderBottom: '2px solid transparent',
                        borderImage: 'linear-gradient(90deg, rgba(102, 126, 234, 0.3) 0%, rgba(118, 75, 162, 0.3) 100%) 1',
                        paddingBottom: 20,
                        marginBottom: 0,
                        background: 'rgba(102, 126, 234, 0.03)'
                    },
                    mask: {
                        backdropFilter: 'blur(8px)'
                    }
                }}
            >
                <Form form={form} layout="vertical" onFinish={handleSubmit}>
                    {/* 服务器消息提示 */}
                    {hostConfig?.messages && hostConfig.messages.length > 0 && (
                        <Alert
                            message={
                                <span style={{ fontWeight: 600, fontSize: 14 }}>
                                    💡 服务器配置提示
                                </span>
                            }
                            description={
                                <ul style={{paddingLeft: 20, margin: '8px 0 0 0', fontSize: 13}}>
                                    {hostConfig.messages.map((msg, idx) => (
                                        <li key={idx} style={{ marginBottom: 4 }}>{msg}</li>
                                    ))}
                                </ul>
                            }
                            type="info"
                            showIcon
                            style={{
                                marginBottom: 32,
                                borderRadius: 16,
                                border: '2px solid rgba(24, 144, 255, 0.2)',
                                background: 'linear-gradient(135deg, rgba(24, 144, 255, 0.08) 0%, rgba(24, 144, 255, 0.03) 100%)',
                                boxShadow: '0 4px 16px rgba(24, 144, 255, 0.1)'
                            }}
                        />
                    )}

                    {/* 基本信息 */}
                    <div style={{
                        marginBottom: 32,
                        padding: '24px',
                        borderRadius: '16px',
                        background: 'linear-gradient(135deg, rgba(102, 126, 234, 0.05) 0%, rgba(118, 75, 162, 0.05) 100%)',
                        border: '2px solid rgba(102, 126, 234, 0.1)',
                        position: 'relative',
                        overflow: 'hidden'
                    }}>
                        <div style={{
                            position: 'absolute',
                            top: 0,
                            left: 0,
                            right: 0,
                            height: '4px',
                            background: 'linear-gradient(90deg, #667eea 0%, #764ba2 100%)'
                        }} />
                        <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 12,
                            marginBottom: 24
                        }}>
                            <div style={{
                                width: 40,
                                height: 40,
                                borderRadius: 12,
                                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                boxShadow: '0 4px 16px rgba(102, 126, 234, 0.3)'
                            }}>
                                <InfoCircleOutlined style={{ fontSize: 20, color: '#fff' }} />
                            </div>
                            <span style={{
                                fontSize: 18,
                                fontWeight: 700,
                                color: 'var(--text-primary)',
                                letterSpacing: '-0.02em'
                            }}>基本信息</span>
                        </div>

                    <Row gutter={16}>
                        {editMode === 'add' && (
                            <Col span={8}>
                                <Form.Item
                                    name="host_name"
                                    label={<span style={{ fontWeight: 600, fontSize: 14 }}>物理主机</span>}
                                    rules={[{required: true, message: '请选择主机'}]}
                                >
                                <Select
                                    placeholder="请选择主机"
                                    size="large"
                                    style={{
                                        width: '100%',
                                        borderRadius: 12,
                                        marginTop: 5,
                                    }}
                                    onChange={async (value) => {
                                            setSelectedHost(value)
                                            await loadHostImages(value)
                                            // 重新生成UUID
                                            const randomUuid = generateRandomString(8)
                                            form.setFieldsValue({vm_uuid_suffix: randomUuid})
                                        }}
                                    >
                                        {Object.entries(availableHosts).map(([name, host]: [string, any]) => (
                                            <Select.Option key={name} value={name}>
                                                {name} ({host.addr || '未知地址'})
                                            </Select.Option>
                                        ))}
                                    </Select>
                                </Form.Item>
                            </Col>
                        )}
                        <Col span={8}>
                            <Form.Item
                                label={<span style={{ fontWeight: 600, fontSize: 14 }}>虚拟机UUID</span>}
                                required
                            >
                                <Space.Compact style={{width: '100%'}}>
                                    <Input
                                        style={{
                                            width: editMode === 'add' ? '25%' : '35%',
                                            background: 'rgba(102, 126, 234, 0.08)',
                                            fontWeight: 600,
                                            borderRadius: '8px 0 0 8px'
                                        }}
                                        size="large"
                                        value={hostConfig?.filter_name || ''}
                                        disabled
                                    />
                                    <Form.Item
                                        name="vm_uuid_suffix"
                                        noStyle
                                        rules={[{required: true, message: '请输入UUID'}]}
                                    >
                                        <Input
                                            style={{
                                                flex: '1 1 auto',
                                                borderRadius: editMode === 'add' ? 0 : '0 8px 8px 0'
                                            }}
                                            size="large"
                                            placeholder="随机生成"
                                            disabled={editMode === 'edit'}
                                        />
                                    </Form.Item>
                                    {editMode === 'add' && (
                                        <Button
                                            size="large"
                                            style={{
                                                width: 80,
                                                flexShrink: 0,
                                                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                                                border: 'none',
                                                color: '#fff',
                                                fontWeight: 600,
                                                borderRadius: '0 8px 8px 0',
                                                boxShadow: '0 4px 12px rgba(102, 126, 234, 0.3)',
                                                transition: 'all 0.3s ease',

                                            }}
                                            onClick={() => form.setFieldsValue({vm_uuid_suffix: generateRandomString(8)})}
                                        >
                                            🎲
                                        </Button>
                                    )}
                                </Space.Compact>
                            </Form.Item>
                        </Col>
                        <Col span={8}>
                            <Form.Item
                                name="os_name"
                                label={<span style={{ fontWeight: 600, fontSize: 14 }}>操作系统</span>}
                                rules={[{required: true, message: '请选择操作系统'}]}
                            >
                                <Select
                                    placeholder={editMode === 'add' && !selectedHost ? '请先选择主机' : '请选择'}
                                    size="large"
                                    style={{
                                        width: '100%',
                                        borderRadius: 12,
                                        marginTop: 5
                                    }}
                                    disabled={isFieldDisabled('os_name') || (editMode === 'add' && !selectedHost)}
                                    onChange={(value) => {
                                        if (hostImages) {
                                            const entry = Object.entries(hostImages).find(([img]) => img === value)
                                            if (entry) {
                                                const minDisk = entry[1][1] || 0
                                                setSelectedOsMinDisk(minDisk)
                                                form.validateFields(['hdd_num'])
                                            }
                                        }
                                    }}
                                >
                                    {Object.entries(hostImages).map(([osName, [imageFile]]) => (
                                        <Select.Option key={imageFile} value={imageFile}>
                                            {osName}
                                        </Select.Option>
                                    ))}
                                </Select>
                            </Form.Item>
                        </Col>
                    </Row>

                    <Row gutter={16}>
                        <Col span={24}>
                            <Form.Item label="安全配置">
                                <Space.Compact style={{width: '100%', display: 'flex', alignItems: 'center'}}>
                                    <Form.Item
                                        name="os_pass"
                                        noStyle
                                        rules={[{validator: validatePassword}]}
                                    >
                                        <Input.Password
                                            placeholder="系统密码"
                                            size="large"
                                            style={{
                                                flex: '1 1 0',
                                                borderRadius: '8px 0 0 8px',
                                                marginRight: 12,
                                            }}
                                            disabled={isFieldDisabled('os_pass')}
                                        />
                                    </Form.Item>
                                    <Form.Item
                                        name="vc_pass"
                                        noStyle
                                        rules={[{validator: validatePassword}]}
                                    >
                                        <Input.Password
                                            placeholder="VNC密码"
                                            size="large"
                                            style={{
                                                flex: '1 1 0',
                                                borderRadius: 0,
                                                marginRight: 12
                                            }}
                                            disabled={isFieldDisabled('vc_pass')}
                                        />
                                    </Form.Item>
                                    <Form.Item name="vc_port" noStyle>
                                        <InputNumber
                                            min={1}
                                            max={65535}
                                            size="large"
                                            style={{
                                                width: 120,
                                                borderRadius: 0,
                                                marginRight: 12,
                                                padding: 0,

                                            }}
                                            placeholder="VNC端口"
                                            disabled={isFieldDisabled('vc_port')}
                                        />
                                    </Form.Item>
                                    <Tooltip title="随机生成密码和端口">
                                        <Button
                                            size="large"
                                            style={{
                                                width: 80,
                                                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                                                border: 'none',
                                                color: '#fff',
                                                fontWeight: 600,
                                                borderRadius: '0 8px 8px 0',
                                                boxShadow: '0 4px 12px rgba(102, 126, 234, 0.3)',
                                                transition: 'all 0.3s ease',
                                            }}
                                            onClick={() => {
                                                const randomPass = generateRandomString(8)
                                                form.setFieldsValue({
                                                    os_pass: randomPass,
                                                    vc_pass: randomPass,
                                                    vc_port: generateRandomVncPort(),
                                                })
                                            }}
                                            disabled={isFieldDisabled('os_pass') && isFieldDisabled('vc_pass')}
                                        >
                                            🎲
                                        </Button>
                                    </Tooltip>
                                </Space.Compact>
                                <div style={{marginTop: 4, fontSize: 12, color: 'var(--text-secondary)'}}>
                                    密码至少8位，需包含字母和数字
                                </div>
                            </Form.Item>
                        </Col>
                    </Row>
                    </div>

                    {/* 资源配置 */}
                    <div style={{
                        marginBottom: 32,
                        padding: '24px',
                        borderRadius: '16px',
                        background: 'linear-gradient(135deg, rgba(240, 147, 251, 0.05) 0%, rgba(245, 87, 108, 0.05) 100%)',
                        border: '2px solid rgba(240, 147, 251, 0.15)',
                        position: 'relative',
                        overflow: 'hidden'
                    }}>
                        <div style={{
                            position: 'absolute',
                            top: 0,
                            left: 0,
                            right: 0,
                            height: '4px',
                            background: 'linear-gradient(90deg, #f093fb 0%, #f5576c 100%)'
                        }} />
                        <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 12,
                            marginBottom: 24
                        }}>
                            <div style={{
                                width: 40,
                                height: 40,
                                borderRadius: 12,
                                background: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                boxShadow: '0 4px 16px rgba(240, 147, 251, 0.3)'
                            }}>
                                <ThunderboltOutlined style={{ fontSize: 20, color: '#fff' }} />
                            </div>
                            <span style={{
                                fontSize: 18,
                                fontWeight: 700,
                                color: 'var(--text-primary)',
                                letterSpacing: '-0.02em'
                            }}>资源配置</span>
                        </div>
                    <Row gutter={16}>
                        <Col span={12}>
                            <Form.Item label="CPU核心数" required>
                                {!isAdmin && (
                                    <div style={{display: 'flex', justifyContent: 'space-between', marginBottom: 8}}>
                                        <span style={{fontSize: 12, color: 'var(--text-secondary)'}}>
                                            <strong>{form.getFieldValue('cpu_num') || 2}</strong> 核
                                        </span>
                                        {userQuota && (
                                            <span style={{fontSize: 12, color: 'var(--text-secondary)'}}>
                                                可用: {userQuota.quota_cpu - userQuota.used_cpu} 核
                                            </span>
                                        )}
                                    </div>
                                )}
                                <Form.Item name="cpu_num" noStyle rules={[{required: true}]}>
                                    {isAdmin ? (
                                        <InputNumber
                                            min={1}
                                            max={256}
                                            size="large"
                                            style={{
                                                width: '100%',
                                                borderRadius: 8
                                            }}
                                            disabled={isFieldDisabled('cpu_num')}
                                            placeholder="最大256核"
                                            controls={false}
                                        />
                                    ) : (
                                        <Slider
                                            min={1}
                                            max={Math.min(256, userQuota ? Math.max(1, userQuota.quota_cpu - userQuota.used_cpu + (editMode === 'edit' ? form.getFieldValue('cpu_num') || 0 : 0)) : 16)}
                                            step={1}
                                            disabled={isFieldDisabled('cpu_num')}
                                            styles={{
                                                track: {
                                                    background: 'linear-gradient(90deg, #667eea 0%, #764ba2 100%)'
                                                }
                                            }}
                                        />
                                    )}
                                </Form.Item>
                            </Form.Item>
                        </Col>
                        <Col span={12}>
                            <Form.Item label="内存 (GB)" required>
                                {!isAdmin && (
                                    <div style={{display: 'flex', justifyContent: 'space-between', marginBottom: 8}}>
                                        <span style={{fontSize: 12, color: 'var(--text-secondary)'}}>
                                            <strong>{((form.getFieldValue('mem_num') || 2048) / 1024).toFixed(1)}</strong> GB
                                        </span>
                                        {userQuota && (
                                            <span style={{fontSize: 12, color: 'var(--text-secondary)'}}>
                                                可用: {((userQuota.quota_ram - userQuota.used_ram) / 1024).toFixed(1)} GB
                                            </span>
                                        )}
                                    </div>
                                )}
                                <Form.Item name="mem_num" noStyle rules={[{required: true}]}>
                                    {isAdmin ? (
                                        <InputNumber
                                            min={512}
                                            max={1024 * 1024}
                                            size="large"
                                            style={{
                                                width: '100%',
                                                borderRadius: 8
                                            }}
                                            disabled={isFieldDisabled('mem_num')}
                                            placeholder="最大1024GB (单位:MB)"
                                            addonAfter="MB"
                                            controls={false}
                                        />
                                    ) : (
                                        <Slider
                                            min={512}
                                            max={Math.min(1024 * 1024, userQuota ? Math.max(512, userQuota.quota_ram - userQuota.used_ram + (editMode === 'edit' ? form.getFieldValue('mem_num') || 0 : 0)) : 16384)}
                                            step={512}
                                            disabled={isFieldDisabled('mem_num')}
                                            styles={{
                                                track: {
                                                    background: 'linear-gradient(90deg, #f093fb 0%, #f5576c 100%)'
                                                }
                                            }}
                                        />
                                    )}
                                </Form.Item>
                            </Form.Item>
                        </Col>
                    </Row>

                    <Row gutter={16}>
                        <Col span={12}>
                            <Form.Item
                                label="硬盘 (GB)"
                                required
                                extra={selectedOsMinDisk > 0 ? `最小要求: ${selectedOsMinDisk}GB` : ''}
                            >
                                {!isAdmin && (
                                    <div style={{display: 'flex', justifyContent: 'space-between', marginBottom: 8}}>
                                        <span style={{fontSize: 12, color: 'var(--text-secondary)'}}>
                                            <strong>{((form.getFieldValue('hdd_num') || 20480) / 1024).toFixed(1)}</strong> GB
                                        </span>
                                        {userQuota && (
                                            <span style={{fontSize: 12, color: 'var(--text-secondary)'}}>
                                                可用: {((userQuota.quota_ssd - userQuota.used_ssd) / 1024).toFixed(1)} GB
                                            </span>
                                        )}
                                    </div>
                                )}
                                <Form.Item
                                    name="hdd_num"
                                    noStyle
                                    rules={[
                                        {required: true},
                                        {
                                            validator: (_, value) => {
                                                if (!value) return Promise.resolve()
                                                const minMB = selectedOsMinDisk * 1024
                                                if (value < minMB) {
                                                    return Promise.reject(new Error(`最小要求: ${selectedOsMinDisk}GB (${minMB}MB)`))
                                                }
                                                return Promise.resolve()
                                            }
                                        }
                                    ]}
                                >
                                    {isAdmin ? (
                                        <InputNumber
                                            min={Math.max(10240, selectedOsMinDisk * 1024)}
                                            max={4096 * 1024}
                                            size="large"
                                            style={{
                                                width: '100%',
                                                borderRadius: 8
                                            }}
                                            disabled={isFieldDisabled('hdd_num')}
                                            placeholder="最大4096GB (单位:MB)"
                                            addonAfter="MB"
                                            controls={false}
                                        />
                                    ) : (
                                        <Slider
                                            min={Math.max(10240, selectedOsMinDisk * 1024)}
                                            max={Math.min(4096 * 1024, userQuota ? Math.max(10240, userQuota.quota_ssd - userQuota.used_ssd + (editMode === 'edit' ? form.getFieldValue('hdd_num') || 0 : 0)) : 102400)}
                                            step={1024}
                                            disabled={isFieldDisabled('hdd_num')}
                                            styles={{
                                                track: {
                                                    background: 'linear-gradient(90deg, #4facfe 0%, #00f2fe 100%)'
                                                }
                                            }}
                                        />
                                    )}
                                </Form.Item>
                            </Form.Item>
                        </Col>
                        <Col span={12}>
                            <Form.Item label="GPU显存 (MB)">
                                {!isAdmin && (
                                    <div style={{display: 'flex', justifyContent: 'space-between', marginBottom: 8}}>
                                        <span style={{fontSize: 12, color: 'var(--text-secondary)'}}>
                                            <strong>{form.getFieldValue('gpu_mem') || 128}</strong> MB
                                        </span>
                                    </div>
                                )}
                                <Form.Item name="gpu_mem" noStyle>
                                    {isAdmin ? (
                                        <InputNumber
                                            min={0}
                                            max={32768}
                                            size="large"
                                            style={{
                                                width: '100%',
                                                borderRadius: 8
                                            }}
                                            disabled={isFieldDisabled('gpu_mem')}
                                            placeholder="最大32768MB"
                                            addonAfter="MB"
                                            controls={false}
                                        />
                                    ) : (
                                        <Slider
                                            min={0}
                                            max={32768}
                                            step={128}
                                            disabled={isFieldDisabled('gpu_mem')}
                                            styles={{
                                                track: {
                                                    background: 'linear-gradient(90deg, #fa709a 0%, #fee140 100%)'
                                                }
                                            }}
                                        />
                                    )}
                                </Form.Item>
                            </Form.Item>
                        </Col>
                    </Row>

                    <Row gutter={16}>
                        <Col span={8}>
                            <Form.Item label="流量限制 (GB)">
                                {!isAdmin && (
                                    <div style={{display: 'flex', justifyContent: 'space-between', marginBottom: 8}}>
                                        <span style={{fontSize: 12, color: 'var(--text-secondary)'}}>
                                            <strong>{((form.getFieldValue('flu_num') || 102400) / 1024).toFixed(1)}</strong> GB
                                        </span>
                                        {userQuota && (
                                            <span style={{fontSize: 12, color: 'var(--text-secondary)'}}>
                                                可用: {((userQuota.quota_traffic - userQuota.used_traffic) / 1024).toFixed(1)} GB
                                            </span>
                                        )}
                                    </div>
                                )}
                                <Form.Item name="flu_num" noStyle>
                                    {isAdmin ? (
                                        <InputNumber
                                            min={0}
                                            max={1024 * 1024 * 1024}
                                            size="large"
                                            style={{
                                                width: '100%',
                                                borderRadius: 8
                                            }}
                                            disabled={isFieldDisabled('flu_num')}
                                            placeholder="最大1PB (单位:MB)"
                                            addonAfter="MB"
                                            controls={false}
                                        />
                                    ) : (
                                        <Slider
                                            min={0}
                                            max={Math.min(1024 * 1024 * 1024, userQuota ? Math.max(1024, userQuota.quota_traffic - userQuota.used_traffic + (editMode === 'edit' ? form.getFieldValue('flu_num') || 0 : 0)) : 1024000)}
                                            step={1024}
                                            disabled={isFieldDisabled('flu_num')}
                                            styles={{
                                                track: {
                                                    background: 'linear-gradient(90deg, #30cfd0 0%, #330867 100%)'
                                                }
                                            }}
                                        />
                                    )}
                                </Form.Item>
                            </Form.Item>
                        </Col>
                        <Col span={8}>
                            <Form.Item label="上行带宽 (Mbps)">
                                {!isAdmin && (
                                    <div style={{display: 'flex', justifyContent: 'space-between', marginBottom: 8}}>
                                        <span style={{fontSize: 12, color: 'var(--text-secondary)'}}>
                                            <strong>{form.getFieldValue('speed_u') || 100}</strong> Mbps
                                        </span>
                                        {userQuota && (
                                            <span style={{fontSize: 12, color: 'var(--text-secondary)'}}>
                                                可用: {userQuota.quota_upload_bw - userQuota.used_upload_bw} Mbps
                                            </span>
                                        )}
                                    </div>
                                )}
                                <Form.Item name="speed_u" noStyle>
                                    {isAdmin ? (
                                        <InputNumber
                                            min={1}
                                            max={10000}
                                            size="large"
                                            style={{
                                                width: '100%',
                                                borderRadius: 8
                                            }}
                                            disabled={isFieldDisabled('speed_u')}
                                            placeholder="最大10000Mbps"
                                            addonAfter="Mbps"
                                            controls={false}
                                        />
                                    ) : (
                                        <Slider
                                            min={1}
                                            max={Math.min(10000, userQuota ? Math.max(1, userQuota.quota_upload_bw - userQuota.used_upload_bw + (editMode === 'edit' ? form.getFieldValue('speed_u') || 0 : 0)) : 1000)}
                                            step={1}
                                            disabled={isFieldDisabled('speed_u')}
                                            styles={{
                                                track: {
                                                    background: 'linear-gradient(90deg, #a8edea 0%, #fed6e3 100%)'
                                                }
                                            }}
                                        />
                                    )}
                                </Form.Item>
                            </Form.Item>
                        </Col>
                        <Col span={8}>
                            <Form.Item label="下行带宽 (Mbps)">
                                {!isAdmin && (
                                    <div style={{display: 'flex', justifyContent: 'space-between', marginBottom: 8}}>
                                        <span style={{fontSize: 12, color: 'var(--text-secondary)'}}>
                                            <strong>{form.getFieldValue('speed_d') || 100}</strong> Mbps
                                        </span>
                                        {userQuota && (
                                            <span style={{fontSize: 12, color: 'var(--text-secondary)'}}>
                                                可用: {userQuota.quota_download_bw - userQuota.used_download_bw} Mbps
                                            </span>
                                        )}
                                    </div>
                                )}
                                <Form.Item name="speed_d" noStyle>
                                    {isAdmin ? (
                                        <InputNumber
                                            min={1}
                                            max={10000}
                                            size="large"
                                            style={{
                                                width: '100%',
                                                borderRadius: 8
                                            }}
                                            disabled={isFieldDisabled('speed_d')}
                                            placeholder="最大10000Mbps"
                                            addonAfter="Mbps"
                                            controls={false}
                                        />
                                    ) : (
                                        <Slider
                                            min={1}
                                            max={Math.min(10000, userQuota ? Math.max(1, userQuota.quota_download_bw - userQuota.used_download_bw + (editMode === 'edit' ? form.getFieldValue('speed_d') || 0 : 0)) : 1000)}
                                            step={1}
                                            disabled={isFieldDisabled('speed_d')}
                                            styles={{
                                                track: {
                                                    background: 'linear-gradient(90deg, #ff9a9e 0%, #fecfef 100%)'
                                                }
                                            }}
                                        />
                                    )}
                                </Form.Item>
                            </Form.Item>
                        </Col>
                    </Row>

                    <Row gutter={16}>
                        <Col span={12}>
                            <Form.Item label="NAT端口数">
                                {!isAdmin && (
                                    <div style={{display: 'flex', justifyContent: 'space-between', marginBottom: 8}}>
                                        <span style={{fontSize: 12, color: 'var(--text-secondary)'}}>
                                            <strong>{form.getFieldValue('nat_num') || 100}</strong> 个
                                        </span>
                                        {userQuota && (
                                            <span style={{fontSize: 12, color: 'var(--text-secondary)'}}>
                                                可用: {userQuota.quota_nat - userQuota.used_nat} 个
                                            </span>
                                        )}
                                    </div>
                                )}
                                <Form.Item name="nat_num" noStyle>
                                    {isAdmin ? (
                                        <InputNumber
                                            min={0}
                                            max={50000}
                                            size="large"
                                            style={{
                                                width: '100%',
                                                borderRadius: 8
                                            }}
                                            disabled={isFieldDisabled('nat_num')}
                                            placeholder="最大50000个"
                                            controls={false}
                                        />
                                    ) : (
                                        <Slider
                                            min={0}
                                            max={Math.min(50000, userQuota ? Math.max(1, userQuota.quota_nat - userQuota.used_nat + (editMode === 'edit' ? form.getFieldValue('nat_num') || 0 : 0)) : 200)}
                                            step={1}
                                            disabled={isFieldDisabled('nat_num')}
                                            styles={{
                                                track: {
                                                    background: 'linear-gradient(90deg, #ffecd2 0%, #fcb69f 100%)'
                                                }
                                            }}
                                        />
                                    )}
                                </Form.Item>
                            </Form.Item>
                        </Col>
                        <Col span={12}>
                            <Form.Item label="Web代理数">
                                {!isAdmin && (
                                    <div style={{display: 'flex', justifyContent: 'space-between', marginBottom: 8}}>
                                        <span style={{fontSize: 12, color: 'var(--text-secondary)'}}>
                                            <strong>{form.getFieldValue('web_num') || 100}</strong> 个
                                        </span>
                                        {userQuota && (
                                            <span style={{fontSize: 12, color: 'var(--text-secondary)'}}>
                                                可用: {userQuota.quota_web - userQuota.used_web} 个
                                            </span>
                                        )}
                                    </div>
                                )}
                                <Form.Item name="web_num" noStyle>
                                    {isAdmin ? (
                                        <InputNumber
                                            min={0}
                                            max={50000}
                                            size="large"
                                            style={{
                                                width: '100%',
                                                borderRadius: 8
                                            }}
                                            disabled={isFieldDisabled('web_num')}
                                            placeholder="最大50000个"
                                            controls={false}
                                        />
                                    ) : (
                                        <Slider
                                            min={0}
                                            max={Math.min(50000, userQuota ? Math.max(1, userQuota.quota_web - userQuota.used_web + (editMode === 'edit' ? form.getFieldValue('web_num') || 0 : 0)) : 200)}
                                            step={1}
                                            disabled={isFieldDisabled('web_num')}
                                            styles={{
                                                track: {
                                                    background: 'linear-gradient(90deg, #ff6e7f 0%, #bfe9ff 100%)'
                                                }
                                            }}
                                        />
                                    )}
                                </Form.Item>
                            </Form.Item>
                        </Col>
                    </Row>
                    </div>

                    {/* 网络配置 */}
                    <div style={{
                        marginBottom: 32,
                        padding: '24px',
                        borderRadius: '16px',
                        background: 'linear-gradient(135deg, rgba(79, 172, 254, 0.05) 0%, rgba(0, 242, 254, 0.05) 100%)',
                        border: '2px solid rgba(79, 172, 254, 0.15)',
                        position: 'relative',
                        overflow: 'hidden'
                    }}>
                        <div style={{
                            position: 'absolute',
                            top: 0,
                            left: 0,
                            right: 0,
                            height: '4px',
                            background: 'linear-gradient(90deg, #4facfe 0%, #00f2fe 100%)'
                        }} />
                        <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 12,
                            marginBottom: 24
                        }}>
                            <div style={{
                                width: 40,
                                height: 40,
                                borderRadius: 12,
                                background: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                boxShadow: '0 4px 16px rgba(79, 172, 254, 0.3)'
                            }}>
                                <RadarChartOutlined style={{ fontSize: 20, color: '#fff' }} />
                            </div>
                            <span style={{
                                fontSize: 18,
                                fontWeight: 700,
                                color: 'var(--text-primary)',
                                letterSpacing: '-0.02em'
                            }}>网络配置</span>
                        </div>
                    {userQuota && (
                        <div style={{
                            padding: 16,
                            borderRadius: 12,
                            background: userQuota.quota_nat_ips - userQuota.used_nat_ips <= 0 && userQuota.quota_pub_ips - userQuota.used_pub_ips <= 0
                                ? 'linear-gradient(135deg, rgba(255, 77, 79, 0.1) 0%, rgba(255, 77, 79, 0.05) 100%)'
                                : 'linear-gradient(135deg, rgba(82, 196, 26, 0.1) 0%, rgba(82, 196, 26, 0.05) 100%)',
                            border: `1px solid ${userQuota.quota_nat_ips - userQuota.used_nat_ips <= 0 && userQuota.quota_pub_ips - userQuota.used_pub_ips <= 0 ? 'rgba(255, 77, 79, 0.3)' : 'rgba(82, 196, 26, 0.3)'}`,
                            marginBottom: 16
                        }}>
                            <Space>
                                <Text style={{ fontWeight: 600 }}>IP配额状态:</Text>
                                <Text
                                    type={userQuota.quota_nat_ips - userQuota.used_nat_ips <= 0 && userQuota.quota_pub_ips - userQuota.used_pub_ips <= 0 ? 'danger' : 'success'}
                                    style={{ fontWeight: 600 }}>
                                    {userQuota.quota_nat_ips - userQuota.used_nat_ips <= 0 && userQuota.quota_pub_ips - userQuota.used_pub_ips <= 0 ? 'IP配额已用尽' : 'IP配额充足'}
                                </Text>
                                <Text type="secondary" style={{fontSize: 12}}>
                                    (内网: {userQuota.used_nat_ips}/{userQuota.quota_nat_ips},
                                    公网: {userQuota.used_pub_ips}/{userQuota.quota_pub_ips})
                                </Text>
                            </Space>
                        </div>
                    )}

                    {nicList.map((nic) => (
                        <Space.Compact key={nic.key} style={{width: '100%', marginBottom: 16}}>
                            <Form.Item name={`nic_name_${nic.key}`} initialValue={nic.name} noStyle>
                                <Input
                                    placeholder="网卡名称"
                                    size="large"
                                    style={{
                                        width: 140,
                                        flexShrink: 0,
                                        background: 'rgba(79, 172, 254, 0.08)',
                                        fontWeight: 600,
                                        borderRadius: '8px 0 0 8px'
                                    }}
                                    disabled
                                />
                            </Form.Item>
                            <Form.Item name={`nic_type_${nic.key}`} initialValue="nat" noStyle>
                                <Select
                                    size="large"
                                    style={{
                                        width: 120,
                                        flexShrink: 0,
                                        borderRadius: 0,
                                        marginTop: 5,
                                        marginLeft: 12
                                    }}
                                    onChange={(val) => {
                                        const updatedList = nicList.map(n => n.key === nic.key ? {
                                            ...n,
                                            type: val
                                        } : n)
                                        setNicList(updatedList)
                                    }}
                                >
                                    <Select.Option
                                        value="nat"
                                        disabled={nic.type !== 'nat' && userQuota && userQuota.used_nat_ips >= userQuota.quota_nat_ips}
                                    >
                                        🏠 内网
                                    </Select.Option>
                                    <Select.Option
                                        value="pub"
                                        disabled={nic.type !== 'pub' && userQuota && userQuota.used_pub_ips >= userQuota.quota_pub_ips}
                                    >
                                        🌐 公网
                                    </Select.Option>
                                </Select>
                            </Form.Item>
                            <Form.Item name={`nic_ip_${nic.key}`} noStyle>
                                <Input
                                    placeholder="IPv4地址"
                                    size="large"
                                    style={{
                                        flex: '1 1 0',
                                        minWidth: 0,
                                        borderRadius: 0,
                                        marginLeft: 12
                                    }}
                                />
                            </Form.Item>
                            <Form.Item name={`nic_ip6_${nic.key}`} noStyle>
                                <Input
                                    placeholder="IPv6地址"
                                    size="large"
                                    style={{
                                        flex: '1 1 0',
                                        minWidth: 0,
                                        borderRadius: 0,
                                        marginLeft: 12
                                    }}
                                />
                            </Form.Item>
                            <Tooltip title="删除网卡">
                                <Button
                                    danger
                                    size="large"
                                    icon={<DeleteOutlined />}
                                    onClick={() => handleRemoveNic(nic.key)}
                                    style={{
                                        width: 48,
                                        flexShrink: 0,
                                        borderRadius: '0 8px 8px 0'
                                    }}
                                />
                            </Tooltip>
                        </Space.Compact>
                    ))}
                    <Button
                        type="dashed"
                        onClick={handleAddNic}
                        block
                        disabled={isFieldDisabled('nic_all')}
                        style={{
                            height: 56,
                            borderRadius: 16,
                            borderWidth: 2,
                            borderStyle: 'dashed',
                            fontSize: 15,
                            fontWeight: 600,
                            borderColor: 'rgba(79, 172, 254, 0.4)',
                            color: 'rgba(79, 172, 254, 1)',
                            background: 'linear-gradient(135deg, rgba(79, 172, 254, 0.05) 0%, rgba(0, 242, 254, 0.05) 100%)',
                            transition: 'all 0.3s ease'
                        }}
                        icon={<PlusOutlined />}
                    >
                        添加网卡
                    </Button>
                    </div>
                </Form>
            </Modal>

            {/* 电源操作对话框 */}
            <Modal
                title="电源操作"
                open={powerModalVisible}
                onCancel={() => setPowerModalVisible(false)}
                footer={null}
                width={400}
            >
                <p style={{marginBottom: 16}}>选择对虚拟机 "<strong>{currentVmUuid}</strong>" 执行的操作：</p>
                <Row gutter={[12, 12]}>
                    <Col span={12}>
                        <Button
                            block
                            type="primary"
                            className="bg-green-500 hover:bg-green-600 dark:bg-green-600 dark:hover:bg-green-700"
                            icon={<PlayCircleOutlined/>}
                            onClick={() => handlePowerAction('start')}
                        >
                            启动
                        </Button>
                    </Col>
                    <Col span={12}>
                        <Button
                            block
                            className="bg-yellow-500 hover:bg-yellow-600 dark:bg-yellow-600 dark:hover:bg-yellow-700 text-white"
                            icon={<PauseCircleOutlined/>}
                            onClick={() => handlePowerAction('stop')}
                        >
                            关机
                        </Button>
                    </Col>
                    <Col span={12}>
                        <Button
                            block
                            type="primary"
                            icon={<RedoOutlined/>}
                            onClick={() => handlePowerAction('reset')}
                        >
                            重启
                        </Button>
                    </Col>
                    <Col span={12}>
                        <Button
                            block
                            className="bg-gray-500 hover:bg-gray-600 dark:bg-gray-600 dark:hover:bg-gray-700 text-white"
                            icon={<PauseCircleOutlined/>}
                            onClick={() => handlePowerAction('pause')}
                        >
                            暂停
                        </Button>
                    </Col>
                    <Col span={12}>
                        <Button
                            block
                            className="bg-purple-600 hover:bg-purple-700 dark:bg-purple-700 dark:hover:bg-purple-800 text-white"
                            icon={<PlayCircleOutlined/>}
                            onClick={() => handlePowerAction('resume')}
                        >
                            恢复
                        </Button>
                    </Col>
                    <Col span={12}>
                        <Button
                            block
                            danger
                            icon={<PoweroffOutlined/>}
                            onClick={() => handlePowerAction('hard_stop')}
                        >
                            强制关机
                        </Button>
                    </Col>
                    <Col span={12}>
                        <Button
                            block
                            danger
                            icon={<ThunderboltOutlined/>}
                            onClick={() => handlePowerAction('hard_reset')}
                        >
                            强制重启
                        </Button>
                    </Col>
                </Row>
            </Modal>

            {/* 保存确认对话框 */}
            <Modal
                title="保存确认"
                open={saveConfirmModalVisible}
                onCancel={() => setSaveConfirmModalVisible(false)}
                onOk={handleConfirmSave}
                okText="确认保存"
                okButtonProps={{disabled: !forceShutdownConfirmed}}
                cancelText="取消"
            >
                <div style={{display: 'flex', gap: 16, alignItems: 'flex-start'}}>
                    <InfoCircleOutlined style={{color: '#faad14', fontSize: 22, marginTop: 4}}/>
                    <div>
                        <p style={{fontWeight: 500, fontSize: 16, marginBottom: 8}}>确定要保存对虚拟机 "{currentVmUuid}"
                            的配置修改吗？</p>
                        <div
                            className="mt-3 p-3 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-700 rounded">
                            <Checkbox
                                checked={forceShutdownConfirmed}
                                onChange={(e) => setForceShutdownConfirmed(e.target.checked)}
                                className="text-red-600 dark:text-red-400 font-bold"
                            >
                                我已确认强制关闭虚拟机
                            </Checkbox>
                        </div>
                    </div>
                </div>
            </Modal>
        </div>
    )
}

export default DockManage