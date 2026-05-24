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
_loggers: dict[str, logging.Logger] = {}


class AuditLogRecord(logging.LogRecord):
    """Custom log record with audit fields."""
    correlation_id = 'N/A'
    agent_id = 'N/A'


# Register the custom record factory
logging.setLogRecordFactory(AuditLogRecord)


def setup_logger(name: str = "orf", level: str = "INFO") -> logging.Logger:
    """配置 ORF 日志器"""
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    if logger.handlers:
        return logger

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '[%(levelname)s] %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

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


def get_audit_logger(name: str = "orf.audit") -> logging.Logger:
    """Get audit logger with correlation_id, agent_id fields."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    audit_file = LOG_DIR / f"audit_{datetime.now().strftime('%Y%m%d')}.log"
    handler = RotatingFileHandler(audit_file, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8")
    handler.setLevel(logging.INFO)

    formatter = logging.Formatter(
        '[%(asctime)s.%(msecs)03d] [%(levelname)s] [%(name)s] [corr:%(correlation_id)s] [agent:%(agent_id)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

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