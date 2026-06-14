# -*- coding: utf-8 -*-
"""
Toolkit 全局历史页 (内建一级页面)
- 左侧：按 request_id（每次提取共享一个 UUID）分组的批次列表
- 右侧：当前选中批次的文件级历史 + summary 概览
- 顶部：按插件筛选 + 关键字搜索 + 刷新

数据来源：
  - 聚合 peel_data_extraction_history（按 request_id 聚合）
  - 汇总每次提取写入主表的统计
"""

from __future__ import annotations

from typing import Dict, List, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QComboBox,
)

from core.logger import get_logger
from core.database import DatabaseManager

logger = get_logger("history_page")


class _SummaryCard(QFrame):
    """批次摘要卡：批次号 / 时间 / 成功 / 失败 / 跳过"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("history_summary_card")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        self._title = QLabel("选择一个批次查看详情")
        self._title.setObjectName("history_summary_title")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(13)
        self._title.setFont(title_font)
        layout.addWidget(self._title)

        self._meta = QLabel("—")
        self._meta.setObjectName("history_summary_meta")
        self._meta.setWordWrap(True)
        layout.addWidget(self._meta)

        self._stats_row = QHBoxLayout()
        self._stats_row.setSpacing(16)
        self._lbl_total = self._stat("总文件", "#1f2937")
        self._lbl_ok = self._stat("成功", "#10b981")
        self._lbl_fail = self._stat("失败", "#ef4444")
        self._lbl_skip = self._stat("跳过/重复", "#f59e0b")
        for w in (self._lbl_total, self._lbl_ok, self._lbl_fail, self._lbl_skip):
            self._stats_row.addWidget(w)
        self._stats_row.addStretch()
        layout.addLayout(self._stats_row)

    def _stat(self, label: str, color: str) -> QLabel:
        wrap = QFrame()
        wrap.setObjectName("history_stat_block")
        v = QVBoxLayout(wrap)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)
        lbl = QLabel("0")
        lbl.setStyleSheet(f"color: {color}; font-size: 22px; font-weight: 700;")
        lbl.setObjectName("history_stat_value")
        cap = QLabel(label)
        cap.setStyleSheet("color: #6b7280; font-size: 12px;")
        cap.setObjectName("history_stat_label")
        v.addWidget(lbl)
        v.addWidget(cap)
        # 返回外层 label 容器，但需要给主程序只读 lbl 数字
        wrap._value_label = lbl  # type: ignore[attr-defined]
        return wrap

    def set_summary(self, title: str, meta: str, total: int, ok: int, fail: int, skip: int):
        self._title.setText(title)
        self._meta.setText(meta)
        self._lbl_total._value_label.setText(str(total))
        self._lbl_ok._value_label.setText(str(ok))
        self._lbl_fail._value_label.setText(str(fail))
        self._lbl_skip._value_label.setText(str(skip))


class HistoryPage(QWidget):
    """Toolkit 全局历史页（按批次聚合）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("history_page")
        self._batches: List[Dict] = []  # 当前展示的批次列表
        self._detail_cache: Dict[str, List[Dict]] = {}
        self._pending_detail_request_id: Optional[str] = None
        self._current_request_id: Optional[str] = None
        self._available_plugins: List[Dict[str, str]] = []  # 来自 PluginManager
        self._current_plugin: str = "__all__"  # __all__ 表示不按插件过滤
        self._setup_ui()
        self._reload_available_plugins()
        QTimer.singleShot(0, self.refresh)

    # --- UI ---
    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 4, 6, 4)
        root.setSpacing(14)

        # 顶部标题 + 工具栏
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("全局历史")
        title.setObjectName("page_title")
        subtitle = QLabel("按批次（request_id）聚合所有功能块的提取记录，便于回看追溯。")
        subtitle.setObjectName("page_desc")
        subtitle.setWordWrap(True)
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box, stretch=1)

        self._count_badge = QLabel("— 个批次")
        self._count_badge.setObjectName("count_badge")
        header.addWidget(self._count_badge, alignment=Qt.AlignmentFlag.AlignTop)
        root.addLayout(header)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        toolbar.addWidget(QLabel("功能块："))
        self._plugin_combo = QComboBox()
        self._plugin_combo.setObjectName("history_plugin_combo")
        self._plugin_combo.setMinimumWidth(140)
        self._plugin_combo.currentIndexChanged.connect(self._on_plugin_changed)
        toolbar.addWidget(self._plugin_combo)

        toolbar.addWidget(QLabel("搜索："))
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("按文件名 / 原因 / 批次号筛选")
        self._search_edit.setClearButtonEnabled(True)
        self._search_edit.textChanged.connect(self._apply_filter)
        self._search_edit.setMaximumWidth(320)
        toolbar.addWidget(self._search_edit)

        toolbar.addStretch()

        btn_refresh = QPushButton("刷新")
        btn_refresh.setObjectName("btn_secondary")
        btn_refresh.clicked.connect(self.refresh)
        toolbar.addWidget(btn_refresh)
        root.addLayout(toolbar)

        # 中部 splitter：左侧批次列表 + 右侧详情
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setObjectName("history_splitter")

        # --- 左侧：批次列表 ---
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        list_label = QLabel("批次列表")
        list_label.setObjectName("section_label")
        left_layout.addWidget(list_label)

        self._batch_list = QListWidget()
        self._batch_list.setObjectName("history_batch_list")
        self._batch_list.itemSelectionChanged.connect(self._on_batch_selected)
        self._batch_list.itemClicked.connect(lambda _item: self._on_batch_selected())
        left_layout.addWidget(self._batch_list, stretch=1)

        splitter.addWidget(left)

        # --- 右侧：详情 ---
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        self._summary = _SummaryCard()
        right_layout.addWidget(self._summary)

        detail_label = QLabel("批次内文件明细")
        detail_label.setObjectName("section_label")
        right_layout.addWidget(detail_label)

        self._detail_table = QTableWidget(0, 5)
        self._detail_table.setObjectName("history_detail_table")
        self._detail_table.setHorizontalHeaderLabels(
            ["文件名", "路径", "结果", "原因", "时间"]
        )
        self._detail_table.verticalHeader().setVisible(False)
        self._detail_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._detail_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._detail_table.setAlternatingRowColors(True)
        header_view = self._detail_table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        right_layout.addWidget(self._detail_table, stretch=1)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 6)
        splitter.setSizes([360, 640])
        root.addWidget(splitter, stretch=1)

    # --- 数据加载 ---
    def refresh(self):
        """重新加载批次聚合（从 peel_data_extraction_history）"""
        self._detail_cache.clear()
        self._pending_detail_request_id = None
        self._detail_table.setRowCount(0)
        self._summary.set_summary("正在加载历史批次", "如果历史很多，会先显示批次列表，再按需加载右侧明细。", 0, 0, 0, 0)
        self._reload_available_plugins()
        self._batches = self._load_batches()
        self._apply_filter()

    def _reload_available_plugins(self):
        """从 PluginManager 拉取已注册插件，更新功能块下拉框。
        如果拉不到（PluginManager 单例未注入），至少保留「全部功能块」与「数据提取」两项。
        """
        plugins: List[Dict[str, str]] = []
        try:
            from core.plugin_manager import PluginManager
            pm = PluginManager()
            for name, plugin in pm.get_all_plugins().items():
                plugins.append({
                    "name": name,
                    "display": getattr(plugin, "display_name", name) or name,
                })
        except Exception as e:
            logger.warning(f"读取插件列表失败（保留默认项）: {e}")

        # 始终确保有「全部」与「数据提取」兜底
        have_peel = any(p["name"] == "peel_data" for p in plugins)
        have_all = False
        for p in plugins:
            if p["name"] == "__all__":
                have_all = True
                break
        if not have_all:
            plugins.insert(0, {"name": "__all__", "display": "全部功能块"})
        if not have_peel:
            plugins.append({"name": "peel_data", "display": "数据提取（兜底）"})

        # 顺序：全部 → 其他插件
        plugins.sort(key=lambda p: (0 if p["name"] == "__all__" else 1, p["display"]))

        if plugins == self._available_plugins:
            return  # 列表无变化，避免触发 currentIndexChanged
        self._available_plugins = plugins

        self._plugin_combo.blockSignals(True)
        self._plugin_combo.clear()
        for p in plugins:
            self._plugin_combo.addItem(p["display"], p["name"])
        # 恢复上次选择（默认「全部」）
        target_idx = 0
        for i, p in enumerate(plugins):
            if p["name"] == self._current_plugin:
                target_idx = i
                break
        self._plugin_combo.setCurrentIndex(target_idx)
        self._plugin_combo.blockSignals(False)

    def _on_plugin_changed(self, _index: int):
        plugin_name = self._plugin_combo.currentData() or "__all__"
        if plugin_name == self._current_plugin:
            return
        self._current_plugin = plugin_name
        self._detail_cache.clear()
        self._pending_detail_request_id = None
        self._batches = self._load_batches()
        self._apply_filter()

    def _load_batches(self) -> List[Dict]:
        """按 request_id 聚合历史表，统计每批次的成功/失败/跳过数。
        优先读取 plugin 列；若不存在则按 request_id 聚合后回填默认插件名。
        """
        try:
            from plugins.peel_data.models import ensure_history_table, get_history_table_name
            ensure_history_table()
            table = get_history_table_name()
            db = DatabaseManager()
            rows = db.query_all(
                f'SELECT "request_id", '
                f'COUNT(*) AS total, '
                f'SUM(CASE WHEN "success"=1 THEN 1 ELSE 0 END) AS ok, '
                f'SUM(CASE WHEN "success"=0 THEN 1 ELSE 0 END) AS fail, '
                f'MIN("operation_time") AS first_at, '
                f'MAX("operation_time") AS last_at, '
                f'COALESCE(MIN("plugin"), "peel_data") AS plugin '
                f'FROM "{table}" '
                f'WHERE "request_id" IS NOT NULL AND "request_id" != "" '
                f'GROUP BY "request_id" '
                f'ORDER BY last_at DESC'
            )
        except Exception as e:
            logger.error(f"加载历史批次失败: {e}", exc_info=True)
            return []

        batches = []
        for r in rows or []:
            # query_all 返回 Dict[str, Any]
            req_id = r.get("request_id", "")
            plugin_name = r.get("plugin") or "peel_data"
            if self._current_plugin != "__all__" and plugin_name != self._current_plugin:
                continue
            batches.append({
                "request_id": req_id,
                "plugin": plugin_name,
                "total": r.get("total", 0) or 0,
                "ok": r.get("ok", 0) or 0,
                "fail": r.get("fail", 0) or 0,
                "first_at": r.get("first_at", "") or "",
                "last_at": r.get("last_at", "") or "",
                # 跳过/重复数量不直接统计在历史表（历史表只记文件级 success/fail）
                "skip": 0,
            })
        return batches

    def _apply_filter(self):
        """根据搜索框过滤批次列表"""
        keyword = self._search_edit.text().strip().lower()
        self._batch_list.blockSignals(True)
        self._batch_list.clear()
        for b in self._batches:
            blob = " ".join([
                b.get("request_id", ""),
                b.get("plugin", ""),
                b.get("first_at", ""),
                b.get("last_at", ""),
            ]).lower()
            if keyword and keyword not in blob:
                continue
            item = QListWidgetItem(self._format_batch_title(b))
            item.setData(Qt.ItemDataRole.UserRole, b)
            self._batch_list.addItem(item)
        self._batch_list.blockSignals(False)
        self._count_badge.setText(f"{self._batch_list.count()} 个批次")
        if self._batch_list.count() > 0:
            self._batch_list.setCurrentRow(0)
            self._on_batch_selected()
        else:
            self._current_request_id = None
            self._pending_detail_request_id = None
            self._summary.set_summary("暂无匹配批次", "调整搜索词或刷新重试。", 0, 0, 0, 0)
            self._detail_table.setRowCount(0)

    @staticmethod
    def _format_batch_title(b: Dict) -> str:
        rid = b.get("request_id", "")
        short = rid[:8] if rid else "—"
        last = b.get("last_at", "")
        ok = b.get("ok", 0)
        fail = b.get("fail", 0)
        total = b.get("total", 0)
        plugin = b.get("plugin") or "peel_data"
        return f"[{plugin}] 批次 {short}… · {last}  · {ok}/{total} 成功  · {fail} 失败"

    # --- 详情 ---
    def _on_batch_selected(self):
        item = self._batch_list.currentItem()
        if not item:
            self._current_request_id = None
            self._pending_detail_request_id = None
            return
        batch = item.data(Qt.ItemDataRole.UserRole)
        self._current_request_id = batch.get("request_id")
        self._show_batch_summary(batch)
        self._detail_table.setRowCount(0)
        self._pending_detail_request_id = self._current_request_id
        QTimer.singleShot(0, lambda b=batch: self._load_detail_deferred(b))

    def _show_batch_summary(self, batch: Dict):
        rid = batch.get("request_id", "")
        short = rid[:8] if rid else "—"
        plugin_name = batch.get("plugin") or "peel_data"
        meta_lines = [
            f"功能块：{plugin_name}",
            f"批次号：{rid}",
            f"起始时间：{batch.get('first_at', '—')}",
            f"结束时间：{batch.get('last_at', '—')}",
        ]
        self._summary.set_summary(
            title=f"[{plugin_name}] 批次 {short}…",
            meta="\n".join(meta_lines),
            total=batch.get("total", 0),
            ok=batch.get("ok", 0),
            fail=batch.get("fail", 0),
            skip=batch.get("skip", 0),
        )

    def _load_detail_deferred(self, batch: Dict):
        rid = batch.get("request_id", "")
        if not rid or rid != self._pending_detail_request_id:
            return
        rows = self._detail_cache.get(rid)
        if rows is None:
            rows = self._fetch_detail_rows(rid)
            self._detail_cache[rid] = rows
        if rid != self._current_request_id:
            return
        self._render_detail_rows(rows)

    def _fetch_detail_rows(self, rid: str) -> List[Dict]:
        """读取当前批次明细。该步骤按需执行，避免历史页首屏一次性渲染大表。"""
        try:
            from plugins.peel_data.models import get_history_table_name
            table = get_history_table_name()
            db = DatabaseManager()
            return db.query_all(
                f'SELECT "file_name", "file_path", "success", "reason", "operation_time", '
                f'COALESCE("plugin", \'peel_data\') AS plugin '
                f'FROM "{table}" WHERE "request_id" = ? '
                f'ORDER BY "operation_time" ASC',
                (rid,),
            ) or []
        except Exception as e:
            logger.error(f"加载批次明细失败: {e}", exc_info=True)
            return []

    def _render_detail_rows(self, rows: List[Dict]):
        self._detail_table.setUpdatesEnabled(False)
        self._detail_table.setSortingEnabled(False)
        self._detail_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            file_name = row.get("file_name", "") or ""
            file_path = row.get("file_path", "") or ""
            success = row.get("success", 0)
            reason = row.get("reason", "") or ""
            op_time = row.get("operation_time", "") or ""

            self._detail_table.setItem(r, 0, QTableWidgetItem(file_name))
            self._detail_table.setItem(r, 1, QTableWidgetItem(file_path))

            result_text = "✓ 成功" if success == 1 else "✗ 失败"
            result_item = QTableWidgetItem(result_text)
            result_item.setData(
                Qt.ItemDataRole.UserRole,
                "ok" if success == 1 else "fail",
            )
            if success == 1:
                result_item.setForeground(Qt.GlobalColor.darkGreen)
            else:
                result_item.setForeground(Qt.GlobalColor.red)
            result_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._detail_table.setItem(r, 2, result_item)

            self._detail_table.setItem(r, 3, QTableWidgetItem(reason))
            self._detail_table.setItem(r, 4, QTableWidgetItem(op_time))
        self._detail_table.setUpdatesEnabled(True)

    def _load_detail(self, batch: Dict):
        """兼容旧调用：立即加载并渲染一个批次。"""
        self._show_batch_summary(batch)
        rows = self._fetch_detail_rows(batch.get("request_id", ""))
        self._render_detail_rows(rows)
