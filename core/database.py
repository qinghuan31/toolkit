# -*- coding: utf-8 -*-
"""
数据库管理模块
使用 SQLite（零安装，单文件数据库）
数据库文件保存在项目根目录 data/ 下
"""

import sqlite3
import os
import datetime as _dt
from contextlib import contextmanager
from typing import Optional, List, Dict, Any
from config import config
from core.logger import get_logger

logger = get_logger("database")


class DatabaseManager:
    """数据库管理器（单例），基于 SQLite"""

    _instance: Optional["DatabaseManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._db_path = config.db.resolved_path
        self._ensure_database()

    def _ensure_database(self):
        """确保数据库文件和目录存在"""
        try:
            db_dir = os.path.dirname(self._db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
            # 测试连接
            conn = sqlite3.connect(self._db_path, timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")       # WAL 模式，读写并发更优
            conn.execute("PRAGMA foreign_keys=ON")
            conn.close()
            self._db_available = True
            logger.info(f"SQLite 数据库就绪: {self._db_path}")
        except Exception as e:
            self._db_available = False
            logger.error(f"数据库初始化失败: {e}")

    @property
    def is_available(self) -> bool:
        """当前数据库是否可用"""
        return self._db_available is True

    @contextmanager
    def get_connection(self):
        """获取数据库连接（上下文管理器）"""
        if not self._db_available:
            raise RuntimeError("数据库不可用")
        conn = sqlite3.connect(self._db_path, timeout=10)
        conn.row_factory = sqlite3.Row   # 返回字典式行
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
        finally:
            conn.close()

    def execute(self, sql: str, params: tuple = None) -> int:
        """执行单条 SQL，返回受影响行数"""
        if not self._db_available:
            return 0
        with self.get_connection() as conn:
            cursor = conn.execute(sql, params or ())
            conn.commit()
            return cursor.rowcount

    def execute_many(self, sql: str, params_list: List[tuple]) -> int:
        """批量执行 SQL，返回受影响行数"""
        if not self._db_available:
            return 0
        with self.get_connection() as conn:
            cursor = conn.executemany(sql, params_list)
            conn.commit()
            return cursor.rowcount

    def query_one(self, sql: str, params: tuple = None) -> Optional[Dict[str, Any]]:
        """查询单条记录，返回字典或 None"""
        if config.db.network_mode == "client":
            rows = self.query_all(sql, params)
            return rows[0] if rows else None
        if not self._db_available:
            return None
        with self.get_connection() as conn:
            cursor = conn.execute(sql, params or ())
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def query_all(self, sql: str, params: tuple = None) -> List[Dict[str, Any]]:
        """查询所有记录，返回字典列表"""
        if config.db.network_mode == "client":
            from core.db_client import DatabaseClient
            return DatabaseClient().query_sql(sql, list(params or ()))
        if not self._db_available:
            return []
        with self.get_connection() as conn:
            cursor = conn.execute(sql, params or ())
            return [dict(row) for row in cursor.fetchall()]

    def insert_ignore(self, table: str, data: Dict[str, Any]) -> bool:
        """
        插入数据，遇到唯一约束冲突则跳过（INSERT OR IGNORE）
        返回 True 表示插入成功，False 表示跳过

        自动将 datetime.date / datetime.time 转换为 isoformat 字符串。
        """
        if not self._db_available:
            return False
        columns = ", ".join(f'"{k}"' for k in data.keys())
        placeholders = ", ".join(["?"] * len(data))
        sql = f'INSERT OR IGNORE INTO "{table}" ({columns}) VALUES ({placeholders})'
        values = tuple(
            v.isoformat() if isinstance(v, (_dt.date, _dt.time)) else v
            for v in data.values()
        )
        affected = self.execute(sql, values)
        return affected > 0

    def insert_many_ignore(
        self, table: str, data_list: List[Dict[str, Any]]
    ) -> tuple:
        """
        批量插入，遇到唯一约束冲突跳过
        返回 (成功数, 跳过数)

        自动将 datetime.date / datetime.time 转换为 isoformat 字符串。
        """
        if not data_list:
            return 0, 0
        if not self._db_available:
            return 0, len(data_list)

        columns = list(data_list[0].keys())
        col_str = ", ".join(f'"{c}"' for c in columns)
        placeholders = ", ".join(["?"] * len(columns))
        sql = f'INSERT OR IGNORE INTO "{table}" ({col_str}) VALUES ({placeholders})'

        def _adapt(val):
            """将 datetime 类型转换为 SQLite 兼容的 isoformat 字符串"""
            if isinstance(val, (_dt.date, _dt.time)):
                return val.isoformat()
            return val

        params_list = [tuple(_adapt(d[c]) for c in columns) for d in data_list]
        with self.get_connection() as conn:
            cursor = conn.executemany(sql, params_list)
            conn.commit()
            affected = cursor.rowcount
            skipped = len(data_list) - affected
            return affected, skipped

    def table_exists(self, table_name: str) -> bool:
        """检查表是否存在"""
        if not self._db_available:
            return False
        result = self.query_one(
            "SELECT COUNT(*) as cnt FROM sqlite_master "
            "WHERE type='table' AND name=?",
            (table_name,),
        )
        return result is not None and result["cnt"] > 0

    def get_table_columns(self, table_name: str) -> List[str]:
        """获取表的列名列表"""
        if not self._db_available:
            return []
        rows = self.query_all(f"PRAGMA table_info(\"{table_name}\")")
        return [row["name"] for row in rows]

    def create_table(self, table_name: str, ddl: str):
        """建表"""
        if not self._db_available:
            return
        self.execute(ddl)
        logger.info(f"表 '{table_name}' 创建/确认就绪")

    # === v1.6.0 网络多设备 CRUD(局域网 server/client 模式) ===

    def update(self, table: str, data: Dict[str, Any], where: str, where_params: tuple) -> int:
        """更新记录。例: update('peel_data', {'sample_name': 'X'}, 'id=?', (1,))"""
        if not self._db_available:
            return 0
        set_clause = ", ".join(f'"{k}"=?' for k in data.keys())
        sql = f'UPDATE "{table}" SET {set_clause} WHERE {where}'
        params = tuple(data.values()) + where_params
        return self.execute(sql, params)

    def delete(self, table: str, where: str, where_params: tuple) -> int:
        """删除记录。例: delete('peel_data', 'id=?', (1,))"""
        if not self._db_available:
            return 0
        sql = f'DELETE FROM "{table}" WHERE {where}'
        return self.execute(sql, where_params)

    def insert(self, table: str, data: Dict[str, Any]) -> int:
        """插入记录,返回新行 rowid"""
        if not self._db_available:
            return 0
        columns = ", ".join(f'"{k}"' for k in data.keys())
        placeholders = ", ".join(["?"] * len(data))
        sql = f'INSERT INTO "{table}" ({columns}) VALUES ({placeholders})'
        values = tuple(
            v.isoformat() if isinstance(v, (_dt.date, _dt.time)) else v
            for v in data.values()
        )
        with self.get_connection() as conn:
            cursor = conn.execute(sql, values)
            conn.commit()
            return cursor.lastrowid

    def count(self, table: str, where: str = "1=1", where_params: tuple = ()) -> int:
        """统计行数"""
        if not self._db_available:
            return 0
        result = self.query_one(f'SELECT COUNT(*) AS cnt FROM "{table}" WHERE {where}', where_params)
        return result["cnt"] if result else 0

    @property
    def db_path(self) -> str:
        """供 server/client 模式使用的数据库路径"""
        return self._db_path
