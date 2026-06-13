# -*- coding: utf-8 -*-
"""
主窗口 —— 提供侧边栏导航和内容区域
"""

import os
import sys

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QStackedWidget, QStatusBar,
    QFrame, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QFont

from core.plugin_manager import PluginManager
from ui.styles import LIGHT_STYLE
from core.logger import get_logger

logger = get_logger("main_window")


class SidebarButton(QPushButton):
    """侧边栏导航按钮"""

    def __init__(self, plugin_name: str, display_name: str, parent=None):
        super().__init__(display_name, parent)
        self.plugin_name = plugin_name
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(44)
        self.setObjectName("sidebar_btn")


class MainWindow(QMainWindow):
    """主窗口"""

    # 特殊页面标识（非插件）
    PAGE_VERSION = "__version__"
    PAGE_SETTINGS = "__settings__"

    def __init__(self):
        super().__init__()
        self._plugin_manager = PluginManager()
        self._nav_buttons: dict = {}
        self._setup_ui()
        self._load_plugins()
        self._add_builtin_pages()
        self._apply_style()

        # 窗口图标（继承自 QApplication，显式设置确保子窗口一致）
        ico = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "app_icon.ico")
        if os.path.exists(ico):
            self.setWindowIcon(QIcon(ico))

    def _setup_ui(self):
        """初始化 UI 布局"""
        # 【v1.5.1】版本号从 config 单一来源读取
        from config import get_version
        self.setWindowTitle(f"Toolkit v{get_version()}")
        self.setMinimumSize(1100, 700)
        self.resize(1280, 800)

        # 中央容器
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # === 侧边栏 ===
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        # 标题
        title_label = QLabel("🛠 Toolkit")
        title_label.setObjectName("sidebar_title")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(title_label)

        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background-color: #1a252f; max-height: 1px;")
        sidebar_layout.addWidget(separator)

        # 导航按钮容器
        self._nav_container = QVBoxLayout()
        self._nav_container.setSpacing(0)
        sidebar_layout.addLayout(self._nav_container)

        # 内建页面分隔线
        builtin_sep = QFrame()
        builtin_sep.setFrameShape(QFrame.Shape.HLine)
        builtin_sep.setStyleSheet("background-color: #1a252f; max-height: 1px; margin: 4px 12px;")
        sidebar_layout.addWidget(builtin_sep)

        # 内建页面导航按钮容器
        self._builtin_nav_container = QVBoxLayout()
        self._builtin_nav_container.setSpacing(0)
        sidebar_layout.addLayout(self._builtin_nav_container)

        # 弹簧
        sidebar_layout.addStretch()

        # 底部版本信息
        # 【v1.5.1】版本号从 config 单一来源读取
        from config import get_version
        version_label = QLabel(f"v{get_version()}")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet("color: #7f8c8d; font-size: 11px; padding: 10px;")
        sidebar_layout.addWidget(version_label)

        main_layout.addWidget(sidebar)

        # === 内容区域 ===
        content_area = QWidget()
        content_area.setObjectName("content_area")
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(20, 16, 20, 16)

        # 欢迎页
        self._stack = QStackedWidget()
        self._welcome_page = self._create_welcome_page()
        self._stack.addWidget(self._welcome_page)

        content_layout.addWidget(self._stack)
        main_layout.addWidget(content_area, stretch=1)

        # 状态栏
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("就绪")

    def _create_welcome_page(self) -> QWidget:
        """创建欢迎页"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        welcome = QLabel("欢迎使用 Toolkit")
        welcome.setObjectName("title_label")
        welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(welcome)

        hint = QLabel("请从左侧选择一个工具开始使用")
        hint.setObjectName("status_label")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("font-size: 14px; margin-top: 10px;")
        layout.addWidget(hint)

        return page

    def _load_plugins(self):
        """发现并加载插件"""
        plugins_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "plugins"
        )
        discovered = self._plugin_manager.discover_plugins(plugins_dir)
        logger.info(f"共发现 {len(discovered)} 个插件")

        # 为每个插件创建导航按钮和内容页
        for _, name in enumerate(discovered):
            plugin = self._plugin_manager.get_plugin(name)

            # 导航按钮
            btn = SidebarButton(name, f"  {plugin.display_name}")
            btn.clicked.connect(lambda checked, n=name: self._switch_plugin(n))
            self._nav_buttons[name] = btn
            self._nav_container.addWidget(btn)

            # 内容页
            widget = self._plugin_manager.get_plugin_widget(name, self)
            if widget:
                self._stack.addWidget(widget)

        # 默认选中第一个
        if discovered:
            first_name = discovered[0]
            self._switch_plugin(first_name)

    def _add_builtin_pages(self):
        """添加内建页面（版本动态等）到侧边栏"""
        from plugins.peel_data.ui.version_history import VersionPageWidget
        from plugins.peel_data.plugin import PeelDataPlugin

        # 版本动态页面
        plugin = PeelDataPlugin()
        self._version_page = VersionPageWidget(
            current_version=plugin.version, parent=self
        )
        self._stack.addWidget(self._version_page)

        btn_version = SidebarButton(self.PAGE_VERSION, "  版本动态")
        btn_version.clicked.connect(lambda: self._switch_builtin(self.PAGE_VERSION))
        self._nav_buttons[self.PAGE_VERSION] = btn_version
        self._builtin_nav_container.addWidget(btn_version)

        # 综合设置（弹出对话框，非嵌入页面）
        btn_settings = SidebarButton(self.PAGE_SETTINGS, "  ⚙ 综合设置")
        btn_settings.setCheckable(False)
        btn_settings.clicked.connect(self._open_settings)
        self._builtin_nav_container.addWidget(btn_settings)

    def _switch_plugin(self, name: str):
        """切换到指定插件"""
        # 更新导航按钮状态
        for btn_name, btn in self._nav_buttons.items():
            btn.setChecked(btn_name == name)

        # 切换内容页
        widget = self._plugin_manager.get_plugin_widget(name, self)
        if widget:
            idx = self._stack.indexOf(widget)
            if idx >= 0:
                self._stack.setCurrentIndex(idx)

        # 激活插件
        self._plugin_manager.activate_plugin(name)
        plugin = self._plugin_manager.get_plugin(name)
        self._status_bar.showMessage(f"当前工具: {plugin.display_name}")
        logger.debug(f"切换到插件: {name}")

    def _switch_builtin(self, page_id: str):
        """切换到内建页面"""
        # 更新导航按钮状态
        for btn_name, btn in self._nav_buttons.items():
            btn.setChecked(btn_name == page_id)

        # 停用当前插件
        active = self._plugin_manager.active_plugin
        if active:
            self._plugin_manager.deactivate_plugin(active)

        # 切换内容页
        if page_id == self.PAGE_VERSION:
            idx = self._stack.indexOf(self._version_page)
            if idx >= 0:
                self._stack.setCurrentIndex(idx)
            self._status_bar.showMessage("版本动态")

    def _apply_style(self):
        """应用样式"""
        self.setStyleSheet(LIGHT_STYLE)

    def _open_settings(self):
        """打开综合设置对话框"""
        from ui.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self)
        dialog.exec()

    def set_status(self, message: str):
        """设置状态栏消息"""
        self._status_bar.showMessage(message)
