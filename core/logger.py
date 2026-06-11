# -*- coding: utf-8 -*-
"""
日志系统模块
支持分级日志、文件输出、统一日志合并
日志保存在项目根目录 logs/ 下，按日期轮转，保留 5 天备份
统一日志文件：logs/unified.log（JSON Lines 格式，含插件名/时间戳/级别/请求ID/线程ID）
"""

import logging
import os
from logging.handlers import TimedRotatingFileHandler
from typing import Optional

# 备份保留天数
LOG_BACKUP_DAYS = 5


class ToolkitLogger:
    """Toolkit 日志管理器（单例）"""

    _instance: Optional["ToolkitLogger"] = None
    _loggers: dict = {}

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, log_dir: str = "", log_level: str = "INFO"):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._log_dir = log_dir or os.path.join(
            os.path.expanduser("~"), ".toolkit", "logs"
        )
        self._default_level = getattr(logging, log_level.upper(), logging.INFO)
        os.makedirs(self._log_dir, exist_ok=True)

        # 初始化统一日志处理器（只初始化一次）
        self._unified_handler = None
        self._setup_unified_handler()

    def _setup_unified_handler(self):
        """初始化统一日志处理器（延迟导入避免循环依赖）"""
        try:
            from core.unified_logger import UnifiedLogHandler
            self._unified_handler = UnifiedLogHandler(
                self._log_dir, backup_count=LOG_BACKUP_DAYS
            )
        except Exception as e:
            # 统一日志初始化失败不应影响主程序
            print(f"[WARN] 统一日志初始化失败: {e}")

    def get_logger(self, name: str, level: Optional[str] = None) -> logging.Logger:
        """获取命名 logger，支持独立日志级别，自动附加统一日志处理器"""
        if name in self._loggers:
            return self._loggers[name]

        logger = logging.getLogger(name)
        effective_level = (
            getattr(logging, level.upper(), self._default_level)
            if level
            else self._default_level
        )
        logger.setLevel(effective_level)

        if not logger.handlers:
            # -------- 控制台 handler --------
            console_handler = logging.StreamHandler()
            console_handler.setLevel(effective_level)
            console_fmt = logging.Formatter(
                "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
                datefmt="%H:%M:%S",
            )
            console_handler.setFormatter(console_fmt)
            logger.addHandler(console_handler)

            # -------- 独立文件 handler（按日期轮转）--------
            log_file = os.path.join(self._log_dir, f"{name}.log")
            file_handler = TimedRotatingFileHandler(
                log_file,
                when="midnight",
                backupCount=LOG_BACKUP_DAYS,
                encoding="utf-8",
            )
            file_handler.suffix = "%Y-%m-%d"
            file_handler.setLevel(logging.DEBUG)
            file_fmt = logging.Formatter(
                "[%(asctime)s] [%(name)s] [%(levelname)s] "
                "[%(filename)s:%(lineno)d] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            file_handler.setFormatter(file_fmt)
            logger.addHandler(file_handler)

            # -------- 统一日志 handler（合并所有插件日志）--------
            if self._unified_handler:
                logger.addHandler(self._unified_handler)

        self._loggers[name] = logger
        return logger

    def set_level(self, name: str, level: str):
        """运行时调整某 logger 的级别（仅影响控制台输出）"""
        if name not in self._loggers:
            return
        lvl = getattr(logging, level.upper(), logging.INFO)
        self._loggers[name].setLevel(lvl)
        for handler in self._loggers[name].handlers:
            if not isinstance(handler, TimedRotatingFileHandler):
                handler.setLevel(lvl)

    def set_all_level(self, level: str):
        """运行时调整所有 logger 的级别"""
        for name in self._loggers:
            self.set_level(name, level)

    def get_unified_log_path(self) -> str:
        """获取统一日志文件路径"""
        if self._unified_handler:
            return self._unified_handler.get_log_path()
        return os.path.join(self._log_dir, "unified.log")


# 便捷函数
def get_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """获取 logger 实例（自动使用 config.log_dir）"""
    from config import config
    return ToolkitLogger(config.log_dir, config.log_level).get_logger(name, level)


def get_unified_log_path() -> str:
    """获取统一日志文件路径"""
    from config import config
    return ToolkitLogger(config.log_dir, config.log_level).get_unified_log_path()
