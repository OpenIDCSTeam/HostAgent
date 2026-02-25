# Hyper-V 配置示例

## 本地连接配置

```python
from MainObject.Config.HSConfig import HSConfig

# 本地Hyper-V主机配置
local_config = HSConfig(
    server_name="Local-HyperV",
    server_addr="localhost",
    server_user="",
    server_pass="",
    server_port=5985,
    system_path="C:\\Hyper-V\\DockManage",
    images_path="C:\\Hyper-V\\Images",
    backup_path="C:\\Hyper-V\\Backups",
    remote_port=6080,
    # 网络配置
    i_kuai_addr="192.168.1.1",
    i_kuai_user="admin",
    i_kuai_pass="admin",
    # IP地址池
    ipaddr_maps=["192.168.1.100", "114.193.206.253", "114.193.206.254"],
    ipaddr_ddns=["119.29.29.29", "223.5.5.5"],
    # 端口范围
    ports_start=10000,
    ports_close=20000,
    # 过滤前缀
    filter_name="VM-"
)
```

## 远程连接配置（HTTP）

```python
# 远程Hyper-V主机配置（HTTP）
remote_http_config = HSConfig(
    server_name="Remote-HyperV-01",
    server_addr="192.168.1.100",
    server_user="Administrator",
    server_pass="YourPassword123!",
    server_port=5985,  # HTTP端口
    system_path="D:\\VirtualMachines",
    images_path="D:\\ISO",
    backup_path="D:\\Backups",
    remote_port=6080,
    i_kuai_addr="192.168.1.1",
    i_kuai_user="admin",
    i_kuai_pass="admin",
    ipaddr_maps=["192.168.100.10", "56.92.28.254", "56.92.28.255"],
    ipaddr_ddns=["119.29.29.29", "223.5.5.5"],
    ports_start=10000,
    ports_close=20000,
    filter_name="PROD-"
)
```

## 远程连接配置（HTTPS）

```python
# 远程Hyper-V主机配置（HTTPS）
remote_https_config = HSConfig(
    server_name="Remote-HyperV-02",
    server_addr="192.168.1.100",
    server_user="Administrator",
    server_pass="YourPassword123!",
    server_port=5986,  # HTTPS端口
    system_path="E:\\HyperV\\DockManage",
    images_path="E:\\HyperV\\ISO",
    backup_path="E:\\HyperV\\Backups",
    remote_port=6080,
    i_kuai_addr="192.168.1.1",
    i_kuai_user="admin",
    i_kuai_pass="admin",
    ipaddr_maps=["192.168.1.100", "114.193.206.253"],
    ipaddr_ddns=["119.29.29.29", "223.5.5.5"],
    ports_start=20000,
    ports_close=30000,
    filter_name="DEV-"
)
```

## 虚拟机配置示例

### 基本虚拟机

```python
from MainObject.Config.VMConfig import VMConfig

basic_vm = VMConfig()
basic_vm.vm_uuid = "WebServer-01"
basic_vm.cpu_num = 2
basic_vm.mem_num = 4096  # 4GB
basic_vm.hdd_num = 50    # 50GB
basic_vm.os_name = "Ubuntu-22.04-Server.iso"
```

### 高性能虚拟机

```python
high_performance_vm = VMConfig()
high_performance_vm.vm_uuid = "Database-01"
high_performance_vm.cpu_num = 8
high_performance_vm.mem_num = 16384  # 16GB
high_performance_vm.hdd_num = 200    # 200GB
high_performance_vm.os_name = "Windows-Server-2022.iso"
```

### 开发测试虚拟机

```python
dev_vm = VMConfig()
dev_vm.vm_uuid = "Dev-Test-01"
dev_vm.cpu_num = 2
dev_vm.mem_num = 2048  # 2GB
dev_vm.hdd_num = 40    # 40GB
dev_vm.os_name = "Debian-12.iso"
```

## 网络配置示例

### 网卡配置

```python
from MainObject.Config.NICConfig import NICConfig

# 创建网卡配置
nic_config = NICConfig()
nic_config.ip4_addr = "192.168.1.100"
nic_config.ip4_mask = "255.255.255.0"
nic_config.ip4_gate = "114.193.206.1"
nic_config.mac_addr = "00:15:5D:00:00:01"
nic_config.dns_addr = ["119.29.29.29", "223.5.5.5"]

# 添加到虚拟机配置
vm_config.nic_all["eth0"] = nic_config
```

### NAT端口映射

```python
from MainObject.Config.PortData import PortData

# SSH端口映射
ssh_port = PortData()
ssh_port.wan_port = 0  # 自动分配
ssh_port.lan_port = 22
ssh_port.lan_addr = "192.168.1.100"
ssh_port.nat_tips = "WebServer-01 SSH"

# RDP端口映射
rdp_port = PortData()
rdp_port.wan_port = 13389
rdp_port.lan_port = 3389
rdp_port.lan_addr = "192.168.1.100"
rdp_port.nat_tips = "WebServer-01 RDP"

# HTTP端口映射
http_port = PortData()
http_port.wan_port = 8080
http_port.lan_port = 80
http_port.lan_addr = "192.168.1.100"
http_port.nat_tips = "WebServer-01 HTTP"
```

### Web代理配置

```python
from MainObject.Config.WebProxy import WebProxy

# HTTP代理
http_proxy = WebProxy()
http_proxy.web_addr = "www.example.com"
http_proxy.lan_addr = "192.168.1.100"
http_proxy.lan_port = 80
http_proxy.is_https = False

# HTTPS代理
https_proxy = WebProxy()
https_proxy.web_addr = "secure.example.com"
https_proxy.lan_addr = "192.168.1.100"
https_proxy.lan_port = 443
https_proxy.is_https = True
```

## 存储配置示例

### 虚拟硬盘配置

```python
from MainObject.Config.SDConfig import SDConfig

# 数据盘
data_disk = SDConfig()
data_disk.hdd_name = "data-disk-01"
data_disk.hdd_size = 100  # 100GB
data_disk.hdd_flag = 1    # 已挂载

# 备份盘
backup_disk = SDConfig()
backup_disk.hdd_name = "backup-disk-01"
backup_disk.hdd_size = 500  # 500GB
backup_disk.hdd_flag = 0    # 未挂载
```

### ISO镜像配置

```python
from MainObject.Config.IMConfig import IMConfig

# Windows安装镜像
windows_iso = IMConfig()
windows_iso.iso_name = "Windows-Server-2022"
windows_iso.iso_file = "Windows-Server-2022.iso"

# Linux安装镜像
linux_iso = IMConfig()
linux_iso.iso_name = "Ubuntu-22.04"
linux_iso.iso_file = "ubuntu-22.04-server-amd64.iso"

# 驱动光盘
driver_iso = IMConfig()
driver_iso.iso_name = "Drivers"
driver_iso.iso_file = "drivers.iso"
```

## 完整示例

```python
from MainObject.Config.HSConfig import HSConfig
from MainObject.Config.VMConfig import VMConfig
from MainObject.Config.NICConfig import NICConfig
from MainObject.Config.PortData import PortData
from MainObject.Config.IMConfig import IMConfig
from HostServer.Win64HyperV import HostServer

# 1. 创建主机配置
host_config = HSConfig(
    server_name="Production-HyperV",
    server_addr="192.168.1.100",
    server_user="Administrator",
    server_pass="SecurePassword123!",
    server_port=5985,
    system_path="D:\\DockManage",
    images_path="D:\\ISO",
    backup_path="D:\\Backups",
    i_kuai_addr="192.168.1.1",
    i_kuai_user="admin",
    i_kuai_pass="admin",
    ipaddr_maps=["192.168.1.100", "114.193.206.253", "114.193.206.254"],
    ipaddr_ddns=["119.29.29.29", "223.5.5.5"],
    ports_start=10000,
    ports_close=20000,
    filter_name="PROD-"
)

# 2. 创建虚拟机配置
vm_config = VMConfig()
vm_config.vm_uuid = "PROD-WebServer-01"
vm_config.cpu_num = 4
vm_config.mem_num = 8192
vm_config.hdd_num = 100
vm_config.os_name = "Windows-Server-2022.iso"

# 3. 配置网卡
nic = NICConfig()
nic.ip4_addr = "192.168.1.100"
nic.ip4_mask = "255.255.255.0"
nic.ip4_gate = "114.193.206.1"
nic.mac_addr = "00:15:5D:00:00:01"
nic.dns_addr = ["119.29.29.29", "223.5.5.5"]
vm_config.nic_all["eth0"] = nic

# 4. 初始化主机服务
host = HostServer(host_config)
host.HSLoader()

# 5. 创建虚拟机
result = host.VMCreate(vm_config)
print(f"创建结果: {result.message}")

# 6. 挂载ISO
iso = IMConfig()
iso.iso_name = "Windows-Install"
iso.iso_file = "Windows-Server-2022.iso"
host.ISOMount(vm_config.vm_uuid, iso, in_flag=True)

# 7. 配置端口映射
rdp_port = PortData()
rdp_port.wan_port = 0
rdp_port.lan_port = 3389
rdp_port.lan_addr = "192.168.1.100"
rdp_port.nat_tips = "PROD-WebServer-01 RDP"
host.PortsMap(rdp_port, flag=True)

# 8. 启动虚拟机
from MainObject.Config.VMPowers import VMPowers
host.VMPowers(vm_config.vm_uuid, VMPowers.S_START)

# 9. 创建快照
host.VMBackup(vm_config.vm_uuid, "初始安装完成")

# 10. 清理
host.HSUnload()
```

## 环境变量配置（可选）

```bash
# Windows环境变量
set HYPERV_HOST=192.168.1.100
set HYPERV_USER=Administrator
set HYPERV_PASS=YourPassword
set HYPERV_PORT=5985
set HYPERV_VM_PATH=D:\DockManage
set HYPERV_ISO_PATH=D:\ISO
set HYPERV_BACKUP_PATH=D:\Backups
```

## 配置文件（JSON格式）

```json
{
  "server_name": "Production-HyperV",
  "server_addr": "192.168.1.100",
  "server_user": "Administrator",
  "server_pass": "SecurePassword123!",
  "server_port": 5985,
  "system_path": "D:\\DockManage",
  "images_path": "D:\\ISO",
  "backup_path": "D:\\Backups",
  "remote_port": 6080,
  "i_kuai_addr": "192.168.1.1",
  "i_kuai_user": "admin",
  "i_kuai_pass": "admin",
  "ipaddr_maps": [
    "192.168.1.100",
    "114.193.206.253",
    "114.193.206.254"
  ],
  "ipaddr_ddns": [
    "119.29.29.29",
    "223.5.5.5"
  ],
  "ports_start": 10000,
  "ports_close": 20000,
  "filter_name": "PROD-"
}
```

## 注意事项

1. **密码安全**: 不要在代码中硬编码密码，使用环境变量或配置文件
2. **路径格式**: Windows路径使用双反斜杠 `\\` 或原始字符串 `r"C:\path"`
3. **IP地址**: 确保IP地址在正确的网段内
4. **端口范围**: 避免使用系统保留端口（0-1023）
5. **虚拟机命名**: 使用有意义的命名规范，便于管理
