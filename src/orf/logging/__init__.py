"""ORF日志系统

基于标准 logging 模块，追踪转换全生命周期。
匹配 OPP/OL 的日志惯例。
"""

import logging
import os
import sys
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True, parents=True)

LOG_FILE_PATTERN = "orf_{date}.log"
MAX_BYTES = 10 * 1024 * 1024
BACKUP_COUNT = 5

_loggers: dict[str, logging.Logger] = {}


class AuditLogRecord(logging.LogRecord):
    """Custom log record with audit fields."""
    correlation_id = 'N/A'
    agent_id = 'N/A'
    request_id = 'N/A'


logging.setLogRecordFactory(AuditLogRecord)


def _is_json_mode() -> bool:
    return os.environ.get("OMNI_LOG_FORMAT", "console").lower() == "json"


def _build_formatter(json_mode: bool) -> logging.Formatter:
    """Return text or JSON formatter based on mode."""
    if json_mode:
        from pythonjsonlogger.json import JsonFormatter
        return JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            rename_fields={
                "asctime": "timestamp",
                "levelname": "level",
                "name": "module",
            },
        )
    return logging.Formatter(
        '[%(asctime)s.%(msecs)03d] [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def setup_logger(name: str = "orf", level: str = "INFO") -> logging.Logger:
    if name in _loggers:
        return _loggers[name]

    level = os.environ.get("ORF_LOG_LEVEL", level).upper()

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    if logger.handlers:
        return logger

    numeric_level = getattr(logging, level, logging.INFO)
    json_mode = _is_json_mode()

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(numeric_level)
    if json_mode:
        console_handler.setFormatter(_build_formatter(json_mode=True))
    else:
        console_handler.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
    logger.addHandler(console_handler)

    log_file = LOG_DIR / LOG_FILE_PATTERN.format(date=datetime.now().strftime("%Y%m%d"))
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(_build_formatter(json_mode=json_mode))
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
        '[%(asctime)s.%(msecs)03d] [%(levelname)s] [%(name)s] [corr:%(correlation_id)s] [agent:%(agent_id)s] [req:%(request_id)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


def log_request_id(request_id: str, context: str = "") -> None:
    """Log a request_id entry to the audit log (B2).

    Writes a single audit line with the request_id and optional
    context message. Used by ORF entry points to trace a
    request from OPP -> OL -> ORF.
    """
    logger = get_audit_logger()
    msg = f"request_id={request_id}"
    if context:
        msg += f" {context}"
    logger.info(msg, extra={"request_id": request_id})


def get_logger(name: str = "orf") -> logging.Logger:
    if name not in _loggers:
        return setup_logger(name)
    return _loggers[name]