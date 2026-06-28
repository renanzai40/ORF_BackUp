"""Tests for the ORF MCP server.py → tools/ package split (Task 3.2).

Verifies that:
1. All 6 tool functions are importable from ``orf.mcp.tools``
2. All 6 tool functions are re-exported from ``orf.mcp.server`` (backward compat)
3. All common helpers are re-exported with their old underscore-prefixed names
4. The MCP server wiring (``_TOOL_DISPATCH``, ``server``, ``_list_tools``,
   ``_call_tool``, ``_orf_classify_status``) is intact in ``server.py``
5. Function signatures of tools are unchanged
6. Common module attributes are accessible
"""

from __future__ import annotations

import inspect
from typing import Any

import pytest

# ─── Test group 1: tools package imports ────────────────────────────


class TestToolsPackageImports:
    """All 6 tools import cleanly from the tools package."""

    def test_import_apply_md(self) -> None:
        from orf.mcp.tools import apply_md
        assert callable(apply_md)

    def test_import_apply_xliff(self) -> None:
        from orf.mcp.tools import apply_xliff
        assert callable(apply_xliff)

    def test_import_batch_convert(self) -> None:
        from orf.mcp.tools import batch_convert
        assert callable(batch_convert)

    def test_import_detect_format(self) -> None:
        from orf.mcp.tools import detect_format
        assert callable(detect_format)

    def test_import_info(self) -> None:
        from orf.mcp.tools import info
        assert callable(info)

    def test_import_ping(self) -> None:
        from orf.mcp.tools import ping
        assert callable(ping)

    def test_tools_all_exports(self) -> None:
        from orf.mcp.tools import __all__
        expected = {"apply_md", "apply_xliff", "batch_convert",
                     "detect_format", "info", "ping"}
        assert set(__all__) == expected


# ─── Test group 2: server.py backward-compat re-exports ─────────────


class TestServerBackwardCompat:
    """All old import paths still work via server.py re-exports."""

    def test_tool_re_exports(self) -> None:
        from orf.mcp.server import (
            apply_md, apply_xliff, batch_convert,
            detect_format, info, ping,
        )
        for fn in (apply_md, apply_xliff, batch_convert, detect_format, info, ping):
            assert callable(fn)

    def test_helper_re_exports(self) -> None:
        from orf.mcp.server import (
            _run_cli_command, _error_response, _success_response, _augment_error,
        )
        for fn in (_run_cli_command, _error_response, _success_response, _augment_error):
            assert callable(fn)

    def test_singleton_re_exports(self) -> None:
        from orf.mcp.server import _path_validator, _orf_config, _MCP_SCRUB_ENV_KEYS
        assert _MCP_SCRUB_ENV_KEYS is not None
        assert _orf_config is not None
        assert _path_validator is not None

    def test_get_server_re_export(self) -> None:
        from orf.mcp.server import get_server
        assert callable(get_server)


# ─── Test group 3: common.py helper functions ───────────────────────


class TestCommonHelpers:
    """Shared helpers in common.py work correctly."""

    def test_error_response_structure(self) -> None:
        from orf.mcp.common import error_response
        resp = error_response("TEST_CODE", "test message")
        assert resp["success"] is False
        assert resp["error"] == {"code": "TEST_CODE", "message": "test message"}
        assert resp["error_code"] == "TEST_CODE"
        assert resp["message"] == "test message"

    def test_error_response_with_extra(self) -> None:
        from orf.mcp.common import error_response
        resp = error_response("E", "msg", extra_field=42)
        assert resp["extra_field"] == 42

    def test_success_response_structure(self) -> None:
        from orf.mcp.common import success_response
        resp = success_response({"result": "ok"})
        assert resp["success"] is True
        assert resp["content"] == {"result": "ok"}

    def test_augment_error_preserves_success(self) -> None:
        from orf.mcp.common import augment_error
        resp = augment_error({"success": True, "data": "ok"})
        assert resp["success"] is True
        # Should not add error block
        assert "error" not in resp

    def test_augment_error_adds_from_errors(self) -> None:
        from orf.mcp.common import augment_error
        resp = augment_error({
            "success": False,
            "errors": [{"code": "E001", "message": "Something failed"}],
        })
        assert resp["error"] == {"code": "E001", "message": "Something failed"}

    def test_augment_error_fallback(self) -> None:
        from orf.mcp.common import augment_error
        resp = augment_error({"success": False})
        assert resp["error"] == {"code": "ORF_ERROR", "message": "Unknown error"}

    def test_mcp_scrub_env_keys_content(self) -> None:
        from orf.mcp.common import MCP_SCRUB_ENV_KEYS
        assert "OMNI_TEST_FAKE_PANDOC" in MCP_SCRUB_ENV_KEYS
        assert "OMNI_TEST_FAKE_LLM" in MCP_SCRUB_ENV_KEYS
        assert len(MCP_SCRUB_ENV_KEYS) >= 5


# ─── Test group 4: server.py MCP wiring ─────────────────────────────


class TestServerWiring:
    """MCP server setup, dispatch table, and lifecycle are intact."""

    def test_server_instance(self) -> None:
        from orf.mcp.server import server
        assert server.name == "ORF MCP Server"

    def test_tool_dispatch_size(self) -> None:
        from orf.mcp.server import _TOOL_DISPATCH
        assert len(_TOOL_DISPATCH) == 6
        assert set(_TOOL_DISPATCH.keys()) == {
            "apply_md", "apply_xliff", "batch_convert",
            "detect_format", "info", "ping",
        }

    def test_tool_dispatch_functions_are_callable(self) -> None:
        from orf.mcp.server import _TOOL_DISPATCH
        for name, fn in _TOOL_DISPATCH.items():
            assert callable(fn), f"{name} is not callable"

    def test_classify_status_success(self) -> None:
        from orf.mcp.server import _orf_classify_status
        from orf.mcp.metrics import STATUS_SUCCESS
        assert _orf_classify_status({"success": True}) == STATUS_SUCCESS

    def test_classify_status_error(self) -> None:
        from orf.mcp.server import _orf_classify_status
        from orf.mcp.metrics import STATUS_ERROR
        assert _orf_classify_status({"success": False}) == STATUS_ERROR

    def test_classify_status_rate_limited(self) -> None:
        from orf.mcp.server import _orf_classify_status
        from orf.mcp.metrics import STATUS_RATE_LIMITED
        assert _orf_classify_status({"error_code": "RATE_LIMITED"}) == STATUS_RATE_LIMITED

    def test_classify_status_auth_failed(self) -> None:
        from orf.mcp.server import _orf_classify_status
        from orf.mcp.metrics import STATUS_AUTH_FAILED
        assert _orf_classify_status({"error_code": "AUTH_FAILED"}) == STATUS_AUTH_FAILED

    def test_classify_status_from_error_dict(self) -> None:
        from orf.mcp.server import _orf_classify_status
        from orf.mcp.metrics import STATUS_AUTH_FAILED
        assert _orf_classify_status({
            "success": False,
            "error": {"code": "AUTH_FAILED"},
        }) == STATUS_AUTH_FAILED

    def test_classify_status_non_dict(self) -> None:
        from orf.mcp.server import _orf_classify_status
        from orf.mcp.metrics import STATUS_ERROR
        assert _orf_classify_status("not a dict") == STATUS_ERROR

    def test_get_server_returns_singleton(self) -> None:
        from orf.mcp.server import get_server, server
        assert get_server() is server

    def test_main_is_callable(self) -> None:
        from orf.mcp.server import main
        assert callable(main)


# ─── Test group 5: function signatures match originals ──────────────


class TestFunctionSignatures:
    """Tool function signatures are unchanged after the split."""

    def test_apply_md_signature(self) -> None:
        from orf.mcp.server import apply_md
        sig = inspect.signature(apply_md)
        params = list(sig.parameters.keys())
        # The original signature has these parameters (in order)
        expected_params = [
            "input_md", "target_format", "output_path", "images",
            "separate_images", "reference_doc", "template", "title",
            "author", "lang", "embed_images", "text_only",
            "max_file_size_mb", "auth_token", "traceparent", "content",
        ]
        assert params == expected_params, f"Got {params}"

    def test_apply_xliff_signature(self) -> None:
        from orf.mcp.server import apply_xliff
        sig = inspect.signature(apply_xliff)
        params = list(sig.parameters.keys())
        expected_params = [
            "input_file", "xliff_path", "output_path", "format",
            "xliff_content", "images", "force", "no_cache",
            "max_file_size_mb", "auth_token", "traceparent", "skeleton_html",
        ]
        assert params == expected_params, f"Got {params}"

    def test_batch_convert_signature(self) -> None:
        from orf.mcp.server import batch_convert
        sig = inspect.signature(batch_convert)
        params = list(sig.parameters.keys())
        assert params == ["input_dir", "target_format", "pattern", "auth_token"]

    def test_detect_format_signature(self) -> None:
        from orf.mcp.server import detect_format
        sig = inspect.signature(detect_format)
        params = list(sig.parameters.keys())
        assert params == ["file_path", "auth_token"]

    def test_info_signature(self) -> None:
        from orf.mcp.server import info
        sig = inspect.signature(info)
        params = list(sig.parameters.keys())
        assert params == ["file_path", "auth_token"]

    def test_ping_signature(self) -> None:
        from orf.mcp.server import ping
        sig = inspect.signature(ping)
        params = list(sig.parameters.keys())
        assert params == ["auth_token"]
        # _ _future_ _ annotations makes this 'str' rather than str
        assert sig.return_annotation in ("str", str)

    def test_apply_md_return_annotation(self) -> None:
        from orf.mcp.server import apply_md
        sig = inspect.signature(apply_md)
        assert sig.return_annotation in ("str", str), f"Got {sig.return_annotation}"

    def test_apply_xliff_return_annotation(self) -> None:
        from orf.mcp.server import apply_xliff
        sig = inspect.signature(apply_xliff)
        assert sig.return_annotation in ("str", str), f"Got {sig.return_annotation}"
