"""detect_format tool — Detect document format for ORF MCP Server."""

from __future__ import annotations

import json
from typing import Optional

from orf.mcp.auth import auth_failure_response, check_auth
from orf.mcp.common import (
    error_response,
    get_path_validator,
    success_response,
)
from orf.mcp.rate_limiter import check_rate_limit, rate_limit_failure_response


def detect_format(file_path: str, auth_token: Optional[str] = None) -> str:
    """Detect document format. In-process equivalent of the MCP tool."""
    # H5: token bucket rate limiter
    rate_ok, rate_err = check_rate_limit()
    if not rate_ok:
        return json.dumps({**rate_limit_failure_response(), "error": rate_err})
    # 2026-06-18 round 16 Phase A4: MCP shared-secret auth.
    auth_ok, _ = check_auth(auth_token)
    if not auth_ok:
        return json.dumps(auth_failure_response(), ensure_ascii=False)
    result_df = get_path_validator().validate_path(file_path)
    if not result_df.success:
        return json.dumps(error_response(
            "PATH_NOT_ALLOWED", result_df.error or "Path validation failed",
            content={"format": "UNKNOWN", "confidence": 0.0},
        ))

    args = ["info", file_path]
    from orf.mcp.server import _run_cli_command
    result = _run_cli_command(args)
    return json.dumps(success_response({
        "format": result.get("format", "UNKNOWN"), "confidence": 1.0,
    }))
