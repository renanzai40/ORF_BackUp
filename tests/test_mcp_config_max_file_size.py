"""P0-T3: ORF_MCP_MAX_FILE_SIZE → ORF_MCP_MAX_FILE_SIZE_MB rename.

The env var name must include the _MB suffix so the unit is unambiguous.
A user setting 100 should get 100 MB, not 100 bytes or 100 TB.
"""

import os
import pytest
from pathlib import Path


class TestMaxFileSizeEnvVar:
    """ORF_MCP_MAX_FILE_SIZE_MB env var must be read correctly."""

    def setup_method(self):
        """Ensure ORF_MCP_ALLOWED_DIRS is set for load_config to succeed."""
        os.environ.setdefault("ORF_MCP_ALLOWED_DIRS", "/tmp")

    def _clear_max_file_size_vars(self):
        """Remove both old and new env var names."""
        os.environ.pop("ORF_MCP_MAX_FILE_SIZE", None)
        os.environ.pop("ORF_MCP_MAX_FILE_SIZE_MB", None)

    def test_new_env_var_mb_suffix(self):
        """ORF_MCP_MAX_FILE_SIZE_MB=50 produces max_file_size_mb=50."""
        from orf.mcp.config import load_config

        self._clear_max_file_size_vars()
        os.environ["ORF_MCP_MAX_FILE_SIZE_MB"] = "50"
        try:
            cfg = load_config()
            assert cfg.max_file_size_mb == 50, (
                f"Expected max_file_size_mb=50, got {cfg.max_file_size_mb}"
            )
        finally:
            os.environ.pop("ORF_MCP_MAX_FILE_SIZE_MB", None)

    def test_old_env_var_no_longer_recognized(self):
        """ORF_MCP_MAX_FILE_SIZE (without _MB) must NOT set max_file_size_mb.

        The old name is ambiguous — a user setting 104857600 (100MB in bytes)
        would be treated as 100TB.  It must be silently ignored so the default
        (100 MB) is used instead.
        """
        from orf.mcp.config import load_config

        self._clear_max_file_size_vars()
        os.environ["ORF_MCP_MAX_FILE_SIZE"] = "104857600"
        try:
            cfg = load_config()
            # The old var should NOT be read; default is 100 MB
            assert cfg.max_file_size_mb == 100, (
                f"Old env var was read! Got max_file_size_mb={cfg.max_file_size_mb}, "
                "expected default 100"
            )
        finally:
            os.environ.pop("ORF_MCP_MAX_FILE_SIZE", None)

    def test_default_is_100_mb(self):
        """When no env var is set, default max_file_size_mb is 100."""
        from orf.mcp.config import load_config

        self._clear_max_file_size_vars()
        cfg = load_config()
        assert cfg.max_file_size_mb == 100

    def test_new_var_invalid_value_ignored(self):
        """Invalid ORF_MCP_MAX_FILE_SIZE_MB value falls back to default."""
        from orf.mcp.config import load_config

        self._clear_max_file_size_vars()
        os.environ["ORF_MCP_MAX_FILE_SIZE_MB"] = "not_a_number"
        try:
            cfg = load_config()
            assert cfg.max_file_size_mb == 100
        finally:
            os.environ.pop("ORF_MCP_MAX_FILE_SIZE_MB", None)
