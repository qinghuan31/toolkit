# -*- coding: utf-8 -*-
"""
插件管理器
负责发现、加载、注册和管理所有工具插件
"""

import os
import importlib
import importlib.util
from typing import Dict, List, Optional
from core.base_plugin import BasePlugin
from core.logger import get_logger

logger = get_logger("plugin_manager")


class PluginManager:
    """插件管理器 —— 核心，负责插件生命周期"""

    _instance: Optional["PluginManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._plugins: Dict[str, BasePlugin] = {}
        self._widgets: Dict[str, object] = {}
        self._active_plugin: Optional[str] = None

    def discover_plugins(self, plugins_dir: str) -> List[str]:
        """
        自动发现插件目录下的所有插件模块

        Args:
            plugins_dir: 插件根目录路径

        Returns:
            发现的插件名称列表
        """
        discovered = []
        if not os.path.isdir(plugins_dir):
            logger.warning(f"插件目录不存在: {plugins_dir}")
            return discovered

        for entry in os.listdir(plugins_dir):
            plugin_path = os.path.join(plugins_dir, entry)
            if not os.path.isdir(plugin_path):
                continue

            # 检查是否有 plugin.py
            plugin_file = os.path.join(plugin_path, "plugin.py")
            if not os.path.isfile(plugin_file):
                continue

            try:
                module_name = f"plugins.{entry}.plugin"
                spec = importlib.util.spec_from_file_location(
                    module_name, plugin_file
                )
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    # 查找 BasePlugin 的子类
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (
                            isinstance(attr, type)
                            and issubclass(attr, BasePlugin)
                            and attr is not BasePlugin
                        ):
                            plugin_instance = attr()
                            self.register_plugin(plugin_instance)
                            discovered.append(plugin_instance.name)
                            logger.info(
                                f"发现插件: {plugin_instance.display_name} "
                                f"({plugin_instance.name} v{plugin_instance.version})"
                            )
            except Exception as e:
                logger.error(f"加载插件 '{entry}' 失败: {e}", exc_info=True)

        return discovered

    def register_plugin(self, plugin: BasePlugin):
        """注册插件"""
        if plugin.name in self._plugins:
            logger.warning(f"插件 '{plugin.name}' 已注册，跳过重复注册")
            return
        self._plugins[plugin.name] = plugin
        logger.debug(f"注册插件: {plugin.name}")

    def unregister_plugin(self, name: str):
        """卸载插件"""
        if name in self._plugins:
            if name == self._active_plugin:
                self._plugins[name].on_deactivated()
            del self._plugins[name]
            if name in self._widgets:
                del self._widgets[name]
            logger.info(f"卸载插件: {name}")

    def get_plugin(self, name: str) -> Optional[BasePlugin]:
        """获取插件实例"""
        return self._plugins.get(name)

    def get_all_plugins(self) -> Dict[str, BasePlugin]:
        """获取所有已注册插件"""
        return dict(self._plugins)

    def get_plugin_widget(self, name: str, parent=None) -> Optional[object]:
        """
        获取插件的界面 Widget（惰性创建，首次获取时创建并缓存）
        """
        if name not in self._plugins:
            return None
        if name not in self._widgets:
            plugin = self._plugins[name]
            self._widgets[name] = plugin.create_widget(parent)
        return self._widgets[name]

    def activate_plugin(self, name: str):
        """激活插件"""
        if name in self._plugins:
            # 先停用当前活跃插件
            if self._active_plugin and self._active_plugin != name:
                self._plugins[self._active_plugin].on_deactivated()
            self._active_plugin = name
            self._plugins[name].on_activated()
            logger.debug(f"激活插件: {name}")

    def deactivate_plugin(self, name: str):
        """停用插件"""
        if name in self._plugins:
            self._plugins[name].on_deactivated()
            if self._active_plugin == name:
                self._active_plugin = None

    @property
    def active_plugin(self) -> Optional[str]:
        """当前活跃插件名称"""
        return self._active_plugin

    @property
    def plugin_count(self) -> int:
        """已注册插件数量"""
        return len(self._plugins)
