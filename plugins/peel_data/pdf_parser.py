# -*- coding: utf-8 -*-
"""
PDF 文件解析器
提取剥离测试 PDF 报告中的结构化数据
增强版：改进文本提取、支持更多格式变体、增加调试日志
修复：正则属性从模块级迁移为类属性；增加异常兜底与超时保护
"""

import re
import os
import signal
import threading
from typing import Optional, List

from core.logger import get_logger
from plugins.peel_data.models import PeelDataRecord

logger = get_logger("peel_data.pdf_parser")


def _clean_text(text: str) -> str:
    """清理提取出的文本：去掉末尾多余标点和空白"""
    text = text.strip()
    # 去掉末尾的标点（中文/英文）
    text = re.sub(r"[：:：\s]+$", "", text)
    return text.strip()


class _TimeoutError(Exception):
    """PDF 解析超时异常"""
    pass


def _timeout_handler(signum, frame):
    """信号处理函数（仅 POSIX 可用）"""
    raise _TimeoutError("PDF 解析超时")


class PDFParser:
    """PDF 剥离数据解析器（增强版）

    修复记录：
    - v1.1.1: 将模块级正则 _pattern_* 迁移为类属性，修复 self._pattern_* 的 AttributeError
    - v1.1.1: 增加 _extract_from_text 逐段异常兜底，单个字段提取失败不中断整体
    - v1.1.1: 增加 parse() 文件级超时保护（默认 30 秒）
    """

    # ------------------------------------------------------------------
    # 编译正则 —— 作为类属性，所有实例共享，避免重复编译
    # ------------------------------------------------------------------
    _FLAG = re.IGNORECASE | re.UNICODE

    PATTERN_CURVE = re.compile(
        r"S([1-9])\s*[=：:\s]+([0-9]+\.?[0-9]*)",
        _FLAG
    )

    PATTERN_STD = re.compile(
        r"A_Sd\s*[=：:\s]+([0-9]+\.?[0-9]*)",
        _FLAG
    )

    PATTERN_TIME = re.compile(
        r"(?:试验时间|测试时间|时间)\s*[=：:\s]+([0-9:]+)",
        _FLAG
    )

    PATTERN_DATE = re.compile(
        r"(?:试验日期|测试日期|日期)\s*[=：:\s]+([0-9/\-年月日]+)",
        _FLAG
    )

    # 试样名称：支持中文/英文/数字/横线/下划线
    PATTERN_SAMPLE = re.compile(
        r"(?:试样名称|样品名称|试样牌号|牌号)\s*[=：:\s]+([^\n\r]{1,80})",
        _FLAG
    )

    # 剥离强度单位：匹配"单位：kN/m"或"Unit: N/mm"等格式
    PATTERN_UNIT = re.compile(
        r"(?:单位|unit|Unit)\s*[=：:\s]*([^\s\r\n（）()]{1,20})",
        _FLAG
    )

    # 备用：从"剥离强度 (kN/m)"这类格式中提取单位
    PATTERN_UNIT_PAREN = re.compile(
        r"(?:剥离强度|peel\s+strength)\s*[（(]([^）)]+)[）)]",
        _FLAG
    )

    # 当提取到的试样名称仅为这些标签文字时，视为无效
    GENERIC_SAMPLE_NAMES = frozenset([
        "试样编号", "试样名称", "样品名称", "样品名", "试样", "编号", "名称", "",
        "试样牌号", "牌号",
    ])

    # 默认超时（秒）
    DEFAULT_TIMEOUT = 30

    def parse(self, file_path: str, timeout: Optional[int] = None) -> Optional[PeelDataRecord]:
        """解析单个 PDF 文件

        Args:
            file_path: PDF 文件路径
            timeout: 单文件解析超时秒数，None 使用默认值 30s
        """
        try:
            import pdfplumber
        except ImportError:
            logger.error("pdfplumber 未安装，请执行: pip install pdfplumber")
            return None

        filename = os.path.basename(file_path)
        timeout = timeout or self.DEFAULT_TIMEOUT
        logger.debug(f"开始解析 PDF: {filename} (超时={timeout}s)")

        # 使用线程+Event 实现跨平台超时（Windows 不支持 signal.alarm）
        result_container = [None]  # [record | None]
        error_container = [None]   # [Exception | None]
        done_event = threading.Event()

        def _parse_inner():
            """在线程内执行实际解析"""
            try:
                full_text = ""
                with pdfplumber.open(file_path) as pdf:
                    for page_num, page in enumerate(pdf.pages):
                        try:
                            # 提取文本
                            text = page.extract_text()
                            if text:
                                full_text += text + "\n"
                                logger.debug(f"  第 {page_num+1} 页提取到 {len(text)} 字符文本")

                            # 同时提取表格内容（表格中的文字可能不在 extract_text 中）
                            try:
                                tables = page.extract_tables()
                                for table in tables:
                                    for row in table:
                                        row_text = " ".join(str(c) for c in row if c)
                                        if row_text.strip():
                                            full_text += row_text + "\n"
                            except Exception as tbl_err:
                                logger.debug(f"  第 {page_num+1} 页表格提取异常: {tbl_err}")

                            # 尝试 extract_words 获取更多内容
                            try:
                                words = page.extract_words()
                                if words:
                                    logger.debug(f"  第 {page_num+1} 页提取到 {len(words)} 个单词")
                            except Exception as words_err:
                                logger.debug(f"  第 {page_num+1} 页单词提取异常: {words_err}")

                        except Exception as page_err:
                            # 单页提取失败不中断后续页面
                            logger.warning(f"  第 {page_num+1} 页提取异常: {page_err}")
                            continue

                if not full_text.strip():
                    logger.warning(f"PDF 无文本内容: {filename}")
                    result_container[0] = None
                    return

                # 记录提取到的原始文本（前 500 字符）供调试
                logger.debug(f"PDF 提取文本预览: {full_text[:500]!r}")

                record = self._extract_from_text(full_text, filename)
                result_container[0] = record

            except Exception as e:
                error_container[0] = e

        # 启动解析线程并等待
        worker = threading.Thread(target=_parse_inner, daemon=True)
        worker.start()
        finished = done_event.wait(timeout=timeout) if False else worker.join(timeout=timeout)

        if worker.is_alive():
            # 线程仍在运行 -> 超时
            logger.error(f"PDF 解析超时 [{filename}]: 超过 {timeout}s，已放弃")
            return None

        # 线程结束，检查是否有异常
        if error_container[0] is not None:
            logger.error(f"PDF 解析异常 [{filename}]: {error_container[0]}", exc_info=False)
            return None

        record = result_container[0]
        if record:
            logger.info(
                f"PDF 解析成功: {filename} -> "
                f"试样={record.sample_name}, 牌号={record.sample_brand}, 极性={record.polarity}"
            )
        else:
            logger.warning(f"PDF 未能提取有效数据: {filename}")

        return record

    def _extract_from_text(
        self, text: str, filename: str
    ) -> Optional[PeelDataRecord]:
        """从文本内容中提取字段（增强版 + 异常兜底）

        每个字段提取独立 try/except，单个字段失败不影响其他字段。
        """
        record = PeelDataRecord()
        record.source_file = filename

        # ---- 提取试样名称 ----
        try:
            sample_match = self.PATTERN_SAMPLE.search(text)
            if sample_match:
                name = _clean_text(sample_match.group(1))
                record.sample_name = name
                logger.debug(f"  试样名称 = {name}")
            else:
                # 尝试从文件名提取
                name_base = os.path.splitext(filename)[0]
                record.sample_name = name_base
                logger.debug(f"从文件名提取试样名称: {name_base}")
        except Exception as e:
            logger.debug(f"试样名称提取异常: {e}")
            record.sample_name = os.path.splitext(filename)[0]

        # 如果试样名称是通用标签，回退到文件名
        if (record.sample_name or "").strip() in self.GENERIC_SAMPLE_NAMES:
            record.sample_name = os.path.splitext(filename)[0]

        # ---- 提取试样牌号（独立字段）----
        try:
            brand_match = re.search(
                r"(?:试样牌号|牌号)\s*[=：:\s]+([^\n\r]{1,50})",
                text,
                self._FLAG
            )
            if brand_match:
                record.sample_brand = _clean_text(brand_match.group(1))
                logger.debug(f"  试样牌号 = {record.sample_brand}")
        except Exception as e:
            logger.debug(f"试样牌号提取异常: {e}")

        # ---- 提取 S1~S9 平均剥离强度 ----
        try:
            for match in self.PATTERN_CURVE.finditer(text):
                idx = int(match.group(1))
                value = float(match.group(2))
                if 1 <= idx <= 9:
                    setattr(record, f"curve_{idx}", value)
                    logger.debug(f"  S{idx} = {value}")
        except Exception as e:
            logger.debug(f"曲线值(S格式)提取异常: {e}")

        # ---- 如果没有匹配到 S1~S9，尝试"曲线N"格式 ----
        if not any(getattr(record, f"curve_{i}") is not None for i in range(1, 10)):
            try:
                for i in range(1, 10):
                    m = re.search(
                        rf"曲线{i}\s*[=：:\s]+([0-9]+\.?[0-9]*)",
                        text,
                        self._FLAG
                    )
                    if m:
                        setattr(record, f"curve_{i}", float(m.group(1)))
                        logger.debug(f"  曲线{i} = {m.group(1)}")
            except Exception as e:
                logger.debug(f"曲线值(曲线N格式)提取异常: {e}")

        # ---- 提取标准差 ----
        try:
            std_match = self.PATTERN_STD.search(text)
            if std_match:
                record.std_dev = float(std_match.group(1))
                logger.debug(f"  A_Sd = {record.std_dev}")
        except Exception as e:
            logger.debug(f"标准差提取异常: {e}")

        # ---- 提取试验时间 ----
        try:
            time_match = self.PATTERN_TIME.search(text)
            if time_match:
                record.test_time = time_match.group(1).strip()
                logger.debug(f"  试验时间 = {record.test_time}")
        except Exception as e:
            logger.debug(f"试验时间提取异常: {e}")

        # ---- 提取试验日期 ----
        try:
            date_match = self.PATTERN_DATE.search(text)
            if date_match:
                record.test_date = _clean_text(date_match.group(1))
                logger.debug(f"  试验日期 = {record.test_date}")
        except Exception as e:
            logger.debug(f"试验日期提取异常: {e}")

        # ---- 清理日期格式 ----
        try:
            if record.test_date and " " in record.test_date:
                record.test_date = record.test_date.split(" ")[0].strip()
        except Exception as e:
            logger.debug(f"日期格式清理异常: {e}")

        # ---- 判定极性 ----
        try:
            record.polarity = self._determine_polarity(record.sample_name, filename)
        except Exception as e:
            logger.debug(f"极性判定异常: {e}")
            record.polarity = "未知"

        # ---- 提取剥离强度单位 ----
        try:
            unit = ""
            # 优先匹配"单位：xxx"格式
            unit_match = self.PATTERN_UNIT.search(text)
            if unit_match:
                unit = _clean_text(unit_match.group(1))
            # 备用：从"剥离强度 (xxx)"格式提取
            if not unit:
                unit_paren_match = self.PATTERN_UNIT_PAREN.search(text)
                if unit_paren_match:
                    unit = _clean_text(unit_paren_match.group(1))
            if unit:
                record.curve_unit = unit
                logger.debug(f"  剥离强度单位 = {unit}")
        except Exception as e:
            logger.debug(f"单位提取异常: {e}")

        # 至少需要有试样名称和一个剥离强度值才算有效
        has_any_curve = any(
            getattr(record, f"curve_{i}") is not None for i in range(1, 10)
        )
        if not record.sample_name or not has_any_curve:
            return None

        return record

    @staticmethod
    def _determine_polarity(sample_name: str, filename: str) -> str:
        """根据试样名称和文件名中的关键字判定正负极"""
        from config import config

        # 先从试样名称判定
        name_lower = sample_name.lower()
        for kw in config.positive_keywords:
            if kw.lower() in name_lower:
                return "正极"
        for kw in config.negative_keywords:
            if kw.lower() in name_lower:
                return "负极"

        # 再从文件名判定
        file_lower = filename.lower()
        for kw in config.positive_keywords:
            if kw.lower() in file_lower:
                return "正极"
        for kw in config.negative_keywords:
            if kw.lower() in file_lower:
                return "负极"

        return "未知"

    def parse_batch(
        self, file_paths: List[str]
    ) -> List[PeelDataRecord]:
        """批量解析 PDF 文件"""
        results = []
        for fp in file_paths:
            record = self.parse(fp)
            if record:
                results.append(record)
        return results
