# AllBuilder - OpenIDCS-Client 构建工具

<div align="center">

将 OpenIDCS-Client 打包成独立可执行文件的完整构建工具集

[快速开始](#快速开始) • [详细文档](#详细文档) • [环境要求](#环境要求) • [常见问题](#常见问题)

</div>

## 📁 目录结构

```
AllBuilder/
├── Nuitka 构建（推荐）
│   ├── build_nuitkaui.py       # Nuitka Python 打包脚本（跨平台）
│   ├── build_nuitkaui.bat      # Windows 批处理脚本（一键打包）
│   └── build_nuitkaui.sh       # Linux/Mac Shell 脚本（一键打包）
│
├── cx_Freeze 构建
│   ├── build_cxfreeze.py       # cx_Freeze 打包脚本
│   ├── build_cxfreeze.bat      # Windows 批处理脚本（仅后端）
│   ├── build_cxfreeze.sh       # Linux/Mac Shell 脚本（仅后端）
│   ├── build_cxfreeze_full.bat # Windows 完整打包（前端+后端）
│   └── build_cxfreeze_full.sh  # Linux/Mac 完整打包（前端+后端）
│
├── Websockify 代理构建
│   ├── build_vncproxy.py       # PyInstaller 打包脚本
│   └── websockify.spec         # PyInstaller 配置文件
│
└── 文档
    ├── README_CXFREEZE_REACT.md  # React 前端 + Python 后端打包指南
    └── QUICKSTART_CXFREEZE.md    # cx_Freeze 快速开始指南
```

## 🚀 快速开始

### 方式一：使用批处理/Shell脚本（推荐）

#### 打包 Python 后端（传统方式）

**Windows 用户**：
```batch
cd AllBuilder
build_nuitkaui.bat
```

**Linux/Mac 用户**：
```bash
cd AllBuilder
chmod +x build_nuitkaui.sh
./build_nuitkaui.sh
```

#### 打包 Python 后端 + React 前端（完整方式）

如果你的项目包含 React 前端（位于 `FrontPages/` 目录），使用以下命令：

**Windows 用户**：
```batch
cd AllBuilder
build_cxfreeze_full.bat
```

**Linux/Mac 用户**：
```bash
cd AllBuilder
chmod +x build_cxfreeze_full.sh
./build_cxfreeze_full.sh
```

> 💡 **提示**：完整打包会自动构建 React 前端，并将其集成到 Python 后端的静态文件目录中。

### 方式二：使用 Python 脚本

```bash
cd AllBuilder
python build_nuitkaui.py
```

## 📦 输出位置

所有构建的临时文件和输出文件统一存放在项目根目录的 `BuildCache` 文件夹中：

### Nuitka 构建输出
- **构建目录**: `BuildCache/nuitka/`
- **Windows 输出**: `BuildCache/nuitka/OpenIDCS-Client.exe`
- **Linux/Mac 输出**: `BuildCache/nuitka/OpenIDCS-Client`

### cx_Freeze 构建输出
- **构建目录**: `BuildCache/cxfreeze/`
- **Windows 输出**: `BuildCache/cxfreeze/OpenIDCS-Client.exe`
- **Linux/Mac 输出**: `BuildCache/cxfreeze/OpenIDCS-Client`

### Websockify 代理输出
- **构建目录**: `BuildCache/websockify/`
- **最终文件**: `Websockify/websocketproxy.exe`（自动复制）

> 💡 **提示**: BuildCache 目录用于存放所有构建过程中的临时文件和输出文件，可以随时删除以清理空间。

## 📚 详细文档

| 文档 | 说明 |
|------|------|
| [快速开始](NUITKA_QUICKSTART.md) | 5分钟快速入门指南 |
| [完整打包文档](NUITKA_BUILD.md) | 详细的打包配置和优化说明 |
| [文件清单](NUITKA_FILES.md) | 所有构建文件的详细说明 |
| [React 前端打包指南](README_CXFREEZE_REACT.md) | Python 后端 + React 前端完整打包方案 |
| [cx_Freeze 快速开始](QUICKSTART_CXFREEZE.md) | cx_Freeze 一键打包指南 |

## ⚙️ 环境要求

### 系统要求
- **Python 版本**: 3.7 或更高
- **磁盘空间**: 至少 4GB 可用空间
- **内存**: 至少 4GB RAM
- **操作系统**: Windows / Linux / macOS

### 编译器要求

**Windows**:
- Visual Studio Build Tools 2017 或更高版本
- 或 Visual Studio Community 2017+（安装 C++ 桌面开发组件）

**Linux**:
```bash
# Ubuntu/Debian
sudo apt-get install build-essential

# CentOS/RHEL
sudo yum groupinstall "Development Tools"
```

**macOS**:
```bash
xcode-select --install
```

### 依赖安装

**安装所有依赖（推荐）**：
```bash
pip install -r requirements.txt
```

**只安装核心依赖**：
```bash
pip install Flask loguru requests websockify psutil GPUtil py-cpuinfo py7zr nuitka
```

### 可选依赖

项目包含一些可选依赖，用于支持特定的虚拟化平台：

- **pyvmomi** - VMware ESXi/vSphere 支持
- **pylxd** - LXD 容器管理支持
- **docker** - Docker/Podman 容器管理支持

如果不需要这些特定功能，可以不安装。打包脚本会自动检测并只包含已安装的包。

详细说明请查看：[可选依赖说明](OPTIONAL_DEPENDENCIES.md)

## 🔨 构建工具对比

| 特性 | Nuitka | cx_Freeze |
|------|--------|-----------|
| 性能 | ⭐⭐⭐⭐⭐ 优秀 | ⭐⭐⭐ 良好 |
| 体积 | ⭐⭐⭐⭐ 较小 | ⭐⭐⭐ 较大 |
| 兼容性 | ⭐⭐⭐⭐ 很好 | ⭐⭐⭐⭐⭐ 优秀 |
| 启动速度 | ⭐⭐⭐⭐⭐ 快 | ⭐⭐⭐ 中等 |
| 构建时间 | ⭐⭐ 较慢 | ⭐⭐⭐⭐ 快 |
| 推荐度 | ✅ 推荐 | ✅ 可选 |

## 💡 使用提示

1. **首次打包**: 需要编译所有依赖，预计耗时 10-30 分钟，这是正常的
2. **增量构建**: 第二次打包会快很多，Nuitka 支持缓存
3. **清理缓存**: 如需完全重新打包，删除 `BuildCache` 目录
4. **测试运行**: 打包完成后，先测试可执行文件是否正常运行
5. **发布部署**: 建议在目标系统上进行打包，以确保最大兼容性

## 🐛 常见问题

### 1. 编译器找不到

**Windows**: 安装 Visual Studio Build Tools，确保包含 C++ 组件

**Linux**: 安装 `build-essential` 或对应的开发工具组

**macOS**: 运行 `xcode-select --install`

### 2. Nuitka 构建失败

- 确保 Python 版本 >= 3.7
- 检查编译器是否正确安装
- 尝试更新 Nuitka: `pip install --upgrade nuitka`

### 3. 打包后运行报错

- 检查是否缺少必要的依赖
- 查看日志文件定位问题
- 尝试使用 `--standalone` 模式重新打包

### 4. 可执行文件体积过大

Nuitka 打包会包含所有依赖，这是正常的。可以使用 `--include-plugin` 精简打包体积。

更多问题请查看：[完整打包文档](NUITKA_BUILD.md#常见问题)

## 📄 许可证

本构建工具集遵循项目主许可证。

---

<div align="center">

如有问题或建议，欢迎提交 Issue

</div>
