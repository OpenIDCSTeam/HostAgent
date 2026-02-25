# Docker/Podman 容器管理 - 快速开始

<div align="center">

5 分钟快速部署 Docker/Podman 容器管理环境

[支持的发行版](#支持的-linux-发行版) • [步骤 1：服务端配置](#步骤-1服务端配置linux-服务器) • [步骤 2：客户端配置](#步骤-2客户端配置windows) • [步骤 3：测试连接](#步骤-3测试连接)

</div>

## 🚀 5 分钟快速部署

### 支持的 Linux 发行版

| 发行版 | 包管理器 | Docker 支持 | Podman 支持 |
|--------|---------|------------|------------|
| Ubuntu 18.04+ | apt | ✅ | ✅ |
| Debian 10+ | apt | ✅ | ✅ |
| CentOS 7/8 | yum/dnf | ✅ | ✅ |
| RHEL 7/8/9 | yum/dnf | ✅ | ✅ |
| Rocky Linux 8/9 | dnf | ✅ | ✅ |
| AlmaLinux 8/9 | dnf | ✅ | ✅ |
| Fedora 36+ | dnf | ✅ | ✅ |
| Arch Linux | pacman | ✅ | ✅ |
| Manjaro | pacman | ✅ | ✅ |

> **注意**：脚本会自动检测系统类型并使用相应的包管理器。

### 步骤 1：服务端配置（Linux 服务器）

```bash
# 1. 上传脚本到服务器
scp HostConfig/envinstall-docker.sh user@192.168.1.100:/tmp/

# 2. SSH 登录服务器
ssh user@192.168.1.100

# 3. 运行初始化脚本
cd /tmp
sudo bash envinstall-docker.sh

# 4. 按照提示完成配置
# - 选择容器引擎（Docker 或 Podman）
# - 配置网络（公网/内网网桥）
# - 生成 TLS 证书（用于远程访问）
# - 配置存储路径

# 5. 记录输出的配置信息
# - 服务器地址和端口（tcp://IP:2376）
# - 网桥名称（docker-pub, docker-nat）
# - 证书路径（/etc/docker/certs）
```

### 步骤 2：客户端配置（Windows）

```bash
# 1. 安装 Python 依赖
pip install docker

# 2. 从服务器下载 TLS 证书
scp user@192.168.1.100:/etc/docker/certs/ca.pem C:\docker-certs\
scp user@192.168.1.100:/etc/docker/certs/client-cert.pem C:\docker-certs\
scp user@192.168.1.100:/etc/docker/certs/client-key.pem C:\docker-certs\
```

### 步骤 3：测试连接

创建测试脚本 `test_docker.py`：

```python
from HostServer.OCInterface import HostServer
from MainObject.Config.HSConfig import HSConfig

# 配置服务器信息
config = HSConfig(
    server_name="my-docker-server",
    server_addr="192.168.1.100",  # 替换为你的服务器 IP
    launch_path="C:\\docker-certs",  # TLS 证书目录
    network_pub="docker-pub",
    network_nat="docker-nat",
    images_path="/var/lib/docker-images",
    system_path="/var/lib/docker-data",
    backup_path="/var/lib/docker-backups",
    extern_path="/var/lib/docker-mounts",
    remote_port=7681  # ttydserver Web Terminal 端口
)

# 创建服务器实例
server = HostServer(config)

# 连接到 Docker
result = server.HSLoader()
print(f"连接结果: {result.message}")

# 扫描现有容器
scan_result = server.VMDetect()
print(f"扫描结果: {scan_result.message}")
```

运行测试：

```bash
python test_docker.py
```

### 步骤 4：创建第一个容器

```python
from MainObject.Config.VMConfig import VMConfig
from MainObject.Config.VMPowers import VMPowers

# 创建容器配置
vm_conf = VMConfig(
   vm_uuid="test-container-001",
   os_name="ubuntu:22.04",  # Docker Hub 镜像
   # 或使用本地 tar 文件: "ubuntu-22.04.tar.gz"
   cpu_num=2,
   mem_num=4  # GB
)

# 创建容器
result = server.VMCreate(vm_conf)
print(f"创建结果: {result.message}")

# 启动容器
server.VMPowers("test-container-001", VMPowers.S_START)
print("容器已启动！")

# 获取 Web Terminal 访问地址
terminal_url = server.VMRemote("test-container-001")
print(f"Web Terminal: {terminal_url}")
```

---

## 📊 架构对比

### Docker vs LXD

```
┌─────────────────┐      TCP+TLS       ┌─────────────────┐
│  Windows 客户端  │ ◄────────────────► │  Linux 服务器    │
│                 │    (2376 端口)      │                 │
│  Python Script  │                    │  Docker Daemon  │
│  + docker SDK   │                    │  + Containers   │
└─────────────────┘                    └─────────────────┘
```

**Docker/Podman 特点**：
| 优势 | 说明 |
|------|------|
| ✅ | 跨平台（Windows/Linux/macOS） |
| ✅ | 远程管理（TLS 加密） |
| ✅ | 镜像生态丰富（Docker Hub） |
| ✅ | 轻量级容器 |
| ✅ | 支持 Web Terminal（ttyd） |
| ❌ | 不支持 ISO 挂载 |
| ❌ | 不支持 GPU 直通（本实现） |

### 容器引擎选择

| 特性 | Docker | Podman |
|------|--------|--------|
| 守护进程 | 需要 dockerd | 无守护进程 |
| Root 权限 | 需要 | 支持 rootless |
| Docker Hub | 原生支持 | 兼容 |
| Compose | docker-compose | podman-compose |
| 远程 API | TCP+TLS | 兼容 Docker API |

---

## 🔧 常用操作

### 容器管理

```python
# 列出所有容器
scan_result = server.VMDetect()

# 启动容器
server.VMPowers("container-name", VMPowers.S_START)

# 停止容器
server.VMPowers("container-name", VMPowers.H_CLOSE)

# 重启容器
server.VMPowers("container-name", VMPowers.S_RESET)

# 删除容器
server.VMDelete("container-name")
```

### 镜像管理

```python
# 从 Docker Hub 拉取镜像
vm_conf = VMConfig(
   vm_uuid="nginx-001",
   os_name="nginx:latest"  # 自动从 Docker Hub 拉取
)

# 从本地 tar 文件加载镜像
vm_conf = VMConfig(
   vm_uuid="custom-001",
   os_name="custom-image.tar.gz"  # 从 images_path 加载
)

# 安装镜像
result = server.VMSetups(vm_conf)
```

### 资源管理

```python
# 更新容器配置（需要重建容器）
vm_conf = server.vm_finds("container-name")
vm_conf.cpu_num = 4  # 修改为 4 核
vm_conf.mem_num = 8  # 修改为 8 GB

old_conf = deepcopy(vm_conf)
server.VMUpdate(vm_conf, old_conf)
```

### 目录挂载

```python
from MainObject.Config.SDConfig import SDConfig

# 创建挂载配置
hdd_conf = SDConfig(
    hdd_name="data-volume",
    hdd_flag=1  # 1=挂载, 0=卸载
)

# 挂载主机目录到容器
# 主机路径: {extern_path}/data-volume
# 容器路径: /mnt/data-volume
server.HDDMount("container-name", hdd_conf, in_flag=True)

# 卸载
server.HDDMount("container-name", hdd_conf, in_flag=False)
```

### 密码设置

```python
# 设置容器 root 密码
server.VMPasswd("container-name", "new_password")
```

### 备份恢复

```python
# 备份容器
server.VMBackup("container-name", "每日备份")

# 恢复容器
server.Restores("container-name", "backup-20250125.7z")
```

### Web Terminal 访问

```python
# 获取 Web Terminal URL
terminal_url = server.VMRemote("container-name")
print(f"访问地址: {terminal_url}")

# 在浏览器中打开该 URL 即可访问容器终端
```

---

## 🌐 网络配置

### 网桥说明

| 网桥 | 用途 |
|------|------|
| **docker-pub** | 公网网桥，用于需要公网访问的容器 |
| **docker-nat** | 内网网桥，用于内网通信的容器 |

### 配置示例

```python
from MainObject.Config.NCConfig import NCConfig

# 配置网卡
nic_conf = NCConfig(
    nic_name="eth0",
    mac_addr="02:42:ac:11:00:02",  # 可选
    ipv4_addr="192.168.1.100",
    ipv4_gate="192.168.1.1",
    ipv4_mask="255.255.255.0"
)

vm_conf.nic_all["eth0"] = nic_conf
```

### 网络模式

容器会根据 `HSConfig` 中的配置自动选择网桥：
- 默认使用 `network_nat`（内网）
- 可通过配置切换到 `network_pub`（公网）

---

## 🐛 故障排查

### 发行版特定问题

#### Ubuntu/Debian

```bash
# 如果遇到 GPG 密钥错误
sudo rm /etc/apt/keyrings/docker.gpg
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# 如果遇到依赖问题
sudo apt-get update
sudo apt-get install -f
```

#### CentOS/RHEL/Rocky/AlmaLinux

```bash
# 如果遇到 SELinux 问题
sudo setenforce 0
sudo sed -i 's/^SELINUX=enforcing$/SELINUX=permissive/' /etc/selinux/config

# 如果遇到 yum-config-manager 命令不存在
sudo yum install -y yum-utils

# CentOS 8 Stream 仓库问题
sudo dnf config-manager --set-enabled powertools
```

#### Fedora

```bash
# 如果遇到 cgroup v2 问题
sudo grubby --update-kernel=ALL --args="systemd.unified_cgroup_hierarchy=0"
sudo reboot

# 或者使用 Podman（原生支持 cgroup v2）
```

#### Arch Linux

```bash
# 如果遇到包冲突
sudo pacman -Syu
sudo pacman -S docker --overwrite '*'

# 启用 Docker 服务
sudo systemctl enable docker.service
sudo systemctl start docker.service
```

### 通用问题排查

#### 问题 1：连接失败

```
错误: Failed to connect to Docker: Connection refused
```

**解决方案**：

```bash
# 在服务器上检查 Docker 状态
systemctl status docker

# 检查端口监听
netstat -tlnp | grep 2376

# 检查防火墙
sudo ufw status
sudo ufw allow 2376/tcp

# 测试本地连接
docker ps
```

#### 问题 2：TLS 证书错误

```
错误: TLS certificates not found
```

**解决方案**：

1. 确认证书路径正确（`launch_path`）
2. 检查证书文件是否存在：
   - `ca.pem`
   - `client-cert.pem`
   - `client-key.pem`
3. 重新生成证书：`sudo bash envinstall-docker.sh`
4. 确保证书文件权限正确

#### 问题 3：容器创建失败

```
错误: Failed to create container
```

**解决方案**：

```bash
# 检查镜像是否存在
docker images

# 检查网络
docker network ls
docker network inspect docker-nat

# 查看 Docker 日志
journalctl -u docker -n 50

# 检查磁盘空间
df -h
```

#### 问题 4：镜像加载失败

```
错误: Image file not found
```

**解决方案**：

1. 确认镜像文件在 `images_path` 目录
2. 检查文件名是否正确（包括 .tar 或 .tar.gz 后缀）
3. 验证文件完整性：`tar -tzf image.tar.gz`

#### 问题 5：远程连接超时

```
错误: Connection timeout
```

**解决方案**：

```bash
# 检查服务器防火墙
sudo ufw status
sudo ufw allow 2376/tcp

# 检查 Docker daemon 配置
cat /etc/docker/daemon.json

# 确认 Docker 监听地址
sudo netstat -tlnp | grep dockerd

# 测试网络连通性
telnet 192.168.1.100 2376
```

---

## ✅ 部署检查清单

部署前请确认：

- [ ] Linux 服务器已安装 Docker 或 Podman
- [ ] 防火墙已开放 2376 端口（Docker TLS）
- [ ] 防火墙已开放 7681 端口（ttyd Web Terminal，可选）
- [ ] 客户端已安装 docker SDK：`pip install docker`
- [ ] TLS 证书已生成并复制到客户端
- [ ] 网桥已创建（docker-pub, docker-nat）
- [ ] 存储目录已配置
- [ ] 镜像文件已准备（如使用本地 tar）

---

## 🔐 安全建议

### TLS 证书管理

1. **定期更新证书**：证书默认有效期 365 天
2. **保护私钥**：确保 `client-key.pem` 权限为 400
3. **备份证书**：定期备份 `/etc/docker/certs/` 目录
4. **限制访问**：仅允许信任的 IP 访问 2376 端口

### 防火墙配置

```bash
# 仅允许特定 IP 访问 Docker API
sudo ufw allow from 192.168.1.0/24 to any port 2376 proto tcp

# 或使用 iptables
sudo iptables -A INPUT -p tcp --dport 2376 -s 192.168.1.0/24 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 2376 -j DROP
```

### 容器安全

1. **限制资源**：设置 CPU 和内存限制
2. **只读文件系统**：对不需要写入的容器使用只读模式
3. **最小权限**：避免使用 `--privileged` 模式
4. **定期更新**：及时更新容器镜像

---

## 🎯 最佳实践

### 镜像管理

1. **使用官方镜像**：优先使用 Docker Hub 官方镜像
2. **版本固定**：使用具体版本号而非 `latest`
3. **本地缓存**：常用镜像导出为 tar 文件
4. **定期清理**：删除未使用的镜像和容器

```bash
# 清理未使用的资源
docker system prune -a
```

### 网络规划

1. **分离网络**：公网和内网容器使用不同网桥
2. **IP 规划**：预先规划好 IP 地址段
3. **DNS 配置**：配置自定义 DNS 服务器

### 存储管理

1. **数据持久化**：重要数据使用卷挂载
2. **定期备份**：使用 `VMBackup` 定期备份容器
3. **监控空间**：定期检查磁盘使用情况

---

## 📚 更多信息

### 相关文档

- Docker 官方文档：https://docs.docker.com/
- Podman 官方文档：https://podman.io/
- Docker SDK for Python：https://docker-py.readthedocs.io/
- ttyd Web Terminal：https://github.com/tsl0922/ttyd

### 配置文件位置

| 文件 | 位置 |
|------|------|
| Docker daemon 配置 | `/etc/docker/daemon.json` |
| TLS 证书 | `/etc/docker/certs/` |
| 容器数据 | `/var/lib/docker/` |
| 初始化脚本 | `HostConfig/envinstall-docker.sh` |

### 常用命令

```bash
# Docker 命令
docker ps -a              # 列出所有容器
docker images             # 列出所有镜像
docker network ls         # 列出所有网络
docker volume ls          # 列出所有卷
docker logs <container>   # 查看容器日志
docker exec -it <container> bash  # 进入容器

# 系统管理
systemctl status docker   # 查看 Docker 状态
systemctl restart docker  # 重启 Docker
journalctl -u docker -f   # 实时查看日志
```

---

## 🎉 完成！

现在你可以从 Windows 客户端远程管理 Linux 服务器上的 Docker/Podman 容器了！

### 快速参考

```python
# 连接服务器
server = HostServer(config)
server.HSLoader()

# 创建容器
vm_conf = VMConfig(vm_uuid="test", os_name="ubuntu:22.04")
server.VMCreate(vm_conf)

# 启动容器
server.VMPowers("test", VMPowers.S_START)

# 访问终端
url = server.VMRemote("test")
```

> **提示**：如果你需要更高级的容器编排功能，可以考虑使用 Docker Compose 或 Kubernetes。
