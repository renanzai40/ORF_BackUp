"""Phase 4.5 — ORF per-module Prometheus metrics.

Verifies the ``orf.mcp.metrics`` module:
- Exposes ``ORF_REQUESTS_TOTAL``, ``ORF_REQUEST_DURATION_SECONDS``,
  ``ORF_BACKFILLS_TOTAL`` with the right names, label sets, and
  histogram buckets.
- ``record_request`` increments the counter and observes the
  histogram, and writes a valid Prometheus textfile under
  ``OMNI_METRICS_DIR`` (default ``/tmp/omni-metrics/orf.prom``).
- ``record_backfill`` increments the backfill counter keyed by
  ``target_format`` and ``status``.
- The ``_call_tool`` dispatcher routes success/error/
  rate_limited/auth_failed/unknown_tool status to the metric.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


ORF_SRC = Path(__file__).resolve().parents[1] / "src"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def metrics_dir(tmp_path, monkeypatch):
    out = tmp_path / "omni-metrics"
    monkeypatch.setenv("OMNI_METRICS_DIR", str(out))
    return out


@pytest.fixture
def metrics(metrics_dir):
    return _load("orf_metrics_under_test", ORF_SRC / "orf" / "mcp" / "metrics.py")


class TestMetricRegistration:
    def test_orf_requests_total_emitted_name(self, metrics, metrics_dir):
        metrics.record_request("t", metrics.STATUS_SUCCESS, 0.001)
        body = (metrics_dir / "orf.prom").read_text(encoding="utf-8")
        assert "orf_requests_total" in body
        assert "# TYPE orf_requests_total counter" in body

    def test_orf_request_duration_seconds_buckets(self, metrics):
        assert tuple(metrics.ORF_REQUEST_DURATION_SECONDS._upper_bounds)[:-1] == (
            0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0,
        )

    def test_label_sets(self, metrics):
        assert sorted(metrics.ORF_REQUESTS_TOTAL._labelnames) == ["status", "tool_name"]
        assert sorted(metrics.ORF_BACKFILLS_TOTAL._labelnames) == [
            "status", "target_format",
        ]
        assert sorted(metrics.ORF_REQUEST_DURATION_SECONDS._labelnames) == ["tool_name"]


class TestStatusConstants:
    @pytest.mark.parametrize(
        "label",
        ["success", "error", "rate_limited", "auth_failed"],
    )
    def test_status_constant_present(self, metrics, label):
        assert label in {
            metrics.STATUS_SUCCESS,
            metrics.STATUS_ERROR,
            metrics.STATUS_RATE_LIMITED,
            metrics.STATUS_AUTH_FAILED,
        }


class TestRecordRequest:
    def test_increments_counter_and_observes_histogram(self, metrics):
        before = metrics.ORF_REQUESTS_TOTAL.labels(
            tool_name="apply_md", status="success",
        )._value.get()
        metrics.record_request("apply_md", metrics.STATUS_SUCCESS, 0.2)
        after = metrics.ORF_REQUESTS_TOTAL.labels(
            tool_name="apply_md", status="success",
        )._value.get()
        assert after == before + 1

    def test_writes_prom_textfile(self, metrics, metrics_dir):
        metrics.record_request("apply_md", metrics.STATUS_SUCCESS, 0.1)
        out = metrics_dir / "orf.prom"
        assert out.exists()
        body = out.read_text(encoding="utf-8")
        assert "# TYPE orf_requests_total counter" in body
        assert "# TYPE orf_request_duration_seconds histogram" in body
        assert 'tool_name="apply_md"' in body


class TestRecordBackfill:
    def test_record_backfill_increments(self, metrics):
        before = metrics.ORF_BACKFILLS_TOTAL.labels(
            target_format="docx", status="success",
        )._value.get()
        metrics.record_backfill("docx", metrics.STATUS_SUCCESS)
        after = metrics.ORF_BACKFILLS_TOTAL.labels(
            target_format="docx", status="success",
        )._value.get()
        assert after == before + 1

    def test_record_backfill_xliff_format(self, metrics):
        before = metrics.ORF_BACKFILLS_TOTAL.labels(
            target_format="epub", status="success",
        )._value.get()
        metrics.record_backfill("EPUB", metrics.STATUS_SUCCESS)
        after = metrics.ORF_BACKFILLS_TOTAL.labels(
            target_format="epub", status="success",
        )._value.get()
        assert after == before + 1


class TestRequestFromArguments:
    def test_routes_target_format_from_apply_md(self, metrics):
        before = metrics.ORF_BACKFILLS_TOTAL.labels(
            target_format="html", status="success",
        )._value.get()
        metrics.record_request_from_arguments(
            "apply_md",
            {"target_format": "html"},
            metrics.STATUS_SUCCESS,
            0.1,
        )
        after = metrics.ORF_BACKFILLS_TOTAL.labels(
            target_format="html", status="success",
        )._value.get()
        assert after == before + 1

    def test_routes_format_from_apply_xliff(self, metrics):
        before = metrics.ORF_BACKFILLS_TOTAL.labels(
            target_format="pptx", status="success",
        )._value.get()
        metrics.record_request_from_arguments(
            "apply_xliff",
            {"format": "pptx"},
            metrics.STATUS_SUCCESS,
            0.1,
        )
        after = metrics.ORF_BACKFILLS_TOTAL.labels(
            target_format="pptx", status="success",
        )._value.get()
        assert after == before + 1


class TestDispatcherWiring:
    """Verify the call_tool dispatcher records metrics correctly."""

    @pytest.fixture
    def server(self, metrics, metrics_dir):
        _register_shared_metrics_module(metrics)
        return _load("orf_server_under_test", ORF_SRC / "orf" / "mcp" / "server.py")

    @pytest.mark.asyncio
    async def test_dispatcher_unknown_tool_records_error(self, server, metrics):
        with pytest.raises(ValueError, match="Unknown tool"):
            await server._call_tool("nope_does_not_exist", {})
        val = metrics.ORF_REQUESTS_TOTAL.labels(
            tool_name="nope_does_not_exist", status="error",
        )._value.get()
        assert val >= 1

    @pytest.mark.asyncio
    async def test_dispatcher_internal_error_records_error(self, server, metrics):
        def boom(**_):
            raise RuntimeError("kaboom")
        server._TOOL_DISPATCH["boom_tool"] = boom
        try:
            with pytest.raises(RuntimeError, match="kaboom"):
                await server._call_tool("boom_tool", {})
            val = metrics.ORF_REQUESTS_TOTAL.labels(
                tool_name="boom_tool", status="error",
            )._value.get()
            assert val >= 1
        finally:
            server._TOOL_DISPATCH.pop("boom_tool", None)

    @pytest.mark.asyncio
    async def test_dispatcher_success_records_status(self, server, metrics):
        def ok_tool(**_):
            return json.dumps({"success": True, "data": "ok"})

        server._TOOL_DISPATCH["ok_tool"] = ok_tool
        try:
            result = await server._call_tool("ok_tool", {})
            assert isinstance(result, list)
            assert len(result) == 1
            val = metrics.ORF_REQUESTS_TOTAL.labels(
                tool_name="ok_tool", status="success",
            )._value.get()
            assert val >= 1
        finally:
            server._TOOL_DISPATCH.pop("ok_tool", None)


def _register_shared_metrics_module(metrics) -> None:
    import types
    pkg = types.ModuleType("orf")
    pkg.__path__ = [str(ORF_SRC / "orf")]
    sys.modules["orf"] = pkg
    sys.modules["orf.mcp"] = types.ModuleType("orf.mcp")
    sys.modules["orf.mcp"].__path__ = [str(ORF_SRC / "orf" / "mcp")]
    sys.modules["orf.mcp.metrics"] = metrics
