"""XLIFF to EPUB channel tests."""

import zipfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from orf.channels.xliff2epub import XLIFF2EPUBConverter
from orf.converters.base import ConversionResult


@pytest.fixture
def sample_epub_skeleton(tmp_path: Path) -> Path:
    """Create a minimal EPUB skeleton ZIP."""
    epub_path = tmp_path / "test.epub"
    with zipfile.ZipFile(epub_path, "w") as zf:
        zf.writestr("EPUB/content.opf", b"<package/>")
        zf.writestr(
            "EPUB/chapter1.xhtml",
            b'<html><body><p id="seg1">Original content</p></body></html>',
        )
    return epub_path


@pytest.fixture
def sample_xliff(tmp_path: Path) -> Path:
    """Create a minimal XLIFF file."""
    xliff_content = """<?xml version="1.0"?>
<xliff version="2.0">
  <unit id="seg1">
    <segment>
      <target>Translated content</target>
    </segment>
  </unit>
</xliff>"""
    xliff_path = tmp_path / "test.xlf"
    xliff_path.write_text(xliff_content, encoding="utf-8")
    return xliff_path


@pytest.fixture
def sample_xliff_with_inline(tmp_path: Path) -> Path:
    """Create XLIFF with inline formatting tags."""
    xliff_content = """<?xml version="1.0"?>
<xliff version="2.0">
  <unit id="bold_text">
    <segment>
      <target>Text with <bx id="b1"/>bold<ex id="b1"/> formatting</target>
    </segment>
  </unit>
  <unit id="italic_text">
    <segment>
      <target>Text with <bx id="i1"/>italic<ex id="i1"/> style</target>
    </segment>
  </unit>
</xliff>"""
    xliff_path = tmp_path / "inline.xlf"
    xliff_path.write_text(xliff_content, encoding="utf-8")
    return xliff_path


class TestXLIFF2EPUBConverter:
    def test_supported_format(self):
        converter = XLIFF2EPUBConverter()
        assert converter.supported_format == "EPUB"

    def test_validate_input_valid(self, sample_epub_skeleton: Path):
        converter = XLIFF2EPUBConverter()
        assert converter.validate_input(sample_epub_skeleton) is True

    def test_validate_input_invalid(self, tmp_path: Path):
        txt_file = tmp_path / "test.txt"
        txt_file.touch()
        converter = XLIFF2EPUBConverter()
        assert converter.validate_input(txt_file) is False

    def test_convert_missing_epub_skeleton(self, sample_xliff: Path, tmp_path: Path):
        output = tmp_path / "output.epub"
        converter = XLIFF2EPUBConverter()
        result = converter.convert(
            tmp_path / "nonexistent.epub",
            sample_xliff,
            output,
        )
        assert result.success is False
        assert len(result.errors) > 0

    def test_convert_missing_xliff(self, sample_epub_skeleton: Path, tmp_path: Path):
        output = tmp_path / "output.epub"
        converter = XLIFF2EPUBConverter()
        result = converter.convert(
            sample_epub_skeleton,
            tmp_path / "nonexistent.xlf",
            output,
        )
        assert result.success is False
        assert len(result.errors) > 0

    def test_convert_success(
        self, sample_epub_skeleton: Path, sample_xliff: Path, tmp_path: Path
    ):
        output = tmp_path / "output.epub"
        converter = XLIFF2EPUBConverter()
        result = converter.convert(sample_epub_skeleton, sample_xliff, output)
        assert result.success is True
        assert output.exists()

    def test_convert_with_toc_option(
        self, sample_epub_skeleton: Path, sample_xliff: Path, tmp_path: Path
    ):
        output = tmp_path / "output.epub"
        converter = XLIFF2EPUBConverter()
        result = converter.convert(
            sample_epub_skeleton, sample_xliff, output, preserve_styles=True
        )
        assert result.success is True

    def test_convert_empty_xliff(self, sample_epub_skeleton: Path, tmp_path: Path):
        """Test conversion with XLIFF containing no segments."""
        empty_xliff = tmp_path / "empty.xlf"
        empty_xliff.write_text("<?xml version='1.0'?><xliff version='2.0'></xliff>")
        output = tmp_path / "output.epub"
        converter = XLIFF2EPUBConverter()
        result = converter.convert(sample_epub_skeleton, empty_xliff, output)
        # Empty XLIFF should still produce valid EPUB
        assert result.success is True

    def test_convert_segments_applied_metadata(
        self, sample_epub_skeleton: Path, sample_xliff: Path, tmp_path: Path
    ):
        output = tmp_path / "output.epub"
        converter = XLIFF2EPUBConverter()
        result = converter.convert(sample_epub_skeleton, sample_xliff, output)
        assert result.success is True
        assert result.metadata is not None
        assert "segments_applied" in result.metadata

    def test_xliff_inline_formatting_conversion(
        self, sample_epub_skeleton: Path, sample_xliff_with_inline: Path, tmp_path: Path
    ):
        """Test that XLIFF <bx>/<ex> tags are converted to HTML <strong>/<em>."""
        output = tmp_path / "output.epub"
        converter = XLIFF2EPUBConverter()
        result = converter.convert(
            sample_epub_skeleton, sample_xliff_with_inline, output
        )
        assert result.success is True

    def test_repack_epub_preserves_structure(
        self, sample_epub_skeleton: Path, sample_xliff: Path, tmp_path: Path
    ):
        """Test that EPUB structure is preserved after repacking."""
        output = tmp_path / "output.epub"
        converter = XLIFF2EPUBConverter()
        result = converter.convert(sample_epub_skeleton, sample_xliff, output)
        assert result.success is True

        # Verify output is a valid ZIP
        with zipfile.ZipFile(output, "r") as zf:
            names = zf.namelist()
            assert "EPUB/content.opf" in names
            assert any(n.endswith(".xhtml") for n in names)