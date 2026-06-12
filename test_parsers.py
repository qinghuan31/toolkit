#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试重构后的 PDF 和 Excel 解析器

使用方法：
    .venv/Scripts/python.exe test_parsers.py <测试文件或目录>

此脚本会：
1. 测试 PDF/Excel 解析器是否能成功提取数据
2. 验证提取的字段是否合理
3. 生成详细的测试报告
"""

import os
import sys
import datetime
import logging

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.logger import setup_logging
from plugins.peel_data.pdf_parser import PDFParser
from plugins.peel_data.excel_parser import ExcelParser
from plugins.peel_data.models import PeelDataRecord


def test_pdf_parser(file_path: str) -> dict:
    """测试 PDF 解析器"""
    print(f"\n{'=' * 60}")
    print(f"测试 PDF: {os.path.basename(file_path)}")
    print(f"{'=' * 60}")

    parser = PDFParser()
    record = parser.parse(file_path)

    result = {
        "file": os.path.basename(file_path),
        "success": record is not None,
        "sample_name": None,
        "test_date": None,
        "test_time": None,
        "S1": None,
        "S2": None,
        "S3": None,
        "S4": None,
        "A_sd": None,
        "polarity": None,
    }

    if record:
        result["sample_name"] = record.sample_name
        result["test_date"] = str(record.test_date) if record.test_date else None
        result["test_time"] = str(record.test_time) if record.test_time else None
        result["S1"] = record.S1
        result["S2"] = record.S2
        result["S3"] = record.S3
        result["S4"] = record.S4
        result["A_sd"] = record.A_sd
        result["polarity"] = record.polarity

        print(f"✓ 试样名称: {record.sample_name}")
        print(f"✓ 试验日期: {record.test_date}")
        print(f"✓ 试验时间: {record.test_time}")
        print(f"✓ S1={record.S1}, S2={record.S2}, S3={record.S3}, S4={record.S4}")
        print(f"✓ A_sd={record.A_sd}")
        print(f"✓ 极性: {record.polarity}")
    else:
        print("✗ 解析失败")

    return result


def test_excel_parser(file_path: str) -> dict:
    """测试 Excel 解析器"""
    print(f"\n{'=' * 60}")
    print(f"测试 Excel: {os.path.basename(file_path)}")
    print(f"{'=' * 60}")

    parser = ExcelParser()
    record = parser.parse(file_path)

    result = {
        "file": os.path.basename(file_path),
        "success": record is not None,
        "sample_name": None,
        "test_date": None,
        "test_time": None,
        "S1": None,
        "S2": None,
        "S3": None,
        "S4": None,
        "A_sd": None,
        "polarity": None,
    }

    if record:
        result["sample_name"] = record.sample_name
        result["test_date"] = str(record.test_date) if record.test_date else None
        result["test_time"] = str(record.test_time) if record.test_time else None
        result["S1"] = record.S1
        result["S2"] = record.S2
        result["S3"] = record.S3
        result["S4"] = record.S4
        result["A_sd"] = record.A_sd
        result["polarity"] = record.polarity

        print(f"✓ 试样名称: {record.sample_name}")
        print(f"✓ 试验日期: {record.test_date}")
        print(f"✓ 试验时间: {record.test_time}")
        print(f"✓ S1={record.S1}, S2={record.S2}, S3={record.S3}, S4={record.S4}")
        print(f"✓ A_sd={record.A_sd}")
        print(f"✓ 极性: {record.polarity}")
    else:
        print("✗ 解析失败")

    return result


def main():
    if len(sys.argv) < 2:
        print("使用方法: python test_parsers.py <测试文件或目录>")
        print("\n示例:")
        print("  python test_parsers.py data/sample.pdf")
        print("  python test_parsers.py data/")
        sys.exit(1)

    path = sys.argv[1]

    # 设置日志
    setup_logging()

    results = []

    if os.path.isfile(path):
        # 测试单个文件
        ext = os.path.splitext(path)[1].lower()
        if ext == ".pdf":
            result = test_pdf_parser(path)
        elif ext in (".xlsx", ".xlsm", ".xlsb", ".xls"):
            result = test_excel_parser(path)
        elif ext == ".csv":
            result = test_excel_parser(path)
        else:
            print(f"不支持的文件类型: {ext}")
            sys.exit(1)
        results.append(result)

    elif os.path.isdir(path):
        # 测试目录中的所有文件
        for fname in os.listdir(path):
            fpath = os.path.join(path, fname)
            if not os.path.isfile(fpath):
                continue

            ext = os.path.splitext(fpath)[1].lower()
            try:
                if ext == ".pdf":
                    result = test_pdf_parser(fpath)
                elif ext in (".xlsx", ".xlsm", ".xlsb", ".xls"):
                    result = test_excel_parser(fpath)
                elif ext == ".csv":
                    result = test_excel_parser(fpath)
                else:
                    continue
                results.append(result)
            except Exception as e:
                print(f"✗ 测试失败: {e}")
                results.append({
                    "file": fname,
                    "success": False,
                    "error": str(e)
                })

    else:
        print(f"路径不存在: {path}")
        sys.exit(1)

    # 生成测试报告
    print(f"\n{'=' * 60}")
    print("测试报告")
    print(f"{'=' * 60}")

    total = len(results)
    success = sum(1 for r in results if r["success"])
    fail = total - success

    print(f"总计: {total} 个文件")
    print(f"成功: {success} 个")
    print(f"失败: {fail} 个")
    print(f"成功率: {success / total * 100:.1f}%" if total > 0 else "N/A")

    # 详细的字段提取统计
    if success > 0:
        print(f"\n字段提取统计:")
        fields = ["sample_name", "test_date", "test_time", "S1", "S2", "S3", "S4", "A_sd"]
        for field in fields:
            count = sum(1 for r in results if r.get(field) is not None)
            print(f"  {field}: {count}/{success} ({count / success * 100:.1f}%)")

    print(f"\n{'=' * 60}")


if __name__ == "__main__":
    main()
