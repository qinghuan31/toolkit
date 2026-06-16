# -*- coding: utf-8 -*-
"""全局配置模块"""

import json
import os
from dataclasses import dataclass, field
from typing import Optional, Tuple


@dataclass
class DatabaseConfig:
    """数据库配置（SQLite）"""
    # SQLite 数据库文件路径，空字符串则使用项目根目录下 data/app.db
    database_path: str = ""

    # 【v1.6.0】网络共享模式 —— 局域网多设备访问同一数据库
    # 模式选项:
    #   "local"     - 默认,只访问本机 SQLite 文件
    #   "server"    - 监听 HTTP API,其他设备通过 HTTP 访问
    #   "client"    - 客户端模式,只访问 server 的 API,不直接动 SQLite
    network_mode: str = "local"

    # 当 network_mode="server" 时,HTTP 监听地址
    server_host: str = "0.0.0.0"
    server_port: int = 8765

    # 当 network_mode="client" 时,server 的访问地址
    # 例: http://192.168.1.100:8765
    server_url: str = ""

    # API 鉴权 token(可选,空字符串=无鉴权,内部用时建议设置)
    api_token: str = ""

    # 【v1.7.0】客户端写入限制
    # True  = 客户端可读可写（默认，兼容旧行为）
    # False = 客户端只能查询，insert/update/delete 被服务端拒绝（403）
    server_allow_write: bool = True

    # 【v1.7.0】局域网设备自动发现 —— 启动时按子网扫描其他 Toolkit 实例
    # 扫描子网掩码位数 (例: 24 表示扫描 192.168.1.0/24)
    discovery_cidr_prefix: int = 24
    # 扫描超时（秒）
    discovery_timeout: float = 0.5
    # 发现的设备列表缓存（不持久化,启动时清空）
    discovered_devices: list = field(default_factory=list)

    @property
    def resolved_path(self) -> str:
        if self.database_path:
            return self.database_path
        return os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "data", "app.db"
        )


@dataclass
class AppConfig:
    """应用全局配置"""
    app_name: str = "Toolkit"
    # 【v1.5.1 单一来源】全项目版本号统一从此处读取
    # 不再在 plugin.py / main_window.py / toolkit.spec / release.yml 硬编码
    app_version: str = "1.8.0"
    organization: str = "WorkBuddy"

    # GitHub 仓库信息 —— 用于自动更新检查
    github_owner: str = "qinghuan31"
    github_repo: str = "toolkit"
    # 代理前缀 —— 国内加速 GitHub 下载(可改可禁)
    github_proxy: str = "https://gh-proxy.org/"

    # 首次使用引导
    onboarding_completed: bool = False

    # 数据目录（动态持久化：首次为空，用户选择后自动保存，下次启动自动回填）
    last_data_dir: str = ""

    # UI 状态（窗口位置/大小等，非业务配置）
    ui_window_geometry: dict = field(default_factory=dict)

    # 数据库配置
    db: DatabaseConfig = field(default_factory=DatabaseConfig)

    # 正负极匹配规则 —— 按优先级从高到低匹配
    # 正极关键字：试样名称包含以下任一关键字则判定为正极
    positive_keywords: list = field(default_factory=lambda: [
        "正极", "阳极", "Al", "铝箔", "铝", "cathode", "positive",
    ])
    # 负极关键字：试样名称包含以下任一关键字则判定为负极
    negative_keywords: list = field(default_factory=lambda: [
        "负极", "阴极", "Cu", "铜箔", "铜", "anode", "negative",
    ])

    # 锂电池制作材料关键词库 —— 用于辅助判断极性和识别试样类型
    # 出现在试样名称中可作为锂电池材料的指示符，结合正负极关键字一起判断
    lithium_battery_materials: list = field(default_factory=lambda: [
        # 导电液类
        "导电液", "单壁管导电液", "多壁管导电液", "碳管导电液",
        "CNT导电液", "碳纳米管导电液", "石墨烯导电液", "银浆",
        # 导电剂/碳材料
        "KS-6", "SP-Li", "SP", "KS6", "SuperP", "Super-P",
        "乙炔黑", "导电炭黑", "VGCF", "气相生长碳纤维",
        # 石墨类
        "石墨", "人造石墨", "天然石墨", "球形石墨", "鳞片石墨",
        "中间相碳微球", "MCMB", "中间相沥青",
        # 三元类
        "三元", "NCM", "NCA", "LFP", "磷酸铁锂", "钴酸锂", "LCO",
        "锰酸锂", "LMO", "镍钴锰", "镍钴铝",
        # 粘结剂
        "PVDF", "聚偏氟乙烯", "CMC", "丁苯橡胶", "SBR",
        "丁腈橡胶", "NBR", "水性粘结剂",
        # 高温胶/膨胀胶
        "高温胶", "膨胀胶", "阻燃胶", "导热胶", "结构胶",
        "耐高温胶", "耐低温胶",
        # 硅基材料
        "硅碳", "硅基", "SiO", "氧化亚硅", "硅氧", "硅纳米",
        "纳米硅", "硅粉", "多孔硅",
        # 隔膜/电解液
        "隔膜", "PE隔膜", "PP隔膜", "陶瓷隔膜", "电解液",
        # 集流体
        "铝箔", "铜箔", "复合箔", "涂炭铝箔", "涂炭铜箔",
        # 其他常见
        "正极材料", "负极材料", "极片", "浆料", "导电剂",
    ])

    # 日志配置
    log_dir: str = ""
    log_level: str = "INFO"
    log_max_bytes: int = 10 * 1024 * 1024  # 10MB
    log_backup_count: int = 5

    def __post_init__(self):
        if not self.log_dir:
            self.log_dir = os.path.join(
                os.path.expanduser("~"), ".toolkit", "logs"
            )
        # 加载持久化配置（上次数据目录）
        self.load()

    # ── JSON 持久化：数据目录记忆 ──
    @property
    def _config_file(self) -> str:
        """配置文件路径：{toolkit}/data/app_config.json"""
        return os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "data", "app_config.json"
        )

    def save(self):
        """将全部配置持久化到 JSON 文件（失败静默忽略）"""
        try:
            config_dir = os.path.dirname(self._config_file)
            os.makedirs(config_dir, exist_ok=True)
            data = self.export_settings()
            with open(self._config_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass  # 不影响主功能

    def load(self):
        """从 JSON 配置文件读取全部设置（失败则以默认值兜底）"""
        try:
            if os.path.isfile(self._config_file):
                with open(self._config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self.import_settings(data)
        except Exception:
            self.last_data_dir = ""

    def export_settings(self) -> dict:
        """导出全部配置为字典（供 save / 导出功能使用）"""
        return {
            "onboarding_completed": self.onboarding_completed,
            "last_data_dir": self.last_data_dir,
            "db": {
                "database_path": self.db.database_path,
                "network_mode": self.db.network_mode,
                "server_host": self.db.server_host,
                "server_port": self.db.server_port,
                "server_url": self.db.server_url,
                "api_token": self.db.api_token,
                "server_allow_write": self.db.server_allow_write,
            },
            "positive_keywords": self.positive_keywords,
            "negative_keywords": self.negative_keywords,
            "lithium_battery_materials": self.lithium_battery_materials,
            "github_proxy": self.github_proxy,
            "ui_window_geometry": self.ui_window_geometry,
        }

    def import_settings(self, data: dict):
        """从字典导入配置（兼容缺失字段，不会因缺少某个 key 而崩溃）"""
        if not isinstance(data, dict):
            return
        self.onboarding_completed = bool(data.get("onboarding_completed", self.onboarding_completed))
        self.last_data_dir = data.get("last_data_dir", self.last_data_dir)
        # 数据库配置
        db_data = data.get("db", {})
        if isinstance(db_data, dict):
            self.db.database_path = db_data.get("database_path", self.db.database_path)
            self.db.network_mode = db_data.get("network_mode", self.db.network_mode)
            self.db.server_host = db_data.get("server_host", self.db.server_host)
            self.db.server_port = db_data.get("server_port", self.db.server_port)
            self.db.server_url = db_data.get("server_url", self.db.server_url)
            self.db.api_token = db_data.get("api_token", self.db.api_token)
            self.db.server_allow_write = db_data.get("server_allow_write", self.db.server_allow_write)
        # 关键词
        if "positive_keywords" in data and isinstance(data["positive_keywords"], list):
            self.positive_keywords = data["positive_keywords"]
        if "negative_keywords" in data and isinstance(data["negative_keywords"], list):
            self.negative_keywords = data["negative_keywords"]
        if "lithium_battery_materials" in data and isinstance(data["lithium_battery_materials"], list):
            self.lithium_battery_materials = data["lithium_battery_materials"]
        # GitHub 代理
        if "github_proxy" in data:
            self.github_proxy = data["github_proxy"]
        # UI 状态
        ui_window_geometry = data.get("ui_window_geometry", {})
        if isinstance(ui_window_geometry, dict):
            self.ui_window_geometry = ui_window_geometry

    # ── 试样名称提取（共享工具，供 excel_parser / pdf_parser 调用） ──
    @staticmethod
    def extract_sample_name_from_filename(filename: str) -> Optional[str]:
        """
        从文件名中提取试样名称（优先级最高的来源）

        规则：
        1. 移除扩展名
        2. 移除常见前缀（PDF转EXCEL文件、EXCEL、PDF 等）
        3. 移除尾部的日期/序号（_20260610、_001 等）
        4. 保留完整的"正极"/"负极"前缀
        5. 替换分隔符（_ - . 空格 → 空格）
        6. 合并多余空格

        示例：
            "INR21700-40PE  6μm铜箔负极.pdf" → "INR21700-40PE  6μm铜箔负极"
            "PDF\\INR21700-40PE  4000-8C正极.pdf" → "INR21700-40PE  4000-8C正极"
            "EXCEL\\26V2(zc干法)正极（涂碳铝箔）第二锅.xlsx" → "26V2(zc干法)正极（涂碳铝箔）第二锅"
        """
        if not filename:
            return None

        import re as _re

        # 1. 取 basename
        name = os.path.basename(filename)
        # 2. 移除扩展名
        name = _re.sub(r"\.(pdf|xlsx?|xlsm|xlsb|csv)$", "", name, flags=_re.IGNORECASE)
        # 3. 移除常见前缀
        prefixes_to_strip = [
            r"^PDF[\\/\-]?转EXCEL文件[\\/\-]?",
            r"^PDF[\\/\-]+",
            r"^EXCEL[\\/\-]+",
            r"^PDF转[\\/\-]+",
        ]
        for pat in prefixes_to_strip:
            name = _re.sub(pat, "", name, flags=_re.IGNORECASE)
        # 4. 移除尾部日期/序号
        name = _re.sub(r"[_\-\s]+(\d{8}|\d{6}|\d{4}[01]\d[0-3]\d)$", "", name)
        name = _re.sub(r"[_\-\s]+(副本|backup|v\d+)$", "", name, flags=_re.IGNORECASE)
        # 5. 替换分隔符为统一空格（保留字母数字之间的连字符，如 INR21700-40PE）
        name = _re.sub(r"[_\s]+", " ", name)
        # 只替换前后是空格或标点的连字符，保留型号中的连字符
        name = _re.sub(r"(?<![A-Za-z0-9])\-(?![A-Za-z0-9])", " ", name)
        name = _re.sub(r"\.(?=[^\w]|$)", " ", name)  # 句点（非扩展名）替换为空格
        # 6. 合并多余空格
        name = _re.sub(r"\s+", " ", name).strip()
        # 7. 过滤掉通用/无意义的名称（如 "test", "data", "新建文件夹"）
        generic_names = {
            "test", "data", "new", "temp", "tmp", "新建", "副本",
            "test1", "test2", "sample", "example", "untitled",
            "新建文件夹", "新建 XLSX 工作表", "新建 PDF 文档",
            "Book1", "Sheet1", "Document1",
        }
        if name.lower() in {g.lower() for g in generic_names}:
            return None
        # 8. 过滤掉纯数字/序号名称
        if _re.match(r"^\d+$", name):
            return None
        return name if name else None

    @staticmethod
    def extract_sample_name_by_polarity_prefix(text: str) -> Optional[str]:
        """
        从文本中提取带"正极"或"负极"前缀的完整名称

        规则：从"正极"/"负极"往前回溯到字符串开头或上一个明显的边界
        （左括号、空格、字母数字），形成完整的名称。
        如果没找到"正极"/"负极"前缀则返回 None。

        示例：
            "INR21700-40PE  6μm铜箔负极" → "INR21700-40PE  6μm铜箔负极"
            "INR18650-20PLX 2000-8C正极" → "INR18650-20PLX 2000-8C正极"
            "26V2(zc干法)正极（涂碳铝箔）第二锅" → "26V2(zc干法)正极（涂碳铝箔）第二锅"
        """
        if not text:
            return None

        import re as _re

        # 查找"正极"或"负极"位置
        m = _re.search(r"(正极|负极)", text)
        if not m:
            return None

        # 从匹配位置开始，往前回溯到合理起点
        # 起点：字符串开头 OR 最近的"。；"标点 OR 上一个完整的"词"
        start = 0
        prefix = text[: m.end()]
        # 寻找前缀中是否有自然的边界（如"|"、";"）
        for sep in ["|", ";", "\n"]:
            idx = prefix.rfind(sep)
            if idx >= 0:
                start = idx + 1
                break

        result = text[start:].strip()
        # 清理：移除尾部多余空格/标点
        result = _re.sub(r"\s+", " ", result).strip(" ，,。；;")
        return result if result else None

    @staticmethod
    def match_material_keywords(text: str) -> list:
        """
        从文本中匹配锂电池制作材料关键词

        Returns:
            匹配到的关键词列表（按出现顺序）
        """
        if not text:
            return []

        found = []
        text_lower = text.lower()
        for kw in config.lithium_battery_materials:
            if kw.lower() in text_lower and kw not in found:
                found.append(kw)
        return found

    @staticmethod
    def determine_polarity_with_materials(
        sample_name: str, filename: str
    ) -> Tuple[str, list]:
        """
        极性判定：先正负极关键字，再用材料关键词辅助

        Returns:
            (极性, 匹配到的材料关键词列表)
        """
        sample_name = sample_name or ""
        filename = filename or ""
        name_lower = sample_name.lower()
        file_lower = filename.lower()

        # 第一轮：正负极关键字
        for kw in config.positive_keywords:
            if kw.lower() in name_lower or kw.lower() in file_lower:
                return "正极", config.match_material_keywords(sample_name)
        for kw in config.negative_keywords:
            if kw.lower() in name_lower or kw.lower() in file_lower:
                return "负极", config.match_material_keywords(sample_name)

        # 第二轮：材料关键词辅助
        # 含铝相关 → 正极；含铜相关 → 负极
        materials = config.match_material_keywords(sample_name)
        for m in materials:
            ml = m.lower()
            # 铝箔/铝 → 正极材料
            if "铝" in m and "铜" not in m:
                return "正极", materials
            # 铜箔/铜 → 负极材料
            if "铜" in m and "铝" not in m:
                return "负极", materials
            # 石墨 → 负极
            if "石墨" in m:
                return "负极", materials
            # 三元/NCM/NCA/LFP/LCO → 正极
            if m in ("三元", "NCM", "NCA", "LFP", "磷酸铁锂", "钴酸锂", "LCO", "锰酸锂", "LMO"):
                return "正极", materials
            # 硅碳/SiO → 负极
            if m in ("硅碳", "硅基", "SiO", "氧化亚硅", "硅氧", "纳米硅"):
                return "负极", materials

        return "未知", materials


# === 版本号工具函数 ===

def get_version() -> str:
    """获取当前应用版本(单一来源)"""
    return config.app_version


def bump_version(level: str = "patch") -> str:
    """
    升版号
    - 'major' / 'minor' / 'patch' 三选一
    - 返回新版本号(同时已写回 config.app_version)
    """
    import re
    v = config.app_version
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)$", v)
    if not m:
        raise ValueError(f"版本号格式不规范: {v}")
    major, minor, patch = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if level == "major":
        major += 1
        minor, patch = 0, 0
    elif level == "minor":
        minor += 1
        patch = 0
    elif level == "patch":
        patch += 1
    else:
        raise ValueError(f"未知升版级别: {level}")
    new_v = f"{major}.{minor}.{patch}"
    config.app_version = new_v
    return new_v


# 全局单例
config = AppConfig()
