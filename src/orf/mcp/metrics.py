"""Per-module Prometheus metrics for the ORF MCP server.

Phase 4.5: module-prefixed metrics (orf_*) emitted to a local
Prometheus text file under ``OMNI_METRICS_DIR`` (default
``/tmp/omni-metrics/orf.prom``). The shared ``omni_metrics`` package
(``omni_mcp_tool_calls_total`` etc.) is used for the suite-wide
aggregator; this module adds the ORF-specific counters and
histograms that the production-readiness plan requires.

Wired from ``server._call_tool``. All write paths are best-effort —
metrics emission must NEVER raise into the request path (would
break the JSON-RPC stream).
"""
from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Histogram,
    write_to_textfile,
)

_logger = logging.getLogger(__name__)

# Per-module registry — kept isolated from the global ``REGISTRY`` that
# ``omni_metrics`` uses, so the two metric families don't collide when
# both run in the same process (tests, docs/examples).
REGISTRY = CollectorRegistry()

# Histogram buckets required by the production-readiness plan.
_DURATION_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10)

ORF_REQUESTS_TOTAL = Counter(
    "orf_requests_total",
    "Total ORF MCP requests, by tool_name and status.",
    ["tool_name", "status"],
    registry=REGISTRY,
)

ORF_REQUEST_DURATION_SECONDS = Histogram(
    "orf_request_duration_seconds",
    "ORF MCP request duration in seconds, by tool_name.",
    ["tool_name"],
    buckets=_DURATION_BUCKETS,
    registry=REGISTRY,
)

ORF_BACKFILLS_TOTAL = Counter(
    "orf_backfills_total",
    "Total ORF backfill operations, by target_format and status.",
    ["target_format", "status"],
    registry=REGISTRY,
)

# Status label values — stable strings; do not rename.
STATUS_SUCCESS = "success"
STATUS_ERROR = "error"
STATUS_RATE_LIMITED = "rate_limited"
STATUS_AUTH_FAILED = "auth_failed"


def _metrics_dir() -> Path:
    return Path(os.environ.get("OMNI_METRICS_DIR", "/tmp/omni-metrics"))


_write_lock = threading.Lock()


def _emit() -> None:
    try:
        outdir = _metrics_dir()
        outdir.mkdir(parents=True, exist_ok=True)
        with _write_lock:
            write_to_textfile(str(outdir / "orf.prom"), REGISTRY)
    except Exception:
        _logger.debug("Failed to write Prometheus metrics", exc_info=True)


def record_request(
    tool_name: str,
    status: str,
    duration_seconds: float,
) -> None:
    try:
        ORF_REQUESTS_TOTAL.labels(tool_name=tool_name, status=status).inc()
        ORF_REQUEST_DURATION_SECONDS.labels(tool_name=tool_name).observe(
            max(0.0, float(duration_seconds))
        )
        _emit()
    except Exception:
        _logger.debug("Failed to write Prometheus metrics", exc_info=True)


def record_backfill(target_format: str, status: str) -> None:
    """Record a single ORF backfill. ``target_format`` is the output
    format (e.g. ``docx``, ``pdf``, ``html``).
    """
    try:
        ORF_BACKFILLS_TOTAL.labels(
            target_format=(target_format or "unknown").lower(),
            status=status,
        ).inc()
        _emit()
    except Exception:
        _logger.debug("Failed to write Prometheus metrics", exc_info=True)


def record_request_from_arguments(
    tool_name: str,
    arguments: dict[str, Any] | None,
    status: str,
    duration_seconds: float,
) -> None:
    """Convenience: record a request and, for backfill tools, also
    bump ``ORF_BACKFILLS_TOTAL`` by target_format.
    """
    record_request(tool_name, status, duration_seconds)
    args = arguments or {}
    if tool_name == "apply_md":
        record_backfill(str(args.get("target_format", "unknown")), status)
    elif tool_name == "apply_xliff":
        record_backfill(str(args.get("format", "unknown")), status)
    elif tool_name == "batch_convert":
        record_backfill(str(args.get("target_format", "unknown")), status)


def time_block() -> "_ORFBlockTimer":
    return _ORFBlockTimer()


class _ORFBlockTimer:
    __slots__ = ("_t0",)

    def __init__(self) -> None:
        self._t0 = time.monotonic()

    def seconds(self) -> float:
        return max(0.0, time.monotonic() - self._t0)


__all__ = [
    "REGISTRY",
    "ORF_REQUESTS_TOTAL",
    "ORF_REQUEST_DURATION_SECONDS",
    "ORF_BACKFILLS_TOTAL",
    "STATUS_SUCCESS",
    "STATUS_ERROR",
    "STATUS_RATE_LIMITED",
    "STATUS_AUTH_FAILED",
    "record_request",
    "record_backfill",
    "record_request_from_arguments",
    "time_block",
]
