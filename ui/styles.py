# -*- coding: utf-8 -*-
"""
QSS 样式表
"""

LIGHT_STYLE = """
/* ========== 全局 ========== */
QWidget {
    font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 13px;
    color: #1a1a1a;
    background-color: #f5f6f7;
}

/* ========== 主窗口 ========== */
QMainWindow {
    background-color: #f5f6f7;
}

/* ========== 侧边栏 ========== */
#sidebar {
    background-color: #2c3e50;
    border: none;
    min-width: 200px;
    max-width: 200px;
}

#sidebar QLabel {
    color: #ecf0f1;
    font-size: 16px;
    font-weight: bold;
    padding: 20px 16px 12px 16px;
    background: transparent;
}

#sidebar QPushButton {
    background-color: transparent;
    color: #bdc3c7;
    border: none;
    text-align: left;
    padding: 12px 20px;
    font-size: 14px;
    border-left: 3px solid transparent;
}

#sidebar QPushButton:hover {
    background-color: #34495e;
    color: #ecf0f1;
}

#sidebar QPushButton:checked {
    background-color: #1a252f;
    color: #3498db;
    border-left: 3px solid #3498db;
    font-weight: bold;
}

/* ========== 内容区域 ========== */
#content_area {
    background-color: #f5f6f7;
    border: none;
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
    background-color: #409eff;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 8px 20px;
    font-size: 13px;
    min-height: 32px;
}

QPushButton:hover {
    background-color: #66b1ff;
}

QPushButton:pressed {
    background-color: #3a8ee6;
}

QPushButton:disabled {
    background-color: #a0cfff;
    color: #ffffff;
}

QPushButton#btn_danger {
    background-color: #f56c6c;
}

QPushButton#btn_danger:hover {
    background-color: #f78989;
}

QPushButton#btn_success {
    background-color: #67c23a;
}

QPushButton#btn_success:hover {
    background-color: #85ce61;
}

QPushButton#btn_warning {
    background-color: #e6a23c;
}

QPushButton#btn_warning:hover {
    background-color: #ebb563;
}

QPushButton#btn_secondary {
    background-color: #909399;
    color: white;
}

QPushButton#btn_secondary:hover {
    background-color: #a6a9ad;
}

QPushButton#btn_open_path {
    background-color: #6b7280;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 4px 10px;
    font-size: 12px;
}

QPushButton#btn_open_path:hover {
    background-color: #4b5563;
}

/* ========== 输入框 ========== */
QLineEdit, QSpinBox {
    border: 1px solid #dcdfe6;
    border-radius: 4px;
    padding: 6px 10px;
    background-color: #ffffff;
    min-height: 28px;
}

QLineEdit:focus, QSpinBox:focus {
    border-color: #409eff;
}

/* ========== 下拉框 ========== */
QComboBox {
    border: 1px solid #dcdfe6;
    border-radius: 4px;
    padding: 6px 10px;
    background-color: #ffffff;
    min-height: 28px;
}

QComboBox:hover {
    border-color: #c0c4cc;
}

QComboBox::drop-down {
    border: none;
    width: 30px;
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
