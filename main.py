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
# 数据库路径：项目根目录下的 data/app.db
_DB_PATH = os.path.join(PROJECT_ROOT, "data", "app.db")
_OLD_DB_PATH = os.path.join(PROJECT_ROOT, "data", "toolkit.db")
# 【v1.7.0】自动迁移：toolkit.db → app.db（静默，零数据丢失）
if not os.path.exists(_DB_PATH) and os.path.exists(_OLD_DB_PATH):
    os.rename(_OLD_DB_PATH, _DB_PATH)
    # 同步更新 app_config.json 中的旧路径（防止 config.load() 覆盖回来）
    _cfg_file = os.path.join(PROJECT_ROOT, "data", "app_config.json")
    if os.path.isfile(_cfg_file):
        import json
        with open(_cfg_file, "r", encoding="utf-8") as f:
            _data = json.load(f)
        if isinstance(_data.get("db"), dict) and "toolkit.db" in str(_data["db"].get("database_path", "")):
            _data["db"]["database_path"] = _DB_PATH
            with open(_cfg_file, "w", encoding="utf-8") as f:
                json.dump(_data, f, ensure_ascii=False, indent=2)
_config.config.db.database_path = _DB_PATH

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

    # 【v1.6.0】根据 network_mode 决定是否启动 DB server
    if _config.config.db.network_mode == "server":
        try:
            from core.db_server import start_server_in_thread
            start_server_in_thread()
            print(f"[DB Server] listening on http://{_config.config.db.server_host}:{_config.config.db.server_port}")
        except Exception as e:
            print(f"[DB Server] startup failed: {e}")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
