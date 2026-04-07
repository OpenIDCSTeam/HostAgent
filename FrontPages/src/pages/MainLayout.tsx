import {useState, useEffect} from 'react'
import {Outlet, useNavigate, useLocation} from 'react-router-dom'
import {Layout, Menu, Avatar, Dropdown, Badge, Button} from 'antd'
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
 */
function MainLayout() {
    const navigate = useNavigate()
    const location = useLocation()
    const {user, logout, setUser} = useUserStore()
    const { theme: currentTheme, toggleTheme, transparentMode, toggleTransparentMode, roundedMode, toggleRoundedMode } = useTheme() // 主题管理
    const [collapsed, setCollapsed] = useState(false) // 侧边栏折叠状态
    const [notifications, setNotifications] = useState(0) // 通知数量
    const [currentLang, setCurrentLang] = useState('zh-cn')
    const [languages, setLanguages] = useState<any[]>([])

    // 兜底：如果用户信息缺失（如首次登录后端未返回user_info），主动获取
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
        // 初始化语言状态
        setCurrentLang(getCurrentLanguage())
        setLanguages(getAvailableLanguages())

        // 监听语言变更事件
        const handleLangChange = (e: any) => {
            setCurrentLang(e.detail.language)
        }
        window.addEventListener('languageChanged', handleLangChange)
        
        // 监听语言列表加载完成事件（替代轮询）
        const handleLangsLoaded = (e: any) => {
            setLanguages(e.detail.languages)
            setCurrentLang(getCurrentLanguage())
        }
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
        icon: lang.code === currentLang ? <SwapOutlined /> : undefined,
    }))

    // 用户界面菜单项
    const userMenuItems: MenuProps['items'] = [
        {
            key: '/user/dashboard',
            icon: <DashboardOutlined/>,
            label: '资源概览',
        },
        {
            key: '/user/vms',
            icon: <CloudServerOutlined/>,
            label: '实例管理',
        },
        {
            key: '/user/proxys',
            icon: <GlobalOutlined/>,
            label: '反向代理',
        },
        {
            key: '/user/nat',
            icon: <SwapOutlined/>,
            label: '端口转发',
        },
        {
            key: '/profile',
            icon: <UserOutlined/>,
            label: '个人资料',
        },
    ]

    // 系统界面菜单项（仅管理员可见）
    const adminMenuItems: MenuProps['items'] = [
        {
            key: '/dashboard',
            icon: <DashboardOutlined/>,
            label: '系统概览',
        },
        {
            key: '/hosts',
            icon: <CloudServerOutlined/>,
            label: '主机管理',
        },
        {
            key: '/vms',
            icon: <CloudServerOutlined/>,
            label: '实例管理',
        },
        {
            key: '/web-proxys',
            icon: <GlobalOutlined/>,
            label: '反向代理',
        },
        {
            key: '/nat-rules',
            icon: <SwapOutlined/>,
            label: '端口转发',
        },
        {
            key: '/users',
            icon: <UserOutlined/>,
            label: '用户管理',
        },
        {
            key: '/logs',
            icon: <FileTextOutlined/>,
            label: '日志查看',
        },
        {
            key: '/settings',
            icon: <SettingOutlined/>,
            label: '系统设置',
        },
    ]

    // 根据用户角色选择菜单
    const menuItems: MenuProps['items'] = user?.is_admin 
        ? [
            {
                key: 'user-interface',
                label: '用户空间',
                type: 'group',
                children: userMenuItems,
            },
            {
                key: 'system-interface',
                label: '系统空间',
                type: 'group',
                children: adminMenuItems,
            },
        ]
        : userMenuItems

    // 下拉菜单项
    const dropdownMenuItems: MenuProps['items'] = [
        {
            key: 'profile',
            icon: <UserOutlined/>,
            label: '个人资料',
            onClick: () => navigate('/profile'),
        },
        {
            key: 'settings',
            icon: <SettingOutlined/>,
            label: '设置',
            onClick: () => navigate('/settings'),
        },
        {
            type: 'divider',
        },
        {
            key: 'logout',
            icon: <LogoutOutlined/>,
            label: '退出登录',
            onClick: () => {
                logout()
                navigate('/login')
            },
        },
    ]

    // 菜单点击处理
    const handleMenuClick: MenuProps['onClick'] = ({key}) => {
        navigate(key)
    }

    return (
        <Layout style={{
            minHeight: '100vh'
        }}>
            {/* 侧边栏 */}
            <Sider
                trigger={null} 
                collapsible 
                collapsed={collapsed}
                width={160}
                collapsedWidth={60}
                className="main-sider"
                style={{
                    marginLeft: '16px',
                    marginTop: '6px',
                    marginBottom: '16px',
                    borderRadius: '16px',
                    overflow: 'hidden',
                }}
            >
                {/* Logo区域 */}
                <div
                    className="gradient-text"
                    style={{
                        height: 80,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: collapsed ? 20 : 24,
                        fontWeight: 'bold',
                        padding: '0 16px',
                        color: transparentMode 
                            ? (currentTheme === 'dark' ? 'var(--text-primary)' : '#0050b3')
                            : (currentTheme === 'dark' ? 'var(--text-primary)' : '#fff'),
                        borderBottom: currentTheme === 'dark' ? '1px solid var(--border-primary)' : 'none',
                        textShadow: transparentMode && currentTheme === 'light' ? '0 2px 4px rgba(0,0,0,0.15)' : 'none',
                    }}
                >{collapsed ? 'OI' : 'OpenIDCS'}
                </div>

                {/* 菜单 */}
                <Menu
                    mode="inline"
                    className="main-menu"
                    selectedKeys={[location.pathname]}
                    items={menuItems}
                    onClick={handleMenuClick}
                    style={{
                        background: 'transparent',
                        border: 'none',
                    }}
                />
            </Sider>

            <Layout>
                {/* 顶部导航 */}
                <Header
                    className="glass-card main-header"
                    style={{
                        padding: '0 16px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        borderBottom: currentTheme === 'dark' ? '1px solid var(--border-primary)' : '1px solid #f0f0f0',
                        backdropFilter: currentTheme === 'dark' ? 'blur(20px)' : 'none',
                        background: currentTheme === 'light' ? '#ffffff' : undefined,
                        margin: '6px 16px 16px ',
                    }}
                >
                    {/* 折叠按钮 */}
                    <Button
                        type="text"
                        icon={collapsed ? <MenuUnfoldOutlined/> : <MenuFoldOutlined/>}
                        onClick={() => setCollapsed(!collapsed)}
                        style={{
                            fontSize: 16,
                            width: 64,
                            height: 64,
                            color: currentTheme === 'dark' ? 'var(--text-primary)' : undefined,
                        }}
                    />

                    {/* 右侧操作区 */}
                    <div style={{display: 'flex', alignItems: 'center', gap: 16}}>
                        {/* 主题下拉菜单 */}
                        <Dropdown
                            placement="bottomRight"
                            overlayStyle={{ zIndex: 20000 }}
                            getPopupContainer={() => document.body}
                            dropdownRender={() => (
                                <div style={{
                                    background: currentTheme === 'dark' ? 'var(--bg-secondary, #1f1f1f)' : '#fff',
                                    border: currentTheme === 'dark' ? '1px solid var(--border-primary, #303030)' : '1px solid #f0f0f0',
                                    borderRadius: 12,
                                    boxShadow: '0 8px 32px rgba(0,0,0,0.15)',
                                    padding: '8px',
                                    minWidth: 180,
                                }}>
                                    <div style={{
                                        padding: '4px 8px 8px',
                                        fontSize: 11,
                                        fontWeight: 600,
                                        letterSpacing: '0.08em',
                                        color: currentTheme === 'dark' ? 'var(--text-secondary, #888)' : '#999',
                                        textTransform: 'uppercase',
                                    }}>主题设置</div>
                                    {/* 暗黑模式 */}
                                    <div
                                        onClick={toggleTheme}
                                        style={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: 10,
                                            padding: '8px 10px',
                                            borderRadius: 8,
                                            cursor: 'pointer',
                                            transition: 'background 0.2s',
                                            color: currentTheme === 'dark' ? 'var(--accent-primary, #1677ff)' : '#333',
                                        }}
                                        className="theme-menu-item"
                                    >
                                        {currentTheme === 'dark'
                                            ? <SunOutlined style={{ fontSize: 16, color: '#faad14' }} />
                                            : <MoonOutlined style={{ fontSize: 16, color: '#595959' }} />}
                                        <span style={{ flex: 1, fontSize: 14, color: currentTheme === 'dark' ? 'var(--text-primary, #fff)' : '#333' }}>
                                            {currentTheme === 'dark' ? '浅色模式' : '深色模式'}
                                        </span>
                                        {currentTheme === 'dark' && <CheckOutlined style={{ fontSize: 12, color: '#faad14' }} />}
                                    </div>
                                    {/* 透明模式 */}
                                    <div
                                        onClick={toggleTransparentMode}
                                        style={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: 10,
                                            padding: '8px 10px',
                                            borderRadius: 8,
                                            cursor: 'pointer',
                                            transition: 'background 0.2s',
                                        }}
                                        className="theme-menu-item"
                                    >
                                        <BgColorsOutlined style={{ fontSize: 16, color: transparentMode ? '#1677ff' : (currentTheme === 'dark' ? '#888' : '#595959') }} />
                                        <span style={{ flex: 1, fontSize: 14, color: currentTheme === 'dark' ? 'var(--text-primary, #fff)' : '#333' }}>透明模式</span>
                                        {transparentMode && <CheckOutlined style={{ fontSize: 12, color: '#1677ff' }} />}
                                    </div>
                                    {/* 圆角模式 */}
                                    <div
                                        onClick={toggleRoundedMode}
                                        style={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: 10,
                                            padding: '8px 10px',
                                            borderRadius: 8,
                                            cursor: 'pointer',
                                            transition: 'background 0.2s',
                                        }}
                                        className="theme-menu-item"
                                    >
                                        <RadiusSettingOutlined style={{ fontSize: 16, color: roundedMode ? '#52c41a' : (currentTheme === 'dark' ? '#888' : '#595959') }} />
                                        <span style={{ flex: 1, fontSize: 14, color: currentTheme === 'dark' ? 'var(--text-primary, #fff)' : '#333' }}>圆角模式</span>
                                        {roundedMode && <CheckOutlined style={{ fontSize: 12, color: '#52c41a' }} />}
                                    </div>
                                </div>
                            )}
                        >
                            <Button
                                type="text"
                                icon={<FormatPainterOutlined style={{ fontSize: 18 }} />}
                                title="主题"
                                style={{
                                    color: (currentTheme === 'dark' || transparentMode || roundedMode)
                                        ? 'var(--accent-primary, #1677ff)'
                                        : undefined,
                                }}
                            />
                        </Dropdown>

                        {/* 语言切换 */}
                        <Dropdown 
                            menu={{
                                items: languageMenuItems,
                                onClick: ({key}) => changeLanguage(key)
                            }} 
                            placement="bottomRight"
                            overlayStyle={{
                                zIndex: 20000,
                                maxHeight: '400px',
                                overflow: 'auto'
                            }}
                            getPopupContainer={() => document.body}
                        >
                            <Button
                                type="text"
                                icon={<TranslationOutlined style={{fontSize: 18}} />}
                                style={{
                                    color: currentTheme === 'dark' ? 'var(--text-primary)' : undefined,
                                }}
                            />
                        </Dropdown>

                        {/* 通知 */}
                        <Badge count={notifications}>
                            <Button
                                type="text"
                                icon={<BellOutlined style={{fontSize: 18}}/>}
                                onClick={() => setNotifications(0)}
                                style={{
                                    color: currentTheme === 'dark' ? 'var(--text-primary)' : undefined,
                                }}
                            />
                        </Badge>

                        {/* 用户信息 */}
                        <Dropdown 
                            menu={{items: dropdownMenuItems}} 
                            placement="bottomRight"
                            overlayStyle={{
                                zIndex: 20000,
                                maxHeight: '400px',
                                overflow: 'auto'
                            }}
                            getPopupContainer={() => document.body}
                        >
                            <div
                                style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    cursor: 'pointer',
                                    padding: '4px 12px',
                                    borderRadius: '12px',
                                    transition: 'all 0.3s ease',
                                }}
                                className="btn-hover"
                            >
                                <Avatar
                                    icon={<UserOutlined/>}
                                    style={{
                                        border: currentTheme === 'dark' ? '2px solid transparent' : undefined,
                                        backgroundImage: currentTheme === 'dark' ? 'var(--gradient-primary)' : undefined,
                                        backgroundClip: currentTheme === 'dark' ? 'padding-box' : undefined,
                                    }}
                                />
                                <span
                                    style={{
                                        marginLeft: 8,
                                        color: currentTheme === 'dark' ? 'var(--text-primary)' : undefined,
                                    }}
                                >
                                    {user?.username || '用户'}
                                </span>
                            </div>
                        </Dropdown>
                    </div>
                </Header>

                {/* 内容区域 */}
                <Content
                    className={`main-content main-layout-content ${currentTheme === 'dark' ? 'grid-background' : ''}`}
                    style={{
                        margin: '0px 16px 16px 16px',
                        padding: 24,
                        minHeight: 280,
                        borderRadius: 16,
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
