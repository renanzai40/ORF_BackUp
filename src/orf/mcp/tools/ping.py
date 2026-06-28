"""ping tool — health check endpoint for ORF MCP Server."""

from __future__ import annotations

import json
from typing import Optional

from orf.mcp.auth import auth_failure_response, check_auth
from orf.mcp.common import success_response
from orf.mcp.rate_limiter import check_rate_limit, rate_limit_failure_response


def ping(auth_token: Optional[str] = None) -> str:
    """Health check endpoint. In-process equivalent of the MCP tool."""
    # H5: token bucket rate limiter
    rate_ok, rate_err = check_rate_limit()
    if not rate_ok:
        return json.dumps({**rate_limit_failure_response(), "error": rate_err})
    # 2026-06-18 round 16 Phase A4: MCP shared-secret auth.
    auth_ok, _ = check_auth(auth_token)
    if not auth_ok:
        return json.dumps(auth_failure_response(), ensure_ascii=False)
    from orf import __version__ as _orf_version
    return json.dumps(
        success_response({"module": "orf", "version": _orf_version}),
        ensure_ascii=False,
    )
