import {useState, useEffect} from 'react'
import {Outlet, useNavigate, useLocation} from 'react-router-dom'
import {Layout, Menu, Avatar, Dropdown, Badge, Button, Input, Tooltip} from 'antd'
import {
    DashboardOutlined,
    CloudServerOutlined,
    UserOutlined,
    SettingOutlined,
    FileTextOutlined,
    BellOutlined,
    LogoutOutlined,
    MenuFoldOutlined,
    MenuUnfoldOutlined,
    GlobalOutlined,
    SwapOutlined,
    TranslationOutlined,
    SunOutlined,
    MoonOutlined,
    BgColorsOutlined,
    RadiusSettingOutlined,
    FormatPainterOutlined,
    CheckOutlined,
    SearchOutlined,
    QuestionCircleOutlined,
    AppstoreOutlined,
    ControlOutlined,
} from '@ant-design/icons'
import {useUserStore} from '@/utils/data.ts'
import api from '@/utils/apis.ts'
import { changeLanguage, getAvailableLanguages, getCurrentLanguage } from '@/utils/i18n.ts'
import { useTheme } from '@/contexts/ThemeContext'
import type {MenuProps} from 'antd'

const {Header, Sider, Content} = Layout

/**
 * 主布局组件
 * 包含侧边栏、顶部导航和内容区域
 * 风格对齐小黑云财务前端 AdminLayout
 */
function MainLayout() {
    const navigate = useNavigate()
    const location = useLocation()
    const {user, logout, setUser} = useUserStore()
    const { theme: currentTheme, toggleTheme, transparentMode, toggleTransparentMode, roundedMode, toggleRoundedMode } = useTheme()
    const [collapsed, setCollapsed] = useState(false)
    const [notifications, setNotifications] = useState(0)
    const [currentLang, setCurrentLang] = useState('zh-cn')
    const [languages, setLanguages] = useState<any[]>([])

    useEffect(() => {
        if (!user || user.is_admin === undefined) {
            api.getCurrentUser().then(res => {
                if (res.code === 200 && res.data) {
                    setUser(res.data)
                }
            }).catch(() => {})
        }
    }, []) // eslint-disable-line react-hooks/exhaustive-deps

    useEffect(() => {
        setCurrentLang(getCurrentLanguage())
        setLanguages(getAvailableLanguages())
        const handleLangChange = (e: any) => { setCurrentLang(e.detail.language) }
        const handleLangsLoaded = (e: any) => {
            setLanguages(e.detail.languages)
            setCurrentLang(getCurrentLanguage())
        }
        window.addEventListener('languageChanged', handleLangChange)
        window.addEventListener('languagesLoaded', handleLangsLoaded)
        return () => {
            window.removeEventListener('languageChanged', handleLangChange)
            window.removeEventListener('languagesLoaded', handleLangsLoaded)
        }
    }, [])

    // 语言菜单项
    const languageMenuItems: MenuProps['items'] = (languages.length > 0 ? languages : [
        { code: 'zh-cn', native: '简体中文' },
        { code: 'en-us', native: 'English' }
    ]).map(lang => ({
        key: lang.code,
        label: lang.native || lang.name,
        icon: lang.code === currentLang ? <CheckOutlined /> : undefined,
    }))

    // 用户界面菜单项
    const userMenuItems: MenuProps['items'] = [
        { key: '/user/dashboard', icon: <DashboardOutlined/>, label: '资源概览' },
        { key: '/user/vms',       icon: <CloudServerOutlined/>, label: '实例管理' },
        { key: '/user/proxys',    icon: <GlobalOutlined/>,      label: '反向代理' },
        { key: '/user/nat',       icon: <SwapOutlined/>,        label: '端口转发' },
        { key: '/profile',        icon: <UserOutlined/>,        label: '个人资料' },
    ]

    // 系统界面菜单项（仅管理员可见）
    const adminMenuItems: MenuProps['items'] = [
        { key: '/dashboard',  icon: <DashboardOutlined/>,   label: '系统概览' },
        { key: '/hosts',      icon: <CloudServerOutlined/>, label: '主机管理' },
        { key: '/vms',        icon: <CloudServerOutlined/>, label: '实例管理' },
        { key: '/web-proxys', icon: <GlobalOutlined/>,      label: '反向代理' },
        { key: '/nat-rules',  icon: <SwapOutlined/>,        label: '端口转发' },
        { key: '/users',      icon: <UserOutlined/>,        label: '用户管理' },
        { key: '/logs',       icon: <FileTextOutlined/>,    label: '日志查看' },
        { key: '/settings',   icon: <SettingOutlined/>,     label: '系统设置' },
    ]

    const menuItems: MenuProps['items'] = user?.is_admin
        ? [
            {
                key: 'user-interface',
                icon: <AppstoreOutlined />,
                label: '用户空间',
                children: userMenuItems,
            },
            {
                key: 'system-interface',
                icon: <ControlOutlined />,
                label: '系统空间',
                children: adminMenuItems,
            },
          ]
        : userMenuItems

    // 用户下拉菜单
    const dropdownMenuItems: MenuProps['items'] = [
        { key: 'profile',  icon: <UserOutlined/>,  label: '个人资料', onClick: () => navigate('/profile') },
        { key: 'settings', icon: <SettingOutlined/>, label: '设置',   onClick: () => navigate('/settings') },
        { type: 'divider' },
        { key: 'logout',   icon: <LogoutOutlined/>, label: '退出登录', onClick: () => { logout(); navigate('/login') } },
    ]

    const handleMenuClick: MenuProps['onClick'] = ({key}) => { navigate(key) }

    // 主题面板下拉内容
    const themePanelContent = (
        <div style={{
            background: currentTheme === 'dark' ? '#1a1d23' : '#fff',
            border: currentTheme === 'dark' ? '1px solid rgba(255,255,255,0.08)' : '1px solid #f0f0f0',
            borderRadius: 12,
            boxShadow: '0 8px 32px rgba(0,0,0,0.18)',
            padding: '8px',
            minWidth: 180,
        }}>
            <div style={{
                padding: '4px 8px 8px',
                fontSize: 11,
                fontWeight: 600,
                letterSpacing: '0.08em',
                color: currentTheme === 'dark' ? 'rgba(255,255,255,0.35)' : '#999',
                textTransform: 'uppercase',
            }}>主题设置</div>

            {/* 暗黑模式 */}
            <div onClick={toggleTheme} className="theme-menu-item" style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '8px 10px', borderRadius: 8, cursor: 'pointer', transition: 'background 0.2s',
            }}>
                {currentTheme === 'dark'
                    ? <SunOutlined style={{ fontSize: 16, color: '#faad14' }} />
                    : <MoonOutlined style={{ fontSize: 16, color: '#595959' }} />}
                <span style={{ flex: 1, fontSize: 14, color: currentTheme === 'dark' ? '#e6e9ef' : '#333' }}>
                    {currentTheme === 'dark' ? '浅色模式' : '深色模式'}
                </span>
                {currentTheme === 'dark' && <CheckOutlined style={{ fontSize: 12, color: '#faad14' }} />}
            </div>

            {/* 透明模式 */}
            <div onClick={toggleTransparentMode} className="theme-menu-item" style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '8px 10px', borderRadius: 8, cursor: 'pointer', transition: 'background 0.2s',
            }}>
                <BgColorsOutlined style={{ fontSize: 16, color: transparentMode ? '#6968fd' : (currentTheme === 'dark' ? '#888' : '#595959') }} />
                <span style={{ flex: 1, fontSize: 14, color: currentTheme === 'dark' ? '#e6e9ef' : '#333' }}>透明模式</span>
                {transparentMode && <CheckOutlined style={{ fontSize: 12, color: '#6968fd' }} />}
            </div>

            {/* 圆角模式 */}
            <div onClick={toggleRoundedMode} className="theme-menu-item" style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '8px 10px', borderRadius: 8, cursor: 'pointer', transition: 'background 0.2s',
            }}>
                <RadiusSettingOutlined style={{ fontSize: 16, color: roundedMode ? '#52c41a' : (currentTheme === 'dark' ? '#888' : '#595959') }} />
                <span style={{ flex: 1, fontSize: 14, color: currentTheme === 'dark' ? '#e6e9ef' : '#333' }}>圆角模式</span>
                {roundedMode && <CheckOutlined style={{ fontSize: 12, color: '#52c41a' }} />}
            </div>
        </div>
    )

    return (
        <Layout style={{ minHeight: '100vh', height: '100vh', overflow: 'hidden' }}>

            {/* ===== 顶部导航（全宽深色，对齐小黑云 AdminLayout header） ===== */}
            <Header style={{
                background: 'linear-gradient(135deg, #1a1d23 0%, #2b2f36 50%, #1a1d23 100%)',
                borderBottom: '1px solid rgba(255,255,255,0.08)',
                boxShadow: '0 2px 8px rgba(0,0,0,0.15), 0 1px 2px rgba(0,0,0,0.1)',
                color: '#e6e9ef',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 16,
                padding: '0 20px',
                height: 64,
                position: 'sticky',
                top: 0,
                zIndex: 1000,
                backdropFilter: 'blur(10px)',
            }}>
                {/* 左侧：折叠按钮 + 品牌 */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                    <Button
                        type="text"
                        icon={collapsed ? <MenuUnfoldOutlined/> : <MenuFoldOutlined/>}
                        onClick={() => setCollapsed(!collapsed)}
                        style={{
                            width: 40, height: 40,
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            borderRadius: 8, color: '#e6e9ef',
                            border: 'none', boxShadow: 'none',
                            transition: 'all 0.3s cubic-bezier(0.4,0,0.2,1)',
                        }}
                    />
                    {/* 品牌 Logo + 名称 */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                        <div style={{
                            width: 38, height: 38, borderRadius: 10,
                            background: 'linear-gradient(135deg, #6968fd 0%, #8b8aff 100%)',
                            color: '#fff', fontWeight: 700, fontSize: 15,
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            boxShadow: '0 4px 12px rgba(105,104,253,0.4)',
                            transition: 'all 0.3s cubic-bezier(0.4,0,0.2,1)',
                            flexShrink: 0,
                        }}>
                            OI
                        </div>
                        {!collapsed && (
                            <span style={{
                                fontWeight: 600, fontSize: 16, letterSpacing: '0.3px',
                                background: 'linear-gradient(135deg, #ffffff 0%, #e6e9ef 100%)',
                                WebkitBackgroundClip: 'text',
                                WebkitTextFillColor: 'transparent',
                                backgroundClip: 'text',
                                whiteSpace: 'nowrap',
                            }}>
                                OpenIDCS
                            </span>
                        )}
                    </div>
                </div>

                {/* 右侧操作区 */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginLeft: 'auto' }}>

                    {/* 搜索框 */}
                    <Input
                        placeholder="搜索功能..."
                        prefix={<SearchOutlined style={{ color: 'rgba(255,255,255,0.45)', fontSize: 14 }} />}
                        style={{
                            background: 'rgba(255,255,255,0.04)',
                            border: '1px solid rgba(255,255,255,0.12)',
                            borderRadius: 6,
                            height: 36,
                            width: 220,
                            color: '#e6e9ef',
                        }}
                        styles={{ input: { background: 'transparent', color: '#e6e9ef' } }}
                    />

                    {/* 主题切换 */}
                    <Dropdown
                        placement="bottomRight"
                        overlayStyle={{ zIndex: 20000 }}
                        getPopupContainer={() => document.body}
                        dropdownRender={() => themePanelContent}
                    >
                        <Tooltip title="主题设置">
                            <Button
                                type="text"
                                icon={<FormatPainterOutlined style={{ fontSize: 16 }} />}
                                style={{
                                    color: (currentTheme === 'dark' || transparentMode || roundedMode) ? '#8b8aff' : '#e6e9ef',
                                    border: 'none', boxShadow: 'none',
                                    width: 36, height: 36,
                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                    borderRadius: 8,
                                }}
                            />
                        </Tooltip>
                    </Dropdown>

                    {/* 语言切换 */}
                    <Dropdown
                        menu={{ items: languageMenuItems, onClick: ({key}) => changeLanguage(key) }}
                        placement="bottomRight"
                        overlayStyle={{ zIndex: 20000 }}
                        getPopupContainer={() => document.body}
                    >
                        <Tooltip title="切换语言">
                            <Button
                                type="text"
                                icon={<TranslationOutlined style={{ fontSize: 16 }} />}
                                style={{
                                    color: '#e6e9ef', border: 'none', boxShadow: 'none',
                                    width: 36, height: 36,
                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                    borderRadius: 8,
                                }}
                            />
                        </Tooltip>
                    </Dropdown>

                    {/* 帮助 */}
                    <Tooltip title="帮助">
                        <Button
                            type="text"
                            icon={<QuestionCircleOutlined style={{ fontSize: 16 }} />}
                            style={{
                                color: '#e6e9ef', border: 'none', boxShadow: 'none',
                                width: 36, height: 36,
                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                                borderRadius: 8,
                            }}
                        />
                    </Tooltip>

                    {/* 通知 */}
                    <Tooltip title="消息中心">
                        <Badge count={notifications} size="small">
                            <Button
                                type="text"
                                icon={<BellOutlined style={{ fontSize: 16 }} />}
                                onClick={() => setNotifications(0)}
                                style={{
                                    color: '#e6e9ef', border: 'none', boxShadow: 'none',
                                    width: 36, height: 36,
                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                    borderRadius: 8,
                                }}
                            />
                        </Badge>
                    </Tooltip>

                    {/* 用户信息 */}
                    <Dropdown
                        menu={{ items: dropdownMenuItems }}
                        placement="bottomRight"
                        overlayStyle={{ zIndex: 20000 }}
                        getPopupContainer={() => document.body}
                    >
                        <div style={{
                            display: 'flex', alignItems: 'center', gap: 10,
                            cursor: 'pointer', padding: '6px 12px', borderRadius: 6,
                            transition: 'all 0.2s cubic-bezier(0.4,0,0.2,1)',
                        }}
                        className="header-user-info"
                        >
                            <Avatar
                                icon={<UserOutlined/>}
                                size="small"
                                style={{
                                    background: 'linear-gradient(135deg, #6968fd, #8b8aff)',
                                    border: '2px solid rgba(105,104,253,0.3)',
                                }}
                            />
                            <span style={{ fontWeight: 500, fontSize: 14, color: '#e6e9ef' }}>
                                {user?.username || '用户'}
                            </span>
                        </div>
                    </Dropdown>
                </div>
            </Header>

            {/* ===== 主体区域（侧栏 + 内容） ===== */}
            <Layout style={{ height: 'calc(100vh - 64px)', overflow: 'hidden' }}>

                {/* 侧边栏（贴边深色，对齐小黑云 sider） */}
                <Sider
                    trigger={null}
                    collapsible
                    collapsed={collapsed}
                    width={230}
                    collapsedWidth={60}
                    className="main-sider"
                    style={{
                        background: '#0f1115',
                        height: '100%',
                        overflow: 'auto',
                    }}
                >
                    <Menu
                        mode="inline"
                        className="main-menu"
                        selectedKeys={[location.pathname]}
                        defaultOpenKeys={user?.is_admin ? ['user-interface', 'system-interface'] : []}
                        items={menuItems}
                        onClick={handleMenuClick}
                        style={{
                            background: '#0f1115',
                            border: 'none',
                            color: 'rgba(255,255,255,0.7)',
                            paddingTop: 8,
                        }}
                    />
                </Sider>

                {/* 内容区域 */}
                <Content
                    className={`main-content main-layout-content ${currentTheme === 'dark' ? 'grid-background' : ''}`}
                    style={{
                        padding: 24,
                        minHeight: 280,
                        overflow: 'auto',
                    }}
                >
                    <Outlet/>
                </Content>
            </Layout>
        </Layout>
    )
}

export default MainLayout
