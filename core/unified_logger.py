# -*- coding: utf-8 -*-
"""
统一日志管理模块

功能：
1. 将多个插件的日志合并输出到单个日志文件
2. 结构化 JSON 格式，包含插件名称、时间戳、日志级别、消息、线程ID、请求ID
3. 支持按时间戳排序、按插件分组显示
4. 线程安全，支持并发写入

统一日志文件路径：logs/unified.log（按日期轮转）
"""

import json
import logging
import os
import threading
import uuid
from contextvars import ContextVar
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from typing import Optional, List, Dict, Any

# 请求ID上下文变量（支持异步和线程隔离）
_request_id_var: ContextVar[str] = ContextVar("request_id", default="")


class RequestContext:
    """请求上下文管理器，用于关联同一业务流程的日志"""

    @staticmethod
    def set_request_id(req_id: str) -> None:
        """设置当前上下文的请求ID"""
        _request_id_var.set(req_id)

    @staticmethod
    def get_request_id() -> str:
        """获取当前上下文的请求ID，未设置则返回空字符串"""
        return _request_id_var.get()

    @staticmethod
    def generate_request_id() -> str:
        """生成新的唯一请求ID"""
        return f"req-{uuid.uuid4().hex[:12]}"

    @staticmethod
    def clear() -> None:
        """清除当前请求ID"""
        _request_id_var.set("")


class UnifiedLogFormatter(logging.Formatter):
    """
    统一日志格式化器
    输出结构化 JSON Lines 格式，每行一个完整的 JSON 对象
    """

    def __init__(self, fmt: Optional[str] = None, datefmt: Optional[str] = None):
        super().__init__(fmt, datefmt)

    def format(self, record: logging.LogRecord) -> str:
        """将日志记录格式化为 JSON 字符串"""
        # 使用 datetime 直接格式化，避免 time.strftime 不支持 %f 的问题
        from datetime import datetime
        ts = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log_entry: Dict[str, Any] = {
            "timestamp": ts,
            "plugin": record.name,
            "level": record.levelname,
            "message": record.getMessage(),
            "thread_id": f"{record.threadName}-{record.thread}",
            "request_id": RequestContext.get_request_id(),
            "source_file": getattr(record, "filename", ""),
            "source_line": getattr(record, "lineno", 0),
        }
        # 如果有异常信息，追加到消息中
        if record.exc_info and record.exc_info[0] is not None:
            import traceback
            exc_text = traceback.format_exception(*record.exc_info)
            log_entry["exception"] = "".join(exc_text)

        return json.dumps(log_entry, ensure_ascii=False)


class UnifiedLogHandler(logging.Handler):
    """
    统一日志处理器
    将所有插件的日志合并写入单个文件，使用线程锁保证并发安全
    """

    _lock = threading.Lock()
    _initialized = False
    _handler_instance: Optional[TimedRotatingFileHandler] = None
    _log_path: str = ""

    def __init__(self, log_dir: str, backup_count: int = 5):
        super().__init__()
        self._log_dir = log_dir
        self._backup_count = backup_count
        os.makedirs(self._log_dir, exist_ok=True)
        self._log_path = os.path.join(self._log_dir, "unified.log")
        UnifiedLogHandler._log_path = self._log_path

        # 使用 TimedRotatingFileHandler 按日期轮转
        if not UnifiedLogHandler._initialized:
            with UnifiedLogHandler._lock:
                if not UnifiedLogHandler._initialized:
                    self._setup_handler()
                    UnifiedLogHandler._initialized = True

        self.setLevel(logging.DEBUG)
        self.setFormatter(UnifiedLogFormatter())

    def _setup_handler(self):
        """初始化底层的文件处理器"""
        self._file_handler = TimedRotatingFileHandler(
            self._log_path,
            when="midnight",
            backupCount=self._backup_count,
            encoding="utf-8",
        )
        self._file_handler.suffix = "%Y-%m-%d"
        self._file_handler.setLevel(logging.DEBUG)
        self._file_handler.setFormatter(UnifiedLogFormatter())

    def emit(self, record: logging.LogRecord):
        """线程安全的日志写入"""
        try:
            with UnifiedLogHandler._lock:
                if hasattr(self, "_file_handler"):
                    self._file_handler.emit(record)
        except Exception:
            self.handleError(record)

    def close(self):
        """关闭处理器"""
        if hasattr(self, "_file_handler"):
            self._file_handler.close()
        super().close()

    @classmethod
    def get_log_path(cls) -> str:
        """获取统一日志文件路径"""
        return cls._log_path


# ==================== 日志读取与展示工具 ====================

def parse_unified_log(
    log_path: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    plugin_filter: Optional[str] = None,
    level_filter: Optional[str] = None,
    request_id_filter: Optional[str] = None,
    limit: int = 0,
) -> List[Dict[str, Any]]:
    """
    解析统一日志文件，支持多种过滤条件

    Args:
        log_path: 日志文件路径，默认使用统一日志路径
        start_time: 起始时间过滤 (格式: YYYY-MM-DD HH:MM:SS)
        end_time: 结束时间过滤
        plugin_filter: 插件名称过滤（支持模糊匹配）
        level_filter: 日志级别过滤（如 INFO, ERROR）
        request_id_filter: 请求ID精确匹配
        limit: 返回最大条数，0 表示不限制

    Returns:
        按时间戳升序排序的日志条目列表
    """
    if log_path is None:
        log_path = UnifiedLogHandler.get_log_path()

    if not log_path or not os.path.exists(log_path):
        return []

    results: List[Dict[str, Any]] = []

    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            # 时间过滤
            ts = entry.get("timestamp", "")
            if start_time and ts < start_time:
                continue
            if end_time and ts > end_time:
                continue

            # 插件过滤
            if plugin_filter and plugin_filter.lower() not in entry.get("plugin", "").lower():
                continue

            # 级别过滤
            if level_filter and entry.get("level", "").upper() != level_filter.upper():
                continue

            # 请求ID过滤
            if request_id_filter and entry.get("request_id", "") != request_id_filter:
                continue

            results.append(entry)

            if limit > 0 and len(results) >= limit:
                break

    # 按时间戳升序排序
    results.sort(key=lambda x: x.get("timestamp", ""))
    return results


def format_log_for_display(
    entries: List[Dict[str, Any]],
    group_by_plugin: bool = True,
    show_request_id: bool = True,
) -> str:
    """
    将日志条目格式化为可读的文本，支持按插件分组

    Args:
        entries: 日志条目列表
        group_by_plugin: 是否按插件分组显示
        show_request_id: 是否显示请求ID

    Returns:
        格式化后的日志文本（HTML 片段）
    """
    if not entries:
        return "<i>暂无日志记录</i>"

    # 插件颜色映射
    plugin_colors = {
        "peel_data.extractor": "#3498db",
        "peel_data.pdf_parser": "#9b59b6",
        "peel_data.excel_parser": "#e67e22",
        "peel_data.ui": "#1abc9c",
        "database": "#f39c12",
        "plugin_manager": "#2ecc71",
        "main_window": "#34495e",
    }
    default_color = "#7f8c8d"

    # 级别颜色映射
    level_colors = {
        "DEBUG": "#6a9955",
        "INFO": "#d4d4d4",
        "WARNING": "#ce9178",
        "ERROR": "#f44747",
        "CRITICAL": "#ff0000",
    }

    lines: List[str] = []
    last_plugin = ""

    for entry in entries:
        plugin = entry.get("plugin", "unknown")
        level = entry.get("level", "INFO")
        ts = entry.get("timestamp", "")
        msg = entry.get("message", "")
        req_id = entry.get("request_id", "")
        src_file = entry.get("source_file", "")
        src_line = entry.get("source_line", 0)

        p_color = plugin_colors.get(plugin, default_color)
        l_color = level_colors.get(level, "#d4d4d4")

        # 插件分组分隔线
        if group_by_plugin and plugin != last_plugin and last_plugin:
            lines.append(
                f'<div style="border-top: 1px dashed #555; margin: 6px 0;"></div>'
            )
        last_plugin = plugin

        # 时间戳只保留时分秒（同一天内）
        time_short = ts.split(" ")[-1] if " " in ts else ts
        if "." in time_short:
            time_short = time_short.split(".")[0]

        # 构建请求ID显示
        req_id_html = f'<span style="color:#888;font-size:10px;">[{req_id}]</span> ' if (show_request_id and req_id) else ""

        # 构建来源位置
        source_info = f"{src_file}:{src_line}" if src_file else ""
        source_html = f'<span style="color:#666;font-size:10px;">{source_info}</span>' if source_info else ""

        line = (
            f'<span style="color:#888;">[{time_short}]</span> '
            f'<span style="color:{p_color};font-weight:bold;">[{plugin}]</span> '
            f'<span style="color:{l_color};">{level:8}</span> '
            f'{req_id_html}'
            f'<span>{msg}</span>'
        )
        if source_html:
            line += f' <span style="color:#555;font-size:10px;">({source_html})</span>'

        lines.append(line)

    return "<br>".join(lines)


def get_recent_logs(minutes: int = 30, limit: int = 500) -> List[Dict[str, Any]]:
    """获取最近 N 分钟的日志条目"""
    from datetime import timedelta
    now = datetime.now()
    start = (now - timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
    return parse_unified_log(start_time=start, limit=limit)


def trace_request(request_id: str) -> List[Dict[str, Any]]:
    """通过请求ID追溯完整的业务流程日志"""
    return parse_unified_log(request_id_filter=request_id)


# ==================== 集成到 ToolkitLogger ====================

# 在 logger.py 中通过 setup_unified_logging() 调用
__all__ = [
    "UnifiedLogHandler",
    "UnifiedLogFormatter",
    "RequestContext",
    "parse_unified_log",
    "format_log_for_display",
    "get_recent_logs",
    "trace_request",
]
