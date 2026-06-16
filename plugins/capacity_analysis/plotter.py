# -*- coding: utf-8 -*-
"""JMP 风格分布图渲染（v1.8.0 hotfix）

严格对齐 JMP "分布"模块的视觉效果：
- 顶层标题折叠层级（🔽 分布 / 🔽 容量）
- 横向直方图：X = 容量值，Y = 频数（绿色填充）
- 箱体图嵌直方图右侧 1/8 宽度：白色中位数线、蓝色箱体、上下须、黑色离群点
- 分位数表：11 行 + 3 行标签值，标签左对齐 + 数值右对齐
- 汇总统计表：6 行，标签左对齐 + 数值右对齐
"""

from __future__ import annotations

import math
import os
from typing import List

from core.logger import get_logger
from plugins.capacity_analysis.models import (
    CapacityStats,
    AnalysisResult,
)

logger = get_logger("capacity_analysis.plotter")


# JMP 风格颜色
_JMP_GREEN = "#9CCB9C"
_JMP_GREEN_EDGE = "#6FAA6F"
_JMP_BOX_BLUE = "#A0B4D5"
_JMP_BOX_EDGE = "#4A6090"
_JMP_BG_GRAY = "#F5F5F5"
_JMP_HEADER_BG = "#E8E8E8"
_JMP_TEXT = "#000000"
_JMP_RED = "#D04040"


def _setup_matplotlib():
    """统一配置 matplotlib（中文字体 / 字号 / 负号）"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    # 中文字体：尝试多个候选
    for font_name in ["Microsoft YaHei", "SimHei", "SimSun", "Noto Sans CJK SC"]:
        try:
            matplotlib.rcParams["font.sans-serif"] = [font_name, "DejaVu Sans"]
            matplotlib.rcParams["font.family"] = "sans-serif"
            matplotlib.rcParams["axes.unicode_minus"] = False
            # 验证字体是否真的可用
            from matplotlib.font_manager import findfont, FontProperties
            path = findfont(FontProperties(family=font_name), fallback_to_default=False)
            if path:
                break
        except Exception:
            continue
    return plt


def _percentile_safe(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    if n == 1:
        return float(s[0])
    rank = (p / 100.0) * (n - 1)
    lo = int(math.floor(rank))
    hi = int(math.ceil(rank))
    if lo == hi:
        return float(s[lo])
    frac = rank - lo
    return float(s[lo] + (s[hi] - s[lo]) * frac)


def _histogram(values: List[float], n_bins: int):
    """等宽分箱，返回 (counts, bin_edges)"""
    v_min, v_max = min(values), max(values)
    if v_min == v_max:
        return [len(values)], [v_min, v_max + 1]
    bin_width = (v_max - v_min) / n_bins
    bin_edges = [v_min + i * bin_width for i in range(n_bins + 1)]
    counts = [0] * n_bins
    for v in values:
        idx = int((v - v_min) / bin_width)
        if idx >= n_bins:
            idx = n_bins - 1
        if idx < 0:
            idx = 0
        counts[idx] += 1
    return counts, bin_edges


def render_distribution_plot(
    result: AnalysisResult,
    output_path: str,
    title: str = "",
) -> str:
    """渲染 JMP 风格分布图并保存为 PNG

    Args:
        result: 包含 records 和 stats 的分析结果
        output_path: 输出 PNG 路径
        title: 图表顶层标题（默认 = 批次名）
    """
    plt = _setup_matplotlib()

    values = [r.capacity_mah for r in result.records if r.capacity_mah > 0]
    if not values:
        logger.warning("没有有效数据，跳过绘图")
        return ""

    stats = result.stats
    if not title:
        title = f"分布 — {result.batch_id}  (n={stats.count})"

    # 画布尺寸与 JMP 输出比例相近
    fig = plt.figure(figsize=(4.2, 9.0), dpi=150, facecolor="white")

    # === 顶层：标题折叠区（🔽 分布 / 🔽 容量） ===
    # 用 fig.text 在画布顶部加两层标题
    fig.text(0.04, 0.975, "🔽", fontsize=11, color=_JMP_RED, ha="left", va="center")
    fig.text(0.10, 0.975, "分布", fontsize=11, fontweight="bold", ha="left", va="center")
    fig.text(0.30, 0.945, "🔽", fontsize=10, color=_JMP_RED, ha="left", va="center")
    fig.text(0.36, 0.945, "容量", fontsize=10, ha="left", va="center")

    # === 主图区：直方图 + 箱体图（重叠布局）===
    # 用 add_axes 精确控制位置
    # [left, bottom, width, height]
    ax_main = fig.add_axes([0.18, 0.43, 0.78, 0.49])
    # 箱体图：嵌在主图右侧 ~8% 宽度
    ax_box = fig.add_axes([0.78, 0.43, 0.06, 0.49], sharey=ax_main)

    # --- 直方图（横向：X=容量，Y=频数） ---
    n = len(values)
    # Sturges 公式：n_bins = ceil(log2(n) + 1)，最少 12
    n_bins = max(12, min(30, int(math.ceil(math.log2(n) + 1))))
    counts, bin_edges = _histogram(values, n_bins)
    bin_centers = [(bin_edges[i] + bin_edges[i + 1]) / 2 for i in range(len(bin_edges) - 1)]
    bin_width = bin_edges[1] - bin_edges[0]

    for i, c in enumerate(counts):
        if c > 0:
            ax_main.barh(
                bin_centers[i], c,
                height=bin_width * 0.92,
                color=_JMP_GREEN,
                edgecolor=_JMP_GREEN_EDGE,
                linewidth=0.5,
            )
    ax_main.set_xlabel("频数", fontsize=9)
    ax_main.tick_params(axis="both", labelsize=8)
    ax_main.grid(axis="x", linestyle=":", color="#cccccc", linewidth=0.5, alpha=0.6)
    ax_main.set_axisbelow(True)
    # Y 轴范围
    v_min, v_max = min(values), max(values)
    pad = (v_max - v_min) * 0.02
    ax_main.set_ylim(v_min - pad, v_max + pad)
    # Y 轴刻度放在左侧
    ax_main.tick_params(axis="y", labelleft=True)

    # --- 箱体图（叠在直方图右侧） ---
    _draw_box(ax_box, values, stats)
    ax_box.set_xlim(0, 1)
    ax_box.set_xticks([])
    # 共享 Y 轴（与 ax_main 一致）
    ax_box.tick_params(axis="y", labelleft=False)
    ax_box.set_ylim(ax_main.get_ylim())

    # === 分位数表区 ===
    _draw_quantile_table(fig, stats, values)

    # === 汇总统计表区 ===
    _draw_summary_table(fig, stats)

    # === 保存 ===
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    logger.info(f"分布图已生成: {output_path}")
    return output_path


def _draw_box(ax, values: List[float], stats: CapacityStats):
    """在 ax 上画垂直箱体图（嵌在直方图右侧）"""
    from matplotlib.patches import Rectangle
    q1, med, q3 = stats.q1, stats.median, stats.q3
    iqr = q3 - q1
    lower_fence = q1 - 1.5 * iqr
    upper_fence = q3 + 1.5 * iqr
    non_outliers = [v for v in values if lower_fence <= v <= upper_fence]
    outliers = [v for v in values if v < lower_fence or v > upper_fence]
    if non_outliers:
        upper_whisker = max(non_outliers)
        lower_whisker = min(non_outliers)
    else:
        upper_whisker, lower_whisker = q3, q1

    # 蓝色箱体（Q1 - Q3）
    rect = Rectangle(
        (0.20, q1), 0.60, q3 - q1,
        facecolor=_JMP_BOX_BLUE,
        edgecolor=_JMP_BOX_EDGE,
        linewidth=1.0,
        zorder=3,
    )
    ax.add_patch(rect)
    # 中位数线（白色短横线）
    ax.plot([0.20, 0.80], [med, med], color="white", linewidth=1.8, zorder=4)
    # 上须（vertical line from box top to upper_whisker）
    ax.plot([0.5, 0.5], [q3, upper_whisker], color=_JMP_BOX_EDGE, linewidth=0.9, zorder=2)
    # 上须帽
    ax.plot([0.40, 0.60], [upper_whisker, upper_whisker], color=_JMP_BOX_EDGE, linewidth=0.9, zorder=2)
    # 下须
    ax.plot([0.5, 0.5], [q1, lower_whisker], color=_JMP_BOX_EDGE, linewidth=0.9, zorder=2)
    # 下须帽
    ax.plot([0.40, 0.60], [lower_whisker, lower_whisker], color=_JMP_BOX_EDGE, linewidth=0.9, zorder=2)
    # 离群点（黑色圆点）
    for ov in outliers:
        ax.plot(0.5, ov, marker="o", markersize=3.5,
                markerfacecolor="black", markeredgecolor="black", zorder=5)
    ax.set_xlim(0, 1)


def _draw_quantile_table(fig, stats: CapacityStats, values: List[float]):
    """分位数表（两列：左=百分位+值，右=标签+值）"""
    # 位置：[left, bottom, width, height]
    ax = fig.add_axes([0.05, 0.21, 0.90, 0.20])
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_facecolor("white")

    # 标题区
    ax.text(0.005, 0.92, "🔽", fontsize=10, color=_JMP_RED,
            ha="left", va="center", transform=ax.transAxes)
    ax.text(0.05, 0.92, "分位数", fontsize=10, fontweight="bold",
            ha="left", va="center", transform=ax.transAxes)

    rows = [
        ("100.0%", stats.max_v,  "最大值",   stats.max_v),
        ("99.5%",  _percentile_safe(values, 99.5), None, None),
        ("97.5%",  stats.p97_5,  None,       None),
        ("90.0%",  _percentile_safe(values, 90.0), None, None),
        ("75.0%",  stats.q3,     "四分位数", stats.q3),
        ("50.0%",  stats.median, "中位数",   stats.median),
        ("25.0%",  stats.q1,     None,       None),
        ("10.0%",  _percentile_safe(values, 10.0), None, None),
        ("2.5%",   stats.p2_5,   None,       None),
        ("0.5%",   _percentile_safe(values, 0.5),  None, None),
        ("0.0%",   stats.min_v,  "最小值",   stats.min_v),
    ]
    n = len(rows)
    # 行高
    row_h = 0.86 / n
    start_y = 0.82
    for i, (p, v, label, label_v) in enumerate(rows):
        y = start_y - i * row_h
        # 左列：百分位
        ax.text(0.04, y, p, fontsize=8.5, ha="left", va="center",
                transform=ax.transAxes, family="monospace")
        # 左列数值
        ax.text(0.22, y, f"{v:.2f}", fontsize=8.5, ha="left", va="center",
                transform=ax.transAxes, family="monospace")
        # 右列：标签
        if label:
            ax.text(0.55, y, label, fontsize=8.5, ha="left", va="center",
                    transform=ax.transAxes, fontweight="bold")
            ax.text(0.80, y, f"{label_v:.2f}", fontsize=8.5, ha="left", va="center",
                    transform=ax.transAxes, family="monospace")


def _draw_summary_table(fig, stats: CapacityStats):
    """汇总统计表"""
    ax = fig.add_axes([0.05, 0.04, 0.90, 0.15])
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_facecolor("white")

    # 标题
    ax.text(0.005, 0.85, "🔽", fontsize=10, color=_JMP_RED,
            ha="left", va="center", transform=ax.transAxes)
    ax.text(0.05, 0.85, "汇总统计量", fontsize=10, fontweight="bold",
            ha="left", va="center", transform=ax.transAxes)

    rows = [
        ("均值",           f"{stats.mean:.4f}"),
        ("标准差",         f"{stats.std_dev:.6f}"),
        ("均值标准误差",   f"{stats.std_err:.6f}"),
        ("均值 95% 上限",  f"{stats.ci95_upper:.4f}"),
        ("均值 95% 下限",  f"{stats.ci95_lower:.4f}"),
        ("数目",           f"{stats.count}"),
    ]
    n = len(rows)
    row_h = 0.72 / n
    start_y = 0.70
    for i, (label, val) in enumerate(rows):
        y = start_y - i * row_h
        ax.text(0.04, y, label, fontsize=9, ha="left", va="center",
                transform=ax.transAxes)
        ax.text(0.50, y, val, fontsize=9, ha="left", va="center",
                transform=ax.transAxes, family="monospace")
