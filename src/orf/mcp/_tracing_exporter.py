"""Shared JSONL file span exporter for the ORF MCP tracing module.

Tiny custom exporter — writes one line per span to a file.  Used
by ``orf.mcp.tracing``.  Kept in a separate module so the SDK
import doesn't run when tracing is disabled.
"""
from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult


_logger = logging.getLogger(__name__)


class _JsonlFileSpanExporter(SpanExporter):
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()

    def export(self, spans: list[ReadableSpan]) -> SpanExportResult:  # type: ignore[override]
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                with self._path.open("a", encoding="utf-8") as fh:
                    for span in spans:
                        try:
                            ctx = span.get_span_context()
                            if ctx is None:
                                continue
                            parent_id = (
                                format(span.parent.span_id, "016x")
                                if span.parent is not None
                                else None
                            )
                            start_ns = span.start_time or 0
                            end_ns = span.end_time or 0
                            payload = {
                                "name": span.name,
                                "trace_id": format(ctx.trace_id, "032x"),
                                "span_id": format(ctx.span_id, "016x"),
                                "parent_span_id": parent_id,
                                "start_time_ns": start_ns,
                                "end_time_ns": end_ns,
                                "duration_ms": max(
                                    0.0,
                                    (end_ns - start_ns) / 1_000_000.0,
                                ),
                                "status": {
                                    "status_code": span.status.status_code.name
                                    if span.status is not None
                                    else "UNSET",
                                    "description": span.status.description
                                    if span.status is not None
                                    else "",
                                },
                                "attributes": dict(span.attributes or {}),
                                "resource": {
                                    k: v for k, v in (span.resource.attributes.items()
                                                      if span.resource is not None
                                                      else [])
                                },
                            }
                            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
                        except Exception:
                            _logger.debug("Failed to serialize span, skipping", exc_info=True)
                            continue
        except Exception:
            _logger.debug("Failed to export spans", exc_info=True)
            return SpanExportResult.FAILURE
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        return None
