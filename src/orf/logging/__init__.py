"""ORF日志系统

基于标准 logging 模块，追踪转换全生命周期。
匹配 OPP/OL 的日志惯例。
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler

# 日志目录
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True, parents=True)

# 日志文件命名
LOG_FILE_PATTERN = "orf_{date}.log"
MAX_BYTES = 10 * 1024 * 1024  # 10MB
BACKUP_COUNT = 5

# 全局 logger 缓存
_loggers = {}


def setup_logger(name: str = "orf", level: str = "INFO") -> logging.Logger:
    """配置 ORF 日志器

    Args:
        name: 日志器名称，用于区分不同模块
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR)

    Returns:
        配置好的 Logger 实例
    """
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    # 控制台 handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '[%(levelname)s] %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # 文件 handler（DEBUG 级别，完整格式）
    log_file = LOG_DIR / LOG_FILE_PATTERN.format(date=datetime.now().strftime("%Y%m%d"))
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '[%(asctime)s.%(msecs)03d] [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    _loggers[name] = logger
    return logger


def get_logger(name: str = "orf") -> logging.Logger:
    """获取 logger 实例

    如果 logger 未配置，先进行默认配置。

    Args:
        name: 模块名称 (如 "cli", "channel.md2docx")

    Returns:
        Logger 实例
    """
    if name not in _loggers:
        return setup_logger(name)
    return _loggers[name]