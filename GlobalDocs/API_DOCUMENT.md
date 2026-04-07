# OpenIDCS-Client API 接口文档

> 生成日期: 2026-03-31 | 基础URL: `http://localhost:1880`

---

## 一、认证方式

### Bearer Token 认证
```
Authorization: Bearer <token>
```
Token认证等同管理员权限，适用于所有API。

### Session 认证
通过 `/api/login` 登录后自动设置Cookie Session。

---

## 二、统一响应格式

```json
{
  "code": 200,       // 状态码: 200成功, 400参数错误, 401未授权, 403权限不足, 429限流, 500服务器错误
  "msg": "成功",     // 响应消息
  "data": { ... }    // 响应数据（可选）
}
```

---

## 三、认证相关 API

### 3.1 用户登录
- **POST** `/api/login`
- **权限**: 公开
- **请求体**:
```json
{
  "login_type": "token|user",
  "token": "Bearer Token值（token登录）",
  "username": "用户名（user登录）",
  "password": "密码（user登录）"
}
```
- **响应**: `{ redirect, user_info }`
- **限流**: 同一IP 5次失败后锁定300秒

### 3.2 用户登出
- **POST** `/api/logout`
- **权限**: 已登录

### 3.3 用户注册
- **POST** `/api/register`
- **权限**: 公开
- **请求体**:
```json
{
  "username": "用户名(3-20字符)",
  "email": "邮箱",
  "password": "密码(>=6字符)"
}
```

### 3.4 邮箱验证
- **GET** `/verify_email?token=<token>`
- **权限**: 公开

### 3.5 邮箱变更验证
- **GET** `/verify-email-change?token=<token>`
- **权限**: 公开

### 3.6 找回密码
- **POST** `/api/system/forgot-password` 或 `/api/forgot-password`
- **权限**: 公开
- **请求体**: `{ "email": "注册邮箱" }`

### 3.7 重置密码
- **POST** `/api/system/reset-password`
- **权限**: 公开
- **请求体**: `{ "token": "重置token", "new_password": "新密码", "confirm_password": "确认密码" }`

### 3.8 修改密码
- **POST** `/api/users/change-password`
- **权限**: 已登录
- **请求体**: `{ "new_password": "新密码", "confirm_password": "确认密码" }`

### 3.9 修改邮箱
- **POST** `/api/users/change-email`
- **权限**: 已登录
- **请求体**: `{ "new_email": "新邮箱" }`

---

## 四、系统管理 API

### 4.1 获取引擎类型
- **GET** `/api/system/engine`
- **权限**: 已认证
- **响应**: 支持的虚拟化引擎类型列表

### 4.2 保存系统配置
- **POST** `/api/system/saving` 或 `/api/system/save`
- **权限**: 已认证

### 4.3 加载系统配置
- **POST** `/api/system/loader` 或 `/api/system/load`
- **权限**: 已认证

### 4.4 系统统计信息
- **GET** `/api/system/statis`
- **权限**: 已认证
- **响应**: 系统统计数据

### 4.5 系统统计（简化版）
- **GET** `/api/system/stats`
- **权限**: 已认证
- **响应**: `{ host_count, vm_count }`

### 4.6 获取当前Token
- **GET** `/api/token/current`
- **权限**: 已认证
- **响应**: `{ token }`

### 4.7 设置Token
- **POST** `/api/token/set`
- **权限**: 已认证
- **请求体**: `{ "token": "新Token" }`

### 4.8 重置Token
- **POST** `/api/token/reset`
- **权限**: 已认证
- **响应**: `{ token: "新生成的Token" }`

### 4.9 获取日志
- **GET** `/api/system/logger/detail`
- **权限**: 已认证

### 4.10 清空日志
- **POST** `/api/system/logger/clear`
- **权限**: 已认证

### 4.11 获取任务
- **GET** `/api/system/tasker`
- **权限**: 已认证

### 4.12 获取系统设置
- **GET** `/api/system/settings`
- **权限**: 管理员

### 4.13 更新系统设置
- **POST** `/api/system/settings`
- **权限**: 管理员
- **请求体**: 设置键值对

### 4.14 获取系统IPv4地址
- **GET** `/api/system/ipv4`
- **权限**: 已认证
- **响应**: 系统网卡IPv4地址列表

### 4.15 测试邮件
- **POST** `/api/system/test-email`
- **权限**: 管理员
- **请求体**: `{ "test_email": "收件人", "subject": "标题", "body": "正文", "resend_email": "发件人", "resend_apikey": "API Key" }`

### 4.16 重新计算配额
- **POST** `/api/system/recalculate-quotas`
- **权限**: 已认证

---

## 五、主机管理 API

### 5.1 获取主机列表
- **GET** `/api/server/detail`
- **权限**: 已认证（普通用户仅看assigned_hosts）
- **响应**: `{ "主机名": { 主机信息 }, ... }`

### 5.2 获取主机详情
- **GET** `/api/server/detail/<hs_name>`
- **权限**: 管理员

### 5.3 添加主机
- **POST** `/api/server/create`
- **权限**: 管理员
- **请求体**:
```json
{
  "server_name": "主机名",
  "server_type": "VMWareSetup|LxContainer|OCInterface|vSphereESXi|HyperVSetup|PromoxSetup|...",
  "server_addr": "主机地址",
  "server_user": "用户名",
  "server_pass": "密码",
  "server_port": 0,
  "system_path": "虚拟机存储路径",
  "images_path": "镜像路径",
  "backup_path": "备份路径",
  "network_nat": "NAT网络设备",
  "network_pub": "公网网络设备",
  "ports_start": 10000,
  "ports_close": 60000
}
```

### 5.4 修改主机
- **PUT** `/api/server/update/<hs_name>`
- **权限**: 管理员

### 5.5 删除主机
- **DELETE** `/api/server/delete/<hs_name>`
- **权限**: 管理员

### 5.6 主机启用控制
- **POST** `/api/server/powers/<hs_name>`
- **权限**: 管理员
- **请求体**: `{ "enable": true|false }`

### 5.7 获取主机状态
- **GET** `/api/server/status/<hs_name>`
- **权限**: 已认证

### 5.8 获取套餐列表
- **GET** `/api/server/plan/<hs_name>`
- **权限**: 管理员

### 5.9 设置套餐
- **POST** `/api/server/plan/<hs_name>`
- **权限**: 管理员

### 5.10 删除套餐
- **DELETE** `/api/server/plan/<hs_name>/<plan_name>`
- **权限**: 管理员

### 5.11 获取区域列表
- **GET** `/api/server/areas`
- **权限**: 已认证

### 5.12 获取套餐规格
- **GET** `/api/server/plans/<hs_name>`
- **权限**: 已认证

### 5.13 获取可分配端口
- **GET** `/api/server/ports/<hs_name>`
- **权限**: 已认证

### 5.14 扫描备份文件
- **POST** `/api/server/backup/scan/<hs_name>`
- **权限**: 已认证

---

## 六、虚拟机管理 API

### 6.1 获取虚拟机列表
- **GET** `/api/client/detail/<hs_name>`
- **权限**: 已认证（检查主机访问权限）

### 6.2 获取虚拟机详情
- **GET** `/api/client/detail/<hs_name>/<vm_uuid>`
- **权限**: 已认证

### 6.3 创建虚拟机
- **POST** `/api/client/create/<hs_name>`
- **权限**: 已认证
- **请求体**:
```json
{
  "vm_uuid": "虚拟机名称/UUID",
  "vm_name": "显示名称",
  "os_name": "操作系统",
  "cpu_num": 2,
  "mem_num": 2048,
  "hdd_num": 8192,
  "gpu_num": 0,
  "speed_u": 100,
  "speed_d": 100
}
```

### 6.4 修改虚拟机
- **PUT** `/api/client/update/<hs_name>/<vm_uuid>`
- **权限**: 已认证

### 6.5 删除虚拟机
- **DELETE** `/api/client/delete/<hs_name>/<vm_uuid>`
- **权限**: 已认证

### 6.6 电源控制
- **POST** `/api/client/powers/<hs_name>/<vm_uuid>`
- **权限**: 已认证
- **请求体**: `{ "action": "S_START|H_CLOSE|S_CLOSE|S_RESET|S_PAUSE|S_RESUME" }`

### 6.7 获取VNC控制台
- **GET** `/api/client/remote/<hs_name>/<vm_uuid>`
- **权限**: 已认证
- **响应**: `{ console_url, terminal_url }`

### 6.8 虚拟机截图
- **GET** `/api/client/screenshot/<hs_name>/<vm_uuid>`
- **权限**: 已认证
- **响应**: `{ screenshot: "base64图片" }`

### 6.9 修改密码
- **POST** `/api/client/password/<hs_name>/<vm_uuid>`
- **权限**: 已认证
- **请求体**: `{ "password": "新密码" }`

### 6.10 获取虚拟机状态
- **GET** `/api/client/status/<hs_name>/<vm_uuid>`
- **权限**: 已认证

### 6.11 扫描虚拟机
- **POST** `/api/client/scaner/<hs_name>`
- **权限**: 已认证

### 6.12 虚拟机上报状态
- **POST** `/api/client/upload`
- **权限**: 公开（无需认证）

---

## 七、虚拟机网络 API

### 7.1 NAT端口转发

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/client/natget/<hs_name>/<vm_uuid>` | 获取NAT规则 |
| POST | `/api/client/natadd/<hs_name>/<vm_uuid>` | 添加NAT规则 |
| DELETE | `/api/client/natdel/<hs_name>/<vm_uuid>/<rule_index>` | 删除NAT规则 |

**添加NAT请求体**:
```json
{
  "wan_port": 10001,
  "lan_port": 22,
  "lan_addr": "192.168.1.100",
  "nat_tips": "SSH"
}
```

### 7.2 IP地址管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/client/ipaddr/detail/<hs_name>/<vm_uuid>` | 获取IP列表 |
| POST | `/api/client/ipaddr/create/<hs_name>/<vm_uuid>` | 添加IP |
| DELETE | `/api/client/ipaddr/delete/<hs_name>/<vm_uuid>/<ip_index>` | 删除IP |

**RESTful风格（推荐）**:

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/hosts/<hs_name>/vms/<vm_uuid>/ip_addresses` | 获取网卡列表 |
| POST | `/api/hosts/<hs_name>/vms/<vm_uuid>/ip_addresses` | 添加网卡 |
| PUT | `/api/hosts/<hs_name>/vms/<vm_uuid>/ip_addresses/<nic_name>` | 修改网卡 |
| DELETE | `/api/hosts/<hs_name>/vms/<vm_uuid>/ip_addresses/<nic_name>` | 删除网卡 |

### 7.3 反向代理（用户级）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/client/proxys/list` | 获取当前用户所有代理 |
| GET | `/api/client/proxys/detail/<hs_name>/<vm_uuid>` | 获取VM代理配置 |
| POST | `/api/client/proxys/create/<hs_name>/<vm_uuid>` | 添加代理 |
| DELETE | `/api/client/proxys/delete/<hs_name>/<vm_uuid>/<proxy_index>` | 删除代理 |

### 7.4 反向代理（管理员级）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/admin/proxys/list` | 获取所有代理 |
| GET | `/api/admin/proxys/list/<hs_name>` | 获取主机代理 |
| GET | `/api/admin/proxys/detail/<hs_name>/<vm_uuid>` | 获取VM代理 |
| POST | `/api/admin/proxys/create/<hs_name>/<vm_uuid>` | 添加代理 |
| PUT | `/api/admin/proxys/update/<hs_name>/<vm_uuid>/<proxy_index>` | 更新代理 |
| DELETE | `/api/admin/proxys/delete/<hs_name>/<vm_uuid>/<proxy_index>` | 删除代理 |

---

## 八、存储管理 API

### 8.1 数据盘管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/client/hdd/detail/<hs_name>/<vm_uuid>` | 获取数据盘列表 |
| POST | `/api/client/hdd/mount/<hs_name>/<vm_uuid>` | 挂载数据盘 |
| POST | `/api/client/hdd/unmount/<hs_name>/<vm_uuid>` | 卸载数据盘 |
| POST | `/api/client/hdd/transfer/<hs_name>/<vm_uuid>` | 移交数据盘 |
| DELETE | `/api/client/hdd/delete/<hs_name>/<vm_uuid>` | 删除数据盘 |

### 8.2 ISO管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/client/isos/detail/<hs_name>/<vm_uuid>` | 获取ISO列表 |
| POST | `/api/client/iso/mount/<hs_name>/<vm_uuid>` | 挂载ISO |
| DELETE | `/api/client/iso/unmount/<hs_name>/<vm_uuid>/<iso_name>` | 卸载ISO |

### 8.3 USB管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/client/usb/mount/<hs_name>/<vm_uuid>` | 挂载USB |
| DELETE | `/api/client/usb/delete/<hs_name>/<vm_uuid>/<usb_key>` | 卸载USB |

---

## 九、备份管理 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/client/backup/detail/<hs_name>/<vm_uuid>` | 获取备份列表 |
| POST | `/api/client/backup/create/<hs_name>/<vm_uuid>` | 创建备份 |
| POST | `/api/client/backup/restore/<hs_name>/<vm_uuid>` | 还原备份 |
| DELETE | `/api/client/backup/delete/<hs_name>/<vm_uuid>` | 删除备份 |

---

## 十、设备直通 API

### 10.1 操作系统镜像
- **GET** `/api/client/os-images/<hs_name>` - 获取OS镜像列表

### 10.2 GPU设备
- **GET** `/api/client/gpu-list/<hs_name>` - 获取GPU列表

### 10.3 PCI设备
- **GET** `/api/client/pci-list/<hs_name>` - 获取PCI设备列表
- **POST** `/api/client/pci/setup/<hs_name>/<vm_uuid>` - PCI直通操作
  - 请求体: `{ "pci_key": "设备键", "gpu_uuid": "UUID", "gpu_mdev": "mdev", "gpu_hint": "描述", "action": "add|remove" }`

### 10.4 USB设备
- **GET** `/api/client/usb-list/<hs_name>` - 获取USB设备列表
- **POST** `/api/client/usb/setup/<hs_name>/<vm_uuid>` - USB直通操作
  - 请求体: `{ "usb_key": "设备键", "vid_uuid": "VID", "pid_uuid": "PID", "usb_hint": "描述", "action": "add|remove" }`

### 10.5 EFI启动项
- **GET** `/api/client/efi-list/<hs_name>/<vm_uuid>` - 获取启动项列表
- **POST** `/api/client/efi/setup/<hs_name>/<vm_uuid>` - 设置启动顺序
  - 请求体: `{ "efi_list": [{ "efi_type": true, "efi_name": "启动项名" }] }`

---

## 十一、虚拟机所有者 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/client/owners/<hs_name>/<vm_uuid>` | 获取所有者列表 |
| POST | `/api/client/owners/<hs_name>/<vm_uuid>` | 添加所有者 |
| DELETE | `/api/client/owners/<hs_name>/<vm_uuid>` | 删除所有者 |
| PUT | `/api/client/owners/<hs_name>/<vm_uuid>/permission` | 更新所有者权限 |
| POST | `/api/client/owners/<hs_name>/<vm_uuid>/transfer` | 移交所有权 |

---

## 十二、用户管理 API

### 12.1 当前用户
- **GET** `/api/users/current` - 获取当前用户信息（含配额使用量）

### 12.2 用户CRUD（管理员）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/users` | 获取用户列表 |
| POST | `/api/users` | 创建用户 |
| GET | `/api/users/<user_id>` | 获取用户详情 |
| PUT | `/api/users/<user_id>` | 更新用户 |
| DELETE | `/api/users/<user_id>` | 删除用户 |

---

## 十三、国际化 API

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/api/i18n/languages` | 公开 | 获取可用语言列表 |
| GET | `/api/i18n/translations/<lang_code>` | 公开 | 获取翻译数据 |

支持语言: zh-cn, zh-tw, en-us, ja-jp, ko-kr, ar-ar, de-de, es-es, fr-fr, it-it, pt-br, ru-ru, hi-in, bn-bd, ur-pk

---

## 十四、API路由总计

| 分类 | 路由数量 |
|------|----------|
| 认证相关 | 9 |
| 系统管理 | 16 |
| 主机管理 | 14 |
| 虚拟机管理 | 12 |
| 网络管理(NAT/IP/代理) | 17 |
| 存储管理(HDD/ISO/USB) | 8 |
| 备份管理 | 5 |
| 设备直通(PCI/USB/EFI) | 6 |
| 所有者管理 | 5 |
| 用户管理 | 6 |
| 国际化 | 2 |
| **总计** | **~100** |
