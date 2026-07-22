"""ORF MCP error code map — centralized error code constants & safe messages.

All ORF MCP modules should import error code constants from this module
instead of using inline string literals. This ensures consistency,
enables easy auditing of used codes, and provides a single source of
truth for safe (user-friendly) messages.

The functions ``error_response()`` and ``augment_error()`` are re-exported
from ``orf.mcp.common`` for convenience, so callers can import everything
related to error handling from a single module.
"""

from __future__ import annotations

# ─── Error code constants ────────────────────────────────────────────
# These are the canonical error codes used across all ORF MCP tools.
# Each value corresponds to a specific error condition.

AUTH_FAILED: str = "AUTH_FAILED"
"""Shared-secret authentication failed."""

RATE_LIMITED: str = "RATE_LIMITED"
"""Rate limit exceeded."""

ORF_ERROR: str = "ORF_ERROR"
"""Fallback / generic error code."""

ORF_UNKNOWN_TOOL: str = "ORF_UNKNOWN_TOOL"
"""MCP tool dispatch received an unknown tool name."""

ORF_INTERNAL_ERROR: str = "ORF_INTERNAL_ERROR"
"""Unhandled exception during tool execution."""

EMPTY_OUTPUT: str = "EMPTY_OUTPUT"
"""CLI subprocess returned empty stdout."""

JSON_PARSE_ERROR: str = "JSON_PARSE_ERROR"
"""CLI subprocess stdout is not valid JSON."""

CLI_ERROR: str = "CLI_ERROR"
"""CLI subprocess exited with non-zero return code."""

MISSING_INPUT: str = "MISSING_INPUT"
"""Required input parameter was not provided."""

MUTUALLY_EXCLUSIVE: str = "MUTUALLY_EXCLUSIVE"
"""Two mutually exclusive parameters were both supplied."""

INLINE_CONTENT_WRITE_FAILED: str = "INLINE_CONTENT_WRITE_FAILED"
"""Failed to write inline markdown content to a temporary file."""

INLINE_REFERENCE_DOC_WRITE_FAILED: str = "INLINE_REFERENCE_DOC_WRITE_FAILED"
"""Failed to write inline reference document to a temporary file."""

PATH_NOT_ALLOWED: str = "PATH_NOT_ALLOWED"
"""Path was rejected by PathValidator."""

FILE_PATH_NOT_ALLOWED: str = "FILE_PATH_NOT_ALLOWED"
"""Image ``file_path`` is not allowed via MCP; use ``data_base64`` instead."""


# ─── Safe user messages ─────────────────────────────────────────────

SAFE_USER_MESSAGES: dict[str, str] = {
    AUTH_FAILED: (
        "Authentication failed: auth_token is missing or incorrect."
    ),
    RATE_LIMITED: (
        "Rate limit exceeded. Please slow down and try again."
    ),
    ORF_ERROR: (
        "An unexpected error occurred. Check server logs."
    ),
    ORF_UNKNOWN_TOOL: (
        "The requested tool is not available."
    ),
    ORF_INTERNAL_ERROR: (
        "An internal server error occurred. Check server logs."
    ),
    EMPTY_OUTPUT: (
        "The conversion returned no output. Check server logs."
    ),
    JSON_PARSE_ERROR: (
        "Failed to parse the conversion result. Check server logs."
    ),
    CLI_ERROR: (
        "The conversion command exited with an error. Check server logs."
    ),
    MISSING_INPUT: (
        "Required input is missing. Provide either input_md (path) "
        "or content (inline markdown)."
    ),
    MUTUALLY_EXCLUSIVE: (
        "Two parameters that cannot be used together were both provided."
    ),
    INLINE_CONTENT_WRITE_FAILED: (
        "Failed to process inline content. Check server logs."
    ),
    INLINE_REFERENCE_DOC_WRITE_FAILED: (
        "Failed to process inline reference document. Check server logs."
    ),
    PATH_NOT_ALLOWED: (
        "Access to the requested path was denied."
    ),
    FILE_PATH_NOT_ALLOWED: (
        "file_path is not allowed via MCP; use data_base64 instead."
    ),
}


def get_safe_message(code: str) -> str:
    """Return a user-friendly message for the given error code.

    Args:
        code: An error code constant (e.g. ``PATH_NOT_ALLOWED``).

    Returns:
        A user-friendly message string. Falls back to a generic message
        for unknown codes.
    """
    return SAFE_USER_MESSAGES.get(
        code,
        "An internal error occurred. Check server logs.",
    )


# ─── Re-exports from common.py ───────────────────────────────────────
# These are imported lazily (at function-call time) to avoid circular
# imports: ``common.py`` imports error constants from this module, so
# ``_errors.py`` must not import from ``common.py`` at module level.

def error_response(code: str, message: str, **extra: object) -> dict:
    """Build a standardized error response dict.

    See ``orf.mcp.common.error_response`` for full documentation.
    This is a lazy re-export for convenience.
    """
    from orf.mcp.common import error_response as _fn
    return _fn(code, message, **extra)


def augment_error(resp: dict) -> dict:
    """Add top-level ``error: {code, message}`` to an existing error dict.

    See ``orf.mcp.common.augment_error`` for full documentation.
    This is a lazy re-export for convenience.
    """
    from orf.mcp.common import augment_error as _fn
    return _fn(resp)


__all__ = [
    # Error code constants
    "AUTH_FAILED",
    "RATE_LIMITED",
    "ORF_ERROR",
    "ORF_UNKNOWN_TOOL",
    "ORF_INTERNAL_ERROR",
    "EMPTY_OUTPUT",
    "JSON_PARSE_ERROR",
    "CLI_ERROR",
    "MISSING_INPUT",
    "MUTUALLY_EXCLUSIVE",
    "INLINE_CONTENT_WRITE_FAILED",
    "INLINE_REFERENCE_DOC_WRITE_FAILED",
    "PATH_NOT_ALLOWED",
    "FILE_PATH_NOT_ALLOWED",
    # Safe messages
    "SAFE_USER_MESSAGES",
    "get_safe_message",
    # Re-exported helpers
    "error_response",
    "augment_error",
]
