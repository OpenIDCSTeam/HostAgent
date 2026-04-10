import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import ErrorBoundary from './components/ErrorBoundary'
import MainLayout from './pages/MainLayout'
import Login from './pages/UserLogins'
import Register from './pages/UserPostin'
import ResetPassword from './pages/UserPasswd'
import Dashboard from './pages/Dashboards'
import VMs from './pages/DockManage'
import VMDetail from './pages/DockDetail'
import Hosts from './pages/HostManage'
import Users from './pages/UserManage'
import Tasks from './pages/TaskManage'
import Logs from './pages/LogsManage'
import Settings from './pages/CoreConfig'
import Profile from './pages/UserConfig'
import WebProxys from './pages/HttpProxys'
import UserDashboard from './user/UserPanels'
import UserVMs from './pages/DockManage'
import UserWebProxys from './user/UserProxys.tsx'
import UserNAT from './user/PortManage'
import { useUserStore } from '@/utils/data.ts'

// 路由守卫：未登录时重定向到登录页
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, user } = useUserStore()
  // 同时检查 user 和 isAuthenticated，避免 persist 异步写入导致误判
  if (!isAuthenticated && !user) {
    return <Navigate to="/login" replace />
  }
  return <>{children}</>
}

/**
 * 应用主组件
 * 配置路由和页面导航
 */
function App() {
  const { user } = useUserStore()
  const defaultRoute = user?.is_admin ? '/dashboard' : '/user/dashboard'

  return (
    <ErrorBoundary>
    <BrowserRouter>
      <Routes>
        {/* 公开路由 - 无需登录 */}
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        
        {/* 受保护路由 - 需要登录 */}
        <Route path="/" element={<ProtectedRoute><MainLayout /></ProtectedRoute>}>
          <Route index element={<Navigate to={defaultRoute} replace />} />
          
          {/* 系统界面 (管理员) */}
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="hosts" element={<Hosts />} />
          <Route path="hosts/:hostName/vms" element={<VMs />} />
          <Route path="hosts/:hostName/vms/:uuid" element={<VMDetail />} />
          <Route path="vms" element={<UserVMs />} /> {/* 全局容器管理 */}
          <Route path="users" element={<Users />} />
          <Route path="tasks" element={<Tasks />} />
          <Route path="logs" element={<Logs />} />
          <Route path="settings" element={<Settings />} />
          <Route path="web-proxys" element={<WebProxys />} />
          <Route path="nat-rules" element={<UserNAT />} /> {/* 暂时指向UserNAT，后续可能需要管理员版的NAT管理 */}

          {/* 用户界面 */}
          <Route path="user">
            <Route path="dashboard" element={<UserDashboard />} />
            <Route path="vms" element={<UserVMs />} />
            <Route path="proxys" element={<UserWebProxys />} />
            <Route path="nat" element={<UserNAT />} />
          </Route>

          <Route path="profile" element={<Profile />} />
        </Route>
        
        {/* 404重定向 */}
        <Route path="*" element={<Navigate to={defaultRoute} replace />} />
      </Routes>
    </BrowserRouter>
    </ErrorBoundary>
  )
}

export default App
