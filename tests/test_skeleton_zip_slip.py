"""RED→GREEN tests for skeleton loader zip-slip protection (W1.1 + W1.2).

Tests the 4 rejection cases (parent-dir, absolute-unix, absolute-windows, backslash-traversal)
and 2 acceptance cases for the SkeletonLoader, plus 4 channel-level tests for the
xliff2pptx and xliff2epub _load_* and inject_images bypass paths.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from orf.channels.xliff2epub import XLIFF2EPUBConverter
from orf.channels.xliff2pptx import XLIFF2PPTXConverter
from orf.mcp.schemas import ImagePlacement
from orf.skeleton.skeleton_loader import SkeletonLoader


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _make_skeleton_with_entry(workdir: Path, entry_name: str, content: bytes = b"x") -> Path:
    """Helper: build a ZIP skeleton with one entry that has the given name."""
    p = workdir / "skeleton.zip"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr(entry_name, content)
    return p


def _make_malicious_pptx_skeleton(workdir: Path) -> Path:
    """Create a PPTX-shaped skeleton with a zip-slip entry."""
    skel = workdir / "malicious.pptx"
    with zipfile.ZipFile(skel, "w") as zf:
        zf.writestr("ppt/slides/slide1.xml", b"<s/>")
        zf.writestr("../../etc/passwd", b"x")  # malicious entry
    return skel


def _make_malicious_epub_skeleton(workdir: Path) -> Path:
    """Create an EPUB-shaped skeleton with a zip-slip entry."""
    skel = workdir / "malicious.epub"
    with zipfile.ZipFile(skel, "w") as zf:
        zf.writestr("EPUB/content.xhtml", b"<html/>")
        zf.writestr("../../etc/passwd", b"x")  # malicious entry
    return skel


def _make_valid_xliff(workdir: Path) -> Path:
    """Create a minimal valid XLIFF file."""
    xlf = workdir / "test.xlf"
    xlf.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2" version="1.2">\n'
        '  <file source-language="en" target-language="zh" original="test">\n'
        '    <body>\n'
        '      <trans-unit id="1">\n'
        '        <source>Hello</source>\n'
        '        <target>你好</target>\n'
        '      </trans-unit>\n'
        '    </body>\n'
        '  </file>\n'
        '</xliff>\n'
    )
    return xlf


def _make_unpositioned_image() -> ImagePlacement:
    """Create an ImagePlacement with no position fields (triggers bypass path)."""
    return ImagePlacement(
        mime_type="image/png",
        data_base64="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk",
    )


# ---------------------------------------------------------------------------
# W1.1 — SkeletonLoader rejection tests (RED: fail before fix)
# ---------------------------------------------------------------------------

class TestZipSlipRejected:
    """W1.1: SkeletonLoader.load_skeleton must reject malicious ZIP entries."""

    def test_rejects_parent_dir_traversal(self, tmp_path: Path) -> None:
        """Entry like '../../etc/passwd' must be rejected with ValueError."""
        skel = _make_skeleton_with_entry(tmp_path, "../../etc/passwd")
        loader = SkeletonLoader()
        with pytest.raises(ValueError, match="parent-directory"):
            loader.load_skeleton(str(skel))

    def test_rejects_absolute_unix_path(self, tmp_path: Path) -> None:
        """Entry starting with '/' must be rejected with ValueError."""
        skel = _make_skeleton_with_entry(tmp_path, "/etc/passwd")
        loader = SkeletonLoader()
        with pytest.raises(ValueError, match="absolute paths"):
            loader.load_skeleton(str(skel))

    def test_rejects_absolute_windows_path(self, tmp_path: Path) -> None:
        """Entry like 'C:\\Windows\\foo' must be rejected with ValueError."""
        skel = _make_skeleton_with_entry(tmp_path, "C:\\Windows\\foo")
        loader = SkeletonLoader()
        with pytest.raises(ValueError, match="absolute paths"):
            loader.load_skeleton(str(skel))

    def test_rejects_backslash_traversal(self, tmp_path: Path) -> None:
        """Entry with '..\\..\\foo' (Windows-style) must be rejected."""
        skel = _make_skeleton_with_entry(tmp_path, "..\\..\\foo")
        loader = SkeletonLoader()
        with pytest.raises(ValueError, match="parent-directory"):
            loader.load_skeleton(str(skel))


# ---------------------------------------------------------------------------
# W1.1 — SkeletonLoader acceptance tests
# ---------------------------------------------------------------------------

class TestValidEntriesAccepted:
    """W1.1: Valid entries must NOT be rejected by the zip-slip guard."""

    def test_accepts_normal_word_document(self, tmp_path: Path) -> None:
        """Valid 'word/document.xml' entry must be loaded without error."""
        skel = _make_skeleton_with_entry(tmp_path, "word/document.xml", b"<doc/>")
        loader = SkeletonLoader()
        loader.load_skeleton(str(skel))
        assert "word/document.xml" in loader.files

    def test_accepts_nested_path(self, tmp_path: Path) -> None:
        """Valid nested path like 'ppt/slides/slide1.xml' must load OK."""
        skel = _make_skeleton_with_entry(tmp_path, "ppt/slides/slide1.xml", b"<s/>")
        loader = SkeletonLoader()
        loader.load_skeleton(str(skel))
        assert "ppt/slides/slide1.xml" in loader.files


# ---------------------------------------------------------------------------
# W1.2 — Channel-level rejection tests (xliff2pptx + xliff2epub)
# ---------------------------------------------------------------------------

class TestChannelZipSlipRejected:
    """W1.2: Each XLIFF channel must reject malicious skeletons at all read points."""

    # — xliff2pptx tests ————————————————————————————————————————————————

    def test_xliff2pptx_load_rejects_traversal(self, tmp_path: Path) -> None:
        """W1.2: xliff2pptx _load_pptx_skeleton rejects malicious ZIP."""
        skel = _make_malicious_pptx_skeleton(tmp_path)
        xlf = _make_valid_xliff(tmp_path)
        output = tmp_path / "result.pptx"

        converter = XLIFF2PPTXConverter()
        result = converter.convert(skel, xlf, output)
        assert result.success is False
        combined = " ".join(e.message for e in result.errors)
        assert "parent-directory" in combined.lower() or "absolute" in combined.lower()

    def test_xliff2pptx_inject_images_bypass_rejects_traversal(
        self, tmp_path: Path
    ) -> None:
        """W1.2: xliff2pptx inject_images bypass path rejects malicious ZIP."""
        skel = _make_malicious_pptx_skeleton(tmp_path)
        output = tmp_path / "result.pptx"

        converter = XLIFF2PPTXConverter()
        # Unpositioned image triggers the bypass (line ~500-503)
        img = _make_unpositioned_image()
        with pytest.raises(ValueError, match="parent-directory|absolute"):
            converter.inject_images(skel, [img], output)

    # — xliff2epub tests —————————————————————————————————————————————————

    def test_xliff2epub_load_rejects_traversal(self, tmp_path: Path) -> None:
        """W1.2: xliff2epub _load_epub_skeleton rejects malicious ZIP."""
        skel = _make_malicious_epub_skeleton(tmp_path)
        xlf = _make_valid_xliff(tmp_path)
        output = tmp_path / "result.epub"

        converter = XLIFF2EPUBConverter()
        result = converter.convert(skel, xlf, output)
        assert result.success is False
        combined = " ".join(e.message for e in result.errors)
        assert "parent-directory" in combined.lower() or "absolute" in combined.lower()

    def test_xliff2epub_inject_images_bypass_rejects_traversal(
        self, tmp_path: Path
    ) -> None:
        """W1.2: xliff2epub inject_images bypass path rejects malicious ZIP."""
        skel = _make_malicious_epub_skeleton(tmp_path)
        output = tmp_path / "result.epub"

        converter = XLIFF2EPUBConverter()
        # Unpositioned image triggers the bypass (line ~432-435)
        img = _make_unpositioned_image()
        with pytest.raises(ValueError, match="parent-directory|absolute"):
            converter.inject_images(skel, [img], output)
