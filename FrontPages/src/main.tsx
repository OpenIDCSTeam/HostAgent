import React from 'react'
import ReactDOM from 'react-dom/client'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'
import App from './App'
import './index.css'
// 导入国际化模块（会自动挂载到 window 对象）
import { initI18n } from './utils/i18n'
// 导入主题管理
import { ThemeProvider } from './contexts/ThemeContext'

// 设置dayjs为中文
dayjs.locale('zh-cn')

// 初始化国际化系统
initI18n().then(() => {
  console.log('i18n 初始化完成')
}).catch(err => {
  console.error('i18n 初始化失败:', err)
})

// 渲染React应用
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    {/* 主题管理 */}
    <ThemeProvider>
      {/* Ant Design中文配置 */}
      <ConfigProvider locale={zhCN}>
        <App />
      </ConfigProvider>
    </ThemeProvider>
  </React.StrictMode>,
)
