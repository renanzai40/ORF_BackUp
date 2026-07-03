"""Round 13+: apply-md --target-format Choice coverage.

Round 10 excluded pptx (md2pptx binary not installed by default).
Round 13 re-added pptx after MartinPacker/md2pptx was installed.

These tests lock in the current Choice composition so future
additions are explicit and tested.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

_OL_ROOT = Path(__file__).resolve().parents[1]
_OL_SRC = _OL_ROOT / "src"
_VENV = _OL_ROOT.parent / ".venv_ol" / "bin" / "python"


def _run_apply_md_help() -> str:
    """Capture `orf apply-md --help` output."""
    import os
    result = subprocess.run(
        [str(_VENV), "-m", "orf", "apply-md", "--help"],
        capture_output=True, text=True, env={
            "PYTHONPATH": str(_OL_SRC),
            "PATH": str(_VENV.parent) + ":" + os.environ.get("PATH", ""),
            "ORF_MCP_ALLOWED_DIRS": os.environ.get("ORF_MCP_ALLOWED_DIRS", "/tmp"),
        },
        timeout=15,
    )
    return result.stdout + result.stderr


class TestApplyMdTargetFormatChoice:
    """Lock in the apply-md --target-format Choice composition."""

    def test_help_shows_target_format_choices(self):
        """--target-format must list the 16 supported formats (round 10)."""
        out = _run_apply_md_help()
        m = re.search(r"--target-format \[([^\]]+)\]", out)
        assert m, f"--target-format Choice not found in help:\n{out}"
        choices = m.group(1).split("|")
        # 17 = auto + 16 formats (pptx re-added in round 13)
        assert len(choices) == 17, (
            f"Expected 17 target-format choices, got {len(choices)}: {choices}"
        )

    def test_pptx_included_in_choices(self):
        """PPTX must now be in --target-format Choice (round 13 re-added
        pptx after md2pptx binary was installed)."""
        out = _run_apply_md_help()
        m = re.search(r"--target-format \[([^\]]+)\]", out)
        assert m
        choices = m.group(1).split("|")
        assert "pptx" in choices, (
            f"pptx should be in choices now; md2pptx is installed. Got: {choices}"
        )

    def test_all_standard_data_formats_present(self):
        """docx, html, pdf, xlsx, csv, json, xml, ipynb, eml, epub
        must all be in the Choice (data format coverage)."""
        out = _run_apply_md_help()
        m = re.search(r"--target-format \[([^\]]+)\]", out)
        choices = set(m.group(1).split("|"))
        for fmt in ("docx", "html", "pdf", "xlsx", "csv", "json",
                    "xml", "ipynb", "eml", "epub"):
            assert fmt in choices, (
                f"{fmt} missing from apply-md --target-format Choice"
            )

    def test_invalid_format_rejected(self):
        """A bogus target format must be rejected (click BadParameter)."""
        import os
        result = subprocess.run(
            [str(_VENV), "-m", "orf", "apply-md",
             "test_fixtures/zh/haier.epub",
             "--target-format", "bogus_format",
             "--output", "/tmp/bogus.out"],
            capture_output=True, text=True, env={
                "PYTHONPATH": str(_OL_SRC),
                "PATH": str(_VENV.parent) + ":" + os.environ.get("PATH", ""),
                "ORF_MCP_ALLOWED_DIRS": os.environ.get("ORF_MCP_ALLOWED_DIRS", "/tmp"),
            },
            timeout=15,
        )
        assert result.returncode != 0
        assert "bogus_format" in (result.stdout + result.stderr)