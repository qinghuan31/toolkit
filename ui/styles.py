# -*- coding: utf-8 -*-
"""
QSS 样式表
v1.7.1: 增强主样式 + 新增 SETTINGS_DIALOG_STYLE(综合设置对话框专用)
"""

# ═══════════════════════════════════════════════════════════
#  综合设置对话框专用样式(独立常量,便于单独覆盖)
# ═══════════════════════════════════════════════════════════
SETTINGS_DIALOG_STYLE = """
/* ========== 对话框整体 ========== */
QDialog {
    background-color: #f6f7f9;
    font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 13px;
    color: #1f2937;
}

/* ========== 标题与未保存角标 ========== */
QLabel#title_label {
    font-size: 18px;
    font-weight: 700;
    color: #1f2937;
    letter-spacing: 0.3px;
}

QLabel#dirty_badge {
    background-color: #fef3c7;
    color: #92400e;
    font-size: 12px;
    font-weight: 600;
    border: 1px solid #fcd34d;
    border-radius: 10px;
    padding: 2px 10px;
    margin-left: 8px;
}

QLabel#dirty_badge[state="dirty"] {
    background-color: #fef3c7;
    color: #92400e;
    border: 1px solid #fcd34d;
}

/* ========== 提示文字(状态行/小字) ========== */
QLabel#hint_label {
    color: #6b7280;
    font-size: 12px;
}
QLabel#hint_label[state="info"]    { color: #6b7280; }
QLabel#hint_label[state="warning"] { color: #b45309; font-weight: 600; }
QLabel#hint_label[state="success"] { color: #047857; font-weight: 600; }
QLabel#hint_label[state="danger"]  { color: #b91c1c; font-weight: 600; }

QLabel#onboarding_hint {
    background-color: #eef2ff;
    color: #3730a3;
    border: 1px solid #c7d2fe;
    border-radius: 8px;
    padding: 10px 12px;
    font-size: 12px;
    font-weight: 600;
}

QLabel#main_guide {
    background-color: #eff6ff;
    color: #1d4ed8;
    border: 1px solid #bfdbfe;
    border-radius: 8px;
    padding: 10px 12px;
    font-size: 12px;
    font-weight: 600;
}

/* ========== 分组框 ========== */
QGroupBox {
    font-weight: 600;
    font-size: 13px;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    margin-top: 14px;
    padding: 18px 14px 14px 14px;
    background-color: #ffffff;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 10px;
    color: #1f2937;
    background-color: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 4px;
}

/* ========== 输入控件 ========== */
QLineEdit, QSpinBox, QComboBox {
    border: 1px solid #d1d5db;
    border-radius: 6px;
    padding: 7px 12px;
    background-color: #ffffff;
    min-height: 30px;
    selection-background-color: #dbeafe;
    selection-color: #1e3a8a;
}
QLineEdit:hover, QSpinBox:hover, QComboBox:hover {
    border-color: #9ca3af;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
    border: 2px solid #3b82f6;
    padding: 6px 11px;     /* 边粗 +1,内边距 -1,避免抖动 */
}
QComboBox::drop-down {
    border: none;
    width: 28px;
}
QComboBox QAbstractItemView {
    border: 1px solid #d1d5db;
    background-color: #ffffff;
    selection-background-color: #dbeafe;
    selection-color: #1e3a8a;
    padding: 4px;
    outline: 0;
}

QTextEdit {
    border: 1px solid #d1d5db;
    border-radius: 6px;
    padding: 8px;
    background-color: #fafafa;
    font-family: "Consolas", "Cascadia Mono", "Microsoft YaHei", monospace;
    font-size: 12px;
    color: #1f2937;
}
QTextEdit:focus { border: 2px solid #3b82f6; padding: 7px; }

/* ========== 复选框 ========== */
QCheckBox {
    spacing: 8px;
    color: #374151;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: 1.5px solid #d1d5db;
    background: #ffffff;
}
QCheckBox::indicator:hover { border-color: #6b7280; }
QCheckBox::indicator:checked {
    background-color: #3b82f6;
    border-color: #3b82f6;
    image: none;
}

/* ========== 按钮 ========== */
QPushButton {
    background-color: #f3f4f6;
    color: #1f2937;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    padding: 7px 16px;
    font-size: 13px;
    min-height: 30px;
    font-weight: 500;
}
QPushButton:hover { background-color: #e5e7eb; }
QPushButton:pressed { background-color: #d1d5db; }
QPushButton:disabled {
    color: #9ca3af;
    background-color: #f9fafb;
    border-color: #e5e7eb;
}

QPushButton#btn_primary {
    background-color: #3b82f6;
    color: white;
    border: 1px solid #3b82f6;
}
QPushButton#btn_primary:hover { background-color: #2563eb; border-color: #2563eb; }
QPushButton#btn_primary:pressed { background-color: #1d4ed8; }
QPushButton#btn_primary:disabled {
    background-color: #93c5fd;
    border-color: #93c5fd;
    color: #f9fafb;
}

QPushButton#btn_success {
    background-color: #10b981;
    color: white;
    border: 1px solid #10b981;
}
QPushButton#btn_success:hover { background-color: #059669; border-color: #059669; }

QPushButton#btn_warning {
    background-color: #f59e0b;
    color: white;
    border: 1px solid #f59e0b;
}
QPushButton#btn_warning:hover { background-color: #d97706; border-color: #d97706; }

QPushButton#btn_secondary {
    background-color: #ffffff;
    color: #374151;
    border: 1px solid #d1d5db;
}
QPushButton#btn_secondary:hover { background-color: #f3f4f6; }

/* ========== 设备列表 ========== */
QListWidget#device_list {
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    background-color: #ffffff;
    font-size: 13px;
    outline: 0;
}
QListWidget#device_list::item {
    padding: 8px 12px;
    border-bottom: 1px solid #f3f4f6;
}
QListWidget#device_list::item:hover {
    background-color: #f9fafb;
}
QListWidget#device_list::item:selected {
    background-color: #dbeafe;
    color: #1e3a8a;
}

/* ========== 标签页 ========== */
QTabWidget::pane {
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    background: #ffffff;
    margin-top: -1px;
}
QTabBar::tab {
    background: #f3f4f6;
    border: 1px solid #e5e7eb;
    padding: 8px 18px;
    margin-right: 4px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    color: #6b7280;
    font-size: 13px;
}
QTabBar::tab:selected {
    background: #ffffff;
    border-bottom-color: #ffffff;
    color: #1f2937;
    font-weight: 600;
}
QTabBar::tab:hover:!selected {
    background: #e5e7eb;
    color: #374151;
}

/* ========== 滚动条 ========== */
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: #d1d5db;
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover { background: #9ca3af; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""

# ═══════════════════════════════════════════════════════════
#  主窗口 / 通用组件样式(沿用 v1.7.0,做了一轮小润色)
# ═══════════════════════════════════════════════════════════
LIGHT_STYLE = """
/* ========== 全局 ========== */
QWidget {
    font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 13px;
    color: #1f2937;
    background-color: #f5f6f7;
}

/* ========== 主窗口 ========== */
QMainWindow {
    background-color: #f5f6f7;
}

/* ========== 侧边栏 ========== */
#sidebar {
    background-color: #172033;
    border: none;
    min-width: 204px;
    max-width: 204px;
}

#sidebar QLabel {
    color: #f3f4f6;
    font-size: 16px;
    font-weight: 700;
    padding: 22px 16px 14px 16px;
    background: transparent;
    letter-spacing: 0.5px;
}

#sidebar QPushButton {
    background-color: transparent;
    color: #cbd5e1;
    border: none;
    text-align: left;
    padding: 12px 20px;
    font-size: 14px;
    border-left: 3px solid transparent;
    font-weight: 500;
}
#sidebar QPushButton:hover {
    background-color: #374151;
    color: #f3f4f6;
}
#sidebar QPushButton:checked {
    background-color: #111827;
    color: #60a5fa;
    border-left: 3px solid #60a5fa;
    font-weight: 600;
}

/* ========== 内容区域 ========== */
#content_area {
    background-color: #f5f6f7;
    border: none;
}

QLabel#onboarding_hint {
    background-color: #eef2ff;
    color: #3730a3;
    border: 1px solid #c7d2fe;
    border-radius: 8px;
    padding: 10px 12px;
    font-size: 12px;
    font-weight: 600;
}

/* ========== 分组框 ========== */
QGroupBox {
    font-weight: bold;
    font-size: 13px;
    border: 1px solid #dcdfe6;
    border-radius: 6px;
    margin-top: 12px;
    padding: 16px 12px 12px 12px;
    background-color: #ffffff;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 10px;
    color: #303133;
}

/* 无标题扁平分组框 */
QGroupBox#flat_group {
    border: 1px solid #e4e7ed;
    border-radius: 6px;
    margin-top: 0px;
    padding: 12px;
    background-color: #ffffff;
}

QGroupBox#flat_group::title {
    display: none;
}

/* ========== 按钮 ========== */
QPushButton {
    background-color: #3b82f6;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 18px;
    font-size: 13px;
    min-height: 30px;
    font-weight: 500;
}
QPushButton:hover { background-color: #2563eb; }
QPushButton:pressed { background-color: #1d4ed8; }
QPushButton:disabled { background-color: #93c5fd; color: #ffffff; }

QPushButton#btn_danger {
    background-color: #ef4444;
}
QPushButton#btn_danger:hover { background-color: #dc2626; }

QPushButton#btn_success {
    background-color: #10b981;
}
QPushButton#btn_success:hover { background-color: #059669; }

QPushButton#btn_warning {
    background-color: #f59e0b;
}
QPushButton#btn_warning:hover { background-color: #d97706; }

QPushButton#btn_secondary {
    background-color: #ffffff;
    color: #374151;
    border: 1px solid #d1d5db;
}
QPushButton#btn_secondary:hover { background-color: #f3f4f6; }

QPushButton#btn_open_path {
    background-color: #6b7280;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 4px 10px;
    font-size: 12px;
}
QPushButton#btn_open_path:hover { background-color: #4b5563; }

/* ========== 输入框 ========== */
QLineEdit, QSpinBox {
    border: 1px solid #d1d5db;
    border-radius: 6px;
    padding: 6px 10px;
    background-color: #ffffff;
    min-height: 28px;
    selection-background-color: #dbeafe;
    selection-color: #1e3a8a;
}
QLineEdit:hover, QSpinBox:hover { border-color: #9ca3af; }
QLineEdit:focus, QSpinBox:focus {
    border: 2px solid #3b82f6;
    padding: 5px 9px;   /* 边粗 +1,内边距 -1,避免抖动 */
}

/* ========== 下拉框 ========== */
QComboBox {
    border: 1px solid #d1d5db;
    border-radius: 6px;
    padding: 6px 10px;
    background-color: #ffffff;
    min-height: 28px;
}
QComboBox:hover { border-color: #9ca3af; }
QComboBox::drop-down {
    border: none;
    width: 28px;
}

/* ========== 表格 ========== */
QTableWidget {
    background-color: #ffffff;
    alternate-background-color: #fafafa;
    gridline-color: #ebeef5;
    border: 1px solid #ebeef5;
    border-radius: 4px;
    selection-background-color: #fef3c7;
    selection-color: #92400e;
}

QTableWidget::item {
    padding: 6px 10px;
    border-bottom: 1px solid #ebeef5;
}

QTableWidget::item:hover {
    background-color: #f5f7fa;
}

QHeaderView::section {
    background-color: #f5f7fa;
    color: #606266;
    font-weight: bold;
    padding: 8px 10px;
    border: none;
    border-bottom: 2px solid #dcdfe6;
    border-right: 1px solid #ebeef5;
}

/* ========== 进度条 ========== */
QProgressBar {
    border: none;
    border-radius: 4px;
    background-color: #ebeef5;
    height: 8px;
    text-align: center;
    color: transparent;
}

QProgressBar::chunk {
    background-color: #409eff;
    border-radius: 4px;
}

/* ========== 状态栏 ========== */
QStatusBar {
    background-color: #ffffff;
    border-top: 1px solid #ebeef5;
    color: #909399;
    font-size: 12px;
    padding: 4px 8px;
}

/* ========== 滚动条 ========== */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background: #c0c4cc;
    border-radius: 4px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background: #909399;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal {
    background: #c0c4cc;
    border-radius: 4px;
    min-width: 30px;
}

QScrollBar::handle:horizontal:hover {
    background: #909399;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* ========== 标签页 ========== */
QTabWidget::pane {
    border: 1px solid #dcdfe6;
    border-radius: 4px;
    background: #ffffff;
}

QTabBar::tab {
    background: #f5f7fa;
    border: 1px solid #dcdfe6;
    padding: 8px 16px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}

QTabBar::tab:selected {
    background: #ffffff;
    border-bottom-color: #ffffff;
    color: #409eff;
    font-weight: bold;
}

QTabBar::tab:hover:!selected {
    background: #ecf5ff;
}

/* ========== 文本编辑框 ========== */
QTextEdit, QPlainTextEdit {
    border: 1px solid #dcdfe6;
    border-radius: 4px;
    padding: 6px;
    background-color: #ffffff;
    font-family: "Consolas", "Microsoft YaHei", monospace;
    font-size: 12px;
}

QTextEdit:focus, QPlainTextEdit:focus {
    border-color: #409eff;
}

/* ========== 标签 ========== */
QLabel#status_label {
    color: #909399;
    font-size: 12px;
}

QLabel#title_label {
    font-size: 18px;
    font-weight: bold;
    color: #303133;
}

/* ========== 复选框 ========== */
QCheckBox {
    spacing: 8px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: 1px solid #dcdfe6;
    background: #ffffff;
}

QCheckBox::indicator:checked {
    background-color: #409eff;
    border-color: #409eff;
}
"""
