# -*- coding: utf-8 -*-
"""分容分析 HTML 交互报告生成器。

生成单文件、自包含 HTML：
- Canvas 绘制 JMP 风格「分布 / 容量」报告
- 直方图柱间距滑块实时调节
- Y 轴最小值 / 最大值 / 刻度步长参数实时调节
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
from plugins.capacity_analysis.models import AnalysisResult, CapacityRecord, CapacityStats

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


def _build_payload(result: AnalysisResult, records: List[CapacityRecord] | None = None) -> dict:
    data_records = records if records is not None else result.records
    values = [float(r.capacity_mah) for r in data_records if r.capacity_mah > 0]
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
    for rec in data_records:
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
:root {
  --panel-gray: #e9e9e9;
  --panel-border: #bcbcbc;
  --text: #111;
  --muted: #666;
  --green: #c4d1c1;
  --green-edge: #6d806d;
  --red: #d52b2b;
  --blue: #4a61a8;
}
* { box-sizing: border-box; }
html, body { margin: 0; background: #fff; color: var(--text); font-family: Arial, 'Microsoft YaHei', SimSun, sans-serif; }
body { padding: 4px 6px 12px; }
.toolbar {
  display: grid;
  grid-template-columns: 1fr;
  gap: 4px;
  width: 286px;
  margin: 0 0 5px 0;
  padding: 5px 6px;
  border: 1px solid var(--panel-border);
  background: #f6f6f6;
  font-size: 12px;
}
.toolbar-row { display: flex; align-items: center; gap: 5px; flex-wrap: wrap; }
.toolbar-title { font-weight: 700; margin-right: 2px; color: #222; }
.toolbar label { display: inline-flex; align-items: center; gap: 2px; color: #222; }
.toolbar input[type=range] { width: 72px; }
.toolbar input[type=number] { width: 58px; height: 20px; padding: 1px 3px; border: 1px solid #aaa; font-size: 12px; background: #fff; }
.toolbar input[type=checkbox] { margin: 0 2px 0 0; }
.toolbar button { height: 22px; padding: 1px 7px; border: 1px solid #999; border-radius: 2px; background: linear-gradient(#fff, #e8e8e8); cursor: pointer; font-size: 12px; }
.toolbar button:hover { background: linear-gradient(#fff, #ddd); }
.status { color: #266b26; min-height: 16px; }
.status.error { color: #b00020; }
.report { width: 286px; max-width: 100%; }
.fold { display: flex; align-items: center; gap: 3px; height: 20px; background: var(--panel-gray); border: 1px solid var(--panel-border); font-weight: 700; line-height: 20px; padding: 0 4px; }
.fold.top { width: 286px; margin-left: 0; font-size: 16px; }
.fold.sub { width: 240px; margin-left: 18px; font-size: 15px; margin-top: 2px; }
.editable-title { min-width: 24px; outline: none; border-radius: 2px; padding: 0 2px; }
.editable-title:focus { background: #fff; box-shadow: inset 0 0 0 1px #6d8fd6; }
.tri { width: 0; height: 0; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 7px solid var(--red); margin-left: 2px; }
.disclosure { width: 0; height: 0; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 8px solid #777; margin-left: 1px; }
.canvas-wrap { margin-left: 30px; margin-top: 4px; width: 236px; }
canvas { display: block; width: 236px; height: 300px; }
.section-title { display: flex; align-items: center; height: 20px; margin-top: 4px; margin-left: 30px; background: var(--panel-gray); border: 1px solid var(--panel-border); font-weight: 700; font-size: 15px; width: 200px; padding: 0 4px; }
.section-title .tri { margin-left: 2px; }
.tables { font-size: 14px; line-height: 1.08; font-family: Arial, 'Microsoft YaHei', SimSun, sans-serif; }
.quantile-grid { display: grid; grid-template-columns: 52px 78px 88px; width: 218px; column-gap: 0; margin-left: 34px; margin-top: 2px; }
.quantile-grid .row { display: contents; }
.quantile-grid .pct { background: #f1f1f1; padding-left: 2px; color: #111; display: flex; align-items: center; min-height: 17px; }
.quantile-grid .value { text-align: right; padding-right: 4px; display: flex; align-items: center; justify-content: flex-end; min-height: 17px; font-family: Arial, 'Microsoft YaHei', sans-serif; }
.quantile-grid .label { padding-left: 4px; color: #111; display: flex; align-items: center; min-height: 17px; }
.summary-grid { display: grid; grid-template-columns: 112px 94px; width: 206px; column-gap: 0; margin-left: 34px; margin-top: 2px; }
.summary-grid .name { background: #ededed; padding-left: 3px; color: #111; display: flex; align-items: center; min-height: 17px; }
.summary-grid .val { text-align: right; padding-right: 4px; display: flex; align-items: center; justify-content: flex-end; min-height: 17px; font-family: Arial, 'Microsoft YaHei', sans-serif; }
.meta { display: none; }
@media print { .toolbar { display: none; } body { padding: 0; } }
</style>
</head>
<body>
<div class="toolbar" aria-label="图表参数设置">
  <div class="toolbar-row">
    <span class="toolbar-title">Y轴参数设置</span>
    <label><input id="autoY" type="checkbox" checked>自动</label>
    <label>最小<input id="yMinInput" type="number" step="1" disabled></label>
    <label>最大<input id="yMaxInput" type="number" step="1" disabled></label>
    <label>步长<input id="yStepInput" type="number" step="1" min="0" disabled></label>
    <button id="resetAxisBtn" type="button">重置</button>
  </div>
  <div class="toolbar-row">
    <label>柱间距</label>
    <input id="gapRange" type="range" min="0" max="70" step="1" value="8" aria-label="直方图柱间距">
    <input id="gapNumber" type="number" min="0" max="70" step="1" value="8">%
    <button id="exportBtn" type="button">导出图片</button>
  </div>
  <div id="status" class="status" aria-live="polite">调整参数可实时预览</div>
</div>

<main class="report" id="report">
  <div class="fold top"><span class="disclosure"></span><span id="distributionTitle" class="editable-title" contenteditable="true" spellcheck="false">分布</span></div>
  <div class="fold sub"><span class="tri"></span><span id="capacityTitle" class="editable-title" contenteditable="true" spellcheck="false">容量</span></div>
  <div class="canvas-wrap"><canvas id="distCanvas" width="354" height="450"></canvas></div>

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
const autoY = document.getElementById('autoY');
const yMinInput = document.getElementById('yMinInput');
const yMaxInput = document.getElementById('yMaxInput');
const yStepInput = document.getElementById('yStepInput');
const resetAxisBtn = document.getElementById('resetAxisBtn');
const statusEl = document.getElementById('status');
const exportBtn = document.getElementById('exportBtn');
const reportEl = document.getElementById('report');
const distributionTitle = document.getElementById('distributionTitle');
const capacityTitle = document.getElementById('capacityTitle');
var lastValidAxis = null;

function fmt(v, digits) {
  if (digits === undefined) digits = 4;
  if (v === null || v === undefined || Number.isNaN(Number(v))) return '';
  var text = Number(v).toFixed(digits);
  while (text.indexOf('.') !== -1 && text.charAt(text.length - 1) === '0') text = text.slice(0, -1);
  if (text.charAt(text.length - 1) === '.') text = text.slice(0, -1);
  return text;
}

function niceStep(min, max, maxTicks) {
  if (maxTicks === undefined) maxTicks = 8;
  var span = Math.max(1e-9, max - min);
  var rawStep = span / Math.max(1, maxTicks - 1);
  var pow = Math.pow(10, Math.floor(Math.log10(rawStep)));
  var candidates = [1, 2, 5, 10].map(function (x) { return x * pow; });
  var step = candidates[candidates.length - 1];
  for (var i = 0; i < candidates.length; i++) {
    if (rawStep <= candidates[i]) { step = candidates[i]; break; }
  }
  return step;
}

function niceTicks(min, max, maxTicks) {
  var step = niceStep(min, max, maxTicks);
  var start = Math.ceil(min / step) * step;
  var ticks = [];
  for (var t = start; t <= max + step * 0.5; t += step) ticks.push(t);
  return ticks;
}

function numericInputValue(input) {
  if (!input || input.value === '') return null;
  var v = Number(input.value);
  return Number.isFinite(v) ? v : null;
}

function getAutoAxis(values) {
  var yMin0 = Math.min.apply(null, values);
  var yMax0 = Math.max.apply(null, values);
  var span0 = yMax0 - yMin0;
  var pad = Math.max(2, span0 * 0.04);
  var min = yMin0 - pad;
  var max = yMax0 + pad;
  return { min: min, max: max, step: niceStep(min, max, 8), auto: true, error: '' };
}

function readAxisSettings(values) {
  var autoAxis = getAutoAxis(values);
  if (autoY.checked) return autoAxis;
  var min = numericInputValue(yMinInput);
  var max = numericInputValue(yMaxInput);
  var step = numericInputValue(yStepInput);
  if (min === null || max === null) {
    return { error: '请填写有效的 Y 轴最小值和最大值。', fallback: lastValidAxis || autoAxis };
  }
  if (min >= max) {
    return { error: 'Y 轴最小值必须小于最大值。', fallback: lastValidAxis || autoAxis };
  }
  if (step !== null && step <= 0) {
    return { error: 'Y 轴刻度步长必须大于 0。', fallback: lastValidAxis || autoAxis };
  }
  if (step === null) step = niceStep(min, max, 8);
  if ((max - min) / step > 80) {
    return { error: 'Y 轴刻度过密，请调大步长。', fallback: lastValidAxis || autoAxis };
  }
  return { min: min, max: max, step: step, auto: false, error: '' };
}

function axisTicks(axis) {
  var ticks = [];
  var start = Math.ceil(axis.min / axis.step) * axis.step;
  for (var t = start; t <= axis.max + axis.step * 0.5; t += axis.step) ticks.push(t);
  if (!ticks.length) ticks = niceTicks(axis.min, axis.max, 8);
  return ticks;
}

function setStatus(text, isError) {
  statusEl.textContent = text;
  statusEl.className = isError ? 'status error' : 'status';
}

function draw(gapPct) {
  var values = DATA.values;
  var stats = DATA.stats;
  var W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = '#fff';
  ctx.fillRect(0, 0, W, H);

  var top = 6, bottom = 20;
  var left = 44;
  var boxLeft = 282, boxRight = 348;
  var plotH = H - top - bottom;
  var axis = readAxisSettings(values);
  if (axis.error) {
    setStatus(axis.error, true);
    axis = axis.fallback;
  } else {
    lastValidAxis = axis;
  }
  var yMin = axis.min, yMax = axis.max;
  var y = function (v) { return top + (yMax - v) / (yMax - yMin) * plotH; };
  var yClamped = function (v) {
    if (v < yMin) v = yMin;
    if (v > yMax) v = yMax;
    return y(v);
  };

  var span = yMax - yMin;
  var binW;
  if (!axis.auto && Number.isFinite(axis.step) && axis.step > 0) {
    binW = axis.step;
  } else {
    var fd = span / Math.max(8, Math.pow(values.length, 1 / 3) * 2);
    binW = Math.max(span / 24, fd);
    var mag = Math.pow(10, Math.floor(Math.log10(binW)));
    var norm = binW / mag;
    var step;
    if (norm < 1.5) step = 1 * mag;
    else if (norm < 3) step = 2 * mag;
    else if (norm < 7) step = 5 * mag;
    else step = 10 * mag;
    binW = step;
  }
  var firstEdge = Math.floor(yMin / binW) * binW;
  var lastEdge = Math.ceil(yMax / binW) * binW;
  var edges = [];
  for (var e = firstEdge; e <= lastEdge + 1e-9; e += binW) edges.push(e);
  var counts = new Array(edges.length - 1).fill(0);
  var inRangeCount = 0;
  for (var vi = 0; vi < values.length; vi++) {
    var v = values[vi];
    if (v < yMin || v > yMax) continue;
    var idx = Math.floor((v - edges[0]) / binW);
    if (Math.abs(v - edges[edges.length - 1]) < 1e-9) idx = counts.length - 1;
    if (idx < 0) idx = 0;
    if (idx >= counts.length) idx = counts.length - 1;
    counts[idx]++;
    inRangeCount++;
  }
  var maxCount = Math.max.apply(null, counts.concat([1]));

  ctx.strokeStyle = '#111';
  ctx.lineWidth = 1.5;
  ctx.strokeRect(left, top, boxRight - left, plotH);
  ctx.beginPath();
  ctx.moveTo(boxLeft, top);
  ctx.lineTo(boxLeft, top + plotH);
  ctx.stroke();

  var yTicks = axisTicks(axis);
  ctx.font = '14px Arial, "Microsoft YaHei", sans-serif';
  ctx.fillStyle = '#222';
  ctx.textAlign = 'right';
  ctx.textBaseline = 'middle';
  for (var yi = 0; yi < yTicks.length; yi++) {
    var t = yTicks[yi];
    var yy = y(t);
    ctx.strokeStyle = '#222'; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(left - 6, yy); ctx.lineTo(left, yy); ctx.stroke();
    ctx.fillText(fmt(t, 0), left - 9, yy);
  }

  var xTicks = niceTicks(0, maxCount, 7);
  ctx.strokeStyle = '#cfcfcf';
  ctx.lineWidth = 1;
  ctx.setLineDash([2, 3]);
  for (var xi = 0; xi < xTicks.length; xi++) {
    var xt = xTicks[xi];
    var x = left + xt / maxCount * (boxLeft - left);
    ctx.beginPath(); ctx.moveTo(x, top); ctx.lineTo(x, top + plotH); ctx.stroke();
  }
  ctx.setLineDash([]);
  ctx.font = '14px Arial, "Microsoft YaHei", sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'top';
  for (var xi2 = 0; xi2 < xTicks.length; xi2++) {
    var xt2 = xTicks[xi2];
    var x2 = left + xt2 / maxCount * (boxLeft - left);
    ctx.fillText(String(Math.round(xt2)), x2, top + plotH + 8);
  }

  var gapRatio = Math.max(0, Math.min(0.85, gapPct / 100));
  for (var i = 0; i < counts.length; i++) {
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
    if (barW > 0) {
      ctx.fillRect(left, barY, barW, barH);
      ctx.strokeRect(left, barY, barW, barH);
    }
  }

  drawBoxplot(yClamped, boxLeft, boxRight, top, plotH, values, stats, left);
  if (!axis.error) {
    var mode = axis.auto ? '自动Y轴' : ('Y轴 ' + fmt(axis.min, 2) + ' ~ ' + fmt(axis.max, 2) + '，步长 ' + fmt(axis.step, 2));
    var clipped = values.length - inRangeCount;
    setStatus(mode + '，分箱 ' + fmt(binW, 2) + (clipped > 0 ? '，范围外 ' + clipped + ' 点未计入直方图' : '') + '，柱间距 ' + Math.round(gapPct) + '%', false);
  }
}

function drawBoxplot(y, boxLeft, boxRight, top, plotH, values, stats, mainLeft) {
  var cx = (boxLeft + boxRight) / 2;
  var boxW = 22;
  var q1 = stats.q1, q3 = stats.q3, med = stats.median;
  var iqr = q3 - q1;
  var lowerFence = q1 - 1.5 * iqr;
  var upperFence = q3 + 1.5 * iqr;
  var nonOut = values.filter(function (v) { return v >= lowerFence && v <= upperFence; });
  var out = values.filter(function (v) { return v < lowerFence || v > upperFence; });
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
  for (var oi = 0; oi < out.length; oi++) {
    var yy = y(out[oi]);
    ctx.beginPath(); ctx.arc(cx, yy, 2.3, 0, Math.PI * 2); ctx.fill();
  }

  ctx.strokeStyle = '#111'; ctx.lineWidth = 1.5;
  var my = y(stats.mean);
  ctx.beginPath();
  ctx.moveTo(cx, my - 7);
  ctx.lineTo(cx + 6, my);
  ctx.lineTo(cx, my + 7);
  ctx.lineTo(cx - 6, my);
  ctx.closePath();
  ctx.stroke();

  ctx.fillStyle = '#d33';
  ctx.font = 'bold 13px Arial, sans-serif';
  ctx.textAlign = 'left';
  ctx.textBaseline = 'middle';
  ctx.fillText('C', boxLeft - 18, my);
}

function safeTitleText(el, fallback) {
  var text = (el && el.textContent ? el.textContent : '').trim();
  return text || fallback;
}

function drawEditableTitleBars(exportCtx, scale) {
  exportCtx.fillStyle = '#e9e9e9';
  exportCtx.strokeStyle = '#bcbcbc';
  exportCtx.lineWidth = 1 * scale;
  exportCtx.fillRect(0, 0, 286 * scale, 20 * scale);
  exportCtx.strokeRect(0.5 * scale, 0.5 * scale, 285 * scale, 19 * scale);
  exportCtx.beginPath();
  exportCtx.moveTo(8 * scale, 7 * scale);
  exportCtx.lineTo(18 * scale, 7 * scale);
  exportCtx.lineTo(13 * scale, 15 * scale);
  exportCtx.closePath();
  exportCtx.fillStyle = '#777';
  exportCtx.fill();
  exportCtx.fillStyle = '#111';
  exportCtx.font = 'bold ' + (16 * scale) + 'px Arial, "Microsoft YaHei", sans-serif';
  exportCtx.textAlign = 'left';
  exportCtx.textBaseline = 'middle';
  exportCtx.fillText(safeTitleText(distributionTitle, '分布'), 24 * scale, 10 * scale);

  exportCtx.fillStyle = '#e9e9e9';
  exportCtx.strokeStyle = '#bcbcbc';
  exportCtx.fillRect(18 * scale, 22 * scale, 240 * scale, 20 * scale);
  exportCtx.strokeRect(18.5 * scale, 22.5 * scale, 239 * scale, 19 * scale);
  exportCtx.beginPath();
  exportCtx.moveTo(26 * scale, 29 * scale);
  exportCtx.lineTo(36 * scale, 29 * scale);
  exportCtx.lineTo(31 * scale, 36 * scale);
  exportCtx.closePath();
  exportCtx.fillStyle = '#d52b2b';
  exportCtx.fill();
  exportCtx.fillStyle = '#111';
  exportCtx.font = 'bold ' + (15 * scale) + 'px Arial, "Microsoft YaHei", sans-serif';
  exportCtx.fillText(safeTitleText(capacityTitle, '容量'), 42 * scale, 32 * scale);
}

function drawTableToCanvas(exportCtx, rows, x, y, colWidths, rowH, scale, options) {
  exportCtx.font = (options.fontWeight || '') + ' ' + (14 * scale) + 'px Arial, "Microsoft YaHei", SimSun, sans-serif';
  exportCtx.textBaseline = 'middle';
  for (var i = 0; i < rows.length; i++) {
    var row = rows[i];
    var rowY = y + i * rowH;
    for (var c = 0; c < row.length; c++) {
      var cellX = x;
      for (var pc = 0; pc < c; pc++) cellX += colWidths[pc];
      if (options.bg && options.bg[c]) {
        exportCtx.fillStyle = options.bg[c];
        exportCtx.fillRect(cellX * scale, rowY * scale, colWidths[c] * scale, rowH * scale);
      }
      exportCtx.fillStyle = '#111';
      exportCtx.textAlign = options.align && options.align[c] ? options.align[c] : 'left';
      var textX = cellX + 3;
      if (exportCtx.textAlign === 'right') textX = cellX + colWidths[c] - 4;
      if (exportCtx.textAlign === 'center') textX = cellX + colWidths[c] / 2;
      exportCtx.fillText(String(row[c] || ''), textX * scale, (rowY + rowH / 2) * scale);
    }
  }
}

function drawSectionTitle(exportCtx, title, x, y, width, scale) {
  exportCtx.fillStyle = '#e9e9e9';
  exportCtx.strokeStyle = '#bcbcbc';
  exportCtx.lineWidth = 1 * scale;
  exportCtx.fillRect(x * scale, y * scale, width * scale, 20 * scale);
  exportCtx.strokeRect((x + 0.5) * scale, (y + 0.5) * scale, (width - 1) * scale, 19 * scale);
  exportCtx.beginPath();
  exportCtx.moveTo((x + 6) * scale, (y + 7) * scale);
  exportCtx.lineTo((x + 16) * scale, (y + 7) * scale);
  exportCtx.lineTo((x + 11) * scale, (y + 14) * scale);
  exportCtx.closePath();
  exportCtx.fillStyle = '#d52b2b';
  exportCtx.fill();
  exportCtx.fillStyle = '#111';
  exportCtx.font = 'bold ' + (15 * scale) + 'px Arial, "Microsoft YaHei", sans-serif';
  exportCtx.textAlign = 'left';
  exportCtx.textBaseline = 'middle';
  exportCtx.fillText(title, (x + 22) * scale, (y + 10) * scale);
}

function buildReportExportCanvas() {
  var scale = Math.max(2, Math.ceil(window.devicePixelRatio || 1));
  var exportCanvas = document.createElement('canvas');
  var reportHeight = Math.ceil(reportEl.getBoundingClientRect().height || 620);
  exportCanvas.width = 286 * scale;
  exportCanvas.height = reportHeight * scale;
  var exportCtx = exportCanvas.getContext('2d');
  exportCtx.scale(scale, scale);
  exportCtx.fillStyle = '#fff';
  exportCtx.fillRect(0, 0, 286, reportHeight);
  exportCtx.scale(1 / scale, 1 / scale);

  drawEditableTitleBars(exportCtx, scale);
  exportCtx.drawImage(canvas, 0, 0, canvas.width, canvas.height, 30 * scale, 46 * scale, 236 * scale, 300 * scale);

  var qTitleY = 350;
  drawSectionTitle(exportCtx, '分位数', 30, qTitleY, 200, scale);
  var qRows = DATA.quantiles.map(function (row) { return [row.pct, row.label || '', fmt(row.value, 2)]; });
  drawTableToCanvas(exportCtx, qRows, 34, qTitleY + 22, [52, 78, 88], 17, scale, {
    bg: ['#f1f1f1', '', ''],
    align: ['left', 'left', 'right']
  });

  var summaryTitleY = qTitleY + 22 + qRows.length * 17 + 4;
  drawSectionTitle(exportCtx, '汇总统计量', 30, summaryTitleY, 200, scale);
  var s = DATA.stats;
  var summaryRows = [
    ['均值', fmt(s.mean, 2)], ['标准差', fmt(s.stdDev, 2)], ['均值标准误差', fmt(s.stdErr, 2)],
    ['均值 95% 上限', fmt(s.ci95Upper, 2)], ['均值 95% 下限', fmt(s.ci95Lower, 2)], ['数目', String(s.count)]
  ];
  drawTableToCanvas(exportCtx, summaryRows, 34, summaryTitleY + 22, [112, 94], 17, scale, {
    bg: ['#ededed', ''],
    align: ['left', 'right']
  });
  return exportCanvas;
}

function buildTables() {
  var q = document.getElementById('quantileTable');
  q.innerHTML = '';
  for (var i = 0; i < DATA.quantiles.length; i++) {
    var row = DATA.quantiles[i];
    var pct = document.createElement('div'); pct.className = 'pct'; pct.textContent = row.pct;
    var value = document.createElement('div'); value.className = 'value'; value.textContent = fmt(row.value, 2);
    var label = document.createElement('div'); label.className = 'label'; label.textContent = row.label || '';
    q.append(pct, label, value);
  }
  var s = DATA.stats;
  var rows = [
    ['均值', s.mean], ['标准差', s.stdDev], ['均值标准误差', s.stdErr],
    ['均值 95% 上限', s.ci95Upper], ['均值 95% 下限', s.ci95Lower], ['数目', s.count]
  ];
  var summary = document.getElementById('summaryTable');
  summary.innerHTML = '';
  for (var ri = 0; ri < rows.length; ri++) {
    var name = rows[ri][0];
    var val = rows[ri][1];
    var n = document.createElement('div'); n.className = 'name'; n.textContent = name;
    var v = document.createElement('div'); v.className = 'val'; v.textContent = name === '数目' ? String(val) : fmt(val, 2);
    summary.append(n, v);
  }
  var abnormalText = Object.keys(DATA.abnormal).map(function (k) { return k + ':' + DATA.abnormal[k]; }).join('，') || '无';
  var groups = Object.keys(DATA.cycleGroups).map(function (k) { return k + '次分容 ' + DATA.cycleGroups[k] + '块'; }).join('，') || '无';
  document.getElementById('meta').textContent = '批次：' + DATA.batchId + '｜样本：' + s.count + '｜分容次数：' + groups + '｜剔除异常：' + abnormalText + '｜生成：' + DATA.generatedAt;
}

function currentGap() {
  return Math.max(0, Math.min(70, Number(gapNumber.value || gapRange.value) || 0));
}

function syncAxisInputsFromAuto() {
  var axis = getAutoAxis(DATA.values);
  yMinInput.value = fmt(axis.min, 2);
  yMaxInput.value = fmt(axis.max, 2);
  yStepInput.value = fmt(axis.step, 2);
}

function setAxisInputsEnabled(enabled) {
  yMinInput.disabled = !enabled;
  yMaxInput.disabled = !enabled;
  yStepInput.disabled = !enabled;
}

function refreshChart() {
  draw(currentGap());
}

function syncGap(value) {
  var v = Math.max(0, Math.min(70, Number(value) || 0));
  gapRange.value = v; gapNumber.value = v;
  draw(v);
}

function resetAxisSettings() {
  autoY.checked = true;
  syncAxisInputsFromAuto();
  setAxisInputsEnabled(false);
  refreshChart();
}

gapRange.addEventListener('input', function (e) { syncGap(e.target.value); });
gapNumber.addEventListener('input', function (e) { syncGap(e.target.value); });
autoY.addEventListener('change', function () {
  setAxisInputsEnabled(!autoY.checked);
  if (autoY.checked) syncAxisInputsFromAuto();
  refreshChart();
});
yMinInput.addEventListener('input', refreshChart);
yMaxInput.addEventListener('input', refreshChart);
yStepInput.addEventListener('input', refreshChart);
resetAxisBtn.addEventListener('click', resetAxisSettings);
[distributionTitle, capacityTitle].forEach(function (titleEl) {
  titleEl.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') { e.preventDefault(); titleEl.blur(); }
  });
  titleEl.addEventListener('paste', function (e) {
    e.preventDefault();
    var text = (e.clipboardData || window.clipboardData).getData('text/plain');
    document.execCommand('insertText', false, text.replace(/[\r\n]+/g, ' '));
  });
  titleEl.addEventListener('blur', function () {
    if (!titleEl.textContent.trim()) titleEl.textContent = titleEl.id === 'distributionTitle' ? '分布' : '容量';
  });
});

exportBtn.addEventListener('click', function () {
  statusEl.textContent = '正在导出报告区域图片...';
  var exportCanvas = buildReportExportCanvas();
  exportCanvas.toBlob(function (blob) {
    if (!blob) { statusEl.textContent = '导出失败：浏览器未生成图片'; return; }
    var url = URL.createObjectURL(blob);
    var link = document.createElement('a');
    link.href = url;
    var safeName = String(DATA.batchId || 'capacity_distribution_report');
    var badChars = ['\\', '/', ':', '*', '?', '"', '<', '>', '|'];
    for (var ci = 0; ci < badChars.length; ci++) safeName = safeName.split(badChars[ci]).join('_');
    link.download = safeName + '.png';
    link.style.display = 'none';
    document.body.appendChild(link);
    link.click();
    setTimeout(function () {
      URL.revokeObjectURL(url);
      link.remove();
      statusEl.textContent = '报告区域图片已导出，临时下载对象已清理';
    }, 300);
  }, 'image/png', 1.0);
});

buildTables();
syncAxisInputsFromAuto();
setAxisInputsEnabled(false);
syncGap(8);
</script>
</body>
</html>
"""


def render_distribution_html(
    result: AnalysisResult,
    output_path: str,
    records: List[CapacityRecord] | None = None,
) -> str:
    """生成自包含 HTML 报告并返回输出路径。

    records 可传入与 result.stats 同口径的过滤后记录；不传则使用 result.records 全量。
    """
    data_records = records if records is not None else result.records
    values = [float(r.capacity_mah) for r in data_records if r.capacity_mah > 0]
    if not values:
        logger.warning("没有有效数据，跳过 HTML 报告生成")
        return ""

    payload = _build_payload(result, data_records)
    payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    safe_title = html.escape(f"分容分布报告 - {result.batch_id}")

    doc = _HTML_TEMPLATE.replace("{title}", safe_title).replace("{payload_json}", payload_json)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(doc)
    logger.info(f"HTML 分布报告已生成: {output_path}")
    return output_path
