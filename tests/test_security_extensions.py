"""T2 — ALLOWED_EXTENSIONS enforcement in PathValidator.validate().

Omni Suite ship-ready remediation plan v2, P0 critical security fix.

These tests assert the exact `(is_valid, error_message)` tuple that
``PathValidator.validate`` returns for paths with allowed vs. disallowed
extensions. Prior to the fix, ``validate()`` never consulted
``ALLOWED_EXTENSIONS`` and every well-formed path passed, including
``.exe`` and ``.sh`` — a P0 path-traversal-adjacent bypass.
"""
import sys
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).parent.parent
_ORF_SRC = _REPO_ROOT / "src"
if str(_ORF_SRC) not in sys.path:
    sys.path.insert(0, str(_ORF_SRC))


from orf.mcp.security import PathValidator  # noqa: E402


# ---------------------------------------------------------------------------
# Exact tuple equality cases
# ---------------------------------------------------------------------------


def test_docx_extension_returns_exact_allowed_tuple(tmp_path: Path) -> None:
    """.docx is in ALLOWED_EXTENSIONS → (True, '')."""
    target = tmp_path / "report.docx"
    target.write_text("placeholder")
    result = PathValidator.validate(str(target), base_dir=tmp_path)
    assert result == (True, ""), f"expected (True, ''), got {result!r}"


def test_exe_extension_returns_exact_blocked_tuple(tmp_path: Path) -> None:
    """.exe is NOT in ALLOWED_EXTENSIONS → blocked with exact error string."""
    target = tmp_path / "malware.exe"
    target.write_text("placeholder")
    result = PathValidator.validate(str(target), base_dir=tmp_path)
    assert result == (False, "Extension '.exe' not in allowed set"), (
        f"expected blocked tuple, got {result!r}"
    )


def test_xliff_extension_returns_exact_allowed_tuple(tmp_path: Path) -> None:
    """.xliff is in ALLOWED_EXTENSIONS → (True, '')."""
    target = tmp_path / "translation.xliff"
    target.write_text("placeholder")
    result = PathValidator.validate(str(target), base_dir=tmp_path)
    assert result == (True, ""), f"expected (True, ''), got {result!r}"


def test_sh_extension_returns_exact_blocked_tuple(tmp_path: Path) -> None:
    """.sh is NOT in ALLOWED_EXTENSIONS → blocked with exact error string."""
    target = tmp_path / "script.sh"
    target.write_text("placeholder")
    result = PathValidator.validate(str(target), base_dir=tmp_path)
    assert result == (False, "Extension '.sh' not in allowed set"), (
        f"expected blocked tuple, got {result!r}"
    )


# ---------------------------------------------------------------------------
# Sanity: the entire ALLOWED_EXTENSIONS set is enforced (parametrized guard).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ext",
    [".md", ".docx", ".pptx", ".xliff", ".xml", ".html", ".odt", ".epub"],
)
def test_every_allowed_extension_passes(tmp_path: Path, ext: str) -> None:
    """Every declared ALLOWED_EXTENSIONS entry must return (True, '')."""
    target = tmp_path / f"file{ext}"
    target.write_text("placeholder")
    result = PathValidator.validate(str(target), base_dir=tmp_path)
    assert result == (True, ""), f"extension {ext} should be allowed, got {result!r}"
