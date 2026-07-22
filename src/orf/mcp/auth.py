"""MCP shared-secret auth (round 16 Phase A4) -- ORF variant."""

from __future__ import annotations

import os

from orf.mcp._errors import AUTH_FAILED


def check_auth(provided_secret: str | None) -> tuple[bool, str | None]:
    expected = os.environ.get("MCP_SHARED_SECRET")
    if not expected:
        return (True, None)
    if provided_secret == expected:
        return (True, None)
    return (False, AUTH_FAILED)


def auth_failure_response() -> dict:
    return {
        "success": False,
        "error_code": AUTH_FAILED,
        "message": "Authentication failed: auth_token is missing or incorrect.",
    }
