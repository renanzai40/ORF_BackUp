"""E2E-79 regression tests.

The bug: MD2PPTXConverter.convert() called ``subprocess.run(['md2pptx', ...])``
without a pre-flight check. On a typical Linux box (no .NET SDK,
no /usr/local/bin/md2pptx) the binary is missing and subprocess
raised FileNotFoundError, which was caught and returned the
unhelpful error message 'md2pptx not installed or not in PATH'.
The user had no idea md2pptx is a .NET tool that needs a separate
install, so they hit a wall.

The fix: pre-flight ``shutil.which('md2pptx')`` check that fails
fast with an actionable install hint covering the three known paths
(.NET SDK tool, GitHub release binary, or pandoc fallback).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from orf.channels.md2pptx import MD2PPTXConverter, _md2pptx_install_hint
from orf.converters.base import ConversionResult
from orf.converters.options import ConverterOptions


@pytest.fixture
def input_md(tmp_path: Path) -> Path:
    p = tmp_path / "input.md"
    p.write_text("# Hello\n\nSlide content.\n", encoding="utf-8")
    return p


@pytest.fixture
def output_path(tmp_path: Path) -> Path:
    return tmp_path / "out.pptx"


class TestMd2PptxInstallHint:
    def test_hint_mentions_dotnet(self):
        hint = _md2pptx_install_hint()
        assert "dotnet" in hint

    def test_hint_mentions_github_releases(self):
        hint = _md2pptx_install_hint()
        assert "github.com" in hint or "MartinPacker" in hint

    def test_hint_mentions_pandoc_fallback(self):
        hint = _md2pptx_install_hint()
        assert "pandoc" in hint


class TestMd2PptxPreFlight:
    def test_missing_binary_returns_failure_with_hint(
        self, input_md: Path, output_path: Path, monkeypatch
    ):
        """E2E-79: when md2pptx is not on PATH, the converter must
        return a failure with the install hint (not a bare
        FileNotFoundError from subprocess)."""
        from orf.channels import md2pptx as md2pptx_mod

        monkeypatch.setattr(md2pptx_mod.shutil, "which", lambda _: None)
        result = MD2PPTXConverter().convert(input_md, output_path)
        assert result.success is False
        assert len(result.errors) == 1
        err = result.errors[0]
        err_str = getattr(err, "message", None) or str(err)
        assert "md2pptx" in err_str
        # Must mention at least one install path
        assert "dotnet" in err_str or "github.com" in err_str
        # Output file must NOT have been created
        assert not output_path.exists(), (
            f"Output file must not be created on failure. "
            f"Exists: {output_path}"
        )

    def test_present_binary_proceeds_to_subprocess(
        self, input_md: Path, output_path: Path, monkeypatch
    ):
        """When md2pptx is on PATH, the converter should call it."""
        from orf.channels import md2pptx as md2pptx_mod

        calls: list[list[str]] = []

        def fake_which(_: str) -> str | None:
            return "/usr/bin/md2pptx"

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            # Create the output file to simulate a successful run
            Path(cmd[2]).write_bytes(b"fake pptx")
            from subprocess import CompletedProcess
            return CompletedProcess(cmd, 0, stdout="ok", stderr="")

        monkeypatch.setattr(md2pptx_mod.shutil, "which", fake_which)
        monkeypatch.setattr(md2pptx_mod.subprocess, "run", fake_run)
        result = MD2PPTXConverter().convert(input_md, output_path)
        assert calls, "subprocess.run should have been called"
        assert calls[0][0] == "md2pptx"
        assert result.success is True
