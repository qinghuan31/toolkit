# -*- coding: utf-8 -*-
"""JMP 风格分布图渲染（matplotlib）

复刻 JMP "分布"模块的视觉效果：
- 左侧：横向直方图（绿色填充）
- 右侧：垂直箱体图（含中位数线、四分位箱、上下须、离群点）
- 下方：分位数表 + 汇总统计表

输出：单图 PNG
"""

from __future__ import annotations

import os
from typing import List, Optional

from core.logger import get_logger
from plugins.capacity_analysis.models import (
    CapacityRecord,
    CapacityStats,
    AnalysisResult,
)

logger = get_logger("capacity_analysis.plotter")


# JMP 风格颜色（JMP 默认绿色调）
_JMP_GREEN = "#7BBE7B"
_JMP_GREEN_EDGE = "#5A9A5A"
_JMP_BOX_BLUE = "#7892C2"
_JMP_BOX_EDGE = "#3A4F7A"
_JMP_OUTLIER = "#222222"


def render_distribution_plot(
    result: AnalysisResult,
    output_path: str,
    title: str = "",
) -> str:
    """渲染分布图并保存为 PNG

    Args:
        result: 包含 records 和 stats 的分析结果
        output_path: 输出 PNG 路径
        title: 图表标题

    Returns:
        输出文件路径
    """
    try:
        import matplotlib
        matplotlib.use("Agg")  # 非交互后端
        import matplotlib.pyplot as plt
        from matplotlib.gridspec import GridSpec
        # 配置中文字体（避免方块字）
        for font_name in ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "WenQuanYi Zen Hei"]:
            try:
                matplotlib.rcParams["font.sans-serif"] = [font_name]
                matplotlib.rcParams["axes.unicode_minus"] = False
                break
            except Exception:
                continue
    except ImportError as e:
        logger.error(f"matplotlib 未安装，无法绘图: {e}")
        return ""

    values = [r.capacity_mah for r in result.records if r.capacity_mah > 0]
    if not values:
        logger.warning("没有有效数据，跳过绘图")
        return ""

    stats = result.stats
    if not title:
        title = f"分布 — {result.batch_id}  (n={stats.count})"

    # 创建画布（与 JMP 输出比例相近）
    fig = plt.figure(figsize=(4.0, 8.0), dpi=150)
    gs = GridSpec(
        nrows=4, ncols=1,
        height_ratios=[5.5, 1.6, 1.6, 0.4],
        hspace=0.35,
        left=0.18, right=0.95, top=0.94, bottom=0.04,
    )

    # === 子图 1：直方图 + 箱体图（占顶部 70%） ===
    ax_main = fig.add_subplot(gs[0])

    # 直方图：横向（bins 旋转 90°）
    # 计算合理分箱
    n = len(values)
    n_bins = max(8, min(20, int(math.sqrt(n)) if 'math' in dir() else 10))
    import math
    n_bins = max(8, min(25, int(math.sqrt(n))))

    counts, bin_edges = _histogram(values, n_bins)
    bin_centers = [(bin_edges[i] + bin_edges[i + 1]) / 2 for i in range(len(bin_edges) - 1)]
    bin_width = bin_edges[1] - bin_edges[0]

    # 横向直方图：X 是容量，Y 是频数
    for i, c in enumerate(counts):
        if c > 0:
            ax_main.barh(
                bin_centers[i], c,
                height=bin_width * 0.92,
                color=_JMP_GREEN,
                edgecolor=_JMP_GREEN_EDGE,
                linewidth=0.5,
            )

    # === 子图 2：箱体图（叠加在直方图右侧 12% 位置）===
    ax_box = fig.add_subplot(gs[1], sharey=ax_main)
    _draw_box(ax_box, values, stats)

    # 主图样式
    ax_main.set_xlabel("频数", fontsize=9)
    ax_main.tick_params(axis="both", labelsize=8)
    ax_main.grid(axis="x", linestyle=":", color="#cccccc", linewidth=0.5)
    ax_main.set_axisbelow(True)
    ax_main.set_title(title, fontsize=10, loc="left", pad=8)

    # Y 轴标签旋转 90 放在左侧
    for label in ax_main.get_yticklabels():
        label.set_rotation(0)

    # === 子图 3：分位数表（占中段）===
    ax_qt = fig.add_subplot(gs[2])
    _draw_quantile_table(ax_qt, stats, values)
    ax_qt.set_xticks([])
    ax_qt.set_yticks([])

    # === 子图 4：汇总统计表（占底部）===
    ax_st = fig.add_subplot(gs[3])
    _draw_summary_table(ax_st, stats)
    ax_st.set_xticks([])
    ax_st.set_yticks([])

    # 保存
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    logger.info(f"分布图已生成: {output_path}")
    return output_path


def _histogram(values: List[float], n_bins: int):
    """简单直方图分箱"""
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


def _draw_box(ax, values: List[float], stats: CapacityStats):
    """在 ax 上画垂直箱体图（含离群点）"""
    from matplotlib.patches import Rectangle
    q1, med, q3 = stats.q1, stats.median, stats.q3
    iqr = q3 - q1
    lower_fence = q1 - 1.5 * iqr
    upper_fence = q3 + 1.5 * iqr
    outliers = [v for v in values if v < lower_fence or v > upper_fence]
    non_outliers = [v for v in values if lower_fence <= v <= upper_fence]
    v_min = min(values) if values else 0
    v_max = max(values) if values else 1

    # 箱体（蓝色填充）
    box_height = (q3 - q1) * 0.35
    rect = Rectangle(
        (0.45, q1), 0.1, q3 - q1,
        facecolor=_JMP_BOX_BLUE, edgecolor=_JMP_BOX_EDGE,
        linewidth=0.8, zorder=3,
    )
    ax.add_patch(rect)
    # 中位数线
    ax.plot([0.45, 0.55], [med, med], color="white", linewidth=1.5, zorder=4)
    # 上下须（whiskers）
    if non_outliers:
        upper_whisker = max(v for v in non_outliers if v <= q3)
        lower_whisker = min(v for v in non_outliers if v >= q1)
    else:
        upper_whisker, lower_whisker = q3, q1
    ax.plot([0.5, 0.5], [q3, upper_whisker], color=_JMP_BOX_EDGE, linewidth=0.8, zorder=2)
    ax.plot([0.5, 0.5], [q1, lower_whisker], color=_JMP_BOX_EDGE, linewidth=0.8, zorder=2)
    # 离群点
    for ov in outliers:
        ax.plot(0.5, ov, marker="o", markersize=3,
                markerfacecolor=_JMP_OUTLIER, markeredgecolor=_JMP_OUTLIER, zorder=5)

    ax.set_xlim(0, 1)
    ax.set_xticks([])
    ax.set_ylim(v_min - (v_max - v_min) * 0.02, v_max + (v_max - v_min) * 0.02)


def _draw_quantile_table(ax, stats: CapacityStats, values: List[float]):
    """分位数表（左：百分位 | 右：值）"""
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    rows = [
        ("100.0%", stats.max_v, "最大值", stats.max_v),
        ("99.5%",  _percentile_safe(values, 99.5), "", ""),
        ("97.5%",  stats.p97_5, "", ""),
        ("90.0%",  _percentile_safe(values, 90.0), "", ""),
        ("75.0%",  stats.q3, "四分位数", stats.q3),
        ("50.0%",  stats.median, "中位数", stats.median),
        ("25.0%",  stats.q1, "", ""),
        ("10.0%",  _percentile_safe(values, 10.0), "", ""),
        ("2.5%",   stats.p2_5, "", ""),
        ("0.5%",   _percentile_safe(values, 0.5), "", ""),
        ("0.0%",   stats.min_v, "最小值", stats.min_v),
    ]
    ax.text(0.02, 0.92, "分位数", fontsize=8, fontweight="bold", transform=ax.transAxes)
    n = len(rows)
    for i, (p, v, label, label_v) in enumerate(rows):
        y = 0.78 - i * 0.072
        ax.text(0.02, y, p, fontsize=7, transform=ax.transAxes)
        ax.text(0.30, y, f"{v:.2f}", fontsize=7, transform=ax.transAxes)
        if label:
            ax.text(0.55, y, label, fontsize=7, fontweight="bold", transform=ax.transAxes)
            ax.text(0.78, y, f"{label_v:.2f}", fontsize=7, transform=ax.transAxes)


def _draw_summary_table(ax, stats: CapacityStats):
    """汇总统计表"""
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.text(0.02, 0.78, "汇总统计", fontsize=8, fontweight="bold", transform=ax.transAxes)
    rows = [
        ("均值", stats.mean),
        ("标准差", stats.std_dev),
        ("均值标准误差", stats.std_err),
        ("均值 95% 上限", stats.ci95_upper),
        ("均值 95% 下限", stats.ci95_lower),
        ("数目", stats.count),
    ]
    for i, (label, val) in enumerate(rows):
        y = 0.55 - i * 0.13
        ax.text(0.02, y, label, fontsize=7, transform=ax.transAxes)
        ax.text(0.45, y, f"{val:.6f}" if isinstance(val, float) else str(val),
                fontsize=7, transform=ax.transAxes)


def _percentile_safe(values: List[float], p: float) -> float:
    """线性插值百分位数（用于绘图）"""
    if not values:
        return 0.0
    import math
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
