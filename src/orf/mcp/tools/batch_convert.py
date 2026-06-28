"""batch_convert tool — Batch convert MD files for ORF MCP Server."""

from __future__ import annotations

import json
from typing import Optional

from orf.mcp.auth import auth_failure_response, check_auth
from orf.mcp.common import (
    augment_error,
    error_response,
    path_validator,
    success_response,
)
from orf.mcp.rate_limiter import check_rate_limit, rate_limit_failure_response


def batch_convert(input_dir: str, target_format: str, pattern: str = "*.md", auth_token: Optional[str] = None) -> str:
    """Batch convert MD files. In-process equivalent of the MCP tool."""
    # H5: token bucket rate limiter
    rate_ok, rate_err = check_rate_limit()
    if not rate_ok:
        return json.dumps({**rate_limit_failure_response(), "error": rate_err})
    # 2026-06-18 round 16 Phase A4: MCP shared-secret auth.
    auth_ok, _ = check_auth(auth_token)
    if not auth_ok:
        return json.dumps(auth_failure_response(), ensure_ascii=False)
    result_dir = path_validator.validate_path(input_dir, allow_missing=True)
    if not result_dir.success:
        return json.dumps(error_response(
            "PATH_NOT_ALLOWED", result_dir.error or "Path validation failed",
            content={"success_count": 0, "fail_count": 0, "total": 0},
        ))

    args = ["convert-batch", input_dir, "--target-format", target_format, "--pattern", pattern]
    from orf.mcp.server import _run_cli_command
    cli_result = _run_cli_command(args)
    if cli_result.get("success"):
        return json.dumps(success_response(cli_result))
    return json.dumps(augment_error(cli_result))
