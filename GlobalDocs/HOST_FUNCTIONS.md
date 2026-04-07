# OpenIDCS-Client 主机函数功能支持完善文档

> 生成日期: 2026-03-31 | 基于 VPCTemplate.py 和 BasicServer.py 的接口定义

---

## 一、接口方法总览

BasicServer 基类定义了所有虚拟化平台需要实现的标准接口方法，各平台通过继承并重写这些方法来实现具体功能。

### 1.1 宿主机管理方法

| 方法名 | 功能 | 返回类型 | 说明 |
|--------|------|----------|------|
| `Crontabs()` | 定时任务 | `bool` | 每60秒执行一次，用于状态刷新、流量统计等 |
| `HSStatus()` | 主机状态 | `HWStatus` | 获取CPU/内存/磁盘/网络等硬件状态 |
| `HSCreate()` | 初始化主机 | `ZMessage` | 首次添加主机时的初始化操作 |
| `HSDelete()` | 还原主机 | `ZMessage` | 删除主机时的清理操作 |
| `HSLoader()` | 加载主机 | `ZMessage` | 启动时加载主机配置和虚拟机列表 |
| `HSUnload()` | 卸载主机 | `ZMessage` | 关闭时卸载主机资源 |

### 1.2 虚拟机管理方法

| 方法名 | 功能 | 参数 | 返回类型 |
|--------|------|------|----------|
| `VMStatus(vm_name, s_t, e_t)` | 虚拟机状态/监控 | 虚拟机名, 起止时间 | `dict[str, list[HWStatus]]` |
| `VMDetect()` | 扫描虚拟机 | - | `ZMessage` |
| `VMCreate(vm_conf)` | 创建虚拟机 | VMConfig | `ZMessage` |
| `VMSetups(vm_conf)` | 安装/重装系统 | VMConfig | `ZMessage` |
| `VMUpdate(vm_conf, vm_last)` | 修改配置 | 新配置, 旧配置 | `ZMessage` |
| `VMDelete(vm_name)` | 删除虚拟机 | 虚拟机名 | `ZMessage` |
| `VMPowers(vm_name, power)` | 电源控制 | 虚拟机名, VMPowers枚举 | `ZMessage` |
| `VMPasswd(vm_name, os_pass)` | 修改密码 | 虚拟机名, 新密码 | `ZMessage` |
| `VMScreen(vm_name)` | 虚拟机截图 | 虚拟机名 | `str` (base64) |
| `VMRemote(vm_uuid, ip_addr)` | VNC控制台 | UUID, IP地址 | `ZMessage` |
| `GetPower(vm_name)` | 获取实际电源状态 | 虚拟机名 | `str` |

### 1.3 存储管理方法

| 方法名 | 功能 | 参数 | 返回类型 |
|--------|------|------|----------|
| `HDDMount(vm_name, vm_imgs, in_flag)` | 挂载/创建磁盘 | 虚拟机名, SDConfig, 挂载标志 | `ZMessage` |
| `ISOMount(vm_name, vm_imgs, in_flag)` | 挂载ISO | 虚拟机名, IMConfig, 挂载标志 | `ZMessage` |
| `RMMounts(vm_name, vm_imgs)` | 卸载磁盘/ISO | 虚拟机名, 设备名 | `ZMessage` |
| `HDDCheck(vm_name, vm_imgs, ex_name)` | 磁盘移交检查 | 虚拟机名, SDConfig, 目标VM | `ZMessage` |
| `HDDTrans(vm_name, vm_imgs, ex_name)` | 磁盘移交 | 虚拟机名, SDConfig, 目标VM | `ZMessage` |

### 1.4 备份管理方法

| 方法名 | 功能 | 参数 | 返回类型 |
|--------|------|------|----------|
| `VMBackup(vm_name, vm_tips)` | 创建备份 | 虚拟机名, 备注 | `ZMessage` |
| `Restores(vm_name, vm_back)` | 还原备份 | 虚拟机名, 备份名 | `ZMessage` |
| `LDBackup(vm_back)` | 加载/扫描备份 | 备份路径 | `ZMessage` |
| `RMBackup(vm_name, vm_back)` | 删除备份 | 虚拟机名, 备份名 | `ZMessage` |

### 1.5 设备直通方法

| 方法名 | 功能 | 参数 | 返回类型 |
|--------|------|------|----------|
| `PCIShows()` | 列出PCI设备 | - | `dict[str, str]` |
| `PCISetup(vm_name, config, pci_key, in_flag)` | PCI直通 | 虚拟机名, VFConfig, 设备键, 添加/移除 | `ZMessage` |
| `USBShows()` | 列出USB设备 | - | `dict[str, USBInfos]` |
| `USBSetup(vm_name, ud_info, ud_keys, in_flag)` | USB直通 | 虚拟机名, USBInfos, 设备键, 添加/移除 | `ZMessage` |

---

## 二、各平台功能实现矩阵

### 2.1 宿主机管理

| 方法 | VMware WS | LXC/LXD | Docker/OCI | PVE | ESXi | Hyper-V | QEMU | VBox | MEmu | 青州云 |
|------|:---------:|:-------:|:----------:|:---:|:----:|:-------:|:----:|:----:|:----:|:------:|
| Crontabs | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| HSStatus | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| HSCreate | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| HSDelete | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| HSLoader | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| HSUnload | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

### 2.2 虚拟机生命周期

| 方法 | VMware WS | LXC/LXD | Docker/OCI | PVE | ESXi | Hyper-V | QEMU | VBox | MEmu | 青州云 |
|------|:---------:|:-------:|:----------:|:---:|:----:|:-------:|:----:|:----:|:----:|:------:|
| VMStatus | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| VMDetect | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| VMCreate | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| VMSetups | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ |
| VMUpdate | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| VMDelete | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| VMPowers | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| VMPasswd | ✅ | ✅外部 | ✅外部 | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ |
| VMScreen | ✅ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ |
| VMRemote | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ |
| GetPower | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

### 2.3 存储管理

| 方法 | VMware WS | LXC/LXD | Docker/OCI | PVE | ESXi | Hyper-V | QEMU | VBox | MEmu | 青州云 |
|------|:---------:|:-------:|:----------:|:---:|:----:|:-------:|:----:|:----:|:----:|:------:|
| HDDMount | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| ISOMount | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️APK | ✅ |
| RMMounts | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| HDDCheck | ✅ | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| HDDTrans | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

### 2.4 备份管理

| 方法 | VMware WS | LXC/LXD | Docker/OCI | PVE | ESXi | Hyper-V | QEMU | VBox | MEmu | 青州云 |
|------|:---------:|:-------:|:----------:|:---:|:----:|:-------:|:----:|:----:|:----:|:------:|
| VMBackup | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ |
| Restores | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ |
| LDBackup | ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ |
| RMBackup | ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ |

### 2.5 设备直通

| 方法 | VMware WS | LXC/LXD | Docker/OCI | PVE | ESXi | Hyper-V | QEMU | VBox | MEmu | 青州云 |
|------|:---------:|:-------:|:----------:|:---:|:----:|:-------:|:----:|:----:|:----:|:------:|
| PCIShows | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ |
| PCISetup | ✅虚拟 | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| USBShows | ✅ | ❌ | ❌ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ |
| USBSetup | ✅ | ❌ | ❌ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ |

---

## 三、图例说明

| 符号 | 含义 |
|------|------|
| ✅ | 已完整实现 |
| ⚠️ | 部分实现或有限制 |
| ❌ | 不支持或未实现 |
| ✅外部 | 通过外部工具（SSH/exec）实现 |
| ✅虚拟 | 通过虚拟方式实现（非硬件直通） |
| ⚠️APK | 功能替换（ISO挂载替换为APK安装） |

---

## 四、各平台特殊说明

### 4.1 VMware Workstation
- 通过 VMware REST API (`vmrest`) 管理虚拟机
- 不支持PCI硬件直通，但可分配虚拟显存
- 支持USB设备直通
- 仅支持Windows宿主机

### 4.2 LXC/LXD
- 通过 pylxd 库连接LXD服务器
- 容器不支持ISO挂载、额外硬盘、PCI/USB直通
- 密码修改通过 `lxc exec` 外部命令实现
- 不支持截图功能

### 4.3 Docker/OCI
- 通过 docker-py 库管理容器
- 支持Docker/Podman/K8s CRI
- 容器不支持ISO挂载、PCI/USB直通
- 密码修改通过 `docker exec` 外部命令实现
- 包含独立子模块: IPTablesAPI, OCIConnects, PortForward, SSHTerminal

### 4.4 Proxmox VE
- 通过 proxmoxer 库连接PVE API
- 功能最完整的远程平台之一
- 备份列表/删除功能有限制（PVE备份管理机制不同）
- 支持PCI/USB直通

### 4.5 VMware vSphere ESXi
- 通过 pyvmomi 库连接vCenter/ESXi
- 功能完整，支持所有核心操作
- 磁盘迁移功能未实现（无对应API方法）
- 包含独立子模块: vSphereAPI

### 4.6 Windows Hyper-V
- 通过 WinRM (pywinrm) + PowerShell 远程管理
- 不支持USB直通
- 支持GPU PV和DDA设备直通
- 无法单独限制上下行带宽
- 包含独立子模块: HyperVAPI

### 4.7 QEMU/KVM
- 通过 libvirt-python 管理，支持降级为命令行模式
- 功能较完整，支持PCI/USB直通
- 修改密码需要虚拟机安装 qemu-guest-agent
- 开发中状态

### 4.8 Oracle VirtualBox
- 通过 VBoxManage 命令行管理
- 不支持PCI直通
- 支持USB直通（需要扩展包）
- 远程桌面通过VRDE（RDP协议）
- 开发中状态

### 4.9 MEmu Game Emulator
- 通过 memuc 命令行管理逍遥安卓模拟器
- 不支持额外硬盘挂载
- ISO挂载替换为APK安装
- 不支持暂停/恢复操作
- VNC替换为ADB连接信息
- 开发中状态

### 4.10 青州云
- 通过HTTP API远程管理
- 云平台不支持PCI/USB设备直通
- 当前在HSEngine中被注释（未启用）

---

## 五、待完善功能清单

| 优先级 | 平台 | 功能 | 说明 |
|--------|------|------|------|
| 🔴 高 | VirtualBox | 全部方法 | 开发中，需完善所有核心功能 |
| 🔴 高 | QEMU/KVM | 全部方法 | 开发中，需完善和测试 |
| 🟡 中 | MEmu | VMSetups/VMScreen/VMRemote | 重装系统、截图、远程控制需完善 |
| 🟡 中 | PVE | LDBackup/RMBackup | 备份列表和删除需适配PVE机制 |
| 🟡 中 | ESXi | HDDTrans | 磁盘迁移功能未实现 |
| 🟢 低 | 青州云 | 启用注册 | HSEngine中被注释，需要启用和测试 |
| 🟢 低 | 全平台 | HDDCheck/HDDTrans | 磁盘检查和迁移仅VMware/PVE支持 |
