# -*- coding: utf-8 -*-
"""分容数据统计分析插件 — 数据模型与表 DDL

【v1.8.0 引入】
- 容量数据主表：capacity_analysis_distribution（保存每批次的统计汇总）
- 提取历史表：capacity_analysis_extraction_history（带 plugin 字段，纳入全局历史聚合）

【工艺标准 — 由 Z 在 2026-06-17 需求澄清中确认】
普通分容流程：充电 → 放电 → 充电
- 第一步：充至满电态
- 第二步：执行 1 次完整放电
- 第三步：执行 1 次充电（可能达满电态也可能不达）

容量取数策略：取最后一次"恒流放电"工步的"单步容量(mAh)"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Dict

from core.database import DatabaseManager
from core.logger import get_logger

logger = get_logger("capacity_analysis.models")


# 工步关键字字典（v1.8.0 锁定）
DISCHARGE_KEYWORDS = ("恒流放电",)
CHARGE_KEYWORDS = ("恒流充电", "恒流恒压充电")


@dataclass
class CapacityRecord:
    """单条电池分容记录（清洗后）"""
    cell_id: str = ""             # 电池标识（如工装位 + 通道）
    capacity_mah: float = 0.0     # 分容容量（mAh）
    cycle_count: int = 0          # 分容次数（恒流放电工步数）
    file_name: str = ""           # 来源文件
    source_row: int = 0           # 源数据行号（用于追溯）


@dataclass
class CapacityStats:
    """单批次统计汇总（对应 JMP "分布" 模块）"""
    count: int = 0
    mean: float = 0.0
    std_dev: float = 0.0
    min_v: float = 0.0
    max_v: float = 0.0
    q1: float = 0.0
    median: float = 0.0
    q3: float = 0.0
    p2_5: float = 0.0
    p97_5: float = 0.0
    ci95_lower: float = 0.0
    ci95_upper: float = 0.0
    std_err: float = 0.0          # 均值标准误差


@dataclass
class AnalysisResult:
    """单文件分析结果（含异常样本分类）"""
    batch_id: str = ""
    source_file: str = ""
    stats: CapacityStats = field(default_factory=CapacityStats)
    records: List[CapacityRecord] = field(default_factory=list)
    abnormal: Dict[str, List[Dict]] = field(default_factory=dict)
    # abnormal 分类键：no_discharge / no_charge / order_error / cycle_test / null_value

    def summary(self) -> str:
        return (
            f"批次 {self.batch_id}：有效 {self.stats.count} 块，"
            f"均值 {self.stats.mean:.2f} mAh，"
            f"剔除异常 {sum(len(v) for v in self.abnormal.values())} 块"
        )


def get_distribution_table_name() -> str:
    return "capacity_analysis_distribution"


def get_history_table_name() -> str:
    return "capacity_analysis_extraction_history"


def ensure_distribution_table() -> str:
    """确保批次统计主表存在"""
    db = DatabaseManager()
    table_name = get_distribution_table_name()
    if not db.table_exists(table_name):
        ddl = f"""
        CREATE TABLE IF NOT EXISTS "{table_name}" (
            "id"            INTEGER PRIMARY KEY AUTOINCREMENT,
            "batch_id"      TEXT    NOT NULL,
            "source_file"   TEXT    DEFAULT '',
            "sample_count"  INTEGER DEFAULT 0,
            "mean"          REAL    DEFAULT 0,
            "std_dev"       REAL    DEFAULT 0,
            "min_v"         REAL    DEFAULT 0,
            "max_v"         REAL    DEFAULT 0,
            "q1"            REAL    DEFAULT 0,
            "median"        REAL    DEFAULT 0,
            "q3"            REAL    DEFAULT 0,
            "p2_5"          REAL    DEFAULT 0,
            "p97_5"         REAL    DEFAULT 0,
            "ci95_lower"    REAL    DEFAULT 0,
            "ci95_upper"    REAL    DEFAULT 0,
            "std_err"       REAL    DEFAULT 0,
            "created_at"    TEXT    DEFAULT (datetime('now','localtime'))
        )
        """
        db.create_table(table_name, ddl)
        logger.info(f"分容统计表已创建: {table_name}")
    return table_name


def ensure_history_table() -> str:
    """确保提取历史表存在；带 plugin 字段，纳入全局历史"""
    db = DatabaseManager()
    table_name = get_history_table_name()
    if not db.table_exists(table_name):
        ddl = f"""
        CREATE TABLE IF NOT EXISTS "{table_name}" (
            "id"             INTEGER PRIMARY KEY AUTOINCREMENT,
            "file_path"      TEXT    NOT NULL,
            "file_name"      TEXT    NOT NULL,
            "success"        INTEGER NOT NULL DEFAULT 0,
            "reason"         TEXT    DEFAULT '',
            "request_id"     TEXT    DEFAULT '',
            "plugin"         TEXT    DEFAULT 'capacity_analysis',
            "operation_time" TEXT    DEFAULT '',
            "created_at"     TEXT    DEFAULT (datetime('now','localtime'))
        )
        """
        db.create_table(table_name, ddl)
        db.execute(f'CREATE INDEX IF NOT EXISTS "idx_{table_name}_request_id" ON "{table_name}" ("request_id")')
        db.execute(f'CREATE INDEX IF NOT EXISTS "idx_{table_name}_operation_time" ON "{table_name}" ("operation_time")')
        db.execute(f'CREATE INDEX IF NOT EXISTS "idx_{table_name}_plugin" ON "{table_name}" ("plugin")')
        logger.info(f"分容历史表已创建: {table_name}")
    return table_name
