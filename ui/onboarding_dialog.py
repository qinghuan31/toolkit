# -*- coding: utf-8 -*-
"""首次使用引导对话框。"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)


_MODE_OPTIONS = [
    {
        "key": "local",
        "title": "单机使用",
        "badge": "推荐",
        "desc": "数据只保存在这台电脑，适合个人处理文件。",
        "steps": "选目录 → 提取 → 保存/导出",
    },
    {
        "key": "server",
        "title": "作为主机",
        "badge": "共享",
        "desc": "这台电脑开放局域网服务，其他设备可连接同一数据库。",
        "steps": "开服务 → 分机连接 → 共同查看",
    },
    {
        "key": "client",
        "title": "连接主机",
        "badge": "分机",
        "desc": "连接已有主机地址，直接查看或写入主机数据库。",
        "steps": "填地址 → 验证连接 → 开始使用",
    },
]


class OnboardingDialog(QDialog):
    """首次启动时让用户明确选择运行模式。"""

    def __init__(self, current_mode: str = "local", parent=None):
        super().__init__(parent)
        self._selected_mode = current_mode if current_mode in {m["key"] for m in _MODE_OPTIONS} else "local"
        self._skipped = False
        self._cards = {}
        self._setup_ui()
        self._apply_style()
        self._select_mode(self._selected_mode)

    @property
    def selected_mode(self) -> str:
        return self._selected_mode

    @property
    def skipped(self) -> bool:
        return self._skipped

    def _setup_ui(self):
        self.setWindowTitle("首次设置")
        self.setModal(True)
        self.setMinimumSize(760, 520)
        self.resize(820, 560)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 22)
        root.setSpacing(18)

        top_row = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(6)

        value = QLabel("快速汇总剥离数据")
        value.setObjectName("value_label")
        title_box.addWidget(value)

        subtitle = QLabel("先选择这台电脑的使用方式，后续可在「综合设置」随时切换。")
        subtitle.setObjectName("subtitle_label")
        subtitle.setWordWrap(True)
        title_box.addWidget(subtitle)
        top_row.addLayout(title_box, stretch=1)

        self._btn_skip_top = QPushButton("跳过")
        self._btn_skip_top.setObjectName("btn_skip")
        self._btn_skip_top.setFixedWidth(84)
        self._btn_skip_top.clicked.connect(self._skip)
        top_row.addWidget(self._btn_skip_top, alignment=Qt.AlignmentFlag.AlignTop)
        root.addLayout(top_row)

        path = QLabel("推荐路径：① 选模式  →  ② 选数据目录  →  ③ 一键提取")
        path.setObjectName("path_label")
        root.addWidget(path)

        card_row = QHBoxLayout()
        card_row.setSpacing(14)
        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)

        for option in _MODE_OPTIONS:
            card = self._create_mode_card(option)
            self._cards[option["key"]] = card
            card_row.addWidget(card, stretch=1)
        root.addLayout(card_row, stretch=1)

        hint = QLabel("提示：如果不确定，选择「单机使用」。联机相关参数可以稍后在综合设置里补齐。")
        hint.setObjectName("hint_label")
        hint.setWordWrap(True)
        root.addWidget(hint)

        footer = QHBoxLayout()
        footer.setSpacing(10)
        footer.addStretch()

        self._btn_skip_bottom = QPushButton("跳过，以后再设置")
        self._btn_skip_bottom.setObjectName("btn_secondary")
        self._btn_skip_bottom.clicked.connect(self._skip)
        footer.addWidget(self._btn_skip_bottom)

        self._btn_continue = QPushButton("进入 Toolkit")
        self._btn_continue.setObjectName("btn_primary")
        self._btn_continue.setMinimumWidth(130)
        self._btn_continue.clicked.connect(self.accept)
        footer.addWidget(self._btn_continue)
        root.addLayout(footer)

    def _create_mode_card(self, option: dict) -> QFrame:
        card = QFrame()
        card.setObjectName("mode_card")
        card.setProperty("mode", option["key"])
        card.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        head = QHBoxLayout()
        radio = QRadioButton(option["title"])
        radio.setObjectName("mode_radio")
        radio.toggled.connect(lambda checked, key=option["key"]: self._select_mode(key) if checked else None)
        self._button_group.addButton(radio)
        card._radio = radio
        head.addWidget(radio, stretch=1)

        badge = QLabel(option["badge"])
        badge.setObjectName("mode_badge")
        head.addWidget(badge)
        layout.addLayout(head)

        desc = QLabel(option["desc"])
        desc.setObjectName("mode_desc")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        steps = QLabel(option["steps"])
        steps.setObjectName("mode_steps")
        steps.setWordWrap(True)
        layout.addWidget(steps)
        layout.addStretch()

        card.mousePressEvent = lambda event, key=option["key"]: self._select_mode(key)
        return card

    def _select_mode(self, mode: str):
        self._selected_mode = mode
        for key, card in self._cards.items():
            selected = key == mode
            card.setProperty("selected", "true" if selected else "false")
            card._radio.blockSignals(True)
            card._radio.setChecked(selected)
            card._radio.blockSignals(False)
            card.style().unpolish(card)
            card.style().polish(card)
            card.update()

    def _skip(self):
        self._skipped = True
        self._selected_mode = "local"
        self.accept()

    def _apply_style(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #f6f7f9;
                font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
                color: #1f2937;
            }
            QLabel#value_label {
                font-size: 28px;
                font-weight: 800;
                color: #111827;
                letter-spacing: 0.4px;
            }
            QLabel#subtitle_label, QLabel#hint_label {
                color: #6b7280;
                font-size: 13px;
                line-height: 1.5;
            }
            QLabel#path_label {
                background-color: #eef6ff;
                color: #1d4ed8;
                border: 1px solid #bfdbfe;
                border-radius: 10px;
                padding: 10px 14px;
                font-size: 13px;
                font-weight: 600;
            }
            QFrame#mode_card {
                background-color: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 14px;
            }
            QFrame#mode_card:hover {
                border-color: #93c5fd;
                background-color: #f8fbff;
            }
            QFrame#mode_card[selected="true"] {
                border: 2px solid #2563eb;
                background-color: #eff6ff;
            }
            QRadioButton#mode_radio {
                color: #111827;
                font-size: 17px;
                font-weight: 700;
                spacing: 8px;
            }
            QLabel#mode_badge {
                background-color: #dbeafe;
                color: #1e40af;
                border-radius: 9px;
                padding: 2px 8px;
                font-size: 12px;
                font-weight: 700;
            }
            QLabel#mode_desc {
                color: #4b5563;
                font-size: 13px;
                line-height: 1.5;
            }
            QLabel#mode_steps {
                color: #047857;
                background-color: #ecfdf5;
                border-radius: 8px;
                padding: 8px 10px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton {
                border-radius: 8px;
                padding: 8px 16px;
                min-height: 34px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton#btn_primary {
                background-color: #2563eb;
                color: white;
                border: 1px solid #2563eb;
            }
            QPushButton#btn_primary:hover { background-color: #1d4ed8; }
            QPushButton#btn_secondary, QPushButton#btn_skip {
                background-color: #ffffff;
                color: #374151;
                border: 1px solid #d1d5db;
            }
            QPushButton#btn_secondary:hover, QPushButton#btn_skip:hover {
                background-color: #f3f4f6;
            }
        """)
