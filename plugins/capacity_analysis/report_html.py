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


_HTML_TEMPLATE = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
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
.fold {{ display: flex; align-items: center; gap: 4px; height: 22px; background: var(--panel-gray); border: 1px solid var(--panel-border); font-weight: 700; line-height: 22px; padding: 0 6px; }}
.fold.top {{ width: 120px; margin-left: 0; font-size: 16px; }}
.fold.sub {{ width: 290px; margin-left: 28px; font-size: 16px; margin-top: 2px; }}
.tri {{ width: 0; height: 0; border-left: 6px solid transparent; border-right: 6px solid transparent; border-top: 7px solid var(--red); margin-left: 4px; }}
.disclosure {{ width: 0; height: 0; border-left: 6px solid transparent; border-right: 6px solid transparent; border-top: 8px solid #777; margin-left: 2px; }}
.canvas-wrap {{ margin-left: 0; margin-top: 4px; width: 360px; }}
canvas {{ display: block; width: 360px; height: 470px; }}
.section-title {{ display: flex; align-items: center; height: 22px; margin-top: 10px; background: var(--panel-gray); border: 1px solid var(--panel-border); font-weight: 700; font-size: 15px; width: 200px; padding: 0 6px; }}
.section-title .tri {{ margin-left: 4px; }}
.tables {{ font-size: 14px; line-height: 1.18; font-family: Arial, 'Microsoft YaHei', SimSun, sans-serif; }}
.quantile-grid {{ display: grid; grid-template-columns: 60px 78px 86px 80px; width: 320px; column-gap: 0; margin-top: 2px; }}
.quantile-grid .row {{ display: contents; }}
.quantile-grid .pct {{ background: #ededed; padding-left: 6px; color: #111; display: flex; align-items: center; min-height: 20px; }}
.quantile-grid .value, .quantile-grid .right-value {{ text-align: right; padding-right: 8px; display: flex; align-items: center; justify-content: flex-end; min-height: 20px; font-family: Consolas, 'Courier New', monospace; }}
.quantile-grid .label {{ padding-left: 8px; color: #222; display: flex; align-items: center; min-height: 20px; }}
.summary-grid {{ display: grid; grid-template-columns: 150px 130px; width: 290px; column-gap: 0; margin-top: 2px; }}
.summary-grid .name {{ background: #ededed; padding-left: 6px; color: #111; display: flex; align-items: center; min-height: 20px; }}
.summary-grid .val {{ text-align: right; padding-right: 8px; display: flex; align-items: center; justify-content: flex-end; min-height: 20px; font-family: Consolas, 'Courier New', monospace; }}
.meta {{ margin-top: 10px; color: var(--muted); font-size: 12px; line-height: 1.5; max-width: 520px; }}
@media print {{ .toolbar {{ display: none; }} body {{ padding: 0; }} }}
</style>
</head>
<body>
<div class="toolbar">
  <label>直方图柱间距</label>
  <input id="gapRange" type="range" min="0" max="70" step="1" value="8" aria-label="直方图柱间距">
  <input id="gapNumber" type="number" min="0" max="70" step="1" value="8">%
  <button id="exportBtn" type="button">导出图片</button>
  <span id="status" class="status">调整滑块可实时预览</span>
</div>

<main class="report" id="report">
  <div class="fold top"><span class="disclosure"></span><span>分布</span></div>
  <div class="fold sub"><span class="tri"></span><span>容量</span></div>
  <div class="canvas-wrap"><canvas id="distCanvas" width="572" height="748"></canvas></div>

  <div class="section-title"><span class="tri"></span><span>分位数</span></div>
  <div class="tables quantile-grid" id="quantileTable"></div>

  <div class="section-title"><span class="tri"></span><span>汇总统计量</span></div>
  <div class="tables summary-grid" id="summaryTable"></div>

  <div class="meta" id="meta"></div>
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

function fmt(v, digits) {{
  if (digits === undefined) digits = 4;
  if (v === null || v === undefined || Number.isNaN(Number(v))) return '';
  var text = Number(v).toFixed(digits);
  while (text.indexOf('.') !== -1 && text.charAt(text.length - 1) === '0') text = text.slice(0, -1);
  if (text.charAt(text.length - 1) === '.') text = text.slice(0, -1);
  return text;
}}

function niceTicks(min, max, maxTicks) {{
  if (maxTicks === undefined) maxTicks = 8;
  var span = Math.max(1e-9, max - min);
  var rawStep = span / Math.max(1, maxTicks - 1);
  var pow = Math.pow(10, Math.floor(Math.log10(rawStep)));
  var candidates = [1, 2, 5, 10].map(function (x) {{ return x * pow; }});
  var step = candidates[candidates.length - 1];
  for (var i = 0; i < candidates.length; i++) {{
    if (rawStep <= candidates[i]) {{ step = candidates[i]; break; }}
  }}
  var start = Math.ceil(min / step) * step;
  var ticks = [];
  for (var t = start; t <= max + step * 0.5; t += step) ticks.push(t);
  return ticks;
}}

function draw(gapPct) {{
  var values = DATA.values;
  var stats = DATA.stats;
  var W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = '#fff';
  ctx.fillRect(0, 0, W, H);

  var top = 8, bottom = 30;
  var left = 56;
  var boxLeft = 484, boxRight = 560;
  var plotH = H - top - bottom;
  var yMin0 = Math.min.apply(null, values), yMax0 = Math.max.apply(null, values);
  var span0 = yMax0 - yMin0;
  var pad = Math.max(2, span0 * 0.04);
  var yMin = yMin0 - pad, yMax = yMax0 + pad;
  var y = function (v) {{ return top + (yMax - v) / (yMax - yMin) * plotH; }};

  var span = yMax - yMin;
  var fd = span / Math.max(8, Math.pow(values.length, 1 / 3) * 2);
  var binW = Math.max(span / 24, fd);
  var mag = Math.pow(10, Math.floor(Math.log10(binW)));
  var norm = binW / mag;
  var step;
  if (norm < 1.5) step = 1 * mag;
  else if (norm < 3) step = 2 * mag;
  else if (norm < 7) step = 5 * mag;
  else step = 10 * mag;
  binW = step;
  var binCount = Math.max(10, Math.min(28, Math.ceil(span / binW)));
  var firstEdge = Math.floor(yMin / binW) * binW;
  var lastEdge = Math.ceil(yMax / binW) * binW;
  var edges = [];
  for (var e = firstEdge; e <= lastEdge + 1e-9; e += binW) edges.push(e);
  var counts = new Array(edges.length - 1).fill(0);
  for (var vi = 0; vi < values.length; vi++) {{
    var v = values[vi];
    var idx = Math.floor((v - edges[0]) / binW);
    if (idx < 0) idx = 0;
    if (idx >= counts.length) idx = counts.length - 1;
    counts[idx]++;
  }}
  var maxCount = Math.max.apply(null, counts.concat([1]));

  ctx.strokeStyle = '#111';
  ctx.lineWidth = 1.5;
  ctx.strokeRect(left, top, boxRight - left, plotH);
  ctx.beginPath();
  ctx.moveTo(boxLeft, top);
  ctx.lineTo(boxLeft, top + plotH);
  ctx.stroke();

  var yTicks = niceTicks(yMin, yMax, 8);
  ctx.font = '20px Arial, "Microsoft YaHei", sans-serif';
  ctx.fillStyle = '#222';
  ctx.textAlign = 'right';
  ctx.textBaseline = 'middle';
  for (var yi = 0; yi < yTicks.length; yi++) {{
    var t = yTicks[yi];
    var yy = y(t);
    ctx.strokeStyle = '#222'; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(left - 6, yy); ctx.lineTo(left, yy); ctx.stroke();
    ctx.fillText(fmt(t, 0), left - 9, yy);
  }}

  var xTicks = niceTicks(0, maxCount, 7);
  ctx.strokeStyle = '#cfcfcf';
  ctx.lineWidth = 1;
  ctx.setLineDash([2, 3]);
  for (var xi = 0; xi < xTicks.length; xi++) {{
    var xt = xTicks[xi];
    var x = left + xt / maxCount * (boxLeft - left);
    ctx.beginPath(); ctx.moveTo(x, top); ctx.lineTo(x, top + plotH); ctx.stroke();
  }}
  ctx.setLineDash([]);
  ctx.font = '20px Arial, "Microsoft YaHei", sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'top';
  for (var xi2 = 0; xi2 < xTicks.length; xi2++) {{
    var xt2 = xTicks[xi2];
    var x2 = left + xt2 / maxCount * (boxLeft - left);
    ctx.fillText(String(Math.round(xt2)), x2, top + plotH + 8);
  }}

  var gapRatio = Math.max(0, Math.min(0.85, gapPct / 100));
  for (var i = 0; i < counts.length; i++) {{
    var y1 = y(edges[i]);
    var y2 = y(edges[i + 1]);
    var bandTop = Math.min(y1, y2);
    var bandH = Math.abs(y2 - y1);
    var barH = Math.max(1, bandH * (1 - gapRatio));
    var barY = bandTop + (bandH - barH) / 2;
    var xEnd = left + counts[i] / maxCount * (boxLeft - left);
    var barW = Math.max(0, xEnd - left);
    ctx.fillStyle = 'rgba(168, 198, 152, 0.95)';
    ctx.strokeStyle = '#5d765d';
    ctx.lineWidth = 1;
    if (barW > 0) {{
      ctx.fillRect(left, barY, barW, barH);
      ctx.strokeRect(left, barY, barW, barH);
    }}
  }}

  drawBoxplot(y, boxLeft, boxRight, top, plotH, values, stats, left);
}}

function drawBoxplot(y, boxLeft, boxRight, top, plotH, values, stats, mainLeft) {{
  var cx = (boxLeft + boxRight) / 2;
  var boxW = 28;
  var q1 = stats.q1, q3 = stats.q3, med = stats.median;
  var iqr = q3 - q1;
  var lowerFence = q1 - 1.5 * iqr;
  var upperFence = q3 + 1.5 * iqr;
  var nonOut = values.filter(function (v) {{ return v >= lowerFence && v <= upperFence; }});
  var out = values.filter(function (v) {{ return v < lowerFence || v > upperFence; }});
  var lo = nonOut.length ? Math.min.apply(null, nonOut) : q1;
  var hi = nonOut.length ? Math.max.apply(null, nonOut) : q3;

  ctx.strokeStyle = '#111'; ctx.lineWidth = 1.5;
  ctx.beginPath(); ctx.moveTo(cx, y(q3)); ctx.lineTo(cx, y(hi)); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(cx - 12, y(hi)); ctx.lineTo(cx + 12, y(hi)); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(cx, y(q1)); ctx.lineTo(cx, y(lo)); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(cx - 12, y(lo)); ctx.lineTo(cx + 12, y(lo)); ctx.stroke();

  ctx.fillStyle = '#fff'; ctx.strokeStyle = '#111'; ctx.lineWidth = 1.5;
  var boxY = y(q3), boxH = Math.max(4, y(q1) - y(q3));
  ctx.fillRect(cx - boxW / 2, boxY, boxW, boxH);
  ctx.strokeRect(cx - boxW / 2, boxY, boxW, boxH);
  ctx.strokeStyle = '#111'; ctx.lineWidth = 1.5;
  ctx.beginPath(); ctx.moveTo(cx - boxW / 2, y(med)); ctx.lineTo(cx + boxW / 2, y(med)); ctx.stroke();

  ctx.strokeStyle = '#d33'; ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(cx - boxW / 2 - 6, y(q1));
  ctx.lineTo(cx - boxW / 2 - 12, y(q1));
  ctx.lineTo(cx - boxW / 2 - 12, y(q3));
  ctx.lineTo(cx - boxW / 2 - 6, y(q3));
  ctx.stroke();

  ctx.fillStyle = '#000';
  for (var oi = 0; oi < out.length; oi++) {{
    var yy = y(out[oi]);
    ctx.beginPath(); ctx.arc(cx, yy, 3, 0, Math.PI * 2); ctx.fill();
  }}

  ctx.strokeStyle = '#111'; ctx.lineWidth = 1.5;
  var my = y(stats.mean);
  ctx.beginPath();
  ctx.moveTo(cx, my - 9);
  ctx.lineTo(cx + 8, my);
  ctx.lineTo(cx, my + 9);
  ctx.lineTo(cx - 8, my);
  ctx.closePath();
  ctx.stroke();

  ctx.fillStyle = '#d33';
  ctx.font = 'bold 13px Arial, sans-serif';
  ctx.textAlign = 'left';
  ctx.textBaseline = 'middle';
  ctx.fillText('C', boxLeft - 18, my);
}}

function buildTables() {{
  var q = document.getElementById('quantileTable');
  q.innerHTML = '';
  for (var i = 0; i < DATA.quantiles.length; i++) {{
    var row = DATA.quantiles[i];
    var pct = document.createElement('div'); pct.className = 'pct'; pct.textContent = row.pct;
    var value = document.createElement('div'); value.className = 'value'; value.textContent = fmt(row.value, 3);
    var label = document.createElement('div'); label.className = 'label'; label.textContent = row.label || '';
    var right = document.createElement('div'); right.className = 'right-value'; right.textContent = row.label ? fmt(row.value, 3) : '';
    q.append(pct, value, label, right);
  }}
  var s = DATA.stats;
  var rows = [
    ['均值', s.mean], ['标准差', s.stdDev], ['均值标准误差', s.stdErr],
    ['均值 95% 上限', s.ci95Upper], ['均值 95% 下限', s.ci95Lower], ['数目', s.count]
  ];
  var summary = document.getElementById('summaryTable');
  summary.innerHTML = '';
  for (var ri = 0; ri < rows.length; ri++) {{
    var name = rows[ri][0];
    var val = rows[ri][1];
    var n = document.createElement('div'); n.className = 'name'; n.textContent = name;
    var v = document.createElement('div'); v.className = 'val'; v.textContent = name === '数目' ? String(val) : fmt(val, 6);
    summary.append(n, v);
  }}
  var abnormalText = Object.keys(DATA.abnormal).map(function (k) {{ return k + ':' + DATA.abnormal[k]; }}).join('，') || '无';
  var groups = Object.keys(DATA.cycleGroups).map(function (k) {{ return k + '次分容 ' + DATA.cycleGroups[k] + '块'; }}).join('，') || '无';
  document.getElementById('meta').textContent = '批次：' + DATA.batchId + '｜样本：' + s.count + '｜分容次数：' + groups + '｜剔除异常：' + abnormalText + '｜生成：' + DATA.generatedAt;
}}

function syncGap(value) {{
  var v = Math.max(0, Math.min(70, Number(value) || 0));
  gapRange.value = v; gapNumber.value = v;
  draw(v);
  statusEl.textContent = '当前柱间距：' + v + '%';
}}

gapRange.addEventListener('input', function (e) {{ syncGap(e.target.value); }});
gapNumber.addEventListener('input', function (e) {{ syncGap(e.target.value); }});
exportBtn.addEventListener('click', function () {{
  statusEl.textContent = '正在导出图片...';
  canvas.toBlob(function (blob) {{
    if (!blob) {{ statusEl.textContent = '导出失败：浏览器未生成图片'; return; }}
    var url = URL.createObjectURL(blob);
    var link = document.createElement('a');
    link.href = url;
    var safeName = String(DATA.batchId || 'capacity_distribution');
    var badChars = ['\\', '/', ':', '*', '?', '"', '<', '>', '|'];
    for (var ci = 0; ci < badChars.length; ci++) safeName = safeName.split(badChars[ci]).join('_');
    link.download = safeName + '.png';
    link.style.display = 'none';
    document.body.appendChild(link);
    link.click();
    setTimeout(function () {{
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


def render_distribution_html(result: AnalysisResult, output_path: str) -> str:
    """生成自包含 HTML 报告并返回输出路径。"""
    values = [float(r.capacity_mah) for r in result.records if r.capacity_mah > 0]
    if not values:
        logger.warning("没有有效数据，跳过 HTML 报告生成")
        return ""

    payload = _build_payload(result)
    payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    safe_title = html.escape(f"分容分布报告 - {result.batch_id}")

    doc = _HTML_TEMPLATE.replace("{title}", safe_title).replace("{payload_json}", payload_json)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(doc)
    logger.info(f"HTML 分布报告已生成: {output_path}")
    return output_path
