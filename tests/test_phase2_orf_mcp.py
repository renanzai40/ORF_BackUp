"""Tests for Phase 2 MCP consistency in ORF (P2-T1, T2, T3, T4).

P2-T1: MCP_ALLOWED_DIRECTORIES as primary env var (ORF_MCP_ALLOWED_DIRS fallback)
P2-T2: Server name 'orf-mcp'
P2-T3: MCP_TOOL_TIMEOUT env var, default 120s
P2-T4: MCP_ALLOWED_EXTENSIONS env var to override defaults
"""

import importlib
import os
from pathlib import Path
from unittest.mock import patch

import pytest


# ── P2-T1: Unified env var ──────────────────────────────────────────────


class TestP2T1UnifiedEnvVar:
    """MCP_ALLOWED_DIRECTORIES should be primary, ORF_MCP_ALLOWED_DIRS fallback."""

    def test_unified_env_var_is_read(self, tmp_path):
        """MCP_ALLOWED_DIRECTORIES env var should set allowed_directories."""
        import orf.mcp.config as cfg

        with patch.dict(os.environ, {"MCP_ALLOWED_DIRECTORIES": str(tmp_path)}, clear=False):
            # Remove ORF-specific so only unified is set
            os.environ.pop("ORF_MCP_ALLOWED_DIRS", None)
            importlib.reload(cfg)
            config = cfg.load_config()
            assert tmp_path.resolve() in [
                d.resolve() for d in config.allowed_directories
            ], f"Unified env var not read: {config.allowed_directories}"

    def test_orf_specific_env_var_still_works(self, tmp_path):
        """Backward compat: ORF_MCP_ALLOWED_DIRS should still work."""
        import orf.mcp.config as cfg

        with patch.dict(os.environ, {"ORF_MCP_ALLOWED_DIRS": str(tmp_path)}, clear=False):
            os.environ.pop("MCP_ALLOWED_DIRECTORIES", None)
            importlib.reload(cfg)
            config = cfg.load_config()
            assert tmp_path.resolve() in [
                d.resolve() for d in config.allowed_directories
            ], f"Backward compat broken: {config.allowed_directories}"

    def test_unified_takes_precedence_over_orf_specific(self, tmp_path):
        """When both are set, MCP_ALLOWED_DIRECTORIES wins."""
        import orf.mcp.config as cfg

        unified = tmp_path / "unified"
        orf_specific = tmp_path / "orf_specific"
        unified.mkdir()
        orf_specific.mkdir()

        with patch.dict(
            os.environ,
            {"MCP_ALLOWED_DIRECTORIES": str(unified), "ORF_MCP_ALLOWED_DIRS": str(orf_specific)},
            clear=False,
        ):
            importlib.reload(cfg)
            config = cfg.load_config()
            assert unified.resolve() in [
                d.resolve() for d in config.allowed_directories
            ], f"Unified should take precedence: {config.allowed_directories}"


# ── P2-T2: Server name ──────────────────────────────────────────────────


class TestP2T2ServerName:
    """ORF MCP server should be named 'orf-mcp'."""

    def test_server_name_is_orf_mcp(self):
        """Server name should match the standard pattern."""
        import orf.mcp.server as srv

        assert srv.server.name == "orf-mcp", f"Server name is '{srv.server.name}', expected 'orf-mcp'"


# ── P2-T3: MCP_TOOL_TIMEOUT ─────────────────────────────────────────────


class TestP2T3McpToolTimeout:
    """MCP_TOOL_TIMEOUT env var should be read; default should be >= 60s."""

    def test_default_timeout_is_at_least_60(self):
        """Default timeout should be >= 60s (was 30s — too low)."""
        import orf.mcp.config as cfg

        os.environ.pop("MCP_TOOL_TIMEOUT", None)
        os.environ.pop("ORF_MCP_TIMEOUT", None)
        importlib.reload(cfg)
        config = cfg.MCPConfig(allowed_directories=[Path("/tmp")])
        timeout = config.timeout_seconds
        assert timeout >= 60, f"ORF timeout {timeout}s is too low, should be >= 60s"

    def test_mcp_tool_timeout_env_var_works(self, tmp_path):
        """MCP_TOOL_TIMEOUT env var should set the timeout."""
        import orf.mcp.config as cfg

        with patch.dict(os.environ, {"MCP_TOOL_TIMEOUT": "90", "MCP_ALLOWED_DIRECTORIES": str(tmp_path)}, clear=False):
            os.environ.pop("ORF_MCP_TIMEOUT", None)
            importlib.reload(cfg)
            config = cfg.load_config()
            assert config.timeout_seconds == 90, f"Expected 90, got {config.timeout_seconds}"

    def test_orf_mcp_timeout_still_works(self, tmp_path):
        """Backward compat: ORF_MCP_TIMEOUT should still work."""
        import orf.mcp.config as cfg

        with patch.dict(os.environ, {"ORF_MCP_TIMEOUT": "45", "MCP_ALLOWED_DIRECTORIES": str(tmp_path)}, clear=False):
            os.environ.pop("MCP_TOOL_TIMEOUT", None)
            importlib.reload(cfg)
            config = cfg.load_config()
            assert config.timeout_seconds == 45, f"Expected 45, got {config.timeout_seconds}"


# ── P2-T4: MCP_ALLOWED_EXTENSIONS ───────────────────────────────────────


class TestP2T4AllowedExtensions:
    """MCP_ALLOWED_EXTENSIONS env var should override the default set."""

    def test_env_var_overrides_default_extensions(self):
        """Setting MCP_ALLOWED_EXTENSIONS should replace the default set."""
        import orf.mcp.security as sec

        custom_exts = ".md,.docx,.pdf"
        with patch.dict(os.environ, {"MCP_ALLOWED_EXTENSIONS": custom_exts}, clear=False):
            importlib.reload(sec)
            validator = sec.PathValidator(allowed_directories=[Path("/tmp")])
            assert validator.ALLOWED_EXTENSIONS == {".md", ".docx", ".pdf"}, \
                f"Expected custom set, got {validator.ALLOWED_EXTENSIONS}"

    def test_default_extensions_when_env_unset(self):
        """Without MCP_ALLOWED_EXTENSIONS, the default set should be used."""
        import orf.mcp.security as sec

        os.environ.pop("MCP_ALLOWED_EXTENSIONS", None)
        importlib.reload(sec)
        validator = sec.PathValidator(allowed_directories=[Path("/tmp")])
        # The default should include at least these
        assert ".md" in validator.ALLOWED_EXTENSIONS
        assert ".docx" in validator.ALLOWED_EXTENSIONS
        assert ".xlsx" in validator.ALLOWED_EXTENSIONS
