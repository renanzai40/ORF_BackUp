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

_ORF_SRC = Path(__file__).resolve().parents[1] / "src"
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


class TestZipSkeletonAccepted:
    """FIX-#8 round 9: OPP packages skeleton as .zip; ORF must accept.

    Without this fix, OPP's `skeleton.zip` is rejected by ORF's
    format-preservation check (`.zip != .docx` for --format=docx).
    e2e_runner.py Tier 2 run caught this on xliff_cli path.
    """

    def test_zip_skeleton_with_format_docx_accepted(self, tmp_path):
        """`.zip` skeleton + --format=docx must be accepted.

        OPP produces `skeleton.zip` from DOCX inputs; this is the
        canonical skeleton source. ORF's skeleton loader handles it.
        The round 5 FIX-#8 guard was too strict; round 9 extends it.
        """
        fake_skeleton = tmp_path / "input.skeleton.zip"
        fake_skeleton.write_bytes(b"PK\x03\x04")  # zip magic
        fake_xlf = tmp_path / "translation.xlf"
        fake_xlf.write_text('<?xml version="1.0"?><xliff/>')
        output = tmp_path / "out.docx"

        result = _run_orf_cli(
            "apply-xliff", str(fake_skeleton),
            "--xliff", str(fake_xlf),
            "--output", str(output),
            "--format", "docx",
        )
        # The guard must NOT fire — expect rc=0 OR rc != 2 (rc=2 is the
        # BadParameter exit code). We accept any other outcome (real
        # ORF execution may fail for unrelated reasons in tests).
        assert "does not match" not in (result.stdout + result.stderr), (
            f".zip skeleton rejected by round 5 guard; round 9 should "
            f"have extended it:\n{result.stdout}\n{result.stderr}"
        )

    def test_pptx_skeleton_with_format_docx_still_rejected(self, tmp_path):
        """Cross-format (pptx + docx) must still be rejected."""
        fake_skeleton = tmp_path / "input.pptx"
        fake_skeleton.write_bytes(b"PK\x03\x04")
        fake_xlf = tmp_path / "translation.xlf"
        fake_xlf.write_text('<?xml version="1.0"?><xliff/>')
        output = tmp_path / "out.docx"

        result = _run_orf_cli(
            "apply-xliff", str(fake_skeleton),
            "--xliff", str(fake_xlf),
            "--output", str(output),
            "--format", "docx",
        )
        combined = result.stdout + result.stderr
        assert "does not match" in combined, (
            f"Cross-format pptx→docx must be rejected; got:\n{combined}"
        )

    def test_html_skeleton_with_format_docx_still_rejected(self, tmp_path):
        """html + docx cross-format: OPP doesn't produce .zip for HTML,
        so HTML skeleton with --format=docx must be rejected."""
        fake_skeleton = tmp_path / "input.html"
        fake_skeleton.write_text("<html></html>")
        fake_xlf = tmp_path / "translation.xlf"
        fake_xlf.write_text('<?xml version="1.0"?><xliff/>')
        output = tmp_path / "out.docx"

        result = _run_orf_cli(
            "apply-xliff", str(fake_skeleton),
            "--xliff", str(fake_xlf),
            "--output", str(output),
            "--format", "docx",
        )
        combined = result.stdout + result.stderr
        assert "does not match" in combined, (
            f"HTML→DOCX cross-format must be rejected:\n{combined}"
        )


class TestForceFlag:
    """W2.2: --force flag bypasses skeleton format validation with a warning."""

    def test_force_bypasses_validation(self, tmp_path):
        """--force allows cross-format skeleton/format mismatch to proceed."""
        skeleton = tmp_path / "input.pptx"
        skeleton.write_bytes(b"PK\x03\x04")
        xlf = tmp_path / "translation.xlf"
        xlf.write_text('<?xml version="1.0"?><xliff/>')
        output = tmp_path / "out.docx"

        # Without --force: should fail with format mismatch
        result = _run_orf_cli(
            "apply-xliff", str(skeleton),
            "--xliff", str(xlf),
            "--output", str(output),
            "--format", "docx",
        )
        assert result.returncode != 0
        combined = result.stdout + result.stderr
        assert "does not match" in combined, (
            f"Expected format rejection without --force; got:\n{combined}"
        )

        # With --force: should NOT fail with the BadParameter rejection
        # (it may still fail for other reasons, but the FORCE MODE warning is present)
        result = _run_orf_cli(
            "apply-xliff", str(skeleton),
            "--xliff", str(xlf),
            "--output", str(output),
            "--format", "docx",
            "--force",
        )
        combined = result.stdout + result.stderr
        # BadParameter produces "Error: Invalid value:" — must be absent
        assert "Invalid value" not in combined, (
            f"--force should bypass BadParameter; got:\n{combined}"
        )
        # FORCE MODE warning must be present
        assert "FORCE MODE" in combined, (
            f"--force should emit warning; got:\n{combined}"
        )

    def test_force_produces_warning_on_mismatch(self, tmp_path):
        """--force emits a clear warning when bypassing format validation."""
        skeleton = tmp_path / "input.pptx"
        skeleton.write_bytes(b"PK\x03\x04")
        xlf = tmp_path / "translation.xlf"
        xlf.write_text('<?xml version="1.0"?><xliff/>')
        output = tmp_path / "out.docx"

        result = _run_orf_cli(
            "apply-xliff", str(skeleton),
            "--xliff", str(xlf),
            "--output", str(output),
            "--format", "docx",
            "--force",
        )
        combined = result.stdout + result.stderr
        assert "FORCE MODE" in combined or "force" in combined.lower(), (
            f"--force warning not produced; got:\n{combined}"
        )


# ── Helpers for skeleton content-level validation tests ────────────────

_DOCX_SKELETON_DOCUMENT = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p>
      <w:r>
        <w:t>Hello World</w:t>
      </w:r>
    </w:p>
  </w:body>
</w:document>
"""


def _create_docx_skeleton_zip(path: Path) -> None:
    """Create a minimal DOCX skeleton ZIP for testing."""
    import zipfile

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("word/document.xml", _DOCX_SKELETON_DOCUMENT)
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
            '  <Default Extension="xml" ContentType="application/xml"/>\n'
            '</Types>',
        )


def _create_pptx_skeleton_zip(path: Path) -> None:
    """Create a minimal PPTX skeleton ZIP for testing."""
    import zipfile

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "ppt/presentation.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"/>',
        )


def _create_xliff(path: Path, source: str = "Hello World", target: str = "Hello World") -> None:
    """Create a minimal XLIFF file for testing."""
    path.write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">\n'
        f'  <file source-language="en" target-language="zh" datatype="plaintext">\n'
        f'    <body>\n'
        f'      <trans-unit id="1">\n'
        f'        <source>{source}</source>\n'
        f'        <target>{target}</target>\n'
        f'      </trans-unit>\n'
        f'    </body>\n'
        f'  </file>\n'
        f'</xliff>'
    )


class TestSkeletonContentValidation:
    """Content-level validation for ZIP skeletons.

    Peek inside .skeleton.zip files via FormatDetector.detect_from_skeleton()
    to verify the actual format matches --format, not just the file extension.
    """

    def test_docx_skeleton_rejects_pptx_format_without_force(self, tmp_path):
        """DOCX skeleton .zip with --format pptx must fail with skeleton error."""
        skeleton = tmp_path / "input.skeleton.zip"
        _create_docx_skeleton_zip(skeleton)
        xlf = tmp_path / "translation.xlf"
        _create_xliff(xlf)
        output = tmp_path / "out.pptx"

        result = _run_orf_cli(
            "apply-xliff", str(skeleton),
            "--xliff", str(xlf),
            "--output", str(output),
            "--format", "pptx",
        )
        assert result.returncode != 0, (
            f"Expected non-zero exit on format mismatch; got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        combined = result.stdout + result.stderr
        assert "Skeleton" in combined, (
            f"Error message should contain 'Skeleton'; got:\n{combined}"
        )

    def test_docx_skeleton_accepts_docx_format(self, tmp_path):
        """DOCX skeleton .zip with --format docx must succeed."""
        skeleton = tmp_path / "input.skeleton.zip"
        _create_docx_skeleton_zip(skeleton)
        xlf = tmp_path / "translation.xlf"
        _create_xliff(xlf, source="Hello World", target="Hello World")
        output = tmp_path / "out.docx"

        result = _run_orf_cli(
            "apply-xliff", str(skeleton),
            "--xliff", str(xlf),
            "--output", str(output),
            "--format", "docx",
        )
        assert result.returncode == 0, (
            f"Expected exit code 0 for matching format; got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_docx_skeleton_accepts_pptx_with_force(self, tmp_path):
        """DOCX skeleton .zip with --format pptx --force must succeed with warning."""
        skeleton = tmp_path / "input.skeleton.zip"
        _create_docx_skeleton_zip(skeleton)
        xlf = tmp_path / "translation.xlf"
        _create_xliff(xlf, source="Hello World", target="Hello World")
        output = tmp_path / "out.pptx"

        result = _run_orf_cli(
            "apply-xliff", str(skeleton),
            "--xliff", str(xlf),
            "--output", str(output),
            "--format", "pptx",
            "--force",
        )
        combined = result.stdout + result.stderr
        assert "FORCE MODE" in combined, (
            f"--force should produce FORCE MODE warning; got:\n{combined}"
        )
        # BadParameter produces "Error: Invalid value:" — must be absent
        assert "Invalid value" not in combined, (
            f"--force should bypass BadParameter; got:\n{combined}"
        )

    def test_ppt_skeleton_rejects_docx_format(self, tmp_path):
        """PPTX skeleton .zip with --format docx must fail with skeleton error."""
        skeleton = tmp_path / "input.skeleton.zip"
        _create_pptx_skeleton_zip(skeleton)
        xlf = tmp_path / "translation.xlf"
        _create_xliff(xlf)
        output = tmp_path / "out.docx"

        result = _run_orf_cli(
            "apply-xliff", str(skeleton),
            "--xliff", str(xlf),
            "--output", str(output),
            "--format", "docx",
        )
        assert result.returncode != 0, (
            f"Expected non-zero exit on format mismatch; got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        combined = result.stdout + result.stderr
        assert "Skeleton" in combined, (
            f"Error message should contain 'Skeleton'; got:\n{combined}"
        )
