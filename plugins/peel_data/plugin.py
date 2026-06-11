# -*- coding: utf-8 -*-
"""
剥离数据汇总插件注册入口
"""

from typing import Optional
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QIcon
from core.base_plugin import BasePlugin
from plugins.peel_data.ui.main_widget import PeelDataWidget


class PeelDataPlugin(BasePlugin):
    """剥离数据汇总插件"""

    @property
    def name(self) -> str:
        return "peel_data"

    @property
    def display_name(self) -> str:
        return "剥离数据汇总"

    @property
    def description(self) -> str:
        return (
            "从 PDF 和 Excel 文件中提取剥离强度数据，"
            "自动识别正负极，汇总存储至数据库并支持导出"
        )

    @property
    def version(self) -> str:
        return "1.3.0"

    def create_widget(self, parent: Optional[QWidget] = None) -> QWidget:
        return PeelDataWidget(parent)

    def on_activated(self):
        from core.logger import get_logger
        get_logger("plugin_manager").info("剥离数据汇总插件已激活")

    def on_deactivated(self):
        from core.logger import get_logger
        get_logger("plugin_manager").info("剥离数据汇总插件已停用")
