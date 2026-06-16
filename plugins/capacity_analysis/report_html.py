# -*- coding: utf-8 -*-
"""分容分析 HTML 交互报告生成器。

生成单文件、自包含 HTML：
- Canvas 绘制 JMP 风格「分布 / 容量」报告
- 直方图柱间距滑块实时调节
- 内置导出 PNG，导出后清理临时下载链接与 ObjectURL
- 不依赖外部 JS/CSS/CDN
"""

from __future__ import annotations

import datetime as _dt
import html
import json
import math
import os
from typing import List

from core.logger import get_logger
from plugins.capacity_analysis.models import AnalysisResult, CapacityStats

logger = get_logger("capacity_analysis.report_html")


def _fmt(value: float, digits: int = 4) -> str:
    try:
        if value is None:
            return ""
        return f"{float(value):.{digits}f}".rstrip("0").rstrip(".")
    except Exception:
        return str(value)


def _percentile(values: List[float], p: float) -> float:
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


def _build_payload(result: AnalysisResult) -> dict:
    values = [float(r.capacity_mah) for r in result.records if r.capacity_mah > 0]
    stats: CapacityStats = result.stats
    quantiles = [
        {"pct": "100.0%", "label": "最大值", "value": _percentile(values, 100)},
        {"pct": "99.5%", "label": "", "value": _percentile(values, 99.5)},
        {"pct": "97.5%", "label": "", "value": _percentile(values, 97.5)},
        {"pct": "90.0%", "label": "", "value": _percentile(values, 90)},
        {"pct": "75.0%", "label": "四分位数", "value": stats.q3},
        {"pct": "50.0%", "label": "中位数", "value": stats.median},
        {"pct": "25.0%", "label": "四分位数", "value": stats.q1},
        {"pct": "10.0%", "label": "", "value": _percentile(values, 10)},
        {"pct": "2.5%", "label": "", "value": stats.p2_5},
        {"pct": "0.5%", "label": "", "value": _percentile(values, 0.5)},
        {"pct": "0.0%", "label": "最小值", "value": _percentile(values, 0)},
    ]
    cycle_groups = {}
    for rec in result.records:
        cycle_groups[str(rec.cycle_count)] = cycle_groups.get(str(rec.cycle_count), 0) + 1
    abnormal = {k: len(v) for k, v in result.abnormal.items() if v}
    return {
        "batchId": result.batch_id,
        "sourceFile": result.source_file,
        "generatedAt": _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "values": values,
        "stats": {
            "count": stats.count,
            "mean": stats.mean,
            "stdDev": stats.std_dev,
            "stdErr": stats.std_err,
            "ci95Upper": stats.ci95_upper,
            "ci95Lower": stats.ci95_lower,
            "min": stats.min_v,
            "max": stats.max_v,
            "q1": stats.q1,
            "median": stats.median,
            "q3": stats.q3,
            "p2_5": stats.p2_5,
            "p97_5": stats.p97_5,
        },
        "quantiles": quantiles,
        "cycleGroups": cycle_groups,
        "abnormal": abnormal,
    }


def render_distribution_html(result: AnalysisResult, output_path: str) -> str:
    """生成自包含 HTML 报告并返回输出路径。"""
    values = [float(r.capacity_mah) for r in result.records if r.capacity_mah > 0]
    if not values:
        logger.warning("没有有效数据，跳过 HTML 报告生成")
        return ""

    payload = _build_payload(result)
    payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    safe_title = html.escape(f"分容分布报告 - {result.batch_id}")

    doc = f"""<!doctype html>
<html lang=\"zh-CN\">
<head>
<meta charset=\"utf-8\">
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
<title>{safe_title}</title>
<style>
:root {{
  --panel-gray: #e9e9e9;
  --panel-border: #bcbcbc;
  --text: #111;
  --muted: #666;
  --green: #c4d1c1;
  --green-edge: #6d806d;
  --red: #d52b2b;
  --blue: #4a61a8;
}}
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; background: #fff; color: var(--text); font-family: Arial, 'Microsoft YaHei', SimSun, sans-serif; }}
body {{ padding: 12px 14px 24px; }}
.toolbar {{
  position: sticky; top: 0; z-index: 5; display: flex; flex-wrap: wrap; align-items: center; gap: 10px;
  margin: -12px -14px 10px; padding: 10px 14px; background: rgba(248,248,248,.96);
  border-bottom: 1px solid #d0d0d0; backdrop-filter: blur(4px);
}}
.toolbar label {{ font-size: 13px; color: #222; }}
.toolbar input[type=range] {{ width: 190px; }}
.toolbar input[type=number] {{ width: 58px; padding: 3px 5px; border: 1px solid #aaa; }}
button {{ padding: 5px 12px; border: 1px solid #999; border-radius: 2px; background: linear-gradient(#fff, #e8e8e8); cursor: pointer; font-size: 13px; }}
button:hover {{ background: linear-gradient(#fff, #ddd); }}
.status {{ font-size: 12px; color: #266b26; min-width: 180px; }}
.report {{ width: 390px; max-width: 100%; }}
.fold {{ display: flex; align-items: center; gap: 4px; height: 24px; background: var(--panel-gray); border: 1px solid var(--panel-border); font-weight: 700; line-height: 24px; }}
.fold.top {{ width: 120px; margin-left: 0; font-size: 20px; height: 26px; }}
.fold.sub {{ width: 322px; margin-left: 28px; font-size: 20px; height: 26px; margin-top: 2px; }}
.tri {{ width: 0; height: 0; border-left: 7px solid transparent; border-right: 7px solid transparent; border-top: 9px solid var(--red); margin-left: 5px; filter: drop-shadow(0 0 0 #900); }}
.disclosure {{ width: 0; height: 0; border-left: 6px solid transparent; border-right: 6px solid transparent; border-top: 8px solid #777; margin-left: 2px; }}
.canvas-wrap {{ margin-left: 46px; margin-top: 10px; width: 286px; }}
canvas {{ display: block; width: 286px; height: 374px; }}
.section-title {{ display: flex; align-items: center; height: 24px; margin-top: 12px; background: var(--panel-gray); border: 1px solid var(--panel-border); font-weight: 700; font-size: 18px; width: 240px; }}
.section-title .tri {{ transform: scale(.78); margin-left: 4px; }}
.tables {{ font-size: 16px; line-height: 1.28; font-family: Arial, 'Microsoft YaHei', SimSun, sans-serif; }}
.quantile-grid {{ display: grid; grid-template-columns: 82px 92px 92px 96px; column-gap: 0; width: 360px; }}
.quantile-grid div {{ min-height: 20px; }}
.quantile-grid .pct {{ background: #efefef; padding-left: 4px; color: #111; }}
.quantile-grid .value, .quantile-grid .right-value {{ text-align: right; padding-right: 8px; font-family: Consolas, 'Courier New', monospace; }}
.quantile-grid .label {{ font-weight: 700; }}
.summary-grid {{ display: grid; grid-template-columns: 150px 120px; width: 300px; column-gap: 8px; }}
.summary-grid .name {{ background: #e8e8e8; padding-left: 4px; }}
.summary-grid .val {{ text-align: right; font-family: Consolas, 'Courier New', monospace; }}
.meta {{ margin-top: 10px; color: var(--muted); font-size: 12px; line-height: 1.5; max-width: 520px; }}
@media print {{ .toolbar {{ display: none; }} body {{ padding: 0; }} }}
</style>
</head>
<body>
<div class=\"toolbar\">
  <label>直方图柱间距</label>
  <input id=\"gapRange\" type=\"range\" min=\"0\" max=\"70\" step=\"1\" value=\"8\" aria-label=\"直方图柱间距\">
  <input id=\"gapNumber\" type=\"number\" min=\"0\" max=\"70\" step=\"1\" value=\"8\">%
  <button id=\"exportBtn\" type=\"button\">导出图片</button>
  <span id=\"status\" class=\"status\">调整滑块可实时预览</span>
</div>

<main class=\"report\" id=\"report\">
  <div class=\"fold top\"><span class=\"disclosure\"></span><span>分布</span></div>
  <div class=\"fold sub\"><span class=\"tri\"></span><span>容量</span></div>
  <div class=\"canvas-wrap\"><canvas id=\"distCanvas\" width=\"572\" height=\"748\"></canvas></div>

  <div class=\"section-title\"><span class=\"tri\"></span><span>分位数</span></div>
  <div class=\"tables quantile-grid\" id=\"quantileTable\"></div>

  <div class=\"section-title\"><span class=\"tri\"></span><span>汇总统计量</span></div>
  <div class=\"tables summary-grid\" id=\"summaryTable\"></div>

  <div class=\"meta\" id=\"meta\"></div>
</main>

<script>
'use strict';
const DATA = {payload_json};
const canvas = document.getElementById('distCanvas');
const ctx = canvas.getContext('2d');
const gapRange = document.getElementById('gapRange');
const gapNumber = document.getElementById('gapNumber');
const statusEl = document.getElementById('status');
const exportBtn = document.getElementById('exportBtn');

function fmt(v, digits = 4) {{
  if (v === null || v === undefined || Number.isNaN(Number(v))) return '';
  let text = Number(v).toFixed(digits);
  while (text.includes('.') && text.endsWith('0')) text = text.slice(0, -1);
  if (text.endsWith('.')) text = text.slice(0, -1);
  return text;
}}

function histogram(values, binCount) {{
  const min = Math.min(...values);
  const max = Math.max(...values);
  if (min === max) return {{ counts: [values.length], edges: [min, max + 1] }};
  const width = (max - min) / binCount;
  const counts = new Array(binCount).fill(0);
  for (const v of values) {{
    let idx = Math.floor((v - min) / width);
    if (idx < 0) idx = 0;
    if (idx >= binCount) idx = binCount - 1;
    counts[idx]++;
  }}
  const edges = Array.from({{ length: binCount + 1 }}, (_, i) => min + i * width);
  return {{ counts, edges }};
}}

function niceTicks(min, max, maxTicks = 8) {{
  const span = Math.max(1e-9, max - min);
  const rawStep = span / Math.max(1, maxTicks - 1);
  const pow = Math.pow(10, Math.floor(Math.log10(rawStep)));
  const candidates = [1, 2, 5, 10].map(x => x * pow);
  let step = candidates[candidates.length - 1];
  for (const c of candidates) {{ if (rawStep <= c) {{ step = c; break; }} }}
  const start = Math.ceil(min / step) * step;
  const ticks = [];
  for (let t = start; t <= max + step * 0.5; t += step) ticks.push(t);
  return ticks;
}}

function draw(gapPct) {{
  const values = DATA.values;
  const stats = DATA.stats;
  const W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = '#fff';
  ctx.fillRect(0, 0, W, H);

  const left = 68, top = 8, bottom = 46;
  const histRight = 388;
  const boxLeft = 388, boxRight = 542;
  const plotH = H - top - bottom;
  const yMin0 = Math.min(...values), yMax0 = Math.max(...values);
  const pad = Math.max(2, (yMax0 - yMin0) * 0.035);
  const yMin = yMin0 - pad, yMax = yMax0 + pad;
  const y = v => top + (yMax - v) / (yMax - yMin) * plotH;

  const binCount = Math.max(10, Math.min(28, Math.ceil(Math.log2(values.length) + 3)));
  const {{ counts, edges }} = histogram(values, binCount);
  const maxCount = Math.max(...counts, 1);
  const xCount = c => left + c / maxCount * (histRight - left);

  ctx.strokeStyle = '#111';
  ctx.lineWidth = 2;
  ctx.strokeRect(left, top, boxRight - left, plotH);
  ctx.beginPath();
  ctx.moveTo(histRight, top);
  ctx.lineTo(histRight, top + plotH);
  ctx.stroke();

  ctx.strokeStyle = '#dedede';
  ctx.lineWidth = 1;
  ctx.setLineDash([2, 3]);
  const xTicks = niceTicks(0, maxCount, 7);
  for (const t of xTicks) {{
    const x = xCount(t);
    ctx.beginPath(); ctx.moveTo(x, top); ctx.lineTo(x, top + plotH); ctx.stroke();
  }}
  ctx.setLineDash([]);

  ctx.font = '24px Arial, Microsoft YaHei, sans-serif';
  ctx.fillStyle = '#222';
  ctx.textAlign = 'right';
  ctx.textBaseline = 'middle';
  for (const t of niceTicks(yMin0, yMax0, 8)) {{
    const yy = y(t);
    ctx.strokeStyle = '#222'; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(left - 7, yy); ctx.lineTo(left, yy); ctx.stroke();
    ctx.fillText(fmt(t, 0), left - 12, yy);
  }}
  ctx.textAlign = 'center';
  ctx.textBaseline = 'top';
  ctx.font = '22px Arial, Microsoft YaHei, sans-serif';
  for (const t of xTicks) {{
    const x = xCount(t);
    ctx.fillText(String(Math.round(t)), x, top + plotH + 12);
  }}

  const gapRatio = Math.max(0, Math.min(0.85, gapPct / 100));
  for (let i = 0; i < counts.length; i++) {{
    if (!counts[i]) continue;
    const y1 = y(edges[i]);
    const y2 = y(edges[i + 1]);
    const bandTop = Math.min(y1, y2);
    const bandH = Math.abs(y2 - y1);
    const barH = Math.max(1, bandH * (1 - gapRatio));
    const barY = bandTop + (bandH - barH) / 2;
    ctx.fillStyle = 'rgba(154, 201, 154, 0.90)';
    ctx.strokeStyle = '#718f71';
    ctx.lineWidth = 1;
    ctx.fillRect(left, barY, Math.max(1, xCount(counts[i]) - left), barH);
    ctx.strokeRect(left, barY, Math.max(1, xCount(counts[i]) - left), barH);
  }}

  drawBoxplot(y, boxLeft, boxRight, top, plotH, values, stats);
}}

function drawBoxplot(y, boxLeft, boxRight, top, plotH, values, stats) {{
  const cx = (boxLeft + boxRight) / 2 + 8;
  const boxW = 42;
  const q1 = stats.q1, q3 = stats.q3, med = stats.median;
  const iqr = q3 - q1;
  const lowerFence = q1 - 1.5 * iqr;
  const upperFence = q3 + 1.5 * iqr;
  const nonOut = values.filter(v => v >= lowerFence && v <= upperFence);
  const out = values.filter(v => v < lowerFence || v > upperFence);
  const lo = Math.min(...nonOut), hi = Math.max(...nonOut);

  ctx.strokeStyle = '#aaa'; ctx.lineWidth = 2;
  ctx.beginPath(); ctx.moveTo(boxLeft, top); ctx.lineTo(boxLeft, top + plotH); ctx.stroke();

  ctx.strokeStyle = '#111'; ctx.lineWidth = 2;
  ctx.beginPath(); ctx.moveTo(cx, y(q3)); ctx.lineTo(cx, y(hi)); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(cx - 18, y(hi)); ctx.lineTo(cx + 18, y(hi)); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(cx, y(q1)); ctx.lineTo(cx, y(lo)); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(cx - 18, y(lo)); ctx.lineTo(cx + 18, y(lo)); ctx.stroke();

  ctx.fillStyle = '#fff'; ctx.strokeStyle = '#111'; ctx.lineWidth = 2;
  const boxY = y(q3), boxH = Math.max(6, y(q1) - y(q3));
  ctx.fillRect(cx - boxW / 2, boxY, boxW, boxH);
  ctx.strokeRect(cx - boxW / 2, boxY, boxW, boxH);
  ctx.strokeStyle = '#111'; ctx.lineWidth = 2;
  ctx.beginPath(); ctx.moveTo(cx - boxW / 2, y(med)); ctx.lineTo(cx + boxW / 2, y(med)); ctx.stroke();

  ctx.strokeStyle = '#d33'; ctx.lineWidth = 2;
  ctx.beginPath(); ctx.moveTo(cx - boxW / 2 - 14, y(q1)); ctx.lineTo(cx - boxW / 2 - 22, y(q1)); ctx.lineTo(cx - boxW / 2 - 22, y(q3)); ctx.lineTo(cx - boxW / 2 - 14, y(q3)); ctx.stroke();

  ctx.strokeStyle = '#111'; ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(cx, y(stats.mean) - 16); ctx.lineTo(cx + 14, y(stats.mean)); ctx.lineTo(cx, y(stats.mean) + 16); ctx.lineTo(cx - 14, y(stats.mean)); ctx.closePath();
  ctx.stroke();

  ctx.fillStyle = '#000';
  for (const v of out) {{
    const yy = y(v);
    ctx.beginPath(); ctx.arc(cx + 2, yy, 5, 0, Math.PI * 2); ctx.fill();
  }}
}}

function buildTables() {{
  const q = document.getElementById('quantileTable');
  q.innerHTML = '';
  for (const row of DATA.quantiles) {{
    const pct = document.createElement('div'); pct.className = 'pct'; pct.textContent = row.pct;
    const value = document.createElement('div'); value.className = 'value'; value.textContent = fmt(row.value, 3);
    const label = document.createElement('div'); label.className = 'label'; label.textContent = row.label || '';
    const right = document.createElement('div'); right.className = 'right-value'; right.textContent = row.label ? fmt(row.value, 3) : '';
    q.append(pct, value, label, right);
  }}
  const s = DATA.stats;
  const rows = [
    ['均值', s.mean], ['标准差', s.stdDev], ['均值标准误差', s.stdErr],
    ['均值 95% 上限', s.ci95Upper], ['均值 95% 下限', s.ci95Lower], ['数目', s.count]
  ];
  const summary = document.getElementById('summaryTable');
  summary.innerHTML = '';
  for (const [name, val] of rows) {{
    const n = document.createElement('div'); n.className = 'name'; n.textContent = name;
    const v = document.createElement('div'); v.className = 'val'; v.textContent = name === '数目' ? String(val) : fmt(val, 6);
    summary.append(n, v);
  }}
  const abnormalText = Object.entries(DATA.abnormal).map(([k, v]) => `${{k}}:${{v}}`).join('，') || '无';
  const groups = Object.entries(DATA.cycleGroups).map(([k, v]) => `${{k}}次分容 ${{v}}块`).join('，') || '无';
  document.getElementById('meta').textContent = `批次：${{DATA.batchId}}｜样本：${{s.count}}｜分容次数：${{groups}}｜剔除异常：${{abnormalText}}｜生成：${{DATA.generatedAt}}`;
}}

function syncGap(value) {{
  const v = Math.max(0, Math.min(70, Number(value) || 0));
  gapRange.value = v; gapNumber.value = v;
  draw(v);
  statusEl.textContent = `当前柱间距：${{v}}%`;
}}

gapRange.addEventListener('input', e => syncGap(e.target.value));
gapNumber.addEventListener('input', e => syncGap(e.target.value));
exportBtn.addEventListener('click', () => {{
  statusEl.textContent = '正在导出图片...';
  canvas.toBlob(blob => {{
    if (!blob) {{ statusEl.textContent = '导出失败：浏览器未生成图片'; return; }}
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    let safeName = String(DATA.batchId || 'capacity_distribution');
    for (const ch of ['\\\\', '/', ':', '*', '?', '"', '<', '>', '|']) safeName = safeName.split(ch).join('_');
    link.download = safeName + '.png';
    link.style.display = 'none';
    document.body.appendChild(link);
    link.click();
    setTimeout(() => {{
      URL.revokeObjectURL(url);
      link.remove();
      statusEl.textContent = '图片已导出，临时下载对象已清理';
    }}, 300);
  }}, 'image/png', 1.0);
}});

buildTables();
syncGap(8);
</script>
</body>
</html>
"""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(doc)
    logger.info(f"HTML 分布报告已生成: {output_path}")
    return output_path
