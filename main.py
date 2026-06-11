# -*- coding: utf-8 -*-
"""
工具集 (Toolkit) —— 主入口
模块化 Windows 桌面 Toolkit
"""

import sys
import os

# 将项目根目录加入 Python 路径
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# 日志目录：项目根目录下的 logs/
import config as _config
_config.config.log_dir = os.path.join(PROJECT_ROOT, "logs")
# 数据库路径：项目根目录下的 data/toolkit.db
_config.config.db.database_path = os.path.join(PROJECT_ROOT, "data", "toolkit.db")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from ui.main_window import MainWindow


def main():
    # 高 DPI 支持
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Toolkit")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("WorkBuddy")

    # 设置应用图标（优先 .ico，回退 .png）
    icon_path_ico = os.path.join(PROJECT_ROOT, "resources", "app_icon.ico")
    icon_path_png = os.path.join(PROJECT_ROOT, "resources", "app_icon_512.png")
    if os.path.exists(icon_path_ico):
        app.setWindowIcon(QIcon(icon_path_ico))
    elif os.path.exists(icon_path_png):
        app.setWindowIcon(QIcon(icon_path_png))

    # Windows 任务栏图标修正：设置 AppUserModelID
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("DNTL.Toolkit")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
