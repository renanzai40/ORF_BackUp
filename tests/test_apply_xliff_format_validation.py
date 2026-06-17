"""FIX-#8: apply-xliff must fail early on a mismatched skeleton.

Regression test for the round 5 fix that adds a format-preservation
check in ORF's `apply-xliff` CLI command. Before the fix, passing
a DOCX skeleton with `--format=odt` would crash deep in
translate-toolkit with an abstract error. After the fix, it raises
a clear click.BadParameter pointing to the format mismatch.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_ORF_SRC = Path(__file__).resolve().parents[1] / "Omni_Re_Formatter" / "src"
_VENV_PYTHON = Path(__file__).resolve().parents[2] / ".venv_ol" / "bin" / "python"


def _run_orf_cli(*args: str) -> subprocess.CompletedProcess:
    """Run ORF CLI as a subprocess (matches production invocation)."""
    cmd = [str(_VENV_PYTHON), "-m", "orf", *args]
    env_add = {"PYTHONPATH": str(_ORF_SRC)}
    import os
    env = {**os.environ, **env_add}
    return subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=30)


def test_apply_xliff_rejects_docx_skeleton_with_odt_format(tmp_path):
    """docx skeleton + --format=odt must fail fast with a clear message.

    Before FIX-#8, the call would proceed and crash in translate-toolkit
    with an abstract 'no content.xml' error. After the fix, it raises
    click.BadParameter before any I/O.
    """
    # Create fake skeleton + xlf + output paths (contents don't matter;
    # the format check fires before any file content is read).
    fake_skeleton = tmp_path / "input.docx"
    fake_skeleton.write_bytes(b"PK\x03\x04")  # zip magic (would be valid DOCX)
    fake_xlf = tmp_path / "translation.xlf"
    fake_xlf.write_text('<?xml version="1.0"?><xliff/>')
    output = tmp_path / "out.odt"

    result = _run_orf_cli(
        "apply-xliff", str(fake_skeleton),
        "--xliff", str(fake_xlf),
        "--output", str(output),
        "--format", "odt",
    )
    # Should fail with non-zero exit
    assert result.returncode != 0, (
        f"Expected non-zero exit on format mismatch; got {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    # Error message should mention the format mismatch
    combined = result.stdout + result.stderr
    assert "odt" in combined.lower(), (
        f"Error message should mention 'odt'; got: {combined}"
    )
    assert "format" in combined.lower() or "skeleton" in combined.lower(), (
        f"Error message should mention format or skeleton; got: {combined}"
    )


def test_apply_xliff_accepts_xlf_input_with_format(tmp_path):
    """`.xlf` or `.xliff` input is skeleton-agnostic — the format check skips.

    The check is permissive when the input is a generic XLIFF file
    (skeleton inferred from the --format value). The XLIFF dispatch
    in ORF handles this correctly via the ODF converter's separate
    skeleton discovery.
    """
    fake_xlf = tmp_path / "translation.xlf"
    fake_xlf.write_text('<?xml version="1.0"?><xliff/>')
    output = tmp_path / "out.docx"

    result = _run_orf_cli(
        "apply-xliff", str(fake_xlf),
        "--xliff", str(fake_xlf),
        "--output", str(output),
        "--format", "docx",
    )
    # We don't care about success/failure here — we just want to confirm
    # the early format check did NOT fire (no "format" / "skeleton" error).
    combined = result.stdout + result.stderr
    assert "does not match" not in combined, (
        f"Generic .xlf should bypass format check; got: {combined}"
    )
