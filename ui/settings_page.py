# -*- coding: utf-8 -*-
"""
Toolkit 综合设置内建页面（v1.7.3）
- 将原 SettingsDialog 内的三个 Tab 抽出为可嵌入的页面
- 保留底部"保存/放弃改动"行为与脏值追踪
- 主窗口可直接 addWidget()，用户从侧边栏进入一级页面
- 兼容旧版弹窗入口：仍提供 open_as_dialog() 兜底
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QScrollArea,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.logger import get_logger
from ui.settings_dialog import (
    _NetworkTab,
    _PluginTab,
    _ImportExportTab,
    SETTINGS_DIALOG_STYLE,
)

logger = get_logger("settings_page")


class SettingsPage(QWidget):
    """综合设置内建页面（一级页面，可嵌入主窗口 QStackedWidget）。

    复用 SettingsDialog 的三个 Tab 组件，保持所有交互行为不变。
    增加了"应用配置后通知外部刷新"的能力，主窗口可在导入配置后
    重新加载工作台 / 功能块 / 历史页。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("settings_page")
        self._dirty = False
        self._setup_ui()
        self._apply_style()
        self._set_dirty(False)

    # --- UI ---
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(12)

        # 顶部 header
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("综合设置")
        title.setObjectName("page_title")
        subtitle = QLabel("网络模式、Token、数据库路径、关键词等敏感配置，统一在显式「保存」后落盘。")
        subtitle.setObjectName("page_desc")
        subtitle.setWordWrap(True)
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box, stretch=1)

        # 版本号 + 角标
        right_box = QHBoxLayout()
        right_box.setSpacing(10)
        from config import get_version
        ver_lbl = QLabel(f"v{get_version()}")
        ver_lbl.setObjectName("hint_label")
        right_box.addWidget(ver_lbl, alignment=Qt.AlignmentFlag.AlignTop)
        self._dirty_badge = QLabel("● 未保存")
        self._dirty_badge.setObjectName("dirty_badge")
        self._dirty_badge.setVisible(False)
        right_box.addWidget(self._dirty_badge, alignment=Qt.AlignmentFlag.AlignTop)
        header.addLayout(right_box)
        layout.addLayout(header)

        # Tab 容器
        self._tabs = QTabWidget()
        self._network_tab = _NetworkTab(self)
        self._tabs.addTab(self._network_tab, "🌐 局域网配置")

        self._plugin_tab = _PluginTab(self)
        try:
            from plugins.peel_data.plugin import PeelDataPlugin
            plugin_display = PeelDataPlugin().display_name
        except Exception:
            plugin_display = "peel_data"
        self._tabs.addTab(self._plugin_tab, f"📋 {plugin_display} 参数")

        self._import_export_tab = _ImportExportTab(self)
        self._tabs.addTab(self._import_export_tab, "💾 导入/导出")

        self._tabs.currentChanged.connect(self._refresh_dirty_state)
        self._tabs.setMinimumSize(760, 650)
        self._network_tab.setMinimumSize(760, 620)
        self._plugin_tab.setMinimumSize(760, 620)
        self._import_export_tab.setMinimumSize(760, 560)

        scroll = QScrollArea()
        scroll.setObjectName("settings_scroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setWidget(self._tabs)
        layout.addWidget(scroll, stretch=1)

        # 底部按钮
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.setContentsMargins(0, 8, 0, 0)

        self._hint_label = QLabel("所有改动仅在「保存」后生效。")
        self._hint_label.setObjectName("hint_label")
        self._hint_label.setWordWrap(True)
        btn_row.addWidget(self._hint_label, stretch=1)

        self._btn_revert = QPushButton("放弃改动")
        self._btn_revert.setObjectName("btn_secondary")
        self._btn_revert.setMinimumWidth(96)
        self._btn_revert.clicked.connect(self._on_revert)
        self._btn_revert.setEnabled(False)
        btn_row.addWidget(self._btn_revert)

        self._btn_save = QPushButton("💾 保存")
        self._btn_save.setObjectName("btn_primary")
        self._btn_save.setMinimumWidth(96)
        self._btn_save.clicked.connect(self._on_save)
        self._btn_save.setEnabled(False)
        btn_row.addWidget(self._btn_save)

        layout.addLayout(btn_row)

    def _apply_style(self):
        self.setStyleSheet(SETTINGS_DIALOG_STYLE)

    # --- 脏值管理（与 SettingsDialog 行为一致） ---
    def _set_dirty(self, dirty: bool):
        self._dirty = bool(dirty)
        self._dirty_badge.setVisible(self._dirty)
        self._btn_save.setEnabled(self._dirty)
        self._btn_revert.setEnabled(self._dirty)
        if self._dirty:
            self._hint_label.setText("⚠ 有未保存的改动 — 点击「保存」或「放弃改动」")
            self._hint_label.setProperty("state", "warning")
        else:
            self._hint_label.setText("所有改动仅在「保存」后生效。")
            self._hint_label.setProperty("state", "info")
        self._hint_label.style().unpolish(self._hint_label)
        self._hint_label.style().polish(self._hint_label)
        # 同步各 Tab 标题小圆点
        tabs = [self._network_tab, self._plugin_tab]
        for idx, tab in enumerate(tabs):
            text = self._tabs.tabText(idx)
            dirty_tab = self._tab_is_dirty(tab)
            if dirty_tab and "●" not in text:
                self._tabs.setTabText(idx, text + "  ●")
            elif not dirty_tab:
                self._tabs.setTabText(idx, text.replace("  ●", ""))

    def _tab_is_dirty(self, tab) -> bool:
        if hasattr(tab, "is_dirty"):
            try:
                return tab.is_dirty()
            except Exception:
                return False
        return False

    def _refresh_dirty_state(self, *_):
        any_dirty = any(self._tab_is_dirty(t) for t in (self._network_tab, self._plugin_tab))
        self._set_dirty(any_dirty)

    def reload_all_tabs(self):
        """导入配置后由 ImportExport Tab 调用"""
        self._network_tab._load_current()
        self._network_tab._capture_initial()
        self._plugin_tab._load_current()
        self._plugin_tab._capture_initial()
        self._set_dirty(False)
        self._network_tab._sync_server_runtime()

    # --- 行为 ---
    def _on_save(self):
        try:
            self._network_tab.persist_to_config()
            self._plugin_tab.persist_to_config()
        except Exception as e:
            logger.error(f"保存配置失败: {e}", exc_info=True)
            QMessageBox.critical(self, "保存失败", f"保存配置时发生错误:\n{e}")
            return
        self._network_tab._capture_initial()
        self._plugin_tab._capture_initial()
        self._set_dirty(False)
        self._status_flash("✓ 已保存", "success")
        logger.info("综合设置已保存")

    def _on_revert(self):
        reply = QMessageBox.question(
            self, "放弃改动",
            "确定要放弃所有未保存的改动吗？\n所有未保存的值将恢复为保存时的状态。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.reload_all_tabs()
        self._status_flash("已放弃改动", "info")

    def _status_flash(self, text: str, state: str = "info", ms: int = 2000):
        self._hint_label.setText(text)
        self._hint_label.setProperty("state", state)
        self._hint_label.style().unpolish(self._hint_label)
        self._hint_label.style().polish(self._hint_label)


def open_as_dialog(parent=None) -> None:
    """兜底入口：保留原弹窗模式，便于兼容旧测试 / 调试。"""
    from ui.settings_dialog import SettingsDialog
    dlg = SettingsDialog(parent)
    dlg.exec()
