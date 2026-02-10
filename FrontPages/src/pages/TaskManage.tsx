import { useEffect, useState } from 'react'
import { message, Modal, Select } from 'antd'
import api from '@/utils/apis.ts'
import PageHeader from '@/components/PageHeader'

/**
 * 任务数据接口
 */
interface Task {
  id?: number
  type?: string
  task_type?: string
  status: string
  vm_name?: string
  vm_uuid?: string
  hs_name?: string
  description?: string
  message?: string
  created_at?: string
  timestamp?: string
  error_message?: string
  [key: string]: unknown
}

/**
 * 任务管理页面
 */
function TaskManage() {
  // 状态管理
  const [tasks, setTasks] = useState<Task[]>([]) // 所有任务列表
  const [filteredTasks, setFilteredTasks] = useState<Task[]>([]) // 过滤后的任务列表
  const [hosts, setHosts] = useState<string[]>([]) // 主机列表
  const [loading, setLoading] = useState(false) // 加载状态
  const [selectedHost, setSelectedHost] = useState<string>('') // 选中的主机
  const [selectedStatus, setSelectedStatus] = useState<string>('') // 选中的状态
  const [autoRefresh, setAutoRefresh] = useState(false) // 自动刷新状态
  const [selectedTask, setSelectedTask] = useState<Task | null>(null) // 选中的任务
  const [modalVisible, setModalVisible] = useState(false) // 模态框显示状态

  /**
   * 加载主机列表
   */
  const loadHosts = async () => {
    try {
      const result = await api.getHosts()
      if (result && result.code === 200) {
        const hostNames = Object.keys(result.data || {})
        setHosts(hostNames)
      }
    } catch (error) {
      console.error('加载主机列表失败:', error)
    }
  }

  /**
   * 加载任务列表
   */
  const loadTasks = async () => {
    try {
      setLoading(true)
      const result = await api.getTasks(selectedHost, 200)
      if (result && result.code === 200) {
        setTasks(result.data || [])
      }
    } catch (error) {
      console.error('加载任务失败:', error)
      message.error('加载任务失败')
    } finally {
      setLoading(false)
    }
  }

  /**
   * 过滤任务
   */
  useEffect(() => {
    let filtered = tasks
    if (selectedStatus) {
      filtered = tasks.filter(task => task.status === selectedStatus)
    }
    setFilteredTasks(filtered)
  }, [tasks, selectedStatus])

  /**
   * 初始化加载
   */
  useEffect(() => {
    loadHosts()
    loadTasks()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  /**
   * 主机变化时重新加载任务
   */
  useEffect(() => {
    loadTasks()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedHost])

  /**
   * 自动刷新
   */
  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | null = null
    if (autoRefresh) {
      interval = setInterval(() => {
        loadTasks()
      }, 5000)
    }
    return () => {
      if (interval) clearInterval(interval)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoRefresh, selectedHost])

  /**
   * 获取状态信息
   */
  const getStatusInfo = (status: string) => {
    const statusMap: Record<string, { text: string; icon: string; bgColor: string; textColor: string }> = {
      pending: {
        text: '等待中',
        icon: 'mdi:clock-outline',
        bgColor: 'bg-yellow-100',
        textColor: 'text-yellow-600'
      },
      running: {
        text: '运行中',
        icon: 'mdi:play-circle',
        bgColor: 'bg-blue-100',
        textColor: 'text-blue-600'
      },
      completed: {
        text: '已完成',
        icon: 'mdi:check-circle',
        bgColor: 'bg-green-100',
        textColor: 'text-green-600'
      },
      failed: {
        text: '失败',
        icon: 'mdi:close-circle',
        bgColor: 'bg-red-100',
        textColor: 'text-red-600'
      }
    }
    return statusMap[status.toLowerCase()] || {
      text: '未知',
      icon: 'mdi:help-circle',
      bgColor: 'bg-gray-100',
        textColor: ''
    }
  }

  /**
   * 计算统计数据
   */
  const getStatistics = () => {
    const stats = {
      pending: 0,
      running: 0,
      completed: 0,
      failed: 0
    }
    tasks.forEach(task => {
      const status = (task.status || 'pending').toLowerCase()
      if (Object.prototype.hasOwnProperty.call(stats, status)) {
        stats[status as keyof typeof stats]++
      }
    })
    return stats
  }

  const statistics = getStatistics()

  /**
   * 显示任务详情
   */
  const showTaskDetail = (task: Task) => {
    setSelectedTask(task)
    setModalVisible(true)
  }

  /**
   * 清空任务显示
   */
  const clearTasks = () => {
    setTasks([])
    message.success('已清空任务显示')
  }

  /**
   * 格式化时间
   */
  const formatTime = (timestamp?: string) => {
    if (!timestamp) return new Date().toLocaleString('zh-CN')
    return new Date(timestamp).toLocaleString('zh-CN')
  }

  return (
    <div className="p-6">
      {/* 页面标题 */}
      <PageHeader
        icon={<span className="iconify" data-icon="mdi:playlist-check" style={{ width: '24px', height: '24px' }}></span>}
        title="任务管理"
        subtitle="查看虚拟机任务执行情况和状态"
      />

      {/* 过滤器 */}
      <div className="glass-card p-4 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>主机筛选</label>
            <Select
              className="w-full"
              placeholder="全部主机"
              value={selectedHost || undefined}
              onChange={setSelectedHost}
              allowClear
              options={[
                { label: '全部主机', value: '' },
                ...hosts.map(host => ({ label: host, value: host }))
              ]}
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>任务状态</label>
            <Select
              className="w-full"
              placeholder="全部状态"
              value={selectedStatus || undefined}
              onChange={setSelectedStatus}
              allowClear
              options={[
                { label: '全部状态', value: '' },
                { label: '等待中', value: 'pending' },
                { label: '运行中', value: 'running' },
                { label: '已完成', value: 'completed' },
                { label: '失败', value: 'failed' }
              ]}
            />
          </div>
          <div className="flex items-end">
            <button
              onClick={loadTasks}
              className="w-full bg-purple-600 hover:bg-purple-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 shadow-sm flex items-center justify-center gap-2"
            >
              <span className="iconify" data-icon="mdi:refresh" style={{ width: '18px', height: '18px' }}></span>
              刷新
            </button>
          </div>
        </div>
      </div>

      {/* 任务统计 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="glass-card p-4 hover:shadow-xl transition-all duration-300 hover:-translate-y-1">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-yellow-100 rounded-lg flex items-center justify-center">
              <span className="iconify text-yellow-600" data-icon="mdi:clock-outline" style={{ width: '20px', height: '20px' }}></span>
            </div>
            <div>
              <p className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>等待中</p>
              <p className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>{statistics.pending}</p>
            </div>
          </div>
        </div>
        <div className="glass-card p-4 hover:shadow-xl transition-all duration-300 hover:-translate-y-1">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
              <span className="iconify text-blue-600" data-icon="mdi:play-circle" style={{ width: '20px', height: '20px' }}></span>
            </div>
            <div>
              <p className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>运行中</p>
              <p className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>{statistics.running}</p>
            </div>
          </div>
        </div>
        <div className="glass-card p-4 hover:shadow-xl transition-all duration-300 hover:-translate-y-1">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
              <span className="iconify text-green-600" data-icon="mdi:check-circle" style={{ width: '20px', height: '20px' }}></span>
            </div>
            <div>
              <p className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>已完成</p>
              <p className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>{statistics.completed}</p>
            </div>
          </div>
        </div>
        <div className="glass-card p-4 hover:shadow-xl transition-all duration-300 hover:-translate-y-1">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-red-100 rounded-lg flex items-center justify-center">
              <span className="iconify text-red-600" data-icon="mdi:close-circle" style={{ width: '20px', height: '20px' }}></span>
            </div>
            <div>
              <p className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>失败</p>
              <p className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>{statistics.failed}</p>
            </div>
          </div>
        </div>
      </div>

      {/* 任务列表 */}
      <div className="glass-card">
        <div className="p-4 border-b flex items-center justify-between" style={{ borderColor: 'var(--border-primary)' }}>
          <h2 className="text-base font-semibold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
            <span className="iconify text-purple-600" data-icon="mdi:format-list-bulleted" style={{ width: '20px', height: '20px' }}></span>
            任务列表
          </h2>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setAutoRefresh(!autoRefresh)}
              className={`text-xs px-3 py-1 rounded-lg transition-all duration-200 ${
                autoRefresh
                  ? 'bg-green-100 hover:bg-green-200 text-green-700'
                  : 'bg-gray-100 hover:bg-gray-200'
              }`}
            >
              <span className="iconify" data-icon={autoRefresh ? 'mdi:pause' : 'mdi:play'} style={{ width: '14px', height: '14px' }}></span>
              {autoRefresh ? ' 停止刷新' : ' 自动刷新'}
            </button>
            <button
              onClick={clearTasks}
              className="text-xs bg-red-100 hover:bg-red-200 text-red-700 px-3 py-1 rounded-lg transition-all duration-200"
            >
              <span className="iconify" data-icon="mdi:delete-sweep" style={{ width: '14px', height: '14px' }}></span>
              {' 清空显示'}
            </button>
          </div>
        </div>
        <div className="max-h-96 overflow-y-auto">
          {loading ? (
            <div className="p-8 text-center text-sm" style={{ color: 'var(--text-secondary)' }}>
              <span className="iconify animate-spin" data-icon="mdi:loading" style={{ width: '20px', height: '20px' }}></span>
              <span className="ml-2">加载任务中...</span>
            </div>
          ) : filteredTasks.length === 0 ? (
            <div className="p-8 text-center text-sm" style={{ color: 'var(--text-secondary)' }}>
              <span className="iconify" data-icon="mdi:playlist-remove" style={{ width: '20px', height: '20px' }}></span>
              <span className="ml-2">暂无任务记录</span>
            </div>
          ) : (
            <div className="divide-y" style={{ borderColor: 'var(--border-primary)' }}>
              {filteredTasks.map((task, index) => {
                const statusInfo = getStatusInfo(task.status || 'pending')
                const taskType = task.type || task.task_type || '未知'
                const vmName = task.vm_name || task.vm_uuid || '未知虚拟机'
                const hostName = task.hs_name || '未知主机'
                const description = task.description || task.message || `${taskType} - ${vmName}`
                const time = formatTime(task.created_at || task.timestamp)

                return (
                  <div
                    key={index}
                    className="p-4 transition-colors duration-200 cursor-pointer"
                    style={{
                      ':hover': { background: 'var(--bg-hover)' }
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-hover)'}
                    onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                    onClick={() => showTaskDetail(task)}
                  >
                    <div className="flex items-start gap-3">
                      <div className={`w-10 h-10 ${statusInfo.bgColor} rounded-lg flex items-center justify-center flex-shrink-0`}>
                        <span className={`iconify ${statusInfo.textColor}`} data-icon={statusInfo.icon} style={{ width: '20px', height: '20px' }}></span>
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{taskType}</span>
                            <span className={`text-xs ${statusInfo.textColor} ${statusInfo.bgColor} px-2 py-1 rounded-full font-medium`}>
                              {statusInfo.text}
                            </span>
                          </div>
                          <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{time}</span>
                        </div>
                        <div className="space-y-1">
                          <p className="text-sm" style={{ color: 'var(--text-primary)' }}>{description}</p>
                          <div className="flex items-center gap-4 text-xs" style={{ color: 'var(--text-secondary)' }}>
                            <span className="flex items-center gap-1">
                              <span className="iconify" data-icon="mdi:server" style={{ width: '14px', height: '14px' }}></span>
                              {hostName}
                            </span>
                            <span className="flex items-center gap-1">
                              <span className="iconify" data-icon="mdi:cube-outline" style={{ width: '14px', height: '14px' }}></span>
                              {vmName}
                            </span>
                          </div>
                        </div>
                      </div>
                      <span className="iconify" data-icon="mdi:chevron-right" style={{ width: '20px', height: '20px', color: 'var(--text-secondary)' }}></span>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>

      {/* 任务详情模态框 */}
      <Modal
        title={
          <div className="flex items-center gap-2">
            <span className="iconify text-purple-600" data-icon="mdi:information" style={{ width: '20px', height: '20px' }}></span>
            任务详情
          </div>
        }
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        footer={null}
        width={800}
      >
        {selectedTask && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>任务类型</label>
                <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{selectedTask.type || selectedTask.task_type || '未知'}</p>
              </div>
              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>状态</label>
                {(() => {
                  const statusInfo = getStatusInfo(selectedTask.status || 'pending')
                  return (
                    <span className={`inline-flex items-center gap-1 text-sm ${statusInfo.textColor} ${statusInfo.bgColor} px-3 py-1 rounded-full font-medium`}>
                      <span className="iconify" data-icon={statusInfo.icon} style={{ width: '16px', height: '16px' }}></span>
                      {statusInfo.text}
                    </span>
                  )
                })()}
              </div>
              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>主机</label>
                <p className="text-sm" style={{ color: 'var(--text-primary)' }}>{selectedTask.hs_name || '未知主机'}</p>
              </div>
              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>虚拟机</label>
                <p className="text-sm" style={{ color: 'var(--text-primary)' }}>{selectedTask.vm_name || selectedTask.vm_uuid || '未知虚拟机'}</p>
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>描述</label>
              <p className="text-sm" style={{ color: 'var(--text-primary)' }}>{selectedTask.description || selectedTask.message || '无描述'}</p>
            </div>

            <div>
              <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>创建时间</label>
              <p className="text-sm" style={{ color: 'var(--text-primary)' }}>{formatTime(selectedTask.created_at || selectedTask.timestamp)}</p>
            </div>

            {selectedTask.error_message && (
              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>错误信息</label>
                <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3">
                  <p className="text-sm text-red-800 dark:text-red-300 font-mono">{selectedTask.error_message}</p>
                </div>
              </div>
            )}

            <div>
              <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>完整数据</label>
              <div className="rounded-lg p-3 max-h-40 overflow-y-auto" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)' }}>
                <pre className="text-xs font-mono" style={{ color: 'var(--text-primary)' }}>{JSON.stringify(selectedTask, null, 2)}</pre>
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}

export default TaskManage
