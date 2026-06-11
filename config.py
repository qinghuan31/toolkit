# -*- coding: utf-8 -*-
"""全局配置模块"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DatabaseConfig:
    """数据库配置（SQLite）"""
    # SQLite 数据库文件路径，空字符串则使用项目根目录下 data/toolkit.db
    database_path: str = ""

    @property
    def resolved_path(self) -> str:
        if self.database_path:
            return self.database_path
        return os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "data", "toolkit.db"
        )


@dataclass
class AppConfig:
    """应用全局配置"""
    app_name: str = "Toolkit"
    app_version: str = "1.0.0"
    organization: str = "WorkBuddy"

    # 默认数据目录
    default_data_dir: str = r"E:\测试数据\Excel"

    # 数据库配置
    db: DatabaseConfig = field(default_factory=DatabaseConfig)

    # 正负极匹配规则 —— 按优先级从高到低匹配
    # 正极关键字：试样名称包含以下任一关键字则判定为正极
    positive_keywords: list = field(default_factory=lambda: [
        "正极", "阳极", "Al", "铝箔", "铝", "cathode", "positive",
    ])
    # 负极关键字：试样名称包含以下任一关键字则判定为负极
    negative_keywords: list = field(default_factory=lambda: [
        "负极", "阴极", "Cu", "铜箔", "铜", "anode", "negative",
    ])

    # 日志配置
    log_dir: str = ""
    log_level: str = "INFO"
    log_max_bytes: int = 10 * 1024 * 1024  # 10MB
    log_backup_count: int = 5

    def __post_init__(self):
        if not self.log_dir:
            self.log_dir = os.path.join(
                os.path.expanduser("~"), ".toolkit", "logs"
            )


# 全局单例
config = AppConfig()
