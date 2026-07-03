"""P0-T2: ORF MCP fail-CLOSED — ORF_MCP_ALLOWED_DIRS must be set.

When the env var is unset or empty, MCPConfig / load_config must raise
ValueError instead of silently falling back to Path.cwd() (fail-OPEN).
"""

import os
import pytest
from pathlib import Path


class TestFailClosedAllowedDirs:
    """load_config must raise ValueError when ORF_MCP_ALLOWED_DIRS is unset."""

    def _clear_allowed_dirs(self):
        """Remove ORF_MCP_ALLOWED_DIRS from env so from_env / load_config sees it as unset."""
        os.environ.pop("ORF_MCP_ALLOWED_DIRS", None)

    def test_raises_when_env_unset(self):
        """MCPConfig construction via load_config raises ValueError when env var is absent."""
        from orf.mcp.config import load_config

        self._clear_allowed_dirs()
        with pytest.raises(ValueError, match="ORF_MCP_ALLOWED_DIRS"):
            load_config()

    def test_raises_when_env_empty_string(self):
        """MCPConfig construction raises ValueError when env var is set to empty string."""
        from orf.mcp.config import load_config

        os.environ["ORF_MCP_ALLOWED_DIRS"] = ""
        with pytest.raises(ValueError, match="ORF_MCP_ALLOWED_DIRS"):
            load_config()

    def test_raises_when_env_whitespace_only(self):
        """MCPConfig construction raises ValueError when env var is whitespace."""
        from orf.mcp.config import load_config

        os.environ["ORF_MCP_ALLOWED_DIRS"] = "   "
        with pytest.raises(ValueError, match="ORF_MCP_ALLOWED_DIRS"):
            load_config()

    def test_works_when_env_set(self, tmp_path):
        """load_config succeeds when ORF_MCP_ALLOWED_DIRS points to a valid directory."""
        from orf.mcp.config import load_config

        os.environ["ORF_MCP_ALLOWED_DIRS"] = str(tmp_path)
        cfg = load_config()
        assert tmp_path in cfg.allowed_directories

    def test_works_with_multiple_dirs(self, tmp_path):
        """load_config parses colon-separated directories."""
        from orf.mcp.config import load_config

        d1 = tmp_path / "a"
        d2 = tmp_path / "b"
        d1.mkdir()
        d2.mkdir()
        os.environ["ORF_MCP_ALLOWED_DIRS"] = f"{d1}:{d2}"
        cfg = load_config()
        assert d1 in cfg.allowed_directories
        assert d2 in cfg.allowed_directories
