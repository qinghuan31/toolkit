# -*- coding: utf-8 -*-
"""
Excel 文件解析器
提取剥离测试 Excel 报告中的结构化数据
"""

import os
from typing import Optional, List, Dict, Any

from core.logger import get_logger
from plugins.peel_data.models import PeelDataRecord

logger = get_logger("peel_data.excel_parser")


class ExcelParser:
    """Excel 剥离数据解析器"""

    CURVE_KEYWORDS = {
        "曲线1": "curve_1", "曲线2": "curve_2", "曲线3": "curve_3",
        "曲线4": "curve_4", "曲线5": "curve_5", "曲线6": "curve_6",
        "曲线7": "curve_7", "曲线8": "curve_8", "曲线9": "curve_9",
    }

    STD_KEYWORDS = [
        "标准差", "平均值的标准差", "Std", "SD", "A_Sd",
    ]

    # 试样名称关键字（映射到 sample_name）
    SAMPLE_NAME_KEYWORDS = [
        "试样名称", "样品名称", "样品名", "试样",
    ]

    # 试样牌号关键字（独立字段，映射到 sample_brand）
    SAMPLE_BRAND_KEYWORDS = [
        "试样牌号", "牌号", "样本编号",
    ]

    # 当提取到的试样名称仅为这些标签文字时，视为无效，需回退到文件名
    GENERIC_SAMPLE_NAMES = [
        "试样编号", "试样名称", "样品名称", "样品名", "试样", "编号", "名称", "",
        "试样牌号", "牌号",
    ]

    TIME_KEYWORDS = ["试验时间", "测试时间", "时间"]
    DATE_KEYWORDS = ["试验日期", "测试日期", "日期"]

    # 剥离强度单位关键字
    UNIT_KEYWORDS = ["单位", "unit", "Unit"]

    def parse(self, file_path: str) -> Optional[PeelDataRecord]:
        """解析单个 Excel 文件"""
        try:
            import openpyxl
        except ImportError:
            logger.error("openpyxl 未安装，请执行: pip install openpyxl")
            return None

        filename = os.path.basename(file_path)
        logger.debug(f"开始解析 Excel: {filename}")

        try:
            wb = openpyxl.load_workbook(file_path, data_only=True)
            record = PeelDataRecord()
            record.source_file = filename

            # 尝试在所有 sheet 中查找数据
            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                logger.debug(f"  检查 Sheet: {sheet_name}")

                found = self._parse_header_layout(ws, record)
                if not found:
                    self._parse_kv_layout(ws, record)

                # 提取单位
                if not record.curve_unit:
                    self._extract_unit(ws, record)

                has_any_curve = any(
                    getattr(record, f"curve_{i}") is not None
                    for i in range(1, 10)
                )
                if has_any_curve:
                    break

            # 清理并判定试样名称
            record = self._finalize_sample_name(record, filename)

            # 试样牌号：如果还是空，尝试从文件名提取
            if not record.sample_brand:
                record.sample_brand = self._extract_brand_from_filename(filename)

            # 判定极性（优先从试样名称，其次从文件名）
            record.polarity = self._determine_polarity(record.sample_name, filename)

            # 清理日期时间格式
            record = self._clean_datetime(record)

            # 验证有效性
            has_any_curve = any(
                getattr(record, f"curve_{i}") is not None
                for i in range(1, 10)
            )
            if not record.sample_name or not has_any_curve:
                logger.warning(f"Excel 未提取到有效数据: {filename}")
                return None

            logger.info(
                f"Excel 解析成功: {filename} -> "
                f"试样={record.sample_name}, 牌号={record.sample_brand}, 极性={record.polarity}"
            )
            return record

        except Exception as e:
            logger.error(f"Excel 解析异常 [{filename}]: {e}", exc_info=True)
            return None

    def _extract_brand_from_filename(self, filename: str) -> str:
        """从文件名中提取可能的牌号信息"""
        name_base = os.path.splitext(filename)[0]
        # 尝试匹配常见牌号格式：字母+数字组合
        import re
        match = re.search(r"([A-Z]+[-]?[0-9]+)", name_base, re.IGNORECASE)
        if match:
            return match.group(1)
        return ""

    def _finalize_sample_name(self, record: "PeelDataRecord", filename: str):
        """
        最终确定试样名称:
        1. 如果提取到的名称仅为标签文字(如"试样编号"), 回退到文件名
        2. 否则保留提取值
        """
        extracted = (record.sample_name or "").strip()

        # 检查是否为无效的标签文字
        is_generic = (
            not extracted
            or extracted in self.GENERIC_SAMPLE_NAMES
            or any(extracted == g for g in self.GENERIC_SAMPLE_NAMES)
        )

        if is_generic:
            # 回退到文件名（去掉扩展名）
            name_base = os.path.splitext(filename)[0]
            record.sample_name = name_base
            logger.debug(f"试样名称回退到文件名: {name_base}")
        else:
            record.sample_name = extracted

        return record

    @staticmethod
    def _determine_polarity(sample_name: str, filename: str) -> str:
        """从试样名称和文件名中综合判定极性"""
        from config import config

        # 先尝试从试样名称判定
        name_lower = sample_name.lower()
        for kw in config.positive_keywords:
            if kw.lower() in name_lower:
                return "正极"
        for kw in config.negative_keywords:
            if kw.lower() in name_lower:
                return "负极"

        # 若试样名称未命中，尝试从文件名判定
        file_lower = filename.lower()
        for kw in config.positive_keywords:
            if kw.lower() in file_lower:
                return "正极"
        for kw in config.negative_keywords:
            if kw.lower() in file_lower:
                return "负极"

        return "未知"

    @staticmethod
    def _clean_datetime(record: PeelDataRecord) -> PeelDataRecord:
        """清理日期和时间格式"""
        if record.test_date and " " in record.test_date:
            record.test_date = record.test_date.split(" ")[0].strip()
        return record

    def _parse_header_layout(self, ws, record: PeelDataRecord) -> bool:
        """解析表头行式布局"""
        header_row = None
        col_map: Dict[str, int] = {}

        for row_idx in range(1, min(11, ws.max_row + 1)):
            for col_idx in range(1, ws.max_column + 1):
                cell_val = ws.cell(row=row_idx, column=col_idx).value
                if cell_val is None:
                    continue
                val_str = str(cell_val).strip()

                # 匹配曲线列
                for keyword, attr in self.CURVE_KEYWORDS.items():
                    if keyword in val_str and attr not in col_map:
                        col_map[attr] = col_idx

                # 匹配标准差列
                for kw in self.STD_KEYWORDS:
                    if kw in val_str and "std_col" not in col_map:
                        col_map["std_col"] = col_idx

                # 匹配试样名称（取右侧单元格的值）
                for kw in self.SAMPLE_NAME_KEYWORDS:
                    if kw in val_str and "sample_col" not in col_map:
                        col_map["sample_col"] = col_idx

                # 匹配试样牌号（独立字段）
                for kw in self.SAMPLE_BRAND_KEYWORDS:
                    if kw in val_str and "brand_col" not in col_map:
                        col_map["brand_col"] = col_idx

                # 匹配时间
                for kw in self.TIME_KEYWORDS:
                    if kw in val_str and "time_col" not in col_map:
                        col_map["time_col"] = col_idx

                # 匹配日期
                for kw in self.DATE_KEYWORDS:
                    if kw in val_str and "date_col" not in col_map:
                        col_map["date_col"] = col_idx

            if col_map:
                header_row = row_idx
                break

        if header_row is None or not col_map:
            return False

        # 读取数据行（表头下一行）
        data_row = header_row + 1
        if data_row > ws.max_row:
            return False

        for attr, col_idx in col_map.items():
            # 对于关键字匹配的列，取右侧单元格的值
            read_col = col_idx + 1 if attr.endswith("_col") else col_idx
            val = ws.cell(row=data_row, column=read_col).value
            if val is None:
                continue

            if attr == "sample_col":
                record.sample_name = str(val).strip()
            elif attr == "brand_col":
                record.sample_brand = str(val).strip()
            elif attr == "time_col":
                record.test_time = str(val).strip()
            elif attr == "date_col":
                record.test_date = str(val).strip()
            elif attr == "std_col":
                try:
                    record.std_dev = float(val)
                except (ValueError, TypeError):
                    logger.debug(f"标准差转换失败: {val}")
            elif attr.startswith("curve_"):
                try:
                    setattr(record, attr, float(val))
                except (ValueError, TypeError):
                    logger.debug(f"曲线值转换失败: {attr}={val}")

        return any(
            getattr(record, f"curve_{i}") is not None
            for i in range(1, 10)
        )

    def _parse_kv_layout(self, ws, record: PeelDataRecord) -> bool:
        """解析键值对式布局"""
        found_any = False

        for row_idx in range(1, min(ws.max_row + 1, 100)):
            for col_idx in range(1, min(ws.max_column + 1, 20)):
                cell = ws.cell(row=row_idx, column=col_idx)
                if cell.value is None:
                    continue

                key = str(cell.value).strip()

                # 检查右侧单元格是否为值
                value_cell = ws.cell(row=row_idx, column=col_idx + 1)
                value = value_cell.value
                if value is None:
                    value_cell = ws.cell(row=row_idx + 1, column=col_idx)
                    value = value_cell.value
                if value is None:
                    continue

                value_str = str(value).strip()

                # 匹配试样名称
                for kw in self.SAMPLE_NAME_KEYWORDS:
                    if kw in key and not record.sample_name:
                        record.sample_name = value_str
                        found_any = True
                        break

                # 匹配试样牌号（独立字段）
                for kw in self.SAMPLE_BRAND_KEYWORDS:
                    if kw in key and not record.sample_brand:
                        record.sample_brand = value_str
                        found_any = True
                        break

                # 匹配曲线
                for keyword, attr in self.CURVE_KEYWORDS.items():
                    if keyword in key:
                        try:
                            setattr(record, attr, float(value))
                            found_any = True
                        except (ValueError, TypeError):
                            pass

                # 匹配标准差
                for kw in self.STD_KEYWORDS:
                    if kw in key and record.std_dev is None:
                        try:
                            record.std_dev = float(value)
                            found_any = True
                        except (ValueError, TypeError):
                            pass

                # 匹配时间/日期
                for kw in self.TIME_KEYWORDS:
                    if kw in key and not record.test_time:
                        record.test_time = value_str
                        found_any = True

                for kw in self.DATE_KEYWORDS:
                    if kw in key and not record.test_date:
                        record.test_date = value_str
                        found_any = True

        return found_any

    def _extract_unit(self, ws, record: PeelDataRecord):
        """从 Excel 中提取剥离强度单位"""
        try:
            import re
            for row_idx in range(1, min(ws.max_row + 1, 50)):
                for col_idx in range(1, min(ws.max_column + 1, 20)):
                    cell = ws.cell(row=row_idx, column=col_idx)
                    if cell.value is None:
                        continue
                    val_str = str(cell.value).strip()

                    # 匹配"单位：kN/m"格式
                    for kw in self.UNIT_KEYWORDS:
                        if kw in val_str:
                            # 尝试取右侧单元格
                            right_val = ws.cell(row=row_idx, column=col_idx + 1).value
                            if right_val:
                                unit = str(right_val).strip()
                                if unit:
                                    record.curve_unit = unit
                                    logger.debug(f"  剥离强度单位 = {unit}")
                                    return
                            # 也可以尝试从当前单元格值中提取（如"单位: kN/m"）
                            parts = re.split(r"[=：:\s]+", val_str, maxsplit=1)
                            if len(parts) >= 2 and parts[1].strip():
                                record.curve_unit = parts[1].strip()
                                logger.debug(f"  剥离强度单位 = {record.curve_unit}")
                                return

                    # 备用：从"剥离强度 (kN/m)"格式提取
                    match = re.search(
                        r"(?:剥离强度|peel\s*strength)\s*[（(]([^）)]+)[）)]",
                        val_str, re.IGNORECASE
                    )
                    if match:
                        record.curve_unit = match.group(1).strip()
                        logger.debug(f"  剥离强度单位 = {record.curve_unit}")
                        return
        except Exception as e:
            logger.debug(f"单位提取异常: {e}")

    def parse_batch(self, file_paths: List[str]) -> List[PeelDataRecord]:
        """批量解析 Excel 文件"""
        results = []
        for fp in file_paths:
            record = self.parse(fp)
            if record:
                results.append(record)
        return results
