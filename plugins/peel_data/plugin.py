# -*- coding: utf-8 -*-
"""
剥离数据汇总插件注册入口
"""

from typing import Optional
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QIcon
from core.base_plugin import BasePlugin
from plugins.peel_data.ui.main_widget import PeelDataWidget
from plugins.peel_data.models import ensure_table, ensure_history_table
from core.logger import get_logger


logger = get_logger("peel_data.plugin")


class PeelDataPlugin(BasePlugin):
    """剥离数据汇总插件"""

    @property
    def name(self) -> str:
        return "peel_data"

    @property
    def display_name(self) -> str:
        return "数据提取"

    @property
    def description(self) -> str:
        return (
            "选择 PDF 或 Excel 文件夹，一键提取剥离强度数据，"
            "自动识别正负极并保存为可导出的数据库记录"
        )

    @property
    def version(self) -> str:
        # 【v1.5.1】版本号从 config 读取,实现单一来源
        from config import get_version
        return get_version()

    def create_widget(self, parent: Optional[QWidget] = None) -> QWidget:
        # 确保数据库表结构最新（含迁移新列）
        try:
            ensure_table()
            ensure_history_table()
        except Exception as e:
            logger.warning(f"确保数据库表结构时出错（可忽略）: {e}")
        return PeelDataWidget(parent)

    def on_activated(self):
        from core.logger import get_logger
        get_logger("plugin_manager").info("剥离数据汇总插件已激活")

    def on_deactivated(self):
        from core.logger import get_logger
        get_logger("plugin_manager").info("剥离数据汇总插件已停用")
