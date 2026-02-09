-- OpenIDCS Host Management Database Schema
-- SQLite数据库表结构定义

-- 全局配置表 (hs_global)
CREATE TABLE IF NOT EXISTS hs_global
(
    id   TEXT PRIMARY KEY,
    data TEXT NOT NULL
);


-- 主机配置表 (hs_config)
CREATE TABLE IF NOT EXISTS hs_config
(
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    hs_name     TEXT NOT NULL UNIQUE,
    server_name TEXT      DEFAULT '',   -- 服务器的名称
    server_type TEXT NOT NULL,          -- 服务器的类型
    server_addr TEXT NOT NULL,          -- 服务器的地址
    server_user TEXT NOT NULL,          -- 服务器的用户
    server_pass TEXT NOT NULL,          -- 服务器的密码
    server_port INTEGER   DEFAULT 0,    -- 服务访问端口
    images_path TEXT,                   -- 系统镜像存储
    dvdrom_path TEXT,                   -- 光盘镜像存储
    system_path TEXT,                   -- 虚拟机的系统
    backup_path TEXT,                   -- 虚拟机的备份
    extern_path TEXT,                   -- 虚拟机的数据
    launch_path TEXT,                   -- 虚拟机的路径
    network_nat TEXT,                   -- 内网IP设备名
    network_pub TEXT,                   -- 公网IP设备名
    filter_name TEXT      DEFAULT '',   -- 前缀过滤名称
    i_kuai_addr TEXT      DEFAULT '',   -- 爱快OS的地址
    i_kuai_user TEXT      DEFAULT '',   -- 爱快OS的用户
    i_kuai_pass TEXT      DEFAULT '',   -- 爱快OS的密码
    ports_start INTEGER   DEFAULT 0,    -- TCP-端口起始
    ports_close INTEGER   DEFAULT 0,    -- TCP-端口结束
    remote_port INTEGER   DEFAULT 0,    -- VNC-服务端口
    system_maps TEXT      DEFAULT '{}', -- 系统映射字典
    images_maps TEXT      DEFAULT '{}', -- ISO镜像映射: 显示名称->文件名
    public_addr TEXT      DEFAULT '[]', -- 公共IP46列表
    extend_data TEXT      DEFAULT '{}', -- 存储扩展数据
    server_dnss TEXT      DEFAULT '[]', -- NS服务器列表
    limits_nums INTEGER   DEFAULT 0,    -- VMS虚拟数量
    ipaddr_maps TEXT      DEFAULT '{}', -- IP地址的字典
    ipaddr_dnss TEXT      DEFAULT '["119.29.29.29", "223.5.5.5"]', -- DNS服务器列表
    is_enabled  INTEGER   DEFAULT 1,    -- 主机是否启用 (1=启用, 0=禁用)
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 主机状态表 (hs_status)
CREATE TABLE IF NOT EXISTS hs_status
(
    id          INTEGER PRIMARY KEY AUTOINCREMENT, -- 主键
    hs_name     TEXT NOT NULL,                     -- 主机名称
    status_data TEXT NOT NULL,                     -- JSON格式存储HWStatus数据
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (hs_name) REFERENCES hs_config (hs_name) ON DELETE CASCADE
);


-- 虚拟机存储配置表 (vm_saving)
CREATE TABLE IF NOT EXISTS vm_saving
(
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    hs_name    TEXT NOT NULL, -- 主机名称
    vm_uuid    TEXT NOT NULL, -- 虚拟机UUID
    vm_config  TEXT NOT NULL, -- JSON格式存储VMConfig数据
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (hs_name) REFERENCES hs_config (hs_name) ON DELETE CASCADE,
    UNIQUE (hs_name, vm_uuid)
);

-- 虚拟机状态表 (vm_status) - 优化版：一行存储一个状态
CREATE TABLE IF NOT EXISTS vm_status
(
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    hs_name     TEXT NOT NULL,                     -- 主机名称
    vm_uuid     TEXT NOT NULL,                     -- 虚拟机UUID
    status_data TEXT NOT NULL,                     -- JSON格式存储单个HWStatus数据
    ac_status   TEXT,                              -- 虚拟机状态(STARTED/STOPPED等)，用于快速查询
    on_update   INTEGER,                           -- 状态更新时间戳(秒)，用于时间范围查询
    flu_usage   REAL DEFAULT 0,                    -- 流量使用量(MB)，用于统计
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- 记录时间
    FOREIGN KEY (hs_name) REFERENCES hs_config (hs_name) ON DELETE CASCADE
    -- 注意: 不再引用 vm_saving(vm_uuid)，因为 vm_uuid 不是单列唯一键
);

-- 虚拟机任务表 (vm_tasker)
CREATE TABLE IF NOT EXISTS vm_tasker
(
    id         INTEGER PRIMARY KEY AUTOINCREMENT, -- 主键
    hs_name    TEXT NOT NULL,                     -- 主机名称
    task_data  TEXT NOT NULL,                     -- JSON格式存储HSTasker数据
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (hs_name) REFERENCES hs_config (hs_name) ON DELETE CASCADE
);

-- 日志记录表 (hs_logger)
CREATE TABLE IF NOT EXISTS hs_logger
(
    id         INTEGER PRIMARY KEY AUTOINCREMENT,   -- 主键
    hs_name    TEXT,                                -- 主机名称
    log_data   TEXT NOT NULL,                       -- JSON格式存储ZMessage数据
    log_level  TEXT      DEFAULT 'INFO',            -- 日志级别
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- 创建时间
    FOREIGN KEY (hs_name) REFERENCES hs_config (hs_name) ON DELETE SET NULL
);

-- 全局反向代理配置表 (web_proxy)
-- CREATE TABLE IF NOT EXISTS web_proxy
-- (
--     id         INTEGER PRIMARY KEY AUTOINCREMENT,   -- 主键
--     lan_port   INTEGER NOT NULL,                    -- 内网端口
--     lan_addr   TEXT NOT NULL,                       -- 内网地址
--     web_addr   TEXT NOT NULL UNIQUE,                -- 域名地址
--     web_tips   TEXT DEFAULT '',                     -- 代理说明
--     is_https   INTEGER DEFAULT 1,                   -- 是否HTTPS (1=是, 0=否)
--     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- 创建时间
--     updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP  -- 更新时间
-- );

-- 用户表 (web_users)
CREATE TABLE IF NOT EXISTS web_users
(
    id                INTEGER PRIMARY KEY AUTOINCREMENT,   -- 主键
    username          TEXT NOT NULL UNIQUE,                -- 用户名
    password          TEXT NOT NULL,                       -- 密码（加密存储）
    email             TEXT NOT NULL UNIQUE,                -- 邮箱
    is_admin          INTEGER   DEFAULT 0,                 -- 是否管理员 (1=是, 0=否)
    is_active         INTEGER   DEFAULT 1,                 -- 是否启用 (1=启用, 0=禁用)
    email_verified    INTEGER   DEFAULT 0,                 -- 邮箱是否验证 (1=已验证, 0=未验证)
    verify_token      TEXT      DEFAULT '',                -- 邮箱验证token
    reset_token       TEXT      DEFAULT '',                -- 密码重置token
    
    -- 权限设置
    can_create_vm     INTEGER   DEFAULT 0,                 -- 允许创建虚拟机 (1=允许, 0=不允许)
    can_delete_vm     INTEGER   DEFAULT 0,                 -- 允许删除虚拟机 (1=允许, 0=不允许)
    can_modify_vm     INTEGER   DEFAULT 0,                 -- 允许修改虚拟机 (1=允许, 0=不允许)
    
    -- 资源配额
    quota_cpu         INTEGER   DEFAULT 0,                 -- CPU核心数配额
    quota_ram         INTEGER   DEFAULT 0,                 -- RAM内存配额(GB)
    quota_ssd         INTEGER   DEFAULT 0,                 -- SSD磁盘配额(GB)
    quota_gpu         INTEGER   DEFAULT 0,                 -- GPU显存配额(GB)
    quota_nat_ports   INTEGER   DEFAULT 0,                 -- NAT端口数配额
    quota_web_proxy   INTEGER   DEFAULT 0,                 -- WEB代理数量配额
    quota_nat_ips     INTEGER   DEFAULT 0,                 -- 内网IP数量配额
    quota_pub_ips     INTEGER   DEFAULT 0,                 -- 公网IP数量配额
    quota_bandwidth_up    INTEGER DEFAULT 0,                 -- 最大上行带宽(Mbps)
    quota_bandwidth_down  INTEGER DEFAULT 0,                 -- 最大下行带宽(Mbps)
    quota_traffic     INTEGER   DEFAULT 0,                 -- 每月最大流量(GB)
    
    -- 已使用资源（实时统计）
    used_cpu          INTEGER   DEFAULT 0,                 -- 已使用CPU核心数
    used_ram          INTEGER   DEFAULT 0,                 -- 已使用RAM(GB)
    used_ssd          INTEGER   DEFAULT 0,                 -- 已使用SSD(GB)
    used_gpu          INTEGER   DEFAULT 0,                 -- 已使用GPU显存(GB)
    used_nat_ports    INTEGER   DEFAULT 0,                 -- 已使用NAT端口数
    used_web_proxy    INTEGER   DEFAULT 0,                 -- 已使用WEB代理数
    used_nat_ips      INTEGER   DEFAULT 0,                 -- 已使用内网IP数
    used_pub_ips      INTEGER   DEFAULT 0,                 -- 已使用公网IP数
    used_bandwidth_up    INTEGER   DEFAULT 0,                 -- 已使用上行带宽(Mbps)
    used_bandwidth_down  INTEGER   DEFAULT 0,                 -- 已使用下行带宽(Mbps)
    used_traffic      INTEGER   DEFAULT 0,                 -- 本月已使用流量(GB)
    
    -- 分配的服务器列表（JSON数组，存储hs_name列表）
    assigned_hosts    TEXT      DEFAULT '[]',              -- 分配的主机列表
    
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- 创建时间
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- 更新时间
    last_login        TIMESTAMP DEFAULT NULL                -- 最后登录时间
);

-- 创建索引以提高查询性能
CREATE INDEX IF NOT EXISTS idx_hs_config_name ON hs_config (hs_name);
CREATE INDEX IF NOT EXISTS idx_hs_status_name ON hs_status (hs_name);
CREATE INDEX IF NOT EXISTS idx_vm_saving_name ON vm_saving (hs_name);
CREATE INDEX IF NOT EXISTS idx_vm_saving_uuid ON vm_saving (vm_uuid);
CREATE INDEX IF NOT EXISTS idx_vm_status_name ON vm_status (hs_name);
CREATE INDEX IF NOT EXISTS idx_vm_status_uuid ON vm_status (vm_uuid);
CREATE INDEX IF NOT EXISTS idx_vm_status_name_uuid ON vm_status (hs_name, vm_uuid);
CREATE INDEX IF NOT EXISTS idx_vm_status_timestamp ON vm_status (on_update);
CREATE INDEX IF NOT EXISTS idx_vm_status_recorded ON vm_status (recorded_at);
CREATE INDEX IF NOT EXISTS idx_vm_tasker_name ON vm_tasker (hs_name);
CREATE INDEX IF NOT EXISTS idx_hs_logger_name ON hs_logger (hs_name);
CREATE INDEX IF NOT EXISTS idx_hs_logger_time ON hs_logger (created_at);
CREATE INDEX IF NOT EXISTS idx_web_users_username ON web_users (username);
CREATE INDEX IF NOT EXISTS idx_web_users_email ON web_users (email);

