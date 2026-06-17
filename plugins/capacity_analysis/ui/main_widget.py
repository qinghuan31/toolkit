# -*- coding: utf-8 -*-
"""分容数据分析插件 — 主界面

v1.8.0 流程：
1. 选择文件夹 / 选择单个文件
2. 解析 → 显示统计概览 + 异常样本数
3. 一键渲染 JMP 风格分布图（用户选输出目录）
4. 历史记录自动写入 capacity_analysis_extraction_history
"""

from __future__ import annotations

import os
import datetime as _dt
from typing import Optional, List
from dataclasses import asdict

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFileDialog, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QLineEdit, QMessageBox, QProgressBar, QPlainTextEdit,
    QListWidget, QListWidgetItem,
)

from config import config
from core.logger import get_logger
from core.unified_logger import RequestContext
from plugins.capacity_analysis.parser import parse_capacity_file
from plugins.capacity_analysis.analyzer import finalize_result
from plugins.capacity_analysis.models import (
    ensure_distribution_table,
    ensure_history_table,
    AnalysisResult,
)
from plugins.capacity_analysis.report_html import render_distribution_html

logger = get_logger("capacity_analysis.ui")


class AnalyzeWorker(QThread):
    """分容数据分析工作线程"""
    progress = Signal(int, int, str)
    finished = Signal(object)
    log_message = Signal(str, str)

    def __init__(self, file_paths: List[str], batch_id: str = ""):
        super().__init__()
        self._file_paths = file_paths
        self._batch_id = batch_id

    def run(self):
        from core.unified_logger import RequestContext
        request_id = RequestContext.generate_request_id()
        RequestContext.set_request_id(request_id)
        try:
            results: List[AnalysisResult] = []
            total = len(self._file_paths)
            for i, fp in enumerate(self._file_paths, 1):
                self.progress.emit(i, total, f"正在解析: {os.path.basename(fp)}")
                result = parse_capacity_file(fp)
                if not self._batch_id and result.batch_id:
                    result.batch_id = self._batch_id or result.batch_id
                finalize_result(result)
                self._save_history(result, request_id)
                results.append(result)
            self.finished.emit({"results": results, "request_id": request_id})
        except Exception as e:
            logger.error(f"分析线程异常: {e}", exc_info=True)
            self.finished.emit(None)
        finally:
            RequestContext.clear()

    def _save_history(self, result: AnalysisResult, request_id: str):
        try:
            from core.database import DatabaseManager
            ensure_history_table()
            db = DatabaseManager()
            db.execute(
                f'INSERT OR IGNORE INTO "capacity_analysis_extraction_history" '
                '("file_path", "file_name", "success", "reason", "request_id", "plugin", "operation_time") '
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (result.source_file, os.path.basename(result.source_file), 1,
                 result.summary(), request_id, "capacity_analysis",
                 _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )
        except Exception as e:
            logger.error(f"保存分容历史失败: {e}", exc_info=True)


class CapacityAnalysisWidget(QWidget):
    """分容数据分析插件主界面"""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("capacity_analysis_widget")
        self._last_results: List[AnalysisResult] = []
        self._setup_ui()
        self._restore_last_dir()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(12)

        # 顶部标题
        title_box = QVBoxLayout()
        title = QLabel("分容数据统计分析")
        title.setObjectName("page_title")
        subtitle = QLabel("选择精捷能分容柜导出的 Excel/CSV，一键生成 JMP 风格交互报告（HTML 内置 Y轴参数设置 + 直方图间距调节 + 导出图片）。")
        subtitle.setObjectName("page_desc")
        subtitle.setWordWrap(True)
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        root.addLayout(title_box)

        # 文件选择区
        file_box = QGroupBox("1. 选择数据文件")
        file_box.setObjectName("flat_group")
        fl = QHBoxLayout(file_box)
        fl.setContentsMargins(14, 12, 14, 12)
        fl.setSpacing(8)

        self._file_edit = QLineEdit()
        self._file_edit.setPlaceholderText("点击右侧按钮选择文件（可多选）或选择整个文件夹")
        self._file_edit.setReadOnly(True)
        fl.addWidget(self._file_edit, stretch=1)

        self._btn_pick_files = QPushButton("选择文件")
        self._btn_pick_files.setObjectName("btn_secondary")
        self._btn_pick_files.clicked.connect(self._on_pick_files)
        fl.addWidget(self._btn_pick_files)

        self._btn_pick_dir = QPushButton("选择文件夹")
        self._btn_pick_dir.setObjectName("btn_secondary")
        self._btn_pick_dir.clicked.connect(self._on_pick_dir)
        fl.addWidget(self._btn_pick_dir)

        self._btn_analyze = QPushButton("开始分析")
        self._btn_analyze.setObjectName("btn_primary")
        self._btn_analyze.clicked.connect(self._on_analyze)
        fl.addWidget(self._btn_analyze)
        root.addWidget(file_box)

        # 进度条
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        # 状态 / 日志
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(200)
        self._log.setObjectName("log_view")
        self._log.setPlaceholderText("分析进度与状态会在这里显示…")
        root.addWidget(self._log, stretch=1)

        # 统计概览
        stats_box = QGroupBox("2. 统计概览")
        stats_box.setObjectName("flat_group")
        sg = QVBoxLayout(stats_box)
        sg.setContentsMargins(14, 12, 14, 12)
        sg.setSpacing(6)

        self._stats_labels = {}
        for key, label in [
            ("count", "样本数"),
            ("mean", "均值 (mAh)"),
            ("std_dev", "标准差"),
            ("min_v", "最小值"),
            ("max_v", "最大值"),
            ("median", "中位数"),
            ("q1", "Q1"),
            ("q3", "Q3"),
            ("ci95", "95% 置信区间"),
            ("abnormal", "剔除异常样本"),
        ]:
            row = QHBoxLayout()
            lbl_name = QLabel(label + "：")
            lbl_name.setMinimumWidth(110)
            lbl_value = QLabel("—")
            lbl_value.setObjectName("stat_value")
            row.addWidget(lbl_name)
            row.addWidget(lbl_value, stretch=1)
            sg.addLayout(row)
            self._stats_labels[key] = lbl_value
        root.addWidget(stats_box)

        # 异常样本 + 出图
        out_box = QHBoxLayout()
        self._btn_show_abnormal = QPushButton("查看异常样本")
        self._btn_show_abnormal.setObjectName("btn_secondary")
        self._btn_show_abnormal.clicked.connect(self._on_show_abnormal)
        self._btn_show_abnormal.setEnabled(False)
        out_box.addWidget(self._btn_show_abnormal)

        out_box.addStretch()

        self._btn_plot = QPushButton("生成交互报告 HTML")
        self._btn_plot.setObjectName("btn_success")
        self._btn_plot.clicked.connect(self._on_plot)
        self._btn_plot.setEnabled(False)
        out_box.addWidget(self._btn_plot)
        root.addLayout(out_box)

    def _restore_last_dir(self):
        last = getattr(config, "last_data_dir", "") or ""
        if last:
            self._log.appendPlainText(f"上次数据目录: {last}")

    def _on_pick_files(self):
        last = getattr(config, "last_data_dir", "") or ""
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择分容数据文件", last,
            "分容数据 (*.xlsx *.xls *.xlsm *.xlsb *.csv);;所有文件 (*.*)"
        )
        if not files:
            return
        self._file_edit.setText("; ".join(files))
        self._log.appendPlainText(f"已选择 {len(files)} 个文件")

    def _on_pick_dir(self):
        last = getattr(config, "last_data_dir", "") or ""
        d = QFileDialog.getExistingDirectory(self, "选择分容数据目录", last)
        if not d:
            return
        config.last_data_dir = d
        try:
            config.save()
        except Exception:
            pass
        files = []
        for root, _, names in os.walk(d):
            for n in names:
                ext = os.path.splitext(n)[1].lower()
                if ext in (".xlsx", ".xls", ".xlsm", ".xlsb", ".csv"):
                    files.append(os.path.join(root, n))
        if not files:
            QMessageBox.warning(self, "提示", f"目录 {d} 中没有可处理的文件")
            return
        self._file_edit.setText("; ".join(files))
        self._log.appendPlainText(f"已选择目录 {d}，共 {len(files)} 个文件")

    def _on_analyze(self):
        text = self._file_edit.text().strip()
        if not text:
            QMessageBox.warning(self, "提示", "请先选择文件或文件夹")
            return
        files = [f.strip() for f in text.split(";") if f.strip()]
        if not files:
            return
        self._progress.setVisible(True)
        self._progress.setRange(0, 0)
        self._btn_analyze.setEnabled(False)
        self._btn_plot.setEnabled(False)
        self._btn_show_abnormal.setEnabled(False)
        self._log.appendPlainText(f"开始分析 {len(files)} 个文件…")
        self._worker = AnalyzeWorker(files)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.log_message.connect(self._log.appendPlainText)
        self._worker.start()

    def _on_progress(self, current: int, total: int, message: str):
        self._progress.setRange(0, total)
        self._progress.setValue(current)
        self._log.appendPlainText(f"[{current}/{total}] {message}")

    def _on_finished(self, payload):
        self._progress.setVisible(False)
        self._btn_analyze.setEnabled(True)
        if not payload:
            QMessageBox.critical(self, "分析失败", "分析过程中发生异常，请查看日志")
            return
        results = payload.get("results", [])
        self._last_results = results
        if not results:
            self._log.appendPlainText("没有产生结果")
            return
        # 聚合：取第一个（多文件场景下 v1.8.1 再支持合并）
        r = results[0]
        s = r.stats
        self._stats_labels["count"].setText(str(s.count))
        self._stats_labels["mean"].setText(f"{s.mean:.4f}")
        self._stats_labels["std_dev"].setText(f"{s.std_dev:.4f}")
        self._stats_labels["min_v"].setText(f"{s.min_v:.4f}")
        self._stats_labels["max_v"].setText(f"{s.max_v:.4f}")
        self._stats_labels["median"].setText(f"{s.median:.4f}")
        self._stats_labels["q1"].setText(f"{s.q1:.4f}")
        self._stats_labels["q3"].setText(f"{s.q3:.4f}")
        self._stats_labels["ci95"].setText(f"[{s.ci95_lower:.4f}, {s.ci95_upper:.4f}]")
        total_abn = sum(len(v) for v in r.abnormal.values())
        abn_text = f"{total_abn} 块" if total_abn else "0 块"
        if r.abnormal:
            abn_text += "（" + "、".join(
                f"{k}: {len(v)}" for k, v in r.abnormal.items() if v
            ) + "）"
        self._stats_labels["abnormal"].setText(abn_text)
        self._log.appendPlainText(r.summary())
        self._log.appendPlainText(f"请求 ID: {payload.get('request_id', '')}")
        self._btn_plot.setEnabled(True)
        self._btn_show_abnormal.setEnabled(total_abn > 0)

    def _on_show_abnormal(self):
        if not self._last_results:
            return
        r = self._last_results[0]
        lines = []
        for k, items in r.abnormal.items():
            if not items:
                continue
            lines.append(f"【{k}】共 {len(items)} 块")
            for it in items[:20]:
                lines.append(f"  - 行 {it.get('row', '?')}: {it.get('cell_id', '?')}")
            if len(items) > 20:
                lines.append(f"  ... 还有 {len(items) - 20} 个")
        if not lines:
            QMessageBox.information(self, "异常样本", "没有异常样本")
            return
        QMessageBox.information(self, "异常样本明细", "\n".join(lines))

    def _on_plot(self):
        if not self._last_results:
            return
        r = self._last_results[0]
        out_dir = QFileDialog.getExistingDirectory(self, "选择分布图输出目录",
                                                  getattr(config, "last_data_dir", ""))
        if not out_dir:
            return
        ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = os.path.join(out_dir, f"{r.batch_id}_{ts}_distribution_report.html")
        try:
            saved = render_distribution_html(r, out_path)
            if saved:
                self._log.appendPlainText(f"交互报告已生成: {saved}")
                QMessageBox.information(
                    self,
                    "完成",
                    "交互报告已保存到:\n"
                    f"{saved}\n\n"
                    "打开 HTML 后可用滑块调节直方图柱间距，并点击“导出图片”保存 PNG。",
                )
            else:
                QMessageBox.critical(self, "失败", "交互报告生成失败（没有有效数据？）")
        except Exception as e:
            logger.error(f"生成交互报告失败: {e}", exc_info=True)
            QMessageBox.critical(self, "失败", f"生成交互报告失败: {e}")
