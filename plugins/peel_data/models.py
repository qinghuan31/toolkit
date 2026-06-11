# -*- coding: utf-8 -*-
"""
数据模型 —— 定义剥离数据的数据结构和数据库表
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List
from core.database import DatabaseManager
from core.logger import get_logger

logger = get_logger("peel_data.models")


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
    source_file: str = ""            # 来源文件名

    @property
    def test_datetime(self) -> str:
        """返回组合的日期时间字符串，格式：YYYY-MM-DD HH:MM:SS"""
        date_part = self.test_date.strip() if self.test_date else ""
        time_part = self.test_time.strip() if self.test_time else ""
        # 清理日期中多余的时间部分（如 2026-06-10 00:00:00）
        if " " in date_part:
            date_part = date_part.split(" ")[0]
        if date_part and time_part:
            return f"{date_part} {time_part}"
        return date_part or time_part or ""

    def to_dict(self) -> dict:
        """转换为完整字典（包含所有字段，None 值保留用于统一列）"""
        return asdict(self)

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


def ensure_history_table():
    """确保提取历史记录表存在"""
    db = DatabaseManager()
    table_name = "extraction_history"

    if not db.table_exists(table_name):
        ddl = """
        CREATE TABLE IF NOT EXISTS "extraction_history" (
            "id"          INTEGER PRIMARY KEY AUTOINCREMENT,
            "file_path"   TEXT    NOT NULL,
            "file_name"   TEXT    NOT NULL,
            "success"     INTEGER NOT NULL DEFAULT 0,
            "reason"      TEXT    DEFAULT '',
            "request_id"  TEXT    DEFAULT '',
            "created_at"  TEXT    DEFAULT (datetime('now','localtime'))
        )
        """
        db.create_table(table_name, ddl)
        logger.info(f"历史记录表已创建: {table_name}")

