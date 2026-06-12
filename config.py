# -*- coding: utf-8 -*-
"""全局配置模块"""

import json
import os
from dataclasses import dataclass, field
from typing import Optional, Tuple


@dataclass
class DatabaseConfig:
    """数据库配置（SQLite）"""
    # SQLite 数据库文件路径，空字符串则使用项目根目录下 data/toolkit.db
    database_path: str = ""

    @property
    def resolved_path(self) -> str:
        if self.database_path:
            return self.database_path
        return os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "data", "toolkit.db"
        )


@dataclass
class AppConfig:
    """应用全局配置"""
    app_name: str = "Toolkit"
    app_version: str = "1.0.0"
    organization: str = "WorkBuddy"

    # 数据目录（动态持久化：首次为空，用户选择后自动保存，下次启动自动回填）
    last_data_dir: str = ""

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
        """将 last_data_dir 持久化到 JSON 配置文件（失败静默忽略）"""
        try:
            config_dir = os.path.dirname(self._config_file)
            os.makedirs(config_dir, exist_ok=True)
            data = {"last_data_dir": self.last_data_dir}
            with open(self._config_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass  # 不影响主功能

    def load(self):
        """从 JSON 配置文件读取 last_data_dir（失败则以空字符串兜底）"""
        try:
            if os.path.isfile(self._config_file):
                with open(self._config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and "last_data_dir" in data:
                    self.last_data_dir = data["last_data_dir"]
        except Exception:
            self.last_data_dir = ""

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


# 全局单例
config = AppConfig()
