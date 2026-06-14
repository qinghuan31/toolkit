# -*- coding: utf-8 -*-
"""
综合设置界面
包含：局域网多设备配置、peel_data 插件参数、配置导入导出
"""

import os
import json
import socket
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QPushButton, QLineEdit, QSpinBox, QComboBox,
    QGroupBox, QFormLayout, QFileDialog, QMessageBox,
    QTextEdit, QGridLayout, QSizePolicy, QCheckBox,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont

from config import config
from core.logger import get_logger

logger = get_logger("settings")


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

class _NetworkTab(QWidget):
    """局域网多设备访问配置"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._test_worker: Optional[_NetworkTestWorker] = None
        self._setup_ui()
        self._load_current()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(16)

        # === 模式选择 ===
        mode_group = QGroupBox("网络模式")
        mode_layout = QFormLayout(mode_group)
        mode_layout.setSpacing(10)
        mode_layout.setContentsMargins(16, 20, 16, 16)

        self._mode_combo = QComboBox()
        self._mode_combo.addItems([
            "local  — 仅本机（默认）",
            "server — 作为服务端，局域网其他设备可连接",
            "client — 作为客户端，连接到局域网服务端",
        ])
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_layout.addRow("工作模式：", self._mode_combo)

        self._mode_hint = QLabel()
        self._mode_hint.setWordWrap(True)
        self._mode_hint.setStyleSheet("color: #6b7280; font-size: 12px;")
        mode_layout.addRow("", self._mode_hint)
        layout.addWidget(mode_group)

        # === Server 配置 ===
        self._server_group = QGroupBox("服务端配置")
        server_layout = QFormLayout(self._server_group)
        server_layout.setSpacing(10)
        server_layout.setContentsMargins(16, 20, 16, 16)

        # 监听地址：自动填本机局域网 IP
        local_ip = "0.0.0.0"
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except Exception:
            pass

        host_row = QHBoxLayout()
        self._host_edit = QLineEdit()
        self._host_edit.setText(local_ip)
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

        # 服务端 Token：明文 + 复制 + 自动生成
        token_row = QHBoxLayout()
        self._token_edit = QLineEdit()
        self._token_edit.setPlaceholderText("留空则无鉴权（建议内部使用时设置）")
        self._token_edit.setEchoMode(QLineEdit.EchoMode.Normal)
        token_row.addWidget(self._token_edit)
        btn_copy_token = QPushButton("📋 复制")
        btn_copy_token.setObjectName("btn_secondary")
        btn_copy_token.setFixedWidth(70)
        btn_copy_token.setToolTip("复制 Token 到剪贴板")
        btn_copy_token.clicked.connect(self._on_copy_token)
        token_row.addWidget(btn_copy_token)
        btn_gen_token = QPushButton("自动生成")
        btn_gen_token.setObjectName("btn_secondary")
        btn_gen_token.setFixedWidth(80)
        btn_gen_token.clicked.connect(self._on_generate_token)
        token_row.addWidget(btn_gen_token)
        server_layout.addRow("API Token：", token_row)

        # 【v1.7.0】客户端写入权限开关
        self._allow_write_check = QCheckBox("允许客户端写入数据库")
        self._allow_write_check.setToolTip(
            "勾选：客户端可读可写（默认）\n"
            "取消：客户端只能查询数据，写入操作会被服务端拒绝（403）\n\n"
            "建议：多人协作时由主机控制写入，避免数据冲突"
        )
        self._allow_write_check.setChecked(True)
        self._allow_write_check.stateChanged.connect(self._save)
        server_layout.addRow("写入权限：", self._allow_write_check)

        layout.addWidget(self._server_group)

        # === Client 配置（独立 group）===
        self._client_group = QGroupBox("客户端配置")
        client_layout = QFormLayout(self._client_group)
        client_layout.setSpacing(10)
        client_layout.setContentsMargins(16, 20, 16, 16)

        self._server_url_edit = QLineEdit()
        self._server_url_edit.setPlaceholderText("http://192.168.1.100:8765")
        client_layout.addRow("服务器地址：", self._server_url_edit)

        # 客户端 Token：明文 + 复制 + 粘贴
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
        self._discovery_status.setStyleSheet("color: #6b7280; font-size: 12px;")
        discovery_btn_row.addWidget(self._discovery_status)
        discovery_btn_row.addStretch()
        discovery_layout.addLayout(discovery_btn_row)

        # 设备列表
        from PySide6.QtWidgets import QListWidget, QListWidgetItem
        self._device_list = QListWidget()
        self._device_list.setMaximumHeight(140)
        self._device_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #dcdfe6;
                border-radius: 4px;
                background: #ffffff;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 6px 10px;
            }
            QListWidget::item:selected {
                background: #ecf5ff;
                color: #409eff;
            }
        """)
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
        self._test_result.setStyleSheet("color: #6b7280; font-size: 13px;")
        test_layout.addWidget(self._test_result)
        test_layout.addStretch()
        layout.addWidget(test_group)

        layout.addStretch()

        # 信号：值变化时实时保存
        self._mode_combo.currentIndexChanged.connect(self._save)
        self._host_edit.editingFinished.connect(self._save)
        self._port_spin.valueChanged.connect(self._save)
        self._token_edit.editingFinished.connect(self._save)
        self._server_url_edit.editingFinished.connect(self._save)
        self._client_token_edit.editingFinished.connect(self._save)

    def _load_current(self):
        """从 config 加载当前值"""
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

    def _on_mode_changed(self, index: int):
        """模式切换时显示/隐藏对应配置区"""
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
        """自动生成 32 字节随机 Token"""
        import secrets
        token = secrets.token_urlsafe(32)
        self._token_edit.setText(token)
        self._save()

    def _on_copy_token(self):
        """复制服务端 Token 到剪贴板"""
        self._on_copy_field(self._token_edit)

    def _on_copy_field(self, line_edit):
        """复制任意 QLineEdit 内容到剪贴板"""
        from PySide6.QtWidgets import QApplication
        text = line_edit.text()
        if not text:
            QMessageBox.information(self, "提示", "字段为空，无需复制。")
            return
        QApplication.clipboard().setText(text)
        # 状态栏式反馈（用 self 顶部的 title 区域临时显示）
        self._discovery_status.setText(f"✓ 已复制到剪贴板（{len(text)} 字符）")
        self._discovery_status.setStyleSheet("color: #059669; font-size: 12px; font-weight: bold;")

    def _on_paste_to_client_token(self):
        """从剪贴板粘贴到客户端 Token 输入框"""
        from PySide6.QtWidgets import QApplication
        text = QApplication.clipboard().text().strip()
        if not text:
            QMessageBox.information(self, "提示", "剪贴板为空。")
            return
        self._client_token_edit.setText(text)
        self._save()

    def _on_detect_local_ip(self):
        """重新检测本机局域网 IP"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
        except Exception as e:
            QMessageBox.warning(self, "检测失败", f"无法获取本机 IP:\n{e}\n请手动输入。")
            return
        self._host_edit.setText(ip)
        self._save()
        QMessageBox.information(self, "检测成功", f"本机局域网 IP：{ip}")

    def _on_discover_devices(self):
        """扫描局域网设备（后台线程）"""
        from core.discovery import discover_devices

        self._btn_discover.setEnabled(False)
        self._discovery_status.setText("正在扫描子网...")
        self._discovery_status.setStyleSheet("color: #6b7280; font-size: 12px;")
        self._device_list.clear()

        class _ScanWorker(QThread):
            result = Signal(list)

            def run(self_):
                self_.result.emit(discover_devices())

        self._scan_worker = _ScanWorker()
        self._scan_worker.result.connect(self._on_scan_result)
        self._scan_worker.start()

    def _on_scan_result(self, devices: list):
        """扫描结果回调"""
        self._btn_discover.setEnabled(True)
        self._device_list.clear()
        if not devices:
            self._discovery_status.setText("未发现其他 Toolkit 实例")
            self._discovery_status.setStyleSheet("color: #e67e22; font-size: 12px;")
            return

        for d in devices:
            from PySide6.QtWidgets import QListWidgetItem
            item = QListWidgetItem(f"  🖥  {d['ip']}:{d['port']}  ({d['mode']})")
            item.setData(Qt.ItemDataRole.UserRole, d)
            self._device_list.addItem(item)

        self._discovery_status.setText(f"✓ 发现 {len(devices)} 个设备")
        self._discovery_status.setStyleSheet("color: #059669; font-size: 12px; font-weight: bold;")

    def _on_device_selected(self):
        """设备列表选中时启用配对按钮"""
        self._btn_pair.setEnabled(self._device_list.currentItem() is not None)

    def _on_pair_device(self):
        """配对：将选中设备 URL 写入客户端服务器地址"""
        item = self._device_list.currentItem()
        if not item:
            return
        device = item.data(Qt.ItemDataRole.UserRole)
        self._server_url_edit.setText(device["url"])
        # 自动切到 client 模式
        self._mode_combo.setCurrentIndex(2)
        self._save()
        QMessageBox.information(
            self, "配对成功",
            f"已配对设备：\n{device['ip']}:{device['port']}\n\n"
            f"工作模式已切换为「客户端」\n"
            f"服务器地址已填入下方输入框"
        )

    def _on_test_connection(self):
        """测试连接"""
        mode_idx = self._mode_combo.currentIndex()
        if mode_idx == 0:
            self._test_result.setText("本地模式无需测试")
            self._test_result.setStyleSheet("color: #6b7280; font-size: 13px;")
            return

        if mode_idx == 1:
            # Server 模式：测试本机端口
            host = self._host_edit.text().strip() or "127.0.0.1"
            if host == "0.0.0.0":
                host = "127.0.0.1"
            port = self._port_spin.value()
            url = f"http://{host}:{port}"
        else:
            url = self._server_url_edit.text().strip()
            if not url:
                self._test_result.setText("请输入服务器地址")
                self._test_result.setStyleSheet("color: #e67e22; font-size: 13px;")
                return

        self._btn_test.setEnabled(False)
        self._test_result.setText("正在测试...")
        self._test_result.setStyleSheet("color: #6b7280; font-size: 13px;")

        self._test_worker = _NetworkTestWorker(url)
        self._test_worker.result.connect(self._on_test_result)
        self._test_worker.start()

    def _on_test_result(self, ok: bool, msg: str):
        """测试结果回调"""
        self._btn_test.setEnabled(True)
        if ok:
            self._test_result.setText(f"✓ {msg}")
            self._test_result.setStyleSheet("color: #059669; font-size: 13px; font-weight: bold;")
        else:
            self._test_result.setText(f"✗ {msg}")
            self._test_result.setStyleSheet("color: #dc2626; font-size: 13px; font-weight: bold;")

    def _sync_server_runtime(self):
        """根据当前网络模式启动或停止本进程内的 DB server。"""
        try:
            from core.db_server import start_server_in_thread, stop_server, is_server_running
            if config.db.network_mode == "server":
                start_server_in_thread()
                self._test_result.setText(f"✓ 服务端已启动: {config.db.server_host}:{config.db.server_port}")
                self._test_result.setStyleSheet("color: #059669; font-size: 13px; font-weight: bold;")
            else:
                if is_server_running():
                    stop_server()
                    self._test_result.setText("✓ 服务端已停止")
                    self._test_result.setStyleSheet("color: #059669; font-size: 13px; font-weight: bold;")
        except Exception as e:
            logger.error(f"同步 DB server 运行状态失败: {e}", exc_info=True)
            self._test_result.setText(f"✗ 服务端状态同步失败: {e}")
            self._test_result.setStyleSheet("color: #dc2626; font-size: 13px; font-weight: bold;")

    def _save(self):
        """实时保存网络配置到 config"""
        modes = ["local", "server", "client"]
        config.db.network_mode = modes[self._mode_combo.currentIndex()]
        config.db.server_host = self._host_edit.text().strip() or "0.0.0.0"
        config.db.server_port = self._port_spin.value()
        # Token：server/client 共用同一 token
        if self._mode_combo.currentIndex() == 1:
            config.db.api_token = self._token_edit.text().strip()
        else:
            config.db.api_token = self._client_token_edit.text().strip()
        config.db.server_url = self._server_url_edit.text().strip()
        config.db.server_allow_write = self._allow_write_check.isChecked()
        config.save()
        self._sync_server_runtime()
        logger.debug("网络配置已保存")


# ═══════════════════════════════════════════════════════════
#  peel_data 插件参数 Tab
# ═══════════════════════════════════════════════════════════

class _PluginTab(QWidget):
    """peel_data 插件参数配置"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._load_current()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(16)

        # === 路径配置 ===
        path_group = QGroupBox("数据路径配置")
        path_layout = QFormLayout(path_group)
        path_layout.setSpacing(10)
        path_layout.setContentsMargins(16, 20, 16, 16)

        # 数据目录
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

        # 数据库路径
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
        self._db_path_hint.setStyleSheet("color: #909399; font-size: 11px;")
        path_layout.addRow("", self._db_path_hint)

        layout.addWidget(path_group)

        # === 关键词配置 ===
        keyword_group = QGroupBox("极性判定关键词")
        keyword_layout = QVBoxLayout(keyword_group)
        keyword_layout.setSpacing(10)
        keyword_layout.setContentsMargins(16, 20, 16, 16)

        # 正极关键词
        pos_label = QLabel("正极关键词（逗号分隔，试样名称包含以下任一则判定为正极）：")
        pos_label.setStyleSheet("font-size: 12px; color: #374151;")
        keyword_layout.addWidget(pos_label)
        self._pos_keywords_edit = QLineEdit()
        self._pos_keywords_edit.setPlaceholderText("如：正极, 阳极, Al, 铝箔")
        keyword_layout.addWidget(self._pos_keywords_edit)

        # 负极关键词
        neg_label = QLabel("负极关键词（逗号分隔，试样名称包含以下任一则判定为负极）：")
        neg_label.setStyleSheet("font-size: 12px; color: #374151;")
        keyword_layout.addWidget(neg_label)
        self._neg_keywords_edit = QLineEdit()
        self._neg_keywords_edit.setPlaceholderText("如：负极, 阴极, Cu, 铜箔")
        keyword_layout.addWidget(self._neg_keywords_edit)

        # 材料关键词 —— 按使用范围正确归类
        # 正极相关材料（粘结剂/正极活性物质/集流体）
        pos_mat_label = QLabel("正极相关材料（PVDF/正极活性物质/铝箔等，逗号分隔）：")
        pos_mat_label.setStyleSheet("font-size: 12px; color: #374151;")
        keyword_layout.addWidget(pos_mat_label)
        self._pos_mat_edit = QLineEdit()
        self._pos_mat_edit.setPlaceholderText("如：PVDF, 聚偏氟乙烯, 三元, NCM, NCA, LFP, 磷酸铁锂, 钴酸锂, LCO, 锰酸锂, LMO, 镍钴锰, 镍钴铝, 铝箔, 涂炭铝箔")
        keyword_layout.addWidget(self._pos_mat_edit)

        # 负极相关材料（粘结剂/负极活性物质/集流体）
        neg_mat_label = QLabel("负极相关材料（CMC/SBR/石墨/硅基/铜箔等，逗号分隔）：")
        neg_mat_label.setStyleSheet("font-size: 12px; color: #374151;")
        keyword_layout.addWidget(neg_mat_label)
        self._neg_mat_edit = QLineEdit()
        self._neg_mat_edit.setPlaceholderText("如：CMC, 丁苯橡胶, SBR, 丁腈橡胶, NBR, 水性粘结剂, 石墨, 人造石墨, 天然石墨, 球形石墨, 鳞片石墨, MCMB, 中间相碳微球, 中间相沥青, 硅碳, 硅基, SiO, 氧化亚硅, 硅氧, 硅纳米, 纳米硅, 硅粉, 多孔硅, 铜箔, 涂炭铜箔")
        keyword_layout.addWidget(self._neg_mat_edit)

        # 导电剂 / 通用材料（正负极都可能用）
        cond_mat_label = QLabel("导电剂 / 通用材料（导电液/导电炭黑/导电剂，逗号分隔）：")
        cond_mat_label.setStyleSheet("font-size: 12px; color: #374151;")
        keyword_layout.addWidget(cond_mat_label)
        self._cond_mat_edit = QLineEdit()
        self._cond_mat_edit.setPlaceholderText("如：导电液, 单壁管导电液, 多壁管导电液, 碳管导电液, CNT导电液, 碳纳米管导电液, 石墨烯导电液, 银浆, KS-6, SP-Li, SP, KS6, SuperP, Super-P, 乙炔黑, 导电炭黑, VGCF, 气相生长碳纤维, 导电剂")
        keyword_layout.addWidget(self._cond_mat_edit)

        # 胶带类（高温胶/膨胀胶/...）
        tape_mat_label = QLabel("胶带类（高温胶/膨胀胶/阻燃胶/导热胶/结构胶，逗号分隔）：")
        tape_mat_label.setStyleSheet("font-size: 12px; color: #374151;")
        keyword_layout.addWidget(tape_mat_label)
        self._tape_mat_edit = QLineEdit()
        self._tape_mat_edit.setPlaceholderText("如：高温胶, 膨胀胶, 阻燃胶, 导热胶, 结构胶, 耐高温胶, 耐低温胶, 隔膜, PE隔膜, PP隔膜, 陶瓷隔膜, 电解液, 复合箔, 极片, 浆料, 正极材料, 负极材料")
        keyword_layout.addWidget(self._tape_mat_edit)

        self._keyword_hint = QLabel("提示：关键词按使用范围分类存储，实时生效。修改后点击「恢复默认」可还原。")
        self._keyword_hint.setStyleSheet("color: #909399; font-size: 11px;")
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

        # 信号：值变化时实时保存
        self._data_dir_edit.editingFinished.connect(self._save)
        self._db_path_edit.editingFinished.connect(self._save)
        self._pos_keywords_edit.editingFinished.connect(self._save)
        self._neg_keywords_edit.editingFinished.connect(self._save)
        self._pos_mat_edit.editingFinished.connect(self._save)
        self._neg_mat_edit.editingFinished.connect(self._save)
        self._cond_mat_edit.editingFinished.connect(self._save)
        self._tape_mat_edit.editingFinished.connect(self._save)

    def _load_current(self):
        """从 config 加载当前值，按使用范围分类填入对应输入框"""
        self._data_dir_edit.setText(config.last_data_dir)
        self._db_path_edit.setText(config.db.database_path)
        self._pos_keywords_edit.setText(", ".join(config.positive_keywords))
        self._neg_keywords_edit.setText(", ".join(config.negative_keywords))

        # 加载材料关键词默认分类（从 config 默认值切分）
        default_config = type(config)()
        all_materials = set(config.lithium_battery_materials or default_config.lithium_battery_materials)

        # 4 大分类的"种子"关键词（与 config.py 默认值对应）
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

    def _browse_data_dir(self):
        """选择数据目录"""
        current = self._data_dir_edit.text().strip()
        path = QFileDialog.getExistingDirectory(self, "选择数据目录", current)
        if path:
            self._data_dir_edit.setText(path)
            self._save()

    def _browse_db_path(self):
        """选择数据库文件"""
        current = self._db_path_edit.text().strip()
        path, _ = QFileDialog.getSaveFileName(
            self, "选择数据库文件", current,
            "SQLite 数据库 (*.db);;所有文件 (*)",
        )
        if path:
            self._db_path_edit.setText(path)
            self._save()

    def _reset_keywords(self):
        """恢复默认关键词"""
        reply = QMessageBox.question(
            self, "确认恢复",
            "确定要将所有关键词恢复为默认值吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        config.positive_keywords = ["正极", "阳极", "Al", "铝箔", "铝", "cathode", "positive"]
        config.negative_keywords = ["负极", "阴极", "Cu", "铜箔", "铜", "anode", "negative"]
        # 材料关键词太长，用 AppConfig 的默认值
        default_config = type(config)()
        config.lithium_battery_materials = default_config.lithium_battery_materials
        self._load_current()
        self._save()
        QMessageBox.information(self, "已恢复", "关键词已恢复为默认值。")

    def _save(self):
        """实时保存插件参数到 config"""
        config.last_data_dir = self._data_dir_edit.text().strip()
        config.db.database_path = self._db_path_edit.text().strip()

        # 解析关键词
        pos_text = self._pos_keywords_edit.text().strip()
        config.positive_keywords = [k.strip() for k in pos_text.split(",") if k.strip()]

        neg_text = self._neg_keywords_edit.text().strip()
        config.negative_keywords = [k.strip() for k in neg_text.split(",") if k.strip()]

        # 合并 4 类材料关键词（保持原 storage 兼容）
        materials = []
        for edit in (self._pos_mat_edit, self._neg_mat_edit, self._cond_mat_edit, self._tape_mat_edit):
            text = edit.text().strip()
            materials.extend(k.strip() for k in text.split(",") if k.strip())
        # 去重保序
        seen = set()
        config.lithium_battery_materials = [k for k in materials if not (k in seen or seen.add(k))]

        config.save()
        logger.debug("插件参数已保存")


# ═══════════════════════════════════════════════════════════
#  配置导入导出 Tab
# ═══════════════════════════════════════════════════════════

class _ImportExportTab(QWidget):
    """配置导入导出"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(16)

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
        export_desc.setStyleSheet("color: #6b7280; font-size: 12px;")
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
            "从 JSON 配置文件导入设置。导入后会覆盖当前配置。"
            "建议先导出当前配置作为备份。"
        )
        import_desc.setWordWrap(True)
        import_desc.setStyleSheet("color: #6b7280; font-size: 12px;")
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
        self._preview_text.setMaximumHeight(200)
        preview_layout.addWidget(self._preview_text)

        btn_refresh = QPushButton("刷新预览")
        btn_refresh.setObjectName("btn_secondary")
        btn_refresh.clicked.connect(self._refresh_preview)
        preview_layout.addWidget(btn_refresh, alignment=Qt.AlignmentFlag.AlignLeft)

        layout.addWidget(preview_group)
        layout.addStretch()

        self._refresh_preview()

    def _refresh_preview(self):
        """刷新配置预览"""
        data = config.export_settings()
        self._preview_text.setPlainText(
            json.dumps(data, ensure_ascii=False, indent=2)
        )

    def _on_export(self):
        """导出配置"""
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
        """导入配置"""
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
                "部分设置（如数据库路径）需要重启应用后生效。"
            )
            logger.info(f"配置已导入: {path}")
        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "JSON 解析失败", f"配置文件不是有效的 JSON:\n{e}")
        except Exception as e:
            QMessageBox.critical(self, "导入失败", f"导入配置时发生错误:\n{e}")


# ═══════════════════════════════════════════════════════════
#  主设置对话框
# ═══════════════════════════════════════════════════════════

class SettingsDialog(QDialog):
    """综合设置界面（Tab 组织三个模块）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Toolkit 综合设置")
        self.setMinimumSize(700, 580)
        self.resize(760, 620)
        self._apply_style()
        self._setup_ui()

    def _apply_style(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #fafbfc;
            }
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
                font-size: 13px;
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
            QLineEdit, QSpinBox, QComboBox {
                border: 1px solid #dcdfe6;
                border-radius: 4px;
                padding: 6px 10px;
                background-color: #ffffff;
                min-height: 28px;
                font-size: 13px;
            }
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
                border-color: #409eff;
            }
            QTextEdit {
                border: 1px solid #dcdfe6;
                border-radius: 4px;
                padding: 6px;
                background-color: #ffffff;
                font-family: "Consolas", "Microsoft YaHei", monospace;
                font-size: 12px;
            }
            QPushButton {
                padding: 8px 20px;
                border-radius: 4px;
                font-size: 13px;
                min-height: 32px;
            }
            QPushButton#btn_success {
                background-color: #67c23a;
                color: white;
                border: none;
            }
            QPushButton#btn_success:hover {
                background-color: #85ce61;
            }
            QPushButton#btn_primary {
                background-color: #409eff;
                color: white;
                border: none;
            }
            QPushButton#btn_primary:hover {
                background-color: #66b1ff;
            }
            QPushButton#btn_warning {
                background-color: #e6a23c;
                color: white;
                border: none;
            }
            QPushButton#btn_warning:hover {
                background-color: #ebb563;
            }
            QPushButton#btn_secondary {
                background-color: #909399;
                color: white;
                border: none;
            }
            QPushButton#btn_secondary:hover {
                background-color: #a6a9ad;
            }
        """)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        # 标题
        title = QLabel("⚙ 综合设置")
        title.setObjectName("title_label")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(title)

        # Tab 容器
        tabs = QTabWidget()

        self._network_tab = _NetworkTab()
        tabs.addTab(self._network_tab, "🌐 局域网配置")

        self._plugin_tab = _PluginTab()
        # Tab 标题用插件 display_name（与侧边栏一致），fallback 到 plugin name
        try:
            from plugins.peel_data.plugin import PeelDataPlugin
            plugin_display = PeelDataPlugin().display_name
        except Exception:
            plugin_display = "peel_data"
        tabs.addTab(self._plugin_tab, f"📋 {plugin_display} 参数")

        self._import_export_tab = _ImportExportTab()
        tabs.addTab(self._import_export_tab, "💾 导入/导出")

        layout.addWidget(tabs, stretch=1)

        # 底部按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_close = QPushButton("关闭")
        btn_close.setMinimumWidth(90)
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)

        layout.addLayout(btn_layout)
