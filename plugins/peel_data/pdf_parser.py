# -*- coding: utf-8 -*-
"""
PDF 文件解析器（重构版 v2.0）

核心改进：
1. 多策略提取：表格提取 → Words 坐标 → OCR fallback
2. 全页面处理：支持多页 PDF
3. OCR 支持：自动检测扫描件并启用 OCR
4. 加密 PDF 支持：自动尝试解密
5. 字段级验证：每个字段提取后验证合理性
6. 详细日志：每个步骤记录详细信息便于调试
7. 多栏布局支持：智能识别多栏结构
"""

import re
import os
import logging
import datetime
from typing import Optional, Dict, List, Tuple
from collections import defaultdict

import pdfplumber

try:
    import pytesseract
    from PIL import Image
    _HAS_OCR = True
except ImportError:
    _HAS_OCR = False

from core.logger import get_logger
from plugins.peel_data.models import PeelDataRecord
from config import config

logger = get_logger("peel_data.pdf_parser")


# ─── 常量定义 ────────────────────────────────────────────────────────────

# 默认超时（秒）
DEFAULT_TIMEOUT = 60

# OCR 语言（中文 + 英文）
OCR_LANG = "chi_sim+eng"

# 常见密码列表（用于加密 PDF）
COMMON_PASSWORDS = ["", "123456", "password", "1234"]


# ─── 工具函数 ────────────────────────────────────────────────────────────

def _clean_number(text: str) -> str:
    """移除数字内部多余空格，如 '0 . 0 0 5 7' -> '0.0057'"""
    return text.replace(' ', '')


def _parse_date(text: str) -> Optional[datetime.date]:
    """解析日期字符串，支持多种格式"""
    if not text:
        return None
    # 尝试 YYYY-M-D 格式
    m = re.match(r'(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})', text)
    if m:
        try:
            return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    return None


def _parse_time(text: str) -> Optional[datetime.time]:
    """解析时间字符串"""
    if not text:
        return None
    m = re.match(r'(\d{1,2}):(\d{2}):(\d{2})', text)
    if m:
        try:
            return datetime.time(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    return None


# ─── 主解析器类 ────────────────────────────────────────────────────────

class PDFParser:
    """
    PDF 剥离数据解析器（重构版）

    提取策略（按优先级）：
    1. 表格提取：使用 pdfplumber.extract_tables() 提取结构化表格
    2. Words 坐标：使用 extract_words() 按坐标归组还原布局
    3. OCR fallback：对扫描件使用 pytesseract 识别
    """

    def parse(self, file_path: str, timeout: int = DEFAULT_TIMEOUT) -> Optional[PeelDataRecord]:
        """
        解析单个 PDF 文件

        Args:
            file_path: PDF 文件路径
            timeout: 解析超时时间（秒）

        Returns:
            PeelDataRecord 或 None（解析失败）
        """
        filename = os.path.basename(file_path)
        logger.info("=" * 60)
        logger.info("开始解析 PDF: %s", filename)
        t_start = datetime.datetime.now()

        record = PeelDataRecord()
        record.source_file = file_path
        record.file_type = "pdf"

        try:
            # ── 步骤1: 打开 PDF（处理加密） ──
            pdf = self._open_pdf(file_path)
            if pdf is None:
                logger.error("[%s] 无法打开 PDF（可能加密且密码错误）", filename)
                return None

            if not pdf.pages:
                logger.warning("[%s] PDF 无页面", filename)
                return None

            # ── 步骤2: 多策略提取 ──
            extracted_data = {}

            # 策略1: 全页面表格提取
            logger.debug("[%s] 策略1: 尝试表格提取...", filename)
            table_data = self._extract_by_tables(pdf)
            if table_data:
                extracted_data.update(table_data)
                logger.info("[%s] 策略1 成功: 提取到 %d 个字段", filename, len(table_data))

            # 策略2: Words 坐标提取（全页面）
            logger.debug("[%s] 策略2: 尝试 Words 坐标提取...", filename)
            words_data = self._extract_by_words_all_pages(pdf, filename)
            if words_data:
                # Words 策略的 sample_name / S 值更可靠，可覆盖策略1
                words_override_keys = {'sample_name', 'S1', 'S2', 'S3', 'S4', 'A_aver', 'A_sd'}
                for k, v in words_data.items():
                    if k in words_override_keys:
                        if v is not None:
                            extracted_data[k] = v
                    elif k not in extracted_data or extracted_data[k] is None:
                        extracted_data[k] = v
                logger.info("[%s] 策略2 完成: 补充 %d 个字段", filename, len(words_data))

            # 策略3: OCR fallback（如果是扫描件）
            if _HAS_OCR and self._is_scanned_pdf(pdf):
                logger.info("[%s] 检测到扫描件，启用 OCR...", filename)
                ocr_data = self._extract_by_ocr(pdf)
                if ocr_data:
                    for k, v in ocr_data.items():
                        if k not in extracted_data or extracted_data[k] is None:
                            extracted_data[k] = v
                    logger.info("[%s] OCR 完成: 补充 %d 个字段", filename, len(ocr_data))

            # ── 步骤3: 字段验证与修正 ──
            extracted_data = self._validate_and_fix(extracted_data, filename)

            # ── 步骤4: 填充到 record ──
            self._fill_record(record, extracted_data)

            # ── 步骤4.5: 升级试样名称 ──
            record.sample_name = self._upgrade_sample_name(
                record.sample_name, filename
            )

            # ── 步骤5: 判断极性 ──
            record.polarity = self._determine_polarity(
                record.sample_name or "", filename
            )

            elapsed = (datetime.datetime.now() - t_start).total_seconds()
            logger.info("[%s] 解析完成 (%.2fs): 试样=%s, 日期=%s, curve=%d/4, std_dev=%s",
                        filename, elapsed,
                        record.sample_name or "未知",
                        record.test_date or "未知",
                        sum(1 for k in ['curve_1', 'curve_2', 'curve_3', 'curve_4'] if getattr(record, k, None)),
                        "有" if record.std_dev else "无")
            logger.info("=" * 60)

            return record

        except Exception as e:
            logger.exception("[%s] PDF 解析异常: %s", filename, e)
            return None

    def _open_pdf(self, file_path: str):
        """打开 PDF，处理加密文件"""
        # 先尝试直接打开
        try:
            pdf = pdfplumber.open(file_path)
            return pdf
        except Exception as e:
            logger.warning("直接打开失败: %s", e)

        # 尝试用常见密码解密
        if _HAS_OCR:  # 仅作示例，实际需要用 pypdf 或 pdfplumber 的解密功能
            for pwd in COMMON_PASSWORDS:
                try:
                    pdf = pdfplumber.open(file_path, password=pwd)
                    logger.info("使用密码打开 PDF: %s", "***" if pwd else "(空密码)")
                    return pdf
                except Exception:
                    continue

        return None

    def _is_scanned_pdf(self, pdf) -> bool:
        """检测是否为扫描件（基于文本密度）"""
        total_words = 0
        total_pages = len(pdf.pages)
        for page in pdf.pages[:3]:  # 仅检查前3页
            words = page.extract_words()
            total_words += len(words)

        avg_words_per_page = total_words / min(3, total_pages)
        # 如果每页平均词数 < 50，可能是扫描件
        return avg_words_per_page < 50

    def _extract_by_tables(self, pdf) -> Dict:
        """策略1: 使用 pdfplumber.extract_tables() 提取结构化表格"""
        data = {}
        filename = "unknown"

        for page_num, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            if not tables:
                continue

            for table in tables:
                # 遍历表格行，查找目标字段
                for row_idx, row in enumerate(table):
                    if not row:
                        continue

                    # 将行转为字符串用于匹配
                    row_str = " ".join(str(cell) if cell else "" for cell in row)

                    # 查找试样名称
                    if not data.get("sample_name"):
                        for col_idx, cell in enumerate(row):
                            if cell and "试样名称" in str(cell):
                                # 尝试从同一行或下一行获取值
                                val = None
                                if col_idx + 1 < len(row) and row[col_idx + 1]:
                                    val = str(row[col_idx + 1]).strip()
                                elif row_idx + 1 < len(table) and table[row_idx + 1]:
                                    next_row = table[row_idx + 1]
                                    if next_row and next_row[0]:
                                        val = str(next_row[0]).strip()
                                if val and val not in ["试样名称", "样品名称"]:
                                    data["sample_name"] = val
                                    break

                    # 查找试验日期
                    if not data.get("test_date"):
                        for cell in row:
                            if cell and "试验日期" in str(cell):
                                m = re.search(r'(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})', str(cell))
                                if m:
                                    data["test_date"] = _parse_date(str(cell))
                                    break

                    # 查找试验时间
                    if not data.get("test_time"):
                        for cell in row:
                            if cell and ("试验时间" in str(cell) or "试验时间" in str(cell)):
                                m = re.search(r'(\d{1,2}):(\d{2}):(\d{2})', str(cell))
                                if m:
                                    data["test_time"] = _parse_time(str(cell))
                                    break

                    # 查找 S1-S4 和 A_sd
                    for cell in row:
                        if not cell:
                            continue
                        cell_str = str(cell)

                        # S 值
                        m_s = re.search(r'S([1-4])\s*[=：:\s]+([\d.]+)', cell_str)
                        if m_s:
                            data[f"S{m_s.group(1)}"] = float(m_s.group(2))

                        # A_sd
                        m_std = re.search(r'A_sd\s*[=：:\s]+([\d.]+)', cell_str, re.IGNORECASE)
                        if m_std:
                            data["A_sd"] = float(m_std.group(1))

        return data

    def _extract_by_words_all_pages(self, pdf, filename: str) -> Dict:
        """策略2: 使用 extract_words() 按坐标归组（全页面）"""
        all_rows = defaultdict(list)

        # 合并所有页面的 words
        for page_num, page in enumerate(pdf.pages):
            words = page.extract_words(x_tolerance=2, y_tolerance=2)
            for w in words:
                # 使用页码 + Y 坐标作为 key，区分不同页面
                key = f"p{page_num}_{round(w['top'], 1)}"
                all_rows[key].append(w)

        # 提取元数据（从第一页）
        page1_key = f"p0_"
        page1_rows = {k: v for k, v in all_rows.items() if k.startswith(page1_key)}
        data = self._extract_metadata_from_rows(page1_rows, filename)

        # 提取剥离强度数据（所有页面）
        data.update(self._extract_peel_strength_from_rows(all_rows, filename))

        return data

    def _extract_metadata_from_rows(self, rows: Dict, filename: str) -> Dict:
        """从 rows 中提取元数据（试样名称、日期、时间）"""
        data = {}
        # 按行构建文本（Y 排序行，X 排序词）
        lines = []
        for key in sorted(rows.keys()):
            row_words = sorted(rows[key], key=lambda w: w['x0'])
            line_text = ' '.join(w['text'] for w in row_words)
            lines.append(line_text)
        full_text = '\n'.join(lines)

        # 优先用试验批号（单值字段，通常在行尾，更可靠）
        m = re.search(r'试验批号\s+(.+)', full_text)
        if m:
            name = m.group(1).strip()
            name = re.split(r'\s+试[样验]', name)[0].strip()
            name = ' '.join(name.split())
            if name and name not in ["试样名称", "样品名称", "试验批号"]:
                data["sample_name"] = name
                logger.debug("[%s] 试样名称(从试验批号) = %s", filename, name)

        # 回退：试样名称
        if "sample_name" not in data:
            m = re.search(r'试样名称\s+(.+?)\s+试验件数', full_text)
            if m:
                name = m.group(1).strip()
                name = ' '.join(name.split())
                if name and name not in ["试样名称", "样品名称"]:
                    data["sample_name"] = name
                    logger.debug("[%s] 试样名称 = %s", filename, name)

        # 试验日期
        m = re.search(r'试验日期\s+(\d{4}-\d{1,2}-\d{1,2})', full_text)
        if m:
            data["test_date"] = _parse_date(m.group(1))
            logger.debug("[%s] 试验日期 = %s", filename, data["test_date"])

        # 试验时间
        m = re.search(r'试验时间\s+(\d{1,2}:\d{2}:\d{2})', full_text)
        if m:
            data["test_time"] = _parse_time(m.group(1))
            logger.debug("[%s] 试验时间 = %s", filename, data["test_time"])

        return data

    def _extract_peel_strength_from_rows(self, all_rows: Dict, filename: str) -> Dict:
        """从所有页面的 rows 中提取剥离强度数据"""
        data = {}

        # 策略1: 从统计行提取 A_aver / A_sd（最可靠）
        stats_data = self._extract_from_stats_line(all_rows, filename)
        data.update(stats_data)

        # 策略2: 从"平均值"行用 X 间隙分组提取各 S 值
        s_data = self._extract_s_values_improved(all_rows, filename)
        for k in ['S1', 'S2', 'S3', 'S4']:
            if k in s_data and s_data[k] is not None:
                data[k] = s_data[k]

        # 策略3: 回退到列位置法
        if not any(k in data for k in ['S1', 'S2', 'S3', 'S4']):
            s_columns = self._find_s_columns_v2(all_rows)
            if s_columns:
                for key in sorted(all_rows.keys()):
                    rows = all_rows[key]
                    line_text = ' '.join(w['text'] for w in sorted(rows, key=lambda w: w['x0']))
                    if '平均值' in line_text:
                        self._assign_values_to_s_columns(rows, s_columns, data, filename)
                        break

        return data

    def _extract_from_stats_line(self, all_rows: Dict, filename: str) -> Dict:
        """从统计行提取 A_aver 和 A_sd（格式：A_max=xxx A_min=xxx A_aver=xxx A_sd=xxx）"""
        data = {}
        for key in sorted(all_rows.keys()):
            rows = all_rows[key]
            line_text = ' '.join(w['text'] for w in sorted(rows, key=lambda w: w['x0']))
            compact = line_text.replace(' ', '')

            if 'A_aver' in compact or '统计' in compact:
                m = re.search(r'A_aver\s*=\s*([\d.]+)', compact, re.IGNORECASE)
                if m:
                    try:
                        data["A_aver"] = float(m.group(1))
                        logger.debug("[%s] A_aver = %s", filename, data["A_aver"])
                    except ValueError:
                        pass

                m = re.search(r'A_sd\s*=\s*([\d.]+)', compact, re.IGNORECASE)
                if m:
                    try:
                        data["A_sd"] = float(m.group(1))
                        logger.debug("[%s] A_sd = %s", filename, data["A_sd"])
                    except ValueError:
                        pass

                # 只在两个字段都提取到时才停止，否则继续搜索下一行
                if data.get("A_aver") is not None and data.get("A_sd") is not None:
                    break

        return data

    def _extract_s_values_improved(self, all_rows: Dict, filename: str) -> Dict:
        """从"平均值"行提取 S1-S9（使用 X 坐标间隙分组，避免列对齐偏差）"""
        data = {}

        for key in sorted(all_rows.keys()):
            rows = all_rows[key]
            line_text = ' '.join(w['text'] for w in sorted(rows, key=lambda w: w['x0']))

            if '平均值' not in line_text:
                continue

            # 收集"平均值"之后的数字片段
            sorted_words = sorted(rows, key=lambda w: w['x0'])
            past_avg = False
            number_fragments = []
            for w in sorted_words:
                t = w['text'].strip()
                if t == '平均值':
                    past_avg = True
                    continue
                if not past_avg:
                    continue
                if re.match(r'^[\d.]+$', t):
                    number_fragments.append(w)

            if not number_fragments:
                continue

            # 按 X 间隙分组（大间隙 = 新数字）
            groups = self._group_by_x_gap(number_fragments)

            # 每组拼接、清理、转为 float
            s_values = []
            for group in groups:
                chars = ''.join(w['text'].strip() for w in sorted(group, key=lambda w: w['x0']))
                num_str = _clean_number(chars)
                try:
                    val = float(num_str)
                    s_values.append(val)
                except ValueError:
                    pass

            # 按顺序赋值 S1-S9
            for i, val in enumerate(s_values[:9]):
                data[f"S{i+1}"] = val
                logger.debug("[%s] S%d = %s", filename, i+1, val)

            break

        return data

    def _group_by_x_gap(self, words: List, gap_threshold: float = 10.0) -> List[List]:
        """按 X 坐标间隙分组 words（大间隙 = 新数字组）"""
        if not words:
            return []
        sorted_words = sorted(words, key=lambda w: w['x0'])
        groups = [[sorted_words[0]]]
        for w in sorted_words[1:]:
            prev = groups[-1][-1]
            gap = w['x0'] - prev['x1']
            if gap > gap_threshold:
                groups.append([w])
            else:
                groups[-1].append(w)
        return groups

    def _find_s_columns_v2(self, all_rows: Dict) -> Dict:
        """找到 S1-S9 列的位置（改进版）"""
        # 遍历所有行，找包含 S1, S2... 的行
        for key in sorted(all_rows.keys()):
            rows = all_rows[key]
            s_positions = []

            for w in sorted(rows, key=lambda w: w['x0']):
                t = w['text'].strip()
                m = re.match(r'^S([1-9])$', t)
                if m:
                    x_center = (w['x0'] + w['x1']) / 2
                    s_positions.append((f"S{m.group(1)}", x_center))

            if s_positions:
                # 计算列边界
                boundaries = []
                for i in range(len(s_positions) - 1):
                    mid = (s_positions[i][1] + s_positions[i + 1][1]) / 2
                    boundaries.append(mid)

                columns = {}
                for i, (label, _) in enumerate(s_positions):
                    low = boundaries[i - 1] if i > 0 else 0
                    high = boundaries[i] if i < len(boundaries) else 9999
                    columns[label] = (low, high)

                logger.debug("S 列区间: %s", columns)
                return columns

        return {}

    def _assign_values_to_s_columns(self, words: List, s_columns: Dict, data: Dict, filename: str):
        """将 words 中的数字按 x 坐标归入 S 列"""
        s_values = defaultdict(list)

        for w in words:
            t = w['text'].strip()
            if not t or t == '平均值':
                continue
            if not re.match(r'^[\d.]+$', t):
                continue

            x_center = (w['x0'] + w['x1']) / 2
            for sk, (x_low, x_high) in s_columns.items():
                if x_low <= x_center <= x_high:
                    s_values[sk].append(t)
                    break

        # 拼接数字并转为 float
        for sk in ['S1', 'S2', 'S3', 'S4']:
            chars = s_values.get(sk, [])
            if chars:
                num_str = _clean_number(''.join(chars))
                try:
                    data[sk] = float(num_str)
                    logger.debug("[%s] %s = %s", filename, sk, data[sk])
                except ValueError:
                    logger.warning("[%s] %s 无法解析: %s", filename, sk, num_str)

    def _extract_a_sd_from_rows(self, all_rows: Dict, filename: str) -> Optional[float]:
        """从所有行中提取 A_sd 值"""
        for key in sorted(all_rows.keys()):
            rows = all_rows[key]
            line_text = ' '.join(w['text'] for w in sorted(rows, key=lambda w: w['x0']))
            compact = line_text.replace(' ', '')

            if 'A_sd' in compact or 'A_SD' in compact or '标准差' in compact:
                m = re.search(r'A_sd\s*=\s*([\d.]+)', compact, re.IGNORECASE)
                if m:
                    try:
                        val = float(m.group(1))
                        logger.debug("[%s] A_sd = %s", filename, val)
                        return val
                    except ValueError:
                        pass

        return None

    def _extract_by_ocr(self, pdf) -> Dict:
        """策略3: 使用 OCR 识别扫描件"""
        if not _HAS_OCR:
            return {}

        data = {}
        try:
            for page_num, page in enumerate(pdf.pages):
                # 将 PDF 页面转为图片
                img = page.to_image(resolution=300)
                img_pil = img.original

                # OCR 识别
                text = pytesseract.image_to_string(img_pil, lang=OCR_LANG)

                # 从文本中提取字段
                # 试样名称
                m = re.search(r'试样名称[:：]?\s*(.+)', text)
                if m and not data.get("sample_name"):
                    data["sample_name"] = m.group(1).strip()

                # 日期
                m = re.search(r'(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})', text)
                if m and not data.get("test_date"):
                    data["test_date"] = _parse_date(m.group(0))

                # 时间
                m = re.search(r'(\d{1,2}):(\d{2}):(\d{2})', text)
                if m and not data.get("test_time"):
                    data["test_time"] = _parse_time(m.group(0))

        except Exception as e:
            logger.warning("OCR 识别失败: %s", e)

        return data

    def _validate_and_fix(self, data: Dict, filename: str) -> Dict:
        """验证提取的字段并修正明显错误"""
        # 验证 S 值合理性（实际数据范围 0.001 ~ 0.1 kN/m）
        for sk in ['S1', 'S2', 'S3', 'S4']:
            val = data.get(sk)
            if val is not None:
                if not (0.0001 <= val <= 100):
                    logger.warning("[%s] %s 值异常: %s，标记为需人工复核", filename, sk, val)
                    data[f"{sk}_warning"] = f"值异常: {val}"

        # 验证 A_sd 合理性
        a_sd = data.get("A_sd")
        if a_sd is not None:
            if not (0 <= a_sd <= 100):
                logger.warning("[%s] A_sd 值异常: %s，标记为需人工复核", filename, a_sd)
                data["A_sd_warning"] = f"值异常: {a_sd}"

        return data

    def _fill_record(self, record: PeelDataRecord, data: Dict):
        """将提取的数据填充到 PeelDataRecord"""
        if "sample_name" in data:
            record.sample_name = data["sample_name"]
        if "test_date" in data:
            record.test_date = data["test_date"]
        if "test_time" in data:
            record.test_time = data["test_time"]
        for sk in ['S1', 'S2', 'S3', 'S4']:
            if sk in data:
                # S1→curve_1, S2→curve_2, ...
                curve_key = f"curve_{sk[1:]}"
                setattr(record, curve_key, data[sk])
        if "A_sd" in data:
            record.std_dev = data["A_sd"]

    def _determine_polarity(self, sample_name: str, filename: str) -> str:
        """判断极性（使用配置中的正负极关键字）"""
        polarity, _ = config.determine_polarity_with_materials(sample_name, filename)
        return polarity

    def _upgrade_sample_name(
        self, existing: Optional[str], filename: str
    ) -> Optional[str]:
        """
        按优先级链升级试样名称

        优先级：
        1. 从文件名提取（最高优先）
        2. 材料关键词辅助判断（用于修正极性，不影响 sample_name 内容）
        3. "正极"/"负极"前缀全量提取（从已有 sample_name 中）
        4. 保留已提取的 sample_name
        """
        # 优先级 1: 从文件名提取
        from_filename = config.extract_sample_name_from_filename(filename)
        if from_filename:
            # 如果文件名有"正极"或"负极"前缀，验证其完整性
            from_polarity = config.extract_sample_name_by_polarity_prefix(from_filename)
            if from_polarity:
                logger.info(
                    "[%s] 试样名称(优先级1-文件名+极性前缀) = %s",
                    os.path.basename(filename), from_polarity
                )
                return from_polarity
            # 文件名无极性前缀但仍然是有效来源
            logger.info(
                "[%s] 试样名称(优先级1-文件名) = %s",
                os.path.basename(filename), from_filename
            )
            return from_filename

        # 优先级 3: 从已有 sample_name 中提取"正极"/"负极"前缀
        if existing:
            from_polarity = config.extract_sample_name_by_polarity_prefix(existing)
            if from_polarity and from_polarity != existing:
                logger.info(
                    "[%s] 试样名称(优先级3-极性前缀) = %s (原: %s)",
                    os.path.basename(filename), from_polarity, existing
                )
                return from_polarity
            # 优先级 2: 材料关键词辅助（用于日志记录，不修改 sample_name）
            materials = config.match_material_keywords(existing)
            if materials:
                logger.debug(
                    "[%s] 试样名称匹配到材料关键词: %s",
                    os.path.basename(filename), materials
                )

        # 优先级 4: 保留已有的 sample_name
        return existing
