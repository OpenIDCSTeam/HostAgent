export const VM_STATUS_MAP: Record<string, { text: string; color: string; className?: string; pulse?: boolean }> = {
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
