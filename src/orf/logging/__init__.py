"""ORF 日志系统 — 基于 structlog 的结构化 JSON 日志。

匹配 OPP/OL 的日志惯例：标准 JSON 字段（timestamp、level、module、
request_id、event）+ env var ``OMNI_LOG_FORMAT=json`` 切换。
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

import structlog

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True, parents=True)

LOG_FILE_PATTERN = "orf_{date}.log"
MAX_BYTES = 10 * 1024 * 1024
BACKUP_COUNT = 5

_loggers: dict[str, Any] = {}


def _uppercase_level(_logger: Any, _method_name: str, event_dict: dict) -> dict:
    if "level" in event_dict:
        event_dict["level"] = event_dict["level"].upper()
    return event_dict


def _add_module_field(_logger: Any, _method_name: str, event_dict: dict) -> dict:
    name = event_dict.pop("logger", None)
    if name is not None and "module" not in event_dict:
        event_dict["module"] = name
    return event_dict


def _is_json_mode() -> bool:
    return os.environ.get("OMNI_LOG_FORMAT", "console").lower() == "json"


def _build_processors() -> list:
    """Pre-processors used by both structlog and the ProcessorFormatter."""
    return [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.ExtraAdder(),
        structlog.stdlib.add_logger_name,
        _add_module_field,
        structlog.stdlib.add_log_level,
        _uppercase_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]


def _build_final_renderer() -> Any:
    """Return the final renderer (JSON in json mode, ConsoleRenderer otherwise)."""
    if _is_json_mode():
        return structlog.processors.JSONRenderer(sort_keys=True)
    return structlog.dev.ConsoleRenderer(colors=False)


def _build_formatter(json_mode: bool) -> logging.Formatter:
    """Back-compat shim: returns a stdlib formatter for legacy stdlib-only tests.

    New code should use the structlog primary path via ``setup_logger()``
    which wires the ``ProcessorFormatter`` onto the file handler.
    """
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
        datefmt='%Y-%m-%d %H:%M:%S',
    )


def _get_stdlib_handler_formatter(json_mode: bool) -> logging.Formatter:
    """Return a ProcessorFormatter that produces the same JSON/text as structlog."""
    if not json_mode:
        return logging.Formatter(
            '[%(asctime)s.%(msecs)03d] [%(levelname)s] [%(name)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
        )
    return structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=_build_processors(),
        processor=_build_final_renderer(),
    )


class _NamedPrintLogger(structlog.PrintLogger):
    def __init__(self, file=None) -> None:
        super().__init__(file)
        self.name = "unnamed"


class _NamedPrintLoggerFactory:
    """Print logger factory that stores the logger name so ``add_logger_name`` works."""

    def __init__(self, file=None) -> None:
        self.file = file

    def __call__(self, *args: Any) -> _NamedPrintLogger:
        logger = _NamedPrintLogger(self.file)
        if args:
            first = args[0]
            if isinstance(first, str):
                logger.name = first
            else:
                logger.name = getattr(first, "name", "unnamed")
        return logger


def _ensure_structlog_configured(level: int, file: Any = None) -> None:
    structlog.configure(
        processors=_build_processors() + [_build_final_renderer()],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=_NamedPrintLoggerFactory(file=file),
        cache_logger_on_first_use=True,
    )


def setup_logger(name: str = "orf", level: str = "INFO") -> logging.Logger:
    if name in _loggers:
        return _loggers[name]

    level = os.environ.get("ORF_LOG_LEVEL", level).upper()

    json_mode = _is_json_mode()
    numeric_level = getattr(logging, level, logging.INFO)

    _ensure_structlog_configured(numeric_level, file=sys.stderr)

    logger = logging.getLogger(name)
    logger.setLevel(numeric_level)

    if not logger.handlers:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(numeric_level)
        if json_mode:
            console_handler.setFormatter(_get_stdlib_handler_formatter(json_mode=True))
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
        file_handler.setFormatter(_get_stdlib_handler_formatter(json_mode=json_mode))
        logger.addHandler(file_handler)

    _loggers[name] = logger
    return logger


def get_audit_logger(name: str = "orf.audit") -> logging.Logger:
    """Get audit logger with correlation_id, agent_id, request_id fields.

    Backed by structlog: the audit log emits the same JSON shape as the
    main logger, with audit-specific fields bound via the structlog
    contextvars (``correlation_id``, ``agent_id``, ``request_id``).
    """
    logger = logging.getLogger(name)
    if name not in _loggers:
        audit_file = LOG_DIR / f"audit_{datetime.now().strftime('%Y%m%d')}.log"
        handler = RotatingFileHandler(
            audit_file, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8",
        )
        handler.setLevel(logging.INFO)
        handler.setFormatter(_get_stdlib_handler_formatter(json_mode=_is_json_mode()))
        logger.addHandler(handler)
        _loggers[name] = logger
    return logger


def log_request_id(request_id: str, context: str = "") -> None:
    """Log a request_id entry to the audit log (B2).

    Writes a single audit line with the request_id and optional
    context message. Used by ORF entry points to trace a
    request from OPP -> OL -> ORF.
    """
    logger = get_audit_logger()
    if context:
        logger.info(f"request_id={request_id} {context}", extra={"request_id": request_id})
    else:
        logger.info(f"request_id={request_id}", extra={"request_id": request_id})


def get_logger(name: str = "orf") -> logging.Logger:
    """Get a stdlib logger for the given module path (back-compat API)."""
    if name in _loggers:
        return _loggers[name]
    return setup_logger(name)


def bind_request_id(request_id: str) -> None:
    """Bind a request_id to the current context (auto-emitted in JSON output)."""
    structlog.contextvars.bind_contextvars(request_id=request_id)


def clear_request_id() -> None:
    """Clear the bound request_id from the current context."""
    structlog.contextvars.unbind_contextvars("request_id")
