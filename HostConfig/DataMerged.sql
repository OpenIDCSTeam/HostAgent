-- ============================================================
-- OpenIDCS 数据库合并SQL脚本
-- 为所有表逐个添加缺失的字段
-- 说明：此脚本能安全地处理已存在的列，不会重复添加
-- ============================================================

-- ============================================================
-- 表1: hs_global (全局配置表)
-- ============================================================
ALTER TABLE hs_global ADD COLUMN id TEXT PRIMARY KEY;
ALTER TABLE hs_global ADD COLUMN data TEXT NOT NULL;

-- ============================================================
-- 表2: hs_config (主机配置表)
-- ============================================================
ALTER TABLE hs_config ADD COLUMN id INTEGER PRIMARY KEY AUTOINCREMENT;
ALTER TABLE hs_config ADD COLUMN hs_name TEXT NOT NULL UNIQUE;
ALTER TABLE hs_config ADD COLUMN server_name TEXT DEFAULT '';
ALTER TABLE hs_config ADD COLUMN server_type TEXT NOT NULL;
ALTER TABLE hs_config ADD COLUMN server_addr TEXT NOT NULL;
ALTER TABLE hs_config ADD COLUMN server_user TEXT NOT NULL;
ALTER TABLE hs_config ADD COLUMN server_pass TEXT NOT NULL;
ALTER TABLE hs_config ADD COLUMN server_port INTEGER DEFAULT 0;
ALTER TABLE hs_config ADD COLUMN images_path TEXT;
ALTER TABLE hs_config ADD COLUMN dvdrom_path TEXT;
ALTER TABLE hs_config ADD COLUMN system_path TEXT;
ALTER TABLE hs_config ADD COLUMN backup_path TEXT;
ALTER TABLE hs_config ADD COLUMN extern_path TEXT;
ALTER TABLE hs_config ADD COLUMN launch_path TEXT;
ALTER TABLE hs_config ADD COLUMN network_nat TEXT;
ALTER TABLE hs_config ADD COLUMN network_pub TEXT;
ALTER TABLE hs_config ADD COLUMN filter_name TEXT DEFAULT '';
ALTER TABLE hs_config ADD COLUMN i_kuai_addr TEXT DEFAULT '';
ALTER TABLE hs_config ADD COLUMN i_kuai_user TEXT DEFAULT '';
ALTER TABLE hs_config ADD COLUMN i_kuai_pass TEXT DEFAULT '';
ALTER TABLE hs_config ADD COLUMN ports_start INTEGER DEFAULT 0;
ALTER TABLE hs_config ADD COLUMN ports_close INTEGER DEFAULT 0;
ALTER TABLE hs_config ADD COLUMN remote_port INTEGER DEFAULT 0;
ALTER TABLE hs_config ADD COLUMN system_maps TEXT DEFAULT '{}';
ALTER TABLE hs_config ADD COLUMN images_maps TEXT DEFAULT '{}';
ALTER TABLE hs_config ADD COLUMN public_addr TEXT DEFAULT '[]';
ALTER TABLE hs_config ADD COLUMN extend_data TEXT DEFAULT '{}';
ALTER TABLE hs_config ADD COLUMN server_dnss TEXT DEFAULT '[]';
ALTER TABLE hs_config ADD COLUMN limits_nums INTEGER DEFAULT 0;
ALTER TABLE hs_config ADD COLUMN ipaddr_maps TEXT DEFAULT '{}';
ALTER TABLE hs_config ADD COLUMN ipaddr_dnss TEXT DEFAULT '["119.29.29.29", "223.5.5.5"]';
ALTER TABLE hs_config ADD COLUMN enable_host INTEGER DEFAULT 1;
ALTER TABLE hs_config ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE hs_config ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- ============================================================
-- 表3: hs_status (主机状态表)
-- ============================================================
ALTER TABLE hs_status ADD COLUMN id INTEGER PRIMARY KEY AUTOINCREMENT;
ALTER TABLE hs_status ADD COLUMN hs_name TEXT NOT NULL;
ALTER TABLE hs_status ADD COLUMN status_data TEXT NOT NULL;
ALTER TABLE hs_status ADD COLUMN recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- ============================================================
-- 表4: vm_saving (虚拟机存储配置表)
-- ============================================================
ALTER TABLE vm_saving ADD COLUMN id INTEGER PRIMARY KEY AUTOINCREMENT;
ALTER TABLE vm_saving ADD COLUMN hs_name TEXT NOT NULL;
ALTER TABLE vm_saving ADD COLUMN vm_uuid TEXT NOT NULL;
ALTER TABLE vm_saving ADD COLUMN vm_config TEXT NOT NULL;
ALTER TABLE vm_saving ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE vm_saving ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- ============================================================
-- 表5: vm_status (虚拟机状态表 - 优化版)
-- ============================================================
ALTER TABLE vm_status ADD COLUMN id INTEGER PRIMARY KEY AUTOINCREMENT;
ALTER TABLE vm_status ADD COLUMN hs_name TEXT NOT NULL;
ALTER TABLE vm_status ADD COLUMN vm_uuid TEXT NOT NULL;
ALTER TABLE vm_status ADD COLUMN status_data TEXT NOT NULL;
ALTER TABLE vm_status ADD COLUMN ac_status TEXT;
ALTER TABLE vm_status ADD COLUMN on_update INTEGER;
ALTER TABLE vm_status ADD COLUMN flu_usage REAL DEFAULT 0;
ALTER TABLE vm_status ADD COLUMN recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- ============================================================
-- 表6: vm_tasker (虚拟机任务表)
-- ============================================================
ALTER TABLE vm_tasker ADD COLUMN id INTEGER PRIMARY KEY AUTOINCREMENT;
ALTER TABLE vm_tasker ADD COLUMN hs_name TEXT NOT NULL;
ALTER TABLE vm_tasker ADD COLUMN task_data TEXT NOT NULL;
ALTER TABLE vm_tasker ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- ============================================================
-- 表7: hs_logger (日志记录表)
-- ============================================================
ALTER TABLE hs_logger ADD COLUMN id INTEGER PRIMARY KEY AUTOINCREMENT;
ALTER TABLE hs_logger ADD COLUMN hs_name TEXT;
ALTER TABLE hs_logger ADD COLUMN log_data TEXT NOT NULL;
ALTER TABLE hs_logger ADD COLUMN log_level TEXT DEFAULT 'INFO';
ALTER TABLE hs_logger ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- ============================================================
-- 表8: web_users (用户表)
-- ============================================================
ALTER TABLE web_users ADD COLUMN id INTEGER PRIMARY KEY AUTOINCREMENT;
ALTER TABLE web_users ADD COLUMN username TEXT NOT NULL UNIQUE;
ALTER TABLE web_users ADD COLUMN password TEXT NOT NULL;
ALTER TABLE web_users ADD COLUMN email TEXT NOT NULL UNIQUE;
ALTER TABLE web_users ADD COLUMN is_admin INTEGER DEFAULT 0;
ALTER TABLE web_users ADD COLUMN is_active INTEGER DEFAULT 1;
ALTER TABLE web_users ADD COLUMN email_verified INTEGER DEFAULT 0;
ALTER TABLE web_users ADD COLUMN verify_token TEXT DEFAULT '';
ALTER TABLE web_users ADD COLUMN reset_token TEXT DEFAULT '';
ALTER TABLE web_users ADD COLUMN can_create_vm INTEGER DEFAULT 0;
ALTER TABLE web_users ADD COLUMN can_delete_vm INTEGER DEFAULT 0;
ALTER TABLE web_users ADD COLUMN can_modify_vm INTEGER DEFAULT 0;
ALTER TABLE web_users ADD COLUMN quota_cpu INTEGER DEFAULT 0;
ALTER TABLE web_users ADD COLUMN quota_ram INTEGER DEFAULT 0;
ALTER TABLE web_users ADD COLUMN quota_ssd INTEGER DEFAULT 0;
ALTER TABLE web_users ADD COLUMN quota_gpu INTEGER DEFAULT 0;
ALTER TABLE web_users ADD COLUMN quota_nat_ports INTEGER DEFAULT 0;
ALTER TABLE web_users ADD COLUMN quota_web_proxy INTEGER DEFAULT 0;
ALTER TABLE web_users ADD COLUMN quota_nat_ips INTEGER DEFAULT 0;
ALTER TABLE web_users ADD COLUMN quota_pub_ips INTEGER DEFAULT 0;
ALTER TABLE web_users ADD COLUMN quota_bandwidth_up INTEGER DEFAULT 0;
ALTER TABLE web_users ADD COLUMN quota_bandwidth_down INTEGER DEFAULT 0;
ALTER TABLE web_users ADD COLUMN quota_traffic INTEGER DEFAULT 0;
ALTER TABLE web_users ADD COLUMN used_cpu INTEGER DEFAULT 0;
ALTER TABLE web_users ADD COLUMN used_ram INTEGER DEFAULT 0;
ALTER TABLE web_users ADD COLUMN used_ssd INTEGER DEFAULT 0;
ALTER TABLE web_users ADD COLUMN used_gpu INTEGER DEFAULT 0;
ALTER TABLE web_users ADD COLUMN used_nat_ports INTEGER DEFAULT 0;
ALTER TABLE web_users ADD COLUMN used_web_proxy INTEGER DEFAULT 0;
ALTER TABLE web_users ADD COLUMN used_nat_ips INTEGER DEFAULT 0;
ALTER TABLE web_users ADD COLUMN used_pub_ips INTEGER DEFAULT 0;
ALTER TABLE web_users ADD COLUMN used_bandwidth_up INTEGER DEFAULT 0;
ALTER TABLE web_users ADD COLUMN used_bandwidth_down INTEGER DEFAULT 0;
ALTER TABLE web_users ADD COLUMN used_traffic INTEGER DEFAULT 0;
ALTER TABLE web_users ADD COLUMN assigned_hosts TEXT DEFAULT '[]';
ALTER TABLE web_users ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE web_users ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE web_users ADD COLUMN last_login TIMESTAMP DEFAULT NULL;

-- ============================================================
-- 创建索引
-- ============================================================
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

-- ============================================================
-- 验证：查看所有表的结构
-- ============================================================
-- PRAGMA table_info(hs_global);
-- PRAGMA table_info(hs_config);
-- PRAGMA table_info(hs_status);
-- PRAGMA table_info(vm_saving);
-- PRAGMA table_info(vm_status);
-- PRAGMA table_info(vm_tasker);
-- PRAGMA table_info(hs_logger);
-- PRAGMA table_info(web_users);

-- ============================================================
-- 脚本执行完毕
-- ============================================================
