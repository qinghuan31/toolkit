# -*- coding: utf-8 -*-
"""Workbench and module-center pages for Toolkit."""

from __future__ import annotations

from typing import Callable, Iterable

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class MetricCard(QFrame):
    """Small dashboard card used on the workbench."""

    def __init__(self, label: str, value: str, hint: str, accent: str = "#3b82f6", parent=None):
        super().__init__(parent)
        self.setObjectName("metric_card")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(8)

        top = QHBoxLayout()
        title = QLabel(label)
        title.setObjectName("metric_label")
        dot = QLabel()
        dot.setFixedSize(9, 9)
        dot.setStyleSheet(f"background-color: {accent}; border-radius: 4px;")
        top.addWidget(title)
        top.addStretch()
        top.addWidget(dot)
        layout.addLayout(top)

        number = QLabel(value)
        number.setObjectName("metric_value")
        layout.addWidget(number)

        desc = QLabel(hint)
        desc.setObjectName("metric_hint")
        desc.setWordWrap(True)
        layout.addWidget(desc)


class ModuleCard(QFrame):
    """Clickable module card for plugin entry points."""

    def __init__(
        self,
        name: str,
        title: str,
        description: str,
        version: str,
        on_open: Callable[[str], None],
        parent=None,
    ):
        super().__init__(parent)
        self._name = name
        self._on_open = on_open
        self.setObjectName("module_card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(152)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        header = QHBoxLayout()
        icon = QLabel(_module_initial(title))
        icon.setObjectName("module_icon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(42, 42)
        header.addWidget(icon)

        title_box = QVBoxLayout()
        title_label = QLabel(title)
        title_label.setObjectName("module_title")
        version_label = QLabel(f"v{version} · 功能块")
        version_label.setObjectName("module_meta")
        title_box.addWidget(title_label)
        title_box.addWidget(version_label)
        header.addLayout(title_box, stretch=1)
        layout.addLayout(header)

        body = QLabel(description)
        body.setObjectName("module_desc")
        body.setWordWrap(True)
        layout.addWidget(body)

        footer = QHBoxLayout()
        badge = QLabel("可用")
        badge.setObjectName("badge_success")
        open_btn = QPushButton("进入功能块")
        open_btn.setObjectName("btn_primary")
        open_btn.clicked.connect(lambda: self._on_open(self._name))
        footer.addWidget(badge)
        footer.addStretch()
        footer.addWidget(open_btn)
        layout.addLayout(footer)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_open(self._name)
        super().mouseReleaseEvent(event)


class WorkbenchPage(QWidget):
    """Toolkit-level home page. The product subject is the workbench, not one plugin."""

    def __init__(self, plugins: Iterable[object], on_open_modules: Callable[[], None], on_open_plugin: Callable[[str], None], parent=None):
        super().__init__(parent)
        self.setObjectName("workbench_page")
        self._plugins = list(plugins)
        self._on_open_modules = on_open_modules
        self._on_open_plugin = on_open_plugin
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 4, 6, 4)
        root.setSpacing(18)

        hero = QFrame()
        hero.setObjectName("workbench_hero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(26, 24, 26, 24)
        hero_layout.setSpacing(18)

        copy = QVBoxLayout()
        eyebrow = QLabel("Toolkit 工作台")
        eyebrow.setObjectName("eyebrow_label")
        title = QLabel("把常用工具收进一个清晰的功能块中心")
        title.setObjectName("hero_title")
        title.setWordWrap(True)
        desc = QLabel("先选择功能块，再进入具体任务。剥离数据、汇总、历史与设置都服务于 Toolkit 的整体工作流。")
        desc.setObjectName("hero_desc")
        desc.setWordWrap(True)
        copy.addWidget(eyebrow)
        copy.addWidget(title)
        copy.addWidget(desc)
        hero_layout.addLayout(copy, stretch=1)

        actions = QVBoxLayout()
        modules_btn = QPushButton("打开功能块中心")
        modules_btn.setObjectName("btn_primary")
        modules_btn.clicked.connect(self._on_open_modules)
        first_btn = QPushButton("进入首个可用功能")
        first_btn.setObjectName("btn_secondary")
        first_btn.clicked.connect(self._open_first_plugin)
        actions.addWidget(modules_btn)
        actions.addWidget(first_btn)
        actions.addStretch()
        hero_layout.addLayout(actions)
        root.addWidget(hero)

        metrics = QHBoxLayout()
        metrics.setSpacing(14)
        metrics.addWidget(MetricCard("功能块", str(len(self._plugins)), "已安装并可从功能中心进入", "#3b82f6"))
        metrics.addWidget(MetricCard("全局历史", "统一", "后续所有功能块共享追溯入口", "#10b981"))
        metrics.addWidget(MetricCard("设置策略", "显式保存", "网络、Token、数据库路径不误触落盘", "#f59e0b"))
        root.addLayout(metrics)

        section = QHBoxLayout()
        section_title = QLabel("推荐入口")
        section_title.setObjectName("section_title")
        more = QPushButton("查看全部")
        more.setObjectName("btn_secondary")
        more.clicked.connect(self._on_open_modules)
        section.addWidget(section_title)
        section.addStretch()
        section.addWidget(more)
        root.addLayout(section)

        card_grid = QGridLayout()
        card_grid.setSpacing(14)
        for index, plugin in enumerate(self._plugins[:2]):
            card_grid.addWidget(
                ModuleCard(
                    plugin.name,
                    plugin.display_name,
                    plugin.description,
                    plugin.version,
                    self._on_open_plugin,
                ),
                0,
                index,
            )
        card_grid.setColumnStretch(0, 1)
        card_grid.setColumnStretch(1, 1)
        root.addLayout(card_grid)
        root.addStretch()

    def _open_first_plugin(self):
        if self._plugins:
            self._on_open_plugin(self._plugins[0].name)


class ModulesPage(QWidget):
    """All modules page. This is Toolkit's plugin-level information architecture."""

    def __init__(self, plugins: Iterable[object], on_open_plugin: Callable[[str], None], parent=None):
        super().__init__(parent)
        self.setObjectName("modules_page")
        self._plugins = list(plugins)
        self._on_open_plugin = on_open_plugin
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 4, 6, 4)
        root.setSpacing(16)

        header = QHBoxLayout()
        copy = QVBoxLayout()
        title = QLabel("功能块中心")
        title.setObjectName("page_title")
        desc = QLabel("所有工具以功能块形式组织。进入功能块后再处理具体任务，避免单个业务抢走 Toolkit 主体。")
        desc.setObjectName("page_desc")
        desc.setWordWrap(True)
        copy.addWidget(title)
        copy.addWidget(desc)
        header.addLayout(copy, stretch=1)

        count = QLabel(f"{len(self._plugins)} 个功能块")
        count.setObjectName("count_badge")
        header.addWidget(count, alignment=Qt.AlignmentFlag.AlignTop)
        root.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        grid = QGridLayout(content)
        grid.setContentsMargins(0, 0, 8, 0)
        grid.setSpacing(14)

        for index, plugin in enumerate(self._plugins):
            row, col = divmod(index, 2)
            grid.addWidget(
                ModuleCard(
                    plugin.name,
                    plugin.display_name,
                    plugin.description,
                    plugin.version,
                    self._on_open_plugin,
                ),
                row,
                col,
            )
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch((len(self._plugins) + 1) // 2, 1)
        scroll.setWidget(content)
        root.addWidget(scroll, stretch=1)


def _module_initial(title: str) -> str:
    clean = title.strip()
    return clean[0] if clean else "T"
