# -*- coding: utf-8 -*-
"""分容数据统计分析器

计算与 JMP "分布"模块一致的统计指标：
- 均值、标准差、最大最小、四分位数、2.5/97.5 百分位
- 95% 置信区间（基于 t 分布，自由度 n-1）
- 均值标准误差
"""

from __future__ import annotations

import math
from typing import List

from core.logger import get_logger
from plugins.capacity_analysis.models import (
    CapacityRecord,
    CapacityStats,
    AnalysisResult,
)

logger = get_logger("capacity_analysis.analyzer")


def _percentile(sorted_data: List[float], p: float) -> float:
    """线性插值百分位数（与 numpy.percentile(method=linear) 一致）"""
    if not sorted_data:
        return 0.0
    n = len(sorted_data)
    if n == 1:
        return float(sorted_data[0])
    rank = (p / 100.0) * (n - 1)
    lo = int(math.floor(rank))
    hi = int(math.ceil(rank))
    if lo == hi:
        return float(sorted_data[lo])
    frac = rank - lo
    return float(sorted_data[lo] + (sorted_data[hi] - sorted_data[lo]) * frac)


def _t_critical_95(df: int) -> float:
    """95% 置信区间 t 临界值（双侧）
    简化为查表 + 插值，避免引入 scipy 依赖
    """
    # 标准 t 分布临界值表（df → t_0.025）
    table = {
        1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571,
        6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
        11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131,
        16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086,
        21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060,
        26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042,
        35: 2.030, 40: 2.021, 50: 2.009, 60: 2.000, 80: 1.990,
        100: 1.984, 200: 1.972, 500: 1.965, 1000: 1.962,
    }
    if df <= 0:
        return 12.706
    if df in table:
        return table[df]
    # 大自由度近似 1.96
    if df > 1000:
        return 1.960
    # 在最近的两个 key 之间线性插值
    keys = sorted(table.keys())
    if df < keys[0]:
        return table[keys[0]]
    if df > keys[-1]:
        return 1.960
    for i in range(len(keys) - 1):
        if keys[i] <= df <= keys[i + 1]:
            k0, k1 = keys[i], keys[i + 1]
            t0, t1 = table[k0], table[k1]
            frac = (df - k0) / (k1 - k0)
            return t0 + (t1 - t0) * frac
    return 1.960


def analyze(records: List[CapacityRecord]) -> CapacityStats:
    """计算 JMP 风格统计指标"""
    stats = CapacityStats()
    if not records:
        return stats
    values = sorted([r.capacity_mah for r in records if r.capacity_mah > 0])
    n = len(values)
    if n == 0:
        return stats
    stats.count = n
    stats.min_v = float(values[0])
    stats.max_v = float(values[-1])
    stats.mean = sum(values) / n
    # 总体标准差
    if n > 1:
        variance = sum((x - stats.mean) ** 2 for x in values) / (n - 1)
        stats.std_dev = math.sqrt(variance)
    else:
        stats.std_dev = 0.0
    stats.std_err = stats.std_dev / math.sqrt(n) if n > 0 else 0.0
    stats.median = _percentile(values, 50)
    stats.q1 = _percentile(values, 25)
    stats.q3 = _percentile(values, 75)
    stats.p2_5 = _percentile(values, 2.5)
    stats.p97_5 = _percentile(values, 97.5)
    # 95% CI（基于 t 分布）
    t_crit = _t_critical_95(n - 1)
    stats.ci95_lower = stats.mean - t_crit * stats.std_err
    stats.ci95_upper = stats.mean + t_crit * stats.std_err
    return stats


def finalize_result(result: AnalysisResult) -> AnalysisResult:
    """在 result 已有 records 基础上计算统计指标"""
    result.stats = analyze(result.records)
    return result
