"""T-08 regression: ``orf.mcp.common.get_path_validator`` must fail CLOSED.

``load_config()`` already raises when the allowlist is unset (P0-T2), but
``get_path_validator()`` still carried a latent fail-OPEN fallback
``cfg.allowed_directories or [Path.cwd()]``. Any config object with no
directories would silently grant the MCP access to the whole working
directory instead of refusing to serve.

These tests are written red-first: the empty/None-config cases return a
cwd-scoped validator before the fix.

Isolation note: the tests null the cached ``_config``/``_path_validator``
singletons via ``monkeypatch`` so pytest restores whatever the server
cached before the test — never leaving a stale ``None`` behind for later
tests (``test_orf_mcp_server.py::test_full_apply_md_flow`` relies on the
cached instance surviving).
"""
from __future__ import annotations

import pytest


def _force_fresh_singletons(monkeypatch) -> None:
    from orf.mcp import common

    monkeypatch.setattr(common, "_config", None)
    monkeypatch.setattr(common, "_path_validator", None)


def test_get_path_validator_rejects_empty_allowed_directories(monkeypatch):
    from orf.mcp import common
    from orf.mcp.config import MCPConfig

    _force_fresh_singletons(monkeypatch)
    monkeypatch.setattr(common, "get_config", lambda: MCPConfig(allowed_directories=[]))
    with pytest.raises(ValueError):
        common.get_path_validator()


def test_get_path_validator_rejects_none_allowed_directories(monkeypatch):
    from orf.mcp import common
    from orf.mcp.config import MCPConfig

    _force_fresh_singletons(monkeypatch)
    monkeypatch.setattr(
        common, "get_config", lambda: MCPConfig(allowed_directories=None)
    )
    with pytest.raises(ValueError):
        common.get_path_validator()


def test_get_path_validator_raises_when_allowlist_env_unset(monkeypatch):
    from orf.mcp import common

    _force_fresh_singletons(monkeypatch)
    monkeypatch.delenv("MCP_ALLOWED_DIRECTORIES", raising=False)
    monkeypatch.delenv("ORF_MCP_ALLOWED_DIRS", raising=False)
    with pytest.raises(ValueError):
        common.get_path_validator()
