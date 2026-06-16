# -*- coding: utf-8 -*-
"""分容数据统计分析插件注册入口"""

from typing import Optional
from PySide6.QtWidgets import QWidget

from core.base_plugin import BasePlugin
from core.logger import get_logger
from plugins.capacity_analysis.models import ensure_distribution_table, ensure_history_table
from plugins.capacity_analysis.ui.main_widget import CapacityAnalysisWidget

logger = get_logger("capacity_analysis.plugin")


class CapacityAnalysisPlugin(BasePlugin):
    """分容数据统计分析插件（v1.8.0 引入）"""

    @property
    def name(self) -> str:
        return "capacity_analysis"

    @property
    def display_name(self) -> str:
        return "分容分析"

    @property
    def description(self) -> str:
        return (
            "导入精捷能分容柜导出的 Excel/CSV 数据，自动识别工艺工步，"
            "清洗分容容量（充电→放电→充电工艺），一键生成 JMP 风格的"
            "直方图+箱体图+统计指标报告 PNG"
        )

    @property
    def version(self) -> str:
        from config import get_version
        return get_version()

    def create_widget(self, parent: Optional[QWidget] = None) -> QWidget:
        try:
            ensure_distribution_table()
            ensure_history_table()
        except Exception as e:
            logger.warning(f"确保数据库表结构时出错（可忽略）: {e}")
        return CapacityAnalysisWidget(parent)

    def on_activated(self):
        logger.info("分容分析插件已激活")

    def on_deactivated(self):
        logger.info("分容分析插件已停用")
