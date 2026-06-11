# -*- coding: utf-8 -*-
"""
基础插件接口
所有工具插件必须继承 BasePlugin 并实现其抽象方法
"""

from abc import ABC, abstractmethod
from typing import Optional
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QIcon


class BasePlugin(ABC):
    """
    插件基类 —— 所有工具模块的接口规范

    子类需实现：
    - name: 插件唯一标识
    - display_name: 界面显示名称
    - description: 插件描述
    - icon: 图标（可选）
    - create_widget(): 创建插件界面
    - on_activated(): 插件激活回调
    - on_deactivated(): 插件停用回调
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """插件唯一标识（英文，用于内部引用）"""
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        """界面显示名称（中文）"""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """插件功能描述"""
        ...

    @property
    def icon(self) -> Optional[QIcon]:
        """插件图标（可选）"""
        return None

    @property
    def version(self) -> str:
        """插件版本"""
        return "1.0.0"

    @abstractmethod
    def create_widget(self, parent: Optional[QWidget] = None) -> QWidget:
        """
        创建插件的主界面 Widget

        Args:
            parent: 父 Widget

        Returns:
            插件的主界面 QWidget
        """
        ...

    def on_activated(self):
        """插件被激活时调用（可选重写）"""
        pass

    def on_deactivated(self):
        """插件被停用时调用（可选重写）"""
        pass

    def __repr__(self):
        return f"<Plugin:{self.name} v{self.version}>"
