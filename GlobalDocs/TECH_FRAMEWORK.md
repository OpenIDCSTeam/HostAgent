# OpenIDCS-Client 前后端技术框架文档

> 生成日期: 2026-03-31 | 项目版本: v0.5

---

## 一、项目总览

OpenIDCS-Client 是一个开源IDC虚拟化统一管理平台，采用 **前后端分离** 架构，后端基于 Python Flask 提供 RESTful API，前端基于 React 18 + TypeScript 构建 SPA 应用。

---

## 二、后端技术框架

### 2.1 技术栈

| 组件 | 技术 | 版本 | 说明 |
|------|------|------|------|
| Web框架 | Flask | >= 2.3.3 | 轻量级WSGI框架，提供路由、Session、模板等 |
| 数据库 | SQLite | 内置 | 通过 `DataManager` 封装，WAL模式提升并发 |
| 日志 | Loguru | >= 0.6.0 | 按主机分文件、自动轮转压缩 |
| HTTP客户端 | Requests | >= 2.28.0 | 用于调用各虚拟化平台API |
| 系统监控 | psutil / GPUtil / py-cpuinfo | >= 5.9.0 | 主机硬件状态采集 |
| 密码加密 | bcrypt | - | 用户密码哈希存储 |
| SSH | Paramiko | - | SSH终端连接 |
| WinRM | pywinrm | - | Windows远程管理 |
| 压缩 | py7zr | >= 0.20.0 | 备份压缩 |
| 邮件 | Resend API | - | 邮箱验证/密码重置 |
| 打包 | Nuitka / cx_Freeze | >= 1.8.0 | 生产环境二进制打包 |

### 2.2 后端架构分层

```
┌─────────────────────────────────────────────────────────┐
│                    MainServer.py                         │
│              Flask应用入口 + 路由注册层                    │
│         (登录/注册/认证/API路由定义/定时任务)               │
├─────────────────────────────────────────────────────────┤
│                   HostModule/ 业务逻辑层                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │RestManager│ │HostManager│ │UserManager│ │DataManager│  │
│  │ API处理器 │ │ 主机管理  │ │ 用户/RBAC │ │ SQLite   │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │HttpManager│ │NetsManager│ │SSHDManager│ │Translation│  │
│  │ HTTP反代  │ │ NAT/网络  │ │ SSH终端   │ │ 多语言   │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │
├─────────────────────────────────────────────────────────┤
│                MainObject/ 核心数据对象层                  │
│  Config/: HSConfig, VMConfig, IPConfig, NCConfig,        │
│           PortData, WebProxy, VMBackup, UserMask...       │
│  Server/: HSEngine(引擎注册), HSStatus, HSTasker, VMStatus│
│  Public/: HWStatus(硬件状态), ZMessage(统一消息)           │
├─────────────────────────────────────────────────────────┤
│              HostServer/ 虚拟化平台驱动层                  │
│  BasicServer.py ─── 基础抽象类(1888行)                    │
│  ├── Workstation.py    (VMware Workstation, 826行)       │
│  ├── LXContainer.py    (LXC/LXD容器, 1600+行)           │
│  ├── OCInterface.py    (Docker/OCI, 1800+行)             │
│  ├── ProxmoxQemu.py    (Proxmox VE, 1996行)             │
│  ├── vSphereESXi.py    (VMware ESXi, 1800+行)           │
│  ├── Win64HyperV.py    (Hyper-V, 2200+行)               │
│  ├── QEMUService.py    (QEMU/KVM, 1000+行)              │
│  ├── VirtualBoxs.py    (VirtualBox, 1000+行)             │
│  ├── MemuAndroid.py    (MEmu模拟器, 800+行)              │
│  ├── QingzhouYun.py    (青州云, 1100+行)                 │
│  └── VPCTemplate.py    (新平台开发模板, 232行)            │
├─────────────────────────────────────────────────────────┤
│                  基础设施层                                │
│  VNCConsole/  ─── VNC远程控制台(WebSocket代理)            │
│  Websockify/  ─── WebSocket转TCP代理                     │
│  ZJMFServer/  ─── 魔方财务对接服务                        │
└─────────────────────────────────────────────────────────┘
```

### 2.3 核心模块说明

#### MainServer.py (2116行)
- Flask应用入口，注册所有API路由
- 登录速率限制（IP锁定机制）
- 认证体系：Bearer Token + Session 双模式
- 定时任务调度器（60秒间隔）
- React SPA静态文件服务

#### HostModule/RestManager.py (4807行)
- 所有API的业务处理逻辑
- 统一响应格式封装
- 权限检查与资源配额校验
- 虚拟机CRUD、电源控制、网络配置等

#### HostModule/HostManager.py (846行)
- 主机生命周期管理（添加/删除/启用/禁用）
- 配置持久化（数据库存储）
- 定时任务执行（Cron调度）
- 用户资源配额重算

#### HostModule/DataManager.py (1362行)
- SQLite数据库封装（WAL模式）
- 主机配置/虚拟机配置/用户/日志/状态的CRUD
- 数据迁移支持
- 系统设置管理

#### HostModule/UserManager.py (498行)
- bcrypt密码加密
- RBAC权限装饰器（require_login, require_admin, require_permission）
- 主机访问权限检查
- 虚拟机操作权限检查
- 资源配额检查
- Resend邮件服务

### 2.4 认证体系

```
请求 ──→ Bearer Token验证 ──→ 通过 ──→ 注入admin上下文 ──→ 执行
  │                              │
  └──→ Session验证 ──→ 通过 ──→ 从session获取用户信息 ──→ 执行
                         │
                         └──→ 401未授权
```

- **Token认证**: `Authorization: Bearer <token>`，等同管理员权限
- **Session认证**: 用户名密码登录，基于Flask Session
- **权限层级**: Token > Admin > 普通用户(RBAC)

### 2.5 数据库设计

| 表名 | 说明 | 关键字段 |
|------|------|----------|
| `hs_global` | 全局配置 | id(TEXT), data(TEXT) |
| `hs_config` | 主机配置 | hs_name, server_type, server_addr, server_plan... |
| `hs_status` | 主机状态 | hs_name, status_data(JSON) |
| `vm_saving` | 虚拟机配置 | hs_name, vm_uuid, vm_config(JSON) |
| `vm_status` | 虚拟机状态 | hs_name, vm_uuid, status_data, ac_status, on_update |
| `vm_tasker` | 任务记录 | hs_name, task_data(JSON) |
| `hs_logger` | 操作日志 | hs_name, log_data(JSON), log_level |
| `web_users` | 用户表 | username, password, email, is_admin, quota_*, used_* |

---

## 三、前端技术框架

### 3.1 技术栈

| 组件 | 技术 | 版本 | 说明 |
|------|------|------|------|
| 框架 | React 18 | >= 18.2.0 | 函数组件 + Hooks |
| 语言 | TypeScript | >= 5.2.2 | 类型安全 |
| 构建 | Vite | >= 7.3.1 | 快速HMR + 代码分割 |
| UI库 | Ant Design 5 | >= 5.12.0 | 企业级组件库 |
| 样式 | TailwindCSS + DaisyUI | >= 3.4.0 | 原子化CSS + 主题 |
| 图表 | ECharts | >= 5.4.3 | 性能监控可视化 |
| 状态管理 | Zustand | >= 4.4.7 | 轻量级状态管理 |
| 路由 | React Router v6 | >= 6.20.0 | SPA路由 |
| HTTP | Axios | >= 1.6.2 | 请求拦截/响应处理 |
| 图标 | @ant-design/icons + @iconify/react + @heroicons/react | - | 多图标库 |
| 弹窗 | SweetAlert2 | >= 11.10.3 | 美观的确认弹窗 |
| 日期 | Day.js | >= 1.11.10 | 日期处理 |

### 3.2 前端目录结构

```
FrontPages/src/
├── App.tsx              # 路由配置（管理员/用户双视图）
├── main.tsx             # 应用入口
├── index.css            # 全局样式（TailwindCSS）
├── pages/               # 页面组件
│   ├── MainLayout.tsx   # 主布局（侧边栏+顶栏+内容区）
│   ├── Dashboards.tsx   # 仪表盘（资源概览+图表）
│   ├── HostManage.tsx   # 主机管理（CRUD+状态监控）
│   ├── DockManage.tsx   # 虚拟机列表
│   ├── DockDetail.tsx   # 虚拟机详情（200KB，最大页面）
│   ├── UserManage.tsx   # 用户管理
│   ├── UserLogins.tsx   # 登录页
│   ├── UserPostin.tsx   # 注册页
│   ├── UserPasswd.tsx   # 密码重置
│   ├── UserConfig.tsx   # 个人设置
│   ├── CoreConfig.tsx   # 系统设置
│   ├── HttpProxys.tsx   # 反向代理管理
│   ├── LogsManage.tsx   # 日志管理
│   └── TaskManage.tsx   # 任务管理
├── user/                # 普通用户专属页面
│   ├── UserPanels.tsx   # 用户仪表盘
│   ├── UserProxys.tsx   # 用户代理管理
│   └── PortManage.tsx   # 用户端口管理
├── components/          # 公共组件
│   ├── PageHeader.tsx   # 页面头部
│   └── dock/            # 虚拟机相关组件
│       ├── DockCard.tsx         # 虚拟机卡片
│       ├── DockCreateModal.tsx  # 创建虚拟机弹窗(44KB)
│       └── DockPowerModal.tsx   # 电源控制弹窗
├── utils/               # 工具模块
│   ├── apis.ts          # API封装（807行，完整的API调用层）
│   ├── axio.ts          # Axios实例配置（拦截器/错误处理）
│   ├── data.ts          # Zustand状态管理
│   └── i18n.ts          # 国际化（15种语言支持）
├── types/               # TypeScript类型定义
│   └── index.ts         # 全局类型（User/Host/VM/NAT/Proxy等）
├── config/              # 配置
│   └── theme.config.ts  # 主题配置
├── constants/           # 常量
│   └── status.ts        # 状态常量
└── contexts/            # React Context
    └── ThemeContext.tsx  # 主题上下文
```

### 3.3 路由设计

```
/ ──→ 根据用户角色重定向
├── /login              # 登录页（公开）
├── /register           # 注册页（公开）
├── /reset-password     # 密码重置（公开）
│
├── /dashboard          # 管理员仪表盘
├── /hosts              # 主机管理
├── /hosts/:hostName/vms          # 主机下虚拟机列表
├── /hosts/:hostName/vms/:uuid    # 虚拟机详情
├── /vms                # 全局虚拟机管理
├── /users              # 用户管理
├── /tasks              # 任务管理
├── /logs               # 日志管理
├── /settings           # 系统设置
├── /web-proxys         # 反向代理管理
├── /nat-rules          # NAT规则管理
│
├── /user/dashboard     # 用户仪表盘
├── /user/vms           # 用户虚拟机
├── /user/proxys        # 用户代理
├── /user/nat           # 用户NAT
│
└── /profile            # 个人设置
```

### 3.4 前端数据流

```
页面组件 ──→ apis.ts (API调用) ──→ axio.ts (Axios拦截器)
    │                                    │
    │                                    ├── 请求拦截: 注入Bearer Token
    │                                    └── 响应拦截: 统一错误处理/401跳转
    │
    └── Zustand Store (data.ts) ──→ 全局状态（用户信息）
```

### 3.5 构建配置

- **开发代理**: `/api` → `http://localhost:1880`（Flask后端）
- **代码分割**: react-vendor / antd-vendor / chart-vendor
- **路径别名**: `@` → `./src`

---

## 四、前后端交互

### 4.1 通信协议

- **协议**: HTTP/HTTPS RESTful API
- **数据格式**: JSON
- **认证方式**: Bearer Token / Cookie Session
- **统一响应格式**:
```json
{
  "code": 200,
  "msg": "成功",
  "data": { ... }
}
```

### 4.2 错误码规范

| 状态码 | 含义 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 401 | 未授权（需要登录） |
| 403 | 权限不足 |
| 404 | 资源不存在 |
| 429 | 请求过于频繁（登录限流） |
| 500 | 服务器内部错误 |

### 4.3 部署模式

```
生产模式:
  Flask ──→ 直接serve React构建产物(static/)
  端口: 1880

开发模式:
  Vite DevServer (3000) ──proxy──→ Flask (1880)
```

---

## 五、国际化支持

- **前端**: `i18n.ts` 支持15种语言，通过API动态加载翻译数据
- **后端**: `HostConfig/translates/` 目录存储PO翻译文件
- **API**: `/api/i18n/languages` 获取语言列表，`/api/i18n/translations/<lang>` 获取翻译数据

---

## 六、安全机制

| 机制 | 实现 |
|------|------|
| 密码存储 | bcrypt哈希 + 兼容旧SHA256 |
| 登录限流 | IP级别，5次失败锁定300秒 |
| Token管理 | 256位随机Token，可重置 |
| Session | Flask secret_key随机生成 |
| 权限控制 | RBAC + 细粒度虚拟机权限掩码(16位) |
| 邮箱验证 | Resend API发送验证链接 |
