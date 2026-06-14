# -*- coding: utf-8 -*-
"""
综合设置界面
包含：局域网多设备配置、peel_data 插件参数、配置导入导出
v1.7.1 改版：底部统一"保存/放弃"按钮，顶部显示"未保存"标记，配置项变更不再实时落盘
"""

import os
import json
import socket
from typing import Optional, Dict, List, Tuple

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QPushButton, QLineEdit, QSpinBox, QComboBox,
    QGroupBox, QFormLayout, QFileDialog, QMessageBox,
    QTextEdit, QGridLayout, QSizePolicy, QCheckBox,
    QListWidget, QListWidgetItem, QFrame, QSpacerItem,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont

from config import config
from core.logger import get_logger
from ui.styles import SETTINGS_DIALOG_STYLE

logger = get_logger("settings")


# ═══════════════════════════════════════════════════════════
#  辅助：脏值追踪基类
# ═══════════════════════════════════════════════════════════

class _DirtyTrackerMixin:
    """
    给任意 QWidget 增加脏值追踪能力：
    - 任何被注册过的子控件变化都把父对象 (SettingsDialog) 的 _dirty 设为 True
    - 顶层 QDialog 在收到这个信号后切换"未保存"角标并启用"保存"按钮
    """

    def __init__(self, host: "SettingsDialog" = None, *args, **kwargs):
        self._host = host
        self._tracked_widgets: List[QWidget] = []

    def _track(self, *widgets: QWidget) -> None:
        """注册需要追踪脏值的控件"""
        for w in widgets:
            if w is None:
                continue
            self._tracked_widgets.append(w)
            self._wire_dirty(w)

    def _wire_dirty(self, w: QWidget) -> None:
        if isinstance(w, QLineEdit):
            w.textChanged.connect(self._mark_dirty)
        elif isinstance(w, QSpinBox):
            w.valueChanged.connect(self._mark_dirty)
        elif isinstance(w, QComboBox):
            w.currentIndexChanged.connect(self._mark_dirty)
        elif isinstance(w, QCheckBox):
            w.stateChanged.connect(self._mark_dirty)

    def _mark_dirty(self, *_args) -> None:
        self._host._set_dirty(True)


# ═══════════════════════════════════════════════════════════
#  网络连接测试工作线程
# ═══════════════════════════════════════════════════════════

class _NetworkTestWorker(QThread):
    """测试 DB server 连接（后台线程，避免阻塞 UI）"""
    result = Signal(bool, str)

    def __init__(self, url: str, timeout: float = 3.0):
        super().__init__()
        self._url = url.rstrip("/")
        self._timeout = timeout

    def run(self):
        try:
            from urllib.request import urlopen, Request
            from urllib.error import URLError
            req = Request(f"{self._url}/api/health", method="GET")
            with urlopen(req, timeout=self._timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("status") == "ok":
                    self.result.emit(True, f"连接成功 — 端口 {data.get('port', '?')}")
                else:
                    self.result.emit(False, f"服务器返回异常: {data}")
        except Exception as e:
            self.result.emit(False, f"连接失败: {e}")


# ═══════════════════════════════════════════════════════════
#  局域网多设备配置 Tab
# ═══════════════════════════════════════════════════════════

class _NetworkTab(QWidget, _DirtyTrackerMixin):
    """局域网多设备访问配置"""

    def __init__(self, host: "SettingsDialog", parent=None):
        QWidget.__init__(self, parent)
        _DirtyTrackerMixin.__init__(self, host)
        self._test_worker: Optional[_NetworkTestWorker] = None
        self._scan_worker: Optional[QThread] = None
        self._initial: Dict[str, object] = {}
        self._setup_ui()
        self._load_current()
        self._capture_initial()
        self._track(
            self._mode_combo, self._host_edit, self._port_spin,
            self._token_edit, self._server_url_edit,
            self._client_token_edit, self._allow_write_check,
        )

    # --- UI 构造 ---
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)

        # === 模式选择 ===
        mode_group = QGroupBox("网络模式")
        mode_layout = QFormLayout(mode_group)
        mode_layout.setSpacing(10)
        mode_layout.setContentsMargins(16, 20, 16, 16)

        self._mode_combo = QComboBox()
        self._mode_combo.setMinimumWidth(420)
        self._mode_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self._mode_combo.addItems([
            "local  — 仅本机（默认）",
            "server — 作为服务端，局域网其他设备可连接",
            "client — 作为客户端，连接到局域网服务端",
        ])
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_layout.addRow("工作模式：", self._mode_combo)

        self._mode_hint = QLabel()
        self._mode_hint.setWordWrap(True)
        self._mode_hint.setObjectName("hint_label")
        mode_layout.addRow("", self._mode_hint)
        layout.addWidget(mode_group)

        # === Server 配置 ===
        self._server_group = QGroupBox("服务端配置")
        server_layout = QFormLayout(self._server_group)
        server_layout.setSpacing(10)
        server_layout.setContentsMargins(16, 20, 16, 16)

        host_row = QHBoxLayout()
        host_row.setSpacing(8)
        host_row.setContentsMargins(0, 0, 0, 0)
        self._host_edit = QLineEdit()
        self._host_edit.setMinimumWidth(360)
        self._host_edit.setPlaceholderText("本机局域网 IP / 0.0.0.0 监听所有网卡")
        host_row.addWidget(self._host_edit)
        btn_detect_ip = QPushButton("自动检测")
        btn_detect_ip.setObjectName("btn_secondary")
        btn_detect_ip.setFixedWidth(80)
        btn_detect_ip.setToolTip("自动获取本机局域网 IP")
        btn_detect_ip.clicked.connect(self._on_detect_local_ip)
        host_row.addWidget(btn_detect_ip)
        server_layout.addRow("监听地址：", host_row)

        self._port_spin = QSpinBox()
        self._port_spin.setRange(1024, 65535)
        self._port_spin.setValue(8765)
        server_layout.addRow("端口：", self._port_spin)

        token_row = QHBoxLayout()
        token_row.setSpacing(8)
        token_row.setContentsMargins(0, 0, 0, 0)
        self._token_edit = QLineEdit()
        self._token_edit.setMinimumWidth(360)
        self._token_edit.setPlaceholderText("留空则无鉴权（建议内部使用时设置）")
        self._token_edit.setEchoMode(QLineEdit.EchoMode.Normal)
        token_row.addWidget(self._token_edit)
        btn_copy_token = QPushButton("📋 复制")
        btn_copy_token.setObjectName("btn_secondary")
        btn_copy_token.setFixedWidth(70)
        btn_copy_token.setToolTip("复制 Token 到剪贴板")
        btn_copy_token.clicked.connect(lambda: self._on_copy_field(self._token_edit))
        token_row.addWidget(btn_copy_token)
        btn_gen_token = QPushButton("自动生成")
        btn_gen_token.setObjectName("btn_secondary")
        btn_gen_token.setFixedWidth(80)
        btn_gen_token.clicked.connect(self._on_generate_token)
        token_row.addWidget(btn_gen_token)
        server_layout.addRow("API Token：", token_row)

        self._allow_write_check = QCheckBox("允许客户端写入数据库")
        self._allow_write_check.setToolTip(
            "勾选：客户端可读可写（默认）\n"
            "取消：客户端只能查询数据，写入操作会被服务端拒绝（403）\n\n"
            "建议：多人协作时由主机控制写入，避免数据冲突"
        )
        self._allow_write_check.setChecked(True)
        server_layout.addRow("写入权限：", self._allow_write_check)

        layout.addWidget(self._server_group)

        # === Client 配置 ===
        self._client_group = QGroupBox("客户端配置")
        client_layout = QFormLayout(self._client_group)
        client_layout.setSpacing(10)
        client_layout.setContentsMargins(16, 20, 16, 16)

        self._server_url_edit = QLineEdit()
        self._server_url_edit.setPlaceholderText("http://192.168.1.100:8765")
        client_layout.addRow("服务器地址：", self._server_url_edit)

        client_token_row = QHBoxLayout()
        self._client_token_edit = QLineEdit()
        self._client_token_edit.setPlaceholderText("与服务端 Token 一致")
        self._client_token_edit.setEchoMode(QLineEdit.EchoMode.Normal)
        client_token_row.addWidget(self._client_token_edit)
        btn_copy_ctoken = QPushButton("📋 复制")
        btn_copy_ctoken.setObjectName("btn_secondary")
        btn_copy_ctoken.setFixedWidth(70)
        btn_copy_ctoken.clicked.connect(lambda: self._on_copy_field(self._client_token_edit))
        client_token_row.addWidget(btn_copy_ctoken)
        btn_paste_ctoken = QPushButton("从剪贴板粘贴")
        btn_paste_ctoken.setObjectName("btn_secondary")
        btn_paste_ctoken.setFixedWidth(110)
        btn_paste_ctoken.clicked.connect(self._on_paste_to_client_token)
        client_token_row.addWidget(btn_paste_ctoken)
        client_layout.addRow("API Token：", client_token_row)

        layout.addWidget(self._client_group)

        # === 设备发现 ===
        discovery_group = QGroupBox("局域网设备发现")
        discovery_layout = QVBoxLayout(discovery_group)
        discovery_layout.setSpacing(10)
        discovery_layout.setContentsMargins(16, 20, 16, 16)

        discovery_btn_row = QHBoxLayout()
        discovery_btn_row.setSpacing(8)
        discovery_btn_row.setContentsMargins(0, 0, 0, 0)
        self._btn_discover = QPushButton("扫描局域网设备")
        self._btn_discover.setObjectName("btn_primary")
        self._btn_discover.setMinimumWidth(140)
        self._btn_discover.clicked.connect(self._on_discover_devices)
        discovery_btn_row.addWidget(self._btn_discover)

        self._btn_pair = QPushButton("配对选中")
        self._btn_pair.setObjectName("btn_success")
        self._btn_pair.setMinimumWidth(100)
        self._btn_pair.setEnabled(False)
        self._btn_pair.clicked.connect(self._on_pair_device)
        discovery_btn_row.addWidget(self._btn_pair)

        self._discovery_status = QLabel("未扫描")
        self._discovery_status.setObjectName("hint_label")
        discovery_btn_row.addWidget(self._discovery_status)
        discovery_btn_row.addStretch()
        discovery_layout.addLayout(discovery_btn_row)

        self._device_list = QListWidget()
        self._device_list.setMinimumHeight(64)
        self._device_list.setMaximumHeight(140)
        self._device_list.setObjectName("device_list")
        self._device_list.itemSelectionChanged.connect(self._on_device_selected)
        discovery_layout.addWidget(self._device_list)

        layout.addWidget(discovery_group)

        # === 连接测试 ===
        test_group = QGroupBox("连接测试")
        test_layout = QHBoxLayout(test_group)
        test_layout.setContentsMargins(16, 20, 16, 16)

        self._btn_test = QPushButton("测试连接")
        self._btn_test.setObjectName("btn_success")
        self._btn_test.setMinimumWidth(100)
        self._btn_test.clicked.connect(self._on_test_connection)
        test_layout.addWidget(self._btn_test)

        self._test_result = QLabel("未测试")
        self._test_result.setObjectName("hint_label")
        test_layout.addWidget(self._test_result)
        test_layout.addStretch()
        layout.addWidget(test_group)

        layout.addStretch()

    # --- 数据加载与初始快照 ---
    def _load_current(self):
        mode = config.db.network_mode
        idx = {"local": 0, "server": 1, "client": 2}.get(mode, 0)
        self._mode_combo.setCurrentIndex(idx)
        self._host_edit.setText(config.db.server_host)
        self._port_spin.setValue(config.db.server_port)
        self._token_edit.setText(config.db.api_token)
        self._server_url_edit.setText(config.db.server_url)
        self._client_token_edit.setText(config.db.api_token)
        self._allow_write_check.setChecked(config.db.server_allow_write)
        self._on_mode_changed(idx)

    def _capture_initial(self):
        """记录当前界面值，'放弃' 时用来恢复"""
        self._initial = self.collect_values()

    def collect_values(self) -> Dict[str, object]:
        """收集当前界面值，供主对话框统一保存/恢复使用"""
        return {
            "mode_index": self._mode_combo.currentIndex(),
            "host": self._host_edit.text(),
            "port": self._port_spin.value(),
            "server_token": self._token_edit.text(),
            "client_token": self._client_token_edit.text(),
            "server_url": self._server_url_edit.text(),
            "allow_write": self._allow_write_check.isChecked(),
        }

    def apply_values(self, values: Dict[str, object]) -> None:
        """回填到 UI（用于 '放弃' 或 '保存后刷新'）"""
        self._mode_combo.setCurrentIndex(values.get("mode_index", 0))
        self._host_edit.setText(values.get("host", ""))
        self._port_spin.setValue(int(values.get("port", 8765)))
        self._token_edit.setText(values.get("server_token", ""))
        self._client_token_edit.setText(values.get("client_token", ""))
        self._server_url_edit.setText(values.get("server_url", ""))
        self._allow_write_check.setChecked(bool(values.get("allow_write", True)))
        self._on_mode_changed(self._mode_combo.currentIndex())

    def is_dirty(self) -> bool:
        """判断当前 Tab 相对初始快照是否被改动"""
        if not self._initial:
            return False
        return self.collect_values() != self._initial

    # --- 行为 ---
    def _on_mode_changed(self, index: int):
        modes = ["local", "server", "client"]
        mode = modes[index] if index < len(modes) else "local"

        self._server_group.setVisible(mode == "server")
        self._client_group.setVisible(mode == "client")

        hints = {
            "local": "仅本机使用 SQLite 文件，不开启网络服务。适合单设备使用场景。",
            "server": "本机作为服务端，开启 HTTP API。局域网内其他设备可通过客户端模式连接。",
            "client": "本机作为客户端，通过 HTTP 连接到局域网服务端。请确保服务端已启动。",
        }
        self._mode_hint.setText(hints.get(mode, ""))

    def _on_generate_token(self):
        import secrets
        token = secrets.token_urlsafe(32)
        self._token_edit.setText(token)

    def _on_copy_field(self, line_edit):
        from PySide6.QtWidgets import QApplication
        text = line_edit.text()
        if not text:
            QMessageBox.information(self, "提示", "字段为空，无需复制。")
            return
        QApplication.clipboard().setText(text)
        self._discovery_status.setText(f"✓ 已复制到剪贴板（{len(text)} 字符）")
        self._discovery_status.setProperty("state", "success")
        self._discovery_status.style().unpolish(self._discovery_status)
        self._discovery_status.style().polish(self._discovery_status)

    def _on_paste_to_client_token(self):
        from PySide6.QtWidgets import QApplication
        text = QApplication.clipboard().text().strip()
        if not text:
            QMessageBox.information(self, "提示", "剪贴板为空。")
            return
        self._client_token_edit.setText(text)

    def _on_detect_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
        except Exception as e:
            QMessageBox.warning(self, "检测失败", f"无法获取本机 IP:\n{e}\n请手动输入。")
            return
        self._host_edit.setText(ip)
        QMessageBox.information(self, "检测成功", f"本机局域网 IP：{ip}")

    def _on_discover_devices(self):
        from core.discovery import discover_devices

        self._btn_discover.setEnabled(False)
        self._discovery_status.setText("正在扫描子网...")
        self._discovery_status.setProperty("state", "info")
        self._discovery_status.style().unpolish(self._discovery_status)
        self._discovery_status.style().polish(self._discovery_status)
        self._device_list.clear()

        class _ScanWorker(QThread):
            result = Signal(list)

            def run(self_):
                self_.result.emit(discover_devices())

        self._scan_worker = _ScanWorker()
        self._scan_worker.result.connect(self._on_scan_result)
        self._scan_worker.start()

    def _on_scan_result(self, devices: list):
        self._btn_discover.setEnabled(True)
        self._device_list.clear()
        if not devices:
            self._discovery_status.setText("未发现其他 Toolkit 实例")
            self._discovery_status.setProperty("state", "warning")
            self._discovery_status.style().unpolish(self._discovery_status)
            self._discovery_status.style().polish(self._discovery_status)
            return

        for d in devices:
            item = QListWidgetItem(f"  🖥  {d['ip']}:{d['port']}  ({d['mode']})")
            item.setData(Qt.ItemDataRole.UserRole, d)
            self._device_list.addItem(item)

        self._discovery_status.setText(f"✓ 发现 {len(devices)} 个设备")
        self._discovery_status.setProperty("state", "success")
        self._discovery_status.style().unpolish(self._discovery_status)
        self._discovery_status.style().polish(self._discovery_status)

    def _on_device_selected(self):
        self._btn_pair.setEnabled(self._device_list.currentItem() is not None)

    def _on_pair_device(self):
        item = self._device_list.currentItem()
        if not item:
            return
        device = item.data(Qt.ItemDataRole.UserRole)
        self._server_url_edit.setText(device["url"])
        self._mode_combo.setCurrentIndex(2)
        QMessageBox.information(
            self, "配对成功",
            f"已配对设备：\n{device['ip']}:{device['port']}\n\n"
            f"工作模式已切换为「客户端」\n"
            f"服务器地址已填入下方输入框\n\n"
            f"⚠️ 点击底部「保存」后才会真正生效"
        )

    def _on_test_connection(self):
        mode_idx = self._mode_combo.currentIndex()
        if mode_idx == 0:
            self._test_result.setText("本地模式无需测试")
            self._test_result.setProperty("state", "info")
            self._test_result.style().unpolish(self._test_result)
            self._test_result.style().polish(self._test_result)
            return

        if mode_idx == 1:
            host = self._host_edit.text().strip() or "127.0.0.1"
            if host == "0.0.0.0":
                host = "127.0.0.1"
            port = self._port_spin.value()
            url = f"http://{host}:{port}"
        else:
            url = self._server_url_edit.text().strip()
            if not url:
                self._test_result.setText("请输入服务器地址")
                self._test_result.setProperty("state", "warning")
                self._test_result.style().unpolish(self._test_result)
                self._test_result.style().polish(self._test_result)
                return

        self._btn_test.setEnabled(False)
        self._test_result.setText("正在测试...")
        self._test_result.setProperty("state", "info")
        self._test_result.style().unpolish(self._test_result)
        self._test_result.style().polish(self._test_result)

        self._test_worker = _NetworkTestWorker(url)
        self._test_worker.result.connect(self._on_test_result)
        self._test_worker.start()

    def _on_test_result(self, ok: bool, msg: str):
        self._btn_test.setEnabled(True)
        prefix = "✓ " if ok else "✗ "
        self._test_result.setText(prefix + msg)
        self._test_result.setProperty("state", "success" if ok else "danger")
        self._test_result.style().unpolish(self._test_result)
        self._test_result.style().polish(self._test_result)

    # --- 由主对话框调用：保存/恢复/同步运行时 ---
    def persist_to_config(self) -> None:
        """把当前界面值同步到 config + 同步运行时 DB server 状态"""
        v = self.collect_values()
        modes = ["local", "server", "client"]
        config.db.network_mode = modes[v["mode_index"]]
        config.db.server_host = (v["host"] or "0.0.0.0").strip() if isinstance(v["host"], str) else v["host"]
        config.db.server_port = int(v["port"])
        # Token: server 模式用服务端 token, client 模式用客户端 token
        if v["mode_index"] == 1:
            config.db.api_token = v["server_token"].strip() if isinstance(v["server_token"], str) else v["server_token"]
        else:
            config.db.api_token = v["client_token"].strip() if isinstance(v["client_token"], str) else v["client_token"]
        config.db.server_url = v["server_url"].strip() if isinstance(v["server_url"], str) else v["server_url"]
        config.db.server_allow_write = bool(v["allow_write"])
        config.save()
        self._sync_server_runtime()

    def _sync_server_runtime(self):
        try:
            from core.db_server import start_server_in_thread, stop_server, is_server_running
            if config.db.network_mode == "server":
                start_server_in_thread()
                self._test_result.setText(f"✓ 服务端已启动: {config.db.server_host}:{config.db.server_port}")
                self._test_result.setProperty("state", "success")
            else:
                if is_server_running():
                    stop_server()
                    self._test_result.setText("✓ 服务端已停止")
                    self._test_result.setProperty("state", "success")
        except Exception as e:
            logger.error(f"同步 DB server 运行状态失败: {e}", exc_info=True)
            self._test_result.setText(f"✗ 服务端状态同步失败: {e}")
            self._test_result.setProperty("state", "danger")
        self._test_result.style().unpolish(self._test_result)
        self._test_result.style().polish(self._test_result)


# ═══════════════════════════════════════════════════════════
#  peel_data 插件参数 Tab
# ═══════════════════════════════════════════════════════════

class _PluginTab(QWidget, _DirtyTrackerMixin):
    """peel_data 插件参数配置"""

    def __init__(self, host: "SettingsDialog", parent=None):
        QWidget.__init__(self, parent)
        _DirtyTrackerMixin.__init__(self, host)
        self._initial: Dict[str, object] = {}
        self._setup_ui()
        self._load_current()
        self._capture_initial()
        self._track(
            self._data_dir_edit, self._db_path_edit,
            self._pos_keywords_edit, self._neg_keywords_edit,
            self._pos_mat_edit, self._neg_mat_edit,
            self._cond_mat_edit, self._tape_mat_edit,
        )

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)

        # === 路径配置 ===
        path_group = QGroupBox("数据路径配置")
        path_layout = QFormLayout(path_group)
        path_layout.setSpacing(10)
        path_layout.setContentsMargins(16, 20, 16, 16)

        data_dir_row = QHBoxLayout()
        self._data_dir_edit = QLineEdit()
        self._data_dir_edit.setPlaceholderText("上次使用的数据目录（自动记忆）")
        data_dir_row.addWidget(self._data_dir_edit)
        btn_browse_dir = QPushButton("浏览...")
        btn_browse_dir.setObjectName("btn_secondary")
        btn_browse_dir.setFixedWidth(70)
        btn_browse_dir.clicked.connect(self._browse_data_dir)
        data_dir_row.addWidget(btn_browse_dir)
        path_layout.addRow("数据目录：", data_dir_row)

        db_path_row = QHBoxLayout()
        self._db_path_edit = QLineEdit()
        self._db_path_edit.setPlaceholderText("留空则使用默认路径: data/app.db")
        db_path_row.addWidget(self._db_path_edit)
        btn_browse_db = QPushButton("浏览...")
        btn_browse_db.setObjectName("btn_secondary")
        btn_browse_db.setFixedWidth(70)
        btn_browse_db.clicked.connect(self._browse_db_path)
        db_path_row.addWidget(btn_browse_db)
        path_layout.addRow("数据库路径：", db_path_row)

        self._db_path_hint = QLabel("默认: {项目根}/data/app.db")
        self._db_path_hint.setObjectName("hint_label")
        path_layout.addRow("", self._db_path_hint)

        layout.addWidget(path_group)

        # === 关键词配置 ===
        keyword_group = QGroupBox("极性判定关键词")
        keyword_layout = QVBoxLayout(keyword_group)
        keyword_layout.setSpacing(10)
        keyword_layout.setContentsMargins(16, 20, 16, 16)

        self._pos_keywords_edit = QLineEdit()
        self._pos_keywords_edit.setPlaceholderText("如：正极, 阳极, Al, 铝箔")
        keyword_layout.addWidget(self._make_section_label("正极关键词（逗号分隔，试样名称包含以下任一则判定为正极）：", self._pos_keywords_edit))

        self._neg_keywords_edit = QLineEdit()
        self._neg_keywords_edit.setPlaceholderText("如：负极, 阴极, Cu, 铜箔")
        keyword_layout.addWidget(self._make_section_label("负极关键词（逗号分隔，试样名称包含以下任一则判定为负极）：", self._neg_keywords_edit))

        self._pos_mat_edit = QLineEdit()
        self._pos_mat_edit.setPlaceholderText("如：PVDF, 三元, NCM, LFP, 铝箔")
        keyword_layout.addWidget(self._make_section_label("正极相关材料（粘结剂/正极活性物质/集流体，逗号分隔）：", self._pos_mat_edit))

        self._neg_mat_edit = QLineEdit()
        self._neg_mat_edit.setPlaceholderText("如：CMC, SBR, 石墨, 硅基, 铜箔")
        keyword_layout.addWidget(self._make_section_label("负极相关材料（粘结剂/负极活性物质/集流体，逗号分隔）：", self._neg_mat_edit))

        self._cond_mat_edit = QLineEdit()
        self._cond_mat_edit.setPlaceholderText("如：导电液, 碳纳米管, SuperP, 乙炔黑")
        keyword_layout.addWidget(self._make_section_label("导电剂 / 通用材料（正负极都可能用，逗号分隔）：", self._cond_mat_edit))

        self._tape_mat_edit = QLineEdit()
        self._tape_mat_edit.setPlaceholderText("如：高温胶, 膨胀胶, 隔膜, 电解液")
        keyword_layout.addWidget(self._make_section_label("胶带类 / 通用辅料（高温胶/膨胀胶/隔膜等，逗号分隔）：", self._tape_mat_edit))

        self._keyword_hint = QLabel("提示：关键词按使用范围分类存储，修改后点击底部「保存」生效，「恢复默认」可还原。")
        self._keyword_hint.setObjectName("hint_label")
        keyword_layout.addWidget(self._keyword_hint)

        layout.addWidget(keyword_group)

        # === 重置按钮 ===
        reset_row = QHBoxLayout()
        reset_row.addStretch()
        btn_reset = QPushButton("恢复默认关键词")
        btn_reset.setObjectName("btn_warning")
        btn_reset.clicked.connect(self._reset_keywords)
        reset_row.addWidget(btn_reset)
        layout.addLayout(reset_row)

        layout.addStretch()

    def _make_section_label(self, text: str, target: QLineEdit) -> QWidget:
        """生成一组说明文字 + 清空按钮 + 输入框，避免关键词区挤成一团"""
        wrap = QWidget()
        v = QVBoxLayout(wrap)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)

        h = QHBoxLayout()
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)

        lbl = QLabel(text)
        lbl.setObjectName("section_label")
        lbl.setWordWrap(True)
        h.addWidget(lbl, stretch=1)

        clear_btn = QPushButton("清空")
        clear_btn.setObjectName("btn_secondary")
        clear_btn.setFixedWidth(56)
        clear_btn.clicked.connect(lambda: target.clear())
        h.addWidget(clear_btn, alignment=Qt.AlignmentFlag.AlignBottom)

        v.addLayout(h)
        v.addWidget(target)
        return wrap

    def _load_current(self):
        self._data_dir_edit.setText(config.last_data_dir)
        self._db_path_edit.setText(config.db.database_path)
        self._pos_keywords_edit.setText(", ".join(config.positive_keywords))
        self._neg_keywords_edit.setText(", ".join(config.negative_keywords))

        default_config = type(config)()
        all_materials = set(config.lithium_battery_materials or default_config.lithium_battery_materials)

        pos_mat_seeds = {
            "PVDF", "聚偏氟乙烯", "三元", "NCM", "NCA", "LFP", "磷酸铁锂", "钴酸锂",
            "LCO", "锰酸锂", "LMO", "镍钴锰", "镍钴铝", "铝箔", "涂炭铝箔",
        }
        neg_mat_seeds = {
            "CMC", "丁苯橡胶", "SBR", "丁腈橡胶", "NBR", "水性粘结剂",
            "石墨", "人造石墨", "天然石墨", "球形石墨", "鳞片石墨",
            "中间相碳微球", "MCMB", "中间相沥青",
            "硅碳", "硅基", "SiO", "氧化亚硅", "硅氧", "硅纳米", "纳米硅", "硅粉", "多孔硅",
            "铜箔", "涂炭铜箔",
        }
        cond_mat_seeds = {
            "导电液", "单壁管导电液", "多壁管导电液", "碳管导电液",
            "CNT导电液", "碳纳米管导电液", "石墨烯导电液", "银浆",
            "KS-6", "SP-Li", "SP", "KS6", "SuperP", "Super-P",
            "乙炔黑", "导电炭黑", "VGCF", "气相生长碳纤维", "导电剂",
        }
        tape_mat_seeds = {
            "高温胶", "膨胀胶", "阻燃胶", "导热胶", "结构胶",
            "耐高温胶", "耐低温胶",
            "隔膜", "PE隔膜", "PP隔膜", "陶瓷隔膜", "电解液",
            "复合箔", "极片", "浆料", "正极材料", "负极材料",
        }

        pos_mat = [k for k in all_materials if k in pos_mat_seeds]
        neg_mat = [k for k in all_materials if k in neg_mat_seeds]
        cond_mat = [k for k in all_materials if k in cond_mat_seeds]
        tape_mat = [k for k in all_materials if k in tape_mat_seeds]

        self._pos_mat_edit.setText(", ".join(pos_mat))
        self._neg_mat_edit.setText(", ".join(neg_mat))
        self._cond_mat_edit.setText(", ".join(cond_mat))
        self._tape_mat_edit.setText(", ".join(tape_mat))

    def _capture_initial(self):
        self._initial = self.collect_values()

    def collect_values(self) -> Dict[str, object]:
        return {
            "data_dir": self._data_dir_edit.text(),
            "db_path": self._db_path_edit.text(),
            "pos_keywords": self._pos_keywords_edit.text(),
            "neg_keywords": self._neg_keywords_edit.text(),
            "pos_mat": self._pos_mat_edit.text(),
            "neg_mat": self._neg_mat_edit.text(),
            "cond_mat": self._cond_mat_edit.text(),
            "tape_mat": self._tape_mat_edit.text(),
        }

    def apply_values(self, values: Dict[str, object]) -> None:
        self._data_dir_edit.setText(values.get("data_dir", ""))
        self._db_path_edit.setText(values.get("db_path", ""))
        self._pos_keywords_edit.setText(values.get("pos_keywords", ""))
        self._neg_keywords_edit.setText(values.get("neg_keywords", ""))
        self._pos_mat_edit.setText(values.get("pos_mat", ""))
        self._neg_mat_edit.setText(values.get("neg_mat", ""))
        self._cond_mat_edit.setText(values.get("cond_mat", ""))
        self._tape_mat_edit.setText(values.get("tape_mat", ""))

    def is_dirty(self) -> bool:
        if not self._initial:
            return False
        return self.collect_values() != self._initial

    def _browse_data_dir(self):
        current = self._data_dir_edit.text().strip()
        path = QFileDialog.getExistingDirectory(self, "选择数据目录", current)
        if path:
            self._data_dir_edit.setText(path)

    def _browse_db_path(self):
        current = self._db_path_edit.text().strip()
        path, _ = QFileDialog.getSaveFileName(
            self, "选择数据库文件", current,
            "SQLite 数据库 (*.db);;所有文件 (*)",
        )
        if path:
            self._db_path_edit.setText(path)

    def _reset_keywords(self):
        reply = QMessageBox.question(
            self, "确认恢复",
            "确定要将所有关键词恢复为默认值吗？\n\n恢复后请记得点击底部「保存」使其生效。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        config.positive_keywords = ["正极", "阳极", "Al", "铝箔", "铝", "cathode", "positive"]
        config.negative_keywords = ["负极", "阴极", "Cu", "铜箔", "铜", "anode", "negative"]
        default_config = type(config)()
        config.lithium_battery_materials = default_config.lithium_battery_materials
        # 重新填 UI(不直接落盘，让用户走"保存")
        self._load_current()
        QMessageBox.information(self, "已恢复", "关键词已恢复为默认值，请点击底部「保存」生效。")

    def persist_to_config(self) -> None:
        v = self.collect_values()
        config.last_data_dir = v["data_dir"].strip() if isinstance(v["data_dir"], str) else v["data_dir"]
        config.db.database_path = v["db_path"].strip() if isinstance(v["db_path"], str) else v["db_path"]

        def _parse(text):
            if not isinstance(text, str):
                return []
            return [k.strip() for k in text.split(",") if k.strip()]

        config.positive_keywords = _parse(v["pos_keywords"])
        config.negative_keywords = _parse(v["neg_keywords"])

        materials: List[str] = []
        for k in (v["pos_mat"], v["neg_mat"], v["cond_mat"], v["tape_mat"]):
            materials.extend(_parse(k))
        seen = set()
        config.lithium_battery_materials = [x for x in materials if not (x in seen or seen.add(x))]
        config.save()


# ═══════════════════════════════════════════════════════════
#  配置导入导出 Tab
# ═══════════════════════════════════════════════════════════

class _ImportExportTab(QWidget):
    """配置导入导出"""

    def __init__(self, host: "SettingsDialog", parent=None):
        super().__init__(parent)
        self._host = host
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)

        # === 导出 ===
        export_group = QGroupBox("导出配置")
        export_layout = QVBoxLayout(export_group)
        export_layout.setSpacing(10)
        export_layout.setContentsMargins(16, 20, 16, 16)

        export_desc = QLabel(
            "将当前所有配置导出为 JSON 文件，可在其他设备上导入使用。"
            "导出内容包含：网络配置、插件参数、关键词等所有设置。"
        )
        export_desc.setWordWrap(True)
        export_desc.setObjectName("hint_label")
        export_layout.addWidget(export_desc)

        btn_export = QPushButton("导出配置文件...")
        btn_export.setObjectName("btn_success")
        btn_export.setMinimumWidth(140)
        btn_export.clicked.connect(self._on_export)
        export_layout.addWidget(btn_export, alignment=Qt.AlignmentFlag.AlignLeft)

        layout.addWidget(export_group)

        # === 导入 ===
        import_group = QGroupBox("导入配置")
        import_layout = QVBoxLayout(import_group)
        import_layout.setSpacing(10)
        import_layout.setContentsMargins(16, 20, 16, 16)

        import_desc = QLabel(
            "从 JSON 配置文件导入设置。导入后会覆盖当前所有配置。"
            "建议先导出当前配置作为备份。"
        )
        import_desc.setWordWrap(True)
        import_desc.setObjectName("hint_label")
        import_layout.addWidget(import_desc)

        btn_import = QPushButton("导入配置文件...")
        btn_import.setObjectName("btn_warning")
        btn_import.setMinimumWidth(140)
        btn_import.clicked.connect(self._on_import)
        import_layout.addWidget(btn_import, alignment=Qt.AlignmentFlag.AlignLeft)

        layout.addWidget(import_group)

        # === 预览区 ===
        preview_group = QGroupBox("当前配置预览（只读）")
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.setContentsMargins(16, 20, 16, 16)

        self._preview_text = QTextEdit()
        self._preview_text.setReadOnly(True)
        self._preview_text.setFont(QFont("Consolas", 11))
        self._preview_text.setMaximumHeight(220)
        preview_layout.addWidget(self._preview_text)

        btn_refresh = QPushButton("刷新预览")
        btn_refresh.setObjectName("btn_secondary")
        btn_refresh.clicked.connect(self._refresh_preview)
        preview_layout.addWidget(btn_refresh, alignment=Qt.AlignmentFlag.AlignLeft)

        layout.addWidget(preview_group)
        layout.addStretch()

        self._refresh_preview()

    def _refresh_preview(self):
        data = config.export_settings()
        self._preview_text.setPlainText(
            json.dumps(data, ensure_ascii=False, indent=2)
        )

    def _on_export(self):
        default_name = "toolkit_config.json"
        path, _ = QFileDialog.getSaveFileName(
            self, "导出配置", default_name,
            "JSON 文件 (*.json);;所有文件 (*)",
        )
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"

        try:
            data = config.export_settings()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            QMessageBox.information(
                self, "导出成功",
                f"配置已导出到：\n{path}\n\n"
                f"文件大小: {os.path.getsize(path)} 字节"
            )
            logger.info(f"配置已导出: {path}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出配置时发生错误:\n{e}")

    def _on_import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "导入配置", "",
            "JSON 文件 (*.json);;所有文件 (*)",
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, dict):
                QMessageBox.warning(self, "格式错误", "配置文件格式不正确，应为 JSON 对象")
                return

            reply = QMessageBox.question(
                self, "确认导入",
                f"即将导入配置文件：\n{path}\n\n"
                f"导入后将覆盖当前所有配置，是否继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

            config.import_settings(data)
            self._refresh_preview()
            QMessageBox.information(
                self, "导入成功",
                "配置已导入并生效。\n"
                "部分设置（如数据库路径）需要重启应用后生效。\n\n"
                "本对话框中的输入框已自动同步最新值。"
            )
            # 通知 host 重新加载所有 Tab
            self._host.reload_all_tabs()
            logger.info(f"配置已导入: {path}")
        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "JSON 解析失败", f"配置文件不是有效的 JSON:\n{e}")
        except Exception as e:
            QMessageBox.critical(self, "导入失败", f"导入配置时发生错误:\n{e}")


# ═══════════════════════════════════════════════════════════
#  主设置对话框
# ═══════════════════════════════════════════════════════════

class SettingsDialog(QDialog):
    """
    综合设置界面（Tab 组织三个模块）
    v1.7.1：底部统一「保存 / 放弃 / 关闭」按钮
            顶部「未保存」角标 + 各 Tab 标题右侧小圆点提示
            任何配置项改动不再实时落盘，必须点「保存」才生效
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Toolkit 综合设置")
        self.setMinimumSize(720, 600)
        self.resize(780, 640)
        self._dirty = False
        self._initial_snapshots: Dict[str, Dict] = {}
        self._setup_ui()
        self._apply_style()
        # 进入时禁用保存按钮
        self._set_dirty(False)

    # --- UI 构造 ---
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        # ===== 顶部标题 + 未保存角标 =====
        header = QHBoxLayout()
        title = QLabel("⚙ 综合设置")
        title.setObjectName("title_label")
        header.addWidget(title)

        self._dirty_badge = QLabel("● 未保存")
        self._dirty_badge.setObjectName("dirty_badge")
        self._dirty_badge.setVisible(False)
        header.addWidget(self._dirty_badge)
        header.addStretch()

        from config import get_version
        ver_lbl = QLabel(f"v{get_version()}")
        ver_lbl.setObjectName("hint_label")
        header.addWidget(ver_lbl)

        layout.addLayout(header)

        # ===== Tab 容器 =====
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

        # Tab 切换后重新计算脏值状态
        self._tabs.currentChanged.connect(self._refresh_dirty_state)

        layout.addWidget(self._tabs, stretch=1)

        # ===== 底部按钮 =====
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._hint_label = QLabel("所有改动仅在「保存」后生效。")
        self._hint_label.setObjectName("hint_label")
        btn_row.addWidget(self._hint_label)
        btn_row.addStretch()

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

        self._btn_close = QPushButton("关闭")
        self._btn_close.setMinimumWidth(80)
        self._btn_close.clicked.connect(self._on_close_requested)
        btn_row.addWidget(self._btn_close)

        layout.addLayout(btn_row)

    def _apply_style(self):
        self.setStyleSheet(SETTINGS_DIALOG_STYLE)

    # --- 脏值管理 ---
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
        # 同步各 Tab 标题右侧小圆点
        for idx, tab in enumerate(self._tabs_widgets()):
            text = self._tabs.tabText(idx)
            if self._tab_is_dirty(tab) and "●" not in text:
                self._tabs.setTabText(idx, text + "  ●")
            elif not self._tab_is_dirty(tab):
                self._tabs.setTabText(idx, text.replace("  ●", ""))

    def _tabs_widgets(self) -> List[QWidget]:
        return [self._network_tab, self._plugin_tab]

    def _tab_is_dirty(self, tab) -> bool:
        if hasattr(tab, "is_dirty"):
            try:
                return tab.is_dirty()
            except Exception:
                return False
        return False

    def _refresh_dirty_state(self, *_):
        # 不自动改 self._dirty —— Tab 内部已发出脏值信号
        # 这里只是检查整体状态,用于刚打开时(无改动)的初始化
        any_dirty = any(self._tab_is_dirty(t) for t in self._tabs_widgets())
        self._set_dirty(any_dirty)

    def reload_all_tabs(self):
        """导入配置后由 ImportExport Tab 调用,重新从 config 读值"""
        self._network_tab._load_current()
        self._network_tab._capture_initial()
        self._plugin_tab._load_current()
        self._plugin_tab._capture_initial()
        self._set_dirty(False)
        # 导入配置可能影响 server 运行时
        self._network_tab._sync_server_runtime()

    # --- 底部按钮事件 ---
    def _on_save(self):
        try:
            # 顺序：先网络（涉及 server 启停），再插件参数
            self._network_tab.persist_to_config()
            self._plugin_tab.persist_to_config()
        except Exception as e:
            logger.error(f"保存配置失败: {e}", exc_info=True)
            QMessageBox.critical(self, "保存失败", f"保存配置时发生错误:\n{e}")
            return

        # 重新快照
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
        # 从 config 重新读值即可
        self.reload_all_tabs()
        self._status_flash("已放弃改动", "info")

    def _on_close_requested(self):
        if self._dirty:
            reply = QMessageBox.question(
                self, "未保存的改动",
                "你有未保存的改动，确定要关闭吗？\n\n"
                "「是」= 放弃改动并关闭\n"
                "「否」= 留在当前窗口继续编辑",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self.accept()

    def _status_flash(self, text: str, state: str = "info", ms: int = 2000):
        """在顶部状态行临时显示一条消息,自动消失"""
        self._hint_label.setText(text)
        self._hint_label.setProperty("state", state)
        self._hint_label.style().unpolish(self._hint_label)
        self._hint_label.style().polish(self._hint_label)

    def closeEvent(self, event):
        if self._dirty:
            reply = QMessageBox.question(
                self, "未保存的改动",
                "你有未保存的改动，确定要关闭吗？\n\n"
                "「是」= 放弃改动并关闭\n"
                "「否」= 留在当前窗口继续编辑",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        event.accept()
