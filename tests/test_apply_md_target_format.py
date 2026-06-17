"""Round 10 regression: apply-md --target-format Choice coverage.

Tier 3 surfaced that orf apply-md's --target-format Choice did not
include 'pptx' (it was in apply-xliff Choice but not apply-md).
Round 10 attempted to add pptx + MD2PPTXConverter wiring but
md2pptx binary is not installed by default, so the converter
fails with FileNotFoundError. Decision: keep pptx out of the
Choice (route pptx users to apply-xliff / P2 instead).

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
    result = subprocess.run(
        [str(_VENV), "-m", "orf", "apply-md", "--help"],
        capture_output=True, text=True, env={
            "PYTHONPATH": str(_OL_SRC),
            "PATH": str(_VENV.parent) + ":" + __import__("os").environ.get("PATH", ""),
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
        # 16 = auto + 15 formats (pptx excluded, requires md2pptx binary)
        assert len(choices) == 16, (
            f"Expected 16 target-format choices, got {len(choices)}: {choices}"
        )

    def test_pptx_excluded_from_choices(self):
        """PPTX must NOT be in --target-format Choice (round 10 decision:
        apply-md requires md2pptx binary which is not installed by
        default; use apply-xliff for PPTX)."""
        out = _run_apply_md_help()
        m = re.search(r"--target-format \[([^\]]+)\]", out)
        assert m
        choices = m.group(1).split("|")
        assert "pptx" not in choices, (
            f"pptx should be excluded; if adding it back, ensure md2pptx "
            f"binary is available (which: md2pptx). Got: {choices}"
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
        result = subprocess.run(
            [str(_VENV), "-m", "orf", "apply-md",
             "test_fixtures/zh/haier.epub",
             "--target-format", "bogus_format",
             "--output", "/tmp/bogus.out"],
            capture_output=True, text=True, env={
                "PYTHONPATH": str(_OL_SRC),
                "PATH": str(_VENV.parent) + ":" + __import__("os").environ.get("PATH", ""),
            },
            timeout=15,
        )
        assert result.returncode != 0
        assert "bogus_format" in (result.stdout + result.stderr)