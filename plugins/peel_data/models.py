# -*- coding: utf-8 -*-
"""
数据模型 —— 定义剥离数据的数据结构和数据库表
"""

import re as _re
import datetime as _dt
from dataclasses import dataclass, field, asdict
from typing import Optional, List
from core.database import DatabaseManager
from core.logger import get_logger

logger = get_logger("peel_data.models")


def _normalize_date(val) -> str:
    """将 test_date 统一为 YYYY-MM-DD 格式"""
    if val is None:
        return ""
    if isinstance(val, _dt.date):
        return val.isoformat()
    s = str(val).strip()
    if not s:
        return ""
    # 移除多余时间部分（如 "2026-06-10 00:00:00"）
    if " " in s:
        s = s.split(" ")[0]
    # 尝试解析并重新格式化为标准格式
    m = _re.match(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})", s)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return s


def _normalize_time(val) -> str:
    """将 test_time 统一为 HH:MM:SS 格式"""
    if val is None:
        return ""
    if isinstance(val, _dt.time):
        return val.isoformat()
    s = str(val).strip()
    if not s:
        return ""
    # 匹配 HH:MM[:SS] 格式，补全秒
    m = _re.match(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", s)
    if m:
        h = int(m.group(1))
        mi = int(m.group(2))
        sec = int(m.group(3)) if m.group(3) else 0
        return f"{h:02d}:{mi:02d}:{sec:02d}"
    return s


@dataclass
class PeelDataRecord:
    """
    剥离数据记录

    唯一性约束：试验时间 + 试验日期 + 试样名称
    新增字段：sample_brand（试样牌号）—— 与试样名称独立
    """
    sample_name: str = ""           # 试样名称
    sample_brand: str = ""          # 试样牌号（独立字段，如 BG-01、T-NCM-01）
    polarity: str = ""              # 极性：正极 / 负极
    test_time: str = ""             # 试验时间
    test_date: str = ""             # 试验日期

    # 平均剥离强度 —— 动态列（曲线1~9 / S1~S9）
    curve_1: Optional[float] = None
    curve_2: Optional[float] = None
    curve_3: Optional[float] = None
    curve_4: Optional[float] = None
    curve_5: Optional[float] = None
    curve_6: Optional[float] = None
    curve_7: Optional[float] = None
    curve_8: Optional[float] = None
    curve_9: Optional[float] = None

    std_dev: Optional[float] = None  # 标准差
    curve_unit: str = ""          # 剥离强度单位（如 kN/m、N/mm）
    file_type: str = ""            # 文件类型：xlsx / xls / csv / pdf
    source_file: str = ""            # 来源文件名

    @property
    def test_datetime(self) -> str:
        """返回组合的日期时间字符串，格式：YYYY-MM-DD HH:MM:SS

        兼容 Python 标准库 datetime 类型：
        - test_date 可能是 datetime.date 对象（来自 Excel/PDF 解析器）
        - test_time 可能是 datetime.time 对象（来自 Excel/PDF 解析器）
        """
        date_part = _normalize_date(self.test_date)
        time_part = _normalize_time(self.test_time)
        if date_part and time_part:
            return f"{date_part} {time_part}"
        return date_part or time_part or ""

    def to_dict(self) -> dict:
        """转换为完整字典（所有字段，None 值保留用于统一列）

        自动规范化 test_date → YYYY-MM-DD, test_time → HH:MM:SS，
        确保 SQLite 唯一约束 (test_date, test_time, sample_name) 不会因
        精度不一致（如 "14:30" vs "14:30:00"）而产生重复记录。
        """
        result = asdict(self)
        result["test_date"] = _normalize_date(result.get("test_date"))
        result["test_time"] = _normalize_time(result.get("test_time"))
        return result

    @staticmethod
    def get_table_name() -> str:
        return "peel_data_summary"

    @staticmethod
    def get_create_table_ddl() -> str:
        return """
        CREATE TABLE IF NOT EXISTS "peel_data_summary" (
            "id"          INTEGER PRIMARY KEY AUTOINCREMENT,
            "sample_name" TEXT    NOT NULL,
            "sample_brand" TEXT    NOT NULL DEFAULT '',
            "polarity"    TEXT    NOT NULL DEFAULT '',
            "test_time"   TEXT    NOT NULL DEFAULT '',
            "test_date"   TEXT    NOT NULL DEFAULT '',
            "curve_1"     REAL    DEFAULT NULL,
            "curve_2"     REAL    DEFAULT NULL,
            "curve_3"     REAL    DEFAULT NULL,
            "curve_4"     REAL    DEFAULT NULL,
            "curve_5"     REAL    DEFAULT NULL,
            "curve_6"     REAL    DEFAULT NULL,
            "curve_7"     REAL    DEFAULT NULL,
            "curve_8"     REAL    DEFAULT NULL,
            "curve_9"     REAL    DEFAULT NULL,
            "std_dev"     REAL    DEFAULT NULL,
            "curve_unit" TEXT    DEFAULT '',
            "source_file" TEXT    DEFAULT '',
            "file_type"   TEXT    DEFAULT '',
            "created_at"  TEXT    DEFAULT (datetime('now','localtime')),
            UNIQUE ("test_time", "test_date", "sample_name")
        )
        """


def ensure_table():
    """确保数据表存在；若缺少 sample_brand 列则自动 ALTER TABLE 添加"""
    db = DatabaseManager()
    table_name = PeelDataRecord.get_table_name()

    if not db.table_exists(table_name):
        db.create_table(table_name, PeelDataRecord.get_create_table_ddl())
        logger.info(f"数据表已创建: {table_name}")
    else:
        # 检查并添加新列（向后兼容）
        existing_cols = db.get_table_columns(table_name)
        if "sample_brand" not in existing_cols:
            db.execute(f'ALTER TABLE "{table_name}" ADD COLUMN "sample_brand" TEXT NOT NULL DEFAULT \'\'')
            logger.info(f"已添加新列 sample_brand 到表 {table_name}")
        if "curve_unit" not in existing_cols:
            db.execute(f'ALTER TABLE "{table_name}" ADD COLUMN "curve_unit" TEXT DEFAULT \'\'')
            logger.info(f"已添加新列 curve_unit 到表 {table_name}")
        if "file_type" not in existing_cols:
            db.execute(f'ALTER TABLE "{table_name}" ADD COLUMN "file_type" TEXT DEFAULT \'\'')
            logger.info(f"已添加新列 file_type 到表 {table_name}")


def ensure_history_table():
    """确保提取历史记录表存在；若缺少 operation_time 列则自动添加"""
    db = DatabaseManager()
    table_name = "extraction_history"

    if not db.table_exists(table_name):
        ddl = """
        CREATE TABLE IF NOT EXISTS "extraction_history" (
            "id"             INTEGER PRIMARY KEY AUTOINCREMENT,
            "file_path"      TEXT    NOT NULL,
            "file_name"      TEXT    NOT NULL,
            "success"        INTEGER NOT NULL DEFAULT 0,
            "reason"         TEXT    DEFAULT '',
            "request_id"     TEXT    DEFAULT '',
            "operation_time" TEXT    DEFAULT '',
            "created_at"     TEXT    DEFAULT (datetime('now','localtime'))
        )
        """
        db.create_table(table_name, ddl)
        logger.info(f"历史记录表已创建: {table_name}")
    else:
        # 向后兼容：检查并添加 operation_time 列
        existing_cols = db.get_table_columns(table_name)
        if "operation_time" not in existing_cols:
            db.execute(
                f'ALTER TABLE "{table_name}" ADD COLUMN "operation_time" TEXT DEFAULT \'\''
            )
            logger.info(f"已添加新列 operation_time 到表 {table_name}")


class PeelDataQuery:
    """
    剥离数据查询类 —— 提供静态方法用于数据库查询/搜索/删除
    """

    @staticmethod
    def search(keyword: str) -> list:
        """
        按关键字模糊搜索（试样名称、来源文件）

        Args:
            keyword: 搜索关键字

        Returns:
            list: 匹配的记录列表，每项为 dict
        """
        db = DatabaseManager()
        table_name = PeelDataRecord.get_table_name()
        rows = db.query_all(
            f'SELECT * FROM "{table_name}" '
            'WHERE "sample_name" LIKE ? OR "source_file" LIKE ? '
            'ORDER BY "test_date", "test_time"',
            (f"%{keyword}%", f"%{keyword}%")
        )
        return [dict(r) for r in rows] if rows else []

    @staticmethod
    def get_stats() -> dict:
        """
        获取数据库统计信息

        Returns:
            dict: {total_records, test_days, positive_count, negative_count}
        """
        db = DatabaseManager()
        table_name = PeelDataRecord.get_table_name()
        row = db.query_one(
            f'SELECT '
            f'COUNT(*)                AS total, '
            f'COUNT(DISTINCT "test_date") AS days, '
            f'SUM(CASE WHEN "polarity"=\'正极\' THEN 1 ELSE 0 END) AS pos, '
            f'SUM(CASE WHEN "polarity"=\'负极\' THEN 1 ELSE 0 END) AS neg '
            f'FROM "{table_name}"'
        )
        if row:
            return {
                "total_records": row[0] or 0,
                "test_days": row[1] or 0,
                "positive_count": row[2] or 0,
                "negative_count": row[3] or 0,
            }
        return {
            "total_records": 0,
            "test_days": 0,
            "positive_count": 0,
            "negative_count": 0,
        }

    @staticmethod
    def delete_by_ids(ids: list) -> int:
        """
        按 ID 列表批量删除记录

        Args:
            ids: ID 列表

        Returns:
            int: 删除的记录数
        """
        if not ids:
            return 0
        db = DatabaseManager()
        table_name = PeelDataRecord.get_table_name()
        placeholders = ','.join('?' * len(ids))
        cur = db.execute(
            f'DELETE FROM "{table_name}" WHERE "id" IN ({placeholders})',
            ids
        )
        deleted = cur.rowcount if cur else 0
        logger.info(f"删除 {deleted} 条记录")
        return deleted

    @staticmethod
    def query_all(order_by: str = "test_date, test_time") -> list:
        """
        查询全部记录

        Args:
            order_by: 排序子句（不含 ORDER BY 关键字）

        Returns:
            list: 全部记录列表，每项为 dict
        """
        db = DatabaseManager()
        table_name = PeelDataRecord.get_table_name()
        # 安全检查：白名单校验 order_by 防止 SQL 注入
        allowed_cols = {
            "test_date", "test_time", "sample_name", "polarity",
            "created_at", "id"
        }
        safe_order = []
        for part in order_by.split(","):
            col = part.strip().split()[0].strip('"')
            if col in allowed_cols:
                safe_order.append(part.strip())
        if not safe_order:
            safe_order = ["test_date", "test_time"]
        order_clause = ", ".join(safe_order)
        rows = db.query_all(
            f'SELECT * FROM "{table_name}" ORDER BY {order_clause}'
        )
        return [dict(r) for r in rows] if rows else []

