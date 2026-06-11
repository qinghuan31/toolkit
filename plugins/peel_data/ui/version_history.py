# -*- coding: utf-8 -*-
"""
版本更新日志页面
解析 VERSION_LOG.md，以时间线形式展示版本历史，
支持分类查看、版本对比、搜索筛选、检查更新。
提供两种使用方式：
  - VersionPageWidget(QWidget): 嵌入侧边栏的页面
  - VersionHistoryDialog(QDialog): 弹窗方式（向后兼容）
"""

import os
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QLineEdit, QComboBox, QTableWidget, QTableWidgetItem,
    QTabWidget, QWidget, QScrollArea, QFrame, QSizePolicy,
    QHeaderView, QMessageBox, QApplication, QStyle,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor, QPalette


VERSION_LOG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "VERSION_LOG.md"
)


@dataclass
class VersionEntry:
    """单个版本的完整信息"""
    version: str
    date: str
    features: List[str] = field(default_factory=list)   # 新增功能
    improvements: List[str] = field(default_factory=list)  # 功能改进
    fixes: List[str] = field(default_factory=list)         # 问题修复

    def all_lines(self) -> List[str]:
        """返回所有更新条目的扁平列表"""
        lines = []
        for prefix, items in [("✨ ", self.features), ("⚡ ", self.improvements), ("🐛 ", self.fixes)]:
            for item in items:
                lines.append(prefix + item)
        return lines

    def match_keyword(self, keyword: str) -> bool:
        """检查该版本是否匹配关键词"""
        kw = keyword.lower()
        if kw in self.version.lower() or kw in self.date.lower():
            return True
        for items in [self.features, self.improvements, self.fixes]:
            for line in items:
                if kw in line.lower():
                    return True
        return False


def parse_version_log(file_path: str = None) -> List[VersionEntry]:
    """
    解析 VERSION_LOG.md 文件，返回版本列表（按版本号降序）。
    格式约定：
      ## [x.y.z] - YYYY-MM-DD
      ### 新增功能
      - 条目1
      ### 功能改进
      - 条目1
      ### 问题修复
      - 条目1
    """
    if file_path is None:
        file_path = VERSION_LOG_PATH

    if not os.path.exists(file_path):
        return []

    entries: List[VersionEntry] = []
    current: Optional[VersionEntry] = None
    current_section: Optional[str] = None

    section_map = {
        "新增功能": "features",
        "功能改进": "improvements",
        "问题修复": "fixes",
    }

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n").rstrip("\r")

            # 匹配版本标题
            m = re.match(r"##\s*\[([^\]]+)\]\s*-\s*(\S+)", line)
            if m:
                if current:
                    entries.append(current)
                current = VersionEntry(version=m.group(1), date=m.group(2))
                current_section = None
                continue

            # 匹配分类标题
            for heading, attr in section_map.items():
                if heading in line and line.strip().startswith("###"):
                    current_section = attr
                    break
            else:
                # 普通条目
                if current and current_section:
                    item = _parse_list_item(line)
                    if item:
                        getattr(current, current_section).append(item)

    if current:
        entries.append(current)

    return entries


def _parse_list_item(line: str) -> Optional[str]:
    """解析列表条目，去掉 - / * 前缀和 Markdown 加粗标记"""
    s = line.strip()
    if not s:
        return None
    # 去掉列表标记
    s = re.sub(r"^[-*]\s*", "", s)
    # 去掉 Markdown 加粗/斜体
    s = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", s)
    # 去掉行末的 ---
    s = re.sub(r"\s*---+\s*$", "", s)
    return s.strip() or None


# ---------------------------------------------------------------------------
# UI 组件
# ---------------------------------------------------------------------------

class VersionTimelineCard(QFrame):
    """单个版本的卡片视图（时间线样式）"""

    def __init__(self, entry: VersionEntry, is_latest: bool = False, parent=None):
        super().__init__(parent)
        self._entry = entry
        self._setup_ui(is_latest)

    def _setup_ui(self, is_latest: bool):
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(self._card_style(is_latest))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(6)

        # 版本号 + 日期行
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)
        version_label = QLabel(f"v{self._entry.version}")
        version_font = QFont()
        version_font.setBold(True)
        version_font.setPointSize(13)
        version_label.setFont(version_font)
        version_label.setStyleSheet("color: #2980b9;" if is_latest else "color: #2c3e50;")
        header_layout.addWidget(version_label)

        date_label = QLabel(self._entry.date)
        date_label.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        header_layout.addWidget(date_label)

        if is_latest:
            latest_tag = QLabel("当前版本")
            latest_tag.setStyleSheet(
                "background-color: #27ae60; color: white; "
                "font-size: 11px; font-weight: bold; "
                "border-radius: 3px; padding: 1px 8px;"
            )
            header_layout.addWidget(latest_tag)

        header_layout.addStretch()
        layout.addLayout(header_layout)

        # 分类条目
        category_configs = [
            ("新增功能", self._entry.features, "#27ae60", "✨"),
            ("功能改进", self._entry.improvements, "#2980b9", "⚡"),
            ("问题修复", self._entry.fixes, "#e67e22", "🐛"),
        ]
        for title, items, color, icon in category_configs:
            if not items:
                continue
            section_label = QLabel(f"{icon} {title}")
            section_label.setStyleSheet(
                f"color: {color}; font-weight: bold; font-size: 12px; margin-top: 6px;"
            )
            layout.addWidget(section_label)
            for item in items:
                item_label = QLabel(f"  · {item}")
                item_label.setWordWrap(True)
                item_label.setStyleSheet("color: #34495e; font-size: 12px; line-height: 1.4;")
                layout.addWidget(item_label)

        layout.addStretch()

    def _card_style(self, is_latest: bool) -> str:
        if is_latest:
            return (
                "QFrame {"
                "  background-color: #ebf5fb;"
                "  border: 1px solid #aed6f1;"
                "  border-radius: 8px;"
                "  margin: 4px 0;"
                "}"
            )
        return (
            "QFrame {"
            "  background-color: #f8f9fa;"
            "  border: 1px solid #d5dbdb;"
            "  border-radius: 8px;"
            "  margin: 4px 0;"
            "}"
        )


class VersionCompareWidget(QWidget):
    """版本对比视图：左-右并排显示两个版本的差异"""

    def __init__(self, entries: List[VersionEntry], parent=None):
        super().__init__(parent)
        self._entries = entries
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # 版本选择器
        select_layout = QHBoxLayout()
        select_layout.setSpacing(8)

        select_layout.addWidget(QLabel("版本 A："))
        self._combo_a = QComboBox()
        self._combo_a.setMinimumWidth(160)
        select_layout.addWidget(self._combo_a)

        select_layout.addWidget(QLabel("  对比  "))

        self._combo_b = QComboBox()
        self._combo_b.setMinimumWidth(160)
        select_layout.addWidget(self._combo_b)

        select_layout.addStretch()

        btn_compare = QPushButton("开始对比")
        btn_compare.setObjectName("btn_success")
        btn_compare.setMinimumWidth(90)
        btn_compare.clicked.connect(self._on_compare)
        select_layout.addWidget(btn_compare)

        layout.addLayout(select_layout)

        # 对比结果表格
        self._table = QTableWidget()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["变更项", "版本 A", "版本 B"])
        h = self._table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        h.resizeSection(1, 80)
        h.resizeSection(2, 80)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        layout.addWidget(self._table)

        # 填充版本下拉框
        for e in self._entries:
            label = f"v{e.version} ({e.date})"
            self._combo_a.addItem(label, e.version)
            self._combo_b.addItem(label, e.version)

        # 默认选最新和次新版本
        if len(self._entries) >= 1:
            self._combo_a.setCurrentIndex(0)
        if len(self._entries) >= 2:
            self._combo_b.setCurrentIndex(1)
        elif len(self._entries) >= 1:
            self._combo_b.setCurrentIndex(0)

        self._on_compare()

    def _find_entry(self, version: str):
        """根据版本号查找 VersionEntry"""
        for entry in self._entries:
            if entry.version == version:
                return entry
        return None

    def _on_compare(self):
        """生成两个版本的对比表格"""
        ver_a = self._combo_a.currentData()
        ver_b = self._combo_b.currentData()
        entry_a = self._find_entry(ver_a)
        entry_b = self._find_entry(ver_b)

        # 每行: (分类/功能点, 版本A标记, 版本B标记)
        display_rows = []

        for title, items_a, items_b in [
            ("✨ 新增功能", entry_a.features if entry_a else [], entry_b.features if entry_b else []),
            ("⚡ 功能改进", entry_a.improvements if entry_a else [], entry_b.improvements if entry_b else []),
            ("🐛 问题修复", entry_a.fixes if entry_a else [], entry_b.fixes if entry_b else []),
        ]:
            # 分类标题行
            display_rows.append((title, "", ""))
            # 所有功能点的并集，排序后显示
            all_items = sorted(set(items_a) | set(items_b))
            for it in all_items:
                mark_a = "✓" if it in items_a else "—"
                mark_b = "✓" if it in items_b else "—"
                display_rows.append((f"  {it}", mark_a, mark_b))

        self._table.setRowCount(len(display_rows))
        self._table.setVerticalHeaderLabels([""] * len(display_rows))
        for row_idx, (col0, col1, col2) in enumerate(display_rows):
            item0 = QTableWidgetItem(col0)
            item1 = QTableWidgetItem(col1)
            item2 = QTableWidgetItem(col2)
            item1.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item2.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            # 标题行样式
            if not col0.startswith("  "):
                font = QFont()
                font.setBold(True)
                item0.setFont(font)
                # 标题行背景色
                item0.setBackground(QColor("#f5f7fa"))
                item1.setBackground(QColor("#f5f7fa"))
                item2.setBackground(QColor("#f5f7fa"))
            else:
                # 对比结果颜色标记
                if col1 == "✓" and col2 == "—":
                    item1.setForeground(QColor("#27ae60"))
                    item2.setForeground(QColor("#95a5a6"))
                elif col1 == "—" and col2 == "✓":
                    item1.setForeground(QColor("#95a5a6"))
                    item2.setForeground(QColor("#27ae60"))
                elif col1 == "✓" and col2 == "✓":
                    item1.setForeground(QColor("#27ae60"))
                    item2.setForeground(QColor("#27ae60"))

            self._table.setItem(row_idx, 0, item0)
            self._table.setItem(row_idx, 1, item1)
            self._table.setItem(row_idx, 2, item2)

        self._table.resizeColumnsToContents()


class VersionHistoryDialog(QDialog):
    """
    版本更新日志主对话框
    顶部：当前版本号 + 搜索/筛选
    标签页1：时间线视图
    标签页2：版本对比视图
    """

    def __init__(self, current_version: str = "1.0.0", parent=None):
        super().__init__(parent)
        self._current_version = current_version
        self._entries = parse_version_log()
        self._filtered: List[VersionEntry] = list(self._entries)
        self.setWindowTitle("版本更新日志")
        self.setMinimumSize(850, 600)
        self.resize(950, 680)
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # ===== 顶部：当前版本 + 搜索 =====
        top_layout = QHBoxLayout()
        top_layout.setSpacing(12)

        current_label = QLabel(f"当前版本：v{self._current_version}")
        current_font = QFont()
        current_font.setBold(True)
        current_font.setPointSize(14)
        current_label.setFont(current_font)
        current_label.setStyleSheet("color: #2980b9;")
        top_layout.addWidget(current_label)

        top_layout.addStretch()

        top_layout.addWidget(QLabel("搜索："))
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("输入关键词...")
        self._search_edit.setMinimumWidth(160)
        self._search_edit.setMaximumWidth(220)
        self._search_edit.textChanged.connect(self._on_filter_changed)
        top_layout.addWidget(self._search_edit)

        top_layout.addWidget(QLabel("版本："))
        self._version_combo = QComboBox()
        self._version_combo.setMinimumWidth(130)
        self._version_combo.addItem("全部版本", "")
        for e in self._entries:
            self._version_combo.addItem(f"v{e.version}", e.version)
        self._version_combo.currentTextChanged.connect(self._on_filter_changed)
        top_layout.addWidget(self._version_combo)

        main_layout.addLayout(top_layout)

        # ===== 标签页 =====
        self._tabs = QTabWidget()

        # Tab 1: 时间线视图
        self._timeline_tab = self._create_timeline_tab()
        self._tabs.addTab(self._timeline_tab, "时间线")

        # Tab 2: 版本对比视图
        self._compare_tab = VersionCompareWidget(self._entries)
        self._tabs.addTab(self._compare_tab, "版本对比")

        main_layout.addWidget(self._tabs)

        # ===== 底部关闭按钮 =====
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_close = QPushButton("关闭")
        btn_close.setMinimumWidth(80)
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)
        main_layout.addLayout(btn_layout)

    def _create_timeline_tab(self) -> QScrollArea:
        """创建时间线滚动视图"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._timeline_container = container
        self._timeline_layout = layout

        scroll.setWidget(container)
        self._refresh_timeline()
        return scroll

    def _refresh_timeline(self):
        """根据筛选条件刷新时间线"""
        # 清空旧内容
        while self._timeline_layout.count():
            item = self._timeline_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._filtered:
            empty_label = QLabel("未找到匹配的版本记录")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_label.setStyleSheet(
                "color: #909399; font-size: 14px; padding: 40px;"
            )
            self._timeline_layout.addWidget(empty_label)
            return

        for idx, entry in enumerate(self._filtered):
            is_latest = (idx == 0) and (entry.version == self._current_version)
            card = VersionTimelineCard(entry, is_latest=is_latest)
            self._timeline_layout.addWidget(card)

        self._timeline_layout.addStretch()

    def _on_filter_changed(self):
        """搜索框或版本筛选器变化时重新筛选"""
        keyword = self._search_edit.text().strip().lower()
        selected_version = self._version_combo.currentData()

        self._filtered = []
        for entry in self._entries:
            # 版本号筛选
            if selected_version and entry.version != selected_version:
                continue
            # 关键词筛选
            if keyword and not entry.match_keyword(keyword):
                continue
            self._filtered.append(entry)

        self._refresh_timeline()

    def _on_version_selected(self, index: int):
        self._on_filter_changed()


class VersionPageWidget(QWidget):
    """
    版本动态页面（嵌入侧边栏的内容页）
    集成：版本时间线、版本对比、检查更新、所有修复项/功能新增/特殊改动记录
    """

    # 信号：请求切换到指定插件的版本动态页
    check_update_requested = Signal()

    def __init__(self, current_version: str = "1.0.0", parent=None):
        super().__init__(parent)
        self._current_version = current_version
        self._entries = parse_version_log()
        self._filtered: List[VersionEntry] = list(self._entries)
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 16, 20, 16)
        main_layout.setSpacing(12)

        # ===== 顶部：标题 + 当前版本 + 操作按钮 =====
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        title_label = QLabel("版本动态")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(14)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)

        version_label = QLabel(f"v{self._current_version}")
        version_label.setStyleSheet(
            "background-color: #27ae60; color: white; "
            "font-size: 11px; font-weight: bold; "
            "border-radius: 3px; padding: 2px 10px;"
        )
        header_layout.addWidget(version_label)

        header_layout.addStretch()

        # 检查更新按钮
        self._btn_check_update = QPushButton("检查更新")
        self._btn_check_update.setMinimumWidth(90)
        self._btn_check_update.setObjectName("btn_warning")
        self._btn_check_update.clicked.connect(self._on_check_update)
        header_layout.addWidget(self._btn_check_update)

        main_layout.addLayout(header_layout)

        # ===== 搜索/筛选栏 =====
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(8)

        filter_layout.addWidget(QLabel("搜索："))
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("输入关键词...")
        self._search_edit.setMinimumWidth(140)
        self._search_edit.setMaximumWidth(200)
        self._search_edit.setClearButtonEnabled(True)
        self._search_edit.textChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self._search_edit)

        filter_layout.addWidget(QLabel("版本："))
        self._version_combo = QComboBox()
        self._version_combo.setMinimumWidth(120)
        self._version_combo.addItem("全部版本", "")
        for e in self._entries:
            self._version_combo.addItem(f"v{e.version}", e.version)
        self._version_combo.currentTextChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self._version_combo)

        filter_layout.addStretch()
        main_layout.addLayout(filter_layout)

        # ===== 标签页 =====
        self._tabs = QTabWidget()

        # Tab 1: 时间线视图
        self._timeline_tab = self._create_timeline_tab()
        self._tabs.addTab(self._timeline_tab, "时间线")

        # Tab 2: 版本对比视图
        self._compare_tab = VersionCompareWidget(self._entries)
        self._tabs.addTab(self._compare_tab, "版本对比")

        # Tab 3: 变更总览（所有修复项/功能新增/特殊改动的统计视图）
        self._overview_tab = self._create_overview_tab()
        self._tabs.addTab(self._overview_tab, "变更总览")

        main_layout.addWidget(self._tabs, stretch=1)

    def _create_timeline_tab(self) -> QScrollArea:
        """创建时间线滚动视图"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._timeline_container = container
        self._timeline_layout = layout

        scroll.setWidget(container)
        self._refresh_timeline()
        return scroll

    def _refresh_timeline(self):
        """根据筛选条件刷新时间线"""
        while self._timeline_layout.count():
            item = self._timeline_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._filtered:
            empty_label = QLabel("未找到匹配的版本记录")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_label.setStyleSheet(
                "color: #909399; font-size: 14px; padding: 40px;"
            )
            self._timeline_layout.addWidget(empty_label)
            return

        for idx, entry in enumerate(self._filtered):
            is_latest = (idx == 0) and (entry.version == self._current_version)
            card = VersionTimelineCard(entry, is_latest=is_latest)
            self._timeline_layout.addWidget(card)

        self._timeline_layout.addStretch()

    def _create_overview_tab(self) -> QWidget:
        """创建变更总览标签页（统计所有版本的修复项/功能新增/特殊改动）"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # 统计概览
        total_features = sum(len(e.features) for e in self._entries)
        total_improvements = sum(len(e.improvements) for e in self._entries)
        total_fixes = sum(len(e.fixes) for e in self._entries)

        stats_label = QLabel(
            f"共 {len(self._entries)} 个版本 | "
            f"✨ 新增功能 {total_features} 项 | "
            f"⚡ 功能改进 {total_improvements} 项 | "
            f"🐛 问题修复 {total_fixes} 项"
        )
        stats_label.setStyleSheet(
            "color: #606266; font-size: 12px; "
            "background-color: #f5f7fa; border-radius: 4px; "
            "padding: 8px 12px;"
        )
        layout.addWidget(stats_label)

        # 完整变更列表表格
        self._overview_table = QTableWidget()
        self._overview_table.setColumnCount(4)
        self._overview_table.setHorizontalHeaderLabels(["版本", "分类", "变更内容", "日期"])
        self._overview_table.setAlternatingRowColors(True)
        self._overview_table.verticalHeader().setVisible(False)
        self._overview_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        h = self._overview_table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        h.resizeSection(0, 80)
        h.resizeSection(1, 90)
        h.resizeSection(3, 110)

        # 填充数据
        rows = []
        for entry in self._entries:
            for cat, items, color in [
                ("新增功能", entry.features, "#27ae60"),
                ("功能改进", entry.improvements, "#2980b9"),
                ("问题修复", entry.fixes, "#e67e22"),
            ]:
                for item in items:
                    rows.append((entry.version, cat, item, entry.date, color))

        self._overview_table.setRowCount(len(rows))
        for row_idx, (ver, cat, content, date, color) in enumerate(rows):
            ver_item = QTableWidgetItem(f"v{ver}")
            ver_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._overview_table.setItem(row_idx, 0, ver_item)

            cat_item = QTableWidgetItem(cat)
            cat_item.setForeground(QColor(color))
            cat_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            font = QFont()
            font.setBold(True)
            cat_item.setFont(font)
            self._overview_table.setItem(row_idx, 1, cat_item)

            content_item = QTableWidgetItem(content)
            self._overview_table.setItem(row_idx, 2, content_item)

            date_item = QTableWidgetItem(date)
            date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._overview_table.setItem(row_idx, 3, date_item)

        layout.addWidget(self._overview_table, stretch=1)
        return page

    def _on_filter_changed(self):
        """搜索框或版本筛选器变化时重新筛选"""
        keyword = self._search_edit.text().strip().lower()
        selected_version = self._version_combo.currentData()

        self._filtered = []
        for entry in self._entries:
            if selected_version and entry.version != selected_version:
                continue
            if keyword and not entry.match_keyword(keyword):
                continue
            self._filtered.append(entry)

        self._refresh_timeline()

    def _on_check_update(self):
        """检查更新"""
        try:
            import json
            import urllib.request

            # 读取当前版本号
            current = self._current_version

            # TODO: 替换为实际的更新检查地址
            update_url = "https://api.example.com/toolkit/version.json"

            self._btn_check_update.setEnabled(False)
            self._btn_check_update.setText("检查中...")

            try:
                req = urllib.request.Request(
                    update_url,
                    headers={"User-Agent": "Toolkit-VersionCheck/1.0"},
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    latest_version = data.get("version", "")
                    download_url = data.get("download_url", "")
                    changelog = data.get("changelog", "")

                    if latest_version and latest_version != current:
                        msg = (
                            f"发现新版本：v{latest_version}\n\n"
                            f"当前版本：v{current}\n\n"
                            f"更新内容：\n{changelog}\n\n"
                            f"请访问下载页面获取最新版本。"
                        )
                        reply = QMessageBox.information(
                            self, "发现新版本", msg,
                            QMessageBox.StandardButton.Ok,
                        )
                    else:
                        QMessageBox.information(
                            self, "已是最新版本",
                            f"当前版本 v{current} 已是最新版本"
                        )
            except Exception as e:
                QMessageBox.warning(
                    self, "检查失败",
                    f"无法连接更新服务器：\n{e}\n\n"
                    f"请检查网络连接或稍后重试。"
                )
        finally:
            self._btn_check_update.setEnabled(True)
            self._btn_check_update.setText("检查更新")
