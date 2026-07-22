"""Shared helpers for ORF MCP tools.

Extracted from server.py during the v0.4.16 tools/ package refactor. Contains
subprocess dispatch, path-safety helpers, response formatters, and module-level
singletons (config, validator, logger) that are shared across all tool modules
and the MCP server itself.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional

from orf.logging import get_logger
from orf.mcp._errors import CLI_ERROR, EMPTY_OUTPUT, JSON_PARSE_ERROR, ORF_ERROR
from orf.mcp.config import MCPConfig, load_config
from orf.mcp.security import PathValidator

# ULTRAREADY-VERIFY (2026-06-07): env vars that must NEVER be inherited
# by the CLI subprocess. These are test-only seams — if a test harness
# started the MCP server with one of them set, every MCP conversion
# would silently produce fake output. The list is centralized here so
# adding a new seam in the future means updating one constant + one test.
MCP_SCRUB_ENV_KEYS = frozenset({
    "OMNI_TEST_FAKE_PANDOC",
    "OMNI_TEST_FAKE_LLM",
    "OMNI_TEST_FAKE",
    "OMNI_TEST_MOCK",
    "OMNI_TEST_STUB",
})

logger = get_logger("mcp.server")

# Config & validator (lazy-initialized singletons).
# Previously these were created at module-import time, which meant tests that
# changed ORF_MCP_ALLOWED_DIRS after import saw stale config (ORF #40).
# Now they are loaded on first access via get_path_validator()/get_config().
_path_validator: PathValidator | None = None
_config: MCPConfig | None = None


def get_config() -> MCPConfig:
    """Load MCPConfig lazily — reads env vars on first call, not at import."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def get_path_validator() -> PathValidator:
    """Lazy-initialized PathValidator singleton.

    Unlike the previous module-level singleton, this reads config (and thus
    env vars) on first call, not at import time. Tests that set
    ``ORF_MCP_ALLOWED_DIRS`` before the first call will see the correct config.
    """
    global _path_validator
    if _path_validator is None:
        cfg = get_config()
        _path_validator = PathValidator(
            allowed_directories=cfg.allowed_directories or [Path.cwd()],
            max_file_size_bytes=cfg.max_file_size_mb * 1024 * 1024,
        )
    return _path_validator


def reset_config_and_validator() -> None:
    """Reset cached config and validator (for testing — e.g. between tests)."""
    global _config, _path_validator
    _config = None
    _path_validator = None


def __getattr__(name: str):
    """Backward-compat attribute access for module-level ``orf_config`` and ``path_validator``.

    ``from orf.mcp.common import path_validator`` triggers this on first
    access, returning the lazy-initialized instance.
    """
    if name == "orf_config":
        return get_config()
    if name == "path_validator":
        return get_path_validator()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def error_response(code: str, message: str, **extra: Any) -> dict:
    """Standardized error response with backward-compat fields."""
    resp: dict[str, Any] = {
        "success": False,
        "error": {"code": code, "message": message},
        "error_code": code,
        "message": message,
        "errors": [{"code": code, "message": message, "recovery_strategy": None}],
    }
    resp.update(extra)
    return resp


def success_response(content: dict) -> dict:
    """Standardized success response wrapping payload under ``content``."""
    return {"success": True, "content": content}


def augment_error(resp: dict) -> dict:
    """Add top-level ``error: {code, message}`` to an existing error dict.

    Extracts code/message from ``errors[0]`` if present, preserving all
    existing fields (backward compat). Also adds flat ``error_code`` and
    ``message`` fields for consistency with ``error_response()``.
    """
    if resp.get("success") is True:
        return resp
    if "error" not in resp:
        errors = resp.get("errors", [])
        if errors and isinstance(errors[0], dict):
            resp["error"] = {
                "code": errors[0].get("code", ORF_ERROR),
                "message": errors[0].get("message", "Unknown error"),
            }
        else:
            resp["error"] = {"code": ORF_ERROR, "message": "Unknown error"}
    if "error_code" not in resp:
        resp["error_code"] = resp["error"].get("code", ORF_ERROR)
    if "message" not in resp:
        resp["message"] = resp["error"].get("message", "Unknown error")
    return resp


# ─── CLI subprocess helper ─────────────────────────────────────────────


def run_cli_command(args: list[str]) -> dict:
    """Run ORF CLI command and return parsed JSON result."""
    # ULTRAREADY-VERIFY (2026-06-07): scrub test-only env vars before
    # invoking the CLI subprocess. Without this, a test harness that
    # started the MCP server with OMNI_TEST_FAKE_PANDOC=1 would silently
    # route every MCP conversion to a stub-DOCX (the FAKE_PANDOC seam
    # in orf/cli.py:191-212 monkey-patches subprocess.run for the
    # lifetime of the CLI process).
    scrubbed_env = {
        k: v for k, v in os.environ.items()
        if k not in MCP_SCRUB_ENV_KEYS
    }
    result = subprocess.run(
        [sys.executable, "-m", "orf.cli"] + args + ["--json"],
        capture_output=True,
        text=True,
        env=scrubbed_env,
    )

    # Bug 4 Fix: Handle empty stdout
    if not result.stdout.strip():
        logger.error(f"CLI returned empty stdout. args={args}, stderr={result.stderr[:500]}")
        return {
            "success": False,
            "output_path": None,
            "errors": [{
                "code": EMPTY_OUTPUT,
                "message": f"CLI returned empty. stderr: {result.stderr[:500]}",
                "recovery_strategy": None
            }],
            "warnings": [],
            "metadata": {}
        }

    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}. stdout: {result.stdout[:200]}")
        return {
            "success": False,
            "output_path": None,
            "errors": [{
                "code": JSON_PARSE_ERROR,
                "message": f"JSON decode failed: {e}. Output: {result.stdout[:500]}",
                "recovery_strategy": None
            }],
            "warnings": [],
            "metadata": {}
        }

    if result.returncode == 0:
        return parsed
    else:
        # CLI failed but might have valid error JSON
        return parsed if "success" in parsed else {
            "success": False,
            "output_path": None,
            "errors": [{
                "code": CLI_ERROR,
                "message": result.stderr or "Unknown error",
                "recovery_strategy": None
            }],
            "warnings": [],
            "metadata": {}
        }


# ─── Path safety helpers ───────────────────────────────────────────────


def safe_unlink(path: str) -> bool:
    """Resolve+revalidate path before unlink; refuse to follow symlinks."""
    try:
        resolved = Path(path).resolve()
    except (ValueError, OSError):
        return False
    if Path(path).is_symlink():
        return False
    result = get_path_validator().validate_path(str(resolved), allow_missing=True)
    if not result.success:
        return False
    try:
        os.unlink(resolved)
        return True
    except OSError:
        return False


def resolve_context_path(
    path: Optional[str], context_dir: Optional[str]
) -> Optional[str]:
    """Resolve a relative path against a context_dir.

    Behaviour:
      - path is None: return None (caller skips the param)
      - path is absolute: return as-is (absolute paths win over context)
      - path is relative + context_dir is set: return context_dir/path
      - path is relative + context_dir is None: return path as-is (current behavior)

    The caller is responsible for validating context_dir through the
    PathValidator. This helper does NOT do path validation — it only
    resolves relative paths.
    """
    if path is None:
        return None
    if context_dir is None:
        return path
    if Path(path).is_absolute():
        return path
    return str(Path(context_dir) / path)


def safe_temp_output(suffix: str, parent: Optional[Path] = None) -> str:
    """Create a tempfile inside parent dir (must be in an allowed dir)."""
    if parent is None:
        parent = Path.cwd()
    parent_resolved = parent.resolve()
    fd, name = tempfile.mkstemp(suffix=suffix, prefix="orf_mcp_", dir=str(parent_resolved))
    os.close(fd)
    return name
