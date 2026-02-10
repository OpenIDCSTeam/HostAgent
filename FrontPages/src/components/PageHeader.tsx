import React from 'react'

/**
 * 页面标题组件属性
 */
interface PageHeaderProps {
  /** 图标 - 可以是 React 节点或 iconify 图标名称 */
  icon: React.ReactNode
  /** 主标题 */
  title: string
  /** 副标题/描述 */
  subtitle: string
  /** 操作按钮区域（可选） */
  actions?: React.ReactNode
  /** 额外的 className（可选） */
  className?: string
}

/**
 * 统一的页面标题组件
 * 布局：图标（占两行）| 主标题 + 副标题 | 操作按钮区域（占两行）
 */
function PageHeader({ icon, title, subtitle, actions, className = '' }: PageHeaderProps) {
  return (
    <div className={`page-header-container mb-6 ${className}`}>
      <div className="flex items-center justify-between">
        {/* 左侧：图标 + 标题 */}
        <div className="flex items-center gap-4">
          {/* 图标区域 - 占两行高度，垂直居中 */}
          <div className="page-header-icon flex-shrink-0 w-14 h-14 rounded-xl flex items-center justify-center"
            style={{
              background: 'linear-gradient(135deg, #3b82f6 0%, #6366f1 100%)',
              boxShadow: '0 4px 12px rgba(59, 130, 246, 0.25)'
            }}
          >
            <span className="text-2xl flex items-center justify-center" style={{ color: '#ffffff' }}>
              {icon}
            </span>
          </div>
          
          {/* 标题区域 - 主标题 + 副标题 */}
          <div className="page-header-titles">
            <h1 className="text-2xl font-bold m-0" style={{ color: 'var(--text-primary)' }}>
              {title}
            </h1>
            <p className="text-sm mt-1 m-0" style={{ color: 'var(--text-secondary)' }}>
              {subtitle}
            </p>
          </div>
        </div>
        
        {/* 右侧：操作按钮区域 - 占两行高度，垂直居中 */}
        {actions && (
          <div className="page-header-actions flex items-center gap-3 flex-shrink-0">
            {actions}
          </div>
        )}
      </div>
    </div>
  )
}

export default PageHeader
