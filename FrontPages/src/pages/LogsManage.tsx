import { useEffect, useState } from 'react'
import { Select, Button, Card, Statistic, Modal, message } from 'antd'
import { 
  ReloadOutlined, 
  PlayCircleOutlined, 
  PauseCircleOutlined,
  DeleteOutlined,
  FileTextOutlined,
  AlertOutlined,
  InfoCircleOutlined,
  BugOutlined,
  EyeOutlined
} from '@ant-design/icons'
import api from '@/utils/apis.ts'
import PageHeader from '@/components/PageHeader'

/**
 * 日志数据接口
 */
interface Log {
  level: string // 日志级别
  message: string // 日志消息
  host: string // 主机名称
  timestamp: string // 时间戳
  actions: string // 操作类型
  success?: boolean // 是否成功
  results?: any // 操作结果
  execute?: string // 错误堆栈
  content?: string // 消息内容（备用字段）
}

/**
 * 日志查看页面
 */
function LogsManage() {
  // 状态管理
  const [logs, setLogs] = useState<Log[]>([]) // 所有日志
  const [filteredLogs, setFilteredLogs] = useState<Log[]>([]) // 过滤后的日志
  const [hosts, setHosts] = useState<string[]>([]) // 主机列表
  const [loading, setLoading] = useState(false) // 加载状态
  const [autoRefresh, setAutoRefresh] = useState(false) // 自动刷新状态
  const [selectedLog, setSelectedLog] = useState<Log | null>(null) // 选中的日志
  const [filters, setFilters] = useState({
    host: '', // 主机筛选
    level: '', // 日志级别筛选
    limit: 100, // 显示条数
  })
  const [statistics, setStatistics] = useState({
    ERROR: 0,
    WARNING: 0,
    INFO: 0,
    DEBUG: 0,
  })

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
   * 加载日志列表
   */
  const loadLogs = async () => {
    try {
      setLoading(true)
      const params: any = {
        limit: filters.limit,
      }
      if (filters.host) {
        params.hs_name = filters.host
      }
      
      const result = await api.getLoggerDetail()
      if (result && result.code === 200) {
        const logData = result.data || []
        setLogs(logData)
        filterLogs(logData, filters.level)
        updateStatistics(logData)
      }
    } catch (error) {
      console.error('加载日志失败:', error)
    } finally {
      setLoading(false)
    }
  }

  /**
   * 过滤日志
   */
  const filterLogs = (logData: Log[], level: string) => {
    if (!level) {
      setFilteredLogs(logData)
    } else {
      setFilteredLogs(logData.filter(log => log.level === level))
    }
  }

  /**
   * 更新统计信息
   */
  const updateStatistics = (logData: Log[]) => {
    const stats = {
      ERROR: 0,
      WARNING: 0,
      INFO: 0,
      DEBUG: 0,
    }

    logData.forEach(log => {
      const level = (log.level || 'INFO').toUpperCase()
      if (level in stats) {
        stats[level as keyof typeof stats]++
      }
    })

    setStatistics(stats)
  }

  /**
   * 切换自动刷新
   */
  const toggleAutoRefresh = () => {
    setAutoRefresh(!autoRefresh)
  }

  /**
   * 清空日志
   */
  const clearLogs = () => {
    Modal.confirm({
      title: '确认清空日志',
      content: filters.host ? `确定要清空主机 "${filters.host}" 的所有日志吗？此操作不可恢复！` : '确定要清空所有日志吗？此操作不可恢复！',
      okText: '确认清空',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          setLoading(true)
          const result = await api.clearLogs(filters.host)
          if (result && result.code === 200) {
            // 清空成功后，清空前端显示
            setLogs([])
            setFilteredLogs([])
            setStatistics({
              ERROR: 0,
              WARNING: 0,
              INFO: 0,
              DEBUG: 0,
            })
            message.success('日志清空成功')
          } else {
            message.error(result?.msg || '清空日志失败')
          }
        } catch (error) {
          console.error('清空日志失败:', error)
          message.error('清空日志失败')
        } finally {
          setLoading(false)
        }
      },
    })
  }

  /**
   * 获取日志级别颜色
   */
  const getLevelColor = (level: string) => {
    switch (level?.toUpperCase()) {
      case 'ERROR':
        return 'bg-red-500'
      case 'WARNING':
        return 'bg-yellow-500'
      case 'INFO':
        return 'bg-blue-500'
      case 'DEBUG':
        return 'bg-gray-500'
      default:
        return 'bg-gray-400'
    }
  }

  /**
   * 获取日志级别文本颜色
   */
  const getLevelTextColor = (level: string) => {
    switch (level?.toUpperCase()) {
      case 'ERROR':
        return 'text-red-600 dark:text-red-400'
      case 'WARNING':
        return 'text-yellow-600 dark:text-yellow-400'
      case 'INFO':
        return 'text-blue-600 dark:text-blue-400'
      case 'DEBUG':
        return ''
      default:
        return ''
    }
  }

  // 初始化加载
  useEffect(() => {
    loadHosts()
    loadLogs()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // 监听筛选条件变化
  useEffect(() => {
    loadLogs()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters.host, filters.limit])

  // 监听日志级别筛选
  useEffect(() => {
    filterLogs(logs, filters.level)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters.level])

  // 自动刷新
  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | null = null
    if (autoRefresh) {
      interval = setInterval(() => {
        loadLogs()
      }, 5000)
    }
    return () => {
      if (interval) clearInterval(interval)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoRefresh, filters])

  return (
    <div className="p-6 h-screen flex flex-col">
      {/* 页面标题 */}
      <PageHeader
        icon={<FileTextOutlined />}
        title="系统日志管理"
        subtitle="查看系统运行日志和事件记录"
        className="flex-shrink-0 mb-4"
      />

      {/* 过滤器 */}
      <div className="glass-card p-4 mb-4 flex-shrink-0">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-sm font-medium mb-1">主机筛选</label>
            <Select
              className="w-full"
              placeholder="全部主机"
              allowClear
              value={filters.host || undefined}
              onChange={(value) => setFilters({ ...filters, host: value || '' })}
            >
              {hosts.map(host => (
                <Select.Option key={host} value={host}>{host}</Select.Option>
              ))}
            </Select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">日志级别</label>
            <Select
              className="w-full"
              placeholder="全部级别"
              allowClear
              value={filters.level || undefined}
              onChange={(value) => setFilters({ ...filters, level: value || '' })}
            >
              <Select.Option value="ERROR">错误</Select.Option>
              <Select.Option value="WARNING">警告</Select.Option>
              <Select.Option value="INFO">信息</Select.Option>
              <Select.Option value="DEBUG">调试</Select.Option>
            </Select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">显示条数</label>
            <Select
              className="w-full"
              value={filters.limit}
              onChange={(value) => setFilters({ ...filters, limit: value })}
            >
              <Select.Option value={50}>50条</Select.Option>
              <Select.Option value={100}>100条</Select.Option>
              <Select.Option value={200}>200条</Select.Option>
              <Select.Option value={500}>500条</Select.Option>
            </Select>
          </div>
          <div className="flex items-end">
            <Button
              type="primary"
              icon={<ReloadOutlined />}
              onClick={loadLogs}
              loading={loading}
              className="w-full"
            >
              刷新
            </Button>
          </div>
        </div>
      </div>

      {/* 统计信息 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4 flex-shrink-0">
        <Card className="glass-card shadow-sm hover:shadow-md transition-shadow">
          <Statistic
            title={<span>错误</span>}
            value={statistics.ERROR}
            prefix={<AlertOutlined className="text-red-600 dark:text-red-400" />}
            valueStyle={{ color: 'var(--error)' }}
          />
        </Card>
        <Card className="glass-card shadow-sm hover:shadow-md transition-shadow">
          <Statistic
            title={<span>警告</span>}
            value={statistics.WARNING}
            prefix={<AlertOutlined className="text-yellow-600 dark:text-yellow-400" />}
            valueStyle={{ color: 'var(--warning)' }}
          />
        </Card>
        <Card className="glass-card shadow-sm hover:shadow-md transition-shadow">
          <Statistic
            title={<span>信息</span>}
            value={statistics.INFO}
            prefix={<InfoCircleOutlined className="text-blue-600 dark:text-blue-400" />}
            valueStyle={{ color: 'var(--info)' }}
          />
        </Card>
        <Card className="glass-card shadow-sm hover:shadow-md transition-shadow">
          <Statistic
            title={<span>调试</span>}
            value={statistics.DEBUG}
            prefix={<BugOutlined />}
            valueStyle={{ color: 'var(--text-secondary)' }}
          />
        </Card>
      </div>

      {/* 两列布局：左边日志列表，右边详情 */}
      <div className="flex gap-4 flex-1 min-h-0">
        {/* 左侧：日志列表 */}
        <div className="glass-card flex-1 flex flex-col">
          <div className="p-4 border-b flex items-center justify-between flex-shrink-0" style={{ borderColor: 'var(--border-primary, rgba(0,0,0,0.08))' }}>
            <h2 className="text-base font-semibold flex items-center gap-2">
              <FileTextOutlined className="text-blue-600" />
              日志记录
            </h2>
            <div className="flex items-center gap-2">
              <Button
                size="small"
                icon={autoRefresh ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
                onClick={toggleAutoRefresh}
                style={autoRefresh ? { background: 'rgba(34,197,94,0.15)', color: '#22c55e', borderColor: 'rgba(34,197,94,0.3)' } : {}}
              >
                {autoRefresh ? '停止刷新' : '自动刷新'}
              </Button>
              <Button
                size="small"
                danger
                icon={<DeleteOutlined />}
                onClick={clearLogs}
                loading={loading}
              >
                清空日志
              </Button>
            </div>
          </div>
          <div className="flex-1 overflow-y-auto">
            {loading && filteredLogs.length === 0 ? (
              <div className="p-8 text-center text-sm" style={{ color: 'var(--text-secondary)' }}>
                <ReloadOutlined spin className="text-xl" />
                <span className="ml-2">加载日志中...</span>
              </div>
            ) : filteredLogs.length === 0 ? (
              <div className="p-8 text-center text-sm" style={{ color: 'var(--text-secondary)' }}>
                <FileTextOutlined className="text-xl" />
                <span className="ml-2">暂无日志记录</span>
              </div>
            ) : (
              <div className="divide-y" style={{ borderColor: 'var(--border-primary, rgba(0,0,0,0.08))' }}>
                {filteredLogs.map((log, index) => {
                  const level = log.level || 'INFO'
                  const timestamp = log.timestamp || new Date().toISOString()
                  const time = new Date(timestamp).toLocaleString('zh-CN')
                  const message = log.message || log.content || '无消息内容'
                  const host = log.host || '系统'
                  const actions = log.actions || '未知操作'
                  const success = log.success !== undefined ? (log.success ? '成功' : '失败') : '未知'
                  const successColor = log.success === true ? 'text-green-600' : (log.success === false ? 'text-red-600' : '')
                  const isSelected = selectedLog === log

                  return (
                    <div 
                      key={index} 
                    className={`p-4 cursor-pointer transition-colors`}
                      style={isSelected ? { borderLeft: '4px solid #6968fd', background: 'rgba(105,104,253,0.06)' } : {}}
                      onClick={() => setSelectedLog(log)}
                    >
                      <div className="flex items-start gap-3">
                        <div className={`w-2 h-2 ${getLevelColor(level)} rounded-full mt-2 flex-shrink-0`}></div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="text-xs font-semibold">{host}</span>
                              <span className={`text-xs ${getLevelTextColor(level)} font-medium uppercase`}>{level}</span>
                              <span className="text-xs font-medium text-blue-600 dark:text-blue-400  px-2 py-1 rounded">{actions}</span>
                              <span className={`text-xs ${successColor} dark:brightness-125 font-medium`}>{success}</span>
                            </div>
                            <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{time}</span>
                          </div>
                          <p className="text-sm break-words line-clamp-2">{message}</p>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>

        {/* 右侧：日志详情 */}
        <div className="glass-card w-1/2 flex flex-col">
          <div className="p-4 border-b flex-shrink-0" style={{ borderColor: 'var(--border-primary, rgba(0,0,0,0.08))' }}>
            <h2 className="text-base font-semibold flex items-center gap-2">
              <EyeOutlined className="text-blue-600" />
              日志详情
            </h2>
          </div>
          <div className="flex-1 overflow-y-auto p-4">
            {selectedLog ? (
              <div className="space-y-4">
                {/* 基本信息 */}
                  <div className="rounded-lg p-4" style={{ background: 'var(--bg-card, rgba(0,0,0,0.03))', border: '1px solid var(--border-primary, rgba(0,0,0,0.06))' }}>
                  <h3 className="text-sm font-semibold mb-3">基本信息</h3>
                  <div className="space-y-2">
                    <div className="flex items-start">
                      <span className="text-xs font-medium w-20 flex-shrink-0" style={{ color: 'var(--text-secondary)' }}>主机:</span>
                      <span className="text-xs">{selectedLog.host || '系统'}</span>
                    </div>
                    <div className="flex items-start">
                      <span className="text-xs font-medium w-20 flex-shrink-0" style={{ color: 'var(--text-secondary)' }}>级别:</span>
                      <span className={`text-xs ${getLevelTextColor(selectedLog.level || 'INFO')} font-medium uppercase`}>
                        {selectedLog.level || 'INFO'}
                      </span>
                    </div>
                    <div className="flex items-start">
                      <span className="text-xs font-medium w-20 flex-shrink-0" style={{ color: 'var(--text-secondary)' }}>操作:</span>
                      <span className="text-xs">{selectedLog.actions || '未知操作'}</span>
                    </div>
                    <div className="flex items-start">
                      <span className="text-xs font-medium w-20 flex-shrink-0" style={{ color: 'var(--text-secondary)' }}>状态:</span>
                      <span className={`text-xs font-medium ${
                        selectedLog.success === true ? 'text-green-600' : 
                        selectedLog.success === false ? 'text-red-600' : ''
                      }`}>
                        {selectedLog.success !== undefined ? (selectedLog.success ? '成功' : '失败') : '未知'}
                      </span>
                    </div>
                    <div className="flex items-start">
                      <span className="text-xs font-medium w-20 flex-shrink-0" style={{ color: 'var(--text-secondary)' }}>时间:</span>
                      <span className="text-xs">
                        {new Date(selectedLog.timestamp || new Date().toISOString()).toLocaleString('zh-CN')}
                      </span>
                    </div>
                  </div>
                </div>

                {/* 消息内容 */}
                  <div className="rounded-lg p-4" style={{ background: 'var(--bg-card, rgba(0,0,0,0.03))', border: '1px solid var(--border-primary, rgba(0,0,0,0.06))' }}>
                  <h3 className="text-sm font-semibold mb-3">消息内容</h3>
                  <p className="text-sm whitespace-pre-wrap break-words">
                    {selectedLog.message || selectedLog.content || '无消息内容'}
                  </p>
                </div>

                {/* 操作结果 */}
                {selectedLog.results && Object.keys(selectedLog.results).length > 0 && (
                  <div className="rounded-lg p-4" style={{ background: 'rgba(139,92,246,0.08)', border: '1px solid rgba(139,92,246,0.2)' }}>
                    <h3 className="text-sm font-semibold mb-3 flex items-center gap-2" style={{ color: '#8b5cf6' }}>
                      <EyeOutlined />
                      操作结果
                    </h3>
                    <pre className="text-xs p-3 rounded whitespace-pre-wrap break-words overflow-x-auto" style={{ background: 'var(--bg-card, rgba(255,255,255,0.8))', border: '1px solid rgba(139,92,246,0.2)' }}>
                      {JSON.stringify(selectedLog.results, null, 2)}
                    </pre>
                  </div>
                )}

                {/* 错误堆栈 */}
                {selectedLog.execute && selectedLog.execute !== 'None' && selectedLog.execute.trim() !== '' && (
                  <div className="rounded-lg p-4" style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)' }}>
                    <h3 className="text-sm font-semibold mb-3 flex items-center gap-2" style={{ color: '#ef4444' }}>
                      <BugOutlined />
                      错误堆栈
                    </h3>
                    <pre className="text-xs p-3 rounded whitespace-pre-wrap break-words font-mono overflow-x-auto" style={{ color: '#ef4444', background: 'var(--bg-card, rgba(255,255,255,0.8))', border: '1px solid rgba(239,68,68,0.2)' }}>
                      {selectedLog.execute}
                    </pre>
                  </div>
                )}
              </div>
            ) : (
              <div className="h-full flex items-center justify-center" style={{ color: 'var(--text-secondary)' }}>
                <div className="text-center">
                  <InfoCircleOutlined className="text-4xl mb-2" />
                  <p className="text-sm">请从左侧选择一条日志查看详情</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default LogsManage