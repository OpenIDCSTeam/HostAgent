import sqlite3
import json
import os
import sys
import traceback
from typing import Dict, List, Any, Optional
from loguru import logger
from MainObject.Config.HSConfig import HSConfig
from MainObject.Config.VMConfig import VMConfig
from MainObject.Public.ZMessage import ZMessage


class DataManager:
    """HostManage SQLite数据库操作类"""

    def __init__(self, path: str = "./DataSaving/hostmanage.db"):
        self.db_path = path
        self.dir_db_loader()
        self.set_db_sqlite()

    # ==================== 数据库初始化 =====================
    def dir_db_loader(self):
        """确保数据库目录存在"""
        db_dir = os.path.dirname(self.db_path)
        if not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

    def get_db_sqlite(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)  # 添加30秒超时
        conn.row_factory = sqlite3.Row  # 启用字典式访问
        # 启用WAL模式以提高并发性能
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def set_db_sqlite(self):
        """初始化数据库表结构"""
        # 修正SQL文件路径，兼容开发环境和打包后的环境
        # 在打包后，需要从可执行文件所在目录查找
        if getattr(sys, 'frozen', False):
            # 打包后的环境：从可执行文件所在目录查找
            project_root = os.path.dirname(sys.executable)
        else:
            # 开发环境：从项目根目录查找
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        sql_file_path = os.path.join(project_root, "HostConfig", "HostManage.sql")

        if os.path.exists(sql_file_path):
            with open(sql_file_path, 'r', encoding='utf-8') as f:
                sql_script = f.read()

            conn = self.get_db_sqlite()
            try:
                # 分割SQL脚本，逐条执行以更好地处理ALTER TABLE错误
                sql_statements = [stmt.strip() for stmt in sql_script.split(';') if stmt.strip()]

                for sql in sql_statements:
                    try:
                        conn.execute(sql)
                    except sqlite3.OperationalError as e:
                        # 忽略ALTER TABLE的重复字段错误
                        if "duplicate column name" in str(e).lower():
                            logger.warning(f"字段已存在，跳过: {e}")
                            continue
                        else:
                            raise e

                conn.commit()
                logger.info(f"[HostDatabase] 数据库初始化完成: {self.db_path}")
                
                # 执行数据迁移：将旧格式的vm_status转换为新格式
                self._migrate_vm_status_data(conn)
                
                # 创建默认管理员用户（如果不存在）
                self._create_default_admin()
                
            except Exception as e:
                logger.error(f"数据库初始化错误: {e}")
                conn.rollback()
            finally:
                conn.close()
        else:
            logger.warning(f"[HostDatabase] 警告: SQL文件不存在: {sql_file_path}")
            logger.warning(f"[HostDatabase] 当前工作目录: {os.getcwd()}")
            logger.warning(f"[HostDatabase] 项目根目录: {project_root}")

    def _migrate_vm_status_data(self, conn: sqlite3.Connection):
        """迁移vm_status数据：将旧格式（JSON数组）转换为新格式（多行记录）"""
        try:
            # 先检查并添加缺失的字段
            cursor = conn.execute("PRAGMA table_info(vm_status)")
            columns = {row[1] for row in cursor.fetchall()}
            
            # 需要的字段列表
            required_columns = {
                'ac_status': 'TEXT',
                'on_update': 'INTEGER',
                'flu_usage': 'REAL DEFAULT 0'
            }
            
            # 添加缺失的字段
            for col_name, col_type in required_columns.items():
                if col_name not in columns:
                    try:
                        conn.execute(f"ALTER TABLE vm_status ADD COLUMN {col_name} {col_type}")
                        logger.info(f"[HostDatabase] 添加字段: vm_status.{col_name}")
                    except sqlite3.OperationalError as e:
                        if "duplicate column name" not in str(e).lower():
                            raise e
            
            conn.commit()
            
            # 检查是否需要迁移：查询是否有旧格式数据
            cursor = conn.execute("SELECT id, hs_name, vm_uuid, status_data FROM vm_status LIMIT 1")
            row = cursor.fetchone()
            
            if not row:
                logger.info("[HostDatabase] vm_status表为空，无需迁移")
                return
            
            # 尝试解析第一条记录，判断是否为旧格式
            status_data = json.loads(row["status_data"])
            
            # 如果status_data是列表，说明是旧格式，需要迁移
            if isinstance(status_data, list):
                logger.info("[HostDatabase] 检测到旧格式vm_status数据，开始迁移...")
                
                # 读取所有旧数据
                cursor = conn.execute("SELECT id, hs_name, vm_uuid, status_data, recorded_at FROM vm_status")
                old_records = cursor.fetchall()
                
                # 创建临时表存储新数据
                conn.execute("""
                    CREATE TEMPORARY TABLE vm_status_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        hs_name TEXT NOT NULL,
                        vm_uuid TEXT NOT NULL,
                        status_data TEXT NOT NULL,
                        ac_status TEXT,
                        on_update INTEGER,
                        flu_usage REAL DEFAULT 0,
                        recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # 转换并插入新数据
                insert_sql = """
                    INSERT INTO vm_status_new (hs_name, vm_uuid, status_data, ac_status, on_update, flu_usage, recorded_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """
                
                total_converted = 0
                for old_row in old_records:
                    hs_name = old_row["hs_name"]
                    vm_uuid = old_row["vm_uuid"]
                    status_list = json.loads(old_row["status_data"])
                    recorded_at = old_row["recorded_at"]
                    
                    # 如果是列表，展开为多行
                    if isinstance(status_list, list):
                        for status_dict in status_list:
                            if isinstance(status_dict, dict):
                                ac_status = status_dict.get('ac_status', '')
                                on_update = status_dict.get('on_update', 0)
                                flu_usage = status_dict.get('flu_usage', 0)
                                status_data_json = json.dumps(status_dict)
                                
                                conn.execute(insert_sql, (
                                    hs_name, vm_uuid, status_data_json, 
                                    ac_status, on_update, flu_usage, recorded_at
                                ))
                                total_converted += 1
                    # 如果是字典，直接插入一行
                    elif isinstance(status_list, dict):
                        ac_status = status_list.get('ac_status', '')
                        on_update = status_list.get('on_update', 0)
                        flu_usage = status_list.get('flu_usage', 0)
                        status_data_json = json.dumps(status_list)
                        
                        conn.execute(insert_sql, (
                            hs_name, vm_uuid, status_data_json, 
                            ac_status, on_update, flu_usage, recorded_at
                        ))
                        total_converted += 1
                
                # 删除旧表，重命名新表
                conn.execute("DROP TABLE vm_status")
                conn.execute("ALTER TABLE vm_status_new RENAME TO vm_status")
                
                # 重建索引
                conn.execute("CREATE INDEX IF NOT EXISTS idx_vm_status_name ON vm_status (hs_name)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_vm_status_uuid ON vm_status (vm_uuid)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_vm_status_name_uuid ON vm_status (hs_name, vm_uuid)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_vm_status_timestamp ON vm_status (on_update)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_vm_status_recorded ON vm_status (recorded_at)")
                
                conn.commit()
                logger.info(f"[HostDatabase] vm_status数据迁移完成，共转换 {total_converted} 条记录")
            else:
                logger.info("[HostDatabase] vm_status数据已是新格式，无需迁移")
                
        except Exception as e:
            logger.error(f"[HostDatabase] vm_status数据迁移失败: {e}")
            import traceback
            traceback.print_exc()
            conn.rollback()

    def _create_default_admin(self):
        """创建默认管理员用户（如果不存在）- 使用bearer作为初始密码"""
        try:
            # 检查是否已有管理员用户
            conn = self.get_db_sqlite()
            cursor = conn.execute("SELECT COUNT(*) FROM web_users WHERE is_admin = 1")
            admin_count = cursor.fetchone()[0]
            
            if admin_count == 0:
                # 获取bearer字段作为初始密码
                ap_config = self.get_ap_config()
                bearer_token = ap_config.get("bearer", "")
                
                if not bearer_token:
                    logger.warning("[HostDatabase] bearer字段为空，使用默认密码")
                    bearer_token = "admin123"
                
                # 创建默认管理员
                from MainObject.Public.ZMessage import ZMessage
                hashed_password = ZMessage.z_hash(bearer_token)
                
                user_id = self.create_user(
                    username="admin",
                    password=hashed_password,
                    email="admin@localhost"
                )
                
                if user_id:
                    # 设置为管理员和启用状态
                    conn.execute("""
                        UPDATE web_users 
                        SET is_admin = 1, is_active = 1, 
                            can_create_vm = 1, can_modify_vm = 1, can_delete_vm = 1,
                            quota_cpu = 32, quota_ram = 64, quota_ssd = 1000
                        WHERE id = ?
                    """, (user_id,))
                    conn.commit()
                    logger.info(f"[HostDatabase] 已创建默认管理员用户: admin，初始密码为bearer字段值")
                else:
                    logger.error("[HostDatabase] 创建默认管理员用户失败")
            else:
                logger.info("[HostDatabase] 已存在管理员用户，跳过默认用户创建")
                
            conn.close()
        except Exception as e:
            logger.error(f"[HostDatabase] 创建默认管理员用户时出错: {e}")

    # ==================== 全局配置操作 ====================

    def get_ap_config(self) -> Dict[str, Any]:
        """获取全局配置（键值对方式）"""
        conn = self.get_db_sqlite()
        try:
            cursor = conn.execute("SELECT id, data FROM hs_global")
            rows = cursor.fetchall()

            # 将键值对转换为字典
            config = {}
            for row in rows:
                config[row["id"]] = row["data"]

            # 如果没有配置记录，插入默认配置
            if not config:
                default_items = [
                    ("bearer", ""),
                    ("saving", "./DataSaving")
                ]
                for key, value in default_items:
                    conn.execute(
                        "INSERT INTO hs_global (id, data) VALUES (?, ?)",
                        (key, value)
                    )
                    config[key] = value
                conn.commit()
                logger.info("[HostDatabase] 已创建默认全局配置")

            return config
        finally:
            conn.close()

    def set_ap_config(self, bearer: str = None, saving: str = None):
        """更新全局配置（键值对方式）"""
        if bearer is None and saving is None:
            return

        conn = self.get_db_sqlite()
        try:
            # 更新指定的配置项
            if bearer is not None:
                conn.execute(
                    "INSERT OR REPLACE INTO hs_global (id, data) VALUES (?, ?)",
                    ("bearer", bearer)
                )
            if saving is not None:
                conn.execute(
                    "INSERT OR REPLACE INTO hs_global (id, data) VALUES (?, ?)",
                    ("saving", saving)
                )
            conn.commit()
        except Exception as e:
            logger.error(f"更新全局配置错误: {e}")
            conn.rollback()
        finally:
            conn.close()

    # ==================== 主机配置操作 ====================

    def set_hs_config(self, hs_name: str, hs_config: HSConfig) -> bool:
        """保存主机配置"""
        conn = self.get_db_sqlite()
        try:
            # 调试日志：打印images_maps
            logger.debug(f"[set_hs_config] hs_name: {hs_name}")
            logger.debug(f"[set_hs_config] hs_config.images_maps: {hs_config.images_maps}")
            logger.debug(f"[set_hs_config] images_maps类型: {type(hs_config.images_maps)}")
            images_maps_json = json.dumps(hs_config.images_maps) if hs_config.images_maps else "{}"
            logger.debug(f"[set_hs_config] images_maps_json: {images_maps_json}")
            
            sql = """
            INSERT OR REPLACE INTO hs_config 
            (hs_name, server_name, server_type, server_addr, server_user, server_pass, server_port,
             filter_name, images_path, dvdrom_path, system_path, backup_path, extern_path,
             launch_path, network_nat, network_pub, i_kuai_addr, i_kuai_user, 
             i_kuai_pass, ports_start, ports_close, remote_port, system_maps, images_maps,
             public_addr, extend_data, limits_nums, ipaddr_maps, ipaddr_ddns, enable_host, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """
            params = (
                hs_name,
                hs_config.server_name,
                hs_config.server_type,
                hs_config.server_addr,
                hs_config.server_user,
                hs_config.server_pass,
                hs_config.server_port,  # 服务访问端口
                hs_config.filter_name,
                hs_config.images_path,
                hs_config.dvdrom_path,  # 光盘镜像存储路径
                hs_config.system_path,
                hs_config.backup_path,
                hs_config.extern_path,
                hs_config.launch_path,
                hs_config.network_nat,
                hs_config.network_pub,
                hs_config.i_kuai_addr,
                hs_config.i_kuai_user,
                hs_config.i_kuai_pass,
                hs_config.ports_start,
                hs_config.ports_close,
                hs_config.remote_port,
                json.dumps(hs_config.system_maps) if hs_config.system_maps else "{}",
                images_maps_json,
                json.dumps(hs_config.public_addr) if hs_config.public_addr else "[]",
                json.dumps(hs_config.extend_data) if hs_config.extend_data else "{}",
                hs_config.limits_nums,
                json.dumps(hs_config.ipaddr_maps) if hs_config.ipaddr_maps else "{}",
                json.dumps(hs_config.ipaddr_ddns) if hs_config.ipaddr_ddns else '["119.29.29.29", "223.5.5.5"]',
                1 if getattr(hs_config, 'enable_host', True) else 0  # 主机启用状态
            )
            conn.execute(sql, params)
            conn.commit()
            logger.debug(f"[set_hs_config] 数据库保存成功")
            return True
        except Exception as e:
            logger.error(f"保存主机配置错误: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_hs_config(self, hs_name: str) -> Optional[Dict[str, Any]]:
        """获取主机配置"""
        conn = self.get_db_sqlite()
        try:
            cursor = conn.execute("SELECT * FROM hs_config WHERE hs_name = ?", (hs_name,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        finally:
            conn.close()

    def all_hs_config(self) -> List[Dict[str, Any]]:
        """获取所有主机配置"""
        conn = self.get_db_sqlite()
        try:
            cursor = conn.execute("SELECT * FROM hs_config")
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def del_hs_config(self, hs_name: str) -> bool:
        """删除主机配置"""
        conn = self.get_db_sqlite()
        try:
            conn.execute("DELETE FROM hs_config WHERE hs_name = ?", (hs_name,))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"删除主机配置错误: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    # ==================== 主机状态操作 ====================

    def add_hs_status(self, hs_name: str, status: Any) -> bool:
        """
        添加单个主机状态（立即保存到数据库）
        :param hs_name: 主机名称
        :param status: 状态对象（HWStatus）
        :return: 是否成功
        """
        try:
            # 获取现有状态
            all_status = self.get_hs_status(hs_name)

            # 转换状态对象为字典
            status_dict = status.__save__() if hasattr(status, '__save__') else status
            all_status.append(status_dict)

            # 限制状态历史记录数量（保留最近100条）
            if len(all_status) > 100:
                all_status = all_status[-100:]

            # 立即保存到数据库
            return self.set_hs_status(hs_name, all_status)
        except Exception as e:
            logger.error(f"[DataManage] 添加主机状态失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def set_hs_status(self, hs_name: str, hs_status_list: List[Any]) -> bool:
        """保存主机状态"""
        conn = self.get_db_sqlite()
        try:
            # 清除旧状态
            conn.execute("DELETE FROM hs_status WHERE hs_name = ?", (hs_name,))

            # 插入新状态
            sql = "INSERT INTO hs_status (hs_name, status_data) VALUES (?, ?)"
            for status in hs_status_list:
                status_data = json.dumps(status.__save__() if hasattr(status, '__save__') else status)
                conn.execute(sql, (hs_name, status_data))

            conn.commit()
            return True
        except Exception as e:
            logger.error(f"保存主机状态错误: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_hs_status(self, hs_name: str) -> List[Any]:
        """获取主机状态"""
        conn = self.get_db_sqlite()
        try:
            cursor = conn.execute("SELECT status_data FROM hs_status WHERE hs_name = ?", (hs_name,))
            results = []
            for row in cursor.fetchall():
                results.append(json.loads(row["status_data"]))
            return results
        finally:
            conn.close()

    # ==================== 虚拟配置操作 ====================

    def set_vm_saving(self, hs_name: str, vm_saving: Dict[str, VMConfig]) -> bool:
        """保存虚拟机存储配置，同时删除已不存在的虚拟机"""
        conn = self.get_db_sqlite()
        try:
            # 获取当前数据库中该主机的所有虚拟机UUID
            cursor = conn.execute("SELECT vm_uuid FROM vm_saving WHERE hs_name = ?", (hs_name,))
            existing_vm_uuids = {row[0] for row in cursor.fetchall()}
            
            # 获取要保存的虚拟机UUID集合
            new_vm_uuids = set(vm_saving.keys())
            
            # 找出需要删除的虚拟机（存在于数据库但不在新配置中）
            vm_uuids_to_delete = existing_vm_uuids - new_vm_uuids
            if vm_uuids_to_delete:
                logger.debug(f"[DataManage] 发现需要删除的虚拟机: {vm_uuids_to_delete}")
                # 删除不存在的虚拟机配置
                for vm_uuid in vm_uuids_to_delete:
                    conn.execute("DELETE FROM vm_saving WHERE hs_name = ? AND vm_uuid = ?", (hs_name, vm_uuid))
                logger.info(f"[DataManage] 已删除 {len(vm_uuids_to_delete)} 个不存在的虚拟机配置: {hs_name}")
            
            # 插入或更新配置，不覆写created_at和updated_at
            sql = """
                INSERT OR REPLACE INTO vm_saving (hs_name, vm_uuid, vm_config, created_at, updated_at)
                VALUES (?, ?, ?, 
                    COALESCE((SELECT created_at FROM vm_saving WHERE hs_name = ? AND vm_uuid = ?), CURRENT_TIMESTAMP),
                    COALESCE((SELECT updated_at FROM vm_saving WHERE hs_name = ? AND vm_uuid = ?), CURRENT_TIMESTAMP)
                )
            """
            for vm_uuid, vm_config in vm_saving.items():
                config_data = json.dumps(vm_config.__save__() if hasattr(vm_config, '__save__') else vm_config)
                conn.execute(sql, (hs_name, vm_uuid, config_data, hs_name, vm_uuid, hs_name, vm_uuid))

            conn.commit()
            return True
        except Exception as e:
            logger.error(f"保存虚拟机存储配置错误: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def update_vm_saving_timestamp(self, hs_name: str, vm_uuid: str) -> bool:
        """更新虚拟机配置的updated_at时间戳（状态上报时调用）"""
        conn = self.get_db_sqlite()
        try:
            sql = "UPDATE vm_saving SET updated_at = CURRENT_TIMESTAMP WHERE hs_name = ? AND vm_uuid = ?"
            cursor = conn.execute(sql, (hs_name, vm_uuid))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"更新虚拟机配置时间戳错误: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_vm_saving(self, hs_name: str) -> Dict[str, Any]:
        """获取虚拟机存储配置"""
        conn = self.get_db_sqlite()
        try:
            cursor = conn.execute("SELECT vm_uuid, vm_config FROM vm_saving WHERE hs_name = ?", (hs_name,))
            result = {}
            for row in cursor.fetchall():
                result[row["vm_uuid"]] = json.loads(row["vm_config"])
            return result
        finally:
            conn.close()

    # ==================== 虚拟状态操作 ====================
    def add_vm_status(self, hs_name: str, vm_uuid: str, status: Any) -> bool:
        """
        添加单个虚拟机状态（立即保存到数据库）- 优化版：直接插入新行
        :param hs_name: 主机名称
        :param vm_uuid: 虚拟机UUID
        :param status: 状态对象（HWStatus）
        :return: 是否成功
        """
        conn = self.get_db_sqlite()
        try:
            # 转换状态对象为字典
            status_dict = status.__save__() if hasattr(status, '__save__') else status
            
            # 提取关键字段用于索引和查询
            ac_status = status_dict.get('ac_status', '') if isinstance(status_dict, dict) else ''
            on_update = status_dict.get('on_update', 0) if isinstance(status_dict, dict) else 0
            flu_usage = status_dict.get('flu_usage', 0) if isinstance(status_dict, dict) else 0
            
            # 累加流量消耗：查询该虚拟机最后一条记录的流量
            cursor = conn.execute(
                "SELECT flu_usage FROM vm_status WHERE hs_name = ? AND vm_uuid = ? ORDER BY id DESC LIMIT 1",
                (hs_name, vm_uuid)
            )
            row = cursor.fetchone()
            if row:
                previous_flu_usage = row[0] or 0
                flu_usage = previous_flu_usage + flu_usage
                logger.debug(f"[DataManage] 流量累加: 之前={previous_flu_usage}MB, 本次={status_dict.get('flu_usage', 0)}MB, 累计={flu_usage}MB")
            else:
                logger.debug(f"[DataManage] 首次上报流量: {flu_usage}MB")
            
            # 更新状态字典中的累计流量
            if isinstance(status_dict, dict):
                status_dict['flu_usage'] = flu_usage
            
            # 序列化状态数据
            status_data = json.dumps(status_dict)
            
            # 直接插入新行
            sql = """
                INSERT INTO vm_status (hs_name, vm_uuid, status_data, ac_status, on_update, flu_usage)
                VALUES (?, ?, ?, ?, ?, ?)
            """
            conn.execute(sql, (hs_name, vm_uuid, status_data, ac_status, on_update, flu_usage))
            
            # 限制状态历史记录数量（保留最近43200条）
            # 使用子查询删除旧记录，性能更好
            conn.execute("""
                DELETE FROM vm_status 
                WHERE hs_name = ? AND vm_uuid = ? AND id NOT IN (
                    SELECT id FROM vm_status 
                    WHERE hs_name = ? AND vm_uuid = ? 
                    ORDER BY id DESC LIMIT 43200
                )
            """, (hs_name, vm_uuid, hs_name, vm_uuid))
            
            conn.commit()
            logger.debug(f"[DataManage] 虚拟机 {vm_uuid} 状态保存成功")
            return True
        except Exception as e:
            logger.error(f"[DataManage] 添加虚拟机状态失败: {e}")
            import traceback
            traceback.print_exc()
            conn.rollback()
            return False
        finally:
            conn.close()

    def set_vm_status(self, hs_name: str, vm_status: Dict[str, List[Any]]) -> bool:
        """保存虚拟机状态 - 优化版：批量插入多行记录"""
        conn = self.get_db_sqlite()
        try:
            logger.debug(f"[DataManage] 开始保存虚拟机状态，主机: {hs_name}, 虚拟机数量: {len(vm_status)}")

            # 清除旧状态
            delete_result = conn.execute("DELETE FROM vm_status WHERE hs_name = ?", (hs_name,))
            logger.debug(f"[DataManage] 已清除旧状态，删除行数: {delete_result.rowcount}")

            # 批量插入新状态
            sql = """
                INSERT INTO vm_status (hs_name, vm_uuid, status_data, ac_status, on_update, flu_usage)
                VALUES (?, ?, ?, ?, ?, ?)
            """
            insert_count = 0
            for vm_uuid, status_list in vm_status.items():
                for status in status_list:
                    # 转换状态对象为字典
                    status_dict = status.__save__() if hasattr(status, '__save__') else status
                    
                    # 提取关键字段
                    ac_status = status_dict.get('ac_status', '') if isinstance(status_dict, dict) else ''
                    on_update = status_dict.get('on_update', 0) if isinstance(status_dict, dict) else 0
                    flu_usage = status_dict.get('flu_usage', 0) if isinstance(status_dict, dict) else 0
                    
                    # 序列化状态数据
                    status_data = json.dumps(status_dict)
                    
                    # 插入单条记录
                    conn.execute(sql, (hs_name, vm_uuid, status_data, ac_status, on_update, flu_usage))
                    insert_count += 1
                
                logger.debug(f"[DataManage] 插入虚拟机 {vm_uuid} 状态，记录数: {len(status_list)}")

            conn.commit()
            logger.debug(f"[DataManage] 虚拟机状态保存成功，共插入 {insert_count} 条记录")
            return True
        except Exception as e:
            logger.error(f"[DataManage] 保存虚拟机状态错误: {e}")
            import traceback
            traceback.print_exc()
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_vm_status(self, hs_name: str, start_timestamp: int = None, end_timestamp: int = None) -> Dict[str, List[Any]]:
        """获取虚拟机状态 - 优化版：从多行记录读取
        
        Args:
            hs_name: 主机名称
            start_timestamp: 开始时间戳（秒），None表示不限制
            end_timestamp: 结束时间戳（秒），None表示不限制
        
        Returns:
            Dict[str, List[Any]]: 虚拟机UUID到状态列表的映射
        """
        conn = self.get_db_sqlite()
        try:
            from datetime import datetime, timedelta
            
            # 构建SQL查询，支持时间范围过滤
            sql = "SELECT vm_uuid, status_data, ac_status, recorded_at FROM vm_status WHERE hs_name = ?"
            params = [hs_name]
            
            # 添加时间范围过滤
            if start_timestamp is not None:
                sql += " AND on_update >= ?"
                params.append(start_timestamp)
            if end_timestamp is not None:
                sql += " AND on_update <= ?"
                params.append(end_timestamp)
            
            # 按ID排序（时间顺序）
            sql += " ORDER BY id ASC"
            
            cursor = conn.execute(sql, params)
            result = {}
            
            # 记录每个虚拟机的最后上报时间
            last_recorded_times = {}
            
            for row in cursor.fetchall():
                vm_uuid = row["vm_uuid"]
                status_dict = json.loads(row["status_data"])
                recorded_at_str = row["recorded_at"]
                
                # 记录最后上报时间
                last_recorded_times[vm_uuid] = recorded_at_str
                
                # 添加到结果列表
                if vm_uuid not in result:
                    result[vm_uuid] = []
                result[vm_uuid].append(status_dict)
            
            # 检查虚拟机是否离线（超过10分钟没有上报）
            current_time = datetime.now()
            for vm_uuid, recorded_at_str in last_recorded_times.items():
                try:
                    # 解析数据库中的UTC时间
                    recorded_at_utc = datetime.strptime(recorded_at_str, "%Y-%m-%d %H:%M:%S")
                    
                    # 转换为本地时间（UTC+8）
                    from datetime import timezone, timedelta as td
                    recorded_at_local = recorded_at_utc + td(hours=8)
                    
                    # 计算时间差
                    time_diff = (current_time - recorded_at_local).total_seconds()
                    
                    # 如果超过10分钟（600秒）没有上报，标记为离线
                    if time_diff > 600:
                        logger.debug(f"[DataManage] 虚拟机 {vm_uuid} 已离线，最后上报时间(UTC): {recorded_at_str}, 本地时间: {recorded_at_local.strftime('%Y-%m-%d %H:%M:%S')}, 距今: {int(time_diff)}秒")
                        # 将所有状态记录的ac_status设置为STOPPED
                        for status in result.get(vm_uuid, []):
                            if isinstance(status, dict):
                                status['ac_status'] = 'STOPPED'
                except Exception as e:
                    logger.warning(f"[DataManage] 解析时间戳失败: {e}, recorded_at={recorded_at_str}")
            
            return result
        finally:
            conn.close()

    def delete_vm_status(self, hs_name: str, vm_uuid: str) -> bool:
        """删除指定虚拟机的状态数据"""
        conn = self.get_db_sqlite()
        try:
            cursor = conn.execute("DELETE FROM vm_status WHERE hs_name = ? AND vm_uuid = ?", (hs_name, vm_uuid))
            conn.commit()
            deleted_count = cursor.rowcount
            logger.debug(f"[DataManage] 删除虚拟机状态数据: 主机={hs_name}, 虚拟机={vm_uuid}, 删除行数={deleted_count}")
            return deleted_count > 0
        except Exception as e:
            logger.error(f"[DataManage] 删除虚拟机状态数据失败: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    # ==================== 虚拟机任务操作 ====================
    def set_vm_tasker(self, hs_name: str, vm_tasker: List[Any]) -> bool:
        """保存虚拟机任务"""
        conn = self.get_db_sqlite()
        try:
            # 清除旧任务
            conn.execute("DELETE FROM vm_tasker WHERE hs_name = ?", (hs_name,))

            # 插入新任务
            sql = "INSERT INTO vm_tasker (hs_name, task_data) VALUES (?, ?)"
            for tasker in vm_tasker:
                task_data = json.dumps(tasker.__save__() if hasattr(tasker, '__save__') else tasker)
                conn.execute(sql, (hs_name, task_data))

            conn.commit()
            return True
        except Exception as e:
            logger.error(f"保存虚拟机任务错误: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_vm_tasker(self, hs_name: str) -> List[Any]:
        """获取虚拟机任务"""
        conn = self.get_db_sqlite()
        try:
            cursor = conn.execute("SELECT task_data FROM vm_tasker WHERE hs_name = ?", (hs_name,))
            results = []
            for row in cursor.fetchall():
                results.append(json.loads(row["task_data"]))
            return results
        finally:
            conn.close()

    # ==================== 全局代理配置操作 ====================
    # def set_web_proxy(self, web_proxies: list) -> bool:
    #     """保存全局代理配置（已废弃，代理配置现在存储在虚拟机配置的web_all字段中）"""
    #     logger.warning("set_web_proxy已废弃，代理配置现在由虚拟机配置统一管理")
    #     return True
    #
    # def get_web_proxy(self) -> list:
    #     """获取全局代理配置（已废弃，代理配置现在存储在虚拟机配置的web_all字段中）"""
    #     logger.warning("get_web_proxy已废弃，代理配置现在从虚拟机配置中获取")
    #     return []
    #
    # def add_web_proxy(self, proxy_data: dict) -> bool:
    #     """添加单个全局代理配置（已废弃，代理配置现在存储在虚拟机配置的web_all字段中）"""
    #     logger.warning("add_web_proxy已废弃，请使用虚拟机配置的web_all字段添加代理")
    #     return True
    #
    # def del_web_proxy(self, web_addr: str) -> bool:
    #     """删除全局代理配置（已废弃，代理配置现在存储在虚拟机配置的web_all字段中）"""
    #     logger.warning("del_web_proxy已废弃，请使用虚拟机配置的web_all字段删除代理")
    #     return True

    # ==================== 日志记录操作 ====================
    def add_hs_logger(self, hs_name: str, logs: ZMessage) -> bool:
        """
        添加单条日志（立即保存到数据库）
        :param hs_name: 主机名称（可为None表示全局日志）
        :param logs: 日志对象（ZMessage）
        :return: 是否成功
        """
        conn = self.get_db_sqlite()
        try:
            log_data = json.dumps(logs.__save__() if hasattr(logs, '__save__') else logs)
            log_level = getattr(logs, 'level', 'INFO') if hasattr(logs, 'level') else 'INFO'

            sql = "INSERT INTO hs_logger (hs_name, log_data, log_level) VALUES (?, ?, ?)"
            conn.execute(sql, (hs_name, log_data, log_level))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"[DataManage] 添加日志失败: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def del_hs_logger(self, hs_name: str, days: int = 7) -> int:
        """
        清理指定天数之前的日志
        :param hs_name: 主机名称（可为None表示全局日志）
        :param days: 保留天数
        :return: 删除的日志条数
        """
        conn = self.get_db_sqlite()
        try:
            sql = """
                  DELETE
                  FROM hs_logger
                  WHERE (hs_name = ? OR (hs_name IS NULL AND ? IS NULL))
                    AND created_at < datetime('now', '-' || ? || ' days') \
                  """
            cursor = conn.execute(sql, (hs_name, hs_name, days))
            deleted_count = cursor.rowcount
            conn.commit()
            return deleted_count
        except Exception as e:
            logger.error(f"[DataManage] 清理日志失败: {e}")
            conn.rollback()
            return 0
        finally:
            conn.close()

    def set_hs_logger(self, hs_name: str, logs: List[ZMessage]) -> bool:
        """保存日志记录"""
        conn = self.get_db_sqlite()
        try:
            # 清除旧日志
            if hs_name:
                conn.execute("DELETE FROM hs_logger WHERE hs_name = ?", (hs_name,))
            else:
                conn.execute("DELETE FROM hs_logger WHERE hs_name IS NULL")

            # 插入新日志
            sql = "INSERT INTO hs_logger (hs_name, log_data, log_level) VALUES (?, ?, ?)"
            for log in logs:
                log_data = json.dumps(log.__save__() if hasattr(log, '__save__') else log)
                log_level = getattr(log, 'level', 'INFO') if hasattr(log, 'level') else 'INFO'
                conn.execute(sql, (hs_name, log_data, log_level))

            conn.commit()
            return True
        except Exception as e:
            logger.error(f"保存日志记录错误: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_hs_logger(self, hs_name: str = None) -> List[Any]:
        """获取日志记录"""
        conn = self.get_db_sqlite()
        try:
            if hs_name:
                cursor = conn.execute(
                    "SELECT log_data, created_at FROM hs_logger WHERE hs_name = ? ORDER BY created_at", (hs_name,))
            else:
                # 获取所有日志，而不仅仅是hs_name为NULL的日志
                cursor = conn.execute("SELECT log_data, created_at FROM hs_logger ORDER BY created_at")

            results = []
            for row in cursor.fetchall():
                log_data = json.loads(row["log_data"])
                log_data['created_at'] = row["created_at"]
                results.append(log_data)
            return results
        finally:
            conn.close()

    def clear_hs_logger(self, hs_name: str = None) -> bool:
        """清空日志记录"""
        conn = self.get_db_sqlite()
        try:
            if hs_name:
                conn.execute("DELETE FROM hs_logger WHERE hs_name = ?", (hs_name,))
            else:
                # 清空所有日志
                conn.execute("DELETE FROM hs_logger")
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"清空日志记录错误: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def add_operation_log(self, hs_name: str = None, operation: str = "", target: str = "", 
                         details: str = "", level: str = "INFO", username: str = None) -> bool:
        """添加操作日志记录
        
        Args:
            hs_name: 主机名称，如果是系统级操作可以为None
            operation: 操作类型，如"创建"、"删除"、"修改"等
            target: 操作目标，如"主机"、"虚拟机"、"用户"等
            details: 操作详情描述
            level: 日志级别，默认INFO
            username: 操作用户名
        """
        conn = self.get_db_sqlite()
        try:
            # 构建日志消息
            log_message = f"{operation}{target}"
            if details:
                log_message += f": {details}"
            
            # 创建日志对象
            log_data = {
                "level": level,
                "message": log_message,
                "operation": operation,
                "target": target,
                "details": details,
                "username": username
            }
            
            # 插入日志
            sql = "INSERT INTO hs_logger (hs_name, log_data, log_level) VALUES (?, ?, ?)"
            conn.execute(sql, (hs_name, json.dumps(log_data), level))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"添加操作日志错误: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    # ==================== 完整数据保存和加载 ====================
    def set_ap_server(self, hs_name: str, host_data: Dict[str, Any]) -> bool:
        """保存主机的完整数据"""
        try:
            success = True

            # 保存主机配置
            if 'hs_config' in host_data:
                hs_config = HSConfig(**host_data['hs_config'])
                success &= self.set_hs_config(hs_name, hs_config)

            # 保存主机状态
            if 'hs_status' in host_data:
                success &= self.set_hs_status(hs_name, host_data['hs_status'])

            # 保存虚拟机存储配置
            if 'vm_saving' in host_data:
                vm_saving = {}
                for uuid, config in host_data['vm_saving'].items():
                    vm_saving[uuid] = VMConfig(**config) if isinstance(config, dict) else config
                success &= self.set_vm_saving(hs_name, vm_saving)

            # 保存虚拟机状态
            if 'vm_status' in host_data:
                success &= self.set_vm_status(hs_name, host_data['vm_status'])

            # 保存虚拟机任务
            if 'vm_tasker' in host_data:
                success &= self.set_vm_tasker(hs_name, host_data['vm_tasker'])

            # 保存日志记录
            if 'save_logs' in host_data:
                save_logs = []
                for log in host_data['save_logs']:
                    save_logs.append(ZMessage(**log) if isinstance(log, dict) else log)
                success &= self.set_hs_logger(hs_name, save_logs)

            return success
        except Exception as e:
            logger.error(f"保存主机完整数据错误: {e}")
            return False

    def get_ap_server(self, hs_name: str) -> Dict[str, Any]:
        """获取主机的完整数据"""
        return {
            "hs_config": self.get_hs_config(hs_name),
            "hs_status": self.get_hs_status(hs_name),
            "vm_saving": self.get_vm_saving(hs_name),
            "vm_status": self.get_vm_status(hs_name),
            "vm_tasker": self.get_vm_tasker(hs_name),
            "save_logs": self.get_hs_logger(hs_name)
        }

    # ==================== 用户管理操作 ====================
    def create_user(self, username: str, password: str, email: str, **kwargs) -> Optional[int]:
        """
        创建新用户
        :param username: 用户名
        :param password: 密码（已加密）
        :param email: 邮箱
        :param kwargs: 其他用户字段（配额、权限等）
        :return: 用户ID，失败返回None
        """
        conn = self.get_db_sqlite()
        try:
# 获取所有可能的用户字段（与web_users表结构完全匹配）
            all_fields = [
                'username', 'password', 'email', 'is_admin', 'is_active', 'email_verified',
                'verify_token', 'reset_token',
                'can_create_vm', 'can_delete_vm', 'can_modify_vm',
                'quota_cpu', 'quota_ram', 'quota_ssd', 'quota_gpu', 'quota_nat_ports',
                'quota_web_proxy', 'quota_nat_ips', 'quota_pub_ips', 'quota_bandwidth_up', 
                'quota_bandwidth_down', 'quota_traffic',
                'used_cpu', 'used_ram', 'used_ssd', 'used_gpu', 'used_nat_ports',
                'used_web_proxy', 'used_nat_ips', 'used_pub_ips', 'used_bandwidth_up', 
                'used_bandwidth_down', 'used_traffic',
                'assigned_hosts'
            ]
            
            # 构建插入SQL
            fields = ['username', 'password', 'email']
            values = [username, password, email]
            placeholders = ['?', '?', '?']
            
# 添加额外的字段
            for field in all_fields[3:]:  # 跳过前三个基本字段
                if field in kwargs:
                    value = kwargs[field]
                    # 处理JSON字段
                    if field in ['assigned_hosts'] and isinstance(value, list):
                        value = json.dumps(value)
                    # 处理布尔字段
                    elif field in ['is_admin', 'is_active', 'email_verified', 'can_create_vm', 'can_modify_vm', 'can_delete_vm']:
                        value = 1 if value else 0
                    fields.append(field)
                    values.append(value)
                    placeholders.append('?')
            
            sql = f"INSERT INTO web_users ({', '.join(fields)}) VALUES ({', '.join(placeholders)})"
            cursor = conn.execute(sql, values)
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError as e:
            logger.error(f"创建用户失败（用户名或邮箱已存在）: {e}")
            return None
        except Exception as e:
            logger.error(f"创建用户错误: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取用户"""
        conn = self.get_db_sqlite()
        try:
            cursor = conn.execute("SELECT * FROM web_users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        finally:
            conn.close()

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """根据用户名获取用户"""
        conn = self.get_db_sqlite()
        try:
            cursor = conn.execute("SELECT * FROM web_users WHERE username = ?", (username,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        finally:
            conn.close()

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """根据邮箱获取用户"""
        conn = self.get_db_sqlite()
        try:
            cursor = conn.execute("SELECT * FROM web_users WHERE email = ?", (email,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        finally:
            conn.close()

    def get_all_users(self) -> List[Dict[str, Any]]:
        """获取所有用户"""
        conn = self.get_db_sqlite()
        try:
            cursor = conn.execute("SELECT * FROM web_users ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def update_user(self, user_id: int, **kwargs) -> bool:
        """
        更新用户信息
        :param user_id: 用户ID
        :param kwargs: 要更新的字段
        :return: 是否成功
        """
        if not kwargs:
            return False

        conn = self.get_db_sqlite()
        try:
            # 构建更新SQL
            fields = []
            values = []
            for key, value in kwargs.items():
                if key in ['assigned_hosts'] and isinstance(value, list):
                    value = json.dumps(value)
                    fields.append(f"{key} = ?")
                    values.append(value)
                elif isinstance(value, str) and value.startswith(('used_nat_ips +', 'used_pub_ips +', 'used_nat_ips -', 'used_pub_ips -')):
                    # 支持表达式更新
                    fields.append(f"{key} = {value}")
                else:
                    fields.append(f"{key} = ?")
                    values.append(value)

            # 添加更新时间
            fields.append("updated_at = CURRENT_TIMESTAMP")
            values.append(user_id)

            sql = f"UPDATE web_users SET {', '.join(fields)} WHERE id = ?"
            conn.execute(sql, values)
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"更新用户错误: {e}")
            traceback.print_exc()
            conn.rollback()
            return False
        finally:
            conn.close()

    def delete_user(self, user_id: int) -> bool:
        """删除用户"""
        conn = self.get_db_sqlite()
        try:
            conn.execute("DELETE FROM web_users WHERE id = ?", (user_id,))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"删除用户错误: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def update_user_last_login(self, user_id: int) -> bool:
        """更新用户最后登录时间"""
        conn = self.get_db_sqlite()
        try:
            conn.execute(
                "UPDATE web_users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
                (user_id,)
            )
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"更新用户登录时间错误: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def verify_user_email(self, user_id: int) -> bool:
        """验证用户邮箱"""
        return self.update_user(user_id, email_verified=1, verify_token='')

    def set_user_verify_token(self, user_id: int, token: str) -> bool:
        """设置用户邮箱验证token"""
        return self.update_user(user_id, verify_token=token)

    def get_user_by_verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """根据验证token获取用户"""
        conn = self.get_db_sqlite()
        try:
            cursor = conn.execute(
                "SELECT * FROM web_users WHERE verify_token = ? AND verify_token != ''",
                (token,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        finally:
            conn.close()

    def get_user_by_email_change_token(self, token: str) -> Optional[Dict[str, Any]]:
        """根据邮箱变更token获取用户（解析token中的邮箱并查找）"""
        conn = self.get_db_sqlite()
        try:
            import base64
            
            # 解析token: base64邮箱:随机值
            if ':' not in token:
                return None
            
            email_base64, random_value = token.split(':', 1)
            
            # 解码base64邮箱
            try:
                # 添加padding
                email_bytes = base64.urlsafe_b64decode(email_base64 + '=' * (-len(email_base64) % 4))
                email = email_bytes.decode()
            except Exception as e:
                logger.warning(f"[DataManager] 解码邮箱base64失败: {e}")
                return None
            
            # 根据邮箱查找用户
            cursor = conn.execute(
                "SELECT * FROM web_users WHERE verify_token != '' AND verify_token LIKE ?",
                ('%"type": "email_change"%',)
            )
            row = cursor.fetchone()
            if row:
                # 验证用户是否有邮箱变更请求
                user_data = dict(row)
                return user_data
            return None
        finally:
            conn.close()

    def update_user_password(self, user_id: int, hashed_password: str) -> bool:
        """更新用户密码"""
        return self.update_user(user_id, password=hashed_password)

    def set_password_reset_token(self, user_id: int, token: str) -> bool:
        """设置密码重置token（使用verify_token字段存储）"""
        return self.update_user(user_id, verify_token=token)

    def get_user_by_reset_token(self, token: str) -> Optional[Dict[str, Any]]:
        """根据重置token获取用户"""
        conn = self.get_db_sqlite()
        try:
            cursor = conn.execute(
                "SELECT * FROM web_users WHERE verify_token = ? AND verify_token != ''",
                (token,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        finally:
            conn.close()

    def delete_password_reset_token(self, token: str) -> bool:
        """删除已使用的密码重置token"""
        conn = self.get_db_sqlite()
        try:
            conn.execute(
                "UPDATE web_users SET verify_token = '' WHERE verify_token = ?",
                (token,)
            )
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"删除重置token错误: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def update_user_resources(self, user_id: int, **resources) -> bool:
        """
        更新用户已使用资源
        :param user_id: 用户ID
        :param resources: 资源字段（used_cpu, used_ram等）
        :return: 是否成功
        """
        return self.update_user(user_id, **resources)

    def update_user_resource_usage(self, user_id: int, **resources) -> bool:
        """
        更新用户资源使用量（别名方法）
        :param user_id: 用户ID
        :param resources: 资源字段（used_cpu, used_ram等）
        :return: 是否成功
        """
        return self.update_user(user_id, **resources)

    def get_system_settings(self) -> Dict[str, Any]:
        """获取系统设置（注册开关、邮件配置等）"""
        conn = self.get_db_sqlite()
        try:
            cursor = conn.execute("SELECT id, data FROM hs_global WHERE id LIKE 'system_%'")
            settings = {}
            for row in cursor.fetchall():
                key = row["id"].replace("system_", "")
                settings[key] = row["data"]
            
            # 设置默认值
            settings.setdefault("registration_enabled", "0")
            settings.setdefault("email_verification_enabled", "0")
            settings.setdefault("resend_email", "")
            settings.setdefault("resend_user", "")
            settings.setdefault("resend_apikey", "")
            
            return settings
        finally:
            conn.close()

    def update_system_settings(self, **settings) -> bool:
        """更新系统设置"""
        conn = self.get_db_sqlite()
        try:
            for key, value in settings.items():
                conn.execute(
                    "INSERT OR REPLACE INTO hs_global (id, data) VALUES (?, ?)",
                    (f"system_{key}", str(value))
                )
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"更新系统设置错误: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
